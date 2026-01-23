# Authoring Guide — `demand_scale_policy_5A` (5A.S1/S3 deterministic base scale, v1)

## 0) Purpose

`demand_scale_policy_5A` is the **sealed authority** for producing the **base scale fields** that live on `merchant_zone_profile_5A`:

* `weekly_volume_expected` (arrivals per local week), and
* `scale_factor` (dimensionless, optional but recommended),
* plus flags like `high_variability_flag`, `low_volume_flag`, `virtual_preferred_flag`.

It MUST be:

* **deterministic / RNG-free** (hash-mix is allowed, but must be pinned),
* **non-toy** (yields realistic magnitudes + heavy-tail variability),
* **stable** (no timestamps, no in-file digests),
* **total & safe** (finite, non-negative outputs for all domain rows).

---

## 1) File identity (MUST)

* **Artefact ID:** `demand_scale_policy_5A`
* **Path:** `config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/demand_scale_policy_5A` *(permissive; this guide pins the real contract)*
* **Digest posture:** token-less; digest recorded by 5A.S0 sealing inventory (do **not** embed `sha256` fields in-file)

---

## 2) Pinned output semantics (what S1 must emit)

For each `(merchant_id, legal_country_iso, tzid)` row in the 5A domain:

### 2.1 Required numeric fields (MUST)

* `weekly_volume_expected` (number, **≥ 0**, finite)
* `weekly_volume_unit` (string, MUST equal `"arrivals_per_local_week"`)

### 2.2 Optional numeric field (RECOMMENDED)

* `scale_factor` (number, **≥ 0**, finite)
  Defined so “typical” rows sit near 1.0.

### 2.3 Flags (RECOMMENDED)

* `high_variability_flag` (bool)
* `low_volume_flag` (bool)
* `virtual_preferred_flag` (bool)

If your pipeline chooses not to emit optional fields, it must be explicit and consistent; do not silently drop them in some runs.

---

## 3) Inputs S1 is allowed to use (feature vocabulary)

This policy may reference only features that S1 already has from sealed inputs:

* `demand_class` (from `merchant_class_policy_5A`)
* `demand_subclass` / `zone_role` (e.g., `primary_zone|secondary_zone|tail_zone`) if you emit it
* `channel_group` (from classing policy’s channel map)
* `virtual_mode` or `is_virtual` (from 3B, if available)
* `zone_site_count`
* `merchant_country_site_count`
* `zone_site_share`
* `zones_per_merchant_country`
* identity: `merchant_id`, `legal_country_iso`, `tzid`
* `parameter_hash` (from S0; stable)

No new external datasets should be required by this policy.

---

## 4) Deterministic variation law (`u_det`) (MUST; decision-free)

To avoid “everyone identical” toy scale, v1 uses a pinned hash-mix per `(merchant, zone)`.

For a `stage` string:

* `msg = UTF8("5A.scale|" + stage + "|" + merchant_id + "|" + legal_country_iso + "|" + tzid + "|" + parameter_hash_hex)`
* `h = SHA256(msg)`
* `x = uint64_be(h[0:8])`
* `u_det = (x + 0.5) / 2^64`  → `u_det ∈ (0,1)` open interval

This is **not RNG** (fully deterministic), but it provides stable heterogeneity.

---

## 5) Pinned scale model (v1)

v1 defines `weekly_volume_expected` as:

### 5.1 Zone role multiplier

Resolve `zone_role` as:

* `primary_zone` if `zone_site_share ≥ 0.60`
* `tail_zone` if `zone_site_share ≤ 0.10`
* else `secondary_zone`

Multipliers (v1 pinned defaults):

* primary: `1.15`
* secondary: `1.00`
* tail: `0.85`

### 5.2 Brand-size multiplier (mild nonlinearity; v1 pinned)

Let `S = max(1, merchant_country_site_count)`.

* `brand_size_multiplier = S ^ brand_size_exponent`
* v1 default: `brand_size_exponent = 0.08`
  (keeps effect mild: big chains slightly higher volume per site)

### 5.3 Virtual multiplier (v1 pinned)

If you have virtual classification:

* `NON_VIRTUAL`: `1.00`
* `HYBRID`: `1.10`
* `VIRTUAL_ONLY`: `1.25`

If virtual classification not sealed, treat all as `NON_VIRTUAL`.

### 5.4 Channel multiplier (v1 pinned)

* `card_present`: `1.00`
* `card_not_present`: `1.15`
* `mixed`: `1.05`

### 5.5 Per-site weekly volume distribution (heavy-tail, simple)

For each `demand_class`, define:

* `median_per_site_weekly`
* `pareto_alpha` (tail index > 1)
* `clip_max_per_site_weekly`

Use a **Pareto quantile** (simple, heavy-tailed) from `u_det`:

* `x_m = median_per_site_weekly / 2^(1/pareto_alpha)`
* `q(u) = x_m / (1 - u)^(1/pareto_alpha)`
* `per_site_weekly = min(q(u_det("per_site")), clip_max_per_site_weekly)`

### 5.6 Combine to get zone weekly expected

Let `n = zone_site_count`.

* If `n == 0`: `weekly_volume_expected = 0`
* Else:

  * `weekly_volume_expected = global_multiplier

    * n
    * per_site_weekly(demand_class)
    * zone_role_multiplier(zone_role)
    * brand_size_multiplier(S)
    * virtual_multiplier(virtual_mode)
    * channel_multiplier(channel_group)`

### 5.7 `scale_factor` definition (dimensionless)

If you emit `scale_factor`, define:

* `scale_factor = weekly_volume_expected / (n * ref_per_site_weekly[demand_class])` if `n>0` else `0`

Where `ref_per_site_weekly[demand_class]` is a per-class reference value (typically the class median).

This makes `scale_factor` interpretable and stable.

---

## 6) Required policy file structure (fields-strict as authored)

Top-level YAML object with **exactly** these keys:

1. `policy_id` (MUST be `demand_scale_policy_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `weekly_volume_unit` (MUST be `arrivals_per_local_week`)
4. `global_multiplier` (number > 0)
5. `brand_size_exponent` (number in `[0.0, 0.20]`)
6. `zone_role_multipliers` (mapping for `primary_zone|secondary_zone|tail_zone`)
7. `virtual_mode_multipliers` (mapping for `NON_VIRTUAL|HYBRID|VIRTUAL_ONLY`)
8. `channel_group_multipliers` (mapping for `card_present|card_not_present|mixed`)
9. `class_params` (list; one entry per demand_class)
10. `thresholds` (object)
11. `realism_targets` (object)

### 6.1 `class_params` entry shape (MUST)

Each entry:

* `demand_class` (string)
* `median_per_site_weekly` (number > 0)
* `pareto_alpha` (number, MUST satisfy `1.10 ≤ alpha ≤ 3.50`)
* `clip_max_per_site_weekly` (number, MUST be ≥ `10 * median_per_site_weekly`)
* `ref_per_site_weekly` (number > 0)  *(recommend equal to median)*
* `high_variability_flag` (bool)

### 6.2 `thresholds` (MUST)

* `low_volume_weekly_lt` (number ≥ 0)
* `high_volume_weekly_ge` (number > 0) *(optional but useful for audits)*

`low_volume_flag = (weekly_volume_expected < low_volume_weekly_lt)`
`virtual_preferred_flag = (virtual_mode != NON_VIRTUAL)` (or `false` if no virtual feature)

---

## 7) Deterministic authoring algorithm (Codex-no-input)

Codex authors the file by:

### Step A — Import class list (MUST)

Read `merchant_class_policy_5A` and extract the set of demand_class IDs from its `demand_class_catalog`.
Policy must cover **every** class.

### Step B — Populate class parameter table (v1 pinned defaults)

Use the following v1 baseline table (non-toy magnitudes; per-site weekly arrivals):

| demand_class       | median_per_site_weekly | pareto_alpha | clip_max_per_site_weekly | high_variability |
| ------------------ | ---------------------: | -----------: | -----------------------: | ---------------- |
| office_hours       |                    180 |          2.2 |                     6000 | false            |
| consumer_daytime   |                    260 |          2.0 |                     8000 | false            |
| evening_weekend    |                    240 |          2.1 |                     7000 | false            |
| always_on_local    |                    320 |          1.9 |                     9000 | false            |
| online_24h         |                    450 |          1.6 |                    20000 | false            |
| online_bursty      |                    380 |          1.4 |                    30000 | true             |
| travel_hospitality |                    200 |          2.0 |                     8000 | false            |
| fuel_convenience   |                    300 |          1.9 |                    12000 | false            |
| bills_utilities    |                    150 |          2.3 |                     6000 | false            |
| low_volume_tail    |                     40 |          2.8 |                     2000 | false            |

Set `ref_per_site_weekly = median_per_site_weekly` for all classes.

If your class catalog contains additional classes beyond these 10, Codex must FAIL CLOSED unless you extend the pinned table (that’s intentional—no silent “unknown class defaults”).

### Step C — Set global parameters (v1 pinned defaults)

* `brand_size_exponent = 0.08`
* `zone_role_multipliers = {primary:1.15, secondary:1.00, tail:0.85}`
* `virtual_mode_multipliers = {NON_VIRTUAL:1.00, HYBRID:1.10, VIRTUAL_ONLY:1.25}`
* `channel_group_multipliers = {card_present:1.00, card_not_present:1.15, mixed:1.05}`
* `thresholds.low_volume_weekly_lt = 5`
* `thresholds.high_volume_weekly_ge = 20000`

### Step D — Calibrate `global_multiplier` (deterministic, non-toy)

To avoid “toy world too quiet / too loud”, set a target mean per-site weekly activity:

* `target_mean_per_site_weekly = 350`

Compute a preview mean using sealed inputs:

1. Build the `(merchant, zone)` domain from `zone_alloc` (or equivalent).
2. For each row, compute `weekly_volume_expected` using Steps §5.1–§5.6 with `global_multiplier=1.0`.
3. Compute:

   * `mean_per_site_weekly = (Σ weekly_volume_expected) / (Σ zone_site_count)`

Set:

* `global_multiplier = clamp(target_mean_per_site_weekly / mean_per_site_weekly, 0.25, 4.0)`

This is deterministic, and it keeps the world in a realistic activity range without hand tuning.

---

## 8) Realism floors (MUST; fail-closed)

Codex MUST abort if any fails (checked using the preview computation in Step D):

1. **Coverage:** every demand_class in `merchant_class_policy_5A` has exactly one `class_params` entry.
2. **Mean per-site corridor:** after applying calibrated `global_multiplier`,

   * `150 ≤ mean_per_site_weekly ≤ 900`
3. **Heavy-tail check:**

   * `P99(weekly_volume_expected) / P50(weekly_volume_expected) ≥ 6`
4. **Non-collapse check:**

   * no single demand_class accounts for > 60% of total expected volume
5. **Sanity bounds:**

   * all weekly volumes finite, non-negative
   * `max(weekly_volume_expected) ≤ 5e6` (guardrail against absurd spikes)

If any check fails → FAIL CLOSED (policy not fit; requires explicit revision / version bump, not auto-silent acceptance).

---

## 9) Recommended v1 policy file (template)

```yaml
policy_id: demand_scale_policy_5A
version: v1.0.0
weekly_volume_unit: arrivals_per_local_week

global_multiplier: 1.000000
brand_size_exponent: 0.08

zone_role_multipliers:
  primary_zone: 1.15
  secondary_zone: 1.00
  tail_zone: 0.85

virtual_mode_multipliers:
  NON_VIRTUAL: 1.00
  HYBRID: 1.10
  VIRTUAL_ONLY: 1.25

channel_group_multipliers:
  card_present: 1.00
  card_not_present: 1.15
  mixed: 1.05

class_params:
  - demand_class: office_hours
    median_per_site_weekly: 180
    pareto_alpha: 2.2
    clip_max_per_site_weekly: 6000
    ref_per_site_weekly: 180
    high_variability_flag: false
  - demand_class: consumer_daytime
    median_per_site_weekly: 260
    pareto_alpha: 2.0
    clip_max_per_site_weekly: 8000
    ref_per_site_weekly: 260
    high_variability_flag: false
  - demand_class: evening_weekend
    median_per_site_weekly: 240
    pareto_alpha: 2.1
    clip_max_per_site_weekly: 7000
    ref_per_site_weekly: 240
    high_variability_flag: false
  - demand_class: always_on_local
    median_per_site_weekly: 320
    pareto_alpha: 1.9
    clip_max_per_site_weekly: 9000
    ref_per_site_weekly: 320
    high_variability_flag: false
  - demand_class: online_24h
    median_per_site_weekly: 450
    pareto_alpha: 1.6
    clip_max_per_site_weekly: 20000
    ref_per_site_weekly: 450
    high_variability_flag: false
  - demand_class: online_bursty
    median_per_site_weekly: 380
    pareto_alpha: 1.4
    clip_max_per_site_weekly: 30000
    ref_per_site_weekly: 380
    high_variability_flag: true
  - demand_class: travel_hospitality
    median_per_site_weekly: 200
    pareto_alpha: 2.0
    clip_max_per_site_weekly: 8000
    ref_per_site_weekly: 200
    high_variability_flag: false
  - demand_class: fuel_convenience
    median_per_site_weekly: 300
    pareto_alpha: 1.9
    clip_max_per_site_weekly: 12000
    ref_per_site_weekly: 300
    high_variability_flag: false
  - demand_class: bills_utilities
    median_per_site_weekly: 150
    pareto_alpha: 2.3
    clip_max_per_site_weekly: 6000
    ref_per_site_weekly: 150
    high_variability_flag: false
  - demand_class: low_volume_tail
    median_per_site_weekly: 40
    pareto_alpha: 2.8
    clip_max_per_site_weekly: 2000
    ref_per_site_weekly: 40
    high_variability_flag: false

thresholds:
  low_volume_weekly_lt: 5
  high_volume_weekly_ge: 20000

realism_targets:
  target_mean_per_site_weekly: 350
  mean_per_site_bounds: [150, 900]
  p99_p50_ratio_min: 6
  max_class_volume_share: 0.60
  max_weekly_volume_expected: 10000000
```

Codex MUST replace `global_multiplier` after running the deterministic calibration step (§7D). No timestamps.

---

## 10) Acceptance checklist (Codex MUST enforce)

1. YAML parses; top-level keys exactly as §6.
2. `policy_id` correct; `version` non-placeholder.
3. Class coverage exact (matches `merchant_class_policy_5A`).
4. Parameter sanity bounds (alphas, clips, multipliers) pass.
5. Deterministic calibration executed; realism floors in §8 pass on the preview distribution.
6. File written deterministically (UTF-8, LF, stable ordering).

---

## Placeholder resolution (MUST)

- Replace `policy_id` and `version` with final identifiers.
- Populate `class_params` for every `demand_class` with real `median_per_site_weekly`, `pareto_alpha`, `clip_max_per_site_weekly`, `ref_per_site_weekly`, and `high_variability_flag`.
- Set `global_multiplier`, `brand_size_exponent`, `zone_role_multipliers`, `virtual_mode_multipliers`, `channel_group_multipliers`, and `thresholds` to final values.

