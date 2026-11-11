# Dormant account journeys (Prompt 17/26)

These modules require explicit trusted bootstrap and are not imported by production
startup. No hosted accounts, email, configuration or databases are changed.

## Native credential actions

`createAuthActions(config)` shares the existing SDK, session controller and native
PKCE helper. Mount the existing `AuthProvider` before using actions. Signup returns
the same `check-email` for new accounts and known existing-account responses;
neither means an account was created or verified. Login uses email/password, never
username. Invalid credentials and pending confirmation share generic guidance.
Provider/network errors expose fixed statuses only. No password policy is guessed:
native Supabase enforces the project's configured policy. Hosted policy, enumeration
behavior, throttling and delivery still need approved acceptance.

Only the SDK request receives credentials; actions return no user, token or password.
One credential operation runs per shared client. Logout/account changes abort and
fence pending signup/password/PKCE HTTP responses before SDK persistence, including
work waiting for PKCE preparation. Native SDK refresh behavior is unchanged. A
request already received by Supabase may still create an account/send email;
cancellation is not remote rollback. No automatic credential retry is added.

An SDK session is presentation state only. Backend native-email, MFA, mapping and
resource authorization remain authoritative. The callback still returns `unproven`
for ambiguous exchanges; it never promotes historical email timestamps to proof
that this link confirmed signup. Origins and acceptance gates remain in
[the callback contract](SIGNUP_CONFIRMATION.md).
