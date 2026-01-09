# Authoring Guide — `channel_shape_modifiers_5A` (5A.S2 deterministic channel-group adjustments)

## 0) Purpose

`channel_shape_modifiers_5A` is an **optional** 5A.S2 policy/table that defines **deterministic, channel-level modifiers** applied to the **unnormalised** weekly vector **after** base template evaluation and alongside zone/country modifiers, then S2 normalises to unit mass. This matches S2’s requirement that shapes may be adjusted by **channel attributes (e.g. POS vs e-com)** in a scenario-independent way.

---

## 1) File identity (MUST)

* **Artefact ID:** `channel_shape_modifiers_5A`
* **Path:** `config/layer2/5A/policy/channel_shape_modifiers_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/channel_shape_modifiers_5A`
* **Token-less posture:** no timestamps/digests in-file (sealed by S0 inventory). 

---

## 2) Authority boundaries (MUST)

* S2 MUST treat this artefact as **read-only** and only if it appears in `sealed_inputs_5A`. 
* This policy MUST NOT:

  * depend on `merchant_id` or per-merchant quirks (S2 is class/zone[/channel]-level only),
  * redefine the weekly grid (`bucket_index` mapping), which is owned by the time-grid/shape grid policy.
* Channel groups MUST align with the **pinned** channel-group vocabulary used by S1/S2 shape logic:

  * `card_present`, `card_not_present`, `mixed`.

If absent and marked OPTIONAL, S2 MUST fall back to **neutral modifiers** (all multipliers = 1) and still produce valid shapes.

---

## 3) When it is applied (pinned semantics)

For each `(demand_class, zone[, channel_group])` in S2’s domain:

1. Evaluate base template → unnormalised vector `v(k)` using the shape library’s pinned template evaluation.
2. Apply deterministic modifiers:

   * zone modifiers (if present),
   * **channel modifiers** from this policy (if channel dimension exists).
3. Normalise: `shape_value(k) = v'(k) / Σ_k v'(k)` and enforce Σ=1 and non-negativity.
4. Optionally emit `adjustment_flags` describing applied modifiers.

**Combination law (pinned v1):** modifiers are multiplicative and commutative:

`v'(k) = v(k) * M_zone(dow,minute) * M_channel(channel_group,dow,minute)`

So order doesn’t matter.

---

## 4) Required payload shape (fields-strict)

Top-level YAML keys MUST be exactly:

1. `policy_id` (MUST be `channel_shape_modifiers_5A`)
2. `version` (e.g. `v1.0.0`)
3. `mode` (MUST be `channel_bucket_profiles_v1`)
4. `channel_groups` (list; MUST match pinned set)
5. `by_channel_group` (object; §5)
6. `limits` (object; §6)
7. `defaults` (object; §7)
8. `notes` (string; optional)

No extra keys.

---

## 5) `by_channel_group` (MUST)

An object whose keys are exactly the pinned channel groups:

* `card_present`
* `card_not_present`
* `mixed`

Each value is a **profile** object (fields-strict):

* `description` (string; non-empty)
* `dow_multipliers` (list of 7 numbers; all > 0)
* `time_window_multipliers` (list; may be empty)
* `flags` (list of strings; optional; used for `adjustment_flags`)

### 5.1 `time_window_multipliers` entry shape

Each entry MUST be:

* `window_id` (string)
* `days` (list of ints in `{1..7}` or `"*"`)
* `start_minute` (int in `[0, 1439]`)
* `end_minute_exclusive` (int in `[1, 1440]`, `> start_minute`)
* `multiplier` (number > 0)
* `flag` (string; optional)

**Bucket alignment requirement:** `start_minute` and `end_minute_exclusive` MUST be multiples of `bucket_duration_minutes` (from the time-grid).

### 5.2 How S2 applies a channel profile (pinned)

For a bucket `k` with `(dow, minute)` from the grid:

`M_channel = dow_multipliers[dow] * Π_{windows matching (dow,minute)} window.multiplier`

---

## 6) `limits` (MUST)

Controls safe bounds (prevents toy/extreme modifiers). Required keys:

* `multiplier_min` (number; v1 recommended `0.75`)
* `multiplier_max` (number; v1 recommended `1.35`)
* `max_windows_per_profile` (int; v1 recommended `6`)

Invariants:

* all `dow_multipliers` and `window.multiplier` must be within `[multiplier_min, multiplier_max]`.

---

## 7) `defaults` (MUST)

* `neutral_when_channel_absent` (bool; v1 MUST be `true`)

  * If S2 is running without a channel dimension (i.e. shapes are `(class, zone)` only), this policy MUST be a no-op.
* `neutral_profile_key` (string; MUST be `mixed` in v1)
* `emit_adjustment_flags` (bool; v1 recommended `true`)

---

## 8) Realism floors (MUST)

Codex MUST reject authoring if any fail:

1. Coverage: `by_channel_group` has exactly the 3 pinned channel groups.
2. Non-triviality: at least **one** of `card_present` or `card_not_present` must include a time window multiplier **or** a day multiplier outside `[0.97, 1.03]` (otherwise it’s pointless).
3. Mildness: no multipliers outside `[0.75, 1.35]` (v1).
4. Does not break S2 invariants: authoring-time check must confirm that applying these modifiers to representative templates still yields non-negative, finite vectors and normalises successfully (Σ=1).

---

## 9) Deterministic authoring algorithm (Codex-no-input)

1. Set pinned `channel_groups = [card_present, card_not_present, mixed]`.
2. Write three profiles with realistic channel tendencies:

   * `card_present`: tilt slightly toward **daytime / office hours** (e.g. +10–20% during 09:00–17:00 on weekdays).
   * `card_not_present`: tilt slightly toward **evening / night** (e.g. +10–25% during 18:00–23:00 all days).
   * `mixed`: near-neutral (all 1.0; no windows).
3. Keep multipliers bounded by `limits`.
4. Ensure all windows are bucket-aligned to the time grid.
5. Run the realism floors + S2-invariant checks.

---

## 10) Example (copy/paste)

```yaml
policy_id: channel_shape_modifiers_5A
version: v1.0.0
mode: channel_bucket_profiles_v1

channel_groups: [card_present, card_not_present, mixed]

by_channel_group:
  card_present:
    description: "Slight weekday daytime tilt for POS-heavy behaviour"
    dow_multipliers: [1.00, 1.00, 1.00, 1.00, 1.00, 0.98, 0.98]
    time_window_multipliers:
      - window_id: weekday_office_boost
        days: [1,2,3,4,5]
        start_minute: 540
        end_minute_exclusive: 1020
        multiplier: 1.18
        flag: "cp_office_boost"
    flags: ["channel_cp"]

  card_not_present:
    description: "Evening tilt for e-com / remote"
    dow_multipliers: [1.00, 1.00, 1.00, 1.00, 1.00, 1.02, 1.02]
    time_window_multipliers:
      - window_id: evening_boost
        days: "*"
        start_minute: 1080
        end_minute_exclusive: 1380
        multiplier: 1.22
        flag: "cnp_evening_boost"
    flags: ["channel_cnp"]

  mixed:
    description: "Neutral"
    dow_multipliers: [1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00]
    time_window_multipliers: []
    flags: ["channel_mixed"]

limits:
  multiplier_min: 0.75
  multiplier_max: 1.35
  max_windows_per_profile: 6

defaults:
  neutral_when_channel_absent: true
  neutral_profile_key: mixed
  emit_adjustment_flags: true

notes: "Deterministic channel-group modifiers applied in S2 alongside zone modifiers; token-less."
```

---

## 11) Acceptance checklist (MUST)

* YAML parses; keys exactly as §4.
* `policy_id` matches exactly; `version` non-placeholder.
* `channel_groups` and `by_channel_group` keys match pinned set.
* All multipliers positive, within limits, and bucket-aligned to the time grid.
* No merchant-specific fields (no `merchant_id`, no per-merchant rules). 
* Applying modifiers preserves S2 invariants (finite, ≥0, Σ=1 after normalisation).
