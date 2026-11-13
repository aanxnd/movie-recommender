# Authentication architecture contract

Status: **Prompts 1-23 merged; Stage 23 isolated integration under review. Prompt 24 on hold.**
Native authentication remains dormant in production. The explicitly selected
[local staging composition](STAGING_CHECKPOINT_REPORT.md) exercises these components
without production cutover. See [native callback integration](SIGNUP_CONFIRMATION.md)
and [account settings](ACCOUNT_SETTINGS.md), plus [native TOTP limits](TOTP_MFA.md).
Initial enrollment remains blocked on complete native factor evidence; existing
factor challenges/additional setup are dormant and await hosted acceptance.
All removal is unavailable pending authoritative concurrency protection; see
[recovery and lockout](MFA_RECOVERY.md). Password/email recovery never substitutes for TOTP.
The owner/ChatGPT maintains the
implementation roadmap and original 16-stage audit separately. No production
activation or hosted configuration change is authorized.

## Decisions and boundaries

| Area | Contract |
|---|---|
| Budget | Strictly $0 additional spending: no paid plans, purchases, upgrades, trial credits or automatic paid overages. No owned domain or domain purchase. |
| Login | Supabase Auth Free email/password; verify email ownership before protected access. Usernames are unique case-insensitively for profile identity, never login identifiers. |
| Sessions | React SPA uses the Supabase SDK. Persistent browser tokens are JavaScript-accessible: XSS or a compromised dependency can steal them. CSP, safe rendering and dependency review reduce risk, not eliminate it. No claim of HttpOnly protection. |
| MFA | Optional standard TOTP, compatible with Google Authenticator, Duo Mobile and other standard authenticator apps. No paid MFA features or additional spending. |
| Email | Gmail's own authenticated SMTP is a conditional domain-free candidate, not validated production infrastructure. Keep email verification enabled. |
| Recovery | Users can enroll a second, independently accessible TOTP factor for backup recovery. Explain and encourage setup during enrollment; disclose possible lockout if every factor is lost. No email-only MFA bypass. |
| Data | Neon remains the application database. Preserve numeric user IDs, ratings and related group/invitation behavior; Supabase owns authentication, not application data. Local SQLite remains for development. |
| Assurance | Assess NIST SP 800-63B-4 through applicable controls, evidence and explicit gaps. Supabase's `aal2` claim alone is not proof of NIST AAL2 compliance. |
| Access policy | Public signup and anonymous movie browsing are the target. Ratings, personalized recommendations and personal features require native confirmed email, a valid Supabase token and backend authorization. Verified MFA enrollment requires signed AAL2. Standard bounded JWT validity after logout is accepted; no custom mailbox ledger, live Auth DB reader or recent-MFA challenge requirement. See [policy](AUTH_POLICY_EVIDENCE.md). |

FastAPI will verify Supabase JWT signatures, approved algorithms, issuer,
audience, expiry and subject using maintained libraries and bounded signing-key
refresh. Server-side authorization must enforce verified email and the required
MFA assurance, not trust browser state or numeric IDs. Neon will map a unique
Supabase subject to its assigned numeric user ID and enforce normalized username
uniqueness transactionally under the identity schema contract below.

No legacy-account migration or account claiming is planned. Preserve existing
records and relationships without linking them by email, username or bearer code.
Prompt 22 inventories and protects still-active legacy paths; no runtime removal
was proven safe. See [retirement inventory](LEGACY_AUTH_RETIREMENT.md) and the
[NOT AUTHORIZED cutover checklist](AUTH_CUTOVER_READINESS.md). Dormant Prompt 23 provides
clean new accounts; current existing-user access must remain until a separately
approved cutover/data-access decision. Rehearse schema-compatible rollback; never
restore a legacy authentication fallback after Supabase cutover.

## Identity foundation: schema version 3

Schema 3 already adds `user_identities` alongside numeric `users.id`. Its
constraints remain unchanged; do not backfill legacy identities or relationships:

| Column/constraint | Contract |
|---|---|
| `user_id` | Primary key and foreign key to `users.id`; at most one identity row per existing numeric user. |
| `supabase_subject` | Nullable unique UUID (`sub`); native PostgreSQL UUID, canonical 32-character lowercase hex storage on SQLite. No fabricated legacy subjects. |
| `username` | Nullable, case-preserving ASCII `[A-Za-z0-9_]`, 3–30 characters; database checks reject other values rather than trimming or renaming. |
| `uq_identity_username_ci` | Unique index on `lower(username)`; PostgreSQL `C` collation makes ASCII folding independent of server locale. `Alice` and `aLiCe` conflict, including concurrent writes. |

Legacy users need no identity row; multiple null subjects/usernames are permitted.
There are no existing database usernames to normalize or collide. Any externally
supplied names need a later ownership/collision review; never silently import or
rename them. Numeric IDs, sequences, ratings, recommendation inputs, credentials
and group invitations remain untouched. Referential integrity rejects orphan links.

Prompt 23 adds an [atomic provisioning service/API](PROVISIONING_STAGING.md),
mounted only in the explicit local staging composition, never production.
New-account provisioning creates a fresh local user and unique subject/username
mapping; never transfer existing users or their data. An identity row alone grants no access. Legacy
authentication remains unchanged. Migrations from versions 1/2 are additive,
transactional and serialized; an unexpected pre-existing identity table stops
migration for inspection. See [release and rollback restrictions](DEPLOYMENT.md).

## Configuration contract (names only; not implemented or configured)

| Location | Intended configuration and boundary |
|---|---|
| React/Vercel | Public `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; retain `VITE_API_BASE_URL`. The public key is not an administrative credential. No SMTP, database or service-role secrets in `VITE_*`. |
| FastAPI/Azure | Server-configured `SUPABASE_URL`, `SUPABASE_AUDIENCE=authenticated` and public `SUPABASE_PUBLISHABLE_KEY`; derive the approved issuer/JWKS location, validate audience `authenticated`, and reject mismatched projects. Keep existing TLS `DATABASE_URL` pointing to Neon. No new environment values in this PR. |
| Supabase dashboard | Owner reports Free project `movelle-auth-dev` with TOTP enabled, a 10-factor limit and Gmail SMTP configured. Exact site/redirect allowlists, secure email change, notifications and abuse settings still need validation. No project settings or public signup activation change in this PR. |
| Gmail SMTP | Candidate `smtp.gmail.com:587` with STARTTLS, actual authenticated Gmail From address, full Gmail username and dedicated app password; enter secrets privately in Supabase, never source control or browser configuration. |
| Administrative access | No service-role key in the browser. Any future backend admin capability needs explicit scope review; ordinary JWT verification does not require it. |

Future JWT validation must pin issuer `SUPABASE_URL + /auth/v1` and its
`/.well-known/jwks.json` endpoint for the approved project, audience `authenticated`,
approved signing algorithms, UUID `sub`, expiry and any `nbf`. Bound key caching
and rotation refresh; reject unknown keys and token-supplied key URLs. Confirm the
project uses supported asymmetric signing keys before relying on JWKS; do not
infer verified-email status from an email string or a browser claim. Define a
supported server-side verification check and session/revocation policy before access.
Supabase owns passwords, email verification, sessions and factors; Neon stores
application identity mappings/data, never copies passwords, refresh tokens or TOTP secrets.

For later owner-approved redirect configuration, use exact callback URLs for
localhost development, each approved preview, and HTTPS production; avoid wildcard
allowlists and user-controlled redirects. Set Site URL to the approved application
origin before launch. The owner-reported `http://localhost:3000` default is not a
production configuration. No callback route, environment value or hosted setting
is created here. References: [JWT validation](https://supabase.com/docs/guides/auth/jwts),
[redirect allowlists](https://supabase.com/docs/guides/auth/redirect-urls).

## Prompt 3A: dormant JWT verifier

`app/supabase_jwt.py` is not imported by application startup, routes or legacy
security. Construct one shared `SupabaseTokenVerifier(SUPABASE_URL)` explicitly in
a later integration; use the project origin, not `/rest/v1/`. No hosted settings
or environment values are activated here. Owner reports current ECC/P-256 signing;
credential-free JWKS inspection on 2026-11-09 UTC confirmed `EC`, `P-256`, `ES256`,
`sig`, `verify` at [the project-pinned endpoint](https://jsbulnrcxtvslvvxjizq.supabase.co/auth/v1/.well-known/jwks.json).

Only ES256/P-256 public signing keys are accepted. Exact issuer and a single
expected audience (default `authenticated`) are checked, with required `iss`,
`aud`, integer `exp`/`iat`, canonical RFC UUID `sub` and `role=authenticated`.
Optional integer `nbf` is enforced; no clock leeway is granted. Token size is 8 KiB;
JWKS is limited to 64 KiB/16 keys, with TLS validation, no redirects, and three-second
socket-operation timeouts (not a whole-request deadline). Cache lifetime is five
minutes; refresh attempts are serialized and limited to once per 30 seconds,
including unknown `kid` and failures. New keys may wait for that cooldown. Expired
cache fails closed; refresh replaces the full set. Provider-side JWKS caching adds
revocation latency: [Supabase verification guidance](https://supabase.com/docs/guides/auth/jwts).

`verify()` returns only a UUID, never verified-email status or Movelle authorization.
Fixed exceptions contain no tokens/claims; later synchronous FastAPI dependencies
must map invalid tokens to 401 and key unavailability to 503 without diagnostics.
The dormant dependency now adds the standard provider policy and identity
resolution; production-route integration remains future work. Legacy bearer handling,
owner checks, group invitations and schema version 3 are unchanged by Prompt 3A.

## Prompt 3D.3: dormant typed verified token evidence

`SupabaseTokenVerifier.verify_claims(token)` uses the same pinned ES256/JWKS and
issuer/audience/signature/time/role/subject checks as `verify(token) -> UUID`.
It adds frozen, slotted `VerifiedTokenClaims` with hidden repr fields:

| Field | Validation / meaning |
|---|---|
| `subject`, `session_id` | Canonical lowercase, hyphenated RFC UUIDs; zero UUIDs rejected. The session ID is signed evidence, not proof that its row exists or belongs to a currently active session. |
| `expires_at`, `issued_at` | Exact nonnegative signed-64-bit integer Unix seconds from `exp`/`iat`; no bool/string/fraction coercion. Expiry must follow issuance; expired/future-issued tokens and future optional `nbf` fail without clock leeway. Present `nbf` also obeys integer bounds. |
| `aal` | Exactly `aal1` or `aal2`; required. AAL2 is historical assurance, not recent MFA or authorization. |
| `amr` | Optional: absent becomes `None`, empty array becomes `()`. Present entries must contain exactly `method` and `timestamp`, becoming frozen `AuthenticationMethodReference` objects in a tuple. |

Reviewed [Supabase JWT claim formats](https://supabase.com/docs/guides/auth/jwt-fields)
document optional AMR method/timestamp pairs, session UUIDs and the two AAL values.
Movelle deliberately accepts only that page's twelve reviewed method names;
unknown names/extensions, duplicate methods, malformed arrays/entries or duplicate
JSON payload keys (including nested keys) fail closed. AMR timestamps must be
nonnegative integer Unix seconds below `2**63` and no later than `iat`. These are
strict parser limits, not new provider guarantees. Additional fields/methods need
review; a `recovery` method name does not approve native MFA recovery codes.

No public method accepts claim dictionaries, decoded browser data or assurance
booleans. Signature verification precedes typed parsing, with one verification per
call; the existing key-cache/rotation/timeouts apply. UUID-only `verify()` preserves
its existing claim requirements and does not acquire session/AAL/AMR requirements.
UUID-only consumers remain compatible; the new access policy uses `verify_claims`.
Fixed errors/log-free operation and hidden result/nested reprs protect diagnostics;
never log JWTs, evidence fields or exception locals. Python types/immutability do
not prove provenance: trusted callers must obtain results from `verify_claims`.

This result alone does not establish native email confirmation, live/revoked session
state, current MFA enrollment, recent step-up, local account ownership/suspension,
group permissions or an access decision. A signed arbitrary session UUID and old
AMR can pass offline verification. No live user/session/factor or database lookup
occurs, no routes consume this result, and no generic access/active/recent flag is
provided. [Policy and launch gates](AUTH_CONFIG_AUDIT.md) remain mandatory.
`test_supabase_claims.py` covers local signatures, strict parsing, tampering,
immutability, stale evidence, key rotation/outages and sanitized diagnostics.

## Standard policy replacement (Prompt 11)

`app/supabase_policy.py` replaces the superseded custom evidence composition.
See [native confirmation, optional MFA and standard-session rules](AUTH_POLICY_EVIDENCE.md).
`MailboxSource`, `LiveStateSource` and their mock-only contracts/tests are removed.
The supported native OTP helper remains dormant; no Auth database adapter is needed.

## Prompt 3B: dormant identity resolution

`app/supabase_identity.py` exposes `resolve_verified_subject(session, subject)`.
Only trusted server code may supply the UUID returned by the configured project's
`SupabaseTokenVerifier.verify()`. UUID objects carry no proof of provenance: never
construct the input from request JSON, a path, email, username or numeric user ID.
The resolver rejects strings and other types rather than parsing/coercing them.
It does not repeat signature verification or make hosted authentication requests.

A single joined SELECT matches `UserIdentity.supabase_subject` and confirms its
`User` exists, returning a frozen `AuthenticatedIdentity(subject, user_id)` with
no identifiers in its repr. No client-selected target ID is accepted. Unknown,
unlinked, orphaned, ambiguous or invalid local identities fail closed. Existing
schema-3 uniqueness/FK guarantees remain unchanged; there are no schema changes.

The caller supplies a short-lived session/transaction. Resolution suppresses
autoflush, uses database columns instead of stale ORM objects, and never creates,
links, flushes, commits, rolls back or closes anything. It sees the statement's
database snapshot, not future revocation/deletion; do not cache results across
requests. Later resource checks/writes need coordinated transaction semantics.

Future dependencies must map every `UnresolvedIdentity` to the same generic 401
response, without exposing link/account existence. `IdentityResolutionUnavailable`
maps to a generic 503; the caller's transaction manager must roll back failures.
Neither exception contains database diagnostics or subjects; do not log tokens,
identifiers or internal exception contexts. This is not a constant-time guarantee.

| Later integration gate | What the dormant foundations establish / remaining requirement |
|---|---|
| Verified token | PR 3A verifies signatures and token claims; callers must use its configured project. |
| Linked local identity | PR 3B reads established links; dormant Prompt 23 creates new accounts atomically, never claims legacy profiles. Hosted integration remains blocked. |
| Verified email and MFA | Neither UUID nor resolved identity proves email verification, current account/session state or required MFA assurance. Obtain supported server evidence and apply policy separately. |
| Resource authorization | A resolved ID grants no endpoint access. Check ownership and group/invitation permissions independently; request IDs never select the caller's identity. |

No route/startup imports or dependencies activate these components. Legacy bearer,
owner, group, invitation and operator flows remain unchanged. A later cutover must
choose its authentication policy explicitly; never retry legacy authentication as
a fallback after Supabase verification/resolution fails. No claiming or linking
API, backfill, hosted mapping, email/MFA flow or deployment is authorized here.

## Open launch gates

The [standard policy](AUTH_POLICY_EVIDENCE.md) replaces mandatory independent
mailbox provenance, live-session DB access and custom MFA recency checks.
Native confirmation/recovery, supported TOTP and bounded token expiry are the
approved design. Full integration and security/operational acceptance remain open.
See [configuration gates](AUTH_CONFIG_AUDIT.md) and [native OTP](EMAIL_PROVENANCE.md).

### Prompt 3C: dormant FastAPI dependency (activation BLOCKED)

`app/supabase_auth.py` exports `make_supabase_auth_dependency(project_url=...,
audience=..., publishable_key=..., session_factory=...)`; all arguments are trusted server configuration.
Construct it once per process, never per request. Construction/import makes no
network/database calls and reads no environment variables. It creates the existing
standard policy with the explicit project/audience/public key; no alternate JWKS URL.
Nothing imports or attaches this factory in production route/startup registration.

The returned synchronous function is for FastAPI `Depends`, which runs blocking
dependencies in a worker: [FastAPI concurrency contract](https://fastapi.tiangolo.com/async/#dependencies).
Do not call it directly from an async handler. It requires exactly one raw
Authorization field, case-insensitive Bearer scheme, one ASCII space and one
unpadded three-segment JWT (maximum 8 KiB). Duplicates, coalesced/multiple credentials,
whitespace ambiguity and legacy 43-character credentials fail before verification.
It never reads identity from query/path/body/cookies or retries legacy auth.

JWT and native email/MFA policy checks run before any database session. Only
the verified subject UUID reaches
the existing resolver. `session_factory` must create a fresh owned Session; its
read transaction commits on success, rolls back on failure and closes in the same
worker before returning frozen `SupabaseAuthContext(user_id, subject, email, aal)`
(extended in Prompt 14). No ORM objects, tokens or sessions escape. Its repr hides
all fields; never serialize/log the principal or include exception locals.
This independent auth snapshot is not a transaction covering later resource writes.

### Prompt 14: central principal and verification order (dormant)

Prompt 15 adds [dormant owner-scoped resource operations](RESOURCE_AUTHORIZATION.md)
which consume this principal in test-only routes. Authentication is still not
attached to production routes; resource grants are separate from the principal.

Use this existing factory as the single future FastAPI authentication dependency,
through `Depends(authenticate)`. Do not call the standalone email reader alongside
it or verify the token again. The exact order for an admitted request is:

1. Reject missing, duplicate, oversized or malformed raw Bearer headers.
2. `SupabaseAccessPolicy.check_with_email(token)` runs the existing ES256 typed
   verifier once (pinned issuer/audience/JWKS, UUIDs, time and AAL/AMR validation).
3. Make exactly one fresh pinned `/auth/v1/user` GET with the public key and bearer
   token; reject duplicate JSON keys. Invalid JWTs never reach this endpoint.
4. Require exact subject, authenticated role/audience and explicit
   `is_anonymous: false`. Reject reported deletion, current bans and malformed
   account evidence. Apply Prompt 13's shared current-email validation; pending
   addresses and stale JWT emails cannot replace the confirmed current address.
5. Require an explicit factor list; verified TOTP needs signed AAL2. Unknown
   enrollment never permits AAL1 or AAL2. No provider response is cached.
6. Resolve only that verified subject through the existing joined Neon lookup,
   confirming the local user exists. Never create/link/claim accounts or accept a
   target identity from client fields. Close the owned read transaction/session.
7. Check expiry again after database work; only then return the principal.

`check_with_email` returns the existing `VerifiedTokenClaims` and
`ProviderEmailConfirmation` as a typed pair. `check(token) -> VerifiedTokenClaims`
remains compatible by delegating to it. Both paths use the same implementation,
one JWT verification and one provider read, not parallel policies. JWKS refreshes
are separate bounded/cached key reads. The principal contains only the resolved
numeric ID, verified UUID subject, provider-confirmed current email and signed
`aal1`/`aal2`. These are authentication evidence, not resource permissions or proof
of recent MFA/session-row existence. The principal's Python type does not prove
provenance; downstream code must obtain it from this dependency.

Supabase documents [getUser](https://supabase.com/docs/reference/javascript/auth-getuser)
as a server read. Its upstream [user model](https://github.com/supabase/auth/blob/master/internal/models/user.go)
defines `is_anonymous` as a required boolean and optional `banned_until`/`deleted_at`;
there is no generic public `disabled` assertion to invent. Provider rejections and
reported ineligibility deny, but this is not a guarantee of instantaneous deletion,
ban or logout revocation. Upstream source does not establish hosted version or
settings. Standard bounded token validity and Prompt 13 native email semantics
(including retained confirmation timestamps) still apply.

Invalid headers/tokens, policy denials and unresolved identities receive the
same generic 401 and Bearer challenge. Key/provider/database failures receive
generic 503 with a fixed
Retry-After; no fallback or stale-key weakening. Errors carry `Cache-Control: no-store`;
the injected success response is marked likewise. Later handlers/middleware must
preserve that policy, including when returning custom Response objects. Known exception diagnostics are suppressed;
the component logs nothing. Platform/APM logging must not capture headers, tokens,
query credentials or exception locals. Existing middleware/rate limits are unchanged.

**Do not activate this dependency on protected routes yet.** It checks the native
confirmation/MFA policy and existing identity mapping, not resource ownership,
group authorization or immediate session revocation. Later route integration must
preserve privacy, transaction boundaries and generic failures. No hosted setting
or data mutation is authorized by this contract update.

Gmail deliverability, backup-TOTP/provider recovery acceptance, full NIST assessment,
the original 16-stage audit, integration and release/rollback tests remain open.
Use approved disposable users only for later authorized hosted tests. Record dates,
provider versions, settings and sanitized results; offline passes are not hosted evidence.

### Gmail SMTP: OPEN

Development signup, email verification, password login and Gmail SMTP connectivity
passed in the disposable-account validation reported below. An Outlook invitation
landed in junk. Production suitability, spam placement, sender limits and
deliverability remain unresolved; development delivery does not close this gate.

- Confirm ongoing no-cost account eligibility, app-password availability with
  2-Step Verification, and acceptable provider-policy use. Google password changes
  revoke app passwords; document credential rotation and sender failure recovery.
- Prove hosted Supabase SMTP connectivity and delivery to controlled Gmail,
  Outlook and Yahoo addresses for signup, reset, secure email change and each
  enabled security notification. Inspect latency, spam placement and SPF/DKIM/DMARC.
- Validate CAPTCHA, resend throttling, quota/failure handling and monitoring.
  Research limits: Gmail up to 500 messages/rolling 24 hours shared across clients;
  Supabase custom SMTP initially 30/hour. These are ceilings, not delivery guarantees.
  Multiple email-change messages and notifications consume the allowance too.
- Preserve verification during outages. No trials, temporary sender rewrites,
  paid fallback or assumed DNS control over a free hosting subdomain.

### Backup TOTP: approved design; implementation acceptance remains OPEN

1. After verifying the primary TOTP factor and obtaining `aal2`, offer and clearly
   encourage a separate `mfa.enroll({ factorType: 'totp' })` enrollment for backup.
   Verify it with `mfa.challengeAndVerify({ factorId, code })` before treating it
   as usable. Each enrollment has its own factor ID and secret.
2. Explain independent access: use a separate device or an independently accessible
   authenticator store whose access does not depend on the primary device/factor.
   Two apps on one lost phone do not provide independent recovery. Scanning the
   same QR twice does not enroll a separate backup factor. Do not store QR images,
   TOTP secrets or codes in logs, reports or application profile records.
3. After losing the primary authenticator, sign in with email/password at `aal1`,
   select the verified backup factor, and challenge/verify its TOTP to regain
   Supabase-issued `aal2`. Password/email recovery alone must not bypass MFA.
4. After the alternative-factor challenge establishes `aal2`, enroll and separately
   verify the replacement. Review lost-factor removal, but **do not execute it**:
   native unenrollment has no established atomic final-factor guard across devices.
   Prompt 21 disables all Movelle removal, including pending cleanup. No hidden bypass.
5. Disclose possible account lockout if every enrolled factor is lost, including
   when the user declines backup setup. No email-only or administrative automatic
   recovery fallback is approved. Support cannot promise restoration from an ID.

Later implementation must test independent primary/backup enrollment, fresh login
and backup-only recovery, replacement/removal, wrong-factor/account rejection,
throttling, session expiry/revocation, password-reset MFA enforcement and secret
redaction. Validate Google Authenticator and Duo Mobile interoperability. These
flows now have dormant Prompt 20/21 implementations and offline tests, with removal
disabled. Hosted acceptance remains open; offline passes do not prove provider behavior.

## Decision and validation history

Prompt 1C evidence, 2026-11-08: an isolated harness outside the repository used
`supabase-js` / `auth-js` 2.119.0 and public/user APIs on `movelle-auth-dev`.
Sanitized outcomes below were reported by the owner; this PR runs no hosted tests.

| Check | Recorded result |
|---|---|
| New disposable signup, email verification, password login | PASS |
| Native `mfa.recoveryCodes.generate()` probe | HTTP 422, `mfa_recovery_codes_enroll_not_enabled` |
| TOTP enrollment and recovery-code redemption/replacement | Not run; stopped at provider restriction; no MFA factors created |
| Test session cleanup | PASS |
| Hosted Free recovery-code enablement research | No supported enablement path established; no upgrade or workaround attempted |

**Native recovery codes: REJECTED FOR INITIAL LAUNCH**, superseded by the owner's
explicit backup TOTP decision. The earlier experimental recovery-code requirement
is closed as a rejected design, not an unresolved launch requirement. Do not enable
or depend on unsupported native codes. Custom application-managed recovery codes
are also outside the approved launch design; they do not supply Supabase `aal2`.

Repository inspection found no Supabase recovery-code implementation to remove.
The existing UI's legacy "private recovery code" is an `ID:credential` bearer
credential, not a single-use MFA code. Preserve its security behavior and tests
until an explicitly approved cutover retires legacy credential paths. Prompt 22
preserves those active paths and records the dependencies. No legacy-account migration or
account claiming is approved; this PR does not alter existing credential behavior.

Historical references: [generation API](https://supabase.com/docs/reference/javascript/auth-mfa-recovery-codes-generate),
[versioned experimental/server-flag contract](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/lib/types.ts).

## Evidence and NIST work

Maintain an applicability matrix as implementation progresses: control/reference,
current and proposed behavior, responsible party, test/evidence, gap, effort/cost.
Keep password length/Unicode/screening, throttling/enumeration, email verification,
JWT/session revocation, reauthentication, TOTP/recovery and secret-safe logging in
scope. Backup-factor independence and loss of all factors are explicit usability
and lockout risks. TOTP is not phishing-resistant. Browser token exposure remains;
Free does not include built-in leaked-password protection or session timeouts.
Record compensating controls and unresolved gaps; never claim full compliance.
Retain the full NIST SP 800-63B-4 assessment and complete original 16-stage
professional audit, maintained separately by the owner/ChatGPT. This small matrix
is implementation evidence, not a replacement for either assessment. Optional
TOTP and default provider sessions can leave NIST requirements unmet; disclose
those gaps rather than changing the standard or inventing compliance claims.

| Control/reference | Current evidence | Responsibility and remaining gap ($0 constraint) |
|---|---|---|
| Identity binding / application authorization | Schema 3 constraints plus `test_user_identities.py` and `test_supabase_identity.py` cover uniqueness and dormant existing-link resolution. | Movelle: implement atomic clean new-account provisioning and route authorization; resolution alone grants no access. |
| Email-confirmation evidence | `test_supabase_email.py` covers fresh provider markers and fail-closed rejection; see [policy review](AUTH_POLICY_EVIDENCE.md). | Validate native confirmation/recovery, redirects and secure email change before launch; no independent provenance ledger is required. No protected route activation. |
| Passwords (§3.1.1), throttling | Prompt 18 offline native-SDK/signed-AMR tests cover recovery, fresh password reauthentication, cancellation and generic failures; [hosted acceptance](PASSWORD_SECURITY.md) remains open. | Supabase + Movelle: validate configured length, Unicode, screening, enumeration and abuse controls; Free lacks built-in leaked-password protection. No compliance claim. |
| OTP (§3.1.4/3.1.5), authenticator management (§4) | Backup TOTP design approved; hosted recovery-code probe rejected. | Supabase + Movelle: test independent factors, replacement, reset enforcement and lockout disclosure; TOTP is not phishing-resistant. |
| Session management (§5) | Dormant JWT and `test_supabase_auth.py` adversarial/lifecycle tests; SPA exposure documented; existing routes remain legacy-only. | Movelle: test standard JWT/refresh/logout behavior and resource authorization before activation; document bounded post-logout validity and Free timeout gaps. |

Official references, reviewed 2026-11-08 (not live validation):

- [Supabase Free features](https://supabase.com/pricing), [SMTP restrictions](https://supabase.com/docs/guides/auth/auth-smtp), [email notifications](https://supabase.com/docs/guides/auth/auth-email-templates).
- [Google SMTP and limits](https://developers.google.com/workspace/gmail/imap/imap-smtp), [app passwords](https://support.google.com/accounts/answer/185833), [Gmail policies](https://support.google.com/mail/answer/16734397).
- [Multiple MFA factors](https://supabase.com/docs/reference/javascript/auth-mfa), [TOTP guide](https://supabase.com/docs/guides/auth/auth-mfa/totp), [enrollment](https://supabase.com/docs/reference/javascript/auth-mfa-enroll), [challenge/verify](https://supabase.com/docs/reference/javascript/auth-mfa-challengeandverify), [user factor removal](https://supabase.com/docs/reference/javascript/auth-mfa-unenroll).
- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html).

## PR review and release boundary

`PR size / Complete PR line budget` checks the entire merge-base-to-head diff,
not individual commits: additions plus deletions, maximum 500, with no exclusions
for tests, documentation, configuration, migrations or lockfiles. Renames count as
deletion plus addition; binary/unmeasurable diffs fail closed. Split work rather
than omitting checks. Owner flexibility on PR 2A size does not change this checker.

After fetching the target branch, check committed changes locally with
`python scripts/check_pr_size.py --base origin/main --head HEAD`; this deliberately
does not count unstaged/untracked files. CI uses event base/head SHAs with full
history, read-only permissions and no service secrets. The owner reports a GitHub
ruleset with required CI checks is configured; preserve it. Repository code cannot
stop an administrator bypass. No settings are changed here.

PRs #23-33 established the historical foundations. PRs #34-36 are superseded
custom database infrastructure; leave them open and unmerged. Prompt 11 replaces
their purpose with supported provider behavior and dormant offline-tested policy.
Prompt 12 adds a dormant native signup callback; no hosted configuration, public-signup activation,
production migration or deployment is authorized. Prompts 22-23 concern legacy
credential-path removal and clean new-account provisioning, not legacy migration.
Keep [deployment/rollback controls](DEPLOYMENT.md) for later authorized rollout.
