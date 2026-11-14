# Dormant native TOTP (Prompt 20/26)

No production entry imports these modules. No hosted tests, configuration, accounts
or factors were changed. Native TOTP adds no paid service. Backend ES256, current
email, numeric identity mapping, AAL and resource ownership remain independent.

## Evidence boundary

`observeMfa` uses the shared client's supported `getClaims` signature verification
plus existing strict ES256/issuer/audience/subject/session/expiry/AMR validation,
then a fresh `getUser(token)` bound to that subject and credential epoch. Only
sanitized factor labels/IDs/statuses leave the private observation. Refresh,
logout, account changes and expiry invalidate observations; no inventory is cached.

Pinned supabase-js **2.119.0**, installed auth-js `GoTrueClient.ts`:
`_listFactors` calls `getUser` and normalizes omitted factors to `[]`;
`_getAuthenticatorAssuranceLevel(jwt)` decodes JWT claims, reads `getUser`, and
also normalizes omission. Without a JWT it uses cached session factors. Neither
method independently verifies signatures or proves complete absence of factors.
The current/next distinction is signed current AAL versus the AAL attainable with
verified factors. Neither AAL2 nor AMR proves recent MFA, complete inventory or
real-time session revocation.

Owner-approved PR88 semantics interpret omission/empty as no factors only after
fresh authenticated exact-subject matching and signed evidence. Null, duplicate,
unsupported or malformed inventories deny. No-factor AAL1 offers optional first
setup; pending factors resume challenge. Verified factors require AAL2 for access
and additional setup. AAL2 without verified factors is stale/conflicting.
This trusts native serialization, not SDK-normalized arrays. The owner accepts
provider-response loss and non-atomic freshness limitations documented in the
[inventory review](MFA_FACTOR_INVENTORY_REVIEW.md). Hosted acceptance is still required.

## Sources and remaining acceptance

[Native TOTP guide](https://supabase.com/docs/guides/auth/auth-mfa/totp),
[MFA overview](https://supabase.com/docs/guides/auth/auth-mfa),
[listFactors](https://supabase.com/docs/reference/javascript/auth-mfa-listfactors),
[AAL reference](https://supabase.com/docs/reference/javascript/auth-mfa-getauthenticatorassurancelevel).
Auth's [user model](https://github.com/supabase/auth/blob/master/internal/models/user.go)
uses `factors,omitempty`; upstream source is not proof of the hosted build.

Owner-approved hosted acceptance must separately cover non-MFA, pending and verified
TOTP at AAL1/AAL2, completeness/omission, factor changes versus issued tokens, and
SDK response compatibility on Free. Offline fixtures prove local handling only.
No new database access, observer, privileged key or independent MFA service exists.
Preview/production origins, Gmail delivery/limits, audit and launch gates remain.

## Native challenge continuation

`createNativeMfa` shares the client/controller and serializes its operations. Each
explicit six-digit submission reads fresh inventory, selects only an owned factor,
calls native `challenge`, then consumes that challenge with `verify`. No challenge
ID, OTP or portable grant is retained. Provider errors never expose diagnostics.
The installed SDK saves the returned session and emits `MFA_CHALLENGE_VERIFIED`;
the existing controller accepts that event without cancelling its own transition.
Credential transport now fences factor mutations, including delayed response bodies
and subject substitution before SDK persistence. Logout/account changes/refresh or
explicit cancellation reject late writes. Other sensitive proofs are invalidated
after the native verification attempt, then the exact new token is cryptographically
validated and factors reread before any success is presented. No old token is restored.

[challenge](https://supabase.com/docs/reference/javascript/auth-mfa-challenge) and
[verify](https://supabase.com/docs/reference/javascript/auth-mfa-verify) are native
APIs. Offline real-SDK event tests are not hosted acceptance. No production login
routing changes. The same `inspect`/`verify` continuation supports dormant login;
unknown inventory blocks continuation, AAL1 prompts for TOTP, verified AAL2 avoids
a needless first-factor signin/downgrade. Backend access remains independent.

## Enrollment and management limitations

[enroll](https://supabase.com/docs/reference/javascript/auth-mfa-enroll) returns an
unverified factor plus QR/secret/URI; only a subsequent challenge can verify it.
Additional enrollment requires fresh verified AAL2 evidence and no pending factor.
First enrollment requires fresh no-factor AAL1 evidence. Unknown inventory denies;
no enrollment alone grants backend access. Production activation remains unapproved.
An uncertain enrollment latches further enrollment off for that service lifetime;
inspect after reload, then explicitly verify or safely remove a pending factor.
Cancellation cannot undo provider work, and no automatic cleanup/retry occurs.

Credentials remain private runtime memory for at most five minutes/token expiry.
Only the dedicated `presentSetup` sink receives them, returning DOM cleanup for
cancel/unmount/logout/refresh/account changes/verification. No React/global store,
clipboard, logging or app persistence. The provider SVG must pass a small structural
allowlist before becoming an encoded image URL; it is never injected as markup.
Strict parsing may reject future provider QR formats; hosted compatibility is required.
The pinned GoTrue renderer uses SVGo's inert root `xmlns:xlink` declaration and
goqrsvg's exact rectangle styles `fill:black;stroke:none` / `fill:white;stroke:none`.
These specific forms are allowed; links, arbitrary CSS, scripts, events and other
attributes remain rejected. Source-shaped fixtures are not hosted QR proof.
The verbose native rectangle format is bounded to 1MiB and10,000 opening tags
before XML parsing; oversized/node-heavy content is rejected, never truncated.

[unenroll](https://supabase.com/docs/reference/javascript/auth-mfa-unenroll) requires
AAL2 for verified factors. **Prompt 21 supersedes the earlier client-only removal
guard: all Movelle unenrollment is unavailable.** Fresh prechecks/postchecks cannot
atomically preserve a verified factor across tabs/devices. Even pending cleanup can
race verification. See [recovery and lockout](MFA_RECOVERY.md); review never deletes.
No admin removal, recovery code or email bypass.
Factor observations are private typed continuations, not reusable authorization
grants. Password/email changes retain their existing MFA-required denial: AAL2 is
not fresh password proof. Supporting them requires separately reviewed native
reauthentication without downgrading the session; no such bypass is added.

Hosted acceptance must cover QR format, additional enrollment, invalid/expired/replayed
codes, rate limits, native AAL2 event/session replacement, refresh/logout/account races,
abandoned factors, owned multi-factor removal and provider-enforced AAL restrictions.
None of those hosted mutations was performed. [Prompt 21](MFA_RECOVERY.md) adds
dormant alternative-factor/replacement continuations with explicit lockout refusal.

## Dormant screens

`MfaScreen` and `MfaLoginScreen` accept the trusted service only at explicit bootstrap.
They never mount from production routes. Read-only inspection may repeat under Strict
Mode; enrollment/challenge/removal require explicit actions. Forms mask and immediately
clear OTPs; no code/secret enters React state. QR/manual credentials use a dedicated
imperative sink and clear on teardown. Removal review focuses Cancel, traps keyboard
focus and explains bounded issued-token validity. Unknown evidence offers reinspection,
not account continuation. First setup uses the approved native no-factor observation.
Native verified AAL2 is presentation, not fresh password proof or a backend access grant.

## Offline preview and activation checklist

Run `npm run dev:frontend` and open `/browser/account-demo.html?screen=mfa`,
`mfa-login`, `mfa-unknown` or `mfa-error`. These are explicitly offline fixtures;
the illustrative QR is not a usable authenticator credential. No SDK is bootstrapped.
Chrome tests cover mobile/desktop keyboard continuation, removal dialog focus,
final-factor denial, unknown evidence and setup-key cleanup. Production entry and
build excludes MFA screens; neither previews nor frontend presentation grant access.

Before activation, approve a minimal hosted test plan separately. Required gates:
approved native no-factor semantics and first enrollment; hosted Free QR/URI formats; native challenge replay/expiry
and throttling; same-subject AAL2/session promotion and concurrent refresh/logout;
multi-factor ownership/removal and abandonment; sensitive password/email restrictions;
backend independent AAL/email/mapping/ownership; approved preview/production origins
and email delivery. No hosted evidence is claimed from mocked HTTP or browser tests.
NIST assessment and the full professional audit remain required; no compliance claim.
Prompt 21 remains under review. Merge review does not authorize deployment or activation.
