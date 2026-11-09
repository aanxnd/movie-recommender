/*
PROMPT 11 — NOT APPROVED FOR EXECUTION. Entire file is deliberately a comment.
Dedicated LOGIN identity; no credential supplied. Hosted provisioning NOT approved.
Prerequisites: explicit owner approval; new names; private schema unexposed;
postgres's EXISTING RLS bypass/owner access demonstrated; exact UUID/timestamp
types checked; default ACL/PUBLIC/SET-role risks accepted. No managed changes.
No IF NOT EXISTS / OR REPLACE: never reuse an unknown role, schema or function.

BEGIN;
DO $guard$ BEGIN
  RAISE EXCEPTION 'NOT APPROVED FOR EXECUTION'; -- retain until separately reviewed
END; $guard$;
CREATE ROLE movelle_auth_state_reader LOGIN NOSUPERUSER NOCREATEDB
  NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1 PASSWORD NULL;
CREATE SCHEMA movelle_auth_private AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA movelle_auth_private FROM PUBLIC, anon, authenticated, service_role;

CREATE FUNCTION movelle_auth_private.observe_state(p_subject pg_catalog.uuid, p_session pg_catalog.uuid)
RETURNS TABLE (binding_present pg_catalog.bool, deletion_clear pg_catalog.bool,
  ban_clear pg_catalog.bool, absolute_expiry_clear pg_catalog.bool, observed_at pg_catalog.timestamptz)
LANGUAGE plpgsql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = ''
SET row_security = off -- ERROR if RLS applies; does NOT grant bypass
AS $body$
BEGIN
  IF p_subject IS NULL OR p_session IS NULL
     OR p_subject = '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid
     OR p_session = '00000000-0000-0000-0000-000000000000'::pg_catalog.uuid THEN
    RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Invalid evidence request';
  END IF;
  IF pg_catalog.current_setting('transaction_isolation') <> 'read committed'
     OR pg_catalog.current_setting('transaction_read_only') <> 'on' THEN
    RAISE EXCEPTION USING ERRCODE = '25000', MESSAGE = 'Evidence transaction required';
  END IF;
  RETURN QUERY SELECT pg_catalog.count(*) = 1,
    pg_catalog.count(*) = 1 AND coalesce(pg_catalog.bool_and(u.deleted_at IS NULL), false),
    pg_catalog.count(*) = 1 AND coalesce(pg_catalog.bool_and(
      u.banned_until IS NULL OR u.banned_until <= pg_catalog.statement_timestamp()), false),
    pg_catalog.count(*) = 1 AND coalesce(pg_catalog.bool_and(
      s.not_after IS NULL OR s.not_after > pg_catalog.statement_timestamp()), false),
    pg_catalog.statement_timestamp()
  FROM auth.users AS u JOIN auth.sessions AS s ON s.user_id = u.id
  WHERE u.id = p_subject AND s.id = p_session;
END;
$body$;
REVOKE ALL ON FUNCTION movelle_auth_private.observe_state(uuid, uuid)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT CONNECT ON DATABASE "<privately_inspected_database>" TO movelle_auth_state_reader;
GRANT USAGE ON SCHEMA movelle_auth_private TO movelle_auth_state_reader;
GRANT EXECUTE ON FUNCTION movelle_auth_private.observe_state(uuid, uuid)
  TO movelle_auth_state_reader;

-- Reject unexpected new-object grants; leave global/provider ACLs unchanged.
DO $acl$
DECLARE reader_oid oid := 'movelle_auth_state_reader'::regrole;
BEGIN
  IF current_user <> 'postgres'
  OR NOT (SELECT rolcanlogin FROM pg_catalog.pg_roles WHERE oid=reader_oid) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = reader_oid
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles r
    WHERE r.rolname IN ('anon','authenticated','service_role','authenticator')
      AND (pg_catalog.pg_has_role(r.oid, reader_oid, 'USAGE')
           OR pg_catalog.pg_has_role(r.oid, reader_oid, 'SET')
           OR pg_catalog.pg_has_role(r.oid, 'postgres'::regrole, 'USAGE')
           OR pg_catalog.pg_has_role(r.oid, 'postgres'::regrole, 'SET'))
  ) THEN RAISE EXCEPTION 'Unexpected role authority'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL
      pg_catalog.aclexplode(coalesce(n.nspacl, pg_catalog.acldefault('n', n.nspowner))) x
    WHERE n.nspname = 'movelle_auth_private'
      AND (n.nspowner <> 'postgres'::regrole OR x.grantee NOT IN (n.nspowner, reader_oid)
           OR (x.grantee = reader_oid AND (x.privilege_type <> 'USAGE' OR x.is_grantable)))
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p CROSS JOIN LATERAL
      pg_catalog.aclexplode(coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))) x
    WHERE p.oid = 'movelle_auth_private.observe_state(uuid,uuid)'::regprocedure
      AND (p.proowner <> 'postgres'::regrole OR x.grantee NOT IN (p.proowner, reader_oid)
           OR (x.grantee = reader_oid AND (x.privilege_type <> 'EXECUTE' OR x.is_grantable)))
  ) THEN RAISE EXCEPTION 'Unexpected new-object ACL'; END IF;
END; $acl$;
ROLLBACK; -- draft never commits; a future approved installer needs full pre/post checks

Future caller uses a fresh READ COMMITTED READ ONLY transaction and one fixed,
parameterized SELECT * FROM movelle_auth_private.observe_state($1::uuid,$2::uuid).
Only verifier-derived UUIDs from the pinned project; no caller claims/GUC trust.
All four flags true means ONLY the documented binding/markers at the snapshot.
No email/AAL/session-inactivity/authorization promise. Missing/multiple rows,
malformed output, permission errors or failures must not yield positive evidence.
No positive cache, arbitrary SQL, RPC exposure or alternate/legacy credential path.
Private password provisioning/storage/rotation, TLS and hosted installation need separate approval.
Rollback after a future installation: remove only these new function/schema/grants
and caller after dependency review, never CASCADE or provider objects.
*/
