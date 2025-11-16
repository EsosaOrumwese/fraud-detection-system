# AGENTS.md — Contract Specs Router

- Layer-wide authorities live here:
  - `schemas.ingress.layer1.yaml` — sealed ingress surfaces shared by all states.
  - `schemas.layer1.yaml` — layer RNG envelopes & shared schema defs.
- State-specific packs are under subfolders (e.g. `1A/`, `1B/`) alongside their dataset dictionaries and artefact registries. Reference the matching state-flow doc before editing.
- Do not alter schema/dictionary entries unless the USER approves spec work. When unlocked, update state-flow docs in sync with any contract change.
- Leave deprecated folders (`data-intake/`, `pseudocode-set/`) alone.
