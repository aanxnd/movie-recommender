# Application database and migrations

Neon PostgreSQL remains the selected application store; SQLite is supported only
for local development/isolated fixtures. Supabase stores authentication identities,
not Movelle ratings. Historical MovieLens users/arrays are separate read-only
reference data, never application profiles or records to copy into Neon.

## Schema and ownership

Repository schema version is4 (`app/migrations.py`), not evidence of the live
database version. `users.id` is the preserved numeric key. Movies are reference IDs;
ratings reference users/movies. Invitations remain owner/expiry/consent capabilities,
not persistent shared-group memberships. Native `user_identities` binds a unique
Supabase UUID to one numeric user; case-insensitive ASCII usernames are profile
labels. Nullable legacy identities stay unlinked; no fabricated subjects, renames,
data transfers, implicit claiming or legacy credential fallback.

Schema4 adds a positive durable username revision to schema3 identities; CAS prevents
concurrent/stale/ABA updates. Existing numeric keys, ratings and relationships are
preserved. See [revision evidence](PROFILE_REVISION.md), [identity/provisioning rules](AUTH_ARCHITECTURE.md)
and [owned resource authorization](RESOURCE_AUTHORIZATION.md).

## Operator actions — no execution approval

Migrations1–4 remain additive, serialized and transactional. SQLite uses BEGIN
IMMEDIATE; PostgreSQL uses an advisory transaction lock. Unknown/newer versions or
unexpected unversioned identity tables stop for inspection; no silent destructive
repair. Default/local development may initialize only its isolated DB. Native/Oracle
production startup checks schema and registers catalog IDs, never performs DDL.

The [Oracle operator tool](ORACLE_RUNBOOK.md#separate-operator-schema-tool-not-approved-for-execution)
requires reviewed exact native target/TLS pins and separate `movelle_native_migrator`
file credential. Only explicit check/migrate; no reset/recovery/claim command.
No credential/role was created and no hosted migration ran. Existing Azure uses its
retained [controlled procedure](DEPLOYMENT.md); do not dispatch it for Oracle.

Before approving hosted SQL: inspect actual target/version/grants privately; verify
backup/restore in a disposable DB, preserve existing IDs/relationships, rehearse
schema4 upgrade/lock/failure behavior and compatible rollback. Runtime privileges
must not include DDL/role management; migration/backup custody is operator-only.
No Auth-table grants or privileged Supabase key are needed for ordinary API policy.
Neon TLS requires verify-full/system roots/channel-binding, exact host/database/role.
Pool2/overflow0 is per process; statement/lock/transaction timeouts remain enforced.

Rollback is artifact-compatible, not a blind reverse migration/table reset. Never
restore legacy credential access for native users or discard deletion tombstones.
The [deletion journal](ACCOUNT_DELETION.md) is separate review-only metadata/SQL,
not installed in Base/migrations or selected at startup. Pending privacy/worker,
retention/storage/grant and provider acceptance gates must precede any erasure.
All real existing data and ignored local staging resources remain untouched here.
