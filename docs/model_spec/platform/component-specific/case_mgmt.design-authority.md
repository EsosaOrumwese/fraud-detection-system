# Case Management/Workbench Design Authority

This file is a rough collection of design or brainstorm notes for the Case Management/Workbench. It views the whole platform as a network and expands open the Case Management/Workbench's position in this network and illuminates it.

---

Got it. We’ll treat **CM/Workbench internals as a black box** and make the rest of the platform’s expectations **crisp and binding**—so later, whatever we design inside CM is forced to satisfy these outer joins without drift.

Below is the **authoritative outer role + interaction design** for **Case Mgmt / Workbench** (CM).

---

## CM’s job in the platform network

### CM’s authority (what CM is the system-of-record for)

**[PINNED] CM is the sole truth store for:**

* **Case objects** (case identity + lifecycle state)
* **Append-only case timelines** (“what happened / what we did / who did it / when”) 

**[PINNED] CM is *not* label truth.** Labels become truth **only** when written to Label Store.  

### CM’s mission (what the platform uses it for)

**CM turns evidence into an investigation story and produces adjudication truth**:

* Consumes **RTDL evidence** by-ref (decisions, intents, outcomes, audit pointers)
* Facilitates **human workflows** (triage, notes, escalation, disposition)
* Emits **LabelAssertions** into Label Store
* Any **human-driven side effects** go through Actions Layer as ActionIntents 

This is the pinned plane boundary between “what we decided/did” and “what is true.” 

---

## CM’s boundary surfaces (what crosses the component boundary)

Think of CM as having 4 “ports” to the rest of the platform:

### Port 1 — Evidence + Trigger Intake (from RTDL world)

**What CM receives**

* **Case triggers and evidence refs** originating from DF decisions, AL outcomes, and DLA pointers 
* The bridge is **stable identifiers + by-ref pointers**, not copied payloads 

**[PINNED] Intake objects must be “joinable”**
Minimum join material CM must be able to accept/store:

* ContextPins `{manifest_fingerprint, parameter_hash, scenario_id, run_id}` when the thing claims run/world joinability 
* One or more stable IDs: `event_id`, `decision_id`, `action_intent_id`, `action_outcome_id`, `audit_record_id`
* Optional **EB coordinates** (partition/offset) if available as a deterministic pointer to the admitted fact
* Optional `seed` when the evidence is seed-variant (engine-realisation derived) 

**[PINNED] CM must be safe under at-least-once**
Because upstream evidence may be duplicated/replayed, CM intake must be idempotent: duplicates must not create duplicate cases/timeline events. (This follows the platform’s at-least-once posture and idempotency law at boundaries.) 

> **Authority choice:** CM does **not** need to parse full event payloads to intake triggers; it relies on (IDs + refs + minimal metadata). That matches the “bridge is refs” pin and keeps CM from becoming a second bus consumer with implicit schema coupling. 

---

### Port 2 — Evidence Resolution (reads, by-ref)

CM must be able to **render investigation context** without becoming another truth store.

**[PINNED] Evidence is stored and transported by-ref**
CM stores:

* DLA audit record refs (object store) as primary evidence anchors 
* Optionally EB history reads (for UI context), but still treated as replayable fact refs, not copied truth 

**[PINNED] Engine truth_products are “oracle/reference lane” only**
If CM reads engine `truth_products` (e.g., synthetic labels/case truth for eval or tool support), they are:

* **never business traffic**, and never hot-path inputs  
* only admissible **by explicit refs + PASS evidence**, starting from SR’s join surface (no scanning) 

---

### Port 3 — Label Emission (CM → Label Store) — the critical join

This is pinned as **J13**.

**What crosses the join:** **LabelAssertions** written as **append-only timeline entries**. 

**[PINNED] Minimum semantics CM must satisfy when emitting a label**
Every LabelAssertion must carry:

* **subject** (event/entity/flow)
* **value** (+ optional confidence)
* **provenance** (who/what process)
* **effective_time** (when it is true)
* **observed_time** (when we learned it) 

**[PINNED] Corrections are append-only**
No destructive edits; new assertions supersede in interpretation, history remains. 

**Control posture**
Label writes are controlled at Label Store (trusted writers, auditable, append-only). CM is the workflow that produces assertions, not the truth owner. 

---

### Port 4 — Manual Intervention (CM → Actions Layer)

**[PINNED] Manual action is not a bypass**
If a human changes the world, CM must express it as an **ActionIntent** executed via **Actions Layer** (effectively-once + immutable outcomes).  

**What CM must include in an ActionIntent request (semantically)**

* Actor principal (human identity) + “origin=manual”
* ContextPins + linkage IDs (event/decision/case references)
* Deterministic idempotency key (so retries don’t re-execute)
* Evidence refs justifying the action (by-ref)

AL is the execution authority; CM is only a requester and recorder of outcomes. 

---

## Optional: CM as a producer (CM → IG → EB)

This is not required for CM’s core truth role, but it’s allowed and sometimes valuable.

**[PINNED] If CM emits events, it is a producer and must go through IG→EB**
Your platform explicitly includes **case/label emissions** as producers feeding IG. 

**[PINNED] Any CM-emitted bus event must use the canonical event envelope**
Required envelope fields: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` (plus optional pins/trace fields).  

**Deployment-shaped hint (already consistent with your ops blueprint):**
CM may optionally emit case events to `fp.bus.control.v1` for automation/observability, but CM’s authoritative truth still lives in `case_mgmt` DB timelines. 

---

## CM operating model in the larger network (behavioural, not internal design)

### CM’s lifecycle posture (externally visible)

**[PINNED] All meaningful case changes become timeline events.**
No “silent edits.” This is essential because CM is truth for the case story. 

### Joins CM must support (queryability expectations)

CM must be queryable by:

* `case_id`
* status/queue/assignee
* linked keys (event_id / decision_id / entity refs / request_id)
* time window (for investigation and reporting) 

### Time semantics CM must preserve

* Evidence keeps its own domain `ts_utc`; CM timeline has “who did what when” timestamps
* Labels preserve **effective_time vs observed_time** (CM must not collapse them) 

---

## Failure-mode expectations (outer behaviour)

These are the behaviours other components (and operators) must be able to rely on:

**[PINNED] If Label Store is down:**
CM may continue investigation work, but **cannot claim “truth label written”** until Label Store accepts the append. Label emission should be retryable/idempotent. (CM remains truth for its own timeline; label truth remains absent until written.) 

**[PINNED] If Actions Layer is down / denies:**
CM can record the request and show status, but the only authoritative execution outcome is AL’s immutable ActionOutcome (including DENIED). Manual override is still not a bypass.  

**[PINNED] If audit evidence is missing/unresolved:**
CM must be able to store the ref and show “evidence unavailable” rather than copying partial payloads into case truth. The case timeline can still progress (investigator notes/actions), but evidence resolution is fail-closed.  

---

## The “outer contract” summary we just pinned

If you want this in one tight statement we can treat as the anchor:

**[PINNED] Case Mgmt / Workbench is the system-of-record for cases + append-only investigation timelines; it consumes RTDL outputs only as by-ref evidence (IDs, refs, EB coords, audit pointers) within ContextPins scope; it emits ground-truth only via append-only LabelAssertions into Label Store (effective vs observed time preserved); and any human side effects are requested as ActionIntents executed by Actions Layer—optionally publishing control-plane case events through IG→EB using the canonical event envelope.**

---

Yes — there are a few **CM “component laws”** worth pinning **before** we even touch joins, because they determine what *kind* of joins are even valid (and they prevent hidden assumptions from leaking into the join discussion).

Here’s what I’d pin as **authoritative CM v0 laws**:

## 1) Scope of a case

**[PIN] Cases are run-scoped by default.**
Every case carries full **ContextPins** (`manifest_fingerprint, parameter_hash, scenario_id, run_id`). Evidence attached to the case must match those pins.

* Rationale: it prevents accidental “cross-world” cases and makes every join deterministic.
* Consequence: if you ever want cross-run investigation later, you do it explicitly as a *meta-case* (separate type), not by quietly mixing pins inside one case.

## 2) The one truth inside CM

**[PIN] CM’s only authoritative truth is the append-only case timeline.**
Anything that looks like “case header state” (status, assignee, priority) is **derived** from timeline events (even if cached/projection exists).

* Rationale: stops “silent edits” and keeps auditability clean.

## 3) Timeline event minimal shape

**[PIN] Every meaningful change is a timeline event with:**

* `case_event_id` (stable)

* `case_id`

* `event_type`

* `observed_at_utc` (when CM learned/recorded it)

* `actor` (principal: human or system)

* `payload` (structured details)

* Rationale: without this, you can’t define idempotency, concurrency behavior, or downstream proofs cleanly.

## 4) Concurrency posture

**[PIN] CM is multi-writer and conflict-tolerant; conflicts are represented, not prevented.**
Two investigators can both append events; projections resolve “current state” deterministically (e.g., ordered by `observed_at_utc`, tie-break by `case_event_id`).

* Rationale: avoids “locking is a hidden dependency” and keeps CM correct under retries/replays.

## 5) Idempotency rules (non-negotiable)

**[PIN] CM must be safe under at-least-once delivery.**
So we pin **idempotency keys** at three levels:

* case creation / trigger intake

* timeline event append

* outbound emissions (labels, manual actions)

* Rationale: without this, joins become unstable because duplicates change truth.

## 6) Evidence vs truth (the core philosophical pin)

**[PIN] CM stores evidence strictly *by reference*, never as copied authoritative payload.**
Evidence can be shown to a human, but it doesn’t become “case truth” unless a human/system writes a timeline event asserting something.

* Rationale: keeps CM from becoming a shadow Event Bus / shadow Audit Log.

## 7) Two lanes inside CM for engine artifacts

**[PIN] CM must separate:**

* **Investigation lane (authoritative):** CM timeline + investigator actions

* **Oracle/reference lane (non-authoritative):** engine `truth_products` and similar reference-only materials

* Rationale: prevents engine truth_products from silently replacing the platform’s human truth loop.

## 8) “Actor” is first-class

**[PIN] Every write requires an actor principal** (human user or system role), and CM records it on the timeline.

* Rationale: without it, you can’t defend “human-in-the-loop truth” or audit who asserted what.

## 9) CM does not own labels or actions

**[PIN] CM never treats labels or action outcomes as its own truth objects.**

* Labels are truth only in Label Store (CM records “I emitted / I saw ack” on timeline).

* Actions are truth only in Actions Layer (CM records request + pointers/outcomes on timeline).

* Rationale: preserves the platform’s truth-ownership map.

## 10) Optional publishing posture (so it doesn’t drift later)

**[PIN] If CM emits events externally, they are control-plane signals, not the primary record.**
The primary record stays the CM timeline.

---

If you accept those pins, then when we move to joins, we can do it with zero ambiguity because each join will be forced to answer:

* “What reference types are allowed?”
* “What pins must match?”
* “What’s the idempotency key?”
* “What timeline event(s) represent this interaction?”
* “What’s truth vs evidence vs reference-only?”

And that’s exactly how we avoid designing a join that later forces CM internals to become something it shouldn’t.

---

Yes — and we can be exhaustive **without opening CM** by enumerating every **production-valid edge** that touches the CM vertex, then listing the **end-to-end paths** and the **closed loops** that those edges create.

Below is the **complete join / path / loop inventory** for **Case Mgmt / Workbench (CM)** as an **opaque vertex**, constrained to what your authoritative platform design already allows.

---

## Legend for edge types (so we don’t mix meanings)

* **Traffic edge (via IG→EB):** producer submits candidate events → IG admits/quarantines/duplicates → EB appends/replays. 
* **Control edge (via IG→EB control topic):** low-volume “control facts” (READY, governance facts, registry lifecycle, optional case/label signals). 
* **By-ref artifact read:** CM reads immutable artifacts from object store via refs/locators (audit records, run join surfaces, engine truth_products).  
* **Authoritative service/API edge:** CM calls/uses the authoritative writer for a truth domain (Label Store, Actions Layer).  

---

## 1) The join set: all edges that can touch CM in a production platform

### A) Inbound edges into CM

**A1) Evidence pointers from RTDL (DF/AL/DLA → CM)**
CM receives *triggers + evidence refs* originating from **DF decisions**, **AL outcomes**, and **DLA pointers**; these are explicitly “evidence, not ground truth.”  

**A2) By-ref audit record reads (CM → `dla/audit/...`)**
CM reads the canonical flight-recorder evidence **by reference** from DLA’s immutable audit record set (object store), optionally aided by an audit index.  

**A3) Optional “audit pointer events” (DLA → EB audit topic → CM)**
DLA may emit *pointer events* (e.g., “audit record written at ref X”) to an audit topic; CM may consume these as “evidence is ready” signals.  

**A4) Optional EB history reads (CM ↔ EB)**
CM may read EB history for additional context (still **evidence**, never duplicating payloads as “case truth”). This is explicitly “optional read for history” in the deployment mapping. 

**A5) Label Store reads for context (Label Store → CM read surface)**
CM can read label timelines “as-of” from Label Store (for UI context / prior adjudications), while Label Store remains the only truth.  

**A6) External outcomes as inputs (disputes/chargebacks → CM workflow)**
Your platform explicitly calls out delayed external outcomes (e.g., disputes/chargebacks) as sources that produce label assertions. CM is the natural workflow surface for those. 

**A7) Engine reference material (SR join surface → engine truth_products → CM read-only “oracle lane”)**
CM may read **engine truth_products** (e.g., synthetic truth labels / case timelines) **only** as gated, immutable artifacts referenced from SR’s join surface; never as hot-path inputs.  

---

### B) Outbound edges from CM

**B1) CM → Label Store (J13)**
CM emits **LabelAssertions** into Label Store; labels become truth only once stored; label timelines preserve **effective_time vs observed_time** and are append-only with supersedes for correction.  

**B2) CM → Actions pathway (manual interventions)**
If a human action changes the world (block/release/notify/etc.), it must be expressed as an **ActionIntent** and executed by **Actions Layer**, with effectively-once semantics and immutable outcomes.  

**B3) Optional CM → IG → EB control (case events)**
CM may optionally emit **case status/timeline events** back to the stream for automation/audit, as control-plane signals (not the primary record).  

**B4) Optional Label Store → IG → EB control (label events)**
Label Store may optionally emit label events to the control topic; CM itself doesn’t have to publish labels to EB, but the platform allows control-plane propagation.  

**B5) Telemetry to Observability/Governance pipeline (CM → OTLP)**
Everything emits OTLP; ops telemetry routes into the observability pipeline (and can influence behavior only via explicit control surfaces like DL).  

---

### C) “CM participates indirectly” edges (CM is not on the edge, but the path passes through CM)

These matter because they create loops that come back to CM:

* **Label Store → Learning & Evolution** (Offline Shadow → Model Factory → Registry → DF) is a pinned loop that starts with CM-produced labels.  
* **Run/Operate / governance facts** can react to case/label events (control topic) and trigger backfills/replays (which then change what evidence shows up in CM).  

---

## 2) The path inventory: all production-ready end-to-end paths that involve CM

I’m listing these as **minimal sequences**; each is a distinct “shape” you must expect CM to coexist with.

### P1 — The canonical investigation path (evidence → case → label)

`DF decision / AL outcome / DLA pointer → CM → Label Store`  

### P2 — Evidence resolution path (case shows “why”)

`CM → (by-ref) DLA audit records (object store) → CM UI renders evidence`  

### P3 — “Human changes the world” action loop (manual intervention)

`CM → ActionIntent (must go through Actions Layer) → ActionOutcome → DLA evidence → CM`
Semantically pinned: action must go through AL, outcomes immutable, and CM consumes outcomes as evidence.  

(Transport-wise, this typically rides the same traffic spine used elsewhere: intents/outcomes are real traffic, so they live in the IG→EB world and DLA records them.  )

### P4 — CM optional publication path (case event as control fact)

`CM → IG → EB(control) → (automation/ops/gov consumers)`  

### P5 — Engine-to-case path via hot-path evidence (business traffic drives a case)

`Engine business_traffic → IG → EB → DF/AL/DLA evidence → CM`  

### P6 — Engine oracle/reference lane path (truth_products are readable but not traffic)

`SR run_facts_view (refs + proofs) → engine truth_products (gated, immutable) → CM (read-only reference)`  

### P7 — Delayed external truth path (chargeback/dispute becomes a label)

`External outcome → CM (as evidence/workflow) → Label Store (append-only assertion)`  

### P8 — Case-derived labels feed learning (start of the long evolution loop)

`CM → Label Store → Offline Shadow → Model Factory → Registry → DF → (new decisions) → CM`  

### P9 — Rebuild/backfill path that changes what CM can see (operational reality)

`Run/Operate triggers replay/backfill → projections/audit indexes refreshed → CM evidence/query experience changes (but truth ownership unchanged)`  

---

## 3) The loop inventory: all closed loops in a production-ready platform that pass through CM

These are the ones that matter for “production readiness” because they define feedback, drift risk, and safe operations.

### L1 — Human adjudication → learning → policy/model evolution → new decisions (the big loop)

`CM → Label Store → Offline Shadow → Model Factory → Registry → DF → decisions/actions → DLA evidence → CM`  

This is the platform’s **truth-to-learning** loop, and it is explicitly pinned as “Label & Case ↔ Learning & Evolution.” 

### L2 — Manual action loop (human acts, platform responds, CM sees outcome)

`CM → ActionIntent → AL executes → ActionOutcome → DLA records → CM`  

### L3 — “Case event” control loop (optional, but production-useful)

`CM → EB(control) → Gov/automation reacts → (may trigger backfill / config activation) → platform evidence shifts → CM`  

### L4 — External delayed truth loop (ground truth arrives later than decision time)

`Decision happens → later dispute/chargeback arrives → CM → Label Store timeline updates → future learning/decisions shift → CM sees new evidence patterns`  

### L5 — Engine oracle loop (evaluation harness loop; not hot-path)

`SR picks world → engine truth_products available → CM uses for evaluation/QA → (optionally drives human corrections) → Label Store → learning loop`
This exists only because truth_products are explicitly allowed for offline eval/tooling but forbidden from leaking into hot path.  

---

## 4) The “no-missing-edges” adjacency view (opaque CM vertex)

Here’s the full adjacency list (what CM can connect to), with “must vs optional”:

**Must-connect (production core):**

* `DF/AL/DLA → CM` (evidence pointers) 
* `CM → Label Store` (LabelAssertions; J13) 
* `CM → Actions Layer pathway` (manual ActionIntent; outcomes return as evidence) 
* `CM → DLA audit records (by-ref)` (evidence resolution) 

**Optional-but-valid (production useful, not required to be “CM exists”):**

* `CM ↔ EB` (read history context) 
* `CM → IG → EB(control)` (case events) 
* `Label Store → IG → EB(control)` (label events) 
* `CM ← external outcomes` (dispute/chargeback inputs) 
* `CM ← SR join surface → engine truth_products (gated)` (oracle/reference lane) 

---

Here’s the **ordered, complete production set** around the **CM (opaque vertex)** — ordered by **(1) truth/side-effect boundaries first, (2) evidence/context next, (3) optional publishing/signal edges last**, because that order prevents drift fastest.

---

## A) Production joins touching CM (ordered)

### Core joins (must-have)

1. **J-CM-01 — CM → Label Store (J13): LabelAssertions (append-only timelines)**
2. **J-CM-02 — CM → Actions Layer: Manual ActionIntents (via AL/IG path; AL executes, not CM)**
3. **J-CM-03 — DF/AL/DLA pointers → CM: case triggers + evidence refs (by-ref)**
4. **J-CM-04 — CM → DLA object truth: read `dla/audit/...` by-ref evidence** 
5. **J-CM-05 — Label Store → CM: as-of label reads (context for investigators)**

### Optional-but-production-valid joins

6. **J-CM-06 — CM → IG → EB(control): optional case events for automation/obs** (must use canonical envelope if emitted)
7. **J-CM-07 — CM ↔ EB: optional history reads for UI context (still evidence, not copied truth)** 
8. **J-CM-08 — DLA → EB(audit) → CM: optional audit pointer events (evidence-ready signals)** 
9. **J-CM-09 — Label Store → EB(control) → CM: optional label events (control-plane propagation)** 
10. **J-CM-10 — SR join surface → Engine truth_products → CM: optional “oracle/reference lane” reads** (by-ref + PASS-required; never hot-path traffic)
11. **J-CM-11 — CM → Obs/Gov pipeline: OTLP metrics/traces/logs (platform law)**

> That’s the full adjacency set that’s explicitly allowed by your pinned platform + deployment mapping.

---

## B) Production paths involving CM (ordered)

1. **P-CM-01 — Human truth loop (core):** `DF/AL/DLA pointers → CM → Label Store (as-of reads back into CM)`
2. **P-CM-02 — Manual intervention path (core):** `CM → ActionIntent → (AL executes) → Outcome → DLA audit → CM`
3. **P-CM-03 — Evidence resolution path (core):** `CM case view → by-ref read of `dla/audit/...` (optionally EB history) → CM UI renders` 
4. **P-CM-04 — Engine traffic → case path (core, upstream-to-CM):** `Engine business_traffic → IG → EB → DF/AL/DLA → CM`
5. **P-CM-05 — Case-event publication path (optional):** `CM → IG → EB(control) → automation/ops consumers`
6. **P-CM-06 — Labels → learning/evolution path (long path):** `CM → Label Store → Offline Shadow → Model Factory → Registry → DF → (new decisions) → CM`
7. **P-CM-07 — Governed change/backfill path (ops reality):** `Run/Operate governance facts/backfill → (replays/rebuilds) → downstream context shifts → CM experience changes (without changing truth ownership)`
8. **P-CM-08 — Engine oracle/reference path (optional, offline-ish):** `SR run_facts_view → engine truth_products (gated) → CM reference lane → (may influence investigator) → Label Store`
9. **P-CM-09 — External adjudication intake (optional, production-common but not pinned by blueprint):** `External feed (e.g., disputes/KYC) → CM workflow → Label Store`

---

## C) Production loops that pass through CM (ordered)

1. **L-CM-01 — Truth → learning → decisions → truth loop (primary platform feedback loop):**
   `CM → Label Store → Offline Shadow → Model Factory → Registry → DF → decisions/actions/audit → CM`

2. **L-CM-02 — Manual action loop (primary operational loop):**
   `CM → ActionIntent → AL → Outcome → DLA → CM`

3. **L-CM-03 — Control-plane automation loop (optional):**
   `CM case events → EB(control) → ops/automation/gov reactions → (policy/backfill/ops actions) → evidence/context shifts → CM`

4. **L-CM-04 — Replay/backfill loop (must exist in prod):**
   `Governance facts (backfill/replay) → EB replays/rebuilds → IEG/OFP/DLA refreshed → CM sees updated evidence context`

5. **L-CM-05 — Engine oracle evaluation loop (optional, safety-gated):**
   `SR world → truth_products → CM reference lane → (human correction) → Label Store → learning loop`

6. **L-CM-06 — Delayed-truth loop (optional, production-common):**
   `Decision happens → later external adjudication arrives → CM → Label Store → learning/decision shifts → CM`

---

Absolutely. We’ll expand the **first 5 (core) CM joins** as **production-grade boundary designs**, while keeping CM’s internals opaque.

I’ll do each join in the same structure:

* **Role of the join**
* **What crosses the boundary**
* **Non-negotiable laws (pins)**
* **Idempotency + duplicates**
* **Failure posture**
* **Security/control posture**
* **What CM must record in its own case timeline about the join**

---

## J-CM-01 — CM → Label Store (J13): LabelAssertions (append-only timelines)

### Role

This is the **human ground-truth entry point**. CM is the workflow that *produces* assertions; Label Store is the **only truth writer** for labels.

### What crosses the boundary

A **LabelAssertion** write request (and an ACK response). At minimum, every assertion must carry: subject, value (+ optional confidence), provenance, **effective_time**, **observed_time**.

### Pinned laws (must hold in production)

* **[PIN] Label Store is append-only.** No destructive edits; corrections happen by writing a new assertion that supersedes in interpretation while history remains.
* **[PIN] “Label becomes truth only once stored.”** CM cannot claim “truth label applied” until it receives Label Store acceptance.
* **[PIN] Effective vs observed time must not be collapsed.** (This is central to leakage-safe “as-of” reads later.)

### Idempotency + duplicates (production reality)

* **[PIN] Label writes must be idempotent.** Duplicate submissions must not create multiple logical labels.
* **Authority choice (v0):** CM derives a deterministic `idempotency_key` from the *case timeline event* that triggered labeling (e.g., `case_id + disposition_event_id`), and Label Store uses that as the uniqueness scope for the assertion.
  This makes retries safe and aligns with your platform’s “at-least-once everywhere” posture.

### Failure posture

* If Label Store is down/slow: **CM continues investigation**, but shows the label as **PENDING** and keeps retrying. CM must never “fake success.”
* If Label Store rejects (schema, auth, invalid subject): CM records **REJECTED** with reason and keeps the case resolvable (humans can adjust / re-emit).

### Security/control posture (choke point)

* **[PIN] Label writes are controlled at Label Store.** Only trusted writers (case workflow/adjudication ingest) may write; writes are auditable; no destructive edits.
* CM should pass through the **human actor identity** as provenance even if the service identity is the authenticated writer.

### What CM must record (externally visible expectation)

CM’s own timeline should record, at minimum:

* “Disposition set” (human intent)
* “LabelAssertion submitted” (with idempotency key + subject summary)
* “LabelAssertion accepted/failed” (with returned label_assertion_id or error)

This preserves the “CM is truth for the investigation story” while labels remain Label Store truth.

---

## J-CM-02 — CM → Actions Layer: Manual ActionIntents (AL executes, not CM)

### Role

This is the **only legal path for human side effects**. “Manual action” is **not a bypass**: it’s an ActionIntent with higher privilege, executed only by AL.

### What crosses the boundary

A **Manual ActionIntent** request that is semantically the same class of object DF sends (intent ≠ execution), carrying:

* ContextPins + join identifiers (bind it to run/world and target)
* Deterministic `idempotency_key` 
* Actor principal + origin = `manual_case` (or equivalent) 
* Action type + scoped target (entity/event)
* Evidence refs justifying the action (by-ref pointers)

### Pinned laws

* **[PIN] Only AL executes.** CM can only request.
* **[PIN] Effectively-once via `(ContextPins, idempotency_key)`.** Duplicates never re-execute; AL re-emits the canonical outcome.
* **[PIN] Every attempt yields an immutable ActionOutcome** (including denial/failure).
* **[PIN] Intents/outcomes are “real traffic”** in the platform spine (IG→EB), even though this join is about semantic authority.

### Idempotency + duplicates (v0 choice)

* **[PIN] CM must generate deterministic idempotency keys** for manual actions (e.g., derived from the CM timeline event that requested the action).
* **Authority choice (v0):** treat “same intent” as: same `(ContextPins, action_type, target_ref, requested_by, idempotency_key)`.

### Failure posture

* If AL is unavailable: CM records **REQUESTED (pending)** and the UI reflects “awaiting execution.”
* If AL denies: denial is an **ActionOutcome**; CM records the denial and does not attempt alternate execution paths.

### Security/control posture (choke point)

* **[PIN] AL authorization is allowlist-based** by `(actor_principal, action_type, scope)`. Unauthorized → Denied outcome (still immutable, still idempotent).
* CM must always send **actor principal**; “manual action” is higher privilege but still policy-governed.

### What CM must record

CM’s timeline must capture:

* the **request** (action type/target, actor, idempotency key)
* the **outcome pointer** (ActionOutcome id / audit ref)
* the resolution state: executed / denied / failed

(Outcome evidence typically returns via the DF/AL/DLA→CM evidence join.)

---

## J-CM-03 — DF/AL/DLA pointers → CM: case triggers + evidence refs (by-ref)

### Role

This join is how the **real-time decision loop** feeds the **human truth loop**: RTDL outputs are **evidence**, not ground truth. CM consumes pointers and builds the case story.

### What crosses the boundary

A **CaseTrigger / EvidencePointer** (conceptually) that includes:

* stable IDs (decision_id, event_id, action_intent_id, action_outcome_id, audit_record_ref, etc.)
* ContextPins when it’s run/world scoped
* minimal severity/route hints (optional)
* timestamps (when detected/produced)

(Importantly: **no raw payload copy required**; pointers are enough because DLA is the flight recorder and EB is replayable context.)

### Pinned laws

* **[PIN] Evidence is by-ref.** CM is not a shadow event bus or shadow audit store.
* **[PIN] CM must be at-least-once safe.** Duplicate triggers must not create duplicate cases or duplicate timeline entries.
* **[PIN] Run/world pin integrity.** If CM is run-scoped (your earlier pin), then incoming pointers must match the case’s ContextPins or be rejected/segregated.

### “Production-ready” clustering expectation (without opening CM)

Even with CM opaque, production requires a deterministic stance on what happens when a trigger arrives:

* **Create new case** (if no open case matches the join keys)
* **Attach to existing case** (if there is an existing open case for the same join keys)
* **Escalate** (if severity crosses a threshold)

**Authority choice (v0):** matching key is *first* `(run pins + primary subject)` and *second* `(decision_id/event_id/entity_ref)` — so you don’t end up with unpredictable clustering. (Exact algorithm is internal; the *principle* is what prevents drift.)

### Failure posture

* If DLA pointer exists but audit record is not yet readable: CM can still open/attach a case but marks evidence as **PENDING/UNRESOLVED** (fail-closed on details).
* If pointers are malformed/unjoinable: CM records the trigger as **rejected/quarantined** (internally) but should never silently drop—mirrors the platform’s explicit-outcome posture.

### What CM must record

For every accepted trigger/evidence pointer:

* “trigger received” with source (DF/AL/DLA), ids, pins
* “case created/attached” decision
* “evidence ref attached (unresolved/resolved)”

That’s the minimum to keep investigations reproducible.

---

## J-CM-04 — CM → DLA object truth: read `dla/audit/...` by-ref evidence

### Role

DLA is the **immutable flight recorder**. CM reads it to show “why did the system decide/do that?” without copying raw payloads.

### What crosses the boundary

Primarily: **by-ref reads** of immutable audit records from the object store prefix `dla/audit/...`.
Optionally: queries via an `audit_index` for lookup by decision_id / event_id (recommended but not required).

### Pinned laws

* **[PIN] Append-only audit record set; corrections via supersedes chains.** No overwrites.
* **[PIN] Quarantine on incomplete provenance.** DLA must not silently write “half-truth” audit records.
* **[PIN] CM stores only refs, not embedded audit payload.**

### How CM must behave with supersedes/corrections

**Authority choice (v0):**

* CM can display the record it referenced *and* surface “this was superseded” if a newer record exists.
* CM must not silently swap evidence without leaving a trace in the case timeline (otherwise investigators can’t reproduce what they saw).

(How CM discovers supersedes can be via audit_index or DLA pointer events; mechanism can stay loose.)

### Failure posture

* If audit record missing/unavailable: CM shows **unavailable** (fail-closed) but preserves the pointer and allows the investigation to proceed.
* If audit record is quarantined: CM should display “quarantined” and show the quarantine pointer only to authorized roles (ops/investigator).

### What CM must record

When an audit record is attached/used:

* the audit record ref (`dla/audit/...`)
* whether it was resolved successfully
* whether it was later discovered to be superseded

---

## J-CM-05 — Label Store → CM: as-of label reads (investigator context)

### Role

CM needs label truth for context (“has this entity/event been adjudicated?”), but must do so **leakage-safely** and **time-aware** because labels are timelines.

### What crosses the boundary

Read queries from CM to Label Store that return:

* label timelines for a subject (entity/event/flow)
* with **effective_time** and **observed_time**
* and an **as-of** boundary option (critical).

### Pinned laws

* **[PIN] Label Store supports leakage-safe “as-of” reads** using effective vs observed time semantics.
* **[PIN] Labels are timelines, not update-in-place.** CM must expect multiple assertions and supersedes behavior.

### The key “as-of” stance CM must adopt (authority choice)

To avoid confusion and to support reproducibility:

* **Default investigator view:** show **Current truth** (as-of now) *and* optionally a “Known at time of decision” view.
* “Known at time of decision” should be an as-of read where **as-of is on observed_time** (what was known then), not on effective_time (what it applied to). This matches your leakage discipline used elsewhere (Offline Shadow as-of posture).

(UI can decide how it renders, but the join semantics must allow both.)

### Failure posture

* If Label Store is unavailable: CM can still run investigations, but labels in the UI become “unavailable,” and CM must not invent cached truth as authoritative. (Cache is allowed as a performance layer, not as truth.)

### What CM must record

CM should record (in the case timeline) when a disposition/label decision was made, including:

* what label context was used (e.g., “as-of boundary used” when relevant)
  This makes later review defensible (“we decided with only what we knew at that time”).

---

If you want to proceed in the most drift-killing order *within these five*, the next step is:

1. **Lock the exact “Disposition → LabelAssertion mapping posture”** (J-CM-01),
2. **Lock the ActionIntent shape for manual actions + idempotency source** (J-CM-02),
3. Then we tighten the **minimal CaseTrigger/EvidencePointer shape + dedupe/clustering principle** (J-CM-03),
4. Then the **DLA supersedes/quarantine display posture** (J-CM-04),
5. Then the **as-of read default** (J-CM-05).

Your call which one you want to expand first.

---

Yep — let’s expand **A6–A11 (J-CM-06 … J-CM-11)** as **production-valid optional joins**, keeping **CM opaque** and staying inside your pinned platform laws.

---

## J-CM-06 — CM → IG → EB(control): optional case events (automation/obs)

### Why this join exists (and what it is *not*)

* **Purpose:** low-volume **signals** for automation, visibility, and governance-like tracking (e.g., “case opened”, “case escalated”, “case resolved”, “investigator disposition set”).
* **Not:** the primary case record. **Case truth remains CM’s DB timelines**; this is a mirror/signal stream.

### What crosses the boundary

CM acts as a **producer** (explicitly allowed: “case/label emissions” feed IG).
So every emitted case event must:

* go **CM → IG (admit/quarantine/duplicate + receipt) → EB**, and
* conform to the **canonical event envelope** at the boundary.

**Envelope minimum (non-negotiable):** `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` (and optional ContextPins, trace fields, producer, etc.).

### Production pins for this join

* **[PIN] Case events are “control facts,” not payload dumps.** Payload should be **by-ref friendly** (IDs + pointers), not full evidence blobs or sensitive user data.
* **[PIN] Idempotent emission:** the event_id must be stable under retries (best: derived from the CM timeline event that caused the emission). This aligns with IG’s duplicate handling posture.
* **[PIN] Joinability:** if the case is run/world scoped (your default), include the ContextPins (`parameter_hash`, `scenario_id`, `run_id`, etc.) so downstream automation doesn’t accidentally cross worlds.

### Failure posture

* If IG quarantines a case event: CM continues operating normally (truth stays in CM); this is **signal loss**, not truth loss. CM should still record “attempted publish” + receipt pointer in its own timeline for later troubleshooting.

### Typical consumers (why you’d bother)

* Ops dashboards, “case throughput / backlog”, alerting on escalations
* Automation that opens follow-up tasks, notifies an on-call, or tags related cases
* Governance/reporting surfaces (still not domain truth)

---

## J-CM-07 — CM ↔ EB: optional history reads for UI context (evidence only)

### Why this join exists

Deployment notes explicitly allow CM “optional read for history.”
This join exists so investigators can see “what happened around the event/decision” **without CM copying the event stream into its own truth store**.

### What CM is allowed to do

* **Read admitted events** from EB (typically `fp.bus.traffic.v1`) to render context.
* Optionally store **pointers** to EB positions (topic/partition/offset) as evidence refs (still by-ref posture).

### Production pins for this join

* **[PIN] EB history is evidence, not case truth.** CM must never “import” event payloads as authoritative case facts; only references and investigator assertions become case truth.
* **[PIN] Retention-aware:** EB is replayable within retention; beyond retention, CM must fall back to DLA audit refs for forensic continuity (that’s what the flight recorder is for).
* **[PIN] No cross-run mixing:** CM’s read queries must respect ContextPins; “show me the transaction” must mean “show me the admitted event for this run/world scope.”

### Failure posture

* If EB read fails (lag, retention expired, network): CM shows “unavailable” and relies on DLA refs; it must not silently substitute cached payloads as truth.

---

## J-CM-08 — DLA → EB(audit) → CM: optional audit pointer events (“evidence-ready” signals)

### Why this join exists

Your deployment map explicitly allows **DLA pointer events → `fp.bus.audit.v1`**.
This is the “fast notify” path: CM can update a case UI quickly when the flight recorder has written something new, without polling object storage.

### What crosses the boundary

* On `fp.bus.audit.v1`: **pointer events**, not audit payload.
* Payload should carry:

  * **by-ref audit locator** (e.g., `dla/audit/...`)
  * the correlated IDs (decision_id / action_intent_id / action_outcome_id / event_id)
  * optional supersedes link if applicable

This stays consistent with “audit is immutable objects; bus events are pointers.”

### Production pins for this join

* **[PIN] Pointer events are hints, not the record.** CM must still fetch the actual audit record by ref when needed.
* **[PIN] Stable correlation keys included.** Your observability baseline pins correlation discipline so we can join “event → decision → action → audit.” CM benefits from the same keyset.
* **[PIN] Idempotent pointers:** multiple pointer events for the same record are safe (dedupe by audit_record_id / locator digest).

### Failure posture

* If CM misses pointer events: nothing breaks — CM can still resolve evidence by reading `dla/audit/...` refs already attached or discovered via normal flow. This join improves UX/latency, not correctness.

---

## J-CM-09 — Label Store → EB(control) → CM: optional label events (control-plane propagation)

### Why this join exists

Deployment map: **Label Store can emit optional label events → `fp.bus.control.v1`.**
This is useful when:

* labels can be written by more than one trusted writer (CM + adjudication ingest + back-office workflow),
* and you want near-real-time UI updates without CM polling Label Store.

### What crosses the boundary

* A **label-appended signal** (control fact), ideally containing:

  * label_assertion_id (or stable ref)
  * subject key(s)
  * effective_time + observed_time (or at least pointers so CM can query full truth)
  * provenance actor (or a pointer to it)

### Production pins for this join

* **[PIN] Label events are not label truth.** Label truth remains in Label Store DB timelines; CM uses the event as a “something changed, go read truth” nudge.
* **[PIN] Append-only + supersedes is expected.** CM must tolerate multiple assertions and corrections.
* **[PIN] By-ref friendliness:** don’t broadcast sensitive label payloads; broadcast identifiers/pointers and let authorized reads pull truth.

### Failure posture

* If label events are missing/delayed: CM still remains correct by reading Label Store as-of; only “freshness of UI” degrades.

---

## J-CM-10 — SR join surface → Engine truth_products → CM: optional oracle/reference lane reads

### Why this join exists (and why it’s fenced)

Your blueprint pins:

* **No PASS → no read**, and no scanning; SR is the broker of join surface.
* **Truth products never leak into the hot path** (offline eval/training/test harness only unless explicitly promoted as a major decision). 

So CM may read truth_products only as a **reference/oracle lane** for:

* evaluation (“what is the synthetic ground truth?”),
* QA of investigations (“investigator labels vs oracle truth”),
* test harness support.

### What crosses the boundary

* CM starts from **SR’s run_facts_view** (by ref) to obtain:

  * explicit locators to truth_products
  * required PASS evidence for the pinned scope
* CM then reads the truth product artifact by-ref from object storage.

### Production pins for this join

* **[PIN] Explicitly separate lanes in CM UX/semantics:** oracle material must never silently overwrite or “become” the case’s investigation truth. It is displayed as reference only.
* **[PIN] Authorization-gated:** in real deployments, oracle access is typically restricted (security envelope difference is allowed; semantics remain the same: “if authorized + PASS + ref, you may read”).
* **[PIN] Immutable posture:** if oracle truth changes, it happens via a new artifact identity / new run join surface — CM never “patches” it.

### Failure posture

* If PASS proof missing or refs absent: CM must fail closed (“oracle unavailable”), never “best effort.”

---

## J-CM-11 — CM → Obs/Gov pipeline: OTLP metrics/traces/logs (platform law)

### Why this join exists

You’ve pinned observability as a **platform law** (OTLP everywhere; correlation keys everywhere; golden signals; trace propagation; “no silent changes”).

### What CM must emit (minimum viable, CM-specific)

**Metrics (golden + CM-specific):**

* Throughput: commands processed / timeline appends / searches
* Latency: p95 for case read, timeline append, label emission, action request
* Error rates: by class (auth, validation, downstream unavailable)
* Saturation: worker backlog / queue depth
* Domain safety: “pending label writes”, “pending actions”, “unresolved evidence refs” counts

**Traces:**

* Preserve incoming `trace_id/span_id` when present, and create spans for:

  * “case command accepted”
  * “label assertion submitted”
  * “action intent submitted”
  * “evidence resolved”

**Logs:**

* Structured, by-ref, safe:

  * log boundary decisions (“created case”, “attached evidence ref”, “submitted label”, “requested action”)
  * never dump raw payloads by default

**Correlation keys rule (critical):**
CM telemetry must include the applicable subset of:

* ContextPins (`manifest_fingerprint`, `parameter_hash`, `scenario_id`, `run_id`, `seed` when relevant)
* event/decision/action IDs when the case is joined to them
* component identity + policy_rev where applicable

### Failure posture

If observability backend is down: CM still functions; telemetry buffers/drops per policy, but CM must never make domain decisions contingent on telemetry availability (except via explicit Degrade Ladder inputs elsewhere).

---

# One unifying “authority choice” for A6–A11 (so these joins don’t drift)

**[PIN] All A6–A11 joins are “signals or reads,” not truth transfers.**

* The only truth transfers out of CM are **(1) its own case timeline DB truth, (2) LabelAssertions via Label Store, (3) ActionIntents via AL**.
  Everything here (A6–A11) is either:
* a **control/audit signal** carried on EB topics, or
* a **read-only context source** (EB history, DLA refs, SR→truth_products), or
* **telemetry**.

This keeps CM from turning into a shadow bus/audit/label store while still being production-useful.

---

Yep — **B1–B4** are the **outbound CM-facing joins** that make CM “real” in production shape (labels + manual actions + optional control-plane signals). These are explicitly called out in your deployment map.

I’ll expand each as an **authoritative outer-join design** (CM remains opaque).

---

## B1 — CM → Label Store: LabelAssertions (J13)

### What this join *is*

CM is the **workflow + provenance capture** for human adjudication; Label Store is the **single truth writer** for labels. The label becomes truth **only once stored**.

### What crosses the join

A **LabelAssertion** write request (and an ack/receipt), with these **non-negotiables**:

**[PIN] Labels are timelines:** append-only assertions, corrections via new assertions (supersedes in interpretation), never “update-in-place.”
**[PIN] Time duality is preserved:** every assertion must carry **effective_time** and **observed_time** (do not collapse them).
**[PIN] Provenance is first-class:** actor (human), workflow origin (CM), and the case linkage must be present.

### Authority choices to lock now (so B1 can’t drift)

**[PIN] CM emits “assertions”, never “labels-in-case”.**
CM may show labels in UI, but CM never stores label truth as its own state; it only stores that it *attempted/emitted* an assertion + the resulting acceptance/denial.

**[PIN] Idempotency anchor:** the idempotency scope for a label write is derived from the CM timeline event that caused it (e.g., `case_id + disposition_event_id`).
Reason: platform is at-least-once shaped; CM retries must not create multiple logical labels.

**[PIN] “Late truth is normal.”**
CM must treat late dispute/chargeback style outcomes as legitimate new assertions (often with effective_time in the past, observed_time now).

### Failure posture (production-true)

* **Label Store down:** CM continues investigation and records “label pending”; it must not claim truth.
* **Label Store rejects:** CM records rejection + reason and keeps the case resolvable (investigator can re-assert).

### What CM must record about B1 (externally expected)

CM timeline must be able to show:

1. **Disposition set** (human intent)
2. **Assertion submitted** (idempotency key + subject)
3. **Accepted / Rejected / Pending** (with returned `label_assertion_id` or error)

This keeps “investigation truth” (CM) separate from “label truth” (Label Store).

---

## B2 — CM → Actions Layer (via AL/IG path): Manual ActionIntents

### What this join *is*

CM can request human-driven side effects, but **CM never executes actions**. Actions Layer is the sole executor, using effectively-once semantics and immutable outcomes.

Deployment shape explicitly pins: “Manual actions submitted as ActionIntents (via AL/IG path).” 

### What crosses the join

A **Manual ActionIntent** request with:

* **ContextPins + join IDs** to bind to the correct run/world and evidence basis
* a **deterministic `idempotency_key`** 
* **actor principal** (human) + origin marker (manual / CM)
* action type + scoped target (entity/event refs)
* evidence refs justifying the action (by-ref pointers to DLA/EB coords)

### Pinned semantics (imported from the platform’s Actions law)

The platform already pins this for DF→AL; we apply the same semantics to CM manual intents:

**[PIN] Uniqueness scope:** AL enforces effectively-once using **(ContextPins, idempotency_key)**. Duplicates never re-execute; they re-emit the canonical outcome.
**[PIN] Outcomes are immutable:** every attempt yields an ActionOutcome (including denial/failure).

### Authority choices to lock now

**[PIN] Manual action is policy-governed, not “superuser mode.”**
AL must authorize manual actions by (actor, action_type, scope). Denials are still outcomes and must be recorded.

**[PIN] CM tracks “intent + outcome pointer”, not execution details.**
Execution details belong in AL (and then DLA audit). CM consumes them as evidence.

### Failure posture

* **AL unavailable:** CM records “action requested (pending)” and retries idempotently.
* **AL denies:** CM records denial and does not attempt a bypass.

### What CM must record about B2

At minimum:

* ActionIntent request (actor, type, target, idempotency_key)
* Status: pending / accepted / executed / denied / failed
* Outcome pointer(s) once available (often via DLA evidence refs)

---

## B3 — CM → IG → EB(control): Optional case events

### What this join *is*

A **control-plane signal stream** for automation/visibility, not the primary case record. CM truth stays in `case_mgmt` timelines.

Deployment pins: “optional case events → `fp.bus.control.v1`.”

### What crosses the join

CM becomes a producer, so it must go through **IG** (admit/quarantine/duplicate + receipts) before **EB**.

**[PIN] Envelope:** if CM emits a case event, it must conform to the **Canonical Event Envelope** (required: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`).

### What CM is allowed to put in the payload (authority choice)

**[PIN] Payload is “pointers + summaries”, not sensitive dumps.**
Recommended payload contents are:

* `case_id`
* `case_event_id` (or “case timeline event pointer”)
* new status/priority/assignee (small fields)
* linkage keys (decision_id/event_id/entity_ref)
* optional refs to DLA/audit pointers if needed

### Idempotency posture

**[PIN] event_id is derived from the CM timeline event that caused publication.**
So retries and replay do not produce extra case events in EB control.

### Failure posture

* If IG quarantines a case event: CM continues (truth unaffected). This is **signal degradation**, not truth corruption. CM may record publish failure for ops.

---

## B4 — Label Store → IG → EB(control): Optional label events

### What this join *is*

A control-plane notification that “label timelines changed,” useful for UI freshness and automation, but **not label truth**. Label truth remains in `label_store` DB timelines.

Deployment pins: “Label Store … optional label events → `fp.bus.control.v1`.”

### What crosses the join

A “label appended / label corrected” **control fact**, ideally carrying:

* `label_assertion_id` (or stable pointer)
* subject keys
* effective_time + observed_time (or enough to retrieve them)
* provenance pointer

(And like all bus events: it goes via IG and uses the canonical envelope.)

### Authority choices to lock now

**[PIN] Label events are “go read truth” nudges.**
Consumers (including CM) treat them as triggers to query Label Store as-of, not as an authoritative payload.

**[PIN] Corrections are normal.**
Label events must tolerate supersedes chains; consumers must not assume “one subject → one label.”

### Failure posture

* If label events are missing/delayed: correctness holds because consumers can read Label Store directly; only freshness suffers.

---

## The key “outer network truth” to keep B1–B4 coherent

**[PIN] B1/B2 are *truth-changing joins* (they create new truth in other authoritative stores).
B3/B4 are *signal joins* (they do not create truth; they announce that truth exists elsewhere).**

---

Cool — we’ll expand **P-CM-05 → P-CM-09** as **production-grade path narratives** (still treating **CM opaque**), focusing on **what the platform expects to be true end-to-end**, what evidence exists, and how drift is prevented.

---

## P-CM-05 — Case-event publication path (optional)

**Path:** `CM → IG → EB(control) → automation/ops consumers`

### Why this exists

This path exists to make CM *observable and automatable* **without** turning EB into “the case database.” CM’s authoritative truth remains `case_mgmt` timelines; the bus carries **signals**.

### Production truth to pin

* **[PIN] If CM emits anything, it is a producer and must go through IG.** “Only one front door”: anything that can influence ops automation must enter via **IG → EB**.
* **[PIN] Canonical envelope is mandatory.** Required fields include `event_id, event_type, ts_utc, manifest_fingerprint` (plus optional pins like `run_id`, `parameter_hash`, etc.).
* **[PIN] Case events are control facts, not payload dumps.** Emit IDs + pointers + small summaries; keep evidence by-ref.
* **[PIN] Idempotency must hold at the boundary.** IG is at-least-once; CM case event replays must not produce “new” case facts on the control stream.

### What “good” looks like operationally

A typical production emission pattern is:

1. CM appends an internal case timeline event (truth).
2. CM **optionally** mirrors that as a control-plane signal (e.g., `case.opened`, `case.escalated`, `case.resolved`) to `fp.bus.control.v1`.
3. IG decides **ADMIT/DUPLICATE/QUARANTINE** and returns a receipt pointer; EB is the durable record of the admitted signal.

### Failure posture (important)

* **If IG quarantines** a case event, CM truth is unaffected; the signal didn’t make it. Quarantine is first-class, not silent loss.
* This path should degrade as “less automation / less freshness,” never as “corrupt case truth.”

---

## P-CM-06 — Labels → learning/evolution path (the long loop)

**Path:** `CM → Label Store → Offline Shadow → Model Factory → Registry → DF → (new decisions) → CM`

This is the **platform’s main improvement loop**. It’s where CM’s output becomes future production behaviour.

### Stage 1: CM → Label Store (ground truth creation)

* **[PIN] Label Store is the only label truth used for learning.** Learning never infers labels from outcomes or “what DF decided.”
* **[PIN] Labels are timelines** with `effective_time` vs `observed_time`; corrections are new assertions (append-only).
* **CM’s only job here:** emit LabelAssertions with proper provenance + time semantics; CM does not dictate training semantics.

### Stage 2: Label Store + EB/Archive → Offline Feature Plane Shadow

Offline Shadow’s pinned mission is **deterministic reconstruction** of training snapshots/datasets “as-of time T.”

Production truths:

* It reads event history from **EB within retention**, and from an **archive beyond retention** (treated as the same logical fact stream).
* It reads labels using **explicit as-of rules** to prevent leakage (effective vs observed time, as-of boundary).
* It records its **basis** (window by offsets or time tied to offsets, as-of boundary, feature definitions/versions used, parity anchors).

### Stage 3: Offline Shadow → Model Factory (DatasetManifests)

* **[PIN] Offline Shadow hands over DatasetManifests, not ad-hoc tables.** A DatasetManifest pins identity, time window/as-of boundaries, join keys/entity scoping, feature group versions, digests/refs, and provenance.

### Stage 4: Model Factory → Registry (deployable bundles + evidence)

* **[PIN] A bundle is a deployable package with identity + immutable refs/digests + training provenance + eval evidence + PASS/FAIL receipts where required.**
* **[PIN] Registry is the only deployable truth.** Nothing in RTDL loads “a model file” directly.
* **[PIN] Promotion/rollback is auditable.** Registry lifecycle is append-only truth evolution.

### Stage 5: Registry → DF → new decisions → CM

* DF resolves the **active bundle deterministically** and **fails closed** if incompatible with feature versions or degrade constraints; it records the resolved bundle ref in provenance.
* That changes what DF emits (decisions + ActionIntents), which creates new DLA evidence and therefore new CM triggers (via the normal DF/AL/DLA → CM evidence join).

**Net effect:** CM’s adjudications become future “system instincts,” but only through the governed Registry gate, never through side channels.

---

## P-CM-07 — Governed change/backfill path (ops reality)

**Path:** `Run/Operate governance facts/backfill → (replays/rebuilds) → downstream context shifts → CM experience changes`

This path is what makes the platform **operable over time** without “time travel corruption.”

### What Run/Operate is allowed to do

* It triggers jobs (including backfills), writes governance facts (`gov/...` + control topic), and manages retention/backfill runs.
* **[PIN] Backfill is explicit, scoped, auditable** and produces *new derived artifacts/state*; never silent overwrites.

### What can be backfilled vs cannot (critical)

* **Can backfill (derived):** IEG projections, OFP state, offline datasets/manifests, audit indexes, analytics views.
* **Cannot backfill as “truth mutation”:** EB admitted events, Label Store timelines, Registry lifecycle history, SR run ledgers, engine outputs for a pinned identity (immutable).

### Why CM cares (even though CM truth doesn’t change)

CM’s **case timelines** remain authoritative and unchanged — but the *context CM can resolve/render* can shift:

* Audit index rebuilt → evidence lookup becomes faster / newly joinable.
* OFP/IEG rebuilt → derived “context views” used elsewhere update (but EB facts didn’t change; watermarks remain meaningful).
* Retention policy changes → EB history availability changes; archive becomes necessary for long-horizon investigations. Governance facts must make this visible.

### CM’s production expectation on this path

* **[PIN] CM must tolerate “context re-materialization” without rewriting case truth.**
* **[PIN] CM must not pretend history changed.** If something becomes resolvable later (because a derived index was rebuilt), CM can show it as newly available, but it must not silently rewrite what an investigator previously saw.

---

## P-CM-08 — Engine oracle/reference path (optional, fenced)

**Path:** `SR run_facts_view → engine truth_products (gated) → CM reference lane → (may influence investigator) → Label Store`

This is the “synthetic oracle” loop: **truth_products exist**, but must never leak into the hot path.

### What the engine contract pins

* Engine outputs have binding roles: `business_traffic` vs `truth_products` vs `audit_evidence` vs `ops_telemetry`.
* **truth_products are for supervision/eval/case tooling; not traffic.**
* **No PASS → no read** is mandatory; gate verification is gate-specific.
* Downstream is forbidden from scanning engine outputs; it must start from SR’s join surface (`run_facts_view`).

### Production truth to pin for CM

* **[PIN] CM must maintain a strict “oracle lane”.** Oracle materials are *reference-only*; they never replace CM’s investigation truth and never become business traffic.
* **[PIN] Default reveal posture (designer decision):** oracle truth_products should be **hidden until after an investigator commits a disposition**, unless the run is explicitly a “training/QA mode.”
  Reason: prevents “rubber-stamping the oracle” and preserves the ability to measure investigator accuracy vs oracle. (Still consistent: oracle exists; access is a UI/policy choice, not a semantic change.)

### How this path closes into labels

An investigator may use oracle comparisons to **correct** a disposition; that becomes a new LabelAssertion (append-only truth evolution).

---

## P-CM-09 — External adjudication intake (optional but production-common)

**Path:** `External feed (disputes/KYC/etc.) → CM workflow → Label Store`

This is where “ground truth arrives late” from outside the RTDL loop.

### What the platform already pins here

J13 explicitly treats LabelAssertions as **human or external adjudication facts** written into Label Store.
So external adjudication is first-class — it just needs a clean path.

### Production truth to pin for this path

* **[PIN] External outcomes become LabelAssertions with proper provenance + time semantics.**
  External “chargeback for txn at T” typically yields:

  * `effective_time = T` (when it was true in the world),
  * `observed_time = now` (when we learned it).
* **[PIN] Conflicts are resolved by append-only evolution, not overwrite.** If external adjudication contradicts investigator disposition, you write a new assertion; the timeline records both.
* **[PIN] CM treats external adjudication as evidence + workflow, not silent truth mutation.** It can reopen/escalate cases, but the truth plane remains Label Store.

### A pragmatic production stance (designer choice)

To avoid ambiguity and keep learning clean:

* External adjudication should either:

  1. emit into the **same label family** but with provenance tiering (external > investigator), or
  2. emit into a distinct “external_outcome” family and training manifests explicitly pick which families are “ground truth.”

Either way, the key is: **learning reads labels only through Label Store rules + as-of joins**, never from ad-hoc case exports.

---

Absolutely — here are the **three CM-centered production loops** expanded as **authoritative loop designs** (CM remains opaque). Everything below is constrained to your pinned platform blueprint + deployment mapping.

---

## C1 / L-CM-01 — Truth → learning → decisions → truth loop (primary feedback loop)

**Loop:**
`CM → Label Store → Offline Feature Shadow → Model Factory → Registry → DF → (decisions/actions/audit) → CM`

### Why this loop exists

This is how **human ground truth** becomes **machine behavior** *without* leakage or training/serving drift. The platform explicitly pins: labels come only from Label Store, training is “as-of”, and learning uses replayable facts + decision-time provenance.

### The loop, stage-by-stage (production narrative)

#### 1) CM creates adjudication truth, but only by emitting LabelAssertions

* Investigator actions in CM produce **LabelAssertions**.
* **Label Store is the only label truth used for learning** (no inferring labels from outcomes or “what DF decided”).
* Labels are **append-only timelines** with **effective_time vs observed_time**, enabling “what was true” vs “when we learned it”.

**CM’s observable obligation in this loop:**
CM must be able to say: *“I asserted label X for subject Y, with provenance + times, and it was accepted/failed.”* (Truth of the label itself lives in Label Store.)

---

#### 2) Offline Feature Shadow rebuilds training reality from replayable facts + label truth

Offline Shadow is explicitly the “bridge” that prevents serving/training drift:

* Reads **EB history** (or archive beyond retention) + **Label Store** + SR run facts (by-ref) to rebuild datasets deterministically.
* Uses **explicit “as-of” joins** (leakage-safe): features/events and labels are joined as-of the boundary, not “latest”.
* Produces **parity evidence** vs online serving (e.g., matching snapshot hashes under the same watermark/graph_version basis).
* Emits **DatasetManifests** + materializations under `ofs/…` as pinned, reproducible artifacts.

**Critical drift-killer pinned by the platform:**
Learning is built from **replayable facts** + **decision-time provenance** (feature snapshot hash, watermarks, graph_version, degrade posture, bundle ref).

---

#### 3) Model Factory turns manifests into a bundle with evidence (not “a model file”)

Model Factory:

* Consumes DatasetManifests from `ofs/…` (not ad-hoc queries).
* Produces training run outputs + eval evidence under `mf/…`.
* Attaches PASS/FAIL evidence where required and produces a **bundle** intended for registry publication.

---

#### 4) Registry is the only deployable truth; it resolves exactly one ACTIVE bundle deterministically

Registry:

* Stores **bundle lifecycle truth** and resolves exactly one **ACTIVE bundle** per scope by deterministic rules (not “most recent”).
* Promotion is **evidence-led** (eval artifacts + lineage + PASS where required).
* Emits registry lifecycle events to `fp.bus.control.v1` (operational visibility).

---

#### 5) DF consumes Registry resolution and records provenance; this changes what CM sees next

Decision Fabric:

* Resolves the ACTIVE bundle from Registry and **records the bundle ref in decision provenance** so decisions are explainable and replayable.
* Emits decisions + action intents into `fp.bus.traffic.v1`.
* Actions execute; DLA records the audit “flight recorder” with decision-time provenance and refs.

**Return to CM:**
CM receives DF/AL/DLA pointers as evidence/triggers (new decision patterns → new cases; changed model → changed outcomes → changed audit).

---

### What “closure” means in C1 (so the loop is real)

This loop is closed when:

* A label emitted by CM **can be traced** into a DatasetManifest,
* which can be traced into a training/eval run,
* which can be traced into a registry bundle promotion,
* which can be traced into DF’s decision provenance,
* which is visible to CM via audit evidence when the next case arrives.

---

## C2 / L-CM-02 — Manual action loop (primary operational loop)

**Loop:**
`CM → ActionIntent → AL → Outcome → DLA → CM`

### Why this loop exists

It guarantees: **human side effects are dedupe-safe and auditable exactly like automated ones**. Platform pin: manual interventions must go through Actions Layer (effectively-once + immutable outcomes).

### The loop, stage-by-stage

#### 1) CM requests an ActionIntent (it does not execute)

* CM produces an **ActionIntent** with ContextPins + actor principal + idempotency key.
* Operationally, this rides the same spine: producers feed IG → EB traffic; AL consumes intents.

**Non-negotiable:** CM never performs the side effect directly.

---

#### 2) AL executes effectively-once and emits immutable outcomes

Actions Layer:

* Enforces effectively-once semantics via `(ContextPins, idempotency_key)` and emits an immutable ActionOutcome history (including denial/failure).
* Outcomes are published to `fp.bus.traffic.v1` and recorded in the actions store.

---

#### 3) DLA records the flight recorder and (optionally) emits pointer events

DLA:

* Consumes intents/outcomes and writes immutable audit records under `dla/audit/...` (quarantining if provenance incomplete).
* Optionally emits pointer events on `fp.bus.audit.v1` (evidence-ready signals).

---

#### 4) CM closes the loop by attaching outcome evidence to the case timeline

CM learns outcomes by:

* receiving the DF/AL/DLA pointer stream (evidence refs), and/or
* consuming audit pointer events (optional) and resolving `dla/audit/...` by-ref.

**CM’s externally observable obligation:**
CM must clearly show: *requested → pending → executed/denied/failed*, with an outcome pointer (audit ref) once available.

### Failure reality (and why the loop stays safe)

* **AL down:** CM records “requested (pending)” and retries idempotently; no duplicate side effects.
* **Outcome delayed:** CM can show pending while audit evidence is unresolved; it must not “assume success.”
* **Denied:** denial is still an immutable outcome (audit-visible) — not an exception path.

---

## C3 / L-CM-03 — Control-plane automation loop (optional, but production-useful)

**Loop:**
`CM case events → EB(control) → ops/automation/gov reactions → (policy/backfill/ops actions) → evidence/context shifts → CM`

### Why this loop exists

It makes the platform **operable**: the system can react to “what humans are seeing/doing” (case volume, escalations, resolution rates) with explicit, auditable operational actions — without silently changing domain truth.

### The loop, stage-by-stage

#### 1) CM emits control facts (optional)

* CM may emit **case events** to `fp.bus.control.v1` (low-volume control facts).
* As a producer, CM must go through IG admission semantics (admit/quarantine/duplicate + receipts).

**Important pin:** These events are **signals**, not the primary case record (truth stays in `case_mgmt`).

---

#### 2) Ops/automation/gov consumes control facts and reacts only via explicit control surfaces

Your blueprint pins “no silent mutation”: operations can influence behavior only through explicit mechanisms, e.g.:

* **Run/Operate** writing governance facts (`gov/…` + `fp.bus.control.v1`) and triggering jobs (backfills, replays, drains).
* **Registry promotions/rollbacks** (explicit lifecycle changes) which affect DF only via deterministic active resolution.
* **Degrade Ladder** producing an explicit mask (DL emits posture changes optionally to control topic) which DF must obey and DLA must record.

This is what prevents control-plane “automation” from becoming a hidden decision engine.

---

#### 3) Those operational actions shift *context/evidence availability*, and CM experiences the shift

The key is: control-plane reactions typically change **derived surfaces**, not domain truths.

Examples of “evidence/context shifts” CM may observe:

* **Backfills** rebuild *indexes/projections* (audit_index, IEG/OFP rebuilds, offline materializations) — improving joinability and investigation UX — without rewriting EB admitted facts or label timelines.
* **Registry activation** changes which bundle DF uses → changes future decisions and action intents → changes what triggers/cases CM receives.
* **Degrade posture changes** constrain DF behavior → changes what actions occur and what audit shows → changes what CM sees.

**CM’s required posture:** CM must tolerate “context re-materialization” (things becoming resolvable later) without rewriting its own case truth/timeline.

---

### What “closure” means in C3

This loop is closed when a CM control fact can lead to an explicit, auditable operational action (gov fact / backfill declaration / promotion / degrade posture), and the resulting effect is observable as:

* changed availability of evidence pointers (audit/index/lookup),
* changed future decision behavior (bundle change / degrade mask),
* or changed operational posture — all without silent truth mutation.

---

## A crisp pin that keeps all three loops from drifting

**[PIN] C1 changes decision behavior only via Registry; C2 changes the world only via Actions Layer; C3 changes operations only via explicit governance/control surfaces.**
Everything else is evidence, pointers, or rebuildable context — never silent truth.

---

Great — here are **C4–C6** expanded as **production loops** that pass through **CM (opaque vertex)**, with the exact **pins/laws** that keep them drift-free.

---

## C4 / L-CM-04 — Replay/backfill loop (must exist in prod)

**Loop shape:**
`Governance facts (retention/backfill/replay declared) → EB/Archive replay → rebuild derived stores (IEG/OFP/DLA indexes/OFS datasets) → CM sees updated evidence context`

### Why this loop exists

Time passes: retention expires, schemas evolve, bugs are fixed, late arrivals happen. The platform must be able to **recompute derived state** without corrupting truth and without “time travel.”

### The non-negotiable production pins (the “laws” of this loop)

* **Archive is a continuation of EB, not a second truth.** Same logical events (`event_id`, same envelope semantics).
* **Replay basis is always explicit.** No “grab all history”; rebuilds declare offset ranges (preferred) or time windows anchored to recorded checkpoints/watermarks.
* **Backfill is declared + auditable, never silent.** It declares scope, purpose, basis, outputs; it emits a governance fact.
* **Watermarks don’t lie (monotonic).** Consumers never “go backward”; backfills don’t redefine what offsets meant.
* **Only derived things can be backfilled.**

  * *Can:* IEG projections, OFP state, offline datasets/manifests, audit indexes, analytics views.
  * *Cannot as truth mutation:* EB admitted events, label store timelines, registry lifecycle history, SR run ledgers, engine outputs for a pinned identity.

### How the loop runs (production narrative)

1. **Run/Operate declares an operation** (retention change, backfill, replay window).

   * It must emit a **governance fact** (who/why/when/scope/basis/outputs).
2. **A backfill/replay job executes** under the same lifecycle discipline as other jobs (run/backfill id, pinned inputs, outputs, completion receipt).
3. The job **replays from EB or Archive** depending on the basis, treating Archive as the extension of EB.
4. It **regenerates derived outputs** (IEG, OFP, audit_index, OFS datasets/manifests), producing new versioned artifacts/state (never stealth overwrites of primary truths).
5. **Consumers switch to or rebuild from the regenerated derived state** explicitly (operationally governed), while their progress tokens remain monotonic.

### What CM experiences (the “CM-visible effect”)

CM’s **case timelines do not change** — CM is still authoritative for the investigation story. What changes is **evidence context availability and joinability**:

* audit lookups become faster or newly possible (audit index rebuilt)
* older event context becomes available via archive-backed replay (if CM reads history)
* derived “context surfaces” used in investigation UI may become consistent after rebuild (without rewriting base truth)

**Critical CM posture:** CM must treat these as *context changes*, not “history changed.” If something becomes resolvable later, CM can show it as newly available — it must not silently rewrite what an investigator previously saw.

---

## C5 / L-CM-05 — Engine oracle evaluation loop (optional, safety-gated)

**Loop shape:**
`SR world selection → engine truth_products (gated, by-ref) → CM “oracle/reference lane” → (human correction) → Label Store → learning loop`

### Why this loop exists

In a closed world, the engine can generate “oracle truth.” That’s valuable for **evaluation, QA, and training discipline** — but it’s dangerous if it leaks into the hot path.

### The non-negotiable production pins

* **Role separation is real:** only **business_traffic** drives the hot path; **truth_products** are *never traffic* and are consumed **by-ref** for eval/training/tooling.
* **SR is the broker of which engine material matters.** Downstream starts from SR’s join surface; no scanning engine outputs.
* **No PASS → no read (platform-wide).** Truth_products are admissible only with explicit refs + PASS evidence for the exact scope.
* **No “patching” engine facts.** Corrections are new artifact identity/version and/or a new run join surface pointing at corrected refs.

### How the loop runs (production narrative)

1. **SR publishes the join surface** for a run (refs + proofs). CM can only reach truth_products via that surface.
2. CM reads **truth_products by reference** (locators/paths) and only if required PASS evidence exists.
3. CM presents oracle truth in a **separate lane** (reference-only). It never becomes “case truth” unless a human writes a case event and emits a LabelAssertion through normal channels.
4. A human may **correct** an adjudication after seeing oracle comparison; that correction becomes a **new LabelAssertion** (append-only evolution) in Label Store.
5. Learning can then build:

   * “what we knew then” datasets, and
   * “oracle vs human” evaluation datasets,
     using explicit as-of semantics and explicit dataset manifests (no hidden leakage).

### The key CM design stance that makes this safe

**[PIN] Oracle truth must never be the default decision guide.**
Practically, the safest posture is: oracle truth is **hidden by default** and only revealed under explicit “evaluation mode” or after an investigator commits an initial disposition, so you can measure human performance and avoid rubber-stamping. This is consistent with “truth_products are privileged evaluation material,” not traffic.

---

## C6 / L-CM-06 — Delayed-truth loop (optional but production-common)

**Loop shape:**
`Decision happens → later external adjudication arrives → CM workflow → Label Store timeline update → learning/decision shifts → CM sees new patterns`

### Why this loop exists

Real ground truth often arrives late (disputes/chargebacks/KYC outcomes). The platform explicitly treats these as **label assertions** — and labels are timelines precisely so late truth is representable without corruption.

### The non-negotiable production pins

* **Labels become truth only in Label Store** as append-only timelines.
* **Effective vs observed time must be preserved.** Late truth is safe only if you don’t collapse those semantics.
* **Late labels are normal; as-of makes them safe.** Learning must support “what we knew then” vs “what we know now” without confusing them.
* **Append-only + supersedes for corrections** (no destructive edits).

### How the loop runs (production narrative)

1. A decision/action occurs; DLA records evidence; CM may already have a case from RTDL triggers.
2. **Later**, an external adjudication arrives (e.g., chargeback for an earlier transaction).

   * CM treats this as **evidence + workflow**, not automatic truth mutation.
3. CM emits a **LabelAssertion** to Label Store with:

   * `effective_time = time the external truth applies to` (often in the past),
   * `observed_time = now` (when the platform learned it),
   * provenance marking it as external adjudication.
4. That assertion may **supersede** an earlier investigator label (still append-only).
5. Learning then (optionally) triggers explicit dataset rebuilds or backfills to incorporate late truth — but **only via declared replay basis + declared backfill**, never silently. (This is where C6 naturally feeds C4.)
6. Over time, models/policies evolve via governed registry changes, shifting decisions and therefore changing what CM sees in future cases — closing the loop.

### What CM must be able to represent (externally)

* A case can be **reopened / re-adjudicated** due to delayed truth, without rewriting earlier case history.
* CM must display that “this label changed because new information arrived,” with explicit provenance and times (effective vs observed), and it must remain audit-defensible.

---

## One compact “pin” that ties C4–C6 together (prevents drift)

**[PIN] C4 changes only *derived* state via declared replay basis; C5 introduces oracle truth only as gated reference material; C6 evolves truth only via append-only label timelines with explicit time semantics — and none of them rewrite primary facts or silently change history.**

---

Yes — the **environment ladder** is basically the *lens* that tells us which of these joins/paths/loops must be **semantics-identical everywhere**, and which parts are allowed to “shrink/loosen” operationally in local/dev and “harden” in prod.

## What must not change across local / dev / prod

If any of these drift, your joins/loops will “work locally, break in prod” (i.e., you’ve accidentally built three platforms).

**Invariant 1 — Same graph + trust boundaries**
IG front door, EB fact log, SR readiness authority, Registry deployable truth, AL only executor, Label Store label truth, CM case truth.

**Invariant 2 — Same rails / join semantics**
ContextPins discipline, canonical envelope, no-PASS-no-read, by-ref locators, watermarks, idempotency, append-only+supersedes, degrade mask as hard constraint, deterministic registry resolution, as-of semantics.

**Invariant 3 — Same meaning of the words**
“READY”, “ADMITTED”, “ACTIVE”, “LABEL AS-OF”, “BACKFILL” must mean the same thing everywhere.

**Invariant 4 — Same reproducibility story**
A run/build in dev/prod must be explainable the same way as local: pinned inputs + evidence + refs.

## What is allowed to differ (and how it affects *your* joins/loops)

Scale, retention/archive, security strictness, reliability posture, observability depth, cost knobs — *but never the semantics of pins/gates/provenance.*

Below I map that directly onto the CM joins/paths/loops we defined.

---

# Environment ladder impact on the CM joins/paths/loops

## 1) “Truth-changing” joins harden with policy profiles (not code forks)

This is the biggest place drift sneaks in.

### CM → Label Store (B1/J-CM-01)

* **Local:** permissive writer allowlists are fine, but *append-only + effective/observed time + provenance* must still hold.
* **Dev:** “real enough” authz so invalid writers/revisions get rejected like prod.
* **Prod:** strict authz + audited policy revs; no one can write labels without leaving governance-grade footprints.

### CM → Actions Layer (B2/J-CM-02)

* **Local:** you can stub the external integration, but the **AL semantic contract** must still be real: idempotency, immutable outcomes, policy rev included.
* **Dev:** tighten allowlists and failure paths (denies must behave like prod).
* **Prod:** strong isolation, strict allowlists, incident-safe execution posture.

**Pin to enforce across envs:** environment ladder uses **profiles** (policy + wiring), not “if prod do X else Y” code paths.

---

## 2) “Signal” joins can be disabled locally, but can’t change shape if enabled

These are B3/B4 + the control-plane loop.

### CM → IG → EB(control) (B3/J-CM-06) and Label Store → EB(control) (B4/J-CM-09)

* **Local:** you may choose to not emit control facts to reduce noise.
* **But:** if you do emit, you still go through **IG**, still get receipts/quarantine/duplicate semantics, and still use the same topic shape and envelope.

This matters because C3 (control-plane automation loop) is where “ops reality” lives: **changes must be durable facts, not just logs.**

---

## 3) Retention/archive differences hit the *evidence experience*, not the truth semantics

This impacts P-CM-07 and loop C4 directly, and affects CM’s “optional EB history reads” (J-CM-07).

**Pinned:** retention differs by environment profile, but **offset/watermark/replay semantics do not**. Archive is a long-horizon extension of admitted canonical events; backfills are explicit, scoped, auditable, and only regenerate derived state (never mutate primary truths).

### Practical effect on your CM world

* **Local:** EB retention is short; therefore EB-history-as-context will frequently be unavailable, forcing CM to rely on by-ref DLA audit artifacts. That’s *good* — it pressure-tests your “by-ref flight recorder” posture.
* **Dev:** medium retention + some archive/backfill practice so replay/backfill workflows are exercised before prod.
* **Prod:** long retention + archive continuity; governance facts for retention changes and backfill executions are mandatory.

**Key drift guard:** CM truth (case timelines) must never “rewrite history” just because evidence becomes resolvable later after a backfill/index rebuild. Backfill changes *derived availability*, not primary truth.

---

## 4) Oracle/reference lane (C5 / P-CM-08) should *tighten* as you go up the ladder

This is the most safety-sensitive “optional” loop.

* **Local:** oracle truth_products access can be wide open for dev/QA — but still gated by “No PASS → no read” and still only reachable via SR’s join surface (no scanning).
* **Dev:** more controlled access so you catch permission mistakes early.
* **Prod:** often restricted to specific roles or disabled by policy profile; but if enabled, semantics remain identical (reference lane only; never hot-path traffic).

---

## 5) Learning loop (C1 / P-CM-06) is where “prod-shaped local” matters most

The environment ladder explicitly pushes you to run a **production-shaped local stack** so the joins/loops are real: Kafka-ish EB offsets, S3-ish object refs, SQL timelines, OTLP observability.

That’s important because:

* the **offline parity** story (OFP versions + OFS rebuild + bundle requirements) must match across envs; you don’t want a “local training join” that can’t happen in prod.
* the **promotion story** must be “build once, run anywhere” with profiles and governed revisions (code + policy revs + bundles), not environment-specific behavior.

---

# The one practical takeaway for *your* CM join/path/loop set

If you want zero drift across environments, enforce this rule:

**Every join/loop must be testable in local with the same semantics, even if it’s smaller or partially disabled — and promotion must be profile selection (policy+wiring), not behavior forks.**

A concrete “ladder-proof” check you already pinned: run one golden end-to-end flow locally (SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA + label + offline + registry resolve). If that works locally under the rails, dev/prod are mostly a hardening exercise, not a redesign.

---

