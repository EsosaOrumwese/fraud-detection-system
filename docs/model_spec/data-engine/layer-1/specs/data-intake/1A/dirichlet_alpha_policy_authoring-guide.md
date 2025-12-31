## Authoring Guide — `config/models/allocation/dirichlet_alpha_policy.yaml` (Dirichlet α policy for country-share sampling)

### 0) Purpose (Binding)

This file defines the **Dirichlet concentration parameters** used when the engine runs any **Dirichlet-based share sampling** lane (e.g., country-allocation shares prior to integerisation).

It exists to make the Dirichlet behaviour:

* **deterministic in configuration** (policy pinned → hash changes)
* **stable across runs** (same inputs → same α vectors)
* **explicitly auditable** (no “magic constants” in code)

If the Dirichlet lane is disabled, this policy may be present but is **not consumed**.

---

## 1) Identity & location (Binding)

* **Path:** `config/models/allocation/dirichlet_alpha_policy.yaml`
* **Type:** authored policy/config (not hunted)
* **Lineage:** bytes MUST participate in `parameter_hash` whenever this file is **opened**. The engine MUST only open/consume this file when `enabled=true`; if `enabled=false`, the lane is disabled and this file must not be opened/claimed as consumed.

---

## 2) Required top-level structure (Binding)

Top-level keys MUST be exactly:

* `semver` (string)
* `version` (string; `YYYY-MM-DD`)
* `enabled` (bool)
* `alpha_model` (object)
* `bounds` (object)
* `fallback` (object)

Reject unknown keys and duplicate keys.

---

## 3) Semantics (Binding)

### 3.1 What the policy produces

For each merchant `m` and its legal country set `C_m` (home + selected foreign), the policy must produce a vector:

* `α_m = { α(m,c) : c ∈ C_m }`, with **α(m,c) > 0**

The Dirichlet draw is then:

* `p_m ~ Dirichlet(α_m)`
  and `p_m` is later used for allocation (before deterministic integerisation).

### 3.2 Determinism law

Given the same:

* candidate set `C_m` (same order authority),
* weights/priors used as base shares (if used),
* and this policy file,

the computed `α_m` MUST be identical bit-for-bit under your numeric law (binary64/RNE).

---

## 4) `alpha_model` (how α is constructed)

### 4.1 Required fields

```yaml
alpha_model:
  kind: "scaled_base_shares" | "uniform"
  total_concentration: <number > 0>
  base_share_source: "base_weight_priors" | "ccy_country_weights_cache" | "uniform"
  include_home_boost: <bool>
  home_boost_multiplier: <number >= 1.0>
```

### 4.1.1 Placeholder resolution (MUST)

Replace the angle-bracket tokens as follows:

* `<number > 0>`: a finite float strictly greater than zero.
* `<number >= 1.0>`: a finite float greater than or equal to 1.0.
* `<bool>`: `true` or `false` (YAML boolean).

Do not introduce additional keys without a semver bump.

### 4.2 Model kinds

#### A) `uniform`

* For `M = |C_m|`: set `α(m,c) = total_concentration / M` for all `c`.

Use when you want “pure randomness around uniform”.

#### B) `scaled_base_shares` (recommended)

1. Obtain base shares `s(m,c)` from the chosen `base_share_source`:

   * `base_weight_priors`: use S3’s prior weights normalised over `C_m`
   * `ccy_country_weights_cache`: use S5 weights when currency-driven allocation is used
   * `uniform`: same as uniform shares
2. Apply optional home boost:

   * if `include_home_boost=true`, multiply `s(m,home)` by `home_boost_multiplier`, then renormalise `s`.
3. Scale into α:

   * `α(m,c) = total_concentration * s(m,c)`

This yields: higher concentration → less randomness; lower concentration → more randomness.

---

## 5) `bounds` (safety clamps)

Required fields:

```yaml
bounds:
  alpha_min: <number > 0>
  alpha_max: <number > alpha_min>
```

After computing `α(m,c)`, clamp:

* `α = min(alpha_max, max(alpha_min, α))`

Then renormalise to preserve total concentration:

* `α ← α * (total_concentration / Σ α)`

---

## 6) `fallback` behaviour (fail closed vs safe default)

Required fields:

```yaml
fallback:
  on_missing_base_shares: "fail" | "uniform"
  on_nonfinite_alpha: "fail"
```

Rules:

* If base shares cannot be constructed (missing inputs), apply `on_missing_base_shares`.
* Any NaN/Inf at any stage MUST trigger `on_nonfinite_alpha` (v1: fail).

---

## 7) Minimal v1 file (Codex can author verbatim)

This is a sane “realistic” configuration: it uses base shares and adds controlled randomness.

```yaml
semver: "1.0.0"
version: "2024-12-31"

# Feature flag: if false, engine must not consume this file.
enabled: true

alpha_model:
  kind: "scaled_base_shares"
  # Total concentration controls randomness: ~30 gives mild variation around base shares.
  total_concentration: 30.0
  # Prefer S3 base weights when they exist, otherwise fall back.
  base_share_source: "base_weight_priors"
  include_home_boost: true
  home_boost_multiplier: 1.25

bounds:
  alpha_min: 0.05
  alpha_max: 200.0

fallback:
  on_missing_base_shares: "uniform"
  on_nonfinite_alpha: "fail"
```

---

## 8) Acceptance checklist (Codex must enforce)

* YAML validates:

  * required keys present
  * no unknown keys / no duplicates
* `enabled` boolean
* `total_concentration > 0`
* `home_boost_multiplier >= 1.0`
* `alpha_min > 0` and `alpha_max > alpha_min`
* For a test grid of `(M=|C|)` values, α is positive, finite, and sums to `total_concentration` after renormalisation.
* If `enabled=false`, engine MUST treat the policy as **not consumed** (no effect on lineage or behaviour).

---

## Non-toy/realism guardrails (MUST)

- Ensure `total_concentration` yields non-degenerate draws for typical |C_m| (not near-delta, not near-uniform by clamp).
- Require `alpha_min < alpha_max` and verify <10% of entries are clamped on a sample run; otherwise fail closed.
- If `include_home_boost=true`, keep `home_boost_multiplier` bounded so home share does not exceed ~0.95 for most multi-country merchants.
- If `base_share_source` is `base_weight_priors` or `ccy_country_weights_cache`, fail closed when any country in C_m has missing or zero weight.

