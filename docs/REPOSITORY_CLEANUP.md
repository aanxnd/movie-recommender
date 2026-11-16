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

No authentication, JWT, provider policy, MFA, ownership, migration, numeric data,
recommendation mathematics or active production code is deleted by these retirements.
The private gateway core/backend remain temporarily test-referenced until their
dependent cleanup replaces the abandoned image check; do not execute old walkthroughs.

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
