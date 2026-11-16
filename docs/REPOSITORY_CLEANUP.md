# Repository cleanup inventory — Oracle preparation, no production retirement

Baseline: main `f054300` plus owner-selected PR111. Audit covers tracked application,
frontend, tests/browser fixtures, scripts, locks, workflows, deployment and Markdown.
Import/name scans were followed by exact import/dynamic-import/subprocess/CLI,
package-script, Docker, CI and documentation searches before each deletion.
Tests alone do not make an abandoned deployment interface a production requirement.
No ignored secrets, local staging data, legal attribution or hosted records are removed.

## Confirmed retirements (file-level)

| Original file | Evidence/reason | Replacement or retained protection |
|---|---|---|
| `frontend/scripts/prepare-private.mjs` | Only npm `prepare:private` and its test invoked it; packages an undeployed Azure/Vercel gateway proposal. | `prepare-native.mjs` packages selected static Vercel artifact; exclusive path/secret tests retained there. |
| `frontend/private/targets.mjs` | Only retired compiler/config/test imports; hardcodes undeployed private Azure/branch targets. | Native manifest validation, Oracle renderer, native-runtime and native-release configuration tests. |
| `frontend/private/handler.mjs` | Only copied into retired bundle; never normal `frontend/api`. | Direct native API with verified JWT/ownership; no public server gate. |
| `frontend/private/index.html` | Only private Vite config selected it, not normal/native entry. | `frontend/native/index.html`; callback/native browser coverage retained. |
| `frontend/private/vercel.json` | Only private compiler copied it; not live `frontend/vercel.json`. | Native bundle generated strict origin headers; existing production config untouched. |
| `frontend/vite.private.config.js` | Only retired compiler selected it. | Explicit native Vite config/build; default legacy build retained. |
| `frontend/src/private-main.jsx` | Only private HTML referenced it. | `native-main.jsx`, same tested auth/screens/movie components. |
| `frontend/src/private-runtime.js` | Only private main and two wrapper tests referenced it. | `native-runtime.js` preserves exact origin/project pins and session fences. |
| `frontend/src/private-package.test.js` | One case concerns deleted packaging and private-Azure-only constraints. | `native-package.test.js` protects exclusive paths, no server markers and exact CSP/static bundle; native-release/renderer tests retain exact-target refusal. Private branch exclusions are obsolete for production preparation. |
| `frontend/src/private-runtime.test.js` | Two cases cover deleted wrapper, not independent policy. | `native-runtime.test.js`, `staging-runtime.test.js`, callback/session/isolation suites retain malformed config, URL scrubbing, no provider I/O and legacy-storage/account fences. |
| `frontend/private/gateway.mjs` | Only its test consumed it after bundle retirement; never a live Vercel API path. | Native API authorization and actual Oracle Host/SNI proxy checks; no server capability advertised. |
| `frontend/src/private-gateway.test.js` | Six cases concern deleted gateway-only capability/route semantics. | Native auth/resource/group/body/rate tests and Oracle TLS/Host/SNI/body/redirect/log tests retain relevant protections. |
| `app/private_manage.py` | Only private CLI/walkthrough and tests; no current Azure startup/workflow reference. | `deploy/oracle/manage.py` retains separate-role/exact-target/generic-error checks; active `app.manage` preserved. |
| `tests/test_private_manage.py` | Seven cases target deleted private CLI. | Eleven native operator cases retain idempotence/target/role/TLS/command guards plus malformed-file checks. |
| `deploy/private-stage23/Dockerfile` | Undeployed alternative; only old image CI/walkthrough referenced it. | New native image/read-only no-network startup-refusal CI; root Azure Dockerfile remains. |
| `deploy/private-stage23/Dockerfile.dockerignore` | Applied only to removed alternative Dockerfile. | New runtime-only image context; existing Azure context retained. |
| `deploy/private-stage23/containerapp.example.yaml` | Private placeholder, never applied by production workflow. | Proposed Oracle Compose; current Azure production release/rollback unchanged. |
| `deploy/private-stage23/targets.example.json` | Only abandoned private tooling/CI consumed it. | Native unapproved target template and exact native/Oracle validators. |
| `docs/PRIVATE_GATEWAY.md` | Instructions for removed undeployed gateway. | Current Vercel/Oracle runbooks; actual provider evidence remains separate. |
| `app/database.py::Base` import | No internal use or import/dynamic/export consumer; metadata belongs to `app.models`. | Model/migration regression tests retained, no model/schema removed. |
| `app/limits.py::time` import | No Name use or external attribute/import reference. | Rate/concurrency behavior unchanged. |
| `app/staging_profiles.py::database` import | No Name use or external attribute/import reference. | Active owned resource-service regressions retained. |
| `app/private_config.py` | Consumers were removed private entry/CLI and their tests; no normal/native runtime import. | Native exact manifest/TLS/role validation plus Oracle file-secret/renderer tests; private Azure exclusions are no longer a supported target. |
| `app/private_entry.py` | Only alternative private Dockerfile/test/walkthrough selected it; never current production. | Explicit native release/Oracle wrapper; native resource, legacy-denial and startup-refusal regressions remain. |
| `app/private_gate.py` | Only private entry/boundary tests consumed it. | Public native authentication/ownership is mandatory; no server-only preview capability is part of selected design. |
| `tests/test_private_boundary.py` | Private-only config/gate fixture and parameterized cases; no remaining consumer. | Native release/image/renderer, actual Host/SNI proxy and authentication regressions cover selected contract. |
| `tests/test_private_entry.py` | Three cases exercise deleted private composition. | `test_native_release.py`, staging native/resource/policy/group suites and image-startup refusal retain resource/JWT/MFA/legacy-isolation coverage. |
| `docs/PRIVATE_RUNTIME.md` | Describes removed alternative; not actual Azure release/rollback instructions. | Native release and Oracle runbooks plus this inventory. |

No authentication, JWT, provider policy, MFA, ownership, migration, numeric data,
recommendation mathematics or active production code is deleted by these retirements.
The undeployed private gateway/backend/image are now retired after native replacement
checks. Historical walkthroughs must not be executed; actual provider evidence remains.

## Deliberately retained / review later

- Root Dockerfile, Azure controlled-release workflow/manifests, migration shell,
  `app.runtime/main/security/manage`: existing deployment, data compatibility and
  rotation/rollback. Retirement requires actual approved Oracle cutover first.
- Native composition imports `staging_profiles`, `staging_recommendations` and
  shared fixtures: names are historical; implementations are active security code.
- Local staging launchers/DB guards, fictional Auth, browser demos and race tests:
  repeatable offline acceptance; ignored owner databases/config stay intact.
- Migrations1–4, legacy credential tables/operator tools: existing-data/rollback
  obligations; no automatic claiming, linking or legacy fallback added.
- Optional native OTP verifier and account-removal candidates: documented supported
  security boundaries/adversarial coverage; execution stays disabled.
- Licenses/fonts/data attribution, security decisions, recommendation traces,
  real-provider evidence and NIST/16-stage audit scope remain required.
- Ignored local `CODEX_CONTEXT.md`/design audits are owner working files, not tracked
  production inputs; preserved rather than silently deleted or committed.

Validation is recorded per PR and in the final readiness handoff. Removed private
tests are supported-interface retirement, never a means to make CI pass.
