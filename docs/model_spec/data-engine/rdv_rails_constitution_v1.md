# RDV Rails Constitution (v1) — Section Header Plan

## 0) Document metadata (Informative)

### 0.1 Document identity

* **Title:** RDV Rails Constitution (Reproducibility, Determinism, Validation)
* **Doc ID:** `rdv_rails_constitution_v1`
* **Status:** Draft (v0-thin → v1)
* **Version:** 1.0.0 (target), currently 0.1.0 (draft)
* **Last updated:** 2026-01-09
* **Owner (Designer):** Platform Spec Designer (you)
* **Primary implementer:** Codex (implementation agent), per your workflow convention

### 0.2 Scope tags

* **Applies to:** **All engine layers, all segments, all states** (including validators/finalizers), plus any new segments added later.
* **Governs:**

  * run anchoring + identity propagation
  * RNG governance + numeric determinism posture
  * artefact addressing + immutability + hashing
  * validation artefacts + PASS gate semantics + “no PASS → no read”
* **Does not govern:** domain realism choices (models/distributions), business semantics, or segment-specific mechanics (those live in segment/state specs).

### 0.3 Normative language and interpretation

* RFC-2119 keywords are used with their standard meaning: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.
* **Binding vs Informative:** Sections labelled **Binding** are normative; **Informative** sections provide guidance/examples only.

### 0.4 Repository placement

* **Intended repo location (conceptual):**
  `docs/model_spec/observability_and_governance/cross_cutting_rails/rdv/rdv_rails_constitution_v1.md`
* **Audience:** spec authors (engine segments), implementers, reviewers, validation/ops consumers, and any downstream component that reads engine artefacts.

### 0.5 Related specs and artefact packs

* **Segment contracts:** per-segment schemas, artefact registries, dataset dictionaries.
* **Cross-cutting rails:** identity/run anchoring rails, observability/governance rails (if separate).
* **Engine interface pack:** output catalogue + gate map surfaces used by downstream components.

### 0.6 Compatibility and change control

* **Compatibility promise:** consumers may rely only on **declared RDV surfaces** (anchors, locators, hashes, gates, validation bundles).
* **Versioning:**

  * **MAJOR**: breaking change to required fields, gate semantics, or hashing/addressing rules
  * **MINOR**: additive requirements or new optional fields/state classes
  * **PATCH**: clarifications/typos with no behavioral impact
* **Exception policy:** any state/segment exception to these rails must be explicitly declared, justified, and treated as a breaking-risk item.

### 0.7 Changelog pointer

* Maintain a short changelog at the top of this file (or a sibling `CHANGELOG.md`) recording: date, version, change summary, and impacted surfaces.

---

## 1) Purpose and scope (Binding)

### 1.1 Purpose

This document defines the **engine-wide constitution** for:

* **Reproducibility**: a run anchored by the same inputs (world manifest + parameterization + run identity) MUST reproduce the same governed artefacts (or fail deterministically and loudly).
* **Determinism**: state execution MUST be free from uncontrolled nondeterminism (ambient RNG, unstable ordering, environment-dependent numerics, time/locale dependence).
* **Validation**: every produced artefact MUST be accompanied by defined validation evidence and MUST be protected by **PASS gates** such that downstream reads are prohibited unless required gates have passed (“no PASS → no read”).

These rules apply **uniformly across all layers, all segments, and all states**, while allowing **declared variability**: different states/segments MAY have different RDV obligations (e.g., RNG-free vs RNG-consuming vs finalizer), but only within the profiles and constraints defined by this constitution.

### 1.2 Scope

This constitution governs, for every engine state:

* **Run anchoring and identity propagation**

  * Required run anchor fields and how they appear in artefacts, manifests, and validation outputs.
* **Artefact addressing and identity**

  * Canonical addressing templates, content hashing rules, immutability/atomic publish rules.
* **Deterministic execution rules**

  * RNG governance (no ambient RNG; scoped streams only), canonical ordering/tie-break rules, concurrency limits, and numeric determinism posture.
* **Validation system**

  * Validation artefact formats, required checks taxonomy, PASS gate semantics, and gate composition across states/segments.
* **Consumer obligations**

  * What downstream states/components MUST check and record when reading engine outputs (gate checks, hash checks, provenance checks).

### 1.3 Out of scope

This document does **not** define:

* Segment-specific domain logic (e.g., distribution choices, realism models, business heuristics).
* Exact artefact schemas for any one segment (these live in per-segment contracts and dictionaries).
* Scenario Runner / Ingestion Gate / downstream platform behavior, except where they must comply when **reading** engine artefacts (gate + identity adherence).

### 1.4 Intended audiences

* **Spec authors** writing or maintaining segment/state-expanded docs and contracts.
* **Implementers** building state executors, validators, and IO/RNG infrastructure.
* **Reviewers/QA** verifying conformance and change safety.
* **Downstream consumers** that read engine artefacts and must honor the gating and identity model.

### 1.5 Definition of “compliance”

A segment/state is compliant only if:

* It executes using the **shared primitives and constraints** defined here (run anchors, scoped RNG, deterministic ordering, numeric policy).
* It produces required **state manifests** and **validation evidence**.
* It enforces and participates in the **PASS gate system**, including “no PASS → no read”.
* It passes the **conformance suite** described later in this document.

---

## 2) Authority boundaries and precedence (Binding)

### 2.1 Authority boundary: what this document is

This document is the **engine-wide constitution** for **Reproducibility, Determinism, and Validation (RDV)**.

* It is **binding** on **every** layer, segment, and state.
* It defines **shared primitives** (run anchors, addressing, hashing, RNG governance, numeric policy, validation/gates) that segment/state specs MUST reuse rather than re-invent.

### 2.2 Precedence order (highest → lowest)

When requirements conflict, the following order applies:

1. **RDV Rails Constitution (this document)**
2. **Cross-cutting rails that this document explicitly depends on** (e.g., global run/identity rails, if separate)
3. **Segment binding contracts** (schemas, registries, dictionaries, validation policy artefacts)
4. **State-expanded specs** (state-by-state procedures and obligations)
5. **Implementation details** (code, tooling, runtime settings)

If a lower-precedence document conflicts with a higher-precedence document, the lower-precedence document MUST be corrected.

### 2.3 What segment/state specs are allowed to decide

Segment and state specifications MAY define:

* Domain logic (models, distributions, thresholds) **provided** all inputs are pinned and deterministically consumed.
* Which **State Class** applies (RNG-free, RNG-consuming, aggregator, validator-only, finalizer), **provided** it is declared and the class obligations are met.
* Additional validations (stronger checks are always allowed).
* Additional artefacts (provided they follow addressing, hashing, provenance, and gating rules).

They MUST NOT redefine or weaken:

* Run anchor semantics
* RNG governance (no ambient RNG; scoped streams only)
* Numeric determinism posture (unless explicitly granted as an exception)
* Gate semantics (“no PASS → no read”)
* Immutability/atomic publish requirements
* Canonical addressing and artefact identity rules

### 2.4 Enforcement boundary: mandatory shared services

To prevent “every state doing its own thing,” the engine runtime MUST provide shared services that states MUST use:

* **Addressed immutable writer** (atomic publish, no overwrite)
* **Content hashing + manifest writer** (standard output identity)
* **RNG service** (scoped deterministic streams; audit/trace)
* **Validation runner** (standard bundle output + PASS gate emission)
* **Canonical serialization utilities** (stable ordering/formatting)

States MUST NOT bypass these services (e.g., direct filesystem writes, custom RNG instantiation, ad-hoc validation outputs).

### 2.5 Exceptions and waivers (rare; strictly controlled)

Exceptions to this constitution are allowed only if all are true:

* The exception is **explicitly declared** in a binding location (segment profile or state manifest).
* The exception includes a **justification**, **risk assessment**, and **scope** (which outputs/surfaces it affects).
* The exception includes **compensating controls** (e.g., quantisation, stricter validation, reduced scope).
* The exception is treated as **breaking-risk** for consumers unless proven otherwise.

Undeclared exceptions are non-compliant.

### 2.6 Conflict resolution and change control

* Any proposal to change this constitution MUST include:

  * which public surfaces change (anchors, addressing, hashing, gates, validation formats)
  * backwards compatibility analysis
  * migration strategy (if required)
  * updated conformance tests
* Segment/state docs MUST be updated to align in the same change set (or explicitly marked incompatible with clear version pinning).

---

## 3) Terminology and key objects (Binding)

### 3.1 Normative language

* **MUST / MUST NOT / SHOULD / MAY** are to be interpreted as requirement levels.
* Terms defined in this section are **normative**: if a segment/state uses a different label for the same concept, it MUST still satisfy the definition and obligations here.

### 3.2 Identity and run anchoring objects

**Run Anchor (a.k.a. RunContext)**
The minimal set of identifiers and pins that uniquely define *what universe is being built* and *which execution instance is producing it*. A Run Anchor MUST include, at minimum:

* **`manifest_fingerprint`**: content identity of the world manifest (inputs closure).
* **`parameter_hash`**: content identity of the resolved parameter/policy bundle.
* **`scenario_id`**: scenario identity (platform-level; stable across retries where applicable).
* **`run_id`**: execution attempt identity (platform-level; may differ across retries).
* **`seed_material`**: the seed root or seed-derivation inputs governed by the RNG rail (even if a state is RNG-free).

**Segment ID / State ID**

* **`segment_id`** identifies a segment (e.g., `1A`, `6B`).
* **`state_id`** identifies a state within a segment (e.g., `S0`, `S7`).
  Both MUST be stable identifiers used in provenance, addressing, and (where applicable) RNG stream derivation.

### 3.3 Artefact identity and addressing objects

**Artefact**
A persisted output object produced by a state (dataset, config, index, report, receipt, etc.). Artefacts are *governed* objects: they MUST be addressable, hash-identifiable, and provenance-bearing.

**ArtefactRef (a.k.a. Locator)**
A structured reference to an artefact. At minimum it MUST include:

* **`kind`** (what type of artefact this is),
* **`address`** (canonical path/template resolved under run anchors),
* **`content_hash`** (hash of the artefact content, using the engine’s declared hash algorithm/version),
* **`anchors`** (run anchor fields required to interpret/verify identity).

**Canonical Address Template**
A rule for computing artefact addresses from run anchors + segment/state identity. Any segment/state-specific conventions MUST be expressible as parameters of this template (not ad-hoc new schemes).

**Content Hash**
A deterministic digest of artefact content computed under the engine’s canonical serialization rules (including ordering and numeric formatting rules). A content hash MUST be computed and recorded for every governed artefact (including validation bundles and indexes).

### 3.4 Determinism and reproducibility terms

**Determinism**
A property of execution: given identical run anchors and identical pinned inputs, the state MUST produce identical outputs (as defined by this constitution’s equality rules) without dependence on ambient randomness, unstable iteration ordering, wall-clock time, locale, or environment-specific numeric behavior.

**Reproducibility**
A property of the system across time and replays: given the same run anchors, pinned policies, pinned externals, and declared engine/rails versions, the system MUST be able to regenerate the same governed artefacts (or deterministically fail with diagnostics). Reproducibility includes determinism, plus pinning/versioning/immutability requirements.

**Equality Rule (for reproduction checks)**
The declared rule for comparing replays:

* **Byte equality** (strongest),
* **Canonical-form equality** (after canonical serialization),
* **Value equality under declared quantisation** (only where explicitly allowed).
  If a segment/state requires anything weaker than canonical-form equality, it MUST be explicitly declared and justified.

### 3.5 RNG governance objects

**RNG Policy**
The declared rules for randomness in the engine (algorithm/version, open-interval mapping rules, stream derivation scheme, logging/audit requirements). States MUST NOT override the RNG policy.

**RNG Service**
The only allowed way for a state to obtain randomness. A state MUST NOT instantiate its own RNG.

**RNG Stream**
A deterministic pseudo-random stream obtained from the RNG Service using a **Stream Key**.

**Stream Key**
A deterministic identifier used to derive an RNG stream from run anchors and execution identity. It MUST be a pure function of:

* run anchors,
* `segment_id`, `state_id`,
* a **purpose tag** (to separate independent uses within a state).

**RNG Counter / Envelope**
The accounting mechanism that makes RNG consumption replayable and auditable:

* **Counter**: the index of draws/events consumed so far in a stream.
* **Envelope**: the declared/recorded bounds and event structure for RNG usage (so validation can detect “missing”, “extra”, or reordered draws).

**RNG Trace / Audit Log**
A required record of RNG usage sufficient to support replay checks and diagnostics. Required detail level MAY vary by State Class, but RNG-consuming states MUST produce trace evidence adequate to:

* confirm the stream key(s) used,
* confirm consumption counts/events,
* support deterministic re-derivation during validation.

### 3.6 Numeric determinism objects

**Numeric Policy**
A declared set of numeric execution rules (floating-point posture, rounding expectations, reduction/aggregation ordering requirements, and quantisation hooks). States MUST comply with the numeric policy; any exception MUST be explicitly declared as an exception under the rules in §2.

**Quantisation Policy (if applicable)**
A declared rule for converting continuous values into stable discrete representations where required for determinism, auditing, or downstream contracts.

### 3.7 Validation and gating objects

**Validation**
A deterministic set of checks applied to artefacts (schema, invariants, referential integrity, realism/statistical corridors where applicable). Validation MUST be reproducible and fail-closed.

**Validation Bundle**
A governed artefact containing:

* what was validated (ArtefactRefs + hashes),
* which checks ran (policy/version),
* outcomes (pass/fail + metrics),
* diagnostics sufficient for debugging,
* provenance (run anchors + segment/state identity).

**PASS Gate (a.k.a. Pass Flag / Receipt)**
A minimal machine-checkable artefact indicating that required validation passed for a declared scope. A PASS gate MUST be:

* immutable once written,
* addressable and hash-identifiable,
* scoped (what it asserts: artefact(s), state, segment, run anchor scope).

**Gate Map**
A declared dependency rule-set stating which PASS gates are required before a consumer (downstream state, segment, or external component) may read a given artefact.

**“No PASS → No Read” rule**
A consumer MUST NOT read or act upon governed artefacts unless all required PASS gates (as per the Gate Map for that consumer) are present and valid.

### 3.8 State execution objects

**State**
A named, versioned transformation unit within a segment that consumes pinned inputs/policies (and optionally RNG streams) and produces governed outputs + required validation evidence.

**State Manifest (a.k.a. Output Manifest)**
A required governed record emitted by every state enumerating:

* inputs consumed (ArtefactRefs + hashes),
* policies/configs used (content-hash pins),
* RNG streams used (if any) and required accounting evidence,
* outputs produced (ArtefactRefs + hashes),
* validation bundles and PASS gates produced.

### 3.9 Classification objects for “states and segments differ”

**State Class**
A normative classification that determines a state’s minimum RDV obligations (e.g., RNG-free, RNG-consuming, aggregator/merge, validation-only, finalizer). Every state MUST declare exactly one State Class (or a declared composite class if supported by this constitution).

**Segment RDV Profile**
A binding declaration for a segment that:

* lists its states and their State Classes,
* declares required gates/receipts and their scopes,
* declares any additional determinism/reproducibility constraints,
* declares any approved exceptions (rare) and compensating controls.

### 3.10 Consumers

**Consumer**
Any entity that reads governed engine artefacts (another state, another segment, another layer, or an external platform component). Consumers MUST:

* enforce gate checks (“no PASS → no read”),
* verify artefact identity (hash/provenance checks as required),
* record minimal evidence of what was read (refs + hashes + gates).

---

## 4) Variability model (Binding) ✅ (this is the key to “states & segments differ”)

### 4.1 Goal of the variability model

This constitution MUST allow **legitimate RDV differences** across **states** and **segments** (e.g., RNG-free vs RNG-emitting, parameter-scoped vs fingerprint-scoped outputs, “receipt gates” vs final egress gate), **without** allowing ad-hoc drift.

Accordingly:

* **Every state MAY differ in RDV posture**, but only by selecting from **declared State Classes** and filling a **declared State RDV Profile**.
* **Every segment MAY differ in RDV posture**, but only by publishing a **Segment RDV Profile** that enumerates its states, their profiles, and their required gates.
* Anything not declared by profile is **forbidden**.

This mirrors how 1A already distinguishes parameter-scoped receipts (e.g., S5) from fingerprint-scoped egress gates (S9) while keeping one shared “no PASS → no read” story.  

---

### 4.2 Two layers of rules: invariant vs variable-by-declaration

#### 4.2.1 Invariant rules (apply everywhere; non-negotiable)

All states, regardless of segment, MUST obey:

1. **Run anchor propagation:** required lineage keys appear where required and are used only for their scoped roles (see §3).
2. **Partition law + path↔embed equality:** where a lineage value appears in both path and embedded fields, **byte-equality is mandatory**.  
3. **Write discipline:** atomic publish; immutability/idempotence per declared write semantics; no partial visibility.  
4. **No ambient nondeterminism:** no uncontrolled RNG, ordering drift, environment/time/locale dependence. (RNG governance and numeric policy are fixed rails; states only *select* a permitted posture.) 
5. **Gating:** “no PASS → no read” as defined by the Gate Map(s). Receipts and final gates are enforced mechanically, not informally. 

#### 4.2.2 Variable rules (allowed to differ; MUST be declared)

A state/segment MAY vary only in the following declared dimensions:

* **Scope & partitioning of outputs** (parameter-scoped vs run/log-scoped vs fingerprint-scoped, etc.)  
* **RNG posture** (no RNG, emits non-consuming events, emits consuming events) under the shared RNG rail.  
* **Equality contract** (byte-identical, canonical-form, row-set) as explicitly permitted and declared (never implicit).  
* **Validation posture** (what checks run; what receipts exist; what is the segment’s consumer gate).  
* **Optional convenience surfaces** and their degrade ladders (what is optional, what substitutes, and what gate must be verified if used).  

---

### 4.3 Variability axes (normative definitions)

#### 4.3.1 Output scope classes (partition identity)

Every produced artefact MUST declare exactly one **Output Scope Class**:

* **PARAMETER_SCOPED**: partitioned by `parameter_hash` (and only those keys permitted by the Dictionary for that dataset). Example pattern: S3 tables are parameter-scoped and MUST NOT be seed-partitioned. 
* **LOG_SCOPED**: partitioned for logs/events by `{seed, parameter_hash, run_id}` (and only those keys permitted by the Dictionary for that log stream).  
* **FINGERPRINT_SCOPED**: partitioned by the run’s `manifest_fingerprint` value (used for egress validation bundles and consumer gates). 
* **EGRESS_SCOPED**: consumer surfaces whose partitioning is explicitly declared in the Dictionary (often includes seed + fingerprint; never invent extra keys). 

**Rule:** A state MUST NOT place an artefact under a scope class that conflicts with its declared lineage role (e.g., `run_id` MUST NOT influence egress partitions or model state; it is log-partitioning only). 

#### 4.3.2 RNG posture (what “R” means for the state)

Every state MUST declare exactly one **RNG Posture**:

* **RNG_NONE**: state does not read or write any RNG event families or RNG logs.
* **RNG_NONCONSUMING**: state emits RNG-enveloped events that MUST be non-consuming (`before==after`, `blocks=0`, `draws="0"`) and still MUST satisfy trace-coverage rules.  
* **RNG_CONSUMING**: state emits consuming RNG events and MUST satisfy envelope budgeting laws + trace-after-each-event discipline.  

**Rule:** Regardless of posture, if a state touches RNG envelopes/logs, it MUST do so only through the shared RNG/log primitives and MUST preserve the shared invariants (open-interval uniforms, envelope arithmetic, trace pairing).  

#### 4.3.3 Deterministic ordering authority (who is allowed to define “order”)

Many segments will have *some* ordering notion (candidate ranks, tie-breakers, writer sorts). To prevent drift:

* A segment MUST declare **Order Authority Artefacts** (datasets whose ordering is authoritative for downstream interpretation).
* Any state that is **not** an order authority MUST NOT encode, persist, or imply a new competing order in its outputs.

This “order-authority separation” is enforced in 1A (e.g., S3 defines cross-country rank; S6 must not persist inter-country order; downstream joins to S3 when needed).  

#### 4.3.4 Validation and gates: receipts vs final consumer gate

Validation may exist at multiple scopes, and segments differ in how many intermediate receipts they use. The model is:

* **Receipt Gate**: a PASS artefact scoped to a subset (often parameter-scoped) used to protect downstream reads of a specific input. Example: S5 writes a parameter-scoped receipt and downstream readers MUST verify it for the same `parameter_hash` before reading.  
* **Final Consumer Gate**: the authoritative PASS artefact for segment egress consumption (often fingerprint-scoped) that downstream components MUST verify before reading consumer outputs. 

**Non-substitution law (binding):** Intermediate receipts are **additive** and MUST NOT be treated as substitutes for the final consumer gate.  

#### 4.3.5 Optional convenience surfaces and degrade ladders

Segments MAY publish optional “convenience” artefacts (e.g., cached membership tables, pre-computed counts). If a segment does so, it MUST also declare:

* **(a) Optionality:** whether the artefact may be absent without failing the run.
* **(b) Substitute source:** what authoritative source(s) to use if absent.
* **(c) Read gate:** if present and used, which receipt/gate MUST be verified first.

This pattern is explicitly used in 1A (e.g., “use membership surface only if its receipt is verified; else reconstruct from logged events”).  

---

### 4.4 State Classes (normative taxonomy)

Every state MUST declare exactly one **State Class**, which determines its minimum RDV obligations. (Details are expanded later in the Determinism/Reproducibility/Validation parts; this section fixes the model and classification.)

**SC-A: Pure Transform (RNG-free producer)**

* Primary role: deterministic transformation; produces governed artefacts under PARAMETER_SCOPED or other declared scope.
* RNG posture: **RNG_NONE**.
* MUST provide deterministic ordering rules for any ordering it introduces. 

**SC-B: RNG Emitter (produces RNG-enveloped events/log updates)**

* Primary role: emits RNG events and updates trace/audit logs under LOG_SCOPED partitioning.
* RNG posture: **RNG_NONCONSUMING** or **RNG_CONSUMING** (must be declared).
* MUST satisfy envelope budgeting, open-interval mapping rules, and trace coverage requirements.  

**SC-C: Aggregator / Reduction / Join State**

* Primary role: merges/join/reduces across artefacts; highly sensitive to ordering and determinism.
* MUST declare canonical ordering/tie-break rules and reduction order; MUST be worker-count invariant. 

**SC-D: Receipt Writer (local validation + scoped gate)**

* Primary role: validates a limited surface and publishes a scoped receipt gate (often parameter-scoped).
* MUST declare receipt scope, contents, hashing rule, atomic publish rule, and downstream gate obligations.  

**SC-E: Finalizer / Segment Egress Gate Publisher**

* Primary role: read-only verification across prior states + publish the segment’s final validation bundle and consumer gate.
* MUST be idempotent (byte-identical on replay), must publish atomically, and must enforce consumer “no PASS → no read”.  

**Rule:** A segment MAY use multiple State Classes. A segment MUST include exactly one Finalizer class state if the segment exposes consumer egress.

---

### 4.5 Segment RDV Profile (binding declaration)

Every segment MUST publish a binding **Segment RDV Profile** that:

1. Enumerates **all states** in the segment and for each state declares:

   * `state_class ∈ {SC-A,SC-B,SC-C,SC-D,SC-E}`
   * `output_scope_class`
   * `rng_posture` (and if applicable, the list of RNG families it emits)
   * declared **input gates** required before reading each governed input (“no PASS → no read”)
   * declared **output gates** it produces (receipts/bundles/flags), with scope
2. Declares the **segment’s consumer gate** (if the segment has egress) and its exact verification rule.
3. Declares any **optional convenience surfaces** and their degrade ladders (authoritative substitutes + required receipts if used). 
4. Declares the segment’s **order authorities** (if any) and the prohibition on competing order encoding by other states. 

**Non-negotiable:** The Segment RDV Profile MUST be sufficient for a validator or downstream component to determine:

* what can be read,
* under what evidence,
* and what constitutes PASS for the segment’s consumer surfaces.

---

### 4.6 Compatibility and extension rules

* A segment MUST NOT invent new State Classes or new RDV dimensions without updating this constitution.
* If a state/segment requires an exception, it MUST be declared as an exception under §2.5 and MUST include compensating controls.
* If a segment has legacy token naming or legacy path shapes, it MUST declare compatibility mapping explicitly (and it remains subject to §2 precedence + future normalization).

---

## 5) Core invariants (“laws”) (Binding)

> These invariants apply to **every** state in **every** segment in **every** layer.
> State/segment variability is allowed only via the **declared profiles** in §4 and MUST NOT violate any invariant below.

### 5.1 Single source of truth and authority

1. **Contracts are authoritative:** For any governed artefact, the authoritative definition of shape/fields is its declared **schema contract**. Any secondary format (e.g., generated Avro) MUST be treated as non-authoritative unless explicitly elevated by contract.
2. **Policies are authoritative when pinned:** Behavioural parameters MUST come only from the **resolved policy bundle** identified by `parameter_hash` (or segment-equivalent), not from implicit defaults or ambient config.
3. **No undeclared dependencies:** A state MUST NOT read any input (file, dataset, config, env var) that is not declared in its State Manifest and pinned by content identity.

### 5.2 Run anchoring and identity propagation

4. **Run anchors are mandatory:** Every state MUST execute under a Run Anchor (RunContext) that includes, at minimum, `manifest_fingerprint`, `parameter_hash`, and the run execution identifiers (e.g., `scenario_id`, `run_id`) plus seed material (even if RNG-free).
5. **Anchor roles are fixed:**

   * `manifest_fingerprint` identifies the **opened input closure** (world manifest).
   * `parameter_hash` identifies the **resolved parameter/policy closure**.
   * `run_id`/`scenario_id` identify execution lineage and MUST NOT silently change the meaning of deterministic model outputs unless explicitly declared by output scope.
6. **Partition law (path ↔ embedded equality):** If an anchor/partition token appears in both an artefact’s **path** and embedded **columns/fields**, the values MUST be **byte-identical**.

### 5.3 Deterministic execution environment

7. **No ambient nondeterminism:** States MUST NOT depend on wall-clock time, locale, machine hostname, filesystem ordering, hash-map iteration order, or OS entropy.
8. **Deterministic ordering:** Any ordering that affects outputs (sorting, tie-breaks, reductions, merges/joins) MUST be explicitly defined and MUST be stable across worker counts and parallelism choices permitted by the runtime.
9. **Numeric policy is a rail:** All numeric execution MUST comply with the declared Numeric Policy (floating-point posture, reduction rules, deterministic math profile). Fast-math / contraction / unspecified reductions are forbidden unless explicitly granted as an exception.

### 5.4 RNG governance (if a state uses randomness at all)

10. **No ambient RNG:** States MUST NOT instantiate their own PRNGs. All randomness MUST be obtained from the shared RNG Service under the declared RNG Policy.
11. **Stream scoping is mandatory:** Every RNG draw MUST be attributable to a deterministic Stream Key derived from run anchors + (`segment_id`,`state_id`) + purpose tag.
12. **Open-interval rule for uniforms:** Any uniform mapping used for stochastic decisions MUST be open-interval (never 0, never 1) as defined by the RNG Policy.
13. **Accounting is mandatory for RNG-consuming states:** RNG-consuming states MUST emit sufficient accounting evidence (envelopes/counters/events) to detect missing/extra/reordered consumption during validation and replay.

### 5.5 Canonical artefact identity and hashing

14. **Canonical serialization:** Governed artefacts MUST be serialized deterministically (stable field ordering, stable row ordering, stable numeric formatting/quantisation rules where required).
15. **Content hashing is required:** Every governed artefact MUST have a recorded `content_hash` computed under the canonical serialization rules and declared hash algorithm/version.
16. **Bundle/index determinism:** Any validation bundle/index used for consumer gates MUST be hashable in a deterministic way (paths relative, stable ordering), and the gate hash MUST be reproducible on replay.

### 5.6 Immutability, atomic publish, and idempotence

17. **Atomic publish:** A state MUST publish outputs atomically (no partial visibility to downstream readers).
18. **Immutability by default:** Once written, governed artefacts MUST NOT be mutated. If an artefact is append-only or monotonic, that exception MUST be explicitly declared (and enforced).
19. **Idempotent re-run:** Re-running a state under identical anchors and inputs MUST either:

* produce byte-identical artefacts (preferred), or
* deterministically no-op (if outputs already exist and are identical by hash), or
* fail with a clear diagnostic explaining the mismatch.

### 5.7 Validation is mandatory, deterministic, and fail-closed

20. **Every governed output is validated:** Each state MUST produce validation evidence for its governed outputs (schema + semantic invariants as declared).
21. **Validation must be deterministic:** Validators MUST NOT introduce nondeterminism (including nondeterministic sampling). Any sampling MUST be deterministic by policy.
22. **Fail-closed:** Missing policies, missing required inputs, missing required validation artefacts, or failed checks MUST cause failure (not silent degradation), unless explicitly declared as an optional surface with a degrade ladder.

### 5.8 Gate semantics are non-negotiable

23. **No PASS → no read:** A consumer (downstream state/segment/component) MUST NOT read governed artefacts unless all required PASS gates are present and valid per the Gate Map.
24. **Receipts do not substitute final gates:** Intermediate receipts are additive. They MUST NOT be treated as substitutes for a segment’s final consumer gate unless explicitly declared (and that declaration is treated as a breaking-risk interface).
25. **Consumers must verify identity:** When reading governed artefacts, consumers MUST verify:

* required PASS gates,
* relevant content hashes (and bundle gate hash where applicable),
* required anchor/path↔embed equality checks.

### 5.9 Exceptions are explicit or they do not exist

26. **Declared or forbidden:** Any deviation from these laws MUST be explicitly declared as an exception under §2.5 with scope + justification + compensating controls. Undeclared deviations are non-compliant and MUST fail validation/conformance.

---

# Part I — Shared primitives (Binding)

## 6) Run identity and anchoring (Binding)

### 6.1 Definition: the Run Anchor is the engine’s “truth root”

Every engine execution MUST be anchored by a **Run Anchor** (RunContext) that unambiguously answers:

* **Which world inputs are in force?** (`manifest_fingerprint`)
* **Which policy/parameter closure is in force?** (`parameter_hash`)
* **Which stochastic branch (if any) is in force?** (seed material)
* **Which platform execution lineage is this?** (`scenario_id`, `run_id`)

A state MUST treat the Run Anchor as read-only, authoritative, and present for the full lifetime of the state.

---

### 6.2 Required fields (minimum binding set)

A Run Anchor MUST include at least the following fields:

1. **`manifest_fingerprint`**
   Content identity of the world-manifest closure (all externals + references used to build the world).

2. **`parameter_hash`**
   Content identity of the resolved parameter/policy bundle used by the segment(s)/state(s).

3. **`scenario_id`**
   Platform-level scenario identity. This SHOULD remain stable across retries of the same scenario.

4. **`run_id`**
   Platform-level execution attempt identity. This MAY change across retries.

5. **`seed_material`** (structured)
   A binding structure sufficient to deterministically derive all RNG streams (even if some states are RNG-free). At minimum:

   * `seed_root` (or equivalent root seed)
   * `seed_policy_id` (identifies which derivation scheme/policy is used)
   * any additional derivation inputs required by the RNG Policy

6. **`engine_build_id`** (or equivalent)
   A version identifier for the engine implementation (or build) that is part of reproducibility claims.

7. **`rails_versions`** (structured)
   Version identifiers for the shared rails that affect determinism/reproducibility, including:

   * RNG Policy version
   * Numeric Policy version
   * Validation Policy bundle version (or its content hash)

**Rule:** If a segment/state claims reproducibility across time, then `engine_build_id` and `rails_versions` MUST be recorded in state manifests and validation bundles.

---

### 6.3 Decomposition: stable identity vs attempt identity

The Run Anchor contains both **stable identity** and **attempt identity**. They have different allowed roles:

#### 6.3.1 Stable identity (MUST influence governed outputs when relevant)

* `manifest_fingerprint`
* `parameter_hash`
* `seed_material` (for seed-dependent outputs)

These are the **replay keys**: if these are the same, governed outputs MUST be reproducible (as defined by the segment/state equality contract), unless the state is explicitly declared non-reproducible (which is generally forbidden for governed artefacts).

#### 6.3.2 Attempt identity (MUST NOT influence governed model outputs by default)

* `scenario_id`
* `run_id`

These exist for platform lineage, logging, and operational tracking. By default:

* `run_id` MUST NOT alter deterministic model outputs.
* `scenario_id` MUST NOT alter deterministic model outputs.

They MAY influence:

* log partitioning,
* operational manifests,
* provenance fields,
* diagnostic artefacts,

…but MUST NOT become a hidden input to model generation.

**Exception rule:** If a segment/state explicitly declares an artefact as `LOG_SCOPED` (or equivalent) and includes `{run_id, scenario_id}` in its declared partition keys, then those keys MAY appear in that artefact’s identity and address **only to the extent declared**.

---

### 6.4 Seed material and RNG anchoring rules

#### 6.4.1 Seed material must be explicit, not implied

* A state MUST NOT invent seed values.
* If a state uses randomness, it MUST derive all RNG streams from `seed_material` via the RNG Service (see RNG rail).
* If a state is RNG-free, it MUST still receive `seed_material` as part of the Run Anchor (for uniformity and validation coherence).

#### 6.4.2 Stream derivation MUST be retry-stable by default

Unless explicitly declared otherwise, RNG stream derivation MUST be stable across retries. Therefore:

* RNG stream keys MUST be derived from **stable identity** (e.g., `manifest_fingerprint`, `parameter_hash`, `seed_root`, `segment_id`, `state_id`, purpose tag).
* RNG stream keys MUST NOT include `run_id` by default.

This ensures that a retry produces the same stochastic outcomes (and only differs in attempt metadata).

#### 6.4.3 Optional: attempt-unique RNG (rare)

If a segment/state truly requires attempt-unique randomness (uncommon for governed outputs), it MUST:

* declare this explicitly in its Segment RDV Profile / State Manifest,
* declare which artefacts become attempt-unique,
* treat this as breaking-risk for reproducibility guarantees.

---

### 6.5 Anchor propagation requirements (what must carry what)

#### 6.5.1 State Manifest MUST record full anchor

Every state MUST emit a State Manifest (or equivalent) that records the **full Run Anchor** used for execution, including:

* `manifest_fingerprint`, `parameter_hash`
* `scenario_id`, `run_id`
* `seed_material` (or a hash of it, if sensitive/large, but the derivation inputs must remain verifiable)
* `engine_build_id`, `rails_versions`

#### 6.5.2 Governed artefacts MUST be anchor-verifiable

Every governed artefact MUST be verifiable against the Run Anchor via at least one of:

* path tokens (addressing),
* embedded fields/columns (where the dataset dictionary permits),
* a sidecar metadata record (e.g., dataset `_meta.json`), or
* inclusion in a state output manifest / index that binds it to anchors and content hash.

**Rule:** A consumer MUST be able to verify that an artefact belongs to the correct run anchor scope without reading undocumented “ambient context.”

#### 6.5.3 Validation bundles MUST bind artefacts to anchors

Every Validation Bundle MUST include:

* the relevant scope anchors (at minimum `manifest_fingerprint`, `parameter_hash`, plus seed if seed-scoped),
* references to validated artefacts (ArtefactRefs + content hashes),
* validation policy identity/version.

---

### 6.6 Anchor usage rules by output scope class

Each artefact MUST declare its output scope class (see §4). Anchors may appear only as permitted:

#### 6.6.1 PARAMETER_SCOPED artefacts

* MUST be invariant with respect to `seed_material`, `run_id`, and `scenario_id`.
* MUST be addressed/partitioned by `parameter_hash` (and any other keys explicitly allowed by its dictionary), and MUST NOT include attempt identity tokens.

#### 6.6.2 FINGERPRINT_SCOPED artefacts

* MUST be invariant with respect to `run_id` (attempt identity).
* MAY depend on `seed_material` only if the segment declares that fingerprint scope includes seed (this MUST be explicit; default is **no**).
* MUST be addressed/partitioned by `manifest_fingerprint` (and allowed companion keys only).

#### 6.6.3 LOG_SCOPED artefacts

* MAY include `run_id` and/or `scenario_id` in partitioning if declared.
* MUST NOT be consumed as model inputs unless the Gate Map explicitly permits them as governed inputs (rare; typically logs are for audit/trace, not model dependence).

#### 6.6.4 EGRESS_SCOPED consumer surfaces

* MUST follow the segment’s declared consumer surface partitioning rules.
* MUST be protected by the segment’s declared final consumer gate.

---

### 6.7 Path ↔ embed equality and “role separation” constraints

#### 6.7.1 Path ↔ embed equality (mandatory where duplicated)

If an anchor token appears both:

* in the artefact’s address (path template), and
* inside the artefact as a field/column/metadata,

…then the values MUST be **byte-identical**.

Violations MUST fail validation.

#### 6.7.2 Role separation: anchors are not interchangeable

* `parameter_hash` MUST NOT be used as a proxy for `manifest_fingerprint`, and vice versa.
* `run_id` MUST NOT be used to “version” model outputs; versioning is through `engine_build_id`, `rails_versions`, and pinned policy/data identities.
* Seed-related tokens MUST NOT be injected into parameter-scoped outputs.

---

### 6.8 Multi-entity execution: scenarios that involve more than one anchor set

If a higher-level component (e.g., Scenario Runner) orchestrates multiple anchor sets, the engine MUST treat each anchor set as an independent run scope:

* A state MUST NOT mix artefacts from different `manifest_fingerprint` values in a single governed output unless the segment explicitly defines a cross-run aggregation mode (rare; treated as a separate segment/state class).
* A state MUST NOT mix artefacts from different `parameter_hash` values unless explicitly declared as a comparative/derivation state with strong provenance and validation.

---

### 6.9 Minimum diagnostics requirements

When failing due to missing/invalid anchors, the engine MUST emit diagnostics that include:

* `segment_id`, `state_id`
* `manifest_fingerprint`, `parameter_hash`
* `scenario_id`, `run_id`
* the specific missing/invalid field(s) and where they were expected (path vs embedded vs manifest)

This is mandatory for fail-closed behavior to be actionable.

---

### 6.10 Conformance checklist for this section (binding)

A segment/state is non-compliant if any of the following are true:

* It executes without a full Run Anchor present.
* It uses `run_id` or `scenario_id` to alter deterministic model outputs without explicit declaration and scope control.
* It produces governed artefacts that cannot be bound back to anchors via address/embed/metadata + manifests.
* It violates path↔embed equality for any duplicated anchor token.
* It derives randomness outside the RNG Service or from undeclared seed material.

---

## 7) Addressing and artefact identity (Binding)

### 7.1 What is authoritative for addresses and identity

1. **Dataset Dictionary is authoritative** for:

   * dataset/log/report **IDs**
   * **format**
   * **path template**
   * **partitioning keys (and order)**
   * declared **ordering / writer sort** (if any)
   * **schema_ref**
   * **gating notes** (consumer obligations)  

2. **Artefact Registry is authoritative** for:

   * the governed **inventory** of artefacts/configs/policies
   * declared **dependencies**
   * the artefact’s **role** and governance notes (including consumer gate semantics where repeated)  

3. **State specs MAY illustrate** paths, but if an illustration conflicts with the Dictionary/Registry, the **Dictionary/Registry win**. (This is explicitly the posture in 1A.) 

---

### 7.2 Canonical address template rules

For every governed artefact, there MUST exist exactly one canonical address template in the Dataset Dictionary (and/or Artefact Registry for non-dataset artefacts).

**7.2.1 Token syntax**

* Tokens MUST be written as `name={value}` inside a single directory segment.
* Token names MUST be ASCII and stable (no per-state invention).
* Token values MUST come from the Run Anchor or from declared dataset versioning (e.g., `{parameter_hash}`, `{seed}`, `{run_id}`).  

**7.2.2 Allowed partition token set (engine-wide)**
At minimum, the engine recognizes these partition tokens (segments may use a subset):

* `parameter_hash={parameter_hash}` (parameter-scoped)
* `seed={seed}` (seed-scoped artefacts/logs)
* `run_id={run_id}` (log-scoped only)
* `fingerprint={manifest_fingerprint}` (egress/validation scope) — see §7.3 for naming constraints

Additional tokens (e.g., `utc_day={utc_day}`, `version={version}`) MAY exist only if declared by the Dictionary/Registry for that artefact (e.g., ops reports). 

---

### 7.3 Canonical naming for `manifest_fingerprint` in paths

Your 1A pattern establishes a crucial convention:

* **Column/field name (semantic key):** `manifest_fingerprint`
* **Recommended path label (interface token):** `fingerprint={manifest_fingerprint}`
  (“fingerprint” is the path label; the value is the run’s `manifest_fingerprint`.)  

**Binding rule (engine-wide):**

* If an artefact is **fingerprint-scoped**, the address MUST include a single token that carries the run’s `manifest_fingerprint` value.
* New/updated segments SHOULD standardize on the **path label** `fingerprint={manifest_fingerprint}` to avoid drift and cross-segment confusion. 
* If a segment uses the legacy label `manifest_fingerprint={manifest_fingerprint}` in its Dictionary/Registry, it MUST declare an explicit alias/migration note in its Segment RDV Profile (and MUST still obey §7.5 path↔embed equality and §7.4 partition matching).  

*(This directly addresses the “S9 consumer text says `fingerprint=…` while some dictionary entries show `manifest_fingerprint=…`” class of drift.)*  

---

### 7.4 Partition keys and “address ↔ partition” matching

For every governed dataset/log/report:

1. The Dictionary’s `partitioning: [...]` list is **normative**. 
2. The path template MUST contain exactly those keys (no more, no fewer), in the same order, unless the format is a single file (then the token may appear in the parent folder). 
3. A state MUST NOT write partitions that do not match the declared keys (e.g., writing a parameter-scoped dataset under a seed-scoped path is a structural failure). 

**Canonical examples from 1A (pattern, not limit):**

* Parameter-scoped datasets: `[parameter_hash]` 
* Egress/validation: `[manifest_fingerprint]` (plus `seed` for some egress datasets)  
* RNG logs/events: `[seed, parameter_hash, run_id]`  

---

### 7.5 Path ↔ embedded lineage equality (identity consistency law)

Where a lineage/partition key is present both:

* in the **path token**, and
* in the artefact’s **embedded fields/columns/metadata**,

…the values MUST be **byte-identical**. Any mismatch is a validation FAIL.  

This includes (illustrative from 1A):

* Egress: `outlet_catalogue.manifest_fingerprint` must equal the path’s fingerprint token; `global_seed` equals `seed`. 
* Parameter-scoped tables: row-embedded `parameter_hash` equals the path token. 
* RNG logs/events: embedded `{seed, parameter_hash, run_id}` equals path tokens on every row. 

---

### 7.6 Artefact identity tuple (what makes “this artefact” *this artefact*)

A governed artefact’s identity MUST be representable as:

* `dataset_id` (or registry `name`)
* `format`
* `schema_ref`
* partition key tuple (values for the Dictionary’s `partitioning` list)
* one or more deterministic **checksums** (see §7.7)

The state MUST record this identity in its State Manifest (and validators MUST use it during gate creation).

---

### 7.7 Deterministic checksums and bundle-style identity

**7.7.1 File artefacts (text/json/yaml)**

* Default checksum algorithm is **SHA-256 over raw bytes**.
* Hex encoding MUST be lower-case and fixed-width where applicable (e.g., hex64).
  (Your 1A gate/bundle patterns already assume SHA-256.)  

**7.7.2 Partitioned datasets (e.g., Parquet folders)**

* The Dictionary’s `ordering` (writer sort) is normative when present, and validators MAY enforce it across files/parts.  
* If byte-identical file layouts are not guaranteed (e.g., differing part splits), the segment MUST still provide deterministic identity evidence via:

  * per-file checksums + a deterministic composite, **or**
  * a canonical rowset hash scheme declared by segment profile.

(1A uses explicit `egress_checksums.json` in the validation bundle for egress partitions.) 

**7.7.3 Folder bundles (validation bundles, receipts, gate folders)**
For any “bundle folder” that is itself the governed artefact (e.g., validation bundle), identity MUST be defined by:

* an **`index.json`** that enumerates every non-flag file exactly once using a schema,
* and a co-located **gate flag** whose content is a deterministic hash over the indexed files.  

**Binding bundle index rules (adopted engine-wide from the 1A pattern):**

* `artifact_id` MUST be unique and ASCII-safe (regex hygiene as per bundle index rules). 
* `path` entries MUST be **relative**, ASCII-normalised, contain no `..`, and be lexicographically orderable. 
* The gate hash MUST be computed over the concatenation of **raw bytes** of all files listed in `index.json` (excluding the flag), in **ASCII-lexicographic order** of the `path` entries.  

---

### 7.8 “No PASS → no read” is an identity boundary, not just a rule of thumb

If a dataset’s Dictionary entry declares a consumer gate requirement (e.g., “verify `_passed.flag` matches SHA256(bundle) for the same fingerprint”), that gate becomes part of the **effective identity boundary** for consumers: the partition is not “readable” until the gate verifies.  

---

### 7.9 Conformance checklist for §7 (Binding)

A segment/state is non-compliant if:

* any governed artefact has no authoritative Dictionary/Registry address template, 
* partitions written do not match declared partition keys (names or order), 
* path↔embedded lineage equality is violated anywhere, 
* a bundle/gate folder exists without a deterministic index+flag identity rule, 
* consumer-facing gates are not co-located / not verifiable as declared. 

---

## 8) IO and publication semantics (Binding)

### 8.1 Definitions (normative)

* **Dataset instance:** the complete materialization of a dataset for a single partition key tuple (as declared in the Dataset Dictionary).
* **Bundle instance:** a governed **folder** artefact (e.g., receipts, validation bundles) whose identity is defined by its `index.json` + associated gate flag rules (see §7.7.3).
* **Stage:** writing outputs to a temporary location that MUST NOT be considered readable by any consumer.
* **Publish:** the single action that makes an instance visible at its canonical dictionary/registry path (typically via atomic rename).
* **Readable:** a stronger condition than “published”: an instance is readable only when all required **PASS gates** are satisfied (“no PASS → no read”).  

---

### 8.2 Unit of atomicity (what must be all-or-nothing)

A producer MUST treat each governed artefact as atomic at one of these granularities:

1. **Single-file artefact:** the file is the unit (write → fsync → atomic move into place).
2. **Folder/bundle artefact:** the entire folder is the unit (build in temp folder → compute hashes/flags → single atomic rename).  
3. **Partitioned dataset instance:** the partition directory is the unit (all parts + metadata complete) and MUST be published as a complete instance (no partial partitions). 

If the underlying storage cannot provide true directory-rename atomicity, the implementation MUST provide an equivalent *single-step publish barrier* (e.g., commit marker with strict “not readable until marker” enforcement) while still satisfying §8.5–§8.8.

---

### 8.3 Atomic publish requirement (no partial visibility)

**Binding rule:** Producers MUST publish atomically such that **no partial contents** of an instance become visible at the canonical path.

**Required pattern (normative):**

* Build under a temporary path (e.g., `…/_tmp.{uuid}`) **in the same parent** as the final destination.
* Write all files/parts.
* Ensure durability (fsync/flush) as required by the runtime.
* Perform a **single atomic rename** to the canonical dictionary/registry path.
* On any failure before publish, delete the temporary path.  

This pattern is explicitly enforced for validation bundles (“stage → compute hash → atomic rename; no partial contents visible”).  

---

### 8.4 Publication ordering for gates (PASS/FAIL semantics)

Where an artefact has an associated **PASS gate** (receipt or final bundle flag), the gate is part of the publication semantics:

1. **PASS gate MUST be computed over the fully staged instance** (never over a partially-written instance). 
2. **PASS gate MUST NOT be written unless the instance is complete.**
3. **PASS vs FAIL outcome MUST be unambiguous:**

   * On **PASS**, publish the full instance **with** the PASS gate artefact.
   * On **FAIL**, publish diagnostics as allowed, but **withhold** the PASS gate (so the instance remains non-readable).  

*(This matches the 1A finalizer behavior: the validation bundle is always written, but `_passed.flag` is withheld on FAIL.)* 

---

### 8.5 Write-once, immutability, and overwrite rules

**8.5.1 Write-once partitions (default)**
For all governed outputs, the default rule is **write-once**:

* A producer MUST NOT overwrite a published instance.
* If a published instance already exists, the producer MUST either:

  * deterministically **no-op** (if identical), or
  * fail closed with an I/O integrity violation.

States that produce receipts/bundles explicitly follow this “atomic publish + equivalence on rerun” posture.  

**8.5.2 Immutability after PASS**
If an instance is protected by a PASS gate, then:

* Once published with PASS, it is **immutable**.
* Any later attempt to mutate or replace it is non-compliant and MUST be treated as an I/O integrity failure. 

**8.5.3 Declared exceptions (append-only / monotonic)**
Append-only or monotonic updates are allowed only if:

* the Dataset Dictionary/Registry explicitly declares the artefact as append-only/monotonic,
* the update law is deterministic and validator-checkable, and
* the Gate Map clarifies how readers should treat intermediate states (generally: still “no PASS → no read” for consumer surfaces).

---

### 8.6 Idempotent retries and resume semantics

**8.6.1 Idempotence for identical lineage**
If a state is re-run with identical lineage keys for a given output scope (as declared by the dictionary/profile), it MUST produce an equivalent published instance (per the segment’s equality rule), or deterministically no-op.

This is a binding expectation for both receipts/bundles and producer partitions.  

**8.6.2 Resume safety**
On failure:

* Producers MUST NOT leave behind a partially published instance.
* Any staging paths MUST be cleaned.
* If any partial output escaped staging, the producer MUST mark it as incomplete using a deterministic sentinel mechanism (so validators and operators can detect/clean it). 

---

### 8.7 Completeness checks (F10 class)

I/O integrity and atomicity are first-class failure conditions:

* Short writes, partial instances, and non-atomic commits MUST be treated as run-failing I/O integrity errors. 
* The **writer commit phase** is the preferred first detector; validators perform secondary completeness checks.  

---

### 8.8 Concurrency and “single-writer per instance”

To prevent corruption and nondeterministic outcomes:

* For any dataset/bundle instance (partition tuple), there MUST be at most **one** active publisher at a time.
* If concurrent execution is allowed, the implementation MUST use a deterministic locking/claim mechanism (e.g., lockfile or orchestration-level mutual exclusion) to enforce single-writer behavior.
* Readers/validators MAY be parallel, but MUST NOT rely on filesystem order for set-semantics logs; ordering rules come from the Dictionary (writer sort vs `ordering: []`).  

---

### 8.9 Lints and auxiliary files in governed bundles

If a bundle includes auxiliary diagnostics (e.g., dictionary/schema lints), the inclusion/exclusion rule MUST be stable:

* By default, optional lints are **included** in the gate hash for the bundle.
* They MAY be excluded only if the exclusion is explicitly documented **and** the hashing rule is updated consistently (i.e., both producers and consumers agree). 

---

### 8.10 Abort artefacts are governed publications too

When a run aborts, the failure artefacts are still governed outputs and MUST follow the same atomic + deterministic posture:

* Failure records live at canonical, fingerprint-scoped validation paths and are committed atomically (temp dir → rename). 
* Under identical inputs/environment, failure records MUST be bit-identical to support reproducible forensics. 

---

## 9) Canonical serialization rules (Binding)

> **Binding intent:** Any artefact that participates in hashing, identity, gates, receipts, or validation evidence MUST have a canonical byte representation so that “hash-of-bytes” is meaningful and replay-stable.

### 9.1 Byte-domain rule (what hashes are over)

1. **All digests are over raw bytes.** Whenever this constitution says “SHA-256 of X”, X means the **exact bytes as opened in binary mode** — no newline translation, no re-encoding, no parse/pretty-print roundtrips. 
2. **Hex encoding is canonical.** Any `sha256_hex` / fingerprint / parameter hash MUST be lower-case hex with fixed width (64 chars for SHA-256). 
3. If a producer/validator needs a canonical form, it MUST be achieved by using the engine’s **canonical emitters** (below), not by “whatever the language library defaults to”.

### 9.2 Text encoding and line endings (applies to JSON, JSONL, txt, flag files)

1. **Encoding:** UTF-8, no BOM.
2. **Line endings:** LF (`\n`) only.
3. **No trailing whitespace** on lines in machine-governed files (manifests, indexes, flags).
4. **Flags are single-line ASCII.** `_passed.flag` content is exactly `sha256_hex = <hex64>` with no extra lines. 

### 9.3 JSON (single-document JSON files: `MANIFEST.json`, `*_resolved.json`, etc.)

For any governed JSON document that may be hashed, indexed, or compared:

1. **No NaN/Infinity.** JSON numeric values MUST be finite; encountering NaN/Inf is a hard error (ties to numeric determinism controls). 
2. **Deterministic object emission:** Producers MUST use a canonical JSON emitter that:

   * emits keys in a deterministic order (e.g., lexicographic), and
   * emits numbers deterministically (no locale dependence; stable algorithm/version pinned).
3. **Deterministic arrays:** If an array’s ordering is not semantically meaningful, the spec for that file MUST require sorting by a deterministic key before emission (do not rely on “insertion order”).
4. **Timestamp fields:** Any “created time” fields included in hashed/compared JSON MUST be derived from the Run Anchor / pinned metadata — not wall clock — otherwise byte-identical replays are impossible. (S9 requires byte-identical re-runs for the bundle.) 

### 9.4 YAML (policy/config sources)

1. YAML inputs that contribute to `parameter_hash` / `manifest_fingerprint` are treated as **opaque bytes** for hashing (no normalization, no parsing/rewriting). 
2. Therefore: **never “round-trip” YAML** (parse + dump) as part of the engine runtime. Any formatting change is a real change and MUST flip the relevant hash.

### 9.5 JSONL (NDJSON) event/log streams

JSONL is used for run-scoped logs and RNG event families. Canonical rules:

1. **One JSON object per line**; LF line endings; **do not pretty-print**. 
2. **Optional compression:** `.jsonl` MAY be stored as `.jsonl.zst` if the segment/profile pins that choice; otherwise treat compression as an implementation detail that must be deterministic if hashed. 
3. **Set semantics where declared:** For streams declared as set-semantic (as in 1A validation posture), validators MUST treat record order as non-semantic and duplicates as structural errors. 
4. **Identity keys required:** Any set-semantic JSONL stream MUST have a declared record identity key (or tuple) so duplicates can be detected deterministically.

### 9.6 Parquet (tables)

Parquet tables are governed by the Dataset Dictionary and must remain deterministic at the **rowset + ordering** level.

1. **Single format per dataset instance:** A dataset partition MUST NOT mix Parquet with other formats. 
2. **Writer sort is authoritative when declared:**

   * If the Dictionary declares `ordering: [...]`, producers MUST emit rows such that the partition is globally sorted by those keys (within and across files).
   * Example: `outlet_catalogue` ordering is declared as `[merchant_id, legal_country_iso, site_order]` and is enforced by validation.  
3. **Physical file order is non-authoritative:** Readers MUST NOT rely on file enumeration order. Equality for Parquet datasets is by **rowset** (and by writer-sort constraints where declared). 
4. **Compression/profile pinning:** If a segment pins a Parquet compression/profile (e.g., ZSTD level 3), producers SHOULD follow it; if it is included in sealed inputs / manifests it becomes reproducibility-relevant. 

### 9.7 Bundle canonicalization (validation bundles, receipts)

Bundles are folder artefacts whose identity is defined by **index + hash gate**:

1. **Index completeness:** Every non-flag file in the bundle MUST appear exactly once in `index.json`. 
2. **Relative paths only:** `path` entries MUST be relative (no leading `/`, no `..` segments) and ASCII-normalised.  
3. **Deterministic hashing order:** The bundle digest used in `_passed.flag` MUST be computed by:

   * taking the `path` entries from `index.json`,
   * sorting them in ASCII-lexicographic order,
   * concatenating the raw bytes of the referenced files in that order (excluding `_passed.flag`),
   * then SHA-256 hashing the concatenation. 
4. **Index schema flexibility (allowed variance):** A segment MAY extend the index entry shape (e.g., `artifact_id`, `kind`, `mime`, `notes`) so long as:

   * the bundle hashing rule remains anchored on the `path` list, and
   * the index schema is pinned in that segment’s schema set (as 1A does).  

### 9.8 Checksums, sidecars, and composite digests

1. For partitioned datasets (Parquet folders, JSONL shards), segments MAY require:

   * per-file `sha256_hex` sidecars, and/or
   * a composite digest over file hashes in lexicographic file-path order. 
2. If such sidecars/composites are used as validation evidence (e.g., `egress_checksums.json`), the exact method MUST be declared and validators MUST enforce it. 

### 9.9 Numeric serialization tie-in (when numbers become bytes)

When numeric values are serialized into JSON/JSONL or into deterministic sort keys:

1. **Decision-critical numeric behavior is governed by Numeric Policy** (binary64, RNE, no FMA, no FTZ/DAZ, deterministic libm profile). 
2. **Stable float ordering:** Any float used in sorting/keys MUST use IEEE-754 totalOrder semantics and deterministic tie-breakers. 
3. **Quantisation rules must be explicit:** If a state stores narrowed floats (e.g., float32 diagnostics) or fixed-dp decimals, the quantisation method MUST be explicitly specified and deterministic. 

### 9.10 Conformance checklist for §9 (Binding)

Non-compliance if any of the following occur:

* A hashed/compared JSON file is emitted with non-deterministic key ordering or non-deterministic numeric formatting.
* JSONL logs violate NDJSON rules (multiple objects per line, CRLF, pretty-print). 
* A Parquet dataset violates declared writer sort constraints or mixes formats.  
* A bundle’s `_passed.flag` does not match the required hash-of-indexed-files rule, or `index.json` includes non-relative/unsafe paths.  
* Any serialization depends on locale, wall-clock time, or environment defaults in a way that breaks byte-identical replay where required. 

---

## 10) Policy/config pinning (Binding)

### 10.1 Purpose (what “pinning” guarantees)

Policy/config pinning exists to ensure that:

* **Every behavioural choice** that can change governed outputs is **explicit, discoverable, and hash-addressable**.
* Replays are meaningful: identical anchors imply identical behaviour (or a deterministic fail).
* Cross-state/segment composition is safe: downstream states can trust that upstream behaviour is fixed by pinned inputs, not ambient defaults.

This section binds the **mechanics** that make “policy” part of lineage (primarily via `parameter_hash` and `manifest_fingerprint`).  

---

### 10.2 Two pinning domains (normative split)

A segment MUST classify every non-code input that it reads into exactly one of the following domains:

#### 10.2.1 Governed Parameter Set `𝓟` (drives `parameter_hash`)

`𝓟` is the set of **parameter/policy files** whose **byte content** defines the segment’s behavioural posture for parameter-scoped outputs.

* `parameter_hash` MUST be computed **only** from `𝓟` (and the basenames of its members).
* Any byte change to any `p ∈ 𝓟` MUST flip `parameter_hash`. 

1A provides an explicit example of `𝓟` being a canonical basename list, and explicitly states that changing bytes flips `parameter_hash`.  

#### 10.2.2 Opened Artefact Set `𝓐` (drives `manifest_fingerprint`)

`𝓐` is the set of **all artefacts actually opened** during execution (schemas, dictionaries, reference datasets, numeric policy files, etc.), plus the code identity and `parameter_hash_bytes`.

* `manifest_fingerprint` MUST flip if **any opened artefact changes bytes or basename**, or if the **code commit** changes, or if `parameter_hash_bytes` changes. 
* `𝓐` MUST include the **transitive dependency closure** declared in the artefact registry; missing dependencies MUST fail closed. 

---

### 10.3 Canonical formation of `parameter_hash` (binding algorithm)

Each segment MUST define a governed set `𝓟` as a list of **canonical basenames** (ASCII, unique). 

**Algorithm requirements (binding):**

1. Validate: every basename in `𝓟` is **ASCII** and **unique**; duplicates or non-ASCII MUST abort.
2. Sort `𝓟` by basename using **bytewise ASCII lexicographic order**.
3. For each file `pᵢ`:

   * `dᵢ = SHA256(bytes(pᵢ))` (raw bytes; no parsing/normalization).
   * `tᵢ = SHA256( UER(basenameᵢ) || dᵢ )` (name + digest binding).
4. Concatenate `C = t₁ || … || tₙ`.
5. `parameter_hash_bytes = SHA256(C)` and `parameter_hash = hex64(parameter_hash_bytes)`.

**Non-negotiable:** The hash MUST be name-sensitive (changing a basename or file membership flips the hash). 

---

### 10.4 Canonical formation of `manifest_fingerprint` (binding algorithm)

A segment MUST compute `manifest_fingerprint` over:

* the set `𝓐` of actually opened artefacts (with dependency closure),
* `git_32` (raw 32 bytes of commit id, padded if necessary),
* and `parameter_hash_bytes`. 

**Algorithm requirements (binding):**

1. Validate: basenames for artefacts in `𝓐` are ASCII and unique; duplicates MUST abort.
2. Sort `𝓐` by basename (ASCII).
3. For each opened artefact `a`:

   * `D(a) = SHA256(bytes(a))`
   * `T(a) = SHA256( UER(basename(a)) || D(a) )`
4. Concatenate `U = T(a₁) || … || T(a_k) || git_32 || parameter_hash_bytes`
5. `manifest_fingerprint_bytes = SHA256(U)` and `manifest_fingerprint = hex64(manifest_fingerprint_bytes)`.

**Dependency-closure rule (binding):** If the registry declares `dependencies` for an opened artefact, the runtime MUST open and include those dependencies in `𝓐`; missing dependency MUST abort. 

---

### 10.5 Required sealing outputs (“resolved” evidence)

Every run MUST emit fingerprint-scoped evidence sufficient to prove what was pinned.

**10.5.1 Parameter evidence (minimum set)**
The validation bundle MUST include:

* `parameter_hash_resolved.json` recording `{parameter_hash, filenames_sorted, artifact_count}` 
* `param_digest_log.jsonl` with one row per `p ∈ 𝓟` containing at least `{filename, size_bytes, sha256_hex, mtime_ns}` 

**10.5.2 Fingerprint evidence (minimum set)**
The validation bundle MUST include:

* `manifest_fingerprint_resolved.json` binding `{manifest_fingerprint, git_commit_hex, parameter_hash, artifact_count}` 
* `fingerprint_artifacts.jsonl` with one row per opened artefact containing at least `{path, sha256_hex, size_bytes}` 

**10.5.3 Schema governance**
Where schemas exist for these evidence artefacts, they MUST be used (single schema authority posture). For example, layer schema defines required fields/patterns for resolved manifests. 

---

### 10.6 Registry-backed pinning (no “unregistered” policies)

Every policy/config/reference artefact that participates in `𝓟` or `𝓐` MUST be present in the Artefact Registry with:

* canonical path,
* digest field,
* manifest key,
* declared dependencies (if any),
* and environment scope.  

If an artefact is opened but absent from the registry (or its dependency closure is incomplete), the run MUST fail closed (pinning cannot be proven). 

---

### 10.7 Policy validity checks (schema-first; spec fallback)

For each policy/config file in `𝓟`:

1. **Schema-first (preferred):** If a JSON-Schema exists for the policy, the policy MUST validate against it, and unknown keys SHOULD be forbidden (`additionalProperties: false`) to prevent “silent semantics.” 1A explicitly requires this for the S6 policy set. 
2. **Spec fallback:** If no schema exists yet, the consuming state spec MUST define the binding key set and domains (no extra keys) until a schema is introduced. 1A S5 uses this posture for its smoothing params policy. 

In both cases, policy validation failures MUST be fail-closed (do not guess defaults).

---

### 10.8 Versioning inside policy/config files

Each policy/config file in `𝓟` MUST carry in-file version metadata sufficient for humans and tooling:

* A semantic version field (e.g., `semver` or `policy_semver`) MUST be present.  
* A date/version tag SHOULD be present where your conventions use it (e.g., `version: YYYY-MM-DD`). 
* These fields are **descriptive**; the binding lineage mechanism remains **byte hashing** (changing any byte flips `parameter_hash`). 

---

### 10.9 No hidden defaults: “resolved policy closure” rule

A segment MUST ensure that:

* every behavioural parameter used by a state is either explicitly present in a policy/config file in `𝓟`, or is a binding default defined by schema/spec and therefore deterministic and reviewable; and
* the applied defaults are deterministic (no environment dependence).

Where a state implements override precedence (e.g., defaults → per-currency), the precedence order MUST be specified and deterministic. 

---

### 10.10 Conformance checklist for §10 (Binding)

Non-compliance if any of the following occur:

* A state reads a policy/config that is not in `𝓟` (for parameter semantics) or not included in `𝓐` (for opened artefacts) when it should be. 
* `parameter_hash` formation is not name-sensitive, not byte-based, not sorted, or not fail-closed on basename issues. 
* Dependency closure is not enforced for opened artefacts. 
* The run does not emit the minimum “resolved evidence” artefacts proving what was pinned. 
* Policy validation is permissive in a way that allows unknown keys to silently change semantics (unless explicitly declared as an allowed extension surface).

---

# Part II — Determinism Rail (Binding)

## 12) RNG governance (Binding)

> This section defines the engine’s **single RNG constitution**. Segments/states MAY differ in *which event families they emit* and *how many draws they consume*, but they MUST do so under the shared rules below.

### 12.1 Non-negotiables (applies to every segment/state)

1. **No ambient RNG:** a state MUST NOT instantiate its own PRNG. All randomness MUST be obtained via the engine RNG Service under this governance.
2. **Replay is mandatory:** given identical run anchors + pinned policies, RNG-consuming states MUST reproduce identical RNG event logs (or deterministically fail).
3. **Accounting is mandatory:** every RNG event MUST carry a valid envelope (`before/after/blocks/draws`) and MUST be reconciled by trace totals.  
4. **Logs are set-semantic:** physical line/file order MUST NOT be used for meaning; pairing/replay uses envelope counters and declared keys only.  

---

### 12.2 RNG engine and version pinning

**12.2.1 Engine (binding default)**

* The engine RNG algorithm is **Philox 2×64-10** with a **monotonically advancing 128-bit counter** per derived substream. 
* Any change to RNG algorithm, counter semantics, lane policy, or uniform mapping is a **rails version change** and MUST be pinned via `rails_versions` (see §6). 

**12.2.2 Counter representation (binding)**

* RNG event envelopes MUST carry counter fields as two u64 halves (`*_hi`, `*_lo`) for both `before` and `after`. Producers and validators MUST interpret the u128 counter as `(hi<<64) | lo`. 

---

### 12.3 Stream derivation and scoping (no cross-state contamination)

**12.3.1 Stream Key (binding)**
Every RNG draw MUST be attributable to a deterministic **Stream Key** derived from:

* run stable identity (`manifest_fingerprint`, `parameter_hash`, seed root/material),
* `segment_id`, `state_id`,
* a **purpose tag** (event family / sampler context),
* and any declared per-event IDs (e.g., merchant, country) as required by that family.

**12.3.2 Keyed substreams (binding)**

* RNG-consuming families MUST use **keyed substreams**: all draws for an event are drawn from `PHILOX(k(stream_key, ids), counter)` with a monotonically advancing counter.  
* The exact IDs used to key a family (e.g., `(merchant_id, country_iso)` for a keyed selection family) MUST be specified by the family schema/profile and MUST be stable. 

**12.3.3 Scope isolation (binding)**

* A state MUST write only the RNG families it owns and MUST NOT write into other states’ families. Validators MAY read for reconciliation but MUST NOT write RNG logs.  

---

### 12.4 Uniform mapping and lane policy

**12.4.1 Open-interval U(0,1) (binding)**

* Any uniform used for stochastic decisions MUST satisfy **strict open interval**: `0 < u < 1`. Exact `0.0` and `1.0` are forbidden.  

**12.4.2 Lane policy (binding)**

* Philox emits two 64-bit words per counter step (“block”).
* For **single-uniform** events, the state MUST consume the **low lane** and discard the high lane, so one counter increment corresponds to one uniform (`blocks=1`, `draws="1"`).  
* For multi-uniform samplers, the segment MUST declare how many uniforms are consumed and how blocks/lanes are used, and MUST account for it via `draws` and `blocks` (see §12.6). 

---

### 12.5 RNG log partitions and path discipline

**12.5.1 Canonical partitions (binding)**

* Core RNG logs and RNG event families are **run-scoped** and MUST be partitioned by `{seed, parameter_hash, run_id}` unless a segment profile explicitly extends the partition keys (rare).  

**12.5.2 Path ↔ embed equality (binding)**

* For event streams, embedded `{seed, parameter_hash, run_id}` fields (when present) MUST byte-equal the partition tokens in the path.  
* `rng_trace_log` MAY omit lineage fields by design; in that case, lineage is enforced by the partition path keys. 

**12.5.3 Physical order is non-authoritative (binding)**

* There are no ordering guarantees across files/parts. Any consumer depending on file order is non-conformant; reconciliation and replay MUST use envelope counters and declared keys only.  

---

### 12.6 Envelope model (before/after/blocks/draws)

**12.6.1 Required envelope fields (binding)**
Every RNG event record MUST include:

* `rng_counter_before_{hi,lo}`
* `rng_counter_after_{hi,lo}`
* `blocks`
* `draws` (decimal u128 string)  

**12.6.2 Envelope arithmetic (binding)**

* `blocks := u128(after) − u128(before)` (unsigned 128-bit delta).  
* `draws` MUST equal the **actual number of U(0,1)** values consumed by the event’s sampler(s). `draws` is independent of the counter delta and MUST be recorded even when `draws ≠ blocks`.  

**12.6.3 Deterministic / non-consuming events (binding)**

* If an event is deterministic (no random draw), it MUST record `draws="0"`, `blocks=0`, and `after == before`. 
* Non-consuming markers (diagnostics) MUST follow the same `before==after`, `blocks=0`, `draws="0"` rule. 

---

### 12.7 Core RNG logs (audit + trace)

**12.7.1 `rng_audit_log` (binding)**

* For each `{seed, parameter_hash, run_id}` partition that emits any RNG events, an **audit row MUST exist** and MUST be emitted **before** the first event in that partition.  

**12.7.2 `rng_trace_log` (binding: trace-after-each-event)**

* After **each** RNG event append, the producer MUST append **exactly one** cumulative trace row for the relevant `(module, substream_label)` key.  
* Validators reconcile totals on the final trace row per key:

  * `events_total` equals number of events,
  * `draws_total == Σ parse_u128(draws)`,
  * `blocks_total == Σ blocks`.  

**12.7.3 Label hygiene (binding)**

* Each RNG event row and trace row MUST carry stable identifiers:

  * `module`
  * `substream_label`
  * and when applicable: `context` (family-specific).
    These literals MUST be registry/profile controlled (not ad-hoc per run).  

---

### 12.8 RNG event families (schema-governed, profile-declared)

**12.8.1 Family registration (binding)**

* Every RNG event family MUST have:

  * a schema reference (layer schema catalog),
  * a dictionary/registry entry with canonical path + partitions,
  * and a declared owning state.  

**12.8.2 Family payload + envelope (binding)**

* Event records are **single flat JSON objects**; “envelope vs payload” is conceptual only. 
* The envelope fields defined in §12.6 are mandatory for all consuming families.

---

### 12.9 Deterministic concurrency posture for RNG-consuming states

**12.9.1 Concurrency units (binding)**

* If a state parallelises work, it MUST define a deterministic concurrency unit (e.g., “per merchant”) and MUST NOT interleave the same unit across workers. 

**12.9.2 Shard-count invariance (binding)**

* Changing thread/shard count MUST NOT change:

  * which draws occur,
  * the order in which per-unit draws are consumed,
  * the resulting selected sets/outcomes,
  * or any PASS receipt/hash evidence. 

**12.9.3 Stable iteration order (binding)**

* When an RNG family consumes a series of draws over a domain (e.g., iterating candidates), the iteration order MUST be defined by an authoritative order artefact (not by hash order, file order, or concurrency).  

---

### 12.10 Validator obligations for RNG governance

A validator/finalizer MUST be able to prove, for each run partition:

1. **Presence:** required audit and trace logs exist. 
2. **Coverage:** trace-after-each-event holds (no gaps). 
3. **Accounting:** envelope arithmetic is valid; totals reconcile.  
4. **Isolation:** only allowed families were written by each owning state. 
5. **Replay correctness:** re-derivation uses envelope counters and declared iteration order (never file order).  

---

### 12.11 Conformance checklist for §12 (Binding)

A segment/state is non-compliant if any of the following are true:

* It uses ambient RNG or an unpinned RNG engine.
* It emits an RNG event without valid `before/after/blocks/draws` fields or violates envelope arithmetic. 
* It emits `u` values with `u ≤ 0` or `u ≥ 1` where a uniform is required. 
* It fails to append exactly one trace row after each event append, or trace totals do not reconcile.  
* It relies on physical file/line order for meaning or replay. 
* It writes RNG families outside its declared ownership, or validators write RNG logs. 

---

## 13) Numeric determinism policy (Binding)

> **Binding intent:** Any computation that can affect a **branch**, **accept/reject**, **sort/order**, **integerisation**, **threshold/regime selection**, or any other decision-critical output MUST be **bit-stable** across machines, compilers, and permitted parallelism.

### 13.1 Policy artefacts and pinning (required)

The numeric determinism rail is defined by **pinned artefacts** that MUST be opened and included in the run’s opened-artefact set (and therefore participate in `manifest_fingerprint`):

* `numeric_policy.json` — declares FP environment, compiler/runtime constraints, and kernel policies.
* `math_profile_manifest.json` — pins the deterministic libm/profile (function set + digests).
* `numeric_policy_attest.json` — runtime attestation output proving the environment and self-tests passed.

A run MUST NOT proceed into any RNG draw or decision-critical computation unless these artefacts are present and the attestation passes.  

---

### 13.2 Floating-point environment (must hold)

For all decision/order-critical computations:

* **Format:** IEEE-754 **binary64** (`f64`) is mandatory. Diagnostics may downcast only if the producing state explicitly allows it. 
* **Rounding mode:** **Round-to-nearest, ties-to-even (RNE)** MUST be set and verified. 
* **FMA:** fused multiply-add MUST be **disabled** on decision/order-critical paths (no contraction). 
* **Subnormals:** MUST be honoured; **FTZ/DAZ MUST be off**. 
* **NaN/Inf:** Any NaN/Inf produced in model computations is a **hard error**. 
* **Decision-critical constants:** MUST be encoded as **binary64 hex literals** (no recomputation like `2*pi`). 

---

### 13.3 Deterministic math profile (libm pin)

Decision-critical calls to math functions MUST be executed under a **deterministic libm profile** pinned by `math_profile_manifest.json`.

* The profile MUST guarantee bit-identical results across supported platforms for the declared function set (e.g., `exp/log/log1p/expm1/sqrt/sin/cos/atan2/pow/tanh/lgamma` as needed).  
* Toolchains MUST NOT substitute host/system libm for pinned calls in decision-critical code paths. 

---

### 13.4 Build/runtime constraints (fast-math forbidden)

Implementations MUST enforce a build/runtime posture that prevents numeric drift:

* **No fast-math / unsafe FP optimizations**; **`fp_contract=off`** on guarded kernels; no algebraic reassociation on decision-critical paths. 
* If the implementation uses managed runtimes (Python/NumPy/JVM), decision-critical reductions MUST use the engine’s deterministic scalar kernels; BLAS thread counts (if present) MUST be pinned to avoid nondeterministic reductions. 
* Offloading decision-critical kernels to GPU is forbidden unless a deterministic math profile and non-fused posture are pinned and attested. 

All effective flags and relevant environment variables MUST be recorded in `numeric_policy_attest.json`.  

---

### 13.5 Reductions, accumulations, and linear algebra (fixed order)

* Any sum/dot/reduction feeding a decision or order MUST use a **serial, fixed-iteration-order** kernel with **Neumaier compensation** (or an equivalent pinned kernel) and MUST NOT be parallel-reduced.  
* External BLAS/LAPACK MUST NOT be used on decision-critical paths unless a deterministic backend is pinned as part of the math profile. 
* Evaluation order is normative: formulas must be executed in the **spelled order**; no reordering or fusion. 

---

### 13.6 Sorting, comparisons, and float total order

Where floats participate in sorting/keys:

* Use IEEE-754 **`totalOrder` semantics** for non-NaN floats; **NaNs are forbidden** (hard error). 
* `-0.0` MUST sort before `+0.0`. 
* Ties MUST be broken by deterministic secondary keys (e.g., ISO code then merchant_id), and sorts MUST be stable when keys compare equal.  
* “Epsilon-fudging” is forbidden for model decisions; ULP-based checks are reserved for self-tests.  

---

### 13.7 Quantisation and numeric serialization rules

* Quantisation/downcasting is **forbidden by default**. If a state requires it (e.g., persisting float32 diagnostics), it MUST explicitly declare:

  * the target type,
  * the rounding rule (default: **RNE**), and
  * the comparison rule used for validation.  
* For JSON emission of `f64`, emit numeric values using **shortest round-trip formatting** (no locale dependence). 
* Where a state uses fixed-dp quantisation for outputs, the dp, rounding mode (e.g., half-even), and any tie-break rules MUST be fully specified and deterministic.  

---

### 13.8 Determinism under concurrency

* Any computation that feeds a branch/order MUST execute in a **single-threaded fixed-order** kernel. 
* Map-style parallelism is allowed only when results are per-row and do not affect ordering/branching without passing through the serial kernel. 

---

### 13.9 Self-tests and attestation (must run before S1 / before first RNG draw)

The runtime MUST run numeric self-tests after sealing/pinning and before any RNG draw:

1. Verify rounding mode is RNE and FTZ/DAZ are off (subnormal preserved). 
2. Verify FMA contraction is disabled on guarded kernels. 
3. Verify deterministic libm profile via a fixed regression suite with expected bit patterns. 
4. Verify deterministic Neumaier kernel on adversarial sequences. 
5. Verify float total-order behavior on crafted arrays. 

On success, write `numeric_policy_attest.json` and include its digest in the opened-artefact enumeration. 

---

### 13.10 Failure semantics (abort)

Violations of numeric determinism controls MUST abort the run with deterministic error codes (examples include: FMA detected, FTZ/DAZ detected, non-RNE rounding mode, libm profile mismatch, NaN/Inf produced, decision-critical parallel reduction, NaN encountered in total-order key). 

---

### 13.11 Conformance checklist for §13 (Binding)

Non-compliance if any of the following are true:

* Decision-critical computations are not binary64/RNE or allow FMA/FTZ/DAZ. 
* Deterministic libm is not pinned/attested or host libm substitution is possible. 
* Decision-critical reductions are parallel or order-unstable.  
* Float sorting does not follow totalOrder semantics or permits NaNs. 
* Required self-tests/attestation are missing or occur after RNG has begun.  

---

## 14) Concurrency and parallelism rules (Binding)

### 14.1 Purpose

Concurrency is permitted only to improve throughput. It MUST NOT change:

* any governed output values,
* any governed output row-sets or declared ordering,
* any RNG consumption / envelopes / traces,
* any receipts, bundles, or PASS gates,
* any content hashes.

In other words: **worker-count invariance is a requirement**, not a best effort.

---

### 14.2 Where parallelism is allowed (normative scope)

A state MAY introduce parallelism at these boundaries only:

1. **Inter-state parallelism (orchestration-level)**
   States MAY run concurrently only if:

   * the dependency DAG says they are independent, and
   * they do not write to the same governed instance paths, and
   * required input gates for each are satisfied.

2. **Intra-state data parallelism (state-level)**
   A state MAY parallelize work across *independent concurrency units* (defined in §14.3).

3. **IO parallelism (writer-level)**
   A state MAY write multiple independent partitions concurrently, subject to **single-writer-per-instance** (see §14.7).

Any other parallelism model is forbidden unless explicitly added as a new allowed pattern in this constitution.

---

### 14.3 Concurrency unit (mandatory declaration)

If a state uses intra-state parallelism, it MUST declare a **concurrency unit**:

* A concurrency unit is the smallest entity that is processed **atomically** (not split across workers).
* The unit MUST have a stable **unit_id** (e.g., `merchant_id`, `country_iso`, `(merchant_id,country_iso)`).
* The state MUST define:

  * `unit_id` schema/type,
  * how units are enumerated (must be deterministic; no hash-map iteration),
  * how units map to shards/workers (any mapping is allowed **only if** worker-count invariance holds).

**Binding rule:** the same unit MUST NOT be processed by more than one worker in the same state invocation.

---

### 14.4 Worker-count invariance (required)

For any state that is parallel-capable:

* Changing the number of workers, shards, batch sizes, or scheduling strategy **MUST NOT** change outputs or gates.
* This MUST hold even if:

  * unit→worker assignment changes,
  * work completion order changes,
  * output part file counts differ (physical layout may vary), **as long as** the dataset’s declared equality rule is satisfied (row-set and declared ordering constraints).

**Decision-critical computations:** if a computation affects branching, acceptance/rejection, ordering, or gate outcomes, it MUST satisfy the stricter numeric determinism constraints in §13 (including fixed-order reductions).

---

### 14.5 Deterministic merge/join/reduction rules

Any state that merges work products from multiple units/workers MUST implement deterministic merge rules:

1. **Canonical merge key:** the state MUST define the exact key(s) used to merge/union results.
2. **No schedule dependence:** merge results MUST NOT depend on worker completion order.
3. **Ordering constraints:** if the Dataset Dictionary declares `ordering: [...]`, the merged output MUST satisfy it globally (not “per shard”).
4. **Reductions:** reductions MUST be performed in a deterministic order.

   * If a reduction is decision-critical, it MUST be serial fixed-order per §13.
   * If a reduction is not decision-critical but influences outputs, the reduction order must still be fixed and declared (no “parallel reduce and hope”).

---

### 14.6 Concurrency rules when RNG is involved

If a state is RNG-consuming (or emits RNG envelopes/events):

1. **No shared stream contention:** two workers MUST NOT interleave draws for the same `(stream key)` without a deterministic rule that preserves the same counter/evidence as single-thread execution.
2. **Preferred pattern:** RNG is keyed at the concurrency unit level (unit_id participates in the stream key), so each unit’s draws are independent of scheduling.
3. **Stable iteration order inside a unit:** if a unit iterates over a set (e.g., candidates), the iteration order MUST be defined by an authoritative order source, not by file enumeration or hash order.
4. **Event/trace coupling must hold under parallelism:** trace-after-each-event invariants remain mandatory (see §12). Parallel execution MUST still produce valid envelopes and reconcilable totals.

---

### 14.7 Single-writer-per-instance (hard IO rule)

Even under parallelism:

* For any governed dataset partition or bundle instance (the dictionary’s partition tuple), there MUST be at most **one** publisher.
* Parallel workers MAY write different instances, but MUST NOT write the same instance path.
* If concurrency makes collisions possible, the runtime MUST enforce a deterministic **claim/lock** mechanism (or orchestration-level mutual exclusion).

This complements §8’s atomic publish and immutability laws.

---

### 14.8 Forbidden concurrency patterns (explicit MUST NOT)

A state MUST NOT:

* rely on map/dict/set iteration order as an implicit scheduling or ordering mechanism,
* rely on filesystem listing order (files/parts) for meaning,
* use “work stealing” outcomes as a hidden input (e.g., “first N wins” based on completion),
* parallel-reduce decision-critical floating-point quantities,
* publish partial outputs and “finish later,”
* let retries reuse partially written outputs without deterministic cleanup and re-stage.

---

### 14.9 Failure and retry semantics under concurrency

If any worker fails:

* the state MUST fail closed,
* MUST NOT publish partial governed instances,
* MAY retry only after ensuring staged outputs are removed or deterministically quarantined (so the retry cannot observe inconsistent leftovers),
* retries MUST preserve the same run anchors and must not silently change scope tokens (except where explicitly allowed for attempt lineage artefacts).

---

### 14.10 Validator/finalizer obligations related to concurrency

Validators/finalizers MUST include checks sufficient to detect concurrency-induced nondeterminism, including at minimum:

* duplicate record identities in set-semantic logs,
* violations of declared writer sort / ordering constraints,
* missing/extra RNG events relative to trace totals,
* multiple “finalize” events where uniqueness is required by family schema,
* mismatched hashes or mismatched path↔embed lineage.

---

### 14.11 Conformance checklist for §14 (Binding)

Non-compliance if any of the following are true:

* outputs differ when worker count / shard count changes,
* RNG envelopes/traces differ across worker counts for identical anchors,
* merge/reduction results depend on scheduling order,
* more than one writer publishes the same governed instance,
* any forbidden concurrency pattern in §14.8 is observed.

---

## 15) Forbidden nondeterminism sources (Binding)

> **Binding rule:** A state MUST NOT allow any of the sources below to influence **governed outputs**, **RNG envelopes/logs**, **validation outcomes**, **gates**, or **content hashes**. If a forbidden source is observed, the state MUST fail closed with a deterministic error code.

### 15.1 Wall-clock time and time-adjacent sources — MUST NOT

A state MUST NOT depend on:

* `now()` / wall-clock timestamps,
* timezone / locale time rules (DST),
* file mtime/ctime as an input,
* “current day” unless it is a pinned policy input.

**Allowed:** timestamps for **observability only**, provided they do not affect control flow or outputs (and are never part of a hashed identity surface). This is explicitly enforced in 1A (timestamps are observational; replay is by counters/order rules, not time). 

### 15.2 Filesystem enumeration order — MUST NOT

A state MUST NOT derive meaning from:

* directory listing order,
* glob order,
* “first file seen” semantics,
* part-file numbering or creation order.

Where a state reads a set of inputs, it MUST treat them as a set and apply explicit deterministic ordering/keys if order matters. 1A calls this out directly: file order is non-authoritative for certain reads. 

### 15.3 Unordered iteration in language runtimes — MUST NOT

A state MUST NOT rely on:

* hash-map / dict / set iteration order,
* randomized hash seeds,
* pointer-address ordering.

If iteration order can affect results, the state MUST define a canonical sort order (using declared order authorities such as `candidate_rank` where applicable). In 1A, S3 is RNG-free and is the sole inter-country ordering authority via `candidate_rank` (downstream joins must use it, not “incidental” order).  

### 15.4 Ambient randomness and OS entropy — MUST NOT

A state MUST NOT use:

* `random()` / default PRNGs,
* `/dev/urandom`,
* UUIDs as “randomness” affecting outputs,
* nondeterministic sampling.

All randomness MUST come from the shared RNG Service under §12, with proper envelope accounting and trace coverage.

### 15.5 Environment / machine identity — MUST NOT

A state MUST NOT allow outputs to vary based on:

* hostname, PID, thread IDs,
* CPU feature flags unless explicitly governed by the numeric policy,
* number of cores, scheduling order, system load.

Worker-count invariance is mandatory (see §14).

### 15.6 Locale/collation/formatting defaults — MUST NOT

A state MUST NOT depend on:

* locale decimal separators,
* locale-aware string collation,
* platform-dependent unicode normalization,
* implicit timezone/locale formatting.

All formatting that affects persisted bytes must use the canonical serialization rules (§9).

### 15.7 Unpinned external reads — MUST NOT

A state MUST NOT read from:

* the network,
* “latest” datasets,
* mutable shared folders,
* environment variables (except those explicitly sealed/pinned and recorded).

All physical locations MUST be resolved via the Dataset Dictionary / Registry (dictionary bypass is forbidden). 

### 15.8 Nondeterministic parallel reductions — MUST NOT

A state MUST NOT:

* parallel-reduce decision-critical floats,
* rely on nondeterministic BLAS/GPU kernels for decision paths,
* allow race conditions to determine “winner” selections.

If parallelism exists, the merge/reduction order must be fixed and declared (§14), and decision-critical reductions must obey §13.

### 15.9 Serialization nondeterminism — MUST NOT

A state MUST NOT emit hashed/compared artefacts using:

* non-deterministic JSON key order,
* YAML parse→dump round trips,
* platform-dependent compression settings (unless pinned),
* variable chunking/part-splitting **as a semantic input**.

If physical layouts may vary, identity must be based on declared rowset + ordering constraints and/or deterministic composite digests (§9).

### 15.10 Instrumentation affecting semantics — MUST NOT

Metrics, counters, debug logs, and profiling MUST NOT affect control flow or outputs (no “if debug then change behavior”). 1A enforces this explicitly: metrics update after events but do not affect control flow. 

### 15.11 Hidden state across runs — MUST NOT

A state MUST NOT allow persisted or in-memory caches to change outputs unless:

* the cache is fully derivable from pinned inputs, and
* its use is deterministic, and
* it is either recomputed or validated as equivalent (hash/manifest) on reuse.

### 15.12 Validator nondeterminism — MUST NOT

Validators/finalizers MUST NOT:

* use random sampling unless deterministically seeded and declared,
* depend on file order,
* depend on wall-clock time.

S9’s replay posture is explicitly read-only and deterministic, issuing PASS/FAIL solely from pinned inputs + declared laws and emitting the gate by deterministic hashing rules. 

### 15.13 Required failure posture

If any forbidden source is detected (or cannot be ruled out), the state MUST:

* fail closed,
* emit deterministic diagnostics (state/segment IDs + anchor scope),
* and MUST NOT publish a PASS gate for the affected scope.

---

## 16) Determinism obligations by State Class (Binding)

> **Rule:** Every state MUST declare exactly one **State Class** (SC-A…SC-E) and one **RNG Posture** (RNG_NONE / RNG_NONCONSUMING / RNG_CONSUMING).
> A state’s determinism obligations are the **union** of:
>
> * the **global determinism laws** (§5, §12–§15),
> * the obligations for its **State Class** (this section),
> * and (if RNG posture ≠ RNG_NONE) the RNG governance obligations in **§12**.

### 16.1 Common determinism obligations (apply to all State Classes)

All states MUST:

1. **Be anchor-pure:** consume only pinned inputs under the Run Anchor; no undeclared reads (§6, §10).
2. **Be order-explicit:** if any ordering affects outputs, the ordering and tie-breakers MUST be spelled out; never rely on incidental iteration/file order (§14–§15).
3. **Be numeric-policy compliant:** decision/order-critical math MUST comply with §13; violations abort.
4. **Be concurrency-invariant:** if parallelism exists, worker/shard count MUST NOT change outcomes (§14).
5. **Be IO-deterministic:** atomic publish, no overwrite, idempotent reruns (§8), and canonical serialization (§9).
6. **Emit determinism evidence:** State Manifest MUST record inputs (refs+hashes), outputs (refs+hashes), and the determinism posture (state class + RNG posture + any declared order authority used).

---

### 16.2 SC-A — Pure Transform (RNG-free producer)

**Intent:** deterministic transformation producing governed artefacts without consuming randomness.

**SC-A MUST:**

* Declare **RNG_NONE** and MUST NOT instantiate or call any PRNGs.
* MUST NOT write or mutate RNG logs/event families. If RNG logs exist in the run scope, SC-A MUST treat them as read-only audit evidence.
* Define any ordering it introduces:

  * If output ordering is contractually meaningful (dictionary `ordering`), output MUST satisfy it globally.
  * If ordering is not meaningful, output MUST still be deterministic (stable writer sort or explicitly “unordered rowset” with deterministic identity evidence).
* Ensure all merges/joins are deterministic:

  * define join keys,
  * define duplicate handling (error vs deterministic collapse),
  * define stable tie-breakers for any “pick one” logic.
* Ensure outputs are worker-count invariant (parallel map allowed only if merge rules are deterministic and do not depend on scheduling).

**SC-A MUST NOT:**

* depend on wall-clock, locale, file order, hash iteration, or ambient env settings (§15).

**SC-A determinism evidence (minimum):**

* State Manifest lists: input refs+hashes, output refs+hashes, ordering rules used, and an explicit statement `rng_posture=RNG_NONE`.

---

### 16.3 SC-B — RNG Emitter (event-family producer)

**Intent:** produce stochastic outcomes and the auditable evidence of stochastic consumption.

**SC-B MUST (in addition to §12):**

* Declare RNG posture as **RNG_CONSUMING** or **RNG_NONCONSUMING**.
* Obtain randomness **only** via RNG Service streams derived from deterministic keys (run anchors + segment/state + purpose tag).
* Emit RNG event families as declared (schemas + registry/dictionary paths), and obey:

  * strict open-interval uniform rule,
  * envelope correctness (`before/after/blocks/draws`),
  * trace coverage (“trace-after-each-event”),
  * totals reconciliation.
* Define deterministic iteration order for any loop that consumes RNG:

  * candidate iteration MUST be based on an authoritative order artefact (or explicitly defined stable order),
  * never based on concurrency scheduling or input file enumeration.
* Be worker-count invariant:

  * if parallelized, concurrency unit MUST be declared,
  * stream keys SHOULD include concurrency unit identifiers to prevent cross-worker interleaving,
  * event emission MUST be schedule-independent (no “first N completed”).

**SC-B MUST NOT:**

* interleave draws for the same stream key across workers unless the interleaving rule is explicitly deterministic and produces identical envelopes/traces as single-thread.

**SC-B determinism evidence (minimum):**

* State Manifest lists: stream keys/purpose tags used (or a verifiable summary), families emitted, and the expected envelope/trace invariants that validators will enforce.

---

### 16.4 SC-C — Aggregator / Reduction / Join state

**Intent:** combine multiple upstream artefacts into derived artefacts; determinism risk is dominated by ordering and reductions.

**SC-C MUST:**

* Declare canonical merge semantics:

  * input set definition (which partitions and which gates must be present),
  * merge keys,
  * duplicate identity policy (fail vs deterministic resolution),
  * stable tie-breakers.
* Declare reduction semantics:

  * explicit evaluation order for reductions,
  * if decision-critical: serial fixed-order kernel per §13,
  * if not decision-critical but affects outputs: still fixed, declared order (no nondeterministic parallel reduce).
* Enforce worker-count invariance:

  * partitioning and merging MUST not depend on completion order,
  * global ordering constraints MUST be satisfied regardless of shard count.
* If RNG posture ≠ RNG_NONE (rare but allowed by the variability model):

  * SC-C MUST also satisfy SC-B’s RNG determinism constraints for the RNG-consuming part (no schedule dependence, envelope/trace correctness).

**SC-C MUST NOT:**

* infer semantics from filesystem ordering, dictionary iteration order, or “natural” arrival order of records.

**SC-C determinism evidence (minimum):**

* State Manifest records: upstream instances consumed (refs+hashes), merge/reduction rules version, and any authoritative order sources used.

---

### 16.5 SC-D — Receipt Writer (scoped validation + deterministic gate)

**Intent:** produce a **scoped PASS receipt** that downstream states may rely on, without weakening determinism.

**SC-D MUST:**

* Be **RNG_NONE** (default) unless explicitly declared otherwise in the segment profile (rare; treated as high risk).
* Be **read-only w.r.t. governed model outputs**: it validates and emits evidence; it must not “repair” data in-place.
* Compute receipts deterministically:

  * receipt scope MUST be explicit (e.g., parameter-scoped),
  * receipt content MUST be a deterministic function of validated artefact bytes/hashes and declared policy versions,
  * any bundle/index hashing MUST follow §7/§9 canonical rules.
* Enforce gating preconditions:

  * if receipt depends on upstream receipts, SC-D MUST require them (no PASS → no read).
* Be idempotent:

  * rerun under same scope MUST produce byte-identical receipt bundle (or deterministic no-op).

**SC-D MUST NOT:**

* include nondeterministic diagnostics (timestamps, random IDs) inside hashed receipt contents.

**SC-D determinism evidence (minimum):**

* Receipt bundle includes deterministic index + hash gate; State Manifest records what was validated and which receipt was emitted.

---

### 16.6 SC-E — Finalizer / Segment Egress Gate Publisher

**Intent:** deterministically certify the segment’s produced surfaces and publish the consumer-facing PASS gate.

**SC-E MUST:**

* Be **RNG_NONE**. Finalizers MUST NOT consume randomness.
* Be **read-only** over upstream artefacts: it verifies, reconciles, and gates; it does not mutate producers’ outputs.
* Re-derive deterministically:

  * replay-critical validations (including RNG reconciliation) MUST not depend on file order,
  * any re-derivation that depends on an order must use declared order authorities.
* Produce the segment’s **final validation bundle** deterministically:

  * bundle contents must be stable under replay,
  * `index.json` is complete and deterministic,
  * PASS flag hash rule is exactly as declared.
* Enforce “no PASS → no read” at the segment boundary:

  * SC-E defines the segment’s consumer gate; consumers MUST be able to verify it purely from declared rules and bytes.

**SC-E MUST NOT:**

* publish PASS if any determinism check fails (missing inputs, hash mismatch, envelope/trace mismatch, ordering violations, etc.).
* rely on “best effort” or partial evidence.

**SC-E determinism evidence (minimum):**

* Final bundle enumerates all validated artefacts (refs+hashes), includes pinning evidence, includes reconciliation outputs, and emits the final PASS gate deterministically.

---

### 16.7 Cross-class forbidden shortcuts (binding)

Regardless of class, a state MUST NOT:

* “fix up” outputs to make validation pass,
* backfill missing gates by assumption,
* treat any optional convenience surface as authoritative unless its declared receipt/gate is verified,
* treat a receipt as a substitute for the segment’s final consumer gate.

---

### 16.8 State-class determinism checklist (binding)

A state is non-compliant if any apply:

* State Class / RNG posture not declared or inconsistent with behavior.
* Outputs or logs vary under identical anchors when worker/shard count changes.
* Any ordering-affecting logic lacks explicit ordering + tie-break rules.
* RNG-consuming states violate envelope/trace invariants or depend on schedule/file order.
* Receipt/finalizer bundles are not byte-stable under replay or do not follow index+hash rules.
* Any forbidden nondeterminism source in §15 is present.

---

# Part III — Reproducibility Rail (Binding)

## 17) Reproducibility definition (Binding)

### 17.1 What “reproducible” means in this engine

A run (or any sub-scope of a run) is **reproducible** iff, for the same **declared reproduction keys** and the same **opened/pinned inputs**, the engine can re-execute and obtain **equal governed artefacts** under the segment’s declared **equality contract**, or deterministically fail with diagnostics and **without** publishing PASS gates.  

Reproducibility is therefore a contract over:

* **Inputs:** pinned by content bytes (policy/config pinning and opened-artefact sealing),
* **Execution regime:** numeric policy + RNG governance + allowed concurrency posture,
* **Outputs:** governed artefacts + their identity evidence (hashes, manifests, gates),
* **Equality:** defined per artefact class (byte vs canonical vs row-set).

---

### 17.2 Reproduction keys (what must be held constant)

Unless a Segment RDV Profile explicitly declares otherwise, the reproduction keys are:

1. **Stable identity keys (MUST be held constant):**

   * `manifest_fingerprint` (opened-artefact closure),
   * `parameter_hash` (policy/config closure),
   * `seed` / seed material used for modelling (when the artefact is seed-scoped).  

2. **Execution regime pins (MUST be held constant):**

   * Numeric policy regime (binary64/RNE/no-FMA/no-FTZ/DAZ + pinned math profile) and its attestation artefacts, which participate in the fingerprint closure.  
   * RNG governance (algorithm/version + stream derivation policy), likewise pinned via rails versions and/or opened artefacts.

3. **Attempt identity keys (MUST NOT be required for reproduction of governed model outputs):**

   * `run_id` and `scenario_id` are *attempt lineage* and by default are not allowed to change governed model outputs. They may partition logs only.  

**Binding rule:** A segment MUST declare for each artefact which subset of the above keys constitutes its identity scope (see §4 output scope classes). The default scopes in 1A demonstrate this separation: parameter-scoped outputs by `parameter_hash`, egress/validation by `manifest_fingerprint` (often with `seed`), and RNG logs by `{seed, parameter_hash, run_id}`.  

---

### 17.3 Equality contracts (what “equal” means)

Every governed artefact MUST have exactly one declared **equality contract**. Allowed contracts are:

1. **BYTE_EQUALITY (strongest):** exact byte equality of the artefact bytes.

   * Required for: flags, single-file JSON/JSONL when used as gates or identity evidence, and any artefact whose digest is used directly.

2. **BUNDLE_GATE_EQUALITY:** equality is defined by the bundle hashing rule and its gate:

   * `index.json` completeness and relative paths,
   * `_passed.flag` equals SHA-256 over concatenated raw bytes of indexed files in deterministic order.  
     If the bundle-gate equality holds, the bundle is considered equal even if non-authoritative filesystem metadata differs.

3. **ROWSET_EQUALITY:** equality is by set/multiset of rows under a declared primary key (duplicates forbidden), optionally plus declared writer-sort constraints.

   * Required for: Parquet datasets whose physical row/row-group order is out-of-contract (row-set equality is normative). 
   * JSONL event/log streams that are declared set-semantic (physical order across parts is non-authoritative; consumers must not depend on it). 

4. **CANONICAL_FORM_EQUALITY:** equality after applying the engine’s canonical serialization emitter (only permitted where canonicalization is explicitly defined and pinned).

5. **QUANTISED_VALUE_EQUALITY (rare):** equality after applying an explicitly declared quantisation policy (must be declared and validated; never implicit).

**Binding default:** If an artefact participates in a consumer gate or is included in a validation bundle index, it MUST be at least bundle-gate-equal or byte-equal under replay; otherwise PASS gating is meaningless. 

---

### 17.4 Idempotence as the operational form of reproducibility

For any governed artefact instance at its canonical dictionary/registry address:

* **Immutability:** the instance is immutable once published.
* **Idempotent rerun:** rerunning the producing state under identical reproduction keys MUST either:

  * no-op, or
  * publish an instance that is equal under the artefact’s equality contract (byte, bundle-gate, or rowset).  
* If an existing instance is present but not equal under the equality contract, the state MUST fail closed (integrity violation) and MUST NOT publish any PASS gate for that scope. 

---

### 17.5 What may vary without breaking reproducibility (explicit allowances)

The following are permitted to vary without violating reproducibility, provided the equality contract still holds:

* **`run_id` differences** across retries (logs are attempt-scoped; model outputs must not depend on `run_id`). 
* **Physical file layout** of partitioned datasets (part counts, file names) *only* when the artefact equality contract is rowset-based and writer-sort constraints (if any) still hold. 
* **Ops telemetry timestamps** and non-gating run reports, provided they do not enter hashed identity surfaces.

Any other variance MUST be declared (e.g., explicit attempt-unique artefacts).

---

### 17.6 Reproducibility obligations for validators/finalizers

Finalizers (segment egress validators) MUST:

* treat producers’ artefacts as read-only,
* check reproducibility-relevant invariants (lineage equality, hash evidence, RNG accounting reconciliation),
* and publish the consumer gate only when the declared equality contracts are satisfied.  

---

### 17.7 Reproducibility failure posture (fail-closed)

On any reproducibility breach (hash mismatch, lineage mismatch, missing pinned input evidence, equality contract violation):

* the run/segment MUST fail closed,
* MUST emit deterministic diagnostics identifying scope and offending artefacts,
* and MUST NOT emit PASS gates for the affected scope. 

---

## 18) Versioning and compatibility (Binding)

### 18.1 Purpose

Versioning exists to make two things simultaneously true:

1. **Replays are meaningful**: “same anchors ⇒ same outputs” is only defensible if the *execution regime* and *inputs* are pinned and discoverable.
2. **Evolution is safe**: segments can improve over time without silently breaking consumers or corrupting cache/reuse behavior.

This section defines what must be versioned/pinned, what counts as a breaking change, and how compatibility is managed.

---

### 18.2 The three version domains (normative split)

Every run MUST record (and final bundles MUST expose) version identity across three domains:

#### 18.2.1 Engine implementation version

* **`engine_build_id`** MUST identify the exact engine build (e.g., git commit + build hash).
* If engine code changes, reproducibility across time is not claimed unless the change is proven behavior-preserving under the conformance suite.

#### 18.2.2 Rails versions (RDV constitution dependencies)

* **`rails_versions`** MUST include at least:

  * `rng_policy_version`
  * `numeric_policy_version`
  * `validation_policy_version` (or content hash of the bundle)
  * `addressing_rules_version` (if addressing templates are versioned separately)

Any change to rails semantics is a compatibility-relevant change and MUST be recorded.

#### 18.2.3 Segment contract versions

For each segment involved in a run, the segment MUST have identifiable versions for:

* schema set (schema catalog version/content hash),
* dataset dictionary version/content hash,
* artefact registry version/content hash,
* segment RDV profile version/content hash.

These MUST be part of the opened-artefact closure (and thus fingerprinted) so that drift is impossible to hide.

---

### 18.3 Compatibility promises (what consumers may rely on)

A consumer MAY rely on the following surfaces being stable within a declared compatibility window:

1. **Run anchors** (`manifest_fingerprint`, `parameter_hash`, seed semantics, run/scenario IDs as attempt lineage).
2. **Canonical addressing templates** declared in dictionaries/registries.
3. **Artefact identity rules** (hashing, canonical serialization, equality contracts).
4. **Validation and gate semantics** (“no PASS → no read”; bundle hashing rules; gate map semantics).
5. **Schema stability** for consumer-facing artefacts (within semver rules below).

Anything not declared on these surfaces is *not* a compatibility promise.

---

### 18.4 Semantic versioning rules (binding)

This constitution uses SemVer principles for compatibility, applied to three kinds of things:

#### 18.4.1 Rails constitution semver

* **MAJOR**: any breaking change to:

  * run anchor required fields,
  * RNG engine/stream derivation/envelope semantics,
  * numeric determinism posture,
  * gate hashing rules / “no PASS → no read” mechanics,
  * required conformance tests.
* **MINOR**: additive constraints that do not break existing compliant producers/consumers (e.g., new optional fields with defaults, new state class type if backward compatible).
* **PATCH**: clarifications/typos/no-behavior changes.

#### 18.4.2 Schema semver (per dataset / per artefact kind)

A schema change is:

* **MAJOR** if it:

  * removes/renames fields,
  * changes field meaning,
  * tightens constraints such that previously valid data becomes invalid (unless explicitly declared as a bug fix requiring migration),
  * changes primary key / identity semantics.
* **MINOR** if it:

  * adds optional fields,
  * adds new enum values that consumers can safely ignore (only if consumers are required to treat unknowns as “ignore” or “fail” consistently).
* **PATCH** if it:

  * fixes descriptions or clarifies constraints without changing accept/reject behavior.

#### 18.4.3 Addressing/dictionary semver

A dictionary change is:

* **MAJOR** if it:

  * changes dataset_id,
  * changes path template,
  * changes partitioning keys or their order,
  * changes declared equality contract or ordering requirements.
* **MINOR** if it:

  * adds new datasets,
  * adds non-breaking metadata (notes, descriptions),
  * adds new optional convenience surfaces with explicit degrade ladders.
* **PATCH** for comments/typos only.

---

### 18.5 Compatibility windows and pinning rules

#### 18.5.1 Default: strict pinning

By default, runs are strictly pinned:

* exact `engine_build_id`,
* exact rails versions,
* exact contract versions/content hashes.

A replay that changes any of these is not a “replay” — it is a different run and must produce a different fingerprint.

#### 18.5.2 Declared compatibility window (optional)

If you choose to allow a compatibility window (e.g., “any PATCH within MAJOR.MINOR”), the segment MUST:

* declare the window explicitly in its Segment RDV Profile,
* publish compatibility tests proving equivalence under the equality contracts for consumer surfaces,
* and record the actual resolved versions used in the run evidence.

Without such proof, “windows” are forbidden.

---

### 18.6 Migration and coexistence (when breaking changes are necessary)

When a MAJOR change occurs that affects consumer surfaces, the engine MUST support one of:

1. **Parallel versioned surfaces**

   * New outputs written under a new dataset_id or versioned path segment,
   * Old outputs remain readable (and gated) for their version.

2. **Explicit migration tooling**

   * A deterministic migration job that reads old gated outputs and writes new gated outputs under new identity rules,
   * Migration must itself comply with RDV rails.

3. **Hard cutover with invalidation** (least preferred)

   * Explicitly mark older outputs as incompatible/unreadable by consumers that require newer semantics (gate map evolves).

Regardless of strategy, the change MUST be logged and the gate maps updated.

---

### 18.7 Backward compatibility rules for consumers

Consumers MUST:

* verify gates and hashes for the version they are reading,
* respect schema semver (if they claim compatibility),
* and fail closed when encountering:

  * incompatible major versions,
  * missing required fields,
  * changed equality contracts.

Consumers MUST NOT “best effort” parse incompatible outputs and proceed silently.

---

### 18.8 Cache/reuse safety across versions

Reuse is allowed only when all of these match for the scope:

* `manifest_fingerprint`
* `parameter_hash`
* relevant seed scope (if applicable)
* equality contract and ordering contract
* and the consumer gate for the partition

If any versioned surface differs (engine build, rails version, schema/dictionary identity), then reuse MUST be treated as unsafe unless an explicit compatibility proof exists.

---

### 18.9 Breaking change checklist (binding)

A change MUST be treated as breaking-risk (MAJOR unless proven otherwise) if it changes any of:

* required run anchor fields or their meaning,
* RNG algorithm, stream derivation, envelope fields, or trace rules,
* numeric determinism posture,
* canonical serialization rules that affect hashes,
* gate hashing rules or bundle index rules,
* dataset_id/path/partitioning keys,
* equality contract (byte/bundle/rowset),
* consumer “no PASS → no read” obligations.

---

### 18.10 Required evidence in validation bundles

Every segment final validation bundle MUST record:

* engine build id,
* rails versions,
* contract identities (schema/dictionary/registry/profile content hashes),
* and any declared compatibility window (if used).

This makes consumer verification and forensic replay unambiguous.

---

## 19) Reuse and caching rules (Binding)

### 19.1 Definitions (normative)

* **Reuse:** A state/segment chooses **not to recompute** an artefact because an **eligible existing instance** already exists at its canonical address (or within a declared cache surface) and is **readable** under the Gate Map.
* **Caching:** Persisting artefacts so that future executions may reuse them (either within the same run, across retries, or across separate runs that share the required identity keys).
* **Eligible existing instance:** An instance that passes the **Reuse Eligibility Predicate** (§19.3).
* **Readable:** Published **and** all required PASS gates verify (“no PASS → no read”).
* **Resume:** Continuing a partially completed write. **Forbidden** unless the artefact is explicitly declared **append-only/resume-safe** under §8 and §19.5.

---

### 19.2 Allowed reuse levels (what the engine MAY reuse)

Reuse is allowed only at these levels, and only when eligibility (§19.3) holds:

**19.2.1 Whole-segment reuse (preferred at boundaries)**
A consumer (including an orchestrator) MAY treat a segment as complete without recomputation if the segment’s **final consumer gate** for the relevant scope is present and verifies.

**19.2.2 Per-state reuse (internal)**
A state MAY skip its work if all of its declared outputs for the relevant scope are already present and readable under the state/segment Gate Map.

**19.2.3 Sub-output reuse (only if explicitly declared)**
A state MAY reuse a subset of its outputs only if:

* the state declares that subset as independently readable (separate gate/receipt), and
* downstream dependencies do not require the missing outputs.

**19.2.4 In-run memoization (non-persisted)**
In-memory caches (e.g., “read a reference table once”) are allowed if they are:

* derived solely from pinned inputs, and
* never used as an implicit source of truth (i.e., they do not replace provenance or gating).

---

### 19.3 Reuse Eligibility Predicate (mandatory checks)

A state/segment MUST NOT reuse an artefact instance unless **all** checks below pass:

**(A) Addressing + scope match**

* The instance address MUST match the Dictionary/Registry canonical path for that artefact.
* The instance MUST match the artefact’s declared **partition keys** (names + order).
* Any duplicated lineage token (path ↔ embedded) MUST be byte-identical.

**(B) Version / compatibility match**

* The instance MUST be produced under compatible versions:

  * rails versions (RNG/numeric/validation/addressing),
  * contract identities (schema/dictionary/registry/profile),
  * and any declared compatibility window (if used).
* If compatibility cannot be proven, reuse is forbidden.

**(C) Gate verification**

* All required PASS gates for reading that artefact (per the Gate Map) MUST be present and MUST verify according to their hashing rules.
* If a bundle exists but the PASS flag is missing/invalid, the instance is **not readable** and MUST NOT be reused.

**(D) Equality contract satisfied**

* The instance MUST satisfy its declared equality contract:

  * byte equality (for single-file identities),
  * bundle-gate equality (for proof packs/receipts),
  * rowset equality + ordering constraints (for partitioned tables/logs),
  * or any explicitly declared alternative.
* If the state cannot verify equality deterministically, it MUST NOT reuse.

---

### 19.4 Reuse decision protocol (what producers MUST do)

When a state considers reuse, it MUST execute this protocol:

1. **Check eligibility** using §19.3.
2. If eligible: **no-op** (do not rewrite), and emit a State Manifest entry indicating:

   * `decision = REUSED`,
   * the artefact refs + content hashes observed,
   * the gate refs verified (what PASS evidence was checked),
   * and the version identities relied upon.
3. If not eligible:

   * either **recompute from authoritative inputs**, or
   * **fail closed** if recomputation would violate immutability (e.g., an unreadable conflicting instance exists).

A state MUST NOT “half reuse” by reading from an instance that is not readable.

---

### 19.5 Append-only / resume-safe caches (rare; strictly governed)

Some artefacts may be designed as **append-only caches** (e.g., per-unit blocks added over time). This is allowed only if the Dictionary/Registry and segment profile explicitly declare:

* **Append law:** what is appended, what is immutable, and what constitutes “already present”.
* **Record identity:** a deterministic primary key (or block key) that prevents duplicates.
* **Skip-if-final rule:** if the target identity already exists:

  * if bytes/equality match → skip/no-op,
  * if mismatch → fail closed (idempotence violation).
* **Atomicity unit:** the smallest publish unit (e.g., “per block” or “per merchant”) and how atomic publish is enforced.
* **Validation posture:** how appended content is validated and what gate(s) make it readable.

If these declarations do not exist, “resume” and “append to an existing instance” are forbidden.

---

### 19.6 Cache invalidation and drift handling (fail-closed)

If a would-be reusable instance exists but fails any eligibility check:

* The instance MUST be treated as **unreadable**.
* Producers/consumers MUST fail closed unless the segment explicitly provides a deterministic remediation mode.

**Hard prohibitions:**

* A producer MUST NOT overwrite an existing published instance to “fix” drift.
* A consumer MUST NOT fall back to “best effort read” when PASS verification fails.

Where cleanup is supported, it MUST be deterministic and auditable (record what was quarantined and why).

---

### 19.7 Interaction with attempt identity (`run_id`, retries)

* **Attempt-scoped artefacts (LOG_SCOPED)** MAY be reused only within the same `{seed, parameter_hash, run_id}` scope unless explicitly declared otherwise.
* **Model outputs** MUST NOT depend on `run_id` by default and therefore may be reused across retries if their required gates and identity checks pass.
* A retry MUST NOT “stitch together” partial outputs from multiple attempts unless the artefact is declared append-only/resume-safe (§19.5).

---

### 19.8 Consumer-side caching of verification (allowed, but cannot weaken gates)

Consumers MAY cache *verification results* (e.g., “I already verified this PASS gate and these hashes”) provided:

* the cached decision is keyed by the same identity tuple used for verification (anchors + artefact refs + content hashes + gate hash),
* the cache is invalidated if any of those keys change,
* and the consumer still enforces “no PASS → no read”.

Optional external indices (e.g., a HashGate metadata service) MAY accelerate discovery, but they MUST NOT override local on-disk gate verification.

---

### 19.9 Conformance checklist for §19 (Binding)

Non-compliance if any of the following occur:

* An artefact is reused without verifying required PASS gates.
* A producer overwrites an existing published instance.
* A consumer reads an instance that is published but not readable (missing/invalid PASS).
* Reuse occurs across incompatible rails/contracts/versions without an explicit compatibility proof.
* Resume/append behavior is used without an explicit append-only declaration and deterministic skip-if-final/idempotence rules.

---

## 20) Drift detection and remediation (Binding)

### 20.1 Definition of “drift” (normative)

**Drift** is any condition where a governed artefact instance (or its proof/gate) is no longer consistent with the identity, determinism, validation, and pinning rules of this constitution.

Drift includes (non-exhaustive):

* **Identity drift:** recomputed `parameter_hash` / `manifest_fingerprint` differs from recorded values.
* **Gate drift:** a PASS gate is missing, malformed, or no longer verifies (e.g., `_passed.flag` hash mismatch).
* **Content drift:** bytes/rowsets differ from the equality contract under identical reproduction keys.
* **Contract drift:** schema/dictionary/registry/profile versions differ from what the run claims, or consumers interpret with a different contract set.
* **Determinism drift:** RNG accounting/trace coverage breaks, writer-sort breaks, ordering authority changes, or concurrency changes outputs.

S9 explicitly treats these as FAIL classes using canonical codes (e.g., `E_LINEAGE_RECOMPUTE_MISMATCH`, `E_WRITER_SORT_BROKEN`, `E_TRACE_TOTALS_MISMATCH`, etc.). 

---

### 20.2 Drift surfaces (where drift is detected)

Drift MUST be detectable at three layers:

1. **Producer-time (state writes):** structural/path/partition violations, forbidden nondeterminism sources, atomicity breaches.
2. **Validator/finalizer-time (segment gate):** re-derivation checks, hash checks, writer-sort checks, RNG envelope/trace reconciliation, lineage equality checks.  
3. **Consumer-time (read-time):** gate verification + identity checks prior to reading (the last line of defense). For 1A egress this is explicitly the `_passed.flag` verification against `index.json` ordering rules.  

---

### 20.3 Required drift detectors (binding minimum set)

A conformant engine MUST implement and enforce at least the detectors below.

#### 20.3.1 Gate verification drift

* A partition is **not readable** unless the required gate exists and verifies.
* For bundle-style gates, `_passed.flag` MUST match the SHA-256 over the raw bytes of all files listed in `index.json` (excluding the flag), in ASCII-lexicographic order of `path`.  
* If the bundle exists but `_passed.flag` is missing or mismatches, consumers MUST refuse reads (“no PASS → no read”).  

#### 20.3.2 Lineage drift (path ↔ embedded equality)

* Where lineage tokens exist in both path and embedded fields, **byte equality is mandatory**.
* Any mismatch is FAIL (`E_PATH_EMBED_MISMATCH` class).  

#### 20.3.3 Partition law drift

* Instances MUST be written under dictionary-declared partition keys (names + order). Misplaced partitions are FAIL (`E_PARTITION_MISPLACED`). 

#### 20.3.4 Pinning drift (hash recomputation mismatch)

* Validators MUST be able to recompute `parameter_hash` / `manifest_fingerprint` from sealed inputs and detect mismatches as FAIL (`E_LINEAGE_RECOMPUTE_MISMATCH`). 

#### 20.3.5 Ordering drift (writer sort + order authority)

* Where dictionary declares writer sort (e.g., `outlet_catalogue`), validators MUST enforce it within and across file boundaries; violations are FAIL (`E_WRITER_SORT_BROKEN`).  
* Order-authority drift (e.g., competing inter-country ordering) MUST be detected as FAIL (`E_ORDER_AUTHORITY_DRIFT`). 

#### 20.3.6 RNG drift (envelope + trace)

* For RNG-consuming families: per-event envelope arithmetic and trace-after-each-event coverage MUST reconcile; mismatches are FAIL (`E_RNG_COUNTER_MISMATCH`, `E_TRACE_TOTALS_MISMATCH`, `E_TRACE_COVERAGE_MISSING`, etc.).  

#### 20.3.7 Set-semantic log drift

* For set-semantic JSONL streams, duplicate identity rows are structural errors (FAIL), and physical order is non-authoritative. 

---

### 20.4 Fail-closed publication rule (binding)

On any detected drift that affects a governed scope:

* The engine MUST **fail closed** for that scope.
* The engine MUST NOT publish a PASS gate for that scope.
* If a bundle/proof-pack is written on FAIL, it MUST be written **without** `_passed.flag` so the partition is mechanically non-readable.  

This is the canonical remediation-by-design: “bundle may exist for diagnostics; PASS gate is the only read authorization.” 

---

### 20.5 Remediation principles (binding)

Remediation MUST obey these principles:

1. **No in-place fixing of governed instances.** Published governed artefacts are immutable; remediation MUST NOT overwrite or mutate them.
2. **Gates are authoritative.** If gate verification fails, the instance is treated as unreadable regardless of what “looks correct.”
3. **Remediation is additive.** Fixes occur by producing new governed outputs under new identity (new `manifest_fingerprint`, new dataset_id/versioned path, or new semver surface), not by editing existing partitions.
4. **Forensics preserved.** When drift is detected, sufficient diagnostics MUST be retained to explain what failed (e.g., S9 bundle contents and failure codes).  

---

### 20.6 Remediation mechanisms (normative options)

A compliant platform MUST support at least one of the following remediation mechanisms; it MAY support more than one.

#### 20.6.1 Recompute under new identity (default)

* Fix the root cause (policy, code, data, numeric posture), then rerun.
* The rerun MUST naturally produce a new `manifest_fingerprint` when any opened artefact changes, and therefore produce a new fingerprint-scoped bundle/gate.

#### 20.6.2 Versioned coexistence

* Introduce new dataset_ids or versioned path segments for breaking changes.
* Consumers choose via contract version and gate map; old outputs remain intact but may be considered incompatible.

#### 20.6.3 Revocation record (post-PASS drift response)

If a previously PASSed partition is later detected as invalid (e.g., `_passed.flag` mismatch at read time), the system MUST support a **revocation record** that:

* is written **outside** the governed bundle folder (so it does not mutate the bundle),
* identifies the revoked scope (`manifest_fingerprint`, dataset_id, optional seed),
* records the reason (failure code taxonomy),
* and is itself governed (hashed + gateable) for audit.

*(Optional)* A central HashGate-like metadata service may mirror revocations, but cannot override local gate verification. 

---

### 20.7 Consumer obligations under drift (binding)

When a consumer detects drift (at minimum: missing/mismatching gates):

* It MUST treat the partition as **failed** and MUST refuse reads.
* It MUST NOT “best-effort” read or “fallback” to partial evidence.
* It SHOULD emit a deterministic diagnostic referencing the scope and offending gate.

For 1A egress this is explicitly: verify the fingerprint-scoped `_passed.flag` before reading `outlet_catalogue`; on mismatch/missing, abort the read.  

---

### 20.8 Drift workflows (binding behavior)

#### 20.8.1 Drift detected before PASS (validator failure)

* Validator publishes diagnostics (bundle) but withholds `_passed.flag`. 
* Remediation is “fix + rerun,” producing a new readable partition only when PASS succeeds.

#### 20.8.2 Drift detected after PASS (consumer-time gate mismatch)

* Treat as **compromised/unreadable** immediately (no PASS → no read).
* Emit revocation record and quarantine/investigate (without mutating original).
* Only remediation path is recompute under a new identity (or versioned coexistence).

#### 20.8.3 Drift due to optional surfaces

Optional convenience surfaces MAY be absent without failing if the segment declares a replay path (e.g., derive membership from events). Using an optional surface requires its own receipt gate where declared.  

---

### 20.9 Conformance checklist for §20 (Binding)

Non-compliance if any of the following occur:

* A consumer reads governed data without verifying required gates (or continues after gate mismatch). 
* A producer/validator overwrites or mutates a published governed instance as “remediation.”
* Drift is detected but PASS gates are still emitted for the affected scope. 
* Drift is “handled” by silent fallback to partial/optional evidence without an explicit degrade ladder and required receipts. 

---

# Part IV — Validation Rail (Binding)

## 21) Validation taxonomy (Binding)

### 21.1 Purpose and posture

Validation in this engine is a **deterministic, fail-closed** system of checks that establishes whether governed artefacts are:

* **structurally valid** (schema/placement/keys),
* **identity-consistent** (anchors, path↔embed equality, hashes),
* **referentially consistent** (FKs),
* **deterministically consistent** (ordering, RNG envelopes/traces, replay laws),
* and (where declared) **realism-acceptable** (corridors/thresholds).

Validation is not a single monolith: segments MAY validate at multiple points (receipts + finalizer), but the *taxonomy* below is shared so that “PASS” means the same kind of thing everywhere. S9’s posture illustrates this sequencing: it completes structural/identity/referential checks **before** RNG accounting or replay checks. 

---

### 21.2 Validation scopes (where checks apply)

A segment MUST classify each validation check as belonging to one (or more) of these scopes:

1. **Artefact-scope** (per dataset/log/bundle instance)
2. **State-scope** (within a producing state; includes per-state receipts)
3. **Segment-scope** (finalizer checks across multiple states and publishes the consumer gate)
4. **Consumer-scope** (read-time verification: gate + identity verification prior to use)

The Segment RDV Profile MUST declare which scopes exist for that segment and which gates each scope produces/consumes.

---

### 21.3 Validation classes (normative taxonomy)

Every segment MUST map its checks (and failure codes) into the classes below. A single check MAY fall into multiple classes, but a segment MUST be able to report failures “by class”.

#### V1 — Schema & domain validity (structural)

**What it asserts:** Each artefact conforms to its authoritative schema: required fields, types, patterns/domains, enums, and per-row structural constraints.
**Failure posture:** Structural FAIL; no PASS gate.
**Example failure codes:** `E_SCHEMA_INVALID`. 

#### V2 — Placement, partitions, and path↔embed equality (structural)

**What it asserts:** Artefacts live under the Dictionary path template with declared partition keys, and any duplicated lineage values (path token vs embedded column/field) are byte-identical. 
**Failure posture:** Structural FAIL; no PASS gate.
**Example failure codes:** `E_PARTITION_MISPLACED`, `E_PATH_EMBED_MISMATCH`. 

#### V3 — Primary/unique keys and writer sort (structural)

**What it asserts:** Declared PK/UK constraints hold per partition, and declared writer-sort/monotonicity constraints hold where specified (including across file boundaries).
**Failure posture:** Structural FAIL; no PASS gate.
**Example failure codes:** `E_DUP_PK`, `E_WRITER_SORT_BROKEN`.

#### V4 — Referential integrity (structural)

**What it asserts:** All declared FKs resolve against their targets (e.g., ISO code tables, seed lists, declared reference sets). 
**Failure posture:** Structural FAIL; no PASS gate.
**Example failure codes:** `E_FK_ISO_INVALID` (and any segment-specific FK failures). 

#### V5 — Gate/bundle integrity (structural; “proof-pack validity”)

**What it asserts:** Bundle folders (validation bundles, receipts) satisfy index+hash rules:

* every non-flag file is listed exactly once in `index.json`,
* paths are relative and ASCII-safe,
* `_passed.flag` equals the SHA-256 over concatenated raw bytes of indexed files in lexicographic `path` order (flag excluded).
  **Failure posture:** Structural FAIL; bundle MAY be written for diagnostics but MUST be written **without** `_passed.flag`. 

#### V6 — RNG structural discipline (structural)

**What it asserts:** RNG logs/event families are present where required, conform to schema, obey partition/path rules, and satisfy *structural* coverage requirements (e.g., “trace-after-each-event” presence).
**Failure posture:** Structural FAIL; no PASS gate.
**Example failure codes:** `E_TRACE_COVERAGE_MISSING`, plus per-family schema/discipline failures.

#### V7 — RNG accounting and replay consistency (determinism)

**What it asserts:** Envelope arithmetic, totals reconciliation, budget constraints, and replayability requirements (as declared by RNG governance) hold.
**Failure posture:** Determinism FAIL; no PASS gate.
**Example failure codes:** `E_RNG_COUNTER_MISMATCH`, `E_TRACE_TOTALS_MISMATCH`, `E_RNG_BUDGET_VIOLATION`, etc. 

#### V8 — Cross-state replay consistency (determinism)

**What it asserts:** Cross-state invariants are satisfied (e.g., outputs can be replay-checked against upstream logs/authorities; order-authority consistency holds).
**Failure posture:** Determinism FAIL; no PASS gate.
**Example failure codes:** segment-specific `E_S*_*` codes and `E_ORDER_AUTHORITY_DRIFT`. 

#### V9 — Realism / corridor checks (semantic health; declared by segment)

**What it asserts:** Run/segment outputs fall within declared realism corridors/thresholds (e.g., rates/quantiles/CUSUM). These are **policy-driven** and must fail-closed if policy is missing.
**Failure posture:** Validation FAIL; MUST NOT write `_passed.flag` for the affected scope. 
**Notes:** Realism checks MUST NOT run until V1–V4 structure is clean (e.g., duplicates/structure errors block corridor computation). 

---

### 21.4 Validation ordering and short-circuit rules (binding)

Validators/finalizers MUST run checks in this minimum order:

1. **V1–V4 (structural)** first: schema, placement, keys, referential integrity.
2. **V6 (RNG structural)** next if RNG is present/required.
3. **V7–V8 (determinism/replay)** next.
4. **V9 (realism/corridors)** last, and only if structure is clean.

**Short-circuit law:** If any structural class (V1–V6) fails for a scope, the validator MUST treat the scope as failed and MUST NOT proceed to compute “derived” or “health” metrics that assume structural correctness. This is explicitly reflected in the corridor validator posture (structure must be clean before corridors). 

---

### 21.5 Determinism requirements for validators (binding)

All validators/finalizers MUST themselves be deterministic:

* set/rowset semantics must not depend on physical file order,
* ordering must be driven by declared order authorities and deterministic sorts,
* numeric rules used in validation must comply with the numeric determinism rail.

(Example: corridor computation uses deterministic merchant ordering and binary64 constraints; S9 treats JSONL streams as sets and flags duplicates as structural errors.)

---

### 21.6 Validation outputs: evidence, decisions, and gates (binding)

For any validated scope, the validator MUST produce:

* **Evidence artefacts** (metrics/reports/diffs as declared),
* a **decision record** (PASS/FAIL + failure codes),
* and (on PASS only) the **PASS gate artefact**.

**FAIL rule:** On FAIL, the validator MAY publish a diagnostic bundle, but MUST NOT publish `_passed.flag` (so the scope remains mechanically unreadable).

---

### 21.7 Failure code taxonomy mapping (binding)

Each segment MUST maintain a canonical mapping from its failure codes to these classes. At minimum it MUST distinguish:

* **Structural** (V1–V6),
* **Lineage/determinism** (V7–V8),
* **Realism/corridor** (V9).

S9 provides an explicit example of structural vs determinism vs RNG accounting vs cross-state replay codes. 

---

## 22) Validation artefacts and formats (Binding)

> **Binding intent:** Validation outputs are **governed artefacts**. They MUST be deterministic, addressable, schema-described (where applicable), and (when used for gating) hash-verifiable.

### 22.1 Validation artefact classes (what exists)

A segment’s validation outputs MUST be expressible as a combination of:

1. **Evidence artefacts (non-gate, but governed)**

   * summaries (`*_summary.json`, `*_VALIDATION.json`)
   * diffs (`*.diff`, `*.json`, `*.txt`)
   * metrics tables (`*.parquet`, `*.csv`, `*.jsonl`)
   * plots (`*.png`, `*.svg`)
   * reconciliation artefacts (e.g., RNG accounting, checksums)
2. **Gate artefacts (read authorization)**

   * PASS gate flag files (`_passed.flag`)
   * (optionally) scoped receipts (folders) that include a PASS flag
3. **Proof packs (folders/bundles)**

   * validation bundles (segment finalizer output)
   * receipt bundles (state-scoped or parameter/seed-scoped gates)

All three classes MUST obey canonical serialization rules (§9), addressing/identity rules (§7), and publication semantics (§8).

---

### 22.2 Two allowed “gated folder” formats (bundles vs receipts)

Segments/states are allowed to gate-read surfaces using either of the following folder formats.

#### 22.2.1 **Indexed bundle folder** (preferred for segment finalizers)

A gated folder MAY be an **indexed bundle** containing:

* `index.json` (complete logical index of all non-flag files)
* `_passed.flag` (PASS gate; optional on FAIL)
* any number of evidence artefacts (plots, metrics, diffs, manifests, etc.)

**Binding rules:**

* Every file in the folder **except** `_passed.flag` MUST appear **exactly once** in `index.json`.
* Every `path` in `index.json` MUST be **relative**, contain no `..`, and be ASCII-normalised.
* `_passed.flag` MUST be computed from the file set referenced by `index.json` (see §22.4).

This format is the default for **segment egress validation bundles**.

#### 22.2.2 **Unindexed receipt folder** (allowed for small scoped receipts)

A gated folder MAY be an **unindexed receipt** containing:

* one or more evidence files (e.g., `S6_VALIDATION.json`)
* `_passed.flag` (PASS gate; optional on FAIL)

**Binding rules:**

* The digest used in `_passed.flag` MUST be computed over **all non-flag files** present in the receipt folder using a deterministic file enumeration rule (see §22.4.2).
* No consumer is allowed to infer semantics from filesystem enumeration order.

This format is allowed for **state-scoped receipts** (e.g., parameter-scoped or seed/parameter-scoped receipts).

---

### 22.3 Validation bundle (segment finalizer output)

If a segment exposes consumer-facing artefacts (egress surfaces), it MUST produce exactly one **final validation bundle** per declared consumer scope (typically fingerprint-scoped).

#### 22.3.1 Location and partitioning

* The bundle MUST live at the canonical dictionary/registry path and MUST be partitioned by the declared scope keys.
* Recommended standard for fingerprint scope: `…/validation/fingerprint={manifest_fingerprint}/` (path label standard), but the Dataset Dictionary remains authoritative if legacy labels exist.

#### 22.3.2 Minimum required contents (by *role*, not by filename)

The final validation bundle MUST include evidence covering these roles:

1. **Run metadata / run anchors** (what run did this validate?)
2. **Pinning evidence** (what parameter set and opened artefact set were sealed?)
3. **Structural validation summary** (schemas, partitions, PK/UK, FK checks)
4. **Determinism/RNG reconciliation** (if RNG exists in the segment scope)
5. **Egress identity evidence** (checksums/rowset identity for consumer datasets)
6. **Bundle index** (`index.json`)
7. **PASS gate** (`_passed.flag` written only on PASS)

Segments MAY choose their own filenames for items (1)–(5), but MUST declare a stable mapping in the Segment RDV Profile if they do not use the default names (see §27).

---

### 22.4 PASS gate file (`_passed.flag`) format and hashing rules

#### 22.4.1 File format (exact)

`_passed.flag` MUST be a single-line ASCII file with content:

`sha256_hex = <hex64>`

Where `<hex64>` is lower-case hex and MUST match the pattern:
`^sha256_hex = [a-f0-9]{64}$`

#### 22.4.2 Hash input rule (what bytes are hashed)

The `<hex64>` value MUST be the SHA-256 of the **concatenation of raw bytes** of the governed files in scope, in a deterministic order:

* **If `index.json` exists (indexed bundle):**

  1. Extract the list of `path` entries from `index.json`
  2. Sort them by ASCII-lexicographic order
  3. For each path in that order: read the referenced file as raw bytes
  4. Concatenate those bytes (exclude `_passed.flag`)
  5. SHA-256 the concatenation → `<hex64>`

* **If `index.json` does not exist (unindexed receipt):**

  1. Enumerate all files in the receipt folder **excluding** `_passed.flag` (and excluding any temp/staging files by rule: temp files MUST NOT be present in a published receipt)
  2. Compute each file’s relative path from the receipt root
  3. Sort relative paths by ASCII-lexicographic order
  4. Concatenate raw bytes of those files in that order
  5. SHA-256 the concatenation → `<hex64>`

**Binding:** The hashing algorithm and ordering rule are part of the consumer contract. Changing either is a breaking change unless versioned as a new gate surface.

---

### 22.5 `index.json` format (for indexed bundles)

If a gated folder uses `index.json`, then:

#### 22.5.1 Index semantics

* `index.json` is a **logical index** of bundle contents, not merely a directory listing.
* It MUST include enough information for a consumer/reviewer to understand what each artefact is.

#### 22.5.2 Minimum index schema

At minimum, `index.json` MUST be representable as a table keyed by `artifact_id` with columns:

* `artifact_id` (string, unique within bundle; primary key)
* `kind` (string; e.g., `plot|table|diff|text|summary`)
* `path` (string; relative path inside bundle)
* `mime` (optional string)
* `notes` (optional string)

Segments MAY extend the index entries with additional optional fields, but MUST preserve:

* uniqueness of `artifact_id`
* relative path restrictions
* deterministic hashing rule that uses the `path` list

---

### 22.6 Checksums artefacts (egress identity evidence)

Where a segment publishes consumer datasets (Parquet/JSONL/etc.), the final validation bundle MUST include deterministic identity evidence for those datasets. This MUST be one of:

* **Per-file checksums + composite digest** (recommended), or
* A declared deterministic **rowset hash** scheme.

#### 22.6.1 Recommended checksums structure (normative shape)

A checksums artefact SHOULD include, for each consumer dataset instance validated:

* dataset identifier (`dataset_id`)
* scope keys (e.g., `manifest_fingerprint`, optional `seed`)
* `files: [{ path, sha256_hex, size_bytes }, …]` where `path` is relative to dataset root
* `composite_sha256_hex` computed as SHA-256 over concatenation of raw bytes of the listed files in ASCII-lexicographic order of `path`

If a segment chooses a different method, it MUST declare it in the Segment RDV Profile and the validator MUST enforce it.

---

### 22.7 RNG accounting/reconciliation artefacts (conditional requirement)

If any state in the segment scope emits RNG events/logs, the final validation bundle MUST include an **RNG accounting** artefact that is sufficient to prove:

* required audit/trace logs exist for each run scope,
* trace-after-each-event coverage holds,
* per-family envelope arithmetic is valid,
* totals reconcile (`events_total`, `draws_total`, `blocks_total`),
* and any family-specific budgets/caps are respected.

If the segment is RNG-free, this artefact MAY be omitted (and MUST be absent from the bundle index if omitted).

---

### 22.8 Receipts (state-scoped PASS gates)

A segment MAY define intermediate receipts (parameter-scoped, seed/parameter-scoped, etc.) to protect downstream reads of convenience surfaces.

**Binding rules for receipts:**

* Receipt location MUST be canonical (dictionary/registry or explicitly co-located adjacent to the dataset it gates).
* Receipt MUST include:

  * one deterministic evidence file (at minimum a summary JSON),
  * and `_passed.flag` written only on PASS.
* Receipt `_passed.flag` hashing MUST follow §22.4.2 (unindexed receipt rule unless an index is used).
* Receipt MUST NOT be treated as a substitute for the segment’s final consumer gate unless explicitly declared (and treated as breaking-risk).

---

### 22.9 FAIL outputs and diagnostics (fail-closed)

On validation FAIL:

* Evidence artefacts MAY be published (diagnostics are encouraged),
* but `_passed.flag` MUST NOT be published for the failed scope.

This makes unreadability mechanical and enforces “no PASS → no read.”

---

### 22.10 Privacy and content restrictions for validation outputs

Validation artefacts MUST avoid embedding row-level sensitive content unless explicitly allowed by the dataset dictionary/registry classification:

* Prefer aggregated counts, hashes, and identifiers over raw payloads.
* If a segment needs row-level exemplars for debugging, they MUST be:

  * strictly scoped,
  * explicitly declared and schema-described,
  * and classified for retention/PII.

---

### 22.11 Conformance checklist for §22 (Binding)

Non-compliance if any of the following are true:

* `_passed.flag` format deviates from the single-line `sha256_hex = <hex64>` rule.
* `_passed.flag` digest is not computed using the deterministic file-set + lexicographic order rule.
* An indexed bundle’s `index.json` is incomplete (missing files), contains non-relative/unsafe paths, or has duplicate `artifact_id`.
* A segment publishes consumer egress surfaces without a final validation bundle + consumer gate.
* A validator publishes PASS for a scope while required evidence artefacts are missing (e.g., missing pinning evidence or missing RNG accounting when RNG exists).
* Consumers are able to read governed artefacts without verifying the required PASS gate.

---

## 23) Gate semantics and composition (Binding)

### 23.1 Purpose

Gates are the engine’s **mechanical read-authorization layer**. They ensure:

* **Validation is enforceable** (not advisory),
* **Consumers cannot accidentally read unverified outputs**, and
* Reuse/caching is safe (only readable, verified partitions are eligible).

### 23.2 Gate types (normative)

A segment/state MAY emit gates in the following forms:

1. **PASS Flag Gate**
   A single-file gate (e.g., `_passed.flag`) whose content is a deterministic digest over a declared file set (see §22.4).

   * **Role:** read authorization for a scope.
   * **Property:** verifiable by bytes; immutable once published.

2. **Receipt Gate (scoped)**
   A scoped proof folder (often smaller than the final bundle) containing evidence + a PASS flag gate.

   * **Role:** protect downstream reads of an *intermediate or convenience surface*.
   * **Property:** additive; never a substitute for final consumer gates unless explicitly declared.

3. **Final Consumer Gate (segment egress gate)**
   The authoritative segment-level gate produced by the segment finalizer (SC-E), typically attached to the segment’s final validation bundle.

   * **Role:** “this segment’s consumer surfaces are safe to read for this scope.”
   * **Property:** MUST be verifiable without running code (hash + index rules).

### 23.3 Gate scope (what a gate authorizes)

Every gate MUST declare exactly one **scope**:

* **Artefact Instance Scope:** authorizes one dataset/log/bundle instance (one partition tuple).
* **State Scope:** authorizes a declared set of outputs from a single state invocation (often still partitioned).
* **Segment Consumer Scope:** authorizes the segment’s declared consumer surfaces for a given segment scope (typically fingerprint-scoped; seed inclusion must be explicit).
* **Layer/Engine Scope (optional):** only allowed if explicitly introduced by a higher-level interface contract; never implicit.

**Binding:** A consumer MUST NOT infer scope from naming conventions; scope must be determinable from declared paths + profile metadata.

### 23.4 Gate properties (required for all gates)

Every gate MUST satisfy:

1. **Canonical location:** gate path is declared in the Dataset Dictionary / Registry / Segment RDV Profile (no ad-hoc placement).
2. **Deterministic verification:** verification is purely by declared hashing/identity rules (no “best effort”).
3. **Immutability:** once written, a gate MUST NOT change. If invalid, remediation is additive (see §20).
4. **Atomic publication:** a gate MUST only be published after the gated file set is complete (see §8.4).
5. **Anchor binding:** a gate must be bound to the correct run scope via partition keys (path tokens) and, where applicable, embedded evidence.
6. **Fail-closed:** missing or invalid gate ⇒ unreadable.

### 23.5 Gate Map (the dependency rule-set)

Every segment MUST publish a **Gate Map** (binding surface) that answers:

* For each **consumer read of dataset X**, **which gates must be verified** first?

The Gate Map MUST be sufficient for automated enforcement and MUST include:

* `consumer_id` (downstream state, segment, or external component),
* `reads` (dataset_id / artefact kind),
* `required_gates` (list),
* `verification_method` per gate (bundle-index method vs unindexed receipt method),
* `scope_keys` (which anchor keys define the gate scope),
* `on_missing_or_fail` (must be FAIL).

**Binding:** If a gate requirement is not in the Gate Map, consumers MUST treat it as **unknown** and fail closed (unless the segment marks the artefact as truly optional with a degrade ladder).

### 23.6 Composition semantics (how multiple gates combine)

Gate requirements compose with **AND** semantics by default:

* If `required_gates = [g1, g2, …]`, **all** must verify before read.

**Receipts are additive, not substitutive:**

* A receipt gate MAY be required for reading a specific intermediate/convenience artefact.
* The existence (or PASS) of a receipt gate MUST NOT be treated as authorizing segment consumer reads unless explicitly declared.

**Final gate does not automatically authorize everything:**

* The segment final consumer gate authorizes only the **consumer surfaces** declared in the segment profile.
* It does not automatically authorize reading internal intermediate artefacts unless those artefacts are explicitly included as consumer surfaces (or the Gate Map says so).

### 23.7 Optional surfaces and degrade ladders (gate-aware OR semantics)

OR semantics are allowed **only** through an explicit degrade ladder:

Example rule shape:

* Prefer reading `optional_surface` **if** `receipt_gate` verifies; otherwise reconstruct from authoritative sources `A+B` (which themselves require their own gates).

**Binding requirements:**

* The degrade ladder MUST be declared in the segment profile and Gate Map.
* The fallback path MUST be deterministic and MUST NOT weaken gating (fallback inputs still require PASS gates).
* “Optional” means “optional to exist”; it does **not** mean “readable without gates.”

### 23.8 Read-time verification protocol (binding for all consumers)

Before reading any governed artefact, a consumer MUST:

1. Resolve the artefact’s canonical path and scope keys (dictionary/registry).
2. Consult the Gate Map to find required gates.
3. For each required gate:

   * verify it using its declared method (bundle-index or receipt hashing),
   * verify scope match (partition keys and path↔embed equality where applicable),
   * verify the gate is not superseded by a declared revocation record (if your platform implements revocation per §20.6.3).
4. Record evidence of verification (gate refs + hash values + artefact refs + hashes) in its own state manifest/log.
5. Only then read the artefact.

**Binding:** If any step fails, the consumer MUST fail closed and MUST NOT proceed with partial reads.

### 23.9 Producer obligations (to make gate enforcement possible)

Any producer state that emits gated outputs MUST:

* Emit validation evidence deterministically,
* Publish outputs atomically,
* Publish PASS gates only after validation success,
* Withhold PASS gates on FAIL (diagnostics may still be published),
* Ensure the gate’s verification set matches the declared rules (index completeness, file enumeration stability, etc.).

### 23.10 Cross-segment and cross-layer composition

When a state in segment **B** reads an artefact produced by segment **A**:

* Segment B MUST treat segment A as an external producer and MUST follow the Gate Map:

  * verify A’s required gates (typically A’s final consumer gate for that scope),
  * verify any required receipts if B reads an A-internal convenience surface (rare; should be avoided).
* Segment B MUST record the verified gate refs/hashes as part of its own provenance.

**Binding:** Cross-segment reads MUST never bypass gates on the assumption that “the orchestrator already validated it.”

### 23.11 Gate failure semantics

On missing/invalid gates:

* The artefact is **unreadable**.
* Consumers MUST fail closed (no fallback to “partial read”).
* Producers MUST not attempt to “repair” by overwriting; remediation is additive (new identity / new run / versioned coexistence).

### 23.12 Conformance checklist for §23 (Binding)

Non-compliance if any of the following are true:

* A governed artefact can be read by any consumer without verifying required gates.
* A receipt gate is treated as a substitute for the final consumer gate without explicit declaration.
* Gate verification depends on filesystem order, wall-clock, or non-deterministic behavior.
* PASS gates are published for incomplete/partially-written instances.
* Gate scope is ambiguous or not determinable from declared paths + profile metadata.

---

## 24) Validator determinism requirements (Binding)

> **Scope:** applies to **all validators** (state-scoped receipt writers **SC-D** and segment finalizers **SC-E**) and to any state that produces **validation evidence** used for gating.

### 24.1 Determinism posture (non-negotiable)

A validator MUST be a deterministic function of:

* the **run anchor** (scope keys only, as declared),
* the **pinned inputs** it is allowed to read (artefact bytes + content hashes + pinned policies),
* and the **declared validation policy** for the scope.

A validator MUST NOT depend on:

* wall-clock time,
* filesystem enumeration order,
* runtime scheduling order,
* ambient environment state,
* or any ambient randomness.

### 24.2 Read model: treat inputs as sets, not “whatever order the OS gives”

Validators MUST read all multi-file/partitioned inputs using a **set-semantics** approach:

* A validator MUST NOT derive meaning from:

  * directory listing order,
  * glob order,
  * parquet part numbering,
  * jsonl shard order,
  * or event arrival order.
* If a check requires order, the validator MUST impose a **declared canonical order** (e.g., dictionary `ordering`, declared PK sort, or an explicitly declared “order authority” dataset).

### 24.3 Canonical ordering rules inside validators

When ordering matters, validators MUST:

* Sort using deterministic key order (ASCII / totalOrder rules where floats are present).
* Use stable tie-breakers (secondary/tertiary keys) so order is fully defined.
* Apply reductions in deterministic order (and if decision-critical, use the serial fixed-order kernels required by §13).

### 24.4 Sampling rules (by default: forbidden)

Validation MUST be **exhaustive** by default.

If a segment introduces **sampling** for performance, it MUST:

* declare sampling explicitly in the Segment RDV Profile,
* make sampling **deterministic** (seeded from stable run identity; fixed sample frame; fixed ordering before sampling),
* and ensure sampled validation cannot produce false PASS for correctness-critical constraints (schema/keys/gates/RNG accounting are never sampleable).

### 24.5 RNG reconciliation checks are deterministic and order-free

If the segment emits RNG logs/event families, validators MUST:

* verify audit/trace presence deterministically,
* verify trace-after-each-event coverage deterministically,
* verify envelope arithmetic and totals reconciliation deterministically,
* and perform replay checks using **envelope counters and declared keys**, never physical ordering.

Validators MUST NOT write RNG logs, mutate RNG state, or “repair” RNG evidence.

### 24.6 Numeric policy compliance inside validation

All validation computations that can affect:

* PASS/FAIL decisions,
* thresholds/corridors,
* ordering constraints,
* or deterministic hashes

MUST comply with the **Numeric Determinism Policy** (§13). Validators MUST fail closed if numeric posture is not attested or if forbidden numeric behavior is detected.

### 24.7 Output determinism: validation evidence must be stable

Validators MUST ensure their outputs are deterministic:

* Any evidence artefact included in a gated bundle/receipt MUST be byte-stable under replay.
* Validators MUST NOT embed nondeterministic fields inside gated evidence (timestamps, random IDs, environment-specific paths, etc.).
* If human-readable timestamps/telemetry are desired, they MUST be emitted as **non-gating** artefacts (outside the hashed file set) or under an explicitly “non-gating” classification that is excluded by a declared hashing rule (changing hashing rules is breaking-risk).

### 24.8 Publication rules for validators (must preserve fail-closed gating)

Validators MUST follow the IO rules in §8:

* Stage → validate → publish evidence → publish PASS gate **only on PASS**.
* On FAIL, evidence MAY be published, but `_passed.flag` MUST NOT be written.
* Validators MUST be idempotent: rerun under identical scope MUST produce identical evidence/gate results (or deterministic no-op).

### 24.9 Concurrency rules for validators

Validators MAY parallelize only if the parallelism is provably deterministic:

* parallel reads are allowed,
* parallel per-part checks are allowed,
* but any merge/reduction into PASS/FAIL decisions MUST be schedule-independent and use deterministic ordering rules.
* A validator MUST be worker-count invariant: changing worker/shard count MUST NOT change PASS/FAIL, hashes, or gated bundle bytes.

### 24.10 Required diagnostics on failure

On any validation failure, a validator MUST emit deterministic diagnostics that include:

* `segment_id`, `state_id` (validator identity),
* scope keys (e.g., `manifest_fingerprint`, `parameter_hash`, seed if applicable),
* failing validation class (V1–V9 taxonomy),
* failure code(s),
* and the minimal set of offending artefact refs/hashes.

Diagnostics MUST not include nondeterministic data inside gated evidence.

### 24.11 Conformance checklist for §24 (Binding)

A validator is non-compliant if any of the following are true:

* PASS/FAIL differs across replays with identical pinned inputs.
* Validation depends on filesystem/glob order or scheduling order.
* Sampling is used without explicit declaration and deterministic rules.
* RNG reconciliation relies on physical ordering or validators write RNG logs.
* Validator outputs included in gates contain nondeterministic fields.
* PASS gate is published despite missing required evidence or failed checks.

---

## 25) Consumer read rules (Binding)

> **Binding intent:** Reading governed engine artefacts is a **controlled operation**. A consumer (downstream state, downstream segment, or external platform component) MUST treat **gate verification** as a prerequisite to read, and MUST fail closed on any ambiguity.

### 25.1 Who is a “consumer”

A **consumer** is any process that reads governed artefacts, including:

* downstream states inside the same segment,
* states in other segments/layers,
* validators/finalizers (readers of producer outputs),
* and external components (Scenario Runner, Ingestion Gate, Feature Plane, Decision Plane, etc.).

All consumers are subject to the same read rules. “Internal” does not mean “trusted.”

---

### 25.2 Non-negotiable principles

1. **No PASS → no read.** If required gates are missing or invalid, the artefact is unreadable.
2. **Fail closed.** If a consumer cannot determine what gates are required, how to verify them, or whether scope matches, it MUST fail.
3. **Scope correctness before content.** Consumers MUST confirm the artefact belongs to the intended run scope (anchors/partition keys) before interpreting content.
4. **No implicit trust in orchestration.** “The orchestrator already validated it” is not a substitute for local verification.
5. **Optional does not mean ungated.** Optional surfaces may be absent, but if present and used they are still gated.

---

### 25.3 Authoritative inputs for consumers

Before reading, a consumer MUST use authoritative sources to resolve what it is about to read:

* **Dataset Dictionary / Artefact Registry**: canonical path template, partition keys, schema refs, equality contract, and any stated gate requirements.
* **Gate Map**: which gates are required for which reads (including receipts vs final gates, and any degrade ladders).
* **Segment RDV Profile**: segment-level declaration of consumer surfaces, receipts, and gate scopes.

If these sources conflict, the precedence rules in §2 apply.

---

### 25.4 Mandatory pre-read protocol

For every governed artefact read, a consumer MUST perform the following steps **in order**:

1. **Resolve identity intent**

   * Determine the intended scope keys (e.g., `manifest_fingerprint`, `parameter_hash`, optional `seed`) and the target artefact ID/kind.
2. **Resolve canonical location**

   * Construct the artefact’s canonical address using the dictionary/registry path template and scope keys.
3. **Consult Gate Map**

   * Determine the required gate set for this consumer and this artefact.
4. **Verify each required gate**

   * Verify gate file format (`_passed.flag`).
   * Verify gate digest using the declared method (indexed-bundle vs unindexed-receipt).
   * Verify gate scope matches the intended scope keys (partition tuple must match).
5. **Verify scope binding**

   * Where applicable, verify path↔embedded lineage equality (or metadata binding) for the artefact instance.
6. **Verify compatibility**

   * Confirm rails/contract version compatibility (or fail closed if incompatible/unknown).
7. **Record read evidence**

   * Persist evidence of what was verified and what was read (see §25.8).
8. **Only then read**

   * Perform the actual data read/scan.

**Binding:** If any step fails, the consumer MUST NOT read, MUST fail closed, and MUST emit deterministic diagnostics (§25.10).

---

### 25.5 Gate verification methods (binding)

Consumers MUST verify gates using exactly the method declared for that gate:

#### 25.5.1 Indexed bundle gate

* Use `index.json` to enumerate the file set.
* Hash the concatenation of raw bytes of indexed files in lexicographic `path` order (excluding `_passed.flag`).
* Compare to `_passed.flag`.

#### 25.5.2 Unindexed receipt gate

* Enumerate all non-flag files in the receipt folder.
* Hash the concatenation of raw bytes in lexicographic relative-path order.
* Compare to `_passed.flag`.

**Binding:** A consumer MUST NOT “approximate” verification (e.g., “the flag exists so it’s fine”).

---

### 25.6 What a consumer is allowed to assume after gate verification

Once required gates verify, a consumer MAY assume:

* The artefact instance satisfied the validations covered by those gates (per the segment’s declared gate meaning).
* The artefact is immutable and therefore will not change after PASS (per §8).

A consumer MUST NOT assume:

* that a receipt gate implies the segment final gate (unless explicitly declared),
* that a segment final gate authorizes reading internal intermediate artefacts (unless the Gate Map says so),
* that PASS implies cross-version compatibility (version checks are separate).

---

### 25.7 Optional surfaces and degrade ladders (binding OR semantics)

A consumer MAY follow an OR choice only if an explicit degrade ladder exists:

* **Primary path:** read optional surface **only if** its required receipt gate verifies.
* **Fallback path:** if optional surface missing or gate fails/missing, reconstruct from declared authoritative inputs **that themselves are gated**.

**Binding:** Fallback MUST be deterministic and MUST NOT weaken “no PASS → no read.”

---

### 25.8 Read evidence requirements (what consumers must record)

Every consumer MUST record a minimal **read evidence record** for each governed artefact it reads.

Minimum required fields:

* consumer identity (`consumer_id`, plus `segment_id/state_id` if applicable),
* run anchors in scope (`manifest_fingerprint`, `parameter_hash`, optional `seed`, plus attempt lineage if relevant),
* artefact identity (`artefact_id/kind`, canonical address, partition tuple),
* verified gate(s):

  * gate address(es),
  * `_passed.flag` value(s),
  * verification method used (indexed vs unindexed),
* (recommended) artefact identity evidence:

  * content hash / composite digest if available,
  * or a reference to the validation bundle that attested it.

**Binding:** This read evidence MUST be append-only and MUST be sufficient to reproduce “what inputs were read” during replay/forensics.

---

### 25.9 Partial reads, streaming, and “peeking”

* A consumer MUST NOT stream-read an artefact “just to inspect it” before verifying gates, unless it is operating under an explicitly declared **diagnostic mode** that:

  * never influences governed outputs,
  * never emits PASS gates,
  * and produces diagnostics only.

If a consumer performs diagnostic peeks, it MUST label them as non-governed and MUST NOT treat them as eligible inputs to any governed computation.

---

### 25.10 Failure behavior and diagnostics (binding)

On any read failure, the consumer MUST:

* fail closed (abort the consuming operation),
* emit deterministic diagnostics containing at minimum:

  * consumer_id,
  * artefact id + canonical address,
  * intended scope keys,
  * missing/failed gate(s) and verification step that failed,
  * incompatibility details if versioning mismatch caused failure.

A consumer MUST NOT “warn and continue” for any governed read.

---

### 25.11 Cross-segment / cross-layer reads (binding)

When reading outputs from another segment/layer:

* The consuming segment MUST treat the producing segment as an external producer.
* The default required gate is the producing segment’s **final consumer gate** for the intended scope.
* Reading a producing segment’s *intermediate* artefacts is forbidden unless:

  * the producing segment explicitly declares them as consumer surfaces, **or**
  * the Gate Map explicitly authorizes the read and specifies required receipts.

---

### 25.12 Conformance checklist for §25 (Binding)

A consumer is non-compliant if any of the following occur:

* It reads governed artefacts without verifying all required gates.
* It proceeds after missing/invalid `_passed.flag` or failed verification.
* It infers gate requirements without consulting Gate Map/Dictionary/Registry.
* It treats receipts as substitutes for final consumer gates without explicit declaration.
* It performs partial reads that influence governed outputs prior to gate verification.
* It fails to record minimal read evidence for governed reads.

---

# Part V — How segments/states declare compliance (Binding)

## 26) State Execution Contract (Binding)

> **Binding intent:** Every state, in every segment, MUST execute through a common contract so that RDV is enforceable. A state may differ in *domain logic* and *State Class*, but it MUST NOT differ in how it is anchored, how it reads, how it writes, how it validates, and how it emits evidence.

### 26.1 Contract overview (what a “state” MUST look like)

A state execution MUST be representable as:

`StateResult = ExecuteState(StateInputs, StateCapabilities)`

Where:

* **StateInputs** are fully pinned (anchors + policies + input refs + required gates),
* **StateCapabilities** are constrained engine-provided services (writer, RNG, validator runner, canonical serializers),
* **StateResult** includes governed outputs + required validation artefacts + gates + a State Manifest.

A state MUST NOT rely on any capability outside **StateCapabilities** to produce governed outputs (e.g., no direct filesystem writes, no ambient RNG, no ad-hoc hashing).

---

### 26.2 Required inputs (StateInputs)

Every state MUST receive, at minimum, the following inputs:

#### 26.2.1 Run Anchor (RunContext)

Must include all fields required by §6 (at minimum `manifest_fingerprint`, `parameter_hash`, seed material, `scenario_id`, `run_id`, plus `engine_build_id` and `rails_versions` where required).

#### 26.2.2 State identity

* `segment_id`
* `state_id`
* `state_class` (SC-A..SC-E)
* `rng_posture` (RNG_NONE / RNG_NONCONSUMING / RNG_CONSUMING)

#### 26.2.3 Resolved policy closure

A state MUST receive (or be able to resolve via pinned references):

* the **resolved policy bundle** for the segment scope (byte-pinned, name-sensitive), and
* any policy schemas required to validate the policies (schema-first posture per §10).

#### 26.2.4 Declared input artefact refs

A state MUST have an explicit list of inputs it intends to read, each expressed as:

* `artefact_id/kind`
* canonical address (or resolvable template + scope keys)
* declared equality contract / expected schema ref (as applicable)

#### 26.2.5 Declared input gate requirements

For each declared input artefact, the state MUST receive or be able to resolve (via the Gate Map):

* the set of required PASS gates to verify before reading that input.

**Binding:** If the state cannot resolve required gates for an input, it MUST fail closed.

---

### 26.3 Allowed capabilities (StateCapabilities)

The runtime MUST provide (and the state MUST use) only the following capabilities for governed work:

1. **Address resolver**

   * resolves canonical addresses from dictionary/registry templates + scope keys.

2. **Immutable writer**

   * stages, writes, and atomically publishes governed outputs (§8),
   * enforces no-overwrite / idempotence rules.

3. **Canonical serialization utilities**

   * canonical JSON emitter, bundle index emitter, hashing utilities (§9).

4. **Hashing service**

   * computes content hashes and composite digests deterministically (§7, §9).

5. **RNG service** (only used if `rng_posture != RNG_NONE`)

   * provides scoped streams and enforces envelope/trace duties (§12).

6. **Validation runner**

   * runs schema/invariant checks deterministically,
   * writes validation evidence artefacts and (on PASS) the correct gate artefacts (§21–§24).

7. **Read-gate verifier**

   * verifies required gates for inputs (indexed-bundle vs receipt hashing) (§25).

8. **Diagnostics logger**

   * may emit non-gating operational logs; MUST NOT influence governed outputs (§15).

**Binding:** Direct filesystem writes to governed locations, direct RNG instantiation, ad-hoc gate computation, and bypassing canonical emitters are forbidden.

---

### 26.4 Required outputs (StateResult)

Every state MUST produce:

#### 26.4.1 Governed outputs (0..N)

Any datasets/logs/bundles the state is responsible for, written only to canonical locations, with deterministic identity evidence (hashes) recorded.

#### 26.4.2 Validation evidence (required for governed outputs)

For each governed output scope produced, the state MUST produce validation evidence appropriate to its State Class:

* SC-A/SC-B/SC-C producers MUST produce at least schema/placement/key evidence for their outputs (either directly or via a declared receipt/finalizer path).
* SC-D/SC-E validators MUST produce validation bundles/receipts in the required formats (§22).

#### 26.4.3 PASS gates (only on PASS)

If the state is responsible for emitting a gate (SC-D receipt or SC-E final bundle gate), it MUST:

* publish `_passed.flag` **only** on PASS,
* withhold `_passed.flag` on FAIL.

#### 26.4.4 State Manifest (mandatory, governed)

Every state MUST emit a **State Manifest** that records, at minimum:

* identity: `{segment_id, state_id, state_class, rng_posture}`
* run anchors: `{manifest_fingerprint, parameter_hash, seed material id/hash, scenario_id, run_id, engine_build_id, rails_versions}`
* inputs consumed:

  * artefact refs + hashes (or verified bundle gate digests)
  * gates verified for each input (gate ref + `_passed.flag` value)
* policies used:

  * policy file basenames + digests (or a resolved bundle ref)
* RNG usage (if applicable):

  * stream keys/purpose tags summary
  * event families emitted
  * required accounting evidence pointers (audit/trace/event logs)
* outputs produced:

  * artefact refs + hashes
  * validation evidence refs
  * gates emitted (if any) and their digest values
* decision flags:

  * `computed` vs `reused` per output (reuse decisions must be recorded)

**Binding:** The State Manifest itself is a governed artefact: it MUST be canonical-serialized and hashable.

---

### 26.5 Mandatory execution protocol (the state “lifecycle”)

Every state MUST follow this protocol:

1. **Preflight**

   * verify Run Anchor presence + rails versions,
   * verify numeric policy attestation if required before decision-critical work (§13),
   * resolve canonical addresses for all declared inputs/outputs.

2. **Input gate verification**

   * consult Gate Map requirements,
   * verify required gates for each input (§25),
   * fail closed if any required gate is missing/invalid.

3. **Reuse decision (optional)**

   * if the state supports reuse, apply the Reuse Eligibility Predicate (§19.3),
   * if reused: record `REUSED` in State Manifest and skip compute for that instance.

4. **Compute**

   * execute deterministic logic under numeric policy,
   * if RNG is used: obtain streams via RNG service only; emit envelopes/events/traces per §12.

5. **Stage writes**

   * write outputs to staging locations using the immutable writer (§8),
   * compute required content hashes and/or composite digests.

6. **Validate**

   * run deterministic validations required for the output scope (§21–§24),
   * generate evidence artefacts.

7. **Publish**

   * atomically publish outputs and evidence (§8),
   * publish PASS gates only on PASS (§22–§23).

8. **Finalize State Manifest**

   * write the State Manifest after outputs/evidence/gates are in their final state,
   * publish it atomically.

---

### 26.6 Failure semantics (fail-closed, deterministic)

On any failure (missing gate, schema violation, RNG reconciliation failure, IO integrity error, nondeterminism detection):

* the state MUST fail closed,
* MUST NOT publish PASS gates for the affected scope,
* MAY publish diagnostics evidence (deterministically) provided it does not masquerade as PASS,
* MUST emit deterministic error codes and include scope identity in diagnostics:

  * `{segment_id, state_id, manifest_fingerprint, parameter_hash, seed (if applicable), run_id}`.

If any governed outputs were staged but not published, staging MUST be cleaned or deterministically quarantined so that retries cannot observe partial outputs (§8.6).

---

### 26.7 Idempotence and retry behavior (binding)

For identical reproduction keys and intended output scope:

* if outputs already exist and are readable, the state MUST either:

  * no-op and record reuse, or
  * recompute into a new identity scope (only if the scope keys legitimately changed, e.g., new fingerprint).

The state MUST NOT overwrite published governed instances.

Retries MUST NOT “stitch” partial outputs unless an append-only/resume-safe declaration exists (§19.5).

---

### 26.8 Conformance checklist for §26 (Binding)

A state is non-compliant if any of the following occur:

* it reads inputs without verifying required gates,
* it writes governed outputs without using the immutable writer / atomic publish,
* it instantiates its own RNG or bypasses RNG governance,
* it emits PASS gates on FAIL or without required evidence,
* it fails to emit a complete State Manifest,
* it allows wall-clock/FS order/env to influence governed outputs,
* it overwrites governed instances or publishes partial instances.

---

## 27) Segment RDV Profile Contract (Binding)

### 27.1 Purpose (what the profile is for)

Every segment MUST publish a **Segment RDV Profile**: a binding declaration that makes RDV enforceable **without reading the state-expanded prose**.

The Segment RDV Profile MUST be sufficient for an automated enforcer (or downstream consumer) to determine, for that segment:

* what each state is (State Class + RNG posture),
* what outputs exist and what scopes they live under,
* what gates/receipts exist and what they authorize,
* what must be verified before any read (“no PASS → no read”),
* what order authorities exist (so no competing ordering is invented),
* what optional surfaces exist and what the degrade ladders are.

This matches how 1A already works in practice: intermediate receipts (e.g., S5 parameter-scoped receipt) are explicitly separate from the segment’s final consumer gate (S9 fingerprint-scoped bundle + `_passed.flag`).  

---

### 27.2 Location, format, and pinning (mandatory)

**27.2.1 Location**

* The Segment RDV Profile MUST live in the segment’s **binding contracts pack** (same authority tier as dictionary/registry/schemas), not in narratives.

**27.2.2 Format**

* The profile MUST be machine-readable as **YAML or JSON**.
* A JSON-Schema SHOULD exist for it in the segment or layer schema set (so CI can validate it), and the profile MUST validate against that schema when present.

**27.2.3 Pinning**

* The profile MUST be treated as an **opened artefact** (it participates in `manifest_fingerprint` sealing), because changing gates/scopes/order-authority is a reproducibility-relevant change. (Your 1A sealing posture already enumerates sealed assets and derives fingerprints from opened artefacts.)  

---

### 27.3 Required header fields (minimum binding set)

A Segment RDV Profile MUST include:

* `segment_id` (e.g., `1A`)
* `profile_semver` (MAJOR.MINOR.PATCH)
* `effective_date` (YYYY-MM-DD)
* `authorities`:

  * `dataset_dictionary_id` (or file ref)
  * `artefact_registry_id` (or file ref)
  * `schema_set_id` (or file ref)
* `token_conventions`:

  * fingerprint path label in use (e.g., `fingerprint=` vs `manifest_fingerprint=`) and any declared aliases
    *(because your 1A ecosystem currently contains both label styles across docs and consumers must not guess)*  
* `consumer_gate` (declared explicitly; see §27.6)

---

### 27.4 State table (every state must be declared)

The profile MUST declare a complete ordered list of states:

For each `state` entry, the profile MUST include:

* `state_id` (e.g., `S5`)
* `state_class` ∈ {SC-A, SC-B, SC-C, SC-D, SC-E} (from §16)
* `rng_posture` ∈ {RNG_NONE, RNG_NONCONSUMING, RNG_CONSUMING}
* `inputs` (list of **dataset ids / artefact names** read)
* `input_gates` (for each input, which gate(s) MUST be verified prior to read)
* `outputs` (list of dataset ids / artefact names produced)
* `output_scopes` (PARAMETER_SCOPED / LOG_SCOPED / FINGERPRINT_SCOPED / EGRESS_SCOPED)
* `produces_gates` (list of gates this state emits, if any)
* `order_authority`:

  * either `none`, or the specific dataset(s) that are authoritative for ordering, plus the domain they order.

**Binding:** Any dataset/log/bundle produced or consumed by the segment that is present in the Dictionary/Registry MUST appear in at least one state’s `outputs` or `inputs` list.

*(Example of “order authority” in 1A: S3 candidate ranks are the single inter-country ordering authority and downstream states must not invent competing order; this is repeated in S5 and the dictionary entry for `s3_candidate_set`.)  

---

### 27.5 Gate declarations (receipts + final gates)

The profile MUST contain a `gates:` section that declares every gate the segment emits and how it is verified.

Each gate declaration MUST include:

* `gate_id` (stable identifier)
* `gate_type` ∈ {receipt, final_bundle_gate, other_flag_gate}
* `scope_keys` (exact partition keys that scope the gate)
* `path` (canonical location; dictionary/registry must agree)
* `verification_method` ∈ {indexed_bundle, unindexed_receipt}
* `file_set_rule`:

  * for indexed bundles: “hash bytes of files listed in `index.json` (excluding `_passed.flag`) in ASCII-lexicographic order of `path`”
  * for unindexed receipts: “hash bytes of all non-flag files in folder in ASCII-lexicographic relative-path order”
* `authorizes_reads_of` (dataset ids / surfaces this gate permits reading)

This matches your existing patterns:

* **S5 receipt** is parameter-scoped, unindexed, and hashes `S5_VALIDATION.json` (excluding `_passed.flag`) in ASCII order. 
* **S9 consumer gate** is fingerprint-scoped, indexed by `index.json`, and hashes files listed in `index.json` in lexicographic `path` order.  

---

### 27.6 Consumer surfaces and the segment consumer gate (mandatory)

If a segment publishes **consumer-facing outputs** (egress surfaces), the profile MUST declare:

* `consumer_surfaces:` list of dataset ids (e.g., `outlet_catalogue`)
* `consumer_gate:` a single authoritative final gate that must be verified before any read of those surfaces

**Binding:** The profile MUST treat receipts as **additive**, not substitutes for the consumer gate (unless explicitly declared as an exception). This is explicitly stated in S5 and S9: S5 PASS is not a substitute for the fingerprint-scoped egress gate.  

Where the dataset dictionary/registry already states consumer obligations, the profile MUST match them (no contradictions). Example: the `outlet_catalogue` dictionary entry explicitly repeats the consumer duty to verify the segment’s `_passed.flag` prior to reading.  

---

### 27.7 Optional surfaces and degrade ladders (mandatory when optionality exists)

If any dataset is optional (may be absent or may be bypassed), the profile MUST declare a degrade ladder:

For each optional surface:

* `surface_id`
* `when_present_required_gate` (often a receipt gate)
* `fallback_sources` (authoritative sources to reconstruct from)
* `fallback_required_gates` (gates required to read fallback inputs)
* `determinism_notes` (e.g., “reconstruct uses order authority X; file order irrelevant”)

This matches your 1A posture: if `s6_membership` is used, the S6 receipt MUST be verified before reading it; otherwise the system can fall back to event-based reconstruction paths.  

---

### 27.8 Cross-segment reads (explicitly declared)

If the segment reads artefacts produced by other segments/layers, the profile MUST declare:

* `external_inputs:` list of `{producer_segment, dataset_id, required_gate}`

This makes cross-layer integration mechanically safe: downstream segments don’t guess; they verify. (Your dictionaries already model “consumed_by” relationships; the RDV profile makes the **gate obligations** explicit.)  

---

### 27.9 Exceptions and compatibility window (rare, explicit)

The profile MAY declare:

* `exceptions:` list of explicitly approved deviations from this constitution (must reference §2.5 exception rules)
* `compatibility_window:` (if you adopt windows; otherwise omit and remain strict)

When version lines are pinned (schemas/dictionaries/registry), the profile MUST name them as compatibility assumptions. S9 explicitly documents the “v1.* line” assumptions for its dependent contract artefacts. 

---

### 27.10 Minimal illustrative shape (informative; not a template you must follow)

```yaml
segment_id: "1A"
profile_semver: "1.0.0"
effective_date: "2026-01-09"
authorities:
  dataset_dictionary: "dataset_dictionary.layer1.1A.yaml"
  artefact_registry: "artefact_registry_1A.yaml"
  schema_set: "schemas.1A.yaml + schemas.layer1.yaml"
token_conventions:
  fingerprint_path_label: "manifest_fingerprint"   # or "fingerprint"
states:
  - state_id: "S5"
    state_class: "SC-D"
    rng_posture: "RNG_NONE"
    inputs: ["settlement_shares_2024Q4", "ccy_country_shares_2024Q4"]
    input_gates: []
    outputs: ["ccy_country_weights_cache"]
    output_scopes: {ccy_country_weights_cache: "PARAMETER_SCOPED"}
    produces_gates: ["s5_receipt_gate"]
gates:
  - gate_id: "s5_receipt_gate"
    gate_type: "receipt"
    scope_keys: ["parameter_hash"]
    verification_method: "unindexed_receipt"
    authorizes_reads_of: ["ccy_country_weights_cache"]
consumer_surfaces: ["outlet_catalogue"]
consumer_gate: "validation_passed_flag_1A"
```

---

### 27.11 Conformance checklist for §27 (Binding)

A segment is non-compliant if any of the following are true:

* It has no Segment RDV Profile (or it is not machine-readable / not schema-valid when a schema exists).
* Any state is missing from the profile, or a state’s declared `state_class` / `rng_posture` contradicts actual behavior.
* Any produced/consumed governed dataset in the Dictionary/Registry is absent from the profile’s state IO declarations.
* Any read dependency lacks an explicit gate requirement (or relies on “implicit trust”).
* Optional surfaces exist without an explicit degrade ladder and required receipts.
* Receipts are treated as substitutes for the segment consumer gate without an explicit exception.
* The profile contradicts the Dictionary/Registry’s canonical paths, partitions, or consumer obligations.

---

## 28) Cross-layer integration posture (Informative → Binding if you want it strict)

### 28.1 Cross-layer integration is “by surfaced artefacts + gates”, not by internal logic

Across layers/segments, integration is achieved by treating each segment as a **producer** that publishes:

* **Declared consumer surfaces** (datasets/logs/bundles that downstream is allowed to read), and
* **Declared readiness evidence** (PASS gates / validation bundles) that authorize reads.

Downstream segments/layers must *never* depend on upstream internal procedures, intermediate scratch artefacts, or “how the upstream code does it”. They depend only on:

* the **output catalogue** (what exists + where), and
* the **gate map** (what must be verified before reading).

This is what makes layers composable: L2/L3 can safely consume L1 outputs without importing L1 mechanics.

---

### 28.2 Output catalogue: what upstream promises downstream can read

Each segment SHOULD publish (and the engine interface pack SHOULD consolidate) an **Output Catalogue** that enumerates:

* **Consumer dataset IDs** (egress surfaces)
* **Canonical paths + partition keys**
* **Schema refs**
* **Equality contract** (byte / bundle-gate / rowset)
* **Declared ordering (writer sort)** if meaningful
* **Required gate(s)** for readability

**Informative example (shape, not a mandate):**

* Segment `1A` exposes an egress dataset like `outlet_catalogue` (seed + fingerprint scope).
* The catalogue indicates its required gate is the segment’s final validation PASS flag (produced by S9) for that same fingerprint scope.

The catalogue is the *single place* downstream looks to answer: “What can I read and where is it?”

---

### 28.3 Gate map: readiness as a first-class interface

Alongside the catalogue, there SHOULD be an engine-wide **Gate Map** (or per-segment gate map entries) that states:

* **Consumer** (downstream state/segment/component)
* **Artefact being read**
* **Required gates** (final gate + any receipts if the artefact is optional/convenience)
* **Verification method** (indexed bundle vs receipt hashing)
* **Failure behavior** (always fail-closed)

This turns “no PASS → no read” into an enforceable *interface rule* rather than a narrative convention.

---

### 28.4 Cross-layer “contract handshake”

Cross-layer reads follow a simple handshake:

1. **Discover** the artefact via the output catalogue (ID → path template → partition keys).
2. **Verify readiness** via the gate map (which gate(s) must PASS).
3. **Verify identity** (scope keys + path↔embed equality where applicable + gate hash verification).
4. **Record evidence** (what was read and what gates/hashes were verified).
5. **Consume**.

This handshake is identical whether the consumer is:

* a downstream **engine segment**,
* an external component like **Scenario Runner**, **Ingestion Gate**, **Feature Plane**, etc.

---

### 28.5 Segment boundaries are “read-only by default”

To keep the engine modular:

* Downstream segments SHOULD treat upstream segments as **read-only producers**:

  * downstream does not “repair” upstream artefacts,
  * downstream does not emit upstream gates,
  * downstream does not reinterpret upstream internal logs as authoritative inputs unless explicitly catalogued as consumer surfaces.

If a downstream segment needs something, the upstream segment should expose it explicitly as a consumer surface (with gates), or the downstream should reconstruct deterministically from upstream consumer surfaces (also gated).

---

### 28.6 Optional convenience surfaces across layers

Some segments may publish optional surfaces (caches, membership tables, precomputed joins) to speed downstream.

Cross-layer rule-of-thumb:

* Optional surfaces are **never trusted by presence alone**.
* If used, they require a **receipt gate** (and the receipt must be declared in the gate map).
* If absent or un-gated, downstream must have a deterministic fallback path that uses authoritative gated inputs.

This prevents “silent performance optimizations” from turning into correctness dependencies.

---

### 28.7 Reuse/caching at cross-layer boundaries

Cross-layer reuse is safe only when:

* The consumer scope keys match (fingerprint/parameter/seed as declared),
* The required PASS gates verify for that scope,
* The contracts/rails versions are compatible (or explicitly proven compatible),
* And the equality contract holds.

In practice: downstream should prefer **whole-segment reuse** (“final gate already PASS, so skip recompute”) rather than reusing random intermediate artefacts.

---

### 28.8 Anti-patterns to avoid (informative)

* **Bypassing gates because “the orchestrator ran validation”**
  → breaks replay safety and makes consumer behavior non-auditable.
* **Reading intermediate artefacts across segments**
  → creates hidden coupling and breaks modularity when upstream refactors.
* **Treating logs as model inputs without explicit surfacing**
  → logs are typically attempt-scoped; importing them as inputs makes outputs attempt-dependent.
* **Letting path conventions drift per segment**
  → breaks discoverability and makes cross-layer tooling brittle (solve via profile-declared token conventions + catalogue + gate map).

---

### 28.9 Minimal cross-layer integration checklist (informative)

For every segment that will be consumed by another layer/component:

* [ ] Consumer surfaces listed in the output catalogue
* [ ] Canonical addressing + partition keys declared
* [ ] Required gate(s) declared and verifiable
* [ ] Gate map entry exists for each consumer read
* [ ] Consumer read protocol implemented (verify → record → read)
* [ ] Optional surfaces have receipts + fallback path
* [ ] Conformance tests include “consumer fails closed when gate missing”

---

# Part VI — Conformance and Definition of Done (Binding)
