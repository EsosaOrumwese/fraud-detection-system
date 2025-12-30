# Authoring Guide — `time_grid_policy_5B` (5B.S1 canonical horizon bucket grid)

## 0) Purpose

`time_grid_policy_5B` is the **sealed authority** that tells 5B.S1 how to turn each scenario’s UTC horizon into a **canonical, gap-free, overlap-free** bucket grid:

* the **bucket duration** (seconds),
* the **bucket_index law** (0-based, contiguous),
* the **alignment rules** (what is considered valid vs fail),
* and which **scenario tags** to carry onto each grid row.

This is “small” but still must be **production-grade**: strict enough that S2–S4 never invent their own time boundaries.

---

## 1) File identity (MUST)

* **Artefact ID:** `time_grid_policy_5B`
* **Path:** `config/layer2/5B/time_grid_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/time_grid_policy_5B` *(permissive shape; this guide pins the real contract)*
* **Token-less posture:** do **not** embed any digest in-file; S0 sealing inventory records file sha256.

---

## 2) Authority boundaries (MUST)

* Horizon start/end come from **`scenario_manifest_5A`** (for a given `manifest_fingerprint` + `scenario_id`).
  `time_grid_policy_5B` MUST NOT redefine horizon windows; it only governs discretisation.
* S1 MUST write `s1_time_grid_5B` exactly once per scenario, and **S2–S4 MUST reference it**.
* S1 MUST NOT use RNG.

---

## 3) Pinned semantics (decision-free)

### 3.1 Bucket duration

Policy provides `bucket_duration_seconds = D`.

Allowed v1 values:

* `900` (15 min), `1800` (30 min), `3600` (60 min)

### 3.2 Alignment rule (v1 pinned: fail-closed)

v1 requires the scenario horizon is already aligned:

For each scenario:

* `horizon_start_utc` and `horizon_end_utc` MUST satisfy:

  * seconds == 0, microseconds == 0
  * `minute_of_hour % (D/60) == 0`
* `(horizon_end_utc - horizon_start_utc)` MUST be a multiple of `D`

If any fails → **FAIL CLOSED** (no floor/ceil snapping in v1).

### 3.3 Bucket index law (v1 pinned)

Let:

* `H0 = horizon_start_utc`
* `D = bucket_duration_seconds`

For bucket_index `b = 0..H-1`:

* `bucket_start_utc(b) = H0 + b*D`
* `bucket_end_utc(b)   = bucket_start_utc(b) + D`

Where:

* `H = (horizon_end_utc - horizon_start_utc) / D`

### 3.4 Scenario tag carry law

S1 MUST carry these scenario-level fields from `scenario_manifest_5A` onto every grid row:

* `scenario_is_baseline`
* `scenario_is_stress`

Optional carry fields (allowed by policy, but MUST be explicitly listed):

* `scenario_labels` (array of strings)

### 3.5 Optional local annotations (diagnostic-only)

If enabled, S1 annotates each bucket row with:

* `local_day_of_week` (1=Mon..7=Sun)
* `local_minutes_since_midnight`
* `is_weekend` (per policy weekend days)

These annotations are for debugging/diagnostics; they MUST NOT be required for correctness downstream.

v1 pinned reference timezone for these annotations:

* `reference_tzid = "Etc/UTC"` (i.e., local == UTC)

---

## 4) Required policy file structure (fields-strict as authored by this guide)

Top-level YAML object with **exactly** these keys:

1. `policy_id` (MUST be `time_grid_policy_5B`)
2. `version` (non-placeholder governance tag, e.g. `v1.0.0`)
3. `bucket_duration_seconds` (int; one of 900/1800/3600)
4. `alignment_mode` (MUST be `require_aligned_v1`)
5. `bucket_index_base` (MUST be `0`)
6. `bucket_index_origin` (MUST be `horizon_start_utc`)
7. `carry_scenario_fields` (object; §4.1)
8. `local_annotations` (object; §4.2)
9. `guardrails` (object; §4.3)

### 4.1 `carry_scenario_fields` (MUST)

```yaml
carry_scenario_fields:
  required:
    - scenario_is_baseline
    - scenario_is_stress
  optional:
    - scenario_labels
```

### 4.2 `local_annotations` (MUST)

```yaml
local_annotations:
  emit: true|false
  reference_tzid: Etc/UTC
  day_of_week_encoding: "1=Mon,...,7=Sun"
  weekend_days: [6, 7]
```

Rules:

* If `emit: false`, S1 MUST NOT write local columns.
* If `emit: true`, `reference_tzid` MUST be exactly `Etc/UTC` in v1.

### 4.3 `guardrails` (MUST; non-toy)

```yaml
guardrails:
  min_horizon_days: 28
  max_horizon_days: 370
  max_buckets_per_scenario: 200000
```

These are checked against each scenario’s horizon length and computed `H`.

---

## 5) Deterministic construction algorithm (Codex implements; this guide specifies)

For each `scenario_id` requested by the run:

1. Read the scenario row from `scenario_manifest_5A@mf`.
   Extract:

   * `horizon_start_utc`, `horizon_end_utc`
   * `is_baseline`, `is_stress`
   * optional `labels`

2. Validate alignment and divisibility using policy §3.2.

3. Compute:

   * `H = (end - start) / D`
   * validate guardrails:

     * horizon_days in `[min_horizon_days, max_horizon_days]`
     * `H ≤ max_buckets_per_scenario`

4. Emit rows for `bucket_index = 0..H-1` with:

   * `bucket_start_utc`, `bucket_end_utc`, `bucket_duration_seconds`
   * scenario flags on every row

5. If local annotations enabled:

   * interpret `bucket_start_utc` in `Etc/UTC`
   * compute day-of-week and minutes-since-midnight
   * compute weekend using `weekend_days`

6. Output rows sorted by `bucket_index` ascending.

No RNG, no environment-dependent fields.

---

## 6) Realism floors (MUST; fail closed)

Codex MUST reject authoring (or S1 must abort) if any fails:

* `bucket_duration_seconds ∈ {900,1800,3600}`
* `alignment_mode == require_aligned_v1`
* `min_horizon_days ≥ 14` and the recommended default is **28**
* `max_horizon_days ≥ min_horizon_days`
* `max_buckets_per_scenario ≥ 10_000`
* Local annotations, if enabled, use `reference_tzid == Etc/UTC` (v1 pinned)

---

## 7) Recommended v1 policy file (copy/paste baseline)

```yaml
policy_id: time_grid_policy_5B
version: v1.0.0

bucket_duration_seconds: 3600
alignment_mode: require_aligned_v1

bucket_index_base: 0
bucket_index_origin: horizon_start_utc

carry_scenario_fields:
  required:
    - scenario_is_baseline
    - scenario_is_stress
  optional:
    - scenario_labels

local_annotations:
  emit: true
  reference_tzid: Etc/UTC
  day_of_week_encoding: "1=Mon,...,7=Sun"
  weekend_days: [6, 7]

guardrails:
  min_horizon_days: 28
  max_horizon_days: 370
  max_buckets_per_scenario: 200000
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; keys are exactly those in §4.
2. `policy_id` correct; `version` non-placeholder.
3. Bucket duration is allowed and consistent.
4. Alignment rules are pinned to fail-closed (`require_aligned_v1`).
5. Guardrails are present and non-toy.
6. If local annotations enabled, `reference_tzid == Etc/UTC` and weekend_days `[6,7]`.
7. S1 output uses bucket_index base 0, origin horizon_start_utc, and produces a contiguous grid with no gaps/overlaps.

---

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
