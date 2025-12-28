# Authoring Guide — `arrival_time_placement_policy_5B` (5B.S4 intra-bucket timestamp placement)

## 0) Purpose

`arrival_time_placement_policy_5B` is the **sealed authority** for how 5B.S4 places `N` arrivals inside each horizon bucket interval:

* `[bucket_start_utc, bucket_end_utc)`,

including:

* interval openness/closedness,
* mapping from uniforms to timestamps,
* how many RNG draws per arrival,
* and optional within-bucket shaping (v1 = uniform).

This prevents “toy” timestamping (e.g., all events at bucket start) and prevents ad-hoc RNG usage.

---

## 1) File identity (MUST)

* **Artefact ID:** `arrival_time_placement_policy_5B`
* **Path:** `config/layer2/5B/arrival_time_placement_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/policy/arrival_time_placement_policy_5B` *(permissive; this guide pins real structure)*
* **Token-less posture:** do **not** embed file digests/timestamps (S0 sealing inventory handles digest).

---

## 2) Pinned v1 semantics (decision-free)

### 2.1 Interval convention (MUST)

Each bucket is half-open in UTC:

* include start, exclude end: `[start_utc, end_utc)`

### 2.2 Draw budget (MUST; matches `arrival_rng_policy_5B`)

* Exactly **1** open-interval uniform per arrival for time placement:

  * `substream_label = arrival_time_jitter`
  * `draws_u64 = 1`

No other RNG consumption is permitted for time placement.

### 2.3 Placement law (v1 pinned)

v1 uses **uniform-in-time** within the bucket:

Given:

* bucket start `t0` (UTC),
* duration `D = bucket_duration_seconds`,
* draw `u ∈ (0,1)`,

Compute:

* `offset_seconds = u * D`
* `t = t0 + offset_seconds`

Then enforce:

* if `t >= bucket_end_utc` (possible only via floating rounding), set `t = bucket_end_utc - 1 microsecond`
* if `t < bucket_start_utc`, set `t = bucket_start_utc` (should never occur)

### 2.4 Timestamp precision (MUST)

Emit timestamps as RFC3339 with microseconds (`...Z`).

Pinned rounding law:

* represent `offset_seconds` in integer microseconds:

  * `offset_us = floor(u * D * 1_000_000)`
* `t = t0 + offset_us microseconds`

This makes the placement deterministic and avoids float-print drift.

### 2.5 Ordering within a bucket (MUST)

For a given `(merchant_id, zone_representation, bucket_index)` with `N>0` arrivals:

* generate timestamps for `arrival_seq = 1..N`
* then **sort ascending by timestamp**
* tie-break by `arrival_seq` ascending

This yields stable event ordering and avoids “same timestamp chaos”.

---

## 3) Required policy file structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `arrival_time_placement_policy_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `placement_kind` (MUST be `uniform_within_bucket_v1`)
4. `interval_semantics` (MUST be `[start,end)` )
5. `timestamp_precision` (MUST be `microsecond`)
6. `draws_per_arrival` (MUST be `1`)
7. `u_mapping` (object; §3.1)
8. `offset_quantisation` (object; §3.2)
9. `ordering` (object; §3.3)
10. `guardrails` (object; §3.4)

### 3.1 `u_mapping` (MUST)

```yaml
u_mapping:
  uniform_law: open_interval_u64
  u_from_u64: "(x+0.5)/2^64"
```

### 3.2 `offset_quantisation` (MUST)

```yaml
offset_quantisation:
  unit: microsecond
  law: floor(u * D_seconds * 1_000_000)
  clamp_end_exclusive: true
```

### 3.3 `ordering` (MUST)

```yaml
ordering:
  sort_by: [timestamp_utc, arrival_seq]
  stable: true
```

### 3.4 `guardrails` (MUST; non-toy)

```yaml
guardrails:
  max_arrivals_per_bucket: 200000
  max_bucket_duration_seconds: 86400
```

---

## 4) Realism floors (MUST; fail closed)

Codex MUST reject authoring if any fail:

* `draws_per_arrival == 1`
* `placement_kind == uniform_within_bucket_v1`
* `timestamp_precision == microsecond`
* `guardrails.max_arrivals_per_bucket >= 5000` (non-toy capacity)
* `max_bucket_duration_seconds >= 3600` and ≤ 86400

---

## 5) Recommended v1 policy file (copy/paste baseline)

```yaml
policy_id: arrival_time_placement_policy_5B
version: v1.0.0

placement_kind: uniform_within_bucket_v1
interval_semantics: "[start,end)"
timestamp_precision: microsecond
draws_per_arrival: 1

u_mapping:
  uniform_law: open_interval_u64
  u_from_u64: "(x+0.5)/2^64"

offset_quantisation:
  unit: microsecond
  law: floor(u * D_seconds * 1_000_000)
  clamp_end_exclusive: true

ordering:
  sort_by: [timestamp_utc, arrival_seq]
  stable: true

guardrails:
  max_arrivals_per_bucket: 200000
  max_bucket_duration_seconds: 86400
```

---

## 6) Acceptance checklist (Codex MUST enforce)

1. YAML parses; keys exactly as §3; `policy_id` correct; `version` non-placeholder.
2. `draws_per_arrival == 1` and placement kind matches v1 pinned law.
3. Uses microsecond quantisation with end-exclusive clamp.
4. Ordering rules pinned and applied.
5. Guardrails non-toy.
6. No timestamps / digests embedded.

---

