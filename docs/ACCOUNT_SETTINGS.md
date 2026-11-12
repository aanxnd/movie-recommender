# Dormant account settings (Prompt 19/26)

No production routing, hosted configuration, account mutation, schema or backend
authorization changes. The 26-prompt roadmap/audit remain owner-maintained; this
implements Prompt 19 only. Prompt 23 provisioning and the separate dormant
[Prompt 20 MFA flows](TOTP_MFA.md) remain outside these settings mutations.
[Prompt 21 recovery](MFA_RECOVERY.md) adds no MFA reset or sensitive-update bypass;
all factor-removal actions remain unavailable because of cross-device races.

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

## Profile read/username contract (dependent PR)

There is no Supabase-aware settings or username-update endpoint. The legacy
`/users/me` is not such an integration. `AccountSettingsService` therefore defaults
to unavailable. No HTTP adapter, direct Neon call or identity writer is introduced.
The future `inspect({signal})` must authorize the server-derived caller before
returning only `{status: ready, username, revision}`. SDK metadata/user IDs never
substitute. Malformed/surplus fields, including emails/IDs, deny before rendering.
The revision is a public optimistic-concurrency value, not identity or a credential.

`changeUsername({username, revision}, {signal})` has no ID/UUID/email ownership input.
Future server guarantees: native email/MFA policy plus current subject mapping and
resource ownership; atomic compare-and-set revision and case-insensitive database
uniqueness; exact Prompt 17 ASCII/length/reserved-name rules; no trimming/Unicode
normalization; preserve spelling, numeric IDs, ratings and relationships. Do not
create, rebind or claim a profile. Missing identity remains a Prompt 23 dependency.
Enforce reserved names on the server too; the existing DB does not reserve them.

Successful replies must name the exact requested username and a current revision.
Concurrent conflicting changes return conflict; another account's collision returns
generic username-taken without identity details. Repeating an already achieved
desired state should return its current authoritative snapshot without a second
write. A stale revision must not overwrite an intervening different change. An
uncertain mutation requires reinspection, never automatic replay. No frontend-only
busy flag can provide server idempotency or concurrency guarantees.

The dormant screen resets/aborts on logout, account generation changes or unmount;
Strict Mode inspection is read-only. Only future backend-authorized profile data
is shown, separately from device sign-in. Mocked CAS/collision tests demonstrate UI
protocol behavior, not an implemented transactional backend or provisioning path.

## Email views (dependent PR)

The native email panel returns/displays statuses, not private email strings. User
input is uncontrolled and cleared at dispatch; no password/address enters React
state, URLs, logs or application persistence. It reuses Prompt 18's form scope and
visibility controls. Background reads announce without moving focus; explicit
requests/errors focus their safe message. Recheck only reads and never sends mail.

Callback snapshots carry the observed local session generation, not an identity
credential. The UI rejects a cached positive snapshot after logout/account switches.
It never automatically navigates or declares the requested address verified from
URL text, null redirectType, current SDK metadata or an old callback result.
Provider profile information remains separate from backend-authorized Movelle data.

## Disable/delete: review-only controls, unavailable execution

There is no application suspension state or approved lifecycle backend. Logout is
neither disabling nor deletion; bounded issued-JWT validity remains. The native
confirmation dialogs describe possible consequences, default focus to Cancel,
trap keyboard focus and restore it on close. Account changes/logout close them.
Acknowledgement is comprehension only, never ownership or reauthentication proof.
The final buttons are unconditionally disabled and have **no destructive handler**.
No service prop, environment flag or frontend checkbox enables either operation.
`pendingAccountLifecycle` is a typed future boundary returning unavailable, not a
working endpoint. Even explicit SDK sign-in does not authorize a lifecycle action.

Before implementing disabling, the owner must choose whether it means Movelle-only
suspension or also blocking provider login. Review the authoritative persisted
state, enforcement at every personal read/write/group boundary, active sessions,
reactivation and treatment of concurrent writes. Data/identity mappings remain
intact here. An app-only flag cannot be presented as a Supabase login ban.

Deletion requires separately reviewed server-side ownership/current-email/MFA and
operation-specific reauthentication, confirmation, idempotent resumable coordination
between Auth and Neon, and a barrier against concurrent username/rating/invitation
writes. A request ID identifies a retry, not a subject or authorization grant.
Do not promise a distributed atomic transaction or immediate JWT invalidation.
Completion must be reconciled before reporting success; uncertainty stays pending.
Review failure/retry ordering, session cleanup and any retained/tombstoned data.

The owner must approve retention/privacy rules and exact referential-integrity
behavior for the new subject's identity/profile, ratings and invitation capabilities.
Saved movies are derived from ratings; no separate watchlist or persisted group
model exists. Never touch another owner's rows, legacy users or public MovieLens
reference data. Do not link old data by email. Prompt 23 provisioning must respect
uniqueness and any future suspension/deletion state without recreating a deleted
account through a stale request. No such state/model/schema is introduced now.

Native [deleteUser](https://supabase.com/docs/reference/javascript/auth-admin-deleteuser)
is an administrative server-only operation; it cannot be performed by this browser
flow. Any future trusted coordinator/credential design requires owner review; no
privileged key is requested, stored or activated here. No deletion, ban or SQL runs.
The complete NIST assessment and original 16-stage audit must assess these gaps,
not equate disabled controls or offline mocks with enforced lifecycle guarantees.

## Offline review and activation gates

`/browser/account-demo.html?screen=settings` composes all dormant panels with fixed
synthetic services; `settings-pending` and `email-callback` preview uncertain flows.
No provider/backend requests or mail occur. Mocked profile/username success is not
server authorization evidence. Production entry/build remains unchanged. Run
`npm test`, `npm run build` and `npm run test:browser -- account-settings`.
Component fixtures disable Vite WebSockets; actual Chrome checks cover native
dialog focus/Tab/Escape and desktop/mobile layouts.

Before activation: approve exact origins/callbacks and hosted secure-email-change
configuration, validate both inbox orders/partial callbacks, signed AMR shapes,
retained timestamps, expiry/replay, resend/replacement behavior, throttling and
Gmail delivery. Resolve factor completeness and provider-side reauth limitations.
Implement/review authenticated profile reads, username CAS/uniqueness/idempotency
and Prompt 23 interactions. Lifecycle execution remains blocked on the decisions
above. Do not begin Prompt 20 or enable any production flow through this work.
