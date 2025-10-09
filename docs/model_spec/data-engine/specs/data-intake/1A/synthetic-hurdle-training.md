# Synthetic Hurdle Training Corpus (Phase Preview)

As it currently stands, the hurdle and NB-dispersion coefficients are backed by a **synthetic training corpus** generated inside the repository. No public or proprietary transaction data is involved; instead we reuse the sealed merchant ingress surface plus governed priors to build a reproducible proxy dataset.

## Pipeline sketch

1. **Load ingress authorities** — the helper `load_enriched_universe` reopens the current `transaction_schema_merchant_ids` parquet and enriches each merchant with GDP bucket and `ln_gdp` from the governed reference tables.
2. **Apply priors** — `hurdle_simulation.priors.yaml` records the RNG seed and per-feature offsets (MCC, channel, bucket) for both hurdle and NB heads.
3. **Simulate outcomes** — `simulate_hurdle_corpus` deterministically draws `is_multi` and zero-truncated NB outlet counts, returning the logistic/NB frames plus alias/channel dictionaries.
4. **Persist artefacts** — `materialise_simulated_corpus` writes the frames under `artefacts/training/1A/hurdle_sim/simulation_version=…/seed=…/<timestamp>/` and emits a manifest mirroring the run metadata.
5. **Validate** — `validate_simulation_run` reopens the persisted datasets, asserting schema coverage, manifest counts, and sanity corridors (multi-rate ∈ (0,1), `k_domestic ≥ 2`). Failing checks abort the persistence step.

## Provenance

- RNG seed, prior version, and source tables are captured in the manifest alongside a summary (`rows_logistic`, `rows_nb`, overall multi-rate, mean outlet count).
- Regenerating the dataset with the same prior file and merchant ingress produces byte-identical outputs (tests cover this determinism).
- These coefficients should therefore be treated as **synthetic priors**. Downstream consumers must not interpret them as empirical statistics; the manifest path should be cited in any report/artefact that depends on them.

## Future work

When richer data becomes available (e.g., curated brand census, partner datasets), the simulator can be swapped out for a real training pipeline by updating the priors and manifest schema while keeping the same orchestration hooks. Until then, the synthetic corpora unblock the YAML coefficient export without compromising the closed-world governance principles.


## Current export

The latest synthetic fit is published under `configs/models/hurdle/exports/version=2025-10-09/20251009T120000Z/`, which contains `hurdle_coefficients.yaml` and `nb_dispersion_coefficients.yaml`.
## Cross-border policy

A synthetic eligibility ladder is staged at `configs/policy/crossborder_hyperparams.yaml`. It denies high-risk CNP MCCs globally, whitelists CP merchants across the synthetic EEA subset, and defaults to allow.