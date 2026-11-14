# Stage 23 real Supabase acceptance - 2026-11-13

**PARTIAL HOSTED ACCEPTANCE — SECURITY GATES REMAIN**

Real signup, confirmed password login, JWT verification, restoration, refresh,
native recovery/password reset and logout passed. The fresh provider response **omitted `factors`**; Movelle correctly
denied provisioning and initial enrollment. Authenticated application acceptance is
blocked. This is not Prompt 24, production activation or deployment approval.

## A. Verified environment and private configuration

Base main: `597d13b1c823a1c3cdf7adc193343f6274f0d560`; its source tree matches
audited `0178e273b5bf5ce8b8406a0ae5fab2add691aee8`. PR87 changes documentation only.
The owner-approved **movelle-auth-dev** target is pinned to
`https://jsbulnrcxtvslvvxjizq.supabase.co`. Private preparation removed `/rest/v1/`
from the supplied REST URL for SDK configuration; runtime URL validation is unchanged.
Project identity/Free plan are owner-attested; public endpoints do not attest billing.

Owner-confirmed: connected Gmail aliases approved, exact
`http://127.0.0.1:5173/` allowlisted, Confirm Email enabled, Site URL unchanged.
Actual `/auth/v1/settings`: HTTP200, `disable_signup=false`,
`mailer_autoconfirm=false`, `external.email=true`. Actual health: GoTrue v2.197.0.
The pinned JWKS supplied one EC/P-256/ES256 public key accepted by existing code;
actual issued JWTs subsequently passed existing cryptographic verification.
No hosted setting was changed.

Private configuration: Git-ignored repository-root **`.env.staging.local`** with
`MOVELLE_STAGING_SUPABASE_URL`, `MOVELLE_STAGING_PUBLISHABLE_KEY`,
`MOVELLE_STAGING_PREPARED_DIR`, `MOVELLE_STAGING_DATABASE_URL`; values withheld.
The launcher requires explicit loading from root:
`node --env-file=.env.staging.local frontend/scripts/staging.mjs`.
Node's [env-file option](https://nodejs.org/api/cli.html#--env-filefile) loads it;
Vite receives only the intended public inputs. Never put privileged keys in VITE.

Old prepared directories were inaccessible and left untouched. The existing
preparer safely refused overwrite; bundled MovieLens CSVs were prepared offline
into fresh `.pytest-tmp/stage23-hosted-reference` and passed `verify_local`.
Only owned PostgreSQL17 container `movelle-supabase-acceptance-pg`, loopback55441,
database `movelle_staging_acceptance`, was initialized to schema3. Actual aggregate
checks found **users0, identities0, ratings0, legacy credentials0** after login tests.
No Neon or copied personal data was used. API8011, frontend5173 and private test
controller19003 bind loopback. Fresh isolated Chrome used actual SDK2.119.0,
UI and hosted transport: no Auth interception, shared profile, traces or screenshots.

## B. Sanitized real-provider ledger

| ID | Intended behavior | Actual observation / result | Evidence |
|---|---|---|---|
| P01 | Audited main | PASS: exact commit/tree comparison above. | Git |
| P02 | ES256 compatibility | PASS: real public JWKS and issued-token verification. | Existing backend verifier |
| P03 | Signup settings | PASS: native email enabled; automatic confirmation false. | Actual public settings API |
| P04 | Local isolation | PASS: schema3/empty app tables; loopback services. | Actual local PostgreSQL17 |
| A01 | Signup | PASS: one campaign account, matching user response, HTTP200. | Actual staging UI/SDK/provider |
| A02 | Unconfirmed restriction | PASS: password grant HTTP400 `email_not_confirmed`; no session. | Actual provider |
| A03 | Email delivery | PASS: campaign messages delivered to INBOX, not SPAM. | Connected Gmail, private recipient binding |
| A04 | Signup confirmation state | PASS: after owner clicked in another browser, later password login/fresh user proved confirmation and matched original created subject. | Actual provider; not inferred from callback UI |
| A05 | Same-browser signup PKCE | NOT RUN successfully: owner opened initial link outside test browser. Original callback showed generic failure; exact original error unavailable. | Owner report; no invented success |
| A06 | Original link retry | PASS rejection: HTTP303 to exact root, no code, `otp_expired`. Consumption versus natural expiry not distinguishable. | One safe native verification read; redirects not followed |
| A07 | Duplicate signup | PASS: HTTP200/generic UI, no local session, no additional account. Subsequent original-password login succeeded. | Actual UI/SDK/provider |
| A08 | Malicious/malformed callback | PASS: malformed code plus external next value scrubbed; zero PKCE calls, no external navigation. | Actual local browser; provider deliberately not called |
| S01 | Signed token evidence | PASS: ES256/issuer/audience, UUID subject/session, `aal1`, password AMR, 3600s issuance-to-expiry. | Actual JWT through existing verifier; values withheld |
| S02 | Restore and refresh | PASS: reload restored session; manual refresh returned valid token and fresh user. | Actual UI/SDK/provider |
| S03 | Logout/stale token | PASS: logout204/local session cleared; old JWT still cryptographically/time-valid, fresh user403 `session_not_found`, policy denied. | Point-in-time real observation, not universal instant-revocation guarantee |
| E01 | Current email | PASS: fresh user confirmed current email, authenticated audience/role, explicit non-anonymous, no pending email. Existing native-email policy accepted. | Actual user response |
| E02 | Pending email changes | NOT RUN: no email-change mutation or assurance bypass. | Blocked sensitive-action prerequisite |
| M01 | Zero-factor account shape | PASS observation: raw fresh user **omitted** `factors`, including after refresh. Not converted to an empty inventory. | Actual raw response shape, no identifiers recorded |
| M02 | Unknown-inventory denial | PASS boundary: profile GET401; UI disclosed incomplete inventory and offered zero enrollment controls. | Actual backend/UI |
| M03 | Pending/verified/multiple TOTP, AAL2 | BLOCKED: initial enrollment requires supported complete evidence; zero factor mutations. | Existing reviewed policy preserved |
| M04 | Backup/removal/lost devices | BLOCKED: no eligible enrolled account; no out-of-band setup or recovery bypass. | Existing restrictions preserved |
| W01 | Recovery request | PASS: native POST recovery200 for same campaign account. | Actual UI/SDK/provider |
| W02 | Expired recovery flow | PASS refusal: native verify303, PKCE exchange422 `flow_state_expired`; no recovery session/password update. | Actual provider after manual handoff delay |
| W03 | Fresh recovery callback | PASS: native verify303, PKCE exchange200, signed recovery AMR, clean root URL and private new-password form. | Real originating browser/provider; no confirmation inferred from URL |
| W05 | Native password reset | PASS: actual UI/user PUT200; logout then new-password login succeeded with signed password AMR. Profile remained401. | Same campaign account; no generated password logged |
| W04 | Sensitive password/email change | BLOCKED: incomplete factor evidence; no fabricated recent-password proof. | Existing policy |
| U01 | Profile provisioning/uniqueness | BLOCKED by M01; no profile POST, injected principal or local writes. | Actual profile denial, empty DB |
| U02 | Ratings/personal recommendations/groups/switching | BLOCKED for real-provider acceptance by U01. | Fictional-provider results kept separate |
| B01 | Anonymous browse/search | PASS: actual local MovieLens browse/search, canonical movie1, no rating controls/provider calls. | Local application, not authenticated provider proof |
| N01 | Natural JWT expiry/outage/other project | NOT RUN against hosted service; no one-hour wait, outage injection or second project. | Offline adversarial coverage remains separate |

## C. Provider compatibility and limitations

Actual signed tokens and native current-user evidence are compatible with existing
verification. The account was confirmed independently of the owner's generic
callback error. Missing original-browser PKCE verifier plausibly explains that
error, but is an **inference**, not a captured original error. No extra signup or
confirmation resend was needed. Positive recovery does not prove signup provenance.

Observed missing factor inventory is a substantive **activation blocker**, not
proof of no MFA and not a runtime defect fixed by normalizing absent fields.
No out-of-band initial enrollment or fabricated provisioning principal is allowed.
Official [getUser](https://supabase.com/docs/reference/javascript/auth-getuser) and
[listFactors](https://supabase.com/docs/reference/javascript/auth-mfa-listfactors)
are interface evidence; they do not alone establish hosted inventory completeness.
A supported completeness/design decision needs separate owner security review.

Supabase documents [single-use, five-minute PKCE codes](https://supabase.com/docs/guides/auth/sessions/pkce-flow).
Observed recovery rejection occurred over eight minutes after email receipt.
The matching [GoTrue v2.197.0 PKCE implementation](https://github.com/supabase/auth/blob/v2.197.0/internal/api/token.go)
checks configurable flow-state expiry before verifier comparison. The precise hosted
flow-state timeout was not inspected; email age alone does not prove its value.
The expired attempt was recorded, not suppressed by a successful retry. A second
request aged without private handoff and was not redeemed. After owner readiness,
fresh flows completed within their validity. Recovery evidence and password update
remained separate from backend access; the unknown-factor denial still applied.

Fresh user rejected a logged-out session while its issued JWT remained valid. This
point-in-time result does not establish every revocation, deletion, ban or expiry
scenario, nor change approved bounded-token behavior. Gmail INBOX delivery does not
close production deliverability, Outlook junk-placement, sender-limit or SMTP gates.

## D. Defects, tooling and security boundaries

No provider-specific runtime defect has been established. No application code,
dependency, route, policy or production setting changed. Private setup normalized
the supplied REST URL and used existing preparation/initialization commands.
A temporary helper needed its import path corrected; inaccessible artifacts were
not overwritten. Unknown-factor denial is intentional and remains enforced.

A temporary harness rejected SDK2.119.0 password-update bodies because the SDK
always adds null `code_challenge` and `code_challenge_method`. That request was
aborted locally before Supabase; no password changed. The private harness now
allows exactly the expected password and those null fields, with offline checks
rejecting extra email/current-password fields and non-null challenges. An initial
fixture-command quoting error was corrected and checks passed. A fresh genuine
recovery flow then completed through unchanged application code. A stale local
navigation timeout was also resolved by restarting only the isolated test context;
request counters proved it sent no additional email. A private-file read before
writing finished failed validation without dispatch; the owner-ready read passed.

Automatic approval rejected an early proposed command containing an encoded link
before execution: encoding still exposes tokens in command history. All subsequent
link operations read owner-created private files at runtime, validate pinned
host/path/type/root, consume inputs and keep tokens out of arguments/output.
A separate approval-review timeout happened before logout; one permitted retry
succeeded. Neither tooling event is a provider/test failure.
Dashboard UI tooling could not initialize; isolated CLI Playwright worked.

JWT verification precedes evidence/ownership. No legacy fallback, client-selected
owner, email-only MFA recovery, final-factor deletion or invented assurance was used.
Only campaign account A was touched. Passwords remained in test-process memory;
SDK session state stayed in isolated Chrome. No addresses, subject IDs, tokens,
seeds, raw email links, credentials or key values belong in this report or ledger.

## E. Resources and cleanup

| Resource | Used/reserved | Ceiling |
|---|---:|---:|
| New synthetic accounts | **1 (A)** | 4 |
| Email-capable signup/recovery requests | **6 reserved** | 10 total provider emails |
| Possible password-change notification | **1 additionally reserved** | Combined conservative reservation **7/10** |
| Received matching messages | **5** (signup, four recovery), all INBOX / zero SPAM at close | Same email ceiling |
| New MFA factors | **0** | 10 |

Duplicate signup was conservatively counted despite no observed extra message.
A notification reservation is separate from received-message counts. No rate limit
or quota was deliberately tested. Campaign A is independently creation-bound and
cleanup-eligible; deletion remains **pending supported owner cleanup**. Public user
APIs provide no reviewed self-delete path; no privileged workaround was used.
No pre-existing account/session/factor, hosted SQL/configuration, production resource
or paid service changed. Final native logout passed. The isolated browser and
frontend/backend/controller were stopped; the owned local PostgreSQL container is
stopped and retained with its empty synthetic database. Zero listeners remain on
5173/8011/19003/55441. Both private link files were consumed/removed. Ephemeral
controller capability/inbox configuration were removed; owner-requested ignored
`.env.staging.local` and prepared artifact remain for later approved local testing.
The stopped database must be started explicitly before that launcher can run.

## F. Commands and separate automated regressions

- `git fetch origin main` and exact commit/tree comparison: PASS.
- Existing JWKS/token/current-email/policy helpers with real provider evidence: outcomes in B.
- `python scripts/prepare_movielens.py --source data --output .pytest-tmp/stage23-hosted-reference`: PASS, bundled offline source.
- Existing `staging_entry.initialize('init')` / `('check')`: PASS, isolated PostgreSQL17.
- Private campaign driver via explicit env-file launcher: real UI/provider observations in B; never CI.
- `python -m pytest -q tests/test_supabase_policy.py tests/test_supabase_email.py -p no:cacheprovider`: **87 passed**, one existing deprecation warning.
- `cd frontend; npx playwright test`: **36 passed (4.3m)**, existing local browser regressions including offline auth screens; no real customer data.

Report-head CI 8c29234 ([run43541015222](https://github.com/aanxnd/movie-recommender/actions/runs/43541015222))
passed **1420 backend / 9 optional skips**, **576 frontend**, both builds and
**11 fictional-provider staging browser tests (39.3s)**. Its PR-size check passed.
These are offline regressions, never added to real-provider acceptance counts.
Final report-head CI and complete PR size are recorded in the PR handoff. No test, required check or fail-closed rule was bypassed.

## G. Remaining decisions and private deployment readiness

Not ready for private cloud deployment. First review supported factor-completeness
options and the resulting provisioning/initial-enrollment decision. Positive signup
PKCE and all blocked hosted journeys still need acceptance; retain current denial.
Owner cleanup must identify only campaign A in the approved synthetic alias inbox.

Separate approval is required for exact frontend/backend/database hosting targets,
private ingress/isolation, HTTPS root callbacks/origins, CORS/TLS adaptation and
verified incremental $0 cost. Existing local guards intentionally reject cloud
hosts. Full NIST assessment, original professional audit and Stages24-26 remain
separate. Production authentication is dormant. No production deployment or merge
occurred. Existing Vercel PR automation ran its preview check for the legacy entry;
no native-auth deployment or hosting-setting change was initiated.
