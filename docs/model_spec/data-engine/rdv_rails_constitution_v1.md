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

