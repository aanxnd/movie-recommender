# Dormant password security (Prompt 18/26)

No production entry/routes, hosted settings, accounts, emails or databases change.
Use one shared SDK/controller and the approved exact origin/root callback from
[Prompt 12](SIGNUP_CONFIRMATION.md); preview/production origins remain unapproved.
Development redirect is `http://127.0.0.1:5173/`. Do not accept URL redirect input.

## Request and callback foundation

`createPasswordResetRequest` uses native `resetPasswordForEmail` with PKCE/S256 and
the fixed root redirect. Local invalid addresses deny before I/O; duplicate requests
are blocked. Existing, nonexistent, unconfirmed, rejected, limited and network-error
responses all receive the same conditional check-email guidance. This does not
assert account existence, provider acceptance, delivery or redemption. Wait/retry
manually if no message arrives; no automatic sends or email persistence are added.

Signup/recovery share `consumePkceCallback`: synchronous history scrubbing, exactly
one UUIDv4 code, exact origin/root, no extra query/hash fields and one attempt per
document, including failures/Strict Mode. A different consumer cannot redeem again.
Only safe results are retained, not SDK response credentials. Signup remains
`unproven`; no callback hint or historical confirmation timestamp proves its flow.

Credential fencing now covers native recovery, reauthentication and password PUTs.
Trusted modules may bind a request to a subject, a session lease and an AbortSignal;
foreign-subject credential responses deny before SDK persistence. The SDK storage
facade delegates to existing persistence while rejecting writes from cancelled work;
it creates no additional token store. Sign-in/recovery/refresh events cancel older
credential work. Cancellation cannot undo a server-side change already committed.
Use synchronous browser storage as configured; arbitrary async storage adapters need
separate race acceptance. Never print provider errors, URL codes, passwords or JWTs.

Native [reset requests](https://supabase.com/docs/reference/javascript/auth-resetpasswordforemail)
and [reauthenticate](https://supabase.com/docs/reference/javascript/auth-reauthenticate)
are public/user APIs; no privileged key or paid service is involved. Offline tests
use the pinned SDK with mocked HTTP. They do not prove hosted delivery or security
configuration. Recovery evidence, completion and sensitive changes follow in the
dependent PRs; this foundation alone authorizes no password mutation.

## Native recovery evidence and completion (dependent PR)

SDK 2.119.0 reads `redirectType` from its stored verifier suffix. Its
[`PASSWORD_RECOVERY` event](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/GoTrueClient.ts)
uses that same hint, not an independent server assertion. Both null and a forged
recovery hint are insufficient. Recovery requires a successful code exchange,
the recovery hint **and** `getClaims`-validated signed `amr.method = recovery` on
that exact returned token, subject and session. The SDK validates with pinned-project
JWKS or provider verification; Movelle additionally requires ES256, exact issuer,
audience, nonzero UUIDs, AAL, integer times and structured nonconflicting AMR.
[Supabase documents recovery AMR](https://supabase.com/docs/guides/auth/jwt-fields#authentication-methods-amrmethod).
Upstream [PKCE](https://github.com/supabase/auth/blob/master/internal/api/token.go)
issues the new session using the flow state's authentication method. This is source
evidence, not proof of the hosted version, custom-hook configuration or response.

`createPasswordRecovery` retains only private, ephemeral binding to this native
observation. No recovery grants, ledger, tokens or booleans enter React or custom
persistence. Restored sessions alone cannot initialize it. Logout, account/native
credential transitions (including refresh), expiry or a different callback consumer
invalidate it. Reload of the scrubbed URL fails safely; no code is re-redeemed.

`setPassword` revalidates the exact current native recovery session, then calls
`updateUser({password})` with a subject/lease-bound transport. Success consumes the
context; uncertain failure discards it, and only known policy/MFA/rate rejections
permit manual correction. No automatic mutation retry. Native MFA restrictions
remain authoritative: recovery at AAL1 is not permission to bypass enrolled TOTP.
Provider insufficient-AAL responses require later supported MFA integration.
Backend email/MFA/mapping/resource policy remains independently authoritative.
Password rules belong to provider configuration; no local complexity policy.
Already-issued JWTs may remain valid until expiry after password change/logout.

Activation needs separately authorized dev acceptance: genuine recovery AMR and
signed subject/session binding with pinned hosted ES256 keys; null/cross-flow hints,
expiry/replay/scanners, same-browser PKCE, update rejection/uncertain responses,
MFA-required recovery and native session/logout behavior. No such hosted tests ran.
