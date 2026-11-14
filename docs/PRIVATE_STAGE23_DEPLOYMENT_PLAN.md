# Private Stage 23 deployment proposal - NOT APPROVED FOR EXECUTION

No resource was created, configured or deployed. Production authentication stays
dormant. This prepares private owner testing, not public rollout or the final audit.
The MFA implementation/acceptance and this plan require separate merge review.

## Exact existing resources and evidence

| Resource | Existing identity | Evidence / boundary |
|---|---|---|
| Repository / images | `aanxnd/movie-recommender`; `ghcr.io/aanxnd/movie-recommender` | Repository workflows; do not dispatch the production release workflow. |
| Vercel | Existing `movie-recommender` project in `anands-projects-77218544`; Hobby | Project/team names in existing Vercel check URLs; Hobby owner-confirmed. Protection settings were not inspected. |
| Azure API | `movie-recommender-api` in `movie-recommender-rg` | Workflow constants and owner verification. Preserve this live app. |
| Azure environment | `managedEnvironment-movierecommende-9747`, Canada Central, Express/Consumption | Owner-verified metadata; no live Azure CLI/connector available here. |
| Azure subscription | Active Azure for Students | Owner-verified. Remaining credits/free grants not displayed. |
| Neon | `movie-recommender`, project `weathered-poetry-89387942` | Owner-verified; actual plan/quotas not yet verified. |
| Neon production branch | `production`, `br-tiny-bonus-b4ec6f9z` | Preserve untouched. No private branch exists/has been selected. |
| Supabase | Existing `movelle-auth-dev`, pinned `jsbulnrcxtvslvvxjizq.supabase.co` | Prior campaign/owner evidence; no new project, privileged key or Auth DB access. |

Azure displayed cost **1.36**, forecast **2.45**, attributed to the existing API.
Currency/reporting period were not independently verified. Zero free services
shown as over limit does not establish remaining Container Apps allowance.
Student credits are not proof of zero incremental spending.

## Recommended isolated architecture

Owner browser -> Vercel-authenticated preview -> server-only same-origin `/api`
gateway -> separate private Azure app -> separate empty Neon development branch.
Supabase browser SDK continues native signup/confirmation/password/TOTP. Every
backend private request independently checks Supabase evidence and local ownership.

**Proposed, not existing/approved:** Neon schema-only root branch `private-stage23`;
Azure app `movie-recommender-api-private`; Vercel source branch
`private/stage23-owner-test`. Names are review candidates, not discovered resources.
Prefer the existing Azure environment only if a second isolated app is supported
and its shared settings/logging do not change production or add charges. Otherwise
a separate Express environment would be a new, separately approved resource.

Do not use a zero-traffic revision/label on the live app. Current
[Express documentation](https://learn.microsoft.com/en-us/azure/container-apps/express-overview)
supports single-revision rolling replacement, not labels/traffic splitting or
Easy Auth. Deploying the candidate there could replace production. Do not change
the live app's environment mode, ingress, secrets or scaling to accommodate staging.

Use the same public MovieLens Small reference as acceptance for the first private
session. Historical ratings remain read-only files, not personal Neon data. Larger
32M capacity/cold-start/egress must be costed separately; no algorithm change.

## Private access: both frontend and API must be protected

- Require Vercel Authentication on the chosen preview and every URL serving it;
  owner/project access only, no bypass exceptions or public share links. Verify
  signed-out denial before enabling native bootstrap. Do not change the production
  domain. Vercel now offers authentication protection on every plan at no extra
  feature charge, including [all deployments](https://vercel.com/changelog/protect-production-deployments-for-free-on-every-plan);
  preview protection is sufficient here. Confirm the actual Hobby account controls.
- Preview protection does not protect a directly reachable Azure API. Proposed
  private gateway uses one separately approved server-only random gate credential;
  Vercel overwrites any caller-supplied gate header and forwards only approved paths
  to one fixed TLS backend. Azure's private entry rejects missing/invalid gate
  credentials before application access. Never place it in VITE/browser bundles,
  URLs or logs. This outer gate grants no Supabase identity or resource permissions.
- No gateway, gate secret or private entry exists yet. Implement/review them in
  focused PRs before deployment. Do not substitute CORS, an obscure hostname or a
  frontend login screen for access control. Direct API calls with even a valid
  Supabase JWT must still fail without the private gate.
- Do not buy Vercel password protection, static egress, private endpoints, VPN,
  Front Door or a new domain. Azure private endpoints may introduce management
  charges. A private network-only API would also require an approved connectivity
  path from Vercel; none is established here.

## Database and configuration requirements

Create no ordinary data-copy branch from production. Neon supports
[schema-only roots](https://neon.com/docs/guides/branching-schema-only), including
Free within its limits. After explicit approval, select schema-only creation and
verify empty personal tables before use. Never copy production users, credentials,
ratings, invitations, identities or backup data into private testing.

The new branch must have its own verified endpoint and branch-specific application
credentials, separate from migration credentials and production. Pin that branch
identity/host/database in the reviewed private bootstrap; TLS is mandatory. Apply
existing schema3 migrations only there after migration approval. No production
connection, migration, linking, sequence reset or data deletion is authorized.

Current staging deliberately enforces loopback database/origin guards. Do not
disable them or deploy `staging.mjs` unchanged. A separate reviewed private entry
must compose the same native routers, schema preflight, limits and authorization,
without legacy issuance/fallback. Production `app.runtime`/`main.jsx` stay unchanged.

| Configuration | Required private value / location |
|---|---|
| Frontend origin | Exact HTTPS preview origin: **TBD, unapproved** until assigned and owner-approved; never infer it or use a wildcard. |
| Backend origin | Exact new private Azure app HTTPS origin: **TBD, unapproved**; fixed gateway destination, never client-selectable. |
| Callback | Exactly approved frontend origin plus `/`; native PKCE/S256, scrubbed root, no arbitrary next/redirect. Add it to Supabase only after explicit hosted-setting approval; no Site URL/SMTP change assumed. |
| Public SDK values | Existing `VITE_STAGING_SUPABASE_URL`/`VITE_STAGING_SUPABASE_PUBLISHABLE_KEY`, private preview scope only; never admin/service-role/Neon/gate credentials. |
| Private runtime inputs | Proposed `MOVELLE_PRIVATE_DATABASE_URL`, `MOVELLE_PRIVATE_FRONTEND_ORIGIN`, `MOVELLE_PRIVATE_GATE_SECRET`; not implemented or stored here. Private bootstrap must validate an explicit owner-approved allowlist, not arbitrary environment destinations. |
| Backend Auth | Existing pinned dev issuer/JWKS, authenticated audience, ES256, public publishable key; verified current email, approved factor contract, signed AAL2 for verified TOTP. |
| Vercel build | Proposed private-only staging build/output `frontend/dist-staging`, after origin support is reviewed. Existing production build/output remains legacy. |
| Azure artifact | Reviewed immutable GHCR digest and explicit private entry; no dispatch of the workflow hardcoded to the production API. |
| Logs | Redacted errors; no access URLs/query strings, email bodies, passwords, JWTs, OTPs, seeds, private gate or DB credentials. No new analytics/paid log sink. |

## Cost gate - $0 target is NOT yet established

| Component | Expected incremental cost only if prerequisites hold | Unresolved evidence |
|---|---|---|
| Vercel Hobby preview/protection | $0 within Hobby limits; no add-on | Verify actual project protection, function/proxy quotas, eligibility and usage. |
| Neon private branch | $0 on Free within shared quotas; no upgrade | Actual plan, remaining branch/root/storage/compute/egress allowances. All branches share project usage. |
| Azure private app | $0 only if verified remaining free allowances cover all activity | Current cost already nonzero; remaining grant/currency/period/meter/egress/logging unknown. |
| Supabase dev / Gmail | No plan/provider change | Existing Free/SMTP limits and controlled campaign email budget still apply. |

Current [Neon plan documentation](https://neon.com/docs/introduction/plans) lists
Free100 CU-hours/project/month,1GB storage/project,10 branches and5GB transfer;
schema-only roots have a separate limit of3 on Free. These are published limits,
not evidence that this project is Free or has room. No paid overage is approved.

Azure's [Consumption billing](https://learn.microsoft.com/en-us/azure/container-apps/billing)
shares monthly180,000 vCPU-seconds/360,000 GiB-seconds and request allowances across
the subscription. Illustratively, one1-vCPU/2GiB replica active for4 hours consumes
14,400 vCPU-seconds and28,800 GiB-seconds; this is usage arithmetic, not a $0 quote.
Existing applications, cold starts, logging and network usage also matter. Proposed
private limits: min0/max1 replica, one worker, finite request/body/rate limits and
a bounded owner session with explicit stop. Verify those controls are supported.
Alerts, forecasts, credits and scale-to-zero do not enforce a hard zero-cost cap.
A request rejected by application code can still consume Azure compute; the
private gate protects access, not billing. Do not treat it as a spending limit.
**Do not create or deploy private Azure compute while $0 remains unproven.**

## Smallest remaining read-only owner checks

1. Azure subscription Cost Management: confirm billing currency/period, meters behind
   the1.36/2.45 display and remaining Container Apps CPU/memory/request allowances;
   include network/logging charges and offer spending controls. Express app/environment
   views: confirm second-app isolation, supported max-replica/stop controls and quotas.
   Return only sanitized usage/settings, never full configuration/secrets.
2. Neon project console: confirm plan, remaining project/root/branch/storage/CU/transfer
   quota, and schema-only creation availability. Approve the new empty branch name;
   do not create it yet. Existing production branch remains untouched.
3. Vercel project: confirm the exact project identity and preview authentication/access
   settings without changing them. Confirm the future preview's exact assigned origin
   before requesting redirect changes; production remains outside this plan.

## Reviewable execution sequence, after separate authorization

1. Review #87/#88/#89 and acceptance results. Merge only when separately authorized;
   rebase each stacked PR after its parent merge and rerun full-diff size/CI checks.
2. Resolve the cost gate and approve exact proposed resources, isolation, quotas,
   private origins and bounded test window. If $0 cannot be established, stop cloud
   preparation at this plan; existing loopback staging remains the $0 testing option.
3. Review dedicated private bootstrap/gateway/configuration PRs (each <=500 lines),
   including signed-out preview denial, direct API denial, token/header redaction,
   no legacy routes, correct JWT/email/AAL/ownership and wrong-target failure tests.
4. Only after explicit hosted approval: create the empty private Neon branch, initialize
   schema3, configure separately protected private app/preview, and review the exact
   image digest and assigned origins before any native SDK access. Do not use the
   production GitHub environment/workflow to deploy the private app.
5. Approve/save the exact root redirect and private configuration. Retest signed-out
   access, direct API bypass, signup/profile/TOTP/AAL2/rating/recommendations and logout.
   Any additional automated email/factor campaign needs a reconciled budget first.
6. Stop only the new private app at the end of its approved window; keep production
   routing/data untouched. Revoke private access/credentials only with owner approval;
   do not delete production resources or use destructive rollback.

The desired result is a private, fully functioning owner preview. This proposal
does not establish cloud readiness, perform the final production audit, activate
production authentication or authorize any deployment.
