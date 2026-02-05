# Decision Log & Audit Build Plan (v0)
_As of 2026-02-05_

## Purpose
Provide a progressive, component-scoped build plan for DLA aligned to Phase 4.5 (audit truth).

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half-baked phases: do not advance until DoD is satisfied.
- Rails are non-negotiable: append-only truth, by-ref evidence, no silent corrections.

## Phase plan (v0)

### Phase 1 — Contracts + storage layout
**Intent:** lock audit record schema and by-ref storage layout.

**DoD checklist:**
- Audit record schema includes decision/outcome refs, provenance, degrade posture, and run_config_digest.
- Object-store prefix layout for audit records is pinned.

### Phase 2 — EB consumer + writer
**Intent:** build immutable audit records from EB events.

**DoD checklist:**
- DLA consumes DecisionResponse + ActionOutcome events from EB.
- DLA writes append-only audit records to object store.

### Phase 3 — Audit index + lookup
**Intent:** provide deterministic lookup of audit records.

**DoD checklist:**
- Postgres index supports lookup by decision_id, run pins, and time range.

---
