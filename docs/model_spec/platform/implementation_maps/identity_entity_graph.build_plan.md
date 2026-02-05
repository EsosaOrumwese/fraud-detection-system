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

### Phase 1 — Intake + projection core (EB → graph)
**Intent:** consume EB context + traffic deterministically and build a run‑scoped graph projection aligned to the RTDL flow narrative.

#### Phase 1.1 — Inputs + replay basis
**Goal:** pin IEG inputs and replay basis so rebuilds are deterministic.

**DoD checklist:**
- IEG consumes EB admitted topics only (no Oracle reads).
- Topic set is explicit per environment profile (traffic + context streams).
- Replay basis is EB offsets (exclusive‑next) and recorded per partition.
- Archive usage follows RTDL pre‑design decisions (archive = long‑term truth for replay).

#### Phase 1.2 — Envelope validation + pins
**Goal:** enforce canonical envelope + run pins for every event.

**DoD checklist:**
- Canonical envelope validation is mandatory.
- Required pins enforced: `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` (legacy `run_id` optional alias).
- `event_id`, `event_type`, and `ts_utc` are required and validated.

#### Phase 1.3 — Event classification
**Goal:** deterministically route events into apply/ignore/failure lanes.

**DoD checklist:**
- Each event is classified as `GRAPH_MUTATING`, `GRAPH_IRRELEVANT`, or `GRAPH_UNUSABLE`.
- Classification is deterministic per `event_type` and config map (no ad‑hoc logic).
- `GRAPH_UNUSABLE` events record apply‑failure with EB offset and reason.

#### Phase 1.4 — Identity hints extraction (v0)
**Goal:** normalize identity hints into a stable internal format without hidden inference.

**DoD checklist:**
- v0 uses a **payload‑level** `observed_identifiers` block or a deterministic field‑mapping per `event_type`.
- Missing identity hints ⇒ `GRAPH_UNUSABLE` (no mutation, explicit failure).
- Identity hints are normalized into `(identifier_type, identifier_value, source_event_id)` rows.

#### Phase 1.5 — Idempotent apply + payload_hash anomaly
**Goal:** at‑least‑once delivery does not change graph state.

**DoD checklist:**
- Dedupe key is `(scenario_run_id, topic_or_class, event_id)`.
- Duplicate deliveries do not mutate state or advance offsets.
- Payload_hash mismatch is recorded as an anomaly and does not mutate state.

#### Phase 1.6 — Checkpoints + graph_version
**Goal:** deterministic progress tokens for downstream provenance.

**DoD checklist:**
- Checkpoints store next‑offset‑to‑apply per partition (exclusive‑next).
- `graph_version` derived from stream identity + partition offset vector.
- Watermark uses canonical `ts_utc` with allowed lateness per RTDL defaults.
- Offsets advance only after durable state commit (DB txn + WAL flush).

### Phase 2 — Storage + rebuildability
**Intent:** ensure projection is durable, scoped, and rebuildable from EB/archive.

#### Phase 2.1 — Postgres schema (v0)
**Goal:** define minimal but sufficient storage.

**DoD checklist:**
- Tables: entities, identifiers, edges, apply_failures, checkpoints, graph_versions.
- All rows scoped by ContextPins; constraints prevent cross‑run contamination.
- Apply‑failure ledger stores EB offsets + reason codes.

#### Phase 2.2 — Retention + TTL
**Goal:** pin retention posture aligned to EB/archive windows.

**DoD checklist:**
- TTL policy defined for projection tables (run‑scoped default).
- Apply‑failure and checkpoint retention pinned for replay/audit.

#### Phase 2.3 — Replay/backfill
**Goal:** rebuild is explicit, deterministic, and auditable.

**DoD checklist:**
- Rebuild input declares stream + offset ranges + pins.
- Rebuild emits new `graph_version` tied to declared basis.
- No silent “latest” scans; rebuilds are explicit operations.

### Phase 3 — Query surface (projection → context)
**Intent:** provide deterministic, read‑only context queries for OFP/DF.

#### Phase 3.1 — Identity resolution
**Goal:** resolve observed identifiers to canonical entities.

**DoD checklist:**
- Deterministic ordering of candidates.
- No merges in v0; ambiguity/conflict is explicit.
- Responses include `graph_version` + ContextPins.

#### Phase 3.2 — Entity profile + neighbors
**Goal:** return stable profiles and 1‑hop context.

**DoD checklist:**
- Profiles include first/last seen and optional counters.
- Neighbor lists are deterministic and paginated with stable tokens.
- Responses include integrity status + `graph_version`.

#### Phase 3.3 — Provenance + integrity
**Goal:** callers can record exactly what context was used.

**DoD checklist:**
- Every response includes `graph_version` and integrity status.
- No implicit “now”; responses are deterministic for a given graph_version.
- Failures are explicit and never fabricate context.

### Phase 4 — Ops + degrade signals
**Intent:** expose operational truth to DL/DF and observability.

#### Phase 4.1 — Metrics + counters
**Goal:** minimal but sufficient telemetry for v0.

**DoD checklist:**
- Counters: events_seen, mutating_applied, unusable, lag, watermark_age.
- Metrics are run‑scoped via ContextPins.

#### Phase 4.2 — Health posture
**Goal:** explicit AMBER/RED criteria for degrade decisions.

**DoD checklist:**
- Health reports lag thresholds and apply‑failure rates.
- RED/AMBER thresholds are pinned and documented.
- IEG never reclassifies EB truth (IG remains admission authority).

#### Phase 4.3 — Reconciliation artifact (optional v0)
**Goal:** provide an auditable summary of applied basis.

**DoD checklist:**
- Run‑scoped reconciliation artifact records applied offsets + graph_version.

### Phase 5 — Performance + backpressure
**Intent:** meet RTDL SLOs without correctness loss.

#### Phase 5.1 — Consumer model
**Goal:** bounded buffering with no drops.

**DoD checklist:**
- Partition‑scoped consumers with bounded queues.
- Backpressure pauses intake rather than dropping events.

#### Phase 5.2 — Apply batching
**Goal:** scale without breaking determinism.

**DoD checklist:**
- Batch apply is idempotent and deterministic.
- Partition parallelism does not reorder within partition.

### Phase 6 — Validation + tests
**Intent:** prove determinism, idempotency, and replay safety.

**DoD checklist:**
- Unit tests for idempotency, payload_hash mismatch, watermark monotonicity.
- Replay test: same offsets → same graph_version + state.
- Integration test: EB sample events → deterministic projection state.

### Phase 7 — Deployment + config
**Intent:** align with environment ladder without semantic drift.

**DoD checklist:**
- Config supports local_parity/dev/prod with identical semantics.
- Secrets are runtime only; no secrets in artifacts or plans.
- Run_config_digest captured for IEG runs and query responses (if applicable).

---

## Notes (v0 pins)
- Identity hints must be standardized and visible at the envelope/payload boundary.
- IEG does not merge entities in v0; it returns conflicts explicitly.
- Query plane is read‑only; no “write on read.”

