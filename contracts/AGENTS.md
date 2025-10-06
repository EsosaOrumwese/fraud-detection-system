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
> Use those specs to author/update files in this folder.

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

## What belongs here (to be created as you implement)
- `schemas/…` — JSON Schemas for inputs/outputs (organize however you prefer; consistent, discoverable paths)
- `dataset_dictionary/…` — one or more YAML files defining datasets referenced by those schemas
- `policies/…` — numeric corridors, bounds, priors (YAML/JSON)
- Optional:
  - `VERSION` — contracts SemVer (e.g., 1.0.0)
  - `CONTRACTS_LOCK.json` — file→digest map for reproducibility

> **Naming guidance (example only):** mirror Layer/Segment/State slugs (e.g., `schemas/l1/seg_1A/...`).  
> Use the convention that best matches your engine and specs.

---

## Do / Don’t
**Do**
- Ground every change in a **specific contract-spec section** (link it in PRs).
- Keep contracts **language-agnostic** (JSON/YAML) so all consumers can read them.
- Maintain determinism fields where required (`seed`, `parameter_hash`, `manifest_fingerprint`).
- Add/update **fixtures** validated by these schemas (positive & negative).

**Don’t**
- Don’t store raw vendor data or generated outputs here.
- Don’t let runtime code **write** into this folder (author via PRs).
- Don’t promote narratives/overviews/previews to binding authority.

---

## Packaging & snapshots (informational)
- The engine may embed a **read-only snapshot** of these contracts for offline/repro use.  
  Source of truth remains this folder; embedded copies should match a pinned digest/version.

---

## Scope boundary
This folder is authority for **contracts** only. Implementation lives in `packages/engine/**`.  
Data-intake previews/flows live under `docs/model_spec/data-engine/specs/data-intake/**` and are **guiding**, not binding.
