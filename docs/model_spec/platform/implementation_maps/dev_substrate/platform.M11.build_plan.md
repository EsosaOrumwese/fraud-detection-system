# Dev Substrate Deep Plan - M11 (F1 Dev-Full Learning/Registry Authority + Runtime Closure)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M11._
_Last updated: 2026-02-22_

## 0) Purpose
M11 closes `F1` by proving Learning/Registry runtime authority is execution-ready on `dev_full` (bridged from the certified `dev_min` spine baseline) with no local compute dependency and no spine regression risk:
1. Required `OFS/MF/MPR` handles are explicit, concrete, and fail-closed.
2. Managed runtime decomposition (jobs/services/entrypoints) is deterministic and auditable.
3. IAM + secrets + data/messaging ownership boundaries are pinned for safe implementation.
4. Observability/evidence contracts are explicit before runtime build starts.
5. Spine carry-forward non-regression gates (`M8..M10`) are pinned as mandatory.
6. Cost/teardown continuity is preserved for Learning/Registry lanes.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` *(required; created/pinned by M11.A if absent)*
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md` *(required; created/pinned by M11.A if absent)*
4. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
5. `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
6. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
7. `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M10.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
3. M10 certification anchors:
   - local: `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
4. `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

## 2) Scope Boundary for M11
In scope:
1. Learning/Registry authority and required-handle closure in `dev_full`.
2. Runtime decomposition and entrypoint closure for:
   - OFS jobs,
   - MF jobs,
   - MPR runtime/control surfaces.
3. IAM/SSM/KMS and identity/authn closure for Learning/Registry lanes.
4. Data store and messaging ownership contracts for F1.
5. Observability/evidence and blocker taxonomy closure for M11 execution.
6. `M8..M10` carry-forward non-regression matrix pin.
7. Cost and teardown continuity posture pin for M11+ runtime lanes.
8. M11 verdict + M12 handoff artifact contract.

Out of scope:
1. OFS dataset build runtime execution (`M12`).
2. MF train/eval/publish runtime execution (`M13`).
3. Integrated full-platform certification runs (`M14`).
4. Production cutover.

## 3) M11 Deliverables
1. `M11.A` authority + M10 handoff closure snapshot.
2. `M11.B` Learning/Registry handle closure matrix snapshot.
3. `M11.C` runtime decomposition + entrypoint matrix snapshot.
4. `M11.D` IAM/secrets/KMS closure snapshot.
5. `M11.E` data-store ownership + path-contract snapshot.
6. `M11.F` messaging + governance/authn corridor closure snapshot.
7. `M11.G` observability/evidence schema + blocker taxonomy snapshot.
8. `M11.H` spine non-regression carry-forward matrix snapshot.
9. `M11.I` cost/teardown continuity snapshot.
10. `M11.J` verdict snapshot (`ADVANCE_TO_M12|HOLD_M11`) + `m12_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. `M10` is closed (`DONE`) with verdict `ADVANCE_CERTIFIED_DEV_MIN`.
2. M10 certification artifacts are readable locally and durably.
3. M11 is activated for planning expansion by explicit user direction.

Execution block:
1. No runtime implementation starts for Learning/Registry lanes until `M11.A..M11.J` planning closure is pass-complete.
2. No `M11` closure is allowed with unresolved handle/IAM/data/messaging ambiguity.
3. No `M11` closure is valid if non-regression matrix for `M8..M10` is missing.

## 4.1) Anti-cram Law (Binding for M11)
1. M11 is not execution-ready unless these lanes are explicit:
   - authority + handoff + required-handle closure,
   - runtime decomposition + entrypoint closure,
   - IAM + secrets + KMS,
   - data stores + ownership boundaries,
   - messaging + governance/authn corridor,
   - observability/evidence + blocker taxonomy,
   - spine non-regression carry-forward,
   - cost + teardown continuity,
   - verdict + handoff contract.
2. If a missing lane is discovered, M11 planning pauses and this file must be expanded before execution.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting owners | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + M10 handoff closure | M11.A | M11.J | handoff gate snapshot (`overall_pass=true`) |
| Required handle closure | M11.B | M11.J | zero unresolved required F1 handles |
| Runtime decomposition + entrypoints | M11.C | M11.J | deterministic OFS/MF/MPR runtime matrix |
| IAM + secrets + KMS closure | M11.D | M11.J | role/secret map with least-privilege checks |
| Data-store ownership closure | M11.E | M11.J | explicit owner map + concrete S3/RDS contract |
| Messaging + governance corridor | M11.F | M11.H | producer/consumer/authn matrix closure |
| Observability + evidence schemas | M11.G | M11.J | snapshot schema + evidence contract closure |
| Spine carry-forward non-regression matrix | M11.H | M11.J | pinned `M8..M10` rerun matrix + acceptance gates |
| Cost + teardown continuity | M11.I | M11.J | learning lane phase-profile + teardown invariants |
| Verdict + M12 handoff | M11.J | - | `ADVANCE_TO_M12` with blocker-free rollup |

## 5) Work Breakdown (Deep)

### M11.A Authority + M10 Handoff Closure
Goal:
1. Validate M10 closure posture and freeze M11 authority references.
2. Ensure M11 planning starts from immutable certified baseline.

Entry conditions:
1. `M10` is `DONE` in `platform.build_plan.md`.
2. M10 verdict is `ADVANCE_CERTIFIED_DEV_MIN`.
3. Source artifacts are readable with fail-closed fallback:
   - for each required artifact, at least one of local or durable source is readable.
   - local is preferred; durable is required fallback.

Required inputs:
1. M10 closure artifacts:
   - `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - `runs/dev_substrate/m10/m10_20260222T081047Z/m10_certification_bundle_index.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m10_20260222T081047Z/m10_certification_bundle_index.json`
2. M11 authority set (Section 1 sources in this file).
3. M11 cross-phase pins from main plan:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` Section `13.1` and `13.2`.
4. Dev-full authority package:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Preparation checks (fail-closed):
1. Validate source artifact readability:
   - local-preferred read, durable-fallback read for both required M10 artifacts.
2. Validate M10 verdict posture:
   - `verdict=ADVANCE_CERTIFIED_DEV_MIN`
   - `overall_pass=true`
   - blockers empty.
3. Validate source consistency:
   - `platform_run_id` parity across local/durable source artifacts.
   - no conflicting verdict across local/durable artifacts.
4. Validate authority set completeness:
   - every Section 1 source exists and is readable.
   - no unresolved "TBD" in M11.A authority-document references.
   - `TBD_M11B` required-handle values inside `dev_full_handles.registry.v0.md` are expected at M11.A and are closed in `M11.B`.
5. Validate M11 target-environment consistency:
   - M11 objective/scope/snapshot contracts reference `dev_full` as runtime target.
   - any remaining `dev_min` runtime target in M11 surfaces is treated as drift.

Deterministic closure algorithm (M11.A):
1. Load local M10 verdict artifact; if unreadable load durable artifact; if both fail -> `M11A-B1`.
2. Load local M10 bundle index artifact; if unreadable load durable artifact; if both fail -> `M11A-B1`.
3. Verify verdict posture:
   - mismatch from required M10 close state -> `M11A-B2`.
4. Verify source coherence:
   - run-scope or verdict inconsistency between local/durable -> `M11A-B4`.
5. Resolve and verify M11 authority inputs (Section 1):
   - any missing/unreadable authority -> `M11A-B3`.
6. Resolve and verify dev-full authority package:
   - missing `dev_full` authority docs -> `M11A-B7`.
7. Build deterministic authority matrix in fixed order:
   - primary authority refs,
   - supporting refs,
   - source artifact refs.
8. Emit `m11_a_authority_handoff_snapshot.json` locally.
9. Publish snapshot durably; publish failure -> `M11A-B5`.

Tasks:
1. Validate M10 verdict, blocker posture, and source readability.
2. Validate M11 authority set completeness (Section 1 docs).
3. Validate dev-full authority package presence/readability.
4. Emit `m11_a_authority_handoff_snapshot.json` (local + durable contract).

Required snapshot fields (`m11_a_authority_handoff_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.A"`.
2. `source_m10_verdict_local`, `source_m10_verdict_uri`.
3. `source_m10_bundle_index_local`, `source_m10_bundle_index_uri`.
4. `entry_gate_checks`.
5. `source_consistency_checks`.
6. `authority_refs` (primary + supporting).
7. `authority_readability_matrix`.
8. `target_environment` (`dev_full` expected).
9. `target_environment_consistency_checks`.
10. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.A` planning/closure target budget: <= 10 minutes wall clock.
2. Over-budget without user waiver is blocker state (`M11A-B6`).

DoD:
- [x] M10 handoff gate is pass-closed and blocker-free.
- [x] M11 authority list is complete and concrete for M11.A scope.
- [x] M10 local/durable artifact coherence is verified.
- [x] Dev-full authority package is present and readable.
- [x] Target environment consistency confirms `dev_full`.
- [x] Snapshot schema for M11.A is pinned.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_a_authority_handoff_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_a_authority_handoff_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Transitional publication note:
   - `M11.A` durable publish reused existing run-control evidence lane; dev-full evidence handle pin remains part of `M11.B`.

Blockers:
1. `M11A-B1`: M10 handoff unreadable/invalid.
2. `M11A-B2`: M10 verdict mismatch or blocker residue.
3. `M11A-B3`: M11 authority set incomplete.
4. `M11A-B4`: local/durable source inconsistency.
5. `M11A-B5`: snapshot publication failure.
6. `M11A-B6`: runtime budget breach without waiver.
7. `M11A-B7`: required dev-full authority package missing/unreadable.

### M11.B Learning/Registry Handle Closure Matrix
Goal:
1. Close all required F1 handle surfaces before build execution.
2. Eliminate wildcard/placeholder handle usage.

Entry conditions:
1. `M11.A` closure snapshot exists locally and durably.
2. `M11.A` snapshot reports `overall_pass=true` and blocker union empty.
3. `M11` remains `ACTIVE` in `platform.build_plan.md`.
4. `dev_full_handles.registry.v0.md` is present/readable and still under v0 fail-closed posture.

Required inputs:
1. `M11.A` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_a_authority_handoff_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_a_authority_handoff_snapshot.json` (transitional evidence lane).
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`.
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Section `13.1` + `13.2`).

Required-handle set for F1 closure (authoritative in M11.B):
1. `DF_AWS_REGION`
2. `DF_EVIDENCE_BUCKET`
3. `DF_EVIDENCE_PREFIX_PATTERN`
4. `DF_RUNTIME_CLUSTER_HANDLE`
5. `DF_RUNTIME_EXECUTION_ROLE`
6. `DF_OFS_DATA_ROOT`
7. `DF_LABEL_TIMELINE_ROOT`
8. `DF_FEATURE_STORE_HANDLE`
9. `DF_TRAINING_JOB_HANDLE`
10. `DF_MODEL_ARTIFACT_ROOT`
11. `DF_MODEL_REGISTRY_HANDLE`
12. `DF_PROMOTION_APPROVAL_CHANNEL`
13. `DF_ROLLBACK_CHANNEL`
14. `DF_ORCHESTRATION_HANDLE`
15. `DF_METRICS_SINK_HANDLE`
16. `DF_ALERTING_CHANNEL_HANDLE`
17. `DF_COST_GUARDRAIL_HANDLE`
18. `DF_TEARDOWN_WORKFLOW_HANDLE`

Required closure categories:
1. Runtime identities and execution:
   - `DF_RUNTIME_CLUSTER_HANDLE`, `DF_RUNTIME_EXECUTION_ROLE`, `DF_TRAINING_JOB_HANDLE`.
2. Data surfaces and evidence:
   - `DF_OFS_DATA_ROOT`, `DF_LABEL_TIMELINE_ROOT`, `DF_FEATURE_STORE_HANDLE`, `DF_MODEL_ARTIFACT_ROOT`, `DF_EVIDENCE_BUCKET`, `DF_EVIDENCE_PREFIX_PATTERN`.
3. Registry/governance corridor:
   - `DF_MODEL_REGISTRY_HANDLE`, `DF_PROMOTION_APPROVAL_CHANNEL`, `DF_ROLLBACK_CHANNEL`.
4. Run/operate and observability:
   - `DF_ORCHESTRATION_HANDLE`, `DF_METRICS_SINK_HANDLE`, `DF_ALERTING_CHANNEL_HANDLE`, `DF_COST_GUARDRAIL_HANDLE`, `DF_TEARDOWN_WORKFLOW_HANDLE`.
5. Region/core constants:
   - `DF_AWS_REGION`.

Preparation checks (fail-closed):
1. Read M11.A snapshot (local preferred, durable fallback).
2. Verify `M11.A` predicate:
   - `overall_pass=true`,
   - blockers empty,
   - `target_environment=dev_full`.
3. Parse Section 3 required-handle table in `dev_full_handles.registry.v0.md`:
   - all required keys present exactly once,
   - no duplicate keys,
   - no missing key from M11.B required-handle set.
4. Value-quality checks:
   - unresolved markers (`TBD_M11B`, empty, null) are blockers,
   - placeholder/wildcard markers (`TBD`, `REPLACE_ME`, `*`) are blockers for required keys.
5. Ownership mapping checks:
   - each handle maps to exactly one owner lane (`M11.C/M11.D/M11.E/M11.F/M11.G/M11.H/M11.I`) for downstream closure.

Deterministic closure algorithm (M11.B):
1. Resolve M11.A snapshot (local preferred, durable fallback); unreadable -> `M11B-B6`.
2. Verify M11.A pass posture; mismatch -> `M11B-B6`.
3. Load `dev_full_handles.registry.v0.md`; unreadable -> `M11B-B4`.
4. Resolve each required handle key by exact match from Section 3 table.
5. Build deterministic resolution matrix in fixed key order (`1..18` above):
   - `key`,
   - `status` (`PINNED|UNRESOLVED|PLACEHOLDER`),
   - `value`,
   - `closure_owner_subphase`,
   - `notes`.
6. Compute closure counters:
   - `required_total`,
   - `resolved_count`,
   - `unresolved_count`,
   - `placeholder_or_wildcard_count`,
   - `ownership_ambiguity_count`,
   - `missing_or_duplicate_key_count`.
7. Apply fail-closed blocker mapping:
   - unresolved -> `M11B-B1`,
   - placeholder/wildcard -> `M11B-B2`,
   - ownership ambiguity -> `M11B-B3`,
   - missing/duplicate key -> `M11B-B4`.
8. Emit `m11_b_handle_closure_snapshot.json` locally.
9. Publish durable snapshot; publish failure -> `M11B-B5`.

Required snapshot fields (`m11_b_handle_closure_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.B"`.
2. `m11a_source_ref_local`, `m11a_source_ref_uri`, `m11a_source_mode`.
3. `required_handle_set` (ordered list).
4. `resolution_matrix` (one row per required key).
5. `closure_counters`.
6. `owner_mapping_matrix` (`key -> M11.C/M11.D/M11.E/M11.F/M11.G/M11.H/M11.I`).
7. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.B` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11B-B7`.

DoD:
- [x] M11.A source snapshot is pass-closed and linked.
- [x] Required F1 handle set (`1..18`) is explicit and versioned.
- [x] Required-handle unresolved count is zero.
- [x] Placeholder/wildcard required-handle count is zero.
- [x] Missing/duplicate required-key count is zero.
- [x] Owner mapping to downstream sub-phases is complete and non-ambiguous.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_b_handle_closure_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_b_handle_closure_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
   - `resolved_count=18`, `required_total=18`
4. Publication note:
   - durable publish remains on transitional run-control lane until dev-full evidence bucket materialization closure in downstream lanes.

Blockers:
1. `M11B-B1`: unresolved required handle.
2. `M11B-B2`: wildcard/placeholder required handle.
3. `M11B-B3`: handle ownership ambiguity across components/sub-phases.
4. `M11B-B4`: required key missing/duplicate or registry parse failure.
5. `M11B-B5`: snapshot publication failure.
6. `M11B-B6`: M11.A dependency unreadable or not pass-closed.
7. `M11B-B7`: runtime budget breach without waiver.

### M11.C Runtime Decomposition + Entrypoint Closure
Goal:
1. Pin exact managed runtime topology for OFS/MF/MPR.
2. Ensure no lane depends on local/laptop execution.

Entry conditions:
1. `M11.B` snapshot exists locally and durably.
2. `M11.B` reports `overall_pass=true` with blocker union empty.
3. Required runtime handles from `dev_full_handles.registry.v0.md` are pinned and non-placeholder:
   - `DF_RUNTIME_CLUSTER_HANDLE`
   - `DF_RUNTIME_EXECUTION_ROLE`
   - `DF_ORCHESTRATION_HANDLE`
   - `DF_TRAINING_JOB_HANDLE`.

Required inputs:
1. `M11.B` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_b_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_b_handle_closure_snapshot.json`.
2. Runtime implementation surfaces:
   - `src/fraud_detection/offline_feature_plane/worker.py`
   - `src/fraud_detection/model_factory/worker.py`
   - `src/fraud_detection/learning_registry/contracts.py`
3. Runtime profile/pack contracts:
   - `config/platform/profiles/dev_full.yaml`
   - `config/platform/run_operate/packs/dev_full_learning_jobs.v0.yaml`
4. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.

Preparation checks (fail-closed):
1. Resolve M11.B snapshot (local preferred, durable fallback) and verify pass posture.
2. Parse required runtime handles and assert no unresolved/placeholder value.
3. Verify OFS/MF entrypoint modules expose CLI main and required `run` command posture.
4. Verify dev_full profile/pack artifacts exist and reference dev_full runtime surfaces.
5. Verify MPR runtime mode is explicitly non-local and bound to orchestration handle.

Deterministic closure algorithm (M11.C):
1. Resolve M11.B snapshot; unreadable or non-pass -> `M11C-B4`.
2. Resolve runtime handle set from registry; unresolved/placeholder -> `M11C-B2`.
3. Build deterministic runtime decomposition matrix for lanes:
   - OFS lane:
     - mode: `ECS_RUN_TASK`,
     - entrypoint: `python -m fraud_detection.offline_feature_plane.worker --profile config/platform/profiles/dev_full.yaml run --once`,
     - role: `DF_RUNTIME_EXECUTION_ROLE`,
     - cluster: `DF_RUNTIME_CLUSTER_HANDLE`.
   - MF lane:
     - mode: `ECS_RUN_TASK`,
     - entrypoint: `python -m fraud_detection.model_factory.worker --profile config/platform/profiles/dev_full.yaml run --once`,
     - role: `DF_RUNTIME_EXECUTION_ROLE`,
     - cluster: `DF_RUNTIME_CLUSTER_HANDLE`.
   - MPR lane:
     - mode: `AIRFLOW_DAG_CONTROL`,
     - entrypoints:
       - promotion trigger from `DF_PROMOTION_APPROVAL_CHANNEL`,
       - rollback trigger from `DF_ROLLBACK_CHANNEL`,
     - run/operate orchestration anchor: `DF_ORCHESTRATION_HANDLE`.
4. Validate command conformance:
   - module import/help checks pass for OFS/MF worker commands under pack env (`PYTHONPATH=src`),
   - no lane references `local_parity` profile or local filesystem-only runtime root.
5. Emit `m11_c_runtime_decomposition_snapshot.json` locally.
6. Publish durable snapshot; publish failure -> `M11C-B5`.

Required snapshot fields (`m11_c_runtime_decomposition_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.C"`.
2. `m11b_source_ref_local`, `m11b_source_ref_uri`, `m11b_source_mode`.
3. `runtime_handle_refs` (resolved key/value set used by C).
4. `runtime_decomposition_matrix` (lane/mode/entrypoint/role/cluster/orchestration bindings).
5. `entrypoint_validation_checks`.
6. `profile_pack_conformance_checks`.
7. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.C` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11C-B6`.

DoD:
- [x] M11.B dependency is pass-closed and linked.
- [x] Runtime mode is pinned for OFS/MF/MPR with no ambiguity.
- [x] Entrypoint matrix is complete and command-valid.
- [x] No local runtime path remains in authoritative flow.
- [x] Profile/pack contracts for dev_full learning lanes are present.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_c_runtime_decomposition_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_c_runtime_decomposition_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Runtime contract artifacts materialized:
   - `config/platform/profiles/dev_full.yaml`
   - `config/platform/run_operate/packs/dev_full_learning_jobs.v0.yaml`

Blockers:
1. `M11C-B1`: missing/invalid entrypoint for required lane.
2. `M11C-B2`: runtime mode ambiguity or unresolved runtime handle.
3. `M11C-B3`: local-runtime dependency detected.
4. `M11C-B4`: M11.B dependency unreadable or not pass-closed.
5. `M11C-B5`: snapshot publication failure.
6. `M11C-B6`: runtime budget breach without waiver.

### M11.D IAM + Secrets + KMS Closure
Goal:
1. Pin least-privilege role map and secret materialization for Learning/Registry lanes.
2. Ensure fail-closed secret posture before execution.

Entry conditions:
1. `M11.C` snapshot exists locally and durably.
2. `M11.C` reports `overall_pass=true` with blocker union empty.
3. Runtime topology in M11.C is fixed for OFS/MF/MPR lanes.

Required inputs:
1. `M11.C` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_c_runtime_decomposition_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_c_runtime_decomposition_snapshot.json`.
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`.

Required IAM/secret handles for D closure:
1. `DF_OFS_TASK_ROLE_ARN`
2. `DF_MF_TASK_ROLE_ARN`
3. `DF_MPR_CONTROL_ROLE_ARN`
4. `DF_KMS_KEY_ALIAS`
5. `DF_SSM_OFS_RUN_LEDGER_DSN_PATH`
6. `DF_SSM_MF_RUN_LEDGER_DSN_PATH`
7. `DF_SSM_RUNTIME_DB_DSN_PATH`
8. `DF_SSM_MLFLOW_TRACKING_URI_PATH`
9. `DF_SSM_DATABRICKS_HOST_PATH`
10. `DF_SSM_DATABRICKS_TOKEN_PATH`
11. `DF_SSM_AIRFLOW_API_TOKEN_PATH`

Preparation checks (fail-closed):
1. Resolve M11.C snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required IAM/secret handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Role-mapping checks:
   - each lane (`OFS`, `MF`, `MPR`) has exactly one role handle,
   - no lane role is empty.
4. Secret-path checks:
   - each required SSM path is absolute (`/fraud-platform/dev_full/...`),
   - no duplicate secret path across different semantic surfaces.
5. KMS checks:
   - alias/key handle present and syntactically valid (`alias/...` or `arn:...`).

Deterministic closure algorithm (M11.D):
1. Resolve M11.C snapshot; unreadable or non-pass -> `M11D-B4`.
2. Resolve required IAM/secret handles from registry; missing/unresolved -> `M11D-B1` or `M11D-B2`.
3. Build lane role map:
   - `OFS -> DF_OFS_TASK_ROLE_ARN`,
   - `MF -> DF_MF_TASK_ROLE_ARN`,
   - `MPR -> DF_MPR_CONTROL_ROLE_ARN`.
4. Build secret materialization matrix:
   - path, owner lane, secret class, materialization policy (`required_before_runtime=true`).
5. Build least-privilege mapping matrix:
   - role -> allowed surface families (object store prefixes, SSM path prefixes, orchestration controls).
6. Validate KMS mapping for secret-bearing surfaces.
7. Emit `m11_d_iam_secret_kms_snapshot.json` locally.
8. Publish durable snapshot; publish failure -> `M11D-B5`.

Required snapshot fields (`m11_d_iam_secret_kms_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.D"`.
2. `m11c_source_ref_local`, `m11c_source_ref_uri`, `m11c_source_mode`.
3. `lane_role_map`.
4. `secret_path_matrix`.
5. `kms_binding_matrix`.
6. `least_privilege_matrix`.
7. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.D` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11D-B6`.

DoD:
- [x] M11.C dependency is pass-closed and linked.
- [x] Each required lane has exactly one runtime task/control role.
- [x] Secret sources/paths are explicit, unique, and non-placeholder.
- [x] KMS binding surface is explicit for secret-bearing materials.
- [x] Snapshot documents role/secret/kms least-privilege closure.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_d_iam_secret_kms_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_d_iam_secret_kms_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty

Blockers:
1. `M11D-B1`: unresolved runtime role handle.
2. `M11D-B2`: missing/invalid required SSM secret path handle.
3. `M11D-B3`: privilege overreach or role/surface mismatch.
4. `M11D-B4`: M11.C dependency unreadable or not pass-closed.
5. `M11D-B5`: snapshot publication failure.
6. `M11D-B6`: runtime budget breach without waiver.

### M11.E Data-Store Ownership + Path Contracts
Goal:
1. Pin deterministic ownership and path contracts for archive/features/models/registry/evidence.
2. Prevent cross-plane truth collisions.

Entry conditions:
1. `M11.D` snapshot exists locally and durably.
2. `M11.D` reports `overall_pass=true` with blocker union empty.
3. Data-store/path-contract handles required by E are pinned and non-placeholder.

Required inputs:
1. `M11.D` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_d_iam_secret_kms_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_d_iam_secret_kms_snapshot.json`.
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
3. Local-parity ownership truth references:
   - `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
   - `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`.
4. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`.

Required data-contract handles for E closure:
1. `DF_SPINE_ARCHIVE_ROOT`
2. `DF_OFS_DATA_ROOT`
3. `DF_LABEL_TIMELINE_ROOT`
4. `DF_DATASET_MANIFEST_ROOT`
5. `DF_EVAL_REPORT_ROOT`
6. `DF_FEATURE_STORE_HANDLE`
7. `DF_MODEL_ARTIFACT_ROOT`
8. `DF_MODEL_REGISTRY_HANDLE`
9. `DF_REGISTRY_EVENT_ROOT`
10. `DF_EVIDENCE_BUCKET`
11. `DF_EVIDENCE_PREFIX_PATTERN`
12. `DF_DATASET_RETENTION_DAYS`
13. `DF_EVAL_REPORT_RETENTION_DAYS`
14. `DF_MODEL_ARTIFACT_RETENTION_DAYS`
15. `DF_EVIDENCE_RETENTION_DAYS`

Preparation checks (fail-closed):
1. Resolve M11.D snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required E handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Build candidate owner matrix and assert one-owner truth law:
   - each truth surface has exactly one writer owner,
   - readers may be multiple but cannot claim ownership.
4. Path-conflict checks:
   - concrete path/prefix values are pairwise non-identical for independent truth surfaces,
   - no learning root collides with spine archive root.
5. Run-scope checks:
   - run-scoped surfaces explicitly include `{platform_run_id}` or equivalent run partitioning,
   - global registry surfaces are explicitly marked non-run-scoped.
6. Retention checks:
   - retention-day handles parse as positive integers,
   - immutable-governance surfaces are marked append-only/non-destructive.

Deterministic closure algorithm (M11.E):
1. Resolve M11.D snapshot; unreadable or non-pass -> `M11E-B4`.
2. Resolve required E handles from registry; unresolved/placeholder -> `M11E-B2`.
3. Build deterministic data-store owner matrix in fixed order:
   - spine archive truth,
   - label timeline truth,
   - OFS dataset manifests/eval outputs,
   - feature store materialization,
   - MF model artifacts,
   - MPR registry state/events,
   - evidence artifacts.
4. Evaluate owner uniqueness and overlap rules:
   - any multi-owner truth surface -> `M11E-B1`.
5. Evaluate path/prefix conflict rules:
   - any unresolved/duplicate/conflicting contract -> `M11E-B2`.
6. Evaluate run-scope semantics:
   - mismatch between declared scope and path contract -> `M11E-B3`.
7. Evaluate retention predicates and append-only posture.
8. Emit `m11_e_data_contract_snapshot.json` locally.
9. Publish durable snapshot; publish failure -> `M11E-B5`.

Required snapshot fields (`m11_e_data_contract_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.E"`.
2. `m11d_source_ref_local`, `m11d_source_ref_uri`, `m11d_source_mode`.
3. `required_handle_refs` (resolved key/value set used by E).
4. `data_store_owner_matrix` (surface/owner/readers/path/scope/append_only).
5. `path_contract_checks`.
6. `run_scope_semantics_checks`.
7. `retention_policy_matrix`.
8. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.E` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11E-B6`.

DoD:
- [x] Data-store owner matrix has zero overlaps on truth ownership.
- [x] Path patterns are concrete and non-conflicting.
- [x] Required run-scope semantics are explicit (`platform_run_id` vs global registry events where applicable).
- [x] Retention posture for learning artifacts is explicit and parse-valid.
- [x] Snapshot captures owner + path + retention contract.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_e_data_contract_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_e_data_contract_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Data-contract handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 7 (`DF_SPINE_ARCHIVE_ROOT`, dataset/eval/registry roots, retention handles).

Blockers:
1. `M11E-B1`: ownership overlap/ambiguity.
2. `M11E-B2`: path conflict or unresolved prefix contract.
3. `M11E-B3`: run-scope semantics mismatch.
4. `M11E-B4`: M11.D dependency unreadable or not pass-closed.
5. `M11E-B5`: snapshot publication failure.
6. `M11E-B6`: runtime budget breach without waiver.

### M11.F Messaging + Governance/Authn Corridor Closure
Goal:
1. Pin learning-plane messaging interfaces and governance writer-boundary authn requirements.
2. Ensure MPR corridor semantics are explicit and fail-closed.

Entry conditions:
1. `M11.E` snapshot exists locally and durably.
2. `M11.E` reports `overall_pass=true` with blocker union empty.
3. Messaging/governance/authn handles required by F are pinned and non-placeholder.

Required inputs:
1. `M11.E` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_e_data_contract_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_e_data_contract_snapshot.json`.
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
3. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`.
4. `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`.
5. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`.

Required messaging/authn handles for F closure:
1. `DF_LEARNING_EVENT_BUS_HANDLE`
2. `DF_LEARNING_EVENT_TOPIC`
3. `DF_GOVERNANCE_EVENT_TOPIC`
4. `DF_REGISTRY_EVENT_TOPIC`
5. `DF_MPR_AUTHN_MODE`
6. `DF_MPR_ALLOWED_SYSTEM_ACTORS`
7. `DF_MPR_ALLOWED_HUMAN_ACTORS`
8. `DF_MPR_RESOLUTION_ORDER`
9. `DF_MPR_FAIL_CLOSED_ON_INCOMPATIBLE`
10. `DF_PROMOTION_APPROVAL_CHANNEL`
11. `DF_ROLLBACK_CHANNEL`
12. `DF_MPR_PROMOTION_TRIGGER_CMD`
13. `DF_MPR_ROLLBACK_TRIGGER_CMD`

Preparation checks (fail-closed):
1. Resolve M11.E snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required F handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Build producer/consumer ownership matrix and assert:
   - each event family has exactly one producer owner,
   - consumer set is explicit and non-empty.
4. Governance/authn checks:
   - MPR actor model is explicit for `SYSTEM` and `HUMAN`,
   - authn mode is explicit and non-open.
5. Corridor semantics checks:
   - promotion and rollback triggers are pinned and deterministic,
   - resolution order is explicit and includes fail-closed terminal posture.

Deterministic closure algorithm (M11.F):
1. Resolve M11.E snapshot; unreadable or non-pass -> `M11F-B4`.
2. Resolve required F handles from registry; unresolved/placeholder -> `M11F-B2`.
3. Build deterministic messaging ownership matrix in fixed order:
   - OFS dataset/evidence lifecycle events,
   - MF publish/eval lifecycle events,
   - MPR registry lifecycle events,
   - governance audit/anomaly events.
4. Validate ownership uniqueness and non-overlap:
   - ambiguity or multi-producer event family -> `M11F-B1`.
5. Build governance/authn corridor matrix:
   - action type, required actor class, authn mode, allowed actor set.
6. Validate MPR corridor semantics:
   - promotion/rollback channels and trigger commands pinned,
   - compatibility mismatch posture is fail-closed,
   - resolution order explicit and deterministic.
7. Emit `m11_f_messaging_governance_snapshot.json` locally.
8. Publish durable snapshot; publish failure -> `M11F-B5`.

Required snapshot fields (`m11_f_messaging_governance_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.F"`.
2. `m11e_source_ref_local`, `m11e_source_ref_uri`, `m11e_source_mode`.
3. `required_handle_refs` (resolved key/value set used by F).
4. `messaging_ownership_matrix` (event_family/producer/consumers/topic_or_channel).
5. `governance_authn_matrix` (action/authn_mode/allowed_actors/fail_closed).
6. `mpr_corridor_checks`.
7. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.F` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11F-B6`.

DoD:
- [x] Messaging ownership matrix is explicit and non-overlapping.
- [x] Governance action authn/actor requirements are explicit.
- [x] MPR fail-closed compatibility/resolution expectations are pinned.
- [x] Snapshot captures corridor contract and acceptance checks.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_f_messaging_governance_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_f_messaging_governance_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Messaging/governance handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 8 (`DF_LEARNING_EVENT_BUS_HANDLE`, `DF_*_TOPIC`, MPR authn/actor/resolution handles).

Blockers:
1. `M11F-B1`: messaging ownership ambiguity.
2. `M11F-B2`: missing governance/authn requirement for MPR actions.
3. `M11F-B3`: unresolved promotion/rollback corridor semantics.
4. `M11F-B4`: M11.E dependency unreadable or not pass-closed.
5. `M11F-B5`: snapshot publication failure.
6. `M11F-B6`: runtime budget breach without waiver.

### M11.G Observability/Evidence + Blocker Taxonomy Closure
Goal:
1. Pin required evidence artifacts and schemas for M11 and downstream M12/M13 entry.
2. Pin blocker taxonomy families for deterministic fail-closed adjudication.

Entry conditions:
1. `M11.F` snapshot exists locally and durably.
2. `M11.F` reports `overall_pass=true` with blocker union empty.
3. Observability/evidence handles required by G are pinned and non-placeholder.

Required inputs:
1. `M11.F` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_f_messaging_governance_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_f_messaging_governance_snapshot.json`.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M11.build_plan.md`.
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
4. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`.

Required observability/evidence handles for G closure:
1. `DF_EVIDENCE_BUCKET`
2. `DF_EVIDENCE_PREFIX_PATTERN`
3. `DF_METRICS_SINK_HANDLE`
4. `DF_ALERTING_CHANNEL_HANDLE`
5. `DF_GOVERNANCE_EVENT_TOPIC`
6. `DF_M11_EVIDENCE_SCHEMA_VERSION`
7. `DF_M11_REQUIRED_EVIDENCE_FAMILIES`
8. `DF_M11_BLOCKER_TAXONOMY_MODE`
9. `DF_M11_NON_SECRET_EVIDENCE_POLICY`

Preparation checks (fail-closed):
1. Resolve M11.F snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required G handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Validate required evidence family list for `M11.A..M11.F` is explicit.
4. Validate minimum snapshot schema contract is explicit and reusable.
5. Validate blocker taxonomy coverage exists across `M11A-B*` .. `M11J-B*` patterns.
6. Validate non-secret evidence policy is explicit and non-open.

Deterministic closure algorithm (M11.G):
1. Resolve M11.F snapshot; unreadable or non-pass -> `M11G-B4`.
2. Resolve required G handles from registry; unresolved/placeholder -> `M11G-B2`.
3. Build required evidence family matrix:
   - `m11_a_authority_handoff_snapshot.json`,
   - `m11_b_handle_closure_snapshot.json`,
   - `m11_c_runtime_decomposition_snapshot.json`,
   - `m11_d_iam_secret_kms_snapshot.json`,
   - `m11_e_data_contract_snapshot.json`,
   - `m11_f_messaging_governance_snapshot.json`.
4. Validate each required family exists under active `m11_execution_id`; missing family -> `M11G-B1`.
5. Extract blocker taxonomy tokens from this file and verify coverage for each M11 sub-phase family (`A..J`); missing family -> `M11G-B3`.
6. Build minimum snapshot-schema contract for reuse in `M11.H/I/J` and `M12/M13` entry checks.
7. Emit `m11_g_observability_evidence_snapshot.json` locally.
8. Publish durable snapshot; publish failure -> `M11G-B5`.

Required snapshot fields (`m11_g_observability_evidence_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.G"`.
2. `m11f_source_ref_local`, `m11f_source_ref_uri`, `m11f_source_mode`.
3. `required_handle_refs` (resolved key/value set used by G).
4. `required_evidence_family_matrix`.
5. `minimum_snapshot_schema_contract`.
6. `blocker_taxonomy_matrix`.
7. `non_secret_evidence_policy`.
8. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.G` target budget: <= 15 minutes.
2. Over-budget without user waiver -> `M11G-B6`.

DoD:
- [x] Required evidence family list is complete and scoped.
- [x] Snapshot schema contract is explicit and reusable.
- [x] Blocker taxonomy and rollup contract are pinned.
- [x] Non-secret evidence policy is explicit.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_g_observability_evidence_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_g_observability_evidence_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Observability/evidence handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 9 (`DF_M11_EVIDENCE_SCHEMA_VERSION`, `DF_M11_REQUIRED_EVIDENCE_FAMILIES`, taxonomy and non-secret policy handles).

Blockers:
1. `M11G-B1`: missing required evidence family.
2. `M11G-B2`: snapshot schema incomplete/ambiguous.
3. `M11G-B3`: blocker taxonomy/rollup contract missing.
4. `M11G-B4`: M11.F dependency unreadable or not pass-closed.
5. `M11G-B5`: snapshot publication failure.
6. `M11G-B6`: runtime budget breach without waiver.

### M11.H Spine Carry-Forward Non-Regression Matrix
Goal:
1. Convert `M8..M10` carry-forward law into executable acceptance matrix for `M11+`.
2. Prevent false green claims that break certified spine behavior.

Entry conditions:
1. `M11.G` snapshot exists locally and durably.
2. `M11.G` reports `overall_pass=true` with blocker union empty.
3. Non-regression source handles are pinned and non-placeholder.

Required inputs:
1. `M11.G` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_g_observability_evidence_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_g_observability_evidence_snapshot.json`.
2. Carry-forward source snapshots:
   - `M8` verdict snapshot (`m8_i_verdict_snapshot.json`),
   - `M9` verdict snapshot (`m9_i_verdict_snapshot.json`),
   - `M10` certification verdict snapshot (`m10_j_certification_verdict_snapshot.json`).
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`.

Required non-regression handles for H closure:
1. `DF_M11_NON_REGRESSION_M8_VERDICT_LOCAL`
2. `DF_M11_NON_REGRESSION_M9_VERDICT_LOCAL`
3. `DF_M11_NON_REGRESSION_M10_VERDICT_LOCAL`
4. `DF_M11_NON_REGRESSION_BLOCKER_MODE`
5. `DF_M11_NON_REGRESSION_RERUN_POLICY`

Preparation checks (fail-closed):
1. Resolve M11.G snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required H handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Resolve M8/M9/M10 source snapshots and verify readability.
4. Validate each source verdict is pass-closed and non-blocked.
5. Validate rerun policy and blocker mode are explicit fail-closed postures.

Deterministic closure algorithm (M11.H):
1. Resolve M11.G snapshot; unreadable or non-pass -> `M11H-B4`.
2. Resolve required H handles from registry; unresolved/placeholder -> `M11H-B2`.
3. Load M8/M9/M10 source verdict snapshots from pinned local paths; unreadable source -> `M11H-B3`.
4. Build non-regression probe matrix in fixed order:
   - Probe `NR-M8-OBS_GOV_VERDICT`: M8 verdict `overall_pass=true`,
   - Probe `NR-M9-TEARDOWN_COST_VERDICT`: M9 verdict `overall_pass=true`,
   - Probe `NR-M10-CERTIFICATION_VERDICT`: M10 verdict `overall_pass=true` and `verdict=ADVANCE_CERTIFIED_DEV_MIN`.
5. Apply acceptance thresholds:
   - all probes must pass; any probe fail -> `M11H-B1`.
6. Apply blocker mode:
   - blocker mode must be `fail_closed_union`; mismatch -> `M11H-B2`.
7. Emit `m11_h_non_regression_matrix_snapshot.json` locally.
8. Publish durable snapshot; publish failure -> `M11H-B5`.

Required snapshot fields (`m11_h_non_regression_matrix_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.H"`.
2. `m11g_source_ref_local`, `m11g_source_ref_uri`, `m11g_source_mode`.
3. `required_handle_refs` (resolved key/value set used by H).
4. `source_snapshot_matrix` (M8/M9/M10 refs and readability).
5. `non_regression_probe_matrix` (probe/predicate/pass/failure_reason).
6. `acceptance_thresholds`.
7. `rerun_policy`.
8. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.H` target budget: <= 20 minutes.
2. Over-budget without user waiver -> `M11H-B6`.

DoD:
- [x] Non-regression matrix has explicit probes, thresholds, and owners.
- [x] Each probe has deterministic evidence source paths.
- [x] Failure mapping to blockers is explicit and fail-closed.
- [x] Matrix is approved as mandatory for `M11..M14`.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_h_non_regression_matrix_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_h_non_regression_matrix_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Carry-forward handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 10 (`DF_M11_NON_REGRESSION_*` handles).

Blockers:
1. `M11H-B1`: missing critical probe for M8/M9/M10 carry-forward.
2. `M11H-B2`: threshold/acceptance ambiguity.
3. `M11H-B3`: probe evidence source undefined/unreadable.
4. `M11H-B4`: M11.G dependency unreadable or not pass-closed.
5. `M11H-B5`: snapshot publication failure.
6. `M11H-B6`: runtime budget breach without waiver.

### M11.I Cost + Teardown Continuity for Learning Lanes
Goal:
1. Keep post-M10 cost discipline intact while adding learning runtime lanes.
2. Ensure learning lanes integrate into existing destroy/guardrail posture.

Entry conditions:
1. `M11.H` snapshot exists locally and durably.
2. `M11.H` reports `overall_pass=true` with blocker union empty.
3. Cost/teardown continuity handles required by I are pinned and non-placeholder.

Required inputs:
1. `M11.H` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_h_non_regression_matrix_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_h_non_regression_matrix_snapshot.json`.
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M9.build_plan.md`.
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`.

Required continuity handles for I closure:
1. `DF_COST_GUARDRAIL_HANDLE`
2. `DF_TEARDOWN_WORKFLOW_HANDLE`
3. `DF_M11_LEARNING_PHASE_PROFILE_POLICY`
4. `DF_M11_LEARNING_DEFAULT_DESIRED_COUNT`
5. `DF_M11_LEARNING_JOB_EXECUTION_MODE`
6. `DF_M11_LEARNING_IDLE_TTL_MINUTES`
7. `DF_M11_LEARNING_INCLUDE_IN_TEARDOWN`
8. `DF_M11_LEARNING_INCLUDE_IN_BILLING_GUARDRAIL`
9. `DF_M11_CROSS_PLATFORM_BILLING_REQUIRED`

Preparation checks (fail-closed):
1. Resolve M11.H snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required I handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Validate phase-profile policy indicates on-demand posture for learning lanes.
4. Validate default desired count is zero and execution mode is explicit.
5. Validate idle teardown TTL is parse-valid positive integer.
6. Validate teardown and billing inclusion flags are explicitly true.

Deterministic closure algorithm (M11.I):
1. Resolve M11.H snapshot; unreadable or non-pass -> `M11I-B4`.
2. Resolve required I handles from registry; unresolved/placeholder -> `M11I-B3`.
3. Build learning-lane continuity matrix in fixed lane order:
   - OFS,
   - MF,
   - MPR control.
4. Validate phase-profile posture:
   - default desired count zero for service lanes,
   - job execution mode set to run-task/ephemeral posture.
5. Validate teardown inclusion:
   - learning resources are included in teardown scope.
6. Validate cost guardrail continuity:
   - learning lanes explicitly included in cross-platform billing guardrail.
7. Emit `m11_i_cost_teardown_continuity_snapshot.json` locally.
8. Publish durable snapshot; publish failure -> `M11I-B5`.

Required snapshot fields (`m11_i_cost_teardown_continuity_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id="M11.I"`.
2. `m11h_source_ref_local`, `m11h_source_ref_uri`, `m11h_source_mode`.
3. `required_handle_refs` (resolved key/value set used by I).
4. `learning_phase_profile_matrix`.
5. `teardown_inclusion_matrix`.
6. `billing_guardrail_continuity`.
7. `blockers`, `overall_pass`, `elapsed_seconds`, `created_utc`.

Runtime budget:
1. `M11.I` target budget: <= 15 minutes.
2. Over-budget without user waiver -> `M11I-B6`.

DoD:
- [x] Learning lanes are included in phase-profile control policy.
- [x] Teardown preserve/destroy matrix includes learning resources.
- [x] Cross-platform billing guardrail posture remains mandatory.
- [x] Snapshot captures continuity policy and blocker mapping.
- [x] Snapshot exists locally and durably.

Execution evidence (2026-02-22):
1. Local snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_i_cost_teardown_continuity_snapshot.json`
2. Durable snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_i_cost_teardown_continuity_snapshot.json`
3. Closure result:
   - `overall_pass=true`
   - blockers empty
4. Cost/teardown continuity handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 11 (`DF_M11_LEARNING_*` continuity handles).

Blockers:
1. `M11I-B1`: learning lane omitted from phase profile controls.
2. `M11I-B2`: teardown inclusion ambiguity for learning resources.
3. `M11I-B3`: cost guardrail continuity gap.
4. `M11I-B4`: M11.H dependency unreadable or not pass-closed.
5. `M11I-B5`: snapshot publication failure.
6. `M11I-B6`: runtime budget breach without waiver.

### M11.J Verdict + M12 Handoff
Goal:
1. Aggregate M11 closure outcomes and publish deterministic verdict.
2. Publish M12 handoff pack only when M11 passes fail-closed gates.

Entry conditions:
1. `M11.I` snapshot exists locally and durably.
2. `M11.I` reports `overall_pass=true` with blocker union empty.
3. Verdict/handoff handles required by J are pinned and non-placeholder.

Required inputs:
1. `M11.I` source snapshots:
   - local: `runs/dev_substrate/m11/<m11_execution_id>/m11_i_cost_teardown_continuity_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/<m11_execution_id>/m11_i_cost_teardown_continuity_snapshot.json`.
2. Source snapshots for `M11.A..M11.I`:
   - `m11_a_authority_handoff_snapshot.json`
   - `m11_b_handle_closure_snapshot.json`
   - `m11_c_runtime_decomposition_snapshot.json`
   - `m11_d_iam_secret_kms_snapshot.json`
   - `m11_e_data_contract_snapshot.json`
   - `m11_f_messaging_governance_snapshot.json`
   - `m11_g_observability_evidence_snapshot.json`
   - `m11_h_non_regression_matrix_snapshot.json`
   - `m11_i_cost_teardown_continuity_snapshot.json`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`.
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`.

Required verdict/handoff handles for J closure:
1. `DF_M11_J_VERDICT_MODE`
2. `DF_M11_J_REQUIRED_SOURCE_SNAPSHOTS`
3. `DF_M11_J_ADVANCE_PREDICATES`
4. `DF_M11_J_M12_HANDOFF_REQUIRED_FIELDS`

Preparation checks (fail-closed):
1. Resolve M11.I snapshot (local preferred, durable fallback) and verify pass posture.
2. Resolve required J handles and assert:
   - all keys present exactly once,
   - status is `PINNED`,
   - value is non-placeholder.
3. Resolve each required `M11.A..M11.I` source snapshot and verify readability/schema parse.
4. Validate verdict mode is explicit fail-closed union posture.
5. Validate required source list and handoff required-field list are explicit.

Deterministic closure algorithm (M11.J):
1. Resolve M11.I snapshot; unreadable or non-pass -> `M11J-B5`.
2. Resolve required J handles from registry; unresolved/placeholder -> `M11J-B4`.
3. Load required `M11.A..M11.I` snapshots from active `m11_execution_id`; any missing/unreadable -> `M11J-B1` or `M11J-B2`.
4. Build deterministic `source_phase_matrix` in fixed order (`A..I`) with:
   - `phase`,
   - `phase_id`,
   - `overall_pass`,
   - `blockers`,
   - source refs (local/durable).
5. Compute `source_blocker_rollup` as deterministic union across all source blockers.
6. Evaluate advance predicates:
   - all source `overall_pass=true`,
   - source blocker rollup empty,
   - required source count complete.
7. Compute verdict:
   - `ADVANCE_TO_M12` when all predicates true,
   - `HOLD_M11` otherwise.
8. Emit:
   - `m11_j_verdict_snapshot.json`,
   - `m12_handoff_pack.json`.
9. Publish both artifacts durably; publication failure -> `M11J-B3`.

Runtime budget:
1. `M11.J` target budget: <= 10 minutes.
2. Over-budget without user waiver -> `M11J-B6`.

DoD:
- [x] Source matrix includes all M11 sub-phase snapshots.
- [x] Blocker rollup is deterministic and reproducible.
- [x] Verdict and handoff artifacts are published locally + durably.
- [x] `ADVANCE_TO_M12` only when all required predicates are true.
- [x] Runtime budget gate is satisfied.

Execution evidence (2026-02-22):
1. Local verdict snapshot:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m11_j_verdict_snapshot.json`
2. Local handoff pack:
   - `runs/dev_substrate/m11/m11_20260222T145654Z/m12_handoff_pack.json`
3. Durable verdict snapshot:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m11_j_verdict_snapshot.json`
4. Durable handoff pack:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m11_20260222T145654Z/m12_handoff_pack.json`
5. Closure result:
   - `verdict=ADVANCE_TO_M12`
   - `overall_pass=true`
   - blockers empty
6. Verdict/handoff handle family pinned:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` Section 12 (`DF_M11_J_*` handles).

Blockers:
1. `M11J-B1`: missing required source snapshot.
2. `M11J-B2`: source snapshot unreadable/schema-invalid.
3. `M11J-B3`: publication failure for verdict/handoff artifacts.
4. `M11J-B4`: predicate mismatch with attempted advance verdict.
5. `M11J-B5`: M11.I dependency unreadable or not pass-closed.
6. `M11J-B6`: runtime budget breach without waiver.

## 6) M11 Runtime Budget Posture (Planning)
Planning target budgets:
1. `M11.A`: <= 10 minutes.
2. `M11.B`: <= 20 minutes.
3. `M11.C`: <= 20 minutes.
4. `M11.D`: <= 20 minutes.
5. `M11.E`: <= 20 minutes.
6. `M11.F`: <= 20 minutes.
7. `M11.G`: <= 15 minutes.
8. `M11.H`: <= 20 minutes.
9. `M11.I`: <= 15 minutes.
10. `M11.J`: <= 10 minutes.

Rule:
1. Over-budget planning execution is blocker state unless explicit user waiver is recorded.

## 7) Required Snapshot Contracts (M11)
Minimum common fields for each M11 sub-phase snapshot:
1. `phase`, `phase_id`, `platform_run_id`, `m11_execution_id`, `subphase_id`.
2. `authority_refs`.
3. `entry_gate_checks`.
4. `predicate_checks`.
5. `blockers`.
6. `overall_pass`.
7. `elapsed_seconds`.
8. `created_utc`.

M11 verdict snapshot (`m11_j_verdict_snapshot.json`) additional required fields:
1. `source_phase_matrix` (`M11.A..M11.I` -> pass/blockers refs).
2. `source_blocker_rollup`.
3. `verdict`.
4. `m12_handoff_ref_local`.
5. `m12_handoff_ref_uri`.

## 8) M11 DoD (Phase-Level)
- [x] `M11.A..M11.I` are planned and executed with blocker-free closure snapshots.
- [x] Required handles for Learning/Registry are fully closed and concrete.
- [x] Runtime/IAM/data/messaging/evidence/cost lanes are explicit and non-ambiguous.
- [x] `M8..M10` non-regression matrix is pinned with executable acceptance rules.
- [x] `M11.J` publishes `ADVANCE_TO_M12` verdict and `m12_handoff_pack.json` locally + durably.

## 9) Planning Status
1. This file is now expanded to execution-grade planning depth.
2. `M11.A..M11.J` closure execution has been completed with local + durable evidence publication.
3. `M11` is closure-ready with `ADVANCE_TO_M12`.
4. Status transitions remain governed only by `platform.build_plan.md`.
