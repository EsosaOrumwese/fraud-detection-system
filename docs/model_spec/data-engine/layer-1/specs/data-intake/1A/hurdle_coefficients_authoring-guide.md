You’re right to demand the **proper** route here. For `hurdle_coefficients.yaml`, the **primary** authoring path is your **offline simulation → design-matrix → GLM fit → export bundle** pipeline. Anything else is fallback-only.

---

# Authoring Guide — `hurdle_coefficients.yaml` (Offline-trained coefficient bundle)

## 0) What this file is

`hurdle_coefficients.yaml` is the sealed model bundle consumed by **1A.S0/S1/S2** that provides:

* `beta` — logistic hurdle coefficients for **π = P(multi-site)** (S1)
* `beta_mu` — NB mean coefficients for **μ = E[N | multi-site]** (S2)

This bundle also carries the **frozen dictionaries** that define the **authoritative column order** used at runtime.

It is produced **offline** and treated as a **parameter artefact** (its bytes must participate in `parameter_hash`).

### 0.1 Hard prohibition & realism bar (MUST)

This is an authored external, but **not** hand-authored numbers. Codex MUST:

* produce this bundle as the output of a recorded offline training run (simulation -> corpus -> deterministic design matrices -> deterministic fit).
* persist the sealed training corpus + `manifest.json`, and reference it via `metadata.simulation_manifest`.
* fail closed on placeholder or degenerate bundles (e.g., all-zeros vectors, repeated constants, NaN/Inf, or near-constant predicted pi/mu across merchants).

---

## 1) Where it must land (binding path)

From your artefact registry, the export path is:

`config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/hurdle_coefficients.yaml`

Where:

* `{config_version}` is the training/export version label (e.g., `2025-10-24`)
* `{iso8601_timestamp}` is the run timestamp directory

---

## 2) What must be inside the YAML (binding keys)

### 2.1 Required keys

* `semver` (string)
* `version` (string; equals `{config_version}`)
* `metadata.simulation_manifest` (string path pointer to the exact training manifest)
* `dict_mcc` (list[int]) — **authoritative order**
* `dict_ch` (list[str]) — must be exactly `["CP","CNP"]`
* `dict_dev5` (list[int]) - must be exactly `[1,2,3,4,5]`
* `beta` (list[float]) - logistic hurdle vector
* `beta_mu` (list[float]) - NB mean vector
* `design.beta_order` (list[str]) - explicit coefficient order tokens for `beta` (must match section 4.2).
* `design.beta_mu_order` (list[str]) - explicit coefficient order tokens for `beta_mu` (must match section 4.2).

### 2.2 Optional but strongly recommended keys

* `metadata.simulation_config_path`
* `metadata.seed`
* `metadata.created_utc`
* `metadata.inputs` (resolved input paths + digests)

---

## 3) Inputs the offline trainer MUST pin (manifested)

Your training run must write a `manifest.json` and the YAML must point to it via `metadata.simulation_manifest`.

That manifest must record (at minimum):

* the **simulation config path** used
* the RNG seed
* the exact reference inputs used to build the corpus, typically:

  * `transaction_schema_merchant_ids` snapshot path/version
  * `world_bank_gdp_per_capita` snapshot path/version
  * `gdp_bucket_map` snapshot path/version
  * `iso3166_canonical` snapshot path/version

The manifest MUST also record **digests** (sha256) for:

* the simulation priors/config file bytes
* each resolved input snapshot/file used to build the corpus
* each emitted corpus parquet file (so the fit is reproducible from bytes, not just paths).

This is what makes the coefficients reproducible and auditable.

---

## 4) Runtime design contract (the most important part)

### 4.1 Dictionaries (column authority)

**`dict_mcc` (MUST)**

* Must be a list of MCC integers in authoritative order.
* **Best practice (no surprises):** derive it from the *same* merchant universe snapshot that the engine run will use:

  * `dict_mcc = sorted(unique(transaction_schema_merchant_ids.mcc))`
* Runtime consequence: if a run’s `merchant_ids.mcc` contains a value not in `dict_mcc`, S0.5 must fail (unknown MCC).

**`dict_ch` (MUST)**

* Exactly `["CP","CNP"]`

**`dict_dev5` (MUST)**

* Exactly `[1,2,3,4,5]`

### 4.2 Feature blocks and coefficient order (binding)

**Hurdle logistic (`beta`)**
Design vector order is fixed:

1. intercept (leading 1)
2. MCC one-hot block in `dict_mcc` order
3. channel one-hot block in `["CP","CNP"]` order
4. GDP bucket one-hot block in `[1,2,3,4,5]` order

**Shape invariant (MUST):**
`len(beta) = 1 + |dict_mcc| + 2 + 5`

**NB mean (`beta_mu`)**
Design vector order is fixed:

1. intercept
2. MCC one-hot block in `dict_mcc` order
3. channel one-hot block in `["CP","CNP"]` order

**Shape invariant (MUST):**
`len(beta_mu) = 1 + |dict_mcc| + 2`

**Non-negotiable rule:**

* GDP bucket enters **hurdle only** (never mean, never dispersion mean model).

---

## 5) Offline training route (the proper route)

### Step A — Load simulation priors

* Config file: `config/models/hurdle/hurdle_simulation.priors.yaml`
* This file defines:

  * the seed
  * simulation priors and corpus scale
  * any regularization strengths and fit settings

### Step B — Materialize a synthetic training corpus (and seal it)

Write a run bundle under:

`artefacts/training/1A/hurdle_sim/simulation_version={config_version}/seed={seed}/{iso8601_timestamp}/`

Bundle contents (minimum):

* `logistic.parquet` (binary labels: single vs multi-site, keyed by merchant_id)
* `nb_mean.parquet` (count targets for multi-site merchants, keyed by merchant_id)
* `manifest.json` (pins config path, seed, resolved input refs)

### Step C — Build deterministic design matrices

From the sealed corpus + reference tables:

**Logistic matrix**

* Rows: all merchants
* Target: `y_hurdle ∈ {0,1}`
* Features: intercept + MCC + channel + GDP bucket dummies (as §4.2)

**Mean matrix**

* Rows: multi-site merchants only (or whichever subset your trainer defines, but it must be documented)
* Target: `log(y_count)` where `y_count` is total outlets for that merchant in the corpus
* Features: intercept + MCC + channel dummies (as §4.2)

**Dictionary freeze**

* `dict_mcc` derived deterministically (see §4.1)
* `dict_ch`, `dict_dev5` fixed as above

### Step D — Fit two GLMs / regressions (deterministic)

1. **Hurdle logistic** (`beta`)

* Ridge-regularized IRLS (as your pipeline already does)
* Deterministic iteration order, deterministic convergence criteria
* No dependence on BLAS parallelism for decision-critical solves (single-threaded linear algebra is safest)

2. **NB mean** (`beta_mu`)

* Your existing approach: regression on `log(y_nb)`
* Ridge regularization (recommended) to stabilize high-cardinality MCC dummies

### Step E — Export the YAML bundle (atomic write)

Write:

`config/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/hurdle_coefficients.yaml`

Include:

* dicts
* vectors
* `metadata.simulation_manifest` pointing back to the sealed manifest from Step B

---

## 6) Acceptance checks (Codex must enforce before publishing)

### 6.1 Structural / shape checks (MUST)

* `dict_ch == ["CP","CNP"]`
* `dict_dev5 == [1,2,3,4,5]`
* `len(beta) == 1 + |dict_mcc| + 2 + 5`
* `len(beta_mu) == 1 + |dict_mcc| + 2`

### 6.2 Numeric sanity checks (MUST)

Across the merchant universe used for design:

* All computed logits and linear predictors are finite
* All probabilities `π` are strictly inside `(0,1)` (no NaN/Inf)
* All `μ = exp(ημ)` are finite and > 0

### 6.3 Behavioural realism checks (SHOULD, but pinned so it’s automatic)

On the training universe:

* mean predicted `π` is within a plausible band (you set this band in the simulation priors; check it matches)
* mean/median predicted `μ` for multi-site merchants is within a plausible band (again, pinned by priors)

### 6.4 Provenance checks (MUST)

* `metadata.simulation_manifest` path exists and is readable
* manifest records: config path, seed, input reference paths/versions

### 6.5 Post-export bundle lock (MUST)

This bundle is only considered publishable if the paired dispersion bundle is also present and the cross-bundle selfcheck passes:

* run the "Belt-and-braces lock - `hurdle_coefficients.yaml` + `nb_dispersion_coefficients.yaml`" (as defined in the dispersion guide),
* write `bundle_selfcheck.json` next to the export directory, and
* require PASS (no PASS -> export is invalid).

---

## 7) Working links (repo paths Codex uses)

**Export entry point**

* `packages/engine/src/engine/training/hurdle/exports.py` → `generate_export_bundle(...)`

**Fitting**

* `packages/engine/src/engine/training/hurdle/fit.py`

**Design matrix construction**

* `packages/engine/src/engine/training/hurdle/design.py`

**Simulation config loader**

* `packages/engine/src/engine/training/hurdle/config.py`

**Corpus persistence + manifest writer**

* `packages/engine/src/engine/training/hurdle/persist.py`

**Universe sources**

* `packages/engine/src/engine/training/hurdle/universe.py`

---

