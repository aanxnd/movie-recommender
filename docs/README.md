# Documentation map

## Authoritative current guidance

| Question | Primary documentation |
|---|---|
| Overview, development and application architecture | [Project README](../README.md); current deployed Azure versus selected future native Oracle is explicitly distinguished. |
| Authentication/authorization | [Current contract](AUTH_ARCHITECTURE.md), [policy evidence](AUTH_POLICY_EVIDENCE.md), [ownership/groups](RESOURCE_AUTHORIZATION.md). |
| Database, migrations and rollback compatibility | [Database guide](DATABASE.md), [profile revisions](PROFILE_REVISION.md). |
| Selected deployment preparation | [Oracle/Compose runbook](ORACLE_RUNBOOK.md), [Vercel native release](VERCEL_NATIVE_RELEASE.md), [native entry contract](NATIVE_RELEASE.md). |
| Existing production release/rollback | [Azure procedure](DEPLOYMENT.md), retained until approved Oracle cutover; not a native deployment shortcut. |
| Security limitations and operational decisions | [Configuration facts/gaps](AUTH_CONFIG_AUDIT.md), [account-operation gates](ACCOUNT_OPERATIONS_READINESS.md). Full NIST assessment/16-stage audit remain separately required. |
| Testing | [Current verification commands](ORACLE_CLEANUP_VALIDATION.md), [local native fixture](STAGING_INTEGRATION.md). |
| Production status | [Launch readiness](PRODUCTION_LAUNCH_READINESS.md), [cutover checklist](AUTH_CUTOVER_READINESS.md). Neither implies activation approval. |

Feature-specific documents (signup/session/password/email/TOTP/provisioning/settings,
artwork, deletion journal/worker) explain supported code and independent tests;
they are technical appendices, not additional deployment procedures. Labels such
as `staging`/`legacy` do not make shared code or meaningful tests disposable.

## Evidence retained for traceability

- [Actual initial provider campaign](STAGING_SUPABASE_ACCEPTANCE.md) and
  [MFA follow-up](NATIVE_MFA_FIX_ACCEPTANCE.md): sanitized genuine Auth evidence,
  local application DB, exhausted10/10 budget; not public deployment acceptance.
- [Checkpoint](STAGING_CHECKPOINT_REPORT.md), [nine-PR audit](STAGING_PREMERGE_AUDIT.md),
  [original verification](VERIFICATION.md), [audit resolution](AUDIT_RESOLUTION.md):
  dated historical findings, not current merge permission or final professional audit.
- [Retired private proposal](evidence/RETIRED_PRIVATE_PREVIEW.md): consolidated
  owner resource/cost/no-execution evidence; old private commands must not be used.
- [Cleanup inventory](REPOSITORY_CLEANUP.md): every deletion/replacement, test
  rationale and retained rollback/data/security boundary.
- Licenses, source attribution, recommendation traces/benchmarks and dependency
  advisory snapshot remain attached to their original artifacts.

Consult current-head CI and readiness first. Historical successful counts, proposed
configuration and merged code do not establish hosted settings, CA$0 or release safety.
