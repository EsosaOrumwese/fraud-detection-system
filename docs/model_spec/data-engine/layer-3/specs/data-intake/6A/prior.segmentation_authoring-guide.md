# Authoring Guide — `segmentation_priors_6A` (`mlr.6A.prior.segmentation`, v1)

## 0) Purpose

`segmentation_priors_6A` is the **sealed SEGMENT_PRIOR** that 6A.S1 uses to split population **by region → party_type → segment**:

* `π_type|region(r,t)` — party type mix inside each region
* `π_segment|region,type(r,t,s)` — segment mix inside each (region, party_type)

S1 then computes cell targets:

`N_cell_target(r,t,s) = N_region_target(r) * π_type|region(r,t) * π_segment|region,type(r,t,s)`

This prior MUST be:

* token-less, RNG-free, fields-strict
* non-toy (no uniform mixes, no single segment dominates all regions)
* compatible with taxonomies (party types, segments, regions).

---

## 1) File identity (binding)

* **manifest_key:** `mlr.6A.prior.segmentation` 
* **dataset_id:** `prior_segmentation_6A` 
* **path:** `config/layer3/6A/priors/segmentation_priors_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/prior/segmentation_priors_6A`
* **sealed_inputs role expected by S1:** `SEGMENT_PRIOR` with `status="REQUIRED"` and `read_scope="ROW_LEVEL"`.

---

## 2) Dependencies (must exist and be consistent)

S1 consumes this prior alongside:

* `party_taxonomy_6A` (`mlr.6A.taxonomy.party`) — provides allowed `party_type`, `segment_id`, and `region_id` vocab.
* `population_priors_6A` (`mlr.6A.prior.population`) — provides `N_world_target` and `π_region(r)` used to compute `N_region_target(r)`.

Hard rule:

* Region IDs referenced here MUST be present in the sealed region vocabulary; otherwise S1 must fail (`TAXONOMY_COMPATIBILITY_FAILED` style).

---

## 3) What this prior must contain (S1-faithful)

For every region `r` in the world’s region set `R`:

1. `π_type|region(r, t)` for all `t ∈ {RETAIL, BUSINESS, OTHER}`, summing to 1 per region.

2. For each `(r,t)`, a segment mixture `π_segment|region,type(r,t, s)` over all valid segments for that party_type, summing to 1 per `(r,t)`.

Optional but recommended:

* **segment_profiles[s]** (0–1 scores) that downstream priors can reuse coherently (product/devices/fraud posture), without re-inventing “income/digital/cash” semantics.

---

## 4) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `prior_id` (string; MUST be `segmentation_priors_6A`)
3. `prior_version` (string; MUST be `v1`)
4. `taxonomy_binding` (object)
5. `region_party_type_mix` (list of objects)
6. `region_type_segment_mix` (list of objects)
7. `segment_profiles` (list of objects)
8. `constraints` (object)
9. `realism_targets` (object)
10. `notes` (optional string)

Unknown keys: INVALID.

Formatting MUST:

* be token-less (no `generated_at`, no digests)
* have no YAML anchors/aliases
* sort lists by stable keys (specified below)

---

## 5) Section schemas

### 5.1 `taxonomy_binding` (MUST)

Required fields:

* `expected_party_taxonomy_id` (string; e.g. `party_taxonomy_6A.v1`)
* `required_party_types` (list; MUST be `[BUSINESS, OTHER, RETAIL]` sorted)
* `segment_scope` (enum: `ALL_SEGMENTS_IN_TAXONOMY`)

S1 MUST fail if the sealed taxonomy does not contain these party types.

### 5.2 `region_party_type_mix[]` (MUST)

Each row MUST contain:

* `region_id` (string)
* `pi_type` (object with keys: `RETAIL`, `BUSINESS`, `OTHER`)

Rules:

* All values in `pi_type` must be in `[0,1]`
* Sum must be 1 within tolerance (e.g. 1e-12)
* Must cover every region_id in the sealed region set.

### 5.3 `region_type_segment_mix[]` (MUST)

Each row MUST contain:

* `region_id`
* `party_type` (one of required party types)
* `pi_segment` (list of `{segment_id, share}`)

Rules:

* segment_ids must be valid for that party_type (per taxonomy)
* shares in `(0,1)` and sum to 1 within tolerance
* must cover **every** `(region_id, party_type)` combination unless explicitly masked out (see `constraints.allowed_zero_cells`)

### 5.4 `segment_profiles[]` (MUST)

One row per segment_id (global, not per region).

Required fields (all in [0,1]):

* `segment_id`
* `party_type`
* `income_score`
* `digital_affinity`
* `cash_affinity`
* `cross_border_propensity`
* `credit_appetite`
* `stability_score`

BUSINESS segments MUST also include:

* `business_size_score` (0..1)

### 5.5 `constraints` (MUST)

Required:

* `min_share_per_segment` (float > 0; applied as a validation floor)
* `max_share_per_segment` (float in (0,1); validation ceiling)
* `min_effective_segments_per_region_type` (object: RETAIL/BUSINESS/OTHER ints)
* `effective_share_threshold` (float > 0)

Optional:

* `allowed_zero_cells` (list of objects `{region_id, party_type, segment_id}`)
  *Use sparingly; default is “no zeroing by rule”.*

### 5.6 `realism_targets` (MUST)

Required:

* `region_diversity_entropy_min` (object: RETAIL/BUSINESS/OTHER floats ≥ 0)
* `region_max_share_cap` (object: RETAIL/BUSINESS/OTHER floats in (0,1))
* `cross_region_variation_min_delta` (float ≥ 0)
* `cross_region_variation_required_if_n_regions_ge` (int ≥ 2)

Meaning:

* For each region and party_type, the segment distribution must meet entropy and max-share caps.
* If there are enough regions, at least one segment’s share must differ by ≥ delta between some pair of regions (prevents “copy-paste regions”).

---

## 6) Non-toy floors (MUST)

At minimum:

* Regions covered: every region in the sealed region set appears in both mix tables.
* In each region:

  * RETAIL must have ≥ 6 “effective” segments (share ≥ threshold)
  * BUSINESS must have ≥ 4 “effective” segments
  * OTHER must have ≥ 2 “effective” segments (if taxonomy has ≥2)

No single segment may exceed:

* 0.35 in RETAIL
* 0.45 in BUSINESS
  (unless you explicitly relax via `region_max_share_cap`, but keep it non-toy)

---

## 7) Authoring procedure (Codex-ready)

1. Read `party_taxonomy_6A` and enumerate:

   * region ids
   * party types
   * segment ids per party type.

2. Create `segment_profiles` first (global, coherent scores).

3. For each region:

   * author `π_type|region` (party type mix)
   * author `π_segment|region,type` for each party type:

     * start from a global template
     * then tilt a few segments realistically (e.g., richer regions → higher-income retail segments, larger-business segments), but keep diversity floors.

4. Validate:

   * sums = 1
   * caps/floors/entropy pass
   * region variation rule passes (if enough regions)

5. Freeze formatting (sorted lists; token-less).

---

## 8) Minimal v1 example (illustrative)

```yaml
schema_version: 1
prior_id: segmentation_priors_6A
prior_version: v1

taxonomy_binding:
  expected_party_taxonomy_id: party_taxonomy_6A.v1
  required_party_types: [BUSINESS, OTHER, RETAIL]
  segment_scope: ALL_SEGMENTS_IN_TAXONOMY

region_party_type_mix:
  - region_id: REGION_A
    pi_type: { RETAIL: 0.965, BUSINESS: 0.032, OTHER: 0.003 }
  - region_id: REGION_B
    pi_type: { RETAIL: 0.955, BUSINESS: 0.040, OTHER: 0.005 }

region_type_segment_mix:
  - region_id: REGION_A
    party_type: RETAIL
    pi_segment:
      - { segment_id: RETAIL_STUDENT,      share: 0.10 }
      - { segment_id: RETAIL_EARLY_CAREER, share: 0.18 }
      - { segment_id: RETAIL_FAMILY,       share: 0.22 }
      - { segment_id: RETAIL_MATURE,       share: 0.20 }
      - { segment_id: RETAIL_RETIRED,      share: 0.12 }
      - { segment_id: RETAIL_VALUE,        share: 0.10 }
      - { segment_id: RETAIL_MASS_MARKET,  share: 0.06 }
      - { segment_id: RETAIL_AFFLUENT,     share: 0.02 }

  - region_id: REGION_A
    party_type: BUSINESS
    pi_segment:
      - { segment_id: BUSINESS_SOLE_TRADER, share: 0.35 }
      - { segment_id: BUSINESS_MICRO,       share: 0.25 }
      - { segment_id: BUSINESS_SME,         share: 0.22 }
      - { segment_id: BUSINESS_MID_MARKET,  share: 0.12 }
      - { segment_id: BUSINESS_ECOM_NATIVE, share: 0.04 }
      - { segment_id: BUSINESS_CORPORATE,   share: 0.02 }

  - region_id: REGION_A
    party_type: OTHER
    pi_segment:
      - { segment_id: OTHER_NONPROFIT,     share: 0.60 }
      - { segment_id: OTHER_PUBLIC_SECTOR, share: 0.40 }

  # REGION_B uses same segment ids but different shares (non-toy variation)
  - region_id: REGION_B
    party_type: RETAIL
    pi_segment:
      - { segment_id: RETAIL_STUDENT,      share: 0.08 }
      - { segment_id: RETAIL_EARLY_CAREER, share: 0.16 }
      - { segment_id: RETAIL_FAMILY,       share: 0.20 }
      - { segment_id: RETAIL_MATURE,       share: 0.22 }
      - { segment_id: RETAIL_RETIRED,      share: 0.14 }
      - { segment_id: RETAIL_VALUE,        share: 0.08 }
      - { segment_id: RETAIL_MASS_MARKET,  share: 0.07 }
      - { segment_id: RETAIL_AFFLUENT,     share: 0.05 }

segment_profiles:
  - segment_id: RETAIL_AFFLUENT
    party_type: RETAIL
    income_score: 0.90
    digital_affinity: 0.65
    cash_affinity: 0.10
    cross_border_propensity: 0.70
    credit_appetite: 0.55
    stability_score: 0.75
  # ... one row per segment_id in taxonomy ...

constraints:
  min_share_per_segment: 0.002
  max_share_per_segment: 0.45
  effective_share_threshold: 0.01
  min_effective_segments_per_region_type: { RETAIL: 6, BUSINESS: 4, OTHER: 2 }

realism_targets:
  region_diversity_entropy_min: { RETAIL: 1.4, BUSINESS: 1.1, OTHER: 0.5 }
  region_max_share_cap: { RETAIL: 0.35, BUSINESS: 0.45, OTHER: 0.85 }
  cross_region_variation_min_delta: 0.02
  cross_region_variation_required_if_n_regions_ge: 2
```

---

## 9) Acceptance checklist (MUST)

* Contract pins match v1 (`mlr.6A.prior.segmentation`, correct path/schema_ref).
* All region ids exist in the sealed region vocabulary.
* For each region: `π_type|region` sums to 1.
* For each `(region, party_type)`: `π_segment|region,type` sums to 1 and uses only valid segment ids.
* Floors/caps/entropy/variation corridors pass.
* Token-less, no anchors/aliases, deterministic formatting.

---
