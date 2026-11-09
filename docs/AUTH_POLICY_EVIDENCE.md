# Authentication policy evidence and activation gates

Reviewed 2026-11-09. Prompt 3D completes **provider-reported email confirmation only**.
Prompt 3D.2 records the [final owner policy and configuration audit](AUTH_CONFIG_AUDIT.md).
Current-account/session and MFA enforcement remain **BLOCKED on evidence and
implementation gates**. No protected route or full-access predicate is provided.

## Provider guarantees and limits

| Evidence | Supported meaning / limitation |
|---|---|
| [JWT claims](https://supabase.com/docs/guides/auth/jwt-fields) | `email` is an address; standard claims do not establish email confirmation. `aal1` and `aal2` are different assurance levels at token issuance. An untrusted decoded claim is not evidence. |
| [User object](https://supabase.com/docs/guides/auth/users) | Top-level `email_confirmed_at` records email confirmation; `confirmed_at` can instead refer to phone confirmation. User-editable metadata is unsuitable for security decisions. |
| [Confirmation configuration](https://supabase.com/docs/guides/auth/general-configuration) | Disabling Confirm Email implicitly confirms addresses. [Admin updates](https://supabase.com/docs/reference/javascript/auth-admin-updateuserbyid) can also force confirmation. A timestamp alone therefore does not prove a mailbox challenge happened. |
| [getUser](https://supabase.com/docs/reference/javascript/auth-getuser) | Fetches authentic user data from Auth. The [JWT guide](https://supabase.com/docs/guides/auth/jwts) documents `GET /auth/v1/user` with a publishable `apikey` and user Bearer JWT. No admin key is necessary for this lookup. |
| [Account removal](https://supabase.com/docs/guides/auth/managing-user-data) | Issued JWTs can outlive deletion. A temporary ban blocks sign-in without revoking existing sessions; generic stateless JWT acceptance must not be called current-account enforcement. |
| [Server-side guidance](https://supabase.com/docs/guides/auth/server-side/advanced-guide) | Recommends fresh `getUser()` to detect server-ended sessions. This is live server evidence, not a guarantee of validity after the request or an application-defined disabled-state policy. |
| [Session guidance](https://supabase.com/docs/guides/auth/sessions) | Strict sign-out detection can check the JWT's `session_id` against `auth.sessions`. Session-row presence alone is not a universal expiry rule; timeout cleanup is deferred. Paid lifetime/inactivity controls are not a Free-plan substitute. |
| [MFA guide](https://supabase.com/docs/guides/auth/auth-mfa), [AAL API](https://supabase.com/docs/reference/javascript/auth-mfa-getauthenticatorassurancelevel) | Signed `aal2` denotes completed MFA, not current factor availability, recent step-up or real-time revocation. Server AAL calls with an explicit JWT validate the user and fetch factors; browser results/booleans are not server evidence. |
| [Free features](https://supabase.com/pricing) | Basic MFA and custom SMTP are included; advanced phone MFA, leaked-password protection, single-session enforcement and session timeouts are not. No upgrade/add-on is authorized. |

Public Auth source is corroborating implementation evidence, not proof of the
hosted project's deployed version/configuration: [user/session loading and ban
rejection](https://github.com/supabase/auth/blob/master/internal/api/auth.go).
No hosted account changes or behavior tests were performed in this review.

## Completed dormant component

`ProviderEmailPolicy(project_url=..., audience=..., publishable_key=...).check(token)`
in `app/supabase_email.py` first uses the existing ES256 verifier, then fetches
fresh user JSON only from that same project's `/auth/v1/user`. There is no
caller-supplied claims/evidence/verified boolean argument and no admin-key support.
Constructor/import performs no I/O; use a synchronous worker for `check()`.

A result requires an exact subject/response-ID match, a nonempty email address,
and a parseable timezone-aware, nonfuture top-level email-confirmation timestamp.
JWT email, `aal`, metadata and phone/generic confirmation fields cannot replace it.
The frozen result contains only subject, confirmation time and observation time;
its repr omits those fields. It is **not** an active-account/session or MFA proof.

Every call fetches new evidence: no user cache, saved-proof input or stale fallback.
Provider 401/403/404 and rejected confirmation evidence produce one fixed denial;
key/network/429/5xx/redirect/invalid-JSON failures produce one fixed unavailable
error. Never forward provider messages or log credentials, user JSON or claims.
TLS validation, fixed URL, no redirects/proxies, 64-KiB body cap and three-second
socket-operation timeouts apply; these are not a hard whole-request deadline.
Freshness ends at the observation: no atomic guarantee covers later resource writes.

This does not modify the FastAPI dependency, verifier, identity resolver, legacy
authorization, schema or hosted configuration. Later composition must preserve
JWT/subject binding before the existing dependency discards them; do not retrofit
client booleans or bypass email/session/MFA gates to make integration convenient.

## Final policy and remaining activation gates

Prompt 3D.3 adds [typed, signature-verified JWT evidence](AUTH_ARCHITECTURE.md#prompt-3d3-dormant-typed-verified-token-evidence),
including session UUID, issued/expiry times, AAL and optional AMR. It performs no
live state or provenance check and confers no access. Existing consumers still
use `verify() -> UUID`; this closes only the typed parsing foundation below.

1. Owner requires genuine current-email challenge evidence; uncertain implicit/admin
   provenance must be reverified before activation. Current settings/history remain
   unknown in the audit. This marker alone must not qualify protected access.
2. Owner requires live provider state on every protected request and fail-closed
   denial on unavailable checks. Hosted session/ban behavior, session binding,
   local suspension semantics and measured revocation limits remain unresolved.
   The audit specifies a conditional minimal server-only read adapter; no privileged
   credential, function, connection or infrastructure is created or activated.
3. Owner requires AAL1+ for ordinary browsing/ratings/recommendations and recent
   AAL2 for sensitive account/MFA operations. The audit recommends five minutes,
   with a fresh challenge protocol, and identifies direct provider-API enforcement
   and first-factor bootstrap blockers. Window/exception approval and hosted
   evidence are still required. Missing, stale or spoofed AAL2 cannot pass.

Fail closed while any required gate is unresolved or its provider is unavailable.
Resource ownership and group/invitation authorization remain independent mandatory
checks. Gmail deliverability, backup-TOTP acceptance, NIST gaps and production
release/rollback verification remain open. No email-only MFA bypass is approved.
