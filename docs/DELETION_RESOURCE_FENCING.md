# Deletion privacy fence — candidate composition only

Queue commit revokes the owner's invitation and legacy credential rows while
preserving ratings/profile until authoritative provider absence. No new sharing
grant is accepted after the intent. Candidate resource/settings/provisioning
transactions take the same user-row lock as queue submission, then read the journal
in a separate statement; an earlier authenticated principal cannot revive sharing
or write after waiting behind deletion. Group computation additionally excludes
every pending/tombstoned participant, not merely the authenticated requester, so a
residual invitation cannot authorize a pending user's ratings.

Only `compose_deletion_candidate` selects the transaction fence. Default legacy,
native-release, staging and private entries remain unchanged/unselected. No lifecycle
table is queried through this fence in those entries and no schema is installed.
All serving revisions/private paths for a target database must use the reviewed
native lifecycle boundary before submission is enabled. An old unaware revision
must not coexist as a bypass. Already admitted reads/computations may finish;
historically shared results cannot be recalled. This is not global instantaneous
revocation. Row locking adds latency and requires deployed contention acceptance.

Synthetic PostgreSQL/SQLite tests cover residual grants, another caller's group
query, authenticated-but-late requests, queued invitation races, missing storage,
capability revocation and preservation of other users. No production rows or hosted
accounts are touched. Default execution gates and the exhausted 10/10 budget remain.
