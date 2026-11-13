# Stage 23 nine-PR pre-merge audit — 2026-11-13

## A. Executive summary

The corrected stack is suitable for an ordered merge without native production activation.
Nine actionable findings below were corrected; no Critical/High vulnerability was established.
Disposition: **APPROVED — SAFE TO MERGE ALL NINE PRS**, effective only when the exact
published #86 head, successful hosted checks and final review ledger are recorded in
[PR86](https://github.com/aanxnd/movie-recommender/pull/86). Until that ledger is complete, do not merge.
This is a pre-merge review, not Prompt 24, hosted acceptance, deployment approval or the final audit.

## B. Audited revisions

Main was independently fetched/verified as `4fa3d446a4c9d99d28eb959b3ee1a613cd19f03f`.
Initial stack head was `8726d111f80bfa25642cddb20616d74b62071d52`; all nine PRs were open,
unmerged and correctly chained. No concurrent changes to these branches were found.
Section I records final runtime/dependency SHAs; #86's exact report commit is in its PR ledger
because a file cannot contain its own commit hash. Original hashes remain in Git history.
Final cumulative diff: **53 files, +2560/-54**; per-PR additions/deletions are in the
exact-head ledger. Source/fixtures/builds remained unchanged during report finalization.
Every complete diff, shared dependency and final cumulative tree was reviewed. Three
independent backend, frontend and infrastructure reviewers assisted; the primary reviewer
reconciled their reproductions, corrections and final tree, rather than relying on test counts.

## C. Findings register

All findings are **resolved**. Test names below refer to actual automated regression assertions.

**A01 — Medium: inherited startup could invoke migrations.** `app/staging.py`, `app/main.py`.
A migration spy fired after staging's schema precheck: inherited development startup still
called `create_schema → migrate`. Intact schema 3 normally performed checks/locking, not DDL.
Explicit trusted schema initializer now calls only `check_schema`; the duplicate engine is removed.
Regression: parameterized `test_staging_startup_never_calls_migrator_or_ambient_artwork[schema]` forbids both migrators; schema-2 refusal remains.

**A02 — Low: ambient artwork initialized before replacement.** Same source files.
Constructor spy observed synthetic ambient keys/paths before keyless replacement. Staging now
selects its keyless initializer before inherited initialization, never production artwork configuration.
Regression: the `[artwork]` case independently forbids `artwork.configure` and verifies a ready keyless store.

**A03 — Medium: saved collection truncated and mislabeled.** `frontend/src/staging-movies.jsx`.
Actual React rendered `1 film rated` for `{total:101,next_after:1}` and no load-more control;
the page DTO had been discarded. Preserve total/cursor, implement scoped pagination and reject late pages.
Tests: `ratings retain total/cursor…` and `a discarded page cannot block…` exercise real components,
including an old transport that ignores abort; it cannot append/unlock/block newer work.

**A04 — Medium: duplicate rating/invitation mutations.** Same component, shared `MovieList` contract.
Two same-tick submits issued two PUTs/two POSTs; numeric pending keys mismatched `user:movie` keys.
Synchronous ref guards now admit one mutation; keys match controls and invitations disable while pending.
Test: `same-tick rating and invitation…` asserts one write each, disabled controls and no late A→B→A capability display.

**A05 — Medium: film-detail find action discarded selection.** Same component.
Actual “Find and rate this film” closed the dialog with empty search/zero search requests.
Pass an ephemeral `findRequest` through the existing Library contract. Test: `film detail find action…`
asserts the selected title and actual search call under React StrictMode.

**A06 — Medium: confirmed rating could retain stale search value.** Same component, `components/Library.jsx`.
Lookup data in search survived a save when the movie was outside the first loaded ratings page.
An explicit optional `ratingsRevision` refreshes the active search after confirmed mutation;
production's undefined default is unchanged. Test: `confirmed rating refreshes…` asserts the new Saved value.

**A07 — Medium: external sign-out could resume deferred PKCE.** `auth-session.js`, staging callback integration.
Pinned SDK incoming BroadcastChannel `SIGNED_OUT` during delayed storage restoration looked like normal
empty storage; queued PKCE then reauthenticated. Existing controller now records `sdk-observed` in
its logout presentation field; callback preparation rejects it. This is not remote revocation evidence.
Tests: actual-SDK `external SDK sign-out…` requires zero PKCE calls; controller test rejects late restore and allows fresh explicit sign-in.

**A08 — Medium: failed launcher spawn could hang shutdown.** `frontend/scripts/staging.mjs`.
Missing Python emitted `error` without `exit`; cleanup waited forever for the nonexistent exit event.
Track completion at launch, handle errors, interrupt readiness on shutdown and bound TERM→KILL cleanup.
`staging-launcher.test.js` covers a real missing executable, resistant child and repeated kill errors;
actual two-process startup/SIGTERM also released both listening ports.

**A09 — Low: fictional OTP rollover caused flaky tests.** `tests/staging_provider.py`.
A synthetic code fetched 2 ms before a 30-second rollover failed verification after the boundary.
Freeze only the fictional OTP step per reset; JWT/challenge-expiry clocks remain real. Boundary regression
also proves replay and expired challenges still reject. This asserts no hosted Supabase tolerance guarantee.

## D. Corrective commits and affected PRs

| PR | Corrective commit | Scope |
|---|---|---|
| 78 | `d2a7e12eb75ac27fa332b473d71419edbaa60b0b` | A01–A02, production-default initializer hooks and independent startup tests |
| 78 | `b225e701dff7367449f278e18ec6b8f7447f6000` | Keep schema-refusal expectation with startup redaction; independently passing intermediate PR |
| 80 | `148da5ec97b858eddd2cc7654c97642668a3545f` | A03–A06, five actual-component tests |
| 83 | `a8cbbee0be566055c09befcf02bd11a46ae95fa9` | A08, bounded process lifecycle tests |
| 84 | `0bb69ea8d2bb6d77330b2778726067dee139e187` | A09, fixture clock/replay/expiry |
| 85 | `3c6e35ec0bf32e81a754623bd8145552d02603f8` | A07, controller and pinned-SDK regressions |

Downstream PRs were consistently rebased. Overlapping later artwork/UI/forwarded-header fixes
were preserved in the earlier corrected implementation, not duplicated or dropped. No extra PR is needed.

## E. Code quality and maintainability

The separate compositions reuse one SDK/controller, existing transport, movie UI, policy,
ownership helpers and recommendation mathematics. No dependencies/lockfiles or second token store.
Removing duplicate preflight avoids a second engine; explicit initializer hooks preserve production defaults.
The launcher is longer because real failure completion/termination needs explicit evidence. Test fixture
code remains test-only; compressed private adapters warrant review, not a cosmetic rewrite or auth redesign.
The staging JS bundle size advisory remains nonblocking and unsuppressed.

## F. Security and final independent review

Reviewed verified signature/issuer/audience/session/AAL, current email/factors, scoped numeric identity,
group consent, SQL constraints/transactions, CORS/origin/body/rate limits, redaction and error paths.
Inspected and reran assertions for expiry during resolution, account switching, refresh during provisioning,
case/subject/process races, before/after-commit interruption, unknown outcomes, invitation revocation and rollback.
Final review rechecked the cumulative diff after conflict resolution, not the original passing revision.
Production entrypoints/authentication/default transports remain legacy; initializer hooks are code-only,
not environment switches. Docker/release startup excludes fictional providers; no staging routes are
mounted on `app.main`. No credential/ownership fallback, custom Auth DB access or relaxed MFA check.

## G. Executed evidence

Use only the disposable loopback `POSTGRES_TEST_URL`; overlapping suites are not additive totals.
Commands from root use `.venv/Scripts/python.exe`; frontend commands run inside `frontend`.

| Command | Result |
|---|---|
| `python -m pytest -q -p no:cacheprovider` | **1418 passed, 11 skipped**, existing deprecation warning; real isolated PG17. Hosted Linux expected two fewer Windows permission skips; use actual hosted ledger. |
| `npm test` | **576 passed**, zero failures/skips, including five actual Vite/React StrictMode UI tests. |
| `npm run build`; `npm run build:staging` | Both passed; staging 562.58 kB/gzip161.01 kB advisory, no threshold weakened. |
| `npx playwright test --config playwright.staging.config.js` | **11 passed**, 45.7s; real app/PG, fictional Auth; cleanup verified. |
| `npx playwright test`; `npx playwright test --config playwright.provisioning.config.js` | **36 passed** (4.0m) and **4 passed** (20.9s), respectively. |
| Focused startup/API/production tests; auth/resource/group/provisioning/concurrency tests | **97 passed** and **234 passed**, respectively; assertions independently inspected. |
| Controller/runtime/callback/recovery/email; launcher; provider regressions | **103**, **5**, **3** passed, respectively; overlapping with full suites. |
| `python scripts/check_pr_size.py --base BASE --head HEAD` | Every complete PR ≤500; final exact counts in section I/ledger. |

Real `main()` launcher reached ready, then SIGTERM completed and 5173/8011 were closed; schema init/check
used only a new DB in the owned disposable container. Browser fixture shutdown marker was `clean`.
New UI and cross-tab tests failed against defective code before correction; harness Windows URL/DOM setup
errors were corrected before counting results. No test was weakened or failure hidden by retrying.
Hosted [initial PR78 CI](https://github.com/aanxnd/movie-recommender/actions/runs/43387057598) found its schema-refusal test expected the pre-redaction exception; moving the same final-tree assertion from PR83 to PR78 fixed independent PR validation.
Existing artwork regressions read Trakt/Fanart resources; no Supabase account/configuration changes or hosted authentication tests occurred.
Hosted CI/size/Vercel links and actual final job counts are in #86's exact-head ledger; old checkpoint CI is historical.

## H. Remaining limitations

1. No unresolved actionable code defect found in final review; approval still requires actual final checks.
2. Initial-factor completeness, all removal, all-device loss and enrolled sensitive updates stay restricted.
3. Real Supabase Free shapes, SMTP delivery/spam/limits, native email/MFA/session acceptance remain unproven.
4. Exact cloud targets/origins, private isolation and $0 cost need owner approval; no hosted mutation/deployment.
5. Stages 24–26, full NIST assessment, original 16-stage audit and coordinated legacy/data cutover remain required.

## I. Exact merge order

Each row's base is the preceding row's head; PR78's base is main SHA in B. Branches remain open/unmerged.
Rebase/recheck after squash merges; do not merge all stacked diffs against main at once.

| PR | Branch | Final head | Changed lines | Hosted CI |
|---|---|---|---:|---|
| 78 | feat/staging-backend-composition | `b225e701dff7367449f278e18ec6b8f7447f6000` | 359 | [Run 43387913958](https://github.com/aanxnd/movie-recommender/actions/runs/43387913958) |
| 79 | feat/staging-recommendation-ownership | `3c6cc3445dc2e79fa9ddde880ef4782103067655` | 122 | [Run 43387914896](https://github.com/aanxnd/movie-recommender/actions/runs/43387914896) |
| 80 | feat/staging-movie-transport | `148da5ec97b858eddd2cc7654c97642668a3545f` | 319 | [Run 43387915067](https://github.com/aanxnd/movie-recommender/actions/runs/43387915067) |
| 81 | feat/staging-callback-dispatch | `bd01a374112af1f4e875c400cb3438a0541b3a04` | 131 | [Run 43387912287](https://github.com/aanxnd/movie-recommender/actions/runs/43387912287) |
| 82 | feat/staging-frontend-composition | `3cc39576ea1662f877a56c4a043793eb48be8dc9` | 187 | [Run 43387912744](https://github.com/aanxnd/movie-recommender/actions/runs/43387912744) |
| 83 | feat/staging-local-launcher | `a8cbbee0be566055c09befcf02bd11a46ae95fa9` | 278 | [Run 43387913942](https://github.com/aanxnd/movie-recommender/actions/runs/43387913942) |
| 84 | test/staging-provider-fixture | `0bb69ea8d2bb6d77330b2778726067dee139e187` | 365 | [Run 43387913659](https://github.com/aanxnd/movie-recommender/actions/runs/43387913659) |
| 85 | test/staging-browser-checkpoint | `3c6e35ec0bf32e81a754623bd8145552d02603f8` | 414 | [Run 43387912974](https://github.com/aanxnd/movie-recommender/actions/runs/43387912974) |
| 86 | docs/staging-integration-handoff | Exact final report head/count in PR86 ledger | ≤500 required |

No merges/closures, production changes, provider-account/configuration mutations, spending or Prompt 24 work.
