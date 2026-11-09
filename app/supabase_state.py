"""Dormant JWT-bound SQL observations; deliberately NOT a LiveStateSource/allow decision."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from threading import BoundedSemaphore
from time import monotonic
from uuid import UUID, uuid4

import psycopg

from app.supabase_jwt import InvalidAccessToken, SupabaseTokenVerifier, VerifiedTokenClaims
from app.supabase_evidence import AuthenticationEvidenceDenied, AuthenticationEvidenceUnavailable


_BODY_SHA256 = 'a43690c99f0a308f55bdb6bd655fea10515bb852d71e246d2021277db8566d2a'
_CALL = 'SELECT * FROM movelle_auth_private.observe_state(%s::pg_catalog.uuid,%s::pg_catalog.uuid)'
_GUARD = """
SELECT p.prosrc, p.proconfig, p.prosecdef, p.proowner::pg_catalog.regrole::pg_catalog.text, n.nspowner::pg_catalog.regrole::pg_catalog.text,
 current_user=session_user AND current_user='movelle_auth_state_reader'
 AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
 AND r.rolconnlimit=1 AND p.provolatile='s' AND p.proparallel='u'
 AND p.prolang=(SELECT oid FROM pg_catalog.pg_language WHERE lanname='plpgsql')
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=r.oid)
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_database d WHERE pg_catalog.has_database_privilege(r.oid,d.oid,'CREATE'))
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace s WHERE s.nspname !~ '^pg_temp'
 AND pg_catalog.has_schema_privilege(r.oid,s.oid,'CREATE'))
 AND NOT pg_catalog.has_schema_privilege(r.oid,'auth','USAGE')
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class t JOIN pg_catalog.pg_namespace s ON s.oid=t.relnamespace
 WHERE s.nspname='auth' AND t.relname IN ('users','sessions') AND
 (pg_catalog.has_any_column_privilege(r.oid,t.oid,'SELECT,INSERT,UPDATE,REFERENCES')
 OR pg_catalog.has_table_privilege(r.oid,t.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')))
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.aclexplode(coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) x
 WHERE x.grantee<>p.proowner AND (x.grantee<>r.oid OR x.privilege_type<>'EXECUTE' OR x.is_grantable))
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.aclexplode(coalesce(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) x
 WHERE x.grantee<>n.nspowner AND (x.grantee<>r.oid OR x.privilege_type<>'USAGE' OR x.is_grantable))
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles a WHERE a.rolname IN
 ('anon','authenticated','service_role','authenticator') AND
 (pg_catalog.pg_has_role(a.oid,r.oid,'SET') OR pg_catalog.pg_has_role(a.oid,r.oid,'USAGE')
 OR pg_catalog.pg_has_role(a.oid,p.proowner,'SET') OR pg_catalog.pg_has_role(a.oid,p.proowner,'USAGE')))
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
JOIN pg_catalog.pg_roles r ON r.rolname=current_user
WHERE p.oid=pg_catalog.to_regprocedure('movelle_auth_private.observe_state(uuid,uuid)')
"""
# Hash a bounded catalog snapshot, not Auth rows/secrets. No automatic trust-on-first-use.
# Conservative: even unrelated ACL/default/role changes require renewed owner review.
_CATALOG = """
SELECT kind, value::pg_catalog.text FROM (
 SELECT 'role' kind, pg_catalog.jsonb_build_array(rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,
 rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,pg_catalog.sha256(pg_catalog.convert_to(rolconfig::pg_catalog.text,'UTF8'))) value FROM pg_catalog.pg_roles
 UNION ALL SELECT 'member',pg_catalog.to_jsonb(m) FROM pg_catalog.pg_auth_members m
 UNION ALL SELECT 'database',pg_catalog.jsonb_build_array(datname,datdba,datacl) FROM pg_catalog.pg_database
 UNION ALL SELECT 'schema',pg_catalog.jsonb_build_array(nspname,nspowner,nspacl) FROM pg_catalog.pg_namespace
 WHERE nspname !~ '^pg_(temp|toast)'
 UNION ALL SELECT 'relation',pg_catalog.jsonb_build_array(n.nspname,c.relname,c.relowner,c.relacl,
 c.relrowsecurity,c.relforcerowsecurity) FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname !~ '^pg_(temp|toast)'
 UNION ALL SELECT 'column',pg_catalog.jsonb_build_array(c.oid,a.attname,a.attacl)
 FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE a.attacl IS NOT NULL AND n.nspname !~ '^pg_(temp|toast)'
 UNION ALL SELECT 'routine',pg_catalog.jsonb_build_array(p.oid::pg_catalog.regprocedure::pg_catalog.text,p.proowner,p.proacl,
 p.prosecdef,p.proconfig,p.prolang,p.provolatile,p.proparallel,pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8'))) FROM pg_catalog.pg_proc p
 JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname !~ '^pg_(temp|toast)'
 UNION ALL SELECT 'policy',pg_catalog.jsonb_build_array(polrelid,polname,polcmd,polroles,polpermissive,
 pg_catalog.sha256(pg_catalog.convert_to(polqual::pg_catalog.text,'UTF8')),
 pg_catalog.sha256(pg_catalog.convert_to(polwithcheck::pg_catalog.text,'UTF8'))) FROM pg_catalog.pg_policy
 UNION ALL SELECT 'default',pg_catalog.to_jsonb(d) FROM pg_catalog.pg_default_acl d
 UNION ALL SELECT 'extension',pg_catalog.jsonb_build_array(extname,extowner,extnamespace,extversion) FROM pg_catalog.pg_extension
 UNION ALL SELECT 'largeobject',pg_catalog.jsonb_build_array(oid,lomowner,lomacl) FROM pg_catalog.pg_largeobject_metadata
 UNION ALL SELECT 'settings',pg_catalog.jsonb_build_array(setdatabase,setrole,pg_catalog.sha256(pg_catalog.convert_to(setconfig::pg_catalog.text,'UTF8'))) FROM pg_catalog.pg_db_role_setting
) entries ORDER BY kind,value::pg_catalog.text LIMIT 5001
"""


def _catalog_digest(rows):
    encoded = json.dumps(rows, separators=(',', ':')).encode()
    if not rows or len(rows) > 5000 or len(encoded) > 2097152:
        raise ValueError
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class AuthStateObservation:
    """Verified UUIDs plus point-in-time DB markers, never full session/MFA/email proof."""
    claims: VerifiedTokenClaims
    issuer: str
    nonce: UUID
    observed_at: datetime
    binding_present: bool
    deletion_clear: bool
    ban_clear: bool
    absolute_expiry_clear: bool


class SupabaseStateObserver:
    """Server-only explicit configuration; no import/constructor I/O or route wiring.

    approved_catalog_sha256 must be owner-reviewed after a separately authorized
    installation. There is NO hosted approved value/default or auto-enrollment.
    Only direct, TLS-verified project DB hosts are supported; poolers need review.
    """
    def __init__(self, project_url, *, database_url, approved_catalog_sha256, audience='authenticated'):
        try:
            self._verifier = SupabaseTokenVerifier(project_url, audience=audience)
            params = psycopg.conninfo.conninfo_to_dict(database_url)
            if (set(params) - {'host','port','dbname','user','password','sslmode','sslrootcert'}
                    or params.get('host') != 'db.' + project_url.removeprefix('https://')
                    or params.get('port', '5432') != '5432' or not re.fullmatch('[A-Za-z0-9_-]{1,63}', params.get('dbname',''))
                    or params.get('user') != 'movelle_auth_state_reader' or not params.get('password')
                    or params.get('sslmode') != 'verify-full' or not params.get('sslrootcert')
                    or not re.fullmatch('[0-9a-f]{64}', approved_catalog_sha256)):
                raise ValueError
            self._params, self._approved = params, approved_catalog_sha256
            self._slot = BoundedSemaphore(1)
        except Exception:
            raise ValueError('Invalid server-only Auth-state configuration') from None

    def observe(self, token: str) -> AuthStateObservation:
        """ONLY raw JWT input: verify cryptographically before any DB connection."""
        acquired = False
        try:
            started = monotonic()
            claims = self._verifier.verify_claims(token)
            # Reject ambient libpq routing/credential overrides; never read their values into diagnostics.
            if any(os.environ.get(o.envvar.decode()) for o in psycopg.pq.Conninfo.get_defaults() if o.envvar):
                raise ValueError
            acquired = self._slot.acquire(blocking=False)
            if not acquired:
                raise ValueError
            with psycopg.connect(**self._params, connect_timeout=2, autocommit=True) as c, c.transaction():
                if not 170000 <= c.info.server_version < 180000:
                    raise ValueError
                c.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY')
                c.execute("SET LOCAL statement_timeout='750ms'; SET LOCAL lock_timeout='250ms'; SET LOCAL transaction_timeout='1500ms'")
                guard = c.execute(_GUARD).fetchone()
                if (guard is None or hashlib.sha256(guard[0].encode()).hexdigest() != _BODY_SHA256
                        or guard[1] != ['search_path=""', 'row_security=off'] or guard[2:] != (True,'postgres','postgres',True)
                        or _catalog_digest(c.execute(_CATALOG).fetchall()) != self._approved):
                    raise ValueError
                rows = c.execute(_CALL, (claims.subject, claims.session_id)).fetchall()
                if (len(rows) != 1 or len(rows[0]) != 5 or any(type(v) is not bool for v in rows[0][:4])
                        or type(rows[0][4]) is not datetime or rows[0][4].utcoffset() is None):
                    raise ValueError
                result = AuthStateObservation(claims,self._verifier.issuer,uuid4(),rows[0][4],*rows[0][:4])
            now = datetime.now(timezone.utc)  # Include transaction/socket cleanup in the budget.
            if (abs((now-result.observed_at).total_seconds()) > 3 or now.timestamp() >= claims.expires_at
                    or monotonic()-started > 3):
                raise ValueError
            return result
        except InvalidAccessToken:
            raise AuthenticationEvidenceDenied('Authentication evidence rejected') from None
        except Exception:
            raise AuthenticationEvidenceUnavailable('Authentication evidence unavailable') from None
        finally:
            if acquired:
                self._slot.release()
