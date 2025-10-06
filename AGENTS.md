# AGENTS.md — Router for the Closed-World Enterprise Fraud System
_As of 2025-10-06_

This file is a **router**, not a design doc. It tells you what to read first, what is binding vs non-binding, where you’re allowed to work **now**, and how to treat tests and structure. Do **not** infer authority from prose that isn’t marked binding.

---

## 0) Scope (current focus)
- Work only on the **Data Engine**: **Layer-1 → Segment 1A → States S0–S4**.
- Other services/packages (apart from contracts) exist but are **LOCKED** for code changes (see their nested `AGENTS.md`).
- NOTE: If need be and you need to access a locked section/folder, let the USER know so the USER can UNLOCK it for you to go ahead. State your reason and the USER will it grant or deny you permission to unlock it.
---

## 1) Reading order (strict)
Read in this exact order before changing anything:

### A) Conceptual references (non-binding; repo-wide end-goal)
1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs/references/closed-world-synthetic-data-engine-with-realism*.md`

> These two give the “whole picture” so you don’t crawl the entire repo to guess intent.

### B) Engine narratives (non-binding; Layer-1 landscape)
- `docs/model_spec/data-engine/narrative/`
  - Explains how Layer-1 is segmented (1A–4B). 4A/4B cross-cut; treat this as orientation only.

### C) Engine state design & implementations (where expanded docs live)
- `docs/model_spec/data-engine/specs/state-flow/`
  - **Within the relevant sub-segment for 1A**, you will find:
    - `overview*.md` → **conceptual** (non-binding; orientation)
    - `s0*expanded*.md`, `s1*expanded*.md`, … → **expanded state docs** (documentation/spec for S0–S4)
    - Pseudocode sets for L0/L1/L2/L3 are **co-located in this area** (either as clearly named files or subfolders). Use these as the implementation guide.

> If file names vary, pick the 1A set by its prefix in the same `state-flow/` area.

### D) Data-intake specs (per-state ingestion; read Markdown only)
- `docs/model_spec/data-engine/specs/data-intake/`
  - **Read only** the Markdown specs here.
  - **Ignore** any `.csv` / `.json` samples — they are exploratory/test scaffolds.

### E) Contract-specs → used to materialize root `contracts/`
- `docs/model_spec/data-engine/specs/contracts/`
  - Per sub-segment/state: **what the contracts should be** (schemas, dataset dictionary entries, policies). Use these to author or update `contracts/**`.

### F) Contracts (binding when materialized)
- `contracts/**` (schemas, dataset dictionary, policies).
  - **Status:** `contracts/` is **UNLOCKED** and **in-progress**. Implement/adjust it by following the contract-specs in **E** above.

### G) Implementation area (the only place to write code now)
- `packages/engine/**` (Layer-1 / seg-1A / S0–S4 only)

---

## 2) Authority & precedence
When sources disagree, follow this order:

1. **Binding policy & contracts** once materialized under `contracts/**`
2. **Pseudocode sets (L0–L3)** for S0–S4 (in `docs/model_spec/data-engine/specs/state-flow/`)
3. **Expanded state docs** (same area as pseudocode)
4. **Data-intake Markdown specs** (guiding for inputs; samples are non-authoritative)
5. **Narratives & conceptual references** (context only)

> Do **not** promote narratives/overviews/samples to binding authority.

---

## 3) Contracts workflow (while S0–S4 are in flight)
- Treat `docs/model_spec/data-engine/specs/contracts/` as the **intent** for contracts.
- When a schema / dataset dictionary / policy is needed or must change:
  1. Read the relevant **contract-spec** (and the matching state’s expanded + pseudocode).
  2. Propose concrete edits in `contracts/` that realize that spec.
  3. Cross-reference the exact contract-spec section you followed.
  4. Add/adjust **fixtures and tests** so validation reflects the new contract.

**Binding vs guiding (contracts edition):**
- **Binding:** Anything under `contracts/**` once authored/updated.
- **Guiding:** The contract-specs in `docs/model_spec/data-engine/specs/contracts/**` until materialized.

---

## 4) Test-yourself policy (no prescribed runner)
- Every change (contracts or engine) must include **self-tests** derived from the spec’s **goal**:
  - **Positive fixtures** that pass when the goal is met.
  - **Negative fixtures** that fail for the right reason.
  - **Security/robustness checks** when implied by specs or policies.
- Execution details (how to run tests) are up to you; keep runs **deterministic** given  
  `{ seed, parameter_hash, manifest_fingerprint }`.
- Document the **test plan** and outcomes in your PR.

---

## 5) Restructuring policy (engine only)
- ✅ You may reorganize **`packages/engine/**`** to improve clarity and progress.
- If you do:
  - Update any paths referenced in this `AGENTS.md` and in engine docs.
  - Include a brief **migration note** (old → new paths, rationale).
  - Preserve or improve **determinism**, **validation gates**, and **binding contract locations**.
- ❌ Do **not** move/rename `contracts/**` without updating all references and explaining the migration.
- ❌ Do **not** edit code in locked areas.

---

## 6) Locked vs unlocked map (high-level)
- ✅ **Unlocked now:** `packages/engine/**` (Layer-1 / seg-1A / S0–S4), `contracts/**` (to realize specs)
- 🛈 **Docs (read-only):** `docs/**` (you may add clarifying notes; do not change intent without discussion)
- 🚫 **Locked code areas:** `services/**`, `orchestration/**`, `infra/**`  
  (Each has a nested `AGENTS.md` that says **LOCKED** and points back here.)

---

## 7) Ignore list (avoid “helpful” but wrong edits)
- `docs/model_spec/data-engine/specs/data-intake/**/*.csv`
- `docs/model_spec/data-engine/specs/data-intake/**/*.json`
- Any `docs/**/overview/**` (orientation only)
- Any deprecated/combined docs explicitly marked as obsolete

---

## 8) Fast path (if you only read five things)
1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs/references/closed-world-synthetic-data-engine-with-realism*.md`
3. The **expanded** doc(s) for the active state (S0–S4) under `docs/model_spec/data-engine/specs/state-flow/`
4. The **pseudocode** set for that state (L0/L1/L2/L3) in the same area
5. The **contract-spec** for that state, then materialize/adjust `contracts/**` accordingly

_This file is intentionally light on mechanics and heavy on routing, so it won’t drift as the project grows._
