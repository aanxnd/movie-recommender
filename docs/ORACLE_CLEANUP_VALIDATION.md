# Oracle preparation and cleanup validation

Review order: owner-corrected PR111 → PR112 image/reference → PR113 Compose/proxy
→ PR114 native Vercel → PR115 private bundle retirement → PR116 native operator
→ PR117 private gateway/image/CLI retirement → PR118 private backend retirement
→ PR119 historical-plan consolidation → PR120 current auth contract → this handoff.
Each child diff is under500 changed lines; rebase descendants after squash merges.
No merge/deployment or production activation follows from these checks.

## Reproduce only in isolated local fixtures

- Python: locked requirements-dev.txt, Python3.14; prepare/verify bundled Small in
  a new local test directory. Run `python -m pytest -q -p no:cacheprovider` with
  `POSTGRES_TEST_URL` privately set to a loopback PostgreSQL17 **disposable** DB.
  Never inherit hosted DATABASE_URL; schema fixtures allocate unique verify_ schemas.
- Frontend: Node24, `npm ci`, `npm test`; normal `npm run build` stays legacy.
  `node scripts/check-native-build.mjs` verifies synthetic approved native build
  and unapproved-build refusal; no production manifest or hosted URL is used.
- Browser: default Playwright suite plus provisioning/staging configurations use
  local servers/fictional Auth. Live artwork is an existing explicit opt-in and
  requires separate authority; never supply real provider keys to an offline run.
- Container: `docker buildx build --platform linux/arm64 --load -f deploy/oracle/Dockerfile ...`
  uses existing free local emulation. Public standard ubuntu-24.04-arm CI separately
  checks actual aarch64 imports/tests. Neither is A1 hardware capacity/Neon TLS proof.
- `python scripts/check_oracle_proxy.py` uses a fictional certificate and new UUID
  loopback-only container; checks Compose parsing, TLS, Host/SNI refusal, body cap,
  fixed redirect and log isolation, and removes only its own fixture.
- Reference: `python deploy/oracle/reference.py --prepared EXISTING_DIRECTORY`
  verifies the exact32M manifest and arrays/license without writes/downloads. Optional
  packaging uses NEW output, verifies archive contents independently and authorizes
  no publication. Repeat in the pinned runtime to compare deterministic hashes.
- Whitespace/import/links/locks: `git diff --check`, Python AST parsing and
  `pip check`; resolve all tracked local Markdown links/anchors and exact imports.
  No dependency pin/Python version or algorithm changed.

## Test retirement and scope

Thirty-three Node cases are removed only with deleted private interfaces (one package,
two wrappers,30 gateway including24 generated parameter cases). Forty-two backend cases are removed only with deleted
private entry/config/gate/CLI (32+3+7). Replacements add20 image/reference,19 renderer/
Compose and11 native operator cases plus one native package case. Existing JWT/MFA/
session/ownership/race/DB/recommendation tests remain. See [file-level evidence](REPOSITORY_CLEANUP.md).
These counts are not an effort to preserve a headline total; each behavior has an
independent current protection or an explicit obsolete-contract rationale.

Current-head results/CI links are recorded in the PR descriptions and final handoff;
historical verification counts are not aggregated. Actual A1 resources/TLS renewal,
Neon production schema/grants/restore, public Vercel protection/promotion, mail,
MFA/removal/deletion races and the full NIST/16-stage audit remain incomplete.
Existing10/10 hosted budget stays exhausted; no real mutation is part of validation.

## Full browser-suite fixture correction

The broader offline run exposed two artwork tests that implicitly needed live
credentials and a password test that assumed email was the first tab stop. The
existing AuthFrame theme button precedes email; the test now checks both stops.
The artwork cases reuse the existing synthetic candidate/image fixture, retaining
canonical IDs, credits, ordered fallbacks and honest missing-image assertions.
No application authentication or artwork behavior changed, and no cases were
removed/skipped. The existing opt-in live artwork case still needs separate
credentials/authorization. CI now runs the complete default suite and isolated
provisioning configuration alongside the existing staging integration suite.
