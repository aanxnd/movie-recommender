# Coordinated account deletion — EXECUTION DISABLED

The [authorization](DELETION_AUTHORIZATION.md), [worker](DELETION_WORKER.md) and
[transactional privacy fence](DELETION_RESOURCE_FENCING.md) are now concrete
dependent candidates. Queue commit revokes invitations/credentials before eventual
erasure; other account data remains until provider absence is authoritative. Every
current entry still leaves execution disabled. See [current readiness](ACCOUNT_OPERATIONS_READINESS.md).

This is preparation for reviewed lifecycle execution, not an enabled endpoint or
migration. `deletion_store.metadata` is separate from application Base/migrations;
only isolated SQLite/PostgreSQL fixtures install it. Live schema remains 4.
Current application entries never create a journal, enqueue work or delete data.

The journal binds one irreversible intent to a server-resolved numeric owner,
verified Supabase subject, exact issuer and request UUID. A server-only HMAC binds
immutable authorization fields: a database-only writer cannot substitute a different
subject/owner/issuer/expiry and turn the worker into a broad admin deputy. No JWT,
password, email, authenticator secret or provider key is stored. Signing-key custody,
rotation and worker privilege separation still need operational review; no key was
configured. Fixture keys are synthetic. UUIDs and audit IDs are personal data and
their retention/erasure policy must be approved before execution.

Pending intent blocks access and reprovisioning through the future lifecycle-aware
policy, including when provider deletion fails. Worker leases serialize claims;
compare-and-swap state transitions reject stale workers. No local data is erased
until authoritative provider absence is established. Local ratings, invitations,
credential, identity and user deletion commit with the complete/audit transition
in one transaction. Unknown new foreign-key dependencies roll it all back. Reference
movies and other users remain untouched. Hashed rate counters retain existing TTLs.

There is no distributed transaction. A deleted provider identity plus failed Neon
cleanup remains **blocked/retryable**, never silently restored or relinked. Provider
timeouts/unknown outcomes must be reconciled from fresh exact-subject evidence.
The code only appends fixed-value events without raw diagnostics; effective grants
must still enforce no audit UPDATE/DELETE before execution. No hard-delete rollback or
automatic identity recreation is promised. Sessions already admitted before a
deletion intent may finish; this is not an immediate global revocation guarantee.

Before activation: approve the exact DDL/migration rehearsal (not included in the
automatic migrator), application/worker grants and HMAC custody, server-side fresh
password/assurance checks, all-route block wiring, retention and storage ownership,
provider admin capability, cost isolation and genuine hosted acceptance under a new
budget. No browser may hold an admin capability. The worker must have no inbound
public deletion endpoint and no ability to select a target from a browser numeric ID.
