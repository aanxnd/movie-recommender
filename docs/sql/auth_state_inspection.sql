-- Prompt 11: OWNER-ONLY, DEVELOPMENT-ONLY, READ-ONLY CATALOG INSPECTION.
-- Prepared, NOT executed. Run one numbered block at a time; no Auth row reads.
-- Return sanitized findings as directed in ../AUTH_DB_ACCESS_INSPECTION.md.
-- No SET ROLE, probes, DDL, credentials, function execution tests or mutations.

-- Q1: inspector, version, existing candidate. Absence is expected; do not create.
SELECT current_user AS inspector, session_user AS login_role,
       current_database() AS inspected_database,
       current_setting('server_version_num') AS server_version_num,
       EXISTS (SELECT 1 FROM pg_catalog.pg_roles
               WHERE rolname = 'movelle_auth_state_reader') AS reader_exists;

-- Q2: all requested columns, including permissions recommended for removal.
WITH wanted(tbl, col) AS (VALUES
  ('users','id'), ('users','banned_until'), ('users','deleted_at'),
  ('users','email'), ('users','email_confirmed_at'), ('sessions','id'),
  ('sessions','user_id'), ('sessions','not_after'), ('sessions','aal'))
SELECT w.tbl, w.col, c.oid IS NOT NULL AS table_present,
       a.attnum IS NOT NULL AS column_present,
       pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
       a.attnotnull, c.relowner::regrole AS table_owner,
       CASE WHEN a.attnum IS NOT NULL THEN
         pg_catalog.has_column_privilege(current_user, c.oid, a.attnum,
                                         'SELECT WITH GRANT OPTION') END AS inspector_can_grant
FROM wanted w LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = 'auth'
LEFT JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid AND c.relname = w.tbl
LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attname = w.col
  AND a.attnum > 0 AND NOT a.attisdropped ORDER BY 1, 2;

-- Q3a: database ACLs (including PUBLIC defaults), no connection strings.
SELECT d.datname, d.datdba::regrole AS owner,
       CASE x.grantee WHEN 0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END AS grantee,
       x.grantor::regrole AS grantor, x.privilege_type, x.is_grantable,
       pg_catalog.has_database_privilege(current_user, d.oid,
                                        'CONNECT WITH GRANT OPTION') AS inspector_can_grant_connect
FROM pg_catalog.pg_database d LEFT JOIN LATERAL
  pg_catalog.aclexplode(coalesce(d.datacl, pg_catalog.acldefault('d', d.datdba))) x ON true
ORDER BY 1, 3, 5;

-- Q3b: schema ACLs and inspector's authority, including auth and PUBLIC reach.
SELECT n.nspname, n.nspowner::regrole AS owner,
       CASE x.grantee WHEN 0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END AS grantee,
       x.grantor::regrole AS grantor, x.privilege_type, x.is_grantable,
       pg_catalog.has_schema_privilege(current_user, n.oid,
                                      'USAGE WITH GRANT OPTION') AS inspector_can_grant_usage
FROM pg_catalog.pg_namespace n LEFT JOIN LATERAL
  pg_catalog.aclexplode(coalesce(n.nspacl, pg_catalog.acldefault('n', n.nspowner))) x ON true
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
ORDER BY 1, 3, 5;

-- Q4: Auth table and column ACLs; table SELECT includes ALL columns.
WITH objects AS (
  SELECT c.oid, c.relname, c.relowner, '*'::text AS col,
         coalesce(c.relacl, pg_catalog.acldefault('r', c.relowner)) AS acl
  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'auth' AND c.relname IN ('users','sessions')
  UNION ALL
  SELECT c.oid, c.relname, c.relowner, a.attname::text, a.attacl
  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
  WHERE n.nspname = 'auth' AND c.relname IN ('users','sessions')
    AND a.attnum > 0 AND NOT a.attisdropped)
SELECT o.relname, o.col, o.relowner::regrole AS owner,
       CASE x.grantee WHEN 0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END AS grantee,
       x.grantor::regrole AS grantor, x.privilege_type, x.is_grantable
FROM objects o CROSS JOIN LATERAL pg_catalog.aclexplode(o.acl) x ORDER BY 1, 2, 4, 6;

-- Q5a: attributes only; no passwords or role configuration values.
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
       rolreplication, rolbypassrls, rolconnlimit FROM pg_catalog.pg_roles ORDER BY 1;

-- Q5b: direct membership edges. JSON extraction supports pre-16 catalogs too.
SELECT m.member::regrole AS member, m.roleid::regrole AS granted_role,
       m.grantor::regrole AS grantor, m.admin_option,
       to_jsonb(m)->>'inherit_option' AS inherit_option_pg16_plus,
       to_jsonb(m)->>'set_option' AS set_option_pg16_plus
FROM pg_catalog.pg_auth_members m ORDER BY 1, 2;

-- Q5c: transitive candidate capabilities. Zero rows if absent, NOT a clean bill.
SELECT r.rolname, pg_catalog.pg_has_role(q.oid, r.oid, 'MEMBER') AS member,
       pg_catalog.pg_has_role(q.oid, r.oid, 'USAGE') AS inherited_now,
       pg_catalog.pg_has_role(q.oid, r.oid,
         CASE WHEN current_setting('server_version_num')::int >= 160000
              THEN 'SET' ELSE 'MEMBER' END) AS set_reachable_or_pre16_member
FROM pg_catalog.pg_roles q CROSS JOIN pg_catalog.pg_roles r
WHERE q.rolname = 'movelle_auth_state_reader'
  AND pg_catalog.pg_has_role(q.oid, r.oid, 'MEMBER') ORDER BY 1;

-- Q6a: RLS flags/policy roles; null policy means no policies, not RLS disabled.
SELECT c.relname, c.relowner::regrole AS owner, c.relrowsecurity, c.relforcerowsecurity,
       p.polname, p.polcmd, p.polpermissive,
       ARRAY(SELECT CASE v WHEN 0 THEN 'PUBLIC' ELSE v::regrole::text END
             FROM unnest(p.polroles) v) AS policy_roles
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_policy p ON p.polrelid = c.oid
WHERE n.nspname = 'auth' AND c.relname IN ('users','sessions') ORDER BY 1, 5;

-- Q6b: PRIVATE ONLY. Expressions may contain identifying literals; DO NOT RETURN.
-- Inspect helpers privately, not by calling them. Report applicability/unknown only.
SELECT c.relname, p.polname,
       pg_catalog.pg_get_expr(p.polqual, p.polrelid) AS using_expression,
       pg_catalog.pg_get_expr(p.polwithcheck, p.polrelid) AS check_expression
FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid = p.polrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'auth' AND c.relname IN ('users','sessions') ORDER BY 1, 2;

-- Q7: PUBLIC relation/column/function ACLs, with default function EXECUTE expanded.
-- Schema USAGE in Q3b gates reachability. No queue, vault or function-body reads.
WITH objects(kind, schema_name, object_name, owner, acl, definer) AS (
  SELECT c.relkind::text, n.nspname, c.relname::text, c.relowner,
         coalesce(c.relacl, pg_catalog.acldefault(
           CASE WHEN c.relkind = 'S' THEN 's'::"char" ELSE 'r'::"char" END, c.relowner)), false
  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r','p','v','m','f','S')
    AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  UNION ALL
  SELECT 'column', n.nspname, c.relname || '.' || a.attname, c.relowner, a.attacl, false
  FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE a.attnum > 0 AND NOT a.attisdropped
    AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  UNION ALL
  SELECT 'routine', n.nspname, p.oid::regprocedure::text, p.proowner,
         coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner)), p.prosecdef
  FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
  WHERE (n.nspname !~ '^pg_' AND n.nspname <> 'information_schema')
     OR n.nspname = 'pg_catalog')
SELECT o.kind, o.schema_name, o.object_name, o.owner::regrole AS owner,
       o.definer AS security_definer, x.grantor::regrole AS grantor,
       x.privilege_type, x.is_grantable
FROM objects o CROSS JOIN LATERAL pg_catalog.aclexplode(o.acl) x
WHERE x.grantee = 0 ORDER BY 2, 1, 3, 7;

-- Q8a: existing candidate's effective database/schema rights, not just direct ACLs.
SELECT 'database' AS kind, d.datname::text AS object_name, v.privilege
FROM pg_catalog.pg_roles q CROSS JOIN pg_catalog.pg_database d
CROSS JOIN (VALUES ('CONNECT'), ('CREATE'), ('TEMPORARY')) v(privilege)
WHERE q.rolname = 'movelle_auth_state_reader'
  AND pg_catalog.has_database_privilege(q.oid, d.oid, v.privilege)
UNION ALL
SELECT 'schema', n.nspname::text, v.privilege
FROM pg_catalog.pg_roles q CROSS JOIN pg_catalog.pg_namespace n
CROSS JOIN (VALUES ('USAGE'), ('CREATE')) v(privilege)
WHERE q.rolname = 'movelle_auth_state_reader'
  AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  AND pg_catalog.has_schema_privilege(q.oid, n.oid, v.privilege) ORDER BY 1, 2, 3;

-- Q8b: reachable relation/column/sequence/routine privileges of an EXISTING reader.
-- Includes column-only grants, function EXECUTE and managed extension capabilities.
WITH q AS (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'movelle_auth_state_reader'),
rels AS (SELECT c.*, n.nspname FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace CROSS JOIN q
  WHERE c.relkind IN ('r','p','v','m','f','S') AND n.nspname !~ '^pg_'
    AND n.nspname <> 'information_schema'
    AND pg_catalog.has_schema_privilege(q.oid, n.oid, 'USAGE'))
SELECT 'relation' AS kind, r.nspname::text AS schema_name,
       r.relname::text AS object_name, v.privilege, false AS security_definer
FROM rels r CROSS JOIN q CROSS JOIN
  (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'),
          ('REFERENCES'), ('TRIGGER')) v(privilege)
WHERE CASE WHEN r.relkind <> 'S'
  THEN pg_catalog.has_table_privilege(q.oid, r.oid, v.privilege) ELSE false END
UNION ALL
SELECT 'column', r.nspname::text, r.relname || '.' || a.attname, v.privilege, false
FROM rels r JOIN pg_catalog.pg_attribute a ON a.attrelid = r.oid CROSS JOIN q
CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('REFERENCES')) v(privilege)
WHERE a.attnum > 0 AND NOT a.attisdropped AND CASE WHEN r.relkind <> 'S'
  THEN pg_catalog.has_column_privilege(q.oid, r.oid, a.attnum, v.privilege) ELSE false END
UNION ALL
SELECT 'sequence', r.nspname::text, r.relname::text, v.privilege, false
FROM rels r CROSS JOIN q CROSS JOIN (VALUES ('USAGE'), ('SELECT'), ('UPDATE')) v(privilege)
WHERE CASE WHEN r.relkind = 'S'
  THEN pg_catalog.has_sequence_privilege(q.oid, r.oid, v.privilege) ELSE false END
UNION ALL
SELECT 'routine', n.nspname::text, p.oid::regprocedure::text, 'EXECUTE', p.prosecdef
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace CROSS JOIN q
WHERE ((n.nspname !~ '^pg_' AND n.nspname <> 'information_schema')
       OR n.nspname = 'pg_catalog')
  AND pg_catalog.has_schema_privilege(q.oid, n.oid, 'USAGE')
  AND pg_catalog.has_function_privilege(q.oid, p.oid, 'EXECUTE') ORDER BY 2, 1, 3, 4;

-- Q9a: custom default ACLs; absent entries do not erase PostgreSQL defaults.
SELECT d.defaclrole::regrole AS creator, n.nspname AS schema_null_means_global,
       d.defaclobjtype,
       CASE x.grantee WHEN 0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END AS grantee,
       x.grantor::regrole AS grantor, x.privilege_type, x.is_grantable
FROM pg_catalog.pg_default_acl d LEFT JOIN pg_catalog.pg_namespace n ON n.oid = d.defaclnamespace
CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) x ORDER BY 1, 2, 3, 4, 6;

-- Q9b: presence/version only, never inspect extension data or invoke HTTP functions.
SELECT extname, extversion, extnamespace::regnamespace AS schema_name
FROM pg_catalog.pg_extension WHERE extname IN ('pg_net','http','pg_cron','supabase_vault')
ORDER BY 1;
