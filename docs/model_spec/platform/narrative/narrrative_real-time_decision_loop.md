# Real-time Decision Loop — how an event becomes an action

This plane is the **nervous system** of the fraud platform. It’s what happens “during the day” after a world has been chosen, the engine has spun up, and the Control & Ingress plane has admitted events as real.

Upstream, the Ingestion Gate hands us a **clean, well-labelled stream**:

* every event has been schema-checked and de-duplicated at the boundary,
* it carries world identity (`parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id`) and correlation IDs,
* and it’s safe to treat as production traffic.

The Real-time Decision Loop takes that stream and turns each event into **a decision and an action**—fast enough to be useful, but rich enough to be meaningful. It keeps a mirror of its own behaviour for tomorrow’s training and replay, and it knows how to bend under pressure without breaking.

The main actors are:

* an **Event Bus** that carries the stream,
* an **Online Feature Plane** that remembers relevant history,
* an **Identity & Entity Graph** that provides context,
* a **Decision Fabric** that turns context into decisions,
* an **Actions Layer** that applies those decisions to the outside world,
* a **Decision Log & Audit Store** that records what really happened,
* and a **Degrade Ladder** that decides how to behave when the system is stressed.

The Offline Feature Plane, Label Store, and Model Factory live mostly in the learning loop, but they have shadows in this plane: every decision we make today needs to be explainable, replayable, and improvable tomorrow.

---

## 1. Event Bus — the backbone of the day

Once events leave the Ingestion Gate, they land on a **durable, ordered event bus**. The bus is not clever. That is on purpose.

Its responsibilities are simple:

* **Carry events forward** with at-least-once delivery and a stable partitioning key (e.g. by world and entity/merchant), so consumers can reason about ordering within that scope.
* **Preserve lineage**: the world IDs and correlation IDs stamped at ingestion travel unchanged on every message.
* **Support replay**: given a world and a time window, you can read the same stream back and reconstruct what the system saw.

The bus does not:

* apply business logic,
* mutate payloads,
* or talk to external systems.

It is a backbone that everyone listens to and nobody tries to “fix”.

---

## 2. Identity & Entity Graph — waking up the context

The platform doesn’t want to make decisions in isolation. It wants to know:

* *who* is behind an event,
* *what* instruments/accounts it touches,
* and *how* they are connected to everything else.

That context lives in the **Identity & Entity Graph**: the read-only view of the world built by 6A (parties, accounts, instruments, devices, IPs, merchants, and their links).

In the Real-time Decision Loop:

* The graph is **hydrated from authority surfaces** (6A bases and link tables).
* It is kept **in sync with the stream** as new derived facts become available (e.g. updated trust scores or static flags).
* When an event arrives on the bus, the feature service and decision fabric can ask the graph simple questions:

  * “Which party is behind this account?”
  * “Which devices and IPs has this card used recently?”
  * “Is this merchant known as high-risk or part of a ring?”

The key rule is:

> Real-time components **query** the graph; they never mutate the ground truth from the engine.

Updates happen either by ingesting new authority surfaces (new worlds) or by writing separate, versioned “platform views” derived from them.

---

## 3. Online Feature Plane — p99-safe memory

To make a good decision, the platform needs **memory**: counts, windows, last-seen timestamps, behaviour patterns. The Online Feature Plane is that memory, tuned for low latency.

It listens to the Event Bus and, for each event:

* identifies one or more **keys** (such as `(party)`, `(card, merchant)`, `(device)`, `(IP)`),
* updates **counters and windows**:

  * transaction counts over sliding windows,
  * sum/avg amounts,
  * distinct merchants, devices, IPs,
  * time-of-day and geo-based features,
* and writes updates into a **fast feature store** under strict SLOs.

For the Decision Fabric, the online plane must:

* respond within a tight latency budget (think p99, not just p50),
* respect **freshness and TTL**: features are only valid if they’ve been updated recently enough,
* expose **schema-anchored feature groups** (so the model and offline plane know what to expect),
* and include world IDs in its keys so features are world-aware and replayable.

The Online Feature Plane does not try to compute everything:

* It focuses on the **minimal core set** needed for real-time scoring.
* Heavy or exotic features live offline, or in an optional second-stage service.

---

## 4. Offline Feature Plane — tomorrow’s twin

The **Offline Feature Plane** is the **shadow twin** of the online one. It is not on the hot path, but it is conceptually part of this loop because it guarantees one crucial thing:

> The features you train and replay with are **the same transforms** as the ones you serve with.

To do that, it:

* consumes the same Event Bus,
* uses the same feature code and schemas as the online plane,
* writes **batch snapshots** of features keyed by:

  * world IDs,
  * entity IDs,
  * and time.

The Real-time Decision Loop relies on this in two ways:

1. Every decision records a **feature snapshot hash** (or equivalent), so that offline jobs can **rebuild the exact feature vector** the model saw when the decision was made.
2. When you replay a world or a time slice, the offline plane can recompute features from the raw event stream and compare them to what the online plane produced, catching drift or bugs.

In this narrative, we don’t care whether the offline plane runs as nightly jobs, micro-batches, or continuous backfills. The important thing is that it **mirrors the online logic** and is treated as a first-class citizen.

---

## 5. Decision Fabric — turning context into a decision

The **Decision Fabric** is a single API from the caller’s perspective:

> “Given this event and its context, what should we do right now?”

Inside, it has a clear structure:

1. **Guardrails (stage 1)**
   Cheap, deterministic checks that enforce:

   * schema/shape expectations,
   * static policy (e.g. “block known test cards in prod”),
   * simple thresholds (amount caps, country blocks under maintenance).
     Guardrails can **short-circuit** to an action (e.g. immediate DECLINE or STEP-UP) without talking to the model.

2. **Primary model (stage 2)**
   A calibrated, first-line ML model that consumes:

   * the event payload,
   * a selected set of online features,
   * world identity (so it can distinguish worlds if needed).
     It outputs a **risk score** (or distribution) and possibly auxiliary signals.

3. **Optional second stage (stage 3)**
   A slower, richer check (graph coherence, deep device/IP analysis, cross-entity correlation).
   It only runs if:

   * the latency budget is still healthy, and
   * the first stages haven’t already yielded a confident decision.

A **policy layer** on top of these stages turns everything into a final decision:

* **APPROVE / STEP-UP / DECLINE / QUEUE**,
* a set of **reasons** (for audit and customer messaging),
* and a **provenance bundle** containing:

  * world IDs,
  * model/policy versions,
  * feature snapshot hash,
  * guardrail hits,
  * and timings per stage.

The Decision Fabric doesn’t fetch raw labels or refit itself. Its job is to **apply policies and models**, given the inputs, under constraints.

---

## 6. Actions Layer — making the outside world move

A decision is only useful if something actually happens.

The **Actions Layer** takes the decision and:

* applies the appropriate **side-effects**:

  * allow the transaction to proceed,
  * trigger a step-up challenge (3DS/OTP),
  * decline and notify,
  * enqueue a case for manual review,
* ensures these effects are **idempotent**:

  * a retried message doesn’t double-charge,
  * a duplicate decline doesn’t spam notifications,
  * double case creation is prevented,
* records **action outcomes**:

  * whether a challenge was passed or failed,
  * whether a queued case was created successfully,
  * any errors or anomalies.

From the Real-time Decision Loop’s perspective, actions are another node in the graph of consequences. They influence labels later, but here the important things are:

* they follow the decision’s intent,
* they are safe under retries,
* and they write their own events back into the system (for logging and labelling).

---

## 7. Decision Log & Audit Store — the black box recorder

To trust a fraud system—especially one powered by synthetic worlds and ML—you need a **complete account of what it did and why**.

The **Decision Log & Audit Store** is that black box recorder.

For each decision, it stores:

* the **event envelope** (or a reference to it on the bus),
* world IDs (`parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id`),
* the **features snapshot hash** and, optionally, feature values (or pointers),
* the decision stages exercised (which guardrails fired, whether the second stage ran),
* the final action, and
* timings and error flags.

For this plane, the important guarantee is:

> You can always reconstruct “what we knew at the time” and “why we did what we did” for any decision.

Later, the learning loop and analytic tooling will rely on this store for training, evaluation, investigations, and compliance.

---

## 8. Degrade Ladder — how the loop bends without breaking

Real systems don’t run at spec forever. Services slow down, feature stores lag, models get heavy. The Real-time Decision Loop needs a way to **protect latency and safety** when that happens.

That’s the job of the **Degrade Ladder**.

It watches a combination of:

* observability signals (latency percentiles, error rates, saturation),
* SLOs for the Decision Fabric and the Online Feature Plane.

When pressure rises, it shifts the Decision Fabric into simpler modes in a **fixed, predictable order**, for example:

1. Turn off the second stage.
2. If necessary, fall back to **last-good feature snapshots** for some features.
3. Increase STEP-UP rates instead of declining outright when confidence is lower.
4. As a last resort, run **guardrails only** and prefer soft friction (STEP-UP / QUEUE) to hard declines.

Two key properties:

* **Monotonicity**: the system only moves “down” the ladder automatically; going back up is deliberate.
* **Policy-driven**: the steps, thresholds and allowed behaviours are described as policies, not scattered conditionals.

The Degrade Ladder doesn’t change business logic by itself; it **chooses which parts of the loop are active**, so the platform stays within its SLOs without silently going crazy.

---

## 9. Boundaries and non-goals for this plane

To keep later specs and implementation aligned with this narrative, it helps to be explicit about what the Real-time Decision Loop does **not** own:

* It does **not** decide which world exists or how synthetic data are generated—that’s the Scenario Runner + Data Engine.
* It does **not** re-derive or mutate authority surfaces; it only reads them via the Identity & Entity Graph or feature jobs.
* It does **not** train models or policies; it only applies them. Training, evaluation, and registration live in the learning loop.
* It does **not** own label semantics; it emits outcomes and decision data that the Label Store and learning loop will interpret.
* It does **not** rely on any specific infrastructure product; it assumes:

  * a durable, partitioned event log,
  * a low-latency feature store,
  * and a queryable audit store.

Its job is to take a **clean, world-identified event** from the bus and, within a bounded time, turn it into **a justified, auditable action**, while keeping enough trace of its own behaviour that the rest of the platform can learn and improve.

Everything the Label & Case plane and the Learning & Evolution plane do later depends on this loop doing exactly that—and no more.