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
Frontend integration follows as separate reviewed PRs.

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
Known empty/omitted factor, initial-MFA, removal/recovery and sensitive-update
restrictions remain. Native authentication is active only in explicitly created
local staging applications/tests, never production. Offline provider fixtures do
not establish hosted Supabase behavior. No hosted tests/deployments are authorized.
