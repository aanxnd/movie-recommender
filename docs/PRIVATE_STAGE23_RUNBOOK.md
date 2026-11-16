# Retired private-preview walkthrough — DO NOT EXECUTE

The unselected private bundle is removed under [the cleanup inventory](REPOSITORY_CLEANUP.md).
Use [Oracle preparation](ORACLE_RUNBOOK.md) and [Vercel native preparation](VERCEL_NATIVE_RELEASE.md).
The remaining text is historical review evidence, not current deployment instructions.

November15 owner direction: this preserved runbook is no longer the final owner
acceptance target. See [production readiness](PRODUCTION_LAUNCH_READINESS.md);
private/local infrastructure remains engineering evidence, not release approval.

Review is separate from resource, secret, migration and deployment approval. No
cloud command here was executed. Never use the production release workflow/app/DB.
Prompt24/final audit has not started. Dependency order: **91 → 92 → 93 → 94**.
After each approved squash merge, rebase the child and repeat full-diff size/CI.

## Current evidence and mandatory cost gate

Owner verified November 14, 2026: Azure for Students active, 138.35 credit remaining,
amount due 0, November Container Apps charges **CA$1.50**. Live API min 0/max 3/current 0
replicas; Neon Free 2/10 branches and about 37 MB production storage; Vercel Hobby,
Require Log In/Standard Protection. These observations are not proof of $0 cost.

**STOP before cloud changes:** establish remaining subscription-wide CPU/GiB/request
grants, meters causing charges, logs/network/registry usage, Neon CU/transfer/root
limits and Vercel function/preview usage. Credits/amount due0 do not establish zero
incremental charges. [Azure grants](https://learn.microsoft.com/en-us/azure/container-apps/billing)
are shared, not a per-app hard cap. Proposed0.5CPU/1GiB for4 hours consumes7,200
vCPU-seconds/14,400GiB-seconds, excluding cold starts/requests/other meters. Scale
limits and alerts do not guarantee $0. If unproven, retain loopback testing only.

## Exact targets and credential boundaries

- Existing Neon project `weathered-poetry-89387942`: proposed **schema-only**
  `private-stage23`. Never copy production/pre-redesign-backup personal data.
  Verify empty users/identities/ratings/invitations/credentials. Protected production
  branch remains `br-tiny-bonus-b4ec6f9z`; SQL cannot attest endpoint/branch ownership.
- New database **`movelle_private_stage23`**, runtime LOGIN role of the same name;
  distinct LOGIN **`movelle_private_stage23_migrator`** owns only the new app schema.
  After approval, use SQL on the approved private branch for least-privilege roles;
  [Neon guidance](https://neon.com/docs/manage/roles) distinguishes SQL-created roles
  from Console/API roles with broad managed memberships. No runtime superuser,
  BYPASSRLS, replication, CREATE ROLE/DB or privileged memberships.
- Runtime grants: CONNECT/schema USAGE; schema_version SELECT; required DML on
  users,user_identities,movies,user_ratings,group_invitations,rate_buckets; sequence
  USAGE. No schema CREATE, migration ownership or profile_credentials access. Verify
  actual fresh runtime password login; privileged impersonation is insufficient.
- Proposed new Azure **`movie-recommender-api-private`**, `movie-recommender-rg`.
  Reuse Express environment only if second-app isolation/quotas are supported without
  changing production. Otherwise stop for revised approval; never replace the live
  single-revision app or change environment mode.
- Existing Vercel `movie-recommender`, root `frontend`; proposed source branch
  `private/stage23-owner-test`. Preserve global Root Directory/build/branch tracking.
  Verify owner-only membership/access and no bypass links, shares or preview
  exceptions. Require denial to signed-out AND unrelated signed-in Vercel users.
- Frontend `.vercel.app` origin, private Azure HTTPS origin, branch ID, endpoint
  and protected production/backup endpoint hosts are **TBD/unapproved**. Resolve
  only through separately approved inert allocation if needed; never guess them.
  Count bootstrap usage/cost. Use a stable approved preview origin across rebuilds.

After approval, fill ignored `deploy/private-stage23/targets.reviewed.json` from
the example, including all protected hosts. approved=true requires owner review.
Only exact nonsecret targets belong in it; it is image-pinned/packaged server-side.
Changing targets requires rebuild/review, never a production authentication flag.

| Input | Exact private requirement |
|---|---|
| APP_ENV | `production` in private image |
| MOVELLE_PRIVATE_MODE | `private-stage23`, backend and gateway only |
| MOVELLE_PRIVATE_TARGETS_FILE | Backend `/backend/private-targets.json`; local packaging path to reviewed JSON |
| CORS_ALLOWED_ORIGINS | One approved frontend HTTPS origin, no trailing slash |
| MOVELLE_PRIVATE_DATABASE_URL | Server-only; approved endpoint:5432, database/role `movelle_private_stage23`; query `sslmode=verify-full&sslrootcert=system&channel_binding=require` |
| MOVELLE_PRIVATE_MIGRATION_URL | One-off only; identical target/TLS, role `movelle_private_stage23_migrator`; never set on running API/Vercel |
| MOVELLE_PRIVATE_GATE_SECRET | Privately generated32-byte base64url (43 chars, no padding), same Azure/Vercel server value; never VITE/client/URL/CLI argument/log |
| MOVELLE_PRIVATE_PUBLISHABLE_KEY | Existing dev publishable key, Azure; never admin/service-role |
| VITE_PRIVATE_PUBLISHABLE_KEY | Public dev SDK input for local private packaging only |
| VERCEL_ENV | Platform-provided `preview`; gateway refuses production/unset |
| Reference/port | Image-pinned repository Small `/backend/reference`; PORT8000, one worker |

No ambient DATABASE_URL, libpq/proxy overrides or production VITE values are
fallbacks. Keep secrets deployment-scoped, outside production and untrusted PRs.

## Execution sequence — AFTER separate authorization

1. Record approved SHA, target file, private DB role/grants, artifact digests,
   expected cost/usage window, isolation/access and secret handling. Verify private
   branch capacity and empty personal tables; do not copy production data.
2. Clean checkout: prepare bundled Small with
   `python scripts/prepare_movielens.py --source data --output data/prepared/latest-small-v1`.
   Verify/reuse an existing destination; never overwrite mapped data. Privately
   load reviewed nonsecret targets and the public SDK build input.
3. From frontend: `npm ci`, then
   `npm run prepare:private -- ../.pytest-tmp/private-stage23-bundle`.
   This refuses existing/unsafe paths and never invokes cloud CLIs/copies env files.
   Inspect public assets for absence of gate/DB/backend target and source maps.
4. From root:
   `docker build -f deploy/private-stage23/Dockerfile -t movelle-private:reviewed .`.
   Only locked dependencies, app, Small and nonsecret targets enter the context.
   Test/record immutable digest. Existing GHCR publication needs separate approval;
   no new registry/service and no mutable/latest deployment tag.
5. After migration approval, privately load dedicated runtime configuration plus
   migration URL into an isolated one-off container, then run
   `python -m app.private_manage migrate` and `python -m app.private_manage check`.
   The wrapper pins identical endpoint/database/TLS and the separate migrator role.
   No automatic server DDL, raw URL arguments, generic production manage command,
   linking, sequence reset or data migration. Apply runtime DML grants; verify fresh
   runtime login/schema3/empty personal tables and forbidden DDL/legacy credentials.
6. Review/fill `containerapp.example.yaml` privately with approved environment ID,
   image digest and secret inputs. It proposes a **new private app**, single revision,
   0.5CPU/1GiB, min0/max1, TLS ingress and TCP probes; verify Express support first.
   No unauthenticated HTTP probe bypass. Startup checks schema3 and registers public
   movie IDs; no migration occurs. Never dispatch the production workflow.
7. After approval, link only the isolated bundle to the existing Vercel project.
   [Root Directory applies to CLI](https://vercel.com/docs/builds/configure-a-build):
   upload the bundle root containing `frontend`, preserving global settings.
   Its vercel.json selects framework/build/output only for that deployment. Use an
   explicit **Preview** target, never `--prod`, promotion or new project creation.
   Verify actual CLI/root/rewrite behavior before exposure; do not change global
   settings to work around mismatch. Gateway needs private server env and approved
   Host; other aliases fail. Standard Protection excludes custom production domains.
8. Separately approve adding exactly frontend origin plus `/` to Supabase redirects.
   Keep Site URL, SMTP, provider project and factors unchanged. Native PKCE callback
   stays root-only/scrubbed; no wildcard/next. No hosted change is implied here.
9. Verify signed-out/unrelated-user denial on every preview/function URL. Direct
   Azure HTTP must deny403 even with JWT unless gate AND exact Host/Origin match.
   Confirm no gate in logs/responses; TLS/channel binding, rewritten query/path,
   25s timeout, body limits, rate limits and401/403/404/429/503 behavior. No legacy API.
10. **Stop before auth mutations:** existing campaign is10/10 conservative email
    reservations. New signup/recovery/enrollment needs a separately approved budget
    and safe account/authenticator prerequisites. C's seed was not retained; no MFA
    bypass, factor removal or account deletion to facilitate testing. Future approved
    owner tests must cover movies/profile/ratings/recommendations, refresh/logout,
    account switches, MFA and cross-account/group denial.
11. End the approved window: stop only new private app, verify zero replicas and
    delayed usage; gate private preview access. Revoke only newly approved secrets
    with authorization. Retain private schema/data; rollback only to reviewed
    native-only private digest, never legacy fallback, drops or production restore.

## Verification boundary and remaining decisions

Offline tests establish target/gate denial, native policy/ownership on synthetic
local models, bounded gateway, asset separation and image refusal. Eleven existing
Chrome/PG fictional-provider journeys are regressions, not hosted proof. Prior real
Supabase acceptance is separate. Hosted TLS/role grants, Vercel rewrite/root/owner
protection, Express deployment, logging/egress and cost remain unverified.

Before execution approve: merges/rebased SHAs, demonstrated $0 window, exact target
pins/resources, DB roles/grants/migration, digests, private protection/secret scopes,
redirect change, execution/stop window and any new hosted-auth budget. Uncertainty
blocks activation. Production authentication and full NIST/16-stage audit remain
outside this private preparation. No cloud operations were performed.
