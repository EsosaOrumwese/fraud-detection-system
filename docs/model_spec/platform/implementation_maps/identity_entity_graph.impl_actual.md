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
