# Signup email codes — pending reviewed rollout

Native signup now presents explicit six-digit code entry. Keep Confirm Email ON.
Use pinned SDK2.119.0 `auth.verifyOtp({ email, token, type: 'email' })` and
`auth.resend({ email, type: 'signup' })`; no custom ledger, Auth DB access or admin key.
The shared session/credential fence aborts stale operations and checks the returned
current email/confirmation before SDK persistence. Backend JWT/current-email/MFA,
numeric profile ownership and Neon provisioning checks remain authoritative.
Email OTP is NOT TOTP, AAL2, recent password proof or authorization.

## Owner-approved coordinated rollout still required

1. Review/merge this PR after tests. Do not change the running preview or public domain.
2. Separately approve and prepare a matching protected native frontend deployment.
3. In Supabase Auth's Confirm signup template, set subject **Your Movelle verification code**
   and copy `supabase/templates/confirmation.html`. It contains only `{{ .Token }}`;
   no ConfirmationURL, TokenHash, href, tracking pixel or automatic redemption link.
   Confirm the provider's email OTP length is six and record its actual expiration
   and rate limits; this PR neither changes nor assumes hosted values.
4. Coordinate the template/frontend switch; old link-only clients are incompatible
   with code-only mail. Preserve existing exact origins, recovery/email-change templates,
   SMTP and security settings. No hosted setting or deployment was changed here.
5. Approve a new bounded Gmail/Waterloo acceptance budget and verify code delivery,
   scanner GETs without confirmation, explicit code success, replay/expiry/throttling,
   profile access and enrolled-factor AAL1 denial/AAL2 success before public release.

The form never auto-submits, reads codes from URLs or persists/logs them. The OTP
is transient input sent only in the SDK POST body; it clears before awaiting I/O.
Malformed codes fail locally. Incorrect/expired/reused codes share generic guidance;
resend hides account existence and has a60s UI cooldown, not a replacement for
provider-enforced limits. Ambiguous network failure is never retried automatically.
Verify email navigation permits reload/another device without retaining an OTP.

Limitations: provider `type: email` accepts both signup and magic-link/recovery-token
families; it is not flow-specific provenance. No new recovery/password privilege
comes from this UI. Existing confirmed accounts and previously issued links are not
revoked/reset; changing the template cannot retroactively undo scanner confirmation.
Code-only mail removes the consumable URL used by GET-only scanners; it does not
defend against a malicious recipient deliberately extracting/submitting the code.
Offline simulators establish regression behavior, not hosted acceptance.

## Delivery investigation, separate from verification

Nov23: Gmail Sent contains the reported Waterloo confirmation at18:23:09 Toronto;
no matching bounce was found. Sent status and the owner-reported automatic Auth
GET suggest sender submission/content inspection, not Inbox placement. Microsoft365
quarantine/message trace (recipient/admin access) is required to distinguish filtering,
quarantine, routing or removal; Gmail SMTP supplies no per-recipient delivery dashboard.
Provide the Message-ID privately to university IT, not the body/confirmation URL.
No resend, extra signup or SMTP/template change was performed for this investigation.

Official evidence: [scanner mitigation and Token](https://supabase.com/docs/guides/auth/auth-email-templates#email-prefetching),
[verifyOtp](https://supabase.com/docs/reference/javascript/auth-verifyotp),
[resend](https://supabase.com/docs/reference/javascript/auth-resend),
[pinned GoTrue verification](https://github.com/supabase/auth/blob/v2.197.0/internal/api/verify.go).
