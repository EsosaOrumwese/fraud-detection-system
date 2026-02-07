# Decision Fabric Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:13:45 — Phase 4 planning kickoff (DF scope + output contracts)

### Problem / goal
Prepare Phase 4.4 by locking DF v0 inputs/outputs and decision provenance requirements before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Platform rails (canonical envelope, ContextPins, no-PASS-no-read, append-only).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DF is **EB-driven only**: consumes admitted events, emits DecisionResponse + ActionIntent via IG→EB.
- Decision boundary time is `ts_utc` (domain time). No hidden “now.”
- Decision provenance must include: `bundle_ref`, `snapshot_hash`, `graph_version`, `eb_offset_basis`, `degrade_posture`, `policy_rev`, `run_config_digest`.
- DecisionResponse event_id is deterministic: `H("decision_response", ContextPins, input_event_id, decision_scope)`.
- ActionIntent event_id is deterministic: `H("action_intent", ContextPins, input_event_id, action_domain)`; ActionIntent carries its own `idempotency_key` for AL.
- Degrade posture is a hard constraint; DF fails closed when DL/Registry/OFP is unavailable.

### Planned implementation scope (Phase 4.4)
- Implement EB consumer for traffic + context topics.
- Build deterministic decision plan: resolve registry bundle, fetch features (OFP), consult DL, produce DecisionResponse + ActionIntents.
- Publish outputs through IG admission (no direct EB writes).

---

## Entry: 2026-02-07 02:53:29 — Plan: expand DF component build plan phase-by-phase from platform 4.4

### Problem / goal
Current `decision_fabric.build_plan.md` is too compact (3 broad phases) for direct implementation execution. Platform `Phase 4.4` was expanded into explicit `4.4.A..4.4.L` DoD gates, so DF component planning must now be expanded with component-granular phases and acceptance checks.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (expanded Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Existing DF build/impl docs.

### Decision trail (live)
1. Keep DF plan strictly component-scoped; do not absorb AL/DLA ownership from platform Phase 4.5.
2. Expand DF into implementation phases that map cleanly to platform 4.4 concerns:
   - trigger boundary,
   - DL/Registry integration,
   - context/feature acquisition and budget handling,
   - decision/intent synthesis and publish boundary,
   - determinism/idempotency,
   - observability/validation.
3. Make each phase contain executable DoD checks with explicit artifacts/tests expected.
4. Preserve progressive elaboration doctrine while still giving enough detail to execute v0 without ambiguity.

### Planned edits
- Replace the short three-phase DF plan with a phased v0 map and explicit DoD checklists aligned to platform 4.4.A-L.
- Mark integration-dependent checks (that require AL/DLA closure) explicitly as pending gates, not hidden assumptions.

---

## Entry: 2026-02-07 02:55:08 — Applied DF phase-by-phase build plan expansion

### Change applied
Updated `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` from a 3-phase high-level outline to an executable 8-phase plan with explicit DoD checklists.

### New DF phase map (v0)
1. Contracts + deterministic identity
2. Inlet boundary + trigger gating
3. DL integration + fail-safe enforcement
4. Registry bundle resolution + compatibility
5. Context/features acquisition + decision-time budgets
6. Decision synthesis + intent emission
7. Idempotency/checkpoints/replay safety
8. Observability/validation/closure boundary

### Alignment checks
- Mapped to platform Phase 4.4 gates (A-L) without absorbing AL/DLA authority from Phase 4.5.
- Preserved RTDL pre-design defaults (fail-closed compatibility, join budgets, deterministic resolver/output behavior, provenance minimums).
- Added explicit closure statement to keep component-green scope clear vs integration-pending gates.

---
