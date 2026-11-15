# Profile revision foundation — dormant

Schema 4 adds `user_identities.profile_revision BIGINT NOT NULL DEFAULT 1`, with
a positive-value database constraint. No identity, username, numeric ID, rating,
credential or invitation is renamed, linked or deleted. Existing nullable identity
fields retain their meaning. Schema-1/2 upgrades create the latest identity table;
schema-3 upgrades add only this column, under the existing migration lock and
transaction. Startup checks never migrate.

The revision supports later atomic username compare-and-swap, including A→B→A
conflicts. It is neither a credential nor a client-selected ownership identifier.
No mutation route or production authentication is activated by this foundation.

Tests rehearse fresh schemas, old upgrades, constraint failures and transactional
rollback on isolated SQLite/PostgreSQL. These are not hosted Neon evidence.
No hosted migration is authorized. Confirm the actual deployed schema privately,
backup and rehearse before any separately approved release. Schema-4 binaries
refuse schema 3; old binaries refuse schema 4. Roll back to a schema-4-compatible
artifact, preserving the additive column and all data. Do not decrement the version
or drop the column to accommodate an unreviewed old image.
