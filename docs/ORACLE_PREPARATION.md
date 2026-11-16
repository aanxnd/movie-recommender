# Oracle native preparation — no execution authorization

Selected: existing Vercel Hobby, non-paid Oracle A1, Neon Free, Supabase Free,
Docker Compose. Depends on owner-corrected PR111 `38f49c7`; no Cloudflare move.
Current Azure/legacy deployment and rollback remain active dependencies until
owner-approved cutover. No cloud resources/settings/accounts or secrets changed.

## Native image and immutable reference

`deploy/oracle/Dockerfile` is separate; it retains the exact existing Python3.14
multi-platform base digest and hash-locked runtime dependency versions. Installation
requires binary wheels; unavailable ARM64 wheels fail the build, never fall back
to source builds/unpinned dependencies. Non-root UID/GID10001 executes only
`python -m app.native_release`, after file-secret and exact reference validation.
Default Dockerfile/CMD, Azure workflow and Vercel configuration are unchanged.

Secrets mount at `/run/secrets/native_database_url` and `native_publishable_key`;
the native reviewed manifest and environment retain existing exact target/TLS
guards. No environment DB/key override, image secret, migration or legacy fallback.
Mounts/host permissions must let UID10001 read; Compose bind-secret mode settings
do not reliably change host ownership. No actual runtime secret was configured.

The prepared32M manifest is pinned to
`2afcd65695fb1dfa16aeb604caa212bdedfb352027e145ac1ec810e5c13199ef`;
all array/catalog/license hashes and inventory are checked offline and on startup.
Provide the verified versioned directory via read-only mount. Ordinary restarts
do not download, preprocess or write reference data. User records remain in Neon.

Operator-only local packaging (no publication):
`python deploy/oracle/reference.py --prepared EXISTING_DIRECTORY --output NEW_ARCHIVE.tar.gz`.
The archive has sorted files/fixed metadata/gzip time, exclusive output and a source
recheck. Incomplete output is untrusted; verify extracted data before selecting it.
Keep GroupLens attribution. Public redistribution permission remains unresolved;
do not publish an archive, embed it in a public image, or copy user databases.

Local sizing from PR111: prepared≈515MiB, peak Windows process≈621MiB; reserve
at least2GiB API RAM plus host/proxy/readiness overhead and preparation disk space.
These are not ARM performance or OOM guarantees. Emulated ARM validation is distinct
from actual A1 hardware acceptance. Native hardware, CA$0 capacity, grants, schema4,
TLS, mail, final security gates and deployment remain unapproved/incomplete.
