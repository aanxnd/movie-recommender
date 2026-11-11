# Prompt 12: dormant native signup confirmation

`frontend/src/signup-confirmation.js` is a headless helper, not a route or session
provider. The current SPA uses in-memory tabs and serves `/`; production startup
does not import the helper. No public signup, backend cutover or provisioning is
activated. Prompts 16-17 will integrate the frontend after their own review.

## Selected mechanism and interface

Use pinned `@supabase/supabase-js` 2.119.0 with `flowType: 'pkce'`, automatic URL
session detection disabled and the standard SDK localStorage adapter. Prompt 16
centralizes this client and enables SDK-managed refresh; callback parsing is unchanged.
`createSignupConfirmation({ projectUrl, publishableKey, appOrigin, browser })`
is explicitly configured by trusted bootstrap code; it reads no environment itself.
`signUp(email, password)` calls native email/password signup with fixed
`emailRedirectTo: appOrigin + '/'`. Use the native Confirm signup template's
`{{ .ConfirmationURL }}` and keep Confirm Email enabled. The Auth verification link
then redirects to `/?code=<authorization-code>`; this is not a token-hash or implicit
session callback. Experimental overlapping-flow options are not enabled.

`confirm()` synchronously replaces the URL/history state with `/` before SDK
construction or I/O. It accepts only one UUIDv4 code, matching the reviewed
[Auth flow-state source](https://github.com/supabase/auth/blob/master/internal/models/flow_state.go),
then calls `exchangeCodeForSession`. Success returns `unproven`, never `confirmed`:
[`redirectType`](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/GoTrueClient.ts#L1972-L2008)
is a client-stored recovery hint, not a provider assertion. [Signup and other
non-recovery flows](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/lib/helpers.ts#L455-L470)
share null; a historical `email_confirmed_at` cannot identify this link's flow.
Recovery/non-null hints deny. A namespaced verifier is not a signup attestation.
All results contain only `status` and fixed `destination: '/'`, never credentials.
Statuses are `check-email`, `unproven`, `missing`, `invalid`, `unavailable`.
A signup-specific success UI remains blocked pending owner review of a supported
flow-specific workflow. No custom ledger or new backend policy is introduced;
the approved native account-email policy is unchanged.

The per-document promise deduplicates concurrent/StrictMode consumers, including
failures. Reload at the clean URL cannot redeem again. Reopening an original link
relies on SDK verifier binding and provider expiry/single use; no local ledger or
automatic retry exists. Network loss can leave redemption uncertain: request a new
confirmation email through later UI, rather than retrying automatically. If URL
cleanup is blocked, no redemption occurs. No raw provider errors or URLs are logged.

The SDK owns PKCE verifiers and returned sessions under `movelle.signup-confirmation`
in localStorage. This enables email links opened in another tab on the same origin,
browser and device; another device/private profile fails safely. Starting another
flow can supersede the previous verifier. JavaScript/XSS can read browser storage;
this is not HttpOnly protection. The [Prompt 16 infrastructure](FRONTEND_AUTH.md)
is dormant; no session handoff UI is implemented. A callback status grants no Movelle access: backend JWT/email/MFA,
identity and resource authorization remain authoritative. Legacy storage is untouched.

## Configuration and acceptance (not applied)

Future trusted bootstrap passes `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`
and `VITE_AUTH_APP_ORIGIN`; no secrets or callback-parameter configuration is allowed.
`appOrigin` is the one-origin allowlist for that build: it must be explicitly
configured and equal the browser origin. There is no inferred deployment origin
or fallback from URL parameters. The owner's approved configuration values are:

| Environment | `VITE_AUTH_APP_ORIGIN` | Exact callback/redirect allowlist entry | Approval |
|---|---|---|---|
| Development | `http://127.0.0.1:5173` | `http://127.0.0.1:5173/` | Approved value; hosted configuration/testing not applied |
| Preview | Unset / TBD | TBD | Explicitly unapproved |
| Production | Unset / TBD | TBD | Explicitly unapproved |

Before later configuration, the owner must approve every exact preview HTTPS
origin and its root callback URL, the exact production HTTPS origin and root
callback URL, and the production Site URL (the same approved production root).
Leave preview/production configuration unset until approval; do not guess Vercel
hosts, infer aliases, allow wildcard previews or accept runtime `next`/`redirectTo`.
`localhost` is a different origin and is not approved by the development decision.
The reported localhost:3000 Site URL is not the approved callback configuration.
URL approval does not authorize settings changes: Supabase and Vercel settings
remain untouched. No hosting rewrite is needed for this root callback.

Offline tests exercise the real SDK with mocked HTTP only. Hosted templates,
allowlists, Confirm Email, actual PKCE redirects, cross-tab/device behavior,
expiry/replay and Gmail spam/link-scanner handling require separately approved dev
acceptance. The no-referrer HTML meta precedes assets; SDK requests also suppress
referrers and redirects. URL scrubbing cannot erase initial ingress/query logs:
owner must verify hosting/APM query redaction before activation. No messages or
hosted accounts/settings changed. The [Prompt 11 factor-completeness blocker](AUTH_POLICY_EVIDENCE.md)
still blocks protected-access activation and is outside this prompt.

Official mechanisms: [PKCE and same-browser limitations](https://supabase.com/docs/guides/auth/sessions/pkce-flow),
[native signup](https://supabase.com/docs/reference/javascript/auth-signup),
[code exchange](https://supabase.com/docs/reference/javascript/auth-exchangecodeforsession),
[native email templates](https://supabase.com/docs/guides/auth/auth-email-templates).
