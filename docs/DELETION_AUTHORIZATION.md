# Dormant deletion authorization / all-route block

`compose_deletion_candidate` is not used by any current application entry or
environment switch. It requires explicit server review, signed-intent key custody
and the reviewed journal schema at startup; missing storage cannot fail open.
The application schema/version and hosted configuration are unchanged.

The candidate POST `/auth/deletion` accepts a request UUID, private password and
exact irreversible confirmation; it accepts no numeric owner, subject, email or
assurance assertion. The server verifies the original JWT/current native email/MFA
policy, uses the provider's password RPC for the same subject in a different AAL1
session, verifies its signature/password AMR and locally signs out that temporary
session. Enrolled accounts additionally require a newly executed owned TOTP
challenge/verification, signed same-session AAL2 and fresh account evidence. An old
AAL2 token plus password cannot bypass that step. No new token is returned to the
browser. A successful challenge may rotate provider session material even if a
later queue write fails; reauthentication may be necessary. No automatic retry.

Only then does the server issue a two-minute deletion-specific receipt and resolve
the existing numeric profile. Exact-subject provider creation time is bound into
the signed journal. An expired pending intent requires fresh authorization to renew
the same request; renewal cannot interrupt a leased worker. IP/global quotas commit
before password work; malformed input/provider diagnostics never echo credentials.

One lifecycle-aware policy guards every candidate protected resource, settings and
provisioning path. Pending, provider-absent and completed tombstones all deny personal
access/reprovisioning for that subject; another subject and anonymous browsing are
unaffected. Already admitted requests may finish, with FK/transaction protections
on cleanup. No immediate provider-session/global-token revocation is claimed.
HTTP enqueue returns only `pending`, never `deleted`. Admin capability belongs only
to the worker. Defaults remain disabled until DDL/grants/retention/worker isolation,
provider behavior, explicit target/cost gates and genuine hosted acceptance are approved.
