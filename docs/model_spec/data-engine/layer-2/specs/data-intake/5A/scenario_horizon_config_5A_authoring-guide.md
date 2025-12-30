# Authoring Guide — `scenario_horizon_config_5A` (5A.S4 Horizon + bucketisation authority)

## 0) Purpose

`scenario_horizon_config_5A` is the **sealed control-plane authority** that tells 5A:

* which **scenario IDs** exist (and their metadata),
* the **UTC horizon window** each scenario runs over,
* the **horizon bucket duration** (minutes),
* and the **exact mapping law** from each horizon bucket to S2/S3’s **local-week bucket index** `k`.

It is **token-less** and sealed by **5A.S0**. Do **not** put timestamps or digests inside the file.

---

## 1) File identity (MUST)

* **Artefact ID:** `scenario_horizon_config_5A`
* **Path:** `config/layer2/5A/scenario/scenario_horizon_config_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/scenario/scenario_horizon_config_5A` *(permissive; this guide pins the real contract)*
* **Digest posture:** digest is recorded in the S0 sealing inventory (do **not** embed file sha/digest inside the YAML)

---

## 2) Pinned semantics (decision-free)

### 2.1 Scenario selection (S0 / S4)

* The 5A run context supplies exactly one `scenario_id`.
* S0/S4 MUST find a scenario definition with **exact string match**.
* If no match exists → **FAIL CLOSED** (no defaults, no “closest match”).

### 2.2 Horizon window (UTC, v1 pinned)

For each scenario:

* `horizon_start_utc` is **inclusive**
* `horizon_end_utc` is **exclusive**
* The horizon is discretised into fixed buckets of `bucket_duration_minutes`.

Define:

* `Δ_minutes = minutes(horizon_end_utc - horizon_start_utc)`
* `H = Δ_minutes / bucket_duration_minutes`

**MUST** hold: `Δ_minutes` is an integer multiple of `bucket_duration_minutes`.
If not → **FAIL CLOSED** (no partial buckets).

### 2.3 Horizon bucket index → UTC time anchor

For each horizon bucket index `h ∈ [0..H-1]`:

* `bucket_start_utc(h) = horizon_start_utc + h * bucket_duration_minutes`
* `bucket_anchor_utc(h) = bucket_start_utc(h)`  *(v1 pinned: anchor is the start time)*

### 2.4 Mapping to local-week bucket `k` (S2/S3 grid)

For each zone tzid, S4 maps the UTC anchor to local time using **2A civil-time** (no independent tz logic):

* `anchor_local = UTC_to_local(bucket_anchor_utc(h), tzid, tz_timetable_cache)`

From that local time:

* derive `local_day_of_week ∈ {1..7}` and `local_minutes_since_midnight ∈ {0..1439}` using a **pinned convention**:

  * `1=Monday, …, 7=Sunday`

Then map to S2 grid:

* Find the unique `k` in `shape_grid_definition_5A` such that:

  * `local_day_of_week(k) == local_day_of_week(anchor_local)` and
  * `local_minutes_since_midnight(k) == floor_to_grid(anchor_local_minutes, bucket_duration_minutes)`

Where:

* `floor_to_grid(x, d) = d * floor(x / d)`

**MUST** hold:

* `shape_grid_definition_5A.bucket_duration_minutes == bucket_duration_minutes`
* For every `(tzid, h)`, a unique `k` exists (otherwise → FAIL CLOSED)

This yields the deterministic `WEEK_MAP[tzid, h] = k`.

### 2.5 Optional UTC outputs (v1)

If `emit_utc_intensities = true`, S4 MAY emit `merchant_zone_scenario_utc_5A` on the same `H` buckets, where:

* `utc_horizon_bucket_index == h`
* and the UTC anchor is exactly `bucket_anchor_utc(h)`.

---

## 3) Required file structure (pinned by this guide)

Top-level YAML object with **exactly**:

* `version` : string (non-placeholder governance tag, e.g. `v1.0.0`)
* `scenarios` : list of scenario objects (minItems ≥ 1)

Each scenario object MUST contain:

* `scenario_id` : string

  * pattern: `^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$`
* `scenario_version` : string (non-placeholder; can be semver-ish)
* `is_baseline` : boolean
* `is_stress` : boolean

  * v1 rule: exactly one of these must be true (`XOR`)
* `labels` : list of strings (may be empty; no nulls)
* `horizon_start_utc` : RFC3339 timestamp with microseconds (UTC “Z”)
* `horizon_end_utc` : RFC3339 timestamp with microseconds (UTC “Z”)
* `bucket_duration_minutes` : integer
* `emit_utc_intensities` : boolean

Optional (allowed but must live under `notes` only):

* `notes` : string (static; no timestamps)

**No extra keys** outside this structure (keep it fields-strict so Codex can’t invent knobs).

---

## 4) Realism floors (MUST; fail-closed)

Codex MUST reject authoring if any fail:

### 4.1 Scenario set realism

* `len(scenarios) ≥ 1`
* At least one scenario has `is_baseline=true`
* All `scenario_id` unique

### 4.2 Bucket duration realism

`bucket_duration_minutes` MUST be one of:

* `15`, `30`, `60`

### 4.3 Horizon length realism (prevents toy 1–7 day configs)

For each scenario:

* horizon length in days MUST satisfy: `28 ≤ days < 370`

*(If you later want multi-year horizons, make it a v2 policy with explicit scale justification.)*

### 4.4 Alignment realism

For each scenario:

* `horizon_start_utc` and `horizon_end_utc` MUST align to bucket boundaries:

  * seconds == 0 and microseconds == 0
  * minute-of-hour divisible by `bucket_duration_minutes`
* `Δ_minutes` divisible by `bucket_duration_minutes` (no partial buckets)

---

## 5) Deterministic ordering + formatting (MUST)

* Write scenarios sorted by `scenario_id` ascending.
* UTF-8, LF newlines.
* No `generated_at`, no timestamps, no environment-dependent metadata.

---

## 6) Recommended v1 example (non-toy)

```yaml
version: v1.0.0
scenarios:
  - scenario_id: baseline_v1
    scenario_version: v1.0.0
    is_baseline: true
    is_stress: false
    labels: ["baseline", "steady_state"]
    horizon_start_utc: "2026-01-01T00:00:00.000000Z"
    horizon_end_utc: "2026-04-01T00:00:00.000000Z"
    bucket_duration_minutes: 60
    emit_utc_intensities: false

  - scenario_id: stress_peak_online_v1
    scenario_version: v1.0.0
    is_baseline: false
    is_stress: true
    labels: ["stress", "peak_online", "campaign"]
    horizon_start_utc: "2026-02-01T00:00:00.000000Z"
    horizon_end_utc: "2026-04-01T00:00:00.000000Z"
    bucket_duration_minutes: 60
    emit_utc_intensities: false
```

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Top-level keys exactly `{version, scenarios}`; scenario objects contain only the allowed keys.
3. `version` and each `scenario_version` are non-placeholder.
4. `scenario_id` unique; pattern satisfied; scenarios sorted by `scenario_id`.
5. `is_baseline XOR is_stress` for every scenario.
6. `bucket_duration_minutes ∈ {15,30,60}`.
7. Timestamps are UTC “Z”, bucket-aligned, and `end > start`.
8. Horizon length floors pass (≥ 28 days, < 370 days).
9. `Δ_minutes` divisible by `bucket_duration_minutes`.

Once this is in place, S0 can bind a run to one `scenario_id`, and S4 has a fully pinned, deterministic horizon grid + mapping law (no guesswork).

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
