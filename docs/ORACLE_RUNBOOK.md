# Oracle/Vercel runbook — PREPARATION ONLY, execution not authorized

Authoritative future Oracle procedure; current Azure procedure remains DEPLOYMENT.md
until cutover. Dependencies: PR111 selection → native image → this Compose proposal.
No hostname/IP, VM, account, credential, schema, certificate or promotion is approved.

## Before any future operation

Owner privately verifies non-paid Always Free A1 capacity/eligible meters (no PAYG,
trial/credit consumption), Vercel Hobby eligibility/caps, Neon quotas/TLS/grants,
Supabase project/mail and exact frontend/API origins. Reclamation downtime is
accepted; no paid rescue. Existing Azure resources remain unchanged; their charges
are not eliminated by preparing another provider. Review production readiness and
full NIST/16-stage audit requirements; no production audit begins in this task.

Use a reviewed Linux ARM64 image digest/local image ID, never `latest`, and existing
verified32M directory. Do not publish datasets; resolve GroupLens permission first.
`deploy/oracle/render.py --targets REVIEWED_JSON --output NEW_DIRECTORY` runs offline
and refuses existing output, duplicate keys, unsafe origins and proxy injection.
Until explicit owner target approval, examples remain `approved:false`.

## Compose inputs (external private file, no secrets in argv or repository)

`MOVELLE_ORACLE_IMAGE`: exact reviewed local `sha256:...` after image load/inspection;
`MOVELLE_ORACLE_CONFIG`: generated nonsecret config directory;
`MOVELLE_ORACLE_REFERENCE`: verified versioned32M directory;
`MOVELLE_ORACLE_FRONTEND_ORIGIN`: exact approved Vercel HTTPS origin;
`MOVELLE_ORACLE_SECRETS`: private directory containing file-only native DB URL/key;
`MOVELLE_ORACLE_TLS`: private certificate-pair directory with `current/`;
`MOVELLE_ORACLE_ACME`: HTTP-01 webroot. All host paths must exist; bind mounts refuse
automatic creation. Host permissions must grant container10001 secret reads and
101 TLS reads. No Docker socket/admin credential/cloud IAM role in either container.

Review with `docker compose --env-file PRIVATE_ENV -f deploy/oracle/compose.yaml config --quiet`.
Do not print expanded configuration or secrets. This is not authority to run `up`.
Only proxy443/80 publish. Port80 serves GET/HEAD ACME challenge files and otherwise
redirects to a fixed approved HTTPS root, dropping query/path. No cleartext API.
API has one worker/CPU,2GiB,128PIDs, bounded tmp/cache/logs; proxy is non-root,
0.25CPU/128MiB/64PIDs. Finite three failure restarts; operator intervention after
failure/reboot, never an unbounded restart loop. Normal bridge permits needed Auth/
Neon egress; API has no host port. Forwarded identity is stripped/ignored: per-IP
quotas aggregate at the proxy until a separate exact-hop anti-spoofing review.

## TLS issuance/renewal design — do not issue certificates now

Pin/review Certbot≥5.4 and an exact owner hostname or public IPv4. No guessed DNS,
self-signed production TLS, paid domain or default catch-all host. For IPv4, use
the supported `--ip-address` plus `--preferred-profile shortlived`; six-day lifetime
requires tested automatic renewal. For DNS use the exact owned name. First rehearse
against ACME staging only after separate network authorization; no certificate
request occurs here. Initial standalone HTTP-01 may run while Compose is stopped;
renewal uses webroot without opening an HTTP application route.

A host-only reviewed deploy hook must validate hostname/IP, expiry and cert/key
match; publish a new restrictive-owner certificate pair under a versioned TLS
directory; serialize atomic `current` replacement and proxy config-test/reload;
roll back that symlink if testing fails. Never mount Certbot's writable state or
Docker socket inside proxy/API. Retain the previous pair until validation passes.
Timer, hook, actual issuance, renewal/reboot and expiry alert acceptance remain
explicit operational gates; their existence is not claimed by this Compose file.

The renderer distinguishes DNS from IP-literal TLS. [RFC6066 section3](https://www.rfc-editor.org/rfc/rfc6066#section-3)
excludes literal addresses from SNI; [Nginx selects the default TLS server](https://nginx.org/en/docs/http/configuring_https_servers.html)
before HTTP Host is available. DNS mode rejects unknown SNI at handshake. IP mode
serves only the approved IP certificate on its default socket, then rejects any
nonempty SNI or incorrect HTTP Host before proxying. This does not authorize a
catch-all API. Loopback fixtures verify IP-SAN hostname validation without SNI,
wrong Host/SNI refusal, body caps and redirects; no public IP is contacted or chosen.

Endpoint ownership is also a release gate: do not use an ephemeral/reassignable IP
as a bearer-token destination. For an IP origin, verify owner-held reserved-address
eligibility/cost/retention and protect it from deletion. [Oracle's public-IP contract](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingpublicIPs.htm)
distinguishes persistent reserved addresses from instance-bound ephemeral ones.
Account/address loss can still put old clients at risk; a hostname/certificate or
compiled origin alone does not prove continuing ownership. Reclamation downtime
acceptance does not authorize JWT exposure to a future address holder. No address
is selected/reserved here; ownership monitoring/recovery must precede activation.

## Release, probes and rollback

Routine `/health` does not touch DB; `/ready` only for explicit deployment/incident
checks. Proxy health checks syntax/certificate readability, not end-to-end readiness.
Verify actual TLS→native API and correct-host/wrong-host behavior before promotion.
Proxy request/error logging is suppressed to avoid callback/header disclosure;
finite application diagnostics and separately approved monitoring must address
the corresponding forensic gap. No external paid logging sink.

Separately approve schema4 backup/restore/rehearsal and runtime grants. No startup
DDL; no deployment via Azure's production-hardcoded workflow. Hold existing Vercel
promotion, validate paired native `dist-native`/API pins, then retire legacy traffic
atomically after explicit approval. Roll back to a reviewed native/schema4-compatible
digest; never reset Neon, recover users through legacy credentials or split traffic.
Factor removal/deletion remain disabled under ACCOUNT_OPERATIONS_READINESS.md.
No new email/factor/account mutation budget exists (10/10 used).

## Separate operator schema tool (NOT APPROVED FOR EXECUTION)

`python deploy/oracle/manage.py check` or `migrate` is an explicit operator action,
using the reviewed native manifest and `/run/secrets` runtime inputs plus a separate
`native_migration_url` file. It requires `movelle_native_migrator` and exactly the
same host/database/TLS options as runtime; no reset, legacy recovery or claiming.
The tool is not copied into the runtime image or mounted/executed by Compose.
Use only a locked operator Python environment after backup/target/grant/migration
approval. No hosted DDL or migration credential was created; tests inject SQLite.
