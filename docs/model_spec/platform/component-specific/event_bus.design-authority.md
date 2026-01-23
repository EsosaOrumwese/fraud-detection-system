# Event Bus Design Authority

This file is a rough collection of design or brainstorm notes for the Event Bus. It views the whole platform as a network and expands open the event bus' position in this network and illuminates it.

---

Yes — even with EB treated as opaque, there are a few **EB-local “laws”** we should pin now, because they’re the assumptions every other component will quietly build on (and if they’re not pinned, joins will drift).

### 1) What counts as “in the bus”

**Pin:** EB contains **only admitted facts** (post-IG). Quarantined/held inputs are *not* “on the bus.” 
Why it matters: keeps “bus = reality” true for consumers; prevents silent second-class streams leaking into hot path.

### 2) Publish truth (what an ACK means)

**Pin:** “Published/ACKed” means **durably appended + assigned stable `{partition_id, offset}`**. IG must treat anything else as “not published.” 
Why: this is the hinge that makes “admission becomes durable fact” non-negotiable.

### 3) Delivery + ordering semantics (what nobody can assume)

**Pin:** Delivery is **at-least-once**, ordering is **partition-only**, and **ts_utc ordering is not guaranteed**. 
Why: forces every consumer (IEG/OFP/DF/DLA/Shadow) to be replay-safe and out-of-order safe.

### 4) Position + checkpoint semantics (the determinism anchor)

**Pin:** The only universally meaningful position is **`(stream_name, partition_id, offset)`**, and a checkpoint `offset` is **exclusive-next** (“next to read/apply”). 
Why: this is literally what later becomes watermarks / `graph_version` / `input_basis`.

### 5) Envelope invariants at the EB boundary

**Pin:** Every EB record’s content is a **Canonical Event Envelope** (EB treats payload as opaque), with required `event_id, event_type, ts_utc, manifest_fingerprint` and optional pins; `schema_version/trace_id/span_id/parent_event_id/producer/emitted_at_utc` are part of the envelope vocabulary.  
Practical pin (important): **EB does not “fix” envelopes**; if it’s not canonical, it shouldn’t arrive at EB (that’s IG’s boundary). 

### 6) Partitioning authority

**Pin:** EB does **not** infer partitioning from domain logic. The publish edge supplies a deterministic `partition_key`/routing decision (v0: **IG stamps it**). 
Why: prevents “bus semantics leak” where EB becomes a hidden domain router.

### 7) Duplicates and dedupe responsibility

**Pin:** EB itself does **not** promise dedupe-by-`event_id`. Duplicates may exist. IG should *aim* to prevent duplicate appends and emit DUPLICATE receipts pointing to originals, but consumers must still be safe.  
Why: keeps the platform honest about at-least-once.

### 8) Corrections posture (no mutation)

**Pin:** No in-place edits. If something must be corrected, it is a **new appended fact** that can reference the original via `parent_event_id` (or an equivalent “supersedes” convention).  
Why: preserves auditability and replay integrity.

### 9) Retention vs archive as one logical stream

**Pin:** EB retention is the hot window; **archive is the continuation of the same admitted fact stream** (same envelope semantics, same event identity), and any replay beyond retention must declare source + basis explicitly. 
Why: keeps training/offline parity possible after time passes.

### 10) Outcome-affecting ops changes are governance facts

**Pin:** Partitioning changes, retention changes, drains/replays/backfills are **operational acts that can affect outcomes** and must be executed via Run/Operate and made auditable as governance facts.  
Why: prevents “someone changed the bus” from becoming an unreproducible mystery.

---

If we lock those pins, then when we move to joins we’ll be reasoning on solid ground: IG can define “admitted,” consumers can define “applied,” and EB remains a clean, non-semantic durability plane.

---

Got it. Treating **EB as an opaque vertex**, the only “design” we can see (and must pin) is the **set of joins/paths that touch it**.

Below is the **complete EB adjacency + all EB-involving paths** that exist in a production-ready version of *your* pinned platform network.

---

## 1) Direct joins that touch EB (EB’s immediate neighbors)

### **Inbound (write-side)**

1. **Ingestion Gate → Event Bus**
   The **only** production write-path for “facts that drive the platform” is: **Producer → IG → EB**. EB does not accept direct producers; IG is the trust boundary and EB is the durability plane. 

### **Outbound (read-side)**

2. **Event Bus → Consumers (general join)**
   Everything downstream reads “admitted facts” from EB under at-least-once + partition-ordering assumptions. 

Concretely, the pinned consumers in your platform graph are:

* **EB → IEG** (projection + graph_version) 
* **EB → OFP** (feature state/provenance; optionally consults IEG) 
* **EB → DF** (decisioning consumes admitted events as triggers/inputs) 
* **EB → AL** (action intents are consumed as bus-carried facts; AL emits outcomes back via IG) 
* **EB → DLA** (audit/flight-recorder consumes the decision/action fact trail) 
* **EB/Archive → Offline Feature Shadow** (history consumption for deterministic rebuild) 

### **Lifecycle/ops adjacency**

3. **EB ↔ Archive continuation**
   Offline can read from EB within retention and from archive beyond retention as the *same logical fact stream* (production posture). 

4. **Run/Operate ↔ EB (operational control edge)**
   Run/Operate is allowed to perform bus ops (retention/backfills/replays/deploy changes) but must keep changes auditable and must not change semantics across environments.  

5. **Observability/Governance ↔ EB (signals edge)**
   EB is a major source of lag/backlog/health signals used for corridor checks and operational posture; governance requires changes be explicit facts, not invisible tweaks.  

That’s the full neighbor set. Everything else is a **multi-hop path** that starts or ends at those joins.

---

## 2) All production paths that include EB (end-to-end)

### A) **Traffic creation → admission → distribution** (the “front door” family)

**A1. Engine business-traffic into the platform (pull model)**
Data Engine outputs (business_traffic datasets) → **IG** (joinability + admit/quarantine/duplicate) → **EB** → {IEG, OFP, DF, AL, DLA, Offline Shadow} 

**A2. DF outputs become platform facts**
DF emits decision/intents (as producer traffic) → **IG** → **EB** → {AL, DLA, Case consumers, Offline} 

**A3. AL outcomes become platform facts**
AL emits outcomes (as producer traffic) → **IG** → **EB** → {DF follow-ons, DLA, Case consumers, Offline} 

**A4. Case/label emissions become platform facts**
Case/label emissions (whatever you choose to stream outward) → **IG** → **EB** → {Offline Shadow / other listeners}
(Truth still lives in Case DB / Label Store; the EB events are the streamed “emissions”.) 

---

### B) **Hot-path decision loop paths** (what “real-time” actually means here)

**B1. Projection path**
EB → **IEG** (build/maintain projection; produce graph_version) 

**B2. Feature path**
EB → **OFP** (update feature state) → DF queries OFP “as-of event time” for decision context
(OFP may consult IEG as part of building canonical keys / provenance.) 

**B3. Decision path (event-triggered)**
EB → **DF** → (decision + intents) → IG → EB 

**B4. Action execution loop (closes the decision loop)**
EB (intents) → **AL** → (outcomes) → IG → EB 

**B5. Audit/flight-recorder path**
EB (decisions/intents/outcomes as they appear) → **DLA** (append-only audit record; quarantine on incomplete provenance) 

---

### C) **Human truth loop paths** (casework + labels)

**C1. Evidence-to-human path**
EB-driven decisions/outcomes produce pointers/evidence → **Case Workbench** (immutable timeline) 

**C2. Human-to-label-truth path**
Case Workbench → **Label Store** (append-only label timelines; effective vs observed time) 

**C3. Labels back into the “learning inputs” stream**
(Label Store truth) + (EB/Archive event history) → **Offline Feature Shadow** 

---

### D) **Offline learning loop paths** (how EB history becomes models)

**D1. Rebuild path**
EB history (within retention) and/or Archive (beyond retention) + Label Store as-of reads → **Offline Feature Shadow** (deterministic datasets/snapshots) 

**D2. Train path**
Offline Feature Shadow outputs → **Model Factory** (training run + evidence + bundle) 

**D3. Promote path**
Model Factory bundle → **Registry** (lifecycle; ACTIVE resolution) → **DF** uses Registry in decisions
(EB is upstream here because the datasets ultimately came from EB/Archive history.) 

---

### E) **Replay/backfill/operations paths** (production reality paths)

**E1. New consumer / rebuild projection**
Run/Operate starts (or re-starts) a projector → projector reads EB from a declared position → builds derived state (IEG/OFP/DLA/Shadow)  

**E2. Backfill (history reprocessing)**
Run/Operate declares a backfill/replay → read EB/Archive basis explicitly → re-run Shadow / rebuild derived stores
(Outcome-affecting changes must be auditable facts.)  

**E3. Quarantine remediation path**
Producer → IG → (quarantine) → (privileged release/reprocess) → IG → EB
(Quarantine is first-class; never drop-and-forget.) 

---

## 3) The “top-of-the-top” simplifier (so you don’t get lost again)

If you remember only one network truth about EB:

**Every meaningful platform fact reaches EB only through IG, and every meaningful derived state/decision/audit/learning loop reads its factual basis from EB (or its archive continuation).** 

---

Good — these two joins are **the spine**. If we pin them cleanly, everything else (IEG/OFP/DF/AL/DLA/Shadow) can be designed without guessing.

I’m going to talk about them as **relationships**: what each side *owns*, what each side *must assume*, and what happens under real production failure.

---

## 1) Inbound join: **Ingestion Gate → Event Bus**

### What this relationship *is*

* **IG is the admission authority** (admit / quarantine / duplicate + receipts + reasons).
* **EB is the fact authority** (durable sequence + replay coordinates).
* “Admission is not done until EB acknowledges append.” 

So this join’s whole meaning is: **IG turns “candidate events” into “admitted events”, and EB turns “admitted events” into durable facts with coordinates.** 

### What crosses the boundary (conceptually)

**From IG to EB**

* A **CanonicalEventEnvelope** (event content) with required `{event_id, event_type, ts_utc, manifest_fingerprint}` and optional pins `{parameter_hash, seed, scenario_id, run_id}` plus trace/provenance fields.  
* A **routing decision** (partition key). EB does *not* infer domain partitioning; IG decides. 

**From EB back to IG**

* Acknowledgment that implies **durable append + assigned position** (partition/offset) and a bus-time like `published_at_utc` (the moment it became durable).  

### Preconditions IG must enforce *before* writing

This is where your platform pins matter most. EB assumes IG has already done these:

1. **Joinability enforcement**
   If the event is meant to drive a particular run/world, IG enforces that the required ContextPins are present and admissible; unknown/unready contexts go to quarantine.  

2. **Canonical boundary shape**
   If it isn’t a CanonicalEventEnvelope, it is not admitted and must not reach EB.  

3. **Deterministic duplicate posture at the boundary**
   At-least-once exists, so IG must treat retries/duplicates deterministically: same event again yields a stable duplicate/admitted-already outcome, not a new “fact.” 

4. **First-class quarantine; no silent drops**
   Malformed/unjoinable/unauthorized/suspicious → quarantine with receipt + evidence pointers. 

### The publish truth we pin (this prevents a ton of drift)

* EB must never “half-ack.” If IG receives an ACK, it **means durable append happened** and a stable position exists. 
* IG must never say “ADMITTED” without that ACK. 

That’s the atomic hinge.

### Failure/retry reality (how this join behaves under stress)

This join lives in the real world, so we need the sober rules:

* **Ambiguous ACKs happen** (timeouts, disconnects). In that case, IG must behave as if *it might have been appended* and retry may create duplicates. That’s acceptable because the platform is built for at-least-once, but IG should still *try* to converge on “one admitted fact” and make duplicates explainable.  
* **Backpressure must be explicit**. EB can throttle/reject; it must not silently drop while ACKing. IG must propagate backpressure to producers / ingestion workers. 
* **Security/trust boundary stays fixed across envs**: IG remains the front door; EB remains the fact log. Local/dev/prod may differ in strictness/scale, not meaning. 

### The one “pin” we should set about partitioning (without going spec-y)

Because EB only guarantees ordering within a partition, **partition choice is a platform-level design lever**. So we pin this now:

* IG’s partition key policy must be **deterministic** (same event → same routing decision), and must be chosen to preserve whatever ordering matters to your hot path (typically “entity-local ordering” rather than global ordering). EB will not rescue you later. 

---

## 2) Outbound join: **Event Bus → Consumers (general join)**

### What this relationship *is*

EB is the shared substrate that lets many independent components observe the same admitted facts:

* EB delivers **admitted canonical events** with **at-least-once** semantics and **partition-only ordering**. 
* Consumers build their own truths (projection, features, decisions, audit, offline datasets) but they must all be replay-safe. 

### What consumers must be able to rely on

1. **Delivery guarantees (and non-guarantees)**

* Guaranteed: within a partition, events are observed in offset order.
* Not guaranteed: global order, causal order across partitions, or time order by `ts_utc`.  

2. **Duplicates/redelivery are normal**
   Consumers must be idempotent under replay/redelivery. The envelope’s `event_id` exists explicitly for idempotency/dedup at ingest/bus boundaries.  

3. **Progress is represented as offsets (“exclusive-next”)**
   This is the determinism anchor: consumer progress is tracked as “next offset to read/apply,” and those per-partition progress tokens are what become watermarks.  

### The key operational rule for consumers (this is the biggest drift trap)

**Consumers must only advance their checkpoint after they have applied the event’s effect to their own durable state.**
If they checkpoint early, replay determinism breaks and you get “phantom applied” behaviour. This is exactly why watermarks are defined as **applied-offset vectors**. 

### What the join enables downstream (why this matters)

* IEG’s `graph_version` is defined by an applied-offset watermark vector (+ stream identity). 
* OFP’s provenance records an `input_basis` watermark vector for snapshot provenance. 

So EB→Consumers isn’t just “streaming.” It’s the platform’s universal answer to: **“what exact facts have you applied?”** 

### How consumers handle “unknowns” without breaking the platform

Even if IG enforces canonical envelope, consumers will still face:

* unfamiliar `event_type`
* new `schema_version`
* payload fields they don’t understand

The pin here is: **unknown must not corrupt truth**. The safe default behaviours are:

* ignore (if not relevant), or
* quarantine *within the consumer’s own truth store* (DLA explicitly does this for incomplete provenance), but do not “rewrite” the bus. 

### Retention pressure is part of this join

Consumers are responsible for not falling so far behind that events expire. If they do:

* it must be an explicit, observable failure state (not silent “just missing history”), and recovery happens via replay/backfill/archival sources.  

---

## Pins I’m setting now (authoritative for our EB join design)

If we agree these are the ground rules, every later design stays clean:

1. **IG is the only admission authority; EB is the durable fact log.** 
2. **IG only says ADMITTED when EB has ACKed durable append with a stable position.** 
3. **EB stores/serves canonical envelopes; it does not validate/transform meaning.**  
4. **EB delivery is at-least-once; consumers must be idempotent using stable event identity.**  
5. **Ordering is partition-only; partition choice is a deliberate platform lever owned by IG.** 
6. **Checkpoints are exclusive-next offsets; watermarks are applied-offset vectors and are the universal replay/provenance token.**  
7. **Semantics don’t change across envs; only operational envelope does.** 

---

Yes — we can (and should) define these joins **even if the consumer vertices are still “black-ish” internally**, because your blueprint already pins the *meaning* of the edges.

I’m going to keep EB opaque and talk purely in **join semantics**: what EB supplies, what the consumer must assume, what the consumer must persist/emit, and what makes the join “production-safe.”

A shared premise for **all** EB→X joins:

* EB gives a replayable fact log where the only universally meaningful position is **(stream_name, partition_id, offset)**; delivery is **at-least-once** and ordering is **partition-only**. 
* Consumer progress is represented as a checkpoint whose offset is **exclusive-next** (“next offset to read/apply”). This is the determinism anchor. 
* Time semantics never collapse: `ts_utc` is domain time; “apply time” is watermark/checkpoint time and is *not written back into the event*. 
* The bus boundary event header is the Canonical Event Envelope (required `event_id, event_type, ts_utc, manifest_fingerprint`, optional pins + trace/provenance fields). 

With that pinned, here are the joins you listed.

---

## a) **EB → IEG** (Identity & Entity Graph projector join)

### What this join *is* (authority split)

* EB is the **fact substrate**; IEG is authoritative for its **projection** and for the meaning of **`graph_version`**. 
* IEG consumes admitted events **assuming duplicates + out-of-order delivery**. 

### What EB must provide to make IEG possible (no more, no less)

* Stable positions (partition+offset) so IEG can define “what has been applied” in a reproducible way. 

### What IEG must do (production safety rule)

* Apply idempotently using an **update_key** derived from **ContextPins + event_id + pinned semantics id** so replay/redelivery can’t double-apply. 
* Persist applied offsets/checkpoints so it can resume without “forgetting what it already applied.” (Rebuildable, but continuity requires checkpoints.) 

### What crosses *out* of IEG to downstream (how it becomes useful)

* Whenever anything downstream uses IEG as context, it records the **`graph_version` that was used**, so the same decision context can be replayed/audited later. 

### What `graph_version` means (pinned; don’t drift)

* `graph_version` is a **monotonic token** representing “what EB facts have been applied,” concretely: a **per-partition applied-offset watermark vector (exclusive-next) + stream_name**.  

---

## b) **EB → OFP** (Online Feature Plane projector join)

### What this join *is*

OFP is an always-on projector that maintains feature state from admitted events and serves snapshots with pinned provenance.  

### What OFP consumes (and what it may consult)

* OFP consumes admitted events from EB; it may optionally query IEG to resolve canonical keys and capture `graph_version` for provenance. 

### Replay safety rule (this is the core of the join)

* OFP’s aggregate updates are idempotent using a key derived from **EB position × FeatureKey × FeatureGroup**:
  `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)` 

This is why EB must expose stable positions and why OFP must treat duplicates as normal.

### What OFP must persist (join requirement, not “internal preference”)

* OFP persists its checkpoints and state for operational continuity (it’s rebuildable, but a hot path can’t rebuild from scratch on every restart). 

### What OFP must return on the serve edge (so the rest of the platform can be audited/replayed)

Every successful feature snapshot must carry provenance including:

* ContextPins
* `feature_snapshot_hash` (deterministic)
* group versions used + freshness/stale posture
* explicit `as_of_time_utc` (no hidden “now”)
* `graph_version` if IEG was consulted
* `input_basis` = applied-event watermark vector
  …and the snapshot hash must deterministically cover the relevant blocks with stable ordering.  

That’s the join contract-of-meaning that makes offline parity possible later.

---

## c) **EB → DF** (Decision Fabric consumption join)

### What this join *is*

DF consumes admitted traffic as one trigger/input channel (it may also accept synchronous decision requests), then emits decisions + action intents back into the platform as canonical events.  

### The pinned time rule (this prevents “hidden now” drift)

* DF treats **event time** as the decision boundary and calls OFP with `as_of_time_utc = event_time_utc` (v0 posture). 

So: EB delivers events with `ts_utc`; DF uses that as the canonical decision time.

### The pinned provenance rule (DF must not hand-wave)

DF must record in its emitted decision provenance what OFP/IEG provided:

* `feature_snapshot_hash`, group versions, freshness flags
* `input_basis` watermark vector
* `graph_version` if IEG was consulted 

### Correctness rule (fail-safe posture)

* DF does not invent missing context: if required features aren’t available, DF records unavailability and follows its pinned fail-safe posture; DF also must obey degrade constraints.  

### How DF’s outputs re-enter EB (important for the network loop)

* Decisions and action-intents are “real traffic” and still enter the rest of the system via **IG → EB**.  

So the EB→DF join is a *consumer* join, but DF closes a loop by becoming a *producer* back through IG.

---

## d) **EB → AL** (Actions Layer consumption join)

### What this join *is*

AL consumes ActionIntents (bus-carried facts), executes side effects, and emits immutable outcomes back as canonical events (again through IG→EB).  

### The pinned idempotency law (because EB is at-least-once)

* AL executes effectively-once via uniqueness on `(ContextPins, idempotency_key)`; duplicates re-emit the same canonical outcome.  

### What AL must persist (so it can be safe under retries/replays)

* Action idempotency truth + outcome history lives in AL’s authoritative store (actions DB). 

### What AL emits back (closing the loop)

* Outcomes are published as canonical envelope events to the traffic stream (via IG).  

---

## e) **EB → DLA** (Decision Log / Audit consumption join)

### What this join *is*

DLA is the immutable “flight recorder.” It consumes the decision/action trail from the bus and writes append-only audit records by-ref with hashes; it is explicitly allowed to quarantine incomplete provenance rather than writing half-truths.  

### What DLA ingests (minimum truth)

* DLA’s primary ingest is DF’s DecisionResponse + provenance; AL outcomes can be ingested to close the loop (intent vs executed), but DF provenance is the non-negotiable base. 
* It may also attach IG receipts/quarantine refs and optional EB coordinates/pointers (as evidence pointers). 

### What the audit record must include (meaning, not schema)

The canonical audit record includes by-ref/hashed pointers to:

* event reference basis (“what was decided on”)
* `feature_snapshot_hash` + `input_basis`
* `graph_version` if used
* degrade posture (mode + enough to identify the mask)
* resolved model/policy bundle ref
* actions including idempotency keys
* audit metadata (`ingested_at`, supersedes link on correction) 

### Immutability + corrections

* Append-only; corrections happen via a **supersedes chain**, not overwrites; ingest is idempotent; incomplete provenance → quarantine. 

This join is what makes later investigations and “why did we do that?” answerable.

---

## f) **EB/Archive → OFS-Shadow** (Offline Feature Shadow job join)

### What this join *is*

OFS-Shadow is the deterministic rebuild lane: it reads event history from EB within retention or from archive beyond retention, treats them as the **same logical fact stream**, joins with Label Store using **as-of** semantics, and produces datasets + DatasetManifests.  

### The critical pins that define this join (production reality)

* Retention differs by environment profile, but semantics of offsets/watermarks/replay do not. 
* Archive is the long-horizon extension of admitted facts, preserving event identity, enabling deterministic replay-basis declarations, and is accessed by pinned by-ref bases (no vague searching).  
* Watermarks remain monotonic even under backfill; rebuild “as-of time T” uses an explicit basis rather than pretending the stream changed.  

### What OFS must output to keep learning reproducible

* OFS emits DatasetManifests that pin replay basis (offset ranges/checkpoints + stream identities), label as-of boundary, join keys/entity scope, feature definition versions, digests/refs, and provenance.  

---

Yep — these three adjacencies are where “production reality” shows up. EB stays opaque; we only pin what the *rest of the network* can assume.

---

## 3) EB ↔ Archive continuation

### What this relationship **is**

Archive is **not a second truth** and not “an offline dataset.” It is the **long-horizon continuation of EB’s admitted fact stream** once EB retention ends. Same logical events, same envelope semantics, same event identity. 

So, from the platform’s point of view:

* **EB = hot window** of the admitted fact log (within retention). 
* **Archive = cold window** of that *same* admitted fact log (beyond retention). 
* Consumers (especially Offline Shadow) may read from EB or Archive, but must treat both as **the same logical stream** and must record which source/basis they used. 

### What must be pinned so this doesn’t drift later

1. **Archive preserves EB identity, not “re-emits”**

* Archive must preserve the event’s **canonical envelope** and **event_id** unchanged. 
* Archive must preserve ordering **by partition**, because the whole replay determinism story is built on partition order + offsets/watermarks. 

2. **Replay basis stays expressible in EB coordinates**
   Your rails pin that EB coordinates are the universal progress token: `(stream, partition, offset)` with exclusive-next checkpoint meaning; higher “versions” are derived from that. 
   So even when reading from Archive, the *basis you record* is still “in EB coordinates” (offset ranges / watermark vectors), not “some archive-specific notion of time.” 

3. **History never rewrites**
   Late arrivals/backfills produce **new offsets** (they don’t retroactively insert into old offsets), and consumers’ applied watermarks never “go backward.” 
   Archive therefore doesn’t need to support “editing history”; it only needs to persist and serve it.

4. **Production-scope decision**
   Your blueprint explicitly calls out the open question: is “training horizon > EB retention” in-scope for v0? 
   For a production-ready platform, the answer is effectively **yes**: otherwise learning parity collapses once retention expires. (Local/dev can run without archive; prod needs it.) This aligns with the environment ladder idea (semantics fixed; operational envelope changes). 

---

## 4) Run/Operate ↔ EB (operational control edge)

### What this relationship **is**

Run/Operate is the **operational substrate** and the **only place platform-wide lifecycle control can live**: start/stop/drain, replay windows, retention, backfills. 
But Run/Operate is **not** allowed to become a shadow source of domain truth: EB remains truth for facts; SR remains truth for readiness; etc. 

### What Run/Operate is allowed to do to/around EB (production moves)

Think of these as the real ops moves the platform must support without breaking determinism:

1. **Retention / archive policy management**

* Adjust retention windows (env-dependent), ensure archive continuity where required. 
* Crucial pin: retention changes are **outcome-affecting operations**, so they must be explicit and auditable (see governance below). 

2. **Drains and controlled shutdowns**

* Coordinate a controlled drain: stop ingress at IG, allow consumers to catch up to a target watermark, then safely stop components.
  This belongs in Run/Operate because it’s platform-wide lifecycle control. 

3. **Replays / backfills**

* Trigger replays/backfills that rebuild derived truths (IEG/OFP projections, offline datasets, parity checks).
  Pinned law: backfill is never silent; it is **declared and auditable**, and outputs are versioned/traceable (not stealth overwrites). 
  Pinned law: watermarks don’t lie — consumers never “go backward”; rebuilds use explicit bases rather than pretending history changed. 

4. **Access / control changes**

* ACLs, producer allowlists, “who can consume what,” kill switches/drains — these are operational acts that can change outcomes and therefore must be governed + traceable. 

### The *safe-change loop* pin (Run/Operate + governance)

Two non-negotiables from your blueprint:

* Run/Operate must not introduce hidden nondeterminism (no silent retries that change semantics, no implicit “now”). 
* Any operational act that can change outcomes must be expressed as an **auditable governance fact** (deployments, config/policy changes, retention changes, backfills/replays, drains). 

And your deployment notes already pin how this shows up in the running network: Run/Operate writes governance facts to durable storage (`gov/…`) and also emits control-plane facts on the bus control topic. 

---

## 5) Observability/Governance ↔ EB (signals edge)

### What this relationship **is**

Obs/Gov is the “make it safe and explainable” plane:

* It defines correlation standards, golden signals, corridor checks, lineage/audit visibility. 
* It does **not** silently mutate behavior; it influences the system only through explicit control surfaces (notably Degrade + governed operations). 

EB is one of the biggest signal sources because it’s where **fact flow** and **lag** become visible.

### What signals must exist (at the relationship level)

You don’t need to pick vendors/tools here; you *do* need the meanings pinned. Minimum EB-adjacent signals that Obs/Gov must be able to observe:

1. **Ingest health**

* publish success/error rates at the IG→EB boundary
* throughput (events/sec), latency to durable append
  This is essential because “ADMITTED means durably appended” is a platform law. 

2. **Consumer health**

* per consumer-group lag (how far behind the head each projector is)
* stuck partitions / stalled checkpoints
  These are the “golden signals” that tell you whether the hot path is coherent or drifting behind reality. 

3. **Retention / archive headroom**

* “how close are we to losing facts from EB retention before consumers/offline have captured what they need?”
  This is how operations stays safe once time passes. 

4. **Anomaly indicators that affect safety**

* spikes in duplicates, spikes in quarantine, schema/version rejection rates (IG policy doing real work)
  These feed corridor checks and can drive degrade constraints. 

### How signals become *action* without becoming a second decision engine

Pinned flow from your blueprint:

* Obs/Gov supplies corridor checks + “golden signals” →
* DL turns that into explicit degrade constraints →
* DF obeys constraints →
* DLA records what constraints were in force. 

And separately:

* Obs/Gov defines the corridor checks Run/Operate must respect to proceed/degrade/halt during operations (deployments, replays, retention changes). 

So EB doesn’t “talk to DL/DF” directly; EB produces signals; Obs/Gov interprets them as checks; DL/RunOperate act through explicit control decisions. 

### Governance facts specifically tied to EB

Anything that changes the behavior/availability of the fact stream must be visible as a governance fact (not hidden in operator chat):

* retention changes
* replay/backfill declarations and completions
* drains / emergency stops
* access/control changes
  This is explicitly pinned as a platform production requirement. 

---

If we keep EB opaque, these three adjacencies boil down to one clean network law:

**EB is the fact-flow spine; Archive keeps the spine continuous when time passes; Run/Operate is the only hand allowed on the spine’s lifecycle controls; Obs/Gov is the monitoring + governed-change layer that turns EB’s health into explicit constraints and auditable operations.**  

---

Cool — the “front door family” is basically **four ways the platform turns something into a replayable fact**.

All four share one spine:

**(Source makes/changes something) → IG (decides admit/quarantine/duplicate + binds it to the right run/world) → EB (durable append + replay coords) → many consumers**. 

Where they differ is: **what the source is**, what “joinability” means, and what the event is *supposed to drive*.

Below I’ll do A1–A4 as end-to-end paths, with the *network obligations* at each hop (no EB internals).

---

## A1) Engine business-traffic into the platform (pull model)

### The path (end-to-end)

1. **SR runs (or reuses) the Data Engine** and verifies required PASS gates. 
2. SR writes the run ledger artifacts and publishes **RunReadySignal + `run_facts_view`** (the downstream join surface: pins + refs to engine outputs and evidence). 
3. **IG (or an ingestion worker operating under IG)** sees READY and uses `run_facts_view` to discover which engine outputs are eligible to become traffic. 
4. IG pulls **only engine outputs whose role is `business_traffic`** (never `audit_evidence` / `ops_telemetry`).
5. Before treating those outputs as authoritative, IG verifies readiness evidence: **segment HashGate PASS** (gate-specific rulebook) and, for instance-scoped outputs, **instance proof bound to exact output locator + digest**.
6. IG wraps/maps each record into a **CanonicalEventEnvelope** and applies admission policy (admit/quarantine/duplicate).  
7. For each admitted event: **IG → EB append**; EB returns stable replay coordinates (partition+offset); IG records receipts/evidence pointers. 
8. EB distributes to all consumer groups (IEG/OFP/DF/AL/DLA/OFS). 

### The critical “join meanings” that must be pinned here

* **READY is a prerequisite to ingestion.** Pull model makes this clean: no READY → no ingestion begins. 
* **Role separation is enforced at ingestion.** Only `business_traffic` becomes EB traffic; engine `truth_products` are read for supervision/case tooling but not treated as traffic.
* **Evidence binding is real, not narrative.** The ingestion decision must be defensible later: “this traffic came from *these* gated engine outputs proven PASS.”  

### Production reality corner cases (that matter for the path design)

* **Restart/resume:** IG pull must be safe under restarts and partial progress. That means events need stable identity so IG can dedupe “already admitted” vs “new.” (At-least-once is assumed everywhere.) 
* **Ordering:** engine output row order is explicitly non-authoritative; the platform must not rely on file order. Any “ordering” property needed later must come from partitioning choice + event time + consumer logic, not “read order.”
* **Start-of-traffic vs READY:** READY means “world join surface exists + evidence pinned,” not “all traffic already published.” That’s fine; if you ever need “traffic fully published” it becomes a *separate* status signal (but not required for v0). 

---

## A2) DF outputs become platform facts

### The path (end-to-end)

1. **DF consumes admitted traffic from EB** (and/or receives synchronous requests) and performs decisioning, obeying Degrade Ladder posture and using OFP/IEG context. 
2. DF produces two kinds of outputs that must become replayable facts:

   * **DecisionResponse** (what was decided + why)
   * **ActionIntents** (what to do next; idempotent) 
3. DF submits these outputs as events to **IG** (never directly to EB). 
4. IG applies admission policy (joinability + envelope validity + duplicate posture) and appends admitted DF outputs to **`fp.bus.traffic.v1`**.
5. EB distributes:

   * AL consumes ActionIntents.
   * DLA consumes DecisionResponse (and later correlates with outcomes).
   * OFS/Shadow consumes everything for offline parity/training inputs. 

### The join meanings that matter most

* **DF outputs are “first-class facts”** because they’re required for audit, replay, and learning. They must re-enter the same durability plane as everything else. 
* **Provenance is not optional** on the DF→IG edge: DF must carry enough provenance (feature snapshot hash, input basis/watermark, graph_version if used, bundle ref, degrade posture) so DLA/forensics can later explain the decision. 
* **Loop discipline:** DF must not accidentally treat its own emitted decision/intents as triggers the same way it treats business traffic (or you get decision feedback loops). This is handled at the EB→DF join by event_type filtering / trigger policy, not by EB magic. 

---

## A3) AL outcomes become platform facts

### The path (end-to-end)

1. **AL consumes ActionIntents from EB** (partition-only ordering; at-least-once delivery). 
2. AL executes side effects **effectively-once** using uniqueness `(ContextPins, idempotency_key)`. 
3. AL emits **ActionOutcome history** (immutable outcomes/attempt record). 
4. AL submits outcomes to **IG**, which admits/quarantines/duplicates and appends admitted outcomes to **`fp.bus.traffic.v1`**.
5. EB distributes outcomes:

   * DLA records the closed-loop evidence chain (intent → outcome).
   * DF may consume outcomes for follow-on decisioning.
   * Case tooling can attach outcomes as evidence.
   * OFS/Shadow uses them as part of replayable history. 

### The join meanings that matter most

* **AL is authoritative for outcome truth**, but EB is where outcomes become replayable platform facts. 
* **The intent→outcome linkage must be explicit** (correlation via event_id/parent_event_id or equivalent) so audit can reconstruct causality without guessing. Your canonical envelope supports parent linkage concepts; DLA is pinned to be able to quarantine incomplete provenance.  
* **Duplicates are expected**: if the same intent is seen twice, AL must not double-execute; it must re-emit the same canonical outcome history. 

---

## A4) Case/label emissions become platform facts

This one is subtle, because **Case Mgmt and Label Store are the truth stores**, not EB. EB carries *emissions* (change facts / notifications / pointers), not the authoritative database truth. 

### The path (end-to-end)

1. Human actions in **Case Workbench** update **case timelines** in the case DB (truth). 
2. Investigators emit assertions into **Label Store** (append-only label timelines; effective_time vs observed_time; as-of reads). 
3. Optionally, these stores emit **bus-visible facts** (low volume) so the rest of the platform can react:

   * case timeline update events
   * label assertion appended events
4. Those emissions still go through an admission boundary (IG) *or* are produced directly to the bus control topic under a tightly governed producer identity — but the platform map you wrote already groups them under the “Producers → IG → EB” intake model, so v0 simplest is: **Case/Label emissions → IG → EB**. 
5. They land naturally on **`fp.bus.control.v1`** (low-volume control facts), not the high-volume traffic topic.
6. Consumers:

   * OFS/Shadow can treat them as triggers (“new labels available; rebuild manifests”), but actual label truth is still read from Label Store as-of. 
   * Governance/audit can correlate “when did this label/case change occur” with other platform facts. 

### The join meanings that matter most

* **Do not mistake emission for truth.** EB facts here are “Label Store asserted X at time Y” (and must carry effective vs observed time semantics), but the authoritative query is still Label Store. 
* **As-of discipline remains:** offline/learning uses Label Store as-of + EB/Archive event history; the emission just coordinates work, it doesn’t replace as-of querying. 
* **Safety/privacy posture:** label/case emissions are privileged, governed producers; they should be low payload and pointer-heavy (by-ref), consistent with your “by-ref default.” 

---

## One unifying “front door” pin (authoritative)

Across A1–A4:

**Anything that should be replayable as a platform fact enters the bus only via a governed admission edge (IG), and becomes a fact only once it is durably appended to EB (traffic or control topic as appropriate).** 

---

Cool — **B is the “real-time loop”** in your platform, meaning:

* facts arrive on EB as **admitted events**,
* the hot services (IEG/OFP/DF/AL/DLA) move forward by **consuming EB** with at-least-once + partition-ordering assumptions,
* and correctness is anchored in **explicit bases** (graph_version / input_basis / provenance), not in “whatever happened to be in memory at the time.” 

I’ll go B1→B5 as **paths/joins**, keeping vertices opaque inside.

---

## B1) Projection path

**EB → IEG (projection + graph_version)**

### What this path is *for*

IEG exists to turn the event stream into a **run/world-scoped identity context** (entities + edges), and to provide a monotonic **`graph_version`** that says *exactly what EB facts the projection reflects*. 

### What EB→IEG means operationally

* IEG is a **consumer** of admitted events; it does not require “perfect ordering” beyond the bus guarantee (partition ordering only). 
* IEG must be safe under duplicates and replay; it cannot assume “each event arrives once.” 

### The one thing we pin here (so later designs don’t drift)

**`graph_version` is defined from applied EB progress**: a monotonic token derived from the per-partition “next_offset_to_apply” watermark vector (exclusive-next semantics). 

That matters because it prevents hand-wavey versions like “timestamp of last update” and makes the entire platform replayable.

### Real-time meaning in B1

IEG is “real-time” if it stays within an acceptable lag corridor behind EB. If it falls behind, *that becomes an explicit system condition* (observed via lag signals), not a hidden failure. 

---

## B2) Feature path

**EB → OFP (feature state) → DF queries OFP “as-of event time”**
(and OFP may consult IEG)

### What this path is *for*

OFP is the “context compiler”: it turns admitted facts into **deterministic feature snapshots** with **snapshot hash + freshness + input_basis** provenance. 

### The two joins embedded in B2

1. **EB → OFP (projector join)**
   OFP consumes EB like IEG does: duplicates possible, partition-only ordering, replayable. Its internal state must be durable enough to resume from checkpoints, but we keep the store mechanics opaque here. 

2. **DF → OFP (serve join)**
   DF does *not* ask “give me your latest.” DF asks **“as-of the event’s time”** (domain time), and OFP returns a snapshot that explicitly declares:

* what it used (feature groups/versions),
* how fresh it is,
* and the **input_basis** watermark vector that anchors reproducibility. 

### Why OFP may consult IEG

IEG supplies canonical identity context (what identifiers map to what entity), so OFP can compute features keyed correctly (and optionally include the `graph_version` used). 

### The pin that prevents “real-time drift”

**DF decisions must be explainable even when OFP is behind.**
So OFP must report freshness/staleness (and DF must handle it deterministically rather than quietly using stale/partial context). This is where degrade posture later becomes relevant. 

---

## B3) Decision path (event-triggered)

**EB → DF → (decision + intents) → IG → EB**

### What this path is *for*

DF is the decisioning core: it consumes admitted events, consults context (OFP/IEG), obeys degrade constraints, and emits **DecisionResponse + idempotent ActionIntents + provenance** back into the fact stream. 

### The critical join semantics

* **EB → DF:** DF must treat EB as the trigger substrate (at-least-once, partition-only ordering). It filters by `event_type` to decide what triggers decisioning. 
* **DF → IG:** DF outputs are not “internal logs.” They are platform facts, so they go through IG (the trust boundary) like everything else. 
* **IG → EB:** once admitted, the decision + intents become durable facts and can be replayed like any other. 

### What makes this “real-time” (and not just streaming)

A decision is “real-time” if:

* it is made relative to the triggering event’s domain time,
* it uses explicitly declared context bases (feature snapshot hash / input_basis / graph_version when relevant),
* and it is emitted promptly enough that downstream actioning still matters. 

### The big drift-trap we pin now: avoiding feedback loops

Because DF writes facts back into EB, DF must not accidentally treat its own outputs as fresh triggers (unless explicitly intended). The safe platform posture is:

* DF is triggered by **business traffic** event types (and perhaps some control facts),
* DF’s own DecisionResponse/Intent events are **not** triggers by default. 

This is a network-level rule, not an implementation detail, and it prevents runaway loops.

---

## B4) Action execution loop

**EB (intents) → AL → (outcomes) → IG → EB**

### What this path is *for*

AL turns **ActionIntents** into side effects and publishes **immutable ActionOutcome history** so the platform can prove what happened. 

### Join semantics (what each edge means)

* **EB → AL:** AL consumes intents under at-least-once delivery; duplicates are expected. 
* **AL internal truth:** AL enforces effectively-once execution via uniqueness on `(ContextPins, idempotency_key)`. That’s the pin that makes duplicates harmless. 
* **AL → IG:** outcomes go through IG (still the trust boundary) and are admitted/quarantined/duplicated with receipts. 
* **IG → EB:** outcomes become durable facts; replay can reconstruct “intent → outcome” history. 

### Real-time meaning here

AL being “real-time” is not “instant actions always.” It’s:

* bounded action lag under normal conditions,
* explicit backpressure/failure signaling under overload,
* and **outcome history** that never lies (no silent drops, no “we think we acted”). 

---

## B5) Audit/flight-recorder path

**EB (decisions/intents/outcomes) → DLA**

### What this path is *for*

DLA is the immutable “flight recorder.” It consumes the hot path fact trail and writes append-only **AuditDecisionRecord** (by-ref + hashes posture), ingest is idempotent, and it may **quarantine incomplete provenance** rather than writing half-truths. 

### Join semantics (EB → DLA)

* DLA consumes EB as a downstream recorder: at-least-once, duplicates possible. 
* DLA’s output is *not* “a stream.” Its truth is the canonical audit record store (append-only, supersedes chains for corrections). 

### What makes this path essential to production readiness

This is what ensures you can answer, later and deterministically:

* what event triggered a decision,
* what context was used (feature snapshot hash / input_basis / graph_version),
* what degrade constraints were in force,
* what intents were issued,
* what outcomes happened,
* and what evidence pointers back that story. 

And the quarantine rule is key: if provenance is incomplete, DLA quarantines instead of polluting the audit truth. 

---

## One cross-cutting pin for “real-time” across B1–B5

**The loop is “real-time” when every step advances on explicit, monotonic EB-anchored bases (checkpoints/watermarks), and any lag/staleness is explicit and handled deterministically (not hidden).** 

---

Yep — let’s treat **C as its own little sub-network** and pin what each path *means* so you don’t get dragged back into “spec-land”.

## C) Human truth loop as a network (what it’s for)

This loop is the platform’s way of separating:

* **Evidence** (“what we decided and did, and why”), from
* **Ground truth** (“what is actually true in the world”),
  without losing auditability or replayability.

Your blueprint pins this very explicitly: RTDL outputs are **evidence**, Case builds an **immutable case story by reference**, and labels become truth **only** in Label Store as append-only timelines with as-of semantics. 

---

## C1) Evidence-to-human path

**DF/AL/DLA pointers → Case Mgmt / Workbench (cases + immutable timelines)**

### What this path *is*

Case Mgmt is the **human work surface** that consumes *triggers + evidence refs* and builds an **append-only case object + timeline** (“what happened / what was done / who did it / when”). It is not a place that *creates truth labels by itself*; it creates the investigation story and produces assertions. 

### What flows into Case (conceptually)

Not raw payload dumps. The pinned “bridge” is:

* **ContextPins** (run/world scope),
* **stable identifiers** (event/decision/action IDs),
* and **by-ref evidence pointers** (audit record IDs, EB coordinates, artifact refs). 

So the Case vertex can always “open the evidence” by dereferencing pointers (DLA record, EB coordinates, feature snapshot ref, model bundle ref), but it does *not* duplicate everything into the case DB just to feel complete. 

### What “pointers” means in practice (still design-level)

There are three natural pointer sources, aligned to your graph:

* **DF decision evidence**: “we decided X” + provenance pointers (feature snapshot hash/ref, input_basis watermark, model/policy bundle ref, degrade mask id). 
* **AL execution evidence**: “we attempted/did Y” + outcome history (effectively-once semantics produce a reliable attempt trail). 
* **DLA audit pointer**: the canonical “flight recorder” record that ties decision→intent→outcome together and is allowed to quarantine incomplete provenance rather than polluting truth. 

So Case Mgmt doesn’t have to “reason about truth.” It consumes a **pre-built evidence trail** and constructs the investigation narrative on top of it. 

### Two production pins to lock here

1. **RTDL outputs stay evidence forever** (unless label policy explicitly promotes some outcomes to labels). Decisions/outcomes are not “truth labels” by default. 
2. **Case timeline is append-only**: investigations evolve; corrections don’t rewrite history, they append new entries (and can reference superseded entries just like audit). 

Also: Case may *optionally* emit case events back to the stream for automation/audit, but it remains the human work surface. 

---

## C2) Human-to-label-truth path

**Case Workbench → Label Store (append-only label timelines + as-of queries)**

### What this path *is*

This is the “truth writing edge”.

Pinned law: **labels become truth only when written to Label Store**. Case Workbench produces assertions; Label Store is the **single source of truth** for labels with effective vs observed time and leakage-safe as-of reads. 

### What a “label” is in your platform

Not a scalar. A label is a **timeline**:

* subject (event/entity/flow)
* label value
* provenance
* **effective_time** (when it is true in the world)
* **observed_time** (when the platform learned it)

That “two-time” structure is the whole reason you can do leakage-safe learning later. 

### Corrections and evolution (critical pin)

Corrections are handled as **append-only truth evolution**: a new assertion on the timeline, not a destructive update. This lets the platform reproduce “what we knew then” vs “what we know now.” 

### Manual interventions (important tie-back to hot path)

If a human wants to change the world (block/release/notify/etc.), the pinned rule is: **only AL executes**. The case UI must request actions by emitting an ActionIntent that goes through the same AL pathway so outcomes remain dedupe-safe and auditable. 

That keeps the human loop consistent with the automation loop: humans don’t get a secret side-channel.

---

## C3) Labels back into the learning inputs stream

**(Label Store truth) + (EB/Archive event history) → Offline Feature Shadow**

### What this path *is*

This is the “turn human truth into training truth” edge.

Pinned law: **learning uses labels only from Label Store** — not from “what the system decided,” not from outcomes heuristics, not from case exports. 

### The core mechanism: leakage-safe “as-of” joins

Training datasets must be built using explicit **as-of** rules:

* events/features taken up to an as-of boundary
* labels taken **as-of the same boundary**
* anything observed after the decision point is excluded unless explicitly modeling delayed feedback

This is how you keep training/serving aligned and prevent silent leakage. 

### Reproducibility pin (why EB/Archive matters here)

The dataset build must be reproducible from:

* the pinned event history source (EB within retention, Archive beyond)
* Label Store timelines
* the declared as-of window / basis

So offline isn’t “export whatever”; it’s a deterministic rebuild from two authoritative truth stores plus an explicit boundary. 

---

## The single “bridge” rule that keeps C clean

Your blueprint says it plainly and it’s worth locking as authority:

**The join across RTDL ↔ Case/Labels is stable identifiers + by-ref evidence pointers (audit record IDs, EB coordinates, artifact refs), not copied payloads.** 

---

Alright — **D is the network that turns “admitted facts + human truth” into “deployable model/policy truth,”** without losing replayability or auditability.

I’ll treat all vertices as black boxes and describe **only the end-to-end paths and what each join *means*** (production-ready, no spec-writing).

---

## D) Offline learning loop network

### What D is doing (one sentence)

It takes **EB/Archive history (what happened)** + **Label Store timelines (what was true)**, builds **reproducible offline feature datasets**, trains/evaluates models into **versioned bundles**, and promotes them via the **Registry**, which DF later resolves deterministically. 

---

## D1) Rebuild path

**EB/Archive + Label Store → Offline Feature Shadow (OFS) → dataset manifests/materialisations**

### What this path is for

OFS is the deterministic “replay compiler”:

* reconstructs feature inputs from event history,
* joins labels safely (as-of),
* and emits datasets that can be reproduced later byte-for-byte given the same basis. 

### The network joins that matter

1. **EB/Archive → OFS**

* OFS reads the admitted fact stream from EB within retention and from Archive beyond retention as the **same logical stream**, just different windows. 
* The *basis* of what it read is explicit (offset/watermark ranges), so rebuild is repeatable. 

2. **Label Store → OFS**

* Labels come only from Label Store truth timelines (effective vs observed time), not from DF outcomes or “what the model said.” 
* OFS joins labels using **as-of discipline** so you can build leakage-safe training views (“what was known when”). 

3. **OFS → outputs**

* OFS outputs are the “training substrate”: feature datasets plus manifests that pin what was used (event basis + label as-of boundary + feature definition versions). 

### The parity sub-path (still inside D1, but important)

OFS isn’t just “offline ETL”; it’s also the parity tool:

* it can produce **parity evidence vs OFP** by rebuilding the same features and comparing against the online snapshot hash for a declared basis. 
  This is how you stop training/serving divergence from becoming a mystery.

---

## D2) Train path

**OFS outputs → Model Factory (MF) → model/policy bundle + evidence**

### What this path is for

MF is the controlled place where “data + code + config” becomes a **bundle** you can later justify, reproduce, and promote. 

### The key joins

1. **OFS → MF**

* MF consumes OFS datasets/manifests as *inputs with pinned provenance* (no “latest dataset” behaviour). 

2. **MF → bundle outputs**
   MF produces a versioned bundle that includes:

* the trained artefact(s),
* evaluation evidence,
* and the provenance needed to replay/defend it (which dataset basis was used, what feature definition versions, what label as-of boundary, what training configuration). 

This is where “training is not a vibe” gets enforced.

---

## D3) Promote path

**Model Factory → Registry → Decision Fabric resolution**

### What this path is for

The Registry is the **single source of truth** for “what bundle is active for this decision context,” with deterministic resolution (no “latest”). 

### The key joins

1. **MF → Registry**

* MF submits bundles to the Registry with lifecycle state (candidate/approved/active/retired). 

2. **Registry → DF**

* DF resolves the active bundle deterministically (compatibility-aware), and records the chosen bundle reference in decision provenance so decisions remain explainable and replayable. 

This is what makes model evolution a governed, auditable progression rather than “someone swapped a file.”

---

## Production reality edges that sit “around” D (and must exist for D to be real)

### Run/Operate scheduling + backfills

* OFS rebuilds and MF training runs are jobs. Run/Operate must be able to schedule them, re-run them, and trigger declared backfills/replays without changing semantics.  

### Governance requirements

* Promotions, backfills, retention/archive changes, and any action that can change outcomes must be auditable governance facts (not silent operations).  

### Environment ladder (local/dev/prod)

* Same network semantics everywhere; only the operational envelope changes (retention, scale, strictness). 

---

## The single most important “pin” for D (authoritative)

**Offline learning is grounded in two truth sources only:**

1. **admitted fact history** (EB/Archive), and
2. **human truth** (Label Store timelines),
   and everything downstream (OFS datasets, MF bundles, Registry activation, DF usage) must be reproducible from explicit bases derived from those. 

---

Alright — **E paths are the “production reality” edges**: they don’t change what the platform *is*, but they decide whether the platform is *operable without lying*.

Across E1–E3, here’s the single governing law we must keep true:

**Facts are immutable (EB/Archive). Operations may rebuild/replace derived state, but must never rewrite the fact stream, and must be declared/auditable so replayability isn’t broken by “invisible ops.”**  

---

## E1) New consumer / rebuild projection

**Run/Operate starts (or re-starts) a projector → projector reads EB from a declared position → builds derived state (IEG/OFP/DLA/Shadow)**  

### What this path exists to solve

* Adding a brand-new consumer (new projector/service), or
* Recovering a projector after corruption/migration, or
* Rebuilding a derived store deterministically from the authoritative fact stream.

### The network meaning (who owns what)

* **EB/Archive owns facts + replay coordinates** (immutable). 
* The projector (IEG/OFP/DLA/Shadow) owns its **derived truth store**, and it is allowed to be rebuilt. 
* **Run/Operate owns the lifecycle control**: start, stop, drain, rebuild orchestration, and ensuring it’s auditable. 

### The one thing that must be pinned in the join

A projector never “starts reading.” It starts reading from an **explicit basis**:

* “from earliest available in EB retention,” or
* “from a specific checkpoint/watermark,” or
* “from archive for older history, then continue on EB.”

If a start basis isn’t explicit, you’ve introduced “hidden now” and destroyed reproducibility. 

### Production-safe posture (how this works without breaking the hot loop)

There are two safe modes:

1. **Catch-up mode (not authoritative yet)**
   Projector starts, reads from declared basis, builds state, but the platform treats it as “warming.” If it serves (like OFP), it must clearly report freshness/lag and DF must obey degrade rules. 

2. **Cutover mode (authoritative for serving)**
   When the projector reaches a target watermark, Run/Operate can switch traffic to it (or switch readers to its store) in a controlled way. The cutover itself is an **ops act** that must be auditable. 

### Failure realities that must be accepted

* **Retention can strand you**: if your declared basis points to facts older than EB retention and there’s no archive continuation, rebuild must fail explicitly (not silently skip). 
* **Checkpoint truth is sacred**: the projector must only advance checkpoints after durable apply to its own store (otherwise “applied watermark” becomes fiction). 

---

## E2) Backfill (history reprocessing)

**Run/Operate declares a backfill/replay → read EB/Archive basis explicitly → re-run Shadow / rebuild derived stores (auditable; no silent changes).**  

### What this path exists to solve

* Fixing a bug in a projector’s logic.
* Introducing a new feature definition that requires recomputation.
* Producing parity evidence or re-training datasets using a different as-of policy.
* Recomputing derived stores after schema/version transitions.

### The network meaning

A backfill is not “replay for fun.” It is a **declared transformation over immutable facts** that produces **new derived artefacts/states**.

So we pin two non-negotiables:

1. **Backfill never mutates facts** (EB/Archive is unchanged). 
2. **Backfill produces new derived versions**, and any adoption of those versions is a governed cutover, not a silent overwrite. 

### What must be explicit for a backfill to be real

For each backfill run, Run/Operate must declare (as an auditable fact):

* **basis**: which stream(s), which partitions, which offset ranges / watermark vector(s), and whether archive was used;
* **target**: which derived store(s) or datasets are being recomputed (IEG projection, OFP features, DLA rebuild, OFS datasets);
* **intent**: why (bug fix, new feature definition, policy change, parity check);
* **cutover plan**: whether this is “for evidence only” or “will replace serving truth.”

This is exactly the boundary between “ops” and “drift.” If you don’t declare those things, you can’t explain later why the system changed.  

### Two safe patterns (choose per target)

1. **Offline/Shadow backfill**
   OFS reprocesses history, emits datasets/manifests; MF trains; Registry may promote. This doesn’t disrupt serving until promotion occurs. 

2. **Online projector backfill (IEG/OFP/DLA)**
   Rebuild into a **new projection generation**, validate parity, then cut over. The old generation remains available for audit/rollback (at least for a bounded period). 

---

## E3) Quarantine remediation path

**Producer → IG → (quarantine) → (privileged release/reprocess) → IG → EB**
(Quarantine is first-class; never drop-and-forget.) 

### What this path exists to solve

Quarantine exists because “admission must fail closed.” In production, you will receive:

* malformed envelopes,
* unjoinable events (unknown run/world, not READY, missing pins),
* suspicious payloads,
* schema/version mismatches,
* policy violations.

Quarantine is how you keep EB clean **without losing evidence**. 

### The network meaning (the important split)

* **IG owns quarantine truth**: why it was rejected/held and the evidence pointer to what was received. 
* **EB owns admitted fact truth**: only after release/reprocess does something become a durable fact. 

So the remediation path is essentially: “make a quarantined candidate eligible for admission — or decide it never should be admitted — with a paper trail.”

### The production-safe remediation flow (still network-level)

There are only a few legitimate remediation outcomes:

1. **Release-as-is**
   A quarantined event becomes admissible because the missing precondition is now true (e.g., SR READY exists; a schema becomes recognized). IG re-evaluates and, if admitted, appends to EB. The admission record must still point back to the quarantine receipt so the chain is provable. 

2. **Correct-then-admit**
   If the payload must be corrected (e.g., missing required pins), the admitted event must be treated as a **new fact that references the quarantined original** (supersedes/parent linkage), so you never pretend the original didn’t exist. 

3. **Reject permanently (with evidence)**
   Some quarantined items are never admitted; that decision is still part of governance/audit (you must be able to show what was rejected and why). 

### The anti-pattern we ban

* “Dead-letter discard with no trace” or “quietly fix and inject without lineage.” That breaks auditability and makes later incident analysis impossible. 

---

## How these three E paths fit together (so you don’t get lost)

* **E1** answers: “How do we (re)create derived state from facts?”
* **E2** answers: “How do we *recompute* derived state/datasets when logic changes?”
* **E3** answers: “How do we keep EB clean while safely handling bad/early/unknown inputs?”

And the spine across all of them is the same: **facts stay immutable; operations are explicit; outcomes are auditable; replay basis is always expressible.**  

---

Yeah — the environment ladder is *exactly* where these EB paths/joins either stay clean or silently drift.

The pinned stance from your deployment notes is: **local/dev/prod run the same platform graph + rails/join semantics; only the operational envelope changes** (scale, retention/archive, security strictness, reliability, observability).

## What must not change across environments (for these EB paths/joins)

These are the “if this drifts, you’ve built 3 different platforms” rules:

* **Same trust boundaries + graph:** IG is the front door for traffic, EB is the fact log, SR is readiness authority, AL executes, Label Store is truth, Registry is deployable truth.
* **Same join semantics/rails:** canonical envelope, ContextPins discipline, no-PASS-no-read, by-ref posture, idempotency, append-only + supersedes, watermark meaning, deterministic registry resolution, label as-of semantics.
* **Same words mean the same thing:** READY / ADMITTED / ACTIVE / LABEL AS-OF / BACKFILL must mean the same across envs.
* **Same EB semantics:** partitions+offsets+consumer groups, at-least-once delivery, checkpoint offset is **exclusive-next**, replay is re-delivery of stored facts (not rewriting).

If these invariants hold, then A/B/C/D/E paths behave “the same”, just smaller or stricter.

## What *is* allowed to differ — and how it impacts the paths

### 1) Retention + archive (biggest EB-adjacent difference)

Retention length is explicitly an **environment profile knob**, but **offset/watermark/replay semantics do not change**.

Practical impact on the paths:

* **Local:** short retention; archive may be off. Your E1/E2 rebuild/backfill flows still exist, but are constrained to the retention window.
* **Dev:** medium retention; archive may be on if you’re testing long-horizon rebuild/training parity.
* **Prod:** long retention **plus archive continuity** for investigations + offline rebuilds + training windows.

This directly touches **D (offline learning)** and **E (replay/backfill)**: if prod depends on archive for “training horizon > EB retention”, local/dev must at least *exercise* the same basis-declaration behaviour (even if the windows are shorter).

### 2) Security strictness (especially IG, Actions, Registry, Label writes)

Local can be permissive, but **the mechanisms must still exist** (IG still admits/quarantines; authn/authz still exists, just looser credentials/allowlists).

Impact on paths:

* **A paths (front door):** IG admission decisions must still be real in local/dev (even if allowlists are wide). Otherwise A1/A2/A3/A4 will “work locally” but fail in dev/prod on auth/quarantine.
* **B paths (hot loop):** AL/Registry/Label writes are explicitly “where security matters,” so local must still route manual actions through AL and label truth through Label Store (no side channels).

### 3) Observability depth (signals exist everywhere; strictness differs)

Sampling/verbosity can differ by env, but **propagation semantics are identical** (trace context preserved IG→EB→downstream).

Impact on paths:

* **B (hot path):** “real-time” is defined by lag/watermark age and staleness rates; those signals must exist even locally (maybe you eyeball them instead of paging).
* **E (ops):** retention changes/backfills/promotions must emit governance facts in all envs; prod just enforces approval gates and stricter auditing.

### 4) Scale/reliability

Throughput, concurrency, HA/backups can differ — but they should not change the meaning of the joins.

## The main “gotcha” to watch for with EB joins across envs

**Partitioning differences can hide or create ordering assumptions.** Even if partition *count* differs between local/dev/prod, the platform must not rely on global order (only partition order). So local should not be “single partition forever” if you want to catch ordering bugs early; dev should mimic prod’s partitioned behaviour enough to flush out accidental assumptions. (This is implied by your “prod-shaped local stack” posture: local should match prod semantics at the interface level.)

## Bottom line

The ladder should change *only* the operational envelope:

* **retention/archive windows**,
* **security strictness**,
* **observability depth / SLO enforcement**,
* **scale/reliability** —
  while keeping A/B/C/D/E **path meanings identical**.

---

Yep. At the “EB is opaque” stage, the environment ladder gives you **a small set of knobs** you’re allowed to turn **without changing platform meaning** — and a few deployment truths to keep you pointed the right way.

## What must never change across local/dev/prod

For EB-related joins/paths, the ladder only works if these stay identical everywhere:

* Same **graph + trust boundaries** (IG is the front door, EB is the durable fact log, SR is readiness authority, etc.). 
* Same **rails/join semantics** (canonical envelope boundary, ContextPins, no-PASS-no-read, by-ref posture, at-least-once + idempotency, watermark/offset meaning, append-only corrections, deterministic registry resolution, label as-of).  
* Same meaning of the words **READY / ADMITTED / BACKFILL / ACTIVE / LABEL AS-OF**. 

That’s the “no three different platforms” pin. 

## Environment profile knobs for EB (the ones you’re allowed to vary)

These are the knobs your deployment notes explicitly allow to differ by environment (and they’re exactly what matters for EB as a vertex). 

### 1) Scale knobs

* Throughput / concurrency expectations (how hard IG can push, how many consumer instances run).
* Partition counts and parallelism *as an operational envelope*, not as a semantic change.
  Practical note: avoid “single partition forever” in local/dev if you want to catch ordering/parallelism bugs early.

### 2) Retention + archive knobs

* How long EB retains the hot window.
* Whether **archive continuation** is enabled and for which environments.
  This knob directly gates whether long-horizon replay/training/investigation is possible beyond retention. Your platform map explicitly calls out the “archive vs retention boundary” as a thing to pin at the platform level. 

### 3) Security strictness knobs (mechanism exists everywhere; strictness changes)

* Producer/consumer authn/authz posture (local permissive; dev “real enough”; prod strict).
* Who can read quarantine lanes / perform replays / change retention.
  The key is: the **same trust-boundary semantics still exist** even locally (IG still admits/quarantines; you just use permissive allowlists/dev creds). 

### 4) Reliability posture knobs

* HA/replication, backups/DR, incident tooling.
* Rolling upgrade discipline and failover expectations.
  These change resilience/cost, not meaning. 

### 5) Observability depth knobs

* Local: inspect-by-hand.
* Dev: dashboards + basic alerts.
* Prod: SLOs + corridor checks + governance dashboards. 

### 6) Cost knobs

* Anything that trades money for safety/retention/HA/observability, without touching semantics. 

## EB-specific deployment truths worth holding in your head right now

These aren’t “values”; they’re the deployment direction that prevents drift when you later illuminate EB.

### EB is an infrastructure deployment unit; consumers are projectors

Your deployment notes pin the unit taxonomy: EB is infra; IG/DF/AL/DLA/DL are always-on services; IEG/OFP are always-on consumers (“projectors”); SR/Engine/OFS/MF/backfills are jobs. Local can collapse units, but **unit roles stay the same**. 

### Ops that touch EB must be governed facts, not “operator folklore”

Anything outcome-affecting around EB (retention changes, replays/backfills, drains, access changes, major config changes) must be **explicit and auditable** through Run/Operate + governance events, because your platform explicitly bans “prod relies on human memory.”  

### Archive continuity is the big “prod-only” pressure point

If you expect investigations/training horizons beyond EB retention, prod needs archive continuity. Local/dev don’t need the same *scale*, but they should still exercise the *behavior*: “replay basis declared; source window explicit; no silent omissions.”  

### Promotion should feel like “same platform, different posture”

Local → dev → prod is pinned as “same code/binaries and same rails; config/policy posture changes.” That matters for EB because it pushes you to keep **topic semantics and join semantics stable**, and only tune envelope constraints/ACLs/retention/HA knobs per env. 

---

If you carry just this forward while EB is still opaque:

* lock semantics everywhere,
* vary only envelope (scale/retention/security/reliability/observability/cost),
* treat EB-touching ops as governed facts,
* and decide early whether **archive is required for prod parity**.

When you’re ready to “enter EB,” these knobs become the guardrails that shape internal design without letting the platform drift.

---

Yep — understood. One level deeper only: **EB contains a handful of internal subnetworks (modules)**. Each subnetwork is still **opaque**; we’re just naming them and pinning what each one is responsible for.

Here is the **authoritative internal subnetwork map** for a final production Event Bus, aligned to the outer-network guardrails (IG front door, durable append + replay, offsets/watermarks, retention+archive, ops/governance, signals).  

## Internal subnetworks inside EB

1. **Stream Topology & Policy**

* Owns: stream identities (`traffic`, `control`, optional `audit`), partition counts, retention policies, ACL/producer allowlists.
* Does **not** own: payload meaning or schema validation (that’s outside EB).

2. **Publish Ingress**

* Owns: the producer-facing entry edge (IG and a small set of governed control-plane producers), authn/authz enforcement, quotas, backpressure, and the “publish request” lifecycle up to durable commit acknowledgment.

3. **Durable Log Core**

* Owns: the immutable partitioned log itself (append sequencing, offsets, segmenting, replication/persistence).
* This is the central truth: **offsets exist here**.

4. **Fetch / Delivery Egress**

* Owns: consumer-facing read edge (fetch by `(stream, partition, offset range)`), batching, flow control, and delivery metadata (partition/offset/published_at alongside the immutable event bytes).

5. **Consumer Group Coordination**

* Owns: group membership, partition assignment/rebalancing, and the guarantee that within a group each partition has a single active owner at a time.

6. **Checkpoint & Progress Truth**

* Owns: committed progress per `(group, stream, partition)` with **exclusive-next offset semantics** (“next offset to read/apply”), and lag computation support.
* This is what downstream watermarks ultimately rest on. 

7. **Retention & Segment Lifecycle**

* Owns: enforcing the hot-window retention policy (segment sealing, expiry, deletion eligibility).
* Ensures retention never changes “meaning”; it only changes how far back the hot log can serve. 

8. **Archive Continuation**

* Owns: exporting sealed segments to archive storage, maintaining an index that maps `(stream, partition, offset range)` to archived segments, and enabling read-through replay beyond hot retention.
* **Exists as a subnetwork even if disabled in local**; in prod it is enabled when long-horizon replay/training is required.  

9. **Ops / Admin Control Surface**

* Owns: the operational control edge used by Run/Operate (create/alter streams, adjust retention, drains, controlled offset resets where permitted, replay/backfill controls).
* This is the only place “humans/ops” are allowed to touch EB behavior, and it is designed to be governable/auditable.  

10. **Signals & Telemetry**

* Owns: emitting the golden signals Obs/Gov needs (publish latency/errors, head offsets, consumer lag, retention pressure, archive backlog, coordinator churn).
* Produces **signals only**; it does not decide degrade or policy outcomes. 

## The minimal internal connectivity (still opaque, just how boxes relate)

* **Publish Ingress → Durable Log Core**
* **Fetch/Delivery Egress ← Durable Log Core**
* **Consumer Group Coordination ↔ Checkpoint & Progress**
* **Retention & Lifecycle ↔ Durable Log Core**
* **Archive Continuation ↔ Durable Log Core** and **↔ Fetch/Delivery** (for read-through)
* **Ops/Admin** touches *Topology/Policy*, *Retention*, *Coordination*, *Archive* (control edge)
* **Signals/Telemetry** taps everything (signals edge)

---

Yes — at this “first-layer inside EB” level, we treat each subnetwork as an opaque node, and we just identify the **joins (edges)** between them and the **canonical internal paths** that run through those edges.

## Internal joins inside EB (subnetwork-to-subnetwork edges)

### Topology & policy joins

* **Stream Topology & Policy ↔ Publish Ingress**
  Publish ingress consults topology/policy for: stream existence, allowed producers, quotas, partitioning config.

* **Stream Topology & Policy ↔ Fetch / Delivery Egress**
  Fetch consults topology/policy for: stream existence, partition count, retention window, read ACLs.

* **Stream Topology & Policy ↔ Consumer Group Coordination**
  Coordination needs stream/partition layout to assign partitions to group members.

* **Stream Topology & Policy ↔ Retention & Segment Lifecycle**
  Retention rules (window/limits) are defined in policy; lifecycle enforces them.

* **Stream Topology & Policy ↔ Archive Continuation**
  Archive enablement + archive retention posture are policy-governed.

* **Stream Topology & Policy ↔ Ops/Admin Control Surface**
  Ops is the *only* internal writer of stream definitions/policies (create/alter streams, ACLs, quotas, retention policy changes). 

### Data plane joins (the immutable fact log spine)

* **Publish Ingress ↔ Durable Log Core**
  Append requests flow in; durable-commit ACKs flow out. (“ACK means durable” is enforced at this join.) 

* **Fetch / Delivery Egress ↔ Durable Log Core**
  Reads by `(stream, partition, offset range)` flow to the log core; immutable records + positions flow back.

* **Retention & Segment Lifecycle ↔ Durable Log Core**
  Lifecycle observes segment boundaries, seals segments, advances low-watermarks, deletes eligible segments.

* **Archive Continuation ↔ Durable Log Core**
  Archive receives *sealed* segments (or equivalent immutable ranges) from the log core lifecycle side.

### Read coordination + progress joins

* **Consumer Group Coordination ↔ Fetch / Delivery Egress**
  Coordination determines *which consumer owns which partitions*; fetch enforces that ownership for “grouped reads”.

* **Consumer Group Coordination ↔ Checkpoint & Progress Truth**
  Commit/read progress flows here; checkpoints are maintained per `(group, stream, partition)` with exclusive-next meaning. 

* **Checkpoint & Progress Truth ↔ Fetch / Delivery Egress**
  Fetch uses checkpoints to serve “resume from committed offset” and to compute lag/bounds (not to change facts).

### Retention ↔ archive joins

* **Retention & Segment Lifecycle ↔ Archive Continuation**
  Lifecycle hands off sealed segments to archive; archive confirms persistence; lifecycle is then allowed to delete hot segments once safe (per policy).

* **Archive Continuation ↔ Fetch / Delivery Egress**
  Read-through: when requested offsets are older than hot retention, fetch routes reads to archive without changing replay meaning.

### Ops/control joins (internal control plane)

* **Ops/Admin Control Surface ↔ Publish Ingress**
  Enables drains/throttles, producer allowlist updates, “stop accepting writes” switches (governed ops).

* **Ops/Admin Control Surface ↔ Fetch / Delivery Egress**
  Enables read throttles, consumer access control changes, controlled pauses.

* **Ops/Admin Control Surface ↔ Consumer Group Coordination**
  Enables controlled group operations: pause/resume groups, force rebalances, controlled partition assignment changes.

* **Ops/Admin Control Surface ↔ Checkpoint & Progress Truth**
  Enables *governed* offset resets (E1/E2 class operations); not an ad-hoc consumer trick. 

* **Ops/Admin Control Surface ↔ Retention & Segment Lifecycle / Archive Continuation**
  Enables retention changes, archive enablement, replay windows, backfill controls (all governed). 

### Signals/telemetry joins (tap edges)

* **Signals & Telemetry ↔ (ALL subnetworks)**
  It taps all of them for golden signals (publish success/latency, head offsets, lag, retention pressure, archive backlog, rebalance churn). Obs/Gov consumes signals; EB does not decide degrade. 

---

## Canonical internal paths inside EB (how joins compose)

### P1) Publish / append path

**Publish Ingress → Durable Log Core**
(with lookups to **Stream Topology & Policy**, and signals emitted via **Telemetry**)

### P2) Consume / fetch path (grouped)

**Consumer Group Coordination → Fetch/Delivery → Durable Log Core (or Archive) → Fetch/Delivery → Consumer**
(Topology consulted; telemetry emitted)

### P3) Commit progress path

**Consumer → Consumer Group Coordination → Checkpoint & Progress Truth**
(then lag is derived from Checkpoint vs Log head; telemetry emitted)

### P4) Replay path (within retention)

**Ops/Admin (declares basis/reset) → Checkpoint & Progress Truth → Consumer resumes via Fetch/Delivery → Durable Log Core**

### P5) Archive continuation path (beyond retention)

**Retention/Lifecycle → Archive Continuation** (write sealed ranges)
and later: **Fetch/Delivery → Archive Continuation** (read-through replay)

### P6) Retention enforcement path

**Retention/Lifecycle ↔ Durable Log Core** (seal → low-watermark → delete eligible segments)
(coordinated with Archive when enabled)

### P7) Ops change path (governed operations)

**Run/Operate → Ops/Admin → (Topology/Policy, Retention, Archive, Coord, Checkpoints)**
(with governance/audit outside EB, signals inside EB) 

---

Yes. Inside EB, the **Stream Topology & Policy** subnetwork is the *internal authority* that makes every other EB subnetwork behave consistently. It is the only place “what streams exist and how they behave” is defined, and it is **read-mostly** (data plane reads it constantly) and **write-only via Ops/Admin** (nobody else mutates it).

Below are the **topology/policy joins** (internal edges) and what each one *means* in a final production EB.

---

## What “Topology & Policy” is authoritative for (so joins don’t drift)

This subnetwork owns exactly these truths:

* **Stream set + identities**: `fp.bus.traffic.v1`, `fp.bus.control.v1`, `fp.bus.audit.v1` (audit is optional at platform level, but if present it’s defined here).
* **Per-stream invariants**:

  * partition count (fixed for the lifetime of a stream version)
  * routing algorithm identity (fixed for the lifetime of a stream version)
  * retention window policy (time-based) + segment sizing policy
  * archive continuation enabled/disabled (fixed for the lifetime of a stream version)
  * ACL policy: who may produce / who may consume
  * quotas: per-producer publish rate/bytes; per-consumer fetch limits
  * max record size
* **PolicyEpoch**: a monotonic generation number that advances on every policy/topology change (internal coherence token).

Everything else is *not* topology/policy (payload meaning, schema validity, joinability) and stays outside EB or in other subnetworks.

---

## Join 1: **Topology & Policy ↔ Publish Ingress**

### Purpose of the join

Make every publish decision deterministic and governed: “is this producer allowed to publish *to this stream*, and under what limits, and how do we route it?”

### What Publish Ingress MUST obtain from Topology & Policy (every time it needs it)

* Stream existence + status (`ACTIVE` vs `DRAINING` vs `FROZEN_WRITES`)
* Producer ACL for that stream
* Quota + max record size rules for that stream/producer
* Partitioning descriptor (partition count + routing algorithm identity)

### Hard pinned outcomes (no ambiguity)

* If the stream does not exist or is not writable: **reject**.
* If producer is not allowed: **reject**.
* If record violates max size/quota: **reject or throttle** (explicit, never silent).
* Routing is computed from topology policy (Publish Ingress does not invent routing).

### The platform-critical policy pins enforced here

* `fp.bus.traffic.v1` producer allowlist is **IG only** (including ingestion workers operating under IG’s identity).
* `fp.bus.control.v1` is allowlisted to SR/Registry/DL/RunOperate (and optionally IG if you want IG to emit control facts).
* `fp.bus.audit.v1` is allowlisted to pointer publishers only (IG/DLA and optionally OFP/IEG/DF).

This join is where those “only writers” rules become mechanically real.

---

## Join 2: **Topology & Policy ↔ Fetch / Delivery Egress**

### Purpose of the join

Make reads safe and consistent: “is this consumer allowed to read *this stream*, and what is the valid replay window?”

### What Fetch MUST obtain from Topology & Policy

* Stream existence + read ACL policy
* Partition count (so fetch can validate partition ids)
* Retention window policy (to compute the earliest-available “low watermark” in hot storage)
* Archive continuation enabled/disabled (so fetch knows whether “older than hot retention” is readable at all)
* Per-consumer fetch limits (bytes/sec, max batch sizes)

### Hard pinned outcomes

* If consumer is not allowed to read: **reject**.
* If requested offsets are below hot retention and archive is disabled: **explicit failure** (not “empty result”).
* If archive is enabled: fetch is allowed to serve older ranges via archive read-through, but the meaning of offsets/replay does not change.

---

## Join 3: **Topology & Policy ↔ Consumer Group Coordination**

### Purpose of the join

Make group assignment coherent: “what partitions exist for this stream and what’s the assignment policy?”

### What Coordination MUST obtain from Topology & Policy

* Partition count per stream
* Whether the stream supports consumer groups (traffic/control yes; audit yes if present)
* Any per-stream group constraints (e.g., max members, required client identity class)

### Hard pinned decisions (to prevent operational drift)

* **Partition count is fixed for the lifetime of a stream version.**

  * Scaling changes *instances and throughput*, not partition topology mid-flight.
  * If you need a different partition topology, you create a **new stream version** (e.g., `fp.bus.traffic.v2`) and do a governed cutover.
    This single rule prevents “partition routing changed → ordering assumptions broke → replay mismatches.”

Coordination still rebalances on membership changes; it does not rebalance because topology changes underneath it (because topology is stable per stream version).

---

## Join 4: **Topology & Policy ↔ Retention & Segment Lifecycle**

### Purpose of the join

Make deletion/expiry governed and predictable: “what is the retention contract for this stream in this environment?”

### What Retention/Lifecycle MUST obtain from Topology & Policy

* Retention window policy (time horizon)
* Segment sizing/sealing rules
* Whether archive continuation is enabled (so lifecycle knows whether it must hand off sealed segments before deletion)

### Hard pinned outcomes

* Retention acts only on **sealed immutable segments**.
* Hot retention deletion is permitted only within the stream’s retention contract.
* Retention never consults “consumer progress” to decide deletion. Consumers are responsible for staying within retention; ops governs retention sizing.

---

## Join 5: **Topology & Policy ↔ Archive Continuation**

### Purpose of the join

Make archive a true continuation of EB, not an ad-hoc export.

### What Archive MUST obtain from Topology & Policy

* Archive enabled/disabled flag (per stream)
* Archive location/class and indexing rules (where segments live; how they’re indexed by offset range)

### Hard pinned decisions

* Archive enablement is **fixed for the lifetime of a stream version**.

  * If archive is off in local, it’s off; if it’s on in prod, it’s on.
  * You don’t “flip archive on later” for an existing stream; you create a new stream version and do a governed migration if you need to change that posture.

This keeps “archive continuation semantics” from becoming a runtime surprise.

---

## Join 6: **Topology & Policy ↔ Ops/Admin Control Surface**

### Purpose of the join

Make topology/policy changes controlled, atomic, and governable.

### What Ops/Admin is the only thing allowed to do

* Create streams (bootstrap)
* Create **new stream versions** (traffic.v2/control.v2 etc.)
* Adjust retention windows (within the bounds of the environment profile)
* Adjust quotas and ACLs (tighten/loosen within env posture)
* Enter drain/freeze modes (controlled operational states)

### Hard pinned mechanics

* Ops changes apply as an **atomic PolicyEpoch bump**:

  * all EB subnetworks converge on the same PolicyEpoch
  * telemetry always reports the current PolicyEpoch so Ops/Gov can correlate “what policy was active” with observed behaviour

And critically: Ops/Admin is the only writer; every other subnetwork is a reader of topology/policy.

---

## The minimal internal “topology join graph”

Just to visualize the joins you’re illuminating:

```text
                [ Ops/Admin ]
                     |
                     v   (atomic PolicyEpoch updates)
          [ Stream Topology & Policy ]
            |      |        |        |        |
            v      v        v        v        v
       [Publish] [Fetch] [Coord] [Retention] [Archive]
```

---

If this matches your intent, the next join family to illuminate cleanly (without diving inside boxes yet) is the **data-plane spine joins**:

* Publish Ingress ↔ Durable Log Core
* Fetch/Delivery ↔ Durable Log Core

…but we’ll only do that when you say so.

---

Understood. We’ll illuminate **only the data-plane joins** between the opaque subnetworks, and we’ll do it as a designer: clear, decisive, production-shaped.

## Data-plane join 1: Publish Ingress ↔ Durable Log Core

### What this join is

This is the internal edge where “a publish request” becomes “a committed log fact with an offset.” It is the *only* place inside EB that can legitimately assign an offset and say “this record exists.” 

### What crosses the join (conceptually)

**Ingress → Log Core**

* `(stream_name, partition_id)` (already resolved by topology/policy + routing upstream)
* `record_bytes` (the canonical envelope bytes, treated as opaque by EB)
* `publish_metadata` limited to what EB owns (e.g., producer identity class, policy epoch, request id)

**Log Core → Ingress**

* Either a **CommitAck** or a **Reject/Fail**
* CommitAck contains: `(stream_name, partition_id, offset, published_at_utc, policy_epoch)` and a “durably committed” flag that is always true if Ack exists.

### The hard invariants this join enforces

1. **ACK means durable, always.**
   An Ack is only emitted after the record is durably committed according to EB’s durability policy (replication/persistence). There is no “soft ack” mode. 

2. **Offsets are monotonic per (stream, partition).**
   The log core assigns offsets in strictly increasing order per partition, and once assigned they never change.

3. **Commit is atomic for the record.**
   A record is either fully committed (and thus fetchable) or not present. No partial visibility.

4. **Visibility rule:** after CommitAck, the record is eligible to be served by the read path immediately (subject to normal propagation delays), and its position is stable.

### Failure semantics (what the join returns upstream)

This join returns only three classes of outcomes:

* **Committed (Ack)** — durable, positioned, fetchable.
* **Retryable failure** — transient inability to commit (storage/replication pressure, leader movement, internal backpressure). Ingress may retry, and duplicates are acceptable at platform level (at-least-once), but the join itself never pretends success. 
* **Non-retryable rejection** — the log core refuses because the target is not writable (e.g., partition sealed/frozen/draining). Ingress must surface this explicitly.

Importantly: **policy violations are not handled here**; they are rejected earlier at the topology/policy join. If a policy violation reaches this join, that is an EB bug.

### What this join makes possible in the outer network

This is the internal mechanism that makes the platform statement “IG only says ADMITTED when EB has acknowledged append” actually true. 

---

## Data-plane join 2: Fetch / Delivery Egress ↔ Durable Log Core

### What this join is

This is the internal edge where a consumer’s read intent (“give me the next facts”) becomes “here are immutable records in offset order.”

### What crosses the join (conceptually)

**Fetch → Log Core**

* `(stream_name, partition_id)`
* `offset_cursor` and bounds (typically half-open ranges like `[from_offset, to_offset)` or “from_offset + max_bytes/max_records”)
* `read_mode` (hot-only vs allow-archive is decided outside this join; within this join, it is hot-log fetch)

**Log Core → Fetch**

* `records[]` in **strict offset order**
* `head_offset` / `high_watermark` for that partition (so fetch can compute “caught up”)
* `low_watermark` for that partition in hot storage (earliest available offset still retained)
* plus enough metadata to form DeliveredRecords (partition/offset/published_at)

### The hard invariants this join enforces

1. **Fetch is offset-addressed, not time-addressed.**
   Time (`ts_utc`) is payload meaning; EB’s replay primitive is offsets.

2. **Strict partition ordering.**
   Records are returned in increasing offset order, contiguous where available.

3. **No phantom gaps.**
   If an offset is not present, it is not silently skipped. The join either returns what exists or indicates bounds (low/high watermarks) so the caller can decide what to do.

4. **Low watermark is authoritative for hot retention.**
   If `from_offset < low_watermark`, the hot-log cannot satisfy it. This is where the system must decide “use archive” or “fail”; the log core reports the truth.

### Failure semantics

* **Retryable fetch failures** (transient storage/index issues, partition movement) are explicit; fetch retries.
* **Out-of-range** is not “failure”; it’s a reported bound:

  * below low_watermark: “not available in hot”
  * above head_offset: “nothing yet”
* **Unauthorized reads** are not handled here; they are blocked at topology/policy earlier.

### What this join makes possible in the outer network

This is the internal truth that lets every consumer define an applied watermark vector and prove its basis later (graph_version / input_basis). 

---

## Data-plane join 3: Retention & Segment Lifecycle ↔ Durable Log Core

### What this join is

This is the internal edge where “retention policy must be enforced” becomes “segments are sealed and eventually removed from hot storage.”

### What crosses the join (conceptually)

**Lifecycle → Log Core**

* “seal/roll” directives (close current segment, open next)
* “advance low watermark” directives (mark older segments eligible for deletion)
* “delete eligible segments” directives (within retention contract)

**Log Core → Lifecycle**

* segment state (open/sealed), segment boundaries (offset ranges), sizes/ages
* deletion safety status (e.g., “sealed”, “exported to archive if required”, “not referenced”)

### The hard invariants this join enforces

1. **Retention acts on sealed immutable segments only.**
   No deletion of anything that is still being written.

2. **Retention is policy-driven, not consumer-progress-driven.**
   Consumers are responsible for staying within retention; EB does not “hold data forever because someone is behind.” (That belongs to env sizing + ops discipline.) 

3. **Deletion never changes offsets.**
   Deletion simply raises the low watermark; it does not rewrite history.

4. **If archive continuation is enabled, lifecycle cannot delete until export is confirmed.**
   This is the internal enforcement of “archive is continuation, not best-effort.” 

### What this join makes possible in the outer network

It gives you an environment ladder knob (retention window) without changing meaning: the bus semantics remain the same, only the hot window length changes. 

---

## Data-plane join 4: Archive Continuation ↔ Durable Log Core

### What this join is

This is the internal edge that turns EB into a time-complete fact stream: “sealed hot segments become archived segments” with an index that preserves offset-based replay beyond retention. 

### What crosses the join (conceptually)

**Log Core/Lifecycle → Archive**

* sealed segments (or immutable offset ranges) with:

  * `(stream_name, partition_id, offset_range)`
  * record bytes exactly as committed (no transformation)
  * integrity metadata (digests, segment id)

**Archive → Log Core/Lifecycle**

* “persisted + indexed” acknowledgment for that offset range
* archive locator/index entry keyed by `(stream, partition, offset_range)`

### The hard invariants this join enforces

1. **Archive preserves the record bytes and event identity exactly.**
   No re-encoding that changes content; no mutation of envelope; no reinterpretation.

2. **Archive indexing is offset-native.**
   Archive must be queryable by the same primitive as EB: partition + offset range.

3. **Archive makes retention safe.**
   If archive is enabled for a stream version, hot retention deletion is permitted only after archive persistence for the relevant sealed ranges is confirmed.

4. **Archive is a continuation, not a second stream.**
   Reading from archive yields the same logical facts as EB would have yielded at those offsets.

### What this join makes possible in the outer network

It’s what allows offline learning, audit, and investigations to operate beyond the hot retention window without changing replay semantics. 

---

### The designer pin that ties all data-plane joins together

Inside EB, the **Durable Log Core** is the sole truth source for offsets, and every other data-plane subnetwork exists to safely write to it, read from it, or extend it over time (retention/archive), while keeping ops/governance and signals cleanly separated. 

---

## USER: PAUSE FOR REFLECTION

Done — I’ve “snapshotted” what we’ve already pinned in this chat so I don’t drift or contradict it later. I’m going to treat the following as **locked authority** for the rest of the EB design thread unless you explicitly override.

## Locked outer-network truths about EB

* **IG is the admission/trust boundary; EB is the durable fact log.** EB never validates/normalizes meaning; it only persists and distributes admitted facts. 
* **“Published” means durable append + stable position.** If EB ACKs, the record is durably committed and has a stable `(stream, partition, offset)`. 
* **Delivery semantics:** at-least-once delivery; ordering only within a partition; no global ordering. 
* **Progress semantics:** consumer checkpoints are **exclusive-next offsets** (“next offset to read/apply”). Watermarks / `graph_version` / `input_basis` are derived from applied-offset vectors. 
* **Archive is a continuation of EB’s admitted fact stream** for history beyond hot retention (same logical facts; replay remains offset-native). 
* **Ops & governance:** outcome-affecting EB operations (retention changes, replays/backfills, drains, access changes) are Run/Operate-governed and auditable; EB surfaces signals, it doesn’t “decide.”  

## Locked stream/topic stance (resolving the earlier ambiguity)

* **Mandatory streams:** `fp.bus.traffic.v1` and `fp.bus.control.v1` (because the platform already uses both). 
* **Optional stream:** `fp.bus.audit.v1` (pointer convenience only; not required for correctness). 
  This replaces my earlier “single mandatory stream” v0 simplification. From here on, the authoritative stance is: **traffic + control are real; audit is optional**.

## Locked “first-layer inside EB” subnetworks (still opaque boxes)

1. Stream Topology & Policy
2. Publish Ingress
3. Durable Log Core
4. Fetch / Delivery Egress
5. Consumer Group Coordination
6. Checkpoint & Progress Truth
7. Retention & Segment Lifecycle
8. Archive Continuation
9. Ops / Admin Control Surface
10. Signals & Telemetry

## Locked topology/policy join meanings

* Topology/Policy is the **only** source of stream existence, partition topology, routing algorithm identity, retention policy, archive enablement, ACLs, quotas; and it is **mutated only via Ops/Admin**. 
* Partition count / routing algorithm / archive enablement are **stable for a stream version**; changing them means a **new stream version + governed cutover** (no “silent topology drift”).

## Locked data-plane join meanings

* **Publish Ingress ↔ Durable Log Core:** ACK only after durable commit; offsets monotonic per partition; no partial visibility. 
* **Fetch/Delivery ↔ Durable Log Core:** reads are offset-addressed; returns strict partition order; reports hot low-watermark/head offsets; never silently skips missing ranges. 
* **Retention/Lifecycle ↔ Durable Log Core:** retention acts only on sealed segments; raises low-watermark; never rewrites offsets; not driven by consumer lag. 
* **Archive ↔ Durable Log Core:** archive stores immutable sealed ranges and is indexed by `(stream, partition, offset-range)` so replay remains offset-native. 

## Environment ladder knobs (allowed to vary without semantic drift)

* Scale (throughput/instances/partition counts per env), retention length, archive on/off, security strictness, reliability posture, observability depth, cost envelope — **but join semantics remain identical across envs**. 

That’s the consistency checkpoint. From here forward, I’ll treat these as the “laws of the world” for EB and won’t contradict them.

---

Got it. We’ll illuminate **only the joins** (edges) between the opaque subnetworks—no internals, no ASCII.

## Read coordination and progress joins

### 1) Consumer Group Coordination ↔ Fetch / Delivery Egress

**Purpose of the join**
Make “grouped consumption” real: *who* is allowed to read *which* partitions *right now*, and ensure a partition is not concurrently processed by two active members in the same group.

**What flows across the join**

* **Coordination → Fetch**

  * `assignment_epoch` (a monotonic generation for the group)
  * `member_id` (the active consumer identity)
  * `owned_partitions` for `(stream, group)`
  * `lease_token` per partition (fencing token)
* **Fetch → Coordination**

  * membership liveness feedback (missed heartbeats / failed fetches that imply a dead member)
  * optional “partition stalled” signals (used for ops visibility, not automatic reassignment logic)

**Hard invariants**

* **Single-owner per partition per group:** at any instant, one partition in one group has at most one active owner (enforced by lease fencing).
* **Fencing is strict:** if a consumer presents a stale `lease_token` or stale `assignment_epoch`, fetch rejects group reads for that partition. This is what prevents split-brain processing on rebalance.
* **Group reads are “authorized by assignment,” not by client intention:** a consumer cannot pull any partition it wants just by asking; ownership must be current.

**Failure / rebalance semantics**

* Rebalance is defined as: **epoch increments → prior leases become invalid → new leases issued**.
* During rebalance, fetch returns explicit “not owner / rebalance in progress” rejections; consumers must re-join and obtain new leases.
* This join does **not** try to preserve “exactly once.” It preserves “no concurrent ownership,” which is the right primitive given the platform’s at-least-once posture. 

---

### 2) Consumer Group Coordination ↔ Checkpoint & Progress Truth

**Purpose of the join**
Make “progress” coherent and defendable: commits are accepted only from the *current* owner of a partition, and the stored checkpoint has the platform’s pinned meaning: **exclusive-next offset** (“next offset to read/apply”). 

**What flows across the join**

* **Coordination → Checkpoint**

  * `assignment_epoch` + `member_id` fencing identity (who is allowed to commit right now)
  * partition ownership map (used to gate commits)
* **Checkpoint → Coordination**

  * last committed offset per `(group, stream, partition)`
  * commit metadata (commit time, committing member, epoch) for auditing/debugging

**Hard invariants**

* **Commit authority is fenced:** only the current partition owner (as per current epoch) can commit progress for that partition.
* **Checkpoints are monotonic forward by default:** committed offsets move forward only.
* **Backward movement is forbidden in normal flow:** any backward offset change is an **ops-controlled reset** (not a consumer action). This keeps “applied watermark vectors” trustworthy.  
* **Checkpoint meaning is fixed:** committed offset = **exclusive-next** (the next offset the consumer will apply). This is the universal basis for watermarks / provenance. 

**Failure semantics**

* If a stale owner tries to commit (rebalance happened), checkpoint rejects.
* If checkpoint store is unavailable, consumers can continue fetching but cannot safely advance committed progress; this is treated as an operational degradation state (signals fire).

---

### 3) Checkpoint & Progress Truth ↔ Fetch / Delivery Egress

**Purpose of the join**
Turn “resume consumption” into a deterministic operation and make lag/pressure observable.

**What flows across the join**

* **Fetch → Checkpoint**

  * “resolve cursor” requests: “start me at the committed position for `(group, stream, partition)`”
  * optional “read-your-writes” checks when a consumer wants to confirm its commit is visible
* **Checkpoint → Fetch**

  * resolved `start_offset` (exclusive-next committed offset)
  * progress snapshots used for lag computation and safety checks

**Hard invariants**

* **Fetch never changes checkpoints.** It may read them to resume or compute lag, but it cannot mutate progress.
* **Resume is deterministic:** “resume” always means “start from committed exclusive-next offset.”
* **Lag is computable and consistent:** fetch combines `(partition head offset)` from the log core with `(committed offset)` from checkpoint truth to produce lag/pressure signals; this is how Obs/Gov and Run/Operate get reliable operational visibility. 

**Failure semantics**

* If checkpoint lookup fails, fetch can still serve explicit offsets (stateless reads) but cannot serve “resume from group position.” That becomes an explicit failure mode for grouped consumers.

---

## Retention and archive joins

### 4) Retention & Segment Lifecycle ↔ Archive Continuation

**Purpose of the join**
Make “archive is continuation” true, not best-effort. Retention enforces the hot-window policy, and archive preserves older facts without changing replay semantics. 

**What flows across the join**

* **Lifecycle → Archive**

  * sealed immutable segment (or sealed offset range) identified by:

    * `(stream, partition, offset_range)`
    * integrity material (segment digest / content digest)
  * “export intent” bound to the current stream version / policy epoch
* **Archive → Lifecycle**

  * `archive_persisted_ack` for that `(stream, partition, offset_range)` including:

    * archive locator/reference
    * index confirmation (the offset range is discoverable for reads)

**Hard invariants**

* **Only sealed ranges may be archived.** Open/active ranges are never exported.
* **Deletion safety gate:** if archive is enabled for a stream version, hot retention deletion for a sealed range is allowed only after archive persistence+index ack for that range. This is the internal enforcement that keeps history continuous. 
* **Archive is offset-native:** archival indexing is keyed by `(stream, partition, offset_range)` so replay remains anchored in EB coordinates.

**Failure semantics**

* Archive lag is treated as a first-class operational condition (retention pressure rises). If archive cannot keep up, EB must apply explicit protective posture via backpressure upstream (through publish ingress), not silent data loss. 

---

### 5) Archive Continuation ↔ Fetch / Delivery Egress

**Purpose of the join**
Enable read-through replay beyond hot retention **without changing what “offset replay” means**.

**Read classes (pinned)**
EB supports two distinct read intents:

1. **Hot reads (default for always-on consumers):** must stay within hot retention; if requested offsets are below hot low-watermark, the read fails explicitly.
2. **Historical reads (declared replay/backfill/offline):** allowed to read from archive beyond hot retention, governed by policy/permissions and typically initiated by Run/Operate or offline jobs.  

This prevents “a lagging hot consumer silently starts reading months of archive” and blowing up production.

**What flows across the join**

* **Fetch → Archive**

  * `(stream, partition, offset_range)` requests (same primitive as hot fetch)
  * authorization class (“historical read capability”)
* **Archive → Fetch**

  * immutable records for that offset range, in strict offset order
  * optional segment boundary metadata (for efficient paging)

**Hard invariants**

* **No semantic differences:** records served from archive preserve:

  * the same event bytes that were committed,
  * the same offsets/partition identities,
  * and consistent `published_at_utc` (or a stable archival metadata mapping that doesn’t alter the event content).
* **No silent truncation:** if archive cannot serve a requested range, fetch returns explicit failure for that range.

**Failure semantics**

* Archive unavailable → historical reads fail explicitly; hot reads continue unaffected.
* If a range straddles hot/archived boundary, fetch is responsible for stitching the result without gaps or duplicates, using hot low-watermark and archive index truth.

---

Understood. We’ll illuminate **only the joins** for:

* **Ops/Admin Control Surface ↔ {other EB subnetworks}** (internal control plane)
* **Signals & Telemetry ↔ {all subnetworks}** (tap edges)

No ASCII, and I’m declaring what *is*—not “maybes”.

---

## Ops/Admin Control Surface joins

### What Ops/Admin *is* inside EB

Ops/Admin is the **only internal actuator** allowed to change EB’s runtime posture or policy/topology state. Everything else is data-plane or coordination/progress. Any action that can affect outcomes (retention, offset resets, access) is executed through Ops/Admin and is externally governed by Run/Operate/Gov (outside EB), but internally enforced here.  

I’m pinning an internal rule for all Ops joins:

**Every Ops/Admin action is (a) fenced by authority/permissions, (b) idempotent by a stable op_id, (c) applied atomically at a defined scope, and (d) emits an internal OpsEvent with the active PolicyEpoch/AssignmentEpoch so later forensics can correlate behaviour to configuration.** 

### 1) Ops/Admin ↔ Publish Ingress

**Purpose:** control and protect the write edge without changing payload meaning.

**What Ops/Admin can do through this join**

* **Ingress mode per stream:** `ACTIVE` / `DRAINING` / `FROZEN_WRITES`

  * `DRAINING`: reject new publishes with a retryable “draining” signal (explicit backpressure).
  * `FROZEN_WRITES`: hard reject (non-retryable) except for explicitly allowed control-plane streams if you choose (but traffic stream freezes are absolute).
* **Throttle knobs:** per-stream and per-producer quotas (rate/bytes), burst limits.
* **Emergency denylist / allowlist enforcement:** *tightening* producer access immediately (never loosening traffic stream beyond IG-only). 

**Hard invariants enforced at this join**

* `fp.bus.traffic.v1` remains **IG-only** as producer. Ops/Admin cannot override that invariant; it can only tighten (e.g., freeze/drain). 
* Any throttling/rejection is **explicit** (visible to IG and telemetry); no silent drops. 

---

### 2) Ops/Admin ↔ Fetch / Delivery Egress

**Purpose:** control read pressure and enforce “hot vs historical read” separation without changing replay semantics.

**What Ops/Admin can do**

* **Read throttles:** per stream / per consumer identity class.
* **Read modes:** enforce that always-on consumer groups are **hot-only** (cannot fall back to archive), while historical replay identities (offline/backfill) are allowed archive reads.  
* **Controlled pause:** pause delivery for a specific consumer group or stream (used during coordinated drains / incident response).
* **Access changes:** tighten consumer ACLs immediately (again: tightening is always allowed; loosening is governed externally, but enforced here).

**Hard invariants**

* Fetch never “fills gaps” by changing meaning. If hot retention can’t satisfy an offset and the consumer is not historical-enabled, the read fails explicitly. 

---

### 3) Ops/Admin ↔ Consumer Group Coordination

**Purpose:** make coordinated operational moves (drains, rebalances, freezes) without split-brain.

**What Ops/Admin can do**

* **Group mode control:** `ACTIVE` / `PAUSED` / `DRAINING`

  * `PAUSED`: stop issuing/renewing leases; consumers stop fetching under group semantics.
  * `DRAINING`: allow existing owners to continue up to a declared target watermark, then stop issuing new work.
* **Force rebalance:** bump assignment epoch, revoke all leases, require rejoin.
* **Fence a member:** evict a bad/stuck consumer, revoke its leases immediately.

**Hard invariants**

* Epoch fencing is absolute: Ops/Admin changes that alter group state always bump an epoch/lease boundary so stale consumers cannot continue processing. This is how you prevent double-processing during incident ops.

---

### 4) Ops/Admin ↔ Checkpoint & Progress Truth

**Purpose:** make progress changes governable; prevent “consumer hacks” from rewriting history.

**What Ops/Admin can do**

* **Controlled offset reset** for a `(group, stream)` scope:

  * rewind (replay) to a declared offset basis,
  * fast-forward (skip) to a declared offset basis (rare, high-risk),
  * or set to “earliest available hot” / “earliest archived available” as an explicit policy-driven selection (never implicit).
* **Checkpoint freeze/hold:** block further commits (used during investigations/backfills).
* **Checkpoint snapshot export** (for audit/support): record “this group was at watermark vector W at time T”.

**Hard invariants**

* Normal consumer commits are **monotonic forward**. Backward movement is **ops-only**. 
* Any reset is fenced by a new checkpoint epoch so old owners cannot commit over it.
* Every reset produces an OpsEvent that can be linked to the external governance/backfill declaration. 

This join is what makes E1/E2 operable without destroying determinism.

---

### 5) Ops/Admin ↔ Retention & Segment Lifecycle / Archive Continuation

**Purpose:** manage time (retention, archival continuity) as an operational envelope knob without semantic drift.

**What Ops/Admin can do**

* **Retention window changes** within environment policy bounds (local/dev shorter, prod longer). 
* **Deletion holds:** temporary “do not delete” holds (incident/investigation) that suspend hot deletion while still allowing append and reads.
* **Archive operations:** pause/resume export, force index rebuild, drain archive backlog, and declare “archive health status” used by ops planning.
* **Stream-version governance actions:** when you must change *invariants* (partition topology, routing identity, archive enablement posture), Ops/Admin creates a **new stream version** and coordinates a governed cutover—never mutating the existing stream version’s invariants. 

**Hard invariants**

* Archive enablement / routing identity / partition topology are **stable per stream version**; ops changes are done via new version + cutover, not in-place mutation.
* If archive continuation is enabled, lifecycle deletion is gated on archive persistence/index acknowledgment (so continuity is real). 

---

## Signals & Telemetry joins (tap edges)

### What Signals/Telemetry *is* inside EB

Signals/Telemetry is a passive tap network that produces **observability truth** (rates, lags, pressures, errors) for Obs/Gov and Run/Operate. It does not decide degrade; it just makes the state measurable. 

### The tap edges (what is tapped from each subnetwork)

I’m pinning the minimum signal families that must exist:

1. **From Publish Ingress**

* publish request rate, ack rate, reject rate (by reason), throttle/backpressure events
* publish latency distribution (to durable ack)
* bytes in/out

2. **From Durable Log Core**

* head offsets per `(stream, partition)`
* low watermark per `(stream, partition)` (hot earliest available)
* storage pressure (segment counts/bytes), replication/commit health

3. **From Fetch/Delivery**

* fetch latency, fetch bytes, throttle events
* hot vs archive read counts (historical reads only)
* out-of-range and low-watermark violations (a leading indicator of retention problems)

4. **From Consumer Group Coordination**

* group membership churn, rebalance frequency/duration
* lease revocations/fencing events (split-brain prevention indicators)

5. **From Checkpoint/Progress**

* commit rate/latency, commit rejections (stale lease/epoch)
* lag per group (head offset minus committed offset)
* offset reset events (always high-signal, governance-correlated)

6. **From Retention/Lifecycle**

* deletion rate, deletion holds active, retention pressure (how close hot window is to losing needed history)
* sealed segment production rate (feeds archive load)

7. **From Archive Continuation**

* export backlog, export latency, index completeness/health
* archive read latency and index miss rate

8. **From Ops/Admin**

* ops actions applied (freeze/drain/throttle/reset/retention changes)
* current PolicyEpoch / AssignmentEpoch / stream-version in force

### Non-negotiable telemetry design pins

* **Everything is keyed** by `stream`, `partition`, and the relevant epochs (PolicyEpoch, AssignmentEpoch) so you can correlate behavioural changes to controlled operations.
* **Signals are environment-scaled, not environment-changed**: local may emit to logs, prod to full telemetry stack; the *meaning* of each signal is identical. 
* **Signals are consumable by Obs/Gov** to power corridor checks and by Run/Operate to execute safe drains/backfills; EB itself never turns signals into policy outcomes. 

---

Yep. Here are **P1–P4** as *internal EB paths* (still staying at “path level”, not opening boxes). I’ll describe each path as: **what triggers it, the sequence across subnetworks, what is guaranteed, what fails, and what the rest of the platform can rely on.**

---

## P1) Publish / append path

**Purpose:** turn a publish request into a **durably committed fact** with a stable `(stream, partition, offset)`.

### Trigger

A producer (in practice: **IG** for `fp.bus.traffic.v1`, plus governed control producers for `fp.bus.control.v1`) submits a publish request.

### Sequence across EB subnetworks

1. **Publish Ingress → Topology & Policy**

   * Confirms stream exists and is writable (not draining/frozen).
   * Confirms producer identity is allowed for the stream.
   * Applies quotas/max record limits.
   * Confirms routing identity + partition topology for the stream version.

2. **Publish Ingress → Durable Log Core**

   * Hands off `(stream, partition_id, record_bytes)` for append.

3. **Durable Log Core commits**

   * Assigns the next offset for that `(stream, partition)`.
   * Persists/replicates per durability posture.
   * Only after commit completes does it return success.

4. **Durable Log Core → Publish Ingress**

   * Returns **CommitAck** containing stable `(stream, partition, offset)` + `published_at_utc` + policy epoch.

5. **Signals & Telemetry taps**

   * publish latency, reject reasons, commit health.

### Hard guarantees (what is *true* if ACK exists)

* **ACK = durably committed + positioned.** No soft ACKs.
* Offset is stable and monotonic per partition; record becomes fetchable by offset.

### Failure outcomes (what the path returns)

* **Reject (non-retryable):** not allowed / not writable / record too large / stream frozen.
* **Throttle/backpressure (retryable):** quota hit / ingress throttling / transient pressure.
* **Transient failure (retryable):** commit couldn’t complete (e.g., internal movement/pressure).

**Important platform consequence:** ambiguous client timeouts can still produce duplicates (client retries after a timeout), but EB never lies about ACK. At-least-once is upheld end-to-end.

---

## P2) Consume / fetch path (grouped)

**Purpose:** deliver admitted facts to consumers with **partition-only ordering** and strict group ownership fencing.

### Trigger

A consumer in a consumer group requests “give me records for my assigned partitions starting from my cursor.”

### Sequence across EB subnetworks

1. **Consumer Group Coordination → Fetch/Delivery**

   * Consumer must present a *current* group assignment epoch and per-partition lease/fencing token.
   * Fetch validates the consumer is the current owner for the partition(s).

2. **Fetch/Delivery → Topology & Policy**

   * Confirms read ACLs, stream version, partition existence.
   * Applies per-consumer fetch limits.
   * Applies “read class” policy:

     * **Always-on groups are hot-only** (they do not silently fall back to archive).
     * Historical reads are separately authorized and handled as “historical read identity/class”.

3. **Fetch/Delivery → Durable Log Core**

   * Requests records by `(stream, partition, offset_cursor, bounds)`.

4. **Durable Log Core → Fetch/Delivery**

   * Returns records in strict increasing offset order (per partition).
   * Returns head offset and hot low watermark for bounds truth.

5. **Fetch/Delivery → Consumer**

   * Delivers `DeliveredRecord`s: immutable event bytes + bus metadata (partition/offset/published_at).

6. **Signals & Telemetry taps**

   * fetch latency, out-of-range, lag signals, rebalance churn indicators.

### Hard guarantees

* **Within a partition:** records delivered in offset order.
* **Within a group:** a partition has only one active owner at a time (fenced by epoch/lease).
* **No silent gaps:** if consumer requests below hot low watermark and it’s a hot-only identity, it gets an explicit failure—not an empty result and not “archive magic.”

### Expected “non-guarantees”

* No global order.
* Duplicates may be delivered (at-least-once), especially across rebalances or retries.

---

## P3) Commit progress path

**Purpose:** turn “I have applied up to X” into durable **checkpoint truth** with **exclusive-next semantics**.

### Trigger

After a consumer has **durably applied** records to its own truth store, it commits progress.

### Sequence across EB subnetworks

1. **Consumer → Consumer Group Coordination**

   * Commit request includes `(group, stream, partition)` plus `assignment_epoch/lease` fencing identity and the committed offset.

2. **Consumer Group Coordination → Checkpoint & Progress Truth**

   * Coordination verifies the committing member is the current owner (epoch/lease fencing).
   * Checkpoint store accepts the commit only if fenced correctly.

3. **Checkpoint & Progress Truth persists**

   * Stores committed offset with fixed meaning: **exclusive-next** (next offset to read/apply).
   * Updates lag computability against head offsets (telemetry derives lag from head − committed).

4. **Signals & Telemetry taps**

   * commit latency/rate, commit rejections, lag, stuck partitions.

### Hard guarantees

* **Only current owners can commit.** Stale owners are rejected.
* **Offsets move forward in normal flow.** Backward movement is ops-only.
* **Meaning is fixed:** committed offset = “next to apply,” which is what downstream watermarks must reflect.

### The single most important operational discipline

Consumers must commit **after apply**, never before. This is what makes “applied watermark” a real provenance basis.

---

## P4) Replay path (within retention)

**Purpose:** perform an explicit, governed rewind/seek for a consumer group **without rewriting facts**.

### Trigger

Run/Operate initiates a replay/backfill operation, and **Ops/Admin** executes it inside EB (consumers cannot do this ad-hoc).

### Sequence across EB subnetworks

1. **Run/Operate → Ops/Admin**

   * Declares replay intent + basis (scope: group/stream/partitions; target offsets within hot retention).
   * Ops/Admin validates permissions and that the requested offsets are satisfiable in hot retention.

2. **Ops/Admin → Consumer Group Coordination**

   * Puts group into a controlled state (`PAUSED` or `DRAINING`) and bumps assignment epoch to fence old owners.

3. **Ops/Admin → Checkpoint & Progress Truth**

   * Applies a controlled checkpoint reset to the declared offsets (within retention).
   * This reset is stamped with an ops epoch/op_id so it can’t be “overwritten” by stale commits.

4. **Consumer resumes via Fetch/Delivery**

   * Consumers re-join, obtain fresh leases, and fetch starting from the new committed offsets (exclusive-next semantics).
   * Fetch reads from the Durable Log Core using offsets; facts are unchanged.

5. **Signals & Telemetry taps**

   * “offset reset executed” is a high-signal event; plus subsequent lag/catch-up metrics.

### Hard guarantees

* **Replay does not change history.** It only changes where a group resumes reading.
* **Resets are fenced and explicit.** Stale consumers cannot keep committing over the reset.
* **Within retention only** for this path. If the target offsets are below hot low watermark, this path must fail (or it becomes an archive/historical replay path, which is a different, explicitly authorized mode).

### Production truth you should keep in mind

A replay is only safe if the consumer’s *own* derived store is also handled correctly (wipe/rebuild or build a new generation). That coordination is owned by Run/Operate and the consumer component, not EB—but EB provides the only safe, explicit “rewind basis” mechanism.

---

## P5) Archive continuation path (beyond hot retention)

### Purpose

Keep **one logical admitted-fact stream over time**: EB serves the hot window; Archive serves older ranges **without changing replay semantics** (still offset-native). 

### Trigger A: exporting sealed history

1. **Retention & Segment Lifecycle → Topology & Policy**
   Confirms archive is enabled for this **stream version** (stable invariant).
2. **Retention & Segment Lifecycle → Archive Continuation**
   Hands off **sealed** immutable ranges (segments / offset-ranges) for a `(stream, partition, offset_range)`.
3. **Archive Continuation persists + indexes**
   Produces an offset-native index so older ranges remain discoverable by `(stream, partition, offset_range)`.
4. **Archive Continuation → Retention/Lifecycle (export ACK)**
   Confirms “persisted + indexed” for that range (this ACK is what later allows hot deletion).

### Trigger B: reading older history

1. **Fetch/Delivery Egress sees request below hot low-watermark**
2. **Fetch/Delivery → Topology & Policy**
   Checks two things:

   * archive enabled for the stream version
   * reader identity class is allowed to do **historical reads** (offline/backfill), not an always-on hot consumer. 
3. **Fetch/Delivery → Archive Continuation**
   Requests the same primitive: `(stream, partition, offset_range)`
4. **Archive Continuation → Fetch/Delivery**
   Returns records in strict offset order, with the same immutable bytes and stable offsets.
5. **Fetch/Delivery stitches hot+archived results (if needed)**
   No gaps, no duplicates, explicit failure if a range is missing.

### Hard invariants

* Archive serves the **same logical facts**, with **the same offsets** and **unchanged record bytes**. 
* Archive is **not** an automatic fallback for lagging hot consumers; it is an explicitly authorized **historical read** mode. 
* Archive enablement is **fixed per stream version**; changing that means a **new stream version + governed cutover**, never flipping a live one.

### Failure posture

* Archive behind/unavailable ⇒ historical reads fail explicitly; hot consumers remain bounded by hot retention.
* Archive lag becomes an operational pressure signal and can force backpressure at ingress (never silent loss). 

---

## P6) Retention enforcement path

### Purpose

Enforce the hot-window contract **without rewriting history**: retention raises the hot low-watermark and deletes eligible sealed segments. 

### Trigger

Continuous lifecycle enforcement and periodic retention evaluation.

### Sequence

1. **Retention & Segment Lifecycle → Topology & Policy**
   Reads retention window policy + segment lifecycle rules (+ whether archive is enabled).
2. **Retention & Segment Lifecycle ↔ Durable Log Core**

   * seals/rolls segments
   * computes eligibility (age/window)
   * advances the hot **low-watermark**
3. **If archive enabled:**
   Retention deletion is gated on **archive export ACK** for the sealed range (from P5).
4. **Deletion occurs (hot only)**
   Eligible sealed segments are removed; offsets are not reused; history is not rewritten.

### Hard invariants

* Retention acts only on **sealed immutable segments**.
* Retention is **policy-driven**, not consumer-progress-driven (consumers must stay within retention; if not, they fail explicitly or use historical replay). 
* Deletion only moves the **low-watermark** forward; offsets remain meaningful and monotonic.
* If archive is enabled, EB never deletes hot history that has not been safely persisted+indexed in archive. 

### Failure posture

* Retention pressure is explicit (signals).
* “Deletion holds” (ops-imposed) pause deletion without changing semantics.
* If retention is too short for operational reality, that is corrected by env policy/ops (not by changing meaning).

---

## P7) Ops change path (governed operations)

### Purpose

Make all outcome-affecting EB changes **explicit, fenced, and auditable**: ops can change posture and policies *only* through the control surface, with clear epochs and predictable effects.  

### Trigger

Run/Operate initiates an operational act: drains, throttles, retention changes, replays/backfills, access changes, stream version cutovers.

### Sequence

1. **Run/Operate → Ops/Admin Control Surface**
   Supplies an op intent + `op_id` (idempotency) + scope.
2. **Ops/Admin applies fenced control actions to the relevant EB subnetworks**

   * **Topology/Policy:** create streams, tighten ACLs/quotas, enter DRAINING/FROZEN states, create *new stream versions* for invariant changes.
   * **Coordination:** pause/drain groups, force rebalances (epoch bump), evict members.
   * **Checkpoint/Progress:** controlled offset resets (replay), freezes/holds (epoch-fenced).
   * **Retention/Archive:** adjust retention window within env bounds; enable/operate archive only via stream-version posture; place deletion holds.
3. **Every ops act produces an internal OpsEvent + epoch bumps**

   * Policy changes bump a **PolicyEpoch** (internal coherence token).
   * Group state changes bump **AssignmentEpoch** and revoke leases.
   * Offset resets bump a checkpoint epoch / fenced reset token.
4. **Signals & Telemetry emits “ops-change markers”**
   So Obs/Gov and operators can correlate behavior shifts to applied ops. 

### Hard invariants

* Ops actions are **idempotent** (same `op_id` does not apply twice).
* Any change that could produce split-brain processing is enforced via **epoch fencing** (leases/assignments/checkpoints).
* Invariant changes (partition topology, routing identity, archive enablement) are done via **new stream version + cutover**, never in-place mutation.
* Ops changes don’t change platform meaning across environments; they only tune the operational envelope (retention length, strictness, scale, observability depth). 

---

Yes — EB has **loops**, but they’re the *right kind*: loops that advance **pointers** (leases, checkpoints, low-watermarks) and enforce operability, **not** loops that rewrite facts or “self-decide” semantics.

Here are the loops that exist in the internal EB network (using our first-layer subnetworks):

## L1) Consume → apply → commit loop (the core progress loop)

**Consumer Group Coordination → Fetch/Delivery → (consumer applies) → Checkpoint/Progress → back to Fetch/Delivery**

* This is the steady-state loop for every always-on projector (IEG/OFP/DF/AL/DLA groups).
* It repeatedly advances **exclusive-next checkpoints** as work is durably applied. 

## L2) Membership / lease renewal → rebalance loop (anti-split-brain)

**Consumer Group Coordination ↔ Fetch/Delivery ↔ (consumer heartbeats/leases) → Coordination**

* Consumers continually prove liveness; coordination continually enforces **single active owner per partition per group** via epochs/leases.
* When liveness breaks, the loop flips into **rebalance**: epoch bumps → old leases fence out → new assignments issued → consumption resumes.

## L3) Log growth → segment seal → retention enforcement loop (hot window maintenance)

**Durable Log Core → Retention & Segment Lifecycle → Durable Log Core**

* As the log grows, segments seal; retention advances the **hot low-watermark** and deletes eligible sealed hot segments (never rewrites offsets).
* This loop is policy-driven (retention rules), not consumer-progress-driven. 

## L4) Seal → archive export → archive ACK → hot delete loop (continuity loop)

**Retention/Lifecycle → Archive Continuation → (ACK) → Retention/Lifecycle**

* When archive continuation is enabled, sealed ranges are exported and indexed.
* Only after **archive persistence+index ACK** is hot deletion allowed for those ranges. This is what makes “archive is continuation” real. 

## L5) Historical replay loop (ops-fenced)

**Ops/Admin → (pause/drain) Coordination → Checkpoint reset → Consumers rejoin → Fetch/Delivery → Commit**

* Run/Operate triggers it; Ops/Admin executes it inside EB.
* The loop is: fence ownership → reset progress to an explicit basis → replay within retention (or via archive in historical mode) → re-commit forward.

## L6) Signals → governed ops response loop (supervised feedback)

**Signals/Telemetry → Run/Operate/Obs-Gov → Ops/Admin → (policy/controls) → Signals/Telemetry**

* EB emits pressure signals (publish latency/errors, lag, retention pressure, archive backlog).
* Humans/Run/Operate act through the **ops control surface** (throttles, drains, retention tuning, controlled resets).
* EB itself does **not** autonomously change semantics based on signals; the loop is *supervised and governed*, consistent with your rails.  

### What EB explicitly does *not* have

* No “self-healing semantic loop” that rewrites history.
* No automatic “move consumers to archive because they’re behind” loop for always-on services (that would hide failures and break your operational truth).
* No loop that changes partitioning/routing in-place; invariant changes are stream-version cutovers via ops.

---

Yep — before we “go deeper” into the inner nodes, the deployment view you need is basically: **same EB semantics everywhere, different operational envelope**. That’s the environment ladder pin you already set.

## What EB looks like across the environment ladder

### What must be identical in local / dev / prod

These are non-negotiable because they’re the *meaning* of EB in your platform:

* **Same graph + trust boundaries**: IG is the only writer to traffic; EB is the fact log; consumers use offsets/watermarks; archive is continuation (when enabled).
* **Same EB semantics**: Kafka-style partitions + offsets + consumer groups; at-least-once delivery; lag/watermarks are real and observable.
* **Same “history rules”**: retention changes length, not meaning; replay is offset-based; backfills are declared/auditable; watermarks don’t lie.
* **Same words mean the same thing**: READY / ADMITTED / BACKFILL / ACTIVE / LABEL AS-OF.

If any of that drifts, you don’t have an environment ladder — you have three different platforms. 

---

## Environment profiles: what is allowed to differ (EB-relevant knobs)

### Local (laptop)

Local is for fast iteration *without breaking rails*.

* **EB shape:** single broker Kafka-compatible bus is fine; still real partitions/offsets/consumer groups.
* **Retention:** short (hours/days). 
* **Archive:** can be off, but the platform must still behave correctly when reads fall below hot retention (explicit failure unless you’re in historical replay mode).
* **Security:** permissive allowlists/creds, but the *mechanism still exists* (traffic stream is still IG-only; you’re just using dev identities).
* **Observability:** “debug observability” is fine, but it must still be real OTLP-style signals so lag/backpressure is visible.

### Dev (shared integration)

Dev is where EB operational reality starts to bite.

* **EB shape:** multi-broker (e.g., 3 brokers) so rebalances, failures, and partition distribution are exercised.
* **Retention:** medium (days/weeks).
* **Archive:** often on (or at least exercised) so you test “replay beyond retention” and archive completeness verification.
* **Security:** “real enough” to catch unauthorized producers/consumers, quarantine access boundaries, registry lifecycle privileges. 
* **Observability:** dashboards + alerts (even if thresholds are low) because dev must catch the failures prod would catch. 

### Prod (hardened runtime)

Prod is outcomes + safety + governance.

* **EB shape:** HA/managed Kafka-compatible bus; strong isolation; strict ACLs; strong ops posture.
* **Retention:** policy-driven weeks/months.
* **Archive:** on for long horizons (offline rebuilds, investigations, training windows). Archive is the long-horizon extension of admitted facts and must preserve event identity and allow deterministic replay basis declarations.
* **Change control:** strict governance for retention changes, replays/backfills, access changes; “prod never relies on human memory.”
* **SLOs/corridor checks:** lag/backlog/retention pressure must be meaningful inputs to safe operation.

---

## Deployment angles to pin now (before inner-node implementation detail)

### 1) Reference “production-shaped local” substrate

You don’t need a cloud choice; you **do** need a runtime ground that matches semantics:

* Kafka-ish bus, S3-ish object store, SQL DBs, OTLP observability.
  This is what stops “works locally” from being a lie.

### 2) Promotion story for EB-facing behaviour

Promotion is **same binaries + same rails**, different profile/policy posture (endpoints/credentials/retention thresholds/strictness) — not a prod fork.

### 3) Archive/backfill operational contract (because it touches EB directly)

Pin these as “operational truths” now:

* Retention differs by env; offsets/watermarks/replay semantics don’t. 
* Archive is continuation; completeness must be verifiable for a declared window.
* Backfills are declared/scoped/auditable; they regenerate derived state only (never mutate EB facts).

### 4) Historical replay authorization class

This is a deployment/security angle that matters *before* internals:

* Always-on consumer groups are **hot-only**.
* Historical reads (archive) are a **separate, explicitly authorized identity/class** used by OFS/backfills.
  That prevents a lagging hot service from “quietly time-traveling into archive” and pretending it’s healthy.

### 5) “One golden flow” integration run

You want one integration script that hits the full graph end-to-end (SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA + label + offline + registry resolve). That’s the ladder guardrail that keeps EB semantics honest across environments.

### 6) Deployment unit boundaries (to avoid accidental coupling)

EB is **infra**; IG/DF/AL/DLA/DL are always-on services; IEG/OFP are always-on consumers/projectors; SR/Engine/OFS/MF/backfills are jobs. Local can collapse units, but those roles must remain true.

---

## USER: PAUSE FOR REFLECTION

Done — I’ve re-anchored on everything we’ve already pinned so we don’t drift when we start illuminating inner nodes. I’m treating the following as the **authoritative “world state” for EB** going forward (unless you explicitly override).

## 1) EB’s role in the larger platform network

* **IG is the trust/admission boundary; EB is the durable fact log.** EB never validates/normalizes meaning; it only persists and distributes what IG admitted. 
* **“Published” means durably appended + stable position.** If EB ACKs, the record exists durably and has a stable `(stream, partition, offset)`. 
* **Delivery semantics are fixed:** at-least-once; ordering only within a partition; no global order. 
* **Progress semantics are fixed:** committed checkpoints are **exclusive-next offsets** (“next offset to read/apply”). Downstream watermarks / `graph_version` / `input_basis` derive from applied-offset vectors. 
* **Archive is continuation of the admitted fact stream** beyond hot retention, with offset-native replay semantics. 
* **Outcome-affecting EB operations are governed and auditable** (retention changes, replays/backfills, drains, access changes). EB emits signals; it doesn’t decide outcomes.  

## 2) EB’s boundary connections (outer joins we already covered)

* Write-side: **IG → EB** (traffic). 
* Read-side consumers: **EB → IEG, OFP, DF, AL, DLA**, and **EB/Archive → OFS (Offline Shadow)**. 
* Lifecycle/ops adjacency: **EB ↔ Archive**, **Run/Operate ↔ EB**, **Obs/Gov ↔ EB (signals)**.  

## 3) Stream stance (resolved and locked)

* **Mandatory:** `fp.bus.traffic.v1` and `fp.bus.control.v1`. 
* **Optional:** `fp.bus.audit.v1` (pointer convenience only; never required for correctness). 

## 4) EB internal first-layer subnetworks (modules) — still opaque boxes

1. Stream Topology & Policy
2. Publish Ingress
3. Durable Log Core
4. Fetch / Delivery Egress
5. Consumer Group Coordination
6. Checkpoint & Progress Truth
7. Retention & Segment Lifecycle
8. Archive Continuation
9. Ops / Admin Control Surface
10. Signals & Telemetry

## 5) Internal join families we already illuminated (no internals yet)

### Topology & policy joins (what they mean)

* Topology/Policy is the sole authority for stream existence, partition topology, routing identity, retention policy, archive enablement, ACLs, quotas; mutated **only** via Ops/Admin. 
* **Invariant changes are never in-place:** partition topology / routing identity / archive enablement are stable for a stream version; changes require **new stream version + governed cutover**. 

### Data plane joins (what they mean)

* Publish Ingress ↔ Durable Log Core: **ACK only after durable commit**, monotonic offsets, no partial visibility. 
* Fetch/Delivery ↔ Durable Log Core: offset-addressed reads, strict partition ordering, explicit bounds (head/low-watermark), no silent skipping. 
* Retention/Lifecycle ↔ Durable Log Core: policy-driven hot deletion over sealed segments, raises low-watermark only, never rewrites offsets, not driven by consumer lag. 
* Archive ↔ Durable Log Core: sealed ranges exported + indexed by `(stream, partition, offset_range)` so replay stays offset-native. 

### Read coordination + progress joins (what they mean)

* Coordination ↔ Fetch: single owner per partition per group via epoch/lease fencing; stale owners are rejected.
* Coordination ↔ Checkpoint: only current owner can commit; commits are monotonic forward; backward moves are ops-only. 
* Checkpoint ↔ Fetch: “resume” means start at committed exclusive-next; lag is computable and consistent. 

### Retention–archive joins (what they mean)

* Lifecycle ↔ Archive: hot deletion is gated on archive persistence+index ACK when archive is enabled. 
* Archive ↔ Fetch: **historical read mode only**; always-on consumer groups are **hot-only** (no silent archive fallback).  

### Ops/control joins (what they mean)

* Ops/Admin is the only actuator: drains/freezes/throttles, group pause/drain, governed offset resets, retention tuning within env bounds, versioned cutovers. 
* Ops actions are fenced + idempotent (op_id) + epoch-marked (PolicyEpoch/AssignmentEpoch) and always visible via telemetry. 

### Signals/telemetry joins (what they mean)

* Telemetry taps all subnetworks and emits golden signals: publish latency/errors, head offsets, lag, retention pressure, archive backlog, rebalance churn, ops-change markers. Obs/Gov consumes; EB doesn’t decide degrade. 

## 6) Internal paths we illuminated (P1–P7)

* **P1** publish/append; **P2** grouped fetch; **P3** commit progress; **P4** replay within retention (ops-fenced); **P5** archive continuation (export + historical reads); **P6** retention enforcement; **P7** ops change path (governed).  

## 7) Internal loops (what exists; what doesn’t)

* Mechanical always-on loops: consume→apply→commit; membership/lease renewal→rebalance; log growth→seal→retention; seal→archive ACK→delete.
* Ops-supervised loops: governed replay/backfill; signals→Run/Operate/Obs-Gov→ops actions.  
* Explicit non-loops: no rewriting history; no auto “move hot consumers to archive”; no in-place invariant mutation.

## 8) Deployment framing (environment ladder) we locked

* **Same semantics everywhere; different envelope only**: scale, retention length, archive on/off, security strictness, reliability posture, observability depth, cost envelope. 
* Deployment unit boundaries: EB is infra; IG/DF/AL/DLA/DL always-on; IEG/OFP always-on consumers; SR/Engine/OFS/MF/backfills are jobs. 

That’s the anchor. From here, when we “illuminate inner nodes,” I’ll treat all of the above as constraints so we don’t accidentally invent a different EB or accidentally shift trust boundaries or semantics.

---

Yes — illumination should only *reveal machinery*; it must not change the network we’ve pinned.

### The EB internal nodes (first-layer subnetworks)

1. **Stream Topology & Policy**
2. **Ops / Admin Control Surface**
3. **Publish Ingress**
4. **Durable Log Core**
5. **Fetch / Delivery Egress**
6. **Consumer Group Coordination**
7. **Checkpoint & Progress Truth**
8. **Retention & Segment Lifecycle**
9. **Archive Continuation**
10. **Signals & Telemetry**

### The order I want us to illuminate (designer choice)

I want to go in the order that locks invariants first, then data plane, then read/progress, then time/ops, then observability:

1. **Stream Topology & Policy** (defines stream versions, ACLs, partition topology, retention/archival posture)
2. **Ops / Admin Control Surface** (how changes happen safely; epochs/op_id; prevents drift)
3. **Durable Log Core** (the central truth: offsets, commit, segmenting)
4. **Publish Ingress** (enforce “ACK means durable”, quotas/backpressure at the edge)
5. **Fetch / Delivery Egress** (offset-addressed reads, hot vs historical reads)
6. **Consumer Group Coordination** (ownership fencing; rebalances)
7. **Checkpoint & Progress Truth** (exclusive-next progress, resets)
8. **Retention & Segment Lifecycle** (hot window enforcement)
9. **Archive Continuation** (continuity beyond retention; index/read-through)
10. **Signals & Telemetry** (golden signals + ops markers)

Reason for this order: it pins “what exists and how it may change” first (Topology + Ops), then locks the fact-truth core (Log), then the write/read edges, then coordination/progress, then retention/archive time mechanics, and finally signals once we know what must be measured.

If you want a slightly more “data-plane-first” flow, we can swap (3) and (4), but otherwise this is the cleanest sequence to avoid later rework.

---

Got it. We’re illuminating **Stream Topology & Policy** as a *white-box node*, but we’ll keep its internals organized as a few **clear internal machines** that make the rest of EB possible—without changing any of the network laws we already pinned. 

## Stream Topology & Policy

### What this node is

This is EB’s **single source of truth for “what streams exist and what the rules are”**, and the only place in EB that can authoritatively answer:

* what streams exist (`fp.bus.traffic.v1`, `fp.bus.control.v1`, optional `fp.bus.audit.v1`) 
* who is allowed to **produce**/**consume** on each stream (traffic is IG-only as producer) 
* partition topology + routing identity (stable per stream version)
* retention + archive posture (stable per stream version; archive is continuation when enabled) 
* read-class rules (hot-only always-on consumers vs explicitly-authorized historical readers) 

Everything else in EB is a *consumer* of these truths.

---

## The internal machinery inside Stream Topology & Policy

I’m pinning these as the internal “sub-machines” (still compact, but concrete).

### 1) Stream Registry

**Purpose:** hold the canonical inventory of streams and their versions.

**It stores, per stream-version:**

* `stream_id` (traffic/control/audit)
* `stream_version` (v1, v2…)
* invariants (cannot change in-place):

  * partition count
  * routing algorithm identity
  * archive enabled/disabled
* operational posture:

  * stream state: `ACTIVE` / `DRAINING` / `FROZEN_WRITES`
* retention policy (hot window)
* max record size

**Non-negotiable design rule:** if you need to change an invariant (partition count, routing identity, archive enablement), you do **not mutate** the existing version—you create a **new stream version** and do a governed cutover. 

---

### 2) Access Policy Engine

**Purpose:** make “who can write/read” enforceable and deterministic.

**It evaluates:**

* producer allowlist per stream (traffic = IG-only; control = SR/Registry/DL/RunOperate; audit = pointer publishers only) 
* consumer allowlist per stream + per read class:

  * always-on consumer groups are **hot-only**
  * historical/archive reads require explicit “historical reader” identity/class 

This is where “no side channels” becomes mechanically true.

---

### 3) Quota & Limit Policy Engine

**Purpose:** prevent EB from being forced into silent loss.

**It owns:**

* per-producer quotas (events/sec, bytes/sec)
* per-consumer fetch limits (bytes/batch, bytes/sec)
* burst policies
* rejection vs throttling rules (explicit backpressure only; never silent drops) 

---

### 4) Routing Descriptor Authority

**Purpose:** make partition routing stable and predictable.

**It owns (per stream-version):**

* partition count
* routing algorithm identity (e.g., “hash-of-partition_key vX” — identity is what matters)
* rule: routing identity is stable for the stream-version lifetime

Publish Ingress uses this; Fetch/Coordination use it to validate topology, but **routing never depends on payload meaning**.

---

### 5) Retention & Archive Policy Authority

**Purpose:** make time (retention/archive) a *policy knob* without changing semantics.

**It owns:**

* hot retention window policy per stream
* archive enabled/disabled per stream-version (invariant)
* deletion constraints that Retention/Lifecycle must obey (e.g., “if archive enabled, deletion requires archive ACK”) 

This is the place where environment ladder differences plug in cleanly (shorter retention locally, longer in prod), without changing what offsets mean. 

---

### 6) PolicyEpoch & Change Propagation

**Purpose:** stop “half the system saw a change and half didn’t.”

**It owns:**

* a monotonic **PolicyEpoch** that bumps on every topology/policy update
* atomic publish of policy updates (so all readers can converge)
* a strict rule: data-plane components must either:

  * operate on the current epoch, or
  * be rejected/fenced until they refresh

This is what keeps Ops/Admin changes, ACL changes, retention changes, and stream-state changes coherent across EB’s internal subnetworks. 

---

### 7) Stream State Machine

**Purpose:** controlled operational modes without semantic drift.

**States (pinned):**

* `ACTIVE`: normal operation
* `DRAINING`: accepts no new “fresh load” (or only under explicit rules), used for safe shutdown/cutover
* `FROZEN_WRITES`: hard stop for publishes (traffic freeze is absolute)

This state machine is read by Publish Ingress and visible in telemetry; it is written only via Ops/Admin.

---

## How this node behaves (reads vs writes)

### Reads (high frequency, internal)

Other EB subnetworks consult this node constantly:

* Publish Ingress: “may I accept this publish? how do I route it? what limits apply?”
* Fetch/Delivery: “may I serve this read? hot-only or historical? what are bounds?”
* Coordination: “how many partitions exist for this stream-version?”
* Retention/Archive: “what retention applies? is archive required/enabled?”

These reads must be fast and consistent, which is why the PolicyEpoch exists.

### Writes (rare, internal control only)

Only **Ops/Admin** is allowed to write changes to Topology & Policy:

* create a stream / create a new stream version
* change retention within env bounds
* tighten ACLs/quotas
* move stream state ACTIVE↔DRAINING↔FROZEN
* declare cutover targets

These writes are outcome-affecting, so they’re governed externally (Run/Operate + Gov), but enforced here. 

---

## Environment ladder posture (how this node changes by env without changing meaning)

What varies by environment is **policy values**, not policy semantics:

* Local/dev/prod all have the same streams and the same meaning of “traffic/control/audit,” same ACL shape (traffic still IG-only), same read-class separation (hot-only vs historical).  
* Differences are in: retention length, quota ceilings, security strictness, reliability targets, and observability depth—plugged in as policy values. 

---

## What “done” looks like for this node (designer-level)

Stream Topology & Policy is correct if:

* every EB subnetwork can make its decisions without inventing rules,
* stream-version invariants can’t drift in-place,
* traffic stream producer identity cannot deviate from IG-only,
* archive/historical read separation is enforceable,
* and every change is coherent via PolicyEpoch (no half-updated EB). 

If you’re ready, next in our illumination order is **Ops/Admin Control Surface** (because it’s the only writer to this node and it’s what makes changes safe and governed).

---

### Ops / Admin Control Surface

This is EB’s **only internal actuator**: the machinery that takes a governed operational intent (from Run/Operate) and applies it inside EB **safely, idempotently, and coherently**—without rewriting facts or changing EB semantics.  

It exists so “production reality paths” (drains, replays/backfills, retention changes, access tightening, stream-version cutovers) are **explicit, fenced, and auditable**, not ad-hoc operator folklore. 

---

## What Ops/Admin is authoritative for (inside EB)

Ops/Admin is the internal authority for:

* **Topology & policy mutation** (the *only* writer): stream create/versioning, ACLs/quotas, retention settings, archive posture as a stream-version invariant, stream state (`ACTIVE/DRAINING/FROZEN`). 
* **Operational posture controls**: throttles/backpressure, drains/freezes, consumer-group pause/drain/rebalance forcing.
* **Governed progress interventions**: checkpoint freezes and **offset resets** (replay/skip) with fencing and explicit basis.
* **Retention/archival operations**: deletion holds, retention window adjustments within env profile bounds, archive export/index health actions.
* **Ops markers + coherence**: epoch bumps and internal ops events so the rest of EB converges on the same reality.

Ops/Admin is *not* a “policy decision engine”. It executes decisions made elsewhere (Run/Operate/Gov), and makes them mechanically safe inside EB. 

---

## What Ops/Admin is forbidden to do (hard design bans)

* **Never rewrites facts**: cannot alter record bytes, offsets, or history.
* **Never changes stream invariants in-place**: partition topology, routing identity, and archive enablement are **stable per stream version**; changes happen via **new stream version + cutover**, not mutation. 
* **Never relaxes traffic writer rule**: `fp.bus.traffic.v1` producer remains **IG-only**; Ops/Admin can tighten (freeze/drain), not broaden. 
* **Never allows silent “archive fallback” for hot consumers**: historical reads are an explicitly authorized class; ops can’t turn lag into hidden time-travel. 

---

## The machinery inside Ops/Admin (the internal sub-network)

I’m pinning these internal machines as the minimal production-shaped implementation of Ops/Admin:

### 1) Command Intake & Identity Gate

* Receives ops commands from the **Run/Operate principal** (or equivalent privileged operator identity).
* Normal data-plane identities (IG producers, consumer services) cannot call this surface.

### 2) Authorization & Guardrail Enforcer

* Evaluates “is this operation permitted in this environment profile?” (local/dev/prod).
* Enforces invariant bans (no widening traffic writers; no in-place invariant mutation; no fact rewrite).  

### 3) Ops Ledger (Idempotency + Status)

* Stores `op_id → {scope, intent, status, timestamps, applied_epochs, results}`.
* Replaying the same `op_id` never applies twice; it resumes/returns the existing result.

### 4) Preflight Planner (Scope + Preconditions)

* Computes the exact scope: which stream(s), which groups, which partitions, which offset ranges.
* Validates preconditions *before* acting:

  * offset reset target is satisfiable (within hot retention for hot replay),
  * stream version exists and is in the right state,
  * retention bounds respect env profile limits,
  * historical replay requests require historical-read capability.

### 5) Fencing & Epoch Coordinator

This is the core safety machine: it prevents split-brain and half-applied changes by bumping the right epochs in the right order.

It owns three epoch/fencing dimensions:

* **PolicyEpoch**: topology/policy coherence token (stream state, ACLs, quotas, retention policy changes).
* **AssignmentEpoch / Lease fencing**: consumer-group ownership resets (pause/drain/rebalance) so stale owners are rejected.
* **CheckpointEpoch**: fenced checkpoint resets/holds so stale commits can’t overwrite an ops reset.

### 6) Actuator Set (Targeted internal controllers)

A small set of focused actuators, each touching one EB subnetwork (and nothing else):

* **Topology/Policy Writer** (the only mutator)
* **Ingress Posture Controller** (drain/freeze/throttle)
* **Read Posture Controller** (pause/throttle; hot-only vs historical enforcement posture)
* **Group Controller** (pause/drain/force rebalance/evict member)
* **Checkpoint Controller** (freeze/hold/reset)
* **Retention Controller** (retention window updates, deletion holds)
* **Archive Controller** (export pause/resume, index repair triggers)

### 7) Ops Event Marker & Telemetry Hook

* Emits an internal **OpsEvent marker** for every applied op: `{op_id, op_type, scope, epochs, result}`.
* Telemetry consumes these markers so Obs/Gov can correlate behavioural changes to explicit ops acts.  

### 8) Failure Handling Contract

* If an op cannot be fully applied, Ops/Admin records **FAILED** with a precise reason and leaves the system in a known fenced state (e.g., still paused/draining), never “half-unpaused”.
* Recovery is always: re-run the same `op_id` (idempotent) or run an explicit compensating `op_id`—never silent rollback.

---

## How Ops/Admin makes “complex ops” safe without changing EB meaning

A few examples at the *mechanics* level (still not spec-level):

### Drain a stream (safe shutdown / cutover prep)

* Bump **PolicyEpoch**, set stream state to `DRAINING` (ingress rejects/throttles explicitly), optionally pause target consumer groups, observe lag convergence via telemetry, then freeze if needed.

### Offset reset (replay/backfill within retention)

* Pause/drain group → bump **AssignmentEpoch** (fence owners) → apply **CheckpointEpoch** reset to explicit basis → resume group with new leases.
  This is what makes replays a governed, auditable operation rather than a consumer-side hack. 

### Retention change / deletion hold

* Bump **PolicyEpoch**, update retention policy (within env bounds) or apply a hold; Retention/Lifecycle obeys it without changing offsets or history semantics. 

### Stream invariant change (partition/routing/archive posture)

* Forbidden in-place. Ops/Admin creates **new stream version** + marks old version for drain/cutover. External orchestration (Run/Operate + component owners) migrates producers/consumers; EB remains semantically stable. 

---

## Environment ladder posture (deployment-angle you must keep)

* **Same Ops/Admin machinery exists everywhere** (local/dev/prod).
  What changes is:
* who can call it (security strictness),
* what bounds it enforces (retention min/max, throttles, HA expectations),
* and how loud the telemetry/approval gates are.
  Semantics never change. 

---

If you want to proceed in the illumination order we set, the next node is the **Durable Log Core** (because Ops/Admin and Topology/Policy exist largely to protect and operate that core truth: offsets and immutable append).

---

## Durable Log Core

This is the **center of truth** inside EB: it is the only internal node that can legitimately say “a record exists,” by assigning a stable **offset** inside a **partitioned, immutable log** and committing it durably. Everything else in EB either *feeds* it, *reads* it, *manages its time window*, or *operates it safely*. 

### What this node is authoritative for

* **Offsets**: stable, monotonically increasing per `(stream_version, partition_id)`.
* **Commit truth**: whether a record is durably committed (and therefore visible to readers).
* **Partition order**: the authoritative ordering is **offset order within a partition** (never global). 
* **Segment boundaries**: immutable storage ranges that can be sealed, retained, archived, and deleted without rewriting history. 

---

## The machinery inside Durable Log Core

### 1) Partition Log Engines

There is one Partition Log Engine per `(stream_version, partition_id)`. This is the unit that actually implements “append-only sequence.”

Each Partition Log Engine contains these internal machines:

#### 1.1 Append Sequencer

* Accepts an append request for *its* partition and assigns the next offset.
* Enforces the invariant: **offsets are strictly increasing** and never reused.

#### 1.2 Commit Barrier

* Enforces the platform’s core promise: **an ACK exists only after durable commit**. 
* “Durable commit” is defined by the environment’s durability policy:

  * local: persisted to local disk
  * dev/prod: persisted to a replicated quorum (HA posture)

Same semantic meaning everywhere: ACK means “this record will survive the expected failure model for that environment.” 

#### 1.3 Visibility Gate (Read Eligibility)

* Defines what records are visible to readers: **only committed offsets are fetchable**.
* Exposes two internal partition pointers:

  * **head offset** (end-of-log / latest appended)
  * **commit watermark** (highest committed offset)
* Fetch/Delivery reads only up to the commit watermark, so consumers never see half-committed facts.

#### 1.4 Segment Store

* Stores the partition log as immutable segments (append-only files/ranges).
* Handles segment roll/seal rules (by size/time), producing sealed segments that later become eligible for retention and archive.

#### 1.5 Index & Range Map

* Maintains offset → segment-position mapping so reads by offset range are fast and deterministic.
* The authoritative replay primitive remains offsets; any timestamp indexing is non-authoritative convenience only.

#### 1.6 Integrity & Recovery

* Writes per-segment integrity material (checksums/digests).
* On restart/failure, it:

  * rebuilds indexes if needed
  * ensures the visible committed log is consistent
  * never fabricates “missing” records or changes committed offsets

---

### 2) Replication & Leader Fencing

The Durable Log Core must ensure there is **exactly one active writer** (sequencer) per partition at any time in HA setups.

So it contains:

#### 2.1 Partition Leadership

* Maintains “who is the current sequencer/leader” for each partition.
* Guarantees single-writer, which is required for monotonic offsets.

#### 2.2 Replica Sync

* Ensures the durable-commit definition is satisfied (local disk vs quorum persistence).
* Drives the Commit Barrier: a record becomes committed only when the durability policy is satisfied.

This is strictly internal; EB still presents “ACK means durable” to Publish Ingress with no ambiguity. 

---

### 3) Segment Lifecycle Interface (to Retention/Archive)

Durable Log Core does **not** decide retention or archive; it exposes the facts needed to do them safely.

#### 3.1 Seal Export Surface

* Produces sealed segment descriptors:

  * `(stream_version, partition_id, offset_range)`
  * integrity material
* These descriptors are what Retention/Lifecycle hands to Archive Continuation. 

#### 3.2 Watermark Surfaces

* Exposes:

  * **hot low-watermark** (earliest offset still available in hot storage)
  * **commit watermark** and **head offset**
* These are the hard bounds that Fetch/Delivery must respect (no silent skipping). 

---

## What enters/exits this node (interfaces to other EB subnetworks)

### Inbound (from Publish Ingress)

* Append requests already have:

  * stream version resolved
  * partition id resolved
  * policy/ACL/quota checks done
* Durable Log Core’s only job is: **commit or fail** (it does not re-check policy; it enforces commit truth).

### Outbound (to Fetch/Delivery Egress)

* Offset-range fetch, returning records in strict offset order
* Bounds truth: head offset + hot low-watermark + commit watermark

### Control (from Ops/Admin + Retention/Lifecycle)

* “seal segment / roll segment” directives (lifecycle)
* “deletion eligibility” is enforced externally, but Durable Log Core provides the sealed ranges and watermark truth
* no ops action is allowed to rewrite committed facts or offsets (ever)  

### Telemetry taps

* partition head offsets
* commit lag (head vs commit watermark)
* storage pressure / segment counts
* replication/commit health

---

## Non-negotiable invariants this machinery enforces

1. **ACK implies durable commit** (no soft ACK). 
2. **Offsets are monotonic per partition** and never change after commit.
3. **Readers see only committed records** (no partial visibility).
4. **Retention and archive never rewrite history**; they only change availability windows over sealed ranges. 
5. **Invariant changes don’t happen here** (partition topology/routing/archive enablement are stream-version concerns in Topology & Policy). 

---

If you want to stay in the illumination order we set, the next node to open is **Publish Ingress** (because it’s the edge that turns “IG wants to publish” into “Durable Log Core append requests,” and it’s where quotas/backpressure and stream-state gating become real).

---

## Publish Ingress

Publish Ingress is EB’s **producer-facing edge**: the machinery that accepts publish requests (from IG for `fp.bus.traffic.v1` and from governed control-plane producers for `fp.bus.control.v1`), enforces **policy + safety**, chooses the target partition deterministically, and then hands off to the Durable Log Core and returns an ACK **only if** the Durable Log Core committed durably. 

It is the place where “EB is not a validator of meaning” stays true: it does **not** interpret payload semantics; it enforces **bus-level** rules (who can publish, limits, routing, and explicit backpressure). 

---

## What Publish Ingress is authoritative for

* **Admission to the bus infra** (not admission to the platform—IG owns that).
* **Producer identity enforcement** (traffic stream is IG-only; control stream is governed set). 
* **Quotas, record size limits, and backpressure** (explicit, never silent). 
* **Deterministic partition routing** based on the stream version’s routing identity + partition_key.
* **Request idempotency at the ingress edge** (to reduce duplicates caused by retries/timeouts, without promising “exactly once”).

---

## The machinery inside Publish Ingress

### 1) Producer Identity Gate

* Authenticates the caller identity class (IG vs control-plane principals).
* Enforces per-stream producer allowlists:

  * `fp.bus.traffic.v1`: IG-only producer identity (including ingestion workers operating under IG’s identity). 
  * `fp.bus.control.v1`: SR/Registry/DL/RunOperate allowed.
  * `fp.bus.audit.v1` (if enabled): pointer publishers only.

This is where “no side channels” becomes mechanically enforced.

---

### 2) Stream State & Policy Resolver

This machine consults **Stream Topology & Policy** and binds each request to a **specific stream version + PolicyEpoch**.

It resolves:

* stream existence and current state (`ACTIVE`, `DRAINING`, `FROZEN_WRITES`)
* max record size
* quotas and burst rules
* routing identity and partition count
* archive posture (not used for writes but fixed as an invariant of the stream version)

**Hard rule:** if the stream is `DRAINING` or `FROZEN_WRITES`, Publish Ingress rejects explicitly (retryable for draining if you want; non-retryable for frozen). No ambiguous “accept then drop.” 

---

### 3) Record Envelope Gate (bus-level, not semantic)

Publish Ingress does not “validate meaning,” but it **must** enforce bus-level constraints:

* record must be bytes (or a canonical serialization) within size limits
* required bus headers exist (at minimum: stream name, partition_key, producer id, request id)
* it does **not** validate `event_type` correctness or payload schema—IG already did canonical envelope validation at the platform boundary. 

If the record is malformed at the transport level, it is rejected.

---

### 4) Quota & Backpressure Controller

This machine ensures EB never silently loses facts under load.

It enforces:

* per-producer and per-stream rate limits (events/sec, bytes/sec)
* burst caps
* global ingress pressure limits (protecting the Durable Log Core)

It outputs only two outcomes when overloaded:

* **THROTTLE**: explicit retryable backpressure
* **REJECT**: explicit non-retryable refusal (used when safety requires it)

No “accept and drop later” is allowed. 

---

### 5) Deterministic Partition Router

This machine applies the stream version’s routing identity:

Inputs:

* `partition_key` (provided by IG/control producer)
* `partition_count`
* `routing_identity`

Output:

* `partition_id`

**Hard invariant:** same `(stream_version, routing_identity, partition_key)` always maps to the same `partition_id`. Routing is stable for the lifetime of the stream version. 

Publish Ingress does not invent routing rules; it applies the declared routing identity from Topology & Policy.

---

### 6) Append Orchestrator (handoff to Durable Log Core)

This is the commit-proxy machine.

It:

* constructs the append request: `(stream_version, partition_id, record_bytes, policy_epoch, producer_id)`
* calls the Durable Log Core append interface
* waits for one of:

  * **CommitAck** (durably committed)
  * retryable failure
  * non-retryable failure (partition not writable, leader movement beyond safe retry window, etc.)

**Critical invariant:** Publish Ingress never synthesizes ACK. It can only forward the log core’s commit result. 

---

### 7) Ingress Idempotency Cache (best-effort dedupe)

Because network timeouts cause retries, Publish Ingress includes a bounded idempotency cache keyed by `(producer_id, request_id)`.

* If a duplicate request arrives with the same key and the first attempt already produced a CommitAck, it returns the same CommitAck (same partition/offset).
* If the first attempt is unknown (ambiguous), it does **not** pretend; it treats it as a new attempt and the platform’s at-least-once posture tolerates potential duplicates.

This reduces accidental duplicates without promising “exactly once.”

---

### 8) Telemetry Hook (publish-edge signals)

Publish Ingress emits:

* publish latency (to durable commit)
* throttle/reject counts by reason
* bytes in/out
* producer identity errors
* policy epoch in force

This is what feeds Obs/Gov corridor checks around ingress health and retention pressure. 

---

## The strict contract Publish Ingress upholds (designer-locked)

* **No silent acceptance.** Every publish attempt resolves to: CommitAck / Throttle / Reject / Explicit retryable failure.
* **ACK is truth.** If an ACK is returned, the record is durably committed with stable coordinates. 
* **Traffic stream remains IG-only.** Publish Ingress enforces the producer allowlist.
* **Routing is deterministic and stable by stream version.** No routing drift. 
* **It does not validate payload meaning.** That boundary stays at IG / canonical envelope enforcement. 

---

If you want to continue in the agreed order, next to illuminate is **Fetch / Delivery Egress** (consumer-facing reads, hot vs historical read handling, and delivery batching/flow control).

---

## Fetch / Delivery Egress

Fetch/Delivery Egress is EB’s **consumer-facing edge**: the machinery that serves immutable records to consumers by **offset**, enforces **read permissions and read class** (hot-only vs historical), applies **group ownership fencing** when reading as a consumer group, and returns **DeliveredRecords** (event bytes + bus metadata like partition/offset/published_at). 

It is where the platform’s replay contract becomes mechanically true: **replay is offset-native**, ordered per partition, and bounded by hot retention unless you are an explicitly authorized historical reader.  

---

## What Fetch/Delivery Egress is authoritative for

* **Serving records by offset** (not by domain time).
* **Read-class enforcement**:

  * always-on consumer groups are **hot-only**
  * historical replay identities are allowed to read beyond hot retention via archive. 
* **Consumer-group fencing at fetch-time** (only the current owner can fetch a partition under group mode).
* **Batching/flow control** to protect EB and consumers.
* **Explicit bounds truth**: hot low-watermark and head/commit bounds; no silent truncation.

It is not authoritative for:

* commit/progress (checkpoint store is)
* admission/meaning (IG is)
* ordering beyond partition offsets (none exists)

---

## The machinery inside Fetch / Delivery Egress

### 1) Read Identity & Access Gate

* Authenticates the consumer identity (service principal).
* Consults **Topology & Policy** to enforce:

  * consumer ACLs per stream
  * permitted read class (hot-only vs historical-enabled)
  * per-consumer fetch limits (bytes/sec, batch caps)
* If not allowed: hard reject.

This is where the “hot-only vs historical” separation is enforced and where you prevent lagging hot services from silently time-traveling into archive. 

---

### 2) Read Intent Resolver

Normalizes read requests into one of two modes:

#### 2.1 Direct offset read (stateless)

* Client supplies `(stream, partition, from_offset)` and bounds (`max_records/max_bytes` or `to_offset`).
* Used mainly for tooling and historical jobs that manage their own cursors.

#### 2.2 Grouped read (stateful consumption)

* Client supplies `(stream, group_id, partition)` and asks to read starting from group position.
* Fetch must consult coordination/leases and checkpoints to determine the correct starting offset.

This resolver is where you keep “what kind of read is this?” explicit, so semantics don’t drift.

---

### 3) Group Ownership Fence (when in grouped mode)

This is the machine that prevents split-brain processing inside a consumer group.

* Validates `(group_id, partition)` ownership against **Consumer Group Coordination**:

  * current assignment epoch
  * partition lease token
* If the consumer is not current owner: reject with “not owner / rebalance in progress.”
* If owner: proceed.

This does not attempt to guarantee exactly-once; it guarantees **no concurrent owners per partition per group**, which is the correct primitive under at-least-once delivery. 

---

### 4) Cursor Resolver (start offset)

Determines where to start reading:

* If direct read: start offset is explicit (client-provided).
* If grouped read: start offset is read from **Checkpoint & Progress Truth**:

  * committed offset has fixed meaning: **exclusive-next** (“next offset to apply”). 
  * If there is no checkpoint yet, start offset is the configured “group start policy” (e.g., earliest available hot) as defined by policy/ops.

**Hard rule:** Fetch never invents progress. It resolves from checkpoint truth or explicit offsets.

---

### 5) Bounds & Availability Resolver (hot retention vs archive boundary)

This machine ensures no silent skipping.

It queries the Durable Log Core for partition bounds:

* **hot low-watermark** (earliest offset still present in hot storage)
* **head offset / commit watermark** (latest committed/visible offsets)

Then applies rules:

* If `from_offset >= hot_low_watermark`: fetch from hot log.
* If `from_offset < hot_low_watermark`:

  * if read class is hot-only: **explicit out-of-range failure**
  * if historical-enabled: **route to archive continuation** for the older range.  

If a requested range straddles the boundary, Fetch stitches results hot+archive without gaps or duplicates.

---

### 6) Hot Fetch Adapter (to Durable Log Core)

Executes the hot read:

* requests `(stream_version, partition, offset_range, max_bytes/max_records)`
* receives records in strict offset order
* receives bounds truth (head/low-watermark) for downstream lag/bounds signals

**Hard invariant:** results are ordered by increasing offset within the partition, and no “phantom gaps” are created by fetch. 

---

### 7) Archive Fetch Adapter (to Archive Continuation)

Executes historical reads (only for authorized historical read class):

* requests `(stream_version, partition, offset_range)`
* receives the exact committed record bytes for that offset range (same offsets)
* any missing range is explicit failure (no silent truncation) 

---

### 8) Batch Builder & Flow Controller

Packages records for delivery while protecting both EB and consumers:

* enforces `max_records`, `max_bytes`, and time-slice limits
* supports backpressure: if consumer can’t keep up, it gets smaller batches or throttled reads
* does not change ordering; does not drop records silently

This is where “high throughput but safe” is handled.

---

### 9) DeliveredRecord Composer

Forms the outbound units:

* **Event bytes** (the immutable canonical envelope bytes stored in the log)
* **Bus metadata**:

  * `stream`, `partition_id`, `offset`
  * `published_at_utc` (time of durable commit)
  * optional: `policy_epoch` marker for correlation/debugging
* The bus metadata is not inserted into the envelope; it’s out-of-band delivery metadata.

---

### 10) Read Telemetry Hook

Emits the golden read signals:

* fetch latency, bytes, batch sizes
* out-of-range errors (below hot low-watermark)
* hot vs archive read rates (archive reads only by historical identities)
* consumer lag estimates (using head offset vs committed offset when grouped)
* rebalance-related rejects (not-owner / epoch mismatch)

These are essential for Obs/Gov and for Run/Operate safe operations. 

---

## Non-negotiable invariants Fetch/Delivery enforces

* **Offset-addressed replay is the primitive.** No time-addressed semantics at the bus layer.
* **Hot vs historical is explicit and enforced.** Hot services cannot silently read archive. 
* **Group fencing is strict.** Stale owners cannot fetch under group mode.
* **No silent gaps/truncation.** Bounds are explicit; if not satisfiable, it fails explicitly.
* **Does not commit progress.** Fetch serves; checkpoint truth is elsewhere.

---

If we continue in our chosen order, the next node to illuminate is **Consumer Group Coordination** (membership, epochs/leases, assignment, and rebalance machinery), since Fetch depends on it for fencing.

---

## Consumer Group Coordination

Consumer Group Coordination is EB’s **ownership and membership authority** for grouped consumption. Its job is to ensure that, for any `(group_id, stream_version, partition_id)`, there is **at most one active consumer** considered the owner at a time, and that ownership changes are **fenced** so stale consumers cannot continue processing after a rebalance. 

This node does *not* promise exactly-once; it promises **no concurrent ownership** and **clean rebalances**, which is the correct primitive given the platform’s at-least-once delivery posture. 

---

## What Consumer Group Coordination is authoritative for

* **Group membership** (who is in the group, who is alive).
* **Partition assignment** (which member owns which partitions).
* **AssignmentEpoch** (monotonic generation token for the group).
* **Lease tokens** (per-partition fencing tokens proving current ownership).
* **Rebalance rules** (when to reshuffle, how to fence stale owners).
* **Operational group state** (`ACTIVE` / `PAUSED` / `DRAINING`) under Ops/Admin control.

It is not authoritative for:

* offsets/progress (Checkpoint & Progress Truth is)
* fetching records (Fetch/Delivery is)
* stream topology (Topology & Policy is)

---

## The machinery inside Consumer Group Coordination

### 1) Group Registry (persistent group metadata)

Stores authoritative group configuration:

* `group_id`
* allowed stream(s)/stream versions
* assignment strategy identity
* max members / expected member identity class
* group state (`ACTIVE/PAUSED/DRAINING`) and its controlling PolicyEpoch marker (so state changes are coherent with ops) 

This registry makes group behaviour stable and prevents ad-hoc “new groups with accidental semantics” from forming in prod.

---

### 2) Membership Manager (join/leave/heartbeat)

This is the liveness machine.

It maintains:

* member sessions: `member_id`, identity principal, last heartbeat, capabilities (what partitions it can handle)
* session expiry rules: if heartbeats stop, the member is considered dead

Hard rule: a dead member’s ownership is revoked via rebalance fencing (epoch bump).

---

### 3) Assignment Planner (partition→member mapping)

This machine decides who owns what, given:

* partition topology (from Topology & Policy)
* active membership set (from Membership Manager)
* assignment strategy identity (e.g., “balanced sticky” semantics—identity matters, not the exact algorithm)

Outputs:

* a deterministic `assignment_map: partition_id → member_id`

Hard design rule:

* assignment is a pure function of `(group_id, AssignmentEpoch, members, partition topology, strategy identity)` so it can be reasoned about and debugged.

---

### 4) Epoch & Lease Fencer (the split-brain killer)

This is the most important coordination machine.

It maintains:

* **AssignmentEpoch** (monotonic, increments on every rebalance or ops pause/drain event)
* per-partition **lease_token** (derived from epoch + partition + member identity)

Fencing rules:

* When AssignmentEpoch increments, **all prior leases become invalid**.
* Fetch/Delivery requires the current `(AssignmentEpoch, lease_token)` for grouped reads; stale tokens are rejected.
* Checkpoint commits are also fenced: only current owners (current epoch/lease) can commit offsets.

This is how you prevent two members from simultaneously processing the same partition after rebalances.

---

### 5) Lease Issuer & Renewal

After an assignment is planned, Coordination issues per-partition leases to the owning members and renews them as long as the member remains alive.

Hard rule:

* Lease renewal is conditional on active membership; no heartbeat → no renewal → eventual revoke via rebalance.

---

### 6) Rebalance Orchestrator

Triggers and manages rebalances:

* triggers: member join, member leave, member death, partition topology change (stream version cutover), ops-driven pause/drain
* actions:

  1. bump AssignmentEpoch
  2. compute new assignment
  3. issue new leases
  4. inform Fetch/Delivery of the new epoch (implicitly via lease validation)

During rebalance:

* grouped fetch requests receive explicit “rebalance in progress / not owner” signals until the new leases are active.

---

### 7) Ops/Admin Group State Controller (ingested control)

This is the join where Ops/Admin influences coordination without creating ambiguity.

Ops/Admin can set:

* `PAUSED`: no leases issued/renewed; grouped reads are effectively blocked (safe maintenance state)
* `DRAINING`: leases continue but only to reach a declared target watermark; new work acquisition can be restricted
* `ACTIVE`: normal behaviour

Any state change bumps AssignmentEpoch (fences stale owners immediately). 

---

### 8) Coordination Event Channel (internal signaling)

Coordination emits internal signals (not “facts”, just coordination state):

* epoch changed
* rebalance started/completed
* member evicted
* partitions reassigned

Fetch/Delivery and Telemetry consume these signals:

* Fetch uses them to enforce fencing
* Telemetry uses them to compute churn and rebalance durations

---

## The hard invariants this node guarantees to the rest of EB

1. **Single active owner per partition per group** (at any instant).
2. **Epoch fencing is absolute**: after a rebalance, stale owners cannot fetch or commit.
3. **Ops control is clean**: pause/drain states are enforced via epoch bumping, never via “best effort.” 
4. **Coordination does not own progress**: it fences commits but does not define offset semantics; checkpoint semantics remain exclusive-next in the progress node. 

---

Next in our agreed illumination order is **Checkpoint & Progress Truth**, because it’s the other half of correctness under at-least-once: coordination prevents split-brain; checkpoints make applied-watermark truth real.

---

## Checkpoint & Progress Truth

This node is EB’s **authoritative truth for consumer progress**. It defines and persists, for every `(consumer_group, stream_version, partition_id)`, the committed offset with one fixed meaning:

**Committed offset = the exclusive-next offset (“the next offset the consumer will read/apply”).** 

Everything downstream in your platform that talks about “watermarks”, “applied basis”, `graph_version`, or `input_basis` ultimately depends on this being real, monotonic, fenced, and governed. 

---

## What this node is authoritative for

* **Checkpoint value** per `(group, stream_version, partition)` with exclusive-next semantics.
* **Monotonic progress** in normal operation (forward only).
* **Commit authority fencing** (only current partition owner can commit).
* **Ops-governed resets** (rewind/fast-forward/freeze) — consumers cannot do these ad-hoc. 
* **Lag truth** primitives (enough to compute lag versus head offsets).

It is not authoritative for:

* membership/ownership (Coordination is)
* reads/fetching (Fetch/Delivery is)
* retention bounds (Log Core + Lifecycle are)
* meaning of events/payloads (outside EB)

---

## The machinery inside Checkpoint & Progress Truth

### 1) Checkpoint Record Store

This is the durable map:

Key:

* `(group_id, stream_version, partition_id)`

Value:

* `committed_offset_exclusive_next`
* `commit_time_utc`
* `commit_epoch_fence` (the assignment epoch/lease identity at the time of commit)
* `committing_member_id` (for audit/debug)
* optional `commit_reason` (normal commit vs ops-reset marker)

**Hard rule:** this store is the only place inside EB where “group progress” is persisted.

---

### 2) Commit Validator & Fence Gate

This machine makes commits safe under rebalances.

Inputs:

* commit request containing:

  * `(group, stream_version, partition)`
  * proposed `offset_exclusive_next`
  * `(assignment_epoch, lease_token, member_id)` fencing identity from Consumer Group Coordination

Validation rules:

1. **Ownership fence:** commit is accepted only if the commit’s fencing identity is current (not stale).
2. **Range sanity:** offset must be within the partition’s addressable universe (it can be equal to head+1 as “caught up”, but never negative, never nonsensical).
3. **Monotonicity (normal mode):** proposed offset must be `>=` current committed offset.

If the fence is stale: reject.
If monotonicity is violated: reject (unless an ops-reset is in effect, see below).

This gate is what prevents “stale consumer commits after rebalance” from corrupting progress.

---

### 3) Monotonic Progress Engine

This is the mechanism that enforces “forward only” in normal flow:

* It treats the checkpoint as a monotonic cursor.
* It will not accept backwards movement from normal consumer commits.

This is critical because watermarks are derived from applied progress; if checkpoints can move backwards casually, provenance becomes meaningless. 

---

### 4) Ops Reset Controller (governed progress interventions)

This machine is the *only* legitimate way to move progress backwards (replay) or to force skip ahead.

It is invoked only by **Ops/Admin Control Surface**. 

Supported ops actions (pinned set):

* **RESET_REWIND**: set committed offset to a lower explicit offset basis (replay).
* **RESET_FAST_FORWARD**: set committed offset to a higher explicit offset basis (skip) — rare and high-risk.
* **FREEZE_COMMITS**: temporarily reject normal commits for a scope (investigation/controlled maintenance).
* **UNFREEZE_COMMITS**: resume normal commit acceptance.
* **SNAPSHOT_PROGRESS**: record a watermark vector snapshot for audit/support.

Safety mechanisms:

* Every reset has an `op_id` (idempotent) and produces an ops marker in the record store.
* A reset is **fenced** by a reset epoch token so that stale consumers cannot overwrite it.
* Resets are applied only after Coordination has fenced ownership (group pause/drain + epoch bump). This prevents “consumer keeps running while ops rewinds.”

---

### 5) Progress View & Lag Basis Exporter

This machine provides read-side access for:

* Fetch/Delivery (to resolve “resume from group position”)
* Telemetry (to compute lag)
* Run/Operate (to observe whether drains/catch-up targets are met)

It serves:

* `committed_offset_exclusive_next`
* commit metadata (epoch/commit time)
* optionally derived “lag basis” values when paired with head offsets from the Log Core

Important: it reports truth; it does not invent or smooth.

---

### 6) Consistency & Compaction Engine (internal housekeeping)

This ensures the checkpoint store remains efficient and consistent:

* compacts commit histories (if you store history) into a current snapshot + optional bounded history
* ensures idempotent ops actions do not duplicate effects

This is purely operational; it never changes checkpoint meaning.

---

## How this node interacts with the rest of EB (mechanically)

* **Coordination → Checkpoint** provides fencing identities (epoch/leases) used by Commit Validator.
* **Fetch/Delivery → Checkpoint** reads committed offsets to resolve starting cursors.
* **Ops/Admin → Checkpoint** performs controlled resets/freezes with op_id and fencing.
* **Telemetry** taps commit rates, rejection reasons, lag, and reset events (high-signal).

---

## Non-negotiable invariants (designer-locked)

1. **Exclusive-next meaning is fixed** for committed offsets. 
2. **Normal commits are forward-only**; backward movement is ops-only. 
3. **Commits are fenced by ownership** (stale owners cannot commit).
4. **Ops resets are fenced and idempotent** (op_id) and never occur while stale consumers can still commit. 
5. **Checkpoints represent applied truth** (consumers must commit after durable apply; EB enforces the mechanics, consumers enforce the discipline). 

---

Next in the illumination order is **Retention & Segment Lifecycle**, because now we have the write truth (log core), the read truth (fetch), and the progress truth (checkpoints); retention is the “time window enforcement” that must not break any of those meanings.

---

## Retention & Segment Lifecycle

This node is EB’s **time-window enforcement machinery** for the hot log. It turns “retention policy for a stream version” into concrete actions over immutable log segments: **seal → age → expire → delete**, while guaranteeing that nothing ever rewrites history, offsets remain meaningful, and (when archive continuation is enabled) hot deletion never breaks continuity.  

Retention/Lifecycle does **not** care about event meaning, schema, or consumer progress as a decision input. It enforces the stream’s retention contract and publishes the bounds truth the rest of EB must obey. 

---

## What this node is authoritative for

* **Segment lifecycle state**: open vs sealed segments per `(stream_version, partition)`.
* **Hot low-watermark** evolution (earliest offset still available in hot storage).
* **Deletion eligibility** for sealed segments under retention policy.
* **Deletion holds** (ops-imposed pauses).
* **Archive gating** when archive is enabled: “delete only after archive ACK”.

It is not authoritative for:

* offsets/commit truth (Log Core is)
* reads (Fetch is)
* consumer lag/progress (Checkpoint is)
* archive storage itself (Archive Continuation is)
* policy values (Topology & Policy is)

---

## The machinery inside Retention & Segment Lifecycle

### 1) Policy Binder

Reads from **Stream Topology & Policy** for each stream version:

* retention window policy (time horizon)
* segment sealing rules (size/time caps)
* archive enabled/disabled flag (invariant)
* any per-stream deletion safety constraints
* current stream state (ACTIVE/DRAINING/FROZEN) insofar as it affects sealing cadence

This binder pins every lifecycle action to a specific **PolicyEpoch**, so deletions never happen “under a different policy than we think.” 

---

### 2) Segment Rollover & Seal Controller

Coordinates with the Durable Log Core to keep segments well-formed:

* monitors open segments for rollover triggers:

  * max size reached
  * max time window reached
  * ops-induced seal request (e.g., before drain/cutover)
* issues “roll/seal” directives to the Log Core.

**Hard rule:** only sealed segments are eligible for retention deletion or archival export. Open segments are never deleted or exported. 

---

### 3) Segment Catalog (sealed-range inventory)

Maintains a catalog of sealed segments with:

* `(stream_version, partition_id)`
* `offset_range` (start/end)
* `sealed_at_utc`
* size/age metrics
* integrity metadata (segment digest)
* **export status** (if archive enabled): `NOT_EXPORTED / EXPORTED_ACKED`

This catalog is what makes retention decisions deterministic and auditable inside EB.

---

### 4) Retention Eligibility Evaluator

Determines when a sealed segment becomes eligible for deletion under the retention window.

Inputs:

* sealed_at timestamp + segment age
* stream retention window policy
* deletion holds (ops)
* archive gating status (if enabled)

Outputs:

* “eligible now” vs “not yet”
* proposed low-watermark advance points

**Non-negotiable invariant:** retention is policy-driven, not consumer-progress-driven. Consumer lag is surfaced as a signal; it does not change deletion eligibility. 

---

### 5) Deletion Hold Gate (ops safety)

Implements ops-imposed holds that pause deletion without changing meaning:

* holds can be scoped per stream-version or global
* used for incident response, investigations, or while archive is unhealthy

While held:

* segments continue to seal
* low-watermark does not advance
* deletion does not occur

This is how you avoid forced history loss under operational distress.

---

### 6) Archive Export Gate (when archive is enabled)

This is the continuity protection mechanism:

* when archive is enabled for a stream version, every sealed segment is sent to **Archive Continuation** for persistence+indexing (P5 export side).
* the segment is marked `EXPORTED_ACKED` only after archive returns a persistence+index ACK.

**Hard rule:** hot deletion is allowed only for sealed segments that have been `EXPORTED_ACKED` when archive is enabled. 

This is the internal enforcement of “archive is continuation, not best-effort.”

---

### 7) Deletion Executor

Performs the actual hot storage deletion:

* deletes only sealed, eligible segments
* advances the stream-partition **hot low-watermark** accordingly
* never deletes partially, never leaves “holes” unaccounted for
* never changes offsets; deletion only changes availability

It coordinates with the Durable Log Core’s segment store to remove the segment bytes and update any hot indexes that reference them.

---

### 8) Low-Watermark Publisher (bounds truth)

Publishes the authoritative **hot low-watermark** per `(stream_version, partition)`:

* Fetch/Delivery uses it to decide:

  * hot read possible
  * hot read out-of-range (explicit failure)
  * historical read routing (if authorized and archive enabled)
* Telemetry uses it to compute retention pressure and detect consumers drifting behind.

**Hard rule:** if a consumer asks for `from_offset < hot_low_watermark`, that fact must be visible and explicit; EB does not silently skip. 

---

### 9) Retention Pressure & Health Reporter (signals producer)

Emits signals (via Telemetry taps) that describe:

* sealed segment backlog
* deletion backlog
* time-to-expiry for current hot window
* holds active
* archive export backlog (if enabled)

Obs/Gov and Run/Operate use these signals for safe operations (throttles/drains/retention tuning), but Retention/Lifecycle itself does not “decide” those actions.  

---

## Non-negotiable invariants (designer-locked)

1. **Retention acts only on sealed immutable segments.** 
2. **Deletion advances low-watermark; it never rewrites offsets or committed facts.**
3. **Retention policy is not influenced by consumer lag.** Lag is observed and acted on via ops/governance, not by changing deletion behaviour. 
4. **If archive is enabled, deletion is gated on archive persistence+index ACK.** 
5. **Deletion holds are explicit and governable** (ops-imposed). 

---

Next in our illumination order is **Archive Continuation** (the cold window machinery that preserves the admitted fact stream beyond hot retention with offset-native indexing and historical read-through).

---

## Archive Continuation

Archive Continuation is EB’s **cold-window machinery**: it preserves the admitted fact stream beyond hot retention by storing **sealed immutable offset ranges** in archive storage and maintaining an **offset-native index** so historical replay remains expressed in the same EB coordinates: `(stream_version, partition_id, offset_range)`. 

It is what makes this platform promise true in production: **“Archive is the continuation of EB, not a different stream.”** 

---

## What Archive Continuation is authoritative for

* **Archive persistence** of sealed ranges (segments) from the hot log.
* **Archive index truth**: mapping from `(stream_version, partition, offset_range)` to archived segment locators.
* **Read-through historical delivery** for authorized historical read identities.
* **Completeness status** for a stream/partition over a window (i.e., whether archival coverage is continuous for a range).

It is not authoritative for:

* offsets/commit truth (Durable Log Core is)
* retention policy and deletion eligibility (Retention/Lifecycle is)
* authorization policy values (Topology & Policy is)
* consumer group progress (Checkpoint is)
* hot fetch batching (Fetch/Delivery is)

---

## The machinery inside Archive Continuation

### 1) Archive Intake Receiver (sealed range ingress)

Receives sealed immutable ranges from Retention/Lifecycle (export side of P5):

Input unit is a **SealedRangeDescriptor**:

* `(stream_version, partition_id, offset_range)`
* integrity material (segment digest)
* sealed_at time
* policy epoch marker (for correlation)

**Hard rule:** Archive Continuation accepts only **sealed** ranges. It never accepts open/unsealed data.

---

### 2) Archive Writer (persistence engine)

Persists each sealed range to archive storage (object storage or equivalent), preserving:

* record bytes **exactly as committed**
* offset ordering within the range
* segment boundaries or an equivalent stable container format

It produces an **ArchiveLocator** (a stable ref to the archived object(s)).

**Hard invariant:** archive persistence does not re-encode in a way that changes record bytes or offsets. If the storage format requires framing, the content must be byte-for-byte recoverable for each record.

---

### 3) Offset-Native Index Builder

This is the core “continuation” mechanism.

For every persisted sealed range, it writes an index entry keyed by:

* `stream_version`
* `partition_id`
* `offset_range` (start, end)

Value:

* archive locator
* integrity material (digest, size)
* optional paging hints (sub-range chunking for efficient reads)

**Hard rule:** the index is offset-native. Archive is queryable by the same primitive as EB: offset ranges.

---

### 4) Archive ACK Generator (export confirmation)

After a sealed range is both:

1. persisted, and
2. indexed,

Archive Continuation emits an **ExportAck** back to Retention/Lifecycle:

Ack includes:

* `(stream_version, partition, offset_range)`
* archive locator
* “indexed = true”
* integrity confirmation

This ACK is the gating token Retention/Lifecycle uses to permit hot deletion when archive is enabled. 

---

### 5) Historical Read Gate (capability boundary)

Archive Continuation does not decide who “should” read history, but it **enforces** the explicit read class boundary:

* Only identities with **historical-read capability** can trigger archive reads.
* Always-on hot consumer groups are **not** allowed to silently fall back to archive.

This is enforced through Topology & Policy and Fetch/Delivery, but Archive Continuation has its own defensive gate: if it receives an archive read request without historical-read capability, it rejects it. 

---

### 6) Archive Read Service (read-through by offset range)

Serves historical reads by the same primitive:

Input:

* `(stream_version, partition_id, offset_range)` + bounds

Output:

* records in strict increasing offset order
* no gaps introduced by the archive read layer

If the request spans multiple archived objects, it stitches them internally but still returns a coherent ordered stream for that range.

**Hard invariant:** no silent truncation. If any requested subrange is missing from the index, the read fails explicitly for that range.

---

### 7) Stitching Support for Boundary Reads

This is a cooperation point with Fetch/Delivery:

* When a requested range crosses the hot low-watermark boundary, Fetch/Delivery can fetch:

  * older part from archive
  * newer part from hot log
* Archive Continuation guarantees its portion is complete and ordered for the archived subrange; Fetch guarantees the composite result has no gaps/duplication.

Archive Continuation supports “range exactness” so stitching can be correct.

---

### 8) Completeness & Continuity Verifier

This machine maintains a measurable truth about archival coverage:

* For each `(stream_version, partition)` it tracks which offset ranges have been archived.
* It detects gaps (missing ranges) and reports them as health faults.
* It reports “archive lag” (how far behind hot sealed segments the archive is).

This is crucial because the platform depends on archive for long-horizon replay/training/investigations in prod. 

---

### 9) Archive Health & Backlog Reporter (signals producer)

Emits signals:

* export backlog (sealed-but-not-archived ranges)
* export latency
* index miss rate
* archive read latency
* continuity faults (gaps)
* storage pressure/cost indicators

Obs/Gov and Run/Operate use these to decide throttles/holds/retention tuning. Archive Continuation does not autonomously change platform behaviour.  

---

## Non-negotiable invariants (designer-locked)

1. **Archive stores sealed immutable ranges only.**
2. **Archive is offset-native:** indexed by `(stream_version, partition, offset_range)`. 
3. **Record bytes and offsets are preserved**; archive does not change event identity or ordering. 
4. **Deletion gating:** if archive is enabled, Retention/Lifecycle can delete hot segments only after archive persistence+index ACK. 
5. **Historical reads are explicitly authorized**; no silent fallback for hot consumers. 
6. **No silent truncation:** missing ranges are explicit failures, and continuity gaps are first-class health faults.

---

Next in our illumination order is **Signals & Telemetry** (the final node), which taps all these internals and exposes the operational truth needed for corridor checks, degrade inputs, and safe ops—without becoming a decision engine itself.

---

## Signals & Telemetry

Signals & Telemetry is EB’s **observability truth emitter**. It is a passive tap network that turns internal state and events into **measurable signals** for Obs/Gov and Run/Operate: throughput, latency, lag, retention pressure, archive health, coordination churn, and explicit ops-change markers. 

It is deliberately *not* a policy engine:

* it does not decide degrade,
* it does not change EB behaviour,
* it does not “heal” anything.
  It only makes EB’s reality visible and attributable to epochs and operations.  

---

## What Signals & Telemetry is authoritative for

* **Signal semantics**: what each metric/event means (so env ladder can scale it without changing meaning). 
* **Correlation keys**: how signals are keyed so you can trace state:

  * `stream_id`, `stream_version`, `partition_id`
  * `group_id`, `member_id`
  * `PolicyEpoch`, `AssignmentEpoch`, `CheckpointEpoch`
  * `op_id` for ops actions
* **Operational truth**: measured lag/backlog/pressure is not a guess; it’s derived from authoritative counters (head offsets, checkpoints, low-watermarks). 

It is not authoritative for:

* decisions/actions (DL/RunOperate)
* facts/offsets (Log Core)
* progress (Checkpoint store)

---

## The machinery inside Signals & Telemetry

### 1) Tap Adapters (one per EB subnetwork)

Each adapter subscribes to the internal event surfaces and state queries of its target node:

* Publish Ingress tap
* Durable Log Core tap
* Fetch/Delivery tap
* Consumer Coordination tap
* Checkpoint/Progress tap
* Retention/Lifecycle tap
* Archive Continuation tap
* Ops/Admin tap
* Topology/Policy tap (for PolicyEpoch changes)

These taps are read-only and cannot influence behaviour.

---

### 2) Metric Normalizer (golden-signal definitions)

This machine standardizes raw taps into a fixed set of EB “golden signals” with stable meanings.

#### Ingress golden signals (Publish)

* publish request rate / ack rate
* publish latency to durable ACK
* throttle rate (explicit backpressure)
* reject rate by reason (ACL, size, stream frozen, etc.)
* bytes/sec in

#### Log core golden signals (Durability)

* head offset per `(stream_version, partition)`
* commit watermark health (head vs committed visibility)
* storage pressure (segments/bytes)
* commit/replication health

#### Egress golden signals (Fetch)

* fetch latency and throughput
* out-of-range (below hot low-watermark) failures
* hot reads vs archive reads (archive reads only for historical class)
* bytes/sec out

#### Coordination golden signals (Churn)

* group membership count
* rebalance frequency and duration
* lease fencing rejects (“not owner”)
* partition assignment distribution

#### Progress golden signals (Lag)

* commit rate/latency
* commit rejects (stale epoch/lease)
* lag per `(group, stream_version, partition)` computed from:

  * `head_offset` (log core truth) minus
  * `committed_offset_exclusive_next` (checkpoint truth)
* offset reset events (ops marker)

#### Retention golden signals (Pressure)

* hot low-watermark per partition
* time-to-expiry (how close hot window is to losing older offsets)
* deletion backlog
* deletion holds active

#### Archive golden signals (Continuity)

* export backlog (sealed-but-not-archived ranges)
* export latency
* index miss rate / continuity gaps
* archive read latency
* archive lag (how far behind sealed segments the archive is)

All of these are keyed by the correlation keys above.

---

### 3) Event Marker Stream (ops-change attribution)

This machine emits high-signal, low-volume **markers** that allow external systems to correlate behavioural shifts with explicit operations:

* `PolicyEpochChanged`
* `StreamStateChanged` (ACTIVE/DRAINING/FROZEN)
* `GroupStateChanged` (ACTIVE/PAUSED/DRAINING)
* `AssignmentEpochBumped` (rebalance)
* `CheckpointResetApplied` (op_id + scope + new basis)
* `RetentionPolicyChanged` (within env bounds)
* `DeletionHoldSet/Cleared`
* `ArchiveExportPaused/Resumed`
* `StreamVersionCutoverInitiated/Completed`

These markers are what makes “prod never relies on human memory” true in practice. 

---

### 4) Lag & Corridor Evaluator (signal shaping, not decisioning)

This machine computes derived indicators that are *inputs* to corridor checks but does not make decisions:

* “hot-path risk” indicators:

  * consumer lag crossing thresholds
  * rebalance storms
  * retention pressure rising
  * archive backlog exploding
  * publish throttle saturation

It outputs these as derived metrics/alerts. The actual decision to degrade or operate differently lives outside EB (DL/RunOperate). 

---

### 5) Export Router (environment ladder output posture)

This machine adapts **where** signals go, not **what they mean**:

* Local: console/logging + lightweight metrics endpoint
* Dev: centralized metrics + dashboards
* Prod: full telemetry stack + alerts + SLO reporting 

The key pin: meanings and keys are identical across envs; only sink/retention/sampling changes.

---

### 6) Telemetry Integrity Guard

Prevents telemetry from becoming a source of lies:

* rejects/flags impossible states (e.g., negative lag, head offset regressing)
* ensures epoch markers are monotonic
* ensures lag is computed from authoritative truths (head offsets + committed offsets), not from sampling guesswork

This keeps “observability” from undermining determinism.

---

## How Signals & Telemetry plugs into the larger platform network

* Obs/Gov consumes EB signals to perform corridor checks and detect drift. 
* Run/Operate uses signals + ops markers to safely orchestrate drains, backfills, replays, retention adjustments, and cutovers. 
* DL can use the health signals as inputs to degrade posture, but DL remains the authority that decides and publishes degrade constraints. 

---

## Non-negotiable invariants (designer-locked)

1. Telemetry is **read-only**; it cannot change EB behaviour.
2. Signal meanings are **stable across environments**; only emission/sampling changes. 
3. Lag/watermark/retention pressure are derived from authoritative counters (offsets, checkpoints, low-watermarks). 
4. Ops-change markers exist and are keyed by epochs/op_id, so behaviour is attributable. 

---

