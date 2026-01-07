# 1A.S0 artefacts/policies/configs (from state.1A.s0.expanded.md only)

## Inputs / sealed artefacts / policies / configs
- `merchant_ids` (ingress table; schema `schemas.ingress.layer1.yaml#/merchant_ids`)
- ISO-3166 country set (reference artefact)
- `world_bank_gdp_per_capita_20250415` (GDP per-capita vintage; obs_year=2024)
- `gdp_bucket_map_2024` (Jenks K=5 bucket map)
- JSON-Schema authority files
  - `schemas.ingress.layer1.yaml`
  - `schemas.1A.yaml` (anchors referenced: `#/model/hurdle_pi_probs`, `#/model/hurdle_design_matrix`, `#/prep/crossborder_eligibility_flags`, `#/alloc/country_set`, `#/egress/outlet_catalogue`)
  - `schemas.layer1.yaml` (RNG core + events)
- Parameter bundle (governed set for `parameter_hash`)
  - `hurdle_coefficients.yaml`
  - `nb_dispersion_coefficients.yaml`
  - `crossborder_hyperparams.yaml`
  - `ccy_smoothing_params.yaml`
  - `s6_selection_policy.yaml`
- `crossborder_hyperparams.yaml` (eligibility rule set for S0.6)
- `numeric_policy.json`
- `math_profile_manifest.json`
- `artefact_registry_1A.yaml` (dependency closure for `manifest_fingerprint`)
- `transaction_schema_merchant_ids` (ingress dataset referenced in dependency closure)
- `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml` (dependency of `transaction_schema_merchant_ids` when declared)
- Fitting bundle dictionaries + coefficient vectors (MCC/channel/GDP bucket dictionaries; hurdle beta; NB dispersion beta) as parameter-scoped inputs

## Parameter-scoped outputs / caches
- `crossborder_eligibility_flags` (schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`)
- `hurdle_pi_probs` (optional diagnostics cache; schema `schemas.1A.yaml#/model/hurdle_pi_probs`)
- `hurdle_design_matrix` (optional/transient cache; schema `schemas.1A.yaml#/model/hurdle_design_matrix`)

## Fingerprint-scoped validation bundle (`validation_bundle_1A`)
- `MANIFEST.json`
- `parameter_hash_resolved.json`
- `manifest_fingerprint_resolved.json`
- `param_digest_log.jsonl`
- `fingerprint_artifacts.jsonl`
- `numeric_policy_attest.json`
- `DICTIONARY_LINT.txt` (optional)
- `SCHEMA_LINT.txt` (optional)
- `_passed.flag`

## RNG logs (log-scoped)
- `rng_audit_log`
- `rng_trace_log`
- `rng_event_*` (family)

## Failure / abort artefacts
- `failure.json`
- `_FAILED.SENTINEL.json`
- `_FAILED.json` (partition sentinel when partial outputs escape temp)
- `merchant_abort_log` (parameter-scoped, when states allow soft aborts)

## Other dataset references in S0 authority notes
- `outlet_catalogue` (egress dataset referenced in schema authority and partitioning examples)
- `s3_candidate_set.candidate_rank` (cross-country order authority, referenced for joins)
- `country_set` (legacy, non-authoritative for order)
- `ranking_residual_cache_1A` (referenced in partitioning notes)

# 1A.S1 artefacts/policies/configs (from state.1A.s1.expanded.md only)

## Inputs / references
- Design vector `x_m` (column-frozen from S0.5)
- Hurdle coefficients bundle (single YAML `beta`, atomic load)
- Lineage/RNG context keys: `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`
- `rng_audit_log` (must exist before first hurdle event)
- Dataset dictionary for gating discovery: `dataset_dictionary.layer1.1A.yaml`
- Artefact registry enumeration (fallback if dictionary lacks `gating`)
- Schema anchors (layer schema):
  - `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`
  - `schemas.layer1.yaml#/rng/core/rng_trace_log`

## Outputs / datasets
- `rng_event_hurdle_bernoulli` (JSONL event stream)
  - `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `rng_trace_log` (cumulative per-substream trace; final-row selection per `#/rng/core/rng_trace_log`)
- In-memory handoff tuple `Xi_m` (not persisted): `(is_multi, N, K, country_set, C_star)`
- Optional diagnostic dataset `hurdle_pi_probs` (parameter-scoped; schema `#/model/hurdle_pi_probs`)

## Failure / validation artefacts
- `_FAILED.json` sentinel (validator failure output)
- Per-failure forensics JSON object (emitted alongside validation bundle / `_FAILED.json`)
