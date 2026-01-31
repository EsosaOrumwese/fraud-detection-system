# Identity & Entity Graph Build Plan (v0)
_As of 2026-01-31_

## Purpose
Provide a progressive, component‑scoped build plan for the Identity & Entity Graph (IEG) that aligns with Phase 4.2 platform needs.

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half‑baked phases: do not advance until DoD is fully satisfied.
- Rails are non‑negotiable: ContextPins, canonical envelope, no‑PASS‑no‑read, by‑ref truth, idempotency, append‑only ledgering, deterministic ordering.
- IEG is **derived** truth only: authoritative for projection + graph_version, not for admission, features, or decisions.

## Phase plan (v0)

### Phase 1 — Projection core (EB → graph)
**Intent:** consume EB traffic deterministically and build a run/world‑scoped projection with stable `graph_version` and checkpoints.

#### Phase 1.1 — EB intake + idempotent apply
**Goal:** apply admitted events deterministically under at‑least‑once delivery.

**DoD checklist:**
- IEG consumes EB traffic stream (Kinesis) with per‑partition ordering only.
- Idempotent apply: duplicates do not change projection state.
- Apply path is **payload‑blind** except for a standardized identity‑hints block.
- GRAPH_UNUSABLE events are recorded (apply failures) without blocking processing.

#### Phase 1.2 — Projection tables (Postgres)
**Goal:** store a minimal but queryable identity/edge projection.

**DoD checklist:**
- Postgres tables defined for entities, edges, identifiers, checkpoints, apply_failures.
- All rows are scoped by ContextPins (run/world isolation).
- Schema constraints prevent cross‑run contamination.

#### Phase 1.3 — Checkpoints + graph_version
**Goal:** make replay and provenance deterministic.

**DoD checklist:**
- Checkpoints store next‑offset‑to‑apply per partition.
- `graph_version` derived from stream + partition offset vector (exclusive‑next).
- Watermark (`watermark_ts_utc`) pinned to canonical event time (`ts_utc`).

### Phase 2 — Query surface (projection → context)
**Intent:** provide a deterministic read surface for OFP/DF with provenance stamps.

#### Phase 2.1 — Resolve identity
**Goal:** resolve observed identifiers to canonical entity refs.

**DoD checklist:**
- Deterministic ordering of candidates.
- Explicit ambiguity/ conflict markers (no merges in v0).
- Response includes `graph_version` + ContextPins.

#### Phase 2.2 — Entity profile + neighbors
**Goal:** return basic profile and 1‑hop graph context.

**DoD checklist:**
- Profile query returns stable entity metadata (first/last seen, counters if any).
- Neighbor query returns deterministic ordering and stable pagination tokens.
- All responses stamped with `graph_version` and integrity status.

### Phase 3 — Integrity + ops posture
**Intent:** expose operational truth to Degrade Ladder and observability.

#### Phase 3.1 — Integrity status
**Goal:** surface apply failures explicitly for downstream degrade posture.

**DoD checklist:**
- Integrity status indicates whether apply failures exist before the served `graph_version`.
- Integrity state is exposed to DL/DF queries and to ops telemetry.

#### Phase 3.2 — Health + telemetry
**Goal:** emit deterministic health/lag signals.

**DoD checklist:**
- Health reports lag, apply failure rate, and checkpoint drift.
- Metrics/logs include ContextPins + stream identity.
- Explicit AMBER/RED criteria for lag or failure spikes.

### Phase 4 — Replay/backfill readiness
**Intent:** make projection rebuild explicit and auditable.

#### Phase 4.1 — Replay basis declaration
**Goal:** rebuild projections from a declared EB offset basis.

**DoD checklist:**
- Rebuild input specifies stream + offset ranges + pins.
- Rebuild produces new graph_version tied to declared basis.
- No silent “latest” scans.

#### Phase 4.2 — Deterministic replay validation
**Goal:** prove replay determinism.

**DoD checklist:**
- Replaying the same basis yields identical graph_version + counts.
- Apply failures are stable under replay.

---

## Notes (v0 pins)
- Identity hints must be standardized and visible at the envelope/payload boundary.
- IEG does not merge entities in v0; it returns conflicts explicitly.
- Query plane is read‑only; no “write on read.”

