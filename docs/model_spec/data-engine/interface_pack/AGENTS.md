# AGENTS.md — Interface Pack Review Router
_As of <2026-01-02>_

This folder contains the **Data Engine Black-Box Interface Pack**: a platform-facing contract that
lets downstream specs depend on the engine **without** importing segment/state internals. 

NOTE: It is not your reference when building or fixing the data engine!! Refer to the other folders which contain the spec `layer-1/`, `layer-2/` and `layer-3/`! Once again, this is not a binding spec for dealing with the data engine's run, stay away from this unless you are working on other components and want to see the blackbox view of the engine!

This router instructs agents (e.g., Codex) how to **review and tighten** the pack for correctness,
consistency, and “black-box purity”.

---

## 0) Scope (binding)

**In scope (review + edits allowed):**
- `data_engine_interface.md`
- `engine_outputs.catalogue.yaml`
- `engine_gates.map.yaml`

**Out of scope (do not edit unless explicitly asked):**
- engine implementation under `packages/engine/...`
- segment expanded docs and contracts (these are **inputs** / source of truth)
- any guides or harvest scratch folders (if present)

**Primary goal:** ensure the three files are **fact-based**, **internally consistent**, and **usable**
by downstream platform components (Scenario Runner, Ingestion Gate, Event Bus, Features, Labels, Governance).

---

## 1) What each file is responsible for (binding)

### A) `data_engine_interface.md` (human contract)
Must state only **boundary truths**:
- identity + determinism promises
- output discovery/addressing rules
- join semantics (keys + scope)
- HashGate rulebook (“no PASS → no read”)
- segment-level invariants that prevent misuse (e.g., “order authority lives only in X”)

Must **not** describe algorithms, model mechanics, or state internals.

### B) `engine_outputs.catalogue.yaml` (machine catalogue)
Single inventory of engine exposures:
- outputs (surfaces/streams/gate artifacts)
- path templates + partition keys
- schema/dictionary refs
- primary/join keys
- gating requirements (`read_requires_gates`)

### C) `engine_gates.map.yaml` (machine gate semantics)
Operational definition of every gate:
- where the bundle/flag lives
- hashing/index law
- verification steps (fail closed)
- which outputs the gate authorizes

---

## 2) Source precedence for review (binding)

When reviewing or correcting the interface pack, treat sources as:

1) **Contracts + dataset dictionaries + schemas** (authoritative for inventories, keys, schema refs)
2) **State-expanded docs** (authoritative for boundary semantics: gates, invariants, partition laws)
3) **Implementation** (drift detection only; never silently overrides specs)

If code disagrees with specs, record a **DRIFT NOTE** in `data_engine_interface.md`
(Informative subsection) and keep spec truth unless the user requests a change.

---

## 3) Non-negotiables (binding)

1) **Black-box purity**
   - No algorithm steps.
   - No RNG internals unless required for *external verification* (usually it is not).

2) **Token convention**
   - Fingerprint scoping MUST use: `fingerprint={manifest_fingerprint}` (exact).
   - Do not introduce variants.

3) **No PASS → no read**
   - If a segment declares a HashGate, any gated output MUST declare the gate in:
     - `engine_outputs.catalogue.yaml: read_requires_gates`
     - and the gate must exist in `engine_gates.map.yaml`.

4) **Fail closed**
   - Gate verification steps must be implementable and fail closed on any missing file / mismatch.

---

## 4) Review checklist (what to focus on)

### P0 — Blocking correctness
- `data_engine_interface.md` contains only boundary truths (no internals).
- Identity/determinism tuple is unambiguous:
  - what defines world vs realisation vs logs partitioning
- Addressing rules are consistent (tokens + templates).
- “no PASS → no read” is explicitly defined and delegated to `engine_gates.map.yaml` for mechanics.

### P1 — Completeness / alignment across the three files
- Every `output_id` is unique in the catalogue.
- Every `gate_id` referenced anywhere exists in `engine_gates.map.yaml`.
- Every gate authorizes at least one output.
- Every gated output lists the correct `read_requires_gates`.
- Segment summaries in `data_engine_interface.md` match catalogue/gate map (no missing egress).

### P2 — Clarity (only if it reduces ambiguity)
- Definitions are minimal but sufficient (authority surface, stream, gate, receipt, sealing).
- Segment invariants that prevent misuse are present where the specs say so.

---

## 5) Standard review workflow (binding)

For each segment in build order (e.g., 1A → 1B → 2A → 2B → ... → 6B):

1) **Inventory check (catalogue)**
   - confirm outputs exist and have correct path templates + partitions
   - confirm schema/dictionary refs resolve

2) **Gate check (gate map)**
   - confirm gate artifacts + hashing law + verification steps
   - confirm `authorizes_outputs` is complete (at least fingerprint-scoped egress)

3) **Interface doc check**
   - confirm segment summary lists:
     - egress surfaces
     - gate artifacts + “no PASS → no read”
     - any explicit invariants (order authorities, “egress is order-free”, etc.)

4) **Cross-file integrity**
   - no dangling IDs (output_id/gate_id)
   - no contradictions in token conventions

5) **(Optional) Drift scan in implementation**
   - only if there is uncertainty or repeated mismatches
   - record drift notes; do not silently rewrite the contract

---

## 6) Output format for review results (binding)

When reporting review results, produce:
- **P0 issues** (must fix)
- **P1 issues** (missing/misaligned facts)
- **P2 suggestions** (only if they reduce ambiguity)

Each issue must include:
- file + section/key
- what is wrong
- exact proposed change (diff-style or replacement snippet)

---

## 7) Quick terminal checks (informative)

Suggested commands:
- Token consistency:
  - `rg "fingerprint=\{(?!manifest_fingerprint\})" -n .`
- Gate references sanity:
  - `rg "read_requires_gates" engine_outputs.catalogue.yaml -n`
  - `rg "gate_" engine_gates.map.yaml -n`
- YAML validity (if tooling exists):
  - `python -c "import yaml,sys; yaml.safe_load(open('engine_outputs.catalogue.yaml')); yaml.safe_load(open('engine_gates.map.yaml'))"`
