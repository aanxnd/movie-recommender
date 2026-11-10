# Prompt 12: dormant native signup confirmation

`frontend/src/signup-confirmation.js` is a headless helper, not a route or session
provider. The current SPA uses in-memory tabs and serves `/`; production startup
does not import the helper. No public signup, backend cutover or provisioning is
activated. Prompts 16-17 will integrate the frontend after their own review.

## Selected mechanism and interface

Use pinned `@supabase/supabase-js` 2.119.0 with `flowType: 'pkce'`, automatic URL
session detection/refresh disabled and the standard SDK localStorage adapter.
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
then calls `exchangeCodeForSession`. Native returned email confirmation is required
for the UI status; URL email/IDs/flags/sessions and recovery-marked flows do not qualify.
All results contain only `status` and fixed `destination: '/'`, never credentials.
Statuses are `check-email`, `confirmed`, `missing`, `invalid`, `unavailable`.

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
this is not HttpOnly protection. No general session provider or session handoff UI
is implemented. A callback status grants no Movelle access: backend JWT/email/MFA,
identity and resource authorization remain authoritative. Legacy storage is untouched.

## Configuration and acceptance (not applied)

Future trusted bootstrap passes `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`
and `VITE_AUTH_APP_ORIGIN`; no secrets or callback-parameter configuration is allowed.
Require the canonical approved origin to equal the browser origin. Exact redirect
allowlist entries are `http://127.0.0.1:5173/` for default development, and each
owner-approved HTTPS preview/production origin plus `/`. If using `localhost`, add
its exact port/origin separately; do not use wildcard previews or runtime `next`.
Preview/production hostnames remain owner-confirmation gates. Set the Site URL to
the approved production root before rollout; the reported localhost:3000 default
is insufficient. No hosting rewrite is needed for this root callback.

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
