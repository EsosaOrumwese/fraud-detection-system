# Dev Substrate Deep Plan - M12 (F2 OFS Dataset Build + Data Contracts Closure)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M12._
_Last updated: 2026-02-22_

## 0) Purpose
M12 closes `F2` by proving deterministic OFS dataset construction on `dev_full` from archive + label surfaces with fail-closed as-of discipline, join/leakage controls, and reproducible manifest evidence.

M12 must ensure:
1. OFS input authority and required handle surfaces are explicit and non-placeholder.
2. Archive + label timeline readiness is proven before OFS execution.
3. OFS runs on managed runtime only (no local compute) with reproducible output surfaces.
4. Dataset manifest/fingerprint reproducibility is deterministic across equivalent reruns.
5. Parity/leakage checks are explicit and fail-closed before verdict.
6. M12 verdict and M13 handoff are deterministic and evidence-backed.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/learning_and_evolution.pre-design_decisions.md`
5. `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
6. `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
7. `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M11.build_plan.md`
2. `runs/dev_substrate/m11/m11_20260222T145654Z/m11_j_verdict_snapshot.json`
3. `runs/dev_substrate/m11/m11_20260222T145654Z/m12_handoff_pack.json`
4. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
5. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

## 2) Scope Boundary for M12
In scope:
1. OFS authority + input-contract closure.
2. Archive/label readiness + as-of gate checks.
3. OFS runtime execution lane closure on managed runtime.
4. Manifest/fingerprint determinism and equivalent-rerun reproducibility.
5. Parity/leakage checks and blocker adjudication.
6. Verdict + M13 handoff artifact publication.

Out of scope:
1. MF train/eval runtime (`M13`).
2. MPR promotion/rollback closure (`M13`).
3. Integrated full-platform certification (`M14`).

## 3) M12 Deliverables
1. `M12.A` authority + input-contract closure snapshot.
2. `M12.B` archive/label-asof readiness snapshot.
3. `M12.C` OFS runtime execution snapshot.
4. `M12.D` manifest/fingerprint determinism snapshot.
5. `M12.E` parity/leakage adjudication snapshot.
6. `M12.F` verdict snapshot and `m13_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. `M11` is closed with verdict `ADVANCE_TO_M12`.
2. M11 verdict/handoff artifacts are readable locally and durably.
3. M12 planning is expanded; runtime execution remains blocked until explicit USER activation.

Execution block:
1. No M12 runtime execution is allowed with unresolved required handle surfaces.
2. No OFS execution is allowed before archive/label-asof readiness pass closure.
3. No M12 close verdict is valid without deterministic rerun + leakage checks.

## 4.1) Anti-cram Law (Binding for M12)
1. M12 is not execution-ready unless these lanes are explicit:
   - authority + handoff + handle closure,
   - identity/IAM + secrets + runtime profile closure,
   - archive/label readiness + as-of controls,
   - managed execution + rerun controls,
   - manifest determinism + parity/leakage checks,
   - evidence/taxonomy + verdict/handoff publication.
2. If a missing lane is discovered, planning expands before execution continues.

## 4.2) Capability-Lane Coverage Matrix
| Capability lane | Primary owner | Supporting owners | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + M11 handoff closure | M12.A | M12.F | `m12_a_authority_input_contract_snapshot.json` |
| Archive/label readiness + as-of closure | M12.B | M12.E | `m12_b_archive_label_asof_readiness_snapshot.json` |
| Managed OFS execution closure | M12.C | M12.D | `m12_c_ofs_runtime_execution_snapshot.json` |
| Manifest/fingerprint determinism | M12.D | M12.F | `m12_d_manifest_determinism_snapshot.json` |
| Parity/leakage adjudication | M12.E | M12.F | `m12_e_parity_leakage_snapshot.json` |
| Verdict + M13 handoff | M12.F | - | `m12_f_verdict_snapshot.json` + `m13_handoff_pack.json` |

## 5) Work Breakdown (Deep)

### M12.A OFS Authority + Input-Contract Closure
Goal:
1. Validate M11 handoff and freeze OFS input contract surfaces for M12.
2. Close required OFS handles (existing + newly pinned for F2) with no placeholders.

Entry conditions:
1. `M11.J` snapshot and `m12_handoff_pack.json` exist locally and durably.
2. `M11.J` verdict is `ADVANCE_TO_M12`.

Required inputs:
1. `runs/dev_substrate/m11/m11_20260222T145654Z/m11_j_verdict_snapshot.json`
2. `runs/dev_substrate/m11/m11_20260222T145654Z/m12_handoff_pack.json`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Required handle set for A closure:
1. Existing required surfaces:
   - `DF_PLATFORM_PROFILE_PATH`
   - `DF_OFS_ENTRYPOINT_CMD`
   - `DF_RUNTIME_CLUSTER_HANDLE`
   - `DF_RUNTIME_EXECUTION_ROLE`
   - `DF_OFS_DATA_ROOT`
   - `DF_SPINE_ARCHIVE_ROOT`
   - `DF_LABEL_TIMELINE_ROOT`
   - `DF_DATASET_MANIFEST_ROOT`
   - `DF_EVIDENCE_BUCKET`
   - `DF_EVIDENCE_PREFIX_PATTERN`
2. M12-specific surfaces to pin during M12.A:
   - `DF_OFS_LABEL_ASOF_UTC`
   - `DF_OFS_LABEL_RESOLUTION_RULE_ID`
   - `DF_OFS_JOIN_SCOPE`
   - `DF_OFS_DROP_POLICY`
   - `DF_OFS_DATASET_FINGERPRINT_MODE`
   - `DF_OFS_PARITY_POLICY`
   - `DF_OFS_LEAKAGE_POLICY`

DoD:
- [ ] Required M12 authority and handle set are explicit and non-placeholder.
- [ ] M11 handoff is pass-closed and coherent.
- [ ] `m12_a_authority_input_contract_snapshot.json` exists locally + durably.

Blockers:
1. `M12A-B1`: M11 handoff unreadable/invalid.
2. `M12A-B2`: unresolved/placeholder required handle.
3. `M12A-B3`: authority/input-contract ambiguity.
4. `M12A-B4`: snapshot publication failure.

### M12.B Archive/Label Readiness + As-of Gate Checks
Goal:
1. Prove archive and label timeline readiness for requested OFS build scope.
2. Enforce label-asof and anti-leakage eligibility gates.

Entry conditions:
1. M12.A pass snapshot exists locally and durably.
2. As-of and label-resolution handles are pinned.

Tasks:
1. Validate archive roots/readability and required replay basis references.
2. Validate label timeline readability and as-of eligibility predicates.
3. Validate join-scope/drop-policy preconditions.
4. Emit `m12_b_archive_label_asof_readiness_snapshot.json`.

DoD:
- [ ] Archive and label surfaces are readable for requested build scope.
- [ ] Label-asof discipline is explicit and pass-closed.
- [ ] Join-scope/drop-policy prerequisites are non-ambiguous.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M12B-B1`: archive surface unreadable/incomplete.
2. `M12B-B2`: label-asof eligibility failure.
3. `M12B-B3`: join-scope/drop-policy ambiguity.
4. `M12B-B4`: snapshot publication failure.

### M12.C OFS Managed Runtime Execution Lane Closure
Goal:
1. Execute OFS dataset build on managed runtime (no local compute).
2. Produce required dataset build evidence artifacts.

Entry conditions:
1. M12.B pass snapshot exists.
2. Runtime profile/entrypoint/role/cluster handles are pinned and valid.

Tasks:
1. Launch OFS runtime execution in managed lane.
2. Capture runtime execution metadata and evidence refs.
3. Publish `m12_c_ofs_runtime_execution_snapshot.json`.

DoD:
- [ ] OFS executes in managed lane only.
- [ ] Build artifacts/evidence refs are produced deterministically.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M12C-B1`: managed runtime launch/execution failure.
2. `M12C-B2`: local-compute dependency detected.
3. `M12C-B3`: required build evidence missing.
4. `M12C-B4`: snapshot publication failure.

### M12.D Manifest/Fingerprint Determinism + Rerun Reproducibility
Goal:
1. Prove manifest/fingerprint determinism for equivalent reruns.
2. Ensure immutable reproducibility surfaces are complete.

Entry conditions:
1. M12.C pass snapshot exists.
2. Dataset manifest root and fingerprint mode handles are pinned.

Tasks:
1. Resolve primary OFS manifest and fingerprint artifacts.
2. Execute equivalent rerun comparison contract.
3. Compute deterministic comparison matrix.
4. Emit `m12_d_manifest_determinism_snapshot.json`.

DoD:
- [ ] Manifest schema contract is valid and complete.
- [ ] Equivalent rerun fingerprint comparison passes.
- [ ] Determinism evidence is published locally + durably.

Blockers:
1. `M12D-B1`: manifest schema or provenance gap.
2. `M12D-B2`: fingerprint mismatch on equivalent rerun.
3. `M12D-B3`: rerun contract unreadable/invalid.
4. `M12D-B4`: snapshot publication failure.

### M12.E Parity/Leakage Checks + Blocker Adjudication
Goal:
1. Adjudicate parity posture and leakage controls before phase verdict.
2. Convert parity/leakage outcomes into deterministic blocker mapping.

Entry conditions:
1. M12.D pass snapshot exists.
2. Parity/leakage policy handles are pinned.

Tasks:
1. Evaluate parity expectations for pinned OFS policy mode.
2. Evaluate leakage guard predicates.
3. Produce blocker-adjudication matrix.
4. Emit `m12_e_parity_leakage_snapshot.json`.

DoD:
- [ ] Leakage controls pass fail-closed policy.
- [ ] Parity expectations are explicitly adjudicated.
- [ ] Blocker mapping is deterministic and evidence-backed.
- [ ] Snapshot exists locally + durably.

Blockers:
1. `M12E-B1`: leakage control failure.
2. `M12E-B2`: parity contract failure/mismatch.
3. `M12E-B3`: adjudication ambiguity.
4. `M12E-B4`: snapshot publication failure.

### M12.F Verdict + M13 Handoff
Goal:
1. Aggregate `M12.A..M12.E` outcomes and publish deterministic M12 verdict.
2. Publish M13 handoff only when M12 passes fail-closed gates.

Entry conditions:
1. `M12.A..M12.E` snapshots exist and are readable.
2. Blocker taxonomy is complete for all M12 lanes.

Tasks:
1. Build source matrix from `M12.A..M12.E` snapshots.
2. Compute blocker union and predicate checks.
3. Emit `m12_f_verdict_snapshot.json` and `m13_handoff_pack.json`.
4. Publish both artifacts locally + durably.

DoD:
- [ ] Source matrix includes all M12 sub-phase snapshots.
- [ ] Blocker rollup is deterministic and reproducible.
- [ ] Verdict/handoff artifacts are published locally + durably.
- [ ] `ADVANCE_TO_M13` only when required predicates are true.

Blockers:
1. `M12F-B1`: required source snapshot missing.
2. `M12F-B2`: source snapshot unreadable/schema-invalid.
3. `M12F-B3`: publication failure for verdict/handoff artifacts.
4. `M12F-B4`: predicate mismatch with attempted advance verdict.

## 6) M12 Runtime Budget Posture (Planning)
Planning target budgets:
1. `M12.A`: <= 15 minutes.
2. `M12.B`: <= 20 minutes.
3. `M12.C`: <= 45 minutes.
4. `M12.D`: <= 20 minutes.
5. `M12.E`: <= 20 minutes.
6. `M12.F`: <= 10 minutes.

Rule:
1. Over-budget execution without explicit user waiver is blocker state.

## 7) Required Snapshot Contracts (M12)
Minimum common fields for each M12 sub-phase snapshot:
1. `phase`, `phase_id`, `platform_run_id`, `m12_execution_id`, `subphase_id`.
2. `authority_refs`.
3. `entry_gate_checks`.
4. `predicate_checks`.
5. `blockers`.
6. `overall_pass`.
7. `elapsed_seconds`.
8. `created_utc`.

M12 verdict snapshot (`m12_f_verdict_snapshot.json`) additional fields:
1. `source_phase_matrix` (`M12.A..M12.E` -> pass/blockers refs).
2. `source_blocker_rollup`.
3. `verdict` (`ADVANCE_TO_M13|HOLD_M12`).
4. `m13_handoff_ref_local`.
5. `m13_handoff_ref_uri`.

## 8) M12 DoD (Phase-Level)
- [ ] `M12.A..M12.E` are executed with blocker-free closure snapshots.
- [ ] OFS dataset build is managed-runtime only and deterministic.
- [ ] Label-asof/join-scope/leakage guards are pass-closed.
- [ ] Manifest/fingerprint reproducibility is proven with equivalent rerun evidence.
- [ ] `M12.F` publishes `ADVANCE_TO_M13` verdict and `m13_handoff_pack.json` locally + durably.

## 9) Planning Status
1. This file is expanded to execution-grade planning depth.
2. M12 runtime execution has not started; status remains governed by `platform.build_plan.md`.
3. M12 execution is blocked until explicit USER activation.
