# Stage 23 integration checkpoint — not Prompt 24

Baseline main: `4fa3d446a4c9d99d28eb959b3ee1a613cd19f03f`, merged PRs 69,
71 and 72–77 verified. Production `app.main:app` and React `main.jsx` remain
legacy-only. Explicit staging composition is separate; no environment flag
switches production authentication.

`create_staging_app` accepts an explicit disposable loopback PostgreSQL URL,
prepared MovieLens path and trusted public Supabase configuration. It requires
schema 3 before startup, retains public catalogue/recommendation algorithms,
bounded middleware and health/readiness, removes every legacy private handler,
and composes native provisioning/ownership dependencies. Ambient `DATABASE_URL`
cannot select its database. Local database names start `movelle_staging_`;
random isolated CI schemas in the `disposable` database are also permitted.
No hosted database URL or startup migration is accepted. Native personal artwork
uses native authentication, not the production legacy handler.

Staging provides ratings/profile/invitation and personal/group recommendation HTTP
operations. Computation reuses the unchanged production mathematics; database
transactions close before CPU work. Group consent uses the existing scoped native
invitation helpers, never legacy authentication. Raw peer ratings stay private.
Frontend integration is included in the dependent review stack below.

The separate staging movie workspace reuses Library, CatalogueExplore,
Recommendations and ArtworkProvider through explicit API injection. Their default
production transport is unchanged. Staging sends private calls through the shared
native lease/controller; it rejects legacy token/header overrides, never restores
`movelle.identity.v1`, and does not replay mutations. Numeric display identity comes
only from authenticated `/users/me`. Workspace state is discarded on generation/
status changes. Existing raw-rating metadata, invitation capabilities and scoped
group calculation are retained. Local staging disables external artwork keys and
disk caches rather than silently using ambient production provider configuration;
fallback covers still work. Personal Fanart-key UI remains unmounted in staging.

The staging root has one PKCE consumer. It scrubs first and redeems once through
the shared SDK, then reuses the existing recovery/email validators. A recovery
hint still requires signed recovery AMR/session evidence; only that private
continuation enables the password form. A null hint is ambiguous: email change
requires its signed method and fresh user state, otherwise confirmation stays
unproven. No signup success is inferred from an old confirmation timestamp. Raw
SDK response data never reaches React, and no publicly callable recovery-accept
method or new verification ledger is introduced. The ordinary dormant standalone
consumers preserve their contracts and share the existing once-only boundary.
The staging-only scheduling hook waits for the existing controller's initial
restoration before credential fencing/redemption. It does not establish identity;
logout/unavailable states abort without redemption. This fixes a real stored-session
email-change callback race without weakening the credential fence.

The separate `staging/index.html`/`staging-main.jsx` entry composes one native
runtime and AuthProvider with signup/login, confirmation dispatch, profile setup,
read-only profile settings, email/password services, TOTP challenge/enrollment and
lost-device screens, plus the movie workspace. It accepts only the approved local
origin and `/api`. `VITE_STAGING_SUPABASE_URL` and
`VITE_STAGING_SUPABASE_PUBLISHABLE_KEY` are explicit public inputs; ambient
production Supabase frontend variables cannot select this project. A dedicated
Vite configuration/launcher follows; normal `npm run build` still builds the
legacy production entry. Native SDK storage/controller remain the sole session
owner. Callback scrubbing precedes SDK construction; a bootstrap subscription uses
the same controller, not another auth store. Read-only settings adapt the owned
username to a display snapshot; `revision=read-only` is never a write precondition
or ownership assertion. Username editing/account lifecycle operations stay disabled.

## Explicit local run/build (no hosted approval implied)

Privately set `MOVELLE_STAGING_DATABASE_URL` to a disposable loopback PostgreSQL
database named `movelle_staging_local` (or another `movelle_staging_` name),
`MOVELLE_STAGING_PREPARED_DIR` to verified local prepared MovieLens, and
`MOVELLE_STAGING_SUPABASE_URL`/`MOVELLE_STAGING_PUBLISHABLE_KEY` to the approved
development project's public configuration. Never paste the database URL into
commands/reports. No production database/SMTP/administrative credential is needed.

From repository root, explicitly initialize/check only that local database:
`.venv/Scripts/python.exe -m app.staging_entry init` then
`.venv/Scripts/python.exe -m app.staging_entry check` (POSIX: `.venv/bin/python`).
Prepare repository Small locally if needed:
`.venv/Scripts/python.exe scripts/prepare_movielens.py --source data --output .pytest-tmp/staging-prepared`.
From `frontend`, run `npm run dev:staging`. The dedicated launcher checks ports,
starts only loopback native API 8011 and frontend 5173, verifies health/readiness
through the proxy, and stops both on Ctrl+C or component failure. It passes an
allowlisted OS/staging environment, not ambient production/cloud secrets. API
access logs are disabled and preflight/unexpected failures have redacted errors.
It does not create a database/container, send email or configure hosted services.
Do not click hosted account mutations until the exact test plan is approved.

`npm run build:staging` uses the explicit staging HTML/config and writes only
`frontend/dist-staging`; normal `npm run build` still writes the production build.
For a direct staging build, supply the two public `VITE_STAGING_*` variables above.
The current composition deliberately accepts only the approved local origin;
cloud origins/targets and a reviewed host/database allowlist require owner approval.

## Local integration evidence categories

`tests/staging_provider.py` is a fictional HTTP Auth simulator with ephemeral local
ES256 keys and published synthetic OTP vectors. It is not a second application
authentication service and is never imported by runtime/release code. The fixture
owns a random schema in a validated disposable loopback PostgreSQL database. Real
HTTP requests exercise the actual staging app, signature/current-email/AAL checks,
provisioning, numeric ratings and shutdown. Only test code redirects the pinned
project's transports to the simulator; no runtime environment flag permits this.
Provider shapes, PKCE, MFA and mailbox events here are **simulated**, not proof of
Supabase Free behavior, actual mail delivery or authenticator independence. Normal
staging uses the unchanged TLS-pinned hosted provider transports, after approval.
Both local launchers disable forwarded-header trust; no client header selects IP.
Known empty/omitted factor, initial-MFA, removal/recovery and sensitive-update
restrictions remain. Native authentication is active only in explicitly created
local staging applications/tests, never production. Offline provider fixtures do
not establish hosted Supabase behavior. No hosted tests/deployments are authorized.

The [checkpoint report](STAGING_CHECKPOINT_REPORT.md) records 11 real Chrome
composition journeys, PG isolation/cleanup, regression evidence, exact review
commits and remaining approval gates. CI also builds staging and runs this isolated
browser checkpoint; its fictional provider is never hosted acceptance evidence.
