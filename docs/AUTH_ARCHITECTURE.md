# Authentication architecture contract

Prompt 11 owner revision: [standard Supabase policy](AUTH_POLICY_EVIDENCE.md)
supersedes the historical strict requirements below while this documentation is
being simplified. No custom mailbox/session DB evidence or recent-MFA ledger is
required; no legacy-account migration is planned. Authentication stays dormant.

Status: **Dormant FastAPI token/link authentication foundation; existing routes remain legacy-only.**
Owner decisions and Prompt 1 / Prompt 1B / Prompt 1C evidence: 2026-11-08.
The owner-approved backup TOTP decision supersedes the earlier recovery-code
requirement. Runtime authentication and public signup activation need separate authorization.

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
| Access policy (Prompt 3D.2) | Genuine verified email and live provider account/session checks on every protected request; fail closed when evidence is unavailable. Ordinary browsing/ratings/recommendations require AAL1+; sensitive account/MFA operations require recent server-enforced AAL2. See the [audit and action matrix](AUTH_CONFIG_AUDIT.md) for unresolved evidence and enforcement gates. |

FastAPI will verify Supabase JWT signatures, approved algorithms, issuer,
audience, expiry and subject using maintained libraries and bounded signing-key
refresh. Server-side authorization must enforce verified email and the required
MFA assurance, not trust browser state or numeric IDs. Neon will map a unique
Supabase subject to the existing numeric user ID and enforce normalized username
uniqueness transactionally under the identity schema contract below.

Legacy linking must require both valid legacy ownership proof and the intended
verified Supabase identity, with one-time atomic linking and uniqueness checks.
Linked profiles must reject legacy authentication and operator credential reissue.
Expand existing bearer-header limits for JWTs in a later PR. Rehearse migrations
and schema-compatible rollback: an additive schema is not automatically compatible
with binaries that require an exact schema version. Never restore legacy bypasses.

## Identity foundation: schema version 3

The inspected schema has numeric `users.id` only, with no stored usernames.
Add `user_identities`; do not alter or backfill `users` or its relationships:

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

This PR adds no linking writers, endpoints or authorization consumers. Do not
populate hosted mappings until the separately reviewed verified linking and legacy
credential cutover are ready. An identity row alone grants no access. Legacy
authentication remains unchanged. Migrations from versions 1/2 are additive,
transactional and serialized; an unexpected pre-existing identity table stops
migration for inspection. See [release and rollback restrictions](DEPLOYMENT.md).

## Configuration contract (names only; not implemented or configured)

| Location | Intended configuration and boundary |
|---|---|
| React/Vercel | Public `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; retain `VITE_API_BASE_URL`. The public key is not an administrative credential. No SMTP, database or service-role secrets in `VITE_*`. |
| FastAPI/Azure | Server-only `SUPABASE_URL`; derive the approved issuer/JWKS location, validate audience `authenticated`, and reject mismatched projects. Keep existing TLS `DATABASE_URL` pointing to Neon. No new environment values in this PR. |
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
Email verification, revocation/disabled-user checks, identity binding, MFA policy
and JWT-sized authorization headers remain later PRs. Legacy bearer handling,
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
The email component, identity resolver and FastAPI dependency keep using that API.
Fixed errors/log-free operation and hidden result/nested reprs protect diagnostics;
never log JWTs, evidence fields or exception locals. Python types/immutability do
not prove provenance: trusted callers must obtain results from `verify_claims`.

This result does not establish genuine email verification, live/revoked session
state, current MFA enrollment, recent step-up, local account ownership/suspension,
group permissions or an access decision. A signed arbitrary session UUID and old
AMR can pass offline verification. No live user/session/factor or database lookup
occurs, no routes consume this result, and no generic access/active/recent flag is
provided. [Policy and launch gates](AUTH_CONFIG_AUDIT.md) remain mandatory.
`test_supabase_claims.py` covers local signatures, strict parsing, tampering,
immutability, stale evidence, key rotation/outages and sanitized diagnostics.

## Prompt 3D.4: dormant provenance/live-state composition

`app/supabase_evidence.py` adds `AuthenticationEvidencePolicy.check(token)`.
Its only request input is a raw JWT; it calls the existing `verify_claims`, then
fresh same-project `GET /auth/v1/user` with a public publishable key and user JWT.
It reuses the existing bounded TLS/no-proxy/no-redirect transport without changing
the email component. Exact subject/audience/role, non-anonymous user, current email
and aware nonfuture confirmation are required; reported deletion or active ban
denies. None of these fields alone proves genuine mailbox history or every live
session property. See [provider user data](https://supabase.com/docs/reference/javascript/auth-getuser)
and [session-record limitations](https://supabase.com/docs/guides/auth/sessions).

Two **server-configured trusted interfaces** are mandatory; neither has a concrete
provider/ledger implementation here. Missing sources/records deny; no allow-by-default.

- `MailboxSource.read(issuer, subject, email, confirmed_at)` returns an internal
  `MailboxChallenge` attestation from a future genuine challenge workflow. Exact
  issuer/subject/current address/confirmation-marker binding, challenge completion
  and expiry are checked. Confirmation time is only an additional binding, never
  proof of a challenge. The source must enforce challenge origin, protected writes,
  revocation and invalidation on every address change, including A -> B -> A;
  current snapshots cannot prove that complete history. Marker-only, admin-confirmed
  or historically unproven accounts cannot supply this attestation automatically.
  No ledger/writer, email delivery, expiry policy or challenge mechanism is invented
  or deployed here. Future workflow and address-change tracking need review.
- `LiveStateSource.read(issuer, subject, session_id, nonce)` must perform an
  authoritative fresh account/session read, enforcing existence, ownership,
  revocation/expiry and defined ban/deletion/disable semantics. Internal
  `LiveAccountSession` must match issuer, both UUIDs, a new per-call nonce and the
  provider email/confirmation snapshot. Observation must fall inside this check;
  stale/future/naive times and replayed records fail. Adapters must stamp local
  observation time only after the authoritative read;
  a nonce/timestamp must never be used to relabel cached claims as live state.
  These are internal contracts, **not undocumented fields or guarantees of `/user`**. No privileged adapter,
  credential, database function or schema change is supplied. Default configuration
  therefore cannot produce successful authentication evidence.

Only trusted backend code may configure adapters; never deserialize these records
from client JSON or treat their Python types as proof of origin. Mock adapters in
tests establish conditional composition correctness, not hosted enforcement.
Unknown/forged/mismatched records receive a fixed denial; provider/adapter failures,
429/5xx, unexpected responses and malformed JSON receive fixed unavailable errors.
No raw errors, credentials, user JSON or evidence fields are logged; result and
record reprs hide fields. Future HTTP mapping must remain generic and no-store.

Every call reads anew; only the existing signing-key cache remains. Completion
after token expiry or a three-second elapsed budget fails closed; this budget
rejects late results but cannot cancel blocked synchronous I/O. Existing transport
socket-operation timeouts are not a hard total deadline. Provider propagation,
address-history tracking, concrete trusted sources and cross-service races remain
activation gates; no immediate-revocation guarantee is established.

The frozen result contains verified token claims and observation time only.
It grants no resource access, local ownership, group permissions, current AAL or
recent MFA. No consumer/route, legacy authentication, email reader or Neon data
changes. `test_supabase_evidence.py` exercises only offline local signatures and
mock providers/sources. Genuine email provenance and live state remain unproven
for hosted accounts until supported sources and acceptance evidence are approved.

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
| Linked local identity | PR 3B reads an already-established UUID-to-numeric-ID link; secure linking/ownership verification is still separate work. |
| Verified email and MFA | Neither UUID nor resolved identity proves email verification, current account/session state or required MFA assurance. Obtain supported server evidence and apply policy separately. |
| Resource authorization | A resolved ID grants no endpoint access. Check ownership and group/invitation permissions independently; request IDs never select the caller's identity. |

No route/startup imports or dependencies activate these components. Legacy bearer,
owner, group, invitation and operator flows remain unchanged. A later cutover must
choose its authentication policy explicitly; never retry legacy authentication as
a fallback after Supabase verification/resolution fails. No claiming or linking
API, backfill, hosted mapping, email/MFA flow or deployment is authorized here.

## Open launch gates

Prompt 3D.5 adds a [native email-OTP redemption component](EMAIL_PROVENANCE.md),
not a concrete `MailboxSource`. Native credential acceptance cannot distinguish
approved inbox delivery from administrative token generation or establish all
address-change history. The new component is dormant; genuine provenance and
authoritative live-state sources remain required before protected access.

Prompt 3D adds only [fresh provider email-confirmation evidence](AUTH_POLICY_EVIDENCE.md).
Prompt 3D.2 records [final owner requirements and the configuration audit](AUTH_CONFIG_AUDIT.md).
Current-account/session and MFA enforcement remain blocked on evidence and design
gates; provider confirmation is not mailbox proof under all settings. Uncertain
verification provenance requires a genuine challenge before activation.
The dependency and existing routes remain unchanged and activation stays BLOCKED.

### Prompt 3C: dormant FastAPI dependency (activation BLOCKED)

`app/supabase_auth.py` exports `make_supabase_auth_dependency(project_url=...,
audience=..., session_factory=...)`; all arguments are trusted server configuration.
Construct it once per process, never per request. Construction/import makes no
network/database calls and reads no environment variables. It creates the existing
ES256 verifier with the explicit project/audience; no alternate JWKS URL or keys.
Nothing imports or attaches this factory in production route/startup registration.

The returned synchronous function is for FastAPI `Depends`, which runs blocking
dependencies in a worker: [FastAPI concurrency contract](https://fastapi.tiangolo.com/async/#dependencies).
Do not call it directly from an async handler. It requires exactly one raw
Authorization field, case-insensitive Bearer scheme, one ASCII space and one
unpadded three-segment JWT (maximum 8 KiB). Duplicates, coalesced/multiple credentials,
whitespace ambiguity and legacy 43-character credentials fail before verification.
It never reads identity from query/path/body/cookies or retries legacy auth.

JWT verification runs before any database session. Only its returned UUID reaches
the existing resolver. `session_factory` must create a fresh owned Session; its
read transaction commits on success, rolls back on failure and closes in the same
worker before returning frozen `SupabaseAuthContext(user_id)`. No ORM objects or
sessions escape, and no subject/claims are included in the result or its repr.
This independent auth snapshot is not a transaction covering later resource writes.

Invalid headers/tokens/unresolved identities receive the same generic 401 and
Bearer challenge. Signing-key/database failures receive generic 503 with a fixed
Retry-After; no fallback or stale-key weakening. Errors carry `Cache-Control: no-store`;
the injected success response is marked likewise. Later handlers/middleware must
preserve that policy, including when returning custom Response objects. Known exception diagnostics are suppressed;
the component logs nothing. Platform/APM logging must not capture headers, tokens,
query credentials or exception locals. Existing middleware/rate limits are unchanged.

**Do not activate this dependency on protected routes yet.** It establishes only
token validity plus an existing link, not verified email, current account/session
status, MFA assurance or resource/security-setting permissions. Neither an email
string nor this context satisfies those gates. Supported server evidence, freshness,
revocation, assurance and transaction/resource policies require later review; no
hosted configuration or architectural shortcut is approved to close those gaps.
Gmail production deliverability, backup-TOTP acceptance and NIST gaps remain open.

**Gmail SMTP production readiness and future MFA acceptance remain OPEN launch gates.**
Recovery codes are no longer a prerequisite for Prompt 2B. This PR implements only
its identity foundation; runtime authentication requires a later reviewed PR.
Use disposable users and controlled recipient mailboxes; no production-data testing.
Record date, SDK/provider version, Free-plan settings, sanitized results and reviewer.
Failure leaves the requirement unresolved; it is not permission to weaken it.

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
4. At `aal2`, enroll and verify the replacement primary factor, then remove the
   lost factor with `mfa.unenroll({ factorId })`. Retain a usable verified backup;
   apply reauthentication/session-revocation policy to sensitive factor changes.
5. Disclose possible account lockout if every enrolled factor is lost, including
   when the user declines backup setup. No email-only or administrative automatic
   recovery fallback is approved. Support cannot promise restoration from an ID.

Later implementation must test independent primary/backup enrollment, fresh login
and backup-only recovery, replacement/removal, wrong-factor/account rejection,
throttling, session expiry/revocation, password-reset MFA enforcement and secret
redaction. Validate Google Authenticator and Duo Mobile interoperability. These
flows have not been implemented or validated by the identity foundation.

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
until the separately reviewed legacy-profile migration; no cleanup is needed here.

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

| Control/reference | Current evidence | Responsibility and remaining gap ($0 constraint) |
|---|---|---|
| Identity binding / application authorization | Schema 3 constraints plus `test_user_identities.py` and `test_supabase_identity.py` cover uniqueness and dormant existing-link resolution. | Movelle: implement verified, atomic legacy linking and route authorization; resolution alone grants no access. |
| Email-confirmation evidence | `test_supabase_email.py` covers fresh provider markers and fail-closed rejection; see [policy review](AUTH_POLICY_EVIDENCE.md). | Hosted confirmation/provenance evidence and current-state/recent-MFA enforcement remain blocked per [Prompt 3D.2](AUTH_CONFIG_AUDIT.md); no protected access is enabled. |
| Passwords (§3.1.1), throttling | Owner-reported disposable password login; existing legacy rate-limit tests do not prove Supabase policy. | Supabase + Movelle: validate length, Unicode, screening, enumeration and abuse controls; Free lacks built-in leaked-password protection. |
| OTP (§3.1.4/3.1.5), authenticator management (§4) | Backup TOTP design approved; hosted recovery-code probe rejected. | Supabase + Movelle: test independent factors, replacement, reset enforcement and lockout disclosure; TOTP is not phishing-resistant. |
| Session management (§5) | Dormant JWT and `test_supabase_auth.py` adversarial/lifecycle tests; SPA exposure documented; existing routes remain legacy-only. | Movelle: implement/evidence the approved email/live-state/recent-MFA policy and resource authorization before activation; Free timeout gaps remain. |

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

PR 2A added the contract and PR-size CI; PR 24 approved backup TOTP. Prompt 2B adds
only the dormant schema foundation and configuration contract, with no runtime auth,
external configuration, public signup activation or production migration. Native recovery codes do not block
Prompt 2B; Gmail production readiness and later security acceptance block launch.
Keep [deployment/rollback controls](DEPLOYMENT.md) for later authorized rollout.
