# Authoring Guide — `scenario_overlay_policy_5A` (5A.S4 event → overlay factor law, v1)

## 0) Purpose

`scenario_overlay_policy_5A` is the **sealed authority** that defines:

* the **event vocabulary** (types + required fields),
* which **scopes** an event may target (global / country / tzid / demand_class / merchant),
* how each event maps to an **overlay factor** `F(h)` over the horizon buckets, and
* how multiple overlays combine and clamp.

It exists so S4 can apply scenario overlays **without inventing rules**.

This file is token-less (sealed by S0); do **not** embed digests or timestamps.

---

## 1) File identity (MUST)

* **Artefact ID:** `scenario_overlay_policy_5A`
* **Path:** `config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/scenario/scenario_overlay_policy_5A` *(permissive; this guide pins the real contract)*
* **Digest posture:** S0 sealing inventory is authoritative; no in-file digest fields.

---

## 2) Pinned semantics (decision-free)

### 2.1 Overlay factor definition

For each horizon bucket `h` (as defined by `scenario_horizon_config_5A`), S4 computes a multiplicative overlay:

* `λ_scenario(h) = λ_base(h) * F_total(h)`

Where:

* `F_total(h)` is the product of per-event factors for all events active at bucket `h`, after applying precedence and clamps.

### 2.2 Active-at-bucket law (UTC)

An event is active at horizon bucket `h` iff:

* `event.start_utc < bucket_end_utc(h)` AND `event.end_utc > bucket_start_utc(h)`
  (half-open intersection; consistent with UTC horizon semantics).

### 2.3 Scope matching law

An event matches a target row `(merchant_id, legal_country_iso, tzid, demand_class)` iff all scope predicates present on the event hold:

Allowed predicates (v1):

* `scope.global == true`
* `scope.country_iso == legal_country_iso`
* `scope.tzid == tzid`
* `scope.demand_class == demand_class`
* `scope.merchant_id == merchant_id`

Multiple predicates can be combined (AND). If scope has no predicates (empty) → invalid (FAIL CLOSED at calendar validation).

### 2.4 Combination and clamp law (v1 pinned)

Let `E(h)` be the set of active events that match the row at bucket `h`.

v1 defines:

* `F_total(h) = clamp( Π_{e ∈ E(h)} F_e(h), min_factor, max_factor )`

Where `min_factor` and `max_factor` come from this policy.

### 2.5 Event factor shape law (v1 pinned)

v1 supports exactly two factor shapes:

1. **`constant`**

   * `F_e(h) = amplitude`

2. **`ramp`** (linear up/down around an interval)
   Parameters:

   * `amplitude_peak`
   * `ramp_in_buckets`
   * `ramp_out_buckets`

Pinned interpretation:

* during the “core” active interval, use `amplitude_peak`
* during ramp-in/out buckets near the boundaries, linearly interpolate from 1.0 to `amplitude_peak` and back.

(If you want gaussians or more shapes later, that’s v2.)

---

## 3) Required file structure (fields-strict as authored)

Top-level YAML object with **exactly** these keys:

1. `policy_id` (MUST be `scenario_overlay_policy_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `event_types` (object; vocab + defaults; §4)
4. `scope_rules` (object; allowed scopes; §5)
5. `combination` (object; product + clamp; §6)
6. `shape_kinds` (object; shape definitions; §7)
7. `calendar_validation` (object; fail-closed checks; §8)

No extra keys.

---

## 4) `event_types` (vocabulary + default factor parameters)

`event_types` MUST be a mapping from `event_type` → definition, with at least these v1 types:

* `HOLIDAY`
* `PAYDAY`
* `CAMPAIGN`
* `OUTAGE`
* `STRESS`

Each type definition MUST include:

* `default_shape_kind` (enum: `constant|ramp`)
* `default_amplitude` (number > 0)
* `amplitude_bounds` (pair `[min,max]` with `0 < min ≤ max`)
* `allowed_scope_kinds` (list; subset of allowed scope kinds in §5)

Pinned recommended defaults (non-toy):

* `HOLIDAY`: constant, amplitude 0.85, bounds [0.50, 1.05]
* `PAYDAY`: ramp, peak 1.20, bounds [1.00, 1.60]
* `CAMPAIGN`: ramp, peak 1.35, bounds [1.00, 2.50]
* `OUTAGE`: constant, amplitude 0.05, bounds [0.00, 0.50]
* `STRESS`: constant, amplitude 1.60, bounds [1.00, 3.00]

*(OUTAGE min bound may be 0.0; others should be strictly positive.)*

---

## 5) `scope_rules` (allowed scope kinds + predicate constraints)

`scope_rules` MUST define:

* `allowed_scope_kinds` list (v1 pinned):

  * `global`
  * `country`
  * `tzid`
  * `demand_class`
  * `merchant`

* `predicate_schema` (object) defining allowed keys:

  * `global` (bool)
  * `country_iso` (ISO2)
  * `tzid` (IANA tzid)
  * `demand_class` (string)
  * `merchant_id` (uint64)

Pinned rule:

* Every event MUST have at least one predicate (global counts).
* `global: true` MUST NOT be combined with any other predicate (prevents ambiguous semantics).
* If `merchant_id` is present, the event MUST NOT also include `country_iso`/`tzid` (merchant is fully specific).
* If `tzid` present, `country_iso` MAY be present (AND), but is optional.

---

## 6) `combination` (product + clamps)

`combination` MUST contain:

* `mode` (MUST be `multiplicative_product_v1`)
* `min_factor` (number ≥ 0)
* `max_factor` (number > 0)
* `apply_clamp_after_product` (bool; MUST be true)

Recommended non-toy bounds:

* `min_factor = 0.0`
* `max_factor = 5.0`

---

## 7) `shape_kinds` (shape parameter validation)

Define exactly:

### 7.1 constant

```yaml
constant:
  required_params: ["amplitude"]
  amplitude_min: 0.0
  amplitude_max: 5.0
```

### 7.2 ramp

```yaml
ramp:
  required_params: ["amplitude_peak", "ramp_in_buckets", "ramp_out_buckets"]
  amplitude_peak_min: 0.0
  amplitude_peak_max: 5.0
  ramp_in_buckets_max: 48
  ramp_out_buckets_max: 48
```

Pinned semantics:

* Ramp parameters are measured in **horizon buckets** (so bucket size is scenario-config controlled).

---

## 8) `calendar_validation` (fail-closed checks)

This section defines checks S4 must apply to `scenario_calendar_5A` before using it.

Must include:

* `require_event_type_in_vocab: true`
* `require_scope_valid: true`
* `require_time_within_horizon: true`
* `disallow_empty_scope: true`
* `disallow_unknown_fields: true`
* `max_events_per_scenario` (int; non-toy, e.g. 50000)
* `max_overlap_events_per_row_bucket` (int; e.g. 20)

---

## 9) Realism floors (MUST; prevents toy policy)

Codex MUST reject authoring if any fail:

* All 5 event types exist in `event_types`.
* Every type has bounds that contain its default amplitude.
* `combination.max_factor ≥ 3.0` and ≤ 10.0
* `calendar_validation.max_events_per_scenario ≥ 5000`
* `calendar_validation.max_overlap_events_per_row_bucket ≥ 10`
* `version` non-placeholder

---

## 10) Recommended v1 policy (copy/paste baseline)

```yaml
policy_id: scenario_overlay_policy_5A
version: v1.0.0

event_types:
  HOLIDAY:
    default_shape_kind: constant
    default_amplitude: 0.85
    amplitude_bounds: [0.50, 1.05]
    allowed_scope_kinds: [country, tzid, demand_class]
  PAYDAY:
    default_shape_kind: ramp
    default_amplitude: 1.20
    amplitude_bounds: [1.00, 1.60]
    allowed_scope_kinds: [country, demand_class]
  CAMPAIGN:
    default_shape_kind: ramp
    default_amplitude: 1.35
    amplitude_bounds: [1.00, 2.50]
    allowed_scope_kinds: [global, country, demand_class, merchant]
  OUTAGE:
    default_shape_kind: constant
    default_amplitude: 0.05
    amplitude_bounds: [0.00, 0.50]
    allowed_scope_kinds: [merchant, tzid]
  STRESS:
    default_shape_kind: constant
    default_amplitude: 1.60
    amplitude_bounds: [1.00, 3.00]
    allowed_scope_kinds: [global, country]

scope_rules:
  allowed_scope_kinds: [global, country, tzid, demand_class, merchant]
  predicate_schema:
    global: bool
    country_iso: ISO2
    tzid: IANA_TZID
    demand_class: DEMAND_CLASS
    merchant_id: U64
  rules:
    require_at_least_one_predicate: true
    global_cannot_combine: true
    merchant_scope_is_exclusive: true

combination:
  mode: multiplicative_product_v1
  min_factor: 0.0
  max_factor: 5.0
  apply_clamp_after_product: true

shape_kinds:
  constant:
    required_params: [amplitude]
    amplitude_min: 0.0
    amplitude_max: 5.0
  ramp:
    required_params: [amplitude_peak, ramp_in_buckets, ramp_out_buckets]
    amplitude_peak_min: 0.0
    amplitude_peak_max: 5.0
    ramp_in_buckets_max: 48
    ramp_out_buckets_max: 48

calendar_validation:
  require_event_type_in_vocab: true
  require_scope_valid: true
  require_time_within_horizon: true
  disallow_empty_scope: true
  disallow_unknown_fields: true
  max_events_per_scenario: 50000
  max_overlap_events_per_row_bucket: 20
```

---

## 11) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; top-level keys exactly as §3.
2. All required event types exist; defaults inside bounds.
3. Scope rules satisfy pinned constraints (global exclusive, merchant exclusive).
4. Combination mode + clamps correct.
5. Shape kind validators present.
6. Calendar validation thresholds non-toy.
7. No timestamps / generated fields.

---
