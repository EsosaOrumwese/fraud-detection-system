# Dev Substrate Stress Plan - M5.P3 (P3 ORACLE_READY)
_Parent authority: `platform.M5.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-03_

## 0) Purpose
M5.P3 stress validates oracle source boundary and stream-view readiness under realistic production posture.

M5.P3 stress must prove:
1. oracle source boundary remains read-only to platform runtime and ownership is not drifted.
2. raw upload contract and managed stream-sort contract are enforced fail-closed.
3. required output surfaces and manifests are present/readable for active oracle source.
4. stream-view materialization and sort-key contract remain deterministic.
5. P3 rollup emits deterministic verdict for P4 entry (`ADVANCE_TO_P4` only when blocker-free).

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P3.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_execution_summary.json`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

## 2) Stage-A Findings (M5.P3)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M5P3-ST-F1` | `PREVENT` | P3 has mixed concerns (boundary, upload/sort, contract, rollup); a shallow runbook can hide blocker propagation errors. | Use explicit staged runbook `S0..S5` with blocker-safe transitions only. |
| `M5P3-ST-F2` | `PREVENT` | Managed-sort path must remain canonical (`EMR_SERVERLESS_SPARK`) with no local fallback. | Enforce runtime-path checks and fail if local execution mode is allowed. |
| `M5P3-ST-F3` | `PREVENT` | P3 verdict must be deterministic and blocker-consistent before P4 activation. | Pin rollup rule: `ADVANCE_TO_P4` only when all prior P3 stages are blocker-free. |
| `M5P3-ST-F4` | `OBSERVE` | Oracle source handle drifts can silently break prefix/materialization checks. | Add explicit handle and prefix resolution checks at S0/S1. |
| `M5P3-ST-F5` | `OBSERVE` | Raw upload and managed sort are high-cost lanes if rerun broadly. | Use targeted rerun policy by failing stage only. |
| `M5P3-ST-F6` | `ACCEPT` | Historical P3 closure exists as reference evidence. | Treat historical evidence as baseline only; require active-source checks for current cycle. |

## 3) Scope Boundary for M5.P3 Stress
In scope:
1. P3 boundary ownership and oracle-source namespace checks.
2. raw upload + managed distributed sort readiness checks.
3. required output and manifest readability checks.
4. stream-view contract/materialization checks.
5. P3 rollup and deterministic verdict emission.

Out of scope:
1. ingest boundary/auth/topic/envelope lanes (`M5.P4`).
2. M6 activation and runtime stream processing.

## 4) M5.P3 Stress Handle Packet (Pinned)
1. `M5P3_STRESS_PROFILE_ID = "oracle_ready_stress_v0"`.
2. `M5P3_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p3_blocker_register.json"`.
3. `M5P3_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p3_execution_summary.json"`.
4. `M5P3_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p3_decision_log.json"`.
5. `M5P3_STRESS_REQUIRED_ARTIFACTS = "m5p3_stagea_findings.json,m5p3_lane_matrix.json,m5p3_probe_latency_throughput_snapshot.json,m5p3_control_rail_conformance_snapshot.json,m5p3_secret_safety_snapshot.json,m5p3_cost_outcome_receipt.json,m5p3_blocker_register.json,m5p3_execution_summary.json,m5p3_decision_log.json"`.
6. `M5P3_STRESS_MAX_RUNTIME_MINUTES = 180`.
7. `M5P3_STRESS_MAX_SPEND_USD = 40`.
8. `M5P3_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_P4"`.
9. `M5P3_STRESS_MANAGED_SORT_REQUIRED = true`.
10. `M5P3_STRESS_LOCAL_SORT_ALLOWED = false`.

Registry-backed required handles for M5.P3:
1. `ORACLE_REQUIRED_OUTPUT_IDS`
2. `ORACLE_SORT_KEY_BY_OUTPUT_ID`
3. `ORACLE_STORE_BUCKET`
4. `ORACLE_STORE_PLATFORM_ACCESS_MODE`
5. `ORACLE_STORE_WRITE_OWNER`
6. `ORACLE_SOURCE_NAMESPACE`
7. `ORACLE_ENGINE_RUN_ID`
8. `S3_ORACLE_RUN_PREFIX_PATTERN`
9. `S3_ORACLE_INPUT_PREFIX_PATTERN`
10. `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`
11. `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`
12. `ORACLE_STREAM_SORT_EXECUTION_MODE`
13. `ORACLE_STREAM_SORT_ENGINE`
14. `ORACLE_STREAM_SORT_TRIGGER_SURFACE`
15. `ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED`
16. `ORACLE_STREAM_SORT_REQUIRED_BEFORE_P3B`
17. `ORACLE_STREAM_SORT_RECEIPT_REQUIRED`
18. `ORACLE_STREAM_SORT_PARITY_CHECK_REQUIRED`
19. `ORACLE_STREAM_SORT_EMR_SERVERLESS_APP`
20. `ORACLE_STREAM_SORT_EXECUTION_ROLE_ARN`
21. `ORACLE_STREAM_SORT_EMR_RELEASE_LABEL`
22. `S3_EVIDENCE_BUCKET`
23. `S3_RUN_CONTROL_ROOT_PATTERN`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M5.P3 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry gate closure | `S0` | required handles + M5 parent S0 readiness dependency |
| Oracle boundary and ownership | `S1` | read-only boundary snapshot blocker-free |
| Raw upload + managed sort | `S2` | upload/sort receipts + parity report blocker-free |
| Required outputs + manifest readability | `S3` | required-output matrix blocker-free |
| Stream-view contract/materialization | `S4` | stream-view contract snapshot blocker-free |
| P3 rollup + verdict | `S5` | deterministic verdict `ADVANCE_TO_P4` |

## 6) Stress Topology (M5.P3)
1. Component sequence:
   - `P3.A` boundary/ownership,
   - `P3.A1` raw upload + managed sort,
   - `P3.B` required outputs + manifests,
   - `P3.C` stream-view contract,
   - `P3.D` rollup verdict.
2. Plane sequence:
   - `oracle_boundary_plane`,
   - `oracle_materialization_plane`,
   - `oracle_rollup_plane`.
3. Integrated windows:
   - `m5p3_s1_boundary_window`,
   - `m5p3_s2_upload_sort_window`,
   - `m5p3_s3_output_manifest_window`,
   - `m5p3_s4_contract_window`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M5P3-ST-S0` - Authority and entry-gate closure
Objective:
1. validate M5.P3 can run with complete authority and valid parent M5 activation.

Actions:
1. validate required M5.P3 handles and placeholder guards.
2. validate parent M5 handoff and M4->M5 dependency chain are readable and pass.
3. validate managed-sort path constraints (`managed_distributed`, no local sort).
4. emit Stage-A findings + lane matrix + blocker register.

Pass gate:
1. required handles complete/non-placeholder.
2. managed-sort path is pinned and local-sort is disallowed.
3. entry dependency artifacts readable and valid.

### 7.2 `M5P3-ST-S1` - Oracle source boundary and ownership
Objective:
1. prove oracle boundary remains read-only and ownership semantics are intact.

Actions:
1. resolve boundary/namespace handles and prefix patterns.
2. enforce read-only posture for platform runtime on oracle source.
3. verify boundary isolation versus evidence/archive/quarantine roots.
4. emit `m5p3_oracle_boundary_snapshot` evidence set.

Pass gate:
1. boundary and ownership checks are blocker-free.
2. boundary snapshot artifacts are complete and readable.

### 7.3 `M5P3-ST-S2` - Raw upload and managed distributed sort
Objective:
1. validate raw-upload contract and managed sort contract for active oracle source.

Actions:
1. validate raw upload receipt/parity evidence for active source namespace/run-id.
2. validate managed sort trigger/terminal-state receipt and required output receipt surfaces.
3. fail if managed sort receipt is missing, non-terminal-success, or parity is drifted.
4. emit `m5p3_upload_sort_snapshot` evidence set.

Pass gate:
1. raw upload and managed sort receipts are readable and pass.
2. parity/readback checks are blocker-free.
3. no local-sort fallback signal exists.

### 7.4 `M5P3-ST-S3` - Required outputs and manifest readability
Objective:
1. validate required output surfaces and manifests for all required output IDs.

Actions:
1. parse required output list and enforce deterministic set integrity.
2. for each output ID verify stream-view prefix presence and manifest readability.
3. emit required-output matrix and blocker register.

Pass gate:
1. all required outputs present and readable.
2. manifest checks pass for every required output ID.
3. matrix and blocker register are consistent.

### 7.5 `M5P3-ST-S4` - Stream-view contract and materialization
Objective:
1. validate stream-view contract conformance and materialization correctness.

Actions:
1. validate sort-key contract by output ID from manifests and handle map.
2. validate non-empty materialization for required outputs.
3. run sampled readability/order checks and publish contract snapshot.

Pass gate:
1. stream-view contract checks pass for required outputs.
2. materialization/readability checks are blocker-free.

### 7.6 `M5P3-ST-S5` - P3 rollup and deterministic verdict
Objective:
1. emit deterministic P3 verdict for P4 entry.

Actions:
1. aggregate S1..S4 artifacts and blocker registers.
2. enforce blocker-consistent verdict rule.
3. emit verdict:
   - `ADVANCE_TO_P4` only when all blockers are closed,
   - otherwise `HOLD_REMEDIATE` or `NO_GO_RESET_REQUIRED`.

Pass gate:
1. no open non-waived `M5P3-B*` blockers.
2. verdict equals `ADVANCE_TO_P4`.
3. required artifacts are complete/readable.

## 8) Blocker Taxonomy (M5.P3)
1. `M5P3-B1`: required oracle handles missing/inconsistent.
2. `M5P3-B2`: oracle source boundary/ownership drift.
3. `M5P3-B3`: required output prefix/manifest missing.
4. `M5P3-B4`: stream-view contract/materialization failure.
5. `M5P3-B5`: rollup matrix/register inconsistency.
6. `M5P3-B6`: deterministic verdict build failure.
7. `M5P3-B7`: durable publish/readback failure.
8. `M5P3-B8`: advance verdict emitted despite unresolved blockers.
9. `M5P3-B9`: raw-upload contract failure/incomplete input staging.
10. `M5P3-B10`: managed stream-sort execution/receipt failure.
11. `M5P3-B11`: stream-sort parity/readback mismatch.

Any open `M5P3-B*` blocks P3 closure and blocks P4 transition.

## 9) Evidence Contract (M5.P3)
Required artifacts for each M5.P3 stage:
1. `m5p3_stagea_findings.json`
2. `m5p3_lane_matrix.json`
3. `m5p3_probe_latency_throughput_snapshot.json`
4. `m5p3_control_rail_conformance_snapshot.json`
5. `m5p3_secret_safety_snapshot.json`
6. `m5p3_cost_outcome_receipt.json`
7. `m5p3_blocker_register.json`
8. `m5p3_execution_summary.json`
9. `m5p3_decision_log.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M5.P3 stress authority created.
- [x] P3 staged runbook (`S0..S5`) pinned with fail-closed transitions.
- [x] P3 blocker taxonomy and evidence contract pinned.
- [x] M5.P3 S0 executed with blocker-free entry closure.
- [ ] P3 verdict `ADVANCE_TO_P4` emitted from blocker-free rollup.

## 11) Immediate Next Actions
1. Execute `M5P3-ST-S1` oracle source boundary and ownership checks.
2. Preserve managed-sort-only posture and reject local-sort fallback.
3. Do not enter `M5P3-ST-S2` until `S1` closes blocker-free.

## 12) Execution Progress
### `M5P3-ST-S0` authority/entry-gate closure execution (2026-03-03)
1. Phase execution id: `m5p3_stress_s0_20260303T233332Z`.
2. Runner:
   - `python scripts/dev_substrate/m5p3_stress_runner.py --stage S0`
3. Verification summary:
   - parent dependency loaded from latest successful `M5-ST-S0` (`m5_stress_s0_20260303T232628Z`),
   - required M5.P3 plan keys + handles passed placeholder guard,
   - managed-sort path law checks passed (`managed_distributed`, `EMR_SERVERLESS_SPARK`, local fallback disabled),
   - P3 and parent authority files were present/readable.
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M5P3_ST_S1_READY`,
   - `open_blockers=0`,
   - `probe_count=1`,
   - `error_rate_pct=0.0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5p3_stress_s0_20260303T233332Z/stress/m5p3_decision_log.json`
