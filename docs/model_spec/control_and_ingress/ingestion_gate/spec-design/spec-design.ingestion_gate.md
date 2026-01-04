# Conceptual Document Plan — Ingestion Gate (IG)

## 0) Document metadata

### 0.1 Document header

* **Title:** *Ingestion Gate — Conceptual Roadmap (Modular Breakdown + Contract Intent)*
* **Component:** Control & Ingress / Ingestion Gate
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final (choose one)
* **Version:** v0.x (increment on substantive changes)
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Provide a **single, coherent conceptual direction** for Ingestion Gate (IG) before writing IG specs and contracts.
* Enumerate the **questions IG must answer** (by module + contract boundary) to guarantee:

  * trust-boundary correctness (admit vs quarantine; no silent fixing)
  * replay safety under retries/duplicates (dedupe + receipts)
  * cross-component interoperability (canonical envelope + schema authority)
  * auditability and explainability (reason codes + evidence pointers)
* Explicitly separate:

  * **design decisions that must be pinned** (later in IG1–IG5 and contract schemas)
  * **implementation freedoms** left to the implementer

### 0.3 Audience and prerequisites

* **Primary readers:** you (architect/spec author), Codex (implementer)
* **Secondary readers:** reviewers for Control & Ingress, downstream consumers (bus/feature/decision/label/observability)
* **Prerequisites (assumed known):**

  * platform “rails” conventions: identity pins, PASS/no-read posture, lineage discipline
  * Scenario Runner concepts: `run_ready` and `run_facts_view` as join surfaces (only as refs, not internals)
  * your repo/path conventions (e.g., `fingerprint={manifest_fingerprint}` where relevant)

### 0.4 How to use this document

* Use as the **roadmap** for authoring:

  * IG spec set (IG1–IG5), and
  * IG contract pack (2 schema files)
* This document is **not** a machine-checkable authority; contract shapes live in `contracts/`.
* Each “question” here must eventually become:

  * a **pinned decision** in IG specs, or
  * a **schema field/rule** in contracts, or
  * explicitly marked as **implementation freedom**

### 0.5 Non-binding disclaimer

* This document is conceptual and **non-binding**.
* Any normative words (MUST/SHALL/SHOULD) used here are **directional** until captured in:

  * IG specs (binding sections), and/or
  * contract schemas (machine validation)

### 0.6 Scope and non-scope

* **In scope:** IG responsibilities, modular breakdown, boundary contracts intent, admitted/quarantine/receipt artifact families, spec mapping.
* **Out of scope:** feature computation, decisioning/actioning logic, label/case semantics, model training, downstream analytics internals.

### 0.7 Repo placement and related artifacts

* **Proposed location:**
  `docs/model_spec/control_and_ingress/ingestion_gate/CONCEPTUAL.md` (or merge into `README.md` later)
* **Related docs (eventual):**

  * `specs/IG1_...` through `specs/IG5_...`
  * `contracts/ig_public_contracts_v1.schema.json`
  * `contracts/ig_admitted_record_v1.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Ingestion Gate exists

Ingestion Gate (IG) is the platform’s **trust boundary**. Its purpose is to ensure that downstream components only see events that are:

* **canonical** (normalized to a platform-approved envelope),
* **schema-valid** (contract-validated; no guessing),
* **joinable** (anchored to the correct run/world via required pins),
* **replay-safe** (duplicates/retries do not change meaning),
* and **auditable** (every admit/quarantine decision has a receipt and reason).

One sentence: **“Admit or quarantine—never ‘maybe’; and stamp everything so it’s replayable and auditable.”**

---

### 1.2 Where IG sits relative to Scenario Runner (SR)

SR establishes **run identity and readiness** (e.g., via `run_ready` and `run_facts_view`). IG operates as the enforcement layer that ensures events entering the platform can be safely attributed to that run/world context.

Conceptually:

* SR says: “this run is READY; here is the canonical join surface.”
* IG says: “events are admitted only if they can be validated and anchored to a run/world (directly by pins or via an allowed run context ref).”

If IG supports enrichment via a `run_facts_view_ref`, then conceptually:

* enrichment MUST only be performed against a **READY** run context (never against an unready or unknown run).

---

### 1.3 IG’s role in the platform “day-in-the-life”

At a high level, IG is the first strict check in the execution/data plane:

1. Producers emit events (engine stream, decisions/actions, labels, etc.).
2. IG receives those events (stream or batch).
3. IG either:

   * **admits** them into the canonical admitted stream/store, or
   * **quarantines** them with a recorded reason and evidence.
4. IG always emits a **receipt** for each event (or per-event within a batch).
5. Downstream components treat admitted events as “real production-grade inputs” because the trust boundary has been applied.

---

### 1.4 Authority: what IG is the system-of-record for

IG is authoritative for:

* **Admission outcomes**

  * accepted vs rejected vs duplicate
* **Quarantine decisions**

  * what was rejected and why (with evidence pointers)
* **Dedupe outcomes**

  * what “same event” means under IG’s rules and what was done about duplicates
* **Ingestion receipts**

  * durable acknowledgements that allow reconciliation and replay safety
* **Canonical admitted event record**

  * the post-gate form and stamping of admitted events (even if payload remains by-ref)

IG is **not** authoritative for:

* the truth of the world (engine outputs),
* business meaning of decisions,
* or label correctness.

It is authoritative for **whether an event is safe to let through**.

---

### 1.5 What IG explicitly is NOT responsible for (non-scope)

To avoid scope creep, IG does **not**:

* compute features
* run fraud policy or decisioning logic
* “fix” invalid events beyond explicitly permitted normalization
* infer or invent missing schema versions
* re-derive run/world truth from content
* manage model lifecycle or governance beyond emitting auditable receipts/telemetry

IG may annotate events with ingestion metadata, but it does not reinterpret domain payloads.

---

### 1.6 What IG must enable for other components

Other components must be able to rely on IG for:

* **Contract integrity**

  * admitted events conform to known schema versions
* **Joinability**

  * admitted events carry the required pins and can be joined to the correct run/world
* **Replay safety**

  * duplicates/retries don’t create multiple “real” events
* **Auditability**

  * every admit/quarantine decision is explainable via receipts + reason codes + evidence pointers
* **Operational clarity**

  * backpressure/overload behaviour is explicit and observable (no silent dropping)

---

## 2) Core invariants (IG “laws”)

> These are **non-negotiable behaviours**. If later IG specs or implementation contradict any of these, it’s a bug.

### 2.1 Admit or quarantine — never “maybe”

* Every ingested event MUST result in a clear outcome:

  * **ADMITTED**, **QUARANTINED/REJECTED**, or **DUPLICATE** (idempotent outcome).
* IG must not “half-admit” or “best-effort admit” ambiguous events.

---

### 2.2 No silent fixing

* If an event cannot be validated/anchored under IG’s policies, it MUST be quarantined.
* Any normalization/mutation is allowed only if explicitly permitted by IG policy; otherwise IG is strict.

---

### 2.3 Joinability is mandatory for admitted events

* Every admitted event MUST be joinable to the correct run/world context.
* Required pins (e.g., `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`) MUST be present on admitted events, either:

  * supplied on the event, or
  * deterministically enriched from an allowed run context reference.
* If pins conflict with a provided run context reference, IG MUST NOT “pick one”; it MUST quarantine (mismatch is evidence of corruption).

---

### 2.4 Schema authority is enforced

* IG MUST validate against registered schema versions and MUST NOT guess unknown versions.
* Unknown schema versions or invalid payloads MUST be quarantined (or rejected) according to IG policy.

---

### 2.5 Replay safety under duplicates/retries

* IG MUST define a dedupe key (“same event” definition) and enforce idempotent behaviour under retries/duplicates.
* Duplicate events MUST still receive a receipt (not silent drop), and the receipt must be reconcilable (e.g., pointer to the admitted record or explicit duplicate outcome).

---

### 2.6 “Accepted” implies durable admission

* IG MUST NOT issue an **ACCEPTED/ADMITTED** receipt unless the admitted record is durably written (or there is an equivalent atomic guarantee).
* IG must never claim “accepted” and then lose the admitted event.

---

### 2.7 Every decision is attributable (auditability)

* For every event IG processes, IG MUST be able to produce:

  * an outcome (admit/quarantine/duplicate),
  * a reason code (if not admitted),
  * correlation keys (attempt/batch IDs, dedupe key or reference),
  * and evidence pointers (refs to stored records) where applicable.

---

### 2.8 Local vs deployed semantics must match

* IG may run locally (single process) or deployed (distributed), but the meaning of outcomes must be consistent:

  * same event + same contracts + same policy → same outcome
* Differences are allowed only in mechanics (transport, batching, worker topology), not in trust semantics.

---

### 2.9 Overload/backpressure behaviour is explicit

* Under overload, IG MUST follow an explicit posture (buffer/fail/shed-load) and MUST surface it via receipts/telemetry.
* IG must not silently drop events without a traceable outcome.

---

## 3) Terminology and key objects

> These are the nouns used throughout the IG conceptual roadmap. Shapes are conceptual here; exact fields land in IG2/IG4 and the contract schemas.

### 3.1 Producer

A **producer** is any upstream source submitting events into the platform (e.g., engine stream, decision/action stream, label stream). IG treats producers as external and potentially untrusted until validated.

---

### 3.2 Ingest input

An **ingest input** is the raw unit IG receives, either:

* a **single event message**, or
* a **batch wrapper** containing multiple events.

---

### 3.3 Event envelope vs payload

* The **event envelope** is the canonical metadata wrapper used for validation, routing, joinability, and audit.
* The **payload** is the domain-specific content (transaction, decision, action, label, etc.) that may be validated and/or carried by-ref.

**Key idea:** IG primarily enforces the envelope; payload handling depends on your validation posture.

---

### 3.4 Schema reference / schema version

A **schema reference** identifies which contract version the event claims to follow. IG uses this to validate:

* known version → validate
* unknown version → quarantine/reject (no guessing)

---

### 3.5 Identity pins (run/world anchoring)

**Pins** are the identifiers that make events joinable to the correct run/world context, typically including:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

These must be present on admitted events, either supplied directly or enriched deterministically.

---

### 3.6 Run context reference (`run_facts_view_ref`)

A **run context reference** is a pointer to SR’s canonical join surface (e.g., `run_facts_view`). IG may use it to enrich pins when:

* enrichment posture allows it, and
* the referenced run context is READY.

---

### 3.7 Event time vs ingest time

* **`event_time`**: the time the event is considered to have occurred in the simulated/operational timeline.
* **`ingest_time`**: the time IG processed/committed the event.

**Key idea:** IG must distinguish these; it must not overwrite event_time with ingest_time.

---

### 3.8 Ingestion attempt / batch identifiers

* **`ingest_attempt_id`**: unique ID for a single processing attempt (useful for retries).
* **`batch_id`**: identifier for a batch submission (if batching is used).

These are for auditability and reconciliation.

---

### 3.9 Dedupe key and dedupe scope

* A **dedupe key** defines what “the same event” means (e.g., producer + event_id + event_type).
* **Dedupe scope** defines where uniqueness is enforced:

  * per run
  * per producer
  * global
  * time-bounded window

IG must pin both eventually.

---

### 3.10 Receipt

A **receipt** is IG’s authoritative acknowledgement of an ingestion outcome. It records:

* status (ADMITTED / QUARANTINED / DUPLICATE)
* correlation keys (attempt/batch IDs, dedupe key or event key)
* reason code and retryability (if not admitted)
* pointers to the admitted/quarantine records

---

### 3.11 Quarantine record

A **quarantine record** stores rejected events plus:

* reason code(s)
* validation evidence (what failed)
* correlation keys for tracing
* reference to original raw input (by-ref preferred)

---

### 3.12 Admitted event record

An **admitted event record** is the canonical post-gate representation of an event. It includes:

* canonical envelope (pins, schema ref/version, timestamps)
* payload (embedded or by-ref, per policy)
* ingestion stamp (ingest_time, dedupe key, attempt info)

Downstream treats admitted records as trustworthy inputs.

---

### 3.13 Failure taxonomy / reason codes

A controlled vocabulary IG uses to explain decisions, e.g.:

* `MISSING_PINS`, `PIN_MISMATCH`
* `SCHEMA_INVALID`, `UNKNOWN_SCHEMA_VERSION`
* `DEDUP_CONFLICT`
* `SECURITY_VIOLATION`, etc.

Each reason code may carry a retryability flag.

---

## 4) IG as a black box (inputs → outputs)

> This section treats Ingestion Gate (IG) as a single black box: what it **accepts**, what it **produces**, and what boundaries it touches. Shapes are conceptual here; machine-checkable shapes live in `contracts/`.

### 4.1 Inputs (what IG consumes)

#### 4.1.1 Primary input: raw events (stream or batch)

IG consumes event messages or batches emitted by producers. Each input should provide, at minimum:

* a schema reference/version claim (so IG can validate)
* enough identifying information to compute a dedupe key (or to mint one deterministically if your posture allows)
* pins (preferred) or a run context reference (if enrichment is allowed)

#### 4.1.2 Optional input: run context reference (if enrichment is allowed)

If your posture permits enrichment, an input may include:

* `run_facts_view_ref` (or equivalent pointer) so IG can resolve missing pins.

Conceptually:

* IG only enriches from a **READY** run context.
* If both pins and run_ref are present and disagree → quarantine.

#### 4.1.3 Read-only reference context

IG may consult, as read-only dependencies:

* schema registry / contract catalogue (what versions exist)
* run ledger facts surface (for enrichment, if allowed)
* dedupe index / prior receipts (for idempotency decisions)

IG must not treat these as mutable state it “fixes”; it uses them as evidence sources.

---

### 4.2 Outputs (what IG produces)

IG always produces a deterministic outcome per event:

#### 4.2.1 Admitted canonical stream/store

For events that pass policy:

* IG writes an **AdmittedEventRecord** (canonical envelope + stamps + payload per policy)
* IG routes/partitions admitted events by canonical keys to support downstream joinability.

#### 4.2.2 Quarantine stream/store

For events that fail policy:

* IG writes a **QuarantineRecord** containing:

  * original event reference (by-ref preferred)
  * reason code(s) + retryability
  * evidence pointers (what check failed)
  * correlation keys for tracing

#### 4.2.3 Ingestion receipts (system-of-record for intake outcomes)

For every processed event, IG writes/emits a **receipt** describing:

* outcome: ADMITTED / QUARANTINED / DUPLICATE
* correlation keys (attempt/batch IDs; event key/dedupe key)
* pointers to the admitted or quarantine record
* reason taxonomy if not admitted
* minimal timing fields (ingest time, latency class if desired)

#### 4.2.4 Telemetry (observable by operators/governance)

IG emits operational telemetry such as:

* counts by outcome + reason code
* latency distributions
* backlog / backpressure indicators
* per-producer health signals

(Exact metrics are not pinned here; IG specs will define “must-have” fields.)

---

### 4.3 Boundary map (what IG touches)

#### 4.3.1 Upstream producers (untrusted until validated)

* engine stream outputs (transactions/events)
* decision/action events
* labels/case events
* any other platform producer

**Boundary rule:** producers don’t get to redefine schema truth; IG enforces it.

#### 4.3.2 Platform schema authority (contracts)

IG depends on a controlled set of schema versions:

* known version → validate
* unknown version → quarantine/reject (policy-driven, but never guess)

#### 4.3.3 Scenario Runner / run context (optional, by-ref)

If enrichment is allowed, IG consumes run context only via a pointer:

* IG must not assume SR storage internals; it follows `run_facts_view_ref`.

#### 4.3.4 Storage and transport surfaces (conceptual)

IG typically interacts with:

* admitted event store / stream
* quarantine store
* receipt store (and possibly a receipt query surface)
* optional event bus for emitting receipts/signals

**Design point:** storage/transport technology is implementation freedom; semantics of outcomes and receipts are not.

---

## 5) Modular breakdown (Level 1) and what each module must answer

> This is a **trust-boundary pipeline**, not an engine-style state machine. The goal is to force IG’s key design choices (trust, replay, interoperability, audit) to be answered somewhere, while leaving implementation mechanics to the implementer.

### 5.0 Module map (one screen)

IG is decomposed into 6 conceptual modules:

1. **Intake & Framing**
2. **Identity & Lineage Enrichment**
3. **Contract / Schema Enforcement**
4. **Idempotency / Dedupe**
5. **Normalization / Tokenization**
6. **Commit & Route**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 5.1 Module 1 — Intake & Framing

### Purpose (what it is)

Accept raw events (stream or batch) and frame them into a standard internal intake unit with correlation metadata.

### What it owns

* intake boundaries (single message vs batch wrapper)
* assignment/recording of:

  * `batch_id` (if batching)
  * `ingest_attempt_id` (per processing attempt)
* basic framing metadata (producer identity, intake timestamp)

### Questions this module must answer

* Are outcomes **per-event** even when submitted in batches? (recommended: yes)
* What does IG guarantee for batch submissions:

  * per-event receipts always, plus optional batch summary?
* What minimal producer identity must be present (`producer_id`, `event_type`, etc.)?
* What is the retry posture at the intake boundary (if the same batch is resent)?

### Can be left to the implementer

* transport (HTTP/queue/file)
* batching strategy and size limits
* concurrency model and worker topology
* internal queueing/backlog strategy

### Local vs deployed operation

* **Local:** likely synchronous framing; may use small batches
* **Deployed:** may be async/high-throughput; semantics unchanged (still per-event outcomes)

### Conceptual inputs → outputs

* **Input:** raw event(s)
* **Output:** framed intake unit(s) with correlation IDs

---

## 5.2 Module 2 — Identity & Lineage Enrichment

### Purpose

Ensure every event that could be admitted is **joinable** by carrying the required pins (or being enriched deterministically, if allowed).

### What it owns

* enforcement of required pins for admitted events:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` (baseline set)
* optional enrichment using `run_facts_view_ref` (if posture allows)
* pin precedence and mismatch handling

### Questions this module must answer

* What pins are **required** for admission?
* Is enrichment allowed?

  * If yes: what is the allowed run context reference (`run_facts_view_ref`)?
  * What must be true to enrich (e.g., referenced run is READY)?
* If both pins and run_ref are present:

  * what happens on mismatch? (recommended: quarantine)
* What is the behaviour when pins are missing and enrichment is disallowed? (quarantine)

### Can be left to the implementer

* how run_facts_view is resolved (cache vs query vs direct read)
* lookup acceleration/indexing
* caching and TTL policies (as long as semantics remain consistent)

### Local vs deployed operation

* **Local:** may disable enrichment and require explicit pins
* **Deployed:** may allow enrichment, but only with readiness constraints and auditability

### Conceptual inputs → outputs

* **Input:** framed event + optional run context ref
* **Output:** event with required pins present (or routed to quarantine decision path)

---

## 5.3 Module 3 — Contract / Schema Enforcement

### Purpose

Validate the event envelope (and optionally payload) against known schema versions.

### What it owns

* schema authority posture:

  * known version → validate
  * unknown version → quarantine/reject (no guessing)
* validation scope decision (envelope-only vs envelope+payload)

### Questions this module must answer

* What exactly is validated?

  * envelope only?
  * envelope + payload?
* How are unknown schema versions handled? (recommended: quarantine)
* What is the extension posture?

  * allow `extensions{}` bag?
  * allow additionalProperties in defined places?
* What evidence is recorded on validation failure (for quarantine record)?

### Can be left to the implementer

* schema technology and validation library
* schema caching and registry lookup mechanics

### Local vs deployed operation

* semantics identical; deployed may use cached registries for performance

### Conceptual inputs → outputs

* **Input:** pinned/enriched event
* **Output:** validated event (or failure evidence for quarantine)

---

## 5.4 Module 4 — Idempotency / Dedupe

### Purpose

Enforce “effectively-once admission” semantics under duplicates/retries.

### What it owns

* dedupe key computation and enforcement
* dedupe scope definition (run-scoped/global/time-bounded)
* duplicate outcome behaviour and receipt semantics

### Questions this module must answer

* What defines “same event”? (dedupe key components)
* What is dedupe scope (per run / global / per producer / time-bounded)?
* What happens on duplicate?

  * emit DUPLICATE receipt with pointer to existing admitted record (preferred), or
  * emit DUPLICATE receipt with explicit duplicate outcome + correlation keys
* How are dedupe outcomes recorded for replay/audit?

### Can be left to the implementer

* dedupe index storage (db/kv/log)
* locking/concurrency mechanism for dedupe enforcement
* performance optimizations

### Local vs deployed operation

* **Local:** may use in-memory or simple store; semantics identical
* **Deployed:** requires durable dedupe index; semantics unchanged

### Conceptual inputs → outputs

* **Input:** validated event
* **Output:** “first-seen” event for commit OR “duplicate outcome” pathway with receipts

---

## 5.5 Module 5 — Normalization / Tokenization

### Purpose

Apply only those transformations that are explicitly permitted by IG policy, and stamp canonical ingestion metadata.

### What it owns

* normalization policy (what is allowed vs forbidden)
* tokenization/security posture (if IG handles sensitive fields at ingress)
* ingestion stamping (ingest_time, attempt IDs, dedupe key)

### Questions this module must answer

* Is normalization allowed at all?

  * if yes: what transformations are permitted?
* Does IG tokenize/mask any fields? If yes:

  * what is the policy boundary and evidence recorded?
* What ingestion stamp fields are mandatory on admitted records?

### Can be left to the implementer

* exact canonicalization tooling
* tokenization implementation and key management mechanics (if applicable)

### Local vs deployed operation

* **Local:** tokenization may be disabled or mocked
* **Deployed:** tokenization may be enabled; semantics still must be policy-driven and auditable

### Conceptual inputs → outputs

* **Input:** dedupe-cleared event
* **Output:** canonical admitted record (or ready-to-commit record)

---

## 5.6 Module 6 — Commit & Route

### Purpose

Durably write admitted/quarantine records and route events consistently, producing receipts that never lie.

### What it owns

* meaning of “ADMITTED” (durable commit before accepted receipt)
* routing/partitioning keys for admitted stream/store (joinability support)
* quarantine writes and receipt writes
* atomicity posture between record writes and receipts

### Questions this module must answer

* What does “admitted” guarantee? (durable write before ACCEPTED)
* Are commit + receipt atomic? If not, what guarantees prevent “accepted without record”?
* What are canonical partition keys (typically includes `run_id` and/or world pins)?
* Where are quarantine records stored and how are they referenced?
* Backpressure/overload posture:

  * buffer vs fail vs shed-load, and how it’s surfaced

### Can be left to the implementer

* storage backend choices (object store/db/log)
* transport mechanism for admitted stream
* infra/deployment topology

### Local vs deployed operation

* **Local:** simple file/db writes; still must not emit “accepted” without write
* **Deployed:** distributed durable storage; semantics unchanged

### Conceptual inputs → outputs

* **Input:** admitted/quarantine decision + stamped record
* **Output:** admitted record write OR quarantine write + receipts + telemetry increments

---

## 5.7 Cross-module pinned items (summary)

Across all modules, IG must ensure:

* outcomes are explicit (admit/quarantine/duplicate)
* required pins are present on admitted events (or enriched deterministically)
* schema authority is enforced (no guessing)
* dedupe is explicit and receipt-backed
* accepted implies durable commit
* all outcomes are attributable (reason codes + evidence pointers)
* local vs deployed changes mechanics, not semantics

---

## 6) Determinism, replay safety, and trust-boundary model

> This section pins what “correct IG behaviour” means at a conceptual level: deterministic admit/quarantine decisions, replay safety under retries/duplicates, and strict trust-boundary semantics.

### 6.1 What “deterministic IG” means (scope)

IG is deterministic if, given the same:

* input event (envelope + payload or payload ref),
* schema registry state (known versions),
* run context state (if enrichment is allowed),
* and IG policy set (pins required, validation scope, dedupe scope),

IG will produce the same:

* outcome (ADMITTED / QUARANTINED / DUPLICATE),
* receipt meaning (including reason codes and pointers),
* admitted/quarantine record semantics,
  independent of whether it runs locally or deployed.

Determinism does **not** require:

* identical internal batching/concurrency,
* identical log ordering,
* identical storage tech,
  as long as the outward-facing outcome semantics are equivalent.

---

### 6.2 Trust boundary model: “no silent fixing”

IG is the boundary where “untrusted input” becomes “trusted platform events”.

Conceptually:

* If the event cannot be proven joinable and schema-valid under policy → **quarantine**.
* IG does not attempt to “repair” ambiguous or invalid inputs unless a transformation is explicitly permitted and auditable.

This prevents downstream components from inheriting ambiguity and having to guess.

---

### 6.3 Replay safety under retries and duplicates

IG must be safe under the common realities of distributed systems:

* producers may retry
* messages may be duplicated
* batches may be resent
* processing may be restarted mid-way

Replay safety is achieved by:

* an explicit **dedupe key definition**
* a defined **dedupe scope**
* receipts that make duplicates reconcilable (not silent drops)

**Conceptual guarantee:** repeated submission of the “same event” yields a stable idempotent outcome:

* either “already admitted” (with pointer), or “duplicate receipt”, without re-admitting a second copy.

---

### 6.4 Dedupe semantics: what “same event” means (conceptual)

IG must eventually pin:

* the minimum dedupe key components (e.g., `producer_id`, `event_type`, `event_id`, or a deterministic content hash)
* dedupe scope (per run / global / time-bounded)

Conceptually, dedupe must be:

* stable across local vs deployed
* stable across replays
* explainable via receipts / evidence

---

### 6.5 Joinability and lineage anchoring rules

IG ensures admitted events are joinable by enforcing pins.

Conceptually:

* admitted events MUST carry `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` (baseline set)
* pins may be:

  * directly supplied, or
  * enriched via a run context reference (if allowed)

If enrichment is allowed, the trust model must be explicit:

* only enrich from a READY run context
* if pins and run_ref conflict → quarantine

This prevents events being silently attached to the wrong world/run.

---

### 6.6 Time semantics: `event_time` vs `ingest_time`

IG must keep time semantics explicit:

* `event_time` is part of the event’s domain meaning (when it occurred).
* `ingest_time` is part of IG’s audit meaning (when it was processed).

IG must not overwrite event_time during ingestion. If normalization touches time fields, it must be explicitly permitted and auditable.

---

### 6.7 “Accepted implies durable” as a safety guarantee

IG must ensure that operational shortcuts do not violate correctness:

* IG must not emit an ACCEPTED/ADMITTED receipt unless the admitted record is durably written (or equivalently guaranteed).
* If atomicity between admitted write and receipt is not perfect, IG must define a posture that avoids “accepted without record” (e.g., receipt points to a record that must exist).

This guarantee is critical for replay/audit correctness.

---

### 6.8 Backpressure and overload posture (conceptual)

Under overload, determinism requires that IG’s behaviour is explicit and observable.

Conceptually IG must define one posture:

* **buffer** (bounded) and surface backlog,
* **fail** intake requests and surface errors,
* **shed-load** but only with traceable outcomes (receipts/telemetry), never silent drop.

This is part of the trust boundary: overload must not create invisible data loss.

---

### 6.9 Determinism acceptance scenarios (conceptual checklist)

IG should be considered “deterministic enough” when it can satisfy:

* same event resent → DUPLICATE receipt (or pointer), no double-admission
* missing pins (and enrichment disallowed) → quarantine with reason `MISSING_PINS`
* unknown schema version → quarantine with reason `UNKNOWN_SCHEMA_VERSION`
* schema invalid → quarantine with reason `SCHEMA_INVALID`
* pins vs run_ref mismatch → quarantine with reason `PIN_MISMATCH`
* accepted receipt implies admitted record exists durably
* local vs deployed yields the same outcomes given the same inputs and policy

---

## 7) Contracts philosophy and boundary surfaces

> Contracts are how IG stays **machine-checkable** and **interoperable** without exploding into dozens of docs. Contracts define *shape*; specs define *behaviour*.

### 7.1 What a “contract” means for Ingestion Gate

For IG, a contract is a machine-readable definition of:

* what IG **accepts** (ingest input wrappers + canonical envelope expectations),
* what IG **produces** (receipts, quarantine records, admitted records),
* and what IG guarantees at its trust boundary (e.g., required pins present on admitted records).

Contracts exist to prevent:

* producers and consumers drifting on envelope shape,
* “unknown schema version but we tried our best” behaviour,
* incompatible receipt semantics across components,
* and ambiguity during replay/reprocessing.

---

### 7.2 Contracts belong at boundaries (not per internal module)

IG is modularized into 6 conceptual modules, but those modules are not (by default) separate deployable systems. Therefore:

* module semantics live in prose invariants within IG1–IG5,
* contracts exist only where other components integrate.

**Rule:** don’t create a “contract per module” unless you intentionally introduce pluggable providers (e.g., a dispatch provider).

---

### 7.3 Boundary surfaces IG must pin contractually

IG touches three main boundary surfaces:

1. **Ingest surface** (producer → IG)

* what an ingestable event/batch looks like
* required fields for correlation and schema validation
* optional run context reference posture (if allowed)

2. **Receipt surface** (IG → producer/operator/downstream)

* how ingestion outcomes are acknowledged
* dedupe/duplicate outcomes and how they are reconciled
* pointers to admitted/quarantine records

3. **Quarantine/admitted surfaces** (IG → platform)

* canonical admitted record shape (post-gate)
* quarantine record shape (reject evidence and traceability)

Even if implemented as one service, these are the external “faces” that need clear shapes.

---

### 7.4 “Deep spec, few files” contract strategy (2-schema pack)

To match your “reduce horizontal surface” goal, IG should ship:

* a small number of schemas with `$defs` (instead of many tiny schema files)

**Target:**

* `ig_public_contracts_v1.schema.json` (ingest inputs + receipts + quarantine + envelope)
* `ig_admitted_record_v1.schema.json` (post-gate admitted record)

This gives enforceability without repo clutter.

---

### 7.5 Avoiding ambiguity: how consumers know what to validate against

Because the contract file may contain multiple `$defs`, IG must define a deterministic validation targeting rule:

* **Preferred:** self-describing objects

  * every IG object carries `kind` + `contract_version`
  * consumers validate by (`contract_version`, `kind`)

* **Alternative:** binding filename/path → `$defs` mapping rule

  * the specs declare the binding and it is treated as authoritative

**Non-negotiable:** consumers must not guess schema targets.

---

### 7.6 Versioning and compatibility posture (conceptual)

IG contracts must support rapid iteration safely:

* contracts carry explicit version identifiers (v1, v2, …)
* objects emitted by IG declare contract version (or are bound by path rules)
* breaking changes require:

  * new contract version
  * explicit compatibility plan (dual-write, adapters, migrations)
  * spec documentation of what changes and why

---

### 7.7 Relationship to Scenario Runner contracts (minimal coupling)

IG depends on SR only in a minimal, by-ref way:

* if IG supports enrichment, it consumes a `run_facts_view_ref` as a pointer
* IG must not assume SR internals (file layout, storage tech)
* any shared identity pins must use the platform’s canonical definitions (avoid duplication/forking)

This prevents circularity and keeps both components evolvable.

---

## 8) IG contract pack overview (what exists and what it covers)

> This section describes the **contract artifacts** IG will ship with, what each covers, and how consumers use them. Still conceptual: the authored JSON Schemas become the source-of-truth.

### 8.0 Contract pack inventory (target set)

IG will ship **two** machine-checkable schema files:

1. `contracts/ig_public_contracts_v1.schema.json`
   **IG ↔ platform boundary** (ingest input, canonical envelope, receipts, quarantine, failure taxonomy)

2. `contracts/ig_admitted_record_v1.schema.json`
   **Post-gate canonical record** (admitted event record shape + ingestion stamps)

This keeps the contract surface minimal while still enforceable.

---

## 8.1 IG ↔ Platform: `ig_public_contracts_v1.schema.json`

### 8.1.1 What this file is for

This schema defines what IG accepts at ingest and what it emits as outcomes. It is the primary interoperability contract for:

* producers (what to send)
* operators/replayers (how to reconcile outcomes)
* downstream systems that consume receipts/quarantine metadata

### 8.1.2 Common identity + envelope core (shared fields)

IG should define (via a shared `$defs` object) the canonical envelope core fields used across multiple objects, conceptually including:

* producer identity (e.g., `producer_id`, `event_type`)
* schema reference/version (e.g., `schema_name`, `schema_version`)
* time fields (`event_time`, `ingest_time` separation)
* required join pins (baseline set):

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* optional `run_facts_view_ref` (if enrichment is supported)

**Principle:** the envelope is the stable join/audit surface; payload may evolve.

### 8.1.3 Target `$defs` (conceptual list)

Within `ig_public_contracts_v1.schema.json`, define `$defs` for:

1. **`IngestInput`**

* supports:

  * single-event submissions
  * batch wrapper submissions (list of events + batch metadata)
* includes correlation fields (batch_id, attempt_id where relevant)

2. **`CanonicalEventEnvelope`**

* required pins and metadata needed for admission
* schema reference/version fields
* event_time vs ingest_time fields
* producer identity fields

3. **`RunContextRef`** (if enrichment is allowed)

* pointer to SR’s `run_facts_view` (by-ref only)
* enough fields to validate it refers to a run context (no guessing)

4. **`IngestReceipt`**

* outcome enum: `ADMITTED` / `QUARANTINED` / `DUPLICATE`
* correlation keys:

  * `ingest_attempt_id`, `batch_id` (optional), event key / dedupe key
* pointers:

  * admitted record ref (if admitted)
  * quarantine record ref (if quarantined)
  * existing admitted ref (if duplicate, preferred)
* reason code + retryability (if not admitted)
* minimal timing fields (ingest_time, latency_ms optional)

5. **`QuarantineRecord`**

* reference to original raw input (by-ref preferred)
* reason codes + retryability
* evidence pointers (what failed: pins missing, schema invalid, mismatch, etc.)
* correlation keys for tracing
* optional “resolution hints” (e.g., what to fix), if you choose

6. **`FailureTaxonomy`**

* controlled vocabulary of reason codes:

  * `MISSING_PINS`, `PIN_MISMATCH`
  * `UNKNOWN_SCHEMA_VERSION`, `SCHEMA_INVALID`
  * `DEDUP_CONFLICT`, `SECURITY_VIOLATION`, etc.
* includes retryability posture per category (or a flag field on receipts)

7. **(Optional but recommended) `ArtifactRef` / `Locator`**

* standard reference type reused in receipts/quarantine:

  * `producer` (ingestion_gate, scenario_runner, engine, etc.)
  * `kind`
  * `uri` (path/URI/key)
  * optional integrity: digest/size/content_type

**Lean approach:** define `ArtifactRef` once and reuse it everywhere by `$ref`.

### 8.1.4 Validation targeting (how consumers know what to validate)

Because this file contains multiple `$defs`, IG must adopt one targeting rule:

* **Preferred:** self-describing objects:

  * `kind` + `contract_version`
* **Alternative:** binding filename/path → `$defs` mapping

Same rule used by SR is preferred for platform consistency.

---

## 8.2 Post-gate canonical record: `ig_admitted_record_v1.schema.json`

### 8.2.1 What this file is for

This schema defines the **canonical admitted record** shape that downstream treats as trusted, post-gate input. It is separated so storage/stream format can evolve without changing the ingest/receipt boundary contract.

### 8.2.2 Target `$defs` (conceptual list)

Within `ig_admitted_record_v1.schema.json`, define `$defs` for:

1. **`AdmittedEventRecord`**

* canonical envelope (pins, schema ref/version, producer identity)
* payload:

  * either embedded payload (if you validate payload),
  * or payload pointer/ref (if you keep payload by-ref)
* ingestion stamping (see below)

2. **`IngestionStamp`**

* `ingest_time_utc`
* `ingest_attempt_id`
* `batch_id` (if applicable)
* `dedupe_key`
* optional processing metadata:

  * normalisation flags applied
  * tokenization flags applied
  * processing latency fields

3. **(Optional) `PartitionKeys`**

* explicit partition fields if you want them machine-validated:

  * `run_id` and/or `manifest_fingerprint`
  * `producer_id` and/or `event_type`

### 8.2.3 Relationship to `ig_public_contracts_v1`

* `AdmittedEventRecord` should reference the same envelope core definitions as `ig_public_contracts_v1` (avoid divergence).
* Receipts should point to admitted records via `ArtifactRef/Locator`.

---

## 8.3 Contracts vs specs (division of labour)

### 8.3.1 Contracts cover (shape/structure)

* required fields and types
* allowed enums (receipt outcomes, reason codes)
* presence of pins on admitted records
* locator/reference shapes
* batch wrapper shape (if supported)

### 8.3.2 Specs cover (behaviour/invariants)

* admit vs quarantine rules and precedence
* enrichment rules (READY requirement, mismatch handling)
* validation scope and compatibility posture
* dedupe key and dedupe scope semantics
* commit semantics (“accepted implies durable”)
* overload/backpressure posture
* what evidence is recorded on failures

---

## 8.4 Naming and versioning posture (conceptual)

* contract filenames include explicit version (`*_v1.schema.json`)
* emitted objects declare `contract_version` (or are bound by path rule)
* breaking changes:

  * new version (v2)
  * explicit compatibility plan
  * spec documentation for migration

---

## 9) Addressing, naming, and discoverability (conceptual)

> This section defines the *idea* of how admitted/quarantine/receipt artifacts are addressed and found. The goal is: **reconcile without guessing**, and make replay/debugging possible from receipts alone.

### 9.1 Design goals (why addressing matters)

IG addressing must support:

* **Reconciliation:** producers/operators can answer “what happened to my event?”
* **Replay safety:** duplicates map to stable outcomes and references
* **Auditability:** every admit/quarantine decision points to durable evidence
* **Deterministic discovery:** no “scan the latest file and hope”
* **Environment independence:** local vs deployed uses different locator types, same meaning

---

### 9.2 Addressing keys (what IG indexes by)

At minimum, IG outcomes should be discoverable by one or more of:

* **event identity** (e.g., `event_id` + `producer_id` + `event_type`)
* **dedupe key** (IG’s canonical “same event” identifier)
* **receipt key** (e.g., `receipt_id` or `ingest_attempt_id`)
* **run pins** (e.g., `run_id`, plus world pins) for partitioning and bulk queries

**Principle:** receipts must carry enough keys so operators don’t need to inspect raw streams.

---

### 9.3 Canonical locator/ref type (how IG points to things)

IG should use a single reference type (e.g., `ArtifactRef/Locator`) in:

* receipts
* quarantine records
* optional audit logs

Conceptually, `ArtifactRef` includes:

* `producer` (ingestion_gate / scenario_runner / data_engine / etc.)
* `kind` (admitted_record / quarantine_record / receipt / raw_input_ref)
* `uri` (path/URI/key)
* optional integrity metadata (digest/size/content_type)
* optional contract targeting (kind + contract_version)

**Principle:** downstream reads **refs**, not implied paths.

---

### 9.4 Admitted record addressing (conceptual)

Admitted records should be written to a stable location that supports:

* partitioning by join pins (at least `run_id` and/or `manifest_fingerprint`)
* lookup by dedupe key or event identity if you maintain an index

A simple conceptual template:

* `.../admitted/run_id={run_id}/producer_id={producer_id}/event_type={event_type}/...`

(Exact layout is implementation freedom, but partition keys should be stable and documented.)

Receipts for admitted events must include an `admitted_record_ref` pointing to this location.

---

### 9.5 Quarantine record addressing (conceptual)

Quarantine records should be stored in an inspectable location, partitioned so triage is easy:

* by reason code and/or by run pins
* optionally by producer

A conceptual template:

* `.../quarantine/reason={reason_code}/run_id={run_id}/...`

Receipts for quarantined events must include a `quarantine_record_ref` pointing to this record.

Quarantine records should carry a pointer to the original raw input (by-ref preferred).

---

### 9.6 Receipt addressing and lookup (conceptual)

Receipts must enable deterministic answers to:

* “Was this event admitted?”
* “If duplicate, what was the original admitted record?”
* “If quarantined, why?”

Receipts should therefore include:

* an outcome enum
* correlation keys (attempt/batch IDs)
* dedupe key (or event identity key)
* refs to admitted/quarantine records
* reason codes + retryability (if not admitted)

Receipt storage options (implementation freedom):

* append-only receipt log (query by key)
* key/value store keyed by dedupe key
* per-run receipt partitions

**Non-negotiable:** there must be a deterministic way to locate the receipt outcome without scanning “latest”.

---

### 9.7 Batch semantics and discoverability

If IG accepts batches:

* outcomes are conceptually **per-event**
* you may optionally emit a **batch summary receipt** (counts + references), but it must not replace per-event receipts.

Batch discoverability should support:

* lookup by `batch_id`
* enumeration of per-event receipt refs within that batch (if needed)

---

### 9.8 Local vs deployed addressing (same semantics, different locator types)

* **Local:** `uri` may be a filesystem path under a local artifact root.
* **Deployed:** `uri` may be an object-store URI, database key, or stream offset pointer.

**Rule:** the meaning of refs is stable:

* receipt points to evidence that must exist
* “accepted implies admitted record exists durably” holds in both environments

---

### 9.9 Minimal integrity/lineage posture (conceptual)

IG can start lean, but should never be ambiguous:

* receipts must reference admitted/quarantine records
* quarantine records must reference raw input evidence (by-ref)
* optional digests strengthen audit, but are not required in the conceptual doc unless you choose to pin them

---

## 10) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Ingestion Gate docs and contracts. The goal is a **single, deep reading surface** for IG design, plus **minimal machine-checkable contracts**.

### 10.1 Target location in repo

Conceptually, IG lives under Control & Ingress:

* `docs/model_spec/control_and_ingress/ingestion_gate/`

This folder should be self-contained: a new contributor should understand IG by starting here.

---

### 10.2 Proposed skeleton (lean, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ control_and_ingress/
      └─ ingestion_gate/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ IG1_charter_and_boundaries.md
         │  ├─ IG2_interface_and_canonical_envelope.md
         │  ├─ IG3_validation_and_normalisation_policy.md
         │  ├─ IG4_dedupe_receipts_quarantine.md
         │  └─ IG5_commit_routing_ops_acceptance.md
         │
         └─ contracts/
            ├─ ig_public_contracts_v1.schema.json
            └─ ig_admitted_record_v1.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; collapse to 2 files (as above) to avoid sprawl.

---

### 10.3 What each file is for (intent)

#### `README.md`

* Entry point: what IG is, why it exists, and how to read the folder.
* Links to:

  * `CONCEPTUAL.md` (roadmap)
  * `specs/` reading order (IG1–IG5)
  * `contracts/` schemas

#### `CONCEPTUAL.md`

* This roadmap document:

  * IG purpose in the platform
  * core invariants (“laws”)
  * modular breakdown and the questions each module must answer
  * contracts philosophy and coverage
  * addressing/discoverability concepts

This doc is directional alignment, not a binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * contracts are source-of-truth for shapes
  * specs are source-of-truth for behavioural semantics
* Non-negotiables to guard:

  * no silent fixing
  * joinability pins required
  * schema authority (unknown version → quarantine)
  * dedupe + receipts for replay safety
  * accepted implies durable admission

#### `specs/`

* The eventual binding-ish IG design docs (IG1–IG5).
* Inline:

  * examples
  * ASCII sequences/diagrams
  * decision rationales
    to avoid extra folders under deadline.

#### `contracts/`

* Machine-checkable schema artifacts.
* Purpose: enforce boundary shapes and prevent drift between producers/consumers.

---

### 10.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (design direction)
3. `specs/IG1_...` → `specs/IG5_...` (behaviour/invariants)
4. `contracts/*.schema.json` (machine-checkable truth)

For implementation: Codex treats

* `contracts/` as source-of-truth for shapes,
* `specs/` as source-of-truth for behaviour.

---

### 10.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge IG1–IG5 into fewer spec files once stable.
* Add a `contracts/README.md` only if you need a short note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders unless reuse later becomes valuable.

---

## 11) What the eventual spec docs must capture (mapping from this concept doc)

> This section bridges the conceptual roadmap into the **actual IG spec docs** (IG1–IG5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 11.0 Mapping rule (how to use this section)

For every “law” and “question” in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in IG1–IG5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared **implementation freedom**.

---

## 11.1 IG1 — Charter & boundaries

### IG1 must capture

* IG’s role as the platform’s **trust boundary**
* Authority boundaries:

  * what IG is system-of-record for (admit/quarantine decisions, receipts, dedupe outcomes)
  * what IG is not responsible for (feature computation, decisioning, “fixing” events)
* Core invariants (IG “laws”) in enforceable prose:

  * admit/quarantine/duplicate outcomes
  * no silent fixing
  * joinability required
  * schema authority enforced
  * accepted implies durable
  * auditability via receipts
* Boundary map:

  * producers → IG → admitted/quarantine/receipts → downstream

### IG1 may leave to the implementer

* transport stack, concurrency model, deployment topology
* internal pipeline decomposition beyond the conceptual modules

---

## 11.2 IG2 — Interface & canonical envelope

### IG2 must capture

* The ingest interface semantics:

  * single vs batch submissions
  * per-event outcomes (recommended) and batch summary posture (optional)
* The canonical event envelope:

  * required pins and metadata fields
  * schema reference/version fields
  * event_time vs ingest_time semantics (at interface level)
* Enrichment posture:

  * whether `run_facts_view_ref` is allowed
  * precedence + mismatch rules (pins vs ref)
  * READY requirement for enrichment
* Contract targeting rule (pin once):

  * `kind + contract_version` preferred, or path→$defs binding

**Appendix (recommended): Contract Map (v1)**

* lists IG boundary objects (`IngestInput`, `CanonicalEventEnvelope`, `IngestReceipt`, etc.)
* required fields only
* enums referenced and where defined
* extension/compatibility posture (`extensions{}` etc.)

### IG2 may leave to the implementer

* sync vs async intake
* transport type (HTTP/queue/file)
* schema validation tooling choice

---

## 11.3 IG3 — Validation & normalisation policy

### IG3 must capture

* Validation scope:

  * envelope-only vs envelope+payload
* Unknown schema version handling:

  * recommended: quarantine/reject, never guess
* Allowed normalization transformations (if any):

  * what is permitted vs forbidden
* Security/tokenization posture (if applicable):

  * what fields are tokenized and how audit evidence is recorded (conceptual)
* Evidence recording requirements for validation failures (what must appear in quarantine records)

### IG3 may leave to the implementer

* exact validation library and registry caching
* exact canonicalization tooling

---

## 11.4 IG4 — Dedupe, receipts, quarantine

### IG4 must capture

* Dedupe semantics:

  * dedupe key definition (“same event”)
  * dedupe scope (per run/global/time-bounded)
  * behaviour on duplicate (idempotent receipt + pointer preferred)
* Receipt semantics (system-of-record for intake outcomes):

  * fields required for reconciliation
  * accepted implies durable
  * retryability flags and reason codes
* Quarantine taxonomy:

  * controlled vocabulary (reason codes)
  * which are retryable vs terminal
* Pin mismatch and enrichment failure rules (if enrichment supported):

  * mismatch → quarantine, with reason code and evidence pointers

**Appendix (recommended): Ledger/Outcome Map (v1)**

* receipt/outcome object list
* minimum required fields per outcome type
* quarantine evidence fields expectations

### IG4 may leave to the implementer

* dedupe index backend choice
* locking strategy / concurrency mechanism

---

## 11.5 IG5 — Commit, routing, ops & acceptance

### IG5 must capture

* Commit semantics:

  * what “admitted” means (durably written before ACCEPTED receipt)
  * atomicity posture between admitted write and receipt write
* Routing/partitioning keys:

  * must support joinability (usually includes run/world pins)
  * stable keys, independent of deployment
* Overload/backpressure posture:

  * buffer/fail/shed-load rules and how outcomes are surfaced (never silent)
* Acceptance scenarios (Definition of Done):

  * happy path admit
  * duplicates/retries
  * schema invalid / unknown version
  * missing pins / pin mismatch
  * batch partial success handling
  * local vs deployed semantic equivalence

**Appendix (recommended): Admitted Record Contract Map (v1)**

* `AdmittedEventRecord` + `IngestionStamp` required fields
* payload by-ref vs embedded policy
* locator/ref conventions

### IG5 may leave to the implementer

* storage backend (object store/db/log)
* compression/serialization
* worker topology and scaling policies

---

## 11.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* canonical envelope required fields (pins, schema refs, timestamps)
* receipt outcome enums + reason taxonomy shape
* locator/ref structure (`ArtifactRef`)
* admitted record canonical shape + ingestion stamps
* batch wrapper shape (if supported)
* contract targeting rule support (`kind` + `contract_version`, if chosen)

### Specs must include

* behavioural rules:

  * admit vs quarantine precedence
  * enrichment rules + mismatch handling
  * validation scope and unknown-version policy
  * dedupe semantics + duplicate handling
  * accepted implies durable + commit/receipt consistency
  * overload/backpressure posture

---

## 11.7 Minimal completeness standard (so IG is implementable)

IG is “spec-ready” for implementation when IG1–IG5 collectively pin:

* canonical envelope + pin/enrichment posture
* schema authority + validation scope
* dedupe key + scope + duplicate behaviour
* receipt + quarantine semantics (reason codes, retryability)
* admitted commit semantics + routing keys
* overload/backpressure posture
* acceptance scenarios that cover duplicates, schema failures, pin failures

Everything else can remain implementer freedom.

---

## 12) Acceptance questions and “Definition of Done”

> This section is the conceptual **ship checklist** for IG: the questions IG must answer and the minimal behavioural scenarios that indicate IG is correct enough to implement and integrate.

### 12.1 Acceptance questions (IG must answer these unambiguously)

1. **What happened to my event?**

* Given an event identity or dedupe key, can I locate a receipt deterministically?
* Does the receipt tell me ADMITTED / QUARANTINED / DUPLICATE?

2. **If admitted, where is the canonical record?**

* Does the receipt include an `admitted_record_ref` (or equivalent) that can be followed?

3. **If quarantined, why and what evidence exists?**

* Does the receipt/quarantine record include reason code(s) + retryability?
* Does it point to evidence (validation errors, missing pins, mismatch details)?

4. **Is the admitted event joinable to the correct run/world?**

* Are required pins present on the admitted record?
* If enrichment is allowed, was it resolved from a READY run context?

5. **What is “the same event”?**

* What dedupe key definition is used?
* What is the dedupe scope (per run/global/time-bounded)?

6. **What happens on duplicates/retries?**

* If I resend the same event, do I get a deterministic DUPLICATE outcome?
* Do I get a receipt that reconciles to the original admitted record (preferred)?

7. **What does ACCEPTED/ADMITTED guarantee?**

* Does ACCEPTED imply the admitted record is durably written?
* Can I trust that the receipt never lies?

8. **What happens with unknown schema versions?**

* Are unknown versions quarantined/rejected rather than guessed?

9. **What happens if pins are missing or inconsistent?**

* Missing pins and enrichment disallowed → quarantine?
* Pins vs run_ref mismatch → quarantine?

10. **How does IG behave under overload?**

* Buffer, fail, or shed-load?
* Is overload surfaced via receipts/telemetry (never silent drop)?

11. **How are batches handled?**

* Are outcomes per-event even within a batch?
* Can I reconcile per-event receipts and optionally batch summary?

---

### 12.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Happy path admit

**Given**

* a well-formed event with valid schema version and required pins

**Expect**

* IG validates successfully
* IG writes an admitted record
* IG emits an ADMITTED receipt pointing to that record
* admitted record contains required pins and ingestion stamp

---

#### DoD-2: Missing pins (no enrichment) → quarantine

**Given**

* an event missing required pins
* enrichment posture is disabled (or run context ref absent)

**Expect**

* IG quarantines the event with reason `MISSING_PINS`
* IG emits a receipt pointing to the quarantine record
* no admitted record is created

---

#### DoD-3: Pins vs run context mismatch → quarantine

**Given**

* an event provides pins and a `run_facts_view_ref`
* the resolved run context pins conflict with event pins

**Expect**

* IG quarantines with reason `PIN_MISMATCH`
* evidence recorded (which fields conflicted)
* no best-effort “pick one” behaviour

---

#### DoD-4: Unknown schema version → quarantine

**Given**

* an event references an unknown schema version

**Expect**

* IG quarantines/rejects with reason `UNKNOWN_SCHEMA_VERSION`
* receipt includes reason + retryability posture
* no guessing / no downgrade behaviour

---

#### DoD-5: Schema invalid → quarantine

**Given**

* known schema version but invalid envelope/payload per validation scope

**Expect**

* IG quarantines with reason `SCHEMA_INVALID`
* quarantine record stores validation evidence (error summary)
* receipt points to quarantine record

---

#### DoD-6: Duplicate resend → deterministic duplicate outcome

**Given**

* an event is admitted once successfully
* the same event is resent (duplicate)

**Expect**

* IG emits a DUPLICATE receipt
* receipt is reconcilable:

  * points to the original admitted record (preferred), or
  * includes stable correlation keys proving it maps to the original
* IG does not create a second admitted record

---

#### DoD-7: Accepted implies durable write

**Given**

* IG emits an ADMITTED receipt

**Expect**

* the referenced admitted record exists durably and is readable
* IG never produces “accepted without record”

---

#### DoD-8: Batch partial success behaves per-event

**Given**

* a batch with mixed quality events (some valid, some invalid)

**Expect**

* per-event receipts exist for every event
* valid events are admitted; invalid ones quarantined
* optional batch summary receipt may be emitted but does not replace per-event receipts

---

#### DoD-9: Local vs deployed semantics match

**Given**

* the same event stream is ingested locally and in a deployed environment

**Expect**

* same outcomes for each event under the same policy/contract state
* differences are only mechanical (locator types, throughput), not semantic drift

---

#### DoD-10: Overload posture is explicit (no silent drop)

**Given**

* IG is overloaded

**Expect**

* IG follows its defined posture (buffer/fail/shed-load)
* outcomes are still traceable (receipts/telemetry)
* no invisible loss of events

---

### 12.3 Minimal deliverables required to claim “DoD satisfied”

To claim IG meets DoD at v1 conceptual level, you should be able to show:

* validated ingest input handling (single + batch if supported)
* at least one admitted record example
* at least one quarantine record example (with evidence pointers)
* receipts for ADMITTED / QUARANTINED / DUPLICATE
* dedupe behaviour demonstrated by duplicate resend
* proof that “accepted implies admitted record exists”
* minimal telemetry counters by outcome/reason

---

## 13) Open decisions log (explicit placeholders)

> This is the decision backlog IG must eventually pin in IG1–IG5 and/or `contracts/`. Until closed, each item stays **OPEN** and neither the implementer nor downstream consumers should assume semantics.

### 13.0 How decisions get closed

* Each decision gets an ID: `DEC-IG-###`
* Status: **OPEN** → **CLOSED**
* When CLOSED, the canonical wording lives in:

  * IG specs (behaviour), and/or
  * contract schemas (shape),
    with a pointer back to the decision ID.

---

### 13.1 Envelope, pins, and enrichment

* **DEC-IG-001 — Required pins for admission**
  *Open question:* exact minimum pins (`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`, plus any extras).
  *Close in:* **IG2** (+ reflected in contracts)

* **DEC-IG-002 — Enrichment allowed?**
  *Open question:* can IG resolve pins via `run_facts_view_ref`, or must pins always be present?
  *Close in:* **IG2**

* **DEC-IG-003 — Pins vs run context precedence + mismatch rule**
  *Open question:* if event pins conflict with resolved pins from run_ref, what happens?
  *Recommended:* quarantine with `PIN_MISMATCH`.
  *Close in:* **IG2/IG4**

* **DEC-IG-004 — Readiness requirement for enrichment**
  *Open question:* must run_ref resolve to a READY run before enrichment is allowed?
  *Recommended:* yes.
  *Close in:* **IG2**

---

### 13.2 Schema enforcement posture

* **DEC-IG-005 — Validation scope**
  *Open question:* envelope-only vs envelope+payload.
  *Close in:* **IG3** (+ impacts admitted record schema choices)

* **DEC-IG-006 — Unknown schema version handling**
  *Open question:* quarantine vs reject vs other.
  *Recommended:* quarantine/reject, never guess.
  *Close in:* **IG3** (+ reason codes in contracts)

* **DEC-IG-007 — Extension/compatibility posture**
  *Open question:* allow `extensions{}` bag? allow additional properties? where?
  *Close in:* **IG2/IG3** (+ contracts)

---

### 13.3 Dedupe / idempotency

* **DEC-IG-008 — Dedupe key definition (“same event” definition)**
  *Open question:* which fields define “same event” (producer+event_id+type vs content hash).
  *Close in:* **IG4** (+ referenced in receipts)

* **DEC-IG-009 — Dedupe scope**
  *Open question:* per run vs global vs time-bounded vs per producer.
  *Close in:* **IG4**

* **DEC-IG-010 — Duplicate behaviour**
  *Open question:* duplicate receipt points to original admitted record vs explicit duplicate receipt only.
  *Recommended:* pointer to original admitted record.
  *Close in:* **IG4**

---

### 13.4 Normalization / security

* **DEC-IG-011 — Allowed normalization transformations**
  *Open question:* is any normalization allowed? if yes, list allowed transformations.
  *Close in:* **IG3**

* **DEC-IG-012 — Tokenization/security posture at ingress**
  *Open question:* does IG tokenize/mask fields? if yes, which ones and how is it audited?
  *Close in:* **IG3** (or defer to platform security docs if centralized)

---

### 13.5 Commit semantics and atomicity

* **DEC-IG-013 — “Accepted implies durable” mechanism**
  *Open question:* what exact guarantee IG provides and how it avoids “accepted without record”.
  *Close in:* **IG5**

* **DEC-IG-014 — Receipt + record atomicity posture**
  *Open question:* atomic write vs ordered writes with reconciliation guarantees.
  *Close in:* **IG5**

* **DEC-IG-015 — Partitioning/routing keys for admitted stream**
  *Open question:* required partition keys (must support joinability).
  *Close in:* **IG5** (+ may influence admitted record schema)

---

### 13.6 Batch semantics and surfaces

* **DEC-IG-016 — Batch submission semantics**
  *Open question:* per-event receipts always? batch summary receipts?
  *Close in:* **IG2/IG5**

* **DEC-IG-017 — Receipt query surface**
  *Open question:* is there a query API/index for receipts, or is it log-only?
  *Close in:* **IG5** (conceptual; implementation can vary)

---

### 13.7 Failure taxonomy and observability

* **DEC-IG-018 — Quarantine reason code set + retryability flags**
  *Open question:* final controlled vocabulary (MISSING_PINS, SCHEMA_INVALID, etc.).
  *Close in:* **contracts** (shape) + **IG4** (behaviour)

* **DEC-IG-019 — Minimum audit fields (“must log/must metric”)**
  *Open question:* which fields must appear in receipts/logs/metrics for traceability.
  *Close in:* **IG4/IG5**

---

### 13.8 Overload/backpressure posture

* **DEC-IG-020 — Backpressure/overload policy**
  *Open question:* buffer vs fail vs shed-load, and how it is surfaced (receipts/telemetry).
  *Close in:* **IG5**

---

### 13.9 Contracts and validation targeting

* **DEC-IG-021 — Validation targeting rule**
  *Open question:* self-describing `kind+contract_version` vs path→$defs mapping.
  *Close in:* **IG2** (+ enforced in contracts)

* **DEC-IG-022 — ArtifactRef/Locator minimum fields**
  *Open question:* what locator fields are mandatory (producer/kind/uri; digest optional?).
  *Close in:* **contracts** (+ referenced in IG5)

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These payloads are illustrative to lock shared understanding.
> They use `kind` + `contract_version` for unambiguous validation targeting (DEC-IG-021).
> They also keep payload handling minimal (payload is shown embedded for readability; you can switch to by-ref later).

---

### A.1 Example — `IngestInput` (single event)

```json
{
  "kind": "ingest_input",
  "contract_version": "ig_public_contracts_v1",

  "producer": {
    "producer_id": "data_engine",
    "event_type": "transaction_event"
  },

  "ingest_attempt_id": "ia_20260104T110000Z_0001",

  "event": {
    "envelope": {
      "schema_name": "transaction_event_v1",
      "schema_version": "1.0",

      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c",

      "event_time": "2026-01-03T12:34:56Z"
    },

    "payload": {
      "txn_id": "txn_000000123",
      "merchant_id": "m_000045",
      "amount_minor": 1299,
      "currency": "GBP"
    }
  }
}
```

---

### A.2 Example — `IngestInput` (batch wrapper, mixed events)

```json
{
  "kind": "ingest_input_batch",
  "contract_version": "ig_public_contracts_v1",

  "producer": {
    "producer_id": "data_engine",
    "event_type": "transaction_event"
  },

  "batch_id": "batch_20260104T110100Z_0007",
  "ingest_attempt_id": "ia_20260104T110100Z_0007",

  "events": [
    {
      "envelope": {
        "schema_name": "transaction_event_v1",
        "schema_version": "1.0",
        "scenario_id": "scn_baseline_v1",
        "run_id": "run_20260103T110000Z_0001",
        "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
        "parameter_hash": "ph_4b1d7a9c",
        "event_time": "2026-01-03T12:35:10Z"
      },
      "payload": { "txn_id": "txn_000000124", "amount_minor": 499, "currency": "GBP" }
    },
    {
      "envelope": {
        "schema_name": "transaction_event_v1",
        "schema_version": "9.9",
        "scenario_id": "scn_baseline_v1",
        "run_id": "run_20260103T110000Z_0001",
        "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
        "parameter_hash": "ph_4b1d7a9c",
        "event_time": "2026-01-03T12:35:11Z"
      },
      "payload": { "txn_id": "txn_000000125", "amount_minor": 199, "currency": "GBP" }
    }
  ]
}
```

---

### A.3 Example — `IngestReceipt` (ADMITTED)

```json
{
  "kind": "ingest_receipt",
  "contract_version": "ig_public_contracts_v1",

  "producer_id": "data_engine",
  "event_type": "transaction_event",

  "ingest_attempt_id": "ia_20260104T110000Z_0001",
  "batch_id": null,

  "dedupe_key": "ddk_data_engine_transaction_event_txn_000000123",

  "outcome": "ADMITTED",
  "retryable": false,

  "scenario_id": "scn_baseline_v1",
  "run_id": "run_20260103T110000Z_0001",
  "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
  "parameter_hash": "ph_4b1d7a9c",

  "event_time": "2026-01-03T12:34:56Z",
  "ingest_time": "2026-01-04T11:00:02Z",

  "admitted_record_ref": {
    "producer": "ingestion_gate",
    "kind": "admitted_event_record",
    "uri": "<ARTIFACT_ROOT>/ig/admitted/run_id=run_20260103T110000Z_0001/producer_id=data_engine/event_type=transaction_event/txn_000000123.json"
  }
}
```

---

### A.4 Example — `IngestReceipt` (DUPLICATE with pointer to original)

```json
{
  "kind": "ingest_receipt",
  "contract_version": "ig_public_contracts_v1",

  "producer_id": "data_engine",
  "event_type": "transaction_event",

  "ingest_attempt_id": "ia_20260104T110005Z_0002",
  "batch_id": null,

  "dedupe_key": "ddk_data_engine_transaction_event_txn_000000123",

  "outcome": "DUPLICATE",
  "retryable": false,

  "reason_code": "DEDUP_CONFLICT",

  "scenario_id": "scn_baseline_v1",
  "run_id": "run_20260103T110000Z_0001",
  "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
  "parameter_hash": "ph_4b1d7a9c",

  "event_time": "2026-01-03T12:34:56Z",
  "ingest_time": "2026-01-04T11:00:06Z",

  "existing_admitted_record_ref": {
    "producer": "ingestion_gate",
    "kind": "admitted_event_record",
    "uri": "<ARTIFACT_ROOT>/ig/admitted/run_id=run_20260103T110000Z_0001/producer_id=data_engine/event_type=transaction_event/txn_000000123.json"
  }
}
```

---

### A.5 Example — `QuarantineRecord` (UNKNOWN_SCHEMA_VERSION)

```json
{
  "kind": "quarantine_record",
  "contract_version": "ig_public_contracts_v1",

  "producer_id": "data_engine",
  "event_type": "transaction_event",

  "ingest_attempt_id": "ia_20260104T110100Z_0007",
  "batch_id": "batch_20260104T110100Z_0007",

  "dedupe_key": "ddk_data_engine_transaction_event_txn_000000125",

  "outcome": "QUARANTINED",
  "reason_code": "UNKNOWN_SCHEMA_VERSION",
  "retryable": true,

  "scenario_id": "scn_baseline_v1",
  "run_id": "run_20260103T110000Z_0001",
  "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
  "parameter_hash": "ph_4b1d7a9c",

  "event_time": "2026-01-03T12:35:11Z",
  "ingest_time": "2026-01-04T11:01:03Z",

  "raw_input_ref": {
    "producer": "ingestion_gate",
    "kind": "raw_ingest_input",
    "uri": "<ARTIFACT_ROOT>/ig/raw/batch_id=batch_20260104T110100Z_0007/event_idx=1.json"
  },

  "evidence": {
    "schema_name": "transaction_event_v1",
    "schema_version": "9.9",
    "note": "Schema version not registered"
  }
}
```

---

### A.6 Example — `AdmittedEventRecord` (post-gate canonical form)

```json
{
  "kind": "admitted_event_record",
  "contract_version": "ig_admitted_record_v1",

  "envelope": {
    "schema_name": "transaction_event_v1",
    "schema_version": "1.0",

    "producer_id": "data_engine",
    "event_type": "transaction_event",

    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c",

    "event_time": "2026-01-03T12:34:56Z"
  },

  "payload": {
    "txn_id": "txn_000000123",
    "merchant_id": "m_000045",
    "amount_minor": 1299,
    "currency": "GBP"
  },

  "ingestion_stamp": {
    "ingest_time_utc": "2026-01-04T11:00:02Z",
    "ingest_attempt_id": "ia_20260104T110000Z_0001",
    "batch_id": null,
    "dedupe_key": "ddk_data_engine_transaction_event_txn_000000123",
    "normalisation_applied": []
  }
}
```

---

## Appendix B — ASCII sequences (happy path + dup + quarantine)

> **Legend:**
> `->` command/call `-->` read/lookup `=>` write/emit
> `[dedupe=…]` indicates the dedupe key used for idempotency decisions.
> `[receipt=…]` indicates the receipt outcome written/emitted.

---

### B.1 Happy path (valid event → ADMITTED + receipt)

```
Participants:
  Producer | IG(Intake) | IG(Enrich Pins) | IG(Validate) | IG(Dedupe) | IG(Normalize) | IG(Commit&Route)
           | Schema Registry | Run Context (SR facts view) | Admitted Store | Receipt Store | Downstream

Producer -> IG(Intake): submit event
IG(Intake): assign ingest_attempt_id

IG(Enrich Pins): ensure required pins present
  - if pins missing and run_facts_view_ref present:
IG(Enrich Pins) --> Run Context: resolve pins (only if READY)
  - else: use provided pins

IG(Validate) --> Schema Registry: validate schema_name+version (and payload if configured)
IG(Dedupe): compute dedupe key [dedupe=ddk(producer,event_id/type,...)]
IG(Dedupe) --> Receipt Store: check prior outcome for dedupe key

IG(Normalize): apply allowed normalizations (if any) + stamp ingest_time

IG(Commit&Route) => Admitted Store: write AdmittedEventRecord (durable)
IG(Commit&Route) => Receipt Store: write IngestReceipt [receipt=ADMITTED] (points to admitted_record_ref)

Downstream --> Admitted Store: consume admitted record (joinable via pins)
```

---

### B.2 Duplicate resend (same event resent → DUPLICATE receipt, no second admit)

```
Producer -> IG(Intake): resend same event
IG(Intake): assign new ingest_attempt_id

IG(Enrich Pins): pins present (or enrich via READY run ref)
IG(Validate) --> Schema Registry: validate
IG(Dedupe): compute same dedupe key [dedupe=ddk(...)]
IG(Dedupe) --> Receipt Store: prior outcome found for dedupe key (ADMITTED)

IG(Commit&Route): DO NOT write a second admitted record
IG(Commit&Route) => Receipt Store: write IngestReceipt [receipt=DUPLICATE]
  - includes existing_admitted_record_ref (preferred)

Downstream: no duplicate event appears in admitted stream/store
```

---

### B.3 Quarantine path (fail validation/anchoring → QUARANTINED + receipt)

```
Producer -> IG(Intake): submit event
IG(Intake): assign ingest_attempt_id (and batch_id if batch)

IG(Enrich Pins):
  Case A: required pins missing and no run_facts_view_ref
  Case B: pins present but run_facts_view_ref present and conflicts (PIN_MISMATCH)
  Case C: run_facts_view_ref present but run is not READY / not resolvable
  => mark as quarantine candidate (with evidence)

IG(Validate) --> Schema Registry:
  Case D: unknown schema version (UNKNOWN_SCHEMA_VERSION)
  Case E: schema invalid (SCHEMA_INVALID)
  => mark as quarantine candidate (with evidence)

IG(Dedupe): (optional) compute dedupe key for tracking; dedupe does not override quarantine outcome

IG(Commit&Route) => Quarantine Store: write QuarantineRecord (raw_input_ref + reason + evidence)
IG(Commit&Route) => Receipt Store: write IngestReceipt [receipt=QUARANTINED]
  - points to quarantine_record_ref
  - includes reason_code + retryable

Downstream: does not see the event in admitted stream/store
Operator/triage --> Quarantine Store: inspect quarantine record and evidence
```

---