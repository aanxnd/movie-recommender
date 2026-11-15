# Dormant MFA-sensitive password/email continuation

The release and existing dormant account services support an enrolled user only
when their **primary, cryptographically checked session is already AAL2** and a
fresh same-subject provider read supplies valid TOTP inventory/current email.
AAL1/unknown inventory fails before password sign-in. This is not a recent-MFA
claim: users who need a challenge use the existing native TOTP flow first.

`checkIsolatedPassword` uses SDK 2.119.0's supported password sign-in in a private,
nonpersistent, nonrefreshing client. Its AAL1 credentials never enter the shared
SDK/controller, browser storage, React state or a backend request. Existing strict
signature/issuer/audience/session/AMR checks require the exact subject, a distinct
session UUID and password method. The temporary session is locally signed out
before the immediate password/email update; failed cleanup blocks dispatch. The
write uses the original AAL2 lease and existing subject/session/credential fences.
Cancellation cannot undo provider commits, so operations are never auto-retried.
No extra provider, persistent token store, custom challenge or privileged key exists.

Official [password sign-in](https://supabase.com/docs/reference/javascript/auth-signinwithpassword)
and [updateUser](https://supabase.com/docs/reference/javascript/auth-updateuser) are
the operations used. Pinned [GoTrue UserUpdate](https://github.com/supabase/auth/blob/v2.197.0/internal/api/user.go)
requires an AAL2 session when changing an enrolled user's email/password. Its
`current_password` check is configuration-dependent and recovery-sensitive; merely
sending that field is not password proof. Here the isolated successful sign-in
supplies proof independently of that setting. SDK `persistSession:false` uses
memory and creates no cross-tab broadcast channel. Logout retains standard bounded
JWT validity; this is not an instant-revocation guarantee.

Offline tests use actual pinned SDK requests with local ES256 signatures and
fictional user responses: AAL1 denial, password/email success preserving AAL2,
wrong account/issuer/session/method/assurance, provider/network/JSON/cleanup failures,
duplicate operations, account switching and safe output. They do **not** prove
hosted secure-password-change settings, email ordering/delivery, independent mobile
factors or deployed behavior. Provider nonce requirements remain authoritative and
fail closed; no email nonce bypass is implemented. A fresh owner-approved test
budget and safe authenticator handoff are required; existing 10/10 is exhausted.
Factor removal/opt-out and coordinated account deletion remain separate blockers.
If sign-in's response is lost, an unknown provider AAL1 session may exist; cleanup
cannot be asserted without its credential. No sensitive update follows and no
local token is retained. This is subject to the accepted bounded-session policy.
