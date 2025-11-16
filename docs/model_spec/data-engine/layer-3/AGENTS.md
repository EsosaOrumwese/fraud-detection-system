# Layer-3 Router – Segments TBD

_As of 2025-11-16_

Layer-3 has not been opened yet; this document reserves the structure so we can spin up the next set of segments the moment Layer-2 is sealed. Treat everything here as a template.

## 0) Scope
- Layer-3 will inherit Layer-1/Layer-2 artefacts as read-only authority surfaces (reference them via `../layer-1/...` and `../layer-2/...`).
- Segments are TBD (likely **6A/6B** once Layer-2 stabilises). Until we bless the scope, **no code** or spec work lives here.

## 1) Reading Order (once unlocked)
1. `narrative/` – conceptual briefs and design memos for the new segments.
2. `specs/state-flow/<segment>/` – state-expanded docs (S0…SX) for each unlocked segment.
3. `specs/contracts/<segment>/` – schema anchors, dataset dictionaries, artefact registries.

## 2) Folder expectations
- `specs/state-flow/<segment>/` – create `state.<segment>.s0.expanded.md`, etc., mirroring Layer-1/Layer-2 conventions.
- `specs/contracts/<segment>/` – catalogue updates, schema packs, Makefile snippets.
- `narrative/` – shared design references, assumptions, performance studies.
- `deprecated__assumptions/` – parking lot for rejected ideas so we keep provenance.

## 3) Notes
- Keep Layer-3 deterministic and isolated: no modifications to upstream specs without routing through the appropriate layer router.
- Update this file as soon as Layer-3 scope is declared (segments, target artefacts, timelines). Until then, this folder is intentionally empty.
