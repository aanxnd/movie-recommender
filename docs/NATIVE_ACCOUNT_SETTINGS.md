# Native username API — dormant

`account_settings_router` is an explicit composition factory, absent from the live
legacy backend. GET/PATCH `/auth/settings` use the existing cryptographic JWT,
fresh native current-email/factor policy and exact verified-subject resolution.
No caller may supply a numeric owner, subject or extra request field. Enrolled
users require signed AAL2; username updates do not create a provider identity.

Schema 4's durable revision is a decimal string, checked atomically alongside the
exact subject and numeric owner. Every successful PATCH increments it, including
same-name requests, preventing stale and A→B→A writes. Database lower(username)
uniqueness remains authoritative; conflicts never rename either user. Separate
committed quotas apply even to failed conflicts. Credentials, numeric IDs, ratings
and invitations are unchanged. No mutation is automatically retried: after any
uncertain result, inspect again before an explicit fresh request.

Offline SQLite/PostgreSQL tests cover atomic races, case collisions, unknown owners,
expiry during writes and existing-data preservation. Production remains dormant;
native frontend wiring and hosted acceptance are separate, unexecuted gates.
