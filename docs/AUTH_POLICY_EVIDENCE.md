# Standard Supabase authentication policy

Prompt 11/26 owner revision supersedes the earlier custom provenance, live Auth
DB-state and recent-MFA requirements. Implementation remains dormant. Prompts
1–10 are historical completed work; Prompt 12 adds a [dormant native callback](SIGNUP_CONFIRMATION.md). The implementation
roadmap and full 16-stage professional audit are maintained separately by the
owner/ChatGPT; this technical policy does not replace either.

## Enforceable dormant boundary

`SupabaseAccessPolicy(...).check(raw_token)` verifies ES256 JWTs with the pinned
project issuer, audience and JWKS, then reads fresh same-project Auth user data
using only the public publishable key and that user's token. It returns immutable
verified token claims, never an authorization flag or client-selected user ID.
Prompt 14's additive `check_with_email` returns those claims and existing native
email evidence from the same checks/read. The central
[FastAPI dependency and principal](AUTH_ARCHITECTURE.md#prompt-14-central-principal-and-verification-order-dormant)
combine them with existing-link resolution, without repeat verification/fetches.
Provider `is_anonymous` must explicitly be false; omission/null is not evidence.

Native `email_confirmed_at` is the approved confirmation authority. It must be
aware, nonfuture and bound to the exact verified subject and a nonempty current
email. Phone confirmation, signed email strings, metadata and client assertions
cannot substitute. We do not independently attest challenge history or reject
native administrative confirmation. Confirm Email must be enabled before launch.
The existing email reader and this policy share current-address validation;
`new_email` never replaces `email`. [Prompt 13](EMAIL_CHANGE.md) documents native
pending/partial changes, retained timestamps and acceptance limits.

The owner approved PR88's provider trust contract: after signature verification
and a fresh successful exact-subject `/user` read, omitted `factors` or `[]` means
zero factors. Explicit null, malformed, duplicate and unsupported factors deny.
Verified TOTP requires signed AAL2; zero or only unverified factors permits AAL1.
AAL2 without any verified factor is stale/conflicting and denies. Provisioning
uses this same policy; it does not require optional MFA or grant resource access.

This relies on reviewed [GoTrue v2.197.0](https://github.com/supabase/auth/blob/v2.197.0/internal/models/user.go)
eager loading and `omitempty` serialization. SDK list/AAL helpers still provide no
independent completeness evidence. The owner accepts silently incomplete valid
provider responses cannot be independently detected and reads are not atomic with
Supabase enrollment or Neon writes. See [review](MFA_FACTOR_INVENTORY_REVIEW.md).
No client claims, cached inventory, Auth DB, privileged key or fallback is used.
Hosted no-factor/pending/verified/AAL1/AAL2 journey acceptance is still required;
implementation review does not authorize deployment or production activation.

[Standard sessions](https://supabase.com/docs/guides/auth/sessions) permit issued
access tokens to remain valid until expiry after logout. Fresh
[getUser](https://supabase.com/docs/reference/javascript/auth-getuser) is provider
user evidence, not proof of session-row existence or immediate revocation. Reported
bans/deletion and provider rejections deny; no immediate ban/deletion guarantee is
claimed. Every check reads anew; only signing keys are cached. Provider outages,
rate limits and malformed responses fail closed, with fixed redacted errors.
The shared transport uses validated TLS, a pinned URL, no redirects/proxies,
64-KiB responses and three-second socket timeouts, not a total-request deadline.

The dormant FastAPI factory now requires `publishable_key` and composes this
policy before existing-link resolution. Neither factory nor policy is attached
to production routes; protected resources still need their own authorization.

## Integration and launch gates

Anonymous movie browsing and public signup are the target. Ratings, personalized
recommendations and personal features require authentication and independent
backend ownership/group/privacy checks. Existing routes remain unchanged.
Use supported Supabase confirmation/password recovery and optional TOTP, with an
independent backup factor encouraged and all-factor-loss lockout disclosed.
No email-only MFA bypass, native recovery-code dependency or legacy-account migration.
New accounts receive new local identities; never claim old data by matching email.

PRs #34–36 are superseded infrastructure, left open and unmerged. No Auth DB role,
SECURITY DEFINER function, catalog fingerprint or privileged runtime key is needed.
Activation still needs full integration, security tests, $0 capacity/abuse controls,
Gmail delivery/spam/limits acceptance, provider MFA/reset acceptance, the complete
NIST SP 800-63B-4 assessment with gaps, and the original 16-stage professional audit.
No formal compliance or production-readiness claim follows from offline passes.
