# Online Feature Plane Design Authority

This file is a rough collection of design or brainstorm notes for the Online Feature Plane. It views the whole platform as a network and expands open the online feature plane's position in this network and illuminates it.

---

Alright — **we’ll treat OFP’s internals as a black box** and pin its **outer role + obligations + joins** so tightly that the inner network can later be designed to satisfy them (without guessing).

Everything below is **authoritative for this brainstorm** and must not violate the platform rails/pins you’ve already locked.  

---

## Pinned Decisions for OFP’s role in the larger network

**PD-OFP-OUT-01 — OFP is a hot-path “projector + serve surface”.**
It continuously consumes **admitted events** from EB and serves **feature snapshots** on-demand; it is not a batch job.  

**PD-OFP-OUT-02 — OFP is system-of-record for: snapshot contents + provenance + snapshot hash (only).**
Not event validity (IG), not durability/replay (EB), not identity truth (IEG), not decisions (DF). 

**PD-OFP-OUT-03 — OFP is run/world-scoped by ContextPins (no cross-run state).**
ContextPins are `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` and appear everywhere features are served/recorded.  

**PD-OFP-OUT-04 — OFP consumes only “admitted traffic” shaped by the canonical envelope.**
So it can rely on required envelope fields (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`) and optional pins.  

**PD-OFP-OUT-05 — OFP is replay-safe by construction (idempotent update key is pinned).**
Each aggregate update is guarded by:
`(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)` 

**PD-OFP-OUT-06 — “As-of time” is explicit and uses domain event time (`ts_utc`).**
DF calls OFP with `as_of_time_utc = event_time_utc`, and “event_time” means `ts_utc` (domain time).  

**PD-OFP-OUT-07 — OFP provenance is mandatory and includes the platform’s replay tokens.**
Every successful `get_features` returns provenance with: ContextPins, group versions + freshness posture, `as_of_time_utc`, optional `graph_version` (if IEG consulted), and `input_basis` watermark vector; snapshot hash covers these with stable ordering.  

**PD-OFP-OUT-08 — Watermarks mean “exclusive-next offsets” per partition.**
`input_basis` is a per-partition vector of **next offset to apply**, not “last applied”. This is the universal replay/determinism hook. 

**PD-OFP-OUT-09 — Feature definitions must be versioned + singular across serving/offline/bundles.**
OFP records feature group versions used; Offline Shadow rebuild uses those exact versions; model/policy bundles declare required feature versions; registry compatibility must respect that (no drift). 

**PD-OFP-OUT-10 — v0 emission posture: OFP does NOT publish “feature snapshot created” onto EB.**
The “what features were used” record is carried via DF decision provenance (then DLA/audit), not via OFP producing a new traffic stream. (This keeps the replay spine clean and avoids a second “facts stream” that can drift.)  

**PD-OFP-OUT-11 — Failure posture is explicit (no fabricated context).**
If OFP cannot serve correctly, it returns an explicit error; DF records unavailability and follows its pinned fail-safe posture. 

---

## OFP’s place in the platform graph (outer network)

```
IG → EB(fp.bus.traffic.v1) → OFP(projector)
                         ↘︎ IEG(projector) ──(optional queries + graph_version)──↗︎

OFP(serve API) ── get_features(as_of=ts_utc) ──> DF
DF records: snapshot_hash + provenance (+ graph_version if used) → DLA/Audit
Offline Shadow later rebuilds using: EB/Archive + Label Store + same feature defs + provenance basis
```

EB topic naming + “projector+serve unit” shape is pinned in your deployment map.  

---

## What OFP *must* do externally (black-box behavior)

### 1) Consume admitted events and maintain online state (J7)

OFP continuously consumes **admitted** events from EB (duplicates + out-of-order are assumed reality).  

OFP’s only externally-relevant guarantees about this consumption are:

* **Idempotent updates** using the pinned update key recipe (so redelivery never double-counts). 
* **Progress is externally expressible as watermarks**: OFP maintains applied checkpoints (exclusive-next offsets) and can report them as `input_basis`. 
* **It stays joinable to identity context**: OFP may consult IEG (and must record `graph_version` when it does). 
* **It does not invent missing semantics**: if an event is malformed in a way that prevents correct update interpretation, OFP does not “guess” an update; it treats it as a failed update (operational signal). (IG should prevent most of this, but OFP still must fail closed.)  

#### Important platform pin that shapes this join

To keep IEG (and OFP parity) **envelope-driven**, admitted events that participate in identity/keying must carry `observed_identifiers[]` at the envelope level (the platform notes explicitly pin this direction for the canonical-event pack tightening). 
So: **OFP should not rely on bespoke payload parsing as the *only* way to key events.** It can still use payload fields for feature transforms, but the identity/linkage anchor should be envelope-level.

---

### 2) Serve deterministic feature snapshots (J8)

**OFP’s single hot-path output is: “serve a snapshot + provenance.”** 

The join expectations are pinned:

* **Caller:** Decision Fabric
* **Call:** `get_features(context_pins, feature_keys, feature_groups(with versions), as_of_time_utc)`
* **Pinned time rule:** DF sets `as_of_time_utc = event_time_utc` (domain event time = `ts_utc`).  
* **Pinned provenance rule:** DF records what OFP returned (snapshot hash, group versions, freshness posture, input_basis, and graph_version if present). 

So OFP must guarantee, at the boundary:

* **Determinism:** same request + same underlying applied basis ⇒ same snapshot hash (stable ordering + canonicalization). 
* **No hidden “now”:** “freshness” is computed relative to the explicit `as_of_time_utc`.  
* **Freshness posture is explicit:** provenance must say whether a group is stale/unavailable (not silently defaulted).  
* **Replay tokens are explicit:** provenance must include `input_basis` (exclusive-next watermark vector) and optionally `graph_version`. 

---

## How OFP interacts with each neighbor (no hidden assumptions)

### OFP ↔ Event Bus (EB)

**EB gives:** delivered admitted facts + partition/offset coordinates (only ordering within a partition; at-least-once). 
**OFP must treat as truth:** `(stream_name, partition_id, offset)` and build idempotency around it. 
**OFP must persist:** checkpoints/state for latency (rebuildable, but durable).  

### OFP ↔ Identity & Entity Graph (IEG)

**IEG is the authority** for identity projection and `graph_version` semantics. 
**OFP uses IEG optionally**:

* to resolve canonical FeatureKeys when needed (envelope-driven via observed identifiers), and/or
* to enrich context for particular feature groups.  
  **When it does:** OFP must record the `graph_version` used in provenance. 

### OFP ↔ Decision Fabric (DF)

**DF expects:**

* as-of semantics pinned to event time,
* a complete provenance bundle,
* deterministic snapshot identity,
* no fabricated missing context. 
  **DF responsibility:** treat degrade mask as hard constraints and only request/use allowed feature groups; record OFP’s returned provenance into decision provenance.  

### OFP ↔ Feature-definition authority (the “minimal hole” we must close)

Your platform notes explicitly flag **FeatureGroup version authority** as a drift-risk hole to pin. 
So I’m pinning it now, in a way that doesn’t introduce a new heavyweight component:

**PD-OFP-DEF-01 — Feature definitions live in a versioned “Feature Definition Profile Pack” (artifact), promoted via governance.**

* OFP and Offline Shadow both read the same pack (by-ref, versioned).
* DF bundles declare required feature group versions; Registry compatibility rules ensure ACTIVE bundles aren’t incompatible with available feature defs + degrade constraints.   

(Implementation can be “static config loaded at boot” in local; semantics remain identical in prod per environment ladder.) 

### OFP ↔ Offline Feature Shadow (parity bridge)

OFP’s **provenance + snapshot hash** is the “rebuild target” for offline parity: offline reconstruction is from **EB/Archive + same feature definitions + as-of** (and labels via Label Store), not from online caches.  
So OFP’s job is to make the target reconstructible by emitting:

* `input_basis` (what facts were applied),
* group versions,
* `as_of_time_utc`,
* `graph_version` if identity context mattered,
* deterministic snapshot hash.  

### OFP ↔ Observability/Governance (indirect but real)

Degrade Ladder reads observability signals and constrains DF; therefore OFP must expose **operational truth** (lag, error rates, availability) in a way DL can consume.  
OFP itself doesn’t decide degrade, but it must make its health/lag visible.

---

## “What OFP means” in one crisp platform sentence

**OFP is the always-on, replay-safe context compiler that consumes admitted events and serves deterministic, as-of feature snapshots with complete provenance (versions + freshness + graph_version if used + applied watermark basis), so decisioning and offline rebuild can both agree on “what we knew at decision time.”**  

---

Yes — **a small handful** of OFP things are worth pinning *before* we walk J7/J8, because they otherwise sneak in as “silent assumptions” during the join discussion.

## Already pinned (carry-forward, no re-litigation)

These are already platform-pinned and we’ll treat them as laws:

* **Scope:** OFP is **run/world scoped** by ContextPins (no cross-run state). 
* **Update safety:** idempotent update key = `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`; duplicates/out-of-order assumed. 
* **Serving rule:** `as_of_time_utc` is explicit (no hidden now) and is based on domain event time (`ts_utc`).  
* **Provenance:** must include group versions, freshness, `input_basis` watermark vector (+ `graph_version` if IEG used), and snapshot hash must deterministically cover these with stable ordering. 
* **OFP is always-on projector + serve surface** in production shape. 

## Remaining pins to lock now (so joins don’t drift)

### PD-OFP-OUT-12 — `input_basis.stream_name` is the *actual* admitted fact stream name

**Decision:** `input_basis.stream_name` must equal the EB stream OFP consumes for admitted traffic: **`fp.bus.traffic.v1`** (not a generic alias like “admitted_events”). 
**Why:** provenance/parity must name the real replay spine. 
**Implication:** if OFP ever consumes more than one stream in future, we add an explicit multi-basis structure; **v0 is single-stream basis**.

### PD-OFP-OUT-13 — One basis per response (atomic basis), not per-group

**Decision:** a `get_features` response has **one** `input_basis` vector for the whole snapshot (shared across all keys/groups in that response). 
**Why:** otherwise snapshot identity/hashing and offline parity become ambiguous (“which basis did group X use?”). 
**Implication:** internally OFP can be concurrent, but externally it must present a single coherent basis token.

### PD-OFP-OUT-14 — Keying posture: requests must be canonical; events may require a “key extraction contract”

**Decision:** `get_features` accepts **only canonical FeatureKeys** (key_id is the canonical entity_id, not raw identifiers). 
**Why:** this matches the platform’s “IEG is identity truth; OFP compiles context on top.” 
**Implication:** the *event→affected FeatureKeys* step must be pinned at the join: either (a) event payload schemas provide a stable “subjects” block OFP can extract, or (b) OFP consults IEG using observed identifiers.

### PD-OFP-OUT-15 — Observed identifiers: v0 transitional rule (because the envelope schema doesn’t carry them today)

There’s an explicit platform drift warning that envelope-driven updates want `observed_identifiers[]`, but the current canonical envelope schema doesn’t include it.  

**Decision (v0):** OFP may rely on **payload-level** observed identifiers / subject fields for key extraction *per event_type*, because the envelope is intentionally minimal today. 
**Decision (v1 target):** we promote a **canonical “observed_identifiers” envelope extension** (or event-type wrapper) and IG enforces it for traffic that must drive IEG/OFP envelope-driven updates. 
**Implication:** when we do J7, we will explicitly state what OFP expects to find for key extraction for each relevant event_type family (so we don’t hand-wave).

### PD-OFP-OUT-16 — “No data” vs NOT_FOUND semantics

**Decision:**

* **NOT_FOUND** is reserved for **invalid/unjoinable requests** (bad pins, malformed keys, impossible key_type, etc.).
* “No historical updates for this key/group” returns **success** with **empty/missing feature values + stale=true + a deterministic NO_DATA warning** (no invented timestamps). 
  **Why:** this keeps DF’s fail-safe logic clean and preserves determinism without pretending data exists. 

---

Absolutely — here’s the **full OFP-adjacent network** (joins + paths + loops) you should expect in a **production-ready** platform, **treating OFP as opaque**.

I’m only using what your platform blueprint + deployment truth pins imply (no extra invention).  

---

## Naming pin (to avoid drift while we talk)

Your docs use both “**admitted_events**” and the concrete topic **`fp.bus.traffic.v1`**. In production these refer to the same logical admitted fact stream.

**PD-OFP-NET-01 (authoritative for this brainstorm):**
**EB admitted facts stream = `fp.bus.traffic.v1`** (conceptually “admitted_events”).  

---

# 1) Direct joins touching OFP (the adjacency list)

## A. Data-plane joins (hot path, always-on)

### J7 — **EB → OFP** (stream consumption)

* **Edge:** `fp.bus.traffic.v1` → OFP projector
* **Why it exists:** OFP maintains feature state from admitted events; duplicates/out-of-order are normal.  
* **Production truth:** OFP persists **state + checkpoints** for latency/continuity (rebuildable but not ephemeral). 

### J7b — **IEG → OFP** (optional query join)

* **Edge:** OFP → IEG query API (RPC)
* **Why it exists:** optional canonical key resolution / identity context; if used, OFP must record `graph_version` in provenance.  

### J8 — **OFP → DF** (serve join)

* **Edge:** DF calls OFP `get_features(...)`
* **Why it exists:** DF needs feature snapshots at a deterministic decision boundary. 

---

## B. Control/config joins (always-on, low QPS but outcome-affecting)

### Cfg-OFP — **Policy/Profile pack → OFP** (feature defs + versions)

* **Edge:** feature definition/version “policy profiles” → OFP
* **Why it exists:** OFP depends on **feature definitions/versions** as an input; these are promoted like other policy/config artifacts.  
* **Platform rail that forces it:** “feature defs are versioned and singular across serving + offline + bundles.” 

*(Note: this is not “Registry → OFP” in the pinned network; OFP reads definition profiles as config/artifacts. Registry interacts with DF for bundle resolution.)* 

---

## C. Observability/Governance joins (meta-plane but real)

### Obs-OFP — **OFP → Observability pipeline**

* **Edge:** OFP emits metrics/traces/logs
* **Why it exists:** DL consumes lag/error signals; OFP staleness/lag are explicitly “platform-specific minimum metrics.”  

### Optional audit pointer join (if you choose to emit pointers)

* **Edge:** OFP → `fp.bus.audit.v1` (optional “snapshot pointer events”)
* **Status:** explicitly marked optional in deployment mapping.  

---

## D. Storage substrate “joins” (infra edges that exist in production reality)

These are not “component joins” but they are real dependencies in the deployed graph:

* **OFP ↔ `ofp` DB** (state + checkpoints) 
* **OFP ↔ network endpoints** (serve API to DF; query to IEG)  

---

# 2) Paths that include OFP (how information flows through the bigger graph)

## Path P1 — “traffic updates OFP state”

**Producer → IG → EB → OFP**

* Producers (engine traffic, external txns, DF/AL emissions) enter via IG, get appended to EB, OFP consumes.  

## Path P2 — “decision needs OFP snapshot”

**EB event → DF → OFP → DF**

* DF consumes an event (or receives sync request), then calls OFP with `as_of_time_utc = event_time_utc` (platform pin), receives snapshot + provenance. 

## Path P3 — “decision provenance carries OFP truth into audit”

**OFP → DF → DLA**

* OFP does not need to publish anything for audit.
* DF records: `feature_snapshot_hash`, group versions, freshness, `input_basis`, (+ `graph_version` if used).
* DLA persists these as part of the canonical audit record.  

## Path P4 — “offline parity / learning reads the same truths”

**(EB + Archive) + Label Store → Offline Shadow → Model Factory → Registry → DF**

* Offline Shadow rebuilds deterministically from the admitted stream (EB/Archive), using as-of label rules; produces DatasetManifests; MF produces bundles; Registry governs ACTIVE; DF resolves bundles compatibly (incl feature versions).  
* OFP participates **indirectly** because:

  * OFP’s recorded feature group versions are the serving anchor, and
  * bundles declare required feature versions; DF must only run compatible bundles.  

## Path P5 — “degrade constraints loop around OFP (via DF)”

**OFP metrics → Obs pipeline → DL → DF → (OFP request shape/load)**

* OFP lag/staleness contributes to DL posture; DF obeys the capability mask (may reduce/alter feature requests), which then affects OFP load and staleness.  

---

# 3) Loops (cycles) that exist in a production-ready platform

Below are the **actual cycles** that include OFP (not speculative).

## Loop L1 — The core hot-path cycle (fact → context → decision → fact)

**EB → OFP → DF → EB**

* EB facts update OFP state.
* DF queries OFP for context.
* DF emits decisions/action intents back onto EB as canonical events.  

This is the fundamental “closed world” loop: **facts generate new facts**.

---

## Loop L2 — The extended action loop (outcomes feed future context)

**EB → OFP → DF → AL → EB → OFP**

* DF emits ActionIntents to EB, AL executes and emits ActionOutcomes to EB, OFP consumes those outcomes like any other admitted facts (if feature definitions use them).  

*(OFP stays opaque; the point is: OFP is downstream of the same admitted fact stream that carries outcomes.)*

---

## Loop L3 — The “safe degradation” feedback loop

**OFP health/lag → DL → DF → OFP**

* OFP exposes staleness/lag/error signals.
* DL converts signals into an explicit constraints mask.
* DF changes behavior (what it requests/uses) and that reduces load / changes reliance on OFP, which changes OFP health signals.  

This is the production control loop that prevents “keep deciding while blind” behavior.

---

## Loop L4 — The learning-to-production loop (OFP is a compatibility anchor)

**(EB/Archive + Labels) → Offline Shadow → Model Factory → Registry → DF → (OFP requests)**

* New bundles change which feature groups DF requests (because bundles declare required feature versions), and OFP must serve with those versions and record them.   

This loop is slow (hours/days) but it is a real production loop.

---

## Loop L5 — The “operability / backfill” loop (derived truths are rebuilt, never silently)

**Obs/Gov signals or operations → Run/Operate backfill → rebuild OFP/IEG state → new watermarks → DF behavior**

* The platform pins that backfills/reprocesses that can change derived truths must be **declared and auditable**; OFP is explicitly a rebuildable projection that persists checkpoints/state.  

This loop is the “platform keeps itself correct over time” loop.

---

# 4) The complete “OFP outer network” picture (one ASCII)

```
                (policy/profile packs)
                   Feature defs/vers
                          |
                          v
EB fp.bus.traffic.v1 ---> OFP (projector+serve) ---> DF (get_features)
      ^                    |     ^                   |
      |                    |     |                   |
      |                    v     |                   v
      |                (optional) |               emits decisions/
      |               fp.bus.audit|               intents to EB
      |                           |
      |                           v
      |                        IEG (optional RPC)
      |
      +---- AL outcomes / DF outputs / engine traffic / external txns ----+

Meta loops:
OFP metrics -> Obs -> DL -> DF -> OFP
Offline: EB/Archive + Labels -> OFS -> MF -> Registry -> DF -> OFP
```

Grounding: J7/J8 and deployment-unit truth for OFP/IEG/DF/AL/EB.   

---

Here’s the **authoritative expansion order** I recommend for OFP’s **complete production joins/paths/loops** (outer network, OFP opaque). We’ll go in this order so each later item can reuse pins from earlier ones and we don’t drift.

## 1) Joins first (interfaces + obligations)

1. **J7 — EB → OFP (consume admitted facts)**
2. **J7b — OFP ↔ IEG (optional identity resolution / graph_version)**
3. **J8 — DF → OFP (get_features serve join)**
4. **Cfg-OFP — Feature-definition/profile pack → OFP (group defs + versions + policy promotion posture)**
5. **Obs-OFP — OFP → Observability/Governance (lag/staleness/error signals that DL can consume)**
6. **(Optional) Audit pointer join — OFP → `fp.bus.audit.v1` (only if you choose to emit pointers)**

## 2) Paths next (end-to-end flows that include OFP)

7. **P1 — Producer → IG → EB → OFP (traffic becomes feature-state)**
8. **P2 — EB event → DF → OFP → DF (decision-time context fetch)**
9. **P3 — OFP → DF → DLA (decision provenance carries OFP snapshot truth into audit)**
10. **P4 — (EB/Archive + Labels) → Offline Shadow → MF → Registry → DF → OFP (parity + compatibility anchor)**
11. **P5 — OFP health → Obs → DL → DF (capability mask) → OFP (load/request-shape feedback path)**

## 3) Loops last (production cycles)

12. **L1 — EB → OFP → DF → EB (core closed-world loop: facts → decisions → new facts)**
13. **L2 — EB → OFP → DF → AL → EB → OFP (action outcomes feed future context loop)**
14. **L3 — OFP health/lag → DL → DF → OFP (degrade/safety feedback loop)**
15. **L4 — Offline learning → Registry ACTIVE → DF → OFP (bundle/feature-version evolution loop)**
16. **L5 — Operability/backfill → rebuild projection → new watermarks → DF behavior (reprocessing loop)**

---

Great — we’ll expand **J7, J7b, J8** as *production joins* (OFP opaque), meaning: what crosses the boundary, what each side must guarantee, and what “correct” means under duplicates, disorder, and replay.

I’m treating the following as **pinned laws** for these joins:

* EB gives only universally meaningful position as **(stream_name, partition_id, offset)**, **exclusive-next checkpoints**, at-least-once delivery. 
* Canonical admitted event shape is the **CanonicalEventEnvelope** with required `{event_id,event_type,ts_utc,manifest_fingerprint}` and optional pins `{parameter_hash,seed,scenario_id,run_id}`.  
* OFP consumes admitted events + optional IEG queries; OFP update idempotency key is **EB position × FeatureKey × FeatureGroup**. 
* Served snapshots must include **input_basis** watermark vector; include **graph_version** if IEG is consulted; hash/provenance must be deterministic with stable ordering. 
* Production shape: OFP is **projector + serve API**, persists **state + checkpoints** in `ofp` store; consumes `fp.bus.traffic.v1`; optional pointer events to `fp.bus.audit.v1`. 

---

## J7 — EB → OFP (consume admitted facts)

### What this join *is*

A **replayable fact stream** (`fp.bus.traffic.v1`) delivering canonical envelopes + EB coordinates; OFP uses it to maintain derived feature state, safely under at-least-once + out-of-order.  

### What crosses the boundary (minimum)

**From EB to OFP**, for each delivered record:

* **EB coordinates (truth):**
  `(stream_name, partition_id, offset)`

  * ordering only within partition
  * delivery at-least-once (redelivery is normal) 

* **Event payload (shape):**
  a **CanonicalEventEnvelope** (validated at IG before it ever becomes admitted). Required:
  `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
  Optional pins when run/world-joinable: `parameter_hash`, `scenario_id`, `run_id`, and `seed` where relevant.  

### OFP’s obligations on this join (what “correct consumption” means)

#### 1) Replay safety (non-negotiable)

**Pinned idempotency rule:** every aggregate/state update must be guarded by:

`(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)` 

Interpretation (authoritative):

* If EB redelivers the *same* record (same partition+offset), OFP must NO-OP (no double-count).
* If one event affects multiple keys/groups, OFP produces multiple update-ids (one per key×group), each guarded independently.

#### 2) Disorder safety (non-negotiable)

OFP must be correct under **out-of-order delivery**, meaning:

* **Event meaning uses `ts_utc`** (domain time). 
* Update semantics must be **event-time driven** and **order-independent** (arrival order must not change meaning). 

This is the *reason* OFP cannot be “just keep last value” unless that last value is defined in event-time terms.

#### 3) Progress tokens (watermarks) are expressed in EB coords

OFP must persist consumer progress as **exclusive-next checkpoints** per partition. 
Those checkpoints are the source of the `input_basis` watermark vector later returned in J8. 

**Pinned meaning:** checkpoint offset = “next offset to apply” (exclusive-next), not “last applied”. 

#### 4) No cross-run state (ContextPins isolation)

Because ContextPins are the platform join pins, OFP must treat run/world-joinable traffic as scoped to:
`{manifest_fingerprint, parameter_hash, scenario_id, run_id}` 

That implies: when OFP updates state, it routes updates into the correct run/world partition (internally), and does not blend across runs.

### Edge-case posture (I’m pinning these as authoritative for production)

**PD-J7-01 — Unknown `event_type` is a no-op, not a failure.**
Rationale: not every admitted event drives every feature set; no-ops must not stall the projector.

**PD-J7-02 — Known `event_type` but un-interpretable for OFP is fail-closed and stalls that partition offset.**
Rationale: if OFP cannot safely apply a fact that *should* affect features, silently skipping would break audit/parity and create hidden drift. Stalling converts it into a visible operability event (DL can degrade DF). This is consistent with “don’t invent missing context” and “fail closed”.  

Operationally, “stall” means:

* do not advance the checkpoint past that offset
* expose lag/error signals (Obs) so DL/ops can respond

### What OFP must persist because of J7

Production shape explicitly pins:

* OFP has **DB `ofp` state + checkpoints** (rebuildable but must persist for latency/continuity). 

---

## J7b — OFP ↔ IEG (optional identity resolution / graph_version)

### What this join *is*

An **optional query join** used when OFP must turn “observed identifiers” into canonical entity keys, and (when used) produce a **recordable `graph_version` token** for provenance. 

### What `graph_version` means (pinned)

`graph_version` is a monotonic token representing “what EB facts have been applied” for a ContextPins graph: concretely a **stream_name + per-partition applied-offset watermark vector (exclusive-next)**. 

### What crosses the boundary (conceptual)

**OFP → IEG request must include:**

* ContextPins (so identity is resolved within the correct run/world) 
* an identifier bundle (whatever the canonical-event payload provides: e.g., PAN, device_fp, merchant_id, etc.)
* the query intent: “resolve_identity” (v0)

**IEG → OFP response returns:**

* canonical EntityRefs (what OFP will treat as FeatureKeys): `(key_type, key_id)`
* a `graph_version` token 

### Two critical pins to prevent drift/leakage

**PD-J7b-01 (v0) — OFP uses IEG only for *identity resolution*, not for graph-neighborhood feature computation.**
Rationale: your pinned J7 description explicitly calls out “resolve canonical keys + capture graph_version,” not “compute graph features.” 
Graph-dependent features can remain DF-side (DF already reads IEG context) in v0. 

**PD-J7b-02 — Canonical key resolution is monotonic-stable within a run/world.**
Meaning: once an observed identifier resolves to a canonical EntityRef in a ContextPins scope, later graph updates do not rewrite that mapping in a way that would make past updates non-replayable.
Rationale: without this, OFP would require historical/as-of graph queries for strict parity, which is an unnecessary v0 burden given the platform’s current pins.

### When OFP *must* call IEG (vs can skip it)

* **Must call** when an admitted event that should update features does not include canonical keys, only observed identifiers.
* **Can skip** when the event already carries canonical entity refs (payload-level) or OFP has already cached a stable mapping in-run.

### Failure posture for J7b

**PD-J7b-03 — If identity resolution is required and IEG is unavailable, OFP cannot safely apply that event.**
So it behaves like PD-J7-02: partition stalls at that offset, lag becomes visible, DL can trigger degrade.

---

## J8 — DF → OFP (get_features serve join)

### What this join *is*

A synchronous serving boundary where DF asks:
“Given these FeatureKeys + FeatureGroupRefs at this explicit decision time, what’s the feature snapshot and what basis did you use?” 

### What crosses the boundary (conceptual request)

**DF → OFP request must include:**

* ContextPins `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` 
* `feature_keys[]` (canonical keys; DF should not send raw identifiers)
* `feature_groups[]` as **(group_name + group_version)** (versions are part of compatibility) 
* `as_of_time_utc` (required; no hidden “now”) 
* **Pinned time rule:** DF sets `as_of_time_utc = event_time_utc` for the decision boundary. 

### OFP’s obligations on this join (what “correct serving” means)

#### 1) As-of correctness (no future leakage)

Even if OFP has applied events with `ts_utc > as_of_time_utc` (because of disorder), the served snapshot must reflect **meaning as-of `as_of_time_utc`**, not “latest applied.” This is implied by the platform’s time semantics rail and the J8 pinned time rule.  

#### 2) Provenance completeness (mandatory)

Every successful response must include provenance with:

* ContextPins
* deterministic `feature_snapshot_hash`
* group versions used + freshness/stale posture
* `as_of_time_utc`
* `graph_version` **if IEG was consulted**
* `input_basis` = OFP applied watermark vector (exclusive-next offsets) 

#### 3) Deterministic identity of the snapshot

`feature_snapshot_hash` must be deterministic and cover the relevant blocks (features, freshness, graph_version if present, input_basis, etc.) with stable ordering.  

#### 4) Single coherent basis per response

**PD-J8-01 — One `input_basis` per response (atomic basis).**
OFP must not return per-key or per-group bases; the snapshot is one coherent claim.

### What DF must do with the response (pinned)

DF must record, in its decision provenance:

* `feature_snapshot_hash`
* group versions
* freshness/stale flags
* `input_basis`
* and `graph_version` if present 
  (Deployment truth also pins DF persists provenance in emitted decision events.) 

### Error / failure semantics (authoritative v0 pin)

The platform pins the *behavior* (“don’t invent context”), but not the exact codes, so I’m pinning a minimal production-ready model:

**PD-J8-ERR-01 — OFP returns one of:**

* **INVALID_REQUEST** (malformed pins, empty keys, unknown group_version format, etc.) → `retryable=false`
* **NOT_FOUND** (valid request shape but OFP cannot serve because the context/key space does not exist for that run/world) → `retryable=false`
* **UNAVAILABLE** (OFP unhealthy / too stale / partition stalled) → `retryable=true`

And critically:

* OFP must not fabricate missing provenance; if it cannot provide `input_basis` (or required provenance blocks), it returns **UNAVAILABLE**. 

---

## Two end-to-end sequences (to make the joins concrete)

### Sequence S1 — Update/apply (J7 + optional J7b)

1. EB delivers `(stream, partition, offset)` + envelope `{event_id,event_type,ts_utc,pins,…}`  
2. OFP derives impacted `(FeatureKey, FeatureGroupRef)`

   * if keys not explicit → call IEG resolve_identity (J7b), get canonical keys + `graph_version` 
3. For each key×group: compute update_id = `(stream,partition,offset,key_type,key_id,group,version)` and apply only if unseen 
4. Commit state update (event-time semantics)
5. Advance checkpoint for that partition to `offset+1` (exclusive-next), durably 

### Sequence S2 — Serve (J8, with or without J7b)

1. DF calls `get_features(ContextPins, FeatureKeys, FeatureGroups+versions, as_of_time_utc=event_time_utc)` 
2. OFP reads state as-of the requested time (no future leakage) 
3. OFP captures `input_basis` watermark vector (exclusive-next) for the state basis used 
4. If OFP consulted IEG during serving, include the returned `graph_version` 
5. OFP returns snapshot + provenance + deterministic `feature_snapshot_hash` 
6. DF records the provenance blocks into decision provenance  

---

Cool — we’ll expand **#4–#6** as true *production joins* (OFP opaque): what crosses the boundary, who owns what truth, what must be guaranteed, and what “failure” looks like.

---

## 4) Cfg-OFP — Feature-definition/profile pack → OFP

### Why this join exists (what it must protect)

This join exists purely to enforce the platform’s anti-drift law:

* **Feature definitions are versioned and singular** — online serving (OFP), offline rebuild (Shadow), and bundles all refer to the *same* versions. OFP must record the group versions used. 
* That singular authority is explicitly pinned as a rail (“Feature definition/version authority is singular”). 

So Cfg-OFP is not “nice config”; it’s an **outcome-affecting policy/profile input** that must be versioned, governed, and auditable.  

### What crosses the boundary (minimum conceptual payload)

OFP consumes a **Feature Definition Profile** (versioned artifact) that provides, at minimum:

* a set of **FeatureGroups** keyed by `{group_name, group_version}`
* per group:

  * **key_type** (what kind of FeatureKey this group is keyed on)
  * **TTL/freshness policy** (needed for staleness computation)
  * stable **feature names** (identifiers)
  * (optionally) transform “recipes” (opaque to this join; just must be versioned)

This is exactly the posture you already pinned: OFP “loads group definitions (name+version, key_type, ttl)” to serve requests, and versions are part of compatibility.  

### Where it lives (production-shaped substrate expectation)

Deployment truth pins that OFP reads **policy profiles (feature definitions/versions)**, and profiles are stored as versioned artifacts under `profiles/…` (object store prefix).  

So the join is: **OFP loads a pinned profile revision from “profiles/”** (or equivalent), not “scan latest”.  

### Governance + promotion posture (non-negotiable)

Config/policy promotion is pinned:

* policy configs (including feature definition version changes) are **versioned artifacts with approval**, and activation emits an auditable governance fact; runtime components report which `policy_rev` they are using.  

So:

**PD-CFG-OFP-01 (authoritative):** OFP must run under a declared `feature_def_policy_rev` (or equivalent), and must expose that rev in its telemetry (and preferably in serve provenance).  

**PD-CFG-OFP-02 (authoritative):** Feature definition changes are never “hot silently”; they happen only via explicit activation (restart or governed reload), and the activation is an observable governance fact.  

### Compatibility contract with DF/Registry (how drift is prevented)

Two rails snap together here:

* OFP must record group versions used (B3). 
* Registry resolution is **compatibility-aware**: it must not resolve an ACTIVE bundle that cannot be satisfied by available feature versions/constraints; fail closed or safe fallback. 

That yields the production expectation:

**PD-CFG-OFP-03 (authoritative):** In steady-state production, DF should never ask OFP for a group_version that the currently-active feature definition profile does not provide — if it happens, it is a config/governance fault and should fail closed (surface as UNAVAILABLE/misconfigured), not “best effort”.  

### Failure modes (what “broken config” looks like)

If the profile artifact is missing, unreadable, or fails validation/digest checks:

* OFP is not allowed to “serve something anyway” — because that would fabricate semantics and break auditability/determinism.  
* OFP must go **UNAVAILABLE** and emit obs signals so DL/ops can respond.  

---

## 5) Obs-OFP — OFP → Observability/Governance

This join is “meta-plane”, but it is *production-critical* because DL depends on it for safe operation.  

### What this join must answer (platform law)

Observability is pinned to answer three questions across environments:

1. what happened/why
2. are we healthy enough to act
3. what changed 

### Correlation keys OFP must emit (so everything is joinable)

OFP telemetry must carry the applicable subset of:

* run/world pins (`run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`, seed when relevant)
* event pins (`event_id`, `event_type`, `ts_utc`, `schema_version`)
* serving provenance pins (`feature_snapshot_hash`, `graph_version`, `input_basis`)
* component identity (`component_name`, `component_version`, `env`)  

And (from the config lane pin):

* the `policy_rev`/profile revision OFP is currently using. 

### Metrics (minimum viable — pinned)

From your deployment pins, OFP must emit at least:

**Universal golden signals** (throughput/latency/error/saturation), plus platform-specific minimums:

* **consumer lag per partition + watermark age** (because OFP is an EB consumer/projector)
* **feature snapshot latency**
* **staleness rate**
* **missing-feature rate**
* **snapshot-hash compute failures**  

These are exactly the signals DL expects to consume. 

### Traces (minimum viable)

Trace posture is pinned:

* if an event has `trace_id/span_id`, platform preserves it IG→EB→consumers; DF decision span has child spans for OFP/IEG/Registry calls. 
* OFP therefore must:

  * emit **server spans** for `get_features` (J8)
  * emit **client spans** for any IEG calls (J7b/J8)
  * and propagate trace context into logs/metrics when present.  

### Logs (what must vs must-not be logged)

Pinned log posture:

* logs are structured, by-ref friendly, safe (no secrets; no raw payload dumps by default). 

For OFP specifically, the “boundary decisions that define truth” aren’t “every request served” (too noisy); the **production-grade log events** are things like:

* **profile_rev loaded / profile_rev switched** (explicit governed change) 
* **partition stall / resume** (cannot apply an event that should affect features) — this is what turns hidden drift into an operable incident  
* **serve degraded** (UNAVAILABLE / missing groups / hash failures) with correlation ids + ContextPins + snapshot hash when applicable 

### Governance facts (what changed)

Outcome-affecting changes must emit durable governance facts (policy rev active, backfill executed, etc.).  
OFP’s role isn’t to originate those facts; it’s to **bind to them** by:

* reporting the active policy/profile revision,
* surfacing any lag/stall that would force DL to constrain DF, and
* keeping everything joinable through the correlation keys above.  

---

## 6) Optional audit pointer join — OFP → `fp.bus.audit.v1`

Deployment truth explicitly allows: **“optional snapshot pointer events → `fp.bus.audit.v1`”** for OFP.  

### What this join is (and what it must NOT become)

This join is *not* a second “truth stream.” It’s an **optional discovery/index hint** channel.

**PD-AUDITPTR-OFP-01 (authoritative):** Audit pointer events are non-decisionable metadata; they must not be used as inputs to IEG/OFP/DF decision logic. They exist to make audit/search/indexing easier.  

### Admission / envelope posture (if you enable it)

If OFP emits anything onto the bus, it must conform to the canonical envelope shape (and, by the “one front door” pin, should still obey the platform’s admission discipline).  

So pointer events should be:

* **CanonicalEventEnvelope** header (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, optional pins). 
* payload carries only **by-ref pointers**, never the full feature snapshot blob. 

### What an OFP “snapshot pointer” would contain (conceptual)

A minimal payload that is maximally useful without becoming a second truth:

* `feature_snapshot_hash`
* ContextPins
* `as_of_time_utc` (the decision boundary target)
* `group_versions_used[]`
* `input_basis` (watermark vector)
* `graph_version` if IEG was involved
* `feature_def_policy_rev` (which profile rev defined the semantics)
* optional `snapshot_ref` (object store locator) + optional digest if OFP actually persisted a snapshot blob

This aligns with the platform’s by-ref + digest posture.  

### When to emit (recommended default)

In v0, you already have a strong audit spine:

* DF records snapshot hash + provenance in decision provenance 
* DLA writes immutable audit records by-ref 

So:

**PD-AUDITPTR-OFP-02 (authoritative default):** leave OFP audit pointer emission **OFF in v0**, unless you explicitly choose to persist snapshots as addressable objects and need a real-time index feed.  

If later enabled, keep volume bounded (e.g., only emit for persisted snapshots / sampled / explicitly requested), so IG/EB aren’t flooded with “audit hints.”  

---

Perfect — here are **P1–P3** expanded as **production paths** (OFP still opaque), written the way you’ll actually *run* the platform: what happens, what each hop is allowed to assume, what artifacts are produced, and where determinism/auditability is “made real”.

---

# P1 — Producer → IG → EB → OFP

## “Traffic becomes feature-state”

### What this path exists to guarantee

1. **Only one front door into the hot path:** anything that could influence identity/features/decisions/audit must go **through IG → EB**, never directly to OFP (or IEG/DF). 
2. **EB is the replay spine:** once admitted, the event becomes a replayable fact with a universally meaningful position `(stream_name, partition_id, offset)` (at-least-once is real). 
3. **OFP projection is derived:** OFP consumes admitted facts (`fp.bus.traffic.v1`) and maintains feature state + checkpoints; its state is rebuildable but must persist for latency/continuity. 

### Who counts as “Producer” here

Production top-view explicitly includes: **engine streams, DF outputs, AL outcomes, case/label emissions** as producers that must pass IG. 

*(Engine traffic enters via the pull-after-READY model we pinned earlier, but once it emits canonical traffic, it is just a “producer” to IG like any other.)* 

---

## The “happy path” sequence (what happens end-to-end)

### Step 0 — Producer prepares an event candidate

Producer must supply a **canonical envelope** (the boundary shape); if it’s not canonical, it’s not admissible. 

If the event is meant to participate in the **current run/world**, it must carry the required pins (ContextPins / joinability pins), because IG enforces joinability at the boundary. 

### Step 1 — Producer submits to IG (the trust boundary)

IG authenticates/authorizes the producer and validates the envelope + policy + joinability. This is not “advice”; it is the gate that decides what becomes fact. 

If run/world-joinable, IG consults SR’s join surface (`run_facts_view`) to enforce “valid (in practice READY) run context” — unready/unknown contexts are quarantined/held, not “best-effort”. 

### Step 2 — IG chooses exactly one outcome (authoritative)

IG outputs **ADMIT | DUPLICATE | QUARANTINE** and produces a receipt/evidence trail. No silent drops, ever. 

**ADMIT:** IG appends to EB and only declares admission once EB acknowledges durability. 
**DUPLICATE:** IG emits a stable “duplicate/admitted already” outcome pointing at the original fact, so downstream doesn’t amplify duplicates. 
**QUARANTINE:** IG stores evidence by-ref and emits a receipt with reason/evidence pointers. 

### Step 3 — EB becomes the durable fact log

EB is append/replay, not validator/transformer. Its truth is: partition/offset order + replay semantics. 

Crucially, EB’s coordinates become the platform’s replay tokens: downstream turns them into watermarks (“what I have applied”). 

### Step 4 — OFP consumes admitted facts and updates its projection

OFP consumes **`fp.bus.traffic.v1`**, and maintains **feature state + checkpoints** in its `ofp` store. 

OFP’s pinned replay safety rule: each aggregate update is idempotent using
`(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`
so duplicates/redelivery don’t double-count. 

OFP’s consumption progress is tracked via **exclusive-next** offsets per partition (checkpoint offset = “next offset to apply”), because that is the universal watermark meaning. 

---

## Production-grade branch behavior (where real systems drift)

### Branch A — event is unjoinable to the run/world

IG quarantines (or holds) and emits an explicit receipt; OFP never sees it because it never becomes an admitted fact. This is how SR readiness becomes enforceable rather than advisory. 

### Branch B — duplicates / retries

IG aims to prevent duplicate appends, but at-least-once is still assumed; therefore OFP must be safe under redelivery. 

### Branch C — OFP cannot interpret an admitted event that *should* drive features

This is an **operability incident**, not a silent skip. Practically: OFP stalls checkpoint advance on that partition (so its applied basis remains truthful), emits strong obs signals, and DL/ops can react. (This aligns with “no silent drops” and “determinism is powered by replay tokens.”)  

---

# P2 — EB event → DF → OFP → DF

## “Decision-time context fetch”

### What this path exists to guarantee

1. DF makes a decision at a **deterministic boundary** and does not invent missing context. 
2. OFP serves **deterministic feature snapshots** with provenance (`feature_snapshot_hash`, group versions, freshness, `input_basis`, optional `graph_version`). 
3. DF records what it used so the decision is later reproducible/explainable. 

---

## The “happy path” sequence

### Step 1 — DF receives the fact to decide on

DF consumes from EB (`fp.bus.traffic.v1`) (or receives a synchronous “decision request” input — both are allowed by the deployment mapping).  

It extracts:

* the event’s **ContextPins** (run/world scope), and
* the **decision boundary time** from the event (`event_time`), because time semantics are explicit. 

### Step 2 — DF chooses what it is allowed to ask for

Before calling OFP, DF is constrained by:

* **DL posture** (capabilities mask is hard constraints), and
* **Registry resolution** (one deterministic active bundle per scope, compatibility-aware).
  (These are not “OFP joins”, but they are what makes DF’s request shape production-safe.) 

### Step 3 — DF calls OFP `get_features`

**Pinned time rule:** DF calls OFP with `as_of_time_utc = event_time_utc`. 

The request includes:

* ContextPins,
* canonical FeatureKeys,
* FeatureGroupRefs with explicit versions (to lock training/serving drift out),
* as_of_time_utc. 

### Step 4 — OFP returns snapshot + provenance (+ deterministic hash)

OFP is system-of-record for:

* served snapshot contents,
* provenance bundle,
* `feature_snapshot_hash`. 

The provenance must include:

* ContextPins,
* `feature_snapshot_hash`,
* group versions used + freshness,
* as_of_time_utc,
* `input_basis` watermark vector,
* `graph_version` if IEG context was used. 

### Step 5 — DF uses the snapshot and proceeds to decisioning

If features are missing/stale/unavailable, DF **does not invent**; it records unavailability and follows its fail-safe posture (and still obeys degrade constraints). 

---

## Production-critical nuance: projector lag vs decision-time correctness

In a real run, DF may see the triggering event *before* OFP has applied it (consumer lag is real). That’s why:

* OFP must expose **freshness/staleness** and **input_basis** (what it had applied), and
* DL exists to constrain DF when OFP’s lag/health makes decisions unsafe.  

So the platform never relies on “hope OFP is caught up”; it relies on explicit provenance + explicit degrade controls.

---

# P3 — OFP → DF → DLA

## “Decision provenance carries OFP snapshot truth into audit”

### What this path exists to guarantee

This is the audit spine: later you must be able to answer, deterministically:

* **what was decided**,
* **what facts it was based on**,
* **what features were used** (and under what definitions/versions),
* **what identity context was used** (graph_version),
* **what degrade posture applied**,
* and do it without embedding raw payloads everywhere. 

---

## The “happy path” sequence

### Step 1 — OFP returns snapshot truth to DF

From P2, DF gets `feature_snapshot_hash` + provenance including `input_basis` and optional `graph_version`. 

### Step 2 — DF emits decision + action intents as traffic (through the same front door)

Your top-view is explicit: DF outputs are producers that go **through IG → EB** like everything else. 

So DF’s decision response (and action intents) become canonical-envelope events that end up on `fp.bus.traffic.v1` as admitted facts.  

### Step 3 — DF must embed provenance in what it emits

Deployment truth pin: DF is mostly stateless, but it **must persist provenance in emitted events** — including snapshot hash, graph_version, degrade posture, bundle ref. 

Blueprint pin (stronger): DF must record what OFP gave it:

* `feature_snapshot_hash`
* group versions
* freshness/stale flags
* `input_basis`
* `graph_version` if used. 

### Step 4 — DLA consumes and writes the immutable flight recorder

DLA is always-on consumer/writer: it ingests decisions/intents/outcomes from `fp.bus.traffic.v1` and writes immutable audit records under `dla/audit/...` (optional audit index).  

Blueprint pin: DLA is append-only, idempotent ingest, and **quarantines audit records if provenance is incomplete** (no “half-truth” audit). Corrections happen via **supersedes chains**, not overwrites. 

### Step 5 — How audit remains joinable without copying everything

DLA’s audit record includes by-ref / hashed pointers to:

* the event reference basis (what was decided on),
* `feature_snapshot_hash` + `input_basis`,
* `graph_version` (if used),
* degrade posture,
* resolved bundle reference,
* actions + idempotency keys,
* and links to IG receipts/evidence where needed.  

This is precisely what enables later offline parity: rebuild the snapshot under the recorded basis and compare hashes — without relying on “memory.” 

---

## The key “no drift” locks across P3

* **OFP owns snapshot truth** (contents + hash + provenance). 
* **DF owns decision truth** (decision + action intents + *what it used*). 
* **DLA owns the canonical flight recorder** (append-only, quarantines incomplete, supersedes chain). 

If any one of those starts “helpfully recreating” another’s truth, drift is guaranteed — so we keep the authority boundaries sharp.

---

Great — expanding **#10–11** as **production paths** (OFP still opaque), with the same discipline: **who owns what truth**, **what crosses each hop**, **what gets pinned for determinism/audit**, and **what failure looks like**.

---

# P4 — (EB/Archive + Labels) → Offline Shadow → MF → Registry → DF → OFP

## Parity + compatibility anchor (the learning→production pipeline)

### Why this path exists (what it guarantees)

This path is your **anti-drift bridge** between “what we served online” and “what we train/evaluate/deploy”:

* **Offline Shadow rebuilds deterministically** from the same admitted fact stream (EB + Archive) and labels “as-of” rules. 
* **DatasetManifests** pin training inputs so training is reproducible (not “here’s a dataframe”).  
* **Model Factory** produces **evidence-backed bundles**, publishes to Registry.  
* **Registry** is the **only gate** for learning to influence production: it resolves one deterministic ACTIVE bundle per scope, compatibility-aware.  
* **Decision Fabric** consumes that resolution and records the bundle ref in decision provenance; it then requests features from OFP **using versions that must match** the compatibility contract.

**One-sentence platform pin you already laid down:** learning influences production only through the Registry, with compatibility enforced (feature versions + capabilities) and everything recorded. 

---

## Production sequence (end-to-end)

### Step 1 — Inputs: Admitted facts + Archive + Labels

Offline Shadow reads:

* **Event history** from EB within retention and from **Archive beyond retention**, but both are treated as **the same logical fact stream** (same identity semantics).
* **Labels** from Label Store using explicit **as-of rules** (effective_time vs observed_time) to prevent leakage.

**Pinned consequence:** Offline Shadow can rebuild “as-of time T” without accidentally learning labels or events that were only observed later. 

### Step 2 — Offline Shadow rebuilds and records its basis

Offline Shadow is a scheduled/on-demand job that produces:

* **materializations** under `ofs/...`
* a **DatasetManifest** that pins the build basis.

The manifest must pin (at minimum):

* dataset identity
* time window / as-of boundaries
* join keys + entity scoping
* **feature group versions used**
* digests/refs to materializations
* provenance (sources + transforms). 

> This is what makes training reproducible: MF can only be reproducible if it can re-resolve the exact manifests later.

### Step 3 — Model Factory consumes DatasetManifests and produces evidence-backed bundles

Model Factory job reads:

* `ofs/...` DatasetManifests + profiles/config 
  and writes:
* training/eval evidence under `mf/...`
* deployable bundle payload(s) published to Registry (API), optionally emitting a governance fact.

**Pinned rule:** a bundle is not “just a model file”; it ships identity + immutable refs/digests + training provenance (which DatasetManifests) + evaluation evidence + PASS receipts where required.

### Step 4 — Registry enforces lifecycle + compatibility + ACTIVE resolution

Registry writes the platform’s production gate:

* stores bundle artifacts under `registry/bundles/...`
* maintains lifecycle and deterministic ACTIVE resolution (DB truth)

**Compatibility is enforced twice** (this is a crucial platform law):

* **At promotion time:** a bundle without compatibility metadata is not a valid deployable artifact. 
* **At resolution time:** Registry must not return ACTIVE-but-incompatible bundles (feature versions mismatch or degrade mask mismatch). Fail closed or safe fallback — never silently proceed.

Compatibility must cover at least:

* required FeatureGroup set + versions
* required capabilities (so degrade can disable safely)
* DF↔bundle interface version (conceptually). 

### Step 5 — Decision Fabric resolves the bundle and calls OFP in a compatible way

In the hot path, DF:

* queries Registry for an **ActiveBundleRef** for the current scope
* treats the answer as deterministic (“no latest”) and records it in decision provenance.

Then DF calls OFP:

* requesting only the FeatureGroups/versions compatible with the resolved bundle and current constraints.

### Step 6 — OFP serves + provenance becomes the parity anchor

OFP is authoritative for:

* snapshot contents + provenance + `feature_snapshot_hash`. 

And the pinned provenance contract is what enables offline parity later:

* provenance contains `input_basis` watermark vector (+ `graph_version` if IEG used), group versions, as-of time, and hash covers them deterministically.

**Net effect:** you can later rebuild offline under the same basis and compare hashes — not “hope it matches.”

---

## The two “hard pins” that make P4 production-safe

### Pin A — Archive is not a second truth

Archive is a logical extension of EB for retention; Offline Shadow records which source and basis.

### Pin B — Version alignment is enforced structurally

Your platform law **B3** is the spine here:

* OFP records group versions used
* Offline Shadow rebuild uses those exact versions
* bundles declare the versions they require 

This is why Registry compatibility can be enforced cleanly (and why drift doesn’t creep in as “someone forgot to update a config”).

---

## Failure posture (production reality)

* If Offline Shadow cannot pin basis deterministically (missing event window definition, missing feature profile versions, ambiguous label as-of), the output is invalid — it must fail closed, not produce “best effort training data.”
* If Registry cannot find a compatible ACTIVE bundle for the current feature versions / degrade constraints, DF must fail closed or route to a defined safe fallback and record why.

---

# P5 — OFP health → Obs → DL → DF (capability mask) → OFP

## Safe-ops feedback path (load/request-shape control loop)

### Why this path exists (what it guarantees)

This is your “platform is safe to operate” loop:

* Observability/Governance is not optional; it defines safe operation rules. 
* **DL consumes health/lag/error signals** and produces an explicit constraints mask (not a second decision engine).
* **DF treats the mask as hard constraints** and records posture in provenance/audit.
* Changing behavior via degrade is explicit and explainable (“this decision was made under posture X”).

---

## What OFP contributes: the signals DL needs

Because OFP is an EB consumer + serving surface, the platform pins **minimum OFP metrics** that matter for safety:

* consumer lag per partition + watermark age (how far behind applied offsets are)
* feature snapshot latency
* staleness rate
* missing-feature rate
* snapshot-hash compute failures

These are the inputs DL is designed to consume.

---

## What crosses DL → DF (the actual control artifact)

Your blueprint pins the join content:

**DegradeDecision** is explicit + deterministic + recordable:

* `mode`
* `capabilities_mask`
* provenance (decided-at timestamp / optional deterministic decision id) 

And you’ve pinned these production truths:

* DF must treat the mask as **hard constraints**
* degrade posture is recorded in decision provenance (and therefore audit)
* if DL unavailable, DF fails **toward safety** (stricter posture) and records fallback 

Deployment shape also pins DL’s operational posture:

* DL reads obs pipeline + threshold profiles
* writes current posture to `dl` DB
* may emit posture change events to `fp.bus.control.v1`

---

## How DF “applies” the capability mask (what changes in practice)

Because the mask is hard constraints, DF must behave as if disabled things **do not exist**, specifically:

* It must not request/use feature groups that are disallowed.
* It must not execute bundles that require disallowed capabilities (Registry compatibility enforcement covers this too).
* It may shift to safe fallback decisioning (explicitly recorded).

**Why this impacts OFP:** DF’s request shape is one of the biggest drivers of OFP load and apparent staleness. Under degrade, DF can:

* reduce feature groups requested
* reduce key fanout
* accept stale groups (explicitly recorded) rather than blocking
* or refuse to decide when unsafe (depending on your pinned DF fail-safe posture).

---

## The feedback dynamics (the “loop” you actually get)

1. OFP’s lag/staleness rises (consumer falls behind, snapshot latency increases). 
2. Observability pipeline captures this; DL evaluates against threshold profiles and updates posture.
3. DF receives the constraints mask (direct query or via control fact), treats it as hard constraints.
4. DF reduces OFP dependency / request shape, or moves to safer decision mode.
5. OFP load drops; staleness improves; DL can relax posture later via explicit change (again recordable).

---

## Failure posture (the “safety default”)

Pinned rule: if DL cannot produce a decision (unavailable, stale inputs, etc.), DF must fail toward safety and record the fallback posture.

This is a big deal: it prevents “ops tooling outage turns into riskier decisions.”

---

## The key coupling between P5 and P4 (why they’re not separate)

P4 says Registry compatibility includes **degrade-mask compatibility** (bundles declare required capabilities).
So P5’s mask doesn’t just throttle OFP usage — it also deterministically constrains which bundles DF is allowed to run at all.

---

Absolutely — here are **#12–#16 (L1–L5)** expanded as **production loops** (OFP remains opaque), with the **outer-network obligations** and the **pins that keep them safe + drift-free**.

---

## L1 — EB → OFP → DF → EB

### Core closed-world loop: facts → context → decisions → new facts

**Purpose:** turn admitted facts into decisions that become new admitted facts, *without* hidden “now”, drift, or replay ambiguity. 

**Loop steps (production reality):**

1. **Fact exists as admitted truth** on `fp.bus.traffic.v1` (durable append + replay; at-least-once is real).  
2. **OFP consumes** the admitted fact stream and updates its derived state with replay-safe idempotency keyed by **EB position × FeatureKey × FeatureGroup** (duplicate deliveries never double-apply). 
3. **DF consumes the same admitted facts**, establishes the decision boundary time from `ts_utc`, and calls OFP with `as_of_time_utc = event_time_utc`.  
4. **OFP serves a snapshot + provenance** (includes `input_basis` watermark vector; deterministic `feature_snapshot_hash`; and `graph_version` if IEG was consulted). 
5. **DF emits DecisionResponse (+ ActionIntents)** back onto the platform as canonical-envelope events (and must persist provenance inside those emitted events: bundle ref, snapshot hash, graph_version, degrade posture). 
6. Those outputs become new admitted facts (via IG’s trust boundary), land on EB, and the loop continues. 

**Pins that make L1 “safe to run”:**

* **No invention:** DF does not invent missing context; it records unavailability and follows its fail-safe posture. 
* **Replay tokens are explicit:** OFP’s `input_basis` and (if used) `graph_version` are the portable “what was applied” tokens that make later parity/replay possible.  
* **Deterministic outputs in an at-least-once world:** idempotency + stable hashing/canonicalization are required whenever you publish a digest/hash. 

**Failure mode you *want* (visible, not silent):**

* If OFP can’t safely apply a fact that should affect features, it must **stall** (don’t advance basis), emit strong lag/error signals, and let DL/ops clamp DF rather than silently skipping. This preserves truthful provenance and prevents hidden drift.  

---

## L2 — EB → OFP → DF → AL → EB → OFP

### Action outcomes feed future context loop

**Purpose:** actions are the only sanctioned side effects, and their outcomes become new facts that later decisions can depend on. 

**Loop steps:**

1. DF’s decision emits **ActionIntent** events to the admitted stream. 
2. **AL consumes intents** and executes side effects as the only executor. 
3. AL enforces **effectively-once** via its own idempotency truth (actions DB), producing a single authoritative outcome history per `(ContextPins, idempotency_key)` posture. 
4. AL emits **ActionOutcome** events back to `fp.bus.traffic.v1` as canonical facts. 
5. OFP consumes outcomes like any other admitted facts — if feature definitions include them, outcomes update feature state; future DF calls can incorporate those outcomes.  

**Pins that make L2 safe:**

* **AL is the sole executor** (no other component may “do the action”). 
* **Outcomes are immutable history** (append-only posture; corrections are additional facts, not rewrites). This keeps replay determinism and audit integrity. 
* **By-ref evidence is allowed** for outcomes (optional evidence blobs) but the outcome fact itself stays canonical-envelope shaped.  

**Common production hazard + the pinned fix:**

* Retries/timeouts create duplicated intents. AL must treat idempotency as *truth*, not “best effort,” so the loop doesn’t multiply side effects.  

---

## L3 — OFP health/lag → DL → DF → OFP

### Degrade/safety feedback loop

**Purpose:** keep the platform safe to operate when OFP (or dependencies) are stale/lagging/unhealthy — with explicit posture, not hidden coupling. 

**Loop steps:**

1. OFP emits the **minimum safety metrics**: consumer lag + watermark age, snapshot latency, staleness rate, missing-feature rate, snapshot-hash failures. 
2. Observability pipeline feeds these into **DL**, which computes an explicit, deterministic **DegradeDecision** `{degrade_mode, capabilities_mask, provenance}` and persists current posture (DB `dl`), optionally emitting posture changes to `fp.bus.control.v1`.  
3. DF treats the mask as **hard constraints**: it must not request/use disallowed feature groups/capabilities, and it must record degrade posture in decision provenance.  
4. DF’s reduced/altered request shape reduces load and dependence on OFP, which (ideally) improves OFP health; DL can later relax posture via another explicit change.

**Pins that make L3 non-hand-wavy:**

* **Degrade is explicit, enforced, recorded.** DF never “secretly” adapts without recording the posture; audit must show what constraints were in force. 
* **Hard constraints, not hints.** This prevents “we decided while blind” behavior. 
* **Watermarks don’t lie.** DL decisions can safely reference lag/watermark age because checkpoint meaning is pinned as exclusive-next offsets.  

**Failure posture (the safety default):**

* If DL is unavailable, DF fails **toward safety** (stricter posture) and records fallback. 

---

## L4 — Offline learning → Registry ACTIVE → DF → OFP

### Bundle/feature-version evolution loop (slow loop that changes production behavior safely)

**Purpose:** let learning evolve production decisions *without* training/serving drift and without unsafe rollouts. 

**Loop steps:**

1. **Offline Shadow** rebuilds datasets deterministically from EB + Archive (archive is a continuation of admitted facts) and Label Store as-of rules, producing **DatasetManifests** that pin replay basis + label boundaries + feature definition versions used.  
2. **Model Factory** trains/evaluates using those manifests and publishes bundles with evidence + compatibility metadata.  
3. **Registry** accepts bundles only if they ship compatibility + evidence, and resolves one deterministic ACTIVE bundle per scope **compatibility-aware** (feature versions + degrade capabilities). 
4. **DF resolves ACTIVE** deterministically and records the resolved bundle ref + compatibility basis in decision provenance. 
5. DF requests features from OFP using explicit FeatureGroup versions (and OFP records the group versions actually used).  

**Pins that make L4 the anti-drift machine:**

* **Feature definitions are versioned and singular:** serving (OFP), offline rebuild (Shadow), and bundles all must agree; OFP must record group versions used. 
* **Registry resolution is compatibility-aware:** never return ACTIVE-but-incompatible; fail closed or route to explicit safe fallback.  
* **DatasetManifests pin history basis:** training/eval must be reproducible even after retention changes and late truth. 

**What “change” looks like in this loop (governed, observable):**

* new bundle promotion to ACTIVE is a governed lifecycle action (registry events / governance facts), and DF’s decision provenance shows which bundle and feature versions were used post-rollout.  

---

## L5 — Operability/backfill → rebuild projection/datasets → new watermarks → DF behavior

### Reprocessing loop (keep the platform correct over time without time travel)

**Purpose:** when time passes (retention boundaries, late arrivals, bug fixes, new feature defs), you must be able to **rebuild derived truths** (IEG/OFP/datasets/indexes) *without mutating primary truth*, and without breaking determinism. 

**Loop steps:**

1. A backfill/reprocess is **explicitly invoked** (Run/Operate) with declared scope + basis + policy revs; it emits durable governance facts. 
2. Backfill may rebuild **derived** stores (IEG projection, OFP state, offline datasets/manifests, audit indexes) but it **never mutates** primary truths (EB events, label timelines, registry history, SR ledgers, engine outputs for a pinned identity). 
3. Consumers’ progress tokens remain **monotonic**: applied offsets/watermarks never “go backward.” Backfills create new derived versions or rebuild from scratch, but they don’t redefine what offsets meant.  
4. After rebuild, OFP/IEG resume with truthful checkpoints; DF’s behavior changes only in ways that are **explainable** via governance facts + recorded provenance (`input_basis`, `graph_version`, bundle ref, degrade posture).  

**Pins that keep L5 from corrupting history:**

* **Archive extends EB** (continuation of admitted facts, not a second truth).  
* **Backfill is never silent and never overwrites truth.**  
* **Watermarks remain meaningful:** monotonic progress tokens preserve the meaning of `graph_version` and `input_basis`, which preserves parity and audit replayability.  

---

Yes — the environment ladder changes **how these joins/paths/loops are *run***, but it must **not change what they *mean***.

Your own ladder pin is the governing rule here: **local/dev/prod run the same platform graph + rails/join semantics; only the operational envelope differs** (scale, retention/archive, security strictness, reliability, observability depth), and promotion is profile selection—not semantic forking.  

Below is what that implies for OFP’s joins/paths/loops.

---

## The non-negotiable invariants across all environments

If any of these differ between local/dev/prod, you don’t have a ladder — you have *three platforms*. 

1. **Same trust boundaries + graph roles**
   IG is the front door; EB is the fact log; SR is readiness authority; Registry is deployable truth; AL executes actions; Label Store is label truth; IEG/OFP are projectors with replay tokens.  

2. **Same rails**
   ContextPins discipline, canonical envelope, no-PASS-no-read, by-ref artifacts, watermarks meaning, idempotency, append-only + supersedes, degrade mask as hard constraint, deterministic registry resolution, explicit as-of semantics.  

3. **Same “meaning words”**
   READY/ADMITTED/ACTIVE/LABEL-AS-OF/BACKFILL must mean the same thing everywhere. 

4. **Same reproducibility story**
   Runs / training builds must be explainable with the same pins + evidence + refs in every env. 

---

## What is allowed to change (and how it impacts the OFP network)

These are legitimate ladder knobs, and they map directly onto your joins/loops. 

### 1) Scale and topology (local may collapse units)

* **Local can collapse deployment units** (e.g., OFP projector+serve in one process, IEG projector in-process), but the **unit roles remain the same** and the edges still exist logically.  
* This is why the “production-shaped local stack” pin matters: local must still feel like a real bus + object store + DB + OTel, not in-memory shortcuts.  

**Practical implication for J7/J7b/J8:**
Even locally, OFP/IEG must be grounded in **real consumer-group / offset semantics** so watermarks (`input_basis`) and `graph_version` remain meaningful.  

### 2) Retention + archive (env knob, semantics unchanged)

* Retention length differs: local short, dev medium, prod long + archive. 
* **But** offsets/watermarks/replay semantics do not change. 
* Archive is a **continuation of admitted facts** (not a second truth) and must be accessed by explicit by-ref bases (pins + stream id + offset/time window + digests).  

**Impacts loops:**

* L4/L5 (learning + backfill) can be “smaller” locally, but they can’t become “hand-wavy” (dataset manifests still pin basis; backfills still declared).  

### 3) Security strictness (mechanism exists everywhere; policy differs)

* Local can be permissive, but **the same trust-boundary semantics must exist** (IG still admits/quarantines; Registry still gates activation; AL still enforces allowlists).  
* Dev must be “real enough” to catch unauthorized producers, incompatible bundles, missing PASS evidence. 
* Prod is strict change control + strong authn/authz. 

**Impacts P1/L1/L2:**
You don’t bypass IG “because local.” If local bypasses IG, you’ll accidentally build OFP/DF behavior that never experiences quarantine/admission realities.  

### 4) Observability depth (baseline must still exist)

* Local = easier inspection, but **baseline observability still exists** (correlation keys + golden signals + lag/watermark metrics + trace context propagation).  
* Your notes explicitly recommend running an OTel pipeline locally so DL isn’t “pretend.” 

**Impacts P5/L3:**
If local doesn’t emit OFP lag/watermark age, you can’t validate degrade behavior end-to-end before dev/prod. 

### 5) Promotion/change control (profiles, not code forks)

* Environments differ by **profiles** (wiring + policy strictness), **not** “if prod do X else do Y” semantics. 
* CI/CD promotes three immutable lanes: **code artifacts**, **policy/profile revisions**, and **bundles**; promotions/rollbacks emit governance facts.  

**Impacts Cfg-OFP + L4:**
Feature definition changes are policy/profile changes (versioned, governed); bundle activation is registry-governed; DF requests must remain compatible with the active profile + bundle requirements.  

---

## Environment-ladder notes specific to the OFP joins/paths/loops

### J7 EB→OFP (consume admitted facts)

* **Local:** single-broker is fine, but it must still be Kafka-ish offsets + consumer groups (so `input_basis` isn’t fake). 
* **Dev:** turn on the kinds of failure you expect in prod (rebalances, duplicates, schema evolution scenarios), at representative volumes. 
* **Prod:** HA/retention/monitoring SLOs, and archive continuity matters. 

### J7b OFP↔IEG (graph_version)

* The *only* thing that may change across env is latency/reliability; the meaning of `graph_version` (offset watermark basis) must not. 
* If local collapses IEG+OFP, you still want the **IEG projector** consuming EB so `graph_version` remains tied to applied offsets. 

### J8 DF→OFP (serve)

* Local/dev/prod must all preserve: explicit `as_of_time_utc`, deterministic snapshot hash, provenance completeness (input_basis + graph_version when applicable).  
* What *can* change: timeouts/retries and concurrency limits, because those are wiring knobs. 

### P4/L4 (offline learning → registry → DF → OFP)

* In local you can run a tiny version, but you still must be able to execute at least one **full golden flow** end-to-end (including offline shadow + registry resolution) to prove the ladder is real. 
* Dataset manifests + explicit replay basis are the bridge that keeps parity valid even when retention differs.  

### P5/L3 (degrade loop)

* Degrade needs real signals; local must still emit lag/watermark metrics and propagate correlation keys so DL isn’t a stub. 
* Thresholds/corridor checks can be relaxed locally and tightened in prod via policy profiles (governed revisions). 

### L5 (backfill/reprocessing loop)

* Backfill is an environment knob (you run it more often in dev), but it must always be explicit + auditable, regenerate only derived stores, and preserve monotonic progress token meaning.  

---

## Three “environment-ladder pins” I recommend we treat as authoritative going forward

**PD-ENV-01 — No semantic shortcuts in local.**
Local may be smaller and collapsed, but it must still obey the trust boundaries + rails; otherwise you’ll validate a different platform.  

**PD-ENV-02 — Environment differences are profiles (policy + wiring), never code forks.**
All join/loop semantics must be explainable as “code artifact X + profile Y.”  

**PD-ENV-03 — Ladder validity is proven by the end-to-end golden flow.**
At minimum, local/CI must be able to run: **SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA + label + offline shadow + registry resolve** once. 

---

Yep — here’s the **environment-profile knob set** (and the few other “deployment truths” you should keep in your head) for **OFP-as-opaque-vertex**, so when you step inside, you design internals that *survive the ladder*.

Everything below respects the ladder pin: **same graph + same rails everywhere; only the operational envelope changes, via profiles (not code forks).**  

---

## 0) Two deployment truths to keep pinned while OFP is opaque

### OFP is one deployment unit in prod-shape

OFP is an **always-on EB consumer + serve API** with a **durable derived store** (`ofp` state + checkpoints). Local/dev may collapse topology, but the role does not change.  

### OFP correctness depends on “real EB semantics”

Your J7/J8 guarantees (idempotency keyed by EB position×key×group, `input_basis` watermarks, `graph_version`, as-of time) only stay meaningful if the environment uses **real partitions/offsets/consumer groups/checkpoints**, even locally.  

---

## 1) The environment profile split you should assume (for OFP)

Every environment provides **two profiles**:

1. **Wiring profile (non-semantic):** endpoints, credentials, timeouts, resource limits.
2. **Policy profile (outcome-affecting):** versioned artifacts (feature-def rev, threshold revs, etc.) that must be auditable; components report which `policy_rev` they’re using.  

---

## 2) OFP environment profile knobs (the practical checklist)

### A) EB consumption knobs (J7 foundation)

* `eb.bootstrap_servers` / TLS / auth settings (wiring)
* `eb.topic_traffic = fp.bus.traffic.v1` (wiring; **must not change** across env) 
* `eb.consumer_group_id` (wiring)
* `eb.offset_reset_policy` (wiring; local often “earliest”, prod “none/explicit”)
* `eb.max_poll_records`, `eb.fetch_bytes`, `eb.max_inflight_batches` (wiring; throughput/latency tuning)
* `eb.checkpoint_flush_interval_ms` (wiring)
* **Partition/replication envelope** (environment knob): partitions and replication factor vary, but **offset meaning (“exclusive-next”) never changes.**  

Why you care before internal design: your projector must tolerate rebalances, redelivery, and restart with truthful checkpoints. 

---

### B) OFP state store knobs (derived substrate)

* `ofp.state_store.kind` (embedded vs managed DB) (wiring; implementer choice)
* `ofp.state_store.dsn` / filesystem path (wiring)
* `ofp.state_store.shard_count` / partitioning strategy (wiring; scaling)
* `ofp.compaction_policy` / `event_time_bucket_retention` (wiring; affects storage cost & as-of capability)
* `ofp.checkpoint_table` / `state_table_prefix` (wiring naming)
* `ofp.rebuild_mode_allowed` (policy+ops): allowed in local/dev, in prod only via explicit Run/Operate backfill rules (never silent) 

Pinned truth: **OFP state is rebuildable but must persist for latency, and checkpoints must survive restarts.** 

---

### C) IEG dependency knobs (J7b / graph_version)

* `ieg.endpoint` / TLS / auth (wiring)
* `ieg.timeout_ms`, `ieg.max_qps`, `ieg.retry_policy` (wiring)
* `ieg.cache.enable` + size/ttl (wiring; latency control)
* `ieg.required_for_event_types[]` (policy): which event families *must* be resolvable to apply updates (controls “stall vs skip” posture)

Pinned meaning: when used, `graph_version` is an applied-offset watermark token; it must remain meaningful across environments. 

---

### D) Serve API knobs (J8 surface)

* `ofp.listen_addr`, `ofp.port` (wiring)
* `ofp.auth.mode` (none/dev token/mTLS) (wiring; stricter up the ladder) 
* `ofp.request_limits.max_keys`, `max_groups`, `max_response_bytes` (policy: prevents overload & keeps determinism manageable)
* `ofp.timeouts.get_features_ms` (wiring)
* `ofp.rate_limits.qps` / concurrency (wiring)

Pinned serving semantics you cannot change per env:
`as_of_time_utc` is explicit; provenance must include `input_basis` (+ `graph_version` if used) and a deterministic `feature_snapshot_hash`. 

---

### E) Feature definition/profile revision knobs (Cfg-OFP join)

These are **policy artifacts** (versioned + auditable), not “random config”:

* `feature_def.policy_id`
* `feature_def.policy_rev` (the active revision OFP loads)
* `feature_def.reload_mode` (explicit activation vs restart; must produce a governance fact when changed) 
* `feature_def.allowed_groups` (optional policy constraint)

This is the drift killer: online (OFP), offline rebuild, and bundles must align on versions. 

---

### F) Degrade/ops corridor knobs (P5 / L3 coupling)

OFP doesn’t decide degrade, but it must emit the signals DL uses; thresholds live in policy profiles:

* `dl.threshold_profile_rev` (policy; versioned) 
* `ofp.staleness_corridor.max_watermark_age_sec` (policy)
* `ofp.error_corridor.max_update_fail_rate` (policy)
* `ofp.serve_corridor.max_p95_latency_ms` (policy)

Key ladder point: dev should be “real enough” to catch these failures; prod thresholds are meaningful SLO corridors. 

---

### G) Observability knobs (must exist even locally)

* `otel.collector_endpoint` (wiring)
* `logs.level` / structured logging enable (wiring)
* `tracing.sample_rate` (wiring)
* `metrics.export_interval` (wiring)
* Correlation keys inclusion rules (policy-ish baseline): OFP telemetry must carry the applicable subset of run/event + `feature_snapshot_hash`/`input_basis`/`graph_version`. 

Pinned: observability must answer “what happened/why”, “safe to act?”, “what changed?” across all envs. 

---

### H) Retention / archive / backfill knobs (env envelope)

* `eb.retention_hours` (env knob; local short, prod longer) 
* `archive.enabled` (env knob; typically off local, on prod) 
* `backfill.allowed` (env knob; but executions are **explicit + auditable** and rebuild only derived stores like OFP) 

---

## 3) “Local / Dev / Prod” stance for OFP (directional, not prescriptive)

This is the right direction your internal design should tolerate:

* **Local:** single broker + simple DB, aggressive inspectability; rebuild often; permissive auth but same trust boundaries. 
* **Dev:** multiple services, real authn/authz, representative volumes; validate rebalances/backfills/schema evolution; dashboards/alerts exist. 
* **Prod:** strict change control (profile revs, feature defs, backfills), strong auth, archive continuity, meaningful SLO corridors.  

---

## 4) The one “extra” thing you should keep in mind before going inside

**Design internals so OFP can be rebuilt without “time travel”:** backfills regenerate derived state, never mutate primary facts; watermarks stay monotonic and meaningful. 
That single constraint drives a lot of the internal architecture choices later (bootstrap, compaction, checkpointing, and “stall vs skip”).

---

## USER: PAUSE FOR REFLECTION

Cool — let’s “freeze” the **outer network constitution** for OFP as we’ve exposed it, so when we step inside the vertex we’re not quietly changing what OFP *is* in the platform.

Below is the **authoritative outer-network frame** for OFP (v0), distilled into the minimum set of **roles, joins, paths, loops, invariants, and drift-traps**.

---

## OFP outer role and authority boundaries

### OFP is

* An **always-on projector + serve surface**.
* A **system-of-record only for**:

  * served snapshot contents (the returned values),
  * snapshot provenance,
  * deterministic `feature_snapshot_hash`.

### OFP is not

* Not the trust boundary (that’s **IG**).
* Not the replay spine (that’s **EB**).
* Not the identity truth (that’s **IEG**).
* Not the decision truth (that’s **DF**).
* Not the governance gate for models/bundles (that’s **Registry**).
* Not the audit flight recorder (that’s **DLA**).

This boundary is what prevents “two places can explain the truth” drift.

---

## Joins that touch OFP (production set)

### J7 — EB → OFP (consume admitted facts)

**Input:** delivered admitted records with:

* EB coordinates: `(stream_name, partition_id, offset)`
* canonical envelope with required fields: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` (+ optional run pins)

**OFP obligations:**

* Assume at-least-once and out-of-order.
* Apply updates **idempotently** using the pinned update key:
  `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)`.
* Track consumer progress as **exclusive-next** checkpoints per partition.
* Treat “can’t safely interpret a relevant event” as **fail-closed** (do not advance basis past it; surface as operability).

### J7b — OFP ↔ IEG (optional identity resolution)

**Purpose:** resolve observed identifiers → canonical entity keys, and (when used) bind serving/projection to a **`graph_version`** token.

* `graph_version` is treated as a monotonic “applied facts basis” token (watermark-vector semantics).

**Constraint:** OFP uses IEG **optionally** and records `graph_version` if consulted; it does not silently “invent identity.”

### J8 — DF → OFP (get_features serve join)

**Request must be explicit:**

* ContextPins (run/world scoping)
* canonical FeatureKeys
* FeatureGroupRefs with **explicit versions**
* `as_of_time_utc` (explicit; no hidden “now”)

**Pinned time rule:** DF calls with `as_of_time_utc = event_time_utc` (domain time = `ts_utc`).

**Response must include:**

* feature values (or explicit missing/stale posture)
* deterministic `feature_snapshot_hash`
* provenance including:

  * ContextPins
  * group versions used + freshness posture
  * `as_of_time_utc`
  * `input_basis` = watermark vector (exclusive-next)
  * `graph_version` if IEG was used

**Atomicity pin:** one coherent `input_basis` per response (not per group/key).

### #4 Cfg-OFP — Feature-definition/profile pack → OFP

OFP loads a **versioned feature definition profile** (artifact/policy-rev driven), providing:

* group_name + group_version inventory
* key_type per group
* TTL/freshness policy per group
* stable feature identifiers

**Governance pin:** feature-def changes are **profile/policy changes**, not silent drift; OFP reports which revision it is running.

### #5 Obs-OFP — OFP → Observability/Governance

OFP must expose:

* consumer lag and watermark age (per partition)
* serve latency
* staleness/missing rates
* update/apply failures
* active profile revision
  …and include joinable correlation keys (run pins, snapshot hash, basis tokens).

These feed DL and ops; if local doesn’t emit them, the ladder isn’t real.

### #6 Optional audit pointer — OFP → `fp.bus.audit.v1` (optional, OFF by default)

If enabled, it emits **non-decisionable metadata pointers** (snapshot hash + provenance + optional object refs), never a second truth stream.

---

## Production paths that include OFP (end-to-end flows)

### P1 — Producer → IG → EB → OFP

The only sanctioned ingress:

* Producers (engine traffic adapter, external txns, DF outputs, AL outcomes…) → IG (admit/quarantine/duplicate) → EB append → OFP projection update.

### P2 — EB event → DF → OFP → DF

Decision-time context:

* DF consumes a fact, derives `event_time` from `ts_utc`, calls OFP with explicit as-of, receives snapshot+provenance.

### P3 — OFP → DF → DLA

Audit spine:

* OFP provides snapshot truth and basis tokens.
* DF embeds snapshot hash + provenance into decision outputs.
* DLA records the immutable flight record (and quarantines incomplete provenance).

### P4 — (EB/Archive + Labels) → Offline Shadow → MF → Registry → DF → OFP

Parity + compatibility anchor:

* Offline rebuild produces DatasetManifests pinned to basis + feature versions.
* MF produces bundles; Registry governs lifecycle + compatibility; DF requests compatible feature versions from OFP.

### P5 — OFP health → Obs → DL → DF → OFP

Safety control:

* DL computes constraints mask from signals; DF obeys mask (hard constraints), which shapes OFP load and reliance.

---

## Production loops that include OFP (real cycles)

* **L1:** EB → OFP → DF → EB (facts → context → decisions → new facts)
* **L2:** EB → OFP → DF → AL → EB → OFP (outcomes feed future context)
* **L3:** OFP health → DL → DF → OFP (degrade feedback)
* **L4:** offline learning → Registry ACTIVE → DF → OFP (version evolution loop)
* **L5:** operability/backfill → rebuild derived → new basis tokens → DF behavior (explicit, auditable reprocessing loop)

---

## Environment ladder: what must stay identical vs what can vary

### Must be identical across local/dev/prod

* Join meanings (READY/ADMIT/ACTIVE, as-of semantics, watermark meaning, provenance requirements).
* Canonical envelope boundary.
* “No silent drops” posture: quarantine/stall/explicit failure, not hand-wave.
* Replay-token semantics (`input_basis` exclusive-next; `graph_version` monotonic basis token).
* Profile-driven behavior (no code forks).

### Allowed to vary via profiles

* retention & archive enabled/disabled
* thresholds and corridors (DL policy revs)
* timeouts/rate limits/resource sizing
* auth strictness
* partitions/replication (but offset meaning unchanged)
* local may collapse deployment units, but edges remain logically intact

---

## Drift traps to watch for as we go inside the vertex

If any of these start creeping into the internal design, we’re drifting:

1. **OFP starts validating/accepting raw producer events** (that’s IG’s role).
2. **OFP serving depends on “latest applied” instead of explicit `as_of_time_utc`.**
3. **OFP returns features without basis tokens** (no `input_basis` / missing `graph_version` when IEG used).
4. **Per-group/per-key basis tokens** (breaks snapshot identity).
5. **Feature definitions become “whatever config is on disk”** rather than governed rev.
6. **Skipping uninterpretable-but-relevant events** (silent drift) instead of stalling and surfacing.
7. **Local shortcuts erase real EB semantics** (fake offsets, fake consumer behavior).

---

## One last “outer-network checklist” before we step inside

When we start illuminating internals, every internal choice must satisfy these external statements:

* “Given admitted facts + EB coords, OFP applies updates idempotently and advances exclusive-next checkpoints.”
* “Given explicit as-of + keys + group versions, OFP serves a deterministic snapshot with complete provenance and a stable hash.”
* “If OFP cannot be correct, it fails closed and makes that visible to DL/ops/DF (not silent).”
* “Definitions/versions are a governed input, and OFP can always say which rev defined the semantics it’s serving.”

---

Yep — **one level deeper, still black-boxing everything inside**.

Below is the **authoritative “first internal layer”** for OFP: the **internal subnetworks (modules)** that must exist inside the vertex so the outer joins/paths/loops you pinned can be satisfied without hidden assumptions. (In local/dev/prod these can be co-located, but they remain **logical boxes**.)  

---

## OFP internal subnetworks (opaque boxes)

### S1) Update Plane Subnetwork

**Role:** Implements **J7 (EB→OFP)**: consume admitted facts, derive updates, apply to derived state, advance exclusive-next checkpoints.
**Inputs:** EB delivered records from `fp.bus.traffic.v1` + coordinates `(stream, partition, offset)` + canonical envelope.  
**Outputs:** committed feature-state mutations + durable checkpoints + operability signals (stall/lag/errors). 
**Owns:** replay safety (idempotency key recipe), disorder safety (event-time semantics), checkpoint truth. 

---

### S2) Identity Resolution Subnetwork

**Role:** Implements **J7b (OFP↔IEG)**: optional identity resolution and `graph_version` binding.
**Inputs:** “needs resolution” requests from Update Plane and/or Serve Plane (observed identifiers / subjects). 
**Outputs:** canonical FeatureKeys + `graph_version` token (when consulted) + cache hints. 
**Owns:** “if we consult IEG, we must record `graph_version`” rule; any caching must preserve determinism within ContextPins. 

---

### S3) Serve Plane Subnetwork

**Role:** Implements **J8 (DF→OFP)**: `get_features` API, as-of reads, freshness evaluation, provenance assembly, deterministic snapshot hashing.
**Inputs:** DF requests: ContextPins + FeatureKeys + (group_name, group_version) + `as_of_time_utc`. 
**Outputs:** feature snapshot + provenance (`input_basis`, versions, freshness, `graph_version` if used) + `feature_snapshot_hash`. 
**Owns:** “no hidden now”, “one coherent basis per response”, deterministic hashing/canonicalization. 

---

### S4) Feature Definition & Policy Subnetwork

**Role:** Implements **Cfg-OFP (#4)**: load the active feature definition/profile revision; expose group registry to Update/Serve planes.
**Inputs:** versioned profile/artifact reference (policy rev), plus reload/activation control (governed).  
**Outputs:** authoritative in-memory “feature group registry” (versions, key_types, TTL/freshness rules, feature ids). 
**Owns:** “feature defs are versioned + singular across online/offline/bundles” alignment; “no silent hot change” posture. 

---

### S5) Basis & Provenance Subnetwork

**Role:** Cross-cutting “truth compiler” that makes OFP’s outputs replay-explainable.
**Inputs:** checkpoints/watermarks from Update Plane, graph_version from Identity subnetwork, group registry from Policy subnetwork, request context from Serve Plane. 
**Outputs:** `input_basis` watermark vector (exclusive-next), provenance blocks, stable snapshot hash input ordering rules. 
**Owns:** the platform’s requirement that decisions can later be explained/rebuilt using basis tokens (this is what makes parity real). 

*(You can think of S5 as “the anti-drift spine” inside OFP.)*

---

### S6) Operability & Observability Subnetwork

**Role:** Implements **Obs-OFP (#5)**: telemetry, health, lag/staleness reporting, stall detection signals that DL/ops can consume.  
**Inputs:** Update Plane (lag/checkpoint age/stalls), Serve Plane (latency/errors/missing rates), Policy (active rev), Identity (IEG error rates). 
**Outputs:** metrics/traces/logs; explicit “unsafe to serve / stale corridor exceeded” signals (for DL feedback loop). 
**Owns:** “fail closed but visible” behavior: if OFP can’t be correct, it must be *operably loud*. 

---

### S7) Lifecycle & Rebuild Subnetwork

**Role:** Owns bootstrapping, controlled rebuild/backfill hooks, state retention/compaction, and environment-profile wiring (without semantic forks). 
**Inputs:** Run/Operate commands / ops triggers (explicit), environment profiles (wiring + policy revs). 
**Outputs:** safe startup, controlled rebuild of derived state, auditable “what changed” facts (through governance/obs). 
**Owns:** “rebuild derived truths without rewriting primary truths” constraint (ties to L5).  

---

### S8) Optional Audit Pointer Emitter Subnetwork (OFF by default)

**Role:** If enabled, emits **non-decisionable** snapshot pointer events to `fp.bus.audit.v1`. 
**Inputs:** provenance + snapshot hash from Serve Plane/Basis subnetwork.
**Outputs:** audit pointer events (by-ref metadata only).
**Owns:** strict separation: pointers must never become a second “truth stream” for decisioning. 

---

## Internal edges between these subnetworks (still opaque)

This is the minimal internal wiring that must exist:

* **S1 Update Plane → S5 Basis & Provenance** (watermarks/checkpoints become `input_basis`)
* **S3 Serve Plane → S5 Basis & Provenance** (response provenance + hash)
* **S1/S3 → S2 Identity Resolution** (only when subject→canonical key resolution is needed)
* **S4 Policy → S1/S3/S5** (group registry + TTL/freshness rules + versions)
* **S1/S3/S4/S2 → S6 Operability** (lag, error, staleness, active rev, IEG health)
* **S7 Lifecycle ↔ (all)** (startup, rebuild control, governed reload posture)
* **S5/S3 → S8 Audit Pointer** (optional, OFF by default)

---

## Why this is the “right level” of granularity

This set is **minimal but complete** for the outer network you’ve frozen:

* J7 needs S1 (+ S6, S7).
* J7b needs S2 (+ S5/S6).
* J8 needs S3 + S5 (+ S4).
* #4 needs S4.
* #5 needs S6.
* L5 needs S7.
* Optional #6 maps cleanly to S8.  

---

Yep — at this “first illuminated layer,” we treat each OFP subnetwork as an **opaque node**, and we map the **internal joins, paths, and loops** that must exist in a **production-ready OFP** to satisfy the *outer* pins (J7/J7b/J8, watermark/provenance, no-hidden-now, monotonic progress, explicit failures).  

I’m going to add one internal node that matters operationally in production:

* **T0 — OFP Durable Store (`ofp`)**: the persisted **state + checkpoints** surface (it’s a real production dependency). 

Everything else stays as the subnetworks we already named.

---

## Internal nodes (still opaque)

* **S1 Update Plane** (implements J7) 

* **S2 Identity Resolution** (implements J7b via IEG) 

* **S3 Serve Plane** (implements J8) 

* **S4 Feature Definition & Policy** (Cfg-OFP) 

* **S5 Basis & Provenance** (input_basis + hash/provenance compiler) 

* **S6 Operability & Observability** (metrics/traces/logs; stall/lag visibility) 

* **S7 Lifecycle & Rebuild** (boot, readiness, controlled rebuild/backfill hooks; profiles-not-forks)  

* **S8 Optional Audit Pointer Emitter** (OFF by default) 

* **T0 OFP Durable Store (`ofp`)** (state + checkpoints persisted) 

---

# 1) Internal joins (edges) in production

I’m naming these **IJ-xx** so we can reference them later when we dive deeper.

### Data-plane joins (update + serve)

**IJ-01 — J7 Intake:** `J7 boundary → S1 Update Plane`

* Delivered admitted events + EB coords are ingested here. 

**IJ-02 — Update writes derived truth:** `S1 → T0`

* S1 commits derived feature-state + advances **exclusive-next checkpoints** (no “watermarks lie”).  

**IJ-03 — Serve reads derived truth:** `S3 → T0`

* S3 reads “as-of” state (event-time semantics; no hidden now). 

### Identity joins

**IJ-04 — Update requests identity:** `S1 ↔ S2`

* When an event doesn’t present canonical keys, S1 asks S2 to resolve subjects; S2 may call IEG and return `graph_version`. 

**IJ-05 — Serve optionally requests identity/context:** `S3 ↔ S2`

* Only when needed for the request (and if used, `graph_version` must be recorded in provenance). 

### Policy/definition joins

**IJ-06 — Definitions feed update interpretation:** `S4 → S1`

* S1 needs “what groups exist + versions + how to interpret updates” as an authoritative input. 

**IJ-07 — Definitions feed serving:** `S4 → S3`

* S3 needs group registry (versioned) and TTL/freshness policy. 

### Basis / provenance joins

**IJ-08 — Watermark basis exported:** `T0 → S5`

* S5 reads applied checkpoints to form `input_basis` (per-partition exclusive-next offsets).  

**IJ-09 — Serve asks for provenance+hash:** `S3 ↔ S5`

* S3 delegates “build provenance + compute snapshot hash deterministically” to S5. 

**IJ-10 — Identity contributes graph_version:** `S2 → S5`

* If S2 consulted IEG for this serve/update context, S5 must include `graph_version` in provenance. 

### Ops / observability joins

**IJ-11 — Update plane emits health/lag:** `S1 → S6`

* Lag, stall, apply failures, checkpoint age. 

**IJ-12 — Serve plane emits health:** `S3 → S6`

* Latency/errors, missing/stale rates, request sizes. 

**IJ-13 — Policy changes observable:** `S4 → S6`

* Active policy rev and reload/activation events are exported as observable facts.  

### Lifecycle / rebuild joins

**IJ-14 — Lifecycle controls update/serve:** `S7 ↔ S1` and `S7 ↔ S3`

* Boot, readiness, throttling/backoff, controlled pause/resume. 

**IJ-15 — Lifecycle controls definitions:** `S7 ↔ S4`

* Loads policy profile rev; governs reload (profiles-not-forks). 

**IJ-16 — Lifecycle controls store semantics:** `S7 ↔ T0`

* Controlled rebuild/rehydration and compaction/retention rules (derived state only). 

### Optional audit pointer joins

**IJ-17 — Pointer emission feed:** `S3/S5 → S8`

* Successful serve produces snapshot hash + provenance; S8 may emit pointer events (if enabled). 

**IJ-18 — Pointer emitter health:** `S8 → S6`

* Queue depth / emit failures become observable. 

---

# 2) Internal paths (end-to-end flows inside the vertex)

These are the **production paths** that stitch the joins together.

### IP-1: Update/apply path (normal)

`IJ-01 → S1 → (IJ-04 optional via S2) → IJ-06 (defs) → IJ-02 (commit to T0) → IJ-11 (obs)`

This is “J7 becomes durable derived state + checkpoint truth.” 

### IP-2: Duplicate/redelivery no-op path

`IJ-01 → S1 → (detect already-applied update_id) → IJ-02 (checkpoint correctness) → IJ-11`

This exists because EB is at-least-once and updates must be replay-safe.  

### IP-3: Serve path (no IEG)

`J8 boundary → S3 → IJ-07 (defs) → IJ-03 (read T0 as-of) → IJ-09 (S5 provenance/hash using IJ-08 basis) → IJ-12 (obs) → response`

Pinned contract items show up here: explicit as-of, deterministic hash, provenance includes input_basis. 

### IP-4: Serve path (IEG consulted)

Same as IP-3 but inserts: `S3 → IJ-05 (S2) → (IEG) → IJ-10 (graph_version to S5)` before final provenance assembly. 

### IP-5: Policy activation / profile reload path

`S7 → IJ-15 (load/reload S4) → (S4 updates registry) → IJ-06/IJ-07 feed S1/S3 → IJ-13 observability`

This is the “feature versions don’t drift silently” path.  

### IP-6: Partition stall / fail-closed path

`S1 encounters uninterpretable-but-relevant event → (no checkpoint advance) → IJ-11 + S6 emits “stall/lag” → S7 may flip readiness/throttle`

This exists to preserve “watermarks don’t lie” and avoid silent drift.  

### IP-7: Rehydrate / rebuild path (derived-state only)

`S7 triggers rebuild → IJ-16 (reset/prepare T0) → S1 replays J7 intake from declared basis → IJ-02 checkpoint advancement → S6 observes catch-up`

This is the internal half of the platform’s “no time travel; rebuild derived truth explicitly” rule. 

### IP-8: Optional pointer emission path (OFF by default)

`IP-3/IP-4 success → IJ-17 (S8) → (emit to audit topic path externally) → IJ-18 + S6`

Only exists if you decide to enable snapshot pointer events. 

---

# 3) Internal loops (cycles) that exist in production

These are **within OFP’s internal network**, not the platform-wide loops.

### IL-1: Identity cache loop (hot-path efficiency without semantic drift)

`S1/S3 → S2 (resolve) → S2 caches mapping → S1/S3 hit cache on future requests`

This loop is inevitable in production if IEG calls are expensive, but must preserve determinism within ContextPins. 

### IL-2: Health/backpressure loop

`S1/S3/S8 → S6 (signals) → S7 (control decisions: throttle/pause/mark unready) → affects S1/S3/S8 behavior`

This is the internal mechanism that prevents OFP from silently limping (it becomes loudly unhealthy instead).  

### IL-3: Policy reload stabilization loop

`S7 loads policy rev → S4 validates/activates → S6 reports active rev → (if invalid) S7 keeps prior rev / marks unhealthy`

You need this loop so a bad profile can’t quietly corrupt meaning. 

### IL-4: Rebuild convergence loop

`S7 triggers rebuild → S1 replay/apply → checkpoints advance → S6 monitors lag → S7 declares ready when caught up`

This is the internal “projection becomes correct again” loop (tied to monotonic watermarks). 

### IL-5: Optional pointer emitter loop (if enabled)

`S3/S5 produce pointers → S8 queues/emits → S6 observes backlog → S7 may disable/throttle S8`

This loop keeps “audit hints” from becoming an outage vector. 

---

## Summary: the internal network in one sentence

**OFP’s internal network is two planes (Update + Serve) bound together by a durable store and a provenance/basis spine, with optional identity resolution and a lifecycle/ops control loop that keeps correctness explicit under replay, disorder, and rebuild.**  

---

Absolutely. We’ll illuminate **IJ-01 → IJ-07** as **internal boundary handshakes** (still *not* diving inside the boxes), and I’ll explicitly declare what is **in-bounds** vs **out-of-bounds** against the platform rails we pinned (ContextPins, canonical envelope, exclusive-next watermarks, no hidden “now”, version singularity).  

I’ll use this format for each join:

* **Purpose (which outer obligation it serves)**
* **Direction / initiator**
* **What crosses (minimum payload)**
* **Must-hold invariants**
* **Failure posture**
* **Out-of-bounds drift (banned)**

---

# IJ-01 — J7 Intake: EB DeliveredRecord → S1 Update Plane

### Purpose

Implements the start of **J7**: turn *admitted facts* into safe, replayable update candidates. This join is where “EB realities are real” (at-least-once, partition+offset truth). 

### Direction / initiator

**EB-delivery surface → S1** (S1 is the initiator of consumption but the join payload is “delivered record”).

### What crosses (minimum)

**DeliveredRecord** (conceptual):

* `stream_name` (must be `fp.bus.traffic.v1` in prod shape) 
* `partition_id`, `offset` (EB coordinate truth; exclusive-next checkpoint meaning derived from offsets) 
* `envelope` = **CanonicalEventEnvelope** with required fields
  `{event_id, event_type, ts_utc, manifest_fingerprint}` (+ optional pins).  

### Must-hold invariants

* **Envelope required fields must exist** (even if IG “should have validated”, S1 must fail closed if missing). 
* **ContextPins discipline:** if the event claims run/world joinability, it must carry full `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`. 
* **Time meaning:** S1 treats `ts_utc` as *domain event time* (meaning), never ingest/apply time.  
* **Classification is allowed:** unknown/uninteresting `event_type` may be treated as NO-OP (but still “processed” for checkpoint progression).

### Failure posture

* If **required envelope fields are missing** or `ts_utc` is malformed: **STALL-by-default** (do not advance that partition’s checkpoint), emit loud ops signal; skipping requires an **explicit Run/Operate action** (auditable) because otherwise your watermark basis would lie.  
* If event is valid but irrelevant: **NO-OP + advance checkpoint**.

### Out-of-bounds drift (banned)

* Treating ingestion time as meaning time. 
* Advancing checkpoint while silently failing to interpret a record that could affect features (that breaks the watermark=basis truth). 

---

# IJ-02 — S1 Update Plane → T0 OFP Durable Store (commit state + checkpoint)

### Purpose

This join is where OFP becomes a **projection with truthful progress tokens**: “if checkpoint says next_offset_to_apply=X, everything <X is applied or explicitly no-opped.” 

### Direction / initiator

**S1 → T0** (S1 commits; T0 persists).

### What crosses (minimum)

**ApplyUnit** (conceptual):

* `context_pins` (run/world scope) 
* `source_coord` = `(stream_name, partition_id, offset)` 
* `updates[]` each keyed by `(FeatureKey, FeatureGroupRef)`
* **idempotency identity per update** must be derivable as:
  `(stream_name, partition_id, offset, key_type, key_id, group_name, group_version)` (this recipe is locally defined but must exist and be stable). 
* `checkpoint_advance_to = offset + 1` (exclusive-next meaning). 

### Must-hold invariants

* **Atomicity requirement:** checkpoint advance is only durable if the associated updates are durable (or provably no-op). This is the core of “basis tokens don’t lie.” 
* **Event-time semantics:** updates must be applied in a way where out-of-order arrival cannot change meaning (order-independent). 
* **Version isolation:** group versions are part of the update identity; you never mix versions in the same accumulator. 

### Failure posture

* If T0 cannot commit: **do not advance checkpoint**; S1 will reprocess after restart (idempotency prevents double-count). 
* If an update is “rejected” internally (e.g., unsupported group version): that is **a policy/definition fault** → treat as stall + ops signal (not silent skip).

### Out-of-bounds drift (banned)

* “Advance checkpoint first, apply later.”
* Applying a change without being able to reproduce its update identity under replay. 

---

# IJ-03 — S3 Serve Plane → T0 OFP Durable Store (as-of reads)

### Purpose

Implements the data read side of **J8**: serve must be **as-of correct**, and must support a coherent basis token. 

### Direction / initiator

**S3 → T0** (S3 reads; T0 answers).

### What crosses (minimum)

**ReadRequest** (conceptual):

* `context_pins` 
* `feature_keys[]` (canonical keys only) 
* `group_refs[]` as `{group_name, group_version}` 
* `as_of_time_utc` (explicit boundary; no hidden now) 

**ReadResult** (conceptual):

* feature values (possibly sparse)
* per key×group: `last_update_event_time` (or “no data”) so freshness can be computed on event-time basis
* (optionally) a consistency token that S5 can map to an `input_basis` vector

### Must-hold invariants

* **No future leakage:** state returned must reflect `ts_utc <= as_of_time_utc`, independent of arrival order. 
* **Coherence:** S3 must be able to serve from a coherent state snapshot (so S5 can attach one `input_basis` per response). 
* **Run/world isolation:** never cross ContextPins boundaries in reads.

### Failure posture

* If T0 cannot provide an as-of correct read (e.g., corrupted indexes): **UNAVAILABLE** path outward; do not fabricate partial “best effort” answers. 

### Out-of-bounds drift (banned)

* Returning “latest” when caller asked “as-of”. 
* Using apply/ingest time to decide freshness. 

---

# IJ-04 — S1 Update Plane ↔ S2 Identity Resolution (for update keying)

### Purpose

Allows update processing to comply with the platform rule: **FeatureKeys must be canonical entity IDs**; if an event only has observed identifiers, S1 must obtain canonical keys via the identity subsystem. 

### Direction / initiator

Typically **S1 → S2 request**, **S2 → S1 response**.

### What crosses (minimum)

**IdentityResolveRequest** (conceptual):

* `context_pins` 
* `subject_bundle` = observed identifiers and/or already-known EntityRefs (opaque internal shape)
* `needed_key_types[]` (e.g., merchant/account/device) based on which groups will be updated

**IdentityResolveResult**:

* `feature_keys[]` (canonical)
* `resolution_source` = {direct, cache, IEG}
* if IEG was consulted: a `graph_version` token (monotonic watermark basis)  

### Must-hold invariants

* **Scope:** resolution is always scoped by ContextPins (no cross-run identity mixing). 
* **No raw identifier keys:** S2 must never output PAN/device_fp/etc as `key_id`.
* **Graph_version semantics:** if returned, it must be “applied offsets basis token,” not a wall-clock timestamp. 

### Failure posture

* If canonical keys are required for an update and resolution fails/unavailable: **S1 must not apply**; default is **stall that partition offset** (checkpoint doesn’t advance) + ops signal. 
* “Skip” is only via explicit ops/backfill action (auditable), not automatic.

### Out-of-bounds drift (banned)

* Baking “best effort identity guesses” into state updates.
* Caching identity mappings across ContextPins boundaries.

---

# IJ-05 — S3 Serve Plane ↔ S2 Identity Resolution (for serving)

### Purpose

Only needed if serving requires identity context beyond “caller already gave canonical FeatureKeys”.

### Direction / initiator

Typically **S3 → S2**.

### What crosses (minimum)

Two legitimate v0 uses:

1. **Request validation hardening:** if a caller ever sends non-canonical keys (shouldn’t happen if DF is correct), S3 can reject or (if you explicitly allow) normalize via S2.
2. **Optional graph/context enrichment:** if a feature group definition explicitly requires identity graph context.

### Must-hold invariants (v0 posture I’m pinning)

**PD-IJ-05-v0:** DF→OFP requests are expected to already contain canonical FeatureKeys; if not, that’s an **INVALID_REQUEST**, not an implicit “helpful resolution.” (Keeps boundaries sharp and avoids new hidden joins.)  

If S2/IEG is consulted during serving for any reason:

* **graph_version must be captured** and passed onward to provenance. 

### Failure posture

* If serving requires identity context and IEG is unavailable: **UNAVAILABLE** (retryable) outward; do not fabricate. 

### Out-of-bounds drift (banned)

* Turning OFP into an “identifier-based public API” that accepts raw identifiers by default (that drifts identity authority away from IEG and muddies audit). 

---

# IJ-06 — S4 Feature Definition & Policy → S1 Update Plane (how to interpret events)

### Purpose

This is the internal realization of the platform rail: **feature definitions are versioned and singular**. S1 must not “make up” what groups exist or how events update them.  

### Direction / initiator

**S1 reads/receives active registry snapshot from S4** (push or pull is implementation freedom; semantics are pinned).

### What crosses (minimum)

**ActiveFeatureDefSnapshot** (conceptual):

* `feature_def_policy_rev` (active revision identifier; profile-driven) 
* `groups[]` each with:

  * `{group_name, group_version}`
  * `key_type`
  * TTL/freshness policy inputs (even if only used at serve time)
  * **update interpretation mapping**: which `event_type` families can update this group, and the opaque transform hooks (implementation freedom)

### Must-hold invariants

* **No implicit “latest group version”:** group_version is part of meaning; S1 updates must be version-addressed. 
* **Deterministic activation:** changes happen via explicit profile rev activation (governed), not silent hot-reload drift. 
* **Snapshot consistency:** when applying one DeliveredRecord, S1 must use one coherent feature-def snapshot (no mid-record changes).

### Failure posture

* If definitions are unavailable/invalid at boot: **S1 must not start consuming** (or must immediately go unhealthy). Better to be unavailable than to produce unversioned semantics.

### Out-of-bounds drift (banned)

* S1 “parses payload and invents features” without a versioned definition anchor.
* Updating a group whose definition isn’t present in the active profile (silent drift).

---

# IJ-07 — S4 Feature Definition & Policy → S3 Serve Plane (validate groups + TTL semantics)

### Purpose

Serving must be compatible and explainable: **S3 cannot serve a group_version it cannot name/validate**, and freshness/TTL rules must come from the same singular definition authority. 

### Direction / initiator

**S3 reads/receives active registry snapshot from S4**.

### What crosses (minimum)

Same **ActiveFeatureDefSnapshot** as IJ-06, plus the serving-needed fields:

* feature identifiers list (stable naming)
* TTL policy per group (for stale computation)
* any deterministic ordering metadata (so hashing/canonicalization is stable) 

### Must-hold invariants

* **Validation:** requested `{group_name, group_version}` must exist in active snapshot or S3 must reject.
* **Freshness basis:** TTL/freshness is computed from **event-time** + explicit `as_of_time_utc`, never wall clock. 
* **Version recording:** S3 must record the exact group versions used in provenance/hashing (via S5 later). 

### Failure posture

* Unknown group/version: **INVALID_REQUEST** (client asked for something unsupported).
* Known group/version but no data: **success with stale/no-data posture**, not an error (that’s a data reality, not a contract violation).

### Out-of-bounds drift (banned)

* “Serve whatever latest group_version exists.”
* Computing stale using apply/ingest time or local wall clock. 

---

## Cross-join consistency pins (so IJ-01..07 don’t drift later)

**PD-IJ-C1 (authoritative):** S1 and S3 must both reference the *same* notion of “active feature definition snapshot,” and changes must be explicit profile rev activations (no silent divergence).  

**PD-IJ-C2 (authoritative):** Any time we cannot preserve the truth of the basis tokens (exclusive-next checkpoint meaning), we stall and surface operability signals; skipping requires explicit auditable ops action.  

---

Absolutely — IJ-08 through IJ-13 are the **“anti-drift spine”** (basis/provenance + observability). I’m going to pin them tightly because *this* is where platforms quietly lose determinism and auditability.

I’ll keep the same structure as before: **purpose → payload → invariants → failure posture → banned drift**.

---

# IJ-08 — Watermark basis exported: **T0 → S5**

*(S5 reads applied checkpoints to form `input_basis` watermark vector)*

### Purpose

Make the platform rail true: **replay/progress tokens are expressed only in EB coordinates** and are portable into provenance. `input_basis` is OFP’s “what facts had been applied for this snapshot” token.  

### What crosses (minimum payload)

**BasisSnapshot** (conceptual):

* `stream_name` (must identify the admitted fact stream; in prod: `fp.bus.traffic.v1`) 
* `watermarks` = map `{partition_id -> next_offset_to_apply}` (**exclusive-next offsets**)  
* (optional but strongly useful) `topic_epoch` / `partition_set_hash` (to make “which partitions existed” explicit in provenance)

### Must-hold invariants (authoritative)

* **Exclusive-next meaning is mandatory:** offsets are “next offset to read/apply,” not “last applied.”  
* **Coherence:** S5 must obtain a **single coherent vector** for one snapshot (no per-key/per-group bases). 
* **No hidden stream alias:** provenance must name the real stream identity (don’t invent “admitted_events” as a semantic token). 

### Failure posture

* If T0 cannot provide a coherent checkpoint vector, S5 **cannot complete provenance** → serving must return **UNAVAILABLE (retryable)**. “Don’t fabricate basis.”  

### Out-of-bounds drift (banned)

* Returning wall-clock “timestamp basis” instead of offsets. 
* Returning per-group/per-key watermarks (breaks snapshot identity). 
* Advancing checkpoints without corresponding state application (basis would lie). 

---

# IJ-09 — Provenance + hash handshake: **S3 ↔ S5**

*(S3 delegates “build provenance + compute deterministic snapshot hash” to S5)*

### Purpose

Fulfill the pinned OFP provenance contract: every `get_features` must return a deterministic `feature_snapshot_hash` and a complete provenance bundle including `input_basis` (+ `graph_version` if used). 

### Direction / initiator

**S3 initiates** (“I have a request + computed features; give me provenance+hash”), **S5 returns** (“here is the canonical provenance + hash”).

### What crosses (minimum payload)

**S3 → S5: SnapshotMaterial**

* `context_pins` 
* request summary: `feature_keys[]` + `group_refs[]` + `as_of_time_utc` (explicit) 
* computed `features_map` (stable structure; values may be sparse)
* per group/key: `last_update_event_time` (or “no data”) needed for TTL/freshness blocks 
* `group_versions_used[]` (explicit list) 
* any “warnings candidates” (stale/no-data), *not yet canonicalized*

**S5 → S3: ProvenancedSnapshot**

* `provenance` (pins, versions, freshness blocks, `input_basis`, `graph_version` if present, warnings) 
* `feature_snapshot_hash` (deterministic) 

### Must-hold invariants (authoritative)

* **No hidden “now”:** provenance freshness uses `as_of_time_utc`, not wall-clock.  
* **Stable ordering + canonicalization are mandatory** for hashing (lists sorted deterministically; maps serialized with stable key ordering; no float formatting drift).  
* **Hash inputs are pinned**: snapshot hash must cover the blocks that make parity possible (features, freshness, versions, `input_basis`, `graph_version` if present, etc.). 
* **One basis per response**: `input_basis` is a single vector for the snapshot. 

### Failure posture

* If any required provenance element cannot be completed (missing basis; missing required pins; missing group version discipline), S5 returns an error and S3 must respond **UNAVAILABLE** (retryable when it’s dependency/basis) or **INVALID_REQUEST** (when the request is malformed). No partial “best effort provenance.”  

### Out-of-bounds drift (banned)

* S3 invents its own hash/provenance rules (must be centralized in S5 to keep determinism stable). 
* Hash includes non-deterministic fields (wall clock, random UUIDs, unordered maps).  
* Omitting `input_basis` or `graph_version` when used (kills parity). 

---

# IJ-10 — Identity basis contribution: **S2 → S5**

*(If S2 consulted IEG, S5 must include `graph_version` in provenance)*

### Purpose

Bind identity context to the same replay-token philosophy: **`graph_version` is the identity-graph “what facts applied” token** and must be recorded whenever IEG influenced the snapshot.  

### What crosses (minimum payload)

**GraphContext** (conceptual):

* `graph_version` = `{stream_name, watermarks{partition->exclusive_next_offset}}` 
* `resolution_source` (cache vs IEG)
* (optional) a minimal “context summary” only if needed for provenance (but avoid heavy data here)

### Must-hold invariants (authoritative)

* **Meaning of graph_version is pinned:** a monotonic applied-offset watermark vector (+ stream_name), not timestamps. 
* **Inclusion rule:** if the snapshot depended on IEG (keys resolved, neighbors used, etc.), provenance must include the `graph_version` used. 
* **Separation of tokens:** OFP `input_basis` and IEG `graph_version` are *both* recorded when relevant (don’t conflate them).  

### Failure posture

* If `graph_version` is required (IEG consulted) but unavailable, treat as **UNAVAILABLE**. Do not “pretend graph_version unknown.”  

### Out-of-bounds drift (banned)

* “Graph version = current time” or “graph version = last cache refresh.” 
* Using cached identity results **without** a traceable `graph_version` basis when identity can change (that kills replay explainability). 

---

# IJ-11 — Update plane health/lag: **S1 → S6**

### Purpose

Support the platform’s ops loop: **lag/watermark age are safety signals** used by Degrade Ladder and operators; they must exist for every consumer.  

### What crosses (minimum payload)

Two channels: **metrics** (low-cardinality) + **structured events/logs** (boundary decisions).

**Metrics (minimum)**

* `consumer_lag{partition}` and **watermark_age{partition}** 
* update throughput (events/sec), apply latency, error rate by class 
* stall indicator (binary) + “stalled_offset” count gauge

**Structured boundary facts**

* “partition stalled at (stream,partition,offset)” with reason code (no raw payload), plus ContextPins when known. 

### Must-hold invariants (authoritative)

* **Correlation keys rule:** telemetry includes applicable subset of IDs (run pins; event_id/event_type/schema_version when emitting boundary facts). 
* **No secrets, no raw payload dumps.** 
* Metrics stay low cardinality; high-cardinality details go to sampled traces/logs. (This keeps prod workable while still explainable.)

### Failure posture

* Telemetry export failure must **not** break correctness (don’t stall J7 ingestion because Grafana is down).
* But: S6 must be able to surface “telemetry degraded” because DL safety depends on signals. 

### Out-of-bounds drift (banned)

* Logging raw admitted payload bodies “for debugging.” (By-ref posture says point to evidence, don’t copy it.) 
* Not emitting watermark age / lag (DL becomes blind). 

---

# IJ-12 — Serve plane health: **S3 → S6**

### Purpose

Make serving safe and explainable: DL/ops must know whether OFP is fast enough, stale, or returning missing data, and DF must be able to correlate failures with a request context.  

### What crosses (minimum payload)

**Metrics (minimum)**

* request throughput, p95 latency, error rate by `error_code` 
* **staleness rate** (per group optional, but at least global) 
* missing-feature rate 
* snapshot-hash compute failure rate 
* request size histograms (keys/groups counts) (to catch overload patterns)

**Structured boundary facts**

* On **UNAVAILABLE**: log/emit a structured “serve failed” fact including ContextPins (when known), request sizes, and *if a hash was computed before failure* include it; otherwise don’t invent. 

### Must-hold invariants (authoritative)

* **Correlation keys rule:** when available, include `feature_snapshot_hash`, `graph_version`, `input_basis` (or checkpoint token) in telemetry that relates to serving outcomes. 
* **No hidden now:** “staleness” must be computed from event-time vs `as_of_time_utc`, not wall clock.  

### Failure posture

* Same as IJ-11: serving must not fail *because* telemetry export failed, but S6 should surface the lack of observability as its own health issue. 

### Out-of-bounds drift (banned)

* Reporting “freshness” based on apply time or wall clock (“it looks fresh because we just processed it”). 
* Emitting high-cardinality per-request metrics keyed by run_id/event_id (kills metrics systems; use traces/logs for that). 

---

# IJ-13 — Policy changes observable: **S4 → S6**

### Purpose

Enforce “changes are facts”: **feature definition/version changes must be observable and auditable**, and runtime must report which policy revision is active.  

### What crosses (minimum payload)

**PolicyActivationEvent** (conceptual structured fact):

* `policy_id`, `policy_rev` (new active) 
* `previous_policy_rev` (if any)
* `activated_at` (operational timestamp, not a semantic token)
* `actor` / trigger (run/operate vs boot) 
* `result` = ACTIVATED | REJECTED (with reason codes)
* (optional) content digest of the policy artifact (by-ref integrity) 

S6 then exports this to logs/metrics/traces and (in dev/prod) the governance fact pipeline. 

### Must-hold invariants (authoritative)

* **No silent activation:** a change in feature definition rev must surface as an explicit observable fact. 
* **Runtime reports active rev:** every OFP telemetry stream should be able to answer “what policy rev was in force?”  
* Policy is split: **policy config is outcome-affecting and auditable; wiring config is not semantic** (but still logged for ops). 

### Failure posture

* If a new policy rev fails validation, OFP should **reject activation** and either remain on previous rev or go UNAVAILABLE depending on your desired safety posture. (My v0 preference: remain on last-known-good + emit a governance fact; only go UNAVAILABLE if no valid rev exists.)

### Out-of-bounds drift (banned)

* “Hot reload succeeded” only as a log line with no durable fact; or no way to tell which revision produced a snapshot. 
* Treating feature definitions as “just config files on disk” without revision identity. 

---

## Cross-join pins for IJ-08..IJ-13 (so we don’t drift later)

**PD-BP-01 (authoritative):** `input_basis` and `graph_version` are both **watermark-vector tokens**, and they are required provenance elements when their respective planes were involved.  

**PD-OBS-01 (authoritative):** OFP must always be able to answer, via telemetry:
“how far behind am I?” (lag + watermark age) and “what policy rev am I running?”  

---

Locked. We’ll illuminate **IJ-14 → IJ-18** as **production-grade internal handshakes** between opaque subnetworks — i.e., what S7/S8 are allowed to *control*, what they must *never* change, and the minimal signals/commands that have to exist so OFP survives the environment ladder without semantic drift.  

I’m going to **pin two lifecycle boundary decisions up front** (authoritative for the rest of this OFP deepening), because every one of IJ-14..16 depends on them:

## Pinned Decisions (lifecycle authority boundaries)

**PD-LIFE-01 — S7 may change *operational posture*, never *semantic meaning*.**
S7 can pause/resume/throttle/rebuild/reload policy; it cannot change: event-time semantics, idempotency keys, watermark meaning (exclusive-next), or version identity. That’s “profiles not forks” made real. 

**PD-LIFE-02 — Serve readiness and Update readiness are distinct, but both must be explicit.**

* OFP may be **SERVE_READY** even if Update Plane is behind (it will return explicit staleness + `input_basis`).
* OFP must **not** be SERVE_READY if it cannot produce complete provenance (`input_basis`, group versions, etc.).
* Update Plane may be paused (maintenance/rebuild) while Serve Plane is also paused or continues under a declared mode — but this is an **explicit posture** surfaced via S6.  

With those pinned, here are IJ-14..IJ-18.

---

# IJ-14 — Lifecycle controls Update/Serve: **S7 ↔ S1** and **S7 ↔ S3**

### Purpose

Make OFP “production-shaped” and survivable:

* safe boot sequencing (don’t consume before definitions/store are ready),
* controlled pause/resume (maintenance and rebuild),
* backpressure/throttling (to avoid uncontrolled lag spirals),
* explicit readiness/health posture (so DL/ops aren’t guessing). 

### Direction / initiator

Bidirectional:

* **S7 → S1/S3**: control commands (start/stop/pause/throttle, drain)
* **S1/S3 → S7**: state reports (ready, stalled, lagging, overloaded)

### What crosses (minimum payload)

#### A) Control commands (S7 → S1)

* `START_CONSUME(stream_name, consumer_group_id, start_policy)`
* `PAUSE_CONSUME(reason_code)`
* `RESUME_CONSUME()`
* `THROTTLE( max_events_per_sec | max_batches_inflight )`
* `DRAIN_AND_STOP(timeout_ms)` (finish in-flight apply units, flush checkpoints)

#### B) Control commands (S7 → S3)

* `OPEN_SERVE()` / `CLOSE_SERVE(reason_code)`
* `SHED_LOAD(policy)` (e.g., reject large requests, reduce concurrency)
* `SET_SERVE_LIMITS(max_keys, max_groups, timeout_ms)`

#### C) State reports (S1/S3 → S7)

* `UPDATE_STATE`: {CONSUMING | PAUSED | STALLED | DRAINING | STOPPED}
* `SERVE_STATE`: {OPEN | DEGRADED | CLOSED}
* `STALL_AT`: (stream, partition, offset, reason_code)
* `LAG_SUMMARY`: watermark age, partition lag summary (high level; S6 gets the detailed metrics)
* `PROVENANCE_CAPABLE`: boolean (“can I currently provide coherent `input_basis` + hashes?”)

### Must-hold invariants (authoritative)

* **No “semantic toggle” control:** S7 cannot ask S1/S3 to “switch to ingest-time semantics”, “ignore group versions”, “skip provenance”, etc. (PD-LIFE-01)
* **Explicit posture:** if S7 closes serving or pauses updates, that posture must be visible via S6 (so DL/DF can react safely). 
* **Drain is correctness-preserving:** `DRAIN_AND_STOP` must not acknowledge until checkpoints/state are durably consistent (ties to “basis tokens don’t lie”). 

### Failure posture

* If S1 reports **STALLED** (uninterpretable-but-relevant event): S7 must not “force advance” checkpoints. It may only (a) keep paused, (b) trigger explicit rebuild/backfill flow, or (c) require explicit Run/Operate override (auditable) — but never silent skip. 
* If S3 cannot compute deterministic provenance/hash (e.g., basis snapshot unavailable): S7 must close serving (SERVE_NOT_READY) rather than allow “best effort snapshots.” 

### Out-of-bounds drift (banned)

* S7 instructing “skip this event and keep going” without an explicit, auditable operational action.
* Serving responses during a posture where `input_basis` is unknown or incoherent.

---

# IJ-15 — Lifecycle controls definitions: **S7 ↔ S4** (profiles-not-forks)

### Purpose

Make “feature definition authority is singular + versioned” enforceable:

* OFP must run under an explicit **feature definition policy revision**,
* activation is explicit and observable,
* both S1 and S3 remain coherent (no mixed definition semantics).  

### Direction / initiator

* **S7 → S4**: load/validate/activate requests
* **S4 → S7**: activation result + active snapshot identity

### What crosses (minimum payload)

#### A) Load/activate request (S7 → S4)

* `LOAD_POLICY(policy_id, policy_rev, artifact_ref, expected_digest)`
* `VALIDATE()` (schema/consistency checks; no deep compute implied)
* `ACTIVATE()` (makes it the active definition snapshot)

#### B) Activation response (S4 → S7)

* `ACTIVE_FEATURE_DEF_SNAPSHOT`:

  * `policy_id`, `policy_rev` (identity)
  * `snapshot_digest` (by-ref integrity posture)
  * `group_inventory_fingerprint` (stable list hash of `{group_name, group_version}`)
  * (optional) `activation_epoch` (a monotonic “definitions epoch” token)

### Must-hold invariants (authoritative)

* **No silent hot change:** definition changes must go through S7→S4 activation and be observable (later via IJ-13). 
* **Atomic cutover (coherence rule):** within OFP, one request / one delivered record must use one coherent definition snapshot. Mixed-snapshot execution is banned.
* **Rollback is explicit:** if activation fails, OFP stays on last-known-good rev (or goes unavailable if none), and emits an observable rejection fact.

### Failure posture

* **No valid policy rev at boot:** OFP cannot be SERVE_READY or UPDATE_READY (it would be inventing semantics).
* **Activation fails in prod:** remain on last-known-good rev and surface a governance/ops signal; do not partially apply. 

### Out-of-bounds drift (banned)

* “Load latest from disk” or “whatever is in env var today” without revision identity.
* Definitions changing without an observable activation event.

---

# IJ-16 — Lifecycle controls store semantics: **S7 ↔ T0** (rebuild/rehydration + retention/compaction)

### Purpose

Support L5 / production reality:

* OFP’s state store is **derived and rebuildable**, but rebuild must be explicit and must not create “time travel” in served provenance.
* Compaction/retention are operational knobs that must not corrupt as-of correctness.  

### Direction / initiator

* **S7 → T0**: maintenance commands (prepare epoch, reset, snapshot, compact)
* **T0 → S7**: readiness + epoch status + integrity status

### What crosses (minimum payload)

#### A) Store lifecycle commands (S7 → T0)

* `INIT_STORE()` (create/open tables)
* `PREPARE_REBUILD(new_epoch_id)` (create new state epoch or staging area)
* `RESET_EPOCH(epoch_id)` (wipe only the *derived* epoch, not primary truths)
* `COMPACT(policy)` / `RETENTION(policy)` (event-time bucket retention rules)
* `SWAP_EPOCH(active_epoch_id)` (atomic promote of rebuilt epoch)

#### B) Store state report (T0 → S7)

* `STORE_READY(epoch_id)`
* `STORE_INTEGRITY_OK(epoch_id)`
* `CHECKPOINT_VECTOR(epoch_id)` (for readiness checks; detailed basis comes via IJ-08)
* `RETENTION_BOUNDARY_INFO` (what as-of horizon is safely answerable)

### Must-hold invariants (authoritative)

**PD-IJ16-01 — No provenance regression (anti–time travel).**
OFP must not produce responses whose `input_basis` regresses for the same ContextPins lineage. Therefore, rebuild is **epochal**:

* either serving is paused during rebuild, **or**
* OFP serves from the old epoch until the new epoch catches up, then atomically swaps. 

**PD-IJ16-02 — Retention/compaction must be compatible with “as-of” promises.**
If retention means older event-time buckets are gone, OFP must surface that as an explicit “cannot answer as-of earlier than X” posture (UNAVAILABLE or bounded response), not silently approximate. 

**PD-IJ16-03 — Only derived state is mutable here.**
S7↔T0 operations must never mutate primary truths (EB/Archive, labels, registry). This is a projection maintenance join only. 

### Failure posture

* If rebuild fails mid-way: keep old epoch active (or remain closed) and emit ops signals; do not half-swap.
* If integrity checks fail: OFP should be UNAVAILABLE rather than serve corrupted basis.

### Out-of-bounds drift (banned)

* Rebuild that silently changes meaning without producing an explicit operational fact.
* Serving during rebuild with a backward-moving checkpoint vector.

---

# IJ-17 — Pointer emission feed: **S3/S5 → S8** (optional; OFF by default)

### Purpose

If enabled, create **non-decisionable** audit/index hints without becoming a second truth stream.
This is explicitly optional in your production mapping for OFP. 

### Direction / initiator

* **S3/S5 → S8**: “pointer candidate” messages
* S8 asynchronously publishes outward (details live outside the vertex; inside we just define feed semantics)

### What crosses (minimum payload)

**SnapshotPointerCandidate**:

* ContextPins
* `as_of_time_utc`
* `feature_snapshot_hash`
* group versions used + freshness posture
* `input_basis`
* `graph_version` (if used)
* `feature_def_policy_rev`
* optional `snapshot_ref` (by-ref locator) + digest (if you persist snapshot blobs)

### Must-hold invariants (authoritative)

* **Non-decisionable:** pointer events must never be consumed as decision inputs (they’re hints/indexing only).
* **No serve coupling:** failure to emit pointers must not change `get_features` correctness.
* **Enablement is profile-driven:** ON/OFF is an environment profile knob; default OFF in v0. 

### Failure posture

* If S8 is enabled but unhealthy: it emits health signals (IJ-18) and may drop/queue pointers based on its own bounded policy — but it must not stall serving.

### Out-of-bounds drift (banned)

* Making pointer emission a prerequisite for serving (“serve only if pointer published”).
* Putting full feature blobs on the bus as “pointers” (breaks by-ref posture and explodes volume).

---

# IJ-18 — Pointer emitter health: **S8 → S6**

### Purpose

If S8 exists, it must not become an outage vector. S6 must see:

* backlog,
* publish failures,
* drop counts,
* enablement state,
  so S7/ops can disable/throttle it safely.  

### What crosses (minimum payload)

**Metrics**

* queue depth / backlog age
* publish success rate / failure rate
* retries / dead-letter counts
* pointer emission rate (events/sec)

**Structured boundary facts**

* “pointer publish failed” with reason code (no payload dump), and correlation keys like snapshot hash when available.

### Must-hold invariants

* Low cardinality metrics; detailed debugging via sampled logs/traces.
* Correlate to `feature_snapshot_hash` only in logs/traces, not as metric labels (avoid cardinality explosion).

### Failure posture

* If S6 pipeline is degraded, pointer health still should be locally visible (logs), but pointer emission must remain decoupled from serving.

### Out-of-bounds drift (banned)

* High-cardinality metrics keyed by run_id / snapshot_hash.
* Emitting raw snapshot payloads in error logs.

---

## The “shape” you should keep in mind as we go deeper

Inside OFP, **S7 is the operational governor**:

* it sequences boot (definitions → store → consume → serve),
* it makes rebuild explicit and non-regressive (epoch swap),
* it enforces profile-driven changes (not code forks),
* and it keeps all disruption *observable*.

While **S8 is optional** and must never be allowed to affect correctness.

---

Locked. We’ll illuminate **IP-1 → IP-4** as **production-grade internal paths** composed of the already-defined internal joins (IJ-01…IJ-13), while keeping each subnetwork (**S1…S6 + T0**) opaque.

I’m going to pin **one** extra “anti-drift” decision now because it matters for IP-3/IP-4 correctness:

**PD-IP-COH-01 (authoritative):** *Serve responses must be computed against a single coherent “read view” of T0 that ties feature values and `input_basis` together.*
Meaning: S3 must not read features “now” and then later ask S5 for a basis vector from a different moment. T0 must support a coherence token (opaque; implementer choice) so S5’s `input_basis` matches the state S3 read.

---

# IP-1 — Update/apply path (normal)

`IJ-01 → S1 → (IJ-04 optional via S2) → IJ-06 (defs) → IJ-02 (commit T0) → IJ-11 (obs)`

## What this path guarantees

* A delivered admitted fact becomes **durable derived state** + **truthful checkpoint advance** (exclusive-next).
* Any identity resolution used to apply the update is handled explicitly (optional S2), never guessed.
* The update semantics are anchored in a versioned feature-def snapshot (S4).

## Preconditions (must be true to start “real apply”)

* OFP has an **active feature definition snapshot** (S4 active via lifecycle).
* T0 is available for atomic commit of (state mutations + checkpoint advance).
* S1 is in a consuming posture (not paused/rebuilding).

## Steps (opaque internals, explicit handshakes)

1. **Ingest delivered record** (IJ-01)

   * Receive `(stream, partition, offset)` + canonical envelope `{event_id, event_type, ts_utc, manifest_fingerprint, pins…}`.
   * Classify event_type: *relevant* vs *irrelevant* to any known feature groups.

2. **Load the authoritative interpretation frame** (IJ-06)

   * S1 obtains the **active feature-def snapshot identity** and the event→group applicability mapping.
   * This step decides *which* groups/versions this event could update and *which key_types* are required.

3. **Derive canonical subjects / keys if needed** (IJ-04 optional)

   * If the event already carries canonical entity refs → skip identity.
   * If it carries only observed identifiers and the event is relevant → request resolution from S2:

     * Provide ContextPins + identifier bundle + required key_types.
     * Receive canonical FeatureKeys (+ `graph_version` only if IEG was consulted).

4. **Assemble the ApplyUnit** (still inside S1, but boundary obligations are pinned)
   The ApplyUnit must be derivable as:

   * ContextPins scope
   * source coord `(stream, partition, offset)`
   * list of per-(FeatureKey×FeatureGroupRef) update candidates
   * stable update identity per update:
     `(stream, partition, offset, key_type, key_id, group_name, group_version)`

5. **Commit apply + checkpoint atomically** (IJ-02)

   * Persist state mutations (order-independent semantics)
   * Advance checkpoint to `offset+1` (exclusive-next)
   * **Atomicity requirement:** checkpoint advance is durable *iff* the state effects are durable (or proven no-op).

6. **Emit operability signals** (IJ-11)

   * Update throughput / apply latency / error classes
   * Lag/watermark age and any stall indicators
   * Boundary facts like “partition applied offset N” (low cardinality) and “stalled at offset X” (structured log/event)

## Branches / failure posture (production)

* **Unknown/uninteresting event_type:**
  NO-OP state mutation but still checkpoint-advancing (because the fact is “processed” for OFP’s purposes).
* **Relevant event but missing required envelope fields / malformed `ts_utc`:**
  **STALL** (do not advance checkpoint), emit loud boundary signal.
* **Relevant event requires identity, but S2/IEG unavailable:**
  **STALL** at that offset (do not advance), emit boundary signal.
* **Feature-def snapshot missing/unavailable:**
  S1 must not proceed (pause/stop consuming); serving may also be closed depending on policy.
* **T0 commit fails:**
  No checkpoint advance; replay will re-deliver (idempotency makes it safe).

## Drift traps (banned)

* Advancing checkpoint without durable application.
* Applying updates using “latest defs” mid-record (mixed snapshot).
* Using ingest/apply time as meaning time (must be `ts_utc`).

---

# IP-2 — Duplicate/redelivery no-op path

`IJ-01 → S1 → (detect already-applied update_id) → IJ-02 (checkpoint correctness) → IJ-11`

## What this path guarantees

* At-least-once redelivery and replays do **not** double-apply updates.
* OFP can still advance checkpoints truthfully even when the record is a duplicate.

## Steps

1. **Ingest delivered record** (IJ-01).
2. **Use defs to decide relevance** (IJ-06).
3. **(Optional) identity resolution** (IJ-04) only if the event is relevant and keys aren’t already canonical.
4. **Compute the per-update identities** for the affected key×group pairs:
   `(stream,partition,offset,key_type,key_id,group_name,group_version)`
5. **Detect duplicates** (inside S1/T0 semantics)

   * If every update_id is already present/applied, the event’s effect is a pure NO-OP.
6. **Commit checkpoint advance** (IJ-02)

   * Checkpoint advances to `offset+1` because the fact is accounted for (its effects already exist).
7. **Emit obs** (IJ-11): a duplicate counter + low cardinality signals.

## Failure posture

* If duplicate detection is uncertain because T0 is unavailable → treat as commit failure (no checkpoint advance) and retry on replay.

## Drift traps (banned)

* “Skip duplicate without advancing checkpoint.” That causes permanent lag and breaks basis tokens.
* Dedupe that ignores group_version (version drift through dedupe).

---

# IP-3 — Serve path (no IEG)

`J8 boundary → S3 → IJ-07 (defs) → IJ-03 (read T0 as-of) → IJ-09 (S5 provenance/hash using IJ-08 basis) → IJ-12 (obs) → response`

## What this path guarantees

* DF gets a deterministic snapshot as-of an explicit time with complete provenance and a stable hash.
* No identity graph dependency is used (so no `graph_version` is required).

## Preconditions

* S3 is in SERVE_OPEN posture (lifecycle).
* Active feature-def snapshot is available (S4).
* T0 can support “as-of correct read” and coherent basis capture (PD-IP-COH-01).

## Steps

1. **Receive get_features request** (J8 boundary into S3)

   * ContextPins
   * canonical FeatureKeys
   * `{group_name, group_version}` list
   * `as_of_time_utc` (explicit)

2. **Validate groups + fetch rules** (IJ-07)

   * Confirm each requested group_version exists in active def snapshot.
   * Fetch TTL/freshness rules and any stable ordering metadata.

3. **Acquire a coherent read view** (PD-IP-COH-01; realized via IJ-03 + IJ-08)
   Conceptually:

   * S3 requests T0 read “as-of” state **and** obtains a coherence token (opaque).
   * S3 reads feature values and per-key/group “last update event time” from that view.

4. **Ask S5 for provenance + hash** (IJ-09)

   * S3 passes request summary + computed values + last-update times + group versions used.
   * S5 obtains `input_basis` from T0 (IJ-08) **using the same coherence token**, and assembles provenance:

     * ContextPins, as_of, group versions, freshness posture, warnings, `input_basis`
   * S5 computes deterministic `feature_snapshot_hash` (stable ordering / canonicalization).

5. **Emit serve health** (IJ-12)

   * latency, errors, staleness/missing rates, hash failures, request-size histograms
   * structured “serve failed” facts on UNAVAILABLE without dumping payloads

6. **Return response**

   * snapshot + provenance + hash (complete, deterministic)

## Failure posture

* Unknown group_version → INVALID_REQUEST (not retryable).
* T0 cannot serve as-of correctly or cannot provide coherent basis → UNAVAILABLE (retryable).
* S5 cannot compute hash/provenance → UNAVAILABLE (retryable) (no partial provenance).

## Drift traps (banned)

* Using “latest applied” instead of as-of.
* Returning a hash without `input_basis`.
* Hashing unordered data / including wall clock.

---

# IP-4 — Serve path (IEG consulted)

Same as IP-3, but inserts `S3 → IJ-05 (S2) → (IEG) → IJ-10 (graph_version to S5)` before final provenance assembly.

## When IP-4 is allowed (v0 pin)

**Default v0 stance:** DF sends canonical FeatureKeys, so IP-4 should be *rare* and only used when a requested feature group explicitly requires identity-graph context.

## Steps (differences only)

1–3) Same as IP-3 up through group validation and (possibly) T0 read view acquisition.

4. **Identity context request** (IJ-05)

   * S3 asks S2 for the required identity context for this request scope.
   * S2 may consult IEG. If it does, it returns a **`graph_version`** token (watermark vector semantics).

5. **Graph_version is bound into provenance** (IJ-10)

   * S2 passes graph_version to S5 as GraphContext.
   * S5 includes graph_version in provenance and in the hash inputs (so parity can account for identity context).

6–7) Same as IP-3: provenance/hash + obs + response.

## Failure posture (key difference)

* If identity context is required for correctness and IEG is unavailable → UNAVAILABLE (retryable).
* Never “serve without graph_version” when IEG was consulted or required.

## Drift traps (banned)

* Calling IEG and then not recording graph_version.
* Accepting raw identifiers in the API and “helpfully resolving them” by default (boundary drift).

---

## One cross-cutting “sanity check” before we go deeper

These four paths collectively enforce: **truthful progress tokens + deterministic snapshots + explicit failures**.
If any later internal design choice would force us to violate *checkpoint truth*, *as-of semantics*, or *provenance completeness*, that choice is out-of-bounds.

---

Locked — illuminating **IP-5 → IP-8** as **production internal paths** (subnetworks still opaque). I’ll keep them *behaviorally precise* and I’ll declare **in-bounds vs banned** where drift usually creeps in.

---

## IP-5 — Policy activation / profile reload path

**`S7 → IJ-15 (load/validate/activate S4) → IJ-06/IJ-07 feed S1/S3 → IJ-13 + S6 observability`**

### Purpose (what this path must guarantee)

* Feature definitions are **versioned + singular** and OFP never “silently changes meaning.” 
* Policy/profile changes follow the platform rule: **policy config is a versioned artifact, changes are auditable facts, profiles not code forks.**  

### Preconditions

* S7 has selected a **policy profile revision** (feature definitions/versions) from the environment profile (local/dev/prod differ by profile, not semantics). 
* S4 can load the policy artifact by-ref and validate it.

### Steps (opaque internals, explicit handshakes)

1. **Trigger**: S7 receives a policy activation intent

   * Cause can be boot, or “activate policy rev X” (governed change). 

2. **Load + validate** (IJ-15)

   * S7 asks S4 to `LOAD(policy_id, policy_rev, digest/ref)` then `VALIDATE()`.
   * Validation means: the artifact is well-formed and self-consistent (e.g., group inventory integrity). 

3. **Activate** (still IJ-15)

   * S4 produces an **ActiveFeatureDefSnapshot identity**: `(policy_id, policy_rev, snapshot_digest, group_inventory_fingerprint)` and marks it active for OFP.

4. **Coherent cutover to S1/S3** (IJ-06 / IJ-07)

   * S1 Update Plane and S3 Serve Plane begin using the new snapshot for new work.
   * **Pinned coherence rule:** one DeliveredRecord and one get_features request must each see one coherent snapshot (no mixing).

5. **Emit “change is a fact”** (IJ-13 via S4→S6)

   * S6 emits a durable/observable fact: “policy rev X became active,” with actor/scope/reason. 
   * OFP telemetry thereafter must be able to answer: “which policy rev was in force?” 

### Hard invariants (authoritative)

* **Policy change is not silent**: activation must be observable/auditable. 
* **B3 anti-drift law**: group versions are the unit of meaning; OFP records them and they must align with offline and bundles. 
* **Profiles not forks**: no “if prod do X else do Y” behavior; activation is profile selection + governed change. 

### Failure posture

* If new policy rev fails validation: **reject activation**, remain on last-known-good, and emit a visible rejection fact (don’t partially apply).  
* If there is **no valid policy** at boot: OFP must not claim correctness (SERVE_NOT_READY / UNAVAILABLE).

### Banned drift

* “Load latest from disk” without revision identity. 
* Changing the meaning of an existing `{group_name, group_version}` across policy revs (that violates “versioned meaning”). 

---

## IP-6 — Partition stall / fail-closed path

**`S1 hits uninterpretable-but-relevant fact → no checkpoint advance → IJ-11/S6 signals → S7 control`**

### Purpose

Preserve the platform’s determinism rails:

* **Watermarks don’t lie** and stay monotonic. 
* When a fact *should* influence features but OFP can’t safely apply it, OFP must **fail closed and make it operably visible**, not silently skip. 

### Typical stall triggers (production reality)

* Missing/invalid required envelope fields needed to interpret the update
* Unsupported `(event_type, schema_version)` shows up as “I can’t interpret it” (even if IG should have prevented it) 
* Required identity resolution unavailable (IEG down / timeout)
* Definition snapshot missing required mapping for a relevant event → indicates a policy/compat fault

### Steps

1. **Detection inside S1**

   * S1 classifies the DeliveredRecord as **relevant** to at least one active feature group (per IJ-06), but cannot derive a safe ApplyUnit.

2. **Fail-closed checkpoint discipline**

   * S1 does **not** advance the partition checkpoint past that `(stream, partition, offset)` (exclusive-next token remains truthful). 

3. **Emit boundary truth signals** (IJ-11 → S6)

   * S6 receives a structured “partition stalled at offset X” fact + reason code.
   * Lag/watermark age metrics rise (DL/ops can see it).  

4. **Operational control reaction** (S7 ↔ S1/S3 via IJ-14)

   * S7 may pause consumption, throttle, or close serving if OFP cannot produce complete provenance.
   * Otherwise, serving may continue **honestly**: `input_basis` shows lag and freshness blocks go stale (explicitly) rather than pretending correctness. 

### Hard invariants (authoritative)

* **No “best effort parse” that yields partial truth** is the platform posture; when you can’t validate/interpret, you quarantine/stall, not guess. 
* **Watermarks are truth tokens**; advancing them while skipping relevant facts is banned. 

### Resolution moves (still within platform rails)

* Fix the cause (policy rev update, schema support, dependency restore), then resume apply.
* If the fix requires recompute, use **IP-7 rebuild** (declared and auditable), not silent skipping.

### Banned drift

* “Skip this one offset and keep going” without an explicit, auditable Run/Operate override (that breaks the meaning of `input_basis`).  

---

## IP-7 — Rehydrate / rebuild path (derived-state only)

**`S7 triggers rebuild → IJ-16 prepares/reset T0 epoch → S1 replays from declared basis → checkpoints advance → S6 observes convergence → epoch swap`**

### Purpose

Implement the platform’s history/backfill laws inside OFP:

* **Backfill/reprocess is declared and auditable**. 
* **Archive extends EB** for long horizons (no second truth).  
* **Derived stores (IEG/OFP) are rebuildable; primary truths are not mutated.**  

### Preconditions

* A **declared rebuild/backfill plan** exists, including:

  * scope (streams/partitions/time window),
  * explicit replay basis (offset ranges/checkpoints),
  * reason,
  * outputs to regenerate, and
  * policy rev(s) in force for the rebuild. 

### Steps (production-safe, no time travel)

1. **Explicit trigger**

   * S7 receives a rebuild command as a declared operation (actor/reason/scope/basis). 

2. **Prepare new derived epoch** (IJ-16)

   * S7 instructs T0 to `PREPARE_REBUILD(new_epoch)` and reset/initialize only the *derived* OFP epoch. 

3. **Replay from declared basis**

   * S1 consumes admitted facts from EB retention and/or Archive (as continuation), bounded by the explicit replay basis.  

4. **Apply + checkpoints** (IJ-02 discipline)

   * S1 advances exclusive-next checkpoints as it applies (same idempotency and event-time semantics as normal operation).

5. **Convergence monitoring** (S6)

   * S6 tracks lag/watermark age and “rebuild progress” signals. 

6. **Atomic swap** (IJ-16)

   * Once the rebuilt epoch has reached the target basis, S7 swaps the active epoch atomically (no partial swap).
   * This prevents “basis regression” in served provenance.

7. **Emit a durable governance fact**

   * “Backfill Z executed; outputs regenerated; basis used; policy rev used.”  

### Hard invariants (authoritative)

* **Backfill never silently overwrites truth**; it regenerates derived outputs and leaves an audit trail. 
* **Monotonic progress tokens**: offsets/watermarks retain their meaning; the active served basis must not regress. 

### Environment ladder note

* Local/dev can make rebuild “easy” (drop DB, replay), but it still must be **explicit** and **record which basis/policy rev** was used; prod requires governed execution.  

### Banned drift

* Rebuild that changes meaning without recording the policy rev / basis (kills reproducibility).  
* Any rebuild that implies “history changed” (it didn’t; you rebuilt derived state). 

---

## IP-8 — Optional pointer emission path (OFF by default)

**`(IP-3/IP-4 success) → IJ-17 (S8) → publish pointer event → IJ-18 + S6 health`**

### Purpose

Provide an **index/discovery hint** channel (e.g., audit/search), without creating a second truth stream for decisioning.

This is explicitly optional in the production mapping: OFP may emit **optional snapshot pointer events → `fp.bus.audit.v1`**.  

### Steps

1. **After a successful serve** (IP-3/IP-4), S3/S5 produce a `SnapshotPointerCandidate` (hash + provenance fields).
2. **Enqueue to S8** (IJ-17)

   * Must be fully decoupled from serving correctness.
3. **Publish outward**

   * Pointer event is emitted as *metadata by-ref*, never full feature blobs.
4. **Observe emitter health** (IJ-18 → S6)

   * queue depth, publish failures, drop/retry rates.

### Hard invariants (authoritative)

* **Non-decisionable**: pointer stream must not be used as an input to DF/OFP/IEG decisioning logic. It’s an index/hint surface.
* **Serve independence**: pointer emission failure must not make `get_features` fail (correctness first; index later).
* **Enablement is profile-driven** and default OFF in v0 (you already have DF→DLA provenance for audit).  

### Production-friendly design pins (I’m declaring these)

**PD-IP8-01:** Pointer events must be **idempotent** by construction (e.g., event_id derived deterministically from `feature_snapshot_hash`), so retries don’t spam the audit topic.
**PD-IP8-02:** S8 must have bounded behavior (sampling, rate limits, drop policy) so it cannot become an outage vector; emitter health is surfaced via IJ-18 and can be disabled by S7.

### Banned drift

* Emitting full snapshot payloads to the bus “for convenience.” (Violates by-ref posture and blows up volume.) 
* Making pointer publication a prerequisite for serving.

---

### Quick cross-check: how these four paths uphold your rails

* **IP-5** enforces “feature meaning is governed + versioned + observable.”  
* **IP-6** enforces “watermarks don’t lie; fail closed, visible.”  
* **IP-7** enforces “backfill is declared; derived stores rebuild; archive continues facts; no time travel.”  
* **IP-8** (optional) stays strictly “index/hint,” never a second decision truth, and is profile-controlled.  

---

Got it. Here are **IL-1 → IL-5** as **production internal loops** across the opaque subnetworks (**S1–S8 + T0**) — i.e., the cycles that *must* exist so OFP stays correct under replay, disorder, profile changes, rebuilds, and operational stress.

I’ll keep each loop at the “network boundary” level: **what circulates, why it circulates, what must never change, and how it fails**.

---

## IL-1 — Identity cache loop

`S1/S3 → S2 (resolve) → (IEG optional) → S2 caches → S1/S3 hit cache`

### Why this loop exists

IEG calls are expensive; OFP still needs canonical FeatureKeys. So S2 memoizes identity resolution while preserving determinism + auditability. 

### What circulates in the loop

* **Request:** `(ContextPins, observed_identifiers bundle, required key_types)` 
* **Response:** `FeatureKeys (canonical entity IDs)` + **graph_version token if identity context depended on IEG** 

### Pinned decisions (authoritative)

**PD-IL1-01 — Cache must be scoped by ContextPins.**
No cross-run/world identity memoization. (Cache key includes ContextPins.) 

**PD-IL1-02 — Any identity result influenced by IEG must carry a `graph_version` token even when served from cache.**
Rationale: the platform pin is “record graph_version whenever IEG context is used,” and caching is still “IEG context via memoization.” 

**PD-IL1-03 — Cache hits must be observationally invisible to correctness.**
Hit/miss can change latency, not results. If results differ on hit vs miss, the boundary drifted.

### Failure posture

* **Update path (S1):** if identity is required and cannot be resolved → **stall that partition offset** (don’t advance checkpoint). 
* **Serve path (S3):** if identity context is required → **UNAVAILABLE** (retryable) rather than inventing identity. 

### Environment ladder note

Local may run with a tiny cache or none, but the **semantics must match** (same canonical keys, same graph_version handling). 

---

## IL-2 — Health/backpressure loop

`S1/S3/S8 → S6 (signals) → S7 (control decisions) → affects S1/S3/S8`

### Why this loop exists

This is how OFP avoids “silently limping.” It turns internal stress into **explicit posture**: throttle/pause/close-serve/disable pointer emitter, and it makes those changes visible for safe operation.  

### What circulates in the loop

* **Signals in:** consumer lag + watermark age, apply failures, serve latency/errors, staleness/missing rates, pointer backlog (if enabled) 
* **Controls out:** pause/resume consume, throttle, shed serve load, close serving, disable/limit S8 pointer emission (operational knobs only)

### Pinned decisions (authoritative)

**PD-IL2-01 — S7 may only change operational posture, never semantic meaning.**
No “switch to ingest-time,” no “ignore group_version,” no “skip provenance.”  

**PD-IL2-02 — Correctness overrides availability:**
If OFP cannot produce **complete provenance** (`input_basis` and required blocks), serving must be **closed** (UNAVAILABLE) rather than returning partial truth.  

**PD-IL2-03 — Thresholds/hysteresis are policy-profile driven.**
This prevents environment forks: same code, different profiles. 

### Failure posture

* Telemetry pipeline down must not break correctness, but OFP must surface “telemetry degraded” as a health fault (because DL/ops depend on these signals). 

### Environment ladder note

Local can be noisy/high-sample; prod is sampled — but **the signal semantics are identical** (lag means lag; watermark age means watermark age).  

---

## IL-3 — Policy reload stabilization loop

`S7 loads policy rev → S4 validates/activates → S6 reports active rev → S7 confirms/rolls back`

### Why this loop exists

Feature meaning is versioned and singular. This loop ensures **bad profiles cannot silently corrupt OFP**, and every change is a visible fact.  

### What circulates in the loop

* **Activation intent:** `(policy_id, policy_rev, artifact_ref, expected digest)`
* **Activation result:** `ACTIVE` or `REJECTED(reason)` + active snapshot identity
* **Observable fact:** “policy rev X became active / rejected” with actor/scope/reason 

### Pinned decisions (authoritative)

**PD-IL3-01 — No silent activation.**
A policy rev change must be observable and citeable in runtime telemetry and provenance.  

**PD-IL3-02 — Coherent cutover:**
One DeliveredRecord and one get_features request must each see a single definition snapshot (no mid-flight mixing). (Cutover can be implemented by pausing S1 briefly or by epoch barrier; mechanism is flexible.)

**PD-IL3-03 — Fail closed on “no valid policy.”**
If there is no valid active snapshot, OFP cannot claim correctness. 

### Failure posture

Reject new policy rev; remain on last-known-good and emit a durable rejection fact. Only go UNAVAILABLE if *no* valid rev exists.  

### Environment ladder note

Local/dev may reload frequently; prod activation is governed, but **the same activation lifecycle exists everywhere** (proposed → validated → active, with auditable facts).  

---

## IL-4 — Rebuild convergence loop

`S7 triggers rebuild → S1 replay/apply → checkpoints advance → S6 monitors lag → S7 declares ready / swaps epoch`

### Why this loop exists

This is how OFP stays correct over time when:

* you need a declared backfill/reprocess,
* you change feature definitions,
* you recover from corruption/stalls,
* retention/archival boundaries change.

And it must preserve the platform truth: **watermarks remain monotonic; no time travel.**  

### What circulates in the loop

* **Declared rebuild plan:** `(scope, purpose, explicit replay basis, outputs, policy revs used)` 
* **Progress tokens:** per-partition exclusive-next checkpoints/watermarks (monotonic)  
* **Readiness signal:** “rebuilt epoch caught up to target basis; safe to swap”

### Pinned decisions (authoritative)

**PD-IL4-01 — Rebuilds are explicit, scoped, and auditable.**
No “we ran it again”; every rebuild produces a governance fact with basis and outputs.  

**PD-IL4-02 — No basis regression:**
Serving must not produce an `input_basis` that goes backward for the same lineage. Use epoch swap (serve old epoch until new epoch catches up, then swap) or close serving during rebuild. 

**PD-IL4-03 — Archive is a continuation of admitted facts:**
Rebuild beyond retention reads archive “as if EB,” with an explicit basis declaration.  

### Failure posture

* Rebuild fails → keep old epoch active (or remain closed), never half-swap.
* Any operation that would require “skipping a fact” must be an explicit, auditable override (otherwise watermarks lie).  

### Environment ladder note

Local/dev can rebuild cheaply (drop derived DB, replay), but still must record the declared basis/policy rev used (otherwise parity can’t be trusted).  

---

## IL-5 — Optional pointer emitter loop (if enabled)

`S3/S5 produce pointer → S8 queues/emits → S6 observes backlog → S7 throttles/disables S8`

### Why this loop exists

If you enable snapshot pointer emission (optional), you need a loop that prevents “audit hints” from becoming an outage vector. Deployment mapping explicitly lists optional snapshot pointer events to `fp.bus.audit.v1`. 

### What circulates in the loop

* **Pointer candidates:** `(feature_snapshot_hash, ContextPins, as_of_time_utc, group versions, freshness, input_basis, graph_version if used, policy_rev, optional snapshot_ref)`
* **Emitter health:** queue depth/backlog age, publish failure rate, drop/retry counts

### Pinned decisions (authoritative)

**PD-IL5-01 — Pointer emission is non-decisionable metadata.**
It must never become an input to DF/OFP/IEG logic; it’s an index/hint channel only. 

**PD-IL5-02 — Pointer emission cannot affect serving correctness.**
If S8 is down, serving continues (or fails) for serving reasons only.

**PD-IL5-03 — Profile-controlled enablement, bounded behavior.**
S7 can disable/throttle S8 under load; emitter must be rate-limited/sampled to avoid flooding. 

### Failure posture

* S8 backlog/failures → S6 surfaces it, S7 throttles/disables S8; no coupling to `get_features` success.

### Environment ladder note

Typically OFF in local/v0; enable in dev/prod only if you actually need index feeds beyond DF→DLA provenance (which already exists). 

---

## Cross-loop constitution (what these loops collectively enforce)

* **Watermarks don’t lie; progress is monotonic and meaningful** (supports `input_basis` and `graph_version`).  
* **Changes are facts** (policy rev activations, backfills, retention changes) — never silent.  
* **Profiles not forks** (operational envelope varies, semantics don’t).  

---

Yes — there’s a whole class of **“non-joins / anti-edges / forbidden paths”** that we should pin explicitly, because *this* is where drift sneaks in later (“it was convenient so we just…”).

Below is the **authoritative “OFP non-join set”**: things that **must not exist** in a production-ready graph (externally and internally), plus a few **allowed-only-under-explicit-flag** edges.

---

## A) External anti-joins (edges that must not exist)

### NJ-A1 — **Producer → OFP is forbidden**

All producers (engine adapter, external txns, DF outputs, AL outcomes, etc.) must go **Producer → IG → EB**.
OFP never accepts raw producer traffic directly.

### NJ-A2 — **OFP must not bypass EB**

OFP must not read “facts” from anywhere except **EB (and Archive continuation for explicit rebuild)**.
No direct ingestion from:

* Data Engine datasets/output locators
* IG quarantine store
* DF/AL internal logs
* “latest transactions” DBs

### NJ-A3 — **OFP must not validate/admit traffic**

Admission semantics are owned by IG. OFP is a consumer/projector, not a trust boundary.

### NJ-A4 — **OFP must not be a “bundle resolver”**

OFP must not talk to Registry to decide “which model is active” or “which features to serve.”
That’s DF+Registry territory.

### NJ-A5 — **OFP must not talk to Label Store**

Labels are offline truth and decision/audit truth, not serving inputs.

### NJ-A6 — **OFP must not decide degrade posture**

OFP emits health signals; **DL decides posture; DF obeys mask**.
No direct **OFP ↔ DL** control coupling.

### NJ-A7 — **OFP must not emit decisionable facts onto EB**

OFP is not a producer of business traffic.
The only allowed emission is optional **audit pointers** (metadata) and only if explicitly enabled (see Section D).

### NJ-A8 — **DF must not read OFP’s store**

No backdoor “DF reads T0 tables.” DF must call OFP’s serve join (J8).

---

## B) External anti-paths (forbidden flow patterns)

### NJ-B1 — **No “scan latest” anywhere**

OFP must not compute or serve “latest features” by wall clock. Every serve is explicit **as-of**.

### NJ-B2 — **No serving without full provenance**

OFP must not return feature values without:

* `input_basis` (watermark vector)
* group versions used
* `feature_snapshot_hash`
* `graph_version` if IEG was consulted
  If any of these can’t be produced → return UNAVAILABLE, not partial truth.

### NJ-B3 — **No serving with implicit group versions**

Requests and responses must always be version-addressed.
No “default to latest group version.”

### NJ-B4 — **No silent skip of a relevant admitted fact**

If a fact could affect features and can’t be safely applied, OFP must **stall / go unhealthy / surface**—not skip and advance checkpoints.

### NJ-B5 — **No “helpful” identity resolution at the public boundary**

OFP should not become an API that accepts raw identifiers and auto-resolves them.
The serve join is canonical-key based; if DF sends non-canonical keys, that’s INVALID_REQUEST.

---

## C) Internal anti-joins (inside OFP)

### NJ-C1 — **S6 (Observability) must not affect semantic outputs**

S6 can trigger throttling/closing serving via S7, but S6 must never:

* change feature values
* change hash rules
* “relax” provenance requirements

### NJ-C2 — **S8 (pointer emitter) must not gate serving**

Pointer emission failure must never cause `get_features` failure if the snapshot itself is correct.

### NJ-C3 — **S5 (Basis/Provenance) must not read EB directly**

S5 must form `input_basis` from **T0 checkpoints**, not by “peeking” at EB consumer offsets.

### NJ-C4 — **S1 Update Plane must not invent its own feature definitions**

S1 must not interpret payloads into feature updates without the versioned definition snapshot from S4.

### NJ-C5 — **S3 Serve Plane must not compute hashes independently**

Hash/provenance rules are centralized (S5) so determinism is stable and reviewable.

---

## D) “Allowed but constrained” edges (exist only under explicit policy/profile)

### NJ-D1 — OFP → `fp.bus.audit.v1` is optional and OFF by default

If enabled, it is strictly:

* metadata pointers
* non-decisionable
* bounded/rate-limited
* never a substitute for DF→DLA provenance

### NJ-D2 — OFP → IEG is optional but audited

IEG calls are allowed only for:

* canonical key resolution, and/or
* explicitly defined graph-context needs
  …and whenever used, `graph_version` becomes mandatory provenance.

### NJ-D3 — Serving while updates are lagging is allowed, but only honestly

OFP can serve while behind, **only if** it can still provide truthful `input_basis` + explicit staleness posture.

---

## E) “Non-loops” (cycles that must not exist)

### NJ-E1 — OFP must not consume its own pointer stream as input

If `fp.bus.audit.v1` exists, it’s not a fact source for OFP.

### NJ-E2 — “Decision made” must not recursively re-trigger feature serving for the same decision

DF outputs can go to EB, but OFP must not treat DF decision events as a trigger to “refresh snapshots” in a way that creates a tight internal recursion loop.

### NJ-E3 — No internal “basis regression loop”

No mechanism should allow:

* checkpoints / `input_basis` to go backward for the same lineage
  Rebuild must be epochal (swap) or serving must be closed during rebuild.

---

## F) Environment ladder anti-shortcuts (local/dev/prod)

### NJ-F1 — Local must not bypass IG/EB semantics

Even locally:

* producers still go through IG→EB
* OFP still consumes with real offsets/consumer groups/checkpoints
  Otherwise you validate a different platform.

### NJ-F2 — Environment differences are profiles, not code forks

No “if prod do X else do Y” semantics that change:

* time meaning
* idempotency identity
* watermark meaning
* provenance completeness

---

## The practical “why this matters” summary

These non-joins are the **guard rails** that keep OFP:

* explainable (basis tokens + provenance)
* replay-safe (no hidden skips)
* non-drifting (versions/policy are singular)
* production-real (ladder works because semantics don’t fork)

---

## USER: PAUSE FOR REFLECTION

Here’s the “designer’s reflection” snapshot of what we’ve established — the **stable mental model + constitution** of OFP as a vertex in the larger platform network, plus its **now-illuminated internal network** (with opaque nodes). This is the anchor I’ll keep referencing to prevent drift as we go deeper.

---

## The OFP vertex in the platform network

### OFP’s role (what it *is*)

OFP is the **always-on projector + serve surface** that:

* **Consumes admitted facts** from the Event Bus (EB) stream (`fp.bus.traffic.v1`) under real EB semantics (partitions/offsets, at-least-once, disorder).
* Maintains **derived feature state + checkpoints** (durable but rebuildable).
* Serves **deterministic “as-of” feature snapshots** (explicit `as_of_time_utc`, never “latest”), with:

  * complete provenance, including `input_basis` (exclusive-next watermark vector),
  * `graph_version` when identity context is consulted,
  * explicit group versions used,
  * a deterministic `feature_snapshot_hash`.

### OFP’s authority boundaries (what it is *not*)

OFP is **not**:

* the trust boundary (IG owns ADMIT/QUARANTINE/DUP),
* the fact log (EB owns durability + replay spine),
* identity truth (IEG owns identity projection + `graph_version` semantics),
* the model/bundle resolver (Registry + DF),
* the decision authority (DF),
* the audit recorder (DLA).

This boundary discipline is one of the main anti-drift pillars.

---

## The production joins touching OFP (outer network)

We pinned the full external join set and treated them as “must not drift” edges:

1. **J7 — EB → OFP**
   Delivered admitted records + EB coords → OFP projection.
   Critical rail: duplicates/out-of-order assumed; update safety is **idempotency keyed by EB position × FeatureKey × FeatureGroup**; checkpoints are **exclusive-next**.

2. **J7b — OFP ↔ IEG (optional)**
   Optional canonical key resolution / identity context; if used, OFP must record **`graph_version`** as a watermark-vector token.

3. **J8 — DF → OFP** (`get_features`)
   DF requests canonical keys + explicit group versions + explicit `as_of_time_utc`; OFP replies with snapshot + provenance + deterministic hash.

4. **Cfg-OFP — Feature definition/profile pack → OFP**
   Versioned feature groups + versions + TTL/freshness + key_types. Governed activation; OFP must be able to say what revision it’s running.

5. **Obs-OFP — OFP → Observability/Governance**
   Lag/watermark age, serve latency/errors, staleness/missing rates, hash failures, active policy rev — so DL/ops can act safely.

6. **Optional audit pointer** — OFP → `fp.bus.audit.v1`
   Allowed only as **non-decisionable metadata pointers**, OFF by default in v0.

---

## The production paths and loops (outer network)

### Paths (end-to-end flows)

* **P1**: Producer → IG → EB → OFP (traffic becomes feature-state)
* **P2**: EB event → DF → OFP → DF (decision-time context fetch)
* **P3**: OFP → DF → DLA (decision provenance carries snapshot truth into audit)
* **P4**: EB/Archive + Labels → Offline Shadow → MF → Registry → DF → OFP (parity + compatibility anchor)
* **P5**: OFP health → Obs → DL → DF → OFP (capability-mask feedback loop)

### Loops (platform cycles involving OFP)

* **L1**: EB → OFP → DF → EB (facts → decisions → new facts)
* **L2**: EB → OFP → DF → AL → EB → OFP (outcomes feed future context)
* **L3**: OFP health → DL → DF → OFP (degrade/safety loop)
* **L4**: Offline learning → Registry ACTIVE → DF → OFP (version evolution loop)
* **L5**: Operability/backfill → rebuild derived → new basis tokens → DF behavior (explicit reprocessing loop)

---

## The first illuminated internal layer: OFP subnetworks (still opaque)

We decomposed OFP into minimal internal subnetworks that fully explain the outer obligations without over-modularizing:

* **S1 Update Plane** (J7)
* **S2 Identity Resolution** (J7b)
* **S3 Serve Plane** (J8)
* **S4 Feature Definition & Policy** (Cfg-OFP)
* **S5 Basis & Provenance Spine** (input_basis + hash/provenance compiler)
* **S6 Operability & Observability** (signals for DL/ops)
* **S7 Lifecycle & Rebuild Governor** (boot, readiness, pause/resume, epoch rebuild, profiles-not-forks)
* **S8 Optional Audit Pointer Emitter** (OFF by default)
* Plus a real production dependency: **T0 the OFP durable store** (state + checkpoints).

The mental model we ended up with is very stable:

> **Two planes (Update + Serve), bound by a durable store, with a provenance spine, governed by lifecycle/ops, and optionally aided by identity resolution and pointer emission.**

---

## Internal joins (IJ-01 → IJ-18) and what they mean

We mapped the internal network as explicit join handshakes (still black-box inside nodes). Highlights:

* **IJ-01/02/03**: intake → commit (state+checkpoint) → as-of reads
* **IJ-04/05**: Update/Serve → Identity (optional)
* **IJ-06/07**: Policy/defs → Update/Serve
* **IJ-08/09/10**: T0 → S5 basis; S3 ↔ S5 provenance+hash; S2 → S5 graph_version
* **IJ-11/12/13**: Update/Serve/Policy → Observability
* **IJ-14/15/16**: Lifecycle governs Update/Serve, policy activation, and derived-store epoch rebuild
* **IJ-17/18**: optional pointer feed + pointer health

We also pinned the “governor rule”:

* Lifecycle can alter **operational posture** (pause/throttle/rebuild/close serving), but **never semantic meaning** (no hidden now, no changing watermark meaning, no skipping relevant events, no altering version identity).

---

## Internal paths (IP-1 → IP-8)

We made the internal “flow catalog” that stitches IJ’s together:

* **IP-1** normal apply
* **IP-2** duplicate/redelivery no-op
* **IP-3** serve without IEG
* **IP-4** serve with IEG consulted (records graph_version)
* **IP-5** policy activation/reload (governed, coherent cutover, observable)
* **IP-6** stall/fail-closed (checkpoint truth preserved, operably loud)
* **IP-7** explicit rebuild/rehydration (epochal, no basis regression, auditable)
* **IP-8** optional pointer emission (decoupled from serving)

We pinned a key coherence requirement for serving:

* **Serve must be computed against a single coherent read-view of T0** so the feature values and `input_basis` match (no “read now, basis later from a different moment”).

---

## Internal loops (IL-1 → IL-5)

These are the cycles inside OFP that keep it production-real:

* **IL-1 Identity cache loop** (scoped by ContextPins; graph_version still tracked when identity depends on IEG)
* **IL-2 Health/backpressure loop** (signals → governor controls → behavior shifts)
* **IL-3 Policy reload stabilization** (validate/activate/rollback with explicit facts)
* **IL-4 Rebuild convergence** (epochal replay → catch-up → atomic swap / explicit readiness)
* **IL-5 Optional pointer emitter loop** (bounded + disable-able, never an outage vector)

---

## The explicit non-joins (forbidden edges)

We pinned a full “anti-edge” set to prevent convenience drift, including:

* No Producer→OFP, no OFP bypassing EB, no OFP acting as IG, no DF reading OFP’s store directly.
* No OFP↔Registry resolution, no OFP↔Label Store, no OFP deciding degrade posture.
* No decisionable outputs from OFP onto EB (optional audit pointers are metadata only).
* No “scan latest”; no serving without provenance; no silent skip of relevant facts; no “helpful raw identifier API.”

These “non-joins” are as important as the joins — they’re the guardrails.

---

## Environment ladder alignment

We also aligned everything to your ladder doctrine:

* **Semantics identical across local/dev/prod** (same rails, same join meanings, same provenance and watermark meaning).
* Differences are **profiles** (wiring + policy revs + thresholds), not forks.
* Local can collapse topology, but must keep real EB semantics so basis tokens remain meaningful.

---

## The drift sentinels I’m carrying forward

If anything we design inside the boxes would violate these, it’s out-of-bounds:

1. **Watermarks don’t lie** (exclusive-next; no advance without durable apply; no silent skip of relevant facts).
2. **No hidden “now”** (as-of is explicit; freshness is event-time based).
3. **Versioned meaning is singular** (group versions + policy revs are explicit; coherent cutovers).
4. **Provenance completeness** (no hash without input_basis; graph_version recorded when IEG is used).
5. **Trust boundaries stay put** (IG admits, EB replays, OFP projects/serves, DF decides, DLA records).

---

Yep — this is exactly the right moment to **pin the deployment posture** for the *inner network* (S1–S8 + T0) so Codex doesn’t accidentally “implement a different OFP” when we start opening boxes.

Everything below is designer-authoritative and must stay consistent with the environment ladder + deployment-unit pins you already laid down.  

---

## 1) Deployment-unit shape for OFP (pin this now)

**PD-DEP-OFP-01 (authoritative): OFP is one deployment unit in v0 production shape — an always-on EB consumer + serve API sharing one durable store (T0).**
This matches the pinned deployment notes: OFP is “projector + serve API,” and *may be one process that both consumes and serves* (still one unit). 

**PD-DEP-OFP-02 (authoritative): Horizontal scale is “replicas of the same unit.”**
Each replica runs **both**:

* S1 Update Plane (consumer group partitions across replicas)
* S3 Serve Plane (load-balanced API)

They all share:

* T0 (ofp DB)
* the active S4 policy snapshot (same policy_rev)

This keeps topology minimal and avoids an early split into “projector deployment vs serve deployment” unless/until you need it.

**PD-DEP-OFP-03 (escape hatch, later): If you ever split, it must remain *one logical component* with the same semantics.**
Allowed future split: `ofp-projector` and `ofp-serve` deployments, both reading the same S4 policy snapshot and the same T0. But v0 default is **not split**.

---

## 2) Environment ladder posture (what must be identical vs what may vary)

**Must be identical across local/dev/prod (no drift):**

* Canonical meaning: event-time semantics, as-of serving, idempotency identities, watermark meaning (exclusive-next), provenance completeness, group version discipline, and policy-rev activation semantics. 
* Trust boundaries and graph roles (OFP never bypasses IG/EB; OFP is derived). 

**Allowed to vary by environment profile (operational envelope only):**

* scale (partitions, concurrency, QPS limits)
* retention + archive availability
* auth strictness
* HA/backup posture
* observability depth and alert thresholds
  …but these are **profiles**, not code forks. 

---

## 3) The two-profile model OFP must support

Pin the separation (Codex must not blur these):

### A) Wiring profile (non-semantic)

Endpoints, ports, credentials injection, resource limits, timeouts:

* EB bootstrap/credentials, `consumer_group_id`, poll sizes
* T0 DSN (ofp DB)
* IEG endpoint + timeouts (if enabled)
* API listen addr, rate limits, request limits
* OTel collector endpoint

### B) Policy profile (outcome-affecting; versioned artifact)

These MUST have revision identity and be observable:

* `feature_def_policy_rev` (active feature definition/profile revision)
* `dl_threshold_profile_rev` (corridors/thresholds used by DL; OFP just emits signals)
* (optionally) enablement of pointer emission and its bounded policy
  This matches the “policy config is versioned + auditable; wiring config is not semantic” pin. 

---

## 4) Stateful substrate posture for the inner network (T0)

**PD-DEP-OFP-04 (authoritative): T0 is a rebuildable derived store, but must be durable in prod.**

* Writer: OFP projector (S1)
* Source of truth: EB/Archive (facts)
* Proof tokens: `input_basis` + `feature_snapshot_hash`
  This exactly matches the derived/rebuildable map. 

**Backups/restore expectation (v0):**

* You don’t “restore T0 as truth.” You restore it for speed, and you must be able to replay/rebuild from EB/Archive as the correctness anchor. 

**Rebuild posture (important for later implementation):**

* Rebuilds/backfills are **explicit, auditable, and epochal** (swap, don’t regress basis). 

---

## 5) Runtime readiness & rollout posture (so deployments behave predictably)

**PD-DEP-OFP-05 (authoritative): OFP must have explicit readiness gates:**

* **UPDATE_READY** requires: S4 active policy snapshot + T0 ready + consumer group running.
* **SERVE_READY** requires: S4 active policy snapshot + T0 read-view coherence + S5 able to produce complete provenance (`input_basis`, versions, hash).
  If provenance cannot be produced → serving must be closed (UNAVAILABLE), not “partial truth.” 

**Rollouts:**

* Rolling upgrade is allowed if idempotency identity + hash/provenance rules are unchanged.
* Any change to hashing/canonicalization or feature definition meaning must be treated like a governed policy/definition change (observable rev), not a silent code upgrade.

---

## 6) Observability baseline that must exist even locally

OFP must always emit:

* consumer lag + watermark age (per partition)
* serve latency/errors
* staleness/missing rates
* hash/provenance failure rates
* active `feature_def_policy_rev`
  Because DL and ops safety loops depend on those signals. 

Local can be “easier to inspect,” but it must still run the same semantics (no fake offsets, no fake basis). 

---

## 7) Security posture pins (minimal but real)

* Secrets are injected at runtime; **never** embedded in provenance, receipts, manifests, or logs. 
* Auth can be permissive locally, but the mechanism must exist in every env (serve endpoint, IEG calls, DB creds, policy artifact access).

---

## 8) Optional pointer emitter (S8) deployment posture

**PD-DEP-OFP-06 (authoritative): S8 is OFF by default in v0.**
You already have DF→DLA provenance for audit; pointers are optional indexing hints only. 

If enabled later:

* run it in-process (still one deployment unit) but **bounded** (rate limits/sampling)
* never allow it to gate serving correctness

---

### What Codex should *not* do (deployment-wise)

* No “dev mode” code paths that change semantics (profiles only). 
* No local shortcuts that bypass IG/EB realities (offsets/watermarks must be real). 
* No serving if provenance is incomplete (input_basis missing/incoherent). 

---

Yep — that assumption is the **right posture**: the outer network is frozen, and illuminating nodes should **reveal machinery**, not change boundaries. If we ever discover an internal need that would “pull” on another node, we’ll treat it as a drift signal and either (a) satisfy it internally, or (b) make an explicit pinned decision rather than silently changing the network.

## Nodes (subnetworks) we have inside OFP

* **T0** — OFP Durable Store (`ofp` state + checkpoints)
* **S1** — Update Plane (J7 consumption → apply → checkpoints)
* **S2** — Identity Resolution (optional IEG usage + caching + `graph_version`)
* **S3** — Serve Plane (`get_features` + as-of reads)
* **S4** — Feature Definition & Policy (feature groups/versions/TTL; policy_rev activation)
* **S5** — Basis & Provenance Spine (`input_basis`, provenance assembly, snapshot hashing)
* **S6** — Operability & Observability (lag/stall/latency/staleness signals)
* **S7** — Lifecycle & Rebuild Governor (boot/readiness, pause/throttle, epoch rebuild/swap)
* **S8** — Optional Audit Pointer Emitter (OFF by default)

## Order I want us to illuminate (min-drift, dependency-correct)

1. **S4 Feature Definition & Policy**
   Pins “what features mean” (groups, versions, TTL rules). Everything else references this.

2. **T0 Durable Store contract**
   Pins what must be persisted and what “coherent read view” means (for as-of + `input_basis`).

3. **S1 Update Plane**
   The hardest correctness surface: idempotent apply, disorder safety, stall semantics, checkpoint truth.

4. **S5 Basis & Provenance**
   Locks `input_basis` extraction, provenance blocks, deterministic hashing rules (anti-drift spine).

5. **S3 Serve Plane**
   Builds on T0+S5: request validation, as-of reads, freshness, response assembly.

6. **S2 Identity Resolution**
   Then we tighten when/why we consult IEG, caching scope, and `graph_version` propagation.

7. **S7 Lifecycle & Rebuild**
   Now we can define the state machine using the realities of S1/S3/T0 (boot, stall handling, epoch rebuild/swap).

8. **S6 Operability & Observability**
   Integration pass: ensure every critical boundary decision has a signal and the ladder loop (DL/ops) has what it needs.

9. **S8 Optional Pointer Emitter** *(only if you plan to enable it; otherwise we skip)*
   It’s deliberately last because it must remain non-decisionable and never gate correctness.

If you’re happy, we start with **S4** (feature definition/policy subnetwork) and keep all other nodes opaque while we open it.

---

Alright — we’re opening **S4: Feature Definition & Policy** and exposing the machinery inside it, while keeping every other OFP node opaque.

Think of S4 as the **“meaning authority”** inside OFP: it’s the only place allowed to say *what features are*, *which versions exist*, *how they’re keyed*, and *how freshness is judged*. Everything else (S1 updates, S3 serving, S5 hashing/provenance) is downstream of whatever S4 declares.

---

# S4’s mission and authority

## What S4 is responsible for

1. **Load** the active Feature Definition Profile Pack (by **policy revision**, not “latest”).
2. **Validate** it (integrity + semantic rules).
3. **Activate** it as a coherent, immutable **ActiveFeatureDefSnapshot**.
4. **Serve** that snapshot to consumers:

   * **S1 Update Plane** (IJ-06): event→group applicability, key_type rules, update interpretation hooks.
   * **S3 Serve Plane** (IJ-07): group inventory, TTL/freshness rules, stable feature ordering/IDs.
   * **S5 Basis/Provenance** (indirectly): stable ordering + policy revision identity for provenance.
5. **Emit “change is a fact”** signals (IJ-13) whenever activation/rejection happens.

## What S4 is NOT allowed to do (hard boundary)

* It must not “invent” features from payloads or runtime observations.
* It must not auto-select “latest version” implicitly.
* It must not mutate the meaning of an existing `(group_name, group_version)` after activation.
* It must not silently hot-change semantics; activation must be explicit and observable.

---

# S4 internal subnetworks (inside S4)

I’m going to define S4 as a small internal network of opaque *submodules* (one level deeper), because that’s what prevents “config blob spaghetti”:

## S4 internal nodes

### S4.1 PolicySource Adapter

**Role:** fetch the policy artifact by **explicit reference** (policy_rev + artifact_ref + expected_digest).

* Local/dev/prod can differ in where it fetches from (file path vs object store), but not in what it fetches (no “latest”).

### S4.2 Integrity & Authenticity Guard

**Role:** verify the artifact is what it claims:

* digest match (and optionally signature later)
* schema version compatibility
* “no forbidden fields” / “no unknown top-level structure” posture

### S4.3 Schema Validator

**Role:** structural validation:

* required fields present (groups list, versions, key_types, TTL policies, etc.)
* types correct (ints, durations, enums)
* uniqueness constraints at the schema level (e.g., no duplicate group keys)

### S4.4 Semantic Validator

**Role:** *meaning* validation:

* version immutability constraints
* update applicability is coherent
* feature IDs are stable, unique, and canonicalizable
* TTL/freshness policies are well-defined and non-contradictory
* event_type mappings don’t create impossible expectations (“group depends on event_type that cannot exist in this run/world”)

### S4.5 Snapshot Builder

**Role:** build a canonical **ActiveFeatureDefSnapshot**:

* canonical sort order
* computed fingerprints:

  * `snapshot_digest`
  * `group_inventory_fingerprint` (stable hash of `(group_name, group_version)` list)
* derived indices for consumers:

  * `group_lookup[(name,version)] -> GroupDef`
  * `event_type_index[event_type] -> applicable GroupRefs`
  * `key_type_index[key_type] -> GroupRefs`
  * stable `feature_ordering` per group (for deterministic hashing and response layout)

### S4.6 Activation Controller

**Role:** own the state machine:

* last-known-good snapshot
* staged snapshot
* active snapshot
* rejection reasons
* activation epoch token (optional but useful)

### S4.7 Consumer Registry API

**Role:** read-only interface that S1/S3 use (IJ-06/IJ-07):

* “give me active snapshot identity”
* “give me group def for (name,version)”
* “what groups are affected by this event_type”
* “what TTL rules apply to this group”
* “what is the stable feature ordering for this group”

### S4.8 Change Journal Emitter

**Role:** produce observable facts (IJ-13):

* activation / rejection events
* active policy revision in telemetry
* group inventory fingerprint

---

# The key artifact S4 produces: ActiveFeatureDefSnapshot

This is the one object that *everything* downstream must treat as authoritative.

## Snapshot identity fields

* `policy_id`
* `policy_rev`
* `snapshot_digest`
* `group_inventory_fingerprint`
* (optional) `definitions_epoch` (monotonic token for “which defs snapshot was active”)

## Snapshot content (minimum)

For each **FeatureGroupRef = (group_name, group_version)**:

* `key_type` (what canonical keys it attaches to)
* `ttl_policy` / freshness rules (event-time based)
* `feature_ids[]` (stable identifiers)
* `feature_ordering[]` (stable, deterministic order—usually same as feature_ids but explicitly pinned)
* `event_type_applicability[]` (which event types can update this group)
* `update_hook_ref` (opaque pointer: “which update interpretation/transform family applies” — could be a code module ID, or a config recipe ID)

**Design authority pin:** `group_version` is part of meaning. If any of these change, you bump the version. Never mutate in-place.

---

# S4 lifecycle: how activation works without drift

This is the “machinery” that keeps meaning stable across environments and rollouts.

## State machine (conceptual)

* **UNINITIALIZED**
* **STAGED(policy_rev X)** (fetched + validated)
* **ACTIVE(policy_rev X)** (current meaning)
* **REJECTED(policy_rev X)** (failed validation; reason recorded)

## Activation path (IP-5, but focused inside S4)

1. S7 requests: `LOAD(policy_id, policy_rev, ref, expected_digest)`
2. S4.1 fetches → S4.2 verifies integrity → S4.3 schema validates → S4.4 semantic validates
3. S4.5 builds the canonical snapshot + fingerprints
4. S4.6 activates atomically:

   * `active_snapshot := staged_snapshot`
   * `active_policy_rev := policy_rev`
5. S4.8 emits “policy_rev active” fact (IJ-13)

## Coherence rule (prevents “mixed semantics”)

**Pinned rule:** one delivered record (S1) and one serve request (S3) must each observe a single coherent snapshot.
Mechanism is flexible (barrier, RW-lock, epoch token), but the rule is non-negotiable.

## Rollback rule

If activation fails:

* remain on last-known-good snapshot (if any)
* emit a rejection fact (with reason)
* never partially activate

If no last-known-good exists (first boot):

* OFP cannot be SERVE_READY / UPDATE_READY (it would be inventing semantics).

---

# What S4 must answer for its consumers (IJ-06 / IJ-07)

## For S1 Update Plane (IJ-06)

S1 must be able to ask S4:

* “Given `event_type`, what FeatureGroups are eligible to update?”
* “For each eligible group, what `key_type` is required?”
* “What update_hook_ref applies for (group_name, group_version)?”
* “Is this group currently active/allowed under this policy_rev?”

This ensures S1 never “guesses” what a payload means.

## For S3 Serve Plane (IJ-07)

S3 must be able to ask S4:

* “Is requested (group_name, group_version) valid under active policy?”
* “What is the TTL/freshness rule for this group?”
* “What is the stable feature ordering (for deterministic output + hashing)?”
* “What feature IDs exist for this group/version?”

This ensures serving cannot silently drift into “latest” or “whatever is configured.”

---

# Warm-up / backfill metadata (the one subtle production issue to pin)

When a **new group_version** is activated, the state for that group/version may be empty until enough history has flowed through S1 (or a rebuild/backfill seeds it).

So S4 should include (per group/version) a minimal, explicit “warm-up” hint:

* `warmup_mode` ∈ {`forward_only`, `requires_replay`}
* `warmup_horizon` (e.g., “needs 30d of history” or “since run start”)

This doesn’t force implementation details, but it prevents silent surprises:

* DF can avoid using a brand-new group_version until it’s warm (or degrade mask can disallow it).
* Ops can decide whether to run IP-7 rebuild to populate it.

**Pinned boundary:** S4 only declares this metadata; S7 orchestrates rebuild; S3 reports missing/stale honestly.

---

# S4 observability outputs (IJ-13 focus)

S4 must produce structured “change facts” and expose active identity:

* `active_policy_rev` (always available)
* activation/rejection events:

  * `{policy_rev, result, reason_code, actor, snapshot_digest, group_inventory_fingerprint}`
* optional gauges:

  * “time since last activation”
  * “number of groups active”
  * “number of rejected activations”

This is what keeps the environment ladder honest: you can always answer “what meaning was in force?”

---

# Out-of-bounds behaviors (explicitly banned inside S4)

* **Implicit latest:** “If no version requested, serve latest.” (No.)
* **Mutable version:** changing meaning of an existing `(group_name, group_version)` without bumping version.
* **Silent hot-change:** switching policy_rev without emitting an observable activation fact.
* **Environment fork:** prod loads from object store, local loads from file, but they don’t agree on identity/digest/rev semantics.
* **Consumer-specific views:** S1 and S3 seeing different active snapshots at the same time (mixed semantics).

---

## What we do next

If you’re good with this S4 machinery, the clean next node to illuminate is **T0 (the OFP durable store contract)**, because S4 defines meaning, and T0 defines what *must* be persisted to make “as-of + basis tokens + determinism” actually possible.

---

Alright — opening **T0: the OFP Durable Store contract** and exposing the machinery inside it.

T0 is the **single internal substrate** that makes *all the rails real*:

* **Replay truth** (`input_basis` = exclusive-next offset vector)
* **As-of truth** (no future leakage by event-time)
* **Idempotency truth** (replays/duplicates don’t double-apply)
* **Epoch truth** (explicit rebuild without basis regression)

Everything else (S1/S3/S5/S7) leans on what T0 can guarantee.

---

# 1) What T0 is (and is not)

## T0 is

A **derived, durable, rebuildable** store that holds:

* **Feature state** keyed by ContextPins + canonical entity key + group version
* **Applied checkpoints** per EB partition (exclusive-next)
* Minimal metadata needed to make reads coherent and provenance truthful

## T0 is not

* Not a source-of-truth for facts (EB/Archive are)
* Not a “compute engine” for features (S1 applies transforms; T0 persists their results + time-indexing)
* Not an “offset mirror” of Kafka consumer group offsets (basis comes from **applied** checkpoints, not “committed offsets”)

---

# 2) The internal subnetworks inside T0 (one level deeper)

Think of T0 as a small internal network of modules:

### T0.1 Epoch Manager

**Role:** supports IJ-16/IP-7 rebuild semantics safely.

* Active epoch vs staging epoch
* Atomic epoch swap
* Epoch integrity status

### T0.2 Checkpoint Ledger

**Role:** the **truth source** for `input_basis`.

* Maintains `next_offset_to_apply` per `(stream_name, partition_id, epoch_id)`
* Guarantees **exclusive-next** semantics and monotonicity

### T0.3 Apply Transaction Engine

**Role:** implements IJ-02 correctly.

* Accepts an ApplyUnit from S1
* Writes feature state mutations
* Advances checkpoint to `offset+1`
* Ensures the **checkpoint only advances iff state effects are durable**

### T0.4 Idempotency / Apply Receipt Index

**Role:** prevents double-apply under replays and partial failures.

* May be implemented as:

  * offset-level apply receipt (partition, offset) **plus**
  * optional per-update receipt (partition, offset, key, group) if ApplyUnit isn’t strictly atomic
* Semantics must behave *as if* the update-id recipe exists

### T0.5 Feature State Families

**Role:** stores derived state in a form that supports **as-of** reads.

* Keyed by `(epoch_id, context_pins, key_type, key_id, group_name, group_version)`
* Stores feature values + event-time lineage (at least last-update event_time, often more)

### T0.6 As-Of Read Engine

**Role:** implements IJ-03.

* Given `(context_pins, keys, groups, as_of_time_utc)` returns:

  * feature values as-of the requested event-time boundary
  * per key×group “last contributing event_time” (or NO_DATA)

### T0.7 Read-View / Coherence Broker

**Role:** enforces PD-IP-COH-01.

* Issues a **read_view_token** that binds:

  * the feature state view used by S3
  * the checkpoint vector used by S5 (`input_basis`)
* Ensures “values and basis came from the same committed horizon”

### T0.8 Retention & Compaction Manager

**Role:** manages storage size without breaking semantics.

* Event-time bucket retention policies
* Produces explicit “earliest_as_of_supported” boundaries

### T0.9 Integrity & Diagnostics

**Role:** detects when invariants are threatened.

* checkpoint gaps, epoch mismatches, corruption signals
* exposes “store health” signals for S7/S6

---

# 3) The core stored truths (what T0 must persist)

## A) Checkpoints (basis truth)

For each epoch and partition:

* `checkpoint[(epoch_id, stream_name, partition_id)] = next_offset_to_apply`

**Pinned meaning:** *exclusive-next*. If checkpoint says `100`, then offsets `<100` are applied (or explicit no-op) and `100` is the next unapplied. No other interpretation is allowed.

## B) Feature state (serving truth)

For each epoch and feature address:

* `state[(epoch_id, context_pins, key_type, key_id, group_name, group_version)] = {feature_values..., lineage...}`

**Lineage minimum:**

* `last_update_event_time_utc` (event-time, not ingest/apply time)
* optionally: a compact structure to support “as-of” beyond just “latest” (implementation freedom)

## C) Optional apply receipts (idempotency truth)

At minimum:

* `applied_offset[(epoch_id, stream_name, partition_id, offset)] = applied|noop`

Optionally (if ApplyUnit isn’t strictly atomic internally):

* `applied_update[(epoch_id, stream, partition, offset, key_type, key_id, group, version)] = applied`

Either way, behavior must satisfy the conceptual idempotency identity.

---

# 4) The T0 surfaces (the “contracts” other nodes rely on)

I’m defining these as **conceptual APIs** (not language-level specs).

## T0.Apply(ApplyUnit) → ApplyReceipt  (IJ-02)

**Inputs (minimum):**

* `epoch_id`
* `context_pins`
* `(stream_name, partition_id, offset)`
* `expected_checkpoint = offset` (next_offset_to_apply must equal this)
* `mutations[]` (already computed by S1; T0 stores them)
* `checkpoint_advance_to = offset+1`

**Outputs:**

* `result = APPLIED | DUPLICATE | REJECTED`
* `new_checkpoint` (if advanced)
* `receipt_id` / digest (optional, but useful for diagnostics)

## T0.ReadAsOf(ReadRequest) → ReadResult  (IJ-03)

**Inputs:**

* `epoch_id`
* `context_pins`
* `feature_keys[]`
* `group_refs[]` (name+version)
* `as_of_time_utc`

**Outputs:**

* feature values (possibly sparse)
* per key×group: `last_update_event_time_utc` or `NO_DATA`
* (optional) a “consistency watermark” internal token to help S5

## T0.BeginReadView() → read_view_token  (IJ-03/IJ-08 coherence)

**Purpose:** binds reads and basis.

* S3 uses this token for all reads for one request
* S5 uses it to fetch `input_basis`

## T0.GetBasis(read_view_token) → BasisSnapshot  (IJ-08)

**Output:**

* `stream_name`
* `watermarks{partition_id -> next_offset_to_apply}` (exclusive-next)
* `epoch_id`
* (optional) `partition_set_hash`

## T0.EpochOps (IJ-16 / IP-7)

* `PrepareEpoch(new_epoch_id)`
* `ResetEpoch(epoch_id)` (derived only)
* `SwapActiveEpoch(epoch_id)` (atomic)
* `GetEpochStatus(epoch_id)` (ready / integrity_ok / checkpoint summary)
* `GetRetentionBoundary(epoch_id)` → earliest_as_of_supported

---

# 5) The non-negotiable invariants inside T0

These are the “laws” T0 must uphold; if any can’t be met, OFP must fail closed.

## I1 — Exclusive-next checkpoint truth

Checkpoint values are always “next offset to apply”, never “last applied”.

## I2 — No gaps in checkpoint advance

T0 must reject an ApplyUnit if:

* `offset != next_offset_to_apply`
  This prevents accidental skipping and makes basis tokens truthful.

## I3 — Atomicity: state + checkpoint advance

For a relevant offset:

* either all state effects for that offset are durable (or explicit no-op),
* **and then** checkpoint becomes `offset+1`,
* or nothing advances.

This is the “watermarks don’t lie” core.

## I4 — Idempotency under duplicates/replays

If T0 receives an ApplyUnit for an offset that is already applied:

* it must return DUPLICATE (or equivalent)
* and must not produce additional state effects

## I5 — As-of correctness (event-time)

ReadAsOf must behave as:

* values derived only from contributions with `event_time <= as_of_time_utc`
* regardless of arrival/apply order

## I6 — Coherent read view (values ↔ basis)

For a single get_features request:

* the feature values S3 reads and the basis vector S5 emits must be from a coherent committed horizon (read_view_token).

## I7 — Version isolation

Group version is part of the storage address.
No blending across `(group_name, group_version)`.

## I8 — Epoch isolation and non-regression

* Writes go to the active epoch.
* Rebuild happens in a staging epoch and swaps atomically.
* Serving must not produce an `input_basis` that regresses for the same lineage.

## I9 — Retention boundaries are explicit

If compaction/retention makes “as-of earlier than X” impossible, T0 must expose that boundary so serving can fail explicitly (not approximate silently).

---

# 6) Concurrency & multi-replica reality (what T0 must tolerate)

Even with multiple OFP replicas:

* Each EB partition should have **one logical writer at a time**, but rebalances happen.

So T0 must enforce correctness via:

* **conditional checkpoint advance** (“apply only if expected_checkpoint matches”) to prevent two writers from racing
* deterministic handling of duplicates

This is how we keep correctness independent of deployment topology.

---

# 7) Failure modes (how T0 expresses “cannot be correct”)

T0 should have explicit failure classes (conceptual):

* **CHECKPOINT_CONFLICT**: expected_checkpoint mismatch (rebalance / double writer / out-of-order apply)
* **GAP_DETECTED**: offset > next_offset_to_apply (would imply skipping)
* **INTEGRITY_FAIL**: corruption / invariant violation
* **RETENTION_BOUNDARY_EXCEEDED**: as_of_time earlier than earliest supported
* **UNAVAILABLE**: store down / cannot provide coherent read_view or basis vector

Downstream mapping is pinned:

* Apply path: conflicts/gaps → pause/stall and surface ops signals (do not advance)
* Serve path: inability to produce coherent basis/provenance → UNAVAILABLE (fail closed)

---

# 8) T0 “non-joins” (things T0 must never do)

* T0 must not peek at EB consumer offsets to manufacture basis.
* T0 must not use wall-clock time as “freshness” input.
* T0 must not accept raw identifiers as key_id (canonical keys only).
* T0 must not auto-select group versions.

---

## Where we go next

With S4 and T0 now illuminated, the next node to open should be **S1 Update Plane**, because S1 is the part that *chooses what to write into T0* and is the main source of stalls, idempotency pressure, and as-of correctness burden.

When we open S1, we’ll treat T0 as a fixed contract: **S1 must live within these invariants, not renegotiate them.**

---

Alright — we’re opening **S1: Update Plane** and exposing the machinery inside it, while keeping **S2/S3/S4/S5/S6/S7/T0** as “known black boxes with fixed contracts.”

S1 is the **hardest correctness surface** because it is where **facts become durable derived state + truthful progress tokens**.

---

## S1’s non-negotiable external obligations

S1 must satisfy (without renegotiation):

* **IJ-01**: accept EB DeliveredRecord `(stream, partition, offset) + canonical envelope`
* **IJ-06**: use **one coherent S4 ActiveFeatureDefSnapshot** to decide relevance + interpretation
* **IJ-04**: optionally resolve identity via S2 (never guess)
* **IJ-02**: commit **state effects + checkpoint advance** atomically into T0 (exclusive-next)
* **IJ-11**: emit lag/stall/apply signals to S6
* **IJ-14**: obey lifecycle controls from S7 (pause/resume/throttle/drain)

Pinned behaviors:

* **Unknown/irrelevant event_type ⇒ NO-OP + checkpoint advances**
* **Relevant but uninterpretable ⇒ STALL (no checkpoint advance)**
* **Checkpoint meaning ⇒ exclusive-next (“next offset to apply”)**
* **Meaning time ⇒ `ts_utc` (event-time), never ingest/apply time**

---

## Pinned internal design decisions for S1 (authoritative)

**PD-S1-01 — Per-partition sequentiality:**
Within a given `(stream, partition)`, S1 processes offsets **in order**, with at most **one “offset apply” in flight** at a time. Cross-partition parallelism is allowed.
Reason: checkpoint truth and no-gap discipline.

**PD-S1-02 — One DeliveredRecord → one ApplyUnit:**
Each offset produces exactly one of:

* `NOOP_APPLY` (checkpoint only)
* `EFFECT_APPLY` (mutations + checkpoint)
* `STALL` (no checkpoint)
  No other outcomes.

**PD-S1-03 — Deterministic planning & ordering:**
All derived lists (affected groups, keys, update tasks) must be **stable-sorted** so retries/replays produce identical ApplyUnits.

**PD-S1-04 — Zero “best effort” interpretation for relevant facts:**
If a relevant fact can’t be safely interpreted, S1 stalls and becomes operably loud. No silent skip.

---

## S1 internal subnetworks (inside S1)

Think of S1 as a small internal network of opaque submodules:

### S1.1 Partition Runner

**Role:** Owns per-partition sequencing, offset discipline, and in-flight control.

* Maintains `PartitionState` (RUNNING / PAUSED / STALLED / DRAINING)
* Ensures no gaps and one-in-flight apply per partition

### S1.2 Intake & Envelope Gate

**Role:** Minimal validation + canonical extraction.

* Extracts required envelope fields
* Extracts ContextPins (if present)
* Parses `event_time = ts_utc`
* Classifies “well-formed enough to proceed” vs “fatal-to-interpret”

### S1.3 Relevance Router

**Role:** Uses S4 snapshot to answer: “does this event_type affect any active groups?”

* If none ⇒ route to NOOP_APPLY
* If some ⇒ route to keying/planning

### S1.4 Subject Extractor

**Role:** From the event (envelope + payload), extract “subjects”:

* canonical entity refs if present, else
* observed identifiers bundle (payload-driven in v0)

This is where we avoid drift: subject extraction must be **event_type-aware** and anchored in S4 definitions (no ad-hoc parsing sprawl).

### S1.5 Identity Orchestrator

**Role:** Decide if identity resolution is required, and call S2 when needed.

* Inputs: ContextPins + subject bundle + required key_types
* Outputs: canonical FeatureKeys (+ graph token if S2 used IEG)

### S1.6 Update Task Builder

**Role:** Convert “(event, keys, affected groups)” into **update tasks**:

* `(FeatureKey, FeatureGroupRef, event_time, event payload view, context_pins)`
* Produces a stable ordered list of tasks

### S1.7 Transform & Mutation Engine

**Role:** Execute group-specific update hooks (from S4 snapshot) to produce **mutations**.

* Must be deterministic
* Must be order-independent with respect to arrival order (event-time safe)
* Must emit lineage needed for as-of reads (at least last_update_event_time per key×group)

### S1.8 Apply Coordinator

**Role:** Build ApplyUnit and commit it to T0:

* Calls `T0.Apply(epoch_id, expected_checkpoint=offset, mutations, advance_to=offset+1)`
* Interprets results: APPLIED / DUPLICATE / CHECKPOINT_CONFLICT / UNAVAILABLE

### S1.9 Stall & Recovery Controller

**Role:** Standardize stall decisions + reason codes and coordinate with S7.

* On STALL: stop advancing checkpoint, emit structured stall event, optionally pause partition consumption
* Requires explicit ops/rebuild to recover if not self-resolving

### S1.10 Telemetry Emitter

**Role:** Emits:

* lag/watermark age summaries
* apply throughput/latency/error classes
* stall boundary facts with `(stream, partition, offset, reason_code)`
  to S6 (IJ-11)

---

## The internal joins inside S1 (S1-only edges)

1. **S1.1 → S1.2**: “next offset record” is admitted for minimal validation
2. **S1.2 → S1.3**: “validated record” goes to relevance router
3. **S1.3 → S1.8**: irrelevant → NOOP_APPLY (checkpoint-only)
4. **S1.3 → S1.4**: relevant → subject extraction
5. **S1.4 → S1.5**: subject bundle → identity orchestration (optional)
6. **S1.5 → S1.6**: canonical keys + affected groups → build tasks
7. **S1.6 → S1.7**: tasks → compute mutations
8. **S1.7 → S1.8**: mutations → apply coordinator (T0.Apply)
9. **Any → S1.9**: errors classified into STALL vs NOOP vs RETRY
10. **Any → S1.10**: telemetry emitted continuously

---

## S1 production paths (inside S1, end-to-end)

### Path S1-P1: Normal apply (relevant event, keys resolvable)

1. Intake/validate (required envelope fields, event_time)
2. Relevance lookup via S4 snapshot
3. Extract subjects → resolve canonical keys (if needed via S2)
4. Build stable update tasks (key×group)
5. Execute update hooks → produce mutations + lineage
6. Commit mutations + advance checkpoint atomically to `offset+1`
7. Emit success + lag signals

### Path S1-P2: Irrelevant / unknown event_type (NOOP_APPLY)

1. Intake/validate enough to safely NOOP
2. Relevance router finds no affected groups
3. Commit checkpoint-only ApplyUnit (no state mutation)
4. Emit “noop processed” counters

### Path S1-P3: Duplicate/redelivery

1. Same steps as normal apply until T0.Apply
2. T0 returns DUPLICATE (already applied)
3. S1 treats as success and ensures checkpoint is correct (advance if needed)
4. Emit duplicate counters (low cardinality)

### Path S1-P4: Stall path (relevant but cannot apply safely)

Triggers include:

* missing required fields needed for interpretation
* identity resolution required but unavailable
* S4 mapping says relevant, but update hook cannot interpret payload version
* T0 indicates a gap/invalid checkpoint condition that implies skipping

Outcome:

* **no checkpoint advance**
* emit stall boundary fact
* partition enters STALLED/PAUSED posture via S7 controls

---

## S1’s error taxonomy and what it means (authoritative)

S1 must classify every failure into one of these outcomes:

### 1) NOOP_SAFE

Event irrelevant to active groups (or safe to ignore)
→ checkpoint advances

### 2) STALL_CORRECTNESS

Event relevant but cannot be applied without inventing meaning
→ checkpoint does **not** advance
→ emit stall reason + become operably loud

### 3) RETRY_TRANSIENT

Transient failures (T0 unavailable, temporary checkpoint conflict due to rebalance)
→ do not advance checkpoint
→ retry under S7 control (or pause/drain)

### 4) DUPLICATE

Already applied offset/update
→ treat as success
→ checkpoint advances appropriately

---

## Critical drift traps inside S1 (explicitly banned)

* **Skipping a relevant fact and still advancing checkpoint**
* **Using wall-clock/apply time as the “meaning time”**
* **Ad-hoc payload parsing that bypasses S4’s declared applicability/interpretation**
* **Accepting raw identifiers as `FeatureKey`**
* **Processing offsets out of order within a partition**
* **Letting “definitions change mid-record” (mixed snapshot)**

---

## How S1 stays correct under deployment realities

### Rebalances / multi-replica writers

S1 relies on T0’s conditional apply (`expected_checkpoint == offset`) to prevent two writers from advancing incorrectly. If checkpoint conflicts occur, S1 treats as **retry/transient** and re-enters orderly processing (or pauses).

### Environment ladder

Local/dev/prod may vary in throughput knobs, but S1 semantics remain invariant:

* same offset discipline
* same stall rules
* same idempotency identity
* same event-time semantics

---

## What we should illuminate next (to keep momentum)

Now that S1 is exposed at the “machinery modules” level, the clean next step is to open **S5 Basis & Provenance**, because S1+T0 creates the raw truths, and S5 defines exactly how those truths become portable provenance + deterministic hashes.

---

Alright — opening **S5: Basis & Provenance Spine** and exposing the machinery inside it.
We keep S1/S3/S4/S6/S7/S2/T0 as “fixed contract black boxes.”

S5 is the **anti-drift spine**: it turns “whatever happened internally” into a **portable, deterministic, replay-explainable claim**:

* `input_basis` (exclusive-next watermark vector)
* `graph_version` (if identity graph was consulted)
* group versions + freshness posture
* deterministic `feature_snapshot_hash`

If S5 is sloppy, parity collapses. So we pin it hard.

---

# 1) S5 mission and authority

## S5 is responsible for

1. **Acquiring the basis tokens** for the snapshot:

   * OFP `input_basis` from T0 checkpoints (IJ-08)
   * IEG `graph_version` from S2 when used (IJ-10)
2. **Canonicalizing** snapshot material (stable ordering, stable serialization)
3. **Computing freshness posture** strictly from event-time + explicit `as_of_time_utc`
4. **Assembling provenance blocks** deterministically
5. **Computing `feature_snapshot_hash`** deterministically from the canonicalized snapshot+provenance (hash covers the “parity-critical” blocks)
6. **Failing closed**: if basis/provenance cannot be completed, S5 must refuse to produce a hash and S3 must return UNAVAILABLE.

## S5 is NOT allowed to do

* Never “peek” at EB directly for basis
* Never use wall-clock “now” to compute freshness
* Never invent missing provenance (“basis unknown but here’s a hash anyway”)
* Never allow per-key/per-group basis vectors (one snapshot → one basis)

---

# 2) Pinned S5 design decisions (authoritative)

**PD-S5-01 — One snapshot, one basis vector.**
Every `get_features` response has exactly one `input_basis` (watermark vector) and (when applicable) one `graph_version`.

**PD-S5-02 — Canonicalization is centralized in S5.**
No other node computes the snapshot hash independently.

**PD-S5-03 — Hash inputs are deterministic and include the replay-critical blocks.**
At minimum, the hash must cover:

* ContextPins
* `as_of_time_utc`
* group versions used
* canonicalized feature values
* freshness posture (per group or per group×key, whichever you choose)
* `input_basis`
* `graph_version` if present
* active feature-def policy revision identity (policy_rev + snapshot digest)
  (So “same features under different defs” cannot collide.)

**PD-S5-04 — Freshness is event-time based.**
Freshness/staleness are computed from:

* `as_of_time_utc` (explicit)
* `last_update_event_time_utc` (from T0 read result)
* group TTL policy (from S4 snapshot)
  Never from apply time or wall clock.

**PD-S5-05 — If required tokens are missing, S5 returns error (no hash).**
This is where fail-closed is enforced.

---

# 3) S5 internal subnetworks (inside S5)

### S5.1 Basis Snapshot Collector

**Role:** obtain `input_basis` from T0 via IJ-08 using the same read-view token as the S3 reads (coherence).

* Produces `{stream_name, watermarks{partition->exclusive_next}, epoch_id, partition_set_hash?}`

### S5.2 Graph Context Collector

**Role:** accept `graph_version` from S2 via IJ-10 when identity context was consulted.

* Produces a token with the same shape semantics: `{stream_name, watermarks{partition->exclusive_next}}`

### S5.3 Definition Identity Binder

**Role:** bind the active definition snapshot identity into provenance/hashing:

* `feature_def_policy_rev`
* `feature_def_snapshot_digest`
* `group_inventory_fingerprint`
  This prevents “same values, different meaning” collisions.

### S5.4 Freshness Evaluator

**Role:** compute freshness/staleness/missing posture from event-time.
Inputs:

* group TTL policy (S4)
* as_of_time_utc (S3)
* last_update_event_time_utc or NO_DATA (T0 read result)
  Outputs:
* a deterministic “freshness block” per group (or per group×key, depending on your granularity choice)

### S5.5 Warning & Constraint Compiler

**Role:** standardize “warning codes” that must be deterministic:

* NO_DATA
* STALE_BY_TTL
* PARTITION_STALL_PRESENT (if basis indicates lag beyond corridor)
* RETENTION_BOUNDARY_HIT (if T0 indicates earliest_as_of_supported > request)
  This is how S5 ensures missing/stale is explicit and consistent.

### S5.6 Canonicalizer

**Role:** turn the snapshot material into a canonical representation:

* stable sort order for keys/groups/features
* stable formatting for numbers/strings/timestamps
* explicit handling of null/missing
* forbid non-deterministic structures

### S5.7 Snapshot Hash Engine

**Role:** compute `feature_snapshot_hash` over the canonicalized representation.

* Hash algorithm choice is flexible, but the input byte stream must be deterministic.

### S5.8 Provenance Assembler

**Role:** assemble the provenance object in stable structure:

* ContextPins
* as_of_time_utc
* group versions used
* feature-def identity
* `input_basis`
* optional `graph_version`
* freshness blocks
* warnings summary

### S5.9 Provenance Validator

**Role:** final sanity checks:

* required fields present
* one-basis-per-response
* graph_version included iff identity context used
* stable ordering constraints met
  If any fails → error (no hash).

---

# 4) S5’s internal “contract” with S3 (IJ-09)

S5 receives from S3 what I’ll call **SnapshotMaterial** (still conceptual):

* `context_pins`
* `as_of_time_utc`
* `feature_keys[]` (canonical)
* `group_refs[]` with explicit versions
* `features_map` (values already computed by T0 reads + serve assembly)
* per key×group: `last_update_event_time_utc` or NO_DATA
* active feature-def identity tokens (or a handle to fetch them from S4 snapshot identity)

S5 returns:

* `provenance` (full, deterministic)
* `feature_snapshot_hash`

If S5 can’t return both, it returns an **error** and S3 must return UNAVAILABLE/INVALID_REQUEST as appropriate.

---

# 5) The S5 production paths (inside S5)

## S5-P1: Normal provenance+hash (no IEG)

1. Collect `input_basis` from T0 (Basis Snapshot Collector)
2. Bind feature-def identity (Definition Identity Binder)
3. Evaluate freshness blocks (Freshness Evaluator)
4. Canonicalize features + metadata (Canonicalizer)
5. Assemble provenance (Provenance Assembler)
6. Validate provenance completeness (Provenance Validator)
7. Compute hash (Snapshot Hash Engine)
8. Return `provenance + hash`

## S5-P2: Provenance+hash with IEG consulted

Same as S5-P1, but:

* also collect `graph_version` from S2 (Graph Context Collector)
* include it in provenance and hash inputs

## S5-P3: Basis unavailable / incoherent

If T0 cannot provide coherent checkpoints for the read-view token:

* S5 returns error “BASIS_UNAVAILABLE”
* S3 must return UNAVAILABLE
  (No partial provenance/hashes.)

## S5-P4: Retention boundary violated

If T0 indicates earliest_as_of_supported > request:

* S5 must not “approximate.”
  Two allowed outcomes (pick one; I’m pinning the safer default):

  * **UNAVAILABLE** with explicit reason `RETENTION_BOUNDARY_EXCEEDED` (retry won’t help, but it’s honest), OR
  * a bounded success response that explicitly says “cannot answer requested as_of; earliest supported is X” (still honest).
    **Pinned default: UNAVAILABLE** (fail closed) until you later decide you want bounded responses.

---

# 6) The provenance schema (conceptual) that S5 produces

This is not a formal schema, but it’s the minimum shape that must exist:

* `context_pins`: `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`
* `as_of_time_utc`
* `feature_def`: `{policy_rev, snapshot_digest, group_inventory_fingerprint}`
* `groups_used[]`: list of `{group_name, group_version}`
* `freshness[]`:

  * per group: `{group_ref, ttl_sec, status, max_age_sec, missing_key_count, stale_key_count}`
  * (or per group×key if you need more granularity later; keep v0 group-level)
* `input_basis`: `{stream_name, watermarks{partition_id -> next_offset_to_apply}}`
* `graph_version` (optional): same shape as input_basis
* `warnings[]`: deterministic codes (no free-text in the hash input)
* `feature_snapshot_hash`

**Authoritative note:** The hash covers the canonicalized structure excluding the hash field itself.

---

# 7) Canonicalization rules (the “determinism kernel”)

These are the rules that prevent “same logical snapshot, different bytes” drift:

1. **Sort order**

* FeatureKeys sorted by `(key_type, key_id)`
* Groups sorted by `(group_name, group_version)`
* Features within group sorted by `feature_ordering` from S4 snapshot (never “map iteration order”)

2. **Timestamp formatting**

* RFC3339 with micros, normalized (same as canonical envelope time formatting)

3. **Numeric formatting**

* Define canonical representation (e.g., integers as base-10 strings; floats with a fixed representation rule)
* No locale-dependent formatting

4. **Missing/null**

* A missing feature value must be represented deterministically (either explicit null or explicit “absent” marker) and treated consistently in the hash input.

5. **Warnings**

* Only stable code enums (no variable text) go into hashed canonical form.

---

# 8) S5’s failure taxonomy (what errors it can return)

* `INVALID_REQUEST` (missing required pins, invalid group_ref, etc.)
* `BASIS_UNAVAILABLE` (cannot obtain coherent checkpoint vector)
* `GRAPH_VERSION_UNAVAILABLE` (IEG consulted but no token)
* `DEF_IDENTITY_UNAVAILABLE` (policy snapshot identity missing)
* `CANONICALIZATION_ERROR` (non-deterministic types/values encountered)
* `RETENTION_BOUNDARY_EXCEEDED` (as_of earlier than supported)

Mapping outward:

* INVALID_REQUEST → client error
* everything else → UNAVAILABLE (fail closed)

---

# 9) S5 non-joins (explicitly banned)

* S5 must not read EB directly to form basis.
* S5 must not compute freshness using wall clock.
* S5 must not compute per-key basis vectors.
* S5 must not allow “hash without basis.”
* S5 must not include secrets or raw payloads in provenance.

---

## What’s next

With **S4**, **T0**, **S1**, and now **S5** illuminated, we have the core correctness spine.

Next best node to open is **S3 Serve Plane**, because it is where requests are validated, as-of reads are orchestrated (including coherence token usage), and responses are assembled before handing off to S5.

---

Alright — opening **S3: Serve Plane** and exposing the machinery inside it, with **S4/T0/S5/S2/S6/S7** treated as fixed-contract black boxes.

S3 is where OFP turns the platform’s serving join (**J8**) into a **deterministic, as-of correct** response **with complete provenance** (delegated to S5), under real production constraints (timeouts, load, lag, staleness).

---

# 1) S3 mission and boundary obligations

## S3 must guarantee

1. **Explicit-as-of serving**: always use `as_of_time_utc` from the request; never “latest”.
2. **Canonical-key boundary**: requests use canonical FeatureKeys; S3 does not become a “raw identifier API”.
3. **Group-version explicitness**: requested groups must be `{group_name, group_version}`; no implicit latest.
4. **Coherent read view**: values read from T0 and `input_basis` used in provenance must correspond to the same committed horizon (read_view_token).
5. **Complete provenance + deterministic hash**: S3 must not return a “successful snapshot” unless S5 returns full provenance + `feature_snapshot_hash`.
6. **Fail closed, not best effort**: if correctness/provenance cannot be guaranteed, return UNAVAILABLE (retryable) rather than partial truth.

## S3 must not do

* Not compute its own hash rules (S5 owns canonicalization/hashing)
* Not peek at EB for basis
* Not use wall clock for freshness
* Not bypass policy/version validation (S4)
* Not bypass T0 coherence rules

---

# 2) Pinned S3 design decisions (authoritative)

**PD-S3-01 — Request validation is strict and early.**
Reject malformed requests before touching T0/IEG (protects correctness and load).

**PD-S3-02 — Read-view coherence is mandatory.**
S3 must acquire a **read_view_token** and use it consistently for:

* T0.ReadAsOf
* S5’s basis acquisition (via T0.GetBasis(read_view_token))

**PD-S3-03 — Deterministic response structure.**
Even before hashing, S3 must assemble response material in stable structures (sorted keys/groups) so S5’s canonicalization has a clean input.

**PD-S3-04 — Granularity v0: multi-key, multi-group per request is allowed but bounded.**
S3 enforces request limits (max keys/groups/bytes) from profiles to prevent runaway.

**PD-S3-05 — Serving while lagging is allowed only honestly.**
S3 can serve even if update plane is behind, as long as it can provide truthful `input_basis` and explicit staleness posture (via S5).

---

# 3) S3 internal subnetworks (inside S3)

### S3.1 API Boundary Adapter

**Role:** Accept J8 requests and produce a normalized internal request object.

* gRPC/HTTP mechanics are implementation choices; semantics are fixed.

### S3.2 Request Validator & Normalizer

**Role:** Enforce “no hidden assumptions”.
Validates:

* required ContextPins present
* `as_of_time_utc` present and parseable
* feature_keys canonical and well-formed
* group_refs include explicit versions
* request size limits (max keys/groups)
  Outputs a normalized request with stable ordering.

### S3.3 Group Registry Resolver (S4 client)

**Role:** Calls S4 to validate group refs and obtain:

* group definitions
* TTL/freshness policies
* stable feature ordering per group
* feature-def snapshot identity (policy_rev, digest, etc.)
  This prevents serving unsupported groups.

### S3.4 Read-View Orchestrator (T0 client)

**Role:** Obtains a **read_view_token** from T0 and orchestrates all reads under it.

* This is the “coherence broker” usage point.

### S3.5 As-Of State Reader (T0 client)

**Role:** Executes T0.ReadAsOf under read_view_token:

* returns feature values (possibly sparse)
* returns `last_update_event_time_utc` per key×group (or NO_DATA)
* returns any retention boundary signals

### S3.6 Optional Identity Context Orchestrator (S2 client)

**Role:** Only used when a requested group explicitly needs identity graph context.

* Calls S2, which may call IEG, and returns `graph_version` token.

**Pinned v0 stance:** DF is expected to provide canonical FeatureKeys, so S3 should not use S2 to “normalize” bad inputs; that’s INVALID_REQUEST.

### S3.7 Snapshot Material Assembler

**Role:** Build the **SnapshotMaterial** package for S5:

* normalized keys/groups
* feature values
* last_update_event_times
* as_of_time_utc
* group versions used
* feature-def identity tokens
* optional graph_version from S2

### S3.8 Provenance + Hash Delegator (S5 client)

**Role:** Calls S5 (IJ-09):

* receives provenance + `feature_snapshot_hash`
* enforces “no response without provenance+hash”

### S3.9 Response Assembler

**Role:** Produces the final outward response:

* feature snapshot payload
* provenance blocks
* hash
* structured warnings/errors

### S3.10 Serve Health & Rate Control

**Role:** Enforce serve concurrency limits, rate limits, timeouts, and emit IJ-12 telemetry to S6:

* latency/errors
* staleness/missing rates
* hash failures
* request size histograms

---

# 4) S3 “happy path” (IP-3) step-by-step

1. **Receive request** (S3.1)
   `get_features(ContextPins, feature_keys[], group_refs[], as_of_time_utc)`

2. **Validate & normalize** (S3.2)

* reject malformed requests
* stable-sort keys and group refs
* enforce limits

3. **Resolve group defs** (S3.3 via S4)

* validate each group_ref exists
* fetch TTL policy + stable feature ordering
* bind feature-def identity snapshot

4. **Acquire read view** (S3.4 via T0)

* `read_view_token = T0.BeginReadView()`

5. **Read as-of state** (S3.5 via T0)

* `ReadAsOf(read_view_token, context_pins, keys, group_refs, as_of_time_utc)`
* returns values + last_update_event_time per key×group (or NO_DATA)

6. **Optional identity context** (S3.6 via S2, only if required)

* receive `graph_version` token (must be included in provenance)

7. **Assemble SnapshotMaterial** (S3.7)

* create deterministic structure to send to S5

8. **Provenance + hash** (S3.8 via S5)

* S5 obtains `input_basis` from T0 using the same read_view_token
* S5 computes freshness blocks + provenance + hash

9. **Assemble response + emit telemetry** (S3.9 + S3.10)

* return feature snapshot + provenance + `feature_snapshot_hash`
* emit metrics/traces/logs via IJ-12

---

# 5) S3 failure taxonomy (authoritative outward behavior)

S3 must classify failures into these buckets:

## A) INVALID_REQUEST (non-retryable)

* missing/invalid ContextPins
* missing/invalid `as_of_time_utc`
* non-canonical keys (raw identifiers)
* unknown/unsupported group_ref (name/version)
* request too large (exceeds limits)

## B) NOT_FOUND (non-retryable; rare)

* request is well-formed but the ContextPins scope does not exist in OFP at all (depends on how you want to treat “unknown run/world”; this can also be INVALID_REQUEST depending on your SR/IG posture)

## C) UNAVAILABLE (retryable or operational)

* T0 cannot provide a coherent read view or basis vector
* S5 cannot compute complete provenance/hash
* identity context is required but IEG is unavailable
* retention boundary prevents answering the requested as-of (fail closed by default)

**Pinned rule:** No “success” without provenance+hash. If S5 fails, S3 returns UNAVAILABLE.

---

# 6) Two subtle production issues S3 must handle (without drifting)

## Issue 1: OFP lag vs decision boundary

DF might request features for an event that OFP hasn’t applied yet.
S3 must still serve honestly:

* `input_basis` reveals what offsets were applied
* freshness blocks reveal staleness/missing data
* DF uses degrade posture / fail-safe logic based on this.

S3 does not “wait until caught up” by default (that would introduce hidden timing coupling). Waiting could exist as an explicit client hint later, but v0 default is honest immediate serving.

## Issue 2: Retention/compaction boundaries

If T0 retention means older as-of queries are impossible, S3 must not approximate.
Default: return UNAVAILABLE with explicit reason, so parity and audit don’t silently drift.

---

# 7) S3 non-joins (explicitly banned inside S3)

* No direct reads from EB or Archive for “serve path”.
* No implicit IEG resolution of raw identifiers.
* No computing hash/provenance in S3.
* No using apply/ingest time as freshness.
* No “latest group version” fallback.

---

# 8) What S3 exposes to the rest of OFP (still internally)

* A deterministic “serve contract” inside OFP that S7 can gate with SERVE_READY logic.
* Telemetry that S6 can publish and DL can consume indirectly (lag, missing, staleness, latency).

---

## What to open next

Now the core data/meaning/provenance surfaces are illuminated (**S4, T0, S1, S5, S3**).
Next best node to open is **S2 Identity Resolution**, because it’s the remaining correctness-critical dependency that determines how `graph_version` is produced and how often J7b is exercised.

---

Alright — opening **S2: Identity Resolution** and exposing the machinery inside it.

S2’s job is to turn **observed identifiers** (from events or requests) into **canonical FeatureKeys** (entity IDs), *optionally* by consulting IEG, and to produce/propagate **`graph_version`** when identity context depended on the identity graph.

We’re still keeping other nodes as fixed-contract black boxes:

* S1/S3 call S2
* S2 may call IEG
* S5 consumes `graph_version` tokens from S2
* S6 observes S2 health
* S7 governs posture/limits

---

# 1) S2 mission and strict boundaries

## S2 must guarantee

1. **Canonical key output only**
   S2 outputs FeatureKeys as `(key_type, key_id)` where `key_id` is canonical entity ID.
   No PANs/device_fps/etc as key_id, ever.

2. **ContextPins scoping**
   All resolution is scoped by ContextPins `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`.
   No cross-run/world mixing.

3. **Graph-version propagation**
   If resolution used identity graph context (IEG), S2 must return a **`graph_version` token** (watermark-vector semantics) and it must flow to S5 → provenance.

4. **Deterministic behavior**
   Same input (ContextPins + identifier bundle) should resolve to the same canonical key (under the same graph_version basis).

5. **Fail closed when required**
   If S1 needs identity to apply a relevant fact and S2 can’t resolve safely → S1 stalls; if S3 requires identity context → UNAVAILABLE. No guesses.

## S2 must not do

* It must not accept “best effort fuzzy matching” that isn’t explainable.
* It must not cache across ContextPins.
* It must not invent graph_version (timestamps are not allowed).
* It must not drift into being a public identifier API; it’s an internal service for OFP.

---

# 2) Pinned S2 design decisions (authoritative)

**PD-S2-01 — Deterministic resolution contract:**
S2 resolution is a pure function of:

* ContextPins
* identifier bundle (observed identifiers and optional existing entity refs)
* the identity-graph basis token (graph_version) if IEG consulted

**PD-S2-02 — Two resolution modes (explicit):**

* **Mode A: Direct/Local resolution** (no IEG call; no graph_version needed)
* **Mode B: Graph-backed resolution** (IEG consulted; graph_version required)

S2 must state which mode was used in its response.

**PD-S2-03 — Cache entries must carry basis identity when graph-backed.**
If a response came from IEG, cache records must include the `graph_version` they’re valid under (or a conservative validity rule).

**PD-S2-04 — v0 scope: identity resolution only (not neighborhood feature computation).**
S2 resolves canonical keys; it doesn’t compute graph features.

---

# 3) S2 internal subnetworks (inside S2)

### S2.1 Input Normalizer

**Role:** canonicalize and sanitize identifier bundles:

* normalize formats (trim, casing, canonical country codes if needed)
* deduplicate identifiers
* validate identifier types (enum)
* reject obviously malformed identifiers early

### S2.2 Resolution Policy Router

**Role:** decide resolution path per request:

* Can we resolve directly from already-present canonical EntityRefs?
* Do we have a cache hit (scoped + valid)?
* Must we consult IEG?
* Are we allowed to consult IEG under current operational posture/limits?

### S2.3 Local Resolver

**Role:** “cheap” deterministic resolution when possible:

* If event already contains canonical entity refs → pass-through
* If there are stable local mappings for this run/world (optional, if you maintain them)
  This path returns `resolution_source = DIRECT` and **no graph_version**.

### S2.4 IEG Client

**Role:** talk to IEG:

* build request including ContextPins + identifier bundle + required key_types
* handle retries/timeouts
* parse response into canonical keys + graph_version

### S2.5 Cache Layer (ContextPins-scoped)

**Role:** store results to avoid repeated IEG calls.
Cache key includes:

* ContextPins
* identifier bundle fingerprint (deterministic canonical form)
* required key_types
  Optionally includes:
* “resolution intent” (update vs serve) if semantics differ (prefer not to)

Cache value includes:

* canonical FeatureKeys result
* `resolution_source` (CACHE / IEG)
* if IEG influenced result: `graph_version` token or a validity rule

### S2.6 Graph-Version Handler

**Role:** enforce the platform semantics:

* graph_version must be a watermark-vector token (stream_name + exclusive-next offsets)
* ensure it is present whenever IEG was consulted
* ensure it is passed along to S5 via IJ-10

### S2.7 Output Formatter

**Role:** produce a deterministic response structure:

* stable ordering of FeatureKeys
* mode/source indicators
* graph_version if present

### S2.8 Health & Telemetry Emitter

**Role:** emit to S6:

* cache hit/miss rates
* IEG latency/error rate
* “identity required but unavailable” counts
* timeouts/retry counts
* rate limiting events
  (without high cardinality labels)

---

# 4) S2 input/outputs (conceptual contract)

## S2.ResolveIdentity(Request) → Result

### Inputs

* `context_pins`
* `subject_bundle`:

  * `observed_identifiers[]` (type + value)
  * optional `entity_refs[]` (already canonical)
* `required_key_types[]`
* `purpose` ∈ {`update_apply`, `serve_context`} (optional, mostly for observability)

### Outputs

* `feature_keys[]` (canonical)
* `resolution_source` ∈ {DIRECT, CACHE, IEG}
* `graph_version` (present iff IEG was consulted or the cached value is graph-backed)
* `notes` (deterministic reason codes only; no free-text in hashed provenance)

---

# 5) S2 production paths (how S2 behaves)

## S2-P1: Direct pass-through (no IEG)

1. Normalize input
2. If canonical EntityRefs exist and satisfy required key_types → return them
3. resolution_source=DIRECT, no graph_version

## S2-P2: Cache hit (graph-backed or direct)

1. Normalize input → compute deterministic cache key
2. If cache hit:

   * return cached FeatureKeys
   * if cached result is graph-backed, include its graph_version (or validity token)
3. resolution_source=CACHE

## S2-P3: Graph-backed resolution (IEG call)

1. Normalize input
2. Rate-limit check / posture check (allowed)
3. Call IEG with ContextPins + identifiers + required_key_types
4. Receive canonical keys + graph_version
5. Validate graph_version shape semantics (watermark vector)
6. Store in cache with graph_version
7. Return resolution_source=IEG + graph_version

## S2-P4: Identity required but unavailable

Triggers:

* IEG unavailable/timeout and no valid cache hit
* posture prohibits IEG usage (e.g., degraded mode)
  Response:
* Return a structured failure that S1 interprets as “STALL_CORRECTNESS” and S3 interprets as UNAVAILABLE.

---

# 6) Graph-version semantics inside S2 (critical pin)

**Pinned meaning:** `graph_version` is a monotonic “applied basis” token, not a wall-clock timestamp.

Shape:

* `stream_name`
* `watermarks{partition_id -> next_offset_to_apply}` (exclusive-next)

**Inclusion rule:**

* If IEG was consulted for a resolution that influences the snapshot or update, S2 must output graph_version.
* If a cached result was originally IEG-derived, graph_version must still be available (either stored or re-checkable).

**Why this matters:** it is what makes identity context replay-explainable and aligns with how OFP uses `input_basis`.

---

# 7) Caching rules (to prevent semantic drift)

**PD-S2-CACHE-01 — Cache key includes ContextPins.**
No cross-run/world reuse.

**PD-S2-CACHE-02 — Cache cannot “smear” across key_types.**
Key_type requirements are part of the cache key.

**PD-S2-CACHE-03 — Cache entries must not outlive their validity silently.**
If identity graph can evolve within a run/world:

* Either cache entries carry their graph_version and are treated as “valid under that version,” or
* cache TTL is conservative and S2 re-consults IEG periodically.
  (v0 preference: store graph_version and treat it as the explicit basis token.)

**PD-S2-CACHE-04 — Cache hit must not change meaning.**
Hit/miss can affect latency only.

---

# 8) Failure posture and how it propagates

* **S1 update path:** if identity is required to apply a relevant offset and S2 fails → S1 stalls that partition offset (no checkpoint advance).
* **S3 serve path:** if identity context is required and S2 fails → S3 returns UNAVAILABLE (retryable).

S2 makes this explicit via failure reason codes:

* `IEG_TIMEOUT`
* `IEG_UNAVAILABLE`
* `RATE_LIMITED`
* `IDENTIFIERS_INVALID`
* `NO_RESOLUTION_POSSIBLE`

---

# 9) S2 observability essentials (so DL/ops can reason)

S2 must export (via S6):

* IEG call latency + error rate
* cache hit rate
* “identity required but unavailable” count
* rate limiting events
* (optional) top-level reason code distribution

No high-cardinality labels (no key_id, no run_id in metric labels); use structured logs/traces for correlation.

---

# 10) S2 non-joins (explicitly banned)

* No cross-ContextPins cache sharing
* No “fuzzy” identity guessing without basis token
* No wall-clock “graph_version”
* No making S2 a public endpoint that DF calls directly (DF goes DF→OFP→S2 if needed)

---

## What to open next

Now S2 is illuminated, the last major “machinery nodes” remaining are:

* **S7 Lifecycle & Rebuild Governor** (state machine + epoch orchestration)
* **S6 Operability & Observability** (integration of signals, readiness posture)

Given what we already pinned, the best next node to open is **S7**, because it glues together policy activation (IP-5), stalls (IP-6), and rebuild/epoch swap (IP-7), and it’s where implementers otherwise drift into ad-hoc operational behavior.

---

Alright — opening **S7: Lifecycle & Rebuild Governor**.

S7 is the **operational governor** for the whole OFP vertex. It doesn’t “compute features” or “define meaning”; it **keeps the machinery correct under production realities**: boots cleanly, enforces readiness, controls pause/throttle, coordinates policy activation, orchestrates rebuild/epoch swap, and makes every posture change **explicit and observable** (profiles-not-forks).

---

## 1) What S7 owns

### S7 is responsible for

* **Boot sequencing** so OFP never runs without:

  * an active feature definition snapshot (S4),
  * a usable durable store epoch (T0),
  * and the ability to produce provenance (`input_basis`) for serving.
* **Explicit readiness** (separate Update vs Serve readiness).
* **Operational posture control**:

  * start/pause/resume/throttle/drain S1 (Update Plane),
  * open/close/shed-load for S3 (Serve Plane),
  * enable/disable S8 (optional pointer emitter).
* **Policy activation orchestration** (via S4):

  * load/validate/activate by `policy_rev`,
  * enforce coherent cutover semantics,
  * emit “change is a fact” signals.
* **Rebuild/backfill orchestration** (via T0 epoch ops + S1 replay):

  * explicit rebuild plans,
  * staging epoch replay,
  * atomic epoch swap,
  * no basis regression.
* **Stall governance**:

  * “stall means correctness threatened” → no forced checkpoint advance.
* **Environment ladder compliance**:

  * differences are profiles (wiring/policy), never semantic forks.

### S7 must never do

* Change semantic meaning (event-time, watermark meaning, idempotency identity, version meaning).
* “Skip a relevant fact” to keep things moving (no silent advance).
* Allow serving without complete provenance/hashing capability.

---

## 2) S7’s I/O surfaces (what it talks to)

### Inputs to S7

* **Environment profiles**

  * wiring profile (endpoints, limits, timeouts)
  * policy profile (feature_def policy_rev, pointer enablement, corridors)
* **Signals**

  * From S1: consuming/paused/stalled, stalled_offset + reason, lag summary
  * From S3: serve latency/errors, “provenance capable” flag
  * From S4: activation success/failure, active policy_rev identity
  * From T0: store ready/integrity, checkpoint summaries, epoch status, retention boundary
  * From S8 (if enabled): backlog/failure signals
* **Ops commands** (Run/Operate)

  * pause/resume, trigger rebuild, activate policy rev, drain/stop, etc.

### Outputs from S7

* **To S1 (IJ-14):** START/PAUSE/RESUME/THROTTLE/DRAIN
* **To S3 (IJ-14):** OPEN/CLOSE_SERVE, SHED_LOAD, set limits
* **To S4 (IJ-15):** LOAD/VALIDATE/ACTIVATE policy_rev
* **To T0 (IJ-16):** PREPARE_EPOCH/RESET_EPOCH/SWAP_EPOCH/COMPACT
* **To S8 (IJ-14-ish):** ENABLE/DISABLE, rate limits
* **To S6 (through the emitters):** posture facts (serve readiness, active policy rev, rebuild events)

---

## 3) S7 state machines (the core machinery)

S7 is best understood as **four coupled state machines** rather than one giant state.

### A) Update State (controls S1)

* `UPDATE_STOPPED`
* `UPDATE_CONSUMING`
* `UPDATE_THROTTLED`
* `UPDATE_PAUSED`
* `UPDATE_STALLED` *(explicit offset + reason)*
* `UPDATE_DRAINING`

Key rule: **STALLED** means “cannot advance basis truthfully.” S7 may pause/throttle but cannot force advance.

### B) Serve State (controls S3)

* `SERVE_CLOSED`
* `SERVE_OPEN`
* `SERVE_SHEDDING` *(limits tightened)*
* `SERVE_DEGRADED` *(still honest, but constrained)*
* `SERVE_UNAVAILABLE` *(cannot produce complete provenance/basis)*

Key rule: **SERVE must not be OPEN unless provenance is complete** (S5 can produce `input_basis` and hash).

### C) Policy State (controls S4)

* `POLICY_NONE`
* `POLICY_STAGED(policy_rev)`
* `POLICY_ACTIVE(policy_rev, snapshot_digest)`
* `POLICY_REJECTED(policy_rev, reason)`

Key rule: policy changes are **explicit activations**, never silent.

### D) Epoch State (controls T0)

* `EPOCH_ACTIVE(epoch_id)`
* `EPOCH_REBUILDING(staging_epoch_id, target_basis)`
* `EPOCH_SWAPPING(staging→active)`
* `EPOCH_INTEGRITY_FAIL`

Key rule: **epoch swap is atomic** and must not cause basis regression.

---

## 4) S7 internal subnetworks (inside S7)

### S7.1 Profile Loader

Loads wiring + policy profiles and exposes them as read-only config to other S7 modules.

### S7.2 Boot Orchestrator

Implements the boot sequence: policy → store → update → serve.

### S7.3 Readiness Gatekeeper

Computes:

* `UPDATE_READY` = policy active + T0 ready + update consumer able to run
* `SERVE_READY` = policy active + T0 coherent read views + S5 provenance-capable

### S7.4 Policy Activation Coordinator

Orchestrates load/validate/activate with S4 and enforces cutover safety (see below).

### S7.5 Rebuild Manager

Owns the “explicit rebuild plan” lifecycle:

* staging epoch prep
* replay mode start
* progress tracking to target basis
* atomic swap
* emitted governance facts

### S7.6 Stall Supervisor

Standardizes stall reasons and actions:

* record stall as a fact
* decide whether to pause further partitions, throttle, or keep serving honestly
* never forces checkpoint advancement

### S7.7 Backpressure Controller

Turns lag/latency/staleness into operational controls:

* throttle S1
* shed S3 load
* disable S8 if it becomes an outage vector

### S7.8 Drain/Shutdown Controller

Ensures clean stop:

* close serve
* drain update applies (flush checkpoints)
* emit “shutdown posture” facts

### S7.9 Ops Command Router

Receives Run/Operate commands and maps them to safe sequences.

---

## 5) The key production flows S7 orchestrates

### Flow F1 — Boot (happy path)

1. **Load profiles** (S7.1)
2. **Activate policy_rev** via S4 (S7.4)

   * if rejected and no prior good → OFP stays not-ready
3. **Initialize T0** (epoch active, integrity ok)
4. **Start Update Plane** (S1 consuming)
5. **Open Serve Plane** only when provenance-capable

   * i.e., T0 coherent read view + S5 can emit `input_basis` + hash

### Flow F2 — Policy activation (in-place, no drift)

* S7 stages a new policy_rev, validates and activates it.
* **Cutover rule:** one record/request sees one coherent snapshot.
  Implementation can be:

  * S4 provides an atomic snapshot handle; S1/S3 pin the handle per unit-of-work
    *(S7 doesn’t need to pause the world if handles are coherent.)*
* Emits activation/rejection fact.

### Flow F3 — Stall handling (fail closed, operably loud)

* S1 reports `STALLED at (partition, offset, reason)`.
* S7 transitions UpdateState → `UPDATE_STALLED`.
* Serving may remain open **only if** it can still produce truthful provenance (it usually can; it will just show lag via `input_basis` and staleness).
* S7 may throttle/pause other partitions to stabilize, but cannot skip the stalled offset.

### Flow F4 — Rebuild/backfill (epochal, no time travel)

1. Receive explicit rebuild plan (scope + target_basis + policy_rev)
2. `PREPARE_EPOCH(staging)` in T0
3. Pause normal consumption or run replay mode into staging epoch
4. Replay facts from explicit basis (EB/Archive continuation) until target basis reached
5. Atomic `SWAP_EPOCH(staging→active)`
6. Resume normal consumption and serving
7. Emit auditable “rebuild executed” fact

### Flow F5 — Drain/stop

* Close serving first (or shed to zero)
* Drain update applies (finish in-flight, flush checkpoint truthfully)
* Stop consumers
* Emit shutdown posture fact

---

## 6) Environment ladder constraints S7 must enforce

* **Profiles, not forks:** all the above flows exist in local/dev/prod; only:

  * limits/timeouts,
  * enablement flags (e.g., S8),
  * thresholds/corridors,
  * retention/archive availability
    differ by profile.
* **Local can be smaller, not different:** you may collapse services, but S7 still enforces readiness, policy activation identity, coherent basis, and explicit rebuild.

---

## 7) Hard “no drift” rules S7 enforces

* Never open serving if provenance (`input_basis` + hash) cannot be produced.
* Never force checkpoint advance past a relevant uninterpretable fact.
* Never allow silent policy change (every activation/rejection is an observable fact).
* Never allow epoch swap that regresses basis tokens.
* Never allow “semantic toggles” via ops controls (pause/throttle only changes posture).

---

If you want the next node: **S6 Operability & Observability** is the natural follow-up, because it’s how all these postures become visible to DL/ops and how you keep the environment ladder honest end-to-end.

---

Alright — opening **S6: Operability & Observability** and exposing the machinery inside it.

S6 is the **visibility plane** for OFP. It doesn’t change correctness, but it makes correctness *operable* and makes the environment ladder *real* by ensuring every critical boundary decision (stall, policy activation, rebuild, serve unavailable, etc.) becomes a **joinable signal** that DL/ops can consume.

---

# 1) S6 mission and strict boundaries

## S6 must guarantee

1. **All critical boundary decisions are visible**
   If OFP stalls, changes policy_rev, rebuilds, closes serving, or cannot produce provenance, S6 must emit a structured, joinable signal.

2. **Low-cardinality metrics + high-cardinality traces/logs**
   Metrics are for dashboards/alerts. Detailed per-request/per-offset context belongs in traces/logs.

3. **Correlation keys exist everywhere they should**
   S6 must preserve joinability using:

* ContextPins when known (`manifest_fingerprint, parameter_hash, scenario_id, run_id`)
* event identifiers (`event_id, event_type, ts_utc`) when a boundary event relates to a fact
* feature identifiers (`feature_snapshot_hash`, group versions) when it relates to serving
* basis tokens (`input_basis`, and `graph_version` when relevant) in logs/traces, not metrics labels

4. **Environment ladder consistency**
   Local/dev/prod can differ in sampling and thresholds, but they must produce the same *kinds* of signals with the same meaning.

## S6 must not do

* Must not mutate serving outputs or feature meanings.
* Must not gate correctness on “observability being up” (correctness first).
* Must not log secrets or raw payload dumps.
* Must not create a second “truth stream” — it emits observability signals, not business facts.

---

# 2) Pinned S6 design decisions (authoritative)

**PD-S6-01 — Separate “signals” into three channels**

* **Metrics** (dashboards, alerts; low cardinality)
* **Structured events** (boundary facts; joinable and searchable)
* **Traces** (request/event-level causality)

**PD-S6-02 — A “boundary fact” is emitted for every correctness-affecting posture change**
Examples:

* partition stalled
* policy activated/rejected
* rebuild started/completed/failed
* serving closed/opened/degraded
* provenance/hash unavailable

**PD-S6-03 — Metrics never include high-cardinality IDs as labels**
No run_id, event_id, key_id, snapshot_hash as metric labels. Put those in logs/traces.

**PD-S6-04 — S6 exports the active policy_rev as a first-class signal**
You must always be able to answer: “what semantics were active when this happened?”

---

# 3) S6 internal subnetworks (inside S6)

### S6.1 Signal Ingestors

Receives raw signals from:

* **S1** (update): lag, watermark age, apply failures, stall facts
* **S3** (serve): latency/errors, missing/stale rates, hash/provenance failures
* **S4** (policy): activation/rejection facts, active policy_rev
* **S2** (identity): IEG call latency/errors, cache hit rate, identity unavailable counts
* **S7** (lifecycle): readiness state changes, rebuild orchestration events
* **T0** (store): integrity alarms, retention boundary info, checkpoint summaries
* **S8** (pointer emitter): backlog, publish failures (if enabled)

### S6.2 Correlation & Context Enricher

Standardizes context attachment:

* attaches ContextPins when available
* attaches event linkage when a signal is about a specific delivered record
* attaches snapshot linkage for serving signals
* attaches policy_rev identity everywhere as a “semantic context”

### S6.3 Metrics Aggregator

Maintains low-cardinality counters, gauges, histograms.
Examples:

* consumer lag / watermark age per partition (bounded)
* p95 serve latency
* staleness rate
* missing-feature rate
* update apply error rate
* IEG client error rate
* pointer backlog (if enabled)

### S6.4 Boundary Fact Emitter

Produces structured events (think “audit-like but operational”) such as:

* `OFP_PARTITION_STALLED`
* `OFP_POLICY_ACTIVATED` / `OFP_POLICY_REJECTED`
* `OFP_REBUILD_STARTED` / `COMPLETED` / `FAILED`
* `OFP_SERVE_STATE_CHANGED` (OPEN/CLOSED/DEGRADED)
* `OFP_PROVENANCE_UNAVAILABLE`
* `OFP_RETENTION_BOUNDARY_EXCEEDED`

These events are joinable and are what ops/DL can reason over.

### S6.5 Trace Adapter

* Creates spans for:

  * `get_features` request handling (S3)
  * IEG calls (S2)
  * T0 reads/basis acquisition
* Propagates trace context if it exists.
* Ensures traces carry correlation fields (as span attributes, not metric labels).

### S6.6 Log Policy & Redaction Guard

Enforces safe logging:

* no secrets
* no raw payload dumps
* only by-ref pointers and stable IDs
* allows sampling for high-volume events

### S6.7 Health Synthesizer

Computes OFP-visible health posture for S7/DL/ops:

* UPDATE health: lag, stalls, apply error corridors
* SERVE health: latency, error corridors, provenance availability
* Identity health: IEG availability, resolution failure corridors
* Store health: integrity flags, retention boundary posture

This is how S7 makes decisions and how DL gets reliable signals.

---

# 4) The “minimum metric set” S6 must publish (platform-critical)

## Update-plane minimums (from S1/T0)

* `ofp_consumer_lag{partition}` (bounded partitions only)
* `ofp_watermark_age_seconds{partition}` (how stale applied basis is)
* `ofp_apply_success_rate`
* `ofp_apply_error_rate_by_class` (small finite classes)
* `ofp_partition_stalled` (boolean gauge) + `stalled_partition_count`

## Serve-plane minimums (from S3/S5/T0)

* `ofp_get_features_latency_ms` (histogram)
* `ofp_get_features_error_rate_by_code`
* `ofp_missing_feature_rate`
* `ofp_stale_feature_rate`
* `ofp_hash_failure_rate`
* `ofp_provenance_unavailable_rate`

## Policy/meaning minimums (from S4/S7)

* `ofp_active_feature_def_policy_rev` (as a log/structured-event always; as a metric, expose a hash/fingerprint rather than raw rev if needed)
* `ofp_policy_activation_count_by_result`

## Identity minimums (from S2)

* `ofp_ieg_call_latency_ms`
* `ofp_ieg_error_rate`
* `ofp_identity_unavailable_rate`
* `ofp_identity_cache_hit_rate`

## Optional pointer emitter (from S8)

* `ofp_pointer_backlog_depth`
* `ofp_pointer_publish_error_rate`

---

# 5) The “boundary facts” S6 must emit (non-negotiable)

These are the **operational truth events** that prevent silent drift:

### A) Stalls (correctness threatened)

`OFP_PARTITION_STALLED`

* stream, partition, offset
* reason_code (enum)
* event_type/event_id if safe
* ContextPins if known
* active policy_rev
* emitted once per stall, plus periodic “still stalled” heartbeat (low rate)

### B) Policy changes (meaning changes)

`OFP_POLICY_ACTIVATED` / `OFP_POLICY_REJECTED`

* policy_rev, snapshot_digest, group_inventory_fingerprint
* actor/trigger (boot, run/operate)
* reason if rejected

### C) Rebuilds/backfills (derived truth regeneration)

`OFP_REBUILD_STARTED` / `COMPLETED` / `FAILED`

* rebuild_id
* scope summary
* target_basis summary (not full vector in the event; store by-ref or include a digest)
* policy_rev used
* epoch ids (old/new)
* actor

### D) Serve posture changes (safety)

`OFP_SERVE_STATE_CHANGED`

* from_state → to_state
* reason_code (e.g., PROVENANCE_UNAVAILABLE, STORE_UNHEALTHY, LOAD_SHEDDING)
* policy_rev

### E) Provenance integrity failures

`OFP_PROVENANCE_UNAVAILABLE`

* why (basis missing, graph_version missing, def identity missing)
* request size summary (keys/groups count)
* policy_rev

### F) Retention boundary violations

`OFP_RETENTION_BOUNDARY_EXCEEDED`

* requested_as_of
* earliest_supported_as_of
* policy_rev
* (optionally) “needs archive/backfill” hint

These events are how DL/ops can govern the platform without guessing.

---

# 6) How S6 supports the DL/DF safety loop (without directly coupling)

S6’s outputs feed the observability pipeline that DL reads. S6 does **not** compute degrade posture, but it must provide the signals DL needs:

* watermark age (how far OFP is behind)
* stall presence (hard correctness issue)
* serve latency/errors (availability risk)
* provenance/hash failures (integrity risk)
* identity resolution failures (graph context risk)

This makes the DL loop rational and auditable.

---

# 7) Environment ladder knobs for S6 (what changes by profile)

### Local

* high verbosity logs
* high trace sampling (or 100% for small runs)
* permissive thresholds
* simple dashboards

### Dev

* representative sampling
* alert thresholds close to prod
* chaos testing / failure injection visibility

### Prod

* sampled traces
* strict redaction
* stable SLO corridors
* durable long-term metrics retention
* explicit alerting on stalls, provenance failures, policy activation failures

**Pinned rule:** semantics do not change; only sampling/thresholds/retention do.

---

# 8) S6 non-joins (explicitly banned)

* S6 must not emit business events to EB.
* S6 must not include raw PII/secrets in logs.
* S6 must not gate serving on observability pipeline uptime.
* S6 metrics must not use high-cardinality IDs as labels.

---

## Where we are now

All core subnetworks are illuminated:

* S4 (meaning/policy)
* T0 (state/checkpoint substrate)
* S1 (update/apply)
* S5 (basis/provenance/hash)
* S3 (serve orchestration)
* S2 (identity resolution)
* S7 (lifecycle/rebuild)
* S6 (operability/observability)

**S8** remains optional and OFF by default, so we can skip opening it unless you intend to enable pointer emission.

If you want, the next step is to do a **quick “integration pass” sanity check**: for each boundary fact above, confirm which node produces it and which IJ/IP/IL it anchors to — that’s how we ensure the illuminated internals still perfectly satisfy the frozen outer network.

---

Alright — opening **S8: Optional Audit Pointer Emitter** and exposing the machinery inside it.

S8 exists to publish **small, non-decisionable pointer events** to **`fp.bus.audit.v1`** (optional), so other tools/services can index “something was written/served at ref X” **without embedding payloads**. It must **never** become a second truth stream and must **never** gate correctness.

---

## 1) S8 mission and hard boundaries

### S8 is responsible for

* Taking **pointer candidates** from inside OFP (typically from S3/S5 after a successful serve),
* Applying a **policy gate** (enabled? sampled? bounded?),
* Emitting a **canonical-envelope event** to `fp.bus.audit.v1`,
* Exposing its own health/backlog/failures to S6 (and allowing S7 to disable/throttle it).

### S8 must never do

* Never block or fail `get_features` because pointers can’t be published.
* Never publish feature values, key lists, raw payloads, or anything decisionable.
* Never be consumed by OFP/DF as an input for decisions (metadata only).
* Never “invent” provenance; it only re-emits already-available pointer metadata.

---

## 2) When S8 is enabled (and why it’s optional)

S8 should be **OFF by default** in v0 because:

* The authoritative “what features were used” record lives in **DF→DLA** provenance/audit.
* Emitting a pointer per `get_features` can be high-volume and not always useful.

So S8 is enabled only via a **policy/profile knob**, typically one of:

* **OFF** (default)
* **ON_PERSISTED_ONLY**: emit only when there is a real by-ref object (e.g., a persisted snapshot blob ref)
* **ON_SAMPLED**: emit a bounded sample of served snapshots (for observability/indexing)

This keeps it aligned with “profiles not forks”.

---

## 3) S8’s inputs and outputs (conceptual contracts)

### Input to S8: `SnapshotPointerCandidate` (from S3/S5 via IJ-17)

Minimum fields:

* `context_pins` (manifest_fingerprint + optional parameter_hash/scenario_id/run_id)
* `as_of_time_utc`
* `feature_snapshot_hash`
* `groups_used[]` (name+version only; **no key lists**)
* `input_basis` token *or* an `input_basis_digest` (prefer digest if vector is large)
* `graph_version` token/digest (only if used)
* `feature_def_identity` (policy_rev + snapshot_digest)
* optional `snapshot_ref` (object locator + digest) **only if you actually persist snapshots**
* optional trace context (`trace_id`, `span_id`, `parent_event_id`)

### Output from S8: `ofp.snapshot_pointer.v1` event to `fp.bus.audit.v1`

Canonical envelope fields:

* `event_type = "ofp.snapshot_pointer.v1"` **(pinned name)**
* `event_id = feature_snapshot_hash` **(pinned idempotency rule)**
* `ts_utc = as_of_time_utc` (domain time of what the snapshot represents)
* `emitted_at_utc = now` (when it was published)
* `manifest_fingerprint` (+ optional pins)
* `producer = "ofp.s8"`

Payload is **metadata only**:

* `feature_snapshot_hash`
* `as_of_time_utc`
* `groups_used[]`
* `feature_def_identity`
* `input_basis_digest` (+ optionally the basis vector if you decide it’s always small)
* `graph_version_digest` (+ optional token if small)
* optional `snapshot_ref` (by-ref pointer if it exists)

---

## 4) S8 internal subnetworks (inside S8)

### S8.1 Candidate Intake

* Receives candidates from S3/S5.
* Performs **cheap structural checks** (required fields present, hash present).

### S8.2 Policy Gate & Sampler

* Checks the enablement mode (OFF / ON_PERSISTED_ONLY / ON_SAMPLED).
* Applies sampling/rate limits **before** any buffering.
* Ensures bounded behavior: **S8 cannot be an outage vector**.

### S8.3 Canonical Envelope Builder

* Builds the canonical event envelope:

  * `event_id = feature_snapshot_hash` (deterministic)
  * `event_type = ofp.snapshot_pointer.v1`
  * `ts_utc = as_of_time_utc`, `emitted_at_utc = now`
  * `producer = ofp.s8`
* Assembles the metadata payload (no values, no keys).

### S8.4 Outbox / Queue (bounded)

* A bounded buffer for pointer events waiting to publish.
* Two reliability modes (profile-driven):

  * **Best-effort in-memory** queue (v0 simplest)
  * **Durable outbox** (later, if you really care about “at least once” pointer publication)
* Boundedness rules:

  * max queue depth
  * drop policy (`DROP_OLDEST` or `DROP_NEWEST`) with explicit counters

### S8.5 Publisher Adapter

* Publishes to `fp.bus.audit.v1` as a normal producer.
* Handles basic retries/backoff.
* Does not block serving (async).

### S8.6 Retry/Backoff & Circuit Breaker

* When publish failures spike:

  * backoff increases
  * circuit breaker can trip to “temporarily disabled”
* Exposes that state to S7/S6.

### S8.7 Health & Telemetry Emitter (IJ-18)

To S6:

* queue depth, backlog age
* publish success/failure rate
* drops, retries
* enabled/disabled state + reason

### S8.8 Control Surface (from S7)

* Enable/disable dynamically (profile change / ops control)
* Adjust rate limits / sampling rate
* Flush/drain on shutdown if desired (but never required for correctness)

---

## 5) The key loop S8 participates in (IL-5)

**S3/S5 → S8 enqueue → publish → S6 sees backlog/failures → S7 throttles/disables S8**

That’s the safety mechanism that keeps “audit hints” from ever harming the core projector/serve paths.

---

## 6) Failure posture (the most important part)

* If publishing fails: S8 retries within bounds, then drops (according to policy) and emits health signals.
* If S8 is down: **nothing else is allowed to change**. OFP continues serving/processing as normal.
* If S8 becomes overloaded: S7 may disable it; serving continues.

This preserves the non-decisionable / non-gating rule.

---

## 7) S8 non-joins (explicitly banned)

* S8 must not read from EB/Archive/T0 to “reconstruct” pointer content.
* S8 must not publish feature values or entity key lists.
* S8 must not be consumed as input for DF/OFP decisions.
* S8 must not couple pointer success to `get_features` success.

---

## USER: PAUSE FOR REFLECTION

Absolutely. Here’s the “pause snapshot” of what we’ve actually built — not in prose, but as a **designer’s mental compression** so I can’t drift and you can sanity-check the complexity before we go further.

---

## The complexity in one sentence

We didn’t just design “a feature store.” We designed a **deterministic, replay-explainable, environment-ladder-safe projection + serving system** whose *correctness* is defined by **basis tokens** (`input_basis`, `graph_version`), **event-time as-of semantics**, and **versioned meaning** (policy_rev + group_version), and whose *operability* is enforced by explicit stalls, rebuild epochs, and observable posture changes.

---

## Why it feels complex (and why it’s not accidental)

There are three independent axes that multiply each other:

### 1) **Time axis**

* Facts arrive out-of-order, duplicates exist, and “meaning time” is `ts_utc`.
* Serving must be **as-of** explicit time, not “latest”.
  This forces event-time indexing and anti-leakage discipline.

### 2) **Replay / determinism axis**

* EB offsets are the only universally meaningful progress truth.
* OFP must expose “what I had applied” as `input_basis` (exclusive-next offsets).
  This forces atomic checkpointing, idempotency, and coherent read views.

### 3) **Meaning/version axis**

* Feature meaning is versioned and singular (group_version + policy_rev).
* Offline training, online serving, and bundle requirements must align.
  This forces explicit definition activation, stable ordering, and provenance binding.

Each axis is individually manageable; the “depth” comes from *making them all true at once* without hidden assumptions.

---

## What we illuminated (the real shape)

### External to OFP (frozen outer network)

* **J7** EB→OFP (consume admitted facts)
* **J7b** OFP↔IEG (optional identity resolution; `graph_version`)
* **J8** DF→OFP (get_features as-of + provenance + hash)
* **Cfg-OFP** feature definitions profile → OFP
* **Obs-OFP** OFP → observability pipeline (feeds DL)
* **Optional** OFP → audit pointer topic (metadata only)

Plus the paths/loops (P1–P5, L1–L5) that make it production-real.

### Inside OFP (internal vertex network, now illuminated)

We ended up with **two planes + a spine + a governor**:

* **S1 Update Plane**: facts → mutations → T0 apply + checkpoints (truthful basis)
* **S3 Serve Plane**: request → as-of read → S5 provenance+hash → response
* **T0 Store**: state + checkpoints + coherence tokens + epochs
* **S5 Spine**: `input_basis`, freshness (event-time), canonicalization, snapshot hash
* **S4 Meaning authority**: policy_rev + group_version → active snapshot
* **S2 Identity**: resolve keys + propagate `graph_version` when IEG used
* **S7 Governor**: boot/readiness, policy activation, stall handling, rebuild epochs, posture control
* **S6 Visibility**: metrics/traces/boundary facts (stalls, rebuilds, activations) to make ops & DL possible
* **S8 Optional**: pointer emitter (metadata only, bounded, non-gating)

This is complex, but it’s also **modular**: each piece exists because a specific platform pin demands it.

---

## The “keystone laws” that tie it all together

These are the few laws I’m holding as the core of the whole design:

1. **Watermarks don’t lie**
   Checkpoint only advances if state effects are durable (or explicit no-op). Exclusive-next always.

2. **No hidden now**
   Serving uses explicit `as_of_time_utc` and event-time (`ts_utc`) for meaning/freshness.

3. **Versioned meaning is singular**
   Group_version + policy_rev define meaning. If meaning changes, version changes.

4. **Provenance completeness or no serve**
   No `feature_snapshot_hash` without `input_basis`, and `graph_version` must be recorded when IEG is used.

5. **Explicit failure is better than silent drift**
   Relevant-but-uninterpretable facts cause stall; rebuild is explicit and auditable; policy activation is an observable fact.

Those five laws are what prevent drift when Codex implements.

---

## Why this is still “minimal” (despite feeling big)

We did *not* explode into dozens of modules. We kept to:

* **8 subnetworks + 1 store**
* a clear mapping from each to a join/path/loop obligation
* explicit “non-joins” to prevent convenience edges

Most of the “extra” depth is simply **making production reality explicit** (stall, backpressure, rebuild, epoch swap, observability).

---

## What I’ll do to prevent drift going forward

As we go deeper (algorithms, storage schemas, caching details), I will constantly check:

* Does this change any of the keystone laws?
* Does it introduce a forbidden edge (non-join)?
* Does it make local/dev/prod semantics diverge (profile vs fork)?
* Does it weaken basis/provenance or allow silent skipping?

If yes, I’ll either reject it or require an explicit pinned decision.

---

