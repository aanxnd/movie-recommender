# Dormant personal-resource authorization (Prompt 15/26)

Authentication supplies `SupabaseAuthContext` through Prompt 14's
`Depends(authenticate)`. Authorization below determines which database rows that
caller can use. No production route imports these helpers; legacy API contracts,
public browsing, credentials, numeric IDs and schema 3 are unchanged.

## Actual inventory and policy

| Resource / existing endpoint | Stored relationship and access policy |
|---|---|
| Movies/search/decades, popular/genre recommendations, artwork | Public catalog/reference data. Keep existing anonymous reads and workload limits; no profile visibility flag applies. |
| `/users/{user_id}`, `/users/me` | `users.id` numeric PK; `user_identities.user_id` FK/PK and unique `supabase_subject`. Private self only; username/email never prove ownership. |
| Ratings, rating detail pages and bulk lookup | `user_ratings(user_id, movie_id)` composite PK, FK to user/movie. Reads, creation, replacement and deletion are owner-only. No rating history table. |
| Saved movies | Presentation of ratings plus public MovieLens metadata; same private owner policy. No independent watchlist/list model. |
| Personalized recommendations | Computed from the authorized owner's ratings; no stored results/preferences/feedback. Never expose another profile as an input or response without its supported capability. |
| Group invitations | `group_invitations.user_id` PK/FK, hashed random token and expiry. Only that profile's owner may issue/replace/revoke; possessing a token is not ownership. |
| `/recommendations/group` | Ephemeral aggregation of 2-5 profiles using each other's explicit expiring invitations. No group/member/role/status tables or persistent shared resources. Capability grants aggregate computation only, not private-rating reads, writes or administrative actions. |
| Profile/account settings | Identity/username mapping exists; no settings model or account-settings routes. No new mutation API in this prompt. Legacy credential/operator tools stay separate. |

There are no public/private flags on personal records. Client `visibility`,
`role`, `owner_id`, emails and usernames cannot create permissions. Persisted
groups, member/viewer/admin roles, membership removal and private shared objects
need a future reviewed model; do not fabricate them. The dependent Prompt 15 PR
implements the existing invitation capabilities as described below.

## Owner interfaces

`app/resource_authorization.py` exposes `require_profile_owner`, `read_ratings`,
`put_rating` and `delete_rating`, using the caller's existing SQLAlchemy Session.
Every operation validates the principal type and rechecks the current subject/ID
binding through a joined `users`/`user_identities` EXISTS predicate. No second
identity store, JWT check, provider fetch, cache or email lookup is introduced.
Types alone cannot prove authentication: never construct/deserialise the principal
from request input or let clients override the dependency.

Personal SQL predicates require both requested owner == principal numeric ID and
the current database UUID binding. Reads are scoped before retrieving private
columns; an outer join distinguishes an authorized empty page from an unbound
caller. Pages accept bounded `after`/`limit`. The same read supports saved-movie
metadata composition and bounded personalized input, never public profile access.

Creation uses INSERT ... SELECT from the bound User row; clients cannot assign
the owner. The existing native conflict insert updates only `rating`, repeating
the binding/owner predicates on conflict. Deletion repeats them in its DELETE.
Existing movie FKs and rating constraints remain; quota serialization is reused.
No arbitrary JSON fields are applied to ORM objects. Existing request parsing,
rate/admission limits, catalog validation and response shaping still belong in
future routes; this is an authorization foundation, not a replacement API.

## Transactions, failures and activation

Compose the principal dependency with a short caller-owned `Session.begin()`;
perform checks and resource work there, committing before sending success. Helpers
suppress autoflush and never commit/rollback/close or flush unrelated ORM changes.
`require_profile_owner` is a check at its statement snapshot, not a lasting write
capability: never follow it with an unscoped mutation. Atomic mutation predicates
recheck binding even after the initial guard/quota step. Tests revoke a link
between those steps and require rejection without a rating write.

PostgreSQL statement snapshots permit an already-admitted concurrent operation
to finish while a revocation commits; no immediate revocation guarantee is made.
See [PostgreSQL isolation](https://www.postgresql.org/docs/17/transaction-iso.html#XACT-READ-COMMITTED)
and [scoped conflict updates](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert).
SQLite/PostgreSQL locks, timeouts and transaction errors must fail closed. Shared
transaction ownership is essential; returning a preauthorized ORM object for a
later unscoped write is unsupported. Concurrent upserts retain owner in the PK.

Unauthorized and absent private resources share generic **404 Resource unavailable**
with `Cache-Control: no-store`; storage errors become generic **503 Resource service
unavailable** with no-store/Retry-After. Roll back on failure; never retry unscoped
or fall back to legacy auth. Authentication retains Prompt 14's generic 401/503.
Helpers log no SQL, tokens, email or IDs; platform logging must exclude sensitive
request fields and exception locals. Successful future handlers must retain no-store.

Offline SQLite/PostgreSQL and test-only FastAPI routes establish these application
contracts, not hosted acceptance. Activation still needs provider MFA-factor
completeness, later frontend/provisioning/integration, email/recovery/MFA acceptance,
full NIST assessment, the original 16-stage audit and approved release/rollback.
Prompt 12's `unproven` callback and Prompt 13's native current-email behavior are
unchanged. No hosted writes, migration, deployment or Prompt 16 work is authorized.

## Existing group-capability interfaces (dependent Prompt 15 PR)

`app/group_authorization.py` reuses the same principal/binding predicates and
error handling, existing `GroupInvitation` table, token format/hash/lifetime,
database clock, workload limits and recommendation-combination service:

- `issue_invitation(session, principal, user_id)` derives the owner from the bound
  User row with INSERT ... SELECT; replacement repeats the binding/owner predicate
  and changes only the hash/expiry. No client chooses token, owner, role or expiry.
  Return the secret privately to its owner; never log or persist it in plaintext.
- `revoke_invitation(...)` is an owner/binding-scoped DELETE. Neither a group
  participant nor a capability holder may issue/revoke for another profile.
- `combined_group_profile(session, principal, user_ids, invitations)` requires
  2-5 distinct IDs, including the caller, and exactly one valid capability for
  every other participant. SQL joins require existing users, current caller
  binding, matching per-owner token hashes and database-clock expiry **before**
  reading ratings. Unknown/missing/revoked/replaced grants deny the whole request;
  stale ORM grants or membership/role assertions cannot substitute.

The internal computation is bounded by existing per-profile/group limits and
returns only combined recommendation input. Do not expose individual or combined
profiles over HTTP; use the existing recommendation service/response schema.
The helper rechecks expiry after reading. Revocation committed before its scoped
SELECT denies; revocation racing an admitted SELECT has the same statement-snapshot
limitation as owner reads. There is no persistent membership or immediate
revocation promise. An invitation authorizes this computation only; it is never
a login credential or a grant to read/write another profile or administer roles.
Future routes must preserve owner admission/rate limits and transaction ownership.

Offline tests cover rotated/deleted/expired grants, account substitution, forged
roles, token-to-owner mismatch, stale ORM state, caller-link removal, expiry and
revocation races, bounded computation, owner-only control and redacted outages.
Real membership status/admin policies remain unsupported until a reviewed schema
exists. No hosted email, user, grant, database or configuration is changed by tests.
