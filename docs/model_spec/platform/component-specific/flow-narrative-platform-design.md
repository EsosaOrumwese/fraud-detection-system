# Descriptive Narrative of Flow w/regards to Platform
_NOTE to AGENT: You are only allowed to change the doc under the EXPLICIT instruction from the USER. And if done, ensure edit is woven into the narrative flow of the platform_

## Local-Parity SR->WSP->IG->EB Narrative (`platform_20260201T224449Z`) — v0 pins surfaced

In local parity, the platform stack is brought up with LocalStack Kinesis, MinIO (object store), and the supporting services used by Control and Ingress. Kinesis exposes the control and event-bus streams, and MinIO exposes the fraud-platform bucket used for run artifacts and receipts. The run begins by generating a new **`platform_run_id`** and writing it as the active platform run (e.g., `runs/fraud-platform/ACTIVE_RUN_ID`) so downstream components resolve **platform-run-scoped** paths deterministically.

Scenario Runner (SR) executes against the Oracle Store roots (`ORACLE_ROOT`, `ORACLE_ENGINE_RUN_ROOT`, `ORACLE_STREAM_VIEW_ROOT`) and the interface pack contract. SR resolves a deterministic **`scenario_run_id`** (from the run equivalence key), validates the gate pass, assembles a `run_facts_view` for the selected scenario, and writes that view into the object store at a platform-run-scoped path (write-once; drift is rejected). SR then emits a READY control event into the control bus (topic `fp.bus.control.v1` on the Kinesis control stream) containing **both** `platform_run_id` and `scenario_run_id`, plus `manifest_fingerprint`, `parameter_hash`, `bundle_hash` (or plan hash), and other required pins. The READY event is idempotent: its `message_id` is derived from `platform_run_id + scenario_run_id + bundle_hash/plan_hash`, and consumers treat duplicates as no-ops.

World Streamer Producer (WSP) runs as the ready consumer. It listens to the control bus and, when it receives a READY event, dedupes by READY `message_id`, loads the `run_facts_view` from MinIO, and validates that the `scenario_run_id` in READY matches the facts view it loads. It builds its output plan from the `local_parity` profile: traffic output ids from `config/platform/wsp/traffic_outputs_v0.yaml` (fraud stream by default) and context output ids from `config/platform/wsp/context_fraud_outputs_v0.yaml` (`arrival_events_5B`, `s1_arrival_entities_6B`, `s3_flow_anchor_with_fraud_6B`). The run applies a stream speedup of `600x` (_this is a variable, where `0x` causes the events to flow according to the realistic `ts_utc` time_) and sets output concurrency to `4`, so all four outputs start together. Each output worker iterates its view, constructs the canonical event envelope with `ContextPins` (including `platform_run_id` and `scenario_run_id`) and payload, derives a deterministic `event_id`, and POSTs the event to the IG ingest endpoint. Under v0 pins, transient 429/5xx/timeouts are retried with bounded exponential backoff using the **same** `event_id`; schema/policy 4xx are treated as non-retryable and stop the stream with an explicit surfaced reason. The run caps emission at `200` events per output, so each worker emits `200` events before stopping (_this is a variable and can be adjusted or ignored to allow a full run_).

Ingestion Gate (IG) receives each POST and performs the admission pipeline. It validates required pins by class (`traffic_fraud`, `context_arrival`, `context_arrival_entities`, `context_flow_fraud`) as defined in `config/platform/ig/class_map_v0.yaml`, applies schema policy, and resolves the canonical `event_class` (aligned to `class_map_v0.yaml` and stable across topic/version changes). IG computes the dedupe tuple **`(platform_run_id, event_class, event_id)`** and persists `payload_hash` for anomaly detection (`eb_topic` is recorded as metadata, not part of the dedupe key). If the same dedupe tuple is seen again with the same `payload_hash`, IG logs a DUPLICATE and drops the event; if the dedupe tuple matches but `payload_hash` differs, IG raises an anomaly and quarantines (never silent replace). For new events, IG records an admission row in state `PUBLISH_IN_FLIGHT`, then selects the partitioning profile and stream for the event class (for example, `ig.partitioning.v0.traffic.fraud` routes to `fp.bus.traffic.fraud.v1`; `ig.partitioning.v0.context.arrival_events` routes to `fp.bus.context.arrival_events.v1`; `ig.partitioning.v0.context.arrival_entities` routes to `fp.bus.context.arrival_entities.v1`; `ig.partitioning.v0.context.flow_anchor.fraud` routes to `fp.bus.context.flow_anchor.fraud.v1`). The partition key is computed from the `key_precedence` rules in `config/platform/ig/partitioning_profiles_v0.yaml` (v0 claim: context locality is by `merchant_id`; `arrival_seq` participates in JoinFrameKey downstream, not partitioning). IG publishes to LocalStack Kinesis and updates the admission row to `ADMITTED` with `eb_ref` on success; on timeout/unknown publish outcome it records `PUBLISH_AMBIGUOUS` and does not blindly re-publish without reconciliation. IG writes an admission receipt JSON into MinIO under `s3://fraud-platform/{platform_run_id}/ig/receipts/` for ADMIT/DUPLICATE/QUARANTINE. ADMIT receipts are written after publish success and include `platform_run_id`, `scenario_run_id`, `event_class`, `payload_hash`, `admitted_at_utc`, and `eb_ref`; if receipt writing fails after publish, IG preserves `eb_ref + payload_hash` in the admission DB and marks `receipt_write_failed` for backfill so EB evidence is not lost.

Event Bus (EB) in local parity is Kinesis. For this run, four EB topics carry the admitted stream: `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, and `fp.bus.context.flow_anchor.fraud.v1`. Because the delivery model is at-least-once, a small number of early retries occurred; IG detected these as duplicates (same dedupe tuple `(platform_run_id, event_class, event_id)` re-sent shortly after) and dropped them. As a result, EB admitted counts reflect unique events, not raw WSP sends. In this run WSP emitted `200` per output, while EB admitted `194` (traffic), `191` (arrival_events), `193` (arrival_entities), and `196` (flow_anchor). This is expected: IG de-duplication protects the EB from replays so downstream consumers see one canonical copy per dedupe tuple.

Operationally, IG health remained AMBER with `BUS_HEALTH_UNKNOWN` during the run, yet admission and publishing proceeded without interruption. The flow observed in logs is continuous and concurrent: WSP outputs start together, events stream into IG in parallel, and EB receives the four topics without sequential gating between streams. At the end of the run, WSP stops each output after its `200`-event cap, while IG completes any in-flight admissions and final receipts/backfill markers.

This is the implemented Control and Ingress posture that RTDL will consume: SR provides run facts plus an idempotent READY signal carrying both `platform_run_id` and `scenario_run_id`; WSP produces traffic and context streams concurrently with deterministic `event_id`s and bounded retries; IG validates, deduplicates using `(platform_run_id, event_class, event_id)` with `payload_hash` anomaly detection, routes by partitioning profile, and preserves EB evidence even under receipt/write faults; and EB provides the four admitted topics with deterministic keys derived from IG partitioning profiles. Context topics are merchant-local by partitioning, while traffic does not carry `(merchant_id, arrival_seq)` yet, so RTDL resolves joins via its FlowBinding bridge until traffic is enriched.

## Planned RTDL Flow (from EB topics, local-parity upstream)

The RTDL plane begins where Control & Ingress ends: the Event Bus holds four admitted topics for a fraud-mode run — `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, and `fp.bus.context.flow_anchor.fraud.v1`. RTDL treats the bus as the sole source of truth for **admitted online events**, and it does so under at-least-once delivery with run-scoped pins. Each consumer group maintains its own per-partition checkpoints, never mutates the bus, and only advances offsets once its downstream side effects are safely committed.

Durability is not assumed to be “only the bus.” The Event Bus is a durable log, but retention is finite and replay windows are bounded. RTDL therefore plans for **explicit archival surfaces**: an **event archive writer** that copies admitted EB events (plus origin_offset metadata and `ContextPins`) into object storage for long-horizon replay, and a **decision/audit store** that writes its own append-only records and payload references into object storage as the authoritative history of decisions and outcomes. This avoids the failure mode where an event ages out of EB retention and becomes unrecoverable. For online processing, EB origin offsets are the evidence boundary; for replay, archive-stored origin offsets and payloads are the evidence boundary. Any mismatch is an audit anomaly and replay fails closed. In local parity this is still a planned capability, but it is treated as necessary for production RTDL, where replay, audit, and training depend on immutable records beyond the bus retention window.

RTDL also depends on **stateful stores** that are distinct from the EB itself: a Context Store for join frames, an Online Feature Store for low-latency aggregates, and (optionally) a Graph projection store. These stores do not replace the EB; they are derived, idempotent projections that can be rebuilt from the archived events when necessary. The key architectural rule is that **the durable truth lives in the bus + archive**, while RTDL state stores are rebuildable and versioned by EB offsets.

At the intake edge, RTDL runs a **bus inlet** per topic. The inlet validates the canonical envelope, enforces `ContextPins` (`platform_run_id`, `scenario_run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`; `seed` is required for synthetic runs and optional otherwise), and re-checks basic schema invariants. The inlet also maintains **idempotency guards** keyed by `(platform_run_id, event_class, event_id)` and persists `payload_hash` so replays do not double-apply state and collisions are flagged as audit anomalies. The `eb_topic` is recorded as metadata for audit/replay but is not part of the dedupe key. Every event that passes inlet checks is stamped with the EB **origin_offset** metadata (stream, partition, sequence) and handed to the appropriate RTDL sub-plane.

Three of the four topics are **context streams**, and they are always treated as **state builders**, not decision triggers. The arrival event stream (`arrival_events_5B`) establishes the “skeleton” of a flow: the arrival sequence, event time, merchant identity, and any canonical IDs from the payload. Each arrival event opens or updates a join frame in the **Context Store**, keyed by `(platform_run_id, merchant_id, arrival_seq)`. The arrival entity stream (`s1_arrival_entities_6B`) attaches entity references to that frame (`party_id`, `account_id`, `instrument_id`, `device_id`, IP, etc.). The flow anchor stream (`s3_flow_anchor_with_fraud_6B`) provides the binding from arrival sequence to a `flow_id` and cements the ordering context; the Context Store uses it to complete the frame and mark it “join-ready.” These context updates are append-only, idempotent, and safe under replay because they are keyed by a stable `event_id` and pinned to run scope.

Because traffic does not include `(merchant_id, arrival_seq)`, RTDL maintains a **FlowBinding Index** that maps `flow_id -> (platform_run_id, merchant_id, arrival_seq)` and is run-scoped by `platform_run_id` (lookups are effectively `(platform_run_id, flow_id)`). Only flow_anchor is allowed to create/update bindings. If a different binding appears for the same `(platform_run_id, flow_id)`, RTDL emits an audit anomaly and quarantines the event. FlowBinding writes are atomic with JoinFrame updates; only after both are committed (WAL flushed) does the flow_anchor checkpoint advance.

The traffic stream (`s3_event_stream_with_fraud_6B`) is the **decision trigger**. For each traffic event, RTDL resolves its join context by first looking up the FlowBinding Index with `(platform_run_id, flow_id)`, then fetching the JoinFrame by `(platform_run_id, merchant_id, arrival_seq)`. If the join frame is complete, the event advances immediately. If it is incomplete, RTDL does not guess: it either (a) waits in a bounded **join-wait buffer** for up to `join_wait_budget_ms` (600-900 ms, always <= `decision_deadline_ms=1500`) or (b) escalates to a **degrade policy** that explicitly records missing context as either `context_missing: flow_binding_missing` or `context_missing: join_frame_incomplete`, and produces a safe, explainable action (for example, STEP-UP or QUEUE). In all cases, the decision record preserves the evidence: which context pieces were present, which were missing, and the **origin_offset** values that define the evidence boundary.

In parallel, two RTDL support planes are hydrated **from the same EB**:

1. **Identity & Entity Graph (IEG)** consumes EB context and traffic to project a run-scoped graph view (entities, edges, identifiers). It provides stable, read-only graph queries to the decision fabric. `graph_version` is derived from EB offsets, so any decision can be replayed against the same graph state.

2. **Online Feature Plane (OFP)** consumes EB streams and updates low-latency feature aggregates (counts, windows, last-seen timestamps, distincts) keyed by `ContextPins` + entity keys. OFP does not attempt to interpret decisions; it only maintains memory that can be deterministically recomputed from the bus.

Once a traffic event is join-ready, the **Decision Fabric** executes its stages. Guardrails run first (cheap, deterministic checks), followed by primary model scoring, with optional second-stage enrichment if latency permits. The fabric uses: (a) the joined context frame, (b) OFP features, and (c) IEG queries. It produces a decision package containing the action, reasons, model/policy versions, and a feature snapshot hash. That decision package is written to the **Decision Log & Audit Store (DLA)** as an append-only record tied to EB **origin_offset** values (traffic + flow_anchor + arrival events/entities used), preserving full provenance for replay.

The **Actions Layer** consumes decision packages and applies idempotent side effects (approve, step-up, decline, queue). Each action is keyed by a stable `decision_id` (derived from `event_id + bundle_ref + traffic origin_offset` — i.e., the `origin_offset` of the traffic evidence event) so that retries do not duplicate external effects. Outcomes (success/failure, error codes, timestamps) are recorded as action result events and/or appended back into the audit stream for later labeling and learning.

Throughout the RTDL plane, **availability and correctness are bounded by the EB evidence**. Duplicates arriving at EB do not cause double processing because RTDL applies idempotency at the inlet and in each state updater. If a duplicate is a true replay, RTDL’s state remains unchanged. If an `event_id` collision were to occur (same `event_id`, different payload), RTDL detects a payload hash mismatch and emits an audit anomaly; the policy response is to quarantine or degrade rather than silently proceed.

The net effect is a deterministic, replayable decision loop: context events build join state, traffic events trigger decisions, decisions produce actions, and every step is pinned to EB offsets and `ContextPins` so the system can be replayed or audited end-to-end. This planned flow is the direct continuation of the local-parity Control & Ingress posture and establishes the exact upstream contract RTDL must honor before we finalize its detailed design.

## Planned Case + Labels Flow (human truth loop)

The Case + Labels plane begins once RTDL has produced **decisions** and the Actions Layer (AL) has produced **immutable outcomes**. The authoritative evidence inputs are **DLA audit records**, **AL outcome records**, and the EB **origin_offset evidence basis**—carried **by reference**, not copied payloads. Every item entering this plane remains pinned to ContextPins, including `platform_run_id` and `scenario_run_id`, so downstream truth never leaks across runs.

A thin **CaseTrigger writer** (or RTDL/AL directly) emits explicit `CaseTrigger` events for review-worthy situations: `DECISION_ESCALATION`, `ACTION_FAILURE`, `ANOMALY`, `EXTERNAL_SIGNAL`, or `MANUAL_ASSERTION`. Each CaseTrigger carries ContextPins, a canonical **CaseSubjectKey** of `(platform_run_id, event_class, event_id)`, plus evidence refs such as `decision_id`, `action_outcome_id`, and `audit_record_id`. The trigger is idempotent under at-least-once delivery: `case_id = hash(CaseSubjectKey)` and `case_trigger_id = hash(case_id + trigger_type + source_ref_id)` ensure duplicates attach cleanly without creating duplicate cases.

**Case Management (CM)** consumes CaseTriggers and builds the **case timeline** as the primary case truth object. A case is created once per `case_id` (no merges in v0), and everything thereafter is **append-only timeline events**. Timeline appends are idempotent: each timeline event uses a stable key `(case_id, timeline_event_type, source_ref_id)` and a deterministic `case_timeline_event_id = hash(case_id + timeline_event_type + source_ref_id)`. If a duplicate arrives, CM no-ops; if the same key arrives with different content, CM flags an **anomaly** rather than silently overwriting. CM stores **refs + minimal metadata only**; it does not become a second evidence store and does not reinterpret upstream payload truth.

Investigators work inside CM and **append assertions** (e.g., “confirmed fraud”, “confirmed legitimate”, “needs follow-up”) as new timeline events with explicit `actor_id`, `source_type=HUMAN`, and `observed_time`. Corrections are new assertions—no destructive edits. CM may support assignment/ownership as timeline-derived state, but v0 remains lock-free: concurrent edits are naturally represented as ordered, append-only events.

When a human workflow requires an operational side effect (block, release, notify, queue), CM does not execute it directly. Instead, it emits an **ActionIntent** to AL with ContextPins, subject identifiers, reasons, and evidence refs, using an idempotency key such as `hash(case_id + source_case_event_id + intent_type + subject_key)`. AL executes the intent idempotently and produces an immutable outcome; CM later attaches the resulting `action_outcome_id` to the timeline **by reference**, closing the loop without CM owning side effects.

Label truth is emitted through the **Label Store (LS)**, not inside CM. When an investigation yields a label, CM creates a **LabelAssertion** whose subject is execution-scoped: **LabelSubjectKey = `(platform_run_id, event_id)`**, where `event_id` is the **traffic/decision-trigger** event (not context event ids). The assertion includes `label_type` (v0 controlled vocabulary such as `fraud_disposition`, `chargeback_status`, `account_takeover`), `label_value`, and both **effective_time** (when it was true) and **observed_time** (when it was learned). The assertion id is stable across retries: `label_assertion_id` is derived from `case_timeline_event_id + LabelSubjectKey + label_type`, and `observed_time` is fixed at first creation.

LS owns its own **writer boundary** (IG-equivalent ingress). CM submits the LabelAssertion to LS and records `LABEL_PENDING` on the case timeline. LS enforces idempotency and integrity at the boundary using the dedupe tuple `(LabelSubjectKey, label_type, label_assertion_id)` plus `payload_hash` anomaly detection (same tuple + different hash ⇒ **ANOMALY**). For hashing, LS uses a canonical field set (subject, type, value, effective/observed time, source_type, actor_id if HUMAN, evidence refs) and a canonical ordering of `evidence_refs` (sorted by `(ref_type, ref_id)`). Only after LS durably commits the append (WAL-flushed) does it return an ack/ref; CM then appends `LABEL_ACCEPTED` (or `LABEL_REJECTED`) to the case timeline. If LS is unavailable, CM remains pending and retries idempotently; CM never claims label truth until LS ack succeeds.

LS maintains **append-only label timelines** and provides a resolved view per `(LabelSubjectKey, label_type)` using explicit precedence rules (human > external feed > automated, then observed_time, then assertion_id). Late-arriving truth (e.g., chargebacks weeks later) is accepted as new assertions with preserved effective vs observed time, so historical “what did we know then?” views remain reconstructible.

External truth signals (chargebacks, disputes, confirmed fraud feeds) enter v0 through the **CM workflow first**, then become LabelAssertions under the same contract. A future direct external ingest can write to LS, but must follow the same idempotency and provenance rules.

This closes the human truth loop cleanly: **RTDL evidence → CaseTriggers → CM timelines → LabelAssertions → Label Store timelines → training consumption**, with run-scoped pins, append-only history, and explicit commit/ack semantics preventing leakage or silent reinterpretation.

## Planned Learning + Evolution Flow (offline model loop) — pinned, reproducible, and auditable

The Learning + Evolution plane begins once the platform has two durable truths it can trust without interpretation: **admitted event history** (Archive as the long-horizon truth; EB as a retention-bounded accelerator) and **label truth timelines** (Label Store, preserving effective_time vs observed_time). This plane does not create new truth. It deterministically **replays**, **rebuilds**, **evaluates**, and **packages** learning artifacts from pinned inputs, using the same integrity rails as upstream: ContextPins everywhere, by-ref inputs, no-PASS-no-read, immutable outputs, and explicit audit evidence.

### OFS enters on intent, not “always on”

The entry vertex is the **Offline Feature Shadow (OFS)**, which runs only when a build intent exists—scheduled or on-demand. A build intent names *what you want to produce* (training dataset, diagnostic dataset, parity rebuild, or evaluation-only dataset), and it must be pinned enough to be reproducible.

OFS resolves its inputs strictly:

* **Replay basis** is defined as **origin_offset ranges per topic/partition**, canonicalized as `{topic/stream, partition/shard_id, sequence_number}`. This is the authoritative basis of replay.
* Time windows are allowed only as **selectors**: OFS may accept “between time A and time B,” but it immediately translates that into concrete origin_offset ranges and records the resolved offsets in the DatasetManifest. Time alone never remains the truth anchor.
* **Archive is the durable truth beyond EB retention.** EB may accelerate reads only when the exact same origin_offset ranges are available. If any part of the replay basis falls outside EB retention, OFS reads that portion from Archive. EB is never required for correctness.
* OFS replays events in **partition order**, and the DatasetManifest records the full replay basis for each stream: topic, partition, start_offset, end_offset.

Because the replay basis is pinned to the evidence tuple, OFS can detect drift. If EB and Archive disagree for the same `{topic, partition, sequence_number}` (defined as a `payload_hash` mismatch for that tuple), OFS **fails closed** and emits an anomaly report—no dataset is produced.

### Labels are joined “as-of” to prevent future leakage

Labels enter OFS through the Label Store, but only through an explicit **as-of boundary**. OFS reads resolved labels using the rule:

* **Eligible labels satisfy `observed_time <= label_asof_utc`**, always.

This preserves “what was known then.” Late truths (chargebacks weeks later) are allowed in principle, but only if they were observed by the as-of cutoff for the dataset being built. “Unknown yet” negatives are treated as **unlabeled/censored** by default. Weak negatives are allowed only if a **maturity policy** is explicitly declared and recorded (e.g., `label_maturity_days`, and any other label completeness rule). OFS records label coverage in the manifest; training-intent datasets fail closed if coverage is insufficient, while diagnostic datasets may proceed if explicitly marked non-training.

### OFS builds are scoped and deterministic

OFS builds datasets around a pinned **join/entity scope**. In v0, the primary subject is transaction-level and execution-scoped:

* **SubjectKey = `(platform_run_id, event_id)`** to align with LabelSubjectKey and prevent cross-run leakage.

OFS joins only what it can justify from the replay basis and pinned surfaces:

* Context JoinFrames (arrival events/entities + flow anchor) and FlowBinding are allowed, as long as their evidence offsets are within the same replay basis.
* IEG projection is allowed only if it is built from the same replay basis (no mixing derived state from different evidence windows).
* Any world/scenario context is fetched only through SR’s `run_facts_view` locators with PASS evidence—never by scanning “latest.”

If required context is missing, OFS defaults to **dropping the example** for training builds, and records drop counts and reasons. A degraded cohort is allowed only when explicitly pinned and consistent with online degrade behavior (so offline doesn’t “invent” a different completeness policy than RTDL).

### DatasetManifest is the contract, and the fingerprint is the identity

Every OFS build produces:

1. materialized artifacts under `ofs/...`, and
2. a **DatasetManifest** that is the dataset’s identity contract.

The DatasetManifest pins the replay basis (origin_offset ranges), label_asof_utc and label resolution rule, join scope and join sources, feature definition set versions, cohort filters, and build profile/config revisions. From these, OFS computes a deterministic **DatasetFingerprint**. Any change to any identity field yields a **new fingerprint and a new manifest**; manifests are immutable and never mutated.

To preserve reproducibility across code upgrades, OFS and MF also record their code identity:

* `ofs_code_release_id` and `mf_code_release_id` (git SHA or container image digest/tag)

These are provenance anchors that explain why two runs may differ even if the underlying truth inputs are the same.

### Feature definitions are shared, and parity is explicit

OFS does not invent feature definitions. It loads a **version-locked feature definition set** from the same shared authority that Online Feature Plane uses. “Latest” is allowed only if explicitly requested and recorded; otherwise, builds are version-pinned.

Parity checks are optional and explicit. If a build intent requests parity, OFS anchors to online provenance (e.g., a feature snapshot hash plus its evidence basis) and produces a parity evidence artifact:

* `MATCH`, `MISMATCH`, or `UNCHECKABLE`, with refs and basis

In v0, parity compares feature snapshot hashes and a minimal set of key feature values. Deterministic features must match exactly; tolerances are allowed only when explicitly declared in the feature definition. For training builds, mismatches are warnings by default; for parity rebuild intents, mismatches fail the run unless explicitly overridden.

### MF trains only from manifests, and evidence gates publishing

The **Model Factory (MF)** is job-driven. It consumes OFS outputs by **DatasetManifest reference only** and refuses “latest dataset” or unpinned inputs. A training intent must provide:

* DatasetManifest refs
* training config/profile revisions
* required gates to run

MF produces a training run record and a full, immutable **EvalReport** that is reproducible from the DatasetManifest + training config refs. PASS gates include compatibility (schema/feature sets), leakage discipline (label_asof enforcement), and explicit thresholded performance checks per bundle slot.

MF must **refuse to publish** a bundle if the required EvalReport or provenance/evidence references are missing. No evidence means no bundle.

### Bundles are immutable, and MPR is the only activation authority

When gates PASS, MF packages a candidate **bundle** that includes model artifact(s), feature schema/version requirements, thresholds/policy config, required capabilities, and full provenance:

* training manifests + eval evidence refs + `ofs_code_release_id` + `mf_code_release_id`

The **Model/Policy Registry (MPR)** is the controlled source of deployable truth. It ingests bundles, enforces immutability (`bundle_id + version` is the unit of truth), and records lifecycle events for approve/promote/rollback/retire as append-only registry events.

Activation is scoped and deterministic. In v0, the ScopeKey is:

* `{ environment, mode, bundle_slot, tenant_id? }` (tenant optional), exactly one ACTIVE per scope

Decision Fabric resolves bundles deterministically through MPR, using a deterministic resolution order:

* tenant-specific ACTIVE → global ACTIVE → explicit safe fallback (if defined) → fail closed

At resolve time, MPR enforces compatibility: feature_def_set match, required capabilities vs degrade mask, and input contract version match. If no compatible ACTIVE exists, resolution fails closed (or routes only to an explicitly defined safe fallback), and the decision record must capture the failure.

### Operability stays pinned: anomalies, sampling, maturity, caching, and multi-run scope

This plane remains operable without drifting:

* Data quality issues (missing partitions, corrupted chunks, schema mismatches, offset gaps) fail closed for training builds; diagnostic builds may proceed only if explicitly tagged incomplete. All such issues produce a replay anomaly report referenced by the DatasetManifest.
* Sampling (downsample/upsample/stratify) is allowed only when the sampling rule and seed are pinned in the manifest; no implicit sampling.
* Mature-window training is controlled by `label_maturity_days` recorded in the manifest. Delayed-label EvalReports (T+7d, T+30d) can be generated as requested and stored as evidence variants.
* Caching is allowed only if cache keys include replay basis + feature_def_set + join scope; caches invalidate on identity change and are never treated as truth.
* Datasets are scoped to one `platform_run_id` by default. Multi-run datasets are allowed only if the manifest explicitly lists all runs, and subject keys keep run_id to prevent leakage.

This closes the loop without breaking upstream guarantees: **pinned admitted events + pinned label timelines → deterministic offline reconstruction → manifested datasets → reproducible training and evaluation → immutable bundles → governed activation**, with explicit audit evidence at every step so the offline loop evolves without introducing drift into the real-time plane.

## Planned Observability + Governance Narrative (meta layer)

Observability + Governance sits *around* the four planes and treats them as producers of **minimal, run-scoped facts** and **immutable evidence refs**. In v0, it is deliberately light on hot-path work: the platform does not “log everything,” it logs **just enough** to (a) operate safely, (b) reconcile runs, and (c) prove governance actions happened.

As runs execute, every plane emits the same core pins on anything that matters: `platform_run_id`, `scenario_run_id`, `environment`, `mode`, plus `manifest_fingerprint`, `parameter_hash`, `scenario_id`, and `policy_rev`/`run_config_digest` when policy/config is relevant. This prevents cross-run mixing and lets ops slice metrics cheaply without joining payloads.

Most observability in v0 is **counters** (periodic flush) rather than per-event logs. Control & Ingress increments sent/received/admitted/duplicate/quarantine/ambiguous counters; RTDL increments inlet seen/deduped, join-wait, degrade reasons, decisions emitted, and action outcomes; Case/Labels increments triggers/cases/timeline appends/labels pending vs accepted; Learning increments datasets built, eval pass/fail, bundles published, and promotions/rollbacks. Deep truth lives elsewhere already (receipts, DLA, archive, label timelines), so the meta layer avoids duplicating that work.

Governance is handled as a **low-volume append-only fact stream**. Only actions that change platform state (bundle promotion/rollback, label accept/reject, policy_rev changes, run lifecycle transitions) are written as structured governance facts. These facts are idempotent under retries, always attributed (`actor_id`, `source_type=HUMAN|SYSTEM`), and always include evidence refs (e.g., EvalReport ref, DatasetManifest fingerprint, decision_id, label_assertion_id). This keeps auditability without adding load to the event hot path.

“Corridor checks” enforce policy at a small number of choke points: IG, DLA append, AL side effects, LS writer boundary, and MPR activation/promotion. In v0 these checks emit **nothing on success** beyond counters; on failure they emit a single anomaly/governance event plus a by-ref evidence pointer. The system fails closed on unsafe governance actions, and degrades only through explicit degrade policy—never through silent skipping.

Finally, the meta layer provides cheap, periodic **run reconciliation**: a small writer/job produces one JSON summary per run/day under the run’s object-store prefix, combining the required counters and referencing key evidence IDs. Reconciliation is not computed continuously; it’s produced out of band so it never slows down SR→WSP→IG→EB or RTDL decisioning.

## Planned Run/Operate / Substrate Narrative (meta layer)

Run/Operate / Substrate is the mechanism layer that makes the pinned policies real: **how services run**, **how they authenticate**, **how configs and secrets are injected**, **how jobs execute**, and **how promotions happen safely**. It aligns all environments to the same contract while allowing scale and security to harden as you move from local to prod.

The environment ladder is explicit: `local_parity → dev → prod`. Parity means the same schema contracts, envelope pins, dedupe keys, manifest/receipt layouts, and registry resolution semantics everywhere. What changes across environments is capacity (shards/DB sizing), retention windows, and auth strength—without changing meaning.

Service identity is uniform per environment. In `local_parity`, writer boundaries (IG ingest, LS writer, MPR governance endpoints) can accept an API key allowlist. In `dev/prod`, the same boundaries require stronger service identity (mTLS or signed service tokens), and every write is attributed (`SYSTEM::<service>` or `HUMAN::<id>`). Substrate enforces that identity; Obs/Gov defines what must be recorded.

Configuration is treated as **pinned evidence**, not “whatever the repo currently says.” Services can load wiring config at startup, but anything run-scoped must stamp digests into evidence artifacts: IG receipts include `policy_rev`, RTDL decisions include bundle/policy refs, LS acks include label vocabulary version, OFS/MF manifests include feature_def_set versions and code release IDs. Mid-run config changes are allowed only as explicit `policy_rev` boundaries—no silent drift.

Deployments are immutable. Services run from immutable artifacts (e.g., container images), and every evidence surface carries a `service_release_id` so you can reproduce behavior. Offline jobs (OFS, MF, reconcilers) run as explicit jobs triggered by pinned intents; no “always-on” expensive compute is allowed to creep into v0.

Storage is provisioned by role, not convenience: object store holds receipts/quarantines, archives, DLA evidence, manifests, eval reports, bundles, and reconciliation summaries; databases hold idempotency/state (IG admission DB, RTDL stores, CM/LS timelines, MPR registry state). Retention is environment-specific, but substrate must not violate rebuild guarantees: if Archive + Label timelines are retained, OFS can rebuild any dataset referenced by a manifest even if materialized datasets expire.

Promotion mechanics are enforced at the substrate boundary where they matter most: MPR promotion endpoints require authenticated governance actors, evidence refs must be present, and activation updates are append-only registry events. Decision Fabric always resolves ACTIVE bundles deterministically through MPR using the pinned ScopeKey `{environment, mode, bundle_slot, tenant_id?}`, and it fails closed unless an explicit safe fallback exists.

Finally, evidence ref resolution is implemented as a secure mechanism (short-lived signed access or service-gated fetch). The substrate enforces access; the Obs/Gov layer defines the minimal audit record. The platform never logs payload contents for ref access—only who/what/when/purpose—keeping the system safe without slowing it down.
