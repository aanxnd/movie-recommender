# Stage 23 full-system integration checkpoint

This is not Prompt 24, a production cutover, hosted acceptance or the final audit.
Baseline `main`: `4fa3d446a4c9d99d28eb959b3ee1a613cd19f03f`; merged PRs
69, 71 and 72–77 were verified. All new PRs remain subject to owner review/merge.

## A. Integrated architecture

The explicitly selected `staging/index.html` → `staging-main.jsx` composition uses
one Supabase SDK client, session controller, AuthProvider and authenticated transport.
The root callback scrubs its URL before SDK construction, waits for initial session
restoration through the same controller, and redeems once under its credential fence.
Existing signed recovery/email validators select only supported continuations.
Null PKCE hints remain ambiguous; old `email_confirmed_at` never proves signup flow.

`app.staging_entry:application` creates a separate FastAPI app. It removes all
legacy private handlers, retains bounded middleware/public catalogue operations,
and explicitly composes native profile/rating/invitation/recommendation routers.
ES256 verification and fresh native user/email/factor policy precede trusted
subject-to-numeric-profile resolution. Explicit atomic provisioning creates only
new accounts; no email/name/ID matching or legacy account claiming occurs.
Numeric IDs, ownership, group consent and unique case-insensitive names remain
server/database authoritative. Recommendation mathematics/MovieLens IDs are unchanged.

Only a disposable loopback PostgreSQL schema-3 database is accepted. Startup checks
schema version through a trusted check-only initializer and performs no migration. Explicit
local initialization is separate. Test fixtures own random schemas and synthetic
data; production Neon and the Supabase Auth database are never used.
Artwork uses keyless local fallbacks, not ambient production API keys or disk cache.
Production `app.main:app`, `app.runtime` and React `main.jsx` retain legacy behavior.
Shared components accept optional API injection; their production defaults remain.

## B. Review stack and implementation changes

Review/merge in dependency order, rebasing after squash merges. Each size is the
complete three-dot diff against its stated base, including docs/tests/configuration.
No files are removed; no dependencies or lockfiles change.

| PR | Base SHA | Head SHA | Added / deleted / total |
|---|---|---|---|
| [78](https://github.com/aanxnd/movie-recommender/pull/78) | `4fa3d446a4c9d99d28eb959b3ee1a613cd19f03f` | `b225e701dff7367449f278e18ec6b8f7447f6000` | 355 / 4 / **359** |
| [79](https://github.com/aanxnd/movie-recommender/pull/79) | `b225e701dff7367449f278e18ec6b8f7447f6000` | `3c6cc3445dc2e79fa9ddde880ef4782103067655` | 120 / 2 / **122** |
| [80](https://github.com/aanxnd/movie-recommender/pull/80) | `3c6cc3445dc2e79fa9ddde880ef4782103067655` | `148da5ec97b858eddd2cc7654c97642668a3545f` | 303 / 16 / **319** |
| [81](https://github.com/aanxnd/movie-recommender/pull/81) | `148da5ec97b858eddd2cc7654c97642668a3545f` | `bd01a374112af1f4e875c400cb3438a0541b3a04` | 118 / 13 / **131** |
| [82](https://github.com/aanxnd/movie-recommender/pull/82) | `bd01a374112af1f4e875c400cb3438a0541b3a04` | `3cc39576ea1662f877a56c4a043793eb48be8dc9` | 184 / 3 / **187** |
| [83](https://github.com/aanxnd/movie-recommender/pull/83) | `3cc39576ea1662f877a56c4a043793eb48be8dc9` | `a8cbbee0be566055c09befcf02bd11a46ae95fa9` | 277 / 1 / **278** |
| [84](https://github.com/aanxnd/movie-recommender/pull/84) | `a8cbbee0be566055c09befcf02bd11a46ae95fa9` | `0bb69ea8d2bb6d77330b2778726067dee139e187` | 365 / 0 / **365** |
| [85](https://github.com/aanxnd/movie-recommender/pull/85) | `0bb69ea8d2bb6d77330b2778726067dee139e187` | `3c6e35ec0bf32e81a754623bd8145552d02603f8` | 398 / 16 / **414** |

- 78: `app/staging.py`, `staging_database.py`, `staging_profiles.py`, real-PG API tests
  and `docs/STAGING_INTEGRATION.md`: native backend composition/isolation/ownership.
- 79: `app/staging_recommendations.py`, composition and HTTP regression tests:
  personal/group computation, scoped invitations, parallel provisioning and rollback.
- 80: `staging-movie-api.js`, `staging-movies.jsx`, Library/CatalogueExplore/GenreShelf/
  Recommendations/ArtworkProvider API injection and tests: reuse actual movie UI.
- 81: `staging-callback.js`, email/password callback adapters and tests:
  one private native PKCE continuation, no fake signup confirmation assertion.
- 82: staging runtime/app/main/CSS/HTML and read-only settings adapter/tests:
  one integrated account/movie UI outside production startup.
- 83: `app/staging_entry.py`, Vite config, `scripts/staging.mjs`, package scripts,
  ignore rule, launcher/entry tests and run documentation: explicit local startup.
- 84: fictional provider and real HTTP fixture/tests: offline signing/Auth simulation
  with disposable PG; no runtime test switch or packaged provider service.
- 85: browser spec/config/supervisor/teardown, rating/group wiring, PKCE restoration
  scheduling and tests: real integration defects corrected and teardown verified.
- Final dependent handoff PR: this report, active README/architecture/readiness/
  provisioning/run documents and CI staging build/browser checks. Its PR metadata
  records its exact base/head and final measured size; no self-referential SHA here.

## C. Functional acceptance matrix

“Local pass” below means actual React/Vite → FastAPI → PostgreSQL with **fictional
Auth HTTP responses**, local signatures and synthetic accounts. No row is hosted proof.

| Journey / invariant | Local evidence / limitation |
|---|---|
| Anonymous discovery/search | Pass; no profile or legacy credential created. |
| Signup / email callback | Native SDK call, URL scrubbing and single redemption pass; ambiguous signup provenance remains unproven. No genuine mailbox/delivery test. |
| Login, restore, explicit refresh, logout | Pass in real browser; failed login, expired/wrong-project tokens and provider outage deny. JWT lifetime after logout remains bounded, not immediately revoked. |
| New profile / username collision | Pass, including case collision, duplicate submission and two concurrent HTTP creations yielding one numeric profile. |
| Lost write acknowledgement | Pass; actual committed backend write is inspected without blind mutation replay or duplicate creation. |
| Ownership / switching | Pass; cross-account private routes deny, old workspace/settings clear, native profiles issue no legacy credential. |
| Ratings / personal recommendations | Pass through actual movie UI and native backend; persisted rating survives reload. |
| Groups / invitations | Pass through UI and HTTP tests; native scoped consent, invalid/revoked invitation denial, no raw peer ratings. |
| Password recovery / changes | Supported no-factor simulated flow passes; signed continuation required. Enrolled sensitive changes remain intentionally unavailable. |
| Current-address email change | Supported simulated flow passes with existing stored session; fixed restoration/redemption race. Hosted native confirmation remains untested. |
| TOTP challenge / additional factor | Pass for existing-factor synthetic accounts; QR/OTP verification and ephemeral setup cleanup exercised. |
| Backup-factor replacement | Accessible independent alternative passes simulated workflow. Physical device independence/real provider semantics unproven. |
| No-factor initial enrollment | Intentionally blocked: empty/omitted provider inventory is not authoritative absence. No bypass added. |
| Removal / all devices lost | Intentionally unavailable, including pending-factor cleanup; no email-only recovery. |
| Profile editing / lifecycle | Owned username displayed read-only; rename, disable/delete stay unavailable. |
| Malformed bodies / throttling / transactions | Backend tests pass: bounded body, invalid rating rollback, rate-limit 429, schema-2 refusal without DDL. |
| Desktop/mobile/keyboard | 1440px and 390px browser journeys pass; no horizontal overflow, keyboard navigation exercised. Not a complete accessibility audit. |
| Shutdown / rollback | Browser teardown waits for server shutdown and owned-schema cleanup; production entry untouched. Stop local stack and retain compatible data; no insecure fallback. |

## D. Security review

- URL codes/credentials never enter React status text or application logs. Existing
  SDK storage is the only token store; XSS/session theft risk remains as documented.
- Initial-restoration readiness only schedules redemption. Cryptographic claims,
  current provider evidence and backend ownership still decide permission. Logout
  during restoration aborts with zero PKCE requests; the credential fence remains.
- Unknown factor evidence fails closed, including AAL2 with incomplete inventory.
  AAL2 is not recent password proof, NIST certification or real-time revocation.
- No custom mailbox ledger, Auth-table reader/role, service-role/admin key,
  independent MFA service, legacy native fallback or client ownership assertion.
- Group invitation capabilities permit scoped computation, not peer data access;
  staged UI capabilities are ephemeral and cleared on account/generation changes.
- Explicit loopback DB validation rejects production/hosted/indirect libpq targets.
  Launcher passes allowlisted OS and staging variables, not ambient cloud secrets.
  Fixed origin, no-cache responses, native request limits and redacted failures remain.
- Production legacy routes/credentials and real numeric relationships are preserved.
  Superseded PRs 34–36 remain untouched. Full NIST SP 800-63B-4 assessment and the
  original 16-stage professional audit remain required; neither is performed here.

## E. Test evidence and pre-merge corrections

The original checkpoint's passing tests did not prove correctness: independent
[pre-merge review](STAGING_PREMERGE_AUDIT.md) found and corrected nine defects.
That report supersedes the original test ledger and records current per-PR SHAs,
findings, adversarial reproductions, full post-fix verification and merge conditions.
Current complete-PR counts are in B; final #86 SHA/count and hosted CI links are
recorded in its exact-head PR body to avoid self-referential commit hashes.

Full local post-fix suites: **1418 backend passed / 11 skipped** and **576 frontend
passed**. Production/staging builds passed; staging JS 562.58 kB/gzip161.01 kB has
an unsuppressed size advisory. Real browser/PG integration still uses fictional
Auth; it is not Supabase acceptance. Full browser results are in the audit ledger.
Existing Vercel Git previews build the legacy production composition, not native
staging. No required CI check was weakened; no lint/type-check script is configured.

## F. Staging deployment readiness and rollback

**Local-only executable configuration is ready for review. Cloud is not deployment-ready.**
Exact [local preparation/start/build instructions](STAGING_INTEGRATION.md) use:

- `MOVELLE_STAGING_DATABASE_URL`: private disposable loopback PG17 URL, database
  `movelle_staging_local`; never production Neon, a copied real dataset or Auth DB.
- `MOVELLE_STAGING_PREPARED_DIR`: verified local prepared reference directory.
- `MOVELLE_STAGING_SUPABASE_URL`, `MOVELLE_STAGING_PUBLISHABLE_KEY`: trusted approved
  development public project values; no service-role/password/SMTP key in Vite.
- Direct frontend build only: `VITE_STAGING_SUPABASE_URL` and
  `VITE_STAGING_SUPABASE_PUBLISHABLE_KEY`; dedicated output `frontend/dist-staging`.

From root, prepare reference data with
`.venv/Scripts/python.exe scripts/prepare_movielens.py --source data --output .pytest-tmp/staging-prepared`,
then explicitly run `python -m app.staging_entry init` and `check` using the venv.
From `frontend`, `npm run dev:staging` launches selected API 127.0.0.1:8011 and Vite
127.0.0.1:5173, checking `/health`, `/ready` and proxied `/api/ready`. Ctrl+C stops
both; no migration/container/cloud resource is created by the launcher.
Rollback: stop this isolated composition, select last reviewed compatible revision,
retain schema-3 data/constraints and recheck readiness. Never drop/backfill/claim
records or enable legacy fallback for native users as rollback.

Only `http://127.0.0.1:5173/` is approved for app origin/root PKCE redirects.
Preview/production origins, backend ingress and cloud DB destinations are **TBD**.
The current origin/DB guards intentionally reject cloud; owner selection followed
by reviewed explicit allowlists/TLS/CORS/private-ingress changes is required.
An artifact upload alone is not an authorized private deployment. Do not run the
production release workflow or alter the existing Vercel project's settings.

Local existing tooling/disposable Docker requires no new paid resource. The
repository is public; standard CI runners are [free under GitHub's documented policy](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
No new artifact/cache storage is configured. Private frontend protection is advertised free
on every plan by [Vercel's official announcement](https://vercel.com/changelog/protect-production-deployments-for-free-on-every-plan);
this does not establish this project's settings or a free private backend/database.
Cloud target isolation, quotas, egress, pausing, storage, cleanup and $0 incremental
cost must be established before any resource/configuration/deployment approval.

## G. Exact owner approvals needed next

1. Review/merge this dependency stack in order; no merge is performed by the agent.
2. Approve a bounded **separate hosted acceptance** plan for `movelle-auth-dev`:
   privately inspect public issuer/ES256, Confirm Email, redirects/Site URL, secure
   email change, factor limit/TOTP and Gmail/rate settings. Report sanitized findings
   only. Any needed setting change requires its own explicit approval.
3. If approved, create at most two new disposable accounts on owner-controlled
   private addresses, never touch pre-existing users. Maximum ten generated messages:
   two signup, at most one resend, two no-factor recovery, four old/new email-change
   confirmations, one enrolled recovery-denial probe. Stop on limits/errors; no retry
   loop. Real passwords/links/TOTP/secrets are privately entered, never recorded.
4. First inspect only sanitized factor-response shape/completeness on the new account.
   If absence remains unproven, stop provisioning/initial-MFA branches. Positive
   existing-factor fixtures do not authorize out-of-band enrollment to force success.
   Further MFA acceptance needs the separately reviewed supported design. Cleanup
   is restricted to these test-created records and separately approved supported
   operations; app factor removal remains unavailable. No administrative shortcut.
5. Separately choose exact private frontend/backend/DB targets, origin/callback list,
   privacy controls and documented $0 budget. Approve reviewed cloud compatibility
   changes and exact deployment actions before provisioning or publishing anything.

## H. Remaining blockers

- **Code/integration:** no failing test remains in the recorded final composition
  run. Read-only profile/lifecycle controls and the size advisory are limitations,
  not authorization to implement new account-management scopes.
- **Provider/security:** authoritative empty-factor completeness/initial enrollment,
  last-factor race protection/all-removal prohibition, all-devices-lost lockout,
  enrolled password/email reauthentication, ambiguous signup-flow provenance and
  actual Free response shapes remain unresolved or deliberately restricted.
- **Hosted email/configuration:** no real signup/recovery/email-change messages or
  factor mutations were performed. Gmail spam placement, delivery, sender/rate limits,
  abuse protection and exact current provider redirect/settings acceptance remain open.
- **Deployment:** no cloud target/origin/private backend isolation/$0 cost approved;
  current source is intentionally local-only. Existing automatic Vercel PR previews
  build the legacy entry; they do not resolve this gate. Main merges may auto-deploy
  that frontend; Azure release remains manual. Coordinate owner review accordingly.
- **Launch:** existing-user data/access disposition, coordinated schema-compatible
  production cutover, full NIST assessment and 16-stage audit remain later gates.

## I. Final verdict

**LOCAL INTEGRATION PASSED — HOSTED APPROVAL REQUIRED**

No hosted account/configuration/production changes, migrations, manual deployment,
paid services, PR merges/closures or Prompt 24 work were performed. Native production
authentication remains dormant. Owner review and the explicit approvals above are next.
