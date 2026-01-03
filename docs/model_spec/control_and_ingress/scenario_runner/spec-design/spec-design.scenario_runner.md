# Conceptual Document Plan — Scenario Runner (SR)

## 0) Document metadata

### 0.1 Document header

* **Title:** *Scenario Runner — Conceptual Roadmap (Modular Breakdown + Contract Intent)*
* **Component:** Control & Ingress / Scenario Runner
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final (choose one)
* **Version:** v0.x (increment on substantive changes)
* **Date (UTC):** `<YYYY-MM-DD>`
* **Owner:** `<you>`
* **Implementer:** Coding agent (source-of-truth will be the eventual specs + contract schemas)

### 0.2 Purpose of this document

* Provide a **single, coherent conceptual direction** for Scenario Runner (SR) before writing specs.
* Enumerate the **questions SR must answer** (by module + contracts) to guarantee:

  * reproducibility / replay
  * cross-component interoperability
  * auditability under retries/failures
  * clean authority boundaries
* Explicitly separate:

  * **design decisions that must be pinned** (spec-level)
  * **implementation freedoms** left to the coding agent

### 0.3 Audience and prerequisites

* **Primary readers:** you (architect/spec author), coding agent (implementer)
* **Secondary readers:** reviewers of Control & Ingress, downstream component owners
* **Prerequisites (assumed known):**

  * Platform “rails” identity concepts (run/world pins, lineage, PASS/no-read)
  * Data Engine treated as a black box with an interface pack
  * Your repo conventions for addressing artifacts (e.g., `fingerprint={manifest_fingerprint}` paths)

### 0.4 How to use this document

* Use as the **roadmap** for authoring the SR spec set (SR1–SR5) and the SR contract pack(s).
* This doc is **not** the source of truth for machine-checkable shapes; those live in `contracts/`.
* When drafting specs, each “question” here should be either:

  * answered as a **binding decision** in SR3/SR4/SR5, or
  * explicitly marked as **implementation freedom**.

### 0.5 Non-binding disclaimer

* This document is **conceptual** and does not define enforceable behaviour on its own.
* Any normative language (MUST/SHALL/SHOULD) here is **informal guidance** until captured in:

  * SR spec docs (binding sections), and/or
  * contract schemas (machine-checkable)

### 0.6 Scope and non-scope

* **In scope:** SR modular breakdown, responsibilities, boundary contracts intent, artifact families, spec mapping.
* **Out of scope:** implementation details (scheduler tech, code layout), feature computation, ingestion validation, decisioning, label writing, model training.

### 0.7 Repo placement and related artifacts

* **Proposed location:**
  `docs/model_spec/control_and_ingress/scenario_runner/CONCEPTUAL.md` (or `README.md` if you prefer it as the entry point)
* **Related docs (eventual):**

  * `specs/SR1_...md` through `specs/SR5_...md`
  * `contracts/sr_public_contracts_v1.schema.json`
  * `contracts/sr_engine_boundary_v1.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Scenario Runner exists

Scenario Runner (SR) is the platform’s **run-orchestrator + run-ledger**. Its job is to take a *scenario intent* and produce an **auditable, replayable run** whose outputs can be safely consumed by downstream components.

SR turns:

* **Scenario intent**

  * what to simulate (scenario definition / scenario class)
  * when to simulate (window/cadence, or explicit window key)
  * operational posture (SLA class / run mode)

* **World pins**

  * `parameter_hash`
  * `manifest_fingerprint` (or a deterministic selection policy if selection is allowed)

* **Run identity policy**

  * `scenario_id`, `run_id` (and any seed policy SR is responsible for)

into:

* an **executed run** (either engine invoked or reuse of existing engine outputs)
* **SR-owned ledger artifacts** (canonical run record + join surfaces)
* **readiness signals** that allow downstream components to proceed **without guessing**.

**SR exists to make the platform joinable and correct under:**

* retries / duplicates
* restarts
* replay and audit requests
* multiple downstream consumers that require consistent referencing.

---

### 1.2 SR’s role in the platform “day-in-the-life”

At a high level, SR sits at the top of the execution plane:

1. SR receives a **Run Request** (scenario intent + pins + identity policy).
2. SR **pins** the run context (writes the stable identifiers / joins).
3. SR **invokes** the Data Engine (or **reuses** a prior engine output set when permitted).
4. SR **verifies** required engine readiness gates (PASS artifacts).
5. SR **registers** the run facts (pins + output refs) as a canonical view.
6. SR **emits** a READY/dispatch signal (or records failure/quarantine) so downstream can proceed.
7. Downstream (ingestion, decision loop, observability, etc.) consumes SR artifacts/signals as the **system-of-record** for “what run is this and where are its authoritative outputs?”

SR is not “the pipeline”. SR is the **conductor + ledger** that makes the rest of the platform safe to operate.

---

### 1.3 Authority: what SR is the system-of-record for

SR is authoritative for:

* **Run identity and lineage anchoring**

  * the canonical `scenario_id` / `run_id` association to world pins
* **Run intent vs run outcome**

  * what was planned (`run_plan`) vs what occurred (`run_record`)
* **Run readiness**

  * whether a run is considered READY (and why)
* **Downstream join surfaces**

  * the canonical “pins + refs” table/view (`run_facts_view`)
* **Run lifecycle status**

  * open/closed/failed/quarantined (with reason).

SR is **not** authoritative for the content of engine outputs themselves; it is authoritative for **how those outputs are referenced, verified, and declared ready**.

---

### 1.4 What SR explicitly is NOT responsible for (non-scope)

To avoid “SR does everything” creep, SR does **not**:

* compute online/offline features
* validate or clean event payloads (that’s Ingestion Gate’s job)
* perform real-time decisions or actioning
* write labels, cases, or truth sets
* train models or manage model rollouts (beyond recording which versions were used if provided)
* implement business fraud policy logic (SR is orchestration, not domain logic)

SR may trigger or signal these systems, but does not own their internal semantics.

---

### 1.5 What SR must enable for other components

Other components must be able to rely on SR for:

* **Deterministic joinability**

  * every downstream artifact/event can be tied back to `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* **Safe progression**

  * downstream can gate on SR readiness without reading partial/invalid worlds
* **Audit & replay**

  * a run can be explained and repeated (or reused) from the ledger artifacts
* **Operational correctness**

  * retries don’t duplicate side effects; failures are recorded and never hidden.

---

### 1.6 Interfaces in one sentence (for orientation)

* **Upstream:** “Tell SR what scenario to run, with which pins, under which identity policy.”
* **Downstream:** “Use SR’s ledger and READY signals as the canonical truth for *what run this is* and *where to read from*.”
* **Engine boundary:** “SR calls the engine with pinned identity and receives completion evidence + PASS gates.”

---

## 2) Core invariants (the “laws” SR must never break)

> These are **non-negotiable behaviours**. If any later spec text or implementation contradicts these, it’s a bug.

### 2.1 Identity and lineage are always present

* Every SR-owned artifact/signal MUST carry the canonical identity pins:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* If SR introduces any window/time key, it MUST be present everywhere the identity pins are present.

**Why this matters:** downstream joins and replay/audit depend on it.

---

### 2.2 SR never lies about readiness

* SR MUST NOT declare a run “READY” unless the required readiness evidence exists and is verifiable (per SR’s defined gate rules).
* SR MUST NOT “best-effort READY” (no greenwashing).

**Why this matters:** prevents downstream from reading partial/invalid worlds.

---

### 2.3 Readiness is monotonic

* Once SR declares a run READY, that READY status MUST NOT be withdrawn or flipped to FAILED.
* Corrections happen by creating a **new run** (new `run_id`), not mutating history.

**Why this matters:** stable downstream behaviour and auditability.

---

### 2.4 The run ledger is the system-of-record and is audit-safe

* SR MUST produce an immutable/audit-safe account of:

  * what was intended (plan)
  * what happened (record)
  * what should be read (facts view)
  * final outcome (status)
* Mutations, if any, must be strictly controlled and traceable (append-only or versioned transitions).

**Why this matters:** replay/debugging must work without tribal knowledge.

---

### 2.5 Idempotency: “same request twice” never duplicates side-effects

* Submitting the same logical Run Request twice MUST result in:

  * no duplicate engine invocations (if reuse is expected), or
  * no duplicate downstream dispatch / READY signals,
  * and no duplicate ledger side-effects beyond safe, repeatable updates.

**Why this matters:** correctness under retries, restarts, and duplicate deliveries.

---

### 2.6 Replay behaviour is explainable from the ledger

* SR MUST support the platform’s replay posture by making replay outcomes derivable from:

  * pins + mode + recorded evidence in the ledger
* SR MUST NOT depend on hidden state (“whatever was in memory last time”).

**Why this matters:** reproducibility and incident response.

---

### 2.7 No hidden time dependence

* SR MUST NOT silently depend on “now” to determine meaning of a run (window selection, manifest selection, etc.)
* If time influences behaviour, it must be represented explicitly in inputs/pins/records.

**Why this matters:** prevents drift between local vs deployed runs and across replays.

---

### 2.8 Authority boundaries are respected

* SR is authoritative for **run identity, readiness, and join surfaces**.
* SR is NOT authoritative for engine content and MUST treat engine outputs as external artifacts verified by gates/evidence.

**Why this matters:** prevents SR from re-deriving or mutating upstream truths.

---

### 2.9 Deterministic selection if SR is allowed to “choose”

* If SR may select a `manifest_fingerprint` (or any “latest” concept), the selection rule MUST be deterministic and recorded in the ledger.

**Why this matters:** otherwise two deployments can pick different worlds for the “same” run.

---

### 2.10 Contract and version discipline

* SR artifacts/signals MUST be attributable to a contract target/version (so consumers validate the same way).
* SR MUST NOT emit ambiguous shapes (“close enough JSON”) that require consumers to guess.

**Why this matters:** prevents schema drift across components.

---

## 3) Terminology and key objects

> This section defines the nouns used throughout the SR conceptual roadmap. These are *conceptual definitions*; the exact fields/shapes land in SR2 + the contract schemas.

### 3.1 Scenario

A **scenario** is a named, versioned *intent* describing what to simulate and under what posture (window/cadence/SLA/run mode). A scenario may be parameterized (e.g., “baseline”, “stress”, “fraud campaign variant”), but SR treats it as an input definition, not a computation.

**Key idea:** scenario = *intent*, not output.

---

### 3.2 Run

A **run** is a single execution instance of a scenario against a pinned world context. A run has a lifecycle (open → ready/failed/quarantined → closed) and produces a ledger trail.

**Key idea:** run = *realisation + ledger*, not “the world”.

---

### 3.3 World

A **world** is the deterministic synthetic universe produced/selected by the Data Engine under a given configuration fingerprint and parameterization. SR does not create worlds directly; it invokes or reuses them through the engine boundary.

---

### 3.4 World pins

**World pins** are the stable identifiers that locate and define the world SR is running against:

* `manifest_fingerprint`: identifies the exact engine manifest/config bundle used
* `parameter_hash`: identifies the chosen parameterization of that manifest

**Key idea:** these pins allow downstream components to join and reproduce without reading SR internals.

---

### 3.5 Run identity pins

**Run identity pins** are the stable identifiers SR uses to name a run and carry lineage everywhere:

* `scenario_id`: identifies the scenario definition/instance being executed
* `run_id`: identifies this specific run instance (unique within the platform)

**Note:** SR must define whether these are caller-provided, SR-minted, or derived—this is pinned later in SR3.

---

### 3.6 Window / cadence / time key

A **window** is the time scope the run covers (e.g., “a day”, “a week”, “T0..T1”). A **cadence** is how often runs occur (daily/hourly/ad-hoc). SR should treat time as explicit via a **window key** (e.g., `window_id` or `{start,end,tz}`), not implicit “now”.

**Key idea:** no hidden time dependence.

---

### 3.7 Run mode (conceptual)

A **run mode** describes how SR should behave regarding reuse/rebuild/replay, e.g.:

* reuse existing engine outputs when pins match and gates PASS
* rebuild world (force engine invocation)
* replay (re-emit readiness / re-register facts without rebuilding)
* resume (continue from a checkpoint, if supported)

**Note:** naming is flexible; semantics must be pinned later.

---

### 3.8 PASS artifacts / readiness gates

A **PASS artifact** is a machine-verifiable indicator produced by an upstream producer (typically the engine) that a required build/validation step succeeded. A **readiness gate** is the rule SR uses to decide whether a run can be declared READY.

**Key idea:** “no READY without required PASS gates”.

---

### 3.9 Readiness (READY)

**READY** is the SR-declared state indicating that:

* required prerequisites are met (gates PASS),
* required artifacts/refs are registered in SR’s join surfaces,
* downstream components can proceed without guessing.

READY is a **monotonic** declaration: once READY, SR does not revoke it.

---

### 3.10 Quarantine

**Quarantine** is a terminal (or semi-terminal) outcome where SR records the run as unsafe for downstream consumption, preserves evidence, and prevents dispatch/readiness propagation.

**Key idea:** quarantine is “record + halt downstream”, not “retry forever”.

---

### 3.11 Idempotency key

An **idempotency key** is the canonical identifier used to ensure “same request twice” does not duplicate side-effects. SR must define:

* what key(s) apply at the SR interface
* what key(s) apply per side-effect (engine invoke, emit signal, write artifacts)

---

### 3.12 Run ledger artifacts (SR-owned)

The **run ledger** is the set of SR-produced artifacts that represent intent, execution, and readiness:

* `run_plan`: SR’s declared intended work (steps, prerequisites)
* `run_record`: append-only log of what happened (events, attempts, outcomes)
* `run_facts_view`: canonical “pins + artifact refs” join surface for downstream
* `run_status`: current/final lifecycle state + reason fields

---

### 3.13 Completion evidence (engine receipt)

**Completion evidence** is the minimal proof SR requires from the engine boundary to consider the engine step complete. Typically includes:

* references/locators to engine outputs
* required PASS artifacts (or refs to them)

SR uses completion evidence as part of readiness gating and ledger registration.

---

### 3.14 Dispatch / READY signal

A **dispatch signal** (often the READY signal) is the event/notification emitted by SR to inform downstream that:

* a run exists,
* it is READY (or failed/quarantined),
* and where to find canonical join surfaces (pointer to `run_facts_view`).

---

## 4) SR as a black box (inputs → outputs)

> This section treats Scenario Runner (SR) as a **single black box**: what it **accepts**, what it **produces**, and what **boundaries** it touches. Shapes are conceptual here; machine-checkable shapes live in `contracts/`.

### 4.1 Inputs (what SR consumes)

SR consumes a **Run Request** plus any authoritative context needed to interpret it.

#### 4.1.1 Primary input: Run Request (conceptual)

A Run Request supplies:

* **Scenario intent**

  * scenario definition reference (name/version or scenario_id input)
  * run posture (SLA class, run mode)
  * window/cadence (or explicit window key)

* **World pins**

  * `manifest_fingerprint`
  * `parameter_hash`
  * (optional) world-selection rule *only if SR is allowed to select*

* **Run identity inputs**

  * `scenario_id` (caller-provided or SR-minted policy)
  * `run_id` (caller-provided or SR-minted policy)
  * (optional) idempotency key input, if caller supplies it

* **Execution constraints (optional)**

  * “reuse allowed” vs “force rebuild”
  * retry budget / priority class (if supported)
  * environment hints (local vs deployed), if you expose them

#### 4.1.2 Authoritative read-only context (conceptual)

SR may read these (without owning them):

* **Rails identity conventions**

  * how runs/worlds are identified and joined across the platform
* **Engine interface pack**

  * the minimal engine invocation surface + completion evidence expectations
* **Existing artifacts / registries**

  * prior run records (for reuse/replay)
  * world catalogues/manifests (if selection is allowed)

**Important boundary rule:** SR can *use* this context but must not “invent” or override it.

---

### 4.2 Outputs (what SR produces)

SR produces a small set of **canonical artifacts and/or signals** that downstream components use as the source of truth for “what run is this and what is safe to read”.

#### 4.2.1 SR-owned ledger artifacts (conceptual)

* **`run_plan`** — what SR intended to do (steps + prerequisites)
* **`run_record`** — append-only record of what actually happened (attempts, outcomes)
* **`run_facts_view`** — canonical join surface: identity pins + refs/locators to authoritative artifacts
* **`run_status`** — lifecycle state + timestamps + reason (READY / FAILED / QUARANTINED / etc.)

**Minimum expectation:** every ledger artifact carries the identity pins:
`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` (+ window key if applicable).

#### 4.2.2 Readiness / dispatch signal (conceptual)

SR emits a **READY (or equivalent)** signal/event/notification that downstream consumes.

* MUST include identity pins
* MUST include a pointer/ref to `run_facts_view` (so consumers never guess)
* MUST follow SR’s readiness laws (no READY without required PASS gates)

#### 4.2.3 Failure / quarantine outputs (conceptual)

When SR cannot safely complete:

* SR records failure/quarantine in the ledger (never silently dies)
* Optionally emits a failure/quarantine signal for observability and downstream gating

---

### 4.3 Boundary map (what SR touches)

#### 4.3.1 Upstream callers (who triggers SR)

Examples (not prescriptive):

* operator / CLI invocation
* scheduler / orchestrator
* API service submitting Run Requests
* test harness / replay controller

**Contract boundary:** all upstream callers speak the same **Run Request** contract.

#### 4.3.2 Engine boundary (SR ↔ Data Engine)

SR interacts with the engine via a thin invocation boundary:

* SR sends **EngineRunRequest** (pins + run identity policy fields)
* SR receives **EngineRunReceipt** / completion evidence (refs + PASS artifacts)

**Authority boundary:** engine owns world construction; SR owns how runs are recorded and declared ready.

#### 4.3.3 Downstream consumers (who relies on SR outputs)

Examples:

* Ingestion Gate (needs run identity + where to read)
* Online feature plane (needs pins + artifact refs)
* Decision loop (needs consistent run identity for decisions)
* Observability & governance (needs status + audit trail)

**Contract boundary:** downstream relies on `run_facts_view` + readiness signals, not SR internals.

#### 4.3.4 Storage & transport surfaces (conceptual)

SR will usually interact with:

* an artifact store (files/object store/db) to write ledger artifacts
* optionally an event bus/queue to emit READY/failure signals

**Design point (conceptual):** storage/transport tech is implementation freedom, but addressing + contract shapes + invariants are not.

---

## 5) Modular breakdown (Level 1) and what each module must answer

> This is **not** an engine-style state machine. It’s a **5-part responsibility split** that forces SR’s important design decisions to be answered *somewhere*, while leaving implementation style to the coding agent.

### 5.0 Module map (one screen)

SR is decomposed into 5 conceptual modules:

1. **Resolve & Pin** — turn inputs into a pinned run context
2. **Plan** — declare intended work + required gates
3. **Execute** — invoke engine or reuse artifacts (idempotently)
4. **Verify & Register** — check evidence + write join surfaces
5. **Emit & Close** — emit READY/failure + close lifecycle

Each module has:

* **what it owns**
* **questions it must answer** (design intent)
* **what it can leave to the agent**
* **how it operates locally vs deployed** (conceptual)

---

## 5.1 Module 1 — Resolve & Pin

### Purpose (what it is)

Resolve scenario intent + identity policy + world pins into a **pinned run context** that SR can treat as immutable for the run.

### What it owns (responsibilities)

* Validating “minimum viable” Run Request (conceptually; schema enforcement is contracts)
* Deciding/recording:

  * run equivalence posture (same vs different run)
  * whether pins are explicit or selected (if selection is allowed)
* Writing the *first* authoritative SR ledger entry that anchors identity (often via `run_plan` draft or `run_record` entry)

### Questions this module must answer (design decisions)

* **Run sameness:** what fields define “same logical run” for idempotency?
* **ID minting:** who supplies/mints `scenario_id` and `run_id` (caller vs SR vs derived)?
* **World pin posture:** must `manifest_fingerprint` be provided, or can SR select?

  * If SR selects: what is the deterministic selection rule and what evidence is recorded?
* **Window/time key posture:** what explicit window key is carried forward (even if it’s a placeholder here)?

### What can be left to the coding agent

* How validation is implemented (schema check, typed DTOs, etc.)
* How selection is executed (registry lookup vs filesystem scan)
* Internal caching, memoization, or local UX flows

### Local vs deployed operation (conceptual)

* **Local:** typically “explicit pins only” is acceptable (simpler, fewer implicit choices)
* **Deployed:** may allow selection policy, but MUST record selection evidence in ledger

### Conceptual inputs → outputs

* **Input:** Run Request (+ read-only catalogues/registries if used)
* **Output:** Pinned run context + initial ledger anchoring entry

---

## 5.2 Module 2 — Plan

### Purpose (what it is)

Produce a **run plan**: SR’s declared intended steps, prerequisites, and gate requirements.

### What it owns (responsibilities)

* Declaring which conceptual steps SR intends to perform (invoke/reuse, verify gates, register facts, emit READY)
* Declaring the **required gate set** for readiness
* Recording mode intent (reuse vs rebuild vs replay posture)

### Questions this module must answer (design decisions)

* What is the minimum set of steps SR recognizes for a run?
* What is the required readiness gate set (even if defined as “engine-required gates + SR-required gates”)?
* What does SR consider “complete enough to proceed to verification”?
* What is the planned behaviour if prerequisites are missing at start (fail-fast vs wait/retry)?

### What can be left to the coding agent

* Whether plan is static or dynamically generated
* Planner implementation style (functions vs workflow graphs)
* Whether the plan is stored as JSON/YAML so long as the contract target is respected

### Local vs deployed operation (conceptual)

* **Local:** plan may omit scheduling metadata; still must be auditable
* **Deployed:** may include priority/SLA fields; still must not change semantic meaning

### Conceptual inputs → outputs

* **Input:** pinned run context
* **Output:** `run_plan` (or plan entries in `run_record`) that downstream/auditors can interpret

---

## 5.3 Module 3 — Execute

### Purpose (what it is)

Carry out the plan by **invoking the engine** or **reusing existing artifacts**, while ensuring idempotency under retries.

### What it owns (responsibilities)

* The engine boundary interaction (send EngineRunRequest; obtain completion evidence)
* Reuse detection logic (if allowed by run mode)
* Ensuring all execution side-effects are idempotent (including engine invocation and any dispatch)

### Questions this module must answer (design decisions)

* What is the minimal **EngineRunRequest** SR sends (pins + identity + any seed policy SR owns)?
* What counts as an “execution attempt” in the run record?
* What is SR’s retry posture for engine invocation failures (conceptual categories; details pinned later)?
* Under what conditions does SR choose reuse vs invoke (existence + PASS + match pins)?
* What side-effects exist during execution that must be protected by idempotency keys?

### What can be left to the coding agent

* Orchestration tech (Airflow/Dagster/custom)
* Concurrency strategy, worker model, polling vs callback
* How retries are implemented (loop vs queue)

### Local vs deployed operation (conceptual)

* **Local:** likely synchronous “call engine and wait”
* **Deployed:** can be distributed/async, but MUST preserve the same retry/idempotency semantics

### Conceptual inputs → outputs

* **Input:** pinned run context + plan
* **Output:** Engine completion evidence (receipt) *or* reuse evidence, plus run record entries of attempts/outcomes

---

## 5.4 Module 4 — Verify & Register

### Purpose (what it is)

Verify required readiness evidence and register canonical **join surfaces** so downstream can safely proceed.

### What it owns (responsibilities)

* Evaluating readiness gates (PASS artifacts and any minimal verification standard SR chooses)
* Producing/updating SR’s canonical facts view:

  * `run_facts_view` (pins + refs/locators to authoritative artifacts)
* Producing/updating `run_status` consistent with the lifecycle law

### Questions this module must answer (design decisions)

* What exactly does SR verify to declare readiness?

  * existence-only vs presence-of-PASS flags vs digest checks (choose minimum you trust)
* Which PASS artifacts are *required* for READY (and where are they referenced from)?
* What is SR’s failure posture:

  * fail-fast vs quarantine vs partial completeness (if partial is allowed at all)
* What must be recorded on verification failure (error category, dependency, evidence pointers)?

### What can be left to the coding agent

* Mechanism of verification (filesystem vs API checks)
* Storage backend choices (object store/db) **as long as** addressing + artifacts are stable
* Internal indexing for faster lookups

### Local vs deployed operation (conceptual)

* **Local:** verification may be minimal but must still enforce “no READY without gates”
* **Deployed:** may include stronger verification (digests) but must not change *which* gates are required without versioning

### Conceptual inputs → outputs

* **Input:** engine receipt/reuse evidence + plan + pinned context
* **Output:** `run_facts_view` + `run_status` updates + run record entries for verification results

---

## 5.5 Module 5 — Emit & Close

### Purpose (what it is)

Emit the run’s declared outcome (READY/FAILED/QUARANTINED) and close lifecycle in a monotonic, auditable way.

### What it owns (responsibilities)

* Emitting READY/dispatch (or failure/quarantine) signal/event/notification
* Ensuring the signal points to the canonical join surface (`run_facts_view`)
* Finalizing the run lifecycle state in `run_status` (consistent with laws)

### Questions this module must answer (design decisions)

* What is the **READY source-of-truth**: event, artifact flag, status endpoint, or combination?
* What is the lifecycle state model (allowed transitions only; no READY rollback)?
* What must be included in READY so downstream can proceed without guessing?
* If SR emits failure/quarantine notifications: what minimum evidence must accompany them?

### What can be left to the coding agent

* Transport mechanism (Kafka/topic vs file drop vs HTTP)
* Subscriber mechanics and delivery guarantees, as long as contract semantics are preserved
* Operational deployment mechanics (service vs job runner)

### Local vs deployed operation (conceptual)

* **Local:** “emit” could be a file marker or console output + artifact write
* **Deployed:** emit to event bus; still must include the same fields/pointers

### Conceptual inputs → outputs

* **Input:** verified readiness or terminal failure state + ledger artifacts
* **Output:** READY/failure/quarantine signal + closed lifecycle state

---

## 5.6 Cross-module “must stay pinned” items (summary)

Across all modules, SR must ensure:

* identity pins carried everywhere
* idempotency is defined for interface + side-effects
* readiness is gated (no greenwashing)
* ledger is audit-safe and explains behaviour
* local vs deployed differences do not change semantics (only mechanics)

---

## 6) Determinism and replay model (conceptual but explicit)

> This section pins the **behavioural guarantees** SR must uphold so that a coding agent can implement SR fast **without** ambiguity, while still having freedom over orchestration tech and internal structure.

### 6.1 What “deterministic SR” means (scope)

SR is deterministic if, given the same **logical Run Request** and the same available upstream artifacts, SR will:

* resolve the **same pins** (or record the same selection outcome),
* produce the same **ledger meaning** (plan/record/facts/status semantics),
* emit the same **READY/failure** outcome (or refuse to proceed for the same reasons),
* and not duplicate side effects under retries/duplicates.

Determinism does **not** require:

* the same internal scheduling strategy,
* the same concurrency implementation,
* identical log line ordering,
  as long as the ledger artifacts and outward-facing semantics are equivalent.

---

### 6.2 Run sameness and idempotency (conceptual model)

SR must define a **run equivalence rule**: what makes two invocations “the same logical run” versus a distinct run.

Conceptually, SR supports one of these postures (you can choose later; the concept doc just names them):

* **Caller-keyed sameness:** caller provides an explicit idempotency key; SR treats identical key + pins + window as the same run.
* **SR-derived sameness:** SR derives an idempotency key from a canonical subset of the Run Request (stable ordering, stable serialization, etc.).
* **SR-minted identity with persistence:** SR mints `run_id` once and persists it; repeats resolve to the existing run via lookup rules.

**Non-negotiable:** whichever posture you choose, SR must be able to answer:

* “If I submit the same Run Request twice, what exactly must happen?”
* “If one field changes (e.g., window), does that force a new run?”

(Details land in SR3 + contract schemas.)

---

### 6.3 Explicit time/window semantics (no hidden “now”)

SR must treat time as **explicit input and explicit record**:

* A run must carry a stable **window key** (e.g., `window_id` or `{start,end,tz}`) so that:

  * local vs deployed execution cannot drift,
  * replays are meaningful and comparable.

SR must not silently interpret “today” based on wall clock unless “today” is first converted into an explicit window key and recorded.

---

### 6.4 Replay and reuse modes (conceptual modes SR may support)

SR should treat reuse/replay as named modes (names are placeholders), with clear semantics:

1. **REBUILD_WORLD**

   * SR forces a fresh engine invocation for the pinned world intent (subject to policy).
2. **REUSE_WORLD**

   * SR reuses existing engine outputs **if** pins match and required PASS evidence exists.
3. **REPLAY**

   * SR does not rebuild the world; it replays SR outputs/signals from ledger truth:

     * re-register facts if needed,
     * re-emit READY (or failure) deterministically,
     * optionally re-verify gates (policy choice).
4. **RESUME**

   * SR continues an interrupted run attempt from recorded progress/checkpoints.
   * Resume must still respect idempotency (resume is “continue safely”, not “run again and hope”).

**Key requirement:** whichever subset you implement in v1, SR must record the chosen mode in the ledger so downstream and auditors can distinguish “rebuilt” vs “reused” vs “replayed”.

---

### 6.5 Evidence-based reuse rules (conceptual)

If reuse is allowed, SR must decide reuse vs rebuild using **evidence**, not guesswork.

Conceptually, reuse should require:

* pins match (`manifest_fingerprint`, `parameter_hash`)
* required PASS artifacts exist (per gate rules)
* completion evidence is consistent enough to register facts (refs/locators resolvable)

If any required evidence is missing, SR must not claim reuse succeeded; it must either:

* rebuild, or
* fail/quarantine (depending on mode/policy).

---

### 6.6 Side-effects and idempotency boundaries (conceptual)

SR determinism depends on listing SR side-effects and ensuring each is idempotent.

At minimum, SR must treat these as side-effects:

* engine invocation request (or reuse declaration)
* writing/updating each ledger artifact (`run_plan`, `run_record`, `run_facts_view`, `run_status`)
* emitting READY/failure/quarantine signals (if any)

**Conceptual rule:** each side-effect must have an idempotency strategy keyed by stable identity (run equivalence key / `run_id` + “effect kind”), so retries don’t duplicate outcomes.

(Exact key shapes live in SR2/SR3 and the contract pack.)

---

### 6.7 Replay semantics: what replay does and does not do

Replay must be definable in one sentence:

* Replay re-materializes the platform-visible outcome of a run **from the ledger** (and any referenced evidence), without changing the meaning of the run.

Replay does not:

* retroactively change a FAILED run into READY,
* mutate engine outputs,
* reinterpret pins using new “latest” rules.

If a correction is needed, SR creates a **new run**.

---

### 6.8 Local vs deployed determinism (conceptual guarantee)

SR may operate locally (single process, synchronous) or deployed (distributed, async). Determinism requires:

* The **same Run Request** resolves to the same pinned context and ledger meaning.
* Differences are allowed only in mechanics:

  * polling vs callbacks,
  * worker parallelism,
  * storage backend,
  * transport mechanism for signals.

**Non-allowed difference:** local and deployed runs must not produce different outcomes due to hidden time, implicit selection, or inconsistent idempotency.

---

### 6.9 Determinism acceptance scenarios (conceptual checklist)

SR should be considered “deterministic enough” when it can satisfy, at minimum:

* Same logical Run Request twice → no duplicate side-effects; same final status.
* REUSE_WORLD with matching pins + PASS evidence → does not invoke engine.
* Missing required PASS evidence → SR does not emit READY.
* Engine failure → SR records failure/quarantine, does not greenwash.
* REPLAY reproduces the same references/pins and emits the same outcome from ledger truth.

---

## 7) Contracts philosophy and boundary surfaces

> Contracts exist to make SR **interoperable and machine-checkable** while keeping your document surface area small. They are not “docs for every internal step”; they are **source-of-truth shapes at boundaries**.

### 7.1 What a “contract” means in this platform

A **contract** is a machine-readable definition of:

* **what SR accepts** (Run Request)
* **what SR emits** (ledger artifacts + READY/failure signals)
* **what SR expects from dependencies** at a boundary (engine receipt/evidence)

Contracts exist to prevent:

* “shape drift” between producer and consumers,
* “interpretation drift” where two components read the same artifact differently,
* and silent breaking changes when you iterate quickly.

**Key principle:** specs define *behaviour/invariants*; contracts define *shape/structure*.

---

### 7.2 Contracts belong at boundaries (not per internal module)

SR is intentionally modularized into 5 responsibility modules, but those modules are **not separate deployable systems** (by default). Therefore:

* SR modules are specified via **prose invariants + questions** (SR1–SR5).
* Contracts are defined only where another system must integrate.

**Rule:** do **not** create “Resolve module schema”, “Execute module schema”, etc., unless:

* the module is independently pluggable, or
* two alternative implementations must be swapped without changing SR behaviour.

This keeps the contract surface minimal and the agent’s reading burden low.

---

### 7.3 Boundary surfaces SR must contractually pin

SR touches two mandatory boundaries:

#### A) SR ↔ Platform boundary (public SR contract pack)

This is what other components rely on as the **system-of-record** for run identity, readiness, and joins.

It covers:

* **RunRequest** (what SR accepts)
* **Ledger artifacts** SR owns (plan/record/facts/status)
* **READY / dispatch signals** (what downstream consumes)
* **Failure/quarantine taxonomy** (so failures have standard meaning)

#### B) SR ↔ Data Engine boundary (engine invocation boundary)

This is thin and exists to prevent accidental coupling to engine internals.

It covers:

* **EngineRunRequest** (pins + identity + any seed policy SR owns)
* **EngineRunReceipt / completion evidence** (refs + PASS evidence SR relies on)

Everything else (bus details, storage tech, orchestration tech) is implementation freedom unless it changes addressing/meaning.

---

### 7.4 “Deep spec, few files” contract strategy

To match your “reduce horizontal surface” goal:

* Keep contracts as **separate artifacts** (for validation), but collapse them into **1–2 files** total.
* Use a single schema file with `$defs` for multiple artifact types, rather than many small schema files.

**Target:**

* `sr_public_contracts_v1.schema.json`
* `sr_engine_boundary_v1.schema.json`

This yields machine-checkability with minimal repo sprawl.

---

### 7.5 Avoiding ambiguity: how consumers know what to validate against

If one schema file contains many `$defs`, the platform must be unambiguous about which `$defs` applies to each artifact. SR will therefore adopt one of these *conceptual* approaches:

* **Preferred:** self-describing artifacts
  Every SR artifact includes:

  * `kind` (e.g., `run_plan`, `run_record`, `run_facts_view`, `run_status`, `run_ready_signal`)
  * `contract_version` (e.g., `sr_public_contracts_v1`)
    Consumers validate by (`contract_version`, `kind`).

* **Alternative:** path/name-to-schema binding rule
  The doc/spec defines a binding mapping:

  * `run_facts_view.json` → `$defs/RunFactsView`
  * `run_status.json` → `$defs/RunStatus`, etc.

**Non-negotiable:** SR must not require consumers to “guess” artifact type from content patterns.

---

### 7.6 Versioning and compatibility posture (conceptual)

Contracts must support iteration without breaking the platform:

* Every contract has an explicit **version identifier**.
* SR outputs must declare the version they conform to (via `contract_version` or an equivalent rule).
* Breaking changes require:

  * a new version (v2),
  * a compatibility plan (dual-write, adapter, or migration),
  * and explicit documentation in the SR specs (not hidden in code).

---

### 7.7 Authority boundaries expressed through contracts

Contracts should reinforce authority boundaries by making it clear:

* what SR **asserts** (run status, readiness, join surfaces)
* what SR **references** (engine outputs, PASS artifacts, external catalogues)
* what SR **never mutates** (engine-produced authoritative content)

In practice: SR contracts should contain **refs/locators** to external artifacts rather than embedding them.

---

### 7.8 When internal “provider interfaces” become contracts

Only introduce additional contract surfaces if SR becomes intentionally pluggable, e.g.:

* **Execution Provider interface** (local vs distributed executors)
* **Dispatch Provider interface** (Kafka vs filesystem vs HTTP)

Even then, keep them tiny: one interface each, not a new universe of schemas.

---

## 8) SR contract pack overview (what exists and what it covers)

> This section describes the **contract artifacts** SR will ship with, what each covers, and how consumers use them. It is still **conceptual** (the schemas are the actual source-of-truth once authored).

### 8.0 Contract pack inventory (target set)

SR will ship **two** machine-checkable schema files:

1. `contracts/sr_public_contracts_v1.schema.json`
   **SR ↔ Platform boundary** (what other components rely on)

2. `contracts/sr_engine_boundary_v1.schema.json`
   **SR ↔ Data Engine boundary** (invocation + completion evidence)

This keeps the surface lean while retaining validation and drift prevention.

---

## 8.1 SR ↔ Platform: `sr_public_contracts_v1.schema.json`

### 8.1.1 What this file is for

This schema file defines the shapes SR **accepts** and **produces** at its platform boundary. It is the primary interoperability contract for:

* Control & Ingress consumers (Ingestion Gate, bus dispatchers)
* Decision loop consumers (feature/decision joinability)
* Observability & governance consumers (run status/audit)

### 8.1.2 Common identity envelope (shared fields)

All SR public artifacts/signals should share a common “identity core” (whether via `$ref` in schema or a shared `$defs` object), conceptually including:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`
* (plus your explicit time/window key, once chosen)

**Principle:** downstream must never need SR-internal context to join or interpret a run.

### 8.1.3 Target `$defs` (conceptual list)

Within `sr_public_contracts_v1.schema.json`, define `$defs` for:

1. **`RunRequest`** (SR input)

* minimal run intent + pins + identity policy inputs
* optional run mode / SLA class
* optional caller idempotency key (if you support that posture)

2. **`RunPlan`** (SR-produced intent)

* pinned context summary
* declared mode (reuse/rebuild/replay)
* declared required readiness gates (as names/refs, not embedded engine content)
* declared planned steps (conceptual step names only)

3. **`RunRecord`** (append-only execution record)

* event list / entries capturing:

  * attempts (engine invoke/reuse decision)
  * verification outcomes
  * retries/failures (with taxonomy linkage)
* **Conceptual rule:** append-only or monotonic updates only (per your laws)

4. **`RunFactsView`** (the most important join surface)

* the canonical “pins + refs/locators” table/view that downstream uses
* includes:

  * identity pins
  * references to engine outputs (locators, digests if you choose)
  * references to PASS artifacts required for readiness
  * references to SR ledger artifacts (plan/record/status)

5. **`RunStatus`** (lifecycle state)

* state enum (OPEN/READY/FAILED/QUARANTINED/CLOSED, etc.)
* timestamps (conceptual; exact set pinned later)
* failure/quarantine reason reference (taxonomy + evidence pointers)

6. **`RunReadySignal`** (dispatch/readiness event)

* identity pins
* readiness state (READY or terminal state if you emit non-ready signals)
* **MUST include** a pointer/ref to `RunFactsView`
* optional pointers to `RunStatus` / `RunRecord`

7. **`FailureTaxonomy`** (standardized failure meaning)

* category (invalid request / missing prereq / dependency fail / internal fail / etc.)
* retryability flag / recommended posture (retry vs quarantine vs fail-fast)
* minimal reason fields (code + short message + evidence refs)

8. **(Optional but useful) `ArtifactRef` / `Locator`**

* a standard reference type reused across facts view and signals:

  * where an artifact lives (path/URI/key)
  * optional digest/version fields
  * optional “producer” field (engine vs SR)

**Lean approach:** you can keep (8) inside `$defs` even if it’s only used internally by other `$defs`.

### 8.1.4 Validation targeting (how consumers know what to validate)

Because this file contains multiple `$defs`, SR must adopt a deterministic validation targeting rule:

* **Preferred:** every SR artifact includes:

  * `kind` (e.g., `run_plan`, `run_record`, `run_facts_view`, `run_status`, `run_ready_signal`)
  * `contract_version` (e.g., `sr_public_contracts_v1`)
    Consumers validate by (`contract_version`, `kind`) → `$defs/<Kind>`.

* **Alternative:** binding filename/path → `$defs` mapping rule (must be written as binding in the specs).

**Non-negotiable:** consumers must not guess which schema applies.

### 8.1.5 What this public contract deliberately does not embed

To preserve authority boundaries and keep contracts stable, SR public contracts should:

* reference engine artifacts via `ArtifactRef/Locator`
* not inline entire engine outputs
* not embed implementation-specific transport headers

---

## 8.2 SR ↔ Engine: `sr_engine_boundary_v1.schema.json`

### 8.2.1 What this file is for

This schema file defines the minimal boundary between SR and the Data Engine so SR can:

* invoke (or request reuse) deterministically
* receive machine-verifiable completion evidence

It exists to prevent accidental coupling to engine internals while still being unambiguous for implementation.

### 8.2.2 Target `$defs` (conceptual list)

Within `sr_engine_boundary_v1.schema.json`, define `$defs` for:

1. **`EngineRunRequest`**

* must include:

  * world pins (`manifest_fingerprint`, `parameter_hash`)
  * run identity pins (`scenario_id`, `run_id`)
  * any seed policy field **only if SR owns it**
* optional:

  * window key (if engine needs it)
  * run mode hints (if supported by engine boundary)

2. **`EngineRunReceipt`** (completion evidence)

* references/locators to the engine output catalogue SR needs
* required PASS artifacts (or refs to them)
* minimal summary fields SR needs for gating/registration (not engine internals)

**Conceptual rule:** SR treats this receipt as “what counts as engine completion evidence”.

### 8.2.3 Relationship to the Engine Interface Pack

If your engine interface pack already defines these shapes, SR should:

* **reference/import** those definitions rather than duplicating them
* or mirror them exactly with explicit linkage to avoid divergence

(Goal: no forking of the engine boundary schema.)

---

## 8.3 What contracts cover vs what specs cover (division of labour)

### 8.3.1 Contracts cover (shape/structure)

* required fields and types
* required presence of identity pins
* allowed enums (status states, failure categories, etc.)
* reference/locator structures
* “what must be present for READY signal payload”

### 8.3.2 Specs cover (behaviour/invariants)

* reuse vs rebuild decision rules
* gating semantics (“no READY without gates” and what gates are required)
* idempotency semantics (what counts as same run; per-side-effect idempotency)
* retry policy and quarantine posture
* lifecycle monotonicity rules
* local vs deployed semantic equivalence

**Rule:** contracts prevent shape drift; specs prevent behaviour drift.

---

## 8.4 Naming and versioning posture (conceptual)

* Contract filenames include a clear version (`*_v1.schema.json`)
* Artifacts/signals should declare `contract_version` (or be bound by path→schema rules)
* Breaking changes require:

  * new version (v2)
  * compatibility plan (dual-write/adapters/migrations)
  * explicit spec note (no silent breakages)

---

## 9) Artifact addressing, naming, and discoverability (conceptual)

> This section defines the *idea* of how SR artifacts are addressed and found. The goal is: **downstream never guesses** where things are, and “replay/join” is always possible from SR’s ledger.

### 9.1 Design goals (why addressing matters)

SR artifact addressing must support:

* **Joinability:** every downstream component can locate the right artifacts from identity pins alone.
* **Replayability:** the ledger must be enough to re-materialize the run outcome.
* **Deterministic discovery:** “latest” or “ready” cannot rely on wall-clock ambiguity.
* **Storage/transport independence:** local filesystem vs deployed object store is an implementation detail; addressing semantics stay the same.

---

### 9.2 Addressing keys (what everything is indexed by)

At minimum, SR artifacts are addressed by:

* `scenario_id`
* `run_id`
* world pins: `manifest_fingerprint`, `parameter_hash`
* (optional but recommended) explicit time/window key (e.g., `window_id`)

**Principle:** `run_id` is the primary lookup key; other keys are for browsing and deterministic selection.

---

### 9.3 Two “roots” SR deals with (SR ledger vs engine world)

SR will usually reference two different artifact families:

1. **Engine world outputs** (owned by Data Engine)
   Canonical addressing convention (already established in your platform):

   * `fingerprint={manifest_fingerprint}/...`
     SR should *reference* these (never embed them).

2. **SR ledger outputs** (owned by Scenario Runner)
   SR should store its own artifacts under a stable run-ledger root, conceptually grouped by run identity.

**Key point:** SR’s facts view bridges these worlds by carrying **pointers/locators** to engine outputs.

---

### 9.4 Canonical SR run-ledger path template (conceptual)

SR artifacts should live in a run-scoped directory so “open a run” is trivial.

A simple conceptual template:

* `.../scenario_id={scenario_id}/run_id={run_id}/`

  * `run_plan.json`
  * `run_record.jsonl` *(or JSON; format is optional)*
  * `run_facts_view.json`
  * `run_status.json`
  * `signals/ready.json` *(only if you persist signals as artifacts)*

**Notes**

* Naming is flexible, but must be stable and documented.
* If you prefer to group by world pins, you can nest them, but avoid making the path depend on “latest”.

---

### 9.5 ArtifactRef / Locator (how SR points to anything)

To keep cross-component integration clean, SR should standardize a single reference type used in:

* `run_facts_view`
* `run_ready_signal`
* `run_record` entries (as evidence pointers)

Conceptually, an `ArtifactRef` includes:

* `producer` (SR vs Engine vs other)
* `locator` (path/URI/key)
* optional integrity metadata: `digest`, `size_bytes`, `content_type`
* optional contract targeting: `kind`, `contract_version`

**Principle:** downstream reads **refs**, not “implied locations”.

---

### 9.6 Discoverability patterns (how consumers find runs)

#### 9.6.1 Direct lookup by `run_id` (primary)

* Given `scenario_id` + `run_id`, consumers locate:

  * `run_status` to check outcome
  * `run_facts_view` to locate all authoritative refs

This is the cleanest path for deterministic replay/audit.

#### 9.6.2 Lookup by scenario + window key (deterministic browsing)

If your platform needs “the run for window X”:

* define a stable window key (e.g., `window_id`)
* and allow a deterministic index like:

  * `.../scenario_id={scenario_id}/window_id={window_id}/run_id={run_id}` *(link/redirect or small pointer file)*

This avoids “search the filesystem and pick newest”.

#### 9.6.3 “Latest READY run” (only if you define it)

If the platform needs “latest READY”, SR must define what “latest” means (conceptually):

* latest by **window key ordering**, not by wall-clock write time
* tie-break rules if multiple READY runs exist for the same window (usually “new run_id wins” only if explicitly allowed)

Mechanisms (pick later; conceptually allowed):

* a small **index artifact** per scenario (e.g., `latest_ready.json`) updated monotonically
* or a query over `run_status` records with a deterministic sort key

**Non-negotiable concept:** “latest” must be deterministic and explainable from the ledger/index.

---

### 9.7 Local vs deployed addressing (same semantics, different mechanics)

* **Local:** `locator` may be a filesystem path under a project/artifact root.
* **Deployed:** `locator` may be an object-store URI or database key.

**Rule:** the *meaning* of locators must not change with environment:

* same run identity → same logical artifact set
* no hidden reliance on machine-local paths without recording them in the ledger

---

### 9.8 Minimal integrity/lineage posture (conceptual)

SR should record enough metadata to make audits and replays sane:

* `run_facts_view` contains refs to:

  * engine completion evidence + required PASS artifacts
  * SR ledger artifacts themselves (self-referential is fine)
* optional digests for “proof” (you can keep this minimal in v1)

**Principle:** SR can start lean, but must never make downstream infer lineage.

---

## 10) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Scenario Runner docs and contracts. The goal is a **single, deep reading surface** for SR design, plus **minimal machine-checkable contracts**.

### 10.1 Target location in repo

Conceptually, SR lives under Control & Ingress:

* `docs/model_spec/control_and_ingress/scenario_runner/`

This folder should be self-contained: a new contributor should understand SR by starting here.

---

### 10.2 Proposed skeleton (lean, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ control_and_ingress/
      └─ scenario_runner/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ SR1_charter_and_boundaries.md
         │  ├─ SR2_interface.md
         │  ├─ SR3_identity_pinning_reuse_replay.md
         │  ├─ SR4_gates_retries_failures.md
         │  └─ SR5_ledger_and_acceptance.md
         │
         └─ contracts/
            ├─ sr_public_contracts_v1.schema.json
            └─ sr_engine_boundary_v1.schema.json
```

**Notes**

* You can collapse `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under a deadline; collapse to 2 files (as above) to avoid sprawl.

---

### 10.3 What each file is for (intent)

#### `README.md`

* Entry point: what SR is, what it’s responsible for, where to start reading.
* Links to:

  * `CONCEPTUAL.md` (if separate)
  * `specs/` SR1–SR5 reading order
  * `contracts/` schemas

#### `CONCEPTUAL.md`

* The roadmap you’re writing now:

  * SR’s purpose in the platform
  * core invariants (“laws”)
  * modular breakdown and the questions each module must answer
  * contract philosophy and what the contract pack covers
  * addressing/discoverability concepts

This is “directional alignment”, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * what is authoritative (specs + contracts)
  * what can be treated as implementation freedom
  * non-negotiables (idempotency, gates, ledger semantics)
* “Do not invent” warnings:

  * never assume readiness without gates
  * never change meanings of IDs/pins
  * never add new side-effects without idempotency keys

#### `specs/` (SR1–SR5)

* These are the eventual binding-ish design documents.
* They carry the **decisions** and **invariants** that define behaviour.
* They inline:

  * diagrams (ASCII)
  * examples
  * decision rationale sections
    to avoid separate folders under deadline.

#### `contracts/`

* Machine-checkable schema artifacts.
* Purpose: enforce the shapes at boundaries and prevent drift.

---

### 10.4 Reading order (recommended)

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (design direction)
3. `specs/SR1_...` → `specs/SR5_...` (binding behaviour decisions)
4. `contracts/*.schema.json` (machine-checkable truth)

For implementation: the coding agent should treat:

* `contracts/` as the source of truth for shapes,
* `specs/` as the source of truth for behaviour/invariants.

---

### 10.5 Allowed variations (without changing intent)

To keep things flexible:

* You may merge `CONCEPTUAL.md` into `README.md`.
* You may merge SR1–SR5 into fewer spec files once stable.
* You may add `contracts/README.md` *only* if necessary for validation rules.
* Avoid adding `examples/`, `diagrams/`, `decisions/` folders unless you later need reuse across components.

---

## 11) What the eventual spec docs must capture (mapping from this concept doc)

> This section is the “bridge”: it maps this conceptual roadmap into the **actual spec docs** you’ll write (SR1–SR5), and clarifies what each spec must pin vs what can remain implementation freedom.

### 11.0 Mapping rule (how to use this section)

For every “question” or “law” in this conceptual doc:

* It must end up either as:

  * a **binding decision** in SR1–SR5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared **implementation freedom** (so the agent doesn’t overfit).

---

## 11.1 SR1 — Charter and boundaries (what SR is and is not)

### SR1 must capture

* SR’s **purpose** in the platform (run-orchestrator + run-ledger)
* Explicit **authority boundaries**:

  * what SR is system-of-record for (identity, readiness, join surfaces)
  * what SR is not responsible for (features, ingestion validation, decisioning, labels, training)
* The **core invariants (“laws”)** in enforceable form:

  * no READY without gates
  * ledger is audit-safe
  * idempotency under duplicates/retries
  * monotonic lifecycle
* High-level boundary map:

  * upstream callers
  * engine boundary
  * downstream consumers

### SR1 may leave to the coding agent

* internal architecture
* orchestration tech
* logging/metrics implementation details (beyond required fields)

---

## 11.2 SR2 — Interface (what SR accepts and emits)

### SR2 must capture

* The **Run Request** semantics:

  * which fields are required conceptually
  * what “same request twice” means at the interface level
* SR’s **public outputs**:

  * which ledger artifacts exist (names + meaning)
  * what READY/dispatch means conceptually
* A **consumer-facing contract narrative**:

  * how downstream should read SR artifacts (start from run_status + run_facts_view)
* Contract targeting rule (one of):

  * self-describing `kind` + `contract_version`, or
  * binding filename/path → `$defs` mapping

### SR2 may leave to the coding agent

* transport mechanism (HTTP/CLI/queue)
* sync vs async API style
* how payloads are serialized (JSON/YAML), as long as schema validity holds

---

## 11.3 SR3 — Identity, pinning, reuse, replay

### SR3 must capture (this is where determinism is pinned)

* **Run equivalence rule** (what defines same vs different run)
* **ID minting posture**:

  * who provides `scenario_id`, `run_id`
  * deterministic derivation vs generated + persisted
* **World pin posture**:

  * explicit pins required vs SR selection allowed
  * if selection allowed: deterministic selection rule + what gets recorded
* **Reuse rules**:

  * when SR reuses vs rebuilds (evidence-based criteria)
* **Replay rules**:

  * what replay means (re-emit, re-register, re-verify)
  * what replay never does (no mutation, no reinterpretation of “latest”)

### SR3 may leave to the coding agent

* lookup mechanics (how SR checks existence)
* caching strategy
* scheduling mechanisms for replay jobs

---

## 11.4 SR4 — Gates, verification, retries, failures

### SR4 must capture (correctness + safety)

* Definition of **READY**:

  * required PASS artifacts (as a set)
  * minimum verification standard (existence vs digest policy, etc.)
* **Failure taxonomy + retryability posture** (aligned to contracts):

  * invalid request vs missing prereq vs dependency fail vs internal fail
* **Retry rules**:

  * what is retriable, attempt limits, backoff posture (even if coarse)
* **Quarantine rules**:

  * when SR quarantines vs fails fast
* **Partial completion posture**:

  * either explicitly “all-or-nothing”
  * or define what partial states mean and how downstream must behave (harder)

### SR4 may leave to the coding agent

* retry implementation mechanism (queue vs loop)
* monitoring wiring (beyond what must be recorded in ledger)
* deployment-specific failure handling, as long as ledger semantics remain true

---

## 11.5 SR5 — Ledger artifacts, storage rules, acceptance scenarios

### SR5 must capture (joinability + audit)

* Canonical artifact set and meanings:

  * `run_plan`, `run_record`, `run_facts_view`, `run_status`, signals
* Minimum required fields for each (in prose + aligned with schema)
* Update/immutability rules:

  * append-only for run_record
  * allowed updates for run_status (monotonic)
  * whether run_facts_view is immutable snapshot or versioned
* Addressing/discoverability rules:

  * run-ledger path template (conceptual)
  * how consumers find facts/status by run_id
  * if “latest READY” exists: deterministic rule
* Acceptance scenarios (Definition of Done):

  * same request twice → no duplicate side effects
  * missing PASS → never READY
  * engine failure → recorded + no downstream dispatch
  * reuse works when evidence matches
  * replay reproduces pins/refs and explainability

### SR5 may leave to the coding agent

* file formats (json/jsonl/parquet) unless you choose to pin them
* storage backend (FS/object store/db)
* indexing approach, as long as discoverability rules are met

---

## 11.6 Contracts mapping (what must be in schema vs prose)

* **Schema must include**:

  * required identity pins
  * artifact kinds and versioning targeting rule
  * structure of refs/locators (ArtifactRef)
  * READY signal pointer to facts view
  * failure taxonomy shape
* **Prose/spec must include**:

  * behaviour rules: gating, idempotency semantics, replay semantics
  * “what counts as evidence” and how to react to missing evidence
  * lifecycle monotonicity rules

---

## 11.7 Minimal completeness standard (so SR is implementable)

SR should be considered “spec-ready” for implementation when SR1–SR5 collectively answer:

* identity & run equivalence
* pinning/selection posture
* reuse vs rebuild rules
* readiness gate set and failure handling
* ledger artifacts + addressing
* deterministic replay posture

Everything else can remain implementation freedom.

---

## 12) Acceptance questions and “Definition of Done”

> This section is the conceptual **ship checklist**: the questions SR must be able to answer and the behavioural tests that indicate SR is “correct enough” to implement and integrate.

### 12.1 Acceptance questions (SR must be able to answer these unambiguously)

These are phrased as “platform operator / downstream consumer” questions:

1. **What run is this?**

* Given any SR artifact or READY signal, can I identify:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` (and window key, if used)?

2. **Where do I read from?**

* Given `run_id` (or READY), can I locate `run_facts_view` deterministically?
* Does `run_facts_view` give me pointers to the authoritative engine outputs I need?

3. **Is it safe to proceed?**

* What does READY mean, precisely?
* Which PASS artifacts/evidence justify READY for this run?

4. **What happened during execution?**

* Can I reconstruct (at a coarse level) attempts, retries, and outcomes from `run_record`?

5. **If I submit the same request twice, what happens?**

* Does SR dedupe and avoid duplicate side effects?
* What is the idempotency key / equivalence rule?

6. **If the engine fails, what happens?**

* Does SR record failure with a standard category and evidence pointers?
* Does SR avoid emitting READY or misleading downstream?

7. **Can I replay it?**

* Can SR reproduce the same outward-facing result (refs/pins/outcome) from the ledger?
* Does replay avoid mutating history or silently switching worlds?

8. **Can I reuse world outputs safely?**

* Under what evidence-based conditions will SR reuse rather than rebuild?

9. **What is the lifecycle state right now?**

* Can I determine state (OPEN/READY/FAILED/QUARANTINED/CLOSED) deterministically from `run_status`?

10. **How do I find the “right” run for a given purpose?**

* If “latest READY” exists, is the selection deterministic and explainable?
* If “run for window X” exists, can I locate it without scanning timestamps?

---

### 12.2 Definition of Done (conceptual test scenarios)

These are the minimum behavioural scenarios that, if satisfied, indicate SR is ready to integrate.

#### DoD-1: Same request twice → no duplicate side effects

**Given**

* the same logical Run Request is submitted twice (or SR is retried after partial progress)

**Expect**

* SR does not create duplicate run identities (per your equivalence rule)
* SR does not duplicate:

  * engine invocation (if reuse is appropriate)
  * READY/dispatch signals
  * ledger artifacts beyond safe idempotent updates

---

#### DoD-2: Missing required PASS evidence → SR never emits READY

**Given**

* engine completion evidence is missing required PASS artifacts (or refs are not resolvable)

**Expect**

* SR does not emit READY
* SR records a failure/quarantine outcome with evidence pointers
* `run_status` reflects a terminal non-ready state

---

#### DoD-3: Engine FAIL → SR records failure and does not greenwash

**Given**

* engine invocation fails (dependency failure)

**Expect**

* SR records failure category + reason (taxonomy)
* `run_record` captures attempt(s) and final outcome
* SR does not emit READY or any signal that could be interpreted as safe-to-read

---

#### DoD-4: Reuse works when evidence matches

**Given**

* a prior engine output set exists for the pins and required PASS evidence is present

**Expect**

* SR can complete in REUSE mode without re-invoking the engine
* SR records reuse evidence and still produces fresh SR ledger artifacts (or references existing SR ledger under explicit reuse policy)

---

#### DoD-5: Replay reproduces outcome from ledger truth

**Given**

* a completed run exists with SR ledger artifacts

**Expect**

* SR can replay in a way that re-materializes the outward-facing outcome:

  * same pins
  * same facts view references
  * same READY/failure outcome
* Replay does not mutate engine outputs or reinterpret “latest” selection rules

---

#### DoD-6: READY is monotonic

**Given**

* SR has declared a run READY

**Expect**

* SR does not later mark that same run FAILED/NOT-READY
* If an issue is discovered, SR produces a **new run** instead of rewriting history

---

#### DoD-7: Local vs deployed semantics match

**Given**

* the same Run Request is executed locally and in a deployed environment

**Expect**

* the meaning of outputs is consistent:

  * same identity pins
  * same readiness semantics
  * same ledger interpretation
* differences are only mechanical (paths, transport) and are represented via locators, not semantic drift

---

### 12.3 Minimal deliverables required to claim “DoD satisfied”

To claim SR meets DoD at v1 conceptual level, you should be able to show:

* a validated `RunRequest`
* a populated `run_plan`
* an append-only `run_record` with at least one attempt and one outcome entry
* a `run_facts_view` that downstream can consume without guessing
* a `run_status` consistent with lifecycle laws
* a READY (or terminal) signal that points to `run_facts_view`

---

## 13) Open decisions log (explicit placeholders)

> This is the “decision backlog” SR must eventually pin in SR1–SR5 and/or `contracts/`. Until closed, each item stays **OPEN** and the coding agent must not invent semantics.

### 13.0 How decisions get closed

* Each decision gets an ID: `DEC-SR-###`
* Status: **OPEN** → **CLOSED**
* When CLOSED, the canonical wording lives in **SR specs** (behaviour) and/or **contracts** (shape), with a pointer back to the decision ID.

---

### 13.1 Identity, equivalence, and idempotency

* **DEC-SR-001 — Run equivalence rule (what is “same run”)**
  *Open question:* which fields define sameness for idempotency?
  *Close in:* **SR3** (+ referenced in SR2)

* **DEC-SR-002 — ID minting posture (`scenario_id`, `run_id`)**
  *Options:* caller-supplied vs SR-minted vs deterministic derivation.
  *Close in:* **SR3** (+ reflected in contracts if required fields change)

* **DEC-SR-003 — Side-effect idempotency keys (per effect kind)**
  *Open question:* enumerate SR side-effects + idempotency key for each.
  *Close in:* **SR4/SR5** (behaviour) + **contracts** (fields if needed)

---

### 13.2 Time and window semantics

* **DEC-SR-004 — Window key representation**
  *Options:* `window_id` vs `{start,end,tz}` vs both.
  *Close in:* **SR3** (+ propagated through all public artifacts in contracts)

* **DEC-SR-005 — “No hidden now” policy details**
  *Open question:* if callers say “today”, who converts to explicit window key and how is it recorded?
  *Close in:* **SR3**

---

### 13.3 World pinning and selection

* **DEC-SR-006 — Are world pins always explicit?**
  *Options:* require explicit `manifest_fingerprint` always vs allow SR selection.
  *Close in:* **SR3**

* **DEC-SR-007 — Deterministic selection rule (if selection is allowed)**
  *Open question:* what does “latest PASS” mean, tie-breakers, evidence recorded.
  *Close in:* **SR3** (+ may require index artifacts in SR5)

---

### 13.4 Reuse, replay, resume modes

* **DEC-SR-008 — Supported run modes in v1**
  *Options:* REUSE / REBUILD / REPLAY / RESUME (subset).
  *Close in:* **SR3**

* **DEC-SR-009 — Evidence required for reuse**
  *Open question:* what must exist (refs + PASS) before reuse is allowed.
  *Close in:* **SR3/SR4**

* **DEC-SR-010 — Replay semantics**
  *Open question:* re-emit only vs re-verify gates vs re-register facts; what replay never does.
  *Close in:* **SR3**

---

### 13.5 Readiness gates and verification standard

* **DEC-SR-011 — Required PASS gate set for READY**
  *Open question:* enumerate required PASS artifacts (engine + SR) for v1.
  *Close in:* **SR4** (+ referenced in SR5 facts view semantics)

* **DEC-SR-012 — Minimum verification standard**
  *Options:* existence-only vs PASS-flag presence vs digest checks.
  *Close in:* **SR4**

* **DEC-SR-013 — Partial readiness posture**
  *Options:* all-or-nothing vs defined partial states (harder).
  *Close in:* **SR4**

---

### 13.6 Failure, retry, quarantine

* **DEC-SR-014 — Retry budget + classification**
  *Open question:* what is retriable, how many attempts, when to stop.
  *Close in:* **SR4**

* **DEC-SR-015 — Quarantine vs fail-fast rules**
  *Open question:* what conditions quarantine a run vs immediate fail.
  *Close in:* **SR4** (+ aligned with FailureTaxonomy in contracts)

* **DEC-SR-016 — Failure taxonomy categories**
  *Open question:* final category set + retryability flags.
  *Close in:* **contracts** (shape) + **SR4** (behaviour)

---

### 13.7 Ledger artifact semantics and lifecycle

* **DEC-SR-017 — Lifecycle state model + monotonic transitions**
  *Open question:* states and allowed transitions (OPEN→READY/FAILED/QUARANTINED→CLOSED, etc.).
  *Close in:* **SR4/SR5** (+ state enum in contracts)

* **DEC-SR-018 — Immutability rules per artifact**
  *Open question:* which are append-only vs versioned vs overwritten (ideally minimal overwrites).
  *Close in:* **SR5**

* **DEC-SR-019 — READY source-of-truth**
  *Options:* event only vs artifact marker vs status endpoint (or combination).
  *Close in:* **SR5** (+ RunReadySignal contract if event)

---

### 13.8 Contracts and validation targeting

* **DEC-SR-020 — Validation targeting rule**
  *Options:* `kind` + `contract_version` self-describing vs path→$defs mapping.
  *Close in:* **SR2** (+ enforced in contracts)

* **DEC-SR-021 — ArtifactRef/Locator minimum fields**
  *Open question:* what locator fields are mandatory (producer, locator, digest optional?).
  *Close in:* **contracts** (+ referenced in SR5)

---

### 13.9 Addressing, discoverability, retention

* **DEC-SR-022 — Canonical run-ledger path template**
  *Open question:* exact directory structure and required filenames.
  *Close in:* **SR5**

* **DEC-SR-023 — “Latest READY” support**
  *Open question:* does this concept exist; if yes, deterministic selection + indexing approach.
  *Close in:* **SR5**

* **DEC-SR-024 — Retention policy for ledger artifacts**
  *Open question:* how long to keep, archive strategy (conceptual).
  *Close in:* **SR5** (or platform governance docs, if centralized)

---

## Appendix A — Examples (inline)

> **Note (conceptual, non-binding):** These examples are *illustrative payloads* to lock shared understanding.
> They intentionally use `kind` + `contract_version` and show a **single join style**: downstream starts from **READY → RunFactsView → ArtifactRefs**.
> For the time key, this appendix uses a `{start,end,tz}` window object; you can swap that for `window_id` later (DEC-SR-004).

---

### A.1 Example — `RunRequest` (what SR accepts)

```json
{
  "kind": "run_request",
  "contract_version": "sr_public_contracts_v1",

  "scenario_intent": {
    "scenario_ref": "baseline_v1",
    "sla_class": "standard",
    "run_mode": "REUSE_WORLD"
  },

  "window": {
    "start": "2026-01-03T00:00:00Z",
    "end": "2026-01-04T00:00:00Z",
    "tz": "UTC"
  },

  "world_pins": {
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "identity_policy": {
    "scenario_id": "scn_baseline_v1",
    "run_id_policy": "SR_MINT",
    "idempotency_key": "ik_scn_baseline_v1_mf_20251231T235959Z_8f3c2a1d_ph_4b1d7a9c_2026-01-03"
  }
}
```

---

### A.2 Example — `RunFactsView` (canonical pins + refs join surface)

```json
{
  "kind": "run_facts_view",
  "contract_version": "sr_public_contracts_v1",

  "scenario_id": "scn_baseline_v1",
  "run_id": "run_20260103T110000Z_0001",
  "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
  "parameter_hash": "ph_4b1d7a9c",

  "window": {
    "start": "2026-01-03T00:00:00Z",
    "end": "2026-01-04T00:00:00Z",
    "tz": "UTC"
  },

  "sr_ledger": {
    "run_plan": {
      "producer": "scenario_runner",
      "kind": "run_plan",
      "uri": "<ARTIFACT_ROOT>/sr/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/run_plan.json"
    },
    "run_record": {
      "producer": "scenario_runner",
      "kind": "run_record",
      "uri": "<ARTIFACT_ROOT>/sr/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/run_record.jsonl"
    },
    "run_status": {
      "producer": "scenario_runner",
      "kind": "run_status",
      "uri": "<ARTIFACT_ROOT>/sr/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/run_status.json"
    }
  },

  "engine_evidence": {
    "engine_run_receipt": {
      "producer": "data_engine",
      "kind": "engine_run_receipt",
      "uri": "<ARTIFACT_ROOT>/fingerprint=mf_20251231T235959Z_8f3c2a1d/runs/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/engine_run_receipt.json"
    },
    "required_pass_artifacts": [
      {
        "producer": "data_engine",
        "kind": "engine_pass_flag",
        "uri": "<ARTIFACT_ROOT>/fingerprint=mf_20251231T235959Z_8f3c2a1d/runs/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/_passed.flag"
      }
    ]
  },

  "authoritative_outputs": [
    {
      "producer": "data_engine",
      "kind": "engine_output_catalogue",
      "uri": "<ARTIFACT_ROOT>/fingerprint=mf_20251231T235959Z_8f3c2a1d/runs/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/outputs/index.json"
    }
  ]
}
```

---

### A.3 Example — `RunReadySignal` (what downstream consumes)

```json
{
  "kind": "run_ready_signal",
  "contract_version": "sr_public_contracts_v1",

  "scenario_id": "scn_baseline_v1",
  "run_id": "run_20260103T110000Z_0001",
  "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
  "parameter_hash": "ph_4b1d7a9c",

  "window": {
    "start": "2026-01-03T00:00:00Z",
    "end": "2026-01-04T00:00:00Z",
    "tz": "UTC"
  },

  "status": "READY",

  "facts_view_ref": {
    "producer": "scenario_runner",
    "kind": "run_facts_view",
    "uri": "<ARTIFACT_ROOT>/sr/scenario_id=scn_baseline_v1/run_id=run_20260103T110000Z_0001/run_facts_view.json"
  },

  "signal_idempotency_key": "sig_ready_scn_baseline_v1_run_20260103T110000Z_0001"
}
```

## Appendix B — Sequence diagrams (ASCII)

> **Legend:**
> `->` call/command `-->` read/poll `=>` write/emit
> Bracket notes like `[idemp=…]` indicate where an idempotency key (or run equivalence key) is applied.

---

### B.1 Happy path (engine invoked, gates PASS, READY emitted)

```
Participants:
  Caller | SR (Resolve&Pin) | SR (Plan) | SR (Execute) | Data Engine | SR (Verify&Register) | SR (Emit&Close)
         | Artifact Store   | Event Bus | Downstream

Caller -> SR (Resolve&Pin): Submit RunRequest [idemp=RunEquivalenceKey]
SR (Resolve&Pin) => Artifact Store: write run_plan (draft) + run_record START
SR (Resolve&Pin) => Artifact Store: write run_status = OPEN

SR (Plan) => Artifact Store: update run_plan (steps + required_gates)

SR (Execute) -> Data Engine: EngineRunRequest (pins + scenario_id/run_id + window if needed)
Data Engine => Artifact Store: write engine outputs + engine_run_receipt
Data Engine => Artifact Store: write required PASS artifacts (e.g., _passed.flag)

SR (Verify&Register) --> Artifact Store: read engine_run_receipt + PASS artifacts
SR (Verify&Register) => Artifact Store: write run_facts_view (pins + refs/locators)
SR (Verify&Register) => Artifact Store: write run_status = READY
SR (Verify&Register) => Artifact Store: append run_record (EXEC_OK + VERIFIED_OK)

SR (Emit&Close) => Event Bus: publish RunReadySignal [idemp=sig_ready_<run_id>] (includes facts_view_ref)
Downstream --> Artifact Store: read run_facts_view
Downstream --> Artifact Store: follow refs/locators to engine outputs
```

---

### B.2 Reuse path (evidence exists; engine not invoked)

```
Caller -> SR (Resolve&Pin): Submit RunRequest [idemp=RunEquivalenceKey]
SR (Resolve&Pin) => Artifact Store: write/locate run ledger (OPEN)

SR (Plan) => Artifact Store: run_plan declares mode = REUSE_WORLD + required_gates

SR (Execute) --> Artifact Store: check for existing engine evidence (receipt + PASS) for pins
SR (Execute): (engine invocation skipped)  [reason=reuse_evidence_present]

SR (Verify&Register) --> Artifact Store: read existing engine_run_receipt + PASS artifacts
SR (Verify&Register) => Artifact Store: write run_facts_view (pins + refs/locators)
SR (Verify&Register) => Artifact Store: write run_status = READY
SR (Verify&Register) => Artifact Store: append run_record (REUSE_SELECTED + VERIFIED_OK)

SR (Emit&Close) => Event Bus: publish RunReadySignal [idemp=sig_ready_<run_id>]
Downstream --> Artifact Store: read run_facts_view and follow refs
```

---

### B.3 Failure path (engine fails OR required PASS evidence missing)

```
Caller -> SR (Resolve&Pin): Submit RunRequest [idemp=RunEquivalenceKey]
SR (Resolve&Pin) => Artifact Store: write run_record START; run_status = OPEN
SR (Plan) => Artifact Store: run_plan declares required_gates

SR (Execute) -> Data Engine: EngineRunRequest
Data Engine => Artifact Store: (optional) partial artifacts / error receipt
Data Engine -> SR (Execute): failure (dependency error)  OR  receipt exists but PASS missing

SR (Verify&Register) --> Artifact Store: read receipt / PASS artifacts (missing or FAIL)
SR (Verify&Register) => Artifact Store: write run_status = FAILED or QUARANTINED (with taxonomy + evidence refs)
SR (Verify&Register) => Artifact Store: append run_record (EXEC_FAIL or GATE_FAIL)

SR (Emit&Close) => Event Bus: (optional) publish RunFailureSignal [idemp=sig_fail_<run_id>]
SR (Emit&Close): NO READY emitted
Downstream: does not proceed (no READY; may observe failure via status/signal)
```

---