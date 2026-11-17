# Authentication architecture contract — current native design

Selected preparation: existing Vercel, Azure Container Apps Express/Consumption,
Neon and Supabase. Azure remains manually stopped. No out-of-pocket charges:
student-credit use needs separately approved activation after Microsoft confirms
this subscription's protection. No paid upgrade, Marketplace or new infrastructure.
PR91–123 are merged; code is not deployment or hosted-feature approval.
Default selectors remain legacy until approved coordinated cutover. Native Azure
uses `app.azure_release` → `app.native_release` and `build:native`; see the
[Azure runbook](AZURE_ACTIVATION_RUNBOOK.md) and [Vercel guide](VERCEL_NATIVE_RELEASE.md).
Prompts 1–23 are historical foundations; Prompt24/final audit/public activation
remain on hold. The owner maintains the fixed roadmap/original16-stage audit separately.

## Owner decisions and data boundaries

| Area | Current contract |
|---|---|
| Access | Public signup/anonymous movie browsing are the target; ratings, personalized recommendations and personal/group features require server authorization. |
| Login | Supabase Free email/password; unique case-insensitive usernames are profile identity, never login or proof of ownership. |
| Sessions | Standard Supabase SDK sessions in React SPA; browser tokens are JavaScript-accessible, not HttpOnly. CSP/dependency review reduce XSS risk, not eliminate it. Already-issued JWTs have bounded post-logout validity. |
| Data | Neon owns numeric users/ratings/invitations; Supabase owns passwords/confirmation/sessions/factors. No copied passwords, refresh tokens or TOTP seeds in application records. |
| Identity | Schema3 `user_identities`: FK/primary-key user_id, nullable unique UUID subject, nullable case-preserving ASCII username 3–30 `[A-Za-z0-9_]`, DB unique lower(username)/PostgreSQL C collation. Null legacy identities remain; never fabricate subjects, rename or claim records. |
| Provisioning | Atomic clean new-account provisioning resolves only verified subject and allocates a fresh numeric user. Schema4 adds durable username revisions/CAS. Existing IDs/relationships preserved; no legacy migration, email/name/ID matching, automatic linking or credential fallback. |
| MFA | Optional standard TOTP (Google Authenticator/Duo Mobile), strongly encouraged second independent enrolled/verified factor; two apps sharing one lost device are not independent recovery. Disclose all-factors-lost lockout. No email/password-only bypass, custom recovery codes or paid MFA. |
| Native removal/deletion | Concrete candidates remain unselected/disabled. Unconditional provider factor DELETE cannot guarantee retain-one across devices. Deliberate opt-out requires policy/provider review. Deletion needs isolated broad admin worker, signed intents, DDL/grants/retention and hosted acceptance. See [account gates](ACCOUNT_OPERATIONS_READINESS.md). |
| Mail | Existing Gmail authenticated SMTP is conditional; development delivery/Outlook junk is not production acceptance. Keep confirmation enabled; sender limits, recovery/email-change delivery, abuse controls and credential rotation remain gates. Password changes can revoke Gmail app passwords. |
| Assurance | Full NIST SP800-63B-4 controls/evidence/gaps assessment and original16-stage professional audit retained; SDK `aal2` alone is not formal NIST compliance. |

## Verified token boundary

`SupabaseTokenVerifier` pins exact project root issuer +`/auth/v1`, audience
`authenticated`, ES256/P-256 JWKS/signature/role and canonical UUID subject.
Required exp/iat and optional nbf use strict integer timestamps, no clock leeway;
malformed/expired/future tokens, duplicate JSON keys and untrusted key URLs deny.
Token≤8KiB, JWKS≤64KiB/16keys, cache5min, serialized refresh/cooldown30s;
three-second socket-operation timeout is not a whole-request deadline. Unknown
keys/outages fail closed, never publishable-key HMAC or stale/unverified fallback.
`verify(token)->UUID` remains compatible; `verify_claims` additionally returns
immutable hidden-repr subject/session UUIDs, exp/iat, exact aal1/aal2 and optional
AMR tuple of exact method/timestamp entries. Zero/malformed session, unknown AMR
methods, duplicate methods or timestamps after iat deny. Obtain evidence only from
cryptographic verification; Python types/caller dictionaries are not provenance.
Signed AAL/AMR/session/expiry do not prove recent MFA, live session-row existence,
mailbox challenge provenance, current revocation or application/resource ownership.
[Provider claims](https://supabase.com/docs/guides/auth/jwt-fields),
[JWT verification](https://supabase.com/docs/guides/auth/jwts); strict local tests
remain `test_supabase_jwt.py`/`test_supabase_claims.py`.

## Server policy and resource authorization

The synchronous FastAPI dependency validates one unambiguous Bearer header, then
cryptographic claims and a fresh exact-subject provider user read; anonymous users,
reported bans/deletion, malformed/unconfirmed current email or unknown factors deny.
Owner-approved GoTrue omission/empty factor semantics allow zero-factor AAL1;
null/malformed/ineligible factors deny. Verified TOTP requires signed AAL2.
SDK-normalized arrays/client assertions are not independent authority. Native
confirmation markers are accepted under standard provider semantics, not independent
mailbox provenance or real-time session proof. No Auth DB observer/ledger is required.
Provider/JWKS/DB failures map to generic503; invalid credentials/unknown links to
indistinguishable401/Bearer challenge. Preserve no-store/redacted diagnostics.
Only then resolve UUID through UserIdentity joined to an existing User, using a
short owned transaction; immutable principal is not an authorization decision.
Every personal/group operation still applies server numeric ownership, invitation/
expiry/consent, quotas and transactional privacy rules. Never trust client target IDs,
email, username or metadata as caller identity. No mixed-auth fallback.
See [policy evidence](AUTH_POLICY_EVIDENCE.md), [configuration/hosted facts](AUTH_CONFIG_AUDIT.md),
[resource/group contract](RESOURCE_AUTHORIZATION.md) and [native current email](EMAIL_PROVENANCE.md).
Native callback/session/password/email/TOTP modules keep SDK fencing, URL scrubbing,
fixed redirects and provider-supported challenge/recovery; no stale assurance bypass.
Backend policy remains authoritative after frontend callback or SDK success.

## Release gates and required evidence

Exact origins/project/key/Neon pins, schema4/grants/backup/restore, native-only
cutover/rollback, AMD64 capacity/billing protection, SMTP/abuse, session/MFA/password/email races,
provider outages, removal/deletion and licensing remain [production gates](PRODUCTION_LAUNCH_READINESS.md).
The existing10/10 hosted mutation budget is exhausted; offline fictional tests do
not authorize sending emails, enrolling/removing factors or deleting accounts.
Preserve active Azure rotation/rollback until cutover; never return native users
to legacy credentials. The records below preserve original validation/assessment
history; current native code/tests and readiness supersede old delivery status.

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
| Identity binding / application authorization | Schema4/identity constraints, atomic clean provisioning and native ownership/composition tests. | Movelle: hosted schema/grants/cutover remain gates; resolution alone never grants resource access. |
| Email-confirmation evidence | `test_supabase_email.py` covers fresh provider markers and fail-closed rejection; see [policy review](AUTH_POLICY_EVIDENCE.md). | Native routes exist only in explicit compositions; confirmation/recovery, public redirects and secure email change need hosted acceptance. No independent provenance ledger. |
| Passwords (§3.1.1), throttling | Prompt 18 offline native-SDK/signed-AMR tests cover recovery, fresh password reauthentication, cancellation and generic failures; [hosted acceptance](PASSWORD_SECURITY.md) remains open. | Supabase + Movelle: validate configured length, Unicode, screening, enumeration and abuse controls; Free lacks built-in leaked-password protection. No compliance claim. |
| OTP (§3.1.4/3.1.5), authenticator management (§4) | Backup TOTP design approved; hosted recovery-code probe rejected. | Supabase + Movelle: test independent factors, replacement, reset enforcement and lockout disclosure; TOTP is not phishing-resistant. |
| Session management (§5) | JWT/dependency/SDK adversarial lifecycle tests and separate native routes; deployed selectors remain legacy. | Movelle: genuine public-origin session/resource acceptance and bounded post-logout validity/SPA/Free timeout gaps remain release requirements. |

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
