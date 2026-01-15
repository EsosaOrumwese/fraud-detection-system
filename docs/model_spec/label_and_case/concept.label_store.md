black-box framing:
{
""""
Through a hierarchical modular lens, the **Label Store** is the platform’s **lagged truth plane**: it turns “what happened + what we later learned” into **versioned, queryable labels and timelines** that can be joined back to decisions/events for audit and learning.

## Level 0 — Black-box view

**Inputs**

* **Label assertions** coming in over time (often delayed):

  * disputes/chargebacks, confirmed fraud/false-positive outcomes
  * investigator decisions (from Case Mgmt)
  * system-derived outcomes (e.g., action outcomes) *as evidence*, not as truth by itself
* Join keys + context: `request_id/decision_id`, `event_id`, entity keys (account/card/customer/merchant), plus world/run scoping (`ContextPins`) if you want closed-world reproducibility.

**Outputs**

* **Label timelines** (append-only facts) and **current-state labels** (materialized views)
* Query surfaces: “what’s the label as-of time T?”, “what labels exist for this event/entity?”, “what changed when?”
* Exportable label slices for training/evaluation (as a contract, not a pipeline).

One sentence: **“Store delayed ground truth as immutable timelines, and serve ‘as-of’ labels deterministically.”**

---

## Level 1 — Minimal responsibility chunks (v0-thin)

These are *sections/facets*, not necessarily separate services:

1. **Label Taxonomy & Families**

* What kinds of labels exist (event-level, entity-level, case-level)
* Label value sets (fraud/legit/unknown, reason codes, severity, etc.)
* “Who is allowed to assert what” (authority boundary)

2. **Ingestion / Write Interface**

* Accept label assertions (from case workbench, dispute feeds, etc.)
* Idempotency rules for writes (no duplicate timeline entries for the same assertion)

3. **Timeline / State Machine**

* Append-only **LabelEvent** timeline per label target (event/entity/case)
* Optional state transitions (e.g., `PENDING → CONFIRMED_FRAUD`, `DISPUTED → RESOLVED_FP`)
* Support for “corrections” as new events (no edits)

4. **Materialized Views**

* “Current label” view per target key
* “Label as-of time T” view (crucial for leakage control in training)
* Derived summaries (counts, lag stats) optional

5. **Query & Export Surface**

* Queries by event_id/decision_id, by entity key, by time window, by run/world pins
* Export contract for downstream learning/evaluation

---

## Level 2 — What other components “see” (boundaries)

* **Decision Log & Audit** links to labels later (to evaluate decisions and build truth timelines)
* **Case Mgmt** writes investigator assertions into Label Store
* **Learning/Model Factory** consumes labels with strict **as-of** semantics to avoid leakage
* **Offline Feature Plane shadow twin** can use labels to rebuild supervised datasets (but Label Store remains the source of truth).

---

## Cross-cutting “laws” (what must be tight)

* **Append-only truth:** labels are timelines; corrections are new events.
* **As-of semantics:** every label has at least two times:

  * *effective time* (when the truth applies to the world)
  * *known/observed time* (when the platform learned it)
* **Joinability:** labels must join cleanly to events/decisions/entities (stable keys).
* **Idempotent writes:** duplicates/retries must not create duplicate label events.
* **Authority boundaries:** not every component can write labels; “evidence” ≠ “truth”.

""""
}


tighten vs loose split
{
""""
Here’s the **v0-thin “tighten vs stay loose”** for the **Label Store** (same pattern we’ve been using).

## What needs tightening (pin this in the spec)

### 1) Authority boundaries (truth vs evidence)

* What counts as a **label assertion** (truth claim) vs **evidence** (supporting info).
* Who is allowed to write which label families (e.g., Case Workbench vs dispute feed).
* Append-only rule: **no edits**; corrections are new events.

### 2) Label targets + join keys (the biggest integration risk)

Pin the target types and required keys, e.g.:

* **Event-level** (by `event_id` and/or `request_id/decision_id`)
* **Entity-level** (by `EntityRef`/FeatureKey)
* **Case-level** (by `case_id`)
  And whether `ContextPins` are required for scoping (in your closed-world setup, they usually should be).

### 3) Label taxonomy (minimal but explicit)

* Label families (fraud/FP/dispute/outcome/etc.)
* Allowed value sets (enums) + reason codes posture
* Confidence / severity fields (optional but define if present)
* “Unknown/unlabeled” semantics (don’t let implementer invent meanings)

### 4) Time semantics (“as-of” correctness)

This is critical for training and audit.
Pin at least:

* `effective_time` (when the label applies to the world)
* `observed_time` (when the platform learned it)
* “As-of T” queries must use **observed_time** to prevent leakage.

### 5) Write contract + idempotency

* Input object: `LabelAssertion` / `LabelEvent`
* Required idempotency key rule (e.g., `{source_system, source_event_id}` or a hash)
* Duplicate behaviour: duplicates must be no-ops (or produce a DUPLICATE receipt if you want)

### 6) Conflict and precedence posture

When two sources disagree:

* v0 rule: keep **both** in the timeline, and define how “current label” is chosen:

  * precedence by source authority, or
  * precedence by latest observed_time, or
  * “CONFLICT” state returned (often safest)
    Pick one; don’t leave it ambiguous.

### 7) Materialized views semantics (even if storage is loose)

Pin the meaning of:

* `current_label(target)` (what rule picks “current”)
* `label_as_of(target, t)` (uses observed_time)
* `timeline(target)` (append-only event list, deterministically ordered)

### 8) Provenance requirements

Each label event must carry:

* `source` (case system, dispute feed, rule, etc.)
* `actor` (optional)
* `evidence_ref` (by-ref, optional)
* timestamps (effective/observed)
  So audit and model training can trust it.

### 9) Privacy posture

* Prefer **by-ref** for documents/evidence blobs.
* Explicitly forbid storing raw sensitive payloads unless necessary.

---

## What can stay loose (implementation freedom)

* Storage backend (DB vs parquet vs log)
* Indexing tech (search engine vs secondary indices)
* API transport (HTTP/gRPC/CLI)
* Batch vs stream ingestion for label assertions
* Caching/materialization strategy
* UI/Workbench integration mechanics (as long as it produces the pinned LabelAssertion shape)
* Retention numbers (can be config), archival mechanics

---

### One-line v0 contract for Label Store

**“Label Store ingests authoritative label assertions as append-only timeline events with effective/observed time semantics and serves current/as-of labels deterministically and joinably.”**
""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s a **Label Store v0-thin package** (I’m choosing the **smaller 3-doc set** so you don’t get bogged down, while still pinning the leakage-critical “as-of” semantics + joinability).

---

## LS v0-thin doc set (3 docs)

### **LS1 — Charter & Authority Boundaries**

* What Label Store is (lagged truth plane; append-only timelines)
* Truth vs evidence boundary (who can assert labels; evidence is by-ref)
* Non-goals (no case UI, no training pipelines here)
* Core laws: append-only, idempotent writes, joinability, no silent overwrites

### **LS2 — Contracts, Time Semantics, Conflicts, Views**

* **Target model + join keys** (event/entity/case targets; ContextPins posture)
* **Label taxonomy v0** (families + value posture; “unknown/unlabeled” semantics)
* **Time semantics**: `effective_time_utc` vs `observed_time_utc` + **as-of rules** (observed-time drives leakage-safe reads)
* **Conflict/precedence posture** (how “current” is computed; conflict representation)
* Materialized views semantics:

  * `timeline(target)`
  * `label_as_of(target, t)`
  * `current_label(target)`
* Inline examples (label events, conflict timeline, as-of query)

### **LS3 — Ingestion, Idempotency, Privacy, Ops & Acceptance**

* Write interface (LabelAssertion/LabelEvent ingest)
* Idempotency key rules + duplicate behaviour
* Optional receipts (accepted/duplicate/rejected) posture
* Privacy/redaction + by-ref evidence rules
* Observability minimums (lag, write failures, conflict rates)
* Acceptance scenarios (append-only, as-of correctness, duplicate safety)

---

## 1 contracts file (v0)

### `contracts/ls_public_contracts_v0.schema.json`

Recommended `$defs` (v0):

* `ContextPins`
* `LabelTarget`

  * `target_type` enum: `EVENT|ENTITY|CASE`
  * `target_ref` (string) + optional structured fields if needed (e.g., `entity_ref`)
* `LabelFamily` (small enum, v0)
* `LabelValue` (string enum per family **or** generic string + optional `reason_code`)
* `LabelEvent`

  * required: `label_event_id`, `idempotency_key`, `context_pins`, `target`, `label_family`, `label_value`,
    `effective_time_utc`, `observed_time_utc`, `source`
  * optional: `actor`, `evidence_ref`, `supersedes_label_event_id`, `notes`
* `WriteLabelRequest` / `WriteLabelReceipt` *(optional but useful)*

  * receipt outcome: `ACCEPTED|DUPLICATE|REJECTED` + `reason_code` + `retryable`
* `GetCurrentLabelRequest/Response`
* `GetLabelAsOfRequest/Response`
* `GetTimelineRequest/Response`
* `ErrorResponse` (thin)

(Examples in LS2/LS3 must validate against this schema once Codex materializes it.)

---

## File tree

```text
docs/
└─ model_spec/
   └─ label_and_case/
      └─ label_store/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ LS1_charter_and_authority_boundaries.md
         │  ├─ LS2_contracts_time_semantics_conflicts_views.md
         │  └─ LS3_ingestion_idempotency_privacy_ops_acceptance.md
         │
         └─ contracts/
            └─ ls_public_contracts_v0.schema.json
```

""""
}
