# Authoring Guide — `scenario_overlay_validation_policy_5A` (5A.S4 numeric bounds + warning thresholds for overlay factors)

## 0) Purpose

`scenario_overlay_validation_policy_5A` is an **optional** S4 companion config that defines:

* **numeric bounds** and/or **warning thresholds** for `overlay_factor_total` (and optionally per-type factors), and
* what counts as a **numeric violation** vs a **warning-only** condition.

S4 explicitly calls this out as an optional overlay-related config that can influence “what counts as a numeric violation.”
S4 also defines a fatal failure mode when overlay factors violate configured numeric constraints (`S4_INTENSITY_NUMERIC_INVALID`).
And S4’s run-report can emit `overlay_factor_violations_count` “if such thresholds exist (e.g. > F_max_warn).”

---

## 1) File identity (MUST)

* **Artefact ID:** `scenario_overlay_validation_policy_5A`
* **Path:** `config/layer2/5A/scenario/scenario_overlay_validation_policy_5A.v1.yaml`
* **Token-less posture:** no timestamps/digests in-file; sealing inventory is authoritative.

---

## 2) Authority boundaries (MUST)

This policy MUST NOT redefine:

* how events map to factors, combination law, or clamp range (`min_factor`, `max_factor`) — that is owned by `scenario_overlay_policy_5A`.
* event vocabulary or per-event amplitude bounds — also owned by `scenario_overlay_policy_5A`.

This policy MAY define:

* **warning thresholds** (e.g. `F_max_warn`) tighter than the hard clamp range,
* **how many warnings are tolerated** before failing,
* aggregate “sanity invariants” (e.g. mean/p95 bounds per scenario class) that S4 may enforce as *optional added checks*.

---

## 3) Pinned v1 semantics (decision-free)

### 3.1 What is validated

Validation targets the **computed overlay factor surface** S4 produces over domain×horizon:

* `overlay_factor_total(m,z[,ch],h)` (always), and optionally
* per-type factors such as `factor_holiday`, `factor_payday`, … if you materialise them.

### 3.2 Hard bounds source

Hard bounds MUST be sourced from `scenario_overlay_policy_5A.combination.min_factor/max_factor` (the clamp range).

### 3.3 Warnings vs failure

v1 supports two severities:

* `WARN` → S4 may still PASS, but must report `overlay_factor_violations_count` and summary stats.
* `FAIL` → S4 MUST abort with `S4_INTENSITY_NUMERIC_INVALID`.

### 3.4 Outage exception posture (MUST be explicit)

Because outage factors can be very low (e.g. 0.05) per overlay policy/calendar conventions, warn-lows must support an explicit exception path.

---

## 4) Required payload shape (fields-strict)

Top-level YAML keys MUST be exactly:

1. `policy_id` (MUST be `scenario_overlay_validation_policy_5A`)
2. `version` (e.g. `v1.0.0`)
3. `numeric` (object; §5)
4. `warnings` (object; §6)
5. `gating` (object; §7)
6. `notes` (string; optional)

No extra keys.

---

## 5) `numeric` (MUST)

### Required keys

* `finite_required` (bool; MUST be `true`)
* `nonnegative_required` (bool; MUST be `true`)
* `hard_bounds_source` (string; MUST be `scenario_overlay_policy_5A.combination`)
* `comparison_epsilon` (number; MUST be > 0; recommended `1e-12`)

Semantics:

* Any `NaN/Inf` or negative factor is **FAIL** (fatal).
* Any factor outside the overlay policy hard bounds (with epsilon) is **FAIL**.

---

## 6) `warnings` (MUST)

### 6.1 Total-factor warn thresholds (MUST)

* `warn_bounds_total` object:

  * `min_warn` (number ≥ 0)
  * `max_warn` (number > 0)
  * `apply_to` (string; MUST be `overlay_factor_total`)
  * `exceptions` (object; §6.2)

Definition:

* A warn-violation occurs when `overlay_factor_total < min_warn` or `> max_warn`, *after applying exceptions*.
* S4 counts these into `overlay_factor_violations_count` for run-report.

### 6.2 Exceptions (MUST)

`exceptions` MUST include an explicit outage posture:

* `suppress_low_warn_when_type_active` (list of event types)

  * v1 MUST include: `[OUTAGE]`

This avoids treating outage-driven low factors as “unexpected,” while still allowing you to warn on extreme uplifts.

*(If you don’t materialise per-type factors, “type active” may be derived from S4’s internal active-event surfaces; it must still be deterministic and sealed-input driven.)*

### 6.3 Optional aggregate warnings (OPTIONAL)

If present, `aggregate_warn_checks` is a list of rules that apply per `(scenario_id)`:

Each rule:

* `name`
* `selector` (e.g. `{scenario_type: baseline}` / `{scenario_type: stress}`)
* `metric` (enum: `mean`, `p95`, `max`)
* `bounds` (`[min,max]` with null allowed on either side)

This aligns with S4’s allowance for “optional added checks” (e.g., mean-factor boundaries for baseline vs stress).

---

## 7) `gating` (MUST)

Defines when warnings become fatal.

Required keys:

* `warn_violation_is_fatal` (bool; v1 recommended `false`)
* `max_warn_violations_fraction_fail` (number in `[0,1]`)
* `max_warn_violations_fraction_warn` (number in `[0,1]`)
* `fraction_denominator` (string; MUST be `domain_horizon_points`)

  * i.e. denominator is total count of `(m,z[,ch],h)` points validated.

Semantics:

* If warn fraction ≥ `..._fail` → treat as **FAIL** (`S4_INTENSITY_NUMERIC_INVALID`).
* Else if warn fraction ≥ `..._warn` → keep PASS but must report the count and fractions.

---

## 8) Deterministic authoring algorithm (Codex-no-input)

1. Read `scenario_overlay_policy_5A` to get:

   * `max_factor` / `min_factor` (hard bounds).
2. Set:

   * `comparison_epsilon = 1e-12`
   * `finite_required = true`, `nonnegative_required = true`
3. Choose warn bounds (v1 recommended, derived from the hard max):

   * `max_warn = 0.70 * max_factor` (e.g. `3.5` when `max_factor=5.0`)
   * `min_warn = 0.20`
4. Set exceptions:

   * `suppress_low_warn_when_type_active = [OUTAGE]`
5. Set gating:

   * `warn_violation_is_fatal = false`
   * `max_warn_violations_fraction_warn = 0.001`  (0.1% of points)
   * `max_warn_violations_fraction_fail = 0.01`   (1% of points)
6. (Optional) Add aggregate checks by scenario_type if you have stable scenario typing (baseline vs stress).

---

## 9) Recommended v1 example (copy/paste)

```yaml
policy_id: scenario_overlay_validation_policy_5A
version: v1.0.0

numeric:
  finite_required: true
  nonnegative_required: true
  hard_bounds_source: scenario_overlay_policy_5A.combination
  comparison_epsilon: 1.0e-12

warnings:
  warn_bounds_total:
    apply_to: overlay_factor_total
    min_warn: 0.20
    max_warn: 3.50
    exceptions:
      suppress_low_warn_when_type_active: [OUTAGE]

  aggregate_warn_checks:
    - name: baseline_mean_factor_reasonable
      selector: { scenario_type: baseline }
      metric: mean
      bounds: [0.85, 1.25]
    - name: stress_p95_not_extreme
      selector: { scenario_type: stress }
      metric: p95
      bounds: [null, 3.50]

gating:
  warn_violation_is_fatal: false
  max_warn_violations_fraction_warn: 0.001
  max_warn_violations_fraction_fail: 0.01
  fraction_denominator: domain_horizon_points

notes: "Optional numeric warning thresholds for S4 overlays; hard bounds come from scenario_overlay_policy_5A clamp."
```

---

## 10) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; top-level keys exactly as §4.
2. `policy_id` matches exactly; `version` non-placeholder.
3. `comparison_epsilon > 0`.
4. `warn_bounds_total.max_warn` MUST be ≤ overlay policy `max_factor`; `min_warn` MUST be ≥ overlay policy `min_factor`.
5. `suppress_low_warn_when_type_active` includes `OUTAGE`.
6. `max_warn_violations_fraction_warn ≤ ..._fail` and both in `[0,1]`.
7. Token-less posture satisfied.

