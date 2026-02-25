# Dev Substrate Deep Plan - M7.P9 (P9 DECISION_CHAIN_COMMITTED)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P9 DECISION_CHAIN_COMMITTED`.

`P9` must prove:
1. `DF` commits run-scoped decisions deterministically.
2. `AL` commits actions/outcomes with duplicate-safe semantics.
3. `DLA` commits append-only audit truth with durable readback.
4. P9 rollup verdict is deterministic from component-level proofs.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P9 DECISION_CHAIN_COMMITTED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P9 Scope
In scope:
1. decision-chain entry precheck and run continuity checks.
2. component execution/verification:
   - `DF`,
   - `AL`,
   - `DLA`.
3. P9 rollup matrix/blocker register/verdict.

Out of scope:
1. P8 RTDL core closure.
2. P10 case/labels closure.

## 3) Anti-Lump Rule for P9
1. `DF`, `AL`, and `DLA` are independently adjudicated lanes.
2. A green decision chain requires all three components to be green.
3. High-level throughput/latency summaries do not replace per-component commit proofs.

## 4) Work Breakdown

### P9.A Entry + Handle Closure
Goal:
1. close required handles and entry gates for decision-chain components.

Tasks:
1. verify `P8` verdict and run-scope continuity.
2. verify required handles for `DF/AL/DLA`.
3. emit `p9a_entry_snapshot.json` and blocker register.

DoD:
- [ ] P9 required-handle set is complete.
- [ ] unresolved required handles are blocker-marked.
- [ ] P9 entry snapshot is committed locally and durably.

### P9.B DF Component Lane Closure
Goal:
1. close `DF` component lane.

Tasks:
1. execute `DF` with run-scoped inputs.
2. verify decision commit evidence and idempotency tuple integrity.
3. verify fail-closed behavior on invalid/missing policy inputs.
4. emit `p9b_df_component_snapshot.json`.

DoD:
- [ ] decision commits are run-scoped and deterministic.
- [ ] DF idempotency and fail-closed checks pass.
- [ ] DF blocker set is empty.

### P9.C AL Component Lane Closure
Goal:
1. close `AL` component lane.

Tasks:
1. execute `AL` with run-scoped decision inputs.
2. verify action/outcome commit evidence.
3. verify duplicate-safe side-effect semantics.
4. emit `p9c_al_component_snapshot.json`.

DoD:
- [ ] action/outcome commits are run-scoped and deterministic.
- [ ] duplicate-safe side-effect checks pass.
- [ ] AL blocker set is empty.

### P9.D DLA Component Lane Closure
Goal:
1. close `DLA` component lane.

Tasks:
1. execute/verify `DLA` append-only audit writes.
2. verify durable readback for run-scoped audit evidence.
3. verify append-only invariants (no in-place mutation).
4. emit `p9d_dla_component_snapshot.json`.

DoD:
- [ ] append-only audit evidence is committed and readable.
- [ ] append-only invariants pass.
- [ ] DLA blocker set is empty.

### P9.E P9 Rollup + Verdict
Goal:
1. adjudicate P9 from `P9.B/P9.C/P9.D`.

Tasks:
1. build `p9e_decision_chain_rollup_matrix.json`.
2. build `p9e_decision_chain_blocker_register.json`.
3. emit `p9e_decision_chain_verdict.json`.

DoD:
- [ ] rollup matrix and blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_P10` or fail-closed hold).

## 5) P9 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P9-V1-ENTRY` | validate P9 entry gates and required handles |
| `P9-V2-DF` | validate DF decision commits + idempotency/fail-closed posture |
| `P9-V3-AL` | validate AL action/outcome commits + duplicate-safe side effects |
| `P9-V4-DLA` | validate DLA append-only audit evidence + readback |
| `P9-V5-ROLLUP` | validate P9 rollup and deterministic verdict |

## 6) P9 Blocker Taxonomy
1. `M7P9-B1`: P9 entry/handle closure failure.
2. `M7P9-B2`: DF component lane failure.
3. `M7P9-B3`: AL component lane failure.
4. `M7P9-B4`: DLA component lane failure.
5. `M7P9-B5`: P9 rollup/verdict inconsistency.

## 7) P9 Evidence Contract
1. `p9a_entry_snapshot.json`
2. `p9b_df_component_snapshot.json`
3. `p9c_al_component_snapshot.json`
4. `p9d_dla_component_snapshot.json`
5. `p9e_decision_chain_rollup_matrix.json`
6. `p9e_decision_chain_blocker_register.json`
7. `p9e_decision_chain_verdict.json`

## 8) Exit Rule for P9
`P9` can close only when:
1. all `M7P9-B*` blockers are clear,
2. all P9 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. `P10` is blocked until `P9` verdict is `ADVANCE_TO_P10`.
