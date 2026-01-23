# Component Spec Planner — Dependency Map and No-Circles Build Order

*Status: Draft (Informative)*
*Effective date: 2026-01-03*

This document defines **spec dependencies between platform components** so we can plan spec creation without moving in circles.

It answers two questions:

1. **Dependency Map:** When authoring a component spec, what other component/interface artefacts must already exist?
2. **No-Circles Build Order:** What is the recommended progression for spec creation to avoid circular design?

This is a **planning document** (informative). Binding requirements are defined in the relevant component specs and in Platform Rails.

---

## 0) Definitions

### 0.1 Hard vs soft dependencies

* **Hard dependency:** Must exist (pinned contracts/interfaces) before writing a robust spec/implementation.
* **Soft dependency:** Helpful but can be stubbed with placeholders and tightened later.

### 0.2 “Depends on” means interface dependencies

A component “depends on” another component only to the extent that it needs:

* the other component’s **contracts** (schemas),
* **authority surfaces** (catalogues, registries, gate maps),
* and **identity/lineage rules** to interoperate.

### 0.3 Global prerequisites

Two artefact families are “global prerequisites” and are treated as dependencies for most components:

* **Cross-cutting Rails**
  Identity tuple, canonical envelope, receipts, “no PASS → no read”, schema authority, degrade marking.

* **Data Engine Interface Pack**
  Engine invocation surface, output catalogue, gate map, output locator shape, gate receipt shape.

---

## 1) Platform dependency spine (minimum chain)

This is the minimum ordering spine that prevents circular design. Everything else can be parallelised around it.

```
Data Engine (sealed truth)
   |
   v
Cross-cutting Rails (platform invariants)
   |
   v
Scenario Runner (run anchoring + discovery pins)
   |
   v
Ingestion Gate (first hard boundary: validate + admit/quarantine)
   |
   v
Canonical Event Payload Contracts (shared language)
   |
   v
Event Bus / Stream Plane
   |
   v
Online Feature Plane  ---> Decision Fabric ---> Actioning
   |                      |                 |
   v                      v                 v
Offline Feature Plane   Decision Log     Label Store / Case
   |
   v
Model Factory ---> Model/Policy Registry ---> feeds back into Decision Fabric
```

Observability & Governance spans all components and consumes their receipts/telemetry.

---

## 2) Component dependency index (what each spec needs)

### Plane 2 — Control & Ingress

#### Scenario Runner

* **Hard deps:** Cross-cutting Rails + Data Engine Interface Pack
* **Soft deps:** none
* **Provides:** Run Record + Run Facts View (“active run(s)” discovery + pins)

#### Authority Surfaces (RO plane)

* **Hard deps:** Cross-cutting Rails + Data Engine Interface Pack (to know what surfaces exist, how they’re keyed/gated)
* **Soft deps:** Feature plane query patterns
* **Provides:** stable read-only joins and “law book” surfaces for downstream

#### Ingestion Gate

* **Hard deps:**

  * Cross-cutting Rails (canonical envelope, receipts, idempotency/conflict rules)
  * Data Engine Interface Pack (gate verification semantics + catalogue)
  * Scenario Runner (Run Facts pins: which run/world is active and what to ingest)
* **Soft deps:** Event Bus naming/partitioning (can be finalised later)
* **Provides:** admitted main-plane stream + quarantine + ingestion receipts

---

### Plane 3 — Real-time Decision Loop

#### Canonical Event Payload Contracts (payload schemas)

* **Hard deps:** Cross-cutting Rails (envelope + identity tuple)
* **Soft deps:** none
* **Provides:** shared event “language” used by bus/features/decision/action/labels

#### Event Bus / Stream Plane

* **Hard deps:** Rails envelope + canonical payload contracts + ingestion outputs
* **Soft deps:** Online Feature details (not required)
* **Provides:** durable stream, partitioning/replay semantics

#### Online Feature Plane

* **Hard deps:**

  * Event Bus + canonical payload contracts
  * Rails (identity, freshness and degrade marking rules)
  * RO Authority Surfaces / Entity Graph if features join on them
* **Soft deps:** Decision Fabric’s exact feature list (core can be defined first)
* **Provides:** feature snapshot contracts + freshness/degrade behaviour

#### Decision Fabric

* **Hard deps:**

  * Feature snapshot contracts (input requirements, missing/stale rules)
  * Model/Policy Registry contract (how to fetch current model/policy bundle)
  * Degrade ladder rules (what fallback modes are allowed)
* **Soft deps:** Label Store (Decision Fabric emits decisions; it does not need labels to exist)
* **Provides:** decision object contract + reasons + provenance

#### Decision Log / Audit Store

* **Hard deps:** Decision Fabric decision object contract
* **Soft deps:** none
* **Provides:** immutable audit/replay trail used by learning + governance

#### Actioning Layer

* **Hard deps:** Decision Fabric output contract + idempotency/receipt posture
* **Soft deps:** Case Mgmt + Label Store (depends on whether you open cases immediately)
* **Provides:** side-effect events + outcome events

#### Label Store + Case

* **Hard deps:** action/outcome event contracts + join keys back to decision/action + label semantics
* **Soft deps:** Model Factory (labels can exist before training)
* **Provides:** training-safe labels + lag/lifecycle rules

---

### Plane 4 — Learning & Evolution

#### Offline Feature Plane + Parity

* **Hard deps:** event stream contracts + label semantics + parity rules vs online features
* **Provides:** training datasets and parity checks (no leakage)

#### Model Factory

* **Hard deps:** offline feature datasets + label store semantics
* **Soft deps:** Decision Fabric (for compatibility checks only)
* **Provides:** model bundles + evaluation artefacts + promotion gates

#### Model/Policy Registry

* **Hard deps:** model bundle contract + decision fabric lookup/consumption rules
* **Provides:** “current model/policy” pointer for Decision Fabric

---

### Meta layers

#### Observability & Governance

* **Hard deps:** Cross-cutting Rails (telemetry requirements, receipts, degrade interaction)
* **Soft deps:** none (can be specced in parallel; it consumes everything)

#### Run / Operate Plane

* **Hard deps:** none (tooling choices are Level-2)
* **Soft deps:** everything (it stitches components together operationally)

---

## 3) Recommended no-circles progression (spec creation)

You’ve completed:

1. Data Engine (spec + interface pack)
2. Cross-cutting Rails
3. Scenario Runner

Next recommended order:

4. **Ingestion Gate** (hard boundary; unlocks downstream)
5. **Canonical Event Payload Contracts** (shared language)
6. **Event Bus / Stream Plane**
7. **Online Feature Plane (core)**
8. **Decision Fabric (core)**
9. **Decision Log / Actioning**
10. **Label Store + Case**
11. **Offline Feature Plane + Parity**
12. **Model Factory + Model/Policy Registry**

---

## 4) Parallel spec tracks (safe concurrency plan)

Once Rails + Engine Interface Pack are pinned (they are), you can spec in parallel:

* **Track A:** Ingestion Gate + RO Authority Surfaces
* **Track B:** Canonical Event Payload Contracts + Event Bus
* **Track C:** Online Feature Plane (core) + Decision Fabric (core) + Decision Log
* **Track D:** Label Store semantics + Offline Feature parity contract

Then start **Model Factory + Registry** once Track D exists.

---

## 5) Anti-circle rule of thumb

If component X needs a contract from component Y to define its *input/output* shape, then **Y must be pinned first**, unless you explicitly mark that dependency as a placeholder with a TODO and a migration plan.
