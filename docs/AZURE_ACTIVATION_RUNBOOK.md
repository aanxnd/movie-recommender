# Azure controlled activation checklist

The app `movie-recommender-api` stays **manually stopped** until the release PR is
merged by the owner and the protected production jobs are approved. The November 23
owner approval covers controlled research testing only; public promotion is excluded.
Read [image/config contract](AZURE_NATIVE_DEPLOYMENT.md) first.

## Current audit and intended shape

Owner-reported existing resource: `movie-recommender-rg`, Canada Central,
`managedEnvironment-movierecommende-9747`, Express/Consumption, Single revision,
HTTPS ingress8000,1vCPU/2GiB,min0/max3,HTTP `http-scaler` concurrency10, public
digest-pinned GHCR and Log Analytics. No cloud API was used to verify these facts.
Prepared target changes only max3→1 plus reviewed native image/config/probes.
Keep min0,concurrency10,Single,existing TLS ingress/environment/identities.

November 23 owner-supplied read-only API evidence confirmed the app remains
Stopped/Succeeded with those limits and three existing secrets with values present. Azure
returned the region display name `Canada Central`; the rollout previously compared
it only with `canadacentral` and failed its first scope check. Both documented
forms now map explicitly to `canadacentral`; other/malformed regions still fail.
The offline response-shape regression uses fictional secret values and verifies
that existing secrets and platform-reported 4Gi ephemeral storage survive preparation.
This is not hosted rollout acceptance. No revision retirement, PATCH or start was
performed; the workflow must not be retried automatically. See Microsoft's
[region names](https://learn.microsoft.com/en-us/azure/reliability/regions-list).
Safe phase labels now distinguish resource reads, secret reads and local validation;
the generic hosted error alone cannot establish the original caller's API permissions.

All Oracle PR111–123 are merged. They added ARM/Compose/TLS preparation and
retired only an undeployed private Azure proposal. The actual Azure workflow,
legacy image, OIDC, migration/rollback tools were never deleted. Do not restore
private gateways, custom session observers or abandoned file-secret bootstraps.
Useful native Vercel packaging, reference verification, browser fixes, docs and
security regressions survive. Oracle Compose/TLS is retained historical code,
not part of the selected deployment. No VM/proxy/certificate service is needed.

## Review configuration privately

`deploy/azure/containerapp.review.json` is an incomplete review worksheet, NOT an
ARM deployment or safe replacement for an exported app. Never apply it wholesale:
it omits existing identity/environment/registry/traffic settings and uses invalid
placeholders. Preserve actual container name and existing resource configuration.
After privately filling a copy with reviewed values, offline-only validation is:
`python deploy/azure/review.py PRIVATE_FILLED_COPY.json`.
It checks selected fields and native targets; it does not prove subscription scope,
image architecture, secret existence, billing, RBAC, live grants or active settings.
Do not print exported secrets, private files or expanded Docker/Azure commands.

Environment requirements (no actual values in this repository):

| Setting | Source / requirement |
|---|---|
| APP_ENV / PORT / MOVELLE_NATIVE_MODE | production /8000/native-release |
| MOVELLE_NATIVE_PREPARED_DIR | baked `/backend/data/reference/ml-32m-v1` |
| MOVELLE_NATIVE_TARGETS_JSON | reviewed `approved:true`, frontend/API roots, Supabase root, exact Neon host/database |
| CORS_ALLOWED_ORIGINS | exactly the manifest frontend HTTPS origin |
| MOVELLE_NATIVE_DATABASE_URL | ACA secretRef; dedicated `movelle_native`, exact host/DB and verified TLS/channel binding |
| MOVELLE_NATIVE_PUBLISHABLE_KEY | ACA secretRef; public project key, never admin/service-role |
| Frontend native build | same target manifest + public key, `npm run prepare:native`; no DB secrets |
| Operator migration | separately reviewed `movelle_native_migrator`; never runtime credentials or startup DDL |

The provider-neutral operator is `python -m app.native_schema check` or `migrate`,
included in the exact native image but never selected by its startup command.
After separate DDL approval, mount private regular files read-only at
`/run/secrets/native_database_url`, `native_publishable_key`, `native_migration_url`;
pass only nonsecret native mode/CORS/target JSON. Do not pass ambient runtime DB/key
environment values to this file-only operator. It requires the separate migrator
role, exact matching host/database/verified TLS and rejects reset/legacy claiming.
This reuses the reviewed native operator, not the paused legacy migration workflow.
The prepared workflow now selects the AMD64 Azure Dockerfile/reference context,
checks its published digest and runs read-only `app.native_preflight` before Azure
login/update. It performs no automatic DDL. Publish/deploy require main, the
default-false `confirm_native_activation` manual input, passing CI and existing
protected production reviews. Never dispatch before the owner merges this release
PR and the exact provider configuration is ready.
Existing protected `production` environment/review/OIDC/stale-SHA safeguards remain.
Future protected GitHub secrets are `NATIVE_RUNTIME_DATABASE_URL` and
`NATIVE_PUBLISHABLE_KEY`; variables are matching `MOVELLE_NATIVE_TARGETS_JSON` and
`CORS_ALLOWED_ORIGINS`. Configure privately only after approval; no actual values
exist in these changes. Retain the full 32M license/citation and noncommercial/no-endorsement notices.
The dataset-specific terms permit the approved research redistribution without
an additional GroupLens email. Other/commercial scopes require separate review.

No PG overrides, proxy trust, legacy DB fallback, deletion worker or extra process.
The backend FQDN in the worksheet validator comes from existing Vercel configuration;
the owner must confirm it remains assigned to this exact app before building public
token destinations. Confirm frontend origin separately; no guessed Vercel domain.

## Activation sequence — requires a new, explicit owner approval

1. **Billing hold:** obtain Microsoft's written answer for this exact subscription,
   spending limit, credit exhaustion/expiry, Marketplace exceptions and out-of-pocket
   protection. Verify remaining credit/expiry privately; never upgrade/remove limits.
   Budget alerts and max1 are not caps. Keep the app stopped until this passes.
2. Verify subscription/resource/environment IDs, stopped state, registry pulls,
   actual secret references, runtime/migrator grants, schema version and restore point.
   Rehearse schema4 migration/rollback on an isolated DB; old schema2/3 binaries
   cannot safely run schema4. No production DDL belongs to this preparation.
3. Authorize public GHCR data/image publication and preserve GroupLens terms.
   Build the default AMD64 release with the verified32M named context. Inspect its
   platform/digest, run local guards, then separately authorize push. No image push
   is executed here. The CI `runtime` target is intentionally incomplete.
4. Prepare exact native/frontend targets, production Supabase root callbacks,
   verified-email/ES256/TOTP settings and native static Vercel output/CSP. Preserve
   preview protection; hold automatic production alias promotion. The current
   default frontend build remains legacy until a coordinated approved switch.
5. Apply only reviewed changes to the existing ACA app: native digest/env/secretRefs,
   max1 and probes; retain min0,1CPU/2GiB,Single,HTTPS8000,HTTP concurrency10.
   Configuration changes may activate revisions: none is safe to execute now merely
   because the app is stopped. Do not dispatch the paused legacy workflow.
6. Explicitly restart only after owner approval. Probe `/health` for platform
   startup/liveness/readiness. Use DB-dependent `/ready` only for bounded deployment
   acceptance/diagnosis, never external periodic warm-up. Test cold starts, deadlines
   and safe UI retry: ordinary frontend read timeouts may expire before a cold wake;
   writes/provisioning must not be blindly replayed.
7. Under a newly approved hosted mutation budget, verify native signup→confirmation
   →profile→optional TOTP/AAL2→ratings/recommendations/groups, wrong-account denials,
   logout/account switching, password callbacks and failure states. The newly approved budget is
   1 new account/profile, 1 TOTP factor, 3 ratings and at most 4 authentication
   emails. Removal/deletion remain gated.
8. Verify idle replicas reach0, then actual HTTP wakes the app; repeated safe GET
   after scale-up succeeds, stale Neon connections recover and no data is lost.
   Do not confuse manually stopped with automatically scaled-to-zero.
9. Promote only the paired native frontend/API after acceptance. Verify TLS/CORS/
   CSP and anonymous browsing. Full NIST assessment/16-stage audit obligations and
   any remaining release gates are retained; this is not a compliance claim.

## Logging, credit monitoring and rollback

Uvicorn access logs remain disabled; do not enable verbose HTTP, URL/header/body,
SDK or SQL parameter logging. Review actual Log Analytics tables/retention/ingestion
and diagnostics. Environment log storage affects other apps: assess before changing
it. Choose minimal system/error evidence or separately approve disabling storage;
record lost incident visibility. No new workspace, paid sink or Marketplace item.
Check Sponsorships credit and Cost Management after approved tests and regularly
while active, including Log Analytics/egress and expiry. Alerts are not hard caps;
max1 can still see platform maintenance/revision overlap and does not guarantee cost.

Retain the previous secure **native/schema4-compatible** digest and matching frontend.
If none exists for first cutover, stop traffic/return to maintenance and fix forward;
never reopen legacy ownership or downgrade/drop schema. Single mode does not imply
inactive revisions can receive traffic: use the separately reviewed previous-image
procedure. Preserve DB restore points; restoration is a separate data-loss decision.
Current legacy release/rotation history remains in [DEPLOYMENT.md](DEPLOYMENT.md).

Official evidence: [AMD64 containers](https://learn.microsoft.com/en-us/azure/container-apps/containers),
[scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app),
[probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes),
[logging options](https://learn.microsoft.com/en-us/azure/container-apps/log-options),
[spending-limit scope](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit).
Provider documents support the design, not the actual subscription protection,
Express feature availability, hosted configuration, cold-start latency or acceptance.
