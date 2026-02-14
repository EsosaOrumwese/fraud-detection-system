# Dev Substrate Deep Plan - M5 (P3 Oracle Lane)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M5._
_Last updated: 2026-02-14_

## 0) Purpose
M5 establishes P3 oracle readiness on managed substrate by producing deterministic `stream_view` artifacts for required output IDs and validating them with fail-closed checker evidence before P4-P7 activation.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P3 section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M4.build_plan.md`
2. `runs/dev_substrate/m4/20260214T170953Z/m5_handoff_pack.json`
3. `runs/dev_substrate/m4/20260214T170155Z/m4_i_verdict_snapshot.json`
4. `runs/dev_substrate/m3/20260213T221631Z/run.json`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M5
In scope:
1. P3 oracle input presence closure:
   - verify run-scoped S3 input prefixes exist or execute managed seed/sync.
2. P3 stream-sort execution:
   - one-shot managed compute jobs only,
   - deterministic per-output sorting,
   - stream_view shard + manifest + receipt publication.
3. P3 checker execution:
   - fail-closed validation for each required output ID.
4. P3 rerun safety proof:
   - per-output rerun contract and evidence.
5. M5 verdict and M6 handoff publication.

Out of scope:
1. WSP streaming execution (`M6` / P6).
2. SR READY publication (`M6` / P5).
3. IG readiness checks (`M6` / P4).
4. RTDL/case/obs closure (`M7/M8`).

## 3) M5 Deliverables
1. `M5.A` P3 handle closure snapshot.
2. `M5.B` seed source-policy decision snapshot.
3. `M5.C` seed snapshot (if seed executed) or explicit seed-skip proof.
4. `M5.D` stream-sort launch contract snapshot.
5. `M5.E` stream-sort summary with per-output receipt/manifest references.
6. `M5.F` checker pass snapshot.
7. `M5.G` per-output rerun safety snapshot.
8. `M5.H` deterministic verdict snapshot (`ADVANCE_TO_M6` or `HOLD_M5`).
9. `M5.I` `m6_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. M5 is active for deep planning and sequential execution preparation.

Execution block:
1. No M6 execution is allowed before M5 verdict is `ADVANCE_TO_M6`.
2. No stream-sort/checker execution is allowed until required output IDs and sort-key mapping are explicitly pinned.
3. No local/laptop/minio seed path is allowed at any step.

## 4.1) Anti-Cram Law (Binding for M5)
1. M5 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - seed source policy
   - managed compute contract
   - S3 artifact contract
   - checker fail-closed contract
   - rerun safety
   - verdict/handoff evidence
2. Sub-phase count is not fixed; this file expands until closure-grade coverage is achieved.
3. Any newly discovered hole blocks progression and must be added before execution continues.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + P3 handles closure | M5.A | M5.H | zero unresolved required P3 handles |
| Seed source-policy closure | M5.B | M5.C | managed object-store-only source proof |
| Seed/input presence closure | M5.C | M5.H | input prefixes present for run |
| Stream-sort launch contract | M5.D | M5.E | per-output launch plan + task definition mapping |
| Stream-sort execution + artifacts | M5.E | M5.F | per-output manifest + receipt durable |
| Checker fail-closed gate | M5.F | M5.H | checker pass artifact with all required output IDs |
| Per-output rerun safety | M5.G | M5.H | targeted rerun proof for failed/missing output |
| Verdict + M6 handoff | M5.H / M5.I | - | `ADVANCE_TO_M6` and durable `m6_handoff_pack.json` |

## 5) Work Breakdown (Deep)

## M5 Decision Pins (Closed Before Execution)
1. Managed-compute law:
   - seed/sort/checker run on managed compute one-shot jobs only.
2. S3 law:
   - oracle inputs and stream_view outputs are S3-resident under run-scoped prefixes.
3. Stream-view-first law:
   - downstream WSP must consume only P3 stream_view artifacts.
4. Determinism law:
   - per-output sort key mapping is pinned and applied consistently.
5. Fail-closed law:
   - missing manifest/receipt/checker evidence blocks M5 closure.
6. Rerun law:
   - per-output rerun only; no destructive raw-input deletion in normal reruns.

### M5.A Authority + Handle Closure (P3)
Goal:
1. Close required P3 handles and eliminate placeholder decisions before any P3 execution.

Tasks:
1. Resolve required handles:
   - `S3_ORACLE_BUCKET`
   - `S3_ORACLE_RUN_PREFIX_PATTERN`
   - `S3_ORACLE_INPUT_PREFIX_PATTERN`
   - `S3_STREAM_VIEW_PREFIX_PATTERN`
   - `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`
   - `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`
   - `S3_STREAM_SORT_RECEIPT_KEY_PATTERN`
   - `ORACLE_REQUIRED_OUTPUT_IDS`
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`
   - `ORACLE_SEED_SOURCE_MODE`
   - `ORACLE_SEED_SOURCE_BUCKET`
   - `ORACLE_SEED_SOURCE_PREFIX_PATTERN`
   - `ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED`
   - `TD_ORACLE_SEED` (if used)
   - `TD_ORACLE_STREAM_SORT`
   - `TD_ORACLE_CHECKER`
   - `ROLE_ORACLE_JOB`
   - `ECS_CLUSTER_NAME`
   - `SUBNET_IDS_PUBLIC`
   - `SECURITY_GROUP_ID_APP`.
2. Fail closed if any required value is unresolved or placeholder (`<PIN_AT_P3_PHASE_ENTRY>`).
3. Emit `m5_a_handle_closure_snapshot.json`.

DoD:
- [ ] Required P3 handle set is explicit and complete.
- [ ] Placeholder handles are fully pinned for execution.
- [ ] M5.A snapshot exists locally and durably.

Blockers:
1. `M5A-B1`: required P3 handle missing/unresolved.
2. `M5A-B2`: placeholder decision remains for required output IDs or sort keys.
3. `M5A-B3`: M5.A snapshot write/upload failure.

### M5.B Seed Source-Policy Closure
Goal:
1. Pin whether seed is required and enforce object-store-only source policy.

Entry conditions:
1. `M5.A` is PASS.

Tasks:
1. Evaluate run-scoped oracle input presence against `S3_ORACLE_INPUT_PREFIX_PATTERN`.
2. Decide seed mode:
   - `SEED_REQUIRED` if required inputs absent,
   - `SEED_SKIPPED_INPUTS_ALREADY_PRESENT` if inputs already present.
3. Validate source policy:
   - allow only managed object-store source (`S3`),
   - reject local/laptop/minio/filesystem source paths.
4. Emit `m5_b_seed_policy_snapshot.json` with decision + source proof.

DoD:
- [ ] Seed decision is explicit and evidence-backed.
- [ ] Source policy is object-store-only and fail-closed.
- [ ] M5.B snapshot exists locally and durably.

Blockers:
1. `M5B-B1`: seed decision ambiguous.
2. `M5B-B2`: seed source violates managed object-store-only policy.
3. `M5B-B3`: M5.B snapshot write/upload failure.

### M5.C Seed/Sync Execution (Conditional)
Goal:
1. Ensure required oracle inputs exist in run-scoped S3 prefix.

Entry conditions:
1. `M5.B` PASS.

Tasks:
1. If seed required:
   - run managed one-shot seed task with `ROLE_ORACLE_JOB`,
   - sync source S3 prefix to run-scoped oracle input prefix,
   - collect object count/size deltas.
2. If seed skipped:
   - verify required input prefixes already exist and are readable.
3. Emit `oracle/seed_snapshot.json` under run evidence root.

DoD:
- [ ] Required oracle input prefixes are present for run.
- [ ] Seed snapshot (or explicit seed-skip proof) exists durably.

Blockers:
1. `M5C-B1`: seed job failed.
2. `M5C-B2`: required input prefixes absent after seed/verify.
3. `M5C-B3`: seed snapshot write/upload failure.

### M5.D Stream-Sort Launch Contract
Goal:
1. Prepare deterministic per-output stream-sort launch plan.

Entry conditions:
1. `M5.C` PASS.

Tasks:
1. Build per-output launch matrix from pinned `ORACLE_REQUIRED_OUTPUT_IDS` and `ORACLE_SORT_KEY_BY_OUTPUT_ID`.
2. Validate each output ID resolves to:
   - input prefix,
   - output stream_view prefix,
   - manifest key pattern,
   - receipt key pattern.
3. Validate task definition/role launch contract:
   - `TD_ORACLE_STREAM_SORT`, `ROLE_ORACLE_JOB`.
4. Emit `m5_d_stream_sort_launch_snapshot.json`.

DoD:
- [ ] Per-output launch matrix is complete and deterministic.
- [ ] Sort task launch contract is fully resolvable.
- [ ] M5.D snapshot exists locally and durably.

Blockers:
1. `M5D-B1`: missing per-output launch mapping.
2. `M5D-B2`: task definition or role contract unresolved.
3. `M5D-B3`: M5.D snapshot write/upload failure.

### M5.E Stream-Sort Execution + Receipts/Manifests
Goal:
1. Produce stream_view artifacts and receipts/manifests for each required output ID.

Entry conditions:
1. `M5.D` PASS.

Tasks:
1. Execute one managed stream-sort job per required output ID (parallel allowed only across disjoint output prefixes).
2. For each output ID, verify durable existence of:
   - stream_view shards,
   - manifest,
   - stream_sort receipt.
3. Emit `oracle/stream_sort_summary.json` with per-output result set.

DoD:
- [ ] All required output IDs have stream_view + manifest + receipt.
- [ ] Stream-sort summary exists locally and durably.

Blockers:
1. `M5E-B1`: one or more stream-sort jobs failed.
2. `M5E-B2`: missing manifest/receipt/shards for one or more required output IDs.
3. `M5E-B3`: stream-sort summary write/upload failure.

### M5.F Checker Execution + PASS Artifact
Goal:
1. Run fail-closed checker and publish checker PASS evidence.

Entry conditions:
1. `M5.E` PASS.

Tasks:
1. Execute managed checker task (`TD_ORACLE_CHECKER`) for run/output scope.
2. Validate checker confirms all required output IDs PASS.
3. Publish `oracle/checker_pass.json`.

DoD:
- [ ] Checker exits success and validates all required outputs.
- [ ] `oracle/checker_pass.json` exists locally and durably.

Blockers:
1. `M5F-B1`: checker job failed.
2. `M5F-B2`: checker reported partial/missing output PASS set.
3. `M5F-B3`: checker pass artifact write/upload failure.

### M5.G Per-Output Rerun Safety Proof
Goal:
1. Prove targeted per-output rerun is supported and non-destructive.

Entry conditions:
1. `M5.F` PASS.

Tasks:
1. Execute one controlled per-output rerun proof:
   - choose a single output ID,
   - rerun stream-sort for that output only,
   - verify only targeted output prefix artifacts change.
2. Verify raw oracle inputs are unchanged by rerun.
3. Emit `m5_g_rerun_probe_snapshot.json`.

DoD:
- [ ] Per-output rerun proof is explicit and passes.
- [ ] Rerun did not require destructive raw-input deletion.
- [ ] M5.G snapshot exists locally and durably.

Blockers:
1. `M5G-B1`: rerun affected unintended output prefixes.
2. `M5G-B2`: rerun procedure required raw-input destructive mutation.
3. `M5G-B3`: M5.G snapshot write/upload failure.

### M5.H P3 Gates + Blocker Rollup + Verdict
Goal:
1. Compute deterministic M5 verdict from explicit gate predicates.

Entry conditions:
1. `M5.A..M5.G` snapshots are readable.

Tasks:
1. Evaluate predicates:
   - `p3_handles_closed`
   - `p3_seed_policy_closed`
   - `p3_inputs_present`
   - `p3_stream_sort_complete`
   - `p3_checker_pass`
   - `p3_rerun_safety_proven`.
2. Roll up blockers from `M5.A..M5.G`.
3. Compute verdict:
   - all predicates true + blockers empty => `ADVANCE_TO_M6`,
   - else => `HOLD_M5`.
4. Publish `m5_h_verdict_snapshot.json`.

DoD:
- [ ] Predicate set is explicit and reproducible.
- [ ] Blocker rollup is complete and fail-closed.
- [ ] Verdict snapshot exists locally and durably.

Blockers:
1. `M5H-B1`: missing/unreadable prerequisite snapshots.
2. `M5H-B2`: predicate evaluation incomplete/invalid.
3. `M5H-B3`: blocker rollup non-empty.
4. `M5H-B4`: verdict snapshot write/upload failure.

### M5.I M6 Handoff Artifact Publication
Goal:
1. Publish canonical handoff surface for M6 entry.

Entry conditions:
1. `M5.H` verdict is `ADVANCE_TO_M6`.

Tasks:
1. Build `m6_handoff_pack.json` containing:
   - `platform_run_id`
   - `m5_verdict`
   - checker pass URI
   - stream-sort summary URI
   - stream_view root URI
   - source execution IDs (`m5_a..m5_h`).
2. Ensure non-secret payload.
3. Publish local + durable handoff artifact.

DoD:
- [ ] `m6_handoff_pack.json` is complete and non-secret.
- [ ] Durable handoff publication passes.
- [ ] URI references are captured for M6 entry.

Blockers:
1. `M5I-B1`: M5 verdict is not `ADVANCE_TO_M6`.
2. `M5I-B2`: handoff pack missing required fields/URIs.
3. `M5I-B3`: non-secret policy violation in handoff artifact.
4. `M5I-B4`: handoff artifact write/upload failure.

## 6) M5 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M5 control-plane evidence root:
   - `evidence/dev_min/run_control/<m5_execution_id>/`
3. `<m5_execution_id>` format:
   - `m5_<YYYYMMDDTHHmmssZ>`

Minimum M5 evidence payloads:
1. `evidence/runs/<platform_run_id>/oracle/seed_snapshot.json` (if seed executed)
2. `evidence/runs/<platform_run_id>/oracle/stream_sort_summary.json`
3. `evidence/runs/<platform_run_id>/oracle/checker_pass.json`
4. `evidence/dev_min/run_control/<m5_execution_id>/m5_a_handle_closure_snapshot.json`
5. `evidence/dev_min/run_control/<m5_execution_id>/m5_b_seed_policy_snapshot.json`
6. `evidence/dev_min/run_control/<m5_execution_id>/m5_d_stream_sort_launch_snapshot.json`
7. `evidence/dev_min/run_control/<m5_execution_id>/m5_g_rerun_probe_snapshot.json`
8. `evidence/dev_min/run_control/<m5_execution_id>/m5_h_verdict_snapshot.json`
9. `evidence/dev_min/run_control/<m5_execution_id>/m6_handoff_pack.json`
10. local mirrors under:
    - `runs/dev_substrate/m5/<timestamp>/...`

Notes:
1. M5 artifacts must be non-secret.
2. Any secret-bearing payload in M5 artifacts is a hard blocker.
3. P3 semantics must preserve stream-view-first and per-output rerun law.

## 7) M5 Completion Checklist
- [ ] M5.A complete
- [ ] M5.B complete
- [ ] M5.C complete
- [ ] M5.D complete
- [ ] M5.E complete
- [ ] M5.F complete
- [ ] M5.G complete
- [ ] M5.H complete
- [ ] M5.I complete

## 8) Risks and Controls
R1: Hidden local seed path reintroduced.  
Control: explicit source-policy gate in M5.B + fail-closed blocker.

R2: Stream-sort produces partial/undocumented outputs.  
Control: per-output artifact checks + checker gate + verdict blocker rollup.

R3: Large-oracle compute cost spike.  
Control: one-shot ephemeral tasks + per-output rerun instead of full rerun.

R4: Checker bypass pressure.  
Control: `ADVANCE_TO_M6` requires checker PASS artifact and zero blockers.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M5 Execution)
Current blockers:
1. None.

Resolved blockers:
1. None yet.

Rule:
1. Any newly discovered blocker is appended here with closure criteria.
2. If this register is non-empty, M5 execution remains blocked.

## 9) Exit Criteria
M5 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M5 evidence contract artifacts are produced and verified.
3. Main plan M5 DoD checklist is complete.
4. M5 verdict is `ADVANCE_TO_M6`.
5. USER confirms progression to M6 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
