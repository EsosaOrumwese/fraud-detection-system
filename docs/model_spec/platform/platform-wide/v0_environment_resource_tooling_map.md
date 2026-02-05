# v0 Environment Resource Tooling Map

## Control & Ingress v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the Control & Ingress plane (SR → WSP → IG → EB + receipts) in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

### 1) Resources to provision (plane-scoped)

#### A) Compute roles
- **Scenario Runner (SR)**: on-demand job/one-shot runner (writes `run_facts_view`, emits READY).
- **World Streamer Producer (WSP)**: on-demand job/one-shot producer (consumes READY, POSTs events to IG).
- **Ingestion Gate (IG)**: long-running service (HTTP ingest boundary, validation, dedupe, publish, receipts/backfill markers).
- *(Optional, out-of-band)* **Run reconciliation writer**: periodic job/writer that aggregates counters + refs into a run-scoped reconciliation JSON (must not sit on the hot path).

#### B) Messaging (Control bus + Event bus)
- **Control bus topic**: `fp.bus.control.v1` (READY + low-volume governance/anomaly facts).
- **Control bus stream** (Kinesis stream name, env-specific): `sr-control-bus` in local_parity.
- **Event bus streams/topics** (fraud-mode local parity example):
  - `fp.bus.traffic.fraud.v1`
  - `fp.bus.context.arrival_events.v1`
  - `fp.bus.context.arrival_entities.v1`
  - `fp.bus.context.flow_anchor.fraud.v1`
- **Knobs per environment**:
  - retention window
  - shard/partition counts
  - consumer/producer concurrency limits (operational only; semantics unchanged)

#### C) Object store
- One bucket (or prefix namespace) for:
  - `run_facts_view`
  - IG receipts + quarantine records
  - reconciliation summaries (out-of-band)
- Must support by-ref evidence, append-only writes, and run-scoped paths via `platform_run_id`.

#### D) Admission DB (IG idempotency + publish state)
- A durable DB for IG admission state that persists:
  - dedupe tuple: `(platform_run_id, event_class, event_id)`
  - `payload_hash` (anomaly detection)
  - publish state machine: `PUBLISH_IN_FLIGHT`, `ADMITTED`, `PUBLISH_AMBIGUOUS`
  - `eb_ref` on success
  - `receipt_write_failed` marker for backfill
- v0 default substrate: Postgres (or equivalent durable OLTP DB).

#### E) Network / ingress
- An HTTP endpoint for IG ingest reachable by WSP.
- dev/prod posture: internal/private by default unless external producers are explicitly required.

#### F) Auth boundary (mechanism varies by env; semantics unchanged)
- `local_parity`: API key allowlist acceptable.
- `dev/prod`: mTLS or signed service tokens enforced at IG ingest boundary (uniform mechanism across services).

#### G) Minimal observability hooks (no hot-path drag)
- **Counters only** (periodic flush; run-scoped labels):  
  `wsp_sent`, `ig_received`, `admitted`, `duplicate`, `quarantined`, `publish_ambiguous`, `receipts_written`, `receipt_write_failed`.
- **Structured events only on anomaly paths** (rare by design):  
  `PAYLOAD_HASH_MISMATCH`, `PUBLISH_AMBIGUOUS`, `SCHEMA_INVALID`, etc.
- Deep truth remains in receipts/DLA/archive; avoid per-event logging in v0.

---

### 2) Low-friction tooling expectations

- **Single config shape** across environments; only profile values differ (`local_parity.yaml`, `dev.yaml`, `prod.yaml`).
- **Infra-as-code module** for this plane that provisions:
  - streams/topics, bucket/prefixes, admission DB, and IG service endpoint.
- **One launch interface**:
  - local: `docker compose` (or make target) bringing up LocalStack/MinIO/Postgres + services.
  - dev/prod: same container images + same env var names + same wiring config references.
- **Standard run invocation**:
  - SR can be invoked as a job/CLI with pinned inputs.
  - WSP can be invoked as a job/CLI with pinned outputs + concurrency/speedup knobs.

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Substrates: LocalStack Kinesis + MinIO + Postgres (compose-based).
- Retention: short.
- Auth: API key allowlist; no mTLS required.
- Observability: counters + minimal anomalies; reconciliation is optional but recommended.
- Rule: fail-closed on rail violations; convenience differences are operational only.

> If Archive is off in local_parity, any flow that requires Archive truth must be explicitly disabled or fail closed (no silent fallback to “whatever EB still has”).

#### dev
- Substrates: managed/real Kinesis + object store + managed Postgres.
- Retention: medium; Archive enabled where possible for replay tests.
- Auth: production-like (mTLS or signed service tokens) enforced at writer boundaries.
- Observability: closer to prod (stable dashboards, alerts, reconciliation artifacts).

#### prod
- Substrates: hardened managed equivalents; capacity scaled.
- Retention: long; Archive mandatory for replay/training guarantees.
- Auth: strongest posture (mTLS, tight allowlists, audited ref-resolution).
- Observability: SLOs, corridor checks, governance dashboards, response playbooks.
- Promotions: governed; immutable deployments; rollback explicit and auditable.

---

## Real-Time Decision Loop (RTDL) v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the RTDL plane (EB → inlets → context/feature/graph → decision → audit → actions) in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

RTDL consumes **admitted EB topics** as the online evidence boundary (origin_offset), applies idempotency + payload_hash anomaly detection, builds deterministic join context, emits decisions to DLA, and executes idempotent actions via AL. Archive may run in parallel as a separate writer but is treated as required for production replay/training guarantees.

---

### 1) Resources to provision (plane-scoped)

#### A) Messaging inputs (Event Bus topics + consumer groups)
- RTDL consumes the admitted EB topics (fraud-mode example):
  - `fp.bus.traffic.fraud.v1` (decision trigger)
  - `fp.bus.context.arrival_events.v1` (context skeleton)
  - `fp.bus.context.arrival_entities.v1` (context attachments)
  - `fp.bus.context.flow_anchor.fraud.v1` (flow binding / join-ready marker)
- Consumer groups:
  - one group per RTDL inlet (topic) with per-partition checkpoints
  - v0: ensure per-topic lag monitoring and safe restart behavior (checkpoints advance only after durable side effects)

#### B) RTDL compute roles
- **Bus inlet workers** (per topic): validate envelope + ContextPins, idempotency guards, stamp `origin_offset`, route to sub-planes.
- **Context builder**: updates JoinFrames in Context Store.
- **FlowBinding writer**: `(platform_run_id, flow_id) -> (platform_run_id, merchant_id, arrival_seq)` updates (authoritative from flow_anchor only).
- **Decision worker**: traffic-triggered join resolution + join-wait/degrade + DF execution.
- **DLA writer**: append-only decision records with evidence offsets.
- **Actions executor (AL)**: idempotent side effects keyed by decision_id + outcome records.

#### C) Stateful stores (rebuildable projections + append-only truth)
- **Context Store** (JoinFrames): keyed by `(platform_run_id, merchant_id, arrival_seq)`; join-ready markers.
- **FlowBinding Index**: keyed by `(platform_run_id, flow_id)`; atomic with JoinFrame updates for flow_anchor ingestion.
- **Online Feature Plane store (OFP)**: low-latency aggregates (rebuildable from EB/archive).
- **Identity & Entity Graph store (IEG)**: run-scoped projection; `graph_version` derived from offsets (rebuildable).
- **Decision Log & Audit Store (DLA)**: append-only decisions; ties to evidence `origin_offset` basis + pins.
- **Action outcomes store** (can be part of audit log): append-only outcomes with refs.

> v0 default substrate can be a single Postgres instance for Context/OFP/IEG/DLA indexes + object store for large artifacts; the key requirement is durability + idempotency, not a particular technology.

#### D) Archive surfaces (required for prod, optional for local)
- **Event Archive Writer** (recommended even in dev): copies EB events with origin_offset metadata + pins into object store for long-horizon replay.
- Archive truth rule: online evidence = EB origin_offset; replay evidence = archive origin_offset + payload; mismatches are anomalies and fail closed for replay/training.

#### E) Network / ingress
- RTDL is primarily a consumer plane (no public ingress required).
- Required internal service-to-service access to:
  - stores (Context/OFP/IEG/DLA)
  - object store (archive, decision evidence refs)
  - MPR (bundle resolution calls) and optionally DL (degrade posture updates)

#### F) Auth boundaries (mechanism varies by env; semantics unchanged)
- Enforced at corridor endpoints:
  - DLA append endpoint (if service-based)
  - Action execution endpoints
  - MPR bundle resolution and promotion endpoints (read vs write separation)
  - evidence-ref resolution services (RBAC-gated)

#### G) Minimal observability hooks (no hot-path drag)
- Counters (periodic flush, run-scoped labels):
  - inlet_seen, inlet_deduped, inlet_quarantined
  - context_updates, flowbinding_writes, flowbinding_conflicts
  - join_wait_count, degrade_count (by reason), decision_emitted
  - action_requested, action_success, action_failed
  - topic lag per partition
- Structured events only on anomalies:
  - PAYLOAD_HASH_MISMATCH, FLOWBINDING_CONFLICT, INCOMPATIBLE_BUNDLE_RESOLUTION, etc.

---

### 2) Low-friction tooling expectations

- **Single wiring/config shape** across environments; only profile values differ.
- **Infra-as-code module** for RTDL that provisions:
  - consumer groups/checkpoint storage (or equivalent), DBs/stores, object store prefixes, and required topics.
- **One launch interface**:
  - local: compose-based RTDL services + local stores + EB emulator.
  - dev/prod: same container images + same env var names + same config refs.
- **Replay tooling**:
  - ability to replay from Archive with pinned `origin_offset` ranges into a controlled test environment without “latest” reads.
- **Bundle resolution tooling**:
  - deterministic bundle selection via MPR; fail closed behavior test harness.

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Substrates: LocalStack Kinesis + MinIO + Postgres (compose-based).
- Stores: Postgres-backed Context/OFP/IEG/DLA indexes; object store for evidence.
- Archive: optional, but recommended for replay tests; if off, replay-only flows must be explicitly disabled or fail closed.
- Auth: simplified (API keys / disabled internally).
- Observability: counters + minimal anomalies; reconciliation optional.

#### dev
- Substrates: real Kinesis + object store + managed Postgres (or equivalent).
- Archive: enabled where possible; used for replay tests and offline loop validation.
- Auth: production-like (mTLS or signed service tokens) at corridor endpoints.
- Observability: stable dashboards, lag alerts, reconciliation artifacts.

#### prod
- Substrates: hardened managed equivalents; scaled partitions/shards and store capacity.
- Archive: mandatory; retention long; replay/training guarantees enforced.
- Auth: strongest posture (mTLS, tight RBAC for evidence ref resolution).
- Observability: SLOs (lag/latency/error), corridor checks, governance dashboards, incident playbooks.
- Governance: MPR promotion controls enforced; fail closed on incompatible bundle resolution.

---

## Case + Labels (Human Truth Loop) v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the Case + Labels plane (CaseTriggers → CM timelines → LabelAssertions → Label Store timelines → resolved views) in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

This plane is explicitly **by-ref** and **append-only**:
- Cases are keyed by `CaseSubjectKey = (platform_run_id, event_class, event_id)` with `case_id = hash(CaseSubjectKey)` (no merges in v0).
- Labels are execution-scoped by `LabelSubjectKey = (platform_run_id, event_id)` where `event_id` is the **traffic/decision-trigger event_id**.
- Label Store writer boundary enforces dedupe `(LabelSubjectKey, label_type, label_assertion_id)` + `payload_hash` anomaly detection and returns a durable ack/ref.

---

### 1) Resources to provision (plane-scoped)

#### A) Messaging inputs (CaseTriggers + optional outcomes feed)
- **CaseTrigger stream/topic** (low-to-moderate volume):
  - carries `CaseTrigger{ContextPins, CaseSubjectKey, trigger_type, source_ref_id, evidence_refs...}`
  - idempotency via `case_trigger_id = hash(case_id + trigger_type + source_ref_id)`
- **Optional**: consume AL outcomes or DLA events directly only if you *do not* use a trigger writer (v0 default is explicit CaseTriggers to keep CM opaque).

> v0 recommendation: emit CaseTriggers on a low-volume control/governance-capable bus (or a dedicated case-trigger stream) rather than having CM parse multiple upstream streams.

#### B) Compute roles
- **CaseTrigger writer** (thin service/job):
  - consumes DLA/AL refs as needed and emits explicit CaseTriggers
  - or RTDL/AL emit CaseTriggers directly (implementation choice)
- **Case Management (CM) service**:
  - consumes CaseTriggers and appends case timeline events
  - exposes an API for investigator actions (and optionally a UI)
  - emits ActionIntents to AL (never performs side effects directly)
- **Label Assertion emitter** (often same CM service):
  - turns investigator assertions/external outcomes into LabelAssertions and submits them to Label Store
- **Label Store (LS) writer boundary**:
  - receives LabelAssertions, enforces idempotency + payload_hash anomaly detection
  - returns durable ack/ref only after commit (WAL flushed)
- **Resolved label view provider**:
  - query-time “resolved label” per `(LabelSubjectKey, label_type)` using precedence rules
  - may be implemented as a query endpoint or materialized view (v0 can be query-time)

#### C) Core state stores (append-only truth + minimal indices)
- **CM store (append-only timelines)**:
  - cases keyed by `case_id = hash(CaseSubjectKey)`
  - timeline events keyed by `(case_id, timeline_event_type, source_ref_id)`
  - deterministic `case_timeline_event_id = hash(case_id + timeline_event_type + source_ref_id)`
- **LS store (append-only label timelines)**:
  - assertions deduped by `(LabelSubjectKey, label_type, label_assertion_id)`
  - `payload_hash` stored; mismatches -> ANOMALY
  - resolved view computed per `(LabelSubjectKey, label_type)` with precedence rules
- v0 default substrate: Postgres (or equivalent) with separate schemas for CM and LS.

#### D) Object store (light usage, by-ref)
- Optional but useful v0 surfaces:
  - reconciliation summaries (out-of-band)
  - exports/snapshots for offline consumers (if desired)
  - quarantine/anomaly evidence blobs (rare)
- CM and LS remain **refs-first**: they do not store authoritative payload truth.

#### E) Corridors / boundaries (mechanisms vary by env; semantics unchanged)
- **CM API/UI boundary**: investigator authn + actor attribution (Obs/Gov defines what must be logged).
- **LS writer boundary**: service authn + durable ack semantics.
- **CM → AL ActionIntent boundary**: idempotent submission keyed by `hash(case_id + source_case_event_id + intent_type + subject_key)`.

#### F) Minimal observability hooks (no hot-path drag)
- Counters (periodic flush, run-scoped labels):
  - `case_triggers_seen`, `cases_created`, `timeline_events_appended`
  - `labels_submitted`, `labels_pending`, `labels_accepted`, `labels_rejected`
  - `ls_deduped`, `ls_payload_hash_mismatch`, `ls_writer_errors`
- Structured events only on anomalies:
  - `PAYLOAD_HASH_MISMATCH`, `LABEL_ASSERTION_ANOMALY`, `REF_ACCESS_DENIED` (as applicable)

---

### 2) Low-friction tooling expectations

- **Single config shape** across environments; only profile values differ.
  - includes controlled vocabularies:
    - `trigger_type` enum (v0): `DECISION_ESCALATION | ACTION_FAILURE | ANOMALY | EXTERNAL_SIGNAL | MANUAL_ASSERTION`
    - `timeline_event_type` vocab (v0 minimal): `CASE_TRIGGERED | EVIDENCE_ATTACHED | ACTION_INTENT_REQUESTED | ACTION_OUTCOME_ATTACHED | LABEL_PENDING | LABEL_ACCEPTED | LABEL_REJECTED | INVESTIGATOR_ASSERTION`
    - `label_type` vocab (v0): `fraud_disposition | chargeback_status | account_takeover` (plus pinned value sets)
    - `ref_type` vocab (v0): `DLA_AUDIT_RECORD | DECISION | ACTION_OUTCOME | EB_ORIGIN_OFFSET | CASE_EVENT | EXTERNAL_REF`
- **Canonical hashing rules** pinned and shared:
  - LS `payload_hash` computed over canonical LabelAssertion fields only
  - `evidence_refs` sorted by `(ref_type, ref_id)` before hashing
- **Infra-as-code module** provisions:
  - case-trigger stream/topic (if dedicated)
  - CM service + DB schema
  - LS writer service + DB schema
  - object store prefixes for reconciliation/exports (optional)
- **One launch interface**
  - local: docker compose bringing up services + DB + any bus emulator
  - dev/prod: same container images + same env var names + same config refs

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Substrates: LocalStack (if using streams) + Postgres + MinIO (compose-based).
- CM/LS can run as simple services; UI optional.
- Auth: minimal (API key allowlist or disabled internally).
- Retention: short; exports optional; reconciliation optional but recommended.
- Failure posture: fail-closed on rail violations (dedupe/anomaly rules), convenience differences are operational only.

#### dev
- Substrates: real messaging + managed Postgres + object store.
- Auth: production-like at writer boundaries (mTLS or signed service tokens).
- Observability: stable counters, reconciliation artifacts, alerting on LS writer failures/anomalies.
- Retention: medium; enough to validate label timelines + offline joins.

#### prod
- Substrates: hardened managed equivalents; scaled DB/storage.
- Auth: strongest posture + RBAC for evidence ref resolution.
- Observability: SLOs for label ingest latency, case backlog metrics, governance dashboards.
- Retention: long-lived append-only CM/LS timelines; exports/snapshots governed.
- Governance: explicit audit for label acceptance/rejection and promotions; incident playbooks.

---

## Learning + Evolution (Offline Model Loop) v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the Learning + Evolution plane (OFS → DatasetManifest → MF → EvalReport → Bundle → MPR promotion) in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

This plane is explicitly **offline and job-driven**:
- OFS builds datasets from pinned **origin_offset replay bases** and **label_asof** cutoffs.
- MF trains only from DatasetManifests; “latest” is refused unless explicitly requested and recorded.
- MPR is the sole activation authority; promotions are explicit, append-only, and auditable.

---

### 1) Resources to provision (plane-scoped)

#### A) Durable truths and inputs
- **Archive store** (object store) holding admitted event history beyond EB retention:
  - events stored with `{topic/stream, partition/shard_id, sequence_number}` + `payload_hash` + ContextPins
- **Label Store timelines**:
  - resolved labels derived by precedence rules, with `effective_time` vs `observed_time`
- **DLA decision evidence** (for linkage/backtests as needed)
- **Feature definition authority**:
  - a versioned feature definition set shared with OFP (single source of truth)

> EB is a retention-bounded accelerator. Archive is the long-horizon truth for training and replay guarantees.

#### B) Job roles (explicit, not always-on)
- **OFS job runner**
  - triggered by a build intent
  - produces: DatasetManifest + materialized dataset artifacts (optional)
- **MF training job runner**
  - consumes DatasetManifest refs only
  - produces: train run record + EvalReport + candidate bundle (if PASS)
- **Evaluation harness**
  - run as part of MF or as a separate job stage
  - produces immutable EvalReports (variants allowed, e.g., delayed-label windows)
- **Registry operator interface** (could be API + CLI)
  - promotes/rolls back bundles in MPR (governed)

#### C) Stores and registries
- **Object store** (durable substrate) for:
  - DatasetManifests (`ofs/...`)
  - materialized datasets (optional; tiered/expirable)
  - EvalReports (immutable evidence)
  - model artifacts + bundles
  - anomaly/parity reports
- **Model/Policy Registry (MPR)** store:
  - bundle metadata, compatibility requirements, lifecycle events
  - ACTIVE pointers per `ScopeKey = {environment, mode, bundle_slot, tenant_id?}`
- Optional v0 DB:
  - index tables for manifests / runs / bundles (can live inside MPR DB)

#### D) Corridors / boundaries (mechanisms vary by env; semantics unchanged)
- **OFS input corridor**: only pinned replay bases and label_asof cutoffs; fail closed on EB/Archive mismatch.
- **MF publish corridor**: refuses to publish without required EvalReport + provenance.
- **MPR promotion corridor**: requires governance actor, evidence refs present, and compatibility metadata; append-only events.

#### E) Minimal observability hooks (no hot-path drag)
- Counters (job-scoped, periodic flush):
  - `ofs_build_requested/completed/failed`, `datasets_built`
  - `mf_train_requested/completed/failed`, `eval_pass/eval_fail`
  - `bundles_published`, `promotions`, `rollbacks`
- Structured events only on anomalies:
  - `REPLAY_BASIS_MISMATCH`, `SCHEMA_MISMATCH`, `INCOMPATIBLE_BUNDLE`, etc.

---

### 2) Low-friction tooling expectations

#### A) Pinned inputs and manifests (reproducibility law)
- **Replay basis** pinned as origin_offset ranges per topic/partition:
  - canonical offset tuple: `{topic/stream, partition/shard_id, sequence_number}`
  - time windows allowed only as selectors; resolved offsets recorded in DatasetManifest
- **Label cut** pinned:
  - `observed_time <= label_asof_utc` always
  - “unknown yet” negatives censored by default; maturity policy must be explicit in manifest
- **DatasetFingerprint law** pinned:
  - replay basis + label_asof + label resolution rule + join scope + feature_def_set + filters + profile/config revision
  - any identity change => new fingerprint + new immutable manifest
- **Code provenance pinned**:
  - `ofs_code_release_id`, `mf_code_release_id` recorded for reproducibility across upgrades

#### B) Evaluation tooling (anti-leakage + PASS gates)
- Splits are time-based and anchored to replay basis; random splits allowed only with pinned seed + rule.
- PASS requires:
  - compatibility gates (schema/features)
  - leakage gates (label_asof discipline)
  - performance gates (explicit metric thresholds per bundle slot)
- MF refuses bundle publish if EvalReport or required evidence refs are missing.

#### C) Promotion tooling (deterministic activation)
- One CLI/API workflow for:
  - list candidates, view evidence refs, approve/promote, rollback
- Deterministic resolution order:
  - tenant-specific ACTIVE → global ACTIVE → explicit safe fallback → fail closed

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Archive: optional, but if off then replay/training beyond EB retention must be explicitly disabled or fail closed.
- Jobs run locally (CLI/compose) with small datasets and short retention.
- Auth: minimal (API keys / local-only).
- Observability: counters + job logs; reconciliation optional but recommended.

#### dev
- Archive: enabled where possible to validate replay + manifests + training loop.
- Jobs run in shared infrastructure (scheduler/on-demand).
- Auth: production-like at MPR promotion corridor and evidence ref resolution.
- Observability: stable job dashboards, alerting on repeated build failures/anomalies.

#### prod
- Archive: mandatory (training/replay guarantees).
- Jobs run under governed schedules; evidence refs retained long-lived.
- Auth: strongest posture (RBAC for evidence access; governed promotions).
- Observability: SLOs for job completion windows, dataset/eval failure rates, promotion audit dashboards.
- Governance: promotions/rollbacks append-only with explicit approvals.

---

## Observability + Governance v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the Observability + Governance meta layer in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

**v0 posture:** minimize hot-path overhead. Prefer **counters + periodic summaries + by-ref evidence** over per-event logs. Governance is **low-volume append-only facts** for state-changing actions and anomalies.

---

### 1) Resources to provision (meta-layer scoped)

#### A) Metrics sink + lightweight aggregation
- A metrics sink/collector that supports:
  - periodic counter flush (10–60s)
  - run-scoped labels (`platform_run_id`, `scenario_run_id`, `environment`, `mode`, `policy_rev`)
  - low-cardinality dashboards (avoid high-cardinality joins in v0)
- v0 requirement: counters must be cheap to emit; avoid per-event logging on success paths.

#### B) Governance/anomaly fact stream (append-only)
- A low-volume, append-only stream (often `fp.bus.control.v1`) for:
  - governance lifecycle facts (promotions/rollbacks, label accepted/rejected, policy rev changed)
  - anomaly facts (payload hash mismatch, publish ambiguous, replay mismatch, incompatible bundle resolution)
- Facts are idempotent under retries and always attributed (`actor_id`, `source_type=HUMAN|SYSTEM`).

#### C) Reconciliation writer (out-of-band)
- A periodic job/writer that emits one run-scoped reconciliation artifact:
  - `s3://fraud-platform/{platform_run_id}/obs/reconciliation/YYYY-MM-DD.json`
- It aggregates counters and references key evidence IDs (receipts/audit ids) without copying payloads.

#### D) Evidence ref audit log (minimal)
- A minimal audit record per evidence-ref resolution:
  - `actor_id`, `source_type`, `ref_type`, `ref_id`, `purpose`, `platform_run_id` (if applicable), `observed_time`
- v0: log one record per resolution action, not per byte read; never log payload contents.

---

### 2) Tooling expectations (low friction)

#### A) Standard counter schema per plane
- **Control & Ingress**: sent/received/admitted/duplicate/quarantine/publish_ambiguous/receipts_written/receipt_write_failed
- **RTDL**: inlet_seen/deduped/quarantined, context_updates, flowbinding_writes/conflicts, join_wait, degrade(by reason), decisions_emitted, actions_outcomes
- **Case/Labels**: case_triggers/cases_created/timeline_appends/labels_pending/accepted/rejected, LS anomalies
- **Learning**: datasets_built, eval_pass/fail, bundles_published, promotions/rollbacks

Counters are required; per-event logs are prohibited except for anomaly/quarantine paths.

#### B) Standard governance fact types (v0 minimal)
- Run lifecycle: `RUN_READY_SEEN`, `RUN_STARTED`, `RUN_ENDED`, `RUN_CANCELLED`
- Registry lifecycle: `BUNDLE_PUBLISHED`, `BUNDLE_APPROVED`, `BUNDLE_PROMOTED_ACTIVE`, `BUNDLE_ROLLED_BACK`, `BUNDLE_RETIRED`
- Labels: `LABEL_SUBMITTED`, `LABEL_ACCEPTED`, `LABEL_REJECTED`
- Policy/config: `POLICY_REV_CHANGED`
- Access: `EVIDENCE_REF_RESOLVED`
- Anomalies: `PAYLOAD_HASH_MISMATCH`, `PUBLISH_AMBIGUOUS`, `REPLAY_BASIS_MISMATCH`, `INCOMPATIBLE_BUNDLE_RESOLUTION`

#### C) Corridor checks (failures only)
- Corridor checks emit:
  - counters always
  - a structured anomaly/governance fact **only on failure**
- Corridors: IG, DLA append, AL, LS writer, MPR promotion/resolution, evidence ref resolution.

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Metrics: minimal local collector/log-export; optional dashboards.
- Governance facts: written to local control stream and/or object store for inspection.
- Reconciliation: optional but recommended for debugging.
- Sampling: allowed; explicit; keep overhead low.

#### dev
- Metrics: stable dashboards + alerting on lags/anomalies; reconciliation artifacts required.
- Governance facts: centralized stream and retained long enough for audit during integration cycles.
- Sampling: reduced vs local; closer to prod.

#### prod
- Metrics: SLO-oriented dashboards (lag, error rates, corridor failures) + incident playbooks.
- Governance facts: retained per policy; immutable; reviewed for promotions/rollbacks.
- Reconciliation: required and operationally monitored.
- Sampling: minimal; default is counters + anomalies only; tracing is P1 and sampled if enabled.

---

## Run/Operate / Substrate v0 — Low/Minimal-Friction Resources & Tooling (per environment ladder)

This section enumerates the **minimum resources** and **low-friction tooling** required to run the Run/Operate / Substrate meta layer in `local_parity → dev → prod` while keeping **platform semantics identical** and only varying the operational envelope (scale/retention/security strictness/observability sampling).

This layer supplies the mechanisms that enforce Obs/Gov policies and keep the four planes operable:
- environment ladder + parity contracts
- service identity + auth at writer boundaries
- config + secret injection
- immutable deployments + promotion mechanics
- job orchestration for offline components (OFS/MF/reconcilers)

---

### 1) Resources to provision (meta-layer scoped)

#### A) Environment ladder baseline
- Named environments: `local_parity`, `dev`, `prod`
- Parity contract enforced by configuration:
  - same schemas, pins, dedupe keys, receipts/manifests, registry ScopeKey + resolution order
  - allowed differences only in capacity, retention, auth strength, and observability sampling

#### B) Deployment substrate
- Container runtime/execution for long-running services (IG, RTDL workers, CM, LS, MPR) and for jobs (SR, WSP, OFS, MF, reconcilers).
- Immutable artifacts:
  - all services deployed by image digest/tag
  - every evidence surface records `service_release_id` (image digest/tag or git SHA)

#### C) Orchestration substrate
- A job runner for:
  - SR, WSP (on-demand)
  - OFS, MF (scheduled/on-demand)
  - reconciliation writers (periodic)
- v0 rule: jobs run only by explicit intent; no “always-on” expensive compute.

#### D) Secrets and key management
- A secrets manager (implementation choice) for:
  - API keys (local_parity)
  - service tokens / mTLS cert material (dev/prod)
  - DB credentials, object-store credentials
- KMS-equivalent for encryption-at-rest keys (object store + DB)
- v0: manual rotation supported; rotation events recorded as governance facts.

#### E) Network posture
- Private connectivity between core services and stores.
- Writer boundaries exposed only where needed:
  - IG ingest boundary
  - LS writer boundary
  - MPR governance endpoints (operator-only)
  - CM UI/API (if present)
- v0: basic segmentation + inbound auth; strict egress allowlists are P1 hardening.

#### F) Config distribution and pinning
- A uniform mechanism to deliver wiring config to services (implementation choice).
- Required stamps in evidence artifacts (run-scoped):
  - `policy_rev` / `run_config_digest` as appropriate
  - `environment`, `mode`, `bundle_slot`, `tenant_id?`
  - `ofs_code_release_id`, `mf_code_release_id` for offline loop provenance

---

### 2) Tooling expectations (low friction)

#### A) One config shape, multiple profiles
- `local_parity.yaml`, `dev.yaml`, `prod.yaml` control only operational envelope:
  - shard counts, retention windows, auth mode, sampling
- Semantics must not differ across profiles.

#### B) One command surface (or make targets) per environment
- `local_parity`: `docker compose up` (or make target) to bring up:
  - LocalStack (Kinesis), MinIO, Postgres, and core services
- `dev/prod`: the same container images + same env var names + same config refs.

#### C) Promotion tooling (bundle lifecycle)
- A single CLI/API workflow for:
  - view candidates (evidence refs), approve, promote ACTIVE, rollback
- Promotions are mechanistically gated:
  - require authenticated governance actor
  - require evidence refs present (EvalReport, DatasetManifest, compatibility metadata)
  - emit append-only registry events (Obs/Gov)

#### D) Evidence-ref access tooling (mechanism)
- Ref resolution uses short-lived signed access or service-gated fetch (implementation choice).
- Substrate enforces:
  - authentication
  - time-bound access
  - audit hooks required by Obs/Gov
- Never log payload contents in access logs.

---

### 3) Environment ladder mapping (same semantics, different envelope)

#### local_parity
- Substrates: LocalStack + MinIO + Postgres + compose-based services/jobs.
- Auth: API key allowlists; no mTLS required.
- Retention: short; archive optional; rebuilds expected quick.
- Purpose: rapid iteration with full rails; fail-closed on rail violations.

#### dev
- Substrates: managed equivalents (real Kinesis/object store/DBs) sized for integration.
- Auth: production-like (mTLS or signed service tokens) enforced at writer boundaries.
- Retention: medium; archive on where possible for replay tests.
- Observability: stable dashboards + alerts + reconciliation artifacts.

#### prod
- Substrates: hardened managed equivalents with scale + DR planning (P1).
- Auth: strongest posture (mTLS, tight allowlists, RBAC for ref resolution).
- Retention: long; archive mandatory for replay/training.
- Governance: promotion controls enforced; corridor failures fail closed; response playbooks.

---
