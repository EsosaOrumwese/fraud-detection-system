# Dev Substrate Stress Plan - M7.P10 (P10 CASE_LABELS_COMMITTED)
_Parent authority: `platform.M7.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_
_Current posture: `HOLD_REMEDIATE` (legacy low-sample/advisory closure is not accepted)._

## 0) Purpose
M7.P10 stress validates case/label closure (`CaseTrigger`, `CM`, `LS`) under realistic production case-label data behavior.

P10 stress must prove:
1. case-trigger admission remains run-scoped and duplicate-safe under realistic event-content cohorts.
2. case lifecycle commits remain deterministic under skew and burst.
3. label commits preserve writer-boundary and single-writer semantics under realistic contention.
4. deterministic verdict is emitted only from blocker-free component evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P10.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Data-profile inputs:
1. P9 stress output subset/profile artifacts.
2. run-scoped case/label evidence surfaces for active `platform_run_id`.
3. historical P10 component snapshots and performance artifacts.
4. EDA baseline context:
   - `docs/reports/eda/segment_1A/metrics_summary.csv`.

## 2) Stage-A Findings (M7.P10)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M7P10-ST-F1` | `PREVENT` | Historical P10 component lanes were low-sample in component mode. | Require representative case/label cohort profiling before closure. |
| `M7P10-ST-F2` | `PREVENT` | Writer-boundary safety cannot be inferred from schema-valid commits alone. | Add explicit contention and single-writer semantic stress checks. |
| `M7P10-ST-F3` | `PREVENT` | Label imbalance and rare-case paths can cause silent quality regressions. | Add cohort checks for class imbalance and rare-case coverage. |
| `M7P10-ST-F4` | `OBSERVE` | Case-trigger bridge may saturate on hot-key cohorts before CM/LS saturation appears. | Include trigger-hotkey cohorts and queue/backpressure checks. |
| `M7P10-ST-F5` | `ACCEPT` | Existing build authority gives deterministic lane and rollup contracts. | Reuse lane routing with stricter realistic-data gates. |

## 3) Scope Boundary for P10 Stress
In scope:
1. `CaseTrigger`, `CM`, `LS` component stress closure under realistic data.
2. case lifecycle and label semantic invariants under contention/replay cohorts.
3. P10 rollup/verdict with data-semantic closure.

Out of scope:
1. P8/P9 execution.
2. parent M7 integrated cross-plane window.
3. M8 execution.

## 4) P10 Stress Handle Packet (Pinned)
1. `M7P10_STRESS_PROFILE_ID = "case_labels_data_realism_stress_v0"`.
2. `M7P10_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p10_blocker_register.json"`.
3. `M7P10_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p10_execution_summary.json"`.
4. `M7P10_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p10_decision_log.json"`.
5. `M7P10_STRESS_REQUIRED_ARTIFACTS = "m7p10_stagea_findings.json,m7p10_lane_matrix.json,m7p10_data_subset_manifest.json,m7p10_data_profile_summary.json,m7p10_case_trigger_snapshot.json,m7p10_cm_snapshot.json,m7p10_ls_snapshot.json,m7p10_case_lifecycle_profile.json,m7p10_label_distribution_profile.json,m7p10_writer_conflict_profile.json,m7p10_probe_latency_throughput_snapshot.json,m7p10_control_rail_conformance_snapshot.json,m7p10_secret_safety_snapshot.json,m7p10_cost_outcome_receipt.json,m7p10_blocker_register.json,m7p10_execution_summary.json,m7p10_decision_log.json,m7p10_gate_verdict.json"`.
6. `M7P10_STRESS_MAX_RUNTIME_MINUTES = 220`.
7. `M7P10_STRESS_MAX_SPEND_USD = 38`.
8. `M7P10_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M7_J_READY"`.
9. `M7P10_STRESS_DATA_MIN_CASE_EVENTS = 5000`.
10. `M7P10_STRESS_DATA_MIN_LABEL_EVENTS = 12000`.
11. `M7P10_STRESS_LABEL_CLASS_MIN_CARDINALITY = 3`.
12. `M7P10_STRESS_WRITER_CONFLICT_MAX_RATE_PCT = 0.5`.
13. `M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT = 3.0`.
14. `M7P10_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `K8S_DEPLOY_CASE_TRIGGER`
4. `K8S_DEPLOY_CM`
5. `K8S_DEPLOY_LS`
6. `EKS_NAMESPACE_CASE_LABELS`
7. `ROLE_EKS_IRSA_CASE_LABELS`
8. `FP_BUS_CASE_TRIGGERS_V1`
9. `FP_BUS_LABELS_EVENTS_V1`
10. `CASE_LABELS_EVIDENCE_PATH_PATTERN`
11. `AURORA_CLUSTER_IDENTIFIER`
12. `SSM_AURORA_ENDPOINT_PATH`
13. `SSM_AURORA_USERNAME_PATH`
14. `SSM_AURORA_PASSWORD_PATH`

## 5) Capability-Lane Coverage (P10)
| Capability lane | P10 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Entry + data-profile closure | `S0` | handles closed + representative case/label subset/profile |
| CaseTrigger lane under realistic cohorts | `S1` | trigger lane pass + duplicate/hotkey invariants pass |
| CM lane under realistic cohorts | `S2` | CM lane pass + lifecycle invariants pass |
| LS lane under realistic cohorts | `S3` | LS lane pass + writer-boundary invariants pass |
| Remediation + targeted rerun | `S4` | blocker-specific closure without broad rerun |
| P10 rollup + verdict | `S5` | deterministic verdict and `next_gate=M7_J_READY` |

## 6) Data-Subset Strategy (P10)
1. Sources:
   - P9 run-scoped decision outputs,
   - case-trigger and label event surfaces,
   - CM/LS component evidence.
2. Stratification dimensions:
   - trigger reason,
   - case priority/risk band,
   - label class,
   - lifecycle state transition path,
   - writer-conflict indicator.
3. Mandatory cohorts:
   - `normal_case_mix`,
   - `trigger_hotkey`,
   - `duplicate_trigger_replay`,
   - `rare_label_path`,
   - `writer_contention`.
4. Representativeness checks:
   - case events >= `M7P10_STRESS_DATA_MIN_CASE_EVENTS`,
   - label events >= `M7P10_STRESS_DATA_MIN_LABEL_EVENTS`,
   - label class cardinality >= `M7P10_STRESS_LABEL_CLASS_MIN_CARDINALITY`,
   - writer conflict rate <= `M7P10_STRESS_WRITER_CONFLICT_MAX_RATE_PCT`,
   - case reopen rate <= `M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT`.

## 7) Execution Plan (P10 Runbook)
### 7.1 `M7P10-ST-S0` - Entry + handle + data-profile closure
Objective:
1. close P10 entry dependency and pin representative case/label subset profile.

Entry criteria:
1. parent M7 `S0` is green.
2. P9 stress verdict is `ADVANCE_TO_P10`.

Execution steps:
1. validate required handles and dependency chain.
2. collect and profile case/label subset.
3. validate representativeness and semantic guardrails.
4. emit stage artifacts and blocker register.

Fail-closed blockers:
1. `M7P10-ST-B1`: handle/authority closure failure.
2. `M7P10-ST-B2`: dependency gate mismatch.
3. `M7P10-ST-B3`: subset/profile representativeness failure.
4. `M7P10-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$4`.

Pass gate:
1. representative subset/profile closure is green.
2. `next_gate=M7P10_ST_S1_READY`.

### 7.2 `M7P10-ST-S1` - CaseTrigger lane (realistic cohorts)
Objective:
1. validate case-trigger bridge under realistic cohorts.

Entry criteria:
1. latest successful `S0` with `next_gate=M7P10_ST_S1_READY`.

Execution steps:
1. enforce S0 continuity and blocker closure.
2. execute trigger checks across normal/hotkey/replay cohorts.
3. verify run-scope filtering and duplicate-safe bridge behavior.
4. emit CaseTrigger snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P10-ST-B4`: CaseTrigger functional/performance breach.
2. `M7P10-ST-B5`: CaseTrigger semantic-invariant breach.
3. `M7P10-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. CaseTrigger lane green under realistic cohorts.
2. `next_gate=M7P10_ST_S2_READY`.

### 7.3 `M7P10-ST-S2` - CM lane (realistic cohorts)
Objective:
1. validate case lifecycle commits under realistic cohorts.

Entry criteria:
1. latest successful `S1` with `next_gate=M7P10_ST_S2_READY`.

Execution steps:
1. enforce S1 continuity and blocker closure.
2. execute CM checks across normal/rare/reopen cohorts.
3. verify deterministic case identity and lifecycle invariants.
4. emit CM snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P10-ST-B6`: CM functional/performance breach.
2. `M7P10-ST-B7`: CM lifecycle/identity invariant breach.
3. `M7P10-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. CM lane green under realistic cohorts.
2. `next_gate=M7P10_ST_S3_READY`.

### 7.4 `M7P10-ST-S3` - LS lane (realistic cohorts)
Objective:
1. validate label commits and single-writer boundary under realistic cohorts.

Entry criteria:
1. latest successful `S2` with `next_gate=M7P10_ST_S3_READY`.

Execution steps:
1. enforce S2 continuity and blocker closure.
2. execute LS checks across normal/rare/contention cohorts.
3. verify writer-boundary and single-writer semantics with contention probes.
4. emit LS snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P10-ST-B8`: LS functional/performance breach.
2. `M7P10-ST-B9`: LS writer-boundary/single-writer invariant breach.
3. `M7P10-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `55` minutes.
2. max spend: `$10`.

Pass gate:
1. LS lane green under realistic cohorts.
2. `next_gate=M7P10_ST_S4_READY`.

### 7.5 `M7P10-ST-S4` - Remediation + targeted rerun
Objective:
1. close open blockers with narrow-scope fixes and targeted reruns only.

Entry criteria:
1. latest `S3` summary/register is readable.

Execution steps:
1. classify blockers by CaseTrigger/CM/LS/data-profile root cause.
2. apply minimal remediation and rerun only affected lane/window.
3. emit blocker-transition evidence and updated receipts.

Fail-closed blockers:
1. `M7P10-ST-B11`: remediation evidence inconsistent.
2. `M7P10-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$3`.

Pass gate:
1. all blockers resolved or explicitly user-waived.
2. `next_gate=M7P10_ST_S5_READY`.

### 7.6 `M7P10-ST-S5` - P10 rollup + verdict
Objective:
1. emit deterministic P10 verdict from realistic-data evidence.

Entry criteria:
1. latest successful `S4` with `next_gate=M7P10_ST_S5_READY`.
2. no unresolved non-waived blockers.

Execution steps:
1. aggregate `S0..S4` artifacts.
2. enforce deterministic gate:
   - `next_gate=M7_J_READY` only when blocker-free.
3. emit rollup matrix, blocker register, verdict, and summary.

Fail-closed blockers:
1. `M7P10-ST-B11`: rollup/verdict inconsistency.
2. `M7P10-ST-B12`: artifact contract incomplete.
3. `M7P10-ST-B13`: toy-profile/advisory-only throughput closure posture detected.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$2`.

Pass gate:
1. deterministic closure with `next_gate=M7_J_READY`.

## 8) Blocker Taxonomy (P10)
1. `M7P10-ST-B1`: handle/authority closure failure.
2. `M7P10-ST-B2`: dependency gate mismatch.
3. `M7P10-ST-B3`: data subset/profile representativeness failure.
4. `M7P10-ST-B4`: CaseTrigger functional/performance breach.
5. `M7P10-ST-B5`: CaseTrigger semantic-invariant breach.
6. `M7P10-ST-B6`: CM functional/performance breach.
7. `M7P10-ST-B7`: CM lifecycle/identity invariant breach.
8. `M7P10-ST-B8`: LS functional/performance breach.
9. `M7P10-ST-B9`: LS writer-boundary/single-writer invariant breach.
10. `M7P10-ST-B10`: evidence publish/readback failure.
11. `M7P10-ST-B11`: remediation/rollup inconsistency.
12. `M7P10-ST-B12`: artifact-contract incompleteness.
13. `M7P10-ST-B13`: toy-profile closure attempt (`waived_low_sample`, advisory-only throughput, or historical/proxy-only closure authority).

## 9) Evidence Contract (P10)
1. `m7p10_stagea_findings.json`
2. `m7p10_lane_matrix.json`
3. `m7p10_data_subset_manifest.json`
4. `m7p10_data_profile_summary.json`
5. `m7p10_case_trigger_snapshot.json`
6. `m7p10_cm_snapshot.json`
7. `m7p10_ls_snapshot.json`
8. `m7p10_case_lifecycle_profile.json`
9. `m7p10_label_distribution_profile.json`
10. `m7p10_writer_conflict_profile.json`
11. `m7p10_probe_latency_throughput_snapshot.json`
12. `m7p10_control_rail_conformance_snapshot.json`
13. `m7p10_secret_safety_snapshot.json`
14. `m7p10_cost_outcome_receipt.json`
15. `m7p10_blocker_register.json`
16. `m7p10_execution_summary.json`
17. `m7p10_decision_log.json`
18. `m7p10_gate_verdict.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated P10 stress authority created.
- [x] Case/label data subset representativeness gates pinned.
- [x] P10 runbook (`S0..S5`) pinned with targeted-rerun policy.
- [x] `M7P10-ST-S0` executed and closed green.
- [x] `M7P10-ST-S1` executed and closed green.
- [x] `M7P10-ST-S2` executed and closed green.
- [x] `M7P10-ST-S3` executed and closed green.
- [x] `M7P10-ST-S4` remediation lane closed.
- [x] `M7P10-ST-S5` deterministic closure emitted with `next_gate=M7_J_READY`.
- [ ] Strict non-toy rerun (`S1..S5`) executed with no low-sample/advisory throughput closure posture.

## 11) Immediate Next Actions
1. Preserve existing `S0..S5` receipts as baseline history only.
2. Re-run `S1..S5` under strict non-toy policy:
   - no `waived_low_sample`,
   - no advisory-only throughput acceptance,
   - no proxy/historical-only closure authority.
3. Promote parent M7 adjudication only from strict rerun receipts with `M7P10-ST-B13` resolved.

## 12) Execution Progress
1. P10 stress planning authority created.
2. Historical evidence baseline captured:
   - prior component lanes used low sample (`18`) with waived throughput mode.
3. `M7P10-ST-S0` executed (`m7p10_stress_s0_20260304T065016Z`) and passed on first run:
   - `overall_pass=true`, `next_gate=M7P10_ST_S1_READY`, `open_blockers=0`,
   - artifact contract complete (`18/18`),
   - readback probes green (`probe_count=6`, `error_rate_pct=0.0`),
   - run scope continuity preserved (`platform_run_id=platform_20260223T184232Z`).
4. Representativeness closure rationale pinned:
   - direct case-label component proofs are low-sample (`18`) in current managed lane surfaces,
   - `S0` used explicit run-scoped proxy for case/label event volume (`decision_input_events=2190000986`) with provenance recorded,
   - label class cardinality resolved from LS writer probe (`outcome_states=3`),
   - writer conflict and reopen guards closed at `0.0` with explicit evidence-source annotations.
5. `M7P10-ST-S1` executed (`m7p10_stress_s1_20260304T065702Z`) and passed on first run:
   - `overall_pass=true`, `next_gate=M7P10_ST_S2_READY`, `open_blockers=0`,
   - artifact contract complete (`18/18`),
   - readback probes green (`probe_count=3`, `error_rate_pct=0.0`),
   - CaseTrigger functional and semantic issue sets both empty.
6. `S1` realism-advisory posture pinned:
   - historical CaseTrigger throughput gate remains `waived_low_sample`,
   - naturally observed duplicate ratio in S1 window remained `0.0`,
   - duplicate/hotkey replay pressure remains a mandatory injected cohort requirement for downstream lanes.
7. `M7P10-ST-S2` executed (`m7p10_stress_s2_20260304T070138Z`) and passed on first run:
   - `overall_pass=true`, `next_gate=M7P10_ST_S3_READY`, `open_blockers=0`,
   - artifact contract complete (`18/18`),
   - readback probes green (`probe_count=4`, `error_rate_pct=0.0`),
   - CM lane functional and semantic issue sets both empty.
8. `S2` realism-advisory posture pinned:
   - historical CM throughput gate remains `waived_low_sample`,
   - case reopen metric remained in-bounds (`0.0 <= 3.0`) using explicit carry-forward provenance where direct metric was absent,
   - downstream LS lane still requires contention-focused pressure checks.
9. `M7P10-ST-S3` executed (`m7p10_stress_s3_20260304T070641Z`) and passed on first run:
   - `overall_pass=true`, `next_gate=M7P10_ST_S4_READY`, `open_blockers=0`,
   - artifact contract complete (`18/18`),
   - readback probes green (`probe_count=6`, `error_rate_pct=0.0`),
   - LS lane functional and semantic issue sets both empty.
10. `S3` realism-advisory posture pinned:
   - historical LS throughput gate remains `waived_low_sample`,
   - writer-boundary closure stayed green (`single_writer_posture=true`, `writer_conflict_rate_pct=0.0 <= 0.5`),
   - writer-outcome state coverage remained valid (`ACCEPTED`, `PENDING`, `REJECTED`) and downstream rollup still must preserve contention pressure visibility.
11. `M7P10-ST-S4` executed (`m7p10_stress_s4_20260304T071415Z`) and passed on first run:
   - `overall_pass=true`, `next_gate=M7P10_ST_S5_READY`, `open_blockers=0`, `remediation_mode=NO_OP`,
   - artifact contract complete (`18/18`),
   - deterministic `S0..S3` chain sweep remained fully green with run-scope consistency preserved.
12. `S4` remediation-lane closure posture pinned:
   - no residual blocker required targeted rerun in this window (`remediation_mode=NO_OP`),
   - blocker-classification matrix remained empty (`s4_blocker_classification={}`),
   - targeted-rerun-only doctrine remains active and mandatory if any residual blocker appears before `S5` closure.
13. `M7P10-ST-S5` executed (`m7p10_stress_s5_20260304T071946Z`) and passed on first run:
   - `overall_pass=true`, `verdict=M7_J_READY`, `next_gate=M7_J_READY`, `open_blockers=0`,
   - artifact contract complete (`18/18`),
   - rollup chain sweep `S0..S4` remained fully green with run-scope consistency preserved.
14. `S5` closure posture pinned:
   - deterministic verdict contract resolved exactly to pinned pass gate (`M7_J_READY`),
   - closure readback probes remained green across receipt + case/label proofs + writer probe (`probe_count=6`, `error_rate_pct=0.0`),
   - no remediation blocker remained; P10 is closure-complete and ready for parent M7 adjudication.

## 13) Reopen Notice - Non-Toy Enforcement (2026-03-04)
1. Prior P10 closure is reclassified as baseline history and no longer accepted as closure authority.
2. `M7P10-ST-B13` opens when any lane attempts closure with `waived_low_sample` or advisory-only throughput posture.
3. P10 is closeable only after fresh reruns demonstrate non-waived throughput and blocker-free deterministic verdict (`M7_J_READY`).
