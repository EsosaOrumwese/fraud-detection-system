# Authoring Guide — `baseline_validation_policy_5A` (5A.S3 weekly-sum tolerance / numeric acceptance)

## 0) Purpose

`baseline_validation_policy_5A` defines **the tolerance ε** used by 5A.S3 when enforcing the **weekly sum vs base-scale** contract:

[
\left| \sum_{k \in GRID} \lambda_{local_base}(m,z[,ch],k) - base_scale(m,z[,ch]) \right| \le \varepsilon
]

S3’s spec explicitly requires that **ε is defined in a baseline validation policy**.

It is an **optional enhancement** (S3 must still be able to run without it), but when present it becomes the authoritative source of this tolerance.

---

## 1) File identity (MUST)

* **Artefact ID:** `baseline_validation_policy_5A`
* **Path:** `config/layer2/5A/policy/baseline_validation_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/baseline_validation_policy_5A` *(or equivalent in your 5A schema pack)*
* **Token-less posture:** no timestamps, no digests, no “generated_at” (S0 sealing inventory is authoritative).

---

## 2) Authority boundaries (MUST)

* This policy **MUST NOT** redefine:

  * which S1 field is “base scale”,
  * the units/meaning of base scale,
  * clipping/renormalisation rules.
* Those belong to `baseline_intensity_policy_5A` (if present) and the S3 spec’s pinned semantics.
* This policy **ONLY** controls **how strict** the weekly-sum check is (ε definition) and (optionally) how relative error is computed for diagnostics.

---

## 3) Pinned v1 semantics (decision-free)

### 3.1 What it applies to (MUST)

v1 applies when S3’s baseline semantics are “expected arrivals per local week” (the common v1 case: `weekly_volume_expected`).

If you later support other semantics (e.g. `scale_factor`), do it as **v2** with an explicit alternative contract (the S3 spec requires the contract to be defined by policy if semantics differ).

### 3.2 ε model (MUST)

Define ε as a deterministic function of `base_scale`:

* Let:

  * `abs_epsilon` (≥ 0)
  * `rel_epsilon` (≥ 0)
  * `rel_denominator_floor` (> 0)

* Define:

```text
denom = max(|base_scale|, rel_denominator_floor)
epsilon(base_scale) = max(abs_epsilon, rel_epsilon * denom)
```

* S3 passes the weekly-sum check iff:

```text
abs_err = |sum_local - base_scale|
abs_err <= epsilon(base_scale)
```

This matches the spec’s “≤ ε” requirement while still letting you express both absolute and relative tolerance robustly.

### 3.3 Relative error law (MUST; for metrics/diagnostics)

Pin the reporting law used in metrics like “weekly_sum_relative_error_max”:

```text
rel_err = abs_err / max(|base_scale|, rel_denominator_floor)
```

(So `base_scale≈0` doesn’t explode.)

### 3.4 Failure posture (MUST)

If the check fails for any `(m,z[,ch])`, S3 MUST treat it as **numeric invalid** and fail the state without committing canonical outputs.

---

## 4) Required file structure (fields-strict)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `baseline_validation_policy_5A`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `weekly_sum_contract` (object)
4. `notes` (string; optional)

`weekly_sum_contract` MUST contain:

* `applies_to_scale_units` (MUST be `arrivals_per_local_week`)
* `abs_epsilon` (number ≥ 0)
* `rel_epsilon` (number ≥ 0)
* `rel_denominator_floor` (number > 0)
* `epsilon_law` (string; MUST match §3.2)
* `relative_error_law` (string; MUST match §3.3)

No extra keys.

---

## 5) Realism floors (MUST; prevents toy configs)

Codex MUST reject authoring if any fail:

* `rel_epsilon` in `[1e-9, 1e-4]` (align with your existing baseline tolerance guidance). 
* `abs_epsilon` in `[0, 1e-3]` *(v1 expectation: errors should be rounding-level; do not “permit” big drift)*
* `rel_denominator_floor == 1.0` (v1 pinned)
* `version` not placeholder-like (`test`, `example`, `todo`, …)

---

## 6) Deterministic authoring algorithm (Codex-no-input)

1. If `baseline_intensity_policy_5A` exists and contains `weekly_sum_rel_tol`, set:

   * `rel_epsilon = weekly_sum_rel_tol` (keeps the system consistent during the transition).
2. Else set `rel_epsilon = 1e-6` (v1 safe default).
3. Set:

   * `rel_denominator_floor = 1.0`
   * `abs_epsilon = rel_epsilon * rel_denominator_floor`  *(so ε is never below the implied relative floor)*
4. Write the law strings exactly as in §3.2–§3.3.
5. Run the acceptance checklist (§8).

---

## 7) Recommended v1 production file (copy/paste)

```yaml
policy_id: baseline_validation_policy_5A
version: v1.0.0

weekly_sum_contract:
  applies_to_scale_units: arrivals_per_local_week

  abs_epsilon: 0.000001
  rel_epsilon: 0.000001
  rel_denominator_floor: 1.0

  epsilon_law: "epsilon=max(abs_epsilon, rel_epsilon*max(|base_scale|, rel_denominator_floor))"
  relative_error_law: "rel_err=|sum_local-base_scale|/max(|base_scale|, rel_denominator_floor)"

notes: "Defines ε for S3 weekly-sum vs base-scale enforcement; token-less."
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Top-level keys are exactly `{policy_id, version, weekly_sum_contract, notes?}`.
3. `policy_id` matches exactly; `version` non-placeholder.
4. `weekly_sum_contract.applies_to_scale_units == arrivals_per_local_week`.
5. `abs_epsilon ≥ 0`, `rel_epsilon ≥ 0`, `rel_denominator_floor > 0`.
6. Realism floors pass.
7. Law strings match pinned definitions.
8. No timestamps / digests / environment metadata.

---

### Small alignment note (so you don’t get drift later)

Right now your `baseline_intensity_policy_5A` guide also carries tolerance fields like `weekly_sum_rel_tol`.
To avoid contradictions, treat `baseline_validation_policy_5A` as **the authority** for ε when it exists (per S3), and keep the values consistent until you consolidate the tolerance knobs into one home.
