# Account operations — implementation prepared; EXECUTION DISABLED

Start: `fabe263` main, merged PR98–103. Review the new dependent stack in order:
PR104 factor-removal continuation → PR105 journal → PR106 provider worker →
PR107 server authorization → PR108 transactional privacy fence → PR109 gated UI
→ this readiness reconciliation. Every child diff must remain ≤500 lines after
rebasing for squash merges. No production activation follows from merge safety.

| Operation | Implemented candidate | Current execution / remaining gate |
|---|---|---|
| List/enroll/challenge | Existing fresh native factor inventory, first/additional TOTP and signed AAL2. | Dormant in production; existing hosted first-factor evidence does not establish all mobile/race cases. |
| Replace authenticator | Accessible alternative challenge, exact new enrollment and replacement verification. | Existing dormant flows remain; old-factor deletion is disabled because retain-one cannot be guaranteed. |
| Remove/opt out | Fresh native challenge, owned signed AAL2, exact session/inventory binding, explicit possible-zero-factor consent, one supported DELETE and same-account logout. | All current bootstraps select unavailable defaults. Review opt-out policy and genuine multi-device semantics first. No backup-retention promise. |
| Delete account | Server fresh-password proof; enrolled users also execute fresh owned TOTP; issuer/subject/session/creation binding; short-lived signed intent; irreversible confirmation. | No current entry selects the candidate, loads signing/admin credentials or installs its journal. Worker/privilege/retention and hosted acceptance remain gates. |
| Pending privacy | Candidate blocks personal/settings/provisioning routes; queue revokes invitations/credentials; transaction locks prevent late writes; group queries exclude pending peers. | All serving revisions must adopt the fence before submission. Old unaware/legacy paths must not coexist as a bypass. Admitted reads may finish. |
| Erasure/retries | Fresh exact-UUID provider absence before atomic local erasure; leases, signed phases and audit; fresh reauthentication renews expired unclaimed intents. | No distributed transaction. Unknown outcomes stay blocked/retryable; no identity recreation, relinking, guessed completion or hard-delete rollback. |

See [factor analysis](FACTOR_REMOVAL.md), [state](ACCOUNT_DELETION.md),
[worker](DELETION_WORKER.md), [authorization](DELETION_AUTHORIZATION.md),
[privacy fence](DELETION_RESOURCE_FENCING.md) and [UI](ACCOUNT_REMOVAL_UI.md).
Application schema remains 4; `deploy/review-only/account-deletion.sql` is NOT
APPROVED FOR EXECUTION and is not registered with migrations. Fixture DDL runs
only in disposable schemas. No production data or existing hosted account changed.

## Required decisions before hosted execution

1. Review deliberate opt-out separately from guaranteed backup retention. Native
   DELETE has no expected-count/revision condition. A fresh-challenge UI cannot
   impose provider-wide freshness on direct AAL2 API callers. Keep all-lost recovery
   and retain-one deletion disabled; no email/password bypass.
2. Approve a separate non-public worker/secret boundary. Supabase's admin key is
   broad, not per-user scoped. No browser/web-serving process receives it. Approve
   dedicated DB grants, signed-intent key custody/rotation and effective permissions;
   no roles or credentials were configured here.
3. Approve journal DDL, backup/rehearsal and tombstone/audit retention. Verify actual
   DB target/schema and every serving revision. Retain pending intents on failure;
   do not roll back to an unaware/legacy binary against that database.
4. Establish Storage ownership/cleanup and provider backup retention. Storage-owner
   refusal blocks deletion with Neon intact. Prohibit concurrent administrative UUID
   reuse: creation-time binding detects many cases but GET/DELETE cannot make that
   race atomic. Approve a total worker deadline and retry/stop policy.
5. Approve exact frontend/API/issuer targets and a verifiable CA$0 no-overage plan.
   Credits and nominal Free allowances are insufficient. No cloud action was taken.
6. Authorize a new explicit low-volume mutation/notification budget, disposable owned
   accounts, independent authenticators and cleanup permissions. Existing 10/10 is
   exhausted; no new hosted mutation or deletion occurred during implementation.

## Genuine-provider acceptance still required

Test wrong/expired/replayed TOTP, last-factor opt-out, competing devices, stored AAL
downgrade, old JWTs, other-session revocation and re-login on the actual hosted build.
Then test native deletion proof, wrong account, session switching, storage refusal,
generic versus real 404, expired authorization renewal, lost DELETE acknowledgments,
provider/Neon outage recovery, residual invitations, fleet isolation and audit
retention with separately approved synthetic accounts. Offline fixtures do not prove
these properties on hosted Supabase, Neon, Azure or Vercel.

Retain the full NIST SP800-63B-4 controls/evidence/gaps assessment and original
16-stage professional audit. Neither is replaced, completed or begun by this work.
Release remains **NOT READY**. Default production authentication/resources are
unchanged; no merge, deployment or production erasure was performed.
