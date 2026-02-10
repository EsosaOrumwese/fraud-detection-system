# Platform Build Plan (v0)
_As of 2026-02-08_

## Purpose
Provide a platform-wide, production-shaped build plan for v0 that aligns component sequencing to the platform blueprint and truth-ownership doctrine. This plan is intentionally high-level and **progressively elaborated**: phases are pinned now; detailed steps are added only when a phase begins.

## Planning rules (binding)
- **Progressive elaboration:** start with Phase 1..Phase X; expand only the active phase into sections and DoD checklists as we enter it.
- **No half-baked phases:** do not advance until the phase DoD is fully satisfied and validated.
- **Rails first:** ContextPins, canonical envelope, no-PASS-no-read, by-ref refs, idempotency, append-only truth, deterministic registry resolution, explicit degrade posture.
- **Engine is a black box:** interface pack is the boundary; never reach into engine internals unless explicitly requested.

## v0 scope boundaries (expectations)
- Single-tenant, single-region, production-shaped semantics.
- Local/dev parity with the same rails (different operational envelope only).
- Minimal viable hot path with correct provenance and audit; no scale optimizations beyond correctness.
- No multi-region DR, no automated rollout gates beyond documented policy profiles.

## Phase plan (v0)

### Phase 1 — Platform substrate + rails
**Intent:** pin the shared rails and the local production-shaped substrate so every component implements the same semantics.

#### Phase 1.1 — Identity + envelope contracts
**Goal:** make the platform’s join semantics unambiguous and versioned.

**DoD checklist:**
- Canonical envelope fields are pinned and versioned (including `ts_utc`, `event_type`, `event_id`, `schema_version`, `manifest_fingerprint` + optional pins).
- Run identity pins are explicit and versioned:
  - canonical execution scope is `platform_run_id`,
  - scenario execution scope is `scenario_run_id`,
  - scenario/world pins include `scenario_id`, `manifest_fingerprint`, `parameter_hash`,
  - `seed` remains a required field for synthetic runs,
  - legacy `run_id` is optional alias only (never canonical).
- Time semantics are pinned (domain `ts_utc`, optional `emitted_at_utc`, ingestion time in IG receipts).
- Naming/alias mapping for any legacy fields is documented (no hidden drift).

#### Phase 1.2 — By‑ref artifact addressing + digest posture
**Goal:** pin how artifacts are referenced and verified across components.

**DoD checklist:**
- Platform object‑store prefix map is pinned (bucket + prefixes for SR/IG/DLA/Registry/etc.).
- Locator schema and digest posture are pinned (content digest, bundle manifest digest rules).
- Instance‑proof receipts path conventions are pinned (engine vs SR verifier receipts).
- Token order rules are pinned for partitioned paths (seed → parameter_hash → manifest_fingerprint → scenario_id → scenario_run_id → platform_run_id → utc_day).
- Canonical run-scoped roots use `platform_run_id`; `scenario_run_id` is retained for provenance and scenario reuse.

#### Phase 1.3 — Event bus taxonomy + partitioning rules
**Goal:** prevent drift on how traffic/control/audit are separated and replayed.

**DoD checklist:**
- Topic taxonomy pinned (traffic/control/audit minimum).
- Partitioning key rules pinned (deterministic, stable across envs).
- Replay semantics and retention expectations documented (v0 scope).

#### Phase 1.4 — Environment ladder profiles (policy vs wiring)
**Goal:** ensure local/dev/prod share semantics but differ in operational envelope only.

**DoD checklist:**
- Local/dev/prod profile schema pinned with clear separation between **policy config** and **wiring config**.
- Policy config is versioned and referenced by revision in receipts/outcomes where applicable.
- Promotion concept documented as profile change, not code change.
- Testing policy pinned: **local = smoke**, **dev = completion** (uncapped).

#### Phase 1.5 — Security + secrets posture
**Goal:** prevent provenance drift and avoid credential leakage.

**DoD checklist:**
- Secrets are runtime‑only; no secrets in artifacts, build plans, impl_actual, or logbooks.
- Provenance records use secret identifiers only (if needed), never secret material.
- Sensitive runtime artifacts are flagged to the user for review/quarantine.

### Local Stack Maximum‑Parity Plan (v0 add‑on)
**Intent:** make local behave like dev/prod by swapping file‑based backends for the same classes of services used in higher environments. This is an **opt‑in parity mode**; file‑based local remains for fast smoke, but parity mode should be the default for “no‑gymnastics” ladder climbs.

**Target parity shape (local = dev/prod semantics):**
- **Oracle Store:** S3‑compatible (MinIO) instead of local filesystem.
- **Event Bus:** Kinesis‑compatible (LocalStack) instead of file‑bus.
- **Control Bus:** Kinesis‑compatible (LocalStack) instead of file control bus.
- **IG indices:** Postgres (docker) instead of SQLite.
- **WSP checkpoints:** Postgres (docker) instead of file checkpoints.
- **Runtime shape:** same env var names, same wiring schema; only endpoints change per env.

#### Compose blueprint (local parity stack)
**Goal:** one local compose file that brings up the parity services.
- **MinIO** (S3‑compatible) for Oracle Store + platform object store.
- **LocalStack** with **Kinesis** for Event Bus + control bus.
- **Postgres** for IG admission/ops indexes + WSP checkpoints.
- Optional: **minio‑mc** init container to create buckets (`oracle-store`, `fraud-platform`).

#### Config blueprint (parity profile)
**Goal:** a dedicated local profile (e.g., `local_parity.yaml`) with the same wiring shape as dev/prod.
- `object_store.root: s3://fraud-platform` (path‑style S3 enabled).
- `oracle_root: s3://oracle-store/<run-root>` (same path shape as dev/prod).
- `event_bus_kind: kinesis` (LocalStack endpoint).
- `control_bus.kind: kinesis` (LocalStack endpoint).
- `wsp_checkpoint.backend: postgres` (DSN env var).
- `admission_db_path` replaced by DSN for Postgres‑backed IG index (new backend).
- Keep `policy.*` identical to dev/prod (speedup optionally elevated but same semantics).

#### Stepwise migration (no‑gymnastics ladder)
**Step 1 — Postgres index parity**
- Implement Postgres backend for IG admission/ops index.
- Wire `IG_ADMISSION_DSN` (env) into IG config; add migrations + health probe.
- Keep SQLite fallback for tests only.

**Step 2 — WSP checkpoint parity**
- Switch local parity profile to Postgres checkpoints (`WSP_CHECKPOINT_DSN`).
- Validate resume semantics across restarts.

**Step 3 — Event Bus parity**
- Turn on `event_bus_kind: kinesis` for local parity profile.
- Add LocalStack endpoint envs + stream bootstrapping step.
- Validate publish + replay via EB reader.

**Step 4 — Control Bus parity**
- Move READY control bus to LocalStack Kinesis.
- Validate WSP READY consumer in parity mode.

**Step 5 — Oracle Store parity**
- Point `oracle_root` to MinIO (`s3://oracle-store/...`).
- Update WSP to read via S3 paths only in parity mode; validate pack manifest + seal.

**Step 6 — Full chain parity smoke**
- Local parity smoke run (SR → WSP → IG → EB) using the parity profile.
- Confirm: no schema errors, stable offsets, IG receipts persisted in Postgres.

**Deliverables for parity mode:**
- `infra/local/docker-compose.platform-parity.yaml` (MinIO + LocalStack + Postgres).
- `config/platform/profiles/local_parity.yaml` (S3 + Kinesis + Postgres wiring).
- `make` targets to bootstrap buckets, streams, and run the parity smoke.

### Phase 2 — World Oracle + Stream Head (Oracle Store + WSP)
**Intent:** establish the sealed world boundary and the primary stream producer so the platform experiences bank‑like temporal flow.

#### Phase 2.1 — Oracle Store contract (sealed world boundary)
**Goal:** define immutable, by‑ref engine outputs as a first‑class platform boundary.

**DoD checklist:**
- Oracle Store prefix layout is pinned (local/dev/prod) with an explicit `oracle_root` that is runtime‑configurable.
- Immutability rules are explicit: sealed runs are write‑once; no overwrite in place.
- Locator + digest posture is pinned (content digest required; schema versioned).
- Oracle Store paths are referenced by SR `run_facts_view` only (no scanning; by‑ref only).

#### Phase 2.2 — WSP v0 stream head (primary runtime producer)
**Goal:** WSP streams engine business_traffic into IG under READY + run_facts_view.

**DoD checklist:**
- WSP consumes READY + `run_facts_view` and derives a StreamPlan (no “latest” scans).
- `business_traffic` **and** time‑safe `behavioural_context` outputs are streamed; truth products remain oracle‑only.
- Canonical envelope framing is enforced; event identity is stable and compatible with legacy pull framing where required.
- **Speedup factor is available in all envs** as a policy knob (semantics preserved across speeds).
- WSP never writes directly to EB; IG remains the only writer.
- WSP emits **single‑mode traffic** (baseline **or** fraud) and streams **per‑output** from the stream‑view.
- WSP streams outputs **concurrently by default** when multiple outputs are present (traffic + context); override for debug.

#### Phase 2.3 — WSP ↔ IG smoke path
**Goal:** prove WSP → IG admission under rails before refactoring SR/IG for full alignment.

**DoD checklist:**
- WSP streams a READY‑scoped run into IG with pass/fail evidence respected (no‑PASS‑no‑read).
- IG receipts reflect ADMIT/DUPLICATE/QUARANTINE outcomes with by‑ref evidence.

### Phase 3 — Control & Ingress plane alignment (SR + IG + EB)
**Intent:** align SR/IG/EB with the WSP‑first runtime truth and preserve rails.

#### Phase 3.1 — Scenario Runner readiness authority (SR)
**Goal:** SR remains the sole readiness authority and publishes the join surface that WSP/IG follow.

**DoD checklist:**
- SR publishes `run_facts_view` + READY with required PASS evidence and pins.
- READY is emitted only after evidence completeness (no PASS → no read).
- SR run ledger artifacts are immutable and append‑only (run_plan/run_record/run_status/run_facts_view).
- Reuse path is evidence‑based (locators + receipts), never “scan latest.”
- `run_facts_view` declares `traffic_delivery_mode` so WSP and IG do not both ingest.

**Status:** ready to proceed to IG; path‑alignment follow‑up noted (see platform.impl_actual).

#### Phase 3.2 — Ingestion Gate admission boundary (IG)
**Goal:** IG is the sole admission authority; push ingestion is primary; legacy pull remains optional/backfill.

**DoD checklist:**
- IG validates canonical envelope + payload schema (versioned) and enforces ContextPins when required.
- IG verifies required HashGates before admitting traffic.
- IG emits receipts with decision (ADMIT/DUPLICATE/QUARANTINE) and by‑ref evidence.
- IG stamps deterministic `partition_key` using policy profiles.

#### Phase 3.3 — Event Bus durability + replay (EB)
**Goal:** EB is the durable fact log with stable offsets and at‑least‑once delivery.

**DoD checklist:**
- EB append ACK implies durable `(stream, partition, offset)` assignment.
- Replay by offsets works with partition‑only ordering semantics.
- Idempotent publish and dedupe semantics are validated under retry.
- Traffic streams are provisioned and writable (`fp.bus.traffic.fraud.v1` default; `fp.bus.traffic.baseline.v1` when baseline mode is enabled).
- Context streams are provisioned and writable:
  - `fp.bus.context.arrival_events.v1`
  - `fp.bus.context.arrival_entities.v1`
  - `fp.bus.context.flow_anchor.fraud.v1` (fraud mode)
  - `fp.bus.context.flow_anchor.baseline.v1` (baseline mode)

#### Phase 3.4 — Control & Ingress E2E proof
**Goal:** demonstrate end‑to‑end READY → WSP stream → IG admission → EB replay under rails.

**DoD checklist:**
- SR READY → WSP streams → IG admits → EB replay works for pinned run.
- Truth ownership enforced: SR readiness authority; IG admission authority; EB offsets/replay only.
- The selected traffic channel receives events; context channels receive join surfaces for the same run.

**Status:** complete (v0 green).
**Meaning of “green”:** a parity run produces SR READY, WSP streams the **selected** traffic channel + context channels from stream view, IG writes run‑scoped receipts, and EB contains readable offsets for traffic + context streams under the same platform run id.

#### Phase 3 narrative flow (control & ingress with context streams)
**Intent:** keep Oracle Store offline, push only time‑safe context + traffic into EB, and make RTDL joins possible without preloading the future.

**Narrative flow (descriptive):**  
**Oracle Store** remains the immutable, offline truth. **SR** validates gates and emits READY with `run_facts_view` pins only when evidence passes.  
**WSP** consumes READY and emits two stream classes into IG:  
- **Traffic:** `s3_event_stream_with_fraud_6B` (default) and optionally `s2_event_stream_baseline_6B`.  
- **Context (time‑safe):** `arrival_events_5B`, `s1_arrival_entities_6B`, and `s3_flow_anchor_with_fraud_6B` (plus `s2_flow_anchor_baseline_6B` only when baseline runs are enabled).  
**IG** enforces canonical envelope + no‑PASS‑no‑read, then publishes admitted events into **EB**.  
**EB** is the durable log; RTDL consumes **traffic + context topics** and builds bounded state for joins. No RTDL component reads Oracle Store directly.

### Phase 4 — Real-time decision loop (IEG/OFP/DL/DF/AL/DLA)
**Intent:** turn admitted traffic into decisions and outcomes with correct provenance and audit.

#### RTDL v0 stack (locked for ladder parity)

**Locked tool stack (v0):**
- **Event Bus:** Kinesis (LocalStack in local‑parity; AWS Kinesis in dev/prod).
- **Object Store:** S3 (MinIO in local‑parity; AWS S3 in dev/prod).
- **Primary state store (IEG/OFP/DF/AL/DLA indices):** Postgres (local container in parity; RDS Postgres in dev/prod).
- **Runtime:** Python services/workers (same code paths in all envs).

**Explicit exclusions (v0):**
- No MLflow (learning/registry comes later in Phase 6).
- No Airflow (batch orchestration belongs to offline pipelines, Phase 6+).
- No extra graph DB or feature store; Postgres is authoritative for v0 projection + features.

**Rationale (ladder parity):**
Local‑parity uses the *same service classes* as dev/prod (S3/Kinesis/Postgres). Only endpoints and credentials change, not architecture. This minimizes ladder friction and prevents filesystem shortcuts.

**Definition of Done (DoD):**
- IEG projector builds graph projection with watermark-based graph_version.
- OFP builds feature snapshots with input_basis + snapshot hash; serves deterministic responses.
- DL computes explicit degrade posture and DF enforces it (no silent bypass).
- DF resolves bundles deterministically from Registry and emits decisions + action intents with provenance (bundle ref, snapshot hash, graph_version).
- AL executes intents effectively-once with idempotency and emits outcomes.
- DLA writes append-only audit records by-ref and supports lookup via refs.
- E2E: admitted event -> decision -> action outcome -> audit record with replayable provenance.

#### RTDL narrative flow (operational story)

- **Event Bus emits immediately (durable log, not a batch buffer).**  
  When IG admits a record, it publishes to EB (Kinesis/Kafka). EB assigns an offset/sequence and makes the event available **right away** to any consumer. RTDL can read live or replay from a past offset. EB ordering is per‑partition/shard; we do not assume global total order.

- **Context streams feed RTDL join state (no preloading).**  
  RTDL consumes **context topics** (arrival events/entities + flow anchors) and incrementally builds join state in its own Postgres store. This replaces preloading: the platform only has context once it has streamed in. Missing context triggers explicit degrade, not silent fallback.

- **IEG projects the world with explicit watermarks.**  
  IEG consumes EB partitions, updates its projection (graph/state), and advances a **graph_version / watermark**. Late or out‑of‑order events are handled by policy (e.g., allowed lateness); the watermark makes the snapshot boundary explicit. The projection is the “world” that every decision will reference.

- **OFP builds features from a pinned snapshot.**  
  OFP reads the projection at a specific graph_version and produces a **feature snapshot**. That snapshot is hashed and stamped with its **input basis** (graph_version + EB offsets used). This is how we guarantee reproducibility under replay.

- **DF + DL decide with provenance and explicit degrade posture.**  
  DF deterministically resolves the model bundle from the Registry and computes the decision. DL evaluates staleness/incompleteness and forces an **explicit degrade posture** when required. The decision carries bundle_ref + snapshot_hash + graph_version + EB offset basis.

- **AL executes idempotent effects.**  
  Actions are executed with idempotency keys derived from the decision + event_id, so replays or retries cannot double‑apply side effects. Outcomes are emitted with a stable outcome_id.

- **DLA records the truth (append‑only).**  
  DLA writes the permanent audit record that ties together the original EB event offsets, the feature snapshot hash, the decision bundle, and the action outcome. This is the compliance and replay trail.

**Event‑time semantics:**  
The platform uses the **canonical event time (`ts_utc`)** for windowing and temporal logic. Speedup only changes the pacing of delivery; it does **not** change ordering or event time. This is why the flow can appear “non‑intuitive” if you expect file order—**it is event‑time order**.

**Traffic stream semantics (post‑EB):**  
The EB traffic plane is **single‑mode for traffic stimuli per run**: a run is either **fraud** (`s3_event_stream_with_fraud_6B`) or **baseline** (`s2_event_stream_baseline_6B`). In local-parity wiring, derived families (for example DF/AL emissions) may share the traffic stream; non-trigger families are explicit non-apply/non-trigger inputs for RTDL projectors and trigger policy.

**v0 parity pin (shared traffic stream for DF outputs):**  
`decision_response` and `action_intent` may be admitted onto `fp.bus.traffic.fraud.v1` in local-parity for wiring convenience. OFP/IEG treat these families as explicit non-apply events (ignored/irrelevant), and DF trigger policy continues to block them as decision triggers.

**Context stream semantics (post‑EB):**  
Context topics are **separate from traffic** and provide join surfaces to downstream consumers. Fraud runs require `s3_flow_anchor_with_fraud_6B`; baseline runs require `s2_flow_anchor_baseline_6B`. Context retention/shape decisions are **deferred to Phase 4 (RTDL)**.

#### Control & Ingress pins (locked for implementation)
The following pins are now locked and should be implemented across SR/WSP/IG immediately.

- **Dedupe semantics:** IG dedupe tuple is `(platform_run_id, event_class, event_id)` and `payload_hash` is persisted for anomaly detection.
- **Run identity boundary (P0):** canonical run id for dedupe/receipts is `platform_run_id`; always carry `scenario_run_id` explicitly in READY/envelopes/receipts.
- **READY idempotency:** `message_id = sha256("ready|platform_run_id|scenario_run_id|bundle_hash_or_plan_hash")`.
- **Receipt minimum fields:** receipts include `event_class`, `payload_hash`, `admitted_at_utc`, `platform_run_id`, `scenario_run_id`, `eb_ref`, `policy_rev`, and `run_config_digest`.
- **Publish unknown success (P0):** admission state machine with `PUBLISH_IN_FLIGHT -> ADMITTED` and `PUBLISH_AMBIGUOUS` on timeout/unknown; no auto-republish.
- **WSP retry posture (P0):** retry 429/5xx/timeouts with bounded exponential backoff (same event_id); schema/policy 4xx are non-retryable.
- **Run-level config freeze (P1):** `run_config_digest` is stamped into READY; mid-run config changes are explicit policy_rev boundaries.

#### Control & Ingress pins (still open)
These remain open and will be resolved during RTDL Phase 4 planning and partitioning alignment work.

- **Partition key consistency:** locality across traffic + context topics is not fully guaranteed; decide whether to enrich traffic events with `merchant_id + arrival_seq` or accept cross-partition joins.
- **Partitioning profiles alignment (P1):** flow_anchor profiles use `flow_id` first; decide whether to pivot to merchant locality or document the different locality claim.
- **Health posture meaning:** confirm AMBER is observational (no gating) and RED gates admission with retry-after semantics.
- **Receipt durability after publish (P0):** finalize `receipt_write_failed` backfill behavior and any local spool mechanism.

#### Phase 4.1 — RTDL contracts + invariants (expanded)

##### 4.1.A — RTDL envelope + provenance contract
**Goal:** reuse canonical envelope for RTDL events and pin the provenance fields required for replay.

**DoD checklist:**
- Canonical envelope is used (no separate decision envelope).
- Envelope includes `payload_kind` (or `decision_kind`) to distinguish RTDL payloads.
- Required pins are enforced: `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` (legacy `run_id` optional alias only).
- Provenance fields are mandatory in RTDL payloads: `eb_offset_basis`, `graph_version`, `snapshot_hash`, `bundle_ref`.
- Error handling for missing pins/provenance is documented (fail‑closed).

##### 4.1.B — Offset + watermark semantics
**Goal:** make replay and ordering deterministic.

**DoD checklist:**
- EB offsets are the authoritative replay cursor (partition/shard scoped).
- Watermark / graph_version definition pinned and documented.
- Allowed lateness is **policy‑configurable** (default documented).
- Mapping `(partition, offset)` → projection state is deterministic.

##### 4.1.C — Feature snapshot contract
**Goal:** ensure feature snapshots are reproducible.

**DoD checklist:**
- Snapshot format is **JSON in S3** (v0) with optional compression.
- Snapshot carries `snapshot_hash`, `graph_version`, `eb_offset_basis`.
- Snapshot hash rule (ordering + encoding) is documented.
- Postgres stores snapshot index/refs only (truth in S3).

##### 4.1.D — Bundle resolution + decision contract
**Goal:** lock deterministic model selection and explicit degrade posture.

**DoD checklist:**
- `bundle_ref` is mandatory and deterministically resolved.
- Degrade posture is explicit and required in decision payload.
- Decision payload includes `bundle_ref`, `snapshot_hash`, `graph_version`, `eb_offset_basis`.
- Decision provenance rule documented (no silent fallback).

##### 4.1.E — Action intent + outcome contract
**Goal:** make effects idempotent and auditable.

**DoD checklist:**
- Action intent carries `decision_id` + `idempotency_key`.
- Outcome carries `outcome_id` + `decision_id` + action ref.
- Idempotency rule is pinned (same key → same effect).

##### 4.1.F — Audit record contract (DLA)
**Goal:** append‑only audit truth with fast lookup.

**DoD checklist:**
- Audit truth stored in **S3 (append‑only)**.
- Postgres holds audit index for lookup (not authoritative).
- Audit record references EB offsets, graph_version, snapshot_hash, bundle_ref, decision_id, outcome_id.

##### 4.1.G — Component compatibility matrix
**Goal:** ensure contract compatibility across RTDL components.

**DoD checklist:**
- Compatibility table exists mapping producer → consumer (IEG→OFP→DF/DL→AL→DLA).
- Each contract references the authoritative schema file path.

#### Phase 4.2 — IEG projector (EB → graph)
**Goal:** build deterministic IEG projection state from EB offsets and provide a stable `graph_version` for downstream RTDL components.

**Status:** **complete (Phase 4 integration-closed)**. IEG projector + integration-hardening checks under `4.2.K` are validated at current v0 scope.

**v0 parity operating note (non‑DoD):**
- IEG is **not auto‑started** in local_parity; it is run explicitly.
- Default parity run uses `--once` for bounded validation; `run_forever` is optional for live parity (with run‑scope locks).

##### 4.2.A — Inputs + replay basis
**Goal:** pin IEG’s inputs and replay basis so rebuilds are deterministic.

**DoD checklist:**
- IEG consumes EB admitted topics only (no Oracle reads).
- Replay basis is EB offsets (exclusive‑next) and is recorded per partition.
- Archive usage (if enabled) follows the RTDL pre‑design decision: archive is long‑term truth for replay, EB is live truth.
- Stream/topic set is explicit per environment profile.
- Run‑scope gating is supported: `platform_run_id` can be required and run scope may lock on first valid event (stream_id rebind).

##### 4.2.B — Envelope validation + event classification
**Goal:** ensure only valid events mutate the graph and failures are explicit.

**DoD checklist:**
- Canonical envelope validated for every event.
- Required pins enforced per class map (includes `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed`; legacy `run_id` accepted only as optional alias).
- Events are classified deterministically as `GRAPH_MUTATING`, `GRAPH_IRRELEVANT`, or `GRAPH_UNUSABLE`.
- `GRAPH_UNUSABLE` events do not mutate state and emit an explicit apply‑failure record.

##### 4.2.C — Idempotency + payload_hash anomaly
**Goal:** stable under duplicates and replay.

**DoD checklist:**
- Semantic idempotency tuple is `(platform_run_id, event_class, event_id)`; payload_hash mismatches are recorded as anomalies.
- `scenario_run_id` remains required for provenance/scope checks but is not part of semantic identity.
- Duplicate deliveries do not change graph state or watermark advancement.
- Payload_hash mismatch never mutates state and is surfaced as an anomaly.
- Payload_hash canonicalization is pinned to `{event_type, schema_version, payload}` canonical JSON.

##### 4.2.D — Watermarks + graph_version
**Goal:** deterministic progress tokens for downstream provenance.

**DoD checklist:**
- `graph_version` derived from per‑partition next_offset_to_apply map + stream identity.
- Watermark is monotonic and uses event_time (`ts_utc`) semantics; v0 uses max observed `ts_utc` with **no lateness window** (explicitly 0).
- Offsets advance only after durable state commit (DB transaction with WAL flush).
- Replay from the same offset basis yields identical `graph_version` and state.

##### 4.2.E — Storage layout + rebuildability
**Goal:** make IEG fully rebuildable from EB/archive.

**DoD checklist:**
- Projection schema separates projection state, applied offsets, and apply‑failure records (SQLite in parity; Postgres in dev/prod).
- All derived state is rebuildable from EB/archive; manual repair emits an audit anomaly.
- TTL/retention posture for IEG state is pinned (aligned with EB/archive retention).

##### 4.2.F — Query surface + provenance
**Goal:** downstream can trust the context used for decisions.

**DoD checklist:**
- Query responses return ContextPins + `graph_version`.
- No implicit “now”; all responses are deterministic for a given graph_version.
- Failure responses are explicit and do not fabricate context.

##### 4.2.G — Failure posture + degrade signals
**Goal:** make IEG health observable and actionable by DL/DF.

**DoD checklist:**
- IEG emits counters for lag, apply failures, and unusable events.
- Health thresholds are defined; RED/AMBER signals feed degrade posture decisions.
- IEG does not reclassify EB truth (IG remains admission authority).

##### 4.2.H — Performance + backpressure
**Goal:** handle sustained + burst throughput without correctness loss.

**DoD checklist:**
- Partition‑scoped consumers with bounded in‑memory queues.
- Batch apply is idempotent; backpressure does not drop events.
- Latency targets align with RTDL pre‑design SLO defaults.

##### 4.2.I — Observability + reconciliation
**Goal:** provide minimal but sufficient ops signals.

**DoD checklist:**
- Counters: events_seen, mutating_applied, duplicate, payload_mismatch, unusable, lag, watermark_age.
- Optional run‑scoped reconciliation artifact records applied offset basis and graph_version.

##### 4.2.J — Validation + tests
**Goal:** prove determinism and correctness.

**DoD checklist:**
- Unit tests: idempotency, payload_hash mismatch, watermark monotonicity.
- Replay test: same offsets → same graph_version and state.
- Integration test: EB sample events applied to projection with deterministic results.

##### 4.2.K — Integration + hardening (IEG‑adjacent)
**Goal:** close remaining IEG integration and ops hardening gaps before advancing RTDL.

**DoD checklist:**
- OFP/DF integration consumes IEG outputs (`graph_version`, `run_config_digest`, `eb_offset_basis`) with compatibility checks.
- IEG metrics/export path exists (OTel‑aligned counters + health signals) beyond DB‑only storage.
- Archive replay tooling exists to generate explicit replay manifests from EB/archive for deterministic rebuilds.
- Explicit migrations exist for IEG tables (replace runtime ALTERs for prod posture).

#### Phase 4.3 — OFP feature plane (graph → features)
**Goal:** materialize reproducible feature snapshots.
**Status:** **complete (Phase 4 integration-closed)**. 4.3.A through 4.3.H are validated at current v0 scope, including DF/DL compatibility paths.

##### 4.3.A — Inputs + basis pinning
**Goal:** ensure OFP only consumes deterministic, run-scoped inputs.

**DoD checklist:**
- OFP consumes **admitted EB traffic** as projector input; IEG is optional query support (no Oracle reads; no side-door inputs).
- Every feature computation is tied to a **pinned `eb_offset_basis`** and carries `graph_version` when IEG is consulted.
- `run_config_digest` is carried through OFP inputs and outputs (provenance).
- Input pins required: `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` (per RTDL pre‑design).

##### 4.3.B — Feature definitions + windows
**Goal:** versioned, reproducible feature definitions.

**DoD checklist:**
- Feature catalog is versioned and referenced in outputs.
- Windowed features have explicit TTLs (v0 default: 1h/24h/7d as configured).
- Feature windows aligned with RTDL pre‑design state‑store TTL rules.
- No implicit “latest” feature resolution; must reference graph_version + feature catalog version.

##### 4.3.C — Snapshot format + hashing
**Goal:** immutable, content‑addressable feature snapshots.

**DoD checklist:**
- Snapshot stored in object store (JSON v0; compression optional).
- Snapshot includes `snapshot_hash`, `graph_version`, `eb_offset_basis`, and feature catalog version.
- Snapshot hash rules (canonical JSON ordering/encoding) are documented and enforced.

##### 4.3.D — Storage layout + index
**Goal:** fast lookup without duplicating truth.

**DoD checklist:**
- Postgres holds snapshot **index/metadata** only; object store holds full snapshot.
- Index includes `snapshot_hash`, `graph_version`, `eb_offset_basis`, and `run_config_digest`.
- Snapshot retrieval uses index to resolve the exact object‑store path.

##### 4.3.E — Query surface + provenance
**Goal:** deterministic, read‑only feature access for DF/DL.

**DoD checklist:**
- Query responses return ContextPins + `graph_version` + `snapshot_hash` + `eb_offset_basis`.
- Responses are deterministic for a given snapshot_hash (no hidden recompute).
- Failure responses are explicit (no fabricated context).
- Component-scope evidence: `python -m pytest tests/services/online_feature_plane -q` -> `14 passed` (includes Phase 5 serve tests).

##### 4.3.F — Rebuild + replay posture
**Goal:** full rebuildability from EB/archive + IEG basis.

**DoD checklist:**
- OFP is rebuildable from EB/archive + IEG basis; no manual repair without audit anomaly.
- Replay from same basis yields identical snapshot_hash and contents.
- Projector checkpoints advance only after durable projection state commit; snapshot materialization is idempotent and does not mutate checkpoints.
- Component-scope evidence:
  - `python -m pytest tests/services/online_feature_plane/test_phase6_replay.py -q` -> `4 passed`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_ofs_parity_contract_v0.md`

##### 4.3.G — Observability + health
**Goal:** actionable ops signals for RTDL.

**DoD checklist:**
- Counters: snapshots_built, snapshot_failures, stale_graph_version, missing_features.
- Health thresholds defined; RED/AMBER status surfaced to DL/DF.
- Component-scope evidence:
  - `python -m pytest tests/services/online_feature_plane/test_phase7_observability.py -q` -> `2 passed`
  - export CLI: `python -m fraud_detection.online_feature_plane.observe --profile <profile> --scenario-run-id <id>`
  - OFP observability exporter writes:
    - `runs/fraud-platform/<platform_run_id>/online_feature_plane/metrics/last_metrics.json`
    - `runs/fraud-platform/<platform_run_id>/online_feature_plane/health/last_health.json`

##### 4.3.H — Validation + tests
**Goal:** prove determinism and parity.

**DoD checklist:**
- Unit tests for snapshot hash determinism and window TTL behavior.
- Replay test: same basis → same snapshot_hash.
- local_parity OFP runbook exists for current boundary operation.
- Integration test: IEG graph_version → OFP snapshot with correct provenance.
- DF-contract compatibility integration test is closed at current v0 scope (evidence in implementation maps/logbook).
- DL consume-path integration test for OFP health/degrade signals is closed at current v0 scope (evidence in implementation maps/logbook).

#### Phase 4.3.5 — Shared RTDL join plane (Context Store + FlowBinding)
**Goal:** pin the runtime join substrate that DF/DL consume at decision time without duplicating IEG or OFP truth ownership.
**Status:** complete through `4.3.5.G` with parity and replay evidence.
**Component build map:** `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md`
**Closure snapshot (2026-02-07):**
- Closed now: `4.3.5.A` through `4.3.5.F` (ownership, invariants, ingest/idempotency, commit/checkpoint order, query surface, observability hooks).
- Closed now: `4.3.5.G` (unit coverage + local-parity monitored evidence and closure assertions complete at current v0 scope).

##### 4.3.5.A — Join-plane boundary + ownership
**Goal:** lock responsibilities for runtime join state.

**DoD checklist:**
- Context Store owns run-scoped JoinFrames consumed online by DF/DL.
- FlowBinding Index owns `flow_id -> JoinFrameKey` resolution, with flow-anchor events as the only authoritative writer.
- IEG remains projection authority; OFP remains feature snapshot authority; join plane remains runtime join-readiness authority.

##### 4.3.5.B — Keys, schema, and pin invariants
**Goal:** prevent cross-run/cross-flow mixing.

**DoD checklist:**
- JoinFrameKey is explicit and pinned (`platform_run_id`, `scenario_run_id`, `merchant_id`, `arrival_seq`).
- FlowBinding records include evidence refs to anchor event offsets and required ContextPins.
- Unknown or incompatible schema/pin combinations fail closed and are logged as anomalies.

##### 4.3.5.C — Ingest/apply semantics + idempotency
**Goal:** keep join state deterministic under at-least-once and replay.

**DoD checklist:**
- Apply path is sourced from admitted EB context topics only (no Oracle side reads).
- Idempotency tuple is pinned and payload-hash mismatch for same tuple is anomaly/fail-closed.
- Duplicate deliveries do not mutate committed join state.

##### 4.3.5.D — Commit points + checkpoints
**Goal:** prevent offset/state divergence.

**DoD checklist:**
- Join state commit and offset checkpoint advance are transactionally ordered (commit before checkpoint).
- Recovery from crash/restart replays safely without creating divergent JoinFrames.
- Replay from same offset basis reproduces identical JoinFrame and FlowBinding state.

##### 4.3.5.E — Query/read contract for DF/DL
**Goal:** give DF/DL an explicit runtime API for join readiness.

**DoD checklist:**
- Read contract supports lookup by source traffic event context (`flow_id` and/or JoinFrameKey surfaces).
- Responses include join completeness status + evidence refs used for resolution.
- Missing binding/context returns explicit machine-readable reasons; no fabricated joins.

##### 4.3.5.F — Degrade and observability hooks
**Goal:** make join deficits actionable by DL/DF and Obs/Gov.

**DoD checklist:**
- Join-miss and binding-conflict reasons are emitted in structured counters/logs.
- Health posture exposes lag, conflict count, and stale-watermark indicators for DL posture inputs.
- Reconciliation artifact is available per run with applied offset basis and unresolved conflict summaries.

##### 4.3.5.G — Validation and closure gate
**Goal:** prove shared join-plane readiness before declaring RTDL integration closure.

**DoD checklist:**
- Unit tests cover binding authority, conflict handling, idempotent replay, and fail-closed unknowns.
- Integration test proves EB context intake -> JoinFrame availability -> DF read contract continuity.
- Local-parity monitored run evidence includes join-plane counters and failure-mode assertions.

#### Phase 4.4 — DF/DL decision core (features → decision)
**Goal:** compute decisions with explicit degrade posture.
**Status:** complete at DF/DL decision+intent boundary; downstream execution/audit dependencies have been closed by Phase 4.5.

##### 4.4.A — Decision trigger boundary + run scope
**Goal:** ensure DF only decides on admissible, run-scoped traffic stimuli.

**DoD checklist:**
- DF consumes **admitted EB traffic** only as decision triggers; context/control topics are not trigger sources.
- Decision-trigger event allowlist is explicit and versioned; DF never re-triggers on its own decision/intent events.
- Required pins are enforced at decision ingress (`platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` when required).
- Every decision candidate records immutable source evidence basis (`source_event_id`, `source_event eb_ref/origin_offset`).

##### 4.4.B — DL posture contract + fail-safe semantics
**Goal:** make degrade posture explicit, deterministic, and enforceable.

**DoD checklist:**
- DL outputs explicit `DegradeDecision` with `mode`, `capabilities_mask`, `policy_rev`, and provenance reasons.
- Mode ladder is pinned and tested (`NORMAL -> DEGRADED_1 -> DEGRADED_2 -> FAIL_CLOSED`).
- DF treats `capabilities_mask` as hard constraints (no silent bypass of forbidden capability).
- Transition semantics are pinned: immediate downshift; controlled one-rung upshift after quiet period.
- Missing/invalid DL posture forces explicit fail-closed decision posture with reason codes.
- Optional posture-change control events are visibility-only and never correctness-critical.

##### 4.4.C — Deterministic bundle resolution + compatibility
**Goal:** remove ambiguity in model/policy bundle selection.

**DoD checklist:**
- Registry resolution is deterministic for `(environment, mode, bundle_slot, tenant?)`; no implicit "latest" lookup.
- Compatibility checks are fail-closed for schema/version/capability mismatch.
- DF records `bundle_ref` + resolver provenance on every decision, including fallback reason when applicable.
- Resolver behavior is stable under replay and restarts for the same input basis + policy revision.

##### 4.4.D — Context/feature join readiness + bounded budgets
**Goal:** bound decision latency while preserving correctness.

**DoD checklist:**
- Join readiness rules are explicit for required vs optional context surfaces (OFP/IEG/context frame).
- Decision deadlines and join wait budgets are policy-pinned (`decision_deadline_ms`, `join_wait_budget_ms`) and enforced.
- OFP reads are `as_of_time_utc = source event ts_utc`; no hidden wall-clock joins.
- Missing required context yields explicit degrade posture; no fabricated context.
- Late context updates do not silently re-score v0 decisions.

##### 4.4.E — Decision artifact contract + provenance minimum
**Goal:** emit replay-defensible decision artifacts.

**DoD checklist:**
- Decision payload includes `decision_id`, outcome/action posture, reasons, `degrade_mode`, `capabilities_mask`, and schema version.
- Provenance minimum is mandatory: `bundle_ref`, `snapshot_hash` (when OFP used), `graph_version` (when IEG used), `eb_offset_basis`, `policy_rev`, `run_config_digest`.
- Source and supporting evidence refs are explicit (traffic origin offset always; context offsets when used).
- Decision artifacts are immutable once emitted; corrections are append-only superseding facts.

##### 4.4.F — Action intent contract (DF output boundary)
**Goal:** hand off executable intents safely without leaking into AL semantics.

**DoD checklist:**
- DF emits `ActionIntent` with deterministic `idempotency_key` and explicit origin/actor metadata.
- Intent set respects DL `action_posture` constraints (for example, `STEP_UP_ONLY` posture restrictions).
- Intents are emitted as canonical envelope traffic and published through IG (no side-channel bypass).
- Intent identity and payload are deterministic for a fixed decision basis.

##### 4.4.G — Idempotency + replay determinism
**Goal:** make DF/DL safe under at-least-once delivery and replay.

**DoD checklist:**
- Re-delivered source events do not produce divergent decisions for the same semantic basis.
- Determinism rule holds: same source event + same DL posture + same bundle + same OFP/IEG basis -> same `decision_id` and intents.
- Payload hash mismatch for the same semantic decision identity is surfaced as anomaly (never silently replaced).
- Consumer checkpoints advance only after durable decision emission boundary succeeds (publish + local decision persistence).

##### 4.4.H — State stores + commit points
**Goal:** pin operationally safe state ownership for DF/DL.

**DoD checklist:**
- DL posture store and DF decision index/checkpoint stores are explicit and environment-parity aligned (Postgres in local-parity/dev/prod).
- Commit points are transactionally defined (DB commit + WAL flush before offset advance).
- State can be rebuilt from authoritative evidence boundaries (EB/archive + decision artifacts) without manual truth edits.
- Manual repair requires explicit anomaly/governance fact; no silent DB patching.

##### 4.4.I — Security + governance stamps
**Goal:** keep decision core compliant and attributable.

**DoD checklist:**
- All decision/intent artifacts carry actor/source attribution and policy revision stamps.
- Secrets are runtime-only; no secret material in decision payloads, artifacts, impl maps, or logbooks.
- Governance-relevant transitions (policy change, forced fail-closed posture, resolver fallback) emit structured facts/refs.
- Unknown compatibility or missing provenance fails closed.

##### 4.4.J — Observability + corridor checks
**Goal:** provide actionable run-scoped operating signals for DF/DL.

**DoD checklist:**
- Metrics include latency SLOs (p50/p95/p99), degrade-mode counts, missing-context counts, resolver failures, fail-closed events.
- Health posture includes explicit GREEN/AMBER/RED semantics with threshold policy refs.
- Run-scoped reconciliation artifact summarizes decisions by mode/bundle/posture with evidence refs.
- Observability signals are sufficient for Obs/Gov to drive degrade/corridor policy without reading payload truth.

##### 4.4.K — Validation matrix + parity proof
**Goal:** prove DF/DL correctness and replay safety before advancing.

**DoD checklist:**
- Unit tests cover DL mode transitions, mask enforcement, deterministic resolver outcomes, and fail-closed fallbacks.
- Integration tests cover OFP + IEG + DF + IG publish path with provenance field assertions.
- Replay tests prove same basis -> same decision ids/intents and stable posture behavior.
- Local-parity proofs executed with monitored runs (20-event sanity + 200-event pass) and recorded evidence paths.

##### 4.4.L — Closure gate + 4.5 handoff boundary
**Goal:** make completion criteria explicit without collapsing phase boundaries.

**DoD checklist:**
- Phase 4.4 is green when DF/DL decisioning is deterministic, fail-safe, and provenance-complete at the decision+intent boundary.
- Remaining integration gates that require AL execution truth and DLA append-only audit closure stay explicitly tracked under Phase 4.5.
- 4.4 completion entry includes unresolved integration risks and exact dependency list for 4.5.

**4.4 completion entry (2026-02-07):**
- Closure basis:
  - DF component phases 1-8 complete with run-scoped observability/reconciliation and replay/checkpoint safety.
  - DL component phases 1-8 complete for posture authority + serving semantics.
  - DF replay/checkpoint stores are backend-aware for `sqlite` and `postgres` locators, closing 4.4.H store parity expectations for local-parity/dev/prod.
- Validation evidence:
  - `python -m pytest tests/services/decision_fabric -q` -> `65 passed`
  - `python -m pytest tests/services/degrade_ladder -q` -> `40 passed`
- Unresolved integration risks (explicitly deferred to 4.5):
  - Action Layer side-effect execution truth and idempotent external effect semantics.
  - Decision Log/Audit append-only closure for decision -> intent -> outcome chain.
  - End-to-end RTDL run proofs that include AL execution and DLA audit artifacts.
- 4.5 dependency list:
  - `action_layer` component implementation/validation map.
  - `decision_log_audit` component implementation/validation map.
  - Integrated DF + AL + DLA local-parity runbook/evidence pass (20 and 200 event monitored runs).

#### Phase 4.5 — AL + DLA (decision → outcome → audit)
**Goal:** apply effects safely and record audit truth.
**Status:** complete at v0 platform boundary.
**Component maps:**
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md`
- `docs/model_spec/platform/implementation_maps/decision_log_audit.build_plan.md`

##### 4.5.A — Decision→Action intake boundary + pin integrity
**Goal:** guarantee AL and DLA process only admissible, run-scoped decision artifacts.

**DoD checklist:**
- AL intake accepts only admitted decision/intent families with required ContextPins (`platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, plus `seed` where required).
- Intake rejects/flags malformed or scope-mismatched intents with explicit machine-readable failure reasons (no silent drop).
- DLA intake validates decision and outcome schema compatibility before append.
- Decision->intent->outcome chain carries immutable source evidence refs (`source_event_id`, traffic `origin_offset`, decision refs).

##### 4.5.B — AL idempotency and side-effect safety
**Goal:** enforce at-least-once safe execution.

**DoD checklist:**
- Action execution semantic key is deterministic and stable under replay.
- Duplicate deliveries do not create duplicate side effects.
- Payload-hash mismatch on an existing semantic key is anomaly/quarantine (never overwrite).
- Retry policy is explicit (bounded attempts, backoff policy, terminal failure semantics).

##### 4.5.C — Outcome contract and publication discipline
**Goal:** make execution results immutable, queryable, and replay-safe.

**DoD checklist:**
- Outcomes are append-only with stable `outcome_id` identity.
- AL writes explicit terminal states (`SUCCEEDED`, `FAILED`, `UNKNOWN/UNCERTAIN_COMMIT` where applicable) with reason codes.
- Outcome publication to IG/EB is idempotent and does not mutate prior outcomes.
- If outcome publish is ambiguous, AL records deterministic retry/reconciliation posture with evidence pointers.

##### 4.5.D — DLA append-only truth and evidence boundary
**Goal:** make audit closure deterministic and reconstructable.

**DoD checklist:**
- DLA stores append-only audit records tying `decision_id -> action_intent_id -> outcome_id`.
- Audit evidence includes traffic `origin_offset` and explicit context offsets used by the decision path.
- By-ref evidence model is enforced; payload copies are only stored when policy explicitly requires.
- DLA index supports lookup by run scope, decision id, action intent id, and outcome id.

##### 4.5.E — Commit-point ordering and checkpoint semantics
**Goal:** prevent offset advancement without durable audit truth.

**DoD checklist:**
- DLA durable append success is the v0 commit gate for advancing relevant traffic offsets.
- Checkpoint advancement order is explicit and tested (durable write before checkpoint move).
- Failure in DLA append blocks checkpoint progression and forces retry/fail-safe lane.
- AL outcome lag is permitted only within pinned decoupling semantics and must not violate audit closure guarantees.

##### 4.5.F — Failure lanes, quarantine, and replay determinism
**Goal:** keep failures explicit and replay-safe.

**DoD checklist:**
- Poison/invalid events are quarantined with deterministic reason taxonomy.
- Replays from identical basis reproduce identical decision->outcome->audit chains.
- Anomaly classes (id collision/payload mismatch/schema incompatibility) are surfaced with durable evidence refs.
- Recovery drills cover DLA outage, AL publish ambiguity, and duplicate storm behavior.

##### 4.5.G — Security, governance, and retention posture
**Goal:** ensure production-safe handling of sensitive execution/audit artifacts.

**DoD checklist:**
- Access controls for AL/DLA reads are least-privilege and auditable.
- Retention/immutability posture for audit artifacts is pinned per environment ladder.
- Governance stamps (`policy_rev`, `bundle_ref`, execution profile refs) are recorded on decisions/outcomes/audit records.
- Sensitive tokens/credentials are excluded from logs, receipts, impl maps, and run artifacts.

##### 4.5.H — Observability and reconciliation surfaces
**Goal:** make AL/DLA operationally diagnosable without becoming a control plane.

**DoD checklist:**
- Counters include decision consumed, intents executed, outcomes emitted, audit appends, quarantines, and ambiguous outcomes.
- Health surfaces expose GREEN/AMBER/RED with explicit reasons and lag signals.
- Reconciliation artifacts can prove per-run closure of decision->outcome->audit lineage.
- Alert posture treats audit-chain breakage and outcome quarantine as high-severity signals.

##### 4.5.I — Validation matrix and parity proof
**Goal:** prove 4.5 behavior under realistic load and replay conditions.

**DoD checklist:**
- Unit tests cover AL idempotency, retry/finalization semantics, DLA append invariants, and checkpoint ordering.
- Integration tests prove DF->AL->DLA chain continuity with provenance refs intact.
- Local-parity monitored runs exist for 20 and 200 events with evidence paths and run ids recorded.
- Replay test proves deterministic re-run behavior with no duplicate external effects and stable audit identity chain.

##### 4.5.J — Closure gate and Phase 5 handoff boundary
**Goal:** make Phase 4.5 completion objective and unblock Label/Case safely.

**DoD checklist:**
- 4.5 is green only when decision->action->outcome->audit closure is deterministic, append-only, and provenance-complete.
- Residual risks and deferred items (if any) are explicitly documented with owner and phase target.
- Platform parity runbook includes AL/DLA operation and evidence collection steps.
- Phase 5 start gate is explicitly met: Label/Case can consume AL outcomes + DLA refs without compatibility gaps.

**4.5 completion entry (2026-02-07):**
- Closure basis:
  - AL component phases 1-8 complete with idempotent execution, IG publish discipline, replay/checkpoint safety, and parity proof artifacts.
  - DLA component phases 1-8 complete with append-only lineage assembly, deterministic query/index behavior, replay safety, and parity proof artifacts.
  - Cross-component RTDL regression sweep passed at current v0 scope using:
    - `python -m pytest --import-mode=importlib tests/services/identity_entity_graph tests/services/online_feature_plane tests/services/context_store_flow_binding tests/services/degrade_ladder tests/services/decision_fabric tests/services/action_layer tests/services/decision_log_audit tests/services/ingestion_gate/test_phase10_df_output_onboarding.py -q`
    - Result: `275 passed`.
- Representative run-scoped parity artifacts:
  - `runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_20.json`
  - `runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_200.json`
  - `runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_20.json`
  - `runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_200.json`

---

#### Pre‑design gating questions (RTDL)
Resolved and pinned in:
`docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`

---
### Phase 4.6 — Meta-layer closure gate (Run/Operate + Obs/Gov)
**Intent:** close platform-meta obligations before moving to Label/Case so downstream planes run under live, governed operating semantics.
**Blocking rule:** Phase 5 is blocked until Phase 4.6 DoD is fully satisfied.

##### 4.6.A — Governance lifecycle fact stream (platform-wide)
**Goal:** make lifecycle-changing actions uniformly auditable as append-only governance facts.

**DoD checklist:**
- Required v0 governance event families are emitted and queryable (**MUST EMIT in Phase 4.6**):
  - run lifecycle (`RUN_READY_SEEN`, `RUN_STARTED`, `RUN_ENDED`, `RUN_CANCELLED`),
  - policy/config (`POLICY_REV_CHANGED`),
  - corridor/anomaly lifecycle for fail-closed boundaries (for example schema/policy missing, publish ambiguous, ref access denied, incompatible resolution),
  - evidence access (`EVIDENCE_REF_RESOLVED`).
- Reserved governance families are pinned now as schema/plumbing contracts and become **MUST EMIT** only when owning planes are active:
  - label lifecycle (`LABEL_SUBMITTED`, `LABEL_ACCEPTED`, `LABEL_REJECTED`) [Phase 5+],
  - registry lifecycle (publish/approve/promote/rollback/retire) [Phase 6+ activation path].
- Governance events are idempotent, append-only, and include actor attribution + scope/pins.
- Missing mandatory governance fields fail closed at writer boundaries.

##### 4.6.B — Evidence-ref resolution corridor + access audit
**Goal:** enforce “refs visible != refs resolvable” with auditable resolution decisions.

**DoD checklist:**
- Evidence-ref resolution is RBAC/allowlist gated (not open direct read by default in dev/prod).
- Every ref resolution emits minimal audit record (`actor_id`, `source_type`, `ref_type`, `ref_id`, `purpose`, `platform_run_id?`, `observed_time`).
- Resolution failures (`REF_ACCESS_DENIED`, expired/invalid ref) emit structured anomaly/governance events.
- No payload contents are logged in access audit records.

##### 4.6.C — Service identity and auth posture by environment
**Goal:** remove auth ambiguity between local parity and higher environments.

**DoD checklist:**
- `local_parity`: API-key/allowlist mode pinned and tested at all writer corridors.
- `dev/prod`: one uniform service identity mechanism across platform writers (mTLS or signed service tokens), enforced at corridor boundaries.
- `actor_id` and `source_type` are derived from auth context (not payload) and stamped consistently in governance/audit surfaces.

##### 4.6.D — Platform run reporter (cross-plane reconciliation artifact)
**Goal:** provide one cheap, run-scoped platform reconciliation truth rather than only component-local snapshots.

**DoD checklist:**
- A platform run reporter writes run-scoped reconciliation artifact under the obs prefix.
- Artifact includes minimum cross-plane counters and references:
  - ingress (`sent/received/admit/duplicate/quarantine/publish_ambiguous/receipt_write_failed`),
  - RTDL (`inlet_seen/deduped/degraded/decision/outcome/audit append`),
  - join to evidence refs (receipt/audit refs), not payload duplication.
- Reporter is periodic or on-demand and does not sit on hot path.

##### 4.6.E — Deployment provenance stamp uniformity
**Goal:** make runtime behavior attributable to immutable deploy artifacts.

**DoD checklist:**
- `service_release_id` (digest/tag/SHA) is present on required runtime/governance records across SR/IG/RTDL surfaces.
- Provenance records include `environment` and run/config revision context where applicable.
- Release stamp propagation is validated in parity and in at least one non-local profile config path.

##### 4.6.F — Run/operate durability for downstream services
**Goal:** ensure decision-lane services are operated as durable units, not only test matrices.

**DoD checklist:**
- Operational runbook/targets exist for always-on posture of live-capable downstream services.
- Supervision/restart posture is pinned (crash recovery, checkpoint safety, replay-safe restart behavior).
- Where a component is still matrix-validated in v0 (not daemonized), that boundary is explicit with a migration gate to durable service mode.

##### 4.6.G — Corridor checks + anomaly policy closure
**Goal:** make fail-closed behavior observable and enforceable at platform choke points.

**DoD checklist:**
- Corridor checks are pinned and tested for IG, DLA append boundary, AL publish boundary, evidence-ref resolution, and registry promotion boundary.
- Structured anomaly taxonomy is wired for minimum required categories (schema/policy missing, publish ambiguous, replay basis mismatch, ref access denied, incompatibility).
- Training/governance fail-closed posture is explicit and verified for anomaly families that must not degrade silently.

##### 4.6.H — Environment parity conformance gate
**Goal:** prevent local-only behavior drift in meta layers.

**DoD checklist:**
- Conformance checklist validates same semantics across `local_parity`, `dev`, `prod` profiles for:
  - envelope/pins,
  - governance event schema,
  - policy/config revision stamping,
  - corridor enforcement behavior.
- Differences are limited to operational envelope (auth strictness, capacity, retention, sampling), not semantics.

##### 4.6.I — Closure evidence and handoff gate
**Goal:** make meta-layer completion objective before starting Phase 5.

**DoD checklist:**
- Monitored parity run demonstrates:
  - full governance fact emission path for a run lifecycle,
  - evidence-ref resolution audit path,
  - platform-level reconciliation artifact generation.
- Validation suite and runbook evidence are attached in implementation maps/logbook.
- Explicit handoff note marks Phase 5 unblocked only after 4.6 PASS.

##### 4.6.J — Platform orchestration contract (meta-layer, plane-agnostic)
**Goal:** ensure orchestration is implemented once as platform Run/Operate substrate and reused by all planes.

**DoD checklist:**
- A single orchestration contract is pinned for all planes: lifecycle (`up/down/restart/status`), readiness/liveness checks, run-scope controls, restart/replay-safe behavior, and log/evidence surfacing.
- `local_parity`, `dev`, and `prod` use the same orchestration semantics and env var keys; only wiring/auth/scale posture differs by profile.
- Current plane packs are onboarded through this same contract (Control/Ingress + RTDL live-capable workers) without bespoke orchestrator logic.
- Future planes (Label/Case, Learning/Registry, Obs/Gov workers) are onboarded by declarative process-pack entries and config only, not orchestrator code rewrites.
- Orchestrator layer contains no RTDL-specific business assumptions (no hardcoded stream families, no DF/OFP-specific policy logic).

##### 4.6.K — Objective meta-layer quality gate
**Goal:** make 4.6 PASS measurable and audit-ready, not narrative-only.

**DoD checklist:**
- A written 4.6 validation matrix exists with explicit PASS/FAIL criteria per subsection `4.6.A`..`4.6.J`.
  - current artifact path: `docs/model_spec/platform/implementation_maps/platform.phase4_6_validation_matrix.md`
- At least one monitored parity run executes under orchestrated mode and produces evidence for:
  - run lifecycle governance facts,
  - corridor anomaly emission on injected negative checks,
  - platform reconciliation artifact generation,
  - restart/recovery behavior for at least one always-on worker pack.
- Evidence pack paths are pinned in implementation maps/logbook with run IDs, timestamps, and command traces (no payload secret leakage).
- Phase 5 **formal closure gate** remains blocked unless all mandatory 4.6 gates are PASS (reserved families excluded until owning plane activation); implementation sequencing may run in parallel when residual 4.6 gaps are explicitly tracked.

##### 4.6.L — Remaining-open closure TODOs from full parity run `platform_20260209T144746Z`
**Goal:** close strict-green residuals with explicit criteria/evidence and synchronize platform status truth.

**Closure checklist (2026-02-09):**
- `TODO-4.6L-01` OFP watermark-age policy closure: **CLOSED**
  - local-parity rule is now explicit in runbook (`platform_parity_walkthrough_v0.md` section `14.1`):
    - `WATERMARK_TOO_OLD` is gate-failing during active ingress progression,
    - post-idle bounded-run watermark drift is informational in local parity and must be recorded.
  - matrix criteria updated in `platform.phase4_6_validation_matrix.md`.
- `TODO-4.6L-02` IEG/DL run-scoped observability completeness: **CLOSED**
  - DL worker now emits run-scoped artifacts each tick:
    - `runs/fraud-platform/<platform_run_id>/degrade_ladder/metrics/last_metrics.json`
    - `runs/fraud-platform/<platform_run_id>/degrade_ladder/health/last_health.json`
  - validation:
    - `python -m pytest -q tests/services/degrade_ladder/test_phase7_worker_observability.py` -> `2 passed`
    - `python -m pytest -q tests/services/degrade_ladder` -> `43 passed`
  - runtime smoke on active run `platform_20260209T144746Z` confirms both files present.
- `TODO-4.6L-03` DF fail-closed posture closure: **CLOSED (bounded local-parity acceptance)**
  - deterministic posture evidence retained on active run:
    - `runs/fraud-platform/platform_20260209T144746Z/decision_fabric/metrics/last_metrics.json` (`degrade_total=200`, `fail_closed_total=200`, `resolver_failures_total=200`)
    - `runs/fraud-platform/platform_20260209T144746Z/decision_fabric/reconciliation/reconciliation.json` (deterministic reason families).
  - acceptance bound is local parity only; env-ladder remediation for dev/prod is mandatory (compatible ACTIVE bundle and feature-group contract closure required).
- `TODO-4.6L-04` Matrix/status truth sync: **CLOSED**
  - matrix and status block are now synchronized with closed `4.6.L` posture and evidence links.

---

### Phase 5 — Label & Case plane
**Intent:** crystallize outcomes into authoritative label timelines and case workflows.
**Execution posture:** Phase 4.6 residuals are closed; Phase 5 proceeds under normal closure gates.

**Definition of Done (DoD):**
- Label Store supports append-only timelines with as-of queries (effective vs observed time).
- Case management backend can open/advance/close cases and emit label assertions.
- Engine 6B truth/bank-view/case surfaces can be ingested via IG into Label Store.
- E2E: action outcome + case event -> label timeline update visible to learning plane.

#### Phase 5.1 — Contracts + identity pins (CaseTrigger, timeline, LabelAssertion)
**Goal:** pin non-ambiguous contracts and identity rules before service implementation.

**DoD checklist:**
- `CaseSubjectKey` is pinned to `(platform_run_id, event_class, event_id)` with deterministic `case_id = hash(CaseSubjectKey)`.
- `CaseTrigger` contract is pinned (trigger type vocabulary + required ContextPins + by-ref evidence refs + deterministic `case_trigger_id`).
- Case timeline event contract is pinned with controlled `timeline_event_type` vocabulary and idempotency key `(case_id, timeline_event_type, source_ref_id)`.
- Label assertion contract is pinned with `LabelSubjectKey=(platform_run_id,event_id)`, `label_type`, `label_value`, `effective_time`, `observed_time`, provenance, and evidence refs.
- Payload-hash canonicalization rule is pinned for CM and LS writer boundaries (sorted refs, stable field set).

#### Phase 5.2 — CaseTrigger service + CM intake boundary
**Goal:** make trigger production deterministic, auditable, and explicit before CM case creation logic.

**DoD checklist:**
- CaseTrigger is operated as an explicit service boundary (standalone writer/emitter path), not hidden CM side logic.
- Source eligibility is pinned (DF/DLA/AL/external/manual signals) with explicit trigger-type mapping.
- Trigger identity and dedupe are deterministic (`case_id`, `case_trigger_id`, canonical payload hash) and collision-fail-closed.
- Publish path is pinned through approved corridor (`IG`/`EB` control or dedicated trigger stream by profile), with run-scoped auth attribution.
- CM intake consumes this explicit trigger contract and remains deterministic under at-least-once delivery.

##### 5.2.A — Source eligibility + trigger mapping
**Goal:** prevent ambiguous trigger generation semantics.

**DoD checklist:**
- Allowed CaseTrigger source classes are explicitly versioned (`DECISION_ESCALATION`, `ACTION_FAILURE`, `ANOMALY`, `EXTERNAL_SIGNAL`, `MANUAL_ASSERTION`).
- Each source class has a pinned trigger mapping rule with evidence-ref requirements (`decision_id`, `action_outcome_id`, `audit_record_id`, etc.).
- Unsupported source events fail closed (no implicit coercion into trigger types).

##### 5.2.B — Evidence-by-ref enrichment boundary
**Goal:** ensure trigger payloads are minimal, joinable, and non-duplicative.

**DoD checklist:**
- CaseTrigger payload carries refs + minimal metadata only; no raw payload mirroring from upstream truth stores.
- Required ContextPins and `CaseSubjectKey` are enforced.
- Evidence refs are normalized to controlled ref vocab and canonical ordering.

##### 5.2.C — Deterministic identity + collision discipline
**Goal:** make trigger stream safe under retries/replays.

**DoD checklist:**
- `case_id = hash(CaseSubjectKey)` and `case_trigger_id = hash(case_id + trigger_type + source_ref_id)` are enforced.
- Canonical payload hash is persisted for collision detection.
- Same deterministic dedupe key + hash mismatch emits structured anomaly and blocks silent overwrite.

##### 5.2.D — Publish corridor + environment auth posture
**Goal:** keep trigger writes policy-safe across env ladder.

**DoD checklist:**
- Writer boundary enforces authn/authz posture by environment (`local_parity` API-key allowlist; stronger dev/prod identity mechanism).
- Trigger writes are actor-attributed from auth context (`SYSTEM::<service>` or `HUMAN::<id>`).
- Publish outcomes are explicit and reconciliation-friendly (`ADMIT`/`DUPLICATE`/`QUARANTINE`/ambiguous).

##### 5.2.E — Retry/checkpoint/replay safety
**Goal:** keep trigger emission deterministic under at-least-once transport.

**DoD checklist:**
- Retry policy preserves stable identity (no regenerated IDs on retries).
- Checkpoint progression occurs only after durable publish outcome is known.
- Replay of the same source evidence yields the same trigger identity and no duplicate case creation downstream.

##### 5.2.F — Observability + governance surfaces
**Goal:** make trigger service operable and auditable at low overhead.

**DoD checklist:**
- Run-scoped counters are emitted (`triggers_seen`, `triggers_published`, `duplicates`, `quarantine`, `publish_ambiguous`).
- Trigger anomalies emit structured governance/anomaly events with evidence refs.
- Reconciliation artifact references trigger counts and IDs without payload leakage.

##### 5.2.G — CM intake integration gate
**Goal:** prove CaseTrigger service and CM boundary align correctly.

**DoD checklist:**
- CM consumes explicit CaseTrigger contract and validates pins/IDs/hash discipline.
- Case creation remains idempotent on `CaseSubjectKey`; duplicate triggers append/no-op as expected.
- v0 no-merge posture remains enforced for case identity.

##### 5.2.H — CaseTrigger parity closure evidence
**Goal:** close CaseTrigger service readiness with monitored parity + fail-closed proofs.

**DoD checklist:**
- CaseTrigger Phase 8 matrix produces run-scoped parity proof artifacts for `20` and `200` event monitored runs.
- Negative-path injections prove fail-closed unsupported-source and collision-mismatch behavior with governance evidence.
- Closure evidence is recorded in implementation maps/logbook and linked in parity runbook.

#### Phase 5.3 — Case timeline truth + workflow projection (CM S2/S3)
**Goal:** establish CM as append-only investigation truth with deterministic projections.

**DoD checklist:**
- Case timeline is append-only and actor-attributed (`actor_id`, `source_type`, `observed_time`) for all meaningful state transitions.
- Header/status views are derived from timeline events only; no hidden mutable state bypass.
- Concurrent edits are represented as append-only events with deterministic projection ordering.
- Required query surfaces exist for `case_id`, linked references (`event_id`, `decision_id`, `action_outcome_id`, `audit_record_id`), queue/state, and time-window filters.

#### Phase 5.4 — CM manual-action lane via AL (CM S6)
**Goal:** preserve action truth ownership boundaries while enabling human intervention.

**DoD checklist:**
- CM never executes side effects directly; manual interventions are emitted as ActionIntents to AL with deterministic idempotency keys.
- CM records action request + outcome attachment on timeline by reference (`action_outcome_id`) only.
- Failure modes are explicit (`ACTION_PENDING`, retry, denied/failed attached) without claiming execution truth before AL outcome.

#### Phase 5.5 — CM->LS label emission handshake (J13)
**Goal:** close the human truth loop without ambiguity about commit points.

**DoD checklist:**
- CM emits LabelAssertions to LS writer boundary and records `LABEL_PENDING` until durable LS ack.
- LS ack/reject drives timeline transitions (`LABEL_ACCEPTED`, `LABEL_REJECTED`, optional `LABEL_RETRYING`); CM never claims label truth before ack.
- Idempotent retries are stable (same assertion id and observed_time across retries).
- Same assertion key + mismatched payload hash is surfaced as anomaly and rejected fail-closed.

#### Phase 5.6 — Label Store append-only truth + as-of query surfaces
**Goal:** make LS authoritative for label truth and leakage-safe for learning.

**DoD checklist:**
- LS write boundary enforces append-only assertions with idempotent dedupe and provenance stamping.
- Effective vs observed time semantics are enforced and queryable.
- LS exposes deterministic read surfaces: timeline-by-subject and `label_as_of(subject, T)` with explicit observed-time eligibility rule.
- Resolved view conflict posture is pinned (deterministic precedence or explicit conflict state; no silent ambiguity).

#### Phase 5.7 — Engine truth/bank-view/case ingest into LS (v0 synthetic truth lane)
**Goal:** ingest 6B truth products through platform rails while preserving LS truth ownership.

**DoD checklist:**
- Adapter path ingests engine 6B truth/bank-view/case surfaces via IG/EB (or explicitly pinned equivalent ingress) with PASS gate verification.
- Ingested truth is translated into LS LabelAssertions with explicit source provenance and dual-time semantics.
- No direct bypass writes to LS without writer-boundary validation/idempotency.
- Replay/re-run behavior is deterministic and scoped by ContextPins (no cross-run leakage).

#### Phase 5.8 — Observability/governance for Case+Labels plane
**Goal:** make the plane operable and auditable under v0 meta-layer posture.

**DoD checklist:**
- Required counters are emitted/run-scoped: `case_triggers`, `cases_created`, `timeline_events_appended`, `label_assertions`, `labels_accepted`, `labels_rejected`, `label_pending`.
- Governance lifecycle events for labels are emitted with actor attribution and evidence refs (`LABEL_SUBMITTED`, `LABEL_ACCEPTED`, `LABEL_REJECTED`).
- Corridor anomalies for CM/LS boundaries are structured and fail-closed where required.
- Reconciliation artifact exists at `s3://fraud-platform/{platform_run_id}/case_labels/reconciliation/YYYY-MM-DD.json` (or environment-equivalent prefix).

#### Phase 5.9 — Integration closure gate (CM + LS + RTDL handoff)
**Goal:** prove end-to-end Case+Labels continuity and unblock Phase 6 safely.

**DoD checklist:**
- Integration proof covers `DLA/AL evidence -> CaseTrigger -> CM timeline -> LabelAssertion -> LS timeline -> as-of read`.
- Negative-path proof exists: LS unavailable, hash mismatch, invalid subject mapping, and retry idempotency.
- Monitored parity evidence includes run-scoped artifacts/logs for CM + LS and reconciliation outputs.
- Phase 6 start is unblocked only when this section is PASS with implementation-map + logbook evidence.

**Implementation status note (2026-02-09):**
- CM Phase 8 and LS Phase 8 component matrices are complete with parity and negative-path artifacts recorded under `runs/fraud-platform/.../case_mgmt/reconciliation/` and `runs/fraud-platform/.../label_store/reconciliation/`.

#### Phase 5.10 — Cross-cutting efficiency hardening gate (meta-layer pre-Phase 6 execution)
**Goal:** reduce full-stream validation cycle time through shared hot-path hardening without scope-creeping into deep per-component tuning.

**DoD checklist:**
- Efficiency baseline artifact is produced from a fresh active run and includes:
  - WSP wall-clock stream runtime from `session.jsonl` (`stream_start` -> `stream_complete`).
  - Per-output source window (`first_event_ts_utc`, `event_200_ts_utc`) and replay-delay estimate:
    - `expected_wall_seconds = (event_200_ts_utc - first_event_ts_utc) / stream_speedup`.
  - IG latency summaries from run-scoped metrics (`admission_seconds`, `phase.publish_seconds`) with median/p95/max.
  - WSP retry pressure (`retry_total`, `retry_exhausted_total`) from run logs/counters.
- Local-parity performance budgets are pinned for acceptance:
  - `20` event full-stream gate wall-clock `<= 300s`.
  - `200` event full-stream gate wall-clock `<= 1200s`.
  - IG `admission_seconds` p95 `<= 8s`.
  - IG `phase.publish_seconds` p95 `<= 5s`.
  - WSP `retry_exhausted_total = 0` and `retry_total / pushed_events <= 1%`.
- Scope boundary is explicit and enforced for this gate:
  - in scope now: `WSP -> IG -> EB` path, run/operate sequencing, and obs/gov measurement surfaces;
  - deferred: deep micro-optimization inside non-hot-path component internals (captured as post-Phase-6 hardening backlog unless they block these budgets).
- Validation is rerun in strict order (`20` then `200`) with run-scoped evidence paths in implementation map + logbook.
- Phase 6 execution is blocked until this gate is PASS, or an explicit user-approved risk acceptance is recorded with rationale and expiry.

**Implementation status note (2026-02-10):**
- Shared Kinesis consumer resilience hardening landed (`src/fraud_detection/event_bus/kinesis.py`) with stale-checkpoint fallback + suppression and transient-read tolerance.
- 20-event gate PASS: `platform_20260210T082746Z` (`emitted=80`, wall-clock `10.703694s`).
- 200-event gate PASS: `platform_20260210T083021Z` (`emitted=800`, wall-clock `85.823407s`).
- Post-fix reconfirmation PASS on fresh active run `platform_20260210T091951Z`:
  - 20-event gate (`emitted=80`, `stream_start=2026-02-10T09:21:46.780111+00:00`, `stream_complete=2026-02-10T09:22:00.188588+00:00`).
  - 200-event gate (`emitted=800`, `stream_start=2026-02-10T09:24:36.354654+00:00`, `stream_complete=2026-02-10T09:25:55.947318+00:00`).
  - Post-stream idle hold remained all-green in run/operate status across all five packs (`control_ingress`, `rtdl_core`, `rtdl_decision_lane`, `case_labels`, `obs_gov`).
- Budget checks PASS:
  - 20 wall-clock `10.703694s <= 300s`
  - 200 wall-clock `85.823407s <= 1200s`
  - IG admission p95 max sample `1.4493895999912638s <= 8s`
  - IG publish p95 max sample `0.16315989999566227s <= 5s`
  - WSP retries in stream windows `0`, retry-exhausted `0`

### Phase 6 — Learning & Registry plane
**Intent:** implement reproducible learning and deterministic bundle lifecycle while keeping new services first-class citizens under run/operate + obs/gov meta layers from day one.

#### Phase 6.0 — Archive readiness gate (blocking precondition)
**Goal:** make long-horizon replay truth explicit and operational before Learning service implementation.

**DoD checklist:**
- Archive writer contract is pinned and implemented as an explicit corridor: admitted EB events are copied to archive storage with immutable refs.
- Archive records carry mandatory provenance fields: `origin_offset` tuple, `ContextPins`, payload digest/hash, schema/event class, and observed write time.
- Replay integrity check is defined and enforced: EB/archive mismatch for the same offset tuple is an anomaly and fails closed for training-intent dataset builds.
- Run/operate and obs/gov surfaces include archive writer health/counters and reconciliation refs so archive readiness is visible in parity and higher environments.
- Phase `6.1` does not begin until this gate is PASS, or explicit user-approved risk acceptance is recorded with rationale and expiry.

**Implementation status note (2026-02-10):**
- Archive writer corridor implemented under `src/fraud_detection/archive_writer/`:
  - immutable archive record contract with `origin_offset` + ContextPins (`contracts.py`),
  - replay-basis mismatch detection (`same offset tuple + different payload hash`) and anomaly posture (`store.py`, `observability.py`),
  - runtime worker (`worker.py`) writing archive artifacts + metrics/health/reconciliation.
- Run/operate onboarding completed:
  - `archive_writer_worker` added to `config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml`.
  - parity env/make defaults wired (`PARITY_ARCHIVE_WRITER_LEDGER_DSN`).
- Obs/Gov onboarding completed:
  - archive summary added to platform report payload,
  - archive reconciliation refs included in reporter discovery.
- Validation evidence:
  - targeted tests green: `tests/services/archive_writer/*`,
  - pack status confirms process-up: `archive_writer_worker: running ready` in `local_parity_rtdl_core_v0`,
  - run-scoped artifacts present under `runs/fraud-platform/<platform_run_id>/archive_writer/*` and `runs/fraud-platform/<platform_run_id>/archive/reconciliation/archive_writer_reconciliation.json`.

#### Phase 6.1 — Contracts + ownership lock (Learning/Registry)
**Goal:** pin cross-component learning/registry contracts and prevent authority drift before service implementation.

**DoD checklist:**
- Authoritative schemas/contracts are pinned for `DatasetManifest`, training/eval outputs, bundle publication, promotion events, and DF bundle-resolution response.
- Ownership boundaries are explicit and enforced:
  - OFS owns dataset manifests/featureset materialization.
  - MF owns training/evaluation artifacts and bundle publication intent.
  - MPR/Registry owns ACTIVE lifecycle and deterministic resolution truth.
- Replay basis contract is pinned: EB/archive offsets + label as-of basis + feature definition version are mandatory; no `latest` lookup semantics.
- Compatibility contract is pinned for DF resolution (`bundle_ref`, compatibility metadata, policy/bundle version gates, fail-closed behavior).

**Implementation status note (2026-02-10):**
- Authoritative schema set added under `docs/model_spec/platform/contracts/learning_registry/`:
  - `dataset_manifest_v0.schema.yaml`
  - `eval_report_v0.schema.yaml`
  - `bundle_publication_v0.schema.yaml`
  - `registry_lifecycle_event_v0.schema.yaml`
  - `df_bundle_resolution_v0.schema.yaml`
- Typed contract validators added in `src/fraud_detection/learning_registry/` and validated via tests.
- Ownership boundaries pinned in `config/platform/learning_registry/ownership_boundaries_v0.yaml`.
- Contracts index updated (`docs/model_spec/platform/contracts/README.md`) to reference Archive + Learning/Registry authorities.
- Validation evidence:
  - `tests/services/learning_registry/test_phase61_contracts.py` green.

#### Phase 6.2 — OFS dataset build corridor
**Goal:** produce deterministic, rebuildable datasets with strict basis/provenance.

**DoD checklist:**
- OFS runs as explicit jobs with pinned inputs (manifest refs, label as-of, feature-def-set version, run scope).
- DatasetManifest carries full provenance: replay basis, label basis, feature-def version, code release id, digests, and evidence refs.
- OFS fails closed on missing/invalid basis inputs, replay mismatches, or label-basis violations.
- Materialized dataset artifacts are by-ref in object store; manifests remain authoritative for rebuild.

**Planning status note (2026-02-10):**
- OFS component execution map created at:
  - `docs/model_spec/platform/implementation_maps/offline_feature_plane.build_plan.md`
- Component plan explicitly includes run/operate and obs/gov onboarding gates before OFS closure.

#### Phase 6.3 — MF train/eval/publish corridor
**Goal:** make model training and publication evidence-first and reproducible.

**DoD checklist:**
- MF consumes only pinned DatasetManifest refs (no implicit dataset discovery).
- Eval outputs are produced with metric schema/version and evidence refs suitable for promotion checks.
- Bundle publication writes immutable bundle refs + manifests with compatibility metadata and lineage to dataset/eval artifacts.
- Failure posture is explicit and fail-closed for missing evidence, incompatible feature definitions, or unresolved lineage refs.

#### Phase 6.4 — Registry/MPR lifecycle + deterministic resolution
**Goal:** enforce governed, deterministic ACTIVE lifecycle across environments/scopes.

**DoD checklist:**
- Registry lifecycle events are append-only and idempotent (`PUBLISHED`, `APPROVED`, `PROMOTED_ACTIVE`, `ROLLED_BACK`, `RETIRED`).
- ScopeKey policy is enforced (`environment`, `mode`, `bundle_slot`, optional tenant) with exactly one ACTIVE per scope.
- Resolution order is deterministic and fail-closed on incompatibility/ambiguity.
- Promotion/rollback requires governance actor attribution + evidence refs; unsafe actions are rejected.

#### Phase 6.5 — DF integration corridor (Registry -> runtime decisions)
**Goal:** cut DF to registry-resolved bundles without provenance loss or silent fallback.

**DoD checklist:**
- DF resolves bundles via MPR/Registry API only; no local ad-hoc bundle selection.
- Decision payloads retain full provenance (`bundle_ref`, snapshot/hash basis, graph/version basis, policy/bundle revs).
- Incompatible or missing ACTIVE resolution causes explicit degrade/fail-closed behavior per pinned policy.
- Replay of prior decision runs re-resolves deterministically to the expected historical bundle context.

#### Phase 6.6 — Run/Operate meta-layer onboarding (Learning/Registry services)
**Goal:** onboard all new Phase 6 services into orchestration packs and environment parity profiles before closure.

**DoD checklist:**
- Run/operate pack(s) include OFS/MF/MPR runtime units (worker/job launcher/scheduler wrappers as designed) with health/readiness probes.
- Local parity wiring uses pinned stack classes from environment map (object store/event bus/postgres) with no silent filesystem fallback in parity mode.
- Startup/sequence contracts are explicit (dependencies, backoff, bounded retry, restart semantics) and reflected in runbook commands.
- Active-run scoping and config-digest stamping rules are enforced in orchestration surfaces.

#### Phase 6.7 — Obs/Gov meta-layer onboarding (Learning/Registry services)
**Goal:** make learning/registry lifecycle and anomalies auditable with low-overhead structured evidence.

**DoD checklist:**
- Required run-scoped counters are emitted for OFS/MF/MPR and included in platform reconciliation/report artifacts.
- Governance lifecycle facts for dataset/build/train/eval/publish/promote/rollback are emitted with actor attribution and evidence refs.
- Corridor anomalies are emitted as low-volume structured events with fail-closed behavior where policy requires.
- Evidence-ref resolution audit is enforced for learning/registry evidence access paths.

#### Phase 6.8 — Plane integration closure gate
**Goal:** prove end-to-end learning loop continuity under orchestrated meta layers before moving to Phase 7.

**DoD checklist:**
- End-to-end continuity proof exists:
  - `decision audit + labels -> dataset manifest -> train/eval -> bundle publish -> promotion -> DF resolution`.
- Negative-path proof exists:
  - missing label basis,
  - replay basis mismatch,
  - incompatible bundle promotion,
  - unauthorized promotion/ref access attempts.
- Monitored parity evidence includes run-scoped logs/artifacts for OFS/MF/MPR and updated platform report/conformance outputs.
- Phase 7 start is blocked until this section is PASS, or explicit user-approved risk acceptance is recorded with rationale and expiry.

### Phase 7 — Efficiency-first P1 hardening (throughput + scale + extended obs/gov)
**Intent:** treat capacity and runtime efficiency as first-order gates before wider P1 hardening, so large-volume operation is engineered from measured evidence rather than assumption.

#### Phase 7.1 — Efficiency + capacity envelope gate (blocking)
**Goal:** establish measured throughput posture and close high-impact bottlenecks before broader P1 work.

**DoD checklist:**
- Two benchmark modes are pinned and reported:
  - event-time fidelity mode (design-faithful pacing),
  - throughput stress mode (minimal pacing for capacity measurement).
- `20` and `200` validation slices in throughput mode complete in seconds (not minutes) under local parity targets, with run-scoped evidence.
- Per-lane throughput/latency budget table exists (WSP/IG/EB/RTDL/Case/Label/Learning) with p50/p95 and saturation indicators.
- Capacity projection is documented from measured throughput to large-run scenarios (including `132M` events) with explicit assumptions and bottleneck map.
- Top bottlenecks are closed or explicitly accepted with quantified risk and follow-up owner/date.

#### Phase 7.2 — Scaled observability posture
**Goal:** raise observability depth at scale without violating hot-path budget.

**DoD checklist:**
- Wider OTel tracing coverage is enabled with controlled sampling/retention policy by environment.
- Golden-signal dashboards + SLO alerts are defined and validated against sustained traffic profiles.
- Run reporter/conformance/reconciliation jobs remain bounded-cost under scaled run counts.

#### Phase 7.3 — Governance/compliance automation
**Goal:** codify corridor checks and lifecycle controls into repeatable automated gates.

**DoD checklist:**
- Corridor-compliance checks-as-code execute periodically and emit PASS/FAIL artifacts.
- Promotion and policy-change workflows enforce governance actor/evidence gates automatically.
- Ref-resolution governance auditing is queryable and supports incident/review workflows.

#### Phase 7.4 — Security and tenancy hardening
**Goal:** harden runtime security posture for broader production exposure.

**DoD checklist:**
- Token/cert rotation workflows are automated and validated.
- Egress controls and least-privilege boundaries are tightened and tested.
- Tenant isolation hardening steps are implemented per environment roadmap.

#### Phase 7.5 — DR/replay resilience gate
**Goal:** validate replay/disaster-recovery posture under injected failures.

**DoD checklist:**
- DR/replay runbooks are validated via fault-injection scenarios with recorded outcomes.
- Recovery objectives and replay correctness evidence are documented per environment profile.
- Residual risk register is updated with explicit mitigations and owners.

## v1 expectations (beyond v0)
- Multi-tenant and multi-world concurrency with stronger isolation.
- HA + autoscaling for hot-path services; replay/DR runbooks with proven RPO/RTO.
- Archive tier for long-horizon replay + backfill orchestration.
- Automated policy gates for registry promotion and schema acceptance.
- Deeper model lifecycle: shadow/canary/ramp automation with guardrails.

## vX possibilities (future horizons)
- Cross-region active/active with deterministic registry resolution.
- Advanced explainability and model governance workflows.
- Federated label sources + privacy-preserving training workflows.
- Multi-bus / multi-domain expansion (fraud + risk + compliance) under shared rails.

## Status (rolling)
- Phase 1: complete (rails + substrate pins + validation + profiles).
- Phase 2: complete (Oracle Store + WSP stream‑view parity).
- Phase 3: complete (control & ingress plane green for v0).
- Phase 4.2 (IEG): complete.
- Phase 4.3 (OFP): complete.
- Phase 4.3.5 (Context Store + FlowBinding join plane): complete.
- Phase 4.4 (DF/DL): complete.
- Phase 4.5 (AL + DLA): complete.
- Phase 4 (RTDL plane overall): strict-green closure complete for current scope; residual `4.6.L` items are closed with explicit criteria/evidence.
- Phase 4.6 (Run/Operate + Obs/Gov meta-layer closure gate): complete (`4.6.A..4.6.K` PASS and `4.6.L` residual closure complete as of 2026-02-09).
- Phase 5 (Label & Case plane): complete (`5.1..5.9` closed; CaseTrigger/CM/LS integration lane is live under run/operate and reflected in platform reporter/conformance artifacts; latest parity evidence anchored to run `platform_20260210T083021Z`).
- Phase 5.10 (cross-cutting efficiency hardening, pre-Phase 6): complete (`20 -> 200` budget PASS validated on `platform_20260210T082746Z` and `platform_20260210T083021Z`, then reconfirmed post-fix on `platform_20260210T091951Z`; run-scoped evidence captured in implementation map + logbook).
- Phase 5.1 (contracts + identity pins): complete (`CM/LS` contract code + schemas + tests, `22 passed` on 2026-02-09).
- LS build-plan Phase 2 (writer boundary + idempotency corridor): complete (`5 passed` Phase 2 matrix; LS Phase1+2 `15 passed`; CM label/phase8 regressions `10 passed`; CM full regression `44 passed`; deterministic LS write corridor landed in `src/fraud_detection/label_store/writer_boundary.py` with fail-closed payload hash mismatch handling).
- LS build-plan Phase 3 (append-only timeline persistence): complete (`4 passed` Phase 3 matrix; LS Phase1..3 `19 passed`; CM label/phase8 regressions `10 passed`; CM full regression `44 passed`; append-only timeline storage + deterministic subject ordering + rebuild utility landed in `src/fraud_detection/label_store/writer_boundary.py`).
- LS build-plan Phase 4 (as-of + resolved-query surfaces): complete (`4 passed` Phase 4 matrix; LS Phase1..4 `23 passed`; CM label/phase8 regressions `10 passed`; observed-time-gated `label_as_of(...)`, deterministic resolved view, and explicit `CONFLICT/NOT_FOUND` posture landed in `src/fraud_detection/label_store/writer_boundary.py` with exports in `src/fraud_detection/label_store/__init__.py`).
- LS build-plan Phase 5 (ingest adapters for CM + engine/external truth lanes): complete (`5 passed` Phase 5 matrix; LS Phase1..5 `28 passed`; CM label/phase8 regressions `10 passed`; source-lane adapters landed in `src/fraud_detection/label_store/adapters.py` with fail-closed mapping and deterministic non-CM case-event derivation, exported via `src/fraud_detection/label_store/__init__.py`).
- LS build-plan Phase 6 (observability/governance/access audit): complete (`4 passed` Phase 6 matrix; LS Phase1..6 `32 passed`; CM label/phase8 regressions `10 passed`; platform reporter regression `2 passed`; LS run-scoped metrics/health/reconciliation + lifecycle governance emission + access-audit hook surfaces landed in `src/fraud_detection/label_store/observability.py`, exported via `src/fraud_detection/label_store/__init__.py`; platform reporter reconciliation discovery now includes LS contribution refs in `src/fraud_detection/platform_reporter/run_reporter.py`).
- LS build-plan Phase 7 (OFS integration and as-of training safety): complete (`4 passed` Phase 7 matrix; LS Phase1..7 `36 passed`; CM label/phase8 regressions `10 passed`; platform reporter regression `2 passed`; OFS-consumable bulk as-of slice surfaces, deterministic digest artifacts, run-scope target enforcement, and dataset gate signals landed in `src/fraud_detection/label_store/slices.py` and were exported via `src/fraud_detection/label_store/__init__.py`).
- LS build-plan Phase 8 (integration closure and parity proof): complete (`4 passed` Phase 8 matrix; LS Phase1..8 `40 passed`; CM label/phase8 regressions `10 passed`; platform reporter regression `2 passed`; continuity + parity + negative-path artifacts captured at `runs/fraud-platform/platform_20260209T213020Z/label_store/reconciliation/phase8_parity_proof_20.json`, `runs/fraud-platform/platform_20260209T213200Z/label_store/reconciliation/phase8_parity_proof_200.json`, and `runs/fraud-platform/platform_20260209T213400Z/label_store/reconciliation/phase8_negative_path_proof.json`).
- Phase 5.2 (CaseTrigger service + CM intake boundary): complete (Phase `5.2.A..5.2.H` closed on 2026-02-09; CaseTrigger Phase 8 matrix `4 passed`; CaseTrigger+IG regression `45 passed`; CM Phase1+2 regression `16 passed`; parity artifacts at `runs/fraud-platform/platform_20260209T180000Z/case_trigger/reconciliation/phase8_parity_proof_{20,200}.json` and `phase8_negative_path_proof.json`; reconciliation refs exposed to platform reporter).
- Phase 5.3 (CM timeline truth + workflow projection): complete (Phase-3 CM matrix `4 passed`; CM Phase1+2+3 suite `20 passed`; deterministic append-only actor-attributed timeline + projection/query surfaces landed in `src/fraud_detection/case_mgmt/intake.py` on 2026-02-09).
- CM build-plan Phase 4 (evidence-by-ref resolution corridor): complete (`4 passed` Phase 4 matrix; CM Phase1..4 `24 passed`; by-ref policy-gated corridor in `src/fraud_detection/case_mgmt/evidence.py` with explicit `PENDING/RESOLVED/UNAVAILABLE/QUARANTINED/FORBIDDEN` status snapshots).
- CM build-plan Phase 5 (CM->LS label emission handshake): complete (`6 passed` Phase 5 matrix; CM Phase1..5 `30 passed`; CaseTrigger/IG regression `45 passed`; lock-safe sequencing fix landed in `src/fraud_detection/case_mgmt/label_handshake.py` with policy at `config/platform/case_mgmt/label_emission_policy_v0.yaml` and exports via `src/fraud_detection/case_mgmt/__init__.py`).
- CM build-plan Phase 6 (CM->AL manual action boundary): complete (`6 passed` Phase 6 matrix; CM Phase1..6 `36 passed`; CaseTrigger/IG regression `45 passed`; deterministic manual ActionIntent emission + by-ref outcome attach lane landed in `src/fraud_detection/case_mgmt/action_handshake.py` with policy at `config/platform/case_mgmt/action_emission_policy_v0.yaml` and projection semantics updated in `src/fraud_detection/case_mgmt/intake.py`).
- CM build-plan Phase 7 (observability, governance, reconciliation): complete (`4 passed` Phase 7 matrix; CM Phase1..7 `40 passed`; CaseTrigger/IG regression `45 passed`; platform reporter regression `2 passed`; CM run-scoped metrics/health/reconciliation and lifecycle governance emission landed in `src/fraud_detection/case_mgmt/observability.py`; Case+Labels reconciliation contribution now emits under `runs/<platform_run_id>/case_labels/reconciliation/{YYYY-MM-DD}.json` and `case_mgmt_reconciliation.json`).
- CM build-plan Phase 8 (integration closure/parity proof): complete (`4 passed` Phase 8 matrix; CM Phase1..8 `44 passed`; CaseTrigger/IG regression `45 passed`; platform reporter regression `2 passed`; parity artifacts captured at `runs/fraud-platform/platform_20260209T210000Z/case_mgmt/reconciliation/phase8_parity_proof_{20,200}.json` and `phase8_negative_path_proof.json`).
- Phase 6.0 (Archive readiness gate): complete (archive writer corridor implemented + run/operate onboarding + reporter/reconciliation evidence surfaces validated on 2026-02-10).
- Phase 6.1 (Learning/Registry contracts + ownership lock): complete (authoritative schema set + typed validators + ownership boundaries pinned on 2026-02-10).
- Phase 6 (Learning & Registry plane): active (`6.2` OFS dataset-build corridor is next; `6.6/6.7` remain mandatory closure gates before plane completion).
- OFS build-plan Phase 1: complete (`BuildIntent + dataset identity + contract lock` implemented on 2026-02-10 in `src/fraud_detection/offline_feature_plane/*` with `15 passed`; next OFS step is Phase 2 run-ledger implementation).
- OFS build-plan Phase 2: complete (`run control + idempotent run ledger` implemented on 2026-02-10 in `src/fraud_detection/offline_feature_plane/run_ledger.py` and `run_control.py`; combined OFS/learning regression `21 passed`; next OFS step is Phase 3 provenance resolver).
- Next active platform phase: Phase 6.2 (OFS dataset build corridor).
- SR v0: complete (see `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`).
