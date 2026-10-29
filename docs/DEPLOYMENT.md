# Controlled deployment and rollback

No production rollout, secret update, push, or cloud mutation was performed during implementation. These are operator steps. Do not release until the required environment/federation/job/probe settings below have been checked.

## One-time prerequisites

1. Take/verify a Neon backup or restore point and rehearse the additive migration against a **non-production clone**. Preserve the existing users, movies, ratings, and sequences. No reset, public claiming, or destructive downgrade is part of this release.
2. Create a GitHub `production` environment restricted to `main`, with required reviewer approval. Configure Azure federation for subject `repo:aanxnd/movie-recommender:environment:production`, audience `api://AzureADTokenExchange`. Existing branch-subject federation must be retired after verifying the new environment flow, otherwise historical insecure workflows may retain cloud access. Grant only the necessary Container Apps/job operations in the intended resource group. Keep the existing client/tenant/subscription identifiers; introduce no Azure client secret.
3. Verify GHCR pull access for both the application and migration job. Public package pulls avoid a long-lived registry credential. GitHub OIDC authenticates deployment management; it does not automatically grant Azure a GHCR image-pull identity.
4. Provision a **manual** Container Apps job named `movie-recommender-migrate` in `movie-recommender-rg`, same network reachability as the API. Parallelism/completion count 1, retry limit 0, replica timeout 300 seconds. Its command is `/usr/local/bin/movelle-migrate`. It needs `APP_ENV=production`, the same TLS PostgreSQL `DATABASE_URL` via a job-local secret reference, and valid `CORS_ALLOWED_ORIGINS`. Provision secrets privately through the cloud secret manager/portal. Job secrets are not inherited from the API. Never print connection strings or check them into YAML.
5. The job template can initially reference an existing known image without running it: each workflow execution overrides image/command with the exact verified release digest. Alternatively provision it after the candidate image has been published and rerun only the failed deployment job. Never substitute an unverified image for migration execution.
6. Review/apply the intended API runtime configuration through the Azure console/IaC in a separate authorized operation. Required environment: `APP_ENV=production`, TLS `DATABASE_URL`, exact frontend HTTPS CORS origins, prepared path, optional pinned archive URL+SHA, `PORT=8000`, and finite validated `TRUSTED_PROXY_IPS`. No wildcard proxy trust. Confirm Azure strips/sanitizes forwarding headers before trusting its proxies. Without validated proxy configuration visitors may share a conservative source-address quota.

## Runtime settings to verify in Azure

| Setting | Initial target |
|---|---|
| API entrypoint | Image CMD `python -m app.runtime`, one worker |
| Container port | 8000 |
| CPU / RAM | Start at 1 CPU / 2 GiB, then measure actual 32M RSS/latency |
| Writable disk | Disk-backed, allow 2 GiB for archive + staging + reference data |
| Startup | HTTP `/health`, period 10s, timeout 3s, failure threshold 60 |
| Readiness | HTTP `/ready`, period 30s, timeout 5s, failure threshold 3 |
| Liveness | HTTP `/health`, period 30s, timeout 2s, failure threshold 3 |
| Termination grace | At least 45s for the 30s app shutdown budget |
| Scaling | Finite maximum (initially 2); verify CPU/memory/cost budget |
| Minimum replicas | 0 for lower idle usage; 1 avoids download cold starts during promotion and incurs ongoing usage |

These are intended settings, not assertions about live resources. Allow the startup probe budget to cover bootstrap before Uvicorn begins listening. A cold start may exceed the browser's request timeout. Each replica can compute one recommendation simultaneously; reference memory and DB connection ceilings multiply by replicas. DB-side admission counts are shared. Readiness may briefly report a cached result after a DB state change.

Use a fresh prepared directory when changing the archive digest. Never overwrite a mapped directory in-place. Mount administrator-supplied data with archive variables unset. Checksum validation is automatic; full semantic preparation verification stays offline.

## Release sequence

1. Review and authorize pushing/merging the local branch separately. Require backend/frontend CI checks on `main`. `tests.yml` runs offline Small tests, a disposable PostgreSQL service, frontend tests, and the production frontend build. Opt-in local 32M tests do not download data in CI.
2. Prepare a Vercel preview from the same source commit. Root directory `frontend`, Node 24, install `npm ci`, build `npm run build`, output `dist`. Set **public** `VITE_API_BASE_URL` to the real backend HTTPS origin without `/api`, and set backend CORS to the intended preview/production origins. No database URL or credential belongs in `VITE_*`. The included Vercel CSP permits HTTPS connections; tighten `connect-src` to the exact backend origin once known.
3. Dispatch **Controlled production release** on `main`. There is no push-triggered deployment. The workflow reruns reusable CI for that exact event SHA, builds/publishes a uniquely tagged GHCR image, then smoke-tests the **published digest**. Publishing an image alone does not deploy it.
4. The protected deployment job rejects a SHA that is no longer `main` before cloud changes. Runs are serialized and never canceled halfway through migration. Approve the protected environment only after checking the preview and the tested SHA/digest.
5. The workflow starts the migration job using that exact digest, waits for `Succeeded`, and fails closed on failure/timeout. Only then can the Azure deployment action update the API using `image@sha256:DIGEST`. Production application startup checks schema version 2; it does not attempt DDL. The image/command override and clearing of inherited arguments follow the [Azure job start CLI contract](https://learn.microsoft.com/en-us/cli/azure/containerapp/job?view=azure-cli-latest#az-containerapp-job-start); validate the provisioned job in the non-production rehearsal.
6. Coordinate the first authentication cutover: pause public promotion/put the old UI behind maintenance if needed, route API traffic entirely to the secure new revision, and retire old unauthenticated revisions. **Do not split traffic between authenticated and old unauthenticated backends.** An old frontend receives authorization errors; it must never trigger an insecure compatibility mode. Promote the tested Vercel frontend once the secure API is healthy.
7. Verify `/health` and `/ready`, profile creation, refresh restoration, cross-profile denial, fractional save, group invitation/revocation, capacity behavior, and two independent client networks for rate-limit attribution. Check logs/metrics for startup/probe failures, 401/403/429/503 rates, transaction/pool waits, duration and RSS. Do not log Authorization headers, bodies containing invitation codes, or recovery files.
8. Verify the database restore procedure and alert/cost limits before broad public sharing. Record the application digest, schema version, reference manifest identity, and frontend commit. Azure/Neon/Vercel behavior remains unverified until these operator checks pass.

After the separately authorized push/merge and prerequisite setup, an operator can dispatch and inspect the release from the repository:

```sh
gh workflow run publish-image.yml --ref main
gh run list --workflow publish-image.yml --branch main --event workflow_dispatch --limit 5
gh run watch RUN_ID --exit-status
```

Replace `RUN_ID` with the new dispatch's actual run ID. Review the exact SHA/digest and approve the protected `production` environment in GitHub when prompted. A failed run is not evidence that deployment occurred; inspect which job failed. Never bypass the CI, image smoke test, stale-SHA guard, or migration-success gate. These commands were documented, not executed here.

## Troubleshooting

- **Production exits before bootstrap:** validate APP_ENV, PostgreSQL/TLS URL, exact HTTPS CORS origins, and proxy trust configuration without printing secrets.
- **Schema migration required:** run the protected migration job; never switch to SQLite or reset Neon. Inspect sanitized job status and private server logs. Migration 1/2 is additive and idempotent under a DB lock.
- **Old profile inaccessible:** old IDs are intentionally locked. Recover only after out-of-band ownership verification. Use an operator shell with the correct backend secret environment and `python -m app.manage recover-profile --user-id ID --output PRIVATE_PATH.credentials.json`. This also supports expired credentials, refuses live claimed credentials, revokes old group invitations, and preserves ratings. Treat a failed recovery output as untrusted until checked; files are not overwritten on retry.
- **Archive mismatch:** choose a fresh versioned prepared directory; do not edit verification markers or disable checks. Missing/changed pinned provenance is a failure, not permission to relabel existing data.
- **503 capacity busy:** expected overload; Retry-After is exposed to the browser and bounded retries apply. Workload-timeout 503s are not automatically retried. Reduce workload or measure/adjust finite capacity.
- **429 across unrelated visitors:** check validated ingress attribution. Do not solve it by trusting arbitrary forwarded headers or removing quotas.
- **Save timed out:** reload ratings before another write. Creation is not automatically retried; a lost creation response can leave an inaccessible anonymous profile, but cannot grant another visitor ownership.
- **Probe failure:** check DB connectivity and process resources. Cached checks prevent public request frequency from driving healthy probe frequency. Never use DB-dependent readiness as liveness.

## Rollback

Stop further release dispatches and retain the failed revision's sanitized diagnostics. Route traffic to the last known **secure, schema-compatible immutable digest**, then restore the matching compatible frontend. Do not use `latest`, rerun an old unauthenticated deployment, or downgrade/drop tables. Additive version 1/2 tables can remain during an application rollback. If the only previous revision is unauthenticated, keep the service in maintenance and fix forward rather than reopening access to all profiles. Database restore is a separate, explicitly authorized recovery action with data-loss implications; do not automate it as application rollback.

## Boundaries of local verification

Local Docker and disposable PostgreSQL validate application code and container contracts. They do not validate Azure RBAC/federation, GHCR pull permissions, Neon transaction pooling/TLS/restore, live probes, Vercel environment variables/CSP, platform scaling, or cost. Cloud release commands in this document/workflow have not been executed during implementation.
