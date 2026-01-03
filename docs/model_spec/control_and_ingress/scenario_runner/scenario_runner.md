# Scenario Runner (Control & Ingress) - Level-2 Specification

## 0. Front matter (Binding)

### 0.1 Document identity (authoritative)

This file defines the **Scenario Runner** component's **Level-2** specification (binding requirements + informative guidance). It is the authoritative description of Scenario Runner's black-box responsibilities within **Control & Ingress**.

* **Canonical path (authoritative):**
  `docs/model_spec/control_and_ingress/scenario_runner/scenario_runner.md`
* **Component:** Control & Ingress - Scenario Runner
* **Spec class:** Level-2 (Binding + Informative)
* **Status:** DRAFT
* **Effective date:** 2026-01-02
* **Spec version:** v0.1
* **Owner:** Control & Ingress spec owner
* **Review cadence:** per release (or on any breaking contract change)
* **Change log pointer:** git history (or local `CHANGELOG.md` if adopted later)

### 0.2 Companion artefacts in this folder (authoritative)

Scenario Runner's component-owned surfaces are defined in this folder:

* **Contracts (binding):**

  * `contracts/scenario_run_request.schema.yaml`
  * `contracts/scenario_definition.schema.yaml`
  * `contracts/run_facts_view.schema.yaml`
  * `contracts/run_status_event.payload.schema.yaml` *(optional; only if status events are emitted)*
* **Examples (informative):** `examples/*`
* **Diagram (informative):** `diagrams/scenario_runner_flow.ascii.txt`

### 0.3 External authoritative dependencies (must be referenced, not duplicated)

Scenario Runner is a control-plane component and MUST align to these authoritative sources:

#### 0.3.1 Platform Rails (authoritative)

Scenario Runner MUST comply with the platform's cross-cutting rails (identity, envelopes, receipts, PASS/no-read rules):

* **Rails doc:**
  `docs/model_spec/observability_and_governance/cross_cutting_rails/cross_cutting_rails.md`
* **Rails contracts:**
  `docs/model_spec/observability_and_governance/cross_cutting_rails/contracts/`

  * `id_types.schema.yaml`
  * `run_record.schema.yaml` *(Scenario Runner emits Run Records in this shape)*
  * `canonical_event_envelope.schema.yaml` *(only if Scenario Runner emits events)*
  * `ingestion_receipt.schema.yaml` / `hashgate_receipt.schema.yaml` *(only if Runner stores/links these receipts as pins)*

#### 0.3.2 Data Engine Interface Pack (authoritative black-box boundary)

Scenario Runner MUST treat the Data Engine as a black box and MUST use the engine interface pack as the authoritative boundary definition for:

* invocation shape
* output inventory + addressing/discovery
* gate map + PASS proof semantics
* output locator shape

(Scenario Runner MUST NOT import engine segment/state internals.)

At minimum, Scenario Runner depends on:

* `data_engine_interface.md`
* `engine_outputs.catalogue.yaml`
* `engine_gates.map.yaml`
* `contracts/engine_invocation.schema.yaml`
* `contracts/engine_output_locator.schema.yaml`
* `contracts/gate_receipt.schema.yaml`
* `contracts/canonical_event_envelope.schema.yaml` *(engine-native; only if used; otherwise mapping to platform envelope is handled at ingestion)*

### 0.4 Binding scope of this document

The following are **Binding** within this document:

1. Any requirement using **MUST / MUST NOT / SHOULD / SHOULD NOT / MAY**.
2. Any declared **canonical field name** or **contract filename** owned by Scenario Runner.
3. Any explicit statements about **authority boundaries** and **precedence** for dependencies.

Everything explicitly labelled **Informative** (examples, diagrams, illustrative flows) is non-binding.

### 0.5 Referencing rules and stable anchors

* Other component specs MUST reference Scenario Runner requirements via:

  * `docs/model_spec/control_and_ingress/scenario_runner/scenario_runner.md#<section-anchor>`
* Referenced section numbers/headings MUST NOT be renamed or renumbered without a version bump.
* If a requirement is moved, the old anchor MUST be preserved with a "Moved to Section X.Y" stub for at least one MINOR cycle.

### 0.6 Non-authoritative copies

Any copies of this specification outside the canonical path are **informative only** and MUST NOT be treated as binding.

---

## 1. Purpose and scope (Binding)

### 1.1 Purpose

Scenario Runner is a **control-plane** component that **plans, anchors, and publishes discovery** for platform runs.

Its primary purpose is to make runs:

* **identifiable** (stable run identity),
* **pinnable** (explicit references to the world and authoritative inputs),
* **discoverable** (downstream can find "what run is active" without heuristics),
* **auditable** (a run can be replayed/examined from its pinned facts).

Scenario Runner treats the Data Engine as a **black box** and coordinates with it only through the **Data Engine Interface Pack** boundary contracts.

### 1.2 Scope (what Scenario Runner is authoritative for)

This specification is authoritative for:

1. **Run planning boundary**

   * Accepting a tool-agnostic request to plan/create a run (`scenario_run_request`)
   * Validating the request and producing a run plan anchor

2. **Run identity anchoring**

   * Assigning/recording canonical run identity:

     * `scenario_id`, `run_id`, and optional `seed`
   * Binding the run to a world:

     * `parameter_hash`, `manifest_fingerprint`

3. **Run lifecycle state**

   * Defining the run lifecycle states and allowed transitions (PLANNED -> STARTED -> COMPLETED/FAILED/CANCELLED)
   * Recording the run state in a pinnable run record and/or discovery surface

4. **Downstream discovery**

   * Publishing a run discovery surface (`run_facts_view`) that downstream components can use to:

     * discover active run(s),
     * locate pinned engine outputs via output locators,
     * identify required PASS proofs/gate receipts for safe reads/ingest.

5. **Optional status events**

   * If enabled, emitting run status-change events whose payload is defined by this component and whose envelope is defined by platform Rails.

### 1.3 Non-scope (explicit exclusions)

Scenario Runner is **not** authoritative for:

* Data Engine segment/state internals (1A->6B), intermediate artefacts, or algorithms
* Ingestion enforcement and quarantine semantics (owned by Ingestion Gate)
* Event bus topology, messaging infrastructure, or deployment architecture
* Feature engineering, scoring/decisioning logic, label/case logic, or training pipelines
* Performance targets, SLO thresholds, or operational runbooks (except minimum audit/telemetry requirements for this component)

### 1.4 Boundary posture

Scenario Runner MUST:

* comply with platform Rails (identity, immutability, and "no PASS -> no read" semantics where applicable),
* use the Data Engine Interface Pack to form engine invocations and to reason about engine outputs and gates,
* avoid any coupling to engine internals beyond those published boundary artefacts.

Scenario Runner MUST NOT:

* infer outputs by scanning storage for "latest,"
* depend on undocumented engine join keys or internal step ordering,
* treat ungated engine outputs as consumable.

---

## 2. Normative language and precedence (Binding)

### 2.1 Normative keywords

This document uses the following keywords:

* **MUST / MUST NOT**: an absolute requirement.
* **SHOULD / SHOULD NOT**: a strong recommendation; deviation is permitted only with a documented rationale in the component spec artefacts.
* **MAY**: optional behaviour; if implemented, it MUST still comply with all MUST/MUST NOT requirements.

Statements not using these keywords are non-normative unless explicitly labelled Binding.

### 2.2 Binding vs informative content

* Sections explicitly labelled **(Binding)** are binding requirements.
* Sections explicitly labelled **(Informative)** are guidance only.
* Examples and diagrams are **Informative by default**, even if referenced from Binding sections, unless explicitly declared canonical.

### 2.3 Precedence ladder

When multiple specifications apply, precedence is:

1. **Platform Rails** (cross-cutting invariants and canonical interfaces)
2. **Data Engine Interface Pack** (Data Engine black-box boundary artefacts)
3. **Scenario Runner spec** (`scenario_runner.md`) and Scenario Runner-owned contracts in `contracts/`
4. Examples and diagrams in this folder (informative)

If there is a conflict, the higher-precedence source prevails.

### 2.4 No-override rule

Scenario Runner MUST NOT override, weaken, or reinterpret any requirement from Platform Rails or the Data Engine Interface Pack.

Allowed:

* additive fields in Scenario Runner-owned schemas, where they do not contradict authoritative fields/semantics;
* stricter validation on Scenario Runner inputs, where it does not prevent compliant downstream interoperability.

Disallowed:

* renaming or aliasing canonical identity fields (`parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, `seed`);
* redefining the canonical event envelope (Rails-owned);
* redefining engine invocation / locator / gate receipt semantics (engine interface-owned);
* using "best effort" reads of ungated outputs in place of PASS enforcement.

### 2.5 Conflict handling

If Scenario Runner artefacts conflict with a higher-precedence source:

* the conflict MUST be treated as a **spec defect**; and
* Scenario Runner MUST NOT be integrated until the defect is corrected (update Scenario Runner artefacts, or formally revise the higher-precedence source via its governance process).

---

## 3. Reading order (Strict) (Binding)

The following reading order is mandatory for anyone authoring, reviewing, or implementing Scenario Runner.

1. **Platform Rails (authoritative)**

   * `docs/model_spec/observability_and_governance/cross_cutting_rails/cross_cutting_rails.md`
   * `docs/model_spec/observability_and_governance/cross_cutting_rails/contracts/*`

2. **Data Engine Interface Pack (authoritative black-box boundary)**

   * `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
   * `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`
   * `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
   * `docs/model_spec/data-engine/interface_pack/contracts/engine_invocation.schema.yaml`
   * `docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml`
   * `docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml`
   * `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml` *(engine-native; used only if explicitly required; otherwise ingestion defines mapping to the platform envelope)*

3. **Scenario Runner spec (this document)**

   * `docs/model_spec/control_and_ingress/scenario_runner/scenario_runner.md`

4. **Scenario Runner contracts (binding)**

   * `docs/model_spec/control_and_ingress/scenario_runner/contracts/README.md`
   * `docs/model_spec/control_and_ingress/scenario_runner/contracts/*`

5. **Examples and diagrams (informative)**

   * `docs/model_spec/control_and_ingress/scenario_runner/examples/*`
   * `docs/model_spec/control_and_ingress/scenario_runner/diagrams/*`

---

## 4. Component responsibilities and non-goals (Binding)

### 4.1 Responsibilities (Binding)

Scenario Runner MUST provide the following capabilities as a control-plane component:

1. **Accept and validate run requests**

   * Accept a `scenario_run_request` as the caller-facing boundary request.
   * Validate required identity and scenario binding fields before any downstream action.
   * Refuse requests that are missing canonical identity inputs (world/run identity) or that are internally inconsistent.

2. **Assign and anchor run identity**

   * Assign (or accept, if provided) a unique `run_id` for each run.
   * Ensure a `scenario_id` is defined for the run context (including baseline/no-overlay runs), and ensure `seed` is captured when stochasticity is required for replay.
   * Treat identity tuple fields as immutable once recorded.

3. **Bind the run to a world**

   * Bind each run to the world identity tuple (`parameter_hash`, `manifest_fingerprint`) provided or selected.
   * Ensure the world identity binding is recorded on all Scenario Runner outputs (run record, run facts, optional events).

4. **Form engine invocations via the black-box interface**

   * Construct Data Engine invocation requests using the **engine invocation contract** only (no segment/state internals).
   * Translate Scenario Runner scenario intent into the engine's `scenario_binding`:

     * baseline/no-overlay runs -> `scenario_binding.mode = "none"`
     * single-scenario runs -> `scenario_binding.scenario_id`
     * multi-scenario runs -> `scenario_binding.scenario_set`
   * Provide correlation/idempotency metadata when available (e.g., `request_id`, `invoker`, notes).

5. **Publish the run anchor (Run Record)**

   * Emit a Run Record as a run-scoped authority surface conforming to the platform Rails `run_record` contract.
   * Record lifecycle state transitions (PLANNED/STARTED/COMPLETED/FAILED/CANCELLED) and required timestamps.
   * Record pins to authoritative inputs used to plan/execute the run (scenario definitions, engine boundary artefacts, and any other declared authority surfaces).

6. **Publish the downstream discovery surface (Run Facts View)**

   * Publish a `run_facts_view` that downstream components can use to discover:

     * active run(s),
     * the canonical identity tuple for each run,
     * a pointer to the Run Record (`run_record_ref`),
     * pinned engine output locators (`engine_output_locator`) for platform-consumable outputs,
     * and the required PASS proofs/gate receipts needed to read/ingest those outputs.
   * Ensure run discovery does not depend on heuristic "latest" scanning of storage paths.

7. **Record engine readiness proofs as pins (not enforcement)**

   * Use the engine outputs catalogue (`read_requires_gates`) and gate map to determine which gate IDs authorize which outputs.
   * Record the relevant PASS proofs (gate receipts or references thereto) into run facts as "pins" suitable for downstream verification.

8. **Optional: emit run status-change events**

   * If enabled, emit run status-change events whose **payload** conforms to `run_status_event.payload.schema.yaml` and whose **envelope** conforms to the platform's canonical event envelope.
   * Status events MUST be consistent with the Run Record lifecycle and MUST be traceable to the run identity tuple.

### 4.2 Non-goals (Binding)

Scenario Runner MUST NOT take responsibility for the following:

1. **No Data Engine internals**

   * MUST NOT depend on segment/state ordering, intermediate artefacts, or internal algorithms.
   * MUST NOT require access to state-expanded docs to function.

2. **No plane-entry enforcement**

   * MUST NOT act as the enforcement boundary for schema validation, quarantine, or "main vs quarantine plane" admission decisions.
   * MUST NOT claim to "authorize ingestion" by itself; it may only publish pins/proofs for other boundaries to verify.

3. **No output interpretation**

   * MUST NOT interpret engine payloads, compute features, make fraud decisions, or derive labels/cases.
   * MUST NOT invent join keys, partitions, or semantics beyond what is declared by the interface pack inventories/contracts.

4. **No discovery by heuristics**

   * MUST NOT instruct downstream components to locate engine outputs by scanning directories, choosing "latest", or relying on naming conventions not declared in the catalogue/locator contracts.

5. **No infrastructure specification**

   * This spec does not define orchestration tooling, deployment topology, queue/bus choices, or runtime scaling strategies (tool-agnostic posture).

---

## 5. Authoritative inputs (Binding)

Scenario Runner MUST treat the following inputs as **authoritative**. If an input is not listed here (or is not referenced via an authoritative contract/inventory), Scenario Runner MUST NOT assume it exists or infer semantics for it.

### 5.1 Caller-provided run request (authoritative at the boundary)

* **`scenario_run_request`** (caller -> Scenario Runner) is the authoritative request payload for creating/planning a run.

  * Scenario Runner MUST validate it against `contracts/scenario_run_request.schema.yaml`.
  * Any fields required to form a valid engine invocation (world identity, seed policy, scenario intent, correlation fields) MUST be present or derivable strictly per this schema.

### 5.2 Scenario definitions (authoritative "scenario knobs" surfaces)

Scenario Runner MUST treat scenario definitions as **read-only authority surfaces** that are either:

* referenced by the run request (preferred), or
* provided/registered through a controlled authoring flow defined by this component.

Authority shape:

* **Scenario catalogue items** MUST conform to `contracts/scenario_definition.schema.yaml`.
* Scenario Runner MUST NOT "invent" scenario knobs not present in the authoritative scenario definition (or not declared as supported in this component).

### 5.3 Platform Rails (authoritative)

Scenario Runner MUST comply with the platform rails as authoritative for:

* **Canonical identity fields** and immutability rules (`parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, optional `seed`)
* **Run anchoring contract** (`run_record` shape and lifecycle semantics)
* **Canonical event envelope** (only if Scenario Runner emits run status events)
* **Receipt semantics** (only if Scenario Runner stores/links receipts as pins)

Scenario Runner MUST NOT duplicate or redefine Rails-owned semantics; it must reference them.

### 5.4 Data Engine Interface Pack (authoritative black-box boundary)

Scenario Runner MUST treat the Data Engine Interface Pack as authoritative for **everything engine-facing**, including:

1. **Engine invocation surface**

   * `contracts/engine_invocation.schema.yaml` is authoritative for the request Scenario Runner sends to the engine.
   * Scenario Runner MUST form invocations that conform to this contract (including `scenario_binding` rules).

2. **Engine output inventory**

   * `engine_outputs.catalogue.yaml` is authoritative for:

     * which outputs exist (`output_id`)
     * how they are addressed (`path_template`, partitions)
     * what their scope is (world/run/seed/scenario/etc.)
     * which outputs are intended for platform exposure (e.g., `exposure: external`)
     * which gates must PASS before read/ingest (`read_requires_gates`)
   * Scenario Runner MUST NOT assume an engine output exists unless it is declared in the catalogue.

3. **Engine gates map**

   * `engine_gates.map.yaml` is authoritative for:

     * gate IDs and their scope
     * how PASS is verified (verification method + required artefacts)
     * which outputs a gate authorizes
     * upstream gate dependencies (if any)
   * Scenario Runner MUST derive "required PASS proofs to record" from:

     * output -> `read_requires_gates` (catalogue), and
     * gate -> verification semantics (gate map).

4. **Output locator and gate receipt shapes**

   * `contracts/engine_output_locator.schema.yaml` is authoritative for the locator objects Scenario Runner pins into `run_facts_view`.
   * `contracts/gate_receipt.schema.yaml` is authoritative for engine gate PASS/FAIL proofs (or references thereto) pinned into `run_facts_view`.

5. **Event envelope (engine-side)**

   * If the interface pack defines an engine-native envelope contract, Scenario Runner MUST treat it as an engine boundary artefact only.
   * For platform-emitted status events, Scenario Runner MUST use the **platform Rails** canonical envelope (not an engine-native variant).

### 5.5 Explicitly non-authoritative inputs (guardrail)

Scenario Runner MUST NOT treat the following as authoritative inputs:

* any Data Engine **segment/state** docs, intermediate artefacts, or internal step ordering;
* any "latest directory scanning" heuristics for discovering engine outputs;
* any join keys or semantics not declared in the engine output catalogue and locator contracts.

---

## 6. Primary outputs (Binding)

Scenario Runner produces **control-plane artefacts** that downstream components rely on for **run identity**, **pinning**, and **discovery**. These outputs MUST be treated as **authority surfaces** (read-only truth for consumers) and MUST carry the canonical identity tuple.

Scenario Runner's primary outputs are:

1. **Run Record** (authoritative run anchor; Rails-owned schema)
2. **Run Facts View** (downstream discovery surface; Scenario Runner-owned schema)
3. **Optional run status-change events** (payload owned here; envelope owned by Rails)

### 6.1 Run Record (Binding)

The **Run Record** is the authoritative anchor for a run.

**Shape and authority**

* Scenario Runner MUST emit a Run Record that conforms to the **Platform Rails** `run_record.schema.yaml`.
* The Run Record is a **run-scoped authority surface**.

**Required content**

* The Run Record MUST include the canonical identity tuple:

  * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
  * and `seed` where required for replayability.
* The Run Record MUST include:

  * provenance fields (runner identity/version, timestamps), and
  * lifecycle `status` with the required timestamp fields for that status.
* The Run Record SHOULD include `authority_pins` that point to:

  * the scenario definition (or scenario-set refs) used for this run, and
  * any other authoritative inputs the run is pinned to (as refs + digests where available).

**Publication and immutability**

* Scenario Runner MUST NOT "silently overwrite" an existing published Run Record instance.
* If run lifecycle status changes (PLANNED -> STARTED -> COMPLETED/FAILED/CANCELLED), Scenario Runner MUST publish an updated Run Record **as a new immutable instance/revision** (pinnable by ref/digest).
* The **current** Run Record for a run MUST be discoverable via the Run Facts View (see Section 6.2), not by "latest folder scanning."

### 6.2 Run Facts View (Binding)

The **Run Facts View** is the downstream discovery surface for "what run(s) are active and what is pinned."

**Shape and authority**

* Scenario Runner MUST publish a Run Facts View that conforms to `contracts/run_facts_view.schema.yaml`.
* The Run Facts View is an **authority surface** and MUST be pinnable and auditable.

**What it must enable**
Downstream components MUST be able to use the Run Facts View to:

* discover the **active run(s)** (and/or the active run for a given environment/tenant partition if you model that),
* obtain the canonical identity tuple for each run,
* obtain a `run_record_ref` (and optional digest) for the run's authoritative Run Record,
* locate platform-consumable engine outputs via **engine output locators** (`engine_output_locator` objects),
* determine which **PASS proofs/gate receipts** are required before reading/ingesting those outputs.

**Required content (minimum)**
For each run entry, the Run Facts View MUST provide, at minimum:

* canonical identity tuple (`parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, optional `seed`)
* run lifecycle status (or a direct pointer to where status is authoritative)
* a pointer to the current Run Record instance: `run_record_ref` (plus digest if available)
* a set of **engine output locators** for engine outputs intended for platform use (at minimum those with `exposure: external` in the engine outputs catalogue, when they exist for the run/world)
* gate proof pins sufficient for downstream verification:

  * either embedded `gate_receipt` objects, or references to them, consistent with the engine interface pack.

**Anti-heuristic rule (hard)**

* Downstream components MUST NOT be instructed to discover runs or outputs by scanning storage for "latest."
  Scenario Runner MUST make Run Facts View sufficient for discovery.

**Publication and consistency**

* Scenario Runner MUST publish Run Facts View updates as new immutable instances/revisions.
* Any published Run Facts View instance MUST be internally consistent:

  * referenced Run Records MUST exist,
  * locators MUST correspond to declared `output_id`s in the engine outputs catalogue,
  * gate receipts/refs MUST correspond to declared `gate_id`s in the engine gate map.

### 6.3 Optional: Run status-change event (Binding)

Scenario Runner MAY emit run status-change events. If it does, the following requirements apply:

**Envelope and payload**

* The **event envelope MUST be the Platform Rails canonical event envelope** (Scenario Runner MUST NOT use an engine-native envelope for platform events).
* The **payload MUST conform** to `contracts/run_status_event.payload.schema.yaml`.

**When to emit**

* Scenario Runner SHOULD emit a status-change event on each lifecycle transition:

  * PLANNED, STARTED, COMPLETED, FAILED, CANCELLED

**Required event linkage**

* Every status event MUST carry the canonical identity tuple in the envelope (per Rails).
* The payload SHOULD include a pointer to the current Run Record (`run_record_ref`) and/or the Run Facts View instance that is current at the time of emission, to support audit.

### 6.4 Output classification and access posture (Binding)

* Scenario Runner outputs (Run Records, Run Facts View, optional status events) MUST be treated as control-plane authority surfaces/events and MUST follow the platform's security/access posture (classification, least privilege, auditability).
* Scenario Runner outputs MUST NOT contain secrets.

---

## 7. Data model and contracts (Binding)

This section defines the **authoritative data objects** Scenario Runner uses/emits and the **contract inventory** that makes those objects machine-checkable. Scenario Runner contracts MUST be consistent with **Platform Rails** and the **Data Engine Interface Pack**.

### 7.1 Contract inventory and ownership (Binding)

#### 7.1.1 Scenario Runner-owned contracts (authoritative here)

These schemas are owned by Scenario Runner and MUST live under `contracts/` in this component:

* `scenario_run_request.schema.yaml`
  Caller -> Scenario Runner request to plan/create a run.

* `scenario_definition.schema.yaml`
  Read-only scenario catalogue item (scenario knobs surface).

* `run_facts_view.schema.yaml`
  Downstream discovery surface for "active run(s)" + pinned refs.

* `run_status_event.payload.schema.yaml` *(optional)*
  Payload-only schema for run status-change events (if emitted).

#### 7.1.2 Referenced authoritative contracts (MUST NOT be duplicated here)

Scenario Runner MUST reference (not redefine) the following authoritative contracts:

**Platform Rails (authoritative):**

* `id_types.schema.yaml` (canonical identifiers / primitive types)
* `run_record.schema.yaml` (authoritative Run Record shape)
* `canonical_event_envelope.schema.yaml` (only if emitting events)
* receipts schemas only if Scenario Runner stores/links them as pins

**Data Engine Interface Pack (authoritative black-box boundary):**

* `engine_invocation.schema.yaml` (engine invocation request shape)
* `engine_output_locator.schema.yaml` (locator/pin object for engine outputs)
* `gate_receipt.schema.yaml` (PASS/FAIL proof object for engine gates)
* `engine_outputs.catalogue.yaml` (authoritative list of `output_id`s + addressing + required gates)
* `engine_gates.map.yaml` (authoritative list of `gate_id`s + verification semantics)

If a Scenario Runner-owned schema conflicts with any referenced authoritative contract, the Scenario Runner schema MUST be corrected.

---

### 7.2 Canonical data objects (logical model) (Binding)

Scenario Runner deals in a small set of canonical objects. These are logical concepts; their machine shapes are defined by the contract files listed in Section 7.1.

#### 7.2.1 Identity tuple (pinned terms)

Scenario Runner MUST use the canonical identity tuple terminology:

* **World identity:** `parameter_hash`, `manifest_fingerprint`
* **Run identity:** `scenario_id`, `run_id`
* **RNG identity (when applicable):** `seed`

These identifiers MUST be treated as immutable once recorded in a run artefact.

#### 7.2.2 Scenario binding (baseline vs overlays)

Scenario Runner MUST represent scenario intent in a form that can be mapped to the Data Engine's `scenario_binding` model:

* baseline/no-overlay runs (engine mode `none`)
* single-scenario overlay
* multi-scenario overlay set

Scenario Runner MUST NOT invent additional scenario binding modes unless the engine interface pack defines them.

#### 7.2.3 Engine invocation (black-box boundary object)

Scenario Runner constructs an engine invocation request using the engine interface contract. It is treated as an **opaque boundary object** with known required fields per that contract.

#### 7.2.4 Output locator (pin object)

Scenario Runner pins engine outputs for downstream discovery using **engine output locator** objects. A locator MUST at minimum provide:

* `output_id` (catalogue-defined)
* `path` (resolved concrete address)

Optional identity fields may be included when helpful, but locators MUST remain valid even if downstream treats them as opaque pins.

#### 7.2.5 Gate receipt (PASS proof pin)

Scenario Runner pins gate proofs using **gate receipt** objects (or references to them) defined by the engine interface pack. Downstream components use these pins to enforce "no PASS -> no read".

---

### 7.3 Scenario Runner-owned contract requirements (Binding)

This subsection defines what each Scenario Runner-owned contract MUST cover. Exact field-level shapes are defined by the schema files; the requirements below are the semantic minimum.

#### 7.3.1 `scenario_run_request.schema.yaml` (Binding)

The run request schema MUST support planning/creating a run in a tool-agnostic way and MUST be sufficient for Scenario Runner to produce:

* a Run Record (Rails `run_record`), and
* an engine invocation request (engine `engine_invocation`).

Minimum semantic coverage:

* **World selection:** the request MUST allow specifying (directly or indirectly) the world identity tuple (`parameter_hash`, `manifest_fingerprint`).
* **Scenario intent:** the request MUST allow expressing baseline vs scenario overlay intent (single or set).
* **Seed policy:** the request MUST allow either:

  * caller-provided `seed`, or
  * an explicit "runner chooses seed" mode (with the chosen seed recorded in outputs).
* **Idempotency/correlation:** the request SHOULD allow a request correlation/idempotency key (e.g., `request_id`) to support safe retries.
* **Validation posture:** the schema MUST be strict enough to refuse internally inconsistent requests (e.g., contradictory scenario intent).

#### 7.3.2 `scenario_definition.schema.yaml` (Binding)

Scenario definitions are read-only authority surfaces that describe scenario knobs.

Minimum semantic coverage:

* **Scenario identifier:** a stable identifier that can be used in scenario binding (single or set).
* **Versioning:** a version field (or versioned identity) so definitions are pinnable.
* **Knob set:** a structured set of allowed knobs/parameters, with types/ranges/enums where applicable.
* **Pins to upstream authority (optional):** if scenarios rely on policy packs or other authority surfaces, the definition MUST be able to reference them by ref + optional digest.
* **Immutability intent:** scenario definitions SHOULD be treated as immutable once published; changes should be via new version.

#### 7.3.3 `run_facts_view.schema.yaml` (Binding)

The run facts view is the downstream discovery surface and MUST not become "a second run record". It is a *view* that pins references.

Minimum semantic coverage:

* **Run discovery:** ability to list "active run(s)" (and optionally partition by environment/tenant if modelled).
* **Canonical identity tuple:** each run entry MUST carry world + run identity (and seed where applicable).
* **Run record pointer:** each run entry MUST include a `run_record_ref` (and optionally digest) pointing to the authoritative Run Record instance.
* **Pinned engine output locators:** the schema MUST support listing engine outputs as `engine_output_locator` objects (or a compatible embedding) keyed by `output_id`.
* **Pinned gate proofs:** the schema MUST support listing required PASS proofs as `gate_receipt` objects or references.
* **Internal consistency constraints:** the schema MUST enforce "no empty anchors" (e.g., an active run entry must at least include identity + run_record_ref).

#### 7.3.4 `run_status_event.payload.schema.yaml` (Optional, Binding if present)

If Scenario Runner emits run status events:

* This schema MUST define **payload only**.
* The event envelope MUST be the Platform Rails canonical envelope.
* Payload MUST include (at minimum):

  * new status (and optionally prior status),
  * status timestamp,
  * and a pointer to `run_record_ref` or equivalent anchor for audit.

---

### 7.4 Referencing rules (schema_ref, refs, and no duplication) (Binding)

#### 7.4.1 Schema authority at boundaries

* Any Scenario Runner **persisted surface** intended for downstream consumption (scenario definitions, run facts views) SHOULD carry a `schema_ref` field (or be accompanied by a manifest carrying it) to enable validation and audit.
* Run Records MUST follow the Rails `run_record` schema authority rules.

#### 7.4.2 No "near duplicate" schemas

Scenario Runner MUST NOT create local copies of:

* Rails envelope/receipt/id contracts, or
* Engine interface invocation/locator/gate contracts.

If Scenario Runner needs additional fields, it MUST extend its *own* schemas and keep referenced objects (locators, gate receipts) either embedded as-is or referenced by pointer, without redefining their meaning.

---

### 7.5 Versioning and compatibility for Scenario Runner-owned contracts (Binding)

* Scenario Runner-owned schemas MUST be versioned (MAJOR.MINOR or equivalent).
* **MAJOR** bump is required for any breaking change (removing/renaming fields, changing requiredness, changing semantics that downstream relies on).
* **MINOR** bump is permitted for additive, backward-compatible changes (new optional fields).
* Downstream consumers MUST be able to read older `run_facts_view` versions during a declared migration window; therefore Scenario Runner SHOULD prefer additive evolution and SHOULD introduce new versions rather than mutating semantics in-place.

---

## 8. Run lifecycle and state machine (Binding)

Scenario Runner MUST model runs using a small, explicit lifecycle state machine. Lifecycle state MUST be recorded in the **Run Record** (authoritative) and reflected in the **Run Facts View** (discovery surface).

### 8.1 Lifecycle states (pinned)

Scenario Runner MUST use the following lifecycle states:

* **PLANNED**: run identity anchored; run has not started execution.
* **STARTED**: run execution has begun.
* **COMPLETED**: run execution finished successfully (control-plane definition).
* **FAILED**: run execution ended unsuccessfully.
* **CANCELLED**: run was intentionally terminated before completion.

No other lifecycle states are permitted unless introduced via a contract version bump and explicitly documented here.

### 8.2 Allowed transitions (hard)

Scenario Runner MUST permit only the following transitions:

* `PLANNED -> STARTED`
* `STARTED -> COMPLETED`
* `STARTED -> FAILED`
* `PLANNED -> CANCELLED`
* `STARTED -> CANCELLED`

Terminal states:

* **COMPLETED**, **FAILED**, and **CANCELLED** are terminal. No transitions out are permitted.

Disallowed examples:

* `PLANNED -> COMPLETED` (must pass through STARTED)
* `FAILED -> STARTED`
* `COMPLETED -> FAILED`

### 8.3 Timestamp requirements per state (hard)

Scenario Runner MUST ensure the Run Record satisfies the Rails run-record lifecycle timestamp requirements:

* **PLANNED** requires `planned_at`
* **STARTED** requires `started_at`
* **COMPLETED** requires `completed_at`
* **FAILED** requires `failed_at` (+ `failure_reason_codes` SHOULD be non-empty)
* **CANCELLED** requires `cancelled_at` (+ `failure_reason_codes` SHOULD be non-empty)

If the Rails run-record schema encodes stricter conditional requirements, that schema prevails.

### 8.4 State meaning and "done" semantics (control-plane)

Scenario Runner MUST interpret lifecycle meaning as follows:

* **STARTED** means the run has been committed to execution and the engine invocation has been issued (or an equivalent "execution begun" action has occurred).
* **COMPLETED** means Scenario Runner has determined the run's execution has finished successfully **for control-plane purposes**.

Important:

* Scenario Runner MUST NOT claim that downstream ingestion/feature/decision pipelines have succeeded. Those are separate components.
* Scenario Runner MAY define "control-plane completion" as:

  * "engine run finished and produced required outputs/gates", and/or
  * "engine signalled completion via its own completion artefact,"
    but this must be expressed only via black-box interface signals (catalogue/gates/receipts), never engine internals.

### 8.5 Failure semantics (hard)

Scenario Runner MUST record a run as **FAILED** if any of the following occur and cannot be resolved within Scenario Runner policy:

* Engine invocation is refused (invalid request, inconsistent identity tuple, etc.)
* Engine invocation repeatedly fails and Scenario Runner exhausts its retry policy
* Required black-box readiness conditions cannot be satisfied (e.g., required PASS proofs are unavailable after a defined window)

When marking FAILED:

* Scenario Runner MUST set `failed_at`
* Scenario Runner SHOULD record failure reason codes and relevant references (request_id, gate IDs expected, etc.) as pins/notes in the Run Record and/or Run Facts View.

### 8.6 Cancellation semantics (hard)

Scenario Runner MUST support cancellation from:

* PLANNED state (before start), and
* STARTED state (during execution).

When marking CANCELLED:

* Scenario Runner MUST set `cancelled_at`
* Scenario Runner SHOULD record cancellation reason codes and who initiated the cancellation (principal/service).

Scenario Runner MUST NOT silently cancel; cancellation must be explicit and auditable.

### 8.7 Idempotency and conflict rules for lifecycle updates (hard)

Scenario Runner MUST ensure lifecycle updates are idempotent and conflict-safe:

* Re-applying the same transition (e.g., retry publishing STARTED with identical timestamps) MUST be treated as a duplicate update (no conflicting state).
* Attempting an invalid transition (e.g., STARTED -> PLANNED) MUST be refused.
* Attempting to update a run with the same `run_id` but differing pinned identity tuple or pins MUST be treated as a conflict and refused.

### 8.8 Run Facts View consistency with Run Record (hard)

Scenario Runner MUST ensure:

* Run Facts View reflects the **current** lifecycle state of the run (or points to the authoritative Run Record revision that carries it).
* Any run marked active/started in Run Facts View MUST have a corresponding Run Record revision that is STARTED.
* A run in a terminal state MUST NOT remain listed as "active" unless explicitly defined as a separate concept (not recommended).

---

## 9. Engine handshake as a black box (Binding)

Scenario Runner MUST interact with the Data Engine **only** through the **Data Engine Interface Pack** boundary artefacts (invocation contract, outputs catalogue, gates map, locator + gate receipt shapes). Scenario Runner MUST NOT depend on any segment/state internals.

### 9.1 Invocation policy (Binding)

#### 9.1.1 Contract compliance (hard)

* Every engine invocation issued by Scenario Runner MUST conform to the engine interface pack's **engine invocation contract** (`engine_invocation.schema.yaml`).
* Scenario Runner MUST NOT add engine-facing fields that are not permitted by that contract.

#### 9.1.2 Required identity binding (hard)

For each invocation, Scenario Runner MUST bind the engine request to the canonical identity tuple as required by the engine invocation contract, including:

* world identity: `parameter_hash`, `manifest_fingerprint`
* run identity: `run_id`
* RNG identity: `seed` (required by the engine invocation boundary; if Scenario Runner chooses it, it MUST be recorded and treated as immutable)

Scenario Runner MUST ensure the invocation identity matches the Run Record identity for that run.

#### 9.1.3 Scenario binding mapping (hard)

Scenario Runner MUST express scenario intent for the engine using the engine's `scenario_binding` model as defined by the engine invocation contract:

* Baseline / no-overlay runs MUST map to the engine's "no scenario overlay" mode.
* Single-scenario runs MUST map to the engine's single-scenario mode using the scenario identifier defined in Scenario Runner's scenario definition surface.
* Multi-scenario runs MUST map to the engine's scenario-set mode using the scenario identifiers defined in Scenario Runner's scenario definition surfaces.

Scenario Runner MUST NOT invent additional scenario binding modes beyond those defined by the engine invocation contract.

#### 9.1.4 Idempotency and correlation (hard)

Scenario Runner SHOULD populate engine invocation correlation/idempotency metadata when supported by the engine invocation contract (e.g., `request_id`, `invoker`, notes).

Rules:

* Re-issuing an invocation with the same `(manifest_fingerprint, parameter_hash, run_id, seed, scenario_binding)` SHOULD be treated as an idempotent retry.
* Re-issuing an invocation that reuses a `run_id` but changes any pinned identity fields or scenario binding MUST be treated as a **conflict** and refused (do not "last-write-wins").
* Scenario Runner MUST record engine invocation correlation identifiers (when present) in the Run Record and/or Run Facts View for audit.

---

### 9.2 Output discovery policy (Binding)

Scenario Runner's job is to publish **pinnable output locators** for downstream discovery without heuristics.

#### 9.2.1 Authoritative source of "what outputs exist" (hard)

* Scenario Runner MUST treat `engine_outputs.catalogue.yaml` as the authoritative inventory of engine outputs.
* Scenario Runner MUST NOT publish locators for any `output_id` not present in the catalogue.

#### 9.2.2 Which outputs Scenario Runner must publish locators for (hard)

At minimum, Scenario Runner MUST be able to publish locators for **platform-consumable outputs** (e.g., those declared for external/platform exposure in the catalogue).

Scenario Runner MAY allow the caller (via `scenario_run_request`) or scenario definitions to request a subset/superset, but:

* any requested `output_id` MUST exist in the catalogue; otherwise refuse the request, and
* Scenario Runner MUST NOT allow downstream-facing discovery of outputs that are explicitly non-exposed unless the spec introduces an explicit "internal use" mechanism.

#### 9.2.3 Locator shape and construction (hard)

* Scenario Runner MUST publish engine output pins using the engine interface pack's **engine output locator** shape (`engine_output_locator.schema.yaml`).
* A locator MUST minimally contain:

  * `output_id`
  * `path` (a concrete resolved address)

How `path` is obtained:

* Preferred: use a concrete locator emitted/returned by the engine boundary (if the engine provides one).
* Permitted fallback: deterministically construct `path` using the catalogue's `path_template` + required partition keys (e.g., `manifest_fingerprint`, and any run/scenario partitions declared for that output).

Prohibited:

* scanning storage to choose "latest"
* guessing output layout not declared in the catalogue
* substituting alternate fingerprint tokens (must remain consistent with the engine's pinned path conventions)

#### 9.2.4 Schema/dictionary pinning (recommended)

Where the catalogue provides authoritative `schema_ref` and/or `dictionary_ref` for an output, Scenario Runner SHOULD include those references in the locator (if the locator shape supports them), or otherwise record them as pins in the Run Record / Run Facts View.

---

### 9.3 Gate readiness policy (Binding)

Scenario Runner MUST treat "no PASS -> no read" as the operating rule and MUST publish sufficient gate pins for downstream verification.

#### 9.3.1 Required gates per output (hard)

For any output locator published for downstream consumption, Scenario Runner MUST determine the required gate IDs by reading:

* `read_requires_gates` from the output's entry in `engine_outputs.catalogue.yaml`.

Scenario Runner MUST NOT weaken these requirements.

#### 9.3.2 Gate semantics and verification method (hard)

Scenario Runner MUST treat `engine_gates.map.yaml` as authoritative for:

* which `gate_id`s exist,
* what artefacts constitute PASS,
* and how PASS is verified (presence/digest/index-hash checks, etc.).

Scenario Runner MUST NOT invent verification rules.

#### 9.3.3 Gate proof pinning (hard)

Scenario Runner MUST publish PASS proofs for required gates in a form downstream can use.

* Gate proofs MUST conform to the engine interface pack's **gate receipt** shape (`gate_receipt.schema.yaml`) or be references to such receipts (if your run facts view chooses a reference model).
* For each output presented as consumable, Scenario Runner MUST publish (or reference) PASS receipts for **all** gates required by that output.

#### 9.3.4 Presenting "ready" vs "not ready" (hard)

Scenario Runner MUST NOT present an engine output as ready/consumable unless all its required gates are pinned as PASS proofs.

If Scenario Runner publishes locators before gates are available, it MUST ensure the Run Facts View makes the readiness state unambiguous (e.g., by:

* omitting "consumable" presentation until PASS proofs exist, or
* explicitly marking the output as pending with the missing gate IDs).

Silently implying readiness is prohibited.

---

### 9.4 Completion and readiness criteria (Binding)

Scenario Runner MUST define run completion strictly using black-box signals.

Recommended default:

* A run SHOULD be considered **COMPLETED** (control-plane sense) when:

  * the run has STARTED, and
  * all outputs designated "required for completion" by the run request/scenario definition have their required gates pinned as PASS.

Permitted alternatives:

* Completion MAY be driven by a dedicated engine "completion gate" if the interface pack defines one.

Scenario Runner MUST NOT define completion using engine-internal step ordering or intermediate artefacts.

---

### 9.5 Event envelope interaction (Binding)

* Scenario Runner MUST NOT assume engine-emitted events use the platform's canonical envelope unless the interface pack explicitly states so.
* If Scenario Runner emits **platform** status events, those events MUST use the **Platform Rails canonical event envelope** (payload is Scenario Runner-owned; envelope is Rails-owned).
* Any mapping between engine-native envelopes and platform envelopes is owned by plane-entry boundaries (e.g., Ingestion Gate), not Scenario Runner.

---

### 9.6 Prohibited couplings (hard)

Scenario Runner MUST NOT:

* consume or depend on engine segment/state internals,
* infer undocumented output paths/keys,
* bypass declared gate requirements,
* treat "directory scanning" or "latest" heuristics as discovery,
* rewrite identity tuple fields when forming invocations or publishing pins.

---

## 10. Determinism, identity, and replayability (Binding)

Scenario Runner is part of the platform's **replayability contract**. Its job is to ensure that runs are anchored with a stable identity tuple and that all downstream discovery is based on **explicit pins**, not heuristics.

### 10.1 Canonical identity propagation (hard)

Scenario Runner MUST propagate the canonical identity tuple on all of its primary outputs:

* **Run Record** (Rails `run_record`): MUST include
  `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (and `seed` where required)

* **Run Facts View**: MUST include the same identity tuple for each run entry

* **Run status events (optional)**: MUST carry identity fields in the Rails canonical event envelope

Scenario Runner MUST NOT alias, rename, or reinterpret these identity fields.

### 10.2 Immutability of identity fields (hard)

Once a run is PLANNED (i.e., Run Record published), the following fields MUST be treated as immutable for that run:

* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `seed` (if present/required)

Scenario Runner MUST NOT "repair" or "normalise" these values. If an incoming request conflicts with an existing run's pinned identity, Scenario Runner MUST refuse it as a conflict.

### 10.3 Determinism promise of the control plane (Binding)

Given:

* the same `scenario_run_request` (or an explicitly idempotent equivalent),
* the same authoritative scenario definitions (same IDs/versions),
* the same pinned world identity (`parameter_hash`, `manifest_fingerprint`),
* and the same seed policy (including chosen seed if runner-chosen),

Scenario Runner SHOULD produce:

* the same logical Run Record content (modulo timestamps that reflect wall-clock creation time), and
* the same Run Facts View pins for the same run identity.

Scenario Runner MUST ensure that any non-determinism in control-plane outputs is limited to:

* creation/issuance timestamps, and
* explicitly declared unique identifiers (e.g., newly generated `run_id` where caller did not provide one).

### 10.4 Seed policy (Binding)

Scenario Runner MUST support one of the following seed policies (declared by contract and recorded in outputs):

1. **Caller-supplied seed**

   * The caller provides `seed` in the run request.
   * Scenario Runner MUST record it and use it in the engine invocation unchanged.

2. **Runner-chosen seed**

   * The run request explicitly allows Scenario Runner to choose the seed.
   * Scenario Runner MUST choose a seed using a defined policy (implementation-defined), record it in the Run Record, and treat it as immutable thereafter.

Scenario Runner MUST NOT allow a seed to be absent if the engine invocation contract requires it, or if replayability requirements for the run demand it.

### 10.5 Replayability and pinning rules (hard)

Scenario Runner MUST make replay possible by ensuring that downstream components can reconstruct "what this run meant" using only pinned references:

* The Run Record SHOULD pin the scenario definition(s) used (refs + digests where available).
* The Run Facts View MUST pin:

  * the Run Record reference,
  * the engine output locators for consumable outputs, and
  * the PASS proofs required to read/ingest those outputs.

Scenario Runner MUST NOT rely on:

* mutable "latest" pointers,
* implicit environment defaults not recorded in pins,
* or undeclared conventions for locating outputs.

### 10.6 Conflict detection for replays (hard)

Scenario Runner MUST detect and refuse conflicting replays:

* If the same `run_id` is reused with different:

  * world identity (`parameter_hash`, `manifest_fingerprint`),
  * scenario binding intent,
  * or seed,
    Scenario Runner MUST treat this as a conflict and refuse the request (no "last write wins").

* If the same request is retried with the same idempotency/correlation key (if supported), Scenario Runner SHOULD treat it as a duplicate and return the existing run identity and pins.

### 10.7 Minimal audit chain (hard)

Scenario Runner MUST ensure the following chain can be established for any run:

`scenario_run_request` -> `Run Record` -> `Run Facts View` -> (engine invocation correlation) -> (engine outputs + gate receipts)

At minimum, Scenario Runner MUST record enough correlation metadata to link:

* the run record to the engine invocation request(s), and
* the run facts pins to the engine output catalogue and gate map entries they correspond to.

---

## 11. Error handling and refusal behaviours (Binding)

Scenario Runner is a control-plane component and MUST fail in a way that preserves **auditability** and **replay safety**. It must refuse ambiguous or conflicting requests rather than "best-effort" proceed.

### 11.1 Error taxonomy (Binding)

Scenario Runner MUST classify failures into at least the following categories (for logs/receipts/diagnostics):

* **INVALID_REQUEST**: run request fails schema or semantic validation
* **IDENTITY_INVALID_OR_MISSING**: required identity tuple fields missing/invalid
* **SCENARIO_INVALID**: scenario binding references unknown/invalid scenario definitions
* **CONFLICTING_REPLAY**: same `run_id` or idempotency key reused with different pins/identity
* **ENGINE_INVOCATION_REFUSED**: engine rejects the invocation as invalid
* **ENGINE_INVOCATION_FAILED**: engine invocation fails due to runtime errors/timeouts
* **READINESS_TIMEOUT**: required gates/PASS proofs not available within a declared window
* **INTERNAL_ERROR**: Scenario Runner internal failure (unexpected)

Components MAY add more granular reason codes but MUST map them into these categories.

### 11.2 Mandatory refusal cases (hard)

Scenario Runner MUST refuse (reject) a run request if any of the following are true:

1. **Schema invalid**: request does not validate against `scenario_run_request.schema.yaml`.
2. **Identity incomplete**: required world identity fields (`parameter_hash`, `manifest_fingerprint`) are missing/invalid, or required run identity fields cannot be established.
3. **Seed required but missing**: the engine invocation boundary requires `seed` and the request does not provide (or permit choosing) one.
4. **Scenario definition invalid**: request references scenario IDs/versions that cannot be resolved to authoritative scenario definitions (when required).
5. **Output IDs invalid**: request asks for outputs not present in `engine_outputs.catalogue.yaml`.
6. **Gate IDs invalid**: request asks for gates not present in `engine_gates.map.yaml` (if request can specify gates explicitly).
7. **Conflicting replay**: same `run_id` (or idempotency key, if supported) is reused with different world identity, scenario binding, seed, or pinned authority inputs.

Refusal MUST be explicit and auditable; silent fallback is prohibited.

### 11.3 Reject vs fail-closed vs retry (control-plane semantics)

Scenario Runner MUST apply the following control-plane behaviours:

* **Reject**: for client/request defects and replay conflicts (non-retryable without change).
* **Retry** (bounded): for transient engine invocation failures where retrying the same invocation is safe and idempotent.
* **Fail-closed**: when ambiguity would compromise replayability (e.g., cannot determine whether a run started, cannot bind gates to outputs). In fail-closed, Scenario Runner MUST refuse to advance state and MUST record why.

Scenario Runner MUST NOT:

* "assume success" on ambiguous outcomes,
* advance lifecycle state without evidence, or
* weaken required gate pins to proceed.

### 11.4 Engine invocation failure handling (Binding)

#### 11.4.1 Engine invocation refused

If the engine refuses the invocation (contract/schema-level refusal):

* Scenario Runner MUST mark the run as **FAILED** (or keep it PLANNED with explicit refusal metadata, if your policy prefers).
* Scenario Runner MUST record:

  * the engine invocation correlation fields (request_id if present),
  * refusal reason codes (mapped to `ENGINE_INVOCATION_REFUSED`),
  * and the identity tuple.

#### 11.4.2 Engine invocation runtime failure / timeout

If engine invocation fails due to runtime errors/timeouts:

* Scenario Runner SHOULD retry under a bounded policy **only if** the invocation is idempotent (same identity tuple + same scenario binding).
* If retries are exhausted, Scenario Runner MUST mark the run **FAILED** and record reason codes (`ENGINE_INVOCATION_FAILED`).

Scenario Runner MUST NOT "re-issue" an invocation with modified identity/scenario binding in an attempt to recover; that would violate replayability.

### 11.5 Readiness and gate proof failures (Binding)

If Scenario Runner is responsible for waiting for or collecting PASS proofs (policy-defined):

* If required PASS proofs are not available within a declared readiness window:

  * Scenario Runner MUST either:

    * keep the run in **STARTED** with a "pending readiness" status marker in run facts, or
    * mark the run **FAILED** with reason category `READINESS_TIMEOUT`,
      depending on the run policy.
* In either case, Scenario Runner MUST:

  * record which gate IDs were expected,
  * record which outputs were blocked,
  * and MUST NOT publish those outputs as consumable in Run Facts View.

### 11.6 Run Facts View publication failures (Binding)

If Scenario Runner cannot publish an updated Run Facts View (storage/bus failure):

* Scenario Runner MUST treat this as a control-plane integrity failure:

  * it MUST NOT claim the run is discoverable if it is not.
* Scenario Runner SHOULD retry publishing boundedly.
* If retries are exhausted, Scenario Runner MUST:

  * mark the run FAILED (or fail-closed),
  * and record `INTERNAL_ERROR` (or a more specific storage/availability code).

### 11.7 Consistency failures (hard)

Scenario Runner MUST refuse to publish internally inconsistent surfaces:

* Run Facts View referencing a Run Record revision that does not exist
* Locators containing `output_id`s not declared in the catalogue
* Gate receipts referencing `gate_id`s not declared in the gate map
* "Ready/consumable" outputs without corresponding PASS proofs

If such inconsistency is detected, Scenario Runner MUST fail-closed and publish no new "authoritative" surfaces until corrected.

### 11.8 What gets recorded on refusal (Binding)

For any refusal or failure, Scenario Runner MUST ensure an audit trail exists.

At minimum, Scenario Runner MUST record:

* canonical identity tuple (where known),
* request correlation key / request_id (if available),
* the failure category and reason codes,
* and references to any authoritative inputs involved (scenario defs, engine invocation request, etc.).

Where the run record already exists:

* Scenario Runner SHOULD record refusal/failure metadata in a new Run Record revision and reflect it in Run Facts View.

### 11.9 Prohibited patterns (explicit)

Scenario Runner MUST NOT:

* proceed on missing/invalid identity tuple fields,
* accept conflicting reuse of `run_id`,
* publish output locators as consumable when required PASS proofs are missing,
* "guess" engine output locations via scanning or "latest" heuristics,
* silently mutate pins/identity fields in response to errors.

---

## 12. Observability and audit (Binding)

Scenario Runner MUST emit sufficient telemetry and durable artefacts to support:

* operational triage (what failed and where),
* audit (what run was planned, by whom, and what it was pinned to),
* replay investigation (reconstruct the run intent and identity without heuristics).

Scenario Runner telemetry MUST align with Platform Rails observability expectations.

### 12.1 Required telemetry (hard)

Scenario Runner MUST provide, at minimum:

1. **Structured logs** (machine-parsable fields)
2. **Metrics** sufficient to evaluate success/failure and latency of run planning and updates
3. **Traces or correlation IDs** sufficient to connect:

   * caller request -> run planning -> engine invocation -> run facts updates

Tooling choice is implementation-defined; the information requirements are binding.

### 12.2 Canonical identity in telemetry (hard)

Whenever telemetry pertains to a specific run or world, Scenario Runner MUST include:

* `parameter_hash`
* `manifest_fingerprint`
* `scenario_id`
* `run_id`
* `seed` (if applicable)

Additionally, where applicable:

* caller correlation key / `request_id` (if present in the run request)
* engine invocation correlation key (if present in the engine invocation contract)
* target references for surfaces published (run record ref, run facts ref)

Telemetry MUST treat these as opaque values (no parsing assumptions).

### 12.3 Minimum metrics (Binding)

Scenario Runner MUST expose metrics (names are illustrative; semantics are binding) covering:

* **Run request throughput**

  * count of run requests received
  * count accepted vs rejected (by category)
* **Lifecycle updates**

  * count of transitions to each state (PLANNED/STARTED/COMPLETED/FAILED/CANCELLED)
* **Engine invocation outcomes**

  * invocation issued count
  * refused count
  * failed/timeout count
  * retry count
* **Run facts publication**

  * run facts updates attempted vs succeeded vs failed
  * latency distribution for publishing run facts updates
* **Readiness/gate status (if tracked)**

  * required gates satisfied vs missing counts
  * time-to-readiness (if measured)

Metrics MUST be taggable by run identity where feasible, but MUST avoid leaking sensitive data per platform security posture.

### 12.4 Audit chain requirements (hard)

Scenario Runner MUST ensure an auditor can establish the following chain for any run:

1. **The initiating request**

   * the `scenario_run_request` (or a stored summary/pointer) that initiated planning,
   * including who/what initiated it (principal/service, when available)

2. **The run anchor**

   * the Run Record revision(s) emitted for the run, conforming to Rails

3. **The run discovery view**

   * the Run Facts View revision(s) published for the run

4. **The engine interaction correlation**

   * the engine invocation request correlation identifiers (request_id/attempts) recorded as pins or in run record extensions

5. **The pinned engine surfaces**

   * engine output locators for declared consumable outputs
   * PASS proofs/gate receipts (or references to them) that justify consumption

Scenario Runner MUST NOT require engine internals to establish this chain.

### 12.5 Durable record posture (Binding)

Run Records and Run Facts Views are authority surfaces and MUST be:

* pinnable (by ref/path and optional digest),
* immutable once published (new revisions rather than mutation),
* consistent with each other (run facts must point to the authoritative run record revision).

If Scenario Runner emits run status events, those events MUST be consistent with:

* the run record lifecycle,
* and the run facts state at the time of emission (or explicitly reference the corresponding revision).

### 12.6 Failure transparency (hard)

When Scenario Runner fails or refuses an action, it MUST:

* emit structured logs with failure category and reason codes (Section 11 taxonomy),
* record correlation keys and identity tuple fields where known,
* avoid silent failures (no "it just didn't happen" outcomes).

If Scenario Runner cannot publish updated authority surfaces, it MUST fail-closed and record that lack of discoverability is itself a control-plane failure.

### 12.7 Prohibited patterns (explicit)

Scenario Runner MUST NOT:

* omit canonical identity fields from audit-relevant logs/records,
* log secrets or sensitive payload content (only refs/IDs),
* claim a run is "discoverable" without a published run facts revision,
* emit status-change events that cannot be traced back to a specific run record/run facts revision.
---

## 13. Security, privacy, and access posture (Binding)

Scenario Runner is a **control-plane** component. Its artefacts (Run Records, Run Facts Views, scenario definitions) are **authority surfaces** and MUST follow the platform's security posture.

### 13.1 Production-like posture (hard)

Scenario Runner MUST behave as if operating in a production financial environment:

* default-deny access,
* least privilege,
* auditability-first,
* data minimisation.

### 13.2 Classification of Scenario Runner outputs (hard)

Scenario Runner MUST assign a classification (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED) to each published authority surface (or its manifest/metadata), consistent with platform rails.

Default guidance:

* `scenario_definition` and `run_facts_view` SHOULD be **CONFIDENTIAL** (they can reveal operational intent and data locations).
* Run Records SHOULD be at least **INTERNAL**, and **CONFIDENTIAL** if they include sensitive pins or operator context.

### 13.3 Access control and separation of duties (hard)

Scenario Runner MUST enforce:

* **separate permissions** for:

  * creating/planning runs,
  * updating run lifecycle state,
  * reading run facts/discovery surfaces,
  * and reading scenario definitions.
* **named principals only** (human SSO identities and service identities). Shared accounts are prohibited.
* **least privilege** per plane/surface (write access is more restricted than read access).

Break-glass access MAY exist but MUST be time-bounded and fully audited.

### 13.4 Secrets handling (hard)

Scenario Runner outputs MUST NOT contain secrets. This includes:

* API keys, tokens, credentials,
* private keys,
* connection strings,
* or any secret material embedded in `notes`, `extensions`, or logs.

If Scenario Runner receives secrets in a request (accidental), it MUST refuse the request or redact/quarantine per platform policy, and MUST log a security reason code without echoing the secret.

### 13.5 Data minimisation and sensitive content (hard)

Scenario Runner MUST:

* publish **pins, refs, and digests** (locators, gate proofs), not full payload data;
* avoid embedding event bodies, datasets, or sensitive identifiers in run facts;
* ensure any operator context (`created_by`, `notes`) is treated as potentially sensitive and is access-controlled accordingly.

Scenario Runner MUST NOT expand engine locators into "directory listings" or enumerations that increase data exposure beyond what the interface pack declares.

### 13.6 Encryption and transport (hard)

Scenario Runner MUST ensure:

* encryption in transit across trust boundaries,
* encryption at rest for persisted authority surfaces,
* key management external to application code (implementation-defined), with least-privilege decrypt permissions.

### 13.7 Audit logging requirements (hard)

Scenario Runner MUST emit audit-relevant logs/records for:

* run creation/planning,
* lifecycle transitions,
* publication of run facts revisions,
* access to CONFIDENTIAL/RESTRICTED run discovery surfaces (where the platform supports access logging).

Audit telemetry MUST include the canonical identity tuple (`parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, and `seed` if applicable).

### 13.8 Quarantine and non-consumable references (hard)

Scenario Runner MUST NOT present quarantine-plane outputs as consumable.

* If run facts include references to quarantined/failed artefacts for debugging, they MUST be explicitly marked as quarantine/non-consumable and MUST be access-restricted.

### 13.9 Prohibited patterns (explicit)

Scenario Runner MUST NOT:

* store or log secrets,
* publish run facts that enable "bypass discovery" (e.g., undocumented paths, "latest" pointers),
* publish consumable locators without required gate proofs,
* weaken platform rails access posture for convenience,
* make run discovery publicly readable by default.

---

## 14. Conformance checklist (Binding)

Scenario Runner MUST be considered "conformant" only when its behaviour can be demonstrated (by schema validation, deterministic pinning, and auditable artefacts) to comply with Platform Rails and the Data Engine Interface Pack boundary.

### 14.1 Rails compliance mapping (hard)

Scenario Runner MUST demonstrate compliance with the following Rails requirements:

* **Canonical identity propagation (Section 3 Rails)**

  * Run Record and Run Facts View MUST carry `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (and `seed` where applicable).
* **Immutability of identity**

  * Identity tuple fields MUST NOT change for a given `run_id` once anchored.
* **Authority surface posture**

  * Run Records and Run Facts Views MUST be treated as authority surfaces (pinnable, immutable, auditable revisions).
* **Canonical envelope (only if events emitted)**

  * If run status events are emitted, they MUST use the Rails canonical event envelope (payload-only contract locally).

### 14.2 Data Engine Interface Pack compliance (hard)

Scenario Runner MUST demonstrate compliance with engine boundary rules:

* **Invocation contract compliance**

  * Engine invocation requests MUST validate against `engine_invocation.schema.yaml`.
* **Catalogue fidelity**

  * Scenario Runner MUST NOT publish locators for `output_id`s not declared in `engine_outputs.catalogue.yaml`.
* **Gate map fidelity**

  * Scenario Runner MUST NOT publish/require gate IDs that are not declared in `engine_gates.map.yaml`.
* **Locator and gate receipt shape compliance**

  * Any pinned engine output locator MUST validate against `engine_output_locator.schema.yaml`.
  * Any pinned gate proof MUST validate against `gate_receipt.schema.yaml` (or be a reference model explicitly defined in `run_facts_view`).

### 14.3 Scenario Runner contract conformance (hard)

Scenario Runner MUST validate its owned boundaries:

* `scenario_run_request` MUST validate against `contracts/scenario_run_request.schema.yaml`.
* Scenario definitions MUST validate against `contracts/scenario_definition.schema.yaml`.
* Run Facts Views MUST validate against `contracts/run_facts_view.schema.yaml`.
* If status events are enabled:

  * payload MUST validate against `contracts/run_status_event.payload.schema.yaml`, and
  * the envelope MUST validate against the Rails canonical envelope contract.

### 14.4 Lifecycle conformance (hard)

Scenario Runner MUST demonstrate:

* Only allowed lifecycle transitions occur (Section 8.2).
* Timestamp requirements per state are satisfied (Section 8.3).
* Terminal states are terminal (no transitions out).
* Run Facts View reflects (or points to) the authoritative Run Record lifecycle state (Section 8.8).

### 14.5 Discovery and pinning conformance (hard)

Scenario Runner MUST demonstrate:

* **No heuristic discovery**

  * Downstream discovery is possible using Run Facts View alone (no "latest scanning" required).
* **Pin completeness**

  * Run Facts View includes:

    * canonical identity tuple,
    * `run_record_ref` to the current Run Record revision,
    * engine output locators for declared consumable outputs,
    * and required PASS/gate proofs (or explicit "pending/missing gate IDs" markers if readiness is not yet met).
* **Internal consistency**

  * Every locator's `output_id` exists in the catalogue.
  * Every gate proof's `gate_id` exists in the gate map.

### 14.6 Idempotency and conflict conformance (hard)

Scenario Runner MUST demonstrate:

* **Idempotent retries**

  * Replaying the same run request with the same idempotency/correlation key (if supported) returns the same anchored run identity and pins (no duplicate runs).
* **Conflict refusal**

  * Reusing the same `run_id` with different world identity, seed, or scenario binding is refused as `CONFLICTING_REPLAY`.
* **Transition idempotency**

  * Retried lifecycle updates do not create conflicting state (duplicates are safe; invalid transitions are refused).

### 14.7 Error/refusal conformance (hard)

Scenario Runner MUST demonstrate:

* Mandatory refusal cases are enforced (Section 11.2).
* Engine refusal/failure paths are recorded and auditable (Section 11.4).
* Readiness timeout behaviour matches policy and never misrepresents outputs as consumable (Section 11.5).

### 14.8 Observability and audit conformance (hard)

Scenario Runner MUST demonstrate:

* Logs/metrics/traces include canonical identity fields when run-specific (Section 12.2).
* An auditor can reconstruct:
  `scenario_run_request -> Run Record revisions -> Run Facts View revisions -> engine invocation correlation -> pinned locators + gate proofs` (Section 12.4).
* Failures are transparent (no silent drops), and reason codes are emitted (Section 12.6).

### 14.9 Required test vectors (minimum)

Scenario Runner MUST be verifiable using at least these test vectors:

**Happy paths**

1. Baseline run (no overlays) -> PLANNED -> STARTED -> COMPLETED; run facts includes expected locators + required PASS proofs.
2. Single scenario overlay run -> same as above.
3. Multi-scenario set run -> same as above.

**Refusals**
4. Missing/invalid world identity -> reject.
5. Seed required but missing -> reject.
6. Unknown scenario_id/version in request -> reject.
7. Requested `output_id` not in catalogue -> reject.
8. Conflicting reuse of `run_id` (different pins/identity) -> reject as conflict.

**Engine/boundary failures**
9. Engine invocation refused -> FAILED (or policy-defined outcome) with auditable reason codes + correlation.
10. Engine invocation transient failure -> bounded retries -> FAILED if exhausted.
11. Readiness timeout (required gates not available) -> policy-defined outcome; outputs not presented as consumable.

**Publication failures**
12. Run facts publication failure -> fail-closed (no false discoverability) with auditable failure record.

### 14.10 Integration gate (hard)

Scenario Runner MUST NOT be considered integration-ready unless:

* owned schemas validate (inputs and published surfaces),
* lifecycle rules are enforced,
* no heuristic discovery is required,
* conflict/refusal behaviour is correct,
* and the audit chain is demonstrably reconstructible from emitted artefacts.

---

## 15. Versioning and change management (Binding)

Scenario Runner contracts and semantics MUST evolve in a way that preserves **downstream interoperability** and **replayability**. This section defines how changes are introduced, versioned, and rolled out.

### 15.1 Versioning scope

This section governs versioning for:

* `scenario_runner.md` (this specification)
* Scenario Runner-owned contracts in `contracts/`
* Published authority surfaces emitted by Scenario Runner (Run Facts Views, scenario definitions)

Rails-owned contracts and engine interface pack contracts are governed by their own change processes and are only referenced here.

### 15.2 Versioning scheme (pinned)

Scenario Runner-owned schemas MUST use a clear `vMAJOR.MINOR` scheme (or semver equivalent), and the `scenario_runner.md` spec MUST declare its own version in front matter.

* **MAJOR** increments for breaking changes.
* **MINOR** increments for backward-compatible additive changes.

### 15.3 What counts as a breaking change (MAJOR required)

A change MUST be treated as breaking if it does any of the following:

* Removes a field that downstream may read.
* Renames a field.
* Changes a field's type or structural shape.
* Changes requiredness in a way that would cause previously valid objects to fail validation (e.g., optional -> required).
* Changes semantic meaning in a way that could cause silent misinterpretation (e.g., changing the meaning of "active" runs, changing seed semantics).
* Changes lifecycle state meanings/transitions in a way that breaks downstream assumptions.
* Changes the discovery contract such that downstream can no longer discover runs/outputs without new logic.

Breaking changes MUST:

* introduce a new schema version (new `schema_ref` target),
* define a migration plan and support window (Section 15.6).

### 15.4 Backward-compatible changes (MINOR permitted)

The following are generally backward-compatible (subject to downstream tolerance for unknown fields):

* Adding new **optional** fields.
* Adding new optional object members under an `extensions` map.
* Adding new scenario knob fields that are optional and have safe defaults.
* Adding new non-breaking examples/diagrams or clarifying text.

Additive changes MUST NOT:

* contradict Rails or engine interface pack semantics,
* introduce a second source of truth for canonical identity/envelope/receipts.

### 15.5 Stability promises per artefact

Scenario Runner MUST treat the following as "high stability" surfaces:

* `run_facts_view.schema.yaml` (downstream discovery contract)
* `scenario_run_request.schema.yaml` (caller boundary contract)
* the logical meaning of lifecycle states and transitions (Section 8)

These SHOULD evolve additively whenever possible, using `extensions` rather than reshaping core fields.

### 15.6 Migration and deprecation process (hard)

For any MAJOR change to a Scenario Runner-owned schema or behaviour:

1. **Introduce a new version** alongside the existing version.
2. **Declare a migration window**:

   * start date,
   * end date,
   * supported versions during the window.
3. **Provide compatibility guidance**:

   * how downstream readers should handle both versions (if dual-read is required),
   * how producers will cut over.
4. **Deprecate explicitly**:

   * mark the old version as deprecated,
   * document removal date and expected downstream action.

Scenario Runner MUST NOT force downstream consumers to infer breaking changes implicitly.

### 15.7 Handling upstream changes (Rails / Engine Interface Pack)

Scenario Runner MUST respond explicitly to upstream contract changes:

* **Rails changes**:

  * If Rails changes a referenced contract (e.g., `run_record`), Scenario Runner MUST declare which Rails versions it supports.
  * During a Rails migration window, Scenario Runner MAY support multiple Rails versions if required, but MUST declare this explicitly.

* **Engine Interface Pack changes**:

  * If the engine output catalogue changes (new/retired `output_id`s, changed required gates), Scenario Runner MUST:

    * update its run facts publishing logic and examples accordingly,
    * ensure no locators or gate pins refer to retired IDs without explicit deprecation handling.
  * If engine invocation schema changes, Scenario Runner MUST update its invocation formation rules and contract references.

Upstream changes MUST be treated as integration-affecting and MUST be logged and versioned in Scenario Runner artefacts when they change behaviour or outputs.

### 15.8 Change logging and traceability (hard)

Any binding change to Scenario Runner MUST:

* update the spec version in front matter (if the document meaning changes),
* update contract versions as applicable,
* be traceable in version control history.

If a local changelog is adopted later, each entry MUST include:

* date,
* versions impacted,
* breaking vs non-breaking flag,
* migration notes (if breaking).

### 15.9 Prohibited patterns (explicit)

Scenario Runner MUST NOT:

* introduce breaking schema changes under a MINOR bump,
* change discovery semantics without versioning,
* duplicate or fork Rails/engine interface contracts locally to "get unstuck,"
* rely on "latest" pointer behaviour to avoid versioning discipline,
* silently change lifecycle meanings or seed policy without updating this spec and contract versions.

---

## Appendix A. Glossary (Informative)

**Active run**
A run currently designated as discoverable for downstream processing via `run_facts_view` (definition is platform-owned; commonly runs in PLANNED/STARTED, but the exact rule must be explicit).

**Authority surface**
A persisted artefact/bundle treated as read-only truth by downstream components (pinnable, immutable, auditable). Run Records and Run Facts Views are authority surfaces.

**Baseline run**
A run with no scenario overlays applied. For engine invocation this maps to `scenario_binding.mode = "none"` (per engine interface pack).

**Black box (Data Engine)**
Integration posture where the platform depends only on the engine's published interface artefacts (invocation contract, output catalogue, gate map, locator + receipt shapes) and not on engine segment/state internals.

**Canonical identity tuple**
The pinned set of identifiers used platform-wide:

* world identity: `parameter_hash`, `manifest_fingerprint`
* run identity: `scenario_id`, `run_id`
* RNG identity (when applicable): `seed`

**Completion (control-plane)**
Scenario Runner's definition of "done" for run lifecycle purposes, expressed only via black-box signals (e.g., required outputs have PASS proofs), not by downstream ingestion or analytics success.

**Conflict (run replay)**
Reuse of a `run_id` (or idempotency key) with different world identity, seed, scenario binding, or pins. Must be refused.

**Engine invocation**
The black-box request Scenario Runner sends to the Data Engine, shaped by `engine_invocation.schema.yaml`.

**Engine output locator**
A pin object that identifies a specific engine output instance for discovery (at minimum `output_id` + `path`), shaped by `engine_output_locator.schema.yaml`.

**Gate / HashGate**
A validation gate that produces PASS/FAIL proof for a target. Downstream reads are authorized only when required gates are PASS ("no PASS -> no read").

**Gate receipt**
The PASS/FAIL proof object for an engine gate, shaped by `gate_receipt.schema.yaml`, pinned into run discovery surfaces for downstream verification.

**Idempotency key (run request)**
A correlation key used to safely retry a run planning request without creating duplicate runs (e.g., `request_id`).

**Lifecycle state**
The run's control-plane state: PLANNED, STARTED, COMPLETED, FAILED, CANCELLED.

**No PASS -> no read**
Operating rule: a component must not read/ingest an output unless all declared required gates have PASS proofs.

**Pins**
Explicit references and/or digests that bind a run to specific authoritative inputs and outputs (scenario definitions, run record ref, output locators, PASS proofs).

**Run Facts View (`run_facts_view`)**
Downstream discovery surface published by Scenario Runner that lists active run(s) and provides pins needed to locate outputs and verify gates.

**Run Record (`run_record`)**
Authoritative run anchor object defined by Platform Rails, emitted by Scenario Runner, binding run identity to world identity and lifecycle status.

**Scenario definition**
A read-only authority surface describing scenario knobs and parameters, shaped by `scenario_definition.schema.yaml`.

**Scenario binding**
The method by which scenario intent is communicated to the engine (none / single / set), per the engine invocation contract.

**Seed policy**
How the run's RNG identity (`seed`) is provided or selected (caller-supplied vs runner-chosen) and how it is recorded for replayability.

**Status-change event**
Optional event emitted by Scenario Runner to report lifecycle transitions. Uses Rails canonical envelope and a Scenario Runner-owned payload schema.

---