# Removal/deletion screens — execution still disabled

The separate native release now offers review pages for both operations. Default
services are unavailable and no current bootstrap selects a reviewed execution
adapter. No environment/URL flag activates them. The existing lifecycle dialog and
backup-preserving removal stay disabled. These are preparation, not enabled accounts.

The concrete `createAccountDeletion` adapter requires explicit trusted review,
uses the shared native controller and credential fence, sends no numeric owner and
never retries writes. It only accepts the server's exact `pending` result; `deleted`,
surplus fields or unknown replies cannot claim erasure. Account switching drops late
outcomes and cannot sign out another account. The candidate backend independently
enforces password, current-email, owned TOTP and issuer/subject policy; a frontend
review flag is not authorization. No administrative capability enters this module.

Screens require typed irreversible intent, private current password for deletion,
and a fresh owned TOTP selection/code when enrolled. Unknown inventory never becomes
an empty non-MFA form. Inputs are uncontrolled and reset at dispatch and session
changes; no password/code enters React state, storage, URL or logs. Accepted queueing
is described as pending with personal access blocked and an explicit sign-out
action; it never means both stores have been erased. Cancellation after dispatch
cannot undo provider or queue commits. Uncertain outcomes require an explicit new
reauthentication request, not replay. Factor-removal warnings explicitly allow zero
remaining factors; no safe retain-one or all-lost recovery promise is made.

Actual SDK/transport, DOM and Chrome responsive tests are fictional-provider evidence.
Hosted delivery, MFA races/revocation, administrative deletion, retention, storage
ownership and worker isolation still require separate approvals and acceptance.
