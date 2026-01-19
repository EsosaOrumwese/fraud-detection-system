# Identity & Entity Graph Design Authority

This file is a rough collection of design or brainstorm notes for the Identity and Entity Graph. It views the whole platform as a network and expands open the identity and entity graph's position in this network and illuminates it.

---

Alright — we’ll treat **IEG’s inner network as a sealed black box**, and fully define **its role, obligations, and handshakes** within the pinned platform network. Everything below is **design-authoritative for this brainstorm** and must not violate the platform pins (truth-ownership, join surfaces, watermarks, degrade, no-PASS/no-read, etc.).

---

## 1) IEG’s job in the larger network

IEG is the **first “context materializer”** in the hot path after admitted facts hit the bus:

**EB admitted facts → IEG projection + graph_version → (queried by) OFP / DF → decisions + provenance.**

### The single sentence definition

IEG provides **queryable, run/world-scoped identity + relationship context** from admitted events, and it returns a **version marker (`graph_version`)** so downstream can record *exactly what context was used*.

---

## 2) Authority boundary (what IEG is allowed to “be true about”)

This is non-negotiable because it prevents drift:

### IEG is authoritative for

* **Its own projection artifacts**: entity/edge/indices state **and** `graph_version` (as the projection’s “applied basis” token).

### IEG is NOT authoritative for

* **World truth** (engine outputs remain truth via SR join surface + PASS evidence; admitted events remain truth via IG/EB).
* **Admission/quarantine outcomes** (IG is the trust boundary; EB is the durable log; IEG cannot “quarantine” an already-admitted event).
* **Feature computation** (OFP owns feature vectors/snapshots).
* **Decisioning** (DF owns decisions; DL owns degrade posture).

That gives you the clean truth map: **IEG is a projection plane, not a second truth source**.

---

## 3) IEG as a black box (what it consumes, what it produces)

### 3.1 Inputs (what crosses into IEG)

**Primary input is EB admitted events** on the traffic topic (`fp.bus.traffic.v1`), delivered at-least-once, ordered only within partition, with stable offsets.

**Hard dependency from the platform:** IEG’s versioning is tied to **EB offsets**; watermarks are the universal progress token.

#### What IEG expects to be present on *graph-mutating* events

IEG is “envelope-driven” by design: it must be able to update without business payload semantics.

So for an event to *mutate* the graph, it must carry:

* **ContextPins** (`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`) — because IEG is run/world-scoped.
* **`event_id`** (idempotency anchor).
* **Domain time**: **`ts_utc`** (this is the platform’s domain event time; do not collapse it with ingest/apply time).
* **`event_type`** (routing key to choose the update semantics).
* **`observed_identifiers[]`** (identity hints required for envelope-driven updates).

**Important pin:** your current canonical envelope schema does **not** include `observed_identifiers` and uses `additionalProperties: false`, so the platform must evolve the envelope to carry this field (or it can’t honestly claim “envelope-driven” IEG updates).

### 3.2 Outputs (what crosses out of IEG)

IEG produces a **query surface** used by OFP/DF to retrieve:

* identity resolution (observed identifiers → canonical entity refs),
* entity profiles,
* neighbor context.

Every successful response must include:

* **ContextPins**
* **`graph_version`** (so callers can record “context used”).

IEG does **not** emit business traffic back onto EB in v0; it’s a derived projection. Optional “pointer”/ops emissions may exist, but are not required to make the loop work.

---

## 4) The handshakes (IEG’s joins with other components)

### J-IEG-1: EB → IEG (projection feed handshake)

**Purpose:** turn admitted observations into a coherent, replay-safe projection.

**What EB provides (pinned):**

* (stream, partition, offset) is the only universally meaningful position; at-least-once delivery is normal.
* consumer checkpoints use the **exclusive-next** meaning (“next offset to read/apply”).

**IEG’s obligations at this join:**

1. **Event classification (deterministic)**

* For each admitted event: deterministically classify as:

  * **GRAPH_MUTATING** (eligible to affect the projection),
  * **GRAPH_IRRELEVANT** (no-op by design),
  * **GRAPH_UNUSABLE** (should have mutated but cannot be applied due to missing required identity hints / malformed fields).

2. **Idempotency and duplicates**

* EB duplicates are normal; IEG must be stable under replay.
* Design rule: the *logical* update must be effectively-once even if delivery is not.

3. **Out-of-order safety**

* Because delivery can be out-of-order, IEG must not corrupt “first seen / last seen” style history when applying late/early events. This is why domain time (`ts_utc`) is the update time basis, not apply time.

4. **Watermark / graph_version advancement**

* IEG advances its applied checkpoint for a partition once the event has been deterministically *processed* (applied or intentionally ignored).
* `graph_version` is derived from the **per-partition next_offset_to_apply map** (+ stream identity) and is monotonic.
* Backfills don’t “time travel”; they produce new derived states under explicit replay bases.

5. **Failure posture at the feed boundary**

* If an event is GRAPH_UNUSABLE, IEG must:

  * **not mutate** projection state from it,
  * **record an explicit apply failure** tied to the EB position,
  * and surface it to ops signals (metrics/logs; optional pointer events).
* IEG does **not** reclassify the primary event as “quarantined” (IG owns that truth).

This keeps the boundary honest: **EB remains the fact log; IEG remains a fallible but deterministic projector**.

---

### J-IEG-2: IEG → OFP (context for feature compilation)

**Purpose:** OFP is the context compiler; when it needs entity context, it consults IEG and stamps the result into snapshot provenance.

**Caller posture (OFP) is pinned:**

* feature snapshots must include provenance: ContextPins, `feature_snapshot_hash`, `input_basis` watermark vector, and **`graph_version` if IEG was consulted**.

**IEG’s obligation at this join:**

* Always return **graph_version** alongside context so OFP can include it and cover it in deterministic hashing.
* Never inject hidden “now”; if the caller wants “as-of”, it must be explicit at the OFP layer (that’s where time discipline is pinned).

**Key design realism:** this join is **latency-sensitive** (hot path). Therefore:

* IEG’s query surface must be safe to call synchronously,
* and its failure mode must be explicit so OFP can degrade or mark features unavailable (not fabricate).

---

### J-IEG-3: IEG → DF (direct context use at decision time)

DF is allowed to use IEG either:

* **indirectly** via OFP snapshots, or
* **directly** (especially if DF needs identity context independent of feature compilation).

**Pinned DF provenance obligation:** DF must record graph_version used (if consulted) in decision provenance, which flows into audit.

**IEG’s obligation at this join:**

* deterministic, joinable responses (pins + graph_version),
* explicit failure responses (no invented context).

---

### J-IEG-4: IEG ↔ Observability / Governance / Degrade Ladder

This is how we keep the system safe when IEG is lagging or unhealthy.

**Pinned global law:** Degrade is explicit and enforced; DF must obey the capabilities mask; audit must record it.

So IEG must surface **operational truth** that can drive degrade decisions:

* consumer lag / current applied watermarks,
* apply failure rates (GRAPH_UNUSABLE),
* query error rates / latency.

**What this enables (design-wise):**

* DL can disable “use IEG context” capability if IEG is too far behind or producing too many apply failures.
* DF then behaves as if that tool doesn’t exist (hard constraint), and records that posture.

This is the correct place to handle “IEG isn’t trustworthy right now” — not by IEG silently fabricating, and not by DF pretending it has context.

---

### J-IEG-5: Run/Operate → IEG (rebuild/backfill)

IEG’s store is **derived/rebuildable**, and backfill is an explicit governed operation.

**Pinned rules:**

* backfills never edit primary truth (EB admitted events don’t change);
* rebuilds declare their **replay basis** explicitly (offset ranges/checkpoints);
* watermarks remain monotonic; tokens don’t “lie.”

So the outer expectation is:

* IEG can be wiped and rebuilt from EB retention or archive (archive is just EB’s long window, not a second truth), and after rebuild its `graph_version` truthfully reflects the applied basis.

---

## 5) The two “outer pins” that must be settled early (so inner design doesn’t drift)

### PIN-IEG-TIME-01: event time naming

IEG’s domain event time is **envelope `ts_utc`** (RFC3339 micros). Any “event_time” wording elsewhere is a naming alias only; apply/ingest time must never overwrite domain time.

### PIN-IEG-IDHINTS-01: identity hints must exist at the bus boundary

Envelope-driven IEG updates require `observed_identifiers[]`. Because the current canonical envelope schema doesn’t support it, the platform must evolve the envelope (or the platform can’t uphold the “payload-blind” IEG promise).

---

Yes — there are a handful of **IEG “foundation pins”** that are worth locking **before** we walk join-by-join, because they determine what *the joins even mean* (and prevent hidden assumptions).

Below are the pins I’d lock now, with my v0 stance for each.

---

## PIN-IEG-01 — Scope and isolation

**Pin:** IEG is **run/world-scoped**, isolated strictly by **ContextPins** `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`. No cross-run/global graph in v0.

Why now: every join handshake (EB ingest, OFP/DF query) must agree on the scoping key.

---

## PIN-IEG-02 — Authority boundary

**Pin:** IEG is authoritative only for **its projection artifacts** (entities/edges/indices) and **`graph_version`** — not for admission, not for world truth, not for feature values.

Why now: prevents “two truths” drift and stops us accidentally assigning SR/IG/OFP responsibilities to IEG.

---

## PIN-IEG-03 — `graph_version` meaning (and what makes it comparable)

**Pin:** `graph_version` = **(stream_name + per-partition next-offset-to-apply vector)** with **exclusive-next** semantics.

**Additional v0 stance (critical):** `graph_version` is only comparable/stable **within a fixed stream identity**. If the platform ever changes the stream’s partitioning scheme in a meaningfully breaking way, that must be treated as a **new stream_name/version** (otherwise old graph_versions lose meaning).

Why now: OFP/DF provenance depends on recording graph_version; it must have stable interpretation.

---

## PIN-IEG-04 — Required identity-hints at the bus boundary

**Pin:** For an admitted event to mutate the graph, IEG requires envelope-visible identity hints (your design calls this `observed_identifiers[]`).

**Hard reality check:** the current canonical envelope schema is `additionalProperties: false` and does **not** include `observed_identifiers`.
So v0 must pin one of these as “the truth”:

* **(Preferred)** evolve the canonical envelope to include `observed_identifiers[]`, or
* define a *single standardized* identity-hints block under `payload` that is mandatory for graph-mutating event types (but then we’re not truly payload-blind).

Why now: without this, we cannot honestly define EB→IEG apply semantics.

---

## PIN-IEG-05 — Canonical entity ID strategy (engine IDs vs minted IDs)

This one matters more than it seems.

**Pin (v0 stance):** IEG canonical `EntityRef` must be **deterministic and stable under replay**; when the admitted event carries an **engine-stable identifier** (e.g., account_id-style identifiers), IEG should **reuse it** as the canonical `entity_id` for that entity_type; otherwise it deterministically mints one from first-seen identifiers + ContextPins.

Why now: it determines whether IEG can cleanly join (by-ref) to engine surfaces/truth products later without a permanent mapping layer. And by-ref + no-PASS/no-read is a platform rail.

---

## PIN-IEG-06 — Completeness and “bad event” posture

We must decide what `graph_version` *implies* about correctness when IEG encounters an event it cannot apply.

**Pin (v0 stance):**

* IEG never invents context; failures are explicit.
* IEG **does not block the whole projector forever** on one unusable event; it records an apply-failure tied to EB position and continues advancing watermarks.
* Therefore, every query response must include (in addition to graph_version) a small **projection integrity status** (e.g., “no known apply failures up to this graph_version” vs “apply failures exist”), so DL/DF can degrade explicitly when integrity is compromised. (This fits the platform’s “degrade is explicit, enforced, recorded” rail.)

Why now: otherwise “graph_version used” can silently mean “context maybe incomplete,” which is exactly the kind of hidden assumption you’re trying to eliminate.

---

## PIN-IEG-07 — Identity resolution posture (merges or no merges)

**Pin (v0 stance):** **no merges**. IEG supports links/aliases and can return **multiple candidates** (conflict) but does not collapse entities.

Why now: it changes the meaning of `resolve_identity` and how DF/OFP interpret ambiguity.

---

## PIN-IEG-08 — Minimal query surface + determinism guarantees

**Pin:** IEG serves a small, deterministic query set (at minimum resolve/profile/neighbors), and **every response includes ContextPins + graph_version** with deterministic ordering.

Why now: the “downstream contract” to OFP/DF is impossible to define without agreeing on what IEG can be asked and what it *must* return.

---

### One extra pin that’s implied by your SR ingest decision

Because v0 uses **pull ingestion** (traffic starts after READY), IEG can assume “hot-path traffic for a run arrives after SR READY exists,” and it should not need to handle a long-lived pre-READY backlog for that run context.

---

Yes — if we treat **IEG as an opaque vertex**, then a “production-ready platform” gives it a **finite, checkable set of joins**, plus **paths** (multi-hop flows) and **loops** (cycles) that either *touch* IEG directly or *use IEG’s outputs as provenance inputs*.

Below is the complete neighborhood + the realistic paths/loops that exist *given your pinned platform graph*.

---

## 1) Direct joins incident to IEG (the full edge set)

### J-IEG-IN-1 — Event Bus → IEG projector (mandatory)

* **Edge:** `EB(fp.bus.traffic.v1)` ➜ `IEG`
* **Meaning:** IEG is an always-on EB consumer; its only “truth feed” is **admitted canonical events** with duplicates/out-of-order assumed.
* **Determinism rail:** idempotent apply via `update_key` and `graph_version` derived from **per-partition next-offset-to-apply watermark vector (+ stream identity)**.
* **Important boundary pin:** hot-path consumers (including IEG) **only accept reality from EB**; no side channel bypasses IG→EB.

### J-IEG-OUT-1 — IEG → IEG derived store (mandatory substrate join)

* **Edge:** `IEG` ➜ `DB schema: ieg` (projection + checkpoints)
* **Meaning:** the graph store is **derived/rebuildable**; correctness token is `graph_version`; checkpoints must persist for operational continuity.

### J-IEG-OUT-2 — Downstream callers → IEG query surface (mandatory in production shape, even if “in-process” locally)

* **Edge A:** `Decision Fabric` ⇄ `IEG query API` (direct context use)
* **Edge B:** `Online Feature Plane` ⇄ `IEG query API` (optional but first-class in design)
* **Meaning:** DF is allowed/expected to call IEG for context; OFP may call IEG to resolve canonical keys and must capture `graph_version` in provenance when it does.

### J-IEG-OUT-3 — IEG → Audit pointer stream (optional)

* **Edge:** `IEG` ➜ `fp.bus.audit.v1` *(pointer events only; no payload dumping)*
* **Meaning:** optional “pointer” emissions (e.g., “IEG status / checkpoint advanced / ref X exists”) for audit/index ergonomics.

### J-IEG-OPS-1 — IEG → Observability pipeline (mandatory ops join)

* **Edge:** `IEG` ➜ `Obs/Gov pipeline (OTLP)`
* **Meaning:** everything emits telemetry; DL consumes obs signals to compute degrade posture; so IEG must expose lag/health/error surfaces via telemetry.

### J-IEG-OPS-2 — Run/Operate / Backfill → IEG rebuild/replay (mandatory production capability)

* **Edge:** `Run/Operate(backfill/replay job)` ➜ `IEG derived store`
* **Meaning:** IEG projections **can be backfilled/rebuilt**, but only as **explicit, scoped, auditable operations**; watermarks remain monotonic; archive is EB’s continuation for long replay.

---

## 2) Explicit non-joins (these do *not* exist in a correct production platform)

These are important because they eliminate “hidden bypasses”:

* **No producer writes directly into IEG.** Anything that can influence identity must enter via **IG → EB**.
* **IEG does not consume engine surfaces as hot-path input.** Engine “surfaces” are by-ref artifacts used by SR/learning/audit, while hot-path identity context is driven from EB facts.

---

## 3) The production paths that involve IEG (multi-hop flows)

Think of these as the “routes” that will be exercised in real operation.

### P1 — Main hot path (context-enabled decision)

`Producer (engine traffic / external txn / etc.)`
➜ `IG (admit/quarantine/dedupe)`
➜ `EB(fp.bus.traffic.v1)`
➜ `IEG (projection updated; graph_version advances)`
➜ `OFP (optional IEG query for canonical keys)`
➜ `DF (gets features + provenance, records graph_version if used)`
➜ `DF emits decision + action intent as events (via IG→EB)`

### P2 — Variant: DF calls IEG directly (without OFP mediation)

`EB event triggers DF`
➜ `DF → IEG query`
➜ `DF uses context + records graph_version in provenance`
➜ `DF emits decision/action events`

### P3 — Action execution path (creates new facts that can later affect identity)

`DF action intent`
➜ `IG → EB`
➜ `AL consumes intent, executes, emits outcome`
➜ `IG → EB`
➜ *(these new admitted events are also consumed by IEG/OFP/etc.)*

### P4 — Evidence/flight-recorder path (IEG context becomes auditable)

`DF decision provenance includes (feature_snapshot_hash, input_basis, graph_version, degrade posture, bundle ref)`
➜ `DLA consumes traffic + receipts refs, writes immutable audit record`
➜ `Case/Offline/Gov read audit by-ref`

### P5 — Learning parity path (IEG’s graph_version becomes a rebuild target)

`Audit record (decision-time provenance)`
➜ `Offline Shadow rebuild uses EB/Archive + as-of rules`
➜ parity evidence ties back to `input_basis` + `graph_version`
➜ `DatasetManifest → Model Factory → Registry`
➜ `Registry changes ACTIVE bundle → DF behavior changes (future decisions)`

### P6 — Backfill/replay path (derived store repair without “time travel”)

`Run/Operate declares backfill(scope,basis,outputs)`
➜ rebuild IEG projection from EB/Archive for that explicit basis
➜ new derived state exists; offsets/watermarks remain meaningful and monotonic

---

## 4) The loops (cycles) that exist in production

### L1 — Decision/action feedback loop (core runtime cycle)

`EB → IEG → (OFP) → DF → (IG→EB) → AL → (IG→EB) → IEG → …`

**Why it matters:** IEG doesn’t just “support one decision”; its context shapes decisions that create actions/outcomes that return as new facts.

### L2 — Observability/degrade control loop (safety + load shedding)

`IEG telemetry (lag/errors)`
➜ `Obs pipeline`
➜ `DL computes capabilities_mask`
➜ `DF constrained (may stop using IEG / certain tools)`
➜ reduced dependency/load until recovery

### L3 — Learning evolution loop (closed-world improvement loop)

`IEG context → decision provenance (graph_version) → audit`
➜ `Offline Shadow rebuild/parity → DatasetManifest`
➜ `Model Factory bundles + evidence`
➜ `Registry ACTIVE change`
➜ `DF decisions change`
➜ new events feed back into `EB → IEG`

### L4 — Backfill correction loop (ops realism loop)

`Bug fix / schema evolution / late facts`
➜ `declared backfill`
➜ rebuild `IEG` (and possibly OFP/offline artifacts)
➜ future decisions cite new provenance; old provenance remains explainable

---

## 5) “IEG neighborhood” as a compact adjacency view

```
                 (OTel / Obs)
                     ^
                     |
                     |
EB fp.bus.traffic.v1  |      (optional) fp.bus.audit.v1
        |             |              ^
        v             |              |
     [IEG] ---------- + ----------> (pointer events)
        |
        v
   DB: ieg projection + checkpoints

Callers (query):
  DF  <------->  IEG
  OFP <------->  IEG   (optional, for canonical keys + graph_version provenance)
```

Grounded by: EB→IEG join semantics + graph_version meaning , deployment unit map , and the “no side door into hot path” rail .

---

Here’s the **order I recommend expanding**, covering the **complete production set** (joins → paths → loops), while keeping IEG opaque:

1. **J-IEG-IN-1:** EB ➜ IEG projector feed (apply semantics, idempotency, watermark inputs)

2. **J-IEG-OUT-1:** IEG ➜ derived graph store + checkpoints (what “exists” as projection truth)

3. **J-IEG-OUT-2A:** DF ⇄ IEG query surface (decision-time context + provenance)

4. **J-IEG-OUT-2B:** OFP ⇄ IEG query surface (feature-time context + provenance)

5. **J-IEG-OPS-1:** IEG ➜ Observability/Governance signals (lag, health, integrity)

6. **J-IEG-OPS-2:** Run/Operate ⇄ IEG (rebuild/backfill/replay control plane)

7. **J-IEG-OUT-3 (optional):** IEG ➜ audit pointer stream (lightweight pointers/status, no payload)

8. **P1:** Main hot path: IG→EB→IEG→(OFP)→DF→(IG→EB)

9. **P2:** Variant path: IG→EB→IEG→DF (DF calls IEG directly)

10. **P3:** Action path: DF→(IG→EB)→AL→(IG→EB)→IEG (new facts feed back)

11. **P4:** Evidence path: (DF provenance includes graph_version) → DLA audit record

12. **P5:** Learning/parity path: audit → offline rebuild/parity → MF/MPR → DF behavior shift

13. **P6:** Repair path: declared replay/backfill → rebuild IEG derived state (no truth rewrite)

14. **L1:** Decision/action feedback loop (runtime cycle)

15. **L2:** Observability/degrade control loop (safety/load shedding)

16. **L3:** Learning evolution loop (model/policy updates feed future decisions)

17. **L4:** Backfill correction loop (ops reality: rebuilds without breaking explainability)

---

Absolutely — we’ll expand those four joins **with IEG still treated as opaque**, meaning: we define **what crosses the boundary, what each side can assume, what must be recorded, and what failure looks like**, without designing the internal modules yet.

---

# J-IEG-IN-1 — Event Bus ➜ IEG projector feed

## What this join *is for*

Turn **admitted canonical events** into a **replay-safe, run/world-scoped projection** whose progress is represented by `graph_version`.

## Upstream truths IEG must assume (and must be safe under)

* EB delivers a fact log where the only stable position is **(stream_name, partition_id, offset)**; ordering is only within a partition; delivery is **at-least-once** (duplicates are normal).
* Consumer checkpoints use **exclusive-next** semantics: the stored offset means “next offset to read/apply”. 
* IG decides admission and stamps a deterministic partition key; EB does not validate/transform.
* The bus boundary shape is the **Canonical Event Envelope**: required `{event_id, event_type, ts_utc, manifest_fingerprint}`, optional pins `{parameter_hash, seed, scenario_id, run_id}`, plus trace fields and `payload`.
* **Time semantics never collapse**: domain time is `ts_utc`; ingestion/apply times must not overwrite it.

## What IEG requires to treat an event as “graph-mutating”

IEG processes *all* admitted events, but only some are **eligible** to mutate the graph.

### Minimum envelope for any event

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` (always). 

### Additional requirements for **run/world-scoped graph mutation**

* Full **ContextPins** must be present: `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`.
* A standardized **identity hints** block must be present (`observed_identifiers[]` concept). Your platform blueprint pins this as required for envelope-driven identity updates.

**Design pin (so this join is implementable today):**
The current canonical envelope schema does not contain `observed_identifiers` (and forbids unknown top-level fields).
So, for v0, we treat `observed_identifiers[]` as **a platform-standard identity-hints block** that is available at the bus boundary by one of:

1. **v1 canonical-event pack** extends the envelope to include it (preferred long-term), or
2. v0 bridge: it lives under a reserved location in `payload` with a fixed name and shape, enforced by IG for identity-impacting event types (explicitly not “freeform payload parsing”).
   Either way, the join contract is: **IEG can reliably obtain `observed_identifiers[]` for identity-impacting events**.

## Core replay-safety rule (the heart of this join)

IEG applies events idempotently using:

* `update_key = H(ContextPins + event_id + update_semantics_id)`
  where `update_semantics_id` is pinned as a constant for v0 (the blueprint explicitly calls out a “pinned semantics id”).

**Consequence:** duplicates / redelivery must be logical no-ops (no duplicate entities/edges, no timestamp corruption).

## Watermark and `graph_version` advancement (what “applied” means)

* For each ContextPins-scoped graph, IEG maintains a **per-partition applied-offset watermark vector** where each value is the **next offset to apply (exclusive)**.
* `graph_version` is a monotonic token meaning:
  **(stream_name + watermark_basis map)**.
* Watermarks **don’t lie**: they are monotonic; backfill doesn’t “edit history”; new facts create new offsets.

## Event classification (so we don’t hide assumptions)

Every admitted event must deterministically fall into one of these categories:

1. **GRAPH_MUTATING**
   Event has ContextPins + identity hints (and is of an identity-relevant type).
2. **GRAPH_IRRELEVANT**
   Event is admitted but intentionally does not participate in identity context (no-op by design).
3. **GRAPH_INVALID_FOR_MUTATION**
   Event type is identity-relevant but missing required pins/hints (this should be rare if IG enforces properly).

### Failure posture at the boundary

IEG must not “fix” or invent missing context. If an event is GRAPH_INVALID_FOR_MUTATION:

* it must **not mutate** the projection from that event,
* it must record an **explicit apply-failure fact** tied to the EB position,
* and expose it via ops signals (so DL/DF can degrade explicitly).

**Design pin (availability over deadlock):**
IEG does **not** stall forever on one bad event; it records the failure and continues advancing offsets, but surfaces an integrity indicator so callers can treat the projection as degraded if needed. (This aligns with “degrade is explicit, enforced, recorded”.)

### Minimal sequence (conceptual)

```
EB delivers (stream, partition, offset, envelope)
  -> IEG derives update_key
  -> if update_key already applied: no-op
  -> else: apply (entities/aliases/edges), record provenance=(stream,partition,offset)
  -> advance partition watermark to offset+1
```

(All meaning is pinned: offsets exclusive-next; duplicates expected; idempotent apply; graph_version from watermark basis.)

---

# J-IEG-OUT-1 — IEG ➜ derived graph store + checkpoints

This is the “IEG persists what it knows” boundary (even if it’s the same process in local).

## Truth posture of the store

* The IEG store is **derived/rebuildable**, not primary truth.
* Source of truth is EB/Archive; proof token is `graph_version` derived from applied watermarks.

## What must exist in the derived store (minimum families)

For each **ContextPins-scoped graph**:

1. **Entity canonical records**

* `EntityRef = {entity_type, entity_id}`
* minimal “thin” record is fine; richer attributes are policy/v1.

2. **Identifier alias/link index**

* mapping from `ObservedIdentifier -> EntityRef(s)`
* must support conflicts (one identifier mapping to multiple entities) without merges (v0 posture).

3. **Edges / relationships**

* unique by `(src, dst, edge_type)`
* timestamps derived from domain time (min/max rules under disorder)
* store a `provenance_ref` that points back to the causing EB position.

4. **Applied update ledger**

* record applied `update_key`s to guarantee idempotency under replay/redelivery.

5. **Checkpoint / watermark basis**

* per partition: `next_offset_to_apply` (exclusive-next), used to compute `graph_version`.

6. **Integrity metadata (mandatory for production realism)**

* apply-failure counts and last-known failure positions (at least)
* enables explicit degrade decisions if projection integrity is compromised.

## The key store invariant (prevents “lying versions”)

IEG must never serve a `graph_version` that implies offsets have been applied **unless the corresponding state mutations are also durable/visible**.

Practical design rule:

* `state mutations + update_key mark + watermark advance` must be committed as one coherent “apply” unit (how is implementer freedom).
* Query responses return a `graph_version` that matches the basis the query is consistent with.

## Rebuild posture (ties to ops/backfill later)

* Wiping/corruption is survivable: rebuild by replaying EB/Archive under an explicit basis; never silent backfill.

---

# J-IEG-OUT-2A — Decision Fabric ⇄ IEG query surface (decision-time context)

## Why DF calls IEG

DF needs identity + relationship context to interpret an event (“who/what is involved, what is connected”) and to record **exactly which context was used** for audit/replay.

## What DF must do (pinned)

* DF must record `graph_version used` in decision provenance whenever IEG contributed context (directly or indirectly).
* DF must not invent missing context; it follows safe posture under unavailability and must obey degrade constraints.

## Join surface: v0 query operations (designer-lock for this brainstorm)

To keep it minimal and sufficient:

* `resolve_identity(observed_identifiers, pins)`
* `get_entity_profile(entity_ref, pins)`
* `get_neighbors(entity_ref, pins, edge_type?, depth=1)`

(These are the only “shapes” DF needs to treat IEG as a context oracle; anything more is v1.)

## Response invariants (critical for determinism + hashing downstream)

Every successful response must include:

* echoed **ContextPins**
* `graph_version` (stream_name + watermark basis)

And list ordering must be deterministic (sorted), so that any downstream hashing/provenance is stable. (This is a platform-wide determinism practice, and we promote it here as a join invariant.)

## Optional but important: “minimum basis” constraint (prevents silent staleness)

DF may include a **minimum required applied position** (e.g., “must have applied at least offset X for partition P”) so it can refuse stale context in high-stakes flows.

If IEG cannot satisfy it, it returns an explicit error:

* `IEG_LAGGING` (retryable=true) + current `graph_version`.
  This is how DF can degrade explicitly instead of unknowingly using stale context.

## Error posture (must be explicit)

If IEG cannot serve correct context:

* it returns an explicit ErrorResponse with `retryable` flag
* it does not fabricate substitutes
* DF records unavailability and follows fail-safe posture.

---

# J-IEG-OUT-2B — Online Feature Plane ⇄ IEG query surface (feature-time context)

This join is deceptively dangerous: if OFP consults IEG at the wrong time, you can create nondeterministic coupling. So we pin the safe posture.

## What the platform already pins

* OFP consumes EB events to maintain aggregates/state, and may consult IEG to resolve canonical keys.
* Every served `get_features` response must include provenance, including:

  * `as_of_time_utc` (explicit; no hidden “now”)
  * `input_basis` watermark vector
  * and **`graph_version` if IEG was consulted**, and snapshot hashing must cover these deterministically.

## Designer pin: when OFP is allowed to consult IEG in v0

**v0 posture (safe + minimal):**
OFP consults IEG **at serve time** (when forming a snapshot), not inside its projector update loop.

Why: it avoids “OFP behavior depends on IEG lag at that moment,” which would break determinism across environments/replays.

So in v0:

* OFP projector updates remain purely EB-position-driven and idempotent on its own key recipe.
* IEG is consulted during snapshot assembly to:

  * resolve identifiers to canonical EntityRefs (if needed),
  * optionally fetch neighbors for context-derived feature grouping,
  * and stamp `graph_version` into provenance.

## What crosses the join (OFP → IEG)

Same v0 ops as DF uses (resolve/profile/neighbors), but with OFP-specific rules:

* OFP must pass ContextPins and any identity hints it has (usually derived from the event being scored or the subject of the snapshot).
* OFP may pass a minimum basis requirement (optional), e.g., “don’t use IEG unless it’s at least as up-to-date as X,” to avoid stale context.

## What crosses the join back (IEG → OFP)

* Context results (EntityRefs / edges / neighbors)
* `graph_version` (mandatory if consulted)

OFP then includes `graph_version` in its provenance and in the deterministic snapshot hash coverage. 

## Failure posture (OFP must make it explicit)

If IEG is unavailable or lagging:

* OFP must either:

  1. serve features that do not require IEG context **and omit graph_version**, explicitly marking that IEG context was not used, or
  2. mark the affected feature groups as unavailable (so DF can follow fail-safe).

No silent fallback where OFP pretends it used identity context when it didn’t.

---

## Quick recap of the four expanded joins (the “outer truth” we just pinned)

* **EB→IEG:** idempotent apply keyed by `update_key`; graph_version = stream_name + per-partition exclusive-next watermark basis; explicit handling of invalid-for-mutation events; domain time is `ts_utc`.
* **IEG→Store:** derived/rebuildable projection must persist entities/aliases/edges/update_keys/watermarks + integrity metadata; never serve a graph_version that overstates applied state.
* **DF↔IEG:** DF uses IEG for context; records graph_version used; explicit errors; optional min-basis constraint to prevent silent staleness.
* **OFP↔IEG:** v0 consult at serve-time; if consulted, graph_version must appear in provenance+hash coverage; explicit behavior when unavailable.

---

Cool — let’s expand **#5–#8** in the same “IEG is opaque” style: define the *outer expectations* (what crosses the boundary, what’s assumed, what must be recorded, and what failure looks like), without opening the inner modules.

---

## #5 — J-IEG-OPS-1: IEG ➜ Observability/Governance signals

### What this join is *for* (production truth)

Obs/Gov must answer, reliably: **(1) what happened/why, (2) are we healthy enough to act, (3) what changed**.
IEG contributes to (2) and (1) mainly: “is identity context trustworthy/available right now?” and “what basis did you use?”

### What IEG must emit (minimum viable, but real)

Think in **4 channels**: metrics, logs, traces, and (optionally) durable “operational facts”.

#### A) Metrics (automation inputs; DL will consume these via Obs)

**Golden signals (always)**: throughput, latency (p95), error rate (by class), saturation/backlog.
**Platform-specific mandatory for EB consumers (IEG/OFP/DLA)**:

* **consumer lag per partition**
* **watermark age** (how far behind in time the applied offsets are)

For IEG specifically, the minimum *useful* set is:

1. **Projector progress**

* `ieg_consumer_lag{partition}`
* `ieg_watermark_age_seconds{partition}` (derived from applied offset → last applied event’s `ts_utc` vs wall-clock)

2. **Apply quality / integrity**

* `ieg_apply_total{class=applied|duplicate_noop|irrelevant|invalid_for_mutation|error}`
* `ieg_apply_failures_total{reason}` (missing pins, missing id-hints, malformed)
* `ieg_projection_integrity_flag` (0/1: “known apply failures exist in this run scope”)

3. **Query surface (if you expose it)**

* `ieg_query_latency_ms{op}` (resolve/profile/neighbors)
* `ieg_query_error_total{op,reason}`

These are the exact kinds of signals your **Degrade Ladder** is designed to consume (via Obs pipeline), so DF can be constrained explicitly.

#### B) Logs (human debugging; structured + by-ref)

Your baseline says logs must be **structured**, **by-ref friendly**, and must never dump raw payloads by default.
IEG’s “truth-defining boundary decisions” are *projection decisions*, so the minimum log events are:

* **Apply classification**: applied / duplicate-noop / invalid-for-mutation (include EB coords)
* **Integrity transitions**: “integrity clean → degraded” (when first apply-failure occurs), and “degraded → clean” (only when explicitly resolved via rebuild/backfill)
* **Query failures**: explicit error responses (retryable vs not)

Every log line carries the **applicable correlation keys** (ContextPins, event_id, graph_version, etc.).

#### C) Traces (end-to-end causality)

Baseline pin: if an event has `trace_id/span_id`, propagation is preserved through IG→EB and downstream; DF spans should include child spans for OFP/IEG/Registry calls.
So IEG must:

* accept inbound trace context on query calls (DF→IEG, OFP→IEG)
* emit a span per query op (resolve/profile/neighbors) so DF’s decision trace becomes inspectable end-to-end.

#### D) “Operational facts” (durable governance-grade signals) — optional but valuable

Obs/Gov baseline also says **changes must be observable facts**, not just logs (e.g., “backfill executed”).
IEG itself shouldn’t invent governance; instead:

* **Run/Operate** (or the backfill job) emits “IEG rebuild/backfill executed” facts, and
* IEG contributes by emitting *the measured results* (lag cleared, integrity restored) as telemetry.

### The non-negotiable guardrail

Obs/Gov must never “silently mutate behavior”; it influences the system only via explicit control surfaces (notably DL).
So: **IEG emits signals; DL turns them into a mask; DF obeys; DLA records.**

---

## #6 — J-IEG-OPS-2: Run/Operate ⇄ IEG rebuild/backfill/replay control plane

### What this join is *for*

IEG is **derived/rebuildable**, so production needs an explicit way to:

* rebuild after corruption,
* reprocess after a bug fix or schema evolution,
* replay beyond EB retention using archive,
* and do it without “time travel” or silent changes.

### What’s allowed vs disallowed (hard pins)

**Allowed to backfill (derived):** IEG projections.
**Not allowed:** mutate EB admitted facts; rewrite SR run ledger; rewrite truth timelines.
**Watermarks don’t lie:** offsets/watermarks remain meaningful and monotonic; backfill doesn’t pretend history changed.

### The required operational handshake (declared + auditable)

Backfill is not “we ran it again”; it is a **declared operation** with:

* **scope** (streams/partitions + offset/time window),
* **purpose** (why),
* **basis** (explicit replay basis),
* **outputs** (what derived artifacts/stores are regenerated),
  and it must emit a **durable governance fact**.

**Replay basis must be explicit** (offset ranges preferred; time windows only if anchored to recorded checkpoints/watermarks).

### Archive involvement (when retention isn’t enough)

Archive is a **continuation of EB**, preserving the same logical events/envelopes; consumers replay from archive “as if it were EB”, and they record the basis used.
Archive addressing is pinned as **by-ref** (no “search vaguely”).

### Operational outcomes IEG must support

From the IEG side, Run/Operate needs only these “outer behaviors”:

1. **Freeze/maintenance posture (optional)**

* During a rebuild, IEG may (a) continue serving stale-but-labelled, or (b) refuse and return explicit “maintenance / lagging” errors. Either way, it must be explicit.

2. **Explicit cutover semantics**

* A rebuild produces a new derived state that becomes “active”; it is not a silent overwrite. (Whether you do side-by-side then swap, or in-place with downtime, is implementer freedom — the *visibility* is the pin.)

3. **Post-rebuild integrity reset**

* If apply-failures previously existed, the only way to claim “integrity clean” again is via an explicit rebuild/backfill event (durably recorded).

---

## #7 — J-IEG-OUT-3 (optional): IEG ➜ audit pointer stream (`fp.bus.audit.v1`)

### What this join is *for*

A low-volume stream of **pointer events** that say “a thing exists at ref X” without embedding payloads — used for audit/index ergonomics, not decisioning.

This aligns with your by-ref posture and “don’t dump payloads into logs” rule.

### What IEG is allowed to emit here (only coarse, low-volume facts)

IEG must **not** emit per-edge/per-entity chatter (that becomes a second traffic stream). Pointer stream is for *milestones*.

Good v0 candidates:

* `IEG_RUN_CONTEXT_ACTIVATED`
  “IEG is now serving for these ContextPins” (helps ops correlate readiness vs projection availability)

* `IEG_INTEGRITY_DEGRADED`
  “apply-failures exist” + pointer to an ops record / log correlation id

* `IEG_REBUILD_COMPLETED`
  includes the **replay basis ref** + resulting `graph_version` checkpoint basis

* `IEG_CHECKPOINT_ADVANCED` (rate-limited / periodic)
  optional heartbeat: “current graph_version for scope S is V”

All of these must carry correlation keys (ContextPins; and `graph_version` when applicable).

### Guardrail: pointer stream is never a “second truth feed”

* It is not consumed by IEG/OFP/DF as factual basis.
* It must never become a side-door that influences identity/features/decisions. (“Only one front door” into the hot path stays intact.)

---

## #8 — P1 Main hot path: IG→EB→IEG→(OFP)→DF→(IG→EB)

Below is the production narrative, including what must be recorded for determinism + auditability.

### Step 0: Preconditions (run/world joinability exists)

SR is the system-of-record for run identity and publishes READY + `run_facts_view` (pins + refs). IG uses this to enforce joinability.

### Step 1: Producer ➜ IG (trust boundary decision)

A producer event arrives (engine traffic, external txn, DF outputs, AL outcomes, etc.). IG:

* validates canonical envelope shape,
* enforces run/world joinability (unknown/unready → quarantine),
* chooses/stamps a deterministic `partition_key`,
* decides **ADMIT / DUPLICATE / QUARANTINE**, and
* **ADMIT isn’t true until EB ack**.

### Step 2: IG ➜ EB (durable fact append)

EB assigns **(partition, offset)**; this is the replay token every consumer uses for watermarks/checkpoints. EB delivers at-least-once, and duplicates are assumed downstream.

### Step 3: EB ➜ IEG projector (identity context materializes)

IEG consumes admitted events and:

* applies idempotently via `update_key = H(ContextPins + event_id + pinned semantics id)`,
* is safe under duplicates/out-of-order,
* advances `graph_version` as a monotonic token based on **per-partition next_offset_to_apply watermark vector + stream_name**.

### Step 4: EB (+ optional IEG queries) ➜ OFP (feature snapshot readiness)

OFP maintains state from EB and, optionally, queries IEG to resolve canonical keys and capture `graph_version` for provenance.
OFP serves deterministic snapshots with provenance including:

* `feature_snapshot_hash`,
* `as_of_time_utc` (explicit; no hidden now),
* `input_basis` watermark vector,
* and `graph_version` if IEG was consulted.

### Step 5: Obs ➜ DL ➜ DF (explicit safety constraints)

Obs/Gov supplies signals; DL produces an explicit, recordable `{mode, capabilities_mask, provenance}`. DF must obey it; DLA must record it.

### Step 6: DF makes the decision (with full provenance)

DF:

* treats `ts_utc` (event time) as the decision boundary and calls OFP with `as_of_time_utc = event_time_utc`,
* may call IEG directly if needed (but still records graph_version),
* resolves ACTIVE bundle via Registry and records bundle ref,
* records provenance: snapshot hash + input_basis (+ graph_version if used) + degrade posture + bundle ref,
* emits **DecisionResponse** + idempotent **ActionIntents** as canonical envelope events.

### Step 7: DF outputs re-enter via IG→EB (same trust boundary)

DF doesn’t write to EB directly; it goes through IG, so admission/quarantine/duplicate logic stays uniform.

*(Then the path continues: AL executes intents effectively-once and emits outcomes; DLA writes the append-only audit “flight recorder”.) *

---

Got it — expanding **#9–#12 (P2–P5)** as **production paths** with IEG kept opaque. I’ll describe the *outer expectations* (what crosses boundaries, what must be recorded, and how failure/degrade behaves), staying inside your pinned platform laws (IG→EB only front door, canonical envelope boundary, idempotency, explicit degrade, by-ref audit, deterministic provenance).

---

## #9 — P2 Variant path: IG→EB→IEG→DF (DF calls IEG directly)

### What makes this a “real” production path

DF is allowed to use **IEG context directly** (not only via OFP), and must record **which `graph_version` it used** so the decision is explainable/replayable.

### The path, step-by-step

1. **Producer → IG → EB**

   * IG admits/quarantines/duplicates and admission is atomic with EB append; EB becomes the replayable fact basis.

2. **DF is triggered**

   * DF receives the driving event either as an EB consumer or via a synchronous decision request that is still bound to the same event identity and pins. (DF’s production inputs include EB traffic + DL posture + Registry bundle resolution + optional IEG context.)

3. **DF obtains degrade posture (always)**

   * DL supplies a deterministic, recordable `capabilities_mask` that DF must treat as **hard constraints**; DF records posture in provenance.

4. **DF resolves the Active bundle (always, unless degraded to safe fallback)**

   * Registry returns a deterministic **ActiveBundleRef** (no “latest”), compatibility-aware; DF records the bundle ref (or records incompatibility + fallback).

5. **DF calls IEG directly (this is the variant)**

   * DF sends a minimal query like `resolve_identity` and/or `get_neighbors` tied to ContextPins; IEG returns context **plus `graph_version`**.
   * DF records `graph_version used` in decision provenance.

### Why DF does this (typical production reasons)

* **When the decision needs identity context even if features are degraded/unavailable** (e.g., safe heuristics that rely on “who is linked to what” rather than numeric features). This fits the “degrade is explicit” rail: the capability may be allowed or disabled.
* **When the Active bundle’s compatibility says identity context is required** (bundle requires certain capabilities; if disabled, DF must fail closed or safe fallback).

### Failure posture (the important “outer contract”)

* If DL disables the “use IEG” capability, DF behaves as if IEG **doesn’t exist**.
* If IEG is lagging/unavailable, DF **does not invent context**; it records unavailability and follows its fail-safe posture (e.g., safer decision/action set).
* If IEG returns context, DF must treat it as **projection context**, not world truth; its trust is bounded by recorded `graph_version`.

---

## #10 — P3 Action path: DF→(IG→EB)→AL→(IG→EB)→IEG (new facts feed back)

### What makes this path essential

Actions are **how decisions create new facts** that re-enter the same IG→EB truth pipeline, then propagate to IEG/OFP/DF again. In production, this is the “closed loop” of detection→intervention→new evidence.

### The path, step-by-step

1. **DF emits ActionIntents (as traffic)**

   * DF’s output is canonical envelope events to `fp.bus.traffic.v1` (decision + action-intents).
   * Each ActionIntent carries a deterministic `idempotency_key` and join identifiers (ContextPins + decision/event identifiers).
   * ActionIntents enter the platform the same way everything does: **via IG→EB** (no side door).

2. **AL consumes intents and executes effectively-once**

   * AL is the only component that executes; everyone else only requests.
   * AL enforces effectively-once execution using **(ContextPins, idempotency_key)** as uniqueness scope; duplicate intents never re-execute, they re-emit the same outcome.
   * AL is also a control choke point: allowlist + scope rules; denies produce immutable outcomes too.

3. **AL emits immutable ActionOutcomes (as traffic)**

   * Outcomes are immutable history; every attempt yields an outcome (EXECUTED/DENIED/FAILED), and duplicates are byte-identical.
   * Outcomes re-enter through **IG→EB** like any other decisionable facts.

4. **IEG consumes outcomes as new observations**

   * IEG reads admitted events from EB; action outcomes are “real traffic,” so they participate like any other event.
   * Whether an outcome mutates the graph depends on whether it carries identity-relevant hints (the platform’s “envelope-driven updates” requirement).

### The key pin here (so the loop is meaningful)

If you want action outcomes to **affect identity context**, they must be emitted in a way IEG can consume without semantic payload parsing — i.e., they must carry the identity-hints block required for IEG mutation (your `observed_identifiers[]` concept).

That’s how “we challenged this device and it succeeded/failed” becomes a new relationship signal without turning IEG into a payload parser.

---

## #11 — P4 Evidence path: (DF provenance includes graph_version) → DLA audit record

### What makes this path “production-grade”

DLA is the immutable **flight recorder**: it must capture the minimum facts needed to reproduce/justify a decision later, **without embedding raw payloads**, and must fail closed on incomplete provenance.

### The path, step-by-step

1. **Facts exist on EB**

   * Decisions, action-intents, and outcomes are all canonical traffic on `fp.bus.traffic.v1` (post IG admission).

2. **DF emits the non-negotiable provenance base**

   * DF records what it used:

     * `feature_snapshot_hash`, group versions, freshness/stale flags, `input_basis` watermark vector
     * and `graph_version` if IEG was consulted
     * plus degrade posture and the resolved ActiveBundleRef.

3. **DLA ingests and writes an immutable AuditDecisionRecord**

   * DLA’s primary ingest is DF’s DecisionResponse (decision + actions + provenance); AL outcomes are optional add-ons to close the loop, but DF provenance is the base.
   * Audit record must include by-ref / hashed pointers to:

     * event reference basis (what was decided on),
     * `feature_snapshot_hash` + `input_basis`,
     * `graph_version` (if used),
     * degrade posture,
     * bundle ref,
     * actions (with idempotency keys),
     * audit metadata (ingested_at, supersedes chain).

4. **Correction posture**

   * DLA is append-only; corrections are **supersedes chains**, never overwrites. Ingest is idempotent.

### Failure posture (critical pin)

If provenance is incomplete, DLA **quarantines the audit record** rather than writing a half-truth.

And because IG receipts can capture EB coordinates (admission atomic with EB append), audit can point deterministically at “where the fact lives.”

---

## #12 — P5 Learning/parity path: audit → offline rebuild/parity → MF/MPR → DF behavior shift

### What makes this path the platform’s anti-drift backbone

This is the “close the world” loop: decisions become auditable facts; offline rebuilds are deterministic; training produces deployable bundles; registry activation changes live behavior in a controlled, explainable way.

### The path, step-by-step

1. **Audit provides the anchors**

   * Audit records include the exact provenance needed to reproduce serving context:

     * `feature_snapshot_hash`, `input_basis`, and `graph_version` (if used), plus feature versions + degrade posture + bundle ref.
   * These are your parity anchors (“rebuild the same snapshot under the same basis”).

2. **Offline Feature Shadow rebuilds deterministically**

   * Reads event history from EB within retention, and from archive beyond retention — treated as the **same logical fact stream** (same envelope semantics/identity).
   * Reads labels from Label Store with explicit **as-of** rules (effective vs observed time) to prevent leakage.
   * Records its basis:

     * event window (offset ranges or declared time window tied to offsets),
     * as-of boundary,
     * feature definitions/versions used,
     * and parity anchors (e.g., target snapshot hashes).

3. **Offline Shadow → Model Factory: DatasetManifests**

   * Offline Shadow outputs **DatasetManifests**, not “a dataframe”: they pin dataset identity, boundaries, join keys/entity scoping, feature versions, refs/digests, and provenance.
   * Model Factory treats manifests as immutable inputs (reproducible training depends on re-resolving exact manifests later).

4. **Model Factory → Registry (MPR): Bundles + evidence**

   * MF publishes deployable bundles with immutable refs/digests, training provenance (which DatasetManifests), evaluation evidence, and any receipts required by governance posture.
   * Registry is the only authority that decides ACTIVE; promotion/rollback is auditable. Compatibility metadata (expected feature versions/inputs and required capabilities) is mandatory.

5. **Registry activation → DF behavior shift**

   * DF resolves bundles deterministically (no “latest”), records bundle ref used, and refuses ACTIVE-but-incompatible bundles under feature mismatch or degrade constraints.
   * Result: when live behavior changes, you can answer “what changed?” precisely: a registry governance event changed ACTIVE, and decisions cite the bundle ref.

### The core parity promise (why all this matters)

Because serving decisions record **feature snapshot hash + input_basis (+ graph_version if IEG was consulted)**, offline can rebuild “as-of” under the same basis and verify parity, preventing training/serving drift by construction.

---

Alright — expanding **#13–#17** (P6 + L1–L4) in **production detail**, with **IEG kept opaque** and everything staying inside your pinned rails: **IG→EB is the only entry for decisionable facts**, **EB is append+replay**, **IEG is a derived projection with `graph_version` from applied offsets**, **DL is the only behavior-control surface**, **DLA is the flight recorder**, **archive is EB’s continuation**, **backfills are declared + auditable + never rewrite truth**.

---

## #13 — P6 Repair path

### Declared replay/backfill → rebuild IEG derived state (no truth rewrite)

### What this path exists to do (production truth)

IEG is a **derived, rebuildable projection**. Repair/backfill is how you restore correctness after corruption, bugs, schema evolutions, or integrity incidents — **without rewriting EB facts** and without making “silent changes” that break explainability.

### Typical triggers (realistic)

* **Projection logic bug fix** (IEG was producing wrong edges/aliases).
* **Integrity degraded** (IEG recorded apply-failures that materially compromise trust).
* **Storage corruption / lost checkpoints**.
* **Schema evolution** that changes what identity hints are available/required at the boundary.
* **Retention/archive boundary** requires replay beyond hot retention.

### The declared backfill handshake (what must happen)

This is **not** “restart the service.” It’s a governed operation:

1. **Backfill is declared (before execution)**

   * Declares **scope** (streams/partitions + ContextPins if scoping by run/world), **purpose**, **basis** (offset ranges/checkpoints preferred), and **outputs** (IEG projection store generation).
   * Emits a durable governance fact (“backfill planned/started”).

2. **Replay source is chosen deterministically**

   * Replay from EB retention if available, else from **archive as EB’s continuation** (same envelope/event identity).
   * No vague “grab history”; basis is explicit.

3. **Rebuild produces a new derived output (not a stealth overwrite)**

   * Output is a **new IEG projection generation** (however implemented: side-by-side then swap, or in-place with downtime — but **visibility must be explicit**).
   * Completion emits a durable governance fact (“backfill completed”) + completion receipt.

4. **Cutover is explicit**

   * Serving flips to the new generation.
   * Old generation is either retained for investigations or treated as reconstructable by replay (but never silently “pretend it didn’t exist”).

### Two invariants that must never be broken

* **Truth is not rewritten:** EB admitted events are untouched; label timelines are append-only; registry history is append-only; SR ledger is append-only with supersedes; engine outputs are immutable for a pinned identity.
* **Watermarks don’t lie:** offsets/watermarks remain monotonic; a “historical rebuild as-of T” is done by explicit basis, not by pretending the stream changed.

### One extra pin I’m adding (to prevent silent semantic drift)

Backfills can change **derived meaning** even when offsets are identical (e.g., new bugfix logic produces different edges for the same applied offsets). Your rails already require derived outputs be **versioned/traceable, not stealth overwrites**.

**PIN (authoritative for this brainstorm):** whenever DF/OFP uses IEG context, provenance must record not just `graph_version` but also the **IEG projection generation/revision** (a stable identifier published by Run/Operate as part of the backfill/cutover).
That’s how “same offsets, different projector semantics” stays explainable later.

---

## #14 — L1 Runtime decision/action feedback loop (the core cycle)

This is the “system acts → the act becomes new facts → future decisions change.”

### The loop (opaque IEG, full platform realism)

```
IG→EB facts
  → IEG projection (graph_version advances)
  → (optional) OFP uses IEG context in snapshot provenance
  → DF decides under DL mask + Registry bundle
  → DF emits ActionIntents (via IG→EB)
  → AL executes effectively-once + emits ActionOutcomes (via IG→EB)
  → those outcomes are new facts → back into IEG/OFP/DF…
```

All enforced by the pinned joins: EB replay tokens power determinism; DF declares, AL executes; outcomes are immutable; everything enters via IG→EB. 

### What makes this production-safe (the three “dedupe anchors”)

* **IG/EB boundary:** admission is atomic with EB append; EB is at-least-once; duplicates are assumed. 
* **IEG boundary:** idempotent apply (duplicates don’t amplify into inconsistent projections); `graph_version` is derived from applied offsets. 
* **Action boundary:** ActionIntents carry deterministic `idempotency_key`; AL enforces effectively-once on `(ContextPins, idempotency_key)` and re-emits byte-identical outcomes on duplicates. 

### Why IEG matters in this loop (even opaque)

If you want actions/outcomes to influence identity context, they must re-enter as **admitted facts** carrying identity-relevant hints that IEG can project — not by side-channel mutation. That keeps “identity context” explainable as a function of the admitted record. 

---

## #15 — L2 Observability/degrade control loop (safety + load shedding)

This loop is the platform’s “nervous system,” but it’s not allowed to become a second decision engine.

### The loop (pinned behavior)

```
Components emit telemetry (lag, errors, health)
  → Obs/Gov aggregates signals
  → DL computes {degrade_mode, capabilities_mask, provenance} deterministically (+ hysteresis)
  → DF treats mask as hard constraints
  → DLA records degrade posture used (so behavior is explainable)
```

Obs influences behavior **only** through explicit DL outputs; if DL is unavailable, DF fails toward safety. 

### What IEG contributes to this loop (outer expectations)

IEG must surface enough signals to decide: “can we safely rely on identity context right now?”
Minimum production-grade signals include:

* consumer **lag / watermark age**
* apply-failure/integrity flag (projection compromised)
* query error rate / latency (if queried in hot path)

### What DL can *do* with those signals (examples of capabilities)

DL’s mask must be actionable. Examples (not exhaustive):

* disable “use IEG context” (DF behaves as if IEG doesn’t exist)
* disable specific OFP feature groups (DF can’t request them)
* disable risky actions (DF cannot emit certain intents)
* force safe fallback policy-only mode 

### The crucial production pin

Degrade is **recorded provenance**, not a hidden runtime tweak: every decision/audit record must be able to say “this was made under posture X.” 

---

## #16 — L3 Learning evolution loop (model/policy updates feed future decisions)

This is the “closed-world improvement loop” that prevents training/serving drift by construction.

### The loop (with the pinned choke points)

1. **Replayable reality exists**

   * Learning consumes **EB history** + **audit/provenance** (not live caches). 

2. **Offline Shadow rebuilds deterministically**

   * Rebuilds features/datasets “as-of time T” using explicit replay basis (offsets/checkpoints), label as-of rules, and feature definition versions.
   * Produces parity evidence vs online serving (e.g., matching snapshot hashes under the same `input_basis` + `graph_version`).

3. **Model Factory trains + produces evidence-backed bundles**

   * Treats DatasetManifests as immutable inputs; training runs are reproducible; outputs include evaluation evidence + (where required) gate receipts. 

4. **Registry is the only deployable truth**

   * MF publishes; Registry promotes/rolls back via governed lifecycle; resolution is deterministic (no “latest”).

5. **DF behavior shifts only via Registry activation**

   * DF resolves exactly one ActiveBundleRef per scope; compatibility with feature versions and degrade mask is enforced; DF records bundle ref in decision provenance. 

6. **New behavior creates new facts**

   * New decisions/actions/outcomes re-enter as EB facts → the loop continues.

### Where IEG fits (even opaque)

IEG influences learning only through **what was recorded at decision time**:

* decisions/audit record `graph_version used` (and, per P6 pin, the IEG projection generation/revision)
* offline reconstruction can rebuild the same context boundary deterministically from the admitted record + recorded bases

---

## #17 — L4 Backfill correction loop (ops reality without breaking explainability)

This is the ongoing “systems change over time” loop: schema evolves, bugs get fixed, retention changes, and you still must keep the platform explainable.

### The loop

1. **A drift/correction need is detected**

   * e.g., “IEG integrity degraded”, “feature definition changed”, “schema migration window”, “retention boundary changed”.

2. **A governed change is declared**

   * retention change / backfill execution / config activation / bundle rollout → all must emit governance facts (no silent changes).

3. **Backfill executes and regenerates derived outputs**

   * Can backfill: IEG projections, OFP state, offline datasets/manifests, audit indexes.
   * Cannot “backfill as truth mutation”: EB admitted events, label timelines, registry lifecycle history, SR run ledgers, immutable engine outputs.

4. **Cutover is explicit and explainability is preserved**

   * Old decisions remain explainable because they cite:

     * the bundle ref,
     * the feature snapshot hash + `input_basis`,
     * the `graph_version` (and the IEG projection generation/revision),
     * and the degrade posture used.
   * If you want “corrected decisions,” you don’t overwrite history — you run a **new replay/adjudication run** and produce new decision/audit artifacts with explicit lineage.

### Two “never allow” failure modes (production anti-drift rules)

* **Stealth overwrites** of derived outputs that change behavior without a trace. (Backfill must declare, outputs must be versioned/traceable.)
* **Time-travel semantics** where offsets/watermarks are reinterpreted. (Watermarks remain monotonic; historical rebuilds are by explicit basis.)

---

Yes — the **environment ladder is basically the “drift firewall” for every join/path/loop we just mapped**: it says *the platform meaning must not change*, only the **operational envelope** changes (scale/retention/security/reliability/observability), and promotion is **profile selection**, not “prod-only semantics.”

## What the environment ladder forces us to keep identical (across local/dev/prod)

These are the parts of the joins/paths/loops that **must not vary**, or you end up with “three different platforms”:

* **Same graph + trust boundaries:** IG is the front door; EB is the admitted fact log; IEG/OFP are EB consumers/projections; DL constrains DF; DLA is the flight recorder.
* **Same join semantics/rails:** ContextPins discipline, canonical envelope meaning, idempotency rules, watermarks (exclusive-next offsets), by-ref refs, append-only + supersedes, explicit degrade mask, deterministic registry resolution, as-of semantics.
* **Same meanings of the “big words”:** READY, ADMITTED, ACTIVE, BACKFILL, LABEL AS-OF must mean the same everywhere.
* **Same provenance obligations:** when DF/OFP uses IEG context it records the `graph_version`; when DF uses OFP snapshots it records `feature_snapshot_hash` + `input_basis`; DLA fails closed on incomplete provenance.

That’s the ladder’s core pin. 

## What is allowed to vary (and how it touches the joins/paths/loops)

These differences are **per-environment profiles** — they change *operational posture*, not meaning:

### 1) Retention + archive (changes which paths are “available,” not what they mean)

* **Local:** short retention (hours/days) → some long-horizon replays won’t be possible without re-running worlds.
* **Dev:** medium retention (days/weeks) → enough to exercise backfill/replay realistically.
* **Prod:** longer retention + **archive continuity** → supports offline rebuilds + investigations beyond retention.

Impacts:

* **P5 (learning/parity)** and **P6/L4 (backfill/rebuild)** become *more complete* as you move up the ladder, but the replay basis semantics don’t change.

### 2) Observability depth (changes thresholds + sampling, not correlation/meaning)

* Local can be “inspect-by-hand,” but **must still emit OTLP + lag/watermark metrics** so DL logic is real.
* Dev should have stable dashboards/alerts (even if low thresholds).
* Prod uses real SLOs/corridor checks; degrade triggers become meaningful.

Impacts:

* **L2 (Obs→DL→DF loop)**: same mechanism everywhere; only the *policy thresholds/profile* change.

### 3) Security strictness (changes policy, not join rules)

* Local may use permissive allowlists and dev creds, **but the IG/AL/Registry/Label boundary mechanisms must still exist** (so dev catches what prod would catch).
* Dev is where you catch: unauthorized producers, incompatible bundles, missing PASS evidence, quarantine access rules.
* Prod has strict authn/authz + change control.

Impacts:

* **J-IEG-IN-1 (EB→IEG)** doesn’t change, but **what IG admits** can be stricter in dev/prod via policy revisions (still audited).
* **P3 (DF→AL→outcomes)**: AL’s allowlists are stricter in prod, but intents still flow IG→EB and outcomes are still immutable.

### 4) Scale/reliability (changes deployment shape, not unit roles)

Local can collapse processes, but the ladder pins that the **deployment unit roles stay the same**: IEG is an always-on EB projector; OFP is an always-on projector+serve; DF/AL/DLA/DL/IG are always-on services; SR/Engine/Offline/MF/Backfill are jobs.

Impacts:

* **Paths/loops remain the same**, but in local you might run them as fewer processes; in dev/prod they’re independent services with real networking and durable dependencies.

## Specific “environment ladder notes” on the paths/loops we just expanded (#9–#17)

### P2 (DF calls IEG directly)

* **Local:** DF↔IEG may be in-process, but it must still behave like a real join: return `graph_version`, propagate trace context, expose query metrics.
* **Dev/Prod:** you validate *real failure modes*: IEG lag → DL disables IEG capability → DF obeys; that loop must be exercised in dev.

### P5 (learning/parity) + L3 (learning evolution loop)

* Ladder mainly changes **history horizon** (retention/archive) and **governance strictness** (approval gates), not the parity contract.

### P6/L4 (backfill correction loop)

* **Local:** you can run backfills easily, but they still must be **declared + produce governance facts** (even if approvals are trivial).
* **Dev:** is where you prove backfill mechanics and cutovers work end-to-end.
* **Prod:** change control + auditability become strict; every backfill/retention/config/bundle change is a recorded fact.

## The practical takeaway for our IEG design

When we finalize IEG’s joins, we must phrase them as **environment-invariant semantics**, and put all “environment differences” behind:

* **profiles** (policy revs, thresholds, allowlists, retention knobs), and
* **deployment envelope** (partition count, HA, sampling),
  never behind “if prod then do X.”

If you want, next we can explicitly pin the **IEG-relevant profile knobs** (the *allowed* environment differences): e.g., DL corridor thresholds for “IEG usable,” retention/archive availability that gates which replays/backfills are possible, and sampling/telemetry settings — while keeping every join/path/loop meaning identical.

---

Here’s what I want you to have **right now (while IEG is still opaque)**: the **environment-profile knobs** that are *allowed* to vary, plus the **deployment-direction anchors** that must stay invariant across local/dev/prod.

All of this follows your environment ladder pin: **same graph + same rails/join semantics everywhere; only the operational envelope changes** (scale, retention/archive, security posture, reliability posture, observability depth).

---

## 1) Deployment shape you should hold in your head for IEG (even while opaque)

* **IEG is a non-negotiable “always-on stream consumer / projector”** that consumes EB and maintains a derived graph projection + `graph_version` from applied offsets.
* It may be **paired with a query API**, but the “projector” role is the fixed production unit. 
* Local/dev/prod may *collapse units for convenience*, but **unit roles remain the same**.

---

## 2) Environment profile knobs for IEG (what may differ by env)

Think of these as “profile fields” (versioned config artifacts), not code forks.

### A) Scale & throughput knobs

* EB **partition count / concurrency** (how many partitions exist and how many workers/threads you run per consumer group).
* Batch sizes / in-flight limits / backpressure posture (operational tuning; semantics unchanged). 

### B) Retention, replay, archive knobs (critical for backfills + learning)

* **EB retention window** (local short, dev medium, prod long).
* **Archive enabled/disabled** and archive “horizon” (prod typically on; local may be off).
* Archive hydration posture (continuous vs scheduled) **but always verifiable**.
* Backfill/replay allowed windows + max parallelism (ops policy, not semantics).

### C) Reliability posture knobs

* Checkpoint durability (how aggressively you persist applied offsets / watermark basis).
* HA level (single instance local → multiple replicas in prod), plus backup/restore for the derived store.

### D) Security strictness knobs (same mechanisms, stricter policy)

* Authn/authz on the IEG query surface (none/dev creds locally → real auth in dev/prod).
* Topic ACLs / DB credentials separation per environment profile.

### E) Observability depth knobs (mechanism identical; sampling/thresholds differ)

* Trace sampling rate (local high; prod sampled) but **propagation semantics identical**.
* Log verbosity (debug in local, tighter in prod) while keeping structured boundary decisions.
* Metrics resolution + alert thresholds: IEG lag / watermark age / apply-failure rates / query latency.
* “Corridor checks” become real SLO gates in prod.

### F) Degrade Ladder policy knobs that depend on IEG (not inside IEG, but driven by IEG signals)

* Thresholds like “max IEG lag,” “max watermark age,” “integrity degraded flag present,” which DL uses to toggle **capabilities_mask** (e.g., “IEG usable” vs “disabled”).

### G) Backfill governance knobs (what approvals exist)

* Who can run backfills, what must be declared, what governance facts must be emitted.

---

## 3) Other deployment-direction info you should keep “loaded”

### A) Profiles and policy revs are first-class deployable artifacts

* Promotion is **environment-profile selection, not code branching**.
* Policy configs (thresholds, allowlists, acceptance rules) are **versioned artifacts**, and runtime components should report which `policy_rev` they’re on.

### B) Backfill/replay must stay declared + auditable

* Backfills are **never silent**; they declare scope/basis/outputs and emit governance facts.
* Watermarks remain monotonic; archive is the continuation of admitted facts.

### C) “Production-shaped local” matters for IEG specifically

So you actually feel the real failure modes (lag, duplicates, offsets, checkpoints), local should run a substrate stack with:

* Kafka-ish EB (partitions/offsets/consumer groups),
* SQL DB for derived store,
* OTLP pipeline for traces/metrics/logs.

---

## 4) The only IEG-specific “status surface” I’d want you to expect (even before we open the box)

This isn’t a spec—just a deployment anchor so ops/degrade/audit can work:

IEG should be able to report (somehow):

* current **`graph_version` basis** (or a summary) per run/world scope,
* lag / watermark age,
* integrity degraded flag (apply failures exist),
* build id + `policy_rev` + stream identity.

That’s what makes DL constraints and “why did we behave this way” explanations actually actionable in dev/prod.

---

Yep — before we “enter” IEG internals, here’s a **drift-checkpoint** of the **outer network contract** we’ve established for the IEG vertex (still treated as opaque), pulled back to **what must remain true** as we illuminate the inside.

---

## 0) The design-authoritative outer sources we’re obeying

* Platform topology + pinned connection points (ContextPins, join surfaces, watermarks, explicit degrade, etc.).
* Environment ladder + deployment units (IEG is an always-on projector; same semantics across envs).
* Canonical bus boundary schema (`CanonicalEventEnvelope`).
* Engine interface “laws” (no PASS→no read; business_traffic vs truth_products vs audit_evidence; byte-identical immutable outputs per identity).

Your IEG conceptual doc is *idea-pool*, but it usefully matches many pinned rails (envelope-first, graph_version basis, no merges), so we’ll treat it as a **consistency reference**, not authority.

---

## 1) IEG’s outer-role and authority boundary (non-negotiable)

**IEG is:** a **run/world-scoped projection** from **EB admitted events** that is authoritative only for:

* its projection artifacts (entities/edges/indices), and
* `graph_version` (applied-stream watermark token).

**IEG is not:** admission, world truth, feature computation, decisioning.

---

## 2) The complete outer join set for IEG (what we must not drift from)

### Mandatory joins

1. **J-IEG-IN-1: EB → IEG projector**

   * IEG consumes `fp.bus.traffic.v1` (admitted facts), at-least-once, duplicates/out-of-order possible.

2. **J-IEG-OUT-1: IEG → derived store**

   * Derived, rebuildable projection in DB schema `ieg` + applied offsets/checkpoints persisted for continuity.

3. **J-IEG-OUT-2A: DF ⇄ IEG query**

   * DF may call IEG directly; DF must record `graph_version used` in decision provenance (or record non-use).

4. **J-IEG-OUT-2B: OFP ⇄ IEG query**

   * OFP may call IEG as context; when it does, it must carry `graph_version` into snapshot provenance alongside its own `input_basis`.

5. **J-IEG-OPS-1: IEG → Obs/Gov pipeline**

   * IEG emits lag/watermark/health/integrity signals; DL uses obs signals to compute a deterministic mask that DF obeys.

6. **J-IEG-OPS-2: Run/Operate ⇄ IEG (rebuild/backfill)**

   * Backfills/replays are declared + auditable; rebuild derived state without rewriting truth.

### Optional join (allowed, not required)

7. **J-IEG-OUT-3: IEG → fp.bus.audit.v1 pointer events**

   * Optional pointer emissions (status/refs), but **no “second truth feed.”**

---

## 3) The pinned semantics that govern those joins (drift kill-switch list)

### GP-PIN-1: Scope is ContextPins

IEG state is isolated strictly by `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`.

### GP-PIN-2: Canonical envelope is the bus boundary

Events admitted to EB must be `CanonicalEventEnvelope` with required `{event_id, event_type, ts_utc, manifest_fingerprint}` and optional `{parameter_hash, seed, scenario_id, run_id}`.

### GP-PIN-3: Time semantics never collapse

For IEG: **domain event time = `ts_utc`**. (Your blueprint explicitly calls out the naming drift risk: “event_time/ingest_time” vs `ts_utc/emitted_at_utc`.)
**Drift guardrail:** inside IEG we can *name* it `event_time`, but it must be sourced from envelope `ts_utc`.

### GP-PIN-4: Envelope-driven updates require observed identifiers

The platform pins “envelope-driven updates for IEG require `observed_identifiers[]`.”
But the current canonical envelope schema does **not** include `observed_identifiers` (and forbids unknown top-level fields).
**So the outer-network truth we must preserve as we enter internals is:**
IEG must have access to a **normalized ObservedIdentifier list** without “domain payload interpretation.” (Whether it’s an envelope vNext field or a reserved payload block is a platform-level packaging choice we will pin when we start internals.)

### GP-PIN-5: Idempotency + duplicates are real

IEG must be replay-safe:

* `update_key = H(ContextPins + event_id + update_semantics_id)` (semantics id is pinned constant `ieg_update_semantics_v0`).
* duplicates → no-op; out-of-order → timestamp rules prevent corruption.

### GP-PIN-6: graph_version meaning is fixed

`graph_version` basis = **(stream_name + per-partition `next_offset_to_apply` watermark vector)**, where values are **exclusive-next offsets**.
Callers record graph_version used for audit/replay parity.

### GP-PIN-7: No merges in v0

IEG returns multiple candidates with conflict markers; it does not collapse entities.

### GP-PIN-8: No feature computation

IEG provides retrieval indices/projections only; OFP owns features.

### GP-PIN-9: Emissions posture

IEG does not emit “graph_version advanced” marker events onto EB in v0; graph_version is surfaced via queries (and telemetry/status).

### GP-PIN-10: Degrade is explicit and recorded

IEG signals feed DL; DL outputs `{mode, mask}`; DF obeys; DLA records — no silent coupling.

---

## 4) The outer paths/loops touching IEG (so we don’t “re-route” internally)

### Hot path routes

* EB → IEG → (OFP and/or DF) → decisions/actions → (IG→EB) → outcomes → back to EB consumers.

### Governance + learning loops

* Obs→DL→DF control loop (IEG contributes lag/health).
* Audit/parity loop: decisions record graph_version used; offline rebuild uses EB/Archive + label as-of and manifests/bundles; registry activation changes DF behavior.
* Backfill loop: declared replay/backfill rebuilds derived state without rewriting truth.

---

## 5) Drift risks we’ve identified (and the “don’t step on this rake” reminders)

1. **`event_time` vs `ts_utc` naming drift**
   Fix: inside IEG, treat `event_time := envelope.ts_utc`.

2. **`observed_identifiers[]` placement mismatch**
   Fix: pin a packaging rule (envelope vNext vs reserved payload block) before internal design depends on it.

3. **“Reject/quarantine” language at IEG boundary**
   Truth: IG quarantines; IEG can only (a) not mutate projection, (b) record apply failure + signal it.

4. **Changing graph_version meaning**
   Not allowed. Only encoding/token format is flexible, not the basis semantics.

---

## 6) The “outer network checklist” we will keep on screen while entering internals

When we design any internal module, it must answer “yes” to all of these:

* Does it preserve **ContextPins scoping**?
* Is it safe under **duplicates/out-of-order**?
* Does it keep **update_key** semantics intact?
* Does it keep **graph_version basis** as applied offsets (exclusive-next vector)?
* Does it avoid merges / avoid feature computation?
* Does it produce query responses that are **versioned + deterministic ordering** and recordable?
* Does it expose enough signals to support **explicit degrade**?
* Does it respect the environment ladder (same semantics; only profile knobs differ)?

---

Yep — one level deeper, **IEG-as-a-vertex decomposes into a small set of internal subnetworks** that collectively satisfy the outer joins (EB→IEG, IEG→store, DF/OFP↔IEG, ops, backfill). These subnetworks are **conceptual boxes**, not separate deployable components in v0 (you may run them as one process, or as “projector + query API” paired units; the projector role is non-negotiable).

## IEG Level-1 internal subnetworks (all opaque for now)

### S1) Projector Intake

**Purpose:** consume admitted events from EB and turn them into “candidate graph updates.”
**Owns:** EB consumer wiring, event classification, update_key derivation, identity-hints extraction/normalization.
**Why it must exist:** EB is at-least-once + partition-ordered only; IEG must be duplicate/out-of-order safe and envelope-driven.
**Key pinned dependencies:**

* update_key = H(ContextPins + event_id + pinned semantics id)
* “Envelope-driven updates for IEG require `observed_identifiers[]`” 
* canonical envelope fields (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, optional pins)

### S2) Scope Router

**Purpose:** enforce **run/world isolation**: every update/query is bound to a single ContextPins scope.
**Owns:** mapping from ContextPins → “which graph instance/state family is being touched.”
**Why it must exist:** the platform rail is explicit: anything run/world-joinable must carry ContextPins and must not leak across runs.

### S3) Idempotent Apply Coordinator

**Purpose:** perform an “apply unit” that is logically atomic: *either the update is applied once, or it’s a no-op/explicit failure — and graph_version never lies.*
**Owns:** update_key ledger checks, ordering rules for timestamps (domain time), apply failure recording, and when offsets/watermarks advance.
**Why it must exist:** J6 pins replay safety (update_key) and pins `graph_version` meaning as applied offsets.

### S4) Canonical Identity Subnetwork

**Purpose:** maintain canonical `EntityRef`s and alias/link mappings from observed identifiers (links/aliases only; no merges).
**Owns:** deterministic entity_id minting posture; alias/index semantics; conflict posture (multiple candidates).
**Why it must exist:** IEG is “identity context” first; downstream needs deterministic resolution and explainable conflicts.

### S5) Relationship / Edge Subnetwork

**Purpose:** maintain entity relationships as edges, with disorder-safe timestamp rules and provenance.
**Owns:** edge identity and timestamp update rules; provenance_ref creation (typically EB position).
**Why it must exist:** your pinned behavior requires edges be attributable and safe under out-of-order delivery.

### S6) Projection Indices Subnetwork

**Purpose:** build the read-optimized indices/projections that make queries fast and deterministic (neighbors, identifier lookups, filtered edge retrieval).
**Owns:** “how do we answer resolve/profile/neighbors efficiently and with stable ordering?”
**Why it must exist:** IEG is a read-mostly context plane; DF/OFP need low-latency queries with deterministic ordering.

### S7) Versioning & Lineage Subnetwork

**Purpose:** own progress truth: checkpoints and `graph_version` basis (and lineage around rebuild/backfill).
**Owns:** per-partition exclusive-next offsets (watermark basis), graph_version computation, projection integrity status (e.g., apply failures exist), and (optionally) a projection generation id for rebuild cutovers.
**Why it must exist:** `graph_version` meaning is pinned as (stream_name + applied-offset watermark vector).

### S8) Serving & Ops Facade

**Purpose:** expose the only “externally touchable” IEG surfaces: query API (DF/OFP), status/health, and observability emissions.
**Owns:** query boundary invariants (ContextPins + graph_version always present), explicit ErrorResponse posture, telemetry (lag/watermark/integrity), and the control-plane hook used by backfill/replay jobs.

---

## One-screen internal adjacency (still opaque boxes)

```text
EB admitted events
      |
      v
 [S1 Projector Intake] ---> [S2 Scope Router]
      |                         |
      v                         v
 [S3 Idempotent Apply Coordinator]  (update_key, failure posture, when to advance)
      |                 \
      |                  \--> [S7 Versioning & Lineage] (watermarks -> graph_version)
      v
 +------------------------------+
 |   Graph state mutation plane |
 |  [S4 Canonical Identity]     |
 |  [S5 Relationship / Edges]   |
 +------------------------------+
      |
      v
 [S6 Projection Indices]
      |
      v
 [S8 Serving & Ops Facade]  <---->  DF / OFP (queries; returns ContextPins + graph_version)
      |
      +----> Obs/Gov (telemetry: lag, watermark age, integrity)
      |
      +<---- Run/Operate backfill/replay (declared rebuilds; cutovers)
```

---

## Why this is the “right” level-1 cut (drift prevention)

* Every pinned outer join has a **single internal owner**:

  * **EB→IEG** safety: S1/S3/S7
  * **IEG→store** durability: S4/S5/S7 (derived but checkpointed)
  * **DF/OFP queries**: S8 backed by S6/S7
  * **Degrade/ops/backfill**: S8/S7 (signals + explicit rebuild lineage)

---

Absolutely. Staying **one level deep** (S1–S8 still opaque), here’s the **production internal join map** for IEG: the **joins (edges/handshakes)**, the **paths (multi-hop flows)**, and the **loops (cycles / feedback)** that must exist for the vertex to satisfy the outer network without drift.

I’m going to treat the **derived store substrate** as an internal boundary node too (call it **ST**), because in production it’s the thing every internal path touches.

---

## Internal nodes in scope (still opaque)

* **S1 Projector Intake**
* **S2 Scope Router**
* **S3 Idempotent Apply Coordinator**
* **S4 Canonical Identity**
* **S5 Relationships / Edges**
* **S6 Projection Indices**
* **S7 Versioning & Lineage**
* **S8 Serving & Ops Facade**
* **ST Derived Store + Checkpoints** (DB + durability surface)

---

## A) Internal joins (the complete edge set)

### A1) Ingest-and-apply spine (mandatory)

1. **J-IEG-1:** `S1 → S2` (scope extraction + routing keying)
2. **J-IEG-2:** `S2 → S3` (scoped “candidate update” handed to apply coordinator)
3. **J-IEG-3:** `S3 → S4` (identity mutations: entities/aliases/indexable identity facts)
4. **J-IEG-4:** `S3 → S5` (relationship mutations: edges / link facts)
5. **J-IEG-5:** `S4 ↔ S5` (endpoint canonicalization + existence/refs; edges depend on entity refs)
6. **J-IEG-6:** `S4,S5 → S6` (index maintenance/update materialization)
7. **J-IEG-7:** `S3 ↔ S7` (apply outcome ↔ watermark + integrity + graph_version basis)
8. **J-IEG-8:** `S3,S4,S5,S6,S7 → ST` (durable commit/read boundary)

> These eight are the “minimum viable internal network” for a production projector: without them you can’t guarantee idempotency, ordering safety, indices, or truthful graph_version.

---

### A2) Query/serve plane (mandatory)

9. **J-IEG-9:** `S8 ↔ S6` (read path uses indices; deterministic ordering/shape)
10. **J-IEG-10:** `S8 ↔ S7` (attach `graph_version` + integrity status; optional min-basis checks)
11. **J-IEG-11:** `S6 ↔ ST` (index-backed reads)
12. **J-IEG-12:** `S7 ↔ ST` (checkpoint/watermark basis reads + durability)

> This plane is what makes DF/OFP calls stable: **responses are always pinned to a version basis** (S7) and are **fast/deterministic** (S6).

---

### A3) Ops/telemetry plane (mandatory)

13. **J-IEG-13:** `S7 → S8` (progress + integrity summary exposed at the facade)
14. **J-IEG-14:** `S8 → Obs pipeline` (metrics/logs/traces emission boundary)
15. **J-IEG-15:** `S8 → S1/S3` (backpressure controls: throttle/pauses/resumes; optional but production-real)

> Even if backpressure is “simple,” a control edge exists in production because saturation/lag must be survivable.

---

### A4) Backfill/rebuild plane (mandatory in prod readiness)

16. **J-IEG-16:** `Run/Operate → S8` (declared replay/backfill command enters IEG boundary)
17. **J-IEG-17:** `S8 ↔ S7` (create/activate a **projection generation** + replay basis; cutover semantics)
18. **J-IEG-18:** `S7 → S1` (consumer start position / replay basis fed into intake)
19. **J-IEG-19:** `S8 ↔ ST` (generation cutover / maintenance mode / read routing)

> This is the internal shape that makes “derived & rebuildable” true in practice, rather than aspirational.

---

### A5) Optional pointer emission plane (allowed, not required)

20. **J-IEG-20:** `S7/S8 → pointer emitter` (rate-limited milestone facts)
    *(If you enable J-IEG-OUT-3 at the vertex boundary.)*

---

## B) Internal paths (production flows through the internal network)

### P-INT-1 — Normal graph-mutating apply (happy path)

`S1 → S2 → S3 → (S4 + S5) → S6 → ST`
with `S3 ↔ S7` producing watermark advancement and version basis.

### P-INT-2 — Duplicate event (idempotent no-op, still progresses)

`S1 → S2 → S3 (detect update_key already applied) → S7 (advance offsets) → ST`
*(No S4/S5 mutation; indices unchanged.)*

### P-INT-3 — Graph-irrelevant event (intentional no-op)

`S1 → S2 → S3 (class=irrelevant) → S7 (advance offsets) → ST`

### P-INT-4 — Invalid-for-mutation (apply failure recorded)

`S1 → S2 → S3 (record failure + integrity degraded) → S7 → ST`
*(Still progresses offsets; integrity signal becomes part of version/health surfaces.)*

### P-INT-5 — Query: resolve_identity

`S8 → S6 → ST` + `S8 → S7` (attach graph_version + integrity) → response

### P-INT-6 — Query: neighbors/profile

Same shape as P-INT-5, just different index accesses:
`S8 → S6 → ST` + `S8 → S7` → response

### P-INT-7 — Status/health (ops read)

`S8 → S7 → ST` (+ optional S1 lag stats) → health payload + telemetry

### P-INT-8 — Rebuild/backfill replay (declared, auditable)

`Run/Operate → S8 → S7 (new generation + basis) → S1 (replay start) → … (P-INT-1/2/3/4 repeated) … → S7 (completion checkpoint) → S8 (cutover)`

---

## C) Internal loops (cycles / feedback that exist in production)

### L-INT-1 — Continuous projector loop (steady-state)

IEG is fundamentally a loop: “consume → apply → checkpoint → consume …”
`S1 → S2 → S3 → ST → S7 → (feeds back into) S1`
*(The feedback is: checkpoints/watermarks determine resume/rebalance behavior.)*

### L-INT-2 — Restart/rebalance loop (durability truth)

On restart or partition rebalance, intake must resume from checkpoint basis:
`S7 → S1` (resume position) → `S1…S7` (re-establish current)

### L-INT-3 — Integrity degradation loop (explicitly surfaced)

`S3 records apply-failure → S7 integrity flag → S8 surfaces/telemeters → (external DL constrains DF) → query load/usage changes`
*(The external DL part is outside the vertex, but the internal loop is “failure → integrity surfaced,” which must exist.)*

### L-INT-4 — Backpressure loop (survivability)

`ST/S7 detect saturation or lag → S8 issues throttle/pause → S1/S3 reduce intake → lag stabilizes → resume`
*(Mechanism can be simple; the loop exists in real systems.)*

### L-INT-5 — Rebuild/cutover loop

`Run/Operate → S8 → S7 (new generation) → S1 replay → S7 completion → S8 cutover → continue steady-state`

---

## One compact internal adjacency sketch (still opaque)

```text
Ingest spine:
S1 -> S2 -> S3 -> (S4 <-> S5) -> S6 -> ST
             \-> S7 <-> ST
Serve plane:
S8 <-> S6 <-> ST
S8 <-> S7 <-> ST
Ops/backfill:
Run/Operate -> S8 <-> S7 -> S1
S8 -> Obs  (telemetry)
S8 -> S1/S3 (throttle/pause/resume; optional but real)
```

---

Locked. We’ll **illuminate A1 (the ingest-and-apply spine)** by defining the **internal joins J-IEG-1 … J-IEG-8** as *production handshakes* between opaque subnetworks, and I’ll **pin** what is “in-bounds” vs “out-of-bounds” for the vertex boundary as we go.

Before the per-join deep dive, I’m pinning **three spine laws** (these govern all A1 joins):

## A1 Spine Laws (authoritative for this brainstorm)

**A1-LAW-1 — Offset truth is sacred**
Per EB partition, IEG processes offsets in order; **`next_offset_to_apply` is exclusive-next**. `graph_version` advances when an offset is *processed* (applied / no-op / invalid recorded), not only when it mutates graph state.

**A1-LAW-2 — Apply is logically atomic**
For a given `(scope, partition, offset)` the system must end in exactly one durable outcome:

* `APPLIED`, `DUPLICATE_NOOP`, `IRRELEVANT_NOOP`, or `INVALID_RECORDED`
  …and **watermarks must never get ahead** of what the derived store can justify.

**A1-LAW-3 — Identity is “no-merge” and payload-blind**
S4 never merges entities. The spine may only use a **normalized identity-hints block** (your `observed_identifiers[]` concept) and must not rely on business payload semantics. If identity hints are missing for an identity-relevant event, that is not “fixed” inside IEG — it becomes `INVALID_RECORDED` for that offset.

---

# A1.1 — J-IEG-1: **S1 → S2** (scope extraction + routing keying)

### Purpose

Turn an EB-delivered record into a **NormalizedEvent** that is:

* syntactically valid enough to reason about,
* **scopable** (ContextPins extracted), and
* **identity-hints normalized** (without semantic payload parsing).

### Input to S1 (conceptual)

`EBRecord = {stream_name, partition_id, offset, envelope_bytes}`

### Output from S1 to S2 (conceptual)

`NormalizedEvent` (minimum fields):

* `stream_name, partition_id, offset`
* `event_id, event_type, ts_utc`
* `context_pins?` (may be missing)
* `identity_hints?` (may be missing)
* `classification_hint` (identity-relevant? maybe/yes/no)
* `parse_status` (OK | MALFORMED)

### What S1 is allowed to do (in-bounds)

* Envelope parsing + minimal schema sanity (required envelope fields).
* Extract ContextPins if present.
* Extract identity hints from a **single standardized location**.

### What S1 is NOT allowed to do (out-of-bounds)

* Interpret business payload semantics (“merchant”, “device”, “ip”, etc.) beyond reading the standardized identity-hints block.
* Perform cross-event correlation (that’s not intake).

### **Design authority pin (resolving a known boundary tension)**

Because the canonical envelope doesn’t currently carry `observed_identifiers[]` at top-level, S1 must support **one normalized “identity hints block”** that can be obtained in either of these packaging modes:

* **Mode A (future)**: envelope vNext provides it at top-level
* **Mode B (v0 bridge)**: a *reserved* payload subfield that is strictly standardized (not “free parsing”)

**Either way, S1 outputs the same internal `identity_hints` structure.** Missing hints on an identity-relevant event is handled later as `INVALID_RECORDED` (not as “we guess”).

---

# A1.2 — J-IEG-2: **S2 → S3** (scoped candidate update handed to apply coordinator)

### Purpose

Bind the event to a **single graph scope**, and hand it to the apply coordinator in a way that preserves:

* per-partition ordering (offset monotonicity),
* run/world isolation, and
* determinism.

### Input to S2

`NormalizedEvent` from S1.

### Output to S3

`ScopedCandidate = {scope_key, stream_name, partition_id, offset, event_id, event_type, ts_utc, identity_hints?, classification_hint, parse_status}`

Where:

* `scope_key := {scenario_id, run_id, manifest_fingerprint, parameter_hash}`
* If pins are incomplete, `scope_key := NONE` (explicitly unscoped)

### What S2 must enforce (in-bounds)

* **No cross-scope leakage:** an event either maps to exactly one `scope_key`, or it is explicitly unscoped.
* **No re-ordering within a partition:** S2 must not deliver offset N+1 before N for the same partition to S3.

### What S2 must NOT do (out-of-bounds)

* Apply idempotency decisions (that belongs to S3/S7).
* Create entities/edges (that’s S4/S5).

### Pin: how “unscoped” is handled

If a record lacks ContextPins, it can’t safely mutate a run/world graph.
So S2 passes it along as `scope_key=NONE`, and **S3 must process it as `INVALID_RECORDED` or `IRRELEVANT_NOOP`**, but still advance offsets (A1-LAW-1). No stalling.

---

# A1.3 — J-IEG-3: **S3 → S4** (identity mutations)

### Purpose

Transform identity hints into **canonical identity state** updates:

* canonical entities (`EntityRef`)
* identifier aliases / claims
  without merges, and deterministically.

### Input to S4 (conceptual)

`IdentityMutationRequest`:

* `scope_key`
* `update_key` (computed by S3; see A1.7)
* `event_id, event_type, ts_utc`
* `identity_hints` (normalized)
* `provenance_ref` (stream/partition/offset)

### Output from S4

`IdentityMutationResult`:

* `resolved_entities`: mapping from each identity hint group → **0..N EntityRef candidates**
* `new_entities_created`: list (if minting occurred)
* `alias_updates_applied`: what identifier→entity assertions were added/updated
* `conflicts`: explicit conflict set(s) when N>1
* `status`: OK | INSUFFICIENT_HINTS | ERROR

### Pinned behavior (design authority)

* **No merges.** S4 may:

  * return multiple candidates, and/or
  * mint a new entity deterministically if resolution yields none, *but only when hints are sufficient to do so*.
* If identity hints are missing/insufficient for an identity-relevant event: **S4 returns `INSUFFICIENT_HINTS`**; S3 converts that into `INVALID_RECORDED` (not guessed identity).

---

# A1.4 — J-IEG-4: **S3 → S5** (relationship mutations)

### Purpose

Apply edges/relationships based on resolved canonical entity references, safe under duplicates and disorder.

### Input to S5

`EdgeMutationRequest`:

* `scope_key`
* `update_key`
* `edge_facts` (edge_type + endpoint EntityRefs or endpoint sets)
* `ts_utc` (domain time basis)
* `provenance_ref` (stream/partition/offset)

### Output from S5

`EdgeMutationResult`:

* `edges_upserted`
* `edge_conflicts` (if endpoint ambiguity prevents applying certain edges)
* `status`: OK | PARTIAL | ERROR

### Pin: “ambiguous endpoints” posture

If S4 returned multiple candidates for an endpoint:

* **v0 safe rule:** S5 does **not** guess.
* Edge apply can either:

  * **skip** edges requiring ambiguous endpoints (record as a conflict artifact), or
  * represent ambiguity explicitly (more complex).

**My design authority choice for v0:** **skip-and-record** (deterministic, explainable, avoids accidental wrong linking). That keeps the projection conservative and avoids silent false joins.

---

# A1.5 — J-IEG-5: **S4 ↔ S5** (endpoint canonicalization dependency)

### Purpose

Ensure edges never reference non-existent / non-canonical endpoints, and keep ownership clean.

### Pin: ownership boundary

* **S4 is the only place allowed to mint/own EntityRefs.**
* **S5 is not allowed to create entities.**

So the practical rule is:

* S3 must call S4 first (or otherwise obtain EntityRefs) before asking S5 to write edges.
* If S5 receives an EntityRef that doesn’t exist (shouldn’t happen), that’s an apply error, not an auto-create.

This makes drift impossible: relationship state cannot silently invent identity state.

---

# A1.6 — J-IEG-6: **S4,S5 → S6** (index maintenance / materialization)

### Purpose

Maintain the read-optimized projections that power deterministic queries (resolve/profile/neighbors) at low latency.

### Input to S6

`IndexDelta` derived from identity + edge mutation outcomes:

* identifier index changes
* entity profile view changes
* adjacency/neighbor index changes

### Output from S6

* `index_update_receipt` (what index partitions advanced)
* optional `index_watermark` (if you track index freshness separately)

### Pin: “what queries are allowed to see”

Query responses must be consistent with the returned `graph_version`. There are only two acceptable designs:

1. **Synchronous indices (simpler v0)**
   Indices update inside the same apply unit, so they’re always caught up when `graph_version` advances.

2. **Asynchronous indices (allowed, but must be gated)**
   If indices lag, then S7/S8 must ensure served `graph_version` never exceeds **index freshness** (serve min(graph_watermark, index_watermark)).

**My v0 design authority choice:** default to **(1) synchronous indices** unless you *need* async for throughput. It’s the lowest drift risk when we later plug DF/OFP latency expectations.

---

# A1.7 — J-IEG-7: **S3 ↔ S7** (apply outcome ↔ watermark + integrity + graph_version basis)

### Purpose

Make `graph_version` truthful and monotonic, and define exactly what “processed” means.

### Key objects

* `update_key := H(scope_key + event_id + ieg_update_semantics_v0)`
  (S3 computes; S7 stores “applied/seen” state by partition and/or update ledger).

### S3 → S7 (ApplyOutcome)

For every offset, S3 emits exactly one outcome:

* `classification`: APPLIED | DUPLICATE_NOOP | IRRELEVANT_NOOP | INVALID_RECORDED
* `scope_key` (or NONE)
* `partition_id, offset`
* `update_key` (if scope exists)
* `integrity_notes` (apply failure reasons / conflict summary)
* `event_ts_utc` (optional, for watermark-age metrics)

### S7 → S3 (ApplyGuard / ResumeBasis)

* current `next_offset_to_apply` for that partition
* any “pause/maintenance” flags (if rebuild is running)
* replay basis (when backfill cutover is active)

### Pins (most important part)

* **Offsets advance on *processing*, not only on mutation.**
  Even INVALID or IRRELEVANT offsets move the partition watermark forward (with integrity flagged as needed).
* **Integrity is explicit.**
  Apply failures (e.g., missing identity hints) set an integrity flag that is surfaced to S8 and telemetry.
* **No lying versions.**
  S7 must never publish a basis that claims offsets were processed if the store doesn’t reflect that durable outcome.

---

# A1.8 — J-IEG-8: **S3,S4,S5,S6,S7 → ST** (durable commit/read boundary)

### Purpose

Make the apply unit durable and restart-safe.

### What ST must durably hold (minimum)

Per `scope_key`:

* identity state (entities + aliases)
* edge state
* indices (or base tables sufficient to derive them)
* update ledger (at least “applied update_key”)
  Per partition:
* `next_offset_to_apply` (exclusive-next)
* integrity markers / apply-failure summary
  Optionally:
* projection generation id / cutover lineage

### The “Apply Unit” (atomicity requirements)

For a given `(partition, offset)` the following must become durable *together* in a coherent way:

* update outcome classification (applied/no-op/invalid)
* any identity/edge/index mutations (if applied)
* update_key ledger mark (if scoped)
* `next_offset_to_apply := offset+1`
* integrity updates

**How** you implement atomicity (single DB tx vs WAL + idempotent steps) is implementer freedom.
**What** must be true after crashes is pinned:

* No double-apply when replaying the same offset.
* No `graph_version` that implies mutations which aren’t durable.
* No “lost” offsets: either processed and advanced, or not processed and retried.

---

## A1 “golden pipeline” sequence (canonical, drift-resistant)

For each EB record `(p,o)`:

1. S1 parses envelope + normalizes identity_hints (or marks missing), emits NormalizedEvent
2. S2 binds to scope_key (or NONE), emits ScopedCandidate
3. S3 checks resume basis with S7 (expects next offset)
4. S3 computes update_key (if scoped) and decides classification
5. If APPLIED: S3 calls S4 then S5, then S6 (per v0 sync indices)
6. S3 emits ApplyOutcome to S7
7. ST commit makes mutations + ledger + watermark durable
8. Next offset begins

---

Great — we’ll illuminate **A2 (Query/Serve plane)** at the same “one-level-deeper” granularity: define the **internal joins J-IEG-9 … J-IEG-12** as production handshakes between still-opaque subnetworks **S8/S6/S7/ST**, and pin the invariants so we don’t drift when we later open the boxes.

I’m going to start by pinning the **A2 Plane Laws** (they apply to all four joins), then expand each join.

---

## A2 Plane Laws (authoritative for this brainstorm)

### A2-LAW-1 — Every query response is versioned and explainable

If IEG answers a query, the response must carry:

* the **scope key** (ContextPins), and
* a **truthful `graph_version`** (plus integrity status).

If IEG cannot answer correctly, it must return an **explicit error** (retryable or not), never silent fallback.

### A2-LAW-2 — “No lying snapshots”

The **data returned** by S6 must be consistent with the **basis** S7 attaches (the returned `graph_version`).
Implementation details are free (transaction snapshots, MVCC, staged reads), but the observable truth is pinned:

> IEG must not return a graph_version that implies context it did not actually use to answer.

### A2-LAW-3 — Deterministic shape and ordering

For the same inputs + same basis, the response must be byte-stable:

* deterministic ordering,
* deterministic pagination,
* no “current time” dependence.

### A2-LAW-4 — Reads are side-effect free

The query plane **never mutates** identity/edges/indices/watermarks. It may emit telemetry, but it does not “fix” projection issues.

---

# A2.9 — J-IEG-9: **S8 ↔ S6**

*(Serving façade orchestrates ↔ projection indices execute reads)*

## Purpose

This join is the **query execution contract**: S8 validates/orchestrates; S6 performs the actual read work against indices/base read models.

## What crosses this join

### S8 → S6: `QueryIntent`

A normalized request that is already:

* syntactically valid,
* scoped,
* bounded (limits, depth), and
* annotated with the selected **serve basis** (or a handle representing it).

Minimum fields:

* `op`: `resolve_identity | get_entity_profile | get_neighbors`
* `scope_key`: ContextPins
* `params`: (depends on op)

  * `resolve_identity`: observed identifiers input (already normalized)
  * `profile`: `EntityRef`
  * `neighbors`: `EntityRef` + optional filters (`edge_type`, `direction`, `depth=1`, `limit`)
* `serve_consistency`: `STRICT | BEST_EFFORT`
* `serve_snapshot`: **read snapshot handle** or **basis token** (from S7 via J-IEG-10)
* `limits`: `max_results`, `max_depth` (v0 depth pinned to 1)
* `pagination`: `page_token` (optional)

### S6 → S8: `QueryResultData`

* `results`: entities / edges / candidate lists
* `conflicts`: explicit “ambiguity present” indicators (because no-merge)
* `paging`: `next_page_token` (deterministic)
* `read_stats`: (optional) “how much work” info for telemetry

## Responsibility split (drift guard)

**S8 owns:**

* input validation + shape enforcement
* scope enforcement
* selecting consistency mode (STRICT vs BEST_EFFORT)
* attaching `graph_version` + integrity status (via S7)
* turning internal failures into explicit client errors

**S6 owns:**

* deterministic query execution
* deterministic ordering + deterministic pagination
* *no* responsibility for choosing `graph_version` (that’s S7)

## Hard pins for this join

* S6 must never return “random order” results; it must produce stable ordering.
* S6 must not silently drop ambiguity; it must return conflicts when multiple candidates exist.
* S8 must not “invent” a graph_version; it must come from S7.

---

# A2.10 — J-IEG-10: **S8 ↔ S7**

*(Serving façade ↔ versioning/lineage: basis selection, integrity gating, min-basis checks)*

## Purpose

This join decides **what basis we are serving at**, and whether the request is allowed under:

* minimum basis requirements,
* integrity requirements,
* maintenance/rebuild state.

This is the “truth stamp” join.

## What crosses this join

### S8 → S7: `ServeBasisRequest`

Minimum fields:

* `scope_key`
* `request_mode`: `STRICT | BEST_EFFORT`
* `min_graph_version?`: optional constraint (caller wants “at least this up-to-date”)
* `require_integrity_clean?`: optional constraint
* `require_scope_active?`: default true (no serving for unknown/uninitialized scope)
* `snapshot_hint?`: if S8 has already opened a DB read snapshot handle, it passes it here so S7 reads basis *from the same snapshot*.

### S7 → S8: `ServeBasisDecision`

Fields:

* `decision`: `OK | LAGGING | INTEGRITY_DEGRADED | SCOPE_UNKNOWN | REBUILDING | MAINTENANCE | INTERNAL_ERROR`
* `retryable`: bool
* `serve_graph_version`: the token to return (plus “basis hash” if you don’t want to expose the full vector)
* `integrity_status`: `CLEAN | DEGRADED | UNKNOWN`
* `projection_generation_id`: stable id for current projection generation (important for backfill cutovers)
* `basis_age / lag_summary`: (optional) “how stale” indicators for telemetry / for callers to log

## Hard pins for this join

### Pin: min-basis is supported (even if most callers won’t use it)

S8 may accept a `min_graph_version` constraint from DF/OFP (“don’t serve if too stale”).
S7 is the only place that compares basis tokens.

### Pin: integrity gating is explicit

If `require_integrity_clean=true` and integrity is degraded, S7 returns `INTEGRITY_DEGRADED` (retryable depends on whether rebuild is in progress).

### Pin: “serve basis” must be honest and stable

S7 must return a basis that corresponds to **durable projection state**, not a speculative in-memory watermark.

### Recommended v0 default (design authority)

* Default `request_mode = BEST_EFFORT` for most calls, but **always include integrity status**.
* DF’s policy can choose to treat degraded integrity as “hard error” via DL mask, not via IEG lying/guessing.

---

# A2.11 — J-IEG-11: **S6 ↔ ST**

*(Indices ↔ derived store for index-backed reads)*

## Purpose

This join is the actual **data retrieval** boundary. S6 uses ST’s read models (indices / base tables) to answer queries.

## The central production concern: consistency

Because the projector can be writing while queries are reading, this join must satisfy:

> The query must read a state that is consistent with the `serve_graph_version` S7 will attach.

### How we pin this without over-specifying implementation

We don’t dictate DB tech, but we **do** dictate the observable semantics:

**Requirement:** S6 must execute reads in a way that corresponds to a **stable read snapshot** (explicit handle or an equivalent mechanism), so that:

* “neighbors list” isn’t half old/half new,
* pagination doesn’t drift across pages,
* ordering isn’t affected by concurrent writes.

**Allowed implementation strategies (implementer freedom):**

* open a DB transaction at repeatable-read / snapshot isolation and run the query in it,
* use MVCC read timestamps,
* use “basis gating” where each row carries a committed watermark/generation marker.

We don’t pick the method; we pin the outcome.

## Deterministic ordering rules (v0 pin)

To prevent “random order” and pagination drift:

* **resolve_identity** returns candidates sorted by:

  1. `entity_type` (stable enum order),
  2. `entity_id` (lexicographic),
  3. then any stable tie-breakers (e.g., first_seen_ts_utc, last_seen_ts_utc) if you expose them.

* **get_neighbors** returns edges sorted by:

  1. `edge_type`,
  2. `neighbor_entity_type`,
  3. `neighbor_entity_id`,
  4. `first_seen_ts_utc`,
  5. `last_seen_ts_utc`,
  6. `provenance_ref` (as final stable tiebreaker).

* **profile** is a single record: deterministic.

(These are ordering pins, not schema pins.)

## Pagination pin

If a query supports paging, `page_token` must encode a stable resume point tied to:

* `scope_key`,
* `serve_basis` (or generation id),
* and the last item’s ordering keys.

If the caller retries with the same token, they must get the same continuation.

---

# A2.12 — J-IEG-12: **S7 ↔ ST**

*(Versioning/lineage ↔ derived store for checkpoints, integrity, generation)*

## Purpose

This join is where S7 obtains (and persists, in other planes) the **ground truth** for:

* per-partition `next_offset_to_apply` (exclusive-next),
* integrity markers / apply-failure summaries,
* the active `projection_generation_id`,
* optional index freshness (if you ever go async).

For A2 (query/serve), we care primarily about **reads** from ST.

## What S7 must read from ST to serve queries

For a given `scope_key`:

1. **Serve basis**

* The basis token derivable from:

  * stream identity, and
  * per-partition `next_offset_to_apply` vector.

2. **Integrity status**

* `CLEAN` if no known apply failures exist for the relevant basis/generation.
* `DEGRADED` if apply-failures exist (and S8 must surface this).

3. **Projection generation**

* The stable id of the current active projection generation.
* Needed to keep explainability across rebuilds/cutovers.

4. **Maintenance/rebuild flags**

* If backfill/rebuild is active, S7 can return `REBUILDING/MAINTENANCE` decisions.

## The critical pin: basis must match what’s durable

S7 may cache in memory for performance, but its returned basis must reflect **durable committed** state, not speculative progress.

Environment knobs can tune cache TTL and refresh frequency, but not the semantics.

---

## The canonical query execution path (how these joins compose)

This is the “no drift” internal path for any query:

1. **S8 validates request** and extracts `scope_key` + op + params.
2. **S8 obtains a read snapshot handle** from ST (or equivalent).
3. **S8 asks S7 (J-IEG-10)** for `ServeBasisDecision` *using the same snapshot handle*.

   * If decision is not OK → explicit error.
4. **S8 asks S6 (J-IEG-9)** to execute the query *in that same snapshot*.
5. **S8 returns response**:

   * results (from S6),
   * `graph_version` + `projection_generation_id` + `integrity_status` (from S7),
   * deterministic ordering + stable pagination.

This is how we guarantee A2-LAW-2 (“no lying snapshots”) without forcing a specific DB or locking strategy.

---

## Error taxonomy (what S8 should surface outward)

We keep this consistent with your platform’s explicit-degrade mindset:

* `SCOPE_UNKNOWN` (non-retryable unless caller expected late activation)
* `LAGGING` (retryable=true; include current graph_version)
* `INTEGRITY_DEGRADED` (retryable depends; include integrity status + current version)
* `REBUILDING/MAINTENANCE` (retryable=true; include “when to retry” hint if available)
* `INVALID_REQUEST` (retryable=false)
* `INTERNAL_ERROR` (retryable maybe; log correlation keys)

---

## Two design authority decisions for v0 (to reduce drift later)

1. **Queries are “current basis” only (no as-of semantics in IEG v0).**
   Callers can enforce minimum freshness via `min_graph_version`, but they cannot ask IEG to time-travel.

2. **Synchronous index freshness is the default.**
   So `graph_version` is both “projection applied basis” and “queryable basis.”
   If you later choose async indices, we add an `index_basis` concept and serve `min(projection_basis, index_basis)` — but we do not complicate v0 unless needed.

---

Yep. **A3 is the “ops truth + survivability” plane** inside IEG: it’s how the vertex stays *observable, governable, and self-protecting* in production without changing the platform semantics (the environment ladder rule: **same meaning everywhere; only thresholds/knobs vary**).

Below are **A3.13 → A3.15** as internal joins between still-opaque boxes.

---

## A3.13 — J-IEG-13: **S7 → S8**

### Progress + integrity summary exposed at the façade

### Why this join exists

S7 is the **only internal authority** for “how far IEG has truthfully processed” and “is the projection integrity compromised.” S8 is the **only place** allowed to expose that outward (queries, status, telemetry). This join prevents two drift failures:

* S8 inventing/guessing a `graph_version`
* S7 being bypassed by “helpful” status code elsewhere

### S7 → S8: `ProjectionStatusFrame` (conceptual payload)

This is the *canonical* internal “status snapshot” S8 can use for:

* query responses (attach `graph_version` + integrity),
* health endpoints,
* telemetry emission,
* backpressure decisions.

Minimum fields:

**Identity**

* `stream_name` (the traffic stream identity)
* `projection_generation_id` (stable id that changes on rebuild/cutover)
* `scope_dimension`: `global | per_scope` (see below)

**Progress**

* `graph_version_basis` (the per-partition `next_offset_to_apply` vector, or a digest + optional sampled vector)
* `basis_digest` (compact stable hash of the basis vector)
* `watermark_age_seconds` (how stale the newest processed domain time is, per partition or aggregated)
* `consumer_lag` (optional if computed in S1; S7 can carry the last-known summary)

**Integrity**

* `integrity_status`: `CLEAN | DEGRADED | UNKNOWN`
* `apply_failures_present`: bool
* `failure_summary`: counts by reason (`missing_pins`, `missing_id_hints`, `malformed`, `apply_error`, `index_error`)
* `first_failure_at` / `last_failure_at`: EB position refs (partition/offset) (no payload)
* `integrity_reset_basis`: if integrity became clean only due to rebuild/backfill, record the cutover id

**Serving constraints**

* `maintenance_mode`: `NONE | REBUILDING | PAUSED | DRAINING`
* `readiness_flags`:

  * `projector_ready` (can consume/apply)
  * `query_ready` (can serve A2 queries)
  * `integrity_ok_for_strict` (a convenience bit for S8 to enforce strict mode)

### The crucial pin (what S8 is allowed to do with this)

* S8 may **present**, **summarize**, and **attach** these fields.
* S8 may **not compute an alternative truth**. If S8 needs “current graph_version”, it calls S7.

### “Per-scope vs global” (so status doesn’t explode)

Production will have many scopes (runs/worlds). So the join supports two levels:

* **Global frame**: whole-projector progress (partition basis + integrity + health)
* **Per-scope frame**: only on-demand (e.g., “status for this `scope_key`”), used for debugging specific run drift

**Design authority choice for v0:**
Always maintain a **global frame**, and expose **per-scope frame** only by explicit request (ops/debug), not by default telemetry spam.

---

## A3.14 — J-IEG-14: **S8 → Observability pipeline**

### Metrics/logs/traces emission boundary

### Why this join exists

This is the *only* path by which IEG’s internal truth becomes:

* measurable (for SLOs, dashboards, corridor checks),
* governable (DL uses obs signals to compute capability masks),
* explainable (operators can answer “why is IEG degraded/lagging?”)

### What S8 emits (three channels + one optional)

Think of these as “what the environment ladder lets vary”: **sampling, thresholds, verbosity**—but not the meaning.

#### 1) Metrics (corridor inputs)

Minimum set that must exist in **all envs** (even if low volume):

**Projector progress**

* `ieg_partition_next_offset{partition}` (or `basis_digest` + `partition_lag` metrics)
* `ieg_consumer_lag{partition}` (if available)
* `ieg_watermark_age_seconds{partition}`

**Apply classification**

* `ieg_apply_total{class=applied|duplicate_noop|irrelevant_noop|invalid_recorded|error}`
* `ieg_apply_failure_total{reason=missing_pins|missing_id_hints|malformed|apply_error|index_error}`

**Integrity & mode**

* `ieg_integrity_degraded` (0/1)
* `ieg_maintenance_mode{mode}` (0/1 per mode)
* `ieg_projection_generation_id` (as label or as gauge value/hard-coded tag)

**Query surface**

* `ieg_query_latency_ms{op}` (p50/p95)
* `ieg_query_error_total{op,reason}`

> These metrics are exactly what DL can use for “IEG usable?” decisions; only thresholds differ by environment profile.

#### 2) Logs (structured boundary decisions)

S8 logs only **boundary-relevant events**, with correlation keys, never raw payload by default:

* projector lifecycle: `START`, `REBALANCE`, `RESUME_FROM_CHECKPOINT`, `PAUSE`, `DRAIN`, `REBUILD_START/END`
* integrity transitions: `INTEGRITY_DEGRADED`, `INTEGRITY_RESTORED` (restored only via explicit rebuild/backfill)
* apply failures: log EB coords + reason + scope_key (if present)
* query failures: op + scope + reason + serve basis digest

#### 3) Traces (end-to-end causality)

S8 must:

* accept incoming trace context from DF/OFP query calls,
* emit spans for each query op,
* (optionally) emit spans for apply batches (low-sampled in prod).

#### 4) Optional durable “ops facts”

If you enable a pointer stream, S8 can emit rate-limited milestone facts (e.g., rebuild completed). But **telemetry is still the primary**; the pointer stream is optional and must not become a second truth feed.

### Hard pins (to avoid drift)

* **Correlation keys always present** on telemetry/logs: `scope_key` (when relevant), `projection_generation_id`, `basis_digest` (or graph_version), and EB position for apply-related events.
* **No payload dumping** as “logs”; payload stays by-ref in the platform’s audit/posture.
* **Same metric names and meanings across envs**; only sampling/thresholds differ.

---

## A3.15 — J-IEG-15: **S8 → S1/S3**

### Backpressure controls: throttle / pause / resume / drain

### Why this join exists

IEG must be able to **protect itself and the platform** under:

* downstream store saturation,
* runaway lag,
* rebuild/backfill operations,
* resource exhaustion.

This is *not* a semantic control (it must never change meaning), it’s an **operational safety valve**.

### The control verbs (what S8 can tell S1/S3 to do)

Treat these as a tiny internal “control API”:

1. **THROTTLE(rate / concurrency)**

* Reduce consumption rate or batch size.
* Used when ST is saturated or apply latency spikes.

2. **PAUSE(partitions | global)**

* Stop fetching new records for specific partitions or entirely.
* Used for maintenance or when checkpoint safety is at risk.

3. **DRAIN(in_flight_only)**

* Stop intake, allow S3 to finish in-flight apply units, then enter PAUSED.
* Used before cutover/backfill or during incident response.

4. **RESUME**

* Resume intake from S7 checkpoint basis (exclusive-next offsets).

5. **REPLAY_SET_BASIS(basis)**

* Only used during declared backfill/rebuild: set the consumer start basis (comes from S7’s generation/basis).

### What triggers these controls (production-real triggers)

S8 decides based on **S7 status frames + store health**:

* `watermark_age_seconds` too high → THROTTLE or PAUSE (depending on whether you can catch up)
* ST write latency / errors → THROTTLE or DRAIN
* rebuild/backfill requested → DRAIN → PAUSE → REPLAY_SET_BASIS → RESUME
* integrity degraded does **not** automatically pause (that’s a policy choice); it must at least surface and allow DL to disable usage. Pausing is only for safety/stability, not “correctness theatre.”

### Non-negotiable invariants (the “don’t break the platform” rules)

* **Never skip offsets.** Pause/resume must preserve ordering and resume exactly from `next_offset_to_apply`.
* **No lying versions.** You cannot advance checkpoints while paused unless the offset has been fully processed and durably recorded.
* **No semantic mutation.** Backpressure changes *when* you process, not *what* processing means.
* **Explicit mode visibility.** Every PAUSE/DRAIN/RESUME must be visible through S7→S8 status and telemetry.

### Environment knobs (allowed to vary)

* thresholds that trigger throttle/pause (local lax, prod strict)
* max in-flight apply units
* batch size / commit frequency
* whether query load shedding is enabled (e.g., return `IEG_BUSY` rather than time out)
* whether to prefer “throttle” or “pause” under saturation

(These are exactly the kinds of profile knobs the environment ladder expects.)

---

## One compact mental model for A3

* **S7 is the truth engine** for progress/integrity/mode.
* **S8 is the mouth + hands**: it *speaks* (telemetry/status) and *acts* (backpressure), but it does not invent truth.
* **Backpressure is survivability**, not correctness; correctness is handled by explicit integrity + DL masks + auditable provenance.

---

Absolutely. We’ll illuminate **A4 (Backfill/Rebuild plane)** and **A5 (Optional pointer emission plane)** as *internal joins between opaque subnetworks*, and I’ll **pin** the invariants so we don’t drift when we later open the boxes.

Below, **S1/S7/S8/ST** (and the pointer emitter) are still opaque.

---

## A4 Plane Laws (authoritative for this brainstorm)

**A4-LAW-1 — Rebuild/backfill is declared, not implicit**
No “just restart and hope.” Every replay/backfill is a **declared operation** with **scope + basis + outputs**, and yields an auditable outcome (accepted/rejected/completed/failed/aborted).

**A4-LAW-2 — Truth is never rewritten**
Backfill changes only *derived* projection state. EB facts remain unchanged; offsets are the basis; no stealth edits.

**A4-LAW-3 — Explicit generations + explicit cutover**
A rebuild produces a **new projection generation**. Cutover to that generation is **explicit**. Old generation may be retained or dropped, but never silently overwritten.

**A4-LAW-4 — graph_version never lies, and is paired with generation**
Every served response must be tied to:

* `projection_generation_id`, and
* `graph_version` (offset-basis token).
  This is how “same offsets, different projector semantics” stays explainable.

**A4-LAW-5 — Maintenance modes are visible**
If IEG is rebuilding/paused/draining, that is surfaced (status + query responses), never hidden.

---

# A4.16 — J-IEG-16: **Run/Operate → S8**

### Declared replay/backfill command enters IEG boundary

### Purpose

Provide the *only internal entry* for rebuild/backfill control, with strict validation and auditability.

### Input: `BackfillCommand` (conceptual)

Minimum fields (production-real, but not overly specific):

* `operation_id` (unique)
* `op_type`: `REBUILD_FULL | REPLAY_RANGE | REINDEX_ONLY | INTEGRITY_RESET_ONLY | ABORT`
* `target`: `scope_selector` (one scope, many scopes, or global)
* `basis` (mandatory for replay/rebuild):

  * `stream_name`
  * `partition_offsets` or `offset_range` per partition
  * optionally `time_window` **only if resolvable to offsets**
* `requested_outputs`: at least `{IEG projection generation}` (and optionally “also rebuild indices”)
* `policy_rev` / `approval_ref` (environment-policy knob: strict in prod, lax locally)
* `dry_run` (allowed)

### Output: `BackfillAck`

* `ACCEPTED | REJECTED`
* `reason` (if rejected)
* `planned_generation_id` (if accepted)
* `planned_mode`: `BUILDING | CUTOVER_PENDING | MAINTENANCE_REQUIRED`
* `initial_status_ref` (for tracking)

### In-bounds (what S8 may do)

* Validate command shape + basis sanity.
* Enforce environment policy (who/when can rebuild).
* Emit governance/ops logs/telemetry milestones (not a second truth feed).

### Out-of-bounds (what S8 must NOT do)

* It must not “interpret facts” or alter EB.
* It must not start consuming from a new basis without an explicit generation plan (that’s J-IEG-17/18).

**Pin:** S8 is the *control gate*, but **S7 is the authority** for generation/basis truth.

---

# A4.17 — J-IEG-17: **S8 ↔ S7**

### Create/activate a projection generation + replay basis; cutover semantics

### Purpose

Turn an accepted command into a **managed generation lifecycle** that is:

* explicit,
* durable,
* and query-visible.

### Key concept: `ProjectionGeneration`

A generation is the “named instance” of the derived projection.

**States (minimum):**

* `ACTIVE` (serving + incremental projector writes)
* `BUILDING` (being constructed by replay/backfill)
* `READY_TO_CUTOVER`
* `CUTOVER_IN_PROGRESS`
* `FAILED`
* `RETIRED`

### S8 → S7: `GenerationPlanRequest`

* `operation_id`
* `op_type`
* `scope_selector`
* `basis` (offset plan)
* `build_strategy`: `SIDE_BY_SIDE | IN_PLACE` *(semantics pinned by cutover visibility; strategy remains implementer freedom)*
* `cutover_policy`: `AUTO | MANUAL_CONFIRM` *(env knob)*

### S7 → S8: `GenerationPlanResponse`

* `planned_generation_id`
* `state=BUILDING` (or `REJECTED`)
* `active_generation_id` (current)
* `serve_mode_during_build`: `SERVE_OLD | SERVE_STALE_LABELED | REFUSE_STRICT`
* `constraints`: e.g., “pause projector first,” “requires drain”

### Activation / cutover handshake (still within J-IEG-17)

S8 orchestrates; S7 owns truth:

* `request_cutover(generation_id)` → `CUTOVER_IN_PROGRESS`
* `confirm_cutover_complete(generation_id)` → new `ACTIVE`
* `abort_generation(generation_id)` → `FAILED/RETIRED`

**Pins (most important):**

* Only **one ACTIVE generation per scope**.
* A query response must always include the generation id it was served from.
* Integrity can only become “clean again” via explicit generation change / declared rebuild, not silently.

---

# A4.18 — J-IEG-18: **S7 → S1**

### Consumer start position / replay basis fed into intake

### Purpose

Make replay deterministic: S1 must consume from **exactly the basis S7 declares**, not “whatever the consumer group feels like.”

### Input to S1: `ConsumptionBasisFrame`

* `generation_id`
* `mode`: `INCREMENTAL | REPLAY`
* `stream_name`
* `partition_start_offsets` (exclusive-next semantics apply when resuming)
* `partition_end_offsets?` (if replay-range job)
* `resume_rule`: `EXACT | AT_LEAST` *(v0 pin: EXACT)*
* `maintenance_flags`: `PAUSED | DRAINING | RUNNING`

### Pins

* **No skipping offsets.** S1 must not advance beyond the declared start without processing.
* **Resume is deterministic.** If S7 says “start at offset X,” S1 starts at X.
* **Replay and incremental are never mixed in one generation** unless explicitly planned (we’ll keep it simple: replay builds a new generation; incremental continues on ACTIVE).

---

# A4.19 — J-IEG-19: **S8 ↔ ST**

### Generation cutover / maintenance mode / read routing

### Purpose

Ensure writes/reads land in the correct generation and that cutover is visible and coherent.

### The problem this join solves

During rebuild you can easily end up with:

* projector writing to one place while queries read from another,
* or “half old half new” reads,
* or silent overwrite.

This join pins the correct behavior.

### What crosses this join

#### S8 → ST: `StoreRoutingDirective`

* `active_generation_id`
* `building_generation_id?`
* `write_target`: which generation receives projector writes
* `read_target`: which generation serves queries (often old until cutover)
* `maintenance_mode`: `NONE | REBUILDING | PAUSED | DRAINING`
* `cutover_step`: `PREPARE | SWITCH_READS | SWITCH_WRITES | FINALIZE`
* `atomicity_requirement`: “switch reads and writes must be perceived coherently”

#### ST → S8: `StoreRoutingReceipt`

* confirms routing changes
* includes any constraints (“cannot switch writes while in-flight transactions exist”)
* returns “current routing state”

### Pinned semantics

* **Side-by-side build is the default v0 posture**: BUILDING generation is separate from ACTIVE.
* **Cutover is explicit** and proceeds in a visible sequence (even if done quickly).
* **Queries never mix generations.** A single query is served from exactly one generation and stamped with that `projection_generation_id`.
* **graph_version is scoped to generation.** Even if offsets are comparable, the *meaning* is always “graph_version under generation G.”

### Maintenance/read posture during rebuild (v0 choices)

To avoid drift and keep it realistic, pin this:

* Default during BUILDING: **serve from ACTIVE generation** (old) and label status as `maintenance_mode=REBUILDING` in health surfaces.
* Strict callers can require “no rebuild” via S7 decision (`REBUILDING` → error).

---

## Canonical A4 internal path (how these joins compose)

1. Run/Operate sends `BackfillCommand` → **J-IEG-16** → S8 validates/accepts
2. S8 requests generation plan → **J-IEG-17** → S7 creates `generation_id=G_new (BUILDING)`
3. S8 sets store routing for build target → **J-IEG-19** → ST writes BUILDING state separately
4. S7 emits replay basis → **J-IEG-18** → S1 replays into BUILDING generation
5. When complete: S8 requests cutover → **J-IEG-17** + **J-IEG-19** do explicit switch
6. New generation becomes ACTIVE; old becomes RETIRED (or retained)

---

# A5.20 — J-IEG-20: **S7/S8 → Pointer Emitter**

### Rate-limited milestone facts (optional plane)

This plane exists only if you enable the *vertex-level* optional join “IEG → audit pointer stream.” If not enabled, you still get full telemetry via A3.

## A5 Plane Laws

**A5-LAW-1 — Pointers are milestones, not a second truth stream**
They must never be consumed as decisionable facts or used to mutate identity. They are purely “index/ops breadcrumbs.”

**A5-LAW-2 — Rate-limited and idempotent**
No per-entity/per-edge chatter. Pointers must be dedupable and stable under retries.

## What S7/S8 may emit (v0 suggested set)

* `IEG_GENERATION_BUILD_STARTED` (includes `generation_id`, basis digest)
* `IEG_GENERATION_BUILD_COMPLETED` (includes `generation_id`, resulting `graph_version`, integrity status)
* `IEG_CUTOVER_COMPLETED` (old→new generation ids)
* `IEG_INTEGRITY_DEGRADED` (first failure position ref + reason summary)
* `IEG_INTEGRITY_RESTORED` (only if a rebuild/backfill explicitly restored it)
* `IEG_CHECKPOINT_HEARTBEAT` (periodic, includes basis digest)

## Required correlation keys on every pointer

* `projection_generation_id`
* `graph_version` (or basis digest + optional sampled basis)
* `stream_name`
* (if relevant) `scope_selector` or `scope_key`
* (if relevant) EB position refs

## Out-of-bounds

* No payload dumping.
* No pointer events that “look like” business traffic.
* No pointers used as triggers for ingestion or graph mutation.

---

## The one “design authority” pin I’m adding here (to prevent future drift)

**PIN-A4A5-01:** Regardless of whether A5 is enabled, **A4 rebuilds must always be observable** through A3 telemetry and S7→S8 status. A5 is optional sugar; it must never be required for correctness or governance.

---

Absolutely. We’ll “illuminate” **P-INT-1 → P-INT-4** as **production-grade internal flows** (still with S1–S7/S6/S4/S5/S3/ST opaque), by pinning:

* **the exact sequence of joins** traversed,
* **what each hop must produce/consume**, and
* **the durable outcomes** that make the flow restart-safe and drift-proof.

I’m going to treat each path as operating on the canonical **Apply Unit**:

> **Apply Unit = “process one EB record at (stream, partition, offset) into exactly one durable outcome + advance next_offset_to_apply to offset+1.”**

That invariant holds for *all* four paths.

---

## Shared primitives used by P-INT-1..4

### Shared inputs

* **EBRecord**: `{stream, partition, offset, envelope_bytes}`

### Shared internal objects

* **NormalizedEvent (S1 output)**: parsed envelope + normalized identity hints (or explicit “missing”) + parse_status
* **ScopedCandidate (S2 output)**: adds `scope_key` (ContextPins) or `NONE` if incomplete
* **ApplyOutcome (S3→S7)**: exactly one of:

  * `APPLIED`
  * `DUPLICATE_NOOP`
  * `IRRELEVANT_NOOP`
  * `INVALID_RECORDED` (with reason)

### Shared “truth rails”

* Offsets are processed **in-order per partition**.
* Watermarks are **exclusive-next** (`next_offset_to_apply = offset + 1` after processing).
* “Processed” means **durably recorded**, not “we tried.”
* `graph_version` advances when offsets are processed, even for no-ops/invalids.

---

# P-INT-1 — Normal graph-mutating apply (happy path)

### High-level route

`S1 → S2 → S3 → (S4 + S5) → S6 → ST`
with `S3 ↔ S7` producing watermark advancement + version basis.

### Preconditions

* S7 indicates the partition’s current `next_offset_to_apply == offset` (i.e., we’re not skipping).
* The event is identity-relevant **and** has the required scoping + identity hints (payload-blind).

### Step-by-step (production truth)

1. **S1 (Intake) parses and normalizes**

   * Parse envelope fields (must have at least `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`).
   * Extract ContextPins (if present) and normalize identity hints into an internal `identity_hints` structure.
   * Output: `NormalizedEvent(parse_status=OK, identity_hints=present)`.

2. **S2 (Scope Router) binds to one scope**

   * Build `scope_key := {scenario_id, run_id, manifest_fingerprint, parameter_hash}`.
   * Output: `ScopedCandidate(scope_key=<value>)`.

3. **S3 (Apply Coordinator) establishes the apply unit**

   * Consults S7 for “expected offset / mode / generation” guard.
   * Computes `update_key := H(scope_key + event_id + ieg_update_semantics_v0)`.
   * Checks update ledger existence for `update_key` (via ST or via cached truth that is backed by ST).
   * Result: not seen → continue as `APPLIED`.

4. **S3 → S4 (Canonical Identity)**

   * S3 submits an `IdentityMutationRequest` (scope + ts_utc + identity_hints + provenance_ref).
   * S4 deterministically resolves or mints canonical `EntityRef`s and writes alias claims (no merges).
   * Output: resolved entities, any new entities created, conflicts (if any).

5. **S3 → S5 (Edges)**

   * S3 submits `EdgeMutationRequest` using the canonical endpoints from S4.
   * **Pinned v0 stance for ambiguity:** if S4 returned multiple candidates for an endpoint, edge creation is **skipped-and-recorded** (conservative, explainable).
   * Output: edges upserted + any edge conflicts.

6. **S4/S5 → S6 (Indices)**

   * S6 updates read projections (identifier lookup, neighbor adjacency, profile views).
   * **Pinned v0 stance:** indices update synchronously within the apply unit (lowest drift risk).

7. **S3 ↔ S7 (Versioning & Integrity)**

   * S3 emits `ApplyOutcome(class=APPLIED, offset, update_key, notes)` to S7.
   * S7 prepares the new basis: `next_offset_to_apply := offset+1` (exclusive-next).
   * Integrity remains `CLEAN` unless there was an actual apply error.
   * Note: “edge skipped due to ambiguity” is **not** an integrity failure; it’s a surfaced conflict.

8. **ST (Durable commit)**

   * ST commits, coherently:

     * identity mutations (S4),
     * edge mutations (S5),
     * index updates (S6),
     * update_key ledger mark,
     * apply outcome classification,
     * partition checkpoint advance (offset+1),
     * any conflict artifacts / stats for observability.
   * Only after this commit is the offset considered processed.

### Observable result

* Projection state changed (entities/aliases/edges/indices).
* Partition watermark advanced.
* `graph_version` basis (vector) advanced, and can be attached to queries.

---

# P-INT-2 — Duplicate event (idempotent no-op, still progresses)

### High-level route

`S1 → S2 → S3 → S7 → ST`
(no S4/S5 mutation; indices unchanged)

### Important nuance (two kinds of “duplicates”)

* **Redelivery of the same offset** (EB at-least-once): you might see (partition, offset) again after a crash or retry.
* **True duplicate at a different offset**: upstream produced a second copy of the same logical event (`event_id` repeats).

**Both must be safe.** The idempotency anchor is `update_key`.

### Step-by-step

1. **S1 parses** into `NormalizedEvent` (OK or not—see mismatch rule below).

2. **S2 scopes** into `ScopedCandidate(scope_key=…)`.

3. **S3 checks idempotency**

   * Computes `update_key`.
   * Finds it already applied in the ledger.
   * Classifies as `DUPLICATE_NOOP`.

4. **S3 ↔ S7**

   * Emits `ApplyOutcome(class=DUPLICATE_NOOP, offset, update_key)` to S7.
   * S7 advances `next_offset_to_apply := offset+1`.

5. **ST commit**

   * Records the duplicate outcome (for audit/metrics/debug).
   * Advances the checkpoint.

### Designer pin (important boundary sanity)

If a repeated `event_id` arrives with **conflicting envelope-critical fields** (e.g., different `event_type` or different `ts_utc` or different ContextPins), that is not a harmless duplicate: it violates the “event_id identifies one fact” assumption.

**My v0 ruling:** treat it as `INVALID_RECORDED(reason=DUPLICATE_MISMATCH)` (still no projection mutation), integrity is degraded, and offsets still advance.
We do **not** stall; we do **not** guess which one is “true”; we surface it.

---

# P-INT-3 — Graph-irrelevant event (intentional no-op)

### High-level route

`S1 → S2 → S3 (class=irrelevant) → S7 → ST`

### When this path applies

* Event type is **not identity-relevant** by IEG’s routing rules, *or*
* The event is identity-adjacent but explicitly declared “non-mutating” for IEG v0.

This is **designed behavior**, not an error.

### Step-by-step

1. **S1 parses** into `NormalizedEvent(parse_status=OK)`
   Identity hints may exist; doesn’t matter.
2. **S2 scopes** (or scope_key NONE; irrelevant is still irrelevant).
3. **S3 classifies** deterministically as `IRRELEVANT_NOOP`

   * No S4/S5/S6 calls.
4. **S3 → S7** emits `ApplyOutcome(IRRELEVANT_NOOP)`
5. **ST commit** records the outcome + advances `next_offset_to_apply := offset+1`

### Why this is production-critical

This path prevents hidden coupling: IEG doesn’t accidentally “learn identity” from every event; it only mutates on the subset explicitly declared identity-relevant.

---

# P-INT-4 — Invalid-for-mutation (apply failure recorded)

### High-level route

`S1 → S2 → S3 (record failure + integrity degraded) → S7 → ST`

### When this path applies

The event is **identity-relevant**, but cannot be safely applied because one or more required inputs are missing/invalid:

* missing ContextPins (scope_key becomes NONE), **or**
* missing/invalid identity hints (your `observed_identifiers[]` equivalent), **or**
* malformed envelope (missing required fields), **or**
* internal apply errors (store write error, etc.).

### Step-by-step

1. **S1 parses**

   * If envelope is malformed: `parse_status=MALFORMED`.
   * Else: OK, but identity hints may be missing.

2. **S2 scopes**

   * If ContextPins incomplete: `scope_key=NONE`.

3. **S3 classifies as invalid-for-mutation**

   * Emits `ApplyOutcome(class=INVALID_RECORDED, reason=<typed>)`.
   * **No S4/S5/S6 mutation** (by design).
   * S7 marks integrity degraded for the relevant scope/generation (or global if unscoped).

4. **S3 ↔ S7**

   * Offsets still advance: `next_offset_to_apply := offset+1`.
   * Integrity status becomes `DEGRADED` (and stays that way until explicit rebuild/backfill).

5. **ST commit**

   * Records the failure artifact:

     * EB position (partition/offset),
     * reason,
     * scope_key if known,
     * minimal correlation keys (event_id, event_type),
     * and the fact that this offset is processed.
   * Advances checkpoint.

### Why we do not stall

Because stalling on a single bad event would freeze the entire projection (and thus the entire hot path that depends on it). Production safety requires:

* continue advancing,
* surface integrity degraded,
* let DL/DF explicitly degrade capability usage.

---

## One compact “who gets called” matrix (so we don’t drift later)

| Path                     | Calls S4/S5/S6? | Advances offsets? | Changes integrity?   | Mutates graph? |
| ------------------------ | --------------- | ----------------- | -------------------- | -------------- |
| P-INT-1 APPLIED          | Yes             | Yes               | Usually no           | Yes            |
| P-INT-2 DUPLICATE_NOOP   | No              | Yes               | No (unless mismatch) | No             |
| P-INT-3 IRRELEVANT_NOOP  | No              | Yes               | No                   | No             |
| P-INT-4 INVALID_RECORDED | No              | Yes               | Yes (DEGRADED)       | No             |

---

Great — here are **P-INT-5 → P-INT-8** as **production internal paths**, with **S1–S8 + ST still opaque**. I’ll keep them join-accurate (A2/A3/A4) and pin the invariants so we don’t drift when we open the boxes.

---

## P-INT-5 — Query: `resolve_identity`

### Purpose

Given a **scope** + **observed identifiers**, return **0..N canonical EntityRef candidates** (no merges) plus conflict markers, stamped with **`graph_version` + `projection_generation_id` + integrity**.

### Internal route

`S8 → S7` (choose serve basis + integrity gating)
`S8 → S6 → ST` (execute deterministic lookup under a read snapshot)
`S8` (attach basis + return)

### Step-by-step (production truth)

1. **S8 validates request**

   * Requires `scope_key` (ContextPins).
   * Requires `observed_identifiers[]` (already normalized).
   * Accepts optional constraints: `request_mode=STRICT|BEST_EFFORT`, `min_graph_version`, `require_integrity_clean`.

2. **S8 opens a read snapshot against ST**

   * The key pin: *the query must not read a “half old / half new” projection.*

3. **S8 asks S7 for a ServeBasisDecision (using the same snapshot)**

   * S7 returns: `serve_graph_version`, `projection_generation_id`, `integrity_status`, `maintenance_mode`.
   * If not OK, S8 returns an explicit error: `LAGGING`, `INTEGRITY_DEGRADED`, `REBUILDING`, `SCOPE_UNKNOWN`, etc., with retryable flag.

4. **S8 submits QueryIntent to S6**

   * Includes the snapshot handle + the selected serve basis token (or its digest).

5. **S6 executes resolve via ST**

   * Reads identifier→entity index rows (and any minimal entity metadata needed).
   * Returns deterministic results:

     * per identifier: candidate EntityRefs (0..N)
     * `conflicts[]` when N>1 (no merge)
     * stable ordering + deterministic pagination tokens.

6. **S8 returns response**

   * Data from S6
   * Plus `graph_version`, `projection_generation_id`, `integrity_status`, and (optionally) `basis_digest`.
   * Emits telemetry/traces (but **no state mutation**).

### Failure posture (pinned)

* Never fabricate identity. If insufficient or degraded, return explicit error or conflict markers.
* `BEST_EFFORT` can return results even if integrity is degraded, but **must label integrity**. `STRICT` can refuse.

---

## P-INT-6 — Query: `get_entity_profile` / `get_neighbors`

These share the **same shape** as P-INT-5; only the index access differs.

### Internal route (both ops)

`S8 → S7` (serve basis decision)
`S8 → S6 → ST` (profile/adjacency reads under the same snapshot)
`S8` (attach basis + return)

### 6A) `get_entity_profile(entity_ref)`

1. S8 validates: `scope_key` + `entity_ref`.
2. S8 opens ST snapshot.
3. S8 asks S7 for serve basis decision (snapshot-coupled).
4. S8 → S6: QueryIntent(profile).
5. S6 reads the entity’s profile view in ST (thin record + optional derived counters).
6. S8 returns record + `graph_version` + `projection_generation_id` + integrity.

**If entity_ref doesn’t exist in that scope/generation:** return `NOT_FOUND` (not an error in the projector).

### 6B) `get_neighbors(entity_ref, edge_type?, depth=1, limit, page_token)`

1. S8 validates: `scope_key` + `entity_ref`, enforces `depth=1` for v0.
2. S8 opens ST snapshot.
3. S8 asks S7 for serve basis decision (snapshot-coupled).
4. S8 → S6: QueryIntent(neighbors) (includes filters + pagination).
5. S6 reads adjacency index from ST and returns:

   * edges + neighbor EntityRefs
   * stable ordering + deterministic pagination tokens
   * conflict markers if ambiguity is represented (v0 is conservative: ambiguity typically means “edge not materialized,” so conflicts are sparse here).
6. S8 returns results + basis stamps.

### Key pins for P-INT-6

* Deterministic ordering and pagination are mandatory.
* Responses are **always** stamped with `graph_version` + `projection_generation_id` + integrity status.
* Reads remain side-effect free (no fixing, no watermark advancement).

---

## P-INT-7 — Status/health (ops read)

### Purpose

Provide a **single truthful “what’s going on” view** for:

* readiness/availability,
* progress (`graph_version` basis),
* integrity degradation,
* maintenance/rebuild mode,
* enough signals for DL corridor checks.

### Internal route

`S8 ← S7` (ProjectionStatusFrame)
`S7 ↔ ST` (durable basis/integrity/generation reads)
`S8 → Obs` (telemetry)
(+ optional `S8 ↔ S1` for runtime consumer stats)

### Step-by-step

1. **S8 receives status request**

   * global or per-scope; verbosity level.

2. **S8 obtains ProjectionStatusFrame from S7**

   * S7 reads from ST the durable truth:

     * `projection_generation_id`
     * current basis vector (or digest)
     * integrity status + failure summary
     * maintenance mode (REBUILDING/PAUSED/DRAINING)
     * watermark age summary.

3. **Optional runtime overlay**

   * S8 may ask S1 (or intake runtime) for *ephemeral* stats:

     * assigned partitions
     * in-flight apply units
     * fetch latency / backpressure state
   * These do **not** override S7’s durable basis; they complement it.

4. **S8 assembles HealthPayload**

   * `projector_ready`, `query_ready`
   * `maintenance_mode`
   * `graph_version` (or basis digest) + generation id
   * `integrity_status` + last failure position (no payload)
   * lag / watermark age summaries
   * build/policy identifiers (`build_id`, `policy_rev`, stream name).

5. **S8 emits telemetry**

   * metrics/logs/traces reflecting the same truth (no “different story” in telemetry vs status).

### Failure posture

If ST is unavailable: status returns **DEGRADED** with explicit reason (and telemetry flags it). Still no mutation.

---

## P-INT-8 — Rebuild/backfill replay (declared, auditable)

### Purpose

Produce a **new projection generation** from a declared replay basis, then **explicitly cut over**, without rewriting truth.

### Internal route (full)

`Run/Operate → S8 → S7` (plan generation + basis)
`S8 → S1/S3` (drain/pause/resume controls)
`S8 ↔ ST` (routing: build vs active generation)
`S7 → S1` (ConsumptionBasisFrame: exact start/end offsets)
Replay applies **P-INT-1..4** repeatedly into BUILDING generation
Then `S8 ↔ S7 ↔ ST` explicit cutover

### Step-by-step (production truth)

1. **Declare the operation**

   * Run/Operate sends `BackfillCommand(operation_id, scope_selector, basis, outputs, approvals)` to S8.
   * S8 validates policy and returns `ACCEPTED/REJECTED` with reasons.

2. **Plan a new generation**

   * S8 ↔ S7: create `generation_id = G_new` in `BUILDING`, record the replay basis (offset plan).
   * Decide serve posture during build (default: continue serving the old ACTIVE generation, labeled REBUILDING).

3. **Drain safely**

   * S8 uses internal controls (A3) to `DRAIN` then `PAUSE` intake for the affected partitions/scopes so no in-flight apply unit is left half-committed.

4. **Route storage**

   * S8 ↔ ST sets routing:

     * projector writes for replay go to `G_new (BUILDING)`
     * queries continue reading `G_active` (or refuse strict callers during rebuild).

5. **Start replay from explicit basis**

   * S7 → S1 publishes `ConsumptionBasisFrame(mode=REPLAY, start_offsets, end_offsets, generation_id=G_new)`.
   * S8 issues `RESUME` for replay mode.

6. **Replay and build**

   * S1 consumes from the declared offsets.
   * For each EB record, the spine executes **P-INT-1/2/3/4** and writes into **BUILDING** generation.
   * S7 tracks checkpoints and integrity for `G_new`.

7. **Completion condition**

   * When all partitions reach their declared end offsets (or “complete basis”), S7 marks `G_new = READY_TO_CUTOVER`.

8. **Explicit cutover**

   * S8 requests cutover via S7.
   * S8 ↔ ST performs explicit routing switches (reads then writes, or an atomic swap) so **new queries and projector writes point at G_new**.
   * S7 marks `G_new = ACTIVE`, `G_old = RETIRED` (or retained for investigation).

9. **Resume steady-state**

   * S7 publishes incremental consumption basis for ACTIVE mode.
   * S8 resumes normal projector operation.

### Failure/abort posture (must exist in production)

* If replay build fails: `G_new = FAILED`, old generation remains ACTIVE, status surfaces `REBUILD_FAILED`, retry/abort is explicit.
* Abort is a declared command: S8 tells S7 to retire BUILDING generation and restore routing; no silent partial cutover.

### The pinned explainability guarantee

Every query/decision that uses IEG context must be able to say:

* **which generation** (`projection_generation_id`), and
* **which applied basis** (`graph_version`)
  it relied on — especially across rebuilds.

---

Got it. We’ll illuminate the **internal loops** as *production-grade feedback cycles* inside IEG, while **keeping S1–S8 + ST opaque** (no module internals yet). I’ll expand each loop with: **trigger → cycle steps → stabilization condition → invariants → failure posture**.

---

## L-INT-1 — Continuous projector loop (steady-state)

### What this loop *is*

IEG’s primary runtime is: **consume → classify/apply → commit → checkpoint → repeat**, per EB partition.

**Cycle (per partition):**
`S1 → S2 → S3 → ST → S7 → (back to) S1`

### Trigger

* Partition is assigned to this IEG instance (or worker) and **S7 says there’s work** (i.e., `next_offset_to_apply` is behind EB head).

### Cycle steps (what happens each iteration)

1. **S7→S1: Resume basis**
   S1 knows the *exact* `next_offset_to_apply` for this partition/generation.

2. **S1 consumes (partition, offset)** from EB and normalizes the event → hands to S2.

3. **S2 binds scope** (ContextPins scope_key or NONE) → hands to S3.

4. **S3 runs the Apply Unit decision**
   Exactly one classification per offset: `APPLIED | DUPLICATE_NOOP | IRRELEVANT_NOOP | INVALID_RECORDED`.

5. **ST commit** makes the outcome durable (plus mutations if APPLIED).

6. **S7 advances** `next_offset_to_apply := offset+1` (exclusive-next) and updates integrity/progress truth.

7. S1 repeats for the next offset.

### Stabilization condition

* For each partition, loop “idles” when `next_offset_to_apply` reaches current EB head (or consumer is intentionally paused).

### Pinned invariants (drift killers)

* **No skipping offsets** within a partition.
* **One durable outcome per offset**, always.
* **Watermarks never lead durability** (S7 cannot claim offset+1 unless ST committed the outcome).
* **Duplicates/out-of-order safety is intrinsic** (idempotency is handled by S3+ledger, not by “hoping EB is clean”).

---

## L-INT-2 — Restart/rebalance loop (durability truth)

### What this loop *is*

The production guarantee that **crashes, restarts, and partition rebalances do not change meaning**—they only change *which instance* is running the projector.

**Cycle:**
`(restart/rebalance) → S7 → S1 → (resume L-INT-1)`

### Triggers

* Process restart/crash
* Scale up/down (consumer group rebalance)
* Maintenance pause/drain (local) or rolling deployments (prod)

### Cycle steps

1. **Partition assignment happens** (outside IEG logic; S1 learns “you own partitions P…”).
2. **S1 asks S7 for resume basis** for each owned partition and the active generation:

   * `generation_id`
   * `next_offset_to_apply` (exclusive-next)
   * any maintenance flags (PAUSED/DRAINING/REPLAY)
3. **S1 positions consumption exactly at that basis**.
4. **Resume normal projector loop (L-INT-1)**.
5. If EB redelivers previously-seen data (at-least-once), **S3’s idempotency** ensures harmless no-ops.

### Stabilization condition

* All newly assigned partitions are resumed at correct offsets and the steady-state projector loop continues.

### Pinned invariants

* **S7 is the resume authority**, not “whatever the consumer group last committed.”
  (We treat EB consumer-group commits as operational hints; S7’s durable checkpoint is the truth.)
* Restart may cause **reprocessing**, but never **double-application** (update_key ledger prevents it).
* Rebalance must not cause “split-brain” ownership of a partition’s offsets (assignment is exclusive).

---

## L-INT-3 — Integrity degradation loop (explicitly surfaced)

### What this loop *is*

A loop that turns “projection couldn’t apply something correctly” into **explicit, query-visible, ops-visible truth**—so the platform can degrade safely rather than silently lie.

**Cycle:**
`S3 apply-failure → S7 integrity flag → S8 surfaces + telemeters → (external DL constrains DF) → usage changes`

(External DL is outside the vertex, but the internal closure is: **failure → integrity becomes explicit**.)

### Triggers (what counts as an integrity-degrading event)

* Identity-relevant event missing ContextPins or identity hints
* Duplicate mismatch (same event_id but conflicting envelope-critical fields)
* Internal apply errors (write failure that forces INVALID_RECORDED)
* Index update failure (if synchronous indices are pinned)

### Cycle steps

1. **S3 records INVALID_RECORDED** for an offset (with a typed reason) and emits ApplyOutcome to S7.
2. **S7 marks integrity DEGRADED** for the relevant generation (and optionally a per-scope integrity view).
3. **S8 begins surfacing this everywhere**:

   * status/health payload includes integrity DEGRADED
   * query responses include `integrity_status` + `graph_version` + `generation_id`
   * telemetry emits integrity flag + failure counters + last-failure EB coords
4. **External system reaction happens** (DL disables “use IEG context”, DF falls back), which typically reduces query load and prevents risky reliance.
5. **Ops either accept degraded mode** or initiate rebuild/backfill (L-INT-5).

### Stabilization condition

There are only two stable end states:

* **Degraded but operating** (explicitly labeled), or
* **Restored by explicit rebuild/backfill** (integrity returns to CLEAN only via generation change / declared reset)

### Pinned invariants

* **Integrity does not auto-reset** due to time passing or “it seems fine now.”
* **Projection does not stall forever** on one bad event: offsets still advance; the system remains live, but integrity is explicit.

---

## L-INT-4 — Backpressure loop (survivability)

### What this loop *is*

A self-protection loop so IEG can survive saturation and lag without changing semantics.

**Cycle:**
`ST/S7 detect pressure → S8 throttles/pauses/drains → S1/S3 intake reduces → system stabilizes → resume`

### Triggers

* ST write latency spikes / error rate rises
* In-flight apply backlog grows
* Watermark age / lag exceeds corridor thresholds (environment-profile knobs)
* Rebuild/cutover preparation (needs drain)

### Cycle steps

1. **Pressure is detected** (from ST health + S7 progress indicators + S1 backlog signals).
2. **S8 chooses a control action** (in increasing severity order):

   * THROTTLE (reduce rate / concurrency)
   * PAUSE partitions or global
   * DRAIN (finish in-flight applies then pause)
   * Load-shed queries (explicit `IEG_BUSY` rather than timeouts)
3. **S1/S3 respond** by reducing consumption/apply pressure.
4. **Telemetry shows the mode change** (so DL/ops understand why behavior changed).
5. When pressure falls below recovery thresholds (with hysteresis), **S8 RESUMEs** and L-INT-1 continues.

### Stabilization condition

* System remains within safe resource bounds while still making forward progress (maybe slower).

### Pinned invariants

* Backpressure must never cause **offset skipping** or “pretend applied.”
* Backpressure changes *when* you process, not *what processing means*.
* Mode changes are explicit and observable (status + telemetry).

---

## L-INT-5 — Rebuild/cutover loop (generation lifecycle)

### What this loop *is*

The loop that makes “derived & rebuildable” true in practice: build a new generation deterministically from a declared basis, then cut over explicitly.

**Cycle:**
`Run/Operate → S8 → S7 (new generation plan) → S8 drain/pause → S7→S1 replay basis → replay builds → S7 ready → S8 cutover → resume L-INT-1`

### Triggers

* Declared backfill/rebuild requested (ops or governance)
* Integrity degraded and needs reset
* Projection semantics change (new logic release) and you want an explainable cutover
* Data repair operation (corruption, lost checkpoints)

### Cycle steps

1. **Declare operation** enters at S8 (validated against environment policy).
2. **S7 creates BUILDING generation** with an explicit replay basis.
3. **S8 drains/pauses** to avoid partial in-flight apply units.
4. **S8 routes writes** to BUILDING generation (side-by-side default v0).
5. **S7 tells S1 the exact replay start/end offsets**; S1 replays.
6. Replay repeatedly executes **P-INT-1..4** into BUILDING generation until basis is reached.
7. **S7 marks READY_TO_CUTOVER**.
8. **S8 performs explicit cutover** (read/write routing switch), and S7 marks the new generation ACTIVE.
9. **Resume steady-state** projector loop under the new generation.

### Stabilization condition

* Exactly one ACTIVE generation per scope, and all serving/reporting is consistent with that generation.

### Pinned invariants

* **No mixed-generation reads**: a query is served from exactly one generation and stamped as such.
* **graph_version is always interpreted under a generation_id** (so “same offsets, different semantics” stays explainable).
* **Abort is explicit**: you can fail a BUILDING generation without disturbing ACTIVE.

---

## How the loops compose (so we don’t drift later)

* **L-INT-1** is the baseline runtime.
* **L-INT-2** is how L-INT-1 survives restarts/rebalances.
* **L-INT-3** is how L-INT-1 surfaces correctness gaps without stalling the platform.
* **L-INT-4** is how L-INT-1 survives saturation/lag without changing meaning.
* **L-INT-5** is how L-INT-3 (and evolution) gets resolved cleanly via explicit rebuild/cutover.

---

Yep — this is worth pinning explicitly. Here are the **non-joins / “must-not-exist” edges** (and a few **anti-paths**) that define the **IEG boundary** and keep us from drifting when we open the boxes.

I’m going to label these as **PIN-NONJOIN** rules. They’re authoritative for this brainstorm.

---

## 1) Platform-level non-joins for the IEG vertex

### PIN-NONJOIN-PLAT-01 — No side door into IEG

**No producer** (engine traffic, DF, AL, external sources) may write into IEG directly.
**Only admitted EB traffic** is a fact feed into IEG. This preserves the IG→EB trust boundary and replay semantics. 

### PIN-NONJOIN-PLAT-02 — IEG does not write decisionable traffic

IEG does **not** emit “graph updates” or “identity events” back onto `fp.bus.traffic.v1`.
IEG is a **derived projection**; the only allowed emission is an **optional pointer/status stream** (milestones) that is *not consumed as decisionable truth*. 

### PIN-NONJOIN-PLAT-03 — No direct Engine→IEG consumption for runtime projection

IEG does not consume engine “event tables” or truth_products directly as a hot-path input.
If we ever seed/hydrate from engine surfaces, it must happen **only via A4 declared rebuild/backfill** (i.e., a controlled generation build), never as a live bypass of EB semantics.

### PIN-NONJOIN-PLAT-04 — No “hidden control plane” behavior changes

Obs/Gov cannot “secretly change” IEG behavior.
The only allowed influence on runtime behavior is via explicit modes (pause/drain) and the platform’s explicit degrade posture (DL→DF), not by silent toggles.

---

## 2) Internal non-joins between IEG subnetworks (S1–S8 + ST)

### PIN-NONJOIN-INT-01 — S6 (indices) never owns truth

* **S6 must not** compute or publish `graph_version`. That is **S7-only**.
* **S6 must not** advance offsets/checkpoints.
* **S6 must not** serve data “ahead” of the basis S7 attaches (no lying snapshots).

### PIN-NONJOIN-INT-02 — S7 (versioning/lineage) never mutates graph content

* **S7 must not** create/modify entities, aliases, or edges.
* **S7 must not** “repair” missing identity hints.
  S7 is the *meter*, not the *machine*.

### PIN-NONJOIN-INT-03 — S8 (serving/ops façade) is read-only for A2 queries

* **S8 must not** write to identity/edges/indices/watermarks as a side-effect of serving queries.
* **S8 must not** invent `graph_version`; it must come from S7.
  (Serving emits telemetry; it does not mutate projection state.)

### PIN-NONJOIN-INT-04 — S5 (edges) cannot mint entities

* **S5 must not** create EntityRefs.
  If an endpoint doesn’t exist, that’s an apply failure / conflict, not “autocreate.”

### PIN-NONJOIN-INT-05 — S4 (identity) does not create edges

* S4 can create entities and identifier claims only; it does not form relationships.

### PIN-NONJOIN-INT-06 — S2 must not reorder or buffer past offsets

* **No re-ordering within a partition**.
  S2 may classify/scope, but it cannot feed S3 offset N+1 before N.

### PIN-NONJOIN-INT-07 — Query plane must never write into ST

* **S6↔ST** is read-only.
* No “write-through cache,” no “on read we backfill missing indices,” no “on query we create entity if missing.”
  Anything that mutates goes through the apply spine (S3→ST).

### PIN-NONJOIN-INT-08 — No cross-generation mixing

During rebuild, **queries must not read from both ACTIVE and BUILDING generations**.
Every query is served from exactly one `projection_generation_id` and stamped as such.

### PIN-NONJOIN-INT-09 — No implicit integrity reset

Integrity cannot silently flip from DEGRADED→CLEAN.
The only way to restore CLEAN is via an explicit A4 generation rebuild/cutover (or an explicitly declared integrity-reset op with auditable lineage).

---

## 3) Prohibited composite paths (anti-paths) we explicitly ban

### PIN-NONJOIN-ANTIPATH-01 — “skip the bad offset” dead-letter bypass

Not allowed: `S3 sees bad event → drop it → jump watermark`.
Allowed: `INVALID_RECORDED` + integrity degraded + watermark advances only after durable recording.

### PIN-NONJOIN-ANTIPATH-02 — “serve latest even if indices lag”

Not allowed: `S7 returns new graph_version → S6 answers from stale index state`.
If indices are ever async, we must introduce **index-basis gating** and serve `min(projection_basis, index_basis)` (or refuse strict requests). But v0 bans “stale indices with advanced version.”

### PIN-NONJOIN-ANTIPATH-03 — payload-semantics parsing in Intake

Not allowed: `S1 reads business payload and infers identity fields ad hoc`.
IEG is payload-blind beyond a **standardized identity-hints block**; otherwise we’ll encode business semantics into the identity plane and drift across producers.

### PIN-NONJOIN-ANTIPATH-04 — “auto-merge” inside IEG

Not allowed: IEG collapsing two entities into one (“merge”).
Allowed: aliases/links + conflict sets + multi-candidate resolution.

### PIN-NONJOIN-ANTIPATH-05 — “implicit backfill”

Not allowed: “We upgraded code, restarted, and the projection changed silently.”
Allowed: explicit rebuild/backfill operation → new `projection_generation_id` → explicit cutover → decisions can cite which generation was used.

---

## 4) Quick “must-not-exist edges” list (internal adjacency bans)

* **S8 → S4/S5/S6 writes** (query side-effects) ❌
* **S6 → S7** (indices defining graph_version) ❌
* **S7 → S4/S5** (versioning mutating graph content) ❌
* **S5 → S4** (edges minting identity) ❌
* **S4 → S5** (identity fabricating edges) ❌ *(S3 orchestrates both)*
* **Any → ST writes** except via the S3 apply unit ❌
* **ST → EB** (derived store emitting truth) ❌
* **Any producer → IEG** direct feed bypassing EB ❌ 

---

## USER: PAUSE FOR REFLECTION

Here’s the **design I’m holding as authoritative** after our brainstorm—both the **outer network placement** of IEG *and* the **first-layer illuminated internal network** (still opaque boxes), plus the **rails/non-joins** that prevent drift as we go deeper.

---

## 1) IEG’s role in the larger platform network

### What IEG *is*

* **Always-on EB consumer / projector**: it consumes **admitted canonical events** from the Event Bus and materializes **queryable identity + relationship context**. 
* It is authoritative only for:

  * **its projection artifacts** (entities/edges/indices), and
  * **`graph_version`** (the “how far applied” token). 

### What IEG is *not*

* Not admission/quarantine (IG owns that).
* Not truth source (EB + SR/engine surfaces are truth).
* Not feature plane (OFP owns features).
* Not decisioning (DF owns decisions).
* Not audit recorder (DLA owns audit). 

### The upstream ingestion fork we pinned (so IEG’s assumptions are stable)

* **Pull model v0**: SR READY → IG pulls engine `business_traffic` refs → wraps canonical envelope → admits into EB. This keeps “READY before traffic” and preserves trust boundaries. 

---

## 2) The outer production joins incident to IEG

**Mandatory joins**

1. **EB → IEG projector** (J-IEG-IN-1)

   * at-least-once delivery, partition-ordered only, duplicates expected.
2. **IEG → derived store + checkpoints** (J-IEG-OUT-1)

   * derived/rebuildable, but checkpointed; must not “lie” about applied basis.
3. **DF ⇄ IEG query** (J-IEG-OUT-2A)

   * DF may call IEG directly; must record `graph_version` used.
4. **OFP ⇄ IEG query** (J-IEG-OUT-2B)

   * OFP may consult IEG and must stamp `graph_version` into feature provenance.
5. **IEG → Obs/Gov** (J-IEG-OPS-1)

   * lag/watermark/integrity/health signals feed DL corridor checks.
6. **Run/Operate ⇄ IEG rebuild/backfill** (J-IEG-OPS-2)

   * declared replay/backfill; explicit cutovers; never rewrite truth.

**Optional join**
7) **IEG → audit pointer stream** (J-IEG-OUT-3)

* milestones only; not a second truth feed.

---

## 3) The pinned semantics that everything hangs off

These are the “don’t drift” core laws:

* **Scope**: strictly run/world-scoped by **ContextPins** `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`. 
* **Event-time**: domain time is **envelope `ts_utc`** (we don’t collapse ingest/apply time into it). 
* **Idempotency**: `update_key = H(ContextPins + event_id + ieg_update_semantics_v0)`; duplicates → logical no-op.
* **graph_version meaning**: `graph_version = (stream_name + per-partition next_offset_to_apply vector)` with **exclusive-next** offsets.
* **No merges (v0)**: IEG returns conflicts/multiple candidates; it does not collapse entities.
* **Explicit degrade**: integrity/lag signals are surfaced; DL constrains DF; DLA records posture. 

**Known boundary tension we pinned early:** IEG requires envelope-visible identity hints (`observed_identifiers[]` concept), but the current canonical envelope doesn’t include it; so the platform must supply a **standard identity-hints block** at the bus boundary (envelope vNext or reserved payload block)—IEG remains “payload-blind” beyond that. 

---

## 4) The outer paths & loops that touch IEG (production reality)

**Paths**

* **P2**: IG→EB→IEG→DF (DF calls IEG directly)
* **P3**: DF→(IG→EB)→AL→(IG→EB)→IEG (actions/outcomes feed back)
* **P4**: decision provenance includes graph_version → DLA audit record
* **P5**: audit + EB/Archive → offline parity → MF/MPR → registry activation → DF behavior shift
* **P6**: declared replay/backfill → rebuild derived state (no truth rewrite)

**Loops**

* **L1** runtime decision/action feedback loop
* **L2** observability/degrade control loop (Obs→DL→DF)
* **L3** learning evolution loop
* **L4** backfill correction loop (explicit, auditable correction without overwriting history)

---

## 5) Environment ladder implications we pinned for IEG

**Invariant across envs**: same semantics, same rails, same join meaning. Only *profiles* differ.

**Allowed knobs (per environment profile)**

* EB partitions/concurrency; batch sizes; in-flight caps
* retention + archive availability/horizon
* checkpoint durability/HA posture
* auth strictness (query surface, topic ACLs, DB creds)
* observability sampling/verbosity/SLO thresholds
* DL corridor thresholds for “IEG usable”
* backfill governance strictness (approvals, who can execute) 

---

## 6) First layer inside the vertex: internal subnetworks (still opaque boxes)

We decomposed IEG into a minimal, drift-resistant Level-1 internal network:

* **S1 Projector Intake**
* **S2 Scope Router**
* **S3 Idempotent Apply Coordinator**
* **S4 Canonical Identity**
* **S5 Relationships / Edges**
* **S6 Projection Indices**
* **S7 Versioning & Lineage**
* **S8 Serving & Ops Facade**
* **ST Derived Store + Checkpoints** (durable substrate)

---

## 7) Internal planes and joins we illuminated

### A1 Ingest-and-apply spine (J-IEG-1 … J-IEG-8)

* S1→S2 (normalize + extract scope/hints)
* S2→S3 (scoped candidate)
* S3→S4 (identity mutations)
* S3→S5 (edge mutations)
* S4↔S5 (endpoint canonicalization dependency)
* S4/S5→S6 (index maintenance)
* S3↔S7 (apply outcome ↔ watermark/integrity)
* all → ST (durable apply unit)

### A2 Query/serve plane (J-IEG-9 … J-IEG-12)

* S8↔S6 (query orchestration/execution)
* S8↔S7 (serve basis decision + integrity gating + min-basis checks)
* S6↔ST (snapshot-consistent reads)
* S7↔ST (basis/integrity/generation truth)

### A3 Ops plane (J-IEG-13 … J-IEG-15)

* S7→S8 (ProjectionStatusFrame truth)
* S8→Obs (metrics/logs/traces; environment knobs only)
* S8→S1/S3 (throttle/pause/drain/resume backpressure controls)

### A4 Backfill/rebuild plane (J-IEG-16 … J-IEG-19)

* Run/Operate→S8 (declared commands)
* S8↔S7 (generation plan + explicit cutover semantics)
* S7→S1 (replay basis frames)
* S8↔ST (routing reads/writes by generation; no mixed-generation reads)

### A5 Optional pointer emission plane (J-IEG-20)

* S7/S8 → pointer emitter (milestones only; not decisionable truth)

---

## 8) Internal paths we pinned

* **P-INT-1** APPLIED (mutates graph, advances basis)
* **P-INT-2** DUPLICATE_NOOP (no mutation, advances basis; mismatch becomes INVALID_RECORDED)
* **P-INT-3** IRRELEVANT_NOOP (no mutation, advances basis)
* **P-INT-4** INVALID_RECORDED (no mutation, advances basis, integrity degraded)
* **P-INT-5/6** queries (resolve/profile/neighbors) with *no lying snapshots* and basis stamping
* **P-INT-7** status/health (truthful ops view)
* **P-INT-8** declared replay/backfill build → explicit cutover

---

## 9) Internal loops we pinned

* **L-INT-1** continuous projector loop (consume→apply→commit→checkpoint→repeat)
* **L-INT-2** restart/rebalance loop (resume from S7 durable basis; safe under redelivery)
* **L-INT-3** integrity degradation loop (failure→integrity explicit→telemetry→DL constrains DF)
* **L-INT-4** backpressure loop (saturation→throttle/pause/drain→stabilize→resume)
* **L-INT-5** rebuild/cutover loop (declared basis→new generation→explicit cutover)

---

## 10) The non-joins we banned (drift blockers)

Key “must-not-exist” edges/anti-paths:

* No producer writes directly into IEG (no side door bypassing IG→EB).
* IEG does not emit decisionable traffic back into EB.
* Query plane is read-only (no “write on read,” no implicit repair).
* S6 does not own `graph_version`; S7 does not mutate graph content; S5 cannot mint entities; S4 does not create edges.
* No cross-generation mixed reads; integrity does not auto-reset; no “skip bad offset.” 

---

## What this reflection is for (my drift guard)

When we start opening modules, I will keep these as the “boundary contract checklist”:

1. Does the internal design preserve **ContextPins scoping**?
2. Does it remain safe under **duplicates/out-of-order**?
3. Does it keep **update_key** and **graph_version basis** exactly as pinned?
4. Does it maintain **explicit integrity + explicit degrade** behavior?
5. Does it prevent **non-joins** (side doors, write-on-read, second truth feeds)?
6. Does it remain **environment-invariant semantics** with profile knobs only?

---

Yep — this is the right moment to **pin the deployment + environment-ladder stance** for the *IEG inner network* (S1–S8 + ST), so Codex can implement without inventing “prod-only semantics” later.

Everything below is **designer-authoritative** and must remain consistent with your ladder rule: **same semantics everywhere; only the operational envelope/profile changes**.  

---

## 1) Deployment units to hold constant across the ladder

### PIN-DEP-IEG-01 — IEG is always an always-on projector

The **projector role** (consume EB → apply → checkpoint → graph_version) is non-negotiable in every environment.  

### PIN-DEP-IEG-02 — One logical vertex, optionally two runtime services

Treat IEG as **one component** with **two optional deployable services**:

1. **`ieg-projector`** (mandatory)
   Owns **S1–S7** + writes to **ST**.

2. **`ieg-serve`** (optional but recommended in production shape)
   Owns **S8** (+ read-only S6/S7/ST access).

**Local/dev can collapse them into one process**, but the *logical separation* must remain (so we don’t drift on read/write coupling and so you can scale query independently later). 

### PIN-DEP-IEG-03 — ST is a durable derived store, not a cache

ST is **durable projection state + checkpoints**. It is rebuildable from EB/Archive, but it is not “optional memory.” It must survive restarts and support explicit generations/cutovers.  

---

## 2) Consumer group + scaling stance (how we scale without breaking semantics)

### PIN-DEP-IEG-04 — Scale by partitions, not by “free parallelism”

* `ieg-projector` scales horizontally by **consumer group membership**: at most one active consumer per partition at a time.
* Any per-partition concurrency is an **implementation optimization**, but must preserve:

  * in-partition order processing, and
  * “one durable outcome per offset” (our Apply Unit).

### PIN-DEP-IEG-05 — DB checkpoint is the truth; bus commits are hints

IEG’s **resume basis** is S7→ST (`next_offset_to_apply` vector), not “whatever the broker says.”
Broker commits may exist for operational convenience, but **must never outrank** the durable basis in ST. 

---

## 3) Environment ladder: what is allowed to vary vs must not vary

### Must not vary (semantic invariants)

* **IG→EB is the only entry door** for decisionable facts. 
* **Canonical envelope semantics** (event_id/event_type/ts_utc/pins) are unchanged across envs. 
* **update_key + graph_version meaning** unchanged.
* **No merges** unchanged.
* **Degrade is explicit** (signals → DL mask → DF obeys → DLA records). 
* **Backfills are declared + auditable; no truth rewrite**.  

### Allowed to vary (profile knobs)

* EB partition count, batching, concurrency
* Retention window + archive availability/horizon
* HA/replica count + durability settings (checkpoint frequency, fsync posture)
* Auth strictness on query surface (none/dev creds locally → real auth in dev/prod)
* Observability sampling/verbosity + SLO thresholds
* DL corridor thresholds for “IEG usable”
* Backfill governance strictness (approvals, who can run, frequency)

All of these must be expressed as **environment-profile artifacts**, not code forks. 

---

## 4) Minimum “profile knobs” I want Codex to externalize (so we don’t drift later)

Think of this as `ieg.profile.yaml` categories (not asking you to write docs—just pinning what must be configurable).

### Intake / apply knobs (S1/S2/S3)

* `stream_name` / topic id for admitted traffic
* `consumer_group_id`
* `max_inflight_apply_units`
* `max_batch_size_records`
* `max_batch_age_ms`
* `throttle_policy` (on/off, rates)
* `poison_policy` (how INVALID_RECORDED is surfaced; never stall forever)

### Versioning / lineage knobs (S7)

* `projection_generation_id` handling (enabled always; format flexible)
* `integrity_policy`:

  * what counts as integrity-degrading (missing pins/hints, mismatch duplicates, internal errors)
  * whether STRICT queries require integrity clean
* `basis_digest_algo` (format, not meaning)

### Store knobs (ST)

* DSN/connection pool sizes
* transaction isolation / snapshot mode for A2 reads (or equivalent)
* schema migrations enabled/disabled per env
* retention for old generations (keep N gens in dev/prod; maybe 1 in local)

### Serving knobs (S8)

* query auth mode (none/dev/prod)
* request timeouts per op
* max neighbors limit / max page size
* load shedding on/off (return `IEG_BUSY` instead of timing out)

### Observability knobs (A3)

* OTLP exporter endpoint
* trace sampling rate
* log verbosity
* alert thresholds (lag, watermark age, query latency, integrity degraded)

### Backfill knobs (A4)

* who can execute (policy)
* max replay window / max concurrency
* serve behavior during rebuild (serve old vs refuse strict)
* cutover policy (auto vs manual confirm)

---

## 5) Operational modes that must exist (and be visible)

Codex should implement these **as explicit modes surfaced by S7→S8 status + telemetry**:

* `RUNNING`
* `THROTTLED`
* `PAUSED`
* `DRAINING`
* `REBUILDING`
* `CUTOVER_IN_PROGRESS`

No mode is allowed to be “implicit.” If we’re draining or rebuilding, DF/OFP operators must be able to see it, and strict queries must be able to refuse. 

---

## 6) Deployment “corridor checks” for readiness (not spec, just direction)

I want two health gates (works in local too, just different thresholds):

### `liveness`

* process alive, can reach ST, can emit telemetry

### `readiness`

* ST reachable and schema OK
* projector has a valid active generation
* checkpoints are readable
* not stuck in permanent DRAINING/REBUILDING unless explicitly allowed

Readiness should **not** require “zero lag”; lag is normal. But readiness must reflect “can we operate safely under our profile.”

---

## 7) Production-shaped local stack (directional, not binding)

To prevent “it worked locally but not in prod,” local should include:

* a Kafka-ish bus (partitions/offsets/consumer groups),
* a SQL-ish durable store for ST,
* an OTLP collector pipeline (even if everything prints to console). 

---

## 8) One extra pin that protects explainability across rebuilds

### PIN-DEP-IEG-06 — Always stamp generation + graph_version

Any outward-facing response that used IEG context (DF/OFP provenance, IEG query responses, ops pointers) must be stampable with:

* `projection_generation_id`
* `graph_version` (basis token)

This is the “no stealth semantics change” guarantee when you backfill or upgrade.  

---

### Nodes (Level-1 subnetworks) in the IEG vertex

1. **S1 Projector Intake**
2. **S2 Scope Router**
3. **S3 Idempotent Apply Coordinator**
4. **S4 Canonical Identity**
5. **S5 Relationships / Edges**
6. **S6 Projection Indices**
7. **S7 Versioning & Lineage**
8. **S8 Serving & Ops Facade**

* **ST Derived Store + Checkpoints** (durable substrate the nodes share)

### Order I recommend we illuminate (drift-minimizing)

1. **S7 Versioning & Lineage** (truth anchor: `graph_version`, generations, integrity, resume basis, rebuild basis)
2. **ST Derived Store + Checkpoints** (what must be durable/atomic to keep S7 truthful)
3. **S3 Idempotent Apply Coordinator** (Apply Unit logic; update_key; failure classification)
4. **S1 Projector Intake** (canonical parsing + identity-hints normalization without payload semantics)
5. **S2 Scope Router** (ContextPins isolation + routing; simplest once S1/S3/S7 are pinned)
6. **S4 Canonical Identity** (no-merge resolution, deterministic entity minting, alias/index rules)
7. **S5 Relationships / Edges** (edge identity, timestamp rules, ambiguity posture, provenance)
8. **S6 Projection Indices** (deterministic query projections + ordering/pagination rules)
9. **S8 Serving & Ops Facade** (query semantics, basis gating, errors, telemetry, backpressure controls)

That order matches the dependency spine we already pinned: **S7/ST/S3 define truth + durability**, then **S1/S2 define what enters**, then **S4/S5 define what gets mutated**, then **S6/S8 define what gets served and observed**.

---

Alright — we’re opening **S7: Versioning & Lineage** and exposing the machinery inside it. This **doesn’t change the network** we already pinned; it’s the internal mechanism that makes those pins *true in production* (truthful `graph_version`, exclusive-next offsets, explicit integrity, explicit generations/cutovers, declared replay).  

---

## S7’s job (one sentence)

**S7 is the sole internal authority for “what has been applied” and “under what lineage,”** expressed as:

* `graph_version = (stream_name + per-partition next_offset_to_apply vector)` with **exclusive-next** semantics, and
* `projection_generation_id` + integrity/mode state. 

Everything else (S1/S3/S4/S5/S6/S8) *must* treat S7’s basis as the truth stamp.

---

## The boundary interfaces S7 owns (what it talks to)

### From S3 (apply outcomes)

S7 receives **exactly one ApplyOutcome per (partition, offset)**:

* `APPLIED | DUPLICATE_NOOP | IRRELEVANT_NOOP | INVALID_RECORDED`
* plus typed reasons (for INVALID), and correlation keys.

This is the input that drives watermark advancement + integrity changes. 

### To S1 (resume/replay basis)

S7 publishes **ConsumptionBasisFrame** (what to read next):

* active `projection_generation_id`
* mode `INCREMENTAL | REPLAY`
* per-partition `next_offset_to_apply` (or replay start/end offsets)
* maintenance flags (PAUSED/DRAINING/REBUILDING).

This is how restarts/rebalances become deterministic. 

### From S8 (serve basis decisions & rebuild orchestration)

S7 answers:

* **ServeBasisDecision**: “OK / LAGGING / INTEGRITY_DEGRADED / REBUILDING …” + basis token.
* **Generation plan / cutover**: create BUILDING generation, mark READY_TO_CUTOVER, activate cutover, retire old generation.

This is how queries never “lie” and rebuilds are explicit.  

### To/From ST (durable truth)

S7 reads/writes durable state for:

* checkpoints (next offsets),
* generation registry,
* integrity ledger,
* rebuild operations.

**Durability is non-negotiable**: S7 cannot be “in-memory truth.” 

---

## S7’s internal subnetworks (inside S7, one level deeper)

Think of S7 as five opaque “gears” that together produce truth.

### S7.1 Generation Registry

Owns:

* `projection_generation_id` lifecycle (ACTIVE / BUILDING / READY_TO_CUTOVER / FAILED / RETIRED)
* mapping: scope-selector → active generation
* linkage: operation_id → generation_id (for backfill/replay auditability)

**Pin enforced here:** *explicit generations + explicit cutover; no stealth overwrites.* 

---

### S7.2 Partition Watermark Ledger

Owns (per generation, per partition):

* `next_offset_to_apply` (exclusive-next)
* optional: `last_processed_event_ts_utc` (for watermark-age metrics)
* optional: `last_processed_offset_committed_at`

**Pin enforced here:** offsets are the universal progress token; exclusive-next semantics. 

---

### S7.3 GraphVersion Encoder

Owns:

* canonical encoding of `graph_version` from `(stream_name + watermark vector)`
* canonical hashing/digest (`basis_digest`) for compact logging/provenance
* comparison semantics (“is basis A at least basis B?”)

**Pin enforced here:** graph_version meaning is fixed; only representation is flexible. 

---

### S7.4 Integrity Ledger

Owns:

* `integrity_status = CLEAN | DEGRADED | UNKNOWN`
* typed failure counters (missing pins, missing id hints, malformed, mismatch duplicate, apply error, index error)
* `first_failure_position` and `last_failure_position` (partition/offset)
* “integrity reset only via explicit rebuild/cutover”

**Pin enforced here:** degrade is explicit and integrity does not auto-reset. 

---

### S7.5 Basis Resolver

Owns:

* serve-time decisions (for S8):

  * min_graph_version checks (“don’t serve if older than X”)
  * integrity gates (STRICT vs BEST_EFFORT)
  * maintenance gates (REBUILDING/PAUSED)
* resume-time decisions (for S1):

  * authoritative start offsets for incremental or replay.

**Pin enforced here:** “no lying snapshots” and explicit error posture. 

---

## The durable model S7 expects ST to provide (logical, not implementation)

This is what *must be durably representable* so S7 can be truthful:

### 1) `ieg_generation_registry`

* `generation_id`
* `state` (ACTIVE/BUILDING/…)
* `stream_name`
* `created_at`, `activated_at`, `retired_at`
* `operation_id` (if created by backfill)
* `parent_generation_id` (optional lineage)
* `active_pointer` per scope-selector

### 2) `ieg_partition_checkpoint`

* `generation_id`
* `partition_id`
* `next_offset_to_apply` (**exclusive-next**)
* `last_event_ts_utc` (optional, for watermark-age)
* `updated_at`

### 3) `ieg_integrity_ledger`

* `generation_id`
* `integrity_status`
* `failure_counts_by_reason`
* `first_failure_partition/offset`
* `last_failure_partition/offset`
* `integrity_reset_operation_id` (set only when a rebuild explicitly resets it)

### 4) `ieg_backfill_ops`

* `operation_id`
* `generation_id`
* `basis` (start/end offsets per partition, plus stream identity)
* `status` (ACCEPTED/RUNNING/COMPLETED/FAILED/ABORTED)

This is enough to support *all* pinned A4 semantics without over-specifying storage tech.  

---

## The two most important S7 flows (how the machinery works)

### Flow A: “Truthful advance” during normal apply (S3 ↔ S7 ↔ ST)

Goal: **one durable outcome per offset, then advance `next_offset_to_apply = offset+1`.**

**Mechanism (conceptual):**

1. S3 asks S7: “what offset is expected next for this partition/generation?”
2. S3 processes `(partition, offset)` and decides the ApplyOutcome.
3. S7 produces a **CheckpointDelta**:

   * set `next_offset_to_apply := offset+1`
   * update integrity ledger if needed
4. **ST commit** persists:

   * the apply outcome record,
   * the CheckpointDelta,
   * (and any graph mutations from S4/S5/S6 if APPLIED).
5. Only after commit does S7 treat the basis as advanced.

**Why this matters:** it enforces “watermarks don’t lie.” 

---

### Flow B: Serve-basis decision for queries (S8 ↔ S7 ↔ ST)

Goal: ensure every query response has a **truthful basis stamp** and does not read across inconsistent states.

**Mechanism (conceptual):**

1. S8 opens a **read snapshot** against ST.
2. S8 asks S7 (within that snapshot): “what is the serve basis + integrity + generation?”
3. S7 returns:

   * `projection_generation_id`
   * `graph_version` (or basis_digest + token)
   * `integrity_status`
   * decision: OK/LAGGING/INTEGRITY_DEGRADED/REBUILDING/…
4. S8 executes the read via S6 in the **same snapshot** and returns results stamped with S7’s basis.

**Why this matters:** “no lying snapshots,” deterministic provenance. 

---

## Rebuild/backfill lineage inside S7 (A4 support, briefly but concretely)

S7.1 + S7.2 + S7.5 together enforce:

1. **Create BUILDING generation** with explicit replay basis (start/end offsets).
2. **Publish replay ConsumptionBasisFrame** to S1.
3. Track checkpoints until end offsets reached → mark READY_TO_CUTOVER.
4. On cutover request:

   * atomically switch ACTIVE pointer to new generation,
   * retire old generation (or keep for investigations),
   * integrity becomes “clean” only because the generation changed (explicit lineage).  

---

## S7’s “design authority decisions” (to prevent later drift)

### Decision 1: `graph_version` is always paired with `projection_generation_id`

Even if offsets are the same, **generation disambiguates semantics** after rebuilds or code changes. This is how we prevent stealth changes. 

### Decision 2: Integrity never auto-resets

Once DEGRADED, it stays DEGRADED until an explicit rebuild/cutover (or an explicitly declared integrity-reset op with lineage). 

### Decision 3: Comparability rules are strict

S7 compares `graph_version` only when:

* stream_name matches, and
* generation context is compatible (same generation or explicitly declared lineage mapping).
  Otherwise it returns “incompatible basis” rather than pretending. 

---

## What S7 must *not* do (non-joins, reiterated)

* Must not mutate entities/edges/indices.
* Must not parse business payloads.
* Must not “fix” missing identity hints.
* Must not advance offsets unless the durable commit justifies it.

---

If you’re happy with S7’s machinery, the clean next illumination step is **ST (Derived Store + Checkpoints)**, because S7’s truthfulness depends on *how ST commits the Apply Unit atomically/coherently* across (mutations + update ledger + checkpoint + integrity).

---

Alright — we’re opening **ST: the Derived Store + Checkpoints** and exposing the machinery inside it.

ST is the *durability engine* that makes S7’s truth possible: **no lying `graph_version`, explicit generations, restart-safe idempotency, snapshot-consistent reads, declared rebuilds/cutovers**. This is still design-level (not a DB-specific spec), but it’s concrete enough that Codex won’t invent semantics.

---

## What ST is responsible for

### ST’s mission

Provide **durable, queryable, rebuildable projection state** such that:

1. **Every EB offset processed has exactly one durable outcome**
   (`APPLIED | DUPLICATE_NOOP | IRRELEVANT_NOOP | INVALID_RECORDED`)

2. **`next_offset_to_apply` is exclusive-next and truthful**
   It advances to `offset+1` **only when the outcome is durable**.

3. **A query sees one coherent snapshot**
   Reads must be consistent with the `graph_version` S7 stamps.

4. **Generations are explicit**
   Rebuild/backfill writes into a BUILDING generation; cutover is explicit; queries never mix generations.

---

## ST’s internal “gears” (subnetworks inside ST)

Think of ST as six internal boxes (still machinery-level, not DB-level):

### ST.1 Generation Router

* Owns: **which generation is ACTIVE**, which is BUILDING, and which one queries/writes target.
* Enforces: **no mixed-generation reads** and explicit routing changes during cutover.

### ST.2 Apply Unit Transaction Engine

* Owns: the **atomic commit contract** for one `(partition, offset)` apply.
* Enforces: “watermarks don’t lie” by committing **outcome + mutations + ledger + checkpoint** coherently.

### ST.3 Graph State Families

* Owns: the **canonical projection data**:

  * entities + identifier claims (aliases)
  * edges/relationships
* Enforces: no merges (by data model posture), and provenance linkage.

### ST.4 Index Families

* Owns: read-optimized structures for:

  * resolve_identity
  * neighbors
  * profile reads
* **v0 pinned stance:** indices are updated *synchronously* inside the apply unit (so there’s no “index lag” vs `graph_version`).

### ST.5 Versioning & Integrity Families

* Owns: durable tables that S7 reads/writes:

  * per-partition checkpoints (`next_offset_to_apply`)
  * integrity status + failure summaries
  * generation registry + backfill ops metadata

### ST.6 Snapshot Reader

* Owns: the “no lying snapshots” read discipline:

  * open a stable read snapshot
  * read routing + basis + integrity within that snapshot
  * run index reads within that same snapshot

---

## The durable data families ST must support (logical tables / keyspaces)

I’m not dictating SQL vs KV; I’m dictating **what must be representable** and the **keys/invariants**.

### 1) Generation registry and routing (ST.1)

**`ieg_generation_registry`**

* Key: `(generation_id)`
* Fields: `state (ACTIVE|BUILDING|...)`, `stream_name`, `created_at`, `activated_at`, `retired_at`,
  `operation_id` (if created by backfill), optional `parent_generation_id`

**`ieg_generation_routing`**

* Key: `(scope_selector)` (v0 may treat “global scope” if you don’t shard by scope)
* Fields:

  * `active_generation_id`
  * `building_generation_id?`
  * `read_target_generation_id`
  * `write_target_generation_id`
  * `maintenance_mode` (NONE|REBUILDING|PAUSED|DRAINING|CUTOVER)

**Invariant:** a single query reads from exactly **one** `read_target_generation_id`.

---

### 2) Partition checkpoints / watermark basis (ST.5)

**`ieg_partition_checkpoint`**

* Key: `(generation_id, partition_id)`
* Fields:

  * `next_offset_to_apply` (**exclusive-next**)
  * optional `last_event_ts_utc` (for watermark-age)
  * `updated_at`

**Invariant:** `next_offset_to_apply` advances only after the apply unit is durable.

---

### 3) Apply outcome log (ST.2/5)

**`ieg_offset_outcome`**

* Key: `(generation_id, partition_id, offset)`
* Fields:

  * `classification` (APPLIED|DUPLICATE_NOOP|IRRELEVANT_NOOP|INVALID_RECORDED)
  * `reason?` (typed for INVALID, and for “duplicate mismatch”)
  * `event_id`, `event_type`, `ts_utc`
  * `scope_key?` (if present)
  * `update_key?` (if scoped)
  * `created_at`

**Invariant:** exactly one outcome row exists per processed offset per generation.

---

### 4) Update ledger (idempotency) (ST.2/3)

**`ieg_update_ledger`**

* Key: `(generation_id, scope_key, update_key)`
* Fields: `first_seen_partition/offset`, `first_seen_ts_utc`, `applied_at`

**Invariant:** if a second offset produces the same update_key:

* it is `DUPLICATE_NOOP`, unless it conflicts on envelope-critical identity (then it’s `INVALID_RECORDED(DUPLICATE_MISMATCH)`).

---

### 5) Integrity ledger + failure summaries (ST.5)

**`ieg_integrity_ledger`**

* Key: `(generation_id)` (optionally also `(generation_id, scope_key)` as an on-demand drilldown)
* Fields:

  * `integrity_status` (CLEAN|DEGRADED|UNKNOWN)
  * `failure_counts_by_reason`
  * `first_failure_partition/offset`
  * `last_failure_partition/offset`
  * `integrity_reset_operation_id?` (set only by explicit rebuild/cutover)

**Invariant:** integrity never auto-resets.

---

### 6) Graph projection state (ST.3)

**Entities**

* Key: `(generation_id, scope_key, entity_type, entity_id)`
* Fields (v0 thin): `created_at`, `first_seen_ts_utc`, `last_seen_ts_utc`, optional minimal tags

**Identifier claims / alias index**

* Key: `(generation_id, scope_key, identifier_key, entity_type, entity_id)`
* Fields: `first_seen_ts_utc`, `last_seen_ts_utc`, optional claim strength/source

**Edges**

* Key: `(generation_id, scope_key, edge_type, src_entity_ref, dst_entity_ref)`
* Fields: `first_seen_ts_utc`, `last_seen_ts_utc`, `provenance_first`, `provenance_last`

**Invariant:** no merge semantics are encoded here; conflicts are represented by “identifier maps to multiple entities” rather than collapsing.

---

### 7) Read indices (ST.4)

At minimum, ST must support read patterns efficiently:

* **Resolve identity:** identifier_key → {candidate EntityRefs}
* **Neighbors:** entity_ref → adjacency list (with stable ordering keys)
* **Profile:** entity_ref → thin profile view

**v0 pin:** indices are updated inside the apply unit. If you later go async, we must add an index-basis and serve `min(projection_basis, index_basis)` — but v0 forbids “advanced graph_version with stale indices.”

---

### 8) Backfill operations (ST.5)

**`ieg_backfill_ops`**

* Key: `(operation_id)`
* Fields:

  * `generation_id`
  * `scope_selector`
  * `basis` (start/end offsets per partition, stream identity)
  * `status` (ACCEPTED|RUNNING|COMPLETED|FAILED|ABORTED)
  * `created_at`, `completed_at`
  * `approval_ref` / `policy_rev`

This is what makes rebuilds “declared and auditable.”

---

## The Apply Unit commit contract (ST.2) — the heart of “no lying versions”

For each EB record at `(partition, offset)` the commit must make **one coherent truth** durable:

### Always durable (for every offset)

* `ieg_offset_outcome(generation, partition, offset)` row inserted
* `ieg_partition_checkpoint.next_offset_to_apply := offset + 1` updated

### Durable when scoped

* `ieg_update_ledger` insert/check (so replay/duplicates are safe)

### Durable when APPLIED

* entity/identifier claim updates
* edge updates
* index updates (v0 synchronous)

### Durable when INVALID_RECORDED

* integrity ledger updated (DEGRADED + counters + first/last failure positions)

**Pinned invariant:** checkpoints cannot advance without a durable outcome row, and (for APPLIED) without the durable mutations the outcome implies.

---

## Read snapshot discipline (ST.6) — “no lying snapshots”

A query must be served from a **single generation** and consistent with the returned basis.

### Canonical query read procedure (what ST must enable)

1. Open a stable read snapshot (DB tx / MVCC snapshot / equivalent)
2. Read:

   * `read_target_generation_id` (routing)
   * basis (`next_offset_to_apply` vector or digest)
   * integrity status
     all within that snapshot
3. Execute index reads within the same snapshot
4. Return results + stamps:

   * `projection_generation_id`
   * `graph_version` (or basis token)
   * `integrity_status`

This is how S8 can attach S7’s basis without ever “overstating” what the query saw.

---

## Generation build & cutover (ST.1 + ST.5) — what ST must make safe

### Side-by-side build (v0 default)

* BUILDING generation gets its own keyspace (via generation_id column or separate schema)
* writes go to BUILDING while reads continue from ACTIVE

### Cutover steps ST must support (explicit)

* Drain in-flight applies (outside ST; enforced by S8/S3)
* Atomically switch `read_target_generation_id` to BUILDING
* Switch `write_target_generation_id` to BUILDING
* Mark BUILDING as ACTIVE; retire old ACTIVE

**Invariant:** no query reads across generations; no mixed “old edges, new aliases” response.

---

## ST non-joins (what ST must NOT do)

* ST must not become a “second event bus” (no decisionable events emitted from ST).
* Query reads must not mutate (“write on read” is banned).
* ST must not autonomously backfill/repair; rebuild is only via declared A4 operations.
* ST must not accept writes that bypass the apply unit coordinator (S3); all mutations are apply-unit driven.

---

## Environment ladder knobs specific to ST (allowed differences)

These are *profile knobs*, not semantic forks:

* checkpoint commit frequency (still exclusive-next truth)
* transaction isolation/read snapshot method (must preserve semantics)
* retention of old generations (keep N gens)
* retention of `ieg_offset_outcome` rows (may compact after a horizon)
* storage tuning: connection pools, batch sizes, fsync posture
* auth: DB creds/ACL strictness

---

If you’re aligned with this ST machinery, the next clean node to open is **S3 (Idempotent Apply Coordinator)**, because ST + S7 define “what must be durable,” and S3 defines “how we decide the per-offset outcome and assemble the apply unit.”

---

Alright — opening **S3: Idempotent Apply Coordinator** and exposing the machinery inside it.

S3 is the **spine brain** of IEG: it takes a *scoped candidate event* (already parsed/normalized by S1/S2), decides **exactly one** outcome for that EB offset, orchestrates mutations (if any), and ensures the store + checkpoints + integrity never drift from the pinned meaning.

---

## What S3 owns and what it absolutely does not own

### S3 owns

* The **Apply Unit** for one `(generation_id, partition, offset)`.
* **Classification** into one of:

  * `APPLIED`
  * `DUPLICATE_NOOP`
  * `IRRELEVANT_NOOP`
  * `INVALID_RECORDED` (typed reason)
* **Idempotency** via `update_key = H(scope_key + event_id + ieg_update_semantics_v0)`
* Orchestration of **S4 (identity)** → **S5 (edges)** → **S6 (indices)** for `APPLIED`
* Ensuring **durable commit coherence** with ST (so `graph_version` never lies)
* Producing the **ApplyOutcome** that feeds S7’s watermark/integrity truth

### S3 does **not** do (hard boundary)

* Does not parse business payload semantics (only uses the normalized identity-hints block produced upstream)
* Does not advance watermarks on its own authority (S7 basis truth must be durably supported)
* Does not serve queries (that’s S8/S6)
* Does not merge entities (v0 posture is no-merge; conflicts are surfaced)
* Does not run rebuilds/backfills (it obeys S7’s generation/mode)

---

## S3’s internal “gears” (subnetworks inside S3)

Think of S3 as 6 gears. Each is internal to the projector process.

### S3.1 Partition Apply Scheduler

* Ensures **in-order processing per partition** and per generation.
* Maintains a per-partition “single flight” rule: offset N must finish (durably) before N+1 begins.
* Allows parallelism **across partitions** (env knob: concurrency).

### S3.2 Apply Guard

* Confirms we are applying under the **active generation** and the expected **resume basis**:

  * “Is this partition assigned to me?”
  * “Is expected `next_offset_to_apply == offset`?”
  * “Is the mode RUNNING vs PAUSED/REPLAY?”
* If not aligned, S3 does not “fix” by skipping; it signals backpressure / re-seek needs (via S8/S1 control plane).

### S3.3 Classification & Validation Pipeline

* Deterministically decides: irrelevant vs invalid vs duplicate vs applied.
* Produces typed `INVALID_RECORDED` reasons (content problems, not infra problems).
* Enforces the “payload-blind beyond identity hints” boundary.

### S3.4 Mutation Orchestrator

* For `APPLIED` only:

  * Calls **S4** to resolve/mint entities + alias claims (no merges)
  * Calls **S5** to upsert edges (conservative on ambiguity)
  * Calls **S6** to update indices (v0 synchronous)

### S3.5 Commit Coordinator

* Builds the **Apply Unit Commit** so ST can atomically (or coherently) persist:

  * the offset outcome row,
  * update ledger mark (if scoped),
  * mutations (if applied),
  * checkpoint advance,
  * integrity updates (if invalid or mismatch),
  * conflict artifacts (if any).
* Defines retry policy for commit failures (infra failures stall safely; they don’t become “invalid recorded”).

### S3.6 Outcome Reporter

* Emits the final ApplyOutcome to S7/S8 surfaces:

  * classification counts, latency, last processed ts_utc (for watermark age),
  * integrity degradation signals,
  * reason summaries.

---

## Inputs S3 consumes (from S2 / S1)

S3 receives a **ScopedCandidate** containing at minimum:

* `generation_id` / mode (implicitly from S7 or consumption basis frame)
* `stream_name, partition_id, offset`
* `event_id, event_type, ts_utc`
* `scope_key` (ContextPins) or `NONE`
* `identity_hints` (normalized observed identifiers) or `MISSING`
* `parse_status` (`OK` or `MALFORMED`)
* `classification_hint` (identity-relevant? yes/no/unknown — produced by S1 or config table)

S3 does **not** accept “raw payload interpretation.” If an event is identity-relevant, the identity hints must already be normalized.

---

## Outputs S3 produces (to S7 and ST)

Every offset produces exactly one **durable outcome** *if ST is available*:

* `ieg_offset_outcome(generation, partition, offset) = classification + typed reason`
* `ieg_partition_checkpoint.next_offset_to_apply = offset+1` (exclusive-next)
* plus optional:

  * `ieg_update_ledger` insert (if scoped and applied/duplicate)
  * integrity ledger update (if invalid/mismatch)
  * graph state mutations (if applied)

And S3 emits to S7:

* `ApplyOutcome(classification, partition, offset, update_key?, reason?, event_ts_utc, scope_key?)`

---

## The classification pipeline (the heart of S3)

This is the deterministic decision tree S3 follows for each `(partition, offset)`.

### Step 0 — Apply Guard

* If `offset != expected_next_offset` for this partition/generation → **do not process**

  * signal “seek/resume mismatch” (ops) and wait for S1/S7 alignment.
* If mode is `PAUSED/DRAINING/REBUILDING` → obey mode (don’t start new Apply Units).

### Step 1 — Envelope parse status

If `parse_status == MALFORMED`:

* classification: `INVALID_RECORDED(reason=MALFORMED_ENVELOPE)`
* (no mutations)
* commit outcome + checkpoint + integrity update
* **advance offsets** after durable commit

### Step 2 — Identity relevance routing

If event type is **not identity-relevant**:

* classification: `IRRELEVANT_NOOP`
* commit outcome + checkpoint
* **advance offsets**

(Identity relevance comes from a pinned event_type routing map, not payload semantics.)

### Step 3 — Scope availability

If identity-relevant but `scope_key == NONE` (missing ContextPins):

* classification: `INVALID_RECORDED(reason=MISSING_PINS)`
* integrity degraded
* commit outcome + checkpoint + integrity update
* **advance offsets**

### Step 4 — Identity hints availability

If identity-relevant + scoped but `identity_hints == MISSING/EMPTY`:

* classification: `INVALID_RECORDED(reason=MISSING_ID_HINTS)`
* integrity degraded
* commit outcome + checkpoint + integrity update
* **advance offsets**

### Step 5 — Idempotency / duplicate detection

Compute:

* `update_key = H(scope_key + event_id + ieg_update_semantics_v0)`

Lookup:

* does `update_key` exist in the update ledger for this generation?

If **yes**:

* verify “duplicate consistency” (see next section)
* if consistent → `DUPLICATE_NOOP` (still checkpoint advances)
* if inconsistent → `INVALID_RECORDED(reason=DUPLICATE_MISMATCH)` (integrity degraded)

If **no**:

* proceed to `APPLIED` path (mutations allowed)

---

## Duplicate mismatch rule (important drift killer)

A repeated `event_id` must not silently mean different facts.

When ledger says update_key already applied, S3 checks a small **envelope-critical fingerprint**, e.g.:

* `event_type`
* `ts_utc`
* `scope_key` (pins)
* optionally a digest of the identity_hints block

If the new occurrence differs materially:

* classification becomes `INVALID_RECORDED(reason=DUPLICATE_MISMATCH)`
* integrity degraded
* still checkpoint advances after durable recording

S3 does **not** guess which one is “true.” EB remains the fact log; IEG records the inconsistency explicitly.

---

## The APPLIED path (mutation orchestration)

If we reach `APPLIED`, S3 does this *in order*:

### 1) Prepare a provenance_ref

* `prov = (stream_name, partition_id, offset, generation_id)`

### 2) Call S4 (Canonical Identity)

Input:

* scope_key, event_id, event_type, ts_utc, identity_hints, prov

S4 returns:

* resolved/minted `EntityRef` candidates per identifier group
* alias/claim deltas
* conflict sets (multiple candidates)

If S4 returns `INSUFFICIENT_HINTS` (despite hints existing but not enough to mint deterministically):

* S3 converts to `INVALID_RECORDED(reason=INSUFFICIENT_HINTS)`
* integrity degraded
* (no further mutations)

### 3) Call S5 (Relationships / Edges)

S3 builds edge requests using *only* the canonical endpoints from S4 and the allowed event-type-to-edge rules (still payload-blind).

**Pinned v0 ambiguity posture:** if an endpoint is ambiguous (multiple candidates), the edge is **skipped-and-recorded** as a conflict artifact (not guessed).

S5 returns:

* edges upserted
* edge conflicts (skipped due to ambiguity)

### 4) Call S6 (Projection Indices)

**Pinned v0 stance:** synchronous index updates inside the apply unit.

* identifier lookup projections
* neighbor adjacency projections
* profile views (thin)

### 5) Write the update ledger mark

Insert `(generation_id, scope_key, update_key)` with first-seen provenance.

### 6) Emit `ApplyOutcome(APPLIED)` and commit everything durably

(Next section.)

---

## The Apply Unit commit contract (S3 ↔ ST)

S3 must only consider the offset “processed” if ST confirms the following are durable in one coherent unit:

### Always durable (every classification)

* `ieg_offset_outcome(generation, partition, offset) = classification + reason?`
* `ieg_partition_checkpoint.next_offset_to_apply = offset + 1`

### If scoped (APPLIED or DUPLICATE_NOOP)

* update ledger insert/check

### If APPLIED

* identity deltas (entities + claims)
* edge deltas
* index deltas
* conflict artifacts (if any)

### If INVALID_RECORDED

* integrity ledger updated (DEGRADED + counters + first/last failure positions)

**If ST commit fails** (infra failure: DB down, write error, etc.):

* S3 must **not advance offsets**
* S3 must retry or trigger PAUSE/DRAIN via S8 backpressure controls
* This is not “invalid recorded” because you have not durably recorded anything yet.

This is the difference between:

* **content invalid** (record INVALID and continue), and
* **infra unable** (pause/retry, do not lie).

---

## S3’s interaction with S7 (truth anchor) during apply

S3 uses S7 in two ways:

### 1) Pre-apply guard

* “What is the active generation and expected next offset for this partition?”
* “Are we in REPLAY or INCREMENTAL mode?”
* “Are we paused/draining?”

### 2) Post-commit outcome reporting

After ST confirms durability, S3 emits ApplyOutcome to S7 so S7 can:

* update in-memory status frame for S8
* update watermark-age metrics (using `ts_utc`)
* update integrity status (already durable, but S7 mirrors it for fast reads)

**Pin:** S7 cannot “get ahead” of ST; it must reflect durable truth.

---

## Backpressure / survivability behavior (S3’s role)

S3 is the first place that *feels* saturation (commit latency spikes, ST errors). It must surface pressure signals upward; it must not invent semantics.

S3 produces:

* commit latency stats
* in-flight apply count
* retry counts
* “store unavailable” flags

S8 uses those signals to:

* THROTTLE
* PAUSE partitions
* DRAIN before rebuild/cutover

S3 obeys those modes (doesn’t start new Apply Units in PAUSED/DRAINING).

---

## Typed INVALID reasons (what S3 should standardize)

These are the core reasons that matter for ops + DL corridor checks:

* `MALFORMED_ENVELOPE`
* `MISSING_PINS`
* `MISSING_ID_HINTS`
* `INSUFFICIENT_HINTS`
* `DUPLICATE_MISMATCH`
* `APPLY_ERROR` *(only if you can durably record the failure outcome)*
* `INDEX_ERROR` *(only if synchronous indices are pinned and failure is durably recorded)*

(Infra failures that prevent durability are not INVALID; they’re “retry/pause” conditions.)

---

## What S3 must never allow (non-joins, restated in S3 terms)

* **No skipping offsets** to “get past a bad record.”
* **No advancing checkpoint without durable outcome.**
* **No mutating graph state from queries** (A2 is read-only).
* **No payload interpretation** outside the standardized identity-hints block.
* **No merges**—ambiguity becomes conflicts, not collapse.

---

## The minimal “done-ness” for S3’s machinery (so Codex can implement without guessing)

If S3 is correctly implemented, these statements are always true:

1. For each `(generation, partition, offset)` that becomes processed, there is exactly **one** durable outcome classification.
2. `next_offset_to_apply` is always **offset+1** for the last processed offset and never jumps.
3. Duplicates never double-apply.
4. Invalid content never stalls the whole projector; it becomes `INVALID_RECORDED` and integrity becomes explicit.
5. Infra failures never produce lying progress; they pause/retry.
6. APPLIED updates either fully show up (state + indices + ledger + checkpoint) or not at all.

---

Opening **S1: Projector Intake** — this is the machinery that turns “bytes from EB” into **normalized, scope-ready, payload-blind** records that the rest of the spine can process **without drift**.

S1’s job is *not* to decide truth, not to dedupe, not to mutate the graph. It’s to **ingest safely**, **normalize consistently**, and **hand off in-order**.

---

## What S1 owns

### S1 owns

* **EB consumption mechanics** (consumer group membership, partition assignment, fetch loop)
* **Basis alignment** (seek/resume from S7’s authoritative basis; never skip offsets)
* **Envelope decoding + minimal validation** (required fields present; parse_status)
* **ContextPins extraction** (but not scope routing — that’s S2)
* **Identity-hints extraction + normalization** from *one standardized identity-hints block* (no business payload parsing)
* **Flow control** (buffers, backpressure compliance: throttle/pause/drain)
* **Telemetry hooks** (intake-side stats; projector truth still comes from S7/ST)

### S1 does **not** own (hard boundary)

* **Idempotency decisions** (S3 owns update_key/duplicate logic)
* **Graph mutation** (S4/S5/S6 via S3)
* **Checkpoint truth** (S7/ST own next_offset_to_apply; S1 obeys)
* **Query serving** (S8/S6)
* **Rebuild orchestration** (S8/S7; S1 only follows replay basis frames)

---

## S1’s external joins (so we don’t blur boundaries)

* **From S7 → S1:** `ConsumptionBasisFrame`
  (“mode, generation_id, partitions, next offsets, optional end offsets, maintenance flags”)
* **From S8 → S1:** control verbs
  `THROTTLE | PAUSE | DRAIN | RESUME | REPLAY_SET_BASIS` (operational only)
* **From EB → S1:** `(partition, offset, envelope_bytes)` (at-least-once delivery)
* **From S1 → S2:** `NormalizedEvent` (one per EB record, in order per partition)
* **Optional:** S1 may emit “broker commit hints” after durable progress, but **ST checkpoint remains truth**.

---

## Internal subnetworks inside S1 (the “gears”)

### S1.1 Consumer Frontend

**Purpose:** join the consumer group, receive partition assignments, fetch records.
**Owns:** topic/stream id, group id, poll loop, assignment callbacks.

**Pinned behavior:** partition ownership is exclusive; per-partition ordering is preserved.

---

### S1.2 Basis Aligner

**Purpose:** ensure consumption starts exactly at S7’s basis.
**Owns:** seek/resume logic per partition and generation.

**Rules:**

* On assignment, always `seek(partition, next_offset_to_apply)` from S7/ST truth.
* Never “trust broker position” over ST; broker commits are hints at most.
* In REPLAY mode, obey explicit `start_offsets` and `end_offsets`.

---

### S1.3 Envelope Decoder

**Purpose:** decode bytes into a `CanonicalEventEnvelope`-shaped object (minimally).
**Owns:** JSON decode, required field presence checks, basic type checks.

**Output fields (minimum extraction):**

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
* optional pins: `scenario_id`, `run_id`, `parameter_hash`, `seed`
* trace/correlation: `trace_id`, `span_id` if present
* `payload` (passed through as opaque bytes/object reference; not interpreted here)

**Parse outcomes:**

* `parse_status=OK`
* `parse_status=MALFORMED` (can’t parse JSON, missing required fields, invalid types)

S1 must not attempt to “repair” malformed events. It marks them and hands them forward.

---

### S1.4 Pins Extractor

**Purpose:** extract ContextPins for later scope binding.
**Owns:** pulling `{scenario_id, run_id, manifest_fingerprint, parameter_hash}` out of the envelope.

**Important:** S1 extracts; **S2 binds** (S1 doesn’t decide whether missing pins are fatal — S3 does).

---

### S1.5 Identity-Hints Extractor (payload-blind)

**Purpose:** obtain identity hints without business-semantic parsing.

Because the canonical envelope doesn’t (yet) guarantee `observed_identifiers[]` at top level, S1 supports exactly **one normalized identity-hints block** in **two packaging modes**:

* **Mode A (future):** top-level `observed_identifiers[]`
* **Mode B (v0 bridge):** a reserved, strictly-standardized location under payload (e.g., `payload.identity_hints`)

**Hard boundary:**
S1 reads **only** that standardized block. It does not “dig around” the payload looking for IDs.

---

### S1.6 Identity-Hints Normalizer

**Purpose:** produce a single internal shape so downstream doesn’t care how hints were packaged.

**Internal normalized shape (minimal, drift-resistant):**

* `IdentityHints`

  * `subjects[]` (0..N)

    * `role` (string/enum: e.g., “primary”, “counterparty”, “instrument”, “device”, “ip”, “merchant”, etc.—*whatever your standardized block provides*)
    * `identifiers[]`

      * `namespace` (e.g., `account_id`, `instrument_id`, `device_id`, `ip`, `email_hash`, etc.)
      * `value`
      * optional: `entity_type_hint` (if your block provides it)
  * `hints_digest` (stable hash of the normalized hints)

**Why this matters:** S3/S4/S5 can build identity + edges deterministically without payload semantics leaks.

If hints are missing or empty, S1 outputs `identity_hints_status=MISSING` (not an error yet).

---

### S1.7 NormalizedEvent Builder

**Purpose:** produce the record handed to S2 with everything needed for scope routing + later apply.

`NormalizedEvent` (minimum):

* stream coords: `stream_name, partition_id, offset`
* envelope core: `event_id?`, `event_type?`, `ts_utc?` (may be missing if MALFORMED)
* pins: raw extracted pins fields (may be missing)
* `identity_hints` (normalized) or `MISSING`
* `parse_status`
* `raw_digest` (hash of envelope bytes) for correlation without logging payload

**Important:** S1 does not decide “graph mutating vs irrelevant.” It may add a *hint* (via config map) but that hint is not authoritative.

---

### S1.8 Partition Buffers + Flow Control

**Purpose:** keep ingestion fast without breaking ordering, and obey backpressure.

**Rules:**

* Maintain a **per-partition FIFO** so delivery to S2 is always offset-ordered.
* Allow bounded prefetch (profile knob), but never deliver N+1 before N.
* Respect S8 controls:

  * `THROTTLE`: reduce poll rate / batch size / in-flight buffers
  * `PAUSE`: stop fetching for partitions
  * `DRAIN`: stop fetching, flush in-flight events to S2, then pause
  * `RESUME`: re-enable fetching from S7 basis

---

### S1.9 Optional Offset Commit Helper (broker commits)

**Purpose:** reduce rebalance churn, but **never become truth**.

**Design pin:** S1 may commit offsets to the broker **only after** the corresponding offset is durably processed (i.e., after ST has recorded the outcome + checkpoint).
If broker commits ever drift, S1 still seeks from ST basis on assignment.

---

## S1’s production state machine (simple but real)

* `RUNNING` (normal fetch)
* `THROTTLED` (rate limited)
* `DRAINING` (stop fetch, flush buffers)
* `PAUSED` (no fetch)
* `REPLAY` (consume within start/end offsets for BUILDING generation)
* `ERROR` (cannot reach EB; cannot decode continuously; surfaces via telemetry)

Transitions are driven by:

* S8 controls (ops/backpressure/rebuild)
* S7 basis frames (generation/mode changes)
* EB assignment changes (rebalance)

---

## The two key S1 guarantees (what downstream can rely on)

### Guarantee 1 — **No reorder, no skip**

For a given partition and generation, S1 delivers records to S2 in **strict increasing offset order**, starting from **S7’s `next_offset_to_apply`**.

### Guarantee 2 — **Payload-blind normalization**

S1 will either:

* produce a normalized identity-hints block (if present), or
* mark it missing,
  but it will not infer identity from arbitrary payload fields.

This keeps identity semantics from drifting across producers/event_types.

---

## Failure handling (what happens when things go wrong)

### Malformed envelope

* S1 marks `parse_status=MALFORMED`
* emits `raw_digest` + partition/offset
* forwards to S2/S3 so the system can record `INVALID_RECORDED(MALFORMED_ENVELOPE)` and advance offsets *after durable recording*

### Missing ContextPins or missing identity hints

* S1 does **not** decide validity
* it forwards with `pins_missing` / `identity_hints_missing`
* S3 classifies `INVALID_RECORDED(MISSING_PINS/MISSING_ID_HINTS)` for identity-relevant event types

### EB connectivity / broker errors

* S1 goes to `ERROR` / `PAUSED` operationally
* does not “pretend progress”
* surfaces telemetry so the degrade ladder can react

---

## What S1 requires as an input artifact (so Codex doesn’t invent behavior)

To keep S1 deterministic and payload-blind, it needs exactly these config artifacts (profile-driven, not hard-coded):

1. **identity_hints packaging rule**
   (Mode A top-level vs Mode B reserved payload path) and the expected schema for that block.

2. **event_type → identity_relevance map**
   so S1 can optionally tag `classification_hint` (S3 still decides).

3. **environment profile knobs**
   poll/batch/in-flight limits, throttle policy, trace/log sampling.

---

If you’re happy with S1, the next node to open in the planned order is **S2 (Scope Router)** — it’s relatively small, but it’s where we pin the exact scoping rules (what counts as “scope present,” how scope NONE is represented, and how that flows into S3’s invalid/irrelevant decisions).

---

Opening **S2: Scope Router** — this is the machinery that takes S1’s normalized event and **binds it to exactly one run/world scope (or explicitly NONE)**, without reordering, without inventing meaning, and without touching durability/graph truth.

S2 is deliberately “small but sharp”: it prevents cross-run leakage and keeps everything downstream deterministic.

---

## What S2 is responsible for

### S2 owns

* **Scope derivation**: build `scope_key := {scenario_id, run_id, manifest_fingerprint, parameter_hash}` **from envelope pins only**.
* **Scope validity classification**: FULL / PARTIAL / NONE (and a missing/invalid bitmap).
* **Scope routing**: hand the event to S3 in a way that **preserves per-partition offset order**.
* **Diagnostics annotation**: attach “why scope is NONE” (missing pins, invalid pin format, etc.) so S3 can record typed INVALID reasons.

### S2 must not do

* **No idempotency decisions** (S3 owns update_key / duplicates).
* **No graph mutation** (S4/S5/S6 via S3).
* **No checkpointing / watermark advancement** (S7/ST).
* **No reading ST** (S2 stays stateless and cheap).
* **No payload semantics parsing** (S1 already extracted the standardized identity-hints block; S2 doesn’t go deeper).

---

## Inputs and outputs

### Input to S2 (from S1)

`NormalizedEvent` (minimum):

* stream coords: `stream_name, partition_id, offset`
* envelope core: `event_id, event_type, ts_utc` (may be missing if MALFORMED)
* raw pins extracted by S1: `scenario_id? run_id? manifest_fingerprint? parameter_hash?`
* `identity_hints_status`: PRESENT | MISSING (S2 doesn’t interpret hints, just carries status)
* `parse_status`: OK | MALFORMED
* optional: `classification_hint` (identity-relevant? yes/no/unknown) — non-authoritative

### Output from S2 (to S3)

`ScopedCandidate` (minimum):

* `generation_id` + `mode` (INCREMENTAL/REPLAY) *(usually attached earlier from S7 basis frame; S2 just forwards)*
* stream coords: `stream_name, partition_id, offset`
* envelope core: `event_id, event_type, ts_utc`
* `scope_key` OR `scope_key = NONE`
* `scope_status`: FULL | NONE | PARTIAL | INVALID_FORMAT
* `missing_pins`: bitmap/list (which of the 4 pins missing)
* `invalid_pins`: bitmap/list (present but invalid)
* `identity_hints_status`: PRESENT | MISSING
* `parse_status`
* passthrough: `identity_hints` (normalized structure from S1, unchanged)

---

## Internal gears inside S2

### S2.1 Pin Validator

**Goal:** decide whether each pin is present and usable **without transforming it**.

Rules:

* A pin is “present” if it exists and is a non-empty string.
* If present but clearly malformed (e.g., wrong type, empty string), mark it **invalid**.
* **No canonicalization** (no trimming, lowercasing, rewriting). Use pins as provided to avoid semantic drift.

Output:

* `present_pins[]`
* `missing_pins[]`
* `invalid_pins[]`

---

### S2.2 ScopeKey Builder

**Goal:** produce exactly one scope key or NONE.

Rules:

* If **all 4 pins are present and valid** ⇒ `scope_status=FULL` and build:
  `scope_key = (scenario_id, run_id, manifest_fingerprint, parameter_hash)`
* Else:

  * if any pin missing ⇒ `scope_status=PARTIAL` (and `scope_key=NONE`)
  * if any pin invalid ⇒ `scope_status=INVALID_FORMAT` (and `scope_key=NONE`)
  * if all absent ⇒ `scope_status=NONE` (and `scope_key=NONE`)

Why PARTIAL vs NONE matters: it lets S3 record **typed reasons** (`MISSING_PINS` vs `INVALID_PINS_FORMAT`) instead of a vague “unscoped”.

---

### S2.3 Scope Discipline Gate

**Goal:** enforce “one event → one scope” and prevent accidental multi-scope expansion.

Rules:

* Envelope pins are the **only** scope source.
* Identity hints may include multiple subjects/roles, but they do **not** create multiple scope_keys.
* If the event somehow presents conflicting pin fields (rare), S2 does not resolve; it flags `INVALID_FORMAT` (scope_key=NONE) and lets S3 record `INVALID_RECORDED`.

---

### S2.4 Partition-Order Dispatcher

**Goal:** feed S3 without breaking in-partition ordering.

Rules:

* S2 must never deliver offset `N+1` to S3 before offset `N` for the same partition.
* S2 may run per-partition FIFO handoff (often it’s just “call S3” inline), but the invariant is the same.
* If S3 backpressures, S2 backpressures S1 (do not buffer unbounded).

---

### S2.5 Annotation & Telemetry Hooks

S2 produces lightweight counters/flags (not “truth”):

* count of PARTIAL/NONE/INVALID_FORMAT scoped events per partition
* which pins are most frequently missing
* rate of “scope_key=NONE” for identity-relevant event types (useful for IG contract validation)

This is how you detect producer/IG schema drift early.

---

## S2’s state machine (tiny but explicit)

S2 is mostly stateless, but in production it effectively behaves as:

* `ACTIVE` (normal routing)
* `BACKPRESSURED` (cannot forward to S3; propagates throttle upstream)
* `PAUSED` (if S8/S7 has paused the generation/partition; S2 simply stops forwarding)

S2 does not invent “replay mode”; it follows what upstream basis frames already declare.

---

## Edge cases S2 must handle cleanly

1. **Malformed envelope**

* `parse_status=MALFORMED` passes through.
* S2 still sets `scope_key=NONE` and forwards; S3 will classify `INVALID_RECORDED(MALFORMED_ENVELOPE)`.

2. **Identity-relevant event missing pins**

* S2 sets `scope_status=PARTIAL`, `scope_key=NONE`, records missing bitmap.
* S3 uses that to record `INVALID_RECORDED(MISSING_PINS)` (and integrity degrades).

3. **Pins present but invalid format**

* S2 sets `scope_status=INVALID_FORMAT`, `scope_key=NONE`.
* S3 records `INVALID_RECORDED(INVALID_PINS_FORMAT)`.

4. **Global/unscoped events**

* S2 makes them explicit (`scope_key=NONE`).
* S3 decides whether that becomes `IRRELEVANT_NOOP` or `INVALID_RECORDED` based on identity relevance.

---

## Non-joins (explicit bans inside S2)

* S2 must not consult ST to check “does this run exist?” (that would couple projector to SR ledger and add drift).
* S2 must not consult S7 for anything besides forwarding the already-known generation/mode context.
* S2 must not create any “fallback scope” (no default run_id, no “latest run”).

---

## The one-line promise S2 makes to the rest of IEG

> **For every EB record, S2 deterministically produces either one FULL scope_key or an explicit NONE with a precise reason, without reordering offsets.**

If you want the next node to open in our planned order: **S4 (Canonical Identity)** is the next “real machinery” piece, because it’s where deterministic entity minting + no-merge conflict posture is defined.

---

Opening **S4: Canonical Identity** — this is the machinery that turns **normalized identity hints** into:

* deterministic **EntityRefs** (no merges),
* a durable **identifier → entity claims** index,
* explicit **ambiguity/conflict surfaces** (so downstream never relies on guessed identity),
* and thin per-entity “seen” metadata (first/last).

S4 is where “identity becomes a stable projection,” *without* becoming a second truth source.

---

## What S4 owns (and what it must not do)

### S4 owns

* Deterministic **identity resolution**: observed identifiers → 0..N candidate EntityRefs
* Deterministic **entity minting** (when allowed)
* Durable **identifier claims** (aliases): identifier_key → {EntityRefs} (possibly multiple)
* **Conflict/ambiguity classification** (no merges)
* Per-entity thin metadata: first_seen / last_seen timestamps (domain time `ts_utc`)
* Provenance anchors: first/last seen EB coords for claims (by-ref, not payload)

### S4 must not do

* **No merges** (ever in v0). If two entities “should be the same,” S4 surfaces conflict; it does not collapse.
* **No edges** (that’s S5).
* **No graph_version / checkpoints** (that’s S7/ST).
* **No idempotency decisions** (S3 owns update_key; S4 is called only when S3 says APPLIED).
* **No payload semantics** beyond the standardized identity-hints block S1 produced.

---

## S4’s boundary interface (with S3)

### Input: `IdentityMutationRequest`

S3 passes S4 exactly what it’s allowed to use:

* `generation_id`
* `scope_key` (ContextPins; never NONE here if we’re in APPLIED path)
* `event_id`, `event_type`, `ts_utc`
* `identity_hints` (normalized structure from S1; payload-blind)
* `provenance_ref = (stream_name, partition_id, offset)` (by-ref evidence anchor)

### Output: `IdentityMutationResult`

S4 returns **resolution + a deterministic write-set** (even if implemented as direct writes inside the ST tx):

* `subjects[]` results (one per “subject” in identity_hints):

  * `subject_ref` (opaque ID for the subject entry)
  * `entity_type` (resolved or hinted)
  * `candidates: [EntityRef...]` (0..N)
  * `resolution_status: RESOLVED | MINTED | AMBIGUOUS | UNRESOLVED | CONFLICT_STRONG`
  * `primary_entity?` (only if uniquely RESOLVED/MINTED)
  * `conflict_detail?` (typed reason)
* `entities_created[]` (EntityRefs minted)
* `claims_upserted[]` (identifier_key ↔ entity claims written/updated)
* `conflicts[]` (identifier-level or subject-level conflict artifacts)
* `status: OK | INSUFFICIENT_HINTS | ERROR`

**Important pin:** S4 may return AMBIGUOUS/UNRESOLVED without failing the whole event. S3 decides whether the overall offset remains `APPLIED` (with partial effects) or becomes `INVALID_RECORDED` (rare; reserved for true “cannot process” cases like missing hints/pins, which should have been caught before APPLIED).

---

## The data model S4 expects ST to provide (logical, minimal)

All keys are implicitly scoped by `(generation_id, scope_key)`.

### 1) Entities

`entity(entity_type, entity_id)`

* `first_seen_ts_utc`
* `last_seen_ts_utc`
* `created_at` (ops timestamp)
* optional thin tags (v0 keep minimal)

### 2) Identifier claims (alias index)

`claim(identifier_key, entity_type, entity_id)`

* `first_seen_ts_utc`
* `last_seen_ts_utc`
* `first_seen_prov` / `last_seen_prov` (partition/offset)
* optional `strength` / `namespace` as stored metadata

**Crucial:** `identifier_key` may map to **multiple** entities (that’s how we represent conflicts in a no-merge world).

### 3) Optional subject-resolution cache (derived)

Not required, but useful:
`subject_resolution(event_id, subject_ref) -> [EntityRef...]`
This can help explain “what S4 thought at the time,” but it’s optional.

---

## S4’s internal gears (inside S4)

### S4.1 Identifier Namespace Registry

A pinned table of “what identifiers mean,” used for canonicalization and mint rules.

Per `namespace` (e.g., `account_id`, `device_id`, `ip`, `email_hash`, …) store:

* `default_entity_type` (e.g., `account`, `device`, `ip`)
* `uniqueness_expectation`: `UNIQUE | NON_UNIQUE`
* `strength`: `PRIMARY | STRONG | WEAK`
* `mint_policy`: `ALLOW_MINT | NO_MINT`
* `canonicalization_rule_id` (how to normalize values deterministically)

**Why this matters:** it prevents S4 from inventing semantics ad hoc and keeps behavior stable across environments.

---

### S4.2 Identifier Canonicalizer

Takes each `(namespace, value)` and produces a **canonical identifier_key**:

* `identifier_key = namespace + ":" + canonical_value`

Rules are deterministic and namespace-specific:

* lowercase/trim where appropriate,
* IP canonical form where appropriate,
* preserve exact bytes where required.

**Pin:** canonicalization is *only* applied to identity hints; S4 never crawls payload fields.

---

### S4.3 Subject Grouper

Identity hints can contain multiple “subjects” (primary actor, counterparty, instrument, device, ip, etc.).

This gear:

* groups identifiers into **subjects** exactly as provided by the standardized hints block,
* does **not** split into multiple scopes,
* attaches an `entity_type_hint` when present.

---

### S4.4 Candidate Resolver

For each subject, builds candidate sets from existing claims:

1. For each identifier_key in the subject:

   * lookup `claim(identifier_key) -> {EntityRefs}`

2. Combine candidate sets using a deterministic rule:

   * If a **PRIMARY** identifier exists:

     * candidates are driven primarily by that identifier’s claim set
   * Else:

     * candidates = union of STRONG identifiers’ claim sets
     * if empty, optionally include WEAK unions (configurable but deterministic)

3. Produce:

   * `candidates[]` (sorted deterministically)
   * `resolution_status`:

     * `RESOLVED` if exactly one candidate
     * `AMBIGUOUS` if >1
     * `UNRESOLVED` if 0

**Pin:** S4 never chooses a single candidate out of multiple unless a deterministic “uniqueness guarantee” holds.

---

### S4.5 Deterministic Minting Engine

When does S4 mint a new entity?

**v0 design authority rule (safe + simple):**
S4 may mint **only** when the subject contains at least one identifier whose namespace has:

* `mint_policy=ALLOW_MINT`, and
* `strength=PRIMARY`, and
* the candidate set for that primary identifier is empty.

**Entity_id choice (deterministic):**

* If namespace is “engine-stable ID” (e.g., `account_id`, `party_id`, `instrument_id`, `device_id`):
  → `entity_id = canonical_value` (direct reuse)
* Else:
  → `entity_id = H(scope_key + entity_type + namespace + canonical_value + mint_v0_salt)`

This ensures replay stability and allows clean joins to engine surfaces when IDs align.

After minting, S4 produces claim inserts for all identifiers in the subject that have `ALLOW_MINT` or are safe to attach as aliases.

---

### S4.6 Claim Upserter

Writes/updates claims and entity metadata:

For each `(identifier_key, entity_ref)` claim:

* if claim exists: update `last_seen_ts_utc` + `last_seen_prov`
* else: insert with `first_seen=last_seen=ts_utc` and provenance

For each `entity_ref` touched:

* update entity `last_seen_ts_utc`
* if new entity: create with `first_seen=last_seen=ts_utc`

**Pin:** updates are monotonic in time semantics:

* `first_seen_ts_utc = min(existing, ts_utc)`
* `last_seen_ts_utc = max(existing, ts_utc)`
  This prevents out-of-order delivery from corrupting history.

---

### S4.7 Conflict & Ambiguity Reporter

Produces explicit conflict artifacts, without “fixing” them:

Types (minimal but useful):

* `IDENTIFIER_NON_UNIQUE`: identifier_key maps to multiple entities (expected for WEAK namespaces)
* `PRIMARY_UNIQUENESS_VIOLATION`: PRIMARY namespace maps to multiple entities (serious ambiguity)
* `SUBJECT_INCONSISTENT`: multiple PRIMARY identifiers in one subject point to different entities
* `UNRESOLVED_SUBJECT`: no candidates and mint not allowed

**Pinned posture:**

* Conflicts are **data facts** about the projection, not apply failures by default.
* They are returned to S3 (and later can be surfaced via queries/telemetry).
* S4 does not mark integrity degraded solely because ambiguity exists; integrity degrade is reserved for inability to process required basics (pins/hints/malformed) unless you later decide otherwise.

---

## S4’s canonical resolution algorithm (per subject)

Here’s the deterministic “playbook” S4 follows:

1. **Canonicalize** all identifiers → identifier_keys

2. **Lookup claims** per identifier_key → candidate sets

3. **If PRIMARY identifier(s) present:**

   * If any PRIMARY has exactly one candidate → treat that as anchor
   * If PRIMARY has 0 candidates and mint_policy allows → **MINT** that entity
   * If PRIMARY has >1 candidates → `CONFLICT_STRONG` (candidates = all; no selection)
   * If multiple PRIMARY identifiers exist and point to different entities → `SUBJECT_INCONSISTENT` (ambiguous)

4. **Else (no PRIMARY):**

   * candidates = union(STRONG claims)
   * if empty and policy allows weak fallback: union(WEAK claims)
   * status:

     * RESOLVED if exactly one
     * AMBIGUOUS if >1
     * UNRESOLVED if 0 (no mint)

5. **Upsert claims** and entity seen-times for:

   * minted entities and their identifiers
   * resolved entities and the identifiers observed
   * (optionally) ambiguous entities: you can still update “seen” times for all candidates, but v0 safer posture is to update only the claim “seen” metrics, not entity-level last_seen, unless the subject is resolved.

**v0 stance recommendation:**

* Update entity last_seen only for RESOLVED/MINTED subjects.
* For AMBIGUOUS, update claim-level last_seen (identifier observed) but avoid “touching” all entities’ last_seen (to prevent ambiguity from inflating activity signals).

---

## S4 observability outputs (what it should surface upward)

S4 should give S3/S8 enough counters for DL corridor checks and debugging:

* `entities_minted_total{entity_type}`
* `subjects_resolved_total`
* `subjects_ambiguous_total`
* `subjects_unresolved_total`
* `primary_uniqueness_violation_total`
* `claims_upserted_total{namespace}`
* `mint_attempt_denied_total{namespace}` (mint_policy=NO_MINT)

These are **not** part of semantic truth, but they are critical for detecting upstream drift (producers not supplying hints, weird duplication, etc.).

---

## S4 non-joins (explicit bans)

* No call to S7 (S4 doesn’t decide progress).
* No call to S5 (S4 never creates edges).
* No query serving.
* No cross-scope reads/writes (scope_key is always required in mutation path).
* No merges, ever (v0).

---

## What S4 guarantees to the rest of the system

If S4 is implemented to this machinery:

1. Identity resolution is **deterministic under replay**.
2. Entity IDs are **stable** (engine IDs reused when available; otherwise deterministic mint).
3. Ambiguity is **explicit**, never silently collapsed.
4. Weak identifiers can be many-to-many without corrupting “canonical identity.”
5. Out-of-order events do not corrupt first/last seen history.

---

Next in the order we pinned is **S5: Relationships / Edges** — that’s where we define edge identity, timestamp rules, provenance, and the conservative “skip-and-record” behavior when S4 returns ambiguous endpoints.

---

Opening **S5: Relationships / Edges** — this is the machinery that turns “resolved identity subjects” into a **stable, replay-safe relationship projection**: typed edges with domain-time history and provenance, **without guessing** and **without minting identity**.

---

## What S5 owns (and what it must not do)

### S5 owns

* **Edge upserts** (create/update typed relationships)
* **Edge identity rules** (how we uniquely represent an edge)
* **Domain-time history** (`first_seen_ts_utc`, `last_seen_ts_utc`) safe under out-of-order delivery
* **Provenance references** (first/last EB coords) so edges are explainable by-ref
* **Ambiguity posture** (v0: *skip-and-record*, never guess)
* Producing **edge deltas** for S6 indices (v0: synchronous index updates)

### S5 must not do

* **No entity minting** (S4 owns EntityRefs; S5 only consumes them)
* **No merges**
* **No checkpoint/watermark work** (S7)
* **No idempotency decisions** (S3 has already decided `APPLIED`; S5 can be pure upsert)
* **No payload semantics parsing** (S5 receives edge candidates already formed from standardized identity hints)

---

## S5’s boundary interface (with S3)

### Input: `EdgeMutationRequest` (from S3)

S3 hands S5 a request that is already:

* scoped (`generation_id`, `scope_key`)
* time-anchored (`ts_utc`)
* provenance-anchored (`provenance_ref = (stream, partition, offset)`)
* and has candidate endpoints produced by S4.

Minimum fields:

* `generation_id`
* `scope_key`
* `event_id`, `event_type`, `ts_utc`
* `provenance_ref`
* `edge_facts[]` where each EdgeFact includes:

  * `edge_type`
  * `directed` (bool)
  * `src_endpoint` (either a single `EntityRef` or an **ambiguous set** of candidates)
  * `dst_endpoint` (same)
  * optional `edge_attrs` (v0 keep minimal; mostly empty)

### Output: `EdgeMutationResult` (to S3)

* `edges_upserted[]` (the canonical edge keys that were written/updated)
* `edges_skipped[]` (with typed reason)
* `edge_conflicts[]` (ambiguity / missing endpoints / rule violations)
* `status`: `OK | PARTIAL | ERROR`

**Pinned v0 stance:** ambiguity produces **skips + conflict artifacts**, not guessed edges.

---

## The ST data families S5 expects (logical, minimal)

All keys are implicitly scoped by `(generation_id, scope_key)`.

### 1) Edge table (canonical relationship state)

`edge(edge_type, src_ref, dst_ref)` *(or canonicalized endpoints if undirected; see below)*

* `first_seen_ts_utc`
* `last_seen_ts_utc`
* `first_seen_prov` (partition/offset)
* `last_seen_prov` (partition/offset)
* optional: `observation_count` (v0 optional but useful)

### 2) Edge conflict artifacts (for “skip-and-record”)

`edge_conflict(conflict_id)` with:

* `edge_type`
* `src_candidates` / `dst_candidates` (or digests if large)
* `reason` (AMBIGUOUS_ENDPOINT | MISSING_ENDPOINT | INVALID_EDGE_RULE)
* `ts_utc`
* `provenance_ref`
* `event_id`

These artifacts are how we stay explainable without lying.

---

## S5’s internal gears (inside S5)

### S5.1 Edge Type Registry

A pinned registry that defines *edge semantics* without payload parsing.

Per `edge_type`:

* `directed` (true/false)
* `canonicalization_rule` (how to store undirected endpoints)
* `endpoint_type_constraints` (optional: allowed entity types)
* `multiplicity` (one edge per pair vs allow multiple variants — v0: one per type+pair)
* `confidence_policy` (v0: minimal, mostly ignore)

This keeps S5 deterministic and prevents ad hoc edge creation logic creeping in.

---

### S5.2 Endpoint Canonicalizer

Enforces endpoint representation rules:

* **Directed edges:** store exactly `(src_ref, dst_ref)` as given.
* **Undirected edges:** store endpoints in a canonical order:

  * `min(endpoint_key), max(endpoint_key)` where `endpoint_key` is a stable sortable string for EntityRef.
  * This prevents duplicate “A—B” and “B—A” records.

---

### S5.3 Ambiguity Gate (v0 conservative)

This is where we enforce the *skip-and-record* posture.

Rules:

* If either endpoint is **not uniquely resolved** (candidate set size ≠ 1):

  * **do not write** the edge
  * record an `edge_conflict(reason=AMBIGUOUS_ENDPOINT)`
* If an endpoint is missing / null:

  * record `edge_conflict(reason=MISSING_ENDPOINT)`
* If endpoint types violate constraints (optional registry rule):

  * record `edge_conflict(reason=INVALID_EDGE_RULE)`

**No guessing. No “pick first candidate.”**

---

### S5.4 Edge Upserter (domain-time safe)

For each EdgeFact that passes the ambiguity gate:

1. Compute canonical edge key:

   * `edge_key = (edge_type, canonical_src_ref, canonical_dst_ref)`

2. Upsert edge record with **out-of-order safe** timestamp logic:

* `first_seen_ts_utc = min(existing.first_seen_ts_utc, ts_utc)`
* `last_seen_ts_utc  = max(existing.last_seen_ts_utc,  ts_utc)`

3. Update provenance safely:

* If `ts_utc` establishes a new earliest time, update `first_seen_prov` to current `provenance_ref`
* If `ts_utc` establishes a new latest time, update `last_seen_prov` to current `provenance_ref`
* If `ts_utc` is between, provenance may remain unchanged (v0 keep minimal)

4. Optional: `observation_count += 1` (safe since S3 idempotency prevents double-apply for the same event)

This makes edges robust under out-of-order delivery without needing apply time.

---

### S5.5 Edge Delta Emitter (to S6 indices)

S5 returns a deterministic “delta” view:

* list of edges created/updated
* list of conflicts recorded

Because v0 indices are synchronous, S6 consumes these deltas inside the same Apply Unit.

---

## Edge identity rules (the “uniqueness contract”)

**v0 pin:** a relationship is uniquely identified by:

* `generation_id + scope_key + edge_type + canonical(src_ref,dst_ref)`

This means:

* repeated observations update `first/last` + provenance
* we do **not** create multiple parallel edges of the same type between the same endpoints

(If later you want multi-edges, you add an `edge_instance_key` derived deterministically; v0 keeps it simple.)

---

## How S5 handles the “partial apply” reality

A single event can produce:

* some identity subjects resolved (S4)
* some subjects ambiguous
  Therefore, S5 can:
* upsert edges for resolved endpoint pairs,
* skip and record conflicts for ambiguous ones

S3 remains `APPLIED` as long as we can **durably record** what we did (edges + conflicts), because ambiguity is not a processing failure — it’s a projection fact.

---

## Observability signals S5 should surface upward

These are counters/notes S3/S8 can emit:

* `edges_upserted_total{edge_type}`
* `edge_conflicts_total{reason, edge_type}`
* `ambiguous_endpoint_skips_total`
* `invalid_edge_rule_total`
* `edge_upsert_latency_ms`

These help DL corridor checks and drift detection (e.g., sudden rise in ambiguous endpoints).

---

## S5 non-joins (explicit bans)

* S5 does not call S7 (no progress truth).
* S5 does not call S4 to “resolve ambiguity” (S4 already returned candidates; ambiguity is a fact).
* S5 does not read EB or payload.
* S5 does not “heal” missing endpoints by creating entities.
* S5 does not perform index reads/serving (S6/S8).

---

## The guarantees S5 provides

If S5 is built to this machinery:

1. Relationship edges are **deterministic under replay**.
2. Out-of-order events do not corrupt `first_seen/last_seen`.
3. Ambiguity never becomes a wrong edge; it becomes an explicit conflict artifact.
4. Edges are explainable by-ref via provenance coords.
5. The neighbor query plane can be stable and version-stamped (via S6/S7/S8).

---

Next in our planned order is **S6: Projection Indices** — that’s where we define the exact read projections (resolve/profile/neighbors), deterministic ordering/pagination, and how it stays consistent with `graph_version` (v0 sync indices).

---

Opening **S6: Projection Indices** — this is the machinery that makes IEG **queryable, fast, deterministic, and version-stampable** without turning the query plane into “random DB joins” or “best-effort guesses.”

S6 is the **read-model layer**: it materializes (or guarantees) the projections needed for:

* `resolve_identity`
* `get_entity_profile`
* `get_neighbors`

…and it does so in a way that stays **consistent with `projection_generation_id` + `graph_version`** (v0: **synchronous index updates inside the Apply Unit**).

---

## What S6 owns (and what it must not do)

### S6 owns

* The **index families** that power reads (identifier lookup, adjacency, profiles)
* The **incremental materialization** of those indices from S4/S5 deltas
* Deterministic **ordering + pagination** rules (byte-stable results)
* Query execution that can run under an ST **read snapshot** provided by S8

### S6 must not do

* **No graph_version authority** (S7 stamps basis; S6 cannot invent/advance it)
* **No offset/checkpoint movement** (S7/ST only)
* **No writes on read** (query plane is read-only; no “fixing missing indices” at serve time)
* **No payload parsing** beyond standardized identity-hints already normalized upstream
* **No multi-generation mixing** (one query reads exactly one generation)

---

## S6’s boundary interfaces

### Inbound (write path) — from S3 (inside Apply Unit)

S6 receives **IndexDelta** objects derived from:

* S4 identity mutations (entities + claims)
* S5 edge upserts + edge conflict artifacts

It applies these deltas **synchronously** (v0 pin) so indices are never behind the basis that S7 will stamp later.

### Outbound (read path) — to S8

S6 exposes read operations that accept:

* `generation_id`
* `scope_key`
* a **read snapshot handle** (or equivalent snapshot token)
* query parameters + pagination

and returns:

* results + deterministic page tokens
* explicit conflict markers when applicable

S8 attaches:

* `projection_generation_id`
* `graph_version` + integrity status (from S7)

---

## S6 internal gears (inside S6)

### S6.1 Index Schema Registry

A small internal registry that defines:

* what index families exist
* their key structure
* their deterministic ordering keys
* their pagination strategy

This stops “new index, new semantics” drift.

---

### S6.2 Delta Translator

Takes mutation outcomes and converts them into index updates:

* From **S4**:

  * claim upserts → identifier index updates
  * entity first/last seen updates → profile view updates
  * ambiguity/conflict artifacts → optional conflict index updates

* From **S5**:

  * edge upserts → adjacency index updates
  * edge conflicts → optional conflict index updates

This gear must be deterministic: same deltas → same index writes.

---

### S6.3 Index Applier

Applies translated index updates to ST within the Apply Unit commit.

**v0 pin:** these updates happen as part of the same durable unit as:

* graph state mutations,
* update ledger mark,
* offset outcome row,
* checkpoint advance.

So the query plane never sees a basis that implies index state that isn’t committed.

---

### S6.4 Query Executor

Implements the three query shapes (resolve/profile/neighbors) using the index families, under a snapshot.

It must:

* enforce limits (`max_results`, `depth=1`, etc.)
* use stable ordering rules
* return deterministic page tokens

---

### S6.5 Ordering & Pagination Engine

Centralizes the “byte-stable” response discipline:

* total ordering keys per op
* deterministic tie-breakers
* stable `page_token` encoding

So results don’t drift with DB planner quirks.

---

### S6.6 Optional Maintenance & Compaction

Housekeeping that **never changes meaning**:

* pruning old conflict artifacts (retention policy)
* compaction of adjacency lists
* statistics refresh

This is environment/profile-tuned and does not affect semantics.

---

## The index families (what S6 maintains)

All are implicitly keyed by `(generation_id, scope_key)`.

### 1) Identifier Index (Resolve Identity)

**Purpose:** `identifier_key → {EntityRef candidates}`

**Logical rows:**

* key: `(identifier_key, entity_type, entity_id)`
* fields: `first_seen_ts_utc`, `last_seen_ts_utc`, optional provenance refs

**Deterministic ordering (pinned):**

1. `entity_type`
2. `entity_id`
3. (optional tie-breakers) `first_seen_ts_utc`, `last_seen_ts_utc`, provenance

**Why it matters:** DF/OFP hashing/provenance wants stable outputs.

---

### 2) Entity Profile View

**Purpose:** `EntityRef → thin profile`

**Logical row:**

* key: `(entity_type, entity_id)`
* fields: `first_seen_ts_utc`, `last_seen_ts_utc`, optional tiny counters (v0 keep thin)

This is the cheapest way to answer “profile” without scanning claims/edges.

---

### 3) Adjacency / Neighbor Index

**Purpose:** `EntityRef → ordered list of neighbor edges`

**Logical rows:**

* key: `(src_entity_ref, edge_type, neighbor_entity_ref)`
  *(for directed edges: src→dst; for undirected: canonical endpoints as pinned in S5)*

* fields:

  * `first_seen_ts_utc`, `last_seen_ts_utc`
  * `first_seen_prov`, `last_seen_prov`
  * optional `observation_count`

**Deterministic ordering (pinned):**

1. `edge_type`
2. `neighbor_entity_type`
3. `neighbor_entity_id`
4. `first_seen_ts_utc`
5. `last_seen_ts_utc`
6. `last_seen_prov` (final tie-breaker)

---

### 4) Optional Conflict Index (Diagnostics surface)

Not required for v0 decisioning, but useful for explainability:

* identifier conflicts (primary uniqueness violations)
* edge conflicts (ambiguous endpoints)
* unresolved subjects

This is helpful for ops and for “why didn’t we create that edge?” debugging.

---

## How S6 stays consistent with `graph_version` (the core v0 pin)

### v0 stance: **synchronous indices**

S6 index updates happen **inside the same Apply Unit** that commits:

* graph mutations (S4/S5),
* update ledger marks,
* offset outcome row,
* checkpoint advance.

So if S7 later stamps a `graph_version` whose basis includes offset `o+1`, then:

* the index state includes all committed effects of processing offsets ≤ `o`
* and queries under that generation can safely return version-stamped results.

**No “index lag” concept exists in v0.** If you ever want async indices later, we introduce `index_basis` and serve `min(projection_basis, index_basis)`—but v0 forbids “advanced basis with stale indices.”

---

## Query semantics inside S6 (what it guarantees)

### Resolve identity

Input:

* `(generation_id, scope_key, observed_identifiers[], snapshot, limit, page_token?)`

Output:

* per identifier: sorted candidates + conflict markers
* deterministic page token (if needed)

### Get entity profile

Input:

* `(generation_id, scope_key, entity_ref, snapshot)`

Output:

* thin profile or NOT_FOUND (deterministic)

### Get neighbors

Input:

* `(generation_id, scope_key, entity_ref, filters, snapshot, limit, page_token?)`
* **v0 pinned:** `depth=1` only

Output:

* ordered neighbor list + stable pagination

---

## Pagination token (what it must encode conceptually)

To guarantee stable continuation, the token must bind to:

* `generation_id`
* `scope_key`
* `op`
* `serve_basis_digest` *(or equivalent)*
* last item’s ordering keys (resume key)
* page size

If any of these don’t match on reuse, S6 returns a clear error (token invalid/expired/incompatible), rather than silently producing different pages.

---

## S6 non-joins (explicit bans, S6-local)

* S6 cannot update checkpoints or claim “applied offsets.”
* S6 cannot choose which generation is active; it reads routing/snapshot from ST as passed by S8.
* S6 cannot “heal” missing index rows during reads.
* S6 cannot return results without deterministic ordering.
* S6 cannot serve cross-generation or cross-scope results.

---

## What S6 enables downstream (why this matters)

If S6 is built like this, then:

* DF/OFP calls are low-latency and stable
* every response is stampable with `projection_generation_id + graph_version`
* parity/offline rebuild has a clean anchor (“this is exactly what we saw under basis B”)
* integrity degradation doesn’t create silent wrong answers; it becomes explicit via S7/S8

---

Next node in our order is **S8: Serving & Ops Facade** — because now that S6 is defined, S8 is where we pin the outward query behavior (STRICT vs BEST_EFFORT, min-basis checks, error taxonomy, telemetry emission, and backpressure controls) without letting the serve plane mutate anything.

---

Opening **S8: Serving & Ops Facade** — this is the machinery that makes IEG *usable* in production without breaking any of our rails:

* **Version-stamped, deterministic queries** (DF/OFP callers)
* **Truthful status + telemetry** (Obs/Gov corridor checks)
* **Operational control** (throttle/pause/drain; declared rebuild/backfill entrypoint)

S8 is the **only outward-facing “touch surface”** of the vertex. It *talks* and it *acts*, but it must never invent truth.

---

## What S8 owns

### S8 owns

1. **Query boundary** (DF/OFP ↔ IEG)

   * request validation + normalization
   * “serve basis” selection (via S7)
   * snapshot-consistent reads (via ST + S6)
   * deterministic responses + pagination
   * explicit error posture (retryable vs not)

2. **Status/health boundary** (ops)

   * expose projector progress, integrity, mode, generation
   * consistent with S7’s durable truth

3. **Observability emission** (metrics/logs/traces)

   * single place where IEG exports its operational truth

4. **Backpressure & mode controls** (operational)

   * throttle/pause/drain/resume controls to S1/S3
   * query load-shedding when needed (`IEG_BUSY`), never silent timeouts

5. **Run/Operate control entrypoint** (declared rebuild/backfill)

   * accepts declared commands
   * orchestrates with S7 + ST routing + S1 replay basis

### S8 must not do

* **No graph mutation on queries** (no “write on read”, no repairs)
* **No graph_version invention** (S7-only)
* **No checkpoint advancement** (S7/ST-only)
* **No payload semantics parsing** beyond the standardized identity-hints block already normalized upstream
* **No mixing generations** in a single response

---

## S8’s two “ports” (conceptual interfaces)

### Port A — Public Query API (DF/OFP)

Operations (v0 minimal set):

* `resolve_identity(scope_key, observed_identifiers, …)`
* `get_entity_profile(scope_key, entity_ref, …)`
* `get_neighbors(scope_key, entity_ref, filters, …)`
* `get_status()` *(read-only status view; can be public or ops-only)*

### Port B — Ops/Admin Control API (Run/Operate)

Operations:

* `submit_backfill(command)` *(declared op)*
* `get_backfill_status(operation_id)`
* `abort_backfill(operation_id)`
* `pause/drain/resume` *(optional; usually driven by ops automation)*

**Pin:** Port B must be privileged (authn/authz differs by environment), but the *meaning* of commands is identical across the ladder.

---

## Internal gears inside S8 (one level deeper)

### S8.1 API Boundary & Auth

* Validates caller identity (profile knob: none/local → strict/prod)
* Separates Public vs Admin routes
* Enforces request size/limits early (protects ST)

### S8.2 Request Normalizer

* Converts input into a canonical internal `QueryIntent`:

  * scope_key (ContextPins)
  * op + params
  * request_mode: `STRICT | BEST_EFFORT`
  * optional constraints: `min_graph_version`, `require_integrity_clean`
  * pagination token (if any)

**Important:** This is also where we reject malformed scope keys (but we don’t consult ST here).

### S8.3 Snapshot & Serve-Basis Gate

This is the “no lying snapshots” machinery.

For each query:

1. Open a **stable read snapshot** on ST.
2. Ask S7 (within that snapshot):
   **ServeBasisDecision** = `{decision, retryable, projection_generation_id, graph_version (or basis_digest), integrity_status, maintenance_mode}`
3. If decision ≠ OK:

   * return explicit error (see taxonomy below)
4. Pass the snapshot handle + generation_id to S6 so S6 reads the same snapshot.

**Pin:** the basis stamp and the data read must come from the *same* snapshot.

### S8.4 Query Orchestrator

* Calls S6 with:

  * snapshot handle
  * generation_id
  * scope_key
  * op + params + limits
* Receives deterministic results + next_page_token

### S8.5 Response Assembler

* Attaches required stamps:

  * `projection_generation_id`
  * `graph_version` (or token + digest)
  * `integrity_status`
* Ensures deterministic response shape (ordering is S6’s job; S8 enforces “must be sorted” invariants)
* Adds explicit “conflicts present” markers (no merge)

### S8.6 Error & Retry Mapper

Maps internal decisions into stable, explicit errors:

* `SCOPE_UNKNOWN` (non-retryable unless caller expects late activation)
* `LAGGING` (retryable=true, include current basis stamp)
* `INTEGRITY_DEGRADED` (retryable depends; include integrity status)
* `REBUILDING | MAINTENANCE | PAUSED | DRAINING` (usually retryable)
* `INVALID_REQUEST` (retryable=false)
* `PAGE_TOKEN_INCOMPATIBLE` (retryable=false)
* `IEG_BUSY` (retryable=true; load shedding, not failure)
* `INTERNAL_ERROR` (retryable maybe; always correlated/logged)

**Pin:** no silent fallback. If we can’t meet STRICT constraints, we say so.

### S8.7 Telemetry Emitter (Obs/Gov boundary)

Emits:

* query latency/error metrics by op + reason
* projector status frames (basis digest, generation id, integrity flag, maintenance mode)
* backpressure actions (throttle/pause/drain/resume events)
* rebuild lifecycle events (start/build/cutover/end)

**Correlation keys always included:**

* `projection_generation_id`
* `basis_digest` (or graph_version token)
* stream identity
* (when relevant) scope_key, partition/offset coords

### S8.8 Backpressure & Mode Controller (operational safety)

Decides when to:

* `THROTTLE` intake/apply (reduce rate)
* `PAUSE` partitions or global
* `DRAIN` in-flight apply units then pause
* `RESUME` from S7 basis
* Load-shed queries (`IEG_BUSY`) when ST is saturated

**Trigger sources:**

* S7 status frames (lag/watermark age/integrity/mode)
* ST health (commit latency/error rate)
* runtime in-flight counts from S1/S3

**Pin:** backpressure changes *when* we process, never *what it means*.

### S8.9 Admin Command Handler (declared rebuild/backfill)

Implements the A4 choreography:

* validate declared command
* ask S7 to create BUILDING generation + replay basis
* instruct drain/pause (S1/S3)
* set ST routing to BUILDING (writes) while reads remain ACTIVE
* start replay by having S7 publish basis frames to S1
* cutover explicitly when S7 marks READY_TO_CUTOVER
* surface mode transitions via status + telemetry

---

## S8’s production state machine (simple but explicit)

S8 exposes (and internally respects) these modes:

* `SERVING_OK` (queries allowed; projector running)
* `SERVING_DEGRADED` (integrity degraded; BEST_EFFORT allowed, STRICT may refuse)
* `SERVING_LAGGING` (too stale for some callers; min-basis may fail)
* `MAINTENANCE_REBUILDING` (BUILDING generation active; reads typically served from ACTIVE)
* `DRAINING/PAUSED` (projector paused; queries may still serve from last committed basis)
* `BUSY` (load shedding; returns `IEG_BUSY` explicitly)

**Pin:** modes are visible through status + telemetry; never implicit.

---

## The two key S8 “golden paths”

### Golden path 1 — Query (resolve/profile/neighbors)

1. Normalize request (S8.2)
2. Open ST snapshot (S8.3)
3. Get ServeBasisDecision from S7 in that snapshot (S8.3)
4. Execute S6 query in same snapshot (S8.4)
5. Assemble response + stamps (S8.5)
6. Emit telemetry/traces (S8.7)

### Golden path 2 — Rebuild/backfill (declared)

1. Accept declared command (S8.9)
2. Plan BUILDING generation + basis with S7 (S8.9)
3. Drain/pause projector (S8.8 → S1/S3)
4. Route writes to BUILDING (S8.9 ↔ ST)
5. Replay (S7→S1 basis frames; S3 applies into BUILDING)
6. Explicit cutover (S8.9 ↔ S7 ↔ ST)
7. Resume steady state; expose new generation id + basis (S8.7)

---

## Non-joins specific to S8 (drift blockers)

* S8 must never mutate graph state during queries.
* S8 must never compute or advance `graph_version` (S7-only).
* S8 must never “auto-reset integrity” (only explicit rebuild/cutover can restore CLEAN).
* S8 must never serve mixed-generation responses.
* S8 must never become a “decision engine” (it exposes signals; DL/DF use them).

---

## Environment ladder knobs that belong *in S8* (profile-driven)

* auth mode (public/admin)
* request timeouts per op
* max limits (neighbors/page size)
* load shedding on/off + thresholds
* trace sampling + log verbosity
* “STRICT allowed?” policy (some envs may default to BEST_EFFORT)
* rebuild cutover policy (auto vs manual confirm)
* backpressure thresholds (watermark age, ST latency)

Same semantics; different thresholds.

---

If you’re happy with S8’s machinery, we’ve now opened all Level-1 nodes. The next useful step is either:

* do a **cross-node sanity pass** (“does any node’s internal behavior contradict the pinned join contracts?”), or
* start refining **the standardized identity-hints block** (because it’s the single biggest real-world interoperability dependency across S1/S3/S4/S5).

---

## USER: PAUSE FOR REFLECTION

Yeah — it’s a *lot*, and it’s the right kind of “a lot.”

What we’ve actually built is a **network-of-networks**:

## The shape of the complexity

* **Outer platform network:** IEG is a *single vertex* with strict truth boundaries (IG→EB is the only door; IEG is derived; DF/OFP consume context; DL governs degrade; DLA records). That outer shape is what prevents “two competing realities.”
* **Inner IEG network:** we didn’t just draw modules — we drew **planes** (A1–A5), **paths (P-INT-1..8)**, and **loops (L-INT-1..5)**, with explicit **non-joins**. That is exactly what makes it “production-shaped” instead of a toy.

## Why it feels complex (and why it *has* to)

IEG sits at the intersection of the hardest operational constraints:

* **At-least-once delivery + duplicates + partition-order only**
* **Determinism under replay** (so audit/parity is real)
* **No merges** (so ambiguity must be representable, not hand-waved away)
* **Versioned truth** (`graph_version` + generation) that must never lie
* **Snapshot-consistent queries** while the projector is writing
* **Explicit rebuild/backfill** without rewriting history
* **Environment ladder**: same semantics everywhere, only knobs change

Any one of those is manageable. All of them together *forces* the architecture we ended up with.

## The “spine vs surface” clarity we achieved

Even with all that, the network is cleanly layered:

* **Spine (A1):** S1→S2→S3→(S4,S5)→S6→ST with S7 as the truth meter.
  This is where we guarantee “one durable outcome per offset” and “watermarks don’t lie.”
* **Serve plane (A2):** S8 + S6 + S7 + ST under a single read snapshot.
  This is where we guarantee “no lying snapshots.”
* **Ops plane (A3):** S7 tells truth, S8 exposes it and applies backpressure, never semantic change.
* **Rebuild plane (A4):** explicit generations + explicit cutover, no stealth semantics.
* **Optional pointers (A5):** allowed, but never a second truth feed.

That’s *why* it’s complex but not chaotic: **each plane has a single job**.

## The two “pressure points” to keep front-of-mind as we go deeper

1. **Identity-hints packaging:** everything depends on a standardized, payload-blind identity-hints block. If we let that drift, we’ll smuggle business semantics into identity.
2. **Truthfulness invariants:** `graph_version` + generation + snapshot-consistent reads + explicit integrity. If we let *any* layer “guess,” the whole platform becomes un-auditable.

## The short mantra that should keep us from drifting

* **Offsets are truth.**
* **Everything is stamped.**
* **Nothing is silently fixed.**
* **Rebuilds are explicit.**
* **No side doors.**

If you’re ready, the next best move is a **cross-node consistency pass**: quickly verify each opened node’s machinery still lines up with the A1/A2/A3/A4 join contracts and the non-joins—then we can tighten the single biggest shared dependency: the exact normalized shape of the identity-hints block.

---

