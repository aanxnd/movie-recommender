# Prompt 22 preservation evidence

Starting main: `4f556c4ab239359ebd09bd8fca3f36ff158c3a99` (Prompts 1–21 merged).
No runtime application/authentication code, model, migration, dependency, lockfile,
environment default or deployment workflow changed. No legacy component was deleted.
See the [inventory](LEGACY_AUTH_RETIREMENT.md) and [blocked readiness contract](AUTH_CUTOVER_READINESS.md).

## Local checks

- New backend separation/preservation tests: **11 passed**, real isolated SQLite and
  PostgreSQL 17, locally signed ES256 JWTs, no hosted provider/database connection.
- Relevant backend security, operator recovery, native auth/email/AAL/identity,
  ownership, schema/database, redaction and PR-size suite: **449 passed**.
- Existing personal-artwork authentication/key-isolation tests: **2 passed** with
  real provider credentials excluded. Combined relevant backend total: **451 passed**.
- Full frontend: **529 passed**, including 6 new real-SDK/storage/import-boundary cases.
- Chrome: **14 passed** across live-entry legacy creation/restoration/persistence,
  anonymous browsing and existing dormant signup/password/email/TOTP/recovery previews.
  New live-entry cases intercept API requests and block external traffic; no hosted
  registration or profile mutation is performed, even with inherited API configuration.
- Production build passed with unchanged asset hashes (`index-DGKnd8Bu.js`,
  `index-316Hum7Y.css`). Production import graph still reaches legacy App/identity/API
  and no dormant native bootstrap. No UI redesign or new screen was introduced.
- PR-size unit tests: **10 passed**, included in the backend suite above. No lint/
  typecheck script is configured. Existing httpx deprecation warning only.

Tests preserve database-allocated numeric IDs, credential digests/expiry, linked and
unlinked mappings, ratings and invitation relationships across rejected provider-token
attempts, read-only resolution and existing idempotent migrations on local fixtures.
They do not claim inspection of actual production records or production schema state.
Wrong-boundary tokens fail without provider fallback, metadata matching or writes.
SDK restoration/login/logout and legacy persistence use separate namespaces; rejected
native requests never read stored legacy credentials. No startup clearing/migration.

A limited tracked-source pattern check found no high-confidence private-key/access-key
or Supabase secret-key literal in the inspected auth/configuration paths. It prints
locations only, never values; local/hosted secret values were not read. No compromise
was established and no rotation was attempted. This is not a complete security audit.

## Remaining gates

Provisioning, existing-user access/data disposition, legacy operator-issuance retirement,
hosted Free acceptance/factor completeness/initial MFA enrollment, sensitive native
reauthentication, approved origins/Gmail delivery, staging, full NIST assessment,
professional audit and Prompt 26 activation/rollback remain owner-reviewed dependencies.
All-devices-lost recovery and factor removal remain unavailable. No Prompt 23/24 work,
hosted SQL/configuration/account changes, production deployment, merges or spending.
