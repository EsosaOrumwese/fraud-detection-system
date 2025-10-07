# AGENTS.md — Data Engine Router (Layer-1 / Segment 1A / States S0–S4)
_As of 2025-10-06_

This file is a **router**, not a design doc. It tells you what to read (in what order), what is binding vs non-binding, where you may work **now**, and how to treat tests and structure. No specific commands are prescribed here.

---

## 0) Scope (you are here)
- You are in the **Data Engine**.
- Current implementation focus: Layer-1 → Segment 1A → States S0–S4. (note this does not refer to the folder in the repo but to the conceptual breakdown of the engine into layers, subsegments and states). You are free to work/update whereever, as long as it's inline with the design goal.
- Other engine segments (1B…4B) are **read-only for context**.
- Note: "XX" here refers to the subsegment within 1A-4B. As we updated the contractual docs, more state-flow files will be added

---

## 1) Reading order (strict)
Read in this exact order before making changes in this package:

### A) Conceptual references (non-binding; repo-wide end-goal)
- `docs/references/closed-world-enterprise-conceptual-design*.md`
- `docs/references/closed-world-synthetic-data-engine-with-realism*.md`

### B) Layer-1 narratives (non-binding; orientation)
- `docs/model_spec/data-engine/narrative/`  
  Explains L1 segmentation (1A–4B). Treat as context only.

### C) State design & implementations for **Segment XX** (where expanded docs live)
- `docs/model_spec/data-engine/specs/state-flow/XX/`
  - `overview*.md` → **conceptual** (non-binding; orientation)
  - `s0*expanded*.md`, `s1*expanded*.md`, … → **expanded state docs** for S0–S4 (documentation/spec)
  - Pseudocode sets for L0/L1/L2/L3 are **co-located** in this XX area (clearly named files or subfolders).  
    Use these as the implementation guide.

### D) Data-intake specs (per sub-segment; **structure & intent**)
- `docs/model_spec/data-engine/specs/data-intake/XX/`
  - `preview/*.md` → **Preview**: examples/illustrations of the **intended ingested data shape** derived from the state docs. Also try to infer the dataset's magnitude as well in order to design efficient systems
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


> Do **not** promote narratives, overviews, previews, conceptual flow notes, or sample CSV/JSON to binding authority.

---

## 2) Test-yourself policy (no prescribed runner)
- As stated at the repo AGENTS.md, always always test yourself. The L3 pseudocode file tries to lay out some validation requirements however, you're not limited to that.

---

## 3) Ignore list (to prevent “helpful” but wrong edits)
- Any `docs/**/overview/**` (orientation only)  
- Deprecated/combined docs explicitly marked as obsolete

---

## 4) If you only read five things for 1A
1. The **expanded** doc for the active subsegment and state under `docs/model_spec/data-engine/specs/state-flow/` acts as your technical documentation which must be obeyed
2. The **pseudocode** (L0/L1/L2/L3) for that state in the same subsegment, acts as a bundle (each depending on the other) which guides best implementation although you can improve on it as you like but must be inline with the technical documentation
3. The **contract-spec** for that state under `docs/model_spec/data-engine/specs/contracts/`  
4. The **data-intake** `preview/*.md` and `data/*.md` notes under `docs/model_spec/data-engine/specs/data-intake/` for each subsegment give an illustration of what the engine expects at injestion and a guide (not binding) for each pipeline on how to collect data, refine it and get it ready for injestion.

---

## House style (soft guidance — optional)
- I leave it to you to work with your best practices as a pro MLOPs Engineer and Software Engineer when dealing with this project. 


_This router is command-free by design. Execution strategy, test harness, and internal folder improvements inside the engine are up to you—so long as you respect precedence, determinism, and validation gates._
