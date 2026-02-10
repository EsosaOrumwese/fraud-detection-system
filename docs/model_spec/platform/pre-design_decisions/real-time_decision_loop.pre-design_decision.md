# Real-Time Decision Loop Pre-design Decisions (Open to adjustment where necessary)
_As of 2026-02-04_

Below are the **design‑level questions** I think we should settle **now** so the RTDL plan and component build are clean and unambiguous. I’ve grouped them by concern and ordered by impact.

## 1) Objectives & SLOs (drives architecture sizing)

- What are the **target latency SLOs** for the decision path (p50/p95/p99), and what is the **max acceptable worst‑case latency**?
- What is the **expected sustained throughput** and **burst factor** (events/sec, per partition)?
- Are we optimizing for **lowest latency** or **highest fidelity** under load (i.e., how aggressive is degrade)?

Detailed answers (recommended defaults, based on current implementation posture):
- Latency SLOs (EB ingest -> decision emitted by DF): p50 <= 100 ms, p95 <= 300 ms, p99 <= 800 ms. Max worst-case (hard timeout) 1500 ms, after which we force explicit degrade posture for that event.
- Throughput target: sustained 1-5k events/sec per run, burst 3-5x sustained for 1-5 minutes. Per-partition design assumes 200-500 events/sec per shard; scale by adding shards/partitions.
- Optimization stance: default to highest fidelity; do not silently trade correctness for latency. Degrade is explicit and recorded when SLOs or context requirements are violated.
- Deadline alignment: decision_deadline_ms = 1500 and join_wait_budget_ms = 600-900 (configurable). Join wait must always be <= decision_deadline, leaving budget for compute + logging.

## 2) EB Contracts & Retention
- What is the **retention window** for EB in each environment (local/dev/prod)?
- Do we require a **formal event archive** in object storage for long‑horizon replay? If yes, what is the required **archival SLAs** and **schema**?
- Is **EB the sole evidence of truth**, or do we treat the archive as equal truth? (This affects replay and dispute resolution.)

Detailed answers (recommended defaults, based on current implementation posture):
- Retention windows: local parity 1 day, dev/prod 7 days (adjustable, but 7 days fits Kinesis defaults without extra cost/ops).
- Archive requirement: yes. We need an object-store archive to preserve replay and audit beyond EB retention. Archive SLA: write within 5 minutes of EB receipt (v0 target).
- Archive schema: NDJSON per topic per day (or per hour at high volume). Each record includes the full canonical envelope plus EB metadata (topic, partition, offset, ingested_at_utc) and ContextPins. Optional: record hash for integrity checks.
- Truth posture: EB is live truth for online consumers; archive is long-term truth for replay/audit once EB retention expires. If EB and archive disagree, treat as audit anomaly and fail closed for replay.
  Truth sentence: for online processing, EB origin offsets are the evidence boundary; for replay, archive-stored origin offsets and payloads are the evidence boundary. Any mismatch is an audit anomaly; replay fails closed.

Open questions to confirm:
- Do we require archive storage to preserve per-partition ordering strictly (replay must be partition-ordered), or is ordering derived from stored offsets?
- What is the maximum acceptable delay for archive catch-up during spikes (SLA beyond the 5-minute target)?

Answers (recommended defaults):
- Archive storage must preserve per-partition ordering. Store records in partition-ordered sequence (or store offsets and replay by sorting on offset) so replay is deterministic.
- Archive catch-up SLA target remains 5 minutes; allowable max delay under spikes is 15 minutes before raising a WARN and 30 minutes before raising a FAIL and triggering backpressure to the archive writer.
- Archive lag does not block decisions in v0 unless EB retention risk is imminent; if gating is required, gate at run-level with explicit degrade posture.

## 3) Canonical Event & Versioning
- What is the **canonical event schema versioning policy** for RTDL consumption? (hard fail vs allow older schema with adapter)
- Are there any **schema evolution guarantees** per topic (backward/forward compatibility)?
- What is the **event_id contract**? (Is it content‑hash, deterministic by source, or random UUID?)  
  → This directly affects duplicate detection and collision risk.

Detailed answers (recommended defaults, based on current implementation posture):
- Versioning policy: major schema mismatch -> reject/quarantine. Minor forward-compatible versions are accepted only if an adapter exists. No silent coercion.
- Schema evolution guarantees per topic: additive-only in v0. No renames or removals without explicit alias mapping. New fields must be optional with stable defaults.
- event_id contract: deterministic content hash of stable fields. Recommended: sha256 over canonical JSON of {event_type, payload, ContextPins, ts_utc}, with stable key ordering and normalized encoding. Exclude volatile fields (ingest time, offsets, retry metadata). If the same event_id arrives with a different payload hash, treat as anomaly and quarantine.
  Canonicalization rules are pinned in code; event_id is producer-assigned and stable across retries. Persist payload_hash (payload-only) and treat mismatches as audit anomalies with quarantine.

Open questions to confirm:
- Which ContextPins are mandatory on all four RTDL topics, and which (if any) are optional?
- Who is the authoritative compatibility source: interface pack schema refs, registry resolution, or repo config revision?

Answers (recommended defaults):
- Mandatory pins on all RTDL topics: run_id, scenario_id, manifest_fingerprint, parameter_hash. Seed is required for synthetic runs; optional otherwise. Optional: trace_id, span_id, producer.
- Authoritative compatibility source is the interface pack schema refs pinned in repo; registry can override only when explicitly versioned and referenced by run_config_digest.

## 4) Join Readiness Rules (context ↔ traffic)
- What is the **exact join key** in RTDL (arrival_seq, flow_id, merchant_id) and which is authoritative when they disagree?
- What is the **join wait policy**: max wait time, queue size, retry strategy, and what triggers degrade?
- What constitutes **“context complete enough”** to score? (e.g., must have arrival_entities + flow_anchor?)

Detailed answers (recommended defaults, based on current implementation posture):
- Join key: authoritative key is (run_id, merchant_id, arrival_seq). flow_id is secondary and used once flow_anchor is present. If arrival_seq and flow_id disagree, arrival_seq wins and the event is flagged for audit.
- Join wait policy: bounded in-memory queue per partition; max wait 600-900 ms (configurable, must be <= decision_deadline) per traffic event. If timeout expires or queue is full, emit decision with explicit degrade_posture=context_missing and record missing context fields in the audit payload.
- Context completeness: required for scoring is arrival_events + flow_anchor for the same join key. arrival_entities is optional (used when present) and must not block scoring in v0. If flow_anchor is missing, default is degrade (do not infer).

## 5) Ordering & Watermarks
- Do we assume **per‑partition ordering only**, or do we need **cross‑topic ordering guarantees**?
- Will RTDL use **event_time watermarks** to gate joins, or strictly **arrival order**?
- What’s the **late‑event policy** (drop, late‑apply, or re‑score)?

Detailed answers (recommended defaults, based on current implementation posture):
- Ordering model: per-partition ordering only. Cross-topic ordering is not assumed; joins rely on time-bound waits and explicit completeness checks.
- Watermarks: use event_time (ts_utc) watermarks per partition with allowed lateness of 2 minutes. Watermarks are tracked and logged; they gate when context windows are considered closed.
- Late events: update state stores but do not trigger re-score in v0. Emit an audit note indicating late arrival and the watermark gap. Re-score is deferred to future phases.

Open questions to confirm:
- Do we require join locality across topics (same partition for a join frame), or accept cross-partition joins?
- If join locality is required, what is the canonical cross-topic partition key (arrival_seq vs flow_id vs merchant_id), and do IG partitioning profiles guarantee compatibility?

Answers (recommended defaults):
- Join locality is required for context topics. Full join locality across all four topics is not achievable without enriching traffic events (traffic schema lacks merchant_id/arrival_seq). v0 default: enforce locality for context streams on (merchant_id, arrival_seq) and allow cross-partition joins for traffic -> context. If we require full locality, we must enrich traffic events with merchant_id + arrival_seq (or add a deterministic mapping layer) and align IG partitioning profiles accordingly.

FlowBinding Index rules (required when traffic can cross partitions):
- Maintain a FlowBinding Index mapping flow_id -> (run_id, merchant_id, arrival_seq).
- Authority: only flow_anchor events may create/update FlowBinding.
- Conflict rule: if a different binding for the same flow_id appears, emit audit anomaly and quarantine; never silently replace.
- Resolution path: traffic event -> lookup FlowBinding by flow_id -> retrieve JoinFrame by JoinFrameKey. If missing within join_wait_budget_ms, degrade with context_missing: flow_binding_missing.

## 6) State Stores & Rebuildability
- What exact **state stores** are required (Context Store, OFP, IEG projection), and what are their **durability/TTL policies**?
- Is the **state rebuildable solely from EB+archive**, or do we allow manual repair?
- What’s the **checkpointing policy** per store (atomicity, lag, backfill strategy)?

Detailed answers (recommended defaults, based on current implementation posture):
- Required stores: Context Store, Online Feature Plane (OFP), Identity & Entity Graph (IEG) projection. v0 uses Postgres for all three; object store is used for archives and by-ref artifacts.
- Durability/TTL: Context Store TTL 7-30 days (aligned to EB retention + safety buffer). OFP TTL is window-based (e.g., 1h/24h/7d). IEG projection retained for run scope with watermark-based versioning.
- Rebuildability: all derived stores must be rebuildable from EB + archive. Manual repair is allowed only as a last-resort operational procedure and must emit an audit anomaly.
- Checkpointing: per partition/shard; offsets advance only after durable commit. Checkpoints are stored transactionally with state updates to prevent partial apply. Backfill is offset-driven and deterministic.

FlowBinding durability rule:
- FlowBinding writes are atomic with JoinFrame updates when processing flow_anchor. Only after both are committed (WAL flushed) may the flow_anchor checkpoint advance. This prevents traffic from resolving a flow_id before its binding is durable.

Open questions to confirm:
- What is the exact commit point per store (DB transaction committed + WAL flushed, or async write acknowledged)?
- Must DLA write succeed before advancing traffic offsets, or can decision logging lag behind with a separate checkpoint?

Answers (recommended defaults):
- Commit point is a committed DB transaction with WAL flushed (fsync on commit). Async acknowledgement is not sufficient for offset advancement.
- DLA write must succeed before advancing traffic offsets. Decision logging cannot lag the traffic offset in v0; if DLA fails, the traffic offset is not committed and the event will be retried.

## 7) Decision Fabric Contract
- What is the **decision API contract** (input envelope + required context artifacts)?
- What is the **minimum viable decision pipeline** for v0 (guardrails only, guardrails + model)?
- What are the **decision outputs** required by downstream (actions, audit, labels)? (fields + versioning)

Detailed answers (recommended defaults, based on current implementation posture):
- Decision API contract: input is the canonical envelope + EB offset basis + join context refs (arrival_events, flow_anchor, optional arrival_entities). Required pins: run_id, manifest_fingerprint, parameter_hash, scenario_id, seed. Required provenance: eb_offset_basis, graph_version (if available), snapshot_hash (if available), policy_rev.
- Minimum v0 pipeline: guardrails + single model. If model is not ready, guardrails-only is allowed but must still emit decision payload with degrade_posture=guardrails_only and policy_rev.
- Decision outputs (required fields): decision_id, action, reasons[], decision_ts_utc, degrade_posture, bundle_ref (or policy_ref), snapshot_hash, graph_version, eb_offset_basis, policy_rev. Version decision schema with explicit schema_version.

## 8) Actions Layer Semantics
- What are the **idempotency keys** for actions? (decision_id, event_id, or composite)
- What is the **action failure policy** (retry, fallback, compensate)?
- Are actions synchronous on the decision path or **async with eventual completion**?

Detailed answers (recommended defaults, based on current implementation posture):
- Idempotency key: decision_id derived from (event_id + bundle_ref + origin_offset). Use this key for action execution and dedupe.
- Failure policy: retry with exponential backoff and capped attempts; on final failure emit action_outcome=FAILED with error_code and reason. No silent success.
- Execution mode: async by default. Decision is emitted immediately; action outcomes are recorded as separate events for audit/labeling.

Open questions to confirm:
- Is the decision log write the commit point for advancing traffic offsets, with actions fully decoupled?

Answers (recommended defaults):
- Yes. Decision log write is the commit point for advancing traffic offsets. Actions are fully decoupled and must be idempotent; action outcomes can lag without blocking offset commits.

## 9) Audit / Decision Log
- What is the **required audit granularity** (full event payload vs references)?
- What is the **audit retention** and **immutability** requirement?
- How will **feature snapshots** be persisted (hash only vs full vector vs pointer)?

Detailed answers (recommended defaults, based on current implementation posture):
- Audit granularity: by-ref to EB event + by-ref to feature snapshot. Full payload stored only when explicitly required for investigation or regulation.
- Retention/immutability: append-only audit records in object storage, retained 1-3 years (configurable). Postgres holds an index only.
- Feature snapshots: store snapshot_hash + S3 ref. Full vector stored in S3 if required; otherwise pointer only.

Open questions to confirm:
- Do we store explicit context offsets (arrival_events, arrival_entities, flow_anchor) as part of the DLA evidence boundary?
- How is decision_id derived (traffic event_id only, or hash of pins + offsets + bundle_ref)?

Answers (recommended defaults):
- Yes. Store explicit context offsets used for the join frame (arrival_events, arrival_entities when present, flow_anchor) in DLA evidence boundary, alongside the traffic offset.
- decision_id is derived as a deterministic hash of (traffic event_id + bundle_ref + origin_offset). This is stable under replay and aligns with action idempotency.

Evidence offsets vs processing offsets:
- origin_offset = the EB offset where the evidence event was first admitted (immutable, stored in audit).
- checkpoint_offset = consumer progress offset (mutable, per consumer group, not evidence).

FlowBinding evidence rule:
- DLA must record the flow_anchor origin_offset used to resolve flow_id -> JoinFrameKey, in addition to traffic origin_offset and any arrival_events/entities offsets.

## 10) Security / Governance
- What data is considered **sensitive** in RTDL (PII, device IDs, etc.) and how is it masked in logs?
- Are there **data residency or encryption** requirements for the archive/audit stores?
- Who owns **truth resolution** when EB and archive disagree?

Detailed answers (recommended defaults, based on current implementation posture):
- Sensitive data: PII, device identifiers, account/instrument IDs, IPs. Logs must redact or tokenize; payloads stored by-ref in object storage with access controls.
- Encryption/residency: TLS in transit, KMS at rest for S3/Postgres; single-region in v0 unless policy states otherwise.
- Truth resolution: EB offsets are authoritative for live processing; archive is authoritative for long-term replay. Any mismatch raises an audit anomaly and fails closed for replay.

Open questions to confirm:
- What is the authentication mechanism between WSP and IG (mTLS, token, signed envelope), and do we sign ContextPins to prevent cross-run mixing?
- What is the access model for audit reads (least-privilege, redaction), and do we require key rotation policy for archive/audit data?

Answers (recommended defaults):
- WSP->IG uses mTLS in dev/prod; local parity uses token-based auth. ContextPins are not signed in v0 but must be verified against run_id and manifest_fingerprint; add signature in v1 if needed.
- Audit reads are least-privilege with redaction on sensitive fields. Key rotation is required for archive/audit encryption keys (KMS rotation policy, at least annually).

## 11) Run Lifecycle & Topic Discovery
- How does RTDL discover the topic set for a run (static config vs READY payload)?
- If a required topic is missing (e.g., flow_anchor), do we fail fast or run in explicit degraded mode?
- Do we emit RUN_END / RUN_CANCEL control events, and how are they deduped?
- Can multiple READY events occur (retries), and what is the dedupe rule?
- What does "active run" mean for components consuming multiple runs concurrently?

Detailed answers (recommended defaults, based on current implementation posture):
- Topic discovery: RTDL uses static config for topic names but validates against READY payload metadata (run_id, scenario_id, traffic mode). READY must include traffic_delivery_mode and expected topic set for validation.
- Missing topic behavior: fail fast for required topics (traffic + flow_anchor + arrival_events). arrival_entities missing triggers explicit degrade but does not block scoring in v0.
- Run lifecycle events: add RUN_END and RUN_CANCEL on control bus. Dedupe by (run_id, event_type, event_id).
- Multiple READY events: allowed for retries; dedupe by (run_id, event_id) and ignore duplicates after first successful activation.
- Active run semantics: RTDL can process multiple runs concurrently; each consumer group isolates by ContextPins. Active run is any run with a READY seen and not yet ended/canceled.

## 12) Health Gates & Backpressure
- Is health purely observational, or can it throttle/stop admission and processing?
- Do we implement backpressure to WSP/IG (429 / retry-after), or only internal throttles?
- What is the policy when EB is down: buffer, reject, or spool to object store?
- Under overload, do we drop, delay, degrade, or shed by class/partition?

Detailed answers (recommended defaults, based on current implementation posture):
- Health gates: health is observational by default but can throttle processing when EB or state stores are degraded (AMBER -> warn, RED -> throttle/stop).
- Backpressure: internal throttles first; if IG is the source, respond 429 with retry-after. WSP must retry with backoff.
- EB down: fail closed. Do not buffer in-memory beyond small safety queue; optionally spool to object store only if configured and idempotent.
- Overload: degrade before drop. Shed by class only if configured (e.g., non-critical contexts); traffic is never dropped without explicit policy.

## 13) Config/Version Pinning
- Which config revisions are part of run identity (class_map, partitioning profiles, output lists)?
- Do we compute a run_config_digest that all components log and validate?

Detailed answers (recommended defaults, based on current implementation posture):
- Run identity includes class_map revision, partitioning_profiles revision, schema_policy revision, and WSP output list revision.
- Compute run_config_digest from these revisions plus policy_rev and include it in READY and all receipts/decisions. Components validate digest matches before processing.

## 14) Observability & Reconciliation
- What are the must-have counters per run/topic (sent, admitted, duplicate, rejected, processed, degraded, quarantined)?
- Where does the reconciliation report live (object store run folder), and who writes it?
- Do we require end-to-end correlation IDs (flow_id, decision_id, event_id) in logs and metrics?

Detailed answers (recommended defaults, based on current implementation posture):
- Must-have counters per run/topic: received, admitted, duplicate, rejected/quarantined, processed, degraded, decision_emitted, action_outcome_recorded, archive_written. Report per topic and per partition.
- Reconciliation report: written to object store under s3://fraud-platform/{run_id}/rtdl/reconciliation/ with a daily summary JSON and per-partition details. RTDL control plane writer owns it.
- Correlation IDs: require flow_id (when present), event_id, decision_id in logs/metrics; trace_id/span_id optional but recommended for distributed tracing.

## 15) Failure Lanes / Poison Events
- What happens to events that consistently fail parsing or processing (DLQ/quarantine)?
- What is the replay procedure for quarantined events?
- How do we handle hot keys that repeatedly fail (partition isolation, throttle, quarantine)?

Detailed answers (recommended defaults, based on current implementation posture):
- Poison events are quarantined after N retries (default N=3) with the failure reason, payload hash, and offsets recorded in audit.
- Replay procedure: quarantine entries are stored by-ref in object storage; replay is an operator action that requeues from archive with a new replay_id and explicit override flag.
- Hot keys: isolate by throttling the affected partition/key, emit a throttle alert, and continue processing other partitions; if failures persist, quarantine by key for a bounded interval.

## 16) Online/Offline Parity & Learning Loop Hooks
- How do we guarantee OFP feature parity with offline recomputation from archive?
- What is the labeling/outcome ingestion path back into the Label Store?
- Do we plan shadow scoring or canary policies (score but do not act) in v0?

Detailed answers (recommended defaults, based on current implementation posture):
- Parity: OFP uses the same feature definitions as offline jobs; offline recomputation reads archive and must produce identical snapshot_hash for the same eb_offset_basis and graph_version.
- Labeling path: Actions Layer outcomes are emitted as events and ingested by Label Store via IG or a dedicated label ingestion pipeline (v1 if not in v0).
- Shadow scoring: optional in v0; if enabled, write decisions with action=SHADOW and do not execute side effects.

## 17) Idempotency & Dedupe (Cross-cutting)
- Is event_id guaranteed unique across all topics within a run_id?
- If not, is the dedupe key (run_id, topic_or_class, event_id)?
- Do we persist payload_hash and treat same id with different payload as an audit anomaly (quarantine/degrade)?

Detailed answers (recommended defaults, based on current implementation posture):
- event_id is not assumed unique across topics; dedupe key is (run_id, topic_or_class, event_id).
- Persist payload_hash for every admitted event; if event_id matches but payload_hash differs, record an audit anomaly and quarantine the later event.
