# Dormant account journeys (Prompt 17/26)

These modules require explicit trusted bootstrap and are not imported by production
startup. No hosted accounts, email, configuration or databases are changed.

## Native credential actions

`createAuthActions(config)` shares the existing SDK, session controller and native
PKCE helper. Mount the existing `AuthProvider` before using actions. Signup returns
the same `check-email` for new accounts and known existing-account responses;
neither means an account was created or verified. Login uses email/password, never
username. Invalid credentials and pending confirmation share generic guidance.
Provider/network errors expose fixed statuses only. No password policy is guessed:
native Supabase enforces the project's configured policy. Hosted policy, enumeration
behavior, throttling and delivery still need approved acceptance.

Only the SDK request receives credentials; actions return no user, token or password.
One credential operation runs per shared client. Logout/account changes abort and
fence pending signup/password/PKCE HTTP responses before SDK persistence, including
work waiting for PKCE preparation. Native SDK refresh behavior is unchanged. A
request already received by Supabase may still create an account/send email;
cancellation is not remote rollback. No automatic credential retry is added.

An SDK session is presentation state only. Backend native-email, MFA, mapping and
resource authorization remain authoritative. The callback still returns `unproven`
for ambiguous exchanges; it never promotes historical email timestamps to proof
that this link confirmed signup. Origins and acceptance gates remain in
[the callback contract](SIGNUP_CONFIRMATION.md).

## Isolated React screens (dependent PR)

`SignupScreen`, `LoginScreen` and `VerificationScreen` take trusted `actions` from
the shared factory; signup/login also require the existing `AuthProvider`. No
production router, application entry, API client or backend dependency is changed.
Optional navigation callbacks are trusted bootstrap functions, never URL targets.
The dark forest/brass layout adapts to mobile, uses explicit labels, native email
validity, accessible password controls, loading/disabled controls and focused live
status/error regions. Forms use uncontrolled password fields, cleared at dispatch;
passwords never enter React state, URLs, analytics or application persistence.

Signup checks matching passwords and uses provider policy, not a guessed local
length/complexity rule. Busy guards block repeated submissions. Login invalid and
pending-confirmation responses share guidance; throttling/outages remain generic.
Session generations clear forms and ignore late UI results after logout/account
switches. SDK session presentation explicitly does not imply protected access.

Verification keeps missing, invalid, expired-or-consumed, unavailable, rate-limited
and `unproven` states distinct. The existing helper scrubs before asynchronous work
and shares one attempt across Strict Mode consumers. No automatic navigation,
definitive signup-confirmed message, resend loop or account provisioning is added.
Mocked tests do not establish hosted delivery, password policy or factor-list
compatibility. Those acceptance gates remain open; no Prompt 18 work is included.

Offline review: Vite serves `/browser/account-demo.html` (also `?screen=login` or
`?screen=verification`). This separate test entry uses fixed fake actions and a
fake session, never hosted configuration/SDK requests. It is not a release entry
and Vite's production build excludes it. `npm run test:browser -- account-screens`
checks keyboard signup, focus and mobile overflow with the offline preview.

## Profile setup: contract, not a provisioning endpoint (final dependent PR)

`ProfileSetupScreen` defaults to an unavailable adapter. Even a restored SDK session
cannot create a local user. `ProfileProvisioning` is a JSDoc typed interface:
`inspect({signal})` returns eligible, complete-with-username, email-required or
unavailable; `provision({username}, {signal})` returns complete-with-username,
username-taken, email-required or unavailable. Surplus/malformed result fields deny.
Only trusted bootstrap may supply a future server adapter. No numeric ID, UUID,
email or browser verification flag chooses a target account. No live registration
endpoint or direct Neon connection is used. The preview's `?screen=profile` shows
the default pending state, not simulated successful provisioning.

Username input is exact, **not trimmed or Unicode-normalized**: 3–30 ASCII letters,
digits or underscores. Preserve case for display; compare ASCII lowercase, matching
the existing PostgreSQL `lower(username COLLATE "C")` unique index. Reserved names
(case-insensitive): admin, administrator, api, auth, help, login, logout, movelle,
root, security, settings, signup, support, system. These are frontend usability rules
pending matching server validation; the current database does not reserve names.
Server/database uniqueness, not frontend checks, must settle concurrent collisions.

The future Prompt 23 endpoint must derive the subject from verified credentials,
apply the native current-email/MFA policy **before** provisioning, and atomically
create at most one new numeric user/profile per subject. The current central
principal requires an existing identity link, so secure unmapped-subject bootstrap
needs separate design/review. Never claim a legacy account. Preserve numeric IDs,
ratings and relationships. Existing username/subject constraints remain unchanged.

Mutation is explicit, double-submit guarded and never automatically replayed.
Retry reinspects server state: an interrupted request may have committed, so a
complete result must return that same profile, irrespective of a later proposed
name. Logout/account changes/unmount abort the scope and reject stale UI results;
cancellation is not server rollback. The future adapter must use the existing
credential lease, bounded transport and generic errors. Offline tests demonstrate
UI behavior against that contract, **not** implemented atomic provisioning.

Activation still requires Prompt 23 provisioning, later route integration, approved
origins, hosted email/PKCE/password/throttle tests and Prompt 11 factor completeness.
No backend/schema changes, production mount or Prompt 18 implementation is included.
