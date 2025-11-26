# Layer-3 Router - Segments 6A & 6B

_As of 2025-11-25_

Layer-3 specs for **6A (Entity & Product World)** and **6B (Behaviour & Fraud Cascades)** are now **fully expanded and sealed**. Treat the state-flow docs, schemas, dataset dictionaries and artefact registries under this tree as authoritative for implementation; do not change them unless spec work is explicitly opened.

## 0) Scope
- Layer-3 inherits Layer-1/Layer-2 artefacts as read-only authority surfaces (reference them via `../layer-1/...` and `../layer-2/...`).
- Segments in scope: **6A** (entity & product world) and **6B** (behaviour & fraud cascades). Both have S0–S5 state specs and matching contracts.
- No implementation code lives here; this tree is for specifications only. Implementation belongs in `packages/engine` and downstream services, wired to these contracts.

## 1) Reading Order
1. `specs/state-flow/6A/` - expanded state docs for 6A (S0–S5).
2. `specs/contracts/6A/` - `schemas.6A.yaml`, `dataset_dictionary.layer3.6A.yaml`, `artefact_registry_6A.yaml`.
3. `specs/state-flow/6B/` - expanded state docs for 6B (S0–S5).
4. `specs/contracts/6B/` - `schemas.6B.yaml`, `dataset_dictionary.layer3.6B.yaml`, `artefact_registry_6B.yaml`.
5. Any Layer-3 narrative docs (once added) for background and design rationale.

## 2) Folder expectations
- `specs/state-flow/6A/` / `specs/state-flow/6B/` – `state.6A.s0.expanded.md` … `state.6A.s5.expanded.md`, `state.6B.s0.expanded.md` … `state.6B.s5.expanded.md`.
- `specs/contracts/6A/`, `specs/contracts/6B/` – catalogue updates, schema packs, dataset dictionaries, artefact registries.
- `narrative/` – optional Layer-3 design references, assumptions, performance studies.
- `deprecated__assumptions/` – parking lot for rejected ideas so we keep provenance.

## 3) Notes
- Keep Layer-3 deterministic and isolated: no modifications to upstream specs without routing through the appropriate layer router.
- Specs in this tree are now **authoritative** for Layer-3 implementation; treat them as read-only unless the USER explicitly opens spec work.
