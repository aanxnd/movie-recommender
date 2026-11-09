# Prompt 11 — verification report and remaining gates

**Definer checks PASS (owner-reported). Hosted SQL NOT APPROVED FOR EXECUTION.**
Owner approved dormant implementation/offline tests; results belong to dependent PRs.

| Completed hosted check | Owner-reported result |
| --- | --- |
| Metadata | Six required UUID/timestamptz columns; postgres Auth USAGE and column SELECT true throughout. |
| Existing RLS context | rolbypassrls=true; rls_applies_to_inspector=false for all six. No bypass/policy changes. |
| Bounded visibility | user_visible=true; session_visible=true. Existing rows visible at inspection time. |
| Data API settings | Exposed: graphql_public, public. Extra search path: public, extensions. Private schema absent from both (owner-confirmed). |
| Dashboard inventory | No exposed tables/functions listed; Automatically expose new tables enabled. Not a catalog proof of wrapper absence. |

## PUBLIC/default-privilege assessment: closed for dormant scope

Q3/Q7/Q9 confirm Auth PUBLIC EXECUTE/managed defaults; exact object/grantee lists
were not supplied. Decisions below are complete for scope, not a hosted inventory.

| Capability | Allowlist decision / evidence |
| --- | --- |
| PUBLIC CONNECT/TEMPORARY, public-schema USAGE, catalog metadata, standard large-object capabilities | Documented residual baseline; explicit acceptance required before a runtime credential, not before offline coding. Exact Q3/Q7 matches not supplied; not a SELECT-only sandbox. |
| Auth function PUBLIC EXECUTE | Q7 confirmed. Not permission to add Auth USAGE; runtime must have no effective Auth-schema access. |
| PUBLIC custom/extension relations, DML or routines (especially SECURITY DEFINER) | No blanket allowance. Unknown/unreviewed reachable entries block hosted setup, not offline implementation. Vault presence does not authorize its data/functions. |
| Managed-role default grants | Q9 confirmed generally, exact grantees unspecified. Preserve existing global/provider ACLs; revoke/guard only new owned objects. |
| New private schema/function | Only postgres owner + reader USAGE/exact EXECUTE; no PUBLIC/API-role access or grant option for reader. Draft aborts on other default grantees. |
| New reader | Only intended grants plus accepted PUBLIC baseline; no memberships, broad flags, privileged SET paths or ownership. Actual Q5/Q8 check follows separately authorized creation. |

[PUBLIC guidance](https://supabase.com/kb/troubleshooting/custom-role-inherits-privileges-that-were-not-explicitly-granted-ddaa1c): NOINHERIT cannot remove the baseline.
Only vault was present among checked optional extensions; reachable-routine safety is unproven.

## Final readiness recommendation and deferred gates

**Recommend approval: dormant observation component + isolated offline tests only.**
Existing definer visibility and configured private-schema exclusion are sufficient
for that scope. No further broad investigation or hosted checks are required to
approve offline work. This recommendation does not authorize implementation here.

Wrapper check: none observed in the owner's exposed-object listing; generic/dynamic
wrappers and exhaustive absence remain unproven. Q5 summaries establish postgres's
powerful inheritance, not absence of API-role-to-postgres SET/inherited paths.
The draft rejects transitive API access to reader/owner; prove that guard offline.
Existing wrapper/API-owner-path unknowns do not require reader creation to inspect,
but remain hosted-setup gates. Actual reader grants/memberships, effective PUBLIC/
extension access and API-to-reader paths cannot be tested until authorized creation.
Never describe those deferred tests or revocation semantics as already passing.

[Automatic exposure guidance](https://supabase.com/kb/troubleshooting/cant-change-the-default-privileges-of-supabase_admin-in-the-public-schema-448af9): the toggle affects postgres defaults in public, not private-schema exposure.
Keep the capability outside public with atomic revokes/default-grantee guards; no wrappers or toggle change.
Before hosted setup: approve the baseline, resolve unknown reachable grants/paths,
and validate installation ACLs. Before activation: lifecycle/latency and other auth
policy gates must pass. Hosted DDL, secrets and activation need separate approvals.
The only next owner decision for this review is whether to authorize that offline
implementation scope, within Prompt 11. No PR, hosted execution or Prompt 12 now.

## Verification tests — approved offline; hosted tests require separate authorization

Offline SQL fixture result: **29 passed on local PostgreSQL 17.11**. The harness
extracts the guarded proposal only into fresh loopback databases with mock roles;
no hosted installation or lifecycle result follows. PUBLIC TEMP remains observable.
Stacked review-branch CI is enabled without altering the manual production release.

### Dormant Python observer (Prompt 11)

`SupabaseStateObserver.observe(raw_jwt)` verifies ES256 using the existing verifier,
then opens a fresh, bounded PG17 READ COMMITTED READ ONLY transaction. Configuration
pins the direct project DB host, reader username and verify-full TLS/root trust;
ambient libpq overrides and poolers are unsupported. No env configuration or routes
instantiate it. One connection/check per instance, no positive state cache.

Before reading markers it enforces owner/body/search-path/ACL/role invariants and
compares a bounded SHA-256 catalog fingerprint to an explicitly owner-approved
server configuration. Roles/memberships, database/schema/table/column grants,
function bodies/ACLs, policies, defaults, extensions, large-object ACLs and settings
are covered. Metadata only: no Auth row/credential inventory. No hosted fingerprint
is approved or supplied; never auto-approve the first observed snapshot. Any drift
(including benign/unrelated changes) denies pending review. API exposure settings
remain a separate hosted gate; the catalog cannot prove every external service's
configuration or eliminate concurrent administrator changes.

Results are frozen, repr-hidden verified claims/issuer/nonce/DB time plus four
independent binding/marker flags. They are NOT LiveAccountSession/LiveStateSource:
no invented email evidence, enabled/present state or full revocation guarantee.
Existing AuthenticationEvidencePolicy is unchanged and still denies without its
mandatory trusted sources. No genuine mailbox, MFA recency or ownership bypass.
Socket connect/server statement/transaction limits and a three-second post-check
budget fail closed; they are not hard cancellation during a network partition.
DB/app clock tolerance is three seconds, not proof of instantaneous revocation.
Local stack validation: **487 security/regression tests passed**, including 29 SQL
and 32 observer cases; 10 PR-budget tests passed. These are offline passes only.
Stacked PRs must be reviewed in order; after each squash merge, rebase the child
onto updated main before retargeting and rerun its complete-PR budget/CI checks.

Use an empty isolated PostgreSQL 17 fixture database with synthetic tables/UUIDs
and mock API roles; never a Supabase/Neon URL. Reproduce managed/PUBLIC defaults.

| Test | Required result |
| --- | --- |
| Matching subject/session, no ban/deletion, NULL/future not_after | Exactly one result; four true flags and aware observation time. |
| Unknown/cross-account IDs, missing user or duplicated join | Binding and clear flags false; no row details. |
| Soft deletion, active ban, expired/equal not_after | Respective flag false; consumer denies. |
| NULL/zero/non-UUID inputs | Rejected; application strips SQL details. |
| READ WRITE/REPEATABLE READ, or RLS now applies to definer | Error; never stale/filtered evidence relabeled as positive state. |
| API/PUBLIC invocation, Auth read/write, private CREATE, privileged SET | Denied except explicitly accepted PUBLIC baseline; assert effective/transitive rights, not direct ACLs alone. |
| Hostile search_path/temp objects/fake JWT GUCs | No substitution; qualified reads and verifier-derived UUIDs only. |
| Unexpected default grantee | Guard aborts; no committed PUBLIC window. |
| Timeout/outage/malformed output, wrong issuer/nonce or replay | Generic denial/unavailable; no cache, JWT-only/legacy fallback or sensitive logs. |

Hosted lifecycle tests require separate approval: two disposable accounts A/B,
A sessions A1/A2 and B session B1; retain tokens privately, no admin runtime key.

| Acceptance case | Required observation in fresh transactions |
| --- | --- |
| Sign-out local/global/others from A1 | After acknowledgment: local removes A1 only; global A1/A2; others A2 only. Affected binding flags false; B1 unchanged. Compare fresh getUser; delays/disagreement block activation. |
| Approved owner hard/soft deletion of A | Hard: no join. Soft: deletion_clear false or no join. B unchanged; unsupported/unapproved soft-delete operation remains unproven. |
| Approved owner ban/unban A | Active ban: ban_clear=false even with surviving row/JWT; deny access. Unban changes only that marker, not other gates; compare getUser. |
| Expiry | JWT expiry denies despite row presence. Local not_after boundaries: NULL/future clear; equal/past deny. No paid hosted timeout activation or SQL writes; unavailable hosted absolute-expiry tests remain unproven. |
| UUID mismatch | A+A1 binds; A+B1, B+A1 and random session do not. Zero/malformed IDs rejected; no client-directed relinking. |

Measure concurrent revocation propagation, clock skew and observation-to-use windows;
password-reset effects remain an activation gate. No pre-existing account mutation,
PII/bind values/error CONTEXT in reports or fixture-only claims of hosted success.
