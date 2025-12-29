# Authoring Guide — `prior.population` (6A.S1 world + geo population sizing, v1)

## 0) Purpose

`prior.population` is the **sealed authority** that tells **6A.S1** how big the party universe should be, and how that population is distributed across geography and party types.

It must be strong enough that:

* S1 **cannot invent** population semantics,
* the resulting world is **non-toy** (not “10 customers everywhere”, not “all countries identical”),
* population size is **plausible relative to the world’s commerce footprint** (outlets + arrival intensity),
* the prior remains **token-less** and **stable** (digest comes from S0 sealing, not in-file fields).

This prior controls **counts and splits only**. It does **not** define segment mixes (`segment_id` split is owned by `prior.segmentation`) and it does **not** define products/devices/fraud roles.

---

## 1) File identity (MUST)

* **Artefact ID:** `prior.population_6A`
* **Manifest key (recommended):** `mlr.6A.prior.population`
* **Path:** `config/layer3/6A/prior/prior.population_6A.v1.yaml`
* **Schema anchor:** *(permissive or stub; this guide is binding until a concrete anchor exists)*
* **Token-less posture:** do **not** embed timestamps, digests, or “generated_at”. Digests are recorded by `6A.S0` in `sealed_inputs_6A`.

---

## 2) What 6A.S1 MUST be able to derive from this prior

Given:

* a sealed world (`manifest_fingerprint`) and
* a target `seed`,

S1 must be able to compute:

1. **World total target population** `N_world_target` (continuous), and a realised integer `N_world_int`.

2. **Geography weights** over a “population geography unit” (v1: country):

* `W_country(c)` for each `country_iso` in the world’s country universe.

3. **Per-country party-type targets**:

* `N_country_partytype_target(c, party_type)` for `party_type ∈ {RETAIL, BUSINESS, OTHER}`.

4. **Constraints** used by S1’s integerisation:

* floors like `min_parties_per_country`, `min_parties_per_partytype_in_country`,
* optional “must-nonzero” constraints like `min_parties_per_cell`.

Everything else in S1 (segment splits, party attributes) is handled by other priors/taxonomies.

---

## 3) Allowed upstream hints (for realism; decision-free)

This prior is allowed to reference *only* upstream artefacts that S1 is allowed to read (as sealed inputs) and can aggregate deterministically:

* `outlet_catalogue` (1A) → outlet counts per `legal_country_iso`
* `merchant_zone_profile_5A` (5A) → expected weekly arrivals per country (if you aggregate its rows)
* optional `zone_alloc` (3A) to interpret zone richness per country

It MUST NOT require reading **arrival rows** from 5B.

If a hint is missing from `sealed_inputs_6A`, S1 must fall back to the specified fallback rule (fail-closed is allowed if you mark it REQUIRED).

---

## 4) Pinned v1 semantics (decision-free)

### 4.1 Population geography unit (v1)

v1 uses **country** as the primary geography unit.

* `country_iso` values are discovered from the sealed world (e.g., countries present in 1A outlets, or present in 3A zone universe).
* Countries not present in the world MUST be ignored.
* Countries present MUST receive a well-formed weight `W_country(c)`.

### 4.2 World size model (v1)

v1 defines **active population** first, then inflates to total population:

* Let `A_world_weekly` be the total expected weekly arrivals across the world, computed from 5A if available:

  `A_world_weekly = Σ rows weekly_volume_expected`

* Let `a_ppw` be the target **arrivals per active party per week** (a scalar).

* Let `active_fraction` be the expected fraction of parties that are “active enough” to appear in arrival attachment.

Then:

* `N_active_target = A_world_weekly / a_ppw`
* `N_world_target = N_active_target / active_fraction`

Clamp:

* `N_world_target = clamp(N_world_target, N_world_min, N_world_max)`

Fallback if 5A is unavailable (or you choose not to use it):

* `N_world_target = total_outlets * parties_per_outlet`
  with clamp to the same `[N_world_min, N_world_max]`.

### 4.3 Country weights model (v1)

Compute a raw “country mass” from available hints:

* `outlets_c = outlet_count(country=c)` (from 1A)
* `arrivals_c = expected_weekly_arrivals(country=c)` (from 5A) if available

Raw weight:

* `w_c = (outlets_c + outlet_offset) ^ outlet_exponent`
* If arrivals are used: `w_c *= (arrivals_c + arrival_offset) ^ arrival_exponent`

Then apply a floor and renormalise:

* `w_c = max(w_c, country_weight_floor)`
* `W_country(c) = w_c / Σ_c w_c`

### 4.4 Party-type mix per country (v1)

For each country `c`, define party-type shares:

* `share_retail(c)`
* `share_business(c)`
* `share_other(c)`

Rules:

* Shares must sum to 1.0 within tolerance.
* `share_business(c)` is allowed to depend weakly on country mass (bigger economies tend to have more business customers), but must be deterministic and pinned by this prior.

Target counts:

* `N_country_target(c) = N_world_target * W_country(c)`
* `N_country_partytype_target(c, t) = N_country_target(c) * share_t(c)`

S1 integerises these targets into integers with your existing residual policy (RNG-bearing realisation is allowed; the prior only provides the targets + constraints).

---

## 5) Required file structure (fields-strict)

Top-level YAML object with **exactly** these keys:

1. `prior_id` (MUST equal `prior.population_6A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `population_unit` (MUST equal `parties`)
4. `geo_unit` (MUST equal `country_iso`)
5. `world_size_model` (object)
6. `country_weight_model` (object)
7. `party_type_model` (object)
8. `constraints` (object)
9. `realism_targets` (object)
10. `inputs_allowed` (object)
11. `notes` (optional string)

Unknown keys: **INVALID**.

### 5.1 `world_size_model` (MUST)

Required fields:

* `mode` ∈ `{ arrivals_based_v1, outlets_based_v1 }`
* `active_fraction` (number in `(0,1]`)
* `arrivals_per_active_party_per_week` (number > 0) *(required if arrivals_based_v1)*
* `parties_per_outlet` (number > 0) *(required if outlets_based_v1)*
* `N_world_min` (int ≥ 1)
* `N_world_max` (int ≥ `N_world_min`)

Optional (recommended realism):

* `seed_scale_lognormal_sigma` (number in `[0, 1.0]`)
  *(S1 may draw a seed-specific multiplier with mean 1; if omitted treat sigma=0)*
* `seed_scale_clip` (object `{min: >0, max: >=min}`)

### 5.2 `country_weight_model` (MUST)

Required fields:

* `use_outlets` (bool; v1 SHOULD be true)
* `use_arrivals` (bool; v1 recommended if 5A is sealed)
* `outlet_offset` (number ≥ 0)
* `outlet_exponent` (number ≥ 0)
* `arrival_offset` (number ≥ 0)
* `arrival_exponent` (number ≥ 0)
* `country_weight_floor` (number > 0)

Optional:

* `max_country_share_cap` (number in `(0,1]`) *(used only as a validation corridor; not a hard clamp)*

### 5.3 `party_type_model` (MUST)

Required fields:

* `party_types` (list; MUST include exactly `{RETAIL, BUSINESS, OTHER}`)
* `base_shares` (object with keys `RETAIL`, `BUSINESS`, `OTHER`)
* `country_adjustment` (object)

`country_adjustment` required fields:

* `mode` ∈ `{ none, mass_tilt_v1 }`

If `mass_tilt_v1`, required:

* `business_tilt_strength` (number in `[0, 0.25]`)
* `other_tilt_strength` (number in `[0, 0.10]`)
* `tilt_reference_share` (number in `(0,1)`; e.g. median `W_country`)

Interpretation (v1):

* larger-than-reference countries get slightly higher `BUSINESS` share and slightly lower `RETAIL`, preserving sum=1.

### 5.4 `constraints` (MUST)

Required:

* `min_parties_per_country` (int ≥ 0)
* `min_parties_per_party_type_in_country` (object with keys `RETAIL`, `BUSINESS`, `OTHER`, each int ≥ 0)
* `min_parties_per_cell` (int ≥ 0)
  *(this is the “min_parties_per_cell” referenced by S1 spec; if >0 then S1 must honour it where a cell exists)*

Optional:

* `allow_zero_other_in_small_countries` (bool; default true)

### 5.5 `realism_targets` (MUST)

These are acceptance corridors (fail-closed if violated):

Required:

* `active_fraction_range` (object `{min, max}` within `(0,1]`)
* `arrivals_per_active_party_per_week_range` (object `{min>0, max>=min}`) *(if arrivals_based_v1)*
* `parties_per_outlet_range` (object `{min>0, max>=min}`) *(if outlets_based_v1, or as a derived check)*
* `business_share_range` (object `{min, max}`) *(world-level after aggregation)*
* `country_share_gini_min` (number in `[0,1]`) *(prevents uniform toy worlds)*
* `max_country_share_range` (object `{min, max}`) *(to prevent one-country dominance unless intended)*

### 5.6 `inputs_allowed` (MUST)

Required:

* `hints` (list of strings; allowed values):

  * `OUTLET_COUNTS_BY_COUNTRY`
  * `EXPECTED_ARRIVALS_BY_COUNTRY`
  * `ZONE_RICHNESS_BY_COUNTRY`
* `required_hints` (list; subset of `hints`)

Rule:

* If a hint is listed in `required_hints` but is missing from `sealed_inputs_6A` with `ROW_LEVEL`, S1 MUST FAIL (do not silently fallback).

---

## 6) Authoring procedure (Codex-ready)

1. **Choose the world size mode**

   * Prefer `arrivals_based_v1` if 5A is always sealed for 6A (recommended).
   * Otherwise use `outlets_based_v1`.

2. **Set core realism anchors**

   * `active_fraction`: typical 0.25–0.65
   * `arrivals_per_active_party_per_week`: typical 2–25 (depends on how “arrival” maps to activity)
   * `N_world_min/N_world_max`: wide enough to support both small and large worlds.

3. **Define country weighting**

   * Use outlets and arrivals as weights with mild exponents (avoid extreme dominance).
   * Pick `country_weight_floor` so small countries never become numerically zero.

4. **Define party type mix**

   * Choose `base_shares` that are plausible globally (e.g. retail dominant).
   * Add only mild `mass_tilt_v1` (business share rises slightly with country mass).

5. **Set constraints**

   * Ensure `min_parties_per_country` is large enough to avoid toy countries (e.g. ≥ 5000 for multi-country worlds), but not so large that tiny country universes become impossible.
   * Ensure per-party-type minima are coherent (e.g., `OTHER` can be very small).

6. **Run acceptance checks**

   * Validate structure + ranges + derived-world corridors.

7. **Freeze formatting**

   * Sort `party_types` list.
   * Keep file token-less; no anchors/aliases.

---

## 7) Minimal v1 example (realistic)

```yaml
prior_id: prior.population_6A
version: v1.0.0
population_unit: parties
geo_unit: country_iso

world_size_model:
  mode: arrivals_based_v1
  active_fraction: 0.45
  arrivals_per_active_party_per_week: 8.0
  N_world_min: 200000
  N_world_max: 50000000
  seed_scale_lognormal_sigma: 0.12
  seed_scale_clip: { min: 0.75, max: 1.35 }

country_weight_model:
  use_outlets: true
  use_arrivals: true
  outlet_offset: 50.0
  outlet_exponent: 0.85
  arrival_offset: 1000.0
  arrival_exponent: 0.20
  country_weight_floor: 1.0
  max_country_share_cap: 0.70

party_type_model:
  party_types: [BUSINESS, OTHER, RETAIL]
  base_shares:
    RETAIL: 0.965
    BUSINESS: 0.032
    OTHER: 0.003
  country_adjustment:
    mode: mass_tilt_v1
    business_tilt_strength: 0.08
    other_tilt_strength: 0.02
    tilt_reference_share: 0.02

constraints:
  min_parties_per_country: 25000
  min_parties_per_party_type_in_country:
    RETAIL: 20000
    BUSINESS: 600
    OTHER: 50
  min_parties_per_cell: 0
  allow_zero_other_in_small_countries: true

realism_targets:
  active_fraction_range: { min: 0.25, max: 0.70 }
  arrivals_per_active_party_per_week_range: { min: 2.0, max: 25.0 }
  parties_per_outlet_range: { min: 50.0, max: 4000.0 }
  business_share_range: { min: 0.01, max: 0.08 }
  country_share_gini_min: 0.25
  max_country_share_range: { min: 0.10, max: 0.80 }

inputs_allowed:
  hints:
    - OUTLET_COUNTS_BY_COUNTRY
    - EXPECTED_ARRIVALS_BY_COUNTRY
    - ZONE_RICHNESS_BY_COUNTRY
  required_hints:
    - OUTLET_COUNTS_BY_COUNTRY
    - EXPECTED_ARRIVALS_BY_COUNTRY

notes: >
  v1 sizes population from 5A expected arrivals, inflating by active_fraction.
  Country weights use both outlets and expected arrivals to avoid toy uniformity.
```

---

## 8) Acceptance checklist (MUST)

### 8.1 Structural

* YAML parses cleanly.
* Top-level keys exactly as specified (unknown keys invalid).
* `prior_id == prior.population_6A`
* `geo_unit == country_iso`
* Token-less: no timestamps, UUIDs, in-file digests.
* No YAML anchors/aliases.

### 8.2 Range validity

* `active_fraction ∈ (0,1]`
* `N_world_min ≥ 1` and `N_world_max ≥ N_world_min`
* If arrivals_based: `arrivals_per_active_party_per_week > 0`
* Exponents/offsets are finite and non-negative as specified.
* Base shares sum to 1 within tolerance (e.g., `1e-9`).

### 8.3 Derived realism corridors (S1 should validate)

Using sealed hints (outlets/arrivals), S1 can compute:

* implied `N_world_target` lies within `[N_world_min,N_world_max]`
* implied `parties_per_outlet` lies within configured corridor
* aggregated world business share lies within `business_share_range`
* country weight distribution is not uniform-toy:

  * gini(country shares) ≥ `country_share_gini_min`
* max country share within `max_country_share_range` (unless world is effectively single-country)

### 8.4 Compatibility with taxonomies

* `party_type_model.party_types` matches the canonical set used in `taxonomy.party`.

---

## 9) Change control (MUST)

* Any semantic change to how world size or country weighting is derived is **breaking**:

  * bump version and filename (`prior.population_6A.v2.yaml`)
  * update S1 validation corridors accordingly
* Never “quietly” widen allowed inputs: if you add new hint types, update `inputs_allowed` and keep the previous behaviour available or version it.
