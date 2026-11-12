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

Missing/null, empty, duplicate, unsupported or malformed inventory fails closed.
Nonempty native TOTP lists distinguish pending, challenge-required and verified.
An AAL2 token with only unverified factors is conflicting/stale. **No observable
"not enrolled" state or first enrollment from an empty list is enabled yet.**
The hosted completeness gate must establish supported absence semantics before
that branch can exist; SDK normalization is not evidence. This intentionally
retains the Prompt 11 activation blocker rather than weakening the backend policy.

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
