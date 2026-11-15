# Deletion worker review — NO EXECUTION APPROVAL

The explicit `DeletionWorker` has no environment loader, scheduler, CLI/public
endpoint or default-app import. Both worker and administrative adapter refuse
construction without explicit review. No actual credential was obtained or stored.
Synthetic fixtures alone enable the constructors and intercept all provider I/O.

Supabase's [deleteUser](https://supabase.com/docs/reference/javascript/auth-admin-deleteuser)
requires administrative capability. It is **broad**, not per-user scoped. The proposed
least-privilege boundary confines it to a separate non-public worker: no browser,
frontend bundle, web-server secret, list/update/factor-admin operation or arbitrary
target URL. The application signs exact deletion intents with a distinct server-only
key; the worker verifies target/issuer/phase/expiry before acting. Database-only
tampering cannot manufacture authority. Review dedicated DB privileges: read journal
and identity binding; update journal state/lease/tag; insert audit; delete only the
known application dependents. No Auth-table, role-management or schema DDL privilege.
No roles/grants or resources are created here; effective grants still need inspection.

Pinned [GoTrue admin source](https://github.com/supabase/auth/blob/v2.197.0/internal/api/admin.go)
returns `{}` on hard-delete. The adapter never mistakes that for absence: it freshly
GETs the exact UUID before and after, accepting only `404/code=user_not_found` as
absence. A wrong UUID/creation timestamp, generic 404, storage-owner refusal, timeout,
rate limit, malformed/duplicate/oversized JSON or failed recheck leaves Neon intact.
The signed provider creation timestamp prevents reusing an old request for a visibly
recreated identity. GET/DELETE are not atomic: prohibit concurrent administrative UUID
reuse during execution; a same-UUID recreation between reads cannot be ruled out by
this API. This remains an activation gate, not an invented conditional-delete guarantee.

Lost DELETE acknowledgments reconcile via fresh GET; confirmed absence plus Neon
failure retains a blocked signed phase and retries local cleanup. A later recreated
identity is never deleted from an already-consumed phase. Expired authorization
permits absence checks/reconciliation, never a new provider DELETE. No retry loop
or immediate JWT/session revocation promise is added. Socket inactivity timeout is
three seconds with capped bodies; a total worker-process deadline and stop/retry
policy still need operational review. Provider retention/backups and Storage ownership
must be reviewed separately. The existing 10/10 budget prohibits hosted validation.
