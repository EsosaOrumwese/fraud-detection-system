# Dev Full Platform Stress-Test Program
_Track: dev_substrate/dev_full_
_As of 2026-03-03_
_Status: ACTIVE PROGRAM AUTHORITY_

## 0) Objective
Harden the platform for realistic production throughput and stability by stress testing:
1. components first,
2. planes second,
3. full platform last,
while remediating bottlenecks phase-by-phase (`M0..M15`) before certification attempts.

Certification is treated as a verification event after stress hardening, not as a discovery workflow.

## 1) Why This Program Exists
Root problem:
1. certification was attempted before stress hardening, causing late-stage failures and high remediation cost.

Program correction:
1. use existing build decisions as the test target,
2. detect likely bottlenecks before expensive long runs,
3. adapt design/runtime decisions when evidence shows bottlenecks,
4. rerun only after targeted remediation.

## 2) Core Rules (Binding)
1. Realistic production standards only. No checkbox testing.
2. Fail-closed progression: no phase advancement with unresolved blockers.
3. Decision-first testing: inspect phase build decisions before launching load.
4. Cost-first discipline: do not run tests that are already predicted to fail for known bottlenecks.
5. Determinism and truth-boundary laws are non-negotiable.

## 3) Clarification on Local Development vs No Local Runtime
Pinned interpretation:
1. `No local compute` means runtime/cert claims must not depend on laptop runtime resources.
2. Local engineering work is required and encouraged:
   - design,
   - code changes,
   - local profiling/unit/integration checks.
3. Workflows are for controlled managed execution, regression gates, and evidence capture, not primary ad-hoc debugging.

## 4) M-Phase Stress Overview (Before Deep Plans)
This is the program-level overview of what each `M*` phase stress effort is expected to achieve before deep `platform.M*.stress_test.md` files are elaborated.

| Stress Phase | Build Scope Anchor | What We Aim to Achieve | Exit Signal | Status |
| --- | --- | --- | --- | --- |
| M0 | Mobilization + authority lock | Validate test authority, handles, and stress evidence surfaces before any load | All prerequisite stress handles and evidence sinks are green | DONE |
| M1 | Packaging readiness | Stress packaging/provenance paths and pin a production-safe acceptance boundary for immutable artifact promotion | Artifact-freeze + immutable digest promotion contract accepted; managed toolchain-path fresh-rebuild nondeterminism recorded as known boundary | DONE |
| M2 | Substrate readiness | Stress core substrate primitives (network/store/bus/runtime) for baseline capacity and failure behavior | Substrate can sustain target baseline load without integrity drift | DONE |
| M3 | Run pinning + orchestrator readiness | Stress run-control/orchestrator behavior under concurrent run activation and retries | Run pinning remains deterministic; no cross-run mixing | DONE |
| M4 | Spine runtime-lane readiness | Stress each spine lane bootstrap path for startup-time, readiness, and dependency bottlenecks | Lane startup and steady-state readiness meet target budgets | ACTIVE |
| M5 | Oracle readiness + ingest preflight (`P3-P4`) | Stress oracle-to-ingress preflight flow for input correctness and ingest warm-path limits | Preflight pass is stable; no upstream-induced ingress stalls | ACTIVE |
| M6 | Control + Ingress (`P5-P7`) | Stress SR/WSP/IG/bus at component -> plane -> integrated levels for throughput and correctness | Target ingress throughput + latency met with replay-safe semantics | NOT_STARTED |
| M7 | RTDL + Case/Labels (`P8-P10`) | Stress decision loop + case/label pathways for sustained throughput and bounded lag | Decision/action/case/label lanes keep pace with ingress without silent degrade | NOT_STARTED |
| M8 | Spine Obs/Gov (`P11`) | Stress observability/governance paths so evidence remains complete under high event rates | Evidence completeness + low-overhead telemetry proven | NOT_STARTED |
| M9 | Learning input readiness (`P12`) | Stress replay-basis/as-of/maturity extraction paths for correctness under realistic volume | Learning input lanes produce deterministic, timely, leak-safe outputs | NOT_STARTED |
| M10 | OFS dataset closure (`P13`) | Stress offline feature dataset generation for throughput, stability, and cost posture | Dataset builds finish within budget with reproducible manifests | NOT_STARTED |
| M11 | MF train/eval closure (`P14`) | Stress model train/eval orchestration for queueing, runtime, and artifact integrity | Train/eval flow stable with deterministic evidence and bounded runtime | NOT_STARTED |
| M12 | MPR promotion/rollback (`P15`) | Stress model promotion, rollback, and resolution lanes under repeated activation pressure | Promotion/rollback deterministic and fail-closed under stress | NOT_STARTED |
| M13 | Full-platform verdict + teardown (`P16-P17`) | Stress full-platform execution windows plus teardown and idle-safe guarantees | Full-lane run + teardown remains stable, complete, and cost-safe | NOT_STARTED |
| M14 | Runtime-placement repin materialization | Stress any placement repins to validate they improve or preserve performance and reliability | Repinned runtime lanes meet or exceed prior stress baselines | NOT_STARTED |
| M15 | Data semantics realization | Stress real-data semantics in learning/evolution lanes at production-like volume and quality | Semantic realism + runtime budget + no-leakage gates all green | NOT_STARTED |

Subphase routing note:
1. Deep stress files may be split (for example `M5.P3`, `M6.P5`, `M7.P8`) when a phase has distinct lanes with different bottleneck signatures.

## 5) Stress Methodology (Per Phase)

### 5.1 Stage A - Decision/Bottleneck Pre-Read
Before stressing a phase:
1. read the phase build authority (`platform.M*.build_plan.md` and relevant `impl_actual` entries),
2. map runtime surfaces for that phase (compute, stores, messaging, IAM, network),
3. identify likely bottlenecks and failure points,
4. classify each finding:
   - `PREVENT`: must fix before running,
   - `OBSERVE`: acceptable to test directly with instrumentation,
   - `ACCEPT`: low risk under current target.

No stress run starts if unresolved `PREVENT` items exist.

### 5.2 Stage B - Component Stress
1. stress each component in the phase independently.
2. isolate local component limits before cross-component coupling noise.
3. capture component-specific saturation curves and error boundaries.

### 5.3 Stage C - Plane Stress
1. stress integrated plane flow (for example: Control+Ingress or RTDL).
2. validate count continuity and latency budgets across interfaces.
3. confirm no hidden queue growth or silent degrade.

### 5.4 Stage D - Full Platform Stress (Scoped to Phase Envelope)
1. execute bounded full-lane workload with phase scope.
2. run soak + burst windows.
3. run bounded failure injection.

### 5.5 Stage E - Remediate and Re-Validate
1. rank bottlenecks by impact and remediation cost.
2. apply targeted fixes.
3. rerun same test profile for direct before/after proof.

## 6) Evidence Contract (Required for Every Stress Step)
1. target profile and workload definition.
2. runtime and config digests.
3. throughput/latency results (`p50`, `p95`, `p99`, error rates).
4. queue/lag/posture snapshots.
5. blocker register (`open`, `resolved`, `waived` with explicit user approval only).
6. cost window snapshot and cost-to-outcome receipt.
7. control artifacts (`execution_summary`, `decision_log`, `blocker_register`) for each active phase.

No stress step is closed without artifact publication and readback verification.

### 6.1) Stress Control Artifact Path Contract (Pinned)
1. `STRESS_RUN_CONTROL_PREFIX_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/"`
2. `STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/{phase_id}_blocker_register.json"`
3. `STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/{phase_id}_execution_summary.json"`
4. `STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/{phase_id}_decision_log.json"`

## 7) Program Structure (Mirrors Build Phase Ladder)
Stress program follows the same canonical ladder:
1. `M0`
2. `M1`
3. `M2`
4. `M3`
5. `M4`
6. `M5`
7. `M5.P3`
8. `M5.P4`
9. `M6`
10. `M6.P5`
11. `M6.P6`
12. `M6.P7`
13. `M7`
14. `M7.P8`
15. `M7.P9`
16. `M7.P10`
17. `M8`
18. `M9`
19. `M10`
20. `M11`
21. `M12`
22. `M13`
23. `M14`
24. `M15`

Per-phase stress files are created only when each phase is activated.

## 8) Phase Activation and Naming Convention
Program control file:
1. `stress_test/platform.stress_test.md` (this file).

Per-phase files (progressive creation):
1. `stress_test/platform.M0.stress_test.md`
2. `stress_test/platform.M1.stress_test.md`
3. ...
4. `stress_test/platform.M15.stress_test.md`

Dedicated phase-file creation rule (deterministic):
1. Keep phase inline in `platform.stress_test.md` when all are true:
   - single-lane or low-coupling stress scope,
   - low expected runtime and low spend,
   - no expected architecture/placement repin,
   - simple blocker taxonomy.
2. Create `platform.M*.stress_test.md` when any are true:
   - multi-lane coupled stress path,
   - custom load profile + failure matrix required,
   - moderate/high expected runtime or spend,
   - likely build-decision bottleneck requiring repin,
   - non-trivial blocker and rerun topology.
3. Default focus guidance:
   - `M0` is inline by default.
   - `M1` and `M3` are usually inline unless complexity expands.
   - heavy phases are expected to get dedicated files (`M2`, `M4`, `M5+subphases`, `M6`, `M7+subphases`, `M8`, `M9..M15`).
   - current cycle note: `M3` complexity expanded (identity/digest/orchestrator/lock coupled lanes), so it is now on a dedicated file.
4. Re-evaluation rule:
   - if an inline phase expands beyond rule-1 boundaries during execution, create a dedicated phase file before further stress work.

Each phase file must contain:
1. scope and dependency map,
2. pre-read bottleneck analysis,
3. component stress plan,
4. plane stress plan,
5. phase-full run plan,
6. remediation loop and rerun policy,
7. DoD and blocker taxonomy,
8. budget envelope and teardown posture.

## 9) Runtime and Cost Gates (Global)
Global runtime gates:
1. no phase run is accepted with unexplained stalls/hours-long single-state runtime unless explicitly user-waived.
2. no unresolved count mismatch across critical producer/consumer boundaries.
3. no persistent lag growth at steady-state target load.

Global cost gates:
1. no unattributed spend.
2. non-active lanes remain stopped.
3. each stress window has deterministic teardown.

## 10) Adaptation Policy (When to Cut/Increase/Change Direction)
For any phase:
1. if measured bottleneck is algorithmic/path-bound, optimize code and data path first.
2. if bottleneck remains after path optimization, resize runtime resources.
3. if both fail, repin architecture/placement decision for that lane.
4. if a test profile is clearly invalid for current known constraints, stop early and remediate first instead of burning cost.

## 11) Relationship to Existing Build Authorities
1. Build authorities remain the design and infrastructure intent source.
2. Stress authorities validate whether those decisions meet realistic production standards.
3. When stress evidence contradicts a build decision:
   - open blocker,
   - propose decision change,
   - update authority before proceeding.

## 12) Program Status
1. Program bootstrapped.
2. Current phase state: `M5` (`ACTIVE` execution lane with dedicated parent + split subphase files).
3. Dedicated phase files:
   - `stress_test/platform.M2.stress_test.md` (`DONE`),
   - `stress_test/platform.M3.stress_test.md` (`DONE`),
   - `stress_test/platform.M4.stress_test.md` (`DONE`),
   - `stress_test/platform.M5.stress_test.md` (`ACTIVE`),
   - `stress_test/platform.M5.P3.stress_test.md` (`DONE`),
   - `stress_test/platform.M5.P4.stress_test.md` (`ACTIVE`).
4. Next step: execute `M5P4-ST-S5` P4 rollup/deterministic verdict (`M5P4-ST-S4` passed with `next_gate=M5P4_ST_S5_READY`, `open_blockers=0`).

## 13) Closed Phase - M0 (Inline)
Status:
1. `DONE`

M0 stress objective:
1. ensure stress program governance is execution-ready before any runtime load is attempted.

M0 stress scope:
1. authority and precedence readback for stress program.
2. stress handle and evidence-surface readiness checks.
3. phase activation control and blocker taxonomy lock.

M0 stress handle packet (pinned):
1. `STRESS_PROGRAM_ID = "dev_full_stress_v0"`
2. `STRESS_PROGRAM_MODE = "pre_cert_hardening"`
3. `STRESS_ACTIVE_PHASE = "M0"`
4. `STRESS_LOCAL_ENGINEERING_ALLOWED = true`
5. `STRESS_LOCAL_RUNTIME_ALLOWED = false`
6. `STRESS_AWS_REGION = "eu-west-2"`
7. `STRESS_EVIDENCE_BUCKET = "fraud-platform-dev-full-evidence"`
8. `M0_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m0_blocker_register.json"`
9. `M0_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m0_execution_summary.json"`
10. `M0_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m0_decision_log.json"`
11. `M0_STRESS_REQUIRED_ARTIFACTS = "m0_blocker_register.json,m0_execution_summary.json,m0_decision_log.json"`
12. `M0_STRESS_FAIL_ON_PLACEHOLDER_HANDLE = true`
13. `M0_STRESS_MAX_RUNTIME_MINUTES = 60`
14. `M0_STRESS_MAX_SPEND_USD = 0`

Stage A pre-read inputs used:
1. `platform.M0.build_plan.md`
2. `platform.build_plan.md`
3. `dev_full_handles.registry.v0.md`

Stage A findings classification:

| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M0-ST-F1` | `PREVENT` | Stress program does not yet pin a dedicated stress-handle packet (targets/profile IDs/window settings) independent of certification knobs. | Define and pin `M0` stress-handle packet before `M1` stress activation. |
| `M0-ST-F2` | `PREVENT` | Stress evidence contract exists, but M0 has no explicit stress blocker register artifact path yet. | Pin M0 stress blocker register artifact contract in M0 closure step. |
| `M0-ST-F3` | `OBSERVE` | Handles registry still contains unresolved `TO_PIN` items mapped to later runtime phases (`M2+`). | Track as forward dependency risk; no M0 runtime action required. |
| `M0-ST-F4` | `ACCEPT` | M0 build phase is docs/control-only with no runtime mutation; this aligns with stress program startup posture. | Continue M0 inline execution and close governance prerequisites. |

M0 blockers (status):
1. `M0-ST-B1`: CLOSED - stress-handle packet pinned.
2. `M0-ST-B2`: CLOSED - blocker-register artifact contract pinned.

M0 DoD (stress):
- [x] Stage A pre-read completed and classified (`PREVENT`/`OBSERVE`/`ACCEPT`).
- [x] Stress-handle packet pinned for downstream phase activation.
- [x] M0 stress blocker-register artifact contract pinned.
- [x] M0 blocker set closed (`M0-ST-B1`, `M0-ST-B2`).
- [x] M0 closure note written in stress implementation map and logbook.

M0 immediate actions:
1. Validate M0 closure readback against pinned artifact contract.
2. If no new blocker appears, mark `M0 DONE` and move to `M1` decision pre-read.

M0 closure verdict:
1. `DONE` and handed off to `M1`.

## 14) Closed Phase - M1 (Inline)
Status:
1. `DONE` (policy-closed under approved immutable artifact-promotion acceptance)

M1 stress objective:
1. validate packaging/provenance decisions under realistic production stress posture and establish a production-safe immutable artifact-promotion baseline before runtime phases consume artifacts.

M1 stress scope:
1. packaging decision/bottleneck pre-read against M1 build authority.
2. local preflight contract for fast engineering loops before managed workflow dispatch.
3. packaging stress control-handle packet and artifact contract pinning.

M1 stress handle packet (pinned):
1. `STRESS_ACTIVE_PHASE = "M1"` (active-phase override).
2. `M1_STRESS_PROFILE_ID = "packaging_repro_profile_v0"`.
3. `M1_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m1_blocker_register.json"`.
4. `M1_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m1_execution_summary.json"`.
5. `M1_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m1_decision_log.json"`.
6. `M1_STRESS_REQUIRED_ARTIFACTS = "m1_blocker_register.json,m1_execution_summary.json,m1_decision_log.json,m1_preflight_checks.json"`.
7. `M1_STRESS_FAIL_ON_PROVENANCE_DRIFT = true`.
8. `M1_STRESS_FAIL_ON_MUTABLE_TAG_EVIDENCE = true`.
9. `M1_STRESS_MAX_RUNTIME_MINUTES = 120`.
10. `M1_STRESS_MAX_SPEND_USD = 10`.
11. `M1_STRESS_BUILD_REPETITIONS = 3`.
12. `M1_STRESS_BUILD_CONCURRENCY_TARGET = 2`.
13. `M1_STRESS_IMAGE_TAG_IMMUTABLE_PATTERN = "git-{git_sha}-run-{ci_run_id}"`.
14. `M1_STRESS_GIT_SHA_CANONICAL_TAG_PATTERN = "git-{git_sha}"` (trace marker only).

M1 local preflight contract (pinned):
1. `M1_LOCAL_PREFLIGHT_REQUIRED = true`.
2. `M1_LOCAL_PREFLIGHT_MODE = "local_static_and_entrypoint_smoke_before_managed_runs"`.
3. `M1_LOCAL_PREFLIGHT_COMMAND_SET = "docker_context_lint,entrypoint_help_matrix,provenance_contract_lint"`.
4. `M1_LOCAL_PREFLIGHT_ARTIFACT = "m1_preflight_checks.json"`.

Stage A pre-read inputs used:
1. `platform.M1.build_plan.md`
2. `platform.build_plan.md`
3. `dev_full_handles.registry.v0.md`

Stage A findings classification:

| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M1-ST-F1` | `PREVENT` | M1 stress-handle packet and M1-specific control-artifact paths were not pinned. | Pin M1 stress-handle packet before Stage-B execution. |
| `M1-ST-F2` | `PREVENT` | Packaging verification was historically managed-workflow heavy; local preflight contract for fast iteration was not pinned. | Pin mandatory local preflight contract for M1. |
| `M1-ST-F3` | `OBSERVE` | `IMAGE_BUILD_CONTEXT_PATH = "."` can become packaging bottleneck as repo grows even with `.dockerignore` controls. | Measure context size and transfer overhead during Stage-B runs. |
| `M1-ST-F4` | `OBSERVE` | Single-image strategy can increase rebuild blast radius and build duration under frequent changes. | Track build-time slope across 3-run repetition and open repin gate if slope exceeds budget. |
| `M1-ST-F5` | `ACCEPT` | Immutable digest/provenance/security contracts from M1 deep plan are explicit and fail-closed. | Reuse as baseline and verify under stress repetition. |

M1 blockers (status):
1. `M1-ST-B1`: CLOSED - M1 stress-handle packet pinned.
2. `M1-ST-B2`: CLOSED - local preflight contract pinned.
3. `M1-ST-B3`: CLOSED - dockerignore default-deny lint false-fail remediated in local preflight tooling.
4. `M1-ST-B6`: CLOSED - initial managed-window run failures from optional S3 direct-upload branch remediated by artifact-pack-only rerun posture.
5. `M1-ST-B8`: POLICY_CLOSED - fresh rebuild provenance drift under concurrent managed repetitions is retained as known managed toolchain-path nondeterminism boundary; downstream runtime phases consume only frozen immutable artifact digests.

M1 diagnostic rationale (pinned understanding):
1. During active remediation windows, `M1-ST-B8` was held fail-closed to preserve trust in immutable packaging provenance.
2. Under the approved acceptance policy, `M1-ST-B8` is now policy-closed with immutable artifact-promotion boundary controls.
3. Observed drift remains after lockfile pinning, base digest pinning, deterministic buildx posture, staged-context timestamp normalization, and offline wheelhouse install lane.
4. Current technical interpretation is that dominant entropy is in the managed build system/toolchain execution path, not in package-version selection from the current pinned dependency stack.
5. This is recorded as system understanding (diagnosis maturity), not as a project failure.

M1 success definition (approved policy):
1. Authoritative success posture for M1 is deterministic immutable artifact promotion, not repeated fresh-rebuild byte identity.
2. Freeze one authoritative Linux build artifact/digest per git-sha.
3. Verify packaging/provenance contract on the frozen artifact once.
4. Promote downstream phases by immutable digest only.
5. Require runtime stress/throughput validation to execute against promoted immutable artifact references.
6. Track fresh-rebuild drift as managed toolchain-path diagnostic evidence; it is not a phase blocker unless it affects the promoted immutable artifact contract itself.

M1 DoD (stress):
- [x] Stage A pre-read completed and classified (`PREVENT`/`OBSERVE`/`ACCEPT`).
- [x] M1 stress-handle packet pinned.
- [x] M1 local preflight contract pinned.
- [x] M1 blocker set closed (`M1-ST-B1`, `M1-ST-B2`).
- [x] Stage-B packaging component stress executed with required artifacts.
- [x] M1 stress closure verdict published (`DONE`) with approved immutable artifact-promotion acceptance policy.

M1 immediate actions:
1. Carry forward M1 packaging baseline as immutable artifact-promotion contract for M2+ stress phases.
2. Start M2 Stage-A pre-read and identify substrate-lane `PREVENT/OBSERVE/ACCEPT` findings before managed stress execution.
3. Keep recording fresh-rebuild drift as diagnostic telemetry; reopen blocker only if promoted artifact contract integrity is impacted.

M1 Stage-B execution progress:
1. Historical chronology note: entries below preserve original fail-closed wording from execution time and do not override current M1 closure status.
2. Local preflight run `m1_stress_preflight_20260303T060333Z` returned `HOLD_REMEDIATE`:
   - blocker `M1-ST-B3` was raised by dockerignore lint logic that required explicit deny tokens even under default-deny posture.
3. Local preflight lint remediation applied:
   - `scripts/dev_substrate/m1_stress_preflight.py` now treats default-deny `.dockerignore` posture (`*` or `**`) as compliant for deny-pattern enforcement.
4. Local preflight rerun `m1_stress_preflight_20260303T060442Z` returned `READY_FOR_M1_STRESS_WINDOW` with zero blockers.
5. Published local stress artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060442Z/stress/m1_preflight_checks.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060442Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060442Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_preflight_20260303T060442Z/stress/m1_decision_log.json`
6. Managed stress window attempt-1 `m1_stress_window_20260303T061142Z`:
   - run set included `22610789727`, `22610791866`, `22610794341`,
   - two `dev-full-m1-packaging` runs failed at optional direct S3 evidence upload (`HeadBucket 403`),
   - fail-closed verdict `HOLD_REMEDIATE`.
7. Managed stress window attempt-2 `m1_stress_window_20260303T061619Z` (artifact-pack-only rerun posture):
   - run set `22610905355`, `22610907538`, `22610910038` all `success`,
   - observed max concurrency `3` (target `2` met),
   - provenance drift detected: same immutable tag `git-e8b010fc47fdae36f4425cba0701459df077b2e0` mapped to three digests,
   - blocker `M1-ST-B8` opened and phase remains fail-closed `HOLD_REMEDIATE`.
8. Managed-window artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_stress_window_results.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T061619Z/stress/m1_decision_log.json`
9. `M1-ST-B8` remediation attempt applied and rerun in dev_full-only mode:
   - workflow contract repin committed (`b4d819270cd84b27fc3dc2028db3e1b2d49b6a8f`) with run-scoped immutable tag pattern and stress concurrency suffix input,
   - dev_full-only run set `22627099194`, `22627105810`, `22627109900` all `success`,
   - observed max concurrency `3` (target `2` met),
   - run-scoped tag pattern passed (`tag_collision=false`),
   - fail-closed blocker persists: `digest_drift=true` across repetitions (`M1-ST-B8` remains open).
10. Dev_full-only rerun artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_stress_window_results.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T141816Z/stress/m1_decision_log.json`
11. Deterministic lockfile hardening rerun `m1_stress_window_20260303T144031Z`:
   - branch head `7d4112bebf7bd2321df4901f01cd42de14834148` (includes digest-pinned base + hash-locked dependency install),
   - dev_full-only run set `22628013765`, `22628020745`, `22628025246` all `success`,
   - observed max concurrency `3` (target `2` met),
   - run-scoped immutable tag checks passed (no tag collision, no git-sha drift),
   - fail-closed blocker persists: `digest_drift=true` (`M1-ST-B8` remains open).
12. Deterministic lockfile hardening rerun artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_dispatch_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_stress_window_results.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T144031Z/stress/m1_decision_log.json`
13. Architecture-level deterministic lane rerun `m1_stress_window_20260303T150118Z`:
   - branch head `716641e404b3a99db23e1080a6847e6c86e3945e` (deterministic buildx path + staged context mtime normalization + manifest-surface evidence),
   - dev_full-only run set `22628887520`, `22628894768`, `22628902354` all `success`,
   - observed max concurrency `3` (target `2` met),
   - run-scoped tag checks passed (no tag collision, no git-sha drift),
   - fail-closed blocker persists with stronger signal:
     - `digest_drift=true`,
     - `config_drift=true`,
     - `layer_drift=true`.
14. Architecture-level deterministic lane rerun artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_dispatch_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_stress_window_results.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T150118Z/stress/m1_decision_log.json`
15. Wheelhouse deterministic lane rerun `m1_stress_window_20260303T151901Z`:
   - branch head `87ff4c0fd8c96b332d021b2a627aa1fe4fc20511` (staged offline wheelhouse + offline install path),
   - dev_full-only run set `22629629443`, `22629636090`, `22629640152` all `success`,
   - observed max concurrency `3` (target `2` met),
   - run-scoped tag checks passed (no tag collision, no git-sha drift),
   - fail-closed blocker persists with unchanged signal:
     - `digest_drift=true`,
     - `config_drift=true`,
     - `layer_drift=true`.
16. Wheelhouse deterministic lane rerun artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T151901Z/stress/m1_dispatch_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T151901Z/stress/m1_stress_window_results.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T151901Z/stress/m1_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T151901Z/stress/m1_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m1_stress_window_20260303T151901Z/stress/m1_decision_log.json`

## 15) Closed Phase - M2 (Dedicated)
Status:
1. `DONE`

Authority routing:
1. `stress_test/platform.M2.stress_test.md` remains the authoritative execution/planning record for M2.
2. Inline M2 detail is intentionally not expanded in this control file to preserve dedicated-file routing discipline.

## 16) Closed Phase - M4 (Dedicated)
Status:
1. `DONE`

Authority routing:
1. `stress_test/platform.M4.stress_test.md` is the closure authority for M4.
2. Latest M4 execution state is `M4-ST-S5` pass (`recommendation=GO`, `next_gate=M5_READY`); M4 handoff is complete.

## 17) Active Phase - M5 (Dedicated)
Status:
1. `ACTIVE` (parent S0, P3 closure, and P4 S3 topic readiness closed green; P4 S4 pending)

Authority routing:
1. Parent orchestration authority: `stress_test/platform.M5.stress_test.md`.
2. Split subphase authorities:
   - `stress_test/platform.M5.P3.stress_test.md` (P3 ORACLE_READY),
   - `stress_test/platform.M5.P4.stress_test.md` (P4 INGEST_READY).
3. Latest M5 parent execution state is `M5-ST-S0` pass (`next_gate=M5_ST_S1_READY`, `open_blockers=0`).
4. Latest M5.P3 execution state is `M5P3-ST-FAST` pass (`next_gate=ADVANCE_TO_P4`, `open_blockers=0`, `waived_observation_count=2`).
5. Latest M5.P4 execution state is `M5P4-ST-S4` pass (`next_gate=M5P4_ST_S5_READY`, `open_blockers=0`).
6. M5 execution is fail-closed in this order:
   - parent `M5-ST-S0`,
   - `M5.P3`,
   - `M5.P4`,
   - parent closure rollup with `M6_READY` recommendation.
