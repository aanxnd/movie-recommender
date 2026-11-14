# Approved native factor contract: implementation and acceptance

**REQUIRED NATIVE MFA JOURNEY PASSED - PRIVATE DEPLOYMENT NOT APPROVED**

The owner approved PR88's native omission contract and acknowledged silent provider
response loss/non-atomic reads. PR89 implements it without production activation.
This report distinguishes real Supabase evidence from offline tests. The
[private deployment plan](PRIVATE_STAGE23_DEPLOYMENT_PLAN.md) is preparation only;
Azure incremental $0 cost has not been established.

## Review stack and unchanged boundaries

| PR | Scope / review state |
|---|---|
| [87](https://github.com/aanxnd/movie-recommender/pull/87) | Independent pre-fix real-provider report,211 lines, head `38d38287ac14a79a68cdd1ec34ca5bc19b3ca52b`; documentation merge-ready after owner review, CI/size passed. Its blocker describes the historical pre-fix policy. |
| [88](https://github.com/aanxnd/movie-recommender/pull/88) | Main-based source/threat proposal and real-SDK characterization,210 lines, head `28fa291f9172d06493d4280b0143e1e3a12c90b4`; owner approved its security contract, not a merge/deployment. |
| [89](https://github.com/aanxnd/movie-recommender/pull/89) | Stacked on88: approved runtime correction, native SVG compatibility and regressions;381 lines, head `8f8055980e9a55c171566a29f18a5ac843fab23c`. |
| This report/plan | Stacked on89; no further runtime/configuration/deployment change. |

Do not merge automatically. After each authorized parent merge, rebase the next PR,
verify only its intended diff remains <=500 lines, and rerun required checks.
Vercel's existing preview automation remains legacy-only; main merges can build
the existing production frontend. Azure production release is manual, targets
`movie-recommender-api`, and must not be dispatched for private staging.

The backend accepts omission/empty only from a fresh authenticated same-project
exact-subject read after ES256/JWKS/issuer/audience/session/expiry verification.
Null, malformed, duplicate, unsupported, conflicting AAL2 and provider errors deny.
Verified factors require signed AAL2; no browser grant, cached factor state, Auth
DB role, admin key, legacy fallback, account claiming or route activation exists.
First setup stays optional; enrollment alone is not verified MFA. Removal,
all-device-loss recovery and password-only downgrade for enrolled accounts remain
unavailable. Ownership, numeric identities, ratings and group privacy stay server-side.

## Actual development-project observations after the approved correction

Only existing `movelle-auth-dev`, pinned `jsbulnrcxtvslvvxjizq.supabase.co`, was used.
Owner-confirmed Confirm Email/root redirect/Gmail configuration was not changed.
The actual app ran in fresh isolated Chrome on loopback5173/API8011, with a private
controller19003 and owned PostgreSQL17/schema3 on55441. Provider traffic was real;
other origins were blocked. No shared profile, screenshots, traces or raw logs.
The existing bundled MovieLens Small prepared artifact was reused without download.

| Test | Actual evidence | Result |
|---|---|---|
| B native signup | New campaign-owned Gmail alias; provider signup200. | PASS |
| B native confirmation | Owner-saved private file; verify303, PKCE exchange200 in originating browser; clean root URL. | PASS |
| B provider email/JWT | Real ES256/issuer/audience/UUIDs, AAL1, signed `email/signup` AMR,3600s lifetime; fresh native current-email evidence accepted. | PASS |
| B zero-factor contract | Fresh user omitted `factors`; backend provisioning policy accepted under explicit owner approval. | PASS |
| B profile | Actual UI selected username; local schema3 allocated numeric identity, `/users/me`200; no client-selected owner or legacy credential. | PASS |
| B first TOTP enrollment | Actual UI/native factors POST200; setup display did not complete, no challenge/verification dispatched. | FAILED setup compatibility; factor left unverified |
| B final logout | Native logout204; helper's exact UI-text wait timed out (the app appends provider status). Browser/controller closed. | Server acknowledgement only |
| C signup/confirmation/profile | Signup200, native verify303/PKCE200, clean URL, fresh omitted-factor response; actual UI allocated a second distinct numeric profile. | PASS |
| C corrected QR/first TOTP | Native enrollment200; actual QR406,128 characters with inert namespace/styles rendered; setup secret used only in private process memory. | PASS |
| C verification | Native challenge200/verify200; signed AAL2 with `totp` AMR, fresh provider factor verified, same numeric profile; setup DOM cleared. | PASS |
| C stale/fresh AAL1 | Pre-enrollment AAL1 denied401 after verification; subsequent native password login produced fresh AAL1 and was also denied401/provisioning denied. | PASS |
| C second MFA challenge | Native challenge200/verify200 restored signed AAL2 with password/TOTP AMR and the same profile. | PASS |
| C movie functionality | Actual search/rating UI saved five ratings; authenticated recommendations GET200 returned10 items. | PASS; recommendation API, not a recommendation-screen assertion |
| C foreign ownership | Actual C bearer denied404 for B's profile through a temporary read-only loopback probe, then probe removed. | PASS; helper originally expected403, correctly rejected its own assertion |
| C logout | Both native logout requests returned204; exact-text helper timed out on the informational suffix. Context/processes closed. | Provider acknowledgement; no invented UI-completion pass |

Positive native signup PKCE is now observed, unlike the initial A campaign's
wrong-browser handoff. The app still makes no unsupported signup provenance claim
from SDK `redirectType=null`; backend native current-email evidence is authoritative.
No success flag, URL email, user ID or decoded-only JWT authorized provisioning.

## QR compatibility defect and bounded correction

B's enrollment succeeded but its original raw QR/secret response was not retained.
The precise rejected original field is therefore not retrospectively attested.
Pinned GoTrue [MFA code](https://github.com/supabase/auth/blob/v2.197.0/internal/api/mfa.go)
and [dependency versions](https://github.com/supabase/auth/blob/v2.197.0/go.mod) use
[SVGo1546f124](https://github.com/ajstarks/svgo/blob/1546f124cd8b/svg.go) and
[goqrsvg17e843f1](https://github.com/aaronarduino/goqrsvg/blob/17e843f1dd40/goqrsvg.go).
Their stock output contains root `xmlns:xlink`, exact black/white rectangle styles
and one rectangle per QR cell. Offline source-shaped responses reproduced rejection
by the old allowlist; verbose output can exceed its previous200,000-character cap.
The C retest directly confirmed the native406,128-character response and both inert
forms; it does not retrospectively establish B's original response size.

PR89 permits only that inert namespace and those exact rectangle styles. It keeps
secret/URI binding, trusted origin/subject/session fencing and all active-content
denials. It bounds the response to1MiB and10,000 opening tags before parsing,
rejecting rather than truncating larger/node-heavy content. New tests cover active
CSS URLs, wrong namespaces, xlink references, oversize and excessive nodes, while
existing script/event/external-image/URI-mismatch cases remain enabled.
No unverified-factor removal, out-of-band enrollment or validation bypass was used.

## Final campaign budget and cleanup

At final shutdown: **3/4 accounts**, **8 email-capable requests**, **2 possible
notifications reserved** (A password update and C MFA verification): **10/10**.
There were **2/10 new factors**: B unverified, C verified. At mailbox inspection,
A had5 messages, B1 and C1; seven actually received does not release reservations.
The pinned provider sends its enrollment notification only after factor verification.
B never issued a verification request and will not be reused, so its untriggered
MFA-notification reservation was explicitly released; no outstanding email was refunded.

No more hosted email/factor/account mutations are planned under this campaign.
Additional testing needs a separately reconciled budget and safe prerequisites.

Accounts A/B/C remain pending supported owner cleanup. No account was deleted and
no pre-existing account/factor was modified. B's setup secret was not retained;
do not weaken pending-factor/removal restrictions to recover it. C's seed was not
retained after testing. The synthetic database retains2 users/identities and5 ratings,
with zero legacy credentials and distinct numeric ownership; no production DB access.
Owned staging/browser/controller processes and PostgreSQL container were stopped;
ports5173/8011/19003/55441 had no listeners. B/C private input links were consumed,
the controller capability file removed, and temporary probe code restored exactly.
Ignored local configuration and prepared reference data remain private for owner use.
No password/JWT/OTP/seed/address/key belongs in committed evidence or reports.

## Automated checks: separate from hosted acceptance

- Complete local backend, real isolated PostgreSQL17: **1422 passed,11 skipped**,
  one existing deprecation warning. An initial run used the wrong database name;
  fixture guards rejected it. Corrected to `disposable`, preserving all guards.
- Full frontend: **598 passed**; focused native setup/adversarial tests36 passed.
- Fictional-provider staging Chrome: **11 passed (52.3s)**, including signup callback,
  profile, first TOTP, AAL2, ratings and fresh-AAL1 denial. This is not real-provider proof.
- Production and staging builds passed; existing staging chunk-size warning remains.
- PR89's unchanged final-head [CI rerun](https://github.com/aanxnd/movie-recommender/actions/runs/43568173321)
  passed: backend1424/9 skips, frontend598/zero skips, browser11, both builds.
  The initial frontend job stalled after account-screen tests and was owner-canceled;
  no failed assertion was logged. Identical runtime source passed in PR90 and the
  unchanged-commit retry; the stall is not reproduced or conclusively root-caused.
  No code/workflow change, skipped test or weakened check was used for the retry.
- An earlier helper-creation action did not execute because automatic approval
  review hit a usage limit. Tool access later resumed normally; no check was bypassed.

## Remaining gates

The required real-provider first-factor/AAL2/movie journey passed. Multi-device
backup, removal, intentional provider outage/throttling/expiry and all Stage23
acceptance combinations were not exercised by this bounded campaign. Offline
adversarial tests are separate evidence. Enrolled sensitive-action restrictions,
all-factor-loss lockout, no removal, Gmail production deliverability and production
cutover/audit gates remain. No production deployment or final audit is authorized.
The cloud plan also needs account-specific $0 proof and separate private resource,
bootstrap/gateway, exact origin, credential, migration and configuration approvals.
