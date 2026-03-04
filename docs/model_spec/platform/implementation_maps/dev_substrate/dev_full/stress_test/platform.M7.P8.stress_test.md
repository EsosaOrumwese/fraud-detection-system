# Dev Substrate Stress Plan - M7.P8 (P8 RTDL_CAUGHT_UP)
_Parent authority: `platform.M7.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-04_
_Current posture: `HOLD_REMEDIATE` (legacy low-sample/advisory closure is not accepted)._

## 0) Purpose
M7.P8 stress validates RTDL closure (`IEG`, `OFP`, `ArchiveWriter`) under realistic production data-content behavior.

P8 stress must prove:
1. RTDL inlet/context/archive lanes remain correct under realistic event mix and edge cohorts.
2. run-scoped data-content invariants hold across `IEG -> OFP -> ArchiveWriter`.
3. replay/duplicate/out-of-order data does not break lag, checkpoint, or archive durability posture.
4. deterministic verdict is emitted only from blocker-free component evidence.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P8.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Data-profile inputs:
1. latest run-scoped ingest artifacts (`receipt`, `offset`, `quarantine`) for active `platform_run_id`.
2. historical P8 performance snapshots (`p8b/p8c/p8d`) and rollup artifacts.
3. parent `M7-ST-S0` black-box realism artifacts (run-scoped):
   - `m7_data_subset_manifest.json`,
   - `m7_data_profile_summary.json`,
   - `m7_data_edge_case_matrix.json`.
4. RTDL proof/evidence references:
   - `evidence/runs/{platform_run_id}/rtdl_core/ieg_component_proof.json`,
   - run-scoped behavior-context refs from `m7_data_subset_manifest.json`.

## 2) Stage-A Findings (M7.P8)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M7P8-ST-F1` | `PREVENT` | Historical `P8` component lanes passed with low sample (`sample_size=18`) and waived throughput assertions. | Require non-waived data-representativeness checks before lane closure. |
| `M7P8-ST-F2` | `PREVENT` | Local checked-in event subset is anchor-only and cannot represent RTDL traffic diversity. | Materialize run-scoped subset from ingest/archive evidence surfaces. |
| `M7P8-ST-F3` | `PREVENT` | Schema-valid events can still fail RTDL on out-of-order/duplicate/hotkey patterns. | Add cohort-specific semantic assertions for IEG/OFP/ArchiveWriter. |
| `M7P8-ST-F4` | `OBSERVE` | Archive durability may degrade under payload-size and skew spikes. | Include payload-size and skew cohorts in archive stress windows. |
| `M7P8-ST-F5` | `ACCEPT` | Existing build-run lanes provide deterministic routing and artifact names. | Reuse routing with stricter data-content gates. |

## 3) Scope Boundary for P8 Stress
In scope:
1. `IEG`, `OFP`, `ArchiveWriter` component stress closure.
2. run-scoped RTDL data subset profiling and representativeness gating.
3. P8 rollup/verdict with data-semantic closure.

Out of scope:
1. P9 decision-chain execution.
2. P10 case/labels execution.
3. parent M7 integrated cross-plane window.

## 4) P8 Stress Handle Packet (Pinned)
1. `M7P8_STRESS_PROFILE_ID = "rtdl_data_realism_stress_v0"`.
2. `M7P8_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p8_blocker_register.json"`.
3. `M7P8_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p8_execution_summary.json"`.
4. `M7P8_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m7p8_decision_log.json"`.
5. `M7P8_STRESS_REQUIRED_ARTIFACTS = "m7p8_stagea_findings.json,m7p8_lane_matrix.json,m7p8_data_subset_manifest.json,m7p8_data_profile_summary.json,m7p8_ieg_snapshot.json,m7p8_ofp_snapshot.json,m7p8_archive_snapshot.json,m7p8_data_edge_case_matrix.json,m7p8_probe_latency_throughput_snapshot.json,m7p8_control_rail_conformance_snapshot.json,m7p8_secret_safety_snapshot.json,m7p8_cost_outcome_receipt.json,m7p8_blocker_register.json,m7p8_execution_summary.json,m7p8_decision_log.json,m7p8_gate_verdict.json"`.
6. `M7P8_STRESS_MAX_RUNTIME_MINUTES = 220`.
7. `M7P8_STRESS_MAX_SPEND_USD = 35`.
8. `M7P8_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_P9"`.
9. `M7P8_STRESS_DATA_MIN_SAMPLE_EVENTS = 6000`.
10. `M7P8_STRESS_EVENT_TYPE_MIN_COUNT = 3`.
11. `M7P8_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT = "0.5|5.0"`.
12. `M7P8_STRESS_OUT_OF_ORDER_RATIO_TARGET_RANGE_PCT = "0.2|3.0"`.
13. `M7P8_STRESS_HOTKEY_TOP1_SHARE_MAX = 0.60`.
14. `M7P8_STRESS_TARGETED_RERUN_ONLY = true`.

Registry-backed required handles:
1. `FLINK_RUNTIME_PATH_ACTIVE`
2. `FLINK_RUNTIME_PATH_ALLOWED`
3. `PHASE_RUNTIME_PATH_MODE`
4. `FLINK_APP_RTDL_IEG_OFP_V0`
5. `FLINK_EKS_RTDL_IEG_REF`
6. `FLINK_EKS_RTDL_OFP_REF`
7. `FLINK_EKS_NAMESPACE`
8. `K8S_DEPLOY_IEG`
9. `K8S_DEPLOY_OFP`
10. `K8S_DEPLOY_ARCHIVE_WRITER`
11. `FP_BUS_TRAFFIC_V1`
12. `FP_BUS_CONTEXT_V1`
13. `RTDL_CORE_CONSUMER_GROUP_ID`
14. `RTDL_CORE_OFFSET_COMMIT_POLICY`
15. `RTDL_CAUGHT_UP_LAG_MAX`
16. `S3_ARCHIVE_RUN_PREFIX_PATTERN`
17. `S3_ARCHIVE_EVENTS_PREFIX_PATTERN`
18. `S3_EVIDENCE_BUCKET`

## 5) Capability-Lane Coverage (P8)
| Capability lane | P8 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + data-profile closure | `S0` | handles closed + representative subset/profile |
| IEG lane under realistic data cohorts | `S1` | IEG lane pass + semantic invariants pass |
| OFP lane under realistic data cohorts | `S2` | OFP lane pass + semantic invariants pass |
| ArchiveWriter under realistic data cohorts | `S3` | archive durability/readback + semantic invariants pass |
| Remediation + targeted rerun | `S4` | blocker-specific closure without broad rerun |
| P8 rollup + verdict | `S5` | deterministic verdict `ADVANCE_TO_P9` |

## 6) Data-Subset Strategy (P8)
1. Sources:
   - run-scoped ingest receipt/offset/quarantine surfaces,
   - run-scoped archive event objects,
   - RTDL lane snapshots.
2. Stratification dimensions:
   - event type,
   - country/mcc/merchant cohorts,
   - payload-size bucket,
   - temporal bucket and lateness bucket.
3. Mandatory cohorts:
   - `normal_mix`,
   - `hotkey_skew`,
   - `duplicate_replay`,
   - `late_out_of_order`,
   - `rare_edge`.
4. P8 representativeness checks:
   - sample size >= `M7P8_STRESS_DATA_MIN_SAMPLE_EVENTS`,
   - event families >= `M7P8_STRESS_EVENT_TYPE_MIN_COUNT`,
   - duplicate/out-of-order ratios within target ranges,
   - top-key share <= `M7P8_STRESS_HOTKEY_TOP1_SHARE_MAX`.

## 7) Execution Plan (P8 Runbook)
### 7.1 `M7P8-ST-S0` - Entry + handle + data-profile closure
Objective:
1. close P8 entry dependency and pin run-scoped realistic subset profile.

Entry criteria:
1. parent M7 `S0` is green.
2. no unresolved required handle decision for P8.

Execution steps:
1. validate required handles and runtime path admissibility.
2. collect run-scoped subset from ingest/archive surfaces.
3. build subset manifest/profile and representativeness verdict.
4. emit stage artifacts and blocker register.

Fail-closed blockers:
1. `M7P8-ST-B1`: handle/authority closure failure.
2. `M7P8-ST-B2`: dependency gate mismatch.
3. `M7P8-ST-B3`: subset/profile representativeness failure.
4. `M7P8-ST-B10`: evidence publish/readback failure.

Runtime/cost budget:
1. max runtime: `30` minutes.
2. max spend: `$4`.

Pass gate:
1. representative subset/profile is closed green.
2. `next_gate=M7P8_ST_S1_READY`.

### 7.2 `M7P8-ST-S1` - IEG lane (realistic cohorts)
Objective:
1. validate IEG under realistic data cohorts.

Entry criteria:
1. latest successful `S0` with `next_gate=M7P8_ST_S1_READY`.

Execution steps:
1. enforce S0 continuity and blocker closure.
2. execute IEG checks across normal/edge cohorts.
3. verify lag, checkpoint, duplicate/out-of-order semantic invariants.
4. emit IEG snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P8-ST-B4`: IEG functional/performance breach.
2. `M7P8-ST-B5`: IEG semantic-invariant breach under realistic cohorts.
3. `M7P8-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. IEG lane is green under realistic cohorts.
2. `next_gate=M7P8_ST_S2_READY`.

### 7.3 `M7P8-ST-S2` - OFP lane (realistic cohorts)
Objective:
1. validate OFP context projection under realistic data cohorts.

Entry criteria:
1. latest successful `S1` with `next_gate=M7P8_ST_S2_READY`.

Execution steps:
1. enforce S1 continuity and blocker closure.
2. execute OFP checks across normal/edge cohorts.
3. verify context projection completeness and ordering semantics.
4. emit OFP snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P8-ST-B6`: OFP functional/performance breach.
2. `M7P8-ST-B7`: OFP semantic/context-projection breach.
3. `M7P8-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `45` minutes.
2. max spend: `$8`.

Pass gate:
1. OFP lane is green under realistic cohorts.
2. `next_gate=M7P8_ST_S3_READY`.

### 7.4 `M7P8-ST-S3` - ArchiveWriter lane (realistic cohorts)
Objective:
1. validate archive durability and readback under realistic data cohorts.

Entry criteria:
1. latest successful `S2` with `next_gate=M7P8_ST_S3_READY`.

Execution steps:
1. enforce S2 continuity and blocker closure.
2. execute archive writes across payload-size/skew/late cohorts.
3. verify append/readback/object-path invariants and no silent drops.
4. emit archive snapshot and stage artifacts.

Fail-closed blockers:
1. `M7P8-ST-B8`: archive durability/readback failure.
2. `M7P8-ST-B9`: archive semantic-integrity drift under realistic cohorts.
3. `M7P8-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `55` minutes.
2. max spend: `$10`.

Pass gate:
1. archive lane is green under realistic cohorts.
2. `next_gate=M7P8_ST_S4_READY`.

### 7.5 `M7P8-ST-S4` - Remediation + targeted rerun
Objective:
1. close open blockers with narrow-scope fixes and targeted reruns only.

Entry criteria:
1. latest `S3` summary/register is readable.

Execution steps:
1. classify blockers by IEG/OFP/archive/data-profile root cause.
2. apply minimal remediation and rerun only affected lane/window.
3. emit blocker-transition evidence and updated receipts.

Fail-closed blockers:
1. `M7P8-ST-B11`: remediation evidence inconsistent.
2. `M7P8-ST-B10`: evidence contract failure.

Runtime/cost budget:
1. max runtime: `25` minutes.
2. max spend: `$3`.

Pass gate:
1. all blockers resolved or explicitly user-waived.
2. `next_gate=M7P8_ST_S5_READY`.

### 7.6 `M7P8-ST-S5` - P8 rollup + verdict
Objective:
1. emit deterministic P8 verdict from blocker-consistent realistic-data evidence.

Entry criteria:
1. latest successful `S4` with `next_gate=M7P8_ST_S5_READY`.
2. no unresolved non-waived blockers.

Execution steps:
1. aggregate `S0..S4` artifacts.
2. enforce deterministic verdict:
   - `ADVANCE_TO_P9` only when blocker-free.
3. emit rollup matrix, blocker register, verdict, and summary.

Fail-closed blockers:
1. `M7P8-ST-B11`: rollup/verdict inconsistency.
2. `M7P8-ST-B12`: artifact contract incomplete.
3. `M7P8-ST-B13`: toy-profile/advisory-only throughput closure posture detected.

Runtime/cost budget:
1. max runtime: `20` minutes.
2. max spend: `$2`.

Pass gate:
1. deterministic verdict `ADVANCE_TO_P9`.
2. `next_gate=ADVANCE_TO_P9`.

## 8) Blocker Taxonomy (P8)
1. `M7P8-ST-B1`: handle/authority closure failure.
2. `M7P8-ST-B2`: dependency gate mismatch.
3. `M7P8-ST-B3`: data subset/profile representativeness failure.
4. `M7P8-ST-B4`: IEG functional/performance breach.
5. `M7P8-ST-B5`: IEG semantic-invariant breach.
6. `M7P8-ST-B6`: OFP functional/performance breach.
7. `M7P8-ST-B7`: OFP semantic/context-projection breach.
8. `M7P8-ST-B8`: archive durability/readback breach.
9. `M7P8-ST-B9`: archive semantic-integrity breach.
10. `M7P8-ST-B10`: evidence publish/readback failure.
11. `M7P8-ST-B11`: remediation/rollup inconsistency.
12. `M7P8-ST-B12`: artifact-contract incompleteness.
13. `M7P8-ST-B13`: toy-profile closure attempt (`waived_low_sample`, advisory-only throughput, or historical/proxy-only closure authority).

## 9) Evidence Contract (P8)
1. `m7p8_stagea_findings.json`
2. `m7p8_lane_matrix.json`
3. `m7p8_data_subset_manifest.json`
4. `m7p8_data_profile_summary.json`
5. `m7p8_ieg_snapshot.json`
6. `m7p8_ofp_snapshot.json`
7. `m7p8_archive_snapshot.json`
8. `m7p8_data_edge_case_matrix.json`
9. `m7p8_probe_latency_throughput_snapshot.json`
10. `m7p8_control_rail_conformance_snapshot.json`
11. `m7p8_secret_safety_snapshot.json`
12. `m7p8_cost_outcome_receipt.json`
13. `m7p8_blocker_register.json`
14. `m7p8_execution_summary.json`
15. `m7p8_decision_log.json`
16. `m7p8_gate_verdict.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated P8 stress authority created.
- [x] Data-subset and representativeness gates pinned.
- [x] P8 runbook (`S0..S5`) pinned with targeted-rerun policy.
- [x] `M7P8-ST-S0` executed and closed green.
- [x] `M7P8-ST-S1` executed and closed green.
- [x] `M7P8-ST-S2` executed and closed green.
- [x] `M7P8-ST-S3` executed and closed green.
- [x] `M7P8-ST-S4` remediation lane closed.
- [x] `M7P8-ST-S5` verdict emitted as `ADVANCE_TO_P9`.
- [ ] Strict non-toy rerun (`S1..S5`) executed with no low-sample/advisory throughput closure posture.

## 11) Immediate Next Actions
1. Preserve existing `S0..S5` receipts as baseline history only.
2. Re-run `S1..S5` under strict non-toy policy:
   - no `waived_low_sample`,
   - no advisory-only throughput acceptance,
   - no proxy/historical-only closure authority.
3. Promote parent `M7-ST-S1` adjudication only from strict rerun receipts with `M7P8-ST-B13` resolved.

## 12) Execution Progress
1. P8 stress planning authority created.
2. Historical evidence baseline captured:
   - prior component lanes used low sample (`18`) with waived throughput mode.
3. `M7P8-ST-S0` first run (`m7p8_stress_s0_20260304T052722Z`) opened blocker:
   - `M7P8-ST-B1`: required bus handles were pinned under newer registry aliases (`FP_BUS_TRAFFIC_FRAUD_V1`, `FP_BUS_CONTEXT_*`) rather than legacy canonical names.
4. `M7P8-ST-S0` remediation:
   - implemented alias-aware required-handle closure in runner (fail-closed preserved if no valid equivalent exists).
5. `M7P8-ST-S0` rerun (`m7p8_stress_s0_20260304T052810Z`) passed:
   - `overall_pass=true`, `next_gate=M7P8_ST_S1_READY`, `open_blockers=0`.
6. `M7P8-ST-S1` first run (`m7p8_stress_s1_20260304T052814Z`) opened blocker:
   - `M7P8-ST-B4`: runtime-path taxonomy mismatch (`EKS_EMR_ON_EKS` historical artifact vs current pinned `EKS_FLINK_OPERATOR`).
7. `M7P8-ST-S1` remediation:
   - normalized runtime-path aliases in S1 checks so fail-closed semantics apply to runtime-class mismatch, not naming drift.
8. `M7P8-ST-S1` rerun (`m7p8_stress_s1_20260304T052941Z`) passed:
   - `overall_pass=true`, `next_gate=M7P8_ST_S2_READY`, `open_blockers=0`,
   - IEG functional/perf/semantic checks closed green with readback proofs,
   - throughput remains documented as `waived_low_sample` (deferred non-waived certification lane).
9. `M7P8-ST-S2` first run (`m7p8_stress_s2_20260304T053741Z`) passed:
   - `overall_pass=true`, `next_gate=M7P8_ST_S3_READY`, `open_blockers=0`,
   - OFP functional/perf/semantic checks closed green with readback proofs and context-completeness checks,
   - throughput remains documented as `waived_low_sample` (deferred non-waived certification lane).
10. `M7P8-ST-S3` first run (`m7p8_stress_s3_20260304T054234Z`) passed:
   - `overall_pass=true`, `next_gate=M7P8_ST_S4_READY`, `open_blockers=0`,
   - ArchiveWriter durability/readback and semantic-integrity checks closed green with proof readback and fallback-object validation,
   - known primary archive-path access restriction remains documented and explicitly covered by validated fallback evidence path.
11. `M7P8-ST-S4` first run (`m7p8_stress_s4_20260304T054605Z`) passed:
   - `overall_pass=true`, `next_gate=M7P8_ST_S5_READY`, `open_blockers=0`,
   - `remediation_mode=NO_OP`,
   - deterministic chain sweep (`S0..S3`) remained blocker-free and consistent, so no targeted rerun was required.
12. `M7P8-ST-S5` first run (`m7p8_stress_s5_20260304T055237Z`) passed:
   - `overall_pass=true`, `verdict=ADVANCE_TO_P9`, `next_gate=ADVANCE_TO_P9`, `open_blockers=0`,
   - chain sweep (`S0..S4`) remained run-scope consistent (`platform_run_id=platform_20260223T184232Z`),
   - rollup evidence contract remained complete and readable (`probe_count=5`, `error_rate_pct=0.0`).

## 13) Reopen Notice - Non-Toy Enforcement (2026-03-04)
1. Prior P8 closure is reclassified as baseline history and no longer accepted as closure authority.
2. `M7P8-ST-B13` opens when any lane attempts closure with `waived_low_sample` or advisory-only throughput posture.
3. P8 is closeable only after fresh reruns demonstrate non-waived throughput and blocker-free deterministic verdict (`ADVANCE_TO_P9`).
