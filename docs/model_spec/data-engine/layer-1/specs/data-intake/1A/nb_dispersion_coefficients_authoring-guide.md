## Authoring Guide — `nb_dispersion_coefficients.yaml` (Offline-trained NB2 dispersion bundle)

This is the **third model** in the 1A trio. It supplies `beta_phi`, the coefficients used to compute **NB2 dispersion**:

* **Dispersion (“size”)**:
  [
  \phi_m = \exp(\beta_\phi^\top x^{(\phi)}_m) ;>; 0
  ]
* Under NB2, a common parameterization is:
  [
  \mathrm{Var}(N\mid \mu,\phi)=\mu+\frac{\mu^2}{\phi}
  ]
  so **higher φ ⇒ less overdispersion** (more Poisson-like).

This file is produced **offline** and consumed **read-only** at runtime by 1A.S2. Runtime never trains.

---

# 1) Where it must land (binding path)

`config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/nb_dispersion_coefficients.yaml`

Same `version={config_version}` and `{iso8601_timestamp}` scheme as the hurdle export bundle.

---

# 2) What must be inside the YAML (binding keys)

### 2.1 Required keys

* `semver` (string)
* `version` (string; equals `{config_version}`)
* `metadata.simulation_manifest` (string path pointer to the exact training manifest)
* `dict_mcc` (list[int]) — **authoritative order**
* `dict_ch` (list[str]) — must be exactly `["CP","CNP"]`
* `beta_phi` (list[float])

### 2.2 Strongly recommended keys

* `metadata.simulation_config_path`
* `metadata.seed`
* `metadata.created_utc`
* `metadata.inputs` (resolved input paths + digests)
* `design.beta_phi_order` (explicit, see §4)

---

# 3) Inputs the offline trainer MUST pin (manifested)

The training run MUST write a `manifest.json` and this YAML must point to it via `metadata.simulation_manifest`.

That manifest must record (at minimum):

* simulation config path (`config/models/hurdle/hurdle_simulation.priors.yaml`)
* RNG seed
* resolved input references used to build the training corpus:

  * `transaction_schema_merchant_ids`
  * `world_bank_gdp_per_capita` (constant 2015 USD; the source of `gdp_pc_usd_2015`)
  * `gdp_bucket_map` (if used in corpus synthesis)
  * `iso3166_canonical`

**Key requirement for dispersion:** `gdp_pc_usd_2015 > 0` for every home country used in training, because S2 uses `ln(gdp_pc_usd_2015)` in the design.

---

# 4) Runtime design contract (shape + ordering is everything)

### 4.1 Dict compatibility locks (non-negotiable)

**`dict_mcc` MUST be identical (values + order) to the one exported in `hurdle_coefficients.yaml` for the same export run.**
This is how you prevent shape drift between μ and φ in S2.

Best practice (Codex enforced):

* load the already-exported `hurdle_coefficients.yaml` from the same `{config_version}/{timestamp}` and copy:

  * `dict_mcc`
  * `dict_ch`
* hard fail if mismatched.

**`dict_ch` MUST be exactly**:

```yaml
dict_ch: ["CP","CNP"]
```

### 4.2 Feature blocks and coefficient order (binding)

Dispersion design vector:

1. intercept (leading 1)
2. MCC one-hot block in `dict_mcc` order
3. channel one-hot block in `["CP","CNP"]` order
4. `ln_gdp_pc_usd_2015` (single scalar; natural log of home-country GDPpc)

**Coefficient order:**
`beta_phi = [ intercept ] || MCC block || CH block || [beta_ln_gdp]`

**Shape invariant (MUST):**
`len(beta_phi) = 1 + |dict_mcc| + 2 + 1`

---

# 5) Offline training route (the proper route)

This mirrors your existing pipeline, with the dispersion-specific details made explicit.

### Step A — Load simulation priors

* `config/models/hurdle/hurdle_simulation.priors.yaml`
* This config pins:

  * corpus scale and priors
  * regularization weights
  * any caps/floors for moments stability

### Step B — Materialize a synthetic training corpus (and seal it)

Write a run bundle under:
`artefacts/training/1A/hurdle_sim/simulation_version={config_version}/seed={seed}/{iso8601_timestamp}/`

For dispersion you need (at minimum):

* `nb_mean.parquet` containing per-merchant:

  * `merchant_id`
  * `mcc`, `channel`, `home_country_iso`
  * `y_count` (simulated total outlets)
* and the run `manifest.json`

### Step C — Build the dispersion design matrix (deterministic)

Rows correspond to merchants (typically the multi-site subset, but you must document your choice in the manifest).

Features:

* intercept
* MCC dummies
* channel dummies
* `ln_gdp_pc_usd_2015(home_country_iso)`

Dictionary freeze:

* `dict_mcc` and `dict_ch` aligned to the hurdle export (see §4.1).

### Step D — Compute method-of-moments φ targets (cellwise, deterministic)

Your existing approach is the right one:

1. Define grouping cells by:

* `(mcc, channel, gdp_bucket)` **or** `(mcc, channel)` depending on your trainer; both are valid as long as you define it and keep it fixed.

2. For each cell, compute:

* `mean_y` and `var_y` over `y_count` values in that cell.

3. For NB2, a standard MOM estimator is:
   [
   \hat\phi = \frac{\mu^2}{\max(\varepsilon,\ \mathrm{Var}(Y)-\mu)}
   ]
   with `ε > 0` pinned to avoid division by zero.

**Pinned stability rules (Codex enforced):**

* if `Var(Y) <= μ + ε`, set `φ_hat = φ_max` (near-Poisson cell)
* clamp `φ_hat` to `[φ_min, φ_max]` before logging
* define weights per cell as a deterministic function of cell count (e.g., `w = n_cell` or `w = sqrt(n_cell)`)

### Step E — Fit `beta_phi` via weighted ridge on `log(φ_hat)`

Fit a linear model:
[
\log(\hat\phi) \approx \beta_\phi^\top x^{(\phi)}
]
using:

* deterministic weighted ridge solver
* fixed iteration / convergence policy
* single-threaded numerics (no parallel reductions) for stability

### Step F — Export the YAML bundle (atomic write)

Write:
`config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/nb_dispersion_coefficients.yaml`

Include:

* dicts
* `beta_phi`
* `metadata.simulation_manifest` pointing back to the sealed manifest

---

# 6) Acceptance checks (Codex must enforce before publishing)

### 6.1 Structural / compatibility (MUST)

* `dict_ch == ["CP","CNP"]`
* `dict_mcc` matches the paired `hurdle_coefficients.yaml` export exactly (values + order)
* `len(beta_phi) == 1 + |dict_mcc| + 2 + 1`

### 6.2 Numeric sanity (MUST)

Across the training universe:

* `ln_gdp_pc_usd_2015` is finite for every row (requires `gdp_pc_usd_2015 > 0`)
* predicted `phi = exp(ηφ)` is finite and strictly > 0
* no NaN/Inf in predictors or outputs

### 6.3 Behavioural corridor sanity (MUST)

Because S2 rejects draws until `N ≥ 2`, dispersion must not make `P(N ≤ 1)` explode.

Codex must compute, over the same universe used for corpus/design:

* predicted `μ` (from `hurdle_coefficients.beta_mu`)
* predicted `φ` (from `beta_phi`)
* implied `P(N ≤ 1)` under NB2
  and assert the **expected rejection load** stays below your pinned threshold (whatever threshold you use internally today, formalize it here and fail closed if exceeded).

### 6.4 Provenance checks (MUST)

* `metadata.simulation_manifest` exists and records:

  * config path
  * seed
  * resolved input references (including GDP per capita source used for ln)

---

# 7) Minimal YAML structure (shape, not placeholder)

```yaml
semver: "1.0.0"
version: "<config_version>"

metadata:
  simulation_manifest: "<path-to-sealed-manifest.json>"

dict_mcc: [ ...must match hurdle export... ]
dict_ch: ["CP","CNP"]

design:
  beta_phi_order:
    - "intercept"
    - "mcc_onehot(dict_mcc)"
    - "ch_onehot(['CP','CNP'])"
    - "ln_gdp_pc_usd_2015"

beta_phi: [ ...length = 1 + |dict_mcc| + 2 + 1 ... ]
```

---

## Belt-and-braces lock — `hurdle_coefficients.yaml` + `nb_dispersion_coefficients.yaml`

This is a **single post-export validation step** Codex must run after generating both YAML bundles. It is designed to prevent “looks fine in isolation” failures at runtime.

---

# 1) Inputs (must be available)

* The paired exports from the **same** `{config_version}/{iso8601_timestamp}`:

  * `.../hurdle_coefficients.yaml`
  * `.../nb_dispersion_coefficients.yaml`
* The **same reference tables** used in the training manifest (or a pinned “evaluation universe”):

  * `transaction_schema_merchant_ids` (merchant universe)
  * `world_bank_gdp_per_capita` (for ln GDPpc)
  * `gdp_bucket_map` (for GDP bucket dummies in hurdle)
  * `iso3166_canonical` (for ISO validation)

Codex must resolve these from `metadata.simulation_manifest` (not by guessing paths).

---

# 2) Hard compatibility locks (FAIL if any violation)

### 2.1 Dictionary equality (MUST)

* `hurdle.dict_mcc` must equal `dispersion.dict_mcc` **exactly** (same length, same values, same order)
* `hurdle.dict_ch == ["CP","CNP"]`
* `dispersion.dict_ch == ["CP","CNP"]`
* `hurdle.dict_dev5 == [1,2,3,4,5]`

### 2.2 Vector length locks (MUST)

Let `C = len(dict_mcc)`:

* `len(beta)      == 1 + C + 2 + 5`
* `len(beta_mu)   == 1 + C + 2`
* `len(beta_phi)  == 1 + C + 2 + 1`

### 2.3 No unknown feature values (MUST)

On the evaluation universe:

* every merchant MCC must be in `dict_mcc` (else FAIL)
* every channel must be in `{CP,CNP}` (else FAIL)
* every merchant home ISO2 must exist in `iso3166_canonical`
* every home ISO2 must have GDPpc(2024) > 0 (else FAIL)
* every home ISO2 must have a GDP bucket in `gdp_bucket_map_2024` (else FAIL)

---

# 3) Numeric sanity locks (FAIL if any violation)

Across the evaluation universe:

### 3.1 Hurdle π sanity

* compute `π_m = sigmoid(βᵀ x_hurdle(m))`
* FAIL if any π is NaN/Inf
* FAIL if any π is exactly 0 or 1 (saturated)
  *(unless you explicitly allow saturation; v1: disallow)*

### 3.2 Mean μ sanity

* compute `μ_m = exp(βμᵀ x_mu(m))`
* FAIL if any μ is NaN/Inf or μ ≤ 0

### 3.3 Dispersion φ sanity

* compute `φ_m = exp(βφᵀ x_phi(m))`
* FAIL if any φ is NaN/Inf or φ ≤ 0

---

# 4) Behavioural corridor lock (the one that saves you at runtime)

This is the key: it ensures S2’s “reject until N≥2” doesn’t blow up attempts.

For each merchant `m`:

1. Compute NB2 parameter:

* `p_m = φ_m / (φ_m + μ_m)`  (in (0,1))

2. Compute:

* `P0_m = p_m ^ φ_m`
* `P1_m = φ_m * (1 - p_m) * p_m ^ φ_m`
* `p_rej_m = P0_m + P1_m`  (probability a draw yields N ≤ 1)

3. Expected attempts inflation for that merchant in S2:

* `infl_m = 1 / max(1e-12, (1 - p_rej_m))`

4. Weight by hurdle probability (because only multi-site merchants enter S2):

* `w_m = π_m * infl_m`

Compute run-level expected rejection ratio (attempt-weighted):
[
\widehat{\rho}=\frac{\sum_m w_m; p_{\text{rej},m}}{\sum_m w_m}
]

**FAIL if** `ρ̂ > 0.055`

Also FAIL if:

* any `p_rej_m >= 0.25` (merchant-level pathological corridor risk)
* any `infl_m > 1.20` (attempt inflation above 20%)

*(These thresholds are pinned; adjust later only by policy bump.)*

---

# 5) Lightweight realism locks (FAIL if wildly off)

These are not “fit to real data” checks; they’re guardrails to keep the world plausible.

Compute:

* `mean_pi = mean(π_m)`
* `q90_mu = 90th_percentile(μ_m | π_m ≥ 0.5)` *(approx multi-site segment)*

**FAIL if:**

* `mean_pi` not in `[0.05, 0.30]`
* `q90_mu` not in `[3.0, 40.0]`

---

# 6) Output of the lock (must be persisted)

Codex must write an artefact next to the export bundle, e.g.:

`config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/bundle_selfcheck.json`

Containing:

* digests of both YAML files
* dict lengths + vector lengths
* summary stats: `mean_pi`, `q90_mu`, `median_phi`, `rho_hat`, max `infl_m`, max `p_rej_m`
* PASS/FAIL + canonical error code if fail

No PASS → export is considered invalid.

---