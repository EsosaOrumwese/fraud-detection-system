# AGENTS.md — Data Engine Interface Pack Derivation Router
_As of <2026-01-02>_

This folder is the authoritative **black-box interface** from the Data Engine to the rest of the platform.

Codex must derive/update the interface pack by reading:
1) Spec contracts (artefact registry, dataset dictionaries, schemas)
2) State-expanded docs (boundary facts: outputs, gates, paths)
3) Implementation (writer paths + gate hash logic), used ONLY to confirm facts and detect drift

Codex MUST keep outputs **fact-based** and **drift-proof**:
- Prefer contracts/dictionaries as the source of truth for inventories and schema refs.
- Prefer state-expanded docs as the source of truth for semantics and gate laws.
- Use implementation to confirm (and flag) mismatches; do not invent new semantics.

---

## 0) Non-negotiables (Binding)
- All path templates MUST use the token: `fingerprint={manifest_fingerprint}` consistently.
- Interface pack MUST remain **black-box**: no segment/state algorithms, only exposed surfaces/streams, identity, discovery, join keys, and gates.
- “No PASS → no read” is mandatory wherever a gate is declared.
- Do not hand-edit derived inventories if a generator exists; fix upstream truth and regenerate.

---

## 1) Inputs Codex must scan (strict)
For each segment in order (1A..6B):
- contracts:
  - `artefact_registry_<SEG>.yaml` (or equivalent)
  - `dataset_dictionary.layer*. <SEG>.yaml`
  - `schemas.<SEG>.yaml`
  - any shared schema file(s): `schemas.layer*.yaml`, `schemas.ingress.layer*.yaml`, etc.
- state-expanded docs:
  - all states OR at minimum: overview + output-writing states + validation state
- implementation:
  - engine writers (where paths are materialized)
  - validation bundle builder + `_passed.flag` writer
  - any “receipt” writers (S5/S6-style)

---

## 2) Output artifacts Codex must produce
Codex updates these files ONLY (others are inputs):
1) `data_engine_interface.md`
2) `engine_outputs.catalogue.yaml`
3) `engine_gates.map.yaml`
4) `contracts/*.schema.yaml` as needed

Codex may create/maintain a derived workspace:
- `interface_pack/_harvest/` (ignored by specs; used for intermediate JSON)
- `tools/` scripts for generation/validation (preferred)

---

## 3) Segment-by-segment workflow (repeatable)
For segment <SEG>:

### Step A — Harvest from contracts (inventory spine)
- Parse artefact registry + dataset dictionary:
  - list all externally readable outputs (tables/files/streams)
  - capture: output_id, partitions, path templates, schema refs, PK/join keys, immutability hints
- Verify schema refs exist (anchors resolve).

### Step B — Harvest from expanded docs (semantics)
- Extract:
  - identity tuple assumptions
  - gate semantics: what constitutes PASS, how bundles are hashed, what receipts exist
  - “order authorities” and join constraints called out explicitly

### Step C — Confirm with implementation (drift detection)
- Locate the writer path templates used in code and compare with contracts.
- Locate gate hashing / index ordering logic in code and compare with expanded docs.
- If mismatch: record as a “DRIFT FINDING” (do not silently change semantics).

### Step D — Update interface pack
- Add/update segment entries in:
  - outputs catalogue (IDs + path templates + join keys + required gates)
  - gates map (verification method + authorizes_outputs)
- Update the human-readable interface doc only with black-box truths.

---

## 4) Validation / acceptance checks (must pass)
- Every `output_id` is unique.
- Every output with `read_requires_gates` references an existing `gate_id`.
- Every gate `authorizes_outputs` references existing `output_id`s.
- All path templates use `fingerprint={manifest_fingerprint}` consistently where fingerprint-scoped.
- Schema refs resolve to real anchors.
- No internal-state coupling appears in `data_engine_interface.md`.

---

## 5) Deliverable posture
Codex MUST work in small commits:
- One segment at a time OR one file at a time (prefer one file at a time).
- Include a short “DRIFT FINDINGS” section in commit message when applicable.
