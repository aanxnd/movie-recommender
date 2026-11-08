# Authentication architecture contract

Status: **PR 2A only; implementation and public signup are not authorized.**
Owner decisions and Prompt 1 / Prompt 1B research baseline: 2026-11-08.
This records the reports' architecture and unresolved conditions; it does not
represent a deployed system or successful provider validation.

## Decisions and boundaries

| Area | Contract |
|---|---|
| Budget | Strictly $0 additional spending: no paid plans, purchases, upgrades, trial credits or automatic paid overages. No owned domain or domain purchase. |
| Login | Supabase Auth Free email/password; verify email ownership before protected access. Usernames are unique case-insensitively for profile identity, never login identifiers. |
| Sessions | React SPA uses the Supabase SDK. Persistent browser tokens are JavaScript-accessible: XSS or a compromised dependency can steal them. CSP, safe rendering and dependency review reduce risk, not eliminate it. No claim of HttpOnly protection. |
| MFA | Optional standard TOTP, compatible with common authenticator apps. Single-use recovery codes are preferred; do not silently require a second device or allow email-only MFA bypass. |
| Email | Gmail's own authenticated SMTP is a conditional domain-free candidate, not validated production infrastructure. Keep email verification enabled. |
| Recovery | Native Supabase recovery codes are conditional and experimental, not approved for production. Hosted Free availability and lifecycle behavior remain unconfirmed. |
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
| Supabase dashboard | Free development project `movelle-auth-dev` was reported provisioned in Prompt 1; live state is unverified. Exact site/redirect allowlists, verification, secure email change, notifications, TOTP and abuse settings need separately authorized validation. No public signup enablement. |
| Gmail SMTP | Candidate `smtp.gmail.com:587` with STARTTLS, actual authenticated Gmail From address, full Gmail username and dedicated app password; enter secrets privately in Supabase, never source control or browser configuration. |
| Administrative access | No service-role key in the browser. Any future backend admin capability needs explicit scope review; ordinary JWT verification does not require it. |

## Open validation gates

**Both gates remain OPEN. PR 2B onward must wait for recorded evidence and owner approval.**
Use disposable users and controlled recipient mailboxes; no production-data testing.
Record date, SDK/provider version, Free-plan settings, sanitized results and reviewer.
Failure leaves the requirement unresolved; it is not permission to weaken it.

### Gmail SMTP: OPEN

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

### Hosted Supabase Free recovery codes: OPEN

- Confirm Free entitlement, enrollment/verification availability, hosted Auth and
  SDK versions, experimental opt-in and production suitability. General MFA docs
  and recovery-specific references conflict; upstream code is not hosted evidence.
- Prove: verified TOTP -> `aal2` generation -> offline one-time code storage ->
  fresh password login at `aal1` after device loss -> code redemption yielding
  genuine Supabase `aal2` -> enroll/verify replacement TOTP -> remove lost factor.
  Enroll the replacement first; recovery codes cannot be the sole remaining factor.
- Test replay, simultaneous redemption, regeneration invalidation, throttling,
  lockout, normal logout, password reset, session expiry, notifications and explicit
  session revocation. Document remaining JWT validity and backend rejection behavior.
- Native upstream uses random codes, salted Argon2id hashes and atomic consumption;
  validate actual hosted controls rather than assuming identical defaults.
- Custom Neon codes are not an approved fallback: admin factor deletion exists,
  but the gap before replacement verification permits enrollment races. A Neon lock
  alone cannot protect direct Supabase Auth calls. Require a demonstrated secure
  provider recovery flow; never fabricate `aal2`, expose admin keys or bypass MFA.

## Evidence and NIST work

Maintain an applicability matrix as implementation progresses: control/reference,
current and proposed behavior, responsible party, test/evidence, gap, effort/cost.
Keep password length/Unicode/screening, throttling/enumeration, email verification,
JWT/session revocation, reauthentication, TOTP/recovery and secret-safe logging in
scope. Existing transferable legacy credentials are not passwords or single-use
MFA recovery codes. TOTP is not phishing-resistant. Browser token exposure remains;
Free does not include built-in leaked-password protection or session timeouts.
Record compensating controls and unresolved gaps; never claim full compliance.

Research references from Prompt 1B, retrieved 2026-11-08 (not live validation):

- [Supabase Free features](https://supabase.com/pricing), [SMTP restrictions](https://supabase.com/docs/guides/auth/auth-smtp), [email notifications](https://supabase.com/docs/guides/auth/auth-email-templates).
- [Google SMTP and limits](https://developers.google.com/workspace/gmail/imap/imap-smtp), [app passwords](https://support.google.com/accounts/answer/185833), [Gmail policies](https://support.google.com/mail/answer/16734397).
- [Recovery generation](https://supabase.com/docs/reference/javascript/auth-mfa-recovery-codes-generate), [verification](https://supabase.com/docs/reference/javascript/auth-mfa-recovery-codes-verify), [general MFA reference](https://supabase.com/docs/reference/javascript/auth-mfa).
- [Upstream recovery implementation](https://github.com/supabase/auth/blob/master/internal/api/recovery_codes.go), [factor removal](https://supabase.com/docs/reference/javascript/auth-admin-deletefactor). Moving upstream sources do not guarantee a hosted version.
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
history, read-only permissions and no service secrets. Configure the named job as
a required branch-protection check separately; repository code cannot enforce
GitHub settings or stop an administrator bypass. No settings are changed here.

PR 2A is documentation and CI tooling only: no auth code, dependencies, database
changes, external configuration, public signup, deployment or automatic release.
Keep [deployment/rollback controls](DEPLOYMENT.md) for later authorized rollout.
