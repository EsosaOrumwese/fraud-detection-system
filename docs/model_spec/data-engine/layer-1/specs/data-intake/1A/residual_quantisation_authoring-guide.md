## Authoring Guide — `config/layer1/1A/numeric/residual_quantisation.yaml` (Residual quantisation & tie-break policy)

### 0) Purpose (Binding)

This file pins the **numeric law for residual handling** used in deterministic allocation steps (notably “largest remainder” / Hamilton-style integerisation). It exists to ensure that:

* residuals are quantised to a fixed decimal precision before sorting,
* sorting ties are resolved deterministically,
* and downstream allocations are reproducible across platforms.

This policy is **not** about model RNG; it is about **RNG-free determinism**.

---

## 1) Identity & location (Binding)

* **Path:** `config/layer1/1A/numeric/residual_quantisation.yaml`
* **Type:** authored numeric policy/config
* **Lineage:** bytes MUST participate in `parameter_hash` whenever any consumer state uses residual sorting / largest-remainder allocation.

---

## 2) Required top-level structure (Binding)

Top-level keys MUST be exactly:

* `semver` (string)
* `version` (string; `YYYY-MM-DD`)
* `dp_resid` (integer)
* `rounding` (string)
* `sort` (object)
* `tiebreak` (object)
* `validation` (object)

Reject unknown keys and duplicate keys.

---

## 3) Semantics (Binding)

### 3.1 Residual quantisation

Given a real residual `r` (binary64), compute the quantised residual:

* `r_q = round_to_dp(r, dp_resid)` under the specified rounding mode.

**Required rounding mode for v1:**

* IEEE-754 binary64 rounding: **RNE** (round-to-nearest, ties-to-even)

### 3.2 Residual sorting direction

In largest remainder allocation, you typically:

* compute floor allocation,
* compute residuals,
* then assign remaining +1 units to the **largest residuals**.

This policy pins how “largest residual” is defined and sorted.

---

## 4) `sort` and `tiebreak` (Binding)

### 4.1 Required `sort` fields

```yaml
sort:
  primary_key: "residual_desc"
  stable: true
```

Meaning:

* primary sort is `residual_q` descending
* sort must be stable

### 4.2 Required `tiebreak` fields

```yaml
tiebreak:
  keys:
    - "country_iso_asc"     # or "candidate_rank_asc" depending on the consumer table
    - "merchant_id_asc"
```

Interpretation:

* If two rows have equal `residual_q`, break ties by deterministic secondary keys.
* The secondary keys chosen must be keys that always exist in the consumer frame.

**Binding:** consumers MUST use `tiebreak.keys` exactly as listed. If any listed key is absent from the consumer frame, hard fail (no silent ignore / no substitution).

---

## 5) `validation` (Binding)

```yaml
validation:
  forbid_nan_inf: true
  residual_domain: [0.0, 1.0]
  enforce_residual_domain: true
```

Meaning:

* If any residual is NaN/Inf → hard fail
* Residuals must lie in [0,1] (or [0,1) depending on your definition; pick one and stick to it)
* If out of domain and `enforce_residual_domain=true` → hard fail

---

## 6) Consumer binding (how states use this)

Any consumer state that uses residual sorting MUST:

* quantise residuals using `dp_resid` and `rounding`
* sort using `sort.primary_key`
* apply `tiebreak.keys` exactly as listed (no consumer override)

### Allowed tiebreak keys (v1 closed set)

* `country_iso_asc`
* `candidate_rank_asc`
* `merchant_id_asc`
* `tile_id_asc`

If the policy lists a tiebreak key that doesn’t exist in the consumer frame → hard fail (don’t silently ignore).

---

## 7) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

This matches the dp=8 discipline you’ve already pinned in 1A integerisation.

```yaml
semver: "1.0.0"
version: "2024-12-31"

# Decimal places used when quantising residuals before sorting
dp_resid: 8

# Rounding law for quantisation
rounding: "RNE"

sort:
  primary_key: "residual_desc"
  stable: true

# Default tie-break sequence; consumer may override only within allowed set
tiebreak:
  keys:
    - "country_iso_asc"
    - "merchant_id_asc"

validation:
  forbid_nan_inf: true
  residual_domain: [0.0, 1.0]
  enforce_residual_domain: true
```

---

## 8) Acceptance checklist (Codex must enforce)

* YAML has no duplicate keys; only allowed top-level keys exist
* `dp_resid` integer in `[0..18]` (recommend cap 18)
* `rounding == "RNE"` for v1
* `tiebreak.keys` is a non-empty list and each entry is in the allowed closed set
* `validation.forbid_nan_inf == true`
* Residual domain is exactly `[0.0, 1.0]` (or whatever you standardise) and is enforced

---

## Non-toy/realism guardrails (MUST)

- `dp` MUST be fixed and tie-break rules MUST be fully deterministic (no locale or floating ordering).
- After quantisation, group sums MUST be exactly 1.0 at dp and numerically within schema tolerances.
- Quantisation MUST NOT collapse all mass to a single country when multiple countries have non-zero pre-weights.

