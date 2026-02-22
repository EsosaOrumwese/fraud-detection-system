# Dev Substrate Deep Plan - M0 (Mobilization + Authority Lock)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail only._
_Last updated: 2026-02-13_

## 0) Purpose
M0 establishes execution governance before any build/infra/runtime implementation begins.
This phase is planning and control only.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting semantic source:
- `docs/design/platform/local-parity/*`

## 2) Scope Boundary for M0
In scope:
- planning structure,
- authority lock,
- phase governance rules,
- evidence strategy framing,
- logging protocol.

Out of scope:
- code changes for runtime components,
- Terraform/infra build execution,
- ECS/image build execution,
- phase M1+ technical implementation.

## 3) M0 Deliverables
1. Main plan contains canonical roadmap and status model.
2. Main plan contains deep-phase routing and status ownership rule.
3. M0 deep plan exists and is aligned with main plan M0 section.
4. Phase transition checklist is pinned and unambiguous.
5. Evidence expectation framing exists for all phases at high level.
6. Decision/action logging protocol is actively used.

## 4) Work Breakdown (Deep)

## M0.A Authority Freeze
Goal:
- prevent reinterpretation drift during implementation.

Tasks:
1. Verify authority precedence is explicitly declared in main plan.
2. Verify drift-stop protocol is explicit (stop/log/repin).
3. Verify scope lock is explicit (Spine Green v0 only).

DoD:
- [x] Authority precedence section is present and complete.
- [x] Drift-stop protocol is present.
- [x] Scope lock matches migration baseline.

## M0.B Planning Topology Lock
Goal:
- separate control-plane status tracking from deep phase planning detail.

Tasks:
1. Pin naming convention for phase deep plan files (`platform.M*.build_plan.md`).
2. Pin status ownership to main plan only.
3. Pin creation policy for future phase docs (only on phase activation approval).

DoD:
- [x] Main plan contains deep-plan routing section.
- [x] Main plan states status ownership rule explicitly.
- [x] Future phase doc policy is present.

## M0.C Evidence Strategy Framing
Goal:
- ensure phase completion cannot be claimed without proof surfaces.

Tasks:
1. Confirm high-level evidence map exists in main plan.
2. Confirm phase transition checklist requires evidence existence checks.
3. Confirm semantic + scale certification rule is present in M10 framing.

DoD:
- [x] Evidence fidelity map exists in main plan.
- [x] Transition checklist includes evidence verification.
- [x] M10 includes Semantic Green + Scale Green requirements.

## M0.D Logging and Decision Discipline
Goal:
- ensure all migration decisions are auditable as they happen.

Tasks:
1. Record pre/post decision entries in `platform.impl_actual.md` for this phase.
2. Record action trail in daily logbook.
3. Cross-reference M0 deep plan adoption in both logs.

DoD:
- [x] Pre/post entries recorded in `platform.impl_actual.md`.
- [x] Corresponding entries recorded in `docs/logbook/02-2026/2026-02-13.md`.
- [x] Entries mention M0 deep-plan structure adoption.

## M0.E Exit Readiness Review
Goal:
- ensure M0 can close cleanly and hand off to M1.

Tasks:
1. Review M0 checklist completion against main plan M0 DoD.
2. Confirm no open ambiguity in authority/phase control/evidence policy.
3. Prepare explicit handoff statement for M1 activation (without activating automatically).

DoD:
- [x] M0 deliverables checklist complete.
- [x] No unresolved governance ambiguity remains.
- [x] Handoff statement drafted in main plan "Immediate Next Action" context.

## 5) Risks and Controls
R1: Fragmented status tracking between docs  
Control: main-plan-only status ownership rule.

R2: Premature implementation before governance lock  
Control: M0 scope boundary explicitly excludes build/infra/runtime execution.

R3: Under-specified proof expectations  
Control: evidence fidelity map + mandatory transition checklist.

## 6) M0 Completion Checklist
- [x] M0.A complete
- [x] M0.B complete
- [x] M0.C complete
- [x] M0.D complete
- [x] M0.E complete

## 7) Exit Criteria
M0 is eligible for closure when:
1. all checklist items in Section 6 are complete,
2. main plan M0 DoD is complete,
3. user confirms progression to M1 activation planning.

## 8) M0 Closure Snapshot
Closure verdict:
- `M0 = DONE` in `platform.build_plan.md` roadmap and section status.

Evidence references:
- Main control plan:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.build_plan.md`
- M0 deep plan:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.M0.build_plan.md`
- Decision trail:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.impl_actual.md`
- Action log trail:
  - `docs/logbook/02-2026/2026-02-13.md`

Handoff posture:
- M1 remains `NOT_STARTED` until explicit USER activation.

Note:
- This file does not change phase status.
- Status transition is made only in `platform.build_plan.md`.
