# Dev Substrate Deep Plan - M7.P10 (P10 CASE_LABELS_COMMITTED)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P10 CASE_LABELS_COMMITTED`.

`P10` must prove:
1. case-trigger bridge admits only run-scoped case-trigger surfaces.
2. `CM` commits case records deterministically.
3. `LS` commits labels via explicit writer-boundary semantics with single-writer posture.
4. P10 rollup verdict is deterministic from component-level proofs.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P10 CASE_LABELS_COMMITTED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P10 Scope
In scope:
1. case-label entry precheck and run continuity checks.
2. component execution/verification:
   - `CaseTrigger bridge`,
   - `CM`,
   - `LS`.
3. writer-boundary and single-writer guarantees for label commits.
4. P10 rollup matrix/blocker register/verdict.

Out of scope:
1. P8 RTDL core closure.
2. P9 decision-chain closure.
3. P11 obs/gov closure.

## 3) Anti-Lump Rule for P10
1. `CaseTrigger bridge`, `CM`, and `LS` are independently adjudicated lanes.
2. `LS` cannot be inferred green from CM results; writer-boundary proof is mandatory.
3. P10 cannot close while any case/label component is unresolved.

## 4) Work Breakdown

### P10.A Entry + Handle Closure
Goal:
1. close required handles and entry gates for case/label components.

Tasks:
1. verify `P9` verdict and run-scope continuity.
2. verify required handles for case-trigger bridge, CM, LS, and label store boundary.
3. emit `p10a_entry_snapshot.json` and blocker register.

DoD:
- [ ] P10 required-handle set is complete.
- [ ] unresolved required handles are blocker-marked.
- [ ] P10 entry snapshot is committed locally and durably.

### P10.B CaseTrigger Bridge Lane Closure
Goal:
1. close case-trigger bridge lane.

Tasks:
1. verify case-trigger input filtering is run-scoped.
2. verify trigger-to-CM bridge contract and delivery receipts.
3. verify duplicate-safe trigger semantics.
4. emit `p10b_case_trigger_snapshot.json`.

DoD:
- [ ] run-scoped case-trigger bridge evidence is present.
- [ ] duplicate-safe trigger semantics pass.
- [ ] CaseTrigger blocker set is empty.

### P10.C CM Component Lane Closure
Goal:
1. close `CM` case-management lane.

Tasks:
1. execute `CM` case writes from run-scoped trigger inputs.
2. verify deterministic case identity and write commits.
3. verify append/readback posture for case evidence.
4. emit `p10c_cm_component_snapshot.json`.

DoD:
- [ ] deterministic case-write evidence is present.
- [ ] case append/readback checks pass.
- [ ] CM blocker set is empty.

### P10.D LS Component Lane Closure
Goal:
1. close `LS` writer-boundary lane.

Tasks:
1. execute `LS` label writes for run-scoped case outcomes.
2. verify writer-boundary protocol:
   - accept/reject outcomes,
   - commit semantics,
   - idempotency key usage.
3. verify single-writer posture for label append surface.
4. emit `p10d_ls_component_snapshot.json`.

DoD:
- [ ] LS writer-boundary protocol evidence is complete.
- [ ] single-writer checks pass.
- [ ] LS blocker set is empty.

### P10.E P10 Rollup + Verdict
Goal:
1. adjudicate P10 from `P10.B/P10.C/P10.D`.

Tasks:
1. build `p10e_case_labels_rollup_matrix.json`.
2. build `p10e_case_labels_blocker_register.json`.
3. emit `p10e_case_labels_verdict.json`.

DoD:
- [ ] rollup matrix and blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_M7`/`ADVANCE_TO_M8` or fail-closed hold as pinned by orchestration gate).

## 5) P10 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P10-V1-ENTRY` | validate P10 entry gates and required handles |
| `P10-V2-CASE-TRIGGER` | validate run-scoped trigger bridge + duplicate-safe semantics |
| `P10-V3-CM` | validate deterministic case writes + readback |
| `P10-V4-LS` | validate LS writer boundary + single-writer posture |
| `P10-V5-ROLLUP` | validate P10 rollup and deterministic verdict |

## 6) P10 Blocker Taxonomy
1. `M7P10-B1`: P10 entry/handle closure failure.
2. `M7P10-B2`: CaseTrigger bridge lane failure.
3. `M7P10-B3`: CM component lane failure.
4. `M7P10-B4`: LS component lane failure.
5. `M7P10-B5`: P10 rollup/verdict inconsistency.

## 7) P10 Evidence Contract
1. `p10a_entry_snapshot.json`
2. `p10b_case_trigger_snapshot.json`
3. `p10c_cm_component_snapshot.json`
4. `p10d_ls_component_snapshot.json`
5. `p10e_case_labels_rollup_matrix.json`
6. `p10e_case_labels_blocker_register.json`
7. `p10e_case_labels_verdict.json`

## 8) Exit Rule for P10
`P10` can close only when:
1. all `M7P10-B*` blockers are clear,
2. all P10 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. M7 rollup remains blocked until `P8`, `P9`, and `P10` are all green.
