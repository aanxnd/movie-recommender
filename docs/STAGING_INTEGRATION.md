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

This first dependency provides ratings/profile/invitation HTTP operations.
Recommendation/group and frontend integration follow as separate reviewed PRs.
Known empty/omitted factor, initial-MFA, removal/recovery and sensitive-update
restrictions remain. Native authentication is active only in explicitly created
local staging applications/tests, never production. Offline provider fixtures do
not establish hosted Supabase behavior. No hosted tests/deployments are authorized.
