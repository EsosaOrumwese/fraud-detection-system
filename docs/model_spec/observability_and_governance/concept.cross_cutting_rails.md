black-box framing:
{
""""
Through the same modular lens, **cross-cutting rails** are a **shared “laws + shared types” pack** (not a runtime service) that every component *imports* and *must obey*.

## Level 0 — Black-box view

**Input:** any component boundary (request/response, event, artifact write/read, admin change)
**Output:** boundaries that are **joinable, auditable, replayable, and policy-safe** (or explicitly FAIL/QUARANTINE)

## Level 1 — Rail families (responsibility chunks)

These are the “modules” of the rails (they can be sections in one doc tree, not separate services):

1. **Contract authority & versioning**

* JSON-Schema is authoritative for shape
* validation targeting rules (e.g., `kind` + `contract_version`) 
* version bump rules + compatibility posture

2. **Identity & lineage pins**

* the platform’s canonical pin set (your ContextPins: `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`) 
* “pins carried everywhere” requirement (requests, responses, audit records)

3. **Addressing & ArtifactRef semantics**

* canonical “by-ref” locator shape + optional digests
* addressing conventions (including your `fingerprint={manifest_fingerprint}` posture)
* “no scan-latest-and-hope” discoverability

4. **Validation + gating (no PASS → no read)**

* what it means to “PASS”
* receipt semantics (admit/quarantine, gates, proofs)
* downstream must not proceed without the required PASS evidence (this is the platform’s safety rail)

5. **Determinism & replay rail**

* event-time discipline (event_time ≠ ingest/apply time) 
* idempotency keys and duplicate safety (at-least-once realities)
* watermark basis semantics (e.g., per-partition `next_offset_to_apply`) used by graph/features provenance 
* deterministic hashing rules when you publish hashes (stable ordering + numeric representation rules) 

6. **Config/policy pinning**

* config versions must be explicit + recorded (no invisible “config drift”)
* deterministic selection rules for “what policy/model is in effect” (ties into MPR/MF)

7. **Error + retryability semantics**

* standard “explicit failure posture” (no invented partial truth)
* shared `ErrorResponse` shape with `retryable` flag (many components already follow this pattern)

8. **Privacy & access rails**

* tokenization posture, “by-ref evidence” preference
* redaction rules for logs/audit artifacts
* role-level access boundaries

9. **Observability/governance hooks**

* mandatory correlation IDs in telemetry
* audited change events (retention/config/promotions)
* these rails are what your Observability & Governance plane *implements/operationalizes*.

""""
}


tighten vs loose split
{
""""
Here’s the **tighten vs loose** split for the **cross-cutting rails**. Since rails are “laws,” the tight part is mostly **shared primitives + invariants**; the loose part is **how each component enforces them**.

## What needs tightening (global, non-negotiable)

### 1) Shared primitives (one canonical set)

* **ContextPins** (exact fields + meaning): `scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash` (+ any window key if you standardize it).
* **ArtifactRef/Locator** (by-ref shape): ref + optional digest + schema/version fields.
* **Contract targeting fields**: how an object declares its schema (`kind` + `contract_version` or equivalent).
* **Standard enums** you keep reusing: `PASS/FAIL`, `ACCEPTED/DUPLICATE/QUARANTINED`, `retryable` flag.

### 2) “No PASS → no read” gating semantics

* What counts as **PASS evidence** (receipt/gate artifact), and where it must be recorded.
* Hard rule: downstream components must not proceed without required PASS artifacts.
* Mismatch behaviour: if PASS evidence missing or inconsistent → fail closed / quarantine (pick posture).

### 3) Determinism & replay laws (only the parts that are cross-component)

* **At-least-once reality**: duplicates can happen; idempotency is required where side effects exist.
* **Event time vs ingest/apply time**: `event_time` is preserved; `ingest_time` is stamped separately.
* **Watermark semantics**: per partition `next_offset_to_apply` (exclusive) if you use watermarks.
* **Hash determinism** rules when hashes are published:

  * stable ordering of maps/lists
  * numeric representation rules (avoid float drift)

### 4) Addressing & pinning rules

* Addressing token conventions (including `fingerprint={manifest_fingerprint}`).
* “No implicit latest”: selection must be explicit/pinned and recorded.

### 5) Config/policy pinning + change control hooks

* Config versions must be explicit and recorded in ledgers/outputs.
* Policy/model selection must be deterministic given scope inputs (even if registry does it).

### 6) Privacy rails

* “By-ref evidence” preference (don’t copy blobs).
* Never log secrets; PII posture (tokenize/redact rules at boundaries).
* Role-level access rules (minimal).

### 7) Canonical error semantics

* Standard `ErrorResponse` shape with `error_code`, `message`, `retryable`.
* Shared failure categories where useful (invalid input vs dependency down vs internal).

---

## What can stay loose (component-specific / implementation freedom)

* **Where** validation happens (IG vs downstream), as long as the rail law is satisfied.
* Exact **validator tooling**, storage backends, orchestration tech.
* Exact **metric names** and dashboards (observability plane can decide), as long as correlation fields and meaning are preserved.
* Component-specific idempotency key composition (rails can require “must exist” and “must be deterministic,” but the key recipe can live in each component spec).
* Performance/latency tactics (caching, batching) as long as semantics don’t change.
* Detailed governance workflows (approvals UI, ticketing), as long as changes are auditable.

---

### The practical takeaway

Rails should be a **small set of globally pinned shared types + invariants**. Everything else (how you enforce, optimize, or operationalize) lives in component specs like SR/IG/EB/etc.

""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s a **cross-cutting rails v0-thin doc set** (kept lean) + **1 contracts file** + **file tree**.

---

## Rails v0-thin doc set (3 docs)

### **CR1 — Shared Primitives & Contract Authority**

Pins the *global shared types* and “schemas are law”.

* JSON-Schema authority + contract targeting fields (`kind`, `contract_version` posture)
* **`ContextPins`** (exact fields + meaning)
* **`ArtifactRef` / Locator** (by-ref standard + digest fields)
* Canonical outcome enums you reuse everywhere (`PASS/FAIL`, `ACCEPTED/DUPLICATE/QUARANTINED`, `retryable`)
* Canonical `ErrorResponse` shape

### **CR2 — Gating, Addressing, Determinism & Replay Laws**

Pins the laws that prevent drift across components.

* **No PASS → no read** semantics (what counts as PASS evidence; fail-closed posture)
* Addressing conventions (incl. `fingerprint={manifest_fingerprint}` rule where relevant)
* Replay/idempotency laws (at-least-once reality, idempotency required where side effects exist)
* Time semantics (`event_time` vs `ingest_time`)
* Watermark semantics (if used): `next_offset_to_apply` (exclusive)
* Hash determinism rules (stable ordering + numeric representation rules)

### **CR3 — Config/Policy Pinning, Privacy, Change Control & Observability Hooks**

Pins the governance hooks that every component must comply with.

* Config version pinning rules (no invisible config drift; record versions in ledgers)
* Policy/model selection determinism hooks (inputs that must be recorded; ties to registry)
* Privacy rails (by-ref evidence, no secrets in logs, redaction posture)
* Change control event requirements (retention/config/promotions must emit auditable events)
* Correlation IDs posture (which IDs must appear in telemetry/artifacts)

---

## 1 contracts file (v0)

### `contracts/rails_public_contracts_v0.schema.json`

This is the **shared `$defs` pack** that other component schemas can reference (or copy verbatim in v0, but must match exactly).

Recommended `$defs`:

* `ContextPins`
* `ContractTarget` (e.g., `kind`, `contract_version`)
* `Digest` (alg + value)
* `ArtifactRef`
* `PassFailStatus`
* `ReceiptOutcome` (ACCEPTED/DUPLICATE/QUARANTINED)
* `ErrorResponse` (`error_code`, `message`, `retryable`)
* `WatermarkBasis` (map of `partition_id` → `next_offset_to_apply`)
* `IdempotencyKey` (string + optional scope fields)

*(No “canonical event language” here — just the base primitives and laws.)*

---

## File tree layout

```text
docs/
└─ model_spec/
   └─ observability_and_governance/
      └─ cross_cutting_rails/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ CR1_shared_primitives_and_contract_authority.md
         │  ├─ CR2_gating_addressing_determinism_replay.md
         │  └─ CR3_config_privacy_change_control_observability_hooks.md
         │
         └─ contracts/
            └─ rails_public_contracts_v0.schema.json
```

""""
}
