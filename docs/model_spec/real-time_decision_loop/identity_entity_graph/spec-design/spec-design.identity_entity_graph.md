# Conceptual Document Plan — Identity & Entity Graph (IEG)

## 0) Document metadata

### 0.1 Document header

* **Title:** *Identity & Entity Graph (IEG) — Conceptual Roadmap (Modular Breakdown + Contract Intent)*
* **Component/Plane:** Real-Time Decision Loop / Identity & Entity Graph
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final (choose one)
* **Version:** v0.x (increment on substantive changes)
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Provide a **single, coherent conceptual direction** for Identity & Entity Graph (IEG) before writing IEG specs and contracts.
* Capture the **designer-locked v0 decisions** (scope, authority boundaries, link posture, version meaning) so later specs cannot drift.
* Enumerate the **questions IEG must answer** (by module + contract boundary) to guarantee:

  * replay-safe, idempotent projection from admitted events
  * joinable, versioned context for decisioning/feature consumers
  * explicit authority boundaries (projection, not world truth)
* Explicitly separate:

  * **pinned design intent** (what must be true and stable)
  * **implementation freedom** left to the implementer (storage, indexing, processing topology)

### 0.3 Audience and prerequisites

* **Primary readers:** you (architect/spec author), Codex (implementer)
* **Secondary readers:** owners of Online Features, Decision Fabric, Observability
* **Prerequisites (assumed known):**

  * IG produces admitted, canonical events (trust boundary already applied)
  * EB transports admitted events with at-least-once semantics (duplicates possible)
  * Canonical Event Contract Pack is separate; in v0 IEG treats consumed payloads as opaque and relies on envelope-level fields

### 0.4 How to use this document

* Use as the **roadmap** for authoring:

  * IEG spec set (IEG1–IEG5), and
  * IEG v0 contract schema (`ieg_public_contracts_v0.schema.json`)
* This document is **non-binding**; authoritative shapes live in `contracts/`.
* Each “question” here must eventually become:

  * a **pinned decision** in IEG specs, or
  * a **schema rule/field** in IEG contracts, or
  * explicitly declared **implementation freedom**

### 0.5 Non-binding disclaimer

* This document is conceptual and **non-binding**.
* Any normative language (MUST/SHALL/SHOULD) is **directional** until captured in:

  * IEG specs (binding sections), and/or
  * IEG contract schema (machine validation)

### 0.6 Scope and non-scope

* **In scope:** IEG responsibilities, v0 pinned design intent, entity/edge vocabulary posture, update semantics, query surface, graph_version meaning, contract intent, repo layout, spec mapping.
* **Out of scope:** full canonical payload schema design, probabilistic identity/merge systems, feature vector computation (owned by Online Feature Plane), “global cross-run entity graph” behaviour (explicitly excluded in v0).

### 0.7 Repo placement and related artifacts

* **Proposed location:**
  `docs/model_spec/real-time_decision_loop/identity_entity_graph/CONCEPTUAL.md` (or merge into `README.md` later)
* **Related docs (eventual):**

  * `specs/IEG1_...` through `specs/IEG5_...`
  * `contracts/ieg_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Identity & Entity Graph exists

Identity & Entity Graph (IEG) is a **read-mostly context plane** for the Real-Time Decision Loop. Its job is to turn admitted observations (events) into a **queryable, versioned entity + relationship context** that other components can use at decision time.

One sentence: **“Provide the best current entity context (and links) for a given event, in a run-scoped, versioned, replay-safe way—without mutating world truth.”**

---

### 1.2 Where IEG sits relative to IG, EB, Features, and Decision Fabric

* **Ingestion Gate (IG)** enforces trust and admits canonical events.
* **Event Bus (EB)** durably distributes admitted events (at-least-once; duplicates possible).
* **IEG** consumes admitted events and maintains a **projection**:

  * entity canonical store
  * relationship edges
  * query indices/projections
* **Online Feature Plane** consumes events and context and computes feature vectors; IEG does **not** compute feature vectors in v0.
* **Decision Fabric** uses IEG queries (directly or via Features) and records which `graph_version` it used.

---

### 1.3 What IEG is system-of-record for (and what it is not)

IEG is authoritative for:

* its own **projection state** (entities + edges + indices)
* its own **version markers** (`graph_version`) that describe “what context was used”

IEG is not authoritative for:

* world truth (engine outputs and admitted events remain upstream truth)
* transaction correctness
* business meaning of events
* merge policy across runs (explicitly excluded in v0)

IEG is a **materializer and indexer**, not a truth source.

---

### 1.4 Why run/world scoping matters (v0 posture)

In v0, IEG is explicitly **run/world-scoped**:

* the graph is isolated by ContextPins:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`

This is critical to prevent:

* cross-run leakage,
* non-reproducible identity context,
* and “global graph drift” that undermines audit/replay.

---

### 1.5 What IEG must enable for loop components

Other loop components must be able to rely on IEG for:

* **Joinable context**

  * every query and response is tied to ContextPins
* **Replay-safe behavior**

  * duplicates/out-of-order events do not corrupt entity/edge state
* **Explainability**

  * decisions can record `graph_version` used
  * edge/link updates carry provenance pointers
* **Operational clarity**

  * lag/health can be observed; failure behavior is explicit

---

## 2) Core invariants (IEG “laws”)

> These are **non-negotiable behaviours** for IEG v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Run/world scoped (no cross-run graph in v0)

* IEG state is isolated by **ContextPins**:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* IEG MUST NOT accumulate or resolve identities across different ContextPins in v0.

---

### 2.2 Projection-only authority (no silent rewrites)

* IEG is a **read-mostly projection** from admitted events.
* IEG MUST NOT “fix” or rewrite upstream truth.
* Any linking decisions must be attributable (provenance recorded).

---

### 2.3 Idempotent updates under duplicate delivery

* EB may deliver duplicates; IEG MUST be duplicate-safe.
* Applying the same logical update more than once MUST be a no-op after the first successful application.

---

### 2.4 Disorder-safe updates (out-of-order cannot break invariants)

* IEG MUST be safe under out-of-order event delivery.
* Edge timestamp fields MUST be updated using event_time monotonic rules:

  * `first_seen_event_time = min(existing, event_time)`
  * `last_seen_event_time  = max(existing, event_time)`

---

### 2.5 Links/aliases only in v0 (no merges)

* v0 supports **links/aliases** only.
* v0 MUST NOT collapse two canonical entities into one (“merge”) and MUST NOT silently merge identities.

---

### 2.6 Joinability is mandatory

* Every query request MUST include ContextPins.
* Every query response MUST echo ContextPins (or contain a resolvable context reference).
* Consumers must be able to join IEG context to the correct run/world without guessing.

---

### 2.7 Versioned context is mandatory

* Every query response MUST include `graph_version`.
* `graph_version` MUST be monotonic and must be recordable by consumers (“graph_version used”).

---

### 2.8 Event-time discipline (event_time ≠ ingest_time)

* IEG relationship updates and “as-of” semantics must be attributable to **event_time**.
* Ingest/apply time may be recorded separately but must not replace event_time.

---

### 2.9 No feature computation in IEG v0

* v0 IEG provides entity/edge retrieval and indices/projections for retrieval only.
* Feature vector computation remains owned by the Online Feature Plane.

---

### 2.10 Explicit failure posture (no invented context)

* If IEG cannot serve correct context, it returns an explicit ErrorResponse (with retryability flag).
* IEG must not invent partial context as a substitute for correctness.

---

## 3) Terminology and key objects

> These are the nouns used throughout the IEG conceptual roadmap. Shapes are conceptual here; exact fields land in IEG2–IEG4 and the contract schema.

### 3.1 ContextPins

**ContextPins** are the run/world scoping identifiers that isolate IEG state:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

All IEG queries and responses are scoped by these pins.

---

### 3.2 Admitted event

An **admitted event** is a post-IG event carried on EB that is considered canonical for ingestion. EB delivery may be duplicate and out-of-order; IEG must be safe under both.

---

### 3.3 Event identity fields

IEG update semantics depend on envelope-level fields:

* `event_id`: stable logical identity of the event (used for idempotency keys)
* `event_time`: when the observation occurred (used for edge timestamps)
* `event_type` (or schema targeting): what kind of event this is, at least for routing update logic
* `observed_identifiers[]`: the identifiers observed in the event that may map to entities

In v0, IEG relies on these envelope-level fields and does not parse domain payloads.

---

### 3.4 ObservedIdentifier

An **ObservedIdentifier** is a normalized representation of an identifier observed in an event:

* `id_kind`: identifier kind (e.g., `account_ref`, `pan_hash`, `device_fp`, `merchant_id`, etc.)
* `id_value`: the observed value (string)
* optional `namespace`/`issuer`: to disambiguate identifier spaces

ObservedIdentifiers are the main input to identity resolution in v0.

---

### 3.5 Entity types (v0 vocabulary)

IEG v0 supports these entity types:

* `account`
* `card`
* `customer`
* `merchant`
* `device`

Entity types are fixed in v0 to avoid schema drift.

---

### 3.6 EntityRef

An **EntityRef** identifies a canonical entity within a context:

* `entity_type`
* `entity_id`

`entity_id` is deterministically minted within the run/world scope.

---

### 3.7 EntityRecord (thin)

An **EntityRecord** is a canonical record for an entity, conceptually containing:

* `entity_ref`
* optional `attributes` (opaque map)
* optional `as_of_event_time` marker

IEG v0 keeps entity records thin; richer attributes can be added later by policy.

---

### 3.8 Alias / link

An **alias/link** is a mapping from an ObservedIdentifier to an EntityRef. In v0, IEG creates and maintains aliases/links but does not perform merges.

---

### 3.9 Edge types (v0 vocabulary)

IEG v0 supports these edge types (directed by edge_type definition):

* `account__has_card`
* `card__seen_on_device`
* `customer__has_account`
* `customer__seen_at_address`
* `merchant__operates_site`

Edge vocab is fixed in v0.

---

### 3.10 EdgeRecord

An **EdgeRecord** represents a relationship edge:

* `src` (EntityRef)
* `dst` (EntityRef)
* `edge_type`
* `first_seen_event_time`
* `last_seen_event_time`
* `provenance_ref` (opaque pointer to the causing event)

Edge uniqueness is keyed by `(src_entity_id, dst_entity_id, edge_type)`.

---

### 3.11 graph_version

**graph_version** is a monotonic token that indicates the applied-stream watermark for a given ContextPins graph.

In v0, graph_version basis is:

* per-partition applied offset watermark vector (map), plus stream_name.

Consumers record graph_version to support audit/replay (“context used”).

---

### 3.12 Update key

An **update_key** is the idempotency key for applying an event to the graph:

* derived from ContextPins + event_id + updater identity/version

If an update_key is already applied, update application is a no-op.

---

### 3.13 Query surface

IEG provides a query surface with these v0 operations:

* `resolve_identity(observed_identifiers, pins)`
* `get_entity_profile(entity_ref, pins)`
* `get_neighbors(entity_ref, pins, edge_type?, depth=1)`

Every response includes ContextPins and graph_version.

---

### 3.14 ErrorResponse

An **ErrorResponse** is returned when IEG cannot serve correct context. It includes:

* error category/code
* `retryable` flag
* ContextPins + (where possible) current graph_version metadata

---

## 4) IEG as a black box (inputs → outputs)

> This section treats IEG as a black box: what it consumes, what it produces, and the boundary surfaces it exposes. Shapes are conceptual here; machine-checkable shapes live in `contracts/`.

### 4.1 Inputs (what IEG consumes)

#### 4.1.1 Primary input: admitted events from EB

IEG consumes EB-delivered admitted events (at-least-once; duplicates possible). In v0, IEG updates are driven by envelope-level fields and do not require parsing domain payloads.

#### 4.1.2 Required update fields (envelope-level)

For an event to mutate IEG projection state in v0, it must carry:

* **ContextPins:** `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* **event identity:** `event_id`
* **event time:** `event_time`
* **event targeting:** `event_type` (or schema targeting fields sufficient to route the update logic)
* **observed identifiers:** `observed_identifiers[]` (ObservedIdentifier objects)

If any required field is missing:

* IEG performs **no state mutation**
* IEG records an explicit failure outcome (counters + error category), and continues.

#### 4.1.3 Optional input: seed snapshots (not required in v0)

IEG may optionally accept pre-seeded entity/edge snapshots for a run/world, but v0 does not require them. If present, they are treated as input context and must be joinable to ContextPins.

---

### 4.2 Outputs (what IEG produces)

#### 4.2.1 Query surface (read-mostly API)

IEG produces a query surface for consumers (features/decisioning):

* identity resolution:

  * `resolve_identity(observed_identifiers, pins)`
* entity retrieval:

  * `get_entity_profile(entity_ref, pins)`
* neighborhood retrieval:

  * `get_neighbors(entity_ref, pins, edge_type?, depth=1)`

#### 4.2.2 Version marker on every response

Every response includes:

* ContextPins
* `graph_version` (monotonic applied watermark token)

This allows consumers to record “graph_version used”.

#### 4.2.3 Error responses (explicit failure posture)

If IEG cannot serve correct context:

* it returns an **ErrorResponse** with a `retryable` flag
* it does not invent substitute context

---

### 4.3 Boundary map (what IEG touches)

#### 4.3.1 Upstream sources

* EB stream `admitted_events` (primary)
* optional future named entity update events (names only in v0; payloads later)

#### 4.3.2 Downstream consumers

* Online Feature Plane (uses IEG as context source)
* Decision Fabric (directly or indirectly uses IEG context; records graph_version used)
* Observability/governance (reads health/lag, not business data)

#### 4.3.3 Storage substrate (implementation detail)

IEG relies on some storage substrate for entities/edges/indices. The choice is implementation freedom; semantic guarantees are pinned in IEG laws.

#### 4.3.4 Optional dependencies (explicitly not required in v0)

* IEG does not require consulting SR run facts or engine RO surfaces in v0. It relies on ContextPins carried in the event envelope.

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for IEG v0. These decisions are treated as fixed direction for the IEG specs and the v0 contract schema.

### 5.1 Scope and isolation

* IEG v0 is **run/world-scoped**.
* IEG state is isolated by ContextPins:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* No cross-run identity resolution, no global graph accumulation in v0.

---

### 5.2 Authority boundary

* IEG v0 is a **read-mostly projection** from admitted events.
* IEG does not rewrite upstream truth and does not “fix” events.
* IEG is authoritative only for its own projection artifacts: entities, edges, indices, and graph_version.

---

### 5.3 Event-driven update posture (envelope-driven)

* IEG consumes EB `admitted_events`.
* IEG v0 updates are driven by envelope-level fields only:

  * ContextPins
  * `event_id`
  * `event_time`
  * `event_type` (or schema targeting)
  * `observed_identifiers[]`
* IEG v0 does not parse domain payloads to mutate the graph.

---

### 5.4 Entity types (v0 vocabulary)

IEG v0 supports exactly these entity types:

* `account`
* `card`
* `customer`
* `merchant`
* `device`

No additional entity types are introduced in v0 without versioning the contracts/specs.

---

### 5.5 Canonical entity reference model

* Entities are referenced as:

  * `EntityRef = {entity_type, entity_id}`
* `entity_id` is deterministically minted within ContextPins.
* The encoding/hash method is implementation freedom, but determinism and stability across replay are mandatory.

---

### 5.6 Identity resolution posture (links/aliases only; no merges)

* IEG v0 supports:

  * creating and maintaining links/aliases from ObservedIdentifiers to EntityRefs
  * recording provenance for link creation
* IEG v0 explicitly does **not** support merges:

  * no collapsing two canonical EntityRefs into one
  * no silent merges

---

### 5.7 Edge vocabulary (v0 allowed edge types)

IEG v0 supports exactly these edge types:

* `account__has_card`
* `card__seen_on_device`
* `customer__has_account`
* `customer__seen_at_address`
* `merchant__operates_site`

Edges are directed by edge_type definition.

---

### 5.8 Edge identity and timestamp update rules

* Edge uniqueness key is:

  * `(src_entity_id, dst_entity_id, edge_type)` (direction implied)
* Edge timestamps update idempotently using event_time:

  * `first_seen_event_time = min(existing, event_time)`
  * `last_seen_event_time  = max(existing, event_time)`
* Each edge stores:

  * `provenance_ref` (opaque pointer to the causing event)

---

### 5.9 Update idempotency and out-of-order posture

* Each event produces an update_key derived from:

  * ContextPins + `event_id` + updater identity/version
* If update_key has already been applied:

  * applying it again is a no-op
* Out-of-order delivery is supported:

  * timestamp rules prevent disorder from corrupting edge history

---

### 5.10 graph_version meaning (basis pinned)

* Every ContextPins-scoped graph has a monotonic `graph_version`.
* graph_version basis is:

  * **per-partition applied offset watermark vector (map)** + stream_name.
* Consumers are expected to record “graph_version used” when making decisions/features.

---

### 5.11 Query surface (v0 operations and invariants)

IEG v0 supports exactly these operations:

* `resolve_identity(observed_identifiers, pins)`
* `get_entity_profile(entity_ref, pins)`
* `get_neighbors(entity_ref, pins, edge_type?, depth=1)`

Response invariants:

* responses include ContextPins and graph_version
* responses are joinable without guessing

---

### 5.12 Graph-derived outputs posture (no feature computation)

* IEG v0 provides retrieval indices/projections only.
* Feature computation remains owned by the Online Feature Plane.

---

### 5.13 Emissions posture (v0)

* IEG v0 does not emit graph marker events (`graph_version_advanced`, etc.) onto EB.
* graph_version is surfaced through query responses (and optionally a status query surface).

---

## 6) Modular breakdown (Level 1) and what each module must answer

> This is a **read-mostly projection plane**. The modular breakdown exists to force IEG’s semantics (scope, idempotent updates, link/alias posture, edges, versioning, query invariants) to be answered *somewhere*, while leaving storage and processing mechanics to the implementer.

### 6.0 Module map (one screen)

IEG is decomposed into 7 conceptual modules:

1. **Stream Update Consumer**
2. **Entity Canonical Store**
3. **Identity Resolution / Linking**
4. **Relationship / Edge Builder**
5. **Projections / Indices**
6. **Query Surface**
7. **Versioning & Lineage**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Stream Update Consumer

### Purpose

Consume admitted events from EB and apply replay-safe, idempotent updates to the projection.

### What it owns

* required envelope fields for updates (ContextPins, event_id, event_time, event_type, observed_identifiers)
* update_key generation and duplicate handling
* out-of-order posture enforcement (timestamp rules)
* basic failure categorization for update application (missing fields, malformed identifiers, etc.)

### Questions this module must answer

* What stream(s) are consumed in v0? (EB `admitted_events` only)
* What envelope fields are required to mutate the graph, and what happens when missing? (no mutation + explicit failure)
* How is update_key derived, and what constitutes “already applied”?
* What is the out-of-order posture and how is it enforced (min/max timestamp updates)?
* What is the failure posture: what is recorded when an event cannot be applied?

### Can be left to the implementer

* streaming vs micro-batch topology
* concurrency/partition assignment strategy
* checkpoint ownership details (consumer-owned vs coordination store)
* storage-layer transaction mechanics

### Local vs deployed operation

* **Local:** can consume from a file log or test stream; semantics identical
* **Deployed:** consumes from EB consumer groups; duplicates/out-of-order still handled correctly

---

## 6.2 Module 2 — Entity Canonical Store

### Purpose

Maintain canonical entity records and alias mappings within ContextPins.

### What it owns

* the v0 entity type vocabulary
* deterministic minting posture for entity_id
* representation of aliases (ObservedIdentifier → EntityRef)
* minimal entity record shape (thin attributes allowed)

### Questions this module must answer

* How are canonical EntityRefs represented and stored?
* How are entity_ids minted deterministically from first-seen identifiers?
* What alias kinds exist and how are they represented?
* What is the no-merge posture enforced by the store (no collapsing)?

### Can be left to the implementer

* physical storage model (tables/graph DB/KV)
* indexing strategy for identifier lookups
* caching and materialization

### Local vs deployed operation

* semantics identical; deployed will need stronger persistence and indexing

---

## 6.3 Module 3 — Identity Resolution / Linking

### Purpose

Resolve observed identifiers into canonical entity references using link/alias rules (no merges).

### What it owns

* v0 posture: links/aliases only; deterministic resolution rules
* provenance capture for link creation or link observation
* conflict handling without merges (record conflict; do not collapse)

### Questions this module must answer

* Given observed_identifiers, how are candidate EntityRefs produced deterministically?
* What happens when identifiers map to multiple entities (conflict posture)?
* What provenance is recorded for newly created links?
* How is deterministic behavior preserved under replay?

### Can be left to the implementer

* exact rule engine structure
* scoring/confidence fields (v0: deterministic only; no probabilistic merge)
* optimization of lookup paths

### Local vs deployed operation

* identical semantics; deployed prioritizes throughput/latency

---

## 6.4 Module 4 — Relationship / Edge Builder

### Purpose

Create and maintain edges between entities based on observed identifiers and link results.

### What it owns

* v0 allowed edge types and directionality
* edge uniqueness key and idempotency
* timestamp update rules (first_seen=min, last_seen=max)
* provenance_ref requirement on edges

### Questions this module must answer

* How are src/dst EntityRefs chosen for each edge type?
* How is edge uniqueness enforced (no duplicates)?
* How are edge timestamps updated under disorder?
* What provenance_ref is written and what does it point to?

### Can be left to the implementer

* edge storage structure (adjacency lists, edge tables, graph DB)
* edge indexing strategy
* storage compaction/cleanup (within run scope)

### Local vs deployed operation

* identical semantics; deployed may use heavier indexing

---

## 6.5 Module 5 — Projections / Indices

### Purpose

Maintain retrieval-optimized indices/projections for fast query answers (not feature computation).

### What it owns

* definition of which projections exist in v0 (neighbors-by-type, recent edges, etc.)
* guarantee that projections do not change semantic meaning of source entities/edges

### Questions this module must answer

* Which projections are maintained to support query operations?
* What are the freshness/consistency expectations (v0 can be simple)?
* How does the system ensure projections remain consistent with the canonical stores?

### Can be left to the implementer

* caching, materialization strategy
* index update scheduling
* storage optimization

### Local vs deployed operation

* local can be naive; deployed may require materialization and caching

---

## 6.6 Module 6 — Query Surface

### Purpose

Expose a versioned, joinable query interface to other loop components.

### What it owns

* the v0 query operations and required request/response invariants
* inclusion of ContextPins + graph_version on responses
* error response posture (explicit + retryable)

### Questions this module must answer

* What are the exact operations supported in v0 (resolve/profile/neighbors)?
* What are request requirements (ContextPins always present)?
* What must every response include (pins + graph_version)?
* What errors are returned when context cannot be served (and retryability)?

### Can be left to the implementer

* API transport (HTTP/gRPC/in-process)
* pagination, response size limits, caching
* auth implementation details (beyond posture in IEG5)

### Local vs deployed operation

* local may be in-process; deployed may be a service; semantics identical

---

## 6.7 Module 7 — Versioning & Lineage

### Purpose

Provide monotonic graph_version markers and provenance pointers for audit/replay.

### What it owns

* graph_version basis meaning (applied offset watermark vector)
* inclusion of graph_version on responses
* provenance_ref posture (opaque by-ref pointers)

### Questions this module must answer

* How is graph_version advanced as events are applied?
* What is the basis metadata for graph_version (per-partition offsets)?
* How are provenance_refs formed and what do they reference?
* How does versioning behave under replay/rebuild within a run scope?

### Can be left to the implementer

* graph_version encoding format
* storage and retrieval mechanism for watermarks
* tooling around surfacing graph version

### Local vs deployed operation

* semantics identical; deployed may include richer monitoring of watermarks/lag

---

## 6.8 Cross-module pinned items (summary)

Across all modules, IEG must ensure:

* run/world scoping via ContextPins (no cross-run accumulation)
* envelope-driven updates with required fields
* idempotent update_key application (duplicate-safe)
* disorder-safe edge timestamps (min/max event_time)
* no merges in v0 (links/aliases only)
* fixed v0 entity and edge vocabularies
* query responses always include ContextPins + graph_version
* explicit ErrorResponse posture; no invented context

---

## 7) Determinism and replay posture

> This section pins what “correct IEG behaviour” means for determinism and replay safety: idempotent application, disorder safety, and versioned auditability.

### 7.1 What “deterministic IEG” means (scope)

IEG is deterministic if, given the same:

* admitted event log (within a ContextPins scope),
* pinned v0 vocabularies (entity types, edge types),
* and pinned update semantics (update_key + disorder rules),

IEG produces the same:

* canonical entity/alias mappings,
* edge set (unique edges),
* edge timestamps (first/last seen),
* and graph_version progression meaning.

Determinism does **not** require:

* identical ingestion timing,
* identical internal batching/concurrency,
* identical storage engine,
  as long as the observable state and query semantics are equivalent.

---

### 7.2 Duplicate delivery posture (idempotency)

Because EB is at-least-once:

* the same event may arrive multiple times

IEG enforces idempotency by:

* deriving an **update_key** from ContextPins + event_id + updater identity/version
* recording applied update_keys
* treating re-application of the same update_key as a **no-op**

This ensures duplicates do not create duplicate entities/edges or overwrite timestamps incorrectly.

---

### 7.3 Disorder posture (out-of-order events)

IEG must be safe under out-of-order delivery.

For edges, disorder safety is pinned by:

* updating timestamps using event_time monotonic rules:

  * `first_seen_event_time = min(existing, event_time)`
  * `last_seen_event_time  = max(existing, event_time)`

This ensures late-arriving events extend history appropriately without corrupting earlier timestamps.

---

### 7.4 Replay posture: rebuilding or re-applying within a run/world scope

Replay in IEG context means:

* re-consuming a portion (or all) of the admitted event log for a ContextPins scope
* re-applying updates deterministically

IEG replay safety is ensured by:

* idempotent update_key application (duplicates no-op)
* disorder-safe timestamp updates
* fixed vocabularies and deterministic entity_id minting

IEG does not require special “replay mode”; reprocessing is safe by construction.

---

### 7.5 graph_version posture under replay

graph_version is a monotonic token whose basis is pinned as:

* per-partition applied offset watermark vector + stream_name

Under replay/rebuild, graph_version must behave consistently:

* applying events to the same watermark basis yields a graph_version that accurately represents that basis
* encoding format may differ, but basis meaning must not.

Consumers must be able to record “graph_version used” and interpret it as “context as of applied offsets”.

---

### 7.6 Provenance posture (no silent linking decisions)

IEG records provenance for relationship updates:

* edges carry `provenance_ref` pointing to the causing event (opaque ref in v0)

This ensures identity/link decisions are explainable without requiring merges.

---

### 7.7 Determinism acceptance scenarios (conceptual checklist)

IEG should be considered deterministic enough when it can satisfy:

* duplicate delivery of the same event → no duplicate entities/edges; update is no-op
* out-of-order events → edge timestamps reflect min/max event_time correctly
* replaying a window of admitted events → produces the same entity/edge projection
* resolve_identity responses are joinable via ContextPins and include graph_version
* graph_version is monotonic and corresponds to applied stream watermarks
* failures return explicit ErrorResponse (retryable flag), not invented context

---

## 8) Contracts philosophy and boundary surfaces

> IEG contracts exist to pin the **query boundary** and core graph object shapes, without duplicating the Canonical Event Contract Pack. Contracts define *shape*; specs define *behaviour* (link posture, idempotency, version meaning).

### 8.1 What a “contract” means for IEG

For IEG, a contract is a machine-readable definition of:

* what callers must send to query IEG (requests)
* what IEG returns (responses, including graph_version and pins)
* the core object shapes used across responses (EntityRef/Record, EdgeRecord, ObservedIdentifier)
* error response shape (explicit failure posture)

Contracts exist to prevent:

* different consumers expecting different query semantics
* missing ContextPins or graph_version (breaking audit/replay)
* ambiguous object identity or edge semantics across components

---

### 8.2 Contracts belong at boundaries (not per internal module)

IEG is modular internally (consumer, store, linker, edge builder, indices, query layer), but these modules are not separate deployable boundaries in v0. Therefore:

* internal module semantics live in the specs (IEG1–IEG5)
* contracts exist only for what external components integrate with: query boundary objects

---

### 8.3 Boundary surfaces IEG must pin contractually

IEG has one primary contract boundary in v0:

1. **Query surface**

* `resolve_identity` request/response
* `get_entity_profile` request/response
* `get_neighbors` request/response
* shared invariants: ContextPins + graph_version in every response

Optionally, a second boundary may be added later:

* “graph status” / “watermark” endpoint shape (not required in v0; can be derived via responses)

IEG v0 does not emit marker events to EB, so there is no emission contract boundary in v0.

---

### 8.4 v0 contract strategy: keep consumed event payloads opaque

IEG consumes admitted events to build its projection, but in v0:

* IEG contracts do not define or validate consumed event payload schemas
* event provenance is represented by `provenance_ref` as an **opaque by-ref pointer**

This avoids duplicating the Canonical Event Contract Pack prematurely.

---

### 8.5 Avoiding ambiguity: validation targeting

IEG contract objects are self-describing:

* `kind` + `contract_version`

This aligns with SR/IG/EB and prevents consumers from guessing schema targets.

---

### 8.6 Versioning and compatibility posture (conceptual)

* contract filename includes explicit version (`*_v0.schema.json`)
* responses declare contract_version
* breaking changes require:

  * new version (v1)
  * explicit compatibility plan
  * updates to IEG specs documenting impacts (entity types, edge types, graph_version basis)

---

## 9) IEG contract pack overview (v0-thin)

> This section describes the **contract artifact** IEG will ship with in v0, what it covers, and how other components use it. The v0 contract pins the query boundary and core graph object shapes.

### 9.0 Contract pack inventory (v0 target set)

IEG v0 ships **one** machine-checkable schema file:

* `contracts/ieg_public_contracts_v0.schema.json`

This file contains `$defs` for:

* ContextPins + GraphVersion
* ObservedIdentifier
* EntityRef/EntityRecord
* EdgeRecord
* Query requests/responses
* ErrorResponse

---

## 9.1 `contracts/ieg_public_contracts_v0.schema.json`

### 9.1.1 What this file is for

This schema defines the shapes that consumers must rely on when querying IEG:

* how to request identity resolution and context
* what invariants responses must satisfy
* how entities and edges are represented
* what error shapes look like

It does not define the canonical event payload schemas consumed from EB.

---

### 9.1.2 Target `$defs` (conceptual list)

#### 1) `ContextPins`

**Required:**

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

Optional:

* `window_key` (only if the platform uses it consistently)

---

#### 2) `GraphVersion`

**Required:**

* `graph_version` (string token)

Optional basis metadata (opaque but present):

* `stream_name`
* `watermark_basis` (object; per-partition offsets map, or an opaque representation of it)

**Pinned meaning:** monotonic applied offset watermark vector basis.

---

#### 3) `ObservedIdentifier`

**Required:**

* `id_kind`
* `id_value`

Optional:

* `namespace`/`issuer`

---

#### 4) `EntityRef`

**Required:**

* `entity_type` (enum; v0 fixed set)
* `entity_id` (string)

---

#### 5) `EntityRecord` (thin)

**Required:**

* `entity_ref` (EntityRef)

Optional:

* `attributes` (object)
* `as_of_event_time` (timestamp)

---

#### 6) `EdgeRecord` (thin)

**Required:**

* `src` (EntityRef)
* `dst` (EntityRef)
* `edge_type` (enum; v0 fixed set)
* `first_seen_event_time`
* `last_seen_event_time`

Optional:

* `provenance_ref` (opaque ref)

---

#### 7) `ResolveIdentityRequest` / `ResolveIdentityResponse`

Request required:

* `kind`, `contract_version`
* `pins` (ContextPins)
* `observed_identifiers[]` (ObservedIdentifier list)

Response required:

* `kind`, `contract_version`
* `pins` (ContextPins)
* `graph_version` (GraphVersion)
* `entity_refs[]` (EntityRef list)
* `provenance` (thin object; optional content, but must exist if links were created)

---

#### 8) `GetEntityProfileRequest` / `GetEntityProfileResponse`

Request required:

* `kind`, `contract_version`
* `pins`
* `entity_ref`

Response required:

* `kind`, `contract_version`
* `pins`
* `graph_version`
* `entity_record` (EntityRecord)

---

#### 9) `GetNeighborsRequest` / `GetNeighborsResponse`

Request required:

* `kind`, `contract_version`
* `pins`
* `entity_ref`
  Optional:
* `edge_type` filter
* `depth` (v0 default 1; max depth policy pinned in specs)

Response required:

* `kind`, `contract_version`
* `pins`
* `graph_version`
* `neighbors[]` (EntityRef list)
* `edges[]` (EdgeRecord list)

---

#### 10) `ErrorResponse`

**Required:**

* `kind`, `contract_version`
* `pins` (if known)
* `error_code`
* `message` (short)
* `retryable` (boolean)

Optional:

* `graph_version` (if known)

---

### 9.1.3 Validation targeting rule

IEG objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

## 9.2 Contracts vs specs (division of labour)

### 9.2.1 Contracts cover (shape/structure)

* required fields, types, and enums
* fixed v0 vocabularies for entity_type and edge_type
* response invariants: pins + graph_version always present
* error shape and retryable posture field

### 9.2.2 Specs cover (behaviour/invariants)

* link/alias posture (no merges)
* deterministic entity_id minting rules (conceptual)
* update_key semantics and duplicate handling
* disorder-safe edge timestamp rules
* graph_version basis meaning and how it advances
* depth limits and consistency posture for queries
* ops posture (lag, failures) and consumer guidance

---

## 9.3 Naming and versioning posture (conceptual)

* contract filename includes explicit version (`*_v0.schema.json`)
* emitted responses declare contract_version
* breaking changes:

  * new version (v1)
  * explicit compatibility plan
  * specs updated to reflect new behaviour/vocab/version semantics

---

## 10) Addressing, naming, and discoverability (conceptual)

> This section defines the *idea* of how IEG state and provenance are discoverable: how callers obtain graph_version, how provenance_ref points to source events, and how local vs deployed environments differ without changing semantics.

### 10.1 Design goals (why discoverability matters)

IEG discoverability must support:

* **Auditability:** consumers can record which graph_version was used and later explain it.
* **Replayability:** it is possible to relate a graph_version to a stream watermark basis.
* **Traceability:** edges/links can point back to the source event via provenance_ref.
* **Environment independence:** local vs deployed changes locator types, not meaning.

---

### 10.2 graph_version discoverability

In v0, graph_version is surfaced through:

* query responses (every response includes graph_version)

Optionally (not required in v0), IEG may expose a “status” query surface:

* “what is the current graph_version for ContextPins?”

**Pinned rule:** consumers do not need to scan internal storage; graph_version is always returned.

---

### 10.3 Provenance discoverability (`provenance_ref`)

Edges carry `provenance_ref`:

* an opaque by-ref pointer to the causing event

In v0, provenance_ref is not required to be “human friendly”; it must be:

* stable within the ContextPins scope
* resolvable by operators/tooling given appropriate access

Typical provenance ref targets (conceptual):

* EB position (`stream_name`, `partition_id`, `offset`)
* or an event store locator
* or a canonical event envelope reference (in v1 once Canonical Event Pack exists)

**Pinned rule:** no silent linking decisions; if an edge exists, its cause must be attributable via provenance_ref.

---

### 10.4 Naming conventions (conceptual)

IEG naming must be stable enough for downstream integration:

* entity types and edge types are fixed vocabularies in v0
* error codes are stable enough to be operationally meaningful

Implementation may add additional internal names, but contract-visible names remain stable.

---

### 10.5 Local vs deployed discoverability

* **Local:** provenance_ref may point to a file log position or local EB simulation offsets.
* **Deployed:** provenance_ref may point to EB offsets or object-store keys.

**Rule:** regardless of locator type, provenance semantics remain:

* “this edge/link is attributable to that admitted event”

Similarly for graph_version:

* local may encode watermarks as simple counters
* deployed may encode per-partition offset maps
  but the basis meaning is the same.

---

### 10.6 Optional indexing/discovery aids (implementation freedom)

IEG may maintain optional indices to support:

* “find entity by identifier”
* “find latest neighbors for entity”
* “find edges by type”
* “explain why link exists” (provenance browsing)

These are implementation aids and do not change pinned query semantics.

---

## 11) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for IEG docs and contracts. The goal is a **single, deep reading surface** for IEG design, plus a **minimal v0 query-boundary contract**.

### 11.1 Target location in repo

Conceptually, IEG lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/identity_entity_graph/`

This folder should be self-contained: a new contributor should understand IEG by starting here.

---

### 11.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ identity_entity_graph/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ IEG1_charter_and_boundaries.md
         │  ├─ IEG2_entity_identifier_edge_model.md
         │  ├─ IEG3_stream_consumption_and_update_semantics.md
         │  ├─ IEG4_query_surface_and_versioning.md
         │  └─ IEG5_ops_security_acceptance.md
         │
         └─ contracts/
            └─ ieg_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; v0 needs only **one** schema file here.

---

### 11.3 What each file is for (intent)

#### `README.md`

* Entry point: what IEG is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (roadmap)
  * `specs/` reading order (IEG1–IEG5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This roadmap document:

  * IEG purpose in platform
  * IEG laws (run-scoped, no merges, idempotent updates, versioned queries)
  * designer-locked v0 decisions
  * modular breakdown + questions per module
  * v0 contract philosophy (query boundary only)
  * discoverability concepts (graph_version + provenance_ref)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behaviour/invariants
  * contract schema defines request/response shapes
* Non-negotiables:

  * run/world scoped via ContextPins
  * envelope-driven updates; required fields or no mutation
  * idempotent update_key; disorder-safe edge timestamps
  * links/aliases only; no merges in v0
  * every response includes graph_version + is joinable
  * explicit ErrorResponse; no invented context

#### `specs/`

* IEG1–IEG5 are the eventual binding-ish IEG design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `ieg_public_contracts_v0.schema.json` pins the query boundary objects.

---

### 11.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (design direction + pinned decisions)
3. `specs/IEG1_...` → `specs/IEG5_...` (behaviour/invariants)
4. `contracts/ieg_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

### 11.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge IEG1–IEG5 into fewer docs once stable.
* Add `contracts/README.md` only if you need a brief note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders under deadline.

---

## 12) What the eventual spec docs must capture (mapping from this concept doc)

> This section bridges the IEG conceptual roadmap into the **actual IEG spec docs** (IEG1–IEG5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 12.0 Mapping rule (how to use this section)

For every IEG “law” and “designer-locked” decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in IEG1–IEG5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 12.1 IEG1 — Charter & boundaries

### IEG1 must capture

* IEG purpose as a **read-mostly context plane** for the loop
* authority boundaries:

  * projection-only; does not mutate upstream truth
  * run/world scoped; no cross-run accumulation in v0
* IEG laws in enforceable prose:

  * idempotent updates
  * disorder-safe timestamp updates
  * no merges (links/aliases only)
  * joinability via ContextPins
  * every response includes graph_version
  * explicit failure posture (ErrorResponse)
* in-scope vs out-of-scope declarations:

  * no global graph
  * no feature computation in IEG v0
  * no emission events in v0

### IEG1 may leave to the implementer

* internal service boundaries and code layout
* infra/deployment choices

---

## 12.2 IEG2 — Entity, Identifier, and Edge Model

### IEG2 must capture

* fixed v0 vocabularies:

  * entity types (account/card/customer/merchant/device)
  * edge types (the pinned list)
* EntityRef rules:

  * `{entity_type, entity_id}` and determinism/stability requirement
* deterministic entity_id minting posture (conceptual):

  * minted from first-seen primary identifier per entity type
  * stable across replay
* ObservedIdentifier model:

  * id_kind/id_value (+ namespace posture)
* alias/link model:

  * ObservedIdentifier → EntityRef representation
  * no merges posture enforcement
* EdgeRecord invariants:

  * uniqueness key
  * first_seen/last_seen event_time rules
  * provenance_ref requirement

### IEG2 may leave to the implementer

* physical storage layout
* indexing and caching strategy
* attribute enrichment beyond thin record posture

---

## 12.3 IEG3 — Stream consumption & update semantics

### IEG3 must capture

* consumed stream(s) in v0:

  * EB `admitted_events`
* required envelope fields for graph mutation:

  * ContextPins, event_id, event_time, event_type, observed_identifiers[]
* update_key posture:

  * derived from ContextPins + event_id + updater id/version
  * duplicates are no-op
* disorder posture:

  * min/max event_time update rules for edges
* failure handling:

  * missing required fields → no mutation + explicit failure recorded
* replay posture:

  * reprocessing is safe by construction (idempotency + disorder rules)

### IEG3 may leave to the implementer

* streaming vs micro-batch topology
* consumer group coordination and checkpointing mechanics
* storage transaction boundaries

---

## 12.4 IEG4 — Query surface & versioning

### IEG4 must capture

* v0 query operations:

  * resolve_identity
  * get_entity_profile
  * get_neighbors (depth=1 default; max depth policy)
* request invariants:

  * ContextPins always required
* response invariants:

  * ContextPins echoed and graph_version always present
* graph_version meaning:

  * basis = per-partition applied offset watermark vector + stream_name
  * monotonic advancement posture
* provenance posture:

  * edges include provenance_ref (opaque by-ref)
* consistency posture:

  * v0 may be simple (e.g., “eventually consistent”), but must be stated explicitly

### IEG4 may leave to the implementer

* API transport (HTTP/gRPC/in-process)
* pagination/caching strategies
* endpoint deployment model (service vs library)

---

## 12.5 IEG5 — Ops, security & acceptance

### IEG5 must capture

* observability minimums:

  * stream lag/watermarks
  * update failure counts
  * resolution success rates
  * query latency
* explicit availability posture:

  * what callers should do if IEG is unavailable (ErrorResponse retryable semantics)
* access control posture:

  * who can query and who can consume updates (conceptual)
* acceptance scenarios (tests-as-intent):

  * duplicate event → no duplicate entities/edges
  * out-of-order events → timestamps remain correct
  * replay window → consistent projection at same watermark basis
  * query responses always include ContextPins + graph_version
  * failures return ErrorResponse (no invented context)

### IEG5 may leave to the implementer

* exact IAM implementation
* dashboards/alerts tooling
* deployment/infra specifics

---

## 12.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* ContextPins + GraphVersion objects
* fixed enums for entity_type and edge_type (v0)
* ObservedIdentifier, EntityRef, EdgeRecord, thin EntityRecord
* request/response shapes for the three v0 query operations
* ErrorResponse shape (retryable flag)
* validation targeting (`kind`, `contract_version`)

### Specs must include

* deterministic entity_id minting posture (conceptual)
* update_key + idempotency semantics
* disorder-safe timestamp update rules
* no-merge posture enforcement
* graph_version basis meaning and advancement posture
* consistency and failure/availability posture

---

## 12.7 Minimal completeness standard (so IEG is implementable)

IEG is “spec-ready” for implementation when IEG1–IEG5 collectively pin:

* run/world scoping via ContextPins (no cross-run)
* v0 entity/edge vocabularies
* envelope-driven update inputs + update_key idempotency
* disorder-safe timestamp rules
* query operations + response invariants (pins + graph_version)
* graph_version basis meaning
* explicit ErrorResponse posture + minimal ops signals

Everything else can remain implementer freedom.

---

## 13) Acceptance questions and “Definition of Done”

> This section is the conceptual **ship checklist** for IEG v0: the questions IEG must answer and the minimal behavioural scenarios that indicate IEG is correct enough to implement and integrate into the loop.

### 13.1 Acceptance questions (IEG must answer these unambiguously)

1. **What context am I using?**

* Does every IEG response include ContextPins and `graph_version` so a decision can record “graph_version used”?

2. **Is the graph scoped correctly?**

* Does IEG prevent cross-run/world leakage (ContextPins isolation)?

3. **What does identity resolution return?**

* Given observed identifiers, does `resolve_identity` deterministically return EntityRefs (or an explicit error)?

4. **Can I retrieve profiles and neighbors safely?**

* Do `get_entity_profile` and `get_neighbors` return joinable, versioned results?

5. **How does IEG behave under duplicates?**

* If the same admitted event is delivered twice, do we avoid duplicate entities/edges and treat the second apply as a no-op?

6. **How does IEG behave under out-of-order delivery?**

* Do edge timestamps remain correct (first_seen=min, last_seen=max event_time) even when events arrive out of order?

7. **What does `graph_version` mean?**

* Can `graph_version` be interpreted as an applied-stream watermark basis (per-partition offsets), and is it monotonic?

8. **Can I trace why a link/edge exists?**

* Do edges carry provenance_ref so identity/link decisions are attributable?

9. **What happens if IEG is unavailable or behind?**

* Does IEG return explicit ErrorResponse with retryable flag rather than inventing context?

10. **Does replay/rebuild produce the same projection?**

* If we reprocess the same admitted log window, do we get the same entity/edge projection and a graph_version that correctly reflects the watermark basis?

---

### 13.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Run/world scoping enforced

**Given**

* events from two different ContextPins scopes

**Expect**

* no entity/edge state crosses scopes
* queries scoped to pins only see their own entities/edges

---

#### DoD-2: Duplicate delivery → no duplicate entities/edges

**Given**

* an admitted event delivered twice (same ContextPins + event_id)

**Expect**

* update_key causes second application to be a no-op
* no duplicate edges or alias mappings are created

---

#### DoD-3: Out-of-order delivery → timestamps remain correct

**Given**

* two events affecting the same edge arrive out of order (event_time T2 then T1)

**Expect**

* `first_seen_event_time` becomes min(T1,T2)
* `last_seen_event_time` becomes max(T1,T2)
* edge uniqueness remains preserved

---

#### DoD-4: Identity resolution returns deterministic EntityRefs

**Given**

* a set of ObservedIdentifiers for a transaction event

**Expect**

* resolve_identity returns a deterministic list of EntityRefs (and graph_version)
* no merges occur; links/aliases only

---

#### DoD-5: Query responses are always joinable and versioned

**Given**

* any successful query response

**Expect**

* response includes ContextPins and graph_version
* callers can record “graph_version used” without additional lookups

---

#### DoD-6: Provenance is recorded for edges

**Given**

* an edge exists in the graph

**Expect**

* edge record includes a provenance_ref attributable to the causing admitted event

---

#### DoD-7: Replay window rebuild is safe by construction

**Given**

* reprocessing the same admitted event window for the same ContextPins scope

**Expect**

* the resulting entity/edge projection is equivalent
* graph_version corresponds to the applied watermark basis (monotonic)

---

#### DoD-8: Explicit failure posture (no invented context)

**Given**

* IEG cannot serve correct context (unavailable, corrupted state, etc.)

**Expect**

* returns ErrorResponse with retryable flag
* does not fabricate partial context as a substitute

---

### 13.3 Minimal deliverables required to claim “DoD satisfied”

To claim IEG meets DoD at v0 conceptual level, you should be able to show:

* successful resolve_identity + profile + neighbors query responses (with pins + graph_version)
* duplicate delivery test demonstrating no duplicate edges/entities
* out-of-order delivery test demonstrating correct first/last seen timestamps
* edge record example showing provenance_ref
* graph_version example showing watermark basis concept (even if encoded)
* explicit ErrorResponse example

---

## 14) Open decisions log (v0 residuals only)

> These are the only remaining decisions for IEG v0 that are **not** already designer-locked. Everything else is either pinned above or explicitly implementation freedom.

### DEC-IEG-001 — Primary identifier selection per entity type (minting input)

* **Question:** for each entity_type, which ObservedIdentifier `id_kind` is treated as the “primary” minting input?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG2 (Entity/Identifier model)
* **Note:** the determinism requirement is pinned; this decision only chooses the primary `id_kind` per type.

### DEC-IEG-002 — Entity ID encoding convention (token format)

* **Question:** what is the canonical encoding of `entity_id` (prefixing, hashing/encoding format)?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG2
* **Constraint:** must remain deterministic and stable across replay.

### DEC-IEG-003 — graph_version token encoding (string format)

* **Question:** how is the graph_version string token encoded (format), given the pinned basis meaning (watermark vector)?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG4 (Versioning)
* **Constraint:** token must represent the pinned watermark basis meaning; encoding is free.

### DEC-IEG-004 — Watermark persistence posture (where basis is stored)

* **Question:** where is the applied watermark basis stored and retrieved from (service state vs durable store)?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG3/IEG5
* **Constraint:** must support monotonic advancement and auditability.

### DEC-IEG-005 — Consistency posture for queries (v0 exact wording)

* **Question:** what is the explicit consistency promise for queries in v0?

  * e.g., “eventually consistent projection; graph_version indicates applied offsets”
* **Status:** OPEN (v0 residual)
* **Close in:** IEG4
* **Constraint:** must not contradict replay/idempotency and version semantics.

### DEC-IEG-006 — Error code vocabulary (v0 minimal set)

* **Question:** what is the minimal stable set of ErrorResponse `error_code` values?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG4/IEG5
* **Constraint:** error codes must be stable enough for callers to implement fallback logic.

### DEC-IEG-007 — Depth limit for `get_neighbors` (v0 cap)

* **Question:** what maximum `depth` is allowed in v0 (default=1)?
* **Status:** OPEN (v0 residual)
* **Close in:** IEG4
* **Constraint:** keep v0 conservative to avoid runaway query costs.

### DEC-IEG-008 — Provenance reference form (EB offset vs artifact ref)

* **Question:** what exact form does `provenance_ref` take in v0?

  * EB position `{stream, partition, offset}` vs a generic ArtifactRef/Locator
* **Status:** OPEN (v0 residual)
* **Close in:** IEG2/IEG4
* **Constraint:** must be stable and resolvable with appropriate access.

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate the v0 query boundary and object shapes.
> They use `kind` + `contract_version` for unambiguous schema targeting.
> `graph_version` is shown with an explicit watermark basis map (per-partition offsets) to reflect the pinned meaning.

---

### A.1 Example — `ResolveIdentityRequest`

```json
{
  "kind": "resolve_identity_request",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "observed_identifiers": [
    { "id_kind": "account_ref", "id_value": "acct_00001234" },
    { "id_kind": "pan_hash",    "id_value": "panh_9f2c..." },
    { "id_kind": "device_fp",   "id_value": "devfp_aa11bb22" }
  ]
}
```

---

### A.2 Example — `ResolveIdentityResponse`

```json
{
  "kind": "resolve_identity_response",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "graph_version": {
    "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
    "stream_name": "admitted_events",
    "watermark_basis": {
      "partition_0": 9812400,
      "partition_1": 10012055
    }
  },

  "entity_refs": [
    { "entity_type": "account", "entity_id": "e_account_7c31d9" },
    { "entity_type": "card",    "entity_id": "e_card_1a0b22" },
    { "entity_type": "device",  "entity_id": "e_device_f09c81" }
  ],

  "provenance": {
    "note": "v0 links/aliases only; no merges",
    "created_links": 0
  }
}
```

---

### A.3 Example — `GetEntityProfileRequest`

```json
{
  "kind": "get_entity_profile_request",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "entity_ref": { "entity_type": "account", "entity_id": "e_account_7c31d9" }
}
```

---

### A.4 Example — `GetEntityProfileResponse`

```json
{
  "kind": "get_entity_profile_response",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "graph_version": {
    "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
    "stream_name": "admitted_events",
    "watermark_basis": {
      "partition_0": 9812400,
      "partition_1": 10012055
    }
  },

  "entity_record": {
    "entity_ref": { "entity_type": "account", "entity_id": "e_account_7c31d9" },
    "attributes": {
      "account_status": "active"
    },
    "as_of_event_time": "2026-01-03T12:35:10Z"
  }
}
```

---

### A.5 Example — `GetNeighborsResponse` (depth=1)

```json
{
  "kind": "get_neighbors_response",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "graph_version": {
    "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
    "stream_name": "admitted_events",
    "watermark_basis": {
      "partition_0": 9812400,
      "partition_1": 10012055
    }
  },

  "neighbors": [
    { "entity_type": "card", "entity_id": "e_card_1a0b22" },
    { "entity_type": "card", "entity_id": "e_card_4b0f90" }
  ],

  "edges": [
    {
      "src": { "entity_type": "account", "entity_id": "e_account_7c31d9" },
      "dst": { "entity_type": "card", "entity_id": "e_card_1a0b22" },
      "edge_type": "account__has_card",
      "first_seen_event_time": "2026-01-03T10:01:00Z",
      "last_seen_event_time": "2026-01-03T12:35:10Z",
      "provenance_ref": {
        "producer": "event_bus",
        "kind": "eb_position",
        "uri": "admitted_events/partition=0/offset=9812399"
      }
    }
  ]
}
```

---

### A.6 Example — `EdgeRecord` (standalone)

```json
{
  "src": { "entity_type": "card", "entity_id": "e_card_1a0b22" },
  "dst": { "entity_type": "device", "entity_id": "e_device_f09c81" },
  "edge_type": "card__seen_on_device",
  "first_seen_event_time": "2026-01-03T08:00:00Z",
  "last_seen_event_time": "2026-01-03T12:34:56Z",
  "provenance_ref": {
    "producer": "event_bus",
    "kind": "eb_position",
    "uri": "admitted_events/partition=1/offset=10012010"
  }
}
```

---

### A.7 Example — `ErrorResponse` (retryable)

```json
{
  "kind": "error_response",
  "contract_version": "ieg_public_contracts_v0",

  "pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "error_code": "IEG_UNAVAILABLE",
  "message": "Identity & Entity Graph is temporarily unavailable",
  "retryable": true,

  "graph_version": {
    "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
    "stream_name": "admitted_events"
  }
}
```

---

## Appendix B — ASCII sequences (update apply, duplicate no-op, disorder timestamp update, query response)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/upsert
> Notes like `[idemp=…]` show the update_key/idempotency concept.
> `event_time` drives edge timestamps; apply time/ingest time is not substituted for event_time.

---

### B.1 Update apply (admitted event → idempotent upsert + edges + graph_version advance)

```
Participants:
  EB | IEG(Update Consumer) | IEG(Linker) | IEG(Entity Store) | IEG(Edge Store) | IEG(Versioning)

EB --> IEG(Update Consumer): Delivered admitted_event (ContextPins, event_id, event_time, observed_identifiers, event_type)

IEG(Update Consumer): derive update_key [idemp=H(ContextPins,event_id,updater_v)]
IEG(Update Consumer) --> IEG(Update Consumer): check update_key already applied?

(if not applied)
  IEG(Linker): resolve observed_identifiers -> EntityRefs (links/aliases only; no merges)
  IEG(Entity Store) => IEG(Entity Store): upsert EntityRecords (deterministic ids, alias mappings)
  IEG(Edge Store)   => IEG(Edge Store): upsert edges (unique by src,dst,edge_type)
                         - first_seen = min(existing, event_time)
                         - last_seen  = max(existing, event_time)
                         - provenance_ref set to EB position (partition/offset)
  IEG(Versioning)   => IEG(Versioning): advance watermark basis (per-partition applied offset)
  IEG(Update Consumer) => IEG(Update Consumer): mark update_key applied

(if already applied)
  no-op (duplicate safe)
```

---

### B.2 Duplicate delivery no-op (same event redelivered)

```
EB --> IEG(Update Consumer): Delivered admitted_event (same ContextPins + same event_id)

IEG(Update Consumer): derive update_key [idemp=H(ContextPins,event_id,updater_v)]
IEG(Update Consumer) --> IEG(Update Consumer): update_key already applied = true

IEG(Update Consumer): NO-OP
  - no new entities
  - no new edges
  - no timestamp regression
```

---

### B.3 Disorder timestamp update (late event extends history without corruption)

```
Assume an edge already exists: account__has_card
Existing:
  first_seen_event_time = T1
  last_seen_event_time  = T2   (T2 > T1)

Case: out-of-order delivery arrives with event_time = T0 (T0 < T1)

EB --> IEG(Update Consumer): Delivered admitted_event(event_time=T0)

IEG(Edge Store) => IEG(Edge Store): upsert edge
  first_seen_event_time = min(T1, T0) = T0   (moves earlier)
  last_seen_event_time  = max(T2, T0) = T2   (unchanged)

Case: late event arrives with event_time = T3 (T3 > T2)
  first_seen stays T0/T1, last_seen becomes T3
```

---

### B.4 Query response (versioned, joinable context)

```
Participants:
  Caller (Features/Decision Fabric) | IEG(Query Surface) | IEG(Stores/Indices) | IEG(Versioning)

Caller -> IEG(Query Surface): resolve_identity(observed_identifiers, ContextPins)

IEG(Query Surface) --> IEG(Stores/Indices): lookup aliases/links and neighbors
IEG(Versioning): read current graph_version basis for ContextPins

IEG(Query Surface) -> Caller: ResolveIdentityResponse
  - echoes ContextPins
  - includes graph_version (monotonic token + basis metadata)
  - returns EntityRefs (+ optional provenance summary)
```

---
