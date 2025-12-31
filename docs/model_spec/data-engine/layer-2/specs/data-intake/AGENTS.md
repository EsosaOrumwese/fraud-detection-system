# AGENTS.md - Data-Intake Router (Layer-2)
_As of 2025-12-31_

Use this router when authoring, acquiring, or deriving any intake artefacts for Layer-2 segments (5A-5B).

---

## 0) Scope (binding)
- Layer-2 segments: 5A, 5B.
- Focus on specs and guides only. Ignore current engine implementation in `packages/engine`.
- Realism is mandatory. Outputs must match intent (scale, volume, variance), not just pass schema checks.
- Specs are authoritative; updates to guides or contracts must be logged.
- Do not modify engine code here unless the USER explicitly requests it.

---

## 1) Reading order (strict)
1. Repo root `AGENTS.md`
2. Layer-2 intake guides in this folder
3. Layer-2 contracts:
   - `docs/model_spec/data-engine/layer-2/specs/contracts/<SEG>/*`
4. Layer-2 expanded specs (state-flow):
   - `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s#.expanded.md`
   - `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s#.expanded.md`

---

## 2) Execution posture (do not rush)
- Work sequentially in order of appearance in the state-expanded docs.
- If a config depends on another policy/dataset, use the upstream artefact already created.
- Each guide gets full focus until it meets realism intent (not just "barely passing").
- Slogan: no stopping until we're green.
- If a guide lacks realism guardrails, add them before authoring.
- Make decisions autonomously to meet realism intent; do not pause for basic questions. Only stop on contract/spec conflicts, and log the decision trail.
- After reading the expanded specs and contracts for the segment, but before authoring any artefact, list the guides in dependency order (topological order) in `guide_order.txt` (one per segment folder under data-intake).

---

## 3) Intake rules (must follow)
- Path correctness: output paths must match artefact registry + data dictionary.
- Schema anchor exists: any `schema_ref` must resolve to a real anchor.
- No guessing: every placeholder must be resolved per guide; missing required inputs fail closed.
- Determinism and provenance: hash raw bytes unless guide says normalize; record digests and source metadata.
- Partition discipline: use contract tokens (`seed`, `parameter_hash`, `manifest_fingerprint`, `scenario_id`, etc.).
- Realism checks: avoid degenerate outputs; apply guide-specific guardrails.
- Examples are stepping stones only. Never copy/paste them as final output.

---

## 4) Documentation (required)
Two evidence streams:
1) Layer evidence file (one per layer):
   - `docs/model_spec/data-engine/layer-2/specs/data-intake/evidence.md`
2) Daily logbook: `docs/logbook/<YYYY-MM>/<YYYY-MM-DD>.md`
   - Append entries in time order, at local time, as you work (not just at the end).
   - Create the log if missing and keep the format consistent with existing logbooks.
   - Before starting work, verify the evidence file and logbook exist; create them if missing and log that creation.

If a snag occurs, log the snag and attempted resolutions before proceeding.

---

## 5) Replacement protocol (for existing externals)
For each external:
- Locate the current external; deprecate it (e.g., prefix with `deprecated_`), and log the change.
- Materialize the new version to meet realism.
- Record in evidence file:
  - deprecated path (if any)
  - new path
  - how realism checks were satisfied

---

## 6) Conflict handling
- If guide contradicts contracts or expanded specs, stop and ask the USER (or fix the docs if instructed).
- Never ship a policy/config whose semantics are not pinned by the guide.

---

## 7) Outputs
- All artefacts produced here must be listed in the segment's registry/dictionary.
- Any new artefact requires a schema anchor and a dictionary entry.

---

This router is intentionally concise; the guides remain the binding source for details.
