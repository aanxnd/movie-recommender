# Prompt 20 offline validation and review

Historical Prompt 20 snapshot. PRs #60–64 are merged. [Prompt 21](MFA_RECOVERY.md)
supersedes removal permissions: all native deletion is unavailable across devices.

Starting main: `6db83662ca1c794b0cbfcb1cd00a37bad181d168` (Prompts 1–19 merged).
Both installed supabase-js and auth-js are **2.119.0**; no dependency changes.

Review order: #60 evidence → #61 native challenges/session promotion → #62 setup
and management → #63 dormant screens → final offline preview/validation PR.
Each is based on the preceding branch and independently stays below 500 changed
lines. Owner/ChatGPT handles review/rebase/retarget/merge; no automatic merge.

## Completed local checks

- Full frontend Node suite: **465 passed**, no skips/failures, including 83 new MFA
  cases across signed evidence, real-SDK native operations, session races and React.
- Production Vite build passed. No production entry, protected route or backend
  authorization code changed; MFA screens are absent from built assets.
- Backend email/AAL/identity/resource/size regressions: **297 passed**, disposable
  local PostgreSQL 17, synthetic fixtures. Existing httpx deprecation warning only.
- Complete-PR checker unit tests: **10 passed** (also included in backend total).
- Chrome MFA preview: **3 passed**, mobile/desktop keyboard continuation, credential
  cleanup, removal review and unknown/error states. Existing account/password
  browser regression files are also run for the shared preview entry.
- Desktop/mobile screenshots visually inspected locally; synthetic illustrative QR
  only. Temporary capture helper removed; no credentials or screenshots committed.

## What these passes do not establish

No hosted user/factor changes or Supabase calls occurred. Offline HTTP fixtures use
the real pinned SDK and locally signed ES256 JWTs; they cannot establish hosted
inventory completeness, Free-plan response formats or provider-side race semantics.
See [the exact activation checklist and provider sources](TOTP_MFA.md).

**First enrollment/no-factor continuation remains unavailable.** Empty and omitted
factor lists are unknown, even with AAL2. Positive native factor evidence permits
dormant challenges and additional enrollment/removal under the documented guards.
Password/email changes remain MFA-required; verified AAL2 is not fresh password proof.
Final usable-factor removal and lost-device recovery are outside this prompt.

Production authentication, legacy behavior, anonymous browsing, Neon numeric IDs,
ratings/groups/invitations and backend ownership/privacy protections are preserved.
No hosted configuration, migrations, account provisioning, paid service, production
deployment or merge occurred. Prompt 21 was not started. These PRs await owner review;
source/offline passes alone never authorize activation or formal NIST claims.
