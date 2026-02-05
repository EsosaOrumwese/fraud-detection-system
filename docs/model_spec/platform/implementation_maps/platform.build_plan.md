# Platform Build Plan (v0)
_As of 2026-01-24_

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
- ContextPins are pinned as `{scenario_id, run_id, manifest_fingerprint, parameter_hash}` and `seed` is treated as a separate, required field when seed‑variant.
- Time semantics are pinned (domain `ts_utc`, optional `emitted_at_utc`, ingestion time in IG receipts).
- Naming/alias mapping for any legacy fields is documented (no hidden drift).

#### Phase 1.2 — By‑ref artifact addressing + digest posture
**Goal:** pin how artifacts are referenced and verified across components.

**DoD checklist:**
- Platform object‑store prefix map is pinned (bucket + prefixes for SR/IG/DLA/Registry/etc.).
- Locator schema and digest posture are pinned (content digest, bundle manifest digest rules).
- Instance‑proof receipts path conventions are pinned (engine vs SR verifier receipts).
- Token order rules are pinned for partitioned paths (seed → parameter_hash → manifest_fingerprint → scenario_id → run_id → utc_day).

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
The EB traffic plane is **single‑mode per run**: a run is either **fraud** (`s3_event_stream_with_fraud_6B`) or **baseline** (`s2_event_stream_baseline_6B`). Each channel carries **one event_type only** (no interleaving in v0). Downstream components subscribe only to the channel that matches the run mode.

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
- Required pins are enforced: `run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed`.
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
**Goal:** build deterministic projection state from EB offsets.

**DoD checklist:**
- IEG consumes EB and writes projection tables in Postgres.
- Graph watermark/graph_version advances deterministically.
- Replay from offsets produces identical graph_version state.

#### Phase 4.3 — OFP feature plane (graph → features)
**Goal:** materialize reproducible feature snapshots.

**DoD checklist:**
- Feature snapshot derived from a pinned graph_version.
- Snapshot hash + input_basis recorded (offset basis + graph_version).
- Snapshot retrieval is deterministic under replay.

#### Phase 4.4 — DF/DL decision core (features → decision)
**Goal:** compute decisions with explicit degrade posture.

**DoD checklist:**
- Registry bundle resolution is deterministic.
- DL enforces explicit degrade posture on stale/incomplete inputs.
- Decision payload includes bundle_ref + snapshot_hash + graph_version + offset basis.

#### Phase 4.5 — AL + DLA (decision → outcome → audit)
**Goal:** apply effects safely and record audit truth.

**DoD checklist:**
- Actions executed idempotently; retries do not duplicate effects.
- Outcomes are recorded with stable outcome_id.
- Append‑only audit record ties decision → action → outcome with provenance refs.

---

#### Pre‑design gating questions (RTDL)
Placeholders to resolve **before** expanding Phase 4 into detailed component build plans.

- **Objectives & SLOs:** What are p50/p95/p99 latency targets, max worst‑case latency, and expected sustained + burst throughput?
- **EB contracts & retention:** What are EB retention windows per env, and do we require an object‑store archive for long‑horizon replay? Is the archive co‑authoritative or a derived mirror?
- **Canonical event + versioning:** What is the event_id contract (hash vs UUID), and what are the schema compatibility rules per topic?
- **Join readiness rules:** What is the authoritative join key (arrival_seq vs flow_id), and when is context “complete enough” to score? What is the join‑wait policy?
- **Ordering & watermarks:** Are we assuming per‑partition ordering only, and what is the lateness policy (drop/late‑apply/re‑score)?
- **State stores & rebuildability:** Which stores are required (Context Store/OFP/IEG), what are their TTLs, and are they fully rebuildable from EB+archive?
- **Decision Fabric contract:** What is the minimal v0 decision pipeline (guardrails only vs model), and what fields must every decision emit?
- **Actions semantics:** What is the idempotency key, retry policy, and sync vs async action posture?
- **Audit / decision log:** What is the audit granularity (full payload vs refs), retention period, and snapshot storage policy?
- **Security & governance:** What data is sensitive in RTDL logs/archives, and what encryption/residency requirements apply?

---

### Phase 5 — Label & Case plane
**Intent:** crystallize outcomes into authoritative label timelines and case workflows.

**Definition of Done (DoD):**
- Label Store supports append-only timelines with as-of queries (effective vs observed time).
- Case management backend can open/advance/close cases and emit label assertions.
- Engine 6B truth/bank-view/case surfaces can be ingested via IG into Label Store.
- E2E: action outcome + case event -> label timeline update visible to learning plane.

### Phase 6 — Learning & Registry plane
**Intent:** create deterministic learning loop with reproducible datasets and controlled deployment.

**Definition of Done (DoD):**
- Offline Feature Plane rebuilds feature snapshots from EB/archive using the same schemas.
- DatasetManifest format pinned and used for training inputs (replay basis + label as-of).
- Model Factory produces bundles with evidence (metrics + lineage) and publishes to Registry.
- Registry resolves ACTIVE bundle deterministically and rejects incompatible bundles.
- E2E: decision audit + labels -> dataset manifest -> model bundle -> registry resolution -> DF uses ref.

### Phase 7 — Observability & Governance hardening
**Intent:** make behavior visible, safe to change, and auditable across planes.

**Definition of Done (DoD):**
- OTel-aligned metrics/logs/traces for SR/IG/DF/AL/DLA/OFP/IEG with ContextPins tags.
- Golden-signal dashboards and corridor checks for control/decision/label/learning planes.
- Governance facts emitted for policy changes, backfills, promotions, and readiness failures.
- Policy revision stamps are recorded on receipts/decisions/outcomes where applicable.
- Kill-switch / degrade ladder triggers are wired and tested end-to-end.

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
- SR v0: complete (see `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`).
