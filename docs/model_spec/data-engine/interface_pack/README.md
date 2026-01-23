# Data Engine Interface Pack (Black-Box Boundary)

This folder defines the **stable, black-box interface** that the rest of the platform depends on when integrating with the Data Engine.

It exists so that **Scenario Runner, Ingestion Gate, Event Bus, Feature/Decision planes, Label/Case, and Observability/Governance** can be **precise** about:
- **Identity & determinism**
- **Where outputs live** and how to discover them
- **How to join** against engine authority surfaces
- **Which HashGates must PASS** before any component may read/ingest

…without importing **any** segment/state internals (1A→6B).

---

## 0) Status and scope

### 0.1 Scope (Binding)
This interface pack is authoritative for:
- **Identity tuple definitions** and the determinism/immutability promises tied to them
- **Output inventory** (streams + surfaces) and how they are addressed/discovered
- **HashGate semantics** (“no PASS → no read”) and operational verification rules
- **Schemas** used at the engine/platform boundary (invocation, envelope, locators, gate receipts)

### 0.2 Non-scope (Binding)
This pack does **not** describe:
- Segment/state algorithms, intermediate artefacts, training procedures, or implementation details
- Internal ordering of steps within the engine
- Performance targets or infrastructure deployment (handled elsewhere)

---

## 1) Directory layout

```

interface_pack/
├─ README.md                               # (This file) – index + usage rules
├─ data_engine_interface.md                # Binding – human-readable contract
├─ engine_outputs.catalogue.yaml           # Binding – machine-readable output inventory (derived view)
├─ engine_gates.map.yaml                   # Binding – machine-readable gate map (derived view)
├─ contracts/                              # Binding – boundary schemas for other components to import
│  ├─ engine_invocation.schema.yaml
│  ├─ canonical_event_envelope.schema.yaml
│  ├─ engine_output_locator.schema.yaml
│  └─ gate_receipt.schema.yaml
├─ examples/                               # Informative – concrete examples for implementers
│  ├─ engine_invocation.min.json
│  ├─ canonical_event.example.json
│  ├─ output_locator.example.json
│  └─ gate_receipt.example.json
└─ diagrams/                               # Informative – one boundary flow diagram
   └─ engine_boundary_flow.ascii.txt

```

---

## 2) The three binding “anchors”

### 2.1 `data_engine_interface.md` (Binding)
Human-readable contract for platform authors.

Must answer:
- What the platform **MAY/MUST** assume about the engine (black box)
- Identity tuple definitions: `parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id`, `run_id`
- Determinism promise (same identity tuple ⇒ same outputs)
- Output classes: **streams**, **authority surfaces**, **HashGates**
- Discovery rules and path templates (must use `manifest_fingerprint={manifest_fingerprint}` consistently)
- Join semantics and canonical join keys (global vs fingerprint-scoped)
- Gate rulebook: what constitutes verification; “no PASS → no read”
- Compatibility/versioning rules for breaking changes

### 2.2 `engine_outputs.catalogue.yaml` (Binding; **derived view**)
Machine-readable inventory of every engine exposure to the platform.

Each `output_id` entry defines:
- `class`: `stream | surface`
- `scope`: `world | run | scenario` (or equivalent)
- `path_template` (must include `manifest_fingerprint={manifest_fingerprint}` where applicable)
- `partitions` (e.g., `manifest_fingerprint`, `run_id`, `scenario_id`, date buckets if any)
- `schema_ref`, `dictionary_ref` (authoritative references)
- `primary_key`, `join_keys`
- `read_requires_gates` (list of gate IDs required before read/ingest)
- `immutability` semantics

**Anti-drift rule (Binding):**
- This file SHOULD be generated from the engine’s authoritative inventory (artefact registry + dataset dictionary).
- It MUST NOT be hand-edited if a generator exists; edit the upstream inventory and regenerate.

### 2.3 `engine_gates.map.yaml` (Binding; **derived view**)
Machine-readable operational definition of all HashGates.

Each `gate_id` entry defines:
- The gate’s authoritative artefacts (bundle path template, `_passed.flag` template, optional indices/digests)
- Verification method (presence checks, digest checks, index hash checks, etc.)
- `authorizes_outputs` (list of `output_id`s in the catalogue)
- `required_by_components` (which platform components must verify; and when)

**Anti-drift rule (Binding):**
- This file SHOULD be generated from the engine’s validation bundle conventions and registry.
- It MUST remain consistent with `engine_outputs.catalogue.yaml`.

---

## 3) Boundary contracts (Binding)

All schemas under `contracts/` are intended to be **imported** by other platform specs.

### 3.1 `engine_invocation.schema.yaml`
Defines the **minimum request** a Scenario Runner (or equivalent orchestrator) sends to the engine:
- identity tuple fields
- optional scenario definition refs / run knobs
- idempotency / request correlation fields

### 3.2 `canonical_event_envelope.schema.yaml`
Defines the minimal envelope the platform can rely on for **any** event emitted from the engine:
- identity tags (world + realisation)
- dedupe key (`event_id`)
- temporal fields (`event_time`, `emitted_at`)
- typing/versioning fields (`event_type`, `schema_version`)
- correlation (`run_id`, `scenario_id`, optional trace IDs)

> If your platform maintains a single cross-cutting envelope contract elsewhere, this schema may be a reference/alias. The engine interface pack must still point to the canonical envelope contract used by Ingestion/Event Bus.

### 3.3 `engine_output_locator.schema.yaml`
Defines how downstream systems **pin** engine outputs for discovery (e.g., inside `run_facts_view`):
- `{ output_id, manifest_fingerprint, run_id?, scenario_id?, path, schema_ref, content_digest? }`

### 3.4 `gate_receipt.schema.yaml`
Defines the payload shape for `_passed.flag` / gate receipts:
- `{ gate_id, status, produced_at, identity tuple, digest(s), index_hash?, … }`

---

## 4) How platform components must use this pack

### 4.1 Referencing rule (Binding)
Any platform spec that reads/ingests/joins engine data MUST:
1) Reference `data_engine_interface.md` for identity + gate semantics
2) Use `engine_outputs.catalogue.yaml` to name outputs (`output_id`) and locate them
3) Use `engine_gates.map.yaml` to determine which PASS receipts must be verified

### 4.2 Gate enforcement rule (Binding)
**No PASS → no read.**  
A component MUST NOT read/ingest an engine output unless all gates listed in:
- `read_requires_gates` (catalogue) are verified as PASS per:
- `verification_method` (gate map)

### 4.3 Discovery rule (Binding)
Components MUST discover engine outputs using:
- output locators (preferred), or
- `path_template` + partition keys in the catalogue

Path templates MUST follow the convention:
- `manifest_fingerprint={manifest_fingerprint}` (exact token usage)

### 4.4 Join rule (Binding)
When joining events to surfaces, components MUST use:
- the `join_keys` declared in the catalogue
- the scope declared for those keys (global vs fingerprint-scoped)

Components MUST NOT infer undocumented join keys.

---

## 5) Maintenance and change control

### 5.1 Versioning (Binding)
Breaking changes MUST be introduced by one (or more) of:
- new `output_id` (preferred) and deprecation of old IDs
- schema version bumps with parallel support windows
- explicit compatibility notes in `data_engine_interface.md`

### 5.2 Regeneration workflow (Binding)
When engine outputs or gates change:
1) Update authoritative upstream inventory (artefact registry / dataset dictionary / validation registry)
2) Regenerate:
   - `engine_outputs.catalogue.yaml`
   - `engine_gates.map.yaml`
3) Update examples (if shapes changed)
4) Ensure references remain consistent (no dangling `output_id` or `gate_id`)

### 5.3 “Don’t couple to segments” rule (Binding)
`owner_segment` fields (if present) are provenance only.  
Platform components MUST NOT depend on segment/state internals or ordering.

---

## 6) Reading order (Suggested)
1) `data_engine_interface.md`
2) `engine_outputs.catalogue.yaml`
3) `engine_gates.map.yaml`
4) `contracts/*`
5) `examples/*`, `diagrams/*`

---

## 7) Glossary (Informative)
- **World identity:** `manifest_fingerprint` (and its associated `parameter_hash`)
- **Realisation identity:** run/scenario/seed tuple identifying a specific instantiation
- **Authority surface:** fingerprint-keyed, read-only “law book” used for joins/context
- **Stream:** production-shaped event flow emitted for ingestion/bus
- **HashGate:** validation bundle + PASS receipt that authorizes downstream reads
- **Output locator:** canonical pin object used by run discovery surfaces (e.g., run facts)

