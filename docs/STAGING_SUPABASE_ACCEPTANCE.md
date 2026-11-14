# Stage 23 real Supabase acceptance — 2026-11-13

**HOSTED TESTING BLOCKED — CONFIGURATION OR ACCESS REQUIRED**

This is the final Stage 23 acceptance campaign, not Prompt 24 or production activation.
Bounded testing is owner-authorized; fresh configuration/access requirements below
remain unsatisfied. Public-key discovery is real hosted evidence, not authenticated
signup/session/MFA/application acceptance. No blocked journey is counted as passed.

## A. Verified environment

- Fetched `origin/main`: **`597d13b1c823a1c3cdf7adc193343f6274f0d560`**, as expected.
  Its source tree matches audited head `0178e273b5bf5ce8b8406a0ae5fab2add691aee8`.
  Work starts from this main on `test/stage23-supabase-acceptance`, not an old stack branch.
- Intended project: **movelle-auth-dev**, mapped by prior owner-supplied configuration
  and repository evidence to `https://jsbulnrcxtvslvvxjizq.supabase.co`.
  The destination was pinned explicitly, never substituted from an environment value.
  Current dashboard project name/Free-plan/settings were not independently inspected.
- One credential-free HTTPS read of that project's `/auth/v1/.well-known/jwks.json`
  passed the existing bounded/no-proxy/no-redirect `_download` and `_parse` functions.
  Observed: **one EC/P-256/ES256 public key**, accepted by Movelle; no private-key field.
  No user access JWT was obtained, decoded or cryptographically tested in this campaign.
- Required configuration names: `MOVELLE_STAGING_SUPABASE_URL`,
  `MOVELLE_STAGING_PUBLISHABLE_KEY`, `MOVELLE_STAGING_PREPARED_DIR`,
  `MOVELLE_STAGING_DATABASE_URL`. Direct builds use public `VITE_STAGING_SUPABASE_URL`
  and `VITE_STAGING_SUPABASE_PUBLISHABLE_KEY`; no privileged key is needed.
- No dedicated staging values were loaded in the process environment or root/frontend
  `.env*` files. The earlier private validation directory was inspected for configuration
  presence only; no reusable approved project key was found. Old accounts/state were not used.
- Native/browser dashboard tools failed to start their Node runtime (`os error 3`).
  No dashboard setting was clicked or altered. Callback allowlist, Confirm Email,
  Site URL, template, SMTP, factor limit and current project settings remain unverified.
- Exact local app origin/root callback: **`http://127.0.0.1:5173/`**. Source pins this
  origin and loopback listeners; relevant ports were free. No staging service was started
  against the real provider without completing its required configuration.
- A newly owned Docker PostgreSQL **17** fixture was bound only to `127.0.0.1:55441`.
  Explicit `staging_entry.initialize('init')` and `initialize('check')` passed.
  Schema version **3** and zero users, credentials and ratings were verified.
  Generated local fixture credentials were not printed or placed in the campaign ledger.
  No Neon, hosted database, production copy, Auth DB or production records were accessed.

## B. Sanitized test ledger

| ID | Intended check | Actual result | Evidence / reason |
|---|---|---|---|
| P01 | Merged audited source | PASS | Fresh Git fetch and exact tree comparison above. |
| P02 | Dev target signing compatibility | PASS | Real public JWKS; existing parser accepted one ES256/P-256 key. Does not prove actual access-token claims. |
| P03 | Current project/dashboard settings | BLOCKED | Dashboard runtime unavailable; current private configuration/owner confirmation needed. |
| P04 | Disposable PG17/schema 3 isolation | PASS | Real local database init/check and aggregate empty-table assertions. |
| P05 | Exact root callback permitted | BLOCKED | Required origin is fixed in code; actual Supabase allowlist cannot be verified. No redirect-dependent request sent. |
| A01 | Signup / duplicate / unconfirmed restrictions | BLOCKED | Missing approved publishable-key configuration and designated test inbox; no signup request. |
| A02 | Confirmation delivery / PKCE / reuse / expired link | BLOCKED | No message/account created; callback configuration unverified. No raw links collected. |
| A03 | Confirmed password login | BLOCKED | No campaign-created confirmed identity or private credentials exist. |
| S01 | Real signed subject/session/AAL/AMR/current-user shape | BLOCKED | Requires an authorized synthetic session; JWKS alone establishes none of these. |
| S02 | Restore / refresh / logout / issued-token lifetime | BLOCKED | No session obtained; no pre-existing session was touched. |
| E01 | Confirmed/unconfirmed/pending current email | BLOCKED | No real `/user` observation available; no email-change mutation. |
| M01 | Zero-factor raw inventory | BLOCKED | Requires the first legitimate campaign session; SDK omission normalization cannot supply evidence. |
| M02 | Unverified / one verified / multiple factors; AAL1/AAL2 | BLOCKED | No eligible account; initial-enrollment gate remains enforced. No out-of-band enrollment bypass. |
| M03 | Additional/backup authenticator recovery | BLOCKED | Requires supported existing-factor evidence/challenges; no factors created. |
| W01 | Recovery request / callback / password update | BLOCKED | Controlled inbox/configuration missing; existing sensitive-action restrictions unchanged. |
| W02 | Email/password changes / reauthentication | BLOCKED | No eligible current session/evidence; no assurance invented from AAL2. |
| U01 | Native profile creation / uniqueness / idempotency | BLOCKED | Requires an eligible real subject; no fabricated principal, profile link or legacy credential. |
| U02 | Hosted-auth ratings / personal/group resources / switching | BLOCKED | No real eligible principal reaches the local app. Earlier fictional-provider passes are separate evidence. |
| N01 | Malformed callbacks / provider outage / actual expiry | NOT RUN | No authenticated real-provider campaign started. Existing offline adversarial tests are not fresh hosted results. |

## C. Provider compatibility

Only public JWKS compatibility was observed live. Actual JWT claims, native `/user`
fields, email timestamps/status, factor inventories and session behavior remain unknown.
Do not infer those properties from public signing keys, documentation or historical tests.
Official [getUser](https://supabase.com/docs/reference/javascript/auth-getuser),
[listFactors](https://supabase.com/docs/reference/javascript/auth-mfa-listfactors)
and [redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls)
describe supported interfaces; they do not attest this hosted project's configuration.
Pinned SDK **2.119.0** and existing signup PKCE/S256 root mechanism remain unchanged.
An omitted, null or empty factor response must not unlock initial enrollment/provisioning.
If observed, preserve denial and submit a separate supported-completeness/design decision.

## D. Defects and corrections

No actual account-response or application/provider defect could be established before
the configuration gate. No runtime code, policy, tests, dependencies or hosted settings
were changed. The temporary local preflight script initially lacked the repository import
path; that harness-only error was corrected before its successful local assertions.
Browser runtime failure is a tooling/access blocker, not evidence of a Movelle defect.
This report PR records partial preflight and blockers; it does not certify hosted acceptance.

## E. Security gates preserved

Native email confirmation and exact project JWT verification precede application access.
Fresh factor evidence, required AAL, numeric mapping, ownership and group consent remain
independent checks. No normalization of unknown factors, JWT-only authorization, legacy
fallback, account claiming, email-only MFA recovery or fabricated recent-password proof.
All factor removal, lost-all-authenticators recovery and enrolled sensitive updates retain
their existing restrictions. No previous user, factor, session or credential was inspected
or changed. Credentials, addresses, tokens, links, seeds and provider bodies are absent here.

## F. Resource budget and private ledger

| Resource | Used | Ceiling |
|---|---:|---:|
| New synthetic Supabase accounts | **0** | 4 |
| Provider-generated authentication emails | **0** | 10 |
| New MFA enrollments | **0** | 10 |

There was **one public JWKS GET**, zero authenticated Auth requests and zero provider
mutations. A connected Gmail profile was detected privately; it was not automatically
designated a test inbox, and no email contents were searched/read or messages sent.
Private temporary ledger reserves labels A/B only; records contain purposes, not addresses,
passwords, JWTs, links or seeds. Both are not-created, MFA-not-started, cleanup-not-applicable.
No account cleanup is needed; no unrelated or previous synthetic account is eligible.
The owned local PG container was stopped/removed; no staging listener remains.
No paid resource, SMTP probe, quota stress or cloud provisioning occurred.

## G. Executed tests and evidence boundaries

Commands executed from repository root:

- `git fetch origin main`; `git rev-parse origin/main`: expected SHA in A.
- `git diff --quiet 0178e273b5bf5ce8b8406a0ae5fab2add691aee8 HEAD`: matching merged tree.
- `.venv/Scripts/python.exe` with existing `SupabaseTokenVerifier`, `_download` and
  `_parse` against the explicit public JWKS: PASS, sanitized algorithm/curve/count output only.
- `.venv/Scripts/python.exe .pytest-tmp/acceptance_local_preflight.py`: PASS for PG17,
  schema 3, empty synthetic database and loopback-only Docker port binding. Temporary
  helper is uncommitted; it obtains only its owned local container credentials privately.
- UI tool initialization: BLOCKED, Node runtime path unavailable; no screenshots or
  authentication content captured. Local port inspection found no staging listeners.

No runtime fix was made, so earlier full suites/builds were not relabeled as newly executed
real-provider tests. The [pre-merge audit](STAGING_PREMERGE_AUDIT.md) records historical
offline/fictional-provider results; those remain useful regressions, not hosted proof.
Report-only PR size and hosted CI results are recorded on its exact head in the PR ledger.

## H. Private deployment readiness

**Not ready for private cloud deployment.** Local composition remains intentionally
loopback-only. Exact frontend/backend/database targets, privacy/ingress, HTTPS origins,
root callback allowlists, CORS/TLS adaptations and incremental **$0** costs need separate
owner decisions and reviewed changes. No cloud target is guessed or provisioned.
SMTP delivery/spam/sender limits, factor completeness and legitimate authenticated
end-to-end acceptance remain open. No deployment approval follows from this campaign.

## I. Smallest remaining owner actions

1. Privately make the existing dev project's public URL/publishable key available in
   local configuration and supply its path; do not send passwords, keys or links in chat.
2. Designate a controlled test inbox, or explicitly select unique aliases of the
   connected Gmail inbox. Inbox connection alone is not test-recipient designation.
3. Confirm the current dashboard project/Free identity, Confirm Email enabled, native
   signup template and exact `http://127.0.0.1:5173/` redirect already allowed. If absent,
   redirect-dependent tests stay blocked; configuration changes need separate approval.
4. After a real zero-factor observation, review any supported completeness/design
   blocker before initial MFA/provisioning; approval to test is not a policy bypass.

Bounded testing is already authorized and does not need another general approval.
No known runtime code defect is asserted. Full NIST assessment, the original 16-stage
audit, later Stages 24–26 and production cutover/legacy-data decisions remain separate.
