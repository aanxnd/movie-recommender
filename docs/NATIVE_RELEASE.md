# Separate native release — NOT APPROVED FOR DEPLOYMENT

The explicit backend command is `python -m app.native_release`; default Docker
`app.runtime`/`app.main` remain legacy and unchanged. The shared native factory
retains only allowlisted public GETs and attaches native-only protected resource
routers, provisioning and owned username settings. It carries body/rate/CPU/DB
limits, sanitized errors, no-store responses and exact-origin CORS (including
PATCH). Documentation endpoints are removed. There is no private gate dependency,
legacy credential issuance/fallback, automatic linking or startup migration.
Local/private entry guards and their gate remain intact.

## Configuration and execution gates

Nothing is approved by the example manifest. After separate owner target/cost/
release approval, supply a reviewed manifest in `MOVELLE_NATIVE_TARGETS_FILE`:
`approved:true`, exact HTTPS `frontend_origin`, exact `supabase_url` root, Neon
`database_host` and actual `database_name`. No guessed public domains are provided.
Set `APP_ENV=production`, `MOVELLE_NATIVE_MODE=native-release`, exact matching
`CORS_ALLOWED_ORIGINS`, `MOVELLE_NATIVE_PREPARED_DIR` (verified prepared dataset),
`MOVELLE_NATIVE_PUBLISHABLE_KEY` and server-only `MOVELLE_NATIVE_DATABASE_URL`.
The URL must match the reviewed host/database, use dedicated `movelle_native`
application credentials and exactly `sslmode=verify-full&sslrootcert=system&channel_binding=require`.
Do not put URLs/passwords in argv, manifests, browser configuration or reports.
Ambient PG overrides/proxy trust are rejected; request access logging is disabled.
Auth is pinned ES256/issuer/JWKS and audience `authenticated`, with fresh provider
current-email/factor evidence and numeric resource ownership. It retains standard
bounded token validity, not immediate session revocation.

Before any execution: prove CA$0 incremental capacity/no-overage; privately inspect
live schema, rehearse the additive schema-4 migration/backup/restore; review runtime
DB grants; approve exact frontend/API origins and matching Supabase root redirects;
review TLS and platform log redaction; complete hosted acceptance under a new budget.
Use the existing pinned image/dependency recipe and explicit alternate command;
do not change production CMD, Azure workflow or Vercel project as part of review.
Rollback must use a schema-4-compatible reviewed artifact with the same target pins.
Never revert to legacy credentials for native users or route traffic to both modes.
Native code/config availability is not activation approval. Full NIST/16-stage
assessment and remaining account/MFA restrictions still block public release.
