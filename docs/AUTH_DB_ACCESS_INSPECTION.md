# Prompt 11 — restricted development Auth DB inspection

Status: **RECOMMEND DORMANT IMPLEMENTATION/OFFLINE TESTS; NO HOSTED APPROVAL** (2026-11-09).
This remains Prompt 11 of the fixed 26-prompt Stage 1 roadmap. No Prompt 12 work.
No hosted SQL executed; only synthetic local SQL fixtures. No hosted changes.

## Evidence: owner-reported hosted findings

The owner completed all 15 blocks in [the inspection SQL](sql/auth_state_inspection.sql),
then both follow-up metadata/visibility checks (PASS).
in development `movelle-auth-dev`. These are supplied hosted findings, not an
independent agent connection or behavioral test. PR #33 is verified locally at
`3d592e30cd3afc9496b240be6b8b46bd9b8fe38d`; dormant evidence interfaces remain.

| Inspection | Reported finding |
| --- | --- |
| Version / inspector / reader | PostgreSQL 17.11; `postgres`; `movelle_auth_state_reader` absent. |
| Columns | All nine requested columns exist; the six state-reader columns have correct UUID/timestamptz types. |
| Grant authority | `postgres` can grant CONNECT and table SELECT, but cannot grant Auth-schema USAGE. |
| Role power | `postgres` inherits powerful roles, including `pg_read_all_data`, and has existing rolbypassrls=true; unacceptable as runtime identity. |
| RLS | Both Auth tables: enabled, FORCE disabled, no policies. |
| Definer metadata PASS | Existing postgres Auth USAGE and SELECT true, RLS inactive for all six required columns. |
| Visibility PASS | user_visible=true and session_visible=true: existing-row visibility at inspection time. |
| Data API (owner-confirmed) | Exposed graphql_public/public; extra path public/extensions; private schema absent. No exposed objects listed; auto-expose-new-tables enabled. |
| Reader effective rights | Not measured: no reader exists. |
| Functions / defaults | Existing Auth functions have PUBLIC EXECUTE; default ACLs grant managed roles, not the proposed reader. |
| Optional extensions checked | Only `supabase_vault` 0.3.1 among pg_net/http/pg_cron/supabase_vault. Not a complete extension inventory. |

Direct Auth grants are **rejected for this design**: table SELECT cannot compensate
for missing schema USAGE. Do not grant provider memberships, `pg_read_all_data`,
BYPASSRLS or change managed Auth RLS/ownership to repair this. Existing PUBLIC
EXECUTE alone is not reachability without schema USAGE. Absence of pg_net reduces
one known risk; it does not establish complete PUBLIC/role isolation.

## Conditional private capability: safest candidate for explicit DB binding

[Supabase documents](https://supabase.com/kb/troubleshooting/permission-errors-when-granting-custom-roles-access-to-the-auth-schema-9e32e7)
a postgres-owned SECURITY DEFINER function in a controlled, non-exposed schema.
It can use the owner's now-evidenced Auth access without giving callers that access;
Free quotas, runtime connectivity and post-install acceptance remain. No paid feature.

**Definer feasibility PASS:** the owner-reported checks establish existing postgres
read access under existing RLS; no new BYPASSRLS or Auth policy is needed/authorized.
This does not prove access for the absent runtime role or after provider changes.
The proposed local `row_security=off` [raises if RLS would apply](https://www.postgresql.org/docs/17/runtime-config-client.html#GUC-ROW-SECURITY);
it does not grant bypass. No need to repeat the completed definer SQL checks.

The owner would remain **postgres**, not a newly isolated definer: granting a new
owner the needed Auth USAGE is blocked too. Accepting this broad trusted function
owner is an explicit security decision. No postgres/service-role secret goes to
runtime. A compromised owner can replace the function; fixed SQL does not confine
that administrator. A compromised caller can probe arbitrary UUID pairs for the
limited observations; the function itself cannot prove JWT origin.

The [review-only SQL](sql/auth_state_role_proposal.sql) proposes a new private
schema and NOLOGIN caller, CONNECT + private-schema USAGE + exact function EXECUTE.
No direct Auth grants, memberships, schema CREATE, DML or elevated caller flags.
The body has no writes, dynamic SQL, callbacks or caller-controlled identifiers;
all objects/types/functions are qualified with an empty search path. It binds both
UUIDs and returns separate binding/deletion/ban/absolute-expiry flags and DB time,
not row data, email, AAL, authorization or a generic "active" result.

Create/restrict privileges atomically; revoke PUBLIC and API-role rights on **new
owned objects only**. Stop on any other default grantee; do not globally revoke
provider/default ACLs. Post-install ACL and membership checks are mandatory.
[PostgreSQL function guidance](https://www.postgresql.org/docs/17/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY)
explains definer/search-path and initial PUBLIC EXECUTE hazards.

Keep the schema out of PostgREST exposed schemas/extra search paths; no RPC wrapper,
public view, API-role membership or authenticator-to-reader SET path. Private-schema
exclusion is owner-confirmed; wrapper/role-path absence is unproven. Future connections
must target this development project over verify-full TLS; no browser, CI or Neon secret.
[PUBLIC baseline privileges](https://supabase.com/kb/troubleshooting/custom-role-inherits-privileges-that-were-not-explicitly-granted-ddaa1c)
survive NOINHERIT. Temporary/large-object/catalog capabilities and reachable custom
functions still need explicit review; read-only defaults are not a security boundary.

## Supported API comparison and unproven semantics

| Source | What it establishes / what it does not |
| --- | --- |
| Signature verification / getClaims | Issued JWT claims, not current session/account state. |
| Fresh public-key + user-token GET `/auth/v1/user` | Authentic provider user response. [Server guidance](https://supabase.com/docs/guides/auth/server-side/advanced-guide) recommends getUser to detect server-ended sessions. No privileged credential needed; retain this check. |
| Public Auth source | [Pinned middleware](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/api/auth.go) loads nonzero session IDs and rejects bans/missing records. Corroboration only: deployed version, exact ownership/expiry checks and propagation are unproven here. |
| Proposed private function | Explicit subject/session join and inspected markers in one database snapshot. Not all provider session-validity rules or proof of real-time revocation. |
| Admin user APIs | Broad privilege, no substitute for exact session binding; rejected as runtime dependency. |

[Session documentation](https://supabase.com/docs/guides/auth/sessions) says sign-out
removes affected session rows; timeout cleanup can lag. [User management](https://supabase.com/docs/guides/auth/managing-user-data)
documents hard-delete cascades, surviving issued JWTs and bans that do not revoke
sessions. Hosted sign-out scopes, deletion/soft deletion, bans, password-reset
effects and observation delays still require controlled acceptance tests. Row
presence + not_after is not a universal inactivity/lifetime/revocation rule.
Do not purchase/enable paid session controls or infer them from these columns.

Future adapter: pinned issuer-to-project connection, verifier-derived UUIDs only,
one fresh READ COMMITTED READ ONLY transaction/query per check, no positive cache,
nonce/issuer/UUID binding in trusted code, bounded pool/deadline and generic errors.
DB observation time is not application-clock proof; validate clock skew/latency.
Provider HTTP + SQL + Neon writes are not atomic; concurrency and time-of-check
windows remain. Unknown state, denied read, timeout or mismatch must deny access.

Email columns remain unnecessary for this state-only capability. The current DTO
still requires them: a separately reviewed contract refactor is needed, not copied
HTTP values disguised as independent SQL evidence. Genuine mailbox provenance,
A → B → A invalidation, current/recent MFA, local suspension, identity linking and
resource/group authorization remain separate gates. No "enabled/present" adapter
may be wired until the complete required semantics are evidenced.

## Exact owner decision and remaining acceptance

**Final recommendation: approve dormant implementation and isolated offline tests.**
The [closed review](AUTH_DB_ACCESS_VERIFICATION.md) distinguishes configured schema
exclusion from unproven wrapper/role isolation. No more broad investigation is needed
for offline work. Implement only truthful typed observations, not an enabled/present
adapter until the required semantics are evidenced; preserve the fail-closed policy.
Unknown PUBLIC grants, generic wrappers and API-to-owner paths block hosted setup,
not dormant code. Actual reader permissions require post-creation verification.
Source-reviewed guards cover fixed search path, qualified reads, owner/ACL checks,
atomic revokes and transitive API SET/USAGE. This is not hosted-test success.
Owner now authorizes dormant implementation/offline tests. Hosted DDL,
credentials, lifecycle tests and activation are separate approvals. No PR/deploy/
spending; this finishes the Prompt 11 review, not its owner acceptance or Prompt 12.
Prompt 11 remains incomplete until its stacked PRs are reviewed and merged.
