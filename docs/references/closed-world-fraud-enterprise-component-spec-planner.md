# Fraud Platform Component Spec Plan

This document defines **spec depth levels** for the fraud platform components, using the fully spec’d **data engine (segments 1A–6B)** as the benchmark for what “deep + binding” looks like.

It then:

1. Defines three spec levels (from *hard contract* to *goals & guides*).
2. Maps the 4 planes + meta-layers of the platform to those levels.
3. Highlights which specs should be prioritised in the next ~1.5 months.

Design constraints (explicit):
- **Solo builder**, with **Codex as implementer**.
- **Time-boxed**: focus on a shippable closed-loop first.
- This is a **planning guide**, not an exhaustive spec: it exists to prevent semantic drift in the few places drift would be fatal.

The intent is to **only nail down what truly needs to be nailed down**, and leave reasonable room for the implementer (Codex) to make design choices elsewhere.

---

## 1. Spec levels (using the engine as the benchmark)

Use the **data engine (1A–6B)** as the reference example of “deep/binding” documentation (contracts, state machines, RNG law, HashGates, strict validation).

Define three levels:

### Level 3 — “Hard spec” (binding contracts)

Characteristics:

* Similar to the engine’s hard-specified segments (e.g., 1A–2B style):
  * Clear inputs/outputs, IDs, schemas.
  * Explicit invariants, failure modes, and error taxonomy.
  * Testable acceptance checks (what must be true for PASS).
  * When necessary: state-wise breakdown (S0/S1/S2-style), but only where it buys determinism/auditability.
* Intended for components where a fuzzy spec would make the system fragile, unsafe, or unreplayable.

Use sparingly.

### Level 2 — “Goals & guides” (structured intent)

Characteristics:

* Similar to the engine’s lighter segments (5A–6B style):
  * Clear purpose and responsibilities.
  * High-level data shapes and a few key invariants.
  * Strong “must / must not” rules, without pinning every algorithm.
  * Clear non-goals (what the spec intentionally does not decide).
* Enough structure that Codex can implement sanely, but lots of room for internal choices.

This is the **default** level for most platform components.

### Level 1 — “Narrative & interface only” (conceptual)

Characteristics:

* Mainly intent + rough shape:
  * What the component is for.
  * Key inputs/outputs in conceptual terms.
  * A few constraints / promises.
* Internal implementation details intentionally left open.

Suitable for areas where iteration is expected, or where a deep spec is not critical for system consistency.

---

### Definition of Done per level (so Level 2 doesn’t quietly become Level 3)

**Level 3 DoD (Hard spec)**
- Interface contracts are pinned (schemas/envelopes/IDs).
- “No PASS → no read” / idempotency / replay semantics are explicit.
- Error taxonomy exists (reject vs retry vs quarantine vs partial).
- Acceptance checks are listed (what S5 validators or runtime checks must enforce).
- Minimum observability hooks are defined (what must be logged/audited).

**Level 2 DoD (Goals & guides)**
- Purpose, boundaries, and responsibilities are clear.
- Inputs/outputs are named (even if only as conceptual shapes).
- 5–15 “must/must-not” rules exist (key invariants only).
- One or two example flows (happy path + one failure path).
- Explicit non-goals prevent over-spec creep.

**Level 1 DoD (Narrative)**
- Story of the component is clear to a non-technical reader.
- Interfaces are named (even loosely).
- A few constraints/non-goals are stated.

---

## 2. Mapping spec levels to planes & components

The platform is organised into **4 planes**, plus **meta-layers**. Below, each component is assigned a target spec level, with a short rationale.

### Plane 1 — Cross-cutting rails

*(What every component must obey)*

* **Contracts / JSON-Schema authority** – **Level 2**
  * One central doc defining:
    * JSON Schema as schema authority.
    * Dataset dictionary + artefact registry expectations.
    * Compatibility/change rules at a conceptual level.

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
  * Non-goal: pinning orchestration technology.

* **Data Engine** – **already deeply spec’d (done)**
  * No further spec needed here; the engine segments are already specified.

* **Authority Surfaces (RO)** – **Level 2**
  * Define which read-only views the platform can depend on (sites, zones/DST/order, routing universes, entity graph, labels), and how they are exposed (catalog/API shape).
  * Non-goal: how the views are physically stored.

* **Ingestion Gate** – **Level 3**
  * Needs a strong contract:
    * Schema validation rules.
    * HashGate enforcement (“no PASS → no read” for engine outputs).
    * Idempotency semantics + ingestion receipts.
    * Error taxonomy (reject vs dead-letter vs retry/quarantine).
  * This is one of the few platform components that should be truly “hard-spec’d”.

> In short: **Scenario Runner** + **Authority Surfaces** are Level 2; **Ingestion Gate** is Level 3.

---

### Plane 3 — Real-time decision loop

*(What happens “during the day”)*

Components:

* **Event Bus** – **Level 2**
  * Define logical streams, keying/partitioning, ordering expectations, retention, and high-level consumer contracts.
  * Non-goal: vendor/infra specifics (Kinesis/Kafka/etc.) beyond what’s needed for semantics.

* **Online Feature Plane** – **Hybrid: Level 2 with a Level-3 core**
  * **Level-3 core** (must be pinned):
    * feature snapshot-at-decision semantics,
    * freshness/TTL guarantees categories,
    * feature availability contract (what happens when a feature is missing/stale),
    * minimal parity rules vs offline.
  * **Level 2** for the long tail of feature definitions and internal implementation choices.

* **Offline Feature Plane** – **Level 2**
  * Define parity with online:
    * same transforms, same schemas (where feasible),
    * replay semantics and dataset shapes for training/replay,
    * point-in-time correctness expectations.
  * Non-goal: exact compute engine choice.

* **Identity & Entity Graph (platform side)** – **Level 2**
  * 6A defines the entity universe; platform spec focuses on read/query semantics:
    * APIs, latency expectations, caching behaviour, and privacy boundaries.
  * Non-goal: choosing the perfect graph DB / resolution algorithm on day 1.

* **Decision Log & Audit Store** – **Level 2 with a pinned contract section**
  * Level-2 overall, but includes a **small hard contract**:
    * exactly what must be logged per decision (inputs, feature snapshot hash, model/policy versions, reasons, timings, world IDs),
    * immutability/append-only semantics,
    * minimum query guarantees.
  * Storage technology remains flexible.

* **Decision Fabric** – **Level 3 (core behaviour)**
  * Needs a hard spec for:
    * pipeline structure: guardrails → model → optional 2nd stage,
    * decision object contract (reasons/provenance),
    * degrade ladder integration rules.

* **Actions Layer** – **Level 2**
  * Specify:
    * mapping from decision → action(s),
    * idempotency rules,
    * retry behaviour,
    * what gets persisted.

* **Label Store** – **Level 2 with a pinned semantics section**
  * Level-2 overall, but includes a **small hard contract**:
    * label semantics and lifecycle/lag rules (fraud, false positive, disputes, chargebacks),
    * point-in-time training-safe views (anti-leakage),
    * linkage keys to events/flows/world IDs.

* **Case Mgmt / Workbench** – **Level 1**
  * For now:
    * conceptual description,
    * “case” data model and basic queue semantics.
  * UI and workflow detail can evolve during implementation.

* **Degrade Ladder** – **Level 2 (behaviour pinned)**
  * Define ladder steps and triggers:
    * `full pipeline → no 2nd stage → stale features → heavier STEP-UP → rules-only`
    * tie these to SLOs and observability signals.
  * Exact code structure can be left to implementation.

---

### Plane 4 — Learning & evolution loop

*(How the platform improves safely)*

Components:

* **Model Factory** – **Level 2**
  * Define:
    * training dataset contracts (which features, labels, world IDs, time windows),
    * evaluation modes (batch, replay, shadow),
    * what a “deployable bundle” contains.
  * Non-goal: dictating training framework/tooling.

* **Model/Policy Registry** – **Level 2**
  * Define:
    * bundle metadata (IDs, versions, hashes),
    * compatibility rules (with world types and feature schemas),
    * linkage back into Decision Fabric.
  * Non-goal: exact storage backend (as long as immutability is respected).

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
    * storage/transport choices (S3+KMS, DynamoDB, RDS/Aurora, streams),
    * high-level retry and failure behaviour.
  * Non-goal: full infra-as-code spec at this stage.

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

Given current constraints (single implementer + Codex, limited time), the priority is to build a **vertical slice** that proves the loop:

Engine → Ingestion → Bus → Features → Decision → Action → Labels → Train/Registry → Redeploy.

### Phase A — Must-pin now (Level-3 cores)

These are worth a more detailed, binding treatment:

* [ ] **Ingestion Gate**
* [ ] **Decision Fabric** (core contract + degrade ladder integration)
* [ ] **Online Feature Plane (Level-3 core only)**

These components are on the “hard path”: a weak spec here will hurt the entire system.

### Phase B — Goals-and-guides now (Level 2)

These should have clear goals and constraints, but don’t need full S0/S1/S2-style breakdowns:

* [ ] **Cross-cutting Rails (platform edition)**
* [ ] **Scenario Runner**
* [ ] **Authority Surfaces (RO)**
* [ ] **Offline Feature Plane**
* [ ] **Label Store** (with pinned semantics section)
* [ ] **Model Factory**
* [ ] **Model/Policy Registry**
* [ ] **Observability & Governance**
* [ ] **Identity & Entity Graph (platform usage)**
* [ ] **Decision Log & Audit Store** (with pinned contract section)
* [ ] **Actions Layer**
* [ ] **Degrade Ladder** (behaviour pinned)

These can mostly be short docs: purpose, boundaries, key shapes, strong “must/must not” statements, and a few critical invariants.

### Phase C — Light / narrative only for now (Level 1)

These can stay at conceptual-level until the core loop is in place:

* [ ] **Case Mgmt / Workbench** (goals + rough data model)
* [ ] **Detailed Analytics/Query layer** (later)
* [ ] **Fine-grained policy distribution runtime** (initially: “Decision Fabric uses Registry API”)
* [ ] **Experiment manager** (keep inside Model Factory narrative initially)

---

## 4. Suggested build order (dependency order)

If you want a clean execution order (to avoid circular design), a sensible path is:

1) Cross-cutting rails (IDs, PASS rules, security posture)
2) Ingestion Gate contract + receipts
3) Canonical event envelope(s) for the bus
4) Decision Log contract (what must be captured at decision time)
5) Online Feature Plane Level-3 core (snapshot + freshness semantics)
6) Decision Fabric Level-3 core (decision object + degrade ladder rules)
7) Actions + Label semantics (how outcomes are represented and fed back)
8) Model bundle identity (Factory ↔ Registry ↔ Decision Fabric handshake)
9) Everything else as Level-2/Level-1 expansions

---

### Alignment with engine style

This plan matches the pattern already present in the engine:

* Some segments (e.g. 1A–2B) are **deeply spec’d**.
* Others (5A–6B) are **“goals & guides”** with targeted detail where necessary.

The platform should follow the same pattern:

* **Deep spec where rigidity and safety are essential** (Ingestion, core Decisioning, core Online Features).
* **Guiding spec where implementation detail can evolve** without breaking the conceptual model.

This is intended to be a **living planning doc**, not a spec in itself. As components are actually specified, they can reference this document to justify how deep (or light) they go.
