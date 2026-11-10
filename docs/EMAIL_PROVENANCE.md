# Native email confirmation and OTP

Prompt 11 replaces the independent mailbox-provenance requirement with standard
Supabase confirmation. `email_confirmed_at` from fresh, subject-bound Auth user
data is the approved authority; JWT email, phone confirmation, metadata and client
flags cannot substitute. The application does not distinguish administrative from
mailed confirmation or maintain an address-history ledger. This is an explicit
trust decision, not a claim that a timestamp proves challenge delivery history.

Keep [Confirm Email](https://supabase.com/docs/guides/auth/general-configuration)
enabled and use the supported [password/confirmation](https://supabase.com/docs/guides/auth/passwords)
and [password recovery](https://supabase.com/docs/reference/javascript/auth-resetpasswordforemail)
flows. Secure email change, exact redirect allowlists, recovery-token handling,
anti-enumeration, resend limits and real delivery remain acceptance gates.
Provider current-address confirmation is checked anew; address changes follow
provider semantics rather than a custom A -> B -> A invalidation system.
See [current email and native changes](EMAIL_CHANGE.md) for the shared reader,
pending/partial/completed states and hosted acceptance gates (Prompt 13).

`app/supabase_email_otp.py` retains a dormant native `/auth/v1/verify` email-OTP
helper. It verifies signatures, subject/address binding, returned session and
native OTP evidence, with bounded TLS transport and redacted errors. It consumes
a code and may create a provider session if called; tests use mocks only. Its
result contains no credentials and grants no resource access, MFA or live-session
proof. It is optional supporting functionality, not a second signup/recovery
system or mandatory challenge-provenance adapter. The future frontend uses the
Supabase SDK for standard flows; do not activate this helper without reviewing
session handoff and provider side effects.

No custom evidence table, delivery hook, privileged key or Auth database reader
is required. No messages, accounts or hosted configuration changed. Gmail SMTP
production suitability, spam placement, quotas and deliverability remain open.
See [standard policy](AUTH_POLICY_EVIDENCE.md) and [configuration gates](AUTH_CONFIG_AUDIT.md).
