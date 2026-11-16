"""Server-only pinned Auth REST operations. No environment loading or import I/O."""
import json
import re
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID

from pydantic import SecretStr

from app.deletion_store import DeletionUnavailable, creation_stamp
from app.supabase_jwt import _NoRedirect, _unique_object


class AuthJsonTransport:
    def __init__(self, project_url, api_key):
        if (not re.fullmatch(r'https://[a-z0-9]{20}\.supabase\.co', project_url)
                or type(api_key) is not SecretStr or not re.fullmatch(r'[!-~]{16,8192}', api_key.get_secret_value())):
            raise DeletionUnavailable()
        self.issuer, self._key = project_url + '/auth/v1', api_key

    def request(self, method, path, *, body=None, token=None):
        if not ((method in {'GET', 'DELETE'} and re.fullmatch(r'admin/users/[0-9a-f-]{36}', path)) or
                (method == 'POST' and re.fullmatch(r'factors/[0-9a-f-]{36}/(?:challenge|verify)', path)) or
                (method == 'POST' and path in {'token?grant_type=password', 'logout?scope=local'})):
            raise DeletionUnavailable()
        try:
            key = self._key.get_secret_value()
            request = Request(self.issuer + '/' + path, method=method,
                data=None if body is None else json.dumps(body).encode(),
                headers={'apikey': key, 'Authorization': 'Bearer ' + (token or key),
                         'Content-Type': 'application/json', 'Accept': 'application/json', 'Cache-Control': 'no-store'})
            opener = build_opener(ProxyHandler({}), _NoRedirect())
            try:
                response = opener.open(request, timeout=3)
            except HTTPError as error:
                response = error
            with response:
                raw, status = response.read(65537), response.status
            if len(raw) > 65536:
                raise DeletionUnavailable()
            value = json.loads(raw, object_pairs_hook=_unique_object) if raw else {}
            if not isinstance(value, dict):
                raise DeletionUnavailable()
            return status, value
        except Exception:
            raise DeletionUnavailable() from None


class SupabaseIdentityEraser:
    """A broad provider credential confined to a non-public worker, not a scoped key claim."""
    def __init__(self, project_url, admin_key, *, reviewed=False):
        if reviewed is not True:
            raise DeletionUnavailable()
        self._transport = AuthJsonTransport(project_url, admin_key)
        self.issuer = self._transport.issuer

    def ensure_absent(self, subject, provider_created_at, authorize_delete):
        if type(subject) is not UUID or not subject.int:
            raise DeletionUnavailable()
        path = 'admin/users/' + str(subject)
        status, user = self._transport.request('GET', path)
        if status == 404 and user.get('code') == 'user_not_found':
            return
        if (status != 200 or user.get('id') != str(subject) or
                creation_stamp(user.get('created_at')) != provider_created_at or authorize_delete() is not True):
            raise DeletionUnavailable()
        # Pinned GoTrue hard-delete returns {}, never proof of absence by itself.
        status, reply = self._transport.request('DELETE', path, body={'should_soft_delete': False})
        if status != 200 or reply != {}:
            raise DeletionUnavailable()
        status, reply = self._transport.request('GET', path)
        if status != 404 or reply.get('code') != 'user_not_found':
            raise DeletionUnavailable()
