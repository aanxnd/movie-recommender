# Reviewed factor-removal candidate — EXECUTION DISABLED

`createFactorRemoval` is a concrete native SDK continuation; its default and every
current bootstrap return `removal-unavailable`. No hosted mutation is authorized.
The explicit reviewed fixture constructor exercises actual SDK requests offline.
Its review flag is a deployment gate, never proof of identity or authorization.

The candidate lists fresh owned factors through the existing signed-token/raw-user
observation, explicitly challenges an accessible verified TOTP factor, independently
checks resulting signed AAL2 and same subject/session/inventory, then issues exactly
one owned `mfa.unenroll`. A supplied AAL boolean never authorizes it. Unknown outcomes
are not retried. After a dispatched DELETE, the same current account is signed out;
another account is never logged out. Sign in anew and inspect authoritative factors
before continuing; no old AAL2 token or guessed AAL1 session is installed.

Every removal requires explicit consent that MFA may be disabled, even if an earlier
read showed several factors. The [supported API](https://supabase.com/docs/reference/javascript/auth-mfa-unenroll)
requires AAL2 for verified-factor removal. Pinned
[GoTrue](https://github.com/supabase/auth/blob/v2.197.0/internal/api/mfa.go) deletes
transactionally and downgrades affected stored sessions; it has no expected inventory
revision or atomic retain-one condition. Therefore backup-preserving replacement
deletion remains disabled. Existing alternative-factor/replacement enrollment and
verification remain available without deleting the lost factor.

This fresh-challenge requirement protects Movelle's continuation, not arbitrary
direct Supabase API callers with an existing AAL2 credential. Cross-device changes
after the last read cannot be prevented by client locks. A competing authenticated
device can change inventory; the candidate makes no final-factor retention promise.
Provider error/races fail closed locally but cannot undo committed provider changes.
Standard bounded JWT validity remains; logout is not instant global revocation.

Before enabling: review the deliberate opt-out semantics versus the old retain-one
invariant; separately authorize genuine same-session/other-session revocation, factor
ownership, deletion races, notification budget, lost acknowledgments, re-login and
independent-device acceptance. Hosted build semantics remain unproven. The 10/10
email reservations are exhausted; no tests here contact hosted Supabase. No admin
key, custom recovery code or email-only bypass is introduced.
