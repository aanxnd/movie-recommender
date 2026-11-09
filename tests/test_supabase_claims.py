"""Offline typed evidence: real local signatures, no provider or database state."""
from dataclasses import FrozenInstanceError
import json
import time
import traceback
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
import jwt
import pytest

from app import supabase_jwt as auth
from test_supabase_jwt import ORIGIN


@pytest.fixture
def evidence():
    private = ec.generate_private_key(ec.SECP256R1())
    public = dict(json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key())), kid="local", alg="ES256")
    now, subject, session_id, calls = int(time.time()), uuid4(), uuid4(), []
    document, clock = {"keys": [public]}, [0]
    def fetch(url):
        assert url == ORIGIN + "/auth/v1/.well-known/jwks.json"
        calls.append(url)
        return json.dumps(document).encode()
    verifier = auth.SupabaseTokenVerifier(ORIGIN, fetch=fetch, clock=lambda: clock[0])
    def sign(changes=None, *, omit=(), key=None, headers=None, raw_edit=lambda value: value):
        claims = dict(iss=ORIGIN + "/auth/v1", aud="authenticated", role="authenticated",
                      sub=str(subject), session_id=str(session_id), aal="aal1", iat=now-10, exp=now+600,
                      amr=[{"method": "password", "timestamp": now-30}])
        claims.update(changes or {})
        for name in omit:
            del claims[name]
        return jwt.PyJWS().encode(raw_edit(json.dumps(claims)).encode(), key or private, algorithm="ES256",
                                 headers={"kid": "local", **(headers or {})})
    return SimpleNamespace(verifier=verifier, sign=sign, subject=subject, session_id=session_id,
                           now=now, calls=calls, document=document, clock=clock)


@pytest.mark.parametrize("aal", ["aal1", "aal2"])
def test_verified_immutable_evidence_and_old_contract(evidence, aal):
    e = evidence
    amr = [{"method": "password", "timestamp": e.now-30}, {"method": "totp", "timestamp": e.now-20}]
    value = e.sign({"aal": aal, "amr": amr})
    result = e.verifier.verify_claims(value)
    assert isinstance(result, auth.VerifiedTokenClaims)
    assert (result.subject, result.session_id, result.aal) == (e.subject, e.session_id, aal)
    assert (result.issued_at, result.expires_at) == (e.now-10, e.now+600)
    assert [(entry.method, entry.timestamp) for entry in result.amr] == [(a["method"], a["timestamp"]) for a in amr]
    assert e.verifier.verify(value) == e.subject and len(e.calls) == 1
    with pytest.raises(FrozenInstanceError): result.aal = "aal2"
    with pytest.raises(FrozenInstanceError): result.amr[0].timestamp = e.now
    with pytest.raises(TypeError): result.amr[0] = result.amr[1]
    assert not hasattr(result, "__dict__")
    assert all(secret not in repr(result) + repr(result.amr) for secret in (str(e.subject), str(e.session_id), "password", "totp"))


@pytest.mark.parametrize("field", ["session_id", "aal", "iat", "exp"])
def test_missing_required_typed_claim(evidence, field):
    with pytest.raises(auth.InvalidAccessToken, match="^Invalid access token$"):
        evidence.verifier.verify_claims(evidence.sign(omit=[field]))


@pytest.mark.parametrize("value", [None, "", 1, True, [], {}, "not-a-uuid",
    "00000000-0000-0000-0000-000000000000", "12345678123442349234123456789abc",
    "12345678-1234-4234-9234-123456789ABC", "ffffffff-ffff-ffff-ffff-ffffffffffff"])
def test_invalid_session_identifiers(evidence, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({"session_id": value}))


@pytest.mark.parametrize("value", [None, "", "aal0", "aal3", "AAL2", "aal2 ", 2, True, [], {}])
def test_invalid_aal(evidence, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({"aal": value}))


@pytest.mark.parametrize("field", ["iat", "exp", "nbf"])
@pytest.mark.parametrize("value", [None, True, "1700000000", 1700000000.0, -1, 2**63, [], {}])
def test_invalid_timestamp_types_and_bounds(evidence, field, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({field: value}))


@pytest.mark.parametrize("value", [None, {}, "password", True, [None], ["password"], [{}],
    [{"method": "totp"}], [{"timestamp": 1}], [{"method": "totp", "timestamp": 1, "recent": True}],
    [{"method": "totp", "timestamp": 1, "provider": "unreviewed"}],
    [{"method": "totp", "timestamp": 1}, {"method": "totp", "timestamp": 2}]])
def test_malformed_amr_structure(evidence, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({"amr": value}))


@pytest.mark.parametrize("value", [None, "", "TOTP", " totp", "unknown", True, 1, [], {}])
def test_malformed_or_unreviewed_amr_method(evidence, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({"amr": [{"method": value, "timestamp": 1}]}))


@pytest.mark.parametrize("value", [None, True, "1", 1.0, -1, 2**63, [], {}])
def test_malformed_amr_timestamp(evidence, value):
    with pytest.raises(auth.InvalidAccessToken):
        evidence.verifier.verify_claims(evidence.sign({"amr": [{"method": "totp", "timestamp": value}]}))


@pytest.mark.parametrize("method", ["oauth", "password", "otp", "totp", "recovery", "invite",
    "sso/saml", "magiclink", "email/signup", "email_change", "token_refresh", "anonymous"])
def test_documented_methods_are_parsed_without_inferred_assurance(evidence, method):
    value = evidence.sign({"amr": [{"method": method, "timestamp": evidence.now-30}]})
    result = evidence.verifier.verify_claims(value)
    assert result.aal == "aal1" and result.amr[0].method == method


@pytest.mark.parametrize("old,new", [
    ('"aal": "aal1"', '"aal": "aal2", "aal": "aal1"'),
    ('"method": "password"', '"method": "totp", "method": "password"'),
])
def test_duplicate_signed_claim_fields_rejected(evidence, old, new):
    value = evidence.sign(raw_edit=lambda raw: raw.replace(old, new))
    with pytest.raises(auth.InvalidAccessToken): evidence.verifier.verify_claims(value)


def test_excessively_nested_signed_json_has_a_generic_error(evidence):
    value = evidence.sign(raw_edit=lambda raw: raw[:-1] + ', "amr": ' + '['*1100 + '0' + ']'*1100 + '}')
    with pytest.raises(auth.InvalidAccessToken, match="^Invalid access token$"):
        evidence.verifier.verify_claims(value)


@pytest.mark.parametrize("case", ["expired", "future-iat", "future-nbf", "order", "amr-after-iat"])
def test_temporal_checks(evidence, case):
    e = evidence
    changes = {"expired": {"iat": e.now-100, "exp": e.now-1}, "future-iat": {"iat": e.now+300},
               "future-nbf": {"nbf": e.now+300}, "order": {"exp": e.now-10},
               "amr-after-iat": {"amr": [{"method": "totp", "timestamp": e.now}]}}[case]
    with pytest.raises(auth.InvalidAccessToken): e.verifier.verify_claims(e.sign(changes))


def test_absent_empty_and_historical_amr_are_not_access_decisions(evidence):
    e = evidence
    assert e.verifier.verify_claims(e.sign(omit=["amr"])).amr is None
    assert e.verifier.verify_claims(e.sign({"aal": "aal2"}, omit=["amr"])).amr is None
    assert e.verifier.verify_claims(e.sign({"amr": []})).amr == ()
    result = e.verifier.verify_claims(e.sign({"aal": "aal2", "email": "unproven@example.invalid", "is_active": True,
        "amr": [{"method": "totp", "timestamp": e.now-86400}]}))
    # No live Auth/session/factor/Neon lookup: even an arbitrary signed session ID parses.
    other = uuid4()
    assert e.verifier.verify_claims(e.sign({"session_id": str(other)})).session_id == other
    assert result.aal == "aal2" and len(e.calls) == 1
    assert not any(hasattr(result, field) for field in
                   ("email", "is_active", "is_authorized", "is_mfa_recent", "user_id"))


def test_legacy_uuid_method_does_not_acquire_typed_requirements(evidence):
    e = evidence
    value = e.sign({"aal": "unknown", "session_id": "bad", "amr": None})
    assert e.verifier.verify(value) == e.subject
    with pytest.raises(auth.InvalidAccessToken): e.verifier.verify_claims(value)


@pytest.mark.parametrize("case", ["signature", "issuer", "audience", "kid", "modified", "unsigned", "dict",
                                  "session", "aal", "amr", "algorithm"])
def test_no_unverified_claims_and_no_sensitive_diagnostics(evidence, case, caplog):
    e = evidence
    changes = {"issuer": {"iss": ORIGIN}, "audience": {"aud": "other"}, "session": {"session_id": "bad"},
               "aal": {"aal": "aal3"}, "amr": {"amr": None}}.get(case, {})
    value = e.sign(changes, key=ec.generate_private_key(ec.SECP256R1())) if case == "signature" else e.sign(changes)
    if case == "kid": value = e.sign(headers={"kid": "unknown"})
    if case == "algorithm": value = e.sign(headers={"alg": "ES384"}, key=ec.generate_private_key(ec.SECP384R1()))
    if case in ("modified", "unsigned", "dict"):
        payload = jwt.decode(value, options={"verify_signature": False})
        payload["aal"] = "aal2"
        payload["session_id"] = str(uuid4())
        if case == "dict": value = payload
        elif case == "unsigned": value = jwt.encode(payload, None, algorithm="none", headers={"kid": "local"})
        else:
            parts = value.split(".")
            parts[1] = jwt.utils.base64url_encode(json.dumps(payload).encode()).decode()
            value = ".".join(parts)
    with pytest.raises(auth.InvalidAccessToken) as error: e.verifier.verify_claims(value)
    rendered = "".join(traceback.format_exception(error.value))
    assert str(error.value) == "Invalid access token" and not caplog.records
    assert all(secret not in rendered for secret in (str(e.subject), str(e.session_id), str(value)))
    if case in ("unsigned", "dict", "algorithm"): assert e.calls == []


def test_key_rotation_and_jwks_failure_remain_fail_closed(evidence, caplog):
    e = evidence
    assert e.verifier.verify_claims(e.sign()).subject == e.subject
    key = ec.generate_private_key(ec.SECP256R1())
    e.document["keys"] = [dict(json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())), kid="rotated", alg="ES256")]
    value = e.sign(key=key, headers={"kid": "rotated"})
    with pytest.raises(auth.InvalidAccessToken): e.verifier.verify_claims(value)
    e.clock[0] = 30
    assert e.verifier.verify_claims(value).session_id == e.session_id
    e.clock[0], e.document["keys"] = 330, []
    with pytest.raises(auth.SigningKeysUnavailable, match="^Signing keys unavailable$"):
        e.verifier.verify_claims(value)
    assert not caplog.records


def test_jwks_timeout_is_generic_and_constructor_has_no_network(evidence, caplog):
    e = evidence
    assert e.calls == []
    def timeout(url): raise TimeoutError(str(e.subject) + " private upstream diagnostic")
    e.verifier._fetch = timeout
    with pytest.raises(auth.SigningKeysUnavailable) as error: e.verifier.verify_claims(e.sign())
    assert str(error.value) == "Signing keys unavailable" and not caplog.records
    assert str(e.subject) not in "".join(traceback.format_exception(error.value))
