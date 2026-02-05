# Identity & Entity Graph Implementation Map
_As of 2026-01-31_

---

## Entry: 2026-01-31 15:40:00 — IEG v0 build plan created (Phase 4.2 alignment)

### Problem / goal
Create a component‑scoped build plan for IEG that satisfies Phase 4.2 platform needs and locks rails before implementation.

### Decisions captured
- IEG is **derived** only; authoritative for projection + graph_version, not admission/features/decisions.
- Projection is run/world‑scoped by ContextPins; no cross‑run graph in v0.
- Postgres is the sole v0 projection store (no graph DB).
- Graph_version is derived from EB offsets with exclusive‑next semantics; watermark uses canonical `ts_utc`.
- Query surface is deterministic and read‑only; no merges in v0.

### Build plan location
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md`

---

---

## Entry: 2026-02-05 18:08:30 — Plan to refine IEG v0 build plan (Phase 4.2)

### Problem / goal
Phase 4.2 is now expanded at the platform level; IEG’s component build plan must be refined to match RTDL pre‑design decisions and the flow narrative (EB → IEG → OFP/DF) so DoD implies a hardened IEG.

### Authorities / inputs
- RTDL pre‑design decisions: `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- IEG design authority: `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- Flow narrative: `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- Platform Phase 4.2 build plan (IEG projector) in `platform.build_plan.md`

### Decision (plan)
Refactor `identity_entity_graph.build_plan.md` to:
- Align phases/sub‑sections with Phase 4.2 A–J intent (inputs, validation, idempotency, watermarks, storage, queries, ops, perf, tests).
- Explicitly pin v0 data‑flow: EB context + traffic → deterministic projection → graph_version → OFP/DF queries.
- Encode DoD with rails: run‑scoped pins, no cross‑run contamination, no merges in v0, replay determinism, explicit apply‑failure handling.

### Expected outputs
- Updated IEG build plan with detailed v0 DoD checklists and flow alignment.
- Logbook entry for the plan update.

---

## Entry: 2026-02-05 18:26:40 — IEG build plan refined for v0 (Phase 4.2)

### Changes applied
- Expanded IEG build plan into detailed v0 sub‑phases aligned to RTDL pre‑design decisions and flow narrative.
- Added explicit DoD for inputs/replay basis, envelope validation, classification, idempotency, watermarks/graph_version, storage, queries, ops, performance, and tests.
- Clarified v0 identity‑hint extraction via payload‑level `observed_identifiers` or deterministic field mapping.

### File updated
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md`
