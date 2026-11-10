# Supabase configuration and launch gates

Prompt 11/26 owner revision replaces the old strict-policy configuration proposal.
The current contract is [standard Supabase policy](AUTH_POLICY_EVIDENCE.md).
All new authentication remains dormant; no environment or hosted setting is changed.
Prompt 12 stays on hold. Prompt 11 needs owner review and approved merges.

## Evidence boundaries

- Repository: ES256 verification, typed claims, native confirmation/OTP, standard
  policy and UUID-to-numeric-ID resolution are offline tested; no protected route
  consumes them. Neon schema 3 and legacy authentication remain unchanged.
- Previously observed public JWKS: the development project's pinned endpoint
  supplied EC/P-256/ES256 verification keys. This establishes no account settings.
- Owner-reported: Free `movelle-auth-dev`, TOTP enabled with ten factors, disposable
  signup/verification/password login and Gmail SMTP delivery passed. Outlook junk
  placement leaves production delivery unresolved. No hosted behavior is retested.
- Owner-reported inspection: private `movelle_auth_private` was outside Data API
  exposed schemas (`graphql_public`, `public`) and extra paths (`public`, `extensions`).
  Those observations neither grant runtime isolation nor require database access.
- Native recovery-code enrollment returned HTTP 422
  `mfa_recovery_codes_enroll_not_enabled`; rejected for initial launch.

PRs #34-36 proposed custom Auth database infrastructure and remain open/unmerged,
superseded. No Auth DB URL, reader login, roles/grants, SECURITY DEFINER function,
catalog fingerprint or live-session adapter is required. Do not execute their SQL.
No broad administrative/service-role key is required by the runtime policy.

## Required configuration (names only)

| Component | Contract before activation |
|---|---|
| Backend | Explicit server factory configuration: `SUPABASE_URL` (canonical project origin), `SUPABASE_AUDIENCE=authenticated`, `SUPABASE_PUBLISHABLE_KEY` (public key). Constructors do not load environment variables. Trusted issuer/JWKS derived from the origin; ES256 only, bounded cache/timeouts. Existing `DATABASE_URL` remains Neon TLS; no Auth DB credential. |
| React SPA | Future `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; existing API base URL. Never expose SMTP, Neon, privileged keys, passwords, refresh tokens or TOTP secrets in source/logs. Browser SDK tokens remain exposed to XSS; review CSP/rendering/dependencies. |
| Auth | Confirm Email on; supported email/password signup, confirmation and password recovery. Public signup is approved as the target, not enabled by this PR. Secure email change and notification behavior need acceptance. No custom mailbox-history ledger or administrative-confirmation prohibition. |
| Redirects | Exact approved development/preview/HTTPS production callbacks and Site URL; no user-controlled redirects or broad wildcard allowlists. Earlier reported `http://localhost:3000` is not a production setting. Review confirmation/recovery redirects and token handling before launch. |
| Sessions | Accept [standard JWT/refresh/logout semantics](https://supabase.com/docs/guides/auth/sessions), including bounded validity of issued tokens after logout. Record actual JWT expiry and test refresh/signout. No immediate revocation, session-row read, paid inactivity timeout or custom five-minute MFA policy. |
| MFA | Optional standard TOTP; fresh provider verified-factor evidence requires signed AAL2 for enrolled accounts. Use supported enrollment/challenge/removal and encourage an independent backup factor. No email-only bypass or native MFA recovery-code dependency. Test all-factor-loss disclosure and password-reset behavior. |
| Email sender | Gmail SMTP remains conditional and $0. Validate sender policy/limits, spam placement, delivery to controlled recipients, resend/CAPTCHA/abuse controls and outage behavior. No paid fallback or assumed DNS ownership. |

## Future action and acceptance matrix

| Action | Required boundary |
|---|---|
| Browse movies | Anonymous; no Supabase anonymous account needed. Preserve public rate/workload limits. |
| Rate, personalize, personal data | Signature/issuer/audience/time + native email confirmation + enrolled-factor AAL policy + unique local mapping + ownership/privacy checks. Server resolves caller; client IDs never prove ownership. |
| Groups/invitations | Same caller policy plus existing membership, invitation, expiry and resource authorization. Never infer permissions from email or username. |
| Confirm, recover password, change email | Supported provider flows, exact redirects and secret-safe errors. Recovery must not bypass application MFA enforcement for enrolled users. |
| Manage TOTP | Provider-supported AAL/factor management; verify backup/replacement before removing a usable factor, disclose lockout. No custom recent-challenge protocol. |
| New local identity | Future atomic clean provisioning; uniqueness/concurrency tests. No legacy migration, email-based claiming or automatic linking to old data. |

Launch tests must cover JWT expiry/tampering/rotation, native unverified email,
provider errors/rate limits, AAL1-vs-enrolled-MFA, logout/refresh limits, email change,
recovery, ownership/IDOR/group privacy and concurrent clean provisioning. Offline
fixtures do not establish hosted guarantees; future hosted tests need authorization.
MFA compatibility is specifically blocked until that review: `/user` may omit
`factors` for non-MFA users, and SDK list/AAL helpers normalize the same field.
The dormant policy requires an explicit list; missing/null evidence never means
unenrolled. Approve a controlled development-only response-shape matrix for no
factors, unverified/verified TOTP and AAL1/AAL2 before activation. If the provider
omits the list, resolve the supported completeness contract first; do not bypass.
Reported ban/deletion or provider rejection denies; no instantaneous revocation
promise follows from `/user`, token expiry or a session UUID. Never use JWT-only,
cached user state or legacy authentication as a policy-failure fallback.

Complete the full NIST SP 800-63B-4 assessment and original 16-stage professional
audit, maintained separately by the owner/ChatGPT. Assess password controls,
throttling/enumeration, session exposure/lifetime, TOTP/phishing/backup risks,
recovery, privacy and logging against evidence and explicit gaps. Free-plan limits
and optional MFA may leave requirements unmet; no formal compliance claim.
Preserve manual production release/rollback controls and the 500-line complete-PR
budget. No deployment, migration, settings changes or spending is authorized here.

## Readiness discrepancy review

Unchanged main `3d592e3` passed 1,031 tests (89 skipped) in a disposable Windows
checkout; its isolated readiness module passed all seven tests. A diagnostic-only
wrapper measured successful worker completion in 1.032 seconds against a 2.489-second
communication budget. Readiness code/tests and their production timeout are unchanged.
The previous full-suite failure exposed only a false readiness result, not worker
diagnostics; its exact historical cause is unproven. The three-second total budget
includes subprocess startup, so environment load can cause a fail-closed result.
Do not classify an uninstrumented failure as an authentication regression or weaken
the production deadline to hide it; compare baseline/full-suite timing evidence.
