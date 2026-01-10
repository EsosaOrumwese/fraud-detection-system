# AGENTS.md - Data Engine Router (Specs sealed; implementation next)
_As of 2025-12-31_

This router tells you what is binding, what to read first, and which parts of the engine are in play. All technical specifications for all segments, 1A to 6B are ready. **Ensure you have read the repo's root AGENTS.md**.

---

## 0) Scope (you are here)
- Package: `packages\engine`
- Specs: `docs\model_spec\data-engine`
- Spec posture: Specs are authoritative for 1A-6B. Layer-1/2/3 (1A-6B) are spec-ready and actively being built with data-intake support. Most of these data/configs/policies have already been materialized in the repo, if none exists, inform the USER
- Binding specs: Contracts and expanded docs for 1A-6B govern code. There are no "locked" areas; focus is driven by the current job plan.
- Implementation note: current engine code is provisional (placeholder-driven) and will be refactored as real externals land; treat specs as the source of truth.

---

## 1) Reading order (strict)
Read these in order before touching code so you align with the frozen specs. Note the USER will tell you what segment to focus on. You must ensure that the state expanded docs and contracts for that segment never leave your mind. You never implement without consulting that source of truth.

**A. Layer-1 implementation references (Segments 1A-3B)**
- Review the current implementation of the project which for now involves understanding the implemented data engine in packages/engine and also its run tests in `runs/`.
- Read in order; do not skip:
   - docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/1A/*
   - docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/1B/*
   - docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/2A/*
   - docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/2B/*
   - docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/3A/*
   - docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s#.expanded.md
      * docs/model_spec/data-engine/layer-1/specs/contracts/3B/*

**B. Layer-2 state design (5A/5B specs)**
- docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s#.expanded.md
      * docs/model_spec/data-engine/layer-2/specs/contracts/5A/*
- docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s#.expanded.md
      * docs/model_spec/data-engine/layer-2/specs/contracts/5B/*

**C. Layer-3 state design (6A/6B specs)**
- docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s#.expanded.md
      * docs/model_spec/data-engine/layer-3/specs/contracts/6A/*
- docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s#.expanded.md
      * docs/model_spec/data-engine/layer-3/specs/contracts/6B/*


> Never promote narratives, previews, or samples to binding authority. Only the expanded specs and contract documents govern code.

---

## 2) Test-yourself policy
- Always, always test yourself robustly.

---

## 3) Ignore list (keep these read-only)
- docs/**/overview/**
- Anything explicitly marked deprecated or combined

---

## House style (soft guidance)
- Prefer clarity and determinism over cleverness.
- Surface TODOs or questions when the spec leaves gaps; do not improvise contracts.
- Keep logging informative—mirror the Segment 1A CLI/orchestrator patterns so smoke tests stay readable.

---

## Implementation guardrails (must follow)
- **Specs state intent; code must deliver outcomes.** If the literal steps in a spec would break determinism, efficiency, or memory posture, design the implementation that hits the stated end-goal instead and document the rationale in the logbook. Contracts and public artefacts still govern what you emit.
- **Performance first.** Treat every state like a production data job: profile, stream, and vectorise. Target sub-15 minute executions for the heavy kernels by default, and justify any regression.
- **No more manual hand-offs.** Ensure prior segment staging covers every reference that next segment consumes. Within the next segment, publish receipts, manifests, and dataset dictionaries so dependent states locate what they need without operator intervention.
- **Run-scoped artefacts live in the run tree.** If an artefact depends on a run manifest fingerprint, it must be emitted under the run root (and its dictionary/registry entry must point there). Do not write run-scoped outputs into the repo root and do not require manual copies into runs/.
- **Output layout must be coherent.** Keep run outputs grouped by layer/segment/state and sealed with receipts; avoid scattering artefacts across unrelated folders. If the spec’s paths are ambiguous, resolve them by contract registry and document the decision in the logbook.
- **Memory-aware by design.** Use chunked IO, deterministic spill directories, and bounded concurrency to keep RSS under control. Loading entire rasters or catalogues into RAM without back-pressure is considered a bug.
- **Resumable orchestration.** The orchestrator must be able to read existing `_passed.flag` artefacts, receipts, and RNG logs to resume from the point of failure (or clearly instruct the operator when manual repair is required) instead of rerunning the entire stateflow from scratch.
- **Operational visibility.** Instrument long-running steps with structured logging (progress counts, ETA-style checkpoints, RNG envelopes) so smoke tests and production monitors never look "stuck".
- **Deterministic artefacts only.** All seeded outputs (parquet partitions, manifests, contract bundles) must hash identically across reruns. Any volatile metadata (timestamps, `run_id`, temp paths, live telemetry) should be isolated from validation surfaces or normalised by tooling.

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._
