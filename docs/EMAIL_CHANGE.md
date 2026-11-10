# Current email and native email changes (Prompt 13/26)

## Dormant implementation

`ProviderEmailPolicy.check(raw_token)` verifies the JWT then makes the existing
fresh, pinned `GET /auth/v1/user` read with the public key and user's bearer token.
Its immutable, repr-redacted result now includes `email`, alongside subject,
confirmation and observation times. The shared private parser is also used by
`SupabaseAccessPolicy`; there is no second reader, cache, ledger or Auth SQL.
Only the exact verified subject's current `email` plus native
`email_confirmed_at` qualify. No frontend value, URL, metadata, signed stale email,
phone confirmation or saved result substitutes for this read. Native administrative
confirmation remains trusted under the approved standard-provider architecture.

Current and nonempty pending addresses must have a bounded, non-whitespace email
shape without control characters. Required confirmation timestamps must be aware
and nonfuture. Missing/malformed evidence, duplicate JSON fields, subject mismatch
and provider errors fail closed with generic errors. Omitted/empty `new_email`
is supported; null, malformed or identical-to-current pending addresses are
unsupported and rejected. An included `email_change_sent_at` must be well formed,
aware and nonfuture; it is neither completion nor confirmation evidence. The
reader does not expose a pending address as confirmed identity or grant access.
Numeric IDs, linking, ownership/privacy checks and production routes are unchanged.

## Supported provider contract and upstream evidence

- Supabase documents [getUser](https://supabase.com/docs/reference/javascript/auth-getuser)
  as an authenticated server read, unlike locally stored session user data.
  Later account settings should use supported
  [updateUser({ email })](https://supabase.com/docs/reference/javascript/auth-updateuser).
  No email-change request or token-redemption endpoint is added here.
- [Secure email change](https://supabase.com/docs/reference/python/auth-updateuser)
  normally requires confirmation at both old and new addresses. Disabling it
  sends confirmation only to the new address. This is configuration-dependent,
  not a guarantee inferred from the public user JSON or a callback result.
- The upstream [User model](https://github.com/supabase/auth/blob/master/internal/models/user.go)
  serializes the pending address as `new_email`; empty pending fields can be
  omitted. Confirmation progress is private, not a public step counter.
  `ConfirmEmailChange` replaces `email`, clears pending state, and can retain the
  original `email_confirmed_at` for an already-confirmed user. The sent timestamp
  can remain after completion; requiring a newer confirmation marker is incorrect.
- Upstream [verification](https://github.com/supabase/auth/blob/master/internal/api/verify.go)
  consumes the first secure-change confirmation without replacing current email,
  then commits the change after the remaining confirmation. Token checks reject
  invalid/expired links; consumed tokens cannot establish a new completion.
  [User update](https://github.com/supabase/auth/blob/master/internal/api/user.go)
  also requires AAL2 for sensitive changes when MFA is enabled.

Source reviewed on 2026-11-10 is upstream `master`, not proof of the hosted Auth
version/configuration. Offline fixtures model public snapshots from that source;
they do not execute provider verification, prove link expiry/replay or demonstrate
hosted delivery. Supabase Free uses the standard user APIs; no paid facility,
privileged key or independent challenge provenance is required or assumed.

| Observed user state | Movelle interpretation |
|---|---|
| Confirmed current A; no pending address | A is current provider-confirmed email. |
| Confirmed A; pending B | A remains current; B never qualifies. |
| First secure-change confirmation completed | Public fields can look identical to pending. Do not infer which side confirmed. |
| Current B; pending omitted/empty; original confirmation time | Use fresh B; do not require the marker to advance. |
| Unconfirmed current email, even with pending B or verified metadata | Deny email evidence. |
| Expired/failed/replayed request with unchanged pending fields | No local promotion or cancellation; read current state anew. |
| Provider error, inconsistent fields or subject substitution | Fail closed; no saved-user, JWT-only or legacy fallback. |

The reader does not implement cancellation or infer it from a missing pending
field. No documented cancel endpoint is assumed. Prompt 19 must establish the
supported retry/resend/replacement/cancellation behavior before offering controls.
Fresh A -> B -> A is accepted as provider state, without a historical ledger.
Email is not local account ownership or permission to claim old data.

## Remaining configuration and hosted acceptance gates

Owner-approved development-only testing is still required; none is performed here.
Verify Confirm Email and Secure email change settings, actual OTP expiry/resend
limits, optional change notifications, and the deployed provider response shape.
Exercise both confirmation orders and first-step-only behavior, completed changes
with retained timestamps, expiry, replay, resend/replaced requests, concurrent
changes and failure/cancellation semantics. Read `/user` freshly at each stage;
ensure the same subject is bound and pending email never grants account access.
Test unconfirmed accounts, provider outage and enrolled-MFA restrictions as well.

Prompt 12's [PKCE callback](SIGNUP_CONFIRMATION.md) remains `unproven` for signup
purpose; an existing confirmation marker cannot distinguish cross-flow callbacks.
It is not an email-change callback UI. Development origin remains
`http://127.0.0.1:5173/`; preview/production origins and redirect entries are
unapproved/TBD. No hosted setting or template is changed by this work.
The Prompt 11 missing-factor completeness blocker still prevents activation; no
normalization of unknown MFA state is introduced. Gmail spam/delivery/limits,
later route integration, NIST assessment and the full professional audit remain
launch gates. Authentication stays dormant; Prompt 14 has not begun.
