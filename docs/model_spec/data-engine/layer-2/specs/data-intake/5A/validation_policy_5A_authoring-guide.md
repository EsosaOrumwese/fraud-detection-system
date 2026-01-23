# Authoring Guide — `validation_policy_5A` (5A.S5 tolerances + blocking vs warning)

## 0) Purpose

`validation_policy_5A` is the **optional validation-level config** that parameterises **how strict** 5A.S5 is when it re-checks S1–S4 invariants:

* numeric tolerances for:

  * **S2 shape normalisation errors** (Σshape≈1),
  * **S3 weekly sum vs base scale** errors,
  * **S4 overlay-factor bounds + λ≈λ_base×F recomposition**,
  * **S4 λ_scenario range guardrails** (and optional local↔UTC consistency),
* and, critically, **which checks are blocking vs warning**.

**Authority boundary:** this policy adjusts strictness and severity only; it MUST NOT redefine what contracts exist (those come from S1–S4 specs and their policies).

If this policy is **missing**, S5 MUST fall back to safe defaults (strict) and MUST NOT silently skip checks.

---

## 1) File identity (MUST)

* **Artefact ID:** `validation_policy_5A`
* **Path:** `config/layer2/5A/validation/validation_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/validation/validation_policy_5A` *(or equivalent; guide pins the semantics)*
* **Token-less posture:** no timestamps, no digests, no environment metadata (sealed by S0 inventory).

---

## 2) Pinned v1 semantics (decision-free)

### 2.1 Two-tier outcomes per check (MUST)

Each check is parameterised so S5 can produce `PASS/WARN/FAIL`, and then aggregate per-run status and world status accordingly.

v1 uses **two thresholds** for numeric checks:

* **warn threshold** → check status becomes `WARN`
* **fail threshold** → check status becomes `FAIL`

And **blocking rules** decide whether a `WARN` can still allow the run/world to be considered “PASS”. (S5 explicitly allows non-blocking warnings.)

### 2.2 Hard bounds still come from modelling policies (MUST)

This policy may set **warning corridors**, but **hard bounds** still come from:

* `scenario_overlay_policy_5A` clamp bounds (`min_factor`, `max_factor`) for overlay factors,
* `baseline_intensity_policy_5A` hard limits for baseline λ / weekly volumes (if present).

S5 must treat out-of-bounds (per those upstream authorities) as **FAIL**, regardless of warning tiers.

### 2.3 Deterministic sampling for recomposition checks (MUST)

S5’s recomposition check (“recompute small sample of λ and confirm ≈ λ_base×F”) MUST be deterministic and RNG-free.

v1 pins a deterministic **min-hash top-N** sampler (§6.3).

---

## 3) Required top-level structure (fields-strict)

Top-level YAML object MUST contain **exactly**:

1. `policy_id` (MUST be `validation_policy_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `tolerances` (object; §4)
4. `bounds` (object; §5)
5. `sampling` (object; §6)
6. `blocking` (object; §7)
7. `notes` (string; optional)

No extra keys.

---

## 4) `tolerances` (MUST)

### 4.1 S2 shape normalisation (MUST)

Applies to S5 checks of S2’s invariant `|Σ_k shape_value − 1| ≤ ε`.

Required keys:

* `s2_shape_sum_abs_warn`
* `s2_shape_sum_abs_fail`

Pinned interpretation:

* If `max_abs_err ≤ warn` → `PASS`
* Else if `max_abs_err ≤ fail` → `WARN`
* Else → `FAIL`

### 4.2 S3 weekly sum vs base scale (MUST)

Applies to S5’s re-check of the weekly-sum invariant when it exists.

Required keys:

* `s3_weekly_sum_rel_fail`
* `s3_weekly_sum_abs_fail`
* `s3_rel_denominator_floor`

Pinned interpretation:

Let `sum_local = Σ_k λ_base_local(k)` and `scale = weekly_volume_expected` (or policy-defined scale field).

* `abs_err = |sum_local - scale|`
* `rel_err = abs_err / max(|scale|, s3_rel_denominator_floor)`
* Fail iff: `abs_err > s3_weekly_sum_abs_fail AND rel_err > s3_weekly_sum_rel_fail`

*(Both must exceed to avoid “scale≈0” pathologies.)*

### 4.3 S4 recomposition tolerance (MUST)

Applies when overlay factors are materialised and S5 checks:
`λ_scenario ≈ λ_base × overlay_factor_total` on a deterministic sample.

Required keys:

* `s4_recompose_rel_fail`
* `s4_recompose_abs_fail`
* `s4_recompose_rel_denominator_floor`

Pinned interpretation:
For each sampled row:

* `abs_err = |λ_scenario - (λ_base×F)|`
* `rel_err = abs_err / max(|λ_scenario|, s4_recompose_rel_denominator_floor)`
  Fail the check if any sampled row violates both thresholds:
* `abs_err > abs_fail AND rel_err > rel_fail`

### 4.4 Optional local↔UTC consistency (OPTIONAL)

Only used if `merchant_zone_scenario_utc_5A` exists and S5 chooses to validate it.

If present, require keys:

* `s4_local_vs_utc_total_rel_fail`
* `s4_local_vs_utc_total_abs_fail`

Pinned meaning: compare total intensity aggregated over the horizon (appropriately aligned) and fail if both abs+rel exceed thresholds.

---

## 5) `bounds` (MUST)

### 5.1 Overlay factor warning corridor (MUST)

Hard bounds still come from `scenario_overlay_policy_5A` (`min_factor/max_factor`), but this policy defines a warn corridor inside that.

Required keys:

* `overlay_factor_min_warn`
* `overlay_factor_max_warn`
* `overlay_low_warn_exempt_types` (list; MUST include `OUTAGE` in v1 to avoid flagging expected shutdown behaviour)

### 5.2 Scenario λ guardrails (MUST)

S4 requires `lambda_local_scenario ≥ 0` and finite, but S5 is allowed to enforce an additional “absurd spike” guardrail because the validation policy explicitly mentions λ_scenario ranges.

Required keys:

* `lambda_scenario_max_per_bucket_warn`
* `lambda_scenario_max_per_bucket_fail`

Pinned meaning:

* if `max(lambda_local_scenario)` exceeds warn → check WARN (unless blocking rules make it fatal)
* if it exceeds fail → check FAIL

*(These are guardrails; they must be non-toy. In v1 authoring, derive them deterministically from baseline hard limits × overlay max_factor; §8.)*

---

## 6) `sampling` (MUST)

S5 must be able to validate recomposition without scanning+joining every row (scale), but it must remain deterministic.

Required keys:

* `recompose_sample_mode` (MUST be `minhash_top_n_v1`)
* `recompose_sample_n` (int; non-toy; recommended 2048)
* `recompose_hash_law` (string; MUST be exactly pinned below)

Pinned `recompose_hash_law` (string literal):

* `hash64 = uint64_be(SHA256("5A.S5.recompose|" + manifest_fingerprint + "|" + parameter_hash + "|" + scenario_id + "|" + merchant_id + "|" + zone_key + "|" + horizon_bucket_key)[0:8])`

Pinned selection semantics:

* compute `hash64` per candidate row,
* keep the **N rows with smallest hash64** (tie-break by full primary key lexicographic).

`zone_key` is the canonical zone representation you use in S3/S4 keys (e.g. `country_iso|tzid` or `zone_id`).

---

## 7) `blocking` (MUST)

S5’s aggregation requires distinguishing blocking vs non-blocking checks.

Required keys:

* `blocking_check_ids` (list of strings)
* `nonblocking_check_ids` (list of strings)
* `warn_is_blocking_check_ids` (list of strings; may be empty)
* `unknown_check_id_posture` (enum; v1 MUST be `fail_closed`)

Pinned meaning:

* Any check_id not listed in either list is treated according to `unknown_check_id_posture`.
* If a check’s status is `WARN` and its id is in `warn_is_blocking_check_ids`, the world MUST NOT be considered PASS.

### 7.1 v1 recommended check IDs (minimal set)

These align to the S5 procedure outline (presence checks + numeric checks).

Recommended **blocking**:

* `S0_PRESENT`, `S0_DIGEST_MATCH`, `UPSTREAM_ALL_PASS`
* `S1_PRESENT`, `S1_PK_VALID`, `S1_REQUIRED_FIELDS`, `S1_SCALE_NONNEG_FINITE`
* `S2_PRESENT`, `S2_GRID_VALID`, `S2_SHAPES_NONNEG`, `S2_SHAPES_SUM_TO_ONE`, `S2_DOMAIN_COVERS_S1`
* `S3_PRESENT`, `S3_DOMAIN_PARITY`, `S3_LAMBDA_NONNEG_FINITE`, `S3_WEEKLY_SUM_VS_SCALE`
* `S4_PRESENT`, `S4_DOMAIN_PARITY`, `S4_HORIZON_COVERAGE`, `S4_LAMBDA_NONNEG_FINITE`, `S4_OVERLAY_FACTOR_HARD_BOUNDS`

Recommended **non-blocking**:

* `S4_OVERLAY_FACTOR_WARN_BOUNDS`
* `S4_RECOMPOSITION_SAMPLE`
* `S4_LAMBDA_SCENARIO_GUARDRAIL`
* `S4_LOCAL_VS_UTC_TOTAL` *(only if UTC outputs exist)*

---

## 8) Realism floors (MUST; fail-closed)

Codex MUST reject authoring if any fail:

1. **Non-toy tolerances**

   * `s2_shape_sum_abs_fail ∈ [1e-9, 1e-4]` (recommended `1e-5`)
   * `s3_weekly_sum_rel_fail ∈ [1e-9, 1e-4]` (recommended `1e-6`)
2. **Recomposition tolerance sanity**

   * `s4_recompose_rel_fail ∈ [1e-9, 1e-4]`
   * `recompose_sample_n ≥ 512`
3. **Overlay warn bounds inside hard bounds**

   * `overlay_factor_min_warn ≥ scenario_overlay_policy_5A.combination.min_factor`
   * `overlay_factor_max_warn ≤ scenario_overlay_policy_5A.combination.max_factor`
4. **Guardrails non-toy**

   * `lambda_scenario_max_per_bucket_fail ≥ 1e6` (avoid toy caps)
5. **Blocking lists are non-empty** and disjoint; `unknown_check_id_posture == fail_closed`

---

## 9) Deterministic authoring algorithm (Codex-no-input)

1. Read:

   * `baseline_intensity_policy_5A` for recommended tolerances + hard limits,
   * `scenario_overlay_policy_5A` for hard factor bounds.
2. Set:

   * `s2_shape_sum_abs_warn = baseline.shape_sum_abs_tol` (recommended `1e-6`)
   * `s2_shape_sum_abs_fail = 10 × warn` (cap at `1e-5` in v1)
3. Set weekly-sum tolerances:

   * `s3_weekly_sum_rel_fail = baseline.weekly_sum_rel_tol` (recommended `1e-6`)
   * `s3_weekly_sum_abs_fail = baseline.weekly_sum_rel_tol` (same order for numeric stability)
   * `s3_rel_denominator_floor = 1.0`
4. Set recomposition tolerances:

   * `s4_recompose_rel_fail = 1e-6`
   * `s4_recompose_abs_fail = 1e-6`
   * `s4_recompose_rel_denominator_floor = 1.0`
5. Set overlay warn corridor:

   * `overlay_factor_min_warn = 0.20`
   * `overlay_factor_max_warn = 0.70 × max_factor` (so 3.5 when max_factor=5.0)
   * `overlay_low_warn_exempt_types = [OUTAGE]`
6. Set λ_scenario guardrails deterministically:

   * `lambda_scenario_max_per_bucket_fail = baseline.hard_limits.max_lambda_per_bucket × max_factor`
   * `lambda_scenario_max_per_bucket_warn = 0.4 × fail`
7. Set sampling:

   * `recompose_sample_mode = minhash_top_n_v1`
   * `recompose_sample_n = 2048`
   * `recompose_hash_law` exactly as pinned in §6
8. Populate blocking lists per §7.1.

---

## 10) Recommended v1 file (copy/paste)

```yaml
policy_id: validation_policy_5A
version: v1.0.0

tolerances:
  s2_shape_sum_abs_warn: 0.000001
  s2_shape_sum_abs_fail: 0.000010

  s3_weekly_sum_rel_fail: 0.000001
  s3_weekly_sum_abs_fail: 0.000001
  s3_rel_denominator_floor: 1.0

  s4_recompose_rel_fail: 0.000001
  s4_recompose_abs_fail: 0.000001
  s4_recompose_rel_denominator_floor: 1.0

bounds:
  overlay_factor_min_warn: 0.20
  overlay_factor_max_warn: 3.50
  overlay_low_warn_exempt_types: [OUTAGE]

  lambda_scenario_max_per_bucket_warn: 10000000.0
  lambda_scenario_max_per_bucket_fail: 25000000.0

sampling:
  recompose_sample_mode: minhash_top_n_v1
  recompose_sample_n: 2048
  recompose_hash_law: 'hash64 = uint64_be(SHA256("5A.S5.recompose|" + manifest_fingerprint + "|" + parameter_hash + "|" + scenario_id + "|" + merchant_id + "|" + zone_key + "|" + horizon_bucket_key)[0:8])'

blocking:
  blocking_check_ids:
    - S0_PRESENT
    - S0_DIGEST_MATCH
    - UPSTREAM_ALL_PASS
    - S1_PRESENT
    - S1_PK_VALID
    - S1_REQUIRED_FIELDS
    - S1_SCALE_NONNEG_FINITE
    - S2_PRESENT
    - S2_GRID_VALID
    - S2_SHAPES_NONNEG
    - S2_SHAPES_SUM_TO_ONE
    - S2_DOMAIN_COVERS_S1
    - S3_PRESENT
    - S3_DOMAIN_PARITY
    - S3_LAMBDA_NONNEG_FINITE
    - S3_WEEKLY_SUM_VS_SCALE
    - S4_PRESENT
    - S4_DOMAIN_PARITY
    - S4_HORIZON_COVERAGE
    - S4_LAMBDA_NONNEG_FINITE
    - S4_OVERLAY_FACTOR_HARD_BOUNDS
  nonblocking_check_ids:
    - S4_OVERLAY_FACTOR_WARN_BOUNDS
    - S4_RECOMPOSITION_SAMPLE
    - S4_LAMBDA_SCENARIO_GUARDRAIL
    - S4_LOCAL_VS_UTC_TOTAL
  warn_is_blocking_check_ids: []
  unknown_check_id_posture: fail_closed

notes: "S5 validation strictness knobs (tolerances, warn corridors, blocking vs warning). Token-less; sealed by S0."
```

---

## 11) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; top-level keys exactly as §3.
2. Tolerances/bounds satisfy realism floors (§8).
3. `overlay_factor_*_warn` are inside overlay policy hard bounds.
4. `recompose_hash_law` matches the pinned string exactly.
5. Blocking/nonblocking lists disjoint; `unknown_check_id_posture == fail_closed`.
6. Token-less posture: no timestamps/digests in-file.
