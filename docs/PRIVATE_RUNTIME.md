# Private Stage 23 runtime boundary — not deployed

These modules are inert until a separately selected private entry composes them.
Production `app.runtime`/`app.main` do not import or enable this gate.
The explicit command is `python -m app.private_entry`, with one worker and no
access logs/forwarded-header trust. It checks schema3 without migrating and reuses
the tested native composition, public algorithms, quotas and keyless artwork.
Every legacy private handler is excluded; API documentation is unmounted.

`private_config` requires a reviewed, bounded JSON target file, explicit private
mode, production TLS validation, the pinned development Supabase project, and
exact HTTPS frontend/backend origins. It rejects the known production API/branch,
protected endpoint hosts, ambient libpq overrides and every database target except
the approved endpoint, dedicated database/role and verify-full/channel-binding TLS.
The owner must verify the endpoint's branch in Neon; SQL cannot attest control-plane
branch membership. A configuration file is operator authority, not remote evidence.
No real cloud target is approved or supplied by this PR.

`PrivateGate` requires one server-only 32-byte base64url capability, exact Host and
Origin before body parsing, quotas, provider calls or application access. It strips
the capability/proxy headers. This gate is additional private access control, never
JWT identity, email/MFA evidence or ownership. All proxy clients share conservative
existing IP quotas; client-supplied forwarding headers never choose an identity.
Azure probes must use TCP: no unauthenticated HTTP probe bypass is provided.

Configuration, private gateway/build, cost verification and hosted acceptance need
separate review. No hosted SQL, credentials, settings or deployment are included.
