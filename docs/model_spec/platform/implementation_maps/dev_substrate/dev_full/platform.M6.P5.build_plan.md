# Dev Substrate Deep Plan - M6.P5 (P5 READY_PUBLISHED)
_Parent orchestration phase: `platform.M6.build_plan.md`_
_Last updated: 2026-02-25_

## 0) Purpose
This document carries execution-grade planning for `P5 READY_PUBLISHED`.

`P5` must prove:
1. READY is emitted to `fp.bus.control.v1`.
2. READY receipt is committed with Step Functions execution reference.
3. duplicate/ambiguous READY states are fail-closed.
4. READY commit authority is Step Functions (not Flink-only compute).

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P5 READY_PUBLISHED`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
5. `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/m6_handoff_pack.json`

## 2) P5 Scope
In scope:
1. READY entry precheck and run-scope continuity.
2. READY emission + receipt commit authority.
3. duplicate/ambiguity fail-closed closure.
4. deterministic `P5` rollup + verdict artifacts.

Out of scope:
1. streaming activation/lag closure (`P6`).
2. ingest commit evidence closure (`P7`).

## 3) Work Breakdown (Owned by M6.B/M6.C/M6.D)

### P5.A Entry + Contract Precheck (M6.B)
Goal:
1. prove prerequisites are complete before READY commit.

Tasks:
1. verify run-scope values from `m6_handoff_pack.json`.
2. verify required handles are pinned:
   - `FP_BUS_CONTROL_V1`
   - `SR_READY_COMMIT_AUTHORITY`
   - `SR_READY_COMMIT_STATE_MACHINE`
   - `SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF`
   - `SR_READY_COMMIT_RECEIPT_PATH_PATTERN`
   - `READY_MESSAGE_FILTER`
3. verify Step Functions orchestrator surface is healthy.

DoD:
- [ ] entry checks pass with no unresolved required handles.
- [ ] `m6b_ready_entry_snapshot.json` committed locally and durably.

### P5.B READY Commit Authority Execution (M6.C)
Goal:
1. commit READY under authoritative Step Functions control.

Tasks:
1. emit READY signal for current run scope.
2. verify control-topic publication evidence.
3. verify receipt contains Step Functions execution reference.
4. verify duplicate/ambiguous READY protection (no unresolved READY ambiguity).

DoD:
- [ ] READY signal proof exists and is run-scoped.
- [ ] READY receipt includes Step Functions execution reference.
- [ ] duplicate/ambiguity checks are green.
- [ ] `m6c_ready_commit_snapshot.json` committed locally and durably.

### P5.C P5 Gate Rollup + Verdict (M6.D)
Goal:
1. adjudicate `P5` closure from P5.A/P5.B evidence.

Tasks:
1. build `m6d_p5_gate_rollup_matrix.json`.
2. build `m6d_p5_blocker_register.json`.
3. emit `m6d_p5_gate_verdict.json`.

DoD:
- [ ] rollup matrix + blocker register committed.
- [ ] deterministic verdict committed (`ADVANCE_TO_P6`/`HOLD_REMEDIATE`/`NO_GO_RESET_REQUIRED`).

## 4) P5 Verification Catalog
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `P5-V1-HANDLE-CLOSURE` | verify required `SR_READY_*`/`READY_*`/`FP_BUS_CONTROL_V1` handles are pinned | prevents silent default drift |
| `P5-V2-READY-EMISSION` | verify READY publication on control topic for run scope | validates READY signal path |
| `P5-V3-RECEIPT-AUTHORITY` | verify READY receipt contains Step Functions execution ref | validates commit authority |
| `P5-V4-DUPLICATE-GUARD` | verify no unresolved duplicate/ambiguous READY outcomes | prevents replay ambiguity |
| `P5-V5-ROLLUP-VERDICT` | build rollup + blocker register + verdict | deterministic gate closure |

## 5) P5 Blocker Taxonomy
1. `M6P5-B1`: required READY handles missing/inconsistent.
2. `M6P5-B2`: READY signal publication failure.
3. `M6P5-B3`: READY receipt missing/invalid.
4. `M6P5-B4`: missing Step Functions commit authority evidence.
5. `M6P5-B5`: duplicate/ambiguous READY unresolved.
6. `M6P5-B6`: P5 rollup/verdict inconsistency.
7. `M6P5-B7`: durable publish/readback failure.

## 6) P5 Evidence Contract
1. `m6b_ready_entry_snapshot.json`
2. `m6c_ready_commit_snapshot.json`
3. `m6d_p5_gate_rollup_matrix.json`
4. `m6d_p5_blocker_register.json`
5. `m6d_p5_gate_verdict.json`

## 7) Exit Rule for P5
`P5` can close only when:
1. all `M6P5-B*` blockers are resolved,
2. all P5 DoDs are green,
3. P5 evidence exists locally and durably,
4. verdict is deterministic and blocker-consistent.

Transition:
1. `P6` is blocked until `P5` verdict is `ADVANCE_TO_P6`.
