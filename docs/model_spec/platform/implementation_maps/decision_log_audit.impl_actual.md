# Decision Log & Audit Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:15:05 — Phase 4 planning kickoff (DLA scope + audit record)

### Problem / goal
Pin the DLA v0 audit-record requirements and ingestion posture before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_log_audit.design-authority.md`
- Platform rails (append-only truth, by-ref evidence, no silent corrections).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DLA is the **immutable flight recorder** for decision context + outcomes.
- DLA consumes DecisionResponse + ActionOutcome events from EB (no direct writers).
- Audit records are **append-only** in object storage; Postgres holds lookup index only.
- Audit record must include: decision event ref, outcome refs (when available), bundle ref, snapshot hash + ref, graph_version, eb_offset_basis, degrade_posture, policy_rev, run_config_digest, and explicit context offsets when present.
- If provenance is incomplete, DLA quarantines rather than writing partial truth.

### Planned implementation scope (Phase 4.5)
- Implement EB consumer for decision/outcome events and object-store writer for audit records.
- Implement Postgres audit index with deterministic keys.

---
