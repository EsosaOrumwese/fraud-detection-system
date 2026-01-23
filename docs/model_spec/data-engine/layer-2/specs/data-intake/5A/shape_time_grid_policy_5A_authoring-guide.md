# Authoring Guide — `shape_time_grid_policy_5A` (5A.S2 local-week discretisation authority)

## 0) Purpose

`shape_time_grid_policy_5A` is the **sealed authority** for what a “local week” means in Segment 5A:

* the **bucket resolution** (minutes per bucket),
* the **week start convention**,
* the **day-of-week encoding**, and
* the **mapping law** between `bucket_index k` and `(local_day_of_week, local_minutes_since_midnight)`.

It exists so **S2/S4/S5 cannot improvise time semantics**. Any change to the grid MUST be enacted by changing this policy and minting a new `parameter_hash`.

> Note: your current `shape_library_5A` guide already embeds a `grid` section. If you keep that combined artefact, treat this policy as the **extracted / standalone** version of that grid contract.

---

## 1) File identity (MUST)

* **Artefact ID:** `shape_time_grid_policy_5A`
* **Path:** `config/layer2/5A/policy/shape_time_grid_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/shape_time_grid_policy_5A`
* **Token-less posture:** do **not** embed digests, timestamps, `generated_at`, hostnames, or provenance in-file (S0 sealing inventory is authoritative).

---

## 2) Pinned v1 semantics (decision-free)

v1 is intentionally narrow and MUST pin:

* **week start:** `monday_00_00_local`
* **day-of-week encoding:** `1=Mon,...,7=Sun`
* **minutes per day:** `1440`
* **days per week:** `7`
* **allowed bucket resolutions:** `bucket_duration_minutes ∈ {15, 30, 60}`

### 2.1 DST posture (MUST be explicit)

This policy defines a **repeatable civil-time week**:

* A day is always treated as **1440 minutes** for grid purposes.
* DST is handled only by upstream UTC→local conversion (2A civil-time); once `(local_day_of_week, local_minutes_since_midnight)` are known, mapping to `k` is purely arithmetic.

Implication (acceptable + intended):

* In “fall back”, two different UTC instants can map to the same `(dow, minute)` and therefore the same `k` (baseline repeats).
* In “spring forward”, some local minutes never occur; those UTC instants map to the next valid local minute (and therefore a valid `k`).

---

## 3) Payload shape (fields-strict)

Top-level keys MUST be exactly:

* `version` (string; non-placeholder; e.g. `v1.0.0`)
* `grid` (object; §4)
* `notes` (string; optional; MUST NOT contain timestamps)

No other top-level keys.

---

## 4) `grid` (MUST)

### 4.1 Required keys

`grid` MUST contain:

* `bucket_duration_minutes` (int) — MUST be one of `{15, 30, 60}`
* `week_start` (string) — MUST be `monday_00_00_local`
* `day_of_week_encoding` (string) — MUST be `1=Mon,...,7=Sun`
* `minutes_per_day` (int) — MUST be `1440`
* `days_per_week` (int) — MUST be `7`

And MUST also contain the derived integer counts (explicit, not “implementation-defined”):

* `buckets_per_day` (int) — MUST equal `minutes_per_day / bucket_duration_minutes`
* `T_week` (int) — MUST equal `days_per_week * buckets_per_day`

And MUST pin the mapping law strings (so nobody re-interprets them later):

* `bucket_index_law` (string) — MUST be:

  * `k=(dow-1)*T_day + floor(minute/bucket_minutes)`
* `inverse_mapping_law` (string) — MUST be:

  * `dow=1+floor(k/T_day); minute=(k%T_day)*bucket_minutes`

Where:

* `T_day = buckets_per_day`
* `bucket_minutes = bucket_duration_minutes`
* `dow ∈ {1..7}`
* `minute ∈ {0..1439}`

### 4.2 Grid invariants (MUST)

Codex MUST reject authoring if any fail:

* `1440 % bucket_duration_minutes == 0`
* `buckets_per_day == 1440 / bucket_duration_minutes` (exact integer)
* `T_week == 7 * buckets_per_day`
* Coverage is exactly one full local week:

  * `k ∈ [0 .. T_week-1]` (contiguous; no gaps)

---

## 5) Derived flags (OPTIONAL but recommended)

If you want `shape_grid_definition_5A` to carry helper flags like `is_weekend` and `is_nominal_open_hours`, define them here so they’re not ad-hoc.

Add a `derived_flags` object inside `grid` (and only there). If present, it MUST be fields-strict.

### 5.1 Weekend definition (recommended)

`grid.derived_flags` MAY include:

* `weekend_days` (list of ints) — v1 recommended: `[6, 7]`
* `is_weekend_law` (string) — MUST be: `dow in weekend_days`

### 5.2 Nominal open hours (recommended, generic)

`grid.derived_flags` MAY include a generic “office-hours style” window used only for sanity/diagnostics:

* `nominal_open_hours` (object):

  * `days` (list of ints) — v1 recommended: `[1,2,3,4,5]`
  * `start_minute` (int) — v1 recommended: `540` (09:00)
  * `end_minute_exclusive` (int) — v1 recommended: `1020` (17:00)
* `is_nominal_open_hours_law` (string) — MUST be:

  * `dow in days AND start_minute <= minute < end_minute_exclusive`

Invariants if present:

* `0 <= start_minute < end_minute_exclusive <= 1440`
* `start_minute % bucket_duration_minutes == 0`
* `end_minute_exclusive % bucket_duration_minutes == 0`

---

## 6) Cross-policy alignment rules (MUST)

Codex MUST enforce:

1. **Horizon alignment (S4 contract)**

   * For every scenario S4 may run, `scenario_horizon_config_5A.bucket_duration_minutes` MUST equal `grid.bucket_duration_minutes`.
   * Rationale: S4’s `κ(h)` mapping is defined as a 1-to-1 mapping from horizon buckets to weekly buckets.

2. **Encoding alignment**

   * Any component mapping UTC→local must use the same pinned encoding:

     * `1=Monday, …, 7=Sunday`.

3. **Shape alignment**

   * Any shape policy/library that emits vectors indexed by `k` MUST use the same `T_week` and bucket law.

If any of these fail, treat it as a **misconfigured world**: mint a new `parameter_hash` after fixing configs.

---

## 7) Deterministic authoring algorithm (Codex-no-input)

Codex authors `shape_time_grid_policy_5A` as follows:

1. Read `scenario_horizon_config_5A`.
2. Collect all `bucket_duration_minutes` values for the scenario set.
3. Enforce **single duration** for v1:

   * all scenarios MUST share the same `bucket_duration_minutes`.
4. Set `grid.bucket_duration_minutes` to that value.
5. Set pinned constants:

   * `week_start=monday_00_00_local`
   * `day_of_week_encoding=1=Mon,...,7=Sun`
   * `minutes_per_day=1440`, `days_per_week=7`
6. Compute:

   * `buckets_per_day = 1440 / bucket_duration_minutes`
   * `T_week = 7 * buckets_per_day`
7. Add `bucket_index_law` and `inverse_mapping_law` exactly as pinned in §4.1.
8. (Optional) Add `derived_flags` per §5 (recommended defaults).
9. Run the acceptance checklist (§9). If any fail: reject authoring.

---

## 8) Recommended v1 example (non-toy)

```yaml
version: v1.0.0
grid:
  bucket_duration_minutes: 60
  week_start: monday_00_00_local
  day_of_week_encoding: "1=Mon,...,7=Sun"
  minutes_per_day: 1440
  days_per_week: 7
  buckets_per_day: 24
  T_week: 168
  bucket_index_law: "k=(dow-1)*T_day + floor(minute/bucket_minutes)"
  inverse_mapping_law: "dow=1+floor(k/T_day); minute=(k%T_day)*bucket_minutes"
  derived_flags:
    weekend_days: [6, 7]
    is_weekend_law: "dow in weekend_days"
    nominal_open_hours:
      days: [1, 2, 3, 4, 5]
      start_minute: 540
      end_minute_exclusive: 1020
    is_nominal_open_hours_law: "dow in days AND start_minute <= minute < end_minute_exclusive"
notes: "v1 local-week discretisation for Segment 5A; token-less; DST handled upstream."
```

---

## 9) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Top-level keys exactly `{version, grid, notes?}`; no extras.
3. `bucket_duration_minutes ∈ {15,30,60}` and divides 1440.
4. Derived counts are correct integers (`buckets_per_day`, `T_week`).
5. Law strings match pinned values exactly.
6. Optional derived flags (if present) satisfy alignment and bucket-boundary divisibility.
7. Cross-policy alignment passes:

   * every scenario in `scenario_horizon_config_5A` uses the same `bucket_duration_minutes`,
   * that duration equals this policy’s `bucket_duration_minutes`.
8. Token-less posture: no timestamps, no digests, no environment metadata.
