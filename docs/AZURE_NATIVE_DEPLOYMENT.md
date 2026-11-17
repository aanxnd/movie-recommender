# Azure native preparation — KEEP THE EXISTING APP STOPPED

Owner decision, November16,2026: retain Vercel, existing Azure Container Apps
Express/Consumption, Neon and Supabase. Oracle is no longer the selected host.
No restart, resource/settings change, image publication or hosted migration is
authorized here. The old manual release workflow is paused at publish/deploy;
its legacy runtime is a rollback artifact, not a native-auth deployment shortcut.

## Image and configuration

`deploy/azure/Dockerfile` keeps the existing Python3.14 digest and hash-locked binary
dependencies. Build `linux/amd64`; the default release includes only app/runtime
dependencies plus the exact verified32M reference. UID10001 runs
`python -m app.azure_release` → `app.native_release`; no legacy routes, downloads,
startup migrations, Auth admin key, background worker or extra server is added.

Future operator build (LOCAL ONLY; no push/deploy authorization):
`docker buildx build --platform linux/amd64 --build-context reference=EXISTING_PREPARED_DIRECTORY --load -f deploy/azure/Dockerfile -t movelle-azure:review .`
The named reference context must contain only the checksum-bound32M inventory.
Missing/Small/corrupt data fails the release build. The `runtime` target is only
an incomplete CI validation image; it must never be published or deployed.
`python -m app.reference` is the shared offline verifier/packager; Oracle's old
image interface remains compatible. No algorithm, dataset or dependency pin changes.

The reviewed native target manifest may be supplied as exactly one nonempty
`MOVELLE_NATIVE_TARGETS_JSON` or `MOVELLE_NATIVE_TARGETS_FILE`; bounded JSON,
duplicate-key, exact-origin/issuer/Neon/TLS/role guards are identical. JSON contains
only approved nonsecret targets. ACA secret references supply the native runtime
DB URL and public Supabase key; no secret is baked into the image or manifest.
See [native configuration](NATIVE_RELEASE.md); actual targets remain unapproved.

## Storage, memory and cold starts

The immutable image includes the515MiB reference and upstream README/license;
there is no per-restart archive download/preprocessing or reference-storage service.
GroupLens permits transformed redistribution under the same noncommercial license
conditions; retain attribution and obtain owner publication approval before GHCR push.
No archive/image is published by local tests. Accounts, ratings, invitations, identity
mapping and quotas live in Neon; only disposable caches/temp files use container disk.

One worker,1vCPU/2GiB is the initial target, not a capacity guarantee. Image pull,
hash verification, mmap loading and Neon cold connection contribute to latency.
Actual AMD64 startup/RSS, readiness, image-pull latency, concurrency10, OOM and
scale-zero/wake acceptance must be distinguished from local fixture evidence.
Local Docker AMD64 evidence: real32M release built successfully; uncompressed image
size1,186,311,597bytes (registry transfer size unmeasured). A one-worker1CPU/2GiB
network-disabled SQLite fixture reached health/search in11.083s with285,712KiB peak
RSS and rejected a legacy bearer. Separate32,000,204-rating recommendation probe
returned10 results in2.69s with523,756KiB peak RSS. mmap pages are demand-loaded:
startup RSS is not working-set capacity. These samples exclude registry pull and
hosted Neon/TLS latency and do not establish concurrency10 or cold-wake acceptance.
Existing DB pool pre-ping,2 connections/no overflow,3s pool and5s connect limits
handle stale idle connections; failed/in-flight transactions are not silently replayed.
The inherited startup checks schema4 and idempotently registers reference movie IDs
in Neon (INSERT/ON CONFLICT, not DDL); this does perform bounded database writes.
Rehearse its transaction deadline and runtime grants before restart. No user reset.

## Mandatory activation hold

Microsoft support must confirm this subscription's spending-limit/out-of-pocket
protection before any production restart. Owner reports approximatelyCA$138 credit,
expiring October4,2027; these are not independently verified billing guarantees.
Min0/max1/concurrency10 reduce consumption; they are not a hard spending cap.
No paid upgrades, Marketplace products or new infrastructure. A stopped app does
not wake on HTTP: explicit owner-approved restart is a later action, then HTTP
scale-zero/wake must be tested. No external uptime pings or periodic DB readiness
polling should keep it warm. Production remains dormant/stopped during preparation.
Existing SDK refresh targets Supabase; authenticated browser session-generation
changes can legitimately recheck the Azure profile. No Azure keepalive is added.
Test idle scale-zero with tabs closed/logged out and account for real browser/abuse
traffic; do not remove security checks to manufacture a zero-usage result.
