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

Native `email_confirmed_at` is the approved confirmation authority. It must be
aware, nonfuture and bound to the exact verified subject and a nonempty current
email. Phone confirmation, signed email strings, metadata and client assertions
cannot substitute. We do not independently attest challenge history or reject
native administrative confirmation. Confirm Email must be enabled before launch.
The existing email reader and this policy share current-address validation;
`new_email` never replaces `email`. [Prompt 13](EMAIL_CHANGE.md) documents native
pending/partial changes, retained timestamps and acceptance limits.

A verified provider TOTP factor requires signed `aal2`; an explicit empty list
or only unverified factors permits `aal1`. Missing/null/malformed factor evidence
fails closed, including at AAL2. AAL2 proves the token's assurance,
not recent MFA. No five-minute challenge ledger is required. The implementation
follows the provider's [server AAL API](https://supabase.com/docs/reference/javascript/auth-mfa-getauthenticatorassurancelevel)
and [verified-factor selection](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/GoTrueClient.ts#L5885-L5915).

**Activation blocker:** SDK `listFactors()` also reads `/user` and normalizes
missing factors; it is not independent completeness evidence. Auth's
[`Factors` field](https://github.com/supabase/auth/blob/master/internal/models/user.go)
uses `omitempty`, so even legitimate non-MFA users may omit it and be denied by
this stricter dormant policy. Do not normalize absence into permission. The
[public API specification](https://github.com/supabase/auth/blob/master/openapi.yaml)
provides no separate non-admin factor-list endpoint. Offline response fixtures
are not hosted acceptance: separately approved Free-project tests must check
non-MFA, unverified/verified TOTP and AAL1/AAL2 response shapes before activation.
An omitted-field deployment remains blocked pending a supported completeness
contract/owner design review; no custom DB, privileged key or service is added.

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
