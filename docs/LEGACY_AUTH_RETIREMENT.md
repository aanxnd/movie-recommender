# Legacy authentication retirement preparation (Prompt 22/26)

Starting main: `4f556c4ab239359ebd09bd8fca3f36ff158c3a99`; Prompts 1–21 merged.
This inventory precedes cleanup decisions. Production behavior remains unchanged.
The fixed roadmap/full audit remain owner-maintained. No Prompt 23/24 implementation.

## Dependency inventory and disposition

| Component / evidence | Classification | Disposition |
|---|---|---|
| `app/security.py`: `issue_credential`, `authenticate`, `require_owner`; used by `app/main.py` | Retire at cutover | Keep all live credential generation/verification and ownership checks. |
| `TOKEN_PATTERN`, `token_hash`, owner/invitation lifetimes | Retain shared capability primitives; retire owner-auth usage at cutover | Opaque 256-bit URL-safe tokens, 43 characters; SHA-256 stores random-token digests, not human passwords. Dormant `group_authorization.py` still needs invitation hashing/pattern/lifetime; never delete the module wholesale. No legacy JWT signing secret or password hasher exists here. |
| `POST /users` → capacity admission → `database.create_user` → `issue_credential` | Retire at cutover | Live registration/profile creation. Database assigns numeric IDs; there is no username/password signup. |
| `GET /users/me`, `/users/{id}`, ratings/details/lookup/write and personal recommendations | Retire at cutover | Live restoration and personal access. Keep legacy header validation, token expiry and owner binding. |
| Group-invitation issue/revoke, `authorize_group`, `/recommendations/group` | Retain shared behavior; retire legacy credential boundary at cutover | Owner bearer plus short-lived peer capabilities. Current groups are request-time combinations, not a persistent group/member table. |
| `app/artwork.py` personal Fanart-key admission; `FanartKeySettings.jsx` | Retain; replace owner-auth boundary at cutover | Ordinary artwork is public; optional personal-key requests authenticate the profile. Keep that guard, scoped transient keys/caches and privacy tests. No persistent key store is introduced. |
| `app/models.py`: `users`, `profile_credentials`, `user_ratings`, `group_invitations` | Retain | Preserve numeric PKs, token digests/expiry, rating and invitation FKs. No password/email column or independent watchlist table currently exists. Do not invent one or drop future/shared data. |
| `UserIdentity`, schema-3 migration, existing-link resolver | Retain / dormant replacement | Nullable unique Supabase UUID, numeric-user PK/FK, case-insensitive unique profile username. No automatic population/linking. |
| `app/manage.py recover-profile` | Retire at cutover; operator investigation required first | Existing explicit operator recovery for unclaimed/expired legacy profiles, with private output file. Not a Supabase/MFA reset. Do not execute, remove, broaden or infer operator ownership proof. |
| `app/database.py` creation, rating/profile queries, quotas, transactions, SQLite/PostgreSQL support | Retain | Shared application data, admission and test/operator dependencies; not disposable auth plumbing. |
| MovieLens reference users, movie IDs and recommender math | Retain | Read-only reference identity is distinct from application users. Never merge/reference-link numeric IDs. |
| `frontend/src/main.jsx` → `App.jsx` → `api.js` / `UserPanel.jsx` | Retire legacy boundary at cutover; retain browsing/shared UI | Sole live React entry and transport. Create profile, restore `ID:credential`, ratings, recommendations and invitations remain operational. |
| `identity.js`: `parseIdentity`, read/save/same identity, `parseRecoveryCode`; `movelle.identity.v1` | Retire at cutover | Active persistence and cross-tab request fencing. The private recovery code is a reusable legacy bearer, not an MFA recovery code. Never auto-clear/migrate it. |
| `identity.js clearIdentity` | Requires investigation / retain | Export has tests but no in-repository production caller. Not proof that external/manual consumers are absent; keep the tested explicit utility and do not wire it to startup. |
| `supabase-client`, session/context/actions, authenticated transport, signup/password/email/TOTP/recovery screens | Dormant replacement | Shared SDK-owned `movelle.signup-confirmation` namespace; no production mount, extra token store or dual-auth fallback. Keep all security and cancellation tests. |
| `supabase_jwt`, email/policy, identity/auth principal, resource/group authorization | Dormant replacement | Exact ES256 issuer/audience/signature/UUID/session/AAL evidence, fresh provider email/factors, existing numeric mapping and ownership. Do not attach to live routes. |
| `DATABASE_URL`, `APP_ENV`, CORS/proxy and quota configuration | Retain | Shared application/deployment configuration; not legacy signing keys. Never remove or print secret values. |
| `VITE_API_BASE_URL` versus dormant public Supabase/origin configuration | Retain / dormant replacement | Separate API transport and explicit SDK bootstrap; environment values must not activate authentication. |
| Existing tests/fixtures, redaction, operator management, migrations and manual release workflow | Retain | Security/compatibility evidence; synthetic credentials are test inputs, not stale runtime secrets. |

**Safe to remove now: none established. No legacy code, endpoint, credential,
environment variable, test or database object was removed.** No dead helper was
deleted simply because Supabase exists. No active username/password login, password
reset, legacy JWT, cookie session or password database was found to clean up.
Only tracked source/configuration was inspected; actual hosted settings/secret values
were not read. No secret rotation, storage migration or credential revocation occurred.

## Current and future trust boundaries

Live: browser private profile credential → explicit legacy API bearer → stored
digest/expiry → numeric owner → ratings/group authorization. Anonymous movie search,
catalogue/popularity and genre recommendations require no profile credential.
`UserPanel` creates/restores profiles; it never authenticates a Supabase identity.
`recover-profile` is operator-only legacy tooling, never a public MFA bypass.

Future: explicit shared Supabase session → FastAPI signature/current-email/AAL policy
→ already-linked numeric user → separate resource authorization. A JWT's email,
username, metadata or user-supplied numeric ID cannot establish a link. Neither
token type falls back to the other. A valid Supabase JWT is rejected by today's live
legacy header/token contract; the dormant verifier rejects opaque credentials.
Rejected credentials must never cause user creation, linkage or data mutation.

## Data and existing-user gates

The only live application-ID creation path is `POST /users` calling
`database.create_user`; other calls are isolated tests. Operator recovery issues a
credential for an existing numeric row, not a new user. Database sequences allocate
IDs; no frontend claim owns that allocation. Existing schema migrations are additive.
Prompt 22 adds no migration and executes none against hosted databases.

The existing operator recovery command checks numeric-row existence/credential expiry,
not Supabase linkage. Preserve today's tool here, but do not use it for new Supabase
profiles. Before provisioning becomes live, explicitly retire/gate legacy credential
issuance for those profiles in the owner-approved cutover. Dormant provisioning tests
must cover this boundary; an operator command is not automatic account ownership proof.

Prompt 23 must provision clean new accounts transactionally from a server-verified
Supabase subject, preserving numeric allocation, UUID/user uniqueness, username
constraints and FKs. It must not call the public legacy creation flow as ownership
proof, issue legacy credentials for new Supabase accounts, or match existing accounts
by email, username or submitted bearer/numeric IDs. No provisioning writer exists yet.

No legacy migration/claiming policy is approved. Existing data must stay intact;
retiring legacy access later still requires an owner-approved existing-user access/
data-disposition decision. This is a cutover blocker, not permission to abandon old
users or silently link them. Preserve all credential digests and relationships.
Future watchlist/group/profile features must preserve their ownership constraints too.

## Deferred sequence — NOT APPROVED FOR EXECUTION

1. Complete Prompt 23's authoritative provisioning and explicit identity binding.
2. Prompt 24 rehearses anonymous access, legacy/new token rejection in the wrong
   boundary, ownership, numeric/data preservation, concurrency, secret redaction,
   signup/email/password/MFA limitations and secure rollback in isolated staging.
3. Resolve every [cutover gate](AUTH_CUTOVER_READINESS.md), including the existing-user
   decision, hosted acceptance, full NIST assessment and original professional audit.
4. Prompt 26 owner approval selects exact immutable backend/frontend releases and
   production configuration. Replace the auth boundary coherently, never by fallback.
5. Retire active legacy routes/credential UI/operator paths only in that reviewed
   cutover. No startup storage clearing, mass revocation or destructive SQL is implied.
6. Any later credential/table retention or deletion needs a separate approved data
   policy. Application rollback requires a secure schema-compatible release; do not
   restore legacy fallback after Supabase activation or downgrade/drop identity data.

Azure release remains manual `workflow_dispatch` with production approval; no release
workflow is invoked. Vercel PR checks may build previews, not production activation.
Repository schema 3 does not prove the deployed schema/version. The existing
[schema-2/3 deployment and rollback gates](DEPLOYMENT.md) remain required.
# Prompt 23 issuance guard

New Supabase-owned numeric profiles never receive opaque legacy credentials.
The shared `security.issue_credential` primitive locks the user row and denies
issuance whenever its identity has a non-null Supabase subject. Operator
`recover-profile` uses this primitive; denial rolls back expired-credential and
invitation changes. Historical legacy registration/recovery stays available.
Authentication of an already-existing credential is unchanged: this is not a
session revocation or historical account-migration operation. No direct SQL
issuance, hosted mutation or automatic linking is authorized.

