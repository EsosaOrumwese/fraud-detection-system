# OFP — Conceptual Spec Design Doc (non-spec) — Section Header Plan

## 0) Document metadata

### 0.1 Document header

* **Title:** *Online Feature Plane (OFP) — Conceptual Spec Design (v0)*
* **Plane:** Real-Time Decision Loop / Online Feature Plane
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final
* **Version:** v0.x
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Capture the **designer-locked v0 intent** for OFP in one place (no drift).
* Provide the roadmap for writing:

  * OFP1–OFP5 specs (behaviour/invariants)
  * `contracts/ofp_public_contracts_v0.schema.json` (machine-checkable boundary shapes)
* Ensure implementer freedom stays in implementation mechanics, not behaviour.

### 0.3 Audience and prerequisites

* **Primary:** you (designer), Codex (implementer)
* **Secondary:** Decision Fabric, Degrade Ladder, Decision Log, Observability owners
* **Prerequisites:**

  * IG admits canonical events
  * EB delivers at-least-once; duplicates/out-of-order possible
  * IEG serves run-scoped, versioned identity context (`graph_version`)

### 0.4 How to use this document

* This is **directional alignment** and a **question map**, not binding spec text.
* Normative truth lives in:

  * OFP specs (OFP1–OFP5), and
  * OFP contract schema file(s)
* Every pinned decision here must appear later as a closed decision in specs/contracts.

### 0.5 Scope and non-scope

* **In scope:** feature keying, group registry/versioning, freshness semantics, idempotent updates, provenance + snapshot hashing, serving surface.
* **Out of scope:** exact feature catalogue contents (beyond v0 minimal set), infra choices, exact compute engine, deployment topology.

### 0.6 Proposed repo placement (conceptual)

* `docs/model_spec/real-time_decision_loop/online_feature_plane/CONCEPTUAL.md`
* Related:

  * `specs/OFP1_...` → `specs/OFP5_...`
  * `contracts/ofp_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why the Online Feature Plane exists

The Online Feature Plane (OFP) is the platform’s **real-time context compiler + serving surface**. Its job is to produce **keyed, freshness-governed feature snapshots** for real-time decisioning, with enough provenance to explain and later reproduce “what we knew at decision time.”

One sentence: **“Given ContextPins + FeatureKeys + FeatureGroup versions + as_of_time, return a deterministic feature snapshot with explicit freshness and complete provenance.”**

---

### 1.2 Where OFP sits relative to IG, EB, IEG, and Decision Fabric

* **Ingestion Gate (IG)** admits canonical events and enforces envelope correctness.
* **Event Bus (EB)** durably distributes admitted events (at-least-once; duplicates/out-of-order possible).
* **Identity & Entity Graph (IEG)** provides run-scoped identity context and graph_version for provenance.
* **OFP** maintains online aggregate/state from admitted events, consults IEG when needed for canonical keying/context, and serves feature snapshots.
* **Decision Fabric** consumes feature snapshots + provenance and must record what it used.

OFP does not replace IEG; it compiles **feature context** on top of EB + IEG.

---

### 1.3 What OFP is system-of-record for (and what it is not)

OFP is authoritative for:

* **feature snapshot contents** returned at serve time
* **feature provenance bundles** (versions, freshness, input basis, graph_version)
* **deterministic snapshot identity** (`feature_snapshot_hash`)

OFP is not authoritative for:

* event validity (IG owns that)
* stream delivery and replay mechanics (EB owns that)
* identity truth or linking (IEG owns that)
* decision outputs or actions (Decision Fabric / Actions own that)

---

### 1.4 Why OFP uses explicit “as_of_time_utc” (no hidden now)

OFP requires `as_of_time_utc` so that:

* freshness decisions are deterministic and auditable
* results do not drift based on wall-clock timing
* replay/offline parity attempts have a clear target time boundary

---

### 1.5 What OFP must enable for downstream components

Downstream components (Decision Fabric, Decision Log, later Offline Features) must be able to rely on OFP for:

* **Canonical keying**

  * features keyed by canonical entity IDs (FeatureKeys), not raw identifiers
* **Explicit freshness**

  * per-group TTL and stale flags
* **Replay-safe online state**

  * duplicates don’t double-count; out-of-order doesn’t corrupt aggregates
* **Provenance completeness**

  * group versions, graph_version, and input_basis watermarks are always present
* **Deterministic snapshot identity**

  * same basis + same request ⇒ same snapshot_hash

---

## 2) Core invariants (OFP “laws”)

> These are **non-negotiable behaviours** for OFP v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Run/world scoped via ContextPins

* OFP state and serving semantics are scoped by **ContextPins**:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* OFP MUST NOT serve or maintain cross-run feature state in v0.

### 2.2 OFP is system-of-record for snapshot + provenance

* OFP is authoritative for:

  * **feature snapshot contents** returned at serve time
  * **provenance bundle** explaining those features
* OFP is not authoritative for event validity (IG), stream durability (EB), identity truth (IEG), or decisions (Decision Fabric).

### 2.3 FeatureKey is canonical (no raw identifier keys)

* OFP v0 FeatureKeys use canonical entity IDs:

  * `FeatureKey = { key_type, key_id }`
  * `key_type ∈ {account, card, customer, merchant, device}`
  * `key_id` MUST be the canonical entity_id (IEG EntityRef) within ContextPins.
* OFP MUST NOT key on raw identifiers (PAN/device_fp/etc.) in v0.

### 2.4 FeatureGroup versions are explicit and recorded

* In v0, `FeatureGroupRef` MUST specify **group_name + group_version**.
* Every snapshot MUST record the exact group versions used.

### 2.5 No hidden “now”: as_of_time_utc is explicit

* `as_of_time_utc` is REQUIRED on `get_features`.
* OFP must not silently substitute wall-clock “now” when interpreting freshness or generating snapshots.

### 2.6 Freshness is explicit; stale is served but flagged

* Freshness/TTL is evaluated on an **event_time** basis.
* If features are stale, OFP still serves them, but MUST:

  * set `stale=true` deterministically (per group)
  * return a warning indicator in the response/provenance

### 2.7 Idempotent under duplicates (EB at-least-once)

* OFP MUST be safe under duplicate event delivery.
* Aggregate/state updates must not double-count under retries/redelivery.

### 2.8 Disorder-safe (out-of-order cannot change meaning)

* OFP MUST be safe under out-of-order delivery.
* Any windowed/rolling logic must be event_time-driven and order-independent.

### 2.9 Snapshot identity is deterministic

* OFP returns a deterministic **feature_snapshot_hash**.
* The hash must be derived from a canonical serialization including:

  * ContextPins, FeatureKeys, group versions, as_of_time_utc, features map (stable ordering), freshness, graph_version (if used), input_basis watermarks.

### 2.10 Provenance bundle is mandatory and complete

Every successful response MUST include provenance containing:

* ContextPins
* feature_snapshot_hash
* requested FeatureKeys and group versions used
* freshness block (per group)
* graph_version used (when IEG consulted)
* input_basis watermark vector (per-partition applied offsets) for OFP state at serve time

### 2.11 OFP v0 does not emit feature snapshot events

* OFP v0 does not emit `feature_snapshot_created` onto EB.
* The only boundary output is the serving response (snapshot + provenance).

### 2.12 Explicit error posture (no invented outputs)

* If OFP cannot serve correct results, it returns an explicit ErrorResponse with a retryable flag.
* OFP must not fabricate partial snapshots as a substitute for correctness.

---

## 3) Terminology and key objects

> These are the nouns used throughout the OFP conceptual design. Exact field shapes live in the v0 contract schema; behavioural meaning is pinned in OFP specs.

### 3.1 ContextPins

Run/world scoping identifiers carried everywhere OFP operates:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

All OFP requests and responses are scoped by ContextPins.

---

### 3.2 FeatureKey

A canonical key identifying the entity for which features are computed/served.

* `key_type ∈ {account, card, customer, merchant, device}`
* `key_id` = canonical entity_id (IEG EntityRef) within ContextPins

FeatureKey never uses raw identifiers in v0.

---

### 3.3 FeatureGroup / FeatureGroupRef

A **FeatureGroup** is a versioned bundle of features defined over a specific key_type with a TTL/freshness policy.

* `group_name`
* `group_version` *(required in v0)*
* `key_type`
* `feature_names[]` (list; the catalogue can be small in v0)
* TTL/freshness policy (defined in OFP3)

A **FeatureGroupRef** is what callers provide: `{group_name, group_version}`.

---

### 3.4 as_of_time_utc

The explicit time boundary for a feature request.

* required in v0
* used for TTL/freshness evaluation (event_time-based)
* prevents hidden dependency on wall-clock “now”

---

### 3.5 FeatureSnapshot

The returned feature values for a request.

Conceptually contains:

* ContextPins
* requested FeatureKeys
* `features{}` map (stable key ordering)
* `feature_snapshot_hash` (deterministic)
* optional per-key/per-group structuring (implementation freedom)

---

### 3.6 FeatureProvenance

The mandatory metadata bundle describing how the snapshot was produced.

Must include:

* ContextPins
* group versions used
* freshness metadata (per group)
* graph_version used (if IEG consulted)
* input_basis (OFP applied EB watermark vector)
* warnings (e.g., stale groups)

---

### 3.7 Freshness / TTL block

A structured description of staleness for each group:

Per group:

* `ttl_seconds`
* `last_update_event_time`
* `age_seconds` (as_of_time - last_update_event_time)
* `stale` boolean

All based on event_time, not ingest_time.

---

### 3.8 input_basis (watermark vector)

A representation of the OFP state basis at serve time:

* stream_name (typically `admitted_events`)
* per-partition applied offset watermark vector (map)

Used for audit/replay parity (“what the OFP had ingested/applied”).

---

### 3.9 graph_version

The IEG version marker returned/used during context resolution.

If OFP consults IEG for the request, OFP includes the graph_version used in provenance.

---

### 3.10 Update idempotency key (OFP state update key)

The identity used to prevent double-counting in OFP aggregates:

* derived from EB position and key/group identity:

  * `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`

---

### 3.11 GetFeaturesRequest / GetFeaturesResponse

The v0 serving boundary objects:

* request:

  * ContextPins
  * FeatureKeys[]
  * FeatureGroupRefs[] (version required)
  * as_of_time_utc
* response:

  * FeatureSnapshot
  * FeatureProvenance
  * optional warnings
  * ErrorResponse on failure

---

### 3.12 ErrorResponse

The explicit failure shape when OFP cannot serve correct results.

* `error_code`
* short `message`
* `retryable` boolean
* ContextPins (when known)

---

## 4) OFP as a black box (inputs → outputs)

> This section treats the Online Feature Plane (OFP) as a single black box: what it consumes, what it produces, and the boundary surfaces it exposes.

### 4.1 Inputs (what OFP consumes)

#### 4.1.1 Primary input: admitted events from EB

OFP consumes EB-delivered admitted events (at-least-once; duplicates and out-of-order possible). In v0, OFP uses these events to maintain online aggregate/state needed to serve feature snapshots.

#### 4.1.2 Context lookups from IEG

OFP uses IEG as a context source to:

* resolve canonical EntityRefs (FeatureKeys) from observed identifiers when needed
* obtain `graph_version` for provenance

OFP does not assume IEG truth beyond its query responses; it records the graph_version used.

#### 4.1.3 Feature definitions (group registry + TTL policy)

OFP relies on a pinned registry of:

* FeatureGroups (name, version, key_type, feature_names)
* freshness/TTL policy per group
* definitions/transforms (implementation detail, but versions are recorded)

---

### 4.2 Outputs (what OFP produces)

#### 4.2.1 Serving output: FeatureSnapshot + FeatureProvenance

OFP serves a deterministic response for each request:

* `FeatureSnapshot`

  * feature values (stable map shape)
  * deterministic `feature_snapshot_hash`
* `FeatureProvenance`

  * ContextPins
  * group versions used
  * freshness block (per group)
  * input_basis watermark vector (OFP applied offsets)
  * graph_version used (when IEG consulted)
  * warnings (e.g., stale groups)

#### 4.2.2 Optional internal materialization (implementation freedom)

OFP may write internal caches/stores for low latency (aggregator state, materialized key views), but these are not external contracts in v0.

#### 4.2.3 Explicit errors

If OFP cannot produce correct results:

* returns ErrorResponse with retryable flag
* does not fabricate partial snapshots as a substitute

---

### 4.3 Boundary map (what OFP touches)

#### 4.3.1 Upstream sources

* EB stream: `admitted_events`
* IEG query surface (resolve identity, profiles/neighbors) as needed

#### 4.3.2 Downstream consumers

* Decision Fabric (primary consumer of feature snapshots)
* Decision Log (may record snapshots/provenance by-ref or as hashes, depending on design)

#### 4.3.3 Storage substrate (implementation detail)

OFP relies on some storage/compute substrate for aggregate state and serving. The choice is implementer freedom; semantics and provenance are pinned.

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for OFP v0. These decisions are treated as fixed direction for OFP specs and the v0 contract schema.

### 5.1 Scope and isolation

* OFP v0 is **run/world-scoped**.
* All serving and (any) maintained state is isolated by **ContextPins**:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* No cross-run feature state in v0.

---

### 5.2 Authority boundary

* OFP is authoritative for:

  * **feature snapshot contents** returned at serve time
  * **feature provenance bundle**
* OFP is not authoritative for:

  * event validity (IG)
  * stream durability / delivery (EB)
  * identity truth (IEG)
  * decisions/actions (Decision Fabric / Actions)

---

### 5.3 FeatureKey model (canonical keying)

* `FeatureKey = { key_type, key_id }`
* `key_type ∈ {account, card, customer, merchant, device}`
* `key_id` MUST be the **canonical entity_id** (IEG EntityRef) within ContextPins.
* OFP v0 MUST NOT key features on raw identifiers (PAN/device_fp/etc.).

---

### 5.4 FeatureGroup versioning (explicit and recorded)

* In v0, `FeatureGroupRef` MUST include:

  * `group_name` **and** `group_version` (version required)
* Every snapshot MUST record the exact group versions used.

---

### 5.5 as_of_time_utc is required (no hidden “now”)

* `as_of_time_utc` is REQUIRED in every `get_features` request.
* OFP must not default to wall-clock “now” for serving or freshness evaluation.

---

### 5.6 Freshness/TTL semantics (v0 posture)

* Freshness evaluation is **event_time-based**.
* For each requested group, OFP returns a freshness block including:

  * `ttl_seconds`
  * `last_update_event_time`
  * `age_seconds` (as_of_time - last_update_event_time)
  * `stale` boolean
* Stale groups are **served but flagged**:

  * response includes warnings and stale markers deterministically.

---

### 5.7 Update idempotency key (replay-safe under EB at-least-once)

* OFP consumes EB `admitted_events` and maintains state/aggregates.
* Each aggregate update is guarded by an idempotency key derived from **EB position × FeatureKey × FeatureGroup**:

  * `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`
* Duplicate deliveries must not double-count.

---

### 5.8 Disorder posture (out-of-order safe)

* OFP must be correct under out-of-order delivery.
* All windowing/aggregation semantics are **event_time-driven** and **order-independent** (arrival order must not change meaning).

---

### 5.9 Snapshot identity is deterministic (feature_snapshot_hash)

* OFP returns a deterministic `feature_snapshot_hash` (no random UUIDs).
* The hash is computed from a canonical serialization of:

  * ContextPins
  * requested FeatureKeys (stable ordering)
  * requested group_name+group_version list (stable ordering)
  * as_of_time_utc
  * features map (stable ordering)
  * freshness blocks (stable ordering)
  * graph_version (if used)
  * input_basis watermark vector
* Any serialization/ordering rules required to make this stable are treated as pinned behaviour.

---

### 5.10 Provenance bundle requirements (mandatory)

Every successful response MUST include provenance containing:

* ContextPins
* `feature_snapshot_hash`
* FeatureKeys requested
* exact group versions used
* freshness blocks (per group)
* `graph_version` used (when IEG consulted for the request)
* `input_basis` = OFP applied EB watermark vector (per-partition offsets) at serve time
* warnings (e.g., stale groups)

---

### 5.11 Serving surface (v0 boundary)

Pinned operation:

* `get_features(context_pins, feature_keys[], feature_groups[], as_of_time_utc) -> {snapshot, provenance}`

Pinned error model:

* INVALID_REQUEST
* NOT_FOUND
* UNAVAILABLE
  Each error includes `retryable` boolean.

---

### 5.12 Emission posture (v0)

* OFP v0 does **not** emit `feature_snapshot_created` (or equivalent) onto EB.
* The boundary output is serving responses only.

---

### 5.13 Contracts packaging (v0)

* OFP v0 ships **one** schema file:

  * `contracts/ofp_public_contracts_v0.schema.json`
* It pins the serving boundary objects:

  * ContextPins, FeatureKey, FeatureGroupRef
  * GetFeaturesRequest/Response
  * FeatureSnapshot, FeatureProvenance (including freshness + input_basis + graph_version)
  * ErrorResponse
* OFP v0 does not redefine canonical event payload schemas inside this contract.

---

## 6) Modular breakdown (Level 1) and what each module must answer

> OFP is a **context compiler + serving surface**. The modular breakdown exists to force OFP’s semantics (keying, freshness, idempotent updates, provenance, deterministic snapshots) to be answered *somewhere*, while leaving storage and compute mechanics to the implementer.

### 6.0 Module map (one screen)

OFP is decomposed into 6 conceptual modules:

1. **Feature Group Registry**
2. **Keying & Entity Context Resolver**
3. **Online Aggregators / State Stores**
4. **On-demand Computation Layer**
5. **Serving API**
6. **Provenance & Snapshotting**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Feature Group Registry

### Purpose

Define what feature groups exist, how they are keyed, how they are versioned, and how TTL/freshness applies.

### What it owns

* FeatureGroup identity: `{group_name, group_version}`
* group metadata: key_type, feature_names list
* TTL policy association per group

### Questions this module must answer

* What is a FeatureGroup in v0 (required fields)?
* How are group versions selected (v0: explicit version required)?
* What TTL policy applies to each group and how is it represented?
* What is the stable ordering/naming posture for feature names?

### Can be left to the implementer

* where registry is stored (file, db, config)
* how transforms are represented internally (DSL vs code)

### Local vs deployed operation

* **Local:** static config registry is fine
* **Deployed:** may be centralized/config-managed; semantics unchanged

---

## 6.2 Module 2 — Keying & Entity Context Resolver

### Purpose

Determine the canonical FeatureKeys for a request or event, using IEG where necessary.

### What it owns

* the pinned FeatureKey model (key_id = IEG entity_id)
* mapping rules: request/event → FeatureKeys
* IEG query integration and graph_version capture

### Questions this module must answer

* How are FeatureKeys obtained (provided directly vs resolved)?
* What is the canonical key_type set (v0 fixed)?
* When OFP consults IEG, which query is used and what is recorded?
* How is graph_version captured and placed into provenance?
* What happens if IEG is unavailable (error posture)?

### Can be left to the implementer

* caching of IEG results
* batching of IEG queries
* internal representation of resolution plans

### Local vs deployed operation

* **Local:** may mock IEG or run in-process; semantics unchanged
* **Deployed:** service-to-service calls; semantics unchanged

---

## 6.3 Module 3 — Online Aggregators / State Stores

### Purpose

Maintain replay-safe, disorder-safe aggregate state used for serving feature values.

### What it owns

* update idempotency key posture (EB position × FeatureKey × FeatureGroup)
* event_time-driven aggregation semantics
* watermark basis capture (input_basis)

### Questions this module must answer

* What is the update idempotency key and how is it applied?
* How are aggregates updated under duplicates (no double-count)?
* How are aggregates updated under out-of-order events (event_time-driven rules)?
* What is the applied watermark basis and how is it surfaced for provenance?
* What happens when events arrive missing required envelope fields for OFP aggregation?

### Can be left to the implementer

* storage backend choice (KV/stream processor/db)
* window implementation strategy
* concurrency and partitioning strategy

### Local vs deployed operation

* **Local:** can run naive in-memory stores; semantics unchanged
* **Deployed:** durable/replicated state; semantics unchanged

---

## 6.4 Module 4 — On-demand Computation Layer

### Purpose

Compute features that are not pure stored aggregates (joins, transforms, simple derived values), deterministically at serve time.

### What it owns

* deterministic computation posture (no randomness, no hidden time)
* stable output shape rules for computed features

### Questions this module must answer

* Which features are computed on-demand vs stored aggregates (group-level decision)?
* What inputs are used (aggregates, IEG context, request as_of_time)?
* How are computed values kept deterministic across runs/replay?
* What happens if a required input is missing (not_found vs default vs error)?

### Can be left to the implementer

* compute engine choice and optimization
* caching of computed results

### Local vs deployed operation

* semantics identical; deployed emphasizes latency

---

## 6.5 Module 5 — Serving API

### Purpose

Expose the v0 serving boundary: get_features returns snapshot + provenance deterministically.

### What it owns

* `get_features` request/response semantics
* stable ordering of keys, groups, and feature maps
* error model and retryability flags

### Questions this module must answer

* What fields are required on GetFeaturesRequest (ContextPins, FeatureKeys, group refs, as_of_time)?
* How are results structured for multiple keys and multiple groups?
* What warnings must be returned (stale groups)?
* What are the error codes and retryable posture?

### Can be left to the implementer

* API transport (HTTP/gRPC/in-process)
* pagination/size limits (if any)
* auth enforcement details (posture pinned in ops spec later)

### Local vs deployed operation

* local may be in-process; deployed may be a service; semantics unchanged

---

## 6.6 Module 6 — Provenance & Snapshotting

### Purpose

Produce the deterministic snapshot identity and provenance bundle required for audit and offline parity hooks.

### What it owns

* deterministic `feature_snapshot_hash` computation
* canonical serialization + stable ordering rules
* required provenance fields and warnings

### Questions this module must answer

* What exact inputs are hashed into feature_snapshot_hash?
* What canonical ordering rules apply for hashing and response maps?
* What provenance fields are mandatory (pins, group versions, freshness, graph_version, input_basis)?
* How is freshness computed and recorded per group?
* How are stale warnings surfaced deterministically?

### Can be left to the implementer

* hashing algorithm choice (as long as deterministic and stable)
* serialization library, provided canonicalization rules are obeyed

### Local vs deployed operation

* identical semantics; deployed may optimize caching of hashes/provenance

---

## 6.7 Cross-module pinned items (summary)

Across all modules, OFP must ensure:

* ContextPins scoping everywhere
* FeatureKeys use canonical entity_id, not raw identifiers
* group versions explicit and recorded
* as_of_time_utc required (no hidden now)
* freshness is event_time-based and stale is flagged (served)
* aggregate updates are idempotent and disorder-safe
* feature_snapshot_hash is deterministic with stable ordering rules
* provenance includes pins, group versions, freshness, graph_version (if used), and input_basis watermarks
* explicit error posture with retryable flag

---

## 7) Freshness, TTL, and staleness semantics (v0)

> This section pins how OFP evaluates “fresh vs stale” in v0 and what it returns to callers. Freshness is part of the contract boundary because Degrade Ladder and Decision Fabric depend on it.

### 7.1 Freshness basis (pinned)

* Freshness is evaluated on an **event_time** basis.
* `as_of_time_utc` is the reference time for evaluation.
* OFP does not use wall-clock “now” implicitly.

---

### 7.2 TTL policy granularity (v0 posture)

* TTL is defined **per FeatureGroup** in v0.
* TTL is represented as `ttl_seconds` on the group definition (registry).

(Per-feature TTL can be introduced later if needed, but v0 is group-level for simplicity.)

---

### 7.3 Required freshness fields returned (per group)

For every requested group, OFP returns a freshness block:

* `group_name`
* `group_version`
* `ttl_seconds`
* `last_update_event_time`
* `age_seconds = max(0, as_of_time_utc - last_update_event_time)`
* `stale = (age_seconds > ttl_seconds)`

If `last_update_event_time` is unknown (no data), OFP treats freshness as:

* `stale=true` and surfaces an explicit warning (rather than inventing freshness).

---

### 7.4 Stale handling posture (pinned)

* OFP **serves stale** features but must:

  * mark stale deterministically in freshness blocks
  * emit deterministic warnings in provenance/response

OFP does not refuse service on staleness in v0; policy decisions are deferred to Degrade Ladder / Decision Fabric.

---

### 7.5 Mixed freshness across groups

If multiple groups are requested:

* each group has its own freshness block and stale flag
* warnings are aggregated but must retain per-group specificity (avoid a single “stale” boolean that hides which group is stale)

---

### 7.6 Event-time discipline for updates

* The `last_update_event_time` for a group/key is driven by event_time of applied updates, not ingest/apply time.
* Under out-of-order delivery, last_update_event_time must reflect the maximum event_time applied.

---

### 7.7 Freshness under replay

Because replay can rebuild OFP state:

* given the same applied events and as_of_time_utc, OFP must produce the same freshness blocks
* freshness computation must not depend on ingestion timing or processing speed

---

### 7.8 Freshness visibility and consumer guidance

Consumers (Decision Fabric / Degrade Ladder) should treat:

* `stale=true` as an explicit signal the feature context is degraded
* warnings + freshness blocks as auditable evidence (“we served stale features and knew it”)

---

## 8) Idempotency, disorder safety, and replay posture

> This section pins how OFP remains correct under EB realities: at-least-once delivery, duplicates, out-of-order events, and replay/backfill.

### 8.1 Deterministic OFP posture (scope)

OFP is deterministic if, given:

* the same admitted event log (within ContextPins),
* the same FeatureGroup registry versions,
* the same request inputs (FeatureKeys, as_of_time_utc),

OFP produces:

* the same snapshot feature values (within the chosen group definitions),
* the same freshness blocks,
* and the same feature_snapshot_hash,
  subject to the pinned update semantics and ordering rules.

---

### 8.2 Update idempotency key (pinned)

Aggregate/state updates are guarded by an idempotency key derived from:

* EB position × FeatureKey × FeatureGroup:

`(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`

If the same DeliveredRecord is processed again:

* the update is a no-op for that FeatureKey+Group.
* aggregates are not double-counted.

---

### 8.3 Duplicate delivery posture

Because EB is at-least-once:

* duplicates can occur due to retries, rebalances, or consumer failures

OFP guarantees:

* duplicates do not change aggregate state beyond the first application
* last_update_event_time and freshness are not corrupted by duplicate re-application

---

### 8.4 Disorder posture (out-of-order safe)

OFP must be correct under out-of-order delivery:

* aggregation semantics must be **order-independent**
* any time-window semantics are driven by **event_time** and updated deterministically

Minimum v0 posture:

* window membership is determined by event_time
* late events are allowed to update historical windows (within whatever window retention you choose internally), without corrupting invariants

---

### 8.5 Replay posture (rebuild is safe by construction)

Replay/backfill means:

* re-consuming the admitted event log within ContextPins and re-applying updates

Replay safety is ensured by:

* idempotent update keys (duplicate-safe)
* disorder-safe event_time-driven updates
* fixed registry versions for groups (explicit version selection)

OFP does not require a special replay mode; reprocessing is safe by construction.

---

### 8.6 input_basis (watermark) posture

OFP exposes an `input_basis` in provenance that represents:

* the applied watermark basis for the OFP state used to answer the request

Pinned meaning:

* input_basis is a per-partition applied offset watermark vector (map) + stream_name.
* it is recordable by consumers and supports offline parity hooks later.

---

### 8.7 Behaviour when required event fields are missing

If OFP cannot interpret an event update due to missing required envelope fields:

* OFP does not apply the update
* OFP records an explicit update failure outcome (metric/counter)
* OFP does not invent substitute data

---

### 8.8 Idempotency vs registry version changes

Because group_version is required in v0:

* a request for a different group_version is considered a different computation context
* update keys include group_version, preventing cross-version double counting

---

## 9) Provenance bundle (audit + parity hook)

> This section pins what provenance must contain so decisions can be explained and later rebuilt (offline parity). Provenance is a first-class output of OFP v0.

### 9.1 Provenance purpose (why it exists)

Provenance enables a downstream consumer (Decision Fabric / Decision Log / Offline rebuild) to answer:

* what features were served,
* under what definitions (group versions),
* with what freshness posture,
* using what identity context (graph_version),
* and from what applied event basis (input watermarks).

---

### 9.2 Mandatory provenance fields (pinned)

Every successful `get_features` response must include provenance containing:

1. **ContextPins**

* `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`

2. **feature_snapshot_hash**

* deterministic hash identifying the snapshot returned

3. **Request summary**

* FeatureKeys requested (stable ordering)
* FeatureGroups requested (group_name + group_version; stable ordering)
* `as_of_time_utc`

4. **Group versions used**

* explicit list of `{group_name, group_version}` actually used

5. **Freshness blocks (per group)**

* ttl_seconds
* last_update_event_time
* age_seconds
* stale boolean

6. **graph_version used (when IEG consulted)**

* graph_version object (same meaning as IEG: applied watermark basis token)

7. **input_basis watermark vector**

* stream_name (typically `admitted_events`)
* per-partition applied offset watermark vector (map)

8. **Warnings**

* deterministic warnings list, at minimum:

  * stale group warnings with group_name/group_version
  * optional “no data” warnings when freshness cannot be computed

---

### 9.3 Deterministic output shape rules (for provenance stability)

To ensure provenance is stable and hashable:

* lists must be sorted deterministically (FeatureKeys, group refs, warnings)
* maps must be serialized with stable key ordering (`features{}` map; freshness blocks by group)
* numeric fields should have stable representation (avoid float formatting drift; keep ints where possible)

These rules exist so the same inputs yield the same provenance and snapshot_hash.

---

### 9.4 feature_snapshot_hash computation (pinned inputs)

feature_snapshot_hash must be computed from a canonical serialization of:

* ContextPins
* FeatureKeys (sorted)
* group refs (sorted)
* as_of_time_utc
* features map (stable ordering)
* freshness blocks (stable ordering)
* graph_version (if present)
* input_basis (watermark vector)
* warnings (sorted)

Hash algorithm choice is implementation freedom, but determinism and stable serialization are not.

---

### 9.5 Offline parity hook (what provenance makes possible later)

With provenance recorded, an offline system can attempt to rebuild:

* the same feature snapshot at the same input_basis and graph_version
* and compare snapshot_hashes

This is why input_basis + graph_version are mandatory: they make the rebuild target explicit.

---

### 9.6 Provenance failure posture

If provenance cannot be completed correctly (missing required basis metadata):

* OFP must not fabricate it
* OFP must return an explicit ErrorResponse (retryable when appropriate)

---

## 10) Serving surface (v0 boundary)

> This section pins the v0 external interface: what callers send and what OFP guarantees to return. The serving surface is designed to be deterministic, versioned, and auditable.

### 10.1 Operation (pinned)

OFP v0 exposes a single pinned operation:

`get_features(context_pins, feature_keys[], feature_groups[], as_of_time_utc) -> {snapshot, provenance}`

No other public operations are required in v0.

---

### 10.2 GetFeaturesRequest (required fields)

A valid request MUST include:

* `context_pins` (ContextPins)
* `feature_keys[]` (one or more FeatureKeys)
* `feature_groups[]` (FeatureGroupRefs; each MUST include group_version in v0)
* `as_of_time_utc` (required; no hidden now)

Optional (if you want in v0, but not required conceptually):

* `request_id` (caller correlation)
* `extensions{}` bag (future-proofing)

---

### 10.3 GetFeaturesResponse (success shape)

A successful response MUST include:

* `snapshot` (FeatureSnapshot)

  * features map with deterministic key ordering
  * feature_snapshot_hash (deterministic)
* `provenance` (FeatureProvenance)

  * mandatory fields per §9
* optional `warnings[]` (also present inside provenance if you prefer one location)

**Pinned rule:** stale features are served but flagged via freshness blocks and warnings.

---

### 10.4 Multi-key and multi-group behavior

v0 supports:

* multiple FeatureKeys per request
* multiple FeatureGroups per request

Pinned constraints:

* response structure must be deterministic for multi-key/multi-group (stable ordering)
* if you choose a nested shape (by key → by group → features), that shape must be fixed in contracts

(Exact nesting is a contract decision; determinism is required either way.)

---

### 10.5 Error model (pinned)

If OFP cannot serve correct results, it returns ErrorResponse with:

* `error_code` ∈ {`INVALID_REQUEST`, `NOT_FOUND`, `UNAVAILABLE`}
* short `message`
* `retryable` boolean
* ContextPins (when known)

Rules:

* INVALID_REQUEST: non-retryable unless caller changes request
* NOT_FOUND: non-retryable by default (unless data expected later; your choice must be pinned)
* UNAVAILABLE: retryable=true

---

### 10.6 Deterministic output shape rules (pinned)

To prevent drift across implementations:

* FeatureKeys in outputs must be sorted deterministically
* group refs in outputs must be sorted deterministically
* feature maps must be serialized with stable ordering
* warnings list must be sorted deterministically

---

### 10.7 Local vs deployed semantics

* Local and deployed implementations may differ in mechanics (cache, compute engine), but must return:

  * the same snapshot/provenance meaning for the same inputs and same underlying applied basis

---

## 11) Contracts philosophy and contract pack overview (v0)

> OFP contracts exist to pin the **serving boundary shapes** (requests, snapshots, provenance) without exploding into many files. Contracts define *shape*; OFP specs define *behaviour* (freshness, idempotency, hashing rules).

### 11.1 Why contracts exist for OFP

Contracts prevent drift between:

* Decision Fabric (consumer) expectations,
* OFP serving behavior,
* and later offline parity rebuild logic.

If the boundary objects are only described in prose, drift is guaranteed under iteration.

---

### 11.2 v0 contract strategy (one schema file)

OFP v0 ships **one** schema file:

* `contracts/ofp_public_contracts_v0.schema.json`

This file contains `$defs` for all public objects and pins:

* field presence and types
* deterministic structure for multi-key/multi-group responses
* required provenance fields (pins, watermarks, versions, freshness)
* validation targeting rule

OFP v0 does not ship per-module contracts and does not ship internal-storage contracts.

---

### 11.3 Validation targeting rule (self-describing)

All OFP contract objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

### 11.4 `$defs` inventory (v0)

`ofp_public_contracts_v0.schema.json` contains `$defs` for:

* `ContextPins` (same shape as IEG v0; may later be shared)
* `FeatureKey`
* `FeatureGroupRef` (group_version required in v0)
* `FreshnessBlock` (per group)
* `InputBasis` (stream_name + watermark vector map)
* `GraphVersion` (shape compatible with IEG graph_version meaning)
* `FeatureSnapshot`
* `FeatureProvenance`
* `GetFeaturesRequest`
* `GetFeaturesResponse`
* `ErrorResponse`

---

### 11.5 What contracts cover vs what specs cover

#### Contracts cover (shape/structure)

* required fields and types
* enums (key_type set, error_code set)
* deterministic nesting for multi-key/multi-group
* required provenance fields and warnings structure
* stable places where freshness and input_basis are reported

#### Specs cover (behaviour/invariants)

* how FeatureKeys are resolved (IEG usage posture)
* idempotency key logic and replay/disorder posture
* event_time-based freshness evaluation rules
* feature_snapshot_hash input set and canonical serialization rules
* how input_basis watermarks are computed/advanced
* what constitutes NOT_FOUND vs INVALID_REQUEST vs UNAVAILABLE

---

### 11.6 Relationship to Canonical Event Contract Pack

OFP consumes admitted events from EB but:

* does not redefine event payload schemas inside OFP contracts
* relies on envelope-level fields and registry-defined feature transforms
* will later reference the Canonical Event Contract Pack once finalized

---

## 12) Addressing, naming, and discoverability (conceptual)

> This section defines how OFP outputs and provenance can be referenced and discovered without guessing. It stays conceptual because storage/backend is implementation freedom in v0.

### 12.1 Design goals

OFP discoverability must support:

* **auditability:** a decision log can record what features were used and later explain them
* **replay parity hooks:** enough basis metadata exists to attempt offline rebuild
* **deterministic referencing:** no “latest scan”; references are explicit

---

### 12.2 Snapshot identity discoverability

In v0, the primary stable identifier for a served snapshot is:

* `feature_snapshot_hash`

Consumers (Decision Fabric / Decision Log) can store:

* the hash itself, and
* the provenance bundle fields that produced it.

If OFP later persists snapshots, that persistence should be addressable by:

* ContextPins + feature_snapshot_hash (conceptual).

---

### 12.3 Provenance discoverability

Provenance is returned inline with every response. It includes:

* ContextPins
* group versions
* freshness blocks
* graph_version (if used)
* input_basis watermarks

This is sufficient for:

* audit (“what we knew at decision time”)
* parity attempts (“rebuild at the same basis”)

---

### 12.4 Naming stability (feature names and groups)

To avoid drift:

* feature names are stable identifiers (lower_snake_case recommended)
* FeatureGroupRefs are `{group_name, group_version}` in v0
* consumers must treat group_version as part of compatibility

Exact naming conventions can be pinned in OFP2 (spec), but the conceptual doc states the stability requirement.

---

### 12.5 Local vs deployed discoverability

* **Local:** OFP may not persist anything; the response bundle is the audit record.
* **Deployed:** OFP may persist state and possibly snapshots, but:

  * the semantic identifier remains feature_snapshot_hash
  * provenance meaning remains identical

Locator types can change (filesystem vs object store vs DB), but the meaning of snapshot_hash/provenance does not.

---

### 12.6 Optional discovery aids (implementation freedom)

OFP may provide additional mechanisms later, such as:

* “lookup snapshot by hash” endpoint
* “list supported feature groups” endpoint
* cached “latest snapshot per key/group”

These are not required in v0 and must not replace the core deterministic `get_features` boundary.

---

## 13) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Online Feature Plane docs and contracts. The goal is a **single, deep reading surface** for OFP design, plus a **minimal v0 serving-boundary contract**.

### 13.1 Target location in repo

Conceptually, OFP lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/online_feature_plane/`

This folder should be self-contained: a new contributor should understand OFP by starting here.

---

### 13.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ online_feature_plane/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ OFP1_charter_and_boundaries.md
         │  ├─ OFP2_feature_keys_group_registry_versioning.md
         │  ├─ OFP3_freshness_ttl_semantics.md
         │  ├─ OFP4_update_idempotency_replay_safety.md
         │  └─ OFP5_serving_provenance_ops_acceptance.md
         │
         └─ contracts/
            └─ ofp_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; v0 needs only **one** schema file here.

---

### 13.3 What each file is for (intent)

#### `README.md`

* Entry point: what OFP is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (designer-locked v0 intent)
  * `specs/` reading order (OFP1–OFP5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This stitched conceptual design document:

  * OFP purpose in platform
  * OFP laws (pins, keying, freshness, idempotency, determinism, provenance)
  * designer-locked v0 decisions
  * modular breakdown + questions per module
  * contract pack overview (v0)
  * discovery concepts (snapshot_hash, provenance)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behaviour/invariants
  * contract schema defines boundary shapes
* Non-negotiables:

  * ContextPins scoping everywhere
  * canonical FeatureKey model (IEG entity_id)
  * explicit group versions in v0
  * as_of_time_utc required
  * event_time freshness; stale served but flagged
  * idempotent updates (EB position × key × group)
  * deterministic feature_snapshot_hash + stable ordering rules
  * provenance completeness (pins, versions, freshness, graph_version, input_basis)
  * explicit ErrorResponse (no invented context)

#### `specs/`

* OFP1–OFP5 are the eventual binding-ish OFP design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `ofp_public_contracts_v0.schema.json` pins serving boundary objects.

---

### 13.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (designer-locked intent)
3. `specs/OFP1_...` → `specs/OFP5_...` (behaviour/invariants)
4. `contracts/ofp_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

### 13.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge OFP1–OFP5 into fewer docs once stable.
* Add `contracts/README.md` only if you need a brief note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders under deadline.

---

## 14) What the eventual spec docs must capture (mapping from this concept doc)

> This section bridges the OFP conceptual design into the **actual OFP spec docs** (OFP1–OFP5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 14.0 Mapping rule (how to use this section)

For every OFP “law” and designer-locked decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in OFP1–OFP5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 14.1 OFP1 — Charter & boundaries

### OFP1 must capture

* OFP purpose as a **context compiler + serving surface**
* authority boundaries:

  * system-of-record for snapshot + provenance
  * not a validator (IG), not durability (EB), not identity truth (IEG), not decisioning
* OFP laws in enforceable prose:

  * ContextPins scoping
  * canonical FeatureKey model (IEG entity_id)
  * explicit group versions in v0
  * as_of_time_utc required
  * event_time freshness; stale served but flagged
  * idempotent + disorder-safe updates
  * deterministic snapshot_hash + stable ordering rules
  * provenance completeness (pins, versions, freshness, graph_version, input_basis)
  * explicit ErrorResponse posture
* v0 non-goals:

  * no snapshot-created event emissions
  * no “latest group version” selection
  * no cross-run feature state

### OFP1 may leave to the implementer

* internal architecture, compute engine selection, infra topology

---

## 14.2 OFP2 — Feature keys, group registry, and versioning

### OFP2 must capture

* FeatureKey model:

  * key_type set (account/card/customer/merchant/device)
  * key_id = canonical entity_id (IEG EntityRef)
  * no raw identifiers as feature keys
* FeatureGroup registry model:

  * required fields (group_name, group_version, key_type, feature_names)
  * group_version required in v0
* deterministic naming/ordering posture for feature names and groups
* how keys are obtained:

  * direct keys vs IEG-assisted resolution posture (conceptual)

### OFP2 may leave to the implementer

* registry storage method and transform representation (DSL vs code)

---

## 14.3 OFP3 — Freshness / TTL semantics

### OFP3 must capture

* freshness basis:

  * event_time-based evaluation using as_of_time_utc
* TTL granularity:

  * per FeatureGroup in v0
* stale posture:

  * serve stale but flag (freshness blocks + warnings)
* freshness block required fields and how last_update_event_time is computed under disorder

### OFP3 may leave to the implementer

* internal TTL evaluation mechanics and caching

---

## 14.4 OFP4 — Update semantics, idempotency, and replay safety

### OFP4 must capture

* EB realities:

  * duplicates possible, out-of-order possible
* idempotency update key:

  * EB position × FeatureKey × FeatureGroup (pinned)
* disorder posture:

  * event_time-driven and order-independent window updates
* replay posture:

  * same events + same group versions + same as_of_time ⇒ same snapshot_hash at same basis
* what happens when events are missing required envelope fields (no update + explicit failure recorded)

### OFP4 may leave to the implementer

* streaming vs micro-batch processing topology
* state store backend and sharding strategy

---

## 14.5 OFP5 — Serving surface, provenance, ops & acceptance

### OFP5 must capture

* get_features boundary semantics:

  * request required fields
  * deterministic multi-key/multi-group response structure
* provenance and snapshot hashing rules:

  * required provenance fields (pins, versions, freshness, graph_version, input_basis)
  * canonical serialization + stable ordering rules
* error model:

  * INVALID_REQUEST / NOT_FOUND / UNAVAILABLE + retryable
* observability minimums:

  * staleness rates, update lag (watermarks), query latency, error rates
* acceptance scenarios (tests-as-intent):

  * duplicates don’t double-count
  * stale served but flagged
  * deterministic ordering + stable snapshot_hash
  * provenance completeness

### OFP5 may leave to the implementer

* deployment details and monitoring stack

---

## 14.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* ContextPins, FeatureKey, FeatureGroupRef
* GetFeaturesRequest/Response
* FeatureSnapshot + feature_snapshot_hash field
* FeatureProvenance with:

  * group versions list
  * freshness blocks
  * graph_version object
  * input_basis watermark vector
  * warnings list
* ErrorResponse with retryable boolean
* validation targeting via kind + contract_version

### Specs must include

* behaviour rules:

  * as_of_time required; no hidden now
  * event_time freshness evaluation and stale posture
  * idempotent update key and replay/disorder semantics
  * snapshot_hash canonicalization inputs and stable ordering rules
  * how input_basis watermarks are computed/advanced conceptually
  * consumer guidance on stale and error handling

---

## 14.7 Minimal completeness standard (so OFP is implementable)

OFP is “spec-ready” when OFP1–OFP5 collectively pin:

* FeatureKey model and group version discipline
* as_of_time semantics and event_time freshness
* idempotent update posture under duplicates and disorder
* deterministic snapshot_hash + provenance completeness (including input_basis + graph_version)
* serving surface semantics and error model
* acceptance scenarios that cover duplicates, staleness, determinism

Everything else can remain implementer freedom.

---

## 15) Acceptance questions and “Definition of Done”

> This section is the conceptual **ship checklist** for OFP v0: the questions OFP must answer and the minimal behavioural scenarios that indicate OFP is correct enough to implement and integrate.

### 15.1 Acceptance questions (OFP must answer these unambiguously)

1. **What feature context am I using?**

* Does every response include ContextPins and a complete provenance bundle?

2. **Are features keyed canonically?**

* Are FeatureKeys always `{key_type, key_id}` where key_id is the canonical IEG entity_id?

3. **Which feature definitions produced this snapshot?**

* Are the exact FeatureGroup versions used recorded in provenance?

4. **What time am I requesting features “as of”?**

* Is `as_of_time_utc` required and respected (no hidden now)?

5. **Are features fresh enough, and how do I know?**

* Does provenance include per-group freshness blocks and stale flags?

6. **What happens if features are stale?**

* Does OFP serve them but flag staleness deterministically (warnings + stale=true)?

7. **What happens under duplicates/retries?**

* Do duplicates from EB fail to double-count aggregates (idempotent updates)?

8. **What happens under out-of-order delivery?**

* Do event_time-driven windows update deterministically without relying on arrival order?

9. **Can I audit/rebuild what we used at decision time?**

* Does provenance include input_basis (applied EB watermark vector) and graph_version (if used)?

10. **Is snapshot identity reproducible?**

* Is feature_snapshot_hash deterministic and stable for the same inputs/basis?

11. **What happens on errors?**

* Are errors explicit with stable error codes and retryable flags (no invented context)?

---

### 15.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Canonical keying enforced

**Given**

* a request with FeatureKeys

**Expect**

* OFP accepts only FeatureKeys keyed by canonical entity_id within ContextPins
* OFP does not accept raw identifiers as keys in v0

---

#### DoD-2: as_of_time_utc is required (no hidden now)

**Given**

* a request missing as_of_time_utc

**Expect**

* INVALID_REQUEST (non-retryable until fixed)

---

#### DoD-3: Deterministic snapshot_hash

**Given**

* the same request (pins, keys, groups, as_of_time) against the same applied basis

**Expect**

* identical features map
* identical provenance
* identical feature_snapshot_hash

---

#### DoD-4: Stale served but flagged

**Given**

* a request where one group’s last_update_event_time exceeds TTL at as_of_time_utc

**Expect**

* snapshot is returned
* freshness block marks stale=true for that group
* warnings include a deterministic stale warning for that group

---

#### DoD-5: Duplicate delivery does not double-count

**Given**

* the same DeliveredRecord from EB is processed twice

**Expect**

* idempotency key blocks re-application
* aggregate state does not double-count
* last_update_event_time is not corrupted

---

#### DoD-6: Out-of-order delivery does not break windows

**Given**

* events arrive out of order in event_time

**Expect**

* windowed aggregates update deterministically based on event_time
* no reliance on arrival order for correctness

---

#### DoD-7: Provenance completeness

**Given**

* any successful get_features response

**Expect**

* provenance includes:

  * ContextPins
  * group versions used
  * freshness blocks per group
  * input_basis watermark vector
  * graph_version when IEG consulted
  * warnings (if stale/no-data)
  * feature_snapshot_hash

---

#### DoD-8: Explicit ErrorResponse posture

**Given**

* OFP cannot serve correct results (e.g., unavailable dependencies)

**Expect**

* ErrorResponse with `error_code=UNAVAILABLE` and `retryable=true`
* no partial/invented snapshot is returned

---

### 15.3 Minimal deliverables required to claim “DoD satisfied”

To claim OFP meets DoD at v0 conceptual level, you should be able to show:

* at least one GetFeaturesRequest/Response example with full provenance
* deterministic snapshot_hash across repeated calls (same basis)
* a stale response example (stale flagged + warnings)
* a duplicate event replay test demonstrating no double-count
* an out-of-order test demonstrating event_time-driven updates
* ErrorResponse example with retryable posture

---

## 16) Open decisions log (v0 residuals only)

> These are the only remaining decisions for OFP v0 that are not already designer-locked. Everything else is pinned above or is implementation freedom.

### DEC-OFP-001 — Response structuring for multi-key / multi-group

* **Question:** what is the canonical response shape when multiple keys and multiple groups are requested?

  * e.g., `by_key -> by_group -> features{}` vs a flattened list.
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5 + `ofp_public_contracts_v0.schema.json`
* **Constraint:** must be deterministic and stable for hashing.

### DEC-OFP-002 — Hash algorithm choice

* **Question:** which hash algorithm is used for `feature_snapshot_hash` (e.g., SHA-256)?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5
* **Constraint:** determinism required; algorithm must be stable and widely available.

### DEC-OFP-003 — Canonical serialization rule for hashing

* **Question:** what exact canonical serialization is used for snapshot_hash inputs (e.g., canonical JSON rules)?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5
* **Constraint:** must fully specify ordering and numeric representation rules.

### DEC-OFP-004 — input_basis watermark encoding

* **Question:** how is the per-partition applied offset watermark vector encoded (map keys, naming convention)?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP4/OFP5
* **Constraint:** meaning is pinned; encoding format is free but must be stable.

### DEC-OFP-005 — NOT_FOUND semantics

* **Question:** when do we return NOT_FOUND vs return an empty snapshot with stale/no-data warnings?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5
* **Constraint:** must be deterministic and consistent across requests.

### DEC-OFP-006 — Minimal error_code vocabulary

* **Question:** do we keep only {INVALID_REQUEST, NOT_FOUND, UNAVAILABLE} or add granular codes (e.g., IEG_UNAVAILABLE, REGISTRY_MISSING)?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5
* **Constraint:** error codes must be stable enough for caller fallback logic.

### DEC-OFP-007 — Max request size limits

* **Question:** maximum number of FeatureKeys and FeatureGroups per request in v0 (to bound cost)?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP5
* **Constraint:** must be enforceable and surfaced as INVALID_REQUEST when exceeded.

### DEC-OFP-008 — “No data” freshness posture

* **Question:** if a group has never been updated for a key, what is last_update_event_time and how is age computed?
* **Status:** OPEN (v0 residual)
* **Close in:** OFP3/OFP5
* **Constraint:** must result in deterministic stale flag and warning; no invented times.

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate the v0 serving boundary and provenance requirements.
> They use `kind` + `contract_version` for schema targeting.
> Multi-key/multi-group response structuring is shown as `by_key -> by_group -> features{}` (DEC-OFP-001), purely as an example.

---

### A.1 Example — `GetFeaturesRequest`

```json
{
  "kind": "get_features_request",
  "contract_version": "ofp_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "as_of_time_utc": "2026-01-03T12:40:00Z",

  "feature_keys": [
    { "key_type": "account", "key_id": "e_account_7c31d9" },
    { "key_type": "merchant", "key_id": "e_merchant_09ab11" }
  ],

  "feature_groups": [
    { "group_name": "txn_velocity", "group_version": "1.0" },
    { "group_name": "merchant_risk_context", "group_version": "1.0" }
  ]
}
```

---

### A.2 Example — `GetFeaturesResponse` (fresh + deterministic provenance)

```json
{
  "kind": "get_features_response",
  "contract_version": "ofp_public_contracts_v0",

  "snapshot": {
    "kind": "feature_snapshot",
    "contract_version": "ofp_public_contracts_v0",

    "context_pins": {
      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c"
    },

    "as_of_time_utc": "2026-01-03T12:40:00Z",

    "feature_snapshot_hash": "fsh_6d3c...sha256...a91b",

    "by_key": [
      {
        "feature_key": { "key_type": "account", "key_id": "e_account_7c31d9" },
        "by_group": [
          {
            "group": { "group_name": "txn_velocity", "group_version": "1.0" },
            "features": {
              "txn_count_5m": 3,
              "txn_count_1h": 18,
              "txn_amount_sum_1h_minor": 12500
            }
          }
        ]
      },
      {
        "feature_key": { "key_type": "merchant", "key_id": "e_merchant_09ab11" },
        "by_group": [
          {
            "group": { "group_name": "merchant_risk_context", "group_version": "1.0" },
            "features": {
              "merchant_chargeback_rate_30d": 0.012,
              "merchant_dispute_count_30d": 4
            }
          }
        ]
      }
    ]
  },

  "provenance": {
    "kind": "feature_provenance",
    "contract_version": "ofp_public_contracts_v0",

    "context_pins": {
      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c"
    },

    "feature_snapshot_hash": "fsh_6d3c...sha256...a91b",

    "requested": {
      "as_of_time_utc": "2026-01-03T12:40:00Z",
      "feature_keys": [
        { "key_type": "account", "key_id": "e_account_7c31d9" },
        { "key_type": "merchant", "key_id": "e_merchant_09ab11" }
      ],
      "feature_groups": [
        { "group_name": "txn_velocity", "group_version": "1.0" },
        { "group_name": "merchant_risk_context", "group_version": "1.0" }
      ]
    },

    "group_versions_used": [
      { "group_name": "txn_velocity", "group_version": "1.0" },
      { "group_name": "merchant_risk_context", "group_version": "1.0" }
    ],

    "freshness": [
      {
        "group_name": "txn_velocity",
        "group_version": "1.0",
        "ttl_seconds": 600,
        "last_update_event_time": "2026-01-03T12:39:10Z",
        "age_seconds": 50,
        "stale": false
      },
      {
        "group_name": "merchant_risk_context",
        "group_version": "1.0",
        "ttl_seconds": 86400,
        "last_update_event_time": "2026-01-03T12:00:00Z",
        "age_seconds": 2400,
        "stale": false
      }
    ],

    "graph_version": {
      "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
      "stream_name": "admitted_events",
      "watermark_basis": {
        "partition_0": 9812400,
        "partition_1": 10012055
      }
    },

    "input_basis": {
      "stream_name": "admitted_events",
      "watermark_basis": {
        "partition_0": 9812500,
        "partition_1": 10012100
      }
    },

    "warnings": []
  }
}
```

---

### A.3 Example — Stale response (served but flagged)

```json
{
  "kind": "get_features_response",
  "contract_version": "ofp_public_contracts_v0",

  "snapshot": {
    "kind": "feature_snapshot",
    "contract_version": "ofp_public_contracts_v0",
    "context_pins": {
      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c"
    },
    "as_of_time_utc": "2026-01-03T12:40:00Z",
    "feature_snapshot_hash": "fsh_stale_...sha256...",
    "by_key": []
  },

  "provenance": {
    "kind": "feature_provenance",
    "contract_version": "ofp_public_contracts_v0",
    "context_pins": {
      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c"
    },
    "feature_snapshot_hash": "fsh_stale_...sha256...",
    "group_versions_used": [
      { "group_name": "txn_velocity", "group_version": "1.0" }
    ],
    "freshness": [
      {
        "group_name": "txn_velocity",
        "group_version": "1.0",
        "ttl_seconds": 600,
        "last_update_event_time": "2026-01-03T12:00:00Z",
        "age_seconds": 2400,
        "stale": true
      }
    ],
    "input_basis": {
      "stream_name": "admitted_events",
      "watermark_basis": { "partition_0": 9812500 }
    },
    "warnings": [
      {
        "code": "STALE_GROUP",
        "group_name": "txn_velocity",
        "group_version": "1.0"
      }
    ]
  }
}
```

---

### A.4 Example — `ErrorResponse` (UNAVAILABLE, retryable)

```json
{
  "kind": "error_response",
  "contract_version": "ofp_public_contracts_v0",

  "error_code": "UNAVAILABLE",
  "message": "Online Feature Plane temporarily unavailable",
  "retryable": true,

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  }
}
```

---

## Appendix B — ASCII sequences (update/apply, duplicate no-op, get_features, replay parity)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/upsert
> Notes like `[idemp=…]` show the update idempotency key concept.

---

### B.1 Event update/apply (admitted event → idempotent aggregate/state update)

```
Participants:
  EB | OFP(Update Consumer) | OFP(Key Resolver) | IEG | OFP(State/Aggregators) | OFP(Watermarks)

EB --> OFP(Update Consumer): Delivered admitted_event (ContextPins, event_id, event_time, event_type, observed_identifiers)

OFP(Update Consumer): determine affected FeatureKeys
  - if keys not already explicit:
OFP(Key Resolver) -> IEG: resolve_identity(observed_identifiers, ContextPins)
IEG -> OFP(Key Resolver): EntityRefs + graph_version

OFP(Update Consumer): for each FeatureKey + FeatureGroup:
  derive update_id [idemp=(stream,partition,offset,key_type,key_id,group,version)]
  check update_id already applied?

(if not applied)
  OFP(State/Aggregators) => OFP(State/Aggregators): apply event_time-based updates (order-independent)
  OFP(Watermarks) => OFP(Watermarks): advance applied watermark basis (per-partition offset)
  mark update_id applied
(if already applied)
  NO-OP (duplicate safe)
```

---

### B.2 Duplicate delivery no-op (same DeliveredRecord redelivered)

```
EB --> OFP(Update Consumer): Delivered admitted_event (same partition_id + offset)

OFP(Update Consumer): derive same update_id for each key/group
update_id already applied = true

OFP(State/Aggregators): NO-OP
  - no double-count
  - last_update_event_time not corrupted
```

---

### B.3 get_features serving path (snapshot + provenance + deterministic hash)

```
Participants:
  Caller (Decision Fabric) | OFP(Serving API) | OFP(Registry) | OFP(State) | IEG | OFP(Provenance/Hash)

Caller -> OFP(Serving API): get_features(ContextPins, FeatureKeys, FeatureGroups, as_of_time_utc)

OFP(Registry): load group definitions (name+version, key_type, ttl)
OFP(Serving API) --> OFP(State): fetch aggregate state as-of (event_time-driven semantics)

(if request needs identity context or graph signals)
OFP(Serving API) -> IEG: (optional) resolve_identity / get_neighbors
IEG -> OFP(Serving API): context + graph_version

OFP(Provenance/Hash): compute freshness blocks per group (event_time-based)
OFP(Provenance/Hash): assemble provenance (pins, versions, freshness, input_basis watermark, graph_version)
OFP(Provenance/Hash): compute feature_snapshot_hash (canonical serialization + stable ordering)

OFP(Serving API) -> Caller: GetFeaturesResponse(snapshot + provenance + warnings)
```

---

### B.4 Replay parity hook (same basis ⇒ same snapshot_hash)

```
Participants:
  Offline Rebuilder | EB Replay | IEG | OFP (rebuild logic)

Offline Rebuilder: chooses target basis from provenance:
  - ContextPins
  - input_basis watermark vector
  - graph_version (if needed)
  - group versions
  - as_of_time_utc

EB Replay --> OFP/Offline: re-deliver admitted events up to input_basis watermarks
IEG: rebuilt/queried to the same graph_version basis (conceptual)

OFP/Offline: recompute features deterministically at as_of_time_utc using same group versions
OFP/Offline: compute snapshot_hash with same canonicalization rules

Expect: rebuilt feature_snapshot_hash == recorded feature_snapshot_hash
```

---