# Decision Fabric Build Plan (v0)
_As of 2026-02-05_

## Purpose
Provide a progressive, component-scoped build plan for DF aligned to Phase 4.4 (RTDL decision core).

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half-baked phases: do not advance until DoD is satisfied.
- Rails are non-negotiable: canonical envelope, ContextPins, fail-closed degrade posture, IG→EB truth boundary.

## Phase plan (v0)

### Phase 1 — Contracts + decision plan
**Intent:** lock DecisionResponse/ActionIntent contracts and deterministic IDs.

**DoD checklist:**
- Decision payload schema includes bundle_ref, snapshot_hash, graph_version, eb_offset_basis, degrade_posture, policy_rev, run_config_digest.
- DecisionResponse event_id and ActionIntent event_id/idempotency rules are pinned and documented.
- Output event_type names and schema_version usage are documented.

### Phase 2 — Decision pipeline (EB → decision)
**Intent:** consume admitted events and emit decisions through IG.

**DoD checklist:**
- DF consumes EB traffic, resolves registry bundle, consults OFP/IEG/DL as allowed.
- Decisions are deterministic and replay-safe (same inputs → same outputs).
- Outputs are published via IG and receipts are recorded.

### Phase 3 — Replay + safety posture
**Intent:** prove idempotency and fail-closed behavior.

**DoD checklist:**
- Replay of the same inputs yields identical DecisionResponse + ActionIntents.
- DL/Registry/OFP failures force explicit degrade posture with recorded provenance.

---
