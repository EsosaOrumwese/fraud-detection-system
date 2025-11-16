# AGENTS.md - Data Engine Router (Layer-1 / Segment 3A in progress)
_As of 2025-11-12_

This router tells you what is binding, what to read first, and which parts of the engine are in play. Segments **1A, 1B, 2A, and 2B** are online and sealed—treat them as read-only authority surfaces. We are preparing the PR to land Layer-1 through Segment 2B before moving on to Segment 3A specifications.

---

## 0) Scope (you are here)
- Package: packages/engine
- Current posture: Layer-1 / Segments **1A–2B** are sealed and ready for PR. Next build cycle will open Segment **3A** (pending spec refinement).
- Sealed references: Segments 1A, 1B, 2A, and 2B act as authority surfaces for downstream inputs.
- Binding specs: 2A/2B expanded state documents and contract artefacts remain locked; 3A will stay locked until the spec is green-lit.
- Other segments (3B…4B) remain locked until explicitly opened.

**Environment posture.** We are intentionally deferring integration with the shared dev environment (full artefact replay and manifest hookups) until the **entire Data Engine**—all layers, segments, and states—is built and wired together. While we are still in that build-out phase, every new state must be treated as if the complete engine were already live: wire states together locally, exercise deterministic cross-state invariants, and extend regression tests so the chain remains ready to run end-to-end the moment we connect to real artefacts. No shortcuts.

---

## 1) Reading order (strict)
Read these in order before touching code so you align with the frozen specs.

**A. Conceptual references (repo-wide, non-binding)**
- docs/references/closed-world-enterprise-conceptual-design*.md
- docs/references/closed-world-synthetic-data-engine-with-realism*.md

**B. Already implemented data engine as well as context**
- Review the current implementation of the project which for now involves understanding the implemented data engine in packages/engine and also its run tests in `runs/`
- Ensure to read (strict) else you'll mess the whole project up:
   - docs/model_spec/data-engine/layer-1/specs/state-flow/1A/s#*.expanded.md (S0-S9)
   - docs/model_spec/data-engine/layer-1/specs/state-flow/1B/s#*.expanded.md (S0-S9)

**C. Segment 2A state design (binding; ready for impl)**
- docs/model_spec/data-engine/layer-1/specs/state-flow/2A/s#*.expanded.md (S0-S5)

**D. Contract specs (blueprints for contracts/)**
- docs/model_spec/data-engine/layer-1/specs/contracts/2A/artefact_registry_2A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/2A/dataset_dictionary.layer1.2A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/2A/schemas.2A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml

**E. Segment 3A state design (binding; in progress)**
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/s#*.expanded.md (S0–Sx)
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/* (artefact registry, dataset dictionary, schemas)

> Never promote narratives, previews, or samples to binding authority. Only the expanded specs and contract documents govern code.

---

## 2) Test-yourself policy
- Run targeted pytest jobs (python -m pytest ...) for the state you modify.
- When adding RNG or egress logic, layer in regression cases that exercise both happy-path and gate-fail scenarios (mirror the Segment 1A test harness).
- Document results when handing work off (logbook or PR notes).

---

## 3) Ignore list (keep these read-only)
- docs/**/overview/**
- Anything explicitly marked deprecated or combined
- ~~Segment 1A code paths unless a migration is authorised~~


---

## House style (soft guidance)
- Prefer clarity and determinism over cleverness.
- Preserve the L0/L1/L2/L3 separation inside each state package.
- Surface TODOs or questions when the spec leaves gaps; do not improvise contracts.
- Keep logging informative—mirror the Segment 1A CLI/orchestrator patterns so smoke tests stay readable.

---

## Implementation guardrails (must follow)
- **Specs state intent; code must deliver outcomes.** If the literal steps in a spec would break determinism, efficiency, or memory posture, design the implementation that hits the stated end-goal instead and document the rationale in the logbook. Contracts and public artefacts still govern what you emit.
- **Performance first.** Treat every state like a production data job: profile, stream, and vectorise. Target sub-15 minute executions for the heavy kernels by default, and justify any regression.
- **No more manual hand-offs.** Ensure prior segment staging covers every reference that next segment consumes. Within the next segment, publish receipts, manifests, and dataset dictionaries so dependent states locate what they need without operator intervention.
- **Memory-aware by design.** Use chunked IO, deterministic spill directories, and bounded concurrency to keep RSS under control. Loading entire rasters or catalogues into RAM without back-pressure is considered a bug.
- **Resumable orchestration.** The orchestrator must be able to read existing `_passed.flag` artefacts, receipts, and RNG logs to resume from the point of failure (or clearly instruct the operator when manual repair is required) instead of rerunning the entire stateflow from scratch.
- **Operational visibility.** Instrument long-running steps with structured logging (progress counts, ETA-style checkpoints, RNG envelopes) so smoke tests and production monitors never look “stuck”.
- **Deterministic artefacts only.** All seeded outputs (parquet partitions, manifests, contract bundles) must hash identically across reruns. Any volatile metadata (timestamps, `run_id`, temp paths, live telemetry) should be isolated from validation surfaces or normalised by tooling.

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._

