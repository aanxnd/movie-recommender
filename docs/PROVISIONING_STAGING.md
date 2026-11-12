# Prompt 23: dormant provisioning and staging checkpoint

## Existing model and first boundary

Baseline: `8616a68554fc710b02657190586e66d18332bb90`, schema 3. `users.id`
is a database-allocated numeric key. Nullable `user_identities.supabase_subject`
is unique; `user_id` is its primary/foreign key; lower(username) is unique.
Ratings and expiring group invitations reference numeric IDs. There are no
password accounts, watchlists or persistent group memberships in this schema.
Opaque legacy credential digests/expirations live separately in
`profile_credentials`; `database.create_user` alone issues no credential.
Live POST `/users` and operator `recover-profile` separately issue credentials.
Existing capacity (5,000 profiles) and database admission counters must remain.

`make_provisioning_dependency` builds a trusted, immutable subject/session/AAL/
expiry principal without resolving an existing numeric profile. It reuses strict
ES256 verification and a fresh native current-email/factor check. No routes are
mounted. This is not a resource-access grant, real-time revocation check or proof
of recent MFA. Existing resource dependencies and global policy are unchanged.

Provisioning explicitly denies missing, null **and empty** factor inventories.
Prompt 20's authoritative no-factor completeness blocker remains: legitimate
accounts without provable inventory cannot provision. Nonempty provider evidence
uses the existing verified-TOTP → signed AAL2 rule. Initial MFA enrollment is not
unblocked here. Offline fixtures do not establish hosted response completeness.

The request contract accepts only `username`: 3–30 ASCII letters, digits or `_`,
case preserved, no trimming/Unicode normalization. Reserved names match the
frontend contract; the database enforces ASCII case-insensitive uniqueness.
No subject, numeric owner, email, AAL or linking evidence is accepted as input.

Production remains legacy-only and anonymous browsing is unchanged. Further
Prompt 23 transaction, issuance-isolation and frontend changes are separate
reviewable dependencies. No hosted changes, migrations or acceptance tests have
been performed. Prompt 24 remains on hold at the staging checkpoint.

## Transaction service

`inspect_profile` performs a fresh subject-only lookup. `provision_profile`
requires the trusted principal plus validated `ProfileInput`; no arbitrary
idempotency key or legacy owner is accepted. A fresh short Session owns the whole
User + UserIdentity transaction. The existing permanent capacity lock serializes
creation with legacy registration; a post-lock subject recheck preserves retries
at capacity. Database unique constraints remain final authority. No credentials,
ratings, invitations or extra profile state are initialized. Sequence gaps after
rollback are harmless; numeric sequences are never reset.

Existing linkage wins without renaming. After any database exception the failed
transaction closes before a fresh authoritative read. A committed subject is
returned; an actual competing username is a sanitized 409; unknown outcomes are
503, never an automatic second INSERT. Expiry is checked before work, before
commit and before returning. An expired response after commit requires new
authentication and inspection, not rollback of already-committed state.
Schema 3 already supplies the constraints; **no migration is required**.
Offline PostgreSQL tests exercise separate sessions/processes, capacity races,
case collisions and lost acknowledgements; these are not hosted acceptance tests.

## Dormant HTTP contract

`make_provisioning_router` is deliberately absent from `app.main`. A future
owner-approved staging composition must explicitly include it and install the
existing bounded-body `RequestLimits` plus exact-origin CORS. No existing env
flag enables it. GET `/auth/profile` returns `{status: eligible}` or
`{status: complete, username}` for the verified subject only. POST at that same
path accepts exactly `{username}` and returns complete; it is separate from live
POST `/users`. There is no profile-ID or subject parameter, claim or repair route.

Both operations authenticate freshly, reject query parameters/foreign Origin,
redact validation input and use no-store responses. Admission commits separately:
30 subject checks/minute; 10 creation attempts/hour per subject; the existing
1,000/day global creation bucket is shared with legacy creation. Parent request
limits retain public/IP admission and 16-KiB bodies. 409 is username unavailable,
401/403 denial, 422 invalid input, 429 bounded rate denial, 503 unknown/unavailable.
Clients must re-inspect after uncertain writes; no automatic POST retry.

## Dormant frontend adapter

`createProfileProvisioning(config)` uses the shared native SDK/controller and
authenticated API transport, then is passed explicitly as ProfileSetupScreen's
`service`. No production bootstrap imports it. GET inspection never creates a
profile. A user must submit the exact username for POST. Shared in-flight state
prevents duplicate writes across consumers; database idempotency remains final.
Logout, account A→B→A, caller abort and same-subject token refresh fence pending
results. No second token store or legacy storage cleanup exists. After an unknown
write outcome only a same-credential GET may recover complete; otherwise the UI
shows uncertain and offers inspection, never an automatic POST replay. Rate
denial/conflict and malformed response fields remain sanitized. A complete result
does not grant resource authorization or unblock any unresolved MFA gate.
