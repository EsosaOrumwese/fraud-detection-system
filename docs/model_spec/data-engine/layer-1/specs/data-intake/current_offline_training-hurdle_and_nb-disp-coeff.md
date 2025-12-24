Offline Training Walkthrough: hurdle_coefficients.yaml + nb_dispersion_coefficients.yaml
======================================================================================

Purpose
-------
This is a concrete, file-referenced walkthrough of how the offline training pipeline
materializes the coefficient bundles that the data engine consumes for 1A:

- `config/models/hurdle/exports/version=.../hurdle_coefficients.yaml`
- `config/models/hurdle/exports/version=.../nb_dispersion_coefficients.yaml`

This is based on the actual code and the real manifest produced by a training run.

What gets produced (and where it lands)
---------------------------------------
1) Hurdle + NB-mean coefficients:
   - `config/models/hurdle/exports/version=2025-10-09/20251009T120000Z/hurdle_coefficients.yaml`
   - `config/models/hurdle/exports/version=2025-10-24/20251024T234923Z/hurdle_coefficients.yaml`

2) NB dispersion coefficients:
   - `config/models/hurdle/exports/version=2025-10-09/20251009T120000Z/nb_dispersion_coefficients.yaml`
   - `config/models/hurdle/exports/version=2025-10-24/20251024T234923Z/nb_dispersion_coefficients.yaml`

Each output embeds a pointer to the exact simulation manifest used to generate it:
`metadata.simulation_manifest` inside the YAML file.

For example, the manifest for the 2025-10-09 export is:
`artefacts/training/1A/hurdle_sim/simulation_version=2025-10-09/seed=9248923/20251009T120000Z/manifest.json`

That manifest explicitly records:
- the simulation config path,
- the RNG seed,
- the input reference tables used to build the training corpus.

Entry points (the actual code that generates these files)
---------------------------------------------------------
Primary export function:
- `packages/engine/src/engine/training/hurdle/exports.py`
  - `generate_export_bundle(...)` is the "one stop" generator.

Fitting logic:
- `packages/engine/src/engine/training/hurdle/fit.py`

Design matrix construction:
- `packages/engine/src/engine/training/hurdle/design.py`

Simulation config loader:
- `packages/engine/src/engine/training/hurdle/config.py`

Simulation corpus persistence:
- `packages/engine/src/engine/training/hurdle/persist.py`

Universe sources:
- `packages/engine/src/engine/training/hurdle/universe.py`

The exact simulation config file
--------------------------------
The offline training config used by the simulation is:
`config/models/hurdle/hurdle_simulation.priors.yaml`

This is confirmed by the real manifest:
`artefacts/training/1A/hurdle_sim/simulation_version=2025-10-09/seed=9248923/20251009T120000Z/manifest.json`

That manifest includes:
```
simulation_config.config_path = "config\\models\\hurdle\\hurdle_simulation.priors.yaml"
```

Step-by-step walkthrough (what actually happens)
------------------------------------------------
1) Load the simulation priors
   - File: `config/models/hurdle/hurdle_simulation.priors.yaml`
   - Loader: `packages/engine/src/engine/training/hurdle/config.py`
   - This config defines the RNG seed, priors, and simulation settings used to
     create a synthetic training corpus.

2) Materialise a synthetic training corpus
   - Function: `materialise_simulated_corpus(...)`
   - File: `packages/engine/src/engine/training/hurdle/persist.py`
   - This writes a run-specific corpus bundle under:
     `artefacts/training/1A/hurdle_sim/simulation_version=.../seed=.../<timestamp>/`
   - The bundle contains:
     - `logistic.parquet`  (binary labels for single vs multi-site)
     - `nb_mean.parquet`   (count data for NB mean + dispersion)
     - plus support tables like channel roster / brand aliases.
   - A `manifest.json` is written alongside, capturing:
     - the exact config path,
     - RNG seed,
     - input reference tables used.

   Example manifest (real):
   `artefacts/training/1A/hurdle_sim/simulation_version=2025-10-09/seed=9248923/20251009T120000Z/manifest.json`
   which shows:
   - `reference/layer1/transaction_schema_merchant_ids/v2025-10-08/transaction_schema_merchant_ids.parquet`
   - `reference/economic/world_bank_gdp_per_capita/2025-10-07/gdp.parquet`
   - `reference/economic/gdp_bucket_map/2025-10-08/gdp_bucket_map.parquet`
   - `reference/layer1/iso_canonical/v2025-10-08/iso_canonical.parquet`

3) Build design matrices
   - Function: `build_design_matrices(...)`
   - File: `packages/engine/src/engine/training/hurdle/design.py`
   - This encodes feature blocks into deterministic design vectors:
     - Logistic hurdle uses MCC + channel + GDP bucket dummies.
     - NB mean uses MCC + channel only.
     - Dispersion uses MCC + channel + ln_gdp_pc_usd_2015.

4) Fit the coefficients
   - Function: `fit_hurdle_coefficients(...)`
   - File: `packages/engine/src/engine/training/hurdle/fit.py`
   - Outputs:
     - `beta`    : logistic coefficients for multi-site probability (hurdle)
     - `beta_mu` : log-linear NB mean coefficients
     - `beta_phi`: dispersion coefficients derived via a MOM + weighted ridge fit

   Technical detail (as coded):
   - Logistic: IRLS (ridge-regularised), `_sigmoid`, iterative solve.
   - NB mean: linear regression on `log(y_nb)`.
   - Dispersion: method-of-moments per (MCC, channel, GDP-bin), then weighted ridge
     on `log(phi)`.

5) Export YAML bundles
   - Function: `generate_export_bundle(...)`
   - File: `packages/engine/src/engine/training/hurdle/exports.py`
   - Writes:
     - `hurdle_coefficients.yaml` (beta + beta_mu + dicts + metadata)
     - `nb_dispersion_coefficients.yaml` (beta_phi + design order + dicts + metadata)
   - Output location:
     `config/models/hurdle/exports/version=<date>/<timestamp>/`

   Each YAML includes:
   - `metadata.simulation_manifest` (link to the simulation manifest)
   - `dicts` (frozen MCC/channel/GDP bucket order)
   - coefficient vectors (beta / beta_mu / beta_phi)

How the engine uses the outputs (runtime consumption)
-----------------------------------------------------
At runtime, the engine treats these as **sealed parameter artefacts**:

- Loaded by:
  `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l1/design.py`
  (via `load_hurdle_coefficients(...)`)

- Wired in:
  `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/runner.py`
  which loads `hurdle_coefficients.yaml` and `nb_dispersion_coefficients.yaml`
  as part of the parameter pack, then uses them downstream in S1/S2.

In short: S0/S1/S2 never "train" anything. They only **consume** these sealed
YAML bundles, which are produced offline by the training pipeline above.

Quick map (single-line summary)
-------------------------------
`config/models/hurdle/hurdle_simulation.priors.yaml`
-> `materialise_simulated_corpus(...)`
-> `build_design_matrices(...)`
-> `fit_hurdle_coefficients(...)`
-> `config/models/hurdle/exports/version=.../{hurdle_coefficients.yaml,nb_dispersion_coefficients.yaml}`
-> consumed by 1A S0/S1/S2.
