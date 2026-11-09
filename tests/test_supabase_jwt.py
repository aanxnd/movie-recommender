"""Offline JWT adversarial cases: ephemeral signing keys, never hosted credentials."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app import supabase_jwt as auth

ORIGIN = "https://" + "a" * 20 + ".supabase.co"
SUBJECT = "12345678-1234-4234-9234-123456789abc"


@pytest.fixture
def setup():
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="first", alg="ES256", use="sig", key_ops=["verify"])
    clock, calls, document = [0], [], {"keys": [jwk]}
    def fetch(url):
        calls.append(url)
        return json.dumps(document).encode()
    verifier = auth.SupabaseTokenVerifier(ORIGIN, fetch=fetch, clock=lambda: clock[0])
    def token(changes=None, headers=None, key=None):
        claims = dict(iss=ORIGIN + "/auth/v1", aud="authenticated", sub=SUBJECT,
                      exp=int(time.time()) + 600, iat=int(time.time()) - 10, role="authenticated")
        claims.update(changes or {})
        # Raw JWS signing lets tests supply intentionally invalid JWT claim types.
        return jwt.PyJWS().encode(json.dumps(claims).encode(), key or private, algorithm="ES256",
                                 headers={"kid": "first", **(headers or {})})
    return verifier, token, document, clock, calls


def test_valid_token_and_cache_do_not_imply_email_or_database_access(setup):
    verifier, token, _, _, calls = setup
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(verifier.verify, [token({"email": "unverified@example.invalid", "nbf": 1})] * 8)) == [UUID(SUBJECT)] * 8
    assert calls == [ORIGIN + "/auth/v1/.well-known/jwks.json"]


@pytest.mark.parametrize("changes", [
    {"iss": ORIGIN}, {"iss": ORIGIN + "/auth/v1/"}, {"aud": "other"},
    {"aud": ["authenticated", "other"]}, {"exp": 1}, {"nbf": 2**40},
    {"iat": 2**40}, {"exp": None}, {"exp": True}, {"exp": "9999999999"},
    {"sub": "bad"}, {"sub": SUBJECT.replace("-", "")}, {"sub": "00000000-0000-0000-0000-000000000000"},
    {"role": "service_role"}, {"iss": None}, {"aud": None}, {"sub": None}, {"iat": None}, {"role": None},
])
def test_invalid_claims_rejected(setup, changes):
    verifier, token, *_ = setup
    with pytest.raises(auth.InvalidAccessToken, match="^Invalid access token$"):
        verifier.verify(token(changes))


@pytest.mark.parametrize("claim", ["iss", "aud", "exp", "iat", "sub", "role"])
def test_missing_required_claim(setup, claim):
    verifier, token, *_ = setup
    payload = jwt.decode(token(), options={"verify_signature": False})
    del payload[claim]
    key = ec.generate_private_key(ec.SECP256R1())
    # Make a matching trusted test key so rejection exercises the missing claim.
    verifier._fetch = lambda url: json.dumps({"keys": [dict(json.loads(jwt.algorithms.ECAlgorithm.to_jwk(
        key.public_key())), kid="first", alg="ES256")]}).encode()
    with pytest.raises(auth.InvalidAccessToken):
        verifier.verify(jwt.encode(payload, key, algorithm="ES256", headers={"kid": "first"}))


@pytest.mark.parametrize("headers", [{"kid": "unknown"}, {"kid": ""}, {"typ": "other"},
    {"jku": "https://attacker.invalid"}, {"x5u": "https://attacker.invalid"}, {"jwk": {}}, {"x5c": []}, {"crit": ["custom"]}])
def test_untrusted_headers_and_urls_rejected(setup, headers):
    verifier, token, _, _, calls = setup
    with pytest.raises(auth.InvalidAccessToken): verifier.verify(token(headers=headers))
    assert all(url == verifier.jwks_url for url in calls)


@pytest.mark.parametrize("value", [None, "", "not.jwt", "x" * 8193,
    jwt.encode({"sub": SUBJECT}, "synthetic-test-only-secret-32bytes", algorithm="HS256"),
    jwt.encode({"sub": SUBJECT}, None, algorithm="none")])
def test_malformed_or_unsupported_algorithm_never_fetches(setup, value):
    verifier, _, _, _, calls = setup
    with pytest.raises(auth.InvalidAccessToken): verifier.verify(value)
    assert calls == []


def test_invalid_signature_and_sanitized_errors(setup, caplog):
    verifier, token, *_ = setup
    value = token(key=ec.generate_private_key(ec.SECP256R1()))
    with pytest.raises(auth.InvalidAccessToken) as error: verifier.verify(value)
    assert str(error.value) == "Invalid access token" and not caplog.records
    assert value not in str(error.value) and SUBJECT not in str(error.value)


def test_other_asymmetric_algorithm_rejected_before_fetch(setup):
    verifier, token, _, _, calls = setup
    value = token(headers={"alg": "ES384"}, key=ec.generate_private_key(ec.SECP384R1()))
    with pytest.raises(auth.InvalidAccessToken): verifier.verify(value)
    assert calls == []


@pytest.mark.parametrize("change", [{"crv": "P-384"}, {"key_ops": ["sign"]}, {"d": "fake"}, {"x": "bad"}, "duplicate"])
def test_unsafe_or_ambiguous_jwk_rejected(setup, change):
    verifier, token, document, *_ = setup
    if change == "duplicate": document["keys"].append(document["keys"][0].copy())
    else: document["keys"][0].update(change)
    with pytest.raises(auth.SigningKeysUnavailable): verifier.verify(token())


@pytest.mark.parametrize("body", [b"bad json", b"[]", b"{}", b'{"keys":[]}',
    b'{"keys":[null]}', b'{"keys":[{"kid":"a","alg":"HS256"}]}', b" " * 65537],
    ids=["json", "array", "missing", "empty", "null-key", "symmetric", "oversized"])
def test_malformed_jwks_fails_closed(setup, body):
    verifier, token, *_ = setup
    verifier._fetch = lambda url: body
    with pytest.raises(auth.SigningKeysUnavailable, match="^Signing keys unavailable$"):
        verifier.verify(token())


def test_rotation_unknown_kid_cooldown_and_expired_cache_outage(setup):
    verifier, token, document, clock, calls = setup
    original = token()
    assert verifier.verify(original) == UUID(SUBJECT)
    replacement = ec.generate_private_key(ec.SECP256R1())
    rotated = token(headers={"kid": "second"}, key=replacement)
    document["keys"] = [dict(json.loads(jwt.algorithms.ECAlgorithm.to_jwk(replacement.public_key())), kid="second", alg="ES256")]
    for _ in range(4):
        with pytest.raises(auth.InvalidAccessToken): verifier.verify(rotated)
    assert len(calls) == 1
    clock[0] = 30
    assert verifier.verify(rotated) == UUID(SUBJECT) and len(calls) == 2
    with pytest.raises(auth.InvalidAccessToken): verifier.verify(original)
    def unavailable(url): raise TimeoutError("upstream diagnostic must stay private")
    verifier._fetch = unavailable
    clock[0] = 330
    with pytest.raises(auth.SigningKeysUnavailable): verifier.verify(rotated)
    with pytest.raises(auth.SigningKeysUnavailable): verifier.verify(rotated)
    clock[0] = 360
    verifier._fetch = lambda url: json.dumps(document).encode()
    assert verifier.verify(rotated) == UUID(SUBJECT)


def test_download_timeout_redirect_policy_and_size(monkeypatch):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            assert size == 65537
            return b"x" * size
    class Opener:
        def open(self, request, timeout):
            assert timeout == 3 and request.full_url == ORIGIN + "/auth/v1/.well-known/jwks.json"
            assert "Authorization" not in request.headers
            return Response()
    monkeypatch.setattr(auth, "build_opener", lambda *handlers: Opener())
    with pytest.raises(ValueError, match="too large"): auth._download(ORIGIN + "/auth/v1/.well-known/jwks.json")
    assert auth._NoRedirect().redirect_request(None, None, 302, "", {}, "https://attacker.invalid") is None


@pytest.mark.parametrize("url", ["http://" + ORIGIN[8:], ORIGIN + "/rest/v1/", ORIGIN + "?x=y", "https://user:secret@host.invalid"])
def test_configuration_rejects_unpinned_origins(url):
    with pytest.raises(ValueError): auth.SupabaseTokenVerifier(url)
