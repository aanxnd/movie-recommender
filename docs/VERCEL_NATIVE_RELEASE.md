# Vercel native preparation — existing project unchanged

Retain the current Vercel Hobby project. No Cloudflare migration, Vercel API call,
production setting/build/root change, protection bypass or promotion occurred here.
Default `npm run build`, `main.jsx`, `dist` and `frontend/vercel.json` remain legacy
until a separately approved coordinated cutover. Azure rollback still matters.

`npm run prepare:native -- NEW_PATH_UNDER_REPO/.pytest-tmp/` creates an exclusive
offline source bundle containing only `frontend/public` and `frontend/vercel.json`.
It invokes the existing native build into a new output; no API/gateway/functions,
database fields, source maps, server keys or private test controls are packaged.
It uses `MOVELLE_NATIVE_TARGETS_FILE` and `MOVELLE_NATIVE_PUBLISHABLE_KEY`; examples
remain unapproved. A failed preparation is incomplete and must not be promoted.
The native Vite build disables ambient `VITE_*` injection; only explicit native
public pins/key enter the artifact. The default legacy build remains unchanged.

The manifest pins exact Vercel frontend/API/Supabase roots, all TBD until approved.
Generated CSP permits only self + that API/Auth pair for connections, required
artwork origins/data QR images, local fonts, no framing/base/form escape and no
callback referrer leakage. Root callbacks retain SDK PKCE and URL scrubbing; no
arbitrary redirect/query assurance. There is no custom route gateway to port over.
Build remains a distinct native artifact, not an environment fallback.

Before any future release, the owner must:

1. Confirm Hobby personal/noncommercial eligibility, usage/pausing and zero paid
   add-ons/functions. Verify all actual domains and deployment-protection settings.
2. Hold automatic production domain assignment/promotion in the existing project;
   verify existing production aliases remain on the compatible artifact. If the
   project cannot hold them, stop and authorize an explicit maintenance window.
   Do not change tracked `main`/default build to achieve a speculative rollout.
3. Approve exact public API origin and root frontend callback in Supabase, issuer/
   ES256/JWKS/audience/email/TOTP settings and Neon schema4/grants/backup/restore.
   Development `http://127.0.0.1:5173/` is not production authorization. No wildcards.
4. Verify the isolated bundle's `frontend` root, static `public` output and headers
   through an explicitly authorized preview. No `vercel deploy` command is run now.
   Do not assume Standard Protection protects or exposes every alias; inspect the
   actual scope, retain preview protection, and approve public access separately.
5. Test HTTPS/CORS, headers, callback/recovery, sessions, ownership/MFA, mobile and
   loading/error states against the native backend; never mix old/native traffic.
   Budget10/10 is exhausted: hosted signup/email/factor mutations require new approval.
6. Promote paired reviewed API/frontend artifacts only after all release gates.
   Roll back only to a compatible native/schema4 pair; no legacy credential fallback.

Offline bundle tests prove packaging/configuration properties, not hosted Vercel
protection, callback settings, mail delivery, A1 performance, CA$0 or production readiness.
