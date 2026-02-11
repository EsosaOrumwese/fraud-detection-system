# Scenario Runner Implementation Map (dev_substrate)
_As of 2026-02-11_

## Entry: 2026-02-11 1:11PM - Pre-change lock: rewrite SR dev_substrate build plan for full-migration 3.C.2 posture

### Trigger
USER requested a dedicated `dev_substrate` SR build plan aligned to the latest full-migration direction and `3.C.2` lock set.

### Problem framing
Existing SR build plan in `dev_substrate` was a lightweight starter:
1. it did not explicitly encode managed-only acceptance runtime/state posture,
2. it did not include the newly locked `3.C.2` repins (re-emit governance, full strict gate stance),
3. it did not define closure-grade ladder/negative-path expectations for component gate progression.

### Authorities and constraints used
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.2` locked gate text).
2. `docs/model_spec/platform/component-specific/scenario_runner.design-authority.md`.
3. `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
4. `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`.
5. Baseline continuity:
   - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md`

### Alternatives considered
1. Keep starter SR plan and rely on platform-level `3.C.2` only.
- Rejected: component plan would remain under-specified and easier to drift in execution.
2. Write an exhaustive implementation checklist with code-level steps.
- Rejected for now: premature detail before active coding sections begin.
3. Rewrite SR plan with phase-grade gates tied directly to `3.C.2` lock set.
- Selected: best balance of executable clarity and progressive elaboration.

### Decisions locked before edit
1. SR plan will explicitly carry full-migration repins (managed-only runtime/state acceptance).
2. SR plan will include explicit stop conditions for local fallback and cross-run re-emit violations.
3. SR plan will pin mandatory ladder closure (`20 -> 200 -> 1000`) and mode proof (`fraud` primary + `baseline` secondary).
4. Plan remains a planning artifact (no runtime behavior changes in this pass).

## Entry: 2026-02-11 1:11PM - Applied SR dev_substrate build-plan rewrite

### What changed
Replaced the starter SR build plan with a closure-grade `3.C.2` plan at:
- `docs/model_spec/platform/implementation_maps/dev_substrate/scenario_runner.build_plan.md`

### Structure now encoded
1. Purpose + binding planning rules.
2. Explicit full-migration repin inheritance from platform `3.C.2`.
3. Five SR migration gates:
- `S1` managed execution/state settlement lock,
- `S2` Oracle-coupled facts authority gate,
- `S3` READY contract/idempotency gate,
- `S4` run/operate + obs/gov onboarding gate,
- `S5` validation ladder + closure gate.
4. Explicit stop conditions.
5. Security/performance/operations posture hooks.
6. Rolling status table (`S1..S5` not started).

### Why this is the selected shape
It makes SR component execution auditable and directly traceable to the platform-level full-migration law without waiting for implementation turns to clarify acceptance boundaries.

### Validation
1. Manual consistency check against platform `3.C.2` lock bullets.
2. Confirmed plan still follows progressive elaboration structure with phase-level DoD checklists.

### Cost posture
Docs-only pass; no paid services touched.
