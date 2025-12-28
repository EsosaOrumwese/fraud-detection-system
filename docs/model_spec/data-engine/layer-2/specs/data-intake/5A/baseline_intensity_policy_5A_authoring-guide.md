# Authoring Guide — `baseline_intensity_policy_5A` (S3 baseline λ semantics)

## 0) Purpose

This policy pins **exactly how** 5A.S3 turns:

* S1 base scale fields (e.g., `weekly_volume_expected`), and
* S2 unit-mass weekly shapes (`shape_value[k]`)

into baseline expected arrivals per local-week bucket:

* `λ_base_local(m,zone,k)`

It exists so S3 **cannot** invent units, normalisation, clipping, or zero-handling “on the fly”.

---

## 1) File identity (MUST)

* **Artefact ID:** `baseline_intensity_policy_5A`
* **Path:** `config/layer2/5A/policy/baseline_intensity_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/baseline_intensity_policy_5A`
* **Token-less posture:** do **not** embed any digest in the file (S0 sealing inventory is authoritative)

---

## 2) Pinned v1 semantics (decision-free)

### 2.1 Scale source (MUST)

v1 MUST set:

* `scale_source_field = weekly_volume_expected`
* `scale_units = arrivals_per_local_week`

Meaning:

* for each `(m,zone)` the weekly constraint is authoritative:

  * `Σ_k λ_base_local(m,zone,k) ≈ weekly_volume_expected(m,zone)`

### 2.2 Shape contract (MUST)

S2 shapes are treated as **unit-mass templates** over the local-week grid:

* `shape_value[k] ≥ 0`
* `Σ_k shape_value[k] = 1` within tolerance `shape_sum_abs_tol`

S3 MUST NOT “reshape” templates—only sanity check them.

### 2.3 Baseline construction (MUST)

For each `(m,zone)`:

* If `weekly_volume_expected == 0`:
  `λ_base_local[k] = 0` for all k.

* Else:
  `λ_base_local[k] = weekly_volume_expected * shape_value[k]`

### 2.4 Clipping / transforms (MUST be pinned; v1 recommendation = fail-closed)

Clipping is allowed only if the policy pins **exactly** what happens.

v1 recommended posture:

* `clip_mode = hard_fail`
* If any `λ_base_local[k]` violates bounds, S3 **ABORTS** (no silent clipping).

(If you later want clipping, make it explicit: `clip_and_renormalise_v1`, with a fully defined algorithm. Don’t leave it “implementation-defined”.)

### 2.5 Units of λ (MUST)

v1 pins:

* `lambda_units_local = expected_arrivals_per_local_week_bucket`

I.e., λ is a **count per bucket**, not a continuous rate.

---

## 3) Required file structure (fields-strict as authored)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `baseline_intensity_policy_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `scale_source_field` (MUST be `weekly_volume_expected`)
4. `scale_units` (MUST be `arrivals_per_local_week`)
5. `lambda_units_local` (MUST be `expected_arrivals_per_local_week_bucket`)
6. `shape_sum_abs_tol` (number)
7. `weekly_sum_rel_tol` (number)
8. `clip_mode` (enum; v1 allows exactly: `hard_fail`)
9. `hard_limits` (object)
10. `utc_projection` (object)

### 3.1 `hard_limits` (MUST)

* `max_lambda_per_bucket` (number > 0)
* `max_weekly_volume_expected` (number > 0)

Pinned meaning:

* If `weekly_volume_expected > max_weekly_volume_expected` → ABORT
* If any computed `λ_base_local[k] > max_lambda_per_bucket` → ABORT

### 3.2 `utc_projection` (MUST)

* `emit_utc_baseline` (bool)

Pinned meaning:

* If false: S3 emits only local baselines.
* If true: S3 may additionally emit `merchant_zone_baseline_utc_5A` using the **scenario horizon grid** and the same civil-time mapping law used elsewhere in 5A (fail-closed if mapping isn’t total).
  *(No other knobs in v1—keep UTC projection deterministic and constrained.)*

---

## 4) Realism floors (MUST; prevents toy configs)

Codex MUST reject authoring if any fail:

* `shape_sum_abs_tol` in `[1e-9, 1e-5]`
* `weekly_sum_rel_tol` in `[1e-9, 1e-4]`
* `clip_mode == hard_fail` (v1)
* `max_weekly_volume_expected ≥ 1e5` (don’t cap the world at toy volumes)
* `max_lambda_per_bucket ≥ 1e3` (avoid flattening by tiny caps)
* `version` not placeholder-like (`test`, `example`, `todo`, etc.)

---

## 5) Recommended v1 production file (copy/paste)

```yaml
policy_id: baseline_intensity_policy_5A
version: v1.0.0

scale_source_field: weekly_volume_expected
scale_units: arrivals_per_local_week
lambda_units_local: expected_arrivals_per_local_week_bucket

shape_sum_abs_tol: 0.000001
weekly_sum_rel_tol: 0.000001

clip_mode: hard_fail

hard_limits:
  max_lambda_per_bucket: 5000000.0
  max_weekly_volume_expected: 50000000.0

utc_projection:
  emit_utc_baseline: false
```

---

## 6) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Keys are exactly those in §3; `policy_id` and `version` valid.
3. Scale semantics pinned (`weekly_volume_expected` + arrivals/week).
4. Tolerances within realism floors.
5. Hard limits are present and non-toy.
6. No timestamps / generated fields.

---
