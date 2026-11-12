# Dormant lost-device handling (Prompt 21/26)

Starting main: `19bd7cc62b777a1bee4f6f1191d151c0a31ded7a`, Prompts 1–20 merged.
Production authentication stays dormant. The owner maintains the fixed roadmap and
full professional audit separately. No Prompt 22/23 implementation is authorized.

## Supported boundary and threat model

An independently accessible, **already verified native TOTP** authenticator can
complete a native challenge, establish same-subject signed AAL2, then permit native
replacement enrollment. Replacement is unverified until its own challenge succeeds
and fresh inventory confirms verification. Registered factors do not prove independent
devices, current accessibility, recent password use or continued session validity.
Recommend another independently accessible device/app before losing the first.
Do not copy/export setup secrets as backups. Keep the native ten-factor limit.

All verified authenticators inaccessible means **recovery-unavailable**, including
with password/email possession or a previously issued AAL2 token. No password-reset,
recovery-AMR, email-only, metadata, support promise or reusable UI flag substitutes
for an alternative authenticator challenge in this workflow. No recovery-complete
claim follows merely from navigation or enrollment. Backend authorization is separate.
Empty/omitted inventory remains unknown; Prompt 20's initial-enrollment/no-MFA gate
is unchanged. Unknown, expired, conflicting or unavailable evidence cannot authorize.

## Removal safety correction

The pinned **supabase-js/auth-js 2.119.0** `_unenroll` sends an unconditional DELETE
using the current user's token. It accepts no expected factor count/version. The
[reference](https://supabase.com/docs/reference/javascript/auth-mfa-unenroll) requires
AAL2 for a verified factor, without promising final-factor preservation.
[Upstream Auth `UnenrollFactor`](https://github.com/supabase/auth/blob/master/internal/api/mfa.go)
deletes transactionally but permits deletion without another factor when no recovery
code set exists. Its recovery-code-specific protection is inapplicable here. This
source review does not establish the hosted build or its concurrency guarantees.

Two devices can both read two verified factors and each remove one. Local locks,
BroadcastChannel, another precheck or a postcheck cannot prevent provider commits.
Unverified cleanup can also race a verification. Therefore **all Movelle native
removal is disabled**, even after replacement. Review is informative, with no handler
or DELETE. No privileged endpoint/database workaround is added. Direct provider API
access remains governed by Supabase; frontend refusal is not a global provider policy.
Enabling removal requires supported authoritative final-factor enforcement or an
explicitly reviewed alternative policy, plus separate hosted acceptance.

## Provider recovery limitations

The [MFA overview](https://supabase.com/docs/guides/auth/auth-mfa) and
[TOTP guide](https://supabase.com/docs/guides/auth/auth-mfa/totp) support native
enrollment/challenge/verification, not an established all-devices-lost self-service
path for this project. The documented [admin deleteFactor](https://supabase.com/docs/reference/javascript/auth-admin-deletefactor)
is privileged server administration, not user identity proofing. No reviewed operator
identity-proofing, authorization, audit, notification or cost/support contract exists.
It is not approved or implemented. Do not promise support can reset MFA.
Native recovery-code enrollment previously returned HTTP 422
`mfa_recovery_codes_enroll_not_enabled`; it remains rejected for initial launch.
SDK/experimental API presence is not hosted availability. No code mechanism is added.

Password/email mutation restrictions remain in force. Relaxing them requires a
reviewed same-subject native password reauthentication continuation that preserves
MFA assurance, operation scope and provider-side sensitive-update requirements.
Recovery AMR proves neither TOTP nor fresh password use; AAL2 proves neither freshness
nor compliance. Full NIST assessment and the 16-stage audit remain launch gates.
