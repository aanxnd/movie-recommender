# Hosted factor-inventory review - Stage 23, not Prompt 24

**OWNER-APPROVED CONTRACT - IMPLEMENTATION UNDER REVIEW**

The owner approved the response contract and non-atomic freshness limitations
below. This implementation allows native no-factor AAL1 provisioning/first setup;
null/malformed/unsupported evidence and verified-factor AAL2 requirements remain.
The earlier blocked verdict described the superseded omission-denial policy.
Hosted validation and separate merge/deployment approvals are still required.

## Evidence and precise conclusion

Review baseline: main `597d13b1c823a1c3cdf7adc193343f6274f0d560`.
[PR87](https://github.com/aanxnd/movie-recommender/pull/87), head
`38d38287ac14a79a68cdd1ec34ca5bc19b3ca52b`, separately records actual development
responses: fresh `/user` omitted `factors` for the campaign account, including after
refresh/reset/login. Zero factors were enrolled by that campaign. Its health
endpoint reported GoTrue **v2.197.0**. This does not attest an immutable/unmodified
hosted binary, all factor states, future upgrades or the absence of provider defects.

Pinned official provider source establishes expected stock behavior:

- [User model](https://github.com/supabase/auth/blob/v2.197.0/internal/models/user.go):
  `Factors` is a slice with `json:"factors,omitempty"`. Both nil and zero-length
  slices are omitted. `FindUserByID` uses `findUser`, which eagerly loads associations;
  lookup errors are propagated. There is no verified-only filter in that lookup.
- [Authentication middleware](https://github.com/supabase/auth/blob/v2.197.0/internal/api/auth.go):
  validates the bearer token and loads its subject's user/session before the handler.
  [UserGet](https://github.com/supabase/auth/blob/v2.197.0/internal/api/user.go)
  returns that loaded user after audience checks. Under this source path, a
  successful empty inventory is expected to serialize without a `factors` member.
- [Routes](https://github.com/supabase/auth/blob/v2.197.0/internal/api/api.go) and
  [API specification](https://github.com/supabase/auth/blob/v2.197.0/openapi.yaml):
  public authenticated `/factors` provides enrollment, not a TOTP inventory GET.
  General factor listing is under privileged `/admin/users/{userId}/factors`.
  Recovery-code/passkey operations are not a substitute for TOTP completeness.
- [SDK2.119.0 source](https://github.com/supabase/supabase-js/blob/v2.119.0/packages/core/auth-js/src/GoTrueClient.ts):
  `_listFactors()` calls `getUser()`, iterates `user?.factors ?? []`, returns `all`
  plus verified type buckets. Unsupported types survive in `all`. Omitted, null
  and explicit empty inventories therefore normalize alike. `getAAL(jwt)` decodes
  claims and repeats the same user-data inference; without a JWT it uses session
  data. Neither is independent completeness or signature-verification evidence.

Official [listFactors reference](https://supabase.com/docs/reference/javascript/auth-mfa-listfactors)
provides a supported user API, but no completeness bit, total count, snapshot
revision or separate negative attestation. The [MFA guide](https://supabase.com/docs/guides/auth/auth-mfa)
requires backend enforcement for opted-in users; its Auth-table RLS example is not
an approved solution for Movelle's separate Neon database. No privileged access is proposed.

**Distinction:** source-supported zero-factor omission is established for the
reviewed implementation. Independent detection of a valid-JSON response that
erroneously omits an enrolled user's factors is not established. Those two
responses are indistinguishable on this wire. SDK normalization cannot repair it.

## Candidate comparison

| Candidate | Assessment |
|---|---|
| SDK empty array or `nextLevel=aal1` as proof | Reject: same underlying response, normalization and sometimes cached state; client results never authorize FastAPI. |
| Signed AAL alone | Reject: AAL1 also exists before an enrolled user completes MFA; AAL2 is not inventory or recent-MFA evidence. |
| Fresh provider `/user` with reviewed omission semantics | Recommended for owner review: standard user-token/public-key access, no extra service. Requires explicit acceptance of provider serialization as authoritative snapshot semantics, not an independent completeness guarantee. |
| Enroll directly while inventory is unknown, then demand AAL2 | Not a complete optional-MFA solution: no-MFA provisioning stays blocked, and bypassing the reviewed bootstrap precheck requires a separate decision. Do not implement this workaround. |
| Mandatory AAL2 for every account | Changes optional MFA to mandatory and still needs approved bootstrap; not selected. |
| Admin listing, Auth DB reader or new custom ledger | Outside approval, unnecessary for the proposed standard design; not implemented. |

## Approved replacement; code review and hosted validation pending

Trust one fresh TLS-pinned provider response, obtained with the exact already
verified token, as the inventory snapshot **only if the owner approves that API
trust contract**. Do not introduce a caller-controlled completeness flag, accept
SDK-normalized inventory from a browser, or add a generic normalization helper.

1. Keep ES256/project/issuer/audience/subject/session/expiry validation. Server reads
   `/user` directly using the public key and that token, with existing no-redirect,
   timeout/size limits, strict JSON parsing and exact subject/native-email binding.
2. Only at this trusted response boundary, interpret an absent member or explicit
   `[]` as zero under the approved provider contract. Null, malformed, duplicate,
   oversized or unsupported factors remain unknown and deny. A partial nonempty
   array with valid entries also has no completeness marker: provider truthfulness
   remains a necessary assumption, not something JSON validation proves.
3. Verified TOTP requires signed AAL2 for backend access/provisioning. Zero or only
   unverified factors permits AAL1 and optional-MFA provisioning. AAL2 with no
   verified factor is conflicting/stale: deny and require fresh reconciliation.
4. Frontend uses the same reviewed raw-response semantics within its private signed
   observation and credential lease. Add an explicit no-factor state. First setup
   requires AAL1/no factors; pending setup resumes its existing owned challenge.
   Additional setup requires current verified AAL2 and no pending factor. Enrollment
   creates an unverified factor, grants no backend access and never substitutes for
   OTP verification. Keep the uncertain-outcome latch and no automatic retries.
5. Use existing native enroll/challenge/verify and verify the promoted signature,
   same subject/session transition and fresh inventory before reporting success.
   Keep all removal unavailable, backup-factor guidance and all-device-loss refusal.
   Do not infer fresh password proof or recent MFA from AAL2.
6. Backend rereads provider data on each check; no success cache, session-row
   observer, legacy fallback, frontend grant or client-selected numeric ownership.
   Existing Neon mapping/uniqueness/ownership/privacy checks remain authoritative.

This changes the explicit current rule that *every* omission is unknown. It also
removes the extra empty-inventory provisioning/bootstrap restriction. These are
owner review decisions, not silent bug fixes. If the owner requires detecting any
erroneously incomplete successful provider response, this candidate is insufficient;
no approved independent authority for that stronger requirement was established.

## Threat model and limits

| Threat | Required control / remaining limit |
|---|---|
| Enrolled user sends AAL1 or spoofs AAL2 | Verify signatures first; fresh verified factor requires signed AAL2. Never use client booleans, decoded-only JWTs or type buckets. |
| Null/error/malformed inventory | Deny on null/unknown types, duplicate IDs, partial transport, bad JSON, timeout,401/403/429/5xx; never reuse last successful state. |
| Provider silently omits/truncates factors in valid JSON | No independent detector. Approving trusted snapshot semantics accepts this provider-defect risk. Version/build reporting and acceptance tests reduce uncertainty, not prove impossibility. |
| Enrollment between read and local write | A fresh snapshot is not atomic with a Neon commit. Already in-flight work may finish using its earlier observation. No claim of instantaneous enforcement across databases; reread on subsequent operations and after MFA changes. Owner must accept this limit. |
| Concurrent first enrollments | Native [validateFactors/verify](https://github.com/supabase/auth/blob/v2.197.0/internal/api/mfa.go) checks verified-factor/session assurance and promotes verification while invalidating lower-AAL sessions/cleaning pending factors. Enrollment validation occurs before creation, so do not claim cross-device serialization. Reconcile fresh state; never auto-retry unknown outcomes. |
| Account switch/logout/refresh during request | Preserve private generation/subject/session fences, cancellation and late-result rejection. A new account cannot inherit another account's observation or setup. |
| Old AAL1 token after opt-in | Fresh verified inventory denies it even if token remains unexpired; expired tokens and provider session rejection deny. No cached zero-factor authorization. |
| Stale AAL2, disabled/unknown factor type | Conflicting evidence denies; AAL2 is not proof of current inventory, recent MFA, email or application ownership. |
| Last-factor removal/lost all devices | No removal or password/email/support bypass added. This review does not resolve those existing gates. |

## Offline characterization and approval gates

New `frontend/src/mfa-sdk-contract.test.js` exercises the installed real SDK with
mocked HTTP and locally signed tokens. Ten cases confirm omission/null/empty
normalization, pending/verified/unsupported factors, one fresh `/user` call per
listing, HTTP401/429/500 errors and malformed inventory. These do **not** execute
GoTrue, prove hosted loading completeness, or validate any replacement policy.
Existing backend policy/email **87 passed**; selected MFA evidence/service/management/
session/recovery-race tests **102 passed**. Existing omission-after-enrollment
regressions remain and pass. Node worker spawn initially failed under the sandbox;
the same offline tests passed with process permission. No test was weakened.
Full `npm test`: **586 passed**; production and staging builds passed (existing
staging chunk-size warning). No runtime, dependency, schema or hosted change.

The owner has now approved both decisions for implementation:

- Use the narrow trusted-provider response contract, accepting its inability to
  independently detect silently incomplete valid JSON.
- Accept fresh-read/in-flight concurrency limits rather than an atomic cross-database
  enrollment guarantee. Keep optional MFA, backend enforcement and all other gates.

Implement/test this approved semantic change in focused PRs, each
at most500 changed lines. Required adversarial coverage: zero/pending/verified/
multiple factors at both AALs, null/unknown evidence, previously enrolled response
loss under the chosen contract, switching/refresh/logout, timeouts and enrollment
races; test the first-factor-to-AAL2 path and non-MFA provisioning separately.

Hosted validation then requires a new bounded plan and resource reconciliation.
Last campaign ledger: **1/4 accounts,7/10 conservative email reservations,0/10 factors**;
only five messages had arrived at close. Do not refund outstanding reservations.
The campaign account lacks retained login credentials, its local database is stopped,
and browser/controller capabilities were removed. Confirm private user access,
approved inbox, exact redirect and isolated local resources before any mutation.
This review made **zero** hosted project requests or mutations. No hosted factor
state beyond PR87's zero-enrollment campaign is claimed.

## Separate PR87 merge review

PR87 is independently ready to merge after owner review: five documentation
files, **209 added+2 deleted=211 lines**, no runtime/dependency/policy changes.
Its exact-head [CI](https://github.com/aanxnd/movie-recommender/actions/runs/43542426069)
passed1420 backend/9 skips,576 frontend, both builds and11 fictional-provider staging
browser tests; [PR size](https://github.com/aanxnd/movie-recommender/actions/runs/43542451077)
and Vercel passed. It honestly records partial hosted acceptance and remaining gates.
Its report does not approve a fix or deployment. Do not merge automatically; a main
merge can trigger the existing legacy Vercel production build. No merge was done.

This proposal does not start Prompt24, activate authentication, change any hosted
setting, spend money, alter production data or remove existing denial tests.
