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
