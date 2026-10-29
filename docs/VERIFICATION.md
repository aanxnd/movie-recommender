# Verification record

Implementation review completed locally on 2026-10-29 (America/Toronto). Dependency advisory snapshot and initial final checks were taken on 2026-10-28. Branch: `production-readiness`; baseline: `6166c8d`. No push, cloud deployment, cloud configuration change, or production database access occurred.

## Exact results

| Check | Passed | Failed | Skipped | Scope |
|---|---:|---:|---:|---|
| Baseline backend, before implementation | 475 | 1 | 9 | Existing suite; optional PG/32M cases disabled |
| Final backend full regression | 512 | 0 | 0 | Disposable SQLite + actual loopback PostgreSQL 17; local 32M opt-ins enabled |
| Additional final-review boundary run | 19 | 0 | 0 | Limits, reliability, PG concurrency and real compute deadline; includes five tests added after the full run collected |
| Final frontend tests | 10 | 0 | 0 | Node test runner, real React server rendering, actual fetch/error/cancellation client |
| Linux container smoke | 7 | 0 | 0 | New disposable container with prepared Small fixture and synthetic SQLite database |

The 19-test review run overlaps the main suite; do not add all counts together. It adds five unique tests (monotonic counter windows, oversize profile/group rejection, incomplete-schema detection, concurrent profile cap, and the actual prepared computation deadline/recovery path). Thus **all 517 distinct backend tests passed across the two runs, with zero failures and zero skips**. The full regression reported 5,357.79 seconds elapsed; this includes a long interruption in local tool execution and is not a request-performance measurement.

Other checks:

- Production frontend build succeeds with Vite 8.3.5, 1,895 modules; output approximately 248.44 kB JavaScript (78.25 kB gzip) and 14.83 kB CSS (3.80 kB gzip).
- `npm audit --json`: zero known vulnerabilities, 83 dependencies in the audit report.
- OSV querybatch: all 31 exact Python pins queried, zero advisory findings after patching. Full snapshot in `dependency-review.json`. `pip check` reports no broken requirements.
- Hash refresh utility reproduces both dependency locks exactly without modifying them.
- Python source AST parse: all 48 application/test/script files passed. Report JSON and frontend header configuration parse; `git diff --check` passes.
- `rhysd/actionlint:1.7.7` checks both workflows including shell blocks, exit 0, no findings.
- Docker build succeeds with pinned base and `--require-hashes --only-binary=:all:` runtime installation. Locally built manifest-list digest: `sha256:9f6f489866bcb503c18935f740bcaf85f8b8ba2367e01d3671b7b442ba7076be`. This is local build evidence, not a published GHCR release digest.
- The image migration entrypoint succeeds on a new disposable SQLite database. Starting the image with default production mode and missing DB configuration fails with the expected sanitized PostgreSQL/TLS error before bootstrap. That deliberate nonzero exit is the expected check outcome.

The baseline failure was a readiness stall test that did not reach its injected stall marker within a 1.5-second process-start allowance on this Windows host. Its test-only startup allowance was increased while retaining real subprocess termination/reaping assertions. The default runtime probe still has its own three-second deadline. A temporary uncommitted indentation error discovered at the pause was fixed before the successful verification runs.

Starlette emits a development TestClient deprecation warning for HTTPX. It does not fail tests; HTTPX remains a dev-only dependency. A future test-client migration can follow upstream guidance without adding a production dependency.

## Reproduction

Use the hash-locked dev environment. Clear inherited application configuration before tests; never use a production `DATABASE_URL`. Run `python -m pytest -q -p no:cacheprovider` against temporary test directories. CI supplies its own PostgreSQL 17 service; local real-PG checks require an explicit `POSTGRES_TEST_URL` that passes the loopback-only test validator. The tests create/drop unique synthetic schemas, never public or application production tables.

For existing official local 32M data, set `MOVIELENS_32M_EQUIVALENCE=1` in the test process. This enables eight full indexed/reference comparisons plus the reported sparse-profile regression. It reads existing prepared artifacts and downloads nothing. The full reference comparisons intentionally inspect every eligible historical neighbor and can take much longer than normal request computation. Test-suite elapsed time is not a performance benchmark.

Frontend: `cd frontend`, `npm ci`, `npm test`, `npm run build`, `npm audit --json`. Node/Vite require subprocess access on Windows. Initial restricted-shell attempts returned EPERM; authorized reruns with subprocess access passed.

Container: `docker build -t movelle-verification:production-readiness .`, then `python scripts/smoke_container.py --image movelle-verification:production-readiness --prepared data/prepared/latest-small-v1`. The runner starts/stops only its own new container. It asserts readiness, user creation, missing-credential denial, fractional rating persistence, metadata, recommendations, UID 10001, and no pytest/HTTPX installation.

## Recommendation regression and timing

The exact supplied eight-film profile reproduces on official 32M artifacts. It produces confidence .04411764705882353 and top-ten predictions between 3.15862 and 3.17400. A hand-calculated synthetic regression independently verifies candidate evidence and shrinkage.

The five warm baseline/current comparisons in `recommendation-benchmark.json` compare every top-ten result field exactly. Medians (seconds):

| Case | Baseline | Current | Exact output |
|---|---:|---:|---|
| Reported eight | .1910306 | .2000851 | Same |
| Reference five | .3704305 | .4079022 | Same |
| Reference twenty | 1.8944100 | 1.9594889 | Same |
| Reference hundred | 5.8142277 | 5.6770154 | Same |
| Group union of 33 | 3.1900347 | 3.0819718 | Same |

One warmup and three alternating measurements per case, same Windows/Python 3.14 process and read-only dataset. No claim of general performance or quality improvement follows from these small timing differences. The frontend explanation changes; recommendation mathematics does not.

## Verification limits

No live Azure/Neon/Vercel verification, actual hosted workflow execution, load test, complete browser interaction suite, or third-party security assessment was performed. A Small-container smoke and local PG integration do not establish 32M Linux memory/cold-start capacity or Neon pooler/TLS behavior. The release stays gated on the operator rehearsal and platform checks in `DEPLOYMENT.md`.

The disposable verification PostgreSQL container was named `movelle-verify-20261028`, labeled `com.movelle.verification=production-readiness`, bound only to loopback, and used synthetic data. It was stopped and automatically removed after verification, after checking its label. Other running containers were not stopped. The locally built verification image remains available.

## Local commits

1. `45439c2` — Security, anonymous identity, group capabilities and additive migrations.
2. `55b8729` — Shared admission, workload bounds and atomic quotas.
3. `8d24ac5` — Exact-commit CI gating, serialized release and immutable image deployment.
4. `39b48d6` — Short DB transactions, readiness/timeouts and consistent dataset integrity.
5. `3ffa362` — Ratings metadata pages and resilient authenticated frontend requests.
6. `f658fd6` — Sparse-evidence explanation, exact baseline benchmarks and regressions.
7. Final verification/documentation/dependency commit — identify with `git log -1` after completion; this record is included in that commit.

All commits are local. Pushing and releasing remain separate user-authorized actions.
