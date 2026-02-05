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
