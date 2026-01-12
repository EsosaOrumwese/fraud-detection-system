# Conceptual Document Plan — Event Bus / Stream Plane (EB)

## 0) Document metadata

### 0.1 Document header

* **Title:** *Event Bus / Stream Plane — Conceptual Roadmap (Modular Breakdown + Contract Intent)*
* **Component/Plane:** Real-Time Decision Loop / Event Bus / Stream Plane
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final (choose one)
* **Version:** v0.x (increment on substantive changes)
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Provide a **single, coherent conceptual direction** for the Event Bus / Stream Plane (EB) before writing EB specs and contracts.
* Enumerate the **questions EB must answer** (by module + contract boundary) to guarantee:

  * durable distribution of events (append-only)
  * replayability within retention windows
  * predictable delivery semantics (at-least-once; per-partition ordering)
  * clear authority boundaries (EB transports; it does not validate or transform)
* Explicitly separate:

  * **design decisions that must be pinned** (later in EB1–EB5 and EB contract schema)
  * **implementation freedoms** left to the implementer (tech choice, infra, tuning)

### 0.3 Audience and prerequisites

* **Primary readers:** you (architect/spec author), Codex (implementer)
* **Secondary readers:** owners of IG, Identity, Features, Decision Fabric, Observability
* **Prerequisites (assumed known):**

  * IG outputs “admitted canonical events” (EB’s preferred input source)
  * consumers are responsible for idempotency (duplicates possible)
  * canonical event envelope/payload contracts are *separate* from EB v0 contracts (EB treats event bytes as opaque)

### 0.4 How to use this document

* Use as the **roadmap** for authoring:

  * EB spec set (EB1–EB5), and
  * EB v0 bus-plane contract schema (`eb_public_contracts_v0.schema.json`)
* This doc is **non-binding**; machine-checkable truth lives in `contracts/`.
* Each “question” here must eventually become:

  * a **pinned decision** in EB specs, or
  * a **schema rule/field** in EB contracts, or
  * explicitly declared **implementation freedom**

### 0.5 Non-binding disclaimer

* This document is conceptual and **non-binding**.
* Any normative words (MUST/SHALL/SHOULD) are **directional** until captured in:

  * EB specs (binding sections), and/or
  * EB contract schema (machine validation)

### 0.6 Scope and non-scope

* **In scope:** EB responsibilities, modular breakdown, delivery/replay/ordering/retention posture, bus-plane contract intent, repo layout, spec mapping.
* **Out of scope:** canonical payload schema design, event validation/normalization, feature computation, decisioning logic, label semantics, “exactly-once” guarantees (unless explicitly added later).

### 0.7 Repo placement and related artifacts

* **Proposed location:**
  `docs/model_spec/real-time_decision_loop/event_bus_stream/CONCEPTUAL.md` (or merge into `README.md` later)
* **Related docs (eventual):**

  * `specs/EB1_...` through `specs/EB5_...`
  * `contracts/eb_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why the Event Bus / Stream Plane exists

The Event Bus / Stream Plane (EB) is the platform’s **distribution + durability plane**. Its job is to take events (ideally **post-Ingestion Gate admitted events**) and provide:

* **durable append** (events are stored as an immutable log),
* **replayable delivery** (consumers can re-read within retention),
* **predictable semantics** (at-least-once delivery; ordering only within partitions).

One sentence: **“Append immutably, deliver at-least-once, preserve per-partition ordering, and enable deterministic replay within retention.”**

---

### 1.2 Where EB sits relative to SR and IG

* **Scenario Runner (SR)** anchors the run context and declares readiness.
* **Ingestion Gate (IG)** is the trust boundary that admits canonical, joinable events.
* **EB** transports and persists those admitted events for Real-Time Decision Loop consumers (features, decisioning, actioning, logging, etc.).

**Key boundary rule:** EB is not a validator or transformer. If events need fixing, rejecting, or pin enrichment, that happens before EB (primarily in IG).

---

### 1.3 What EB is system-of-record for

EB is authoritative for:

* the **durable position** of an event in a stream (partition + offset)
* the **replay window** within retention (what can be replayed and how)
* **delivery metadata** (e.g., bus publish time, consumer checkpoints), as part of the transport layer

EB is **not** authoritative for:

* event schema correctness,
* event business meaning,
* run/world truth,
* or feature/decision outputs (it only carries them).

---

### 1.4 What EB explicitly is NOT responsible for (non-scope)

EB does **not**:

* validate schema versions (IG does)
* mutate or normalize event payloads/envelopes
* compute partition keys from domain logic (v0 posture: **require `partition_key`, do not infer it**)
* guarantee exactly-once delivery (v0 posture: at-least-once)
* provide global ordering across all events (unless explicitly promised later)

EB may attach transport metadata (offset, partition, publish time) **outside** the event blob; it must not write it back into the canonical event itself.

---

### 1.5 What EB must enable for loop components

Real-Time Decision Loop components must be able to rely on EB for:

* **stable distribution semantics**

  * duplicates are possible → consumers must be idempotent
* **ordering clarity**

  * ordering guaranteed only within a partition
* **replay support**

  * re-delivery from offset/time within retention (no history rewriting)
* **operational transparency**

  * lag, backlog, retention utilization, errors are observable
* **local vs deployed equivalence**

  * same meaning of publish/deliver/replay, even if mechanics differ

---

## 2) Core invariants (EB “laws”)

> These are **non-negotiable behaviours**. If later EB specs or implementation contradict any of these, it’s a bug.

### 2.1 Immutability: EB does not mutate event content

* EB MUST treat the event (envelope + payload) as **opaque immutable content**.
* EB may attach **transport metadata** (partition, offset, publish time), but it must do so **outside** the event content (e.g., in a DeliveredRecord wrapper).

**Implication:** replay re-delivers the same stored content, not a “normalized” variant.

---

### 2.2 Publish truth: “published” means durably appended + position assigned

* EB MUST NOT acknowledge a publish as successful unless the event is **durably appended** and has a stable position (partition + offset) assigned.
* EB must not “accept into memory” and call it published.

---

### 2.3 Delivery posture: at-least-once

* EB delivers events with **at-least-once** semantics:

  * duplicates can occur,
  * redelivery can occur after consumer failures or retries.
* Consumers MUST assume duplicates are possible and enforce idempotency at their boundaries.

---

### 2.4 Ordering scope: within partition only

* EB guarantees ordering **only within a partition**.
* EB does not guarantee global ordering across partitions unless explicitly pinned later.

---

### 2.5 Replay semantics: replay re-delivers stored events

* Replay means re-delivering stored events from a specified offset/time range.
* Replay does not recompute events and does not rewrite history.
* Replayed events must remain identifiable as the same logical events (via stable event identity carried in the event content).

---

### 2.6 Partition key posture (v0): required but composition deferred

* EB requires a **single explicit `partition_key`** for published events.
* EB MUST NOT infer or compute partition_key from domain logic in v0.
* The composition/mapping of partition_key (e.g., account_id vs merchant_id) is explicitly deferred until Identity + Features are pinned.

---

### 2.7 Retention is explicit and enforceable

* EB must have an explicit retention posture (time/size/window concept).
* Beyond retention, replay/backfill is not guaranteed.

---

### 2.8 No silent drop under overload

* Under overload/backpressure, EB must follow an explicit posture (buffer/fail/shed-load) and must surface it via observable signals/metrics/errors.
* EB must not silently drop events.

---

### 2.9 Local vs deployed semantics must match

* EB may run locally (dev) or deployed (prod), but the meaning of:

  * publish acknowledgment,
  * per-partition ordering,
  * replay semantics,
  * and retention rules
    must remain consistent. Differences are only mechanical (transport, storage engine, throughput).

---

## 3) Terminology and key objects

> These are the nouns used throughout the EB conceptual roadmap. Shapes are conceptual here; exact fields land in EB2–EB5 and the EB contract schema.

### 3.1 Stream (topic)

A **stream** is a named append-only sequence of events. Streams may be implemented as topics/logs/queues, but the conceptual meaning is consistent: producers append, consumers read.

---

### 3.2 Partition

A **partition** is a subdivision of a stream that provides a scoped ordering guarantee. Each stream has one or more partitions.

**Key idea:** ordering is guaranteed only within a partition.

---

### 3.3 Offset (position)

An **offset** is the immutable position of an event within a specific partition. Offsets are assigned at publish time.

**Key idea:** offsets are stable identifiers for replay (“start from offset X”).

---

### 3.4 Publish

**Publish** is the act of appending an event to a stream such that:

* it becomes durably stored, and
* is assigned a partition + offset.

---

### 3.5 Durable append

A **durable append** means the event content is persisted such that:

* it survives process crashes/restarts, and
* can be replayed within retention.

The exact durability mechanism is implementation-specific, but EB must not claim durability if it cannot provide it.

---

### 3.6 Delivery

**Delivery** is the act of making published events available to consumers. Under at-least-once semantics, the same event may be delivered more than once.

---

### 3.7 Consumer group / subscription

A **consumer group** (or subscription) is a logical consumer identity that reads from a stream and tracks progress independently. The specific mechanics (leases/heartbeats) are implementation details.

---

### 3.8 Checkpoint (consumer progress)

A **checkpoint** records how far a consumer has progressed, typically expressed as:

* `{stream_name, partition_id, offset}`

Checkpoint `offset` is the next offset to read (exclusive) and is the authoritative progress token for replay/rewind semantics. Checkpoints can be stored by the bus, by the consumer, or by a coordination store-this is a design choice pinned later.

---

### 3.9 Consumer lag

**Lag** is the gap between:

* the latest published offsets, and
* a consumer’s checkpoint offset,
  per partition.

Lag is a key ops signal.

---

### 3.10 Partition key (`partition_key`)

The **partition key** is a required field supplied at publish time that determines partition routing.

* In v0, EB requires `partition_key` but does not define its composition.
* It must be stable, deterministic, and present on every published event.

---

### 3.11 Replay / backfill

**Replay** (or backfill) is re-reading events from:

* a given offset, or
* a time window (if time-indexed replay is supported),
  within retention.

Replay re-delivers the same stored event content; it does not rewrite history.

If `partition_id` is omitted, replay applies to all partitions in the stream; no cross-partition ordering is implied.

---

### 3.12 Retention

**Retention** is the policy that limits how long/how much data the bus stores. Retention may be time-based, size-based, or both. Once expired, events may not be replayable.

---

### 3.13 Compaction (v0 default: not used)

**Compaction** refers to rewriting log storage by collapsing records (often key-based). In v0, the default posture is **no compaction** unless explicitly chosen, because compaction can violate simple “append-only replay” mental models.

---

### 3.14 Event content vs bus metadata

* **Event content**: the canonical envelope + payload (opaque to EB in v0).
* **Bus metadata**: delivery-specific fields such as partition, offset, publish time, consumer group, etc.

**Key rule:** EB must not inject bus metadata into event content.

---

### 3.15 `published_at_utc` (bus time)

`published_at_utc` is the timestamp when the event became durably appended and the position `{partition_id, offset}` was assigned.

---

### 3.16 `kind` (contract object type)

* `kind` values are lower_snake_case.
* v0 allowed set: `publish_record`, `publish_ack`, `delivered_record`, `consumer_checkpoint`, `replay_request`.

---

## 4) EB as a black box (inputs → outputs)

> This section treats the Event Bus / Stream Plane (EB) as a single black box: what it **accepts**, what it **produces**, and what boundaries it touches. Shapes are conceptual here; EB contracts pin bus-plane objects only (not canonical payload schemas).

### 4.1 Inputs (what EB consumes)

#### 4.1.1 Primary input: events to publish

EB accepts events from producers, ideally **post-IG admitted events**.

At v0, EB treats event content as **opaque**:

* EB does not validate the canonical envelope/payload
* EB does not normalize or transform the content

#### 4.1.2 Required publish metadata (conceptual)

Each publish operation must supply at least:

* `stream_name`
* `partition_key` (required; composition deferred)
* `event_bytes_b64` (base64 of immutable canonical event bytes; required in v0)

**Boundary rule:** EB requires `partition_key`; it does not compute it.

---

### 4.2 Outputs (what EB produces)

#### 4.2.1 Publish acknowledgments (producer-facing)

EB returns a PublishAck after a successful durable append, including the assigned position:

* `kind`
* `stream_name`
* `partition_id`
* `offset`
* `published_at_utc`
* `contract_version`

#### 4.2.2 Durable log of events

EB stores events as an append-only log:

* immutable event content
* durable positions (partition + offset)

#### 4.2.3 Delivered records to subscribers

When consumers read, EB provides delivery metadata alongside the event content, conceptually as a DeliveredRecord:

* `partition_id`
* `offset`
* `published_at_utc` (timestamp when durable append + position assignment completed)
* event content (`event_bytes_b64`, same bytes stored)

#### 4.2.4 Consumer progress / checkpointing (conceptual)

EB supports consumer progress tracking via a checkpoint concept:

* consumer group/subscription identity
* per-partition offset progress

Checkpoint `offset` is the next offset to read (exclusive). Regardless of ownership, a checkpoint is the authoritative progress token for replay/rewind semantics. Whether checkpoints are persisted by EB or by consumers is a design decision pinned later; the conceptual model assumes checkpointing exists.

#### 4.2.5 Telemetry and governance signals

EB exposes operational information:

* publish rates
* consumer lag
* retention utilization
* error rates / redelivery indicators (where measurable)
* access audit signals (publisher/subscriber identity)

---

### 4.3 Boundary map (what EB touches)

#### 4.3.1 Producers (publishers)

* primary publisher is usually IG (admitted events)
* other platform components may publish (actions, decisions, labels), but EB does not validate their meaning

#### 4.3.2 Consumers (subscribers)

* online features
* decision fabric
* actioning
* decision log/audit
* observability tooling
  Consumers must be idempotent and must not assume global ordering.

#### 4.3.3 Storage substrate (implementation detail)

EB relies on some durable storage substrate (log store). The choice is implementation freedom, but the semantic guarantees are not.

#### 4.3.4 Ops/security control plane (conceptual)

EB must support:

* minimal access control (who can publish/subscribe)
* minimal audit fields for operations
* explicit overload/backpressure posture

---

## 5) Modular breakdown (Level 1) and what each module must answer

> This is a **distribution + durability plane**, not a logic plane. The modular breakdown exists to force EB’s semantics (delivery, ordering, replay, retention, overload) to be answered *somewhere*, while leaving technology and infra choices to the implementer.

### 5.0 Module map (one screen)

EB is decomposed into 6 conceptual modules:

1. **Publish surface**
2. **Partitioning / routing**
3. **Durable log store**
4. **Subscribe / delivery surface**
5. **Replay / backfill**
6. **Ops / governance surface**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 5.1 Module 1 — Publish surface

### Purpose

Accept publish requests and append events durably with a stable position assigned.

### What it owns

* publish acknowledgment semantics (“published” meaning)
* required publish fields (`stream_name`, `partition_key`, `event_bytes_b64`)
* rejection/error conditions (conceptual)

### Questions this module must answer

* What does a successful publish ACK guarantee?

  * durable append completed?
  * partition + offset assigned?
* What fields are required at publish time?
* What happens if required fields are missing (reject vs route to error)?
* Does EB accept batches (optional) and, if so, what are per-record semantics?
* Does EB assign a publish time (`published_at_utc`, timestamp of durable append + position assignment) and where does it live? (bus metadata, not event content)

### Can be left to the implementer

* transport mechanism (Kafka API, HTTP, gRPC, etc.)
* batching and throughput tuning
* auth mechanism details (beyond minimal posture)

### Local vs deployed operation

* **Local:** often in-process or lightweight broker; semantics must still hold (ACK means durable within the chosen substrate)
* **Deployed:** distributed durable substrate; semantics unchanged

### Conceptual inputs → outputs

* **Input:** PublishRecord (`event_bytes_b64` + metadata)
* **Output:** PublishAck (stream_name, partition_id, offset, published_at_utc)

---

## 5.2 Module 2 — Partitioning / routing

### Purpose

Route events to partitions deterministically and provide ordering scope.

### What it owns

* partition assignment rule (based on `partition_key`)
* definition of ordering scope (partition-only)
* “bus does not compute partition_key” posture (requires it as input)

### Questions this module must answer

* How is partition_id chosen from partition_key (conceptually: deterministic mapping)?
* What are EB’s ordering guarantees and explicit non-guarantees?
* What is the stability constraint for partition_key (must be deterministic and present)?
* What happens when partition counts change (rebalance semantics) — can be high-level

### Can be left to the implementer

* number of partitions and scaling strategy
* rebalance mechanics and hashing algorithm specifics
* hot-key mitigation techniques

### Local vs deployed operation

* semantics identical; deployed may rebalance partitions more often due to scaling

---

## 5.3 Module 3 — Durable log store

### Purpose

Persist events as an append-only immutable log within a defined retention posture.

### What it owns

* append-only persistence posture
* retention policy concept (time/size/window)
* compaction posture (v0 default: no compaction)

### Questions this module must answer

* What does “durable” mean for EB (conceptually)?
* What retention window concept applies, and what are the consequences of expiry?
* Is compaction allowed? (v0 default: no)
* What integrity guarantees exist for stored content (e.g., exact bytes replayed)?

### Can be left to the implementer

* storage engine choice and replication strategy
* compression, serialization optimization
* performance tuning and sizing

### Local vs deployed operation

* **Local:** simpler retention and smaller durability guarantees (but still consistent semantics)
* **Deployed:** strong durability and replicated storage

---

## 5.4 Module 4 — Subscribe / delivery surface

### Purpose

Deliver events to consumers under at-least-once semantics and track progress.

### What it owns

* at-least-once delivery semantics
* consumer progress/checkpoint concept
* redelivery behaviour (duplicates possible)

### Questions this module must answer

* What is the delivery posture (at-least-once) and what does it imply?
* How are consumers identified (consumer group/subscription concept)?
* How is progress tracked (checkpoint concept), and is it per-partition?
* What does the DeliveredRecord include (offset/partition/publish_time + event content)?
* What happens on consumer failure (redelivery rules conceptually)?

### Can be left to the implementer

* group coordination and lease/heartbeat mechanics
* pull vs push delivery style
* checkpoint persistence mechanism details

### Local vs deployed operation

* semantics identical; deployed will have more complex group coordination

---

## 5.5 Module 5 — Replay / backfill

### Purpose

Support deterministic re-delivery of stored events within retention.

### What it owns

* definition of replay (re-delivery, not recomputation)
* replay request semantics (offset/time)
* replay invariants (no history rewriting)

### Questions this module must answer

* How is replay initiated (conceptually: by offset and/or by time window)?
* What are boundary rules (half-open `[from_offset, to_offset)` when `to_offset` is provided)?
* Does replay require a new consumer group or can it be done as a controlled rewind?
* What happens if requested replay range exceeds retention?

### Can be left to the implementer

* replay tooling UX (CLI/API)
* implementation mechanism (new subscription vs checkpoint reset)
* time-indexing strategy (if supporting time-window replay)

### Local vs deployed operation

* local replay may be file-based; deployed replay may be via consumer group rewind; semantics unchanged

---

## 5.6 Module 6 — Ops / governance surface

### Purpose

Define operational semantics that affect correctness: overload/backpressure, observability, and access control.

### What it owns

* backpressure posture (buffer/fail/shed-load — explicit)
* minimum observability fields
* minimal access control + audit signals

### Questions this module must answer

* What happens under overload (explicit posture; never silent drop)?
* What metrics must be exposed (publish rate, lag, retention utilization, errors)?
* What minimal audit fields exist (publisher identity, stream name, time)?
* Who is allowed to publish/subscribe (conceptually)?

### Can be left to the implementer

* exact infra (K8s, managed service, etc.)
* detailed IAM policies
* dashboards and alerting implementation details

### Local vs deployed operation

* local may allow relaxed access control; deployed must enforce it
* observability should exist in both (even if minimal locally)

---

## 5.7 Cross-module pinned items (summary)

Across all modules, EB must ensure:

* publish ACK implies durable append + assigned position
* event content is immutable (metadata kept outside content)
* delivery is at-least-once; consumers must be idempotent
* ordering is per-partition only
* replay is deterministic re-delivery within retention
* partition_key required (composition deferred) and EB does not compute it
* overload posture explicit; no silent drop
* local vs deployed changes mechanics, not semantics

---

## 6) Determinism and replay model (bus semantics)

> This section pins what “correct EB behaviour” means for determinism and replay: stable append positions, stable re-delivery, and explicit boundaries around duplicates, ordering, and retention.

### 6.1 What “deterministic EB” means (scope)

EB is deterministic if, given the same stored log and the same consumer replay parameters, EB will:

* deliver the **same event content** (same bytes via `event_bytes_b64`),
* in the **same per-partition order** (offset order),
* with stable delivery metadata (partition + offset),
  within the limits of at-least-once delivery (duplicates possible).

Determinism does **not** require:

* identical delivery timing,
* identical batching,
* identical consumer scheduling,
  as long as ordering within partitions and event identity remain consistent.

---

### 6.2 Immutability and “same bytes” replay

Determinism relies on immutability:

* EB stores the event content as an **opaque immutable blob**.
* Replay re-delivers the same blob bytes (the same `event_bytes_b64` content).
* Any EB metadata (offset, publish time, partition) is delivered separately and must not alter the event blob.

**Result:** consumers can dedupe using stable event identity fields inside the event content.

---

### 6.3 Duplicate delivery and consumer obligations

Because EB is at-least-once:

* consumers may receive the same event multiple times (redelivery)
* consumers must be idempotent at their boundaries

EB’s role is to:

* make duplicates *possible but explainable* (same offset/event identity),
* not to eliminate duplicates via “exactly-once” promises in v0.

---

### 6.4 Ordering model (what is guaranteed vs not)

EB guarantees:

* strict ordering by offset **within a partition**

EB explicitly does not guarantee:

* global ordering across partitions
* atomic multi-partition transactions
* causal ordering across independent producers unless they route to the same partition

If a consumer requires stronger ordering, it must design around partitioning (by choosing appropriate partition keys) or use an additional coordination layer.

---

### 6.5 Replay definition and modes

Replay is re-delivery of already stored events, typically in one of these conceptual modes:

* **Offset replay:** start from `{stream_name, partition_id, from_offset}` (or all partitions if `partition_id` is omitted)
* **Time-window replay (optional):** start from `{stream_name, from_time_utc}` and map to offsets, if supported (all partitions unless `partition_id` is provided)

Replay does not:

* rewrite history
* recompute or regenerate events
* mutate stored event content

---

### 6.6 Replay boundary rules (must be explicit)

Offsets use half-open ranges: `[from_offset, to_offset)` when `to_offset` is provided. If `to_offset` is omitted, replay continues from `from_offset` to the latest available offset within retention.

If time-based replay is supported, it is based on `published_at_utc` and uses half-open ranges: `[from_time_utc, to_time_utc)` when `to_time_utc` is provided. Precision should be declared (exact vs best-effort mapping to offsets).

---

### 6.7 Checkpointing and deterministic progress

Consumer progress is represented as checkpoints:

* `{consumer_group, stream_name, partition_id, offset}`

Deterministic replay depends on:

* checkpoints being stable identifiers of "what has been consumed" (offset is next_offset_to_read)
* rewind/replay being definable as "set checkpoint back to X" or "create new group at X"

Whether checkpoints are stored by EB or consumers is implementation detail; the semantics must be stable and checkpoints remain the authoritative progress token for replay/rewind.

---

### 6.8 Retention bounds replayability

Replay is only guaranteed within retention.

EB must make it explicit that:

* events beyond retention may be unavailable
* replay requests beyond retention must fail or degrade explicitly (never silent)

This affects backfill strategies in the rest of the loop.

---

### 6.9 Determinism acceptance scenarios (conceptual checklist)

EB should be considered deterministic enough when it can satisfy:

* publish returns a stable partition+offset and implies durable append
* a consumer can read and re-read a partition range and get the same content in offset order
* duplicates can occur, but the same logical event remains identifiable via event identity fields
* replay from offset produces deterministic re-delivery within retention
* replay beyond retention fails explicitly
* local vs deployed preserves the same semantics, only changing mechanics/throughput

---

## 7) Contracts philosophy and boundary surfaces

> EB contracts exist to pin **bus-plane semantics** (publish/deliver/checkpoint/replay objects) without prematurely redefining the full Canonical Event Contract Pack. EB contracts define *shape at the bus boundary*; EB specs define *behaviour/invariants*.

### 7.1 What a “contract” means for the Event Bus

For EB, a contract is a machine-readable definition of:

* what EB **accepts** at publish time (PublishRecord)
* what EB **delivers** to consumers (DeliveredRecord)
* how consumer progress can be represented (ConsumerCheckpoint)
* how replay/backfill can be requested (ReplayRequest)

Contracts exist to prevent:

* ambiguous publish ACK semantics (“accepted” vs “durably appended”)
* mutation of event content during transport
* incompatible replay/checkpoint semantics across environments

---

### 7.2 Contracts belong at boundaries (not per internal module)

EB is modularized conceptually, but those modules are not separate deployable services by default. Therefore:

* module semantics are pinned via EB1–EB5 prose invariants
* contracts exist only where other components integrate: publish/deliver/checkpoint/replay

**Rule:** don’t create “contract per module” unless EB becomes intentionally pluggable (e.g., multiple transport adapters with strict interfaces).

---

### 7.3 Boundary surfaces EB must pin contractually

EB touches four boundary surfaces:

1. **Publish surface**

* what must be supplied (stream_name, partition_key, event content)
* what a successful publish means (durable append + assigned position)

2. **Delivery surface**

* what a consumer receives (offset/partition metadata + the immutable event content)

3. **Checkpoint surface**

* how consumer progress is represented
* what “rewind” or “replay” means conceptually relative to checkpoints

4. **Replay/backfill surface**

* how replay is requested (offset/time window)
* what happens when replay exceeds retention

---

### 7.4 v0-thin contract strategy: keep event content opaque

To avoid duplicating the Canonical Event Contract Pack too early:

* EB contracts treat event content as:

  * `event_bytes_b64` (base64 of immutable canonical event bytes; required in v0)

`event_ref` is deferred in v0; if introduced later, it must carry immutability proof fields (e.g., `event_digest`, `digest_alg`) so "same bytes replayed" remains true.

**Preferred v0 posture:** `event_bytes_b64` only.

In v1, EB contracts may optionally reference the canonical event envelope (by `$ref`) once that pack exists and is stable.

---

### 7.5 Avoiding ambiguity: validation targeting

EB contract objects should be self-describing:

* `kind` + `contract_version`

v0 kind values are fixed (lower_snake_case): `publish_record`, `publish_ack`, `delivered_record`, `consumer_checkpoint`, `replay_request`.

This aligns with the SR and IG approach and prevents consumers from guessing which `$defs` applies.

---

### 7.6 Versioning and compatibility posture (conceptual)

* EB contracts carry explicit version identifiers (v0, v1, …)
* published/delivered/checkpoint objects declare contract version
* breaking changes require:

  * new contract version
  * explicit compatibility plan
  * updates to EB specs documenting semantic impacts (ordering/replay/ack)

---

### 7.7 Relationship to Canonical Event Contract Pack (explicit separation)

* EB contracts are bus-plane wrappers and must not become a second canonical payload source.
* Canonical Event Contract Pack defines the envelope/payload semantics; EB treats that content as opaque in v0.
* Once canonical pack v1 exists, EB can reference it without redefining it.

---

## 8) EB contract pack overview (v0-thin)

> This section describes the **contract artifacts** EB will ship with in v0, what they cover, and how other components use them. EB v0 contracts deliberately keep event content **opaque** to avoid duplicating the Canonical Event Contract Pack prematurely.

### 8.0 Contract pack inventory (v0 target set)

EB v0 ships **one** machine-checkable schema file:

* `contracts/eb_public_contracts_v0.schema.json`

This file contains `$defs` for EB boundary objects:

* publish
* publish ack
* delivery
* checkpointing
* replay/backfill

---

## 8.1 `contracts/eb_public_contracts_v0.schema.json`

### 8.1.1 What this file is for

This schema defines the shapes EB exposes at its boundary so components can integrate without guessing:

* what fields are required to publish
* what fields appear on delivered records
* how consumer checkpoints are represented
* how replay can be requested

It is not a canonical event schema and must not redefine canonical payloads.

---

### 8.1.2 Target `$defs` (conceptual list)

#### 1) `PublishRecord`

Defines what a publisher submits.

**Required (conceptual):**

* `kind`, `contract_version`
* `stream_name`
* `partition_key` (required; composition deferred)
* `event_bytes_b64` (required in v0)
* optional publish metadata:

  * `publisher_id` (audit)
  * `submitted_at_utc` (client time, optional)

**Conceptual rule:** EB does not mutate `event_bytes_b64`; EB does not compute `partition_key`.

---

#### 2) `PublishAck`

Defines what EB returns after a successful durable append.

**Required (conceptual):**

* `kind`, `contract_version`
* `stream_name`
* `partition_id`
* `offset`
* `published_at_utc`

**Conceptual rule:** `published_at_utc` is the durable-append timestamp for the assigned `{partition_id, offset}`.

---

#### 3) `DeliveredRecord`

Defines what EB delivers to consumers.

**Required (conceptual):**

* `kind`, `contract_version`
* `stream_name`
* `partition_id`
* `offset`
* `published_at_utc` (durable append timestamp)
* `partition_key` (echoed for convenience, optional but often useful)
* event content (`event_bytes_b64`, consistent with PublishRecord)

**Conceptual rule:** DeliveredRecord wraps bus metadata; it does not alter event content.

---

#### 4) `ConsumerCheckpoint`

Represents consumer progress.

**Required (conceptual):**

* `kind`, `contract_version`
* `consumer_group` (or subscription id)
* `stream_name`
* `partition_id`
* `offset`
* `updated_at_utc`

**Conceptual rule:** checkpoint `offset` is the next offset to read (exclusive), and the checkpoint is the authoritative progress token for replay/rewind semantics.

---

#### 5) `ReplayRequest` (optional but useful in v0)

Represents a replay/backfill request.

**Required (conceptual):**

* `kind`, `contract_version`
* `stream_name`
* one of:

  * `from_offset` (plus optionally `partition_id` if replay is partition-scoped)
  * `from_time_utc` (if time-based replay supported)
* optional end bounds:

  * `to_offset` or `to_time_utc`
* optional `consumer_group` or "replay_group" semantics (if you support it)

If `partition_id` is omitted, replay applies to all partitions in the stream (no cross-partition ordering guarantee).

**Conceptual rule:** replay is re-delivery; it does not rewrite history. Offset ranges are half-open: `[from_offset, to_offset)` when `to_offset` is provided.

---

### 8.1.3 Event content posture (v0)

To keep immutability unambiguous in v0:

* `event_bytes_b64`: base64 of the immutable canonical event bytes (required)

`event_ref` is deferred in v0; if introduced later, it must carry immutability proof fields (e.g., `event_digest`, `digest_alg`) so "same bytes replayed" remains true.

Avoid "event as JSON object" in EB contracts unless you explicitly ban normalization and define canonical serialization rules, because otherwise "same bytes replayed" becomes ambiguous.

---

### 8.1.4 Validation targeting rule

EB objects are self-describing via:

* `kind` + `contract_version`

`kind` values are lower_snake_case and pinned in v0 to: `publish_record`, `publish_ack`, `delivered_record`, `consumer_checkpoint`, `replay_request`.

Consumers validate based on those fields mapping to `$defs`.

---

## 8.2 What EB contracts cover vs what EB specs cover

### 8.2.1 Contracts cover (shape/structure)

* required fields for publish/deliver/checkpoint/replay objects
* types (strings, integers, byte blob shapes)
* enums for `kind` values (pinned set: `publish_record`, `publish_ack`, `delivered_record`, `consumer_checkpoint`, `replay_request`)
* minimal audit fields (`publisher_id`, etc.) if required

### 8.2.2 Specs cover (behaviour/invariants)

* publish ack semantics (durable append + assigned position)
* ordering scope (partition-only)
* at-least-once delivery semantics and redelivery posture
* replay semantics and boundary rules (half-open ranges)
* retention posture and behaviour on expiry
* backpressure/overload posture and required observability
* security posture (conceptual access control)

---

## 8.3 Naming and versioning posture (conceptual)

* contract filename includes explicit version (`*_v0.schema.json`)
* emitted objects declare contract_version
* breaking changes:

  * new version (v1)
  * explicit compatibility plan
  * spec documentation of semantic impact

---

## 9) Addressing, naming, and discoverability (conceptual)

> This section defines the *idea* of how EB concepts are addressed and discovered: streams, partitions, offsets, checkpoints, and replay ranges. The goal is: **no “scan latest and hope”**; everything is referable and replayable within retention.

### 9.1 Design goals (why addressing matters)

EB addressing must support:

* **Deterministic replay:** specify exactly what to re-read (stream/partition/offset or time)
* **Consumer reconciliation:** answer “how far has consumer X progressed?”
* **Operational observability:** map lag/backlog to stream partitions
* **Environment independence:** local vs deployed uses different tech, same meaning

---

### 9.2 Core addressing keys

EB revolves around a small set of addressing keys:

* `stream_name`
* `partition_id`
* `offset`
* `consumer_group` (or subscription id)
* `partition_key` (routing input; not an address itself, but impacts partition assignment)

**Principle:** `{stream_name, partition_id, offset}` is the primary address for a specific published event position.

---

### 9.3 Stream taxonomy (v0 posture)

At v0, keep stream taxonomy minimal:

* define at least one logical stream: **`admitted_events`** (post-IG)

Everything else (separate streams per event_type, per-plane streams, receipts stream, etc.) can be deferred until the Canonical Event Contract Pack and component boundaries are pinned.

---

### 9.4 Partition naming and stability (conceptual)

Partitions are identified by `partition_id`:

* stable within a given stream configuration
* partition scaling/rebalancing is implementation-specific

EB must not require consumers to know hashing algorithms; they should only require:

* partition_id and offsets as delivered by EB
* partition_key provided at publish time

---

### 9.5 Offset semantics (conceptual)

Offsets:

* are monotonically increasing within a partition
* are immutable identifiers for replay
* are the canonical basis for consumer checkpoints

**Boundary rule:** when EB acknowledges publish, it must provide the assigned offset (or an equivalent stable position identifier).

---

### 9.6 Checkpoint addressing (consumer progress)

A checkpoint is addressable by:

* `{consumer_group, stream_name, partition_id}` → `offset`

Checkpoints may be stored:

* in EB, or
* in a consumer-owned coordination store,
  but the semantic representation remains stable.

Checkpoint `offset` is the next offset to read (exclusive), and the checkpoint is the authoritative progress token for replay/rewind semantics.

**Discoverability requirement:** operators must be able to determine consumer lag from published offsets and checkpoints.

---

### 9.7 Replay addressing (how replay ranges are specified)

Replay requests should be definable in one of these conceptual ways:

* **Offset-based replay** (preferred for determinism):

  * `{stream_name, partition_id, from_offset}` with optional end offset (half-open `[from_offset, to_offset)`)

* **Time-based replay** (optional):

  * `{stream_name, from_time_utc}` mapping to offsets using bus publish time (half-open `[from_time_utc, to_time_utc)`)

If `partition_id` is omitted, replay applies to all partitions in the stream; no cross-partition ordering is implied.

If time-based replay is offered, it must be clear whether mapping is exact or best-effort.

---

### 9.8 Retention and its impact on discoverability

Retention bounds what can be discovered/replayed:

* offsets older than retention may not be available
* replay requests beyond retention must fail or degrade explicitly (never silent)

EB should surface retention status in ops telemetry (utilization and oldest available offsets/time).

---

### 9.9 Local vs deployed addressing

* **Local:** stream may be a file log; offsets may be line numbers or record indices.
* **Deployed:** stream may be a distributed log; offsets are broker-assigned.

**Rule:** regardless of implementation, the conceptual identifiers behave the same:

* publish returns a stable position
* delivered records include position metadata
* replay can target a position range within retention

---

## 10) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Event Bus / Stream Plane docs and contracts. The goal is a **single, deep reading surface** for EB design, plus a **minimal v0 bus-plane contract**.

### 10.1 Target location in repo

Conceptually, EB lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/event_bus_stream/`

This folder should be self-contained: a new contributor should understand EB by starting here.

---

### 10.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ event_bus_stream/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ EB1_charter_and_boundaries.md
         │  ├─ EB2_publish_and_subscribe_surfaces.md
         │  ├─ EB3_ordering_and_partitioning_posture.md
         │  ├─ EB4_replay_and_retention.md
         │  └─ EB5_ops_backpressure_security_acceptance.md
         │
         └─ contracts/
            └─ eb_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; v0 needs only **one** schema file here.

---

### 10.3 What each file is for (intent)

#### `README.md`

* Entry point: what EB is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (roadmap)
  * `specs/` reading order (EB1–EB5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This roadmap document:

  * EB purpose in platform
  * EB laws (immutability, at-least-once, partition ordering, replay, retention)
  * modular breakdown + questions per module
  * EB v0 contract philosophy (event content opaque)
  * addressing/discoverability concepts

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * EB specs define behaviour/invariants
  * EB contract schema defines bus-plane object shapes
* Non-negotiables:

  * publish ack implies durable append + assigned position
  * no event mutation; bus metadata is wrapper-only
  * at-least-once delivery and partition-only ordering
  * replay semantics and retention bounds
  * partition_key required; EB does not compute it

#### `specs/`

* EB1–EB5 are the eventual binding-ish EB design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `eb_public_contracts_v0.schema.json` pins:

  * PublishRecord / DeliveredRecord / ConsumerCheckpoint / ReplayRequest shapes

---

### 10.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (design direction)
3. `specs/EB1_...` → `specs/EB5_...` (behaviour/invariants)
4. `contracts/eb_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

### 10.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge EB1–EB5 into fewer docs once stable.
* Add `contracts/README.md` only if you need a brief note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders under deadline.

---

## 11) What the eventual spec docs must capture (mapping from this concept doc)

> This section bridges the EB conceptual roadmap into the **actual EB spec docs** (EB1–EB5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 11.0 Mapping rule (how to use this section)

For every EB “law” and “question” in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in EB1–EB5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared **implementation freedom**.

---

## 11.1 EB1 — Charter & boundaries

### EB1 must capture

* EB’s purpose as a **distribution + durability plane**
* authority boundaries:

  * EB transports and persists; it does not validate/transform
  * EB is system-of-record for partition+offset positions
* EB laws in enforceable prose:

  * no payload mutation (event content opaque)
  * publish ack implies durable append + assigned position
  * at-least-once delivery
  * ordering within partition only
  * replay semantics and retention bounds
* in-scope vs out-of-scope declarations:

  * no exactly-once promise in v0
  * no global ordering promise in v0
  * partition_key composition explicitly deferred

### EB1 may leave to the implementer

* technology choice (Kafka/Kinesis/custom)
* infra topology, replication details, performance tuning

---

## 11.2 EB2 — Publish & subscribe surfaces

### EB2 must capture

* publish surface semantics:

  * required fields (`stream_name`, `partition_key`, `event_bytes_b64`)
  * publish ack meaning (durable append + position) and PublishAck shape
  * publish rejection/error cases (missing fields, unauthorized, overload)
* delivery surface semantics:

  * what a consumer receives (DeliveredRecord wrapper with offset/partition metadata + `event_bytes_b64`)
  * consumer obligation: idempotency (duplicates possible)
* checkpoint/progress concept at the interface:

  * how progress is represented and how consumers advance
* minimal stream taxonomy (v0):

  * `admitted_events` (post-IG) as baseline

### EB2 may leave to the implementer

* API transport choice and batching mechanics
* push vs pull consumption style
* group coordination specifics

---

## 11.3 EB3 — Ordering & partitioning posture

### EB3 must capture

* ordering guarantee scope:

  * within partition only
  * explicit non-guarantees (no global order, no cross-partition atomicity)
* partition_key posture:

  * required single field (`partition_key`)
  * EB does not compute it
  * stability constraints (deterministic, stable)
* deferrals:

  * partition_key composition mapping deferred until Identity + Features v0
* partition scaling/rebalance posture (high-level):

  * what changes consumers may observe (e.g., partition count changes) without changing EB laws

### EB3 may leave to the implementer

* hashing algorithm choice
* partition count tuning
* hot-key mitigation strategies

---

## 11.4 EB4 — Replay & retention

### EB4 must capture

* replay definition:

  * re-delivery of stored events; not recomputation; not history rewriting
* replay request semantics:

  * by offset and/or time (if supported)
  * boundary rules (half-open `[from_offset, to_offset)` when `to_offset` is provided)
  * behaviour when replay exceeds retention
* retention posture:

  * retention window concept (time/size)
  * consequences of expiry
* compaction posture v0:

  * default no compaction unless explicitly chosen

### EB4 may leave to the implementer

* replay tooling UX (CLI/API)
* time-indexing technique if time-based replay offered
* storage internals and optimizations

---

## 11.5 EB5 — Ops, backpressure, security & acceptance

### EB5 must capture

* explicit overload/backpressure posture:

  * buffer/fail/shed-load (never silent drop)
* minimum observability requirements:

  * publish rate, consumer lag, retention utilization, error rates
* access control posture:

  * who can publish/subscribe (conceptual)
  * minimal audit fields (publisher/subscriber identity, stream_name, time)
* acceptance scenarios (Definition of Done):

  * publish ack truth
  * duplicates/redelivery
  * per-partition ordering
  * replay within retention
  * replay beyond retention fails explicitly
  * overload behaviour is visible and explicit
  * local vs deployed semantic equivalence

### EB5 may leave to the implementer

* exact IAM implementation
* dashboards/alerts tooling
* infrastructure deployment details

---

## 11.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* `PublishRecord`, `PublishAck`, `DeliveredRecord`, `ConsumerCheckpoint`, `ReplayRequest` shapes
* required fields: stream_name, partition_key, offsets, timestamps
* event content representation (`event_bytes_b64`)
* self-describing targeting (`kind`, `contract_version`, pinned lower_snake_case `kind` enum)

### Specs must include

* publish ack semantics
* ordering and non-guarantees
* at-least-once delivery implications
* replay semantics and boundary rules (half-open ranges)
* retention posture and expiry behaviour
* overload/backpressure posture and observability requirements

---

## 11.7 Minimal completeness standard (so EB is implementable)

EB is “spec-ready” for implementation when EB1–EB5 collectively pin:

* publish ACK truth (durable append + assigned position)
* immutability rule (no mutation; metadata wrapper only)
* at-least-once delivery + partition-only ordering
* replay semantics and retention bounds
* partition_key required (composition deferred) and EB does not compute it
* explicit overload/backpressure posture + minimum metrics

Everything else can remain implementer freedom.

---

## 12) Acceptance questions and “Definition of Done”

> This section is the conceptual **ship checklist** for EB: the questions EB must answer and the minimal behavioural scenarios that indicate EB is correct enough to implement and integrate.

### 12.1 Acceptance questions (EB must answer these unambiguously)

1. **What does a publish ACK guarantee?**

* Does ACK mean the event is durably appended and has an assigned partition+offset?

2. **Does EB ever change event content?**

* Is event content stored and replayed immutably (same bytes via `event_bytes_b64`), with bus metadata separate?

3. **What delivery semantics do consumers get?**

* Are duplicates possible (at-least-once)?
* What does redelivery look like conceptually?

4. **What ordering is guaranteed?**

* Is ordering guaranteed only within a partition?
* Are global ordering and cross-partition atomicity explicitly not guaranteed?

5. **How do consumers track progress?**

* What is the checkpoint concept and what keys identify it (group/stream/partition/offset as next_offset_to_read)?

6. **How do we replay/backfill?**

* Can we replay from an offset with half-open ranges (`[from_offset, to_offset)`)?
* If time-based replay exists, what time is used (bus publish time) and how precise is it?
* If `partition_id` is omitted, does replay apply to all partitions (no cross-partition ordering)?

7. **What happens when a replay range is outside retention?**

* Does EB fail explicitly or provide an explicit degraded response?

8. **What happens under overload/backpressure?**

* Buffer/fail/shed-load? Never silent drop?
* How is overload surfaced (errors/metrics)?

9. **What minimum observability exists?**

* Can we see publish rate, consumer lag, retention utilization, error rates?

10. **Do local and deployed EB behave the same semantically?**

* Do publish/deliver/replay semantics match, even if mechanics differ?

---

### 12.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Publish ACK implies durable append + assigned position

**Given**

* a PublishRecord with required fields (`stream_name`, `partition_key`, event content)

**Expect**

* EB returns PublishAck including `stream_name`, `partition_id`, `offset`, `published_at_utc`
* the event is durably stored and can be read by consumers

---

#### DoD-2: No mutation (immutability preserved)

**Given**

* an event published with specific event content bytes (or a stable ref)

**Expect**

* EB delivers and replays the exact same content (same bytes via `event_bytes_b64`)
* EB metadata (offset, publish time) is delivered outside event content

---

#### DoD-3: At-least-once delivery (duplicates possible)

**Given**

* a consumer group reading from a stream experiences failure/retry

**Expect**

* EB may redeliver previously delivered events
* duplicates are possible and consumers must be able to handle them
* EB does not promise exactly-once in v0

---

#### DoD-4: Per-partition ordering preserved

**Given**

* multiple events published with the same `partition_key` (thus same partition)

**Expect**

* consumers receive them in offset order within that partition
* no guarantee is claimed across partitions

---

#### DoD-5: Replay from offset is deterministic

**Given**

* a replay request from `{stream, partition, from_offset}` within retention

**Expect**

* EB re-delivers events in offset order using half-open ranges (`[from_offset, to_offset)`)
* replay does not rewrite history or recompute events

---

#### DoD-6: Replay beyond retention fails explicitly

**Given**

* a replay request whose range includes offsets older than retention

**Expect**

* EB fails or degrades explicitly (clear error/response)
* no silent omission of missing history

---

#### DoD-7: Consumer checkpoints represent progress deterministically

**Given**

* a consumer group advances through a partition

**Expect**

* a stable checkpoint exists (stream/partition/offset as next_offset_to_read)
* "rewind to X" is definable using checkpoint semantics (even if implemented differently)

---

#### DoD-8: Overload posture is explicit (no silent drop)

**Given**

* EB is overloaded (publish rate exceeds capacity)

**Expect**

* EB follows its defined posture (buffer/fail/shed-load)
* overload is visible via metrics/errors
* EB does not silently drop published events without surfacing outcome

---

#### DoD-9: Minimal observability signals exist

**Given**

* EB is running

**Expect**

* metrics/telemetry exist for:

  * publish rate
  * consumer lag
  * retention utilization
  * error rates

---

#### DoD-10: Local vs deployed semantic equivalence

**Given**

* the same publish/consume/replay behaviours exercised locally and in deployed mode

**Expect**

* same semantic meaning for ACK, ordering, replay, retention
* differences only in mechanics and performance

---

### 12.3 Minimal deliverables required to claim “DoD satisfied”

To claim EB meets DoD at v0 conceptual level, you should be able to show:

* successful publish ACK with assigned position
* consumer delivery including DeliveredRecord wrapper
* evidence of immutability (same bytes via `event_bytes_b64` replayed)
* demonstration of possible duplicates under failure (conceptual test)
* replay from offset within retention
* explicit behaviour on replay beyond retention
* basic metrics for lag and publish rate

---

## 13) Open decisions log (explicit placeholders)

> This is the decision backlog EB must eventually pin in EB1–EB5 and/or `contracts/`. Until closed, each item stays **OPEN** and the implementer should not invent semantics.

### 13.0 How decisions get closed

* Each decision gets an ID: `DEC-EB-###`
* Status: **OPEN** → **CLOSED**
* When CLOSED, the canonical wording lives in:

  * EB specs (behaviour), and/or
  * EB contract schema (shape),
    with a pointer back to the decision ID.

---

### 13.1 Publish semantics and durability

* **DEC-EB-001 — Publish ACK semantics (durable append definition)**
  *Open question:* what exact durability standard is implied by ACK (conceptual).
  *Close in:* **EB2** (behaviour) + optionally in contracts (fields)

* **DEC-EB-002 — Batch publish posture (if any)**
  *Open question:* does EB accept batch publish in v0? If yes, per-record ack semantics.
  *Close in:* **EB2**

---

### 13.2 Partitioning and ordering

* **DEC-EB-003 — Partition key field name + constraints**
  *Open question:* exact field name (`partition_key` vs `primary_entity_key`) and constraints (type, encoding).
  *Close in:* **EB3** (+ contracts)

* **DEC-EB-004 — Partition count change/rebalance posture**
  *Open question:* what consumers may observe when partitions change (high-level).
  *Close in:* **EB3**

* **DEC-EB-005 — Partition key composition mapping**
  *Open question:* what domain key(s) feed partition_key (account/card/merchant/etc.).
  *Deferral:* explicitly deferred until Identity + Features v0.
  *Close in:* post-Identity/Features (not in EB v0)

---

### 13.3 Delivery and checkpointing

* **DEC-EB-006 - Checkpoint ownership posture**
  *Open question:* are checkpoints persisted by EB, by consumers, or by a coordination store?
  *Close in:* **EB2/EB5** (conceptually; implementation can vary)

* **DEC-EB-007 - Redelivery semantics detail**
  *Open question:* what conditions trigger redelivery and what is guaranteed about it (high-level).
  *Close in:* **EB2**

* **DEC-EB-017 - Checkpoint offset meaning + authority (CLOSED)**
  *Closed decision:* checkpoint `offset` is the next offset to read (exclusive), and the checkpoint is the authoritative progress token for replay/rewind semantics regardless of ownership.
  *Close in:* **EB2/EB4** (contracts + replay semantics)

---

### 13.4 Replay semantics

* **DEC-EB-008 - Replay boundary rules (CLOSED)**
  *Closed decision:* offset ranges are half-open `[from_offset, to_offset)` and time ranges are half-open `[from_time_utc, to_time_utc)` when end bounds are provided.
  *Close in:* **EB4**

* **DEC-EB-009 — Time-based replay support (v0?)**
  *Open question:* is `from_time_utc` supported in v0; if yes, which time (publish time) and precision posture.
  *Close in:* **EB4**

* **DEC-EB-010 — Replay mechanism posture**
  *Open question:* replay via new consumer group vs checkpoint rewind; what is supported in v0.
  *Close in:* **EB4**

---

### 13.5 Retention and compaction

* **DEC-EB-011 — Retention policy concept**
  *Open question:* time/size retention concept for v0 and its operator guarantees.
  *Close in:* **EB4**

* **DEC-EB-012 — Compaction posture**
  *Open question:* is compaction allowed at all in v0 (default: no).
  *Close in:* **EB4**

---

### 13.6 Overload/backpressure and ops

* **DEC-EB-013 — Backpressure/overload posture**
  *Open question:* buffer vs fail vs shed-load (explicit, never silent).
  *Close in:* **EB5**

* **DEC-EB-014 — Minimum observability set**
  *Open question:* the minimum metrics/log fields required (publish rate, lag, retention utilization, errors).
  *Close in:* **EB5**

---

### 13.7 Security and governance

* **DEC-EB-015 — Access control posture**
  *Open question:* minimal publish/subscribe authorization model.
  *Close in:* **EB5**

* **DEC-EB-016 — Audit fields required**
  *Open question:* publisher/subscriber identity fields and what gets recorded.
  *Close in:* **EB5**

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples pin the **bus-plane wrappers** only.
> Event content is shown as `event_bytes_b64` (base64 of immutable canonical event bytes) to make "same bytes replayed" unambiguous in v0.
> Canonical event envelope/payload schemas live elsewhere (Canonical Event Contract Pack); EB treats content as opaque here.

---

### A.1 Example - `PublishRecord`

```json
{
  "kind": "publish_record",
  "contract_version": "eb_public_contracts_v0",

  "stream_name": "admitted_events",
  "partition_key": "pk_account_00001234",

  "publisher_id": "ingestion_gate",

  "event_bytes_b64": "BASE64(<OPAQUE_CANONICAL_EVENT_BYTES>)",
  "submitted_at_utc": "2026-01-05T18:02:10Z"
}
```

---

### A.2 Example - `PublishAck`

```json
{
  "kind": "publish_ack",
  "contract_version": "eb_public_contracts_v0",

  "stream_name": "admitted_events",
  "partition_id": 12,
  "offset": 9812345,

  "published_at_utc": "2026-01-05T18:02:11Z"
}
```

---

### A.3 Example - `DeliveredRecord`

```json
{
  "kind": "delivered_record",
  "contract_version": "eb_public_contracts_v0",

  "stream_name": "admitted_events",
  "partition_id": 12,
  "offset": 9812345,

  "published_at_utc": "2026-01-05T18:02:11Z",

  "partition_key": "pk_account_00001234",

  "event_bytes_b64": "BASE64(<OPAQUE_CANONICAL_EVENT_BYTES>)"
}
```

---

### A.4 Example - `ConsumerCheckpoint`

```json
{
  "kind": "consumer_checkpoint",
  "contract_version": "eb_public_contracts_v0",

  "consumer_group": "online_features_v0",
  "stream_name": "admitted_events",

  "partition_id": 12,
  "offset": 9812400,

  "updated_at_utc": "2026-01-05T18:03:20Z"
}
```

---

### A.5 Example - `ReplayRequest` (offset-based, partition-scoped, half-open `[from_offset, to_offset)`)

```json
{
  "kind": "replay_request",
  "contract_version": "eb_public_contracts_v0",

  "stream_name": "admitted_events",
  "partition_id": 12,

  "from_offset": 9812000,
  "to_offset": 9812500,

  "requested_at_utc": "2026-01-05T18:10:00Z",
  "replay_group": "replay_online_features_20260105T181000Z"
}
```

---

### A.6 Example - `ReplayRequest` (time-based, best-effort mapping, half-open `[from_time_utc, to_time_utc)`)

If `partition_id` is omitted, replay applies to all partitions in the stream.

```json
{
  "kind": "replay_request",
  "contract_version": "eb_public_contracts_v0",

  "stream_name": "admitted_events",

  "from_time_utc": "2026-01-05T00:00:00Z",
  "to_time_utc": "2026-01-05T06:00:00Z",

  "time_basis": "bus_published_at_utc",
  "precision": "best_effort",

  "requested_at_utc": "2026-01-05T18:12:00Z",
  "replay_group": "replay_decision_fabric_20260105T181200Z"
}
```

---

## Appendix B — ASCII sequences (publish/deliver/checkpoint/replay/overload)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/append
> Notes like `[ACK=durable+offset]` describe the semantic guarantee, not the implementation.

---

### B.1 Publish → durable append → PublishAck (truthful publish semantics)

```
Participants:
  Publisher (IG) | EB (Publish) | EB (Partition) | EB (Durable Log)

Publisher -> EB (Publish): PublishRecord(stream_name, partition_key, event_bytes_b64)
EB (Partition): choose partition_id = f(partition_key)

EB (Durable Log) => EB (Durable Log): append event_bytes_b64 (immutable) to {stream, partition}
EB (Durable Log): assign offset N

EB (Publish) -> Publisher: PublishAck(stream_name, partition_id, offset=N, published_at_utc=...)   [ACK=durable+offset]
```

---

### B.2 Subscribe/consume → delivery wrapper → consumer checkpoint

```
Participants:
  EB (Subscribe/Delivery) | Consumer | Checkpoint Store (EB-owned or consumer-owned)

EB (Subscribe/Delivery) --> Consumer: DeliveredRecord(partition_id, offset, published_at_utc, event_bytes_b64)
Consumer: process event_bytes_b64 (idempotent; duplicates possible)

Consumer => Checkpoint Store: write ConsumerCheckpoint(stream, partition_id, offset=K)  (next_offset_to_read)
Consumer --> EB (Subscribe/Delivery): (conceptual) ACK/progress advanced to offset K (next_offset_to_read)
```

---

### B.3 Duplicate delivery (at-least-once redelivery)

```
Participants:
  EB (Delivery) | Consumer

EB (Delivery) --> Consumer: DeliveredRecord(partition=12, offset=9812345, event_bytes_b64)
Consumer: processes event (records idempotency via event_id inside event_bytes_b64)

(consumer failure / retry / rebalance occurs)

EB (Delivery) --> Consumer: DeliveredRecord(partition=12, offset=9812345, event_bytes_b64)  (redelivery)
Consumer: detects duplicate (idempotency) -> does not double-apply side effects
```

---

### B.4 Replay from offset (deterministic re-delivery)

```
Participants:
  Operator/Tool | EB (Replay) | EB (Durable Log) | Consumer (Replay Group)

Operator -> EB (Replay): ReplayRequest(stream, partition_id, from_offset=X, to_offset=Y)
EB (Replay) --> EB (Durable Log): read events offsets [X..Y) in order

EB (Replay) --> Consumer (Replay Group): DeliveredRecord(offset=X, event_bytes_b64)
EB (Replay) --> Consumer (Replay Group): DeliveredRecord(offset=X+1, event_bytes_b64)
...
EB (Replay) --> Consumer (Replay Group): DeliveredRecord(offset=Y-1, event_bytes_b64)

Note: replay re-delivers stored bytes; it does not recompute or rewrite history.
```

---

### B.5 Replay beyond retention (explicit failure, no silent omission)

```
Participants:
  Operator/Tool | EB (Replay) | EB (Retention/Index)

Operator -> EB (Replay): ReplayRequest(from_offset=OLD)
EB (Retention/Index): determines OLD is older than retention window / not available

EB (Replay) -> Operator: ERROR(OUT_OF_RETENTION)  [explicit failure]
```

---

### B.6 Overload/backpressure (explicit posture, never silent drop)

```
Participants:
  Publisher | EB (Publish) | EB (Ops/Backpressure)

Publisher -> EB (Publish): PublishRecord(...)
EB (Ops/Backpressure): detects overload (queue depth / lag / rate)

EB applies chosen posture (explicit):
  Option A: BUFFER (bounded)
    EB (Publish): delays/queues publish; later appends and ACKs
  Option B: FAIL-FAST
    EB (Publish) -> Publisher: ERROR(OVERLOADED, retryable=true)
  Option C: SHED-LOAD (traceable)
    EB (Publish) -> Publisher: ERROR(OVERLOADED_SHED, retryable=true)

Note: EB does not silently drop published events without an explicit outcome.
```

---
