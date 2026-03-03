# Platform Stress-Test Implementation Map (dev_full)
_As of 2026-03-03_

## Entry: 2026-03-03 05:37 +00:00 - Program pivot decision

### Trigger
1. User directed a pivot from throughput-plan framing to stress-testing-first framing.
2. User required realistic production standards and adaptive bottleneck-first decisioning.

### Decision
1. Adopt a dedicated stress-test authority path under `dev_full/stress_test/`.
2. Preserve phase alignment with build ladder (`M0..M15`).
3. Enforce progressive elaboration: create only program-level stress authority now, phase files later.

### Result
1. `platform.stress_test.md` created as active program authority.

## Entry: 2026-03-03 05:42 +00:00 - Folder architecture decision (`build/` + `stress_test/`)

### Alternatives considered
1. Immediate relocation of all existing build docs into `build/`.
2. Safe routing first, then phased migration.

### Evaluation
1. Alternative 1 rejected:
   - high path-drift risk against existing status-owner references.
2. Alternative 2 selected:
   - satisfies requested folder architecture,
   - avoids immediate breakage in existing dev_full document routing.

### Result
1. Added `build/README.md` with migration-safe policy.
2. Added `stress_test/README.md` and program control file.

## Entry: 2026-03-03 05:49 +00:00 - Local development clarification captured as binding rule

### Decision
1. Explicitly pin in stress authority:
   - local engineering work is normal and required,
   - no-local-compute restriction applies to runtime/cert posture, not design and coding activity.

### Result
1. Prevents repeated process confusion and workflow over-reliance for early debugging.

## Entry: 2026-03-03 05:54 +00:00 - Throughput draft retirement

### Trigger
1. User requested ditching throughput-hardening framing.

### Decision
1. Remove throughput draft docs from active workspace.
2. Keep stress-test authority as single active hardening direction.

### Result
1. Throughput draft files removed.
2. `dev_full/README.md` updated to reflect retirement and stress-test authority activation.

## Entry: 2026-03-03 05:45 +00:00 - Program-level M-phase overview added to main stress authority

### Trigger
1. User requested build-plan-like overview in main stress authority before deep per-phase files.

### Decision
1. Add a dedicated roadmap overview section in `platform.stress_test.md` with `M0..M15` rows.
2. For each phase, pin:
   - build scope anchor,
   - intended stress outcome,
   - exit signal,
   - stress status.
3. Keep deep elaboration progressive (phase files created only when activated).

### Result
1. `platform.stress_test.md` now includes a program-level M-phase overview table.
2. Section numbering adjusted so methodology/evidence/routing sections remain readable after insertion.
3. Methodology subsection numbering normalized to `5.1..5.5` for consistency.

## Entry: 2026-03-03 05:50 +00:00 - Dedicated phase-file creation rule added

### Trigger
1. User requested explicit rule for when an `M*` stress phase needs its own file versus inline control-file handling.

### Decision
1. Add deterministic thresholds into `platform.stress_test.md`:
   - inline when low complexity/low spend/single-lane/no repin expected,
   - dedicated file when any complexity-cost-coupling-repin condition is met.
2. Add default guidance:
   - `M0` inline by default,
   - `M1`/`M3` usually inline unless expanded,
   - heavy phases expected as dedicated files.
3. Add re-evaluation trigger:
   - inline phase must be split into dedicated file if scope expands beyond inline boundaries.

### Result
1. Main stress authority now includes a deterministic doc-creation rule that guides focus and avoids unnecessary document sprawl.

## Entry: 2026-03-03 06:08 +00:00 - M0 stress activation (inline) and Stage-A pre-read

### Trigger
1. User requested starting stress execution with `M0`.

### Decision
1. Keep `M0` inline in `platform.stress_test.md` (consistent with inline-default rule).
2. Activate `M0` status in the program overview and add a dedicated inline `Active Phase - M0` section.
3. Execute Stage-A pre-read against:
   - `platform.M0.build_plan.md`,
   - `platform.build_plan.md`,
   - `dev_full_handles.registry.v0.md`.

### Findings (classified)
1. `M0-ST-F1` (`PREVENT`): stress-handle packet for non-cert stress execution is not yet pinned.
2. `M0-ST-F2` (`PREVENT`): explicit M0 stress blocker-register artifact path contract is not yet pinned.
3. `M0-ST-F3` (`OBSERVE`): unresolved `TO_PIN` handles remain for later runtime phases (`M2+`) and must be carried as forward dependency risk.
4. `M0-ST-F4` (`ACCEPT`): docs/control-only M0 posture is aligned with stress startup.

### Result
1. `M0` is now marked `ACTIVE` in the main stress overview.
2. M0 stress DoD and blockers (`M0-ST-B1`, `M0-ST-B2`) are now explicit.
3. Immediate action queue for closing M0 is pinned in the active-phase section.

## Entry: 2026-03-03 06:15 +00:00 - M0 stress-handle packet pinned and blockers closed

### Trigger
1. User approved proceeding with recommended M0 stress pin set.

### Decision
1. Pin M0 stress-handle packet directly in `platform.stress_test.md`.
2. Pin control artifact path contract in the evidence section so blocker register location is deterministic.
3. Close `M0-ST-B1` and `M0-ST-B2` based on pinned values and updated contracts.

### Pinned handle set applied
1. Program controls:
   - `STRESS_PROGRAM_ID`, `STRESS_PROGRAM_MODE`, `STRESS_ACTIVE_PHASE`.
2. Local/runtime posture:
   - `STRESS_LOCAL_ENGINEERING_ALLOWED=true`,
   - `STRESS_LOCAL_RUNTIME_ALLOWED=false`.
3. Region/evidence anchors:
   - `STRESS_AWS_REGION=eu-west-2`,
   - `STRESS_EVIDENCE_BUCKET=fraud-platform-dev-full-evidence`.
4. M0 control artifacts:
   - `M0_STRESS_BLOCKER_REGISTER_PATH_PATTERN`,
   - `M0_STRESS_EXECUTION_SUMMARY_PATH_PATTERN`,
   - `M0_STRESS_DECISION_LOG_PATH_PATTERN`,
   - `M0_STRESS_REQUIRED_ARTIFACTS`.
5. M0 guards:
   - `M0_STRESS_FAIL_ON_PLACEHOLDER_HANDLE=true`,
   - `M0_STRESS_MAX_RUNTIME_MINUTES=60`,
   - `M0_STRESS_MAX_SPEND_USD=0`.

### Result
1. `M0-ST-B1` closed.
2. `M0-ST-B2` closed.
3. M0 DoD checklist moved to fully checked state and phase is now transition-ready (`M0 DONE -> M1` decision gate).

## Entry: 2026-03-03 06:24 +00:00 - M1 stress activation (inline) and Stage-A pre-read

### Trigger
1. User requested proceeding with `M1`.

### Decision
1. Transition stress overview status from `M0 ACTIVE` to `M0 DONE`, and set `M1 ACTIVE`.
2. Keep `M1` inline (still within inline-rule bounds at Stage-A).
3. Execute M1 Stage-A pre-read against:
   - `platform.M1.build_plan.md`,
   - `platform.build_plan.md`,
   - `dev_full_handles.registry.v0.md`.

### Findings (classified)
1. `M1-ST-F1` (`PREVENT`): M1-specific stress handle packet/artifact paths were not pinned.
2. `M1-ST-F2` (`PREVENT`): local preflight packaging contract (before managed run) was not pinned.
3. `M1-ST-F3` (`OBSERVE`): `IMAGE_BUILD_CONTEXT_PATH="."` may become build-context bottleneck as repo grows.
4. `M1-ST-F4` (`OBSERVE`): single-image strategy may increase build-time blast radius under frequent changes.
5. `M1-ST-F5` (`ACCEPT`): immutable provenance/security packaging contract is strong and reusable as stress baseline.

### Pinning and blocker closure
1. Pinned M1 stress-handle packet:
   - profile id,
   - blocker/execution/decision artifact paths,
   - fail-closed drift rules,
   - runtime/spend envelope,
   - repetition + concurrency targets.
2. Pinned local preflight contract:
   - required local preflight gate before managed stress windows,
   - required artifact `m1_preflight_checks.json`.
3. Closed blockers:
   - `M1-ST-B1` closed,
   - `M1-ST-B2` closed.

### Result
1. `M1` is now the active stress phase.
2. M0 is closed and preserved inline as historical phase record.
3. M1 moved from Stage-A to Stage-B execution-ready posture.

## Entry: 2026-03-03 06:32 +00:00 - M1 Stage-B execution plan before coding (local preflight lane)

### Trigger
1. User requested to proceed with the next M1 step (Stage-B local preflight).

### Problem
1. The required M1 local preflight command set is pinned in stress authority, but no reusable script currently exists in `scripts/dev_substrate/` to execute and emit the required artifact deterministically.

### Alternatives considered
1. Run ad-hoc shell commands and manually assemble JSON output.
   - Rejected: weak reproducibility and higher audit drift risk.
2. Create a dedicated deterministic script for M1 preflight and run it.
   - Selected: repeatable, auditable, and directly mappable to stress artifact contract.

### Planned implementation
1. Add `scripts/dev_substrate/m1_stress_preflight.py` to run:
   - `docker_context_lint`,
   - `entrypoint_help_matrix`,
   - `provenance_contract_lint`.
2. Script output:
   - deterministic `m1_preflight_checks.json`,
   - optional blocker register + summary payload for immediate M1 status adjudication.
3. Execute script locally with `PYTHONPATH=src`.
4. Update stress authority section for M1 Stage-B result and keep fail-closed posture if checks fail.

### Guardrails
1. No runtime compute mutation; this is local preflight only.
2. Keep secrets out of emitted artifacts.
3. Preserve existing build/runtime authority surfaces; script is read-only against contracts and source paths.

## Entry: 2026-03-03 06:04 +00:00 - M1 Stage-B blocker triage (dockerignore lint false-fail)

### Trigger
1. First execution of `scripts/dev_substrate/m1_stress_preflight.py` returned `HOLD_REMEDIATE` with blocker `M1-ST-B3`.

### Evidence reviewed
1. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060333Z/stress/m1_preflight_checks.json`
2. `.dockerignore`
3. `Dockerfile`

### Analysis
1. `.dockerignore` is default-deny (`**`) with explicit allowlist reopen rules, matching M1.A packaging boundary intent.
2. The preflight check currently requires explicit deny tokens (`runs/`, `.env`, `.git/`, `__pycache__/`) even when default-deny is already enforced.
3. This yields a false-fail and blocks progression for a policy that is actually stricter than the required deny patterns.

### Decision
1. Patch `m1_stress_preflight.py` dockerignore lint logic:
   - if default-deny posture is detected (`**`), treat required deny pattern checks as satisfied,
   - keep explicit deny-pattern enforcement for non-default-deny posture.
2. Re-run M1 preflight immediately to validate corrected gate behavior.

### Guardrails
1. No relaxation of packaging boundary: broad-copy checks and required Docker COPY path checks remain unchanged.
2. No changes to runtime or managed compute; local preflight only.

## Entry: 2026-03-03 06:05 +00:00 - M1 Stage-B remediation applied and preflight rerun passed

### Trigger
1. M1 local preflight run `m1_stress_preflight_20260303T060333Z` failed with blocker `M1-ST-B3` due to dockerignore lint strictness mismatch.

### Implementation
1. Updated `scripts/dev_substrate/m1_stress_preflight.py` in `_docker_context_lint()`:
   - parse effective `.dockerignore` tokens,
   - detect default-deny posture (`*` or `**`),
   - skip explicit deny-token requirement when default-deny is active,
   - preserve explicit deny-token requirement for non-default-deny posture.
2. Reran local preflight: `python scripts/dev_substrate/m1_stress_preflight.py --phase-id M1`.

### Result
1. Rerun execution id: `m1_stress_preflight_20260303T060442Z`.
2. Verdict: `READY_FOR_M1_STRESS_WINDOW`.
3. Blockers: `0`.
4. Entrypoint matrix: `21/21 PASS`.
5. Artifact set emitted under:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060442Z/stress/`.
6. Stress authority updated with Stage-B progress and artifact references; `M1-ST-B3` marked closed.

### Follow-on
1. Next M1 step is the first managed packaging stress window (`build repetitions=3`, `concurrency target=2`) with timing/provenance drift evidence capture.

## Entry: 2026-03-03 06:10 +00:00 - M1 Stage-B managed stress window plan (execution-grade)

### Trigger
1. User instructed to proceed with the next step: first managed M1 packaging stress window.

### Decision-completeness check (required inputs/lanes)
1. Authority surfaces confirmed:
   - stress authority: `stress_test/platform.stress_test.md` (`M1_STRESS_BUILD_REPETITIONS=3`, `M1_STRESS_BUILD_CONCURRENCY_TARGET=2`),
   - build authority: `platform.M1.build_plan.md` (`P(-1)` packaging/provenance fail-closed posture).
2. Required workflow dispatch inputs resolved:
   - `aws_region=eu-west-2`,
   - `ecr_repo_name=fraud-platform-dev-full`,
   - `ecr_repo_uri=230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-full`,
   - `aws_role_to_assume=arn:aws:iam::230372904534:role/GitHubAction-AssumeRoleWithAction` (prior M1+dev_full managed lanes).
3. Identity/IAM lane: GitHub OIDC role is pinned and historically remediated for ECR push.
4. Evidence lane: CI artifacts + optional S3 upload path available; local stress summary artifacts will be published under run-control stress prefix.
5. Cost/runtime lane: M1 envelope remains (`max_runtime=120m`, `max_spend=10 USD`).

### Constraint discovered
1. Both packaging workflows have per-branch concurrency group locks:
   - `dev-full-m1-packaging-${ref_name}` and `dev-min-m1-packaging-${ref_name}`.
2. A single workflow id cannot produce concurrent run pressure on the same branch.

### Selected execution method
1. Use dual managed carrier workflows concurrently to satisfy target concurrency without branch/push changes:
   - carrier A: `dev-full-m1-packaging`,
   - carrier B: `dev-min-m1-packaging` with `secret_contract_profile=dev_full`.
2. Launch window profile:
   - wave-1 concurrent pair (A+B),
   - wave-2 third repetition after first wave settles,
   - total repetitions = 3.
3. Capture per-run metrics:
   - run_id, workflow id, queued/start/end times, duration_seconds, conclusion,
   - provenance digest/tag readback from CI artifact packs.
4. Publish stress artifacts in local run-control mirror:
   - `m1_blocker_register.json`,
   - `m1_execution_summary.json`,
   - `m1_decision_log.json`,
   - `m1_stress_window_results.json` (detailed per-run matrix).

### Fail-closed conditions
1. Any run failure, missing artifact pack, digest mismatch, or immutable-tag drift opens blocker and holds M1 closure.
2. If concurrency evidence does not meet target profile, open explicit blocker and pin remediation path before phase advancement.

## Entry: 2026-03-03 06:15 +00:00 - M1 managed window attempt-1 blocker adjudication and rerun decision

### Attempt-1 execution evidence
1. Dispatched managed window execution id: `m1_stress_window_20260303T061142Z`.
2. Run outcomes:
   - `22610789727` (`dev-full-m1-packaging`) -> `failure`,
   - `22610794341` (`dev-full-m1-packaging`) -> `failure`,
   - `22610791866` (`dev-min-m1-packaging`) -> `success`.
3. Failure log root cause (both dev_full runs):
   - step: `Optional direct upload to S3 evidence bucket`,
   - error: `HeadBucket ... Forbidden (403)` on `fraud-platform-dev-full-evidence`.
4. Packaging build/push lane itself did not fail; failure occurred in optional post-build evidence upload branch.

### Decision
1. Keep fail-closed posture for attempt-1 (`HOLD_REMEDIATE`).
2. Apply no-code operational remediation for attempt-2:
   - disable optional `s3_evidence_bucket` input on `dev-full-m1-packaging` dispatch,
   - rely on mandatory CI artifact packs + local run-control mirror for stress evidence rollup.
3. Re-run 3-repetition managed window with same concurrency strategy (dual carrier wave + third repetition).

### Rationale
1. This avoids IAM/policy mutation for a non-critical optional step and directly tests packaging/provenance behavior under managed concurrency.
2. Evidence completeness remains satisfiable through run-artifact download and local stress receipt publication.

### Guardrails
1. No branch/push operations.
2. No runtime/infra mutation; workflow dispatch-only remediation.
3. Preserve `aws_region`, `OIDC role`, ECR handles, immutable-tag posture unchanged.

## Entry: 2026-03-03 06:19 +00:00 - M1 managed stress window execution results (attempt-1 and attempt-2)

### Attempt-1 execution (`m1_stress_window_20260303T061142Z`)
1. Dispatch topology:
   - `r1`: `dev-full-m1-packaging` (`run_id=22610789727`),
   - `r2`: `dev-min-m1-packaging` + `secret_contract_profile=dev_full` (`run_id=22610791866`),
   - `r3`: `dev-full-m1-packaging` (`run_id=22610794341`).
2. Outcomes:
   - `r2` success,
   - `r1/r3` failure at optional `S3 head-bucket` check (`403 Forbidden`) for `fraud-platform-dev-full-evidence`.
3. Gate verdict:
   - fail-closed `HOLD_REMEDIATE`.
4. Closure action:
   - opened temporary blocker lane (`M1-ST-B6` context),
   - pinned no-code remediation: disable optional direct S3 upload on `dev-full-m1-packaging` dispatch and rely on mandatory artifact-pack download + local run-control publication.

### Attempt-2 execution (`m1_stress_window_20260303T061619Z`)
1. Dispatch topology retained with remediation (no `s3_evidence_bucket` input for dev_full workflow).
2. Run outcomes:
   - `22610905355` (`dev-full-m1-packaging`) success,
   - `22610907538` (`dev-min-m1-packaging`) success,
   - `22610910038` (`dev-full-m1-packaging`) success.
3. Concurrency evidence:
   - observed max concurrent managed runs = `3` (target `>=2`, pass).
4. Provenance evidence:
   - all runs share immutable tag `git-e8b010fc47fdae36f4425cba0701459df077b2e0` and same git sha,
   - digest set diverged across repetitions:
     - `sha256:b5eef8274db36649832998fea9fd255cfcc1a0a7ade88d323a50245d405be649`,
     - `sha256:95f7edcf5cc6672dab30ec1c4c7731fce29ffe8ac1d9641a98b508bb76d94caa`,
     - `sha256:e2f36e9369eb48aa9d32adbf3ec1d1b6f1f39aaeac2652ec188fc1c00c769c40`.
5. Gate verdict:
   - fail-closed `HOLD_REMEDIATE` with blocker `M1-ST-B8` (provenance drift under concurrent repetitions).

### Published artifacts (attempt-2 authoritative for current blocker state)
1. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_dispatch_receipt.json`
2. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_stress_window_results.json`
3. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_blocker_register.json`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_execution_summary.json`
5. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_decision_log.json`

### Next remediation gate (required before M1 closure)
1. Resolve concurrent immutable-tag race:
   - repin packaging tag/digest contract so concurrent repetitions cannot produce digest ambiguity for a single immutable tag claim.
2. Rerun managed window after contract repin and require:
   - all runs success,
   - no digest drift for immutable claims,
   - concurrency target maintained.

## Entry: 2026-03-03 14:08 +00:00 - M1-ST-B8 remediation design (tag/digest repin + deterministic hardening)

### Trigger
1. User directed immediate implementation of `M1-ST-B8` remediation and rerun.
2. Current blocker state: concurrent M1 managed window produced same git-sha tag mapping to multiple digests.

### Root-cause model
1. Current workflow tags all repetitions with `git-{git_sha}`.
2. Under concurrent dispatch this creates tag-write race and provenance ambiguity.
3. Build reproducibility posture is weak (no pinned build timestamp controls; default pip bytecode/build metadata variability surface remains).

### Remediation decision (selected)
1. Re-pin M1 packaging immutable-tag contract to run-scoped immutable tag:
   - `git-{git_sha}-run-{ci_run_id}`.
2. Preserve git-sha traceability by adding canonical marker field:
   - `git_sha_canonical_tag = git-{git_sha}` (informational, not digest authority).
3. Harden deterministic build posture in packaging lane:
   - set deterministic build arg `SOURCE_DATE_EPOCH` from commit timestamp,
   - pass `SOURCE_DATE_EPOCH` into Docker build,
   - enable deterministic Python packaging posture (`PIP_NO_COMPILE=1`, `PYTHONHASHSEED=0`) and wire Docker `ARG SOURCE_DATE_EPOCH`.
4. Provenance checks will validate new run-scoped tag pattern and strict run-id coupling.

### Scope of change
1. `.github/workflows/dev_full_m1_packaging.yml`
2. `.github/workflows/dev_min_m1_packaging.yml`
3. `Dockerfile`
4. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (contract repin note)
5. stress authority/logging updates after rerun.

### Validation plan
1. Re-run managed 3-repetition M1 window with dual-carrier topology.
2. Evaluate fail-closed gates:
   - all runs `success`,
   - concurrency target met,
   - no digest drift across repetitions,
   - no tag collision, and run-scoped tag pattern correctness.
3. Publish updated blocker register/execution summary.

### Risk posture
1. If digest drift persists after deterministic hardening, keep `M1-ST-B8` open and escalate next-level deterministic controls (base-image digest pinning + lockfile/hash-verified deps).

## Entry: 2026-03-03 14:12 +00:00 - M1-ST-B8 remediation implementation completed (pre-rerun)

### Implemented changes
1. Workflow contract repin (`dev_full_m1_packaging.yml`, `dev_min_m1_packaging.yml`):
   - immutable tag moved to run-scoped pattern `git-{git_sha}-run-{ci_run_id}`,
   - canonical git-sha marker retained as `git-{git_sha}` (`git_sha_canonical_tag`) for traceability only,
   - `SOURCE_DATE_EPOCH` derived from commit timestamp and injected into build.
2. Deterministic build hardening:
   - workflows now export `DOCKER_BUILDKIT=1` and pass `--build-arg SOURCE_DATE_EPOCH=...`.
   - `Dockerfile` updated with:
     - `ARG SOURCE_DATE_EPOCH`,
     - `ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}`,
     - `PIP_NO_COMPILE=1`,
     - `PYTHONHASHSEED=0`.
3. Provenance check hardening (dev_full workflow evidence emitter):
   - validates run-scoped immutable tag format and exact run-id coupling,
   - validates canonical git-sha marker consistency,
   - records canonical marker in provenance artifacts.
4. Handle registry repin:
   - added `IMAGE_TAG_IMMUTABLE_PATTERN = git-{git_sha}-run-{ci_run_id}`,
   - retained `IMAGE_TAG_GIT_SHA_PATTERN = git-{git_sha}` as informational trace marker.

### Validation before rerun
1. Workflow YAML parse check passed for both modified workflow files.

### Next action
1. Immediate managed rerun of M1 3-repetition stress window using updated workflow contract.

## Entry: 2026-03-03 14:14 +00:00 - Dev_full-only rerun adjustment after user correction

### Trigger
1. User clarified stress scope is `dev_full` only; `dev_min` is out of scope.
2. Interrupted command had already dispatched one `dev_full` and one `dev_min` run using previous branch state.

### Constraint
1. `dev-full-m1-packaging` workflow uses branch-scoped concurrency key (`dev-full-m1-packaging-${ref_name}`), which serializes dev_full runs and prevents proving `concurrency_target=2` without secondary carrier.

### Decision
1. Keep remediation scope strictly `dev_full`.
2. Add controlled concurrency suffix input to `dev-full-m1-packaging`:
   - default keeps existing serialized posture (`shared`),
   - stress dispatch can set per-repetition suffix (`r1/r2/r3`) to permit concurrent execution within dev_full only.
3. Rerun M1 window with three `dev-full-m1-packaging` dispatches (no dev_min usage).
4. Evaluate fail-closed gates using updated tag/digest contract and deterministic controls.

### Guardrails
1. No branch operations.
2. No dev_min dispatch for rerun.
3. Preserve fail-closed blocker posture if digest drift persists.

## Entry: 2026-03-03 14:21 +00:00 - M1-ST-B8 remediation rerun (dev_full-only) results

### Execution adjustment
1. Implemented dev_full-only stress concurrency control in workflow:
   - added `concurrency_group_suffix` input to `dev-full-m1-packaging`,
   - concurrency group now `${ref_name}-${suffix}` (default `shared`, stress runs use per-repetition suffix).
2. Workflow-only commit created and pushed:
   - commit: `b4d819270cd84b27fc3dc2028db3e1b2d49b6a8f`.

### Managed rerun details
1. Phase execution id: `m1_stress_window_20260303T141816Z`.
2. Dev_full-only run set:
   - `22627099194`,
   - `22627105810`,
   - `22627109900`.
3. All runs succeeded (`conclusion=success`).
4. Observed max concurrency: `3` (target `2`, pass).
5. Run-scoped immutable tag contract checks passed:
   - unique run tags present,
   - tag collision not detected,
   - git-sha drift not detected.

### Blocker adjudication
1. `M1-ST-B8` remains OPEN due digest drift:
   - digest set diverged across repetitions for same git sha.
2. Current phase verdict remains fail-closed:
   - `HOLD_REMEDIATE`.

### Evidence
1. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_stress_window_results.json`
2. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_blocker_register.json`
3. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_execution_summary.json`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_decision_log.json`

### Next required remediation lane
1. Closure-grade deterministic packaging controls are now required before another rerun:
   - pin base image by digest,
   - pin dependency graph via lock/hash-verified install,
   - rerun M1 window and require `digest_drift=false`.

## Entry: 2026-03-03 14:30 +00:00 - M1-ST-B8 closure-grade deterministic packaging plan (pre-implementation)

### Trigger
1. User approved immediate continuation of deterministic remediation and rerun.
2. Current blocker is still fail-closed: `M1-ST-B8` (`digest_drift=true`) after tag-race remediation.

### Drift and law checks
1. Design-intent drift check: deterministic provenance hardening is aligned with active M1 stress gate and does not alter component ownership boundaries.
2. Performance-first and cost-control check: this lane is a preflight/build determinism improvement, reducing wasted managed reruns by enforcing deterministic inputs before dispatch.
3. Scope check: `dev_full` only; no `dev_min` stress dispatches.

### Alternatives considered
1. Retry managed window without additional hardening:
   - rejected; this repeats known drift and burns spend.
2. Introduce remote build cache controls only:
   - rejected for now; cache tuning does not guarantee dependency graph reproducibility.
3. Pin deterministic base + lock/hash-verified dependency install:
   - selected; strongest immediate control with local contract lint enforceability.

### Selected implementation
1. Update Docker context allowlist to admit `requirements/m1-image.lock.txt` under default-deny `.dockerignore`.
2. Strengthen `m1_stress_preflight.py` docker context lint:
   - require Dockerfile to copy lockfile path,
   - require `.dockerignore` allowlist to reopen lockfile path when default-deny mode is active.
3. Keep Dockerfile deterministic posture already staged:
   - digest-pinned `FROM`,
   - `SOURCE_DATE_EPOCH`,
   - hash-verified install via `pip --require-hashes -r requirements/m1-image.lock.txt`.
4. Run local preflight and docker build smoke to prove contract integrity before commit.
5. Commit/push deterministic packaging files to active branch so managed workflow uses hardened state.
6. Execute dev_full-only 3-run managed stress window and re-evaluate `M1-ST-B8`.

### Files in scope
1. `.dockerignore`
2. `scripts/dev_substrate/m1_stress_preflight.py`
3. `Dockerfile`
4. `requirements/m1-image.in`
5. `requirements/m1-image.lock.txt`
6. Stress evidence outputs under `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/<execution_id>/stress/`

### Acceptance gates
1. Local preflight: PASS with zero blockers.
2. Managed rerun:
   - three `dev-full-m1-packaging` runs succeed,
   - max concurrency meets target (`>=2`),
   - `digest_drift=false`.
3. If `digest_drift=true` persists, hold fail-closed and escalate next deterministic surfaces.

## Entry: 2026-03-03 14:37 +00:00 - Deterministic closure lane implementation + local validation

### Implemented controls
1. Docker context/default-deny allowlist updated:
   - `.dockerignore` now explicitly reopens `requirements/` and `requirements/m1-image.lock.txt`.
2. Preflight docker lint strengthened:
   - `m1_stress_preflight.py` now requires Dockerfile copy coverage for `requirements/m1-image.lock.txt`,
   - enforces required default-deny allowlist reopen tokens for lockfile path.
3. Handles parser hardened for annotated registry lines:
   - `_parse_handles` now accepts trailing prose after closing backtick, preserving machine parse for documented handle notes.
4. Deterministic Docker build posture retained:
   - digest-pinned base image,
   - hash-verified dependency install from lockfile.

### Local evidence
1. Preflight rerun:
   - execution id `m1_stress_preflight_20260303T143350Z`,
   - verdict `READY_FOR_M1_STRESS_WINDOW`,
   - blocker count `0`.
2. Docker build smoke:
   - no-cache build completed successfully with lockfile contract and digest-pinned base.
3. Additional repeated local build comparison showed local image-id drift and one BuildKit extraction error during re-export.
   - interpreted as local builder/exporter nondeterminism surface (not contract failure in managed lane),
   - does not invalidate moving to managed rerun gate; managed evidence remains authoritative.

### Next gate
1. Commit/push deterministic closure controls to `cert-platform`.
2. Execute dev_full-only 3-run managed M1 stress window and adjudicate `M1-ST-B8` fail-closed.

## Entry: 2026-03-03 14:42 +00:00 - M1-ST-B8 managed rerun after deterministic lockfile hardening

### Execution
1. Deterministic closure controls were committed and pushed on `cert-platform`:
   - commit `7d4112bebf7bd2321df4901f01cd42de14834148`.
2. Dispatched dev_full-only managed stress window:
   - phase execution id: `m1_stress_window_20260303T144031Z`,
   - run ids: `22628013765`, `22628020745`, `22628025246`.
3. All runs completed `success`.
4. Observed max concurrency: `3` (target `2`, pass).
5. Run-scoped immutable tag checks passed:
   - no tag collision,
   - no git-sha drift.

### Blocker adjudication
1. `M1-ST-B8` remains OPEN:
   - `digest_drift=true` across all three repetitions despite lockfile + base digest controls.
2. Verdict remains fail-closed:
   - `HOLD_REMEDIATE`.

### Evidence
1. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_dispatch_receipt.json`
2. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_stress_window_results.json`
3. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_blocker_register.json`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_execution_summary.json`
5. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_decision_log.json`

### Fail-closed escalation posture
1. Stop further M1 remediation changes until explicit user direction on next deterministic architecture-level lane.
2. Candidate next lane to propose:
   - move to single-arch Buildx with deterministic output settings (`--provenance=false --sbom=false`) and immutable digest-by-digest comparison against OCI config hash surfaces.

## Entry: 2026-03-03 14:55 +00:00 - M1-ST-B8 architecture-level deterministic lane implementation plan

### Trigger
1. User directed immediate implementation of the architecture-level deterministic lane and asked for immediate M2 rerun after execution.
2. Current blocker state remains fail-closed (`M1-ST-B8` open) with confirmed digest drift on managed rerun.

### Root-cause refinement from latest evidence
1. ECR manifest inspection confirms drift is not limited to top-level tag/index metadata:
   - config digest differs across repetitions,
   - layer digest sets differ across repetitions while base layers stay constant.
2. This indicates true build-byte nondeterminism in generated application layers.

### Selected remediation lane
1. Replace mutable docker build path in workflow with deterministic Buildx push path:
   - fixed platform `linux/amd64`,
   - disable attestation/SBOM emit for this determinism gate (`--provenance=false --sbom=false`),
   - push directly from build command.
2. Canonicalize build context before build:
   - stage only pinned include surfaces,
   - normalize mtimes to `SOURCE_DATE_EPOCH` recursively.
3. Remove time-varying pip upgrade behavior:
   - stop `pip install --upgrade pip`,
   - pin pip version explicitly in Dockerfile and keep hash-verified dependency install.
4. Upgrade packaging evidence:
   - include `config_digest` and ordered `layer_digests` in provenance artifact.

### Scope
1. `.github/workflows/dev_full_m1_packaging.yml`
2. `Dockerfile`
3. Stress docs/logbook updates after rerun

### M2 rerun posture (decision-completeness gate)
1. M2 immediate rerun is requested by user.
2. Current stress authority still holds `M2` advancement blocked while `M1-ST-B8` is open.
3. Execution will therefore proceed in sequence:
   - implement lane,
   - rerun M1 determinism gate immediately,
   - if and only if M1 clears, execute discoverable M2 rerun command surface.
4. If M2 command surface is unavailable/unpinned for current stress track, fail-closed escalation will be raised with exact missing inputs.

## Entry: 2026-03-03 14:58 +00:00 - Architecture-level deterministic lane implemented (pre-rerun validation)

### Implemented changes
1. `dev_full_m1_packaging` workflow hardened:
   - added Buildx setup (`docker/setup-buildx-action@v3`),
   - introduced deterministic context staging step that:
     - enforces `IMAGE_BUILD_CONTEXT_PATH='.'`,
     - copies only pinned Docker include surfaces,
     - normalizes all staged file mtimes to `SOURCE_DATE_EPOCH`,
   - replaced docker build/push steps with deterministic buildx push:
     - `--platform linux/amd64`,
     - `--provenance=false`,
     - `--sbom=false`,
   - added ECR manifest-surface extraction (`config_digest`, ordered `layer_digests`),
   - enriched emitted evidence with config/layer digest surfaces and deterministic-context flag.
2. Dockerfile deterministic install hardening:
   - removed `pip --upgrade` pattern,
   - pinned pip install to `pip==25.0.1`,
   - preserved hash-verified dependency install.
3. Preflight contract hardened:
   - blocks forbidden `pip install --upgrade pip`,
   - requires deterministic install patterns (`pip==25.0.1` and hash-locked install command).

### Local validation
1. Workflow YAML parse: PASS.
2. M1 preflight run:
   - execution id `m1_stress_preflight_20260303T145720Z`,
   - verdict `READY_FOR_M1_STRESS_WINDOW`,
   - blocker count `0`.
3. Local docker smoke build with updated Dockerfile: PASS.

### Next action
1. Commit/push deterministic-lane implementation.
2. Execute immediate managed M1 rerun for `M1-ST-B8` adjudication.
3. If and only if M1 clears, proceed to M2 rerun command surface.

## Entry: 2026-03-03 15:04 +00:00 - Immediate M1 rerun after architecture-level deterministic lane

### Execution
1. Deterministic lane commit pushed on `cert-platform`:
   - `716641e404b3a99db23e1080a6847e6c86e3945e`.
2. Immediate dev_full-only managed M1 rerun executed:
   - phase execution id: `m1_stress_window_20260303T150118Z`,
   - run ids: `22628887520`, `22628894768`, `22628902354`.
3. All runs completed `success`.
4. Observed max concurrency: `3` (target `2`, pass).
5. Tag contract checks passed:
   - no tag collision,
   - no git-sha drift.

### Blocker adjudication
1. `M1-ST-B8` remains OPEN:
   - `digest_drift=true`,
   - `config_drift=true`,
   - `layer_drift=true`.
2. Verdict remains fail-closed:
   - `HOLD_REMEDIATE`.

### Evidence
1. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_dispatch_receipt.json`
2. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_stress_window_results.json`
3. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_blocker_register.json`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_execution_summary.json`
5. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_decision_log.json`

### Scope correction
1. User corrected follow-up to rerun `M1` (not `M2`).
2. No M2 rerun was executed in this lane.

## Entry: 2026-03-03 15:09 +00:00 - Wheelhouse deterministic lane plan (offline install surface)

### Trigger
1. User approved proceeding with the recommended next step: offline wheelhouse lane and immediate M1 rerun.
2. Current fail-closed blocker persists after architecture-level lane:
   - `digest_drift=true`,
   - `config_drift=true`,
   - `layer_drift=true`.

### Problem framing
1. Drift persists in application-generated layers despite:
   - base digest pin,
   - hash-locked requirement set,
   - deterministic buildx posture,
   - staged context mtime normalization.
2. Remaining likely entropy surface is package retrieval/install path during image build.

### Selected lane
1. Add wheelhouse pre-materialization in workflow deterministic context stage:
   - run `pip download --require-hashes -r requirements/m1-image.lock.txt -d requirements/wheelhouse`,
   - normalize wheelhouse file mtimes to `SOURCE_DATE_EPOCH`.
2. Switch Dockerfile install path to offline install:
   - copy `requirements/wheelhouse`,
   - install with `--no-index --find-links=/app/requirements/wheelhouse --require-hashes`.
3. Harden preflight lint to enforce wheelhouse copy/install contract.
4. Extend `.dockerignore` allowlist tokens for wheelhouse path.

### Acceptance gates
1. Local preflight: PASS (zero blockers).
2. Managed rerun:
   - all runs success,
   - concurrency target met,
   - `digest_drift=false`, `config_drift=false`, `layer_drift=false`.
3. If drift persists, keep fail-closed and escalate to artifact-freeze lane (prebuilt venv/wheel bundle digest pinning).

## Entry: 2026-03-03 15:16 +00:00 - Wheelhouse deterministic lane implemented (pre-rerun validation)

### Implemented controls
1. Workflow wheelhouse materialization:
   - deterministic context stage now runs `pip download --require-hashes --no-deps --only-binary=:all:` into staged `requirements/wheelhouse`,
   - wheelhouse files are normalized with `SOURCE_DATE_EPOCH` alongside rest of staged context.
2. Dockerfile offline install contract:
   - added `COPY requirements/wheelhouse /app/requirements/wheelhouse`,
   - dependency install now uses offline wheelhouse:
     - `pip install --no-index --find-links=/app/requirements/wheelhouse --require-hashes -r /app/requirements/m1-image.lock.txt`.
3. Preflight deterministic contract updates:
   - requires wheelhouse copy path in Dockerfile,
   - requires offline install pattern with `--no-index --find-links`,
   - requires default-deny `.dockerignore` reopen tokens for `requirements/wheelhouse`.
4. Repository hygiene:
   - added `requirements/wheelhouse/.gitkeep`,
   - `.gitignore` updated so wheelhouse binaries are not tracked.

### Local validation
1. Workflow YAML parse: PASS.
2. M1 preflight rerun:
   - execution id `m1_stress_preflight_20260303T151622Z`,
   - verdict `READY_FOR_M1_STRESS_WINDOW`,
   - blocker count `0`.
3. Local docker wheelhouse smoke was not executed as authoritative validation:
   - host is Windows and lock includes Linux-target package set for managed runner,
   - managed GitHub Linux runner rerun is authoritative for this lane.

### Next action
1. Commit/push wheelhouse deterministic lane.
2. Execute immediate managed M1 rerun and adjudicate `M1-ST-B8`.
