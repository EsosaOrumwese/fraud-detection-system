# Dev Substrate Deep Plan - M5 (P3 Oracle Lane)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M5._
_Last updated: 2026-02-14_

## 0) Purpose
M5 establishes P3 oracle readiness on managed substrate by keeping the oracle inlet contract explicit, producing deterministic `stream_view` artifacts for required output IDs, and validating them with fail-closed checker evidence before P4-P7 activation.

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
1. P3 oracle inlet closure:
   - explicit inlet path for how oracle inputs arrive into run-scoped S3.
2. P3 oracle input presence closure:
   - verify run-scoped S3 input prefixes exist (no platform seed/sync execution).
3. P3 stream-sort execution:
   - one-shot managed compute jobs only,
   - deterministic per-output sorting,
   - stream_view shard + manifest + receipt publication.
4. P3 checker execution:
   - fail-closed validation for each required output ID.
5. P3 rerun safety proof:
   - per-output rerun contract and evidence.
6. M5 verdict and M6 handoff publication.

Out of scope:
1. WSP streaming execution (`M6` / P6).
2. SR READY publication (`M6` / P5).
3. IG readiness checks (`M6` / P4).
4. RTDL/case/obs closure (`M7/M8`).

## 3) M5 Deliverables
1. `M5.A` P3 handle closure snapshot.
2. `M5.B` inlet policy decision snapshot.
3. `M5.C` inlet assertion snapshot (input-presence proof).
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
3. No platform seed/sync execution lane is allowed at any step.

## 4.1) Anti-Cram Law (Binding for M5)
1. M5 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - inlet ownership/policy
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
| Inlet policy closure | M5.B | M5.C | external-inlet ownership + no-platform-seed proof |
| Input presence assertion | M5.C | M5.H | input prefixes present for run |
| Stream-sort launch contract | M5.D | M5.E | per-output launch plan + task definition mapping |
| Stream-sort execution + artifacts | M5.E | M5.F | per-output manifest + receipt durable |
| Checker fail-closed gate | M5.F | M5.H | checker pass artifact with all required output IDs |
| Per-output rerun safety | M5.G | M5.H | targeted rerun proof for failed/missing output |
| Verdict + M6 handoff | M5.H / M5.I | - | `ADVANCE_TO_M6` and durable `m6_handoff_pack.json` |

## 5) Work Breakdown (Deep)

## M5 Decision Pins (Closed Before Execution)
1. Managed-compute law:
   - stream-sort/checker run on managed compute one-shot jobs only.
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
7. Inlet posture law (current cycle):
   - inlet remains an explicit contract in M5,
   - current run requires externally pre-staged oracle inputs under run-scoped prefix with evidence,
   - platform runtime must not execute seed/sync/copy.
8. Two-lane execution law (locked):
   - `M5` is the migration functional-closure lane (deterministic correctness + contracts),
   - full-scale throughput/perf proof is a separate lane and is not allowed to silently redefine M5 closure semantics.
9. M5.E gating law:
   - only `lane_mode=functional_green` may gate progression to `M5.F`,
   - `lane_mode=full_scale_probe` publishes performance/challenge evidence only and cannot by itself open M5->M6.
10. Capacity-proof law:
   - if full-scale probe is run during M5, runtime/capacity evidence must be recorded explicitly (row counts, task resources, runtime, blocker codes).

### M5.A Authority + Handle Closure (P3)
Goal:
1. Close required P3 handles and eliminate placeholder decisions before any P3 execution.

Entry conditions:
1. `M4.J` handoff is PASS and open for M5:
   - `m5_handoff_pack.json` has `overall_pass=true`, `blockers=[]`, `m5_entry_gate=OPEN`.
2. `platform_run_id` is inherited from M4 handoff (no re-mint at M5.A).
3. `M5` blocker register is empty at entry.

Required inputs:
1. Authority sources:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - `runs/dev_substrate/m4/20260214T170953Z/m5_handoff_pack.json`
   - `runs/dev_substrate/m4/20260214T170155Z/m4_i_verdict_snapshot.json`
   - `runs/dev_substrate/m3/20260213T221631Z/run.json`.
3. Handle materialization sources:
   - Terraform outputs and/or SSM parameters pinned by exact handle key.
   - wildcard/umbrella keys are not acceptable closure evidence.

Tasks:
1. Validate M4->M5 handoff invariants:
   - `m5_entry_gate=OPEN`
   - zero inbound blockers
   - run-id consistency across `m4_handoff_pack` and `m4_i_verdict`.
2. Resolve always-required handles for M5.A closure:
    - `S3_ORACLE_BUCKET`
    - `S3_ORACLE_RUN_PREFIX_PATTERN`
    - `S3_STREAM_VIEW_PREFIX_PATTERN`
    - `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`
    - `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`
    - `S3_STREAM_SORT_RECEIPT_KEY_PATTERN`
   - `ORACLE_REQUIRED_OUTPUT_IDS`
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`
   - `ORACLE_INLET_MODE`
   - `ORACLE_INLET_PLATFORM_OWNERSHIP`
   - `ORACLE_INLET_ASSERTION_REQUIRED`
   - `TD_ORACLE_STREAM_SORT`
   - `TD_ORACLE_CHECKER`
   - `ROLE_ORACLE_JOB`
   - `ECS_CLUSTER_NAME`
   - `SUBNET_IDS_PUBLIC`
   - `SECURITY_GROUP_ID_APP`
   - `S3_EVIDENCE_BUCKET`.
3. Enforce fail-closed closure rules:
   - reject placeholders (including `<PIN_AT_P3_PHASE_ENTRY>`),
   - reject wildcard/umbrella key references as closure proof,
   - reject ambiguous source-of-truth (more than one conflicting origin),
   - reject any `ORACLE_SEED_*` or `TD_ORACLE_SEED` usage.
4. Emit `m5_a_handle_closure_snapshot.json` with minimum fields:
   - `m5_execution_id`, `platform_run_id`
   - `required_handle_keys_always`
   - `resolved_handle_count_always`, `unresolved_handle_count_always`
   - `unresolved_handle_keys_always`
   - `placeholder_handle_keys`
   - `wildcard_key_present`
   - `disallowed_seed_handles_present`
   - `overall_pass`.
5. Publish snapshot:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_a_handle_closure_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_a_handle_closure_snapshot.json`.
6. Stop phase progression if `overall_pass=false`.

DoD:
- [x] M4->M5 entry gate invariants verified and recorded.
- [x] Always-required P3 handle set is explicit, concrete, and fully resolved.
- [x] Placeholder and wildcard handle usage are absent from closure evidence.
- [x] Inlet policy handles are explicit and disallowed seed handles are absent.
- [x] M5.A snapshot exists locally and durably.

Blockers:
1. `M5A-B1`: M4->M5 handoff precondition invalid or unreadable.
2. `M5A-B2`: always-required P3 handle missing/unresolved.
3. `M5A-B3`: placeholder/wildcard/ambiguous key detected in closure set.
4. `M5A-B4`: required output-id or sort-key decision remains unpinned.
5. `M5A-B5`: M5.A snapshot write/upload failure.

Execution result (2026-02-14):
1. `M5.A` executed PASS with zero blockers.
2. Local snapshot:
   - `runs/dev_substrate/m5/20260214T190332Z/m5_a_handle_closure_snapshot.json`
3. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T190332Z/m5_a_handle_closure_snapshot.json`

### M5.B Oracle Inlet Policy Closure
Goal:
1. Pin external-inlet ownership and fail-closed policy (no platform seed/sync lane).

Entry conditions:
1. `M5.A` is PASS.
2. `M5.A` snapshot is readable:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_a_handle_closure_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_a_handle_closure_snapshot.json`

Required inputs:
1. Authority:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P3.5`)
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` (inlet policy handles).
2. Source artifacts:
   - latest `M5.A` snapshot (local + durable URI),
   - `runs/dev_substrate/m4/20260214T170953Z/m5_handoff_pack.json`,
   - `runs/dev_substrate/m3/20260213T221631Z/run.json`.
3. Scan scope (drift guard):
   - migration authority docs in `docs/model_spec/platform/migration_to_dev/`,
   - active M5 planning docs under `docs/model_spec/platform/implementation_maps/dev_substrate/`.

Tasks:
1. Validate `M5.A` carry-forward invariants:
   - `overall_pass=true`,
   - `blockers=[]`,
   - `platform_run_id` matches M4 handoff and M3 run header.
2. Resolve and validate inlet policy handles from registry (exact-value match):
   - `ORACLE_INLET_MODE = external_pre_staged`,
   - `ORACLE_INLET_PLATFORM_OWNERSHIP = outside_platform_runtime_scope`,
   - `ORACLE_INLET_ASSERTION_REQUIRED = true`.
3. Validate P3 boundary consistency against runbook `P3.5`:
   - inlet is external to platform runtime,
   - platform runtime must not perform sync/copy/seed,
   - no local/minio/filesystem source path allowance in dev runtime.
4. Enforce fail-closed drift guard with symbol scans:
   - disallow active handle/task references:
     - `ORACLE_SEED_*`, `TD_ORACLE_SEED`, `ENTRYPOINT_ORACLE_SEED`,
   - disallow active execution-mode language implying platform seed lane:
     - `SEED_REQUIRED` (for P3 runtime),
     - `oracle/seed_snapshot.json` in active M5 surfaces.
5. Emit `m5_b_inlet_policy_snapshot.json` with minimum fields:
   - `m5_execution_id`, `platform_run_id`,
   - `source_m5a_snapshot_local`, `source_m5a_snapshot_uri`,
   - `inlet_policy_expected`, `inlet_policy_observed`,
   - `policy_value_match`,
   - `boundary_consistency_checks`,
   - `disallowed_symbols_found`,
   - `blockers`,
   - `overall_pass`.
6. Publish snapshot:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_b_inlet_policy_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_b_inlet_policy_snapshot.json`.
7. Stop progression if `overall_pass=false`.

DoD:
- [x] `M5.A` carry-forward invariants are verified and recorded.
- [x] Inlet policy handle values are exact-match and non-ambiguous.
- [x] Drift guard scan shows no disallowed seed-lane symbols in active docs/surfaces.
- [x] Inlet policy boundary statement is explicit and evidence-backed.
- [x] M5.B snapshot exists locally and durably.

Blockers:
1. `M5B-B1`: M5.A carry-forward invariants invalid or unreadable.
2. `M5B-B2`: inlet policy handles missing/ambiguous/mismatched.
3. `M5B-B3`: disallowed seed-lane symbol detected in active scope.
4. `M5B-B4`: M5.B snapshot write/upload failure.

Execution result (2026-02-14):
1. First pass attempt produced `M5B-B3` due drift-scanner false positives on guardrail-list lines.
2. Scanner context classification was tightened (guardrail declaration context is allowlisted); rerun closed PASS.
3. Final PASS snapshot:
   - local: `runs/dev_substrate/m5/20260214T191428Z/m5_b_inlet_policy_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T191428Z/m5_b_inlet_policy_snapshot.json`
4. Final state:
   - `overall_pass=true`
   - `blockers=[]`
   - `policy_value_match.overall=true`
   - `boundary_consistency_checks.overall=true`
   - `disallowed_symbols_found.violation_count=0`

### M5.C Oracle Input Presence Assertion (No Seed Execution)
Goal:
1. Ensure required oracle inputs exist in the engine-run-scoped Oracle Store S3 prefix (no `platform_run_id` coupling).

Entry conditions:
1. `M5.B` PASS.
2. `M5.B` snapshot is readable:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_b_inlet_policy_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_b_inlet_policy_snapshot.json`

Required inputs:
1. Authority:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P3.5`, `P3.8`)
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - latest `M5.B` snapshot (local + durable URI),
   - `runs/dev_substrate/m3/20260213T221631Z/run.json`.
3. Required handles:
    - `S3_ORACLE_BUCKET`,
    - `S3_ORACLE_RUN_PREFIX_PATTERN`,
    - `S3_EVIDENCE_BUCKET`,
    - `ORACLE_REQUIRED_OUTPUT_IDS`.
4. Required object keys under engine-run oracle input root:
    - `_oracle_pack_manifest.json`,
    - `_SEALED.json`.

Tasks:
1. Validate `M5.B` carry-forward invariants:
   - `overall_pass=true`,
   - `blockers=[]`,
   - `platform_run_id` matches M3 run header.
2. Resolve run-scoped input root using:
    - `S3_ORACLE_RUN_PREFIX_PATTERN` expanded from pinned `ORACLE_SOURCE_NAMESPACE` + `ORACLE_ENGINE_RUN_ID` (no `platform_run_id` token).
3. Assert oracle input prefix presence/readability:
   - prefix exists,
   - at least one object present under run-scoped input root.
4. Assert required manifest/seal object presence/readability:
   - `_oracle_pack_manifest.json`,
   - `_SEALED.json`.
5. Parse `_oracle_pack_manifest.json` and assert required output-id coverage:
   - every `output_id` in `ORACLE_REQUIRED_OUTPUT_IDS` is represented in manifest-declared surfaces,
   - if manifest parse fails or required output IDs are missing, fail closed.
6. Emit `oracle/inlet_assertion_snapshot.json` with minimum fields:
   - `m5_execution_id`, `platform_run_id`,
   - `source_m5b_snapshot_local`, `source_m5b_snapshot_uri`,
   - `oracle_bucket`, `oracle_input_prefix`,
   - `required_output_ids`, `missing_output_ids`,
   - `manifest_key`, `sealed_key`,
   - `input_prefix_readable`,
   - `manifest_readable`, `seal_readable`,
   - `manifest_output_coverage_pass`,
   - `blockers`,
   - `overall_pass`.
7. Publish snapshot:
   - local: `runs/dev_substrate/m5/<timestamp>/inlet_assertion_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/oracle/inlet_assertion_snapshot.json`.
8. Stop progression if `overall_pass=false`.

DoD:
- [x] `M5.B` carry-forward invariants are verified and recorded.
- [x] Engine-run oracle input prefix is present and readable.
- [x] Required manifest/seal objects are present and readable.
- [x] Required output IDs are fully covered by manifest-declared input surfaces.
- [x] Inlet assertion snapshot exists locally and durably.

Blockers:
1. `M5C-B1`: M5.B carry-forward invariants invalid or unreadable.
2. `M5C-B2`: required input prefix absent/unreadable.
3. `M5C-B3`: required oracle manifest/seal artifacts missing/unreadable.
4. `M5C-B4`: required output IDs missing from manifest-declared surfaces.
5. `M5C-B5`: inlet assertion snapshot write/upload failure.

Execution result (2026-02-14):
1. First pass attempt produced blockers `M5C-B2` and `M5C-B4` from assertion implementation defects:
   - `list-objects-v2 --max-items` undercounted prefix presence in this flow,
   - one manifest `path_template` string retained leading quote noise during prefix derivation.
2. Assertion logic was corrected to:
   - use API-level `--max-keys 1` prefix existence checks,
   - normalize/trim quoted template values before static-prefix checks.
3. Final rerun closed PASS with durable publication:
   - local: `runs/dev_substrate/m5/20260214T193548Z/inlet_assertion_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/inlet_assertion_snapshot.json`
4. Final state:
   - `overall_pass=true`
   - `blockers=[]`
   - `missing_output_ids=[]`
   - `manifest_output_coverage_pass=true`

### M5.D Stream-Sort Launch Contract
Goal:
1. Prepare deterministic per-output stream-sort launch plan.

Entry conditions:
1. `M5.C` PASS.
2. `M5.C` snapshot is readable:
   - local: `runs/dev_substrate/m5/<timestamp>/inlet_assertion_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/oracle/inlet_assertion_snapshot.json`

Required inputs:
1. Authority:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P3.9`, `P3.10`)
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - latest `M5.C` snapshot (local + durable URI),
   - `runs/dev_substrate/m3/20260213T221631Z/run.json`.
3. Required handles:
    - `S3_ORACLE_BUCKET`,
    - `S3_ORACLE_RUN_PREFIX_PATTERN`,
    - `S3_STREAM_VIEW_PREFIX_PATTERN`,
    - `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`,
    - `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`,
    - `S3_STREAM_SORT_RECEIPT_KEY_PATTERN`,
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
   - `TD_ORACLE_STREAM_SORT`,
   - `ROLE_ORACLE_JOB`,
   - `ECS_CLUSTER_NAME`,
   - `SUBNET_IDS_PUBLIC`,
   - `SECURITY_GROUP_ID_APP`,
   - `S3_EVIDENCE_BUCKET`.

Tasks:
1. Validate `M5.C` carry-forward invariants:
   - `overall_pass=true`,
   - `blockers=[]`,
   - `platform_run_id` matches M3 run header.
2. Build deterministic per-output launch matrix from:
    - `ORACLE_REQUIRED_OUTPUT_IDS`,
    - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
    - engine-run-scoped prefix patterns (`S3_ORACLE_RUN_PREFIX_PATTERN`, `S3_STREAM_VIEW_*`).
3. Validate sort-key closure for each required output:
   - every required output_id has exactly one mapped sort key,
   - no missing or blank sort-key entries,
   - no unsupported multi-output ambiguity for required output set.
4. Validate per-output artifact path contract resolves for launch:
   - input prefix,
   - stream_view output prefix,
   - stream_view manifest key,
   - stream-sort receipt key.
5. Validate managed launch profile contract:
   - `TD_ORACLE_STREAM_SORT`, `ROLE_ORACLE_JOB`,
   - `ECS_CLUSTER_NAME`, `SUBNET_IDS_PUBLIC`, `SECURITY_GROUP_ID_APP`,
   - execution mode remains managed one-shot (no local/laptop fallback).
6. Emit `m5_d_stream_sort_launch_snapshot.json` with minimum fields:
   - `m5_execution_id`, `platform_run_id`,
   - `source_m5c_snapshot_local`, `source_m5c_snapshot_uri`,
   - `required_output_ids`,
   - `per_output_launch_matrix` (output_id, sort_key, input_prefix, stream_view_output_prefix, manifest_key, receipt_key),
   - `task_profile` (`task_definition`, `role`, `cluster`, `subnets`, `security_group`),
   - `unresolved_sort_key_output_ids`,
   - `unresolved_path_contract_output_ids`,
   - `launch_profile_valid`,
   - `blockers`,
   - `overall_pass`.
7. Publish snapshot:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_d_stream_sort_launch_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_d_stream_sort_launch_snapshot.json`.
8. Stop progression if `overall_pass=false`.

DoD:
- [x] `M5.C` carry-forward invariants are verified and recorded.
- [x] Per-output launch matrix is complete and deterministic.
- [x] Sort-key closure is complete for all required output IDs.
- [x] Managed launch profile contract is fully resolvable.
- [x] M5.D snapshot exists locally and durably.

Blockers:
1. `M5D-B1`: M5.C carry-forward invariants invalid or unreadable.
2. `M5D-B2`: missing/ambiguous sort-key mapping for one or more required outputs.
3. `M5D-B3`: per-output input/output/manifest/receipt path contract unresolved.
4. `M5D-B4`: task/profile/network launch contract unresolved.
5. `M5D-B5`: M5.D snapshot write/upload failure.

Execution result (2026-02-14):
1. `M5.D` execution produced a fail-closed HOLD with blocker `M5D-B4`.
2. Carry-forward and path/sort contract checks passed:
   - `M5.C` invariants PASS,
   - required-output sort-key closure PASS,
   - per-output launch path contract resolution PASS.
3. Launch-profile check failed on task-definition materialization:
   - `TD_ORACLE_STREAM_SORT = "fraud-platform-dev-min-oracle-stream-sort"` could not be described in ECS at execution time.
4. Snapshot publication:
   - local: `runs/dev_substrate/m5/20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
5. Final state:
   - `overall_pass=false`
   - `blockers=["M5D-B4"]`
6. Blocker resolution + rerun closure:
   - materialized missing oracle task-definition families through demo Terraform apply:
     - `fraud-platform-dev-min-oracle-stream-sort`
     - `fraud-platform-dev-min-oracle-checker`
   - reran `M5.D`; final PASS artifact:
     - local: `runs/dev_substrate/m5/20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
   - final PASS state:
     - `overall_pass=true`
     - `blockers=[]`
     - `task_definition_materialized=true`

### M5.E Stream-Sort Execution + Receipts/Manifests
Goal:
1. Produce stream_view artifacts and receipts/manifests for each required output ID.

Entry conditions:
1. `M5.D` PASS.
2. `M5.D` snapshot is readable:
   - local: `runs/dev_substrate/m5/<timestamp>/m5_d_stream_sort_launch_snapshot.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m5_execution_id>/m5_d_stream_sort_launch_snapshot.json`

Required inputs:
1. Authority:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P3 stream-sort execution section)
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`.
2. Source artifacts:
   - latest `M5.D` snapshot (local + durable URI),
   - `runs/dev_substrate/m3/20260213T221631Z/run.json`.
3. Required handles/launch surfaces:
   - `TD_ORACLE_STREAM_SORT`,
   - `ECS_CLUSTER_NAME`,
   - `SUBNET_IDS_PUBLIC`,
   - `SECURITY_GROUP_ID_APP`,
   - `S3_ORACLE_BUCKET`,
   - `S3_EVIDENCE_BUCKET`.
4. Required execution matrix source:
   - `per_output_launch_matrix` from `M5.D` snapshot (authoritative; no ad hoc recompute during M5.E execution).

Tasks:
1. Pin execution lane + workload profile before launching any task:
   - `lane_mode` must be one of:
     - `functional_green` (migration-gating),
     - `full_scale_probe` (non-gating capacity evidence lane).
   - bind and record a concrete workload profile for the run (`workload_profile_id`) with explicit source artifact.
2. Validate `M5.D` carry-forward invariants:
   - `overall_pass=true`,
   - `blockers=[]`,
   - `launch_profile_valid=true`,
   - no unresolved sort-key/path-contract output IDs.
3. Build execution set from `M5.D.per_output_launch_matrix` only:
   - output_id,
   - sort_key,
   - input_prefix,
   - stream_view output prefix,
   - manifest key,
   - receipt key.
4. Launch one managed ECS run-task per output ID using `TD_ORACLE_STREAM_SORT`:
   - run-scope env (`REQUIRED_PLATFORM_RUN_ID`),
   - per-output launch payload from matrix row,
   - network config from pinned cluster/subnets/security-group handles.
5. Execution concurrency rule:
   - default serial launch for closure safety,
   - parallel allowed only across disjoint output prefixes with explicit operator cap.
6. Await task completion for each output and record runtime status:
   - task ARN,
   - last status,
   - stopped reason,
   - container exit code.
7. For each output ID, verify durable artifact contract:
   - stream_view output prefix has at least one shard/object,
   - stream_view manifest key exists/readable,
   - stream-sort receipt key exists/readable.
8. Emit `oracle/stream_sort_summary.json` with minimum fields:
   - `m5_execution_id`, `platform_run_id`,
   - `source_m5d_snapshot_local`, `source_m5d_snapshot_uri`,
   - `lane_mode`, `workload_profile_id`,
   - `compute_profile` (task resource/override contract used),
   - `required_output_ids`,
   - `per_output_results` (launch payload, task runtime result, artifact checks),
   - `failed_output_ids`,
   - `blockers`,
   - `overall_pass`.
9. Publish summary:
   - local: `runs/dev_substrate/m5/<timestamp>/stream_sort_summary.json`
   - durable: `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/oracle/stream_sort_summary.json`.
10. Lane-specific progression rule:
   - if `lane_mode=functional_green`, stop progression when `overall_pass=false`,
   - if `lane_mode=full_scale_probe`, always keep M5 in HOLD and route closure decision to M10 scale lane evidence.

DoD:
- [x] `lane_mode` + `workload_profile_id` are explicitly pinned in summary.
- [x] `M5.D` carry-forward invariants are verified and recorded.
- [x] Every required output ID has a completed managed stream-sort task result.
- [x] All required output IDs have stream_view shards + manifest + receipt durably present.
- [x] `failed_output_ids=[]` in summary.
- [x] Stream-sort summary exists locally and durably.

Blockers:
1. `M5E-B1`: M5.D carry-forward invariants invalid/unreadable.
2. `M5E-B2`: one or more managed stream-sort task launches fail.
3. `M5E-B3`: one or more stream-sort tasks stop non-successfully (non-zero exit/terminal failure).
4. `M5E-B4`: missing stream_view shards and/or manifest/receipt for one or more required output IDs.
5. `M5E-B5`: stream-sort summary write/upload failure.
6. `M5E-B6`: lane/workload profile not pinned (`lane_mode` and/or `workload_profile_id` missing).
7. `M5E-B7`: full-scale probe attempted to advance M5 gating directly.
8. `M5E-B8`: `functional_workload_profile.json` missing for a `lane_mode=functional_green` execution.

Execution observations + decision lock (2026-02-14):
1. First full-matrix M5.E run failed fail-closed with:
   - `M5E-B3` + `M5E-B4` on all required outputs.
2. Root cause cycle 1:
   - oracle task-role lacked object-store data-plane access; logs showed `s3:GetObject AccessDenied` for `.../inputs/run_receipt.json`.
   - fixed via demo Terraform IAM patch on `fraud-platform-dev-min-rtdl-core`.
3. Root cause cycle 2 (post-IAM):
   - full-scale stream-sort remained runtime-heavy; task exits observed `137` and DuckDB temp/offload exhaustion in logs.
   - summary evidence:
     - local: `runs/dev_substrate/m5/20260214T202411Z/stream_sort_summary.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/stream_sort_summary.json`
4. Capacity proof:
    - single-output probe `arrival_events_5B` processed `124724153` rows and completed only under high resource profile (`8 vCPU`, `32GB`, chunked sort), with runtime around `~77 min`.
    - proof artifacts:
      - `s3://fraud-platform-dev-min-object-store/oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/stream_view/ts_utc/output_id=arrival_events_5B/_stream_sort_receipt.json`
      - `s3://fraud-platform-dev-min-object-store/oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/stream_view/ts_utc/output_id=arrival_events_5B/_stream_view_manifest.json`
5. Locked resolution:
   - M5 continues as migration functional-closure lane (`functional_green` workload profile),
   - full-scale throughput/perf closure is explicitly moved to M10 scale lane (no semantic drift, no silent gate mutation).
6. Immediate closure requirement lock:
   - next functional-gating M5.E execution must publish `functional_workload_profile.json` before task launch.

Execution result (2026-02-15):
1. Functional-green rerun closed PASS with pinned bounded workload profile.
2. Published artifacts:
   - local:
     - `runs/dev_substrate/m5/20260214T235117Z/functional_workload_profile.json`
     - `runs/dev_substrate/m5/20260214T235117Z/m5_d_stream_sort_launch_snapshot.json`
     - `runs/dev_substrate/m5/20260214T235117Z/stream_sort_summary.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/functional_workload_profile.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m5_d_stream_sort_launch_snapshot.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/stream_sort_summary.json`
3. Final state:
   - `lane_mode=functional_green`
   - `workload_profile_id=fg_small_v1_n20`
   - `failed_output_ids=[]`
   - `blockers=[]`
   - `overall_pass=true`

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
- [x] Checker exits success and validates all required outputs.
- [x] `oracle/checker_pass.json` exists locally and durably.

Blockers:
1. `M5F-B1`: checker job failed.
2. `M5F-B2`: checker reported partial/missing output PASS set.
3. `M5F-B3`: checker pass artifact write/upload failure.

Execution result (2026-02-15):
1. `M5.F` closed PASS with managed checker run-task.
2. Artifacts:
   - local:
     - `runs/dev_substrate/m5/20260215T002040Z/checker_pass.json`
     - `runs/dev_substrate/m5/20260215T002040Z/m5_f_checker_execution_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/checker_pass.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m5_f_checker_execution_snapshot.json`
3. Managed execution proof:
   - task ARN: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/824426be72784c83b1deff0174b41bf7`
   - exit code: `0`

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
- [x] Per-output rerun proof is explicit and passes.
- [x] Rerun did not require destructive raw-input deletion.
- [x] M5.G snapshot exists locally and durably.

Blockers:
1. `M5G-B1`: rerun affected unintended output prefixes.
2. `M5G-B2`: rerun procedure required raw-input destructive mutation.
3. `M5G-B3`: M5.G snapshot write/upload failure.

Execution result (2026-02-15):
1. `M5.G` closed PASS via targeted rerun on `s3_event_stream_with_fraud_6B`.
2. Managed rerun task:
   - task ARN: `arn:aws:ecs:eu-west-2:230372904534:task/fraud-platform-dev-min/5fd0bfed46a54bc7bc88bd3f5a111f51`
   - exit code: `0`
3. Invariants:
   - input prefix unchanged: `true`
   - non-target output prefixes unchanged: `true`
   - target manifest + receipt present: `true`
4. Snapshot:
   - local: `runs/dev_substrate/m5/20260215T002310Z/m5_g_rerun_probe_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m5_g_rerun_probe_snapshot.json`

### M5.H P3 Gates + Blocker Rollup + Verdict
Goal:
1. Compute deterministic M5 verdict from explicit gate predicates.

Entry conditions:
1. `M5.A..M5.G` snapshots are readable.

Tasks:
1. Evaluate predicates:
   - `p3_handles_closed`
   - `p3_inlet_policy_closed`
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
- [x] Predicate set is explicit and reproducible.
- [x] Blocker rollup is complete and fail-closed.
- [x] Verdict snapshot exists locally and durably.

Blockers:
1. `M5H-B1`: missing/unreadable prerequisite snapshots.
2. `M5H-B2`: predicate evaluation incomplete/invalid.
3. `M5H-B3`: blocker rollup non-empty.
4. `M5H-B4`: verdict snapshot write/upload failure.

Execution result (2026-02-15):
1. `M5.H` closed PASS with deterministic verdict `ADVANCE_TO_M6`.
2. Predicate set:
   - `p3_handles_closed=true`
   - `p3_inlet_policy_closed=true`
   - `p3_inputs_present=true`
   - `p3_stream_sort_complete=true`
   - `p3_checker_pass=true`
   - `p3_rerun_safety_proven=true`
3. Artifacts:
   - local: `runs/dev_substrate/m5/20260215T002310Z/m5_h_verdict_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m5_h_verdict_snapshot.json`

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
- [x] `m6_handoff_pack.json` is complete and non-secret.
- [x] Durable handoff publication passes.
- [x] URI references are captured for M6 entry.

Blockers:
1. `M5I-B1`: M5 verdict is not `ADVANCE_TO_M6`.
2. `M5I-B2`: handoff pack missing required fields/URIs.
3. `M5I-B3`: non-secret policy violation in handoff artifact.
4. `M5I-B4`: handoff artifact write/upload failure.

Execution result (2026-02-15):
1. `M5.I` closed PASS and published canonical M6 handoff pack.
2. Artifacts:
   - local: `runs/dev_substrate/m5/20260215T002310Z/m6_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m6_handoff_pack.json`
3. Handoff verdict field:
   - `m5_verdict=ADVANCE_TO_M6`

## 6) M5 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M5 control-plane evidence root:
   - `evidence/dev_min/run_control/<m5_execution_id>/`
3. `<m5_execution_id>` format:
   - `m5_<YYYYMMDDTHHmmssZ>`

Minimum M5 evidence payloads:
1. `evidence/runs/<platform_run_id>/oracle/inlet_assertion_snapshot.json`
2. `evidence/runs/<platform_run_id>/oracle/stream_sort_summary.json`
3. `evidence/runs/<platform_run_id>/oracle/checker_pass.json`
4. `evidence/dev_min/run_control/<m5_execution_id>/m5_a_handle_closure_snapshot.json`
5. `evidence/dev_min/run_control/<m5_execution_id>/m5_b_inlet_policy_snapshot.json`
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
- [x] M5.A complete
- [x] M5.B complete
- [x] M5.C complete
- [x] M5.D complete
- [x] M5.E complete
- [x] M5.F complete
- [x] M5.G complete
- [x] M5.H complete
- [x] M5.I complete

## 8) Risks and Controls
R1: Hidden inlet bootstrap/seed lane reintroduced.  
Control: explicit inlet-policy gate in M5.B + fail-closed blocker.

R2: Stream-sort produces partial/undocumented outputs.  
Control: per-output artifact checks + checker gate + verdict blocker rollup.

R3: Large-oracle compute cost spike.  
Control: one-shot ephemeral tasks + per-output rerun instead of full rerun.

R4: Checker bypass pressure.  
Control: `ADVANCE_TO_M6` requires checker PASS artifact and zero blockers.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M5 Closure)
Current blockers:
1. None.

Resolved blockers:
1. `M5D-B4` resolved by IaC materialization + rerun PASS.
   - failing artifact:
     - local: `runs/dev_substrate/m5/20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
   - closure artifact:
     - local: `runs/dev_substrate/m5/20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
2. Initial M5.E IAM blocker (role could not read oracle run receipt) resolved by Terraform IAM patch on RTDL core lane role.
   - root-cause evidence: CloudWatch log stream for task `5f3fa831393d4a6682ffb132490785cc` (`s3:GetObject AccessDenied` on oracle input run_receipt).
3. `M5E-B3`, `M5E-B4`, `M5E-B6`, and `M5E-B8` resolved by functional-green closure run:
   - local: `runs/dev_substrate/m5/20260214T235117Z/stream_sort_summary.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/stream_sort_summary.json`
4. `M5F-B3` resolved by IAM expansion on RTDL core role to include evidence run-prefix write/read:
   - policy source: `infra/terraform/modules/demo/main.tf`
   - closure proof: checker pass artifact published by managed checker task.

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
