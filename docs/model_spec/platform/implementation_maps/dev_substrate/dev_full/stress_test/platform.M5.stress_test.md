# Dev Substrate Stress Plan - M5 (Oracle and Ingest Preflight Orchestration)
_Status source of truth: `platform.stress_test.md`_
_This document provides deep stress-planning detail for M5 orchestration._
_Track: `dev_full` only_
_As of 2026-03-03_

## 0) Purpose
M5 stress validates oracle-to-ingress preflight readiness under realistic production posture before M6 activation.

M5 stress must prove:
1. M4 handoff (`M5_READY`) is preserved with no readiness drift at phase entry.
2. P3 oracle-ready stress closure is explicit, blocker-consistent, and evidence-complete.
3. P4 ingest-ready stress closure is explicit, blocker-consistent, and evidence-complete.
4. M5 closure rollup emits deterministic M6 handoff recommendation from blocker-consistent evidence.
5. runtime and spend envelopes are enforced at phase level before any M6 transition.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P3.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P4.build_plan.md`
5. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
6. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m4_stress_s5_20260303T200552Z/stress/m4_execution_summary.json`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

## 2) Stage-A Findings (M5)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M5-ST-F1` | `PREVENT` | M5 carries two materially different stress sub-lanes (`P3` oracle, `P4` ingest). Single-file inline runbook would be phase-cram risk. | Split into dedicated `platform.M5.P3.stress_test.md` and `platform.M5.P4.stress_test.md` with parent orchestration gating. |
| `M5-ST-F2` | `PREVENT` | P3 and P4 have independent blocker taxonomies and verdict semantics (`ADVANCE_TO_P4`, `ADVANCE_TO_M6`). | Pin deterministic parent gate checks for both subphase verdicts before M5 closure. |
| `M5-ST-F3` | `PREVENT` | M5 entry must remain strictly chained to latest successful M4 S5 summary (`M5_READY`, `GO`). | Enforce S0 fail-closed dependency validation before any M5 subphase execution. |
| `M5-ST-F4` | `OBSERVE` | Oracle refresh lanes can appear green from stale historical artifacts if active-source readbacks are not rechecked. | Require P3 to verify active-source handles and fresh run-scope evidence surfaces. |
| `M5-ST-F5` | `OBSERVE` | Ingress boundary/auth/topic/envelope lanes can drift after runtime rematerialization. | Require P4 to treat handle/runtime parity as mandatory pass gates. |
| `M5-ST-F6` | `OBSERVE` | Oracle upload/sort and ingress probe windows can consume budget quickly if reruns are broad. | Enforce targeted rerun-only policy and explicit cost-outcome receipts for each subphase. |
| `M5-ST-F7` | `ACCEPT` | M4 closure is green and explicitly recommends M5 activation (`M5_READY`). | Use M4 S5 evidence as authoritative entry gate for M5 planning/execution. |

## 3) Scope Boundary for M5 Stress
In scope:
1. phase-level M5 orchestration gates and subphase sequencing (`P3` then `P4`).
2. parent-level authority/entry checks and closure rollup logic.
3. deterministic gating from P3 verdict to P4 entry and from P4 verdict to M6 recommendation.
4. parent-level runtime/spend envelope and artifact-completeness checks.
5. parent-level blocker adjudication for unresolved subphase states.

Out of scope:
1. detailed oracle lane execution logic (owned by `platform.M5.P3.stress_test.md`).
2. detailed ingest lane execution logic (owned by `platform.M5.P4.stress_test.md`).
3. M6 runtime activation and full control+ingress stress execution.

## 4) M5 Parent Stress Handle Packet (Pinned)
1. `M5_STRESS_PROFILE_ID = "oracle_ingest_preflight_orchestration_stress_v0"`.
2. `M5_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5_blocker_register.json"`.
3. `M5_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5_execution_summary.json"`.
4. `M5_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5_decision_log.json"`.
5. `M5_STRESS_REQUIRED_ARTIFACTS = "m5_stagea_findings.json,m5_lane_matrix.json,m5_probe_latency_throughput_snapshot.json,m5_control_rail_conformance_snapshot.json,m5_secret_safety_snapshot.json,m5_cost_outcome_receipt.json,m5_blocker_register.json,m5_execution_summary.json,m5_decision_log.json"`.
6. `M5_STRESS_MAX_RUNTIME_MINUTES = 240`.
7. `M5_STRESS_MAX_SPEND_USD = 60`.
8. `M5_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M6_READY"`.
9. `M5_STRESS_REQUIRED_SUBPHASES = "M5.P3|M5.P4"`.
10. `M5_STRESS_P3_REQUIRED_VERDICT = "ADVANCE_TO_P4"`.
11. `M5_STRESS_P4_REQUIRED_VERDICT = "ADVANCE_TO_M6"`.
12. `M5_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles for M5 parent entry checks:
1. `S3_EVIDENCE_BUCKET`
2. `S3_RUN_CONTROL_ROOT_PATTERN`
3. `ORACLE_REQUIRED_OUTPUT_IDS`
4. `ORACLE_SORT_KEY_BY_OUTPUT_ID`
5. `ORACLE_STORE_BUCKET`
6. `ORACLE_SOURCE_NAMESPACE`
7. `ORACLE_ENGINE_RUN_ID`
8. `S3_ORACLE_INPUT_PREFIX_PATTERN`
9. `S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN`
10. `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`
11. `ORACLE_STREAM_SORT_EXECUTION_MODE`
12. `ORACLE_STREAM_SORT_ENGINE`
13. `ORACLE_STREAM_SORT_TRIGGER_SURFACE`
14. `ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED`
15. `IG_BASE_URL`
16. `IG_INGEST_PATH`
17. `IG_HEALTHCHECK_PATH`
18. `IG_AUTH_MODE`
19. `IG_AUTH_HEADER_NAME`
20. `SSM_IG_API_KEY_PATH`
21. `MSK_CLUSTER_ARN`
22. `MSK_BOOTSTRAP_BROKERS_SASL_IAM`
23. `MSK_CLIENT_SUBNET_IDS`
24. `MSK_SECURITY_GROUP_ID`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M5 parent stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry gate closure | `S0` | valid M4->M5 handoff + required parent handle closure |
| P3 orchestration closure | `S1` | latest successful P3 rollup with verdict `ADVANCE_TO_P4` |
| P4 orchestration closure | `S2` | latest successful P4 rollup with verdict `ADVANCE_TO_M6` |
| M5 closure rollup + M6 recommendation | `S3` | blocker-free M5 closure rollup + `M6_READY` recommendation |

Subphase authority routing:
1. P3 deep stress runbook: `stress_test/platform.M5.P3.stress_test.md`.
2. P4 deep stress runbook: `stress_test/platform.M5.P4.stress_test.md`.

## 6) Stress Topology (M5 Parent)
1. Component sequence:
   - `M5.S0` (entry/authority),
   - `M5.S1` (P3 rollup gate),
   - `M5.S2` (P4 rollup gate),
   - `M5.S3` (M5 closure and M6 recommendation).
2. Plane sequence:
   - `oracle_preflight_plane` (`P3`),
   - `ingress_preflight_plane` (`P4`),
   - `phase_closure_plane`.
3. Integrated windows:
   - `m5_s0_entry_window`,
   - `m5_s1_p3_rollup_window`,
   - `m5_s2_p4_rollup_window`,
   - `m5_s3_m6_handoff_window`.

## 7) Execution Plan (Parent Orchestration Runbook)
### 7.1 `M5-ST-S0` - Authority and entry-gate closure
Objective:
1. fail-closed validation that M5 can activate with complete authority and valid M4 handoff.

Actions:
1. validate required M5 parent handles and placeholder guards.
2. validate latest successful M4 S5 summary:
   - `overall_pass=true`,
   - `recommendation=GO`,
   - `next_gate=M5_READY`.
3. validate presence/readability of M5 split stress authorities (`M5`, `M5.P3`, `M5.P4`).
4. emit Stage-A findings + lane matrix + blocker register.

Pass gate:
1. required M5 parent handles complete/non-placeholder.
2. M4 S5 handoff summary and blocker register are valid/readable.
3. split M5 stress authorities are present/readable.
4. full parent S0 artifact set exists/readable.

### 7.2 `M5-ST-S1` - P3 orchestration gate closure
Objective:
1. validate that P3 deep stress closure is complete and verdict-safe for P4 entry.

Actions:
1. load latest successful P3 summary/register from `platform.M5.P3` stress lane.
2. require deterministic P3 verdict gate:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P4`,
   - no open non-waived `M5P3-B*` blockers.
3. verify P3 required artifact contract completeness.
4. emit parent S1 gate receipt and blocker adjudication.

Pass gate:
1. P3 closure verdict is deterministic and equals `ADVANCE_TO_P4`.
2. P3 blocker register has no open non-waived blockers.
3. P3 required artifacts are complete/readable.

### 7.3 `M5-ST-S2` - P4 orchestration gate closure
Objective:
1. validate that P4 deep stress closure is complete and verdict-safe for M6 handoff.

Actions:
1. load latest successful P4 summary/register from `platform.M5.P4` stress lane.
2. require deterministic P4 verdict gate:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_M6`,
   - no open non-waived `M5P4-B*` blockers.
3. verify P4 required artifact contract completeness including `m6_handoff_pack` reference.
4. emit parent S2 gate receipt and blocker adjudication.

Pass gate:
1. P4 closure verdict is deterministic and equals `ADVANCE_TO_M6`.
2. P4 blocker register has no open non-waived blockers.
3. P4 required artifacts are complete/readable.

### 7.4 `M5-ST-S3` - M5 closure rollup and M6 recommendation
Objective:
1. publish deterministic M5 closure verdict and explicit M6 readiness recommendation.

Actions:
1. aggregate latest successful parent `S0..S2` receipts and subphase rollups.
2. enforce parent artifact/runtime/spend envelope checks.
3. emit deterministic recommendation:
   - `GO` + `next_gate=M6_READY` only when blocker-free and envelope-safe,
   - otherwise `NO_GO` + `next_gate=BLOCKED`.

Pass gate:
1. no open non-waived `M5-ST-B*` blockers.
2. subphase verdicts are `ADVANCE_TO_P4` and `ADVANCE_TO_M6` respectively.
3. runtime/spend envelope within pinned bounds.
4. next gate matches expected pass gate (`M6_READY`).

## 8) Blocker Taxonomy (M5 Parent)
1. `M5-ST-B1`: missing/unresolved required parent handle or plan key.
2. `M5-ST-B2`: invalid M4 handoff dependency or entry-gate mismatch.
3. `M5-ST-B3`: missing/unreadable split subphase authority file.
4. `M5-ST-B4`: P3 gate failure (missing/invalid verdict or open blocker).
5. `M5-ST-B5`: P4 gate failure (missing/invalid verdict or open blocker).
6. `M5-ST-B6`: closure-rollup or deterministic recommendation inconsistency.
7. `M5-ST-B7`: secret-safety or evidence publish/readback violation.
8. `M5-ST-B8`: unattributed spend or budget envelope breach.
9. `M5-ST-B9`: artifact/evidence contract incomplete or unreadable.

Any open `M5-ST-B*` blocks M5 closure and M6 transition recommendation.

## 9) Evidence Contract (Parent)
Required artifacts for each M5 parent stress stage:
1. `m5_stagea_findings.json`
2. `m5_lane_matrix.json`
3. `m5_probe_latency_throughput_snapshot.json`
4. `m5_control_rail_conformance_snapshot.json`
5. `m5_secret_safety_snapshot.json`
6. `m5_cost_outcome_receipt.json`
7. `m5_blocker_register.json`
8. `m5_execution_summary.json`
9. `m5_decision_log.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M5 parent stress authority created.
- [x] M5 split-subphase routing (`P3` and `P4`) pinned.
- [x] Parent handle packet and parent blocker taxonomy pinned.
- [x] Parent orchestration runbook (`S0..S3`) pinned.
- [x] M5 parent S0 executed with blocker-free entry closure.
- [ ] P3 and P4 orchestration gates validated from stress evidence.
- [ ] M5 closure rollup emitted with deterministic `M6_READY` recommendation.

## 11) Immediate Next Actions
1. Execute `M5P3-ST-S0` authority/entry-gate closure.
2. Keep targeted-rerun posture: rerun only failed stage windows (`M5P3` or `M5P4`) when blockers open.
3. Do not advance parent `M5-ST-S1` until `M5P3` emits blocker-free rollup verdict `ADVANCE_TO_P4`.

## 12) Execution Progress
### `M5-ST-S0` authority/entry-gate closure execution (2026-03-03)
1. Initial fail-closed run:
   - `phase_execution_id=m5_stress_s0_20260303T232538Z`,
   - blocker: `M5-ST-B1` (`missing_handles` detected for stream-view handles).
2. Root cause and remediation:
   - registry parser in new runner split on the wrong `=` when values contained `output_id=...`,
   - remediated parser to split on first `=` token inside backtick handle body.
3. Authoritative rerun:
   - `phase_execution_id=m5_stress_s0_20260303T232628Z`,
   - command: `python scripts/dev_substrate/m5_stress_runner.py --stage S0`,
   - verdict: `overall_pass=true`,
   - `next_gate=M5_ST_S1_READY`,
   - `open_blockers=0`,
   - `probe_count=1`,
   - `error_rate_pct=0.0`.
4. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m5_stress_s0_20260303T232628Z/stress/m5_decision_log.json`
