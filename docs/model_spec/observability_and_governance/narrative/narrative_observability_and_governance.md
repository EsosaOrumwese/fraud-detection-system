# Observability & Governance — how we watch, trust, and change the system

The rest of the platform is about **doing things**: generating worlds, taking events in, computing features, making decisions, opening cases, training models.

The Observability & Governance plane is about **knowing what’s really happening** and **changing it safely**.

It answers questions like:

* “Is the system healthy right now?”
* “Are we within our latency and error budgets?”
* “Are our data and features still what we think they are?”
* “Did that change we just made actually improve things, or did it quietly make them worse?”
* “If something goes wrong, can we stop the bleeding and reconstruct what we did?”

It doesn’t live in one box. It wraps the entire platform and engine like a **control shell**: defining the rules everyone must obey, watching the golden signals, and enforcing discipline around change.

At its core, it has four big ideas:

* **Cross-cutting rails**: contracts, identity, validation, and security.
* **Golden signals & data health**: metrics for infra, data, and ML.
* **Deterministic replay & DR**: the ability to rewind and rebuild.
* **Change control & kill switches**: how you evolve without tearing the system apart.

---

## 1. Cross-cutting rails — the laws of the universe

Every component in the engine and platform sits inside a shared set of laws. Observability & Governance is where these laws are written down and enforced.

### Contracts & schemas

* **JSON Schema is authority** for messages and tables.
* Dataset dictionaries and artefact registries define:

  * what fields exist,
  * how they are typed,
  * and which components own them.

This means monitoring can ask simple questions like:

> “Are we seeing messages that don’t conform to the agreed contracts?”

…and treat any violation as a first-class incident.

### Identity & lineage

Every significant artefact and event is tagged with:

* `parameter_hash` — which parameter/policy pack is in play,
* `manifest_fingerprint` — which world the data belongs to,
* `seed` — which stochastic realisation we’re in,
* `scenario_id` — which scenario this traffic belongs to.

Decisions and models also carry:

* model/policy version IDs,
* feature snapshot IDs,
* and correlation IDs.

This isn’t just bookkeeping. It allows observability to slice metrics by world, run, model version, and scenario, answering:

* “Is this model misbehaving in one specific world?”
* “Is scenario X much spikier than scenario Y?”

### Validation & HashGates

The engine uses **HashGates** at segment level:

* each segment (1A…6B) publishes a validation bundle + `_passed.flag_*`,
* the platform obeys a simple rule: **“no PASS → no read”.**

On the platform side, Observability & Governance:

* defines which components must verify which HashGates before reading,
* surfaces failures as critical alerts: “we are about to ingest from a world that hasn’t passed validation”.

This is governance encoded as code and policy, not a suggestion.

### Security & privacy

Even though worlds can be synthetic, the platform behaves as if they were real:

* least-privilege access for humans and services,
* encryption in transit and at rest,
* tokenisation/redaction on ingest,
* retention policies per table,
* audit trails for who accessed what and when.

These rules live alongside the contracts and identity, as part of “how we are allowed to operate this system”.

---

## 2. Golden signals — seeing if the system is healthy

Observability doesn’t try to monitor “everything equally”. It focuses on **golden signals**: a small number of metrics per plane that tell you whether things are fundamentally OK.

### For the Control & Ingress plane

* Ingestion latency (time from engine event to bus publish).
* Schema error rate (events rejected at the gate).
* HashGate failures (attempts to read from non-PASS worlds).
* Idempotency failures (duplicates beyond expected patterns).

### For the Real-time Decision Loop

* Decision latency p50/p95/p99 (end-to-end and per stage).
* Error rates (per endpoint, per world).
* Throughput (events/sec, decisions/sec) and saturation (queue depths).
* Decision mix: APPROVE / STEP-UP / DECLINE / QUEUE, broken down by merchant, segment, scenario.
* Feature freshness (how many feature reads are beyond TTL).

### For the Label & Case plane

* Label arrival lags (distribution of time between decision and label).
* Label state distributions (how many flows are still “unknown”, “suspected”, “confirmed”).
* Case queue depths and case ageing.
* Consistency rates between case outcomes and labels.

### For the Learning & Evolution plane

* Training job success rates and durations.
* Data-volume anomalies in training datasets.
* Train/serve feature distribution differences (drift).
* Model performance metrics over time (precision/recall, cost).

All of these metrics are tagged by **world, scenario, and model/version IDs**, so you can drill down.

---

## 3. Data health — making contracts measurable

Observability & Governance isn’t just about latency and errors; it’s also about **what the data looks like**.

This includes:

* schema compliance (counts of violations by field/table),
* null-rate and missingness trends per feature,
* distribution shifts (e.g. mean/variance of transaction amount, per merchant segment),
* outlier rates,
* lineage mismatches (events or rows whose world IDs don’t match the surfaces they claim to belong to).

Some of these can be automated:

* **schema checks** can run continuously at ingest,
* **distribution checks** can run on rolling windows,
* **synthetic probes** can inject known patterns into the engine to test whether the platform still responds as expected.

Governance defines which deviations are:

* informational (log and watch),
* warning-level (page the team),
* error-level (trigger degrade modes or halt certain operations).

---

## 4. Deterministic replay & disaster recovery

One of the core promises of this architecture is:

> “We can rebuild what we did.”

That’s what deterministic replay and DR are for.

Observability & Governance ensures that:

* raw event streams are stored in a way that allows **world-scoped replays** (e.g. “replay world F, seed S, scenario SC for day D”),
* downstream components (features, decisions, labels) are deterministic **functions** of those streams plus their configs and models,
* key configs (models, policies, feature definitions) are versioned and attached to runs.

This makes two things possible:

1. **Investigation:**

   * For a given decision or cluster of decisions, you can replay the world to see:

     * the events as they were,
     * the features as they were,
     * the model/policy as it was,
     * and what would happen under a new candidate model.

2. **Recovery:**

   * If a feature store is corrupted or a deployment goes wrong, you can:

     * restore from snapshots,
     * or replay from event streams to rebuild features and decisions.

Governance defines:

* which components must be replayable,
* how long raw events are retained,
* and what “acceptable drift” is between replay and primary runs.

---

## 5. Change control — evolving without breaking

Change is where systems most often fail. Observability & Governance defines **how changes are allowed to happen**.

Typical patterns include:

* **Contract tests in CI**

  * Schemas, dataset dictionaries, and APIs are tested against:

    * backward compatibility expectations,
    * invariants (e.g. no key drops, no silently changed semantics).
* **Dual-read / dual-write** modes for risky migrations

  * For example:

    * write to old and new feature stores,
    * read from both and compare,
    * only switch the primary once parity is proven.
* **Feature flags / toggles**

  * used for enabling new branches (e.g. a new guardrail, a new model stage) without redeploying everything.

On the model/policy side, this ties directly into the Learning & Evolution plane:

* new models and policies must go through **shadow → canary → ramp**,
* promotion and rollback are driven by **policy artefacts** in the registry, not by ad-hoc code pushes.

Governance sets the rules for:

* who can approve a change,
* what evidence is required (metrics, tests, validations),
* and what steps must be followed to roll out or roll back safely.

---

## 6. Incidents, kill switches, and degrade modes

Even with good tests, things go wrong. Observability & Governance also covers **what to do in an incident**.

There are two sides:

1. **Detection**

   * Alerts tied to SLO breaches and data-health anomalies:

     * e.g. “decision latency p99 > 300ms for N minutes”,
     * “schema error rate above X%”,
     * “false positive rate spike in merchant segment S”.

2. **Response**

   * **Kill switches**:

     * turn off the second stage,
     * freeze a risky rule,
     * pause promotion of a model,
     * temporarily route a class of traffic to guardrails-only.
   * **Degrade Ladder activation**:

     * observability feeds its signals into the decision fabric’s degrade ladder,
     * making sure the platform moves to simpler modes in a controlled sequence rather than failing catastrophically.
   * **Playbooks**:

     * documented steps for common failures (feature-store outage, bad model deployment, label corruption, etc.).

Underneath, DR and replay capabilities support **postmortems**:

* you can rewind and see exactly what happened,
* compare “actual” vs “what should have happened”,
* and feed those learnings back into contracts and policies.

---

## 7. Governance of synthetic vs real

This platform is built to run on **synthetic worlds** as well as real traffic. Governance has to cover both.

For synthetic runs:

* the engine’s HashGates are king:

  * worlds must pass 1A–6B validations before ingest,
  * Label Store can be seeded from 6B’s truth and bank-view surfaces,
  * corridors (e.g. expected fraud rates, loss levels) can be defined and probed routinely.
* Observability can use **corridor checks**:

  * comparing observed behaviour (fraud/decline/step-up rates) against expected ranges for a given synthetic scenario.

For real runs:

* external label sources are allowed, but they’re still ingested through the same Label & Case plane and subject to schema/lineage contracts.
* privacy, compliance, and audit requirements become stricter, but the **same machinery** (HashGates, identities, logs, replay) can be used to demonstrate behaviour.

The principle is:

> Synthetic runs are governed at least as strictly as real ones, so that the same platform can safely serve both.

---

## 8. Boundaries and non-goals

To keep future specs and implementations anchored to this narrative, it’s useful to spell out what Observability & Governance **does not** try to do:

* It does **not** own business decisions; it observes and constrains them.
* It does **not** define the behaviour of the engine or the platform components; it defines **how they must expose themselves** (metrics, logs, IDs, contracts) and **how changes are allowed to happen**.
* It does **not** replace monitoring inside services; it gives a **shared language and set of expectations** for all of them.
* It does **not** assume any particular vendor’s monitoring stack; it assumes:

  * metrics can be collected and tagged,
  * logs can be correlated by IDs,
  * alerts and playbooks can be wired into an on-call process.

Its job is to make sure that:

* you can see what’s going on,
* you can trust that what you’re seeing is consistent,
* you can change the system without guessing,
* and, if something goes wrong, you can both **stop it quickly** and **understand it later**.

Every other plane leans on this one to keep it honest.