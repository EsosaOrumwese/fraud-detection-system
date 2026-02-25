# Dev Substrate Deep Plan - M5 (P3 ORACLE_READY + P4 INGEST_READY)
_Status source of truth: `platform.build_plan.md`_
_This document provides orchestration-level deep planning detail for M5._
_Last updated: 2026-02-24_

## 0) Purpose
M5 closes:
1. `P3 ORACLE_READY` (oracle source + stream-view contract readiness).
2. `P4 INGEST_READY` (ingress boundary + MSK topic + envelope preflight readiness).

M5 must prove:
1. oracle source-of-stream posture is read-only from platform runtime and contract-valid,
2. required stream-view outputs are present and pass manifest/materialization checks,
3. ingest edge boundary (health + auth + bus topics + envelope controls) is ready fail-closed,
4. P3/P4 gate verdicts and M6 handoff are deterministic and auditable,
5. M5 phase-budget and cost-outcome posture is explicit and pass-gated.

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
3. validate oracle inlet mode boundary (`external_pre_staged`) and ownership.
4. publish oracle boundary posture snapshot.

DoD:
- [x] oracle boundary posture is explicit and read-only.
- [x] ownership posture is explicit and producer-owned.
- [x] oracle boundary snapshot is committed locally and durably.

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
   - copied required oracle stream-view output prefixes/manifests from dev-min authoritative source to pinned dev-full oracle source path.
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
- [ ] ingest and ops health endpoints are healthy.
- [ ] boundary response contracts are readable and valid.
- [ ] ingress boundary health snapshot committed locally and durably.

### M5.G Boundary Auth Enforcement (P4)
Goal:
1. prove boundary auth contract is enforced as pinned.

Tasks:
1. verify auth mode and required header handles.
2. run positive auth preflight with valid key.
3. run negative auth preflight without/invalid key and require fail-closed behavior.
4. publish auth enforcement snapshot.

DoD:
- [ ] auth contract handles are consistent.
- [ ] positive and negative auth probes pass expected outcomes.
- [ ] auth enforcement snapshot committed locally and durably.

### M5.H MSK Topic Readiness (P4)
Goal:
1. prove required ingress/control topics are ready and reachable.

Tasks:
1. validate MSK cluster/bootstrap handles and connectivity posture.
2. verify required topics exist and are writable/readable by intended producer/consumer identities.
3. publish topic readiness snapshot.

DoD:
- [ ] required topics exist and are reachable.
- [ ] topic ownership/readiness checks pass.
- [ ] topic readiness snapshot committed locally and durably.

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
- [ ] payload/timeout/retry/idempotency controls conform to pinned handles.
- [ ] DLQ/replay/rate-limit controls conform to pinned handles.
- [ ] envelope conformance snapshot committed locally and durably.

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
- [ ] P4 gate rollup is complete and blocker-explicit.
- [ ] deterministic P4 verdict artifact is committed.
- [ ] `m6_handoff_pack.json` committed locally and durably.
- [ ] phase-budget envelope and cost-outcome receipt are committed and valid.
- [ ] closure notes appended in required docs.

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
- [ ] M5.F complete
- [ ] M5.G complete
- [ ] M5.H complete
- [ ] M5.I complete
- [ ] M5.J complete
- [ ] M5 blockers resolved or explicitly fail-closed
- [ ] M5 phase-budget and cost-outcome artifacts are valid and accepted
- [ ] M5 closure note appended in implementation map
- [ ] M5 action log appended in logbook

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
   - next actionable execution lane is `M5.F` (`P4`).
