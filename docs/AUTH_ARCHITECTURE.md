# Authentication architecture contract

Status: **Architecture correction before Prompt 2B; no authentication implementation.**
Owner decisions and Prompt 1 / Prompt 1B / Prompt 1C evidence: 2026-11-08.
The owner-approved backup TOTP decision supersedes the earlier recovery-code
requirement. Implementation and public signup activation need separate authorization.

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

FastAPI will verify Supabase JWT signatures, approved algorithms, issuer,
audience, expiry and subject using maintained libraries and bounded signing-key
refresh. Server-side authorization must enforce verified email and the required
MFA assurance, not trust browser state or numeric IDs. Neon will map a unique
Supabase subject to the existing numeric user ID and enforce normalized username
uniqueness transactionally. Exact username normalization is a later reviewed contract.

Legacy linking must require both valid legacy ownership proof and the intended
verified Supabase identity, with one-time atomic linking and uniqueness checks.
Linked profiles must reject legacy authentication and operator credential reissue.
Expand existing bearer-header limits for JWTs in a later PR. Rehearse migrations
and schema-compatible rollback: an additive schema is not automatically compatible
with binaries that require an exact schema version. Never restore legacy bypasses.

## Configuration contract (names only; not implemented or configured)

| Location | Intended configuration and boundary |
|---|---|
| React/Vercel | Public `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`; retain `VITE_API_BASE_URL`. The public key is not an administrative credential. No SMTP, database or service-role secrets in `VITE_*`. |
| FastAPI/Azure | Server-only `SUPABASE_URL`; derive the approved issuer/JWKS location, validate audience `authenticated`, and reject mismatched projects. Keep existing TLS `DATABASE_URL` pointing to Neon. No new environment values in this PR. |
| Supabase dashboard | Owner reports Free project `movelle-auth-dev` with TOTP enabled, a 10-factor limit and Gmail SMTP configured. Exact site/redirect allowlists, secure email change, notifications and abuse settings still need validation. No project settings or public signup activation change in this PR. |
| Gmail SMTP | Candidate `smtp.gmail.com:587` with STARTTLS, actual authenticated Gmail From address, full Gmail username and dedicated app password; enter secrets privately in Supabase, never source control or browser configuration. |
| Administrative access | No service-role key in the browser. Any future backend admin capability needs explicit scope review; ordinary JWT verification does not require it. |

## Open launch gates

**Gmail SMTP production readiness and future MFA acceptance remain OPEN launch gates.**
Recovery codes are no longer a prerequisite for Prompt 2B. Its implementation
requires separate owner authorization after review of this architecture correction.
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
flows have not been implemented or validated by this documentation correction.

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

PR 2A added the contract and PR-size CI. This correction changes documentation only:
no auth code, dependencies, database changes, external configuration, public signup
activation, deployment or automatic release. Native recovery codes do not block
Prompt 2B; Gmail production readiness and later security acceptance block launch.
Keep [deployment/rollback controls](DEPLOYMENT.md) for later authorized rollout.
