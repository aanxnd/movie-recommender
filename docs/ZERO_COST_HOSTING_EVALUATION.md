# Zero-cost hosting evaluation — decision proposed, deployment NOT approved

Verified 2026-11-15 (America/Toronto), against official public documentation and
main `f0543000058c9d195c2eb030763f287bcb7ee319` (PR91–110 merged). No infrastructure
provisioning, production credential access, hosted mutations, deployment or student-credit usage occurred.
Provider terms are evidence at this date, not a perpetual price/availability promise.

## Recommendation and financial verdict

Prefer **A: Cloudflare Pages static frontend + a non-paid Oracle Always Free A1 VM
+ Neon Free application PostgreSQL + Supabase Free Auth**. Use Docker Compose,
one native API worker and a TLS reverse proxy. Retain Vercel Hobby as a migration-
minimizing static alternative for an eligible noncommercial portfolio. All targets
remain TBD/unapproved. [Implementation blueprint](PRODUCTION_HOSTING_BLUEPRINT.md).

**Strict CA$0 is conditionally possible under published Free-account terms, but
NOT verified for an actual complete production deployment.** Oracle eligibility,
home-region capacity, exact meters, public TLS, SMTP suitability, backup recovery
and application release gates remain unproven. Do not deploy until established.
No option guarantees both continued availability and unlimited public traffic at
zero cost. If uninterrupted production service is essential, none qualifies here.
Quota refusal/outages are the permitted financial failure mode; paid fallback is not.

Never upgrade Oracle to PAYG to obtain capacity. Its non-paid account is the charge
boundary; a PAYG budget is not equivalent. Trial-only resources/credits are excluded.
Existing Azure credits offset charges, not metered usage; Azure is not recommended.
This proposal neither stops nor certifies the cost of existing Azure resources.

## Actual application requirements

| Area | Inspected behavior / requirement |
|---|---|
| Frontend | React 19/Vite 8, Node 24 in CI, pinned Supabase SDK 2.119.0. `npm ci && npm run build:native` produces `frontend/dist-native`; default `build` still selects legacy. Root `/` PKCE callback, no client pathname router; retain static fallback/security headers. No SSR requirement. |
| Backend | Python 3.14, FastAPI/Uvicorn, NumPy/Pandas, SQLAlchemy/psycopg, PyJWT/cryptography; hash-locked wheels. Explicit `python -m app.native_release`; existing Docker CMD is legacy `app.runtime` and must NOT be used for native launch. Linux ARM64 wheel/image compatibility needs a real build, not an assumption. |
| Reference data | Read-only memory-mapped 32M arrays, catalog and attribution; not user data or database rows. Verify pinned manifest/checksums before serving; no implicit Small fallback. Bake/mount once, rather than downloading on every request/ephemeral cold start. |
| PostgreSQL | Schema 4: numeric users, UUID identities, ratings, movie IDs, invitations, rate buckets, legacy credential rows retained pending retirement. Startup checks schema and registers catalog IDs; no startup migrations. Pool2, overflow 0 per process, checkout3 s/connect5s, statement5s/lock2s/transaction10 s. |
| CPU/admission | One recommendation at a time/process, cooperative20s budget, Uvicorn concurrency64. Profile100 ratings, group5 members/200 combined ratings, lifetime5,000 profiles. Public600/min global; recommendations30/min global and6/min/owner. These are ceilings, not capacity promises. |
| Auth | Browser calls Supabase directly; API verifies exact issuer/JWKS/ES256/audience, then fresh exact-subject user/email/factor evidence plus Neon ownership. Verified factors require signed AAL2. Standard bounded issued-token validity; no email-only bypass or immediate revocation promise. |
| Background/persistence | No mandatory recommendation queue/cron. Prepared data immutable; artwork cache disposable (bounded128MiB disk/24MiB memory). Persistent application data lives in Neon. Deletion journal/worker is dormant, not installed/selected and not required by the launch process. |
| Secrets/logs/network | DB credentials server-only; publishable key public; SMTP credentials only at Auth provider. No admin key for normal API. TLS443 ingress, outbound TLS to Neon/Auth/JWKS and optional licensed artwork; DNS/ACME egress. Disable raw URL/access/body/token logs; bounded local rotation, no paid log sink. |

Sources in repository: `app/native_release.py`, `native_app.py`, `database.py`,
`limits.py`, `historical.py`, `budget.py`, `frontend/vite.native.config.js`,
[native release](NATIVE_RELEASE.md), [frontend](NATIVE_FRONTEND.md),
[readiness](PRODUCTION_LAUNCH_READINESS.md), [account gates](ACCOUNT_OPERATIONS_READINESS.md).

## Reproducible local sizing (measured, not cloud capacity)

Run `.venv\Scripts\python.exe scripts/benchmark_hosting.py --prepared data/prepared/ml-32m-v1`
(POSIX: `.venv/bin/python`). It reads existing reference files only, verifies hashes,
imports native dependencies without starting an app/DB, recreates catalog mappings,
then takes one warmup and three serial measurements per synthetic reference profile.
No download, user data, provider call, service startup or filesystem output by script.

Windows 11 AMD64, Python 3.14.0, 16 logical CPUs; no CPU quota. CPU model/frequency not
measured. Existing OS file cache was not flushed. Manifest SHA256
`2afcd65695fb1dfa16aeb604caa212bdedfb352027e145ac1ec810e5c13199ef`.

| Measurement | Observed |
|---|---|
| Dataset | 32,000,204 ratings; 200,948 reference users; 87,585 movies |
| Prepared disk | 539,837,273 bytes =514.83 MiB; includes arrays/catalog/manifest/license |
| Imports / checksum / load+catalog | 2.909s /1.247s /0.582s; excludes DB startup, network, download and TLS |
| Peak working set | 253.68 MiB after catalog; **621.32 MiB** after recommendations (file-backed pages included) |
| 5-rating profile | 0.308/0.303/0.298s; median0.303s |
| 20-rating profile | 1.458/1.503/1.559s; median1.503s |
| 100-rating profile | 4.232/4.359/4.296s; median4.296s |

All cases returned10 results; CPU time approximately tracked wall time. Different
profiles vary: [earlier benchmark](recommendation-benchmark.json) had a100-rating
median5.677s. Small fixture peak142.19 MiB is NOT evidence of32M suitability.
Windows peak working set is not Linux cgroup RSS, committed memory or a bound.
HTTP handling, DB/readiness subprocess, kernel/page cache, proxy, artwork and burst
allocations are excluded. 512 MB hosts have no demonstrated headroom. **Estimate:**
start with a2 GiB API limit on a4 GiB+ host, one worker; measure Linux ARM64 cold/warm
RSS, OOM behavior and p95 before approval. One or two OCPUs, not a throughput guarantee.
Allow at least2 GiB disk for reference download/unpack staging, plus OS/images/logs;
raw32M preprocessing needs separate workspace and was not remeasured or rerun here.

## Backend provider comparison

All priced examples below are USD unless stated; zero converts to CA$0, nonzero
prices are not a Canadian quote. Free allocations must not be extended with credits.

| Provider | Continuing allowance / behavior | Financial and suitability verdict |
|---|---|---|
| [Oracle non-paid A1][o] | **2 OCPU/12GB total**, 1,500 OCPU-h/9,000GB-h monthly; home region;200GB combined boot/block, five volume backups,10TB outbound. | Best resource fit. [Non-paid account cannot charge absent upgrade][of]; card/phone verification and temporary holds apply. Capacity can be unavailable; idle reclamation after7days is documented. No fabricated keepalive load. PAYG would reintroduce overage exposure. |
| [Google e2-micro][g] | One shared-core VM in us-west1/us-central1/us-east1;30GB standard disk,1GB outbound. [0.25 sustained vCPU,1GB RAM][gm]. | Tight memory/CPU; [ordinary external IPv4 $0.005/hour][ip] ≈$3.65/730h BEFORE traffic. IPv6-only is not equivalent public reachability. Active paid billing exposes disk/egress/logs; no verified whole-stack hard CA$0 cap. Reject. |
| [Render Free][r] |[512 MB/0.1CPU][rc],750h/workspace/month;15min idle sleep, roughly1min wake, ephemeral disk; Free Postgres expires30days. | Native TLS/subdomain is useful, but no demonstrated32M memory headroom. Bandwidth/build overages can bill with a payment method; without one services suspend. Docs explicitly discourage production Free instances. Demo alternative only, not a hidden dataset downgrade. |
| [Koyeb Free][k] | One512 MB/0.1vCPU/2GB instance; Frankfurt/Washington;1h idle scale-to-zero; no volumes/worker service. | Insufficient measured headroom and severe CPU throttle; docs discourage production. [Pricing FAQ][kp] promises free-instance use but warns signup selects/prorates Pro, $29 card hold and no spending-limit feature. Do not sign up/enter billing as part of this research. |
| [Cloud Run][cr] | Request billing:180,000vCPU-s/360,000GiB-s/2M requests monthly aggregated by billing account; region/billing-mode dependent. | Technically fits with2 GiB+, min0/max1; repeated dataset cold-start cost and egress remain. Registry, builds, storage and logging are separate meters. A max replica count is not a free cap. Reject strict CA$0. |
| [Fly.io][fly] | New smallest always-on256MB machine $2.19/30days; stopped rootfs, volumes, egress also bill. | No generally available continuing free compute for a new account. Trials/grandfathered allowances do not qualify. |
| [Railway][rw] | Continuing Free: $1 usage credit/month, max0.5GB RAM/1vCPU/1GB ephemeral disk. | Recurring allowance exists, but credit-funded metered usage is not proof of no incremental spending; memory fails this workload. Hobby $5 subscription is paid. Reject; no student/trial substitution. |

Google now offers [service-specific spend-cap budgets][gc] including Cloud Run.
They are not merely alerts, but enforcement is delayed, in-flight work/fixed costs
continue, and overages still bill. Thus even these do NOT satisfy the exact-zero
requirement; neither do alerts, service quotas or delayed billing shutdown scripts.

## Frontend, database and email

| Service | Limits / controls / suitability |
|---|---|
| [Cloudflare Pages][cf] | Free static requests are unlimited; no Functions needed. [Free limits][cfl]:500 builds/month,1 concurrent,20min timeout,20,000 files,25MiB/file. Use free pages.dev hostname/TLS, no purchased domain. Do not enable paid Workers, R2 or add-ons. Preferred static target; terms/abuse enforcement and build limits still apply. |
| [Vercel Hobby][v] | Existing integration reusable:100GB Fast Data Transfer,10GB origin transfer,1M CDN requests; excess generally pauses access. Personal/noncommercial only. No paid plan/functions/gateway needed for direct native API. Existing protection/automatic promotion must be reviewed before public access, not silently removed. |
| [Netlify Free][n] |300 monthly credits with hard limit; sites pause at exhaustion, no Free overage charge. Deploys/traffic share that budget. Viable static alternative with netlify.app/TLS, less traffic/deploy headroom. Avoid paid/auto-recharge plans; verify account is current credit-based Free. |
| [Neon Free][ne] | Current live pricing/docs agree:1GB/project (20GB total),100CU-h/project/month,5GB transfer/project/month,10 branches, max2CU;5min idle scale-to-zero. Compute/egress exhaustion suspends compute; storage-growing operations fail at limit. Card not required. Six-hour/1GB-change restore history and one snapshot are not an offsite backup plan. |
| [Supabase Free PostgreSQL/Auth][s] |500MB DB/shared500MB RAM,50k MAU,5GB egress +5GB cached, two active projects; pauses after one inactive week. [Free excess restricts service, not billing][sc]. Auth and its database are the same project availability boundary. Moving Neon data here adds migration/coupling and requires changing the Neon-pinned release contract; no automatic consolidation. |
| [Aiven Free PostgreSQL][a] |1CPU/1GB RAM/1GB disk, backups, no card;20 connections/no pooler, no HA/SLA; may power off inactive services. [No automatic charge][af]. Credible alternative if Neon active-hours dominate, but region/restore/grants/TLS/version need acceptance and native DB pins need a separate reviewed change. Not an approved migration. |
| PostgreSQL on A1 | Fits proposed larger VM but competes for RAM/disk and shares compromise/reclamation/failure domain with API. Operator patches/backup/restore/monitoring replace managed services. TLS/least-privilege contract needs a separately reviewed provider change. Keep Neon initially. |

Historical owner report: Neon production≈37MB and2/10 branches; not a new hosted
measurement. Reference arrays must NOT be loaded into Neon/Auth storage. Old repo
planning values0.5GB are historical; recheck the actual account entitlement privately.

Neon minimum0.25CU ×730h =182.5CU-h, above100. Even at minimum size,400 active hours
consume the allowance, excluding extra branches/autoscaling. Frequent `/ready`,
public DB-backed browsing, rate-counter writes or external pings can prevent sleep.
Use `/health` for routine liveness; never fake activity to avoid provider suspension.
Monitor real CU/egress; accept refusal, not an upgrade. Aiven is a fallback design
to review if steady legitimate load makes Neon unsuitable, not an automatic switch.

Supabase [built-in mail][smtp] is non-production/team-address restricted; it cannot
support arbitrary public signup. Reuse existing Gmail custom SMTP only conditionally:
new SMTP initially30messages/h; actual project settings unknown here. [Gmail][gmail]
may block over500messages/day and other abuse patterns; this is not guaranteed sender
capacity. Outlook junk placement remains a launch gate. No paid domain/provider,
deliverability claim, email bypass or new send is authorized. [Auth rate limits][ar]
include MFA15/min/IP (burst30), token150/5min/IP (burst30); limits are not user quotas.
Approve public exact redirects/Confirm Email/recovery/MFA/abuse controls separately.

## Four complete architectures and decision matrix

Every option retains Supabase/Gmail limitations above; all require current account
gates and offline/owner backup copies. Conditional $0 excludes purchased DNS,
logging, registries, snapshots outside allowances and paid rescue capacity.

| Option | Cost and exposure | Fit, responsiveness, persistence, operations and growth |
|---|---|---|
| A: Pages + A1 + Neon |CA$0 only on unupgraded Free accounts/eligible resources; capacity/quotas may deny service. | One native API with2 GiB target; no normal host sleep, but idle reclaim possible; Neon wake adds latency. Persist reference volume/ACME; managed DB + encrypted offline dumps/rehearsal. Moderate Linux patching/security burden. Small intermittent population plausible; benchmark before promises. Later paid VM/DB migration requires a new budget. |
| B: Pages/Vercel + Render or Koyeb + Neon |CA$0 conditional Free selection/cardless Render; Koyeb signup/payment exposure. |512 MB is below measured working set;15min/1h sleeps and cold reference loads. Ephemeral reference rebuilt each time, no local user persistence. Managed TLS simplifies operations; no free worker for deletion. Not suitable for unchanged32M production; paid RAM or explicit product/data redesign needed. |
| C: Pages + Cloud Run + Neon |May total0 at low usage, but bills are possible; credits/caps do not guarantee it. |2 GiB allocation technically plausible, cold data loading penalizes first request, concurrency must match CPU gate. Managed TLS/operations, DB external, images/reference immutable; separate backup. Scales later, but quota-safe growth is not cost-safe growth. Financially disqualified. |
| D: A1 Compose frontend + API + PostgreSQL (or Neon) |CA$0 conditional non-paid A1; no managed LB/NAT/paid DNS. | Avoid static-host dependency; same-origin proxy would require frontend pin-contract change. Local Postgres reduces external CU limits but puts all data on reclaimable single host. Volume + encrypted off-host dumps essential. Most operator/security/restore burden; weakest failure isolation. Move DB out before adding replicas. |

Scores1–5 are engineering judgments, not provider guarantees or measured capacities.
Apply priority lexicographically: cost safety first, then security/reliability;
do not let an aggregate score hide a financial disqualification.

| Option | Cost safety | Security | Reliability | Ease | Performance | Scale | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| A |5*|4|2|3|4*|2|Preferred conditional investigation |
| B |3|3|1|4|1|1|Reject unchanged32M production |
| C |1|4|3|4|3|4|Reject strict financial requirement |
| D |5*|3|1|2|4*|2|Fallback only with operational review |

`*` Free-only account/availability and ARM performance unverified. Security scores
assume exact TLS/auth/ownership/patching controls; lower scores do not permit removal.

## Scale and orchestration

| Scenario | Likely bottleneck / required response (estimates) |
|---|---|
|10 active users | Sparse interactions can fit one worker; ten simultaneous recommendation requests cannot. Measure duty cycle, Auth calls, CU hours and cold starts. |
|100 active users | Activity spread across a day matters more than registration count. Polling can defeat Neon sleep; one CPU slot and30/min global admission reject bursts. Keep UI retries bounded/manual. |
|1,000 registered | Registration alone uses storage/MAU/mail, not continuous CPU.100ratings each means up to100k rating rows; index/WAL/audit size is unmeasured. Load synthetic rows into a disposable DB before claiming1GB suffices. |
|100 concurrent sessions | Idle sessions are not100 requests. Synchronized requests exceed Uvicorn64 and pool 2; protected requests also perform fresh Auth I/O. Expect bounded429/503, not100 simultaneous personalized calculations. Auth shared-IP limits/egress may dominate. |

Local medians imply a single serial slot's mathematical ceiling≈3.3/0.67/0.23
recommendations/s for these5/20/100-rating samples, ignoring all HTTP/DB/Auth work;
not production throughput. Existing30/min ceiling is lower in some cases. More
replicas multiply memory, DB pools and provider traffic. Do not increase workers
until CPU/RAM/connection budgets and CA$0 eligibility are re-established.
Optimize without weakening checks: cache immutable catalog/public artwork within
bounds, avoid polling, debounce user search, paginate, keep algorithm indexing,
and consider bounded owner+profile-revision result caching only after authorization
and invalidation review. Never cache current email/factor policy into a bypass.

**Kubernetes is unwarranted.** [Compose][dc] handles the few containers on one VM.
[K3s][ks] adds a control plane/datastore/patching overhead without another failure
domain; its baseline excludes application resources. [GKE][gke] control-plane free
credits do not pay worker compute/network/storage. Managed K8s, multi-node clusters,
LBs and persistent volumes do not produce free capacity. Reconsider orchestration
only after an actual multi-host availability requirement and approved paid budget.

## Official source register (checked 2026-11-15)

[o]: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
[of]: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
[g]: https://docs.cloud.google.com/free/docs/free-cloud-features
[gm]: https://docs.cloud.google.com/compute/docs/general-purpose-machines#e2_shared-core
[ip]: https://cloud.google.com/vpc/network-pricing
[r]: https://render.com/docs/free
[rc]: https://render.com/docs/compute-plans
[k]: https://www.koyeb.com/docs/reference/instances
[kp]: https://www.koyeb.com/docs/faqs/pricing
[cr]: https://cloud.google.com/run/pricing
[gc]: https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps
[fly]: https://docs.fly.io/about/pricing
[rw]: https://docs.railway.com/pricing/plans
[cf]: https://developers.cloudflare.com/pages/functions/pricing/
[cfl]: https://developers.cloudflare.com/pages/platform/limits/
[v]: https://vercel.com/docs/plans/hobby
[n]: https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/
[ne]: https://neon.com/pricing
[s]: https://supabase.com/pricing
[sc]: https://supabase.com/docs/guides/platform/cost-control
[a]: https://aiven.io/docs/products/postgresql/concepts/pg-free-tier
[af]: https://aiven.io/free-tier
[smtp]: https://supabase.com/docs/guides/auth/auth-smtp
[gmail]: https://support.google.com/mail/answer/22839
[ar]: https://supabase.com/docs/guides/auth/rate-limits
[dc]: https://docs.docker.com/compose/intro/compose-application-model/
[ks]: https://docs.k3s.io/installation/requirements
[gke]: https://cloud.google.com/kubernetes-engine/pricing
