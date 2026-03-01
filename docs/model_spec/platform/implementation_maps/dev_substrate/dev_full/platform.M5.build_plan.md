# Dev Substrate Deep Plan - M5 (P3 ORACLE_READY + P4 INGEST_READY)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M5._
_Last updated: 2026-02-28_

## 0) Purpose
M5 closes:
1. `P3 ORACLE_READY` (oracle source + stream-view contract readiness).
2. `P4 INGEST_READY` (ingress boundary + MSK topic + envelope preflight readiness).

M5 must prove:
1. oracle source-of-stream posture is read-only from platform runtime and contract-valid,
2. oracle raw inputs are uploaded to S3 under canonical oracle input prefix and stream-view is produced by managed distributed sort (no local sort path),
3. required stream-view outputs are present and pass manifest/materialization checks,
4. ingest edge boundary (health + auth + bus topics + envelope controls) is ready fail-closed,
5. P3/P4 gate verdicts and M6 handoff are deterministic and auditable,
6. M5 phase-budget and cost-outcome posture is explicit and pass-gated.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P3`, `P4` sections)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M4.build_plan.md`
2. `runs/dev_substrate/dev_full/m4/m4j_20260224T064802Z/m5_handoff_pack.json`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M5
In scope:
1. P3 oracle readiness closure:
   - source boundary checks,
   - raw upload to canonical oracle input prefix,
   - managed distributed stream-sort execution + receipt,
   - required output presence,
   - stream-view/manifest contract checks.
2. P4 ingress readiness closure:
   - IG boundary health and auth checks,
   - MSK topic readiness checks,
   - ingress envelope controls (payload/timeout/retry/idempotency/DLQ/replay/rate limits).
3. P3/P4 gate rollups and deterministic verdict artifacts.
4. M6 entry handoff publication.

Out of scope:
1. READY publication and streaming activation (`M6`, `P5+`).
2. RTDL/decision/case-label closures (`M7+`).
3. Learning/evolution closures (`M9+`).

## 3) Deliverables
1. P3 readiness artifacts and gate verdict.
2. P4 readiness artifacts and gate verdict.
3. M5 execution summary (phase-level verdict).
4. M6 handoff pack with deterministic references.

## 4) Entry Gate and Current Posture
Entry gate for M5:
1. M4 is `DONE` with verdict `ADVANCE_TO_M5`.

Current posture:
1. M4 closure is complete (`m4j_20260224T064802Z`).
2. M5 planning is being expanded before any execution.

Initial pre-execution blockers (fail-closed, now closed by planning expansion):
1. `M5-B0`: M5 deep plan/capability-lane incompleteness.
2. `M5-B0.1`: P3/P4 execution decomposition not explicit.

## 4.1) Anti-Cram Law (Binding for M5)
M5 is not execution-ready unless these capability lanes are explicit:
1. authority and handles,
2. oracle source boundary and ownership,
3. oracle required outputs and stream-view contract checks,
4. ingress boundary health and auth contract,
5. MSK topic readiness and bus contract,
6. ingress envelope controls,
7. durable evidence publication,
8. blocker adjudication and M6 handoff,
9. phase-budget and cost-outcome gating.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M5.A | no unresolved required P3/P4 handles |
| Oracle source boundary + ownership | M5.B | read-only platform posture proof |
| Oracle raw upload + managed sort | M5.R1 | raw upload receipt + managed sort receipt + parity report |
| Required outputs + manifest readability | M5.C | required-output matrix pass |
| Stream-view contract + materialization | M5.D | stream-view contract snapshot pass |
| P3 gate rollup + verdict | M5.E | blocker-free P3 verdict artifact |
| Ingress boundary health | M5.F | ingest + ops health snapshot pass |
| Boundary auth enforcement | M5.G | auth posture/enforcement snapshot pass |
| MSK topic readiness | M5.H | topic readiness snapshot pass |
| Ingress envelope controls | M5.I | envelope conformance snapshot pass |
| P4 verdict + M6 handoff | M5.J | blocker-free P4 verdict + durable `m6_handoff_pack.json` |
| Cost-outcome guardrail | M5.J | `phase_budget_envelope.json` + `phase_cost_outcome_receipt.json` pass |

## 5) Work Breakdown (Orchestration)

### M5.A Authority + Handle Closure (P3/P4)
Goal:
1. close required M5 handles before oracle/ingress actions.

Tasks:
1. resolve required P3 handles:
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
   - `S3_ORACLE_*` and `S3_STREAM_VIEW_*` patterns.
2. resolve required P4 handles:
   - `IG_*` boundary/auth/envelope handles,
   - `MSK_*` cluster/topic handles.
3. resolve required M5 evidence handles for P3/P4 gate snapshots and M6 handoff.
4. classify unresolved required handles as blockers.

DoD:
- [x] required M5 handle set is explicit and complete.
- [x] every required handle has a verification method.
- [x] unresolved required handles are blocker-marked.
- [x] M5.A closure snapshot exists locally and durably.

M5.A execution closure (2026-02-24):
1. First attempt `m5a_20260224T182348Z` was invalidated:
   - registry quoted values (for example `S3_EVIDENCE_BUCKET`) were not normalized before AWS CLI usage,
   - native command non-zero handling was not strict.
2. Authoritative rerun (fail-closed, corrected):
   - execution id: `m5a_20260224T182433Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5a_20260224T182433Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5a_20260224T182433Z/m5a_execution_summary.json`
   - result: `overall_pass=true`, `blocker_count=0`, required handles checked=`51`.
3. Durable evidence (PASS):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5a_20260224T182433Z/m5a_handle_closure_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5a_20260224T182433Z/m5a_blocker_register.json`
4. Invalidated attempt marker:
   - `runs/dev_substrate/dev_full/m5/m5a_20260224T182348Z/INVALIDATED.txt`

### M5.B Oracle Source Boundary and Ownership
Goal:
1. prove platform runtime uses oracle store as read-only source-of-stream boundary.

Tasks:
1. validate oracle source namespace/run-id handles and active prefixes.
2. validate platform runtime write-deny posture for oracle source paths.
3. validate oracle inlet mode boundary (`external_raw_upload_then_managed_sort`) and ownership.
4. validate oracle bucket binding posture:
   - `ORACLE_STORE_BUCKET` resolves to the canonical dev_full oracle source bucket,
   - no cross-track copy lane is used for active oracle refresh.
5. publish oracle boundary posture snapshot.

DoD:
- [x] oracle boundary posture is explicit and read-only.
- [x] ownership posture is explicit and producer-owned.
- [x] oracle boundary snapshot is committed locally and durably.

### M5.R Oracle Refresh Reopen Lane (Required Before Next P3 Certification)
This lane is mandatory for the repinned oracle source (`local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`) and must run before any new P3 closure claim.

Execution sequence:
1. `M5.R1`: high-throughput full-tree mirror upload from local source root to canonical oracle-store run prefix.
2. `M5.R2`: trigger managed distributed stream-sort (`ORACLE_STREAM_SORT_ENGINE`).
3. `M5.R3`: verify stream-view manifests, readback, and object-count parity.
4. `M5.R4`: issue refreshed P3 rollup/verdict from refreshed evidence set.

DoD (reopen lane):
- [x] raw upload receipt exists locally and durably.
- [ ] managed stream-sort receipt exists locally and durably.
- [ ] parity report confirms manifest/readback/object-count consistency for full oracle source tree and required outputs.
- [ ] refreshed P3 verdict is emitted from refreshed evidence artifacts (no reuse of legacy copy-remediation evidence).

#### M5.R1 Execution Expansion (Raw Upload)
Goal:
1. mirror the full local oracle run tree into canonical dev_full oracle-store prefix (no subset upload).

Pinned source root:
1. `runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/`
2. mirror scope is the full source tree exactly as present at execution time (no subset filtering, no assumed folder set).

Target prefix:
1. `s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/`

Execution steps:
1. verify pinned source root exists/readable and capture source tree inventory snapshot (top-level + recursive count/bytes).
2. clear existing target run prefix to remove stale/cluttered residue.
3. sync full source root to target run prefix with `aws s3 sync --delete`.
4. compute local object-count + byte totals across full tree.
5. compute S3 object-count + byte totals across full tree.
6. fail-closed on any parity mismatch.
7. publish lane artifacts:
   - `m5r1_raw_upload_receipt.json`
   - `m5r1_blocker_register.json`
   - `m5r1_execution_summary.json`
   - `m5r1_tree_parity_matrix.json`
8. upload artifacts to durable evidence prefix:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/<m5r1_execution_id>/oracle/`

M5.R1 DoD:
- [x] full source tree uploaded successfully (no subset-only upload).
- [x] local/S3 parity checks pass (count + bytes for full tree).
- [x] `m5r1_raw_upload_receipt.json` exists locally.
- [x] `m5r1_raw_upload_receipt.json` exists durably and readback passes.
- [x] blocker register is empty.

M5.R1 blocker map:
1. `M5R1-B1` -> `M5P3-B9`: source root missing/unreadable.
2. `M5R1-B2` -> `M5P3-B9`: full-tree upload command failure.
3. `M5R1-B3` -> `M5P3-B11`: local vs S3 parity mismatch for full tree.
4. `M5R1-B4` -> `M5P3-B7`: durable evidence publish/readback failure.
5. `M5R1-B5` -> `M5P3-B8`: attempted transition with unresolved blocker.

M5.R1 prior closure note (superseded by scope correction):
1. prior run `m5r1_raw_upload_20260301T004342Z` uploaded only `input/output_id=*` subset.
2. this does not satisfy the current authoritative instruction to mirror the full source tree.
3. re-execution `m5r1_full_tree_upload_20260301T073206Z` completed against full-tree contract with blocker-free parity.

M5.R1 authoritative closure (full-tree mirror):
1. execution id:
   - `m5r1_full_tree_upload_20260301T073206Z`
2. source and destination:
   - source: `runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/`
   - destination: `s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/`
3. parity results:
   - local: `11,465 files`, `92,622,942,077 bytes`
   - s3: `11,465 files`, `92,622,942,077 bytes`
4. lane verdict:
   - `overall_pass=true`, `blocker_count=0`, `next_gate=M5.R2_READY`
5. local artifacts:
   - `runs/dev_substrate/dev_full/m5/m5r1_full_tree_upload_20260301T073206Z/m5r1_raw_upload_receipt.json`
   - `runs/dev_substrate/dev_full/m5/m5r1_full_tree_upload_20260301T073206Z/m5r1_tree_parity_matrix.json`
   - `runs/dev_substrate/dev_full/m5/m5r1_full_tree_upload_20260301T073206Z/m5r1_blocker_register.json`
   - `runs/dev_substrate/dev_full/m5/m5r1_full_tree_upload_20260301T073206Z/m5r1_execution_summary.json`
6. durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5r1_full_tree_upload_20260301T073206Z/oracle/m5r1_raw_upload_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5r1_full_tree_upload_20260301T073206Z/oracle/m5r1_tree_parity_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5r1_full_tree_upload_20260301T073206Z/oracle/m5r1_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5r1_full_tree_upload_20260301T073206Z/oracle/m5r1_execution_summary.json`

#### M5.R2 Execution Expansion (Managed Distributed Stream-Sort)
Goal:
1. materialize stream-view outputs from the uploaded raw oracle inputs using managed compute (`EMR_EKS_SPARK`) and publish deterministic closure receipts.

Pinned runtime path for this lane:
1. `ORACLE_STREAM_SORT_EXECUTION_MODE=managed_distributed`
2. `ORACLE_STREAM_SORT_ENGINE=EMR_EKS_SPARK`
3. `ORACLE_STREAM_SORT_TRIGGER_SURFACE=github_actions_managed` (operator-run managed trigger)
4. `ORACLE_STREAM_SORT_RUNTIME_PATH=EMR_ON_EKS_SPARK`

Execution steps:
1. generate `m5r2_execution_id` and local run root under `runs/dev_substrate/dev_full/m5/<m5r2_execution_id>/`.
2. resolve and verify required handles before trigger:
   - `ORACLE_STORE_BUCKET`,
   - `ORACLE_SOURCE_NAMESPACE`,
   - `ORACLE_ENGINE_RUN_ID`,
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID`,
   - `EMR_EKS_VIRTUAL_CLUSTER_ID`,
   - `EMR_EKS_EXECUTION_ROLE_ARN`,
   - `ORACLE_STREAM_SORT_EMR_RELEASE_LABEL`,
   - `S3_EVIDENCE_BUCKET`.
3. submit EMR-on-EKS Spark job for stream-sort using pinned virtual cluster + execution role.
4. poll job state to terminal status; fail-closed on non-`COMPLETED` terminal states.
5. verify per required output under `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`:
   - parquet object presence (`>0`),
   - `_stream_sort_receipt.json` exists and `status=OK`,
   - `_stream_view_manifest.json` exists and is readable,
   - manifest/receipt output_id and stream_view_root are consistent.
6. build lane receipts:
   - `m5r2_stream_sort_receipt.json`,
   - `m5r2_stream_sort_parity_report.json`,
   - `m5r2_blocker_register.json`,
   - `m5r2_execution_summary.json`.
7. publish lane receipts to:
   - local run root,
   - `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5r2_execution_id>/oracle/`.

M5.R2 DoD:
- [ ] managed job reached terminal `COMPLETED`.
- [ ] required outputs `4/4` have parquet materialization under stream-view prefix.
- [ ] required receipts/manifests `4/4` are present and readable.
- [ ] local + durable `m5r2_stream_sort_receipt.json` exists with `overall_pass=true`.
- [ ] blocker register is empty.

M5.R2 blocker map:
1. `M5R2-B1` -> `M5P3-B1`: required handle missing/unresolved for managed trigger.
2. `M5R2-B2` -> `M5P3-B10`: EMR job submit/poll failed or terminal non-success state.
3. `M5R2-B3` -> `M5P3-B10`: required stream-view receipt missing/unreadable.
4. `M5R2-B4` -> `M5P3-B10`: required stream-view manifest missing/unreadable.
5. `M5R2-B5` -> `M5P3-B11`: output materialization parity mismatch/incomplete required output set.
6. `M5R2-B6` -> `M5P3-B7`: durable evidence publish/readback failed.
7. `M5R2-B7` -> `M5P3-B8`: attempted transition with unresolved `M5R2-B*`.

### M5.C Required Outputs and Manifest Readability (P3)
Goal:
1. prove all required outputs exist and are readable under oracle stream-view root.

Tasks:
1. enumerate required outputs from pinned handles.
2. verify output_id prefixes and object presence.
3. verify manifest readability for each required output.
4. publish required-output matrix.

DoD:
- [x] required outputs are present.
- [x] required manifests are readable.
- [x] required-output matrix is committed locally and durably.

M5.C execution closure (2026-02-24):
1. Baseline fail-closed run:
   - `runs/dev_substrate/dev_full/m5/m5c_20260224T190532Z/m5c_execution_summary.json`
   - outcome: `overall_pass=false`, blockers=`P3B-B2,P3B-B3`.
2. Remediation:
   - legacy (superseded) copy-remediation path copied required oracle stream-view output prefixes/manifests from dev-min source into dev-full oracle path.
   - this path is retained only as historical evidence and is not the active standard for future oracle refresh runs.
3. Probe-fix:
   - corrected prefix probe contract from `--max-items` to `--max-keys` to avoid false-negative prefix presence.
4. Authoritative green run:
   - `runs/dev_substrate/dev_full/m5/m5c_p3b_required_outputs_20260224T191554Z/m5c_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, `prefixes=4/4`, `manifests=4/4`.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_required_output_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_p3b_required_outputs_20260224T191554Z/m5c_execution_summary.json`
6. Prior fail evidence retained:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_20260224T190532Z/m5c_required_output_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_20260224T190532Z/m5c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5c_20260224T190532Z/m5c_execution_summary.json`
7. Next action:
   - advance to `M5.D` (`P3.C`) execution.

### M5.D Stream-View Contract and Materialization (P3)
Goal:
1. validate stream-view materialization contract fail-closed.

Tasks:
1. validate stream-view key ordering contract against pinned output sort keys.
2. validate chunk/materialization completeness for each required output.
3. validate schema/readability contract for stream-view slices.
4. publish stream-view contract snapshot.

DoD:
- [x] stream-view contract checks pass.
- [x] materialization completeness checks pass.
- [x] stream-view contract snapshot committed locally and durably.

M5.D execution closure (2026-02-24):
1. First attempt failed due verifier temp-file handle cleanup issue on Windows (`WinError 32`); empty folder pruned.
2. Authoritative rerun:
   - `runs/dev_substrate/dev_full/m5/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`.
3. Contract outcomes:
   - materialization: `4/4` required outputs have parquet parts,
   - manifest primary sort-key match: `4/4`,
   - sampled schema/readability/order contract pass: `4/4`.
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_stream_view_contract_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5d_p3c_stream_view_contract_20260224T192457Z/m5d_execution_summary.json`
5. Next action:
   - advance to `M5.E` (`P3.D`) rollup/verdict execution.

### M5.E P3 Gate Rollup + Verdict
Goal:
1. adjudicate P3 (`ORACLE_READY`) from M5.B..M5.D evidence.

Tasks:
1. build P3 gate rollup matrix.
2. build P3 blocker register.
3. emit deterministic P3 verdict artifact.
4. publish P3 artifacts locally and durably.

DoD:
- [x] P3 rollup matrix is complete.
- [x] unresolved blocker set is explicit.
- [x] deterministic P3 verdict artifact is committed.

M5.E execution closure (2026-02-25):
1. Authoritative run:
   - `runs/dev_substrate/dev_full/m5/m5e_p3_gate_rollup_20260225T005034Z/m5e_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, verdict=`ADVANCE_TO_P4`.
2. Rollup integrity:
   - lane count=`3`, lanes passed=`3` (`P3.A/P3.B/P3.C`).
3. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_gate_rollup_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_p3_gate_verdict.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5e_p3_gate_rollup_20260225T005034Z/m5e_execution_summary.json`
4. Next action:
   - advance to `M5.F` (`P4` ingress boundary health preflight).

### M5.F IG Boundary Health Preflight (P4)
Goal:
1. prove ingress boundary health at ops and ingest surfaces.

Tasks:
1. resolve authoritative ingest and health endpoints from handles.
2. run health probes for `/ops/health` and `/ingest/push` preflight path.
3. validate run-scope/correlation surface in boundary responses where applicable.
4. publish ingress boundary health snapshot.

DoD:
- [x] ingest and ops health endpoints are healthy.
- [x] boundary response contracts are readable and valid.
- [x] ingress boundary health snapshot committed locally and durably.

M5.F execution closure (2026-02-25):
1. Initial fail-closed run:
   - `runs/dev_substrate/dev_full/m5/m5f_p4a_ingress_boundary_health_20260225T005845Z/m5f_execution_summary.json`
   - outcome: `overall_pass=false`, blockers=`P4A-B2,P4A-B3`.
2. Root cause:
   - stale IG API handles (`APIGW_IG_API_ID/IG_BASE_URL`) pointed to deleted API edge.
3. Remediation:
   - repinned IG API handles in `dev_full_handles.registry.v0.md` to live API `5p7yslq6rc`.
4. Authoritative green run:
   - `runs/dev_substrate/dev_full/m5/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, ops=`200`, ingest=`202`.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_ingress_boundary_health_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_execution_summary.json`
6. Next action:
   - advance to `M5.G` (`P4.B` boundary auth enforcement).

### M5.G Boundary Auth Enforcement (P4)
Goal:
1. prove boundary auth contract is enforced as pinned.

Tasks:
1. verify auth mode and required header handles.
2. run positive auth preflight with valid key.
3. run negative auth preflight without/invalid key and require fail-closed behavior.
4. publish auth enforcement snapshot.

DoD:
- [x] auth contract handles are consistent.
- [x] positive and negative auth probes pass expected outcomes.
- [x] auth enforcement snapshot committed locally and durably.

M5.G execution closure (2026-02-25):
1. Pre-remediation drift was confirmed:
   - missing/invalid API-key requests were admitted at IG boundary.
2. Runtime remediation:
   - patched `infra/terraform/dev_full/runtime/lambda/ig_handler.py` with fail-closed auth enforcement,
   - materialized runtime env pins `IG_AUTH_MODE` and `IG_AUTH_HEADER_NAME`,
   - re-applied runtime Terraform stack (`aws_lambda_function.ig_handler` in-place update).
3. Authoritative green run:
   - `runs/dev_substrate/dev_full/m5/m5g_p4b_boundary_auth_20260225T011324Z/m5g_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, `next_gate=M5.H_READY`.
4. Probe contract outcomes:
   - valid key: health `200`, ingest `202`,
   - missing key: health `401`, ingest `401`,
   - invalid key: health `401`, ingest `401`.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_boundary_auth_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_execution_summary.json`
6. Next action:
   - advance to `M5.H` (`P4.C` MSK topic readiness).

### M5.H MSK Topic Readiness (P4)
Goal:
1. prove required ingress/control topics are ready and reachable.

Tasks:
1. validate MSK cluster/bootstrap handles and connectivity posture.
2. verify required topics exist and are writable/readable by intended producer/consumer identities.
3. publish topic readiness snapshot.

DoD:
- [x] required topics exist and are reachable.
- [x] topic ownership/readiness checks pass.
- [x] topic readiness snapshot committed locally and durably.

M5.H execution closure (2026-02-25):
1. Fail-closed baseline attempts were executed and preserved for audit:
   - `m5h_p4c_msk_topic_readiness_20260225T013103Z` (invoke race + stale MSK handle drift),
   - `m5h_p4c_msk_topic_readiness_20260225T014014Z` (private-subnet SSM reachability failure),
   - `m5h_p4c_msk_topic_readiness_20260225T014538Z` (Kafka admin API mismatch),
   - `m5h_p4c_msk_topic_readiness_20260225T014950Z` (create-topics response handling mismatch).
2. Remediation closure applied:
   - repinned stale `MSK_*` handles in registry from live streaming outputs,
   - removed SSM dependency from in-VPC probe path,
   - corrected `kafka-python` topic create/relist logic.
3. Authoritative green run:
   - `runs/dev_substrate/dev_full/m5/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, `next_gate=M5.I_READY`.
4. Topic outcomes:
   - required topics ready: `9/9`,
   - probe errors: `0`,
   - handle drift: none.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_msk_topic_readiness_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_execution_summary.json`
6. Next action:
   - advance to `M5.I` (`P4.D` ingress envelope conformance).

### M5.I Ingress Envelope Conformance (P4)
Goal:
1. prove ingress edge envelope controls match pinned production posture.

Tasks:
1. validate payload size limits and timeout posture.
2. validate retry/backoff and idempotency TTL posture.
3. validate DLQ/replay mode posture.
4. validate rate-limit posture.
5. publish envelope conformance snapshot.

DoD:
- [x] payload/timeout/retry/idempotency controls conform to pinned handles.
- [x] DLQ/replay/rate-limit controls conform to pinned handles.
- [x] envelope conformance snapshot committed locally and durably.

M5.I execution closure (2026-02-25):
1. Runtime conformance remediation (pre-run):
   - materialized pinned ingress-envelope handles into runtime Terraform variables and Lambda env surfaces,
   - added SQS DLQ resource (`fraud-platform-dev-full-ig-dlq`) and runtime wiring,
   - bound API Gateway integration timeout + stage throttles to pinned handle values,
   - added fail-closed oversized payload handling in IG runtime (`413 payload_too_large`).
2. Authoritative green run:
   - `runs/dev_substrate/dev_full/m5/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, `next_gate=M5.J_READY`.
3. Contract outcomes:
   - valid-key small ingest returns `202`,
   - valid-key oversized ingest returns `413` with `payload_too_large`,
   - API Gateway integration timeout is `30000ms` (`IG_REQUEST_TIMEOUT_SECONDS=30`),
   - stage throttles match pins (`rps=200`, `burst=400`),
   - DDB TTL is enabled on `ttl_epoch`,
   - DLQ queue is present and queryable.
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_ingress_envelope_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_execution_summary.json`
5. Next action:
   - advance to `M5.J` (`P4.E` rollup + M6 handoff).

### M5.J P4 Gate Rollup + M6 Handoff
Goal:
1. adjudicate P4 (`INGEST_READY`) and publish M6 handoff if green.

Tasks:
1. build P4 gate rollup matrix.
2. build P4 blocker register and deterministic verdict artifact.
3. build `m6_handoff_pack.json` with run-scope and explicit evidence references.
4. build and validate:
   - `phase_budget_envelope.json` using `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`,
   - `phase_cost_outcome_receipt.json` using `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`.
5. enforce fail-closed cost gate:
   - if `PHASE_COST_OUTCOME_REQUIRED=true` and receipt is missing/invalid, M5 cannot close.
6. publish M5 closure artifacts locally and durably.
7. append closure note to master plan + impl map + logbook.

DoD:
- [x] P4 gate rollup is complete and blocker-explicit.
- [x] deterministic P4 verdict artifact is committed.
- [x] `m6_handoff_pack.json` committed locally and durably.
- [x] phase-budget envelope and cost-outcome receipt are committed and valid.
- [x] closure notes appended in required docs.

M5.J execution closure (2026-02-25):
1. Authoritative run:
   - `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/m5j_execution_summary.json`
   - outcome: `overall_pass=true`, blockers=`[]`, verdict=`ADVANCE_TO_M6`, next gate=`M6_READY`.
2. Rollup integrity:
   - lane count=`4`, lanes passed=`4` (`P4.A/P4.B/P4.C/P4.D`),
   - P4 blocker register is empty.
3. Handoff publication:
   - local: `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/m6_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m6_handoff_pack.json`
4. Cost-outcome closure:
   - `m5j_phase_budget_envelope.json` and `m5j_phase_cost_outcome_receipt.json` emitted locally and durably,
   - receipt spend posture: `64.835684 USD`,
   - no `M5-B11`/`M5-B12` active blocker.
5. Durable evidence root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/`
6. Next action:
   - M5 is complete; advance to `M6` planning/execution.

## 6) P3/P4 Split Deep Plan Routing
1. P3 detailed lane plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P3.build_plan.md`
2. P4 detailed lane plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P4.build_plan.md`

Rule:
1. M5 execution follows:
   - `M5.A -> M5.B -> M5.C -> M5.D -> M5.E -> M5.F -> M5.G -> M5.H -> M5.I -> M5.J`
2. P4 execution (`M5.F+`) does not start until `M5.E` emits P3 verdict `ADVANCE_TO_P4`.

## 7) M5 Blocker Taxonomy (Fail-Closed)
1. `M5-B0`: deep plan/capability-lane incompleteness.
2. `M5-B0.1`: required P3/P4 decomposition missing/incomplete.
3. `M5-B1`: required handle missing/inconsistent.
4. `M5-B2`: oracle source boundary/ownership drift.
5. `M5-B3`: required output/manifest presence failure.
6. `M5-B4`: stream-view contract/materialization failure.
7. `M5-B5`: P3 rollup/verdict inconsistency.
8. `M5-B6`: IG boundary health/auth failure.
9. `M5-B7`: MSK topic readiness failure.
10. `M5-B8`: ingress envelope conformance failure.
11. `M5-B9`: P4 rollup/verdict inconsistency.
12. `M5-B10`: M6 handoff artifact missing/invalid/unreadable.
13. `M5-B11`: phase-budget/cost-outcome artifact missing/invalid.
14. `M5-B12`: cost-outcome hard-stop violated (`PHASE_COST_HARD_STOP_ON_MISSING_OUTCOME=true`).

Any active `M5-B*` blocker prevents M5 closure.

## 8) M5 Evidence Contract (Pinned for Execution)
1. `m5a_handle_closure_snapshot.json`
2. `m5b_oracle_boundary_snapshot.json`
3. `m5c_required_output_matrix.json`
4. `m5d_stream_view_contract_snapshot.json`
5. `m5e_p3_gate_verdict.json`
6. `m5f_ingress_boundary_health_snapshot.json`
7. `m5g_boundary_auth_snapshot.json`
8. `m5h_msk_topic_readiness_snapshot.json`
9. `m5i_ingress_envelope_snapshot.json`
10. `m5j_p4_gate_verdict.json`
11. `m6_handoff_pack.json`
12. `phase_budget_envelope.json`
13. `phase_cost_outcome_receipt.json`
14. `m5_execution_summary.json`

## 8.1) Run-Folder Naming Convention (operator readability)
1. New run-folder pattern (M5 onward where tooling is ad-hoc lane-driven):
   - `<phase_code>_<semantic_label>_<UTCSTAMP>`
   - example: `m5c_p3b_required_outputs_20260224T191554Z`
2. Compatibility rule:
   - legacy short ids (for example `m5c_20260224T190532Z`) remain valid evidence references and are not retroactively renamed.
3. Hygiene rule:
   - keep only authoritative run folders for each closure attempt,
   - prune empty/non-authoritative ad-hoc attempts to avoid operator confusion.

## 9) M5 Completion Checklist
- [x] M5.A complete
- [x] M5.B complete
- [x] M5.C complete
- [x] M5.D complete
- [x] M5.E complete
- [x] M5.F complete
- [x] M5.G complete
- [x] M5.H complete
- [x] M5.I complete
- [x] M5.J complete
- [x] M5 blockers resolved or explicitly fail-closed
- [x] M5 phase-budget and cost-outcome artifacts are valid and accepted
- [x] M5 closure note appended in implementation map
- [x] M5 action log appended in logbook

## 10) Exit Criteria
M5 can close only when:
1. all checklist items in Section 9 are complete,
2. P3 and P4 verdicts are blocker-free and deterministic,
3. M5 evidence is locally and durably readable,
4. `m6_handoff_pack.json` is committed and reference-valid,
5. `phase_budget_envelope.json` and `phase_cost_outcome_receipt.json` are valid and blocker-free.

Handoff posture:
1. M6 remains blocked until M5 verdict is `ADVANCE_TO_M6`.

## 11) Planning Status (Current)
1. M4 entry dependency is closed green (`ADVANCE_TO_M5`).
2. M5 orchestration plan is expanded to execution-grade with full P3/P4 lane coverage.
3. Dedicated detailed subplans are materialized:
   - `platform.M5.P3.build_plan.md`
   - `platform.M5.P4.build_plan.md`.
4. Pre-execution planning blockers closed:
   - `M5-B0` resolved,
   - `M5-B0.1` resolved.
5. Execution posture:
   - `M5.A` is closed green (`m5a_20260224T182433Z`).
   - `M5.B` / `P3.A` is closed green (`m5b_20260224T185046Z`).
   - `M5.C` / `P3.B` is closed green (`m5c_p3b_required_outputs_20260224T191554Z`) after oracle materialization remediation.
   - `M5.D` / `P3.C` is closed green (`m5d_p3c_stream_view_contract_20260224T192457Z`).
   - `M5.E` / `P3.D` is closed green (`m5e_p3_gate_rollup_20260225T005034Z`) with verdict `ADVANCE_TO_P4`.
   - `M5.F` / `P4.A` is closed green (`m5f_p4a_ingress_boundary_health_20260225T010044Z`) after IG handle repin remediation.
   - `M5.G` / `P4.B` is closed green (`m5g_p4b_boundary_auth_20260225T011324Z`) after IG runtime auth-enforcement remediation.
   - `M5.H` / `P4.C` is closed green (`m5h_p4c_msk_topic_readiness_20260225T015352Z`) after handle repin + in-VPC probe hardening.
   - `M5.I` / `P4.D` is closed green (`m5i_p4d_ingress_envelope_20260225T020758Z`) after runtime envelope conformance remediation.
   - `M5.J` / `P4.E` is closed green (`m5j_p4e_gate_rollup_20260225T021715Z`) with verdict `ADVANCE_TO_M6`.
   - next actionable execution lane is `M6` (Control + Ingress closure planning/execution).
