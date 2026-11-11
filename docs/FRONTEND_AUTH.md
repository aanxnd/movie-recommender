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
