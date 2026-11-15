# Native completion review — NOT READY FOR DEPLOYMENT

Review order: PR98 (schema4 revision) → PR99 (owned username API) → PR100 (backend
release entry) → PR101 (frontend release entry) → PR102 (AAL2-sensitive password
proof) → this readiness reconciliation. Rebase child diffs after squash merges;
never merge the whole accumulated stack as a single >500-line PR. No PR merges,
cloud changes, hosted accounts, emails, factors or database mutations occurred.

## Implemented boundaries and tests

| Boundary | Control / residual limitation |
|---|---|
| Native/legacy separation | New `app.native_release` and `native-main.jsx`; default live entries unchanged. Public GET allowlist plus native protected/provisioning/settings routers; no legacy bearer issuance/fallback. |
| Configuration | Reviewed exact HTTPS frontend/API/project pins, dedicated TLS Neon target/role, schema check only. Public build excludes database fields; invalid configuration refuses startup/build. Owner pins remain unapproved. |
| Ownership | Existing subject resolver, numeric profile and group permissions; settings has no client-selected owner. Database uniqueness and revision CAS preserve IDs, ratings and invitations. |
| Sensitive MFA | Fresh exact-subject inventory and primary signed AAL2; isolated signed password session, scoped cleanup, unchanged primary credential. No nonce bypass, recent-MFA or immediate revocation claim. |
| Concurrency/failures | Credential/abort/session fences, CAS/ABA rejection, quotas, no write retries. Unknown commits require inspect; lost sign-in responses cannot prove temporary-session cleanup. Supabase/Neon observations remain non-atomic under the approved policy. |
| Browser artifact | Existing cinematic/theme/session components; no operator bar/test provider/legacy storage. Offline actual-bundle check refuses unapproved targets. No deployment selector was changed. |

Local backend stack: 1510 passed, 11 skipped; focused synthetic PostgreSQL/SQLite
migration/settings/composition: 63 passed. Frontend before the MFA continuation:
641 passed; including it: 656 passed. Actual pinned-SDK sensitive MFA tests: 15
passed. Browser/hosted CI results must be checked at each final PR head; fixture
results are not genuine hosted Supabase/Neon/Azure/Vercel acceptance. Existing
Starlette test-client deprecation and staging chunk-size warnings remain visible.

## Still unavailable; proposed review boundaries only

**Verified-factor removal / optional opt-out is not implemented.** Pinned
[GoTrue DELETE](https://github.com/supabase/auth/blob/v2.197.0/internal/api/mfa.go)
requires stored-session AAL2 for a verified factor, deletes that factor and
downgrades affected sessions. It offers no expected-inventory revision or atomic
"retain one" operation. A future supported opt-out flow should explicitly disclose
that every removal can leave zero factors, require signed current AAL2, bind the
exact subject/session/factor, avoid retries, refresh/reinspect after deletion and
report unknown/partial outcomes. It must replace the old final-factor-retention
invariant explicitly in the reviewed contract, rather than pretending client counts
provide it. Independent backup enrollment and all-lost lockout remain unchanged.
The current UI/services still send no DELETE, including during recovery.

**Account deletion is not implemented.** Official
[admin deleteUser](https://supabase.com/docs/reference/javascript/auth-admin-deleteuser)
requires a privileged server credential; no public user deletion API was established.
Approval of account management does not make Neon and Supabase one transaction.
Before a separate implementation: review a server-only privilege boundary, exact
owner/assurance checks, retention/erasure semantics and a durable deletion-intent
state that blocks access before irreversible provider deletion. Audit and reconcile
partial failures idempotently; never silently restore access, recreate/link an
identity or delete Neon first. No broad key is requested, stored or activated here.

## Next gates

Review the dormant stack and the two unfinished operation designs above. Then
approve exact resource/origin pins, schema4 rehearsal/rollback and a verifiable
CA$0 no-overage architecture. Student credits/free quotas alone are insufficient.
Obtain a new explicit email/factor/account test budget and safe independent
authenticator/link handoffs before genuine hosted acceptance; existing 10/10 remains
exhausted. Review secure-password-change/nonce/email settings and both confirmation
orders, provider races/outages, cross-account groups, cold starts and resource limits.
Retain the full NIST SP800-63B-4 controls/evidence/gaps assessment and original
16-stage professional audit. Neither is completed or started by these PRs. No
activation/deployment is approved by tests, configuration presence or merge safety.
