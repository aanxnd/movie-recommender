# Audit implementation and release review

Reviewed through 2026-10-29 against the 25 supplied findings and audited source commit `6166c8d`. All seven implementation phases are complete in local commits, including the final verification commit containing this report. This is a local release candidate, not a claim that the live Azure/Neon/Vercel deployment has been verified. No production database, cloud configuration, push, or deployment was used during this work.

## Resolution matrix

“Implemented / verified” means the repository change has relevant local behavioral checks or, for workflow/platform configuration, static validation. The release prerequisites below still apply to every production claim.

| Finding | Status | Implemented fix | Evidence |
|---|---|---|---|
| SEC-001 Anonymous profile ownership | Implemented / verified | Random 256-bit bearer credentials, hashes only, owner authorization, expiry, local persistence, narrow expiring group invitations, additive legacy migration/operator recovery | `test_security.py`, `test_management.py`, frontend identity/request tests, container ownership check |
| SEC-002 Unrestricted profile/write growth | Implemented / verified | Shared DB source/global creation limits, atomic write quota, 100-rating ceiling, serialized 5,000-profile lifetime ceiling; preserve existing data | `test_limits.py`, real PostgreSQL concurrent creation/write tests |
| SEC-003 Unbounded recommendation work | Implemented / verified | Shared caller/global admission, at most 100 ratings/profile, five members/200 combined ratings, existing semaphore, cooperative 20-second budget | Limits tests reject excess work before computation; API gate/release tests; PostgreSQL counters |
| SEC-004 Missing endpoint/request limits | Implemented / verified | 16-KiB body cap, receive deadline, search/genre/count bounds, bounded results, shared general API admission; historical popularity uses precomputed order | Body/search/creation tests, API validation/equivalence tests |
| REL-001 Readiness collisions/churn | Implemented / verified | Single-flight cached readiness with 30-second success/two-second failure TTL; retain killable subprocess isolation | `test_reliability.py`, stalled checkout/query/cleanup and process reaping tests |
| REL-002 Connections held during compute | Implemented / verified | Authenticate, charge admission, load bounded profiles, commit/close before recommendation computation; avoid nested pool checkout | Personal/group tests assert zero checked-out connections; real PG concurrent authenticated transactions |
| REL-003 Missing execution timeouts | Implemented / verified | PG statement 5s, lock 2s, idle transaction 10s, PG17+ overall transaction 10s; Python transaction guard, pool/connect budgets, SQLite statement progress budget | Real PG lock/statement cancellation followed by connection reuse; timeout settings assertions |
| REL-004 Concurrent schema races | Implemented / verified | Versioned transactional migrations under PostgreSQL advisory lock/SQLite BEGIN IMMEDIATE; prod startup checks version/table inventory | Dual fresh-schema migrators on SQLite and PostgreSQL; incomplete-schema test |
| REL-005 Changed archive digest reused | Implemented / verified | Require matching pinned provenance; reject reuse with changed/missing provenance; fresh versioned directory required | Changed-pin test preserves previous marker; bootstrap corruption/provenance tests |
| REL-006 Startup integrity inconsistency | Implemented / verified | Shared artifact inventory/checksum validation for runtime and direct ASGI startup; full semantic scan remains offline | Same-shape corruption rejected before database initialization; runtime/bootstrap tests |
| OPS-001 Deployment independent of CI | Implemented / verified locally | Manual release invokes reusable backend/frontend CI for exact event SHA; publish and deploy depend on success; exact published digest smoke-tested | Release invariant test, actionlint; actual hosted workflow execution pending |
| OPS-002 Out-of-order deployments | Implemented / verified locally | Serialized non-canceling release workflow; require main; reject stale SHA against main before cloud mutation | Workflow invariant test, actionlint; environment protection must be configured |
| OPS-003 Production SQLite fallback | Implemented / verified | Image defaults to production; required TLS PostgreSQL and HTTPS CORS validated before bootstrap | Production config tests and image refusal with missing DB config |
| OPS-004 No migration strategy | Implemented / verified | Additive schema version 2; explicit migration CLI/image shim; migration job must succeed before API update; no runtime prod DDL | Legacy preservation/idempotency/concurrency/recovery tests and disposable image migration |
| OPS-005 Reproducibility | Implemented / verified | Hash-locked exact Python dependencies, npm lock/ci, pinned base/service images and action SHAs, unique publish tag and digest deployment; Dependabot | Hash-enforced image build, advisory scans, frontend build, actionlint |
| OPS-006 Test dependencies in image | Implemented / verified | Separate runtime/dev locks and minimized Docker context; non-root runtime image excludes pytest/HTTPX | Built Linux image smoke asserts UID 10001 and no pytest/HTTPX |
| BUG-001 Lost status/Retry-After | Implemented / verified | Structured ApiError and exposed Retry-After; two bounded jittered retries only for explicit recommendation-capacity 503s | Frontend tests cover dates/status, authenticated query strings, retry ceiling and cancellation |
| BUG-002 N+1/ratings rendering | Implemented / verified | Keyset metadata pages of 100, one search rating batch, Map lookup, local update after save | 150-entry metadata/unavailable pagination test; actual 100-row React render test |
| BUG-003 Identity lost on refresh | Implemented / verified | Validated localStorage credential, authenticated restore, cross-tab updates, response epochs | Identity parse/persistence tests; authenticated restoration contract; manual live-browser checks pending |
| BUG-004 Unavailable movie breaks view | Implemented / verified | Enriched response preserves orphaned-catalog ratings with unavailable label; omit invalid rating control | Mixed available/unavailable page test and actual component render |
| BUG-005 Missing deadlines/recovery | Implemented / verified | 45s request budget, abort on obsolete requests, stale response guards, clear auth/rate errors, reload after uncertain writes; no mutation retry | Frontend deadline/abort/204/no-retry tests and API errors |
| BUG-006 Fractional rating display | Implemented / verified | Preserve exact saved rating string and add nonstandard fraction to selectable options | React render and API persistence tests use 3.25 |
| DOC-001 SQLite production footer | Implemented / verified | Footer describes private profile storage | Frontend production build and source review |
| DOC-002 Documentation drift | Implemented / verified | README plus controlled deployment/rollback and recommendation investigation documents | Final code/document cross-check; live settings explicitly unverified |
| TEST-001 Production boundaries | Implemented / verified | Raw-client ownership/capability tests, real PG quotas/upserts/deadlines/migrations, runtime container smoke, workflow lint, frontend request/component tests, opt-in real 32M equivalence | Exact results and scope in `VERIFICATION.md` |

## Architecture and compatibility

The application remains React/Vite/Tailwind + FastAPI/SQLAlchemy + prepared read-only MovieLens arrays. No Redis, authentication SaaS, machine-learning framework, or new runtime service was introduced. PostgreSQL stores anonymous application identity and ratings; historical reference users remain separate. Runtime and test dependencies are separately hash-locked; development retains pytest/HTTPX and production excludes them.

Original `users`, `movies`, and `user_ratings` survive. Additive `profile_credentials`, `group_invitations`, `schema_version`, and `rate_buckets` support ownership and shared quotas. Credentials are sent once at issuance, kept by the browser/recovery file, and validated by hash. Numeric IDs never serve as authorization. Existing unclaimed/expired profiles require operator ownership verification; there is no public claim endpoint. There is no scheduled user/rating deletion.

Authentication is an intentional breaking security boundary. An old frontend cannot operate private endpoints after the cutover. Never mix old unauthenticated backend revisions with secure revisions. Original raw ratings GET remains available but now paginates at 100; the new frontend uses enriched keyset pages. Existing ratings over the new limit remain readable and updateable; personalization rejects oversized profiles instead of deleting/sampling them.

## Recommendation outcome

The exact eight-film case reproduces near-mean scores (3.15862–3.17400) and confidence .0441176471 on official 32M artifacts. Sparse candidate support is the cause, not a demonstrated mathematics defect. A calibrated global threshold or popularity substitution is not justified by this example. Preserve all scoring/ranking mathematics and show a limited-evidence message when every returned CF result has confidence below .1. See `RECOMMENDATIONS.md` for the five exact-output baseline benchmarks and raw trace links.

## Final independent review

A separate end-to-end review after the six implementation phases traced public request admission through authentication, transactions, computation, browser state, and the release workflow against every finding above. It found and corrected a nested-session pool-exhaustion risk: owner admission now uses the existing short transaction, preventing two simultaneous authenticated requests from each waiting for an additional connection from the two-connection pool. Real PostgreSQL concurrency tests exercise that path. The review also added the serialized lifetime profile cap, database-clock monotonic rate windows, expired-profile recovery with invitation revocation, schema-column validation, exact-image smoke gating, and patched dependency pins.

The paused working-tree indentation error was corrected before regression tests; the final application models match the intended committed schema. Full regression verification, workflow lint and container behavior are recorded in `VERIFICATION.md`. The review was performed by the implementing agent in a separate pass; it was not an external penetration test or another human's review.

## Remaining operator work and risks

- Follow `DEPLOYMENT.md`: backup/clone migration rehearsal, protected main/environment, environment-scoped OIDC, GHCR pulls, migration-job provisioning/secrets, ingress proxy attribution, probes/resources, coordinated frontend/backend cutover, and compatible rollback. No cloud commands were executed during implementation.
- Local PostgreSQL validates dialect behavior, not Neon's transaction pooler/TLS/restore. Local Linux Small smoke validates packaging, not Azure cold-start memory, 32M concurrency, scaling or actual HTTP latency. Measure these before public promotion.
- Browser bearer credentials are accessible to same-origin scripts and remain transferable. Maintain dependencies/CSP; credentials cannot be recovered from a numeric ID. Verify Windows ACLs for operator recovery files.
- Limits are conservative portfolio defaults. Proxy misattribution can group visitors into one quota; distributed attacks can exhaust the finite creation allowance/storage cap. Use finite platform scaling/cost controls and review budgets before raising caps. Fixed windows permit bursts around boundaries.
- Computation cancellation is cooperative, with checks in the expensive neighbor/prediction loops. It does not interrupt a single executing native operation. PG17+ enforces overall transaction timeout; older servers rely on statement/idle limits plus a Python pre-statement budget and do not provide the same server-enforced whole-transaction bound.
- Cached readiness can lag a changed DB state for up to its TTL. It is intentionally independent of spare recommendation capacity and does not prove every application write permission.
- Metadata pagination is bounded; the tests do not replace a full live-browser, cross-tab, accessibility or mobile interaction review. Vercel's actual API URL/CSP and real-client retry/429 behavior require operator checks.
- Known-advisory scans are snapshots, not guarantees. Continue reviewing automated dependency updates and rebuilding immutable images.

Release instructions are concrete and reviewable, but executing them requires separate authorization. This task creates local commits only.
