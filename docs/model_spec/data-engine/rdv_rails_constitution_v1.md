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
