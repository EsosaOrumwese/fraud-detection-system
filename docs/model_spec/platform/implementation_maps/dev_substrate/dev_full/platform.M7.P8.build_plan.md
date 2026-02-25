# Dev Substrate Deep Plan - M7.P8 (P8 RTDL_CAUGHT_UP)
_Parent orchestration phase: `platform.M7.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P8 RTDL_CAUGHT_UP`.

`P8` must prove:
1. `IEG` inlet projection lane is run-scoped and healthy.
2. `OFP` context projection lane is run-scoped and healthy.
3. `ArchiveWriter` persists durable archive evidence with append/readback guarantees.
4. `P8` rollup verdict is deterministic from component-level proofs.
5. `IEG/OFP/ArchiveWriter` meet pinned throughput and latency budgets.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P8 RTDL_CAUGHT_UP`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 2) P8 Scope
In scope:
1. RTDL entry precheck for P8.
2. Component execution/verification:
   - `IEG`,
   - `OFP`,
   - `ArchiveWriter`.
3. P8 rollup matrix/blocker register/verdict.

Out of scope:
1. P9 decision chain (`DF/AL/DLA`).
2. P10 case/labels (`CaseTrigger/CM/LS`).

## 3) Anti-Lump Rule for P8
1. `IEG`, `OFP`, and `ArchiveWriter` are independent closure lanes.
2. `P8` cannot be green if any one lane lacks explicit evidence.
3. Shared RTDL lag metrics cannot substitute component evidence.

## 3.1) P8 Performance Contract (binding)
Each component lane must publish `*_performance_snapshot.json` for the lane run window and pass pinned numeric SLOs:
1. `IEG`:
   - throughput (`ieg_records_per_second`),
   - processing latency (`ieg_processing_latency_p95_ms`),
   - lag/backlog (`ieg_lag_messages`),
   - resource posture (`ieg_cpu_p95_pct`, `ieg_memory_p95_pct`),
   - stability (`ieg_error_rate_pct`).
2. `OFP`:
   - throughput (`ofp_records_per_second`),
   - processing latency (`ofp_processing_latency_p95_ms`),
   - lag/backlog (`ofp_lag_messages`),
   - resource posture (`ofp_cpu_p95_pct`, `ofp_memory_p95_pct`),
   - stability (`ofp_error_rate_pct`).
3. `ArchiveWriter`:
   - write throughput (`archive_objects_per_minute`),
   - commit latency (`archive_commit_latency_p95_ms`),
   - queue depth/backpressure (`archive_backpressure_seconds`),
   - resource posture (`archive_cpu_p95_pct`, `archive_memory_p95_pct`),
   - stability (`archive_write_error_rate_pct`).
4. Numeric thresholds are mandatory and must be pinned during `P8.A`; missing pins are fail-closed.

## 4) Work Breakdown

### P8.A Entry + Handle Closure
Goal:
1. close required handles and runtime prerequisites for P8.

Tasks:
1. verify M6->M7 continuity and run-scope pin set.
2. verify required handles for `IEG`, `OFP`, and archive surfaces.
3. emit `p8a_entry_snapshot.json` and blocker register.

DoD:
- [ ] P8 required-handle set is complete.
- [ ] unresolved required handles are blocker-marked.
- [ ] P8 entry snapshot is committed locally and durably.
- [ ] per-component P8 performance SLO targets are pinned.

### P8.B IEG Component Lane Closure
Goal:
1. close `IEG` with run-scoped evidence.

Tasks:
1. execute `IEG` lane in selected managed runtime path.
2. verify run-scoped inlet projection outputs.
3. verify lane checkpoint/lag posture for `IEG`.
4. emit `p8b_ieg_component_snapshot.json`.

DoD:
- [ ] `IEG` run-scoped output proofs are present.
- [ ] `IEG` lag/checkpoint checks are green.
- [ ] `IEG` blocker set is empty.
- [ ] `p8b_ieg_performance_snapshot.json` is committed and within pinned SLO.

### P8.C OFP Component Lane Closure
Goal:
1. close `OFP` with run-scoped evidence.

Tasks:
1. execute `OFP` lane in selected managed runtime path.
2. verify run-scoped context projection outputs.
3. verify lane checkpoint/lag posture for `OFP`.
4. emit `p8c_ofp_component_snapshot.json`.

DoD:
- [ ] `OFP` run-scoped output proofs are present.
- [ ] `OFP` lag/checkpoint checks are green.
- [ ] `OFP` blocker set is empty.
- [ ] `p8c_ofp_performance_snapshot.json` is committed and within pinned SLO.

### P8.D ArchiveWriter Component Lane Closure
Goal:
1. close `ArchiveWriter` durable evidence lane.

Tasks:
1. verify durable archive object writes under run-scoped prefix.
2. verify append/readback invariants for archive ledger.
3. verify archive evidence is replay-discoverable.
4. emit `p8d_archive_writer_snapshot.json`.

DoD:
- [ ] archive object existence/readback proof is present.
- [ ] append-only/archive-ledger invariants pass.
- [ ] `ArchiveWriter` blocker set is empty.
- [ ] `p8d_archive_writer_performance_snapshot.json` is committed and within pinned SLO.

### P8.E P8 Rollup + Verdict
Goal:
1. adjudicate P8 from `P8.B/P8.C/P8.D`.

Tasks:
1. build `p8e_rtdl_gate_rollup_matrix.json`.
2. build `p8e_rtdl_blocker_register.json`.
3. emit `p8e_rtdl_gate_verdict.json`.

DoD:
- [ ] rollup matrix and blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_P9` or fail-closed hold).

## 5) P8 Verification Catalog
| Verify ID | Purpose |
| --- | --- |
| `P8-V1-ENTRY` | validate handles and entry gates for all P8 components |
| `P8-V2-IEG` | validate IEG run-scoped projection outputs and lag/checkpoint posture |
| `P8-V3-OFP` | validate OFP run-scoped projection outputs and lag/checkpoint posture |
| `P8-V4-ARCHIVE` | validate archive writer durable object + append/readback posture |
| `P8-V5-ROLLUP` | validate P8 rollup and deterministic verdict |

## 6) P8 Blocker Taxonomy
1. `M7P8-B1`: P8 entry/handle closure failure.
2. `M7P8-B2`: IEG component lane failure.
3. `M7P8-B3`: OFP component lane failure.
4. `M7P8-B4`: ArchiveWriter component lane failure.
5. `M7P8-B5`: P8 rollup/verdict inconsistency.
6. `M7P8-B6`: missing P8 component performance SLO pins.
7. `M7P8-B7`: P8 component performance budget breach.

## 7) P8 Evidence Contract
1. `p8a_entry_snapshot.json`
2. `p8b_ieg_component_snapshot.json`
3. `p8c_ofp_component_snapshot.json`
4. `p8d_archive_writer_snapshot.json`
5. `p8e_rtdl_gate_rollup_matrix.json`
6. `p8e_rtdl_blocker_register.json`
7. `p8e_rtdl_gate_verdict.json`
8. `p8b_ieg_performance_snapshot.json`
9. `p8c_ofp_performance_snapshot.json`
10. `p8d_archive_writer_performance_snapshot.json`

## 8) Exit Rule for P8
`P8` can close only when:
1. all `M7P8-B*` blockers are clear,
2. all P8 DoDs are green,
3. component evidence exists locally and durably,
4. rollup verdict is deterministic and blocker-consistent.

Transition:
1. `P9` is blocked until `P8` verdict is `ADVANCE_TO_P9`.
