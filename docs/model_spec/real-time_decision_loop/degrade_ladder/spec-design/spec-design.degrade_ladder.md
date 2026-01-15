# DL — Conceptual Spec Design Doc (non-spec) — Section Header Plan

## 0) Document metadata

### 0.1 Document header

* **Title:** *Degrade Ladder (DL) — Conceptual Spec Design (v0)*
* **Plane:** Real-Time Decision Loop / Degrade Ladder
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final
* **Version:** v0.x
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Capture the **designer-locked v0 intent** for Degrade Ladder in one place (no drift).
* Provide the roadmap for writing:

  * DL1–DL5 specs (behaviour/invariants)
  * `contracts/dl_public_contracts_v0.schema.json` (machine-checkable boundary shapes)
* Ensure Decision Fabric and Decision Log have a single, unambiguous source of truth for:

  * degrade_mode meaning
  * capability constraints
  * provenance requirements

### 0.3 Audience and prerequisites

* **Primary:** you (designer), Codex (implementer)
* **Secondary:** Decision Fabric, Decision Log, OFP, IEG, Observability owners
* **Prerequisites:**

  * OFP v0 provides serving posture + staleness/freshness signals
  * IEG v0 provides query posture + availability signals
  * EB v0 provides lag/backpressure signals
  * Model serving provides latency/error signals

### 0.4 How to use this document

* This doc is **directional alignment** and a **question map**, not binding spec text.
* Normative truth lives in:

  * DL specs (DL1–DL5), and
  * DL contract schema file
* Every pinned decision here must appear later as a closed decision in specs/contracts.

### 0.5 Scope and non-scope

* **In scope:** mode ladder, capability mask, signals considered, evaluation determinism, hysteresis rules, missing-signal posture, output/provenance shape, downstream obligations.
* **Out of scope:** exact threshold numbers (config), metrics plumbing implementation, detailed IAM design, deployment topology.

### 0.6 Proposed repo placement (conceptual)

* `docs/model_spec/real-time_decision_loop/degrade_ladder/CONCEPTUAL.md`
* Related:

  * `specs/DL1_...` → `specs/DL5_...`
  * `contracts/dl_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Degrade Ladder exists

Degrade Ladder (DL) is a **control-plane policy module** inside the Real-Time Decision Loop. Its job is to decide **“what level of service is safe right now”** based on current health signals, and to make that decision **explicit, deterministic, and auditable**.

One sentence: **“Select the safest allowed decisioning posture given current health, and make that choice recordable and enforceable.”**

---

### 1.2 Where DL sits in the loop

DL sits alongside (or inside) Decision Fabric and depends on health signals from key loop services:

* Online Feature Plane (OFP)
* Identity & Entity Graph (IEG)
* Model serving / Decision Fabric runtime
* Event Bus consumption lag (and optionally IG/ingestion lag indicators)

DL does not compute features, and it does not decide fraud outcomes. It constrains what Decision Fabric is allowed to do.

---

### 1.3 What DL is system-of-record for (and what it is not)

DL is authoritative for:

* the **chosen degrade_mode**
* the **capabilities mask** (what is allowed/disallowed in that mode)
* the **provenance** explaining why the mode was chosen (which signals triggered it)

DL is not authoritative for:

* event validity (IG)
* stream durability/ordering (EB)
* identity truth (IEG)
* feature values (OFP)
* final decisions/actions (Decision Fabric/Actions)

---

### 1.4 Why explicitness matters

Without DL, “degrade behaviour” becomes implicit and inconsistent:

* services silently drop optional calls,
* consumers guess whether to proceed,
* audits can’t reconstruct why behaviour changed.

DL prevents this by requiring:

* one explicit degrade decision,
* one explicit capabilities mask,
* and mandatory downstream recording.

---

### 1.5 What DL must enable for downstream components

Downstream components must be able to rely on DL for:

* **hard constraints:** a clear mask of what is allowed
* **determinism:** same signals + same policy ⇒ same mode
* **auditability:** Decision Log can reconstruct “what mode we were in and why”
* **stability:** anti-flap posture (hysteresis) prevents mode oscillation

---

## 2) Core invariants (DL “laws”)

> These are **non-negotiable behaviours** for DL v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Explicitness: every downstream decision carries the mode

* Every Decision Fabric decision MUST carry the `degrade_mode` used (and/or a deterministic decision ID referencing it).
* Decision Log MUST record the mode and its provenance for each decision.

### 2.2 Deterministic evaluation

* Given the same signal snapshot + policy table, DL MUST choose the same degrade_mode.
* If multiple triggers apply, DL resolves deterministically (tie-break rule pinned in v0).

### 2.3 Monotonic downshift under pressure

* When health degrades, DL MUST only move **down** the ladder (to equal or more degraded modes), never up.

### 2.4 Hysteresis / anti-flap posture

* Downshift occurs immediately when entry conditions breach.
* Upshift occurs only after a quiet period and only one rung at a time.
* DL must not oscillate rapidly between modes.

### 2.5 Missing/stale signals are treated as unhealthy (v0)

* If a required signal reading is missing or stale, DL treats it as unhealthy and contributes to downshift.

### 2.6 No silent coupling: constraints are declared and must be obeyed

* DL MUST publish a capabilities mask describing what is allowed.
* Decision Fabric MUST treat the mask as hard constraints (no bypass).

### 2.7 Provenance is mandatory

* DL MUST produce a provenance bundle that includes which signals triggered the decision and the thresholds/comparisons used.

### 2.8 Safety default: fail closed at worst

* DL MUST always be able to choose a safe mode.
* If evaluation cannot be completed safely, DL must select the safest mode (`FAIL_CLOSED`) rather than guessing.

---

## 3) Terminology and key objects

> These are the nouns used throughout the DL conceptual design. Exact field shapes live in the v0 contract schema; behavioural meaning is pinned in DL specs.

### 3.1 degrade_mode

The selected ladder state indicating how degraded the system is.

* Ordered v0 modes:

  * `NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`

---

### 3.2 CapabilityMask

A structured set of constraints describing what Decision Fabric is allowed to do under the chosen mode.

Pinned v0 fields:

* `allow_ieg` (bool)
* `allowed_feature_groups[]` (allowlist of group_name)
* `allow_model_primary` (bool)
* `allow_model_stage2` (bool)
* `allow_fallback_heuristics` (bool)
* `action_posture` (enum: `NORMAL` | `STEP_UP_ONLY`)

---

### 3.3 SignalReading

A normalized snapshot reading of a health signal.

Required conceptual fields:

* `signal_name`
* `source_component`
* `observed_value`
* `unit`
* `window` (e.g., rolling 1m/5m)
* `observed_at_utc`

---

### 3.4 Trigger

A specific threshold breach that contributed to the selected mode.

Required conceptual fields:

* `signal_name`
* `observed_value`
* `threshold`
* `comparison` (e.g., `>`, `<`, `>=`)
* `triggered_at_utc`

---

### 3.5 DegradeProvenance

The “why bundle” explaining the decision.

Minimum v0 content:

* `triggers[]` (list of Trigger)
* either:

  * `signals_used[]` (inline list of SignalReading), or
  * `signals_used_ref` (opaque reference to a stored snapshot)
* optional correlation fields (ContextPins or run_id if available)

---

### 3.6 DegradeDecision

The primary output object produced by DL.

Required conceptual fields:

* `mode` (degrade_mode)
* `capabilities_mask` (CapabilityMask)
* `provenance` (DegradeProvenance)
* `decided_at_utc`
* optional `degrade_decision_id` (deterministic hash of decision payload, if enabled)

---

### 3.7 Quiet period

A required duration of stable “healthy enough” signals before DL allows an upshift.

Quiet period duration is config; the posture is pinned.

---

### 3.8 Downshift / upshift

* **Downshift:** move to a more degraded (safer) mode.
* **Upshift:** move to a less degraded mode (only after quiet period; one rung at a time).

---

### 3.9 Missing/stale signal

A signal is **missing** if no reading exists in the evaluation snapshot.
A signal is **stale** if `observed_at_utc` is older than the evaluator’s allowed age window.

Pinned v0 posture: missing/stale treated as unhealthy.

---

## 4) DL as a black box (inputs → outputs)

> This section treats Degrade Ladder as a black box: what it consumes, what it produces, and who relies on it.

### 4.1 Inputs (what DL consumes)

#### 4.1.1 Health signal snapshot (primary input)

DL consumes a snapshot of health signals from loop services, including (v0 minimum set):

* OFP latency/error/lag
* IEG latency/error
* model serving latency/error
* EB consumer lag (for admitted_events consumption)

Signals are treated as windowed readings (rolling snapshot), not instantaneous guesses.

#### 4.1.2 Optional input: requested latency class / SLO tier

If upstream supplies a latency class (e.g., “standard” vs “low-latency”), DL may use it as an additional policy parameter. This is optional in v0; policy remains deterministic.

---

### 4.2 Outputs (what DL produces)

#### 4.2.1 DegradeDecision (authoritative output)

DL outputs one object:

* `DegradeDecision { mode, capabilities_mask, provenance, decided_at_utc }`

This is the single authoritative statement of “what is allowed now.”

#### 4.2.2 Optional deterministic decision identifier

DL may also output:

* `degrade_decision_id` (deterministic hash of the decision payload)

This supports compact recording in logs if desired.

---

### 4.3 Boundary map (who consumes DL)

#### 4.3.1 Decision Fabric (hard consumer)

* Must consume and obey DL constraints.
* Must record degrade_mode (and decision id / provenance linkage) in decision provenance.

#### 4.3.2 Decision Log & Audit Store (recording consumer)

* Records degrade decisions used by each decision so explainability is reconstructible.

#### 4.3.3 Optional consumers

* OFP may optionally read mode for internal posture (but OFP v0’s stale/serve policy is already pinned).
* Observability tools may consume DL outputs to show time-in-mode and trigger histories.

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for DL v0. These decisions are treated as fixed direction for DL specs and the v0 contract schema.

### 5.1 Mode vocabulary and ordering (v0)

Pinned ordered modes:

1. `NORMAL`
2. `DEGRADED_1`
3. `DEGRADED_2`
4. `FAIL_CLOSED`

The ordering is strict: higher index = more degraded/safer posture.

---

### 5.2 CapabilityMask fields (v0)

Pinned fields in v0 CapabilityMask:

* `allow_ieg` (bool)
* `allowed_feature_groups[]` (allowlist of FeatureGroup group_name)
* `allow_model_primary` (bool)
* `allow_model_stage2` (bool)
* `allow_fallback_heuristics` (bool)
* `action_posture` (`NORMAL` | `STEP_UP_ONLY`)

Decision Fabric must treat these as hard constraints.

---

### 5.3 Mode → capabilities mapping table (v0)

Pinned mapping:

#### `NORMAL`

* `allow_ieg=true`
* `allowed_feature_groups=["*"]` (all groups)
* `allow_model_primary=true`
* `allow_model_stage2=true`
* `allow_fallback_heuristics=true`
* `action_posture=NORMAL`

#### `DEGRADED_1`

* `allow_ieg=false`
* `allowed_feature_groups=[<small allowlist>]` *(final allowlist comes from OFP registry; placeholder in v0)*
* `allow_model_primary=true`
* `allow_model_stage2=false`
* `allow_fallback_heuristics=true`
* `action_posture=NORMAL`

#### `DEGRADED_2`

* `allow_ieg=false`
* `allowed_feature_groups=[]`
* `allow_model_primary=true` *(guardrails/simple scoring allowed)*
* `allow_model_stage2=false`
* `allow_fallback_heuristics=true`
* `action_posture=STEP_UP_ONLY`

#### `FAIL_CLOSED`

* `allow_ieg=false`
* `allowed_feature_groups=[]`
* `allow_model_primary=false`
* `allow_model_stage2=false`
* `allow_fallback_heuristics=false`
* `action_posture=STEP_UP_ONLY`

---

### 5.4 Signal set (named signals + sources) (v0)

Pinned v0 signal names:

**OFP**

* `ofp_p95_latency_ms`
* `ofp_error_rate`
* `ofp_update_lag_seconds`

**IEG**

* `ieg_p95_latency_ms`
* `ieg_error_rate`

**Model serving**

* `model_p95_latency_ms`
* `model_error_rate`

**EB**

* `eb_consumer_lag_seconds`

Each reading must carry source_component, unit, window, observed_at_utc.

---

### 5.5 Missing/stale signals posture (v0)

* Missing or stale signals are treated as unhealthy.
* This can trigger downshift.

---

### 5.6 Deterministic evaluation and tie-break (v0)

* Given the same signal snapshot + policy table → same chosen mode.
* Tie-break rule: choose the **most degraded** mode whose entry conditions are met.

---

### 5.7 Hysteresis posture (v0)

* **Downshift:** immediate when entry conditions breach.
* **Upshift:** only after quiet period, **one rung at a time**:

  * `FAIL_CLOSED → DEGRADED_2 → DEGRADED_1 → NORMAL`

Quiet period duration is config, but posture is pinned.

---

### 5.8 Output boundary object (v0)

Pinned output object:

* `DegradeDecision { mode, capabilities_mask, provenance, decided_at_utc }`

Pinned provenance minimum:

* `triggers[]` including observed_value and threshold and comparison
* signals_used snapshot included inline or by ref (shape pinned in schema)

Optional:

* deterministic `degrade_decision_id` (hash of decision payload)

---

### 5.9 Downstream obligations (v0)

* Decision Fabric MUST obey CapabilityMask constraints.
* Decision Fabric MUST record degrade_mode (and decision linkage) in decision provenance.
* Decision Log MUST persist DL decision used for each decision event.

---

## 6) Modular breakdown (Level 1) and what each module must answer

> DL is a **control-plane policy selector**. The modular breakdown exists to force DL’s semantics (signal inputs, deterministic evaluation, hysteresis, capability constraints, provenance) to be answered *somewhere*, while leaving telemetry plumbing and deployment mechanics to the implementer.

### 6.0 Module map (one screen)

DL is decomposed into 5 conceptual modules:

1. **Signal Ingest & Normalization**
2. **Threshold/Policy Table (“the ladder”)**
3. **Mode Evaluator**
4. **Capabilities/Constraints Publisher**
5. **Audit/Provenance Recorder**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Signal Ingest & Normalization

### Purpose

Collect health signals from dependencies and normalize them into stable SignalReadings for evaluation.

### What it owns

* the v0 signal list and their source_components
* normalization posture (unit consistency, window labeling, staleness detection)
* missing/stale signal classification (pinned unhealthy posture)

### Questions this module must answer

* What signal readings are required in v0, and from which components?
* What time-window labels apply (rolling 1m/5m snapshot concept)?
* How is staleness detected (observed_at age threshold concept)?
* How are units normalized (ms, seconds, rate)?
* What happens when a signal cannot be collected (missing → unhealthy)?

### Can be left to the implementer

* metrics collection method (scrape vs push)
* signal aggregation implementation (p95 vs p99 plumbing)
* buffering and sampling frequency

### Local vs deployed operation

* **Local:** may be mocked or sampled; semantics unchanged
* **Deployed:** uses real metrics; semantics unchanged

---

## 6.2 Module 2 — Threshold/Policy Table (“the ladder”)

### Purpose

Define the ordered ladder of modes and the entry/exit conditions for each.

### What it owns

* mode vocabulary and ordering (pinned)
* capability mapping table (pinned)
* threshold condition shapes (config-driven numbers)

### Questions this module must answer

* What modes exist and what is their ordering?
* What capability profile applies to each mode?
* What thresholds define entry into each degraded mode?
* What conditions permit upshift (quiet period posture; one rung at a time)?
* How are policy tables versioned/configured (conceptually)?

### Can be left to the implementer

* storage of policy table (config file, service config, feature flags)
* exact threshold numbers (config)
* policy rollout mechanics

### Local vs deployed operation

* identical semantics; deployed may have configuration management

---

## 6.3 Module 3 — Mode Evaluator

### Purpose

Apply the policy table to the current signal snapshot deterministically and select the mode.

### What it owns

* deterministic evaluation rule
* tie-break rule (most degraded satisfied)
* hysteresis enforcement logic (downshift immediate; upshift gated)

### Questions this module must answer

* Given signals + policy, how is mode selected deterministically?
* If multiple triggers fire, what is the tie-break?
* How does hysteresis affect mode transitions over time?
* What happens if evaluation cannot be completed safely (FAIL_CLOSED)?

### Can be left to the implementer

* evaluation frequency (per request vs periodic), as long as outputs are timestamped and consistent
* internal state for quiet period tracking

### Local vs deployed operation

* local may evaluate on-demand; deployed may evaluate periodically; semantics unchanged

---

## 6.4 Module 4 — Capabilities/Constraints Publisher

### Purpose

Publish the chosen constraints as an authoritative mask that Decision Fabric must obey.

### What it owns

* CapabilityMask shape and fields (pinned)
* mode→capabilities mapping (pinned)
* delivery of the mask to consumers (conceptual)

### Questions this module must answer

* What exact constraints are expressed in CapabilityMask?
* How does each mode map to a capabilities profile?
* How do consumers obtain the current decision (inline per request vs cached)?

### Can be left to the implementer

* how the decision is delivered (embedded in Decision Fabric vs separate service endpoint)
* caching strategy

### Local vs deployed operation

* semantics identical; deployed may have stronger distribution needs

---

## 6.5 Module 5 — Audit/Provenance Recorder

### Purpose

Record “why” DL chose a mode and make it joinable in decision logs.

### What it owns

* provenance minimum fields (pinned)
* trigger construction rules
* optional degrade_decision_id computation

### Questions this module must answer

* What triggers must be recorded (signal, observed value, threshold, comparison)?
* What timestamping is used (decided_at_utc)?
* What correlation keys are included (optional run_id/ContextPins)?
* How is degrade_decision_id derived if enabled (deterministic hash)?

### Can be left to the implementer

* persistence backend for DL history (if any)
* whether signals_used are stored inline or by ref (both allowed)

### Local vs deployed operation

* local can log to console/file; deployed should integrate with observability/logging; semantics unchanged

---

## 6.6 Cross-module pinned items (summary)

Across all modules, DL must ensure:

* explicit degrade_mode and capabilities mask are produced
* deterministic evaluation and tie-break
* monotonic downshift and hysteresis posture
* missing/stale signals treated as unhealthy
* provenance includes triggers and timestamp
* Decision Fabric obeys constraints and records mode in decision provenance

---

## 7) Signals model (v0)

> This section pins the v0 signal vocabulary and how signals are represented for deterministic evaluation. It is intentionally thin: plumbing and metric collection are implementation freedom, but signal names and semantics are not.

### 7.1 SignalReading shape (pinned fields)

Every signal used by DL is represented as a `SignalReading` containing:

* `signal_name` (stable identifier)
* `source_component` (OFP / IEG / MODEL / EB)
* `observed_value` (number)
* `unit` (e.g., `ms`, `seconds`, `ratio`)
* `window` (e.g., `rolling_1m`, `rolling_5m`)
* `observed_at_utc` (timestamp)

DL evaluates a snapshot of such readings.

---

### 7.2 v0 signal vocabulary (pinned)

Pinned v0 signal names and sources:

**Online Feature Plane (OFP)**

* `ofp_p95_latency_ms`
* `ofp_error_rate`
* `ofp_update_lag_seconds`

**Identity & Entity Graph (IEG)**

* `ieg_p95_latency_ms`
* `ieg_error_rate`

**Model serving / Decision Fabric runtime**

* `model_p95_latency_ms`
* `model_error_rate`

**Event Bus consumption**

* `eb_consumer_lag_seconds`

The signal names are stable interface-level concepts, regardless of how they are measured.

---

### 7.3 Windowing posture (v0)

Signals are evaluated as **windowed snapshots**:

* each reading carries a `window` label
* DL policy table thresholds apply to specific windows (e.g., p95 over rolling_1m)

Exact window durations and metric aggregation mechanics are config/plumbing; DL only requires stable naming and window labeling.

---

### 7.4 Staleness detection (pinned posture)

DL treats missing or stale readings as unhealthy.

* A reading is **stale** if:

  * `now_utc - observed_at_utc` exceeds an allowed max age
* The max allowed age is config, but the rule that stale ⇒ unhealthy is pinned.

---

### 7.5 Normalization posture (v0)

DL normalizes readings for evaluation:

* units must match the signal’s expected unit
* missing unit or inconsistent unit is treated as invalid/missing → unhealthy

Normalization steps are implementation freedom, but the outcome classification must be deterministic.

---

### 7.6 Missing readings (pinned posture)

If a required signal is missing from the snapshot:

* DL treats it as unhealthy and downshifts accordingly.

---

## 8) Policy evaluation semantics (v0)

> This section pins how DL evaluates signals deterministically into a mode, without hardcoding threshold numbers in the spec.

### 8.1 Policy table structure (conceptual)

DL uses a policy table containing:

* ordered modes (v0 ladder)
* entry conditions per mode (threshold rules over named signals)
* exit conditions per mode (hysteresis posture; quiet period gating)

Threshold numeric values are config; evaluation semantics are pinned.

---

### 8.2 Entry condition evaluation (v0)

* DL evaluates entry conditions against the current signal snapshot.
* A mode is considered “eligible” if its entry conditions are met.

Pinned posture:

* downshift occurs when a more degraded mode becomes eligible.

---

### 8.3 Deterministic tie-break (pinned)

If multiple modes’ entry conditions are met simultaneously:

* DL selects the **most degraded** eligible mode.

This guarantees deterministic selection under multiple triggers.

---

### 8.4 Trigger construction (provenance rule)

For every breached threshold that contributes to the selected mode, DL records a Trigger containing:

* signal_name
* observed_value
* threshold
* comparison
* triggered_at_utc

Triggers must be sufficient for audit (“why did we downshift?”).

---

### 8.5 Default safe behavior (pinned)

If DL cannot evaluate safely (e.g., policy missing, evaluation error):

* DL outputs `FAIL_CLOSED` with a provenance reason indicating evaluation failure.

DL never returns “unknown mode”.

---

### 8.6 Mode transition constraints (interaction with hysteresis)

* Entry conditions may cause immediate downshift.
* Upshift is governed by hysteresis rules (quiet period; one rung at a time) in §9.

---

### 8.7 Missing/stale signals in evaluation

Missing/stale signals are treated as unhealthy:

* they can satisfy “bad health” conditions
* they cannot be used as evidence of health for upshift

This prevents mode oscillation due to incomplete telemetry.

---

## 9) Hysteresis, missing signals, and stability (v0)

> This section pins the v0 anti-flap posture. The goal is: **downshift fast**, **upshift cautiously**, and never oscillate due to noise.

### 9.1 Downshift rule (pinned)

* DL downshifts **immediately** when entry conditions for a more degraded mode are met.
* Downshift is monotonic (cannot jump upward while conditions are degraded).

---

### 9.2 Upshift rule (pinned)

Upshift is allowed only under these v0 constraints:

* requires a **quiet period** where signals remain healthy enough for the less degraded mode
* upshift occurs **one rung at a time**:

  * `FAIL_CLOSED → DEGRADED_2 → DEGRADED_1 → NORMAL`

Quiet period duration is config; the posture is pinned.

---

### 9.3 Quiet period definition (conceptual)

* Quiet period is measured from the last time any downshift trigger fired.
* Quiet period is reset if any downshift-eligible condition occurs during the period.

The exact time value is config; the reset rule is pinned.

---

### 9.4 Missing/stale signals (pinned)

* Missing or stale signals are treated as unhealthy.
* Therefore:

  * missing/stale signals can trigger downshift,
  * and they prevent upshift (quiet period cannot be satisfied if required signals are missing/stale).

---

### 9.5 Minimal stability posture (optional but compatible with v0)

DL may optionally enforce a minimum “time-in-mode” before allowing any upshift.
This can be config-driven and is not required if quiet-period rule exists, but is compatible.

---

### 9.6 Flapping prevention outcome

These rules ensure:

* DL never oscillates rapidly between modes due to noisy signals
* the system degrades quickly and recovers slowly and predictably

---

## 10) Output contract (DegradeDecision) and downstream obligations

> This section pins the DL output object and the non-negotiable obligations for consumers (Decision Fabric and Decision Log).

### 10.1 DegradeDecision (pinned output object)

DL outputs a single object:

`DegradeDecision { mode, capabilities_mask, provenance, decided_at_utc }`

Optional:

* `degrade_decision_id` (deterministic hash of decision payload)

This object is the authoritative statement of “what is allowed now.”

---

### 10.2 CapabilityMask (hard constraints)

Decision Fabric MUST treat the CapabilityMask as hard constraints:

* if `allow_ieg=false`, Decision Fabric must not call IEG
* if `allowed_feature_groups` excludes a group, Decision Fabric must not request/consume it
* if `allow_model_stage2=false`, Decision Fabric must not execute stage2
* if `allow_model_primary=false`, Decision Fabric must not run primary model inference
* if `allow_fallback_heuristics=false`, Decision Fabric must not substitute heuristics
* `action_posture=STEP_UP_ONLY` means Decision Fabric must not issue “approve/allow” actions; only step-up / hold / deny postures are permitted per your platform action semantics

---

### 10.3 Provenance requirements (pinned)

DegradeDecision provenance must include:

* `triggers[]` describing which thresholds were breached
* either:

  * `signals_used[]` inline snapshot, or
  * `signals_used_ref` pointing to a stored signal snapshot

Minimum trigger fields:

* signal_name
* observed_value
* threshold
* comparison
* triggered_at_utc

Provenance must be sufficient for audit reconstruction.

---

### 10.4 Decision Fabric obligations (pinned)

Decision Fabric MUST:

* consume the current DegradeDecision (per request or cached; implementation choice)
* obey the CapabilityMask
* record in decision provenance, at minimum:

  * `degrade_mode`
  * and either `degrade_decision_id` or the full DegradeDecision object reference/hash

Decision Fabric must not “improve” on DL’s meaning.

---

### 10.5 Decision Log obligations (pinned)

Decision Log MUST persist:

* the degrade_mode used for each decision
* sufficient linkage to the DegradeDecision provenance (full object or decision_id + reference)
* the capability mask (or hash) used at the time

This enables later reconstruction of behavior under degraded operation.

---

### 10.6 Error posture for DL output

DL must always be able to output a mode. If DL cannot evaluate safely:

* output `FAIL_CLOSED` with provenance indicating evaluation failure (not a missing/empty object).

---

## 11) Contracts philosophy and contract pack overview (v0)

> DL contracts exist to pin the **mode / mask / provenance boundary objects** in a machine-checkable way. Contracts define shape; DL specs define behavior (evaluation, hysteresis, tie-break).

### 11.1 v0 contract strategy (one schema file)

DL v0 ships **one** schema file:

* `contracts/dl_public_contracts_v0.schema.json`

This keeps the repo surface small while still enforcing interoperability with Decision Fabric and Decision Log.

---

### 11.2 Validation targeting rule (self-describing)

All DL contract objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

### 11.3 `$defs` inventory (v0)

`dl_public_contracts_v0.schema.json` contains `$defs` for:

* `DegradeMode` (enum: NORMAL, DEGRADED_1, DEGRADED_2, FAIL_CLOSED)
* `ActionPosture` (enum: NORMAL, STEP_UP_ONLY)
* `CapabilityMask`
* `SignalReading`
* `Trigger`
* `DegradeProvenance`
* `DegradeDecision`
* optional `ErrorResponse` (thin; rarely needed because FAIL_CLOSED is the safe default)

---

### 11.4 What contracts cover vs what specs cover

#### Contracts cover (shape/structure)

* required fields and types for:

  * mode
  * capability mask fields
  * signal readings and triggers
  * provenance bundle shape
  * decided_at_utc and optional decision_id field
* stable enums (mode names, action_posture)
* deterministic nesting and ordering expectations (if any lists are required)

#### Specs cover (behavior/invariants)

* signal staleness rules and “missing treated unhealthy” posture
* evaluation determinism and tie-break (most degraded eligible)
* hysteresis rules (downshift immediate; upshift quiet period; one rung)
* default safe behavior (FAIL_CLOSED on evaluation failure)
* downstream obligations (obey + record)

---

### 11.5 Relationship to Canonical Event Contract Pack

DL’s DegradeDecision will eventually be represented in the Canonical Event Contract Pack as:

* either an embedded object inside decision provenance, or
* a dedicated event type (e.g., `degrade_decision_made`)

But DL v0 keeps its schema self-contained to avoid premature coupling. Later, Canonical Event contracts can reference DL’s shapes.

---

## 12) Addressing, naming, and discoverability (conceptual)

> This section defines how DL decisions are referenced and how “current mode” is obtained without guessing. It stays conceptual because storage/transport is implementation freedom in v0.

### 12.1 Design goals

DL discoverability must support:

* **auditability:** Decision Log can reconstruct which mode/mask was used and why
* **deterministic referencing:** the same decision snapshot has a stable identity (optional decision_id)
* **environment independence:** local vs deployed differs in mechanics, not meaning

---

### 12.2 DegradeDecision identity

In v0, DL outputs:

* DegradeDecision object containing mode/mask/provenance and decided_at_utc.

Optionally, DL may include:

* `degrade_decision_id` (deterministic hash of the decision payload)

If included, decision_id can be used as a compact reference in Decision Log.

---

### 12.3 How consumers obtain “current mode”

DL may be consumed in one of two conceptual patterns (implementation freedom):

1. **Inline/per-request evaluation**

* DL evaluates per request and returns a DegradeDecision for that request time.

2. **Periodic evaluation with caching**

* DL evaluates periodically and publishes “current mode” which Decision Fabric reads/caches.

Pinned requirement:

* whichever pattern is used, Decision Fabric must record the DegradeDecision (or linkage) it actually used for that decision.

---

### 12.4 Provenance discoverability

Provenance is carried inline inside DegradeDecision:

* triggers list (threshold breaches)
* signals_used snapshot inline OR by-ref

If signals_used is by-ref, `signals_used_ref` must be resolvable by operators with access.

---

### 12.5 Local vs deployed discoverability

* **Local:** signals may be mocked; DegradeDecision can still be emitted and recorded.
* **Deployed:** signals come from monitoring pipelines; decisions may be stored in logs/DB.

Pinned rule:

* semantics of mode selection, mask meaning, and provenance fields must remain identical.

---

## 13) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for Degrade Ladder docs and contracts. The goal is a **single, deep reading surface** for DL design, plus a **minimal v0 contract**.

### 13.1 Target location in repo

Conceptually, DL lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/degrade_ladder/`

This folder should be self-contained: a new contributor should understand DL by starting here.

---

### 13.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ degrade_ladder/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ DL1_charter_and_boundaries.md
         │  ├─ DL2_modes_and_capabilities_mask.md
         │  ├─ DL3_signals_and_policy_evaluation.md
         │  ├─ DL4_hysteresis_missing_signals_stability.md
         │  └─ DL5_output_contract_ops_acceptance.md
         │
         └─ contracts/
            └─ dl_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; DL v0 needs only **one** schema file.

---

### 13.3 What each file is for (intent)

#### `README.md`

* Entry point: what DL is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (designer-locked v0 intent)
  * `specs/` reading order (DL1–DL5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This stitched conceptual design document:

  * DL purpose in platform
  * DL laws (determinism, monotonic downshift, hysteresis, missing-signal posture)
  * designer-locked v0 decisions (modes, mask, signals)
  * modular breakdown + questions per module
  * contract pack overview (v0)
  * discoverability concepts (decision_id optional)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behavior/invariants
  * contract schema defines boundary shapes
* Non-negotiables:

  * mode ladder and ordering
  * capability mask mapping per mode
  * missing/stale treated as unhealthy
  * deterministic tie-break (most degraded eligible)
  * hysteresis posture (downshift immediate; upshift quiet period; one rung)
  * provenance always present
  * Decision Fabric obeys and records

#### `specs/`

* DL1–DL5 are the eventual binding-ish DL design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `dl_public_contracts_v0.schema.json` pins DegradeDecision boundary objects.

---

### 13.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (designer-locked intent)
3. `specs/DL1_...` → `specs/DL5_...` (behavior/invariants)
4. `contracts/dl_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

### 13.5 Allowed variations (without changing intent)

* Merge `CONCEPTUAL.md` into `README.md`.
* Merge DL1–DL5 into fewer docs once stable.
* Add `contracts/README.md` only if you need a brief note on validation targeting.
* Avoid separate `examples/`, `diagrams/`, `decisions/` folders under deadline.

---

## 14) What the eventual spec docs must capture (mapping from this concept doc)

> This section bridges the DL conceptual design into the **actual DL spec docs** (DL1–DL5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 14.0 Mapping rule (how to use this section)

For every DL “law” and designer-locked decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in DL1–DL5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 14.1 DL1 — Charter & boundaries

### DL1 must capture

* DL purpose as a **control-plane safe-posture selector**
* authority boundaries:

  * authoritative for mode + mask + provenance
  * not feature computation, not decisioning
* DL laws in enforceable prose:

  * explicitness (mode recorded in every decision)
  * deterministic evaluation and tie-break
  * monotonic downshift
  * hysteresis posture
  * missing/stale treated unhealthy
  * fail-closed default
* v0 non-goals:

  * not a metrics system; it consumes signals
  * not an exactly-once system; it is deterministic given snapshot

### DL1 may leave to the implementer

* deployment (inside Decision Fabric vs separate service)
* signal collection wiring

---

## 14.2 DL2 — Modes & capability mask

### DL2 must capture

* pinned mode enum list + ordering
* pinned CapabilityMask fields
* pinned mapping table: `mode -> capability profile`
* consumer obligations:

  * Decision Fabric must obey constraints
  * capability mask is hard constraint layer

### DL2 may leave to the implementer

* how mask is enforced internally in Decision Fabric

---

## 14.3 DL3 — Signals & policy evaluation

### DL3 must capture

* pinned v0 signal list and sources
* SignalReading shape requirements (unit/window/observed_at)
* policy table posture:

  * thresholds are config-driven numbers
  * evaluation semantics are pinned
* deterministic tie-break: most degraded eligible
* trigger construction rules for provenance

### DL3 may leave to the implementer

* metric aggregation plumbing (p95 collection)
* signal sampling frequency

---

## 14.4 DL4 — Hysteresis, missing signals, stability

### DL4 must capture

* downshift immediate
* upshift after quiet period
* upshift one rung at a time
* quiet period reset rule
* missing/stale signals treated unhealthy and prevent upshift
* optional time-in-mode minimum (if used)

### DL4 may leave to the implementer

* exact quiet period duration (config)
* internal state tracking for hysteresis

---

## 14.5 DL5 — Output contract, ops & acceptance

### DL5 must capture

* DegradeDecision boundary semantics
* provenance minimum fields (triggers + timestamp)
* optional deterministic degrade_decision_id posture
* downstream recording rules (Decision Fabric + Decision Log)
* observability minimums:

  * mode distribution, trigger counts, time-in-mode
* acceptance scenarios (tests-as-intent)

### DL5 may leave to the implementer

* persistence backend for DL history (if any)
* dashboards/alerts tooling

---

## 14.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* DegradeMode enum (v0)
* ActionPosture enum (v0)
* CapabilityMask fields
* SignalReading, Trigger, DegradeProvenance, DegradeDecision
* decided_at_utc field
* validation targeting (`kind`, `contract_version`)

### Specs must include

* evaluation behavior:

  * tie-break rule
  * hysteresis posture
  * missing/stale treated unhealthy
  * fail-closed default
* consumer obligations (obey + record)
* mode → capability meaning table (can be mirrored in schema too as documentation)

---

## 14.7 Minimal completeness standard (so DL is implementable)

DL is “spec-ready” when DL1–DL5 collectively pin:

* mode ladder and capability mask mapping
* signal list and staleness posture
* deterministic evaluation + tie-break
* hysteresis rules
* output/provenance shape and downstream obligations
* acceptance scenarios that cover downshift/upshift/missing signals

Everything else can remain implementer freedom.

---

## 15) Acceptance questions and Definition of Done

> This section is the conceptual **ship checklist** for DL v0: the questions DL must answer and the minimal behavioural scenarios that indicate DL is correct enough to implement and integrate.

### 15.1 Acceptance questions (DL must answer these unambiguously)

1. **What mode are we in right now?**

* Does DL always output a single degrade_mode and capability mask?

2. **Why did DL choose this mode?**

* Does provenance include triggers (signal, observed value, threshold, comparison)?

3. **Is mode selection deterministic?**

* Same signal snapshot + same policy ⇒ same mode?

4. **Is downshift monotonic?**

* When health worsens, does DL only move down the ladder?

5. **Is upshift controlled (anti-flap)?**

* Does DL require a quiet period and step up one rung at a time?

6. **What happens if signals are missing or stale?**

* Are missing/stale treated as unhealthy, triggering downshift and blocking upshift?

7. **Do downstream components obey the constraints?**

* Does Decision Fabric treat CapabilityMask as hard constraints?

8. **Is the decision recordable/auditable?**

* Is DegradeDecision recorded in decision provenance and in Decision Log?

9. **What happens if DL can’t evaluate safely?**

* Does it fail closed (FAIL_CLOSED) with provenance indicating evaluation failure?

---

### 15.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Deterministic selection

**Given**

* an identical signal snapshot and policy table

**Expect**

* identical degrade_mode
* identical capabilities_mask
* identical triggers selected (ordering deterministic if listed)

---

#### DoD-2: Monotonic downshift under pressure

**Given**

* DL is in NORMAL and a degraded threshold breaches

**Expect**

* DL downshifts to the appropriate degraded mode (or worse)
* DL does not upshift while degraded conditions remain

---

#### DoD-3: Tie-break selects most degraded eligible

**Given**

* entry conditions for multiple degraded modes are met simultaneously

**Expect**

* DL selects the **most degraded** eligible mode

---

#### DoD-4: Missing signal causes downshift

**Given**

* a required signal is missing or stale

**Expect**

* DL treats it as unhealthy and downshifts appropriately
* provenance indicates missing/stale reason (as a trigger or evaluation note)

---

#### DoD-5: Upshift requires quiet period and steps one rung

**Given**

* DL is in DEGRADED_2 and all signals remain healthy for the quiet period

**Expect**

* DL upshifts to DEGRADED_1 (not directly to NORMAL)
* further upshifts require additional quiet periods

---

#### DoD-6: FAIL_CLOSED on evaluation failure

**Given**

* DL cannot evaluate (policy missing, internal error)

**Expect**

* DL outputs FAIL_CLOSED
* provenance indicates evaluation failure cause

---

#### DoD-7: Decision Fabric obeys CapabilityMask

**Given**

* DL outputs DEGRADED_1 with allow_ieg=false and restricted feature groups

**Expect**

* Decision Fabric does not call IEG
* Decision Fabric requests only allowed_feature_groups
* Decision provenance records degrade_mode used

---

#### DoD-8: Audit record exists for decisions

**Given**

* a real-time decision is produced while DL is degraded

**Expect**

* Decision Log record includes:

  * degrade_mode
  * capabilities mask (or hash)
  * provenance linkage (full object or decision_id/ref)

---

### 15.3 Minimal deliverables required to claim “DoD satisfied”

To claim DL meets DoD at v0 conceptual level, you should be able to show:

* a DegradeDecision example for each v0 mode
* a trigger/provenance example demonstrating threshold breach recording
* a missing-signal downshift example
* an upshift-after-quiet-period example
* a FAIL_CLOSED example (evaluation failure)
* evidence that Decision Fabric recorded and obeyed the mask in at least one decision record

---

## 16) Open decisions log (v0 residuals only)

> These are the only remaining decisions for DL v0 that are not already designer-locked. Everything else is pinned above or is implementation freedom.

### DEC-DL-001 — Threshold numeric values per signal per mode

* **Question:** what are the numeric thresholds for each signal that trigger entry into each mode?
* **Status:** OPEN (v0 residual)
* **Close in:** DL3 (policy table) as config values
* **Constraint:** keep numbers out of JSON Schema; store as configuration with versioning.

### DEC-DL-002 — Quiet period duration

* **Question:** what is the quiet period duration required before upshift?
* **Status:** OPEN (v0 residual)
* **Close in:** DL4 as config value
* **Constraint:** posture is pinned; duration is config.

### DEC-DL-003 — Evaluation frequency posture

* **Question:** is DL evaluated per request or on a periodic schedule (with caching)?
* **Status:** OPEN (v0 residual)
* **Close in:** DL5 (ops) as an implementation/config posture
* **Constraint:** whichever is used, DegradeDecision must be recorded with decided_at_utc and obey hysteresis.

### DEC-DL-004 — Decision identifier requirement

* **Question:** is `degrade_decision_id` required in v0 or optional?
* **Status:** OPEN (v0 residual)
* **Close in:** DL5 + contracts
* **Constraint:** if present, it must be deterministic (hash of decision payload).

### DEC-DL-005 — Inline signals_used vs by-ref signals_used_ref

* **Question:** does provenance embed `signals_used[]` inline or provide a `signals_used_ref`?
* **Status:** OPEN (v0 residual)
* **Close in:** DL5 + contracts
* **Constraint:** provenance must be auditable; either approach is acceptable if resolvable.

### DEC-DL-006 — CapabilityMask allowlist finalization for DEGRADED_1

* **Question:** which exact OFP feature groups are allowed in `DEGRADED_1`?
* **Status:** OPEN (v0 residual)
* **Close in:** DL2 after OFP group registry v0 is finalized
* **Constraint:** allowlist is by group_name; must remain stable and recorded in mask.

### DEC-DL-007 — Error code vocabulary beyond FAIL_CLOSED

* **Question:** do we need additional error codes (e.g., POLICY_MISSING) or is FAIL_CLOSED always sufficient?
* **Status:** OPEN (v0 residual)
* **Close in:** DL5
* **Constraint:** safe default remains FAIL_CLOSED; error codes are for ops clarity only.

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate DL v0 boundary objects.
> Threshold numbers are placeholders (real values live in config).
> The `allowed_feature_groups` allowlist in DEGRADED_1 uses placeholder group names; it will be finalized after OFP registry v0.

---

### A.1 Example — Signal snapshot (inputs as SignalReadings)

```json
{
  "kind": "signal_snapshot",
  "contract_version": "dl_public_contracts_v0",
  "observed_at_utc": "2026-01-06T10:00:00Z",
  "signals": [
    {
      "signal_name": "ofp_p95_latency_ms",
      "source_component": "OFP",
      "observed_value": 220,
      "unit": "ms",
      "window": "rolling_1m",
      "observed_at_utc": "2026-01-06T10:00:00Z"
    },
    {
      "signal_name": "ieg_error_rate",
      "source_component": "IEG",
      "observed_value": 0.12,
      "unit": "ratio",
      "window": "rolling_5m",
      "observed_at_utc": "2026-01-06T10:00:00Z"
    },
    {
      "signal_name": "eb_consumer_lag_seconds",
      "source_component": "EB",
      "observed_value": 18,
      "unit": "seconds",
      "window": "rolling_1m",
      "observed_at_utc": "2026-01-06T10:00:00Z"
    }
  ]
}
```

---

### A.2 Example — DegradeDecision (NORMAL)

```json
{
  "kind": "degrade_decision",
  "contract_version": "dl_public_contracts_v0",

  "mode": "NORMAL",
  "decided_at_utc": "2026-01-06T10:00:00Z",

  "capabilities_mask": {
    "allow_ieg": true,
    "allowed_feature_groups": ["*"],
    "allow_model_primary": true,
    "allow_model_stage2": true,
    "allow_fallback_heuristics": true,
    "action_posture": "NORMAL"
  },

  "provenance": {
    "triggers": [],
    "signals_used_ref": "signalsnap://2026-01-06T10:00:00Z"
  }
}
```

---

### A.3 Example — DegradeDecision (DEGRADED_1 due to OFP latency)

```json
{
  "kind": "degrade_decision",
  "contract_version": "dl_public_contracts_v0",

  "mode": "DEGRADED_1",
  "decided_at_utc": "2026-01-06T10:01:00Z",

  "capabilities_mask": {
    "allow_ieg": false,
    "allowed_feature_groups": ["txn_velocity"],
    "allow_model_primary": true,
    "allow_model_stage2": false,
    "allow_fallback_heuristics": true,
    "action_posture": "NORMAL"
  },

  "provenance": {
    "triggers": [
      {
        "signal_name": "ofp_p95_latency_ms",
        "observed_value": 450,
        "threshold": 300,
        "comparison": ">",
        "triggered_at_utc": "2026-01-06T10:01:00Z"
      }
    ],
    "signals_used_ref": "signalsnap://2026-01-06T10:01:00Z"
  }
}
```

---

### A.4 Example — DegradeDecision (DEGRADED_2 due to IEG errors)

```json
{
  "kind": "degrade_decision",
  "contract_version": "dl_public_contracts_v0",

  "mode": "DEGRADED_2",
  "decided_at_utc": "2026-01-06T10:02:00Z",

  "capabilities_mask": {
    "allow_ieg": false,
    "allowed_feature_groups": [],
    "allow_model_primary": true,
    "allow_model_stage2": false,
    "allow_fallback_heuristics": true,
    "action_posture": "STEP_UP_ONLY"
  },

  "provenance": {
    "triggers": [
      {
        "signal_name": "ieg_error_rate",
        "observed_value": 0.25,
        "threshold": 0.10,
        "comparison": ">",
        "triggered_at_utc": "2026-01-06T10:02:00Z"
      }
    ],
    "signals_used_ref": "signalsnap://2026-01-06T10:02:00Z"
  }
}
```

---

### A.5 Example — DegradeDecision (FAIL_CLOSED due to missing signals)

```json
{
  "kind": "degrade_decision",
  "contract_version": "dl_public_contracts_v0",

  "mode": "FAIL_CLOSED",
  "decided_at_utc": "2026-01-06T10:03:00Z",

  "capabilities_mask": {
    "allow_ieg": false,
    "allowed_feature_groups": [],
    "allow_model_primary": false,
    "allow_model_stage2": false,
    "allow_fallback_heuristics": false,
    "action_posture": "STEP_UP_ONLY"
  },

  "provenance": {
    "triggers": [
      {
        "signal_name": "ofp_p95_latency_ms",
        "observed_value": null,
        "threshold": null,
        "comparison": "MISSING",
        "triggered_at_utc": "2026-01-06T10:03:00Z"
      }
    ],
    "signals_used_ref": "signalsnap://2026-01-06T10:03:00Z",
    "note": "Missing required signals treated as unhealthy; fail closed."
  }
}
```

---

## Appendix B — ASCII sequences (evaluate, downshift, upshift, record)

> **Legend:**
> `->` command/call `-->` read/pull `=>` write/emit
> DL may run inline or periodically; the semantics below are the same.

---

### B.1 Evaluate → DegradeDecision → Decision Fabric obeys → Decision Log records

```
Participants:
  Metrics/Signals | DL(Signal Ingest) | DL(Evaluator) | DL(Capabilities) | Decision Fabric | Decision Log

Metrics/Signals --> DL(Signal Ingest): SignalReadings snapshot (windowed)
DL(Signal Ingest): normalize + mark missing/stale as unhealthy

DL(Evaluator): apply policy table deterministically
DL(Evaluator): select mode (tie-break = most degraded eligible)
DL(Capabilities): map mode -> CapabilityMask

DL -> Decision Fabric: DegradeDecision(mode, mask, provenance, decided_at)
Decision Fabric: enforce constraints (no bypass)
Decision Fabric: include degrade_mode (and linkage) in decision provenance

Decision Fabric -> Decision Log: DecisionRecord(..., degrade_mode, degrade_decision_ref/obj)
Decision Log: persists mode + provenance linkage
```

---

### B.2 Downshift (immediate) when threshold breaches

```
Current mode: NORMAL

Signals snapshot arrives:
  ofp_p95_latency_ms = 450  (threshold for DEGRADED_1 is 300)

DL(Evaluator): entry conditions for DEGRADED_1 met
DL(Evaluator): downshift immediately to DEGRADED_1
DL: outputs DegradeDecision(DEGRADED_1) with trigger recorded

Next decision:
  Decision Fabric obeys new mask (e.g., allow_ieg=false; stage2 disabled)
```

---

### B.3 Tie-break selects most degraded eligible mode

```
Signals snapshot arrives:
  ieg_error_rate breaches DEGRADED_2 threshold
  model_error_rate breaches FAIL_CLOSED threshold

DL(Evaluator): multiple modes eligible
Tie-break: choose most degraded eligible -> FAIL_CLOSED
DL: outputs DegradeDecision(FAIL_CLOSED) with both triggers recorded
```

---

### B.4 Upshift after quiet period (one rung at a time)

```
Current mode: DEGRADED_2

Signals return to healthy thresholds and remain healthy for quiet period T.
(If any downshift-eligible condition occurs, timer resets.)

After quiet period satisfied:
  DL(Evaluator): upshift one rung -> DEGRADED_1

After another quiet period satisfied:
  DL(Evaluator): upshift one rung -> NORMAL
```

---

### B.5 Missing/stale signals block upshift and can trigger downshift

```
Current mode: DEGRADED_1

Signals snapshot arrives missing ofp_update_lag_seconds (required).
DL: treats missing as unhealthy
DL(Evaluator): cannot consider system healthy -> no upshift permitted
(if missing contributes to degraded entry conditions, downshift may occur)

DL outputs DegradeDecision with trigger "MISSING" recorded
```

---