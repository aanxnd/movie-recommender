# Prompt 23: dormant provisioning and staging checkpoint

Stage 23 follow-up: the explicitly selected local staging application now composes
this API and frontend. See the [integration report](STAGING_CHECKPOINT_REPORT.md)
and [current local commands](STAGING_INTEGRATION.md). Statements below about future
bootstrap/cloud acceptance describe the original handoff; production remains dormant.

## Existing model and first boundary

Baseline: `8616a68554fc710b02657190586e66d18332bb90`, schema 3. `users.id`
is a database-allocated numeric key. Nullable `user_identities.supabase_subject`
is unique; `user_id` is its primary/foreign key; lower(username) is unique.
Ratings and expiring group invitations reference numeric IDs. There are no
password accounts, watchlists or persistent group memberships in this schema.
Opaque legacy credential digests/expirations live separately in
`profile_credentials`; `database.create_user` alone issues no credential.
Live POST `/users` and operator `recover-profile` separately issue credentials.
Existing capacity (5,000 profiles) and database admission counters must remain.

`make_provisioning_dependency` builds a trusted, immutable subject/session/AAL/
expiry principal without resolving an existing numeric profile. It reuses strict
ES256 verification and a fresh native current-email/factor check. No routes are
mounted. This is not a resource-access grant, real-time revocation check or proof
of recent MFA. Existing resource dependencies and global policy are unchanged.

Provisioning explicitly denies missing, null **and empty** factor inventories.
Prompt 20's authoritative no-factor completeness blocker remains: legitimate
accounts without provable inventory cannot provision. Nonempty provider evidence
uses the existing verified-TOTP → signed AAL2 rule. Initial MFA enrollment is not
unblocked here. Offline fixtures do not establish hosted response completeness.

The request contract accepts only `username`: 3–30 ASCII letters, digits or `_`,
case preserved, no trimming/Unicode normalization. Reserved names match the
frontend contract; the database enforces ASCII case-insensitive uniqueness.
No subject, numeric owner, email, AAL or linking evidence is accepted as input.

Production remains legacy-only and anonymous browsing is unchanged. Prompt 23's
principal, transaction, issuance-isolation, API and frontend changes are separate
review dependencies. No hosted changes, migrations or acceptance tests have
been performed. Prompt 24 remains on hold at the staging checkpoint.

## Transaction service

`inspect_profile` performs a fresh subject-only lookup. `provision_profile`
requires the trusted principal plus validated `ProfileInput`; no arbitrary
idempotency key or legacy owner is accepted. A fresh short Session owns the whole
User + UserIdentity transaction. The existing permanent capacity lock serializes
creation with legacy registration; a post-lock subject recheck preserves retries
at capacity. Database unique constraints remain final authority. No credentials,
ratings, invitations or extra profile state are initialized. Sequence gaps after
rollback are harmless; numeric sequences are never reset.

Existing linkage wins without renaming. After any database exception the failed
transaction closes before a fresh authoritative read. A committed subject is
returned; an actual competing username is a sanitized 409; unknown outcomes are
503, never an automatic second INSERT. Expiry is checked before work, before
commit and before returning. An expired response after commit requires new
authentication and inspection, not rollback of already-committed state.
Schema 3 already supplies the constraints; **no migration is required**.
Offline PostgreSQL tests exercise separate sessions/processes, capacity races,
case collisions and lost acknowledgements; these are not hosted acceptance tests.

## Dormant HTTP contract

`make_provisioning_router` is deliberately absent from `app.main`. A future
owner-approved staging composition must explicitly include it and install the
existing bounded-body `RequestLimits` plus exact-origin CORS. No existing env
flag enables it. GET `/auth/profile` returns `{status: eligible}` or
`{status: complete, username}` for the verified subject only. POST at that same
path accepts exactly `{username}` and returns complete; it is separate from live
POST `/users`. There is no profile-ID or subject parameter, claim or repair route.

Both operations authenticate freshly, reject query parameters/foreign Origin,
redact validation input and use no-store responses. Admission commits separately:
30 subject checks/minute; 10 creation attempts/hour per subject; the existing
1,000/day global creation bucket is shared with legacy creation. Parent request
limits retain public/IP admission and 16-KiB bodies. 409 is username unavailable,
401/403 denial, 422 invalid input, 429 bounded rate denial, 503 unknown/unavailable.
Clients must re-inspect after uncertain writes; no automatic POST retry.

## Dormant frontend adapter

`createProfileProvisioning(config)` uses the shared native SDK/controller and
authenticated API transport, then is passed explicitly as ProfileSetupScreen's
`service`. No production bootstrap imports it. GET inspection never creates a
profile. A user must submit the exact username for POST. Shared in-flight state
prevents duplicate writes across consumers; database idempotency remains final.
Logout, account A→B→A, caller abort and same-subject token refresh fence pending
results. No second token store or legacy storage cleanup exists. After an unknown
write outcome only a same-credential GET may recover complete; otherwise the UI
shows uncertain and offers inspection, never an automatic POST replay. Rate
denial/conflict and malformed response fields remain sanitized. A complete result
does not grant resource authorization or unblock any unresolved MFA gate.

## Staging plan — approval required, not deployed

Stop feature development here. Review/merge the stack in order, then approve an
isolated staging composition and its immutable SHA before any deployment. Do not
start Prompt 24 until initial staging integration results have been reviewed.
Production activation remains exclusively Prompt 26. The full NIST SP 800-63B-4
assessment and original 16-stage audit remain required; no compliance claim follows
from these tests. The owner maintains the fixed roadmap/audit separately.

| Component | Proposed isolation / approval needed |
|---|---|
| Frontend | Local `http://127.0.0.1:5173`; isolated browser profile/native SDK namespace, no real legacy browser credentials. Cloud preview/production **TBD/unapproved**: owner must name exact HTTPS origin, no wildcard. |
| FastAPI | Separate staging process/service, DB and CORS; no production route traffic. Explicitly compose provisioning router with bounded body/IP middleware and exact CORS. Existing native resource dependencies remain separately reviewed; this factory does not cut over their routes. |
| Application DB | Disposable PostgreSQL 17 with synthetic data; never the production Neon URL, branch or copied personal records. A cloud Neon staging branch/project requires owner isolation/$0 verification first. No hosted creation is performed here. |
| Auth | Existing `movelle-auth-dev` only after explicit owner approval of synthetic staging signup/email/factors and its URL/key/issuer. No production identities or privileged keys. Approval for earlier probes does not authorize new account mutation here. |
| Cost | Local existing tooling + disposable PostgreSQL is the $0 fallback. Do not provision Azure/Vercel/Neon resources until owner verifies incremental cost and approves exact targets. Free-plan limits/pausing and Gmail quotas remain constraints. |

Configuration names (never credential values):

- Frontend: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`,
  `VITE_AUTH_APP_ORIGIN`, `VITE_API_BASE_URL`. No database/admin/SMTP values in Vite.
- Backend: `SUPABASE_URL`, `SUPABASE_AUDIENCE`, `SUPABASE_PUBLISHABLE_KEY` are
  trusted future bootstrap inputs to the existing factories, **not auto-loaded
  activation switches**. Audience is `authenticated`. Derive issuer/JWKS from the
  same pinned project. `DATABASE_URL` is application PostgreSQL only (TLS for cloud).
  Existing `APP_ENV`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_PROXY_IPS` and
  `MOVIELENS_PREPARED_DIR` retain their current semantics. Local staging may use
  `APP_ENV=development`; cloud production-mode validation requires HTTPS CORS/TLS.
- Local tooling/test names: `MOVELLE_DEV_API_PORT`, `MOVELLE_DEV_INSTANCE`,
  `POSTGRES_TEST_URL` (disposable loopback only). Existing launchers compose the
  legacy app, **not** a staged native-auth application. The new dedicated
  `npm run dev:staging` uses only `MOVELLE_STAGING_*` inputs documented separately.

No production enable flag exists. The separate local staging bootstrap mounts
`make_provisioning_router` with a fresh Session factory and approved origins, and
inject `createProfileProvisioning` into the shared AuthProvider/ProfileSetupScreen.
Review the integration PRs before running it; simply setting env variables cannot
activate dormant production code. Never wrap live POST `/users` as provisioning.

Provider configuration to review privately: Confirm Email enabled, native
email/password signup and recovery, ES256 signing/audience, optional TOTP and
independent backup factor. Keep the maximum factor count consistent with the
current limit of 10. Current factor completeness is unresolved: empty/omitted
inventories deny provisioning, including AAL2. Initial enrollment, final-factor
deletion and all-devices-lost recovery remain blocked; no email-only bypass.
MFA-sensitive password/email changes remain restricted by the existing native
reauthentication limitations. This prompt does not change any of these decisions.

Email/signup and recovery both use the exact approved local root callback
`http://127.0.0.1:5173/`, native PKCE/S256, one code, no arbitrary next/redirect
input; email-change uses the existing separately scoped root consumer. The future
staging bootstrap must select the correct consumer; callback hints are not signup
provenance or backend permission. Owner must separately approve each cloud origin
and its exact `https://<approved-origin>/` callback, CORS origin and Site URL/
redirect allowlist before hosted changes. No origins are guessed. Gmail production
suitability, delivery/spam placement, sender/rate limits and abuse remain open.

## Rehearsal and acceptance matrix

1. Privately verify isolated targets, database fingerprint/schema version and
   logging before sending traffic. Never print URLs containing credentials. Build
   immutable reviewed images/assets; hosted release workflow is manual, not a
   merge action. PR Vercel checks use the unchanged dormant production entry.
2. Create an empty disposable application DB. Run existing explicit migrations
   there only to schema 3, inspect constraints and seed synthetic movies/legacy
   fixtures. No Prompt 23 migration/backfill is needed. Schema 2 hosting remains
   incompatible until a separately approved additive migration/rehearsal; do not
   infer the current hosted version from repository files.
3. Owner-approved synthetic Auth accounts only: current confirmed/unconfirmed
   email, anonymous/rejected tokens, verified/unverified/absent factor inventories,
   AAL1/AAL2. Record sanitized provider shapes, never tokens, addresses or secrets.
   Absence/completeness must be resolved before no-MFA enrollment/continuation.
4. Test anonymous browsing creates no profile; explicit provisioning creates only
   User+identity, repeated/cross-process requests preserve one ID/name; subject and
   ASCII-case username conflicts roll back. Disconnect before commit, lose HTTP
   acknowledgement/commit acknowledgement, expire proof during writes, exhaust
   quotas, retry with refreshed proof, inspect during creation. No orphan/linking.
5. Exercise native signup/confirmation/recovery callback boundaries, expired/reused
   links and provider failures at low email volume. Acceptance requires approved
   Gmail delivery/spam/rate evidence, not just a prior successful dev invitation.
6. Verify frontend double clicks, StrictMode, logout/A→B→A/refresh/unmount fencing,
   conflict focus/mobile/keyboard flows and uncertain-write GET recovery. No second
   token store or legacy fallback. Test backend resource ownership/group/privacy
   separately; completing setup is not permission to read another numeric profile.
7. Verify legacy creation/restoration/recovery and unchanged ratings/invitations;
   native profiles get no legacy credential through issuance/operator recovery.
   Wrong-provider bearers deny at each boundary. Never automatically migrate or
   claim historical users by ID, email, name, metadata or opaque credential.
8. Disable request/response body capture and redact Authorization, callback queries,
   cookies, usernames, email, SQL parameters, provider diagnostics and error traces.
   Monitor only aggregated statuses, latency, quota/outage counts; no raw evidence
   in logs, screenshots or shared test reports. Verify access-log URL scrubbing.
9. Rehearse rollback by stopping the isolated staging entry, restoring the last
   reviewed dormant revision and retaining schema-3 data/constraints. Never drop
   users/identities, reset sequences, revoke sessions or restore a legacy fallback
   for newly native-owned profiles. The rollback binary must retain the Prompt 23
   legacy-issuance guard; otherwise keep all issuance/operator entry points offline.
   An old schema-2 binary is not a safe rollback.

Local checks: full backend 1,391 passed / 11 skipped (local PostgreSQL enabled);
548 frontend tests; unchanged production asset hashes; four new
approved-origin Chrome provisioning checks plus 14 existing auth/MFA/password/
legacy browser regressions; 21 transaction tests on SQLite/local PostgreSQL 17,
including spawned-process races; 94 legacy/identity/provisioning regressions;
42 isolated HTTP tests; 10 PR-size unit tests. These overlap and must not be summed
as distinct backend coverage. Hosted CI must pass for each exact PR head separately.
No frontend lint/typecheck script is configured; Node tests and Vite build apply.

Remaining owner decisions: exact isolated staging origins/services/database, $0
capacity confirmation, explicit hosted configuration/account/email-test approval,
approved staging composition and monitoring. Before production cutover, approve
historical legacy users' data/access disposition: duplicate new accounts do not
inherit old data; retiring legacy access could abandon/invalidate access to it.
That release remains blocked without an explicit decision, full assessment/audit
and all factor/email/provider acceptance gates. No hosted behavior is verified by
the local fixture tests. **Prompt 24 has not begun.**
