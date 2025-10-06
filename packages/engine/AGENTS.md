# AGENTS.md — Data Engine Router (Layer-1 / Segment 1A / States S0–S4)
_As of 2025-10-06_

This file is a **router**, not a design doc. It tells you what to read (in what order), what is binding vs non-binding, where you may work **now**, and how to treat tests and structure. No specific commands are prescribed here.

---

## 0) Scope (you are here)
- You are in the **Data Engine**.
- Current implementation focus: **Layer-1 → Segment 1A → States S0–S4**.
- Other engine segments (1B…4B) are **read-only for context**.

---

## 1) Reading order (strict)
Read in this exact order before making changes in this package:

### A) Conceptual references (non-binding; repo-wide end-goal)
- `docs/references/closed-world-enterprise-conceptual-design*.md`
- `docs/references/closed-world-synthetic-data-engine-with-realism*.md`

### B) Layer-1 narratives (non-binding; orientation)
- `docs/model_spec/data-engine/narrative/`  
  Explains L1 segmentation (1A–4B). Treat as context only.

### C) State design & implementations for **Segment 1A** (where expanded docs live)
- `docs/model_spec/data-engine/specs/state-flow/1A/`
  - `overview*.md` → **conceptual** (non-binding; orientation)
  - `s0*expanded*.md`, `s1*expanded*.md`, … → **expanded state docs** for S0–S4 (documentation/spec)
  - Pseudocode sets for L0/L1/L2/L3 are **co-located** in this 1A area (clearly named files or subfolders).  
    Use these as the implementation guide.

### D) Data-intake specs (per sub-segment; **structure & intent**)
- `docs/model_spec/data-engine/specs/data-intake/1A/`
  - `preview/*.md` → **Preview**: examples/illustrations of the **intended ingested data shape** derived from the state docs.  
    *These are orientation, not contracts. Do **not** treat preview Markdown—or any sample CSV/JSON—as binding.*
  - `data/*.md` → **Conceptual flow**: how the **ingestion pipeline** should move from **raw → pre-processed** (sources, scraping/collection approaches, normalization, preprocessing).  
    *This is a plan for how we expect to ingest; it is **guiding**, not binding.*
- Global rule for Data Intake:
  - **Read** the Markdown in `preview/` and `data/` to understand **what** should be ingested and **how** we intend to flow it.
  - **Ignore** any `.csv` / `.json` sample files (exploratory scaffolds, non-authoritative).

### E) Contract-specs (blueprint for root `contracts/`)
- `docs/model_spec/data-engine/specs/contracts/`  
  Per sub-segment/state articulation of **what the contracts should be** (schemas, dataset dictionary entries, policies).  
  Use these to author or update `contracts/**` at the repo root.

### F) Binding contracts (materialized)
- `contracts/**` (schemas, dataset dictionary, policies).  
  **Status:** `contracts/` is **UNLOCKED** and **in-progress**; materialize/adjust it to match the **contract-specs** in **E**.

---

## 2) Authority & precedence
When sources disagree, follow this order:

1. **Binding contracts** once materialized under `contracts/**`
2. **Pseudocode sets (L0/L1/L2/L3)** for S0–S4 in `docs/model_spec/data-engine/specs/state-flow/1A/`
3. **Expanded state docs** in the same 1A area
4. **Data-intake Markdown** (`preview/*.md` + `data/*.md`) — **guiding** (inputs shape & conceptual flow); samples are non-authoritative
5. **Narratives & conceptual references** — context only

> Do **not** promote narratives, overviews, previews, conceptual flow notes, or sample CSV/JSON to binding authority.

---

## 3) Implementation loop (per state, S0→S4)
1. **Read:** 1A **expanded** doc for the state → its **pseudocode** set.  
2. **Align contracts:** read the corresponding **contract-spec** in `docs/model_spec/data-engine/specs/contracts/`; if needed, author/update the real files under `contracts/**` (schemas, dataset dictionary, policies).  
3. **Consult Data Intake (1A):** use `preview/*.md` to shape expectations for ingested data and `data/*.md` to understand the raw→pre-processed flow.  
   - Use these to choose fixtures and pipeline structure, but remember they’re **guiding**, not binding.
4. **Implement:**  
   - **L0/L1** must be **pure** (no I/O, deterministic).  
   - **L2** performs I/O, writes outputs, and embeds `{ seed, parameter_hash, manifest_fingerprint }`.  
   - **L3** performs schema + corridor validation; **no PASS → no read** downstream.  
5. **Self-test:** create your own tests/fixtures (see §4). Iterate until green.  
6. **Document:** in your PR, reference the exact contract-spec + expanded/pseudocode + intake preview/flow notes you implemented against.

---

## 4) Test-yourself policy (no prescribed runner)
Every change (contracts or engine) must include **self-tests** derived from the spec’s **goal**:

- **Positive fixtures** that pass when the goal is met.  
- **Negative fixtures** that fail for the right reason.  
- **Security/robustness** checks where specs or policies imply them.  
- Keep execution **deterministic** given `{ seed, parameter_hash, manifest_fingerprint }`.  
- Record a brief **test plan** and outcomes in the PR.

> You choose how to execute tests; this repo intentionally does **not** prescribe commands here.

---

## 5) Restructuring policy (engine-only autonomy)
- ✅ You may reorganize **this engine package** to improve clarity and progress.  
  If you do:
  - Update any paths referenced in this `AGENTS.md` and in engine docs you link.  
  - Add a brief **migration note** (old → new paths, rationale).  
  - Preserve or improve **determinism**, **validation gates**, and the locations of **binding contract** files (which live at repo root under `contracts/**`).  
- ❌ Do **not** move/rename `contracts/**` without updating all references and documenting the migration.  
- ❌ Do **not** touch locked code areas outside the engine.

---

## 6) What is unlocked vs locked (engine view)
- ✅ **Unlocked (implementation):** this engine package for **L1 / 1A / S0–S4**.  
- 🛈 **Docs (read-only intent):** `docs/**` (you may add clarifying notes; do not change intent without discussion).  
- 🚫 **Locked code outside engine:** see nested `AGENTS.md` in those folders; they point back here.

---

## 7) Ignore list (to prevent “helpful” but wrong edits)
- `docs/model_spec/data-engine/specs/data-intake/**/*.csv`  
- `docs/model_spec/data-engine/specs/data-intake/**/*.json`  
- Any `docs/**/overview/**` (orientation only)  
- Deprecated/combined docs explicitly marked as obsolete

---

## 8) If you only read five things for 1A
1. The **expanded** doc for the active state under `docs/model_spec/data-engine/specs/state-flow/1A/`  
2. The **pseudocode** (L0/L1/L2/L3) for that state in the same 1A area  
3. The **contract-spec** for that state under `docs/model_spec/data-engine/specs/contracts/`  
4. The **data-intake** `preview/*.md` and `data/*.md` notes under `docs/model_spec/data-engine/specs/data-intake/1A/`  
5. The corresponding **materialized contract** file(s) under `contracts/**`

## House style (soft guidance — optional)
- Keep the per-state folder `sX/` with tier dirs `{l0,l1,l2,l3}`; tiers are the only hard boundary.
- L0 — pure helpers: small modules by topic (e.g., `l0/helpers_geo.py`). No I/O. Dataclasses OK if immutable.
- L1 — kernels composing L0 (e.g., `l1/kernels_rank.py`). Still pure; no file/network access.
- L2 — orchestration & I/O: e.g., `l2/orchestrate.py`, `l2/io.py`. Writes outputs and embeds `{seed, parameter_hash, manifest_fingerprint}`.
- L3 — validators: e.g., `l3/schema.py`, `l3/corridor.py` (no business logic here).
- Shared types/constants for the state live at `sX/types.py` and `sX/constants.py` (import-only, no side effects).
- Prefer modules < ~400–500 LOC; split when larger. Re-export a stable surface via `__init__.py` in each tier.
- MAY separate “models” (dataclasses/TypedDicts) and “helpers” (pure functions) into different files if it improves clarity.


_This router is command-free by design. Execution strategy, test harness, and internal folder improvements inside the engine are up to you—so long as you respect precedence, determinism, and validation gates._
