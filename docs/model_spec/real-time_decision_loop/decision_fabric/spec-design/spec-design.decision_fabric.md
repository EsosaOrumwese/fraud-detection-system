# Decision Fabric (DF) — Conceptual Spec Design Doc (non-spec) — Section Header Plan

## 0) Document metadata

### 0.1 Document header

* **Title:** *Decision Fabric (DF) — Conceptual Spec Design (v0)*
* **Plane:** Real-Time Decision Loop / Decision Fabric
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final
* **Version:** v0.x
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Capture the **designer-locked v0 intent** for Decision Fabric in one place (no drift).
* Provide the roadmap for writing:

  * DF1–DF5 specs (behaviour/invariants)
  * `contracts/df_public_contracts_v0.schema.json` (machine-checkable boundary shapes)
* Ensure DF’s relationships to DL/OFP/IEG are unambiguous:

  * degrade obedience is hard
  * provenance is complete
  * action intents are idempotent

### 0.3 Audience and prerequisites

* **Primary:** you (designer), Codex (implementer)
* **Secondary:** DL, OFP, IEG, Actions Layer, Decision Log owners
* **Prerequisites:**

  * IG admits canonical events
  * EB delivers admitted events at-least-once (duplicates/out-of-order possible)
  * DL outputs DegradeDecision (mode + capability mask)
  * OFP serves feature snapshots with deterministic hash + provenance
  * IEG serves identity context and graph_version (when allowed)

### 0.4 How to use this document

* This doc is **directional alignment** and a **question map**, not binding spec text.
* Normative truth lives in:

  * DF specs (DF1–DF5), and
  * DF contract schema file
* Every pinned decision here must appear later as a closed decision in specs/contracts.

### 0.5 Scope and non-scope

* **In scope:** request framing, degrade enforcement, feature/context acquisition semantics, staged pipeline posture, decision outcomes, action intents + idempotency, provenance + determinism rules.
* **Out of scope:** exact ML model internals, training/rollout, infra/deployment topology, telemetry plumbing specifics (beyond required provenance fields).

### 0.6 Proposed repo placement (conceptual)

* `docs/model_spec/real-time_decision_loop/decision_fabric/CONCEPTUAL.md`
* Related:

  * `specs/DF1_...` → `specs/DF5_...`
  * `contracts/df_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Decision Fabric exists

Decision Fabric (DF) is the Real-Time Decision Loop’s **decisioning core**. Its job is to take an admitted event and produce:

* a **decision outcome** (what we decided),
* **action intent(s)** (what we plan to do),
* and a **complete provenance bundle** (what we knew and why we acted),

all **under an explicit degrade posture**.

One sentence: **“Turn an admitted event into an auditable decision under a known degrade mode, emitting idempotent action intents and complete provenance.”**

---

### 1.2 Where DF sits relative to IG, EB, DL, OFP, IEG, Actions, and Decision Log

* **Ingestion Gate (IG)** admits canonical events.
* **Event Bus (EB)** delivers admitted events (at-least-once).
* **Degrade Ladder (DL)** provides the current safe-posture decision:

  * `degrade_mode` + `capabilities_mask` + provenance.
* **Online Feature Plane (OFP)** provides feature snapshots + provenance (freshness, group versions, snapshot hash).
* **Identity & Entity Graph (IEG)** provides identity context + `graph_version` when permitted.
* **Decision Fabric (DF)** consumes these inputs (subject to DL constraints), runs a staged decision pipeline, and produces DecisionResponse + ActionIntents.
* **Actions Layer** consumes ActionIntents and performs side effects (idempotently).
* **Decision Log** records DF outputs and the provenance for audit/replay.

---

### 1.3 What DF is system-of-record for (and what it is not)

DF is authoritative for:

* **DecisionResponse** (outcome + actions + provenance)
* **ActionIntent** generation rules (including idempotency keys)
* **Decision provenance** (which mode, which features, which versions, which graph_version, which policy/model refs)

DF is not authoritative for:

* event validity (IG)
* stream semantics (EB)
* identity truth (IEG)
* feature computation (OFP)
* action execution (Actions Layer)

---

### 1.4 Why degrade obedience is central

DF must not silently change behavior under pressure. Instead:

* DL explicitly declares constraints (mask),
* DF obeys them,
* and records them in provenance.

This prevents “silent coupling” and makes audits and incident reconstruction possible.

---

### 1.5 What DF must enable for downstream components

Downstream components must be able to rely on DF for:

* **deterministic, replay-safe outputs** under duplicate deliveries
* **idempotent action intents** (so side effects aren’t double-triggered)
* **complete provenance** (mode, features, versions, freshness, graph_version, policy refs, timings)
* **fail-safe posture** when dependencies are unavailable (safe default action)

---

## 2) Core invariants (DF “laws”)

> These are **non-negotiable behaviours** for DF v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Run/world scoped via ContextPins

* DF processing and outputs are scoped by **ContextPins**:

  * `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`
* DF must not mix context across different ContextPins.

### 2.2 Hard obedience to DegradeDecision (no bypass)

* DF MUST consume a `DegradeDecision` and MUST obey its `capabilities_mask`.
* DF MUST NOT call disallowed dependencies (IEG/OFP groups/stage2) or use disallowed heuristics/models.
* DF MUST record the degrade decision used in provenance.

### 2.3 No hidden “now”: DF uses explicit event_time

* DF MUST treat event_time as the canonical time boundary.
* DF MUST call OFP using `as_of_time_utc = event_time_utc` (v0 posture).
* DF must not silently substitute wall-clock “now”.

### 2.4 Deterministic staged pipeline gating

* DF has a fixed stage order (Stage 0/1/2).
* Stage execution is gated deterministically by:

  * degrade capabilities, and
  * availability of required inputs.
* Skipped stages MUST be recorded with a reason in provenance.

### 2.5 Idempotent action intents

* DF MUST emit action intents with deterministic idempotency keys.
* Duplicates/replays must not result in duplicate side effects.

### 2.6 Provenance completeness

Every DecisionResponse MUST include provenance sufficient to reconstruct:

* degrade mode + mask used
* features used (snapshot hash, group versions, freshness, input basis)
* graph_version used (if any)
* policy/model refs
* stage execution summary
* timing fields

### 2.7 Fail-safe posture (safe default)

* If DF cannot decide safely, it must fail-safe:

  * conservative outcome (v0: STEP_UP)
  * conservative action intent (STEP_UP_AUTH)
  * explicit error details recorded in provenance.

### 2.8 Deterministic output shape and ordering

* DF outputs must have stable ordering for lists/maps:

  * actions list ordering is deterministic
  * provenance lists/maps are deterministically ordered
* DF must not rely on DB iteration order or nondeterministic map ordering.

### 2.9 Explicit error posture (no invented context)

* DF must not invent missing features, identities, or modes.
* If required inputs are unavailable, DF records unavailability and uses the pinned fail-safe posture.

---

## 3) Terminology and key objects

> These are the nouns used throughout the DF conceptual design. Exact field shapes live in the DF v0 contract schema; behavioural meaning is pinned in DF specs.

### 3.1 ContextPins

Run/world scoping identifiers carried through DF:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

---

### 3.2 Admitted event

A post-IG event delivered by EB (at-least-once; duplicates possible). DF consumes an admitted event as the primary stimulus for decisioning.

---

### 3.3 event_ref, event_id, event_time_utc, event_type

* `event_ref`: opaque by-ref pointer to the canonical event (v0)
* `event_id`: stable logical identity of the event
* `event_time_utc`: event-time boundary for OFP calls and ordering semantics
* `event_type`: type/schema target of the event (e.g., `transaction_event` in v0)

---

### 3.4 DecisionRequest

The canonical request DF processes, containing:

* ContextPins
* event_ref
* event_id, event_time_utc, event_type
* request_id (v0: request_id = event_id)
* optional latency_class (if provided)

---

### 3.5 DegradeDecision

The DL output describing:

* `degrade_mode`
* `capabilities_mask` (hard constraints)
* provenance triggers and decided_at

DF must obey and record this.

---

### 3.6 CapabilityMask fields (v0)

* `allow_ieg`
* `allowed_feature_groups[]`
* `allow_model_primary`
* `allow_model_stage2`
* `allow_fallback_heuristics`
* `action_posture` (`NORMAL` | `STEP_UP_ONLY`)

---

### 3.7 Feature snapshot and provenance (OFP outputs)

* `feature_snapshot_hash` (deterministic)
* group versions used
* freshness blocks (per group, stale flags)
* input_basis watermark vector (OFP applied offsets)

DF records these in decision provenance.

---

### 3.8 graph_version (IEG)

The version marker for identity/graph context used:

* recorded in provenance if IEG was consulted.

---

### 3.9 Staged pipeline (v0)

Pinned stage structure:

* Stage 0: Guardrails (always)
* Stage 1: Primary (gated by allow_model_primary)
* Stage 2: Secondary (gated by allow_model_stage2)

---

### 3.10 DecisionOutcome (v0 enum)

Pinned decision outcomes:

* `APPROVE`
* `DECLINE`
* `STEP_UP`
* `REVIEW`

---

### 3.11 ActionIntent

An idempotent intent describing a downstream side effect.

Pinned v0 action types:

* `APPROVE_TRANSACTION`
* `DECLINE_TRANSACTION`
* `STEP_UP_AUTH`
* `QUEUE_CASE`

Each ActionIntent carries:

* `idempotency_key` (deterministic)
* `parameters` (object)

---

### 3.12 DecisionProvenance

The audit bundle capturing:

* degrade decision used
* OFP snapshot hash + group versions + freshness + input_basis
* graph_version if used
* df_policy_ref and stage execution summary
* timings

---

### 3.13 Fail-safe posture

If DF cannot decide safely:

* outcome defaults to `STEP_UP`
* action defaults to `STEP_UP_AUTH`
* error reason recorded (and retryable flag if applicable)

---

## 4) DF as a black box (inputs → outputs)

> This section treats Decision Fabric as a black box: what it consumes, what it produces, and who relies on it.

### 4.1 Inputs (what DF consumes)

#### 4.1.1 Primary input: admitted event

DF consumes an admitted event from EB, represented as:

* `event_ref` (opaque by-ref)
* plus required envelope fields carried into DecisionRequest:

  * event_id, event_time_utc, event_type
  * ContextPins

#### 4.1.2 DegradeDecision (required)

DF consumes the current DegradeDecision:

* mode + capabilities mask + provenance
  This is mandatory and always recorded.

#### 4.1.3 OFP feature snapshots (conditional)

DF requests OFP feature snapshots as allowed by the capabilities mask:

* within allowed_feature_groups
* using as_of_time_utc = event_time_utc
  DF records snapshot hash, versions, freshness, and input_basis.

#### 4.1.4 IEG identity/graph context (conditional)

DF may call IEG only when allow_ieg=true:

* resolve identity / neighbors as needed
* record graph_version used

If allow_ieg=false, DF does not call IEG and proceeds without that context.

---

### 4.2 Outputs (what DF produces)

#### 4.2.1 DecisionResponse (authoritative output)

DF outputs a DecisionResponse containing:

* DecisionOutcome (v0 enum)
* ActionIntents (idempotent)
* DecisionProvenance (complete audit bundle)
* request_id/event_id linkage

#### 4.2.2 ActionIntents (for Actions Layer)

DF emits ActionIntents to the Actions Layer:

* deterministic idempotency keys ensure no double side effects under duplicates/replay.

#### 4.2.3 Optional decision events (conceptual)

DF may optionally emit a “decision made” event to EB for logging/audit, but in v0 the authoritative output is the DecisionResponse that Decision Log persists.

---

### 4.3 Boundary map (who consumes DF outputs)

#### 4.3.1 Actions Layer

Consumes ActionIntents and executes side effects idempotently.

#### 4.3.2 Decision Log & Audit Store

Records DecisionResponses and provenance for explainability and replay.

#### 4.3.3 Observability

Consumes DF operational metrics and mode distributions (conceptual).

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for DF v0. These decisions are treated as fixed direction for DF specs and the v0 contract schema.

### 5.1 Authority + scope (v0)

* DF is system-of-record for:

  * DecisionResponse
  * ActionIntents
  * DecisionProvenance
* DF is run/world scoped by ContextPins.

---

### 5.2 DecisionRequest minimum fields (v0)

DecisionRequest MUST include:

* `context_pins`
* `event_ref` (opaque)
* `event_id`
* `event_time_utc`
* `event_type`
* `request_id`

Pinned v0 rule:

* `request_id = event_id` (idempotent retries).

---

### 5.3 DegradeDecision obedience (v0 hard constraints)

* DF MUST consume DegradeDecision and MUST obey CapabilityMask.
* DF MUST record the degrade decision used in provenance:

  * at minimum: degrade_mode + full capabilities_mask + triggers (or deterministic degrade_decision_id if enabled).
* No bypass is permitted.

---

### 5.4 Staged pipeline posture (v0)

Pinned stages and gating:

* **Stage 0: Guardrails**

  * always executed
* **Stage 1: Primary**

  * executed only if `allow_model_primary=true`
* **Stage 2: Secondary**

  * executed only if `allow_model_stage2=true`

Stage skips:

* if a stage is disallowed or missing required inputs, it is skipped and recorded with a reason.

---

### 5.5 IEG usage posture (v0)

* If `allow_ieg=false`: DF MUST NOT call IEG.
* If `allow_ieg=true`: DF may call IEG and MUST record graph_version used.
* If IEG is unavailable:

  * DF proceeds without IEG context
  * records unavailability in provenance
  * does not invent identity context.

---

### 5.6 OFP usage posture (v0)

* DF requests OFP feature groups only if permitted:

  * groups must be within `allowed_feature_groups` (or all if `["*"]`).
* DF calls OFP with:

  * `as_of_time_utc = event_time_utc`
* If OFP returns stale or missing data for groups DF requested:

  * DF treats it as degraded inputs
  * DF skips Stage 2
  * DF records staleness/missing in provenance.

---

### 5.7 DecisionOutcome vocabulary (v0 enum)

Pinned DecisionOutcome values:

* `APPROVE`
* `DECLINE`
* `STEP_UP`
* `REVIEW`

---

### 5.8 ActionIntent vocabulary + idempotency (v0)

Pinned action types:

* `APPROVE_TRANSACTION`
* `DECLINE_TRANSACTION`
* `STEP_UP_AUTH`
* `QUEUE_CASE`

Pinned idempotency key rule:

* `idempotency_key = H(ContextPins, event_id, action_type)` (deterministic)

Pinned posture constraint:

* if `action_posture=STEP_UP_ONLY`, DF MUST NOT emit `APPROVE_TRANSACTION`.

---

### 5.9 Fail-safe posture (v0)

If DF cannot decide safely:

* DecisionOutcome = `STEP_UP`
* emits ActionIntent = `STEP_UP_AUTH`
* records error details in provenance (and retryable flag if relevant)

---

### 5.10 Provenance minimum (v0)

Every DecisionResponse includes provenance containing:

* ContextPins
* DegradeDecision used (mode + mask + trigger linkage)
* OFP: feature_snapshot_hash + group versions + freshness + input_basis
* IEG: graph_version when consulted
* df_policy_ref (string; v0 may use placeholder)
* stage execution summary (stages run/skipped + reasons)
* timings: started_at_utc, ended_at_utc (optional per-stage timings)

---

### 5.11 Deterministic output shape (v0)

* actions list sorted deterministically by action_type
* lists/maps in provenance are deterministically ordered
* no reliance on nondeterministic iteration order

---

### 5.12 Contracts packaging (v0)

* DF v0 ships one schema file:

  * `contracts/df_public_contracts_v0.schema.json`
* v0 keeps refs opaque:

  * `event_ref` and any feature refs remain by-ref/opaque until Canonical Event Contract Pack v1
* contract includes DecisionRequest/Response, enums, ActionIntent, DecisionProvenance, ErrorResponse.

---

## 6) Modular breakdown (Level 1) and what each module must answer

> DF is a **staged decisioning pipeline** constrained by DegradeDecision. The modular breakdown exists to force DF’s semantics (degrade obedience, acquisition posture, stage gating, idempotent action intents, provenance) to be answered *somewhere*, while leaving model internals and infra to the implementer.

### 6.0 Module map (one screen)

DF is decomposed into 7 conceptual modules:

1. **Request Framing & ContextPins**
2. **Degrade Gate / Capabilities Enforcer**
3. **Context Acquisition (IEG)**
4. **Feature Acquisition (OFP)**
5. **Staged Decision Pipeline (0/1/2)**
6. **Action Derivation**
7. **Provenance & Output Assembly**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Request Framing & ContextPins

### Purpose

Normalize the incoming admitted event into a canonical DecisionRequest and ensure ContextPins are carried end-to-end.

### What it owns

* DecisionRequest shape (v0 minimum fields)
* request_id posture (v0: request_id = event_id)
* extraction/validation of event_id, event_time_utc, event_type from the envelope

### Questions this module must answer

* What fields are required to form a valid DecisionRequest?
* What happens when required fields are missing? (invalid request → fail-safe + provenance)
* How are ContextPins carried through outputs?

### Can be left to the implementer

* parsing mechanics and DTO representation
* how event_ref is represented internally

### Local vs deployed operation

* semantics identical; local may read from file logs, deployed from EB consumer

---

## 6.2 Module 2 — Degrade Gate / Capabilities Enforcer

### Purpose

Consume DegradeDecision and enforce CapabilityMask constraints with no bypass.

### What it owns

* enforcement of allow_ieg, allowed_feature_groups, stage gating, action_posture
* recording degrade decision used in provenance

### Questions this module must answer

* How is DegradeDecision obtained (inline vs cached) without changing semantics?
* What happens when a dependency is disallowed (skip path + record)?
* What happens if DL output is missing or invalid? (treat as FAIL_CLOSED; fail-safe)

### Can be left to the implementer

* where DL runs (inline module vs separate service)
* caching strategy for mode decisions

### Local vs deployed operation

* semantics identical; deployed may retrieve signals from real monitoring

---

## 6.3 Module 3 — Context Acquisition (IEG)

### Purpose

Obtain identity/graph context from IEG when permitted.

### What it owns

* allow_ieg gating and enforcement
* recording graph_version used (when consulted)
* explicit behavior when IEG is disallowed or unavailable

### Questions this module must answer

* When allow_ieg=true, what IEG queries are used (resolve_identity, neighbors)?
* What happens when IEG is unavailable? (proceed without; record unavailability)
* What does DF do when allow_ieg=false? (no call; no invented context)

### Can be left to the implementer

* query batching and caching
* choice of which neighbor depth/fields are fetched (within allowed posture)

### Local vs deployed operation

* local may mock IEG; deployed calls service; semantics unchanged

---

## 6.4 Module 4 — Feature Acquisition (OFP)

### Purpose

Request feature snapshots from OFP within the capability constraints and record feature provenance.

### What it owns

* enforcement of allowed_feature_groups
* as_of_time_utc posture (event_time_utc)
* staleness/missing posture effects on stage gating (skip stage2)
* recording OFP snapshot hash, group versions, freshness, input_basis

### Questions this module must answer

* Which groups are requested (subset of allowed groups)?
* How are OFP request keys determined (FeatureKeys from IEG or event)?
* What happens on OFP NOT_FOUND or stale groups? (record + skip stage2)
* What happens on OFP UNAVAILABLE? (fail-safe; record error)

### Can be left to the implementer

* caching of OFP responses
* timeouts and retry strategies (as long as recorded)

### Local vs deployed operation

* semantics identical; deployed emphasizes latency budgets

---

## 6.5 Module 5 — Staged Decision Pipeline (0/1/2)

### Purpose

Apply a staged evaluation pipeline to produce a decision outcome under the enforced degrade posture.

### What it owns

* Stage 0/1/2 structure and deterministic gating
* recording stage execution/skips and reasons
* mapping from stage outputs to DecisionOutcome

### Questions this module must answer

* What does Stage 0 (guardrails) do conceptually and what it cannot depend on?
* Under what conditions is Stage 1 executed (allow_model_primary)?
* Under what conditions is Stage 2 executed (allow_model_stage2 + non-stale features)?
* What happens if a stage fails internally? (record + fail-safe)
* How are outcomes produced deterministically?

### Can be left to the implementer

* the internal implementation of models/rules
* scoring algorithms and threshold tuning
* latency optimizations and circuit breakers (recorded)

### Local vs deployed operation

* semantics identical; deployed may use model serving endpoints

---

## 6.6 Module 6 — Action Derivation

### Purpose

Map the chosen DecisionOutcome into idempotent ActionIntents consistent with action_posture constraints.

### What it owns

* v0 action intent vocabulary
* idempotency key computation rule
* action_posture enforcement (STEP_UP_ONLY prohibits approvals)

### Questions this module must answer

* How does each DecisionOutcome map to one or more ActionIntents?
* How are idempotency keys derived deterministically?
* What happens when action_posture forbids an action? (substitute step-up; record)

### Can be left to the implementer

* action parameter formats (within schema constraints)
* case routing details (QUEUE_CASE parameters)

### Local vs deployed operation

* semantics identical; actions execution handled elsewhere

---

## 6.7 Module 7 — Provenance & Output Assembly

### Purpose

Assemble DecisionResponse and ensure provenance completeness and deterministic output shape.

### What it owns

* provenance minimum fields and inclusion rules
* stable ordering for actions and provenance lists/maps
* fail-safe error annotations

### Questions this module must answer

* What exact provenance fields are mandatory (DL/OFP/IEG/policy/timings)?
* How are stable ordering rules enforced?
* What is recorded when data is missing or stages skipped?
* How is request_id echoed and linked to event_id?

### Can be left to the implementer

* serialization library
* optional decision_hash posture (if added later)

### Local vs deployed operation

* semantics identical

---

## 6.8 Cross-module pinned items (summary)

Across all modules, DF must ensure:

* ContextPins always present in request/response
* DegradeDecision is enforced with no bypass
* OFP called with as_of_time_utc = event_time_utc and groups constrained by allowlist
* IEG called only when allowed and graph_version recorded if used
* staged pipeline gating is deterministic and recorded
* actions are idempotent with deterministic keys and obey action_posture
* fail-safe default produces STEP_UP intent on unsafe conditions
* provenance is complete and outputs are deterministically ordered

---

## 7) Degrade Ladder integration (v0)

> This section pins how DF consumes and obeys DegradeDecision so degrade behavior is explicit, auditable, and non-ambiguous.

### 7.1 Required DL input (pinned)

DF MUST consume a DegradeDecision containing:

* `mode` (degrade_mode)
* `capabilities_mask`
* `provenance` (triggers / signals snapshot)
* `decided_at_utc`
* optional `degrade_decision_id`

DF must treat DL output as authoritative for what is allowed.

---

### 7.2 Hard enforcement rules (no bypass)

DF MUST enforce CapabilityMask constraints:

* `allow_ieg=false` → no IEG calls
* `allowed_feature_groups` allowlist enforced on OFP requests
* `allow_model_stage2=false` → Stage 2 skipped
* `allow_model_primary=false` → Stage 1 skipped
* `allow_fallback_heuristics=false` → DF must not substitute heuristics when models/stages are disabled
* `action_posture=STEP_UP_ONLY` → DF must not emit approve actions

DF must not treat these as hints; they are hard constraints.

---

### 7.3 Degrade impacts on stage execution (pinned)

Pinned stage effects under degrade:

* If Stage 1 is disallowed → skip Stage 1 and record reason
* If Stage 2 is disallowed → skip Stage 2 and record reason
* If both are disallowed → decision is produced from Stage 0 only; if Stage 0 cannot decide safely → fail-safe STEP_UP

Additionally:

* If OFP returns stale/missing features for requested groups → Stage 2 is skipped (even if allow_model_stage2=true), and staleness is recorded.

---

### 7.4 Recording requirements (pinned)

DF provenance MUST include:

* degrade_mode
* full capabilities_mask used
* linkage to DL provenance:

  * either the full DegradeDecision object, or
  * degrade_decision_id + triggers snapshot reference

---

### 7.5 Missing/invalid DL posture (pinned)

If DF cannot obtain a valid DegradeDecision:

* treat as `FAIL_CLOSED`
* enforce FAIL_CLOSED mask
* record “DL invalid/unavailable” in provenance
* proceed with fail-safe outcome

---

### 7.6 Deterministic usage rule

For each DecisionResponse, DF must record the **exact** DL decision snapshot used. If DL is reevaluated frequently, DF cannot record “current mode”; it must record “mode used for this decision.”

---

## 8) Feature acquisition semantics (v0)

> This section pins how DF requests and uses OFP features, and how feature staleness/missingness affects DF stages and provenance.

### 8.1 Allowed feature groups (pinned)

DF may request feature groups only when permitted by DL:

* If `allowed_feature_groups=["*"]` → DF may request any group it needs.
* Otherwise DF MUST request only groups whose `group_name` appears in the allowlist.
* Group versions are explicit (v0): `{group_name, group_version}`.

---

### 8.2 as_of_time posture (pinned)

DF MUST call OFP with:

* `as_of_time_utc = event_time_utc` (from the admitted event envelope)

No hidden “now” and no wall-clock defaults.

---

### 8.3 Feature key posture (pinned)

DF requests OFP features keyed by canonical FeatureKeys:

* FeatureKey key_id must be canonical entity_id (IEG EntityRef)
* If allow_ieg=false, DF must proceed with the FeatureKeys it can derive without IEG (if any), and record the limitation.

(DF never keys OFP on raw identifiers in v0.)

---

### 8.4 Stale features posture (pinned)

If OFP returns any requested group as stale (`stale=true`):

* DF still records and may use the feature values (they were served)
* DF MUST:

  * record staleness in provenance (group_name/version + freshness block)
  * skip Stage 2 (even if allow_model_stage2=true)
  * proceed with Stage 0 and Stage 1 only (if Stage 1 allowed)

---

### 8.5 Missing / NOT_FOUND posture (pinned)

If OFP returns NOT_FOUND for requested groups (no data):

* DF records missingness in provenance
* DF skips Stage 2
* DF proceeds with Stage 0 and Stage 1 only (if Stage 1 allowed)

If missingness prevents safe Stage 1 operation, DF must fail-safe STEP_UP.

---

### 8.6 OFP UNAVAILABLE posture (pinned)

If OFP is unavailable:

* DF records OFP unavailability in provenance
* DF skips Stage 2
* DF proceeds with Stage 0 and Stage 1 only if Stage 1 can run safely without OFP features; otherwise DF fails-safe STEP_UP.

---

### 8.7 Required feature provenance capture (pinned)

DF provenance MUST include (from OFP):

* feature_snapshot_hash
* group versions used
* freshness blocks (including stale flags)
* input_basis watermark vector

These are necessary for audit and replay explainability.

---

## 9) Identity/graph context semantics (v0)

> This section pins how DF uses IEG for identity/graph context, and how that is controlled by DegradeDecision.

### 9.1 allow_ieg gating (pinned)

* If `allow_ieg=false`: DF MUST NOT call IEG.
* If `allow_ieg=true`: DF may call IEG for identity resolution and/or neighbor context.

No bypass is permitted.

---

### 9.2 What DF may request from IEG (v0 posture)

When allowed, DF may use IEG to:

* resolve canonical EntityRefs from observed identifiers (resolve_identity)
* fetch neighbor context (get_neighbors) if needed by the policy/model

The exact query mix is implementer freedom, but:

* any IEG consultation must be recorded (see below).

---

### 9.3 Recording graph_version (pinned)

If DF consults IEG:

* DF MUST record the `graph_version` returned/used in DecisionProvenance.

If DF does not consult IEG (disallowed or skipped):

* DF MUST record that IEG context was not used and why (disallowed vs unavailable).

---

### 9.4 IEG UNAVAILABLE posture (pinned)

If allow_ieg=true but IEG is unavailable:

* DF proceeds without IEG context
* DF records unavailability in provenance
* DF must not invent identities or graph neighbors.

If the absence of IEG context prevents safe decisioning, DF must fail-safe STEP_UP.

---

### 9.5 Interaction with OFP and FeatureKeys

* DF and OFP use canonical entity IDs as keys.
* If DF cannot consult IEG, it may have reduced ability to derive canonical keys; DF must record this limitation and proceed conservatively.

---

## 10) Staged decision pipeline semantics (v0)

> This section pins the v0 staged pipeline posture and how degrade/inputs affect stage execution. It does not pin model internals; it pins **stage structure and gating** so behaviour is predictable and auditable.

### 10.1 Stage definitions (v0)

Pinned stage structure:

* **Stage 0: Guardrails**

  * deterministic hard rules / sanity checks
  * must not rely on Stage 1/2 availability
  * may operate with minimal inputs

* **Stage 1: Primary**

  * primary policy/model evaluation
  * executed only if allowed by capabilities and inputs are sufficient

* **Stage 2: Secondary**

  * secondary model/challenger/escalation stage
  * executed only if explicitly allowed and required inputs are non-stale/available

---

### 10.2 Stage gating rules (pinned)

Stage execution is gated by:

**DegradeDecision capability flags**

* Stage 1 runs only if `allow_model_primary=true`
* Stage 2 runs only if `allow_model_stage2=true`

**Input availability posture**

* Stage 2 additionally requires that requested OFP groups are:

  * not stale, and
  * not missing,
    for this request (v0 pinned rule)

If a stage is gated off:

* it is skipped
* the skip reason is recorded in provenance.

---

### 10.3 Stage 0 behaviour (pinned fail-safe anchor)

Stage 0 always executes and ensures a safe baseline:

* If the system is highly degraded or inputs are insufficient for safe model evaluation, Stage 0 must be able to produce a conservative outcome.
* If Stage 0 cannot decide safely due to missing required request fields, DF falls back to fail-safe STEP_UP.

---

### 10.4 Stage 1 behaviour (v0 posture)

Stage 1 is the primary policy/model stage:

* It may depend on OFP features and optionally IEG context.
* If required inputs are unavailable (OFP unavailable or keys missing), Stage 1 is skipped or degraded according to the policy, but v0 pinned rule is:

  * if Stage 1 cannot run safely, DF fails-safe STEP_UP.

Stage 1 internals (rules/ML) are implementation freedom.

---

### 10.5 Stage 2 behaviour (v0 posture)

Stage 2 is optional and is the first thing disabled under degrade:

* If Stage 2 is disabled by capabilities OR inputs are stale/missing → Stage 2 is skipped.
* Stage 2 must never run when OFP inputs are stale/missing in v0.

Stage 2 internals are implementation freedom.

---

### 10.6 Deterministic stage execution summary (pinned)

DF provenance must include a stage execution summary:

* which stages ran
* which were skipped
* skip reasons (capability-disabled, stale features, missing features, dependency unavailable, etc.)
* optional per-stage timing (if captured)

---

### 10.7 Latency-budget awareness (conceptual)

DF may shorten itself under degrade by skipping expensive stages, but must:

* record what was skipped and why
* avoid changing meaning silently (degrade mode + mask makes it explicit)

---

## 11) Outputs: DecisionResponse, ActionIntents, and determinism rules

> This section pins DF outputs (DecisionResponse + ActionIntents) and the determinism rules that prevent drift across implementations.

### 11.1 DecisionResponse shape (v0)

DF outputs a DecisionResponse containing:

* `context_pins`
* `request_id` (v0: event_id)
* `event_ref` (opaque) + `event_id`
* `decision_outcome` (enum)
* `actions[]` (ActionIntents)
* `provenance` (DecisionProvenance)

DecisionResponse is the authoritative unit recorded by Decision Log.

---

### 11.2 DecisionOutcome vocabulary (v0 enum)

Pinned outcomes:

* `APPROVE`
* `DECLINE`
* `STEP_UP`
* `REVIEW`

Outcomes must map to action intents consistently.

---

### 11.3 ActionIntent vocabulary (v0 enum)

Pinned action types:

* `APPROVE_TRANSACTION`
* `DECLINE_TRANSACTION`
* `STEP_UP_AUTH`
* `QUEUE_CASE`

Each ActionIntent includes:

* `action_type`
* `idempotency_key` (deterministic)
* `parameters` (object; minimal required keys pinned in contracts/specs)

---

### 11.4 Action intent idempotency (pinned)

Each ActionIntent must have:

* `idempotency_key = H(ContextPins, event_id, action_type)`

This ensures duplicate DF processing does not produce multiple real-world side effects.

---

### 11.5 Action posture constraints (from DL)

If DL capability mask sets:

* `action_posture=STEP_UP_ONLY`

Then DF must enforce:

* no `APPROVE_TRANSACTION` intents are emitted.
* DF may emit `STEP_UP_AUTH` (and optionally `QUEUE_CASE`) as conservative actions.

Any constraint enforcement must be recorded in provenance.

---

### 11.6 Deterministic output ordering (pinned)

To prevent drift:

* `actions[]` must be sorted deterministically by `action_type` (and stable tie-break if multiple same type)
* provenance lists (feature groups, triggers, warnings, stage summary entries) must be deterministically ordered
* maps must be serialized with stable ordering where hashing/comparison is expected

DF must not rely on insertion order or backend iteration order.

---

### 11.7 Optional decision_hash (not required in v0)

DF may later include a `decision_hash` for stronger audit parity, but v0 does not require it. If introduced, it must follow stable canonicalization rules similar to OFP snapshot_hash posture.

---

## 12) Provenance bundle (audit minimum)

> This section pins the minimum provenance DF must emit so decisions are explainable and replay/audit can reconstruct “what we knew and why we acted.”

### 12.1 Provenance purpose

DecisionProvenance must allow an auditor (or replay tooling) to answer:

* what degrade posture applied,
* what feature/identity context was used,
* what versions of definitions/models were used,
* what stages ran or were skipped,
* and what timing/availability constraints shaped the outcome.

---

### 12.2 Mandatory provenance fields (pinned)

Every DecisionResponse MUST include provenance containing:

1. **ContextPins**

* `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`

2. **Degrade decision used**

* `degrade_mode`
* `capabilities_mask` (full mask as applied)
* linkage to DL provenance:

  * either inline triggers, or
  * `degrade_decision_id` / reference

3. **OFP features used**

* `feature_snapshot_hash`
* `feature_groups_used[]` (group_name + group_version)
* `freshness[]` blocks (per group)
* `ofp_input_basis` watermark vector (per-partition offsets)

4. **IEG context used (when consulted)**

* `graph_version` (if IEG consulted)

If IEG not used:

* record reason: disallowed vs unavailable.

5. **DF policy/model references**

* `df_policy_ref` (string; v0 placeholder allowed)
* optional model refs per stage (if multiple)

6. **Stage execution summary**

* stage list:

  * ran/skipped
  * skip reason (capability-disabled, stale, missing, unavailable)
* optional per-stage timing

7. **Timing fields**

* `started_at_utc`
* `ended_at_utc`
* optional stage timings

8. **Error annotations (when applicable)**

* `error_code` / `error_reason` (if fail-safe or degraded due to dependency failures)
* `retryable` flag (if relevant)

---

### 12.3 Deterministic shape rules for provenance

To keep provenance stable and scannable:

* lists are sorted deterministically (groups, triggers, stage entries, warnings)
* maps are serialized with stable ordering (if any)
* timestamps are in UTC and in canonical string format

---

### 12.4 Provenance completeness under degrade

When stages are skipped or dependencies disallowed/unavailable:

* DF MUST still emit provenance, explicitly stating:

  * what was skipped
  * why it was skipped
  * what substitute posture was used (fail-safe STEP_UP if needed)

No silent omissions.

---

## 13) Contracts philosophy and contract pack overview (v0)

> DF contracts exist to pin **DecisionRequest/DecisionResponse boundary shapes** in a machine-checkable way without exploding contract surface area. Contracts define shape; DF specs define behavior (degrade obedience, stage gating, fail-safe posture).

### 13.1 v0 contract strategy (one schema file)

DF v0 ships **one** schema file:

* `contracts/df_public_contracts_v0.schema.json`

This keeps the surface small and still enforceable for:

* Decision Log ingestion
* Actions Layer consumption
* Canonical Event Contract Pack integration later

---

### 13.2 Validation targeting rule (self-describing)

All DF contract objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

### 13.3 `$defs` inventory (v0)

`df_public_contracts_v0.schema.json` contains `$defs` for:

* `ContextPins` (same shape used across the loop)
* `DecisionRequest`
* `DecisionOutcome` (enum)
* `ActionType` (enum)
* `ActionIntent`
* `DecisionProvenance` (minimum fields pinned in §12)
* `DecisionResponse`
* `ErrorResponse` (thin; error_code/message/retryable)

Refs remain opaque in v0:

* `event_ref`
* optional `degrade_decision_ref`
* optional feature refs beyond hash (OFP is referenced by hash + provenance)

---

### 13.4 What contracts cover vs what specs cover

#### Contracts cover (shape/structure)

* required fields for request/response
* stable enums for DecisionOutcome and ActionType
* required ActionIntent idempotency_key field
* required provenance fields presence
* deterministic structure (lists/maps locations)

#### Specs cover (behavior/invariants)

* DegradeDecision enforcement rules (no bypass)
* stage gating rules (capabilities + input staleness)
* fail-safe posture mapping to STEP_UP intent
* deterministic ordering rules (actions and provenance lists)
* when and how OFP/IEG are consulted

---

### 13.5 Relationship to Canonical Event Contract Pack

DF outputs will become canonical payloads/events:

* DecisionRequest (input)
* DecisionResponse / DecisionMade event
* ActionIntent event

In v0, DF schemas keep refs opaque. In v1, Canonical Event Contract Pack can:

* define envelope fields for these events
* reference DF `$defs` for payload shape to avoid drift

---

## 14) Addressing, naming, and discoverability (conceptual)

> This section defines how DF outputs are referenced and reconciled without guessing. It stays conceptual because storage/transport is implementation freedom in v0.

### 14.1 Design goals

DF discoverability must support:

* **auditability:** Decision Log can reconstruct “what happened and why”
* **idempotent action execution:** Actions layer can dedupe by idempotency_key
* **replayability:** duplicates/replays of the same event do not create new side effects

---

### 14.2 Primary identifiers

In v0, the primary identifiers for DF outputs are:

* `event_id` (from admitted event)
* `request_id` (v0: equals event_id)

These keys anchor idempotency and log correlation.

---

### 14.3 Action intent idempotency discoverability

Action intents carry deterministic:

* `idempotency_key = H(ContextPins, event_id, action_type)`

Actions Layer can use this key to:

* dedupe repeats
* safely retry side effects

---

### 14.4 Provenance linkage discoverability

DF provenance includes:

* `feature_snapshot_hash` (OFP)
* OFP group versions and input_basis (watermarks)
* graph_version (IEG) if used
* degrade_mode + mask and linkage to DL provenance

These fields allow Decision Log to cross-link:

* to OFP and IEG context basis
* to degrade posture used

---

### 14.5 Local vs deployed semantics

* **Local:** DF may write outputs to local files/logs; the semantic identifiers remain event_id/request_id and idempotency keys.
* **Deployed:** DF may emit decision events and action intents onto EB and/or to services; Decision Log persists authoritative record.

Pinned rule:

* regardless of transport, DF outputs must be deterministically linkable by event_id/request_id and idempotency keys.

---

### 14.6 Optional durable references (implementation freedom)

DF may optionally persist:

* DecisionResponse artifacts (files/object store/db)
* a “decision made” event to EB

But these are implementation choices; the conceptual contract focuses on the payload shapes and idempotency anchors.

---

## 15) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Decision Fabric docs and contracts. The goal is a **single, deep reading surface** for DF design, plus a **minimal v0 contract**.

### 15.1 Target location in repo

Conceptually, DF lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/decision_fabric/`

This folder should be self-contained: a new contributor should understand DF by starting here.

---

### 15.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ decision_fabric/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ DF1_charter_and_boundaries.md
         │  ├─ DF2_inputs_outputs_core_contracts.md
         │  ├─ DF3_degrade_obedience_and_staged_pipeline.md
         │  ├─ DF4_feature_and_context_acquisition_semantics.md
         │  └─ DF5_outputs_actions_provenance_ops_acceptance.md
         │
         └─ contracts/
            └─ df_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; DF v0 needs only **one** schema file here.

---

### 15.3 What each file is for (intent)

#### `README.md`

* Entry point: what DF is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (designer-locked v0 intent)
  * `specs/` reading order (DF1–DF5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This stitched conceptual design document:

  * DF purpose in platform
  * DF laws (degrade obedience, stage gating, idempotent actions, provenance)
  * designer-locked v0 decisions
  * modular breakdown + questions per module
  * contract pack overview (v0)
  * discoverability concepts (event_id/request_id, idempotency keys)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behavior/invariants
  * contract schema defines boundary shapes
* Non-negotiables:

  * ContextPins scoping
  * request_id = event_id
  * DL constraints enforced with no bypass
  * stage gating rules
  * OFP as_of_time posture + stale handling
  * IEG gating + graph_version recording
  * idempotent action intents
  * provenance completeness and deterministic ordering
  * fail-safe STEP_UP posture on unsafe conditions

#### `specs/`

* DF1–DF5 are the eventual binding-ish DF design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `df_public_contracts_v0.schema.json` pins DF boundary objects.

---

### 15.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (designer-locked intent)
3. `specs/DF1_...` → `specs/DF5_...` (behavior/invariants)
4. `contracts/df_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

### 15.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge DF1–DF5 into fewer docs once stable.
* Add `contracts/README.md` only if you need a brief note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders under deadline.

---

## 16) What the eventual spec docs must capture (mapping)

> This section bridges the DF conceptual design into the **actual DF spec docs** (DF1–DF5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 16.0 Mapping rule (how to use this section)

For every DF “law” and designer-locked decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in DF1–DF5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 16.1 DF1 — Charter & boundaries

### DF1 must capture

* DF purpose as the **decisioning core** of the loop
* authority boundaries:

  * authoritative for DecisionResponse + ActionIntents + provenance
  * not feature computation, not identity truth, not validation/durability
* DF laws:

  * ContextPins scoping
  * hard obedience to DL mask (no bypass)
  * idempotent action intents
  * provenance completeness
  * fail-safe posture (STEP_UP)
  * deterministic output ordering

### DF1 may leave to the implementer

* deployment model and infra topology

---

## 16.2 DF2 — Inputs, outputs, core contracts

### DF2 must capture

* DecisionRequest shape and required fields
* v0 idempotency posture:

  * request_id = event_id
* DecisionResponse shape (outcome + actions + provenance)
* enums for outcomes and action types
* basic error model (INVALID_REQUEST vs UNAVAILABLE etc., as pinned in contract)

### DF2 may leave to the implementer

* how event_ref is represented and transported

---

## 16.3 DF3 — Degrade obedience & staged pipeline

### DF3 must capture

* enforcement rules for CapabilityMask
* stage definitions (Stage 0/1/2) and deterministic gating rules
* skip reasons and how they are recorded in provenance
* fail-closed posture when DL decision missing/invalid (treat as FAIL_CLOSED)

### DF3 may leave to the implementer

* internal model/rules implementation

---

## 16.4 DF4 — Feature & context acquisition semantics

### DF4 must capture

* OFP call posture:

  * group allowlist enforcement
  * as_of_time_utc = event_time_utc
  * stale/missing handling (skip stage2; record)
* IEG call posture:

  * gated by allow_ieg
  * record graph_version if used
  * proceed without if disallowed/unavailable, with recording
* required provenance captured from OFP/IEG

### DF4 may leave to the implementer

* caching, retries, timeouts (as long as recorded and deterministic in meaning)

---

## 16.5 DF5 — Outputs, actions, provenance, ops & acceptance

### DF5 must capture

* DecisionOutcome → ActionIntent mapping rules
* action_posture STEP_UP_ONLY enforcement rule
* idempotency_key rule for ActionIntent
* provenance minimum fields list and deterministic ordering rules
* ops minimums:

  * latency, error rates, degrade mode distribution
* acceptance scenarios:

  * obey degrade
  * idempotent actions under duplicates
  * stale/missing features handled as pinned
  * fail-safe STEP_UP on unsafe conditions
  * provenance completeness

### DF5 may leave to the implementer

* observability tooling stack details

---

## 16.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* ContextPins
* DecisionRequest and DecisionResponse shapes
* enums: DecisionOutcome and ActionType
* ActionIntent with idempotency_key required
* DecisionProvenance with required fields presence
* ErrorResponse with retryable boolean
* validation targeting via kind + contract_version

### Specs must include

* behavior rules:

  * degrade obedience and stage gating
  * OFP/IEG acquisition posture
  * fail-safe STEP_UP posture mapping
  * deterministic ordering rules for outputs/provenance
  * what is recorded when inputs are stale/missing/disallowed/unavailable

---

## 16.7 Minimal completeness standard (so DF is implementable)

DF is “spec-ready” when DF1–DF5 collectively pin:

* request framing + idempotency posture
* degrade enforcement + stage gating
* OFP/IEG acquisition semantics and recording
* outcome/action vocab + idempotent intents
* provenance completeness + deterministic ordering
* fail-safe posture and acceptance scenarios

Everything else can remain implementer freedom.

---

## 17) Acceptance questions and Definition of Done

> This section is the conceptual **ship checklist** for DF v0: the questions DF must answer and the minimal behavioural scenarios that indicate DF is correct enough to implement and integrate.

### 17.1 Acceptance questions (DF must answer these unambiguously)

1. **What decision posture was in effect?**

* Does every DecisionResponse include degrade_mode and the capability mask used (or linkage)?

2. **Did DF obey the Degrade Ladder?**

* Can we verify DF did not call disallowed dependencies or run disallowed stages?

3. **What feature context was used?**

* Does provenance include OFP feature_snapshot_hash, group versions, freshness, input_basis?

4. **Was IEG consulted, and what version?**

* If allowed and used, is graph_version recorded?
* If disallowed/unavailable, is that recorded explicitly?

5. **Which stages ran, and why?**

* Does provenance include stage execution summary with skip reasons?

6. **Are action intents safe under duplicates?**

* Do ActionIntents carry deterministic idempotency keys?

7. **Are outputs deterministic in shape?**

* Are actions and provenance lists/maps consistently ordered?

8. **What happens under stale or missing features?**

* Does DF skip Stage 2 and record staleness/missingness?

9. **What happens under dependency failures?**

* Does DF fail-safe STEP_UP with explicit error annotations?

---

### 17.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Degrade obedience (no bypass)

**Given**

* DL outputs `allow_ieg=false`, `allow_model_stage2=false`, restricted feature groups

**Expect**

* DF does not call IEG
* DF does not run Stage 2
* DF requests only allowed feature groups
* DF records DL mode/mask in provenance

---

#### DoD-2: Idempotent action intents under duplicate event delivery

**Given**

* the same admitted event is processed twice (duplicate delivery)

**Expect**

* DF emits ActionIntents with the same idempotency keys
* Actions Layer can dedupe and does not execute side effects twice

---

#### DoD-3: Stage gating recorded deterministically

**Given**

* Stage 2 is disallowed by DL OR features are stale

**Expect**

* Stage 2 skipped
* provenance includes skip reason (capability-disabled or stale/missing)
* decision outcome is produced from remaining stages

---

#### DoD-4: Stale features cause Stage 2 skip

**Given**

* OFP returns stale=true for any requested group

**Expect**

* DF records freshness blocks and stale warnings
* DF skips Stage 2
* DF proceeds with Stage 0 + Stage 1 (if allowed)

---

#### DoD-5: Missing features (NOT_FOUND) handled safely

**Given**

* OFP returns NOT_FOUND for requested groups

**Expect**

* DF records missingness
* DF skips Stage 2
* if Stage 1 cannot run safely, DF fail-safe STEP_UP

---

#### DoD-6: IEG unavailable handled safely

**Given**

* allow_ieg=true but IEG is unavailable

**Expect**

* DF proceeds without IEG context
* DF records unavailability
* if safe decisioning is compromised, DF fail-safe STEP_UP

---

#### DoD-7: Fail-safe posture on internal or dependency failures

**Given**

* DF cannot complete safely due to an internal error or missing required request fields

**Expect**

* DecisionOutcome = STEP_UP
* ActionIntent includes STEP_UP_AUTH with deterministic idempotency key
* error details recorded with retryable flag as appropriate

---

#### DoD-8: Provenance completeness

**Given**

* any DecisionResponse

**Expect**

* provenance includes:

  * ContextPins
  * DL mode + mask (and triggers linkage)
  * OFP snapshot hash + group versions + freshness + input_basis
  * graph_version if used
  * stage summary + timings
  * policy refs
* deterministic ordering in lists/maps

---

### 17.3 Minimal deliverables required to claim “DoD satisfied”

To claim DF meets DoD at v0 conceptual level, you should be able to show:

* a DecisionRequest/DecisionResponse example (NORMAL mode)
* a DecisionResponse example under DEGRADED_2 / STEP_UP_ONLY
* proof DF obeyed allowlists/allow_ieg/stage gating rules
* duplicate delivery test showing identical idempotency keys
* stale feature test showing Stage 2 skipped and recorded
* fail-safe test showing STEP_UP posture with error annotations

---

## 18) Open decisions log (v0 residuals only)

> These are the only remaining decisions for DF v0 that are not already designer-locked. Everything else is pinned above or is implementation freedom.

### DEC-DF-001 — df_policy_ref naming/versioning convention

* **Question:** what is the canonical naming/versioning format for `df_policy_ref` in v0 (and how it evolves)?
* **Status:** OPEN (v0 residual)
* **Close in:** DF3/DF5
* **Constraint:** must be stable and recorded on every decision.

### DEC-DF-002 — Stage 0 rule vocabulary (guardrails rule IDs)

* **Question:** do we assign stable IDs to guardrail rules (so provenance can cite which fired)?
* **Status:** OPEN (v0 residual)
* **Close in:** DF3/DF5
* **Constraint:** if included, rule IDs must be deterministic and stable.

### DEC-DF-003 — Stage failure classification

* **Question:** how are internal stage failures categorized in provenance (error_code taxonomy)?
* **Status:** OPEN (v0 residual)
* **Close in:** DF5
* **Constraint:** must not affect fail-safe posture; only improves audit clarity.

### DEC-DF-004 — Multi-action posture per outcome

* **Question:** can DF emit multiple actions for one decision (e.g., STEP_UP_AUTH + QUEUE_CASE)?
* **Status:** OPEN (v0 residual)
* **Close in:** DF5 + contracts
* **Constraint:** output ordering must remain deterministic.

### DEC-DF-005 — NOT_FOUND vs empty snapshot semantics (OFP interplay)

* **Question:** when OFP returns no data, do we treat as NOT_FOUND, stale/no-data warning, or both?
* **Status:** OPEN (v0 residual)
* **Close in:** DF4/DF5
* **Constraint:** must align with OFP v0 semantics and stage gating rules.

### DEC-DF-006 — DecisionResponse emission onto EB (v0)

* **Question:** does DF emit decision made/action intent events to EB in v0, or is Decision Log persistence sufficient?
* **Status:** OPEN (v0 residual)
* **Close in:** DF5
* **Constraint:** if emitted, payload shape must match Canonical Event Contract Pack later.

### DEC-DF-007 — decision_hash inclusion (v0)

* **Question:** do we add an optional deterministic `decision_hash` field for audit parity?
* **Status:** OPEN (v0 residual)
* **Close in:** DF5
* **Constraint:** if included, must follow stable canonicalization rules.

### DEC-DF-008 — Timeout budgets per dependency

* **Question:** do we pin timeout budgets for OFP/IEG/model calls in v0?
* **Status:** OPEN (v0 residual)
* **Close in:** DF5 (ops)
* **Constraint:** if pinned, must interact cleanly with degrade posture and be recorded in provenance when exceeded.

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate DF v0 boundary objects and provenance expectations.
> Refs are opaque in v0; Decision Log persists the full DecisionResponse.

---

### A.1 Example — `DecisionRequest`

```json
{
  "kind": "decision_request",
  "contract_version": "df_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "event_ref": "eb://admitted_events/partition=0/offset=9812399",
  "event_id": "evt_txn_000000123",
  "event_time_utc": "2026-01-03T12:34:56Z",
  "event_type": "transaction_event",

  "request_id": "evt_txn_000000123"
}
```

---

### A.2 Example — `DecisionResponse` (NORMAL mode, APPROVE)

```json
{
  "kind": "decision_response",
  "contract_version": "df_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "request_id": "evt_txn_000000123",
  "event_id": "evt_txn_000000123",
  "event_ref": "eb://admitted_events/partition=0/offset=9812399",

  "decision_outcome": "APPROVE",

  "actions": [
    {
      "action_type": "APPROVE_TRANSACTION",
      "idempotency_key": "H(pins,evt_txn_000000123,APPROVE_TRANSACTION)",
      "parameters": {
        "reason": "risk_below_threshold"
      }
    }
  ],

  "provenance": {
    "context_pins": {
      "scenario_id": "scn_baseline_v1",
      "run_id": "run_20260103T110000Z_0001",
      "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
      "parameter_hash": "ph_4b1d7a9c"
    },

    "degrade": {
      "mode": "NORMAL",
      "capabilities_mask": {
        "allow_ieg": true,
        "allowed_feature_groups": ["*"],
        "allow_model_primary": true,
        "allow_model_stage2": true,
        "allow_fallback_heuristics": true,
        "action_posture": "NORMAL"
      },
      "decided_at_utc": "2026-01-03T12:34:56Z",
      "triggers": []
    },

    "ofp": {
      "feature_snapshot_hash": "fsh_6d3c...a91b",
      "group_versions_used": [
        { "group_name": "txn_velocity", "group_version": "1.0" }
      ],
      "freshness": [
        {
          "group_name": "txn_velocity",
          "group_version": "1.0",
          "ttl_seconds": 600,
          "last_update_event_time": "2026-01-03T12:34:30Z",
          "age_seconds": 26,
          "stale": false
        }
      ],
      "input_basis": {
        "stream_name": "admitted_events",
        "watermark_basis": { "partition_0": 9812400 }
      }
    },

    "ieg": {
      "used": true,
      "graph_version": {
        "graph_version": "gv_admitted_events_run_20260103T110000Z_0001_000042",
        "stream_name": "admitted_events",
        "watermark_basis": { "partition_0": 9812400 }
      }
    },

    "df_policy_ref": "df_policy_v0",
    "stage_summary": [
      { "stage": "stage0_guardrails", "status": "ran" },
      { "stage": "stage1_primary", "status": "ran" },
      { "stage": "stage2_secondary", "status": "ran" }
    ],

    "timings": {
      "started_at_utc": "2026-01-03T12:34:56Z",
      "ended_at_utc": "2026-01-03T12:34:56Z"
    }
  }
}
```

---

### A.3 Example — `DecisionResponse` (DEGRADED_2 / STEP_UP_ONLY)

```json
{
  "kind": "decision_response",
  "contract_version": "df_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "request_id": "evt_txn_000000124",
  "event_id": "evt_txn_000000124",
  "event_ref": "eb://admitted_events/partition=0/offset=9812400",

  "decision_outcome": "STEP_UP",

  "actions": [
    {
      "action_type": "STEP_UP_AUTH",
      "idempotency_key": "H(pins,evt_txn_000000124,STEP_UP_AUTH)",
      "parameters": {
        "challenge": "3ds"
      }
    }
  ],

  "provenance": {
    "degrade": {
      "mode": "DEGRADED_2",
      "capabilities_mask": {
        "allow_ieg": false,
        "allowed_feature_groups": [],
        "allow_model_primary": true,
        "allow_model_stage2": false,
        "allow_fallback_heuristics": true,
        "action_posture": "STEP_UP_ONLY"
      },
      "decided_at_utc": "2026-01-03T12:35:10Z",
      "triggers": [
        {
          "signal_name": "ieg_error_rate",
          "observed_value": 0.25,
          "threshold": 0.10,
          "comparison": ">",
          "triggered_at_utc": "2026-01-03T12:35:10Z"
        }
      ]
    },

    "ofp": {
      "feature_snapshot_hash": "fsh_degraded_no_ofp",
      "group_versions_used": [],
      "freshness": [],
      "input_basis": {
        "stream_name": "admitted_events",
        "watermark_basis": { "partition_0": 9812400 }
      },
      "note": "OFP not used due to DL capabilities_mask."
    },

    "ieg": {
      "used": false,
      "reason": "DISALLOWED_BY_DEGRADE"
    },

    "df_policy_ref": "df_policy_v0",
    "stage_summary": [
      { "stage": "stage0_guardrails", "status": "ran" },
      { "stage": "stage1_primary", "status": "ran", "note": "ran without OFP/IEG context" },
      { "stage": "stage2_secondary", "status": "skipped", "reason": "DISALLOWED_BY_CAPABILITIES" }
    ],

    "timings": {
      "started_at_utc": "2026-01-03T12:35:10Z",
      "ended_at_utc": "2026-01-03T12:35:10Z"
    }
  }
}
```

---

### A.4 Example — Fail-safe response (dependency failure)

```json
{
  "kind": "decision_response",
  "contract_version": "df_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "request_id": "evt_txn_000000125",
  "event_id": "evt_txn_000000125",
  "event_ref": "eb://admitted_events/partition=0/offset=9812401",

  "decision_outcome": "STEP_UP",

  "actions": [
    {
      "action_type": "STEP_UP_AUTH",
      "idempotency_key": "H(pins,evt_txn_000000125,STEP_UP_AUTH)",
      "parameters": { "challenge": "3ds" }
    }
  ],

  "provenance": {
    "degrade": { "mode": "NORMAL" },
    "error": {
      "error_code": "OFP_UNAVAILABLE",
      "message": "OFP timed out",
      "retryable": true
    },
    "stage_summary": [
      { "stage": "stage0_guardrails", "status": "ran" },
      { "stage": "stage1_primary", "status": "skipped", "reason": "DEPENDENCY_UNAVAILABLE" },
      { "stage": "stage2_secondary", "status": "skipped", "reason": "DEPENDENCY_UNAVAILABLE" }
    ]
  }
}
```

---

## Appendix B — ASCII sequences (end-to-end, degrade gating, fail-safe)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/emit
> Notes like `[mask]` indicate where DL constraints are applied.

---

### B.1 End-to-end (event → DL → OFP/IEG → stages → decision → actions → log)

```
Participants:
  EB | DF(Framing) | DL | DF(Degrade Gate) | IEG | OFP | DF(Stages) | DF(Actions) | Decision Log | Actions Layer

EB --> DF(Framing): admitted_event (event_ref + envelope fields)
DF(Framing): build DecisionRequest (ContextPins, event_id, event_time_utc, request_id)

DF -> DL: fetch current DegradeDecision
DL -> DF: DegradeDecision(mode, capabilities_mask, provenance)

DF(Degrade Gate): enforce [mask]
  - decide whether IEG/OFP/stage2 are allowed

(if allow_ieg=true)
  DF -> IEG: resolve_identity / neighbors
  IEG -> DF: context + graph_version
(if allow_ieg=false)
  DF: no IEG call; record disallowed

(if OFP groups allowed)
  DF -> OFP: get_features(keys, groups, as_of_time_utc=event_time_utc)
  OFP -> DF: feature_snapshot + provenance (freshness + snapshot_hash + input_basis)
(if OFP disallowed)
  DF: no OFP call; record disallowed

DF(Stages): execute Stage 0 always
DF(Stages): execute Stage 1 if allowed
DF(Stages): execute Stage 2 if allowed AND features not stale/missing

DF(Actions): derive ActionIntents (idempotency keys deterministic)
DF => Decision Log: write DecisionResponse (outcome + actions + provenance)
DF => Actions Layer: emit ActionIntents (idempotent)
```

---

### B.2 Degrade disables IEG and Stage 2 (DEGRADED_1 / DEGRADED_2)

```
DL -> DF: DegradeDecision(mode=DEGRADED_1, mask: allow_ieg=false, allow_model_stage2=false)

DF: enforce mask
  - no IEG calls
  - Stage 2 skipped
  - OFP limited to allowed_feature_groups

DF: records degrade mode + mask in provenance
```

---

### B.3 Stale features force Stage 2 skip (even if allowed)

```
DL -> DF: allow_model_stage2=true
DF -> OFP: get_features(...)
OFP -> DF: freshness indicates stale=true for group txn_velocity

DF: records staleness in provenance
DF: Stage 2 skipped due to stale inputs
DF: Stage 0 + Stage 1 proceed (if allowed)
```

---

### B.4 Fail-safe path (dependency unavailable)

```
DF -> OFP: get_features(...)
OFP timeout/unavailable

DF: records dependency failure
DF: skips Stage 1/2 if cannot run safely
DF: outputs STEP_UP + STEP_UP_AUTH intent (fail-safe)
DF: records provenance including error_code + retryable
```

---