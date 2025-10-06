# AGENTS.md — Contracts (Canonical Authority)
_As of 2025-10-06_

This folder is the **canonical, enterprise-wide authority** for contracts once files are materialized.  
Contracts here are consumed by the Data Engine now and by other services later.

**Contracts include:**
- JSON Schemas (structure & types)
- Dataset Dictionary (dataset IDs, partitions, lineage fields, retention, licensing)
- Policy bundles (numeric corridors, bounds, priors, etc.)

> **Design source:** The intended shapes live in **docs** under  
> `docs/model_spec/data-engine/specs/contracts/` (per sub-segment/state contract-specs).  
> Use those specs to author/update files in this folder. You are free to group and arrange the folders as you like but ensure that each folder is still inline with the contracts started in `docs/model_spec/data-engine/specs/contracts/<subsegment>/...`

---

## Status
- **UNLOCKED** and **in-progress** for Layer-1 → Segment **1A** → States **S0–S4**.
- This folder may be **empty or partial** until specs are implemented here.

---

## Reading order (for any change)
1. Read the relevant **contract-spec** under  
   `docs/model_spec/data-engine/specs/contracts/<subsegment>/...`
2. Read the matching state’s **expanded** + **pseudocode** docs under  
   `docs/model_spec/data-engine/specs/state-flow/<subsegment>/`
3. Materialize or adjust **this folder** accordingly (schemas / dataset dictionary / policies).

---

> **Naming guidance (example only):** mirror Layer/Segment/State slugs (e.g., `schemas/l1/seg_1A/...`).  
> Use the convention that best matches your engine and specs.

---

## Do / Don’t
- I'll let you use best practices for this.

---

## Packaging & snapshots (informational)
- The engine may embed a **read-only snapshot** of these contracts for offline/repro use.  
  Source of truth remains this folder; embedded copies should match a pinned digest/version.
