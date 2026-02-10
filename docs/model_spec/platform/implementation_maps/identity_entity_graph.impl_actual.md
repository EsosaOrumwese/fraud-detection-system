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

## Entry: 2026-02-05 20:15:00 — Phase 2 replay-manifest validation run

### Run
- Profile: `config/platform/profiles/local_parity.yaml`
- platform_run_id: `platform_20260205T201203Z`
- Replay manifest: `scratch_files/ieg_replay_manifest_small.yaml`
- Projection DB: `runs/fraud-platform/platform_20260205T201203Z/identity_entity_graph/projection/identity_entity_graph.db`

### Results
- processed: 80
- `ieg_dedupe`: 80
- `ieg_entities`: 175
- `ieg_identifiers`: 175
- `ieg_apply_failures`: 0
- `ieg_checkpoints`: 4
- `ieg_graph_versions`: 1
- `ieg_replay_basis`: 1

---

## Entry: 2026-02-05 20:18:00 — Fix IEG topic list to match traffic stream names

### Problem / goal
IEG topics list used `fp.bus.traffic.v1`, but v0 default traffic is split into fraud/baseline streams. This caused Kinesis read attempts to target a non-existent stream.

### Decision
Update IEG topics list to include `fp.bus.traffic.fraud.v1` and `fp.bus.traffic.baseline.v1` instead of `fp.bus.traffic.v1`.

### Files updated
- `config/platform/ieg/topics_v0.yaml`

---

## Entry: 2026-02-05 20:18:00 — Phase 3 implementation plan (query surface)

### Problem / goal
Implement Phase 3 of the IEG build plan: a deterministic, read‑only query surface for identity resolution, entity profiles, and neighbors, aligned to RTDL pins and flow narrative (IEG provides context + graph_version).

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md` (Phase 3 DoD)
- RTDL pre-design decisions (graph_version provenance; explicit failures; no merges)
- IEG design authority (deterministic ordering, explicit conflicts, graph_version in responses)

### Decision trail (live)
1) **Query surface is a small Flask service** mirroring IG/SR patterns (`service.py`), with read‑only endpoints: resolve_identity, get_entity_profile, get_neighbors, and status.
2) **Scope is pinned by ContextPins**: require `{platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed}` in request payloads; run_id is accepted as legacy but not required.
3) **Deterministic ordering:** candidates are ordered by `(entity_type, entity_id)`; neighbors are ordered by `(entity_type, entity_id)` and grouped with sorted shared identifiers. Pagination uses stable keyset tokens to avoid offset drift.
4) **No merges in v0:** resolve_identity returns all candidates with an explicit `conflict=true` when >1; no collapsing.
5) **Integrity status:** include `graph_version` and `integrity_status` (CLEAN/DEGRADED) on every response; integrity is derived from apply‑failure count for the stream + scenario_run_id (failures do not block, but are visible).
6) **Neighbors definition (v0):** neighbors are other entities that share identifiers with the target entity under the same pins. This avoids inventing edges and stays deterministic until explicit edge construction is introduced.

### Planned files / paths
- `src/fraud_detection/identity_entity_graph/query.py` (query logic + validation)
- `src/fraud_detection/identity_entity_graph/service.py` (Flask API)
- `src/fraud_detection/identity_entity_graph/store.py` (add read helpers: apply_failure_count)
- Tests: `tests/services/identity_entity_graph/test_query_surface.py`

### Validation plan (Phase 3)
- Unit: resolve_identity returns deterministic ordering and conflict markers.
- Unit: get_neighbors returns stable, grouped shared identifiers and supports page tokens.
- Unit: integrity_status flips to DEGRADED when apply failures exist.

---

## Entry: 2026-02-05 20:23:00 — Phase 3 implemented (query surface)

### Summary of changes
- Added read‑only query surface (resolve identity, entity profile, neighbors, status) with deterministic ordering and explicit conflict signaling (no merges).
- Added query logic with ContextPins validation, graph_version + integrity_status in every response, and keyset pagination tokens bound to pins + graph_version.
- Implemented neighbor queries via shared identifiers (v0) to avoid invented edges; explicit, deterministic grouping.

### Files added/updated
- `src/fraud_detection/identity_entity_graph/query.py` (query logic + pagination tokens)
- `src/fraud_detection/identity_entity_graph/service.py` (Flask API)
- `src/fraud_detection/identity_entity_graph/store.py` (query helpers + apply_failure_count)
- `src/fraud_detection/identity_entity_graph/__init__.py` (exports)
- `tests/services/identity_entity_graph/test_query_surface.py` (query tests)

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (10 passed)

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

## Entry: 2026-02-05 20:30:00 — Phase 3 live query demo (HTTP service)

### Run
- Service: `src/fraud_detection/identity_entity_graph/service.py`
- Profile: `config/platform/profiles/local_parity.yaml`
- Host/port: `127.0.0.1:8091`
- Projection DB: `runs/fraud-platform/platform_20260205T201203Z/identity_entity_graph/projection/identity_entity_graph.db`

### Results (sample)
- `/v1/ops/status`: `graph_version=346174b68f8bab4c8248004ec7112f1cb531d82e7e9c559498b977cab2a0a85a`, `integrity_status=CLEAN`, `apply_failure_count=0`
- `/v1/query/resolve`: returned 1 candidate for `flow_id=2417673993654239652`
- `/v1/query/profile`: returned flow profile for `entity_id=20ec5d4b...` with first/last seen timestamps
- `/v1/query/neighbors`: empty neighbor list for this entity (expected for single-identifier flow)

---

## Entry: 2026-02-05 20:35:00 — Phase 4 implementation plan (ops + degrade signals)

### Problem / goal
Implement Phase 4 of the IEG plan: operational metrics, explicit health posture, and optional reconciliation artifact so RTDL/Obs/Gov can reason about IEG lag/integrity.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/identity_entity_graph.build_plan.md` (Phase 4 DoD)
- RTDL pre‑design decisions (explicit degrade, watermark meaning, health visibility)
- IEG design authority (integrity signal; no hidden repairs)

### Decision trail (live)
1) **Metrics source of truth**: add an `ieg_metrics` counter table keyed by `(stream_id, scenario_run_id, metric_name)` and update counters inside projection store apply paths.
2) **Counters tracked**: `events_seen`, `mutating_applied`, `unusable`, `irrelevant`, `duplicate`, `payload_mismatch` (v0 minimal; extra counters allowed). These support required DoD counters without external telemetry.
3) **Health posture**: status endpoint computes `watermark_age_seconds` and `checkpoint_age_seconds` from checkpoints, plus `apply_failure_count` and metrics. Health state is `GREEN/AMBER/RED` with pinned default thresholds (configurable later).
4) **Integrity signal**: `integrity_status=CLEAN` when apply_failure_count=0 else `DEGRADED` (explicit; no silent masking).
5) **Reconciliation artifact**: provide a small CLI to write a run‑scoped JSON artifact with `graph_version` + basis snapshot (from `ieg_graph_versions`).

### Planned files / paths
- `src/fraud_detection/identity_entity_graph/store.py` (metrics table + counters + checkpoint summary)
- `src/fraud_detection/identity_entity_graph/query.py` (health/metrics computation)
- `src/fraud_detection/identity_entity_graph/service.py` (status/reconciliation endpoints)
- `src/fraud_detection/identity_entity_graph/reconcile.py` (artifact writer)
- Tests: extend `tests/services/identity_entity_graph/test_projection_store.py` for metrics counters

### Validation plan (Phase 4)
- Unit: counters increment across applied/duplicate/unusable/irrelevant paths.
- Unit: health status returns expected AMBER/RED with synthetic timestamps.
- Smoke: reconciliation artifact writes to run‑scoped path with graph_version + basis.

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

## Entry: 2026-02-05 20:45:00 — Phase 4 implemented (ops + degrade signals)

### Summary of changes
- Added operational metrics counters (`ieg_metrics`) updated on apply paths (events_seen, mutating_applied, unusable, irrelevant, duplicate, payload_mismatch).
- Added status computation of watermark/checkpoint ages and health posture (GREEN/AMBER/RED) with explicit reasons.
- Added reconciliation reader endpoint and CLI artifact writer.

### Files updated/added
- `src/fraud_detection/identity_entity_graph/store.py` (metrics table, counters, checkpoint summary, graph_basis)
- `src/fraud_detection/identity_entity_graph/query.py` (health + metrics in status)
- `src/fraud_detection/identity_entity_graph/service.py` (ops reconciliation endpoint)
- `src/fraud_detection/identity_entity_graph/reconcile.py` (artifact writer)
- `tests/services/identity_entity_graph/test_projection_store.py` (metrics counter test)

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (11 passed)
- Reconciliation artifact written to `runs/fraud-platform/platform_20260205T201203Z/identity_entity_graph/reconciliation/reconciliation.json`

---

## Entry: 2026-02-05 21:00:00 — Phase 5 implemented (bounded buffering + batch apply)

### Summary of changes
- Added explicit `max_inflight` buffering per (topic, partition) and `batch_size` drain logic to the projector. Intake pauses when buffers are full; no drops.
- Configurable batch size keeps deterministic per-partition ordering while allowing bounded batch processing.
- Added `max_inflight` and `batch_size` wiring to local/local_parity/dev/prod profiles.

### Files updated
- `src/fraud_detection/identity_entity_graph/projector.py` (buffered intake + batch drain)
- `src/fraud_detection/identity_entity_graph/config.py` (wiring knobs)
- `config/platform/profiles/{local,local_parity,dev,prod}.yaml` (explicit values)

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (11 passed)
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

---

## Entry: 2026-02-05 21:50:00 — Parity buffering validation + run-scope drift findings

### Run / evidence
- platform_run_id: `platform_20260205T212544Z`
- scenario_run_id: `dce02beeb230f669e01fad7f9d061f11`
- WSP emitted: 800 (200 per output) via READY re-emit (message_id `ccee876be4566994084d2e8c669881b6dd2aee5e3038e4b72ad54f88a5c7d3e6`).
- IG receipts: 800 under `s3://fraud-platform/platform_20260205T212544Z/ig/receipts/`
- EB (localstack) counts by stream: traffic.fraud=200, arrival_events=200, arrival_entities=194, flow_anchor.fraud=196 (duplicates dropped by IG).
- IEG projection DB: `runs/fraud-platform/platform_20260205T212544Z/identity_entity_graph/projection/identity_entity_graph.db`

### Buffering / load behavior
- IEG run_once loop processed counts: `[200, 200, 200, 190, 0]` (total 790).
- Multi-pass draining confirms bounded buffering/backpressure behavior under load (batch_size=50, max_inflight=200).
- IEG counts: `ieg_dedupe=790`, `ieg_apply_failures=0`, `ieg_checkpoints=4`, `ieg_graph_versions=1`.

### Drift vs flow narrative (run-scope / replay-basis)
Observed drift relative to the flow narrative requirement that IEG be run-scoped and built from a single replay basis:
1) No platform_run_id gating at intake: IEG currently accepts any EB event and does not filter to a single platform_run_id in non-replay mode.
2) Dedupe key excludes platform_run_id: dedupe is sha256(scenario_run_id + class_name + event_id); repeated runs with the same scenario_run_id can collide.
3) Checkpoint/graph_version not run-scoped: ieg_checkpoints, ieg_graph_versions, and ieg_metrics are keyed only by stream_id (no platform_run_id), so multiple runs can mix offsets in a shared projection.
4) Apply failures lack platform_run_id: failures are only keyed by stream_id + scenario_run_id; cross-run attribution is ambiguous.
5) Replay-basis enforcement only in explicit replay mode: the “same replay basis” constraint is enforced only when a replay manifest is supplied.

### Proposed fixes (run-scope hardening)
1) Require platform_run_id for non-replay runs (fail closed): add IEG_REQUIRED_PLATFORM_RUN_ID (or profile flag) and drop/quarantine any EB event whose platform_run_id does not match the required value.
2) Run-scoped stream identity: incorporate platform_run_id into the IEG stream_id (e.g., ieg.v0::<platform_run_id>), and key ieg_checkpoints, ieg_graph_versions, and ieg_metrics by that composite stream id. This isolates replay bases per run.
3) Dedupe key update: include platform_run_id in the dedupe key and store it explicitly in ieg_dedupe and ieg_apply_failures for audit and run separation.
4) Apply-failure attribution: add platform_run_id column + index to ieg_apply_failures so integrity signals are run-scoped.
5) Optional strict mode for non-manifest runs: when no replay manifest is provided, enforce that all processed events share the same platform_run_id (first seen locks the run scope). If a different run_id appears, record RUN_SCOPE_MISMATCH and halt or quarantine.
6) Graph_version exposure: include platform_run_id in any graph_version responses/records so downstream consumers can assert they are using the correct run scope.

These fixes align the implementation with the narrative’s “run-scoped + single replay basis” posture and prevent cross-run contamination in local/parity and beyond.
---

## Entry: 2026-02-05 22:00:00 — Plan to harden IEG run-scope + dedupe (drift fixes)

### Problem / goal
Close run-scope drift against the flow narrative: ensure IEG is run-scoped, built from a single run evidence basis, and exposes graph_version tied to platform_run_id. Fix dedupe and audit attribution to prevent cross-run contamination.

### Authorities / inputs
- Flow narrative (IEG run-scoped + single replay basis) in `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- RTDL pre-design decisions (ContextPins, provenance, fail-closed)
- IEG build plan Phase 4.2 (run-scoped projection + deterministic replay)

### Decisions (planned)
1) **Require platform_run_id for non-replay runs** and fail closed when missing (`PLATFORM_RUN_ID_MISSING`) or mismatched (`RUN_SCOPE_MISMATCH`).
2) **Run-scoped stream identity**: derive stream_id as `graph_stream_base::platform_run_id` and bind store state to that stream id. If platform_run_id is not pre-configured, lock on first valid event and rebind stream id before applying state.
3) **Dedupe key includes platform_run_id**; persist platform_run_id on dedupe + apply-failure rows for audit attribution.
4) **Run-scope guardrail**: when run scope is locked, reject any event whose platform_run_id deviates (quarantine via apply-failure).
5) **Expose run scope in graph_version responses**: include stream_id/platform_run_id in status + reconciliation outputs so downstream consumers can assert correct scope.

### Planned changes
- `src/fraud_detection/identity_entity_graph/config.py`: add `required_platform_run_id` + `lock_run_scope_on_first_event` wiring; compute `graph_stream_id` from base + platform_run_id.
- `src/fraud_detection/identity_entity_graph/projector.py`: enforce platform_run_id presence + mismatch handling; lock run scope on first valid event; rebind store stream_id; update dedupe_key call.
- `src/fraud_detection/identity_entity_graph/ids.py`: include platform_run_id in dedupe key; include platform_run_id in scope key for entity_id derivation.
- `src/fraud_detection/identity_entity_graph/store.py`: add platform_run_id columns to dedupe + apply_failures; add `rebind_stream_id`; update inserts/queries and failure recording.
- `src/fraud_detection/identity_entity_graph/query.py`: include graph scope (stream_id + platform_run_id) in status and query responses.
- `src/fraud_detection/identity_entity_graph/reconcile.py`: include stream_id/platform_run_id in reconciliation artifact.
- Tests: update IEG store/query tests for new dedupe_key signature and platform_run_id-aware failures.

### Validation plan
- `python -m pytest tests/services/identity_entity_graph -q`
- Manual sanity: run IEG projector with parity env and confirm apply failures include RUN_SCOPE_MISMATCH when platform_run_id differs.
---

## Entry: 2026-02-05 22:10:00 — Run-scope hardening implemented (IEG)

### Summary of changes
- Enforced platform_run_id run scope at intake (missing/mismatch => apply-failure with RUN_SCOPE_MISMATCH).
- Dedupe key now includes platform_run_id and platform_run_id is persisted in dedupe + apply-failure rows.
- Stream identity is run-scoped: graph_stream_id derived as `graph_stream_base::platform_run_id` when required is set, or locked on first valid event with store rebind.
- Query/reconciliation responses now include graph_scope (stream_id + platform_run_id when available).
- Added apply-failures scope index and automatic schema column adds for new platform_run_id fields.

### Files updated
- `src/fraud_detection/identity_entity_graph/config.py` (run-scope wiring + stream_id derivation)
- `src/fraud_detection/identity_entity_graph/projector.py` (platform_run_id enforcement, run-scope lock + rebind, dedupe change)
- `src/fraud_detection/identity_entity_graph/ids.py` (dedupe key + scope key includes platform_run_id)
- `src/fraud_detection/identity_entity_graph/store.py` (platform_run_id columns + rebind + index + failure filtering)
- `src/fraud_detection/identity_entity_graph/query.py` (graph_scope surfaced in responses)
- `src/fraud_detection/identity_entity_graph/reconcile.py` (graph_scope in artifact)
- `tests/services/identity_entity_graph/*` (dedupe + new params)

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (11 passed)
---

## Entry: 2026-02-05 22:25:00 — Phase 6 validation plan (corrective entry)

### Problem / goal
Complete Phase 6 validation for IEG: determinism, watermark monotonicity, and EB→projection integration test coverage.

### Why corrective
Phase 6 coding began before a formal plan entry. This entry records the intended plan and decisions after the fact to keep the decision trail auditable.

### Planned tests
1) **Replay determinism**: identical EB offsets ⇒ same graph_version + identical projection counts.
2) **Watermark monotonicity**: out-of-order event timestamps must not regress watermark (max ts_utc wins).
3) **Integration projection**: file-bus sample events (traffic + context) yield deterministic, non-empty projection with expected entity/identifier counts and zero apply failures.

### Targets
- New tests under `tests/services/identity_entity_graph/` using file-bus + projector with a temporary profile.
- Assertions rely on schema-valid envelopes with full ContextPins.
---

## Entry: 2026-02-05 22:27:00 — Phase 6 validation implemented (IEG)

### Tests added
- `tests/services/identity_entity_graph/test_projector_determinism.py`
  - Replay determinism: same EB sample ⇒ identical graph_version + counts.
  - Watermark monotonicity: decreasing ts_utc does not regress watermark.
  - Integration projection: EB sample events ⇒ deterministic projection (dedupe=4, entities=8, identifiers=8, apply_failures=0).

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (14 passed)
---

## Entry: 2026-02-05 22:35:00 — Phase 7 plan (deployment + config, run_config_digest)

### Problem / goal
Complete Phase 7: ensure env ladder config stays aligned, secrets remain runtime-only, and IEG emits a run_config_digest for run-level pinning in query/reconciliation outputs.

### Decisions (plan)
1) **Compute run_config_digest** for IEG from policy + wiring refs (classification, identity_hints, class_map, partitioning_profiles, retention, topics) plus deterministic extras (event_bus_kind, graph_stream_base, lock_run_scope_on_first_event). Do not include platform_run_id so the digest is stable across runs.
2) **Persist run_config_digest** in graph_versions table and surface in query/status/reconciliation responses.
3) **Keep env ladder unchanged**: use existing env placeholders; no secrets added to profiles.

### Planned changes
- `src/fraud_detection/identity_entity_graph/config.py`: compute run_config_digest during profile load.
- `src/fraud_detection/identity_entity_graph/store.py`: add run_config_digest to graph_versions table + storage; expose current_run_config_digest.
- `src/fraud_detection/identity_entity_graph/query.py`: include run_config_digest in status/query responses and graph_scope output.
- Tests: extend determinism test to assert run_config_digest present when using a profile.

### Validation plan
- `python -m pytest tests/services/identity_entity_graph -q`

## Entry: 2026-02-05 22:44:00 — Phase 7 implemented (run_config_digest pinning)

### Decisions (implemented)
1) **run_config_digest inputs**: policy refs (classification, identity_hints, retention, class_map, partitioning_profiles) + deterministic wiring extras (event_bus_kind, graph_stream_base, lock_run_scope_on_first_event, sorted event_bus_topics). Exclude platform_run_id, projection_db_dsn, and runtime secrets so the digest is stable across runs.
2) **Persistence + exposure**: persist run_config_digest alongside graph_version in ieg_graph_versions and surface in query status/resolve/profile/neighbors plus reconciliation artifacts.

### Implementation
- `src/fraud_detection/identity_entity_graph/config.py`: added run_config_digest to IegPolicy and compute from normalized config payload during profile load.
- `src/fraud_detection/identity_entity_graph/store.py`: added run_config_digest column to ieg_graph_versions (SQLite/Postgres + auto-migration), stored with graph_version updates, and exposed via current_run_config_digest + graph_basis.
- `src/fraud_detection/identity_entity_graph/projector.py`: passes run_config_digest into store.
- `src/fraud_detection/identity_entity_graph/query.py`: surfaces run_config_digest in status + query responses and reconciliation payloads.
- `src/fraud_detection/identity_entity_graph/reconcile.py`: includes run_config_digest in reconciliation artifact JSON.
- `tests/services/identity_entity_graph/test_projector_determinism.py`: assert run_config_digest is populated and consistent across replay runs.

### Invariants / guarantees
- run_config_digest is deterministic for a given policy/wiring bundle and is run-stable (platform_run_id excluded).
- graph_version remains replay-deterministic; run_config_digest anchors the configuration used to produce it.

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` (14 passed).

---

## Entry: 2026-02-06 08:46:47 — Phase 4.2 (IEG) closure plan: IEG-only DoD

### Scope (IEG-only items we can finish now)
- 4.2.E explicit migrations (replace runtime ALTER posture).
- 4.2.G partial: health/lag/apply-failure counters + run-scoped health artifact.
- 4.2.H backpressure/bounded buffers + batch apply safeguards.
- 4.2.I reconciliation artifact writer (offset basis + graph_version).
- 4.2.J deepen tests (replay determinism, payload mismatch, watermark monotonicity).
- 4.2.K partial: OTel-style counters export hooks; EB-only replay manifest generator.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` Phase 4.2 DoD.
- `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- Platform rails (ContextPins, append-only, idempotency, no-PASS-no-read).

### Decisions
- Add explicit migration runner for IEG schema (SQLite/Postgres) and replace runtime ALTER usage with versioned migrations.
- Produce run-scoped reconciliation artifact at `runs/fraud-platform/<run_id>/identity_entity_graph/reconciliation/replay_basis.json` containing topics, partitions, next_offset, graph_version, run_config_digest.
- Health artifact includes lag counters, apply failures, and last watermark; RED when lag exceeds threshold or apply failures above threshold.
- Replay manifest generator is EB-only: generates manifest from EB offsets (no Archive dependency).

### Planned steps
1) Inspect IEG store/schema creation and replace runtime ALTER with migrations.
2) Implement a migration runner and invoke at projector startup.
3) Add metrics counters + run-scoped health JSON.
4) Implement reconciliation writer for offset basis + graph_version.
5) Implement EB replay manifest generator.
6) Add tests for replay determinism, payload mismatch, and watermark monotonicity.
7) Update IEG build plan if needed and logbook.

### Invariants
- Derived state rebuildable from EB offsets alone.
- No schema changes without migration entries.
- Health/metrics are low-overhead and run-scoped; no payload copies.


---

## Entry: 2026-02-06 09:00:25 — Implemented Phase 4.2 IEG-only closures (migrations, health, reconciliation, replay manifest)

### Changes applied
- Introduced explicit IEG migrations and removed runtime ALTER posture.
- Added run-scoped health + metrics + reconciliation artifacts from projector.
- Added backpressure logging counters and bounded buffer checks.
- Added EB-only replay manifest generator from current graph basis.

### Files touched
- `src/fraud_detection/identity_entity_graph/migrations.py`
- `src/fraud_detection/identity_entity_graph/store.py`
- `src/fraud_detection/identity_entity_graph/projector.py`
- `src/fraud_detection/identity_entity_graph/config.py`
- `src/fraud_detection/identity_entity_graph/replay_manifest_writer.py`
- `tests/services/identity_entity_graph/test_replay_manifest.py`

### Behavior
- Projector writes:
  - `runs/fraud-platform/<run_id>/identity_entity_graph/health/last_health.json`
  - `runs/fraud-platform/<run_id>/identity_entity_graph/metrics/last_metrics.json`
  - `runs/fraud-platform/<run_id>/identity_entity_graph/reconciliation/reconciliation.json`
- Replay manifest writer outputs:
  - `runs/fraud-platform/<run_id>/identity_entity_graph/replay/replay_manifest.json`

### Tests
- `python -m pytest tests/services/identity_entity_graph -q`

### Remaining Phase 4.2 dependencies (non‑IEG)
- OFP/DF integration compatibility checks.
- Archive-based replay manifests (beyond EB-only).
- DL/DF consume IEG health signals for degrade posture.

---

## Entry: 2026-02-06 15:09:54 — IEG flow narrative + operating posture (v0 state)

### Why this entry
Capture the **current, as‑implemented** IEG flow and how we **operate** it today (local_parity), including the fact that it is **not auto‑started** and defaults to `--once`. This provides a narrative checkpoint for “where we are” before calling the plane green.

### Authorities / inputs
- IEG design authority: `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- RTDL flow narrative: `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- Local parity runbook: `docs/runbooks/platform_parity_walkthrough_v0.md`
- IEG implementation (projector, store, config, hints): `src/fraud_detection/identity_entity_graph/`

### Current flow narrative (implemented)
1) **EB intake (reader):** `IdentityGraphProjector` reads admitted EB events (Kinesis in parity) using `KinesisEventBusReader`. Topics are explicit in profile or a fixed stream is used with topic filtering.  
2) **Envelope validation:** canonical envelope schema is enforced; invalid envelopes are recorded in `ieg_apply_failures` and checkpoints advance.  
3) **Pin validation + run scoping:** required pins are enforced per class map; `platform_run_id` required. If `IEG_REQUIRED_PLATFORM_RUN_ID` is set (parity run‑scoped), mismatches are recorded as failures. Optional lock‑on‑first‑event (run‑scope hardening) rebinds stream_id to the first run.  
4) **Classification:** event type is mapped to a class; graph‑irrelevant events only advance checkpoints (no mutation).  
5) **Identity hints:** v0 uses deterministic field‑map rules (`identity_hints_v0.yaml`). Missing hints yield `IDENTITY_HINTS_MISSING` failure.  
6) **Dedupe + payload hash:** dedupe key = hash(platform_run_id + scenario_run_id + class + event_id); payload hash covers `{event_type, schema_version, payload}`. Duplicates or payload mismatches are recorded and checkpoints advance.  
7) **Projection writes:** entities + identifiers are upserted with run pins; **edges are not written in v0** (edge logic deferred).  
8) **Checkpoint + graph_version:** per topic/partition checkpoints advance; `graph_version` is derived from basis offsets and written with `run_config_digest`.  
9) **Operational artifacts:** projector emits `health`, `metrics`, and `reconciliation` JSON under `runs/fraud-platform/<run_id>/identity_entity_graph/`.

### Current operating posture (local_parity)
- **IEG is not auto‑started** in parity; it is run explicitly after EB has events.  
- **Default parity mode:** `--once` (bounded, deterministic validation).  
- **Live parity mode (optional):** run without `--once` (run_forever) + set `IEG_REQUIRED_PLATFORM_RUN_ID` and `IEG_LOCK_RUN_SCOPE=true` to keep it run‑scoped.  
- **IEG is a projector, not a service**: it reads EB and materializes projection DB + artifacts. The query service is optional and separate.

### Where to operate it
- Runbook section: `docs/runbooks/platform_parity_walkthrough_v0.md` → IEG step 11.  
- Outputs (run‑scoped):  
  - `runs/fraud-platform/<run_id>/identity_entity_graph/projection/identity_entity_graph.db`  
  - `runs/fraud-platform/<run_id>/identity_entity_graph/health/last_health.json`  
  - `runs/fraud-platform/<run_id>/identity_entity_graph/metrics/last_metrics.json`  
  - `runs/fraud-platform/<run_id>/identity_entity_graph/reconciliation/reconciliation.json`

### Invariants (v0 state)
- IEG consumes **admitted EB events only**; no side‑door inputs.  
- **Run‑scoped projection** when `IEG_REQUIRED_PLATFORM_RUN_ID` is set.  
- **Idempotent apply** under replay; payload mismatch is explicit.  
- **No edges** written in v0; projection is nodes + identifiers only.

---

## Entry: 2026-02-07 12:59:30 - Plan: align IEG semantic dedupe tuple to corridor law

### Problem
Current IEG dedupe identity uses `platform_run_id + scenario_run_id + class_name + event_id`. Pinned corridor law for RTDL parity is semantic idempotency by `(platform_run_id, event_class, event_id)` with `payload_hash` anomaly discipline. Keeping `scenario_run_id` inside tuple can cause false non-duplicates for the same platform-scoped event identity.

### Authorities
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`

### Decision and migration posture
1. Change dedupe key builder to accept `(platform_run_id, event_class, event_id)` only.
2. Continue requiring/persisting `scenario_run_id` as a pin for run provenance and failure diagnostics, but not semantic dedupe identity.
3. Keep `event_class` source as canonical class-map result (`class_for(event_type)`), not classification lane (`GRAPH_*`).
4. Preserve payload-hash mismatch behavior (`PAYLOAD_HASH_MISMATCH`) on same dedupe key.

### Files planned
- `src/fraud_detection/identity_entity_graph/ids.py`
- `src/fraud_detection/identity_entity_graph/projector.py`
- `tests/services/identity_entity_graph/*` (targeted updates for key recipe expectations)

### Validation plan
- `python -m pytest tests/services/identity_entity_graph -q`
- ensure duplicate and payload mismatch semantics remain unchanged except tuple identity axes.

---

## Entry: 2026-02-07 13:09:19 - IEG dedupe tuple drift closed

### What changed
1. Updated IEG dedupe key recipe from:
   - `platform_run_id + scenario_run_id + class_name + event_id`
   to:
   - `platform_run_id + event_class + event_id`.
2. Updated projector dedupe generation to use the new tuple while preserving:
   - required `scenario_run_id` pin checks,
   - payload hash mismatch anomaly behavior,
   - class-map canonical event class source.
3. Updated IEG tests to use the new dedupe key contract.

### Files changed
- `src/fraud_detection/identity_entity_graph/ids.py`
- `src/fraud_detection/identity_entity_graph/projector.py`
- `tests/services/identity_entity_graph/test_query_surface.py`
- `tests/services/identity_entity_graph/test_projection_store.py`

### Validation
- `python -m pytest tests/services/identity_entity_graph -q` -> `15 passed`.

### Invariant confirmation
- `scenario_run_id` remains mandatory run provenance pin for IEG processing, but is no longer part of semantic dedupe identity.

---

## Entry: 2026-02-07 14:24:00 - Plan: classify DF output families as graph-irrelevant in v0

### Problem
IEG classification map defaults unknown event types to `graph_unusable`. With shared v0 traffic stream routing for DF outputs, `decision_response`/`action_intent` currently generate avoidable apply-failure noise.

### Decision and reasoning
1. Add `decision_response` and `action_intent` to `graph_irrelevant` in `config/platform/ieg/classification_v0.yaml`.
   - Reasoning: these families are intentionally non-mutating for IEG in v0.
2. Preserve default action and all existing mutating/irrelevant mappings.
   - Reasoning: avoid changing broader classification posture.
3. Validate via targeted projector test that these events advance checkpoints as irrelevant and do not add apply failures.

### Expected outcome
- Cleaner ops signals (no false unusable failures for DF outputs).
- Correct projection boundaries while retaining shared-stream parity posture.

---

## Entry: 2026-02-07 14:27:00 - Implemented IEG irrelevant classification for DF output families

### Change applied
Added DF output families to IEG `graph_irrelevant` classification set:
- `decision_response`
- `action_intent`

File changed:
- `config/platform/ieg/classification_v0.yaml`

### Effect on projector behavior
When these event types arrive on shared traffic stream:
- IEG advances checkpoints with `count_as="irrelevant"`,
- no `apply_mutation`,
- no `record_failure`/`ieg_apply_failures` noise for these families.

### Test coverage added
- `tests/services/identity_entity_graph/test_projector_determinism.py`
  - `test_df_output_families_are_irrelevant_no_apply_failure`
  - asserts:
    - `apply_failures == 0`,
    - dedupe table unchanged for ignored DF events,
    - `irrelevant` metric increments,
    - checkpoint advances to next offset.

### Validation evidence
- `python -m pytest tests/services/identity_entity_graph/test_projector_determinism.py -q` (included in targeted run) -> pass.
- `python -m pytest tests/services/identity_entity_graph -q` -> `16 passed`.
## Entry: 2026-02-08 14:47:54 - Plan: fix Postgres reserved identifier crash in IEG live projector

### Problem
`platform-ieg-projector-parity-live` fails at runtime with Postgres syntax error near `offset` while writing `ieg_apply_failures`.

### Plan
- Update IEG Postgres/SQLite migration DDL for `ieg_apply_failures` to quote `"offset"` identifier.
- Update IEG store SQL statements touching `ieg_apply_failures` inserts to reference `"offset"` consistently.
- Validate by re-running `make platform-ieg-projector-parity-live` startup.

### Invariant
No change to IEG replay semantics; only SQL identifier safety fix.

---
## Entry: 2026-02-08 15:30:54 - Implemented reserved-identifier fix and revalidated live IEG run

### Implementation applied
- Quoted `"offset"` in `ieg_apply_failures` DDL for sqlite/postgres migration branches.
- Quoted `"offset"` in insert statements that write `ieg_apply_failures`.

Files:
- `src/fraud_detection/identity_entity_graph/migrations.py`
- `src/fraud_detection/identity_entity_graph/store.py`

### Runtime validation evidence
Run scope:
- `platform_run_id=platform_20260208T151238Z`
- `scenario_run_id=9bad140a881372d00895211fae6b3789`

Evidence:
- live startup no longer fails with Postgres syntax error near `offset`.
- `runs/fraud-platform/platform_20260208T151238Z/identity_entity_graph/metrics/last_metrics.json`:
  - `events_seen=800`
  - `mutating_applied=800`
  - `apply_failure_count=0`

### Invariant check
No mutation/replay logic changed; fix is SQL identifier safety only.

---
## Entry: 2026-02-09 21:39:00 - Live-stream drift hardening: guarantee IEG health artifact emission for irrelevant-branch traffic

### Trigger
Full-platform live run showed `dl_health=RED` with required signal failure on `ieg_health` because run-scoped IEG health artifact was missing in the acceptance run path.

### Root cause
`IdentityGraphProjector` only emitted run-scoped artifacts once `_locked_scenario_run_id` was set, but this lock occurred late in record handling (after classification branch checks). For run-scoped traffic that resolves as `graph_irrelevant`, lock could remain unset and observability artifact emission could be skipped.

### Decision
Capture scenario scope immediately after envelope/run-scope/replay validation and before classification branching.

### Implementation
File: `src/fraud_detection/identity_entity_graph/projector.py`
- Added early scenario-run lock:
  - `scenario_run_id_hint = envelope.scenario_run_id or envelope.run_id`
  - if present and no prior lock, set `_locked_scenario_run_id`.
- Left mutation/failure semantics unchanged.

### Why this is safe
- No ownership drift: only observability emission gating changed.
- No event classification or projection mutation logic altered.
- Maintains fail-closed behavior for actual invalid/mismatched scope events.

### Regression coverage
File: `tests/services/identity_entity_graph/test_projector_determinism.py`
- Added `test_irrelevant_events_emit_run_scoped_health_artifact`:
  - publishes `decision_response` (IEG-irrelevant) with valid run pins,
  - runs projector,
  - asserts run-scoped health artifact exists,
  - asserts graph scope run ID and `irrelevant` metric value.

### Validation results
- `python -m py_compile src/fraud_detection/identity_entity_graph/projector.py tests/services/identity_entity_graph/test_projector_determinism.py` -> pass
- `python -m pytest -q tests/services/identity_entity_graph/test_projector_determinism.py` -> `7 passed`
- `python -m pytest -q tests/services/degrade_ladder/test_phase7_worker_observability.py` -> `2 passed`
## Entry: 2026-02-09 21:48:00 - Hardening: emit IEG run-scoped health/metrics even before scenario lock settles

### Problem
IEG observability emission was gated on `_locked_scenario_run_id`. During trim-horizon catch-up and mixed historical streams, that lock can lag while checkpoints are already advancing for the active run, leaving `identity_entity_graph/health/last_health.json` absent and causing downstream DL required-signal failure.

### Implementation
File changed:
- `src/fraud_detection/identity_entity_graph/projector.py`
  - `_emit_operational_artifacts` now emits whenever run root is known; scenario lock is no longer a hard gate.
  - uses `scenario_run_id = _locked_scenario_run_id or ""` for health/metrics writes.

### Validation
- Existing/new determinism tests still pass, including health-artifact emission coverage.
- Combined evidence run:
  - `pytest -q tests/services/identity_entity_graph/test_projector_determinism.py` -> pass.

### Invariant
No projection/mutation ownership changes; this is observability-availability hardening so DL can evaluate IEG signal from component-owned artifact path.
## Entry: 2026-02-09 22:10:00 - Pre-change lock: add IEG Kinesis start-position control for bounded parity runs

### Problem
IEG Kinesis consume path always used trim-horizon semantics. In local-parity bounded validation (`20/200`), this causes historical catch-up before current run flow and delays/obscures run-scoped closure.

### Decision
- Add `event_bus_start_position` to IEG profile wiring (`trim_horizon|latest`).
- Pass this value to Kinesis reader calls in projector.
- Keep default `trim_horizon` for backward compatibility; allow parity override via env/profile when needed.

### Validation
- run targeted identity graph tests after patch,
- confirm no regression in existing trim-horizon behavior,
- verify bounded parity run can use `latest` override.
