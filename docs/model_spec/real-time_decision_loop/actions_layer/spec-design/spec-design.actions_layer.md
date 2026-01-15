# Actions Layer (AL) — Conceptual Spec Design Doc (non-spec) — Section Header Plan

## 0) Document metadata

### 0.1 Document header

* **Title:** *Actions Layer (AL) — Conceptual Spec Design (v0)*
* **Plane:** Real-Time Decision Loop / Actions Layer
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final
* **Version:** v0.x
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Capture the **designer-locked v0 intent** for Actions Layer in one place (no drift).
* Provide the roadmap for writing:

  * AL1–AL5 specs (behaviour/invariants)
  * `contracts/al_public_contracts_v0.schema.json` (machine-checkable boundary shapes)
* Ensure AL’s semantics are unambiguous:

  * effectively-once execution via idempotency
  * immutable outcomes, append-only attempts history
  * joinability to DF and DLA

### 0.3 Audience and prerequisites

* **Primary:** you (designer), Codex (implementer)
* **Secondary:** DF, DLA, Label/Case, Observability owners
* **Prerequisites:**

  * DF v0 emits ActionIntents with deterministic idempotency keys
  * EB delivers intents/outcomes at-least-once (duplicates possible)
  * DLA records outcomes and joins them to decisions

### 0.4 How to use this document

* This doc is **directional alignment** and a **question map**, not binding spec text.
* Normative truth lives in:

  * AL specs (AL1–AL5), and
  * AL contract schema file
* Every pinned decision here must appear later as a closed decision in specs/contracts.

### 0.5 Scope and non-scope

* **In scope:** ActionIntent input contract, idempotency scope, duplicate handling, retry attempt semantics, ActionOutcome output contract, failure posture, emission semantics, joinability.
* **Out of scope:** exact executor implementations, queue/worker topology, external system protocols, infra deployment details, observability tooling stack.

### 0.6 Proposed repo placement (conceptual)

* `docs/model_spec/real-time_decision_loop/actions_layer/CONCEPTUAL.md`
* Related:

  * `specs/AL1_...` → `specs/AL5_...`
  * `contracts/al_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why the Actions Layer exists

Actions Layer (AL) is the loop’s **side-effect executor + outcome reporter**. Its job is to:

* consume ActionIntents emitted by Decision Fabric,
* execute the intended side effects **effectively once** (via idempotency),
* and emit immutable ActionOutcome events that close the loop for audit and later labeling/case timelines.

One sentence: **“Execute action intents effectively-once, then report outcomes immutably and joinably.”**

---

### 1.2 Where AL sits in the loop

* **Decision Fabric (DF)** produces ActionIntents (idempotent, deterministic keys).
* **AL** executes those intents (approve/decline/step-up/case).
* **EB** may transport intents/outcomes (at-least-once).
* **Decision Log & Audit (DLA)** records outcomes and joins them back to decisions.
* **Label/Case plane** may later consume outcomes to build timelines and truth sets.

AL is the “execution arm” of the decision loop, distinct from decisioning.

---

### 1.3 What AL is system-of-record for (and what it is not)

AL is authoritative for:

* **ActionOutcome truth** (what happened when an intent was executed)
* **idempotent execution posture** (no double-apply under duplicates/retries)
* **attempt history** (append-only outcomes across retries)

AL is not authoritative for:

* the decision itself (DF)
* features/identity context (OFP/IEG)
* stream semantics (EB)
* admission/validation of raw events (IG)

---

### 1.4 Why immutable outcomes matter

Without immutable outcomes:

* audits can’t prove what happened,
* retries become ambiguous,
* and labels/cases cannot reconstruct timelines.

Pinned v0 posture:

* every execution attempt yields an ActionOutcome
* outcomes are append-only; retries create new outcomes; duplicates re-emit the same canonical outcome.

---

### 1.5 What AL must enable for downstream components

Downstream components rely on AL for:

* **idempotency**: retries/duplicates do not double-apply side effects
* **joinability**: outcomes carry ContextPins + decision/request/event ids
* **audit linkage**: DLA can connect intent ↔ outcome history deterministically
* **future label/case timelines**: outcome events provide ground truth of what actually occurred

---

## 2) Core invariants (AL “laws”)

> These are **non-negotiable behaviours** for AL v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Idempotency is mandatory (effectively-once execution)

* AL MUST enforce idempotency using:

  * `(ContextPins, idempotency_key)` as the uniqueness scope.
* AL MUST NOT execute a side effect more than once for the same scope.

### 2.2 Duplicate intents never re-execute

* If AL receives a duplicate ActionIntent (same ContextPins + idempotency_key):

  * AL MUST NOT re-execute the side effect.
  * AL MUST re-emit the same canonical ActionOutcome payload.

### 2.3 Outcome immutability (append-only history)

* ActionOutcomes are immutable once emitted/stored.
* Retries produce new ActionOutcomes (attempt increments).
* Previous outcomes remain part of the history.

### 2.4 Every attempt produces an outcome (no silent attempts)

* For every execution attempt (including failures), AL MUST emit an ActionOutcome.
* No silent queueing of attempts without an outcome event.

### 2.5 Joinability is mandatory

* Every ActionOutcome MUST carry:

  * ContextPins
  * decision_id/request_id/event_id
  * action_type
  * idempotency_key
  * attempt

So DLA and label/case planes can join outcomes back to decisions.

### 2.6 Failure posture is explicit and safe

* If executors are unavailable, AL MUST emit:

  * outcome_status=FAILED
  * retryable=true
  * error_category=EXECUTOR_UNAVAILABLE (or stable equivalent)
* AL must not “hide” failures.

### 2.7 Deterministic output shape and ordering

* ActionOutcome payloads must be deterministic in shape and field normalization.
* Duplicate re-emits must be byte-identical.

---

## 3) Terminology and key objects

> These are the nouns used throughout the AL conceptual design. Exact field shapes live in the AL v0 contract schema; behavioural meaning is pinned in AL specs.

### 3.1 ContextPins

Run/world scoping identifiers:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

All intents and outcomes carry ContextPins.

---

### 3.2 decision_id / request_id / event_id (v0 posture)

In v0 these are aligned:

* `decision_id = request_id = event_id`

AL uses these for joinability to DF and DLA.

---

### 3.3 ActionType (v0 enum)

Pinned action types:

* `APPROVE_TRANSACTION`
* `DECLINE_TRANSACTION`
* `STEP_UP_AUTH`
* `QUEUE_CASE`

---

### 3.4 ActionIntent

The input object AL consumes, containing:

* ContextPins
* decision_id/request_id/event_id
* action_type
* parameters
* idempotency_key

---

### 3.5 idempotency_key

A deterministic key that defines “same intent” for execution:

* uniqueness scope: (ContextPins, idempotency_key)

Duplicate intents share the same idempotency_key.

---

### 3.6 attempt

An integer attempt counter:

* starts at 1
* increments only when AL performs a real retry execution
* duplicates do not increment attempt

---

### 3.7 OutcomeStatus (v0 enum)

Pinned outcome statuses:

* `SUCCEEDED`
* `FAILED`

(Additional statuses like PENDING are explicitly excluded from v0.)

---

### 3.8 ActionOutcome

The output object AL emits, containing:

* ContextPins + decision/request/event ids
* action_type + idempotency_key + attempt
* outcome_status
* started_at_utc, ended_at_utc, emitted_at_utc
* if failed: error_category + retryable
* optional external_ref (opaque)

---

### 3.9 external_ref

An opaque reference to any external/simulated execution artifact:

* gateway response id, simulated receipt, etc.
* kept opaque in v0

---

### 3.10 error_category and retryable

* error_category: stable category string indicating why execution failed
* retryable: boolean indicating whether AL will (or may) retry

Retry budgets are config; the presence and meaning of retryable is pinned.

---

## 4) AL as a black box (inputs → outputs)

> This section treats Actions Layer as a black box: what it consumes, what it produces, and who relies on it.

### 4.1 Inputs (what AL consumes)

#### 4.1.1 Primary input: ActionIntent(s)

AL consumes ActionIntents produced by DF, each containing:

* ContextPins
* decision/request/event ids
* action_type
* parameters
* idempotency_key

AL assumes duplicates and out-of-order delivery are possible (via EB or retries).

#### 4.1.2 Optional execution environment context (implementation detail)

AL may depend on external/simulated executors, but that dependency is not part of the public contract; only outcomes are.

---

### 4.2 Outputs (what AL produces)

#### 4.2.1 ActionOutcome events (public output)

For every intent (and every attempt), AL emits an ActionOutcome containing:

* join keys (pins + ids + idempotency_key)
* status (SUCCEEDED/FAILED)
* timestamps
* retryability and error_category on failure
* optional external_ref

#### 4.2.2 Optional internal receipts (non-contract)

AL may persist internal receipts for execution bookkeeping, but the public contract is the ActionOutcome stream.

---

### 4.3 Boundary map (who consumes AL outputs)

#### 4.3.1 Decision Log & Audit Store (DLA)

* records ActionOutcome history and joins it back to DecisionResponse.

#### 4.3.2 Label/Case plane (later)

* uses outcomes to build timelines and truth sets.

#### 4.3.3 Observability

* consumes outcomes and metrics for execution success, retries, and executor health.

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for AL v0. These decisions are treated as fixed direction for AL specs and the v0 contract schema.

### 5.1 ActionType vocabulary (v0)

Pinned ActionType enum:

* `APPROVE_TRANSACTION`
* `DECLINE_TRANSACTION`
* `STEP_UP_AUTH`
* `QUEUE_CASE`

No additional action types exist in v0.

---

### 5.2 ActionIntent minimum fields (v0)

Every ActionIntent MUST include:

* `context_pins`
* `decision_id` / `request_id` / `event_id`
* `action_type`
* `parameters`
* `idempotency_key` (mandatory)

---

### 5.3 Idempotency scope and duplicate handling (v0)

* Uniqueness scope: `(ContextPins, idempotency_key)`
* Duplicate ActionIntent handling:

  * do not re-execute
  * re-emit the **same canonical ActionOutcome payload** (byte-identical)

---

### 5.4 Attempts and retries (v0)

* `attempt` starts at 1.
* attempt increments only when AL performs a real retry execution.
* every attempt emits an ActionOutcome (append-only history).

---

### 5.5 ActionOutcome minimum fields (v0)

Every ActionOutcome MUST include:

* `context_pins`
* `decision_id/request_id/event_id`
* `action_type`
* `idempotency_key`
* `attempt`
* `outcome_status` ∈ {SUCCEEDED, FAILED}
* `started_at_utc`, `ended_at_utc`, `emitted_at_utc`

If FAILED:

* `error_category` (stable category string)
* `retryable` boolean

Optional:

* `external_ref` (opaque)

---

### 5.6 Failure posture when executor is down (v0)

If execution cannot be performed due to executor/dependency unavailability:

* emit FAILED outcome
* `retryable=true`
* `error_category=EXECUTOR_UNAVAILABLE` (or stable equivalent)

No silent queueing without outcome.

---

### 5.7 Outcome immutability (v0)

* outcomes are append-only and immutable
* retries produce new outcomes with attempt incremented
* duplicates re-emit existing outcome payload unchanged

---

### 5.8 Emission posture (v0)

* ActionOutcomes are emitted to EB (and may also be stored internally; implementation freedom).
* Consumers dedupe on `(ContextPins, idempotency_key, attempt)`.

---

### 5.9 Contracts packaging (v0)

* One schema file:

  * `contracts/al_public_contracts_v0.schema.json`
* Pins: ContextPins, ActionIntent, ActionOutcome, enums, and optional ErrorResponse.

---

## 6) Modular breakdown (Level 1) and what each module must answer

> AL is an **idempotent executor + immutable outcome emitter**. The modular breakdown exists to force AL’s semantics (validation, dedupe, execution, retry, outcome immutability) to be answered *somewhere*, while leaving routing/executor tech to the implementer.

### 6.0 Module map (one screen)

AL is decomposed into 5 conceptual modules:

1. **Intent Intake & Validation**
2. **Idempotency / Dedup Guard**
3. **Action Router / Executor**
4. **Outcome Assembler**
5. **Emit & Persist**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Intent Intake & Validation

### Purpose

Validate ActionIntents are well-formed before any execution is attempted.

### What it owns

* required ActionIntent fields and type validation
* explicit reject/quarantine posture for malformed intents
* preservation of correlation keys (pins + ids)

### Questions this module must answer

* What fields are required on ActionIntent (v0 minimum)?
* What happens if required fields are missing (reject/quarantine + outcome)?
* What happens if action_type is unknown (reject/quarantine + outcome)?
* How are parameters validated (minimal v0 schema by action_type)?

### Can be left to the implementer

* how validation is implemented (schema validation library)
* how malformed intents are routed/stored

### Local vs deployed operation

* semantics identical; local may be simpler validation

---

## 6.2 Module 2 — Idempotency / Dedup Guard

### Purpose

Enforce effectively-once execution under duplicates/retries.

### What it owns

* uniqueness scope `(ContextPins, idempotency_key)`
* duplicate intent behaviour (no execute; re-emit canonical outcome)
* attempt counter semantics (increment only on real retry)

### Questions this module must answer

* How is “already executed” determined (dedupe store lookup)?
* What happens on duplicate intent (re-emit same canonical ActionOutcome)?
* How are retries represented (same idempotency_key, attempt increments)?
* What is the posture if dedupe store is unavailable (safe failure)?

### Can be left to the implementer

* dedupe store backend (KV/DB/in-memory with persistence)
* locking/concurrency strategy

### Local vs deployed operation

* local may use simple store; deployed requires durable dedupe semantics; behaviour unchanged

---

## 6.3 Module 3 — Action Router / Executor

### Purpose

Route by action_type and perform the side effect.

### What it owns

* action_type → executor mapping posture
* execution attempt boundaries (start/end timestamps)
* executor-down failure posture (FAILED + retryable)

### Questions this module must answer

* What executors exist for v0 action types?
* What does each action_type mean at a sentence level (approve/decline/step-up/case)?
* What happens when executor is down (emit FAILED + retryable=true)?

### Can be left to the implementer

* actual executor implementations (stub/simulated gateway vs real)
* concurrency and resource management

### Local vs deployed operation

* local may use simulators; deployed may call real systems; outcome semantics unchanged

---

## 6.4 Module 4 — Outcome Assembler

### Purpose

Assemble the canonical ActionOutcome payload deterministically.

### What it owns

* ActionOutcome required fields and enums
* deterministic payload normalization and timestamps
* error_category and retryable posture on failure
* external_ref posture (opaque)

### Questions this module must answer

* What fields must ActionOutcome include (v0 minimum)?
* How is attempt field set (dedupe vs retry)?
* What error categories exist (minimal stable set)?
* How are timestamps generated and normalized (UTC canonical format)?

### Can be left to the implementer

* external_ref structure
* detailed error taxonomy beyond minimal stable set

### Local vs deployed operation

* semantics identical

---

## 6.5 Module 5 — Emit & Persist

### Purpose

Emit ActionOutcome events and optionally persist them, preserving append-only history.

### What it owns

* emission to EB (v0 posture)
* append-only outcome history
* re-emit semantics for duplicates (byte-identical payload)
* persistence optionality (store is non-contract)

### Questions this module must answer

* Where are outcomes emitted (EB stream/topic) and what is the naming posture?
* How are outcomes persisted (optional), and how is append-only enforced?
* What is the behaviour on emit failure (retry emission; still no silent loss)?

### Can be left to the implementer

* transport and persistence mechanisms
* retry/backoff for emission failures

### Local vs deployed operation

* local may log/write files; deployed emits to EB; semantics unchanged

---

## 6.6 Cross-module pinned items (summary)

Across all modules, AL must ensure:

* intents validated; malformed intents handled explicitly
* idempotency enforced by (ContextPins, idempotency_key)
* duplicates never re-execute and re-emit canonical outcome payload
* retries increment attempt and emit new outcomes (append-only)
* executor down yields FAILED + retryable=true
* outcomes are joinable to DF/DLA via pins + ids + idempotency key

---

## 7) Idempotency and duplicate intent semantics (v0)

> This section pins the “effectively-once” execution semantics that make AL safe under duplicates and retries.

### 7.1 Uniqueness scope (pinned)

AL defines sameness as:

* `(ContextPins, idempotency_key)`

This is the canonical scope for dedupe and execution.

---

### 7.2 Duplicate intent rule (pinned)

If AL receives an ActionIntent whose `(ContextPins, idempotency_key)` has already been executed:

* AL MUST NOT re-execute the side effect.
* AL MUST re-emit the **same canonical ActionOutcome payload** that corresponds to the first execution.

This ensures duplicates are visible as outcomes but do not cause duplicate real-world effects.

---

### 7.3 Canonical outcome selection for duplicates

When multiple outcomes exist (attempt history), AL treats the “canonical outcome for duplicate re-emit” as:

* the latest emitted outcome by attempt number (highest attempt), within the same idempotency scope.

This rule is deterministic and ensures duplicates observe the current state of execution.

---

### 7.4 Idempotency store posture (conceptual)

AL maintains a dedupe store indexed by:

* ContextPins + idempotency_key → latest attempt outcome record (or pointer)

Backend choice is implementation freedom; the semantics are pinned.

---

### 7.5 Dedupe store unavailable posture (pinned safe stance)

If the idempotency store is unavailable:

* AL MUST NOT attempt execution “blind”.
* AL emits FAILED outcome with:

  * retryable=true
  * error_category=IDEMPOTENCY_STORE_UNAVAILABLE (stable equivalent)

This preserves safety (no double-execution risk).

---

### 7.6 Deterministic payload normalization

Duplicate re-emits must be byte-identical:

* same field ordering/serialization rules
* same timestamps as in the recorded outcome
* no “new emitted_at” drift for re-emits (v0 posture)

---

## 8) Retry semantics and attempt history (v0)

> This section pins how AL represents retries without mutating history: attempts are append-only, and retryability is explicit.

### 8.1 Attempt semantics (pinned)

* `attempt` starts at **1** for the first execution attempt.
* attempt increments only when AL performs a real retry execution for the same idempotency scope.
* duplicates do not increment attempt.

---

### 8.2 Retryable vs terminal failures (v0 posture)

AL classifies failures as:

* **retryable** (`retryable=true`) — e.g., executor unavailable, transient timeouts
* **terminal** (`retryable=false`) — e.g., invalid parameters, disallowed action, permanent rejection

Exact numeric retry budgets are config, but the retryable flag semantics are pinned.

---

### 8.3 Every attempt produces an outcome (pinned)

For every attempt AL performs, it MUST emit an ActionOutcome:

* SUCCEEDED or FAILED
* with attempt number and timestamps

No silent retries.

---

### 8.4 Append-only outcome history (pinned)

* Each retry attempt emits a new ActionOutcome with incremented attempt.
* Prior outcomes remain part of history and are not overwritten.

---

### 8.5 Retry budget posture (conceptual)

AL may enforce a retry budget:

* max attempts or max time window
* backoff strategy

These are config/implementation freedom, but outcomes must reflect when retries stop:

* terminal FAILED with retryable=false once budget exhausted.

---

### 8.6 External_ref posture under retries

If an external_ref is produced:

* it may differ per attempt
* it must be captured in the ActionOutcome for that attempt

Outcome history preserves this.

---

## 9) Execution routing and external_ref posture (v0)

> This section pins how AL routes action types to executors and how execution artifacts are referenced without bloating contracts.

### 9.1 Routing posture (v0)

* AL routes by `action_type` to a corresponding executor.
* v0 action types are fixed (APPROVE_TRANSACTION, DECLINE_TRANSACTION, STEP_UP_AUTH, QUEUE_CASE).
* Each action_type has a one-line semantic meaning:

  * APPROVE_TRANSACTION: allow the transaction
  * DECLINE_TRANSACTION: block the transaction
  * STEP_UP_AUTH: require step-up authentication (e.g., 3DS)
  * QUEUE_CASE: create/queue a case for review

---

### 9.2 Execution boundaries and timestamps

* For each attempt, AL records:

  * `started_at_utc` when execution begins
  * `ended_at_utc` when execution completes
  * `emitted_at_utc` when ActionOutcome is emitted

Timestamps are UTC and canonical format.

---

### 9.3 external_ref posture (v0)

* external_ref is **opaque** in v0.
* external_ref may point to:

  * simulated gateway response
  * external system receipt id
  * internal execution receipt

Pinned rule:

* external_ref is never required for joinability; it is optional evidence only.

---

### 9.4 Failure categories (v0 minimal stable set)

AL uses a small stable `error_category` set (conceptual):

* `EXECUTOR_UNAVAILABLE`
* `TIMEOUT`
* `INVALID_INTENT`
* `IDEMPOTENCY_STORE_UNAVAILABLE`
* `EXECUTION_ERROR`

Final enum vs string posture is a v0 residual decision; stability is required.

---

### 9.5 Determinism posture for routing

Routing is deterministic:

* same action_type and same parameters lead to the same executor selection posture
* any routing changes require versioning (not introduced silently in v0)

---

## 10) Output contract: ActionOutcome and downstream obligations

> This section pins the ActionOutcome output contract and what downstream components (DLA, labels) rely on.

### 10.1 ActionOutcome required fields (v0)

Every ActionOutcome MUST include:

* `context_pins`
* `decision_id` / `request_id` / `event_id`
* `action_type`
* `idempotency_key`
* `attempt`
* `outcome_status` ∈ {SUCCEEDED, FAILED}
* timestamps:

  * `started_at_utc`
  * `ended_at_utc`
  * `emitted_at_utc`

If FAILED:

* `error_category`
* `retryable` boolean

Optional:

* `external_ref` (opaque)

---

### 10.2 Joinability requirements (pinned)

ActionOutcomes must be joinable to:

* DF DecisionResponse via decision_id/request_id/event_id
* DF ActionIntent via (ContextPins, idempotency_key)
* DLA audit records via the same ids and pins

This is why pins and ids are mandatory.

---

### 10.3 DLA obligations (consumer expectations)

DLA will record ActionOutcome history and link it to the canonical AuditDecisionRecord:

* for each decision_id, DLA can store:

  * the latest outcome per action_type/idempotency_key
  * and/or the full attempt history

Exact storage strategy is DLA’s choice; ActionOutcome must provide the join keys.

---

### 10.4 Label/Case timeline posture (future consumer)

Label/Case plane can use ActionOutcomes to build:

* action timelines (intent → outcome)
* eventual ground truth about what action happened

No extra fields are required beyond join keys and status in v0.

---

### 10.5 Emission posture (pinned)

* ActionOutcomes are emitted to EB (and may also be stored internally).
* Outcomes are append-only; consumers treat them as immutable events.

---

## 11) Determinism rules (stable shapes)

> This section pins the normalization rules that prevent drift across implementations and make duplicate re-emits byte-identical.

### 11.1 Canonical field normalization

* Timestamps are UTC and canonical string format.
* Enums use stable string values (ActionType, OutcomeStatus).
* Optional fields (external_ref) are either present or absent deterministically (no random inclusion).

### 11.2 Deterministic ordering

* If any lists appear in ActionOutcome (v0 keeps it minimal), they must be deterministically ordered.
* If ActionOutcome is embedded inside a wrapper that contains multiple outcomes, that wrapper must sort outcomes deterministically by:

  * (action_type, idempotency_key, attempt).

### 11.3 Byte-identical duplicate re-emits (pinned)

On duplicate ActionIntents, AL must re-emit the same canonical ActionOutcome payload:

* identical field values
* identical timestamps
* identical emitted_at_utc (no “new emit time” drift)
* identical serialization ordering rules

### 11.4 Deterministic attempt assignment

* attempt increments only on real retry execution
* duplicates do not affect attempt

### 11.5 Stable error_category vocabulary

* error_category values must be drawn from a stable set (even if represented as strings in v0).
* do not introduce new categories silently; version them.

---

## 12) Contracts philosophy and contract pack overview (v0)

> AL contracts exist to pin the **ActionIntent input** and **ActionOutcome output** shapes in a machine-checkable way. Contracts define shape; AL specs define behavior (idempotency, duplicate handling, retries).

### 12.1 v0 contract strategy (one schema file)

AL v0 ships **one** schema file:

* `contracts/al_public_contracts_v0.schema.json`

This keeps the surface small but enforceable for:

* DF producers of ActionIntents
* DLA/labels consumers of ActionOutcomes
* Canonical Event Contract Pack integration later

---

### 12.2 Validation targeting rule (self-describing)

All AL contract objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

### 12.3 `$defs` inventory (v0)

`al_public_contracts_v0.schema.json` contains `$defs` for:

* `ContextPins`
* `ActionType` (enum)
* `OutcomeStatus` (enum)
* `ActionIntent`
* `ActionOutcome`
* optional `ErrorResponse` (thin)

external_ref remains opaque in v0.

---

### 12.4 What contracts cover vs what specs cover

#### Contracts cover (shape/structure)

* required fields and types for ActionIntent and ActionOutcome
* enums for ActionType and OutcomeStatus
* required idempotency_key and attempt fields
* required timestamps fields
* retryable and error_category presence on FAILED

#### Specs cover (behavior/invariants)

* idempotency scope and duplicate handling rule (no re-execute; re-emit outcome)
* retry semantics and attempt history rules
* executor unavailable posture and failure categories meaning
* determinism/byte-identical re-emits requirements

---

### 12.5 Relationship to Canonical Event Contract Pack

AL payloads will later become canonical event types:

* `action_intent`
* `action_outcome`

In v0, AL keeps schemas self-contained; the Canonical Event Contract Pack can reference AL `$defs` for payload shapes to avoid drift.

---

## 13) Addressing, naming, and discoverability (conceptual)

> This section defines how ActionIntents and ActionOutcomes are referenced and reconciled **without guessing**, across local and deployed environments.

### 13.1 Design goals

AL discoverability must support:

* **idempotent execution:** duplicates map to the same idempotency scope
* **audit linkage:** DLA can join outcomes back to decisions deterministically
* **operational triage:** operators can answer “did this action happen, and what was the outcome?”

---

### 13.2 Primary identifiers (pinned discovery keys)

In v0, the primary identifiers are:

* `decision_id` / `request_id` / `event_id` *(same value in v0)*
* `idempotency_key` *(defines the execution scope)*
* `attempt` *(attempt history within that scope)*

Canonical identity for an outcome attempt:

* `(ContextPins, idempotency_key, attempt)`

---

### 13.3 ActionOutcome discovery

ActionOutcomes must be discoverable by:

* decision_id (list all outcomes for a decision)
* (ContextPins, idempotency_key) (find the execution history for one intent)
* (ContextPins, idempotency_key, attempt) (find a specific attempt outcome)

Pinned v0 behavior:

* duplicates re-emit the same canonical outcome payload, so discovery remains stable.

---

### 13.4 Duplicate recognition and reconciliation

* A duplicate ActionIntent is recognized by:

  * same ContextPins + same idempotency_key
* On duplicate:

  * AL re-emits the canonical ActionOutcome (no re-execution)
* Consumers (DLA, labels) dedupe by:

  * (ContextPins, idempotency_key, attempt)

---

### 13.5 Naming stability

* `action_type` values are stable enums (v0 fixed set).
* `outcome_status` values are stable enums (SUCCEEDED/FAILED).
* `error_category` comes from a stable vocabulary (even if represented as strings).

No silent changes to these names in v0.

---

### 13.6 Local vs deployed discoverability

* **Local:** outcomes may be written to files/logs; references may be filesystem-like.
* **Deployed:** outcomes are emitted to EB; references may be EB offsets or object-store keys.

Pinned rule:

* regardless of transport/storage, the semantic identifiers remain:

  * ContextPins + decision_id/event_id + idempotency_key + attempt.

---

### 13.7 Optional persistence (implementation freedom)

AL may optionally persist:

* the latest outcome per idempotency scope, and/or
* the full attempt history

But the public contract remains the emitted ActionOutcome events.

---

## 14) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Actions Layer docs and contracts. The goal is a **single, deep reading surface** for AL design, plus a **minimal v0 contract**.

### 14.1 Target location in repo

Conceptually, AL lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/actions_layer/`

This folder should be self-contained: a new contributor should understand AL by starting here.

---

### 14.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ actions_layer/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ AL1_charter_and_boundaries.md
         │  ├─ AL2_action_intents_input_contract.md
         │  ├─ AL3_idempotency_and_retry_semantics.md
         │  ├─ AL4_execution_routing_and_outcome_assembly.md
         │  └─ AL5_emit_persistence_ops_acceptance.md
         │
         └─ contracts/
            └─ al_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; AL v0 needs only **one** schema file.

---

### 14.3 What each file is for (intent)

#### `README.md`

* Entry point: what AL is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (designer-locked v0 intent)
  * `specs/` reading order (AL1–AL5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This stitched conceptual design document:

  * AL purpose in platform
  * AL laws (idempotency, immutable outcomes, no silent attempts)
  * designer-locked v0 decisions (action types, duplicate handling, retries)
  * modular breakdown + questions per module
  * contract pack overview (v0)
  * discoverability concepts (idempotency_key, attempt)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behavior/invariants
  * contract schema defines boundary shapes
* Non-negotiables:

  * idempotency scope (ContextPins, idempotency_key)
  * duplicates never re-execute; canonical outcome re-emit
  * attempt semantics and append-only history
  * executor-down failure posture (FAILED + retryable=true)
  * joinability fields always present

#### `specs/`

* AL1–AL5 are the eventual binding-ish AL design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `al_public_contracts_v0.schema.json` pins ActionIntent/ActionOutcome boundary objects.

---

### 14.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (designer-locked intent)
3. `specs/AL1_...` → `specs/AL5_...` (behavior/invariants)
4. `contracts/al_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

## 15) What the eventual spec docs must capture (mapping)

> This section bridges the AL conceptual design into the **actual AL spec docs** (AL1–AL5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 15.0 Mapping rule (how to use this section)

For every AL “law” and designer-locked decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in AL1–AL5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 15.1 AL1 — Charter & boundaries

### AL1 must capture

* AL purpose as side-effect executor + outcome reporter
* authority boundaries:

  * authoritative for ActionOutcome truth + idempotent execution posture
  * not decisioning, not features/identity, not stream semantics
* AL laws:

  * idempotency scope and duplicate handling rule
  * outcome immutability and append-only attempts history
  * every attempt emits an outcome
  * executor-down failure posture
  * joinability requirements

### AL1 may leave to the implementer

* deployment model (service/worker/library)

---

## 15.2 AL2 — Action intents (input contract)

### AL2 must capture

* ActionIntent required fields
* ActionType enum list and one-line semantics per type
* validation rules for malformed intents
* reject/quarantine posture for invalid intents (and whether outcomes are emitted for invalid intents)

### AL2 may leave to the implementer

* validation tooling and parameter schema details

---

## 15.3 AL3 — Idempotency & retry semantics

### AL3 must capture

* idempotency scope: (ContextPins, idempotency_key)
* duplicate intent behavior:

  * no re-execute
  * re-emit canonical ActionOutcome payload
* attempt semantics (start at 1; increment on real retries)
* retryable vs terminal failure posture (minimal taxonomy)
* dedupe store unavailable safe stance (FAILED + retryable)

### AL3 may leave to the implementer

* dedupe store backend and locking strategy
* retry budgets and backoff mechanics (config)

---

## 15.4 AL4 — Execution routing & outcome assembly

### AL4 must capture

* routing posture: action_type → executor
* ActionOutcome required fields and enums
* external_ref posture (opaque)
* error_category minimal stable set and meaning
* timestamp semantics (start/end/emitted)

### AL4 may leave to the implementer

* executor implementations and external system interaction details

---

## 15.5 AL5 — Emit, persistence, ops & acceptance

### AL5 must capture

* emission posture (to EB) and append-only outcome history rules
* deterministic re-emit behavior for duplicates (byte-identical)
* observability minimums (success rate, retry counts, dedupe hits, lag)
* acceptance scenarios (duplicates safe, retries produce outcomes, joinability)

### AL5 may leave to the implementer

* observability stack, persistence backend if any

---

## 15.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* ContextPins
* ActionType enum
* OutcomeStatus enum
* ActionIntent shape (idempotency_key required)
* ActionOutcome shape (attempt + timestamps; retryable+error_category on FAILED)
* validation targeting via kind + contract_version

### Specs must include

* duplicate handling rule (no re-execute; canonical re-emit)
* retry and attempt history semantics
* executor-down failure posture
* determinism/byte-identical re-emits requirement
* safe stance when dedupe store unavailable

---

## 15.7 Minimal completeness standard (so AL is implementable)

AL is “spec-ready” when AL1–AL5 collectively pin:

* action types and intent/outcome contracts
* idempotency scope + duplicate semantics
* retry attempt history semantics (append-only)
* failure posture for executor/dedupe store unavailability
* emission and joinability requirements
* acceptance scenarios covering duplicates, retries, and failure cases

Everything else can remain implementer freedom.

---

## 16) Acceptance questions and Definition of Done

> This section is the conceptual **ship checklist** for AL v0: the questions AL must answer and the minimal behavioural scenarios that indicate AL is correct enough to implement and integrate.

### 16.1 Acceptance questions (AL must answer these unambiguously)

1. **Did we avoid double side effects?**

* Under duplicates/retries, does AL execute effectively-once for the same idempotency scope?

2. **How are duplicates handled?**

* Do duplicates re-emit the canonical ActionOutcome without re-execution?

3. **How are retries represented?**

* Do retries increment attempt and emit new outcomes append-only?

4. **Are outcomes immutable and joinable?**

* Do all outcomes carry ContextPins + ids + idempotency_key + attempt?

5. **What happens when executors are down?**

* Do we emit FAILED with retryable=true and a stable error_category?

6. **What happens when the idempotency store is down?**

* Do we fail safely (FAILED + retryable=true) without blind execution?

7. **Are outputs deterministic?**

* Are duplicate re-emits byte-identical and stable in shape?

---

### 16.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Happy path success

**Given**

* a valid ActionIntent for APPROVE_TRANSACTION with new idempotency_key

**Expect**

* AL executes side effect once
* emits ActionOutcome SUCCEEDED attempt=1 with timestamps
* outcome is emitted/persisted append-only

---

#### DoD-2: Duplicate intent does not re-execute

**Given**

* the same ActionIntent delivered twice (same ContextPins + idempotency_key)

**Expect**

* second delivery causes no execution
* AL re-emits the same ActionOutcome payload (byte-identical)
* no double side effect occurs

---

#### DoD-3: Retryable failure produces FAILED + retryable=true

**Given**

* executor unavailable on first attempt

**Expect**

* ActionOutcome FAILED attempt=1, retryable=true, error_category=EXECUTOR_UNAVAILABLE
* later retry attempt (if performed) emits ActionOutcome attempt=2

---

#### DoD-4: Retry success produces new attempt outcome

**Given**

* attempt=1 FAILED retryable=true
* attempt=2 execution succeeds

**Expect**

* ActionOutcome SUCCEEDED attempt=2 is emitted
* attempt=1 outcome remains in history (append-only)

---

#### DoD-5: Idempotency store unavailable fails safe

**Given**

* dedupe store is unavailable

**Expect**

* AL does not execute blindly
* emits ActionOutcome FAILED retryable=true error_category=IDEMPOTENCY_STORE_UNAVAILABLE

---

#### DoD-6: Joinability to DLA/DF guaranteed

**Given**

* any emitted ActionOutcome

**Expect**

* contains ContextPins + decision/request/event id + action_type + idempotency_key + attempt
* DLA can join the outcome back to DF decision record deterministically

---

### 16.3 Minimal deliverables required to claim “DoD satisfied”

To claim AL meets DoD at v0 conceptual level, you should be able to show:

* one SUCCEEDED outcome example per action_type
* duplicate intent test showing no re-execution and byte-identical re-emit
* retry failure then success attempt history (attempt=1 failed, attempt=2 success)
* executor-down failure example (FAILED + retryable=true)
* idempotency-store-down safe failure example
* evidence DLA can join outcomes by ids and idempotency_key/attempt

---

## 17) Open decisions log (v0 residuals only)

> These are the only remaining decisions for AL v0 that are not already designer-locked. Everything else is pinned above or is implementation freedom.

### DEC-AL-001 — error_category vocabulary finalization

* **Question:** finalize the minimal stable error_category set (enum vs string).
* **Status:** OPEN (v0 residual)
* **Close in:** AL4 + contracts
* **Constraint:** stable set; no silent additions.

### DEC-AL-002 — Hash/ID for an optional outcome_id

* **Question:** do we include an optional deterministic `outcome_id` (hash of outcome payload)?
* **Status:** OPEN (v0 residual)
* **Close in:** AL4/AL5
* **Constraint:** if included, must be deterministic and stable.

### DEC-AL-003 — Retry budget defaults

* **Question:** default max attempts / max time window before retryable becomes terminal?
* **Status:** OPEN (v0 residual)
* **Close in:** AL3/AL5 (config posture)
* **Constraint:** must be explicit; outcomes reflect when retries stop.

### DEC-AL-004 — Backoff posture details

* **Question:** backoff schedule for retries (constant/exponential/jitter)?
* **Status:** OPEN (v0 residual)
* **Close in:** AL3 (config posture)
* **Constraint:** retries must always emit outcomes.

### DEC-AL-005 — Persistence beyond EB emission

* **Question:** does AL persist outcomes in addition to emitting to EB (for retrieval/re-emit), or can it rely on EB replay?
* **Status:** OPEN (v0 residual)
* **Close in:** AL5
* **Constraint:** duplicate re-emit must be possible without re-execution (either via internal persistence or EB fetch).

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate v0 ActionIntent and ActionOutcome payloads.
> Idempotency keys are shown as placeholders; DF v0 defines them deterministically.

---

### A.1 Example — ActionIntent (APPROVE_TRANSACTION)

```json
{
  "kind": "action_intent",
  "contract_version": "al_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000123",
  "request_id": "evt_txn_000000123",
  "event_id": "evt_txn_000000123",

  "action_type": "APPROVE_TRANSACTION",
  "idempotency_key": "H(pins,evt_txn_000000123,APPROVE_TRANSACTION)",

  "parameters": {
    "reason": "risk_below_threshold"
  }
}
```

---

### A.2 Example — ActionOutcome (SUCCEEDED, attempt=1)

```json
{
  "kind": "action_outcome",
  "contract_version": "al_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000123",
  "request_id": "evt_txn_000000123",
  "event_id": "evt_txn_000000123",

  "action_type": "APPROVE_TRANSACTION",
  "idempotency_key": "H(pins,evt_txn_000000123,APPROVE_TRANSACTION)",
  "attempt": 1,

  "outcome_status": "SUCCEEDED",

  "started_at_utc": "2026-01-03T12:34:57Z",
  "ended_at_utc": "2026-01-03T12:34:57Z",
  "emitted_at_utc": "2026-01-03T12:34:57Z",

  "external_ref": "sim_gateway://resp/ok/txn_000000123"
}
```

---

### A.3 Example — ActionOutcome (FAILED, retryable=true, executor unavailable)

```json
{
  "kind": "action_outcome",
  "contract_version": "al_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000124",
  "request_id": "evt_txn_000000124",
  "event_id": "evt_txn_000000124",

  "action_type": "STEP_UP_AUTH",
  "idempotency_key": "H(pins,evt_txn_000000124,STEP_UP_AUTH)",
  "attempt": 1,

  "outcome_status": "FAILED",

  "started_at_utc": "2026-01-03T12:35:11Z",
  "ended_at_utc": "2026-01-03T12:35:16Z",
  "emitted_at_utc": "2026-01-03T12:35:16Z",

  "error_category": "EXECUTOR_UNAVAILABLE",
  "retryable": true
}
```

---

### A.4 Example — Retry success (attempt=2)

```json
{
  "kind": "action_outcome",
  "contract_version": "al_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000124",
  "request_id": "evt_txn_000000124",
  "event_id": "evt_txn_000000124",

  "action_type": "STEP_UP_AUTH",
  "idempotency_key": "H(pins,evt_txn_000000124,STEP_UP_AUTH)",
  "attempt": 2,

  "outcome_status": "SUCCEEDED",

  "started_at_utc": "2026-01-03T12:35:30Z",
  "ended_at_utc": "2026-01-03T12:35:30Z",
  "emitted_at_utc": "2026-01-03T12:35:30Z",

  "external_ref": "sim_gateway://resp/challenge/evt_txn_000000124"
}
```

---

### A.5 Example — Duplicate intent re-emit (byte-identical outcome)

Same as A.2 (or whichever is the latest attempt outcome for that idempotency scope).

---

## Appendix B — ASCII sequences (execute, duplicate no-op, retry attempts, audit linkage)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/emit

---

### B.1 End-to-end (DF intent → AL dedupe → execute → outcome → DLA records)

```
Participants:
  Decision Fabric | EB | Actions Layer | Executor | Decision Log & Audit

Decision Fabric => EB: emit ActionIntent (idempotency_key)
EB --> Actions Layer: deliver ActionIntent (duplicates possible)

Actions Layer: validate intent fields
Actions Layer: check dedupe store (ContextPins, idempotency_key)

(if new)
  Actions Layer -> Executor: execute action_type(parameters)
  Executor -> Actions Layer: result (success/failure) + optional external_ref
  Actions Layer => EB: emit ActionOutcome(attempt=1, status, timestamps, retryable)
  Decision Log & Audit --> EB: consume ActionOutcome and store/attach to decision_id
(if duplicate)
  Actions Layer: no execute
  Actions Layer => EB: re-emit canonical ActionOutcome (byte-identical)
```

---

### B.2 Duplicate intent (no re-execute; canonical outcome re-emit)

```
EB --> Actions Layer: duplicate ActionIntent (same ContextPins + idempotency_key)

Actions Layer: dedupe store indicates already executed
Actions Layer: NO-OP execution
Actions Layer => EB: re-emit same ActionOutcome payload (byte-identical)
```

---

### B.3 Retry attempt history (append-only outcomes)

```
Attempt 1:
  Executor unavailable -> FAILED retryable=true
  Actions Layer => EB: emit ActionOutcome(attempt=1, FAILED, retryable=true)

Later retry:
  Actions Layer decides to retry (budget allows)
  Actions Layer -> Executor: execute again
  Executor -> Actions Layer: success
  Actions Layer => EB: emit ActionOutcome(attempt=2, SUCCEEDED)

History is preserved: both attempt=1 and attempt=2 outcomes exist.
```

---

### B.4 Executor down safe stance (no silent queue)

```
Actions Layer -> Executor: call fails (unavailable)

Actions Layer => EB: emit ActionOutcome(FAILED, retryable=true, error_category=EXECUTOR_UNAVAILABLE)
No silent waiting without an outcome event.
```

---

### B.5 DLA joinability (intent/outcome to decision record)

```
Decision Log & Audit stores:
  - DF DecisionResponse keyed by decision_id/event_id
  - AL ActionOutcome keyed by (ContextPins, idempotency_key, attempt)

Join is possible via:
  decision_id/event_id and idempotency_key.
```

---

