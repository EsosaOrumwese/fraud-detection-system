# Offline Feature Plane Design Authority

This file is a rough collection of design or brainstorm notes for the Offline Feature Plane. It views the whole platform as a network and expands open the offline feature plane's position in this network and illuminates it.

---

Locked. We’ll treat **OFS’s inner network as opaque for now**, and design its **outer role + obligations + interactions** in the platform graph. What I pin below becomes **authoritative** for OFS, but stays at **blueprint level** (not a full spec/contract). Everything is consistent with your pinned joins/rails and deployment shape.  

---

# OFS’s role in the platform network

## What OFS *is*

**Offline Feature Shadow (OFS)** is a **batch-plane “replay + reconstruction” job** that consumes the **admitted fact stream** (EB + Archive), applies **explicit as-of label semantics**, uses **version-locked feature definitions**, and outputs **reproducible training/eval datasets** plus (optionally) **parity evidence** against what the Online Feature Plane (OFP) served.  

## What OFS is *not*

* Not a serving plane. It never participates in real-time decisions.
* Not a writer of truth for events or labels (it reads them).
* Not a “scan the lake and build something” system — it operates only on **pinned inputs** and produces **pinned artifacts**.  

---

# OFS as a vertex: outer adjacency and authority boundaries

## Deployment-unit posture (pinned)

OFS runs as a **job** (scheduled/on-demand), not an always-on service. 

## What OFS reads (inbound joins)

### J14 — (Label Store + EB/Archive) → OFS

This is OFS’s primary input join.

**From EB/Archive (facts):**

* OFS reads **admitted events** from `fp.bus.traffic.v1` (within retention) and from **Archive** (beyond retention).
* Archive is treated as the **same logical stream as EB**: same `event_id`, same envelope semantics, same “ordering basis per partition.”  

**From Label Store (truth timelines):**

* Labels are **append-only timelines** with **effective_time** and **observed_time**.
* OFS must query labels using explicit **as-of rules** to prevent leakage.  

**Non-negotiable output of this join:**
OFS must **record the basis** of anything it builds:

* replay basis (offset ranges per partition, or time window *anchored to offsets*),
* label as-of boundary,
* feature definition versions used,
* any parity anchors. 

---

### Feature definitions / versions → OFS (anti-drift input)

OFS reads **feature definition profiles** (same authority source OFP uses) and must lock versions per build. Deployment mapping explicitly lists “feature definition profiles” as an OFS input. 

**Pin:** OFS is not allowed to use “latest by default” unless the build intent explicitly says so and it is recorded as part of the build provenance (so it’s reproducible).

---

### SR join surface (`sr/run_facts_view`) → OFS (pinned read)

Deployment mapping explicitly shows OFS reading `sr/run_facts_view` from object storage. 

**Why it exists (what OFS is allowed to use it for):**

* **ContextPins** for scoping (world/run joinability): `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`. 
* Optional **world/context surfaces**: if some offline features require static “world” context, OFS may only obtain those surfaces via SR-provided locators/receipts (by-ref, with PASS evidence). This stays consistent with “by-ref” and “no PASS → no read.”  

**Pin:** OFS must never “discover” engine/world artifacts by scanning. If it needs world context, SR’s join surface is the only start. 

---

### Optional parity anchor input (DLA/DF provenance → OFS)

Not required for the learning loop to function, but permitted if you want the “shadow twin” parity behavior.

* OFS may read decision/audit provenance that includes snapshot identifiers, `input_basis`, and the versions used online—so it can rebuild exactly that snapshot and compare.  

(Exact wiring can be “read audit records by-ref from object store” in the same way Case Workbench does; OFS doesn’t need to become a consumer of hot-path traffic to do this.) 

---

## What OFS writes (outbound joins)

### J15 — OFS → Model Factory (MF)

**What crosses the join:** **DatasetManifests + evidence** (by-ref pointers to materializations), not a dataframe handoff. 

**Pinned MF expectation:** MF treats DatasetManifests as **immutable inputs**; reproducibility depends on being able to re-resolve exactly those manifests later. 

---

### Object store — OFS artifact authority

Deployment mapping pins OFS writes:

* `ofs/...` dataset materializations
* `ofs/...` **DatasetManifest** (the authoritative output artifact family for training inputs) 

**Pin:** OFS is the authority for the meaning of `ofs/...` artifacts, and they must be durable (they’re part of the “platform memory” story for learning reproducibility). 

---

### Optional governance fact emission — OFS → `fp.bus.control.v1`

Deployment mapping allows an optional governance fact emission from OFS. 

**Pin:** Any backfill/rebuild that changes derived outputs is **never silent**; emitting a governance fact is the platform-native way to make it auditable.  

---

# How OFS operates (externally) — the “outer behavior” blueprint

## OFS is driven by Build Intents (not “run forever”)

Because OFS is a job, it runs in **invocations**. Each invocation is a **declared operation** with pinned inputs and pinned outputs.  

### The three externally-visible invocation families (v0)

These are not “schemas” yet — they’re the *conceptual kinds of work* OFS performs for the network:

1. **Dataset Build (learning/eval)**

* Inputs: replay basis + label as-of boundary + feature versions + dataset kind (per-event/per-entity/per-window).
* Output: DatasetManifest + artifact refs.

2. **Parity Rebuild (shadow twin)**

* Inputs: an online anchor (snapshot hash/ref + its `input_basis` + versions used).
* Output: parity result (MATCH/MISMATCH/UNCHECKABLE) + evidence by-ref.

3. **Forensic Snapshot Rebuild (audit support)**

* Inputs: a feature key + explicit as-of spec (+ versions).
* Output: rebuilt snapshot artifact + provenance (and optionally parity if an online target exists).

These align with what the platform says crosses J14/J15 (basis + as-of + versions + parity anchors + manifests). 

---

## Replay basis and “as-of” are *external obligations*, not internal choices

### Replay basis (hard law)

Any OFS output must be reproducible even after retention changes.
So every build must record an explicit replay basis:

* offset ranges per partition (preferred), **or**
* time window **anchored to offsets/checkpoints** (recorded mapping).  

### As-of labels (hard law)

OFS must be able to produce both:

* “what we knew then” (observed-time bounded), and
* “what we know now” (later labels included),
  without confusing them — therefore **the label as-of boundary must be explicit and recorded**.  

### Watermarks monotonic (hard law)

OFS never implies “history changed.” Late arrivals/backfills create new offsets; OFS rebuilds are new derived artifacts tied to an explicit basis.  

---

## Interaction posture with EB / Archive (what OFS must assume)

* OFS assumes at-least-once and duplicates are real (platform rail). It must be replay-safe and deterministic. 
* Events are canonical envelopes at the boundary (required fields are fixed). 
* Archive is accessed **by-ref and pinned** (no vague searching). 

---

## The OFS output posture (what others can rely on)

### DatasetManifest is the “unit of truth” for OFS outputs

A dataset is “real” only when its DatasetManifest exists and pins:

* replay basis (stream identities + offsets/checkpoints),
* label as-of boundary,
* join keys/entity scope,
* feature definition versions used,
* digests/refs to materializations,
* provenance (including pipeline/profile revs).  

### Publication rule (outer expectation)

OFS should behave like the engine does for immutability: publish artifacts **atomically** under an identity, and never silently overwrite. (If a rebuild is needed, it produces a **new** derived version with an auditable backfill declaration.)  

---

# Failure and “can’t prove it” posture (outer behavior)

OFS must never “half succeed” without making that explicit to downstream.

**Pinned rules for failure modes:**

* Missing history (retention boundary + archive gap) → build fails or produces an explicit “incomplete/UNCHECKABLE” outcome (but not a silent dataset).  
* Missing feature definition version → explicit failure (cannot drift to latest silently).
* Missing/late labels relative to as-of boundary → handled by the label as-of rules; the manifest must state which as-of posture was used. 

---

# What I’m pinning as the authoritative “outer contract” for OFS (v0)

1. **OFS is a job** invoked explicitly (scheduled/on-demand). 
2. OFS reads admitted events from **EB + Archive treated as one stream**; it records explicit replay basis. 
3. OFS reads labels only from **Label Store timelines** using explicit as-of semantics (effective vs observed). 
4. OFS uses **version-locked feature definitions**; no silent “latest.” 
5. OFS may read `sr/run_facts_view` for ContextPins and (if needed) by-ref world context surfaces with PASS evidence; no scanning.  
6. OFS outputs are authoritative only via **DatasetManifests + by-ref artifacts** in `ofs/...`.  
7. Backfills/rebuilds are **declared and auditable** (optional gov fact emission is allowed/encouraged).  

---

Yes — there are a few **OFS “meaning pins”** that are worth locking **before** we talk join-by-join, because they determine what the joins *must* carry and what downstream can safely assume. Your platform notes even call out three of these as “holes” that should be pinned to prevent drift. 

Here’s what I’m pinning now (authoritative for this brainstorm), while keeping OFS internally opaque.

## Pin 1 — What an OFS run *is* and what “done” means

**OFS is an invoked job** (scheduled/on-demand). Each invocation produces **immutable, by-ref artifacts** plus a single authoritative **DatasetManifest** (and optionally a ParityReport). There is no notion of “the current dataset” unless expressed as an explicit pointer elsewhere; OFS itself only publishes immutable outputs.  

**Why pin now:** it prevents later drift into “service-y” behavior and prevents MF from expecting a mutable table.

## Pin 2 — DatasetManifest semantics are the unit of truth

A dataset is only “real” when there is a **DatasetManifest** that pins, at minimum:

* **ReplayBasis** (offset/watermark vector, or a time window *resolved to offsets and recorded*)
* **LabelAsOfSpec** (explicit leakage boundary)
* **FeatureVersionSet** (the exact feature profile revision(s) used)
* **Scope** (what ContextPins / entities / event-types it covers)
* **Materializations** (refs/locators + content digests)
* **Policy/Profile revisions** that affect meaning (e.g., feature profile rev, any build policy rev)

This is explicitly called out in your platform map as something that must be pinned once so MF doesn’t drift from OFS. 

## Pin 3 — Feature-definition version authority and resolution

We must pin “where feature versions come from” because OFP + OFS + MF must agree.

**Pinned v0 decision:** Feature definitions live as a **versioned artifact family** (“feature definition profiles”), and every OFS build must cite an explicit `feature_profile_ref` (revision + digest). If a build says “use active,” that “active revision” must come from a single deterministic authority (policy/profile), and the resolved revision is recorded into the manifest so the build is still reproducible.  

(We’re not inventing a new component here; we’re pinning the *authority mechanism* as “versioned artifact + governed active pointer,” which your deployment/config notes already treat as the general pattern for outcome-affecting config.) 

## Pin 4 — ReplayBasis is offsets/watermarks, not “time” (time is a selector only)

**Pinned v0 decision:** OFS outputs are anchored on **offset/watermark basis**. Time windows may be used as a *request convenience*, but must be deterministically resolved to an offset basis and recorded. This matches the platform’s “watermark basis is the shared replay determinism hook.” 

## Pin 5 — Label “as-of” semantics are explicit and leakage-safe

**Pinned v0 decision:** Label inclusion for supervised datasets is governed by an explicit **observed-time cutoff** (“what we knew by T”), while the label’s **effective_time** governs *what it applies to* when aligning to events/entities. The manifest must record the as-of cutoff and the label-resolution rule (e.g., last-observed assertion per entity-case as-of). 

## Pin 6 — Archive vs EB retention boundary is a declared capability, not an assumption

**Pinned v0 decision:** OFS must support two modes:

* **Within-retention builds**: EB alone is sufficient.
* **Beyond-retention builds**: require Archive continuity.

If a build’s basis demands history beyond retention and Archive isn’t available, the run must end in an explicit, non-silent outcome (FAIL or UNCHECKABLE/INCOMPLETE depending on intent), and no “quietly partial” dataset is published as if complete.  

## Pin 7 — Parity is optional, but if attempted it has strict outcomes

Parity (shadow twin) is allowed, but only meaningful when anchored to an online provenance target (snapshot hash + input_basis + feature version set). Parity results are one of:

* **MATCH**
* **MISMATCH** (with evidence)
* **UNCHECKABLE** (missing anchor, missing history, version mismatch, etc.)

This matches your platform statement that OFS provides parity evidence vs online snapshot hash. 

---

### What we are *not* pinning yet (safe to leave for later)

* Storage format (Parquet/Delta/etc.), execution engine, performance strategy
* Exact hashing/canonicalization algorithms (only the requirement that they be deterministic and comparable when parity is claimed)

---

Below is the **complete production-shaped “outer graph” around OFS** while treating OFS itself as **opaque** (no internal modules yet). I’m listing **all joins/paths/loops that can exist** without violating your pinned platform network (J1–J16 + rails + deployment units).  

---

## 1) All direct joins that touch OFS (edge inventory)

### Required inbound joins (OFS reads)

**J14a — EB (`fp.bus.traffic.v1`) → OFS (within retention)**
OFS reads the **admitted fact stream** (canonical envelopes) for a declared basis/window.  

**J14b — Archive → OFS (beyond retention)**
Archive is the **long-horizon extension of the admitted fact stream**; OFS treats EB+Archive as one logical stream (same identity + ordering basis per partition).  

**J14c — Label Store (DB timelines) → OFS**
OFS reads labels via **as-of rules** (effective vs observed time); no “latest labels” joins.  

**J14d — Feature definition profiles (versioned artifacts) → OFS**
OFS must lock feature definition versions used for the build (anti-drift). (Authority is “feature definition profiles” as an input in the production map.)  

**J14e — SR join surface (`sr/run_facts_view` in object store) → OFS**
OFS reads run/world ContextPins and (if needed) by-ref world/context artifacts via SR’s join surface (no scanning).  

**J14f (optional, but production-real) — DLA exports/audit records → OFS**
Used only to **target parity** (“rebuild *the* snapshot that DF/OFP used”) and to import online provenance anchors (snapshot hash + input basis + versions). This is present as “DLA exports” feeding OFS in the learning loop diagram. 

---

### Required outbound joins (OFS writes)

**J15 — OFS → Model Factory**
What crosses is **DatasetManifests + evidence**, not “a dataframe.” MF treats these manifests as immutable inputs for reproducible training. 

**J15b — OFS → Object store (`ofs/...`)**
OFS publishes dataset materializations + the DatasetManifest by-ref under `ofs/...` (this is the substrate mapping). 

---

### Optional outbound joins (production/ops)

**J15c (optional) — OFS → `fp.bus.control.v1` (governance fact)**
OFS may emit a control-plane fact such as “dataset build completed”, “parity mismatch”, “backfill run completed”, etc. The production map explicitly allows optional gov facts from OFS.  

**J15d (always present operationally) — OFS → Obs/Gov pipeline (OTLP telemetry)**
Everything emits OTLP; OFS must emit metrics/traces/logs for rebuild latency, parity rates, mismatch reasons, etc. 

---

### Control-plane trigger join (how OFS starts)

**J0 (implicit but production-required) — Run/Operate → OFS (job trigger / build intent)**
OFS is an on-demand/scheduled **job unit** triggered explicitly by the orchestrator plane; backfills are also explicit jobs under Run/Operate.  

---

## 2) “Paths” through the platform that include OFS (end-to-end routes)

These are **not new joins**—just the common **production routes** that traverse the joins above.

### Path P1 — Main learning loop (the big one)

```
EB/Archive + Label Store (+ optional DLA exports)
  → OFS
  → MF
  → Registry (bundle lifecycle / ACTIVE)
  → DF uses active bundle
  → decisions/actions happen (hot path)
  → cases/labels accumulate
  → (back to) Label Store
  → (back to) OFS
```

This loop is explicitly described as the “Learning + evolution” flow. 

### Path P2 — Parity loop (shadow twin validation loop)

```
OFP/DF provenance captured in DLA
  → (DLA export anchors)
  → OFS rebuild same basis+versions
  → ParityResult (MATCH/MISMATCH/UNCHECKABLE)
  → (optional) governance fact + observability
  → Run/Operate triggers corrective backfill / feature fix / rollback decisions
```

J14 describes parity anchors; the learning loop calls out parity evidence vs online snapshot hash.  

### Path P3 — Retention horizon path (when training window exceeds EB retention)

```
Retention policy + Archive completeness
  → determines whether OFS can build requested basis
  → OFS either builds (using Archive) or produces explicit INCOMPLETE/UNCHECKABLE outcome
```

Archive is explicitly the long-horizon extension that makes offline rebuilds possible, and access is pinned “by-ref” with declared bases. 

### Path P4 — Backfill/rebuild path (derived artifacts only)

```
Run/Operate declares backfill scope+basis
  → triggers OFS rebuild (new manifests/artifacts; no silent overwrite)
  → triggers MF retrain (optional)
  → Registry promotion/rollback (auditable)
```

Backfills are pinned as explicit, scoped, auditable operations that regenerate derived artifacts (including offline datasets/manifests).  

---

## 3) “Loops” that exist in production (cycles involving OFS)

### Loop L1 — Model improvement feedback cycle (continuous)

`(EB/Archive + Labels) → OFS → MF → Registry → DF → (new decisions/events) → … → Labels → (back to OFS)` 

### Loop L2 — Governance/ops correction cycle

`Parity mismatch / drift evidence → gov fact + obs → Run/Operate backfill → OFS rebuild → (new evidence)`  

### Loop L3 — “Dataset identity / immutability” self-loop (via object store)

Even with OFS opaque, production reality includes:
`OFS reads prior manifests/artifacts (by identity) → decides “already exists / supersedes / new build” → writes new immutable artifacts`
This is the practical loop that enforces *immutability + non-silent overwrite* (without needing OFS to be a mutable service). 

---

## 4) Compact opaque-vertex network sketch (OFS-centered)

```
                     (optional) fp.bus.control.v1
                ┌───────────────────────▲──────────────────────┐
                │                       │                      │
Run/Operate ────┼── trigger/job intent ─┼── OFS (opaque) ───────┼──► Object store: ofs/… (manifests + mats)
                │                       │                      │
EB fp.bus.traffic.v1 ──────────────────►│                      ├──► Model Factory (consumes manifests)
Archive (beyond retention) ────────────►│                      │
Label Store (as-of timelines) ─────────►│                      │
SR run_facts_view (context pins/refs) ─►│                      │
DLA exports (optional parity anchors) ─►│                      │
Obs/Gov pipeline (OTLP) ◄───────────────┴──────────────────────┘
```

(Every arrow above corresponds to a join pinned by J14/J15 + the production substrate map.)  

---

### Expansion order for **OFS** (opaque vertex)

#### A) Joins (edges touching OFS)

1. **Run/Operate → OFS** (job trigger / build–backfill intent) 
2. **SR `sr/run_facts_view` (object) → OFS** (ContextPins + by-ref run/world context if needed) 
3. **Feature definition profiles → OFS** (version-locked feature set input) 
4. **EB `fp.bus.traffic.v1` → OFS** (within-retention admitted fact replay) 
5. **Archive → OFS** (beyond-retention continuation of the same fact stream) 
6. **Label Store → OFS** (leakage-safe as-of label timelines) 
7. **(Optional) DLA exports/provenance anchors → OFS** (parity rebuild targets) 
8. **OFS → Object store `ofs/...`** (materializations + DatasetManifest) 
9. **OFS → Model Factory** (DatasetManifests + evidence handoff) 
10. **(Optional) OFS → `fp.bus.control.v1`** (governance facts) 
11. **OFS → Obs/Gov pipeline (OTLP)** (telemetry) 

#### B) Paths (end-to-end routes that include OFS)

P1) **Learning route:** (EB/Archive + Label Store) → OFS → MF → Registry → DF → … → Label Store → OFS
P2) **Parity route:** (OFP/DF provenance via DLA) → OFS rebuild → ParityResult → ops/governance actions 
P3) **Retention/Archive route:** retention boundary forces EB-only vs EB+Archive basis; gaps yield explicit incomplete/UN-CHECKABLE posture
P4) **Backfill/rebuild route:** Run/Operate declares backfill → OFS rebuild (new manifests) → MF retrain → Registry promote/rollback

#### C) Loops (cycles involving OFS)

L1) **Continuous learning feedback loop:** P1 closed-loop 
L2) **Governance correction loop:** P2 + P4 closed-loop 
L3) **Immutability/idempotency loop:** OFS outputs (prior manifests/artifacts) become referenced inputs for future OFS decisions (no silent overwrite)

---

Absolutely — expanding **A1–A4** as **production joins** while keeping **OFS opaque** (we’re only pinning *outer handshake meaning* + obligations).

---

# A1) Run/Operate → OFS

**(job trigger / build–backfill intent)**

### What this join *is for*

Run/Operate is the platform’s **execution fabric + substrate**, not a source of domain truth. Its job is to **trigger OFS runs**, provide the **durable substrate for by-ref artifacts**, and ensure any outcome-affecting operational act is **explicit + auditable**.  

### Authority boundary (hard pin)

* **Run/Operate may schedule/trigger and provide config/secrets/storage**, but it **must not decide what is true** about events, labels, runs, or bundles. Those truths live in the planes: SR readiness, EB facts, Label Store, Registry, etc. 
* **Run/Operate must not introduce hidden nondeterminism** (no “silent retries that change meaning”, no implicit “now” unless captured as an explicit input pin). 

### What crosses the join (conceptual payload: “BuildIntent”)

Run/Operate triggers OFS with a **BuildIntent** that must be *fully pin-able*. Minimum fields, conceptually:

1. **request_id** (idempotency handle for the job invocation)
2. **build_kind**: `dataset_build | parity_rebuild | forensic_rebuild | backfill_rebuild`
3. **scope**:

   * optional `ContextPins` filter (`manifest_fingerprint, parameter_hash, scenario_id, run_id`) if you’re building for a particular world/run
   * optional entity/event_type selectors (if building a subset)
4. **replay_selector**: either

   * an **offset/watermark basis**, or
   * a **time window** that must be deterministically resolved to offsets and recorded (time is allowed only as a selector, not the final basis) 
5. **label_as_of_spec** (explicit as-of boundary; never implicit “now”) 
6. **feature_profile_ref** (or a deterministic rule to resolve one; but the resolved ref must be recorded) 
7. **output_identity hint** (where results land, e.g., `ofs/…` namespace + dataset key)

### What OFS owes back across the join (at outer level)

Even though OFS is “just a job”, a production platform needs explicit lifecycle visibility:

* **Run record / status**: started / completed / failed (can be an object record, DB entry, and/or a governance event — implementation is open)
* **Stable output pointer(s)**: DatasetManifest ref(s) and/or ParityReport ref(s) once complete
* **Failure posture**: if the intent cannot be satisfied (missing history, missing feature versions, etc.), OFS must **fail closed** (no “quiet partial dataset published as complete”). This aligns with the platform’s explicitness + auditability laws. 

### Idempotency + replay safety (pin)

* `request_id` is the **job idempotency key**. If Run/Operate retries the same intent, OFS must not create semantically different outputs without producing a new declared intent (e.g., new request_id or explicit “supersedes”). This is part of “no hidden nondeterminism / no silent change.”  
* Backfills/rebuilds are explicitly called out as Run/Operate responsibilities and must be **auditable governance acts**, never silent.  

---

# A2) SR `sr/run_facts_view` (object) → OFS

**(ContextPins + by-ref run/world context if needed)**

### Why this join exists

Your platform pins SR as the system-of-record for **run identity + readiness + the downstream join surface**, and `run_facts_view` is explicitly the **bridge artifact** that points downstream to authoritative outputs/evidence by-ref.  
And the deployment mapping explicitly lists OFS reading `sr/run_facts_view` from the object store. 

### What OFS is allowed to use `run_facts_view` for (pin)

1. **ContextPins resolution**
   If OFS is building anything that claims run/world joinability, `ContextPins` must be recoverable and consistent (`manifest_fingerprint, parameter_hash, scenario_id, run_id`). 

2. **By-ref world/context surfaces** (optional, but sometimes necessary)
   If an offline feature needs static “world context” (e.g., merchant/location surfaces), OFS may read those only **by-ref** using locators/pointers embedded in `run_facts_view`, and only when the required PASS evidence exists (“no PASS → no read”).  

3. **Joinability discipline**
   OFS must not “scan engine/ or sr/ for whatever looks latest”. The only legitimate starting point is READY → `run_facts_view` → refs.  

### What `run_facts_view` must contain (minimum needed for OFS)

We don’t need the exact schema here; but to satisfy the platform laws, the view must provide at least:

* `ContextPins`
* **artifact refs/locators** for any world/context surfaces OFS is allowed to consume
* **PASS evidence pointers** (gate receipts or equivalent) when those surfaces are gated
* enough metadata to support “this ref is admissible” checks (digest posture when present is fail-closed on mismatch)  

### Failure posture (pin)

* If a BuildIntent references a run, but `run_facts_view` is missing or not joinable, OFS should fail closed (or declare UNCHECKABLE if the intent is explicitly “forensic/attempt best effort”).
* If `run_facts_view` references gated artifacts without PASS evidence, OFS must treat them as **inadmissible** (platform-wide gating law). 

---

# A3) Feature definition profiles → OFS

**(version-locked feature set input)**

### Why this join must be pinned early

Your blueprint explicitly calls feature version authority a “minimal hole” that must be pinned so **OFP + OFS + MF don’t drift**. 
And your production deployment mapping already treats “feature definition profiles” as a first-class input to OFS. 

### Authority model (pin)

* Feature definitions live as **versioned artifacts** (think “profiles/feature_definitions/…”) under the broader “profiles/” posture in your substrate map.  
* OFS must never use “latest by default” unless the BuildIntent explicitly requests a deterministic resolver rule, and the **resolved version ref** is recorded into outputs (so the run is reproducible).  

### What crosses the join (conceptual)

OFS needs either:

* **Explicit profile ref**: `{profile_id, revision, digest}` (best), or
* **Deterministic resolution rule**: e.g., “use ACTIVE profile for scope S as of governance activation G” — but OFS must **materialize the resolved ref** into its manifest.

### Special case: parity rebuilds (pin)

If the BuildIntent is a parity rebuild tied to an online decision/snapshot, then:

* the feature profile/version set must match what online recorded in provenance (or OFS must return UNCHECKABLE/MISMATCH-on-version, not silently substitute).
  This follows your “parity must be provable; no silent mutation” posture.  

### Failure posture (pin)

* Missing profile revision/digest → fail closed (or UNCHECKABLE if intent explicitly allows “best effort”).
* Profile resolves differently across retries without being recorded → **disallowed** (that would be hidden nondeterminism). 

---

# A4) EB `fp.bus.traffic.v1` → OFS

**(within-retention admitted fact replay)**

### What this join is

OFS consumes the **primary admitted fact log** for history within retention. The topic name and role are pinned in your deployment substrate layout. 

### What is admissible on this join (rails)

* Only **admitted traffic** is on the bus, and it must be representable as the **Canonical Event Envelope**. 
* EB itself does not validate meaning — it provides durable append, partitions, and offsets (replay semantics). 

### The shape OFS reads (outer guarantee)

OFS reads **CanonicalEventEnvelope** records with required fields `{event_id, event_type, ts_utc, manifest_fingerprint}` and optional pins `{parameter_hash, scenario_id, run_id, seed}` + trace/provenance.  

### Replay basis (hard pin)

The only universal progress token is **EB coordinates**: `(stream, partition, offset)` with exclusive-next meaning (watermark vector). This is the shared determinism hook for rebuild/provenance.  

So on this join, OFS must operate in one of two modes:

1. **Offset-basis replay (preferred)**: BuildIntent provides `{partition → [from_offset, to_offset)}`
2. **Time selector replay (allowed)**: BuildIntent provides `{from_time_utc, to_time_utc}`, but OFS must resolve to offsets deterministically and record the resolved basis into its manifest.

### Ordering + duplicates (production reality)

* EB guarantees **order within a partition by offset**, not a total order across partitions. OFS must not assume global ordering. 
* At-least-once is assumed; duplicates exist. OFS must be replay-safe and deterministic under duplicates/retries (end-to-end idempotency rail). 

### Retention boundary interaction (pin, even though Archive is A5)

For A4 specifically: the build is “within retention.”
Therefore OFS must detect when the requested replay basis extends earlier than the earliest retained offsets; if so, it must either:

* **fail closed**, or
* require the build to switch to the Archive join (A5) and declare the build as such.
  No silent partial history. This is consistent with the platform’s retention/archive hole being explicitly pinned as something to make visible. 

### Partitioning note (important for determinism)

IG stamps deterministic `partition_key` when admitting events; EB enforces partition+offset semantics. This matters because OFS manifests/provenance will often be per-partition. 

---

## The key “bridge pins” across A1–A4 (so we don’t drift later)

* A1 **must** supply an intent that can be fully pinned (no hidden nondeterminism). 
* A2 **must** be the only lawful way to bring in world/context surfaces (by-ref + PASS).  
* A3 **must** be version-locked and recorded (feature authority hole closed). 
* A4 **must** be offset-basis truth (watermarks), canonical envelope only.  

---

Absolutely — here are **A5–A8** expanded as **production joins** while keeping **OFS opaque**. I’m going to be explicit about **what the join means**, **what is allowed**, **what must be recorded**, and **how it fails**. Everything below obeys your pinned “archive/retention + as-of + by-ref + manifests” laws.  

---

# A5) Archive → OFS

**(beyond-retention continuation of the same fact stream)**

## Why this join exists (production purpose)

This join exists so OFS can do **reproducible rebuilds and training windows that exceed EB retention**—without changing semantics. Retention length is an environment knob; **replay semantics must not change**. 

## Authority boundary (hard pins)

1. **Archive is not a second truth.** It is the **long-horizon extension** of the admitted event stream: same logical events, same `event_id`, same canonical envelope meaning.  
2. Consumers (including OFS) replay from Archive **as if it were EB** and **must record the replay basis used**. 
3. Archive access is **by-ref and pinned**, never “search vaguely.”  

## What crosses the join (conceptual)

Archive must be able to supply the admitted stream in a way that supports the platform’s basis law:

### Minimum “read contract” (conceptual, not schema)

* **Stream identity**: `fp.bus.traffic.v1` logical stream (same as EB) 
* **Selection**: by **offset ranges per partition** (preferred) or **time windows anchored to offsets via checkpoints/watermarks** (allowed) 
* **Records**: canonical envelopes preserving event identity and semantics 

### What OFS must record whenever it uses Archive

OFS must pin, in its outputs (DatasetManifest / ParityReport):

* which stream(s) were replayed,
* the **explicit replay basis** (offset ranges/checkpoints),
* the fact that Archive contributed (vs EB only),
* and any **archive segment/manifest refs** used to prove completeness.  

## The key production subtlety: offsets beyond retention

Your platform pins replay determinism to **offset/watermark basis**. That implies a v0 design decision for Archive:

### Designer pin (v0): Archive must preserve EB coordinates

To keep “basis by offsets” meaningful beyond retention, Archive needs to preserve (or reconstruct deterministically) the original **(partition, offset)** coordinates for events, or provide a deterministic mapping via checkpoints.

* Otherwise, you can’t honestly say “this dataset was built from offsets X→Y” once EB has expired.
* This also makes overlap handling (below) deterministic.

This matches the “recorded checkpoints/watermarks” posture you’ve pinned. 

## Overlap handling (EB + Archive both contain some of the same history)

In production, you’ll often have overlap because Archive hydration may lag or be redundant.

### Designer pin (v0): EB is authoritative for the hot window; Archive for the cold window

* If a build basis includes offsets that are still in EB, OFS may read them from EB; if those offsets are only in Archive, OFS reads them from Archive.
* If both sources supply the same events, dedupe is by **event identity** (same `event_id`) not by “which file it came from.” 

## Completeness & verifiability

Archive hydration can be continuous or scheduled — but must be **verifiable** for a declared window. OFS must not trust Archive blindly for a basis if completeness can’t be established. 

### Failure posture (pin)

If BuildIntent requires history beyond retention and:

* Archive is missing segments / cannot prove completeness for the declared basis → OFS must **fail closed** or return **explicit INCOMPLETE/UNCHECKABLE** (depending on build kind), but must not publish a “complete” dataset manifest silently.  

---

# A6) Label Store → OFS

**(leakage-safe as-of label timelines)**

## Why this join exists (production purpose)

Learning must consume **labels as truth** without leaking “future knowledge” into past training/eval windows. That’s only possible if labels are stored as **timelines** and queried **as-of**. 

## Authority boundary (hard pins)

1. **Label Store is the only label truth used for learning.** OFS must not infer labels from outcomes/decisions/heuristics. 
2. Labels are **append-only timelines**, not single mutable values. 
3. Training joins are **as-of by rule** (leakage-safe):

   * events/features up to boundary,
   * labels as-of the same boundary (by observed_time),
   * effective_time governs when a label applies.  
4. Corrections are new assertions; OFS must be able to produce “what we knew then” vs “what we know now.” 

## What crosses the join (conceptual)

### Minimum label “read shape”

For any subject (event/entity/flow), Label Store can supply a set of label assertions with:

* **subject identity**
* label value (+ optional confidence)
* provenance
* **effective_time**
* **observed_time**
* supersedes/override semantics (implicit by timeline interpretation, not destructive updates)  

### OFS must provide an explicit LabelAsOfSpec

OFS must read labels with an explicit “as-of boundary” and must record it into outputs:

* the **observed_time cutoff** (what was known by T)
* the label-resolution rule (e.g., “latest observed assertion as-of, interpreted by effective_time”)  

## Two label postures OFS must support (pin)

1. **Historical / honest evaluation**: labels **observed as-of T** (no future knowledge) 
2. **Improved training / hindsight**: labels **observed after T included** (explicitly declared as “know-now”) 

They must never be conflated; the DatasetManifest must state which posture was used. 

## Failure posture (pin)

* If Label Store cannot resolve labels for a declared scope/as-of (schema mismatch, missing subject mapping, etc.), OFS must not silently “drop labels and continue” unless the BuildIntent explicitly declares an unlabeled dataset kind. The manifest must reflect reality. 

---

# A7) Optional DLA exports / provenance anchors → OFS

**(parity rebuild targets)**

## Why this join exists (production purpose)

This join exists to make the “shadow” part real: **rebuild what the online system actually used** and produce parity evidence.

Your platform pins that the audit record must contain by-ref pointers to:

* event reference basis (EB coords / watermark basis),
* `feature_snapshot_hash` + `input_basis`,
* `graph_version` (if used),
* degrade posture,
* resolved bundle ref,
* actions, etc. 

That is exactly what OFS needs to target parity precisely (instead of guessing “around that time”). 

## Authority boundary (hard pins)

1. DLA is append-only; corrections are via **supersedes chain** (no overwrites). 
2. OFS uses DLA records as **anchors**, not as an alternate event/label truth store. The event truth is still EB/Archive; label truth is Label Store. 

## What crosses the join (conceptual “ParityAnchor”)

A DLA export/anchor sufficient for parity contains:

* `decision_id` (or audit record id)
* `ContextPins`
* **input basis**: watermark vector / EB basis for “what was applied”
* `feature_snapshot_hash` (or ref) plus the feature version set used
* `graph_version` (if needed for feature parity)
* degrade posture id (so OFS can assert it rebuilt under the same constraints if relevant)
* bundle ref (not required for feature parity itself, but often useful for full decision reproduction)  

## How OFS uses it (still outer behavior)

* OFS takes the anchor and sets:

  * replay basis = the anchor’s `input_basis`
  * feature versions = the versions recorded in provenance
  * parity target = `feature_snapshot_hash` (and/or snapshot ref)
* Then it rebuilds and produces:

  * MATCH / MISMATCH / UNCHECKABLE + evidence (basis + versions used + mismatch fields list).
    (UNCHECKABLE is mandatory when inputs are missing; no pretending.)  

## Failure posture (pin)

If the DLA record is incomplete (missing basis / missing snapshot hash / missing version ref), OFS must return **UNCHECKABLE** rather than inventing defaults. 

---

# A8) OFS → Object store `ofs/...`

**(materializations + DatasetManifest)**

## Why this join exists (production purpose)

This is how OFS publishes durable, reproducible outputs **by-ref**. In your substrate layout, OFS owns `ofs/` and publishes dataset materializations plus the DatasetManifest that pins meaning.  

## Authority boundary (hard pins)

1. OFS is authoritative for the meaning of objects under `ofs/…` (they are part of the learning reproducibility story). 
2. Outputs are **immutable** (no silent overwrite); rebuilds/backfills produce new derived artifacts and are declared/auditable.  
3. **DatasetManifest is the unit of truth** for training inputs.  

## What OFS writes (artifact families)

At minimum, OFS publishes:

### 1) Dataset materializations

* actual dataset files (format open)
* optional intermediate aggregates (format open)
* optional index files for consumers (open)

### 2) DatasetManifest (authoritative)

Must pin enough to reproduce:

* replay basis (streams + offsets/checkpoints),
* label as-of boundary,
* join keys + entity scope,
* feature definition versions used,
* digests/refs to the materializations,
* provenance (pipeline/config version). 

### 3) Optional parity artifacts

* ParityReport: MATCH/MISMATCH/UNCHECKABLE + evidence by-ref (useful even if not routed anywhere else)

## Publication semantics (pin)

### Atomic publish rule

A dataset is not “published” until the DatasetManifest exists and points to fully written materializations. This prevents partial visibility.

### Deterministic naming/idempotency (v0 pin)

OFS must support idempotent retries for the *same* BuildIntent:

* Either by writing to a deterministic `build_id` derived from (intent pins + request_id), or
* by content-addressing the manifest/artifacts (digest-based)
  Implementation stays open, but the **behavior** is pinned: retries don’t create semantically different “new datasets” silently.  

## How this join supports MF cleanly

MF should consume OFS outputs by reading the DatasetManifest ref (J15) and then resolving the referenced `ofs/...` objects. That keeps “by-ref is the default truth transport” consistent across the platform.  

## Failure posture (pin)

* If a run fails, OFS must not publish a “success-shaped” DatasetManifest.
* If it publishes an incomplete/UNCHECKABLE artifact (allowed for parity/forensics), that must be explicit in the artifact and must not masquerade as a normal training dataset. 

---

## The one tight cross-join pin that matters most (A5–A8)

**Everything OFS publishes must be reproducible from:**

* EB/Archive admitted fact stream basis,
* Label Store timelines + as-of boundary,
* feature definition versions,
  and those pins must be carried in the DatasetManifest (and parity evidence if used).  

---

Great — expanding **A9–A11** as **production joins**, with **OFS still opaque** (we’re only pinning the outer handshake meaning + obligations + failure/idempotency posture).  

---

# A9) OFS → Model Factory

**(DatasetManifests + evidence handoff)**

## What this join *is for*

This join is the **only legitimate bridge** from “replay + reconstruct” to “train + evaluate + publish bundles.” OFS outputs are the **truth for training inputs**, and MF is the **truth for training runs + eval evidence + produced bundles**.  

## What crosses the join (the authoritative payload)

### 1) **DatasetManifest (non-negotiable unit)**

Per your pinned J15: OFS must hand MF a **DatasetManifest** that pins (at minimum):

* dataset identity
* time window / **as-of boundaries**
* join keys + entity scoping
* **feature group versions** (or “feature definition versions”)
* digests/refs to materializations
* provenance (sources + transformations) 

### 2) **Evidence (supporting, but still by-ref)**

“Evidence” is intentionally broad in your notes; production-real evidence commonly includes:

* basic completeness/accounting (counts, partition ranges, coverage stats)
* label-join diagnostics (label coverage, leakage posture declaration)
* parity artifacts (if this dataset is tied to an online target)
* schema version + compatibility declarations (so MF can fail fast, not guess)

**Pin:** Evidence is always **by-ref** (object refs/digests), never embedded bulk.  

## How MF “consumes” (what MF is allowed to assume)

MF is allowed to assume:

* the DatasetManifest is **immutable** and reproducible (it references immutable objects under `ofs/...`) 
* the manifest declares enough to recreate the *meaning* of the dataset (basis/as-of/versions/scope) without MF scanning anything else 
* MF should not treat datasets as “latest”; it should only train from **explicit manifest refs** given by orchestration or a declared control fact (see A10).  

## Notification / triggering posture (this is the drift point to pin)

There are two production-valid ways MF learns “a manifest exists”:

1. **Orchestrated handoff (preferred v0):** Run/Operate triggers MF with an explicit `dataset_manifest_ref`.
2. **Evented discovery (optional):** OFS emits a control fact “dataset published” carrying the manifest ref; MF subscribes and decides whether to train.

**My v0 pin (authoritative):** **Orchestrated handoff is primary.** Control facts may exist, but MF training must still be invoked with explicit pinned refs (no autonomous “train on whatever arrives” in v0). This matches your “by-ref default truth transport” and “no scanning latest” rails.  

## Idempotency + duplicate posture (outer-law)

* A DatasetManifest should have a stable **dataset_id** (or stable identity tuple) such that MF can recognize duplicates and avoid “double training by accident.” (Exact formatting is implementer choice; stability is the design law.) 
* MF may still re-train intentionally (for hyperparam changes etc.), but that becomes a new MF run record/evidence, not a new meaning for the dataset. 

## Failure posture (outer-law)

* If MF cannot satisfy compatibility (missing feature versions, schema mismatch, missing referenced objects), MF must **fail closed** and write its own run evidence as a failure outcome; it must not “best effort” train on partial truth. This is aligned with your platform’s “unknown/unsupported versions never silently flow” posture.  

---

# A10) (Optional) OFS → `fp.bus.control.v1`

**(governance facts)**

## What this join *is for*

This join exists to make offline rebuilds **auditable and operationally visible**, without turning OFS into a hot-path participant. Your deployment map explicitly allows OFS to emit optional governance facts to `fp.bus.control.v1`.  

## What *kind* of facts belong on control bus (pin)

Control bus is **low volume**, high importance. It carries “facts about operations and governance,” not event traffic. 

For OFS, the production-ready control facts are:

1. **DatasetPublished**

* emitted when a DatasetManifest is atomically published
* payload includes: `dataset_id`, `dataset_manifest_ref`, summary pins (`ContextPins` if applicable, replay basis summary, as-of, feature_profile_ref), and `request_id/build_id` for correlation

2. **DatasetBuildFailed**

* emitted when a build intent fails closed
* includes: `request_id/build_id`, failure class (missing history / missing profile / archive gap / etc.), plus optional evidence ref

3. **BackfillDeclared / BackfillCompleted**

* only when the run is explicitly a backfill/rebuild operation
* includes: scope/basis/what is being superseded, and refs to new manifests

4. **ParityResult**

* only if parity was requested/attempted
* includes: MATCH/MISMATCH/UNCHECKABLE + anchor refs + evidence ref

These are consistent with your “governance facts…never silent” posture (backfills, activations, lifecycle changes).  

## Envelope posture (pin)

Even control facts should still obey your platform’s “bus boundary shape” discipline: minimal stable envelope, payload versioned by `event_type`/`schema_version`. (Whether you literally use the same canonical envelope schema for control bus is an implementation detail; the **discipline** is not.)  

## Idempotency posture (pin)

Governance facts must be idempotent:

* keyed by `request_id/build_id` + fact type
* duplicates are tolerated and do not create new meaning

This is mandatory in an at-least-once world.  

## What this join must *not* become

* Not a “dataset transport.” The manifest ref is the bridge; the bus is just the announcement.
* Not a replacement for Run/Operate governance indexing (which may also write `gov/...`). OFS may emit, but governance truth is still governed holistically by Run/Operate.  

---

# A11) OFS → Obs/Gov pipeline (OTLP)

**(telemetry)**

## What this join *is for*

Observability is not domain truth, but it’s required for safe ops, and your deployment notes pin **OTLP everywhere** with a centralized OTel pipeline.  

OFS is a batch unit, so telemetry is what gives you:

* “did it run?”
* “did it build the right window?”
* “are parity mismatches spiking?”
* “are archive gaps breaking training?”

## The minimum telemetry “contract” OFS must emit (pin)

### Traces (per build invocation)

Every OFS invocation should emit a trace rooted at a stable operation id:

* `request_id` / `build_id`
* linked to any `dataset_id` produced
* optional linkage to `decision_id` when parity rebuilds are tied to audit anchors

### Metrics (golden signals for OFS)

At minimum:

* **job_duration_seconds** (by build_kind)
* **events_replayed_total** (and per stream/partition summaries)
* **replay_lag / basis_span** (how big the basis is; helps spot runaway windows)
* **archive_used_boolean** + **archive_gap_detected_boolean**
* **label_coverage_ratio** / label join rates (helps detect label store issues)
* **dataset_publish_success_total / failure_total**
* **parity_match_total / mismatch_total / uncheckable_total** + mismatch categories (if parity enabled)

### Logs (structured, correlation-friendly)

* start/finish records containing the pinned input summary (basis/as-of/feature profile ref) and output refs (manifest ref)
* failure logs carrying explicit error class + evidence refs

This aligns with your “corridor checks + golden signals” observability posture.  

## Correlation standards (pin)

To keep cross-plane debugging sane, OFS telemetry must include:

* `ContextPins` when the build is run/world scoped
* `request_id/build_id`
* `dataset_id` and `dataset_manifest_ref` (once known)
* `feature_profile_ref` / revision
* `as_of_time_utc` and basis summary (offset vector hash or window digest)

This makes OFS outputs joinable to MF/Registry/DF provenance later without inventing ad-hoc correlation.  

---

## The “tight” v0 pins across A9–A11

1. **MF consumes DatasetManifests (by-ref) — not tables — and training is triggered with explicit manifest refs (orchestrated primary).** 
2. **OFS may emit governance facts to `fp.bus.control.v1`, but those facts are announcements + audit hooks, not transports.** 
3. **OTLP everywhere: OFS must emit trace/metric/log signals keyed by request/build + dataset identity to keep the learning loop debuggable.** 

---

Got you — here’s **B: P1–P4** expanded as **production end-to-end routes** (still in blueprint/brainstorm mode, and still treating **OFS as opaque**). I’m going to spell out: **what each path is for, what flows, what gets pinned, and where the hard decision points are**, so there are no hidden assumptions.  

---

# P1) Learning route

**(EB/Archive + Label Store) → OFS → MF → Registry → DF → … → Label Store → OFS**

## Purpose

This is the **continuous learning + evolution loop**: the platform produces admitted facts and late human truth; OFS turns those into pinned datasets; MF trains and produces bundles; Registry governs activation; DF consumes active bundle deterministically; decisions produce more cases/labels; loop repeats.  

## Production route (step-by-step)

### 1) Facts accumulate on the admitted stream

* Business traffic is admitted to the bus as **CanonicalEventEnvelope**. 
* Consumers treat **offset/watermark vectors** as the universal “what was applied” tokens (replay determinism).  

**Pinned outcome:** The learning loop never trains on “some past”; it trains on a **declared replay basis** (offsets/checkpoints). 

### 2) Human truth accumulates as append-only timelines

* Case Workbench emits label assertions into Label Store, as **append-only timelines** with effective vs observed time. 
* “As-of” is the leakage safety mechanism: “what we knew then” vs “what we know now” must be constructible without confusion.  

### 3) OFS builds pinned training/eval datasets

OFS reads:

* admitted stream history (EB within retention, Archive beyond), and
* labels with explicit as-of semantics.  

**OFS outputs the bridge artifact:** a **DatasetManifest** that pins:

* replay basis (streams + offsets/checkpoints),
* label as-of boundary (effective/observed posture),
* join keys + entity scope,
* feature definition versions,
* digests/refs to materializations,
* provenance (pipeline/config). 

> This is not optional paperwork — it’s the unit of reproducibility in the learning route. 

### 4) MF trains from manifests, produces evidence + bundle

* MF treats DatasetManifests as **immutable inputs**; training is reproducible only if the exact manifests can be re-resolved later. 
* MF publishes a **bundle** plus training provenance and evaluation evidence for promotion. 

### 5) Registry governs activation (promotion/rollback)

* Registry is the **only authority** for “ACTIVE,” and promotion/rollback is auditable truth. 
* Compatibility metadata must be part of what crosses MF→Registry so DF can enforce safe resolution later.  

### 6) DF resolves ACTIVE bundle deterministically and records provenance

* DF resolves the active bundle deterministically and must record the resolved bundle ref + compatibility basis in decision provenance. 
* DF consumes OFP snapshots and must record the bundle used, feature versions used, and degrade posture.  

### 7) Actions → cases → labels → back into Label Store

* Decisions/actions create outcomes, cases evolve, and labels arrive late and get corrected (append-only).  
* That updated label timeline feeds the next OFS run.

## The key “decision points” in P1 (what operators/governance choose)

1. **Dataset intent selection:** which scope/window/basis? (offset basis preferred) 
2. **As-of posture:** “knew-then” vs “know-now” (must be explicit) 
3. **Feature version set:** explicit or deterministically resolved and recorded 
4. **Activation:** Registry promotion/rollback (governed) 

---

# P2) Parity route

**(OFP/DF provenance via DLA) → OFS rebuild → ParityResult → ops/governance actions**

## Purpose

This is the **shadow-twin integrity loop**: prove that “offline rebuild under the same basis + versions produces the same snapshot hash,” or else surface controlled, auditable mismatch signals.  

## Production route (step-by-step)

### 1) Online path records the anchor (DLA as flight recorder)

The platform pins that audit must persist **by-ref**:

* receipts / hashes,
* resolved bundle ref,
* degrade posture,
* and critically: OFP snapshot provenance including `input_basis` watermark vector and snapshot hash. 

### 2) OFS consumes a parity anchor and rebuilds

OFS is invoked with a target like:

* decision/audit record id (or exported anchor),
* the online snapshot hash/ref,
* the recorded `input_basis` watermark vector,
* the feature definition versions used online.  

**Pinned constraint:** parity is only meaningful if OFS uses the **same** basis + version set; otherwise the result must be explicit (UNCHECKABLE). 

### 3) ParityResult is produced (explicit outcomes)

Parity must resolve to one of:

* **MATCH**
* **MISMATCH** (with evidence: basis/version/mismatch fields)
* **UNCHECKABLE** (missing history, missing versions, missing anchor info, etc.) 

### 4) Ops/governance response loop

Parity results feed **operational actions**, not hot-path decisions:

* open an incident / alert,
* trigger a declared backfill/rebuild (P4),
* freeze/pause promotion, or rollback ACTIVE,
* tighten feature numeric canonicalization rules (if mismatch is representational),
* adjust archive hydration or retention posture if history is missing.  

---

# P3) Retention/Archive route

**Retention boundary forces EB-only vs EB+Archive basis; gaps yield explicit incomplete/UNCHECKABLE posture**

## Purpose

Make the learning/parity loops **time-proof**: when EB retention expires, the platform still supports reproducible rebuilds by treating Archive as a continuation of admitted facts — with explicit basis declarations.  

## Production route (step-by-step)

### 1) Build intent declares a basis/window

* Replay basis must be explicit: either offset ranges (preferred) or time windows anchored to offsets/checkpoints. 
* Retention length may differ by environment, but **replay semantics do not change**. 

### 2) Source selection happens deterministically

* If the basis lies within retention → EB supplies it.
* If the basis extends beyond retention → Archive supplies the cold portion (continuation of EB). 
* Archive addressing is **by-ref and pinned** (no vague searching). 

### 3) Completeness is verified, not assumed

* Archive hydration may be continuous or scheduled, but must be **verifiable** for a declared window.  

### 4) Outputs record the basis + source truthfully

Whether the run is dataset-build or parity:

* manifest/report must record: basis, which source(s) were used, and any checkpoints/digests needed to re-run later.  

### 5) Gap handling is fail-closed / explicit

If required history cannot be replayed (retention expired + archive gap):

* dataset build: fail closed or explicitly “incomplete” (but never publish a “complete-shaped” manifest),
* parity rebuild: **UNCHECKABLE** (never pretend).  

---

# P4) Backfill/rebuild route

**Run/Operate declares backfill → OFS rebuild (new manifests) → MF retrain → Registry promote/rollback**

## Purpose

Backfill is the production mechanism for **correcting derived truths** (features/datasets/projections) without mutating primary truth. It keeps watermarks meaningful, avoids “time travel,” and makes changes auditable.  

## Production route (step-by-step)

### 1) Backfill is declared (never silent)

A backfill declaration pins:

* scope (streams/partitions/windows),
* reason,
* basis (offset ranges/checkpoints),
* outputs being regenerated.  

**Hard law:** backfill produces new derived artifacts; it does not mutate EB events, Label Store timelines, Registry history, or immutable engine outputs.  

### 2) OFS rebuilds under declared basis and publishes new DatasetManifests

* New manifests are versioned/traceable, and they pin the new basis/as-of/feature versions used. 
* Watermarks remain monotonic; backfill doesn’t “change what an offset meant,” it creates a new derived version.  

### 3) MF retrains (optionally) from the new manifests

* MF run evidence + eval artifacts are produced; bundles are published for promotion.  

### 4) Registry governs promotion/rollback

* Promotion is a governed lifecycle action; rollback paths exist and are auditable.  
* DF always resolves deterministically and records the resolved bundle ref in decisions, so “what changed?” is answerable.  

## Typical backfill triggers (production-real)

* Feature definition change (new profile revision / bug fix) → rebuild datasets, retrain. 
* Archive gap resolved / retention policy changed → rebuild windows previously unbuildable. 
* Parity mismatches → declared rebuild + investigation + possible rollback. 

---

## One compact “map view” of P1–P4 (how they relate)

* **P1** is the normal loop (facts+labels → datasets → training → activation → more facts+labels). 
* **P2** is the correctness overlay (online provenance → offline rebuild → parity evidence). 
* **P3** is the time-proofing overlay (retention ends → archive continuation → explicit basis). 
* **P4** is the controlled correction mechanism (declare backfill → rebuild → retrain → govern activation/rollback). 

---

Below are the **three production loops (C: L1–L3)** expanded as **closed cycles that include OFS**, while still treating OFS as **opaque** (we only pin *outer behavior, triggers, invariants, and what must be recorded*).  

---

# L1) Continuous learning feedback loop

*(P1 closed-loop)*

## What this loop is for

This is the **“reality → learning → deployable change → new reality”** loop, where:

* **Reality** = admitted events (EB/Archive) + human truth (Label Store timelines)
* **Learning** = OFS builds reproducible datasets; MF trains and produces evidence-backed bundles
* **Deployable change** = Registry governs ACTIVE; DF uses ACTIVE deterministically and records provenance
* **New reality** = actions/outcomes + cases/labels + more admitted events

## The cycle edges (what vertices are “in the loop”)

A production-ready, minimal L1 includes:

1. **EB/Archive → OFS** (replayable facts)
2. **Label Store → OFS** (truth timelines, leakage-safe as-of joins)
3. **OFS → MF** (DatasetManifest + by-ref materials)
4. **MF → Registry** (bundle + evaluation evidence; promotion is governed)
5. **Registry → DF** (deterministic ACTIVE resolution)
6. **DF → EB** (decisions / intents / outcomes become replayable evidence facts)
7. **DLA + Case Workbench → Label Store** (human investigation writes truth; labels evolve append-only)
   …and back to (1)+(2).

## Step-by-step: what *must* happen (no hidden assumptions)

### Step 1 — Facts become replayable

* IG admits events, EB persists them as the **primary admitted fact log**.
* Replay identity is offsets/watermarks (per-partition), not “whatever time range.”

### Step 2 — Truth becomes learnable (without leakage)

* Labels are **only** truth once in **Label Store**, as **append-only timelines** with `effective_time` vs `observed_time`.
* OFS must build datasets using explicit **as-of joins** so you can reproduce “what we knew then” vs “what we know now.”

### Step 3 — OFS produces a pinned dataset artifact (the bridge)

* OFS is explicitly called out as the **contract bridge** between serving and training: deterministic reconstruction from replayable facts + same feature versions. 
* The output is not “a query result”; it is a **DatasetManifest** that pins replay basis, as-of boundary, join keys/scope, feature versions, and digests/refs.

### Step 4 — MF turns pinned datasets into evidence-backed bundles

* MF consumes DatasetManifests, produces training/eval evidence and bundle artifacts.
* This is where “learning outputs” become promotable objects with lineage.

### Step 5 — Registry governs activation; DF consumes deterministically

* Registry is the **only deployable truth source**; DF does not “load latest model file.”
* DF records the resolved bundle ref in provenance so every production behavior change is explainable.

### Step 6 — New decisions/actions produce new evidence and new labels over time

* Decisions + action intents/outcomes are replayable *evidence*; labels are truth only via Label Store.
* Case workflow emits new label assertions/corrections; loop continues.

## The “control points” (where humans/policies steer the loop)

In production, L1 is not “fully automatic”; these are the levers:

* **Dataset build intent** (which basis/window/scope to train on)
* **As-of posture** (“knew-then” eval vs “know-now” training)
* **Feature definition versions** (must be explicit/recorded; parity + drift prevention)
* **Promotion/rollback** (Registry governed lifecycle, not ad-hoc deploy)

---

# L2) Governance correction loop

*(P2 + P4 closed-loop)*

## What this loop is for

This is the loop that makes the platform **safe to operate** when something is wrong:

* parity mismatches,
* broken feature versions,
* archive gaps,
* schema evolution issues,
* or any “derived truth” corruption.

It ensures corrections happen as **declared, auditable operations**, without mutating primary truth.

## The cycle edges (what vertices are “in the loop”)

A minimal production L2 includes:

1. **DLA/audit provenance → OFS** (rebuild targets: input_basis, snapshot hash, versions, graph_version, degrade posture)
2. **OFS → ParityResult** (MATCH/MISMATCH/UNCHECKABLE) + evidence
3. **Run/Operate → backfill jobs** (explicit, scoped, auditable)
4. **OFS rebuild → new DatasetManifests** (versioned outputs; no silent overwrite)
5. **MF retrain → Registry promote/rollback** (governed change)
   …and parity/monitoring checks repeat until resolved.

## Step-by-step: how correction happens (production-real)

### Step 1 — A trigger exists (something “smells wrong”)

Common triggers:

* Parity mismatch spikes (OFS vs OFP snapshot hashes) 
* Archive completeness failures for requested windows 
* Feature version incompatibility (bundle expects different features) 
* Hot-path degrade posture changes causing unexpected behavior (observability → DL) 

### Step 2 — The platform produces *a rebuild target* (no guessing)

Your pins require RTDL to leave behind rebuild targets:

* EB coordinates/watermarks (`input_basis`)
* `feature_snapshot_hash`
* `graph_version`
* degrade posture used
* bundle ref used

This is what makes parity/correction evidence-based instead of “try around that time.”

### Step 3 — OFS attempts parity rebuild and emits an explicit outcome

OFS rebuilds using the recorded basis + versions. Outcome must be explicit:

* MATCH / MISMATCH / UNCHECKABLE (no silent “best effort”).

### Step 4 — If correction is needed, backfill is declared (never silent)

Backfill must declare:

* scope (streams/partitions/windows),
* purpose,
* basis (offset ranges/checkpoints),
* outputs being regenerated.

**Hard boundary:** derived stores/artifacts can be backfilled; primary truths cannot be “rewritten as correction.”

### Step 5 — OFS/MF/Registry execute the correction safely

* OFS publishes **new** manifests/artifacts (no overwrite)
* MF retrains from new manifests (optional, depending on what changed)
* Registry promotes/rolls back in a governed way; DF behavior changes only via this explicit mechanism

### Step 6 — Loop closes when evidence stabilizes

* Parity outcomes return to MATCH (or the mismatch is explained and accepted as a known divergence with recorded reason) 
* Operational metrics/alerts return to expected ranges (Obs/Gov loop)

---

# L3) Immutability / idempotency loop

*(OFS outputs become inputs for future OFS decisions; “no silent overwrite”)*

## What this loop is for

This loop is about **preventing “dataset drift” and “rerun roulette.”** It ensures:

* the same BuildIntent doesn’t create multiple contradictory “truthy” datasets,
* rebuilds create new versions with explicit lineage,
* and every downstream system can safely rely on **by-ref immutable artifacts**.

This is the loop that makes your learning plane *audit-grade*.

## The cycle edges (outer behavior, OFS still opaque)

1. **OFS publishes DatasetManifest + materials to `ofs/...`**
2. Later, OFS (or Run/Operate) references prior manifests as the authoritative “what was built” record
3. New builds either:

   * resolve to “already built” (idempotent), or
   * produce a *new* dataset identity and declare supersession/backfill

## The pinned laws that make L3 work

### Law 1 — “No patching”: corrections create new identity/version

Downstream must not “patch” facts/artifacts; corrections happen as:

* a new artifact/version with new identity, and/or
* a new run with a new join surface pointing at corrected refs. 

### Law 2 — DatasetManifest is the reproducibility unit

DatasetManifest must pin:

* replay basis,
* label as-of boundary,
* scope/join keys,
* feature versions,
* digests/refs,
* provenance.

### Law 3 — Watermarks don’t lie; backfills don’t time travel

Backfills create new offsets and/or new derived versions; they don’t redefine the past.

## What “idempotent OFS behavior” means (externally)

Without defining internal mechanisms, we pin the *observable behavior*:

### Case A — Same BuildIntent retried

* OFS must return the **same DatasetManifest ref** (or deterministically equivalent) if the intent pins are identical and the build already exists.
* It must not create “DatasetManifest v2” silently just because it ran again.

### Case B — New build that changes meaning

If any meaning-changing pin differs (basis/as-of/feature versions/scope), OFS must produce a **new dataset identity** and a new manifest, not overwrite the old one.

### Case C — Declared backfill/supersession

If a rebuild is a correction, it must be:

* explicitly declared (who/why/scope/basis),
* and link old→new in governance/audit form (implementation can be `gov/...` objects and/or control facts).

## Why L3 matters to the whole platform graph

L3 is what lets:

* MF train from a manifest and later prove *exactly* what it trained on,
* Registry promote/rollback without mystery artifacts, 
* parity checks remain meaningful months later even after retention changes (because the basis is pinned and archive exists).

---

Yes — the **environment ladder** is *exactly* where a lot of “looks fine in local, breaks in prod” drift sneaks in, so it’s worth pinning how **these joins/paths/loops must behave across Local → Dev → Prod**.

The ladder is *not* “three platforms”; it’s **one platform graph + one set of rails**, with only the **operational envelope** changing (scale, retention/archive, security strictness, reliability, observability).  

## 1) What must NOT change across environments (applies to all joins/paths/loops)

These are the “no drift” invariants that *must* hold for OFS’s A/B/C network everywhere:

* **Same component graph + trust boundaries** (IG is front door, EB is fact log, SR is readiness authority, Registry is deployable truth, Label Store is label truth, etc.). 
* **Same rails + join semantics**: ContextPins discipline, canonical envelope at bus boundary, no-PASS-no-read, by-ref refs/locators, watermarks as the universal “what was applied” token, idempotency in at-least-once world, append-only + supersedes, deterministic registry resolution, explicit as-of semantics.  
* **Same meaning of the key words** everywhere: “READY”, “ADMITTED”, “ACTIVE”, “LABEL AS-OF”, “BACKFILL”. 

**Implication for OFS:** the *meaning* of A4/A5 replay basis, A6 label as-of, and A8 DatasetManifest must not change across envs; only the **constraints** (how much history exists, who may trigger, how strict auth is, etc.) may change.

## 2) What *is allowed* to differ, and how it hits OFS joins/paths/loops

### A) Retention + Archive (biggest impact on P3 and A5)

Retention length is explicitly an **environment profile knob**, *not* a semantic change. 

* **Local:** short EB retention; **Archive may be disabled** (or minimal).
* **Dev:** medium retention; Archive may exist but can be “scheduled/hydrated” as long as it’s verifiable. 
* **Prod:** longer retention **plus archive continuity** for long-horizon rebuilds.  

**How this constrains the network you already mapped:**

* **P3 (Retention/Archive path)** must be exercised explicitly across the ladder:

  * Local may legitimately fail/UNCHECKABLE for horizons beyond retention (because A5 may be absent), but it must fail *explicitly* (never silent partial). 
  * Dev must prove “archive is verifiable for a declared window” so OFS can trust it. 
  * Prod must treat archive policy/retention changes as governed changes (emit governance facts).  

### B) Security strictness (hits A1 triggers, A9 MF, Registry promotions, Label writes)

Security posture is allowed to vary, but **the mechanism must exist in all envs**, and dev must be “real enough to catch prod failures.”  

**What that means for OFS network behavior:**

* In **local**, you can run permissive allowlists/dev creds, but OFS still behaves as a job with explicit intent; no “special local semantics.” 
* In **dev**, the ladder’s purpose is to catch: unauthorized job triggers, unauthorized label access, unauthorized registry lifecycle actions, and missing PASS evidence that local might accidentally allow. 
* In **prod**, *every* outcome-affecting change (policy rev, bundle activation, backfill, retention change) is a governed act and must be attributable.

### C) Observability depth + sampling (hits A11 + L2)

Observability is a platform law; local should still run a production-shaped OTel pipeline, even if thresholds/sampling differ.  

* Sampling/alert thresholds can differ by env, but **propagation semantics and correlation keys must be identical**. 
* In **prod**, corridor checks/degrade triggers are meaningful; in local they can be informational — but the “degrade mask is a hard constraint” rule remains the same.  

**Practical OFS effect:** L2 (governance correction loop) should show up as metrics/alerts in dev/prod (parity mismatch, archive gaps, dataset build failures), not as “someone noticed it in logs.”  

### D) Scale / throughput / reliability (doesn’t change meaning, but changes which failures appear)

This mainly changes:

* how often you hit duplicates/retries (at-least-once realism),
* how often archive overlap/gaps show,
* how often backfills are needed,
* and how strict you must be about idempotency keys and “exclusive-next offset” checkpoint meaning.  

## 3) Promotion across the ladder (why L1/L2/L3 don’t drift)

Your ladder explicitly pins promotion as **environment-profile selection**, not “rewrite for prod.”  

Three promotion lanes matter to these loops: 

1. **Code artifacts** (build once, run same binaries everywhere)
2. **Policy/profile revisions** (outcome-affecting configs are versioned + auditable; components report policy rev in provenance) 
3. **Bundles** (MF publishes; Registry governs activation; DF resolves deterministically and records bundle ref) 

**Loop impact:**

* **L3 (immutability/idempotency loop)** becomes enforceable because artifacts/manifests/policy revs are all immutable+identifiable across envs — you can answer “what ran under what rules?” in local/dev/prod the same way.  

## 4) Environment ladder “must-run” checks for OFS network (so it’s production-ready)

This is the cleanest way to connect *your* A/B/C maps to the ladder:

* **Local:** run a *tiny* golden flow that includes “label + offline shadow + registry resolve at least once” (even with small data and short retention).  
* **Dev:** run the same flows but with “real enough” auth/policies to catch missing PASS evidence / unauthorized operations / incompatibilities.  
* **Prod:** same semantics, but stricter change control: retention/archive policy changes and backfills emit governance facts; parity mismatches trigger the governed correction loop.

---

### Net-net (the authoritative pin for this discussion)

Your **paths/joins/loops (A/B/C) do not change across the environment ladder**; only their **operational envelope** changes (especially retention/archive availability, security strictness, reliability, observability depth). Promotion is **code+profile+bundle selection**, not semantic branching.  

---

Yep — here are the **environment profile knobs** (and the few **deployment truths**) you should keep in your head for OFS *while it’s still opaque*, so when we “open the box” we design internals that fit the real substrate + ladder without drift.

Everything below follows your pinned split: **same platform semantics everywhere**, only the **operational envelope** changes (scale / retention+archive / security / reliability / observability).  

---

## 1) First pin: OFS is a job deployment unit (batch plane)

So its deployment shape is: **invoked**, with **pinned inputs**, **deterministic outputs**, a **run record / receipt story**, and explicit **start/finish/fail** lifecycle.  

That alone drives several knobs: scheduling/triggering, idempotency keys, output publication, and telemetry posture.

---

## 2) The config knobs you’ll actually need (grouped the right way)

Your deployment notes pin the key separation: **policy config vs wiring config**. 

### A) Wiring profile knobs (non-semantic “where/how to connect”)

These can vary freely by environment without claiming meaning changed.

**Substrate endpoints**

* **Event Bus**: broker endpoints + consumer group id(s) for OFS readers (EB side). 
* **Object store**: bucket + base prefixes for:

  * `sr/…` (read `sr/run_facts_view`)
  * `ofs/…` (write datasets + DatasetManifest)
  * `profiles/…` (read feature definition profiles) 
* **DB**: Label Store DSN/schema. 
* **Observability**: OTLP collector endpoint + service/job identity. 

**Resource/compute**

* CPU/memory limits, worker concurrency, batch sizes, spill/temp dirs, etc. (pure wiring/perf knobs).

**Scheduling**

* Cron/frequency defaults per env (local often manual; dev scheduled; prod policy-driven), plus max concurrent runs.

### B) Policy profile knobs (outcome-affecting “what rules are in force”)

These are *governed*, versioned, and should be reported as `policy_rev` in outputs/telemetry.  

For OFS, the policy knobs that matter most:

**Replay + history policy**

* EB **retention window** (environment knob) and “what to do when requested basis exceeds retention” (fail / require archive / uncheckable). 
* Archive policy:

  * enabled/disabled,
  * “completeness must be verifiable for a declared window” (required),
  * addressing must be by-ref and pinned (no vague search). 

**Label as-of policy (leakage)**

* Default as-of posture (knew-then vs know-now) and the required recording in DatasetManifest.

**Feature version policy**

* How OFS resolves a feature definition profile (explicit ref vs “ACTIVE pointer” resolution), and the rule that the resolved version must be recorded (anti-drift).

**Build kinds allowed + completeness thresholds**

* Which build kinds are allowed in this env (dataset builds, parity rebuilds, forensic rebuilds).
* What counts as “publishable” vs “incomplete/uncertain”.

**Backfill governance**

* Who can trigger backfills, what approvals are required, what scope limits exist, and the rule that backfills are explicit + auditable and regenerate **derived** artifacts only.  

**Security policy (authz)**

* Permissions: who can read labels, who can read SR join surfaces, who can publish `ofs/…`, who can emit gov facts, etc. (mechanism exists in all envs; strictness rises up the ladder).

---

## 3) Environment ladder knobs (what differs across local/dev/prod)

This is the “allowed to change” set — and it impacts OFS more than most components because it lives on history + rebuild. 

### Local (fast iteration, still obey rails)

* **Short EB retention**, often **no archive** (or minimal). 
* Security friction low, but semantics unchanged (no “special local meaning”). 
* Observability is “debug friendly,” but still OTLP/collector semantics match prod. 

### Dev (integration realism)

* Medium retention, **archive may exist** (continuous or scheduled) but must be verifiable for declared windows. 
* Security is “real enough” to catch missing permissions, missing PASS evidence, bad lifecycle actions. 

### Prod (governed, hardened)

* Longer retention + **archive continuity** as a first-class capability for long-horizon datasets and audits. 
* Strict change control: policy rev activations, retention changes, backfills emit governance facts.  
* Observability depth is higher: SLOs/alerts; parity mismatch and archive gaps are operational signals. 

---

## 4) The OFS substrate mapping you should keep front-of-mind

This is the “deployment wiring truth” for OFS as a vertex (so we don’t accidentally design internals that require new dependencies). 

**Reads**

* Bus/Archive: `fp.bus.traffic.v1` history + archive continuation
* DB: `label_store` as-of timelines
* Object: `sr/run_facts_view`
* Artifacts: feature definition profiles  

**Writes**

* Object: `ofs/…` dataset materializations + **DatasetManifest**
* Optional: gov fact → `fp.bus.control.v1` 

---

## 5) Observability + governance expectations for OFS runs

Two “deployment-grade” expectations you’ll want as we open the box:

1. **OTLP everywhere** (even jobs) — traces/metrics/logs must be emitted with the same correlation posture across envs. 
2. **Outcome-affecting changes are facts** — policy activations, retention changes, backfills, bundle promotions, etc., are durable governance facts (not just logs).  

---

## 6) Practical “direction” before we illuminate the internals

If you want your next phase to go smoothly, the minimum you’ll want to have ready (conceptually) is:

* A named **profile split** for OFS: `ofs.wiring.*` vs `ofs.policy.*` (even if it’s one YAML now). 
* A clear stance per environment for:

  * retention length,
  * archive enabled/disabled and how completeness is proven,
  * security strictness for job triggers + label reads + artifact writes.  
* The “production-shaped local substrate” assumption (Redpanda/MinIO/Postgres/OTel) so the internal design doesn’t accidentally depend on cloud-only behaviors.  

When you’re ready to leave the opaque vertex, the very first internal design move should be: **define the OFS run lifecycle + idempotency + publication semantics** (because those are the deployment-unit constraints that everything else hangs off). 

---

## USER: PAUSE FOR REFLECTION

Perfect moment to “freeze the outer shell” before we open the box.

Below is the **authoritative outer-network checkpoint** for **OFS** (joins + paths + loops + env-ladder constraints), distilled to the pieces that must *not* drift when we start designing internals.

---

## 1) OFS’s outer role and authority boundary

**OFS is an on-demand/scheduled *job* deployment unit** (not an always-on service), whose domain authority is:

* **truth for training inputs** via `DatasetManifest + by-ref materials` under `ofs/…`, and
* optional **parity evidence** (shadow twin validation),
  while **never** becoming a serving plane or a writer of primary truth (events/labels/registry history).

This is exactly aligned with the platform’s “History/backfill overlay” (archive continuation, explicit replay basis, declared backfills, monotonic watermarks, manifests as reproducibility units).

---

## 2) The complete join surface around OFS (A-edges, frozen)

### Inbound joins (OFS reads)

1. **EB `fp.bus.traffic.v1` → OFS** (within retention; canonical envelopes; replay by offsets/watermarks).
2. **Archive → OFS** (beyond retention; *continuation* of EB; same logical events; replay “as if EB”; basis must be recorded).
3. **Label Store → OFS** (append-only timelines; leakage-safe “as-of” reads using effective vs observed time).
4. **Feature definition profiles → OFS** (versioned artifacts; OFS must lock and record feature definition versions used).
5. **SR `sr/run_facts_view` (object) → OFS** (ContextPins + by-ref join surface; “scan latest” disallowed).
6. **Optional: DLA exports / provenance anchors → OFS** (for parity targets: `feature_snapshot_hash`, `input_basis`, etc.).

### Outbound joins (OFS writes)

7. **OFS → object store `ofs/…`** (dataset materializations + **DatasetManifest** as the unit of truth).
8. **OFS → Model Factory** (**DatasetManifest + evidence**, not a dataframe handoff).
9. **Optional: OFS → `fp.bus.control.v1`** (governance facts: publish/backfill/parity/build-failed announcements; by-ref pointers).
10. **OFS → OTLP pipeline** (telemetry; required for safe ops).

**Substrate mapping is consistent and closed**: OFS reads bus/archive + `label_store` + `sr/run_facts_view` + feature profiles; writes `ofs/…` (+ optional control facts). No new external dependencies are required by the outer design.

---

## 3) The pinned “outer laws” OFS must obey (rails + history overlay)

These are the non-negotiables that constrain every internal design choice:

* **Canonical Envelope at bus boundary** for anything treated as admitted traffic. 
* **By-ref truth transport** (refs/locators + optional digests), no “scan latest”. 
* **No PASS → no read** (platform-wide gating discipline). 
* **Watermarks are the universal “what was applied” token**; provenance uses per-partition offsets/watermark vectors.
* **Archive is continuation of EB, not a second truth**.
* **Replay basis is always explicit** (offset ranges preferred; time windows allowed only when anchored to offsets/checkpoints).
* **Backfill is declared + auditable**; never silent; never “time travel.”
* **DatasetManifest is the pinned bridge artifact** (unit of reproducibility).
* **Late labels are normal; “as-of” makes them safe** (knew-then vs know-now is explicit).

---

## 4) Paths and loops (B + C) — what they guarantee

### P1 / L1: Learning feedback loop (continuous)

**Facts + labels → OFS datasets → MF training → Registry activation → DF decisions → cases/labels → back to OFS**, with DatasetManifests as the reproducibility bridge.

**Invariant:** any model/bundle in prod must be explainable as “code X + policy/profile rev Y + dataset manifests Z”.

### P2 / L2: Governance correction loop (parity + backfill)

DLA provenance anchors enable **evidence-based parity rebuild**; mismatches trigger **declared backfills** and governed rollouts/rollbacks.

**Invariant:** if provenance is incomplete, outcomes are quarantined/explicit (no half-truth). 

### P3: Retention/archive route

When retention expires, rebuild is still reproducible because archive preserves identity and basis semantics; gaps become explicit FAIL/UNCHECKABLE, never silent partial success.

### P4 / L3: Backfill + immutability/idempotency loop

Derived artifacts can be regenerated, but primary truth is not rewritten; OFS outputs are immutable and retries are idempotent in meaning.

---

## 5) Environment ladder implications (so we don’t drift into “works locally” semantics)

**Pinned ladder rule:** local/dev/prod run the *same platform graph and rails*; environments differ only in operational envelope (scale, retention/archive, security strictness, reliability, observability depth).

For OFS specifically, the critical env knobs are:

* **Retention length** (local short; dev medium; prod policy-driven) — but offsets/watermarks/replay semantics do not change. 
* **Archive enabled/disabled + verifiability** (local may not have it; dev may have partial; prod must be continuous or scheduled but verifiable).
* **Security strictness** (mechanism exists everywhere; tightens up the ladder). 
* **Observability depth** (OTLP everywhere; prod adds SLOs/alerts).

And your “golden flow” expectation explicitly includes “label + offline shadow + registry resolve at least once” to keep local production-shaped.

---

## 6) Drift tripwires (if we see these when we open the box, we stop)

When we start designing internals, any proposal that implies the following is **design drift**:

* OFS “serves” features or participates in hot-path decisions.
* OFS writes to EB facts / Label Store timelines / Registry history (primary truth mutation).
* OFS relies on “latest” discovery instead of pinned refs/basis.
* OFS publishes datasets without a DatasetManifest (or manifests that don’t pin basis/as-of/versions).
* OFS treats archive as a different event truth (instead of EB continuation).
* OFS treats time windows as the *basis* (instead of offsets/checkpoints).
* OFS “best-effort succeeds” silently when history/versions are missing (must be explicit FAIL/UNCHECKABLE).

---

Yep — I understand exactly: **one level deeper**, still **opaque boxes**, but now we name the **internal subnetworks** OFS must contain so the later “illumination” is guided and doesn’t sprawl.

Below is the **v0 internal subnetwork map** I’m declaring as authoritative for OFS. It’s directly forced by J14/J15 + the history/backfill overlay + the deployment substrate map (inputs/outputs), so it shouldn’t drift later.

---

# OFS internal subnetworks (first layer, all opaque)

## S1) Build Orchestration and Run Ledger

**Purpose:** Turn a BuildIntent into a single, pinned execution with explicit lifecycle (start/finish/fail) and idempotency.

**Owns (authority):**

* job-level idempotency (`request_id` / build identity)
* run lifecycle record (even if it’s just an object record + telemetry)
* “no silent retries that change meaning” posture

**Consumes:** BuildIntent from Run/Operate (A1).
**Produces:** a frozen BuildPlan handed to S2; final status + output refs handed to S6/S7.
**Why it must exist:** OFS is a **job deployment unit** with pinned inputs/outputs and explicit lifecycle. 

---

## S2) Pin & Provenance Resolver

**Purpose:** Freeze *all meaning-affecting pins* up front so nothing later “decides implicitly.”

This subnetwork is the “anti-drift brain” of OFS.

**Owns (authority):**

* resolving & freezing **ContextPins** and any run/world context allowed via `sr/run_facts_view` (no scanning)
* resolving & freezing **ReplayBasis** (offset/watermark vector preferred; time windows only if anchored to offsets/checkpoints)
* resolving & freezing **LabelAsOfSpec** (effective vs observed time posture; no hidden “now”)
* resolving & freezing **FeatureVersionSet** from feature definition profiles (no “latest by default” unless explicitly requested and then recorded)
* (optional) resolving **ParityAnchor** from DLA exports (snapshot hash + input_basis + versions)

**Consumes:** A2/A3/A7 inputs (sr view, profiles, parity anchors) + the BuildIntent.
**Produces:** a *fully pinned* plan: `{ReplayBasis, LabelAsOfSpec, FeatureVersionSet, Scope, optional ParityAnchor}`.

---

## S3) History Acquisition and Replay Unifier

**Purpose:** Provide the **admitted fact stream slice** described by ReplayBasis.

**Owns (authority):**

* treating EB + Archive as **one logical stream** (same identity + same ordering basis per partition)
* enforcing the “watermarks don’t lie” rule (replay tokens are offsets/checkpoints; monotonic; no time travel)
* explicit gap/completeness posture: if basis cannot be satisfied (retention boundary / archive gap), the outcome is explicit FAIL/UNCHECKABLE—not silent partial

**Consumes:** A4/A5 (EB `fp.bus.traffic.v1` + Archive) and the pinned ReplayBasis.
**Produces:** deterministic replay batches/iterators + replay receipts (counts, partition ranges, checkpoint evidence) to S5/S6.

---

## S4) Truth Timeline Resolver (Label As-Of)

**Purpose:** Provide leakage-safe labels aligned to the pinned as-of rules.

**Owns (authority):**

* Label Store is the only label truth (append-only timelines)
* explicit as-of semantics using **effective_time vs observed_time** (produce “knew-then” vs “know-now” datasets without confusion)
* declared label-resolution rules (latest observed assertion as-of, supersedes semantics, etc.)

**Consumes:** A6 (Label Store) + pinned LabelAsOfSpec + scope from S2.
**Produces:** label views keyed for joins + label coverage diagnostics to S5/S6.

---

## S5) Feature Reconstruction and Dataset Shaping

**Purpose:** Apply **feature definition versions** to the replay slice and shape outputs into “snapshots” and/or training tables.

**Owns (authority):**

* semantics match with online feature definitions by version set (anti-drift)
* deterministic assembly rules (no implied global ordering across partitions; stable canonicalization where hashes are computed)
* output “kinds”: per-event / per-entity / per-window datasets (shaping), without changing the pinned meaning

**Consumes:** replay stream from S3 + labels from S4 + FeatureVersionSet from S2.
**Produces:** materializable datasets/snapshots + computed summaries to S6 (and parity-comparable snapshots to S7).

*(Note: this corresponds closely to your conceptual “Dataset Materializer” idea, but here it is pinned to the platform rails and versioning laws.) *

---

## S6) Artifact Publisher and DatasetManifest Authority

**Purpose:** Publish **immutable by-ref outputs** under `ofs/...` and make “dataset truth” real only via DatasetManifest.

**Owns (authority):**

* atomic publish: dataset isn’t “real” until the DatasetManifest exists and points to fully written materials
* DatasetManifest semantics as the **unit of reproducibility** (pins replay basis, label as-of, feature versions, scope/join keys, digests/refs, provenance)
* immutability/idempotency loop: same pinned intent ⇒ same manifest (or explicitly declared supersession/backfill)

**Consumes:** shaped outputs from S5 + pinned plan from S2 + receipts from S3/S4.
**Produces:** A8 `ofs/...` materials + DatasetManifest; handoff refs for MF (A9).

---

## S7) Parity, Governance, and External Signalling

**Purpose:** Close the “shadow twin” and operations loops without contaminating the hot path.

This is a combined subnetwork because they are all *external signalling* surfaces.

**Owns (authority):**

* parity outcomes: **MATCH / MISMATCH / UNCHECKABLE**, always evidence-backed if attempted
* emitting optional governance facts to `fp.bus.control.v1` (DatasetPublished / BackfillDeclared / ParityResult / BuildFailed) as *announcements with by-ref pointers*, not transports
* OTLP telemetry emission and correlation keys (job id, dataset id, pins, basis hash)

**Consumes:** optional DLA anchors (A7) + outputs/manifests from S6.
**Produces:** A10 control facts (optional) + A11 telemetry + parity artifacts (by-ref) to object store if needed.

---

# How these subnetworks connect (still opaque, but now ordered)

```
S1 Build Orchestration
        |
        v
S2 Pin & Provenance Resolver  <--- (sr/run_facts_view, feature profiles, optional DLA anchors)
        |
        +------------------+
        |                  |
        v                  v
S3 Replay Unifier       S4 Label As-Of Resolver
 (EB + Archive)          (Label Store)
        \                  /
         \                /
          v              v
        S5 Feature Reconstruction & Dataset Shaping
                   |
                   v
        S6 Artifact Publisher & DatasetManifest
                   |
                   v
        S7 Parity/Gov/Telemetry Signalling  ---> (MF handoff refs, optional control facts, OTLP)
```

This layout is deliberately the minimum that satisfies:

* J14/J15 meaning pins
* the deployment substrate map for OFS inputs/outputs
* the environment ladder constraint that semantics don’t change across local/dev/prod (only operational envelope changes)

---

# Tight vs loose (so we don’t over-design too early)

**Tight (must be pinned in these subnetworks):**

* ReplayBasis semantics (offset/watermark basis; archive continuation; explicit gaps)
* Label as-of semantics (effective vs observed; explicit posture)
* Feature version locking and recording
* DatasetManifest publish semantics and contents
* Parity outcomes and explicit UNCHECKABLE posture

**Loose (defer inside the boxes):**

* file formats, execution engines, parallelism, caching strategy, incremental vs full rebuild mechanics.

---

Yep — we stay **one level deep**: the OFS internal network is a graph of **opaque subnetworks** (S1–S7). Now we identify the **internal joins (edges)** between them, plus the **internal production paths** (workflows) and the **internal loops** (retry / chunk / backfill / parity cycles) that exist even before we open any box.

I’m going to name these as **I-joins / I-paths / I-loops** so they’re unambiguous later.

---

## A) Internal joins inside OFS (edge inventory)

### I1) S1 → S2

**BuildIntent → BuildPlan request**

* **Flows:** `BuildIntent` (request_id, build_kind, selectors)
* **Return expectation:** S2 will *freeze* meaning pins (basis/as-of/versions/scope) or fail closed.

### I2) S2 → S3

**ReplayBasis handoff**

* **Flows:** `ReplayBasis + SourcePlan` (EB vs Archive slices; partition ranges; checkpoints)
* **Purpose:** make history acquisition deterministic and explicit.

### I3) S2 → S4

**LabelAsOfSpec handoff**

* **Flows:** `LabelAsOfSpec + LabelScope` (subjects/entities/event-types)
* **Purpose:** make leakage posture explicit and reproducible.

### I4) S2 → S5

**ExecutionPins handoff**

* **Flows:** `FeatureVersionSet + Scope + OutputKind`
* **Purpose:** S5 must not “discover” feature versions or shape rules mid-run.

### I5) S3 → S5

**Replay stream feed**

* **Flows:** `ReplaySlice` (partitioned event batches/iterators) + `ReplayReceipts` (coverage, counts, ranges)
* **Purpose:** drive deterministic reconstruction without assuming global order.

### I6) S4 → S5

**Label view feed**

* **Flows:** `LabelView` (as-of resolved label assertions) + coverage diagnostics
* **Purpose:** supervised dataset shaping, evaluation postures.

### I7) S5 → S6

**Materialization stream**

* **Flows:** `DatasetDraft` / `SnapshotDraft` (shards + stats + digest candidates)
* **Purpose:** publishing must be atomic and manifest-driven.

### I8) S2 + S3 + S4 → S6

**Provenance bundle to manifest builder**

* **Flows:** `PinnedPlan + ReplayReceipts + LabelReceipts`
* **Purpose:** S6 constructs the **DatasetManifest** as the unit of truth.

### I9) S6 → S1

**Publish receipt**

* **Flows:** `PublishReceipt` (dataset_id, manifest_ref, output_refs, status)
* **Purpose:** close the job lifecycle; idempotency handling.

### I10) S6 → S7

**Parity/governance signal inputs**

* **Flows:** manifest_ref + (optional) snapshot hash / draft parity inputs
* **Purpose:** S7 can emit ParityResult/control facts/telemetry without touching core build.

### I11) S7 → S1

**External signalling summary**

* **Flows:** “signals emitted” summary + final parity outcome (if any)
* **Purpose:** ensures the run ledger reflects what was announced.

### (Production-real “short-circuit” joins)

These exist in mature systems and help idempotency, without opening boxes:

* **I12) S1/S2 ↔ S6 (preflight existence check)**
  If the same pinned intent already has a published manifest, OFS can return it without replaying history. (This is the internal expression of the immutability/idempotency loop.)

* **I13) S3 ↔ S6 (staged commit receipts)**
  S3 can provide “segment completeness receipts” that S6 uses to gate atomic publish.

---

## B) Internal paths (production workflows inside OFS)

Each “I-path” is a *route through the internal graph* that corresponds to real production invocations.

### IP1) Standard dataset build (training/eval)

```
S1 → S2 → (S3 || S4) → S5 → S6 → S7 → S1
```

* Parallel fanout: S3 (replay) and S4 (labels) can run concurrently once pins are frozen.
* Merge at S5 to produce shaped datasets.
* Publish is always through S6 (manifest-driven).

### IP2) Parity rebuild (shadow twin)

```
S1 → S2(uses ParityAnchor) → S3 → S5 → S6 → S7(parity) → S1
```

* Labels are usually **optional** here (depends whether parity is “feature snapshot parity” only, or “full supervised dataset parity”).
* Key: S2 pins basis/versions from the parity anchor; S7 produces MATCH/MISMATCH/UNCHECKABLE.

### IP3) Forensic snapshot rebuild (audit/support)

```
S1 → S2 → S3 → S5 → S6 → S7(optional) → S1
```

* Similar to parity rebuild but anchored on an explicit feature key / as-of request (not necessarily a DF decision anchor).
* Output may be a “snapshot artifact + provenance” rather than a training dataset.

### IP4) Backfill rebuild (declared correction)

```
S1(backfill intent) → S2 → (S3 || S4) → S5 → S6(new manifest) → S7(backfill fact) → S1
```

* Same mechanical flow as dataset build, but:

  * S6 must treat outputs as **new identity/supersession**, not overwrite.
  * S7 emits explicit “BackfillDeclared/Completed” style signals (if enabled).

### IP5) Plan-only / feasibility check (production convenience)

```
S1 → S2 → S3(feasibility: retention/archive) → S1
```

* No publishing; used to answer “can we build this basis?” before burning compute.
* This is where archive gaps and retention boundaries get detected early.

---

## C) Internal loops (cycles that exist inside the vertex)

These are the **production cycles** that will show up even if every box is opaque.

### IL1) Idempotent retry loop (job-level)

```
S1 retry → S2 pins → (S6 preflight says “already published”) → S1 done
```

* Same request (same pinned intent) should not create a new dataset “version” silently.
* This loop is why I12 exists.

### IL2) Chunk / partition processing loop (data-level)

```
S3 emits ReplaySlice(k) → S5 processes(k) → S6 stages(k) → repeat for k+1
```

* In production, replay is almost always partition/chunk driven.
* The loop exists regardless of how we implement S3/S5/S6 internally.

### IL3) Publish-commit loop (atomicity loop)

```
S6 stage writes → validate digests/receipts → commit manifest → (if failure) rollback/mark failed → retry
```

* “Dataset is real only when the manifest exists” creates this inherent loop.

### IL4) Supersession/backfill loop (derived-truth correction loop)

```
S7 (mismatch/backfill needed) → external trigger → S1(backfill intent) → … → S6(new manifest)
```

* The trigger may be parity mismatch, archive gap resolution, or feature profile change.
* OFS itself doesn’t mutate the old dataset; it loops by producing a new one.

### IL5) Parity stabilization loop (optional but production-real)

```
S7 parity mismatch → governance signal → (operator action) → S1 rebuild → S7 parity again → stabilize
```

* This is the internal reflection of the broader “governance correction loop,” but it’s still a real cycle across S1/S2/S3/S5/S6/S7.

---

## D) One compact internal network sketch (still opaque boxes)

```
          (I12 preflight) ┌───────────────┐
        ┌────────────────►│ S6 Publisher  │◄──────────┐
        │                  └──────┬────────┘           │
        │                         │ I9                │
┌───────┴───────┐   I1   ┌────────▼────────┐    I10   │
│ S1 Orchestr.  ├───────►│ S2 Pins/Prov    ├────────►┌▼──────────────┐
└───────┬───────┘        └───┬────────┬────┘         │ S7 Signals     │
        │ I11                 │ I2     │ I3          └─────┬──────────┘
        │                     ▼        ▼                  │
        │                ┌────────┐ ┌────────┐            │
        │                │ S3     │ │ S4     │            │
        │                │ Replay │ │ Labels │            │
        │                └───┬────┘ └───┬────┘            │
        │                    │ I5       │ I6             │
        │                    └──────┬───┘                │
        │                           ▼ I7                 │
        │                     ┌───────────┐              │
        └────────────────────►│ S5 Rebuild│──────────────┘
                              └───────────┘
```

---

Locked. We’ll illuminate **internal joins I1–I4** as *handshake contracts between opaque subnetworks* (S1/S2/S3/S4/S5). I’m going to **pin what is “in-bounds” vs “drift”** for each join so when we go deeper later we don’t accidentally violate the outer network laws (explicit replay basis, watermarks monotonic, label as-of safety, version-locked features, manifest-driven reproducibility).

I’ll use a consistent pattern:

* **Purpose** (why the join exists)
* **Authority boundary** (who decides what)
* **Handshake payloads** (inputs/outputs, still conceptual—no full schemas)
* **Hard invariants** (non-negotiable)
* **Failure classes** (fail-closed vs explicit “uncheckable” posture)
* **Env ladder notes** (what differs operationally, not semantically)

---

## Internal Join I1 — S1 → S2

### “Plan-and-pin” handshake (BuildIntent → Pinned BuildPlan)

### Purpose

Take a **BuildIntent** (what the operator wants) and produce a **Pinned BuildPlan** (what OFS will *actually do*, deterministically), *before* any heavy replay/compute happens.

This is the internal enforcement point for:
**explicit replay basis**, **explicit label as-of**, **explicit feature versions**, and **no hidden defaults**.

### Authority boundary (my pin)

* **S1 owns job lifecycle + idempotency for execution** (request/run tracking).
* **S2 owns meaning pins** (basis/as-of/versions/scope).
  S1 must not “decide” versions/basis; it just carries operator intent.

### Handshake payloads

**I1.Request = BuildIntent (conceptual minimum)**

* `request_id` (job idempotency key)
* `build_kind`: `dataset_build | parity_rebuild | forensic_rebuild | backfill_rebuild`
* `scope_selectors`: (optional) ContextPins filter or dataset scope selectors
* `replay_selector`: either

  * `offset_basis` (preferred), or
  * `time_window` (allowed only as selector; must resolve → offsets and be recorded)
* `label_as_of_spec` (required for supervised dataset kinds; explicit posture)
* `feature_profile_selector`: explicit ref OR “ACTIVE pointer rule” (but must resolve to a concrete ref and be recorded)
* `output_spec`: dataset_kind + dataset_key/namespace + any shaping intent (per-event / per-entity / per-window)
* optional `parity_anchor_ref` (e.g., DLA anchor id/ref)

**I1.Response = PlanResult**

* `status`: `ACCEPTED_PINNED | REJECTED | NEEDS_HUMAN/WAIT | UNSATISFIABLE_IN_ENV`
* If accepted:

  * `plan_id` (hash of *meaning pins*, stable across retries)
  * `pinned_plan`: `{scope, replay_basis(or resolvable spec), label_as_of, feature_version_set, output_spec, policy_rev, env_profile_id}`
  * `execution_hints`: “archive required”, “labels required”, etc. (advisory, not semantic)

### Hard invariants (non-negotiable)

1. **No heavy work starts until pins are frozen.**
2. **Time windows are never the final basis**; they must resolve to offsets/checkpoints and the resolved basis is what gets recorded.
3. **No implicit “now.”** If “as-of now” is desired, S1 must materialize a concrete timestamp at trigger time and pass it explicitly. (This prevents invisible drift across retries.)
4. **Feature versions cannot float.** “ACTIVE” must resolve to a concrete revision/digest and be recorded in the pinned plan.

### Failure classes

* **REJECTED (invalid intent):** missing required fields, contradictory posture (e.g., supervised dataset build without label_as_of_spec).
* **UNSATISFIABLE_IN_ENV:** basis requires archive but archive disabled in this env profile; or policy forbids this build_kind here.
* **NEEDS_HUMAN/WAIT:** caller asked for something that requires an explicit decision (e.g., “use ACTIVE as-of what?”) and policy doesn’t define a resolver.

### Drift boundary (what is *not* allowed)

* S1 “choosing” feature versions based on convenience.
* S2 silently substituting “latest” or silently changing as-of time between retries.

---

## Internal Join I2 — S2 → S3

### “ResolveReplayBasis” handshake (ReplaySelector → Resolved ReplayBasis + SourcePlan)

### Purpose

Turn a pinned replay intent into a **replayable slice** of the admitted stream, respecting the platform history overlay:

* Archive is **continuation** of EB, not a second truth.
* Replay basis is **explicit** and recorded.
* Watermarks/offsets are **monotonic** and meaningful.

### Authority boundary (my pin)

* **S2 owns the requirement**: “basis must be offsets/checkpoints + recorded.”
* **S3 owns feasibility + source planning + completeness evidence** (EB vs Archive cutover, gaps, overlap).

### Handshake payloads

**I2.Request = ReplayBasisRequest**

* `stream_id`: `fp.bus.traffic.v1`
* `basis_spec`: either

  * explicit `partition_offset_ranges`, or
  * `time_window` (must resolve deterministically → offsets; record mapping)
* `strictness`: `FAIL_CLOSED` vs `ALLOW_UNCHECKABLE` (parity rebuild often allows UNCHECKABLE; dataset build typically fail-closed)
* `env_profile_id` / retention+archive capabilities (operational envelope info)

**I2.Response = ReplayBasisResolution**

* `status`: `RESOLVED | UNSATISFIABLE | INCOMPLETE | UNCHECKABLE`
* `resolved_basis`: `{partition -> [from_offset, to_offset)}`
* `source_plan`: per partition segments: `EB` or `ARCHIVE` (hot vs cold)
* `basis_hash` (stable digest of resolved basis)
* `completeness_evidence`: (conceptual) pointers/checkpoints/digests sufficient to justify “this basis is complete”
* `notes`: “archive required”, “gap detected”, “overlap dedup by event_id”, etc.

### Hard invariants

1. **Offsets/watermarks are the basis**; time is only a selector.
2. **Archive behaves “as if EB.”** Same logical events; same event identity; replay continuity preserved.
3. **No silent partial success.** If basis can’t be satisfied, the resolution must say UNSATISFIABLE/INCOMPLETE/UNCHECKABLE explicitly.
4. **Watermarks don’t lie.** Backfills/new arrivals create new offsets; we never “reinterpret history.”

### Env ladder notes (what can differ)

Retention and archive availability differ by env profile, but **basis semantics do not**.
So in local you may hit UNSATISFIABLE more often (no archive), but you never change the meaning of “basis”.

---

## Internal Join I3 — S2 → S4

### “LabelAsOfContract” handshake (LabelAsOfSpec → LabelQueryPlan contract)

### Purpose

Make label leakage control explicit and reproducible:

* labels are timelines
* you can produce “knew-then” vs “know-now”
* you never implicitly join “latest labels”.

### Authority boundary (my pin)

* **S2 owns the as-of rule** (the policy and the cutoff values).
* **S4 owns the interpretation** against the Label Store and the mechanics of constructing a label view later.

### Handshake payloads

**I3.Request = LabelAsOfRequest**

* `label_as_of_spec`:

  * `observed_time_cutoff_utc` (explicit)
  * `posture`: `KNEW_THEN | KNOW_NOW` (or equivalent)
  * interpretation rule: e.g., “latest observed assertion as-of; apply by effective_time”
* `label_scope`: which subjects/label types are in-scope for this build (derived from BuildIntent scope + dataset kind)
* `strictness`: `REQUIRE_LABELS | ALLOW_UNLABELED` (dataset_kind dependent)

**I3.Response = LabelAsOfAck**

* `status`: `ACCEPTED | REJECTED | PARTIAL_SUPPORTED`
* optional `label_query_plan_hint`: “requires subject mapping X”, “requires label types Y”, etc.

### Hard invariants

1. **As-of is explicit** (cutoff is a concrete timestamp, never implicit).
2. **Timelines, not mutable values** (append-only semantics; interpretation is rule-based).
3. **If labels are required and unavailable, fail closed** (unless the dataset kind explicitly permits unlabeled output and the manifest will state that).

### Drift boundary (not allowed)

* “Just join the latest label per entity.”
* S4 deciding its own as-of cutoff.

---

## Internal Join I4 — S2 → S5

### “ExecutionPins” handshake (FeatureVersionSet + Scope + OutputKind → Compatibility/Execution contract)

### Purpose

Guarantee that the reconstruction engine (S5) runs under **frozen meaning**:

* exact feature definitions/versions
* exact scope and output kind
* parity rebuilds use the versions recorded in provenance (or declare UNCHECKABLE).

### Authority boundary (my pin)

* **S2 owns which feature profile revision is in force** (and records it).
* **S5 owns whether it can execute that profile** (compatibility checks), but it may not substitute alternatives.

### Handshake payloads

**I4.Request = ExecutionPins**

* `feature_version_set`:

  * `feature_profile_ref` (resolved revision + digest)
  * (optional) “hash/canonicalization ruleset ref” if it is part of the profile (prevents cross-run drift)
* `scope`: entity/event types, ContextPins filters, dataset shaping scope
* `output_kind`: per-event / per-entity / per-window, plus any declared schema posture

**I4.Response = ExecutionPinsAck**

* `status`: `COMPATIBLE | INCOMPATIBLE | REQUIRES_UPGRADE | UNCHECKABLE_FOR_PARITY`
* `reasons`: missing feature group versions, incompatible schema expectations, etc.

### Hard invariants

1. **No “latest by default.”** A concrete revision/digest must be used and recorded.
2. **Parity rebuilds must match the recorded version set** or return UNCHECKABLE (not “close enough”).
3. **Compatibility fails closed** (or explicit safe fallback if you later decide to add one, but never silent partial compatibility).

### Drift boundary (not allowed)

* S5 silently substituting a different feature profile revision because it can’t find the requested one.
* S2 changing version set mid-run.

---

## One compact view of I1–I4 (what we just pinned)

```
S1 (job lifecycle, request_id) 
        |
        | I1: BuildIntent → PlanResult (pins frozen)
        v
S2 (meaning pins authority)
   |      |      |
   |I2    |I3    |I4
   v      v      v
S3      S4      S5
(replay) (labels) (feature exec)
```

**Design-authority declaration:**
If an internal design later tries to (a) start replay before pins are frozen, (b) treat time windows as the basis, (c) join latest labels implicitly, or (d) float feature versions—**that is out of bounds** with the platform network and we reject it immediately.

---

Locked — illuminating **A.I5 → A.I8** as **production-grade internal handshakes** between still-opaque subnetworks. I’m going to **pin what is in-bounds vs drift** for each join, because these four edges are where most hidden assumptions creep in (ordering, duplicates, label leakage, publish atomicity, provenance completeness).

---

# A.I5 — S3 → S5

## Replay stream feed (ReplaySlice + ReplayReceipts)

### Purpose

Deliver the **admitted fact replay slice** described by the resolved ReplayBasis **as a partitioned stream**, so S5 can reconstruct features without assuming a global order.

### Authority boundary (pinned)

* **S3 is authoritative** for: *what offsets were actually replayed*, *what source was used (EB vs Archive)*, and *what completeness evidence exists*.
* **S5 is authoritative** for: *how replayed facts are interpreted into feature state*, but it may not “patch” gaps or invent ordering guarantees not present in the feed.

### Handshake payload (conceptual)

**I5.ReplaySlice** (delivered as an iterator/stream or micro-batches):

* `stream_id` (logical `fp.bus.traffic.v1`)
* `partition_id`
* `slice_id` (stable id for this slice; enables idempotent re-processing)
* `offset_range`: `[from_offset, to_offset)` (half-open)
* `source`: `EB | ARCHIVE` (or both with explicit “overlap mode”)
* `records[]`: each is a CanonicalEventEnvelope (already admitted)

  * must include `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, optional ContextPins
* optional `decode_receipts` (count of malformed/unreadable records; should normally be 0 in admitted traffic)

**I5.ReplayReceipts** (per slice and roll-up):

* `basis_hash` (ties back to the resolved basis)
* `delivered_offsets`: actual contiguous subranges delivered
* `counts`: events delivered, per event_type counts (optional)
* `overlap_dedupe_report`: if EB+Archive overlap exists, how duplicates were handled
* `completeness_evidence_refs`: (by-ref) proofs/checkpoints that justify “this range is complete”

### Hard invariants (non-negotiable)

1. **Partition order only.** Within a partition, offsets are strictly non-decreasing; across partitions, **no global order is implied**.
2. **No silent gaps.** If S3 cannot deliver some offsets that are part of the resolved basis, it must surface that explicitly (error / INCOMPLETE / UNCHECKABLE), not skip.
3. **Duplicates are expected.** At-least-once semantics mean duplicates may occur; the replay feed must not pretend “exactly once.”
4. **Overlap discipline (EB + Archive).** If both sources can yield the same offset range, the rule is:

   * **event identity is `event_id`**, and overlap must be handled deterministically (either S3 de-dupes before emitting, or it flags duplicates explicitly so S5 can de-dupe deterministically).
     What’s out-of-bounds is “sometimes EB wins, sometimes Archive wins” without recording it.

### Failure classes (what S5 must be prepared to receive)

* `REPLAY_IO_ERROR` (source unavailable)
* `DECODE_ERROR` (should be rare for admitted traffic; if it happens it’s a platform incident)
* `BASIS_GAP_DETECTED` (retention boundary / missing archive segment)
* `UNSUPPORTED_EVENT_SCHEMA` (schema drift—should be caught earlier, but surfaced here if needed)

### Drift boundary (not allowed)

* S5 assuming “ts_utc order” is the same as replay order.
* S3 silently dropping corrupted records and still claiming completeness.

---

# A.I6 — S4 → S5

## Label view feed (LabelView + coverage diagnostics)

### Purpose

Provide **leakage-safe labels** aligned to the pinned LabelAsOfSpec, so S5 can shape supervised datasets (and/or compute evaluation targets) without ever joining “latest labels.”

### Authority boundary (pinned)

* **S2** pins the as-of rule and cutoff; **S4** executes it.
* **S4 is authoritative** for “these are the labels consistent with `LabelAsOfSpec` for this scope.”
* **S5 is not allowed** to re-query labels ad-hoc or loosen the as-of boundary.

### Handshake payload (conceptual)

**I6.LabelView**:

* `label_as_of_spec` (echoed back: posture + observed_time cutoff + interpretation rule id)
* `label_scope` (what subject types / label types are included)
* `labels[]` as either:

  * **resolved labels** (already collapsed per subject per rule), or
  * **assertion timeline slices** (and S5 applies the final collapse rule)

  **My v0 pin:** S4 should deliver **resolved labels** (so the leakage rule lives in one place).
* each label record includes:

  * `subject_key` (event_id / entity_id / case_id etc — must match what S5 expects)
  * `label_type`
  * `label_value` (+ optional confidence)
  * `effective_time`
  * `observed_time`
  * `provenance_ref` (by-ref, if needed)

**I6.LabelReceipts / diagnostics**

* `coverage` (how many subjects in-scope have labels; rates by label type)
* `missing_subject_classes` (e.g., no mapping for some subject keys)
* `label_store_watermark` (optional: “label store state as-of” marker for reproducibility)
* `query_evidence_ref` (by-ref query receipt / stats)

### Hard invariants

1. **Observed-time cutoff is enforced exactly** for “knew-then” posture: all included labels must satisfy `observed_time <= cutoff`.
2. **Effective vs observed time are not interchangeable.** Effective time controls *what the label applies to*; observed time controls *what was knowable*.
3. **No silent label dropping** when labels are required. If label coverage is too low or label types missing, the output must be explicit so S5/S6 can decide to fail closed (or publish an “unlabeled” dataset kind only if intent allows it).
4. **Deterministic subject keys.** If labels are keyed by entity_id and S5 expects event_id, that mismatch is a build-breaking incompatibility (must not be papered over).

### Failure classes

* `LABEL_SCHEMA_INCOMPATIBLE`
* `AS_OF_SPEC_INVALID`
* `SUBJECT_MAPPING_MISSING`
* `LABEL_STORE_UNAVAILABLE`
* `LABELS_REQUIRED_BUT_UNSATISFIABLE`

### Drift boundary (not allowed)

* S5 “helpfully” joining the newest label state.
* S4 returning different label resolutions for the same as-of spec without an explicit change in label store state marker.

---

# A.I7 — S5 → S6

## Materialization stream (DatasetDraft / SnapshotDraft)

### Purpose

Hand S6 everything it needs to **publish atomically** under `ofs/...` and to build a correct DatasetManifest, without S6 having to understand feature semantics.

### Authority boundary (pinned)

* **S5 is authoritative** for: the *content* computed under a FeatureVersionSet (features, snapshots, shaped tables) and the *schema* of that output for this build.
* **S6 is authoritative** for: publication rules (immutability, atomic manifest commit, idempotent retries), and is **not allowed** to modify content semantics.

### Handshake payload (conceptual)

**I7.DatasetDraft** (can be chunked/sharded):

* `plan_id` (ties back to pinned plan)
* `dataset_kind` (per-event / per-entity / per-window / snapshot)
* `schema_ref` (versioned schema identifier for the output)
* `shards[]` (each shard describes a materialization unit)

  * `shard_id` (deterministic)
  * `row_count`
  * `partitioning_keys` used in the shard (if any)
  * `content_digest` (or “digest candidate” if computed after serialization)
  * `staging_ref` or `write_handle` (depends on write model—see below)
* `summary_stats` (counts, min/max ts_utc, coverage metrics, feature list hash)
* optional `snapshot_hashes` (if S7 parity later needs them)

### Publication model (designer pin)

To keep internal design flexible but still safe, I’m pinning only the **publication boundary**, not the write mechanism:

* **In-bounds model A:** S6 writes all final objects; S5 streams content to S6 (S6 serializes).
* **In-bounds model B (more common at scale):** S5 writes shards to object storage under a **build-scoped staging namespace**, and S6 “publishes” by writing the manifest that references them (objects are considered unpublished until manifest exists).

**Out-of-bounds:** S5 writing to “final” paths that downstream might discover without the manifest, or S6 publishing a manifest that points to incomplete shards.

### Hard invariants

1. **Dataset is not real until the manifest is committed.** I7 must support S6’s atomic publish rule.
2. **Deterministic shard identity.** Retries must not produce semantically different shard layouts without a declared new plan_id.
3. **Schema and feature-set are pinned.** Draft must carry enough info to prove it matches the FeatureVersionSet/S2 pins (e.g., feature profile ref hash included in summary).
4. **Digest posture is explicit.** If digests are provided, S6 must verify; if not, S6 must compute them and record.

### Failure classes

* `DRAFT_SCHEMA_MISMATCH`
* `SERIALIZATION_FAILURE`
* `DIGEST_MISMATCH` (if shard content doesn’t match declared digest)
* `INCOMPLETE_SHARD_SET` (missing shard that draft promised)

### Drift boundary (not allowed)

* Publishing a manifest without verifying shard completeness.
* S6 “helpfully” reshaping the dataset (changing partitioning/order) in ways that change digests without declaring it.

---

# A.I8 — (S2 + S3 + S4) → S6

## Provenance bundle to manifest builder (PinnedPlan + ReplayReceipts + LabelReceipts)

### Purpose

Give S6 the **full provenance bundle** required to construct the DatasetManifest as the unit of truth — meaning S6 should be able to build the manifest without asking any subnetwork for “extra context.”

### Authority boundary (pinned)

* **S2 is authoritative** for meaning pins: scope, feature versions, label as-of, output spec.
* **S3 is authoritative** for replay completeness and the resolved basis actually delivered.
* **S4 is authoritative** for label as-of resolution and label coverage posture.
* **S6 is authoritative** for *manifest construction + publication*, and must fail closed if the provenance bundle is inconsistent.

### Handshake payload (conceptual)

**I8.PinnedPlan (from S2)**

* `plan_id`
* `scope` (ContextPins filters, entity/event types)
* `feature_version_set` (resolved `feature_profile_ref` + digest)
* `label_as_of_spec` (explicit)
* `output_spec` (dataset_kind + shaping intent)
* `policy_rev` + `env_profile_id`

**I8.ReplayReceipts (from S3)**

* `basis_hash`
* `resolved_basis` summary (partition ranges)
* `source_plan` summary (EB vs Archive contribution)
* `completeness_evidence_refs`
* `anomalies` (overlap, duplicates report, gaps)

**I8.LabelReceipts (from S4)**

* `label_as_of_spec` echo
* `coverage` + `label_types_present`
* optional `label_store_state_marker` (for reproducibility)
* `anomalies` (missing mapping, missing types)

### Manifest construction rules (designer pins)

1. **Consistency checks are mandatory.** S6 must reject building a “success-shaped” manifest if:

   * plan_id doesn’t match basis_hash/receipts,
   * replay is incomplete for a required dataset build,
   * label receipts violate the pinned as-of rule,
   * feature profile ref is missing/unresolved.
2. **Manifest must be self-sufficient.** MF must be able to train from a manifest without scanning other stores to “figure out what happened.”
3. **Explicit incompleteness posture.** If the build kind permits UNCHECKABLE/INCOMPLETE (parity or forensic), the manifest (or parity artifact) must declare that state explicitly.

### Drift boundary (not allowed)

* S6 “making up” missing provenance fields (e.g., filling feature versions with “current active”).
* S6 publishing a manifest that doesn’t record replay basis and label as-of boundary.

---

## One compact view of I5–I8 (what we just pinned)

```
S3 ReplayUnifier  --I5-->  S5 Reconstruct/Shape  --I7-->  S6 Publish/Manifest
S4 LabelResolver  --I6-->          ^                      ^
        |                          |                      |
        +------------I8------------+----(S2 pins)---------+
```

**Design-authority declaration:**
If later internal designs try to (a) imply global ordering, (b) treat labels as “latest,” (c) publish without a manifest, or (d) allow provenance gaps to be silently filled — that is **out of bounds** with the outer network and must be rejected.

---

Locked — illuminating **A.I9 → A.I13** as *production handshakes between still-opaque subnetworks*, with me explicitly declaring what’s **in-bounds** vs **drift** relative to the outer network laws (manifest-as-truth, explicit basis/as-of/versions, immutability, declared backfills, optional control facts, OTLP everywhere).

I’ll keep the same structure per join.

---

## A.I9 — S6 → S1

### Publish receipt handshake (close lifecycle + idempotency)

### Purpose

Once S6 has *atomically* published (or decided not to publish), S1 must be able to:

* close the job lifecycle deterministically,
* return stable outputs to the caller/orchestrator,
* record whether the run produced **new outputs** vs **reused** existing ones.

### Authority boundary (pinned)

* **S6 is the only authority** on “is the dataset published?” because publication truth is defined by “DatasetManifest exists and is committed.”
* **S1 is the only authority** on “is the job done?” (run lifecycle state), but it must not reinterpret publish outcomes.

### Handshake payload (conceptual)

**I9.PublishReceipt** must contain, at minimum:

* `request_id` (job idempotency)
* `plan_id` (meaning-pins digest)
* `publish_outcome`:

  * `NEW_PUBLISHED` | `ALREADY_PUBLISHED` | `SUPERSEDED_PUBLISHED` | `FAILED_NO_PUBLISH`
* `dataset_id` (stable dataset identity)
* `dataset_manifest_ref` (by-ref pointer; the primary output)
* `output_refs[]` (by-ref pointers to materials / parity report if written)
* `basis_hash`, `feature_profile_ref`, `label_as_of_spec` (summary pins for quick correlation; full pins live in the manifest)
* `status_class`:

  * `COMPLETE_SUCCESS` | `INCOMPLETE_EXPLICIT` | `UNCHECKABLE_EXPLICIT` | `FAILED`
* `failure_summary` (only if failed; includes failure class + evidence refs)

### Hard invariants (non-negotiable)

1. **Receipt is emitted only after commit.** If S6 can’t guarantee the manifest is committed, it cannot emit a “published” receipt.
2. **Idempotency rule:** same pinned intent ⇒ same `dataset_manifest_ref` (or explicitly declared supersession/backfill). No silent “v2” for the same plan.
3. **S1 must not “infer success” from partial artifacts.** Only a committed manifest counts.

### Failure classes (what S1 must handle)

* `PUBLISH_CONFLICT` (race: someone else published same plan concurrently)
* `COMMIT_FAILED` (staging wrote, manifest commit failed)
* `DIGEST_MISMATCH` (materials don’t match expected digests)
* `PROVENANCE_INCOMPLETE` (cannot build a self-sufficient manifest → fail closed)

### Drift boundary (not allowed)

* S1 scanning `ofs/...` to “find outputs” if I9 isn’t returned.
* S6 returning “success” without a manifest pointer.

---

## A.I10 — S6 → S7

### Signal-input handshake (parity/gov/telemetry inputs without touching core build)

### Purpose

Feed S7 enough **authoritative outputs + pins** to emit:

* optional governance facts (`fp.bus.control.v1` announcements),
* parity artifacts/outcomes (if requested),
* OTLP telemetry (traces/metrics/logs),
  without S7 needing to read or recompute the dataset.

### Authority boundary (pinned)

* **S6 is authoritative** for: manifest ref, dataset identity, publication outcome, output refs/digests.
* **S7 is authoritative** for: what signals get emitted (policy-driven), and the exact external envelopes for those signals.

### Handshake payload (conceptual)

**I10.SignalInputs**:

* `publish_receipt_core` (the parts of I9 needed for signalling)

  * `dataset_id`, `dataset_manifest_ref`, `publish_outcome`, `status_class`
* `signal_policy_context` (what signals are enabled in this env/profile)

  * e.g., “emit DatasetPublished”, “emit ParityResult”, etc.
* `parity_context` (optional):

  * `parity_anchor_ref` (if parity requested)
  * `target_snapshot_hash/ref` (from anchor)
  * `rebuilt_snapshot_hash/ref` (if available from S5/S6 outputs)
* `evidence_refs[]` (by-ref): parity reports, completeness receipts, publish logs, etc.

### Hard invariants

1. **S7 never publishes new dataset truth.** It only announces what S6 already committed (by-ref).
2. **Signals are announcements, not transports.** Control bus carries refs + small summaries, never bulk.
3. **Parity outcomes must be explicit** (MATCH/MISMATCH/UNCHECKABLE) and tied to the pinned basis+versions recorded in provenance.

### Drift boundary (not allowed)

* S7 re-reading EB/Archive/Label Store to “double-check” and accidentally creating a second truth path.
* S7 emitting “DatasetPublished” for an uncommitted/staged-only run.

---

## A.I11 — S7 → S1

### External signalling summary (make the run ledger reflect what was announced)

### Purpose

Close the loop so S1’s run ledger (job record) reflects:

* what signals were emitted externally,
* any parity outcome,
* what correlation IDs exist for tracing across systems.

### Authority boundary (pinned)

* **S7 is authoritative** for “what I emitted” (or attempted to emit).
* **S1 is authoritative** for recording run completion state and returning the final “result view” to caller/orchestrator.

### Handshake payload (conceptual)

**I11.SignalSummary**:

* `request_id`, `plan_id`, `dataset_id`
* `signals_emitted[]`:

  * `signal_type` (DatasetPublished / BuildFailed / BackfillDeclared / ParityResult / etc.)
  * `signal_ref` (event id / receipt ref / by-ref pointer)
  * `emit_status` (SENT | SKIPPED_BY_POLICY | FAILED_TO_SEND)
* `parity_outcome` (optional): MATCH/MISMATCH/UNCHECKABLE + parity evidence ref
* `telemetry_correlation`:

  * trace/span root IDs (or equivalent correlation token)
* `warnings[]` (non-fatal anomalies surfaced for ops)

### Hard invariants

1. **Run record must not imply signals that weren’t emitted.** If emission failed, it is recorded as such.
2. **Parity result (if attempted) must land in the run record** even if control-bus emission is disabled (object refs are still acceptable).

### Drift boundary (not allowed)

* S1 claiming “published” if signal emission failed but publish succeeded (publish truth comes from I9; signalling is separate and explicitly recorded).

---

## A.I12 — S1/S2 ↔ S6

### Preflight existence check (short-circuit idempotency + cost control)

### Purpose

Avoid replaying history and rebuilding datasets when the same pinned intent has already produced a committed manifest.

This is the internal expression of **L3 immutability/idempotency** at “job start.”

### Authority boundary (pinned)

* **S2 produces the stable key** for “what would this build mean?” (plan_id + pins).
* **S6 is authoritative** for “does a committed manifest already exist for this plan?” (publication truth).

### Handshake payload (conceptual)

**I12.Query (from S1/S2 to S6)**:

* `plan_id` (primary key)
* `dataset_kind` + `output_spec` (so we don’t collide different output kinds)
* summary pins: `basis_hash` (if already resolved), `feature_profile_ref`, `label_as_of_spec` (optional but useful sanity)
* `reuse_policy`:

  * `ALLOW_REUSE_IF_COMPLETE`
  * `ALLOW_REUSE_IF_EXPLICIT_INCOMPLETE` (rare; mostly for forensic)
  * `DISALLOW_REUSE` (force rebuild)

**I12.Response (from S6)**:

* `found`: yes/no
* if yes:

  * `dataset_manifest_ref`
  * `dataset_id`
  * `status_class` (COMPLETE_SUCCESS vs INCOMPLETE_EXPLICIT vs FAILED)
  * `superseded_by` (if this dataset has been superseded by a declared backfill)
  * `provenance_summary` (basis_hash, versions, as-of) for quick consistency check

### Hard invariants

1. **Reuse is only allowed from a committed manifest** with compatible status (normally COMPLETE_SUCCESS).
2. **Backfill/supersession is explicit.** If a newer declared dataset supersedes this plan in policy terms, I12 must report that rather than letting S1 “accidentally” reuse old truth.
3. **Preflight is advisory, not a lock.** Two jobs may race; final correctness is enforced at publish time (S6 must handle commit conflicts deterministically).

### Env ladder notes

* Local: you may disable reuse to simplify iteration, but semantics must remain (if enabled, it must behave the same).
* Prod: reuse is valuable; commit-race handling is mandatory.

### Drift boundary (not allowed)

* S1 scanning object store for “something similar.”
* S6 returning “found” based on staged/partial artifacts.

---

## A.I13 — S3 ↔ S6

### Staged commit receipts (gate atomic publish on replay completeness)

### Purpose

Make sure S6 only commits a DatasetManifest when it has **proof the replay slice is complete** for the declared basis, and that the materials correspond to that basis.

This prevents the worst production failure: “manifest says complete, but replay silently missed partitions/offsets.”

### Authority boundary (pinned)

* **S3 is authoritative** for replay completeness evidence (what offsets were delivered, gaps/overlap, EB vs Archive sourcing).
* **S6 is authoritative** for the publish decision: it must refuse to commit a “complete” manifest without required receipts.

### Handshake payload (conceptual)

**I13.SegmentReceipt (S3 → S6)** (per partition or per slice):

* `basis_hash`, `plan_id`
* `partition_id`
* `delivered_offset_ranges` (actual delivered)
* `source` (EB/ARCHIVE)
* `completeness_evidence_ref` (by-ref checkpoint/segment manifest)
* `anomalies` (gaps, overlap, decode errors)

**I13.Ack / GateDecision (S6 → S3)**:

* `receipt_accepted` yes/no
* if no: `reason` (mismatch with plan basis, missing evidence, etc.)
* optional: `required_receipts_missing[]` (so S3 knows what remains)

### Hard invariants

1. **Receipts must match the pinned basis** (basis_hash/plan_id).
2. **No “complete manifest” without complete receipts** (unless the build kind explicitly allows INCOMPLETE/UNCHECKABLE and that state is written explicitly into the manifest).
3. **Overlap/gap handling is explicit.** If overlap dedupe occurred, it must be recorded as an anomaly/evidence element.

### Failure classes

* `RECEIPT_BASIS_MISMATCH`
* `MISSING_REQUIRED_RECEIPTS`
* `COMPLETENESS_UNPROVABLE` (archive gap; retention boundary)
* `ANOMALY_FATAL` (decode errors on admitted stream)

### Drift boundary (not allowed)

* S6 committing a manifest based on “best effort replay.”
* S3 claiming completeness without evidence refs.

---

## Compact map of I9–I13 (what we just illuminated)

```
S6 Publisher  --I9-->  S1 Orchestrator
     |
     +--I10--> S7 Signals --I11--> S1

S1/S2 <----I12----> S6   (preflight reuse / idempotency)

S3 Replay <----I13----> S6  (completeness receipts gating publish)
```

### Designer boundary call (authoritative)

If any future internal design:

* lets S1/S7 “discover outputs” without manifest refs,
* allows “complete” publication without replay completeness receipts,
* or treats reuse/backfill as implicit rather than explicit,
  it is **out of bounds** with the platform network and we reject it immediately.

---

Locked. We’ll illuminate **IP1–IP4** as **production internal routes through the OFS internal graph**, using the internal joins we just pinned (**I1–I13**) — but still treating the subnetworks **S1–S7 as opaque**.

I’ll do this in a way that’s actually useful later: for each IP, you’ll get:

* the **route skeleton**
* the **step-by-step** (which internal joins fire, in what order)
* the **branch points** (where production forks happen)
* the **required outputs** (what “done” means)
* the **allowed failure posture** (fail-closed vs UNCHECKABLE)
* the **idempotency story** (where I12/I9/I13 show up)
* the **drift tripwires** (what would violate the outer boundary)

---

## Shared primitives (so IP1–IP4 don’t drift)

These are common across all internal paths:

* **request_id**: job idempotency key (S1-owned)
* **plan_id**: stable digest of *meaning pins* (S2-owned; includes basis/as-of/versions/scope/output kind + policy/build rev)
* **basis_hash**: digest of the resolved replay basis (S3-owned; referenced everywhere)
* **dataset_manifest_ref**: the *published truth pointer* (S6-owned)
* **status_class**: COMPLETE_SUCCESS | INCOMPLETE_EXPLICIT | UNCHECKABLE_EXPLICIT | FAILED (S6/S1 owned with S3/S4 evidence)

**Design pin (important for backfills):** plan_id must include a **meaning-affecting “build provenance stamp”** (e.g., `ofs_build_profile_rev` or image digest) so a bug-fix rebuild doesn’t accidentally “reuse” an old dataset just because the BuildIntent looks similar. This stays consistent with “policy/config revs are outcome-affecting and must be recorded.” (We’ll formalize later; for now it’s a pinned behavior.)

---

# IP1) Standard dataset build (training/eval)

**Route:** `S1 → S2 → (S3 || S4) → S5 → S6 → S7 → S1`

## What it’s for

Produce a **train/eval dataset** that is:

* derived from the **admitted fact stream** (EB + optional Archive),
* joined with **labels using explicit as-of semantics**,
* computed with **version-locked feature definitions**,
* published as **immutable artifacts + a DatasetManifest**,
* and optionally announced via control facts and telemetry.

## Step-by-step (internal joins)

### 0) Trigger + idempotency preflight (cost control)

* **S1 receives BuildIntent** (dataset_build).
* **S1 calls S2 (I1)** to get a pinned plan (or at least plan_id derivation).
* **Optional but production-real:** **I12 preflight** (S1/S2 ↔ S6)

  * If a committed manifest already exists for this `plan_id` and reuse policy allows, **short-circuit** to completion:

    * S6 returns `ALREADY_PUBLISHED` + manifest ref
    * S1 closes run (no replay, no compute)
  * If not found: continue.

### 1) Pin everything up front (no implicit defaults)

* **I1 (S1 → S2):** BuildIntent → PlanResult
  S2 freezes:

  * scope selectors (ContextPins filters if any),
  * label_as_of_spec (explicit cutoff/posture),
  * feature_profile_ref (resolved revision/digest),
  * output_spec (dataset kind, shaping intent),
  * replay selector (offset basis preferred; time-window allowed only as selector).

### 2) Resolve replay basis + start parallel fanout

* **I2 (S2 → S3):** resolve ReplayBasis
  S3 resolves to explicit per-partition offset ranges and source plan (EB vs Archive).
* **I3 (S2 → S4):** confirm LabelAsOfSpec + label scope

Now the classic production fanout:

### 3a) Replay acquisition begins

* S3 begins streaming replay slices to S5 via **I5 (S3 → S5)**.
* In parallel, S3 emits completeness receipts to S6 via **I13 (S3 ↔ S6)** (or buffers them for later delivery).

### 3b) Label view resolution begins

* S4 constructs the label view per as-of rule and feeds it to S5 via **I6 (S4 → S5)**.

### 4) Feature reconstruction + dataset shaping

* Before processing, S5 must ack compatibility with pinned versions:

  * **I4 (S2 → S5):** ExecutionPins (feature versions + scope + output kind)
* S5 consumes replay slices (I5) + label view (I6), producing dataset drafts.

### 5) Publish atomically (manifest-driven truth)

* S5 sends dataset drafts/shards to S6 via **I7 (S5 → S6)**.
* S6 receives the full provenance bundle via **I8 (S2+S3+S4 → S6)**.
* S6 gates commit on replay completeness via **I13**.
* **Commit rule:** dataset is “real” only when DatasetManifest is committed.

### 6) Close the run and optionally announce

* S6 returns **I9 (S6 → S1)** publish receipt: NEW_PUBLISHED / ALREADY_PUBLISHED, manifest ref, etc.
* S6 sends **I10 (S6 → S7)** signal inputs.
* S7 emits:

  * OTLP telemetry (always)
  * optional `fp.bus.control.v1` announcements (DatasetPublished / BuildFailed)
  * returns **I11 (S7 → S1)** signal summary
* S1 closes lifecycle and returns outputs to caller/orchestrator.

## Branch points (production forks)

* **Within retention vs beyond retention:** S3 chooses EB only vs EB+Archive.
* **Label required vs unlabeled dataset kind:** depends on output_spec.
* **Reuse vs rebuild:** I12 preflight can short-circuit.
* **Strictness:** dataset builds are normally **FAIL_CLOSED** if replay or labels are unsatisfiable.

## “Done” outputs

* **DatasetManifest ref** (primary)
* by-ref dataset materials under `ofs/...`
* optional evidence refs (coverage stats, completeness receipts)

## Drift tripwires (not allowed)

* S5 assuming global ordering across partitions.
* labels joined “latest”
* publishing without manifest
* silent partial dataset when history/labels missing

---

# IP2) Parity rebuild (shadow twin)

**Route:** `S1 → S2(uses ParityAnchor) → S3 → S5 → S6 → S7(parity) → S1`

## What it’s for

Prove (or disprove) that **offline rebuild under the same basis + versions** yields the same **feature snapshot hash** as online, using a DLA/DF/OFP provenance anchor.

## Step-by-step (internal joins)

### 0) Trigger + optional preflight reuse

* S1 receives BuildIntent (parity_rebuild) with `parity_anchor_ref`.
* **I1:** S1 → S2 (plan-and-pin)
* **Optional I12:** if this parity target has already been rebuilt under identical pins, reuse prior parity artifacts.

### 1) Pin from the anchor (no guessing)

* In S2, parity anchor is treated as authoritative input for:

  * `input_basis` (watermark/offset basis)
  * `feature_profile_ref` (versions used online)
  * target `feature_snapshot_hash`
* If anchor lacks basis/versions/hash: S2 must pin the run as **UNCHECKABLE** (not “try around that time”).

### 2) Replay and rebuild

* **I2:** S2 → S3 resolve replay basis (usually already offset-based from the anchor; still verify feasibility)
* S3 feeds replay slices via **I5**.
* **I4:** S2 → S5 execution pins (must match anchor versions exactly or parity becomes uncheckable).
* S5 reconstructs the snapshot(s) required for parity.

### 3) Publish parity artifacts and compute parity outcome

* S6 publishes:

  * a parity report artifact (by-ref) and (optionally) the rebuilt snapshot artifact.
  * It may publish a “manifest-like” record even if it’s not a training dataset (still pinned by basis/versions).
* **I10:** S6 → S7 signal inputs include:

  * target hash/ref (from anchor)
  * rebuilt hash/ref (from rebuild outputs)
* S7 produces ParityResult: **MATCH / MISMATCH / UNCHECKABLE** and returns it via **I11**.

## Failure posture (pinned)

Parity rebuild is allowed to be **UNCHECKABLE_EXPLICIT** when:

* history cannot be replayed (retention + archive gap),
* feature versions unavailable,
* anchor incomplete.

It must never “pretend match” by substituting versions or widening basis.

## Drift tripwires

* “Close enough” parity (wrong versions, wrong basis)
* converting UNCHECKABLE into FAIL without making it explicit (parity’s value is the explicit reason)

---

# IP3) Forensic snapshot rebuild (audit/support)

**Route:** `S1 → S2 → S3 → S5 → S6 → S7(optional) → S1`

## What it’s for

Rebuild a snapshot for investigation/debugging when you **don’t have** (or don’t need) an online parity anchor:

* “What did the features look like as-of X for entity Y?”
* “Recompute feature state for this window using profile revision R.”

## Step-by-step (internal joins)

### 0) Trigger

* S1 receives BuildIntent (forensic_rebuild):

  * explicit scope (entity/event-type)
  * explicit as-of (or basis selector)
  * explicit feature profile selector

### 1) Pin everything (still no implicit defaults)

* **I1:** S1 → S2 pinned plan
* **I2:** S2 → S3 resolve basis (may be offset-based or time selector → offsets)
* **I4:** S2 → S5 execution pins

### 2) Replay + rebuild snapshot

* **I5:** S3 → S5 replay slices
* S5 reconstructs the requested snapshot(s).

### 3) Publish + optional signalling

* S6 publishes snapshot artifacts and a pinned record (manifest-like output).
* S7 may emit:

  * OTLP telemetry always
  * optional governance facts if policy wants forensic runs recorded
  * parity is usually not computed unless explicitly requested (no anchor).

## Failure posture

Forensics may allow **INCOMPLETE_EXPLICIT** more often than dataset build:

* you might request “best effort rebuild for what’s available.”
  But it must be explicit and never masquerade as a complete training dataset.

## Drift tripwires

* making forensic outputs look like training datasets without declaring incomplete posture
* allowing “latest feature profile” implicitly (forensics must be explicit or explicitly resolved + recorded)

---

# IP4) Backfill rebuild (declared correction)

**Route:** `S1(backfill intent) → S2 → (S3 || S4) → S5 → S6(new manifest) → S7(backfill fact) → S1`

## What it’s for

Regenerate **derived truth** (offline datasets/snapshots) under a declared correction:

* feature definition fix,
* OFS build logic fix,
* archive gap resolved,
* label rule correction,
  without mutating primary truth (EB events, label timelines, registry history).

## Step-by-step (internal joins)

### 0) Trigger (declared)

* S1 receives BuildIntent (backfill_rebuild) containing:

  * explicit scope + basis selectors
  * reason code / ticket / governance metadata
  * optional “supersedes dataset_id/manifest_ref” target(s)

### 1) Pin with backfill metadata + no accidental reuse

* **I1:** S1 → S2 pinned plan (includes backfill intent metadata + build provenance stamp)
* **I12 policy:** **DISALLOW_REUSE unless the plan_id already represents the corrected build**

  * Backfill exists to produce *new derived outputs*; reuse is only valid if it points to the already-corrected manifest.

### 2) Rebuild mechanics (same as dataset build)

* **I2:** S2 → S3 basis resolution (EB vs Archive)
* **I3:** S2 → S4 label as-of resolution (if supervised dataset)
* **I4:** S2 → S5 execution pins
* **I5/I6:** replay + labels → S5
* **I7/I8/I13:** draft + provenance + completeness receipts → S6 publish

### 3) Publish as supersession (never overwrite)

* S6 returns **I9** with `publish_outcome = SUPERSEDED_PUBLISHED` (or NEW_PUBLISHED) and carries:

  * explicit supersedes link(s) if provided/known
* S7 emits optional governance facts:

  * BackfillDeclared / BackfillCompleted
  * DatasetPublished (for the new manifest)
* S1 records the run as a backfill and closes.

## Failure posture

Backfills are normally **FAIL_CLOSED** (because they’re corrections meant to be reliable).
If the backfill is “attempt rebuild for audit,” it can be INCOMPLETE_EXPLICIT, but that must be declared in the intent.

## Drift tripwires

* overwriting old `ofs/...` outputs
* silently changing old dataset meaning without a new manifest identity and explicit backfill declaration
* reusing pre-backfill datasets just because pins “look similar” (this is why build provenance stamp matters)

---

## Quick comparative summary (what differs across IP1–IP4)

| Path               |                          Labels |                      Anchor required | Strictness                  | Output primary truth               |
| ------------------ | ------------------------------: | -----------------------------------: | --------------------------- | ---------------------------------- |
| IP1 Dataset build  | Required (for supervised kinds) |                                   No | Fail-closed                 | DatasetManifest                    |
| IP2 Parity rebuild |                Usually optional |                 Yes (DLA/provenance) | UNCHECKABLE allowed         | ParityReport (+ snapshot ref)      |
| IP3 Forensics      |                        Optional |                                   No | Explicit incomplete allowed | Snapshot artifact + pinned record  |
| IP4 Backfill       |     Usually yes (if supervised) | No (but may reference prior dataset) | Fail-closed                 | New DatasetManifest + supersession |

---

### Designer boundary call (authoritative)

If, when we go deeper, any internal design tries to:

* compute before pins are frozen,
* publish without manifest truth,
* drift feature versions/as-of/basis,
* or treat backfill as overwrite,
  it is **not** in line with the network boundary and we reject it immediately.

---

Absolutely — illuminating **IP5 (Plan-only / feasibility check)** as a production-grade internal path, still with **S1/S2/S3 opaque**, but with the **handshake meaning pinned** so it cleanly supports the environment ladder and prevents drift.

---

# IP5) Plan-only / feasibility check

**Route:** `S1 → S2 → S3(feasibility only) → S1`
*(No S4/S5/S6/S7; no publish; no dataset artifacts.)*

## What IP5 is for (why it exists in a production platform)

IP5 is a **cheap “can we do this?” probe** that answers, before you burn compute:

* Is the requested replay window **satisfiable** in this environment (given retention + archive availability)?
* If the caller supplied a time window, what **resolved offset basis** would that translate to?
* Are there likely **archive gaps** or **retention boundary** problems?
* Do we need archive, and is archive completeness **verifiable** for the requested basis?

This is the path that prevents “surprise failures 45 minutes into a rebuild” and makes your ladder explicit: local/dev/prod can differ in *capability envelope* without changing semantics.

---

## Step-by-step (internal joins)

### Step 0 — Trigger

S1 receives a BuildIntent with `build_kind = plan_check` (or a normal build_kind with a “dry-run” flag). The key requirement is: **no publish**.

### Step 1 — Pin meaning upfront (I1)

* **I1 (S1 → S2):** BuildIntent → PlanResult
  S2 pins as much as possible:
* scope selectors (ContextPins filter if any),
* replay selector (offset basis or time window),
* strictness (fail-closed vs allow-uncheckable),
* feature_profile_selector can be accepted but **does not need full compatibility validation** yet (since we’re only checking replay feasibility).
* label_as_of_spec may be present but **not resolved** here (labels don’t affect replay feasibility).

**Output of this step:** a `plan_id` and a “pinned intent” sufficient to evaluate replay feasibility.

### Step 2 — Replay feasibility + basis resolution (I2 in “feasibility mode”)

* **S2 → S3 (I2)** but in a special mode: **FEASIBILITY_ONLY**

  * If input is offset basis: S3 checks whether those offsets are available in EB, or require Archive, and whether completeness is provable.
  * If input is time window: S3 performs deterministic mapping to offsets/checkpoints and returns a `resolved_basis` (or says mapping is impossible/ambiguous).

S3 does **not** stream events (no I5) — it only returns a feasibility outcome and evidence pointers.

### Step 3 — Return feasibility report to S1

S1 closes this as a cheap run and returns the feasibility outcome to the caller/orchestrator.

No S6, no manifest, no dataset.

---

## What crosses the join back to S1 (the “FeasibilityReport”)

This is the central product of IP5.

### FeasibilityReport (conceptual)

* `request_id`, `plan_id`
* `feasibility_status` (one of):

  * **FEASIBLE_EB_ONLY** (within retention)
  * **FEASIBLE_REQUIRES_ARCHIVE** (basis spans beyond retention but archive can satisfy)
  * **INFEASIBLE_RETENTION_EXCEEDED_NO_ARCHIVE**
  * **INFEASIBLE_ARCHIVE_GAP**
  * **UNCHECKABLE_ARCHIVE_COMPLETENESS** (archive exists but completeness can’t be proven)
* `resolved_basis` (if time selector was given and could be mapped)
* `source_plan_summary` (which partitions would come from EB vs Archive)
* `earliest_available_offsets` / `latest_available_offsets` summaries (optional, used for “how far back can we go?” UX)
* `evidence_refs[]` (by-ref):

  * retention boundary evidence
  * archive segment manifest/checkpoint refs
  * any gap diagnostics
* `recommendation` (advisory, not semantic):

  * “shrink window to X”
  * “enable archive in env”
  * “run in dev/prod instead of local”
  * “await archive hydration job”

---

## Hard invariants (non-negotiable)

1. **IP5 never publishes.** No DatasetManifest, no `ofs/...` outputs.
2. **Basis semantics remain identical to real builds.**

   * time windows must resolve to offsets/checkpoints the same way IP1/IP2/IP4 would.
3. **No silent optimism.** If archive completeness is not provable, the result must say **UNCHECKABLE** (not “probably fine”).
4. **Environment ladder is explicit.**
   Local may report “infeasible” for long windows simply because archive is disabled; that’s not a semantic change — it’s the envelope.

---

## Branch points (what IP5 must be able to answer explicitly)

* **Within retention** → EB only feasible
* **Beyond retention** → requires Archive
* **Archive disabled** → infeasible beyond retention
* **Archive enabled but incomplete** → infeasible or uncheckable (depending on strictness)
* **Time window mapping ambiguous** (if your system can’t map time→offset deterministically) → infeasible (you must not guess)

*(I’m pinning that last line: if mapping isn’t deterministic, we declare it infeasible, because guessing would later break parity and reproducibility.)*

---

## How IP5 supports the larger system (why it matters)

* **Run/Operate** can call IP5 before scheduling expensive OFS runs.
* **Backfill controllers** can use IP5 to detect archive gaps before declaring backfill completion.
* **Parity loop** can use IP5 to decide whether a requested parity rebuild is checkable or will be UNCHECKABLE.
* **Environment ladder** becomes transparent: dev/prod feasibility differs because archive/retention differs, not because logic differs.

---

## Drift tripwires (not allowed)

* IP5 “helpfully” reading labels and making feasibility depend on label availability (labels are a different join; replay feasibility is about EB/Archive).
* Returning “feasible” without a resolved basis when time selectors were used.
* Producing any publish-shaped artifact (manifest or `ofs/...` outputs).

---

Locked — we’ll illuminate **IL1–IL3** as **production internal loops** that exist *inside* OFS, while keeping **S1–S7 opaque**. I’m going to pin the **observable behavior**, the **state each loop must maintain**, and the **failure/retry semantics** so we can later open boxes without drifting.

---

## IL1 — Idempotent retry loop (job-level)

**Loop:** `S1 retry → S2 pins → (I12 preflight / S6 says “already published”) → S1 done`

### What this loop is for

Guarantee that **retries (and duplicate triggers)** do **not** create new dataset truth or “v2 by accident.”

### Participants

* **S1** (job lifecycle / retries)
* **S2** (meaning pins → `plan_id`)
* **S6** (publication truth → committed `DatasetManifest`)
* Internal joins: **I1, I12, I9** (and indirectly I13 in non-short-circuit runs)

### The pinned identity model (the thing that makes IL1 possible)

I’m declaring these identities as authoritative (we can refine fields later, but the roles are pinned):

* `request_id` = **execution idempotency** (S1-owned). Retries reuse the same request_id.
* `plan_id` = **meaning idempotency** (S2-owned). Same meaning pins ⇒ same plan_id.
* `dataset_id` = **published dataset identity** (S6-owned). Typically derived from plan_id + output_kind (and build provenance stamp).
* `dataset_manifest_ref` = **the truth pointer** (S6-owned). If you have this, you have the dataset.

### The IL1 state machine (external behavior, no internals)

There are only three truth-relevant states:

1. **NOT_PUBLISHED**
   No committed manifest exists for this `plan_id` and output_kind.

2. **PUBLISHED**
   A committed manifest exists and is authoritative.

3. **SUPERSEDED** (optional but production-real)
   A newer declared backfill output supersedes the older one; old one is still immutable, but shouldn’t be “reused” by policy.

### The IL1 steps (what happens on retry)

1. **S1 receives a retry** (same request_id) or a duplicate trigger (new request_id but same intent).

2. **I1 (S1→S2):** S2 re-computes the same pins and plan_id deterministically.

3. **I12 preflight (S1/S2↔S6):** ask: “is there already a committed manifest for this plan?”

   * **If yes:** S6 returns `{dataset_manifest_ref, dataset_id, status_class, supersession info}`
     → S1 completes immediately with `publish_outcome = ALREADY_PUBLISHED`.
   * **If no:** proceed to full build path (IP1/IP4), which will end in I9.

4. **I9 (S6→S1):** even if S1 timed out previously, on retry S6 must return a stable publish receipt once commit happened.

### Failure / race cases (must be handled)

* **Lost acknowledgement:** manifest committed, but S1 never got I9 (crash/network).
  ✅ Next retry resolves via **I12** and returns ALREADY_PUBLISHED.
* **Concurrent duplicate runs:** two jobs compute same plan_id and race.
  ✅ Only one commit wins; the other must converge to ALREADY_PUBLISHED (or COMMIT_CONFLICT → then I12).
* **Supersession/backfill:** a backfill creates a new dataset that supersedes an old plan.
  ✅ I12 must be able to report `superseded_by` so S1 can decide whether reuse is allowed by policy.

### Drift boundary (not allowed)

* “Retry creates a new dataset version” without a declared reason.
* “Find the latest dataset under ofs/…” scanning instead of asking S6 via I12.
* “Same meaning pins produce different plan_id” (hidden defaults, implicit now, floating feature versions).

---

## IL2 — Chunk / partition processing loop (data-level)

**Loop:** `S3 emits ReplaySlice(k) → S5 processes(k) → S6 stages(k) → repeat`

### What this loop is for

Make large replays **streamable, parallelizable, and restartable**, without changing the meaning of the output.

### Participants

* **S3** replay unifier (EB/Archive)
* **S5** feature reconstruction + shaping
* **S6** staging/publish preparation
* Internal joins: **I5, I7, I13** (and S2 pins via I4 already frozen)

### The critical pin: “chunking must not change meaning”

Chunking is an execution detail, but it *can* accidentally affect:

* output file boundaries,
* per-file digests,
* ordering of rows,
* and therefore manifest identity.

So I’m pinning this:

> **IL2 must be deterministic with respect to plan_id.**
> Either (a) shard/chunk boundaries are derived deterministically from plan_id + basis, or (b) the final published artifact layout is normalized so chunk differences don’t alter published digests/refs.

For v0, the simplest drift-resistant stance is **(a)**: deterministic chunking/sharding.

### The IL2 “slice contract”

Each iteration `k` is a **ReplaySlice** with:

* `partition_id`
* `offset_range [a,b)` (half-open)
* `slice_id` (deterministic, e.g., hash(plan_id, partition, a, b))
* `source` EB/ARCHIVE (or overlap mode explicitly declared)

This makes resume/idempotency straightforward.

### The loop steps

1. **S3** emits `ReplaySlice(k)` to S5 (**I5**), and also emits/updates replay receipts toward S6 (**I13**).
2. **S5** processes slice k under frozen ExecutionPins (**I4 already acked**) and produces a `DatasetDraftShard(k)`.
3. **S6** stages shard k (not published yet), and records staging progress keyed by `slice_id/shard_id`.
4. Repeat until all slices in the resolved basis are processed.

### Restart semantics (production necessity)

If OFS crashes mid-way:

* S3 can re-emit the same slices (same slice_id).
* S5 can re-process a slice (same shard_id).
* S6 can treat staging as idempotent:

  * if shard already staged with matching digest → accept and continue
  * if mismatch → fail closed (corruption / nondeterminism)

### Drift boundary (not allowed)

* “Sometimes slice sizes differ” in a way that changes published layout/digests for the same plan_id.
* “S5 relies on a global total order across partitions.” (It must treat partitions independently and only use deterministic tie-breakers when needed.)
* “S6 commits based on ‘most slices processed’.” Completeness must be proven (IL3/ I13).

---

## IL3 — Publish–commit loop (atomicity loop)

**Loop:** `S6 stage writes → validate digests/receipts → commit manifest → (if failure) rollback/mark failed → retry`

### What this loop is for

Make publication **atomic and audit-grade**:

* objects can be partially written,
* processes can crash,
* duplicates can race,
  but **truth** only exists when the **DatasetManifest is committed**.

### Participants

* **S6** is the center of this loop
* inputs from **S2/S3/S4** (pins + receipts) and **S5** (draft shards)
* internal joins: **I7, I8, I13, I9** (and I12 for conflict convergence)

### The v0 publish protocol (pinned behavior, not storage-specific)

S6 runs a strict 2-phase publish protocol:

#### Phase 1 — Stage

* Accept shard writes (or pointers to staged writes) from S5 (I7)
* Accumulate provenance bundle from S2/S3/S4 (I8)
* Accumulate replay completeness receipts from S3 (I13)

**Key property:** staged objects are not “truth” because nothing references them as authoritative yet.

#### Phase 2 — Validate

Before commit, S6 must validate:

* **completeness**: required I13 receipts cover the entire resolved basis (unless build_kind explicitly permits INCOMPLETE/UNCHECKABLE and that is declared)
* **digest integrity**: shards match expected digests (or S6 computes and records them)
* **pin consistency**: plan_id / basis_hash / feature_profile_ref / label_as_of_spec are coherent across inputs

If validation fails → **no commit**.

#### Phase 3 — Commit (atomic)

* Write the DatasetManifest in a way that is “atomic enough” for the substrate
* Once committed, the dataset becomes real.

Then emit **I9 PublishReceipt** back to S1.

### Rollback / retry behavior

Rollback doesn’t need “delete everything.” It needs **truth safety**:

* If staging exists but commit didn’t happen: safe to retry; staged objects are unreferenced.
* If commit happened but acknowledgement failed: IL1 will converge via I12.
* If commit conflicts (another publisher committed first): S6 must converge to ALREADY_PUBLISHED after verifying it’s the same meaning pins.

### Drift boundary (not allowed)

* Publishing a manifest without full provenance (basis/as-of/versions).
* Publishing “complete” without completeness evidence.
* Mutating or overwriting an existing committed dataset instead of creating a superseding one for backfills.

---

## The three loops as one coherent “production spine”

If you squint, IL1/IL2/IL3 are the three safety rails inside the vertex:

* **IL1** prevents truth duplication across retries and races.
* **IL2** makes processing scalable *without changing meaning*.
* **IL3** makes publication atomic and auditable.

They’re also intentionally ladder-safe:

* local may have smaller bases and no archive,
* prod has big bases and archive,
  but these loops remain identical in semantics.

---

Locked — illuminating **IL4** and **IL5** as **production correction loops** inside OFS (still keeping S1–S7 opaque). These are the loops where “derived truth changes over time” is handled **without mutating primary truth** and without breaking your audit/reproducibility rails.

I’ll pin:

* **what triggers them**
* **what they are allowed to change**
* **what must be recorded**
* **how they terminate**
* **where drift would occur**

---

# IL4) Supersession / backfill loop (derived-truth correction loop)

**Loop shape:**
`(Trigger) → S1(backfill intent) → S2 pins → S3/S4/S5 rebuild → S6 new manifest (supersedes) → S7 signals → (optionally repeat)`

## What IL4 is for

Handle **corrections** to *derived artifacts* produced by OFS—datasets/manifests/parity artifacts—when something meaning-affecting changes, **without rewriting history**.

This loop exists because in production you will inevitably have:

* feature definition fixes (profile revision changes),
* OFS build logic fixes (bugfix in reconstruction/materialization),
* archive gaps being resolved after the fact,
* label-rule adjustments,
* and parity findings that demand correction.

## Allowed vs forbidden changes (hard pin)

### Allowed

* Publish a **new DatasetManifest** (and new materials) under `ofs/...` with a **new dataset identity**, explicitly linked as a **supersession/backfill**.
* Publish a **BackfillDeclaration** / **BackfillCompleted** fact (optional, but production-recommended).
* Update **governed pointers elsewhere** (e.g., Registry ACTIVE bundle) via their own authority paths — not inside OFS.

### Forbidden (drift)

* Mutating old `ofs/...` datasets/manifests in place.
* Mutating EB events, Label Store timelines, Registry history.
* “Silent rebuild” where the system starts using the new dataset without an explicit declared backfill/supersession trail.

## The trigger set (what can initiate IL4)

IL4 can be triggered by any of these **external facts** (not by “feelings”):

1. **Parity mismatch evidence** (from S7 parity outcomes)
2. **Archive completeness changes** (gap resolved / archive hydration caught up)
3. **Feature profile revision change** (new version promoted as ACTIVE or explicitly requested)
4. **Policy revision change** that affects meaning pins (label as-of rule change, canonicalization rule change)
5. **Operator-declared correction** (manual backfill request with scope/basis)

## The internal steps (what actually happens)

### Step 1 — Trigger becomes a declared BuildIntent (S1)

* S1 receives a **backfill intent** including:

  * scope/basis,
  * reason code,
  * whether it **supersedes** a known dataset/manifest,
  * any approvals/governance metadata.

**Pin:** IL4 does not start from “run it again.” It starts from an explicit **declared** intent.

### Step 2 — Pins are frozen (S2)

S2 must produce a **new plan_id** when any meaning-affecting pin changes.
In IL4, a meaning change is often the *point*, so we must not accidentally collide with old plan_id.

**Designer pin:** backfill intent includes a **correction_stamp** (e.g., “reason + policy_rev + build_rev”), which contributes to plan_id so corrected outputs cannot be mistaken for the old ones.

### Step 3 — Rebuild executes (S3/S4/S5)

Same mechanics as IP4:

* replay basis resolved and satisfied (EB/Archive),
* label as-of resolved (if supervised),
* features computed under pinned versions.

### Step 4 — Publish as supersession, not overwrite (S6)

S6 publishes:

* new materials,
* a new manifest,
* and records **supersedes** linkage (old dataset_id/manifest_ref if provided/known).

### Step 5 — Signals and governance closure (S7)

S7 may emit:

* BackfillDeclared / BackfillCompleted (control facts),
* DatasetPublished for the new manifest,
* telemetry.

S1 records the run outcome and references new manifest ref.

## Termination condition (when IL4 “stops”)

IL4 stops when the correction’s acceptance criteria are met, which is usually one of:

* parity returns to MATCH (if parity was the trigger),
* archive basis becomes satisfiable and dataset built successfully (if archive was the trigger),
* the corrected feature profile/dataset is published and consumed by MF (if training was the trigger).

**Pin:** IL4 is not “continuous churn.” It is **a declared operation** that produces a stable new artifact.

## Drift tripwires (stop immediately if seen)

* “We rebuilt the dataset but kept the same dataset_id and overwrote files.”
* “We changed label as-of behavior but didn’t record policy_rev in manifest.”
* “We fixed a bug and reused old plan_id without a correction stamp.”
* “We replaced the dataset without an explicit supersedes/backfill declaration.”

---

# IL5) Parity stabilization loop (optional but production-real)

**Loop shape:**
`S7 parity mismatch → governance signal → operator action → S1 parity rebuild / backfill rebuild → S7 parity again → stabilize`

## What IL5 is for

IL5 is the **closed-loop process for driving parity mismatches to a stable conclusion** (MATCH or an explicitly accepted divergence with recorded reason). It is effectively a “control system” around parity.

IL5 only exists if you enable parity checks, but if enabled, it must be handled deliberately because parity mismatches are noisy unless you pin outcomes and remediation paths.

## What counts as “stabilized” (hard pin)

IL5 stabilizes only when one of these is true:

1. **MATCH** under the same basis + versions (ideal)
2. **MISMATCH explained and accepted** with an explicit “known divergence” record (e.g., numeric canonicalization differences accepted temporarily) and recorded in governance/audit.
3. **UNCHECKABLE resolved** into either MATCH/MISMATCH by fixing missing prerequisites (archive gaps closed, provenance fixed, versions made available).

**Not allowed:** “We stopped checking parity so it’s fine.”

## The loop stages (production shape)

### Stage 1 — Detect and classify (S7)

S7 must classify parity outcomes with enough detail to drive action:

* MISMATCH category (version mismatch, basis mismatch, feature canonicalization mismatch, replay gap, label dependency mismatch if applicable)
* Evidence refs (by-ref) to what exactly was compared

### Stage 2 — Announce / escalate (optional control fact)

If enabled, emit a ParityResult control fact; always emit telemetry.

### Stage 3 — Operator action (external, but required)

The system cannot automatically fix everything. Typical actions:

* correct feature definitions (new profile revision),
* fix OFS build logic and bump build provenance stamp,
* repair archive hydration/completeness,
* repair online provenance recording so anchors are complete,
* declare a backfill.

### Stage 4 — Re-run parity target (S1 → … → S7)

Depending on action, the loop chooses:

* **IP2 parity rebuild** (rebuild snapshot and compare again), or
* **IP4 backfill rebuild** + then parity rebuild (if correction required new datasets/features).

### Stage 5 — Stabilize / close

* MATCH, or
* explicit accepted divergence record, or
* explicit uncheckable due to known missing prerequisites (with remediation planned).

## The critical “no thrash” pin

To prevent endless loop churn, IL5 must incorporate:

* **stable parity target identity** (the anchor: input_basis + versions + snapshot hash)
* **stable rebuild identity** (plan_id includes correction stamp)
* **rate-limited / policy-driven triggers** (don’t fire parity rebuild for every single decision unless that’s intentional)

(We’ll keep rate limiting as an implementation/perf choice, but the *existence* of a “don’t thrash” posture is a production requirement.)

## Drift tripwires

* parity rebuild uses different feature versions than the anchor (“close enough”)
* parity rebuild widens/narrows basis silently (“around that time”)
* mismatches are “resolved” by disabling parity without recording accepted divergence
* remediation changes meaning but doesn’t bump correction stamp / policy_rev in pins

---

## Relationship between IL4 and IL5 (how they compose)

* **IL5 is the control loop around parity** (detect → act → verify).
* **IL4 is the mechanism that performs corrections** (act → publish superseding derived truths).

In practice:

* IL5 detects mismatch → IL4 executes correction → IL5 re-checks until stable.

---

Yep — this is the **negative space** of the graph: the **explicit non-joins / forbidden edges / “must NOT happen” flows**. I’m going to pin these as **authoritative boundary constraints** so if any later internal design implies one of these edges, we treat it as *drift* and reject it immediately.

## 1) External non-joins around OFS (platform-level “no edges”)

### OFS must not write primary truths

* **NO:** OFS → **Event Bus (traffic topics)** (OFS never produces admitted events)
* **NO:** OFS → **Archive** (OFS never mutates the history store)
* **NO:** OFS → **Label Store** (OFS never writes labels; it only reads)
* **NO:** OFS → **Registry** (OFS never promotes/rolls back bundles)
* **NO:** OFS → **SR readiness surfaces** (OFS never declares READY or alters SR ledgers)

### OFS must not bypass trust boundaries

* **NO:** OFS ↔ **Ingestion Gate (IG)** as a data source or admission path
  (OFS consumes the *admitted* stream, not the pre-admission world.)
* **NO:** OFS ↔ **Data Engine** directly for “traffic”
  (engine business traffic enters EB via IG pull; OFS replays from EB/Archive, not engine datasets.)

### OFS must not become part of the hot path

* **NO:** OFS → **Online Feature Plane (OFP)** (no “push offline features to serve”)
* **NO:** OFS → **Decision Fabric (DF)** (no direct influence on live decisions)
* **NO:** OFS → **Action Layer / Case Workbench** (no operational actions)

### OFS must not do “discovery by scanning”

* **NO:** OFS scanning object store for “latest dataset/run/world”
  Everything must be anchored by **explicit refs** (e.g., SR `run_facts_view`, explicit feature profile ref, explicit basis).

### OFS must not become a hidden scheduler of the platform

* **NO:** OFS self-triggering MF training (“dataset published → auto-train”) as the *primary* mechanism in v0
  (Announcements are allowed; **training invocation must still be explicit/pinned** via orchestration.)

---

## 2) Internal non-joins inside OFS (subnetwork “no edges”)

These prevent “cross-talk” that creates hidden defaults.

### Data access separation (forced by determinism + auditability)

* **NO:** S5 (Reconstruct/Shape) → EB/Archive directly
  All history comes through **S3** (Replay Unifier) so basis/completeness is controlled.
* **NO:** S5 → Label Store directly
  All labels come through **S4** so as-of semantics are enforced in one place.
* **NO:** S6 (Publisher) → EB/Archive/Label Store for “extra context”
  S6 builds manifests from **pinned plan + receipts** only (I8/I13), not ad-hoc queries.

### Pin authority separation (prevents floating meaning)

* **NO:** S3/S4/S5 deciding feature versions or as-of rules
  Only **S2** pins: replay basis intent, label as-of spec, feature profile ref, scope.
* **NO:** S1 (Orchestrator) deciding meaning pins
  S1 owns lifecycle/idempotency only; S2 owns meaning.

### Signalling isolation (prevents “second truth paths”)

* **NO:** S7 (Signals) reading EB/Archive/Label Store to “verify” results
  S7 only emits signals based on **committed outputs** from S6 + optional parity anchors.
* **NO:** S7 publishing dataset truth
  Only S6 publication makes datasets real.

### No publish-side semantic transforms

* **NO:** S6 reshaping datasets (sorting/partitioning/format changes) in a way that changes meaning without it being explicitly pinned
  Publishing may serialize, but it can’t “change the dataset” silently.

---

## 3) Forbidden internal loops (anti-thrash / anti-drift)

These are “non-loops” we do **not** allow even if they sound convenient:

* **NO:** “Parity mismatch → OFS auto-backfill itself repeatedly”
  S7 may signal; **Run/Operate must declare backfill** as an explicit intent.
* **NO:** “Retry → new dataset version” for the same meaning pins
  Retries must converge via I12/I9; new identity requires an explicit change in pins or a declared backfill/supersession.
* **NO:** “Best-effort publish” when replay/labels are missing for a dataset build
  Fail closed (or explicitly INCOMPLETE/UNCHECKABLE only when the build kind allows it).

---

## 4) Quick “negative-space checklist” (use later as a drift alarm)

If, while we open boxes, we see any design that implies:

* OFS writes to EB/Archive/Label Store/Registry, or
* OFS discovers by scanning “latest,” or
* S5 talks directly to EB/Label Store, or
* S7 reads truth stores or triggers autonomous training/backfills,
  then we stop: that’s **out of bounds** with the platform network boundary.

---

## USER: PAUSE FOR REFLECTION

([Past chat][1])([Past chat][1])([Past chat][2])([Past chat][3])

Here’s the “design freeze reflection” of what we’ve established so far — the **outer network** OFS must obey, plus the **first-layer internal network** (opaque subnetworks), plus the **internal joins/paths/loops** and the **negative space** (non-joins). This is the spine we must not drift from when we open the boxes further.

---

## 0) The stance we took and why it matters

* We treated **OFS as a vertex inside a pinned platform graph**, and we designed its **outer obligations first** (joins/paths/loops), because *that* is what prevents drift when you later implement components in parallel.
* We then stepped **one level inward** and defined OFS’s **internal subnetworks** as opaque boxes (S1–S7), and only after that enumerated the **internal joins/paths/loops** (I1–I13, IP1–IP5, IL1–IL5).

---

## 1) OFS’s outer role in the platform network (frozen)

**OFS is a batch/job plane**, invoked on-demand or scheduled. It is the platform’s **deterministic rebuilder**:

* Reads **admitted facts** (EB within retention; Archive beyond retention as continuation).
* Reads **label truth** only from Label Store, using explicit **as-of** semantics (effective vs observed).
* Uses **version-locked feature definitions** (no silent “latest”).
* Outputs **immutable datasets/snapshots** whose truth is defined by a **DatasetManifest** (by-ref pointers + digests + provenance).
* Optionally produces **parity evidence** against online snapshots (MATCH/MISMATCH/UNCHECKABLE).

**What OFS is not:** not serving, not hot-path, not a truth writer for events/labels/bundles.

---

## 2) The complete OFS outer join surface (A1–A11, frozen)

### Inbound joins (OFS reads)

1. **Run/Operate → OFS**: BuildIntent/job trigger (request_id, selectors, policy posture).
2. **SR `sr/run_facts_view` → OFS**: ContextPins + (optional) by-ref world/context surfaces with PASS evidence; *no scanning*.
3. **Feature definition profiles → OFS**: versioned feature profile refs; must lock and record.
4. **EB `fp.bus.traffic.v1` → OFS**: admitted canonical envelopes; replay by offsets/watermarks (within retention).
5. **Archive → OFS**: continuation of EB for cold history; by-ref + verifiable completeness.
6. **Label Store → OFS**: append-only label timelines; explicit as-of rules.
7. **Optional DLA exports → OFS**: provenance anchors for parity targets (basis + versions + snapshot hash).

### Outbound joins (OFS writes)

8. **OFS → object store `ofs/...`**: materials + DatasetManifest (unit of truth).
9. **OFS → Model Factory (MF)**: manifest ref + evidence refs (by-ref handoff; not a dataframe).
10. **Optional OFS → `fp.bus.control.v1`**: governance announcements (DatasetPublished, BackfillDeclared/Completed, ParityResult, BuildFailed).
11. **OFS → OTLP/Obs**: traces/metrics/logs with correlation keys.

**Pinned nuance:** control bus facts are **announcements**, never a bulk transport.

---

## 3) The platform paths (P1–P4) that include OFS (frozen)

* **P1 Learning route:** EB/Archive + Label Store → OFS → DatasetManifest → MF → Registry → DF → (cases/labels) → Label Store → OFS.
* **P2 Parity route:** DLA anchor → OFS rebuild under same basis+versions → ParityResult → ops/governance action.
* **P3 Retention/Archive route:** within retention uses EB; beyond retention uses Archive; gaps → explicit FAIL/UNCHECKABLE (never silent partial).
* **P4 Backfill route:** declared backfill intent → OFS rebuild (new manifests) → MF retrain (optional) → Registry promote/rollback.

---

## 4) The platform loops (L1–L3) that include OFS (frozen)

* **L1 Continuous learning loop:** P1 closed-loop.
* **L2 Governance correction loop:** P2 + P4 closed-loop (mismatch/gaps → declared rebuild → new evidence → stabilize).
* **L3 Immutability/idempotency loop:** OFS outputs are immutable; retries converge; meaning changes create new identity + explicit supersession.

---

## 5) Environment ladder lens (what changes vs what must not)

**Pinned rule:** graph + semantics don’t change across local/dev/prod; only the *operational envelope* changes.

Key knobs that affect OFS behavior (without changing meaning):

* **Retention length** (local short, dev medium, prod governed).
* **Archive enabled/disabled + verifiability** (local may not have it; prod must be a first-class continuation for long horizons).
* **Security strictness** (mechanism exists everywhere; strictness increases up the ladder).
* **Observability depth** (OTLP everywhere; prod adds SLOs/alerts).
* **Scheduling/throughput** (how often and how big builds are).

---

## 6) First-layer internal subnetworks (S1–S7) inside OFS (opaque, frozen)

We declared these as the **minimum internal boxes** forced by the outer graph:

* **S1 Build Orchestration & Run Ledger**: lifecycle, request_id, retries, result reporting.
* **S2 Pin & Provenance Resolver**: freezes meaning pins (scope, basis, as-of, versions, optional parity anchor).
* **S3 History Acquisition & Replay Unifier**: EB+Archive as one logical stream; basis satisfaction + completeness evidence.
* **S4 Truth Timeline Resolver (Labels)**: label as-of resolution + coverage diagnostics.
* **S5 Feature Reconstruction & Dataset Shaping**: apply versioned features + deterministic shaping.
* **S6 Artifact Publisher & DatasetManifest Authority**: atomic publish; manifest truth; immutability/idempotency.
* **S7 Parity/Governance/Telemetry Signalling**: parity outcome, control facts, OTLP correlation.

---

## 7) Internal joins (I1–I13) we pinned (still opaque boxes)

### “Pin first” joins

* **I1 (S1→S2)**: BuildIntent → pinned BuildPlan (no heavy work before pins).
* **I2 (S2→S3)**: ReplayBasis resolve (offset basis; time windows only resolve-to-offsets).
* **I3 (S2→S4)**: LabelAsOfSpec contract (explicit observed-time cutoff; no “latest”).
* **I4 (S2→S5)**: ExecutionPins (feature profile ref + scope + output kind; no substitution).

### “Build stream” joins

* **I5 (S3→S5)**: ReplaySlice feed (partition order only; duplicates allowed; no silent gaps).
* **I6 (S4→S5)**: LabelView feed (resolved labels per as-of; coverage diagnostics).
* **I7 (S5→S6)**: DatasetDraft/SnapshotDraft (shards + schema refs + digests candidates).
* **I8 (S2+S3+S4→S6)**: Provenance bundle for manifest construction (pins + receipts).

### “Close & signal” joins

* **I9 (S6→S1)**: PublishReceipt (NEW/ALREADY/SUPERSEDED/FAILED + manifest ref).
* **I10 (S6→S7)**: signal inputs (manifest ref + optional parity context).
* **I11 (S7→S1)**: signal summary (what was emitted; parity outcome; telemetry correlation).
* **I12 (S1/S2↔S6)**: preflight existence check (idempotent reuse; no scanning).
* **I13 (S3↔S6)**: completeness receipts gating manifest commit.

---

## 8) Internal paths (IP1–IP5) we illuminated

* **IP1 Dataset build:** S1→S2→(S3||S4)→S5→S6→S7→S1 (with optional I12 short-circuit).
* **IP2 Parity rebuild:** S1→S2(anchor)→S3→S5→S6→S7(parity)→S1 (UNCHECKABLE allowed).
* **IP3 Forensic rebuild:** S1→S2→S3→S5→S6→(S7 optional)→S1 (explicit incomplete allowed if declared).
* **IP4 Backfill rebuild:** like IP1 but publishes **superseding** manifests + explicit backfill signalling.
* **IP5 Feasibility check:** S1→S2→S3(feasibility-only)→S1 (no S5/S6; no publish).

---

## 9) Internal loops (IL1–IL5) we pinned

* **IL1 Idempotent retry loop:** retries converge to same manifest via I12/I9; no accidental new truth.
* **IL2 Chunk/partition loop:** replay/process/stage in deterministic slices; restartable without meaning change.
* **IL3 Publish/commit loop:** stage → validate → commit manifest (atomic truth); failures never “half publish.”
* **IL4 Supersession/backfill loop:** corrections produce new identities + explicit linkage; never overwrite.
* **IL5 Parity stabilization loop:** mismatch → declared action/backfill → re-check until MATCH/accepted divergence/explicit uncheckable.

---

## 10) The negative space (non-joins / forbidden edges)

We explicitly banned these drift edges:

* OFS must **not** write EB/Archive/Label Store/Registry/SR readiness.
* OFS must **not** bypass IG (it consumes admitted stream only).
* OFS must **not** read engine datasets directly for “traffic” (engine traffic enters EB via IG pull; OFS replays EB/Archive).
* OFS must **not** become part of hot path (no OFS→OFP/DF live influence).
* OFS must **not** scan object store for “latest.”
* Internally: S5 never reads EB/Label Store directly; S7 never re-reads truth stores; S6 never invents missing provenance.

---

## 11) The core drift tripwires (if we see these next, we stop)

* starting replay before pins are frozen
* treating time windows as *basis* (instead of resolve-to-offsets)
* joining “latest labels”
* floating feature versions
* publishing without a committed DatasetManifest
* claiming completeness without completeness evidence
* overwriting old datasets instead of superseding
* silently “best-effort succeeding” when history/versions are missing

---

Yep — this is the right moment. Here are the **designer-pinned deployment + environment-ladder rules** for the **OFS inner network (S1–S7)** that I want Codex to treat as *ground truth* while implementing, before we open any boxes.

---

## 1) Deployment unit pin: OFS is one **job** (batch plane), not a service

* OFS runs as a **scheduled/on-demand job unit** in dev/prod; in local it can be a CLI/job runner, but it must still behave like an independent deployment unit with real networking + durable dependencies. 
* Internally you may implement S1–S7 as modules in a single process/container; the *deployment boundary* is “one job run produces pinned outputs (or explicit failure)”. 

---

## 2) Substrate map pin: what OFS reads/writes in production

OFS must be buildable/testable purely from the standard substrate (no hidden dependencies):

**Reads**

* **Bus/Archive:** replay history from `fp.bus.traffic.v1` + archive continuation
* **DB:** `label_store` (as-of queries on append-only timelines)
* **Object:** `sr/run_facts_view` (by-ref join surface, no scanning)
* **Profiles:** feature definition profiles (versioned artifacts)

**Writes**

* **Object:** `ofs/...` dataset materializations + **DatasetManifest** (truth for training inputs)
* **Optional:** governance fact → `fp.bus.control.v1` (announcements, not transport)
* **OTLP:** traces/metrics/logs to the OTel pipeline

---

## 3) Environment ladder pin: “same platform semantics, different envelope”

Local/dev/prod must share:

* same graph + trust boundaries,
* same rail meanings (READY/ADMITTED/ACTIVE/LABEL-AS-OF/BACKFILL),
* same replay/idempotency/manifest semantics. 

What’s allowed to differ:

* scale, retention+archive, security strictness, reliability posture, observability depth. 

---

## 4) Profile pin: **wiring config** vs **policy config**

This one is non-negotiable:

* **Wiring config (non-semantic):** endpoints, ports, timeouts, resource limits.
* **Policy config (outcome-affecting):** retention/backfill rules, feature profile activation rules, label leakage posture defaults, archive completeness rules, signal emission rules. These are versioned and auditable.

**Every OFS run must report `policy_rev`** (and the resolved feature profile ref) in provenance/telemetry so you can answer “what rules were in force?”

---

## 5) CI/CD + promotion pin (what must be true operationally)

There are **three promotion lanes**, and OFS must fit them:

1. **Code artifacts are immutable** (build once; run the same artifact in local/dev/prod). 
2. **Policy/profile revisions are versioned artifacts** with governed activation + governance facts.
3. **Bundles are published by MF and activated via Registry** (OFS never shortcuts this).

And your **golden integration flow must include “label + offline shadow + registry resolve” at least once**.

---

## 6) Retention / Archive / Backfill knobs (the big OFS deployment drivers)

These are the ladder knobs that shape what OFS can do in each environment — **without changing meaning**:

* **Retention is an environment profile knob** (local short, dev medium, prod policy-driven) but offsets/watermarks/replay semantics don’t change.
* **Archive is the continuation of EB, not a second truth**; replay beyond retention must be “as if EB” and the basis must be recorded.
* **Archive completeness must be verifiable** for a declared window; otherwise outcomes must be explicit (INCOMPLETE/UNCHECKABLE), never silent partial success.
* **Backfills are declared and auditable**, regenerate derived artifacts only (OFS datasets/manifests are backfillable; EB facts / label timelines / registry history are not).
* **Retention or archive policy changes emit governance facts** (because they change what is replayable).

---

## 7) Observability pin: OTLP everywhere, locally too

Local must run a production-shaped observability substrate (OTel collector + Grafana stack) so OFS behavior is real and debuggable.

For OFS runs, telemetry must carry correlation keys sufficient to join across the platform:

* `request_id`, `plan_id`, `dataset_id`, `dataset_manifest_ref`
* `basis_hash` / basis summary
* `feature_profile_ref`
* `label_as_of_spec`
* `policy_rev` + code artifact identity

(Exact metric names can be implementer choice; the correlation posture is the pin.)

---

## 8) Security/secrets pin (especially important for batch jobs)

* Secrets are **never** embedded in manifests/ledgers/audit artifacts; injected at runtime only. 
* Dev must be “real enough” to catch permission issues (who can read labels, who can publish `ofs/...`, who can trigger backfills). Prod is stricter, but the mechanism exists everywhere.

---

## 9) Reference “production-shaped local” stack (so Codex can implement now)

We are not picking a cloud vendor; we *are* pinning interface semantics:

* **Kafka-ish bus** (partitions/offsets/consumer groups/at-least-once) → Redpanda locally
* **S3-ish object store** (bucket/key, refs+digests) → MinIO locally
* **SQL authoritative DB** → Postgres locally
* **OTel pipeline** → OTel collector + Grafana stack locally

Local/dev/prod mapping is “same interfaces, stronger envelope up the ladder.”

---

## 10) What I want Codex to build around (deployment ergonomics)

To keep OFS implementable and testable from day one, Codex should have:

* **one command to bring up local infra (Compose)**
* **one local profile** with endpoints + policy revs
* **one integration script** that runs the golden flow end-to-end (including OFS)

---

### The final “designer pin” before we open nodes

When we illuminate S1–S7 next, every internal design choice must preserve this invariant:

> **Any OFS output is explainable as “code artifact X + policy_rev Y + feature profile ref Z + replay basis (offsets/checkpoints) + label as-of boundary + by-ref materials + committed DatasetManifest.”**

If you’re good with these deployment pins, we can now start opening the first subnetwork box (I recommend **S1+S2 together**, because deployment correctness hinges on run lifecycle + pin freezing + idempotency).

---

Yes — illumination should **not** change the network; it should only reveal the machinery that satisfies the already-pinned joins/paths/loops.

## Nodes (subnetworks) inside OFS

1. **S1 — Build Orchestration & Run Ledger**
2. **S2 — Pin & Provenance Resolver**
3. **S3 — History Acquisition & Replay Unifier**
4. **S4 — Truth Timeline Resolver (Label As-Of)**
5. **S5 — Feature Reconstruction & Dataset Shaping**
6. **S6 — Artifact Publisher & DatasetManifest Authority**
7. **S7 — Parity / Governance / Telemetry Signalling**

## Illumination order I want us to use

1. **S1 + S2 together** (they pin lifecycle + meaning; prevents downstream drift)
2. **S3** (replay basis, EB/Archive continuity, completeness evidence)
3. **S4** (label as-of semantics, subject keys, coverage posture)
4. **S5** (reconstruction semantics + shaping under version-locked definitions)
5. **S6** (atomic publish, manifest construction, idempotency/supersession)
6. **S7** (parity outcomes + control facts + OTLP correlation)

That order mirrors the forced dependency chain: *pins first → inputs acquisition → reconstruction → publication → signalling*.

---

Got it. We’ll open **S1 + S2 as the “Run Control & Pinning layer”** of OFS. This layer is the **mechanical heart** that makes everything downstream deterministic, replayable, auditable, and ladder-safe.

I’m going to expose:

* the **submodules inside S1 and S2**
* the **state machines**
* the **pinned artifacts they must produce**
* the **decision points / invariants**
* the **failure & retry posture**
* how they interact with opaque neighbors (S3/S4/S5/S6/S7) **without changing the network**

---

# S1 + S2: Run Control & Pinning Layer

## What this layer is responsible for

1. Convert a human/operator “intent” into a **fully pinned execution plan** (no hidden defaults).
2. Guarantee **idempotent retries** and **cost control** (reuse if already built).
3. Provide a **run ledger** (explicit start/finish/fail, correlation keys).
4. Produce the one thing the rest of OFS depends on: a **Pinned BuildPlan**.

This layer must *never* compute features, replay data, or publish datasets — it only **pins and orchestrates**.

---

# S1 — Build Orchestration & Run Ledger (machinery)

### S1’s submodules (opaque-but-named machinery)

**S1.1 Intent Intake & Validation**

* Accept a `BuildIntent` (from Run/Operate).
* Perform *structural* validation only (required fields present, obvious contradictions).

**S1.2 Run Identity & Trace Context**

* Establish `request_id` as the job idempotency handle.
* Create a root trace/span context and carry it forward.

**S1.3 Run Ledger Writer**

* Write a run record with explicit lifecycle states (see state machine below).
* This run record is the recovery surface if the job crashes mid-run.

**S1.4 Concurrency / Lease Manager (optional but production-real)**

* Prevent wasteful duplicate work (two runs with the same meaning pins racing).
* Can be implemented as: optimistic commit convergence (preferred) plus optional advisory lease.

**S1.5 Preflight Reuse Router (I12)**

* After pins exist, ask S6 “already published?” before doing replay/compute.

**S1.6 Path Router**

* Based on pinned plan, choose which internal path to execute:

  * IP1 dataset build
  * IP2 parity rebuild
  * IP3 forensic rebuild
  * IP4 backfill rebuild
  * IP5 feasibility check

**S1.7 Cancellation / Timeouts**

* Allow cancellation **before publish commit**.
* After publish commit, cancellation only affects signalling/telemetry, not truth.

**S1.8 Result View Assembler**

* Combine:

  * publish receipt (I9)
  * signalling summary (I11)
    into a final `RunResultView` for Run/Operate/caller.

---

## S1 lifecycle state machine (what must exist)

Minimal states that keep things unambiguous:

1. **RECEIVED** (intent accepted)
2. **PINNING** (S2 is producing pins)
3. **PREFLIGHT_REUSE_CHECK** (optional I12)
4. **DISPATCHED** (router chooses IP*)
5. **RUNNING** (downstream modules executing; S1 tracks phase)
6. **PUBLISH_COMMITTED** (only after S6 commit confirmed via I9)
7. **SIGNALLING** (S7)
8. **COMPLETED** | **FAILED** | **UNCHECKABLE_EXPLICIT** | **INCOMPLETE_EXPLICIT** | **CANCELLED**

**Hard pin:** S1 must never mark “published” unless it has a **DatasetManifest ref** from S6 (I9).

---

## S1’s durable “run ledger” artifacts (conceptual)

S1 must persist these early and often (so retries and crash recovery converge):

* `run_record` (state transitions + timestamps + correlation keys)
* `pinned_plan_ref` (pointer to the pinned plan produced by S2)
* `run_result_view` (final outcome: manifest refs, parity outcome, signals emitted)

This can be object-store based; exact file names are implementer choice. The *existence* and *meaning* are the pin.

---

## S1’s idempotency posture (the rule that prevents chaos)

S1 must support two kinds of duplicates:

### Duplicate triggers with the same `request_id`

* Return the same run state / outcome deterministically.
* If the run already completed, return the prior result view.

### Different `request_id` but identical meaning pins

* Must converge via **plan_id + I12**:

  * If a dataset is already published for that plan, reuse it (ALREADY_PUBLISHED).
  * Otherwise proceed normally.

---

# S2 — Pin & Provenance Resolver (machinery)

S2 is the **meaning authority**. It is where “implicit” dies.

### S2’s submodules (opaque-but-named machinery)

**S2.1 Policy & Environment Profile Loader**

* Load the applicable `policy_rev` and `env_profile_id`.
* This is *not* about wiring endpoints; it’s about outcome-affecting rules:

  * whether time-window selectors are allowed,
  * strictness defaults by build kind,
  * feature profile resolution rules,
  * label-as-of defaults, etc.

**S2.2 Intent Normalizer**

* Canonicalize the BuildIntent into a stable internal form:

  * normalize timestamps to UTC,
  * canonicalize selectors (ordering, casing, empty vs null),
  * assign default strictness *explicitly* (never implicit).

**S2.3 ContextPin Resolver**

* If the intent references run/world context:

  * read `sr/run_facts_view` (by-ref, no scanning),
  * extract ContextPins,
  * validate joinability posture.
* If not needed, this module is bypassed.

**S2.4 Feature Profile Resolver**

* Resolve feature definition input into a **concrete versioned ref**:

  * if explicit revision/digest provided: verify it exists
  * if “ACTIVE pointer rule”: resolve to a specific revision/digest and record it
* **Hard pin:** no floating “latest”.

**S2.5 Label As-Of Pinner**

* Produce an explicit `LabelAsOfSpec`:

  * observed-time cutoff
  * posture (KNEW_THEN vs KNOW_NOW)
  * resolution rule id
* **Hard pin:** if the intent says “now”, S2 must materialize a concrete timestamp and record it.

**S2.6 Replay Selector Normalizer**

* Normalize replay selector into one of:

  * explicit offset ranges (preferred), or
  * time window selector (allowed only if policy permits)
* It does **not** yet replay anything; it prepares the basis request.

**S2.7 Parity Anchor Extractor (optional)**

* If build_kind = parity_rebuild:

  * load anchor ref (from DLA exports)
  * extract required pins: `input_basis`, `target_snapshot_hash`, `feature_versions`
  * if missing → pin UNCHECKABLE explicitly (never guess)

**S2.8 Replay Basis Finalizer (via S3, still opaque)**

* Call S3 through **I2** to resolve:

  * time window → explicit offset ranges/checkpoints
  * EB vs Archive source plan
  * basis_hash + feasibility status
* This is still “pinning phase,” not “heavy compute.”

**S2.9 Plan ID Builder**

* Compute a stable **plan_id** (meaning-idempotency key).
* Produce the full **Pinned BuildPlan**.

---

## The Pinned BuildPlan (what S2 must output)

This is the “contract object” that makes the rest of OFS possible.

Minimum conceptual fields (in meaning terms):

* `plan_id` (stable digest of meaning pins)
* `build_kind` (dataset/parity/forensic/backfill/feasibility)
* `scope` (ContextPins filters, entity/event types, dataset scope selectors)
* `feature_profile_ref` (resolved revision + digest)
* `label_as_of_spec` (explicit cutoff + posture + rule id)
* `resolved_replay_basis` (partition → [from,to) offsets; or checkpoint form)
* `basis_hash`
* `source_plan_summary` (EB vs Archive slices)
* `strictness` (fail-closed vs allow-uncheckable; driven by policy + build_kind)
* `output_spec` (dataset kind + shaping intent)
* `policy_rev` + `env_profile_id`
* `build_provenance_stamp` (see below)

---

## The “build_provenance_stamp” pin (prevents a nasty drift bug)

We must prevent this failure mode:

> “Bug fix in OFS reconstruction logic → rerun uses same pins → system reuses old dataset because plan_id didn’t change.”

So, **plan_id must include a meaning-affecting provenance stamp**, such as:

* OFS build-profile revision, or
* code artifact digest/version (at least at major meaning-change boundaries), or
* an explicit “correction stamp” for backfills.

This is not overkill — it’s what makes **IL4 supersession** safe and prevents silent reuse of incorrect outputs.

---

# How S1 + S2 interact (their internal mini-graph)

```
BuildIntent
   |
   v
S1 Intake → S1 Ledger(RECEIVED)
   |
   v  I1
S2 Pinning pipeline
   |  (may call S3 for basis resolution, still “pinning”)
   v
Pinned BuildPlan (plan_id, basis_hash, versions, as-of, scope, policy_rev)
   |
   v
S1 Ledger(PINNED) → I12 preflight with S6 → route to IP* (later)
```

**Hard pin:** pins exist (and are persisted) before any replay/compute begins.

---

# Failure posture in S1+S2 (what they’re allowed to return)

S1+S2 can terminate early with explicit classes:

* **REJECTED** (invalid intent)
* **UNSATISFIABLE_IN_ENV** (e.g., archive required but disabled; time windows forbidden by policy)
* **UNCHECKABLE_EXPLICIT** (parity anchor incomplete; archive completeness unprovable and strictness allows uncheckable)
* **NEEDS_HUMAN/WAIT** (policy requires explicit choice; no default is allowed)

Dataset builds should default to **FAIL_CLOSED**; parity/forensics may allow UNCHECKABLE/INCOMPLETE if declared.

---

# The “no contradictions later” guarantee you asked about

This design *prevents* downstream contradictions because:

* S2 is the **single authority for meaning pins**; S3/S4/S5 are forbidden from inventing them.
* S1 is the **single authority for lifecycle**, and it only declares publish truth when S6 confirms commit.

So when we open S3/S4/S5/S6 later, they should not demand “new inputs” — they should consume the pinned plan and receipts we’ve already defined.

---

Absolutely. We’ll open **S3: History Acquisition & Replay Unifier**.

S3 is the “history physics engine” inside OFS: it turns a pinned replay request into **(a)** a **resolved offset basis**, **(b)** a **deterministic replay stream**, and **(c)** **completeness evidence/receipts** strong enough that S6 can publish a “complete” DatasetManifest without lying.

---

# S3’s boundary and promises

## What S3 is allowed to do

* Read **EB** (`fp.bus.traffic.v1`) and **Archive** (continuation of EB).
* Resolve a **time window selector** into an **explicit offset basis** (or declare it infeasible/unchecked).
* Emit **ReplaySlices** (partitioned, bounded chunks) and **ReplayReceipts**.
* Emit **completeness receipts** that gate publication (I13).

## What S3 is not allowed to do

* Invent feature versions, label rules, or scope (that’s S2).
* Assume a global order across partitions (only per-partition offset order exists).
* “Best-effort skip” missing ranges and pretend complete.

---

# S3 interfaces to other opaque nodes (the joins it must satisfy)

S3 has three critical internal joins:

### I2 (S2 → S3): ResolveReplayBasis

Input: `ReplayBasisRequest`
Output: `ReplayBasisResolution` (resolved basis + EB/Archive source plan + basis_hash + evidence refs)

### I5 (S3 → S5): Replay stream feed

Output: `ReplaySlice` batches (partitioned, deterministic slice_id) + `ReplayReceipts`

### I13 (S3 ↔ S6): Completeness receipts gate

Output: `SegmentReceipts` proving the delivered offsets match the resolved basis and are complete enough for the build kind.

S3 also supports **IP5 feasibility-only** (it runs I2 but does not stream I5).

---

# Internal machinery inside S3 (submodules)

Think of S3 as seven tightly-coupled internal boxes:

## S3.1 Capability & Envelope Probe

**Goal:** know what the environment can satisfy *before* deciding feasibility.

* EB retention boundary per partition (earliest retained offset, latest known).
* Archive availability and “completeness evidence” capability.
* Operational knobs (timeouts, max concurrent partitions, slice size policy).

**Outputs:** `EnvReplayCapabilities` (used to classify UNSATISFIABLE vs UNCHECKABLE).

---

## S3.2 Basis Resolver

**Goal:** produce a deterministic **resolved offset basis**.

Two input shapes:

1. **Offset-basis request** (preferred): already `{partition → [from,to)}`

   * Validate ranges, normalize half-open intervals.
   * Validate against retention/availability.

2. **Time-window selector** (allowed only as selector): `{from_ts_utc, to_ts_utc}`

   * Deterministically map to per-partition offset ranges.
   * If mapping cannot be made deterministic → return **INFEASIBLE** (don’t guess).

**Key pinned semantics:**

* Time windows are **half-open**: `[from_ts_utc, to_ts_utc)`
* Offset ranges are **half-open**: `[from_offset, to_offset)`

**Output:** `ResolvedBasis {partition → [from,to)}` + `basis_hash`.

---

## S3.3 Source Planner (EB vs Archive cutover)

**Goal:** decide *where each portion of the basis will be read from*.

Primary rule we pinned earlier:

* **EB for hot (within retention), Archive for cold (beyond retention)**.
* Avoid reading the same offset range from both sources unless policy explicitly enables overlap verification.

**Output:** `SourcePlan`:

* per partition: a list of segments like:

  * `[from,to) → EB`
  * `[from,to) → ARCHIVE`
* optional overlap policy:

  * `NO_OVERLAP_READ` (default)
  * `READ_BOTH_AND_COMPARE` (debug mode only; expensive)

---

## S3.4 Readers (adapters)

Two adapters with identical output shape:

### EB Reader

* Reads by partition + offset range.
* Guarantees monotonic offsets in its emission.

### Archive Reader

* Reads archived segments that preserve EB partition/offset coordinates.
* Must provide **completeness evidence** (segment manifests/checkpoints) sufficient to prove coverage for `[from,to)`.

**Important:** Archive isn’t “different data.” It must behave **as if EB**, just stored differently.

---

## S3.5 Slice Scheduler (deterministic chunking)

**Goal:** break the resolved basis into **ReplaySlices** that are:

* deterministic,
* restartable,
* parallelizable without changing meaning.

**Deterministic slice rule (pinned):**

* Slice boundaries must be derived from `(plan_id, partition_id, from_offset, to_offset, slice_policy_rev)` so two runs with identical pins produce identical slice IDs and boundaries.

**Output:** sequence of `ReplaySliceDescriptor`s:

* `{partition_id, [from,to), source, slice_id}`

---

## S3.6 Overlap / Duplicate Handler

**Goal:** handle the two realities:

* at-least-once duplicates,
* (rare) EB+Archive overlap windows.

**Pinned identity:** `event_id` is the dedupe key.

**Deterministic policy:**

* Within a partition, duplicates with the same `event_id` are tolerated; S3 can either:

  * emit duplicates but mark them in receipts (so S5 can deterministically dedupe), **or**
  * dedupe in S3 deterministically (recommended when overlap mode is enabled).
* If overlap read occurs (debug mode), S3 must record:

  * which source “won,”
  * counts of duplicates,
  * any mismatched payload digests.

**Output:** `OverlapDedupeReport` (goes into receipts/evidence).

---

## S3.7 Completeness & Receipt Builder

**Goal:** provide the evidence that lets S6 publish a manifest confidently.

S3 emits three tiers of receipts:

1. **Slice receipts** (per ReplaySlice):

* delivered offset range
* count of records
* anomalies (decode errors, gaps, duplicates observed)

2. **Partition receipts** (roll-up):

* union of delivered ranges
* proof that union == resolved basis for that partition (or explicit gap list)

3. **Basis receipts** (global):

* `basis_hash`
* EB/Archive coverage summary
* evidence refs (archive segment manifests, checkpoints)

These receipts are what flow over **I13** to gate “complete publish.”

---

# S3 execution modes (production paths)

## Mode A: Feasibility-only (IP5)

Runs:

* S3.1 capability probe
* S3.2 basis resolver
* S3.3 source planner
* S3.7 feasibility receipts (no streaming)

Returns a `FeasibilityReport`:

* FEASIBLE_EB_ONLY / FEASIBLE_REQUIRES_ARCHIVE / INFEASIBLE / UNCHECKABLE
* resolved basis (if time selector was used)
* evidence refs

**Hard pin:** no ReplaySlices, no dataset artifacts, no publish.

---

## Mode B: Full replay (IP1/IP2/IP3/IP4)

Runs:

* resolve basis (I2)
* schedule slices
* stream slices to S5 (I5)
* emit completeness receipts to S6 (I13)

**Hard pin:** S3 must never claim completeness until it can evidence coverage for the resolved basis.

---

# S3’s internal state machine (mechanical truth)

Minimal production state machine:

1. **INIT**
2. **CAPABILITIES_LOADED**
3. **BASIS_RESOLVED** (basis_hash computed)
4. **SOURCE_PLANNED** (EB/Archive segment plan)
5. **SLICES_SCHEDULED** (deterministic slice list)
6. **STREAMING** (emit slices + receipts)
7. **RECEIPTS_FINALIZED**
8. **DONE** | **INCOMPLETE_EXPLICIT** | **UNCHECKABLE_EXPLICIT** | **FAILED**

**Rule:** dataset-build paths usually forbid INCOMPLETE/UNCHECKABLE unless explicitly requested by build kind/policy.

---

# S3’s hard invariants (non-negotiable)

1. **Offsets/checkpoints are the basis**. Time is only a selector.
2. **No global order guarantee** beyond per-partition offset order.
3. **No silent gaps**: missing offsets → explicit INCOMPLETE/UNSATISFIABLE/UNCHECKABLE.
4. **Archive is continuation** of EB, preserving partition+offset semantics.
5. **Deterministic slice boundaries + slice IDs** for the same pinned plan.
6. **Receipts must be strong enough** for S6 to refuse to publish “complete” without them.

---

# Failure taxonomy (how S3 classifies problems)

This matters because S2/S1 need to decide “fail closed” vs “uncheckable.”

### UNSATISFIABLE

* archive disabled but required
* offsets earlier than earliest retained and no archive path exists

### INCOMPLETE

* archive exists but missing segments for required ranges
* EB retention boundary cuts off required offsets

### UNCHECKABLE

* archive data exists but completeness cannot be proven under policy
* parity anchor demands history that exists but lacks verifiable evidence

### FAILED

* IO failures, decode failures in admitted stream (should be rare and treated as incidents)

---

# Environment ladder posture (what differs without changing meaning)

* **Local:** often EB-only, short retention; S3 will frequently return UNSATISFIABLE for long windows. That’s fine—semantics unchanged.
* **Dev:** archive may exist but can be partial; S3 must surface INCOMPLETE/UNCHECKABLE explicitly.
* **Prod:** archive continuity + verifiable completeness becomes expected; S3 receipts become the backbone of audit-grade rebuilds.

---

# Drift tripwires (if we see these when implementing, we stop)

* “We can’t map time→offset deterministically so we’ll approximate.”
* “We’ll read whatever is available and call it complete.”
* “We’ll assume event_time order across partitions.”
* “We’ll publish without completeness evidence.”
* “Archive stores events without preserving EB coordinates, but we’ll pretend basis is offsets anyway.”

---

## Quick mental picture of S3’s machinery

```
CapabilitiesProbe → BasisResolver → SourcePlanner → SliceScheduler → Readers(EB/Archive)
                                                        |
                                                        v
                                              ReplaySlices (I5)
                                                        |
                                          Completeness/Receipts (I13)
```

---

Absolutely — we’ll open **S4: Truth Timeline Resolver (Label As-Of)**.

S4 is the “leakage firewall” inside OFS: it turns a pinned **LabelAsOfSpec** into a **deterministic, reproducible label view** that S5 can join to replayed facts *without ever reaching into the future* (unless explicitly requested as KNOW_NOW).

---

# S4’s boundary and promises

## What S4 is allowed to do

* Read from **Label Store** (append-only timelines).
* Enforce **as-of semantics** using *observed_time* and *effective_time* properly.
* Produce a **LabelView** keyed for joining to replay facts and/or entities.
* Produce **coverage diagnostics** and **evidence receipts** for the DatasetManifest.

## What S4 is not allowed to do

* Infer labels from decisions/outcomes (Label Store is the only label truth).
* Invent its own as-of cutoff (“now” must be materialized upstream and pinned).
* Silently “best-effort” by dropping label types/subjects if labels are required.
* Change feature versions, replay basis, or scope (that’s S2).

---

# S4 interfaces to other opaque nodes (the joins it must satisfy)

### I3 (S2 → S4): LabelAsOfContract

Input: `LabelAsOfSpec + LabelScope + strictness`
Output: an ACK (accepted/rejected/partial support)

### I6 (S4 → S5): Label view feed

Output: `LabelView` + coverage diagnostics + reproducibility marker(s)

### I8 (S4 → S6 via provenance bundle): Label receipts

Output: `LabelReceipts` (coverage, as-of posture, store state marker, evidence refs)

---

# Internal machinery inside S4 (submodules)

S4 is best thought of as 8 internal boxes:

## S4.1 Label Policy Loader (ruleset binding)

**Goal:** bind S4’s behavior to an explicit rule ID so “label meaning” is not implicit.

* resolves `label_resolution_rule_id` from policy (or verifies caller-provided rule ID)
* determines what constitutes “required label types” for the dataset kind
* defines defaults for “knew-then vs know-now” if permitted (but note: cutoff must still be explicit)

**Output:** `LabelPolicyBinding { rule_id, required_label_types, allowed_postures }`

---

## S4.2 Subject Mapping Resolver (join-key discipline)

**Goal:** decide *what the label subjects are* and ensure they are joinable to what S5 will produce.

There are typically 3 subject families in a fraud platform:

* **event-level** (subject = `event_id`)
* **entity-level** (subject = `merchant_id`, `card_id`, `account_id`, etc.)
* **case-level** (subject = `case_id`)

**Pinned behavior:** S4 must declare which subject key is used for this dataset build and fail closed if it can’t produce a joinable view.

**Output:** `SubjectKeyPlan`:

* subject_type (event/entity/case)
* subject_key_schema (e.g., “event_id string”, “merchant_id string”)
* mapping requirements (if event→case mapping is required, it must be explicit)

---

## S4.3 As-Of Cutoff Materializer (no implicit “now”)

**Goal:** enforce the explicit as-of boundary.

Inputs:

* `observed_time_cutoff_utc` (always explicit)
* posture:

  * **KNEW_THEN**: include only assertions with `observed_time <= cutoff`
  * **KNOW_NOW**: include assertions regardless of observed_time (but still record the requested cutoff as the “evaluation point”)

**Output:** `AsOfFilter` (a deterministic predicate)

**Hard pin:** As-of cutoff is applied on **observed_time**, never effective_time.

---

## S4.4 Timeline Query Planner (efficient + reproducible reads)

**Goal:** construct deterministic queries to Label Store that are:

* reproducible (same cutoff yields same results given same store state)
* scoped correctly (subject sets, label types, time ranges)

This planner decides:

* which tables/indices to hit
* whether to query by:

  * explicit subject list (if S2 provides a scope list), or
  * by time window / label types (if building broader datasets)

**Output:** `LabelQueryPlan` with query fingerprints (for evidence)

---

## S4.5 Timeline Extractor (append-only read)

**Goal:** fetch raw label assertions.

A label assertion record must conceptually include:

* `subject_key`
* `label_type`
* `label_value` (+ optional confidence)
* `effective_time`
* `observed_time`
* `provenance_ref` (by-ref) or provenance fields
* optional `supersedes_id` (or derived supersession chain)

**Output:** `LabelAssertionStream` (raw timeline slices)

---

## S4.6 Resolver / Collapser (turn timeline into a label view)

**Goal:** convert append-only assertions into the final “label view” under an explicit rule.

### Pinned v0 resolution rule (authoritative default)

For each `(subject_key, label_type)`:

* consider only assertions passing the as-of filter (observed_time cutoff for KNEW_THEN)
* choose the **latest observed assertion** as-of cutoff
  tie-break deterministically: `(observed_time, assertion_id)`
* interpret **effective_time** as “when it applies,” used when aligning to event time windows, but it does not override observed_time filtering.

This yields a single resolved label per subject per label type.

**Output:** `ResolvedLabelView`:

* rows keyed by subject_key
* each row includes resolved label values per label type (or a long-form table)

---

## S4.7 Coverage & Quality Diagnostics

**Goal:** produce visibility needed to decide whether a dataset is publishable.

Diagnostics include:

* coverage ratio: `labeled_subjects / subjects_in_scope` (if scope known)
* counts by label_type
* missing label types (required vs optional)
* late label rate (labels observed after cutoff) — useful to understand leakage pressure
* mapping failures (subjects that couldn’t be resolved)

**Output:** `LabelCoverageReport` + `AnomalyList`

**Hard pin:** If labels are required and coverage is below a configured threshold, S4 must surface that explicitly so the build can fail closed (unless intent allows unlabeled outputs).

---

## S4.8 Reproducibility Marker & Evidence Builder

**Goal:** produce a stable “label store state marker” for the manifest.

Because Label Store is a DB, reproducibility needs a marker like:

* a transaction snapshot ID,
* a high-watermark timestamp/LSN,
* or an application-level “label_store_version/watermark”

Exact mechanism is implementer choice, but S4 must output:

* `label_store_state_marker`
* query fingerprint(s)
* evidence refs (stats, counts, sample checks)

**Output:** `LabelReceipts` for I8:

* `label_as_of_spec` (echo)
* `rule_id`
* `label_store_state_marker`
* `coverage_report`
* `evidence_refs`

**Hard pin:** without a state marker, a “rebuild later” might be ambiguous; for training/eval reproducibility this marker is strongly recommended (mandatory in prod profiles).

---

# S4 state machine (mechanical truth)

Minimal production states:

1. **INIT**
2. **POLICY_BOUND**
3. **SUBJECT_PLAN_READY**
4. **ASOF_FILTER_READY**
5. **QUERY_PLANNED**
6. **ASSERTIONS_EXTRACTED**
7. **LABELS_RESOLVED**
8. **RECEIPTS_BUILT**
9. **DONE** | **FAILED** | **PARTIAL_EXPLICIT**

“PARTIAL_EXPLICIT” is only allowed if the dataset kind allows unlabeled outputs; otherwise fail closed.

---

# Hard invariants (non-negotiable)

1. **Observed-time controls knowability.** `observed_time <= cutoff` is the KNEW_THEN gate.
2. **Effective-time controls applicability.** Used for alignment, not for leakage filtering.
3. **No implicit as-of.** Cutoff must be concrete and recorded.
4. **Deterministic collapse rule.** Same inputs + same store state marker ⇒ same resolved labels.
5. **Join-key discipline.** If S5 expects event-level labels but S4 can only produce entity-level labels, that mismatch is explicit and build-breaking unless output_kind allows it.

---

# Failure taxonomy (what S4 returns and why)

* **UNSATISFIABLE_LABEL_SCOPE**: required label types/subjects cannot be provided
* **SUBJECT_MAPPING_MISSING**: cannot map subjects to required key space
* **LABEL_STORE_UNAVAILABLE**
* **ASOF_SPEC_INVALID**: cutoff missing/ill-formed
* **COVERAGE_BELOW_THRESHOLD** (if policy enforces)
* **RULE_NOT_SUPPORTED**: requested rule_id not implemented

Parity/forensics can allow “labels unavailable” if labels are optional; supervised training builds generally fail closed.

---

# Environment ladder notes (what differs without changing meaning)

* **Local:** may run with tiny label data; coverage thresholds can be relaxed, but the *rule semantics* don’t change.
* **Dev:** must catch mapping/subject-key mismatches and permission issues.
* **Prod:** requires strong reproducibility markers + strict leakage posture + coverage alerts.

---

# Drift tripwires (stop if seen)

* Using effective_time as the as-of gate.
* “Latest label” joins without observed-time cutoff.
* Silent dropping of required label types/subjects.
* Returning labels without any reproducibility marker in prod.

---

## Quick mental picture of S4’s machinery

```
PolicyBind → SubjectPlan → AsOfFilter → QueryPlan → ExtractAssertions
                                   ↓
                         Resolve/Collapse → Coverage → Receipts/Marker
                                   ↓
                              LabelView (I6) + Receipts (I8)
```

---

Absolutely — we’ll open **S5: Feature Reconstruction & Dataset Shaping**.

S5 is the “offline twin” of the Online Feature Plane’s semantics: it takes **replayed admitted facts** (from S3) and **as-of label views** (from S4), applies **version-locked feature definitions** (from S2), and emits **deterministic dataset/snapshot drafts** to S6 for publication.

---

# S5 boundary and promises

## What S5 is allowed to do

* Consume **ReplaySlices** (I5) and **LabelViews** (I6).
* Apply a **FeatureVersionSet** (I4) exactly as pinned (no substitutions).
* Maintain **per-key feature state** while replaying.
* Produce:

  * **feature snapshots** (parity-comparable when needed),
  * **training/eval datasets** shaped per output_spec,
  * **draft shards + stats + hashes** for S6 to publish.

## What S5 is not allowed to do

* Read EB/Archive directly (only S3 does that).
* Read Label Store directly (only S4 does that).
* Invent/resolve feature versions, label rules, or basis (S2/S3/S4 own those).
* Assume a global total order across partitions.
* “Fix” missing data by quietly dropping records/fields if the build kind requires completeness.

---

# S5’s external joins (what it must satisfy)

### I4 (S2 → S5): ExecutionPins

S5 must accept/decline compatibility with:

* `feature_profile_ref` (resolved revision + digest),
* `scope`,
* `output_kind / output_spec`,
  and must **fail closed** if incompatible.

### I5 (S3 → S5): Replay stream feed

S5 processes:

* partitioned slices `[from_offset, to_offset)` in partition offset order
* CanonicalEventEnvelope records.

### I6 (S4 → S5): LabelView feed

S5 receives:

* resolved labels consistent with `LabelAsOfSpec`,
* subject key discipline + coverage diagnostics.

### I7 (S5 → S6): DatasetDraft/SnapshotDraft

S5 emits:

* deterministic shard drafts,
* schema refs,
* content digests (or digest candidates),
* summary stats,
* snapshot hashes (when parity is enabled).

---

# Internal machinery inside S5 (submodules)

Think of S5 as 10 internal boxes. Each is “machinery” we’ll later deep dive, but naming them now prevents drift.

## S5.1 Feature Profile Loader & Compiler

**Goal:** turn `feature_profile_ref` into an executable feature graph.

* Loads the exact revision/digest (no “active/latest”).
* Validates it against:

  * allowed event_types,
  * required payload fields,
  * feature output schema,
  * canonicalization ruleset (if part of the profile).
* Produces a **CompiledFeaturePlan**:

  * feature list + stable ordering,
  * dependencies,
  * state requirements per feature group,
  * output schema reference.

**Pin:** compilation output must be deterministic for the same profile digest.

---

## S5.2 Event Decoder & Normalizer

**Goal:** convert CanonicalEventEnvelope into an internal typed event without losing meaning.

* Validates required envelope fields (`event_id`, `event_type`, `ts_utc`, …).
* Extracts join keys / entity keys required by the compiled plan.
* Normalizes:

  * timestamp parsing,
  * numeric canonical forms (if ruleset exists),
  * missing/optional fields behavior per profile.

**Pin:** normalization rules must be stable and versioned (either in the feature profile or a policy rev), because parity depends on it.

---

## S5.3 Deterministic Deduper / Integrity Filter

**Goal:** handle duplicates and corruption deterministically.

* Dedup key: `event_id` (platform-wide).
* If duplicates occur:

  * either treat later duplicates as no-ops,
  * or require exact payload match (mismatch becomes anomaly/failure based on strictness).

**Pin:** the dedupe policy must be deterministic and recorded (at least via policy_rev).

---

## S5.4 Key Router & Scope Filter

**Goal:** decide which events affect which feature states.

* Extracts one or more **feature subject keys** (entity_id / merchant_id / account_id / etc.).
* Applies `scope` filters from pinned plan:

  * include/exclude event_types,
  * include/exclude entities,
  * include ContextPins constraints if present.

**Pin:** scope filtering happens here, not downstream, so stats and manifests reflect reality.

---

## S5.5 Stateful Aggregation Engine (Feature State Store)

**Goal:** maintain per-subject feature state while replaying.

* Holds per-key state for feature groups (counts, sums, rolling windows, sketches, etc.).
* Must support incremental update per event.

**Important determinism pin:** the state evolution is defined by:

* replay inclusion (basis offsets),
* per-partition replay order,
* deterministic tie-breakers (when needed),
  not by concurrency scheduling.

(Implementation may parallelize; **meaning must be invariant**.)

---

## S5.6 Window/Time Semantics Manager

**Goal:** handle time-windowed features correctly using `ts_utc` as event meaning-time.

Key clarifications (pinned):

* **Inclusion** in the replay is by **offset basis**, not by event_time.
* **Feature calculations** may depend on `ts_utc` (e.g., “last 24h”), so late-arriving events (older ts_utc) still affect the state *once they appear*—consistent with “what was observed by basis.”

This keeps parity feasible: for the same basis offsets, both online/offline should reflect the same observed set of events.

---

## S5.7 Anchor Selector (what rows/snapshots we materialize)

**Goal:** decide *where* to emit examples/snapshots based on `output_spec`.

Three common anchor modes (still conceptual):

* **Per-event dataset:** one row per qualifying event; features computed “as-of just before/at that event” (must define tie-breaks; we’ll pin later).
* **Per-entity snapshot:** one row per entity at end-of-basis (or at declared cut points).
* **Per-window dataset:** one row per entity per window bucket (e.g., daily).

**Pin:** anchor selection must be deterministic given the same plan_id and replay.

---

## S5.8 Snapshot Builder

**Goal:** produce feature vectors at a specific as-of point.

Two snapshot styles:

* **End-of-basis snapshots** (common for parity).
* **Event-aligned snapshots** (common for per-event training examples).

**Pin:** snapshot definition must be explicit and recorded in output_spec/manifest (no implicit “current state”).

---

## S5.9 Label Joiner (supervised shaping)

**Goal:** join labels from S4 to the shaped outputs without violating as-of rules.

* Uses subject keys exactly as declared (event_id/entity_id/case_id).
* Never queries Label Store.
* Surfaces coverage issues explicitly (don’t silently drop unlabeled rows unless dataset kind allows unlabeled).

**Pin:** label join semantics are “as-of safe” by construction because S4 already enforced observed-time cutoff; S5 must not widen it.

---

## S5.10 Parity Hash Generator + Stats Reporter

**Goal:** produce the parity-comparable hashes and dataset diagnostics.

* **Snapshot hash** computed over:

  * feature vector values in a stable feature order,
  * stable canonicalization rules,
  * stable serialization rules for hashing.
* Dataset stats:

  * counts, min/max ts_utc, entity coverage,
  * feature list hash,
  * dedupe/anomaly counts.

**Pin:** hashing must be deterministic and tied to feature profile/policy rev; otherwise parity becomes meaningless.

---

# S5 state machine (production-shape)

Minimal, observable phases:

1. **INIT**
2. **PROFILE_COMPILED**
3. **COMPATIBILITY_OK** (I4 ack)
4. **CONSUMING_REPLAY** (I5 slices)
5. **STATE_UPDATED** (incremental)
6. **ANCHORS_EMITTED** (examples/snapshots produced)
7. **LABELS_JOINED** (if required)
8. **DRAFTS_EMITTED** (I7 to S6)
9. **DONE** | **FAILED** | **INCOMPLETE_EXPLICIT** (only if build kind permits)

---

# Determinism and ordering rules (the big drift killers)

## What S5 may assume

* Within a partition: offsets increase; process in that order.
* Across partitions: no order; any merge must be deterministic (e.g., sort keys if required).

## What S5 must *not* assume

* That `ts_utc` is monotonic.
* That there’s a global ordering across partitions.
* That duplicates won’t happen.

## Deterministic tie-breakers (pinned as a requirement)

Whenever S5 needs a stable ordering for a local operation (e.g., event-aligned snapshots), it must use deterministic fields, typically:

* `(partition_id, offset)` as the primary ordering token,
* and only use `ts_utc` for time-based calculations, not for replay ordering.

(Exact tie-break sequences can be pinned when we open S5.7/S5.8.)

---

# Failure taxonomy (how S5 fails without lying)

S5 should classify failures so S1/S6 can produce correct outcomes:

* **FEATURE_PROFILE_INCOMPATIBLE** (I4 fail)
* **EVENT_SCHEMA_MISSING_FIELDS** (required payload missing; strictness decides fail vs skip—default fail for dataset builds)
* **DEDUPE_PAYLOAD_MISMATCH** (same event_id different payload; usually fatal)
* **LABEL_JOIN_UNSATISFIABLE** (labels required but subject mapping missing / coverage below threshold)
* **CANONICALIZATION_RULE_MISSING** (if parity required and hash ruleset missing)
* **RESOURCE_EXCEEDED** (operational; should fail cleanly, no partial publish)

**Pin:** S5 may produce “partial drafts” during processing, but S6 must never publish a complete manifest unless receipts support completeness.

---

# Environment ladder implications (deployment realism)

* Local/dev/prod can differ in **volume**, **window sizes**, and **resource limits**, but S5 semantics don’t change.
* “Production-shaped local” matters especially for S5 because concurrency and chunking are where nondeterminism creeps in; local must exercise deterministic slicing (IL2) even on tiny data.

---

# Drift tripwires for S5 (stop immediately if seen)

* Feature versions substituted because requested revision unavailable.
* Label join re-queries Label Store or widens as-of.
* Hash computed with unstable feature ordering or non-versioned canonicalization.
* Any output shaped using “global time sort” rather than replay basis/offsets without explicit deterministic tie-break.

---

Absolutely — we’ll open **S6: Artifact Publisher & DatasetManifest Authority**.

S6 is the “truth boundary” inside OFS. Everything upstream (S3/S4/S5) can do a perfect job, and you can still ruin the system if publication isn’t **atomic, idempotent, and provenance-complete**. S6 is where “a dataset becomes real.”

---

# S6 boundary and promises

## What S6 is allowed to do

* Write to object store under `ofs/...` (materials + manifests + evidence artifacts).
* Construct and commit the **DatasetManifest** (the unit of truth).
* Enforce **immutability**, **idempotency**, and **supersession/backfill linkage**.
* Gate publication on **completeness evidence** (I13) and provenance bundle (I8).
* Provide stable publish receipts to S1 (I9), signal inputs to S7 (I10), and preflight reuse to S1/S2 (I12).

## What S6 is not allowed to do

* Recompute features or labels.
* Read EB/Archive/Label Store to “fill in missing provenance.”
* Publish “complete” outputs if it cannot prove completeness.
* Overwrite old datasets in place (corrections must supersede).

---

# S6’s external joins (what it must satisfy)

### I7 (S5 → S6): DatasetDraft/SnapshotDraft

S6 receives drafts/shards/stats, and stages them for publication.

### I8 (S2+S3+S4 → S6): Provenance bundle

S6 receives the pinned plan and receipts to build the manifest.

### I13 (S3 ↔ S6): Completeness receipts

S6 must verify replay completeness before committing a “complete” manifest.

### I12 (S1/S2 ↔ S6): Preflight existence check

S6 answers: “is a committed manifest already published for this plan_id/output_kind?” (+ supersession info)

### I9 (S6 → S1): PublishReceipt

S6 closes the truth boundary: published/not published + manifest ref + status class.

### I10 (S6 → S7): Signal inputs

S6 passes authoritative refs and outcomes to S7.

---

# Internal machinery inside S6 (submodules)

Think of S6 as 9 internal boxes:

## S6.1 Publish Identity & Namespace Builder

**Goal:** compute deterministic object keys and dataset identity.

Inputs:

* `plan_id`
* `output_kind` / dataset_kind
* `policy_rev` + `env_profile_id`
* (for backfill) supersession metadata / correction stamp

Outputs:

* `dataset_id` (stable dataset identity)
* `publish_prefix` (e.g., `ofs/datasets/{dataset_id}/...`)
* `staging_prefix` (e.g., `ofs/staging/{request_id or plan_id}/...`)

**Pinned behavior:** same meaning pins ⇒ same dataset_id (unless supersession/backfill changes pins explicitly).

---

## S6.2 Staging Area Manager

**Goal:** accept writes safely before the dataset is “real.”

Two valid models (we pinned earlier):

* **Model A:** S6 does final writes (S5 streams content to S6).
* **Model B:** S5 writes shards to staging prefix; S6 verifies and then commits a manifest that references them.

S6 supports either as an implementation choice. The invariant is:

> Nothing is “published truth” until the manifest commit happens.

S6.2 tracks:

* expected shard list (from I7)
* shard arrival and digest verification
* idempotent shard writes (same shard_id + same digest is okay)

---

## S6.3 Draft Integrity Verifier

**Goal:** ensure drafts are consistent and publishable.

Verifies:

* shard completeness (all expected shards exist)
* schema refs present and consistent
* digest match (if provided) or computes digests
* summary stats coherence (counts, min/max time, feature list hash)

**Pinned rule:** if shard digests mismatch, fail closed.

---

## S6.4 Provenance Assembler (Manifest Inputs)

**Goal:** assemble the self-sufficient provenance bundle for the manifest.

Consumes:

* **PinnedPlan** (S2): scope, feature_profile_ref, label_as_of_spec, output_spec, policy_rev
* **ReplayReceipts** (S3): basis_hash, resolved basis, source plan, evidence refs
* **LabelReceipts** (S4): as-of spec echo, rule_id, label store marker, coverage stats

**Pinned rule:** S6 may *validate* provenance, but must not create missing pins by itself.

---

## S6.5 Completeness Gate (I13 enforcement)

**Goal:** decide whether S6 is allowed to publish a COMPLETE dataset.

Mechanics:

* Compare `resolved_basis` from S3 receipts against the plan’s basis_hash.
* Confirm per-partition delivered ranges cover required ranges.
* Confirm archive completeness evidence exists when Archive is used.

**Outcomes:**

* **COMPLETE_ALLOWED**
* **INCOMPLETE_EXPLICIT_ALLOWED** (only if build kind allows)
* **UNCHECKABLE_EXPLICIT_ALLOWED** (parity/forensic)
* **FAIL_CLOSED** (dataset_build/backfill default)

**Pinned rule:** a dataset_build cannot be published as complete without completeness evidence.

---

## S6.6 DatasetManifest Builder (Unit of truth)

**Goal:** build the DatasetManifest as a *complete, self-contained* truth record.

### Minimal manifest content (pinned)

At minimum, the manifest must pin:

**Identity**

* `dataset_id`
* `dataset_kind` / output_kind
* `plan_id`
* `request_id` (optional but useful)

**Meaning pins**

* `feature_profile_ref` (revision + digest)
* `label_as_of_spec` (cutoff + posture + rule_id)
* `scope` (ContextPins filters, entity/event type scope)
* `policy_rev` + `env_profile_id`
* `build_provenance_stamp` (code/build profile identity)

**Replay basis**

* `stream_id` (fp.bus.traffic.v1)
* `basis_hash`
* per-partition offset ranges (or checkpoint form)
* source plan summary (EB vs Archive)
* completeness evidence refs (archive segment manifests/checkpoints)

**Materializations**

* list of artifacts:

  * object refs/paths
  * content digests
  * schema refs
  * row counts / partitioning info

**Diagnostics / evidence**

* replay counts, anomaly summaries
* label coverage stats
* dedupe/overlap report
* optional parity hashes/refs

**Supersession**

* optional `supersedes` list (old dataset_id/manifest_ref)
* optional backfill metadata (reason code, declared scope)

### Manifest must be “MF-sufficient”

MF must be able to train from a manifest without scanning the world. That is the core reason the manifest exists.

---

## S6.7 Atomic Commit Manager

**Goal:** commit publication in a way that is recoverable and race-safe.

S6 implements a strict commit protocol:

1. **Stage complete** (S6.2/S6.3)
2. **Provenance complete** (S6.4)
3. **Completeness gate passes** (S6.5)
4. **Write manifest draft** (staging)
5. **Commit manifest** (final location)
6. **Optionally write an index pointer** (e.g., plan_id → manifest_ref map) to support I12 quickly

**Pinned rule:** the manifest commit is the moment the dataset becomes real. Anything before that is not truth.

**Race handling:**

* If two jobs race to publish the same dataset_id:

  * only one should “win”
  * the loser must converge to **ALREADY_PUBLISHED** by reading the committed manifest and verifying plan_id/basis_hash match.

---

## S6.8 Supersession & Backfill Linker

**Goal:** represent corrections without rewriting history.

* For backfill runs, S6 records:

  * `supersedes` pointers (old dataset_id/manifest_ref)
  * backfill reason metadata
* S6 never deletes or overwrites the old dataset; it publishes a new identity with explicit linkage.

**Pinned rule:** supersession is explicit; any consumer who cares can follow the chain.

---

## S6.9 Receipts & Query Surfaces (I9/I12)

**Goal:** provide fast, deterministic answers to:

* “what was published?” (I9)
* “was it already published?” (I12)

### I12 support (preflight)

S6 should maintain a lookup surface such as:

* `ofs/index/by_plan/{plan_id}.json` → manifest_ref
  or equivalent. Exact structure is implementer choice; the behavior is pinned.

### I9 receipt

S6 returns:

* publish_outcome (NEW/ALREADY/SUPERSEDED/FAILED)
* dataset_manifest_ref
* dataset_id
* status_class (COMPLETE/INCOMPLETE/UNCHECKABLE/FAILED)
* evidence refs for failures

---

# S6 state machine (production-shape)

Minimal states:

1. **INIT**
2. **IDENTITY_COMPUTED**
3. **STAGING_OPEN**
4. **DRAFTS_INGESTED**
5. **PROVENANCE_READY**
6. **COMPLETENESS_VERIFIED**
7. **MANIFEST_BUILT**
8. **COMMITTING**
9. **COMMITTED** | **FAILED_NO_PUBLISH**
10. **RECEIPT_EMITTED**

---

# S6 hard invariants (non-negotiable)

1. **Dataset truth exists iff manifest is committed.**
2. **Manifest is self-sufficient** (pins basis/as-of/versions/scope/material refs/digests).
3. **No complete publish without completeness evidence.**
4. **Idempotency:** same meaning pins converge (NEW vs ALREADY) without creating drift.
5. **Supersession only** for corrections; never overwrite.

---

# Failure taxonomy (how S6 fails correctly)

* **INCOMPLETE_REPLAY** (missing required offsets; archive gap)
* **UNCHECKABLE_COMPLETENESS** (cannot prove archive completeness and strictness allows)
* **PROVENANCE_INCOMPLETE** (missing pins/receipts)
* **DRAFT_INTEGRITY_FAILURE** (missing shards, digest mismatch, schema mismatch)
* **COMMIT_CONFLICT** (race) → converge to ALREADY_PUBLISHED if compatible; else fail
* **STORAGE_IO_FAILURE**

Pinned behavior: failures must not produce a “success-shaped” manifest.

---

# Environment ladder posture

* Local: can use simpler index surfaces; may disable reuse; but commit semantics and immutability remain identical.
* Dev: must exercise race + retry + partial staging recovery.
* Prod: strict completeness gating, explicit backfill linking, governance facts enabled (via S7).

---

# Drift tripwires (stop if seen)

* Publishing without basis_hash/as-of/feature_profile_ref pinned.
* Publishing a “complete” manifest when completeness is unproven.
* Overwriting old datasets in place.
* Allowing plan_id reuse to hide a meaning-changing code/policy revision.
* Treating staged outputs as “published” without commit.

---

Absolutely — we’ll open **S7: Parity / Governance / Telemetry Signalling**.

S7 is the “external signalling skin” of OFS. It **does not create truth**; it **announces** and **proves** what S6 has already committed (and what parity checks conclude), and it emits the telemetry that makes the learning/correction loops operable.

---

# S7 boundary and promises

## What S7 is allowed to do

* Compute and emit **ParityResult** outcomes (MATCH/MISMATCH/UNCHECKABLE) using:

  * parity anchors (from DLA exports) + rebuilt outputs (from S6/S5)
* Emit **optional governance facts** to `fp.bus.control.v1`:

  * DatasetPublished, BuildFailed, BackfillDeclared/Completed, ParityResult
* Emit **OTLP telemetry** (traces/metrics/logs) with correct correlation keys
* Return a **SignalSummary** to S1 (I11)

## What S7 is not allowed to do

* Rebuild datasets, replay history, or query Label Store/EB/Archive to “verify”
* Publish dataset truth (only S6 does that via manifest commit)
* Trigger MF training or auto-backfill as the primary mechanism (it may announce; orchestration remains explicit)
* Silently suppress mismatch/uncertainty (UNCHECKABLE must be explicit)

---

# S7’s external joins (what it must satisfy)

### I10 (S6 → S7): Signal inputs

S7 receives:

* publish receipt core (dataset_id, manifest_ref, outcome)
* pinned plan summaries (basis_hash, versions, label-as-of)
* optional parity context (target snapshot hash, anchor ref, rebuilt snapshot hash/ref)
* evidence refs

### I11 (S7 → S1): Signal summary

S7 returns:

* what signals were emitted (or skipped by policy)
* parity outcome (if any)
* correlation tokens (trace IDs)
* warnings/errors for run ledger

---

# Internal machinery inside S7 (submodules)

Think of S7 as 7 internal boxes:

## S7.1 Signal Policy Evaluator

**Goal:** decide which signals are enabled in this environment/profile.

Inputs:

* `policy_rev`, `env_profile_id`
* build_kind (dataset/parity/backfill/forensic)
* strictness knobs (e.g., parity required? control-bus enabled?)

Outputs:

* `SignalPlan`:

  * emit DatasetPublished? (yes/no)
  * emit BuildFailed? (yes/no)
  * emit Backfill facts? (yes/no)
  * emit ParityResult? (yes/no)
  * telemetry level (full vs sampled)

**Pin:** policy determines emission; S7 must record “SKIPPED_BY_POLICY” explicitly when it doesn’t emit.

---

## S7.2 Parity Anchor Interpreter (optional)

**Goal:** validate and normalize the parity anchor.

A parity anchor (from DLA exports/provenance) must provide:

* target snapshot hash/ref
* input_basis (watermark/offset basis)
* feature version set used online (profile ref/digest)
* optional degrade posture / graph_version

S7 checks:

* anchor completeness
* whether the rebuilt run used the same basis and versions (based on S6/S2 pins)

If anchor is incomplete or incompatible → parity outcome is **UNCHECKABLE**.

---

## S7.3 Parity Comparator (optional)

**Goal:** compute ParityResult deterministically.

Inputs:

* `target_snapshot_hash` (from anchor)
* `rebuilt_snapshot_hash` (from rebuilt outputs)
* optionally: feature list hash, canonicalization ruleset id, basis_hash

Outputs:

* **MATCH** if hashes equal
* **MISMATCH** if hashes differ, plus:

  * mismatch classification (see below)
  * evidence refs
* **UNCHECKABLE** if missing prerequisites

### Parity mismatch classification (pinned categories)

S7 must classify mismatches into explicit buckets (at minimum):

* `BASIS_MISMATCH` (rebuilt used different input_basis)
* `VERSION_MISMATCH` (feature profile differs)
* `CANONICALIZATION_MISMATCH` (hash ruleset differs / feature order differs)
* `DATA_GAP` (replay incomplete/uncertain)
* `CONTENT_MISMATCH` (same basis/versions but hash differs)

This classification is critical for IL5 remediation (stabilization loop).

---

## S7.4 Control Fact Builder (optional)

**Goal:** build low-volume governance announcements.

S7 builds facts for `fp.bus.control.v1`, each containing:

* `event_type` (DatasetPublished / BuildFailed / BackfillDeclared / BackfillCompleted / ParityResult)
* minimal summary pins:

  * dataset_id, manifest_ref
  * plan_id, basis_hash
  * feature_profile_ref
  * label_as_of posture (if relevant)
  * status_class
* by-ref evidence pointers (parity report ref, failure evidence ref)

**Pin:** control facts are announcements; they never carry bulk dataset content.

---

## S7.5 Control Fact Emitter

**Goal:** send the control facts reliably under at-least-once conditions.

* Emits with a deterministic `event_id` (idempotency) such as:

  * hash(`event_type`, `dataset_id`, `plan_id`, `request_id`)
* If emission fails:

  * record failure in SignalSummary (do not lie)
  * the dataset remains published truth; signalling failure is separate

**Pin:** emission is best-effort-but-explicit; it must not affect the committed dataset truth.

---

## S7.6 Telemetry Emitter (OTLP)

**Goal:** emit traces/metrics/logs keyed to the run and its outputs.

### Correlation keys (pinned)

S7 must attach to telemetry:

* `request_id`, `plan_id`
* `dataset_id`, `dataset_manifest_ref`
* `basis_hash`
* `feature_profile_ref`
* `label_as_of_spec` summary
* `policy_rev`, `env_profile_id`
* build_kind
* parity outcome (if any)

### Minimum signals (pinned)

* trace span for signalling phase
* counters:

  * datasets_published_total
  * build_failed_total
  * parity_match/mismatch/uncheckable_total
* timers:

  * signalling_duration
* structured log entries:

  * dataset published (with refs)
  * parity outcome (with classification)
  * emission failures

(Exact metric names can be implementer choice; meaning and correlation are pinned.)

---

## S7.7 Signal Summary Builder (I11 output)

**Goal:** return a truthful, audit-friendly summary to S1.

Includes:

* list of signals attempted/emitted/skipped
* parity outcome + classification + evidence ref
* telemetry correlation tokens (trace_id root)
* warnings/errors (e.g., “control bus unreachable”)

**Pin:** S1’s run ledger must reflect signalling outcomes accurately; no implied emissions.

---

# S7 state machine (production-shape)

1. **INIT**
2. **POLICY_EVALUATED**
3. **PARITY_EVALUATED** (optional)
4. **FACTS_BUILT** (optional)
5. **FACTS_EMITTED** (optional)
6. **TELEMETRY_EMITTED**
7. **SUMMARY_BUILT**
8. **DONE** | **DONE_WITH_WARNINGS**

S7 should almost never “fail the run” once S6 has committed; signalling failures become warnings and are recorded explicitly.

---

# S7 hard invariants (non-negotiable)

1. **S7 never creates dataset truth** — only announces committed truth.
2. **Parity is explicit:** MATCH/MISMATCH/UNCHECKABLE; no silent “close enough.”
3. **Control facts are idempotent and low volume**, by-ref pointers only.
4. **Telemetry correlation keys are consistent across envs** (ladder-safe).
5. **Signalling failures do not rewrite run outcomes**; they are recorded as emission failures.

---

# Environment ladder posture

* **Local:** control-bus emission may be disabled by policy; telemetry still emitted to local OTel stack.
* **Dev:** control-bus emission should be enabled often to test idempotency and correlation.
* **Prod:** signalling is enabled and monitored; parity mismatches should feed IL2/L5 correction workflows operationally.

---

# Drift tripwires (stop if seen)

* S7 queries EB/Archive/Label Store to validate (creates a second truth path).
* S7 emits “DatasetPublished” without a committed manifest ref.
* Parity “fixes” mismatches by substituting versions/basis.
* Control facts carry bulk data or become a discovery mechanism (“train on whatever arrives”).
* Telemetry lacks the correlation keys needed to join to dataset manifests and decisions.

---

## USER: PASUE FOR REFLECTION

Totally. Here’s the “pause view” of what we’ve actually built — not as prose, but as the **structural reality** we now need to keep in our heads so we don’t accidentally simplify it away when implementation starts.

## What we’ve illuminated

We started with **OFS as one vertex** in the platform graph, then revealed that inside this one vertex is a **second production-grade graph**:

* **7 internal subnetworks (S1–S7)**, each with its own authority boundary
* **13 internal joins (I1–I13)** that enforce determinism and prevent hidden defaults
* **5 internal paths (IP1–IP5)** corresponding to real operational workflows
* **5 internal loops (IL1–IL5)** corresponding to real operational realities (retries, chunking, atomic publish, backfills, parity stabilization)
* Plus a full set of **non-joins** (forbidden edges) that keep trust boundaries intact

That’s not “over-design”; it’s the minimum set of moving pieces required to make replay + leakage-safe supervision + reproducibility + auditability work at production scale.

---

## Why it’s complex (and why it has to be)

OFS sits at the intersection of **four hard constraints** that can’t be wished away:

1. **History is large and partitioned** (no global order, duplicates exist, retention ends).
2. **Labels arrive late and change** (must support “knew-then” vs “know-now” without leakage).
3. **Feature definitions evolve** (version locking + parity against online requires exact version fidelity).
4. **Truth must be reproducible and auditable** (DatasetManifest is the truth unit; atomic publish; declared backfills).

Each of those constraints alone creates complexity; together they force the internal network we designed.

---

## The “spine” that keeps it coherent

Even with all that complexity, the design has a clean backbone:

### Pins-first spine

* **S1+S2** freeze meaning and lifecycle early
* Everything else becomes “just execution” against frozen pins

### Truth-boundary spine

* **S6** is the single place where outputs become truth (manifest commit)
* That makes retries, races, and partial work safe

### Correction spine

* **IL4/IL5** provide the only legitimate way to correct derived truth without rewriting primary truth

If we keep those three spines intact, the system remains understandable even as it grows.

---

## What makes this network safe to implement in parallel

We deliberately prevented cross-talk:

* S5 can’t “reach around” to EB or Label Store.
* S7 can’t “verify” by querying truth stores.
* S6 can’t invent missing provenance.
* S1 can’t decide meaning pins.
* S2 is the single meaning authority.

Those boundaries are what prevent contradictions when Codex starts implementing node-by-node.

---

## The right mental compression (so we don’t get overwhelmed)

If you want the simplest reliable mental model:

* **S1+S2:** *Freeze the contract* (what does this run mean?)
* **S3+S4:** *Acquire truth inputs* (facts + labels, both as-of safe and basis-pinned)
* **S5:** *Compute deterministically* (under version-locked semantics)
* **S6:** *Publish truth atomically* (manifest is the unit of reality)
* **S7:** *Announce + prove + observe* (parity/governance/telemetry)

That’s the whole machine in six lines.

---

## The two biggest drift risks to watch now

As we move into deeper dives or implementation, the biggest places teams accidentally drift are:

1. **Plan identity / pinning**
   If plan_id doesn’t include all meaning-affecting pins (including build/policy stamps), you’ll get silent reuse or false equivalence.

2. **Publish semantics**
   If anything is treated as “published” before a committed manifest exists, you’ll get partial truth and irreproducible training.

Everything else is secondary compared to those.

---

