# Label & Case — how outcomes crystallise

The Real-time Decision Loop is about **what we do now**.
The Label & Case plane is about **what that meant in the end**.

Decisions, actions, and simulations all create ripples: some transactions were truly fraudulent, some were misunderstandings, some were good but treated harshly. Some warranted a case, some slipped past. If the platform is going to learn anything, it needs a place where those outcomes **settle and harden**.

This plane has two big responsibilities:

* a **Label Store** that holds the system’s understanding of “what really happened”, in a way that training and monitoring can rely on, and
* a **Case Management / Workbench** that tracks human-facing investigations over time.

Together, they close the loop from “decision” to “ground truth”.

---

## 1. Where labels come from

Labels don’t pop out of nowhere. In this system there are two broad sources:

1. **Engine-generated labels** (in synthetic worlds)

   * The Data Engine’s 6B segment already knows the **true stories**:

     * which flows were fraud vs abuse vs legit,
     * what the bank thought happened (bank-view labels),
     * what cases were opened and how they moved.
   * These surfaces give you, for each world:

     * **truth labels** (ground truth about fraud/abuse),
     * **bank-view labels** (what an on-paper bank would mark as confirmed fraud, FP, dispute, chargeback),
     * and **case timelines**.

2. **Platform outcomes** (in real or mixed worlds)

   * When the platform is integrated with live transactions, labels also come from:

     * dispute/chargeback systems,
     * manual analyst decisions,
     * customer self-reports,
     * external bureaus, etc.
   * These sources can be messy: partial, late, contradictory, incomplete.

The Label & Case plane is where all of this gets **pulled into a single vocabulary**.

---

## 2. Label Store — one place for “what happened”

The **Label Store** is the platform’s **source of truth for outcomes**. Not necessarily ground-truth reality (because no such oracle exists in production), but the single, coherent place where we say:

> “For this flow, with this world identity, our best understanding is X.”

Conceptually, the Label Store holds:

* **Flow-level labels**, e.g.:

  * `LEGIT`, `FRAUD_CARD_NOT_PRESENT`, `FRAUD_ACCOUNT_TAKEOVER`, `ABUSE_REFUND`, etc.
  * Bank-view labels like `CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `DISPUTE_OPEN`, `CHARGEBACK_LOSS`, `CHARGEBACK_REVERSAL`.
* **Event-level labels**, e.g.:

  * which specific events in a flow were fraudulent,
  * which events correspond to detection actions, challenges, case events.
* **Entity-level labels**, e.g.:

  * “this card is compromised”,
  * “this device is a known mule device”,
  * “this merchant is collusive”.

Under the hood (conceptually):

* Every label is **keyed by world identity** (`parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id`) and by some **business key**:

  * `(flow_id, world_id)`, `(event_id, world_id)`, or `(entity_id, world_id)`.
* Labels have a **lifecycle**:

  * they move from “unknown / pending” to “suspected” to “confirmed / rejected” over time,
  * with timestamps so you can reconstruct what was known *at any point*.

In synthetic runs:

* Label Store can be **hydrated primarily from 6B** surfaces:

  * the engine tells you truth + bank-view + cases;
  * the platform simply ingests them via the same Ingestion + Bus rails and writes them as if they came from live systems.
* This gives you a **fully closed loop** with no dependence on external label sources.

In real runs:

* The Label Store also accepts signals from external systems (chargebacks, analyst decisions, customer flags), reconciles them with model decisions, and expresses them in the same unified schema.

Everything in the learning and monitoring planes reads from **this** store, not from ad hoc label tables.

---

## 3. Lag and lifecycle — making time explicit

Fraud labels are rarely instant:

* a card test might be detected within seconds,
* a card-not-present fraud might surface as a chargeback 60 days later,
* a false positive might be discovered only when a customer complains.

The Label & Case plane **does not pretend** everything is known on day one. Instead, it makes lag explicit:

* Labels have **state machines**, not just binary flags:

  * e.g. for flow truth: `UNKNOWN → SUSPECTED_FRAUD → CONFIRMED_FRAUD` or `UNKNOWN → SUSPECTED_FP → CONFIRMED_FP`.
  * for bank view: `NO_CASE → CASE_OPEN → CASE_IN_PROGRESS → CASE_CLOSED_[OUTCOME]`.
* The Label Store keeps **time-stamped transitions**:

  * when we first suspected something,
  * when we confirmed or cleared it,
  * when financial loss was actually realised.

For synthetic worlds, 6B already simulates these delays; Label Store just reflects them.

For real worlds, the Label Store is where those delayed signals land and become **usable** for training, monitoring, and offline evaluation. It is the place where “we initially thought this was fine” and “we later learned it was fraud” can both be true, but in different time slices.

This is crucial when training models:

* It allows you to build datasets that represent **what was known at decision time**, not what we know now.
* It lets you compute metrics with different labeling cut-offs (e.g. “30-day view vs 90-day view”).

---

## 4. Cases — stories that need a human

Not every suspicious flow should be auto-declined, and not every label is the result of automation. Some subsets of events and flows become **cases**: work items that an analyst needs to investigate.

The **Case Management / Workbench** side of this plane is where:

* flows, events, entities, and labels are grouped into **cases**,
* humans can inspect, annotate, and resolve them,
* and the state of those investigations is tracked over time.

Conceptually:

* A **case** is anchored to:

  * a world identity,
  * one or more flows/events/entities,
  * and a case type (fraud investigation, dispute resolution, merchant review, etc.).
* It has a **timeline**:

  * opened at T₀ (maybe as soon as a model suggests `QUEUE`),
  * triaged at T₁,
  * enriched with notes, attachments, and decisions at T₂…Tₙ,
  * closed at Tₙ+1 with an outcome (`CONFIRMED_FRAUD`, `NO_ISSUE`, `ABUSE_PATTERN_FOUND`, etc.).
* It writes back **case events** into the system, which in turn influence labels:

  * e.g. “Case closed as confirmed fraud” updates flow and entity labels accordingly.

In synthetic worlds, the engine’s case timelines from 6B can be ingested into the Case plane to:

* test whether the Case UI and pipelines *can* carry realistic workloads,
* test queueing strategies, SLAs, and playbooks.

In real worlds, the Case plane becomes the living record of analysts’ work, but it still writes outcome labels into the same Label Store so models and metrics see a coherent picture.

---

## 5. How Label & Case feed the rest of the platform

This plane is the **hinge** between the real-time loop and the learning loop.

Downstream:

* The **Offline Feature Plane** uses Label Store as its source of targets when assembling training/replay datasets.
* The **Model Factory** pulls labels and case outcomes to:

  * build supervised datasets,
  * compute evaluation metrics (precision/recall, cost curves, calibration) w.r.t ground truth and bank-view,
  * measure model impact on **case workload** (how many cases, how many unnecessary ones).
* **Monitoring & Governance** rely on Label Store to:

  * measure false positives vs false negatives,
  * track decision mix over time (e.g. rising decline rates in some segments),
  * detect drift (e.g. model sees a familiar pattern but labels suggest it’s a new flavour of fraud).

Upstream:

* Decisions and actions emit **outcome events** into the system (STEP-UP passed/failed, disputes filed, chargebacks processed).
* External systems (in real worlds) can also feed the Label Store, which in turn influences how case queues and model evaluations are interpreted.

The key idea is:

> The Label & Case plane is the **only place** from which models, dashboards, and governance logic should draw conclusions about outcomes.

No more secret label tables scattered across the system.

---

## 6. Boundaries and non-goals

To keep later specs and implementations aligned with this narrative, it’s helpful to say what this plane **does not** do:

* It does **not** decide in real time; that is the Decision Fabric’s job. It reacts to decisions and external signals.
* It does **not** re-simulate behaviour or re-run the engine; it ingests label-like facts and case timelines from engine or production sources.
* It does **not** define training logic; it only provides clean label surfaces and case outcomes that the Model Factory consumes.
* It does **not** pretend labels are perfect; instead, it makes uncertainty, lag, and lifecycle *explicit*.

Its job is to take all the messy, time-lagged, multi-source hints about “what happened” and turn them into a **coherent, time-aware label and case system**. The rest of the platform can then:

* train models,
* compute metrics,
* and make governance decisions
  on top of those surfaces without guessing.

Everything about the Learning & Evolution plane assumes that this Label & Case plane is doing exactly that: **crystallising outcomes**, and nothing else.
