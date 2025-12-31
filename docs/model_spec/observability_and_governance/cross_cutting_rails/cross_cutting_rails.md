# Platform Rails: Invariants & Canonical Interfaces

## 0. Front matter (Binding)

### 0.1 Document identity (authoritative)
This file is the **single authoritative** definition of platform-wide “rails” (cross-cutting invariants and canonical interfaces).

- **Canonical path (authoritative):** `docs/model_spec/cross_cutting_rails/rails.md`
- **Companion contracts (authoritative):** `docs/model_spec/cross_cutting_rails/contracts/`
- **Applies to (mandatory):** every specification and component under `docs/model_spec/**`
- **Non-authoritative copies:** any duplicated text outside the canonical path is **informative only** and MUST NOT be treated as binding.

### 0.2 Document metadata (must be maintained)
Maintain the following fields at the top of this document (update on every binding change):

| Field | Requirement |
|---|---|
| **Title** | `Cross-cutting Rails (Platform Invariants)` |
| **Spec class** | `Binding` |
| **Status** | One of: `DRAFT`, `ACTIVE`, `DEPRECATED` |
| **Effective date** | ISO date: `YYYY-MM-DD` |
| **Spec version** | `vMAJOR.MINOR` (MAJOR for breaking rail changes; MINOR for additive/clarifying changes) |
| **Owner** | A named owner (team/role), not “nobody” |
| **Review cadence** | e.g. `per release` or `quarterly` |
| **Last updated** | UTC timestamp `YYYY-MM-DDTHH:MM:SSZ` |
| **Change log pointer** | One of: `git history`, or a local `CHANGELOG.md` path |

### 0.3 Binding scope of this document
The following are **Binding** within this file:

1. Any requirement stated using **MUST / MUST NOT / SHOULD / SHOULD NOT / MAY**.
2. Any defined **field name**, **identifier**, or **token** declared “canonical”.
3. Any referenced contract in `contracts/` declared authoritative (schemas/receipts/envelopes).
4. Any “refusal semantics” (“no PASS → no read”) stated herein.

Everything else is **Informative** only if explicitly labelled informative (e.g., examples in appendices).

### 0.4 Stable anchors and referencing rules
This document is designed to be referenced by other specs using section anchors.

- Components MUST reference rails requirements via:
  - `docs/model_spec/cross_cutting_rails/rails.md#<section-anchor>`
- Section numbers/headings that are referenced externally MUST NOT be renumbered or renamed without a **MAJOR** version bump.
- If a requirement is moved, the old anchor MUST be preserved via a redirect note (or an explicit “Moved to §X.Y” stub) for at least one MINOR cycle.

### 0.5 Contracts directory authority boundary
Where a rule can be machine-validated, it MUST be expressed as a contract file under `contracts/` and referenced from this document.

Minimum authoritative contract set (these filenames are canonical once introduced):
- `contracts/canonical_event_envelope.schema.(yaml|json)`
- `contracts/run_record.schema.(yaml|json)`
- `contracts/hashgate_receipt.schema.(yaml|json)`
- `contracts/ingestion_receipt.schema.(yaml|json)`
- `contracts/id_types.schema.(yaml|json)`

Rules:
- A component MUST treat these contracts as **read-only authority** at runtime boundaries.
- A component MUST NOT weaken these contracts. It MAY extend payload schemas, but it MUST keep the envelope and identity rules intact.

### 0.6 Repository-wide path token convention (pinned)
All storage/path conventions defined by platform specs MUST use the token:

- `fingerprint={manifest_fingerprint}`

A component MUST NOT introduce a competing token (e.g., `manifest=` or `fp=`) for the same concept.

### 0.7 Editing and change discipline
- Any binding change to rails MUST be accompanied by:
  1) a version bump per §0.2, and  
  2) an updated `Last updated` timestamp.
- Additive clarifications that do not change meaning MAY be MINOR.
- Any change that alters required fields, semantics, or refusal behaviour MUST be MAJOR.

(Implementation notes, vendor/tool notes, and non-normative examples MUST be kept clearly separated as Informative.)

---

## 1. Purpose and scope (Binding)

### 1.1 Purpose (why these rails exist)

This document pins the **platform invariants** that make the enterprise system:

* **Replayable:** the same declared inputs + declared lineage yield the same observable outputs (or explicitly declared RNG outcomes).
* **Composable:** components can be swapped/iterated without breaking integration because they share canonical interfaces.
* **Auditable:** every decision, label, and action can be traced back to the exact world/run identity and verified gates.
* **Safe by default:** invalid or unverified upstream artefacts/events are refused or quarantined, never silently consumed.

Accordingly, this document defines:

1. the **minimum canonical metadata** that must travel with all shared-plane artefacts/events, and
2. the **non-negotiable refusal semantics** and boundary behaviours that prevent drift.

### 1.2 What “rails” are (strict definition)

“Rails” are **cross-cutting laws** that every component MUST follow. Rails are limited to:

* **Invariants** (things that must always be true)
* **Canonical interfaces** (IDs, envelopes, receipts, schema authority)
* **Boundary behaviours** (verification, refusal/quarantine, idempotency)
* **Governance rules** (how these laws change)

Rails are intentionally *small*, *stable*, and *globally referenced*.

### 1.3 What rails are not (explicit exclusions)

Rails MUST NOT define:

* Component internals, algorithms, or implementation detail
* Business logic for fraud policy, model scoring, feature engineering, label rules
* Vendor/tool choices (Kafka vs Pub/Sub, Dagster vs Airflow, etc.)
* Performance tuning specifics beyond minimum observability/SLO requirements

Where behaviour is component-specific, it MUST live in that component’s specs and MUST remain compatible with these rails.

### 1.4 Scope boundaries (what this document governs)

Rails govern any surface that crosses a **component boundary** or enters a **shared plane**, including:

* Events emitted to an internal bus or consumed from it
* Persisted datasets/tables shared across components
* Bundles/artefacts referenced by other components (authority surfaces)
* Receipts produced at boundaries (ingestion receipts, verification receipts)
* Audit and observability emissions that claim run/world identity

If it can be consumed by a component other than the producer, it is in scope.

### 1.5 In-scope domains (enumerated)

The following domains are **in scope** and will be fully specified (binding) in later sections:

1. **Identity & lineage propagation**
   Canonical identifiers and where they must appear (world identity, run identity, RNG lineage).
2. **Authority surfaces and immutability rules**
   What is authoritative, how it is versioned, and how it is referenced.
3. **HashGates + refusal semantics (“no PASS → no read”)**
   What constitutes PASS, who verifies it, and what happens when it is missing/invalid.
4. **Schema authority and compatibility rules**
   Schema refs, validation duties, and change/versioning rules.
5. **Canonical event envelope (metadata wrapper)**
   Mandatory envelope fields and constraints; payloads remain component-owned.
6. **Receipts + idempotency + ordering expectations**
   Boundary receipts, idempotency key rules, retry semantics.
7. **Security/privacy posture (tool-agnostic)**
   Minimum required posture for access control and sensitive handling.
8. **Observability + SLOs + degrade ladder interaction**
   Minimum telemetry + how failures drive allowed degrade modes.
9. **Governance for rails changes**
   How these rails evolve without breaking the platform.

### 1.6 Out-of-scope domains (enumerated)

The following are explicitly **out of scope** for rails and MUST NOT be introduced here:

* Fraud strategy content (rule packs, thresholds, risk appetites)
* Feature definitions and feature store design (beyond envelope + lineage)
* Model training details and evaluation methodology
* Case management workflow rules (beyond identity/receipts/audit)
* Data Engine internal state flows (already covered by engine specs)
* UI/UX, dashboards, operational runbooks (except minimum observability signals)

### 1.7 Applicability rule (universal)

Any component specification under `docs/model_spec/**` MUST:

* Treat these rails as **binding**, and
* Include a **rails compliance statement** in its own spec that references the relevant rails sections, and
* Demonstrate that it does not redefine or weaken any pinned interface/invariant.

Failure to comply with rails is a **hard integration stop**: the component is not considered “platform-compatible.”

---

## 2. Normative language and precedence (Binding)

### 2.1 Normative keywords

This document uses the following keywords with the meanings defined below:

* **MUST** / **MUST NOT**: an absolute requirement.
* **SHOULD** / **SHOULD NOT**: a strong recommendation; deviation is permitted only with a documented rationale and explicit acceptance in the component spec.
* **MAY**: optional behaviour; if implemented, it MUST still conform to all MUST/MUST NOT requirements.
* **REQUIRED** / **OPTIONAL**: synonyms for MUST / MAY respectively, used only when describing fields.

If a statement does not use one of these keywords, it is **non-normative** unless it is explicitly labelled Binding.

### 2.2 Binding vs informative within this document

* Any section or statement explicitly labelled **(Binding)** is binding.
* Any section or statement explicitly labelled **(Informative)** is non-binding guidance only.
* Examples are **Informative by default**, even if located in a Binding section, unless the example is explicitly declared “canonical”.

### 2.3 Specification precedence order

When multiple documents apply, precedence is:

1. **Cross-cutting Rails (this document)** — highest authority for platform invariants.
2. **Component binding contracts** (schemas/contracts under the component’s spec tree), but only to the extent they do not conflict with Rails.
3. **Component informative guides** (authoring/acquisition guides, walkthroughs, narratives).
4. **Implementation** (`packages/**`, pipelines, infra code) — never authoritative over specs.

If an implementation or guide contradicts Rails, Rails prevails.

### 2.4 No-override rule (hard)

A component spec **MUST NOT** override, weaken, or reinterpret any Rails requirement.

Allowed patterns:

* **Additive extension**: a component MAY add fields to its own payload schemas, provided the canonical envelope and pinned identifiers remain unchanged.
* **Stricter validation**: a component MAY enforce stricter checks than Rails (e.g., additional required fields), provided it does not create incompatibility with upstream producers that are Rails-compliant.
* **Additional gates**: a component MAY introduce additional HashGates, provided it still honours upstream PASS/no-read semantics.

Disallowed patterns:

* Redefining any canonical identifier name or semantics (e.g., aliasing `manifest_fingerprint` to `fp`).
* Introducing a competing storage token for the same concept (e.g., `manifest=` instead of `fingerprint=`).
* Treating missing PASS as a soft warning while continuing execution.
* Allowing non-authoritative schemas to supersede authoritative contracts.

### 2.5 Conflict handling (what to do when docs disagree)

If a component spec appears to conflict with Rails:

1. The conflict MUST be treated as a **spec defect**.
2. The component MUST not proceed to integration until one of the following happens:

   * Rails is revised (per the rails change process), or
   * The component spec is revised to comply with Rails.
3. Temporary “local exceptions” are prohibited unless explicitly introduced as a Rails-managed mechanism (e.g., a formal waiver process) and versioned.

### 2.6 Local waivers (prohibited unless Rails defines them)

No component may declare a waiver to Rails on its own.

If a waiver mechanism is needed:

* It MUST be defined in this Rails document (governance section),
* It MUST be versioned and time-bounded,
* It MUST be auditable (who approved, why, and when it expires).

### 2.7 Citation and referencing rule (mandatory)

When a component spec relies on a Rails requirement, it MUST reference the specific Rails section(s) by anchor (or section number).

Minimum requirement in every component spec:

* A “Rails compliance” section that lists:

  * which Rails sections apply, and
  * how the component satisfies each one.

---

## 3. Canonical identity and lineage (Binding)

### 3.1 Definitions (canonical)

The platform uses a strict separation between:

* **World identity**: “what world is being generated” (the declared inputs/config that define the world).
* **Run identity**: “which execution of that world (and plan) this is”.
* **Artefact/event identity**: “which concrete object/message is this”.
* **Lineage**: “what authoritative inputs were consumed, and what gates/receipts justify consumption”.

These definitions are **canonical** and MUST be used consistently.

---

### 3.2 Canonical identifiers (names and meaning are pinned)

#### 3.2.1 World identity (pinned)

* **`parameter_hash`**
  Canonical meaning: content-derived hash of the *declared world-defining parameters/config* used for generation.
  Requirements:

  * MUST be deterministic and stable for identical declared inputs.
  * MUST be treated as an opaque identifier (no parsing assumptions).
  * MUST be propagated unchanged across all downstream components.

* **`manifest_fingerprint`**
  Canonical meaning: identifier of the materialised world-manifest instance addressed in storage and referenced by consumers.
  Requirements:

  * MUST be stable and immutable for the life of the manifest.
  * MUST be propagated unchanged across all downstream components.
  * MUST be the sole canonical token used in storage addressing per §3.4.

World identity is the tuple:

* **`(parameter_hash, manifest_fingerprint)`**

A component MUST NOT introduce alternate names for these concepts.

#### 3.2.2 Run identity (pinned)

* **`scenario_id`**
  Canonical meaning: identifier of the scenario specification/plan used to drive a run (knobs, schedules, load shape, etc.).
  Requirements:

  * MUST be stable for the same scenario definition.
  * MUST be recorded wherever run identity is recorded.

* **`run_id`**
  Canonical meaning: identifier of a single concrete execution instance.
  Requirements:

  * MUST be unique per execution (collision-resistant).
  * MUST be immutable once assigned.
  * MUST be carried on all shared-plane outputs produced by that execution.

Run identity is the tuple:

* **`(scenario_id, run_id)`**

#### 3.2.3 RNG identity (pinned where RNG is used)

* **`seed`**
  Canonical meaning: the declared seed (or seed material) used by the run’s RNG policy to generate stochastic outcomes.
  Requirements:

  * If a component consumes RNG, it MUST declare the RNG identity used for the outputs it produces.
  * MUST be propagated on all stochastic outputs and all receipts that justify them.

A component MUST NOT use “hidden randomness”. If RNG affects an output, it MUST be attributable to declared RNG identity and logged per the platform’s RNG policy.

---

### 3.3 Where identity MUST appear (propagation rules)

#### 3.3.1 Shared-plane requirement (hard)

Any artefact/event/record that crosses a component boundary or is written to a shared plane MUST carry, at minimum:

* **World identity**: `parameter_hash`, `manifest_fingerprint`
* **Run identity**: `scenario_id`, `run_id`

If RNG affects the artefact/event/record, it MUST additionally carry:

* **RNG identity**: `seed` (and any other pinned RNG identifiers once defined by policy)

#### 3.3.2 Boundary receipts requirement (hard)

Any boundary receipt (ingestion receipt, verification receipt, quarantine receipt, etc.) MUST carry the same identity fields as the boundary object it refers to:

* MUST include `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
* MUST include `seed` if the boundary object is stochastic or derived from stochastic inputs

#### 3.3.3 Logs/metrics/traces (minimum)

Operational telemetry SHOULD include these identities wherever feasible.
However, any telemetry used for audit/replay MUST include them (i.e., if it claims to support audit, it becomes binding).

---

### 3.4 Storage addressing invariant (pinned)

All platform storage path conventions that key by the world-manifest MUST use the canonical token:

* **`fingerprint={manifest_fingerprint}`**

Rules:

* A component MUST NOT introduce a competing token for the same concept (e.g., `manifest=`, `fp=`, `world=`).
* If additional partitioning is required (scenario/run), it MUST be additive and MUST NOT replace the fingerprint token.

---

### 3.5 Minimal lineage record (what must be knowable)

For any shared-plane output, it MUST be possible to determine:

1. The **producer identity** (component name) and producer version/build.
2. The **authoritative schema reference** for the object (see §6/§7).
3. The **identity tuple** (§3.2) carried on the object.
4. The **upstream authoritative inputs** used, expressed as references (URIs/paths/IDs) and digests where applicable.
5. The **gate justification** used for consumption of upstream inputs (e.g., which PASS/receipt was verified).

This does not require a single universal “lineage object” format yet, but the information MUST exist and be auditable.

---

### 3.6 Determinism and RNG declaration (hard)

* If an output is intended to be deterministic given declared inputs, the producing component MUST ensure:

  * no stochasticity affects the output, OR
  * any stochasticity is explicitly declared and attributable to declared RNG identity.

* If an output is stochastic:

  * the output MUST carry RNG identity, and
  * the component MUST emit sufficient RNG traceability to allow replay under the same declared RNG policy.

---

### 3.7 Immutability rules (hard)

* `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, and (when present) `seed` MUST be treated as **immutable**.
* No component may “correct”, “recompute”, or “normalise” these identifiers.
* If identifiers are missing or invalid, the correct behaviour is refusal/quarantine per boundary policy (not silent repair).

---

### 3.8 Refusal rule on missing canonical identity (hard)

A component MUST NOT emit to a shared plane (or accept into one) any object that is required to carry canonical identity but does not.

At minimum:

* Missing/invalid world/run identity at a boundary MUST result in **reject or quarantine** (per the boundary’s contract).
* Downstream components MUST treat such objects as **non-consumable**.

---

## 4. Authority surfaces and immutability (Binding)

### 4.1 Definition (canonical)

An **authority surface** is any persisted artefact/bundle that is treated as **read-only truth** by one or more downstream components.

An artefact qualifies as an authority surface if it is intended to be:

* referenced by ID/path (not “whatever is current”),
* reused across steps/components,
* relied upon for correctness/audit/replay.

Authority surfaces include (non-exhaustive): schemas, registries, policy/config packs, run plans, reference tables, validation bundles, and receipts.

### 4.2 Authority surface classes (scope is pinned)

Every authority surface MUST declare its scope class as one of:

1. **Global** (not world/run specific)
   Example: canonical schemas, global enumerations.
2. **World-scoped** (tied to `manifest_fingerprint`)
   Example: world materialisations, world-level reference tables.
3. **Scenario-scoped** (tied to `scenario_id`)
   Example: scenario definitions / scenario control knobs.
4. **Run-scoped** (tied to `run_id`)
   Example: run plans, run logs/receipts, run-produced bundles.
5. **Composite-scoped** (explicitly ties multiple scopes)
   Example: artefacts keyed by both world and run: `(manifest_fingerprint, run_id)`.

A component MUST NOT publish an authority surface without explicitly declaring which scope class it belongs to.

### 4.3 Canonical provenance metadata (MUST be present)

Every authority surface MUST carry (or be accompanied by a manifest that carries) the following provenance metadata:

* **Producer identity**: component name + producer version/build identifier
* **Creation time**: UTC timestamp
* **Schema authority**: `schema_ref` that describes the surface layout (or the manifest layout)
* **Canonical identity** per §3:

  * MUST include `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` if in-scope for that surface’s class
  * MUST include `seed` if the surface is stochastic or derived from stochastic inputs
* **Content integrity**:

  * a digest (or digests) sufficient to verify content immutability
  * a declared digest algorithm (opaque string is acceptable, but MUST be consistent within a surface family)

If the surface is a bundle of multiple files/objects, it MUST have a **bundle manifest** that enumerates members and their digests.

### 4.4 Publication semantics (atomicity requirement)

Publishing an authority surface MUST be **atomic from the perspective of consumers**:

* A consumer MUST never observe a “half-published” surface.
* If the surface is multi-file:

  * all members MUST be present before the surface is considered published, and
  * the bundle manifest MUST be present and valid before the surface is considered published.

If a platform uses a “commit marker” or a PASS-style marker, that marker MUST only be emitted after the surface is fully materialised.

### 4.5 Immutability rule (hard)

Once an authority surface is published under its canonical address (IDs/paths), it MUST be treated as **immutable**:

* No in-place edits.
* No silent replacement.
* No “fix-up” writes.

If a correction is needed, it MUST be done by publishing a **new authority surface instance** (new version, new address, or new identity tuple as applicable) with its own provenance and integrity metadata.

### 4.6 Versioning and pinning requirements

Authority surfaces MUST be referenceable in a way that supports **pinning**:

* Consumers MUST be able to reference an exact version/instance deterministically.
* Producers MUST NOT require consumers to use “latest” unless a specific “latest policy” is explicitly defined as a separate authority surface or rule.

Where “latest” behaviour is required operationally, it MUST be implemented as:

* an explicit pointer/alias surface with its own provenance and governance, not implicit directory scanning.

### 4.7 Consumption rules (verification before use)

Before consuming an authority surface, a component MUST:

1. Verify the surface’s **integrity** (bundle manifest + digests, where applicable).
2. Verify any required **gates/receipts** that justify consumption (see §5 “no PASS → no read”).
3. Record (in its own outputs/receipts/logs as applicable) **which exact instance** it consumed (IDs/paths + digests).

Caching is permitted, but a cached surface MUST be tied to the exact identity/version consumed and MUST NOT bypass gate verification.

### 4.8 Mandatory refusal behaviour

If an authority surface required for execution is:

* missing,
* fails integrity verification,
* fails required gate verification,
* or has invalid/missing canonical identity fields (per §3 propagation rules),

then the consumer MUST NOT proceed as if the surface were valid.

The correct behaviour is **refusal** via reject/quarantine/fatal-stop as appropriate to the boundary/plane (defined by the consuming component’s contracts), but “best-effort continue” is prohibited when it would create unauditable or non-replayable outcomes.

### 4.9 Prohibited patterns (explicit)

A component MUST NOT:

* mutate an authority surface after publication,
* recompute or “normalise” canonical identity fields on read,
* consume an authority surface based on a heuristic (“most recent folder”, “highest lexicographic version”) unless an explicit pointer policy exists,
* treat non-authoritative artefacts (ad-hoc local files, manual overrides) as if they were authoritative without publishing them as authority surfaces under these rules.

---

## 5. HashGates and “No PASS → no read” (Binding)

### 5.1 Definition (canonical)

A **HashGate** is a machine-checkable gate that certifies a target artefact/bundle/event stream is:

1. **complete** (all required parts present),
2. **integrity-verified** (content matches declared digests), and
3. **policy-verified** (required validations passed for the relevant scope).

A HashGate has a single authoritative outcome for a specific target instance:

* **PASS**: the target is consumable by downstream components.
* **FAIL**: the target is non-consumable and must be refused/quarantined per §5.6.

### 5.2 Gate targets and scope classes

HashGates MAY be applied to any of the following **targets**:

* **Authority surface** (persisted artefact/bundle)
* **Boundary stream** (e.g., a partitioned event stream or batch landing zone)
* **Derived dataset** (tables/materialisations emitted for downstream use)

Every HashGate MUST declare its **scope class** (aligned with §4.2):

* Global / World-scoped / Scenario-scoped / Run-scoped / Composite-scoped

A HashGate MUST NOT be ambiguous about what it gates.

### 5.3 Canonical gate artefacts (minimum required)

For any gated target, the producer MUST publish (or emit) artefacts sufficient to support independent verification by a consumer.

Minimum required gate artefacts for persisted bundles/surfaces:

1. **Bundle manifest** (canonical inventory)

   * Enumerates all gated members (files/objects) and their digests
   * Declares digest algorithm(s) used
2. **PASS marker** (the only authoritative “go” signal)

   * Indicates successful completion of required validations
   * MUST only be created after all required validations succeed
3. **Gate receipt** (auditable record)

   * Identifies validator identity/version, time, and what was verified

For stream targets, the same concepts apply, but “bundle manifest” may be expressed as a stream checkpoint + digestable metadata as defined by the stream boundary contract.

### 5.4 Binding relationship between gate and target (no “floating PASS”)

A PASS MUST be bound to an exact target instance. Therefore:

* The PASS marker/receipt MUST reference the target by:

  * canonical identity tuple (§3), and
  * target address/ref (path/URI/topic+partition/checkpoint), and
  * a digest or digest-set that uniquely identifies the gated content.

A consumer MUST reject/quarantine a PASS that is not bound to the exact instance it is about to consume.

### 5.5 Verification duties (who must do what)

#### 5.5.1 Producers (gate issuers)

Any component that publishes a target intended for downstream consumption MUST:

* publish the minimum gate artefacts per §5.3,
* ensure gate artefacts are published atomically with target availability (see §4.4),
* ensure PASS is emitted only after validation succeeds,
* ensure FAIL results are recorded (receipt + reason codes) even if the target is quarantined.

#### 5.5.2 Boundary components (gate enforcers)

Any boundary into a shared plane (e.g., ingestion) MUST enforce gates:

* MUST verify required upstream PASS before admitting data into the “main” plane.
* MUST emit an ingestion/boundary receipt that records which PASS (and which target instance) justified admission.

#### 5.5.3 Consumers (gate verifiers)

Any component that reads a gated target MUST:

* verify the PASS marker exists and is valid for the exact target instance,
* verify integrity against the bundle manifest/digests (where applicable),
* record the verified gate reference in its own outputs/receipts (so downstream audit can see what it relied on).

Caching is permitted, but cached content MUST NOT bypass these checks.

### 5.6 “No PASS → no read” rule (hard)

If a target is required to be gated, then:

* **Missing PASS** MUST be treated as **non-existence for consumption purposes**.
* A component MUST NOT:

  * read the target “partially,”
  * fall back to older versions implicitly,
  * continue execution using the ungated target as if it were valid.

The only permitted behaviours are:

* **Refuse** (hard-stop execution for that path), or
* **Quarantine** (route to a quarantine plane with explicit receipts), or
* **Degrade** (only if the component’s degrade ladder explicitly allows an alternative that does not consume the ungated target, and the output is marked degraded per §10).

### 5.7 FAIL semantics and quarantine requirements

When validation fails:

* The producer/boundary MUST emit a **FAIL receipt** with:

  * validator identity/version,
  * timestamp,
  * target reference,
  * outcome = FAIL,
  * reason codes (machine-readable),
  * and (where safe) human-readable summary.

FAILED or ungated targets MUST NOT enter the main consumable plane. If retained, they MUST be stored in a **quarantine plane** that:

* is clearly separated from consumable surfaces/streams,
* is not read by normal consumers,
* and is only accessible for debugging/audit under controlled access.

### 5.8 Gate chaining (upstream gate dependencies)

A component MAY require that a target’s PASS is only meaningful if certain upstream gates were also PASSED.

If so:

* the gate receipt MUST record the upstream PASS references it relied on, and
* consumers MUST be able to audit that chain.

A component MUST NOT claim transitive validity without recording the upstream gate references.

### 5.9 Immutability of gated targets (hard)

Once a target has a PASS:

* the target MUST be treated as immutable (see §4.5),
* the PASS MUST NOT be reused for any modified content,
* any correction MUST publish a new target instance with a new PASS bound to that instance.

### 5.10 Minimum gate receipt fields (canonical requirements)

Every PASS/FAIL receipt MUST include, at minimum:

* `gate_outcome` ∈ {PASS, FAIL}
* `validator_id` (component/service identity)
* `validator_version` (build/version identifier)
* `verified_at` (UTC timestamp)
* `target_ref` (address/URI/topic+checkpoint/etc.)
* canonical identity tuple (§3): `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (and `seed` where applicable)
* `target_digest` (or digest-set reference) sufficient to bind the receipt to the target instance
* `reason_codes` (non-empty on FAIL; MAY be empty on PASS)

### 5.11 Prohibited patterns (explicit)

A component MUST NOT:

* treat “best effort read” as acceptable when PASS is missing/invalid,
* accept a PASS without verifying it binds to the exact target instance being consumed,
* emit PASS before the target is complete and validated,
* silently switch to a different target instance (e.g., “latest”) when PASS is missing,
* publish PASS in a way that can be confused with other runs/worlds (identity must be present and correct).

---

## 6. Schema authority and compatibility (Binding)

### 6.1 Definitions (canonical)

* **Schema**: a machine-readable contract that defines the permitted structure and types of a message/artefact.
* **Schema authority**: the rule that a specific schema source is the *sole* binding definition for validation at boundaries.
* **Schema reference (`schema_ref`)**: an opaque reference that identifies the exact schema version that governs an object.
* **Compatibility**: whether a producer/consumer pair can interoperate safely across schema versions without ambiguity or silent corruption.

### 6.2 Authority rule (hard)

* **JSON-Schema is the canonical authority** for structural validation, even if stored in YAML form in the repo.
* Informal descriptions (docs, README tables, narratives) MUST NOT be treated as schema authority.
* Implementations MUST conform to authoritative schemas; schemas never conform to implementations.

### 6.3 Required presence of `schema_ref` (hard)

Any object that crosses a component boundary or is written to a shared plane MUST include a `schema_ref` that:

* identifies the **exact** schema version that governs the object, and
* is sufficient for an independent validator to fetch/resolve the schema deterministically.

Missing or invalid `schema_ref` at a boundary MUST result in **reject or quarantine** (boundary-specific), never silent accept.

### 6.4 Canonical schema layout (where schemas live)

Schemas are pinned to the spec repo layout:

1. **Platform-wide pinned schemas (highest authority)**
   Located under: `docs/model_spec/cross_cutting_rails/contracts/`
   Includes (minimum): canonical event envelope, run record, receipts, id types.

2. **Component schemas (component authority, subordinate to Rails)**
   Located under: `docs/model_spec/<component_path>/contracts/`
   Includes payload schemas and component-specific artefact schemas.

Rules:

* Component schemas MUST NOT contradict or weaken Rails contracts.
* Component schemas MAY extend payloads, but MUST preserve the pinned envelope and identity rules.

### 6.5 Resolution and pinning rules for `schema_ref`

A `schema_ref` MUST be:

* **pinned** (never “latest”),
* **stable** (resolves to the same schema content for the same reference),
* **unambiguous** across repo changes.

Permitted resolution strategies (tool-agnostic):

* repo path + version (e.g., a versioned contract file path),
* registry key + version (if you later add a registry), or
* content-addressed digest reference.

Disallowed:

* references that depend on “current branch HEAD”,
* non-versioned aliases,
* implicit schema selection by topic name alone.

### 6.6 Boundary validation duties (hard)

#### 6.6.1 Producers

A producer that emits a boundary object MUST:

* emit the correct `schema_ref`,
* ensure emitted objects conform to that schema,
* bump schema versions according to §6.8 when changing shape.

#### 6.6.2 Boundary components (ingestion / plane entry)

Any boundary that admits objects into a shared plane MUST:

* resolve `schema_ref` deterministically,
* validate the object against the authoritative schema,
* reject or quarantine on validation failure,
* emit a receipt containing the `schema_ref` validated and the outcome.

#### 6.6.3 Consumers

Consumers SHOULD validate when feasible.
If a consumer skips validation for performance reasons, it MUST still refuse objects that:

* lack `schema_ref`, or
* fail upstream boundary receipts that assert schema validation occurred.

### 6.7 Envelope vs payload separation (hard)

* The **canonical event envelope** schema is platform-pinned and MUST remain consistent across components.
* Component teams own their **payload** schemas.
* Payload schemas MUST NOT redefine identity/lineage fields differently from Rails, and MUST NOT conflict with the envelope.

### 6.8 Compatibility classification (canonical)

Schema changes are classified as:

#### 6.8.1 Backward-compatible (non-breaking) changes

Permitted without breaking existing consumers (assuming consumers ignore unknown fields):

* adding **optional** fields,
* adding new enum values **only if** consumers are not required to treat unknown values as fatal,
* loosening constraints (e.g., widening a max length) *only if* it does not violate security/safety posture,
* adding new schema versions while continuing to publish the older version during a transition window.

#### 6.8.2 Breaking changes

These are breaking and MUST trigger a **MAJOR** schema version bump and a migration plan:

* adding a **required** field (for existing objects),
* removing a field,
* renaming a field,
* changing a field’s type (e.g., string → int),
* tightening constraints in a way that rejects previously valid objects,
* changing identity/lineage semantics or required presence,
* changing envelope structure.

#### 6.8.3 Semantically breaking changes (must be treated as breaking)

Even if structurally compatible, a change MUST be treated as breaking if it changes meaning in a way that can cause silent misinterpretation (e.g., reinterpreting units, changing the meaning of a status code, changing partition_key semantics).

### 6.9 Versioning rules (pinned)

* Schemas MUST use a clear versioning scheme (e.g., `vMAJOR.MINOR` or semver).
* **MAJOR** increments for breaking changes (per §6.8.2/§6.8.3).
* **MINOR** increments for additive, backward-compatible changes (per §6.8.1).
* Patch-level versioning MAY be used for clarifications that do not change validation outcomes.

The `schema_ref` MUST identify at least MAJOR+MINOR (or equivalent), and MUST resolve to an immutable schema content.

### 6.10 Deprecation and migration duties (hard)

When a breaking change is introduced:

* producers MUST support a defined migration window by emitting either:

  * dual-publish (old + new), or
  * a clearly defined translation boundary (with receipts), or
  * a coordinated cutover (if explicitly governed and time-bounded).

Consumers MUST NOT be forced to infer breaking changes implicitly. Deprecations MUST be explicit and versioned.

### 6.11 Failure behaviour (hard)

* Validation failure at a boundary MUST produce a receipt with:

  * `schema_ref`,
  * failure reason codes,
  * and the identity tuple (§3).
* Components MUST NOT “fix up” invalid objects silently.
* Components MUST NOT accept structurally invalid objects into a consumable plane.

### 6.12 Prohibited patterns (explicit)

A component MUST NOT:

* accept objects without a valid `schema_ref`,
* use “latest schema” resolution,
* treat docs/examples as schema authority,
* publish breaking schema changes under an existing schema version,
* redefine pinned envelope/identity fields in payload schemas.

---

## 7. Canonical event envelope (Binding)

### 7.1 Purpose (what the envelope is for)

The canonical event envelope is the **minimum mandatory metadata wrapper** that makes events:

* routable (partitioning + identity),
* verifiable (schema authority + gate/receipt linkage),
* auditable (world/run lineage),
* replayable (deterministic addressing + time semantics).

The envelope is **platform-owned** and **uniform across all components**. Components own only their payload schemas (within the constraints of these rails).

### 7.2 Envelope vs payload (hard separation)

Every event is logically:

* **Envelope**: pinned metadata defined by these rails.
* **Payload**: component-specific body defined by the producer’s contracts.

Rules:

* Producers MUST emit the envelope exactly as specified here.
* Payload schemas MAY evolve, but MUST NOT alter the meaning or presence of envelope fields.
* Payload MUST NOT redefine canonical identity/lineage fields in a competing way.

### 7.3 Schema authority for the envelope (pinned)

* The authoritative envelope schema MUST live under:
  `docs/model_spec/cross_cutting_rails/contracts/canonical_event_envelope.schema.(yaml|json)`
* Every emitted event MUST be valid against that schema (in addition to any payload schema).

### 7.4 Canonical envelope field set (required unless stated optional)

The following field names are **canonical**. Components MUST NOT rename them, alias them, or reuse them with different meaning.

#### 7.4.1 Event identity (required)

* **`event_id`**
  Unique identifier of this event instance.
  Requirements:

  * MUST be globally unique (collision-resistant).
  * MUST be treated as opaque.
  * MUST be immutable once emitted.

* **`event_type`**
  Namespaced identifier of the event’s semantic type (e.g., `feature.vector.materialised`, `decision.emitted`).
  Requirements:

  * MUST be stable for the lifetime of the event family.
  * MUST NOT encode environment-specific details (no “prod/dev” suffixes).

#### 7.4.2 Producer provenance (required)

* **`producer_id`**
  Canonical producer component identifier (stable component name).
* **`producer_version`**
  Build/version identifier sufficient for audit/replay.
* **`emitted_at`**
  UTC timestamp when the producer emitted the event.

#### 7.4.3 Time semantics (required)

* **`occurred_at`**
  UTC timestamp representing when the event “logically happened” in the domain sense (business-time).
  Requirements:

  * MUST be present even if equal to `emitted_at`.
  * MUST be used for replay semantics where business-time ordering matters.

* **`ingested_at`** (optional at emission; required at/after ingestion)
  UTC timestamp when the boundary admitted the event into the consumable plane.
  Requirements:

  * Boundary components MUST set this on acceptance.
  * Producers MAY omit; boundaries MUST populate.

#### 7.4.4 Schema authority (required)

* **`schema_ref`**
  Reference to the authoritative schema governing this event (envelope + payload).
  Requirements:

  * MUST be present and pinned (not “latest”).
  * MUST resolve deterministically.
  * MUST be validated at boundary entry.

#### 7.4.5 Canonical identity & lineage (required)

Every event that crosses a component boundary or is written to a shared plane MUST include:

* **`parameter_hash`**
* **`manifest_fingerprint`**
* **`scenario_id`**
* **`run_id`**

And MUST include:

* **`seed`** if the event is stochastic or derived from stochastic inputs.

These fields MUST obey §3 immutability/refusal rules.

#### 7.4.6 Routing and partitioning (required)

* **`partition_key`**
  Canonical partition key used by the event bus / storage partitioning.
  Requirements:

  * MUST be stable for the intended grouping semantics (component-defined, but declared).
  * MUST NOT be derived from non-deterministic or ephemeral values.
  * SHOULD be chosen to preserve per-entity ordering where required (e.g., per account / per merchant / per case), if that ordering is relied upon.

* **`sequence`** (optional; required if consumer relies on strict ordering within a partition)
  Monotonic sequence indicator within `partition_key`.
  Requirements (if present/required):

  * MUST be monotonic non-decreasing within the partition for a given run.
  * MUST be auditable (no gaps assumptions unless declared).

#### 7.4.7 Correlation and tracing (optional but reserved)

If used, these fields are reserved and canonical:

* **`correlation_id`** (ties a chain of events across components)
* **`causation_id`** (event_id of the direct causal predecessor)
* **`trace_id`**, **`span_id`** (distributed tracing identifiers)

If present, they MUST be treated as opaque and MUST NOT replace canonical identity fields.

#### 7.4.8 Extensions (optional, constrained)

* **`extensions`** (optional)
  A dictionary for additive metadata that is not yet standardized.
  Requirements:

  * Keys MUST be namespaced (e.g., `component_x.foo`, `platform.bar`) to prevent collisions.
  * MUST NOT duplicate or contradict canonical envelope fields.
  * MUST NOT contain sensitive raw identifiers where rails require tokenisation/posture controls.

#### 7.4.9 Payload container (required)

* **`payload`**
  The component-specific body.
  Requirements:

  * MUST conform to the schema referenced by `schema_ref`.
  * MUST NOT contain conflicting versions of canonical envelope fields.

### 7.5 Timestamp constraints (binding semantics)

* All timestamps in the envelope MUST be UTC and unambiguous.
* `emitted_at` MUST be set by the producer at emission.
* `ingested_at` MUST be set by the boundary upon acceptance.
* `occurred_at` MUST represent domain-time and MUST be present; it MUST NOT be omitted as a substitute for `emitted_at`.

A component MUST NOT reinterpret these meanings locally.

### 7.6 Encoding and immutability (hard)

* Envelope fields MUST be treated as immutable once emitted.
* Serialization format (JSON/Avro/etc.) is implementation-defined, but the logical field set and meanings are fixed.
* If an event needs “correction”, it MUST be a new event with a new `event_id` and explicit linkage via `causation_id`/`correlation_id` (if used).

### 7.7 Boundary validation and failure behaviour (hard)

At any boundary into a shared plane:

* Missing required envelope fields MUST cause **reject or quarantine**.
* Invalid `schema_ref` or schema validation failure MUST cause **reject or quarantine**.
* Missing/invalid canonical identity fields (§3) MUST cause **reject or quarantine**.
* Boundaries MUST emit receipts that record:

  * the `schema_ref` validated,
  * the identity tuple,
  * acceptance outcome,
  * and reason codes on failure.

### 7.8 Prohibited patterns (explicit)

A component MUST NOT:

* emit boundary/shared-plane events without `schema_ref`,
* emit events lacking `parameter_hash` / `manifest_fingerprint` / `scenario_id` / `run_id`,
* treat `extensions` as a place to smuggle competing identity/lineage or override envelope semantics,
* embed environment-specific routing logic in `event_type`,
* “repair” missing canonical identity fields in-flight (must refuse/quarantine instead),
* rely on “latest schema” resolution.

### 7.9 Minimum contract surface (what downstream may assume)

Any downstream component MAY assume that a Rails-compliant event has:

* a valid canonical envelope,
* valid canonical identity fields,
* a resolvable `schema_ref`,
* and boundary receipts that can be used for audit and replay (where the plane requires them).

---

## 8. Receipts, idempotency, and ordering (Binding)

### 8.1 Definitions (canonical)

* **Receipt**: an authoritative, durable record of a boundary decision or verification outcome (e.g., ingest accept/reject, HashGate PASS/FAIL).
* **Boundary**: any interface where an object moves from one trust plane to another (producer → shared plane, quarantine → main, etc.).
* **Idempotency**: repeated submission of the “same” object produces the **same** boundary outcome and does **not** create duplicate side effects.
* **Duplicate**: a repeated submission of an object that is identical under the platform’s idempotency rules.
* **Conflict**: a repeated submission that reuses an identity/idempotency key but differs in content (or differs in any pinned identity fields).

### 8.2 Receipt classes (minimum set)

The platform recognises (at minimum) the following receipt classes:

1. **Ingestion receipt** (required at plane entry)
   Records the outcome of admitting (or refusing) an object into a consumable plane.

2. **Verification receipt** (required where HashGates apply)
   Records the outcome of HashGate verification (PASS/FAIL), per §5.

Other receipt classes MAY exist (e.g., “processing receipt”), but they MUST NOT substitute for ingestion/verification receipts where those are required.

### 8.3 Receipts are authority surfaces (hard)

All receipts are authority surfaces and MUST follow §4 authority and immutability rules.

Therefore:

* Receipts MUST be publishable/queriable deterministically (pinnable).
* Receipts MUST carry canonical identity and provenance.
* Receipts MUST be immutable once published.

### 8.4 Canonical receipt fields (minimum required)

Every receipt (of any class) MUST include, at minimum:

* **Receipt identity**

  * `receipt_id` (unique, collision-resistant)
  * `receipt_type` (e.g., `ingestion`, `hashgate_verification`)
  * `issued_at` (UTC timestamp)

* **Issuer provenance**

  * `issuer_id` (boundary/validator component identity)
  * `issuer_version` (build/version identifier)

* **Target binding**

  * `target_ref` (address/URI/topic+partition+offset/checkpoint/path/etc.)
  * `target_identity` sufficient to identify the target instance:

    * for events: `event_id` (and `producer_id` if needed for uniqueness)
    * for bundles/surfaces: bundle ref + digest-set pointer
  * `target_digest` (or digest-set reference) sufficient to bind receipt to exact content

* **Schema authority**

  * `schema_ref` for the receipt itself
  * `validated_schema_ref` (required when the receipt asserts schema validation occurred at a boundary)

* **Canonical identity tuple (§3)**

  * MUST include: `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
  * MUST include: `seed` where applicable (stochastic targets or stochastic derivation)

* **Outcome + reasons**

  * `outcome` (class-specific; see §8.5 and §5.10 for HashGates)
  * `reason_codes` (required for non-success outcomes; MAY be empty on success)

A component MAY add additional fields, but MUST NOT rename or redefine these canonical fields.

### 8.5 Outcome vocabularies (pinned)

#### 8.5.1 Ingestion outcome (pinned)

Ingestion receipts MUST use:

* `outcome` ∈ { **ACCEPTED**, **REJECTED**, **QUARANTINED** }

Semantics:

* **ACCEPTED**: admitted into the main consumable plane.
* **REJECTED**: not admitted; producer must correct/resubmit (or stop).
* **QUARANTINED**: not admitted into main plane; retained in quarantine plane for inspection.

#### 8.5.2 HashGate verification outcome

HashGate receipts use the pinned fields in §5.10, including:

* `gate_outcome` ∈ {PASS, FAIL}

If a receipt records HashGate verification, it MUST conform to §5.10 in addition to §8.4.

### 8.6 Idempotency requirements (hard)

#### 8.6.1 Events (primary rule)

For envelope-compliant events, **`event_id` is the primary idempotency key**.

At any ingestion boundary:

* Re-receipt of the same `event_id` MUST be treated idempotently **if** the content is identical under §8.7 duplicate rules.
* The boundary MUST NOT create a second admitted copy of the same event in the main plane.

#### 8.6.2 Authority surfaces / bundles

For persisted bundles/surfaces, idempotency MUST be defined using:

* `target_ref` + `target_digest` (or digest-set) + canonical identity tuple (§3)

Re-publication with identical binding MUST be treated as a duplicate, not as a new surface.

#### 8.6.3 Side-effect boundaries

Any boundary that triggers downstream side effects (actions, notifications, case creation, etc.) MUST:

* be guarded by a deterministic idempotency rule, and
* emit receipts that allow auditors to prove “no double side effects occurred”.

### 8.7 Duplicate vs conflict rules (hard)

At any boundary that enforces idempotency:

#### 8.7.1 Duplicate handling

If a submission matches an existing admitted/processed object under the boundary’s idempotency rule:

* The boundary MUST treat it as a **duplicate**.
* The boundary MAY return/emit the same receipt (or a receipt that references the prior receipt), but MUST NOT duplicate the admitted object or side effects.

#### 8.7.2 Conflict handling (must refuse)

A **conflict** exists if any of the following are true for the same idempotency key:

* `target_digest` differs, or
* canonical identity fields differ (§3), or
* `schema_ref` differs in a way that changes the validated structure, or
* (for events) payload differs while reusing the same `event_id`.

On conflict:

* The boundary MUST NOT accept into the main plane.
* The boundary MUST **REJECT or QUARANTINE** (boundary policy), and MUST emit a receipt that:

  * records the conflicting digests,
  * records the conflicting refs/identities,
  * includes reason codes that clearly identify “ID reuse with differing content”.

Silent overwrite is prohibited.

### 8.8 Ordering semantics (what may be assumed)

#### 8.8.1 No global ordering guarantee

The platform provides **no global total ordering** across events or across partitions unless a component explicitly defines and enforces it.

Consumers MUST NOT infer correctness from “arrival order” alone.

#### 8.8.2 Partition ordering is conditional

Within a `partition_key`, a consumer MAY rely on ordering **only if**:

* the producer emits an explicit monotonic ordering indicator (e.g., `sequence` per §7), and
* the boundary/transport preserves or reasserts that ordering as part of its contract.

If these conditions are not met, consumers MUST treat ordering as best-effort and handle reordering.

#### 8.8.3 Time fields are not ordering guarantees

* `occurred_at` represents domain-time, not transport order.
* `emitted_at` represents producer-time, not global order.
* `ingested_at` represents boundary acceptance time, not domain order.

Consumers MUST choose ordering logic explicitly (domain-time vs ingestion-time) and document it in their own specs.

### 8.9 Retry semantics (hard)

* Boundaries and transports MAY deliver objects **at least once**.
* Therefore, components MUST be correct under duplicate delivery by relying on §8.6–§8.7 idempotency and conflict rules.
* A retry MUST NOT be a mechanism for “editing” an object. If content changes, it is a new object/event (new identity) or a conflict (must refuse), per §8.7.

Receipts MUST allow distinguishing:

* transient failure (retryable) vs
* permanent failure (non-retryable),
  via reason codes (and optional retry hints), without changing the object identity.

### 8.10 Mandatory refusal behaviours

A boundary MUST reject or quarantine (never accept) if:

* required canonical identity fields are missing/invalid (§3),
* `schema_ref` is missing/invalid or validation fails (§6),
* required upstream PASS/verification is missing/invalid (§5),
* a conflict is detected (§8.7.2).

### 8.11 Prohibited patterns (explicit)

A component MUST NOT:

* create side effects without an idempotency rule and auditable receipts,
* accept conflicting replays of the same idempotency key by “last write wins,”
* rely on implicit “latest” selection to resolve duplicates or missing inputs,
* treat ordering by arrival time as a correctness guarantee without explicit contract support,
* silently drop duplicates without emitting or linking to a receipt (audit must remain possible).

---

## 9. Privacy, security, and access posture (Binding)

### 9.1 Security posture principle (hard)

Even though the platform may operate on synthetic data, components MUST behave as if operating in a production financial environment:

* **Default-deny** access.
* **Least privilege** for all principals (human and service).
* **Data minimisation**: only emit/retain what is necessary for the component boundary.
* **Auditability-first**: every access and boundary decision must be explainable after the fact.

### 9.2 Data classification (canonical)

All shared-plane objects (events, surfaces, receipts, logs) MUST be classified into one of the following levels:

1. **PUBLIC** — safe for public disclosure (rare; e.g., open-source schemas)
2. **INTERNAL** — non-public but low sensitivity
3. **CONFIDENTIAL** — sensitive operational/business data
4. **RESTRICTED** — highest sensitivity (PII-like identifiers, secrets, security-relevant internals)

Rules:

* Every authority surface (§4) MUST declare its classification in its provenance metadata (or in the bundle manifest).
* Events SHOULD carry classification as a metadata tag (envelope extension is permitted) where it affects routing/storage/access.
* Any object containing **secrets** MUST be **RESTRICTED** and MUST NOT be placed on general shared planes.

### 9.3 Identity and access management (IAM) requirements (hard)

* All access MUST be mediated by named principals:

  * human identities (SSO-backed), and
  * service identities (service accounts/workloads).
* Shared accounts are prohibited.
* Component runtime services MUST use service identities scoped to:

  * specific planes (main vs quarantine),
  * specific datasets/streams, and
  * specific actions (read vs write vs admin).

Separation-of-duties requirements:

* The principal that **publishes** an authority surface MUST NOT be the only principal able to **approve/verify** it where verification exists (§5).
* “Break-glass” access MAY exist but MUST be time-bounded and fully audited.

### 9.4 Secrets handling (hard)

* Secrets (API keys, tokens, private keys, DB creds) MUST NOT appear:

  * in repos/specs,
  * in event payloads,
  * in logs/metrics/traces,
  * in authority surfaces that are broadly readable.
* Secrets MUST be sourced from an approved secrets mechanism (implementation-defined) and MUST support:

  * rotation,
  * revocation,
  * least-privilege scoping.

A component MUST treat any detected secret-in-payload/log as a **security defect** and MUST quarantine/reject per boundary policy.

### 9.5 Encryption requirements (hard)

* **In transit:** all network transport across trust boundaries MUST be encrypted.
* **At rest:** all persisted shared-plane datasets/streams/bundles MUST be encrypted.
* Key management MUST be external to application code (implementation-defined), and access to decrypt MUST be least-privileged.

Where feasible:

* RESTRICTED data SHOULD use separate keys/scopes from INTERNAL/CONFIDENTIAL.

### 9.6 Tokenisation / pseudonymisation (pinned posture)

The platform MUST prefer **tokens** over raw identifiers wherever an identifier could be sensitive in a production setting.

Rules:

* Events and shared-plane surfaces MUST NOT expose raw PII-like fields by default.
* If a domain requires entities like “customer”, “account”, “device”, “merchant” identifiers, they MUST be represented as:

  * synthetic stable IDs, or
  * tokens derived via an approved tokenisation scheme.
* Any mapping from token → underlying raw value (if it exists at all) MUST be treated as **RESTRICTED** and placed behind strict access controls.

### 9.7 Access logging and auditability (hard)

For any access to CONFIDENTIAL or RESTRICTED objects, the platform MUST be able to audit:

* who/what accessed it (`principal_id`),
* what was accessed (`target_ref` + classification),
* when it was accessed (UTC),
* why it was accessed (request context / job/run reference where applicable),
* what action occurred (read/write/delete/admin).

Audit logs are authority surfaces and MUST follow §4 immutability rules.

### 9.8 Plane isolation (main vs quarantine) (hard)

The platform MUST maintain at least two trust planes:

* **Main plane**: PASS-verified, consumable surfaces/streams.
* **Quarantine plane**: failed validation, failed gate, or suspicious content.

Rules:

* Normal consumers MUST NOT read from quarantine by default.
* Promotion from quarantine → main MUST be explicit, receipted, and auditable (§8).
* Quarantine contents MUST be access-restricted and retained only as long as necessary for inspection.

### 9.9 Retention, deletion, and minimisation (hard)

* Every authority surface family and stream MUST define a retention policy (time or volume based).
* RESTRICTED artefacts MUST have the shortest feasible retention.
* Deletion/expiration mechanisms MUST be auditable (a deletion action MUST produce a receipt or audit record).
* Components MUST NOT create “shadow copies” of sensitive/shared-plane data outside governed storage.

### 9.10 Safe logging rules (hard)

* Logs MUST NOT contain secrets.
* Logs MUST NOT contain raw sensitive identifiers unless explicitly authorised and classified RESTRICTED.
* Logs SHOULD reference objects via canonical identity (§3) and `event_id`/`target_ref`, not by embedding sensitive payload excerpts.
* Debug dumps of full payloads to logs are prohibited on shared runtimes.

### 9.11 Prohibited patterns (explicit)

A component MUST NOT:

* hardcode credentials or embed them in configs committed to VCS,
* use shared user accounts or unmanaged service identities,
* bypass gate/receipt checks to access quarantined or ungated data (§5),
* copy shared-plane data to unmanaged locations (local disks, personal devices, ad-hoc buckets),
* emit sensitive payload fields into envelopes/extensions to “make debugging easier”,
* rely on obscurity (hidden paths) instead of access control and audit.

### 9.12 Minimum compliance statement (required in every component spec)

Every component spec under `docs/model_spec/**` MUST include a brief “Security & privacy compliance” subsection stating:

* what classifications it produces/consumes,
* which principals access which planes,
* where it might handle RESTRICTED data (if at all),
* and how it prevents secrets/PII leakage in events and logs.

---

## 10. Observability, SLOs, and degrade ladder (Binding)

### 10.1 Definitions (canonical)

* **Observability**: the ability to explain, from emitted telemetry, what happened, why it happened, and what inputs/identities it involved.
* **Telemetry**: logs, metrics, traces, and structured audit/receipt records produced by components.
* **SLO** (Service Level Objective): a target for a measured service behaviour over a defined window (availability, latency, correctness, freshness, etc.).
* **SLI** (Service Level Indicator): the measured metric used to evaluate an SLO.
* **Degrade ladder**: an explicitly ordered set of permitted fallback behaviours a component may enter when dependencies fail or SLOs are violated.
* **Degraded output**: any output produced while not operating in the component’s normal mode.

### 10.2 Universal observability requirement (hard)

Every component MUST produce telemetry sufficient to support:

1. **Audit**: what exact inputs and gates were relied on, and what outputs were produced.
2. **Replay debugging**: which world/run identities were involved, and which path (normal vs degraded) executed.
3. **Operational triage**: what failed, where, and with what reason codes.

If a component claims “auditable” or “replayable,” then the corresponding telemetry becomes an authority surface and MUST follow §4 immutability rules (no silent edits, pinnable references).

### 10.3 Identity propagation in telemetry (minimum requirements)

Telemetry emitted by components MUST include canonical identity fields whenever it pertains to a specific run/world:

* `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`
* `seed` where stochastic behaviour affects outcomes
* For event-related telemetry: `event_id` and `event_type` where applicable
* For surface-related telemetry: `target_ref` and (where applicable) `target_digest`

Correlation/tracing identifiers (`correlation_id`, `trace_id`, `span_id`) MAY be used, but MUST NOT substitute for canonical identity.

### 10.4 Minimum telemetry types (required)

Each component MUST emit, at minimum:

1. **Structured logs** (machine-parsable fields, not only human text)
2. **Metrics** (counters/gauges/histograms sufficient for SLO evaluation)
3. **Traces** (or equivalent execution linkage) for cross-component latency attribution **where the platform supports it**
4. **Receipts** at boundaries and gates, as required by §5 and §8

A component MAY implement these using any tooling, but the logical information requirements are binding.

### 10.5 Golden signals (minimum required signals)

Every component that participates in the runtime loop (ingestion, features, decisioning, actioning, labelling, etc.) MUST expose SLIs covering the following classes:

1. **Availability / success**

* request/job success rate
* boundary acceptance rate (where applicable)
* gate verification success rate (where applicable)

2. **Latency**

* end-to-end latency for its primary operation (per request / per batch / per partition)
* dependency latency (time spent waiting on upstream dependencies)

3. **Errors**

* error rate by reason code class (schema failures, missing PASS, conflicts, timeouts, internal exceptions)
* quarantine/reject counts (where applicable)

4. **Saturation / capacity**

* queue depth / backlog / lag (where applicable)
* resource saturation indicators (implementation-defined)

5. **Data correctness / integrity (where applicable)**

* schema validation failures
* hash/digest mismatches
* PASS verification failures
* idempotency conflicts detected (per §8.7)

6. **Freshness (where applicable)**

* staleness of “last good” authoritative surfaces used
* age of the most recent accepted input for a run/partition

If a component cannot measure one of these classes, it MUST state so explicitly in its spec and justify why it is not applicable.

### 10.6 Minimum SLO set (platform-wide expectation)

Exact thresholds are component-owned, but each applicable component MUST define SLOs for:

* **Availability** (or success rate) of its primary operation
* **Latency** of its primary operation (p50/p95 or equivalent)
* **Correctness at boundaries** (schema validation success, PASS compliance)
* **Backlog/lag** (if it has queues/streams)
* **Freshness** (if it uses cached/authority surfaces)

SLO definitions MUST include:

* the SLI definition,
* measurement window (e.g., 5m, 1h, 24h),
* target value,
* what constitutes a breach,
* and the required degrade behaviour (see §10.8–§10.10) if a breach is actionable.

### 10.7 Required error taxonomy alignment

Where components emit reason codes (logs/metrics/receipts), they MUST support at least these high-level reason code classes:

* `SCHEMA_INVALID`
* `SCHEMA_REF_MISSING_OR_UNRESOLVABLE`
* `IDENTITY_MISSING_OR_INVALID`
* `PASS_MISSING_OR_INVALID`
* `INTEGRITY_DIGEST_MISMATCH`
* `IDEMPOTENCY_CONFLICT`
* `DEPENDENCY_TIMEOUT_OR_UNAVAILABLE`
* `CAPACITY_OR_RATE_LIMIT`
* `INTERNAL_ERROR`

Components MAY add finer-grained reason codes but MUST map them into these classes for platform-wide triage.

### 10.8 Degrade ladder framework (hard)

Any component that can degrade MUST define a **degrade ladder** in its own spec that:

* is explicitly ordered (Mode 0 → Mode N),
* defines entry conditions per mode,
* defines exit conditions per mode,
* defines what inputs are permitted in each mode,
* and defines what outputs must be marked as degraded.

A component MUST NOT degrade in a way that violates other rails. In particular:

* Degrade MUST NOT be used to consume ungated targets (see §5.6).
* Degrade MUST NOT bypass schema validation at boundaries (see §6.6).
* Degrade MUST NOT weaken idempotency/receipt requirements (see §8).

### 10.9 Canonical degrade modes (platform vocabulary)

Components MAY define their own modes, but any mode they define MUST map to one of the following canonical categories:

* **NORMAL**: full functionality, all required dependencies satisfied.
* **REDUCED_FUNCTION**: still correct, but fewer capabilities (e.g., skip non-critical enrichments).
* **STALE_ALLOWED**: use explicitly pinned “last known good” authoritative surfaces or cached outputs, within declared freshness bounds.
* **RULES_ONLY / GUARDRAILS_ONLY**: bypass learned/scored components while maintaining conservative safety rules (component-defined).
* **FAIL_CLOSED**: refuse to produce the primary output (or produce only refusal outcomes) because correctness/safety cannot be guaranteed.

A component spec MUST declare which of these categories it supports and in what order it may transition.

### 10.10 Degrade triggers (minimum required triggers)

A component MUST enter an appropriate degrade mode when any of the following occur and normal operation would otherwise violate rails:

* Required upstream **PASS** is missing/invalid for a required target (§5)
* Required schema validation cannot be performed (missing/unresolvable `schema_ref`, validation failure) (§6)
* Idempotency conflict detected at a side-effect boundary (§8)
* Dependency outage/timeout that prevents required authoritative input consumption
* SLO breach that the component defines as actionable for degrade (per §10.6)

A component MUST NOT silently “keep going” in NORMAL mode under these conditions.

### 10.11 Mandatory degraded output marking (hard)

Any output produced in a degraded mode MUST be marked so downstream consumers and auditors can tell.

For events, this MUST be expressed using canonical keys under the envelope `extensions` object (§7.4.8). The following extension keys are **reserved and canonical** when degrade applies:

* `platform.degraded` = true
* `platform.degrade_mode` = one of the canonical categories (§10.9) or a component-mapped value
* `platform.degrade_reason_codes` = list of reason codes (aligned to §10.7 classes)
* `platform.last_good_ref` (optional) = reference to the last-known-good surface/receipt used (if stale/cached behaviour occurred)
* `platform.degrade_entered_at` (optional) = UTC timestamp

For non-event artefacts/surfaces, the same marking MUST exist in provenance metadata or the bundle manifest.

### 10.12 Degrade receipts (required for boundary-affecting degrade)

If degrade changes boundary outcomes or side effects (e.g., refusing transactions, suppressing actions, bypassing a stage), the component MUST emit a durable record (receipt or audit event) that includes:

* canonical identity tuple (§3),
* degrade mode and reason codes,
* what was suppressed/refused/altered,
* and references to the triggering failures (e.g., missing PASS ref, dependency timeout details).

### 10.13 Prohibited patterns (explicit)

A component MUST NOT:

* claim NORMAL operation while using stale/partial/ungated inputs,
* degrade by consuming quarantine-plane data as if it were main-plane data,
* degrade by disabling schema validation or PASS verification,
* hide degrade from downstream (no unmarked degraded outputs),
* use “best effort” heuristics (e.g., “latest folder”) as a degrade strategy unless explicitly governed as a pinned pointer surface (§4.6).

### 10.14 Minimum compliance statement (required in every component spec)

Every component spec under `docs/model_spec/**` MUST include an “Observability & degrade” subsection stating:

* the SLIs/SLOs it exposes (or why not applicable),
* the degrade ladder modes it supports (mapped to §10.9),
* the triggers for entering/exiting each mode,
* how degraded outputs are marked (including the canonical extension keys),
* and what receipts/audit records it emits when degrade affects boundary outcomes.

---

## 11. Governance and change management (Binding)

### 11.1 Governance objectives (hard)

Rails exist to be **stable, small, and globally trusted**. Therefore governance MUST ensure:

* changes are intentional and reviewable,
* compatibility impact is understood before merge,
* rollouts are auditable and do not silently break components,
* “temporary hacks” do not become permanent, undocumented rails drift.

### 11.2 Ownership and decision authority (hard)

* Rails MUST have an explicitly named **Owner** (team/role) in the Front matter.
* The Owner is accountable for:

  * approving binding changes,
  * enforcing versioning discipline,
  * maintaining contract authority files under `cross_cutting_rails/contracts/`,
  * ensuring platform-wide communication of breaking changes.

No component team may unilaterally change Rails without the Owner’s approval.

### 11.3 Versioning rules for rails (pinned)

Rails use `vMAJOR.MINOR` as declared in Front matter.

* **MAJOR** MUST increment when:

  * any MUST/MUST NOT requirement changes meaning,
  * any canonical field name/semantics changes,
  * refusal semantics change (e.g., missing PASS handling),
  * any pinned contract changes in a breaking way,
  * any externally referenced anchor/section is removed or meaningfully repurposed.

* **MINOR** MAY increment when:

  * adding new requirements that are additive and do not break existing compliant components,
  * clarifying language without changing required behaviour,
  * adding new optional fields/extension keys (without changing existing semantics).

A change MUST NOT be merged without the appropriate version bump.

### 11.4 Change proposal requirements (hard)

Any proposed Rails change MUST include, at minimum:

1. **Problem statement** (what breaks without this change)
2. **Proposed change** (what text/contracts change)
3. **Compatibility assessment**:

   * which components are affected,
   * whether the change is breaking,
   * how consumers/producers migrate.
4. **Validation plan**:

   * how conformance will be checked (schema updates, boundary tests, receipts).
5. **Rollout plan** (if breaking or operationally sensitive)

If any of the above is missing, the change MUST be treated as incomplete and MUST NOT be approved.

### 11.5 Review and approval workflow (hard)

* All binding Rails changes MUST be reviewed and approved by:

  * the Rails Owner, and
  * at least one reviewer from a boundary-critical domain (e.g., ingestion/decision/audit) when the change touches envelopes, receipts, PASS semantics, or schema rules.

* The approval record MUST be traceable (e.g., PR review history).

### 11.6 Contract change discipline (hard)

When a Rails change affects machine-checkable structure/validation:

* The corresponding authoritative contract(s) in `cross_cutting_rails/contracts/` MUST be updated in the same change.
* Any updated contract MUST remain **pinnable and immutable per version**:

  * a new versioned schema MUST be introduced for breaking changes,
  * the previous version MUST remain available for the migration window.

Docs-only changes MUST NOT silently change machine validation expectations.

### 11.7 Migration and deprecation requirements (hard)

For any **MAJOR** Rails change:

* A migration strategy MUST be defined, using one (or more) of:

  * **dual-publish** (old + new in parallel),
  * **translation boundary** (explicit adapter with receipts),
  * **coordinated cutover** (time-bounded, explicitly governed).

* A deprecation window MUST be declared:

  * start date,
  * end date,
  * what happens at end (refusal/quarantine/fail-closed).

Consumers MUST NOT be forced to infer breaking changes implicitly.

### 11.8 Effective date and enforcement (hard)

* Every Rails version MUST declare an **Effective date**.
* Boundaries that validate envelopes/schemas/receipts MUST enforce the Rails version(s) declared as ACTIVE after their effective dates.
* If multiple Rails versions are supported during migration, the supported set MUST be explicitly declared (e.g., “supports v2.x and v3.x during window”).

### 11.9 Emergency changes (controlled, still auditable)

Emergency changes are permitted only to address critical correctness/security failures.

Rules:

* An emergency change MUST still:

  * bump version appropriately,
  * include a minimal compatibility assessment,
  * be reviewed by the Rails Owner (at minimum),
  * produce an auditable record of why standard process was expedited.

“Emergency” MUST NOT be used to bypass governance for convenience.

### 11.10 Waivers and exceptions (strictly controlled)

Local component waivers are prohibited unless issued via this mechanism.

A waiver MAY be granted only if all conditions hold:

* It is time-bounded (explicit expiry date).
* It is scoped (which requirement is waived, for which component(s), for which planes).
* It includes compensating controls (what prevents harm during waiver).
* It is auditable (who approved, why, and link to tracking issue).

A waiver MUST NOT waive:

* canonical identity presence/immutability requirements (§3),
* “no PASS → no read” for gated targets (§5),
* schema authority requirements at boundaries (§6),
* idempotency conflict refusal (§8),
  unless the waiver explicitly forces **FAIL_CLOSED** behaviour (i.e., refusal rather than weaker acceptance).

### 11.11 Required documentation of changes (hard)

Every Rails change MUST update:

* Front matter version + last-updated timestamp, and
* a change record (either a `CHANGELOG.md` or a consistent “Change log” section).

Each change record MUST include:

* version,
* date,
* summary,
* breaking vs non-breaking flag,
* migration notes (if breaking).

### 11.12 Component pinning requirement (hard)

Every component spec under `docs/model_spec/**` MUST declare:

* which Rails version(s) it is compliant with, and
* whether it requires any active waivers.

A component MUST NOT claim compliance with an ACTIVE Rails version if it relies on behaviour that Rails prohibits.

### 11.13 Prohibited patterns (explicit)

Rails governance MUST NOT allow:

* silent breaking changes under a MINOR bump,
* removing or repurposing referenced anchors without MAJOR bump + migration,
* “latest-only” behaviour that prevents deterministic replay,
* undocumented waivers,
* contract drift (docs say one thing, validators enforce another) without versioned schema updates.

---

## 12. Conformance and testability (Binding)

### 12.1 What “conformance” means (canonical)

A component is **Rails-conformant** if, at every boundary it owns or participates in, it can be shown (by machine-checkable tests and durable receipts) that it:

* emits/accepts canonical identity and lineage correctly (§3),
* enforces PASS/no-read where required (§5),
* validates and emits `schema_ref` correctly (§6),
* emits the canonical envelope correctly (§7),
* enforces idempotency/conflict rules and emits receipts (§8),
* follows privacy/security posture constraints (§9),
* marks and records degraded operation when applicable (§10),
* and does not override Rails (§2.4).

“Conformance” is not a statement of intent; it is **demonstrable behaviour**.

### 12.2 Mandatory conformance artefacts per component spec (required)

Every component spec under `docs/model_spec/**` MUST include (at minimum) a **Conformance** section containing:

1. **Rails compliance matrix**
   A list of applicable Rails sections with a short statement of how the component satisfies each.

2. **Boundary inventory**
   A precise list of all boundaries the component owns, including:

   * what it accepts/emits (event types / surfaces),
   * which planes it touches (main/quarantine),
   * and what receipts it issues.

3. **Contract references (authoritative)**
   Explicit references to:

   * the Rails envelope schema,
   * any Rails receipt schemas it uses,
   * and the component’s own payload schemas.

4. **Degrade ladder declaration** (if applicable)
   The modes supported, triggers, and degraded output markings required by §10.

If any of these artefacts is missing, the component is not considered integration-ready.

### 12.3 Minimum conformance checks (must be testable)

Each component MUST be testable against the following minimum checks wherever they apply:

#### 12.3.1 Identity and lineage checks (required where objects cross boundaries)

* Reject/quarantine when any required identity field is missing/invalid:

  * `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id` (and `seed` where applicable)
* Ensure identity fields are treated as immutable (no rewriting/normalising).

#### 12.3.2 Envelope checks (required for events)

* Validate that emitted events conform to the canonical envelope schema.
* Reject/quarantine events missing:

  * `event_id`, `event_type`, required timestamps, `schema_ref`, canonical identity.

#### 12.3.3 Schema authority checks (required at plane entry boundaries)

* Validate that `schema_ref` resolves deterministically and validation is applied.
* Ensure boundary behaviour is correct on schema failure:

  * receipt emitted,
  * outcome recorded,
  * event/surface not admitted to main plane.

#### 12.3.4 PASS/no-read checks (required where gated targets exist)

* Demonstrate refusal behaviour when PASS is missing/invalid.
* Demonstrate successful consumption only when PASS is present and bound to the exact target instance.
* Demonstrate that consumers record which PASS/receipt justified consumption.

#### 12.3.5 Receipt checks (required at all boundaries)

* For every accept/reject/quarantine outcome, a receipt MUST be emitted with:

  * identity tuple (§3),
  * target binding (`target_ref` + digest binding where applicable),
  * outcome + reason codes on failure.
* Receipts must be immutable and pinnable (authority surface rules apply).

#### 12.3.6 Idempotency and conflict checks (required where duplicates may occur)

* Duplicate submission produces no duplicate side-effects and results in:

  * the same receipt, or a receipt that links to the prior receipt.
* Conflict submission (same idempotency key, different content/identity) results in:

  * reject/quarantine,
  * a receipt that records conflict reason codes and binding details.

#### 12.3.7 Quarantine isolation checks (required where quarantine exists)

* Quarantined objects do not become consumable by normal consumers.
* Promotion (if supported) requires explicit, receipted, auditable action.

### 12.4 Test vectors and fixtures (required)

For each boundary, a component MUST provide (or be able to derive) a minimal set of test vectors covering:

* **Happy path**: valid object → accepted → receipt emitted.
* **Missing identity**: missing one required identity field → reject/quarantine → receipt emitted.
* **Missing/invalid PASS** (if gated): attempt to consume → refusal/quarantine → receipt emitted.
* **Schema invalid**: violates authoritative schema → reject/quarantine → receipt emitted.
* **Duplicate delivery**: same idempotency key, same content → idempotent handling.
* **Conflict delivery**: same idempotency key, different content → reject/quarantine.

Fixtures MUST be deterministic and MUST be versioned/pinnable (do not depend on “latest”).

### 12.5 Evidence, audit, and reproducibility requirements

Conformance evidence MUST be reproducible and attributable:

* Tests MUST emit logs/receipts that include canonical identity.
* Where applicable, conformance runs SHOULD produce a small “conformance bundle” (authority surface) containing:

  * the inputs used,
  * receipts produced,
  * and references to schemas/versions validated.

A component MUST NOT claim conformance without producing evidence that can be replayed.

### 12.6 Integration gate rule (hard)

**No conformance → no integration.**

A component MUST NOT be integrated into the platform’s main plane unless it can pass the applicable conformance checks in §12.3 for all of its declared boundaries (§12.2).

If conformance cannot be established, the component MUST operate in **FAIL_CLOSED** mode (refusal) rather than silently weakening rails.

### 12.7 Change impact and regression obligations (hard)

When a component changes a boundary contract or behaviour, it MUST:

* rerun its conformance suite,
* demonstrate that previously supported schemas/versions remain supported for the declared migration window,
* and update its conformance section if any rails mapping changes.

When Rails contracts change (MAJOR/MINOR), affected components MUST:

* declare which Rails versions they support (§11.12),
* and update tests to cover both old/new versions during migration if dual-support is required.

### 12.8 Prohibited patterns (explicit)

A component MUST NOT:

* declare compliance without boundary-level testability,
* rely on manual inspection instead of receipts/validators for boundary correctness,
* treat conformance as “best effort” while still operating in main plane,
* accept ungated/invalid inputs and “fix them up” in processing,
* bypass quarantine isolation in tests or in production behaviour.

---

## 13. Cross-component touchpoints map (Informative)

### 13.1 The “happy path” spine (day-in-the-life)

A minimal end-to-end run typically looks like:

`Scenario Runner` → `Data Engine` → `Ingestion Gate` → `Event Bus / Landing Plane` → `Online Feature Plane` → `Decision Fabric` → `Actioning` → `Label & Case` → `Learning & Evolution` → `Observability & Governance`

Everything riding that spine is expected to carry the canonical identity tuple and be auditable via receipts/gates.

---

### 13.2 Touchpoints by component (what touches what)

For each component, this lists the main boundary touchpoints and the Rails sections it most directly exercises.

#### Scenario Runner

* **Consumes:** scenario definitions, authority surfaces (global + scenario-scoped)
* **Emits:** run plan / run record (scenario_id + run_id), run-scoped authority surfaces
* **Rails exercised:** §3 Identity/lineage, §4 Authority surfaces, §6 Schema authority, §8 Receipts (if boundary), §10 Observability

#### Data Engine (already specced)

* **Consumes:** pinned configs/externals, upstream PASS where applicable (engine-internal)
* **Emits:** world/run-scoped datasets + validation bundles + PASS flags
* **Rails exercised:** §3 Identity/lineage, §4 Authority surfaces, §5 HashGates, §6 Schemas, §8 Receipts (as bundles/flags), §10 Observability

#### Authority Surfaces Plane

* **Consumes:** published contracts/policies/config packs
* **Emits:** read-only pinned surfaces for all other components
* **Rails exercised:** §4 Authority surfaces + immutability, §6 Schema authority, §9 Access posture, §10 Observability

#### Ingestion Gate

* **Consumes:** engine outputs/events + required PASS proofs + schemas
* **Emits:** ACCEPT/REJECT/QUARANTINE outcomes + ingestion receipts; writes to main vs quarantine planes
* **Rails exercised:** §5 No PASS→no read enforcement, §6 Schema validation, §7 Envelope checks, §8 Idempotency/conflict, §9 Plane isolation, §10 Observability/degrade

#### Event Bus / Shared Landing Plane

* **Consumes:** accepted, envelope-valid events
* **Emits:** routed/partitioned delivery for downstream components
* **Rails exercised:** §7 Envelope (partition_key/sequence), §8 Ordering expectations + retries, §9 Access posture, §10 Telemetry (lag/backlog)

#### Online Feature Plane

* **Consumes:** accepted events + pinned feature configs + (optionally) last-known-good surfaces
* **Emits:** feature materialisations (events and/or surfaces) + receipts where boundary-like
* **Rails exercised:** §3 Identity/lineage, §5 PASS checks on required inputs, §7 Envelope, §8 Idempotency, §10 Degrade ladder (stale/skip), §9 Posture

#### Decision Fabric

* **Consumes:** features + pinned fraud policy/config + model artefacts (authority surfaces)
* **Emits:** decision events (decision + reasons + provenance) and/or action intents
* **Rails exercised:** §3 Identity/lineage, §5 PASS checks (models/policies), §7 Envelope, §8 Idempotency for side-effects, §10 Degrade ladder (rules-only/guardrails), §9 Posture

#### Actioning / Case Initiation

* **Consumes:** decisions + action policies
* **Emits:** action events / case-open events + side-effect receipts
* **Rails exercised:** §8 Side-effect idempotency + receipts (critical), §7 Envelope, §10 Degrade marking, §9 Access posture

#### Label & Case

* **Consumes:** action/case streams + outcomes + investigations (as applicable)
* **Emits:** labels + case state transitions as authority surfaces/events
* **Rails exercised:** §3 Identity/lineage, §4 Authority surfaces, §7 Envelope, §8 Receipts, §9 Access posture

#### Learning & Evolution

* **Consumes:** labelled datasets + feature/decision logs + pinned training configs
* **Emits:** new model artefacts (authority surfaces) + model validation PASS receipts
* **Rails exercised:** §4 Authority surfaces, §5 HashGates for model packs, §6 Schemas, §3 Identity, §10 Observability

#### Observability & Governance

* **Consumes:** telemetry + receipts + audit logs
* **Emits:** compliance signals, governance records, investigations
* **Rails exercised:** §10 Observability/SLOs, §11 Governance, §9 Auditability/access logging

---

### 13.3 Common “edge” touchpoints (where rails prevent drift)

* **Plane entry:** Ingestion Gate is the first hard enforcement point (schema_ref, envelope, PASS, idempotency).
* **Model/policy consumption:** Decision/learning components must treat model/policy artefacts as authority surfaces with PASS proofs.
* **Side effects:** Actioning/case creation must be receipt-driven and idempotent (no duplicate actions).
* **Degrade:** Feature/decision components may degrade, but may not consume ungated or schema-invalid inputs; degraded outputs must be marked.

---

## Appendix A. Glossary (Informative)

**Authority surface**
A persisted artefact/bundle treated as read-only truth by downstream components (schemas, policy packs, run plans, reference tables, validation bundles, receipts). Governed by §4.

**Boundary**
A trust or responsibility edge where objects move between components or planes (e.g., producer → shared plane, quarantine → main). Boundaries issue receipts and enforce validation/gates.

**Bundle manifest**
A machine-checkable inventory for a multi-object surface, listing members and their digests and enabling completeness/integrity verification.

**Canonical (field / identifier / rule)**
Pinned and non-negotiable: name and meaning must not be changed or aliased by components.

**Causation ID (`causation_id`)**
Optional envelope field referencing the `event_id` of the direct causal predecessor event.

**Classification**
Sensitivity category for objects (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED) used to control access and retention (§9).

**Component boundary**
A boundary specifically between two components, typically mediated by shared planes (event bus, landing zones) or pinned authority surfaces.

**Compatibility**
Whether producers/consumers can interoperate safely across schema versions without ambiguity or silent corruption (§6).

**Conflict**
A repeated submission that reuses an idempotency key but differs in content or pinned identity fields (must be rejected/quarantined; §8.7).

**Correlation ID (`correlation_id`)**
Optional envelope field tying a chain of events across components or within a workflow.

**Degrade ladder**
Ordered fallback modes a component may enter when dependencies fail or SLO breaches occur; outputs must be marked degraded (§10).

**Degraded output**
Any output produced outside NORMAL mode; must be explicitly marked (e.g., via `platform.degraded` keys in envelope extensions; §10.11).

**Digest**
A content-derived hash used to verify integrity and bind receipts/gates to exact content instances.

**Duplicate**
A repeated submission of the same object under the platform’s idempotency rules (must not create duplicate side-effects; §8.7.1).

**Envelope (canonical event envelope)**
Platform-owned metadata wrapper required on all shared-plane events; payload remains component-owned (§7).

**Event ID (`event_id`)**
Globally unique identifier for an event instance; primary idempotency key for events (§7, §8).

**Event type (`event_type`)**
Namespaced semantic type identifier for an event family (stable; not environment-specific) (§7).

**HashGate**
A gate that certifies completeness/integrity/policy validity for a target; produces PASS/FAIL outcomes; enforces “no PASS → no read” (§5).

**Idempotency**
Property where repeated submission of the same object yields the same boundary outcome and no duplicate side-effects (§8).

**Ingestion Gate**
Boundary component that validates schema/envelope/identity and enforces gates before admitting objects into the main plane (§5–§8).

**Ingestion receipt**
Authority-surface record capturing ACCEPTED/REJECTED/QUARANTINED outcome for a boundary admission decision (§8.5).

**Lineage**
Auditable record of what authoritative inputs were consumed and what gates/receipts justified that consumption (§3, §4, §5).

**Main plane**
Consumable plane containing validated/gated objects. Normal consumers read here by default (§9.8).

**Manifest fingerprint (`manifest_fingerprint`)**
Pinned identifier for the materialised world-manifest instance; used in storage addressing token `fingerprint={manifest_fingerprint}` (§3.2, §3.4).

**“No PASS → no read”**
Universal refusal rule: gated targets missing valid PASS are treated as non-consumable (§5.6).

**Occurred-at (`occurred_at`)**
Envelope timestamp representing domain/business-time of an event (§7.5).

**Parameter hash (`parameter_hash`)**
Pinned identifier for the declared world-defining parameters/config; part of world identity (§3.2).

**Partition key (`partition_key`)**
Routing/partitioning key for the event bus/storage; stable grouping semantics declared by producer (§7.4.6).

**PASS marker / PASS receipt**
Artefacts indicating a HashGate succeeded and binding that success to an exact target instance (§5.3–§5.4).

**Plane**
A trust or handling domain for data (main vs quarantine; potentially others). Planes enforce different access/validation policies (§9.8).

**Producer**
Component that emits an event/surface and is responsible for correct envelope/schema identity and gate artefacts (where required).

**Quarantine**
Isolated plane for failed/ungated/suspicious objects not admitted into main plane; access-restricted and auditable (§9.8).

**Receipt**
Durable, authoritative record of a boundary decision or verification outcome; treated as an authority surface (§8).

**Run ID (`run_id`)**
Identifier for a single execution instance; part of run identity (§3.2).

**Scenario ID (`scenario_id`)**
Identifier for a scenario definition/run plan; part of run identity (§3.2).

**Schema authority**
Rule that authoritative schemas (JSON-Schema) define validation at boundaries; docs/examples are not authoritative (§6.2).

**Schema reference (`schema_ref`)**
Pinned reference identifying the exact authoritative schema version governing an object (§6.3–§6.5).

**Seed (`seed`)**
Declared RNG identity used when stochasticity affects outputs; must be present on stochastic outputs and related receipts (§3.2.3).

**Sequence (`sequence`)**
Optional monotonic ordering indicator within a partition; only relied upon if explicitly defined and preserved (§7.4.6, §8.8).

**SLA / SLO / SLI**
Service level agreement/objective/indicator; used to define operational targets and degrade triggers (§10).

**Target ref (`target_ref`)**
Receipt/gate reference to the exact object/stream checkpoint being validated or admitted (§5, §8).

**Verification receipt**
Receipt capturing the outcome of verifying a HashGate or other validation required before consumption (§5, §8).

**World identity**
Tuple `(parameter_hash, manifest_fingerprint)` defining the world being generated (§3.2.1).

---

## Appendix B. Examples (Informative)

### B.1 Example: canonical event envelope (NORMAL)

Example of a shared-plane event emitted by a component (payload is illustrative only):

```json
{
  "event_id": "evt_01JHNHK3R8M9QZ8F2S5D7E1B4C",
  "event_type": "decision.emitted",
  "producer_id": "decision_fabric",
  "producer_version": "2025.12.31+build.1842",
  "occurred_at": "2025-12-31T16:55:12Z",
  "emitted_at": "2025-12-31T16:55:12Z",
  "ingested_at": null,

  "schema_ref": "docs/model_spec/real_time_decision_loop/decision_fabric/contracts/decision_emitted.event.schema.yaml#v1.0",

  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",

  "partition_key": "account:acct_tok_9f21b8",
  "sequence": 14021,

  "correlation_id": "corr_01JHNHK1EJ7D9K0A2X4C3PZQ8M",
  "causation_id": "evt_01JHNHK0V2R2K8R3Y9T8D6A1BC",

  "extensions": {
    "platform.degraded": false
  },

  "payload": {
    "decision_id": "dec_01JHNHK3QW5M6Y2ZK9",
    "entity_type": "transaction",
    "entity_id": "txn_tok_5a8c1e",
    "decision": "DECLINE",
    "reasons": [
      {"code": "RULE.VELOCITY_SPIKE", "weight": 0.62},
      {"code": "MODEL.RISK_HIGH", "weight": 0.31}
    ]
  }
}
```

---

### B.2 Example: canonical event envelope (DEGRADED: STALE_ALLOWED)

Example where a component degrades (e.g., dependency outage) and uses last-known-good surfaces. Note the canonical `platform.*` keys:

```json
{
  "event_id": "evt_01JHNHN9Q0ZP7K2X4F8B1A6C3D",
  "event_type": "feature.vector.materialised",
  "producer_id": "online_feature_plane",
  "producer_version": "2025.12.31+build.771",
  "occurred_at": "2025-12-31T16:56:03Z",
  "emitted_at": "2025-12-31T16:56:03Z",
  "ingested_at": null,

  "schema_ref": "docs/model_spec/real_time_decision_loop/feature_plane/contracts/feature_vector.event.schema.yaml#v2.2",

  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",

  "partition_key": "account:acct_tok_9f21b8",
  "sequence": 14022,

  "extensions": {
    "platform.degraded": true,
    "platform.degrade_mode": "STALE_ALLOWED",
    "platform.degrade_reason_codes": ["DEPENDENCY_TIMEOUT_OR_UNAVAILABLE", "FRESHNESS_RISK"],
    "platform.last_good_ref": "authority://features/last_good/fingerprint=mf_2d4a0b8c6e19.../run_id=run_20251231T165500Z_9b3f/feature_cache_manifest@sha256:ab12...",
    "platform.degrade_entered_at": "2025-12-31T16:55:58Z"
  },

  "payload": {
    "entity_type": "transaction",
    "entity_id": "txn_tok_5a8c1e",
    "feature_vector": {"f_001": 0.12, "f_002": 7.0, "f_003": 1},
    "feature_version": "fv_2025-12-31"
  }
}
```

---

### B.3 Example: ingestion receipt (ACCEPTED)

Boundary receipt emitted by the Ingestion Gate after validating envelope + schema + identity + any required upstream PASS:

```json
{
  "receipt_id": "rcpt_01JHNHK5ZP8Y6R1W3Q9T4B2C7D",
  "receipt_type": "ingestion",
  "issued_at": "2025-12-31T16:55:13Z",

  "issuer_id": "ingestion_gate",
  "issuer_version": "2025.12.31+build.102",

  "target_ref": "bus://main/events/decision.emitted/partition=account:acct_tok_9f21b8/offset=883201",
  "target_identity": {"event_id": "evt_01JHNHK3R8M9QZ8F2S5D7E1B4C"},
  "target_digest": "sha256:5d1b2f8c...",

  "schema_ref": "docs/model_spec/control_and_ingress/ingestion_gate/contracts/ingestion_receipt.schema.yaml#v1.0",
  "validated_schema_ref": "docs/model_spec/real_time_decision_loop/decision_fabric/contracts/decision_emitted.event.schema.yaml#v1.0",

  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",

  "outcome": "ACCEPTED",
  "reason_codes": []
}
```

---

### B.4 Example: ingestion receipt (QUARANTINED due to schema failure)

Illustrative refusal outcome showing reason codes:

```json
{
  "receipt_id": "rcpt_01JHNHM0H7D3X9K1P2Q8R6S5T4",
  "receipt_type": "ingestion",
  "issued_at": "2025-12-31T16:55:44Z",

  "issuer_id": "ingestion_gate",
  "issuer_version": "2025.12.31+build.102",

  "target_ref": "landing://quarantine/events/feature.vector.materialised/blob=.../attempt=1",
  "target_identity": {"event_id": "evt_01JHNHM0A1B2C3D4E5F6G7H8I9"},
  "target_digest": "sha256:9a88d1e0...",

  "schema_ref": "docs/model_spec/control_and_ingress/ingestion_gate/contracts/ingestion_receipt.schema.yaml#v1.0",
  "validated_schema_ref": "docs/model_spec/real_time_decision_loop/feature_plane/contracts/feature_vector.event.schema.yaml#v2.2",

  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",

  "outcome": "QUARANTINED",
  "reason_codes": ["SCHEMA_INVALID", "SCHEMA_VALIDATION_FAILED"]
}
```

---

### B.5 Example: HashGate bundle layout (PASS) under `fingerprint={manifest_fingerprint}`

Illustrative persisted bundle gated by a HashGate (files and names are examples; the key idea is: manifest + receipt + PASS marker, bound to the exact instance).

```
.../validation/fingerprint={manifest_fingerprint}/run_id={run_id}/
  bundle_manifest.json
  hashgate_receipt.json
  _passed.flag
  index.json
  parts/
    part-0000.parquet
    part-0001.parquet
```

Example `bundle_manifest.json` (informative shape):

```json
{
  "bundle_ref": "validation/fingerprint=mf_2d4a0b8c6e19.../run_id=run_20251231T165500Z_9b3f",
  "digest_alg": "sha256",
  "members": [
    {"path": "index.json", "digest": "sha256:1111..."},
    {"path": "parts/part-0000.parquet", "digest": "sha256:2222..."},
    {"path": "parts/part-0001.parquet", "digest": "sha256:3333..."}
  ]
}
```

Example `hashgate_receipt.json` (informative shape; aligns with §5.10 minimums):

```json
{
  "gate_outcome": "PASS",
  "validator_id": "engine_validation",
  "validator_version": "2025.12.31+build.9001",
  "verified_at": "2025-12-31T16:54:59Z",
  "target_ref": "validation/fingerprint=mf_2d4a0b8c6e19.../run_id=run_20251231T165500Z_9b3f",
  "target_digest": "sha256:ab12...",
  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",
  "reason_codes": []
}
```

---

### B.6 Example: HashGate FAIL receipt (informative)

```json
{
  "gate_outcome": "FAIL",
  "validator_id": "engine_validation",
  "validator_version": "2025.12.31+build.9001",
  "verified_at": "2025-12-31T16:54:10Z",
  "target_ref": "validation/fingerprint=mf_2d4a0b8c6e19.../run_id=run_20251231T165500Z_9b3f",
  "target_digest": "sha256:ab12...",
  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",
  "reason_codes": ["INTEGRITY_DIGEST_MISMATCH", "SCHEMA_INVALID"]
}
```

---

### B.7 Example: idempotency conflict (same `event_id`, different `target_digest`) (Informative)

Scenario: the boundary has already accepted an event with `event_id = evt_...`, and later receives **another** submission reusing the *same* `event_id` but with **different content** (so the computed `target_digest` differs). Per §8.7.2, this MUST be refused (REJECTED or QUARANTINED) and must record the conflict details.

```json
{
  "receipt_id": "rcpt_01JHNK1C0Z6V9M2R8T3Q7W1E5A",
  "receipt_type": "ingestion",
  "issued_at": "2025-12-31T17:02:10Z",

  "issuer_id": "ingestion_gate",
  "issuer_version": "2025.12.31+build.102",

  "target_ref": "landing://main/events/decision.emitted/blob=.../attempt=2",
  "target_identity": {
    "event_id": "evt_01JHNHK3R8M9QZ8F2S5D7E1B4C"
  },

  "target_digest": "sha256:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",

  "schema_ref": "docs/model_spec/control_and_ingress/ingestion_gate/contracts/ingestion_receipt.schema.yaml#v1.0",
  "validated_schema_ref": "docs/model_spec/real_time_decision_loop/decision_fabric/contracts/decision_emitted.event.schema.yaml#v1.0",

  "parameter_hash": "ph_7f3c9a4b1d2e...",
  "manifest_fingerprint": "mf_2d4a0b8c6e19...",
  "scenario_id": "scn_retail_day_v3",
  "run_id": "run_20251231T165500Z_9b3f",
  "seed": "seed_0000000000000042",

  "outcome": "REJECTED",
  "reason_codes": [
    "IDEMPOTENCY_CONFLICT",
    "EVENT_ID_REUSE_WITH_DIFFERENT_DIGEST"
  ],

  "conflict": {
    "conflict_key": "event_id",
    "conflict_value": "evt_01JHNHK3R8M9QZ8F2S5D7E1B4C",

    "existing_target_ref": "bus://main/events/decision.emitted/partition=account:acct_tok_9f21b8/offset=883201",
    "existing_target_digest": "sha256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",

    "existing_receipt_id": "rcpt_01JHNHK5ZP8Y6R1W3Q9T4B2C7D",
    "notes": "Same event_id previously ACCEPTED, but new submission differs in content digest; last-write-wins is prohibited."
  }
}
```

---