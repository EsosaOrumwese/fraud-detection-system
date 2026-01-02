Below is a **paste-ready `README.md`** for:

`docs/model_spec/control_and_ingress/scenario_runner/`

It’s written to match your style: clear authority boundaries, “rails-first”, and minimal-but-complete.

---

# Scenario Runner (Control & Ingress) — Spec Folder

This folder defines the **Scenario Runner** component in the Control & Ingress plane.

Scenario Runner is responsible for **planning and anchoring runs** of the platform:

* selecting (or referencing) a **world** (`parameter_hash`, `manifest_fingerprint`)
* defining a **scenario** (run knobs / load shape)
* assigning a **run identity** (`scenario_id`, `run_id`, optional `seed`)
* producing **run discovery surfaces** so downstream components can locate the run and its pinned inputs

Scenario Runner treats the Data Engine as a **black box** and MUST NOT depend on any engine segment/state internals.

---

## 0) Status and scope

### 0.1 Scope (Binding)

This component spec is authoritative for:

* The **run planning boundary**: how runs are requested, planned, and anchored
* The **run identity model** and propagation requirements for Scenario Runner outputs
* The **run discovery surface** used by downstream components (e.g., `run_facts_view`)
* The **contract shapes** in `contracts/` for:

  * run requests
  * scenario definitions
  * run discovery/facts views
  * optional status-change event payloads

### 0.2 Non-scope (Binding)

This folder does **not** specify:

* Data Engine internals (segments/states, intermediate artefacts)
* Ingestion Gate behaviour (schema enforcement/quarantine/idempotency at plane entry)
* Event bus topology or infrastructure deployment
* Feature/Decision logic, labelling logic, or model training

---

## 1) Reading order (Strict)

1. Platform Rails:

   * `docs/model_spec/observability_and_governance/cross_cutting_rails/cross_cutting_rails.md`
   * Rails authoritative contracts under:

     * `docs/model_spec/observability_and_governance/cross_cutting_rails/contracts/`
2. This folder:

   * `scenario_runner.md`
3. Contracts:

   * `contracts/README.md`
   * schemas in `contracts/`
4. Examples and diagrams:

   * `examples/*`
   * `diagrams/*`

---

## 2) Authority boundaries (Rails-first)

### 2.1 Rails contracts imported (Binding)

Scenario Runner MUST reference (not duplicate) the following Rails-owned contracts:

* `.../cross_cutting_rails/contracts/run_record.schema.yaml` (run anchor object)
* `.../cross_cutting_rails/contracts/id_types.schema.yaml` (canonical ID + refs types)
* `.../cross_cutting_rails/contracts/canonical_event_envelope.schema.yaml` (only if emitting status events)
* `.../cross_cutting_rails/contracts/ingestion_receipt.schema.yaml` (if Scenario Runner records boundary receipts)
* `.../cross_cutting_rails/contracts/hashgate_receipt.schema.yaml` (if Scenario Runner stores PASS refs)

Scenario Runner MUST NOT redefine canonical identity, envelope, or receipt semantics.

### 2.2 Scenario Runner owned contracts (Binding)

This folder owns the following boundary schemas:

* `scenario_run_request.schema.yaml` — request/plan a run (tool-agnostic)
* `scenario_definition.schema.yaml` — scenario knobs catalogue item (RO authority surface)
* `run_facts_view.schema.yaml` — downstream discovery surface for “active run(s)” and pinned refs
* `run_status_event.payload.schema.yaml` — payload-only schema for status-change events (optional)

---

## 3) Folder layout

```
scenario_runner/
├─ scenario_runner.md
├─ contracts/
│  ├─ README.md
│  ├─ scenario_run_request.schema.yaml
│  ├─ scenario_definition.schema.yaml
│  ├─ run_facts_view.schema.yaml
│  └─ run_status_event.payload.schema.yaml   # optional
├─ examples/
│  ├─ run_request.baseline.json
│  ├─ run_request.multi_scenarios.json
│  ├─ run_record.planned.json
│  ├─ run_facts_view.active.json
│  └─ run_status_event.started.json          # optional
└─ diagrams/
   └─ scenario_runner_flow.ascii.txt
```

---

## 4) The three binding anchors in this folder

### 4.1 `scenario_runner.md` (Binding + Informative)

Human-readable specification that defines:

* responsibilities and non-goals
* run planning lifecycle (PLANNED → STARTED → COMPLETED/FAILED)
* how identity tuples are created and propagated
* what Scenario Runner pins for downstream discovery (run facts)

### 4.2 `contracts/*` (Binding)

Machine-checkable schemas used by other platform specs and implementers.

### 4.3 `run_facts_view` (Binding)

The run discovery surface MUST be the **single** downstream mechanism for:

* discovering active run(s)
* pinning run identity and authoritative references
* recording upstream PASS references (if tracked)

Downstream components MUST NOT infer runs by scanning storage paths or guessing “latest”.

---

## 5) “Don’t couple to internals” rule (Binding)

Scenario Runner MUST:

* treat the Data Engine as a black box
* depend only on the engine boundary/interface artefacts (when available)
* avoid segment/state coupling or assumptions about engine ordering

---

## 6) Versioning and change control (Binding)

Breaking changes to Scenario Runner contracts MUST be introduced via:

* new schema versions with a parallel support window, or
* additive evolution that remains backward-compatible, or
* explicit cutover notes coordinated with dependent components.

Scenario Runner MUST declare which Rails version it is compliant with.

---

## 7) Notes for implementers (Informative)

* Scenario Runner is a **control-plane** component: its primary deliverables are **run anchoring**, **pinning**, and **discoverability**.
* Ingestion Gate remains the **hard enforcement boundary** for schema validation, PASS verification, and quarantine semantics (specified elsewhere).
