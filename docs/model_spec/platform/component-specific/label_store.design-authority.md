# Label Store Design Authority

This file is a rough collection of design or brainstorm notes for the Label Store. It views the whole platform as a network and expands open the label store's position in this network and illuminates it.

---

Alright — we’ll keep **LS internals opaque** for now and pin **LS’s outer role/edges/behaviour** so tightly that the inner network later has no room to drift.

Everything below is **authoritative for this brainstorm**, constrained by the platform pins (J13/J14 + rails + deployment shape).   

---

## 0) What Label Store is in this platform (and what it is not)

### LS is

* The platform’s **lagged truth plane**: it turns “what we later learned” into **append-only label timelines** that learning can safely join back to events/decisions.  
* The **single truth writer** for labels. Labels become “truth” **only once written to LS**.  
* A **control-plane always-on service** with an authoritative **labels DB** (`label_store`).  

### LS is not

* Not a hot-path dependency: DF/AL/IEG/OFP do **not** consult LS to make real-time decisions. LS is for truth/learning, not for decision-time features. (This follows the plane boundaries: LS is a lagged truth loop behind Case/learning, not RTDL.)  
* Not a place where “evidence becomes truth automatically.” Outcomes/heuristics can be stored **as evidence refs**, but do not become labels unless an explicit label policy says so. 

---

## 1) LS’s non-negotiable “laws” (outer behaviour pins)

These are the behavioural pins that define the box from the outside:

1. **Append-only truth**
   Labels are **timelines**, not update-in-place. Corrections are new assertions; history remains.  

2. **Dual-time semantics are mandatory**
   Every label assertion carries:

   * **effective_time**: “when this label is true in the world”
   * **observed_time**: “when the platform learned it”
     and learning/exports must respect “as-of” rules to prevent leakage.   

3. **Learning consumes labels only from LS**
   No inferring labels from outcomes/decisions. LS is the only label truth input.  

4. **Joinability is by stable identifiers + by-ref evidence**
   The bridge is **ContextPins + IDs + refs** (audit record IDs, EB coordinates, artifact refs). LS does not require copying raw payloads to be “complete.”  

5. **Idempotency is assumed**
   Duplicates/retries must not create duplicate timeline entries. (Platform rail: at-least-once is normal; labels are append-only but idempotent at the write boundary.) 

6. **Label timelines are primary truth and cannot be “backfilled as mutation”**
   Backfill may rebuild *derived* artifacts, but **must not rewrite label history**. 

---

## 2) LS in the larger network: its outer edges

Think of this as the **adjacency list** for LS in the platform graph.

### Inbound (writers into LS)

**J13: Case Workbench → LS**

* What crosses: **LabelAssertions** written as timeline entries. 
* Case Workbench is a workflow/UI that produces assertions; LS is where they become truth. 

Also allowed (same semantics as Case assertions, just different “source”):

* **Delayed external outcomes** (e.g., disputes/chargebacks) written as label assertions (either via Case workflow or a feed that produces assertions). 

### Outbound (readers from LS)

**J14: (LS + EB/Archive) → Offline Feature Plane Shadow**

* Offline Shadow reads labels from LS using **explicit as-of rules** and joins them to replayed event history. 

Then downstream:

* **Offline Shadow → Model Factory** through DatasetManifests (LS doesn’t feed MF directly; MF consumes manifests that embed label as-of boundaries).  

### Optional (not required for correctness)

* **LS → `fp.bus.control.v1`** “label_written / label_corrected” low-volume control facts (useful for triggers/alerts). This is explicitly allowed as optional in deployment wiring. 

---

## 3) What must cross each join (without turning this into a contract)

### J13 — Write surface: what a LabelAssertion *must* contain

The platform already pins the minimum. I’m going to make it operationally crisp (still conceptual, not schema):

**Required fields**

* **subject**: one of `(event | entity | flow)` (the platform pin), plus a stable subject identifier (e.g., `event_id`, `entity_ref`, `decision_id/request_id`).  
* **label value**: the asserted truth (plus optional confidence). 
* **provenance**: who/what process asserted it (human investigator, dispute feed, adjudication job, etc.). 
* **effective_time** + **observed_time**.  

**Pinned join pins (scope)**

* Because labels participate in J13–J15 and Rails require run/world joinability, LS assertions must carry **ContextPins** `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` when the subject is run/world-joinable.  

**Evidence posture (by-ref)**

* A label assertion may include **evidence refs** (audit record IDs, EB coords, artifact refs), but not raw payloads.  

### J14 — Read surface: what Offline Shadow must be able to ask LS

Offline Shadow’s requirement is “deterministic rebuild as-of time T” and labels must be read using effective/observed rules. 

So LS must support (conceptually):

* **timeline(subject)**: append-only list of label assertions for that subject.
* **label_as_of(subject, as_of_time)**: “what did we know by time T?” (leakage-safe).
* **bulk label_as_of**: because shadow rebuild is at dataset scale, LS must support querying many subjects for a declared as-of boundary (not necessarily via one API call — just as a capability).  

---

## 4) The one thing we MUST pin hard: the “as-of” rule (leakage safety)

This is the **core behavioural definition** LS contributes to the platform.

### Two distinct questions LS must answer

1. **What is the truth about the subject?** → that’s what the timeline + effective_time represents.
2. **What did the platform know at time T?** → that’s what observed_time + as-of provides. 

### My authoritative v0 as-of semantics (simple, safe, deterministic)

* **Eligibility rule (knowledge cut):**
  For an as-of query at time `T_asof`, LS considers only assertions with `observed_time <= T_asof`. 
* **Interpretation rule (truth application):**
  Among eligible assertions for the same subject + label-family, LS interprets the label using the timeline order and explicit supersedes/corrections (see next section). 
* **No hidden “now”:**
  Every query that claims to be leakage-safe must supply `T_asof`. If no as-of is supplied, the result is explicitly “as_of = now” and must be treated as *not* evaluation-safe by default.  

This matches the platform’s pinned “as-of everywhere” posture. 

---

## 5) Corrections + conflicts: how LS stays truthful without rewriting history

The blueprint pins: corrections are new assertions that “supersede/override in interpretation.” 
So we must define what that means externally.

### Correction posture (authoritative)

* A correction is a **new assertion** that either:

  * explicitly references what it supersedes, **or**
  * is implicitly “later knowledge” and overrides in interpretation under a deterministic rule. 

### Conflict posture (authoritative v0)

* LS always preserves **both** assertions in the timeline.
* For **resolved views** (e.g., `current_label` / `label_as_of`), LS must be deterministic and must not silently invent truth:

  * If a single “winner” exists under the rule → return it.
  * If not → return **CONFLICT** (with the competing candidates + provenance), forcing the consumer (Offline Shadow / MF) to choose a policy intentionally.

This keeps LS from being a hidden policy engine while still making it usable for learning.

---

## 6) Idempotency and write outcomes (what callers can rely on)

Because duplicates/retries are normal platform-wide, LS must provide a stable write outcome. 

Authoritative v0 behaviour:

* Each write includes an **idempotency handle** (however you encode it later).
* LS returns one of:

  * **ACCEPTED** (new timeline entry appended)
  * **DUPLICATE** (same assertion already recorded; no new entry)
  * **REJECTED** (invalid subject/pins/time semantics/unauthorized source)
* Replays of the same write must produce the same outcome and must not create new timeline entries.

(We’re not spec’ing the exact key recipe yet — just pinning the external behaviour.)

---

## 7) Operational reality pins (still “outer network”, not internals)

### Deployment shape

* LS is an **always-on service** with a query surface (low-QPS) and an authoritative DB (`label_store`).  

### Backfill/retention posture

* Label timelines are **primary truth** and are not rewritten by backfill. Backfill can rebuild *derived* exports or indexes, but not mutate history. 

### Optional event emission

* If LS emits events, they go to **control bus**, not traffic bus, and they’re notifications/pointers—not an alternate label truth channel. 

---

## 8) What we’ll do next (still outer-first, then inner)

If we stay disciplined to your method, the next “outer expectation” to pin is:

1. **Subject model**: concretely define `subject (event/entity/flow)` in platform terms (what IDs are valid, and how ContextPins scope them). 
2. **Label family taxonomy v0**: the minimal set of label families/value meanings that learning can rely on without inventing semantics. 
3. **The exact “resolved view” rule** for `label_as_of` (tie-breaks, source precedence posture, conflict surface).

Once those three are pinned, the LS inner network almost designs itself, because the box has no wiggle room left.

---

Yes — there are a handful of **LS “platform-shaping pins”** worth locking **before** we even talk about joins, because they determine what the joins *mean* and prevent downstream drift.

Here’s the short list I would pin up front (authoritative for our brainstorm), with what each pin buys us:

## Pins to lock early

### 1) Authority boundary: who can write label truth

Pin **which producers are allowed to create label assertions** (e.g., Case Workbench + specific outcome feeds), and explicitly that everything else is **evidence only** (DF/AL/DLA do not “write labels”). This is the core “truth vs evidence” guardrail.  

### 2) Append-only correction law (no mutation)

Pin that LS is **append-only timelines**, and “corrections” are **new events that supersede**, never silent edits. This matches the platform’s append-only rail for ledgers/labels.  

### 3) Dual-time semantics + the as-of rule

Pin that LS carries **effective_time vs observed_time**, and that **as-of queries are defined by observed_time** (knowledge cut), with no hidden “now”. This is explicitly called out as a platform rail and the leakage-safety basis for learning.  

### 4) Target model (what can be labeled) + required join keys

Pin the canonical **label target types** (platform mentions event/entity/flow for labels), and the **minimum join keys** per type. Also pin whether targets are **run/world-scoped via ContextPins** when they claim joinability. Without this, every consumer will invent a different join key.  

### 5) Conflict posture (when two truths disagree)

Pin what LS returns when two eligible assertions conflict:

* keep both in the timeline (always),
* and for “resolved views” either pick deterministically **or** return an explicit **CONFLICT** state (my preference for v0, because it prevents LS from becoming a hidden policy engine). This is the biggest “silent drift” risk if left ambiguous. 

### 6) Read views semantics (even if internals stay opaque)

Pin the meaning of the three canonical reads:

* `timeline(target)`
* `label_as_of(target, T)` (leakage-safe)
* `current_label(target)` (explicitly “as-of now”, not evaluation-safe unless declared)
  This ties directly to the “time semantics never collapse” rail. 

### 7) Idempotent write behaviour

Pin that retries/duplicates are normal platform-wide, so LS writes are **idempotent** and return a stable outcome (accepted/duplicate/rejected). This aligns with end-to-end idempotency posture.  

### 8) Evidence-by-ref + privacy posture

Pin that LS stores **by-ref evidence pointers**, not raw sensitive payloads, consistent with the platform’s “object store holds by-ref artifacts/evidence” substrate posture. 

### 9) Export basis alignment with DatasetManifest

Pin that when labels are used for training/eval, the **DatasetManifest** must record the **label as-of boundary + join keys + replay basis** (LS doesn’t define the manifest, but LS must support the semantics the manifest needs). 

### 10) Deployment truth: LS is an always-on authoritative DB timeline service

Pin the operational identity: **LS is always-on**, authoritative, and lives in the `label_store` DB with an **as-of query surface**; optional low-volume control events are allowed.

---

## The minimal “pin set” I’d do first (if you want it ultra-focused)

If we only pin *three* things to start brainstorming safely, it’s:

1. **Target model + join keys**
2. **As-of rule (observed_time discipline)**
3. **Conflict posture for resolved views** 

Once those are nailed, the joins become straightforward to reason about.

---

Yep. If LS stays **opaque**, then the “complete view” you want is: **every edge that can legally touch LS**, plus the **multi-hop paths and cycles** those edges participate in, in a production-shaped deployment.

Below is the **LS-centric join / path / loop catalogue** (with *pinned* vs *optional* clearly marked).

---

## LS-centric “outer graph” (one diagram)

```
                     (hot path evidence)
fp.bus.traffic.v1 ──> IEG ─> OFP ─> DF ─> AL ──┐
     │                     │          │       │
     │                     └──────┐   └────┐  │
     │                            │        │  │
     └───────────────> DLA (audit flight recorder) <────────┘
                           │   (by-ref evidence)
                           v
                  Case Workbench / Case Mgmt
                   │          ▲
         J13 write │          │ read (timeline/UI)
                   v          │
                Label Store (LS)
                   │
                   │  J14 read (as-of labels)
                   v
       Offline Feature Shadow (OFS job)
          │
          │ J15 DatasetManifest
          v
       Model Factory (MF job)
          │
          │ J16 Bundle publish
          v
   Model/Policy Registry ────────────────> DF (active bundle resolution)

Optional control emissions:
LS ──> IG ──> fp.bus.control.v1  (label_written / label_corrected)
```

This diagram is literally the “human truth + learning loop” spliced into the “decision evidence loop” as your blueprint pins it.    

---

## 1) All **direct joins** that can touch LS (vertex is opaque)

### Pinned joins (must exist)

**J13 — Case Workbench → LS (WRITE)**

* **What crosses:** LabelAssertions appended to timelines (subject + value + provenance + effective_time + observed_time; corrections are new assertions). 
* **Substrate:** `label_store` DB (LS is the authoritative writer). 

**J14 — (LS + EB/Archive) → Offline Feature Shadow (READ)**

* **What crosses:** leakage-safe “as-of” label reads + replay basis for deterministic rebuild. 
* **Substrate:** OFS reads `label_store` DB as-of, and replays admitted history from EB+Archive.  

### Implied-but-production-required joins (they exist if the platform is usable)

**LS → Case Workbench (READ)**

* Case tools must be able to read label timelines/current interpretations to display / reconcile investigations.
* This is reflected in the deployment wiring (“Case Workbench … Label Store reads”). 

### Optional joins (allowed; not required for correctness)

**LS → IG → fp.bus.control.v1 (EMIT control facts)**

* Optional label events (“label_written/label_corrected”) on the **control bus**, not traffic. 
* If emitted, they must go through IG/EB front door (same producer rule). 

**External adjudication feeds → LS (WRITE)**

* Disputes/chargebacks/delayed outcomes are explicitly named as label assertion sources (either mediated by Case tooling or a controlled feed writer). 

**Model Factory → LS (READ, optional)**

* The substrate map notes labels are used by Offline Shadow **and Model Factory** via as-of; MF may query LS directly for evaluation or audit-consistent label slices, even if training inputs come via OFS DatasetManifests.  

**Data Engine truth_products → (writer) → LS (WRITE, optional but important for closed-world realism)**

* Engine exposes `truth_products` (labels/case timelines) as **surfaces**, not traffic.  
* Because “learning consumes labels only from Label Store,” the safe way to use engine truth is: an explicit writer translates truth_products into LabelAssertions and writes them into LS with observed_time discipline (so LS remains the only label truth for learning).  

---

## 2) All **production paths** that touch LS (multi-hop)

I’m going to list these as “path templates” you’ll see in a production-ready deployment.

### A) Evidence → Investigation → Label truth (hot path feeding LS via humans)

**P-A1 (Decision evidence to label):**
`EB → (IEG/OFP) → DF → (decisions/intents to EB) → DLA → Case → LS`

* RTDL outputs are evidence; DLA is the flight recorder; Case consumes by-ref evidence; LS stores truth.  

**P-A2 (Action outcomes to label):**
`EB → AL → (outcomes to EB) → DLA → Case → LS`

* Same structure; outcomes are evidence until a label assertion is written.  

**P-A3 (Manual action loop feeding labels):**
`Case → (manual ActionIntent) → AL → (outcome) → DLA → Case → LS`

* Manual interventions must go through AL; labels still become truth only in LS. 

### B) Label truth → Offline rebuild → Training → Deployment (the learning path)

**P-B1 (Core learning pipeline):**
`LS (as-of labels) + EB/Archive (replay) → OFS → DatasetManifest → MF → Registry → DF`

* This is literally J14 → J15 → J16 chained into deployment reality.  

**P-B2 (Repro / audit evaluation path):**
`DLA exports + LS timelines + EB basis → OFS/MF evaluation`

* Blueprint explicitly calls out learning uses replayable facts + audit/provenance record + labels.  

### C) Synthetic closed-world truth injection (optional, but coherent)

**P-C1 (Engine oracle labels without leakage):**
`SR run_facts_view → Engine truth_products (by-ref, gated) → (Oracle label writer) → LS → OFS`

* Engine truth_products are “surfaces” not traffic; they must not leak into the hot path, but can support offline eval/training—safely—through LS.  

### D) Control-plane / automation triggers (optional)

**P-D1 (Label event triggers):**
`LS → IG → fp.bus.control.v1 → (Run/Operate / monitoring / schedulers) → OFS or MF jobs`

* Deployment notes explicitly allow optional label events on the control bus.  

---

## 3) The **loops/cycles** that include LS (the “closed circuits”)

### Loop L1 — The core improvement loop (pinned)

`DF/AL evidence → DLA → Case → LS → OFS → MF → Registry → DF`

* This is the platform’s “decision → truth → learning → deployment” feedback loop.  

### Loop L2 — Human correction loop (pinned behaviour)

`Case → LS (assert/correct) → Case (read timeline) → LS (further corrections)`

* Append-only corrections with supersedes semantics; case tooling reads the evolving truth and can correct it again.  

### Loop L3 — Manual action loop (pinned)

`Case → AL (manual action) → DLA evidence → Case → LS`

* Manual side effects are auditable; labels can reflect final adjudication. 

### Loop L4 — Control-plane automation loop (optional but production-real)

`LS emits control fact → scheduler/run-operate triggers rebuild → OFS updates manifests → MF produces bundles → Registry updates ACTIVE → DF behaviour changes → new evidence → new labels`

* This is how “label volume/lag/drift detected” can trigger refresh, without changing the graph’s meaning.  

### Loop L5 — Closed-world oracle loop (optional, simulation-specific)

`Engine truth_products → LS (via explicit writer) → OFS/MF → Registry → DF → (decisions) → Case/LS (compare vs oracle for eval)`

* Uses engine truth strictly outside the hot path; LS remains the single label truth for learning.  

---

## 4) Explicit **non-joins** (things that must *not* exist, to prevent drift)

These are as important as the allowed edges:

* **LS → DF / hot path**: LS must not become an online feature source or decision input. (Labels are lagged truth; hot path is driven by admitted traffic + projections.) 
* **RTDL writes labels directly**: DF/AL/DLA are evidence producers; labels become truth only via LS writes. 
* **Engine truth_products treated as traffic**: truth_products are surfaces; if they influence learning, it must be via LS (or you’ve broken the “LS-only labels” rule).  

---

Here’s the **recommended expansion order** for the **complete LS outer network** (vertex stays opaque), grouped as **Joins → Paths → Loops**.

## A) Direct joins that touch LS (expand first)

1. **J13 — Case Workbench → LS (WRITE)**: LabelAssertions (append-only; effective_time + observed_time; corrections as new assertions).  
2. **(Implied) LS → Case Workbench (READ)**: timelines / current / as-of views for investigation workflow.  
3. **(Production-real) External adjudication feeds → LS (WRITE)**: delayed outcomes (e.g., disputes/chargebacks) expressed as LabelAssertions (directly or via Case workflow).  
4. **J14 — (LS + EB/Archive) → Offline Feature Shadow (READ)**: label as-of rules + deterministic replay basis inputs.  
5. **(Optional) LS → IG → `fp.bus.control.v1` (EMIT)**: low-volume label notification facts (label_written/label_corrected).  

## B) Downstream joins that complete the LS learning chain (expand second)

6. **J15 — Offline Shadow → Model Factory**: DatasetManifests pin replay basis + label as-of boundary + join keys.  
7. **J16 — Model Factory → Registry**: bundles + promotion evidence (including which DatasetManifests were used). 
8. **Registry → DF (ACTIVE resolution)**: DF consumes Registry’s ACTIVE bundle decision (to close the feedback loop). 

## C) Production paths that include LS (expand third)

9. **P1 — Evidence → investigation → truth**: EB / DF / AL / DLA evidence refs → Case Workbench → (J13) LS.  
10. **P2 — Truth → rebuild → train → deploy**: (J14) LS+EB/Archive → OFS → (J15) MF → (J16) Registry → DF.  
11. **P3 — Late truth path**: external adjudication → (J13) LS → (J14) OFS → MF → Registry.  
12. **P4 — Optional automation path**: LS emits control fact → scheduler/Run-Operate triggers OFS/MF jobs → Registry updates → DF behaviour shifts.  

## D) Platform loops/cycles that include LS (expand last)

13. **L1 — Core improvement loop**: P1 + P2 chained (decisions → labels → training → new bundle → new decisions).  
14. **L2 — Human correction loop**: Case ↔ LS (append-only corrections over time). 
15. **L3 — Manual action loop**: Case → AL (manual action intent) → DLA evidence → Case → LS.  
16. **L4 — Optional ops automation loop**: LS control events → jobs/backfills → new manifests/bundles → DF → new evidence → new labels.  

---

Absolutely — here’s a **thorough, production-shaped expansion** of **A1–A3**, keeping **LS opaque** (we define only what must be true at the boundary).

---

## A1) Case Workbench → Label Store (WRITE)  **(J13)**

### What this join *is for*

This join is the **only place label truth is created** in the platform: **labels become truth only when stored in LS**. Case Workbench is a human workflow that *produces assertions*, but LS is the **single truth writer**.  

It exists to formalize the separation:

* RTDL outputs (decisions/intents/outcomes) are **evidence**, not truth labels. 
* Case consumes evidence **by-ref**, builds an immutable case timeline, and produces **label assertions**. 
* LS stores those assertions as **append-only label timelines** with **effective vs observed time** and **as-of semantics**.  

### What must cross the join (conceptual “LabelAssertion”)

Per the blueprint pin, each assertion carries at minimum: 

* **subject**: `(event | entity | flow)`
* **value** (+ optional confidence)
* **provenance** (who/what process)
* **effective_time**: when the truth applies in the world
* **observed_time**: when the platform learned it

Additionally, to obey the platform’s join rails:

* **ContextPins** are the platform’s canonical join pins `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` when the label claims run/world joinability. 
* Evidence stays **by-ref**: Case/labels point to audit record IDs / EB coordinates / artifact refs; do not copy big payloads.  

### The behavioural guarantees of this join (what Case can rely on)

**1) Append-only truth evolution**
A label write never “edits” history; it appends a new timeline entry. If an investigator changes their mind, that’s a **new assertion** that *supersedes in interpretation* (history remains).  

**2) Idempotent write boundary**
Because at-least-once / retries are normal in this platform, Case → LS must be safe under duplication: a repeated write does not create duplicate timeline entries; the join yields a stable outcome (e.g., accepted vs duplicate vs rejected). This follows the global idempotency rail. 

**3) “No hidden now” at write time**
LS must preserve both times; Case can’t “collapse time” by only writing “now.” The platform explicitly pins time semantics separation and explicit as-of posture. 

### How Case uses evidence without turning evidence into truth

The key guardrail: **system-derived outcomes may be stored as evidence refs, but they do not become truth unless label policy explicitly says so.** 
So a typical investigator label assertion carries pointers like:

* the DLA audit record id(s),
* EB coordinate(s) for the triggering events,
* action outcome reference(s),
* supporting documents as object-store refs,

…but the asserted label is still a human (or explicitly-authorized) truth claim.  

### Operational substrate expectations (still “outer join”)

* LS persists truth in the **authoritative `label_store` DB**. 
* Case Workbench is always-on and writes labels **via Label Store**, not directly into some shared table.  

---

## A2) Label Store → Case Workbench (READ)  **(implied but production-required)**

This join is implied by production reality: Case Workbench must be able to *see* the label truth it created (and its full history) while investigating and correcting. Deployment mapping explicitly shows **Case Workbench reads Label Store**.  

### What Case needs to read (the minimum set of views)

Even with LS opaque, Case needs three conceptual reads:

1. **timeline(subject)**
   Returns the append-only label assertion history for the subject (including provenance and the dual times). This is needed to show “what changed, when, and why.” 

2. **label_as_of(subject, T_asof)**
   Returns “what we knew by time `T_asof`” using the platform’s as-of discipline (leakage-safe semantics are pinned platform-wide; “no hidden now”).  

3. **current_label(subject)**
   A convenience read meaning “as-of now.” It must be explicitly treated as **not** evaluation-safe unless the as-of boundary is declared. 

### What Case does with these reads (and what it must not do)

* Case uses these reads to render the investigation state, justify decisions, and decide whether to correct. 
* Case does **not** use LS as a hot-path decision input; it’s a human truth surface behind the RTDL loop. (This follows the pinned plane separation around truth vs evidence.)  

### Consistency expectations

Because LS is authoritative truth, Case must treat LS reads as the source of truth for labels (Case DB remains the case story; LS is the label truth timeline). The platform’s substrate map pins Label Store timelines as a primary non-negotiable truth.  

---

## A3) External adjudication feeds → Label Store (WRITE)  **(delayed truth writers)**

The blueprint explicitly calls out **delayed external outcomes like disputes/chargebacks** as sources of label assertions, alongside investigators.  

### What this join must mean (authoritative stance)

External adjudication is **allowed to assert label truth**, but only by producing the same kind of **LabelAssertion** that Case would produce, including:

* subject + value,
* provenance identifying the external system/process,
* effective_time vs observed_time,
* and by-ref evidence pointers where available.  

### Two production-real wiring patterns (both legal)

**Pattern 1: Feed → Case → LS**

* The external outcome becomes a case event/task first (human review), then the investigator writes the final label to LS.
  This preserves maximum human control, but adds latency.

**Pattern 2: Feed → LS directly (recommended for “obviously authoritative” outcomes)**

* A small ingest adapter maps the external outcome into a LabelAssertion and writes to LS immediately.
* Case Workbench can then *read* it, attach it to a case, or open a case if needed.

Both are consistent with the platform pin (“Investigators and delayed external outcomes produce label assertions; LS is the truth store”). 

### The critical semantics for external writes

**1) Idempotency must be first-class**
External feeds commonly redeliver. The LS write must be idempotent under a stable source identity (e.g., source_system + source_event_id) so the label timeline isn’t polluted. This is required by the platform’s at-least-once posture. 

**2) Time semantics must reflect “late truth”**

* **effective_time**: when the adjudicated truth applies (often earlier than discovery)
* **observed_time**: when the platform learned it (feed arrival / import time)
  This is exactly why the platform pins dual-time + as-of reads.  

**3) Joinability rules still apply**
If the external outcome references an event/decision in EB, it must carry enough stable identifiers to join (event_id/decision IDs + ContextPins when applicable). The platform pins join-by-refs + ContextPins as the bridge.  

### Optional but useful: emitting a notification

After an accepted external label write, LS may optionally emit a **low-volume control fact** (e.g., `label_written`) to `fp.bus.control.v1` so schedulers/case automation can react — this is explicitly allowed in the deployment mapping. 

---

Sure — here’s **A4–A5** expanded in **production terms**, keeping **LS opaque** (we only pin what the *rest of the platform* must be able to assume).

---

## A4) (Label Store + EB/Archive) → Offline Feature Plane Shadow (READ)  **(J14)**

### What this join exists to do

This join is the **training/analysis reconstruction bridge**: it gives Offline Shadow the **exact inputs needed to rebuild datasets/snapshots deterministically “as-of time T”**, without leakage and without “grab whatever history exists today.”   

Think of it as: **(facts spine) + (truth timelines) + (explicit basis) → reproducible dataset build**.  

---

### Inputs that cross the join (what OFS is allowed/required to read)

#### 1) Admitted event history: EB *and* Archive as one logical stream

* OFS may read history from **EB within retention** and from **Archive beyond retention**, but it must treat them as **the same logical fact stream**: same event identity (`event_id`) and **same ordering basis per partition**.  
* The Archive is explicitly pinned as a **continuation of EB**, not a second truth. 

**What that means operationally (outer expectation):**

* OFS is not allowed to “switch semantics” when it crosses retention boundaries; replay determinism must survive EB→Archive boundaries. 

#### 2) Labels: read from LS using explicit as-of rules (leakage safe)

* Labels are read from **Label Store** using explicit **as-of** rules that respect **effective_time vs observed_time**, so training can produce “what we knew then” vs “what we know now” without confusing the two.   

**Pin to enforce:** OFS must never join labels using “current truth” unless the build explicitly declares that it is doing a “know-now” dataset. “No hidden now” is a platform law.  

#### 3) Replay basis: always explicit (offsets/watermarks), never “all history”

OFS rebuild **must declare a replay basis**:

* preferably as **offset ranges per partition**, or
* as **time windows anchored to offsets** via recorded checkpoints/watermarks. 

This is non-negotiable because watermarks are the shared “what was applied” truth, and they remain monotonic even under backfill.  

#### 4) Feature definition/versions used (the “feature contract input”)

J14 pins that the rebuild must record **feature definitions/versions used**. This means OFS must take a **versioned feature definition profile** (however you store it) as an explicit input into the build. 

*(We don’t need to pin where the feature registry lives right now; we just pin that OFS receives versioned definitions as inputs and records them.)* 

#### 5) (Production-shaped) run join surface as a by-ref input

In the deployment mapping, OFS reads the **SR `run_facts_view`** from object storage as a by-ref input in addition to EB/archive and LS. That’s consistent with the general “start from pinned refs, no scanning” posture.   

---

### What OFS must do with these inputs (behavioural pins of the join)

#### A) Deterministic reconstruction is the mission

OFS is not an “export job.” It is pinned as a **deterministic reconstruction** job (rebuild snapshots/datasets “as-of time T”).  

That implies the join must support:

* deterministic replay order (partition+offset basis),
* explicit as-of boundary for leakage safety,
* and recorded provenance sufficient to reproduce the build later.  

#### B) Record the basis (so reproducibility survives retention + backfill)

J14 explicitly requires OFS to record its basis:

* input event window (by offsets or offset-anchored time window),
* as-of boundary,
* feature definitions/versions used,
* parity anchors (e.g., snapshot hashes). 

Overlay pins reinforce:

* backfill is declared/auditable and never silently edits history,
* watermarks don’t lie (monotonic),
* archive is EB continuation,
* dataset builds must be reproducible by the recorded basis.   

#### C) Output is by-ref + pinned (DatasetManifest comes next, but J14 constrains it)

Even though DatasetManifest is *formally J15*, J14 forces OFS to produce outputs that can be referenced and reproduced:

* OFS writes materializations + DatasetManifests under `ofs/…` (object store), and optionally emits a small governance/control fact.   

---

### Failure modes / edge conditions OFS must handle (outer expectations)

These matter because they define what “production-ready” means for the join:

1. **Retention gap handling**
   If offsets needed for the replay basis are outside EB retention, OFS must transparently source from Archive **as if it were EB**, without semantic drift. 

2. **Backfill semantics**
   A backfill triggers a **new build** (new derived outputs + new manifest), not mutation of past builds; it must be declared/auditable.  

3. **Late labels**
   Late labels are normal; the join must make it easy to build:

* “what we knew then” datasets (as-of earlier boundary),
* and “what we know now” datasets (as-of later boundary),
  without mixing.  

---

## A5) Label Store → IG → `fp.bus.control.v1` (EMIT)  **(optional)**

### What this join exists to do (and what it must NOT become)

This is a **notification/control edge**, not a truth edge.

* It exists so downstream control-plane automation can react to label changes (schedule rebuilds, update dashboards, open workflows) without polling LS constantly.  
* It must **not** become “a second channel for label truth.” Learning still consumes labels **only** from LS timelines via as-of rules. 

### What crosses the join (minimal event semantics)

These are **low-volume control facts**, e.g.:

* `label_written`
* `label_corrected` (i.e., a superseding assertion appended)

Deployment notes explicitly allow “optional label events → `fp.bus.control.v1`.” 

**Pinned design choice for v0:** the event payload is **pointer-like**, not a copy of label history:

* subject key (event/entity/flow),
* label family,
* observed_time + effective_time (so consumers can decide whether they care),
* provenance (source),
* and a pointer/reference to the LS timeline entry (by-ref posture).  

### Why it routes through IG

Your platform posture is that the bus is an **admitted fact log** and IG is the **front door** (admit/duplicate/quarantine with receipts); even control-plane emissions are safer if they obey the same discipline.  

So the outer expectation is:

* LS behaves like a producer to IG for control events,
* IG dedupes/idempotently admits them,
* they land on `fp.bus.control.v1`.  

### Who consumes these control events (production-real uses)

Common consumers (all optional, all “hint-based”):

* **Run/Operate / schedulers**: trigger OFS builds / evaluation runs / governance tracking when enough labels changed. 
* **Obs/Gov**: label lag metrics, label volume, correction rates (operational signals). 
* **Case automation**: open/close tasks, notify investigators, etc. (deployment notes also allow Case to emit optional control events, so the pattern is consistent). 

### Reliability posture (so optional doesn’t create hidden coupling)

Because this edge is optional:

* If control events are delayed/dropped/duplicated, **platform correctness does not break** (truth is still in LS; OFS can still be run on schedule or by explicit invocation). 
* Consumers must treat these as **notifications**, not authoritative state.

---

Got you — here’s **B6–B8** expanded in **production-ready outer-network terms**, with **LS still opaque**. These three joins are the **learning → promotion → serving** chain that turns LS truth into changed RTDL behaviour (only via Registry).   

---

## B6) Offline Feature Shadow → Model Factory (J15)

### What this join *is for*

To make training **reproducible and auditable**, MF cannot accept “a dataset” as an informal blob. It must accept a **pinned definition** of *exactly what dataset was built*, including **history basis + label as-of boundary + feature versions**. That pinned unit is the **DatasetManifest**.  

### What crosses the join

**DatasetManifests + evidence**, where the manifest is the *primary* object and materializations are referenced by-ref. 

The manifest must pin (at minimum):

* **Dataset identity** (stable identifier / name + version posture)
* **Replay basis**: offset ranges/checkpoints + stream identities (not “last 90 days” handwaving)
* **Label as-of boundary** (observed/effective-time posture)
* **Join keys + entity scope** (how records join to labels/entities; what entity universe is in-scope)
* **Feature group versions used** (so serving/training drift is structurally prevented)
* **Digests/refs to materializations** (object-store refs + digests)
* **Provenance** (sources + transformations + pipeline version/config)  

### The non-negotiable “meaning” of DatasetManifest (pin this)

A DatasetManifest is **the unit of reproducibility**. If you can’t re-resolve the *exact* manifest later, you can’t claim the training run is reproducible. MF must treat manifests as **immutable inputs** (no “we’ll just rebuild the dataset again”).  

This is especially important because:

* **Archive extends EB** (same event identity) and replay beyond retention must still be deterministic. 
* **Replay basis must always be explicit** (offsets/checkpoints), because watermarks are the shared determinism hook and are monotonic even under backfill.  
* **Late labels are normal**, and “as-of” is how you prevent leakage and still allow “knew-then” vs “know-now” datasets. 

### MF’s consumption behaviour (outer expectation)

MF’s behaviour at this join must be **fail-closed** with respect to reproducibility inputs:

* If a manifest ref/digest can’t be resolved → **no training run** (don’t silently substitute “similar”).
* If the manifest is missing required pins (basis/as-of/join keys/feature versions) → **inadmissible**.
* If MF is given multiple manifests (train/eval/test), MF must record exactly which were used (by immutable ref/digest).  

*(This is the “No PASS → no read” posture applied to learning inputs: manifests aren’t “best effort”.)*  

---

## B7) Model Factory → Model/Policy Registry (J16)

### What this join *is for*

This join is where “learning outputs” become **deployable candidates**, but **Registry** is the only authority that can make a candidate **ACTIVE**. Model Factory publishes; Registry governs activation, rollback, and auditable lifecycle.  

### What crosses the join

A deployable **Bundle** *plus* promotion evidence. Importantly: the bundle is not just “a model file” — it is a package with:

* **Bundle identity**
* **Immutable artifact refs/digests** (model weights, rules, thresholds, metadata)
* **Training run provenance**: *which DatasetManifests were used* (refs/digests)
* **Evaluation evidence**
* **PASS/FAIL receipts** where required by governance posture
* **Compatibility metadata** (expected feature versions/inputs, required capabilities)  

Deployment shape pins where these live:

* MF writes training/eval evidence under `mf/...` and publishes bundles to the Registry (API), and Registry stores lifecycle truth in `registry` DB + bundle artifacts in `registry/bundles/...`. 

### Two-phase lifecycle is a hard pin (publish ≠ active)

**Authoritative v0 stance**: MF may *publish* candidate bundles, but activation is a **separate governed step** in Registry (approve/promote/rollback). This is required so “what changed?” is always answerable as “a registry lifecycle event changed ACTIVE.”  

### Compatibility is not optional paperwork (pin this)

Registry must refuse to treat a bundle as deployable unless it carries compatibility metadata (and evidence) sufficient for DF to resolve safely later. Promotion without compatibility metadata is **invalid**, not “discouraged.”  

---

## B8) Registry → Decision Fabric (ACTIVE resolution)

*(This is the serving closure: learning can only influence production through this edge.)* 

### What this join *is for*

DF needs a deterministic answer to: **“what should I use for this decision right now?”** Registry returns an **ActiveBundleRef** (one bundle per scope by rule), never “latest.” 

### What crosses the join

An **ActiveBundleRef** that includes:

* bundle id + immutable artifact refs/digests
* compatibility metadata (feature group/version deps, required capabilities, input contract posture)  

### Determinism + compatibility-aware resolution (two hard pins)

1. **Deterministic resolution (no “latest”)**
   For a given resolution scope, Registry returns **exactly one** active bundle by rule. 

2. **ACTIVE is necessary, not sufficient**
   Registry resolution must be **compatibility-aware**. If the active bundle is incompatible with:

* the currently available feature definitions/versions (what OFP can serve), or
* the current degrade mask (capabilities disabled),
  then DF must **fail closed or route to an explicitly defined safe fallback**, and it must record why.  

### DF provenance obligations (so audit/replay works)

DF must record in decision provenance:

* the resolved bundle ref (id + digest posture),
* feature group versions actually used (from OFP),
* degrade posture in force.  

This is what makes “what changed?” answerable and makes decisions replayable after rollouts.  

---

## The key LS-thread that runs through B6–B8 (why these are in the LS network at all)

Even though LS is not directly in B6–B8, it **controls the truth boundary** that B6 must pin:

* DatasetManifests must pin the **label as-of boundary** (which is “how LS truth was read”) so training and evaluation are leakage-safe and reproducible. 
* MF must cite those manifests in the bundle’s lineage, and Registry must carry that evidence, so deployments are auditable and explainable.  

---

Yep — **C9–C12** are the four **production paths** that “route through” LS (directly or indirectly). I’ll expand them as **end-to-end narratives**, keeping **LS opaque** (we pin only what the rest of the platform can assume).

---

## C9 / P1 — Evidence → investigation → truth

**EB / DF / AL / DLA evidence refs → Case Workbench → (J13) LS**

### Why this path exists

To enforce the platform law: **RTDL emits evidence, not truth; truth labels exist only once written to LS**. Case is the “human truth plane” that consumes evidence by-ref and produces label assertions.  

### End-to-end flow (outer behaviour)

1. **Admitted facts accumulate on EB** (business traffic + decision/action events as canonical envelopes). EB is the replayable fact spine; it doesn’t own “meaning,” just position/ordering semantics.  
2. **DF makes a decision** and emits its **DecisionResponse** (decision + provenance + action intents). This is **evidence** of what the system decided and why. 
3. **AL executes ActionIntents effectively-once** and emits immutable **ActionOutcome** history. Outcomes are **evidence** of what actually happened in the world. 
4. **DLA ingests the minimum immutable audit facts** into an append-only “flight recorder.” If provenance is incomplete, it quarantines rather than writing a half-truth.  
5. **Case Workbench opens/updates a case** using **evidence refs**: DLA record pointers, EB coordinates, and other by-ref artifacts. Case maintains an **append-only case timeline** (“what happened / what was done / who did it / when”).  
6. **Investigator produces a LabelAssertion** and writes it to LS via **J13**. **Only now** does the label become ground truth for the platform.

### The key invariants (drift-killers) in P1

* **Evidence ≠ truth**: DF/AL/DLA outputs are never treated as labels unless a label policy explicitly says so. 
* **By-ref bridge**: Case/labels store **IDs + refs** (audit record IDs, EB coordinates, artifact refs), not copied payloads. 
* **Manual interventions** must go through **the same Actions Layer pathway** (ActionIntent → AL → Outcome) so everything stays dedupe-safe and auditable.
* **Append-only everywhere it matters**: DLA is append-only with supersedes chains; LS is append-only label timelines with corrections as new assertions.

### Failure modes (production-real) and what must happen

* **Incomplete provenance**: DLA quarantines the audit record (don’t let Case/labels build on half-truth). 
* **Duplicate evidence / retries**: AL and DLA are idempotent by design, so Case sees stable, repeatable pointers and outcomes.
* **Correction**: investigator changes mind → new label assertion; history remains; interpretation uses supersedes chain (no destructive edits).

---

## C10 / P2 — Truth → rebuild → train → deploy

**(J14) LS+EB/Archive → OFS → (J15) MF → (J16) Registry → DF**

### Why this path exists

To turn **human truth** into **machine-learnable truth** without leakage, and to make training/deployment **reproducible and auditable**.

### End-to-end flow (outer behaviour)

1. **OFS reads the factual history** from EB (within retention) and Archive (beyond retention) — but must treat them as **the same logical fact stream** with the same event identity + ordering basis per partition.
2. **OFS reads labels from LS with explicit “as-of” semantics** (effective vs observed time). This is the leakage-safety rule: “what we knew then” vs “what we know now.”
3. **OFS rebuild is deterministic** and must record its basis:

   * replay basis (offset ranges or offset-anchored time window),
   * label as-of boundary,
   * feature definitions/versions used,
   * parity anchors (e.g., snapshot hashes).
4. **OFS produces DatasetManifests** — the pinned bridge artifact. It does not “hand over a dataframe”; it hands over a manifest that pins identity, basis, as-of, join keys/entity scope, feature versions, and refs/digests to materializations.
5. **Model Factory consumes DatasetManifests as immutable inputs**. Training runs are only reproducible if the exact manifests can be re-resolved later.
6. **MF publishes a deployable Bundle + promotion evidence to Registry** (lineage to manifests, eval evidence, PASS/FAIL receipts where required, compatibility metadata).
7. **Registry is the only authority that decides ACTIVE**, with auditable lifecycle actions (promote/rollback/retire).
8. **DF resolves the active bundle deterministically** (no “latest”), enforces compatibility (feature versions + degrade posture), and records the resolved bundle ref in decision provenance.

### The key invariants in P2

* **Leakage safety is structural**: label joins are *as-of by rule* (observed_time discipline), not “best effort.” 
* **Replay basis is always explicit**: “last 90 days” is invalid unless pinned to offsets/checkpoints.
* **Feature definitions are versioned and singular** across serving + offline + bundles (anti-drift).
* **DatasetManifest is the unit of reproducibility**, and becomes evidence for promotion.
* **Promotion is evidence-based and compatibility-aware**; DF never runs an incompatible ACTIVE bundle silently.

### Failure modes and what must happen

* **Retention expiry**: OFS seamlessly sources older history from Archive “as if it were EB,” recording the basis.
* **Backfill**: produces new derived artifacts/manifests; never silently overwrites primary truth. Must be declared and auditable.
* **Late labels**: you rebuild a new dataset with a later as-of boundary; you can reproduce “knew-then” vs “know-now” datasets.

---

## C11 / P3 — Late truth path

**external adjudication → (J13) LS → (J14) OFS → MF → Registry**

### Why this path exists

Because **delayed truth is normal** (disputes/chargebacks/etc). The platform must ingest late truth without rewriting history or corrupting evaluation.

### End-to-end flow

1. An external adjudication system produces an outcome signal.
2. That outcome becomes a **LabelAssertion** written to LS (either directly via an authorized writer or mediated through Case workflow). LS records:

   * **effective_time** (when the truth applied),
   * **observed_time** (when the platform learned it).
3. OFS can now build:

   * **historical evaluation datasets** (“what we knew then”: observed_time as-of earlier boundary), and
   * **improved training datasets** (“what we know now”: later boundary),
     without mixing them.
4. MF trains/evaluates, publishes bundles with lineage, Registry governs activation, DF changes behaviour only via ACTIVE resolution.

### The key invariants in P3

* **No time travel**: late truth doesn’t rewrite past labels; it appends new assertions and changes interpretation under as-of rules.
* **Truth is still LS-only for learning**: learning doesn’t infer labels from “chargeback events”; it consumes LS timelines. 
* **Backfill is declared**: if late truth triggers rebuilds, those rebuilds are explicit operations that produce new manifests/artifacts, not silent mutation.

---

## C12 / P4 — Optional automation path

**LS emits control fact → scheduler/Run-Operate triggers OFS/MF jobs → Registry updates → DF shifts**

### Why this path exists

To reduce human/manual coordination: when label truth changes “enough,” the system can **schedule rebuilds/training** automatically. But it must remain **optional** (correctness must not depend on it).

### End-to-end flow

1. LS optionally emits a **low-volume control fact** (e.g., `label_written`, `label_corrected`) to `fp.bus.control.v1`.
2. A scheduler / Run-Operate workflow consumes the control fact and decides whether to:

   * trigger an OFS rebuild (new DatasetManifest),
   * trigger an MF run (new Bundle candidate),
   * or do nothing (thresholding / batching).
3. If jobs run, they must obey the History/Backfill overlay:

   * explicit replay basis,
   * explicit as-of boundary,
   * declared/auditable backfill where relevant.
4. Registry lifecycle events (publish/promote/rollback) remain the only mechanism for DF behaviour change.

### The key invariants in P4

* **Control facts are notifications, not truth**. Truth remains in LS timelines and in Registry lifecycle state.
* **Idempotency + auditability**: scheduled jobs can re-run; outputs are new manifests/bundles; no silent overwrite of primary truths (EB, LS, Registry history).

---

### If you want the best “next thing” to pin (to make all C9–C12 airtight)

Pin the **single shared “as-of boundary handshake”** used end-to-end:

* Case/LS writes preserve observed/effective.
* OFS declares a specific **as-of boundary** and records it in the DatasetManifest.
* MF/Registry carry that manifest lineage into the bundle evidence.

That one pin is what prevents 90% of leakage/drift across the whole LS → learning loop.

---

On it. **D13–D16** are the **four LS-including production loops** (L1–L4). I’ll expand each as an end-to-end **cycle** with (a) what it’s *for*, (b) the step-by-step “lap”, and (c) the **drift-killer invariants** that must hold in a production-ready platform.

---

## D13 — L1 Core improvement loop

**(decisions → evidence → labels → training → new bundle → new decisions)**

### What this loop is for

This is the platform’s **closed learning feedback circuit**: it converts *production reality* (admitted events + decision-time provenance) into *replayable training reality*, then returns the result to production **only via Registry**.  

### One full “lap” of the loop (outer behaviour)

1. **Facts + decisions are produced and preserved as evidence**

   * Admitted business traffic and system events land on **EB** (via IG). EB is the fact spine (append+replay), not the meaning engine. 
   * **DF** emits decisions + action intents + provenance; **AL** executes intents effectively-once and emits immutable outcomes; **DLA** writes the canonical audit record (append-only; quarantine if provenance is incomplete).  

2. **Case consumes evidence by-ref and emits label truth**

   * Case Workbench pulls **evidence refs** (audit record IDs / EB coordinates / artifact refs) and maintains an immutable investigation timeline. 
   * Investigators (and authorized adjudication sources) write **LabelAssertions** into **LS**, and **labels become truth only when written to LS** (append-only timelines; corrections are new assertions).  

3. **Offline Shadow reconstructs training-ready datasets deterministically**

   * **OFS** reads event history from **EB** (within retention) and **Archive** (beyond retention) but treats them as **the same logical fact stream**.  
   * OFS reads labels from LS using explicit **as-of** rules (effective vs observed time) to prevent leakage.  
   * OFS records the rebuild basis (offset/window basis, as-of boundary, feature versions used, parity anchors) and emits **DatasetManifests** (pinned dataset definitions), not “a dataframe”.  

4. **Model Factory trains/evaluates reproducibly**

   * **MF** treats DatasetManifests as immutable inputs; training runs are reproducible only if the exact manifests can be re-resolved.  
   * MF produces bundles + eval evidence + PASS/FAIL posture (where governance requires it). 

5. **Registry governs promotion and is the only deployable truth**

   * MF publishes candidate bundles to **Registry**; Registry is the only authority that decides **ACTIVE**, with auditable promotion/rollback.  
   * Compatibility metadata is required (promotion without it is invalid).  

6. **DF changes behaviour only by deterministic ACTIVE resolution**

   * DF asks Registry “what should I use right now?” and gets a deterministic **ActiveBundleRef** (no “latest”), enforces compatibility (feature versions + degrade mask), and records the resolved bundle in provenance.  
   * New decisions now reflect the new ACTIVE bundle → producing new evidence → feeding new cases/labels → continuing the loop. 

### Drift-killer invariants for L1 (must hold)

* **Truth ownership is unambiguous**: LS owns label truth; DLA owns audit truth; Registry owns deployable truth; EB owns stream position truth. 
* **Learning uses replayable facts + provenance, never live caches** (OFS is the contract bridge). 
* **Leakage safety is structural**: labels are read “as-of” (observed-time discipline) and the basis is pinned in DatasetManifests.  
* **No silent rollouts**: behaviour change is an auditable Registry lifecycle event; DF resolves deterministically.  

---

## D14 — L2 Human correction loop

**(Case ↔ LS: append-only corrections over time)**

### What this loop is for

To let humans revise truth **without rewriting history**, while preserving the ability to reproduce:

* “what we knew then” vs
* “what we know now”
  …which is foundational for fair evaluation and leakage-safe training.  

### One full “lap”

1. **Case reads LS for the subject**

   * Case Workbench reads the label timeline (and potentially a resolved view) to see current truth and prior assertions. (Deployment explicitly expects Case to read LS.)  

2. **Investigator appends a new assertion**

   * Correction is a **new LabelAssertion** appended to LS, with provenance + effective_time + observed_time; no destructive edits.  

3. **Case immediately sees the new truth evolution**

   * Case reads back the timeline (and/or resolved view) and continues workflow; the record remains an immutable evolution. 

4. **Learning can choose the correct semantic view**

   * OFS/MF can build datasets “as-of boundary T” to exclude future knowledge, or “as-of now” for retrospective analysis—**explicitly**, never implicitly.  

### Drift-killer invariants for L2

* **Corrections are truth evolution, not mutation** (append-only timeline). 
* **Dual-time is preserved** (effective vs observed), enabling “late truth” without time travel. 
* **Case produces assertions; LS defines learning semantics** (Case can’t dictate training semantics via ad-hoc exports). 

---

## D15 — L3 Manual action loop

**(Case → AL (ActionIntent) → DLA evidence → Case → LS)**

### What this loop is for

To ensure human-driven side effects (block/release/notify/etc.) are:

* **executed only by Actions Layer**,
* **idempotent/effectively-once**,
* and fully auditable—exactly like automated actions.  

### One full “lap”

1. **Case decides a manual intervention is needed**

   * Case Workbench is a human control surface; it may request manual actions but must not execute them directly.  

2. **Case submits a proper ActionIntent**

   * The manual intervention is expressed as an **ActionIntent** (same pathway as automated), carrying:

     * actor principal / origin (manual),
     * deterministic idempotency key,
     * and join context (ContextPins + target IDs).  

3. **AL authorizes + executes (or denies)**

   * AL enforces allowlists and executes effectively-once scoped by `(ContextPins, idempotency_key)`.
   * Duplicate intents never re-execute; they re-emit the same canonical outcome.  

4. **AL emits immutable ActionOutcome evidence**

   * Outcomes are immutable and replayable as evidence.  

5. **DLA records the evidence as the flight recorder**

   * DLA ingests decision + action provenance and keeps an append-only record; corrections via supersedes chain; quarantine if incomplete provenance.  

6. **Case consumes that evidence and may emit label truth**

   * Case updates the investigation timeline using by-ref pointers (audit record refs, EB coords).
   * If the investigation resolves truth, Case writes a label assertion to LS (append-only).  

### Drift-killer invariants for L3

* **Only AL executes** (manual action is not a bypass). 
* **Idempotency is law** for manual actions too. 
* **Audit completeness**: DLA is append-only, quarantines half-truth. 
* **Truth still lives in LS**: outcomes are evidence; labels become truth only when asserted into LS. 

---

## D16 — L4 Optional ops automation loop

**(LS control events → jobs/backfills → new manifests/bundles → DF → new evidence → new labels)**

### What this loop is for

To reduce manual coordination and keep the platform “self-tending”:

* label changes can **trigger** rebuilds/training/eval/backfills,
* but correctness never depends on this loop (it is **optional automation**).  

### One full “lap”

1. **LS optionally emits a control fact**

   * LS may emit low-volume label notifications to `fp.bus.control.v1` (e.g., label_written/label_corrected).  
   * This is a *notification*, not an alternate truth channel (truth remains in LS timelines). 

2. **Scheduler / Run-Operate decides what to run**

   * Consumes control facts and decides whether to schedule:

     * OFS rebuild,
     * MF train/eval,
     * or a backfill/replay job.  

3. **Backfill/rebuilds are explicit and auditable**

   * Backfill is never silent; it’s declared (who/why/scope/basis) and produces new versioned outputs—not stealth overwrites. 

4. **OFS emits new DatasetManifests with pinned basis**

   * Archive is treated as EB continuation; watermarks don’t lie; manifests pin replay basis and as-of boundaries.  

5. **MF publishes bundles; Registry governs activation**

   * MF publishes bundle + evidence; Registry lifecycle governs ACTIVE, emitting governance facts.  

6. **DF resolves ACTIVE deterministically and produces new evidence**

   * DF behaviour changes only via Registry resolution; new evidence flows to DLA → Case → LS, potentially triggering the next automation cycle.  

### Drift-killer invariants for L4

* **Optional means non-blocking**: if control facts are delayed/dropped/duplicated, nothing breaks (truth is still in LS; jobs can still be scheduled explicitly). 
* **History discipline**: archive is EB continuation; backfill declared; watermarks monotonic; manifests pin basis. 
* **Deployable truth discipline**: only Registry lifecycle changes ACTIVE; DF never loads “latest”.  

---

Yes — the **environment ladder** changes how we should *interpret and “harden”* every LS join/path/loop, without changing their meaning.

The core rule to keep in view is the pinned ladder itself:

> **Local, dev, prod run the same platform graph + the same rails/join semantics; only the operational envelope differs (scale, retention/archive, security strictness, reliability, observability). Promotion is profile/policy selection, not semantic forks.**  

Below is what I’d say about your LS joins/paths/loops under that rule.

---

## What must stay identical across environments for LS joins/paths/loops

### 1) The *meaning* of the key words cannot change

Across local/dev/prod, these must mean the same thing (just smaller/cheaper locally):

* **LABEL truth** = only what’s in LS timelines (append-only; corrections = new assertions).  
* **LABEL AS-OF** = explicit, leakage-safe as-of semantics (no hidden “now”).  
* **ACTIVE** bundle resolution = deterministic (no “latest”).  
* **BACKFILL** = explicit, scoped, auditable regeneration of *derived* artifacts only; never “truth mutation” of LS/EB/Registry/SR ledgers.  

### 2) Rails/join semantics must be identical

Your LS loop touches the most important rails, and they must not drift by environment:

* **By-ref** pointers (no “scan latest”). 
* **No PASS → no read** as a platform rule (not just engine).  
* **At-least-once reality** + **idempotency** at boundaries.  
* **Watermarks/offsets** are the universal “what was applied” tokens. 

### 3) Same deployment-unit *roles* (even if you collapse them locally)

LS loop is “always-on services + on-demand jobs.” Local can run them in one process, but the roles must stay:

* **Label Store service** always-on truth timeline.
* **Offline Shadow job** scheduled/on-demand.
* **Model Factory job** scheduled/on-demand.
* **Registry service** always-on, governs activation.  

---

## What is allowed to differ — and how it impacts your LS joins/paths/loops

### A) Retention + archive (operational knob; semantics must not change)

* Local: short EB retention; archive may be disabled.
* Dev: medium retention; archive likely enabled for realism.
* Prod: long retention + archive continuity. 

**Implication for LS paths/loops (especially J14, P2, L1):**

* OFS must be written so **“EB+Archive” is one logical stream** when archive exists, but it must also operate when archive is absent (local) *without changing the definition of replay basis*. 
* Your pinned backfill rule becomes critical: OFS rebuilds and MF training should always be explainable by **pinned basis + as-of + manifests**, regardless of retention length.  

### B) Security strictness (mechanism exists everywhere; strictness tightens with the ladder)

* Local: permissive allowlists/dev creds, but **same trust boundaries**. 
* Dev: “real enough” auth to catch issues (unauthorized producers, registry privileges, quarantine access). 
* Prod: strong authn/authz + strict change control everywhere it matters (including label writes). 

**Implication for LS joins:**

* **J13 (Case→LS)** and **external adjudication→LS** must exist in all envs, but *who is allowed to write* is policy-profile driven (local permissive; dev catches wrong writers; prod strict). 
* **A5 (LS control emits)**, if enabled, still must route through the same front-door posture (IG/bus discipline), but may be disabled locally to reduce noise—because it’s explicitly optional and must not be correctness-critical. 

### C) Observability depth (local still must be “real” enough to validate the rails)

Local may be “inspect-by-hand,” but it still must preserve:

* correlation keys everywhere,
* lag/watermark visibility,
* structured boundary decisions as facts.  

**Implication for LS loop:**

* In dev/prod you need dashboards/alerts for **label lag**, **correction rate**, **OFS build basis**, **manifest lineage**, **bundle activation events** — but local still needs enough to prove the loop is behaving correctly (not silently mixing as-of).  

### D) Promotion discipline (this matters a lot for B6–B8 and L1/L4)

Promotion is pinned as **three lanes**:

1. code artifacts (build once/run anywhere),
2. policy/profile revisions (versioned, auditable),
3. model/policy bundles (MF publishes, Registry activates).  

**Implication for LS learning chain (B6–B8):**

* Local may “auto-approve,” dev is where you validate compatibility + schema evolution + degrade interactions, prod requires explicit governed activation — but the *shape* (proposed→approved→active, with governance facts) should remain consistent.  
* MF→Registry and Registry→DF semantics must not change: DF always resolves deterministic ACTIVE and records bundle refs in provenance.  

---

## Practical “environment ladder checks” to apply to every LS join/path/loop

When you expand any join/path/loop, ask:

1. **Is this a semantics change or an envelope change?**
   If semantics: **banned** by the ladder. 

2. **If we disable something locally (like archive or LS control emits), does correctness still hold?**
   If no: it wasn’t optional — we accidentally created hidden coupling.  

3. **Can we reproduce the same story in dev/prod as in local?**
   Meaning: pinned refs + manifests + policy revs + governance facts, not “it worked because we were on a laptop.”  

---

Yep — here are the **environment profile knobs** and the **deployment-direction info** I want you to have *before* we “enter” LS, while it’s still opaque.

Everything below respects your ladder pin: **same graph + same rails/join semantics across local/dev/prod; only the operational envelope changes**.  

---

## 1) First, the LS invariants that must not drift by environment

These are “profile-immune” meanings:

* **LS is label truth** (append-only timelines), and labels are consumed for learning via **as-of semantics**.  
* **Backfill cannot mutate primary truths** (explicitly includes *label store timelines*). Local/dev/prod may rebuild *derived* things, but not rewrite label history.  
* **Same trust-boundary posture** everywhere: “local must still obey the rails,” even if permissive. 

---

## 2) Deployment-unit reality for LS (so profiles have something to “turn”)

While opaque, LS still has a pinned runtime shape:

* **Deployment unit type:** *always-on service* (control-plane truth) 
* **Primary durable store:** `label_store` authoritative DB (append-only assertions)  
* **Optional emission:** low-volume label notifications → `fp.bus.control.v1`  

That’s enough to define “what gets deployed” even before we design internals. 

---

## 3) The environment profile knobs for LS (v0 set)

### A) Wiring knobs (non-semantic)

These can vary freely across environments (they must not change meaning): 

* DB endpoint/DSN, pool sizes, timeouts
* Service ports / hostnames
* Topic endpoints if control emissions are enabled (broker URLs)
* Resource limits (CPU/mem), concurrency caps

### B) Policy knobs (semantic “strictness” but not semantic “meaning”)

These must be **versioned artifacts** with a revision identity, and LS should be able to cite the **policy_rev** in logs/receipts/provenance.  
Core LS policy knobs:

* **Write authority matrix:** who may write which label families (Case vs adjudication feed, etc.) 
* **Required fields discipline:** (e.g., observed/effective time always required; ContextPins required when joinable) 
* **Conflict posture:** whether resolved views ever return `CONFLICT` vs deterministic precedence (still “append-only always”) 
* **Privacy posture:** forbid raw sensitive payload storage; prefer by-ref evidence pointers 

### C) Operational envelope knobs (allowed to differ per ladder)

These are the knobs that *should* differ across local/dev/prod: 

* **Security strictness:** authn/authz enforcement level for reads/writes (mechanism exists everywhere; strictness increases) 
* **Reliability posture:** backups, replication/HA, recovery drills (prod hardened) 
* **Observability depth:** local “inspect-by-hand” vs prod SLOs/alerts (but OTLP semantics should exist locally too)  
* **Scale:** expected write/read volume, burst limits, rate limiting

**Important nuance:** unlike EB retention, **label timelines are primary truth**, so you don’t treat “label retention” as a casual knob. In local you keep smaller worlds, not shorter truth.  

---

## 4) LS-adjacent profile knobs you should still carry (because LS loops depend on them)

Even though these aren’t “inside LS,” they’re the knobs that determine whether the LS→learning loops behave the same across environments:

* **EB retention length** (env knob) + **archive enabled** (env knob) — semantics of replay/offsets/watermarks must not change. 
* **Archive addressing rules:** by-ref + pinned basis (no vague searching). 
* **Backfill controls:** declared, scoped, auditable; produces new derived artifacts; never mutates truths (including LS).  
* **DatasetManifest “bridge meaning”:** must pin replay basis + label as-of boundary + feature versions so MF/Registry evidence is reproducible even after retention/backfill changes.  

---

## 5) “What I want you to have in mind” before we enter LS internals

This is the practical deployment direction:

1. **Production-shaped local stack is worth it** (even if small): Kafka-ish bus + S3-ish object store + SQL DBs + OTLP pipeline, so LS/OFS/MF/Registry behaviour is real locally.  
2. **Promotion is profile selection, not code forks**: same binaries; different environment profile + stronger policy configs in dev/prod.  
3. **Integration gate you should insist on early:** run one “golden loop” end-to-end locally/CI that includes *labels + offline shadow + registry resolution* (so LS semantics are validated in the full loop).  
4. **Non-negotiable persistence plan:** `label_store` DB is primary truth → treat backups/restore as real even in dev, because you can’t “backfill labels.”  

---

## A simple way to think about the LS “profile” (one line)

**LS profile = wiring (where) + policy_rev (what rules) + envelope (how strict / how durable / how observable)** — with semantics pinned and identical across environments.  

When you’re ready to “enter LS,” the first internal thing we should illuminate is **how LS enforces policy_rev + authority matrix + idempotent append-only writes**, because that’s where deployment profiles actually bite without changing meaning. 

---

## USER: PAUSE FOR REFLECTION

([Past chat][1])([Past chat][1])([Past chat][1])([Past chat][1])([Past chat][1])

Yep — this is the right “checkpoint” before we crack LS open.

Below is the **outer-network snapshot** we’ve established for **Label Store (LS)**, with the **platform pins** called out explicitly so we have a drift-proof frame as we move inward. (LS remains opaque here; this is *only* its role/edges/paths/loops.)

---

## 1) LS outer purpose and authority boundaries

**LS is the platform’s label truth authority**:

* Labels are **append-only timelines** (not update-in-place).
* A label becomes “truth” **only once stored in LS**.
* Every assertion carries **effective_time** + **observed_time**, enabling leakage-safe **as-of** reads and late/corrected truth handling.

**LS is not part of the hot path**:

* RTDL emits **evidence** (decisions/intents/outcomes), not truth labels.
* LS does **not** feed DF/OFP as an online dependency. (Truth loop, not decision loop.)

**Deployment truth**: LS is an **always-on control-plane service** with an authoritative **`label_store` DB**.

---

## 2) LS adjacency list (direct joins)

### Required joins

**J13 — Case Workbench → LS (WRITE)**
What crosses: **LabelAssertions** as append-only timeline entries:

* subject (event/entity/flow), value (+ optional confidence), provenance, effective_time, observed_time
* corrections are new assertions that supersede in interpretation; history remains

**J14 — (LS + EB/Archive) → Offline Shadow (READ)**
What crosses: inputs for **deterministic rebuild “as-of time T”**:

* EB within retention + Archive beyond retention treated as **same logical stream** (same identity + ordering basis per partition)
* labels read from LS using explicit **as-of** rules (effective vs observed)
* rebuild must record basis: offsets/time window tied to offsets, as-of boundary, feature versions, parity anchors

**J15 — Offline Shadow → Model Factory**
What crosses: **DatasetManifests** (pinned dataset definitions) + evidence.
Manifest pins replay basis, label as-of boundary, join keys/entity scope, feature versions, refs/digests, provenance.

**J16 — Model Factory → Registry**
What crosses: deployable **Bundles + promotion evidence** (manifest lineage, eval evidence, PASS/FAIL where required, compatibility metadata).
Registry is the only authority for **ACTIVE**; promotion/rollback is auditable.

### Production-required implied join

**LS → Case Workbench (READ)**
Case needs label timelines / as-of views for investigation workflow (deployment wiring expects Case reads LS).

### Optional join (allowed but non-essential)

**LS → IG → fp.bus.control.v1 (EMIT)**
Low-volume “label_written / label_corrected” notifications for schedulers/ops. Must remain **non-correctness-critical**.

---

## 3) Production paths that include LS (multi-hop)

**P1 (Evidence → investigation → truth)**
EB/DF/AL evidence → DLA audit record refs → Case → **J13** LS
(“evidence becomes truth only via LS write”).

**P2 (Truth → rebuild → train → deploy)**
**J14** LS(as-of)+EB/Archive(replay) → OFS → **J15** MF → **J16** Registry → DF ACTIVE resolution
(DatasetManifest is the pinned bridge).

**P3 (Late truth path)**
External adjudication → **J13** LS → **J14** OFS → MF → Registry → DF
(why dual-time + as-of is mandatory).

**P4 (Optional ops automation path)**
LS control notify → scheduler/run-operate triggers OFS/MF jobs → Registry lifecycle → DF behaviour changes → new evidence → new labels
(allowed, but must be optional).

---

## 4) Loops/cycles that include LS

**L1 Core improvement loop**
DF/AL evidence → DLA → Case → LS → OFS → MF → Registry → DF

**L2 Human correction loop**
Case ↔ LS (append-only corrections; as-of supports “knew then” vs “know now”).

**L3 Manual action loop**
Case → AL (manual action intent) → evidence → Case → LS.

**L4 Optional ops loop**
LS notify → jobs/backfills → new manifests/bundles → DF → new evidence → new labels.

---

## 5) Explicit non-joins (things we must *not* accidentally create)

These are drift traps:

* **LS → hot path decisioning** (no online feature/decision dependency).
* **RTDL writes labels directly** (DF/AL/DLA produce evidence; labels become truth only in LS).
* **Truth mutation by backfill**: label timelines are primary truth and cannot be rewritten by backfill; backfill only regenerates derived artifacts.

---

## 6) Environment ladder implications (so outer network doesn’t silently fork)

Across local/dev/prod:

* **Same graph + rails + meanings** (“LABEL AS-OF”, “BACKFILL”, “ACTIVE”, etc.).
  Allowed to vary: scale, retention/archive, security strictness, reliability, observability depth — **without changing semantics**.
  Also pinned: **deployment unit roles don’t change** (LS stays an always-on truth service; OFS/MF remain jobs; Registry remains always-on).

---

## 7) The drift checklist as we enter LS internals

When we start illuminating the inside, we must preserve these outer truths:

1. **Append-only label timelines + supersedes semantics**
2. **Dual-time + explicit as-of read discipline**
3. **By-ref evidence pointers** (no payload duplication as “truth”)
4. **DatasetManifest is the reproducibility bridge** (pins basis/as-of/join keys/features)
5. **Backfill cannot mutate LS truth**
6. **Same semantics across environments** (only envelope changes)

---

## What’s still intentionally “un-pinned” (safe to decide inside LS next)

These are the knobs we *can* choose when we enter the vertex, without violating the outer network:

* the precise **subject/target model** (how event/entity/flow targets are keyed + scoped),
* the **conflict policy** for resolved views (e.g., return CONFLICT vs precedence),
* the **idempotency recipe** for writes,
* the **authority policy model** (who can assert which label families; policy_rev handling),
* the exact **read surfaces** and export shapes (while preserving as-of semantics).

All of those can be decided “inside the box” — but only if they keep the outer graph unchanged.

If you’re happy with this checkpoint, the clean transition into LS internals is: **start by pinning the target/subject model + join keys**, because that’s the single biggest place internal choices can accidentally break J13/J14/J15.

---

Yes — one level down, LS naturally decomposes into a small set of **internal subnetworks** (modules) that mirror the *outer* pins (J13 write semantics, J14 as-of reads, append-only truth, idempotency, and the learning reproducibility bridge).   

Below is the **authoritative LS Level-1 internal network** (each box is still opaque; we’re only naming the subnetworks and their edges).

### LS internal subnetworks (Level 1)

```
            writers                                   readers
   (Case Workbench, feeds)                     (Case UI, OFS/MF bulk)

        ┌──────────────┐
        │  S1: LS Edge  │  (public surfaces: write/read/bulk)
        └──────┬───────┘
               |
               v
   ┌──────────────────────────┐
   │ S2: Governance & Policy   │  (authority + shape validation)
   └──────────┬───────────────┘
              |
              v
   ┌──────────────────────────┐
   │ S3: Target Canonicalizer  │  (join keys + ContextPins scoping)
   └──────────┬───────────────┘
              |
              v
   ┌──────────────────────────┐
   │ S4: Write Determinism     │  (idempotency + duplicate control)
   └──────────┬───────────────┘
              |
              v
   ┌──────────────────────────┐
   │ S5: Timeline Ledger Core  │  (append-only label events = truth)
   └──────┬─────────┬─────────┘
          |         |
          |         v
          |   ┌──────────────────────┐
          |   │ S6: Resolver & Views  │  (as-of/current/conflict views)
          |   └─────────┬────────────┘
          |             |
          |             v
          |   ┌──────────────────────┐
          |   │ S7: Export & Slices   │  (bulk label slices for OFS/MF)
          |   └──────────────────────┘
          |
          v
   (optional) ┌──────────────────────┐
              │ S8: Notifications     │  (label_written/corrected hints)
              └─────────┬────────────┘
                        v
                      IG → fp.bus.control.v1
```

---

## S1) LS Edge Subnetwork (Public Surfaces)

**Why it exists:** to make the outer joins explicit and non-drifting:

* J13 “write label assertion”
* J14 “read as-of labels / bulk joins for OFS”
* Case read surfaces (timeline/current/as-of) 

**What it does (conceptually):**

* Exposes **Write**, **Read**, and **Bulk/Export** entrypoints (API/CLI doesn’t matter yet).
* Normalizes request envelopes and routes internally.
* Returns stable outcomes (e.g., ACCEPTED/DUPLICATE/REJECTED) without revealing internals. 

---

## S2) Governance & Policy Subnetwork

**Why it exists:** to enforce the platform’s hardest boundary: **truth vs evidence** and “who may assert what.”  

**What it does (conceptually):**

* Checks **writer authority** (Case vs adjudication feed vs anything else).
* Validates that a “label assertion” has the pinned minimum fields (subject/value/provenance/effective_time/observed_time). 
* Applies a **policy_rev** posture (same semantics everywhere; strictness can tighten by env profile later). 

---

## S3) Target Canonicalizer Subnetwork

**Why it exists:** joinability is your biggest drift risk. This subnetwork turns “whatever the caller calls the subject” into a canonical target key.  

**What it does (conceptually):**

* Canonicalizes **subject types** (event/entity/flow) and their **join keys**.
* Enforces **ContextPins** when the label claims run/world joinability (rail R1). 
* Produces the internal “LabelTargetKey” used everywhere downstream.

---

## S4) Write Determinism Subnetwork

**Why it exists:** the platform is at-least-once; LS must be duplicate-safe. 

**What it does (conceptually):**

* Computes/verifies the **idempotency scope** for label assertions.
* Ensures retries/duplicates don’t create duplicate timeline entries.
* Emits a stable write outcome (ACCEPTED/DUPLICATE/REJECTED). 

---

## S5) Timeline Ledger Core Subnetwork

**Why it exists:** this is the **only truth nucleus** inside LS: the append-only label event timeline.  

**What it does (conceptually):**

* Appends label events immutably (corrections are new events; no edits).
* Maintains supersedes links (if used) and the canonical ordering needed for interpretation.
* This is what lives in the authoritative `label_store` DB posture.  

**Design pin:** everything else may be rebuildable; **this ledger is not.** 

---

## S6) Resolver & Views Subnetwork

**Why it exists:** the platform explicitly pins “as-of correctness” and “late labels are normal.”  

**What it does (conceptually):**

* Provides deterministic interpretations:

  * `timeline(target)`
  * `label_as_of(target, T)` (observed_time drives leakage-safe reads)
  * `current_label(target)` (explicitly “as-of now”)  
* Detects/represents conflicts for resolved views (we’ll pin the exact conflict posture later).

---

## S7) Export & Slices Subnetwork

**Why it exists:** Offline Shadow / learning needs **bulk label slices** to join with replay history, under a declared as-of boundary.  

**What it does (conceptually):**

* Efficient bulk reads (“give me labels for these targets / this scope as-of T”).
* Produces exportable slices (still by-ref posture; not “a training pipeline”).
* Aligns with the DatasetManifest bridge requirement (manifest pins label as-of boundary + join keys). 

---

## S8) Notifications Subnetwork (Optional)

**Why it exists:** purely to reduce polling / trigger automation; **not correctness-critical.** 

**What it does (conceptually):**

* Emits low-volume “label_written / label_corrected” hints to `fp.bus.control.v1` via IG. 
* Consumers treat these as *notifications*, never an alternate truth channel.

---

## One internal “law” to prevent drift as we go deeper

Inside LS, there is exactly **one truth spine**:

* **Truth:** S5 Timeline Ledger Core
* **Derived / rebuildable:** S6 views, S7 export materializations, S8 notifications

This matches your platform’s general truth-vs-derived discipline and the deployment mapping (LS truth = `label_store` timelines).  

---

Understood. We’re now describing the **LS internal graph**: the **joins/paths/loops between LS subnetworks** (S1–S8), while **each subnetwork stays opaque**.

I’ll name internal joins and then group them into production paths + loops.

---

## 0) Reminder: LS Level-1 nodes (still opaque)

* **S1** Edge (public write/read/bulk surfaces)
* **S2** Governance & Policy (authority + shape rules)
* **S3** Target Canonicalizer (subject→canonical target key + ContextPins scoping)
* **S4** Write Determinism (idempotency + duplicate control)
* **S5** Timeline Ledger Core (append-only truth spine)
* **S6** Resolver & Views (timeline/as-of/current/conflict views)
* **S7** Export & Slices (bulk slices for OFS/MF; join helpers)
* **S8** Notifications (optional outbox → IG/control bus)

---

## 1) Internal joins (edges) inside LS

### Write-chain joins (truth creation)

**IJ-W1:** `S1 → S2`  (admit the write request: authority + required fields)
**IJ-W2:** `S2 → S3`  (canonicalize subject into a stable TargetKey + scope)
**IJ-W3:** `S3 → S4`  (compute idempotency scope and dedupe identity)
**IJ-W4:** `S4 → S5`  (append the assertion into the truth ledger, or short-circuit as DUPLICATE)
**IJ-W5:** `S5 → S1`  (return outcome: ACCEPTED / DUPLICATE / REJECTED)

### Read-chain joins (truth consumption)

**IJ-R1:** `S1 → S3`  (canonicalize requested subject into TargetKey)
**IJ-R2:** `S3 → S6`  (request a view: timeline / as-of / current)
**IJ-R3:** `S6 ↔ S5`  (S6 fetches timeline events from truth ledger; applies as-of/conflict rules)
**IJ-R4:** `S6 → S1`  (return resolved view payload)

### Bulk/export joins (OFS/MF scale reads)

**IJ-X1:** `S1 → S3`  (canonicalize bulk scope / target set)
**IJ-X2:** `S3 → S7`  (translate scope into bulk slice request)
**IJ-X3:** `S7 ↔ S5`  (bulk timeline scan / keyed fetch)
**IJ-X4:** `S7 ↔ S6`  (optional: reuse the same resolver semantics for as-of/current views at scale)
**IJ-X5:** `S7 → S1`  (return slice pages/refs and digests)

### Derived-coherence joins (keep derived views/slices aligned with the ledger)

**IJ-D1:** `S5 → S6`  (signal “new assertion appended” for view invalidation / incremental update)
**IJ-D2:** `S5 → S7`  (signal “label state changed” for export/slice invalidation / incremental update)

### Optional notification joins (non-correctness)

**IJ-N1:** `S5 → S8`  (enqueue notification payload in outbox on successful append)
**IJ-N2:** `S8 → (external)`  (emit to IG → fp.bus.control.v1; retries are internal to S8)

### Policy distribution joins (rule source for multiple nodes)

**IJ-P1:** `S2 → S1` (public surface rules: required fields, allowed operations)
**IJ-P2:** `S2 → S3` (target/key rules: what constitutes event/entity/flow targets; scoping rules)
**IJ-P3:** `S2 → S4` (idempotency rules: what defines “same assertion”)
**IJ-P4:** `S2 → S6/S7` (resolution rules: conflict posture, as-of semantics, precedence if any)

That’s the **complete internal join set** you should assume in a production-ready LS. Everything else (caches, DB indexes, storage layout) is an implementation detail *inside* S5/S6/S7.

---

## 2) Internal production paths (sequences of joins)

### P-W1: Write new assertion (happy path)

`S1 → S2 → S3 → S4 → S5 → S1`
(+ optionally `S5 → S6` and/or `S5 → S7` and/or `S5 → S8` as follow-on internal side effects)

### P-W2: Write retry / duplicate (idempotent)

`S1 → S2 → S3 → S4 (detect DUP) → S1`
(ledger unchanged; side-effects suppressed or deterministic)

### P-W3: Write rejected (authority / shape / target invalid)

`S1 → S2 (REJECT) → S1`  *or*  `S1 → S2 → S3 (REJECT) → S1`

### P-R1: Read timeline

`S1 → S3 → S6 → S5 → S6 → S1`

### P-R2: Read label_as_of(T)

`S1 → S3 → S6(as_of=T) → S5 → S6 → S1`
(same path; different resolver mode)

### P-X1: Bulk label_as_of slice for OFS

`S1 → S3(scope) → S7 → S5 → (S6 if needed) → S7 → S1`

### P-D1: Post-append coherence update (derived refresh)

`S5 → S6` (invalidate/update view layer)
`S5 → S7` (invalidate/update export/slice layer)

### P-N1: Optional control emission (outbox-driven)

`S5 → S8(outbox) → emit/retry → (external IG/control bus)`
(never required for correctness)

### P-P1: Policy revision takes effect

`policy input → S2 → {S1,S3,S4,S6,S7}`
(and may trigger a **recompute** path inside S6/S7)

---

## 3) Internal loops/cycles (what “cycles” exist inside LS)

### L-C1: Read-after-write coherence loop (Case UX + correctness)

`P-W1 append → (S5 → S6 update) → subsequent P-R1/P-R2 reads reflect new truth`
This is the “ledger drives views” cycle.

### L-C2: Export freshness loop (OFS/MF bulk consumption)

`P-W1 append → (S5 → S7 dirty/update) → subsequent P-X1 bulk slice uses updated state`
Ledger drives slices, not the other way round.

### L-C3: Notification retry loop (optional)

`S5 enqueue → S8 emit fails → S8 retry → emit succeeds`
Must be **idempotent** and **non-blocking**.

### L-C4: Policy-change recomputation loop

`policy_rev changes → S2 distributes → S6/S7 recompute derived interpretations/slices (if needed)`
Truth ledger does not change; only derived views shift under new rules.

### L-C5: Repair/reconciliation loop (production hardening)

A background reconciliation conceptually exists:
`S6/S7 detect “derived lag” → reread from S5 → repair`
This is what keeps “derived layers” rebuildable without ever mutating truth.

---

## 4) One compact internal graph (joins only)

```
Writes:   S1 -> S2 -> S3 -> S4 -> S5
Reads:    S1 -> S3 -> S6 <-> S5
Bulk:     S1 -> S3 -> S7 <-> S5  (optionally via S6)
Derived:              S5 -> S6,  S5 -> S7
Notify:               S5 -> S8 -> (external)
Policy:               S2 -> {S1,S3,S4,S6,S7}
```

---

Perfect. We’ll illuminate **the LS write chain** one join at a time, and I’ll **declare what is / isn’t allowed** so we stay inside the outer-network pins (truth vs evidence, append-only, as-of semantics, idempotency, environment ladder).

### Write-chain (context)

```
IJ-W1  S1 Edge  → S2 Governance/Policy
IJ-W2  S2       → S3 Target Canonicalizer
IJ-W3  S3       → S4 Write Determinism
IJ-W4  S4       → S5 Timeline Ledger Core
IJ-W5  S5       → S1 Edge  (receipt out)
```

## Global “write-chain laws” (authoritative, to prevent drift)

1. **Truth is created only by appending to the S5 ledger** (append-only; corrections are new assertions).
2. **Every accepted label assertion must carry effective_time + observed_time** (leakage-safe as-of depends on this).
3. **Evidence is by-ref only** (no big payload duplication “to be complete”).
4. **Idempotency is mandatory at the LS boundary** (at-least-once is real; duplicates must not create new timeline entries).
5. **Same semantics in local/dev/prod**; only strictness/operational envelope varies (but the mechanism exists everywhere).

With those pinned, here’s IJ-W1 → IJ-W5.

---

# IJ-W1 — S1 → S2 (Write admission: authority + shape)

### Purpose

Turn an external “write request” into an **admissible label assertion** *only if*:

* the writer is authorized, and
* the assertion has the minimum truth semantics (times, provenance, target form, etc.).

### What crosses this join (conceptually)

A single object we’ll call **WriteIntent**, containing:

* **caller identity / principal** (who is writing)
* **declared source** (Case Workbench vs dispute feed, etc.)
* the **proposed LabelAssertion** (subject/value/provenance/effective+observed times)
* optional **evidence_ref(s)** (by-ref pointers)
* an **idempotency handle** (see IJ-W3)

### What S1 is allowed to do (and not do)

**S1 MAY:**

* do basic envelope parsing, request sizing limits, and authentication handoff
* attach correlation ids for tracing
* reject malformed JSON/shape errors early

**S1 MUST NOT:**

* decide authority (“is this writer allowed?”) → that’s S2
* invent missing semantics (e.g., silently synthesize effective_time/observed_time)
* write to the ledger (no bypass)

### Output of IJ-W1 (S2’s response)

**AdmissionDecision**:

* `ACCEPT` + **PolicyContext** (policy_rev, allowed label families, required fields, conflict posture hooks)
* or `REJECT` with reason (unauthorized / missing required fields / forbidden payload style, etc.)

### Designer boundary call (authoritative)

**If the request is missing effective_time or observed_time → REJECT.**
Reason: the platform explicitly pins dual-time semantics as the basis for “LABEL AS-OF” and leakage-safe learning.

*(Environment ladder note: local can use a permissive policy_rev, but it still goes through S2 and the same checks exist; “local bypass” is banned.)*

---

# IJ-W2 — S2 → S3 (Target canonicalization under policy)

### Purpose

Convert “what the caller thinks the subject is” into a **canonical TargetKey** that the rest of the platform can join on consistently (this is the biggest drift risk).

### What crosses this join

A **CanonicalizeTargetRequest**:

* the admitted LabelAssertion (minus any disallowed payload)
* **PolicyContext** from S2 (what target types exist, what scoping pins are required, any normalization rules)

### What S2 is allowed to do (and not do)

**S2 MAY:**

* enforce “truth vs evidence” boundary (e.g., evidence must be by-ref)
* enforce “writer authority matrix” (who may write which label families)

**S2 MUST NOT:**

* decide the canonical join key (that’s S3’s authority)
* “fix up” ambiguous subjects (ambiguity must surface as rejectable)

### Output of IJ-W2

**CanonicalTargetResult**:

* `TargetKey` (canonical, stable, deterministic)
* `TargetScope` (ContextPins scoping if required)
* or `REJECT` with reason `INVALID_TARGET` / `AMBIGUOUS_TARGET` / `MISSING_SCOPE_PINS`

### Designer boundary call (authoritative)

**S3 must fail closed on ambiguous targets.**
No “best effort guess” (that’s how silent join drift starts).

---

# IJ-W3 — S3 → S4 (Idempotency + dedupe identity)

### Purpose

Turn a canonical TargetKey + admitted assertion into a **write-determinism identity**:

* so retries don’t create duplicate timeline events, and
* so “same idempotency key, different content” is caught as a conflict.

### What crosses this join

A **DeterminizeWriteRequest**:

* canonical `TargetKey` + `TargetScope`
* normalized label payload (family/value/times/provenance)
* the caller-provided **idempotency handle** (or source_event_id equivalent)

### Output of IJ-W3

A **WriteDeterminismPlan**:

* `dedupe_fingerprint` (what must be unique)
* `content_fingerprint` (what content we claim we’re writing)
* `idempotency_scope` (what “same” means)
* and either:

  * `PROCEED_TO_APPEND` with a fully prepared AppendCommand
  * or `DUPLICATE_SHORT_CIRCUIT` (if S4 can deterministically prove it’s a no-op without hitting the ledger)
  * or `REJECT` with `IDEMPOTENCY_KEY_CONFLICT` / `INVALID_IDEMPOTENCY_HANDLE`

### Designer boundary call (authoritative)

**Idempotency handle is required for production writes.**
If a producer can’t provide one, we cannot guarantee append-only timelines won’t get polluted under retries (at-least-once is real).

(If you want a “dev convenience,” it must still be deterministic and explicit, e.g., “server derived idempotency = hash(payload)” and *recorded*—but that’s a policy decision, not an implicit fallback.)

---

# IJ-W4 — S4 → S5 (Append to truth ledger, or prove duplicate)

### Purpose

Perform the **only truth-creating operation** in LS:

* append a label event to the authoritative timeline ledger, or
* return DUPLICATE without changing truth.

### What crosses this join

A **LedgerAppendCommand** (prepared by S4):

* canonical `TargetKey` + scope pins
* label family/value
* effective_time + observed_time
* provenance (source/actor)
* evidence_ref(s) by-ref only
* idempotency identity (dedupe_fingerprint + content_fingerprint)
* optional `supersedes` pointer (if this is a correction event)

### S5’s non-negotiable behaviour

* **Atomic append**: either the event is appended once, or it isn’t.
* **No destructive updates**: corrections are new events; the prior remains.
* **Duplicate protection is enforced at the ledger** (unique constraint / transactional check), even if S4 pre-checks.

### Output of IJ-W4

**LedgerAppendResult**:

* `APPENDED` (returns new label_event_id + ledger position token)
* `DUPLICATE` (returns existing label_event_id it duplicates)
* `REJECT` (constraint violations / invariant breaks) with retryable flag for transient DB errors

### Designer boundary call (authoritative)

**S4 is allowed to *detect* duplicates, but S5 is the only authority that *decides* truth.**
So “duplicate short-circuit” can exist, but ledger-level uniqueness must still be the final guardrail.

---

# IJ-W5 — S5 → S1 (Return receipt to caller)

### Purpose

Give the caller a stable, idempotent outcome that’s usable for workflow and audit.

### What crosses this join

A **WriteReceipt**:

* outcome: `ACCEPTED | DUPLICATE | REJECTED`
* canonical TargetKey (so the caller knows what LS actually keyed it as)
* label_event_id (new or existing)
* policy_rev used (from S2 context, persisted in the ledger provenance)
* reason_code + retryable (for rejected)

### What’s “in line” vs “not in line” with the network boundary

**IN LINE:**

* receipts that allow Case / feed writers to retry safely and reconcile duplicates
* explicit “REJECTED because …” without hidden repair
* policy_rev attached so environment ladder/promotion doesn’t create mystery behaviour

**NOT IN LINE (banned):**

* returning `ACCEPTED` when only a derived view updated (truth must be S5 append)
* silently treating errors as duplicates
* silently accepting but dropping evidence/times fields (that breaks as-of truth)

---

## Quick “end-to-end” sanity: what we’ve pinned by exploring IJ-W1..IJ-W5

* **Authority boundary is enforced before canonicalization and before append** (S2 is mandatory).
* **Joinability is canonicalized once** (S3), not re-invented by callers.
* **Retries are safe** (S4/S5 idempotency), which is required for a Kafka-ish at-least-once world.
* **Truth is append-only** and lives in the `label_store` authoritative DB (S5).

---

Absolutely. We’ll illuminate **IJ-R1 → IJ-R4** as the **authoritative read chain** for LS, while still treating **S1/S3/S6/S5 as opaque modules** (we’re only pinning what must be true at their boundaries).

### Read-chain (context)

```
IJ-R1:  S1 Edge → S3 Target Canonicalizer
IJ-R2:  S3      → S6 Resolver & Views
IJ-R3:  S6  ↔   S5 Timeline Ledger Core
IJ-R4:  S6      → S1 Edge (response out)
```

## Read-chain laws (authoritative, to prevent drift)

1. **Time semantics never collapse**: reads must preserve the difference between *effective_time*, *observed_time*, and explicit **as-of** time; no hidden “now” for leakage-safe reads. 
2. **LS truth is the S5 ledger**; S6 is a *derived interpreter* of ledger events, never an alternate truth source.
3. **Labels are read “as-of” for training/rebuild** to make late/corrected labels safe.
4. **Same semantics across environments**; only operational envelope (scale/security/obs) changes.

With that pinned, here’s IJ-R1 to IJ-R4.

---

# IJ-R1 — S1 → S3

## Canonicalize the requested subject into a stable TargetKey

### Purpose

Turn whatever the caller supplies (“this event/entity/flow”) into **the one canonical target identity** LS uses everywhere. This is the **joinability drift kill-switch**: if canonicalization is sloppy, Case, OFS, and MF will silently diverge. 

### What crosses IJ-R1 (conceptually)

A **ReadIntent**:

* `read_mode`: `timeline | resolve`
* `subject`: raw caller subject (event/entity/flow)
* optional `label_family` filter
* optional `as_of_observed_time` (required for leakage-safe use cases)
* optional `effective_at_time` (the world time you want truth applied at; see IJ-R2)
* `caller_principal` + `purpose` tag (case_ui vs offline_shadow vs mf_eval)
* optional ContextPins (when the subject claims run/world scope)

### What S1 may / must not do

**S1 MAY**

* authenticate/identify caller
* route by endpoint (“/timeline”, “/as_of”, “/current”, “/bulk”) and enforce required parameters

**S1 MUST NOT**

* “guess” missing target identity
* silently fill `as_of` (“no hidden now” for leakage-safe reads)

### S3 output (what S1 receives back)

**CanonicalTargetResult**

* `TargetKey` (canonical stable key)
* `TargetScope` (ContextPins scoping if applicable)
* or `REJECT` with `INVALID_TARGET | AMBIGUOUS_TARGET | MISSING_SCOPE_PINS`

### Designer boundary call (authoritative)

**Ambiguous subject ⇒ REJECT (fail closed).**
No “best effort” canonicalization. That’s banned because it creates silent training/serving mismatch.

---

# IJ-R2 — S3 → S6

## Request a view: timeline / resolved “as-of” / current

### Purpose

Convert a canonical target into a **query specification** that S6 can execute deterministically:

* **timeline**: raw append-only events
* **resolve**: deterministic interpreted label state under explicit time semantics

### What crosses IJ-R2 (conceptually)

A **ViewRequest**

* `TargetKey`, `TargetScope`
* `view_kind`:

  * `timeline`
  * `resolved_label`
* `as_of_observed_time` (knowledge cut)
* `effective_at_time` (world-time application)
* `label_family` filter (optional)
* `caller_entitlements` (what the caller is allowed to see—e.g., whether evidence refs are returned)

### The critical pin: LS resolved reads are *2-time* queries

To avoid later drift, I’m pinning the resolved view to two explicit times:

* **observed_as_of** = “what did we know by time T?” (leakage-safety basis)
* **effective_at** = “what truth applies at world time t?”

This matches your platform’s “labels are effective vs observed time” and “as-of makes late labels safe.”

### Designer boundary calls (authoritative)

1. **Leakage-safe endpoints require `as_of_observed_time`.**
   If the caller uses the “as-of” surface without providing it ⇒ `REJECT(MISSING_AS_OF)`.

2. **`current_label` is allowed only as an explicit convenience view**, defined as:
   `observed_as_of = now` and `effective_at = now`, and the response must clearly report those values (so nobody mistakes it for evaluation-safe output). 

---

# IJ-R3 — S6 ↔ S5

## Fetch timeline events from the truth ledger; apply as-of/conflict rules

### Purpose

This is the “truth ↔ interpretation” boundary:

* **S5**: authoritative append-only label events (truth spine)
* **S6**: deterministic interpretation of those events into views (timeline/as-of/current)

### What crosses IJ-R3 (conceptually)

Two directions:

**S6 → S5: LedgerReadRequest**

* `TargetKey`, `label_family` (optional)
* optional `observed_time_upper_bound` (for efficient as-of queries)
* ordering requirement (“deterministic timeline order”)

**S5 → S6: LedgerEventStream**

* list/iterator of **LabelEvents** (append-only), including:

  * effective_time, observed_time
  * provenance
  * optional supersedes link
  * evidence refs (by-ref) where present

### Non-negotiable behaviour at this boundary

* **S6 must be able to recompute from S5**. Any caching/materialization in S6 is rebuildable; it can’t become a second truth store.
* **Ordering must be deterministic**, because “timeline” is a truth artifact used by Case and by learning.
* **Conflict posture must be explicit** (either a deterministic resolution rule or an explicit CONFLICT surface). Leaving conflict implicit is banned.

### Designer boundary call (authoritative)

**S5 is the final authority on what exists; S6 is never allowed to fabricate label events.**
If data is missing, the view must say “not found / unknown / conflict,” not invent “best guess.”

---

# IJ-R4 — S6 → S1

## Return the view payload (with explicit basis metadata)

### Purpose

Return a response that is:

* stable under replay,
* explicit about time basis,
* safe to use downstream (especially OFS/MF).

### What crosses IJ-R4 (conceptually)

A **LabelViewResponse** with:

* `TargetKey` (+ scope)
* `view_kind`: timeline/resolved
* `basis`:

  * `observed_as_of` used
  * `effective_at` used
  * `policy/version markers` if applicable later
* `result`:

  * **timeline**: ordered label events
  * **resolved**: `LABEL(value)` or `UNKNOWN` or `CONFLICT` (plus minimal metadata: which event(s) caused it)
* `visibility`: whether evidence refs are included or redacted (based on entitlements)
* error outcomes: `INVALID_TARGET | NOT_FOUND | UNAUTHORIZED | MISSING_AS_OF | CONFLICT`

### Designer boundary calls (authoritative)

1. **Every resolved response must echo the basis** (`observed_as_of`, `effective_at`).
   This is how we prevent “as-of drift” later and aligns with the platform rail. 

2. **No silent redaction that changes meaning.**
   If the caller lacks access to evidence refs, return “evidence_redacted=true” rather than omitting fields silently (so Case/OFS don’t mistake “missing evidence” for “no evidence”).

---

## Quick sanity: how IJ-R1..R4 stays aligned with outer network pins

* LS remains **lagged truth** (readable by Case + OFS), not a hot-path dependency.
* J14’s requirements (“as-of rules”, “deterministic rebuild basis”) are structurally supported by the read chain.
* Environment ladder is preserved: local/dev/prod share semantics; strictness/scale differ.

---

Yep. **IJ-X1 → IJ-X5** is the **bulk / export chain** that makes LS usable at OFS/MF scale *without* violating the platform rails (explicit as-of, by-ref + digests, reproducibility, no “scan latest”).

I’m going to pin a few **bulk laws** first (authoritative), then illuminate each join.

---

## Bulk/export laws (authoritative, production-safe)

1. **Bulk must be semantically identical to single-read semantics**
   A bulk “label_as_of” result for a target must equal what IJ-R would return for that same target + basis (only delivery/scale differs). This prevents “bulk drift” from poisoning training.

2. **Resolved bulk reads require an explicit `as_of` boundary**
   Leakage-safe joins are “as-of by rule”; “hidden now” is banned. Bulk interfaces must therefore *require* the observed-time as-of boundary for any resolved/bulk training slice.

3. **By-ref + digest posture is default**
   For large slices, the primary output should be **refs + digests**, not copied megabyte payloads, so DatasetManifests can pin reproducibility.

4. **Determinism is mandatory**
   Stable ordering + stable canonicalization rules are required whenever LS returns digests/“slice fingerprints”.

5. **Environment ladder only changes envelope** (limits, auth strictness, throughput), **not meaning**.

---

# IJ-X1 — S1 → S3

## Canonicalize **bulk scope / target set** into a canonical TargetSetPlan

### Purpose

Turn “here’s a million things I need labels for” into a **canonical target universe** that LS can serve reproducibly and deterministically—without allowing vague “scan LS for everything” behaviour.

### What crosses IJ-X1 (conceptually)

A **BulkReadIntent** with one of two *allowed* input shapes:

**Shape A — explicit target list (small/medium)**

* `targets_raw[]` (subjects: event/entity/flow in caller form)

**Shape B — by-ref target set (large, recommended)**

* `target_set_ref` (pointer to a stored list of subjects/keys the caller already built, e.g., from replay)

Plus shared parameters:

* `mode`: `bulk_resolve_as_of` | `bulk_timeline`
* `label_family` (or set)
* `observed_as_of` (**required** for `bulk_resolve_as_of`)
* optional `effective_at` (world-time application)
* caller purpose tag (case_ui vs offline_shadow vs mf_eval)

### What S3 outputs

A **TargetSetPlan**:

* canonical `TargetKey` representation (or a plan to derive it from `target_set_ref`)
* `target_scope` (ContextPins scoping when the target claims run/world joinability)
* a **stable ordering** rule for the target set (needed for stable digests)
* optional sharding hints (for scale), but **sharding must not affect semantic results**

### Designer boundary calls (authoritative)

* **No unbounded “give me all labels” queries.** Bulk must be driven by an explicit target universe (list or by-ref target_set). This is required by the platform’s by-ref / reproducibility posture.
* **Heterogeneous target types (event+entity+flow mixed) are allowed only if explicitly declared**; otherwise reject and force separate requests. This prevents ambiguous canonicalization and unstable ordering.

---

# IJ-X2 — S3 → S7

## Translate the TargetSetPlan into a BulkSliceRequest

### Purpose

Convert “canonical targets” into the actual **slice request** S7 can execute: what to fetch, under what time basis, and what the output contract must include for later manifests.

### What crosses IJ-X2

A **BulkSliceRequest**:

* `TargetSetPlan` (canonical targets + stable ordering + scope pins)
* `basis`:

  * `observed_as_of` (required for resolved)
  * optional `effective_at`
* `label_family` filters
* desired output shape:

  * `resolved_labels` or `timelines`
  * delivery: `paged_inline` or `by_ref_artifact` (S7 may override based on size thresholds)

### Designer boundary calls (authoritative)

* **If `mode = bulk_resolve_as_of` and `observed_as_of` is missing → reject.** (Leakage safety is a platform law.)
* **S7 is not allowed to change “basis meaning.”** It may choose paging/streaming/artifact emission, but the semantic basis must be echoed back unchanged.

---

# IJ-X3 — S7 ↔ S5

## Bulk ledger fetch: keyed reads / bounded scans (append-only truth spine)

### Purpose

Fetch the necessary **ledger events** (truth) at scale for the target universe.

### What crosses IJ-X3

**S7 → S5: LedgerBulkReadRequest**

* canonical targets (or shard descriptors)
* label_family filters
* optional `observed_time_upper_bound = observed_as_of` (optimization; not semantics)
* deterministic ordering requirement

**S5 → S7: LedgerBulkEventStream**

* ordered label events per target (append-only)
* includes effective_time + observed_time + provenance + evidence refs (by-ref)

### Non-negotiables at this boundary

* **S5 remains the only truth source.** S7 can’t “invent” missing labels; it can only report UNKNOWN/NOT_FOUND/CONFLICT from derived logic.
* **Deterministic ordering** is mandatory (for stable digests and reproducible slices).
* **No silent drops**: if a target_set_ref is malformed, unreadable, or inconsistent, that’s a hard error (and should be diagnosable), not a partial success disguised as success.

---

# IJ-X4 — S7 ↔ S6

## (Optional) Use the same resolver semantics as single reads, at scale

### Purpose

Guarantee **semantic parity** between:

* “bulk resolved labels as-of” and
* the normal single-target `label_as_of(...)` read chain.

This is where bulk correctness is protected from “helpful but wrong” shortcut logic.

### What crosses IJ-X4

Two equivalent conceptual designs (either is allowed; semantics must match):

**Design A (service/library call):**

* S7 supplies ledger events + basis → S6 returns resolved results (per target)

**Design B (shared rule kernel):**

* S6 exposes a “resolver kernel” that S7 uses identically for bulk

Either way, the contract is the same:

* input: ledger events + basis (`observed_as_of`, `effective_at`) + conflict posture rules
* output: resolved label state per target: `LABEL(value)` | `UNKNOWN` | `CONFLICT` (with minimal explanation)

### Designer boundary calls (authoritative)

* **Bulk resolved output must equal single resolved output for the same basis.** If not, that’s a bug, not an acceptable divergence.
* **Conflicts must surface explicitly** (either as CONFLICT state or a deterministic, declared precedence rule). Silent precedence is banned because it becomes hidden policy.

---

# IJ-X5 — S7 → S1

## Return slice pages / refs + digests (manifest-friendly)

### Purpose

Deliver bulk results in a form that:

* Case can page through, and
* OFS/MF can pin into **DatasetManifests** for reproducibility.

### What crosses IJ-X5

A **BulkSliceResponse**, with one of two delivery shapes:

### Shape 1 — paged inline

* `basis` echoed: `observed_as_of`, `effective_at`
* `target_set_fingerprint` (stable identity of the target universe)
* `page[]`: `(TargetKey, status, resolved_label?)`
* `next_page_token` (stable under retry)
* `page_digest` (optional, but recommended for reproducibility)

### Shape 2 — by-ref slice artifact (preferred for big OFS builds)

* `label_slice_ref` (object-store ref or equivalent)
* `slice_digest` (integrity claim)
* `row_count`, `schema_id`
* `basis` echoed + `target_set_fingerprint`
* optional `slice_receipt_id` (for audit/debug)

This directly supports the “DatasetManifest pins digests/refs + basis” posture.

### Designer boundary calls (authoritative)

* **Every bulk response must echo the basis explicitly.** Otherwise “as-of drift” will silently enter training pipelines.
* **If a digest is provided, mismatch is inadmissible** (fail closed / quarantine posture), not a warning.
* **Paging tokens must be retry-safe** (at-least-once reality); re-requesting the same page must not yield different content.

---

## Environment profile knobs that affect IJ-X (envelope only, not semantics)

These are the knobs you’ll want when you implement:

* `max_inline_targets`, `max_page_size`, `max_bytes_per_response`
* “force by-ref artifact above size threshold”
* timeouts/concurrency caps
* auth strictness for bulk reads (local permissive, prod strict), **without changing basis requirements**

---

## The single most important pin we just made

**Bulk slices are “manifest-grade outputs”:** they must be deterministic, basis-echoing, and digestable so OFS can build reproducible DatasetManifests.

---

Yep — we’ll illuminate **IJ-D1 / IJ-D2** (derived coherence) and **IJ-N1 / IJ-N2** (optional notifications) with **design-authority pins** on what is/isn’t allowed, while keeping **S5/S6/S7/S8 opaque**.

---

# First: what these joins are “allowed to be”

**Authoritative stance:** **IJ-D*** and **IJ-N*** are *secondary effects* of a successful ledger append. They exist to improve latency/ops/automation, but **must never become a second truth channel** and must never be required for correctness.
This matches:

* LS truth lives in the **append-only label_store timeline** 
* late labels are normal; as-of semantics keep things safe 
* optional label events to `fp.bus.control.v1` are permitted but are **optional** 

---

# IJ-D1 — S5 → S6

## “Ledger append committed” → view invalidation / incremental update

### Purpose (what it’s for)

To keep **S6 (Resolver & Views)** aligned with **S5 (truth ledger)** efficiently:

* invalidate caches
* update materialized views
* maintain fast “current / as-of” resolution without re-scanning timelines every time

**But:** S6 must always be able to answer correctly by reading S5 directly; IJ-D1 is an optimization edge.  

### When it fires

**Only after** S5 has durably committed an append (i.e., after IJ-W4 results in `APPENDED`).
**Designer call:** do **not** fire IJ-D1 for a pure `DUPLICATE` write; it creates noise and can cause needless churn.

### What crosses the join (conceptual payload)

A minimal **LedgerDelta** signal (pointer-like, deterministic):

* `label_event_id`
* `target_key` (canonical)
* `label_family`
* `observed_time`, `effective_time`
* `supersedes_label_event_id` (if correction)
* `ledger_position_token` (optional ordering/progress marker)

No large blobs; no “derived result”; just “a new truth event exists.”

### Non-negotiable rules (what is / isn’t inline)

**IN LINE**

* S6 may use the delta to **invalidate** or **incrementally update** derived indices/views.
* S6 may lag behind briefly; correctness comes from S5.

**NOT IN LINE (banned)**

* S6 treating IJ-D1 as the source of truth (e.g., “if I didn’t receive the signal, the event doesn’t exist”).
* S6 “materializing” an interpretation that can’t be derived from S5 (fabricating truth).

### Read correctness constraint that matters for as-of safety

Even if S6 is stale, it must never violate as-of semantics:

* For `label_as_of(observed_as_of=T)`, S6 must never return a label derived from any event with `observed_time > T`.
  Staleness that returns *older* truth is safe; staleness that leaks future knowledge is not. 

---

# IJ-D2 — S5 → S7

## “Ledger append committed” → export/slice invalidation / incremental maintenance

### Purpose (what it’s for)

To keep **S7 (Export & Slices)** aligned with ledger truth:

* mark cached slices as stale
* update per-family/per-scope indexes
* maintain “bulk label_as_of” performance (OFS/MF scale)

Again: S7 must be rebuildable from S5; IJ-D2 is an optimization edge.

### When it fires

Same rule as IJ-D1:

* fires **only after** durable commit of a new label event (`APPENDED`)
* does not fire on `DUPLICATE` (designer call)

### What crosses the join (conceptual payload)

A minimal **SliceDelta**:

* `label_event_id`
* `target_key`
* `label_family`
* `observed_time`, `effective_time`
* optional “scope tags” that help precompute slices (e.g., run/world pins if you later choose to scope exports that way)

### The big production constraint (ties to manifests/backfill)

Because OFS/MF reproducibility is pinned to **by-ref artifacts + digests**, any LS-produced “slice artifact” that is referenced externally must follow this rule:

**Designer call (authoritative):**
If S7 emits a by-ref slice artifact with a digest, it is **immutable**. A rebuild creates a **new ref/digest**, never overwrites.
This aligns with “DatasetManifest is the reproducibility bridge” and “backfill is declared/auditable; never silent.” 

---

# IJ-N1 — S5 → S8

## enqueue optional notification (outbox) on successful append

### Purpose (what it’s for)

To create a **notification hint** (“label_written / label_corrected”) that can trigger schedulers/ops without polling LS.

This is explicitly allowed: “Label Store … optional label events → fp.bus.control.v1.” 

### When it fires

**Only after** S5 commit of a new event (`APPENDED`).
**Designer call:** do not enqueue notifications for `DUPLICATE` (noise) unless you later have a very specific ops reason.

### What crosses the join (conceptual payload)

A **NotificationOutboxEntry** that is *pointer-like*:

* `notification_type`: `label_written` | `label_corrected`
* `label_event_id`
* `target_key` (+ label_family)
* `observed_time` (so consumers can decide relevance/lag)
* optionally `effective_time`
* optionally a short “why” (provenance source type)

**Not allowed:** full timelines, large payloads, or any “truth state” that could be mistaken as canonical.

### Non-negotiable rule

**N1 is non-blocking:** failure to enqueue must not make the write fail.
Reason: notifications are optional and must never become correctness-critical. 

---

# IJ-N2 — S8 → external (IG → `fp.bus.control.v1`)

## emit notification events (idempotent + retryable)

### Purpose (what it’s for)

Deliver the notification to the control bus so external automation can react.

Deployment pins the control topic and allows low-volume control facts, including label events.  

### How it must behave (authoritative)

* **Idempotent emission:** if S8 retries, it must not create logically distinct notifications (same outbox entry → same emitted event identity).
* **At-least-once tolerant:** duplicates may happen; consumers must treat as notifications, not state. (Matches the platform’s general bus reality.) 
* **Never a truth channel:** consumers must still read LS for truth; N2 only says “something changed.”

### What “in line” vs “not in line” looks like

**IN LINE**

* event contains pointers (label_event_id / target_key / observed_time) and correlation IDs
* goes through IG/bus discipline (front door) as a control fact (low volume)

**NOT IN LINE (banned)**

* consumers using control events as “the label store”
* emitting payloads that could be joined as if they were authoritative label states

---

## Environment ladder notes (what changes and what must not)

**Semantics must not change** across local/dev/prod; only envelope changes. 

Allowed differences:

* local may implement IJ-D* as in-process callbacks, prod as async queue/outbox — **same meaning**
* retry policy, batching thresholds, rate limits
* auth strictness for emitting to control bus

Not allowed:

* “local bypasses derived coherence/notifications entirely and behaves differently” — you can disable optional notification emission, but derived coherence semantics (ledger is truth; views/slices are derived) must still hold.

---

## The single pin I’m declaring for all four joins

**S5 is the only truth.**

* IJ-D1/IJ-D2 keep **derived** layers aligned.
* IJ-N1/IJ-N2 publish **optional hints**.
  None of these may be required for correctness, and none may create alternate truths.  

If you want to go deeper next, the best next illumination is: **what “view invalidation” means concretely for S6 under as-of (observed_time discipline)**, because that’s the easiest place for an implementer to accidentally leak future knowledge even if everything else is correct. 

---

Alright — **IJ-P1 → IJ-P4** is the “policy distribution spine” inside LS. This is where we prevent the classic drift failure mode: *different submodules quietly interpreting the same label differently*.

I’m going to **pin (authoritatively)** what “policy” is inside LS, how it’s versioned, and what each IJ-P edge carries.

---

## 0) What “policy” means inside LS (authoritative)

### P0.1 — Policy is an **immutable bundle** with a **revision id**

* LS policy ships as an immutable **PolicyBundle** identified by `ls_policy_rev`.
* “Changing policy” means activating a *new* `ls_policy_rev`; it never mutates existing bundles.

### P0.2 — Every write/read must be attributable to a specific `ls_policy_rev`

* **Write receipts** echo the `ls_policy_rev` used.
* Ledger events (S5) record the `ls_policy_rev` used at write time (provenance).
* Read responses echo the `ls_policy_rev` used to interpret the view.
* Bulk slice responses echo `ls_policy_rev` and their basis metadata (so manifests can pin it later).

### P0.3 — Policy changes must not rewrite truth

* Policy can change **derived interpretation** (S6/S7), but never rewrites the append-only ledger (S5).
* If a policy change would make a previously valid label event “invalid”, the event stays; the *interpretation* changes.

### P0.4 — Read reproducibility requires explicit policy capture

* Default: reads use the **currently active** `ls_policy_rev` (fast, operationally simple).
* Reproducibility: any “serious” offline job (OFS/MF) must **record** the `ls_policy_rev` used in its basis (e.g., in DatasetManifest).
  (This is the same spirit as pinning replay basis + as-of boundary — otherwise you can’t reproduce training.)

Those four pins are the backbone; everything else is detail.

---

## 1) The policy objects that flow over IJ-P edges

Think of PolicyBundle as 4 sub-policies (exactly matching IJ-P1..P4):

1. **SurfacePolicy** (S1 rules): required fields, endpoint enablement, max sizes, “as-of required” gating, etc.
2. **TargetPolicy** (S3 rules): what “event/entity/flow” means, required join keys, ContextPins scoping rules, canonicalization rules.
3. **IdempotencyPolicy** (S4 rules): what defines “same assertion”, how dedupe/content fingerprints are built, what conflicts look like.
4. **ResolutionPolicy** (S6/S7 rules): as-of semantics parameters (within the pinned law), conflict posture, precedence rules *if any*, view shapes.

---

## 2) IJ-P1 — S2 → S1

### Public surface rules distribution

**Purpose**
Give S1 enough rules to behave consistently at the boundary *without* becoming the authority engine.

**What crosses IJ-P1**

* `ls_policy_rev`
* SurfacePolicy:

  * required fields for write/read/bulk endpoints
  * which endpoints are enabled (per environment profile)
  * parameter requirements (e.g., “resolved as-of requires observed_as_of”)
  * size/limit knobs *as policy-configured* (request max bytes, max targets, paging caps)
  * coarse operation allowlists (e.g., only Case principals may call `/write`, etc.)

**What’s allowed**

* S1 may do **early rejection** on purely mechanical policy rules (missing required param, endpoint disabled, payload too large).
* S1 may attach `ls_policy_rev` to the request context for downstream modules.

**What’s not allowed (banned)**

* S1 must not be the final authority on *who may assert what label family* (that remains S2’s job at IJ-W1).
* S1 must not “repair” missing semantics (no synthesizing times; no guessing targets).

**Design pin**

* S1’s job is **fast, deterministic gating**; S2 remains the **semantic authority**.

---

## 3) IJ-P2 — S2 → S3

### Target/key rules distribution (joinability definition)

**Purpose**
Make **TargetKey** canonicalization stable across the entire platform. This is the #1 drift vector, so we treat this edge as sacred.

**What crosses IJ-P2**

* `ls_policy_rev`
* TargetPolicy:

  * allowed target types: `event`, `entity`, `flow` (and any future extension)
  * required join keys per type (e.g., event_id vs entity_ref; what “flow” is keyed by)
  * ContextPins scoping rules:

    * when ContextPins are **required**
    * when they are **optional**
    * when they are **forbidden** (to avoid false uniqueness)
  * canonicalization rules (normalization, alias handling, strictness)

**What’s allowed**

* S3 uses TargetPolicy to:

  * fail closed on invalid/ambiguous targets
  * enforce “missing scope pins” when required
  * produce one canonical TargetKey form used everywhere else

**What’s not allowed (banned)**

* “Best effort” canonicalization. If multiple interpretations exist, reject.
* Silent fallback to a different key shape depending on environment.

**Design pin**

* **TargetPolicy is the single source of truth** for how labels join back to events/entities/flows.

---

## 4) IJ-P3 — S2 → S4

### Idempotency rules distribution (write determinism)

**Purpose**
Make write idempotency a **policy-defined contract**, not a code-path accident.

**What crosses IJ-P3**

* `ls_policy_rev`
* IdempotencyPolicy:

  * what fields participate in `dedupe_fingerprint`
  * what fields participate in `content_fingerprint`
  * idempotency scope rules (per target? per label family? include observed_time? include provenance?)
  * conflict rule: what happens if the same idempotency handle appears with different content
  * whether server-derived idempotency is permitted (if you ever allow it, it must be explicit + deterministic)

**What’s allowed**

* S4 uses IdempotencyPolicy to:

  * return DUPLICATE safely
  * reject `IDEMPOTENCY_KEY_CONFLICT` deterministically
  * ensure retries do not pollute the append-only ledger

**What’s not allowed (banned)**

* “Idempotency is optional” in prod. It isn’t.
* Using non-deterministic inputs (wall clock “now”, random) in fingerprinting.

**Design pin**

* If policy says “these fields define sameness,” *every* environment must obey it; only strictness/limits differ.

---

## 5) IJ-P4 — S2 → S6/S7

### Resolution rules distribution (views + bulk semantics)

**Purpose**
Ensure single reads (S6) and bulk exports (S7) are **semantically identical**, especially for “as-of” leakage safety and conflict handling.

**What crosses IJ-P4**

* `ls_policy_rev`
* ResolutionPolicy:

  * the allowed view kinds (`timeline`, `resolved_as_of`, `current`)
  * required basis parameters:

    * `observed_as_of` required for leakage-safe resolved views
    * `effective_at` usage rules (if/when applied)
  * conflict posture:

    * either explicit `CONFLICT` return
    * or a declared precedence rule (if you ever choose one)
  * redaction/visibility rules (what evidence refs are returned to which caller class)
  * bulk parity requirement (bulk resolved must match single resolved)

**What’s allowed**

* S6/S7 can cache, index, and materialize **derived** views as long as:

  * they can be rebuilt from S5
  * they never leak future knowledge beyond `observed_as_of`
  * they always echo the basis (`observed_as_of`, `effective_at`, `ls_policy_rev`) in responses

**What’s not allowed (banned)**

* Silent precedence rules that aren’t surfaced in policy.
* Bulk using “approximate” heuristics that differ from S6.
* Treating “current” as default for anything that claims to be leakage-safe.

**Design pin**

* **ResolutionPolicy is part of the reproducibility basis** (same class as as-of boundary and replay basis).

---

## 6) Policy activation & distribution mechanics (how the edges behave in production)

I’m pinning a simple, robust mechanism:

1. **S2 owns the active pointer**: `active_ls_policy_rev`.
2. Each request (write/read/bulk) is evaluated under **one specific `ls_policy_rev`**:

   * S2 attaches it as PolicyContext early.
3. S1/S3/S4/S6/S7 may cache bundles by `ls_policy_rev`, but:

   * if they don’t have it cached, they fetch it from S2 (or S2 supplies it in-band).
4. Policy changes are **atomic at the pointer**:

   * new requests get the new rev
   * in-flight requests finish under the old rev (no mid-flight semantic split)

This gives consistency without turning policy into a performance bottleneck.

---

## The key “boundary” calls I’m making (so you can sanity-check drift)

* **Policy is versioned, immutable, and echoed everywhere.**
* **TargetPolicy is the canonical join definition**; ambiguous targets fail closed.
* **IdempotencyPolicy defines sameness**; conflicts are explicit rejections.
* **ResolutionPolicy governs views + bulk parity**; “as-of requires observed_as_of” is enforced at the surface.

If you want the next illumination step, the highest leverage is **IJ-P2 (TargetPolicy)**: we pin the minimal TargetKey shapes for `event/entity/flow` and the ContextPins scoping rule. That single decision removes most of the remaining ambiguity in both the write chain and the bulk export chain.

---

Understood. We’ll “illuminate” the **internal production paths** you listed — still treating S1/S2/S3/S4/S5/S6 as opaque boxes, but making the **step-by-step flow, guarantees, and failure semantics** explicit so we can’t drift later.

These path semantics must remain aligned with the platform pins:

* **Labels become truth only when written to Label Store**, as **append-only timelines** with **effective_time + observed_time**, and corrections are new assertions. 
* **Training/rebuild joins are “as-of” by rule** (leakage-safe), and rebuilds must be reproducible against the basis.  
* **Time semantics never collapse** (domain time vs observed/ingest/apply must remain distinct). 
* We assume production-shaped substrate realities: **transactional DB writes** for truth timelines and **at-least-once** delivery in the wider platform.  

---

## P-W1 — Write new assertion (happy path)

**Path:** `S1 → S2 → S3 → S4 → S5 → S1` (+ optional `S5 → S6/S7/S8`)

### What this path does (authoritative intent)

Create **new label truth** by appending a single **LabelEvent** into the S5 timeline ledger (append-only). 

### Step-by-step (opaque modules, explicit contracts)

1. **S1 (Edge) receives a write**

   * Input is a LabelAssertion + caller identity + idempotency handle.
   * S1 may parse/size-limit/authenticate, but **must not** decide authority or invent missing semantics. 

2. **S2 (Governance/Policy) admits or rejects**

   * Enforces: writer authority (“who can assert what”), required fields, truth-vs-evidence boundary.
   * **Design authority call:** missing `effective_time` or `observed_time` ⇒ **REJECT** (no “server fills it in”). 

3. **S3 (Target Canonicalizer) produces canonical TargetKey**

   * Converts subject (event/entity/flow) into a stable canonical TargetKey.
   * Enforces scoping pins when target is run/world-joinable (ContextPins posture). 
   * **Design authority call:** ambiguity ⇒ **REJECT** (no “best effort guess”). 

4. **S4 (Write Determinism) produces the append plan**

   * Computes dedupe identity from (TargetKey + label family + idempotency handle + content fingerprint).
   * Prepares a single LedgerAppendCommand.

5. **S5 (Timeline Ledger Core) appends truth**

   * Transactionally appends a new label event (append-only).
   * Records: effective_time, observed_time, provenance, and by-ref evidence pointers (if any). 
   * Returns `APPENDED` with `label_event_id` (and any ledger position token).

6. **S1 returns WriteReceipt**

   * `ACCEPTED`, canonical TargetKey, label_event_id, and the policy rev used (so behavior is attributable).

### Follow-on internal side effects (still part of production reality)

After **APPENDED** only:

* `S5 → S6` (**IJ-D1**) invalidate/update resolved views (derived layer).
* `S5 → S7` (**IJ-D2**) invalidate/update bulk/export indices/slices (derived layer).
* `S5 → S8` (**IJ-N1**) enqueue optional “label_written/label_corrected” notification (non-correctness). 

**Design authority call:** these side effects must never be required for correctness; if they fail, the write is still committed and truth exists in S5. 

---

## P-W2 — Write retry / duplicate (idempotent)

**Path:** `S1 → S2 → S3 → S4(detect DUP) → S1`
*(ledger unchanged; side effects suppressed or deterministic)*

### What this path does (authoritative intent)

Handle at-least-once retries without polluting the append-only ledger: duplicates must not create new timeline entries. 

### Two legitimate outcomes (and one forbidden)

1. **Duplicate, same content**

   * S4 determines the write is identical to a previously accepted assertion **under idempotency scope**.
   * Returns `DUPLICATE` with the existing `label_event_id`.
   * **No** IJ-D/IJ-N side effects (or if emitted, they must be deterministic/noise-free).

2. **Duplicate key, different content**

   * Same idempotency handle but different content fingerprint ⇒ **REJECT: IDEMPOTENCY_KEY_CONFLICT**.
   * **Design authority call:** we must fail closed here; otherwise you get “silent label corruption” under retries. 

3. **Forbidden behavior**

   * “Treat conflict as a new correction event automatically.”
     That’s banned: corrections are explicit human/external assertions, not a side-effect of transport retries. 

---

## P-W3 — Write rejected (authority / shape / target invalid)

**Path:** `S1 → S2(REJECT) → S1` **or** `S1 → S2 → S3(REJECT) → S1`

### What this path does (authoritative intent)

Reject writes **before** they can affect truth, with a reason that is stable and auditable.

### Rejection class A — S2 rejects (governance/policy)

Common reasons:

* unauthorized writer (wrong principal/source)
* missing required fields (effective_time/observed_time/provenance/subject/value)
* forbidden payload style (e.g., raw sensitive payload instead of by-ref evidence pointers) 

### Rejection class B — S3 rejects (target canonicalization)

Common reasons:

* invalid/unknown subject type
* ambiguous target (multiple interpretations)
* missing required ContextPins when the target claims run/world joinability 

### What S1 must return

A **WriteReceipt(REJECTED)** that includes:

* stable reason_code
* retryable flag (e.g., transient auth backend vs invalid target is non-retryable)
* policy rev used (so you can reproduce/diagnose behavior)

---

## P-R1 — Read timeline

**Path:** `S1 → S3 → S6 → S5 → S6 → S1`

### What this path does (authoritative intent)

Return the **append-only label event timeline** for a target (truth history), deterministically ordered, suitable for Case UX and audit reasoning. 

### Step-by-step

1. **S1 receives timeline request**

   * includes subject (raw), optional label-family filter, caller identity/entitlements.

2. **S3 canonicalizes target**

   * same “fail closed on ambiguity” rule as writes.

3. **S6 requests timeline events from S5**

   * S6 is an interpreter; it must not fabricate events.
   * S5 returns ordered events; S6 may apply redaction rules (evidence pointers may be hidden based on caller entitlements) but must not change meaning silently. 

4. **S1 returns timeline response**

   * includes canonical TargetKey, ordered events (each with effective_time + observed_time + provenance), and paging if needed.

**Design authority call:** timeline must always include superseded history (append-only); you can add a convenience “superseded_by” field, but you can’t hide prior assertions. 

---

## P-R2 — Read `label_as_of(T)` (resolved view)

**Path:** `S1 → S3 → S6(as_of=T) → S5 → S6 → S1`

### What this path does (authoritative intent)

Return “**what label state did we know by time T**?” in a leakage-safe way — the key requirement for OFS/MF joins and honest evaluation.  

### Inputs (must be explicit)

* `observed_as_of = T` (**required** for “as-of”)
* optional `effective_at` (world-time application; often set equal to T for training/eval joins)
* target subject + optional label family filter 

### Resolution semantics (pinned)

S6 computes the resolved label in two stages:

1. **Knowledge cut (leakage safety):**

   * eligible events are those with `observed_time <= observed_as_of`. 

2. **World application (optional but explicit):**

   * among eligible events, consider truth that applies at `effective_at` (if provided).
   * if not provided, default `effective_at = observed_as_of` for “as-of” reads (designer call: keeps semantics simple and safe). 

3. **Conflict posture must be explicit:**

   * if S6 can determine a single resolved value under the declared rules → return it
   * else return `CONFLICT` (or whatever explicit conflict representation we pin later)
     **No silent precedence.** 

### Step-by-step

1. **S1 receives label_as_of request**

   * **Design authority call:** missing `observed_as_of` ⇒ **REJECT** (no hidden now). 

2. **S3 canonicalizes target**

3. **S6 fetches eligible ledger events from S5**

   * S5 may support an upper bound filter by observed_time for efficiency, but semantics are the same.

4. **S6 resolves and returns**

   * response must echo basis metadata:

     * observed_as_of used
     * effective_at used
     * policy rev used

### Why basis echo is non-negotiable

Because DatasetManifests must pin **as-of boundary** and reproducibility basis; if LS doesn’t echo it, downstream will drift or silently mis-train.  

---

## One last drift check before we move deeper

Across all five paths:

* **Truth creation happens only at S5 append** (P-W1), never via views or exports. 
* **All resolved reads that claim leakage safety require explicit observed_as_of** (P-R2). 
* **Idempotency is mandatory** (P-W2). 
* **Same semantics across environments**; only envelope knobs change.

---

Yep — “these” = **P-X1, P-D1, P-N1, P-P1**. I’ll illuminate each as a **production path** (modules still opaque), and I’ll be explicit about **what is allowed / banned** so we don’t drift.

---

## P-X1 — Bulk `label_as_of` slice for OFS

**Path:** `S1 → S3(scope) → S7 → S5 → (S6 if needed) → S7 → S1`

### What this path exists to do

Provide **the label inputs needed for deterministic offline rebuild “as-of time T”** at dataset scale, with **late/corrected labels handled safely** and **no leakage**.  

This path is the internal mirror of the platform pin:

* Offline Shadow rebuild must be deterministic and record basis (replay basis + as-of boundary + feature versions). 
* Late labels are normal; “as-of” makes them safe. 

### Production inputs (what S1 must require)

From OFS (or any bulk consumer), S1 must receive:

1. **Target universe** (what labels to fetch): either

   * explicit target list, or
   * **by-ref target_set** derived from replay (preferred at scale).
2. **Observed-time as-of boundary** (mandatory for resolved slices).  
3. Optional **effective-time posture** (usually same as observed boundary unless explicitly different). 

**Design authority call:** bulk resolved slices **must not** allow “give me current labels” by default. If a consumer wants “current,” it must be explicit (and that output must clearly say it used “as-of now”). This prevents silent leakage into training/eval. 

### Step-by-step (opaque modules, explicit behavior)

1. **S1 (Edge)** accepts a bulk request and validates **presence of `observed_as_of`** for resolved slices; applies size limits/paging. 
2. **S3 (Target Canonicalizer)** converts the supplied scope/targets into canonical **TargetKeys**, enforcing required join pins (ContextPins posture) when targets claim run/world joinability. 
3. **S7 (Export & Slices)** constructs a **BulkSlicePlan** that includes:

   * the canonical target set (or a ref to it),
   * the exact **as-of boundary**,
   * label-family filters,
   * a required **stable ordering** rule (so digests are stable). 
4. **S7 ↔ S5 (Ledger)** reads the **append-only truth events** needed for those targets; may apply an upper bound `observed_time <= observed_as_of` as an efficiency filter (not a semantics change). 
5. **(Optional) S7 ↔ S6 (Resolver)** applies the exact same resolution semantics as single reads (parity is required), producing `LABEL / UNKNOWN / CONFLICT` states per target under the declared basis. 
6. **S7 → S1** returns either:

   * paged inline results, **or**
   * a **by-ref slice artifact** (preferred for OFS), with **digest + basis metadata** so OFS can pin it into a DatasetManifest.  

### Output requirements (what must be echoed back)

Every bulk slice response must include:

* **observed_as_of boundary used**
* any **effective-time posture used**
* **join key semantics identifier** (at least policy/target schema rev)
* **digest/refs** if by-ref emitted
  so DatasetManifests can be the unit of reproducibility.  

### Banned behaviors (drift traps)

* ❌ Unbounded “give me all labels” scans (breaks reproducibility + encourages hidden coupling). 
* ❌ Bulk semantics diverging from single `label_as_of` semantics. 
* ❌ Returning results without explicit basis metadata (leakage + non-reproducibility). 

---

## P-D1 — Post-append coherence update

**Path:** `S5 → S6` (views) and `S5 → S7` (export/slices)

### What this path exists to do

Keep **derived layers** (views and bulk/export helpers) aligned with the **truth ledger**, so reads remain fast without creating a second truth source.

This is consistent with the platform’s “append-only truth + derived rebuildable outputs” posture and the explicit rails (append-only + supersedes, as-of semantics, idempotency).  

### When it fires

Only after **S5 commits a new label event** (`APPENDED`), not on `DUPLICATE`.

### What crosses the join (minimal “delta”, pointer-like)

* `label_event_id`
* `target_key`
* `label_family`
* `observed_time`, `effective_time`
* `supersedes` pointer (if correction)
* optional ledger position token

### Allowed outcomes (and what they mean)

* **S6 updates/invalidate**: cached or materialized resolved views are refreshed or marked stale.
* **S7 updates/invalidate**: cached slice indexes or precomputed export helpers are refreshed or marked stale.

**Design authority call:** If these coherence updates fail, **truth still exists** and correctness must still be obtainable by recomputing from S5. Coherence is an optimization, not a correctness dependency.

### Banned behaviors

* ❌ S6/S7 acting as “truth” (i.e., missing an update means the event doesn’t exist).
* ❌ Any coherence action that rewrites truth history (ledger is append-only; corrections are new events). 

---

## P-N1 — Optional control emission (outbox-driven)

**Path:** `S5 → S8(outbox) → emit/retry → (external IG/control bus)`

### What this path exists to do

Emit **low-volume notification facts** like `label_written` / `label_corrected` to the control bus **as hints**, so schedulers/Run-Operate can react without polling.

This is explicitly allowed in the deployment mapping:

* Label Store: “optional label events → `fp.bus.control.v1`.” 

And it must respect the platform bus posture:

* producers submit to IG; IG is the trust boundary; EB/control topics are durable append/replay planes. 

### How it works (opaque modules, pinned behavior)

1. **S5 commits** a new label event.
2. **S8 outbox** records a small notification entry (pointer-like, not a timeline).
3. S8 emits to **IG → `fp.bus.control.v1`**, retrying idempotently on transient failure.

### Notification payload posture (what is allowed)

Allowed fields are *pointers and basis cues*, e.g.:

* `label_event_id`, `target_key`, `label_family`
* `observed_time` (and optionally `effective_time`)
* `type = label_written | label_corrected`
  No label history dumps. No “resolved label state” as if it were truth.

### Critical pin

**Non-correctness-critical.** If S8 is down, LS truth still works; OFS/MF can still operate by reading LS directly. 

### Banned behaviors

* ❌ Treating notifications as the label truth source (learning must read labels from LS as-of). 
* ❌ Blocking label writes on notification emission failure.

---

## P-P1 — Policy revision takes effect

**Path:** `policy input → S2 → {S1,S3,S4,S6,S7}` (+ possible recompute in S6/S7)

### What this path exists to do

Make LS explainable and drift-resistant by ensuring:

* policy/config changes are **versioned artifacts**,
* runtime components **report which policy rev they used**, and
* policy changes don’t create “mystery behavior.”  

This is a platform-wide pin (not LS-only):

* policy configs are promoted like code; activation is governed; and components cite `policy_rev`.  

### What counts as LS “policy” (one bundle, multiple sub-policies)

At minimum LS policy includes:

* **Surface policy** (S1): required params (e.g., as-of required), limits, endpoint enablement
* **Target policy** (S3): what event/entity/flow targets mean; join key rules; ContextPins scoping
* **Idempotency policy** (S4): dedupe identity rules; conflict handling
* **Resolution policy** (S6/S7): conflict posture + as-of resolution rules + redaction rules

### Step-by-step behavior

1. A new policy bundle (new rev) is introduced via the config/promotion lane (propose → validate → activate).  
2. **S2** becomes authoritative for “active LS policy rev” and distributes it internally:

   * `S2 → S1` surface gating
   * `S2 → S3` target canonicalization rules
   * `S2 → S4` idempotency rules
   * `S2 → S6/S7` view + bulk semantics rules
3. **S6/S7 may recompute derived artifacts** if needed (e.g., conflict posture changes), but **S5 ledger history is never rewritten** (policy affects interpretation, not truth storage).  

### Governance/observability expectations

Policy activation should produce an **auditable governance fact** (“policy rev X became active”), consistent with the platform’s “changes are facts” baseline.  

### Environment ladder constraint

Local/dev/prod may differ in *strictness* and approval gates, but **must not fork semantics**:

* same mechanism exists in all envs,
* same “meaning of LABEL AS-OF / BACKFILL / ACTIVE,” etc.

### Banned behaviors

* ❌ “Prod-only policy behavior” implemented as code branches (violates the ladder). 
* ❌ Policy changes silently affecting outcomes without emitting governance facts / without being attributable.

---

### If you want the next illumination step

The highest-leverage “next pin” for preventing downstream drift is to open **S3 Target Canonicalizer** one notch and **lock the TargetKey shapes + ContextPins scoping rule**, because that single definition underlies **writes (IJ-W2), reads (IJ-R1), and bulk slices (P-X1)**.

---

Yep — here are the **production internal cycles** inside LS, now illuminated as *real loops* (still keeping S1–S8 opaque). I’m going to be explicit about **triggers, the “lap,” invariants, and what’s banned**, so we can’t drift later.

---

## L-C1 Read-after-write coherence loop

**Ledger drives views (Case UX + correctness)**

**Trigger:** `P-W1` commits a **new** label event (`APPENDED`) into **S5** (truth ledger).  

**Loop lap (what happens next):**

1. `S5 APPENDED(label_event)`
2. `IJ-D1: S5 → S6` sends a minimal “ledger delta” (pointer-like) to invalidate/update derived views.
3. Subsequent reads (`P-R1` timeline, `P-R2` label_as_of) go through S6 and **must reflect the ledger** (either because the view updated, or because S6 falls back to reading S5). 

**Authoritative correctness guarantees:**

* **Truth source is always S5**; S6 is derived and must be rebuildable from S5. 
* **Read-your-writes (interactive guarantee):** after LS returns `ACCEPTED(label_event_id)`, any subsequent read for that same `TargetKey` must be able to observe that event (timeline/current/as-of-now). This is required for Case UX sanity.
* **Leakage safety rule:** a read with `observed_as_of = T` must **never** include events whose `observed_time > T` — even if they were just written. (Stale-older is acceptable; stale-newer is not.)

**Failure modes & recovery (still within the loop):**

* If `S5→S6` delta delivery fails: S6 must still return correct answers by consulting S5 (slower, but correct).
* If S6 cache is stale: it must not leak future knowledge; worst case it returns older truth until refreshed.

**Banned drift:**

* ❌ “If S6 didn’t receive the delta, the event doesn’t exist.” (Makes S6 a second truth.)
* ❌ “As-of defaults to now silently.” (Breaks leakage discipline.)

---

## L-C2 Export freshness loop

**Ledger drives bulk slices (OFS/MF consumption)**

**Trigger:** `P-W1` commits `APPENDED` into S5. 

**Loop lap:**

1. `S5 APPENDED(label_event)`
2. `IJ-D2: S5 → S7` sends a minimal “slice delta” (pointer-like) to invalidate/update export indices and cached slice helpers.
3. Next bulk slice request `P-X1` (`bulk label_as_of`) uses S7, which must produce the same semantics as single reads.

**Authoritative semantics (the important bit):**

* Bulk slices are **basis-driven**: they are computed for a declared `observed_as_of` boundary (and any effective-time posture).
* Therefore, a newly appended label event only “belongs” in a slice if `observed_time <= observed_as_of`. If the slice boundary is earlier, the new event must not appear even though the system knows it now.
* If S7 emits **by-ref slice artifacts + digests**, they are **immutable**. New truth produces **new** slice artifacts; it never mutates old ones (so DatasetManifests remain reproducible).

**Failure modes & recovery:**

* If S7’s derived indexes fall behind, S7 must still be able to serve correct slices by reading from S5 (slower) and then repairing/invalidation (ties to L-C5).
* If a requested target set is huge, S7 must switch to by-ref/paged delivery but **not change meaning**.

**Banned drift:**

* ❌ “Give me the latest labels” bulk endpoint without explicit basis.
* ❌ Updating an existing slice artifact in-place (breaks reproducibility).

---

## L-C3 Notification retry loop

**Optional outbox → IG/control-bus emission (non-blocking)**

This loop exists only if you enable “optional label events → `fp.bus.control.v1`.”

**Trigger:** `S5 APPENDED(label_event)`.

**Loop lap:**

1. `IJ-N1: S5 → S8` enqueue an **outbox entry** (pointer-like: `label_event_id`, `target_key`, `observed_time`, type = written/corrected).
2. `IJ-N2: S8 → IG → fp.bus.control.v1` attempts to emit.
3. If emit fails, S8 retries until success (or until policy says to dead-letter), **idempotently**.

**Authoritative rules:**

* **Non-blocking:** notification failure must not fail the label write. Notifications are hints, not truth.
* **Idempotent emission:** the same outbox entry must map to the same emitted event identity; duplicates on the bus are acceptable (consumers treat as notifications).
* **Never a truth channel:** any consumer who cares about label truth must read LS (as-of), not trust control events.

**Banned drift:**

* ❌ Downstream automation treating control events as authoritative labels.
* ❌ “Emit full label state/timeline” on the bus (pointer-only).

---

## L-C4 Policy-change recomputation loop

**policy_rev changes → derived interpretation/slices recompute (ledger unchanged)**

This loop is the “no silent change” guardrail: policy is versioned, auditable, and components report the policy rev they used.

**Trigger:** a new `ls_policy_rev` becomes **ACTIVE** (governance fact should exist).

**Loop lap:**

1. `policy_rev activated`
2. `S2` loads the new PolicyBundle and distributes it internally:

   * `IJ-P1: S2→S1` surface gating (required params, endpoint enablement, limits)
   * `IJ-P2: S2→S3` target/join-key rules (canonicalization)
   * `IJ-P3: S2→S4` idempotency rules
   * `IJ-P4: S2→S6/S7` resolution + bulk parity rules
3. `S6/S7` recompute/invalidate derived structures **keyed by policy_rev** (eagerly or lazily).

**Authoritative rules:**

* **Ledger S5 is never rewritten** by policy change. Policy only changes interpretation (S6/S7), never truth history.
* **Requests execute under one policy_rev** (no mid-flight policy mixing).
* **Offline reproducibility:** OFS/MF must record the `ls_policy_rev` used alongside as-of boundary and replay basis (so training can be reproduced later).

**Banned drift:**

* ❌ Environment-specific semantic forks (“prod interprets labels differently”). The ladder forbids this; only strictness/envelope can differ.
* ❌ Policy change that affects outcomes without emitting an auditable governance fact.

---

## L-C5 Repair/reconciliation loop

**Derived lag detection → reread S5 → repair (production hardening)**

This is the “self-healing” loop that makes derived layers safe to operate without elevating them to truth. It’s directly aligned with your platform truth map: authoritative timelines in DB, everything else rebuildable.

**Trigger:** periodic check OR detection of inconsistency/lag:

* S6 view cache behind
* S7 export/index behind
* S8 outbox stuck
* or a “parity check” failure (e.g., digest mismatch)

**Loop lap:**

1. Detect lag/inconsistency (e.g., S6/S7 last_applied_token < S5 ledger head token).
2. Reread authoritative truth from S5 (bounded by tokens).
3. Repair:

   * rebuild/update view state (S6)
   * rebuild/update export indexes (S7)
   * re-drive stuck outbox emissions (S8)
4. Emit observability signals (lag metrics, repair counts) and, where appropriate, governance facts for significant ops actions (esp. if repair implies a backfill-like rebuild of derived artifacts).

**Authoritative rules:**

* Repairs must **never mutate S5 history**.
* Repairs may produce **new derived artifacts** (new refs/digests) but must not overwrite referenced artifacts.
* Repairs must preserve the **as-of leakage rule** (never leak events beyond `observed_as_of`).

**Banned drift:**

* ❌ “Repair” that deletes or rewrites label ledger entries.
* ❌ “Repair” that silently changes previously published digest’d artifacts.

---

## One-line internal loop pin (so we stay aligned as we go deeper)

**S5 is the only truth spine; S6/S7 are derived and rebuildable; S8 is optional; every loop must preserve explicit as-of semantics and must not fork meaning across environments.**

---

Yep — we *do* need an explicit “**non-joins / forbidden edges**” list for LS, because most drift happens via **shortcuts** (“we’ll just read LS here” / “we’ll just write labels there” / “we’ll just emit state on the bus”). I’m going to declare these as **banned** unless we later *explicitly* upgrade them as a major design decision.

I’ll split them into **platform boundary non-joins** and **internal LS non-joins**.

---

## A) Platform boundary non-joins (banned edges around LS)

### NJ-B1 — Hot path must not read LS

**DF/OFP/IEG (or any decision-time component) must not query LS as an online dependency.**
LS is the *lagged truth plane*; RTDL produces evidence, not truth labels.

### NJ-B2 — RTDL components must not write labels

**DF/AL/DLA must never write “truth labels” into LS.**
Labels become truth only when written as **label assertions** (investigators + delayed external outcomes). System outputs stay **evidence** unless policy explicitly promotes them via an authorized label writer.

### NJ-B3 — Learning must not infer labels from evidence

**OFS/MF must not derive labels from outcomes/heuristics/“what the system decided.”**
Learning consumes labels only from **Label Store timelines**.

### NJ-B4 — Training joins must not use “current labels” implicitly

**Any training/eval dataset build must not join labels using “whatever LS says now” unless explicitly declared.**
Training joins are “as-of” by rule; late labels are normal; as-of makes them safe.

### NJ-B5 — Control-bus label events must not be treated as label truth

If LS emits optional label events to `fp.bus.control.v1`, **no consumer may treat those events as authoritative label state**. They are notifications/pointers only.

### NJ-B6 — Case must not execute side-effects directly (related loop guard)

Manual interventions (block/release/notify) must not bypass AL; they must be ActionIntents executed by Actions Layer (auditability + dedupe).

### NJ-B7 — Backfill must not mutate LS truth

Backfill can rebuild **derived artifacts** (datasets/manifests/indexes), but **must not rewrite label_store timelines**. Truth evolves append-only.

### NJ-B8 — Unbounded “scan all labels” consumption is banned

Offline consumers must not “grab all labels” by scanning LS. They must supply an explicit target universe (or by-ref target_set). This is required for reproducibility discipline (manifests + basis).

### NJ-B9 — Engine truth_products must not leak into hot path

Engine “truth_products” can support offline eval/training/test harnesses, but **must not** become hot-path inputs. If used as labels, they must be written into LS as label assertions (so LS remains the single truth source for learning).

---

## B) Internal LS non-joins (banned shortcuts inside the vertex)

### NJ-I1 — No S1 bypass of governance

**S1 must not route writes directly to S3/S4/S5 without passing S2.**
Writer authority + required-field enforcement is not optional and must exist even in local.

### NJ-I2 — No direct writes to the ledger from edge/canonicalizer

**S1 and S3 must never append to S5.**
All writes must go through S4 (idempotency/dedupe) and then S5 (truth).

### NJ-I3 — S6/S7 are read/derived only

**S6 (views) and S7 (exports) must never write or “correct” S5.**
They may cache/materialize, but must be rebuildable from S5 and must not become second truth stores.

### NJ-I4 — Policy changes must not rewrite truth

**S2 policy activation must not mutate S5 history.**
Policy may change interpretation (S6/S7) but not ledger truth.

### NJ-I5 — Derived coherence signals must not be correctness-critical

**Missing IJ-D1/IJ-D2 deltas must not imply “truth doesn’t exist.”**
Views/slices can lag; correctness comes from recomputing from S5.

### NJ-I6 — Notifications must not block writes

**S8 notification/outbox failures must not fail IJ-W* write commits.**
Optional label events are allowed, not required for correctness.

### NJ-I7 — Bulk semantics must not diverge from single-read semantics

**S7 bulk “label_as_of” must not implement different resolution rules than S6.**
If bulk differs, training drift is guaranteed. (So either share S6 logic/kernel or treat it as the same authority.)

### NJ-I8 — “As-of” must not default silently inside LS

Within LS, any path that claims leakage-safety must not treat `as_of` as optional / default-to-now. The basis must be explicit and echoed back (so manifests can pin it).

---

## C) Environment ladder non-join (meta rule)

**No environment-specific semantic forks are allowed** (e.g., “local bypasses S2” or “dev allows missing as-of”). Local/dev/prod can differ in strictness/scale/retention, but the *rails* and meanings must be identical.

---

Here’s the **design checkpoint** for the Label Store (LS) vertex as we’ve established it—outer network + inner network (Level-1) + the internal joins/paths/loops we illuminated—so we have a single, drift-proof mental model before going deeper. The platform pins that constrain everything come from your blueprint + deployment notes.  

---

## 1) LS’s role in the platform graph (outer network truth)

### What LS *is*

* **Label truth authority**: labels become truth **only when written to LS**, as **append-only timelines** with **effective_time** and **observed_time**, enabling leakage-safe **as-of** reads. 
* **Lagged truth plane**, not hot path: RTDL emits **evidence** (decisions/intents/outcomes), and truth labels exist only via LS writes. 
* **Always-on control-plane service** with an authoritative `label_store` DB. 

### What LS *is not*

* Not an online decision dependency (no DF/OFP/IEG “read LS to decide”).
* Not a place where “evidence automatically becomes truth.”
* Not a second truth channel via bus emissions.

---

## 2) Outer joins / paths / loops we pinned

### Direct joins touching LS

**A1 (J13)** Case Workbench → LS (WRITE label assertions) 
**A2** LS → Case Workbench (READ timelines / as-of / current) 
**A3** External adjudication feeds → LS (WRITE label assertions; late truth) 
**A4 (J14)** LS(as-of) + EB/Archive(replay) → Offline Shadow (READ basis-driven labels) 
**A5 (optional)** LS → IG → `fp.bus.control.v1` (label_written/label_corrected **notifications**) 

Downstream learning chain (LS is upstream truth source for it):
**B6 (J15)** OFS → MF via **DatasetManifest** (pins replay basis + as-of boundary + join keys + feature versions + digests) 
**B7 (J16)** MF → Registry (bundles + evidence) 
**B8** Registry → DF (deterministic ACTIVE resolution; no “latest”) 

### Production paths including LS

**C9/P1** Evidence → Case → LS (truth created only via LS write) 
**C10/P2** LS+EB/Archive → OFS → MF → Registry → DF (the improvement pipeline) 
**C11/P3** Late truth (adjudication) → LS → OFS → MF → Registry → DF 
**C12/P4 (optional)** LS notifications → scheduler triggers OFS/MF → Registry updates → DF changes → new evidence → new labels 

### Platform loops including LS

**D13/L1** Core improvement loop: DF/AL evidence → DLA → Case → LS → OFS → MF → Registry → DF 
**D14/L2** Human correction loop: Case ↔ LS (append-only corrections; as-of makes “knew then” vs “know now” possible) 
**D15/L3** Manual action loop: Case → AL → evidence → Case → LS 
**D16/L4 (optional)** Ops automation loop: LS notify → jobs/backfills → new manifests/bundles → DF → new evidence → new labels 

---

## 3) Environment ladder overlay (how deployment can vary without semantic drift)

Pinned rule: **same graph + same rails everywhere; only operational envelope differs** (scale/retention/security/HA/obs). 

So we explicitly treated as “profile knobs” (envelope-only):

* strictness of authn/authz for label writes/reads
* rate limits, paging thresholds, “inline vs by-ref slice”
* HA/backup/restore hardening
* observability depth (but correlation keys still exist everywhere)

And we explicitly banned “local shortcuts” that change meaning (e.g., local bypasses as-of requirements).

---

## 4) First internal layer we illuminated (LS Level-1 subnetworks, still opaque)

We decomposed LS into these internal boxes:

* **S1 Edge** (public write/read/bulk surfaces)
* **S2 Governance & Policy** (authority matrix + required fields + policy_rev)
* **S3 Target Canonicalizer** (event/entity/flow → canonical TargetKey + ContextPins scoping)
* **S4 Write Determinism** (idempotency + duplicate control)
* **S5 Timeline Ledger Core** (append-only truth spine)
* **S6 Resolver & Views** (timeline / as-of / current / conflict view)
* **S7 Export & Slices** (bulk as-of slices; manifest-grade outputs)
* **S8 Notifications** (optional outbox → IG/control bus)

**Truth law inside LS:** **S5 is the only truth**; S6/S7 are derived/rebuildable; S8 is optional.

---

## 5) Internal joins we explicitly pinned (between opaque subnetworks)

### Write-chain joins (truth creation)

**IJ-W1** S1→S2 admit write (authority + required fields)
**IJ-W2** S2→S3 canonicalize target (fail closed on ambiguity)
**IJ-W3** S3→S4 determinize write (idempotency required; conflict on key mismatch)
**IJ-W4** S4→S5 append truth (ledger enforces uniqueness; append-only)
**IJ-W5** S5→S1 receipt (ACCEPTED/DUPLICATE/REJECTED + TargetKey + policy_rev)

Key write pins we declared:

* missing effective_time/observed_time ⇒ reject
* idempotency handle required (no timeline pollution under retries)
* S5 is final truth arbiter (S4 can precheck, S5 enforces)

### Read-chain joins (truth consumption)

**IJ-R1** S1→S3 canonicalize target
**IJ-R2** S3→S6 request view (timeline / resolved)
**IJ-R3** S6↔S5 ledger fetch + interpret (S6 never fabricates; ordering deterministic)
**IJ-R4** S6→S1 response that **echoes basis** (observed_as_of + effective_at + policy_rev)

Key read pins we declared:

* leakage-safe reads require explicit `observed_as_of` (no hidden “now”)
* resolved view uses **two-time basis**: knowledge cut (observed_as_of) + world application (effective_at, default = observed_as_of)
* conflicts must surface explicitly (no silent precedence)

### Bulk/export joins (manifest-grade slices)

**IJ-X1** S1→S3 canonicalize bulk target universe (must be explicit list or by-ref target_set)
**IJ-X2** S3→S7 bulk slice request (basis required; stable ordering)
**IJ-X3** S7↔S5 bulk ledger fetch (deterministic)
**IJ-X4** S7↔S6 parity with single-read resolver semantics (bulk must match single)
**IJ-X5** S7→S1 return pages or by-ref slice + digest + basis

Key bulk pins:

* no unbounded “scan everything”
* slices must be reproducible (refs + digests + basis echoed)

### Derived coherence + notifications

**IJ-D1** S5→S6 view invalidation/update (optimization; never correctness-critical)
**IJ-D2** S5→S7 export/index invalidation/update (optimization; immutable digest’d artifacts)
**IJ-N1** S5→S8 enqueue optional notification (pointer-like; non-blocking)
**IJ-N2** S8→IG/control bus emit/retry idempotently (never treated as truth)

### Policy distribution (policy_rev spine)

**IJ-P1** S2→S1 surface gating rules
**IJ-P2** S2→S3 target/key rules (joinability definition)
**IJ-P3** S2→S4 idempotency rules
**IJ-P4** S2→S6/S7 resolution/bulk parity/conflict posture rules

We pinned: policy is versioned (`ls_policy_rev`), immutable bundles; attribution is mandatory; policy changes don’t rewrite S5.

---

## 6) Internal production paths and internal cycles we illuminated

### Internal paths

* **P-W1** write new assertion happy path
* **P-W2** retry/duplicate (idempotent)
* **P-W3** rejected writes (authority/shape/target invalid)
* **P-R1** timeline read
* **P-R2** label_as_of(T) resolved read
* **P-X1** bulk label_as_of slice (OFS scale)
* **P-D1** coherence refresh triggers (S5→S6/S7)
* **P-N1** optional notification emission
* **P-P1** policy rev activation and internal propagation

### Internal loops/cycles

* **L-C1** ledger → views coherence (read-after-write)
* **L-C2** ledger → bulk/export freshness
* **L-C3** notification retry loop (optional, non-blocking)
* **L-C4** policy-change recomputation loop (derived changes only)
* **L-C5** repair/reconciliation loop (derived lag detection → reread S5 → repair; never mutate truth)

---

## 7) Non-joins we declared to prevent drift (forbidden shortcuts)

We explicitly banned (unless later promoted as major design changes):

* hot path reading LS (DF/OFP/IEG don’t depend on LS online) 
* RTDL writing “truth labels” directly (DF/AL/DLA produce evidence only) 
* training/eval joining labels without explicit as-of boundary 
* treating control-bus label notifications as truth 
* backfill mutating LS truth timelines 
* internal bypasses: S1 bypassing S2/S4, S6/S7 writing to S5, policy changes rewriting S5

---

## 8) What’s intentionally still “open” (safe to decide next)

These are the *remaining big pins* we have not yet locked, and they’re the right next “enter the vertex” targets:

1. **TargetKey model for event/entity/flow** (exact key shapes + ContextPins scoping)
2. **Conflict posture** for resolved views (CONFLICT vs precedence rules)
3. **Idempotency recipe** (how handles are formed/required across Case vs adjudication feeds)
4. **Entitlements/redaction rules** for evidence refs in reads/bulk slices
5. **Policy bundle schema** (what exactly is in ls_policy_rev, and how it’s promoted)

---

## Drift checklist for the next stage

When we go deeper, we keep these as the “never violate” guardrails:

* S5 is the only truth; everything else derived/rebuildable
* dual-time (effective/observed) is mandatory
* as-of requires explicit boundary; basis must be echoed
* append-only corrections; no mutation
* idempotent writes; duplicates don’t pollute timelines
* environment ladder changes envelope only, not meaning

---

Yep — this is exactly the right moment to **pin the deployment + environment-ladder posture for LS’s internal network (S1–S8)** so Codex can implement without “works local / breaks prod” drift.

Everything below is **authoritative design guidance**, aligned to your ladder pin: **same graph + same rails/join semantics across local/dev/prod; only the operational envelope differs**.  

---

## 1) Deployment-unit stance for LS internals (S1–S8)

### D1. LS is **one deployment unit** in v0: an always-on service

* LS is a pinned always-on, control-plane service with authoritative DB `label_store`.  
* **Authoritative call:** In v0, **S1–S7 ship in the same LS service process** (modules/libraries internally). Keep the vertex as *one* runtime unit; don’t prematurely split. This avoids drift in TargetKey semantics / as-of semantics across “microservices”.

### D2. S8 (Notifications/outbox) can be *either* in-process or a sidecar — but remains “part of LS”

* The platform allows optional label events on `fp.bus.control.v1`. 
* **Authoritative call:** model S8 as an **outbox worker** that can be:

  * a background loop inside the LS process **or**
  * a separate worker reading the outbox table
    …but *either way* it is logically LS and must be non-blocking for writes.

---

## 2) Persistence truth vs derived truth (what must be durable)

### D3. Only S5 is primary truth; S6/S7 are derived and rebuildable

* `label_store` DB holds **append-only label truth timelines**. 
* **Authoritative call:** anything S6/S7 persist (materialized views, indexes, cached slices) is explicitly **derived**, and must be rebuildable from S5.

### D4. Backfill may regenerate derived LS artifacts, but cannot mutate label truth

* “Cannot be backfilled as truth mutation” explicitly includes **label store timelines**. 
* Therefore: restore/backups matter for LS in dev/prod; you can’t “just backfill labels”.

### D5. Derived rebuilds use **monotonic progress tokens**

* Mirror the platform’s monotonic progress principle (“watermarks don’t lie”) by giving LS a monotonic ledger position token (e.g., event sequence) that S6/S7 use to track “applied up to X”.  
* This makes L-C1/L-C2/L-C5 operationally real (invalidate/repair without “second truth”).

---

## 3) Environment ladder: what must never change vs what may change

### D6. Non-drift invariants (must be identical in local/dev/prod)

* Same rails/join semantics, including: **append-only + supersedes**, **idempotency**, **as-of semantics**, **by-ref posture**, and the meaning of the words “LABEL AS-OF” and “BACKFILL”.  
* Dataset builds must remain reproducible: manifests pin basis + as-of + join keys + feature versions.  

### D7. Allowed envelope knobs (can differ per environment)

Per the ladder: scale, retention/archive, security strictness, reliability posture, observability depth — **without changing meaning**.  

For LS specifically, the knobs you *will* tune by profile:

* request limits (max payload, max targets, page size)
* caching/materialization aggressiveness (S6/S7)
* authn/authz strictness and approval gates for label writers
* outbox emission enabled/disabled (still optional), retry policy

---

## 4) Config & promotion posture for LS (so “prod behavior” is explainable)

### D8. Separate **policy config** from **wiring config**

* Wiring config: endpoints, timeouts, resource limits.
* Policy config: authority matrix, required fields, target semantics, idempotency semantics, resolution/conflict posture. 

### D9. Policy is a **versioned artifact**; LS must report `policy_rev`

* Policy revisions are promoted/approved like code; runtime components always report which policy rev they’re using.  
* **Authoritative call for LS:** every write receipt and every resolved/bulk response must echo `ls_policy_rev` (and record it with the ledger event provenance), so you can always answer “what rules were in force?”

### D10. Promotions are the three pinned lanes

* code artifacts (build once/run anywhere)
* policy/profile revisions (versioned + governance facts)
* bundles (MF publishes; Registry activates)  

---

## 5) Observability + governance facts (deployment-grade)

### D11. LS must emit the observability baseline like everything else

Minimum: correlation keys, traces/metrics/logs, golden signals, and “changes are facts.” 

**LS-specific signals to carry from day one (per env, different thresholds):**

* write rates, reject rates (by reason), duplicate rates
* read rates by mode (timeline/as-of/bulk)
* “as-of missing” rejections (should be near-zero in OFS/MF)
* derived lag (S6/S7 last_applied_token vs ledger head)
* outbox backlog + retry counts (if S8 enabled)

### D12. Outcome-affecting changes emit governance facts

Policy rev activation, backfill runs, retention policy changes, etc. must be durable facts, not just logs.  

---

## 6) Local/dev/prod “production-shaped” stance (what Codex should assume)

### D13. Use the reference local stack so semantics match prod

* Kafka-ish bus semantics, S3-ish object store, Postgres for authoritative timelines, OTLP pipeline locally.  
* This is explicitly recommended so integration tests are real without vendor lock-in. 

### D14. “Golden flow” must include LS + offline chain at least once

Your deployment notes explicitly include: Case → Label Store and Offline Shadow → Model Factory → Registry → ACTIVE resolution as part of the end-to-end integration flow.  

**Authoritative call:** Codex should treat this as a non-negotiable integration gate for LS implementation.

---

## 7) Two explicit “don’t let Codex drift” pins for LS deployment

1. **No env-specific semantic forks** (“local bypasses policy/as-of/idempotency”) — banned by ladder. 
2. **No “we can backfill labels” escape hatch** — label timelines are truth and must be protected via DB durability/restore discipline. 

---

Yes — illumination should **not** change the network; it should only reveal the machinery that satisfies the already-pinned joins/paths/loops. If we discover a mismatch, we treat it as **a clarification/pin**, not a redesign of edges.

## Nodes (LS Level-1 subnetworks)

* **S1** Edge (public write/read/bulk surfaces)
* **S2** Governance & Policy (authority matrix + policy_rev + required fields)
* **S3** Target Canonicalizer (event/entity/flow → canonical TargetKey + ContextPins scoping)
* **S4** Write Determinism (idempotency + duplicate control)
* **S5** Timeline Ledger Core (append-only truth spine)
* **S6** Resolver & Views (timeline / label_as_of / current / conflict)
* **S7** Export & Slices (bulk as-of slices; manifest-grade outputs)
* **S8** Notifications (optional outbox → IG/control bus)

## Recommended illumination order (v0, drift-minimizing)

1. **S3 Target Canonicalizer**
   Biggest cross-cutting drift vector: every write/read/bulk path depends on TargetKey + scoping.
2. **S6 Resolver & Views**
   Pins leakage-safe “as-of” semantics + conflict posture (critical for OFS/MF correctness).
3. **S4 Write Determinism**
   Locks idempotency and duplicate/conflict behaviour (at-least-once reality).
4. **S5 Timeline Ledger Core**
   Truth spine: append semantics, ordering tokens, immutability, durability expectations.
5. **S2 Governance & Policy**
   Authority matrix + policy_rev distribution (easier once TargetKey + resolver semantics are pinned).
6. **S7 Export & Slices**
   Bulk delivery mechanics + digests/refs parity with S6; depends on S3+S6+S5.
7. **S1 Edge**
   Thin by design: endpoint shapes, parameter gating, auth plumbing—best finalized after core semantics are fixed.
8. **S8 Notifications** (optional)
   Outbox + retry semantics; easiest last since it must not affect correctness.

---

Below is the **authoritative v0 design** for **S3: Target Canonicalizer** — the machinery that makes **event/entity/flow** labels **joinable, deterministic, and drift-proof** across **writes (IJ-W2)**, **reads (IJ-R1)**, and **bulk slices (IJ-X1)**.

This is grounded in your platform pins:

* labels target **subject (event/entity/flow)** and carry **effective_time + observed_time** 
* **ContextPins** are the canonical join pins `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` for anything that claims run/world joinability 
* the bus boundary uses a canonical envelope with required `{event_id, event_type, ts_utc, manifest_fingerprint}` and optional pins 

---

# S3 Charter

**S3 is the *only* authority inside LS for answering:**

> “What *exactly* is this label attached to, and under what scope can it be joined?”

If S3 is wrong or ambiguous, **everything downstream drifts** (Case UX, OFS joins, MF datasets, evaluation).

**S3 does not:**

* validate that the target *exists* in EB/DLA (no referential integrity checks here)
* interpret time semantics (that’s S6)
* decide write authority (that’s S2)
* compute idempotency/fingerprints (that’s S4, but S3 provides canonical inputs)

---

# S3 Inputs and Outputs

## Inputs (what S3 receives)

S3 is invoked from three places:

1. **IJ-W2 (write path):** `S2 → S3`

   * Admitted LabelAssertion (post-policy admission) + `ls_policy_rev` + any “target rules” (TargetPolicy).

2. **IJ-R1 (read path):** `S1 → S3`

   * Read intent for `timeline / label_as_of / current`, including a raw subject and (for as-of) basis params.

3. **IJ-X1 (bulk path):** `S1 → S3`

   * Bulk target universe: explicit list or by-ref target_set + declared basis.

## Outputs (what S3 returns)

S3 always returns one of:

* `CanonicalTargetResult{ target_key, scope, key_fingerprint, canonical_display_ref }`
* or `REJECT{ reason_code }` where reason is deterministic (`AMBIGUOUS_TARGET`, `MISSING_PINS`, `INVALID_ID`, …)

`key_fingerprint` exists because everything else (S4 dedupe, S7 stable ordering, slice digests) must be deterministic.

---

# The TargetKey model (v0, designer-authoritative)

## TargetKey (structured)

```
TargetKey v0 =
  key_version: "ls.targetkey.v0"
  scope: ContextPins
  target_type: EVENT | ENTITY | FLOW
  target_body:
    EVENT: { event_id }
    ENTITY: { entity_type, entity_id }
    FLOW: { flow_type, flow_id }
```

### Why this shape

* It’s minimal, stable, and unambiguous.
* It lines up with the platform’s pinned subject types (event/entity/flow). 
* It uses ContextPins as the join scope anchor. 

---

# Scope model (ContextPins rules)

**Authoritative v0 rule:**

> **All LS labels are assumed joinable** for learning/replay unless explicitly declared otherwise.
> Therefore, **ContextPins are required on all label assertions and all canonical TargetKeys**.

**ContextPins = `{manifest_fingerprint, parameter_hash, scenario_id, run_id}`** 

### Enforcement

* If any pin is missing → `REJECT(MISSING_PINS)`
* If pins exist but fail basic format validation → `REJECT(INVALID_PINS)`
* S3 does **not** try to “fill missing pins” from elsewhere (no hidden joinability).

**Note:** This rule is intentionally strict because training joins are “as-of by rule” and must be reproducible against pinned history + pinned scope. 

---

# Target types in detail

## 1) EVENT targets

**Meaning:** label attached to a single admitted event identity.

**Required fields:**

* `event_id` (from canonical envelope identity) 
* `ContextPins` (LS join scope)

**Canonicalization rules:**

* normalize `event_id` (trim whitespace; preserve case only if the format is case-sensitive; default to lowercase for hex ids)
* validate it matches allowable formats (uuid/hex/string per envelope definition) 
* produce:

  * `target_type=EVENT`
  * `target_body={event_id=<canon>}`

**Why event_id is acceptable:** the platform already pins `event_id` as the stable dedupe identity at the bus boundary. 

---

## 2) ENTITY targets

**Meaning:** label attached to a real-world (or closed-world) entity that appears in traffic and/or in entity graph/feature plane.

**Required fields:**

* `entity_type` (small controlled vocabulary)
* `entity_id` (string, normalized)
* `ContextPins` (LS join scope)

**Canonicalization rules:**

* `entity_type` normalized to an enum (e.g., `ACCOUNT`, `CARD`, `CUSTOMER`, `MERCHANT`, …)
  *This list is policy-controlled (TargetPolicy) so it can evolve without breaking code.*
* `entity_id` canonicalization:

  * trim
  * enforce no whitespace/control chars
  * normalize case depending on type rules (default: lowercase)

**Output:**

* `target_type=ENTITY`
* `target_body={entity_type, entity_id}`

---

## 3) FLOW targets

**Meaning:** label attached to a multi-event “thing” that is neither a single event nor a stable entity — a *process instance*.

**Authoritative v0 stance (minimal but realistic):**
Flow exists to support labeling of:

* **decision/request flows** (a single decision point with evidence spread across multiple events)
* **case flows** (a case lifecycle)

So v0 supports:

* `flow_type = DECISION`
* `flow_type = CASE`

**Required fields:**

* `flow_type` enum
* `flow_id`
* `ContextPins`

**Canonicalization rules:**

* `flow_id` normalized as string, trimmed, stable format checks
* reject unknown flow_type (fail closed)

**Output:**

* `target_type=FLOW`
* `target_body={flow_type, flow_id}`

---

# S3 Internal machinery (inside the node)

Think of S3 as a deterministic pipeline with strict “no guessing” rules:

## S3.1 Subject Intake Adapter

Accepts subject in one of these shapes (write/read/bulk):

* structured: `{target_type, ...typed fields...}`
* or legacy/raw: `{event_id=...}` / `{entity_ref=...}` / `{flow_ref=...}`
  *(Only if TargetPolicy says it’s permitted; otherwise reject.)*

## S3.2 Type Router

Determines target_type:

* EVENT if `event_id` provided
* ENTITY if `entity_type/entity_id` provided
* FLOW if `flow_type/flow_id` provided
* else reject (`MISSING_TARGET_FIELDS`)

## S3.3 ContextPins Validator

Validates ContextPins present + well-formed (hex lengths etc.).
ContextPins model is pinned at platform level. 

## S3.4 Identifier Normalizers

Per target_type:

* normalize event_id (uuid/hex/string) 
* normalize entity_id
* normalize flow_id
* enforce “no ambiguous formats”

## S3.5 TargetKey Builder

Builds `TargetKey v0` exactly (no alternative layouts) and attaches:

* `key_version`
* `scope=ContextPins`
* typed body

## S3.6 Key Fingerprinter

Computes:

* `key_fingerprint = H(canonical_json(TargetKey))`
* and a **stable ordering key** (used for bulk target sets and slice digests)

**Determinism rule:** canonical JSON must be stable (sorted keys, stable encoding, no float weirdness).

## S3.7 Failure Taxonomy (fail closed)

S3 rejects instead of guessing:

* `AMBIGUOUS_TARGET` (multiple plausible interpretations)
* `INVALID_TARGET_TYPE`
* `INVALID_ID_FORMAT`
* `MISSING_PINS / INVALID_PINS`

---

# How S3 interacts with other LS nodes (so we don’t drift)

## With S2 (Governance/Policy)

* S3 obeys **TargetPolicy** distributed by S2 (IJ-P2): what entity types exist, what flow types exist, whether legacy subject shapes are permitted.

## With S4 (Write Determinism)

* S4 treats `(TargetKey, ContextPins)` as canonical inputs to idempotency/dedupe identity.
* If S3 is stable, idempotency becomes stable.

## With S6/S7 (Views/Bulk)

* S6 and S7 must operate on canonical TargetKey only.
* Bulk parity depends on S3 producing the same canonical key for all callers.

---

# Explicit non-joins (inside S3)

To keep S3 pure and deterministic:

* **S3 must not call EB/DLA/Case DB** to “verify” targets exist.
* **S3 must not query other LS nodes** to infer missing pins or IDs.
* **S3 must not accept “partial scope”** (no “manifest only” joins) in v0.

If later you want weaker scoping for cross-world real prod, that’s a deliberate v1 design fork — not an implementation convenience.

---

# Acceptance checks for S3 (what “correct” means)

1. **Same input → same TargetKey + fingerprint** across retries and across envs.
2. **Ambiguity fails closed** (never guesses).
3. **ContextPins required** and preserved. 
4. **Bulk target universe ordering is stable** (slice digests reproducible). 
5. **Event targets align with envelope identity** (`event_id` as the stable handle). 

---

Below is the **authoritative v0 design** for **S6: Resolver & Views** — the machinery that turns the **append-only truth ledger (S5)** into the **timeline / as-of / current** read surfaces, *without ever becoming a second truth source*.

This is constrained by your platform pins:

* LS labels are **append-only timelines**; corrections are new assertions; labels carry **effective_time** and **observed_time**, enabling **as-of** reads. 
* “Time semantics never collapse” (domain vs observed/apply) — as-of is explicit. 
* Event identity is stable at the platform boundary (`event_id` in canonical envelope), which S6 can reference for EVENT-target labels. 

---

# S6 Charter

**S6 is the single interpreter for label truth.** It provides deterministic views over S5’s ledger events:

* `timeline(target[, family])`
* `label_as_of(target, observed_as_of[, effective_at][, family])`
* `current_label(target[, family])` (explicit “as-of now”, never implicitly used for evaluation)

**S6 does not:**

* write or mutate truth (never writes S5)
* “verify existence” of targets in EB/DLA (no cross-system lookups)
* invent missing times or pins (fail closed)

---

# S6 Inputs and Outputs

## Inputs S6 consumes

S6 receives a **ViewRequest** from S1→S3→S6 (IJ-R2) containing:

* `TargetKey` (+ ContextPins scope) from S3
* `view_kind`: `timeline` | `resolved`
* `label_family` filter (optional)
* **basis**:

  * `observed_as_of` (knowledge cut) — **required** for leakage-safe resolved views
  * `effective_at` (world-time application) — optional; default rules below
* caller entitlements (for redaction)
* `ls_policy_rev` / ResolutionPolicy (via S2 IJ-P4)

## Outputs S6 returns

S6 returns one of:

### TimelineView

* ordered label events (append-only)
* includes effective_time + observed_time + provenance
* evidence refs may be redacted based on entitlements

### ResolvedView

* basis echo: `observed_as_of`, `effective_at`, `ls_policy_rev`
* status: `LABEL(value)` | `UNKNOWN` | `CONFLICT`
* minimal explanation: winning event id (or conflict set)

---

# The Two-Time Resolution Basis (pinned)

S6 resolves labels using **two explicit clocks**:

1. **observed_as_of (knowledge cut)**
   “What did we know by time T?”
   Eligible events must satisfy: `observed_time <= observed_as_of`. 

2. **effective_at (world application)**
   “What truth applies at world time t?”
   Applicable events must satisfy: `effective_time <= effective_at`. 

### Default rule (authoritative v0)

For `label_as_of(target, observed_as_of)` **without** an explicit `effective_at`:

* **effective_at defaults to observed_as_of**.

Reason: it gives a simple, safe default for “what did we know then, about then,” while still allowing deliberate retroactive evaluation by passing `effective_at` explicitly.

---

# Core Resolver Algorithm (machinery, deterministic)

S6 resolves **per (TargetKey, label_family)** independently.

## Step 0 — Fetch truth from S5 (no shortcuts)

S6 asks S5 for ledger events for the target (and family if filtered). S5 is the only truth source.

## Step 1 — Apply knowledge cut

`E = { e | e.observed_time <= observed_as_of }`

If `E` is empty → `UNKNOWN`.

## Step 2 — Apply world-time applicability

`A = { e in E | e.effective_time <= effective_at }`

If `A` is empty → `UNKNOWN`.

## Step 3 — Choose the effective slice (temporal state)

Let `t* = max(e.effective_time for e in A)`
Let `C = { e in A | e.effective_time == t* }`

This is the **time-state** rule: at a given world time, the “current state” comes from the most recent effective_time not after that world time.

## Step 4 — Resolve conflicts within the slice

Now we only need to resolve among `C` (same effective_time). This is where corrections / disagreements show up.

S6 applies ResolutionPolicy in this order:

### 4A) Supersedes pruning (if present)

If events in `C` include `supersedes_event_id` links:

* remove any event that is (transitively) superseded by another event in `C`

### 4B) If exactly one candidate remains

Return that candidate as `LABEL(value)`.

### 4C) If multiple remain

This is a **true conflict at the same effective_time**. S6 must not hide it.

**Authoritative v0 default:** return `CONFLICT`, with:

* the set of candidate `label_event_id`s
* their values + provenance summary

**Optional via policy (explicit only):** a declared precedence rule may choose a winner (e.g., “adjudication feed overrides investigator” or vice versa). If precedence is used, S6 must:

* record in the response that precedence was applied
* include the losing candidates (at least IDs) so the conflict isn’t invisible

This keeps LS from quietly becoming a policy engine while still allowing production pragmatism when you *want* precedence.

---

# Timeline View Semantics (machinery)

Timeline is a **truth history view**, not a resolved state.

**Authoritative ordering (v0):** **ledger append order** (monotonic S5 position token / sequence).

* This reflects “what was asserted, when we learned it.”
* Each event still contains effective_time so consumers can re-sort for UI if they want.

S6 may support paging; paging tokens must be retry-safe and stable under at-least-once access.

---

# Redaction & Entitlements (machinery)

S6 is responsible for ensuring read outputs don’t silently change meaning.

**Rules:**

* If a caller isn’t allowed to see evidence refs, S6 returns `evidence_redacted=true` rather than omitting the field silently.
* Redaction is **view-level** (presentation), never truth mutation.

Policy-driven knobs (IJ-P4):

* which principals can see evidence refs
* whether provenance fields are partial or full

---

# Derived State & Coherence (how S6 stays fast without becoming truth)

S6 can keep derived state, but it must be **rebuildable from S5**.

## S6 internal derived stores (allowed)

* per `(TargetKey, family)` index of events keyed by effective_time
* optional “head summaries” (e.g., current_label as-of-now cache)
* progress token: `s6_last_applied_ledger_token`

## Coherence loop hooks (IJ-D1 / L-C1)

* On `S5 APPENDED`, S5 emits a minimal delta to S6 (event_id, target_key, times, etc.)
* S6 updates/invalidate caches accordingly
* If deltas are missed, S6 must detect lag (token mismatch) and repair by rereading from S5

**Hard rule:** S6 missing a delta must never imply “truth doesn’t exist.”

---

# Bulk parity (S6 ↔ S7)

To prevent training drift, S6 exposes a **Resolver Kernel**:

* `resolve(events[], observed_as_of, effective_at, policy) -> LABEL/UNKNOWN/CONFLICT`

S7 uses this same kernel for bulk slices (IJ-X4), guaranteeing:

> bulk `label_as_of` == single `label_as_of` for the same target and basis.

---

# S6 Non-joins (forbidden shortcuts)

* S6 must not write to S5 or “correct” ledger history.
* S6 must not default `observed_as_of` silently for leakage-safe reads.
* S6 must not resolve conflicts via hidden tie-breakers (like event_id sort) unless policy explicitly declares precedence.
* S6 must not call EB/DLA to “validate” targets (that would create cross-component coupling and drift).

---

# Acceptance checks for S6 (what “correct” means)

1. **As-of safety:** no result includes events with `observed_time > observed_as_of`. 
2. **Temporal correctness:** resolved state at `effective_at` uses `max effective_time <= effective_at`.
3. **Conflict honesty:** same-effective_time disagreements surface as `CONFLICT` unless explicit precedence policy says otherwise.
4. **Parity:** bulk resolution equals single resolution (same basis).
5. **Truth purity:** S6 can be deleted and rebuilt from S5 without changing answers.

---

Got it — we’re illuminating **S4: Write Determinism** (the idempotency + dedupe “gearbox” that makes LS safe under retries/at-least-once delivery, without polluting the append-only ledger). This must preserve: **append-only truth**, **dual-time semantics**, and **no silent mutation**. 

---

# S4 Charter

**S4 is the sole authority inside LS for:**

* deciding whether an incoming write is **NEW**, **DUPLICATE**, or an **IDEMPOTENCY CONFLICT**
* producing a single deterministic **LedgerAppendCommand** for S5
* ensuring *transport retries* don’t masquerade as *truth evolution*

**S4 does not:**

* decide who is allowed to write (S2)
* decide what the target is (S3)
* write truth (S5 is the only append authority)
* interpret “as-of” semantics (S6)

---

# What S4 consumes and produces

## Inputs to S4 (from S3 + admitted assertion)

S4 receives a **DeterminizeWriteRequest**:

* `TargetKey` + `ContextPins` scope (from S3)
* `label_family` (or equivalent) + `label_value` (+ optional confidence)
* `effective_time`, `observed_time` (already required at the LS boundary) 
* `provenance` (source type/system/actor)
* optional `evidence_refs[]` (by-ref pointers; order not meaningful)
* optional `supersedes_event_id` (for explicit corrections)
* **idempotency handle** (required in v0 production; see below)

## Outputs of S4

S4 returns exactly one of:

1. **PROCEED_TO_APPEND** with a fully prepared `LedgerAppendCommand`
2. **DUPLICATE** with the existing `label_event_id` (no append)
3. **REJECT: IDEMPOTENCY_KEY_CONFLICT** (same idempotency handle used for different content)
4. **REJECT: INVALID_IDEMPOTENCY_HANDLE** (missing/invalid handle when required)

S4 also returns a **WriteDeterminismReceipt** fields (for S1’s write receipt):

* `dedupe_key` (canonical)
* `content_fingerprint` (canonical)
* `idem_kernel_version` (pinned; see below)

---

# The Idempotency model (v0, designer-authoritative)

## 1) Idempotency handle is required (prod semantics)

**Authoritative v0 rule:** every write must provide an **idempotency handle** that stays stable across retries. Without it, append-only truth gets polluted under at-least-once delivery. 

### Where it comes from (examples, not specs)

* **Case Workbench:** generates a `label_assertion_id` per user action (stable across retries).
* **Adjudication feed:** uses `(source_system, source_event_id)` as the handle.
* **Oracle/engine label writer (if ever used):** uses the upstream truth-product record id.

## 2) Dedupe key must be scoped to avoid cross-writer collisions

Two different sources might both emit “id=123”. So S4 defines:

### `writer_namespace`

A stable namespace derived from provenance (from S2/S3 admission context), e.g.:

* `case_workbench`
* `adjudication.<provider>`
* `oracle_writer.<engine_bundle>`

### `AssertionKey`

```
AssertionKey = (writer_namespace, idempotency_handle)
```

### `DedupeKey` (what must be unique)

**Authoritative v0:**

```
DedupeKey = (TargetKey, label_family, AssertionKey)
```

This means: *“the same writer asserting the same label_family for the same target, with the same handle, is the same write.”*

---

# Content fingerprint (conflict detection without guessing)

S4 computes a deterministic **content_fingerprint** over a canonicalized “semantic payload”:

```
SemanticPayload =
  TargetKey
  label_family
  label_value (+ confidence if used)
  effective_time
  observed_time
  provenance (at least writer_namespace; optionally actor_id)
  supersedes_event_id (if present)
  evidence_refs (canonicalized set, stable order)
```

**Why include these fields?**

* If a retry arrives with the same idempotency handle but different value/times/supersedes, that is not a harmless retry — it’s either a client bug or attempted mutation. We must fail closed.

**Important canonicalization rules inside S4**

* `evidence_refs` are treated as a **set** (sorted deterministically) to avoid false conflicts due to ordering
* timestamps are normalized to a single canonical representation
* JSON encoding is canonical (sorted keys, stable types) before hashing

---

# S4 Internal machinery (inside the node)

Think of S4 as a deterministic pipeline:

## S4.1 Idempotency Intake & Normalizer

* Validates `idempotency_handle` exists and is well-formed
* Derives `writer_namespace` deterministically from provenance
* Produces `AssertionKey`

**Fail closed** if missing/invalid (unless an explicit *environment policy* enables a dev-only fallback; see ladder section).

## S4.2 DedupeKey Builder

* Builds `DedupeKey = (TargetKey, label_family, AssertionKey)`
* Computes `dedupe_fingerprint = H(canonical(DedupeKey))`

## S4.3 Semantic Canonicalizer

* Builds `SemanticPayload` in canonical form
* Produces `content_fingerprint = H(canonical(SemanticPayload))`

## S4.4 Duplicate/Conflict Gate (the “decision point”)

S4 must determine one of three states:

### A) Existing record found for the DedupeKey

* If stored `content_fingerprint == incoming content_fingerprint` → **DUPLICATE(existing_label_event_id)**
* Else → **REJECT(IDEMPOTENCY_KEY_CONFLICT)**

### B) No existing record

→ **PROCEED_TO_APPEND** (prepare append command)

### C) Race / concurrency

Two writers concurrently attempt same DedupeKey:

* both may “see empty” during precheck
* the ledger (S5) must enforce uniqueness
* the loser receives `DUPLICATE` from S5 and maps it back into the stable write outcome

**Designer call:** S4 may do a precheck for efficiency, but **S5 is the final uniqueness authority**.

## S4.5 Append Command Builder

Creates the single authoritative `LedgerAppendCommand` for S5:

* includes `DedupeKey`, `content_fingerprint`, `ls_policy_rev`, and all fields required for the ledger event
* includes `supersedes_event_id` when provided (correction is still append-only)

---

# What S4 stores (minimal, production-real)

S4 needs a stable mapping:

* `DedupeKey -> (label_event_id, content_fingerprint)`

This can be:

* a dedicated idempotency index table, or
* columns on the ledger table with a unique constraint

**Design pin:** whichever way Codex implements it, it must support:

* atomic uniqueness
* stable retrieval of the existing `label_event_id` for duplicates

---

# Environment ladder posture for S4 (deployment pins)

**Semantics never change across envs** (duplicate vs conflict vs append). 

Allowed profile knobs (envelope-only):

* request limits, rate limits, timeouts
* how aggressively S4 prechecks vs relies on S5 uniqueness
* logging/metrics verbosity

### Optional dev/local convenience (explicit only)

You *may* allow a dev-only policy that supports:

* `ALLOW_SERVER_DERIVED_IDEMPOTENCY=true`

If enabled:

* when handle missing, S4 derives `idempotency_handle = H(canonical(SemanticPayload))`
* **and the receipt must explicitly say** `idem_mode=server_derived` and echo the derived handle so callers can reuse it

**Banned:** silently deriving handles without telling the caller (creates prod drift).

---

# Non-joins / forbidden shortcuts for S4 (drift killers)

* S4 must not accept the same `(writer_namespace, idempotency_handle)` with different content (must reject, not “turn into a correction”)
* S4 must not use non-deterministic inputs (wall clock “now”, randomness) in fingerprints
* S4 must not let policy_rev changes redefine what a given handle “means” in a way that breaks retries; idempotency kernel version must be stable

---

# Acceptance checks for S4 (what “correct” means)

1. **Idempotent:** same request replayed N times results in exactly one ledger append.
2. **Conflict-safe:** same DedupeKey with different content always rejects deterministically.
3. **Concurrency-safe:** two concurrent writes with the same DedupeKey produce one ACCEPTED and the rest DUPLICATE.
4. **Deterministic across environments:** fingerprints and outcomes are identical given the same inputs.
5. **Append-only preserved:** S4 never mutates history; it only decides whether to append a new event.

---

Got it — we’re illuminating **S5: Timeline Ledger Core** (the truth spine). This is the most sensitive node: **everything else is derived/rebuildable; S5 is primary truth**. It must uphold the platform pins: **append-only labels**, **corrections as new assertions**, **dual-time**, **no backfill mutation**, and **replayable, attributable provenance**.  

---

# S5 Charter

**S5 is the only place in LS where “truth is created.”**
It provides:

* **atomic append** of label events
* **ledger ordering** (monotonic position token)
* **uniqueness enforcement** (idempotency at truth boundary)
* **durable truth storage** in `label_store` DB 

**S5 does not:**

* interpret labels (S6 does)
* decide authority/policy (S2 does)
* canonicalize targets (S3 does)
* decide idempotency semantics (S4 does, but S5 enforces uniqueness)

---

# What S5 Stores: the Label Ledger (truth schema, conceptual)

Think of S5 as an append-only table of **LabelEvents** keyed by `label_event_id` and ordered by a monotonic `ledger_seq`.

## Core event fields (non-negotiable)

Each LabelEvent stored in S5 must carry:

### Identity and joinability

* `label_event_id` (opaque unique id)
* `TargetKey` (canonical; includes ContextPins scope) — from S3
* `label_family` (string/enum)
* `ls_policy_rev` used at write time (provenance attribution)

### Truth content

* `label_value` (+ optional confidence)
* `effective_time` (world-time)
* `observed_time` (when platform learned) 

### Provenance

* `writer_namespace` / source type (Case vs adjudication feed)
* `actor_principal` or actor ref (if available)
* optional `evidence_refs[]` (by-ref pointers only; no raw payload) 

### Correction / supersedes (optional but supported)

* optional `supersedes_label_event_id` (points to an earlier ledger event)

### Ledger mechanics

* `ledger_seq` (monotonic position token)
* `created_at_utc` (infrastructure timestamp)
* `dedupe_key` + `content_fingerprint` (from S4)

**Design authority call:** `effective_time` and `observed_time` are mandatory on every event; S5 must not store “timeless” events. 

---

# Append semantics (the machinery)

## S5.1 Append API (what S5 accepts)

S5 receives a **LedgerAppendCommand** from S4 containing:

* canonical TargetKey + scope
* label family/value
* effective_time + observed_time
* provenance
* evidence refs (by-ref)
* dedupe_key + content_fingerprint
* optional supersedes pointer
* ls_policy_rev

S5 produces a **LedgerAppendResult**:

* `APPENDED(label_event_id, ledger_seq)`
* or `DUPLICATE(existing_label_event_id)`
* or `REJECT(reason, retryable_flag)`

## S5.2 Atomicity rule (non-negotiable)

Append is **atomic**:

* either one event is committed once, or not committed.

If the DB transaction fails, S5 must return retryable vs non-retryable clearly.

## S5.3 Uniqueness rule (truth-boundary idempotency)

S5 enforces uniqueness using the **DedupeKey** (from S4):

* If the dedupe key already exists:

  * if `content_fingerprint` matches → `DUPLICATE(existing_label_event_id)`
  * else → `REJECT(IDEMPOTENCY_KEY_CONFLICT)` (or an equivalent invariant breach)

**Design authority call:** S5 must enforce this even if S4 already prechecked. S5 is the final guardrail against races. 

## S5.4 Append-only rule (no updates, no deletes)

* S5 never updates an existing LabelEvent’s truth fields.
* Corrections are new events with `supersedes_label_event_id` referencing earlier events. 

**Only allowed mutation in S5 (operational):**

* non-semantic metadata fields for ops (e.g., replication markers) **if and only if** they cannot affect truth interpretation.

But even those are discouraged; simplest is “no updates at all”.

---

# Ledger ordering and progress tokens (how loops are made real)

S5 provides a monotonic **ledger_seq** (or equivalent) that:

* increases with each committed append
* is used by S6/S7 to track “last applied”
* enables repair/reconciliation (L-C5)

This mirrors the platform’s monotonic progress principle (“watermarks don’t lie”) but localized to LS truth. 

**Design authority call:** ledger ordering is by **append time**, not by effective_time or observed_time. Those are semantic timestamps; the ledger_seq is the *truth recording order*.

---

# Evidence refs posture (what S5 will and won’t store)

**Allowed:**

* by-ref pointers (DLA record IDs, EB coords, object-store refs, etc.)
* small, structured metadata that helps a human understand the label (e.g., “reason_code”)

**Banned:**

* raw payloads of events or sensitive documents copied into LS “for completeness”
  This violates the platform’s by-ref posture and creates duplication risk. 

---

# Derived triggers (how S5 connects to IJ-D / IJ-N)

Once a new event is committed (`APPENDED`), S5 emits minimal deltas:

* **IJ-D1** to S6 (view invalidation/update)
* **IJ-D2** to S7 (export/index invalidation/update)
* **IJ-N1** to S8 (optional outbox notification)

**Design authority call:** these are *post-commit* side effects; failure to send them must not invalidate the committed truth.

---

# Repair & reconciliation support (production hardening)

S5 must support:

* reading events by target key
* reading events by label family
* reading events by ledger_seq range (for catch-up)
* retrieving the “head” ledger_seq token

This is what makes:

* L-C1 (views) and L-C2 (exports) repairable
* L-C5 (reconciliation) implementable without handwaving

---

# Environment ladder & deployment pins for S5

## Semantics identical everywhere

* append-only truth
* uniqueness enforcement
* dual-time required
* no truth mutation via backfill  

## Envelope knobs that vary by env

* DB sizing, replication/HA, backup schedule, retention of *derived* caches
* performance indexes
* stricter auth/monitoring/alert thresholds in prod

**Critical pin:** because you cannot backfill label truth, **dev/prod must practice restore**. Local can be lighter, but must still support the concept.

---

# Non-joins / forbidden shortcuts for S5

* S5 must not accept writes from anyone except S4 (no bypass).
* S5 must not expose “write by update” operations.
* S5 must not allow policy changes to rewrite stored events.
* S5 must not overwrite any previously published slice artifact (that’s S7’s domain, but S5’s immutability is the spine that enables it). 

---

# Acceptance checks for S5 (what “correct” means)

1. **Append-only:** no destructive edits; corrections are new events. 
2. **Uniqueness enforced at truth boundary:** races cannot create duplicates.
3. **Dual-time preserved:** every event has effective_time + observed_time. 
4. **Monotonic ledger token exists:** S6/S7 can track and repair.
5. **Durable truth:** `label_store` DB is authoritative; restore is feasible and tested. 

---

Alright — here’s **S2: Governance & Policy** illuminated (machinery exposed), with **authoritative v0 pins** that keep LS aligned to the platform’s outer network: **labels become truth only in LS**, **append-only timelines**, **effective_time vs observed_time**, **as-of discipline**, and **no semantic forks across the environment ladder**.  

---

# S2 Charter

**S2 is the control brain of LS.** It is the *only* place inside LS that answers:

1. **Who is allowed to assert what label truth?**
2. **What is an admissible label assertion shape (minimum semantics)?**
3. **Which policy revision is in force, and how is it applied consistently across nodes?**

S2 **does not**:

* canonicalize targets (S3 does)
* compute idempotency/dedupe (S4 does)
* interpret truth into views (S6 does)
* append truth (S5 does)

S2 exists to prevent drift like “some pipeline started writing labels” or “training suddenly used a different as-of rule”.

---

# S2’s “truth” objects

## 1) PolicyBundle (immutable, versioned)

**Authoritative pin:** LS policy is a single immutable bundle, identified by `ls_policy_rev`.

* Policy changes = activate a new `ls_policy_rev`
* Never mutate an existing bundle
* Every write/read must be attributable to a specific `ls_policy_rev` 

### PolicyBundle contents (v0)

S2 owns and distributes these sub-policies (this matches IJ-P1..P4 we already pinned):

1. **SurfacePolicy** (for S1): endpoint enablement, required params, size limits
2. **TargetPolicy** (for S3): what EVENT/ENTITY/FLOW mean, allowed types, required join keys/pins
3. **IdempotencyPolicy** (for S4): what defines “same write”, conflict-on-mismatch rules
4. **ResolutionPolicy** (for S6/S7): as-of rules, conflict posture (CONFLICT vs explicit precedence), redaction rules
5. **AuthorityPolicy** (S2 local): writer authority matrix (who may assert which label families for which target types)

> **Design pin:** S2 is the only node that can “know” the authority matrix. Everyone else receives their slices of policy via IJ-P edges.

---

## 2) Authority Matrix (writer → allowed label families)

**Authoritative v0 stance:** only explicitly whitelisted writers may produce truth labels.
This aligns with the platform pin: labels become truth via LS assertions; RTDL is evidence, not truth. 

Writers are identified as `writer_namespace` (derived from auth principal + declared source), e.g.:

* `case_workbench`
* `adjudication.<provider>`
* (optional later) `oracle_writer.<engine_bundle>`

Per writer, S2 defines:

* allowed **label_families**
* allowed **target_types** (EVENT/ENTITY/FLOW)
* required fields extras (e.g., evidence refs required for some families)
* whether supersedes is allowed/required

---

# S2 Internal Machinery (opaque submodules inside S2)

Think of S2 as six internal “micro-boxes”:

### S2.1 Policy Loader

* loads PolicyBundle by `ls_policy_rev`
* exposes “active policy pointer” (`active_ls_policy_rev`)
* caches bundles by revision
* **never** edits policy in-place

### S2.2 Authority Engine

* maps caller principal → `writer_namespace`
* checks authority matrix: “is this writer allowed to assert this family for this target type?”
* produces deterministic reject reasons on failure

### S2.3 Assertion Shape Validator

Enforces minimum semantics required by the platform pins:

* subject present (event/entity/flow)
* value present
* provenance present
* **effective_time present**
* **observed_time present** 
* evidence refs are by-ref only (no raw payload blobs)

> **Authoritative call:** missing `effective_time` or `observed_time` ⇒ REJECT (no silent synthesis). 

### S2.4 Time & Sanity Rules

Policy-controlled “sanity checks” that reduce garbage truth (not changing semantics):

* observed_time must be >= effective_time? (optional; not always true for retroactive truth)
* allowed backdating window for some families
* reject impossible timestamps (far future etc.)
  These are *policy knobs*, not hard-coded behavior.

### S2.5 Entitlements & Visibility Gate (read-time)

* determines what a caller may see (evidence refs visible or redacted)
* ensures “no silent redaction”: if evidence is hidden, mark it explicitly

### S2.6 Policy Distributor

Implements IJ-P1..IJ-P4:

* S2→S1 (surface gating)
* S2→S3 (target rules)
* S2→S4 (idempotency rules)
* S2→S6/S7 (resolution + bulk parity rules)

---

# How S2 participates in LS paths

## Writes (IJ-W1 / IJ-W2)

### IJ-W1: S1 → S2 (Admission)

S2 returns:

* `ACCEPT` + `PolicyContext{ls_policy_rev, writer_namespace, authority grants, policy slices}`
* or `REJECT(reason_code)`

**S2 rejects** before any canonicalization/idempotency if:

* unauthorized writer
* missing required fields (esp. effective/observed time)
* forbidden payload style (raw payloads instead of refs)
* label family not allowed

### IJ-W2: S2 → S3

S2 passes:

* admitted assertion
* `TargetPolicy` slice (what target types exist, required pins)
  S3 remains the canonicalizer; S2 does not attempt to guess targets.

---

## Reads (policy + entitlements)

S2 supplies S1/S6/S7 with:

* required parameter rules (e.g., as-of required for leakage-safe endpoints)
* visibility rules (what evidence refs can be returned)
* resolution policy rev attribution

**Design pin:** any response that is “resolved” (as-of/current/bulk resolved) must echo:

* `ls_policy_rev`
* basis (`observed_as_of`, `effective_at`)
  so downstream manifests can pin it. 

---

# Policy lifecycle and environment ladder posture

## Policy activation (P-P1)

**Authoritative pin:** policy changes are *governed* and must be attributable. 
When `active_ls_policy_rev` changes:

* new requests use the new rev
* in-flight requests complete under the rev they started with (no mid-flight mixing)
* S6/S7 may invalidate/recompute derived layers (ledger unchanged)

## Environment ladder

Pinned ladder rule: **same semantics everywhere; only envelope/strictness differs**. 

So S2 supports per-environment profile *knobs* that do not change meaning:

* stricter authority matrix in prod (fewer writers)
* stricter time sanity windows
* stricter redaction
* tighter request limits

But **banned**: local/dev bypassing S2 admission rules or allowing missing as-of/dual-time semantics.

---

# S2 Failure taxonomy (stable, drift-resistant)

S2 must use stable reject reasons (so callers and ops can act deterministically), e.g.:

* `UNAUTHORIZED_WRITER`
* `LABEL_FAMILY_NOT_ALLOWED`
* `MISSING_REQUIRED_FIELDS`
* `INVALID_TIME_FIELDS`
* `FORBIDDEN_PAYLOAD_STYLE`
* `POLICY_REV_NOT_AVAILABLE` (rare; should be ops-visible)

This prevents “mystery rejection” drift across environments.

---

# S2 Non-joins (explicitly forbidden)

* S2 must not write truth directly (no S2→S5).
* S2 must not canonicalize targets (no hidden S2 logic duplicating S3).
* S2 must not interpret labels (no S2 pretending to resolve conflicts).
* S2 must not change ledger history on policy rev changes (policy affects interpretation, not truth storage). 

---

# Acceptance checks for S2 (what “correct” means)

1. Every write/read is attributable to a `ls_policy_rev`. 
2. Unauthorized writers cannot create truth labels. 
3. Missing effective/observed time is rejected (no silent filling). 
4. Policy distribution keeps S1/S3/S4/S6/S7 semantically aligned (no divergent rules).
5. Policy changes never rewrite S5; only derived layers may recompute.

---

Alright — here’s **S7: Export & Slices** illuminated. This is the LS subnetwork that makes **OFS/MF-scale** label reads possible **without** breaking any of the pinned semantics (append-only truth, explicit as-of, bulk parity with single reads, by-ref + digests, no unbounded scans).

---

# S7 Charter

**S7 is the “manifest-grade bulk label surface.”** It exists to answer questions like:

* “Given this *explicit target universe*, give me `label_as_of` for these targets at `observed_as_of=T` (and optionally `effective_at=t`)”
* “Give me a reproducible slice output I can pin into a DatasetManifest (refs + digests + basis)”
* “Do this at scale, deterministically, with paging/streaming”

**S7 is not:**

* a truth store (truth is only S5)
* a training pipeline (it only produces slices/exports for consumers like OFS)
* allowed to invent resolution rules (must match S6)

---

# The hard pins S7 must obey

1. **Bulk parity**: bulk resolved results must equal single `label_as_of` semantics for the same `(TargetKey, basis, policy_rev)`.
2. **Explicit basis always**: resolved slices require `observed_as_of`; “hidden now” is banned.
3. **No unbounded scans**: bulk must be driven by an explicit target universe (list or by-ref `target_set_ref`).
4. **By-ref + digest first**: large slices are returned as artifact refs + digests, not giant inline payloads.
5. **Immutability**: any slice artifact with a digest is immutable; rebuilds create a **new** ref/digest, never overwrite.

---

# Inputs & Outputs

## Inputs S7 consumes (from S3 via IJ-X2)

S7 receives a **BulkSliceRequest** roughly shaped like:

* **Target universe**:

  * `targets[]` (small) *or*
  * `target_set_ref` (large, preferred) — a by-ref list of targets the caller already built (usually from replay)
* **Basis**:

  * `observed_as_of` (**required** for resolved)
  * optional `effective_at` (defaults to `observed_as_of` if omitted)
* `label_families` filter(s)
* `mode`:

  * `resolved_as_of` (one row per target per family)
  * `timeline` (events per target/family)
* delivery hint:

  * `inline_paged` vs `by_ref_artifact` (S7 may override based on size thresholds)
* `ls_policy_rev` + ResolutionPolicy slice (from S2 IJ-P4)

## Outputs S7 produces (to S1 via IJ-X5)

A **BulkSliceResponse** with two delivery shapes:

### 1) Inline paged (small / Case UX / debugging)

* `basis` echoed: `observed_as_of`, `effective_at`
* `ls_policy_rev` echoed
* `target_set_fingerprint`
* `page[]`: rows with deterministic ordering
* `next_page_token` (retry-safe)
* optional `page_digest`

### 2) By-ref slice artifact (preferred for OFS/MF)

* `label_slice_ref` (object store ref)
* `slice_digest` (integrity)
* `schema_id`
* `row_count`
* `basis` echoed + `ls_policy_rev`
* `target_set_fingerprint`

**Design note:** even inline responses must still echo basis + policy_rev (so downstream can’t “forget” what it used).

---

# Internal machinery inside S7

Think of S7 as a pipeline of opaque internal micro-boxes:

## S7.1 Slice Planner

**Job:** decide *how* to execute the slice request without changing meaning.

* selects retrieval strategy (keyed fetch vs batched queries vs streaming)
* decides delivery mode (inline vs artifact) based on thresholds
* defines **stable ordering** for output rows
* chooses shard plan (parallelism) but guarantees output determinism

## S7.2 Target Universe Loader

**Job:** materialize the canonical target universe.

* If request is `targets[]`: ensure they’re already canonical (or route through S3 earlier)
* If `target_set_ref`: load the referenced set and validate it
* compute `target_set_fingerprint = H(canonical(target_set))`
* enforce “no unbounded scan” rule (must have a finite universe)

## S7.3 Ledger Bulk Reader (S7 ↔ S5)

**Job:** fetch **truth events** needed for the universe.

* performs bulk reads keyed by `(TargetKey, label_family)`
* applies `observed_time <= observed_as_of` as an **efficiency bound** when in resolved mode (not a semantic change)
* streams results to avoid holding everything in memory
* requires deterministic ordering of events per target (via S5 ledger order)

## S7.4 Resolver Kernel Adapter (S7 ↔ S6)

**Job:** ensure parity with S6.

* for `resolved_as_of` mode:

  * feed the per-target event lists + basis into the **same resolver kernel** S6 uses
  * produce `LABEL(value)` / `UNKNOWN` / `CONFLICT`
* for `timeline` mode:

  * no resolving; just format ordered events (with optional redaction rules)

**Hard pin:** S7 must not implement “similar but faster” resolution logic that diverges from S6.

## S7.5 Slice Builder

**Job:** build deterministic rows.

* stable row schema (schema_id)
* deterministic ordering:

  * primary: canonical target ordering key (from S3/S7.2)
  * secondary: label_family order (canonical)
* represents conflicts explicitly (never hides)

## S7.6 Artifact Writer (by-ref mode)

**Job:** write immutable slice artifacts.

* writes to object store under an address that includes:

  * `target_set_fingerprint`
  * `observed_as_of` / `effective_at`
  * `ls_policy_rev`
  * `slice_digest`
* compresses safely (compression must not change digest semantics; digest is over canonical bytes)
* returns `label_slice_ref + slice_digest`

**Immutability pin:** once written and referenced, that ref/digest pair is never overwritten.

## S7.7 Slice Index / Receipt Store (derived, optional)

**Job:** make ops/debugging practical.

* stores a small receipt mapping:

  * `(target_set_fingerprint, basis, policy_rev) -> slice_ref, slice_digest, row_count`
* purely derived convenience; can be rebuilt, can be dropped

## S7.8 Coherence Listener (IJ-D2)

**Job:** keep derived helpers fresh when S5 appends new truth.

* consumes minimal deltas from S5 (`target_key`, family, times, ledger_seq)
* marks caches/indexes “dirty” or advances progress tokens
* never treats missed deltas as “truth missing” (repair loop covers that)

## S7.9 Repair/Reconciliation Worker (L-C5 hook)

**Job:** self-heal if derived state lags.

* compares `s7_last_applied_ledger_seq` with S5 head
* rereads missing ranges from S5
* repairs indexes/caches/receipts
* does **not** mutate S5 and does **not** overwrite published slice artifacts

---

# Derived state vs truth (deployment-critical)

* **Truth:** S5 ledger only.
* **Derived (S7):** indexes, cached slices, receipts, progress tokens.
* S7 must always be able to serve a correct slice **by reading S5**, even if derived state is missing (slower is acceptable; wrong is not).

---

# Environment ladder knobs for S7 (allowed envelope differences)

These can vary by local/dev/prod without changing meaning:

* thresholds for switching inline → by-ref artifact
* max targets per request, max page sizes, max bytes
* concurrency/sharding limits
* caching/materialization aggressiveness
* compression settings
* auth strictness (who can request bulk slices)

**Not allowed:** relaxing the requirement for explicit `observed_as_of` for resolved slices in any environment.

---

# S7 Non-joins (forbidden shortcuts)

* S7 must not write to S5 or “fix” truth.
* S7 must not do “scan all labels” queries without explicit target universe.
* S7 must not default `observed_as_of` silently (no “latest” unless explicitly requested as current).
* S7 must not overwrite digest’d artifacts.
* S7 must not diverge from S6 resolution semantics.

---

# Acceptance checks for S7 (what “correct” means)

1. **Parity:** for any target, bulk resolved output == single resolved output under the same basis/policy.
2. **Determinism:** same inputs → same `target_set_fingerprint`, same ordering, same `slice_digest`.
3. **Immutability:** published slice refs are never overwritten.
4. **Basis echo:** every slice (inline or by-ref) echoes `observed_as_of`, `effective_at`, `ls_policy_rev`.
5. **Repairable:** deleting S7 derived state doesn’t lose truth; slices can still be produced from S5.

---

Got it — illuminating **S1: Edge** (the public boundary of LS). This node should stay **thin** and purely enforce the already-pinned semantics from S2/S3/S4/S5/S6/S7, without inventing meaning.

---

# S1 Charter

**S1 is LS’s public façade.** It provides:

* ingress/egress surfaces for **writes**, **reads**, and **bulk slices**
* authentication + caller identity extraction
* parameter gating (e.g., “as-of required”)
* request shaping (size limits, paging)
* correlation/tracing and stable error mapping

**S1 must not:**

* decide writer authority (S2 does)
* canonicalize targets (S3 does)
* compute idempotency (S4 does)
* interpret label truth (S6 does)
* write truth (S5 does)
* implement bulk resolution logic (S7/S6 do)

---

# S1 Surfaces (v0)

S1 exposes three logical entrypoint families (API/CLI doesn’t matter yet):

## 1) Write surface (J13/J13-like producers)

**Intent:** accept a label assertion and return an idempotent receipt.

### Input (conceptual)

* `LabelAssertion`:

  * subject (event/entity/flow)
  * label_family + value (+ optional confidence)
  * provenance (source/actor)
  * **effective_time**
  * **observed_time**
  * optional evidence_refs (by-ref pointers)
  * optional supersedes pointer
* `idempotency_handle`
* caller principal (auth)

### Output (conceptual)

* `WriteReceipt`: `ACCEPTED | DUPLICATE | REJECTED`
* canonical TargetKey
* label_event_id (new or existing)
* `ls_policy_rev`
* reason_code + retryable

**S1’s pinned behavior**

* If payload is malformed → reject early (400-class)
* If required parameters missing (like effective/observed times) → may reject early, but must still be consistent with S2 rules (S2 is final authority)
* It must pass through to S2/S3/S4/S5 and return the stable outcome.

---

## 2) Read surface (Case + internal consumers)

**Intent:** read timelines and resolved views.

### Read modes

* `timeline(subject[, family])`
* `label_as_of(subject, observed_as_of[, effective_at][, family])`
* `current_label(subject[, family])` (explicit convenience)

### S1 pinned gating rules

* `label_as_of` **requires** `observed_as_of` (no hidden now)
* `current_label` is allowed but must be clearly marked “as-of now”
* Response must echo basis: `observed_as_of`, `effective_at`, `ls_policy_rev` (S6 supplies; S1 ensures it isn’t dropped)

---

## 3) Bulk/export surface (OFS/MF scale)

**Intent:** return manifest-grade label slices.

### Input shapes (allowed)

* small: explicit target list
* large: `target_set_ref` (by-ref target universe)

### Required

* `mode = bulk_resolve_as_of` requires `observed_as_of`
* optional `effective_at` (defaults handled downstream, but S1 must enforce explicitness rules)
* delivery preference (inline vs by-ref; S7 may override)

### Output shapes

* inline paged results **or**
* by-ref slice artifact (`label_slice_ref` + `slice_digest`), plus echoed basis + policy_rev

**S1’s pinned behavior**

* rejects unbounded “all labels” requests (must have finite target universe)
* enforces paging + max limits
* ensures basis/policy metadata are present in responses

---

# S1 Internal Machinery (inside the node)

Think of S1 as a router with strict gates:

## S1.1 Authn/Authz Front Door

* extracts caller principal / service identity
* attaches request context (tenant/workspace if you later add)
* calls into S2 for semantic authorization (S1 doesn’t own label-family authority)

## S1.2 Request Normalizer

* parses input
* normalizes timestamps to canonical representation (format only; not semantics)
* strips disallowed fields (e.g., raw payload blobs) only if policy says “reject”; default is reject, not silent drop

## S1.3 Parameter Gate (policy-driven)

* consults SurfacePolicy from S2:

  * which endpoints are enabled in this env profile
  * required params per endpoint
  * size limits and paging limits
* blocks requests that are invalid *before* they reach deeper modules

## S1.4 Router / Orchestrator

* Write: routes to `S2 → S3 → S4 → S5`
* Read: routes to `S3 → S6 ↔ S5`
* Bulk: routes to `S3 → S7 ↔ S5 (↔ S6 kernel)`

S1’s orchestration is deliberately thin: it wires the internal graph, it doesn’t compute business logic.

## S1.5 Response Assembler

* maps internal outcomes to stable external responses
* ensures the response includes:

  * canonical TargetKey
  * basis echo (for resolved/bulk)
  * ls_policy_rev
  * stable reason codes

## S1.6 Error Mapper (stable taxonomy)

S1 emits stable error families (examples):

* `INVALID_REQUEST_SHAPE`
* `MISSING_REQUIRED_PARAM`
* `UNAUTHORIZED` (auth layer)
* `REJECTED_BY_POLICY` (from S2 with reason_code)
* `INVALID_TARGET` (from S3)
* `IDEMPOTENCY_CONFLICT` (from S4/S5)
* `TRANSIENT_FAILURE_RETRYABLE` (DB/broker transient)

S1 must preserve “retryable vs non-retryable” and must not collapse distinct failure causes.

## S1.7 Observability Hooks

* correlation id / trace id injection
* structured logs for boundary decisions
* metrics:

  * write outcomes accepted/dup/reject by reason
  * read mode volumes
  * bulk slice sizes / by-ref vs inline
  * latency buckets

---

# Environment ladder posture for S1 (allowed knobs)

These vary by env without changing meaning:

* endpoint enablement (e.g., disable bulk in local)
* max payload size / max targets / page size
* rate limits
* auth strictness (local permissive, prod strict)

**Not allowed:** making `observed_as_of` optional in any environment for as-of reads/slices.

---

# S1 Non-joins / forbidden shortcuts

* S1 must not bypass S2 for write admission
* S1 must not bypass S4 and write directly to S5
* S1 must not default as-of to “now” for leakage-safe modes
* S1 must not return responses that drop basis/policy metadata
* S1 must not “fix” ambiguous targets (must fail closed via S3)

---

# Acceptance checks for S1

1. Thin boundary: all semantic decisions come from S2/S3/S4/S5/S6/S7.
2. Correct gating: as-of requires observed_as_of; bulk requires finite target universe.
3. Stable outcomes: write receipts are idempotent; error taxonomy is stable.
4. Basis and policy rev always echoed on resolved/bulk outputs.
5. Same semantics across environments; only envelope limits differ.

---

Got it — illuminating **S8: Notifications** (optional). This is the outbox/retry machinery that emits **label_written / label_corrected** hints to the **control plane** without ever becoming a truth channel or affecting correctness.

This aligns to the platform’s deployment pin: **Label Store may emit optional label events to `fp.bus.control.v1`**, and IG is the front door for bus admission.  

---

# S8 Charter

**S8 is an optional, non-blocking notification subsystem** that:

* listens for **new committed label events** (from S5 post-commit)
* records notification intent in an **outbox**
* emits control-plane notification facts to **IG → `fp.bus.control.v1`**
* retries idempotently until success or explicit dead-letter

**S8 must not:**

* block label writes
* change or interpret label truth
* emit “authoritative label state” (only pointers/hints)
* become required for OFS/MF correctness (truth is still read from LS)

---

# What notifications are (and aren’t)

## Notification types (v0)

* `label_written` — a new label assertion was appended
* `label_corrected` — a new assertion that supersedes another (or is marked as correction)

These are **control facts**, not traffic.

## Notification payload posture (authoritative)

Notifications must be **pointer-like**, containing only:

* `notification_id` (stable)
* `notification_type`
* `label_event_id` (the ledger truth pointer)
* `target_key` (canonical)
* `label_family`
* `observed_time` (and optionally `effective_time`)
* `writer_namespace` (provenance summary)
* `ls_policy_rev` (attribution)
* correlation ids / trace ids

**Banned:** full label timelines, resolved label state, or anything that could be mistaken as “label truth” without consulting LS.

---

# S8 Inputs and Outputs

## Inputs

S8 is fed by **S5 post-commit** (IJ-N1): a minimal “notification intent” message:

* includes `label_event_id`, `target_key`, family, times, type, policy_rev

## Outputs

S8 emits **control-plane events** to the bus **via IG**:

* admitted onto `fp.bus.control.v1` (or equivalent control topic)
* duplicates tolerated downstream (notifications are idempotent hints)

---

# S8 Internal machinery (inside the node)

## S8.1 Notification Classifier

Decides which notification type to enqueue:

* If the label event has a `supersedes_label_event_id` → `label_corrected`
* Else → `label_written`

Policy can refine this (e.g., only emit for certain families), but v0 keeps it simple.

## S8.2 Outbox Writer (durable intent record)

On successful ledger append, S8 records an **OutboxEntry** with:

* `notification_id` (deterministic; see idempotency)
* `status = PENDING`
* payload fields (pointer-like)
* `created_at`, `attempt_count`, `next_attempt_at`

**Design authority call:** outbox write must be **best-effort but non-blocking**:

* If outbox insert fails, label write still succeeds; S8 can later be repaired by scanning S5 (repair loop).

## S8.3 Emitter Worker

A background worker that:

* polls `PENDING` outbox entries whose `next_attempt_at <= now`
* emits each as a control event via IG
* marks entry `SENT` on success
* on failure, increments `attempt_count` and schedules exponential backoff

## S8.4 Idempotency Kernel (critical)

S8 must ensure that retries don’t create “new” notifications.

**Authoritative idempotency rule:**

* `notification_id = H(label_event_id + notification_type)`
* emitted event’s `event_id` is derived from `notification_id`

So:

* the same outbox entry always emits the same event identity
* bus duplicates are safe (consumers dedupe or tolerate)

If you later wrap in the canonical envelope, the `event_id` field should be set to this deterministic id. 

## S8.5 Dead-letter / quarantine lane (ops safety)

After N failures or a terminal error, mark entry:

* `status = DEAD_LETTER`
* with `last_error_code`

This is for ops; it must not affect correctness.

## S8.6 Repair / Reconciliation hook (ties into L-C5)

Because outbox is non-blocking, S8 must support repair:

* detect gaps (e.g., S5 ledger head > last_notified_seq)
* re-enqueue missing notification intents by scanning S5 for recent events and creating outbox entries deterministically
* idempotency ensures no duplicates harm anything

This ensures “outbox loss” doesn’t permanently break notification capability.

---

# How S8 integrates with the platform (external join)

## Emission via IG (recommended)

S8 behaves like any other producer:

* submit notification to IG
* IG applies admit/dedupe/quarantine semantics
* event lands on `fp.bus.control.v1`

This keeps “bus front door” consistent with the platform’s trust boundary posture. 

**Note:** If you decide to bypass IG for control events, that must be an explicit platform fork. v0 keeps it consistent: go through IG.

---

# Environment ladder posture (deployment knobs)

Semantics identical everywhere; envelope differs. 

## Allowed knobs per env

* enable/disable notifications entirely (still optional)
* retry/backoff profile
* max in-flight emits
* DLQ thresholds
* auth strictness for emitting to IG/control bus
* polling intervals

## Not allowed

* making label writes depend on notifications (blocking)
* emitting full label state/timelines in prod but not in dev (semantic drift)

---

# S8 Non-joins / forbidden shortcuts

* S8 must not read/serve label truth to consumers (truth is LS read surfaces)
* S8 must not emit notifications as “authoritative label state”
* S8 must not mutate S5 or trigger corrections
* S8 must not be required for OFS/MF training correctness (at most it triggers jobs)

---

# Acceptance checks for S8

1. **Non-blocking:** label writes succeed even if S8 is down. 
2. **Idempotent:** same label event → same notification_id/event_id; retries don’t create new identities. 
3. **Pointer-like payload:** consumers must still query LS for truth.
4. **Repairable:** scanning S5 can reconstruct missing outbox entries.
5. **Optional:** disabling S8 does not break any correctness path; only reduces automation convenience.

---

## USER: PAUSE FOR REFLECTION

Absolutely. Here’s the “pause-point” view of what we’ve actually built, in a way that helps keep it all in your head without drifting.

## What we illuminated

We didn’t just define a component — we revealed a **two-layer network**:

1. **Outer platform network** (LS as a vertex in the platform graph)
2. **Inner LS network** (LS as its own graph of subnetworks S1–S8 with joins/paths/loops)

Both layers are now pinned enough that implementation should feel like “filling in machinery,” not inventing semantics.

---

## Why it’s complex (in the right way)

LS is deceptively simple (“a label DB”), but in this platform it sits at the intersection of:

* **truth vs evidence** (the hardest boundary)
* **time semantics** (effective vs observed + as-of leakage safety)
* **reproducibility** (DatasetManifest-grade outputs)
* **idempotency** (at-least-once reality)
* **governed change** (policy_rev attribution, no silent drift)
* **optional automation** (notifications that must not become correctness-critical)

So the complexity isn’t feature bloat — it’s **guardrails** that prevent drift across the learning loop.

---

## The “spine” mental model (what everything revolves around)

Inside LS we pinned one primary truth spine:

* **S5 Timeline Ledger Core** = the only truth creator
  Append-only events, dual-time preserved, uniqueness enforced, monotonic ledger token.

Everything else exists to **safely interact with that spine**:

* **S3** gives stable join keys (TargetKey + ContextPins)
* **S4** makes writes retry-safe (idempotency & conflict)
* **S6** interprets truth safely (as-of & conflicts)
* **S7** makes it usable at scale (bulk parity + digests + refs)
* **S2** keeps rules coherent (policy_rev + authority matrix)
* **S1** is the thin boundary router (no semantics)
* **S8** is optional automation (outbox hints only)

That’s the internal network’s “center of gravity.”

---

## The “closed circuits” we intentionally created

We explicitly designed loops so the platform can improve without cheating:

* **Core improvement loop:** evidence → case → labels → rebuild → train → registry → new decisions
* **Human correction loop:** truth evolves append-only (no mutation)
* **Export freshness loop:** ledger drives slices (rebuildable)
* **Policy change loop:** interpretation can change without rewriting history
* **Repair loop:** derived layers can lag and heal without becoming truth
* **Notification loop:** retries happen without affecting correctness

This is why it feels complex: we made **every feedback path explicit** and **fail-safe**.

---

## The most important “complexity reducers” we baked in

Even with all that, we reduced future chaos by pinning:

* **Non-joins** (hot path doesn’t read LS; RTDL doesn’t write labels; control events aren’t truth; no unbounded scans)
* **Basis echo everywhere** (observed_as_of, effective_at, policy_rev)
* **Bulk parity** (bulk == single semantics)
* **Environment ladder discipline** (same semantics everywhere; only envelope differs)

Those pins are what keep the network understandable as it grows.

---

## What to watch for as we go deeper (the real drift risks)

If anything is likely to cause drift later, it’s these three:

1. **TargetKey model** getting “helpfully flexible” (S3 must stay strict)
2. **as-of semantics** being treated as optional (S6/S7 must fail closed)
3. **derived layers** becoming “truthy” (S6/S7/S8 must remain rebuildable/optional)

If we keep those guarded, the rest stays stable.

---

