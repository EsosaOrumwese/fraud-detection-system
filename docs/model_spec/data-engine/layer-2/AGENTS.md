# Layer-2 Router — Segments 5A & 5B

_As of 2025-11-16_

## Scope
- Layer-2 focuses on Segments **5A** (TBD) and **5B**. No code yet; this is the planning ground.
- Layer-1 artefacts remain read-only authority surfaces; reference them via `../layer-1/...`.

## Reading Order
1. `narrative/` — conceptual briefs that justify 5A/5B.
2. `specs/state-flow/5A/` and `specs/state-flow/5B/` — state-expanded docs (stubbed today).
3. `specs/contracts/5A/` and `specs/contracts/5B/` — schema/dictionary deltas.

## Folders
- `specs/state-flow/5A/` — create `state.5A.s0.expanded.md`, etc., as they materialise.
- `specs/state-flow/5B/` — same pattern for 5B.
- `specs/contracts/5A/`, `specs/contracts/5B/` — catalogue entries, schema anchors, makefiles.
- `narrative/` — shared design references.
- `deprecated__assumptions/` — park any rejected ideas so they stay discoverable.

## Notes
- Keep Layer-2 deterministic and isolated: no modifications to Layer-1 specs without going through the appropriate router.
- Update this document as soon as 5A/5B scopes solidify.
