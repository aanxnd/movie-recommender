# Dormant frontend authentication (Prompt 16/26)

No module here is mounted/imported by production `main.jsx` or the live API client.
Existing anonymous browsing and legacy credentials stay unchanged. No signup/login
UI, backend cutover, provisioning, MFA workflow or hosted setting is introduced.

## Shared SDK and configuration

`getBrowserSupabaseClient` uses pinned Supabase JS 2.119.0. Explicit trusted
bootstrap may pass options or use only `VITE_SUPABASE_URL`,
`VITE_SUPABASE_PUBLISHABLE_KEY` and `VITE_AUTH_APP_ORIGIN`. Missing values fail;
setting environment values does not activate anything. Reject privileged keys,
noncanonical project URLs, credentials, origin mismatches and conflicting clients.
There is one client per browser window, shared with the Prompt 12 callback.

The explicit app origin is the build's exact one-origin allowlist. Development
is `http://127.0.0.1:5173` with root callback; preview/production origins remain
unapproved/TBD and unset. HTTPS configuration still requires owner approval; syntax
validation is not deployment approval. No guessed hosts, wildcards or URL-provided
configuration. The existing [callback contract](SIGNUP_CONFIRMATION.md) still
scrubs URLs before client construction and returns `unproven`, never signup proof.

Use PKCE, `detectSessionInUrl: false`, `autoRefreshToken: true`, SDK persistence
enabled and debug disabled. The SDK alone manages its existing `movelle.signup-confirmation`
storage namespace, including PKCE/session records; no custom token storage is added.
Only pinned-project `/auth/v1/` HTTPS requests are accepted by its bounded transport,
with redirects rejected, credentials omitted, no-store and no-referrer. Browser
storage remains exposed to XSS, not HttpOnly protection.

Hosted PKCE, cross-tab behavior, refresh/logout, provider factor completeness,
approved callback/API origins, Gmail delivery, backend integration and release
audits still require separate acceptance. No hosted users or emails are involved
in the offline real-SDK/mocked-network tests. Prompt 17 has not begun.

## Session controller and React boundary (dependent PR)

Create `getSessionController(sharedClient)` once in trusted bootstrap; it is shared
per SDK client and performs no I/O until subscribed. Pass it explicitly to
`AuthProvider`; `useAuth()` exposes status, SDK presentation user ID, safe error,
logout outcome, invalidation generation, refresh and logout actions. No raw session,
JWT, refresh token or metadata enters React state/context. `authenticated` is
presentation only; backend JWT/email/MFA/mapping/resource checks are authoritative.

States are restoring, authenticated, unauthenticated, refreshing, logging-out,
error and unavailable. One active SDK subscription serves all consumers; cleanup
unsubscribes, cancels personal requests and prevents detached callbacks. Strict Mode
shares pending restoration; newer SDK events supersede old `getSession()` results.
Callbacks are synchronous and do not invoke SDK auth methods inside the SDK lock.
Explicit refreshes coalesce; SDK 2.119.0 also coalesces native background refresh
and applies its failure cooldown. No additional polling/retry loop or JWT decoding.
SDK expiry hints trigger one refresh; bad/expired results clear credential access.

Logout immediately invalidates UI/transport, then calls supported
[`signOut({scope: 'local'})`](https://supabase.com/docs/reference/javascript/auth-signout).
Pinned 2.119.0 removes its local session before the server request and guards late
refresh commits. Offline tests verify this behavior through real SDK/mocked HTTP.
`sdk-accepted` means the SDK returned no error, **not** proof of remote revocation:
the SDK also normalizes certain 401/403/404 responses. Network/provider failure
reports `unconfirmed`; UI remains cleared. Existing access JWTs can remain valid
until expiry, as specified by standard Supabase sessions. No account deletion.

Only the trusted API adapter uses `withAccess`'s short-lived credential lease.
Identity switches, logout and final unmount abort/fence pending operations, including
late network results that ignore AbortSignal. Future personalized UI must key/reset
its caches by `generation` (not just user ID), ignore cancellation errors and never
store leases/tokens. Prompt 17 may compose these dormant interfaces after review;
no login UI, application provider mount or current API-client replacement is added.
Operations waiting for SDK restoration/refresh are fenced too; logout cancels them
before SDK work settles. Start personal requests after the authenticated state is
restored: discovering a different/initial identity cancels pre-bound operations.
