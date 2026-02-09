# CaseTrigger Implementation Map
_As of 2026-02-09_

---

## Entry: 2026-02-09 03:49PM - Phase 5.2 planning kickoff (CaseTrigger as explicit component)

### Objective
Create an explicit implementation decision trail for CaseTrigger so trigger production is treated as a first-class service boundary in Phase `5.2`.

### Inputs / authorities
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `5.2`)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`

### Decisions captured
- Adopt explicit CaseTrigger service posture (preferred Option A from pre-design decisions).
- Keep CM opaque by feeding only CaseTrigger events (not direct multi-stream source parsing inside CM).
- Preserve by-ref evidence discipline and deterministic id recipes from Phase `5.1` contracts.
- Keep v0 no-merge case policy in downstream integration gates.

### Planned implementation threads
1. Contract + taxonomy alignment for trigger source mapping.
2. Source adapter and eligibility gate implementation.
3. Deterministic publish boundary with replay-safe retries/checkpoints.
4. CM integration and parity closure evidence.

### Invariants to enforce
- ContextPins and CaseSubjectKey are mandatory for all published triggers.
- Trigger identities remain stable across retries and replay.
- Collision semantics are fail-closed (never silent replace).
- Trigger lane remains low-volume control/governance posture (no hot-path payload mirroring).
