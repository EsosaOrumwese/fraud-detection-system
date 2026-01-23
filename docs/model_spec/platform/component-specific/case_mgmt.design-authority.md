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

Yep — here are the **environment profile knobs** (and a few “keep-in-mind” deployment facts) that matter for **Case Mgmt / Workbench (CM)** *while it’s still opaque*, so when we open it up we don’t accidentally design something that only works in one environment.

Everything here follows your pinned ladder rule: **same graph + same rails; environments differ only by profiles (wiring + policy strictness), not code forks.**

---

## 1) The two config buckets you must keep separate

**Wiring config (non-semantic):** endpoints, ports, timeouts, resource limits.
**Policy config (outcome-affecting):** auth rules, allowlists, redaction rules, required gates, approval requirements, etc.

**Pin reminder:** policy configs are versioned artifacts and components should always report which **policy_rev** they’re using; and any outcome-affecting change should emit a governance fact.

---

## 2) CM profile knobs (what you’ll actually want to be able to tune)

### A) Wiring profile knobs (CM’s runtime plumbing)

These should exist in **local/dev/prod**; values differ, semantics don’t.

* **DB:** `case_mgmt` connection + pool sizing (CM’s authoritative truth store).
* **Object store:** read access for `dla/audit/...` evidence (by-ref).
* **Service endpoints:** Label Store (writes + reads), Actions Layer (submit intents), optional IG producer endpoint (if CM emits case events), optional EB read endpoint (if CM reads history).
* **Observability endpoint:** OTLP exporter target (otel-collector).

### B) Policy profile knobs (CM’s “rules of engagement”)

These are the ones that change *strictness*, not meaning.

**Identity & access**

* **Authn/Authz mode:** local relaxed vs prod strict; *but the mechanism exists everywhere*.
* **Role permissions:** who can

  * create/close/escalate cases,
  * write labels,
  * request manual actions,
  * view quarantined / sensitive evidence.

**Label emission guardrails (CM → Label Store)**

* **Allowed label families / schemas** CM can emit (a practical allowlist).
* **Required provenance fields** (actor, case link, reason codes).
* **As-of display defaults** in UI (current truth vs “known at time”).
  (All remain consistent with “labels are append-only timelines with effective vs observed time”.)

**Manual actions guardrails (CM → AL)**

* **Allowed action types and scopes** for “manual origin” intents (allowlist + constraints).
* **Approval mode** (e.g., some actions require a second reviewer in prod; in local everything is single-step).
* **Rate limits / circuit breakers** for manual actions (safety).

**Evidence access & redaction**

* **Redaction policy** for showing evidence (never dump raw payloads by default; by-ref posture).
* **Quarantine evidence access** (who can view IG/DLA quarantine refs).
* **EB-history context read policy** (whether CM is allowed to read EB for UI context; if yes, how far back; fallback behavior).

**Optional join toggles (feature knobs, not semantic forks)**
These are the “A6–A11 / B3–B4” optional edges you can toggle per env:

* `publish_case_events_to_control` (CM → IG → `fp.bus.control.v1`)
* `consume_label_events_from_control` (if Label Store emits)
* `consume_audit_pointer_events` (from `fp.bus.audit.v1`)
* `enable_oracle_lane` (SR → engine truth_products → CM reference lane) + who can see it

**Pin warning:** toggling these must only affect *freshness/UX/automation*, not truth meaning. The “truth-changing” joins (labels/actions) are always real.

---

## 3) CM deployment-unit facts you should keep in your head

This is what CM “is” operationally on the ladder:

* CM is an **always-on human-facing app: UI + backend**.
* It **must persist**: `case_mgmt` timelines (authoritative).
* It **reads** by-ref evidence (`dla/audit/...`), **writes labels** via Label Store, and **requests manual actions** via AL/IG path; it may optionally read EB history and emit case events to `fp.bus.control.v1`.
* Local/dev can **collapse** units (run multiple things in one process/compose), but the unit roles don’t change.

---

## 4) The “minimum viable deployment readiness” checklist for CM (ladder-proof)

Not specs — just what you should ensure is possible in every env:

* **Correlation keys in telemetry** (run/event/decision/action ids) so investigations are joinable.
* **Boundary-decision logging**: label append accepted/rejected; action intent accepted/denied; case event publish receipt/quarantine if enabled.
* **Golden signals + CM-specific safety metrics**: pending labels, pending actions, unresolved evidence refs.
* **One local “golden flow” exercise includes CM** (case → label store) alongside the rest of the platform wiring.

---

## 5) Practical defaults by environment (directional)

Just to orient you (not binding values):

* **Local:** permissive auth, short retention, high sampling/verbose observability, optional oracle lane often on, optional control-plane emissions optional.
* **Dev:** “real enough” auth to catch prod failures, medium retention, governance/change control exercised, oracle lane restricted.
* **Prod:** strict auth + approvals, long retention + archive continuity, SLOs/alerts meaningful, oracle lane usually highly restricted/off.

---

## USER: PAUSE FOR REFLECTION

Absolutely — here’s the **outer-network checkpoint** for **Case Mgmt / Workbench (CM)** as an **opaque vertex**, grounded in your **design-authoritative platform + deployment pins**, so we can “enter” CM without drifting.

---

## 1) The pinned outer truth about CM’s role in the platform

### Where CM sits (plane-level)

Your platform explicitly defines the **human truth loop** as:

`DF/AL/DLA pointers → Case Mgmt / Workbench (cases + immutable timelines) → emits investigator assertions → Label Store (append-only label timelines + as-of)` 

### What CM is (deployment-shape)

CM is an **always-on human interface (UI + backend)** whose durable truth is `case_mgmt` timelines; it:

* reads evidence by-ref from `dla/audit/...`,
* writes labels via Label Store,
* requests manual actions via the AL/IG path,
* may optionally read EB for history,
* may optionally emit case events to `fp.bus.control.v1`.

---

## 2) Rails that bite CM (non-negotiable drift guards)

These are the rails that “grab” CM whether we want them to or not:

* **Traffic vs surfaces:** only `business_traffic` drives hot path; truth_products/audit_evidence/ops_telemetry are by-ref only (never treated as decisionable traffic).
* **Canonical admitted event shape:** anything on the bus that can influence the platform must be representable as the **canonical event envelope** (required: `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`).
* **No PASS → no read (platform-wide):** gated artifacts/surfaces are inadmissible without required PASS evidence for the pinned scope.
* **By-ref transport + digest posture:** across boundaries we move refs/locators (+ optional digests), not copied payloads; digest mismatch is inadmissible.
* **Replay basis is EB coordinates:** offsets/watermarks are the only universal progress token; anything “replay/backfill” must be expressed on that basis.
* **End-to-end idempotency:** duplicates are normal; CM’s joins must be stable under replay; labels are append-only; AL is effectively-once via `(ContextPins, idempotency_key)`.
* **Time semantics never collapse:** `ts_utc` is domain time; ingestion time is receipt truth; labels carry **effective_time vs observed_time**.
* **Append-only truth + supersedes:** applies to audit, labels, ledgers, registry lifecycle.
* **Quarantine is first-class:** no silent drops for anything that matters.

---

## 3) Authority boundaries (what CM may and may not “own”)

Pinned plane rules for the CM neighborhood:

* **Labels become truth only in Label Store** (append-only timelines, effective vs observed time, as-of semantics).
* **Manual interventions must go through Actions Layer** (ActionIntent → effectively-once execution → immutable outcomes).
* **RTDL ↔ Case/Labels bridge is stable identifiers + refs, not copied payloads.**

So: **CM owns cases + immutable investigation timelines**, but it **does not** become a label store, an action executor, an audit store, or a shadow event bus.

---

## 4) The outer adjacency set (joins) we’ve exposed — drift-safe version

### Must-have joins (CM is incomplete without these)

1. **Inbound evidence/triggers:** DF/AL/DLA pointers → CM (IDs + refs, not payload).
2. **Evidence resolution:** CM reads `dla/audit/...` by ref (flight recorder).
3. **Label emission:** CM → Label Store (J13) LabelAssertions (append-only, effective vs observed).
4. **Manual actions:** CM submits ActionIntents via AL/IG path; AL executes; outcomes immutable.
5. **Label context reads:** CM reads Label Store for as-of context.

### Optional-but-allowed joins (must not become “truth dependencies”)

6. **CM → `fp.bus.control.v1` case events (signals only)**.
7. **CM reads EB history for UI context (optional)**.
8. **DLA pointer events on `fp.bus.audit.v1` (optional)**.
9. **Label Store optional label events on control topic (optional)**.
10. **SR → engine truth_products → CM oracle lane (optional, fenced)**: never traffic; must obey “No PASS → no read”; file order is non-authoritative; only declared keys matter.

---

## 5) Outer paths/loops: what “closure” means (so we know the graph is coherent)

The big closures we must preserve as we enter CM:

* **C1 (truth → learning → decisions → truth):** CM labels → Label Store timelines → Offline Shadow as-of rebuild → DatasetManifests → MF bundles → Registry ACTIVE resolution → DF provenance → DLA evidence → CM triggers.
* **C2 (manual action loop):** CM ActionIntent → AL executes effectively-once → outcomes → DLA flight recorder → CM sees outcome evidence.
* **C4 (replay/backfill):** governance-declared, offset-anchored replays rebuild **derived** state only; CM truth (case timelines) is not silently rewritten—only context becomes newly joinable/available.

---

## 6) Environment ladder checkpoint (so CM doesn’t fork by environment)

Pinned rule: **local/dev/prod run the same graph and rails; only operational envelope changes** (scale, retention/archive, security strictness, reliability, observability).

For CM specifically, that implies:

* **Semantics never change:** append-only case timelines, label timeline semantics (effective vs observed), ActionIntent→AL execution, by-ref evidence posture.
* **Allowed profile differences:**

  * EB retention shorter locally → CM relies more on `dla/audit/...` than EB history (but still correct).
  * Oracle lane may be enabled in local/dev but restricted/disabled in prod **by policy**, not by different meaning.
  * Optional signal joins (case events / label events / audit pointer events) can be toggled without changing truth behavior.

---

## 7) Drift alarms to carry into the “inside CM” phase

When we illuminate CM internals, we must **never** accidentally implement these anti-patterns:

* **“Labels-in-case” truth** (CM storing label truth as state) → violates J13/Label Store truth.
* **Direct execution of manual actions** → violates “AL is the only executor.”
* **Copying large event/audit payloads into case truth** → violates by-ref truth transport.
* **Treating engine truth_products/audit_evidence/ops_telemetry as traffic** → violates traffic vs surfaces.
* **Relying on file row order for engine surfaces** → explicitly forbidden by engine interface. 
* **Collapsing effective_time/observed_time or domain time/ingest time** → violates time rails.
* **Silent drops instead of explicit rejection/quarantine outcomes** → violates quarantine rail.

---

## One “outer network anchor” we can treat as the guardrail going forward

**CM is the always-on human control surface that stores cases as immutable investigation timelines; it consumes RTDL evidence by stable IDs + refs; it produces ground truth only by emitting append-only LabelAssertions into Label Store; it triggers side effects only by submitting ActionIntents to AL; and any bus participation is either canonical traffic (via IG) or optional control signals—never a second truth store.**

---

If we’re aligned on this checkpoint, the “enter CM” move is straightforward: we design the **minimum internal structure** that satisfies the **5 must-have joins** first (evidence intake → timeline truth → label emission → action requests → label context reads), and we treat the optional joins as profile-toggled add-ons that **cannot** carry truth.

---

Yes — at “one level deeper” inside **Case Mgmt / Workbench (CM)**, the clean way to avoid overwhelm is to decompose CM into a small set of **internal subnetworks that line up with the outer joins/truth-ownership pins** (cases/timelines are CM truth; labels are Label Store truth; actions execute only via AL; evidence is by-ref).

Below are the **Level-1 internal subnetworks** (treat each as an opaque box for now).

---

## CM Level-1 internal subnetworks (opaque boxes)

### S1) Workbench Gateway

**Purpose:** the single “front door” for *human* and *system* interactions: auth/session, role checks, command intake, idempotency keys, input validation.
**Touches externally:** everything indirectly (it is the entry surface), but it owns no domain truth.
**Why it exists:** CM is an always-on UI + backend unit, so you need a clear boundary between “requests” and “case truth writes.”

---

### S2) Case Truth Ledger

**Purpose:** CM’s *authoritative* truth: **case objects + append-only investigation timelines** (the thing the platform calls “cases + immutable timelines”).
**Touches externally:** none directly; it is the internal source-of-truth that other CM subnetworks must write through.

---

### S3) Workflow & Triage Orchestrator

**Purpose:** queueing/assignment/escalation/state-machine semantics for investigations (how humans “work cases”).
**Data posture:** derived/managed view over the ledger; does not become a second truth store.
**Why it exists:** CM must be usable in production without forcing every consumer to understand raw timeline events. (This aligns with the “workbench” deployment reality.)

---

### S4) Evidence Plane

**Purpose:** everything about **evidence references + resolution** while keeping CM “by-ref” and drift-safe.
**Includes (still opaque):**

* **Evidence Intake** (from DF/AL/DLA pointers; stable IDs + refs, not copied payloads)
* **Evidence Registry** (stores refs/locators and minimal metadata)
* **Evidence Resolver** (fetch/resolve by-ref from `dla/audit/...`; optional EB history reads)
* **Oracle/Reference Adapter (optional)** (SR join surface → engine truth_products; fenced as reference-only)

**Touches externally:** DLA object store by-ref; optional EB reads; optional SR/engine truth_products.

---

### S5) Adjudication & Labels Plane

**Purpose:** turn “human disposition” into **LabelAssertions** and keep label truth ownership correct.
**Responsibilities (opaque):**

* Disposition capture & mapping → LabelAssertion
* Label write submission + ACK tracking
* **As-of label reads** for investigator context (labels are timelines; effective vs observed time semantics)

**Touches externally:** Label Store reads/writes (J13 is the key boundary).

---

### S6) Manual Intervention Plane

**Purpose:** request human-driven side effects *without bypassing* platform rails.
**Responsibilities (opaque):**

* Build **manual ActionIntents** with idempotency + join identifiers
* Submit via AL/IG pathway
* Track outcomes and attach outcome evidence back into the case story (as refs)

**Touches externally:** Actions Layer (executor), plus outcomes returning as evidence pointers via the normal DF/AL/DLA→CM bridge.

---

### S7) Signals & Bus Adapters (optional subnetwork)

**Purpose:** optional event-driven “freshness/automation” without becoming truth-dependent.
**Examples (still opaque):**

* Publish **case events** → IG → `fp.bus.control.v1` (signals only; CM ledger remains primary)
* Consume optional **audit pointer events** (`fp.bus.audit.v1`) and/or **label events** (`fp.bus.control.v1`) as “something changed, go read truth” nudges

---

### Cross-cutting rails inside CM (not separate boxes, but attached to all)

* **Access control + audit discipline** (actor always recorded; no silent edits)
* **Observability & profile/policy plumbing** (OTLP everywhere; env ladder uses profiles; semantics unchanged)

(These are “everywhere inside CM,” so we don’t treat them as a standalone box unless you want to.)

---

## One-level internal network sketch (modules still opaque)

```text
        [S1 Workbench Gateway]
                 |
                 v
        [S2 Case Truth Ledger] <---- [S3 Workflow & Triage]
                 |
     +-----------+-------------------+
     |           |                   |
     v           v                   v
[S4 Evidence]  [S5 Labels]        [S6 Manual Actions]
  |   |          |   |              |      |
  |   +--> DLA   |   +--> Label     |      +--> AL/IG path
  |        refs  |        Store     |           (ActionIntents)
  |
  +--> (opt) EB history
  +--> (opt) SR/engine truth_products (oracle lane)

 (opt) [S7 Signals & Bus Adapters]
   - case events -> IG -> fp.bus.control.v1
   - consume fp.bus.audit.v1 / label control events as nudges
```

---

Yep — **one level deeper**, treating **S1–S7** as opaque, the CM “internal network” in production is basically:

* a **single internal truth spine** (S2 Case Truth Ledger),
* multiple **specialist planes** that hang off it (evidence / labels / actions),
* and optional **signal adapters** (bus/control nudges) that must never become truth dependencies.

This is fully consistent with the platform pins: **CM truth = cases + immutable timelines; evidence is by-ref; labels become truth only in Label Store; manual side-effects only via Actions Layer; optional signals via IG→EB.**

---

## Internal nodes (still opaque)

* **S1 Workbench Gateway**
* **S2 Case Truth Ledger**
* **S3 Workflow & Triage Orchestrator**
* **S4 Evidence Plane**
* **S5 Adjudication & Labels Plane**
* **S6 Manual Intervention Plane**
* **S7 Signals & Bus Adapters (optional)**

---

## Internal joins (edges) that exist in production

I’m naming these **I-Jxx** to keep them crisp later.

### Core “truth spine” joins

**I-J01 — S1 → S2 (Command Append)**
All durable CM changes are expressed as a “case command” that results in an append to the case timeline (or a rejection).

**I-J02 — S2 → S3 (Ledger → Workflow stream)**
S3 derives queues/assignment/escalation views from the ledger (derived, rebuildable).

**I-J03 — S1 ↔ S3 (Triage/View Queries)**
UI asks for “my queue / open cases / escalations / status views” from S3.

> This preserves the pin “case truth is immutable timelines” while still allowing production UX (queues) without making queues into truth. 

### Evidence joins (by-ref posture)

**I-J04 — S4 → S2 (Evidence Attach)**
S4 normalizes pointers (DF/AL/DLA / external) into by-ref EvidenceRefs and appends “evidence attached/unresolved/resolved” timeline events.

**I-J05 — S1 ↔ S4 (Evidence Resolve Requests)**
UI asks to render evidence; S4 resolves by-ref (primarily via `dla/audit/...`, optionally EB history) and returns a view.

**I-J06 — S7 → S4 (Evidence-ready Nudges, optional)**
If enabled, bus/audit pointer events “nudge” S4 to refresh/resolve, but S4 still must treat them as hints (truth lives in by-ref records). 

### Labels joins (truth owner is Label Store)

**I-J07 — S2 → S5 (Disposition/Label Work Items)**
When a disposition is committed in the ledger, S5 is triggered to produce a LabelAssertion.

**I-J08 — S5 → S2 (Label ACK / Failure Recording)**
S5 reports label submission outcome back to the ledger as timeline events (“label emitted/failed/pending”). Labels themselves remain Label Store truth.

**I-J09 — S1 ↔ S5 (Label Context Reads)**
UI reads label timelines “as-of” for investigation context (S5 is the internal portal to those reads).

**I-J10 — S7 → S5 (Label-changed Nudges, optional)**
If Label Store emits control events, S7 nudges S5 to refresh caches/views; it never replaces Label Store reads as the truth source.

### Manual action joins (executor is Actions Layer)

**I-J11 — S2 → S6 (Manual Action Work Items)**
Ledger contains “action requested”; S6 is triggered to build/submit an ActionIntent (with idempotency + join IDs).

**I-J12 — S6 → S2 (Intent Submitted / Denied / Pending)**
S6 reports submission/denial/pending as ledger timeline events (not execution).

**I-J13 — S4 → S2 (Outcome Evidence Attach)**
When outcomes arrive as DF/AL/DLA pointers, S4 attaches outcome refs into the case timeline (closing the loop).

### Optional signals (must not become truth dependencies)

**I-J14 — S2 → S7 (Publish Case Signal Work Items, optional)**
Certain ledger events are mirrored as “case control facts” for IG→EB control topic.

**I-J15 — S7 → S2 (Publish Receipt Recording, optional)**
S7 records “published / quarantined / duplicate” outcomes back into the ledger (so CM can prove what it tried to signal).

---

## Internal paths (end-to-end within CM) in production

### I-P01 — “New case from upstream evidence”

`(S7 or inbound endpoint) → S4 intake → S2 append (case created/attached + evidence ref) → S3 queue updates → S1 UI shows it`

### I-P02 — “Investigator triage”

`S1 → S3 (queues/views) → S1 → (open case) → S2/S3 summary`

### I-P03 — “Evidence drill-down”

`S1 → S4 resolve → (optional) S4 → S2 “evidence resolved/unavailable” → S1 render`

### I-P04 — “Disposition → label emission”

`S1 → S2 (disposition event) → S5 (label work item) → S2 (label emitted/failed/pending) → S3 updates → S1 UI`

(Truth lands in Label Store; ledger only records the attempt/outcome.)

### I-P05 — “Manual action request → later outcome”

`S1 → S2 (action requested) → S6 (submit intent) → S2 (intent submitted/pending/denied) → later: S4 ingests outcome pointer → S2 attaches outcome evidence → S3 updates → S1 UI`

(Executor is AL; CM just requests + records.)

### I-P06 — “Optional case event publish”

`S2 emits publish work item → S7 publishes via IG→EB(control) → S7 records publish receipt → S2 timeline records “published/quarantined”`

### I-P07 — “Evidence becomes available later”

`S7 consumes audit pointer event (optional) → nudges S4 → S4 resolves by-ref → S4 appends update to S2 → S3/UI reflect “now available”`

### I-P08 — “Label changes outside CM (optional)”

`S7 consumes label control event → nudges S5 → S5 refreshes as-of reads → S1 UI sees updated context (without rewriting CM truth)`

---

## Internal loops (cycles) that define CM’s production behavior

**I-L01 — The UI consistency loop**
`S1 → S2 (write) → S3 (derived views) → S1 (read)`

**I-L02 — Evidence closure loop**
`S4 (attach/resolve) → S2 (timeline) → S1 (render)`
(+ optional nudge `S7 → S4`)

**I-L03 — Disposition/label closure loop**
`S2 (disposition) → S5 (emit) → S2 (ack recorded) → S3/S1 (updated case state)`

**I-L04 — Manual action closure loop**
`S2 (request) → S6 (intent) → (later evidence) S4 → S2 (outcome attached) → S3/S1`

**I-L05 — Optional signal loop**
`S2 (case event) → S7 (publish) → S2 (receipt recorded)`
(never required for truth correctness)

**I-L06 — Rebuild/reconcile loop (implicit in production)**
Anything derived (S3 views, some S4/S5 caches) must be rebuildable from S2 truth + external authoritative reads; this is what makes CM resilient under restarts/backfills without rewriting case history. 

---

## Simple internal network sketch (opaque nodes, production)

```text
           [S1 Gateway]
        (UI + system API)
                |
                | I-J01 (commands)
                v
         +----------------+
         | [S2 Ledger]    |  (authoritative case timeline truth)
         +----------------+
           |     |     |  \
     I-J02 | I-J07  I-J11  I-J14(opt)
           v     v     v     v
        [S3]   [S5]   [S6]   [S7]
      (triage) (labels)(actions) (signals)
           ^      ^      ^      |
           |      |      |      +-- I-J06/I-J10(opt) nudges
     I-J03 | I-J09 |      |             v
           |      |      |           [S4 Evidence]
           +------+------+- I-J04/I-J13 --> (attach refs to ledger)
                  I-J05 (resolve UI)
```

If you’re happy with this internal join/path/loop inventory, the next “deep dive later” step can be: pick **one subnetwork** (usually S2 first) and pin its **public IO + invariants** in a handful of bullets — still without opening its internals.

---

Locked. Before we go join-by-join, I’m going to **declare the boundary-compatibility rules** for the CM internal truth spine (this is me using the design authority you granted).

## Boundary compatibility rules for the CM truth spine

These are **non-negotiable** because they are the only way CM stays aligned with the platform’s truth-ownership + “immutable timelines” pin:

1. **Only S2 is “case truth.”** CM is authoritative for **cases + immutable timelines**. 
2. **Everything durable is an append to S2 (or a rejection).** No silent edits, no in-place mutation of prior events.
3. **S3 is derived view only.** Queues/assignment/escalation views may be cached/materialized, but they are **rebuildable from S2** and never become an authority competing with S2.
4. **Actor is mandatory on any write.** CM is a human truth loop; “who did what” is part of the truth.
5. **Idempotency is mandatory.** The whole platform assumes at-least-once and demands deterministic behavior under retries/duplicates.

With those pinned, we can safely illuminate I-J01 to I-J03.

---

# I-J01 — S1 → S2: Command Append

### Purpose of the join

Turn “a user/system intent” into **a single durable timeline append** (or a deterministic rejection). This is the join that makes “cases + immutable timelines” real.

### What crosses the join (authoritative shape, still conceptual)

A `CaseCommand` request from S1 into S2:

* **Identity / routing**

  * `case_id` (optional for create)
  * `command_type` (create, assign, status change, note add, evidence attach, disposition set, etc.)
* **Idempotency**

  * `idempotency_key` (required) — stable across retries
* **Auth + provenance**

  * `actor` (required; human or system principal)
  * `actor_role`/`authority_context` (optional but useful)
* **Time**

  * `observed_at_utc` (when CM records it; not domain event time)
* **Join links (optional but strongly recommended)**

  * `links[]` (decision_id / event_id / entity_ref / request_id) + optional ContextPins scoping (closed-world discipline)
* **Payload**

  * structured `payload` for the command (small; by-ref posture)

### What S2 returns

An `AppendResult`:

* `ACCEPTED` with:

  * `case_id`
  * `case_event_id` (new timeline event ID)
  * `ledger_cursor` (monotonic pointer, see I-J02)
* or `REJECTED` with:

  * rejection reason code + details
  * (optional) pointer to previously-accepted result if this was a duplicate

### Laws for I-J01 (pinned)

**[PIN] Every accepted command produces exactly one new CaseEvent** in the timeline; no “header updates” outside the timeline.
**[PIN] Duplicate commands return the same semantic result** (idempotent).
**[PIN] Actor is required**; missing actor ⇒ reject.
**[PIN] Corrections are new CaseEvents** (supersedes-by-meaning), never mutation.

### Concurrency stance (designer choice, boundary-safe)

**[PIN] CM is multi-writer and conflict-tolerant; conflicts are represented, not prevented.**
Meaning: two investigators can append concurrently; S2 accepts both (if valid) and the “current state” is derived deterministically later.

This avoids hidden “global locks” as a dependency and keeps the timeline truthful (it really happened).

### Ordering stance (designer choice, minimal + sufficient)

S2 guarantees:

* **per-case append order** (the order it committed events for that case)
* and publishes a deterministic ordering key for tie-breaks (see cursor below)

This aligns with the platform’s general “ordering only guaranteed within a partition/scope” posture.

### What is NOT allowed (declared out-of-bounds)

* S1 writing directly to S3 to “change assignment/state” (would create a second truth).
* S2 accepting a “patch” command that mutates prior events.
* S2 accepting writes without idempotency keys.

---

# I-J02 — S2 → S3: Ledger → Workflow stream (projection feed)

### Purpose of the join

Let S3 build production-grade workbench views (queues, assignment, escalation, SLAs) **without** becoming truth.

### What crosses the join

A stream (or feed) of `CaseEvent`s emitted from S2 to S3, plus a monotonic cursor.

I’m going to pin a **CM-internal cursor concept** analogous to EB offsets, but local to CM:

* `ledger_cursor`: “the next event position to apply (exclusive)”
* Semantics: **exclusive-next** (same idea as EB checkpoints)

This gives S3 deterministic rebuilds and makes “how stale is my queue view?” measurable.

### Delivery semantics (designer choice, production-safe)

**[PIN] At-least-once delivery between S2 and S3; S3 must be idempotent.**
S3 dedupes by `(case_id, case_event_id)` or `(case_id, ledger_cursor)`.

This mirrors the platform’s global posture and prevents drift when we later add scaling/retries.

### Failure posture (critical for production UX)

* If **S3 is down**, **S2 still accepts writes** (cases can be updated); only queue/query freshness degrades.
* S1 must be able to serve **case-by-id + timeline** directly from S2 if needed (read fallback), while “my queue” may be stale/unavailable.

This keeps the authoritative truth spine available even when projections lag.

### What is NOT allowed

* S3 inventing or mutating truth (“case is resolved” without a corresponding ledger event).
* S3 requiring synchronous coupling for S2 commits (“can’t write unless projection succeeded”). That would make derived state a gating dependency.

---

# I-J03 — S1 ↔ S3: Triage/View Queries

### Purpose of the join

Give the workbench fast, ergonomic views **without** letting view logic become truth logic.

### Query classes that must exist (production-minimum)

S1 must be able to ask S3 for:

1. **Queue views**

   * “my queue”, “unassigned”, “escalated”, “by team”, “by priority”
2. **Search / discovery**

   * by join keys: decision_id / event_id / entity_ref / request_id
3. **List & filter**

   * status, assignee, time window
4. **Summaries**

   * case header summaries for lists (not the full timeline)

This matches your pinned “query surface semantics” expectation (queryable by case_id, status/queue/assignee, linked keys, time window).

### Consistency model (designer choice, avoids “read-your-writes” pain)

**[PIN] Queue views are eventually consistent; case detail is read-your-writes consistent.**

* For **case detail**, S1 may read from S2 (authoritative) or from S3 with fallback to S2, ensuring the user sees their own changes immediately.
* For **queues**, S1 accepts that S3 may lag; responses should include `as_of_ledger_cursor` so the UI can show staleness (“as of cursor N”).

This is the smallest model that remains truthful and usable.

### What is NOT allowed

* S1 asking S3 to “apply” a state change (no write path into S3).
* UI decisions that assume “queue state is truth” (queues are derived).

---

## The core truth spine as a closed internal loop

Once these joins exist, CM’s minimal internal loop is:

`S1 (intent) → S2 (append truth) → S3 (derive workflow) → S1 (triage views)`

This is exactly the internal version of your platform’s broader pattern: **one authoritative log + derived views**.

---

## Two micro-decisions we should pin now (so we don’t drift later)

1. **Idempotency scope for I-J01:**
   **Per-case** idempotency keys (preferred) unless a command creates a case (then it’s global to the case-creation attempt). This prevents cross-case collisions.

2. **Cursor semantics for I-J02/I-J03:**
   `ledger_cursor` is **exclusive-next** (same semantic as EB checkpoints) so rebuilds and staleness reporting are deterministic.

If you’re aligned, next we can **open S2 just enough** to define:

* the minimal CaseEvent taxonomy (event_type list),
* the minimal “case create vs attach” stance, and
* the canonical idempotency key recipes for the most important command types.

---

Locked — we’ll illuminate **I-J04 → I-J06** as the **Evidence Plane** joins, while keeping **S4/S2/S1/S7** opaque.

Before the joins: the platform pins that make evidence *evidence* (not truth) and force this design:

* **RTDL outputs are evidence, not ground truth**; the canonical flight recorder is **DLA**; Case Work consumes **evidence by reference** and builds an **immutable case story**. 
* **Case Workbench reads `dla/audit/...` by-ref**, may optionally read EB for history, and is always-on UI+backend. 
* If CM ever touches engine “oracle” material: **truth_products never leak into hot path**, **no PASS → no read**, **no scanning**, and **file order is non-authoritative**.

With that, here are the joins.

---

# I-J04 — S4 → S2: Evidence Attach (and Evidence Status Updates)

## Purpose

S4 takes “evidence pointers” (from DF/AL/DLA, external adjudication, optional EB refs, optional oracle refs) and turns them into **by-ref EvidenceRefs** that become part of the **case timeline truth** in S2 — *as references + status*, not copied payload.

## What crosses the join (authoritative conceptual shape)

An `EvidenceAttachRequest` (or internal “evidence command”) with:

* `case_id`
* `evidence_ref` (normalized, by-ref)
* `lane`: `INVESTIGATION_SUPPORT` | `ORACLE_REFERENCE` (oracle lane is optional and fenced)
* `attach_reason`: `TRIGGER_FROM_RTDL` | `INVESTIGATOR_ATTACH` | `EXTERNAL_OUTCOME` | `SYSTEM_CORRELATION`
* `actor` (required; human principal or “system” principal with source attribution)
* `observed_at_utc` (CM time of attachment)
* `idempotency_key` (required)

S2 returns: `ACCEPTED(case_event_id)` or `REJECTED(reason)`.

### EvidenceRef variants (the minimum set CM must support)

S4 normalizes inputs into one of these by-ref shapes (still opaque inside S4; this is boundary-meaning):

1. **`DLARecordRef`** → pointer to `dla/audit/...` (flight recorder evidence) 
2. **`EventRef`** → `event_id` + optional EB coords (topic/partition/offset) for context reads (optional) 
3. **`Decision/Action Ref`** → `decision_id`, `action_intent_id`, `action_outcome_id` (IDs only; details remain by-ref via DLA) 
4. **`ExternalDocRef`** → external evidence pointer (doc id/uri + integrity metadata)
5. **`EngineOracleRef` (optional)** → engine truth_products locator + required PASS evidence pointers (fenced)

> **Design authority call:** S4 *must* normalize to a small set of ref types so the ledger stays stable and joinable; raw payloads are not an acceptable EvidenceRef.

## Pinned laws for I-J04

**[PIN] Evidence attachments are timeline events.** “Evidence exists in the case” only if a new case timeline event is appended (no hidden side tables that become truth).

**[PIN] By-ref only.** S4 may store small redacted previews elsewhere if you later choose, but S2 timeline payload must remain *refs/locators* (privacy + drift control).

**[PIN] Idempotent attachment.** Duplicate evidence pointers must not create duplicate timeline truth. (At-least-once is assumed everywhere.)

**[PIN] Pin integrity.** If your cases are run/world-scoped, S4 must reject (or explicitly mark as “foreign”) any evidence whose ContextPins don’t match the case. Default v0: **reject** to avoid cross-world drift.

**[PIN] Oracle lane is fenced.** If `EngineOracleRef` exists, it must carry explicit refs + PASS proof; no scanning, and it never becomes hot-path “evidence” that drives automated state changes.

## Evidence “state” (how unresolved/available/superseded is represented)

Because DLA can quarantine and can supersede, and because EB retention can expire, we need a production-safe evidence status posture:

* `ATTACHED` (ref recorded)
* `PENDING` (ref exists but not currently resolvable)
* `RESOLVED` (ref was fetched successfully at least once)
* `QUARANTINED` (ref points to quarantined evidence)
* `SUPERSEDED` (ref still exists but a newer canonical ref is known)
* `UNAVAILABLE` (e.g., retention expired / object missing / access denied)

**Design authority call:** status changes are **new timeline events**, not in-place edits. That preserves the “what investigators saw when” story.

## What is out of bounds for I-J04

* Copying full audit/event payload blobs into S2 case events (“shadow DLA/EB”).
* “Auto-truthing” case outcomes based purely on attached evidence (truth is labels in Label Store).
* Using engine file row order or “latest output directory” semantics for oracle refs.

---

# I-J05 — S1 ↔ S4: Evidence Resolve Requests (rendering evidence to humans)

## Purpose

Give the UI a way to **render evidence context** while keeping:

* evidence by-ref,
* privacy/redaction enforced,
* and correctness intact when evidence is missing, quarantined, superseded, or outside retention.

## What crosses the join (conceptual)

A `ResolveEvidenceRequest`:

* `case_id`
* `evidence_ref_id` (or a selector like `case_event_id` → evidence ref)
* `actor` + role/permission context (for redaction decisions)
* `view_mode`: `SUMMARY` | `DETAIL` | `RAW_POINTERS_ONLY`
* optional `as_of` (for “what did we know when” style views)

A `ResolveEvidenceResponse`:

* `status`: `RESOLVED | PENDING | UNAVAILABLE | QUARANTINED | FORBIDDEN | SUPERSEDED`
* `rendered_view` (redacted/structured)
* `pointers` (the underlying refs, always present)
* optional `supersedes_hint` (if a newer record exists)

## Resolution sources (priority order, production-safe)

1. **DLA by-ref evidence** (`dla/audit/...`) is the primary forensic source.
2. **EB history reads** are optional, best-effort context only (retention-dependent). 
3. **Engine oracle reads** (optional lane) only via SR join surface and PASS proofs.

## Pinned laws for I-J05

**[PIN] Read does not mutate truth.** Simply viewing evidence must not rewrite case truth. (If you later want “evidence viewed” audit, that should go to security/audit logging, not the case timeline by default.)

**[PIN] Fail closed.** If evidence is missing/quarantined/unauthorized, S4 returns an explicit status; it does not fabricate content.

**[PIN] Supersedes is visible, not silent.** If DLA indicates a correction via supersedes chain, S4 must surface “superseded” rather than silently swapping content.

**[PIN] Canonical envelope expectations for EB context.** If S4 reads events from EB for context, it must rely on the canonical envelope fields (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`) and treat payload as secondary. 

**[PIN] Privacy posture.** Default views are redacted/minimal; “raw” is privilege-gated. (This matches “by-ref, minimal sensitive data in case store.”)

---

# I-J06 — S7 → S4: Evidence-ready Nudges (optional)

## Purpose

Improve freshness/latency without becoming correctness-critical.

S7 listens to *pointer events* (e.g., DLA optional pointer events on `fp.bus.audit.v1`) and nudges S4 that “new evidence is available / updated / superseded.”

## What crosses the join

An `EvidenceNudge` message:

* correlation keys: `decision_id/event_id/action_*` and/or `audit_record_ref`
* optional `supersedes_ref`
* optional `case_hint` (if known)

## Pinned laws for I-J06

**[PIN] Nudges are hints, not truth.** Missing nudges must not break correctness; S4 must still resolve evidence on-demand via I-J05 and attach via I-J04 when needed.

**[PIN] Idempotent processing.** Duplicate nudges are normal; S4 must dedupe by stable keys (e.g., audit ref / event id).

**[PIN] Any durable change still goes through I-J04.** If a nudge causes S4 to discover “now resolvable” or “superseded,” S4 records that as a new case timeline event via I-J04 (not as a hidden cache update).

## Failure posture

* If S7 is disabled or the audit topic lags: S4 still works; UI just resolves on demand and shows “pending” longer.
* If nudges arrive out of order: status events in the timeline preserve the story; S4 never rewrites history silently.

---

## The internal evidence loop these joins create (production behavior)

`Attach ref (I-J04) → Resolve on demand (I-J05) → Optional nudge (I-J06) → Status update back to ledger (I-J04 again)`

That loop is the minimum production-safe way to keep evidence **by-ref, auditable, and drift-resistant**.

---

Locked — we’ll illuminate **I-J07 → I-J10** (the **Labels Plane** joins) and I will **declare what is/ isn’t boundary-compatible** so we don’t drift from the platform’s truth map:

* **Label Store is the only label truth**: append-only label timelines with **effective_time vs observed_time** and **as-of queries**.
* **CM is the truth for cases + immutable investigation timelines**; it *produces assertions* but does not become “label truth.”
* **A label becomes truth only once stored**; corrections are new assertions (supersedes in interpretation; history remains).
* **Label writes are controlled at Label Store** (trusted writers only; auditable; no destructive edits).
* Deployment reality: CM writes labels via Label Store; Label Store may optionally emit label events to `fp.bus.control.v1`.

With that pinned, here are the internal joins.

---

# I-J07 — S2 → S5: Disposition → Label Work Items

## Purpose

Turn a **committed case disposition** (ledger truth) into a **deterministic label emission attempt** that S5 can execute *idempotently*.

This join exists so S2 remains the authoritative record (“investigator decided X”) while S5 handles the “produce LabelAssertion” obligation to Label Store.

## What crosses the join (authoritative conceptual shape)

A `LabelWorkItem` created **only** after S2 commits a disposition-like event (e.g., `DISPOSITION_SET`).

Minimum fields:

* **Link to the ledger cause (the anchor)**

  * `case_id`
  * `source_case_event_id` (the disposition event that caused this work item)
* **Subject binding (what is being labeled)**

  * `subject` (event/entity/flow) — required by the platform’s J13 pin 
  * optional `context_pins` when run/world-scoped (closed-world discipline)
* **Assertion payload seed**

  * `disposition` (CM vocabulary)
  * `mapping_id` (the pinned “disposition→label mapping” identifier; we’ll define the mapping later, but **the work item must name which mapping rule is being used** so it’s audit-stable)
  * optional `confidence`
* **Time semantics (non-negotiable)**

  * `effective_time` (when it is true)
  * `observed_time` (when we learned it)
* **Provenance**

  * `actor_principal` (human) + `origin = case_workbench`
* **Idempotency**

  * `label_idempotency_key` (required; derived from `(case_id, source_case_event_id, mapping_id)`)

### Design authority call: where do `effective_time` and `observed_time` come from?

To avoid hidden assumptions later, we pin this now:

* **`observed_time` = the disposition event’s observed_at (CM time)** (never “now at emission time”).
* **`effective_time` must be explicit** in the disposition payload *or* chosen by a documented default:

  * if the label’s subject is an `event_id` and the event has a domain `ts_utc`, default `effective_time = that ts_utc`
  * otherwise default `effective_time = observed_time`
    This preserves the platform’s effective/observed split without making S5 guess unpredictably.

## Delivery semantics

**[PIN] S2→S5 is at-least-once**; S5 dedupes on `label_idempotency_key`. This mirrors your global posture and prevents duplicate writes.

## Out of bounds (declared)

* “Labeling” happening without a committed disposition/timeline event.
* S5 inventing subjects/times silently (must be explicit or follow the pinned defaults above).
* S2 storing “labels as state” instead of emitting work items + recording outcomes.

---

# I-J08 — S5 → S2: Label ACK / Failure Recording

## Purpose

Make the **investigation story complete**: S2 must record *that* CM attempted to emit a label, and whether it was accepted/rejected/pending — without claiming label truth ownership.

Label truth still lives only in Label Store.

## What crosses the join

A `LabelEmitResult` that corresponds to a single `LabelWorkItem`:

* `case_id`
* `source_case_event_id` (so the ledger can tie the result to the disposition)
* `label_idempotency_key`
* `result_status`:

  * `SUBMITTED` | `ACCEPTED` | `REJECTED` | `RETRY_SCHEDULED`
* On `ACCEPTED`: `label_assertion_id` (or stable pointer/receipt returned by Label Store)
* On `REJECTED`: `reason_code` (+ message), and whether it’s retryable

## Pinned laws

* **[PIN] S2 records these as new timeline events** (e.g., `LABEL_SUBMITTED`, `LABEL_ACCEPTED`, `LABEL_REJECTED`). No in-place mutation of the disposition event.
* **[PIN] Idempotent recording:** duplicates of the same emit result must not create duplicate timeline events. (Dedup key: `label_idempotency_key + result_status`.)
* **[PIN] “Truth only once stored”:** S2 must not treat “submitted” as truth; only “accepted” means “Label Store now contains truth.”

## Failure posture (production-real)

* Label Store unavailable: S5 reports `RETRY_SCHEDULED`; S2 records “pending” (still truthful).
* Hard rejection (auth/schema/forbidden family): S2 records `LABEL_REJECTED` and exposes it in the case UI.

---

# I-J09 — S1 ↔ S5: Label Context Reads (as-of)

## Purpose

Let investigators see label truth **as context** while preserving leakage discipline and timeline semantics.

Label Store is the truth and supports **as-of queries** using effective vs observed time.

## What crosses the join

A `LabelContextQuery` and `LabelContextResult`.

### Query must support (minimum)

* `subject` (event/entity/flow)
* `mode`:

  * `CURRENT_TRUTH` (as-of now)
  * `KNOWN_AT` (as-of a provided boundary)
* `as_of_observed_time` (required when mode = `KNOWN_AT`)
* optional filters: label family, provenance, confidence thresholds

### Result must include

* the returned **timeline** (not “one value”)
* enough metadata to show the basis:

  * `as_of_observed_time_used`
  * (optional) `as_of_effective_time_used` if you support that view
* pointers/ids (`label_assertion_id`, supersedes links where relevant)

## Design authority call: default “known at time” semantics

To prevent leakage and to align with the platform’s “as-of” discipline:

* **Default “KNOWN_AT” uses observed_time as the boundary** (what was known then).
  Effective_time remains part of the returned assertions, but the *visibility* cut is observed_time.

## Out of bounds

* UI reading “latest labels” without specifying whether it’s “current” or “known at time.”
* S5 fabricating label truth from CM state; it must read Label Store.

---

# I-J10 — S7 → S5: Label-changed Nudges (optional)

## Purpose

Improve UI freshness and reduce polling by letting S5 know “label truth changed” (but never making nudges authoritative).

Deployment explicitly allows **optional label events → `fp.bus.control.v1`**.

## What crosses the join

A `LabelChangedNudge` (a hint), typically containing:

* `label_assertion_id` or stable ref
* `subject` keys
* `observed_time` of the new assertion (if present)
* optional `supersedes_ref`

## Pinned laws

* **[PIN] Nudges are hints, not truth.** S5 must re-read Label Store to obtain truth. Missed nudges must not break correctness.
* **[PIN] Idempotent nudge handling.** Duplicates are normal; dedupe by assertion id / subject + observed_time.
* **[PIN] Nudges may be disabled by profile.** If disabled, S5 still serves correct context reads by querying Label Store (only freshness suffers).

---

## The internal label loop these joins create

This is the production-true closure inside CM:

`S2 (DISPOSITION_SET) → I-J07 work item → S5 writes LabelAssertion → I-J08 records ACK/FAIL in S2 → S1 reads label context via I-J09 (optionally refreshed by I-J10 nudges)`

…and it stays boundary-correct because:

* CM truth = investigation timeline,
* Label Store truth = label timelines,
* and the only coupling is explicit, idempotent, append-only facts.

---

Locked — we’ll illuminate **I-J11 → I-J15** (Manual Intervention plane + optional Signals plane), still keeping **S2/S4/S6/S7** opaque.

Before the joins, I’m going to **declare the boundary-compatibility laws** for this slice (designer authority):

## Boundary laws for I-J11 → I-J15

1. **Only Actions Layer executes side effects.** CM (and DF) can only *request* actions; “manual override” is a higher-privilege ActionIntent, not a bypass.
2. **CM cannot claim an action happened until an outcome exists.** Outcomes are immutable (including denial/failure) and become evidence via the RTDL→Case bridge (DF/AL/DLA pointers).
3. **If CM publishes case events, they are control facts (signals), not the primary case record.** They must go through IG and use the canonical event envelope; IG returns explicit ADMIT/DUPLICATE/QUARANTINE outcomes (no silent drop).
4. **Everything is at-least-once; idempotency is mandatory.** (This is why work items and receipts exist.)

With those pinned, here are the joins.

---

# I-J11 — S2 → S6: Manual Action Work Items

### Purpose

When the case timeline records **“ACTION_REQUESTED”** (or equivalent), S6 must produce a **Manual ActionIntent** request that is policy-checked, idempotent, and joinable — while S2 remains the authoritative investigation record.

### What crosses the join (authoritative conceptual payload)

A `ManualActionWorkItem` derived from a committed case event:

* **Anchors**

  * `case_id`
  * `source_case_event_id` (the timeline event that requested the action)
* **Who + why**

  * `actor_principal` (human) + `origin = case_workbench` (mandatory for AL authz)
  * `reason_code` / “justification” pointer (often a note/evidence ref, not a blob)
* **What action**

  * `action_type`
  * `target_ref` (entity/event refs; scoped)
  * optional `constraints` (time window, limit, TTL)
* **Scope pins**

  * `ContextPins` when run/world-scoped (so AL can authorize by scope)
* **Evidence refs (by-ref)**

  * `evidence_refs[]` (DLA refs / EB coords / decision ids) — supports “why did we do this” without copying payloads
* **Idempotency**

  * `action_idempotency_key` (required)
  * **Designer pin:** `action_idempotency_key` MUST be derivable from `(case_id, source_case_event_id, action_type, target_ref)` so retries can’t fork side effects.

### Delivery semantics

* **At-least-once S2→S6**; S6 must dedupe on `action_idempotency_key`.

### What is out-of-bounds

* S6 inventing actions that aren’t anchored to a committed case event.
* S6 executing side effects directly (violates AL-only executor).

---

# I-J12 — S6 → S2: Intent Submitted / Local Reject / Pending

### Purpose

Record *what CM attempted to do* and the **submission state**, without pretending that submission == execution.

### Critical designer clarification (to avoid drift)

There are **two kinds of “deny”**:

* **Pre-check deny (CM/S6):** user not allowed to request this action → the intent is never submitted.
* **Execution deny (AL):** AL emits a **Denied ActionOutcome** (still immutable, still idempotent). This is an *outcome* and should be captured via I-J13 evidence attach, not treated as a mere “submit response.”

So I-J12 is about **submission truth**, not final execution truth.

### What crosses the join

A `ManualIntentSubmitResult` referencing the work item:

* `case_id`
* `source_case_event_id`
* `action_idempotency_key`
* `submit_status`:

  * `SUBMITTED` (accepted for processing / queued to AL pathway)
  * `PRECHECK_REJECTED` (actor not permitted by CM policy)
  * `SUBMIT_FAILED_RETRYABLE` (transport failure; will retry)
  * `SUBMIT_FAILED_FATAL` (invalid shape; will not retry)
* Optional: `action_intent_id` (if assigned/known) or “intent locator/pointer”

### Pinned laws

* **S2 records submission state as new timeline events** (e.g., `ACTION_INTENT_SUBMITTED`, `ACTION_REQUEST_REJECTED`, `ACTION_INTENT_SUBMIT_FAILED`). No mutation of the original request event.
* **Idempotent recording:** duplicates of the same submit result must not create duplicate timeline entries (dedupe by `action_idempotency_key + submit_status`).

### Failure posture

* If AL pathway is down: S6 emits `SUBMIT_FAILED_RETRYABLE`; S2 shows “pending submission” and remains truthful.
* If CM policy denies request: S2 shows “rejected” (no hidden bypass).

---

# I-J13 — S4 → S2: Outcome Evidence Attach (closing the action loop)

### Purpose

Close the manual-action story in the case timeline by attaching **outcome evidence** (by-ref) when it arrives from the RTDL evidence bridge.

This is exactly what your platform pins: CM consumes **action outcomes as evidence refs** (from AL outcomes + DLA pointers) and builds an immutable story.

### What crosses the join

An `ActionOutcomeEvidenceAttach` from S4 into S2:

* `case_id`
* linkage keys:

  * `action_idempotency_key` (preferred join key)
  * and/or `action_intent_id`, `action_outcome_id`
* evidence pointers (by-ref):

  * `DLARecordRef` to `dla/audit/...` (preferred canonical evidence)
  * optional EB coords for admitted outcome events (context)
* `outcome_class`:

  * `EXECUTED | DENIED | FAILED | TIMED_OUT | UNKNOWN`
* `observed_at_utc` (when CM learned outcome)

### Pinned laws

* **Outcomes are immutable and attributable**; denial is a first-class outcome (not an exception).
* **Attach-by-ref only:** S2 stores pointers, not the full outcome payload.
* **Status evolution is append-only:** “pending → executed/denied” is represented as new timeline events, not overwrites.

### Failure posture

* If the outcome evidence is temporarily unavailable (audit record not yet written / quarantined), S4 attaches “pending/unresolved” status and later appends an update when resolvable (same pattern as evidence plane).

---

# I-J14 — S2 → S7: Publish Case Signal Work Items (optional)

### Purpose

Mirror selected case timeline events as **control-plane signals** for automation/ops — without making EB the primary case store.

Deployment explicitly allows: “optional case events → `fp.bus.control.v1`.”

### What crosses the join

A `CaseSignalWorkItem` emitted when S2 appends certain event types (the “publish set” is profile-configured):

* `case_id`
* `source_case_event_id`
* `event_type` (control signal taxonomy)
* `ts_utc` (use the case event’s observed timestamp)
* **canonical envelope fields**

  * `event_id` (must be stable; derive from `source_case_event_id`)
  * `manifest_fingerprint` (and optional `parameter_hash/run_id/scenario_id/seed` if pinned to a world scope)
* `payload` (small, by-ref friendly):

  * case summary fields + linkage keys + pointers (no evidence blobs)

### Pinned laws

* **If it goes on the bus, it goes through IG.** S7 is effectively the “producer adapter” that submits to IG for ADMIT/QUARANTINE/DUPLICATE.
* **Canonical envelope is mandatory** (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` required). 
* **Signals are optional and must never be correctness-critical.** Disabling S7 must not change CM truth — only automation/freshness.

### What is out-of-bounds

* Publishing sensitive evidence payloads as “case events.”
* Treating the presence/absence of a published signal as part of case truth.

---

# I-J15 — S7 → S2: Publish Receipt Recording (optional)

### Purpose

Make it provable what happened to CM’s optional signals at the platform trust boundary.

IG’s posture is explicit outcomes + receipts; no silent drop. S2 should record the receipt outcome so case operations are explainable.

### What crosses the join

A `PublishReceiptResult` corresponding to a single `CaseSignalWorkItem`:

* `case_id`
* `source_case_event_id`
* `published_event_id`
* `ig_outcome`: `ADMIT | DUPLICATE | QUARANTINE`
* `receipt_ref` (pointer/locator to the IG receipt evidence; may include policy_rev)
* optional `quarantine_ref` if quarantined

### Pinned laws

* **S2 records receipt outcome as new timeline events** (e.g., `CASE_SIGNAL_ADMITTED`, `CASE_SIGNAL_DUPLICATE`, `CASE_SIGNAL_QUARANTINED`).
* **Idempotent recording:** dedupe by `(published_event_id, ig_outcome)`.
* **Non-fatal:** quarantine here affects only the signal stream, not CM truth.

---

## The two internal loops these joins create

### Manual action closure loop (core)

`S2 (ACTION_REQUESTED) → I-J11 work item → S6 submit → I-J12 submission recorded → (later) I-J13 outcome evidence attached → S2 timeline shows executed/denied/failed`

### Optional signal loop (non-core)

`S2 event → I-J14 publish work item → S7 submits via IG → I-J15 records receipt outcome`

---

Locked — here’s **I-P01 → I-P04** illuminated as **production-grade internal paths**, with **S1–S7 still opaque** and with me explicitly declaring what is **in-bounds vs out-of-bounds** relative to your platform network.

These paths must remain consistent with the outer pins:

* **RTDL outputs are evidence, not truth**; CM builds **cases + append-only timelines** from **refs/IDs**, not payload copies.
* **Labels become truth only in Label Store** (append-only timelines; effective vs observed time; as-of reads).
* CM is an **always-on UI + backend** with `case_mgmt` timelines; reads `dla/audit/...` by-ref; writes labels via Label Store; manual actions go as ActionIntents via AL/IG path.

---

# I-P01 — New case from upstream evidence

**Path:** `(S7 or inbound evidence endpoint) → S4 intake → S2 append (case created/attached + evidence ref) → S3 queue updates → S1 UI shows it`

## Purpose

Turn “something happened / system decided / action outcome exists” into an **investigation unit** without duplicating truth stores.

## Production sequence (step-by-step)

1. **Inbound trigger arrives** (from DF/AL/DLA pointer flow, or external adjudication feed, or optional bus pointer). Importantly: it arrives as **IDs + refs**, not a payload blob.
2. **S4 normalizes it** into one or more **EvidenceRefs** (e.g., `DLARecordRef`, `DecisionRef`, `ActionOutcomeRef`, optional `EventRef`), and computes an **idempotency key** for “this trigger.”
3. **S4 chooses “create vs attach”** using a deterministic matching posture:

   * If there’s an **open case** whose join keys match (ContextPins + primary subject key), **attach evidence**.
   * Else **create new case** and attach the evidence.
     (Implementation can vary; the *principle* is deterministic clustering to avoid drift.)
4. **S2 appends** timeline truth:

   * `CASE_CREATED` (if new)
   * `EVIDENCE_ATTACHED` (always)
   * (optionally) `TRIGGER_RECEIVED` as the “bridge” record, if you want that explicitly visible in the case story.
     CM’s append-only timeline posture is pinned.
5. **S3 consumes ledger events** and updates queues/assignment/escalation views (derived).
6. **S1 UI** shows the case in the appropriate queue (“unassigned”, “my queue”, etc.).

## Idempotency & duplicates (designer pin)

* **[PIN] Trigger intake is at-least-once safe**: duplicates of the same upstream pointer must not create multiple cases or duplicate `EVIDENCE_ATTACHED` events.
* Recommended uniqueness anchor: `(trigger_source, trigger_id)` where `trigger_id` is decision_id / action_outcome_id / audit_record_id / external_outcome_id.

## Failure posture

* If evidence is not yet resolvable (audit record not written / quarantined): the case is still created/attached, but the evidence ref is marked “pending/unavailable” until it resolves.

## Out-of-bounds (declared)

* Creating cases by copying full event/audit payloads into CM (violates by-ref/evidence posture).
* Auto-writing labels from these triggers (labels require the CM disposition→LabelAssertion route into Label Store).

---

# I-P02 — Investigator triage

**Path:** `S1 → S3 (queues/views) → S1 → (open case) → S2/S3 summary`

## Purpose

Enable the human workflow (triage/assignment/escalation) while keeping **one truth** (S2 timeline) and **derived workflow** (S3).

## Production sequence

1. **S1 requests queues/views from S3** (“my queue”, “unassigned”, “escalated”).
2. **S3 responds with summaries**, each including:

   * `case_id`
   * current derived state (status/assignee/priority)
   * linkage keys (decision_id/event_id/entity_ref)
   * **as-of cursor** (how fresh the view is)
3. Investigator **opens a case**:

   * S1 retrieves **case detail** (either via S3 with fallback, or directly from S2 for “truth detail”).
   * S1 shows the **timeline + attached evidence refs** (not payload).
4. Investigator takes actions (assign, note, escalate) → those become **commands into S2** (I-J01), which then flow back to S3 for updated queues.

## Consistency model (designer pin)

* **[PIN] Queue views are eventually consistent; case detail is read-your-writes consistent.**
  This keeps CM usable when projections lag, without turning projections into truth.

## Failure posture

* If S3 is lagging/unavailable: S1 can still show **case-by-id + timeline** from S2; only “queues/search” degrade.

## Out-of-bounds

* Any “write” performed by S3 (S3 must never become a second truth store).

---

# I-P03 — Evidence drill-down

**Path:** `S1 → S4 resolve → (optional) S4 → S2 “evidence resolved/unavailable” → S1 render`

## Purpose

Let an investigator see “why did the system decide/do that?” using the **DLA flight recorder** and by-ref evidence posture.

## Production sequence

1. Investigator clicks an attached evidence item in S1.
2. **S1 asks S4 to resolve** the EvidenceRef (with actor/role context for redaction).
3. **S4 resolves by priority**:

   * Primary: fetch `dla/audit/...` record by-ref (canonical evidence).
   * Optional: read EB history for extra context (retention-dependent; evidence only). 
4. **S4 returns a rendered view**:

   * redacted summary by default
   * explicit status if `UNAVAILABLE/QUARANTINED/SUPERSEDED/FORBIDDEN`
5. **Optional state update:** if the resolution status changed materially (e.g., from PENDING→RESOLVED or RESOLVED→SUPERSEDED), S4 appends a **new timeline event** to S2 noting the status change. (Not “viewed”; just “resolution status changed.”)

## Key pinned behaviors

* **[PIN] Fail closed:** missing/quarantined/unauthorized evidence returns an explicit status; nothing is fabricated.
* **[PIN] Supersedes is visible, not silent:** if DLA corrected something, CM must surface “superseded” rather than quietly swapping what the investigator saw.

## Out-of-bounds

* Pulling evidence “by scanning” object store; evidence must be referenced/joinable.
* Turning resolved evidence into “truth labels” automatically.

---

# I-P04 — Disposition → label emission

**Path:** `S1 → S2 (disposition event) → S5 (label work item) → S2 (label emitted/failed/pending) → S3 updates → S1 UI`

## Purpose

Convert a human adjudication into **ground truth** correctly — meaning: **as a LabelAssertion written to Label Store**, not “labels-in-case.”

## Production sequence

1. Investigator sets a disposition in S1.
2. **S1 issues a command to S2** to append `DISPOSITION_SET` to the case timeline (actor required; idempotent).
3. **S2 emits a LabelWorkItem to S5** anchored to that specific disposition event (so emission is deterministic and replay-safe).
4. **S5 maps disposition → LabelAssertion** using an explicit mapping rule ID (so later you can say “which mapping produced this”), and submits the assertion to **Label Store**.
5. **Label Store ACKs** (or rejects). Remember: *label becomes truth only once stored*.
6. **S5 reports outcome back to S2**, which appends:

   * `LABEL_SUBMITTED` / `LABEL_ACCEPTED` / `LABEL_REJECTED` / `LABEL_PENDING`
     as new timeline events (append-only story).
7. **S3 updates queues/views**, and S1 reflects the new state (“Resolved”, “Pending label write”, etc.).

## Time semantics (designer pin)

* **[PIN] effective_time vs observed_time must be preserved** in the emitted LabelAssertion; CM must not collapse them.

## Failure posture

* Label Store down: S5 retries; S2 records “pending”; CM remains truthful and usable.
* Label rejected (auth/schema): S2 records rejection and the case remains resolvable (investigator can correct and re-emit).

## Out-of-bounds

* Marking the case “truth-labeled” before Label Store acceptance.
* Editing an old disposition/label event instead of appending a correction (append-only posture).

---

## A quick “path integrity” pin (so we don’t drift when we go deeper)

**[PIN] I-P01/I-P03 produce case story from evidence refs; I-P04 is the only path that creates ground truth (via Label Store); and I-P02 is purely workflow view over the story.**

If you want to keep moving in the same illumination order, the next natural set is **I-P05 → I-P08** (manual action + optional publishing + late evidence/label nudges).

---

Locked — here are **I-P05 → I-P08** illuminated as **production internal paths** (S1–S7 still opaque), with explicit “what’s allowed / not allowed” so we stay inside your platform boundary laws.

---

# I-P05 — Manual action request → later outcome (core)

**Path:**
`S1 → S2 (action requested) → S6 (submit intent) → S2 (intent submitted/pending/precheck-rejected) → later: S4 ingests outcome pointer → S2 attaches outcome evidence → S3 updates → S1 UI`

## Purpose

Allow investigators to cause side effects **safely and audibly** without CM executing anything. The executor is **Actions Layer (AL)**; CM is request + record.

## Production sequence (step-by-step)

1. Investigator triggers a manual action in the UI (block, release, notify, etc.).
2. **S1 issues a command into S2** to append an `ACTION_REQUESTED` case event:

   * actor required,
   * idempotency key required,
   * includes action type + target ref + justification refs (by-ref).
3. **S2 emits a ManualActionWorkItem to S6** (I-J11), anchored to that exact `source_case_event_id` so retries cannot fork.
4. **S6 performs prechecks** (policy/role allowlist, shape validation) and then submits a **Manual ActionIntent** via the AL/IG pathway (executor is AL).
5. **S6 reports submit state back to S2** (I-J12) as a new timeline event:

   * `ACTION_INTENT_SUBMITTED` (accepted for execution),
   * `ACTION_REQUEST_REJECTED_PRECHECK` (CM policy denied),
   * `ACTION_INTENT_SUBMIT_FAILED_RETRYABLE` (transport failure; will retry).
6. **Later**, the actual outcome arrives back into CM as **evidence** (not “a response”):

   * AL emits ActionOutcome (executed/denied/failed) and DLA records it as `dla/audit/...`.
   * CM receives pointers (DF/AL/DLA → CM bridge) or audit pointer nudges (optional) and S4 attaches the outcome evidence to the case timeline via I-J13.
7. **S3 updates derived views** (e.g., case status “Action completed/Denied”) and S1 shows the final state with the outcome evidence link.

## Production pins (designer declarations)

* **[PIN] Submission is not execution.** `ACTION_INTENT_SUBMITTED` does not mean “action happened.” Only an attached **outcome** closes the loop.
* **[PIN] Denial is a first-class outcome** (usually from AL), and should appear as outcome evidence, not as a silent UI failure.
* **[PIN] Everything is idempotent.** The intent idempotency key is derived from the case event that requested it; retries cannot double-execute.

## Out-of-bounds

* CM executing the side effect directly (bypass AL).
* CM “marking success” without an immutable outcome evidence ref.
* CM treating a submit ACK as proof the action happened.

---

# I-P06 — Optional case event publish (signal path)

**Path:**
`S2 emits publish work item → S7 publishes via IG→EB(control) → S7 records publish receipt → S2 timeline records “admitted/duplicate/quarantined”`

## Purpose

Publish **control facts** (“case opened/escalated/resolved”) for automation/ops without turning EB into the case database. CM truth remains the S2 timeline.

## Production sequence

1. A case timeline event is appended in S2 that matches the “publish set” (profile knob).
2. **S2 emits a CaseSignalWorkItem to S7** (I-J14) containing:

   * canonical envelope fields,
   * event_id derived from `source_case_event_id`,
   * small payload (IDs + pointers; not evidence blobs).
3. **S7 submits to IG** (because CM is now acting as a producer), and IG decides **ADMIT / DUPLICATE / QUARANTINE** and produces a receipt.
4. **S7 reports the receipt outcome back to S2** (I-J15), and S2 appends a timeline event like:

   * `CASE_SIGNAL_ADMITTED` or `CASE_SIGNAL_QUARANTINED` (with receipt ref).

## Production pins

* **[PIN] Signals must never become a correctness dependency.** If S7 is disabled or IG quarantines, CM truth is unchanged — only automation/freshness degrades.
* **[PIN] Canonical envelope + IG trust boundary always applies** for any bus emission.
* **[PIN] Receipt outcomes are explicit** (no silent drops). Recording them in S2 keeps the platform explainable.

## Out-of-bounds

* Publishing sensitive evidence payloads or raw audit content as “case events”.
* Treating the presence of a control event as “case truth”.

---

# I-P07 — Evidence becomes available later (optional freshness loop)

**Path:**
`S7 consumes audit pointer event (optional) → nudges S4 → S4 resolves by-ref → S4 appends update to S2 → S3/UI reflect “now available”`

## Purpose

When DLA writes or corrects audit records **after** the case was opened (normal in distributed systems), CM should become “fresh” without polling, but correctness must not depend on these nudges.

## Production sequence

1. DLA emits an **audit pointer event** on `fp.bus.audit.v1` (optional) indicating a new/updated audit record ref.
2. **S7 consumes it** and emits an **EvidenceNudge** to S4 (I-J06) with correlation keys (decision/action/event ids, audit ref).
3. **S4 attempts resolution** (by-ref fetch `dla/audit/...`, apply quarantine/supersedes logic).
4. If resolution status materially changes, **S4 appends a new timeline event to S2** via I-J04:

   * `EVIDENCE_RESOLVED` / `EVIDENCE_STILL_UNAVAILABLE` / `EVIDENCE_SUPERSEDED`.
     (Append-only: do not rewrite the old “pending” event.)
5. **S3 updates derived views** and the UI reflects “evidence now available” (or “superseded”).

## Production pins

* **[PIN] Nudges are hints, not truth.** Missing them must not break correctness; evidence can still resolve on-demand via I-P03.
* **[PIN] Supersedes is visible, not silent.** If a newer audit record supersedes a prior one, CM must surface that fact rather than invisibly swapping content.
* **[PIN] The case timeline records the evolution of availability.** That’s key to auditability (“what did we know when”).

## Out-of-bounds

* Updating evidence status only in caches (hidden); changes must be represented as new timeline events if they affect what an investigator sees as “resolved.”

---

# I-P08 — Label changes outside CM (optional)

**Path:**
`S7 consumes label control event → nudges S5 → S5 refreshes as-of reads → S1 UI sees updated context (without rewriting CM truth)`

## Purpose

In production, labels may be written by multiple trusted writers (CM, external adjudication ingest, back-office tools). CM should see label truth changes quickly for context **without** polling heavily, but label truth remains in Label Store.

## Production sequence

1. Label Store emits a **label event** to `fp.bus.control.v1` (optional) indicating a new LabelAssertion exists.
2. **S7 consumes** and emits a **LabelChangedNudge** to S5 (I-J10) containing subject keys + assertion id/pointer.
3. **S5 refreshes** any relevant cached context (if caching exists) by re-reading Label Store truth **as-of** (never trusting the nudge as truth).
4. The next time S1 requests label context (I-J09), it reflects the updated truth.

## Production pins

* **[PIN] Nudges are “go read truth” hints.** If nudges are missing, CM still reads Label Store directly and remains correct.
* **[PIN] CM truth is not rewritten by label changes.** A label change may influence investigator decisions, but it does not retroactively rewrite the case timeline; any “reopen” must be an explicit new case event.
* **[PIN] As-of semantics remain explicit.** UI should not confuse “current truth now” with “known at time of decision.”

## Out-of-bounds

* Treating the control event payload as label truth (must query Label Store).
* Silent reopening/closing of cases purely because a label changed; it must be an explicit case event if it changes case status.

---

## A unifying “path pin” for I-P05 → I-P08

**[PIN] I-P05 is the only internal path that causes external side effects (via AL) and it closes only on immutable outcomes; I-P06/I-P07/I-P08 are optional freshness/automation paths whose failure can only degrade freshness, never corrupt truth.**

---

Locked — let’s “illuminate” **I-L01 → I-L06** as the **production cycles** that *must* hold inside CM, while keeping **S1–S7** opaque. Everything below is **authoritative** for CM’s internal network boundary behavior (and must remain consistent with your platform truth map).

---

## Global loop laws (apply to all I-Lxx)

These are the invariants that make CM compatible with the outer platform network:

* **S2 (Ledger) is the only CM truth**: cases + append-only investigation timelines. 
* **Derived ≠ truth**: S3/S4/S5 caches/projections can be wrong/stale and must be rebuildable. 
* **Evidence is by-ref** (DLA/EB/oracle locators), never copied into “case truth payload” as authoritative blobs.
* **Labels become truth only in Label Store** (append-only timelines; effective vs observed time; as-of reads). 
* **Actions execute only via Actions Layer**; CM requests + records outcomes as evidence.
* **At-least-once everywhere → idempotency everywhere** (commands, work items, receipts). 

With that pinned, here are the loops.

---

# I-L01 — UI consistency loop

`S1 → S2 (write) → S3 (derived views) → S1 (read)`

### What this loop guarantees (production meaning)

* **Case detail is truth-consistent**: after a write, the investigator can see their change reflected immediately in the **case timeline** (S2 truth).
* **Queues/search are eventually consistent**: S3 views may lag, but must converge deterministically.

### Closure condition

This loop is “closed” when **S1 can render**:

1. the **committed case event** in S2 (read-your-writes), and
2. the **updated triage view** in S3 (eventual).

### Drift traps (declared out-of-bounds)

* “Write via S3” (S3 must never be an authority).
* “Queue state is truth” (queues are derived convenience).

### Production-grade behavior knobs (without opening boxes)

* **Staleness signaling**: S3 responses include an `as_of` marker (“how fresh is this view”) so the UI can show “as-of cursor N”.
* **Fallback rule**: if S3 lags/unavailable, S1 still can render case-by-id + timeline directly from S2 (so investigation doesn’t stop).

---

# I-L02 — Evidence closure loop

`S4 (attach/resolve) → S2 (timeline) → S1 (render)` (+ optional nudge `S7 → S4`)

### What this loop guarantees

* Evidence becomes part of the **case story** as **references + resolution status**, not embedded payload.
* Investigators can view evidence *when available*, and can still progress when it’s not.

### Closure condition

This loop is “closed” when:

* the evidence ref is **attached** to the case (S2 has an `EVIDENCE_ATTACHED`-type event), and
* S1 can render either:

  * a **resolved, redacted evidence view**, or
  * an **explicit non-resolved state** (`PENDING`, `UNAVAILABLE`, `QUARANTINED`, `SUPERSEDED`, `FORBIDDEN`).

### Key authoritative decisions

* **Fail-closed**: if evidence can’t be resolved, S4 returns an explicit status (no guessing).
* **Supersedes is visible**: if DLA indicates correction, S1 must see “superseded” rather than silent replacement.
* **Status evolution is append-only**: “pending → resolved” is represented as *new* case timeline events, not mutation of old ones.

### Why the optional nudge exists (and what it can’t do)

`S7 → S4` nudges can reduce polling and latency (“evidence ready”), but:

* **nudges are hints**, not correctness dependencies;
* missing nudges must not break evidence resolution on demand.

---

# I-L03 — Disposition / label closure loop

`S2 (disposition) → S5 (emit) → S2 (ack recorded) → S3/S1 (updated case state)`

### What this loop guarantees

* A disposition becomes **ground truth only** via **Label Store acceptance**, while CM still records the investigation story end-to-end.

### Closure condition (authoritative)

This loop is closed only when **S2 records an ACK outcome** of the label emission attempt:

* `LABEL_ACCEPTED` (Label Store truth exists), **or**
* `LABEL_REJECTED` (truth was not written), **or**
* `LABEL_PENDING/RETRYING` (truth not yet written, explicitly shown)

**Not closed** at “submitted” — submission is not truth. 

### Key authoritative decisions

* **Mapping is named**: each emission must be anchored to a specific disposition event + mapping identifier (so it’s explainable later).
* **Time semantics preserved**: effective vs observed time must not collapse.
* **Corrections are append-only**: if an investigator changes their mind, that’s a new disposition + new label assertion attempt, not editing history. 

### Failure posture (production-ready)

* Label Store down → the case can still be worked; the label stays **pending**; no fake success.
* Rejection → recorded + visible; human can correct/redo.

---

# I-L04 — Manual action closure loop

`S2 (request) → S6 (intent) → (later evidence) S4 → S2 (outcome attached) → S3/S1`

### What this loop guarantees

* Humans can request side effects **without bypass**, and CM can show a truthful lifecycle: requested → submitted → outcome.

### Closure condition (authoritative)

This loop is closed only when **outcome evidence is attached** to the case:

* `ACTION_OUTCOME_EXECUTED` / `DENIED` / `FAILED` (or equivalent) with by-ref pointers to authoritative evidence (typically DLA).

### Key authoritative decisions

* **Two denials exist** (must be distinguished):

  * **Precheck rejected** (CM/S6 policy says “you may not request this”) → closes the “request attempt” but does not create an AL outcome.
  * **AL denied outcome** (Action Layer decision) → must appear as immutable outcome evidence (via S4). 
* **Submission ≠ execution**: `ACTION_INTENT_SUBMITTED` is never presented as “done.”

### Failure posture

* AL unavailable → intent submission is retrying; case shows pending.
* Outcome delayed → case shows pending; no assumption of success.

---

# I-L05 — Optional signal loop

`S2 (case event) → S7 (publish) → S2 (receipt recorded)` (never required for truth correctness)

### What this loop is for

Purely **control-plane observability/automation**: “case opened/escalated/resolved” signals that travel through **IG → EB(control)** and get receipts.

### Closure condition

This loop is closed when **S2 records the IG receipt outcome**:

* `SIGNAL_ADMITTED` / `DUPLICATE` / `QUARANTINED` with a receipt pointer.

### Key authoritative decisions

* **Signal failure is non-fatal**: disabling S7 or quarantines must not alter CM truth, only external automation/freshness.
* **No payload dumping**: signals carry IDs + pointers, not sensitive evidence blobs.
* **Receipts are explicit**: no silent drops at the trust boundary.

---

# I-L06 — Rebuild / reconcile loop (implicit in production)

Anything derived (S3 views, some S4/S5 caches) must be rebuildable from S2 truth + external authoritative reads.

### What this loop guarantees

CM remains correct across:

* restarts,
* partial outages,
* lagging projections,
* retention changes,
* and backfill/replay operations in the broader platform.

### Authoritative rebuild rules (designer declarations)

1. **S2 is never “rebuilt” from others** (it is the authoritative ledger).
2. **S3 is always rebuildable from S2** (queues/search/state summaries).
3. **S4 is resolvable from refs**: evidence registry can be rebuilt by re-scanning S2 timeline for EvidenceRefs, then re-resolving by-ref (DLA/EB/oracle) as needed.
4. **S5 is resolvable from truth owners**:

   * label context comes from Label Store reads,
   * label emission state can be reconstructed by reading S2’s emission events; if needed, it can re-check Label Store for the presence of an assertion **by idempotency key** (idempotent reconciliation).

### What *must not* happen during reconcile

* **No silent rewriting of the case story**. Rebuild may:

  * refresh caches,
  * recompute queues,
  * re-resolve evidence,
  * re-derive “current status,”
    but it must not mutate historical timeline events.

If reconcile discovers a material truth-lifecycle change that investigators must see (e.g., “label now accepted” that was previously unknown), the correct behavior is to **append a new timeline event** that records the discovery — not rewrite the past.

### Why this aligns with the environment ladder

Local/dev/prod differ in retention, strictness, and scale — so rebuild/reconcile must be a first-class loop. It ensures CM remains operational even when EB history is short (local) and evidence must come primarily via DLA refs.

---

## One concise “loop discipline” pin (to carry forward as we go deeper)

**Truth loops (L01–L04) close only on authoritative acknowledgements/evidence; optional loops (L05) only affect freshness/automation; reconcile loop (L06) can rebuild anything derived but cannot rewrite case history.**

---

Yep — there’s a *negative space* around CM that’s just as important as the joins. We’ve hinted at some “out-of-bounds” along the way, but here’s the **explicit, authoritative non-join / non-path / non-loop set** for CM (both **platform boundary** and **internal CM network**) so we can’t drift later.

---

## A) Platform-boundary non-joins (CM must NOT have these edges)

### A1) Trust-boundary bypasses

* **CM must not write directly to EB** (traffic or control) **without IG**. Any emission is **CM → IG → EB** and must use the canonical envelope.
* **CM must not “execute” side effects** (blocks/releases/notifications/etc.). Manual interventions must be **ActionIntents executed by Actions Layer**, with immutable outcomes.
* **CM must not treat DLA as writable** or “correct” audit truth. DLA is the flight recorder; CM reads by-ref.

### A2) Truth-ownership violations

* **CM must not become a label store.** It can record “I emitted / I saw accepted,” but **label truth lives only in Label Store** (append-only timelines; as-of). 
* **CM must not become a decision engine.** Decisions/policy application live in DF; CM is the human workflow + case story, not automated adjudication logic. 
* **CM must not mutate registry/model truth** (promotion/rollback/active resolution). That’s Registry/MPR governance. 

### A3) Engine interface violations (oracle/fidelity rules)

* **CM must not scan engine output directories** or infer “latest.” Oracle reads (truth_products) must start from **SR join surface** and obey **No PASS → no read**.
* **CM must not treat `truth_products` as business traffic** or use them to drive hot-path behavior. Roles are binding (`business_traffic` vs `truth_products` vs `audit_evidence` vs `ops_telemetry`).
* **CM must not rely on file/row order** for engine surfaces. Order is non-authoritative by contract. 

---

## B) Internal CM non-joins (between S1–S7) — hard bans

These prevent “two truths” and hidden coupling inside the vertex.

### B1) Projection truth leaks

* **S1 must not write to S3** (no “set assignee/status via queue store”). All writes go **S1 → S2** only. 
* **S3 must not write to S2** (no backdoor “auto-escalate” truth writes). S3 is derived view/orchestration only. 
* **S3 must not become correctness-gating** for writes (no “can’t append to ledger unless queue update succeeded”).

### B2) Evidence-plane truth leaks

* **S4 must not write “facts” into S2** beyond *refs + resolution status*. No copying audit payloads/events into case truth.
* **S1 must not fetch evidence directly from DLA/EB** bypassing S4 (or you lose consistent redaction, status handling, and “supersedes visible” discipline).

### B3) Labels/actions plane bypasses

* **S1 must not write labels directly** (bypassing S5) and must not treat “disposition set” as equivalent to “label truth written.” 
* **S3 must not emit labels or actions** (bypassing S5/S6). Workflow views don’t get to produce truth-changing side effects. 
* **S6 must not directly update case state as “executed.”** Only outcome evidence (via S4 attach) closes actions.

### B4) Signals plane becoming a dependency

* **S7 must not be required for correctness**. If S7 is off, CM still functions end-to-end; only freshness/automation degrades.
* **S7 must not push “truth updates” into S2** except recording publish receipts for optional signals (and even that is non-core).

### B5) “Distributed commit” inside CM

* **S2 must not synchronously call Label Store / AL / DLA / IG as part of committing the case timeline** (no cross-system 2PC). S2 commit must stand alone; external effects are work items handled asynchronously (S5/S6/S7).

---

## C) Non-paths (end-to-end flows inside CM that must never exist)

These are “if this flow exists, it’s a design bug.”

* **Evidence → automatic disposition → label write** (no auto-labeling from evidence resolution). Humans (or explicitly defined external adjudication writers) drive LabelAssertions via the proper lane. 
* **Label control event → auto-close case** (label-change nudges may refresh context; they must not silently change case truth). Case status changes must be explicit S1→S2 commands.
* **Manual action submit ACK → “action executed”** (submission is not execution; only immutable outcomes close the loop).
* **Case event publish success/failure → change case truth** (signals never gate or redefine the investigation timeline).
* **Oracle truth_products → “replace” investigation truth** (oracle lane is reference-only; must not overwrite what humans asserted/recorded).

---

## D) Non-loops (feedback cycles CM must not accidentally create)

* **CM emits case signals → automation consumes → automation writes back into CM as “truth”** without explicit actor/provenance. Any operational reaction must come through explicit governance/control surfaces and then appear to CM as evidence/context, not silent mutation.
* **CM + oracle lane creates a self-fulfilling loop** (“show oracle first → human rubber-stamps → labels become oracle”). Oracle access must be policy/profile controlled and clearly separated so evaluation remains meaningful.

---

## E) Environment-ladder non-joins (the “don’t fork the platform” rules)

* **No environment-specific semantics.** Local/dev/prod may change strictness (auth, retention, observability depth), but must not change meanings: append-only timelines, as-of labels, “no PASS → no read,” IG front door, AL-only executor.
* **No “dev-only” shortcuts that bypass IG/AL/Label Store**. You can stub integrations, but the *flow and receipts* must exist so production behavior is exercised early.

---

### The compact “red line” summary to carry forward

If you see **any** design where:

* a derived view becomes truth,
* a signal becomes correctness-critical,
* evidence becomes copied truth,
* labels/actions bypass their truth owners,
* or engine oracle leaks into hot path,

…that’s a boundary violation and we cut it.

---

## PAUSE FOR REFLECTION

Absolutely. Here’s the **designer’s anchor reflection** of what we’ve established — so when we go deeper into CM internals, we don’t accidentally re-invent, contradict, or drift from the network we’ve already pinned.

---

## 0) What we did in this brainstorm

We treated the platform as a **pinned outer network** and treated **CM/Workbench as a vertex** inside it. We first pinned CM’s **outer obligations** (joins/paths/loops), then we stepped **one layer inside** and decomposed CM into a small set of **opaque internal subnetworks**, then we mapped the **internal joins/paths/loops** between those subnetworks, and finally we explicitly named the **non-joins / forbidden paths** (the negative space).

Result: we now have a **drift-resistant CM network boundary** and a **first-layer internal network map** that is coherent with the broader platform.

---

## 1) The platform rails CM must obey (the “laws” we kept hitting)

These are the rails that shaped everything we designed:

* **Truth-ownership is exclusive** (no competing truth owners).

  * CM owns **cases + append-only investigation timelines**.
  * Label Store owns **labels** (append-only timelines, as-of).
  * Actions Layer owns **execution + immutable outcomes**.
  * DLA owns **flight recorder audit truth** (append-only).
  * IG owns **admit/quarantine/duplicate** with receipts.
  * EB owns **durable append + replay**, not payload meaning.
  * SR is the **join-surface authority** for runs/worlds (READY + run_facts_view).
* **One front door for bus writes:** producer → **IG → EB** (if CM emits anything onto a bus, it must pass through IG).
* **Canonical envelope at the bus boundary.**
* **No PASS → no read** for gated artifacts/surfaces.
* **By-ref everywhere across boundaries:** refs/locators/receipts, not payload copying.
* **Append-only + supersedes everywhere** (labels, audit, ledgers, registry).
* **Idempotency everywhere** (at-least-once delivery is assumed).
* **Time semantics are explicit:** don’t collapse domain time vs ingest time; don’t collapse effective vs observed time.
* **Environment ladder:** same graph + same semantics across local/dev/prod; only profile knobs change (security strictness, retention, obs depth, scale).

These laws are what made CM’s shape almost inevitable.

---

## 2) CM’s outer-network role (what CM *is* in the platform)

**CM is the human truth loop vertex:**

* It turns **evidence pointers** (DF/AL/DLA) into a **case story** (append-only timeline).
* It emits **ground-truth only** as **LabelAssertions into Label Store**.
* It triggers side effects only as **Manual ActionIntents** that **Actions Layer executes**.
* It reads for context **by reference** (DLA as the forensic source; optional EB context reads).
* It may optionally emit **control-plane case signals** via **IG → EB(control)**, but those are **signals**, never truth.

We explicitly split “what CM owns” vs “what it only references” so CM never becomes a shadow EB, shadow DLA, shadow label store, or shadow AL.

---

## 3) The complete outer join/path/loop inventory we established

We enumerated and ordered the production set:

### Core joins (must-have)

1. **CM → Label Store** (J13): LabelAssertions (append-only, effective vs observed).
2. **CM → Actions Layer**: Manual ActionIntents (CM requests; AL executes; outcomes immutable).
3. **DF/AL/DLA pointers → CM**: triggers + evidence refs (by-ref).
4. **CM → DLA**: by-ref reads of audit records (`dla/audit/...`).
5. **Label Store → CM**: as-of label reads for investigator context.

### Optional but valid joins

* CM → IG → EB(control): case events (signals only).
* CM ↔ EB: history reads for UI context (evidence only).
* DLA → EB(audit) → CM: audit pointer events (nudges).
* Label Store → EB(control) → CM: label changed events (nudges).
* SR join surface → engine truth_products → CM: oracle/reference lane (fenced).
* CM → observability pipeline (OTLP).

### Outer loops (the big feedback realities)

* **C1:** CM labels → learning → registry → DF decisions → CM evidence.
* **C2:** CM manual intent → AL outcome → DLA evidence → CM.
* **C3:** CM case signals → ops/automation/governance → evidence/context shifts → CM.
* **C4:** replay/backfill rebuilds derived state → CM evidence becomes newly joinable (case truth unchanged).
* **C5:** oracle truth_products (fenced) → human correction → Label Store → learning loop.
* **C6:** delayed truth arrives → CM workflow → Label Store timeline update → learning/decisions shift → CM.

We also side-stepped and pinned the SR ingestion fork: **pull model** (READY then IG pulls business_traffic), because it keeps invariants clean downstream — but that doesn’t alter CM’s boundary; it just stabilizes what upstream evidence looks like.

---

## 4) CM Level-1 internal subnetworks (opaque modules)

We decomposed CM into a small set of opaque internal boxes that map cleanly to the outer obligations:

* **S1 Workbench Gateway** (UI/API, auth, role checks, command intake).
* **S2 Case Truth Ledger** (the sole CM truth: append-only case timeline).
* **S3 Workflow & Triage Orchestrator** (queues/assignment/escalation views; derived).
* **S4 Evidence Plane** (evidence intake, ref registry, resolution; by-ref + redaction; optional oracle adapter).
* **S5 Adjudication & Labels Plane** (disposition → LabelAssertion; label reads as-of).
* **S6 Manual Intervention Plane** (manual action work items → ActionIntent submit; tracks submit state).
* **S7 Signals & Bus Adapters** (optional: publish case signals via IG; consume pointer/control nudges).

Cross-cutting (not its own box): access/audit discipline, telemetry/OTLP, profile/policy plumbing.

---

## 5) CM’s internal joins (I-J01 → I-J15) we pinned

We mapped the internal edges between those boxes:

### Truth spine

* **I-J01:** S1 → S2 command append (every durable change is a new timeline event or rejection).
* **I-J02:** S2 → S3 ledger stream (projections fed at-least-once; rebuildable).
* **I-J03:** S1 ↔ S3 triage/query views (eventually consistent; staleness visible).

### Evidence

* **I-J04:** S4 → S2 evidence attach (refs + status only; lane tagging; idempotent).
* **I-J05:** S1 ↔ S4 evidence resolve (by-ref; fail closed; supersedes visible).
* **I-J06:** S7 → S4 evidence-ready nudges (optional hints; durable changes still append via I-J04).

### Labels

* **I-J07:** S2 → S5 disposition → label work items (anchored to a specific ledger event).
* **I-J08:** S5 → S2 record emission outcomes (submitted/accepted/rejected/pending) as new timeline events.
* **I-J09:** S1 ↔ S5 as-of label context reads (current truth vs known-at-time are explicit).
* **I-J10:** S7 → S5 label-changed nudges (optional hints; truth still read from Label Store).

### Manual actions + optional signals

* **I-J11:** S2 → S6 manual action work items (anchored to ledger event; idempotent).
* **I-J12:** S6 → S2 record submit/precheck outcomes (submission ≠ execution).
* **I-J13:** S4 → S2 attach outcome evidence (immutable outcomes close the loop).
* **I-J14:** S2 → S7 publish case signal work items (optional).
* **I-J15:** S7 → S2 record IG receipt outcomes for signals (admit/duplicate/quarantine).

---

## 6) CM internal paths (I-P01 → I-P08)

We then expressed the production “storylines” through those joins:

* **I-P01:** upstream evidence → case created/attached → queue shows it.
* **I-P02:** investigator triage via derived views + case detail.
* **I-P03:** evidence drill-down (resolve by-ref; fail closed; supersedes visible).
* **I-P04:** disposition → label emission → ledger records ack/fail/pending.
* **I-P05:** manual action requested → intent submitted → outcome evidence later closes loop.
* **I-P06:** optional case signal publish via IG → receipt recorded.
* **I-P07:** evidence becomes available later → nudges resolve → status update appended.
* **I-P08:** label changes outside CM → nudges refresh context → UI sees updated truth (without rewriting CM truth).

---

## 7) CM internal loops (I-L01 → I-L06)

We pinned the cycles that define “production correctness”:

* **I-L01:** UI write → ledger append → projections update → UI reads.
* **I-L02:** evidence attach/resolve → ledger truth → UI renders (+ optional nudges).
* **I-L03:** disposition → label emission → ledger records ack → UI reflects.
* **I-L04:** manual request → submission → outcome evidence attach → UI reflects.
* **I-L05:** optional signal publish → receipt recorded (non-critical).
* **I-L06:** rebuild/reconcile: anything derived must be rebuildable; case history must never be rewritten.

---

## 8) The negative space we made explicit (non-joins / forbidden paths)

We declared “red lines” to prevent drift:

* No bypassing **IG** for bus emission.
* No bypassing **AL** for side effects.
* No bypassing **Label Store** for label truth.
* No writing/patching DLA audit truth.
* No scanning engine outputs; no using truth_products as traffic.
* Inside CM: no writes to S3; no S3 gating S2 commits; no direct evidence fetch from UI bypassing S4; no 2PC coupling S2 commit to external systems.
* No “auto-labeling from evidence resolution.”
* No treating submit ACK as execution outcome.
* No making optional signals correctness-critical.
* No environment-specific semantic forks.

This negative space is a big part of why the network remains coherent.

---

## 9) Environment ladder perspective for CM (what varies vs what cannot)

We pinned that **semantics don’t change** across envs — only profiles do:

* Vary by env: retention/archive depth, strictness of auth/approvals, observability depth, scale limits, optional joins toggles (signals/oracle lane).
* Must never vary: append-only case timelines, label timeline semantics, AL-only execution, IG-only bus ingress, no-PASS-no-read, by-ref evidence posture, idempotency.

We also separated deployment knobs into two buckets:

* **Wiring** (endpoints/resources/timeouts)
* **Policy** (role permissions, allowed label families, allowed manual actions, redaction rules, oracle access)

---

## 10) What’s still intentionally not defined (safe “open” items)

We deliberately *did not* deep-dive yet into:

* the exact **case event taxonomy** (event_type set inside S2),
* the exact **disposition → label mapping** catalog (beyond “mapping_id must be named”),
* the exact **case clustering key** and “create vs attach” algorithm,
* detailed auth matrices and approval workflows,
* storage/indexing strategies and performance mechanics,
* UI workflows/screens.

Those are the next layers — but the network boundary we’ve defined will constrain them.

---

## Drift guardrail to carry into the next stage

If we keep only one sentence in mind as we go deeper:

**CM is an append-only investigation ledger with derived workflow views; it never copies evidence into truth, never executes side effects, never owns labels, and any optional bus signals are non-critical hints that must still obey IG + envelope rules.**

If you’re aligned with this reflection, the next step is clean: we pick one internal subnetwork (usually **S2** first), and pin its **external IO + invariants** (still minimal, still drift-resistant) before opening its internal mechanics.

---

Yep — this is the right moment to **pin the deployment + environment-ladder stance** for the *internal CM subnetworks* (S1–S7) **before** we open any of them up.

Below is what I want **Codex (implementer)** to treat as **authoritative deployment design** for CM.

---

## 1) Deployment invariants for CM across the environment ladder

### Invariant A — Same semantics, different profiles

Local / dev / prod must run the **same CM graph** and obey the **same CM laws** (append-only case timeline truth; by-ref evidence; labels only become truth in Label Store; actions only execute in AL; IG front door for any bus emissions).
Environments may only differ by **profile knobs**: security strictness, retention, observability depth, scale, and optional feature toggles.

### Invariant B — CM write-path must not depend on other services

**The “commit truth” path (S1 → S2)** must be available even if Label Store / AL / IG / EB / object store are degraded.
External effects are **asynchronous work** that can lag, retry, or fail, without blocking case timeline truth.

> Designer pin: **No cross-system distributed commit**. No 2PC. No “write case only if label write succeeds.”

### Invariant C — Optional signal/refresh edges must never be correctness-critical

S7 (nudges, control-plane case events, audit pointer consumption, label event consumption) can improve freshness/automation, but CM must remain correct with S7 disabled.

---

## 2) The production deployment shape for CM’s internal subnetworks

CM is an always-on human app, but internally it wants **two runtime roles**: a **request-serving role** and one or more **worker roles**. Whether those roles are separate processes or separate deployments is an operational choice — the **interfaces and semantics must support both**.

### Role 1: `cm-api` (request-serving)

Houses:

* **S1 Workbench Gateway** (auth/session, request validation, idempotency keys, command intake)
* **S2 Case Truth Ledger** (writes + authoritative reads)
* Read-only query surfaces (can proxy to S3/S4/S5 as needed)

Properties:

* Stateless except DB connections.
* Horizontally scalable.
* Must remain up even when workers are down.

### Role 2: `cm-workers` (async processing)

Houses (can be separate worker pools, but same semantics):

* **S3 Projector** (ledger → triage views)
* **S4 Evidence resolver/refresher** (resolve by-ref, handle nudges, refresh statuses)
* **S5 Label emission worker** (disposition → LabelAssertion → ACK back to ledger)
* **S6 Manual action intent worker** (manual request → ActionIntent submit → submit-state back to ledger)
* **S7 Bus adapters** (optional publish case signals via IG; optional consume nudges)

Properties:

* Can lag; can restart; must be idempotent.
* Must never be required for the API to accept new case timeline events.

> Designer pin: you can deploy S3/S4/S5/S6/S7 as **one worker process with multiple queues**, or as separate deployments for scale — but the boundaries must not assume either.

---

## 3) The reliability pattern inside CM: “ledger + outbox work items”

To make the above deployable and ladder-proof:

### Pin: S2 owns a persistent “work item outbox”

Whenever a case timeline event implies external work, S2 records a **work item** (same transaction as the timeline append). Workers consume these work items **at-least-once** and report back outcomes as new timeline events.

* S2 timeline append = truth
* Outbox work items = “things to try”
* Worker results = new timeline events (“label accepted”, “intent submitted”, “signal quarantined”, “evidence now resolved”, etc.)

This gives you:

* no distributed commit,
* deterministic retry,
* simple drain/replay,
* and clean scaling.

---

## 4) Environment profile knobs CM must support (the “deployment knobs”)

Keep these as **profile-driven config**, not code forks.

### A) Feature toggles (optional edges)

* `enable_case_signal_publish` (S2 → S7 → IG → EB control)
* `enable_audit_pointer_consume` (S7 consumes audit pointers, nudges S4)
* `enable_label_event_consume` (S7 consumes label events, nudges S5)
* `enable_eb_history_reads` (S4 may enrich context from EB; evidence only)
* `enable_oracle_lane` (S4 may show truth_products via SR join surface; fenced)

**Pin:** toggles may change freshness/automation, **never** truth semantics.

### B) Security strictness (policy knobs)

* Auth mode (local relaxed / dev realistic / prod strict)
* RBAC: who can create/escalate/close cases; who can emit labels; who can request manual actions
* Manual actions: allowlist of action types, scope constraints, approval requirements (prod may require dual approval)
* Evidence redaction policy: what roles can view raw pointers vs rendered summaries; who can see quarantined evidence
* Oracle lane access policy (often restricted/off in prod)

### C) Reliability/backpressure knobs

* Worker concurrency per subnetwork (S3/S4/S5/S6/S7)
* Retry strategy (backoff caps, jitter)
* Circuit breakers per external dependency (Label Store, AL, IG, object store, EB)
* Max outstanding work items per case (avoid a “storm”)

### D) Retention and “history availability” knobs

* EB retention in local will be short; CM must gracefully fall back to DLA refs for older context.
* Object store retention and access controls.
* Case timeline retention/archival policy (append-only implies growth; prod needs a plan — even if it’s “indefinite + partitioning/archival jobs later”).

### E) Observability depth knobs

* Trace sampling rate
* Verbosity of structured logs (never dump payloads by default)
* Alerts/SLO thresholds (prod only)
* Exporters endpoints (OTLP collector)

---

## 5) Production operational readiness expectations for CM

These aren’t implementation details — they’re *deployment truths* Codex must make possible.

### A) Health and lifecycle

* `liveness`: process is alive
* `readiness`: can reach its own DB + can accept requests (workers can be down and still “ready” for cm-api)
* Graceful shutdown/drain: stop accepting new work, finish in-flight, persist checkpoints

### B) Rebuild/reconcile operations must exist

Because S3/S4/S5 can be derived, you need operator-triggerable operations that are safe in all envs:

* Rebuild S3 projections from S2 timeline
* Re-resolve evidence statuses for a case range
* Re-drive pending label work items / action submit work items safely (idempotent)
* Re-drive publish receipts reconciliation (optional)

### C) Clear “pending state” UX is a deployment requirement

Because external dependencies can be down:

* label writes can be pending
* action intents can be pending submission or awaiting outcome
* evidence can be unresolved/unavailable/superseded
  CM must visibly represent this and never pretend completion.

---

## 6) Deployment anti-patterns we explicitly ban

* **Making S3 projection success a prerequisite for S2 writes**
* **S2 calling Label Store/AL/IG synchronously in the commit path**
* **Depending on S7 nudges for correctness**
* **Embedding evidence payloads in case truth to “avoid reads”**
* **Environment-specific behavior forks** (“in prod we do X, in dev we do Y”) instead of profile knobs

---

## The one-liner to carry into node illumination

Design every subnetwork so it can run as either **(a) a module inside one service** or **(b) an independently scalable worker**, while keeping the **S2 ledger commit path independent** and keeping all external effects **outbox-driven and idempotent**.

---

Yep — with the network already pinned, node illumination should only **reveal internal machinery**, not invent new dependencies.

## CM internal nodes (Level-1, opaque modules)

* **S1 — Workbench Gateway**: UI/API entry, auth/session, command intake, idempotency stamping
* **S2 — Case Truth Ledger**: authoritative case objects + append-only case timeline (+ internal outbox/work items)
* **S3 — Workflow & Triage Orchestrator**: queues/search/status views (derived from S2)
* **S4 — Evidence Plane**: evidence ref intake/registry + by-ref resolution (DLA primary; optional EB context; optional oracle lane)
* **S5 — Adjudication & Labels Plane**: disposition→LabelAssertion emission + as-of label reads (truth lives in Label Store)
* **S6 — Manual Intervention Plane**: manual ActionIntent submission + submit-state tracking; outcomes return as evidence
* **S7 — Signals & Bus Adapters (optional)**: case signal publish via IG; consume audit/label nudges (hints only)

## Recommended illumination order (min-drift)

1. **S2 Case Truth Ledger**
   Foundation: event taxonomy, invariants, cursors, outbox/work-item model.
2. **S1 Workbench Gateway**
   Defines the *only* write entry: command shapes, actor rules, idempotency recipes, rejection semantics.
3. **S3 Workflow & Triage Orchestrator**
   Derived read models: queue/query semantics, staleness markers, rebuild rules.
4. **S4 Evidence Plane**
   Evidence ref types + attach/resolve behavior, redaction, supersedes visibility, fail-closed semantics.
5. **S5 Adjudication & Labels Plane**
   Disposition mapping + LabelAssertion lifecycle (pending/accepted/rejected), as-of read defaults.
6. **S6 Manual Intervention Plane**
   ActionIntent construction, prechecks, submission retries, outcome linkage back into cases.
7. **S7 Signals & Bus Adapters (optional, last)**
   Publish receipts + nudges as *non-critical* freshness/automation, never correctness.

---

Yep. We’ll **open S2 (Case Truth Ledger)** and expose the **machinery** that makes the already-pinned joins/paths/loops possible — without changing the network.

I’m going to treat S2 as **a ledger + a small amount of internal indexing + an outbox**, all *inside CM*, and I’ll be explicit about what is “truth” vs “supporting machinery.”

---

# S2 — Case Truth Ledger

## 1) S2’s purpose and hard boundaries

### What S2 *is* (authoritative)

* **System-of-record for CM truth:**
  **Case objects + append-only case timelines** (“investigation ledger”).
* Everything meaningful that happens in CM becomes a **new case event** or a **rejection**.

### What S2 is *not*

* Not a label store (labels become truth only in Label Store).
* Not an action executor (actions execute only via Actions Layer).
* Not an audit store (DLA is flight recorder).
* Not a bus producer (if CM emits, it’s via S7→IG).

### Critical deployment pin

* **S2 commit path is standalone.**
  It must not synchronously call Label Store / AL / IG / DLA / EB as part of committing case truth. External effects happen via **outbox work items**.

---

## 2) S2’s internal sub-machines (still all “inside S2”)

Think of S2 as these internal parts:

1. **Event Log Store**
   Append and read the case timeline.
2. **Case Registry**
   A small “case header” record for stable facts (case_id, pins, created_at, kind).
3. **Idempotency Guard**
   Dedup retries and at-least-once delivery.
4. **Precondition / Gate Evaluator**
   Optional “compare-and-set” semantics for commands that must not silently conflict.
5. **Cursor & Stream Emitter**
   Deterministic cursors for projection consumers (S3) and read staleness.
6. **Outbox / Work Item Store**
   Durable “things to do” for S3/S5/S6/S7 that don’t block S2 commits.
7. **Reconcile / Repair Hooks**
   Rebuild derived indices and re-drive stuck work items without rewriting history.

---

## 3) The core objects S2 persists

### 3.1 Case record (small, stable, authoritative “envelope”)

This is **not** a mutable case state store; it’s stable metadata + indexing support.

Minimum conceptual fields:

* `case_id`
* `case_kind` (e.g., `investigation_case`, future: `meta_case`)
* `context_pins` (run/world scoping defaults)
* `created_at_utc`
* `created_by_actor`
* `primary_subject_keys[]` (join anchors: entity_ref/event_id/decision_id etc., as pointers)
* `is_open` (current-open flag **maintained** for fast queries; *derivable from timeline*)

> Designer stance: it’s OK to store `is_open` as **supporting machinery** because it’s rebuildable from the timeline and exists only to make “create vs attach” and queue discovery viable in production.

### 3.2 CaseEvent (the actual truth)

Each appended event is immutable.

Minimum conceptual fields:

* `case_event_id` (stable)
* `case_id`
* `case_seq` (monotonic per case)
* `event_type`
* `observed_at_utc`
* `actor` (principal + role context)
* `links[]` (decision_id/event_id/action_ids/entity_refs; plus pins if needed)
* `payload` (small; refs/pointers; never bulk evidence payload)
* optional `prev_event_hash` + `event_hash` (tamper-evident chain; optional but powerful)

### 3.3 IdempotencyReceipt

Maps retries → the same result.

Conceptually:

* `scope` (per-case or create-scope)
* `idempotency_key`
* `result_kind` (accepted/rejected)
* `case_id`
* `case_event_id` (if accepted)
* `created_at_utc`

### 3.4 OutboxWorkItem

Durable queue items derived from ledger events.

Conceptually:

* `work_item_id`
* `work_item_type` (PROJECT_TO_S3, EMIT_LABEL, SUBMIT_ACTION_INTENT, PUBLISH_CASE_SIGNAL, OPTIONAL_EVIDENCE_PREFETCH)
* `case_id`
* `source_case_event_id` (anchor!)
* `dedupe_key` (usually derived from `source_case_event_id` + type)
* `payload` (small)
* `status` (PENDING / IN_PROGRESS / DONE / RETRY / DEAD)
* `attempt_count`, `next_attempt_at_utc`
* `last_error_code` (if any)

---

## 4) The S2 append pipeline (I-J01 in machinery form)

When S2 receives a `CaseCommand` from S1, it performs:

### Step A — Validate and normalize

* Validate command shape.
* Require `actor`.
* Require `idempotency_key`.
* Normalize “links” and “pins” fields.

### Step B — Idempotency check (fast exit)

* Look up `(scope, idempotency_key)` in IdempotencyReceipt.
* If found:

  * return the same accepted/rejected result deterministically (no re-append).

### Step C — Precondition evaluation (optional but important)

Some commands must not silently conflict (e.g., “claim unassigned”, “close open case”).

S2 supports optional preconditions like:

* `expected_case_seq` (optimistic concurrency)
* `require_open = true`
* `require_current_assignee = null` (claim)
* `require_disposition_absent` (first disposition)
* etc.

If preconditions fail: reject with a **conflict reason** (still deterministic, still idempotent).

### Step D — Append the event atomically

Inside one DB transaction:

* Allocate next `case_seq`.
* Insert new CaseEvent.
* Update supporting indexes (e.g., `is_open`, subject-key index, open-case index).
* Write IdempotencyReceipt.
* Insert any OutboxWorkItems implied by the event.

### Step E — Return AppendResult

Return:

* `case_event_id`
* `case_seq` (and/or `ledger_cursor`)
* plus a canonical “command outcome”.

**Key property:** S2 always returns a deterministic answer under retries and concurrency.

---

## 5) Cursors and streaming (I-J02/I-J03 support)

S2 must expose **two cursor notions**:

### Per-case cursor

* `case_seq` is the per-case monotonic order.
* Used for: read-your-writes consistency and “what changed in this case?”

### Global ledger cursor (for S3 projection)

* A monotonic `ledger_cursor` across all case events (could be `(created_at, tiebreak_id)` or a sequence).
* Used for: “project all events in order into S3”.

**Pin:** cursor semantics are **exclusive-next** (same mental model as offsets):
S3 can checkpoint “processed up to cursor X” and replay safely.

---

## 6) The outbox model (how S2 drives S3/S5/S6/S7 without coupling)

This is the deployment-critical machinery.

### Work item generation rules (examples)

* `DISPOSITION_SET` event → create `EMIT_LABEL` work item for S5.
* `ACTION_REQUESTED` event → create `SUBMIT_ACTION_INTENT` work item for S6.
* “publishable case event” → create `PUBLISH_CASE_SIGNAL` work item for S7 (if enabled).
* Any appended event → S3 can project via event stream; optionally you also emit `PROJECT_TO_S3` work items if you prefer explicit queues.

### Work item consumption rules (at-least-once)

* Workers claim items, execute, and then report back by appending **result events** into S2 (I-J08, I-J12, I-J15).
* Duplicate execution is safe because:

  * work items have `dedupe_key`
  * and the external boundary writes are idempotent (label idempotency key; action idempotency key; publish event_id derived from case_event_id)

**Pin:** outbox prevents distributed commit and makes CM survive partial outages.

---

## 7) Minimal event taxonomy S2 must support (the “spine vocabulary”)

Not a full spec list, but the *minimum families* implied by our joins/paths/loops:

### Case lifecycle

* `CASE_CREATED`
* `CASE_CLOSED`
* `CASE_REOPENED` (optional but useful)

### Workflow actions (truth of what humans did)

* `ASSIGNED`, `UNASSIGNED`
* `PRIORITY_SET`, `ESCALATED`
* `NOTE_ADDED` / `COMMENT_ADDED`
* `TAG_ADDED` / `TAG_REMOVED` (optional)

### Evidence (refs + status only)

* `EVIDENCE_ATTACHED`
* `EVIDENCE_STATUS_UPDATED` (PENDING/RESOLVED/UNAVAILABLE/QUARANTINED/SUPERSEDED)

### Disposition + label emission lifecycle

* `DISPOSITION_SET`
* `LABEL_SUBMITTED`
* `LABEL_ACCEPTED`
* `LABEL_REJECTED`
* `LABEL_RETRY_SCHEDULED` (or “PENDING”)

### Manual actions lifecycle

* `ACTION_REQUESTED`
* `ACTION_REQUEST_PRECHECK_REJECTED`
* `ACTION_INTENT_SUBMITTED`
* `ACTION_INTENT_SUBMIT_FAILED_RETRYABLE`
* `ACTION_OUTCOME_ATTACHED` (EXECUTED/DENIED/FAILED)

### Optional signals lifecycle (if enabled)

* `CASE_SIGNAL_ADMITTED`
* `CASE_SIGNAL_DUPLICATE`
* `CASE_SIGNAL_QUARANTINED`

---

## 8) Reconcile & rebuild hooks (I-L06 made real)

S2 must make it possible to:

* **Rebuild S3 projections** from the ledger stream.
* **Re-drive outbox work items** (stuck/pending) safely.
* **Reconcile “pending” states** by checking authoritative truth owners:

  * “Is the label actually present in Label Store for this idempotency key?”
  * “Is there an action outcome in DLA for this action idempotency key?”
* If reconciliation discovers something investigators must see, it **appends a new timeline event** (“label discovered accepted”, etc.). It never rewrites history.

---

## 9) Deployment + environment ladder stance specific to S2

### Across all environments

* Same semantics, same event taxonomy, same idempotency rules, same outbox behavior.

### What changes by profile

* DB scale and retention strategy (local small, prod partitioning/archival)
* auth strictness at S1 (but S2 still requires actor fields)
* worker concurrency and retry knobs
* whether optional signal work items are enabled

### Operational necessities

* Backups + migration discipline (because S2 is the case truth)
* Health/readiness that depends on **S2’s own DB** only (not on Label Store/AL/IG)

---

## 10) The “don’t accidentally break the network” list for S2

If any of these show up during implementation, it’s a design violation:

* S2 commit waits on Label Store/AL/IG/DLA.
* S2 stores bulk evidence payload as case truth.
* S2 treats “label submitted” as “label truth exists.”
* S2 treats “intent submitted” as “action executed.”
* S2 requires S7 signals for correctness.

---

Got it. We’ll open **S1 — Workbench Gateway** and expose the machinery that makes the already-pinned CM network work in production, **without changing any joins/paths/loops**.

# S1 — Workbench Gateway

## 1) What S1 is responsible for

S1 is the **only human/system entry surface** into CM. It is *not* a truth store; it is the **policy + shaping + routing layer** that ensures every interaction with CM becomes either:

* a **well-formed command** into S2 (append-only truth), or
* a **well-formed query** against S2/S3/S4/S5 (reads with explicit consistency semantics), or
* a **well-formed “resolve” request** (evidence/label context), with redaction + permissions applied.

S1 is the layer that makes the platform laws *practical*:

* actor always recorded,
* idempotency always present,
* no writes to projections,
* evidence stays by-ref,
* labels/actions go through their rightful authorities.

---

## 2) S1’s internal sub-machines (inside the Gateway)

Think of S1 as these submodules (all inside the “cm-api” deployment unit):

### G1) Identity & Session Manager

* Authn: validates user/session tokens (local/dev/prod profiles differ in strictness).
* Produces a normalized **ActorPrincipal** object:

  * `principal_id`, `display_name`, `roles`, `scopes`, `auth_strength`, `policy_rev`.

### G2) Authorization & Policy Evaluator

* Central RBAC/ABAC checks for:

  * case reads/writes,
  * label emission permissions,
  * manual action request permissions,
  * evidence visibility (including quarantined/sensitive).
* Enforces policy by **decision + reason codes**, never implicit.

### G3) Command Builder (Write Shaper)

Turns UI intents into **canonical CaseCommands**:

* validates payload shape
* attaches actor + timestamps
* generates/validates idempotency keys
* attaches optional **preconditions** (optimistic checks) for operations like “claim case” or “close case”.

### G4) Idempotency Front-End

* Accepts a client-provided `request_id` (preferred) or generates one.
* Normalizes to a **stable idempotency key** per operation.
* Ensures the same UI action (retry, double-click, refresh) doesn’t fork truth.

### G5) Query Router (Read Shaper)

Routes reads to the right internal authority:

* **S2** for case-by-id truth and timelines (read-your-writes)
* **S3** for queues/search/filters (eventually consistent)
* **S5** for label context reads (as-of semantics)
* **S4** for evidence resolution (redaction + fail-closed)

### G6) UI Composition Layer

Builds “workbench-ready” responses by **composing**:

* case timeline from S2
* queue summaries from S3
* evidence render panels from S4
* label context widgets from S5
  …but without copying payloads into CM truth.

### G7) Observability + Audit Emission

* OTLP traces/metrics/logs with correlation keys (case_id, case_event_id, decision_id, etc.)
* Security audit logs (“who accessed what evidence”, “who requested what action”) separate from case truth timeline unless you explicitly choose otherwise.

### G8) Rate Limiter / Abuse Guard

* Prevents UI or automation from flooding writes/resolve calls.
* Critical for evidence resolution and manual actions (safety).

---

## 3) The S1 interface surface (what it exposes)

You can think of S1’s external API as 4 groups:

### A) Case write commands (all become S2 appends)

* Create/open case
* Assign/claim/unassign
* Change priority/escalate
* Add notes/tags
* Attach evidence refs (investigator-driven)
* Set disposition
* Request manual action
* Close/reopen case

**Invariant:** every one of these becomes a **CaseCommand → S2** with actor + idempotency, and returns an **AppendResult** (or rejection).

### B) Case reads

* Case-by-id (timeline + metadata)
* Timeline pagination / slices
* “Case summary” for UI panels

**Invariant:** truth detail comes from **S2** (not S3).

### C) Workflow reads (triage)

* My queue / team queue / unassigned / escalated
* Search by join keys (event_id, decision_id, entity_ref)
* Filters by status/assignee/time window

**Invariant:** these go to **S3** and are allowed to be **eventually consistent**, but must return an **as_of cursor**.

### D) Context & resolution

* Resolve evidence item (by-ref → rendered view) → **S4**
* Read label context (current truth or known-at-time) → **S5**
* Optional live updates (websocket/SSE) driven by **changes in S2 cursor** (not by “S3 says so”).

---

## 4) S1 write-path machinery (how S1 safely produces S2 truth)

When a user does anything that changes a case:

### Step 1 — Authenticate → build ActorPrincipal

If actor missing/invalid → reject.

### Step 2 — Authorize action

Evaluate: “Is this principal allowed to do this command on this case (or in this scope)?”

* On deny: return `403` + reason code.
* **Never** “best effort” partial writes.

### Step 3 — Build canonical CaseCommand

S1 constructs a normalized command envelope:

* `command_type`
* `case_id` (or create payload)
* `actor`
* `observed_at_utc`
* `idempotency_key`
* `payload`
* optional `preconditions`

### Step 4 — Submit to S2

S2 returns:

* ACCEPTED: `case_event_id`, `case_seq`, maybe `ledger_cursor`
* REJECTED: reason (validation / conflict / forbidden / etc.)

### Step 5 — Read-your-writes confirmation

For UI correctness:

* S1 can immediately re-read the case timeline from S2 and return it, ensuring the user sees the committed truth even if S3 lags.

**Pinned outcome:** S1 never writes to S3. S3 updates only by consuming S2.

---

## 5) S1 read-path machinery (how S1 keeps views truthful)

S1 enforces a clear consistency model:

### Case detail = truth-consistent

* Source: **S2**
* Always shows the committed timeline events
* Can include “derived badges” (e.g., “pending label”) but those are derived from timeline + known pending work, not separate truth.

### Queues/search = eventually consistent

* Source: **S3**
* Response includes `as_of_cursor` so the UI can show staleness (“as of cursor X”).
* If S3 is down: S1 can still allow direct case-by-id reads; queue views degrade.

### Evidence rendering = fail-closed, privilege-aware

* Source: **S4**
* S1 passes actor role context → S4 returns redacted view or explicit status:

  * UNAVAILABLE / QUARANTINED / FORBIDDEN / SUPERSEDED

### Label context = timeline truth with explicit as-of

* Source: **S5** (Label Store reads)
* S1 requires mode clarity:

  * `CURRENT_TRUTH` vs `KNOWN_AT(as_of_observed_time)`
* No “latest by accident.”

---

## 6) Idempotency: S1’s “no double-click bugs” and retry safety

S1 is where idempotency becomes real for humans:

### What S1 must guarantee

* Every write command has an idempotency key.
* Retries yield the same semantic result.

### How S1 typically sources idempotency keys

* Prefer client-provided `request_id` header (stable per user action).
* If not provided, S1 generates one **but must return it** so the UI can retry safely.
* For “toggle-ish” operations (assign/close), S1 includes a precondition (e.g., expected assignee) to avoid accidental conflicting updates.

---

## 7) S1’s security posture (profile-driven, semantics constant)

Across the environment ladder:

* Local: relaxed auth may be okay, but S1 still produces actor principals (even if “dev-user”).
* Dev: realistic roles/scopes; denies should resemble prod.
* Prod: strict auth + approvals for certain manual actions.

S1’s crucial job: ensure every downstream truth-changing act has **actor + reason + policy_rev** attached or available.

---

## 8) Failure behavior (how S1 behaves when dependencies wobble)

S1 must make CM usable under partial outages:

* If **S3 is down** → queue views degrade, but case-by-id + writes still work.
* If **S4 cannot resolve evidence** → show explicit status; don’t fabricate.
* If **Label Store is down** → disposition can be recorded in S2; label emission becomes pending (S5 workers retry). UI must reflect “pending label write”.
* If **AL/IG path is down** → manual action request can be recorded; submission pending; do not pretend execution.

This preserves the “S2 commit path is independent” deployment law.

---

## 9) S1 anti-patterns (hard bans inside the gateway)

If any of these appear during implementation, it violates the network we pinned:

* Writing directly to S3 (“update queue state”)
* Calling Label Store / AL / IG synchronously as part of committing the case timeline
* Treating label submit as label truth
* Treating intent submit as action execution
* Fetching evidence directly from DLA/EB in the UI layer (bypassing S4 redaction/fail-closed discipline)
* Using optional nudges/signals as correctness dependencies

---

Got it — we’re illuminating **S3: Workflow & Triage Orchestrator**.

S3 is the “**derived workflow brain**” of CM: it turns the S2 ledger’s append-only timeline into **queues, search, summaries, and triage signals** that make the Workbench usable at production scale — **without ever becoming a second truth store**.

Below is the **machinery inside S3** that makes I-J02/I-J03, I-P02, and the truth spine loops actually work.

---

# S3 — Workflow & Triage Orchestrator

## 1) What S3 is allowed to be

### S3 is

* A **projection subsystem**: consumes S2’s case events and derives:

  * queue membership,
  * case summaries,
  * search indexes,
  * “triage state” (e.g., new/escalated/stale/pending-label/pending-action),
  * staleness markers.

### S3 is not

* Not an authority for case truth.
* Not a write surface (no “set assignee/status” via S3).
* Not a gating dependency for S2 commits.
* Not a place to “fix up” missing evidence by reaching out to DLA/EB/Label Store (those are S4/S5 concerns).

**Designer pin:** S3 must be rebuildable from S2 alone (plus config/policy artifacts).

---

## 2) S3’s internal sub-machines (opaque-to-code, explicit-to-design)

### T1) Projection Ingestor (ledger consumer)

* Consumes S2’s event stream using a **monotonic `ledger_cursor`** (exclusive-next semantics).
* Delivery is **at-least-once**, so it must be **idempotent**.

**Idempotency strategy (pin):**

* Dedup by `(case_id, case_event_id)` or `(case_id, case_seq)`.
* Maintain a per-case “last applied seq” watermark so repeats don’t double-apply.

### T2) State Deriver (the “compiler”)

A deterministic set of mapping rules that turns a stream of case events into a **CaseSummary** and **QueueMembership**.

* It never calls external services to “decide truth.”
* It may consult local static policy/config (queue definitions, SLA definitions), versioned as `policy_rev`.

### T3) Projection Store (query-optimized data)

Stores the derived artifacts that make the Workbench fast:

* `case_summary` table (one row per case)
* `queue_index` (queue → ordered list of case_ids)
* `join_key_index` (event_id/decision_id/entity_ref → case_ids)
* `time_index` (created_at/last_activity → case_ids)
* optional `tag_index` / `assignee_index`

**Designer pin:** all of these are **rebuildable** and therefore not truth.

### T4) Query Engine (S1 ↔ S3 interface)

Implements the read-side contract:

* queue reads (my queue, unassigned, escalated)
* search by join keys
* filtering/sorting/pagination
* returns **`as_of_ledger_cursor`** in every response (staleness visible)

### T5) Consistency & Staleness Reporter

Keeps S3 honest:

* “as-of cursor” on every response
* lag metrics (cursor behind S2)
* per-queue freshness metrics

This directly supports your pinned “eventually consistent queues, truth-consistent case detail” stance.

### T6) Rebuild / Reconcile Controller (ops machinery)

Operator/automation accessible routines:

* full rebuild from S2 cursor 0
* partial rebuild by case_id range or time window
* replay from a specific cursor
* verify/repair indexes

**Pin:** rebuild never rewrites S2; it only recomputes derived state.

---

## 3) The core derived artifacts S3 produces

### 3.1 CaseSummary (what the UI needs for lists)

A CaseSummary is a compact, derived “header” that’s safe to show in lists and queues.

Minimum fields (conceptual):

* `case_id`
* `case_kind`
* `is_open` (derived)
* `status` (derived “triage status”)
* `assignee` / `team` (derived)
* `priority`, `escalation_level` (derived)
* `created_at`, `last_activity_at`
* `primary_subject_keys[]` (for display + joins)
* “pending flags” derived from timeline:

  * `pending_label_write`
  * `pending_action_outcome`
  * `unresolved_evidence`
* `as_of_ledger_cursor` (or stored separately)

### 3.2 QueueMembership

Derived membership rules yield queue sets such as:

* `unassigned_open`
* `my_open_cases`
* `team_open_cases`
* `escalated`
* `stale`
* `pending_label`
* `pending_action`
* `needs_review` (optional)

**Designer pin:** queue definitions are policy-configured and versioned (`policy_rev`); S3 includes policy_rev in responses so behavior is explainable across environments.

### 3.3 JoinKey Index

This is key to the “network” feel of the platform.
S3 must support queries like:

* “show the case for `event_id = X`”
* “show cases linked to `decision_id = Y`”
* “show cases linked to `entity_ref = Z`”

It does this by indexing the `links[]` that S2 already records (so we don’t invent new joins).

---

## 4) How S3 derives state from events (the deterministic mapping)

This is the “compiler rules” concept. A few examples (not exhaustive, but shows the machinery):

* `CASE_CREATED` → `is_open=true`, `status=NEW`, `created_at=...`, `last_activity=created_at`
* `ASSIGNED(actor→assignee)` → `assignee=...`, `status=IN_PROGRESS`, `last_activity=...`
* `ESCALATED(level++)` → `escalation_level=...`, add to `escalated` queue
* `DISPOSITION_SET` → `status=DISPOSITION_SET` + `pending_label_write=true` (until ack)
* `LABEL_ACCEPTED` → `pending_label_write=false`, `status=RESOLVED`
* `ACTION_REQUESTED` → `pending_action_outcome=true`, add to `pending_action` queue
* `ACTION_OUTCOME_ATTACHED(EXECUTED|DENIED|FAILED)` → `pending_action_outcome=false`, update status badge
* `EVIDENCE_ATTACHED` → `unresolved_evidence=true` (until resolved)
* `EVIDENCE_STATUS_UPDATED(RESOLVED)` → `unresolved_evidence=false`
* `CASE_CLOSED` → `is_open=false`, remove from open queues

**Designer pin:** S3 must never derive “final label truth” or “action executed” from *submission* events — only from ledger events that reflect authoritative closure (LABEL_ACCEPTED, ACTION_OUTCOME_ATTACHED). That matches the loops we pinned.

---

## 5) Query semantics (I-J03 made real)

### Consistency model (pinned)

* **Queues/search are eventually consistent**.
* **Case detail is truth-consistent** (S1 falls back to S2 for detail reads).

So S3 must:

* return `as_of_ledger_cursor` always,
* support pagination stable under churn (cursor + ordering keys),
* and be safe when behind (never returns “truth claims,” only derived views).

### Ordering in queues (designer choice, production-friendly)

S3 should support order-by options:

* `last_activity_at desc`
* `priority desc, last_activity desc`
* `escalation_level desc, last_activity desc`
* optional `sla_due_at asc` (see below)

**Pin:** ordering is deterministic given the same derived state and cursor.

---

## 6) SLA / staleness machinery (optional but very production-real)

S3 is the right place to compute “stale” and “SLA due” flags because:

* it’s derived,
* it’s query-heavy,
* it shouldn’t pollute S2 truth.

Mechanism:

* Policy defines SLA durations per case_kind/priority.
* S3 computes:

  * `sla_due_at = created_at + SLA(policy_rev, kind, priority)`
  * `is_stale = now - last_activity > threshold(policy_rev)`

These become queues:

* `stale_cases`
* `sla_breaching_soon`

**Environment ladder note:** local can run with trivial thresholds; prod uses stricter/real ones — semantics remain identical, only policy values differ.

---

## 7) Security posture for S3 (designer call)

To avoid coupling and complexity inside S3:

**Pin (v0): S1 enforces authorization; S3 enforces coarse filtering only.**

* S3 supports filters like “assignee = me” or “team = X”
* S1 decides whether the actor is allowed to query that team/queue and whether to show certain fields.

Later, if needed, you can add row-level security inside S3 — but it’s not required to preserve correctness.

---

## 8) Failure and rebuild behavior (production reality)

### If S3 is down

* S1 can still:

  * accept writes (S1→S2)
  * read case-by-id + timeline (S2)
* Only:

  * queues/search degrade

This is critical: **truth acceptance must not depend on S3**.

### Rebuild/reconcile

S3 must support:

* full rebuild from S2 cursor 0
* incremental catch-up from last checkpoint
* partial rebuild by case_id or time range

Rebuild must never mutate S2 history; it only recomputes derived views.

---

## 9) Deployment mapping for S3 (how Codex should think about it)

S3 is best deployed as a **worker + query store**, with two operational roles:

* **Projector worker(s):** consume S2 events, update projection store, maintain cursor checkpoints.
* **Query handler:** serves S1 queries (can be inside cm-api or separate; semantics must support both).

**Pin:** S3 scaling is horizontal; correctness is maintained by idempotent event application + cursor checkpoints.

---

## 10) S3 anti-patterns (hard bans)

If any of these appear during implementation, it violates the network we pinned:

* S3 writes case truth (“auto close”, “auto assign”) without going through S1→S2.
* S2 commit blocks on “projection update succeeded.”
* S3 calls Label Store / Actions / DLA / EB to “complete” truth.
* S3 becomes the “case database” for detail views (detail truth must come from S2).
* S3 assumes it is always caught up (must surface staleness).

---

Absolutely — we’re illuminating **S4: Evidence Plane** and exposing the machinery that makes **I-J04/I-J05/I-J06**, **I-P03**, and **I-L02/I-L04/I-L06** actually work in production, **without changing the network**.

S4 exists to make **evidence-by-ref** real, safe, and usable:

* DLA is the **flight recorder** (canonical evidence by-ref),
* EB reads are **optional context** (retention-bound),
* engine `truth_products` are **optional oracle/reference lane** (gated, never hot-path traffic),
* and CM truth remains **the case timeline in S2**, with evidence represented as **refs + status evolution**.

---

# S4 — Evidence Plane

## 1) What S4 is allowed to be

### S4 is

A **reference-and-resolution subsystem** that:

* ingests evidence pointers (IDs/refs),
* normalizes them into stable **EvidenceRefs**,
* resolves them **by reference** into redacted views for humans,
* and records **evidence availability/status evolution** as append-only case timeline events (via S2).

### S4 is not

* Not a truth store for evidence payloads (no copying audit/event bodies into case truth).
* Not a decision engine (never auto-disposes or auto-labels from evidence).
* Not an ingestion boundary (does not bypass IG/EB).
* Not a substitute for DLA/Label Store/AL ownership boundaries.

**Designer pin:** S4 may cache, but caches are **non-authoritative** and rebuildable; any investigator-visible “state” change must be representable as **new S2 timeline events**, not silent cache mutation.

---

## 2) S4’s internal sub-machines (the “machinery”)

### E1) Evidence Intake Normalizer

Takes inbound “evidence pointers” from:

* DF/AL/DLA pointer flows,
* investigator attachments,
* external adjudication feeds,
* optional nudges (audit/label events),
  and turns them into a small stable set of **EvidenceRef types**.

**Output:** `EvidenceAttachRequest` → (I-J04) to S2.

---

### E2) EvidenceRef Registry (by-ref index)

Maintains a CM-internal registry keyed by `(case_id, evidence_ref_id)` with:

* EvidenceRef canonical form,
* lane classification,
* last known resolution status,
* correlation keys (decision_id/event_id/action ids),
* optional integrity metadata (digests).

**Important:** This registry is **supporting machinery**. The authoritative “evidence is part of this case” fact is still the **S2 timeline event**.

---

### E3) Resolution Router (source selection)

Chooses which authoritative store to read based on EvidenceRef type:

**Primary source:** DLA by-ref records (`dla/audit/...`).
**Optional enrichment:** EB history reads (retention-bound; evidence only).
**Optional oracle lane:** engine `truth_products` only via SR join surface + PASS gating (never traffic).

---

### E4) Resolver Adapters (per source)

Concrete resolvers that:

* fetch by-ref objects,
* verify integrity (digest if present),
* interpret supersedes/quarantine markers,
* return a structured “resolved evidence view” (still not truth).

Adapters you will typically have:

* **DLAResolver** (object store read)
* **EBResolver** (event context read)
* **ExternalDocResolver** (external evidence store)
* **EngineOracleResolver** (truth_products read, gated)

---

### E5) Redaction & View Composer

Produces the investigator-facing view:

* default: redacted summary,
* optional: deep view for privileged roles,
* always: includes underlying pointers/refs (so “what is this based on?” is explainable).

---

### E6) Evidence Status Tracker (append-only status evolution)

If resolution yields a meaningful state change, S4 emits **status update events** into S2 via I-J04 (never “edits”):

* `EVIDENCE_ATTACHED`
* `EVIDENCE_RESOLVED`
* `EVIDENCE_UNAVAILABLE`
* `EVIDENCE_QUARANTINED`
* `EVIDENCE_SUPERSEDED`
* `EVIDENCE_FORBIDDEN` (policy block)
  …as new timeline events.

This is what preserves “what investigators could see when”.

---

### E7) Nudge Consumer (optional) + Refresh Scheduler

Consumes hints from S7 (I-J06):

* audit pointer events (`fp.bus.audit.v1`) and similar,
* “something changed” signals,
  and schedules background refresh / re-resolution **without becoming correctness-critical**.

---

### E8) Rate Limiting + Cache + Backpressure

Because evidence resolution can be expensive:

* rate-limit per user/case,
* cache redacted views with TTL,
* bound concurrent fetches,
* degrade gracefully (show “unavailable/pending” with pointers).

---

### E9) Evidence Reconcile / Rebuild Controller (ops-grade)

Supports:

* rebuild EvidenceRef registry by scanning S2 timeline,
* refresh status for a case range,
* reconcile “pending” items (e.g., try resolve again),
* never rewrites history; only appends status evolution.

This is the internal counterpart of your platform’s replay/backfill posture (derived state rebuildable).

---

## 3) EvidenceRef types S4 must support (stable set)

This is the minimal stable vocabulary that prevents drift:

1. **DLARecordRef**

* pointer to `dla/audit/...` (canonical forensic evidence).

2. **EventRef**

* `event_id` + optional EB coordinates (topic/partition/offset) for context reads.
* Treated as *context*, not truth.

3. **Decision/Action Refs**

* `decision_id`, `action_intent_id`, `action_outcome_id` (IDs only; details still via DLA refs).

4. **ExternalDocRef**

* pointer to an external doc store, with integrity metadata if available.

5. **EngineOracleRef (optional)**

* locator(s) for engine `truth_products` plus required PASS evidence pointers.
* **Must** be gated and never treated as business traffic.

**Lane pin:** every EvidenceRef is tagged:

* `INVESTIGATION_SUPPORT` (normal evidence),
* `ORACLE_REFERENCE` (optional; fenced).

Oracle lane must never silently override investigation lane.

---

## 4) I-J04 / I-J05 / I-J06 made real inside S4

### I-J04 — Evidence Attach (S4 → S2)

S4 emits an “attach ref” command to S2 with:

* `case_id`, `actor`, `observed_at_utc`,
* normalized EvidenceRef + lane + idempotency key,
* correlation keys (event/decision/action ids),
* optional pin validation (run/world scoping).

**Pin:** attach is idempotent; duplicates do not create duplicate timeline truth.

---

### I-J05 — Evidence Resolve (S1 ↔ S4)

S1 calls S4 with:

* `case_id`, `evidence_ref_id`,
* actor + role context,
* view mode (summary/detail),
* optional “as-of” framing.

S4 returns:

* explicit status (`RESOLVED | PENDING | UNAVAILABLE | QUARANTINED | SUPERSEDED | FORBIDDEN`)
* rendered redacted view
* underlying refs/pointers

**Pin:** fail closed — if it can’t be verified or fetched, it says so.

---

### I-J06 — Nudges (S7 → S4, optional)

Nudges are **hints**, never truth:

* S4 may schedule refresh,
* any durable change still must be represented by **new S2 timeline events** (via I-J04).

Missing nudges must not break correctness.

---

## 5) Resolution algorithm (production-safe, deterministic)

When resolving an EvidenceRef:

### Step A — Authorize view

Based on actor roles and policy:

* If forbidden → return `FORBIDDEN` (and do not fetch sensitive payload).

### Step B — Fetch by-ref from authoritative store

* **DLARecordRef:** read object from `dla/audit/...` (preferred).
* **EventRef:** optional EB context read if enabled and within retention.
* **EngineOracleRef:** only if oracle lane enabled and:

  * obtained via SR join surface (no scanning),
  * required PASS proofs exist,
  * uses output locators (no relying on row order).

### Step C — Integrity and correction handling

* If digest present, verify.
* If record indicates quarantine/supersedes:

  * surface it explicitly (`QUARANTINED` / `SUPERSEDED`),
  * do not silently replace.

### Step D — Render a view

* Redact by default
* Provide pointers always
* Optionally enrich with EB context when available

### Step E — Status evolution

If the case previously had “pending/unavailable” and now becomes resolvable (or superseded):

* append a **new evidence status event** to the case timeline (via I-J04), not a mutation.

---

## 6) Deployment stance for S4 (environment ladder-friendly)

### Runtime roles

* **S4 “API-side” component** (inside `cm-api`): handles I-J05 resolve requests fast.
* **S4 “worker-side” component** (inside `cm-workers`): handles refresh/re-resolution from nudges and scheduled tasks.

These can be the same codebase with different process roles. Semantics must support both.

### Environment profile differences (allowed)

* **Local:** EB retention short → EB context often unavailable; DLA refs dominate.
* **Dev:** mid retention + more realistic auth; nudges maybe enabled.
* **Prod:** strict redaction, strict access controls, nudges enabled for freshness, oracle lane often restricted/disabled by policy.

**Pin:** none of this changes semantics; it changes *availability* and *strictness* only.

---

## 7) S4 anti-patterns (hard bans)

If Codex implements any of these, it’s a design violation:

* Copying full audit/event payloads into case truth (shadow DLA/EB).
* Treating EB context as authoritative truth for the case story.
* Treating engine `truth_products` as hot-path evidence or business traffic.
* Scanning engine outputs or relying on file/row order.
* Silent evidence replacement when superseded (must be visible).
* Making nudges correctness-critical.
* S1 bypassing S4 to fetch DLA/EB directly (breaks redaction + fail-closed discipline).

---

Absolutely — illuminating **S5: Adjudication & Labels Plane**.

S5 is the machinery that turns CM’s **human decisions** into **ground truth** *correctly* — meaning:

* CM records **the disposition** as investigation truth (S2 timeline),
* S5 emits a **LabelAssertion** to **Label Store** (truth owner),
* S5 records **ack/reject/pending** back into S2 as timeline events,
* and S5 serves **as-of label context reads** to the UI without leakage or “latest by accident.”

---

# S5 — Adjudication & Labels Plane

## 1) What S5 is allowed to be

### S5 is

A **translation + emission + context-read** subsystem:

* translates “case disposition” → “LabelAssertion”
* submits LabelAssertions to Label Store **idempotently**
* tracks emission lifecycle and reports outcomes back to the case timeline
* serves label context reads with explicit **as-of semantics**

### S5 is not

* Not a label truth store (Label Store is the only truth).
* Not a place where “disposition == label truth”.
* Not allowed to “fix” labels by mutating them (append-only corrections only).
* Not allowed to infer labels automatically from evidence resolution.

**Designer pin:** S5 must remain correct even when Label Store is down; it must represent “pending” honestly and retry safely.

---

## 2) S5’s internal sub-machines (the machinery)

### L1) Disposition Interpreter

Reads S2’s `DISPOSITION_SET` (or similar) event and extracts:

* subject (what is being labeled)
* disposition value (CM vocabulary)
* actor/principal
* observed time (when CM learned/recorded it)
* optional effective time hints
* mapping_id (which mapping rule set applies)

**Pin:** S5 never emits labels without a **ledger anchor** (`source_case_event_id`).

---

### L2) Disposition → Label Mapping Engine

A deterministic mapping layer that converts CM disposition semantics into label semantics.

It should be treated as a **versioned policy artifact**, not ad-hoc code:

* `mapping_id` (explicit identifier)
* `mapping_rev` (version)
* `label_family` / `label_key`
* how disposition values map to label values
* which subject types are allowed
* any required fields (confidence, reason codes, etc.)

**Designer call:** every emitted LabelAssertion must include the mapping identity in provenance (or at least S2 must record it), so you can always answer: “which mapping produced this label?”

---

### L3) Time Semantics Resolver (critical)

This is where the platform’s label timeline rail is enforced.

S5 must always set:

* **observed_time** = the CM disposition event’s observed timestamp (when we learned it)
* **effective_time** = when it is true in the world (may be earlier)

**Pinned default rule (v0):**

* If the subject is an `event_id` and the event has a domain `ts_utc`, default `effective_time = event.ts_utc`
* Otherwise default `effective_time = observed_time`
* If the disposition explicitly specifies effective_time, use it

This makes late truth (chargebacks, delayed outcomes) representable without collapsing semantics.

---

### L4) LabelAssertion Builder

Constructs the actual assertion object to submit to Label Store:

Conceptual fields:

* `subject` (entity/event/flow key)
* `label_family` + `value` (+ optional confidence)
* `effective_time`, `observed_time`
* provenance:

  * `origin = case_workbench`
  * `actor_principal` (human)
  * `case_id`, `source_case_event_id`
  * `mapping_id`/`mapping_rev`
  * optional evidence pointers (by-ref, not blobs)

**Designer pin:** S5 always carries enough provenance to trace the label back to the exact case event.

---

### L5) Idempotent Emitter (submission machinery)

This is the “safety core” of S5.

* Emits LabelAssertions to Label Store with a **deterministic idempotency key** derived from:

  * `(case_id, source_case_event_id, mapping_id)` (minimum)
* Handles retries and duplicate sends without creating multiple logical assertions.

**Pinned semantics:**

* “submitted” is not truth.
* only Label Store acceptance makes the label truth exist.

---

### L6) Outcome Tracker (ack/reject/pending → back to S2)

S5 must report back to S2 (I-J08) as **new timeline events**:

* `LABEL_SUBMITTED`
* `LABEL_ACCEPTED` (with `label_assertion_id` pointer)
* `LABEL_REJECTED` (with reason code)
* `LABEL_RETRY_SCHEDULED` / `LABEL_PENDING`

**Designer call:** these are append-only. Never rewrite the disposition event.

---

### L7) Label Context Reader (as-of queries)

Serves UI and other CM needs (I-J09):

Two explicit modes:

* `CURRENT_TRUTH` (as-of now)
* `KNOWN_AT(as_of_observed_time)` (what was known then)

**Pinned default:** `KNOWN_AT` uses **observed_time** boundary (leakage-safe).

Returns:

* a timeline of assertions (not one value)
* supersedes chain metadata
* the as-of basis used

This is crucial for reproducibility: “we decided with only what we knew then.”

---

### L8) Optional Nudge Handler (from S7)

Consumes label-change nudges (I-J10) as hints:

* refresh caches / invalidate views
* but never treat nudge payload as truth
* always re-read Label Store for authoritative truth

---

### L9) Backpressure / Retry Controller

Because Label Store can be down or slow:

* retry with backoff
* cap outstanding pending label emissions per case
* expose metrics: pending, retrying, rejected, accepted

---

## 3) S5’s canonical lifecycle (how it behaves in production)

1. Investigator sets disposition → S2 appends `DISPOSITION_SET`.
2. S2 emits a `LabelWorkItem` (I-J07) → S5.
3. S5 builds LabelAssertion (mapping + time semantics + provenance).
4. S5 submits to Label Store (idempotent).
5. S5 reports the outcome to S2 as new timeline events (I-J08).
6. S3 derives “case resolved/pending label/rejected label” badges from S2 events.
7. UI reflects truth honestly.

**Closure rule (pinned):** the “label loop” closes only when S2 records `LABEL_ACCEPTED` or `LABEL_REJECTED` (pending is explicitly pending).

---

## 4) Deployment stance for S5 (ladder-proof)

### Runtime role

S5 is primarily a **worker** (inside `cm-workers`):

* consumes LabelWorkItems from S2 outbox
* calls Label Store
* appends results back into S2

S1/UI may call S5 in-process for **label context reads**, but emission itself should be async and retryable.

### Environment differences (profiles)

* local: permissive writer policy, lower rate limits, faster iterations
* prod: strict allowlists, potentially approvals for certain label families, stronger audit logging

**Pin:** semantics don’t change; strictness and throughput do.

---

## 5) S5 “red line” anti-patterns (hard bans)

If any of these happen, it violates the design:

* Treating `DISPOSITION_SET` as if it automatically created label truth (it doesn’t).
* Writing labels without effective_time/observed_time distinction.
* Mutating prior labels (no destructive edits; corrections are new assertions).
* Emitting labels without actor provenance and case linkage.
* Using label-change nudges as truth (must query Label Store).
* Auto-labeling from evidence resolution (labels come from disposition/external adjudication workflows).

---

Absolutely — illuminating **S6: Manual Intervention Plane**.

S6 is the machinery that lets humans request side effects **safely** while preserving the platform’s pins:

* CM **never executes** actions.
* Humans request via **ActionIntent**.
* **Actions Layer (AL)** executes and produces immutable outcomes (including denial).
* CM closes the loop only when outcome evidence returns (typically via DLA refs through S4).

---

# S6 — Manual Intervention Plane

## 1) What S6 is allowed to be

### S6 is

A **request-to-intent submission subsystem** that:

* consumes “manual action requested” work items from the CM ledger (S2 outbox),
* validates and authorizes the request (prechecks),
* constructs a properly-scoped **Manual ActionIntent**,
* submits it into the platform’s actions pathway (AL/IG traffic spine),
* records **submission state** back to the case timeline (S2),
* and then relies on S4 to attach immutable outcomes later.

### S6 is not

* Not an executor (no direct side effects).
* Not an outcome authority (submission is not execution).
* Not allowed to “close” an action without outcome evidence.
* Not allowed to bypass CM truth: every action attempt must be anchored to a case timeline event.

**Designer pin:** S6 must remain correct under at-least-once delivery; duplicate work items must not fork actions.

---

## 2) S6’s internal sub-machines (the machinery)

### A1) Work Item Consumer

Consumes `SUBMIT_ACTION_INTENT` work items from S2’s outbox, each anchored to:

* `case_id`
* `source_case_event_id` (the action request timeline event)
* `action_idempotency_key` (dedupe anchor)

**Pin:** a work item always maps to exactly one intended ActionIntent identity.

---

### A2) Policy / Authorization Precheck Engine

This is where manual actions become safe.

Precheck decides whether the action request may proceed, based on:

* actor principal + roles,
* action type,
* scope (entity/event ref + ContextPins),
* any “approval mode” policy (local relaxed vs prod strict),
* rate limits / safety constraints.

Precheck outputs:

* `ALLOW` → proceed to build/submit intent
* `DENY` → do not submit; report `ACTION_REQUEST_PRECHECK_REJECTED` to S2
* `REQUIRE_APPROVAL` (optional posture) → create an approval workflow record inside CM (still anchored to S2) before submission

> Designer call: **Precheck denies are CM-side denies** (they are not AL outcomes). We must keep that distinction clear: AL denials are immutable outcomes later; CM precheck is “never submitted.”

---

### A3) ActionIntent Builder (canonical construction)

Builds a **Manual ActionIntent** from the request and policy context.

Minimum conceptual fields:

* `action_type`
* `target_ref` (entity/event ref)
* `origin = manual_case_workbench`
* `actor_principal` (human) + role/scope context
* `context_pins` (run/world scoping when relevant)
* `idempotency_key` (required; derived deterministically)
* `requested_at_utc` (CM observed time)
* `justification_refs[]` (by-ref evidence pointers, not blobs)
* optional `constraints` (TTL, limits)

**Designer pin (idempotency recipe):**
`action_idempotency_key = hash(case_id + source_case_event_id + action_type + canonical(target_ref))`

This ensures:

* retries don’t fork,
* duplicates don’t re-execute,
* and the same requested action has a stable identity.

---

### A4) Submitter (transport + retries)

Submits the ActionIntent into the actions pathway.

Mechanically, this goes where your platform expects intents to go (traffic spine via IG/EB; AL consumes). S6 doesn’t need to know the whole bus topology; it just needs to submit into the “ActionIntent intake” surface.

Submission outcomes (local to S6) are:

* `SUBMITTED` (accepted for processing / queued)
* `SUBMIT_FAILED_RETRYABLE` (transport error)
* `SUBMIT_FAILED_FATAL` (shape invalid / policy mismatch)

**Pin:** `SUBMITTED` is not execution, not success.

---

### A5) Submission State Reporter (back to S2)

S6 reports submission state as **new case timeline events** (I-J12):

* `ACTION_INTENT_SUBMITTED`
* `ACTION_INTENT_SUBMIT_FAILED_RETRYABLE` (+ retry schedule)
* `ACTION_REQUEST_PRECHECK_REJECTED` (+ reason)

These become part of the investigation story: “we tried to do X; here’s what happened at submission time.”

---

### A6) Outcome Linker (join-key discipline, but not an outcome store)

S6 ensures the system can later link the immutable outcome back to the case by making sure the intent contains stable join keys:

* `action_idempotency_key`
* `action_intent_id` (if assigned on submit)
* correlation keys (case_id, source_case_event_id)

But S6 does **not** fetch or decide outcomes.

Outcomes return as evidence via S4:

* DF/AL/DLA pointers or audit pointer nudges
* S4 attaches `ACTION_OUTCOME_ATTACHED` evidence refs to S2 (I-J13)

**Designer pin:** S6 never marks “executed” — only S4 + DLA evidence closes the loop.

---

### A7) Safety & Backpressure Guard

Manual actions are high-risk. S6 enforces:

* per-actor and global rate limits,
* per-case limits (e.g., “no more than N pending manual actions per case”),
* circuit breaker when AL/transport is down,
* “cooldown” rules for repeated denies/failures.

This prevents operational disasters without changing semantics.

---

### A8) Audit/Telemetry Emitter

S6 must emit:

* structured logs for “requested/denied/submitted/retry scheduled”
* metrics: pending submissions, denied by policy, retry queues, submission latency
* traces: link case_event_id → action_intent submission span

This is critical for ops.

---

## 3) S6’s production lifecycle (end-to-end within CM)

1. Investigator requests action → S2 appends `ACTION_REQUESTED`.
2. S2 creates `SUBMIT_ACTION_INTENT` work item.
3. S6 consumes work item, prechecks, builds ActionIntent, submits.
4. S6 reports `SUBMITTED / PRECHECK_REJECTED / RETRY` into S2 timeline.
5. Later, immutable outcome arrives (AL executes; DLA records).
6. S4 attaches outcome evidence to S2.
7. S3 derives “pending/executed/denied/failed” badges for UI.

**Closure rule (pinned):** action loop closes only on `ACTION_OUTCOME_ATTACHED` evidence, not on submission.

---

## 4) Deployment stance for S6 (environment ladder-friendly)

* S6 is a **worker** role (cm-workers).
* It must tolerate AL outages: queue and retry idempotently.
* Environment differences are **policy profiles**:

  * local: permissive, minimal approval
  * dev: realistic allowlists
  * prod: strict allowlists + optional multi-approval + lower rate limits

Semantics remain identical.

---

## 5) S6 anti-patterns (hard bans)

If Codex does any of these, it violates the design:

* Executing side effects directly from CM.
* Treating submit ACK as execution success.
* “Auto-closing” actions without immutable outcomes.
* Generating non-deterministic idempotency keys (would fork actions).
* Allowing manual actions without actor principal and scoped target.
* Hiding precheck denies (must be explicit in the case timeline).

---

Absolutely — illuminating **S7: Signals & Bus Adapters**.

S7 is **optional**, but in a production platform it’s valuable because it:

* publishes **case control facts** (signals) for automation/ops,
* consumes **pointer/control events** (nudges) to improve freshness,
* and does both **without ever becoming correctness-critical**.

S7 must obey the platform boundary pins:

* Any bus emission must go **through IG** and use the **canonical event envelope**.
* Quarantine/duplicate/admit outcomes are explicit (no silent drop).
* Nudges are **hints**, not truth; missing nudges must not break correctness.

---

# S7 — Signals & Bus Adapters

## 1) What S7 is allowed to be

### S7 is

A **non-critical adapter layer** that:

* turns certain S2 timeline events into **control-plane bus events** (via IG),
* records the IG admission outcome as receipts back into S2,
* consumes optional bus topics (audit/control) to create **nudges** for S4/S5 refresh.

### S7 is not

* Not a truth owner.
* Not a required dependency for any core CM loop (cases, labels, actions must still work if S7 is off).
* Not allowed to publish sensitive evidence payloads (signals are pointers/summaries).
* Not allowed to “apply truth updates” into S2 (except recording publish receipts).

**Designer pin:** Disabling S7 may reduce freshness/automation but must never change correctness.

---

## 2) S7 internal sub-machines (the machinery)

### B1) Publish Selector (event filter)

A deterministic rule set that decides which S2 case events are eligible to publish as signals.

Inputs:

* `source_case_event_id`, `event_type`, `case_id`, summary fields, pins.

Rules are **profile-controlled**:

* local: often disabled or minimal
* dev: moderate
* prod: focused, low-volume, high value

Examples of publishable events:

* `CASE_CREATED`, `CASE_ESCALATED`, `CASE_CLOSED`
* `DISPOSITION_SET` (maybe)
* `LABEL_ACCEPTED` (maybe as “resolved” signal)
* `ACTION_OUTCOME_ATTACHED` (maybe)

> Pin: publish set is configuration, not hard-coded behavior.

---

### B2) Canonical Envelope Builder

Constructs a bus event that conforms to your **canonical event envelope**:

Required:

* `event_id` (stable)
* `event_type`
* `ts_utc`
* `manifest_fingerprint`

Optional:

* additional ContextPins (`parameter_hash`, `run_id`, `scenario_id`, etc.)
* tracing fields
* producer identity

**Stable event_id rule (pin):**
`event_id` must be derived from `source_case_event_id` (or a deterministic function of it), so retries don’t create new signals.

Payload discipline:

* must be **small** and by-ref friendly:

  * `case_id`
  * `case_event_id` (pointer to CM truth)
  * summary fields (status/assignee/priority)
  * linkage keys (event_id, decision_id, entity_ref)
  * optional references to evidence pointers (never blobs)

---

### B3) IG Producer Client (trust boundary submitter)

S7 submits the built signal to **Ingestion Gate** as a producer.

IG will:

* ADMIT
* DUPLICATE
* QUARANTINE
  and issue a **receipt** (and quarantine reference if applicable).

**Pin:** S7 never writes directly to EB; IG is always the front door.

---

### B4) Receipt Recorder (S7 → S2)

S7 writes the IG outcome back into S2 as new timeline events:

* `CASE_SIGNAL_ADMITTED`
* `CASE_SIGNAL_DUPLICATE`
* `CASE_SIGNAL_QUARANTINED`

Including:

* `published_event_id`
* `ig_outcome`
* `receipt_ref`
* optional `quarantine_ref`

**Pin:** receipts are explicit outcomes; no silent drop.

---

### B5) Audit Topic Consumer (optional)

Consumes `fp.bus.audit.v1` (if enabled) — pointer events indicating new/updated audit records.

S7 does **not** treat these as evidence truth.
It emits **EvidenceNudges** to S4:

* correlation keys (decision_id / action ids / event_id)
* audit record ref if present
* supersedes hint if present

**Pin:** nudges are hints; S4 must still resolve by-ref and update S2 via append-only events.

---

### B6) Control Topic Consumer (optional)

Consumes `fp.bus.control.v1` label events (if Label Store emits them) and potentially other control facts.

It emits **LabelChangedNudges** to S5:

* subject keys
* label_assertion_id / pointer
* observed_time (if present)

Again: **hint only**; S5 must read Label Store truth.

---

### B7) Nudge Deduper & Scheduler

Because bus delivery is at-least-once and can reorder:

* dedupe by stable keys (audit_ref / label_assertion_id / subject+observed_time)
* schedule refresh jobs for S4/S5 with backoff
* cap per-case / per-subject nudge storms

---

### B8) Backpressure & Safety Controls

S7 must be “quiet and safe”:

* publish rate limits (control topic must not be spammed)
* nudge rate limits
* circuit breaker if IG is down (publish work items retry later; signals are non-critical)
* bounded memory/queues

---

### B9) Observability (mandatory)

S7 emits:

* publish attempt metrics (submitted/admitted/duplicate/quarantined)
* time-to-admit latency
* consumer lag on audit/control topics
* nudge throughput/dedup rates
* trace correlation from `source_case_event_id` to `published_event_id`

---

## 3) S7 core workflows (how it behaves)

### Workflow A — Publish case signal (optional)

1. S2 creates `PUBLISH_CASE_SIGNAL` outbox work item (I-J14).
2. S7 consumes it.
3. Builds canonical envelope event with stable event_id.
4. Submits to IG.
5. Receives outcome + receipt ref.
6. Records receipt outcome into S2 (I-J15).

Failure: IG down/quarantine → record outcome; CM truth unaffected.

---

### Workflow B — Audit pointer → evidence refresh (optional)

1. S7 consumes audit pointer event.
2. Dedup + schedule.
3. Emits EvidenceNudge to S4 (I-J06).
4. S4 resolves and, if status changes, appends to S2 via I-J04.

Failure: if S7 misses it, S4 still resolves on demand; correctness intact.

---

### Workflow C — Label event → label context refresh (optional)

1. S7 consumes label control event.
2. Dedup + schedule.
3. Emits LabelChangedNudge to S5 (I-J10).
4. S5 refreshes by reading Label Store.

Failure: if S7 misses it, S5 still reads Label Store on query; correctness intact.

---

## 4) Deployment stance for S7 (environment ladder)

S7 is a worker-style component and may be:

* disabled entirely (local),
* enabled partially (dev),
* enabled with stricter rate limits and monitoring (prod).

**Profile knobs:**

* enable_publish_case_signals
* enable_consume_audit_pointers
* enable_consume_label_events
* topic names / consumer groups
* rate limits / backoff caps

**Pin:** toggles change only freshness/automation; never truth semantics.

---

## 5) S7 anti-patterns (hard bans)

If Codex does any of these, it violates the design:

* Publishing directly to EB without IG.
* Treating signal publish as truth (“case closed only if signal admitted”).
* Emitting raw evidence/audit payloads onto control topic.
* Treating nudges as truth and skipping authoritative reads.
* Letting nudge processing mutate S2 truth except via the already-defined append-only “receipt/status” event pathways.
* Designing the system so S7 must be online for case/label/action correctness.

---

That completes the illumination of the Level-1 CM subnetworks (S1–S7) without changing the network we pinned.

---

## USER: PAUSE FOR REFLECTION

Agreed — and it’s worth pausing because what we’ve just revealed isn’t “a component,” it’s a **mini-platform** whose shape is forced by your rails.

## What makes the network deep (in a good way)

### 1) It has a single truth spine, but many closure loops

At the core, CM is simple: **S1 → S2 append-only timeline truth**.
What creates depth is the number of *closure loops* that must complete **without distributed commit**:

* **Evidence loop:** attach refs → resolve by-ref → status evolves (append-only)
* **Label loop:** disposition → emit LabelAssertion → ack/reject recorded
* **Manual action loop:** request → submit intent → outcome evidence later closes
* **Optional signal loop:** publish → IG receipt recorded
* **Rebuild loop:** derived state rebuildable, truth never rewritten

That’s exactly how you get production reliability without turning everything into synchronous coupling.

### 2) Every external truth owner remains sovereign

The network is complex because it **refuses to cheat**:

* Labels are not “a field on the case” — they’re timelines in Label Store.
* Actions aren’t “done when you click” — they’re intents + immutable outcomes in AL/DLA.
* Evidence isn’t “copied into the case” — it’s pointers into the flight recorder and event log.

That separation creates more edges, but it prevents the *worst* kind of complexity: hidden contradictions.

### 3) It’s designed for at-least-once reality

A lot of systems look simple until you add retries and duplicates. Here, idempotency is baked into:

* commands,
* work items,
* emissions,
* receipts,
* nudges,
* reconciliation.

That’s why the network feels “heavy,” but it’s the correct weight for production.

### 4) The environment ladder is satisfied by design, not by hope

Local/dev/prod differ in:

* strictness,
* retention,
* observability depth,
* which optional edges are enabled,

…but **the semantics don’t change**. That’s a big achievement: you can harden the same graph rather than maintain three versions.

## The mental model to carry forward (so we don’t get lost)

If we compress the illuminated CM into one sentence:

**CM is an append-only investigation ledger (S2) with derived workflow views (S3), by-ref evidence resolution (S4), truth emission via LabelAssertions (S5), side-effect requests via ActionIntents (S6), and optional bus adapters for signals/nudges (S7) — all coordinated through an outbox so nothing external blocks truth.**

## The key risk to watch as we move from “modules” to “internals”

The danger isn’t that we forget a feature — it’s that we accidentally:

* introduce a second truth store (S3/S4/S5 caches becoming authoritative),
* make optional edges correctness-critical (S7),
* or sneak in synchronous coupling (S2 commit waiting on external systems).

If we keep those three risks in mind, the next deeper dive can be methodical rather than overwhelming.

---