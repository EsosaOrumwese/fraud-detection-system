# Authoring Guide — `hurdle_simulation.priors.yaml` (Offline corpus priors for 1A GLMs)

## 1) Purpose and contract

This file defines the **synthetic ground-truth priors** used to materialise the training corpus for the 3 fitted models:

1. **Hurdle (logistic)**: `is_multi ~ Bernoulli(π)`
2. **NB mean**: `μ = E[N | is_multi]`
3. **Dispersion**: `φ` for NB2 variance

It must be:

* deterministic given `{algorithm, seed}` and pinned inputs
* realistic enough that fitted coefficients produce sensible runtime behaviour
* explicit about **clamps** and **noise** to prevent pathological training data

### 1.1 Contract status (offline-only)

`hurdle_simulation.priors.yaml` is an **offline training input**, not a sealed engine artefact.

* **Pinned path:** `config/models/hurdle/hurdle_simulation.priors.yaml`
* **Contract note:** do **not** register this file as a runtime sealed input; it exists only to build the training corpus and coefficient bundles.

---

## 2) Inputs the training run must already have (read-only)

The simulation uses *realistic covariates* from your pinned reference universe:

* `transaction_schema_merchant_ids` (merchant_id, mcc, channel, home_country_iso)
* `world_bank_gdp_per_capita` (to get `gdp_pc_usd_2015` and `ln_gdp_pc`)
* `gdp_bucket_map_2024` (GDP bucket 1..5)

This file does **not** define those datasets; it defines how to use them.

---

## 3) Required top-level keys (strict; fail closed)

```yaml
semver: "<MAJOR.MINOR.PATCH>"
version: "<YYYY-MM-DD>"

rng:
  algorithm: "philox2x64-10"
  seed: <uint64>

# Required (but can be "disabled" deterministically):
calibration: { ... }   # set enabled=false to bypass
noise: { ... }         # set sds to 0.0 to remove stochasticity
clamps: { ... }        # always required (keeps corpus corridor-safe)

hurdle: { ... }
nb_mean: { ... }
dispersion: { ... }
```

### 3.1 Placeholder resolution (MUST)

Replace the angle-bracket tokens in the snippet with concrete values:

* `<MAJOR.MINOR.PATCH>`: semantic version for the priors file (e.g., `1.0.0`).
* `<YYYY-MM-DD>`: release date label for the priors file.
* `<uint64>`: RNG seed as an unsigned integer in `[0, 2^64-1]`.

Use finite numeric values for any inline `<float>` placeholders later in the file; do not leave placeholders in a sealed priors file.

Reject unknown top-level keys (fail closed).

---

## 4) Model semantics (what each block means)

### 4.1 Hurdle block (logistic prior)

For merchant *m*:

* `logit(π_m) = base_logit + channel_offset + bucket_offset + mcc_offset + ε_logit`
* `is_multi ~ Bernoulli( clamp_pi( sigmoid(logit(π_m)) ) )`

**Required keys**

* `base_logit`
* `channel_offsets` (CP, CNP)
* `bucket_offsets` (1..5)
* `mcc_offsets` (sparse overrides; default 0)
* `mcc_range_offsets` (recommended; see §6)

### 4.2 NB mean block (log-mean prior)

For merchant *m* (only if `is_multi=1`):

* `log(μ_m) = base_log_mean + channel_offset + mcc_offset + ε_log_mu`
* `μ_m = clamp_mu( exp(log(μ_m)) )`

**Required keys**

* `base_log_mean`
* `channel_offsets`
* `mcc_offsets`
* `mcc_range_offsets` (recommended)

### 4.3 Dispersion block (log-φ prior)

For merchant *m* (only if `is_multi=1`):

* `log(φ_m) = base_log_phi + gdp_log_slope * ln_gdp_pc(home_country) + channel_offset + mcc_offset + ε_log_phi`
* `φ_m = clamp_phi( exp(log(φ_m)) )`

**Required keys**

* `base_log_phi`
* `gdp_log_slope`
* `channel_offsets`
* `mcc_offsets`
* `mcc_range_offsets` (recommended)
* `mom` (required; pinned MOM knobs for dispersion training; see below)

### 4.3.1 Dispersion MOM knobs (PINNED; MUST)

These do not affect corpus generation directly, but they MUST be pinned so the dispersion trainer is deterministic:

* `epsilon` (float > 0) - stability floor in MOM denominator
* `n_min` (int >= 1) - minimum samples per cell before pooling
* `cell_weight_rule` (enum) - `"n_cell"` or `"sqrt_n_cell"`

## 4.4 Corpus generation semantics (PINNED; MUST match runtime intent)

The offline corpus MUST generate labels and counts consistently with the runtime model family:

1. Compute `pi_m` from `hurdle` (including noise + clamps), then draw:
   * `is_multi ~ Bernoulli(pi_m)` using Philox/open-interval `u in (0,1)`.

2. If `is_multi=1`, compute `(mu_m, phi_m)` from `nb_mean` and `dispersion` (including noise + clamps), then draw outlet counts using NB2:

   * Use the NB2 gamma-Poisson mixture parameterization:
     - `lambda ~ Gamma(shape=phi_m, scale=mu_m/phi_m)`
     - `N ~ Poisson(lambda)`

3. Truncation rule (MUST be explicit):
   * For the training corpus, enforce `N >= 2` for multi-site merchants by **rejection sampling** (repeat NB2 draw until `N>=2`), matching the engine's "multi-site means >=2 outlets" semantics.
   * Record `nb_rejections` per merchant in the corpus (recommended) so corridor diagnostics are possible.

Fail-closed rules:
* if any required covariate is missing (`home_country_iso` not in ISO spine, missing GDPpc, missing bucket), FAIL the training run (do not impute silently).

---

## 5) The missing piece in your old priors (why it felt “thin”)

Your old file is structurally fine, but it’s missing two things that make it “feel real” and remain stable across different merchant mixes:

1. **Range-based MCC effects** (so realism isn’t driven by 4 hand-picked MCCs)
2. **Calibration targets** (so intercepts adjust deterministically to hit realistic global rates)

Also: your example `base_log_phi: -0.70` implies `φ ≈ 0.5` before offsets, which is *extremely overdispersed* and tends to create lots of 0/1 counts (bad for the S2 corridor unless you explicitly design around it). For realism, φ should usually be comfortably > 5 for this kind of “number of outlets” process.

---

## 6) MCC range offsets (the realism lever that stays deterministic)

Instead of listing thousands of MCCs, define a **small deterministic set of range rules**:

### Format (recommended)

```yaml
mcc_range_offsets:
  - range: "4000-4799"   # travel/transport
    offset: <float>
  - range: "4800-4999"   # telecom/utilities
    offset: <float>
  ...
```

Semantics:

* For a given MCC code, sum the offsets of all ranges that contain it (usually ranges are disjoint).
* Then apply `mcc_offsets` as explicit **additive** overrides (epsilon added to the range-sum; no "replace" mode).

This gives “broad realism” without a huge file.

---

## 7) Calibration (PINNED deterministic; removes hand-tuning)

Add a `calibration` block so Codex can **solve intercepts** deterministically from targets on the actual merchant universe used for simulation.

### Required keys

```yaml
calibration:
  enabled: true
  mean_pi_target: 0.12
  mean_mu_target_multi: 4.5
  median_phi_target: 20.0
  fixed_iters: 64
  brackets:
    base_logit: [-10.0, 2.0]
    base_log_mean: [-2.0, 4.0]
    base_log_phi: [1.0, 5.0]
```

Pinned method:

* bisection with `fixed_iters` (no tolerance-based early stop)
* evaluate over the training merchant universe deterministically (stable ordering)
* if calibration disabled, use the provided base_* values as-is

Pinned calibration order (MUST):
1) Solve `hurdle.base_logit` to hit `mean_pi_target` using the **mean of pi_m** (not realised Bernoulli labels).
2) Solve `nb_mean.base_log_mean` to hit `mean_mu_target_multi` using merchants with `pi_m >= 0.5` (same convention as downstream corridor locks).
3) Solve `dispersion.base_log_phi` to hit `median_phi_target` using merchants with `pi_m >= 0.5`.

This removes seed-sensitive dependence on realised `is_multi` draws while keeping calibration deterministic.

---

## 8) Noise and clamps (prevents pathological corpora)

These are what keep the synthetic corpus “alive” but controlled.

### Noise

```yaml
noise:
  per_merchant_logit_sd: 0.35
  per_merchant_log_mu_sd: 0.25
  per_merchant_log_phi_sd: 0.20
```

* Noise is additive in the latent linear predictor space and is drawn deterministically from Philox.

**Noise distribution (MUST):**
* `e_logit`, `e_log_mu`, `e_log_phi` are i.i.d. `Normal(0, sd)` in their respective latent spaces.
* The Normal generator must be deterministic and pinned (e.g., Box-Muller on Philox open-interval uniforms); do not use platform RNGs.

### Clamps

```yaml
clamps:
  pi: { min: 0.01, max: 0.80 }
  mu: { min: 2.0,  max: 40.0 }
  phi: { min: 8.0, max: 80.0 }
```

These bounds are corridor-safe and avoid “ridiculous chains” or “infinite dispersion”.

---

## 9) An example of a proper v1 prior file (synthetic-realistic, deterministic)

This is an example to be built open and tuned by Codex to my current data

```yaml
# config/models/hurdle/hurdle_simulation.priors.yaml
# Training-only input (offline corpus priors). Not a sealed runtime artefact. 
#
# Semantics:
# - Hurdle: is_multi ~ Bernoulli(pi_m)
# - If is_multi=1: draw NB2 via Gamma-Poisson, then reject until N>=2 (to match runtime multi-site semantics). 
#
semver: "1.0.0"
version: "2025-12-31"

rng:
  algorithm: "philox2x64-10"
  seed: 9248923

calibration:
  enabled: true
  # Targets are evaluated deterministically on the training merchant universe
  # (using pi_m and the pi>=0.5 convention in the guide). 
  mean_pi_target: 0.12
  mean_mu_target_multi: 5.0
  median_phi_target: 22.0
  fixed_iters: 64
  brackets:
    base_logit: [-10.0, 2.0]
    base_log_mean: [-2.0, 4.0]
    base_log_phi: [1.0, 5.0]

noise:
  # Noise is additive in latent space; deterministically generated (e.g. Box–Muller on Philox uniforms). 
  per_merchant_logit_sd: 0.35
  per_merchant_log_mu_sd: 0.25
  per_merchant_log_phi_sd: 0.20

clamps:
  # Corridor-safe clamps to prevent pathological corpora / fits. 
  pi: { min: 0.01, max: 0.80 }
  mu: { min: 2.0,  max: 40.0 }
  phi: { min: 8.0, max: 80.0 }

hurdle:
  # logit(pi_m) = base_logit + channel + bucket + mcc_effect + e_logit 
  # base_logit is solved by calibration when enabled=true; value here is the starting point.
  base_logit: -1.20

  channel_offsets:
    CP: 0.00
    CNP: -0.85

  # GDP bucket (1..5) offsets: richer home markets -> higher multi-site propensity.
  bucket_offsets:
    "1": -0.75
    "2": -0.35
    "3":  0.00
    "4":  0.35
    "5":  0.75

  # Broad, deterministic sector shaping without enumerating thousands of MCCs. 
  mcc_range_offsets:
    - { range: "1500-1799", offset:  0.10 }  # contractors/services
    - { range: "3000-3999", offset:  0.40 }  # travel (airlines etc.)
    - { range: "4000-4799", offset:  0.35 }  # transport
    - { range: "4800-4999", offset:  0.20 }  # telecom/utilities/digital infra
    - { range: "5000-5999", offset:  0.20 }  # broad retail
    - { range: "5300-5399", offset:  0.45 }  # discount/warehouse
    - { range: "5400-5599", offset:  0.55 }  # grocery/fuel/pharmacy band
    - { range: "5600-5699", offset:  0.25 }  # apparel
    - { range: "5700-5799", offset:  0.20 }  # home furnishings
    - { range: "5800-5899", offset:  0.30 }  # eating/drinking
    - { range: "8000-8999", offset: -0.45 }  # professional/medical
    - { range: "9000-9999", offset: -0.55 }  # government/nonprofit

  # Sparse overrides (additive on top of range offsets). 
  mcc_offsets:
    "5411": 0.80  # grocery stores
    "5541": 0.70  # service stations
    "5542": 0.70  # automated fuel dispensers
    "5912": 0.60  # drug stores/pharmacies
    "5812": 0.35  # eating places/restaurants
    "5814": 0.35  # fast food
    "7011": 0.55  # lodging/hotels
    "4511": 0.45  # airlines
    "4111": 0.30  # commuter transport
    "7995": -0.35 # gambling
    "6011": -0.10 # ATM/cash disbursement
    "4829": -0.25 # money transfer

nb_mean:
  # log(mu_m) = base_log_mean + channel + mcc_effect + e_log_mu 
  base_log_mean: 1.00

  channel_offsets:
    CP: 0.05
    CNP: -0.15

  mcc_range_offsets:
    - { range: "1500-1799", offset:  0.10 }
    - { range: "3000-3999", offset:  0.45 }
    - { range: "4000-4799", offset:  0.35 }
    - { range: "5000-5999", offset:  0.20 }
    - { range: "5300-5399", offset:  0.40 }
    - { range: "5400-5599", offset:  0.55 }
    - { range: "5600-5699", offset:  0.25 }
    - { range: "5700-5799", offset:  0.20 }
    - { range: "5800-5899", offset:  0.25 }
    - { range: "8000-8999", offset: -0.25 }
    - { range: "9000-9999", offset: -0.30 }

  mcc_offsets:
    "5411": 0.75
    "5541": 0.60
    "5542": 0.60
    "5912": 0.50
    "5812": 0.30
    "5814": 0.30
    "7011": 0.55
    "4511": 0.45
    "7995": -0.20
    "6011": -0.10
    "4829": -0.10

dispersion:
  # log(phi_m) = base_log_phi + gdp_log_slope*ln_gdp_pc + channel + mcc_effect + e_log_phi 
  base_log_phi: 2.95
  gdp_log_slope: 0.08

  # Pinned MOM knobs for deterministic dispersion training. 
  mom:
    epsilon: 1.0e-6
    n_min: 30
    cell_weight_rule: "n_cell"

  channel_offsets:
    CP: 0.00
    CNP: -0.05

  mcc_range_offsets:
    - { range: "3000-3999", offset:  0.10 }
    - { range: "4000-4799", offset:  0.10 }
    - { range: "4800-4999", offset:  0.15 }
    - { range: "5300-5399", offset:  0.20 }
    - { range: "5400-5599", offset:  0.25 }
    - { range: "5800-5899", offset:  0.10 }
    - { range: "8000-8999", offset: -0.15 }
    - { range: "9000-9999", offset: -0.20 }

  mcc_offsets:
    "5411": 0.30
    "5541": 0.25
    "5542": 0.25
    "7011": 0.15
    "4511": 0.10
    "7995": -0.25
    "4829": -0.20
```

This prior:

* produces realistic variation across sectors and wealth buckets
* keeps dispersion in a corridor-safe band
* is deterministic and self-calibrating (no hand-tuning required)

---

## 10) What to change in your coefficient guides

Update the offline-training routes so they explicitly say:

* “The training corpus is generated using `config/models/hurdle/hurdle_simulation.priors.yaml` as a sealed input.”
* “This prior file must include calibration/noise/clamps and range-based MCC effects.”

---

## Appendix A — `artefact_registry_training_1A.yaml`

```yaml
subsegments:
- id: training.1A
  name: Offline Training · 1A Hurdle GLMs
  artifacts:

  - name: hurdle_simulation_priors
    path: config/models/hurdle/hurdle_simulation.priors.yaml
    type: config
    category: training_priors
    semver: '{semver}'
    version: '{simulation_version}'
    digest: '{sha256}'
    license: '{spdx_or_internal}'
    role: >
      Training-plane priors used to materialise the synthetic corpus for fitting:
      (1) hurdle logistic beta, (2) NB mean beta_mu, (3) dispersion beta_phi.
    dependencies:
      - transaction_schema_merchant_ids
      - world_bank_gdp_per_capita_20250415
      - gdp_bucket_map_2024
      - iso3166_canonical_2024
    source: internal
    owner: {ml_platform_team: null}
    last_updated: '{iso8601_timestamp}'
    environment: [training]
    schema: schemas.layer1.yaml#/training/hurdle_simulation_priors
    cross_layer: false
    notes: Training-only. Its sha256 MUST be recorded in the training manifest.

  - name: hurdle_simulation_manifest
    path: artefacts/training/1A/hurdle_sim/simulation_version={simulation_version}/seed={seed}/{iso8601_timestamp}/manifest.json
    type: manifest
    category: training_manifest
    semver: '{semver}'
    version: '{simulation_version}'
    digest: '{sha256}'
    license: '{spdx_or_internal}'
    role: >
      Sealed training manifest capturing: priors config path + sha256, RNG seed,
      resolved input references (paths + sha256), corpus outputs, export outputs,
      and bundle selfcheck results.
    dependencies:
      - hurdle_simulation_priors
    source: internal
    owner: {ml_platform_team: null}
    last_updated: '{iso8601_timestamp}'
    environment: [training]
    schema: schemas.layer1.yaml#/training/training_manifest_1A_hurdle_sim
    cross_layer: false
    notes: Export YAMLs MUST embed metadata.simulation_manifest pointing here.
```

---

## Appendix B — `schemas.layer1.yaml` (training section)

```yaml
version: '1.0'
$id: schemas.layer1.yaml
description: Training-plane schemas for Layer-1 offline simulations and manifests (1A hurdle training).

$defs:
  semver: {type: string, pattern: '^\d+\.\d+\.\d+$'}
  sha256: {type: string, pattern: '^[0-9a-f]{64}$'}
  rng_algorithm: {type: string, enum: [philox2x64-10]}
  uint64: {type: integer, minimum: 0, maximum: 18446744073709551615}

  iso8601_utc:
    type: string
    anyOf:
      - {pattern: '^\d{8}T\d{6}Z$'}
      - {pattern: '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'}

  channel_offsets:
    type: object
    additionalProperties: false
    required: [CP, CNP]
    properties:
      CP: {type: number}
      CNP: {type: number}

  bucket_offsets_1_to_5:
    type: object
    additionalProperties: false
    required: ["1","2","3","4","5"]
    properties:
      "1": {type: number}
      "2": {type: number}
      "3": {type: number}
      "4": {type: number}
      "5": {type: number}

  mcc_offsets:
    type: object
    patternProperties:
      '^[0-9]{4}$': {type: number}
    additionalProperties: false

  mcc_range_offsets:
    type: array
    items:
      type: object
      additionalProperties: false
      required: [range, offset]
      properties:
        range: {type: string, pattern: '^[0-9]{4}-[0-9]{4}$'}
        offset: {type: number}

  artifact_ref:
    type: object
    additionalProperties: false
    required: [path, sha256]
    properties:
      path: {type: string, minLength: 1}
      sha256: {$ref: '#/$defs/sha256'}

# ----------------------------
# A) Priors file schema
# ----------------------------
hurdle_simulation_priors:
  type: object
  additionalProperties: false
  required: [semver, version, rng, calibration, noise, clamps, hurdle, nb_mean, dispersion]
  properties:
    semver: {$ref: '#/$defs/semver'}
    version: {type: string, minLength: 1}

    rng:
      type: object
      additionalProperties: false
      required: [algorithm, seed]
      properties:
        algorithm: {$ref: '#/$defs/rng_algorithm'}
        seed: {$ref: '#/$defs/uint64'}

    calibration:
      type: object
      additionalProperties: false
      required: [enabled, mean_pi_target, mean_mu_target_multi, median_phi_target, fixed_iters, brackets]
      properties:
        enabled: {type: boolean}
        mean_pi_target: {type: number, minimum: 0.0, maximum: 1.0}
        mean_mu_target_multi: {type: number, exclusiveMinimum: 0.0}
        median_phi_target: {type: number, exclusiveMinimum: 0.0}
        fixed_iters: {type: integer, minimum: 1, maximum: 1024}
        brackets:
          type: object
          additionalProperties: false
          required: [base_logit, base_log_mean, base_log_phi]
          properties:
            base_logit:
              type: array
              minItems: 2
              maxItems: 2
              items: {type: number}
            base_log_mean:
              type: array
              minItems: 2
              maxItems: 2
              items: {type: number}
            base_log_phi:
              type: array
              minItems: 2
              maxItems: 2
              items: {type: number}

    noise:
      type: object
      additionalProperties: false
      required: [per_merchant_logit_sd, per_merchant_log_mu_sd, per_merchant_log_phi_sd]
      properties:
        per_merchant_logit_sd: {type: number, minimum: 0.0}
        per_merchant_log_mu_sd: {type: number, minimum: 0.0}
        per_merchant_log_phi_sd: {type: number, minimum: 0.0}

    clamps:
      type: object
      additionalProperties: false
      required: [pi, mu, phi]
      properties:
        pi:
          type: object
          additionalProperties: false
          required: [min, max]
          properties:
            min: {type: number, minimum: 0.0, maximum: 1.0}
            max: {type: number, minimum: 0.0, maximum: 1.0}
        mu:
          type: object
          additionalProperties: false
          required: [min, max]
          properties:
            min: {type: number, exclusiveMinimum: 0.0}
            max: {type: number, exclusiveMinimum: 0.0}
        phi:
          type: object
          additionalProperties: false
          required: [min, max]
          properties:
            min: {type: number, exclusiveMinimum: 0.0}
            max: {type: number, exclusiveMinimum: 0.0}

    hurdle:
      type: object
      additionalProperties: false
      required: [base_logit, channel_offsets, bucket_offsets, mcc_offsets]
      properties:
        base_logit: {type: number}
        channel_offsets: {$ref: '#/$defs/channel_offsets'}
        bucket_offsets: {$ref: '#/$defs/bucket_offsets_1_to_5'}
        mcc_offsets: {$ref: '#/$defs/mcc_offsets'}
        mcc_range_offsets: {$ref: '#/$defs/mcc_range_offsets'}

    nb_mean:
      type: object
      additionalProperties: false
      required: [base_log_mean, channel_offsets, mcc_offsets]
      properties:
        base_log_mean: {type: number}
        channel_offsets: {$ref: '#/$defs/channel_offsets'}
        mcc_offsets: {$ref: '#/$defs/mcc_offsets'}
        mcc_range_offsets: {$ref: '#/$defs/mcc_range_offsets'}

    dispersion:
      type: object
      additionalProperties: false
      required: [base_log_phi, gdp_log_slope, channel_offsets, mcc_offsets, mom]
      properties:
        base_log_phi: {type: number}
        gdp_log_slope: {type: number}
        channel_offsets: {$ref: '#/$defs/channel_offsets'}
        mcc_offsets: {$ref: '#/$defs/mcc_offsets'}
        mcc_range_offsets: {$ref: '#/$defs/mcc_range_offsets'}
        mom:
          type: object
          additionalProperties: false
          required: [epsilon, n_min, cell_weight_rule]
          properties:
            epsilon: {type: number, exclusiveMinimum: 0.0}
            n_min: {type: integer, minimum: 1}
            cell_weight_rule:
              type: string
              enum: ["n_cell", "sqrt_n_cell"]

# ----------------------------
# B) Training manifest schema
# ----------------------------
training_manifest_1A_hurdle_sim:
  type: object
  additionalProperties: false
  required:
    - manifest_semver
    - simulation_version
    - created_utc
    - rng
    - simulation_config
    - inputs
    - outputs
    - exports
  properties:
    manifest_semver: {$ref: '#/$defs/semver'}
    simulation_version: {type: string, minLength: 1}
    created_utc: {$ref: '#/$defs/iso8601_utc'}

    rng:
      type: object
      additionalProperties: false
      required: [algorithm, seed]
      properties:
        algorithm: {$ref: '#/$defs/rng_algorithm'}
        seed: {$ref: '#/$defs/uint64'}

    simulation_config:
      type: object
      additionalProperties: false
      required: [config_path, sha256]
      properties:
        config_path: {type: string, minLength: 1}
        sha256: {$ref: '#/$defs/sha256'}
        semver: {$ref: '#/$defs/semver'}
        version: {type: string, minLength: 1}

    inputs:
      type: object
      additionalProperties: false
      required:
        - transaction_schema_merchant_ids
        - world_bank_gdp_per_capita
        - gdp_bucket_map
        - iso3166_canonical
      properties:
        transaction_schema_merchant_ids: {$ref: '#/$defs/artifact_ref'}
        world_bank_gdp_per_capita: {$ref: '#/$defs/artifact_ref'}
        gdp_bucket_map: {$ref: '#/$defs/artifact_ref'}
        iso3166_canonical: {$ref: '#/$defs/artifact_ref'}

    outputs:
      type: object
      additionalProperties: false
      required: [logistic_parquet, nb_mean_parquet]
      properties:
        logistic_parquet: {$ref: '#/$defs/artifact_ref'}
        nb_mean_parquet: {$ref: '#/$defs/artifact_ref'}
        notes: {type: string}

    exports:
      type: object
      additionalProperties: false
      required: [hurdle_coefficients_yaml, nb_dispersion_coefficients_yaml, bundle_selfcheck_json]
      properties:
        hurdle_coefficients_yaml: {$ref: '#/$defs/artifact_ref'}
        nb_dispersion_coefficients_yaml: {$ref: '#/$defs/artifact_ref'}
        bundle_selfcheck_json: {$ref: '#/$defs/artifact_ref'}

    git_commit_hex:
      type: string
      pattern: '^(?:[0-9a-f]{40}|[0-9a-f]{64})$'
```

---

## Appendix C — Training manifest template (`manifest.json`)

This is the **file Codex writes per training run** at:

`artefacts/training/1A/hurdle_sim/simulation_version={simulation_version}/seed={seed}/{iso8601_timestamp}/manifest.json`

…and validates against:
`schemas.layer1.yaml#/training/training_manifest_1A_hurdle_sim`

```json
{
  "manifest_semver": "1.0.0",
  "simulation_version": "{simulation_version}",
  "created_utc": "{iso8601_timestamp}",

  "rng": {
    "algorithm": "philox2x64-10",
    "seed": {seed}
  },

  "simulation_config": {
    "config_path": "config/models/hurdle/hurdle_simulation.priors.yaml",
    "sha256": "{sha256_priors}",
    "semver": "{priors_semver}",
    "version": "{priors_version}"
  },

  "inputs": {
    "transaction_schema_merchant_ids": {
      "path": "{path_transaction_schema_merchant_ids}",
      "sha256": "{sha256_transaction_schema_merchant_ids}"
    },
    "world_bank_gdp_per_capita": {
      "path": "{path_world_bank_gdp_per_capita}",
      "sha256": "{sha256_world_bank_gdp_per_capita}"
    },
    "gdp_bucket_map": {
      "path": "{path_gdp_bucket_map}",
      "sha256": "{sha256_gdp_bucket_map}"
    },
    "iso3166_canonical": {
      "path": "{path_iso3166_canonical}",
      "sha256": "{sha256_iso3166_canonical}"
    }
  },

  "outputs": {
    "logistic_parquet": {
      "path": "{path_logistic_parquet}",
      "sha256": "{sha256_logistic_parquet}"
    },
    "nb_mean_parquet": {
      "path": "{path_nb_mean_parquet}",
      "sha256": "{sha256_nb_mean_parquet}"
    },
    "notes": "Synthetic training corpus for 1A hurdle/mean/dispersion fits."
  },

  "exports": {
    "hurdle_coefficients_yaml": {
      "path": "{path_hurdle_coefficients_yaml}",
      "sha256": "{sha256_hurdle_coefficients_yaml}"
    },
    "nb_dispersion_coefficients_yaml": {
      "path": "{path_nb_dispersion_coefficients_yaml}",
      "sha256": "{sha256_nb_dispersion_coefficients_yaml}"
    },
    "bundle_selfcheck_json": {
      "path": "{path_bundle_selfcheck_json}",
      "sha256": "{sha256_bundle_selfcheck_json}"
    }
  },

  "git_commit_hex": "{git_commit_hex}"
}
```

## Acceptance checklist

- Required top-level keys present (`rng`, `calibration`, `noise`, `clamps`, `hurdle`, `nb_mean`, `dispersion`).
- `rng.algorithm` is philox2x64-10 and `seed` is recorded.
- Input paths + sha256 are recorded for merchant_ids, GDP, buckets, and ISO.
- Clamp ranges are valid (min < max) and noise scales are finite.
- Manifest and export bundle paths are recorded and exist after export.

