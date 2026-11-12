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
