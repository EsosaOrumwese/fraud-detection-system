# Authoring Guide — `zone_shape_modifiers_5A` (5A.S2 deterministic zone/country adjustments)

## 0) Purpose

`zone_shape_modifiers_5A` is an **optional** 5A.S2 shape-side policy/table that defines **deterministic, zone-level modifiers** applied **after** evaluating a base template and **before** normalisation. This is exactly the “Apply deterministic modifiers” step in S2 (e.g. weekend-pattern shifts, “night economy” tilt).

It exists to add **non-toy heterogeneity across zones** without using `merchant_id` (S2 must stay class/zone-level only).

---

## 1) File identity (MUST)

* **Artefact ID:** `zone_shape_modifiers_5A`
* **Path:** `config/layer2/5A/policy/zone_shape_modifiers_5A.v1.yaml`
* **Token-less:** no timestamps/digests in-file (sealed by S0 inventory). 

---

## 2) Authority boundaries (MUST)

* S2 MUST discover this artefact only via `sealed_inputs_5A` and treat it as **read-only**.
* This policy MUST NOT:

  * depend on `merchant_id`, or per-merchant exceptions,
  * redefine the local-week grid or `bucket_index` semantics (that comes from the time-grid / shape library config).
* If this artefact is absent and marked OPTIONAL, S2 MUST be able to proceed using the documented default (neutral modifiers).

---

## 3) When it is applied (pinned v1 semantics)

For each `(demand_class, zone[, channel])` domain element, S2:

1. selects a **base template** from the shape library,
2. evaluates it into an **unnormalised** week vector `v(class, zone, k) ≥ 0`,
3. applies **zone modifiers** to obtain `v'(class, zone, k)`,
4. normalises to `shape_value = v' / Σ_k v'`.

S2 MAY record which modifiers were applied via `adjustment_flags` (recommended).

---

## 4) Required file structure (fields-strict)

Top-level YAML object MUST contain **exactly**:

1. `policy_id` (MUST be `zone_shape_modifiers_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `mode` (MUST be `bucket_profiles_v1`)
4. `zone_group_mode` (object; §5)
5. `overrides` (list; §6)  *(may be empty)*
6. `profiles` (list; §7)
7. `defaults` (object; §8)
8. `notes` (string; optional)

No extra keys.

---

## 5) `zone_group_mode` (MUST)

This MUST align with the shape library’s zone grouping so S2 can compute a `zone_group_id` deterministically.

Required keys:

* `mode` (MUST be `tzid_hash_bucket_v1`)
* `buckets` (int; v1 recommended `8`)
* `zone_group_id_prefix` (string; v1 recommended `zg`)

Pinned derivation law (string field in this policy, required):

* `zone_group_id_law` (string; MUST be exactly):

  `msg=UTF8("5A.S2.template|" + demand_class + "|" + channel_group + "|" + tzid + "|" + parameter_hash_hex); x=uint64_be(SHA256(msg)[0:8]); zone_group_id=zone_group_id_prefix + str(x % buckets)`

This mirrors the pinned selector source in your shape library guide (and avoids S2 inventing a different grouping).

---

## 6) `overrides` (MAY be empty; evaluated first)

Overrides let you inject “country/weekend-culture” realism without enumerating all zones.

Each override object MUST be fields-strict:

* `override_id` (string; unique)
* `match` (object; at least one key)

  * allowed keys: `legal_country_iso_in` (list), `tzid_in` (list), `tzid_prefix_in` (list)
* `force_profile_id` (string; must exist in `profiles`)
* `notes` (string)

Pinned semantics:

* For a domain element `(demand_class, legal_country_iso, tzid, channel_group)`:

  * if **exactly one** override matches, use its `force_profile_id`;
  * if **more than one** matches → FAIL CLOSED (ambiguous);
  * if none match, fall through to zone-group assignment.

---

## 7) `profiles` (MUST)

You MUST define a complete set of modifier profiles, each representing a “zone time-use flavour” (night economy, Fri–Sat weekend, early-bird, etc.). This is how S2 can apply “zone/country attributes” deterministically.

Each profile object MUST be fields-strict:

* `profile_id` (string; unique; e.g. `zg0`, `zg1`, …)
* `description` (string; non-empty)
* `dow_multipliers` (list of 7 numbers; all > 0)
* `time_window_multipliers` (list; may be empty)
* `constraints` (object; optional but recommended)
* `notes` (string; optional)

### 7.1 `time_window_multipliers` entry shape

Each entry MUST be:

* `window_id` (string)
* `days` (list of ints in `{1..7}` or `*`)
* `start_minute` (int in `[0, 1439]`)
* `end_minute_exclusive` (int in `[1, 1440]`, `> start_minute`)
* `multiplier` (number > 0)

**Alignment requirement:** `start_minute` and `end_minute_exclusive` MUST be multiples of `bucket_duration_minutes` from the grid (so the modifier is bucket-aligned).

### 7.2 How S2 applies a profile (pinned)

For each bucket `k` with `(dow, minute)` from the grid:
`v'(k) = v(k) * dow_multipliers[dow] * Π_{windows matching (dow,minute)} window.multiplier`

S2 then normalises; `v'` must remain ≥ 0 and finite.

---

## 8) `defaults` (MUST)

* `neutral_profile_id` (string; must exist in `profiles`)
* `on_missing_profile_id` (enum; MUST be `FAIL_CLOSED`)
* `emit_adjustment_flags` (bool; v1 recommended `true`)

Rationale: if a computed `profile_id` doesn’t exist, that is a config error (`S2_REQUIRED_SHAPE_POLICY_MISSING` / `S2_TEMPLATE_RESOLUTION_FAILED` style posture).

---

## 9) Realism floors (MUST; prevents toy modifiers)

Codex MUST reject authoring if any fail:

1. **Coverage**

   * `profiles` MUST include at least `buckets` distinct profiles with ids matching `zone_group_id_prefix + [0..buckets-1]` (e.g. `zg0..zg7`) so every zone-group can resolve.

2. **Non-trivial heterogeneity**

   * At least **3** profiles must differ materially (e.g. have at least one day multiplier outside `[0.95, 1.05]` **or** contain at least one time window multiplier outside that range).

3. **No extreme distortions**

   * All multipliers MUST be within `[0.6, 1.6]` in v1 (keeps shapes plausible; avoids “all traffic at 3am” artifacts).

4. **Does not break base constraints**

   * Authoring-time compilation check (required): apply each profile to a representative set of templates and ensure your existing `shape_library_5A.constraints` (night mass, weekend mass, non-flat ratio) remain satisfiable for the class families they are intended for.

---

## 10) Deterministic authoring algorithm (Codex-no-input)

1. Read `shape_library_5A.zone_group_mode` (buckets + prefix).
2. Create `profiles` for each `zg{i}` (i=0..buckets-1) with mild but distinct patterns, e.g.:

   * `zg0`: neutral,
   * `zg1`: evening tilt (boost 18:00–23:00),
   * `zg2`: night economy (boost 00:00–04:00),
   * `zg3`: early-bird (boost 06:00–10:00),
   * `zg4`: Fri–Sat weekend emphasis (boost Fri/Sat, reduce Sun),
   * … others mild variants.
3. Add `overrides` for any high-level country patterns you want (e.g. selected `legal_country_iso` get `zg4` for Fri–Sat weekend), keeping the list small and deterministic.
4. Set `neutral_profile_id` to the most neutral profile (usually `zg0`).
5. Run realism floors + compilation checks; fail closed if any fail.

---

## 11) Example (snippet only)

```yaml
policy_id: zone_shape_modifiers_5A
version: v1.0.0
mode: bucket_profiles_v1

zone_group_mode:
  mode: tzid_hash_bucket_v1
  buckets: 8
  zone_group_id_prefix: zg
  zone_group_id_law: 'msg=UTF8("5A.S2.template|" + demand_class + "|" + channel_group + "|" + tzid + "|" + parameter_hash_hex); x=uint64_be(SHA256(msg)[0:8]); zone_group_id=zone_group_id_prefix + str(x % buckets)'

overrides:
  - override_id: gulf_weekend_style
    match: { legal_country_iso_in: ["AE", "SA", "QA", "KW", "BH", "OM"] }
    force_profile_id: zg4
    notes: "Fri–Sat weekend emphasis profile (synthetic)."

profiles:
  - profile_id: zg0
    description: "Neutral"
    dow_multipliers: [1.0,1.0,1.0,1.0,1.0,1.0,1.0]
    time_window_multipliers: []

  - profile_id: zg2
    description: "Night economy tilt"
    dow_multipliers: [1.0,1.0,1.0,1.0,1.0,1.05,1.05]
    time_window_multipliers:
      - { window_id: night_boost, days: "*", start_minute: 0, end_minute_exclusive: 240, multiplier: 1.20 }

defaults:
  neutral_profile_id: zg0
  on_missing_profile_id: FAIL_CLOSED
  emit_adjustment_flags: true
```

---

## 12) Acceptance checklist (MUST)

* YAML parses; fields-strict keys match §4.
* `zone_group_id_law` matches pinned string exactly (no “creative variants”).
* `profiles` cover all bucket ids (`zg0..zg{buckets-1}`).
* No per-merchant fields; only zone/country/tzid matching.
* Multipliers positive, bounded, and bucket-aligned.
* Compilation/realism floors pass and don’t violate S2 invariants (non-negativity + normalisation).

