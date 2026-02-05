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

---

## Entry: 2026-02-05 19:18:00 — Phase 1 implementation plan (IEG intake + projection core)

### Problem / goal
Implement Phase 1 of the IEG v0 build plan: deterministic EB intake, envelope/pins validation, classification, identity-hint extraction, idempotent apply, checkpoints, and `graph_version` derivation.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md` (Phase 1 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- Canonical envelope schema: `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`
- Platform rails (ContextPins, no‑PASS‑no‑read, idempotency, append‑only truths)

### Decision trail (live)
1) **Bus intake:** implement file-bus + Kinesis readers with identical semantics; Kinesis uses shard list + `AFTER_SEQUENCE_NUMBER` when checkpoints exist. File-bus uses line offsets (exclusive-next).
2) **Topic set is explicit:** topics list is configured per environment profile; if a fixed Kinesis stream name is configured, IEG reads that stream and filters by event_type/classification rather than assuming per-topic streams.
3) **Classification map:** deterministic event_type → {GRAPH_MUTATING | GRAPH_IRRELEVANT}; unknown event_type fails closed with `GRAPH_UNUSABLE` and an apply-failure record.
4) **Identity hints extraction:** v0 uses payload-level `observed_identifiers[]` as the standard identity-hints block; optional per‑event field-mapping is supported via config but not required for baseline.
5) **Idempotency key:** dedupe key = sha256(`scenario_run_id` + class_name + `event_id`); payload_hash uses canonical JSON of `{event_type, schema_version, payload}`.
6) **Storage substrate:** support Postgres when DSN is provided; otherwise use run-scoped SQLite for local/dev (same schema and semantics).
7) **Graph_version:** derived from stream_id + `{topic → {partition → next_offset}}` basis map (exclusive-next). `watermark_ts_utc` tracks max seen `ts_utc` (v0); offsets advance only after durable commit.

### Planned files / paths
- New package: `src/fraud_detection/identity_entity_graph/` (config, projector, store, ids, hints).
- Event bus reader extension for Kinesis: `src/fraud_detection/event_bus/kinesis.py`.
- Config artifacts: `config/platform/ieg/` (classification + identity hints + topics list).
- Profiles: `config/platform/profiles/{local,local_parity,dev,prod}.yaml` with `ieg` section.
- Tests: `tests/services/identity_entity_graph/` (idempotency, payload_hash mismatch, checkpoint/graph_version determinism).

### Validation plan (Phase 1)
- Unit: duplicate event_id with same payload does not mutate state; mismatched payload_hash records apply-failure.
- Unit: missing identity hints => GRAPH_UNUSABLE + apply-failure; checkpoints still advance.
- Unit: graph_version stable for same basis vector.
- Smoke: process a small local file-bus batch and produce non-empty projection + graph_version.

---

## Entry: 2026-02-05 19:46:00 — Phase 1 implemented (IEG intake + projection core)

### Summary of changes
- Implemented IEG projector package with deterministic intake, envelope validation, classification, identity-hints extraction, idempotent apply, checkpoints, and graph_version derivation.
- Added config artifacts for IEG classification, identity-hints policy, and explicit topic list; wired profiles for local/local_parity/dev/prod.
- Added Kinesis read adapter to the Event Bus module (list shards + batch read).
- Added unit tests for idempotency, payload_hash mismatch, and graph_version presence.

### Key mechanics (as implemented)
- **Envelope validation:** uses canonical envelope schema via `SchemaRegistry` (`canonical_event_envelope.schema.yaml`).
- **Required pins:** enforced via IG class_map required pins; missing pins → `REQUIRED_PINS_MISSING` apply-failure.
- **Classification:** event_type → {GRAPH_MUTATING, GRAPH_IRRELEVANT} via `classification_v0.yaml`; unknown defaults to `GRAPH_UNUSABLE` and records `CLASSIFICATION_UNSUPPORTED`.
- **Identity hints:** v0 uses `payload.observed_identifiers[]` (optionally field-map in config). Missing hints → `IDENTITY_HINTS_MISSING`.
- **Idempotency:** dedupe key = sha256(`scenario_run_id` + class_name + `event_id`); payload hash = sha256(canonical JSON of `{event_type, schema_version, payload}`).
- **Storage:** SQLite (default) or Postgres (dsn) with identical schema; checkpoints are stored with exclusive-next semantics.
- **Graph_version:** hash of canonical basis `{stream_id, topics → partitions → next_offset, offset_kind}`; watermark uses max seen `ts_utc` (v0).

### Files added/updated
- `src/fraud_detection/identity_entity_graph/`:
  - `config.py`, `classification.py`, `hints.py`, `ids.py`, `store.py`, `projector.py`, `__init__.py`
- `src/fraud_detection/event_bus/kinesis.py` (added read adapter)
- `config/platform/ieg/` (`classification_v0.yaml`, `identity_hints_v0.yaml`, `topics_v0.yaml`)
- `config/platform/profiles/{local,local_parity,dev,prod}.yaml` (added `ieg` section)
- Tests: `tests/services/identity_entity_graph/test_projection_store.py`

### Validation
- `python -m pytest tests/services/identity_entity_graph/test_projection_store.py -q` (3 passed)

---

## Entry: 2026-02-05 20:08:00 — Add v0 identity-hints field mapping (payload-level)

### Problem / goal
IEG v0 requires identity hints for graph mutation. Current EB payloads do not yet carry `observed_identifiers[]`, so a deterministic field-mapping is needed to populate hints from payload fields without introducing ad‑hoc logic.

### Authorities / inputs
- IEG build plan Phase 1.4 (identity hints extraction)
- 6B schema pack:
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
  - `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
- Flow narrative (context streams supply identity context; traffic stream is sparse)

### Decision
Introduce a **payload field-mapping** for v0 event_types that lack `observed_identifiers[]`:
- `arrival_events_5B`: map `payload.merchant_id` → `merchant_id` (entity_type `merchant`).
- `s1_arrival_entities_6B`: map `payload.merchant_id`, `payload.party_id`, `payload.account_id`,
  `payload.instrument_id`, `payload.device_id`, `payload.ip_id`, `payload.session_id`.
- `s2_flow_anchor_baseline_6B` + `s3_flow_anchor_with_fraud_6B`: map `payload.flow_id` (entity_type `flow`)
  plus `merchant_id`, `party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`.
- `s2_event_stream_baseline_6B` + `s3_event_stream_with_fraud_6B`: map `payload.flow_id` (entity_type `flow`).

### Files to update
- `config/platform/ieg/identity_hints_v0.yaml`

### Validation
- No code changes; config-only. Existing IEG tests remain valid. Field mapping will be exercised in the next projector run.

---

## Entry: 2026-02-05 20:18:00 — Fix IEG topic list to match traffic stream names

### Problem / goal
IEG topics list used `fp.bus.traffic.v1`, but v0 default traffic is split into fraud/baseline streams. This caused Kinesis read attempts to target a non-existent stream.

### Decision
Update IEG topics list to include `fp.bus.traffic.fraud.v1` and `fp.bus.traffic.baseline.v1` instead of `fp.bus.traffic.v1`.

### Files updated
- `config/platform/ieg/topics_v0.yaml`

---

## Entry: 2026-02-05 20:24:00 — IEG projector pass (local_parity)

### Run
- Profile: `config/platform/profiles/local_parity.yaml`
- PLATFORM_RUN_ID: `platform_20260205T172824Z`
- Projection DB: `runs/fraud-platform/platform_20260205T172824Z/ieg/projection/ieg.db`

### Results
- `ieg_dedupe`: 80
- `ieg_entities`: 175
- `ieg_identifiers`: 175
- `ieg_apply_failures`: 0
- `ieg_checkpoints`: 4
- `ieg_graph_versions`: 1

---

## Entry: 2026-02-05 20:30:00 — Use full identity_entity_graph pathing (not `ieg`)

### Problem / goal
Align run-scoped projection paths with the full component name to avoid `ieg/` shorthand in run artifacts.

### Decision
Change IEG projection default path suffix from `ieg/projection/ieg.db` to
`identity_entity_graph/projection/identity_entity_graph.db`. Add logging component map for `ieg` → `identity_entity_graph`.

### Files updated
- `src/fraud_detection/identity_entity_graph/config.py`
- `src/fraud_detection/ingestion_gate/logging_utils.py`

---

## Entry: 2026-02-05 20:36:00 — Phase 2 implementation plan (storage + rebuildability)

### Problem / goal
Implement Phase 2 of the IEG plan: retention/TTL posture and explicit replay/backfill inputs so rebuilds are deterministic, auditable, and aligned to EB/archive windows.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md` (Phase 2 DoD)
- RTDL pre‑design decisions (EB retention windows + archive truth posture)
- IEG design‑authority (rebuild explicit, no silent “latest”)

### Decision trail (live)
1) **Retention policy is explicit config**: add `retention_ref` per profile; define retention windows aligned to EB (local parity 1 day; dev/prod 7 days).
2) **Prune is explicit**: provide a `--prune` flag that applies retention policy; no automatic deletion by default.
3) **Replay/backfill is declared**: add a replay manifest (YAML/JSON) with stream_id, topic/partition ranges, and pins; replay runs only with explicit manifest.
4) **Auditable basis**: store replay manifest + resulting graph_version in a `ieg_replay_basis` table.
5) **Reset is explicit**: replay may optionally wipe projection tables before apply (`--reset`).

### Planned files / paths
- Config: `config/platform/ieg/retention_*.yaml`
- Profile wiring: add `retention_ref` under `ieg.policy` in `config/platform/profiles/*`
- Code: `src/fraud_detection/identity_entity_graph/projector.py`, `store.py`, `config.py` (retention + replay)
- New table: `ieg_replay_basis` in both SQLite/Postgres stores.

### Validation plan (Phase 2)
- Unit: retention prune deletes only when enabled; no prune when disabled.
- Unit: replay manifest validation rejects missing basis fields.
- Smoke: replay manifest is recorded with graph_version after run.

---

## Entry: 2026-02-05 21:12:00 — Phase 2 implemented (retention + replay manifest)

### Summary of changes
- Implemented explicit retention policy plumbing + manual prune/reset for IEG projection stores.
- Added replay manifest support (YAML/JSON) with explicit basis recording for auditable replays.
- Added replay basis persistence (`ieg_replay_basis`) and graph_version lookup for replay runs.
- Added unit tests for retention pruning and replay manifest/basis recording.

### Key mechanics (as implemented)
- **Retention policy**: loaded from `retention_ref` (per profile), with explicit TTLs for entities/identifiers/edges/apply_failures/checkpoints. No automatic deletion; prune only on `--prune`.
- **Prune semantics**: deletes by `last_seen_ts_utc` (entities/identifiers/edges), `recorded_at_utc` (apply_failures), and `updated_at_utc` (checkpoints). Checkpoint pruning recomputes graph_version.
- **Replay manifest**: declarative basis with `topics[]` + `partitions[]` (+ optional `from_offset`/`to_offset`) and optional `pins`. Run is explicit via `--replay-manifest`; pins mismatches are recorded as apply_failures.
- **Replay basis**: recorded in `ieg_replay_basis` with manifest_json, basis_json, replay_id (sha256), and resulting graph_version.
- **Reset**: explicit `--reset` wipes all projection tables prior to replay/backfill.

### Files updated/added
- Config:
  - `config/platform/ieg/retention_v0.yaml` (dev/prod defaults)
  - `config/platform/ieg/retention_local_v0.yaml` (local/local_parity)
  - `config/platform/profiles/{local,local_parity,dev,prod}.yaml` (added `retention_ref`)
- Code:
  - `src/fraud_detection/identity_entity_graph/config.py` (IegRetention policy loader)
  - `src/fraud_detection/identity_entity_graph/store.py` (prune/reset/replay_basis/current_graph_version)
  - `src/fraud_detection/identity_entity_graph/replay.py` (ReplayManifest parsing + basis)
  - `src/fraud_detection/identity_entity_graph/projector.py` (replay ranges, pins mismatch, CLI flags)
- Tests:
  - `tests/services/identity_entity_graph/test_projection_store.py` (retention prune)
  - `tests/services/identity_entity_graph/test_replay_manifest.py` (manifest + basis)

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (7 passed)
