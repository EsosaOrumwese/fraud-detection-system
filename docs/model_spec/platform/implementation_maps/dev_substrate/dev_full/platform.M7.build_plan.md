# Dev Substrate Deep Plan - M7 (P8 RTDL_CAUGHT_UP + P9 DECISION_CHAIN_COMMITTED + P10 CASE_LABELS_COMMITTED)
_Status owner: `platform.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
`M7` closes spine runtime truth for:
1. `P8 RTDL_CAUGHT_UP`,
2. `P9 DECISION_CHAIN_COMMITTED`,
3. `P10 CASE_LABELS_COMMITTED`.

`M7` must prove:
1. RTDL core lanes are run-scoped, active, and caught up.
2. Decision/action/audit chain is append-safe and replay-safe.
3. Case/label boundaries are deterministic with single-writer label semantics.
4. Closure is component-granular, not service-bundle inferred.
5. Each component lane meets pinned performance/throughput budgets, not just functional correctness.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P8..P10`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary
In scope:
1. P8 component closures: `IEG`, `OFP`, `ArchiveWriter`, `RTDL caught-up rollup`.
2. P9 component closures: `DF`, `AL`, `DLA`, decision-chain rollup.
3. P10 component closures: `CaseTrigger bridge`, `CM`, `LS`, case-label rollup.
4. M7 phase rollup and M8 entry handoff.

Out of scope:
1. P11 obs/gov closure (`M8`).
2. Learning/evolution closures (`M9+`).

## 3) Anti-Lump Execution Law (M7-local, binding)
1. No combined pass claims like "`P8` green" unless each component lane in that phase has its own evidence and DoD closure.
2. A downstream phase cannot close on upstream aggregate metrics alone; each upstream component must have explicit run-scoped proofs.
3. Any component with missing evidence is a blocker, even if sibling components are green.
4. Rollups (`P8/P9/P10/M7`) can only aggregate already-closed component lanes.

## 3.1) Performance-First Gate for M7 (binding)
1. Each component lane must publish a performance snapshot for its run window.
2. Per-component numeric SLO budgets are mandatory and must be pinned in `M7.A` before executing component lanes.
3. Required metric families per component:
   - throughput (`records_per_second` or equivalent),
   - latency (`p95`/`p99` processing latency),
   - backlog/lag (queue/topic lag or checkpoint delay),
   - resource efficiency (`cpu_p95`, `memory_p95`),
   - stability (`error_rate`, retry/backpressure posture).
4. Any missing SLO pin or budget breach is fail-closed and blocks phase advancement.

## 4) Component Inventory and Lane Ownership
| Canonical phase | Component | Lane owner | Minimum closure proof |
| --- | --- | --- | --- |
| P8 | IEG | M7.C / M7.P8.B | run-scoped inlet projection evidence + lag posture |
| P8 | OFP | M7.D / M7.P8.C | run-scoped context projection evidence + lag posture |
| P8 | ArchiveWriter | M7.E / M7.P8.D | durable archive object presence + append/readback proof |
| P9 | DF | M7.F / M7.P9.B | run-scoped decision commits + idempotency posture |
| P9 | AL | M7.G / M7.P9.C | action outcomes committed + replay-safe duplicates |
| P9 | DLA | M7.H / M7.P9.D | append-only audit evidence + readback |
| P10 | CaseTrigger bridge | M7.I / M7.P10.B | trigger ingress surface and run-scope filter proof |
| P10 | CM | M7.I / M7.P10.C | case rows committed + deterministic case identity |
| P10 | LS | M7.I / M7.P10.D | writer-boundary protocol proof + single-writer guarantee |

## 5) Work Breakdown (Orchestration)

### M7.A Authority + Handle Closure (`P8..P10`)
Goal:
1. close required handles for all M7 components before runtime execution.

Tasks:
1. enumerate required handles per component lane.
2. fail-closed any missing required handle (`M7-B1`).
3. publish `m7a_handle_closure_snapshot.json` and blocker register.
4. pin per-component performance SLO targets for:
   - `IEG`, `OFP`, `ArchiveWriter`,
   - `DF`, `AL`, `DLA`,
   - `CaseTrigger bridge`, `CM`, `LS`.

DoD:
- [ ] required-handle matrix for all M7 components is explicit.
- [ ] unresolved required handles are blocker-marked.
- [ ] `m7a_*` evidence is committed locally and durably.
- [ ] per-component numeric performance SLO pins are complete.

### M7.B P8 Entry + RTDL Core Precheck
Goal:
1. prove P8 entry is valid before component execution.

Tasks:
1. verify M6 handoff continuity and run-scope pins.
2. verify stream refs/checkpoint surfaces for `IEG` and `OFP`.
3. verify archive writer prerequisites and target prefixes.

DoD:
- [ ] P8 entry precheck passes.
- [ ] unresolved precheck failures are explicit blockers.

### M7.C P8 IEG Lane Closure
Goal:
1. close `IEG` lane with component-level proofs.

Tasks:
1. execute/run `IEG` lane in managed runtime.
2. verify run-scoped inlet projection outputs.
3. verify lag and checkpoint posture.

DoD:
- [ ] `IEG` component evidence set is complete.
- [ ] `IEG` blockers are clear.
- [ ] `IEG` performance snapshot meets pinned budget.

### M7.D P8 OFP Lane Closure
Goal:
1. close `OFP` lane with component-level proofs.

Tasks:
1. execute/run `OFP` lane in managed runtime.
2. verify run-scoped context projection outputs.
3. verify lag and checkpoint posture.

DoD:
- [ ] `OFP` component evidence set is complete.
- [ ] `OFP` blockers are clear.
- [ ] `OFP` performance snapshot meets pinned budget.

### M7.E P8 ArchiveWriter + P8 Rollup
Goal:
1. close `ArchiveWriter` and adjudicate P8.

Tasks:
1. verify durable archive object writes with readback.
2. verify append-only semantics for archive ledger.
3. emit `P8` rollup matrix/blocker register/verdict.

DoD:
- [ ] archive writer closure evidence is complete.
- [ ] `P8` verdict is deterministic and blocker-consistent.
- [ ] `ArchiveWriter` performance snapshot meets pinned budget.

### M7.F P9 DF Lane Closure
Goal:
1. close `DF` lane with component-level proofs.

Tasks:
1. execute/run `DF` lane.
2. verify decision commits and idempotency keys.
3. verify replay-safe duplicate handling.

DoD:
- [ ] `DF` component evidence is complete.
- [ ] `DF` blockers are clear.
- [ ] `DF` performance snapshot meets pinned budget.

### M7.G P9 AL Lane Closure
Goal:
1. close `AL` lane with component-level proofs.

Tasks:
1. execute/run `AL` lane.
2. verify action/outcome commitments.
3. verify duplicate-safe side-effect handling.

DoD:
- [ ] `AL` component evidence is complete.
- [ ] `AL` blockers are clear.
- [ ] `AL` performance snapshot meets pinned budget.

### M7.H P9 DLA Lane + P9 Rollup
Goal:
1. close `DLA` and adjudicate P9.

Tasks:
1. verify append-only audit writes and readback.
2. verify run-scope continuity across `DF/AL/DLA`.
3. emit `P9` rollup matrix/blocker register/verdict.

DoD:
- [ ] `DLA` component evidence is complete.
- [ ] `P9` verdict is deterministic and blocker-consistent.
- [ ] `DLA` performance snapshot meets pinned budget.

### M7.I P10 CaseTrigger/CM/LS + P10 Rollup
Goal:
1. close case/label components individually and adjudicate P10.

Tasks:
1. close `CaseTrigger bridge` ingress contract.
2. close `CM` case write surface.
3. close `LS` writer boundary and single-writer semantics.
4. emit `P10` rollup matrix/blocker register/verdict.

DoD:
- [ ] `CaseTrigger bridge` closure evidence is complete.
- [ ] `CM` closure evidence is complete.
- [ ] `LS` writer-boundary evidence is complete.
- [ ] `P10` verdict is deterministic and blocker-consistent.
- [ ] `CaseTrigger bridge` performance snapshot meets pinned budget.
- [ ] `CM` performance snapshot meets pinned budget.
- [ ] `LS` performance snapshot meets pinned budget.

### M7.J M7 Gate Rollup + M8 Handoff
Goal:
1. finalize M7 verdict and publish M8 entry pack.

Tasks:
1. aggregate `P8/P9/P10` verdict chain.
2. emit `m8_handoff_pack.json`.
3. emit M7 phase budget envelope + cost-outcome receipt.

DoD:
- [ ] `m7_execution_summary.json` committed locally and durably.
- [ ] `m8_handoff_pack.json` committed locally and durably.
- [ ] M7 cost-outcome artifacts are valid and blocker-free.
- [ ] M7 verdict is `ADVANCE_TO_M8` with `next_gate=M8_READY`.

## 6) Deep Phase Routing
1. `P8` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P8.build_plan.md`
2. `P9` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P9.build_plan.md`
3. `P10` detailed plan: `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P10.build_plan.md`

## 7) M7 Blocker Taxonomy (Fail-Closed)
1. `M7-B1`: required handles missing/inconsistent.
2. `M7-B2`: P8 entry contract failure.
3. `M7-B3`: IEG lane closure failure.
4. `M7-B4`: OFP lane closure failure.
5. `M7-B5`: archive writer closure failure.
6. `M7-B6`: P8 rollup/verdict inconsistency.
7. `M7-B7`: DF lane closure failure.
8. `M7-B8`: AL lane closure failure.
9. `M7-B9`: DLA lane closure failure.
10. `M7-B10`: P9 rollup/verdict inconsistency.
11. `M7-B11`: CaseTrigger bridge closure failure.
12. `M7-B12`: CM closure failure.
13. `M7-B13`: LS writer-boundary closure failure.
14. `M7-B14`: P10 rollup/verdict inconsistency.
15. `M7-B15`: M7 handoff/cost-outcome artifact failure.
16. `M7-B16`: missing per-component performance SLO pins for active lane.
17. `M7-B17`: component performance budget breach (throughput/latency/lag/resource/stability).

## 8) M7 Completion Checklist
- [ ] M7.A complete
- [ ] M7.B complete
- [ ] M7.C complete
- [ ] M7.D complete
- [ ] M7.E complete
- [ ] M7.F complete
- [ ] M7.G complete
- [ ] M7.H complete
- [ ] M7.I complete
- [ ] M7.J complete
- [ ] all active `M7-B*` blockers resolved

## 9) Planning Status
1. M7 deep-plan scaffold created.
2. P8/P9/P10 deep plans are split and referenced.
3. No M7 execution has started in this document yet.
