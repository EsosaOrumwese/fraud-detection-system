# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2025-10-14_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live.

---

## 0) Scope (current focus)
- Active build: Data Engine - Layer-1 / Segment **2A** (States S0-S5) — implementation phase just beginning.
- Segments **1A & 1B** are live and sealed; treat their artefacts as read-only authority surfaces for downstream states.
- All other packages/services remain LOCKED; check their nested `AGENTS.md` for status before making changes.
- Need to work in a locked area? Ask the USER with a clear justification before touching it.

---

## 1) Reading order (strict)
Read these in order before modifying code so you share the project context:
1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs/references/closed-world-synthetic-data-engine-with-realism*.md` (current build focus)
3. Review the current implementation of the project which for now involves understanding the implemented data engine (1A-1B) in packages/engine and also its run tests in `runs/`

---

## 2) Project components
- Data Engine — see `packages/engine/AGENTS.md` for the Segment 1B router.
- Everything else is conceptual for now; treat those folders as read-only unless explicitly unlocked.

---

## 3) Test-yourself policy (no prescribed runner)
- Own your test plan — even small regressions can break determinism.
- Default to deterministic runs (`python -m pytest`, targeted CLI smokes) and extend coverage when behaviour changes.
- Record the test plan and results in each PR or working log entry.

---

## 4) Restructuring policy (engine only)
- You may reorganise `packages/engine/**` when it improves clarity or progress.
- If you do, also update the top-level README layout map and add a short migration note (old -> new paths with rationale).

---

## Extra information
- Stay proactive: surface TODOs, challenge suspect contract assumptions, and suggest stronger designs where appropriate.
- Keep changes efficient and reproducible; add concise comments only when they clarify non-obvious intent.
- Keep `pyproject.toml` aligned with any new dependencies you introduce.

---

## Implementation doctrine (binding for every agent)
- **Chase project outcomes, not verbatim spec text.** Specs capture intent; if the implementation path in the doc would violate determinism, performance, or robustness targets, design a compliant alternative and call it out in the logbook before landing changes. Deviations must still honour the published contracts.
- **Engineer for efficiency from day zero.** Profile early, stream large artefacts, and design kernels that cope with the actual data volumes (Segment 1B S1 is your cautionary tale). Aim for multi-minute, not multi-hour, execution envelopes.
- **Design the hand-off surfaces.** Every state must publish the artefacts the next state/segment needs—shape, quality, and location included. No manual copying between Segment 1A and 1B; wire staging steps and manifest updates directly into the orchestration.
- **Control memory usage deliberately.** Prefer chunked/iterator-based flows, deterministic temp directories, and spill-to-disk patterns over loading entire datasets into RAM. Treat OS-level crashes or thrash as regressions.
- **Build for resumability.** Leverage run receipts, `_passed.flag`, and determinism records so the orchestrator can skip completed states, resume at the point of failure, or clearly instruct the operator how to recover.
- **Instrument heavy paths.** Add structured logging around long-running loops and RNG envelopes so operators can observe progress in real time.
- **Protect reproducibility.** Deterministic artefacts must hash identical across seeded runs. Volatile metadata (timestamps, `run_id`, temp paths) should be isolated from comparisons or normalised through tooling.

_This router stays deliberately light on mechanics so it evolves slowly while the project grows._
