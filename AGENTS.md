# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2025-10-14_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live.

---

## 0) Scope (current focus)
- Active build: Data Engine - Layer-1 / Segment 1B executing States S0-S9.
- Segment 1A (States S0-S9) remains sealed; use its artefacts as read-only authority surfaces.
- All other packages/services remain LOCKED; check their nested `AGENTS.md` for status before making changes.
- Need to work in a locked area? Ask the USER with a clear justification before touching it.

---

## 1) Reading order (strict)
Read these in order before modifying code so you share the project context:
1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs/references/closed-world-synthetic-data-engine-with-realism*.md` (current build focus)

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
- Segment 1B has full expanded specs for States S0-S9 and updated contract artefacts (`docs/model_spec/data-engine/specs/state-flow/1B/**`, `docs/model_spec/data-engine/specs/contracts/1B/**`). There is intentionally no dataset preview for 1B—derive data expectations directly from the design.
- For prior sealed work (Segment 1A) there are still no L0/L1/L2/L3 pseudocode docs; infer the layer split from the expanded specs (L0 primitives/helpers, L1 kernels, L2 orchestrator, L3 validator).
- Stay proactive: surface TODOs, challenge suspect contract assumptions, and suggest stronger designs where appropriate.
- Keep changes efficient and reproducible; add concise comments only when they clarify non-obvious intent.
- Keep `pyproject.toml` aligned with any new dependencies you introduce.

_This router stays deliberately light on mechanics so it evolves slowly while the project grows._
