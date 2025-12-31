# Authoring Guide — `config/allocation/ccy_smoothing_params.yaml` (S5 blending + smoothing + fixed-dp output)

This file is **required** by **1A.S5**. It governs how the two ingress share surfaces:

* `ccy_country_shares_2024Q4` (currency-area priors)
* `settlement_shares_2024Q4` (settlement concentration)

…are blended and smoothed into the **single authority** output:

* `ccy_country_weights_cache` (parameter-scoped)

Changing this file **must flip `parameter_hash`** (it is a governed parameter input).

---

### Realism bar (MUST)

This policy controls whether currency-to-country weights look like the real world or like a toy. Before sealing defaults, you MUST:

* Calibrate `blend_weight` / `alpha` / `obs_floor` / `shrink_exponent` so the output is neither nearly-uniform nor dominated by noise.
* Provide `per_currency` overrides for major multi-country currencies where a single global default is not credible (e.g., shared-currency areas with very uneven member sizes).
* Validate that the output weight distributions look plausible for a small audit sample of major currencies (top shares sensible; long tail present; sum=1 at dp).

---

## 1) File identity

* **Artefact id:** `ccy_smoothing_params`
* **Path:** `config/allocation/ccy_smoothing_params.yaml`
* **Type:** policy/config (authored; not hunted)
* **Hashing:** SHA-256 over exact bytes (no YAML normalisation)

---

## 2) Required top-level structure

The YAML **MUST contain exactly** these top-level keys (no extras):

* `semver` : string (`MAJOR.MINOR.PATCH`)
* `version` : string (`YYYY-MM-DD`)
* `dp` : int in `[0, 18]` (fixed decimals for OUTPUT weights)
* `defaults` : object (required)
* `per_currency` : object (optional)
* `overrides` : object (optional)

**Fail closed** on:

* unknown keys
* duplicate keys
* out-of-domain values

---

## 3) `defaults` block (required)

`defaults` MUST contain:

* `blend_weight` : `w ∈ [0,1]`
  Interpretation: `q = w·s_ccy + (1−w)·s_settle`

* `alpha` : `≥ 0`
  Additive Dirichlet α per ISO (applied as α[c])

* `obs_floor` : integer `≥ 0`
  Minimum effective evidence mass

* `min_share` : `∈ [0,1]`
  Post-smoothing floor per ISO (applied before renormalisation)

* `shrink_exponent` : `≥ 0`
  Used to shrink large evidence masses:
  `N_eff = max(obs_floor, N0^(1/max(shrink_exponent, 1)))`
  (Values `< 1` are treated as `1` at evaluation time.)

---

## 4) Currency overrides and ISO overrides

### 4.1 Override precedence (deterministic)

For any quantity **Q** at currency `cur` and ISO `iso` (where ISO overrides are permitted):

1. ISO override: `overrides.<Q>_iso[cur][iso]` (if defined for Q), else
2. Currency override: `per_currency[cur].<Q>`, else
3. Global default: `defaults.<Q>`

If a required Q cannot be resolved → **hard FAIL**.

### 4.2 What can be overridden

* Currency-level only: `blend_weight`, `obs_floor`, `shrink_exponent`
* Currency + ISO overrides allowed: `alpha`, `min_share`

### 4.3 `per_currency` (optional)

If present: map ISO-4217 currency code (uppercase) → object containing any subset of:

* `blend_weight`, `alpha`, `obs_floor`, `min_share`, `shrink_exponent`

Reject unknown fields inside each currency block.

**Currency universe guard (MUST):** every currency key in `per_currency` MUST exist in the input currency universe
used by S5, i.e. it MUST appear in `ccy_country_shares_2024Q4.currency` (and therefore be eligible to produce rows in
`ccy_country_weights_cache`). If any `per_currency` key is absent from that universe, FAIL CLOSED (do not ignore it).

### 4.4 `overrides` (optional)

If present, it may contain **only**:

* `alpha_iso: { <CCY>: { <ISO2>: number ≥ 0 } }`
* `min_share_iso: { <CCY>: { <ISO2>: number ∈ [0,1] } }`

All ISO2 keys must be uppercase and FK-valid to `iso3166_canonical_2024`.
**Feasibility guard:** for any currency with ISO floors, must hold:
`Σ min_share_iso[cur][*] ≤ 1.0` else **hard FAIL**.

---

### 4.5 Placeholder resolution (MUST)

The angle-bracket tokens in the override examples are literal placeholders. Replace them with:

* `<CCY>`: ISO-4217 alpha-3 currency code present in `ccy_country_shares_2024Q4.currency`.
* `<ISO2>`: ISO-3166-1 alpha-2 country code present in `iso3166_canonical_2024`.
* `<Q>`: one of the allowed quantity names in this section (exact field names only).

Do not introduce new field names or currencies outside the input currency universe.

---

## 5) S5 algorithm semantics this policy controls

For each currency `cur` and each country `c` in the **union** country set from both input share surfaces:

1. **Blend shares**
   `q[c] = w·s_ccy[c] + (1−w)·s_settle[c]`

2. **Blend evidence mass**
   `N0 = w·Σ n_ccy + (1−w)·Σ n_settle` (per currency)

3. **Shrink + floor evidence**
   `N_eff = max(obs_floor, N0^(1/max(shrink_exponent, 1)))`

4. **Dirichlet smoothing**
   `posterior[c] = (q[c]·N_eff + α[c]) / (N_eff + Σ α)`

5. **Apply minimum shares**
   `p′[c] = max(posterior[c], min_share_for_c)`

6. **Renormalise**
   `p[c] = p′[c] / Σ p′`

7. **Quantise to fixed dp and force Σ=1 at dp**

* Let `u[c] = round_half_even(10^dp · p[c])` (integer ULPs)
* Let `T = 10^dp`, `S = Σ u[c]`

  * If `S < T`: add `T−S` one-ULP increments to countries ordered by **descending** remainder `r[c]=frac(10^dp·p[c])`, tie-break `country_iso` A→Z
  * If `S > T`: subtract `S−T` one-ULP from countries ordered by **ascending** remainder, tie-break `country_iso` Z→A
* Persist `weight[c] = u[c] / 10^dp` as numeric

---

## 6) Minimal v1 file (Codex can author verbatim)

```yaml
semver: "1.0.0"
version: "2024-12-31"

# Fixed decimals for OUTPUT weights in ccy_country_weights_cache.weight
dp: 8

defaults:
  # w in q[c] = w*s_ccy + (1-w)*s_settle
  blend_weight: 0.60

  # Dirichlet alpha per ISO (applied uniformly unless overridden)
  alpha: 0.50

  # Minimum effective mass after shrink
  obs_floor: 1000

  # Post-smoothing floor per ISO (keep 0 unless you have a strong reason)
  min_share: 0.0

  # Shrink large evidence masses: N_eff = max(obs_floor, N0^(1/max(shrink_exponent,1)))
  shrink_exponent: 2.0

# Optional in schema, but v1 includes minimal overrides for major multi-country currencies (realism bar).
per_currency:
  EUR:
    blend_weight: 0.75
    alpha: 0.30
    obs_floor: 2000
    shrink_exponent: 2.0
  XOF:
    blend_weight: 0.70
    alpha: 0.35
  XAF:
    blend_weight: 0.70
    alpha: 0.35
  XCD:
    blend_weight: 0.70
    alpha: 0.35

# Optional; omit entirely if unused
overrides: {}
```

---

## 7) Acceptance checklist (Codex must enforce)

* YAML has **no duplicate keys**
* Top-level keys are exactly the allowed set
* `dp ∈ [0,18]`
* `defaults` contains all five required fields with correct domains
* `per_currency` currency keys are uppercase ISO-4217
* For every `cur` in `per_currency`, verify `cur ∈ distinct(ccy_country_shares_2024Q4.currency)`; else **hard FAIL**
* `overrides` contains only `alpha_iso` / `min_share_iso`
* For any currency with `min_share_iso`, verify feasibility `Σ floors ≤ 1.0`
* Deterministic quantisation rules (half-even + residual fixup) are implemented exactly
* Output weights are non-degenerate for major currencies (not flat-uniform, not single-country collapse unless the currency is truly single-country in the input surfaces).
