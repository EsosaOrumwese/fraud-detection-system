black-box framing:
{
""""
Through a hierarchical modular lens, **Case Mgmt / Workbench** looks like the platform’s **human-in-the-loop control surface**: it turns “alerts + evidence + investigator actions” into **cases with immutable timelines**, and it produces **authoritative investigator assertions** that flow into the **Label Store**.

## Level 0 — Black-box view

**Inputs**

* **Case triggers / evidence refs** (typically from Decision Fabric + Actions outcomes + Decision Log/Audit pointers)
* **Investigator actions** (triage, notes, links, disposition, escalations)
* Optional: external feeds (disputes, KYC findings) as evidence

**Outputs**

* **Case objects** (case_id, state, priority, assignment, SLAs)
* **Case timeline** (append-only event history: what happened, what was done, when, by whom)
* **Investigator assertions** (e.g., “confirmed fraud”, “false positive”, “needs more info”) written to **Label Store**
* Optional: **case events** back to the stream for audit/automation

One sentence: **“Manage investigations as immutable, joinable case timelines and emit authoritative investigator assertions into labels.”**

---

## Level 1 — Minimal responsibility chunks (v0-thin)

These are *sections/facets* you can spec without turning it into a giant system.

1. **Case Registry (Case Store)**

* Create/read/update the *case header*: `case_id`, status, severity, assignment, SLA clocks
* Stable joins to decision/event/entity keys (+ `ContextPins` if you keep closed-world scoping)

2. **Case Timeline (Append-only)**

* Every meaningful change is a timeline event: created, assigned, note added, evidence attached, disposition set
* Corrections are new timeline events (no edits)

3. **Triage / Queue / Assignment**

* Queueing model: unassigned → assigned → escalated
* Minimal routing rules (priority, workload) (can be loose in v0, but states must be clear)

4. **Evidence & Attachments (by-ref)**

* Store only **refs** to evidence (DLA record refs, event refs, documents), not raw blobs
* Evidence is “support”, not truth

5. **Disposition & Label Emission**

* When an investigator disposes a case, emit a **LabelAssertion** to Label Store
* Explicit mapping: case disposition → label family/value + effective/observed times

6. **Access Control & Audit**

* Who can view/edit/close cases
* Every investigator action is auditable (actor, time, what changed)

7. **Workbench Query Surface**

* Queries by: case_id, status/queue, entity keys, decision_id/request_id, time window
* This is what the UI uses (even if UI itself isn’t specced in detail)

---

## Level 2 — Boundaries with other components

* **Consumes:** decision/audit pointers from **Decision Log & Audit**, action outcomes from **Actions Layer**, and any alerts/flags.
* **Produces:** authoritative label assertions into **Label Store**.
* **Optionally emits:** case status/timeline events back to EB for observability/automation.

---

## Cross-cutting “laws” (what must be tight later)

* **Append-only case timeline** (no silent edits; corrections as new events)
* **Joinability** (case links to decisions/events/entities + optional `ContextPins`)
* **Truth vs evidence** (case stores evidence refs; labels are the truth assertions written to Label Store)
* **Idempotent writes** (duplicate submissions don’t create duplicate timeline events)
* **Privacy** (evidence by-ref; minimal sensitive data in the case store)
""""
}


tighten vs loose split
{
""""
Here’s the **v0-thin “tighten vs stay loose”** for **Case Mgmt / Workbench**.

## What needs tightening (pin this)

### 1) Case object model + lifecycle (minimal state machine)

* Required case fields: `case_id`, `status`, `priority/severity`, `created_at`, `updated_at`
* Minimal status enum + allowed transitions (e.g., `OPEN → IN_REVIEW → RESOLVED → CLOSED`, plus `ESCALATED` if needed)
* Rule: state transitions are driven by **timeline events** (no silent state flips)

### 2) Join keys (how cases link to the rest of the platform)

Pin what a case can be attached to:

* `decision_id` / `request_id`
* `event_id`
* `EntityRef` / `FeatureKey` (account/card/customer/merchant etc.)
* Optional `ContextPins` scoping (recommended in your closed-world setting)
  This avoids implementers inventing incompatible linkage fields.

### 3) Append-only case timeline contract

* Case timeline is **append-only**; no edits.
* Define `CaseEvent` required fields:

  * `case_event_id`, `case_id`, `event_type`, `observed_at_utc`, `actor`, `payload` (structured)
* Deterministic ordering rule (by `observed_at_utc`, then `case_event_id`).

### 4) Investigator actions taxonomy (v0)

Pin a small set of timeline `event_type`s:

* `CASE_CREATED`, `ASSIGNED`, `EVIDENCE_ATTACHED`, `NOTE_ADDED`, `STATUS_CHANGED`, `DISPOSITION_SET`, `LABEL_EMITTED`
  And what each means at a sentence level.

### 5) Disposition → Label Store mapping (the key boundary)

Pin exactly:

* What dispositions exist (enum) (e.g., `CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `INCONCLUSIVE`)
* How each maps to a **LabelAssertion**:

  * label family/value
  * effective_time vs observed_time semantics
  * required join targets (event/entity/case)
* Rule: Label Store is the truth store; Case Mgmt emits label assertions, not “labels-in-case”.

### 6) Idempotency rules

* For case creation: define idempotency key (e.g., `{trigger_source, trigger_id}`) so duplicates don’t create multiple cases.
* For timeline events: define event idempotency key (e.g., client-generated `case_event_id` or hash).
* For label emissions: ensure you emit idempotent LabelAssertions (reuse Label Store idempotency key strategy).

### 7) Evidence/attachments posture (privacy + by-ref)

* Evidence stored as **refs/locators** only (DLA record ref, event ref, document ref).
* No raw sensitive payloads inside case events by default.
* If you allow small previews, pin redaction rules.

### 8) Query surface (minimum)

Pin what must be queryable:

* by `case_id`
* by status/queue/assignee
* by linked keys (decision_id/event_id/entity)
* by time window
  You don’t need DB indexes, just semantics.

### 9) Access control posture (minimal)

* Who can create/assign/resolve cases
* Every action must carry `actor` and be auditable.

---

## What can stay loose (implementation freedom)

* UI details (screens, workflows, UX)
* Storage backend and indexing tech
* Assignment algorithm (round-robin, skill-based)
* Notifications/integrations
* Comment formatting, rich text, attachments storage
* Automation rules (auto-close, auto-escalate) — can be added later
* SLA computations (exact timers) — can stay conceptual in v0

---

### One-line v0 contract for Case Mgmt

**“Case Mgmt stores investigations as immutable case timelines linked to decisions/events/entities, and emits authoritative disposition-based LabelAssertions into Label Store.”**
""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s a **Case Mgmt / Workbench v0-thin package** (kept to a **3-doc set** + **1 contracts file**, like Label Store).

---

## CM v0-thin doc set (3 docs)

### **CM1 — Charter, Boundaries, and Lifecycle**

* What Case Mgmt is (human-in-the-loop investigation surface)
* Authority boundaries (cases/timelines are authoritative; labels are written to Label Store)
* Minimal case lifecycle (status enum + allowed transitions)
* Core laws: append-only timeline, joinability, idempotency, privacy by-ref

### **CM2 — Case & Timeline Contracts, Joins, Evidence**

* Case object minimum fields + join targets (decision_id/event_id/entity/case + ContextPins posture)
* **CaseEvent** timeline contract (append-only; deterministic ordering)
* Investigator action taxonomy (event_type enum list)
* Evidence attachment posture (refs only; redaction rules if previews allowed)
* Query surface semantics (must-query axes)

### **CM3 — Dispositions, Label Emission, Idempotency, Ops & Acceptance**

* Disposition enum list + meanings
* **Disposition → LabelAssertion mapping** (family/value + effective/observed times + targets)
* Idempotency rules:

  * case creation idempotency key
  * timeline event idempotency key
  * label emission idempotency alignment with Label Store
* Minimal access control posture (roles; actor required on events)
* Observability minimums (case volumes, time-to-triage, conflict rates)
* Acceptance scenarios (append-only, duplicate safety, label emission correctness)

---

## 1 contracts file (v0)

### `contracts/cm_public_contracts_v0.schema.json`

Recommended `$defs`:

* `ContextPins` *(reuse shape; duplicate in v0 if needed)*
* `CaseStatus` (enum)
* `Disposition` (enum)
* `CaseLink` (one-of: `decision_id`, `request_id`, `event_id`, `entity_ref`, `feature_key`) + optional `context_pins`
* `CaseRecord`

  * required: `case_id`, `status`, `priority`, `created_at_utc`, `updated_at_utc`, `links[]`
  * optional: `assignee`, `queue`, `tags[]`
* `EvidenceRef` (opaque locator + optional digest)
* `CaseEventType` (enum)
* `CaseEvent`

  * required: `case_event_id`, `case_id`, `event_type`, `observed_at_utc`, `actor`, `payload`
  * optional: `idempotency_key`, `evidence_refs[]`, `supersedes_case_event_id`
* `EmitLabelRequest` *(or `LabelEmission`)*

  * required: `case_id`, `disposition`, `label_assertion_ref` (or embedded minimal label fields), `emitted_at_utc`
* `ErrorResponse` (thin)

(Examples live inline in CM2/CM3; Codex can validate them once the schema exists.)

---

## File tree

```text
docs/
└─ model_spec/
   └─ label_and_case/
      └─ case_mgmt_workbench/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ CM1_charter_boundaries_lifecycle.md
         │  ├─ CM2_case_timeline_contracts_joins_evidence.md
         │  └─ CM3_dispositions_label_emission_idempotency_ops_acceptance.md
         │
         └─ contracts/
            └─ cm_public_contracts_v0.schema.json
```

""""
}
