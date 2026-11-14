# Authentication cutover readiness — NOT AUTHORIZED

Prompts 22–23 prepare retirement/provisioning; neither activates Supabase or retires live access.
This is a fail-closed **review checklist**, not a runtime switch, endpoint, client
assertion or authorization grant. Passing tests or supplying environment variables
cannot change these decisions. No code reads this file to select an auth provider.

| Area | Current state / evidence | Required before cutover |
|---|---|---|
| Live production boundary | Legacy opaque profile bearer remains active in `app/main.py`; browser persists `movelle.identity.v1`. | Preserve until a separately reviewed coherent replacement; no mixed-token fallback. |
| Supabase boundary | Dormant in production; explicit local staging composes SDK/controller and backend principal/policy/resolver. | Review local integration and obtain hosted JWT/email/AAL/ownership acceptance. |
| Prompt 23 provisioning | **Merged, dormant in production**; subject-only principal, atomic schema-3 service and fenced adapter. | [Integration report](STAGING_CHECKPOINT_REPORT.md), approved configuration and hosted acceptance; no frontend metadata ownership. |
| Existing users | **Not migrated or automatically linked**; credentials, IDs and data remain. | Owner decision on existing-user access/data disposition. No email/username/code/ID matching or implicit claiming. |
| Hosted acceptance | **Partial real-provider acceptance:** signup, provisioning, first TOTP/AAL2, ratings and recommendations passed; additional failure and multi-device cases remain. | See [initial campaign](STAGING_SUPABASE_ACCEPTANCE.md) and [follow-up acceptance](NATIVE_MFA_FIX_ACCEPTANCE.md); complete remaining hosted security gates. |
| Factor absence / initial enrollment | **Implemented; first enrollment and AAL2 passed real-provider acceptance.** | Retain denial for null/malformed evidence and complete remaining adversarial/MFA journeys before activation. |
| Lost all authenticators | **Recovery unavailable**. | No email/password/recovery-AMR/support bypass. Any different provider-supported design needs explicit review. |
| Factor removal | **All Movelle deletion disabled**. | Authoritative final-factor concurrency protection or explicitly approved alternative policy; client counts/postchecks are insufficient. |
| MFA-sensitive password/email updates | **Restricted**. AAL2 is not fresh password proof. | Reviewed native same-subject/session/operation reauthentication that preserves assurance and provider requirements. |
| Redirects / email | Development root `http://127.0.0.1:5173/`; preview/production origins unapproved. Gmail production suitability open. | Exact owner-approved origins/redirects plus delivery, spam placement, sender limits and $0 abuse acceptance. |
| Data/schema / rollback | Repository schema 3; no hosted version inspected. Earlier deployment evidence describes schema 2. | Verify current production privately, rehearse additive migration and secure schema-compatible rollback. No drops/backfill/reset. |
| Pre-Prompt-24 staging | **Local and bounded real-provider acceptance recorded; no private cloud deployment. Prompt 24 not started.** | Approve exact private targets, cost/isolation and additional hosted tests separately. |
| Full assessment/audit | Full NIST SP 800-63B-4 assessment and original 16-stage professional audit remain required. | Document controls, evidence and gaps; no compliance claim from SDK AAL/offline tests. |
| Prompt 26 activation | **Not authorized**. | Explicit owner release/configuration/activation approval after all prior gates; no automatic merge/deploy. |

See [post-approval MFA acceptance](NATIVE_MFA_FIX_ACCEPTANCE.md) and the
[unapproved private deployment plan](PRIVATE_STAGE23_DEPLOYMENT_PLAN.md) for current evidence and cost/isolation gates.

Overall decision: **NOT READY / DO NOT CUT OVER**. An unavailable feature must remain
unavailable; it must not silently restore legacy credentials after Supabase rejection.

## Required evidence, not caller booleans

Use reviewed server code, database constraints, owner configuration decisions,
hosted acceptance records and staging/audit results. Frontend success flags,
`user_metadata`, matching addresses/names, a local storage key, UUID syntax or a
passing build are not authority. The future principal must resolve the numeric owner;
resource paths/group membership still require server authorization.

Keep `users.id`, existing credential digests/expiry, all ratings, invitations and
identity constraints intact. Do not delete records, change ownership/sequences,
clear persisted login state or add a second password database as preparation.
Live creation/restoration remain legacy-only. Prompt 23 gates the shared legacy
issuance primitive against non-null Supabase ownership, including operator recovery.
Historical credentials still authenticate; no legacy data or sessions are revoked.
This guard is not permission to claim accounts or activate new production routes.

See [component inventory and unapproved retirement sequence](LEGACY_AUTH_RETIREMENT.md),
[current policy](AUTH_POLICY_EVIDENCE.md), [MFA recovery](MFA_RECOVERY.md), and
[deployment/rollback](DEPLOYMENT.md). The fixed roadmap/audit remain owner-maintained.
