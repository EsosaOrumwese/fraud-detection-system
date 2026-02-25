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
- [x] oracle source boundary is explicit and valid.
- [x] platform write-deny/read-only posture is explicit.
- [x] snapshot committed locally and durably.

P3.A precheck:
1. M4 verdict is `ADVANCE_TO_M5`.
2. oracle source namespace/run-id handles are pinned.
3. oracle seating law remains intact (source-of-stream outside platform ownership).

P3.A capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Authority + handle integrity | `ORACLE_STORE_*`, `S3_ORACLE_*`, `S3_STREAM_VIEW_*`, `ORACLE_INLET_*` | resolve handle set and validate non-empty/non-placeholder values | any required handle missing/inconsistent |
| Namespace and boundary isolation | `S3_ORACLE_ROOT_PREFIX`, `S3_EVIDENCE_ROOT_PREFIX`, archive/quarantine prefixes | prove oracle prefixes remain under `oracle-store/` and do not overlap evidence/archive/quarantine roots | overlap or namespace drift detected |
| Ownership semantics | `ORACLE_STORE_PLATFORM_ACCESS_MODE`, `ORACLE_STORE_WRITE_OWNER`, `ORACLE_INLET_PLATFORM_OWNERSHIP` | enforce read-only platform posture and external producer ownership | ownership contradiction or implicit platform write ownership |
| Runtime write-deny posture | policy + runtime path selection evidence | verify no active write path to oracle source namespace for this phase execution | any active write-capable path to oracle prefix |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local artifact emission + durable publish/readback | local-only artifact or durable publish/readback failure |
| Blocker adjudication | P3.A scoped blocker register | every unresolved check classified before transition | unresolved issue without blocker classification |

P3.A verification command templates (operator lane):
1. Handle presence:
   - `rg -n "ORACLE_STORE_|S3_ORACLE_|S3_STREAM_VIEW_|ORACLE_INLET_" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
2. Oracle prefix and namespace isolation:
   - `aws s3api list-objects-v2 --bucket <ORACLE_STORE_BUCKET> --prefix <S3_ORACLE_ROOT_PREFIX> --max-items 10`
   - `aws s3api list-objects-v2 --bucket <S3_EVIDENCE_BUCKET> --prefix <S3_EVIDENCE_ROOT_PREFIX> --max-items 10`
3. Overlap/drift check:
   - assert oracle root does not start with any evidence/archive/quarantine root token.
   - assert `ORACLE_STORE_BUCKET` is the canonical external oracle bucket for the track and is not an ad-hoc duplicate copy target.
4. Ownership/read-only check:
   - assert `ORACLE_STORE_PLATFORM_ACCESS_MODE == read_only`.
   - assert `ORACLE_STORE_WRITE_OWNER != platform_runtime`.
5. Runtime write-path posture check:
   - verify active runtime path selection artifact for phase run does not include oracle write lanes.
6. Durable publish/readback:
   - `aws s3 cp <local_m5b_oracle_boundary_snapshot.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5b_oracle_boundary_snapshot.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5b_oracle_boundary_snapshot.json`

P3.A scoped blocker mapping (must be explicit before transition):
1. `P3A-B1` -> `M5P3-B1`: required oracle handle missing/inconsistent.
2. `P3A-B2` -> `M5P3-B2`: oracle namespace/boundary overlap drift.
3. `P3A-B3` -> `M5P3-B2`: ownership/read-only semantics violation.
4. `P3A-B4` -> `M5P3-B2`: runtime write-deny posture violation for oracle source.
5. `P3A-B5` -> `M5P3-B7`: durable publish/readback failure.
6. `P3A-B6` -> `M5P3-B8`: transition attempted with unresolved `P3A-B*`.

P3.A exit rule:
1. all capability lanes above are `PASS`,
2. `m5b_oracle_boundary_snapshot.json` exists locally and durably,
3. no active `P3A-B*` blocker remains,
4. P3.B remains blocked until P3.A pass is explicit in rollup evidence.

P3.A execution closure (2026-02-24):
1. First attempt `m5b_20260224T184949Z` was invalidated:
   - PowerShell inline expression bug prevented clean check rendering in the first execution command.
2. Authoritative rerun:
   - execution id: `m5b_20260224T185046Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5b_20260224T185046Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5b_20260224T185046Z/m5b_execution_summary.json`
   - result: `overall_pass=true`, `blocker_count=0`.
3. Durable evidence (PASS):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5b_20260224T185046Z/m5b_oracle_boundary_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5b_20260224T185046Z/m5b_blocker_register.json`
4. Invalidated attempt marker:
   - `runs/dev_substrate/dev_full/m5/m5b_20260224T184949Z/INVALIDATED.txt`

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
- [x] all required outputs are present.
- [x] all required manifests are readable.
- [x] output matrix committed locally and durably.

P3.B precheck:
1. P3.A is green.
2. required output list is non-empty and deterministic.

P3.B capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Required output contract integrity | `ORACLE_REQUIRED_OUTPUT_IDS` | parse pinned output list and validate non-empty + deterministic (no duplicates) | missing/empty/non-deterministic required output list |
| Stream-view output surface presence | `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`, `ORACLE_SOURCE_NAMESPACE`, `ORACLE_ENGINE_RUN_ID` | for each required output_id, resolve prefix and prove object presence | any required output prefix missing/empty |
| Manifest readability | `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN` | for each required output_id, resolve manifest key and prove readable object | any required manifest missing/unreadable |
| Matrix integrity + blocker adjudication | `m5c_required_output_matrix.json`, `m5c_blocker_register.json` | emit per-output pass/fail matrix and explicit blockers | unresolved failure without blocker mapping |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local artifacts plus durable publish/readback | local-only artifacts or durable publish/readback failure |

P3.B verification command templates (operator lane):
1. Required output list presence:
   - `rg -n "ORACLE_REQUIRED_OUTPUT_IDS|S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN|S3_STREAM_VIEW_MANIFEST_KEY_PATTERN" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
2. Prefix presence per output:
   - `aws s3api list-objects-v2 --bucket <ORACLE_STORE_BUCKET> --prefix <resolved_output_prefix> --max-keys 1`
3. Manifest readability per output:
   - `aws s3api head-object --bucket <ORACLE_STORE_BUCKET> --key <resolved_manifest_key>`
4. Durable matrix publish:
   - `aws s3 cp <local_m5c_required_output_matrix.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5c_required_output_matrix.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5c_required_output_matrix.json`

P3.B scoped blocker mapping (must be explicit before transition):
1. `P3B-B1` -> `M5P3-B1`: required output/stream-view handles missing or unresolved.
2. `P3B-B2` -> `M5P3-B3`: required output prefix missing/empty.
3. `P3B-B3` -> `M5P3-B3`: required manifest missing/unreadable.
4. `P3B-B4` -> `M5P3-B5`: output matrix/register inconsistency.
5. `P3B-B5` -> `M5P3-B7`: durable publish/readback failure.
6. `P3B-B6` -> `M5P3-B8`: transition attempted with unresolved `P3B-B*`.

P3.B exit rule:
1. all required outputs in `ORACLE_REQUIRED_OUTPUT_IDS` are present,
2. all required manifests are readable,
3. `m5c_required_output_matrix.json` exists locally and durably,
4. no active `P3B-B*` blocker remains,
5. P3.C remains blocked until P3.B pass is explicit in rollup evidence.

P3.B execution closure (2026-02-24):
1. Initial fail-closed run (pre-remediation baseline):
   - execution id: `m5c_20260224T190532Z`
   - result: `overall_pass=false`, blockers `P3B-B2/P3B-B3` (no outputs/manifests in dev-full oracle path at that time).
2. Remediation applied:
   - materialized required output prefixes from authoritative dev-min oracle source into pinned dev-full oracle source path.
3. Probe-fix note:
   - one interim rerun used `--max-items` for prefix probe and produced false-negative prefix checks;
   - non-authoritative run folder was pruned and probe contract corrected to `--max-keys`.
4. Authoritative pass run:
   - execution id: `m5c_p3b_required_outputs_20260224T191554Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5c_p3b_required_outputs_20260224T191554Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5c_p3b_required_outputs_20260224T191554Z/m5c_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, prefix presence `4/4`, manifest readability `4/4`.
5. Durable evidence (authoritative pass):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_required_output_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_execution_summary.json`
6. Gate impact:
   - P3.B is green; P3.C (`M5.D`) is unblocked.

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
- [x] sort-key and active-scope checks pass.
- [x] materialization checks pass.
- [x] contract snapshot committed locally and durably.

P3.C precheck:
1. P3.B required-output matrix is green.
2. sort-key map is pinned for all required outputs.

P3.C capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Active sort-key contract integrity | `ORACLE_SORT_KEY_BY_OUTPUT_ID`, `ORACLE_SORT_KEY_ACTIVE_SCOPE`, `ORACLE_REQUIRED_OUTPUT_IDS` | resolve active required outputs and required sort key per output | missing active sort-key mapping for any required output |
| Manifest sort-key conformance | `_stream_view_manifest.json` per required output | verify required sort key exists in manifest `sort_keys` and is leading key for active scope | manifest sort key absent/mismatched |
| Materialization completeness | stream-view output prefix parquet parts | verify each required output has at least one parquet part | empty/missing parquet materialization |
| Schema/readability contract | sampled parquet parts per required output | verify parquet readable, required sort-key columns exist, and sampled ordering is non-decreasing on active sort key | unreadable parquet, missing key columns, or sample ordering violation |
| Contract snapshot + blocker register consistency | `m5d_stream_view_contract_snapshot.json`, `m5d_blocker_register.json` | emit per-output checks and explicit blockers | unresolved failure without blocker mapping |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local + durable publish/readback | durable publish/readback failure |

P3.C verification command templates (operator lane):
1. Active sort-key mapping:
   - `rg -n "ORACLE_REQUIRED_OUTPUT_IDS|ORACLE_SORT_KEY_BY_OUTPUT_ID|ORACLE_SORT_KEY_ACTIVE_SCOPE" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
2. Materialization surface:
   - `aws s3api list-objects-v2 --bucket <ORACLE_STORE_BUCKET> --prefix <resolved_output_prefix> --max-keys 5`
3. Manifest sort-key check:
   - `aws s3 cp s3://<ORACLE_STORE_BUCKET>/<resolved_manifest_key> -`
4. Sample readability check:
   - read sampled parquet parts and validate key-column presence + sampled non-decreasing order for active sort key.
5. Durable snapshot publish:
   - `aws s3 cp <local_m5d_stream_view_contract_snapshot.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5d_stream_view_contract_snapshot.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5d_stream_view_contract_snapshot.json`

P3.C scoped blocker mapping (must be explicit before transition):
1. `P3C-B1` -> `M5P3-B1`: required sort-key handles missing/inconsistent.
2. `P3C-B2` -> `M5P3-B4`: manifest sort-key contract mismatch.
3. `P3C-B3` -> `M5P3-B4`: stream-view materialization missing/empty.
4. `P3C-B4` -> `M5P3-B4`: sampled schema/readability/order contract failure.
5. `P3C-B5` -> `M5P3-B7`: durable publish/readback failure.
6. `P3C-B6` -> `M5P3-B8`: transition attempted with unresolved `P3C-B*`.

P3.C exit rule:
1. active sort-key checks pass for all required outputs,
2. materialization completeness checks pass for all required outputs,
3. sampled readability/order checks pass for all required outputs,
4. `m5d_stream_view_contract_snapshot.json` exists locally and durably,
5. no active `P3C-B*` blocker remains,
6. P3.D remains blocked until P3.C pass is explicit in rollup evidence.

P3.C execution closure (2026-02-24):
1. First attempt:
   - failed due Windows temp-file handle lock during sampled parquet cleanup (`WinError 32`);
   - no authoritative artifacts emitted; empty run folder pruned.
2. Remediation:
   - switched sampled parquet handling to explicit temp-file close/delete strategy,
   - reran full P3.C end-to-end.
3. Authoritative run:
   - execution id: `m5d_p3c_stream_view_contract_20260224T192457Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5d_p3c_stream_view_contract_20260224T192457Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_execution_summary.json`
4. Result:
   - `overall_pass=true`
   - blockers: `[]`
   - outputs with materialization: `4/4`
   - outputs with manifest primary sort-key match: `4/4`
   - outputs with sampled schema/readability/order contract pass: `4/4`
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_stream_view_contract_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_execution_summary.json`
6. Gate impact:
   - P3.C is green; P3.D (`M5.E`) is unblocked.

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
- [x] P3 rollup matrix committed.
- [x] unresolved blockers explicit.
- [x] deterministic verdict artifact committed locally and durably.

P3.D precheck:
1. P3.A..P3.C artifacts exist and are readable.
2. blocker taxonomy is pinned and explicit.

P3.D capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Upstream artifact closure | `m5b_execution_summary.json`, `m5c_execution_summary.json`, `m5d_execution_summary.json` | resolve authoritative upstream summaries and confirm readability | missing/unreadable upstream summary artifact |
| Upstream blocker closure | upstream `active_blocker_codes` from P3.A..P3.C | require all upstream lanes `overall_pass=true` and blocker-free | unresolved upstream blocker in any P3 lane |
| Rollup matrix consistency | `m5e_p3_gate_rollup_matrix.json` | emit deterministic lane matrix with source refs and pass/fail adjudication | matrix missing lane or inconsistent with source summaries |
| Verdict determinism | `m5e_p3_gate_verdict.json` | derive verdict from blocker-consistent rule (`ADVANCE_TO_P4` only when blocker-free) | verdict contradicts blocker state |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local + durable publish/readback of rollup artifacts | durable publish/readback failure |

P3.D verification command templates (operator lane):
1. Upstream summaries:
   - `cat runs/dev_substrate/dev_full/m5/<m5b_id>/m5b_execution_summary.json`
   - `cat runs/dev_substrate/dev_full/m5/<m5c_id>/m5c_execution_summary.json`
   - `cat runs/dev_substrate/dev_full/m5/<m5d_id>/m5d_execution_summary.json`
2. Verdict consistency check:
   - require `ADVANCE_TO_P4` iff blocker set is empty.
3. Durable publish/readback:
   - `aws s3 cp <local_m5e_p3_gate_verdict.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5e_p3_gate_verdict.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5e_p3_gate_verdict.json`

P3.D scoped blocker mapping (must be explicit before transition):
1. `P3D-B1` -> `M5P3-B5`: upstream P3 artifact missing/unreadable.
2. `P3D-B2` -> `M5P3-B5`: unresolved upstream blocker propagated into rollup.
3. `P3D-B3` -> `M5P3-B6`: deterministic verdict build failure.
4. `P3D-B4` -> `M5P3-B7`: durable publish/readback failure.
5. `P3D-B5` -> `M5P3-B8`: transition attempted with unresolved `P3D-B*`.

P3.D exit rule:
1. P3.A..P3.C upstream summaries are resolved and blocker-free,
2. `m5e_p3_gate_rollup_matrix.json` exists and is source-consistent,
3. `m5e_p3_gate_verdict.json` is deterministic and blocker-consistent,
4. P3 rollup artifacts exist locally and durably,
5. no active `P3D-B*` blocker remains,
6. P4 remains blocked until verdict is explicitly `ADVANCE_TO_P4`.

P3.D execution closure (2026-02-25):
1. Authoritative run:
   - execution id: `m5e_p3_gate_rollup_20260225T005034Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5e_p3_gate_rollup_20260225T005034Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5e_p3_gate_rollup_20260225T005034Z/m5e_execution_summary.json`
2. Rollup outcome:
   - `overall_pass=true`
   - `lane_count=3`, `lanes_passed=3`
   - blocker codes: `[]`
3. Verdict:
   - `ADVANCE_TO_P4`
   - next gate: `P4_READY`
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_gate_rollup_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_gate_verdict.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_execution_summary.json`
5. Gate impact:
   - P3 is closed green and P4 (`M5.F+`) is unblocked.

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
