# Fraud Platform Component Spec Plan

This document defines **spec depth levels** for the fraud platform components, using the fully spec’d **data engine (segments 1A–6B)** as a benchmark.

It then:

1. Defines three spec levels (from *hard contract* to *goals & guides*).
2. Maps the 4 planes + meta-layers of the platform to those levels.
3. Highlights which specs should be prioritised in the next ~1.5 months.

The intent is to **only nail down what truly needs to be nailed down**, and leave reasonable room for the implementer (Codex) to make design choices elsewhere.

---

## 1. Spec levels (using the engine as a benchmark)

Treat the **entire data engine (1A–6B)** as **depth = 1.0** in terms of specification effort and complexity (contracts, state machines, RNG, HashGates, etc.).

Define three levels:

### Level 3 — “Hard spec” (engine-like)

Characteristics:

* Similar to 1A–2B style:

  * Clear inputs/outputs, IDs, schemas.
  * Explicit invariants and failure modes.
  * Possibly state-wise breakdown (S0/S1/S2-style).
* Intended for components where a fuzzy spec would make the system fragile or hard to reason about.

Use sparingly.

### Level 2 — “Goals & guides”

Characteristics:

* Similar to the *lighter* parts of 5A–6B:

  * Clear purpose and responsibilities.
  * High-level data shapes and a few key invariants.
  * “Must / must not” rules, but not every algorithm spelled out.
* Enough structure that Codex can implement sanely, but lots of room for internal choices.

This is the **default** level for most platform components.

### Level 1 — “Narrative & interface only”

Characteristics:

* Mainly intent + rough shape:

  * What the component is for.
  * Key inputs/outputs in conceptual terms.
  * A few constraints.
* Internal implementation details intentionally left open.

Suitable for areas where experimentation and iteration are expected, or where a deep spec is not critical for consistency.

---

## 2. Mapping spec levels to planes & components

The platform is organised into **4 planes**, plus **meta-layers**. Below, each component is assigned a target spec level, with a short rationale.

### Plane 1 — Cross-cutting rails

*(What every component must obey)*

* **Contracts / JSON-Schema authority** – **Level 2**

  * One central document defining:

    * JSON Schema as schema authority.
    * Dataset dictionary + artefact registry expectations.

* **Lineage & validation (“no PASS → no read”)** – **Level 2**

  * Define how segment-level HashGates are verified and respected platform-wide.

* **Deterministic replay (parameter_hash + manifest_fingerprint + seed + scenario_id)** – **Level 2**

  * Specify how these IDs propagate and are logged.

* **Privacy/security + SLOs/observability** – **Level 2**

  * High-level requirements for RBAC, KMS, retention, and latency/error SLOs.

> Deliverable: **one “Cross-cutting Rails” spec** at Level 2 that all components reference.

---

### Plane 2 — Control & ingress

*(How a run starts, and how data is admitted)*

Components:

* **Scenario Runner** – **Level 2**

  * Define how runs are described:

    * world (`manifest_fingerprint`),
    * parameter pack (`parameter_hash`),
    * seed(s), scenario set, time horizon.
  * Define how it triggers engine runs and tracks their state (high-level).

* **Data Engine** – **already Level 3 (done)**

  * No further spec needed here; the engine segments are already deeply specified.

* **Authority Surfaces (RO)** – **Level 2**

  * Define which read-only views the platform can depend on (e.g., sites, zones, routing universes, entity graph, labels), and how they are exposed (catalog/API shape).

* **Ingestion Gate** – **Level 3**

  * Needs a strong contract:

    * Schema validation rules.
    * HashGate enforcement (“no PASS → no read” for engine outputs).
    * Idempotency semantics.
    * Error taxonomy (reject vs dead-letter vs retry).

> In short: **Scenario Runner** + **Authority Surfaces** get Level 2; **Ingestion Gate** is one of the few platform components that should be spec’d at **Level 3**.

---

### Plane 3 — Real-time decision loop

*(What happens “during the day”)*

Components:

* **Event Bus** – **Level 2**

  * Define logical streams, keying, ordering guarantees, and high-level consumer contracts.

* **Online Feature Plane** – **Hybrid: Level 2/3**

  * **Core contracts** (identity keying, a small core set of feature families, freshness/SLO and consistency guarantees) warrant **Level 3**.
  * The long tail of specific features can be described at **Level 2**.

* **Offline Feature Plane** – **Level 2**

  * Define parity with online:

    * Same transforms, same schemas.
    * Replay semantics, dataset shapes for training/replay.
  * Implementation details can be left to Codex.

* **Identity & Entity Graph (platform side)** – **Level 2**

  * 6A already defines the graph structure.
  * Platform spec focuses on read/query semantics:

    * APIs, latency expectations, cache behaviour.

* **Decision Log & Audit Store** – **Level 2**

  * Define exactly what must be logged per decision:

    * inputs, features snapshot hash, model/policy versions, reasons, timings, world IDs.
  * Storage technology can remain flexible.

* **Decision Fabric** – **Level 3 (core behaviour)**

  * Needs an engine-like spec for:

    * pipeline structure: guardrails → model → optional 2nd stage.
    * decision object contract.
    * integration with degrade ladder.
    * provenance expectations (what must be attached to every decision).

* **Actions Layer** – **Level 2**

  * Specify:

    * mapping from decision → action(s),
    * idempotency rules,
    * retry behaviour,
    * what gets persisted.

* **Label Store** – **Level 2**

  * Define:

    * label object shapes,
    * how labels link to flows/events/world IDs,
    * lifecycle/lag semantics (fraud, false positive, disputes, chargebacks),
    * access patterns for training & evaluation.

* **Case Mgmt / Workbench** – **Level 1**

  * For now:

    * conceptual description,
    * “case” data model and basic queue semantics.
  * UI and workflow detail can evolve during implementation.

* **Degrade Ladder** – **Level 2**

  * Define the ladder steps and triggers:

    * e.g.,
      `full pipeline → no 2nd stage → stale features → STEP-UP heavier → rules-only`
    * tie these to SLOs and observability signals.
  * Exact code structure can be left to implementation.

---

### Plane 4 — Learning & evolution loop

*(How the platform improves safely)*

Components:

* **Model Factory** – **Level 2**

  * Define:

    * training dataset contracts (which features, labels, world IDs, time windows),
    * evaluation modes (batch, replay, A/B/shadow),
    * what a “deployable bundle” contains.

* **Model/Policy Registry** – **Level 2**

  * Define:

    * bundle metadata (IDs, versions, hashes),
    * compatibility rules (with world types and feature schemas),
    * linkage back into Decision Fabric.

* **Feedback wiring (labels/metrics → training/monitoring)** – **Level 1–2 (light)**

  * One small spec that clarifies:

    * which labels and metrics go to Model Factory,
    * how they are keyed by world/run/model.

---

### Meta-layers

#### Run / Operate Plane

*(Orchestration, storage, bus, secrets, registries)*

* **Level 2**

  * One platform-ops spec describing:

    * orchestration (Airflow/MWAA → ECS tasks),
    * storage/transport choices (S3+KMS, DynamoDB, RDS/Aurora, Kinesis),
    * high-level retry and failure behaviour.

#### Observability & Governance

* **Level 2**, with small pockets where **Level 3**-style precision is useful (e.g. HashGate verification process).
* Define:

  * golden signals per plane (ingestion, features, decision, actions, model factory),
  * how SLO breaches interact with the Degrade Ladder,
  * CI contract tests and schema-change rules,
  * replay/DR strategy using manifests and fingerprints,
  * audit requirements (for decisions, models, policy changes).

---

## 3. Practical focus for the next ~1.5 months

Given current constraints (single implementer + Codex, limited time), the priority is:

### Must-spec (harder) now — **Level 3**

These are worth a more detailed, engine-like treatment:

* [ ] **Ingestion Gate**
* [ ] **Decision Fabric** (core contract + degrade ladder integration)
* [ ] **Online Feature Plane** (core feature families, keying, SLO & consistency rules)

These components are on the “hard path”: a weak spec here will hurt the entire system.

---

### Goals-and-guides spec now — **Level 2**

These should have clear goals and constraints, but don’t need full S0/S1/S2-style breakdowns:

* [ ] **Cross-cutting Rails (platform edition)**
* [ ] **Scenario Runner**
* [ ] **Authority Surfaces (RO)**
* [ ] **Offline Feature Plane**
* [ ] **Label Store**
* [ ] **Model Factory**
* [ ] **Model/Policy Registry**
* [ ] **Observability & Governance**
* [ ] **Identity & Entity Graph (platform usage)**
* [ ] **Decision Log & Audit Store**
* [ ] **Actions Layer**

These can mostly be 4–10 page docs each: purpose, responsibilities, key shapes, strong “must/must not” statements, and a few critical invariants.

---

### Light / narrative only for now — **Level 1**

These can stay at conceptual-level until the core loop is in place:

* [ ] **Case Mgmt / Workbench** (goals + rough data model)
* [ ] **Detailed Analytics/Query layer** (e.g. “we’ll use Athena/Trino later”)
* [ ] **Fine-grained policy distribution runtime** (for now: “Decision Fabric uses the Registry API”)
* [ ] **Experiment manager** (keep inside Model Factory narrative initially)

---

### Alignment with engine style

This plan matches the pattern already present in the engine:

* Some segments (e.g. 1A–2B) are **deeply spec’d**.
* Others (5A–6B) are **“goals & guides”** with targeted detail where necessary.

The platform should follow the same pattern:

* **Deep spec where rigidity and safety are essential** (Ingestion, core Decisioning, core Online Features).
* **Guiding spec where implementation detail can evolve** without breaking the conceptual model.

This is intended to be a **living planning doc**, not a spec in itself. As components are actually specified, they can reference this document to justify how deep (or light) they go.