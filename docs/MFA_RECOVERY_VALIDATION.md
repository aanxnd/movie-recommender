# Prompt 21 offline validation

Starting main: `19bd7cc62b777a1bee4f6f1191d151c0a31ded7a` (Prompts 1–20 merged).
Both supabase-js/auth-js remain pinned to 2.119.0. No dependency, production route,
backend policy, schema, runtime credential or hosted configuration changes.

## Local results

- Full frontend suite: **523 passed**, no skips/failures (58 additional tests).
- Production build passed; existing asset hashes unchanged. No recovery screen is
  included in production entry assets.
- Backend email/AAL/identity/ownership regressions: **297 passed**, disposable local
  PostgreSQL 17. Existing httpx deprecation warning only.
- PR-size checker unit tests: **10 passed**, also included in the backend total.
- Chrome: **12 passed** across recovery (3), existing MFA (3), account/settings (5),
  password/recovery (1), including mobile/desktop keyboard and dialog-focus checks.
- Desktop/mobile visual inspection completed with synthetic offline fixtures.
- New UI tests also passed under an ephemeral Node 24 runtime (8 tests); project
  dependencies were not changed. Hosted Linux checks are independently required.

The exact initial PR #67 commit also passed **519/519** tests in an isolated Linux/
Node 24 container. Its hosted frontend attempt stalled inside `npm test`; this local
reproduction does not substitute for a successful hosted run. GitHub rejected retry
while it remained running (403). No test or workflow was skipped to conceal that state.

The first browser launcher attempt timed out waiting for the local API before tests
ran; an unchanged retry started successfully. Browser testing then exposed a real
modal-return-focus defect; the trigger reference was fixed, regression-tested, and
all 12 browser tests subsequently passed. No readiness check was removed or weakened.
No lint/typecheck script exists. Temporary capture tooling is removed before commit.

## Evidence and limitations

Offline real-SDK HTTP fixtures with locally signed ES256 JWTs establish local
handling, not hosted Free guarantees. The native operation is always followed by
fresh subject/session/AAL/inventory checks. Replacement verification may promote to
a new native session UUID; only a known rejection may retain the unchanged-session
pending continuation. Unknown writes discard context and clear setup credentials.

All Movelle removal is disabled before DELETE, including concurrent, foreign,
expired, pending-cleanup and nominally multi-factor cases. Earlier tests that assumed
client prechecks made removal safe now assert no provider mutation is dispatched.
This does not claim to restrict direct calls to Supabase's own public APIs.

All-inaccessible recovery refuses; no recovery codes, support-assisted reset, email/
password bypass or recovery-complete claim exists. Initial enrollment/no-MFA inventory
absence, native Free response compatibility, capacity/QR/promotion/replay/race tests,
password/email reauthentication and authoritative removal protection remain blocked.
See [the threat model and exact hosted acceptance checklist](MFA_RECOVERY.md).

NIST assessment, full professional audit and launch review remain required.
No hosted account/factor/email/SQL mutation, deployment, merge, paid service,
superseded PR #34–36 change or Prompt 22 work occurred. Production remains dormant.
