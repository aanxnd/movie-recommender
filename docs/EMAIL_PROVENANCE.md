# Native email challenge evidence: completed boundary and remaining blockers

Prompt 3D.5, reviewed 2026-11-09, starts from merged PR #32 (`d00e135`).
`AuthenticationEvidencePolicy`, `MailboxSource` and `LiveStateSource` are present
and remain dormant. No concrete `MailboxSource` is enabled by this PR.

## Supported mechanisms and precise limits

| Official evidence | What it establishes / does not establish |
|---|---|
| [verifyOtp](https://supabase.com/docs/reference/javascript/auth-verifyotp) | Supports email + OTP + `type: email`, or token hash. A successful server response establishes acceptance of that native credential. |
| [Native email flow](https://supabase.com/docs/guides/auth/auth-email-passwordless) | The native six-digit OTP and confirmation link share Supabase's verification mechanism; link use is one-time. A future resend/sign-in request must use `shouldCreateUser: false` for existing accounts. No new OTP generator/provider is needed. |
| [Email templates](https://supabase.com/docs/guides/auth/auth-email-templates) | `Token` is the native code; `TokenHash` is the link credential. Both are secrets, not historical proof. Current link-only templates may need an approved code/callback change. |
| [Admin generateLink](https://supabase.com/docs/reference/javascript/auth-admin-generatelink) | Returns links/OTPs for custom delivery. Credential possession/redemption alone cannot establish that delivery occurred or exclude administrative acquisition. We do not call this API. |
| [User object](https://supabase.com/docs/guides/auth/users) | Email/confirmation timestamps and editable metadata do not supply immutable challenge-origin evidence or a monotonic address generation. A snapshot cannot detect every A -> B -> A transition. |
| [Free hooks](https://supabase.com/docs/guides/auth/auth-hooks), [Send Email hook](https://supabase.com/docs/guides/auth/auth-hooks/send-email-hook) | A supported option for authenticated issuance events, not completion proof by itself. Enabling it replaces Supabase SMTP delivery with the hook's sender; it is not a passive observer of existing Gmail SMTP. No hook is configured here. |

Pinned official implementation corroborates the API, not our hosted version:
[`verify.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/api/verify.go)
POST verification issues an OTP-authenticated session. The supported
[`auth-js verifyOtp`](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/GoTrueClient.ts)
posts to `/verify`. No undocumented endpoint or invented verification claim is used.
That source also accepts confirmation/recovery token namespaces for `type: email`;
signed `otp` AMR does not establish signup/recovery purpose or mail delivery.

## Concrete independently useful component

`SupabaseEmailOtpVerifier.redeem(access_token, code)` in `app/supabase_email_otp.py`
is a dormant **existing-session reverification building block**, not first-signup
callback handling, login or a mailbox-provenance adapter. It:

1. Rejects non-ASCII/non-six-digit input and verifies the existing ES256 JWT using
   the pinned project's issuer/audience/JWKS and typed claims. No client-selected
   subject, numeric ID, address, assurance flag or decoded claim object is accepted.
2. Reads fresh `/auth/v1/user` with the user JWT/public publishable key. An account
   may be unconfirmed at this stage; its subject, role, audience, current address
   and non-anonymous status must agree with the trusted project/identity.
3. Posts only that provider-derived address, native code and fixed `type: email`
   to `/auth/v1/verify`. Address binding occurs **before** the consuming operation;
   arbitrary token-hash redemption is deliberately outside this component.
4. Verifies the returned ES256 JWT: same subject, a different session, issuance and
   signed `otp` AMR event no earlier than this request's integer-second start.
   These strict freshness checks are not recent MFA or a hosted acceptance result.
5. Checks returned user data and another fresh user lookup for the exact same
   address and nonfuture aware confirmation marker. Inconsistent changes fail.
   Returns frozen, repr-hidden `EmailOtpRedemption` without access/refresh tokens.

This actually verifies native credential redemption when called against a trusted
provider; offline tests validate the protocol, not hosted behavior. It does **not**
prove exclusive inbox delivery, genuine issuance provenance or address history.
Even an admin-generated valid OTP would yield only this limited result, never a
`MailboxChallenge`. Old/implicit/admin confirmation alone cannot skip redemption.
Uncertain historical accounts remain unproven for protected access.

No receipt is persisted, reused or converted into a durable allow decision. A
second call always asks Supabase again; native OTP expiry/single use remain provider
responsibilities, not claims of an implemented local anti-replay ledger. A -> B
and response mismatches are rejected; **unobserved A -> B -> A remains unproven**.
Existing evidence composition still denies without genuine provenance/live sources.

TLS, no proxies/redirects, fixed endpoints, 64-KiB responses, strict JSON and
three-second socket timeouts apply. Late completion/token expiry fails closed;
elapsed-time checks cannot cancel blocked I/O. Errors are generic and nothing is
logged. No automatic retry after timeout: the provider may already have consumed
the OTP. If integrated later, verification can confirm an Auth account and create
a new provider session; its credentials are discarded here. Session handoff/cleanup
and provider side effects require review before use. No live call occurs in this PR.

## Required supported workflow and owner authorization

Before any concrete `MailboxSource` can be safe, review an end-to-end native
confirmation workflow with protected issuance provenance, durable atomic receipt
consumption and exact subject/address binding. It must distinguish uncontrolled
admin-generated credentials from the approved delivery path, and invalidate every
prior receipt on all address changes, including direct/admin changes and A -> B -> A.
A Send Email hook alone does not establish that complete change history. Do not
invent a generation guarantee from `updated_at`, AMR or confirmation timestamps.

Owner approval is needed before template/redirect/hook/sender changes, backend
confirmation routes, new server-only secrets, an authoritative address-change
observer, evidence schema/migrations, or controlled hosted acceptance tests. Reuse
Supabase confirmation and the existing $0 Gmail candidate; no paid sender is
proposed. Gmail production deliverability remains open. No message is sent here.
If an approved delivery/change-observation design cannot establish these properties,
retain the fail-closed interfaces rather than installing a marker-only adapter.

No Neon IDs, ratings, groups, relationships, schema, legacy credentials, routes,
MFA policies or existing authentication components change. NIST evidence-based
alignment retains explicit provenance, session-revocation and recent-MFA gaps.
