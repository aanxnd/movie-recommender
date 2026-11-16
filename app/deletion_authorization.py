"""Server-enforced deletion proof and fail-closed lifecycle policy; dormant factories only."""
from time import time
from uuid import UUID

from pydantic import SecretStr

from app.deletion_provider import AuthJsonTransport
from app.deletion_store import DeletionAuthorization, DeletionUnavailable, creation_stamp
from app.supabase_policy import AccessDenied, AccessUnavailable, SupabaseAccessPolicy


class DeletionAuthorizer:
    def __init__(self, project_url, publishable_key):
        self.policy = SupabaseAccessPolicy(project_url=project_url, audience='authenticated', publishable_key=publishable_key)
        self.issuer = self.policy._verifier.issuer
        self._transport = AuthJsonTransport(project_url, SecretStr(publishable_key))

    def authorize(self, token, password, factor_id=None, code=None):
        if type(password) is not SecretStr or not 1 <= len(password.get_secret_value()) <= 1024:
            raise AccessDenied('Authentication evidence rejected')
        before, email, user = self.policy.observe_account(token)
        stamp = creation_stamp(user.get('created_at'))
        if before.aal == 'aal2':
            if (type(factor_id) is not UUID or type(code) is not SecretStr or
                    not any(f['id'] == str(factor_id) and f['status'] == 'verified' for f in user.get('factors', []))):
                raise AccessDenied('Authentication evidence rejected')
        elif factor_id is not None or code is not None:
            raise AccessDenied('Authentication evidence rejected')
        cleanup = None
        try:
            status, data = self._transport.request('POST', 'token?grant_type=password',
                body={'email': email.email, 'password': password.get_secret_value()})
            if status != 200:
                raise AccessDenied('Authentication evidence rejected')
            proof = self.policy._verifier.verify_claims(data.get('access_token'))
            if (proof.subject != before.subject or data.get('user', {}).get('id') != str(before.subject)
                    or proof.session_id == before.session_id or proof.aal != 'aal1'
                    or not proof.amr or not any(a.method == 'password' for a in proof.amr)):
                raise AccessDenied('Authentication evidence rejected')
            cleanup = data['access_token']
        finally:
            if cleanup is not None:
                status, _ = self._transport.request('POST', 'logout?scope=local', token=cleanup)
                if status != 204:
                    raise DeletionUnavailable()
        if before.aal == 'aal2':
            token = self._verify_factor(token, before, factor_id, code)
        # Re-read after password proof, retaining the original AAL2 session for enrolled users.
        after, _, user = self.policy.observe_account(token)
        if (after.subject != before.subject or after.session_id != before.session_id or after.aal != before.aal
                or creation_stamp(user.get('created_at')) != stamp):
            raise AccessDenied('Authentication evidence rejected')
        return DeletionAuthorization(after.subject, after.session_id, min(after.expires_at, int(time())+120),
                                     after.aal, self.issuer, stamp)

    def _verify_factor(self, token, before, factor_id, code):
        import re
        if not re.fullmatch(r'[0-9]{6}', code.get_secret_value()):
            raise AccessDenied('Authentication evidence rejected')
        path = 'factors/' + str(factor_id)
        status, c = self._transport.request('POST', path + '/challenge', body={}, token=token)
        if (status != 200 or c.get('type') != 'totp' or type(c.get('expires_at')) is not int
                or c['expires_at'] <= time() or str(UUID(c['id'])) != c['id'] or not UUID(c['id']).int):
            raise AccessDenied('Authentication evidence rejected')
        status, data = self._transport.request('POST', path + '/verify', token=token,
            body={'challenge_id': c['id'], 'code': code.get_secret_value()})
        if status != 200: raise AccessDenied('Authentication evidence rejected')
        promoted = data.get('access_token')
        claims = self.policy._verifier.verify_claims(promoted)
        if (claims.subject != before.subject or claims.session_id != before.session_id or claims.aal != 'aal2'
                or data.get('user', {}).get('id') != str(before.subject)
                or not claims.amr or not any(a.method == 'totp' for a in claims.amr)):
            raise AccessDenied('Authentication evidence rejected')
        return promoted


class DeletionAwarePolicy:
    def __init__(self, policy, store):
        if policy._verifier.issuer != store.issuer:
            raise DeletionUnavailable()
        self._policy, self._store = policy, store

    def check_with_email(self, token):
        claims, email = self._policy.check_with_email(token)
        try:
            blocked = self._store.blocked(claims.subject)
        except Exception:
            raise AccessUnavailable('Authentication temporarily unavailable') from None
        if blocked:
            raise AccessDenied('Authentication evidence rejected')
        return claims, email

    def check_for_provisioning(self, token):
        return self.check_with_email(token)[0]

    def check(self, token):
        return self.check_with_email(token)[0]
