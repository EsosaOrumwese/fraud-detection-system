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

## 4) Pinned Decisions (Binding for M15)
1. Data-output semantics and ownership are anchored to `data_engine_interface.md`.
2. Runtime decision lanes must remain isolated from truth-only outputs (`s4_*`).
3. Learning inputs must remain replay-basis and as-of bounded (`origin_offset_ranges` mode continuity).
4. Label maturity is mandatory and enforced fail-closed.
5. Learning/evolution closure evidence must come from managed compute only.
6. Bootstrap-only OFS/MF placeholders cannot be used as closure evidence.

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
- [ ] data contract matrix published with no ambiguous ownership.
- [ ] every output ID is tagged `runtime`, `learning`, or `both` with explicit rules.
- [ ] unresolved semantic questions are fail-closed blockers, not assumptions.

Blockers:
1. `M15-B1` ambiguous ownership or unresolved semantic mapping.

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

DoD:
- [ ] profile report committed local + durable.
- [ ] all critical integrity checks either pass or are explicit blockers.

Blockers:
1. `M15-B2` schema/profile drift beyond policy.

### M15.C - Point-in-Time Policy Realization
Goal:
1. Pin executable policy for as-of joins, maturity lag, and leakage exclusions on real surfaces.

DoD:
- [ ] policy spec published and machine-checkable.
- [ ] adversarial edge cases are enumerated and tested.
- [ ] future-boundary and truth-surface misuse are fail-closed.

Blockers:
1. `M15-B3` point-in-time semantics mismatch.
2. `M15-B4` leakage boundary breach.

### M15.D - OFS Real Dataset Build
Goal:
1. Replace bootstrap OFS build logic with real data transformations and publish real manifest/fingerprint evidence.

DoD:
- [ ] OFS build references real stream/truth surfaces.
- [ ] manifests/fingerprints encode replay/as-of/maturity fields.
- [ ] no bootstrap-only artifact is used for closure.

Blockers:
1. `M15-B5` OFS dataset correctness failure.
2. `M15-B7` evidence/readback parity failure.

### M15.E - MF Real-Data Train/Eval Rewire
Goal:
1. Ensure MF train/eval consumes OFS datasets directly and preserves provenance chain.

DoD:
- [ ] M11-equivalent eval report is tied to OFS dataset refs.
- [ ] lineage and rollback metadata remain complete.
- [ ] synthetic-generation path is not used for authoritative closure.

Blockers:
1. `M15-B6` MF semantics mismatch to OFS input contract.

### M15.F - Leakage Adversarial Validation
Goal:
1. Prove guardrails hold under intentionally challenging temporal and truth-leak scenarios.

DoD:
- [ ] adversarial suite executed with deterministic verdicts.
- [ ] zero unresolved leakage blocker for closure path.

Blockers:
1. `M15-B4` leakage/future-boundary breach.

### M15.G - Semantic Non-Regression Pack
Goal:
1. Verify real-data realization does not regress M9/M10/M11 contracts.

DoD:
- [ ] replay/as-of/maturity continuity preserved.
- [ ] contract continuity pass across M9->M10->M11 semantic checkpoints.

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
1. M15 is planning-only (`NOT_STARTED`) while M14 execution continues.
2. No M15 subphase is active.
