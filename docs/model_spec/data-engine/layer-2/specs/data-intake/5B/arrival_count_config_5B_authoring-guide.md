# Authoring Guide — `arrival_count_config_5B` (5B.S3 bucket count law from λ_realised)

## 0) Purpose

`arrival_count_config_5B` is the **sealed authority** that tells 5B.S3 how to turn realised bucket intensities:

* `λ_realised(m, zone, bucket_index)`  *(expected arrivals in that horizon bucket)*

into integer bucket counts:

* `N(m, zone, bucket_index) ∈ {0,1,2,...}`

It must be:

* deterministic in semantics,
* non-toy (produces realistic overdispersion where needed),
* fail-closed (no silent fallbacks),
* and compatible with `arrival_rng_policy_5B` budgets (Poisson uses 1 u; NB uses 2 u).

---

## 1) File identity (MUST)

* **Artefact ID:** `arrival_count_config_5B`
* **Path:** `config/layer2/5B/arrival_count_config_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/arrival_count_config_5B` *(permissive; this guide pins real structure)*
* **Token-less posture:** do **not** embed file digests; S0 sealing inventory is authoritative.

---

## 2) Pinned v1 semantics (decision-free)

### 2.1 Units (MUST)

`λ_realised` is interpreted as **expected arrivals per horizon bucket** (not a rate per second).

S3 MUST NOT re-scale λ by bucket duration.

### 2.2 Count law IDs (v1 pinned)

v1 supports exactly two `count_law_id` values:

* `poisson`
* `nb2`  *(NB2: variance = μ + μ²/κ)*

Any other value ⇒ FAIL CLOSED.

### 2.3 Deterministic zero rule (MUST)

If `λ_realised ≤ lambda_zero_eps`, S3 MUST set `N = 0` deterministically and MUST NOT emit an RNG event for this bucket.

### 2.4 Poisson law (1 uniform) (MUST)

If `count_law_id == poisson` and `λ > lambda_zero_eps`:

* S3 MUST consume exactly **1** open-interval uniform `u` from the `bucket_count` family.
* It MUST generate `N ~ Poisson(λ)` using the v1 pinned inversion method:

**Pinned inversion method (v1):**

* Let `L = exp(-λ)`
* Initialize: `k=0`, `p=1`
* While `p > L`:

  * draw `u_k ∈ (0,1)` (each iteration consumes 1 uniform)
  * set `p = p * u_k`
  * increment `k`
* Return `N = k-1`

But this uses variable numbers of uniforms, which conflicts with `arrival_rng_policy_5B` fixed draw budgets.

So v1 instead pins a **fixed-uniform Poisson approximation**:

**Pinned v1 Poisson sampler (1-u):**

* Use a bounded one-uniform sampler with a pinned switch:

  * If `lambda <= poisson_exact_lambda_max`:
    - exact CDF recursion with cap `poisson_n_cap_exact`
  * Else:
    - normal approximation with continuity correction (pinned), still using the same single uniform `u`.

Exact CDF recursion (for lambda small/moderate):

* `u in (0,1)`
* initialize `n = 0`, `p = exp(-lambda)`, `cdf = p`
* while `cdf < u` and `n < poisson_n_cap_exact`:
  - `n = n + 1`
  - `p = p * lambda / n`
  - `cdf = cdf + p`
* if `cdf < u` after the cap, set `n = max_count_per_bucket` and flag `capped=true`

Normal approximation (for lambda large):

* `z = normal_icdf_erfinv_v1(u)` where `normal_icdf_erfinv_v1(u) = sqrt(2) * erfinv(2u - 1)` using the deterministic libm profile
* `n = floor(lambda + sqrt(lambda) * z + 0.5)`
* clamp `n` into `[0, max_count_per_bucket]`; if clamped, set `capped=true`

This consumes exactly **1** uniform, matching the RNG policy.

### 2.5 NB2 law (2 uniforms) (MUST)

If `count_law_id == nb2` and `λ > lambda_zero_eps`:

NB2 is sampled as Poisson-Gamma mixture:

* mean `μ = λ`
* dispersion parameter `kappa > 0` controls variance:

  * `Var[N] = μ + μ^2 / kappa`

Sampling steps (v1 pinned to 2 uniforms total):

1. Draw `u1, u2 ∈ (0,1)` (exactly 2)
2. Convert to a Gamma draw deterministically using pinned method `gamma_shape_rate_v1`:

   * `shape = kappa`
   * `rate  = kappa / μ`  (so mean of Gamma = μ)
3. Let `Λ ~ Gamma(shape, rate)`
4. Draw `N ~ Poisson(Λ)` using the **same 1-u CDF inversion** but reusing `u2` (no extra draws).
   *(i.e., u2 is the Poisson inversion uniform; u1 is the gamma uniform.)*

This keeps total draws = 2 and matches `arrival_rng_policy_5B`.

> Note: This "single-uniform gamma" is an approximation. That's acceptable for v1 as long as it's pinned and validated. If you want exact gamma, you'd need variable draws and a policy version bump.

**Pinned gamma_one_u_approx_v1 mapping (MUST):**
Given `u1 in (0,1)` and desired `Gamma(shape=kappa, rate=kappa/mu)`:

* approximate `Gamma(shape=kappa, scale=mu/kappa)` by a lognormal moment-match:
  - `sigma2 = log(1 + 1/kappa)`  (requires kappa > 0)
  - `m = log(mu) - 0.5 * sigma2`
  - `Z = normal_icdf_erfinv_v1(u1)` where `normal_icdf_erfinv_v1(u) = sqrt(2) * erfinv(2u - 1)`
  - set `Lambda = exp(m + sqrt(sigma2) * Z)`

This yields positive `Lambda` with mean approximately `mu` and variance controlled by `kappa` (v1 approximation).

### 2.6 Kappa law (deterministic per group) (MUST)

If `count_law_id == nb2`, S3 must compute `kappa` deterministically per group using group features already present from S1 grouping.

---

## 3) Required file structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `arrival_count_config_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `count_law_id` (enum: `poisson|nb2`)
4. `lambda_zero_eps` (number ≥ 0)
5. `max_count_per_bucket` (int ≥ 1)
6. `poisson_sampler` (object)
7. `nb2` (object; required only if `count_law_id == nb2`)
8. `realism_floors` (object)

### 3.1 `poisson_sampler` (MUST)

```yaml
poisson_sampler:
  kind: cdf_inversion_one_u_bounded_v1
  p0_law: exp_minus_lambda
  recurrence: p_next = p * lambda / (n+1)
  poisson_exact_lambda_max: 50.0
  poisson_n_cap_exact: 200000
  normal_icdf: erfinv_v1
```

### 3.2 `nb2` (MUST if nb2)

```yaml
nb2:
  kappa_law:
    base_by_scenario_band: { baseline: 30.0, stress: 12.0 }
    class_multipliers: { ... every demand_class ... }
    kappa_bounds: [2.0, 200.0]
  gamma_sampler:
    kind: gamma_one_u_approx_v1
    shape: kappa
    rate: kappa_over_mu
  poisson_on_gamma:
    kind: cdf_inversion_reuse_u2_v1
```

### 3.3 `realism_floors` (MUST)

```yaml
realism_floors:
  max_count_per_bucket_min: 5000
  lambda_zero_eps_max: 0.000001
  require_kappa_distinct_values_min: 3
```

---

## 4) Realism floors (MUST; fail closed)

Codex MUST reject authoring if any fail:

* `lambda_zero_eps ≤ 1e-6`
* `max_count_per_bucket ≥ 5000` (prevents toy caps)
* `poisson_exact_lambda_max > 0`
* `poisson_n_cap_exact >= max_count_per_bucket`
* If `count_law_id == nb2`:

  * `kappa_bounds` within `[1, 1000]`
  * at least 3 distinct `kappa` values appear across groups in baseline scenario
  * median `kappa` in baseline within `[10, 80]` (non-toy dispersion)

---

## 5) Deterministic authoring algorithm (Codex-no-input)

### Step A — choose count law (v1 pinned)

* Baseline v1 recommendation: `count_law_id = nb2` (more realistic arrival overdispersion).
* If you want pure Poisson, that’s allowed but tends to look too “smooth”.

### Step B — populate kappa multipliers (if nb2)

Use a pinned table keyed by `demand_class` (must cover all classes):

Example for the standard 10 classes:

* `office_hours`: 1.10
* `consumer_daytime`: 1.00
* `evening_weekend`: 0.90
* `always_on_local`: 1.05
* `online_24h`: 0.85
* `online_bursty`: 0.40
* `travel_hospitality`: 0.80
* `fuel_convenience`: 0.95
* `bills_utilities`: 1.20
* `low_volume_tail`: 0.60

Pinned meaning: lower multiplier → lower kappa → higher variance.

### Step C — set global guardrails

* `lambda_zero_eps = 1e-9`
* `max_count_per_bucket = 200000` (non-toy; prevents runaway memory in S4)

### Step D — validate against the actual realised λ preview (optional but recommended)

Without consuming RNG, S3 can preview the λ distribution from S2 outputs and ensure:

* `max λ_realised` isn’t so large that `max_count_per_bucket` is constantly hit.

If it is, the fix is to adjust upstream scale/clips, not to silently lower caps.

---

## 6) Recommended v1 file (copy/paste baseline)

```yaml
policy_id: arrival_count_config_5B
version: v1.0.0

count_law_id: nb2
lambda_zero_eps: 0.000000001
max_count_per_bucket: 200000

poisson_sampler:
  kind: cdf_inversion_one_u_bounded_v1
  p0_law: exp_minus_lambda
  recurrence: p_next = p * lambda / (n+1)
  poisson_exact_lambda_max: 50.0
  poisson_n_cap_exact: 200000
  normal_icdf: erfinv_v1

nb2:
  kappa_law:
    base_by_scenario_band: { baseline: 30.0, stress: 12.0 }
    class_multipliers:
      office_hours: 1.10
      consumer_daytime: 1.00
      evening_weekend: 0.90
      always_on_local: 1.05
      online_24h: 0.85
      online_bursty: 0.40
      travel_hospitality: 0.80
      fuel_convenience: 0.95
      bills_utilities: 1.20
      low_volume_tail: 0.60
    kappa_bounds: [2.0, 200.0]
  gamma_sampler:
    kind: gamma_one_u_approx_v1
    shape: kappa
    rate: kappa_over_mu
  poisson_on_gamma:
    kind: cdf_inversion_reuse_u2_v1

realism_floors:
  max_count_per_bucket_min: 5000
  lambda_zero_eps_max: 0.000001
  require_kappa_distinct_values_min: 3
```

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; keys exactly as §3.
2. `count_law_id` in `{poisson, nb2}`.
3. `lambda_zero_eps` and `max_count_per_bucket` meet realism floors.
4. If `nb2`: class multipliers cover all demand_class values; kappa bounds sane.
5. Sampling budgets align with `arrival_rng_policy_5B`:

   * Poisson uses 1 u
   * NB2 uses 2 u (u1 for gamma approx, u2 for Poisson inversion)
6. Deterministic zero rule enforced (no RNG emitted when λ≈0).
7. Poisson sampler settings are bounded (`poisson_n_cap_exact >= max_count_per_bucket`).
8. No timestamps / digests embedded.

---
