# Dev Substrate Deep Plan - M5.P3 (P3 ORACLE_READY)
_Parent phase: `platform.M5.build_plan.md`_
_Last updated: 2026-02-24_

## 0) Purpose
This document carries execution-grade planning for M5 `P3 ORACLE_READY`.

P3 must prove:
1. oracle source boundary is read-only to platform runtime,
2. required output_id surfaces are present and readable,
3. stream-view materialization and contract checks pass fail-closed,
4. deterministic P3 verdict is emitted for M5.P4 entry.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P3`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (oracle handles + required outputs/sort keys)
4. `runs/dev_substrate/dev_full/m4/m4j_20260224T064802Z/m5_handoff_pack.json`

## 2) P3 Work Breakdown

### P3.A (M5.B) Oracle Source Boundary and Ownership
Goal:
1. prove oracle-store boundary and ownership posture match pinned dev_full model.

Tasks:
1. verify source handles:
   - `ORACLE_STORE_*`,
   - `S3_ORACLE_*`,
   - `S3_STREAM_VIEW_*`,
   - `ORACLE_INLET_*`.
2. verify active oracle prefixes are under `oracle-store/` namespace and not under platform evidence/archive roots.
3. verify platform runtime posture is read-only for oracle source paths.
4. emit `m5b_oracle_boundary_snapshot.json`.

DoD:
- [ ] oracle source boundary is explicit and valid.
- [ ] platform write-deny/read-only posture is explicit.
- [ ] snapshot committed locally and durably.

P3.A precheck:
1. M4 verdict is `ADVANCE_TO_M5`.
2. oracle source namespace/run-id handles are pinned.
3. oracle seating law remains intact (source-of-stream outside platform ownership).

### P3.B (M5.C) Required Outputs + Manifest Readability
Goal:
1. prove required output set is present/readable for current oracle source.

Tasks:
1. load `ORACLE_REQUIRED_OUTPUT_IDS`.
2. for each output_id, verify:
   - stream-view prefix exists,
   - manifest exists/readable at `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`.
3. build `m5c_required_output_matrix.json` with pass/fail per output.

DoD:
- [ ] all required outputs are present.
- [ ] all required manifests are readable.
- [ ] output matrix committed locally and durably.

P3.B precheck:
1. P3.A is green.
2. required output list is non-empty and deterministic.

### P3.C (M5.D) Stream-View Contract and Materialization
Goal:
1. validate stream-view contract for required outputs fail-closed.

Tasks:
1. validate sort-key contract for required outputs using:
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
   - `ORACLE_SORT_KEY_ACTIVE_SCOPE`.
2. validate chunk/materialization presence per required output.
3. validate schema/readability of sampled stream-view objects.
4. emit `m5d_stream_view_contract_snapshot.json`.

DoD:
- [ ] sort-key and active-scope checks pass.
- [ ] materialization checks pass.
- [ ] contract snapshot committed locally and durably.

P3.C precheck:
1. P3.B required-output matrix is green.
2. sort-key map is pinned for all required outputs.

### P3.D (M5.E) P3 Gate Rollup + Verdict
Goal:
1. adjudicate P3 gate and emit deterministic transition verdict.

Tasks:
1. roll up P3.A..P3.C checks into matrix.
2. build blocker register with explicit unresolved set.
3. emit deterministic verdict artifact:
   - `ADVANCE_TO_P4`, `HOLD_REMEDIATE`, `NO_GO_RESET_REQUIRED`.
4. emit P3 execution summary artifact.

DoD:
- [ ] P3 rollup matrix committed.
- [ ] unresolved blockers explicit.
- [ ] deterministic verdict artifact committed locally and durably.

P3.D precheck:
1. P3.A..P3.C artifacts exist and are readable.
2. blocker taxonomy is pinned and explicit.

## 3) P3 Verification Catalog
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `P3-V1-HANDLE-CLOSURE` | `rg -n \"ORACLE_STORE_|S3_ORACLE_|S3_STREAM_VIEW_|ORACLE_REQUIRED_OUTPUT_IDS|ORACLE_SORT_KEY_BY_OUTPUT_ID\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | verifies required oracle handle presence |
| `P3-V2-BOUNDARY-CHECK` | build oracle boundary snapshot from handle resolution + prefix checks | validates source-of-stream posture |
| `P3-V3-OUTPUT-MATRIX` | enumerate required output_id prefixes/manifests and emit matrix | validates required output presence |
| `P3-V4-CONTRACT-CHECK` | validate sort/materialization/readability and emit contract snapshot | validates stream-view contract |
| `P3-V5-ROLLUP-VERDICT` | build P3 rollup + blocker register + verdict | emits deterministic P3 gate result |
| `P3-V6-DURABLE-PUBLISH` | `aws s3 cp <artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/...` | commits durable P3 evidence |

## 4) P3 Blocker Taxonomy (Fail-Closed)
1. `M5P3-B1`: required oracle handles missing/inconsistent.
2. `M5P3-B2`: oracle source boundary/ownership drift.
3. `M5P3-B3`: required output prefix/manifest missing.
4. `M5P3-B4`: stream-view contract/materialization failure.
5. `M5P3-B5`: rollup matrix/register inconsistency.
6. `M5P3-B6`: deterministic verdict build failure.
7. `M5P3-B7`: durable publish/readback failure.
8. `M5P3-B8`: advance verdict emitted despite unresolved blockers.

## 5) P3 Evidence Contract
1. `m5b_oracle_boundary_snapshot.json`
2. `m5c_required_output_matrix.json`
3. `m5d_stream_view_contract_snapshot.json`
4. `m5e_p3_gate_rollup_matrix.json`
5. `m5e_p3_blocker_register.json`
6. `m5e_p3_gate_verdict.json`
7. `m5e_execution_summary.json`

## 6) Exit Rule for P3
P3 can close only when:
1. all `M5P3-B*` blockers are resolved,
2. all P3 DoDs are green,
3. P3 evidence exists locally and durably,
4. verdict is deterministic and blocker-consistent.

Transition:
1. P4 is blocked until P3 verdict is `ADVANCE_TO_P4`.
