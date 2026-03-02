# Dev Substrate Deep Plan - M15 (DATA_SEMANTICS_REALIZATION)
_Status source of truth: `platform.build_plan.md`_
_Track: `dev_full`_
_Last updated: 2026-03-02_

## 0) Purpose
M15 formalizes and executes data semantics realization for learning/evolution.

M15 is green only when all are true:
1. Learning/evolution lanes consume real data semantics, not bootstrap placeholders.
2. Point-in-time correctness is enforced (`replay_basis`, `feature_asof_utc`, `label_asof_utc`, `label_maturity_days`).
3. No-future leakage posture is proven on real datasets.
4. OFS and MF evidence ties directly to authoritative stream-view/truth-view contracts.
5. Cost/performance receipts remain within pinned envelopes.
6. Data-reality closure (`M15.A..M15.C`) is completed before any runtime/ops-governance certification rerun claims are made.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
4. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
5. `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M10.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M11.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Current Reality Snapshot (Planning Baseline)
1. M9 guardrails for replay/as-of/maturity/leakage are implemented and evidenced.
2. M10/M11 managed lanes are contract-green, but OFS build notebooks are bootstrap sources:
   - `platform/databricks/dev_full/ofs_build_v0.py`
   - `platform/databricks/dev_full/ofs_quality_v0.py`
3. M11.D currently computes training/eval inputs through deterministic generated payloads in managed workflow path, not from authoritative OFS tables.

M15 exists to close this semantic gap without regressing M9 guardrails.

## 3) Entry Contract (Fail-Closed)
M15 execution cannot start unless all are true:
1. USER explicitly activates M15 in `platform.build_plan.md`.
2. M14 active work does not have unresolved blockers that invalidate upstream data surfaces.
3. Required handle set for M15.A is resolved or explicitly listed as unresolved blockers.
4. Managed query/compute path is available for semantic profiling and dataset builds (Athena/Databricks/EMR).

## 3.1) Execution Posture Lock (Data-Reality First)
1. M15 is the pre-certification semantic hardening phase; it is not an optional analysis track.
2. `M15.A`, `M15.B`, and `M15.C` must close green before:
   - any new runtime certification claim,
   - any ops/governance certification claim,
   - any "production-like learning" claim.
3. Bounded dataset policy for initial closure:
   - execute on a representative bounded horizon first (for example 2-4 weeks),
   - then repin sample-size and horizon for broader closure in `M15.H`.
4. All M15 closure evidence is managed-compute only; local ad-hoc analysis is non-authoritative.

## 4) Pinned Decisions (Binding for M15)
1. Data-output semantics and ownership are anchored to `data_engine_interface.md`.
2. Runtime decision lanes must remain isolated from truth-only outputs (`s4_*`).
3. Learning inputs must remain replay-basis and as-of bounded (`origin_offset_ranges` mode continuity).
4. Label maturity is mandatory and enforced fail-closed.
5. Learning/evolution closure evidence must come from managed compute only.
6. Bootstrap-only OFS/MF placeholders cannot be used as closure evidence.
7. IEG entity-relationship posture must be empirically pinned from observed key stability, joinability, and late-arrival behavior.
8. Archive/truth routing to offline learning surfaces must have explicit timeliness and maturity contracts with measured receipts.
9. Feature engineering and explainability surfaces must be derived from observed data behavior; schema-only assumptions are non-authoritative.

## 5) Data Semantics Contract (Expected Use by Plane)
Hot path (runtime):
1. Stream-view outputs are used for runtime progression and event-time bounded processing.
2. Truth products (`s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_case_timeline_6B`) are forbidden in live decision path.

Learning path (offline):
1. Truth products are learning-only surfaces.
2. Training/eval datasets are point-in-time materialized:
   - feature rows are bounded by `feature_asof_utc`,
   - label rows are bounded by `label_asof_utc`,
   - mature labels only (`label_maturity_days`).
3. Future-derived fields are fail-closed in learning input audits.

## 6) Capability-Lane Coverage Matrix
| Capability lane | Subphase | Minimum PASS evidence |
| --- | --- | --- |
| Canonical output contract map | M15.A | output ownership/use matrix + unresolved count=0 |
| Managed semantic profiling | M15.B | schema/profile report with key/time/null integrity |
| Point-in-time policy realization | M15.C | as-of/maturity/leakage policy spec + validation probes |
| OFS real-data implementation | M15.D | real dataset build snapshot + artifact parity |
| MF real-data eval rewiring | M15.E | train/eval snapshot tied to OFS refs |
| Leakage adversarial validation | M15.F | guardrail report pass under challenge cases |
| Semantic non-regression pack | M15.G | M9/M10/M11 semantic continuity pass |
| Cost/perf envelope closure | M15.H | semantic-workload cost/perf receipt pass |
| Phase rollup verdict | M15.I | deterministic blocker-free verdict |
| Closure sync | M15.J | summary + blocker register parity pass |

## 7) Subphase Plan and DoD Contracts

### M15.A - Canonical Data Contract Mapping
Goal:
1. Produce authoritative mapping of output IDs to runtime/learning use, ownership, keys, and temporal semantics.

Required handles:
1. `ORACLE_REQUIRED_OUTPUT_IDS`
2. `ORACLE_SORT_KEY_BY_OUTPUT_ID`
3. `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`
4. `LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS`
5. `LEARNING_REPLAY_BASIS_MODE`
6. `LEARNING_LABEL_MATURITY_DAYS_DEFAULT`

DoD:
- [x] data contract matrix published with no ambiguous ownership.
- [x] every output ID is tagged `runtime`, `learning`, or `both` with explicit rules.
- [x] unresolved semantic questions are fail-closed blockers, not assumptions.
- [x] initial entity-map candidates for IEG are pinned with key/relationship hypotheses and explicit unresolveds.

Blockers:
1. `M15-B1` ambiguous ownership or unresolved semantic mapping.

Execution plan (M15.A):
1. Parse required M15.A handles from `dev_full_handles.registry.v0.md`.
2. Build canonical output set from:
   - `ORACLE_REQUIRED_OUTPUT_IDS`,
   - `ORACLE_SORT_KEY_BY_OUTPUT_ID` keys,
   - `LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS`,
   - `ORACLE_OFFLINE_TRUTH_OUTPUT_IDS`.
3. Emit deterministic contract matrix rows per output ID with fields:
   - `output_id`, `usage_scope` (`runtime|learning|both`),
   - `runtime_allowed`, `learning_allowed`,
   - `sort_key`, `time_order_mode`,
   - `entity_keys_candidate`, `future_field_risk`, `notes`.
4. Emit IEG candidate relationship map with:
   - candidate entities and link hypotheses,
   - expected join surfaces and stability assumptions,
   - unresolved list (must be empty for PASS).
5. Fail-closed checks:
   - all required handles present and non-placeholder,
   - all output IDs mapped exactly once,
   - no truth-only output has `runtime_allowed=true`,
   - unresolved list count is zero.
6. Publish artifact set local and durable (if credentials permit), then emit deterministic summary + blocker register.

M15.A artifact contract:
1. `m15a_semantics_contract_matrix.json`
2. `m15a_ieg_entity_map_candidates.json`
3. `m15a_execution_summary.json`
4. `m15a_blocker_register.json`

M15.A runtime budget:
1. Target <= 15 minutes (docs/contract lane).

### M15.B - Managed Semantic Profiling
Goal:
1. Profile authoritative data surfaces and publish deterministic profile evidence.

Execution rules:
1. Use managed query lanes only (Athena/Databricks SQL/Spark).
2. Profile dimensions:
   - schema and type stability,
   - null rates,
   - key uniqueness expectations,
   - time-range continuity,
   - cardinality and joinability baselines.
3. Additional required profiling:
   - stream progression posture (state growth over time),
   - late-arrival/ordering behavior,
   - entity-link stability for IEG candidate relationships.

DoD:
- [x] profile report committed local + durable.
- [x] all critical integrity checks either pass or are explicit blockers.
- [x] profile includes at least one bounded representative horizon with explicit row/event counts.

Blockers:
1. `M15-B2` schema/profile drift beyond policy.

Execution strategy (M15.B, detailed):
1. Execution objective:
   - convert M15.A hypotheses into measured facts from managed compute on a bounded representative horizon.
2. Managed compute path:
   - primary engine: `ATHENA_GLUE_ICEBERG` for profile SQL and reproducible receipts,
   - fallback engine: `Databricks SQL/Spark` only if a required query cannot be expressed/performed reliably in Athena.
3. Bounded-horizon inputs (must be pinned at run start):
   - `window_start_utc`,
   - `window_end_utc`,
   - `window_profile_label` (for example `7d_baseline`),
   - `max_scan_bytes_gb` hard cap,
   - `max_rows_per_surface` soft cap for exploratory sub-profiles.
4. In-scope surfaces for first pass:
   - runtime/context: `s3_event_stream_with_fraud_6B`, `s3_flow_anchor_with_fraud_6B`, `arrival_events_5B`, `s1_arrival_entities_6B`,
   - learning/truth: `s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_case_timeline_6B`,
   - cautionary learning-only surface: `s1_session_index_6B`.
5. Profiling lanes (all required):
   - `B1 schema_profile`: column presence/type/null profile per surface,
   - `B2 key_integrity`: duplicate/missing-key checks on expected key tuples,
   - `B3 time_integrity`: coverage window, monotonic/time-gap posture, out-of-order indicators,
   - `B4 joinability`: measured coverage for canonical join pairs from interface pack,
   - `B5 entity_stability`: reuse/churn/collision posture for IEG candidate entity keys.
6. Canonical key tuples (first-pass checks):
   - event-flow pair: `flow_id,event_seq` (event granularity),
   - arrival linkage: `merchant_id,arrival_seq`,
   - flow truth linkage: `flow_id`,
   - case linkage: `case_id` where applicable.
7. Canonical join coverage matrix (first-pass):
   - `s3_event_stream_with_fraud_6B` <-> `s3_flow_anchor_with_fraud_6B` on `flow_id`,
   - `s3_flow_anchor_with_fraud_6B` <-> `arrival_events_5B` on `merchant_id,arrival_seq`,
   - `arrival_events_5B` <-> `s1_arrival_entities_6B` on `merchant_id,arrival_seq`,
   - `s4_event_labels_6B` <-> `s3_event_stream_with_fraud_6B` on `flow_id,event_seq`,
   - `s4_flow_truth_labels_6B` <-> `s3_flow_anchor_with_fraud_6B` on `flow_id`,
   - `s4_flow_bank_view_6B` <-> `s3_flow_anchor_with_fraud_6B` on `flow_id`.
8. Late-arrival and ordering posture:
   - compute observed delay distributions between event-time fields and label/case observation fields where available,
   - when explicit observation timestamp is absent, emit explicit unresolved and block closure.
9. Fail-closed policy for M15.B:
   - missing required surface in bounded horizon,
   - key tuple cannot be computed from available columns,
   - unresolved join coverage for canonical pairs,
   - scan cap breach without approved rebound run,
   - durable evidence publish/readback failure.
10. Classification model for findings:
   - `PASS`: measured and within pinned policy,
   - `ADVISORY`: measurable but outside preferred envelope (non-blocking for B only if no semantic risk),
   - `BLOCKER (M15-B2)`: schema/profile drift that undermines contract assumptions.
11. Output decision coupling to later phases:
   - `M15.C` consumes `joinability`, `late-arrival`, and `entity_stability` outputs,
   - `M15.D` consumes schema/key/time contracts and null policies,
   - `M15.E` consumes feature-feasibility and label-link confidence outputs.

M15.B execution sequence:
1. Preflight:
   - validate run inputs and scan caps,
   - assert all in-scope surfaces are resolvable,
   - generate `m15b_profile_manifest.json`.
2. Run `B1..B5` profiling lanes in deterministic order.
3. Assemble cross-lane matrix and adjudicate pass/advisory/blocker.
4. Publish local artifacts and durable mirror.
5. Emit phase verdict:
   - `ADVANCE_TO_M15_C` when blocker count is zero,
   - `BLOCKED_M15_B` otherwise.

M15.B artifact contract:
1. `m15b_profile_manifest.json`
2. `m15b_schema_profile.json`
3. `m15b_key_integrity_report.json`
4. `m15b_time_integrity_report.json`
5. `m15b_join_coverage_matrix.json`
6. `m15b_entity_stability_report.json`
7. `m15b_blocker_register.json`
8. `m15b_execution_summary.json`

M15.B runtime and cost guardrails:
1. Target runtime <= 60 minutes for bounded first-pass window.
2. Hard fail on `max_scan_bytes_gb` breach unless explicit operator-approved rebounded run is pinned.
3. Emit `query_count`, `total_scanned_bytes`, `cost_estimate_usd`, and `rows_profiled` in execution summary.

M15.B v1 pinned run inputs (approved):
1. `window_profile_label = "7d_baseline"`
2. `window_end_utc = max(ts_utc)` from `s3_event_stream_with_fraud_6B` at run start.
3. `window_start_utc = window_end_utc - 7 days`.
4. `max_scan_bytes_gb = 300`.
5. `max_rows_per_surface = 50000000`.

M15.B closure snapshot:
1. Final green execution:
   - `m15b_semantic_profile_20260302T072457Z`
2. Verdict:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M15.C_READY`
3. Runtime/cost receipt:
   - `query_count=32`
   - `total_scanned_gb=95.108`
   - `cost_estimate_usd=0.4644`
   - scan cap respected (`95.108 < 300` GB).
4. Advisory retained (non-blocking):
   - `M15-AD2` optional surface absent for this run: `s1_session_index_6B`.
5. Local artifacts:
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_profile_manifest.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_schema_profile.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_key_integrity_report.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_time_integrity_report.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_join_coverage_matrix.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_entity_stability_report.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_blocker_register.json`
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_execution_summary.json`
6. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_profile_manifest.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_schema_profile.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_key_integrity_report.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_time_integrity_report.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_join_coverage_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_entity_stability_report.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15b_semantic_profile_20260302T072457Z/m15b_execution_summary.json`

### M15.C - Point-in-Time Policy Realization
Goal:
1. Pin executable policy for as-of joins, maturity lag, and leakage exclusions on real surfaces.

DoD:
- [x] policy spec published and machine-checkable.
- [x] adversarial edge cases are enumerated and tested.
- [x] future-boundary and truth-surface misuse are fail-closed.
- [x] archive/truth routing contract is pinned with timeliness and maturity semantics (bank-truth + oracle-truth intake lanes).
- [x] IEG entity-relationship selection is pinned from observed profile evidence (not assumptions).

Blockers:
1. `M15-B3` point-in-time semantics mismatch.
2. `M15-B4` leakage boundary breach.

M15.C execution strategy (locked):
1. Authority and evidence inputs:
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_semantics_contract_matrix.json`,
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_ieg_entity_map_candidates.json`,
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_schema_profile.json`,
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_time_integrity_report.json`,
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_join_coverage_matrix.json`,
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_key_integrity_report.json`,
   - `runs/dev_substrate/dev_full/m15/m15b_semantic_profile_20260302T072457Z/m15b_entity_stability_report.json`,
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`,
   - `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`,
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`.
2. Policy spec realization:
   - materialize machine-checkable JSON policy containing:
     - replay basis mode,
     - `feature_asof_utc`,
     - `label_asof_utc`,
     - `label_maturity_days`,
     - runtime-forbidden truth surfaces,
     - runtime-forbidden future-field list,
     - fail-closed leakage mode.
   - derive policy timestamps from `M15.B` bounded profile window (`window_end_utc`) and maturity days pin.
3. Validation lanes:
   - `C1`: runtime boundary checks (`runtime_max_ts <= feature_asof_utc`) on all runtime-allowed surfaces from `M15.A`,
   - `C2`: truth boundary checks (`truth_max_ts <= label_asof_utc`) on all offline truth surfaces,
   - `C3`: maturity envelope semantics check (`label_maturity_cutoff_utc = label_asof_utc - maturity_days`) with explicit readiness posture for downstream `M15.D`,
   - `C4`: leakage guardrail checks:
     - truth outputs cannot be runtime-allowed,
     - runtime surfaces cannot expose forbidden future fields,
     - learning-only caution surfaces are excluded from runtime path.
4. Adversarial probe suite (must be executed and pass):
   - invalid policy mutation probes:
     - future-valued as-of,
     - zero/negative maturity days,
     - runtime inclusion of truth outputs,
     - runtime inclusion of future-only fields.
   - each probe must deterministically fail in policy evaluator.
5. Archive/truth routing contract closure:
   - emit explicit bank-truth and oracle-truth intake contract with:
     - source outputs,
     - timeliness pairing to runtime anchors,
     - measured max-lag posture from `M15.B` reports,
     - maturity gating semantics for learning eligibility.
6. IEG relationship pin from observed evidence:
   - select primary relationship spine from measured stability/joinability (not schema assumption),
   - publish explicit selected graph and deferred/non-selected relationships with reason.
7. Fail-closed conditions:
   - required policy handles unresolved,
   - any boundary/leakage check fails,
   - adversarial probe unexpectedly passes,
   - durable evidence publish/readback fails.
8. Verdict rules:
   - `ADVANCE_TO_M15_D` when blocker count is zero,
   - `BLOCKED_M15_C` otherwise.

M15.C artifact contract:
1. `m15c_point_in_time_policy_spec.json`
2. `m15c_policy_validation_report.json`
3. `m15c_adversarial_probe_report.json`
4. `m15c_archive_truth_timeliness_contract.json`
5. `m15c_ieg_entity_relationship_pin.json`
6. `m15c_blocker_register.json`
7. `m15c_execution_summary.json`

M15.C runtime/cost guardrails:
1. Target runtime <= 30 minutes.
2. No new heavy data-profile scans are allowed in M15.C; this lane is evidence-closure and policy validation over M15.A/B outputs.
3. Publish local + durable receipts for all M15.C artifacts.

M15.C closure snapshot:
1. First attempt failed closed:
   - execution: `m15c_point_in_time_policy_20260302T074331Z`,
   - blocker: `M15-B3` (`Required M15.C handles missing: EVIDENCE_BUCKET`),
   - remediation: align lane handle to canonical key `S3_EVIDENCE_BUCKET`.
2. Green rerun:
   - execution: `m15c_point_in_time_policy_20260302T074401Z`,
   - verdict: `overall_pass=true`, `blocker_count=0`, `advisory_count=1`, `next_gate=M15.D_READY`.
3. Advisory retained:
   - `M15-AD3`: no mature-window rows in bounded 7-day profile; `M15.D` must widen historical extraction for mature-label dataset closure.
4. Local artifacts:
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_point_in_time_policy_spec.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_policy_validation_report.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_adversarial_probe_report.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_archive_truth_timeliness_contract.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_ieg_entity_relationship_pin.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_blocker_register.json`
   - `runs/dev_substrate/dev_full/m15/m15c_point_in_time_policy_20260302T074401Z/m15c_execution_summary.json`
5. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_point_in_time_policy_spec.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_policy_validation_report.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_adversarial_probe_report.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_archive_truth_timeliness_contract.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_ieg_entity_relationship_pin.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15c_point_in_time_policy_20260302T074401Z/m15c_execution_summary.json`

### M15.D - OFS Real Dataset Build
Goal:
1. Replace bootstrap OFS build logic with real data transformations and publish real manifest/fingerprint evidence.

DoD:
- [x] OFS build references real stream/truth surfaces.
- [x] manifests/fingerprints encode replay/as-of/maturity fields.
- [x] no bootstrap-only artifact is used for closure.
- [x] feature catalog is published with source lineage, availability horizon, leakage class, and null policy.

Blockers:
1. `M15-B5` OFS dataset correctness failure.
2. `M15-B7` evidence/readback parity failure.

M15.D execution strategy (locked):
1. Authority and entry inputs:
   - `M15.C` green execution summary and policy spec (`m15c_point_in_time_policy_20260302T074401Z`),
   - `M15.B` profile manifest/time/join/key reports (`m15b_semantic_profile_20260302T072457Z`),
   - dev_full handle pins for OFS paths/fingerprint requirements.
2. Compute and materialization lane:
   - managed compute path: Athena CTAS,
   - materialize a real supervised OFS dataset to object store under:
     - `s3://{S3_OBJECT_STORE_BUCKET}/learning/ofs/realized/{m15d_execution_id}/dataset/`.
3. M15.D v1 extraction policy (pinned):
   - keep M15.C as-of policy (`feature_asof_utc`, `label_asof_utc`, `label_maturity_days`),
   - satisfy `M15-AD3` by widening historical extraction to a mature window:
     - `cohort_end_utc = label_maturity_cutoff_utc`,
     - `cohort_start_utc = cohort_end_utc - 14 days`,
   - deterministic sample rule for bounded first-pass build:
     - `sample_mode = flow_id_modulo`,
     - `sample_modulus = 20`,
     - `sample_remainder = 0` (5% cohort),
   - filters and sample rule must be recorded in manifest/fingerprint.
4. Dataset semantics:
   - runtime feature surfaces:
     - `s3_flow_anchor_with_fraud_6B`,
     - `arrival_events_5B`,
   - truth surfaces:
     - `s4_flow_truth_labels_6B`,
     - `s4_flow_bank_view_6B`,
   - join keys:
     - `flow_id`,
     - `merchant_id + arrival_seq` for arrival enrichment,
   - supervised row eligibility requires mature truth label presence.
5. Required M15.D outputs:
   - dataset physical materialization (Parquet),
   - dataset manifest with replay/as-of/maturity/cohort filters,
   - dataset fingerprint including all `DATASET_FINGERPRINT_REQUIRED_FIELDS`,
   - time-bound and leakage audit,
   - feature catalog with lineage/availability horizon/leakage class/null policy.
6. Fail-closed checks:
   - zero mature-labeled rows,
   - any as-of/maturity boundary violation,
   - missing required fingerprint fields,
   - bootstrap/synthetic artifact used as source,
   - durable evidence publish/readback failure.
7. Verdict:
   - `ADVANCE_TO_M15_E` when blocker count is zero,
   - `BLOCKED_M15_D` otherwise.

M15.D artifact contract (phase-local):
1. `m15d_ofs_dataset_manifest.json`
2. `m15d_ofs_dataset_fingerprint.json`
3. `m15d_time_bound_leakage_audit.json`
4. `m15d_feature_catalog.json`
5. `m15d_materialization_receipt.json`
6. `m15d_blocker_register.json`
7. `m15d_execution_summary.json`

M15.D runtime/cost guardrails:
1. Target runtime <= 90 minutes.
2. Hard scan cap for M15.D v1 build: `250 GB`.
3. Emit query-count, scanned-bytes, and estimated Athena cost in the execution summary.

M15.D closure snapshot:
1. First attempt failed closed:
   - execution: `m15d_ofs_real_build_20260302T080027Z`,
   - blocker: `M15-B5` (`Athena CTAS build failed for M15.D`),
   - root cause: arrival surface field drift (`event_type` not present; actual field is `channel_group`).
2. Remediation:
   - updated M15.D real-data transform to use `arrival_channel_group <- arrival_events_5B.channel_group`.
3. Green rerun:
   - execution: `m15d_ofs_real_build_20260302T080146Z`,
   - verdict: `overall_pass=true`, `blocker_count=0`, `next_gate=M15.E_READY`.
4. Materialization and audit receipt:
   - dataset table: `fraud_platform_dev_full_ofs.ofs_m15d_m15d_ofs_real_build_20260302t080146z`,
   - dataset URI: `s3://fraud-platform-dev-full-object-store/learning/ofs/realized/m15d_ofs_real_build_20260302T080146Z/dataset/`,
   - row_count: `1,838,137`,
   - distinct_flows: `1,838,137`,
   - leakage/time checks: all pass (`feature_future_rows=0`, `label_future_rows=0`, `immature_label_rows=0`),
   - query_count: `4`,
   - scanned: `13.902 GB`,
   - estimated Athena cost: `$0.0679`.
5. Local artifacts:
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_ofs_dataset_manifest.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_ofs_dataset_fingerprint.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_time_bound_leakage_audit.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_feature_catalog.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_materialization_receipt.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_blocker_register.json`
   - `runs/dev_substrate/dev_full/m15/m15d_ofs_real_build_20260302T080146Z/m15d_execution_summary.json`
6. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_ofs_dataset_manifest.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_ofs_dataset_fingerprint.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_time_bound_leakage_audit.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_feature_catalog.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_materialization_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15d_ofs_real_build_20260302T080146Z/m15d_execution_summary.json`
7. Run-scoped OFS contract artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260302T080146Z/learning/ofs/dataset_manifest.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260302T080146Z/learning/ofs/dataset_fingerprint.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260302T080146Z/learning/ofs/time_bound_audit.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260302T080146Z/learning/ofs/feature_catalog.json`

### M15.E - MF Real-Data Train/Eval Rewire
Goal:
1. Ensure MF train/eval consumes OFS datasets directly and preserves provenance chain.

DoD:
- [ ] M11-equivalent eval report is tied to OFS dataset refs.
- [ ] lineage and rollback metadata remain complete.
- [ ] synthetic-generation path is not used for authoritative closure.
- [ ] explainability artifact set (feature importance/SHAP-equivalent) is tied to the real feature catalog.

Blockers:
1. `M15-B6` MF semantics mismatch to OFS input contract.

### M15.F - Leakage Adversarial Validation
Goal:
1. Prove guardrails hold under intentionally challenging temporal and truth-leak scenarios.

DoD:
- [ ] adversarial suite executed with deterministic verdicts.
- [ ] zero unresolved leakage blocker for closure path.
- [ ] leakage checks cover both feature engineering and label-join boundaries.

Blockers:
1. `M15-B4` leakage/future-boundary breach.

### M15.G - Semantic Non-Regression Pack
Goal:
1. Verify real-data realization does not regress M9/M10/M11 contracts.

DoD:
- [ ] replay/as-of/maturity continuity preserved.
- [ ] contract continuity pass across M9->M10->M11 semantic checkpoints.
- [ ] decision/evidence explainability payload continuity is validated against pre-M15 contracts.

Blockers:
1. `M15-B3` semantic continuity break.

### M15.H - Cost and Performance Closure
Goal:
1. Publish semantic-workload cost/performance receipts and enforce envelope.

DoD:
- [ ] phase budget receipt published.
- [ ] cost-to-outcome map present and attributable.
- [ ] runtime/perf posture within pinned envelope or approved waiver.

Blockers:
1. `M15-B8` cost/performance envelope breach.

### M15.I - Phase Rollup Verdict
Goal:
1. Aggregate `M15.A..M15.H` deterministically and emit gate verdict.

DoD:
- [ ] rollup matrix complete.
- [ ] blocker register and summary consistent.
- [ ] verdict is deterministic and reproducible.

### M15.J - Closure Sync
Goal:
1. Publish final M15 closure artifacts and handoff pack.

DoD:
- [ ] final summary and blocker register are parity-verified.
- [ ] closure artifacts are readable local + durable.
- [ ] next-gate handoff pack is emitted.

## 8) Global M15 Blocker Taxonomy
1. `M15-B1` contract ambiguity.
2. `M15-B2` profile/schema drift.
3. `M15-B3` as-of/maturity semantic mismatch.
4. `M15-B4` leakage/future boundary breach.
5. `M15-B5` OFS data-build correctness failure.
6. `M15-B6` MF eval semantic mismatch.
7. `M15-B7` evidence parity/readback failure.
8. `M15-B8` cost/perf envelope breach.

## 9) Runtime and Cost Targets (Initial Planning)
1. M15.A-C (contract/policy/profiling): target <= 90 minutes cumulative.
2. M15.D-E (real-data build + train/eval rewire): target <= 240 minutes cumulative.
3. M15.F-G (semantic validation/non-regression): target <= 120 minutes cumulative.
4. M15.H-I-J (cost/perf + rollup + closure): target <= 90 minutes cumulative.

All targets are planning baselines and may be repinned with measured evidence.

## 10) Evidence Contract
M15 artifacts must be published locally and durably under deterministic prefixes:
1. Local: `runs/dev_substrate/dev_full/m15/{execution_id}/`
2. Durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/{execution_id}/`

Minimum closure artifacts:
1. `m15_execution_summary.json`
2. `m15_blocker_register.json`
3. `m15_semantics_contract_matrix.json`
4. `m15_profile_report.json`
5. `m15_policy_validation_report.json`
6. `m15_cost_outcome_receipt.json`

## 11) Initial Status
1. M15 is active and `M15.A` + `M15.B` + `M15.C` + `M15.D` are closed green.
2. Next active entry gate is `M15.E`.

## 12) M15.A Closure Snapshot
1. Execution:
   - `m15a_contract_mapping_20260302T070156Z`
2. Verdict:
   - `overall_pass=true`
   - `blocker_count=0`
   - `verdict=ADVANCE_TO_M15_B`
   - `next_gate=M15.B_READY`
3. Local artifacts:
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_semantics_contract_matrix.json`
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_ieg_entity_map_candidates.json`
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_blocker_register.json`
   - `runs/dev_substrate/dev_full/m15/m15a_contract_mapping_20260302T070156Z/m15a_execution_summary.json`
4. Durable artifacts:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15a_contract_mapping_20260302T070156Z/m15a_semantics_contract_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15a_contract_mapping_20260302T070156Z/m15a_ieg_entity_map_candidates.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15a_contract_mapping_20260302T070156Z/m15a_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m15a_contract_mapping_20260302T070156Z/m15a_execution_summary.json`
