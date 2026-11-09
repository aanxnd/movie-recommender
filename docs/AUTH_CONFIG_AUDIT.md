# Authentication configuration and policy audit

Prompt 3D.2, reviewed 2026-11-09 against `main` at
`d751f0e68f0f290a2774c1f5618a9347b3a3ee3e` (PR #29).
Documentation/design only; all Supabase components remain dormant.

## Evidence and hosted findings

Labels: **HOSTED** = directly observed on this project during this audit;
**DOC** = official provider documentation; **SOURCE** = official implementation,
not a hosted-version guarantee; **REPO** = inspected repository;
**REPORTED** = owner/prior validation report; **INFERRED** = conclusion requiring
validation; **UNKNOWN** = unavailable evidence. Confidence follows that boundary.
No connected Supabase tool or working browser/dashboard session was available.
No authenticated provider request or account-state experiment was performed.

| Question | Finding and confidence |
|---|---|
| Public signing metadata | HOSTED: `/auth/v1/.well-known/jwks.json` on the owner's project origin returned EC / ES256 / P-256, signature use, verify operation. This establishes no email/session configuration. No key material is recorded here. |
| Confirm Email currently enabled? | UNKNOWN. Its intended enabled state in the contract is not hosted evidence. |
| Historically disabled / implicit confirmation? | UNKNOWN; present settings cannot establish past settings. |
| Administrative confirmation or provisioning? | UNKNOWN; no account inventory or retained event history was available. No records can be certified as genuinely challenged by this audit. |
| Email delivery | REPORTED: disposable signup, verification and password login passed; Gmail invitation delivery reached Outlook junk. Not a production deliverability result or evidence for every account. |
| Redirect restrictions | REPORTED earlier Site URL `http://localhost:3000`; current Site URL, allowlist, templates and intended callback paths UNKNOWN. |
| Unverified Supabase credentials | DOC: Confirm Email enabled prevents initial email/password sign-in until confirmation; disabling it implicitly confirms. Current hosted behavior UNKNOWN; no signup/sign-in probe made. |
| Unverified Movelle access | REPO: `POST /users` issues anonymous legacy profile credentials without email; movie catalog is public; protected profile/rating/group routes use legacy credentials. The new email policy is not active. Live deployed behavior was not probed. |
| Sessions, bans, factor state and JWT lifetime | UNKNOWN on hosted project. REPORTED TOTP enabled / ten-factor ceiling; neither proves current enforcement. |

The [confirmation setting](https://supabase.com/docs/guides/auth/general-configuration)
can imply confirmation; [admin updates](https://supabase.com/docs/reference/javascript/auth-admin-updateuserbyid)
can force it. The [user object](https://supabase.com/docs/guides/auth/users)
distinguishes email confirmation from phone confirmation and editable metadata.
Consequently, neither a populated `email_confirmed_at` nor delivery alone proves
that the current address completed a mailbox challenge.

## Final owner policy

- Every Supabase-backed account needs genuine verified email before protected
  access. Uncertain provisioning/verification provenance requires a genuine email
  challenge before activation. No client flag, metadata or email string is proof.
- Every protected request needs live Supabase account/session evidence; failure or
  unavailability denies access. Use the strongest feasible Free-plan checks and
  disclose measured revocation limits; no immediate-revocation promise.
- Ordinary authenticated browsing, ratings and recommendations need AAL1 or
  stronger, verified email and an active session. Security-sensitive account/MFA
  changes need recent AAL2 with server enforcement. Independent backup TOTP remains
  the recovery method; no email-only bypass or native recovery-code requirement.

These requirements are final; the five-minute freshness recommendation below,
bootstrap exception and provider enforcement design still need review. They do
not activate routes or authorize hosted changes. Supabase Free, SPA sessions,
Neon data/numeric IDs, profile-only usernames and $0 additional spending remain.
NIST alignment is evidence and gaps, not a compliance assertion.

## Read-only owner checklist and verification provenance

In the existing `movelle-auth-dev` dashboard, inspect without saving/toggling:

1. **Authentication -> Sign In / Providers -> Email**: record Confirm Email and
   secure email-change state, observation time and project name. Under general
   sign-up settings also record Allow new users and anonymous sign-in state.
   Do not enable signup. Current values do not prove their historical values.
2. **Authentication -> URL Configuration**: privately inventory Site URL and each
   Redirect URL. Compare exact scheme/host/port/path with intended development and
   eventual production callbacks. Flag unrelated origins, broad preview wildcards
   and localhost as a production default. There is no approved callback route yet;
   do not invent one or change settings. See [redirect rules](https://supabase.com/docs/guides/auth/redirect-urls).
3. **Authentication -> Email Templates / Custom SMTP**: inspect confirmation/reset/
   email-change link destinations and sender configuration without revealing SMTP
   credentials or token-bearing template previews. Review existing delivered mail
   headers privately for SPF/DKIM/DMARC and junk placement; send nothing new.
   Gmail sender limits, policy suitability, spam placement and deliverability stay
   open launch gates even if development delivery succeeded.
4. **Authentication -> Users** and **Configuration -> Audit Logs**, plus retained operator/change
   records: privately correlate provisioning method, admin confirmation, signup/
   invitation verification and address changes for each account. Record whether
   evidence covers the full period since creation and who could set confirmation.
   [Auth audit logs](https://supabase.com/docs/guides/auth/audit-logs) document
   verification events; database storage is optional. Inspect existing records
   only; do not enable storage. Review configuration-change history where available;
   absence of old
   logs is UNKNOWN, not proof that implicit/admin confirmation never happened.
   Do not export addresses, IDs, JWTs or verification links into this repository.
5. Produce a sanitized count of proven/unproven/unverified records and missing
   history. If no reliable account-level challenge trail exists, classify those
   accounts as unproven. No numeric inventory can be supplied from this audit.
6. **Authentication -> Sessions / Multi-Factor / Rate Limits**: record current JWT
   lifetime, applicable limits, factor settings and any account-disable policy.
   Do not refresh sessions, test sign-out, send challenges or change values.

Before activation, unproven, implicitly/admin-confirmed, missing-confirmation or
address-changed records require a separately authorized genuine mailbox challenge.
Future server evidence must bind the challenge completion to the subject **and
current address**, invalidate it on address change, and protect the evidence from
client/admin-marker substitution. A new timestamp alone cannot repair provenance.
Do not link legacy profiles by matching email. The existing email reader omits the
address from its result, so provenance composition also needs a reviewed interface.

## Live account/session evidence

| Event / check | Documented meaning and remaining gap |
|---|---|
| Local JWT verification | Signature/issuer/audience/expiry prove issued claims, not current account/session state. Remaining stateless acceptance is `max(0, exp - now)` plus verifier clock tolerance; hosted lifetime is unknown. |
| Fresh `GET /auth/v1/user` | [getUser](https://supabase.com/docs/reference/javascript/auth-getuser) obtains server user data; [server guidance](https://supabase.com/docs/guides/auth/server-side/advanced-guide) recommends it for detecting server-ended sessions. No admin key needed. It does not prove a genuine mailbox challenge or application suspension state. |
| Hard deletion | [User management](https://supabase.com/docs/guides/auth/managing-user-data) describes removal of user/session rows and refresh capability; already issued JWTs remain cryptographically valid until expiry. A fresh state check must reject missing records. |
| Ban / disabled | Same guidance says bans block sign-in without revoking existing sessions. SOURCE below rejects banned users on authenticated API calls; hosted version/behavior UNKNOWN. Explicitly deny active ban, soft deletion, or any future Movelle suspension, not just failed refresh. No local suspension model exists today. |
| Global / local / others sign-out | [Sign-out scopes](https://supabase.com/docs/reference/javascript/auth-signout) invalidate all/current/other sessions respectively when server revocation succeeds. Local browser clearing alone is not server revocation. Unexpired JWTs need live checks. |
| Session record | [Sessions](https://supabase.com/docs/guides/auth/sessions) connects signed `session_id` to `auth.sessions`; absent row rejects. Row existence alone does not enforce every timeout; cleanup can lag expiry by 24 hours. |
| Refresh | A fresh access token is not fresh MFA. Revoked/deleted sessions cannot legitimately refresh; refresh-token rotation/reuse rules are separate from access-token acceptance. Free does not include paid session lifetime/inactivity/single-session controls. |
| Outage, 429, inconsistent evidence | No stale allow, JWT-only fallback or legacy fallback. Return generic unavailable, with no provider payload/PII; retain fail-closed behavior even when this makes the application unavailable. |

Corroborating SOURCE pinned at Auth commit
[`35307ce6`](https://github.com/supabase/auth/tree/35307ce6c1ca59016fd820f1d77d9b6201dc2e15):
[`auth.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/api/auth.go)
loads the subject and, **if present and nonzero**, session UUID; missing session
rows and bans fail. This is not a hosted guarantee, nor a documented promise of
every session expiry/ownership check. Require a nonzero signed session UUID locally.

**Existing component insufficient:** `ProviderEmailPolicy` returns only subject,
confirmation and observation timestamps; it neither requires/exposes session ID,
checks provenance, nor establishes session ownership, current session AAL or every
disable rule. `SupabaseTokenVerifier.verify()` currently returns only a UUID.
Do not reinterpret either result as a complete access decision.

Future request boundary, in order:

1. Verify ES256 with pinned project/issuer/audience and bounded JWKS; expose a typed,
   immutable verified subject/session UUID/expiry/AAL and optional parsed AMR result. Validate types,
   reject zero IDs/malformed claims; never accept client-decoded evidence objects.
2. Fetch fresh same-project user evidence with user Bearer JWT + public publishable
   `apikey`, bind returned ID, confirmation and current address to server provenance.
3. Require positive current user/session binding and non-disabled state. Public
   lookup is the least-privileged candidate, **conditional on hosted acceptance
   tests** for deletion, ban, sign-out, session ownership, expiry and downgrade.
   If it cannot establish a required property, stop activation or use the narrowly
   scoped read-only adapter below; do not silently accept JWT-only evidence.
4. Resolve the existing Neon link; enforce action AAL/freshness and resource
   ownership/group permissions independently. No auto-creation/linking, no numeric
   ID supplied by the client as caller identity, no mixed legacy fallback.

Use no cross-request positive state cache. Malformed/denied identity gets one
generic 401; authenticated policy denial gets generic 403; provider ambiguity,
timeout/429/5xx gets generic 503. No-store responses; no tokens, addresses, IDs or
provider bodies in logs. Bound concurrency and body sizes; propose a three-second
**total** evidence budget (existing socket timeout is not a total deadline), no
retry storm, and fail closed on budget exhaustion. Recheck before sensitive writes.

Residual acceptance after a provider change is propagation delay + time from last
successful observation to use; neither has a measured hosted bound here. Desired
cache TTL is **0 seconds**, not a zero-revocation claim. Provider reads and Neon
writes are not atomic. Measure p95/p99 and worst observed delays before activation;
reject the launch if the owner cannot accept that window.

### Conditional server-only read-only adapter (proposal, not authorized setup)

**Prompt 11 decision hold:** [owner-reported hosted inspection](AUTH_DB_ACCESS_INSPECTION.md)
rejects direct Auth grants (no grantable schema USAGE). The historical direct-grant
and narrow definer-owner ideas below are superseded by a review-only postgres-owned
private capability proposal, conditional on existing RLS access and owner acceptance.
No setup is approved; omit email fields and defer `aal` for a state-only reader.

If hosted public validation cannot supply explicit session binding/current AAL or
ban/deletion status, propose one parameterized query joining exactly
`auth.users.id = auth.sessions.user_id`, constrained by **both** verified subject
and verified session UUID. Require one row, `deleted_at IS NULL`, no future
`banned_until`, unexpired `not_after` if set, and known current session `aal`.
For sensitive actions require both signed and live AAL2; reject disagreement.

Minimum proposed runtime privileges: CONNECT on the Supabase database, USAGE on
`auth`, column SELECT on `auth.users(id, banned_until, deleted_at)` and
`auth.sessions(id, user_id, not_after, aal)` only. No passwords, refresh tokens,
factor secrets, DML, schema CREATE, role administration, BYPASSRLS or Auth admin
API privileges. Column names are SOURCE-supported in
[`user.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/models/user.go)
and [`sessions.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/models/sessions.go),
not a stable hosted-schema guarantee. Inspect hosted columns, grants and RLS first;
stop if this isolation is unsupported. Do not grant broad managed-schema access.
Audit effective/inherited/PUBLIC grants as well as explicit grants. Compromise of
this role could expose IDs and state across accounts despite parameterized queries;
it must not inherit broader roles or allow arbitrary query input from clients.

Use a dedicated backend-only role/secret over verified TLS, a bounded pool and
statement timeout, read-only transactions and fixed parameterized SQL; no public
Data API exposure. No browser/env `VITE_*`, logs, CI artifacts or Neon connection
may receive this credential. Return only a typed decision/observation, no row JSON.
Every request still needs fresh provider evidence and genuine email provenance.

An RPC alternative needs separate review: a dedicated NOLOGIN function owner with
only those column grants, fixed qualified tables/search path, no dynamic SQL,
EXECUTE restricted to a dedicated backend role and revoked from PUBLIC, anon and
authenticated. Its definer/argument/enumeration/exposure risks exceed a private
read-only query; do not use generic service-role access to make it convenient.
[Admin getUserById](https://supabase.com/docs/reference/javascript/auth-admin-getuserbyid)
requires broad server privilege and does not establish the caller's session row;
it is not the minimum solution. Read-only state cannot itself revoke sessions.

Budget: public path adds at least one Auth round trip per protected request;
adapter adds a database round trip/pool load. Latency is unmeasured, not a claimed
millisecond figure. Keep within existing Free quotas/connections/egress, measure
load, and fail closed/throttle rather than purchase capacity. [Rate-limit docs](https://supabase.com/docs/guides/auth/rate-limits)
list `/auth/v1/user` among limited paths; exact GET applicability/hosted quotas must
be validated. Shared backend egress can aggregate users' quota. Do not spoof
forwarded IPs or add a privileged key to evade limits. Outages/pausing are an
availability cost of the owner's live-check policy.

## MFA assurance and recent step-up

[Signed claims](https://supabase.com/docs/guides/auth/jwt-fields) define `aal1`,
`aal2` and `amr` method/timestamp entries; neither `iat` nor a refreshed JWT measures
TOTP recency. Current verified-factor enrollment is distinct from authentication
history. A browser AAL response or editable profile field is never server proof.
[Enroll/challenge/verify](https://supabase.com/docs/guides/auth/auth-mfa/totp)
first creates an unverified factor, then verifies a provider challenge and returns
an elevated session; use newly issued tokens and revalidate server-side.
[Verified-factor removal](https://supabase.com/docs/reference/javascript/auth-mfa-unenroll)
requires AAL2. [MFA guidance](https://supabase.com/docs/guides/auth/auth-mfa) warns
that removal's token downgrade waits for refresh; old signed AAL2 can be stale.
Never rely on the browser voluntarily refreshing or hiding a button.

Recommendation: **five minutes maximum** from successful TOTP verification to the
sensitive action, checked with server time; reject future/missing/invalid evidence.
SOURCE `sessions.go` derives AMR timestamps from method `updated_at`;
[`amr.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/models/amr.go)
updates that event on authentication. Hosted repeated-challenge/refresh/removal
semantics remain untested: do not ship a bare AMR-age predicate as sufficient.

Defensible default for future Movelle-owned sensitive actions: create a server-
tracked pending action bound to verified subject/session, action, target and nonce;
use supported [challengeAndVerify](https://supabase.com/docs/reference/javascript/auth-mfa-challengeandverify)
with the user's current verified TOTP factor, validate the resulting JWT and fresh
provider state, then record server completion time. Mint/consume a single-use
server-held action grant within five minutes and recheck live state at execution.
Do not accept a client-reported successful challenge, reuse a grant for another
action/session, log codes, or treat a recovery email as MFA. Replay/race/downgrade
tests and an exact protocol review are prerequisites, not implemented guarantees.

**Provider-owned operation blocker:** SPA users possess their user JWT/public key
and can call [updateUser](https://supabase.com/docs/reference/javascript/auth-updateuser)
or MFA APIs directly. A backend grant does not govern those calls. SOURCE
[`user.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/api/user.go)
requires AAL2 for password/email changes when MFA is enabled; SOURCE
[`mfa.go`](https://github.com/supabase/auth/blob/35307ce6c1ca59016fd820f1d77d9b6201dc2e15/internal/api/mfa.go)
checks AAL2 for additional factors/verified removal, without a five-minute TOTP
rule in those checks. Password reauthentication's separate nonce/session-age
behavior is not recent TOTP. No documented Free setting establishing our exact
recent-AAL2 rule for every direct sensitive API was found. [Auth hooks](https://supabase.com/docs/guides/auth/auth-hooks)
are not a universal per-operation guard; MFA/password attempt hooks are paid and
unauthorized. A custom JWT hook or server proxy alone does not close direct calls.
This remains a launch blocker requiring supported provider enforcement evidence
or an explicitly reviewed architecture/policy decision, not a silent exception.

With optional MFA, a user without any factor cannot yet satisfy recent AAL2.
First-factor bootstrap needs explicit approval: allow only enrollment/challenge
from a verified/live AAL1 session, with no other sensitive action until successful
fresh AAL2. Existing-factor changes must require the existing authenticator first.
This proposed narrow exception is not approved by calling MFA optional.
Backup recovery: password + surviving independent factor -> fresh AAL2 -> verify
replacement primary -> remove lost factor, retaining the independent backup.
Loss of every factor can lock out the account; no email/admin automatic bypass.

## Protected-action matrix (future contract, not current route behavior)

All rows require authenticated Supabase identity, **genuine current-email proof**
and **live account/session checks on each request**. No unknown evidence passes.
`R2` = recent AAL2 with server enforcement (five-minute window proposed above).
Ordinary features accept AAL1 or AAL2; MFA enrollment alone does not impose AAL2
on them under the owner's finalized policy. This risk must be clear to opt-in users.

| Action | AAL / step-up | Independent authorization | Remaining gate |
|---|---|---|---|
| Authenticated movie browsing / recommendations | AAL1+ / no | Own profile; group consent where applicable | Route cutover; public catalog exception would need explicit decision |
| Create/edit/delete ratings | AAL1+ / no | Resolved profile owns rating | Preserve numeric IDs and transaction checks |
| Profile / username changes | AAL1+ / no, proposed for non-security fields | Self only; database username uniqueness | Classify security-affecting fields separately as R2 |
| Password change/reset completion | R2 / yes | Self; provider-owned credential operation | Direct API freshness; no-factor policy; reset email is not MFA |
| Email change | R2 / yes | Self; challenge new address; protect old-address flow | Direct API freshness; invalidate old provenance |
| First TOTP enrollment | Proposed bootstrap, then fresh AAL2 | Self; provider factor ownership | Owner approval of narrow AAL1 bootstrap exception |
| Additional / backup enrollment | R2 / yes | Self; verify independent new factor | Direct API enforcement; genuine independent access acceptance |
| Factor removal/replacement | R2 / yes | Self; verify replacement before removal | Direct API freshness; live downgrade/revocation tests |
| Backup-TOTP recovery | R2 / yes via surviving factor | Same subject/session; no account reassignment | Lost-all-factors lockout disclosure; hosted acceptance |
| Account deletion | R2 / yes | Self; retention/deletion authorization | Separate server-only deletion design; no admin activation here |
| Group/invitation create/use/revoke | AAL1+ / no for current consent operations | Own profile, valid recipient capabilities and all-member consent | Preserve existing group logic; future privilege/destructive operations need R2 review |
| Administrative/operator actions | R2 / yes for future interactive accounts | Separate explicit operator role and action scope | No automatic operator rights from JWT/link; service workflows need separate design |

Existing public catalog/anonymous credential issuance and legacy authorization
are unchanged; this matrix is not a claim they already enforce verified email.

## Ordered handoff and launch gates

1. Owner completes the read-only checklist and returns sanitized findings, including
   history gaps; approve the freshness duration and bootstrap classification.
2. Small offline PR: typed verified-claims boundary requiring session UUID/AAL,
   parsing AMR when present without treating it as sufficient freshness proof,
   with malformed/spoof/replay tests; preserve the dormant existing API contract.
3. Separate design/PR for genuine email provenance and fresh user/session policy;
   mock deny/outage/429/address-change cases. No marker-only access predicate.
4. If public checks are insufficient, separately review the minimal read-only
   adapter and its privilege model. No setup until explicit approval. Define local
   suspension semantics before claiming to enforce an application-disabled state.
5. Resolve direct provider sensitive-API enforcement, then implement/review recent
   step-up and backup-factor policy in small dormant PRs. Unsupported guarantees
   block this portion; no paid workaround or frontend-only enforcement.
6. Only with separate authorization, disposable hosted acceptance tests establish
   deletion/ban/sign-out/refresh/session binding, repeated TOTP, factor removal,
   direct API bypass behavior, provider limits and measured revocation windows.
7. Route integration/cutover and rollout require later approval, all above evidence,
   Gmail production gates and [schema/release/rollback checks](DEPLOYMENT.md).

Safe next work is offline typed evidence and policy/provenance design, not route
activation. Free quotas/pausing, SPA token theft, cross-service races, unknown
history, stale AAL2, no-factor sensitive actions and direct provider API freshness
remain explicit risks. Native recovery codes remain rejected for initial launch.
This documentation PR changes no code, dependencies, accounts, settings or schema;
it is independently reviewable for merge after CI, and authorizes no deployment.
