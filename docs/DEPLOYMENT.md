# Controlled deployment and rollback

No production rollout, secret update, push, or cloud mutation was performed during implementation. These are operator steps. The existing API is `movie-recommender-api` in resource group `movie-recommender-rg`, in Express environment `managedEnvironment-movierecommende-9747`. This environment does not support Container Apps Jobs, so the protected GitHub-hosted runner executes migrations directly from the tested release image. No Azure migration job is required.

## One-time prerequisites

1. Take/verify a Neon backup or restore point. Schema version 2 was reported successfully rehearsed on an isolated Neon branch; retain that evidence and repeat the rehearsal for future migration changes. Preserve existing users, movies, ratings, and sequences. No reset, public claiming, or destructive downgrade is part of this release.
2. Preserve the existing GitHub `production` environment restricted to `main`, with required reviewer approval. Azure OIDC uses user-assigned managed identity `movie-recommender-github`, federation subject `repo:aanxnd/movie-recommender:environment:production`, audience `api://AzureADTokenExchange`, and environment secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. Retire obsolete branch-subject federation after verifying the environment flow. Grant only the required API deployment operations; this workflow no longer needs Container Apps Job permissions. Introduce no Azure client secret.
3. In GitHub Settings -> Environments -> `production`, an authorized operator must privately add **environment secret `PRODUCTION_DATABASE_URL`**. Use the intended production Neon database with a role authorized for the additive migrations. Prefer a dedicated migration role and a direct/unpooled endpoint; keep the runtime API role/secret separate when practical. TLS is mandatory (`sslmode=require`, `verify-ca`, or `verify-full`); prefer verified certificates when correctly configured. Never put this value in repository variables, frontend configuration, command arguments, artifacts, or workflow outputs. This implementation does not create or change the secret.
4. In the same protected environment, set the non-secret **environment variable `CORS_ALLOWED_ORIGINS`** to the actual frontend HTTPS origin(s), comma-separated, without paths, trailing slashes, or wildcards. The migration explicitly uses `APP_ENV=production`. An empty secret or variable blocks migration and deployment; there is no placeholder origin or SQLite fallback.
5. Verify that a GitHub-hosted Ubuntu runner can reach the intended Neon endpoint over TLS/PostgreSQL (DNS and outbound port 5432), and that the selected role can perform the required DDL. An isolated branch rehearsal does not prove production network reachability. If production requires private networking or an IP allowlist that excludes the runner, **stop**: use an approved runner with suitable network/static-egress access in a separately reviewed change. Do not disable TLS, expose the database broadly, or expand IP allowlists automatically to make a deployment pass.
6. Verify GHCR pull access for the application and the protected runner. The runner authenticates with the job's short-lived `GITHUB_TOKEN` and `packages: read`; its fresh job does not inherit the publish job's Docker login. Azure OIDC authenticates deployment management and does not grant GHCR pull access or authenticate to Neon. Keep existing API image-pull access configured; no Azure migration job/pull identity is needed.
7. Review API runtime configuration separately: `APP_ENV=production`, TLS `DATABASE_URL`, exact frontend HTTPS CORS origins, prepared path, optional pinned archive URL+SHA, `PORT=8000`, and finite validated `TRUSTED_PROXY_IPS`. The GitHub migration secret does not automatically update the API's database secret. Verify that both point to the intended database. Confirm ingress sanitizes forwarded headers before trusting proxies; otherwise visitors may share a source-address quota.

## Migration execution and secret boundary

The protected job runs `bash scripts/migrate_release.sh`. It validates required inputs and the full GHCR SHA-256 digest reference, pulls that exact published/smoke-tested image, and starts a short-lived container with the image's non-root user. Inside the container, the release's existing configuration/CORS validators run first, followed by its existing `/usr/local/bin/movelle-migrate` entrypoint. The runner does not install Python application dependencies, reconstruct migration code, mount repository code over the image, start the API, or download MovieLens data for this step.

The secret is scoped to the migration step as `DATABASE_URL` and forwarded with `--env DATABASE_URL`, so only the variable name appears in Docker arguments. Shell tracing is disabled. There are no credential files, host mounts, Docker socket mounts, published ports, or forwarded Azure/GitHub credentials in the container. The filesystem is read-only, capabilities are dropped, and privilege escalation is disabled. Docker logging is disabled and container stdout/stderr are suppressed; the runner prints only fixed success/failure messages. The execution has a five-minute timeout, a cleanup trap removes its named container, and the workflow step has a seven-minute outer timeout. A failed pull, validation, migration, or timeout fails the job and prevents the Azure login/deploy steps. There is no automatic migration retry.

This deliberately extends trust to the approved release image and ephemeral GitHub runner: the process and Docker daemon necessarily receive the plaintext database credential, and trusted code could use or exfiltrate it. Environment masking is not a sandbox. Review the exact SHA, image, workflow and scripts before approval, keep secrets environment-scoped, protect `main`, use a narrowly privileged role, and do not enable environment/debug dumps or publish container inspection/log artifacts. No secret is baked into the image. See [GitHub secret handling](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets), [Docker environment forwarding](https://docs.docker.com/reference/cli/docker/container/run/#env), and [Neon secure connections](https://neon.com/docs/connect/connect-securely).

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
5. After approval and the stale-SHA guard, the runner logs into GHCR, runs the migration container from that exact digest with the protected database secret and CORS variable, and requires exit status zero. Only then does Azure OIDC login run and the deployment action update `movie-recommender-api` using the same `image@sha256:DIGEST`. Production startup checks schema version 2; it does not attempt DDL. This flow works with the existing Express environment and performs no Container Apps Job operation.
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
- **Migration configuration missing:** privately check that `PRODUCTION_DATABASE_URL` is a secret in the `production` environment and `CORS_ALLOWED_ORIGINS` is a variable in that environment. Do not print their values into Actions logs. An environment/repository value with a different name is not a fallback.
- **Schema migration required or runner migration failed:** inspect the fixed failure category, Neon connectivity/role/TLS settings, and existing private database diagnostics. Container output is intentionally suppressed. Reproduce against an isolated branch with the same image before a new approved release; never bypass the migration step, switch to SQLite, reset Neon, or expose the production secret through debug output. Migration 1/2 is additive and idempotent under a DB lock. A timeout or lost response does not prove rollback: verify schema state privately before retrying. Successful migration followed by deployment failure leaves the additive schema in place; do not downgrade it.
- **Old profile inaccessible:** old IDs are intentionally locked. Recover only after out-of-band ownership verification. Use an operator shell with the correct backend secret environment and `python -m app.manage recover-profile --user-id ID --output PRIVATE_PATH.credentials.json`. This also supports expired credentials, refuses live claimed credentials, revokes old group invitations, and preserves ratings. Treat a failed recovery output as untrusted until checked; files are not overwritten on retry.
- **Archive mismatch:** choose a fresh versioned prepared directory; do not edit verification markers or disable checks. Missing/changed pinned provenance is a failure, not permission to relabel existing data.
- **503 capacity busy:** expected overload; Retry-After is exposed to the browser and bounded retries apply. Workload-timeout 503s are not automatically retried. Reduce workload or measure/adjust finite capacity.
- **429 across unrelated visitors:** check validated ingress attribution. Do not solve it by trusting arbitrary forwarded headers or removing quotas.
- **Save timed out:** reload ratings before another write. Creation is not automatically retried; a lost creation response can leave an inaccessible anonymous profile, but cannot grant another visitor ownership.
- **Probe failure:** check DB connectivity and process resources. Cached checks prevent public request frequency from driving healthy probe frequency. Never use DB-dependent readiness as liveness.

## Rollback

Stop further release dispatches and retain the failed revision's sanitized diagnostics. Route traffic to the last known **secure, schema-compatible immutable digest**, then restore the matching compatible frontend. Do not use `latest`, rerun an old unauthenticated deployment, or downgrade/drop tables. Additive version 1/2 tables can remain during an application rollback. If the only previous revision is unauthenticated, keep the service in maintenance and fix forward rather than reopening access to all profiles. Database restore is a separate, explicitly authorized recovery action with data-loss implications; do not automate it as application rollback.

## Boundaries of local verification

Local script tests use mocked Docker/timeouts and synthetic credentials; they do not execute production migrations. Local Docker and disposable PostgreSQL checks validate application/container contracts, not protected-secret availability, hosted-runner access to production Neon, Azure RBAC/federation, GHCR pulls, live probes, Vercel settings, scaling, or cost. The reported isolated Neon rehearsal is separate evidence. Cloud release commands and production secret changes in this document/workflow have not been executed during this update.
