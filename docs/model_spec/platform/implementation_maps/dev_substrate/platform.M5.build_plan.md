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
   - `S3_ORACLE_INPUT_PREFIX_PATTERN`
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
1. Ensure required oracle inputs exist in run-scoped S3 prefix.

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
   - `S3_ORACLE_INPUT_PREFIX_PATTERN`,
   - `S3_EVIDENCE_BUCKET`,
   - `ORACLE_REQUIRED_OUTPUT_IDS`.
4. Required object keys under run-scoped oracle input root:
   - `_oracle_pack_manifest.json`,
   - `_SEALED.json`.

Tasks:
1. Validate `M5.B` carry-forward invariants:
   - `overall_pass=true`,
   - `blockers=[]`,
   - `platform_run_id` matches M3 run header.
2. Resolve run-scoped input root using:
   - `S3_ORACLE_INPUT_PREFIX_PATTERN` + `platform_run_id`.
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
- [x] Run-scoped oracle input prefix is present and readable.
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
- [ ] M5.D complete
- [ ] M5.E complete
- [ ] M5.F complete
- [ ] M5.G complete
- [ ] M5.H complete
- [ ] M5.I complete

## 8) Risks and Controls
R1: Hidden inlet bootstrap/seed lane reintroduced.  
Control: explicit inlet-policy gate in M5.B + fail-closed blocker.

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
