# Decision Log & Audit Store (DLA) — Conceptual Spec Design Doc (non-spec) — Section Header Plan

## 0) Document metadata

### 0.1 Document header

* **Title:** *Decision Log & Audit Store (DLA) — Conceptual Spec Design (v0)*
* **Plane:** Real-Time Decision Loop / Decision Log & Audit
* **Doc type:** Conceptual (non-spec)
* **Status:** Draft / Review / Final
* **Version:** v0.x
* **Date (UTC):** `<YYYY-MM-DD>`
* **Designer (spec authoring model):** GPT-5.2 Thinking
* **Implementer (coding agent):** Codex

### 0.2 Purpose of this document

* Capture the **designer-locked v0 intent** for DLA in one place (no drift).
* Provide the roadmap for writing:

  * DLA1–DLA5 specs (behaviour/invariants)
  * `contracts/dla_public_contracts_v0.schema.json` (machine-checkable boundary shapes)
* Ensure DLA forces a consistent “must-record” set for explainability:

  * what we knew (inputs, versions, freshness, mode)
  * why we acted (policy refs, stage summary)
  * what we did (actions with idempotency keys)

### 0.3 Audience and prerequisites

* **Primary:** you (designer), Codex (implementer)
* **Secondary:** DF, DL, OFP, IEG, Actions, Observability/Governance owners
* **Prerequisites:**

  * DF v0 emits DecisionResponse with complete provenance
  * DL v0 outputs DegradeDecision (mode + mask + triggers)
  * OFP v0 provides feature_snapshot_hash + group versions + freshness + input_basis
  * IEG v0 provides graph_version when used
  * EB delivers admitted events at-least-once (so DLA ingest must be idempotent)

### 0.4 How to use this document

* This doc is **directional alignment** and a **question map**, not binding spec text.
* Normative truth lives in:

  * DLA specs (DLA1–DLA5), and
  * DLA contract schema file
* Every pinned decision here must appear later as a closed decision in specs/contracts.

### 0.5 Scope and non-scope

* **In scope:** canonical audit record shape, append-only rules, idempotent ingestion, corrections linkage, required query axes, quarantine on incomplete provenance, by-ref privacy posture, export posture.
* **Out of scope:** exact storage backend, indexing tech, query API transport, IAM implementation details (beyond posture), threshold numbers, infra topology.

### 0.6 Proposed repo placement (conceptual)

* `docs/model_spec/real-time_decision_loop/decision_log_audit/CONCEPTUAL.md`
* Related:

  * `specs/DLA1_...` → `specs/DLA5_...`
  * `contracts/dla_public_contracts_v0.schema.json`
  * `AGENTS.md` (implementer posture + reading order)

---

## 1) Purpose and role in the platform

### 1.1 Why Decision Log & Audit Store exists

Decision Log & Audit Store (DLA) is the loop’s **immutable flight recorder**. Its job is to persist an **append-only, reconstruction-ready** record of:

* what decision was made,
* what actions were intended,
* what inputs and context were used,
* what degrade posture applied,
* and what versions/freshness basis justified the decision.

One sentence: **“Persist enough immutable facts to reproduce the decision context and justify the outcome.”**

---

### 1.2 Where DLA sits in the loop

* **Decision Fabric (DF)** emits DecisionResponse (decision + actions + provenance).
* **DLA** ingests that output and writes the canonical audit record.
* **Decision Log consumers**:

  * investigators and analysts
  * governance/observability tooling
  * offline training assembly (exports)
* **Actions Layer** may later feed action outcomes back to DLA (optional v0+).

DLA is downstream of DF and provides the “source of truth” for explainability.

---

### 1.3 What DLA is system-of-record for (and what it is not)

DLA is authoritative for:

* the canonical **AuditDecisionRecord** (append-only)
* correction/supersession linkage (audit history)
* deterministic queryability across required axes (ids, pins, entity keys, time, mode)

DLA is not authoritative for:

* deciding outcomes (DF)
* executing actions (Actions Layer)
* computing features (OFP)
* resolving identities (IEG)
* validating/curating events (IG)

DLA records; it does not decide.

---

### 1.4 Why “by-ref + hashes” is the v0 posture

Audit must support privacy and reconstruction without becoming a raw data lake.

Pinned v0 posture:

* store pointers (`event_ref`) and digests (`feature_snapshot_hash`), plus essential metadata
* do not embed raw event payloads or full feature vectors in the audit store

This keeps DLA minimal, safe, and interoperable.

---

### 1.5 What DLA must enable for the platform

DLA must enable:

* **incident reconstruction** (“what did we know and why did we act?”)
* **audit proofs** (mode, features, versions, freshness, policy refs)
* **replay explainability** (input refs + watermarks/versions)
* **deterministic querying** (by ids, entity keys, pins, time, mode)
* **governed exports** for offline training and reporting

---

## 2) Core invariants (DLA “laws”)

> These are **non-negotiable behaviours** for DLA v0. If later specs or implementation contradict any of these, it’s a bug.

### 2.1 Append-only truth (no mutation)

* Canonical audit records are **immutable** once written.
* No in-place updates are allowed.
* Any correction is written as a new record (with explicit supersession linkage).

### 2.2 Deterministic identity posture

* v0 identity inheritance:

  * `decision_id = request_id = event_id`
* Every canonical audit record also has:

  * `audit_record_id` = deterministic hash of the audit payload.

### 2.3 Idempotent ingestion under duplicates

* Ingestion must be safe under DF retries and stream duplicates.
* Idempotent ingest key:

  * `(ContextPins, audit_record_id)`
* Duplicate ingest of the same audit_record_id is a **no-op**.

### 2.4 Corrections require explicit supersession linkage

* A second audit record for the same decision_id is only valid as a correction if it includes:

  * `supersedes_audit_record_id` pointing to the prior record.
* Otherwise it must not be accepted as canonical.

### 2.5 Provenance completeness is enforced

* Canonical audit records must include the required provenance fields.
* Missing required fields must not silently pass into canonical storage:

  * they are routed to audit_quarantine with reason `INCOMPLETE_PROVENANCE`.

### 2.6 By-ref privacy posture (v0)

* DLA stores **refs + hashes + metadata**, not raw payloads:

  * store `event_ref`, not embedded event payload
  * store OFP `feature_snapshot_hash` + metadata, not full feature vectors
* Raw embedding is forbidden in v0.

### 2.7 Joinability is mandatory

* Every canonical record carries:

  * ContextPins
  * input refs/hashes
  * outputs (decision/actions)
    so reconstruction is possible without guessing.

### 2.8 Deterministic queryability requirements

Canonical records must be queryable by:

* decision_id/request_id/event_id
* feature_keys_used (entity keys)
* ContextPins (run_id, manifest_fingerprint, etc.)
* time window
* degrade_mode

### 2.9 Deterministic export semantics

Exports must return the canonical record shape and be selected deterministically (no “latest by scan”).

---

## 3) Terminology and key objects

> These are the nouns used throughout the DLA conceptual design. Exact field shapes live in the DLA v0 contract schema; behavioural meaning is pinned in DLA specs.

### 3.1 decision_id / request_id / event_id

In v0 these are pinned to the same value:

* `decision_id = request_id = event_id`

This provides a stable join anchor across DF, Actions, and DLA.

---

### 3.2 audit_record_id

A deterministic hash of the canonical audit payload. Used for:

* idempotent ingestion
* canonical record identity and dedupe

---

### 3.3 supersedes_audit_record_id

A linkage field used when writing a correction record:

* points to the prior audit_record_id being superseded
* establishes explicit audit history

---

### 3.4 ContextPins

Run/world scoping identifiers:

* `scenario_id`
* `run_id`
* `manifest_fingerprint`
* `parameter_hash`

Every audit record carries ContextPins.

---

### 3.5 feature_keys_used

A list of canonical entity keys associated with the decision, used for indexing and investigations.

* shape is compatible with OFP FeatureKey / IEG EntityRef:

  * `key_type`, `key_id`

---

### 3.6 event_ref

An opaque by-ref pointer to the admitted event that triggered the decision.

* could be EB position, or a canonical event store locator

DLA stores the ref, not the raw payload.

---

### 3.7 OFP references

Fields that capture feature context used at decision time:

* `feature_snapshot_hash`
* `group_versions_used[]`
* `freshness[]` blocks (per group)
* `input_basis` watermark vector (OFP applied offsets)

---

### 3.8 IEG context block

Records whether IEG was used:

* if used: `graph_version`
* if not used: `{used:false, reason}`

---

### 3.9 DL degrade block

Records degrade posture used:

* `degrade_mode`
* full `capabilities_mask`
* triggers linkage (inline triggers or ref)

---

### 3.10 DF outputs block

Records decision outcome and action intents:

* `decision_outcome`
* `actions[]` including action_type and idempotency_key

---

### 3.11 DF policy/stage/timings block

Records DF provenance essentials:

* `df_policy_ref`
* stage_summary
* timings (start/end; optional stage timings)
* error/fallback flags (if any)

---

### 3.12 AuditDecisionRecord

The canonical append-only record persisted by DLA, containing:

* identity (decision_id + audit_record_id)
* ContextPins
* input refs/hashes/versions (event_ref, OFP, IEG, DL)
* outputs (decision/actions)
* provenance essentials
* audit metadata (ingested_at_utc, supersedes link if correction)

---

### 3.13 audit_quarantine record

A non-canonical append-only record capturing rejected/incomplete audit ingests.

* includes reason code `INCOMPLETE_PROVENANCE`
* includes enough evidence to debug upstream compliance

---

## 4) DLA as a black box (inputs → outputs)

> This section treats DLA as a black box: what it consumes, what it emits, and how it is used.

### 4.1 Inputs (what DLA consumes)

#### 4.1.1 Primary input: DecisionResponse from DF

DLA ingests DF’s DecisionResponse (decision + actions + provenance). DLA treats DF as the producer of decision truth, but enforces audit completeness.

#### 4.1.2 Optional input: action outcomes (v0+)

In later iterations, DLA may ingest:

* action execution outcomes from the Actions Layer
  to close the loop (“intent” vs “executed”), but this is optional in v0.

---

### 4.2 Outputs (what DLA produces)

#### 4.2.1 Canonical AuditDecisionRecord (append-only)

For complete records, DLA writes an immutable canonical AuditDecisionRecord containing:

* ContextPins
* decision identity (decision_id + audit_record_id)
* input references/hashes (event_ref, feature_snapshot_hash, graph_version, degrade info)
* decision outcome + actions (with idempotency keys)
* provenance essentials (policy refs, stage summary, timings)
* audit metadata (ingested_at_utc, supersedes linkage if correction)

#### 4.2.2 audit_quarantine record (append-only)

If an ingest lacks required provenance fields:

* DLA writes a quarantine record (append-only) with reason `INCOMPLETE_PROVENANCE`
* no canonical record is written

#### 4.2.3 Query and export surfaces

DLA supports:

* deterministic queries by required axes
* deterministic export slices for offline training/governance

Exact API and storage tech are implementation freedom; the semantics are pinned.

---

### 4.3 Boundary map (who uses DLA)

#### 4.3.1 Writers

* DF writes DecisionResponses into DLA (primary)
* Actions Layer may write outcomes later (optional v0+)

#### 4.3.2 Readers

* investigators and analysts
* governance/observability tooling
* offline training assembly and reporting pipelines

---

## 5) Pinned v0 design decisions (designer-locked)

> This section is the **designer intent snapshot** for DLA v0. These decisions are treated as fixed direction for DLA specs and the v0 contract schema.

### 5.1 Append-only + correction posture (v0)

* Canonical audit records are immutable.
* Corrections are written as new records only.
* Correction records must include `supersedes_audit_record_id`.

---

### 5.2 Identity posture (v0)

* `decision_id = request_id = event_id` (inherits DF v0 posture).
* `audit_record_id` is a deterministic hash of the canonical audit payload.

---

### 5.3 Idempotent ingestion key (v0)

* Idempotent ingest key is:

  * `(ContextPins, audit_record_id)`
* Duplicate ingest of the same key is a no-op.

---

### 5.4 Canonical AuditDecisionRecord minimum fields (v0)

Canonical records MUST include:

**Identity + pins**

* ContextPins
* decision_id/request_id/event_id
* audit_record_id
* ingested_at_utc

**Event input**

* event_ref (opaque)
* event_time_utc
* event_type

**DL used**

* degrade_mode
* full capabilities_mask
* triggers linkage (inline triggers or ref)

**OFP used**

* feature_snapshot_hash
* feature_keys_used[]
* group_versions_used[]
* freshness[] blocks
* input_basis watermark vector

**IEG used**

* graph_version when used
* else used=false + reason

**DF outputs**

* decision_outcome
* actions[] including idempotency_key

**DF provenance essentials**

* df_policy_ref
* stage_summary
* timings (start/end)
* error/fallback flags (if any)

---

### 5.5 Provenance completeness enforcement (v0)

* Missing required fields → no canonical record.
* Instead write audit_quarantine record with reason:

  * `INCOMPLETE_PROVENANCE`.

---

### 5.6 Privacy posture (v0)

* Store by-ref pointers + hashes + metadata only.
* Do not embed raw event payloads or full feature vectors in v0.

---

### 5.7 Query axes (must be indexable)

DLA must support deterministic query by:

* decision_id/request_id/event_id
* feature_keys_used (entity key)
* ContextPins (`run_id`, `manifest_fingerprint`, etc.)
* time window
* degrade_mode

---

### 5.8 Export posture (v0)

* Exports return the canonical audit record shape.
* Export selection is deterministic (pins + window + filters); no “latest by scan.”

---

### 5.9 Contracts packaging (v0)

* One schema file:

  * `contracts/dla_public_contracts_v0.schema.json`
* Includes canonical record shape plus quarantine record shape.

---

## 6) Modular breakdown (Level 1) and what each module must answer

> DLA is an **append-only audit recorder** with deterministic queryability. The modular breakdown exists to force DLA’s semantics (immutability, idempotent ingest, corrections, required axes, quarantine) to be answered *somewhere*, while leaving storage/indexing tech to the implementer.

### 6.0 Module map (one screen)

DLA is decomposed into 8 conceptual modules:

1. **Ingest & Normalize**
2. **Append-only Store**
3. **Idempotency & Dedup**
4. **Corrections Linker**
5. **Indexing / Query Surfaces**
6. **Quarantine (incomplete provenance)**
7. **Exports / Slices**
8. **Privacy / Governance Hooks**

Each module specifies:

* what it owns
* the questions it must answer (design intent)
* what it can leave to the implementer
* how it behaves locally vs deployed (conceptual)

---

## 6.1 Module 1 — Ingest & Normalize

### Purpose

Consume DF DecisionResponses and normalize them into the canonical AuditDecisionRecord shape.

### What it owns

* mapping from DecisionResponse → AuditDecisionRecord
* required field presence checks (completeness gate)
* stable deterministic ordering normalization (lists/maps)

### Questions this module must answer

* What fields must be present for canonical storage?
* How are missing fields detected and categorized?
* What canonical ordering rules are enforced before hashing audit_record_id?
* How are opaque refs (event_ref) carried without embedding raw payload?

### Can be left to the implementer

* ingestion transport (HTTP/queue/file)
* parsing libraries and DTO representation
* batching and throughput mechanics

### Local vs deployed operation

* semantics identical; local may ingest from files; deployed from service/event stream

---

## 6.2 Module 2 — Append-only Store

### Purpose

Persist canonical AuditDecisionRecords immutably.

### What it owns

* append-only write posture
* immutability rules and constraints
* storing ingested_at_utc and supersedes links

### Questions this module must answer

* What does “immutable” mean operationally (no updates)?
* How are correction records appended and linked?
* What is the canonical record history posture (keep all superseded records)?

### Can be left to the implementer

* storage backend selection
* partitioning and compression

### Local vs deployed operation

* identical semantics; deployed supports larger scale

---

## 6.3 Module 3 — Idempotency & Dedup

### Purpose

Ensure duplicate ingests do not create duplicate canonical records.

### What it owns

* audit_record_id computation posture (deterministic hash of canonical payload)
* idempotent ingest key: (ContextPins, audit_record_id)
* no-op semantics for duplicates

### Questions this module must answer

* What exact payload is hashed to form audit_record_id?
* What happens if the same record arrives twice (no-op)?
* How are collisions handled (should be practically impossible if hash is strong; still define posture)?

### Can be left to the implementer

* hash algorithm choice (as long as deterministic and stable)
* dedupe index storage backend

### Local vs deployed operation

* identical semantics

---

## 6.4 Module 4 — Corrections Linker

### Purpose

Handle correction records through explicit supersession linkage.

### What it owns

* requirement that corrections include supersedes_audit_record_id
* linking rules and validation
* query semantics for “current” vs “historical” views

### Questions this module must answer

* When is a record considered a correction?
* What must supersedes link point to, and what if it is missing/invalid?
* How do queries treat superseded records (return all vs return canonical latest)?

### Can be left to the implementer

* how “current view” is materialized (view/index)

### Local vs deployed operation

* identical semantics

---

## 6.5 Module 5 — Indexing / Query Surfaces

### Purpose

Provide deterministic queryability across required axes.

### What it owns

* required query axes presence and indexability
* deterministic selection rules for queries and “current” views

### Questions this module must answer

* How are records queryable by decision_id/request_id/event_id?
* How are records queryable by feature_keys_used (entity key)?
* How are records queryable by ContextPins and time windows?
* How are records queryable by degrade_mode?

### Can be left to the implementer

* exact indexing technology (DB indices, search engine)
* query API transport

### Local vs deployed operation

* local can be simple; deployed can be indexed/searchable

---

## 6.6 Module 6 — Quarantine (incomplete provenance)

### Purpose

Capture incomplete records without polluting canonical audit.

### What it owns

* reason code `INCOMPLETE_PROVENANCE`
* quarantine record shape
* operator inspectability posture

### Questions this module must answer

* What exact conditions route to quarantine?
* What evidence is stored in quarantine (missing field list, producer info)?
* How can operators reconcile quarantine back to upstream fix?

### Can be left to the implementer

* quarantine storage backend
* alerting and dashboards

### Local vs deployed operation

* semantics identical

---

## 6.7 Module 7 — Exports / Slices

### Purpose

Provide deterministic exports for offline training/governance.

### What it owns

* export includes canonical audit record shape
* deterministic export selection rules

### Questions this module must answer

* What filters define an export (pins + window + optional entity keys/mode)?
* How is export selection deterministic (no timestamp scan ambiguity)?
* What is the export format posture (implementation freedom; shape is pinned)?

### Can be left to the implementer

* export transport/storage mechanism
* file formats (parquet/json)

### Local vs deployed operation

* local can write files; deployed can write to lake

---

## 6.8 Module 8 — Privacy / Governance Hooks

### Purpose

Enforce by-ref discipline and define minimal governance posture.

### What it owns

* by-ref only posture (no raw payload embedding)
* access control posture (who can write/read)
* retention concept (configurable)

### Questions this module must answer

* Which fields are allowed vs forbidden (raw payloads forbidden)?
* Who can read canonical vs quarantine records?
* What retention posture exists (time window + archival/deletion)?

### Can be left to the implementer

* IAM implementation details
* retention exact numbers and archival tooling

### Local vs deployed operation

* local may be relaxed; deployed must enforce posture

---

## 6.9 Cross-module pinned items (summary)

Across all modules, DLA must ensure:

* append-only immutability and correction via supersedes link
* deterministic audit_record_id and idempotent ingest
* quarantine on incomplete provenance
* by-ref privacy posture
* required query axes are supported deterministically
* exports return canonical record shape with deterministic slicing

---

## 7) Canonical audit record semantics (v0)

> This section defines what the canonical AuditDecisionRecord *means* and how it must be structured so reconstruction is possible without ambiguity.

### 7.1 What the canonical record represents

A canonical AuditDecisionRecord is the immutable “decision-time truth bundle” that captures:

* what stimulus was processed (event_ref + envelope summary),
* what constraints applied (degrade mode + mask),
* what context was used (OFP snapshot hash + freshness + input_basis; IEG graph_version if used),
* what the system output (decision outcome + action intents),
* and how it got there (policy refs, stage summary, timings).

---

### 7.2 Mandatory field groups (v0)

Canonical records must include the minimum fields pinned in §5.4, grouped as:

1. Identity + pins + audit metadata
2. Event input
3. DL degrade posture used
4. OFP feature context used
5. IEG context used (or not used block)
6. DF outputs
7. DF provenance essentials

---

### 7.3 Deterministic ordering rules (pinned)

Before hashing and storing:

* `feature_keys_used[]` must be sorted deterministically (key_type, key_id)
* `group_versions_used[]` must be sorted deterministically (group_name, group_version)
* freshness blocks sorted deterministically by group
* actions sorted deterministically by action_type
* stage_summary sorted deterministically by stage id/name

This ensures audit_record_id hashing is stable and comparisons are meaningful.

---

### 7.4 “Used vs not used” blocks (avoid ambiguity)

For each dependency context, canonical record must disambiguate:

* IEG:

  * either `{used:true, graph_version:...}`
  * or `{used:false, reason:<DISALLOWED|UNAVAILABLE|NOT_REQUIRED>}`

* OFP:

  * even when disallowed, record a structured block indicating not used and why, rather than omitting.

* DL:

  * always present (DF must always consume a DegradeDecision; if missing, DF treats as FAIL_CLOSED and records it)

---

### 7.5 Privacy discipline (by-ref posture)

Canonical record must not embed raw event payloads or full feature vectors:

* store `event_ref`
* store `feature_snapshot_hash` + metadata
* store graph_version and watermarks
* store actions and decision outcome (these are not raw sensitive payloads in the same way)

If any raw field is required later, it must be explicitly added via versioning and governance approval.

---

### 7.6 Canonicalization inputs for audit_record_id

audit_record_id is computed from the canonical record content:

* ContextPins
* identity fields (decision_id/event_id/request_id)
* all mandatory blocks (event ref summary, DL/OFP/IEG/DF output/provenance)
* deterministic ordering rules applied

The exact hash algorithm is open, but determinism and stability are mandatory.

---

## 8) Idempotent ingestion and duplicate handling (v0)

> This section pins how DLA remains correct under retries and duplicate deliveries from DF or upstream transport.

### 8.1 Idempotency goal

DLA must be safe if the same DecisionResponse is ingested multiple times:

* due to DF retries,
* transport duplication,
* or replay/backfill.

Duplicates must not create multiple canonical audit records.

---

### 8.2 audit_record_id computation (pinned posture)

* DLA computes `audit_record_id` as a deterministic hash of the canonicalized AuditDecisionRecord payload.
* Canonicalization includes:

  * mandatory fields only (no ephemeral fields like ingestion attempt IDs),
  * deterministic ordering rules (lists/maps) as defined in §7.3.

Hash algorithm choice is open; canonicalization rules are pinned.

---

### 8.3 Idempotent ingest key (pinned)

DLA’s idempotent ingest key is:

* `(ContextPins, audit_record_id)`

On ingest:

* if the key is new → write canonical record
* if the key already exists → no-op (do not write duplicate)

---

### 8.4 Duplicate DecisionResponse with identical payload

If DF resends the same DecisionResponse (same content):

* DLA computes the same audit_record_id
* ingestion is a no-op after first write

---

### 8.5 Duplicate decision_id with different payload (corrections only)

If a second record arrives with the same decision_id but a different payload:

* it is accepted as canonical only if it includes:

  * `supersedes_audit_record_id` pointing to an existing record for that decision_id.

If no valid supersedes link exists:

* DLA treats it as non-canonical and routes it to quarantine (reason: `MISSING_SUPERSEDES_LINK` or a v0 equivalent).

---

### 8.6 Duplicate handling for quarantine records

Quarantine records are also append-only. If the same incomplete payload is ingested repeatedly:

* DLA may dedupe quarantine entries or keep all attempts (implementation freedom),
  but must remain inspectable.

---

## 9) Corrections and supersession semantics (v0)

> This section pins how DLA represents corrections without mutating history.

### 9.1 No updates in place (restated)

* Canonical audit records are immutable.
* Corrections are represented as new records only.

---

### 9.2 When a correction record is allowed

A record is treated as a correction if:

* it has the same `decision_id` as a previously stored canonical record, and
* it includes `supersedes_audit_record_id` pointing to the prior canonical record it replaces.

If `supersedes_audit_record_id` is missing or invalid:

* the record is not accepted as canonical and is routed to quarantine.

---

### 9.3 Supersedes linkage rules (pinned)

* `supersedes_audit_record_id` must reference an existing canonical record within the same ContextPins scope.
* Supersession must not cross ContextPins.

This prevents accidental cross-run overwrites.

---

### 9.4 Query semantics for superseded records (v0 posture)

DLA must support two conceptual query views:

1. **Historical view**

* returns all records, including superseded ones, in append-only order.

2. **Current view**

* returns the latest canonical record per decision_id, following supersedes chains.

The exact implementation (materialized view vs query logic) is implementation freedom.

---

### 9.5 Correction provenance

Correction records must include:

* correction reason (optional field, but recommended)
* linkage to the prior record
* the complete canonical record payload (not a delta), so reconstruction does not require joining across versions.

---

### 9.6 Limits and safety

DLA may enforce a maximum supersedes chain length (config) to prevent infinite loops, but must preserve append-only history regardless.

---

## 10) Quarantine semantics (incomplete provenance)

> This section pins how DLA handles non-canonical ingests safely: **never pollute canonical audit**, but never lose evidence of what went wrong.

### 10.1 Quarantine purpose

Quarantine exists to:

* preserve evidence that DF (or transport) produced an audit payload that DLA cannot accept as canonical,
* make failures inspectable and countable,
* force upstream compliance without silent data loss.

### 10.2 When DLA routes to quarantine (pinned)

An ingest is routed to `audit_quarantine` if any of the following hold:

* **INCOMPLETE_PROVENANCE**: missing any required canonical fields (as defined in §5.4 / §7.2)
* **MISSING_SUPERSEDES_LINK**: same `decision_id` as an existing canonical record, payload differs, but no `supersedes_audit_record_id` provided
* **INVALID_SUPERSEDES_LINK**: supersedes field present but:

  * points to a non-existent audit_record_id, or
  * points across ContextPins (context mismatch)

(These are the v0 reason-code concepts; exact enum names get pinned in the v0 schema.)

### 10.3 Quarantine record shape (v0 minimum)

A quarantine record MUST include:

* **Identity**

  * `quarantine_record_id` (deterministic hash of the quarantined payload + reason + timestamp bucket or similar)
  * `ingested_at_utc`

* **Source correlation**

  * `decision_id` (if present)
  * `request_id` (if present)
  * `event_id` (if present)
  * `event_ref` (if present)
  * `context_pins` (if present; may be partial)

* **Reason**

  * `reason_code` (one of the pinned quarantine reasons)
  * `missing_fields[]` (when INCOMPLETE_PROVENANCE; list of required fields absent)
  * `notes` (optional short text)

* **Payload evidence**

  * `payload_ref` (preferred: by-ref pointer to the original DecisionResponse/audit payload blob)
  * or `payload_excerpt` (only if you explicitly allow it; v0 posture prefers by-ref)

### 10.4 Append-only posture for quarantine (pinned)

* Quarantine is **append-only**.
* DLA must not “update” quarantine records.
* Repeated failures may create repeated quarantine entries (allowed); optional dedupe is implementation freedom.

### 10.5 Operator/triage posture (conceptual but required)

Quarantine must be inspectable by operators:

* searchable by `decision_id/event_id` when present
* searchable by `reason_code`
* queryable by time window

The goal is to quickly answer:

* “What is failing to meet audit completeness, and why?”

### 10.6 Privacy discipline (inherits v0 posture)

* Quarantine must follow the same by-ref/privacy posture as canonical audit:

  * no raw event payload embedding
  * no full feature vectors embedded
* Store refs + minimal evidence only.

### 10.7 Remediation expectation (conceptual)

Quarantine does not “fix” records.

* Upstream components (primarily DF) must correct their output and emit a **new canonical DecisionResponse**, which will then ingest successfully.
* If a correction for the same decision_id is needed, it must follow supersedes linkage rules (§9).

---

## 11) Query axes, indexing posture, and exports (v0)

> This section pins what DLA must be able to query and export deterministically. It does **not** pin database technology; it pins semantics and required axes.

### 11.1 Required query axes (pinned)

Canonical audit records must be queryable by:

**Identity**

* `decision_id` / `request_id` / `event_id`
* `audit_record_id`

**Entity keys**

* `feature_keys_used[]` (FeatureKey / EntityKey list)

**Run/world scope**

* ContextPins (including `run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`)

**Time**

* `event_time_utc` (decision stimulus time)
* `decided_at_utc` (if recorded from DF timing)
* `ingested_at_utc`

**Degrade posture**

* `degrade_mode`

---

### 11.2 Query semantics for supersedes chains (current vs historical)

DLA must support two conceptual views:

* **Historical view:** returns all canonical records (including superseded), ordered by ingestion time.
* **Current view:** returns the “current” canonical record per decision_id following supersedes chains.

How the “current view” is implemented is implementation freedom.

---

### 11.3 Indexing posture (conceptual, pinned intent)

DLA must maintain sufficient indices (or equivalent query capability) to make the required axes feasible.

Pinned intent:

* queries must not require scanning the full dataset (“latest by scan” is forbidden as a semantic requirement).
* deterministic selection rules must be used for any “current view” or export slices.

---

### 11.4 Export posture (v0)

DLA supports deterministic exports (“slices”) for offline training/governance.

Pinned rules:

* exports include the **same canonical AuditDecisionRecord shape** (not a different schema).
* export selection is deterministic based on:

  * ContextPins + time window
  * optional filters: feature_keys_used, degrade_mode, decision_outcome

No “latest by timestamp scan” semantics are allowed.

---

### 11.5 Export determinism rules

To keep exports reproducible:

* ordering of records in export is deterministic (e.g., sort by {event_time_utc, decision_id}).
* if pagination/partitioning is used, it must be deterministic and documented.

---

### 11.6 Quarantine query axes (minimal)

Quarantine records must be queryable by:

* reason_code
* time window
* decision_id/event_id when present

---

## 12) Privacy, security, and retention (v0)

> This section pins the v0 governance posture: by-ref storage, minimal access control intent, and retention as a concept. Exact IAM and durations remain configurable.

### 12.1 Privacy posture (pinned)

DLA v0 follows strict **by-ref + hashes** discipline:

* Store `event_ref`, not embedded event payloads.
* Store `feature_snapshot_hash` + metadata, not full feature vectors.
* Store `graph_version`, DL mode/mask, and DF outputs/provenance essentials (these are necessary for audit).
* Raw sensitive fields are forbidden unless explicitly introduced via versioning and governance approval.

This applies to both canonical and quarantine records.

---

### 12.2 Access control posture (pinned at a high level)

DLA requires a minimal role posture:

* **Writers:** Decision Fabric (and later Actions outcomes) only.
* **Readers:** investigators, governance/audit tooling, offline training assembly (role-gated).
* **Quarantine readers:** restricted to operators/governance roles.

Exact IAM implementation is left to the implementer, but the role separation intent is pinned.

---

### 12.3 Retention posture (conceptual, pinned)

DLA retention is defined as a time-based concept:

* canonical audit records retained for a configured window
* quarantine records retained for a configured window (may differ)

Pinned rule:

* for the retention period, referenced digests/refs must remain resolvable enough for audit (event_ref targets, snapshot hashes, etc.).

Archival vs deletion mechanics are implementation freedom, but must be explicit.

---

### 12.4 Redaction posture (v0)

Since raw payload embedding is forbidden in v0, redaction is minimal:

* ensure that any optional text fields (notes/messages) are short and non-sensitive
* forbid copying raw event payloads into notes

If later versions embed more data, explicit redaction rules must be added.

---

### 12.5 Observability minimums (ops)

DLA must expose:

* ingest success/failure counts
* quarantine counts by reason_code
* lag/throughput indicators (if ingestion is streaming)
* query latency (for key query surfaces)
* export job status metrics (if exports exist)

Exact telemetry plumbing is implementation freedom.

---

## 13) Contracts philosophy and contract pack overview (v0)

> DLA contracts exist to pin the **canonical audit record boundary shape** in a machine-checkable way. Contracts define shape; DLA specs define behavior (immutability, idempotent ingest, quarantine, supersedes semantics).

### 13.1 v0 contract strategy (one schema file)

DLA v0 ships **one** schema file:

* `contracts/dla_public_contracts_v0.schema.json`

This file contains `$defs` for:

* canonical AuditDecisionRecord
* quarantine record shape
* correction linkage fields
* supporting objects (ContextPins, FeatureKey, ActionIntent compatibility)

---

### 13.2 Validation targeting rule (self-describing)

All DLA contract objects are self-describing via:

* `kind` + `contract_version`

Consumers validate based on those fields mapping to `$defs`.

---

### 13.3 `$defs` inventory (v0)

`dla_public_contracts_v0.schema.json` contains `$defs` for:

* `ContextPins`
* `FeatureKey` (EntityKey)
* `AuditDecisionRecord`
* `AuditProvenance` (structured sub-blocks: DL/OFP/IEG/DF essentials)
* `ActionIntent` (compatible with DF action shape; idempotency_key required)
* `CorrectionLink` (`supersedes_audit_record_id`)
* `AuditQuarantineRecord` (reason_code + missing_fields + payload_ref)
* `ErrorResponse` (optional)

---

### 13.4 What contracts cover vs what specs cover

#### Contracts cover (shape/structure)

* required fields presence and types for canonical record
* stable nested blocks for DL/OFP/IEG/DF data
* reason_code enum for quarantine
* deterministic places for identity and timestamps
* correction linkage field presence

#### Specs cover (behavior/invariants)

* append-only rules and no mutation
* audit_record_id canonicalization rules
* idempotent ingestion semantics
* when to quarantine vs accept canonical
* supersedes chain query semantics (current vs historical views)
* privacy and retention posture

---

### 13.5 Relationship to Canonical Event Contract Pack

DLA will influence the Canonical Event Contract Pack because:

* it defines the “must-record” fields DF must emit.

In v0, DLA uses refs and hashes; in v1, canonical event schemas can:

* reference DLA’s audit record shape for exported decision events, or
* define decision/action event payloads that map directly to the audit record fields.

---

## 14) Addressing, naming, and discoverability (conceptual)

> This section defines how canonical and quarantine audit records are referenced and discovered without guessing. It stays conceptual because storage and query mechanisms are implementation freedom in v0.

### 14.1 Primary identifiers for discovery

In v0, the key identifiers are:

* `decision_id` / `request_id` / `event_id` (same value)
* `audit_record_id` (deterministic hash of canonical audit payload)

These are the primary handles for reconciliation and idempotent ingestion.

---

### 14.2 Canonical record discovery

Canonical audit records are discoverable by:

* decision_id (find all records for a decision; include supersedes chain)
* audit_record_id (direct lookup)
* ContextPins + time window
* feature_keys_used (entity axis)
* degrade_mode

Pinned rule:

* DLA must not require scanning by “latest file”; discovery is via explicit keys/indices.

---

### 14.3 Quarantine record discovery

Quarantine records are discoverable by:

* reason_code
* time window
* decision_id/event_id when present
* payload_ref (if used as a lookup anchor)

Pinned rule:

* quarantine is inspectable and searchable enough for triage.

---

### 14.4 Supersedes chain discovery

For a given decision_id, DLA must be able to:

* show the full history (all records)
* identify the “current” canonical record (follow supersedes chain)

The exact implementation is implementation freedom; the semantics are pinned.

---

### 14.5 Local vs deployed semantics

* **Local:** records may be written to files; queries may be CLI-based.
* **Deployed:** records may be stored in a DB/lake; queries may be API-based.

Pinned rule:

* key semantics remain identical across environments:

  * audit_record_id deterministic
  * append-only and supersedes rules preserved
  * query axes available

---

## 15) Intended repo layout (conceptual target)

> This section describes the **target folder structure** for DLA docs and contracts. The goal is a **single, deep reading surface** for DLA design, plus a **minimal v0 contract**.

### 15.1 Target location in repo

Conceptually, DLA lives under the Real-Time Decision Loop plane:

* `docs/model_spec/real-time_decision_loop/decision_log_audit/`

This folder should be self-contained: a new contributor should understand DLA by starting here.

---

### 15.2 Proposed skeleton (v0-thin, deadline-friendly)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ decision_log_audit/
         ├─ README.md
         ├─ CONCEPTUAL.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ DLA1_charter_and_boundaries.md
         │  ├─ DLA2_canonical_audit_record_core_contract.md
         │  ├─ DLA3_immutability_corrections_idempotent_ingestion.md
         │  ├─ DLA4_query_axes_indexing_exports.md
         │  └─ DLA5_privacy_security_retention_ops_acceptance.md
         │
         └─ contracts/
            └─ dla_public_contracts_v0.schema.json
```

**Notes**

* You can merge `CONCEPTUAL.md` into `README.md` later if you want fewer files.
* Keep `contracts/` even under deadline; DLA v0 needs only **one** schema file here.

---

### 15.3 What each file is for (intent)

#### `README.md`

* Entry point: what DLA is, why it exists, and how to read this folder.
* Links to:

  * `CONCEPTUAL.md` (designer-locked v0 intent)
  * `specs/` reading order (DLA1–DLA5)
  * `contracts/` schema

#### `CONCEPTUAL.md`

* This stitched conceptual design document:

  * DLA purpose in platform
  * DLA laws (append-only, idempotent ingest, quarantine, supersedes)
  * designer-locked v0 decisions (required field sets, privacy posture)
  * modular breakdown + questions per module
  * contract pack overview (v0)
  * discoverability concepts (audit_record_id and query axes)

This doc is directional alignment, not binding spec.

#### `AGENTS.md`

* Implementer posture + reading order:

  * specs define behavior/invariants
  * contract schema defines boundary shapes
* Non-negotiables:

  * append-only canonical records
  * deterministic audit_record_id
  * idempotent ingest key (ContextPins, audit_record_id)
  * quarantine on incomplete provenance
  * supersedes linkage for corrections
  * by-ref privacy posture
  * required query axes

#### `specs/`

* DLA1–DLA5 are the eventual binding-ish DLA design docs.
* Inline examples/ASCII diagrams/decision notes in appendices (avoid extra folders).

#### `contracts/`

* `dla_public_contracts_v0.schema.json` pins DLA boundary objects.

---

### 15.4 Recommended reading order

1. `README.md` (orientation)
2. `CONCEPTUAL.md` (designer-locked intent)
3. `specs/DLA1_...` → `specs/DLA5_...` (behavior/invariants)
4. `contracts/dla_public_contracts_v0.schema.json` (machine-checkable truth)

Codex should treat:

* `contracts/` as source-of-truth for shape,
* `specs/` as source-of-truth for semantics.

---

## 16) What the eventual spec docs must capture (mapping)

> This section bridges the DLA conceptual design into the **actual DLA spec docs** (DLA1–DLA5) and clarifies what each spec must pin vs what can remain implementer freedom.

### 16.0 Mapping rule (how to use this section)

For every DLA “law” and designer-locked decision in this conceptual doc:

* it must end up either as:

  * a **pinned decision** in DLA1–DLA5, and/or
  * a **machine-checkable shape** in `contracts/`,
* or be explicitly declared implementation freedom.

---

## 16.1 DLA1 — Charter & boundaries

### DLA1 must capture

* DLA purpose as the loop’s immutable flight recorder
* authority boundaries:

  * system-of-record for audit record persistence and queryability
  * not decisioning, not feature computation, not identity truth
* DLA laws:

  * append-only, no mutation
  * by-ref privacy posture
  * idempotent ingestion
  * quarantine on incomplete provenance
  * required query axes

### DLA1 may leave to the implementer

* deployment model and storage backend choice

---

## 16.2 DLA2 — Canonical audit record (core contract)

### DLA2 must capture

* canonical AuditDecisionRecord shape and required field groups
* deterministic ordering rules for lists/maps
* “used vs not used” blocks (OFP/IEG) to avoid ambiguity
* forbidden embedded payload posture (privacy)

### DLA2 may leave to the implementer

* exact physical schema layout in storage

---

## 16.3 DLA3 — Immutability, corrections, idempotent ingestion

### DLA3 must capture

* append-only rules
* supersedes linkage rules for corrections
* audit_record_id computation posture (canonicalization inputs)
* idempotent ingest key (ContextPins, audit_record_id)
* duplicate handling semantics (no-op)
* quarantine rules for missing/invalid supersedes

### DLA3 may leave to the implementer

* dedupe index backend and transaction mechanics

---

## 16.4 DLA4 — Query axes, indexing posture, and exports

### DLA4 must capture

* required query axes (ids, entity keys, pins, time, mode)
* current vs historical view semantics for supersedes chains
* deterministic export selection rules and export shape (canonical record)
* quarantine query axes (minimal)

### DLA4 may leave to the implementer

* indexing tech and query transport/API style

---

## 16.5 DLA5 — Privacy, security, retention, ops & acceptance

### DLA5 must capture

* by-ref privacy discipline (forbidden embedded payload fields)
* access posture (writer/reader roles)
* retention concept and “refs resolvable during retention” rule
* observability minimums (ingest failures, quarantine counts, lag, query latency)
* acceptance scenarios (append-only, idempotent ingest, quarantine correctness)

### DLA5 may leave to the implementer

* IAM implementation details and retention durations (config)

---

## 16.6 Contracts mapping (what must be in schema vs prose)

### Schema must include

* ContextPins, FeatureKey/EntityKey
* AuditDecisionRecord shape (required fields)
* AuditQuarantineRecord shape (reason_code + missing_fields + payload_ref)
* CorrectionLink (supersedes_audit_record_id)
* ActionIntent compatibility (idempotency_key required)
* validation targeting via kind + contract_version

### Specs must include

* append-only and supersedes behavior
* audit_record_id canonicalization inputs
* quarantine routing rules and reason codes meaning
* query view semantics (current vs historical)
* privacy/retention posture rules

---

## 16.7 Minimal completeness standard (so DLA is implementable)

DLA is “spec-ready” when DLA1–DLA5 collectively pin:

* canonical record shape and deterministic ordering
* append-only + corrections linkage rules
* idempotent ingestion key and duplicate handling
* quarantine on incomplete provenance
* required query axes and export semantics
* by-ref privacy posture and retention concept

Everything else can remain implementer freedom.

---

## 17) Acceptance questions and Definition of Done

> This section is the conceptual **ship checklist** for DLA v0: the questions DLA must answer and the minimal behavioural scenarios that indicate DLA is correct enough to implement and integrate.

### 17.1 Acceptance questions (DLA must answer these unambiguously)

1. **Is the audit record immutable?**

* Once written, can the canonical record ever change? (No.)

2. **How do we correct a record?**

* Are corrections represented only as new records with explicit supersedes linkage?

3. **Is ingestion idempotent under duplicates?**

* If the same DecisionResponse arrives twice, is only one canonical record stored?

4. **What is the canonical record identity?**

* Can we deterministically identify a record via audit_record_id and decision_id?

5. **Do we enforce provenance completeness?**

* Do incomplete ingests get quarantined instead of entering canonical storage?

6. **Is the record joinable and reconstruction-ready?**

* Does every canonical record include refs/hashes and metadata sufficient to reconstruct context?

7. **Are privacy rules upheld?**

* Are raw payload embeddings forbidden and by-ref posture enforced?

8. **Can we query by required axes?**

* Can we query by ids, entity keys, ContextPins, time windows, and degrade_mode?

9. **Are exports deterministic and schema-consistent?**

* Do exports return canonical record shape and deterministic selection/order?

---

### 17.2 Definition of Done (conceptual test scenarios)

#### DoD-1: Canonical write is append-only

**Given**

* a valid DecisionResponse with complete provenance

**Expect**

* DLA writes exactly one canonical AuditDecisionRecord
* record is immutable once stored

---

#### DoD-2: Duplicate ingest is a no-op

**Given**

* the same DecisionResponse ingested twice (identical payload)

**Expect**

* DLA computes the same audit_record_id
* second ingest is a no-op (no duplicate canonical record)

---

#### DoD-3: Missing required fields → quarantine

**Given**

* a DecisionResponse missing required provenance fields (e.g., no feature_snapshot_hash)

**Expect**

* no canonical record written
* audit_quarantine record written with reason_code INCOMPLETE_PROVENANCE
* missing_fields[] lists the absent required fields

---

#### DoD-4: Correction requires supersedes linkage

**Given**

* a second record for the same decision_id with different payload

**Expect**

* it is accepted only if supersedes_audit_record_id is present and valid
* otherwise it is quarantined with a supersedes-related reason code

---

#### DoD-5: Current vs historical view works

**Given**

* a decision_id with an original record and a correction record

**Expect**

* historical view returns both records
* current view returns the corrected record only (following supersedes chain)

---

#### DoD-6: Query axes are satisfied

**Given**

* a population of canonical records

**Expect**

* queries work deterministically for:

  * decision_id/event_id
  * ContextPins (run_id, manifest_fingerprint)
  * feature_keys_used
  * time window
  * degrade_mode

---

#### DoD-7: Privacy posture enforced

**Given**

* an ingest payload that attempts to embed raw event payload or full feature vector

**Expect**

* DLA rejects/quarantines it (or strips and quarantines) per policy
* canonical storage does not contain forbidden embedded fields

---

#### DoD-8: Deterministic export slices

**Given**

* an export request (pins + time window + optional filters)

**Expect**

* export contains canonical AuditDecisionRecord shape
* record ordering is deterministic (e.g., by event_time_utc then decision_id)
* repeated export with same parameters yields the same result set/order (within retention)

---

### 17.3 Minimal deliverables required to claim “DoD satisfied”

To claim DLA meets DoD at v0 conceptual level, you should be able to show:

* a canonical AuditDecisionRecord example
* a duplicate-ingest test demonstrating no duplicate canonical record
* an INCOMPLETE_PROVENANCE quarantine example
* a correction record with supersedes linkage example
* current vs historical query results example
* export slice example with deterministic ordering

---

## 18) Open decisions log (v0 residuals only)

> These are the only remaining decisions for DLA v0 that are not already designer-locked. Everything else is pinned above or is implementation freedom.

### DEC-DLA-001 — Hash algorithm for audit_record_id

* **Question:** which hash algorithm is used to compute audit_record_id (e.g., SHA-256)?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA3
* **Constraint:** must be deterministic, stable, and widely available.

### DEC-DLA-002 — Canonical serialization for audit_record_id inputs

* **Question:** what canonical serialization rules are used for hashing inputs (canonical JSON rules, ordering, numeric representation)?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA3
* **Constraint:** must fully specify ordering and numeric formatting to avoid drift.

### DEC-DLA-003 — “Current view” materialization posture

* **Question:** does DLA expose a built-in “current canonical record per decision_id” view, or is this left to query tooling?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA4
* **Constraint:** semantics must remain deterministic; must follow supersedes chains.

### DEC-DLA-004 — Retention window defaults

* **Question:** default retention durations for canonical vs quarantine records (config)?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA5
* **Constraint:** refs/hashes must remain resolvable within retention.

### DEC-DLA-005 — Quarantine reason code vocabulary finalization

* **Question:** finalize the enum values:

  * INCOMPLETE_PROVENANCE
  * MISSING_SUPERSEDES_LINK
  * INVALID_SUPERSEDES_LINK
* **Status:** OPEN (v0 residual)
* **Close in:** contracts + DLA3/DLA5

### DEC-DLA-006 — Export format and transport

* **Question:** what export format is used (parquet/json) and where exports land?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA4
* **Constraint:** export shape is canonical record; format is free.

### DEC-DLA-007 — Privacy enforcement mechanism on forbidden fields

* **Question:** do we reject-and-quarantine on forbidden embedded fields, or strip-and-quarantine?
* **Status:** OPEN (v0 residual)
* **Close in:** DLA5
* **Constraint:** canonical store must not contain forbidden embedded fields.

---

## Appendix A — Minimal examples (inline)

> **Note (conceptual, non-binding):** These examples illustrate the v0 canonical audit record, quarantine record, and a correction record with supersedes linkage. Payload refs are opaque by-ref pointers.

---

### A.1 Example — Canonical `AuditDecisionRecord`

```json
{
  "kind": "audit_decision_record",
  "contract_version": "dla_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000123",
  "request_id": "evt_txn_000000123",
  "event_id": "evt_txn_000000123",

  "audit_record_id": "ar_9b2c...sha256...11aa",
  "ingested_at_utc": "2026-01-03T12:34:57Z",

  "event": {
    "event_ref": "eb://admitted_events/partition=0/offset=9812399",
    "event_time_utc": "2026-01-03T12:34:56Z",
    "event_type": "transaction_event"
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
    "triggers": []
  },

  "features": {
    "feature_keys_used": [
      { "key_type": "account", "key_id": "e_account_7c31d9" }
    ],
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

  "decision": {
    "decision_outcome": "APPROVE",
    "actions": [
      {
        "action_type": "APPROVE_TRANSACTION",
        "idempotency_key": "H(pins,evt_txn_000000123,APPROVE_TRANSACTION)",
        "parameters": { "reason": "risk_below_threshold" }
      }
    ]
  },

  "df_provenance": {
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

### A.2 Example — `AuditQuarantineRecord` (INCOMPLETE_PROVENANCE)

```json
{
  "kind": "audit_quarantine_record",
  "contract_version": "dla_public_contracts_v0",

  "quarantine_record_id": "qr_aa11...sha256...77bb",
  "ingested_at_utc": "2026-01-03T12:35:05Z",

  "reason_code": "INCOMPLETE_PROVENANCE",
  "missing_fields": ["features.feature_snapshot_hash", "features.group_versions_used"],

  "correlation": {
    "decision_id": "evt_txn_000000124",
    "event_ref": "eb://admitted_events/partition=0/offset=9812400"
  },

  "payload_ref": "blob://dla_ingest_payloads/2026-01-03/evt_txn_000000124.json"
}
```

---

### A.3 Example — Correction record (supersedes linkage)

```json
{
  "kind": "audit_decision_record",
  "contract_version": "dla_public_contracts_v0",

  "context_pins": {
    "scenario_id": "scn_baseline_v1",
    "run_id": "run_20260103T110000Z_0001",
    "manifest_fingerprint": "mf_20251231T235959Z_8f3c2a1d",
    "parameter_hash": "ph_4b1d7a9c"
  },

  "decision_id": "evt_txn_000000123",
  "request_id": "evt_txn_000000123",
  "event_id": "evt_txn_000000123",

  "audit_record_id": "ar_correction_...sha256...",
  "ingested_at_utc": "2026-01-03T12:40:00Z",

  "supersedes_audit_record_id": "ar_9b2c...sha256...11aa",
  "correction_reason": "Policy hotfix applied; corrected outcome",

  "event": {
    "event_ref": "eb://admitted_events/partition=0/offset=9812399",
    "event_time_utc": "2026-01-03T12:34:56Z",
    "event_type": "transaction_event"
  },

  "decision": {
    "decision_outcome": "REVIEW",
    "actions": [
      {
        "action_type": "QUEUE_CASE",
        "idempotency_key": "H(pins,evt_txn_000000123,QUEUE_CASE)",
        "parameters": { "queue": "fraud_ops" }
      }
    ]
  }
}
```

---

## Appendix B — ASCII sequences (ingest, dedupe, quarantine, correction, export)

> **Legend:**
> `->` command/call `-->` read/consume `=>` write/append

---

### B.1 DF → DLA ingest → canonical append-only write

```
Participants:
  Decision Fabric | DLA(Ingest/Normalize) | DLA(Dedup) | DLA(Canonical Store) | DLA(Indices)

Decision Fabric -> DLA(Ingest/Normalize): DecisionResponse (decision + actions + provenance)

DLA(Ingest/Normalize): validate required fields present
DLA(Dedup): compute audit_record_id (canonicalized payload hash)
DLA(Dedup): check (ContextPins, audit_record_id) exists?

(if new)
  DLA(Canonical Store) => append AuditDecisionRecord (immutable)
  DLA(Indices) => update query indices (ids, keys, pins, time, mode)
(if exists)
  NO-OP (idempotent ingest)
```

---

### B.2 Duplicate ingest no-op

```
Decision Fabric -> DLA: same DecisionResponse resent
DLA computes same audit_record_id
DLA finds (ContextPins, audit_record_id) already present
DLA: NO-OP (does not create duplicate canonical record)
```

---

### B.3 Incomplete provenance → quarantine

```
Decision Fabric -> DLA: DecisionResponse missing required feature provenance fields

DLA(Ingest/Normalize): required field check fails
DLA => Quarantine Store: append AuditQuarantineRecord(reason=INCOMPLETE_PROVENANCE, missing_fields, payload_ref)
DLA: no canonical record written
```

---

### B.4 Correction record supersedes prior record

```
Decision Fabric -> DLA: corrected DecisionResponse for same decision_id
  includes supersedes_audit_record_id

DLA: validates supersedes link exists and matches ContextPins
DLA => Canonical Store: append new AuditDecisionRecord (correction)
DLA(Indices): "current view" now points to correction record (historical view keeps both)
```

---

### B.5 Deterministic export slice

```
Operator/Offline Tool -> DLA(Export): request export (ContextPins + time window + optional filters)
DLA(Export) --> Canonical Store: select records deterministically
DLA(Export): sort deterministically (event_time_utc, decision_id)
DLA(Export) => Export Sink: write export file(s) containing canonical AuditDecisionRecord shape
```

---