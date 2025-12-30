# Authoring Guide — `arrival_lgcp_config_5B` (5B.S2 latent intensity model, v1)

## 0) Purpose

`arrival_lgcp_config_5B` is the **sealed authority** for 5B.S2 that pins:

* whether a latent field is used (`none` vs LGCP),
* the **time-correlation law** over horizon buckets (OU/AR(1) vs IID),
* how to compute per-group hyperparameters (σ, ℓ) deterministically,
* the **latent→factor** transform (including mean-correction),
* and clipping guardrails so `λ_realised` is realistic and safe.

It must be deterministic (RNG lives only in `arrival_rng_policy_5B`) and strong enough that S2 cannot invent semantics.

---

## 1) File identity (MUST)

* **Artefact ID:** `arrival_lgcp_config_5B`
* **Path:** `config/layer2/5B/arrival_lgcp_config_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/arrival_lgcp_config_5B` *(permissive; this guide pins real structure)*
* **Token-less posture:** do **not** embed file digests/timestamps (S0 sealing inventory handles digests).

---

## 2) Pinned v1 semantics (decision-free)

### 2.1 Latent model switch

* `latent_model_id ∈ { none, log_gaussian_ou_v1, log_gaussian_iid_v1 }`

Rules:

* If `none`: S2 MUST emit **no** `latent_vector` RNG events and MUST set `λ_realised = λ_target` (subject only to `lambda_max` if you choose to enforce it).
* If `log_gaussian_*`: S2 MUST emit exactly **one** `latent_vector` RNG event per `(scenario_id, group_id)`.

### 2.2 Latent field dimensionality (v1 pinned)

* `latent_dims = H` where `H = #horizon buckets` from `s1_time_grid_5B`.
* One latent value per horizon bucket per group.

### 2.3 Gaussian process law (v1 pinned options)

**A) OU / AR(1) on buckets (`log_gaussian_ou_v1`)**
For a given group, with parameters `(sigma, length_scale_buckets=L)`:

* `phi = exp(-1 / L)`  (L > 0)
* Draw `Z_0 ~ Normal(0, sigma^2)`
* For t=1..H-1:

  * `eps_t ~ Normal(0, sigma^2 * (1 - phi^2))`
  * `Z_t = phi * Z_{t-1} + eps_t`

**B) IID log-Gaussian (`log_gaussian_iid_v1`)**

* For each t: `Z_t ~ Normal(0, sigma^2)` independent.

### 2.4 Latent → multiplicative factor (v1 pinned)

Default (recommended) is **mean-one lognormal** so expected intensity stays anchored to 5A:

* `log_factor_t = Z_t - 0.5 * sigma^2`
* `factor_t = exp(log_factor_t)`  (so `E[factor_t] = 1`)

Then:

* `λ_realised = λ_target * factor_t`

### 2.5 Clipping / guardrails (v1 pinned)

Apply factor clipping deterministically:

* `factor_t = clamp(factor_t, min_factor, max_factor)`
* `λ_realised = λ_target * factor_t`
* optionally cap absolute lambda:

  * `λ_realised = min(λ_realised, lambda_max)` if `lambda_max_enabled=true`

No NaNs, no infs, no negatives; any violation ⇒ fail closed (S2 abort).

### 2.6 Diagnostics toggle

* If `emit_latent_field_diagnostic=true`, S2 MUST write `s2_latent_field_5B`.
* Else it MUST NOT write it.

---

## 3) Required file structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `arrival_lgcp_config_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `latent_model_id` (enum; §2.1)
4. `normal_method` (MUST be `box_muller_u2`)
5. `latent_dims_mode` (MUST be `horizon_buckets_H`)
6. `kernel` (object; §3.1)
7. `hyperparam_law` (object; §3.2)
8. `latent_transform` (object; §3.3)
9. `clipping` (object; §3.4)
10. `diagnostics` (object; §3.5)
11. `realism_floors` (object; §4)

### 3.1 `kernel` (MUST)

```yaml
kernel:
  kind: ou_ar1_buckets_v1 | iid_v1
  length_scale_buckets_bounds: [2.0, 168.0]
```

Rules:

* If `latent_model_id == log_gaussian_ou_v1`, then `kernel.kind` MUST be `ou_ar1_buckets_v1`.
* If `latent_model_id == log_gaussian_iid_v1`, then `kernel.kind` MUST be `iid_v1`.
* Bounds are hard guardrails used to clamp derived length-scales.

### 3.2 `hyperparam_law` (MUST; deterministic per-group)

```yaml
hyperparam_law:
  group_feature_sources:
    scenario_band: from_s1_time_grid_flags     # baseline|stress
    demand_class: from_5A_labels
    channel_group: from_5A_labels
    virtual_band: from_5A_or_3B_labels         # physical|virtual
    zone_group_id: from_grouping_policy        # zgXX (optional)
  sigma:
    base_by_scenario_band: { baseline: 0.25, stress: 0.40 }
    class_multipliers: { ... all demand_class ... }
    channel_multipliers: { card_present: 1.00, card_not_present: 1.10, mixed: 1.05 }
    virtual_multipliers: { physical: 1.00, virtual: 1.15 }
    sigma_bounds: [0.05, 1.20]
  length_scale_buckets:
    base_by_scenario_band: { baseline: 24.0, stress: 12.0 }
    class_multipliers: { ... all demand_class ... }
    length_scale_bounds: [2.0, 168.0]
```

Pinned computation per group:

* `sigma_g = clamp( base_band * class_mult * channel_mult * virtual_mult, sigma_bounds )`
* `L_g = clamp( base_band_L * class_mult_L, length_scale_bounds )`

No other group features allowed in v1.

### 3.3 `latent_transform` (MUST)

```yaml
latent_transform:
  kind: exp_mean_one_v1
  mean_correction: subtract_half_sigma2
```

Pinned meaning: `factor = exp(Z - 0.5*sigma^2)`.

### 3.4 `clipping` (MUST)

```yaml
clipping:
  min_factor: 0.20
  max_factor: 5.00
  lambda_max_enabled: true
  lambda_max: 1000000000.0
```

### 3.5 `diagnostics` (MUST)

```yaml
diagnostics:
  emit_latent_field_diagnostic: false
```

---

## 4) Realism floors (MUST; fail-closed)

Codex MUST reject authoring (or S2 must abort at runtime) if any fail:

1. **Non-toy heterogeneity**

* At least **3 distinct** `sigma_g` values occur across groups (baseline scenario), and
* At least **10%** of groups have `sigma_g ≥ 0.35` in stress scenarios (if stress exists).

2. **Reasonable correlation**

* For OU: median `length_scale_buckets` in baseline must be within `[8, 72]` (not “almost IID”, not “almost constant”).

3. **Mean anchored**

* `latent_transform.kind == exp_mean_one_v1` in v1 (prevents uncontrolled drift).

4. **Clip range non-toy**

* `max_factor / min_factor ≥ 10`
* `max_factor ≥ 3.0`
* `min_factor ≤ 0.5`

5. **Class coverage**

* `hyperparam_law.sigma.class_multipliers` and `length_scale_buckets.class_multipliers` must cover **every demand_class** in `merchant_class_policy_5A`. Missing any ⇒ fail closed.

---

## 5) Deterministic authoring algorithm (Codex-no-input)

Codex writes this config by:

1. Read class catalog from `merchant_class_policy_5A` (must match exactly).
2. Populate `sigma.class_multipliers` and `length_scale.class_multipliers` using a pinned v1 table (below).
3. Keep channel/virtual multipliers as pinned defaults.
4. Keep transform as `exp_mean_one_v1`.
5. Validate realism floors by simulating group hyperparams from `s1_grouping_5B` (no RNG needed).

### v1 pinned class multipliers (example; must cover all classes)

For the common 10-class taxonomy:

* `office_hours`: sigma 0.85, L 1.20
* `consumer_daytime`: sigma 1.00, L 1.00
* `evening_weekend`: sigma 1.05, L 0.95
* `always_on_local`: sigma 0.95, L 1.10
* `online_24h`: sigma 1.10, L 0.90
* `online_bursty`: sigma 1.60, L 0.50
* `travel_hospitality`: sigma 1.15, L 0.80
* `fuel_convenience`: sigma 1.05, L 0.85
* `bills_utilities`: sigma 0.90, L 1.10
* `low_volume_tail`: sigma 1.25, L 0.70

*(If your class catalog differs, Codex must FAIL CLOSED until you extend this table.)*

---

## 6) Recommended v1 config (copy/paste baseline)

```yaml
policy_id: arrival_lgcp_config_5B
version: v1.0.0

latent_model_id: log_gaussian_ou_v1
normal_method: box_muller_u2
latent_dims_mode: horizon_buckets_H

kernel:
  kind: ou_ar1_buckets_v1
  length_scale_buckets_bounds: [2.0, 168.0]

hyperparam_law:
  group_feature_sources:
    scenario_band: from_s1_time_grid_flags
    demand_class: from_5A_labels
    channel_group: from_5A_labels
    virtual_band: from_5A_or_3B_labels
    zone_group_id: from_grouping_policy

  sigma:
    base_by_scenario_band: { baseline: 0.25, stress: 0.40 }
    class_multipliers:
      office_hours: 0.85
      consumer_daytime: 1.00
      evening_weekend: 1.05
      always_on_local: 0.95
      online_24h: 1.10
      online_bursty: 1.60
      travel_hospitality: 1.15
      fuel_convenience: 1.05
      bills_utilities: 0.90
      low_volume_tail: 1.25
    channel_multipliers: { card_present: 1.00, card_not_present: 1.10, mixed: 1.05 }
    virtual_multipliers: { physical: 1.00, virtual: 1.15 }
    sigma_bounds: [0.05, 1.20]

  length_scale_buckets:
    base_by_scenario_band: { baseline: 24.0, stress: 12.0 }
    class_multipliers:
      office_hours: 1.20
      consumer_daytime: 1.00
      evening_weekend: 0.95
      always_on_local: 1.10
      online_24h: 0.90
      online_bursty: 0.50
      travel_hospitality: 0.80
      fuel_convenience: 0.85
      bills_utilities: 1.10
      low_volume_tail: 0.70
    length_scale_bounds: [2.0, 168.0]

latent_transform:
  kind: exp_mean_one_v1
  mean_correction: subtract_half_sigma2

clipping:
  min_factor: 0.20
  max_factor: 5.00
  lambda_max_enabled: true
  lambda_max: 1000000000.0

diagnostics:
  emit_latent_field_diagnostic: false

realism_floors:
  require_sigma_distinct_values_min: 3
  require_stress_sigma_ge_fraction: 0.10
  require_baseline_median_L_bounds: [8.0, 72.0]
  require_transform_kind: exp_mean_one_v1
```

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; top-level keys exactly as §3.
2. `latent_model_id` is valid and consistent with `kernel.kind`.
3. `normal_method == box_muller_u2` and latent dims are `H`.
4. Class multiplier maps cover every demand_class (no missing).
5. Derived group hyperparameters (from actual `s1_grouping_5B`) satisfy realism floors.
6. Clip bounds non-toy and sane.
7. No timestamps / generated-at fields in the config.

---

## Placeholder resolution (MUST)

- Replace placeholder kernel parameters with final values (variance, length-scale, correlation).
- Replace any example group overrides with the actual grouping rules.

