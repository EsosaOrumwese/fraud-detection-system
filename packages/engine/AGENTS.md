# AGENTS.md - Data Engine Router (Specs sealed; implementation next)
_As of 2026-01-23_

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

## Run isolation + external roots (authoritative)
- A run is logically isolated: all writes go to runs/<run_id>/... (data/logs/tmp/cache).
- Inputs may be read from shared roots and are not “missing” if present there.
- Resolution order: run-local staged → shared external roots → error.
- S0 must record all external inputs in sealed_inputs_* (path + hash).
- Default: do NOT copy large immutable datasets (e.g., hrsl_raster).
- Optional: staged/hermetic mode copies small/medium inputs into runs/<run_id>/reference/.


---

## Implementation map discipline (mandatory, detail-first)
- For every segment/state you touch, you MUST append entries to
  `docs/model_spec/data-engine/implementation_maps/segment_{SEG}.impl_actual.md`.
- Each entry MUST be detailed and auditable. A 1-2 line summary is allowed, but
  the plan itself must be explicit and stepwise. No vague "we will implement"
  phrasing and no skipped rationale.
- The implementation map is a running **brainstorming notebook**. As you reason
  through a state, capture the full thought process (assumptions, alternatives,
  decision criteria, edge cases, and intended mechanics). Do this **during** the
  design, not just before/after. The goal is to make the entire reasoning trail
  reviewable later, not a minimal recap.
- This is NOT a two-time update doc. Append entries repeatedly while you are
  actively thinking and deciding. If you explore multiple approaches or adjust
  your plan mid-stream, record each thread as it happens so the reader can see
  the full evolution of the decision process.
- The plan MUST include: exact inputs/authorities, file paths, algorithm or
  data-flow choices, invariants to enforce, logging points, resumability hooks,
  performance considerations, and validation/testing steps.
- Before implementing any change, append a detailed plan entry that captures
  your full thought process: the problem, alternatives considered, the decision
  and why, and the exact steps you intend to take. Do this *before* coding so
  the record reflects the real decision path (not a retrospective summary).
- For every decision or review during implementation (no matter how small),
  append another entry describing the reasoning and the outcome. If you realize
  a missing decision later, append a corrective entry rather than rewriting
  history.
- If you are about to implement a change and the in-progress reasoning is not
  captured yet, stop and append a new entry first. The map must mirror the live
  design process, not a reconstructed summary.
- If a plan changes, append a new entry describing the change and why. Never
  delete or rewrite prior entries.
- Before implementing a state, read ALL expanded docs for that segment/state
  and note the files read in the logbook (time-stamped).
- Log every decision and action as it happens in `docs/logbook` with local time.
  The logbook must reference the matching implementation-map entry (or note
  that one was added).
- If you are unsure, stop and add a detailed plan entry first, then proceed.

## Execution logging requirements (engine)
- Use loggers in every process; include a heartbeat plus narrative state-aware logs.
- Log lines must be narrative and state-aware: whenever you log counts/progress,
  include what the count represents, the gate defining scope, and the stage/output.
- Emit a short story header log per state (objective, gated inputs, outputs).
- For long-running loops, include elapsed time, processed/total, rate, ETA using
  monotonic time and a predictable cadence.
- Logging must obey a performance budget: required audit signals stay on, but
  high-cardinality/per-record logs are opt-in and disabled by default.

## Implementation records + hygiene (engine)
- Keep `pyproject.toml` aligned with new dependencies.
- Ensure truly large files are tracked in Git LFS.
- Update the Makefile as workflows evolve (human-readable; no reverse-engineer constraints).
- Before implementation, declare the contract source (model_spec for dev; root-ready switch later).
- Do not use placeholders; locate externals via artefact registry/data dictionary.

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
- **Narrative log context.** Any log line that reports counts/progress must explain what the count represents, the gating criteria that define the scope, and the stage/output being produced so operators can follow the state flow.
- **Deterministic artefacts only.** All seeded outputs (parquet partitions, manifests, contract bundles) must hash identically across reruns. Any volatile metadata (timestamps, `run_id`, temp paths, live telemetry) should be isolated from validation surfaces or normalised by tooling.
- **Lightweight RNG observability by default.** Per-event RNG logs are opt-in for dev runs (use `ENGINE_5B_S{2,3,4}_RNG_EVENTS=1` or future layer-3 equivalents when a deep audit is needed). Default posture is `rng_trace_log` + run reports + deterministic outputs. Apply this same mindset for 5B + layer-3 states unless explicitly overridden.

## Remediation sequencing law (engine, binding)
- **Pre-remediation performance design is mandatory:** before code changes, document baseline runtime, target runtime budget, expected complexity, chosen data structures/search/join strategy, IO plan, and rejected alternatives with rationale.
- **Performance triage before quality tuning:** before remediating statistical behavior for any state/segment, first assess and optimize runtime path efficiency (algorithm/data-structure/index/join/IO strategy) to practical minute-scale execution.
- **No wait-it-out remediation:** running known-slow code repeatedly to chase statistical score is prohibited when bottlenecks are unresolved.
- **Single-process efficiency baseline first:** implementations must achieve strong performance without requiring parallel workers. Parallelism is optional and must remain memory-safe and user-approved.
- **State runtime budgets are mandatory:** each remediation phase must define per-state budget, measure elapsed time, and record evidence in implementation notes/logbook.
- **Performance gate blocks phase progression:** do not advance remediation phases unless measured elapsed evidence shows improvement against baseline and movement toward (or achievement of) the state runtime budget.
- **Fail-closed on stalls/regressions:** if a state stalls or materially exceeds budget, stop feature/statistical tuning and do bottleneck closure first (external tool latency, hot loops, IO amplification, memory pressure, path resolution).
- **Correctness + determinism remain mandatory:** optimization is valid only if contracts pass, outputs remain deterministic, and statistical realism does not regress.
- **Definition of done requires both:** a remediation step is only done when it meets quality thresholds and runtime budget (or has explicit USER waiver recorded).

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._
