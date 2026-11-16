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
denies; enrolled AAL1 requires MFA, while enrolled AAL2 uses the
[isolated password proof](MFA_SENSITIVE_OPERATIONS.md). No AAL2 downgrade or refresh-as-reauth.
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
API calls. Provider-side enforcement/owner review and broader hosted acceptance
remain; the native omission contract is now approved, as documented in
[password security](PASSWORD_SECURITY.md) and [production gates](PRODUCTION_LAUNCH_READINESS.md).

## Profile read/username contract (dependent PR)

The separate native release now supplies [owned GET/PATCH settings](NATIVE_ACCOUNT_SETTINGS.md)
and its credential-fenced frontend adapter. Legacy `/users/me` is not a substitute.
`AccountSettingsService` still defaults to unavailable outside explicit composition;
the local/private staging composition remains read-only. `inspect({signal})` authorizes the server-derived caller before
returning only `{status: ready, username, revision}`. SDK metadata/user IDs never
substitute. Malformed/surplus fields, including emails/IDs, deny before rendering.
The revision is a public optimistic-concurrency value, not identity or a credential.

`changeUsername({username, revision}, {signal})` has no ID/UUID/email ownership input.
Server guarantees: native email/MFA policy plus current subject mapping and
resource ownership; atomic compare-and-set revision and case-insensitive database
uniqueness; exact Prompt 17 ASCII/length/reserved-name rules; no trimming/Unicode
normalization; preserve spelling, numeric IDs, ratings and relationships. Do not
create, rebind or claim a profile. Missing identity uses the separate dormant
[Prompt 23 provisioning boundary](PROVISIONING_STAGING.md), never settings or metadata.
Enforce reserved names on the server too; the existing DB does not reserve them.

Successful replies must name the exact requested username and a current revision.
Concurrent conflicting changes and another account's case-insensitive collision
both return HTTP409 without identity details. The transport intentionally maps
both to a generic recheck. Every accepted explicit update increments the durable
revision, even for the same spelling; stale retries cannot masquerade as no-ops.
A stale revision must not overwrite an intervening different change. An
uncertain mutation requires reinspection, never automatic replay. No frontend-only
busy flag can provide server idempotency or concurrency guarantees.

The dormant screen resets/aborts on logout, account generation changes or unmount;
Strict Mode inspection is read-only. Only backend-authorized profile data is
shown, separately from device sign-in. UI protocol mocks are complemented by
real isolated PostgreSQL/SQLite CAS/constraint/transaction tests; none establishes
hosted acceptance. Provisioning remains a separate server boundary.

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

## Disable/delete: defaults remain unavailable

Default lifecycle controls still cannot execute disabling or deletion. A separate
[deletion candidate](ACCOUNT_DELETION.md) now supplies durable owned intent,
[server password/TOTP authorization](DELETION_AUTHORIZATION.md), an isolated
[provider worker](DELETION_WORKER.md), [privacy fence](DELETION_RESOURCE_FENCING.md)
and [gated screens](ACCOUNT_REMOVAL_UI.md). It is not selected by current entries;
its review-only metadata is not part of automatic migrations. No admin credential,
hosted DDL or real account deletion occurred. Enqueue success means pending, not
erased. Unknown outcomes remain blocked/retryable; no guessed restoration/linking.
Ordinary account disabling still has no execution path. Resolve the [current
operational gates](ACCOUNT_OPERATIONS_READINESS.md) before enabling either feature.

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
above. The fixed roadmap/audit remain owner-maintained; no production flow is enabled here.
