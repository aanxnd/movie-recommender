"""TEST ONLY: fictional Auth HTTP provider. Never imported by application/release code.

Exercises SDK/API wiring, not actual Supabase behavior, deliverability or security guarantees.
Ephemeral signing keys, fixture passwords/codes and accounts have no hosted counterpart.
"""
import base64
import hashlib
import hmac
import json
import struct
import time
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import jwt

PROJECT = 'https://aaaaaaaaaaaaaaaaaaaa.supabase.co'
SECRET = 'JBSWY3DPEHPK3PXP'  # Published synthetic test vector, never a real authenticator.


class ProviderFixture:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.jwk = {**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.key.public_key())),
                    'kid': 'fixture-' + uuid4().hex, 'alg': 'ES256', 'use': 'sig'}
        self.reset()
        self.app = FastAPI()
        self.app.add_api_route('/auth/v1/{path:path}', self.handle, methods=['GET', 'POST', 'PUT', 'DELETE'])

    def reset(self):
        self.users, self.passwords, self.refreshes, self.links, self.challenges = {}, {}, {}, {}, {}
        self.events, self.outage = [], False
        # Freeze only this simulator's OTP vector, so a browser roundtrip cannot
        # fail at a wall-clock step boundary. JWT/challenge expiry still use real
        # time. This establishes no hosted Supabase OTP-window tolerance guarantee.
        self.otp_step = int(time.time()) // 30
        for name, count in [('alice', 2), ('bob', 1), ('plain', 0)]:
            self.add_user(name + '@example.invalid', 'fixture-password', count, confirmed=True)

    def add_user(self, email, password, factors=0, *, confirmed=False):
        identifier = str(uuid4())
        self.users[identifier] = dict(id=identifier, aud='authenticated', role='authenticated', is_anonymous=False,
            email=email, email_confirmed_at='2026-01-01T00:00:00Z' if confirmed else None,
            factors=[dict(id=str(uuid4()), factor_type='totp', status='verified', friendly_name=f'Fixture device {i+1}')
                     for i in range(factors)])
        self.passwords[identifier] = password
        return identifier

    def token(self, identifier, *, method='password', aal='aal1', session=None, changes=None):
        now = int(time.time())
        claims = dict(iss=PROJECT + '/auth/v1', aud='authenticated', role='authenticated', sub=identifier,
            is_anonymous=False, session_id=session or str(uuid4()), iat=now, exp=now+3600, aal=aal,
            amr=[dict(method=method, timestamp=now)], jti=str(uuid4()))
        claims.update(changes or {})
        access = jwt.encode(claims, self.key, algorithm='ES256', headers={'kid': self.jwk['kid']})
        refresh = uuid4().hex
        self.refreshes[refresh] = claims
        return dict(access_token=access, refresh_token=refresh, expires_in=3600, expires_at=now+3600,
                    token_type='bearer', user=self.users[identifier])

    def claims(self, request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        return jwt.decode(token, self.key.public_key(), algorithms=['ES256'], audience='authenticated', issuer=PROJECT+'/auth/v1')

    def otp(self):
        digest = hmac.new(base64.b32decode(SECRET), struct.pack('>Q', self.otp_step), hashlib.sha1).digest()
        offset = digest[-1] & 15
        return str((struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff) % 1000000).zfill(6)

    def link(self, identifier, method, body):
        code = str(uuid4())
        self.links[code] = dict(subject=identifier, method=method, challenge=body.get('code_challenge'))
        return code

    async def handle(self, request: Request, path: str):
        # Record sanitized operation names only, never bodies, tokens or addresses.
        self.events.append((request.method, path))
        if self.outage: return self.error('fixture_outage', 503)
        try:
            raw = await request.body()
            body = json.loads(raw) if raw else {}
            if path == '.well-known/jwks.json': return {'keys': [self.jwk]}
            if path in {'signup', 'recover'}:
                identifier = next((i for i, u in self.users.items() if u['email'] == body.get('email')), None)
                if identifier is None and path == 'signup': identifier = self.add_user(body['email'], body['password'])
                if identifier: self.link(identifier, 'email/signup' if path == 'signup' else 'recovery', body)
                return self.users[identifier] if path == 'signup' and identifier else {}
            if path == 'token':
                grant = request.query_params.get('grant_type')
                if grant == 'pkce':
                    link = self.links.pop(body.get('auth_code'), None)
                    actual = base64.urlsafe_b64encode(hashlib.sha256(body.get('code_verifier', '').encode()).digest()).decode().rstrip('=')
                    if not link or link['challenge'] != actual: return self.error('flow_state_not_found', 422)
                    return self.token(link['subject'], method=link['method'])
                if grant == 'refresh_token':
                    c = self.refreshes[body['refresh_token']]
                    return self.token(c['sub'], method=c['amr'][0]['method'], aal=c['aal'], session=c['session_id'])
                identifier = next((i for i, u in self.users.items() if u['email'] == body.get('email')), None)
                if not identifier or self.passwords[identifier] != body.get('password'): return self.error('invalid_credentials')
                if not self.users[identifier]['email_confirmed_at']: return self.error('email_not_confirmed')
                return self.token(identifier)
            c = self.claims(request); user = self.users[c['sub']]
            if path == 'logout':
                self.refreshes = {key: value for key, value in self.refreshes.items()
                                  if (value['sub'], value['session_id']) != (c['sub'], c['session_id'])}
                return {}  # Already-issued JWTs retain bounded validity, matching the approved policy.
            if path == 'user':
                if request.method == 'GET': return {k: v for k, v in user.items() if k != 'factors' or v}
                if any(f['status'] == 'verified' for f in user['factors']) and c['aal'] != 'aal2': return self.error('insufficient_aal', 401)
                if 'password' in body: self.passwords[c['sub']] = body['password']
                if 'email' in body:
                    user['new_email'] = body['email']; self.link(c['sub'], 'email_change', body)
                return {k: v for k, v in user.items() if k != 'factors' or v}  # Native omitempty wire shape.
            if path == 'factors' and request.method == 'POST':
                if (any(f['status'] == 'verified' for f in user['factors']) and c['aal'] != 'aal2') or len(user['factors']) >= 10:
                    return self.error('insufficient_aal', 401)
                factor = dict(id=str(uuid4()), factor_type='totp', status='unverified', friendly_name=body['friendly_name'])
                user['factors'].append(factor)
                return dict(id=factor['id'], type='totp', totp=dict(secret=SECRET,
                    qr_code='<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"><path d="M0 0h10v10H0z"/></svg>',
                    uri='otpauth://totp/Movelle:fixture?secret='+SECRET+'&issuer=Movelle'))
            parts = path.split('/')
            if len(parts) == 3 and parts[0] == 'factors':
                factor = next(f for f in user['factors'] if f['id'] == parts[1])
                if parts[2] == 'challenge':
                    identifier = str(uuid4()); self.challenges[identifier] = (c['sub'], factor['id'], time.time()+120)
                    return dict(id=identifier, type='totp', expires_at=int(time.time())+120)
                challenge = self.challenges.pop(body.get('challenge_id'), None)
                if not challenge or challenge[:2] != (c['sub'], factor['id']) or challenge[2] <= time.time() or body.get('code') != self.otp():
                    return self.error('mfa_verification_failed')
                factor['status'] = 'verified'
                return self.token(c['sub'], method='totp', aal='aal2', session=c['session_id'])
            return self.error('unsupported_fixture_operation')
        except (KeyError, ValueError, StopIteration, jwt.PyJWTError):
            return self.error('fixture_evidence_rejected', 401)

    @staticmethod
    def error(code, status=400):
        return JSONResponse({'code': code, 'msg': 'Synthetic provider rejected the request'}, status_code=status)
