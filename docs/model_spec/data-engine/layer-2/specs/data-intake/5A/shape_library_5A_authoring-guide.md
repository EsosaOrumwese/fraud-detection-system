# Authoring Guide - `shape_library_5A` (5A.S2 template library + template resolution)

## 0) Purpose

`shape_library_5A` is the **sealed authority** for the "weekly shape template" side of 5A:

* defines a **library of weekly templates** (unnormalised preference curves over the grid),
* defines **template resolution** (how `(demand_class, channel_group, tzid[, scenario_profile]) → template_id` is chosen deterministically, without merchant-level logic).

It is **token-less** and sealed by **5A.S0**. Do **not** embed file digests or timestamps in the file.

---

## 1) File identity (MUST)

* **Artefact ID:** `shape_library_5A`
* **Path:** `config/layer2/5A/policy/shape_library_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/shape_library_5A` *(permissive; this guide pins the real contract)*
* **Digest posture:** digest is recorded in S0 sealing inventory (do **not** embed a `sha256_*` field)

---

## 2) Authority boundaries (MUST)

* **S2 is the only weekly-shape authority.** S3/S4 MUST NOT invent weekly shape logic.
* `shape_library_5A` is the **only authority** for:

  * the available templates,
  * the template-selection rule.
* The **local-week grid** is defined exclusively by `shape_time_grid_policy_5A`. This file MUST NOT redefine grid parameters.
* This file MUST NOT depend on `merchant_id` or per-merchant exceptions.
* Scenario-specific shape changes are **not** done here in v1 (scenario effects belong to S4 overlays). If you later want scenario-dependent templates, that’s a v2 policy.

---

## 3) Required top-level structure (fields-strict as authored)
Top-level YAML object with **exactly** these keys (no extras):

1. `policy_id` (MUST be `shape_library_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `scenario_mode` (MUST be `scenario_agnostic` in v1)
4. `channel_groups` (list; 4)
5. `zone_group_mode` (object; 5)
6. `templates` (list; 6)
7. `template_resolution` (object; 7)
8. `constraints` (object; 8)
9. `realism_floors` (object; 9)

---

## 4) `channel_groups` — MUST

A list containing **exactly** these three strings (v1 pinned):

* `card_present`
* `card_not_present`
* `mixed`

This keeps S2 template resolution compatible with S1 classing.

---

## 5) `zone_group_mode` — MUST

v1 keeps zone variation simple and deterministic:

```yaml
zone_group_mode:
  mode: tzid_hash_bucket_v1
  buckets: 8
  zone_group_id_prefix: zg
```

Pinned meaning:

* For each `tzid`, compute a deterministic `zone_group_id ∈ {zg0..zg7}` using the pinned hash law in §7.3.
* Templates may vary across zone groups (this gives you non-toy heterogeneity without using merchant_id).

---

## 6) `templates` — MUST (template library)

### 6.1 Template count realism

Templates must be **numerous** and class-diverse:

* Minimum total templates: **≥ 40**
* Minimum templates per demand_class: **≥ 3** (and ≥ 2 per channel group via resolution rules)

### 6.2 Template object shape (fields-strict)

Each template entry MUST have:

* `template_id` (string; unique; pattern `^[a-z][a-z0-9_.-]{2,63}$`)
* `demand_class` (string; must match class catalog from `merchant_class_policy_5A`)
* `channel_group` (enum from §4)
* `shape_kind` (enum; v1 pinned to `daily_gaussian_mixture`)
* `dow_weights` (list of 7 numbers; all >0)
* `daily_components` (list; ≥ 1 component)
* `baseline_floor` (number; ≥ 0)
* `power` (number; in `[0.6, 2.0]`)
* `notes` (string; non-empty; no timestamps)

### 6.3 `daily_components` component shape

Each component MUST be an object with:

* `kind` (MUST be `gaussian_peak`)
* `center_min` (int in `[0, 1439]`)
* `sigma_min` (number in `[20, 240]`)
* `amplitude` (number > 0)

---

## 7) Template evaluation + resolution (decision-free)

### 7.1 How S2 evaluates a template into an unnormalised week vector

Given `template` and bucket index `k`, using grid parameters from `shape_time_grid_policy_5A`:

1. Derive:

* `dow = 1 + floor(k / T_day)`
* `minute = (k % T_day) * bucket_duration_minutes`

2. Compute daily profile:

* `g(minute) = baseline_floor + Σ_j amplitude_j * exp(-0.5 * ((minute - center_j)/sigma_j)^2)`

3. Apply day weight and power:

* `v(k) = (dow_weights[dow] * g(minute)) ^ power`

4. Enforce:

* `v(k) ≥ 0` and finite.

S2 then normalises:

* `shape(k) = v(k) / Σ_k v(k)`
  and MUST validate the sum-to-1 tolerance in `baseline_intensity_policy_5A` / S2 rules.

### 7.2 `template_resolution` structure (fields-strict)

`template_resolution` MUST contain:

* `mode` (MUST be `deterministic_choice_by_tzid_v1`)
* `default_template_id` (string; must exist)
* `rules` (list; ≥ 1)

Each rule MUST have:

* `demand_class` (string)
* `channel_group` (string)
* `candidate_template_ids` (list of strings; length ≥ 2)
* `selection_law` (MUST be `u_det_pick_index_v1`)

Rules MUST cover **every** `(demand_class, channel_group)` pair; otherwise FAIL CLOSED.

### 7.3 Pinned deterministic selector (`u_det`) for choosing among candidate templates

This is used to select a template **per tzid** (no merchant_id):

* `msg = UTF8("5A.S2.template|" + demand_class + "|" + channel_group + "|" + tzid + "|" + parameter_hash_hex)`
* `h = SHA256(msg)`
* `x = uint64_be(h[0:8])`
* `u_det = (x + 0.5) / 2^64`  (open interval)
* `idx = floor(u_det * K)` where `K = len(candidate_template_ids)`
* pick `candidate_template_ids[idx]`

Zone group id (for §5) uses the same hash source:

* `zg = x % buckets` → `zone_group_id = zone_group_id_prefix + str(zg)`

---

## 8) `constraints` (must-stop-toy checks used by S2)

`constraints` MUST include:

* `min_mass_night` (number in `[0.02, 0.25]`)
* `night_window_minutes` (object)

  * `start_min` (e.g. `0`)
  * `end_min` (e.g. `360`)  # 00:00–06:00
* `min_weekend_mass_for_weekend_classes` (number in `[0.25, 0.55]`)
* `office_hours_window` (object)

  * `weekday_start_min` (e.g. `480`)  # 08:00
  * `weekday_end_min` (e.g. `1080`)  # 18:00
  * `min_weekday_office_mass` (number in `[0.55, 0.90]`)
* `shape_nonflat_ratio_min` (number; MUST be ≥ `1.5`)
  *(ratio of max bucket to min bucket for most templates; prevents uniform toy curves)*

Pinned interpretations:

* “Night mass” = sum of normalised shape(k) over buckets whose `minute` is in `[start_min, end_min)`.
* "Weekend mass" = sum over `dow ? weekend_days` from `shape_time_grid_policy_5A`.
* “Office hours weekday mass” = sum over Mon–Fri and `minute ∈ [weekday_start_min, weekday_end_min)`.

---

## 9) `realism_floors` (authoring-time fail-closed requirements)

This section prevents Codex from outputting a “sample policy”.

Must include (v1 pinned defaults shown):

```yaml
realism_floors:
  min_total_templates: 40
  min_templates_per_class_per_channel: 2
  require_all_classes_present: true
  require_all_channel_groups_present: true
  min_nonflat_templates_fraction: 0.90
  min_night_mass_online24h: 0.08
  min_weekend_mass_evening_weekend: 0.30
  min_weekday_mass_office_hours: 0.65
```

---

## 10) Deterministic authoring algorithm (Codex-no-input)

Codex authors `shape_library_5A` by:

1. **Read** `merchant_class_policy_5A` and extract demand classes (must cover all).
2. Resolve `shape_time_grid_policy_5A` and read its `bucket_duration_minutes`, `T_week`, and `weekend_days`.
3. For each `(demand_class, channel_group)` generate **≥ 3** template variants with different peak timings and weekend weights, using a fixed parameter table per class family (below).
4. Write `template_resolution.rules` so each `(demand_class, channel_group)` has ≥2 candidates.
5. Validate all constraints + realism floors against the generated templates (by compiling and normalising them over the grid). If any fail → abort authoring.

### v1 parameter families (non-toy, pinned)

Examples of what Codex should encode as templates (illustrative; the policy must actually contain the parameters):

* `office_hours`: strong Mon–Fri daytime peaks, low weekend mass
* `consumer_daytime`: daily noon/afternoon peaks, moderate weekend mass
* `evening_weekend`: strong evening peaks + weekend uplift
* `always_on_local`: broad mass across day, mild peaks
* `online_24h`: high night mass, mild circadian structure
* `online_bursty`: sharper peaks, higher power (more peaky)
* `travel_hospitality`: mixed daytime/evening, weekend uplift
* `fuel_convenience`: commute peaks (morning + late afternoon)
* `bills_utilities`: weekday bias, morning/early afternoon
* `low_volume_tail`: flatter but still non-uniform (must pass nonflat ratio)

---

## 11) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; top-level keys exactly as §3.
2. `shape_time_grid_policy_5A` is present in `sealed_inputs_5A` and provides grid parameters for template evaluation.
3. All templates validate:

   * non-negative, finite,
   * compile + normalise successfully,
   * meet `constraints` checks for their class family.
4. Coverage:

   * every demand_class present,
   * every channel_group present,
   * template_resolution covers every `(demand_class, channel_group)` pair and has ≥2 candidates each.
5. Realism floors pass (counts + nonflatness + night/weekend/office-mass constraints).
6. Deterministic ordering:

   * templates sorted by `(demand_class, channel_group, template_id)` ascending,
   * resolution rules sorted by `(demand_class, channel_group)` ascending.
7. No timestamps / generated_at fields.

---

## Placeholder resolution (MUST)

- Replace `policy_id` and `version` with final identifiers.
- Set `zone_group_mode.buckets` to the final grid bucket count and ensure `shape_time_grid_policy_5A` is sealed.
- Populate `templates` and `template_resolution` with the final library and mapping rules.
- Set `constraints` and `realism_floors` to final values (no placeholders).

