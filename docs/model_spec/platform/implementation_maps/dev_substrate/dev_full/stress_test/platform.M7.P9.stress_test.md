# Dev Substrate Stress Plan - M7.P9 (P9 DECISION_CHAIN_COMMITTED)
_Parent authority: `platform.M7.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_

## 0) Purpose
M7.P9 stress validates decision-chain closure (`DF`, `AL`, `DLA`) under realistic production decision-data behavior.

P9 stress must prove:
1. decision commits remain deterministic across realistic score/event cohorts.
2. action/outcome commits stay duplicate-safe and replay-safe under realistic retry/ordering patterns.
3. audit truth remains append-only and causally consistent under realistic throughput and skew.
4. deterministic verdict is emitted only from blocker-free component evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P9.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Data-profile inputs:
1. P8 stress output subset/profile artifacts.
2. run-scoped decision-lane evidence surfaces for active `platform_run_id`.
3. historical P9 component snapshots and performance artifacts.
4. EDA baseline context:
   - `docs/reports/eda/segment_1A/metrics_summary.csv`.

## 2) Stage-A Findings (M7.P9)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M7P9-ST-F1` | `PREVENT` | Historical P9 lanes also ran low-sample (`sample_size=18`) in component mode. | Force representative decision-input subset gating before lane closure. |
| `M7P9-ST-F2` | `PREVENT` | Decision/action correctness can hide cohort-specific regressions (rare paths, high-risk tails). | Add score/policy/action cohort assertions to each lane. |
| `M7P9-ST-F3` | `PREVENT` | Idempotency correctness under replay depends on real duplicate distribution, not schema checks. | Add duplicate collision and replay-window semantic checks. |
| `M7P9-ST-F4` | `OBSERVE` | AL/DLA lanes can pass average metrics while tail retries/backpressure degrade. | Gate p95/p99 and retry-ratio posture by cohort. |
| `M7P9-ST-F5` | `ACCEPT` | Existing build authority provides deterministic lane boundaries and rollup routing. | Reuse routing with stronger realistic-data checks. |

## 3) Scope Boundary for P9 Stress
In scope:
1. `DF`, `AL`, `DLA` component stress closure under realistic data.
2. decision/action/audit semantic invariants under cohorted replay windows.
3. P9 rollup/verdict with data-semantic closure.

Out of scope:
1. P8 runtime execution.
2. P10 case/labels execution.
3. parent M7 integrated cross-plane window.

## 4) P9 Stress Handle Packet (Pinned)
1. `M7P9_STRESS_PROFILE_ID = "decision_chain_data_realism_stress_v0"`.
2. `M7P9_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p9_blocker_register.json"`.
3. `M7P9_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p9_execution_summary.json"`.
4. `M7P9_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p9_decision_log.json"`.
5. `M7P9_STRESS_REQUIRED_ARTIFACTS = "m7p9_stagea_findings.json,m7p9_lane_matrix.json,m7p9_data_subset_manifest.json,m7p9_data_profile_summary.json,m7p9_df_snapshot.json,m7p9_al_snapshot.json,m7p9_dla_snapshot.json,m7p9_score_distribution_profile.json,m7p9_action_mix_profile.json,m7p9_idempotency_collision_profile.json,m7p9_probe_latency_throughput_snapshot.json,m7p9_control_rail_conformance_snapshot.json,m7p9_secret_safety_snapshot.json,m7p9_cost_outcome_receipt.json,m7p9_blocker_register.json,m7p9_execution_summary.json,m7p9_decision_log.json,m7p9_gate_verdict.json"`.
6. `M7P9_STRESS_MAX_RUNTIME_MINUTES = 220`.
7. `M7P9_STRESS_MAX_SPEND_USD = 38`.
8. `M7P9_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_P10"`.
9. `M7P9_STRESS_DATA_MIN_SAMPLE_EVENTS = 8000`.
10. `M7P9_STRESS_POLICY_PATH_MIN_CARDINALITY = 5`.
11. `M7P9_STRESS_ACTION_CLASS_MIN_CARDINALITY = 3`.
12. `M7P9_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT = "0.5|5.0"`.
13. `M7P9_STRESS_RETRY_RATIO_MAX_PCT = 5.0`.
14. `M7P9_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `K8S_DEPLOY_DF`
4. `K8S_DEPLOY_AL`
5. `K8S_DEPLOY_DLA`
6. `EKS_NAMESPACE_RTDL`
7. `ROLE_EKS_IRSA_DECISION_LANE`
8. `FP_BUS_RTDL_V1`
9. `FP_BUS_AUDIT_V1`
10. `DECISION_LANE_EVIDENCE_PATH_PATTERN`
11. `AURORA_CLUSTER_IDENTIFIER`
12. `SSM_AURORA_ENDPOINT_PATH`
13. `SSM_AURORA_USERNAME_PATH`
14. `SSM_AURORA_PASSWORD_PATH`
15. `DDB_IG_IDEMPOTENCY_TABLE`

## 5) Capability-Lane Coverage (P9)
| Capability lane | P9 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Entry + data-profile closure | `S0` | handles closed + representative decision-data subset/profile |
| DF lane under realistic cohorts | `S1` | DF lane pass + decision semantic invariants pass |
| AL lane under realistic cohorts | `S2` | AL lane pass + action/retry semantic invariants pass |
| DLA lane under realistic cohorts | `S3` | DLA lane pass + append-only/audit invariants pass |
| Remediation + targeted rerun | `S4` | blocker-specific closure without broad rerun |
| P9 rollup + verdict | `S5` | deterministic verdict `ADVANCE_TO_P10` |

## 6) Data-Subset Strategy (P9)
1. Sources:
   - P8 run-scoped outputs and context projections,
   - decision-lane component evidence (`DF/AL/DLA`),
   - ingest duplicate/idempotency indicators.
2. Stratification dimensions:
   - score decile,
   - policy path,
   - action class,
   - retry count,
   - event freshness bucket.
3. Mandatory cohorts:
   - `normal_decision_mix`,
   - `high_risk_tail`,
   - `duplicate_replay`,
   - `policy_edge_paths`,
   - `retry_pressure`.
4. Representativeness checks:
   - sample size >= `M7P9_STRESS_DATA_MIN_SAMPLE_EVENTS`,
   - policy-path/action-class cardinality minimums met,
   - duplicate ratio in target range,
   - retry ratio <= `M7P9_STRESS_RETRY_RATIO_MAX_PCT`.

## 7) Execution Plan (P9 Runbook)
### 7.1 `M7P9-ST-S0` - Entry + handle + data-profile closure
Objective:
1. close P9 entry dependency and pin representative decision-data subset profile.

Entry criteria:
1. parent M7 `S0` is green.
2. P8 stress verdict is `ADVANCE_TO_P9`.

Execution steps:
1. validate required handles and dependency chain.
2. collect and profile decision-input subset.
3. validate representativeness and semantic guardrails.
4. emit stage artifacts and blocker register.

Fail-closed blockers:
1. `M7P9-ST-B1`: handle/authority closure failure.
2. `M7P9-ST-B2`: dependency gate mismatch.
3. `M7P9-ST-B3`: subset/profile representativeness failure.
4. `M7P9-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$4`.

Pass gate:
1. representative subset/profile closure is green.
2. `next_gate=M7P9_ST_S1_READY`.

### 7.2 `M7P9-ST-S1` - DF lane (realistic cohorts)
Objective:
1. validate deterministic decision commits under realistic cohorts.

Entry criteria:
1. latest successful `S0` with `next_gate=M7P9_ST_S1_READY`.

Execution steps:
1. enforce S0 continuity and blocker closure.
2. execute DF checks across normal/tail/edge cohorts.
3. verify deterministic decision identity and idempotent commit behavior.
4. emit DF snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P9-ST-B4`: DF functional/performance breach.
2. `M7P9-ST-B5`: DF semantic-invariant breach.
3. `M7P9-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. DF lane green under realistic cohorts.
2. `next_gate=M7P9_ST_S2_READY`.

### 7.3 `M7P9-ST-S2` - AL lane (realistic cohorts)
Objective:
1. validate action/outcome commits under realistic cohorts.

Entry criteria:
1. latest successful `S1` with `next_gate=M7P9_ST_S2_READY`.

Execution steps:
1. enforce S1 continuity and blocker closure.
2. execute AL checks across action/retry cohorts.
3. verify retry/backpressure bounds and duplicate-safe outcomes.
4. emit AL snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P9-ST-B6`: AL functional/performance breach.
2. `M7P9-ST-B7`: AL semantic/retry-invariant breach.
3. `M7P9-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. AL lane green under realistic cohorts.
2. `next_gate=M7P9_ST_S3_READY`.

### 7.4 `M7P9-ST-S3` - DLA lane (realistic cohorts)
Objective:
1. validate append-only audit truth under realistic cohorts.

Entry criteria:
1. latest successful `S2` with `next_gate=M7P9_ST_S3_READY`.

Execution steps:
1. enforce S2 continuity and blocker closure.
2. execute DLA checks across normal/edge/replay cohorts.
3. verify append-only and causal chain invariants.
4. emit DLA snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P9-ST-B8`: DLA functional/performance breach.
2. `M7P9-ST-B9`: DLA append-only/causal-invariant breach.
3. `M7P9-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `55` minutes.
2. max spend: `$10`.

Pass gate:
1. DLA lane green under realistic cohorts.
2. `next_gate=M7P9_ST_S4_READY`.

### 7.5 `M7P9-ST-S4` - Remediation + targeted rerun
Objective:
1. close open blockers with narrow-scope fixes and targeted reruns only.

Entry criteria:
1. latest `S3` summary/register is readable.

Execution steps:
1. classify blockers by DF/AL/DLA/data-profile root cause.
2. apply minimal remediation and rerun only affected lane/window.
3. emit blocker-transition evidence and updated receipts.

Fail-closed blockers:
1. `M7P9-ST-B11`: remediation evidence inconsistent.
2. `M7P9-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$3`.

Pass gate:
1. all blockers resolved or explicitly user-waived.
2. `next_gate=M7P9_ST_S5_READY`.

### 7.6 `M7P9-ST-S5` - P9 rollup + verdict
Objective:
1. emit deterministic P9 verdict from realistic-data evidence.

Entry criteria:
1. latest successful `S4` with `next_gate=M7P9_ST_S5_READY`.
2. no unresolved non-waived blockers.

Execution steps:
1. aggregate `S0..S4` artifacts.
2. enforce deterministic verdict:
   - `ADVANCE_TO_P10` only when blocker-free.
3. emit rollup matrix, blocker register, verdict, and summary.

Fail-closed blockers:
1. `M7P9-ST-B11`: rollup/verdict inconsistency.
2. `M7P9-ST-B12`: artifact contract incomplete.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$2`.

Pass gate:
1. deterministic verdict `ADVANCE_TO_P10`.
2. `next_gate=ADVANCE_TO_P10`.

## 8) Blocker Taxonomy (P9)
1. `M7P9-ST-B1`: handle/authority closure failure.
2. `M7P9-ST-B2`: dependency gate mismatch.
3. `M7P9-ST-B3`: data subset/profile representativeness failure.
4. `M7P9-ST-B4`: DF functional/performance breach.
5. `M7P9-ST-B5`: DF semantic-invariant breach.
6. `M7P9-ST-B6`: AL functional/performance breach.
7. `M7P9-ST-B7`: AL semantic/retry-invariant breach.
8. `M7P9-ST-B8`: DLA functional/performance breach.
9. `M7P9-ST-B9`: DLA append-only/causal-invariant breach.
10. `M7P9-ST-B10`: evidence publish/readback failure.
11. `M7P9-ST-B11`: remediation/rollup inconsistency.
12. `M7P9-ST-B12`: artifact-contract incompleteness.

## 9) Evidence Contract (P9)
1. `m7p9_stagea_findings.json`
2. `m7p9_lane_matrix.json`
3. `m7p9_data_subset_manifest.json`
4. `m7p9_data_profile_summary.json`
5. `m7p9_df_snapshot.json`
6. `m7p9_al_snapshot.json`
7. `m7p9_dla_snapshot.json`
8. `m7p9_score_distribution_profile.json`
9. `m7p9_action_mix_profile.json`
10. `m7p9_idempotency_collision_profile.json`
11. `m7p9_probe_latency_throughput_snapshot.json`
12. `m7p9_control_rail_conformance_snapshot.json`
13. `m7p9_secret_safety_snapshot.json`
14. `m7p9_cost_outcome_receipt.json`
15. `m7p9_blocker_register.json`
16. `m7p9_execution_summary.json`
17. `m7p9_decision_log.json`
18. `m7p9_gate_verdict.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated P9 stress authority created.
- [x] Decision-data subset representativeness gates pinned.
- [x] P9 runbook (`S0..S5`) pinned with targeted-rerun policy.
- [x] `M7P9-ST-S0` executed and closed green.
- [x] `M7P9-ST-S1` executed and closed green.
- [x] `M7P9-ST-S2` executed and closed green.
- [x] `M7P9-ST-S3` executed and closed green.
- [x] `M7P9-ST-S4` remediation lane closed.
- [x] `M7P9-ST-S5` verdict emitted as `ADVANCE_TO_P10`.

## 11) Immediate Next Actions
1. Promote `M7P9` closure verdict into parent `M7-ST-S2` adjudication input.
2. Carry forward `S0/S1/S2/S3/S4/S5` advisories into `P10` stress pressure:
   - policy-path coverage currently uses proxy from P8 event diversity,
   - active decision-class coverage is sparse in observed receipts,
   - duplicate floor is below target and must be injected explicitly downstream,
   - managed-lane low-sample throughput remains advisory and must be stress-pressured explicitly downstream.
3. Begin `M7.P10` sequential execution (`S0 -> S5`) with the same fail-closed rollup posture.

## 12) Execution Progress
1. P9 stress planning authority created.
2. Historical evidence baseline captured:
   - prior component lanes used low sample (`18`) with waived throughput mode.
3. Pre-execution blocker confirmation:
   - latest `M7P8-ST-S5` remained blocker-free (`open_blocker_count=0`, `verdict=ADVANCE_TO_P9`),
   - upstream `M7P8-ST-S4` blocker register remained closed.
4. `M7P9-ST-S0` executed (`m7p9_stress_s0_20260304T060915Z`) and passed:
   - `overall_pass=true`, `next_gate=M7P9_ST_S1_READY`, `open_blockers=0`,
   - `probe_count=7`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present),
   - representativeness blocking checks passed with explicit advisories for downstream duplicate/retry/policy-edge injections.
5. `M7P9-ST-S1` executed (`m7p9_stress_s1_20260304T061430Z`) and passed:
   - `overall_pass=true`, `next_gate=M7P9_ST_S2_READY`, `open_blockers=0`,
   - DF functional/performance and semantic-invariant checks closed green,
   - `probe_count=2`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present),
   - sparse natural cohort coverage remains explicit advisory (duplicate-floor and active action-class pressure retained for downstream injected stress).
6. `M7P9-ST-S2` executed (`m7p9_stress_s2_20260304T061756Z`) and passed:
   - `overall_pass=true`, `next_gate=M7P9_ST_S3_READY`, `open_blockers=0`,
   - AL functional/performance and semantic/retry-invariant checks closed green,
   - `probe_count=2`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present),
   - sparse natural cohort coverage and managed-lane low-sample throughput remain explicit advisories for downstream injected stress windows.
7. `M7P9-ST-S3` executed (`m7p9_stress_s3_20260304T062431Z`) and passed:
   - `overall_pass=true`, `next_gate=M7P9_ST_S4_READY`, `open_blockers=0`,
   - DLA functional/performance and append-only/causal-invariant checks closed green,
   - `probe_count=3`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present),
   - managed-lane low-sample throughput and sparse natural cohort coverage remain explicit advisories for downstream pressure windows.
8. `M7P9-ST-S4` executed (`m7p9_stress_s4_20260304T062934Z`) and passed:
   - `overall_pass=true`, `next_gate=M7P9_ST_S5_READY`, `open_blockers=0`, `remediation_mode=NO_OP`,
   - targeted-rerun lane remained deterministic and blocker-consistent across `S0..S3` chain sweep,
   - `probe_count=1`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present).
9. `M7P9-ST-S5` executed (`m7p9_stress_s5_20260304T063429Z`) and passed:
   - `overall_pass=true`, `verdict=ADVANCE_TO_P10`, `next_gate=ADVANCE_TO_P10`, `open_blockers=0`,
   - chain sweep remained run-scope consistent across `S0..S4` (`platform_run_id=platform_20260223T184232Z`),
   - `probe_count=7`, `error_rate_pct=0.0`,
   - artifact contract complete (`18/18` required artifacts present).
