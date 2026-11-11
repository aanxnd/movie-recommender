# Dormant account settings (Prompt 19/26)

No production routing, hosted configuration, account mutation, schema or backend
authorization changes. The 26-prompt roadmap/audit remain owner-maintained; this
implements Prompt 19 only. Prompt 23 provisioning and later MFA flows remain separate.

## Native email changes

`createNativeEmailSettings` reuses the pinned SDK, session leases and Prompt 18's
immediate password continuation, scoped to `email-change`. Unknown factor evidence
denies and enrolled TOTP returns MFA-required; no AAL2 downgrade or refresh-as-reauth.
Only native `updateUser({email}, {emailRedirectTo: approvedOrigin + '/'})` writes.
Subject/session/credential/persistence fences prevent stale account substitution.
Already committed provider changes cannot be undone by browser cancellation.

`inspect` verifies native token evidence and freshly reads the same subject's user.
It exposes only current-confirmed, current-unconfirmed or change-pending statuses,
never addresses, IDs, metadata or credentials. `new_email` is pending, never the
current identity. Original confirmation timestamps may remain after A → B → A;
no history ledger or newer-timestamp requirement is invented. Backend Prompt 13's
fresh current-email policy remains the access authority; frontend state grants none.

Update dispatch returns identical conditional check-email guidance for acceptance,
email-exists, throttling and uncertain provider/network responses. It does not
confirm a new address or delivery. Recheck freshly before another request; no
automatic retry. Existing pending requests are not silently replaced. No raw
provider errors or private emails are returned to React, logs or URL state.

Callback uses the shared synchronous scrubbed, once-only PKCE boundary and requires
signed `email_change` AMR on the exact exchanged token before a fresh status read.
Null redirectType alone proves no purpose. Signup/recovery cannot redeem again.
Partial confirmation can redirect with a message and no code: URL text is never
evidence. Show an ambiguous result and request a fresh status check instead of
guessing which inbox has confirmed. No automatic navigation or implicit callback.

Official [updateUser](https://supabase.com/docs/reference/javascript/auth-updateuser),
[verification source](https://github.com/supabase/auth/blob/master/internal/api/verify.go),
[resend source](https://github.com/supabase/auth/blob/master/internal/api/resend.go)
and SDK 2.119.0 were reviewed. Secure email change can require both inboxes;
hosted settings/order/expiry/AMR are unverified. `resend(type: email_change)` is
documented but takes an email lookup, not a subject-bound authenticated mutation;
this PR exposes no resend, replacement or cancellation control. No supported
public cancel API is assumed. Recheck is read-only. Approve hosted acceptance of
both confirmation orders, retained timestamps, expiry/replay, provider errors,
enumeration, races and Gmail delivery before activation. Preview/production roots
remain unapproved; development is `http://127.0.0.1:5173/`.

Fresh password use protects this Movelle continuation, not all direct Supabase
API calls. Provider-side enforcement/owner review and the Prompt 11 factor-shape
blocker remain, as documented in [password security](PASSWORD_SECURITY.md).
