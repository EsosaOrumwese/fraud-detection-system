# Online Feature Plane Build Plan (v0)
_As of 2026-02-05_

## Purpose
Provide a progressive, component-scoped build plan for OFP aligned to Phase 4.3 (RTDL feature plane).

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half-baked phases: do not advance until DoD is satisfied.
- Rails are non-negotiable: ContextPins, canonical envelope, no-PASS-no-read, idempotency, append-only truth.

## Phase plan (v0)

### Phase 1 — Contracts + meaning authority
**Intent:** lock the external feature snapshot/provenance contract and feature-definition versioning.

**DoD checklist:**
- Feature snapshot schema includes `as_of_time_utc`, feature group versions, `input_basis`, and `snapshot_hash`.
- Feature definition identity (policy_rev/digest) is pinned and recorded in provenance.
- Input basis semantics (exclusive-next offsets) documented and enforced.

### Phase 2 — Projector core (EB → state)
**Intent:** consume EB admitted facts and build deterministic feature state.

**DoD checklist:**
- EB consumer applies updates idempotently under at-least-once delivery.
- Postgres state + checkpoints are updated atomically with apply.
- `input_basis` vector is maintained and exposed.

### Phase 3 — Serve surface (state → snapshot)
**Intent:** serve deterministic, as-of feature snapshots to DF.

**DoD checklist:**
- `get_features` supports `as_of_time_utc` and returns deterministic snapshots.
- Snapshot hash covers provenance + feature values with stable ordering.
- `graph_version` is included when IEG is consulted.

### Phase 4 — Ops + health signals
**Intent:** expose lag/health signals for DL and ops.

**DoD checklist:**
- Emit lag, apply errors, and serve latency metrics.
- Surface explicit “stale/missing” posture in serve responses.

---
