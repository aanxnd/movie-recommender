# Production launch readiness — NOT READY / execution not authorized

Owner direction, November 15, 2026: deliver the complete production Movelle
experience; local staging is an engineering fixture, not the final owner acceptance
environment. This plan does not authorize deployment, public signup/configuration,
cloud resources, migrations, spending or authentication activation. The original
26-prompt roadmap and full NIST/16-stage assessment requirements remain intact.

Target: create account → confirm email → complete profile → optional TOTP/backup
→ rate films → recommendations → consent-based groups/account settings → logout
and sign back in. Cosmetic readiness is not authentication or release readiness.

## Evidence matrix

| Area | Implemented/offline evidence | Genuine provider evidence / remaining work |
|---|---|---|
| Signup/login/confirmation | Native SDK, PKCE/S256, once-only scrubbed root callback, safe errors and session fencing. | Real dev signup/confirmation/password sessions passed. SDK redirectType=null is not signup-purpose evidence; backend native current-email policy remains authoritative. Public origins/settings/abuse controls unapproved. |
| Identity/profile | Atomic schema3 provisioning; unique case-insensitive ASCII usernames; UUID maps to server-allocated numeric ID. | Real Supabase plus **local** PostgreSQL profile creation passed. No production/Neon schema, account linking or migration has been verified/approved. |
| MFA | Optional first TOTP, AAL2 challenge, additional independent factor and backup continuation; enrolled AAL1 denial. | Real first-factor QR/verification, stale and fresh-password AAL1 denial and second challenge passed. Independent Google/Duo devices, replacement/races and broader failures need genuine acceptance. All factor removal remains disabled. |
| Password/email | Native recovery, purpose-bound callbacks, same-account fences and safe unknown outcomes. | Real non-MFA recovery passed. Enrolled-account password/email actions remain intentionally restricted; genuine email-change ordering, A→B→A, replay/expiry and recovery-with-MFA are unproven. |
| Ratings/recommendations | Native ownership, numeric IDs, fractional ratings, bounded CPU/DB work and unchanged mathematics. | Real dev Auth/local app saved5 ratings and recommendations API returned10; production dataset/capacity and actual deployed UI are not proven. |
| Groups | Native invitation/expiry/consent checks; no peer raw-rating read/write; UI/offline multi-account coverage. | Genuine multi-account provider/deployed group journey still needed. Current groups are invitation-based computations, not persistent shared group records. |
| Settings/lifecycle | Read-only owned username adapter; separate safe mutation contracts/screens. | Username mutation and account deletion are unavailable in the current native composition. Do not advertise those functions as complete. Implement/review them or explicitly approve disclosed launch exclusions. |
| Session/logout | Native restoration/refresh/account-switch fencing, backend JWT/current-email/factor checks. | Provider logout204 and restoration evidence exist. Exact old logout text assertions failed on an informational suffix, not a demonstrated logout failure. Verify deployed UI completion and accepted bounded token validity; no immediate-revocation claim. |
| Visual/theme | PR95→96 reuse existing presets/key/tokens with cinematic copy, copper default, keyboard and responsive checks. | Cosmetic/offline evidence only. Production main.jsx still selects the legacy application, not these native account screens. |

The [initial campaign](STAGING_SUPABASE_ACCEPTANCE.md) and
[follow-up](NATIVE_MFA_FIX_ACCEPTANCE.md) used genuine Supabase **development Auth**
with a loopback app/local PostgreSQL. They are not Azure/Vercel/Neon deployment
acceptance. Fictional-provider tests simulate emails, factors and outages; they
cannot establish hosted provider settings, mail delivery or mobile independence.

## Ranked release blockers

**P0 — CA$0 and execution authority.** Owner-reported Azure charges were CA$1.50
in November despite amount due0/remaining student credits138.35. Those observations
are not live billing checks and do not establish zero incremental usage. Vercel
Hobby and Neon Free capacity are shared/limited; branch count/storage alone are
insufficient. No cloud query, resource or deployment was performed for this plan.

Public ingress, even denied requests, can consume Azure resources. Credits offset
invoices; they do not eliminate metered consumption. Confirm compute/memory/request,
logging, network, registry, Neon CU/egress/storage and frontend/function allowances
with enforceable no-overage behavior. Alerts/min0/max1 are not hard free-spend caps.
If no production architecture can establish the strict CA$0 boundary, release stays
blocked. Investigating a hard-free alternative needs a reviewed design; no resource
may be created and the request for production is not permission to spend credits.

**P0 — Coherent native production composition.** Production still uses legacy
bearers. The local and private entries are separate tested foundations, not launch
switches. Build a reviewed production backend/frontend composition using existing
native dependencies, provisioning and resource routers. Keep anonymous browsing;
personal actions require fresh backend policy and numeric ownership. Never expose
legacy issuance/fallback beside new auth or turn a private preview public merely
by removing its gate/mode/origin checks. Remove staging controls/test providers
from the release UI and preserve root callback purpose/session fencing.

**P0 — MFA/account feature policy.** Resolve legitimate password/email changes for
enrolled users without password-only downgrade. Review supported AAL2-authorized
factor removal/opt-out and cross-device races; frontend refusal is not a global
Supabase policy. Current unconditional provider DELETE is not proof of final-factor
retention. Implement a reviewed supported approach or obtain explicit acceptance
of disclosed unavailable functionality before advertising a complete account system.
All-factors-lost lockout remains disclosed; no email-only bypass, custom Auth DB
reader, independent mailbox ledger or paid recovery feature. Native recovery codes
remain rejected for initial launch, not an unresolved implementation requirement.

**P1 — New bounded hosted acceptance.** Existing conservative email reservations
are **10/10**; no new signup, recovery, email/factor/account mutation is authorized.
Obtain a new explicit budget, owned test accounts/inboxes, safe authenticator/link
handoffs and cleanup permissions before testing. Do not reuse C's unretained seed,
remove factors, reset accounts or send extra messages to work around prerequisites.

**P1 — Data and legacy retirement.** No legacy migration/linking is approved. Keep
numeric IDs, ratings, identities and invitation relationships intact. Owner must
approve historical legacy users' access/retention/communication plan; matching an
email/username/ID never claims data. Repository schema3 is not proof of live Neon
schema; older release records describe schema2. Separately approve read-only live
inspection, additive migration rehearsal and schema-compatible rollback. Never
drop/reset tables/sequences or roll back to a schema2/unauthorized legacy binary.

**P1 — Mail, abuse and provider configuration.** Gmail dev delivery/Outlook junk
placement does not establish public sender limits, deliverability or abuse safety.
Verify native Confirm Email/recovery/email-change settings, supported Free password
controls, signup/email throttling and applicable Free bot controls. Record gaps
rather than buying features or claiming NIST compliance. Approve exact public
frontend/API origins and intended issuer/project/ES256/JWKS/audience; the dev
project's prior acceptance is not production authorization. No wildcard callback,
service-role/admin key in client code, arbitrary redirect or URL credential evidence.

**P1 — Operational reliability and final audit.** Rehearse cold starts, exact prepared
dataset/digest, memory/CPU/concurrency/pool ceilings, rate/body limits, backend/provider
outages, backup/restore and bounded rollback. Small offline results do not establish
32M public capacity or cost. Verify optional artwork fallbacks/rights/quotas without
exposing personal keys. Validate platform logs/query/header redaction, TLS, CORS,
security headers, monitoring and stop/maintenance behavior before exposure.
Complete the full NIST SP800-63B-4 controls/evidence/gaps assessment and original
16-stage professional audit before public activation. This plan starts neither.

## Implementation and acceptance sequence

1. Review cosmetic PR95→96 independently; no native auth activation is bundled.
   Review this production plan separately. Rebase child diffs after squash merges;
   each complete implementation PR must stay at or below500 added+deleted lines.
2. Resolve the cost/target approval gate. In parallel, implement the missing native
   account/MFA/settings and final product composition in small dormant PRs. Each
   needs adversarial ownership, subject/session/AAL, race/outage and no-fallback tests.
3. Complete offline browser/mobile/keyboard regressions of the entire target journey,
   including unknown write outcomes, cross-account/group denial, callbacks/replay,
   signup/login double clicks, logout/account switches and theme continuity. No test
   stubs/preview booleans may become authorization or appear in a release bundle.
4. After separately approved capacity and configuration, run genuine hosted Auth
   acceptance: zero/unverified/verified factors, both independent devices, wrong/expired
   JWTs/codes, unconfirmed/current-changed email, both email-change orders, recovery,
   enrolled sensitive actions, logout/refresh, multi-account groups and outages.
   Report each case PASS/FAIL/NOT RUN with source/version and sanitized evidence.
5. Verify the exact final production-shaped artifact/configuration and approved
   schema/rollback. Local staging is test infrastructure, not another final owner
   preview milestone. Record remaining failures and run the full professional audit;
   findings require remediation and retest, not a compliance badge from green CI.
6. Only after explicit release/migration/activation approval, execute the reviewed
   native-only cutover without mixed credentials or unauthenticated old revisions.
   Production domain promotion and Azure release are separate coordinated actions;
   main merges may auto-build Vercel. Verify no unexpected public exposure first.
7. Validate deployed owner journey and access denials against the actual approved
   targets, then public rollout only if authorized. Owner feedback should concern
   functional/visual defects, not unfinished security controls or missing features.

**Single next owner action:** resolve the strict CA$0 production-hosting gate with
a verifiable no-overage plan. Without that evidence there is no deployment approval
to request or execute, regardless of available student credit or cosmetic test passes.
