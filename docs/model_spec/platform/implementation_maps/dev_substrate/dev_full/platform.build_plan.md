# Dev Substrate Build Plan (dev_full)
_Track: dev_min certified baseline -> dev_full full-platform managed substrate_
_Last updated: 2026-02-22_

## 0) Purpose
This is the active execution plan for building `dev_full` from the certified `dev_min` baseline into a full-platform managed stack with:
- no laptop runtime compute,
- strict fail-closed phase gates,
- full-platform scope (Spine + Learning/Evolution),
- deploy/monitor/fail/recover/rollback/cost-control proof per lane,
- cost-to-outcome discipline (spend must map to explicit proof/decision outcomes).

This plan is progressive: detailed phase steps are expanded only when a phase becomes active.

## 1) Scope Lock
In scope:
- Control + Ingress
- RTDL
- Case + Labels
- Run/Operate + Obs/Gov
- Learning + Evolution (OFS/MF/MPR)

Out of scope for dev_full v0:
- multi-region active-active,
- compliance program expansion beyond engineering controls.

## 2) Authority and Precedence
Execution authority:
1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md` (spine baseline continuity)
5. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (spine semantic inheritance)

If drift appears:
- stop implementation,
- log drift severity/impact,
- repin authority before proceeding.

## 3) Global Success Criteria (Program DoD)
Program is complete only when all are true:
- `P(-1), P0..P17` close green in `dev_full` with blocker-free verdict.
- Full-platform proof matrix is complete for each lane (deploy/monitor/fail/recover/rollback/cost-control).
- Spine non-regression anchors remain green after learning activation (`P5`, `P8`, `P9`, `P10`, `P11`).
- Learning closure is complete (`P12..P15`) with rollback drill evidence.
- No laptop runtime compute is used.
- `P17` teardown/idle-safe closure is proven.
- Cost-to-outcome receipts exist for each executed phase.

## 4) Non-Negotiable Guardrails
- No unpinned handle usage.
- No local runtime fallback.
- No unresolved `PUBLISH_UNKNOWN` during green closure.
- No bypass of fail-closed gates.
- No phase advancement without required evidence artifacts.
- No spend-only progress: phase spend without material outcome is blocked.

## 5) Progressive Elaboration Method
Rules:
- Only one plan phase may be `ACTIVE` at a time.
- A phase cannot start until previous phase is `DONE` (unless explicit controlled exception is pinned).
- Each active phase must define:
  - entry criteria,
  - implementation lanes,
  - explicit DoD checklist,
  - rollback/rerun posture,
  - evidence contract,
  - phase spend envelope + expected outcomes.
- Future phases remain gate-level until activated.

Statuses:
- `NOT_STARTED`
- `ACTIVE`
- `DONE`
- `BLOCKED`

## 6) Phase Roadmap (Canonical)
Canonical lifecycle key: `phase_id=P#` from dev_full runbook.

| Plan Phase | Canonical phase_id | Name | Status |
| --- | --- | --- | --- |
| M0 | pre-P(-1) | Mobilization + authority lock | ACTIVE |
| M1 | P(-1) | Packaging readiness (image/provenance) | NOT_STARTED |
| M2 | P0 | Substrate readiness (core/streaming/runtime/data_ml/ops) | NOT_STARTED |
| M3 | P1 | Run pinning and orchestrator readiness | NOT_STARTED |
| M4 | P2 | Spine daemon readiness on EKS | NOT_STARTED |
| M5 | P3-P4 | Oracle readiness + ingest preflight | NOT_STARTED |
| M6 | P5-P7 | Control + Ingress closure | NOT_STARTED |
| M7 | P8-P10 | RTDL + Case/Labels closure | NOT_STARTED |
| M8 | P11 | Spine obs/gov closure + non-regression pack | NOT_STARTED |
| M9 | P12 | Learning input readiness | NOT_STARTED |
| M10 | P13 | OFS dataset closure | NOT_STARTED |
| M11 | P14 | MF train/eval closure | NOT_STARTED |
| M12 | P15 | MPR promotion/rollback closure | NOT_STARTED |
| M13 | P16-P17 | Full-platform verdict + teardown/idle-safe closure | NOT_STARTED |

---

## 6.1) Deep Phase Plan Routing
Per-phase deep planning docs follow:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M0.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M1.build_plan.md`
- ...
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`

Control rule:
- `platform.build_plan.md` is the only file allowed to change phase status.
- `platform.M*.build_plan.md` documents deep details and blockers but cannot independently advance status.

## 6.2) Phase Evidence Template (Pinned)
Each phase (M1..M13) must publish:
- plan phase + canonical `phase_id`
- `platform_run_id` (or `N/A` if not created yet)
- authority refs used
- entry gate result
- DoD gate result
- commit evidence artifact list
- rollback/retry note
- phase verdict (`PASS`/`FAIL`)
- cost envelope artifact path
- cost-to-outcome receipt path
- operator + UTC timestamp

## 7) Current Active Phase

## M0 - Mobilization + Authority Lock
Status: `ACTIVE`

Objective:
- lock the dev_full authority stack and create execution control surfaces before implementation lanes begin.

Entry criteria:
- dev_full design authority exists and stack pins are set.
- dev_full run-process authority exists.
- dev_full handles registry exists.

Implementation tasks:
1. Validate internal consistency across authority trio:
   - design authority,
   - run-process,
   - handles registry.
2. Close any naming mismatches between run-process and handles registry.
3. Confirm open materialization set (`TO_PIN`) is isolated and fail-closed.
4. Create deep-phase plan shell for M0 and define M0 DoD checks.
5. Pin phase transition protocol for M1 entry.

M0 DoD checklist:
- [ ] Authority trio validated without contradictions.
- [ ] `TO_PIN` list accepted as fail-closed materialization backlog.
- [ ] Deep M0 plan exists (`platform.M0.build_plan.md`).
- [ ] Phase transition protocol to M1 is pinned.
- [ ] M0 closure evidence recorded in impl map + logbook.

Rollback posture:
- Docs-only rollback is allowed before M1 starts.

Evidence outputs:
- `platform.M0.build_plan.md`
- M0 closure note in `platform.impl_actual.md`
- dated action record in `docs/logbook`

Phase exit:
- M0 can move to `DONE` only after all checklist items are checked.

---

## 8) Cost-to-Outcome Operating Rule (Execution Binding)
For every active phase:
1. Publish a phase spend envelope before execution.
2. Publish phase cost-to-outcome receipt at closure.
3. Block advancement if spend occurred without material proof/decision outcome.
4. Maintain daily cross-platform cost posture during active execution windows.

This rule is binding for all phases M1..M13.

## 9) Branch and Change Safety
- No branch-history operations without explicit USER branch-governance confirmation.
- No cross-branch execution improvisation.
- No destructive git commands.

## 10) Next Action
- Expand and execute `M0` in `platform.M0.build_plan.md`.
