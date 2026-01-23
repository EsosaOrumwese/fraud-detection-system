# Layer-2 Router - Segments 5A & 5B

_As of 2025-11-25_

## Scope
- Layer-2 focuses on Segments **5A** and **5B**. Specs (state-flow + contracts) are **sealed**; no implementation code here yet.
- Layer-1 artefacts remain read-only authority surfaces; reference them via `../layer-1/...`.

## Reading Order
1. `narrative/` - conceptual briefs that justify 5A/5B.
2. `specs/state-flow/5A/` and `specs/state-flow/5B/` - fully expanded state docs (S0–S5).
3. `specs/contracts/5A/` and `specs/contracts/5B/` - schema packs, dataset dictionaries, artefact registries.

## Folders
- `specs/state-flow/5A/` - `state.5A.s0.expanded.md` … `state.5A.s5.expanded.md` (arrival surfaces).
- `specs/state-flow/5B/` - `state.5B.s0.expanded.md` … `state.5B.s5.expanded.md` (arrival realisation).
- `specs/contracts/5A/`, `specs/contracts/5B/` - catalogue entries, schema anchors, makefiles.
- `narrative/` - shared design references.
- `deprecated__assumptions/` - park any rejected ideas so they stay discoverable.

## Notes
- Keep Layer-2 deterministic and isolated: no modifications to Layer-1 specs without going through the appropriate router.
- Specs in this tree are now **authoritative** for implementation in `packages/engine` and downstream services; treat them as read-only unless the USER explicitly opens spec work.
