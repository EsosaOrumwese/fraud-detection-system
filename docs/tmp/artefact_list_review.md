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


---

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


---

# 1A.S2 artefacts/policies/configs (from state.1A.s2.expanded.md only)

## Inputs / references
- S1 hurdle gate stream: `logs/rng/events/hurdle_bernoulli/...` (must contain `is_multi=true` to enter S2)
- Coefficient bundles (parameter-scoped inputs):
  - `hurdle_coefficients.yaml` (`beta_mu`)
  - `nb_dispersion_coefficients.yaml` (`beta_phi`)
- Schema anchors (layer schema):
  - `schemas.layer1.yaml#/rng/events/gamma_component`
  - `schemas.layer1.yaml#/rng/events/poisson_component`
  - `schemas.layer1.yaml#/rng/events/nb_final`
- Validation policy artefact (CUSUM thresholds): `validation_policy.yaml` (cusum `reference_k`, `threshold_h`)
- Policy flags referenced for S3 hand-off: `crossborder_eligibility_flags(parameter_hash)`

## Outputs / datasets
- `gamma_component` (JSONL event stream)
  - `logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `poisson_component` (JSONL event stream)
  - `logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `nb_final` (JSONL event stream; non-consuming)
  - `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `rng_trace_log` (cumulative per-substream trace; one row per RNG event append)
- In-memory handoff to S3: `N_m` (accepted domestic outlet count), `r_m` (rejection tally)

## Validation bundle outputs (on failure)
- `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`
  - `index.json`
  - `schema_checks.json`
  - `rng_accounting.json`
  - `metrics.csv`
  - `diffs` (bundle diffs; file naming not specified)
  - CUSUM trace (bundle artefact; file naming not specified)
  - `_passed.flag` is omitted on failure


---

# 1A.S3 artefacts/policies/configs (from state.1A.s3.expanded.md only)

## Inputs / references
- Upstream datasets (gates):
  - `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` (S1 hurdle; `is_multi==true`)
  - `schemas.layer1.yaml#/rng/events/nb_final` (S2 accepted outlet count `N >= 2`)
  - `schemas.ingress.layer1.yaml#/merchant_ids` (merchant scope)
- Governed artefacts / static refs:
  - `policy.s3.rule_ladder.yaml` (ordered rules, precedence, closed `reason_codes`)
  - `iso3166_canonical_2024` (canonical ISO list/order)
  - `static.currency_to_country.map.json` (currency→country map, if referenced)
  - `policy.s3.base_weight.yaml` (optional deterministic priors + dp)
  - `policy.s3.thresholds.yaml` (optional deterministic cutoffs used by rule ladder)
- Schema/dictionary/registry authority:
  - `schemas.layer1.yaml` (JSON-Schema authority; includes `#/s3/*` anchors)
  - `schema.index.layer1.json` (optional schema index)
  - `dataset_dictionary.layer1.1A.yaml` (dataset id → partition → path)
  - `artefact_registry_1A.yaml` (artefact registry + digests)

## Outputs / datasets (parameter-scoped)
- `s3_candidate_set` (required; ordered candidates)
  - Schema: `schemas.1A.yaml#/s3/candidate_set`
  - Partition: `parameter_hash={parameter_hash}`
- `s3_base_weight_priors` (optional deterministic priors)
  - Schema: `schemas.1A.yaml#/s3/base_weight_priors`
  - Partition: `parameter_hash={parameter_hash}`
- `s3_integerised_counts` (optional integerised counts)
  - Schema: `schemas.1A.yaml#/s3/integerised_counts`
  - Partition: `parameter_hash={parameter_hash}`
- `s3_site_sequence` (optional sequencing owned by S3)
  - Schema: `schemas.1A.yaml#/s3/site_sequence`
  - Partition: `parameter_hash={parameter_hash}`

## Sidecars / write discipline
- `_manifest.json` (required dataset-level sidecar per S3 write: `{manifest_fingerprint, parameter_hash, row_count, files_sorted, dataset_digest}`)


---

# 1A.S4 artefacts/policies/configs (from state.1A.s4.expanded.md only)

## Inputs / references (gates & facts)
- S1 hurdle events (gate): `schemas.layer1.yaml#/rng/events/hurdle_bernoulli` (`is_multi==true`)
- S2 finaliser (fact): `schemas.layer1.yaml#/rng/events/nb_final` (`N_m >= 2`)
- S3 eligibility gate: `schemas.1A.yaml#/s3/crossborder_eligibility_flags` (`is_eligible==true`)
- S3 candidate universe: `schemas.1A.yaml#/s3/candidate_set` (for `A := size(candidate_set \ {home})`)

## Governed artefacts (participate in `parameter_hash`)
- `crossborder_hyperparams` (ZTP link parameters `theta`, `MAX_ZTP_ZERO_ATTEMPTS`, `ztp_exhaustion_policy`)
- `crossborder_features` (optional feature view `X_m` with default when missing)

## Schema / dictionary authority
- Event schema anchors:
  - `schemas.layer1.yaml#/rng/events/poisson_component` (context `"ztp"`)
  - `schemas.layer1.yaml#/rng/events/ztp_rejection`
  - `schemas.layer1.yaml#/rng/events/ztp_retry_exhausted`
  - `schemas.layer1.yaml#/rng/events/ztp_final`
  - `schemas.layer1.yaml#/rng/core/rng_trace_log`
- Data Dictionary entries for S4 logs (partitions `{seed, parameter_hash, run_id}`)

## Outputs / datasets (logs-only)
- `rng_event_poisson_component` (context `"ztp"`)
- `rng_event_ztp_rejection`
- `rng_event_ztp_retry_exhausted`
- `rng_event_ztp_final`
- `rng_trace_log` (cumulative; one row per S4 event append)

## Hard literals / constants
- `module = "1A.ztp_sampler"`
- `substream_label = "poisson_component"`
- `context = "ztp"`
- Poisson regime threshold `lambda_extra < 10 => inversion`, otherwise `ptrs`

## Failure / abort artefacts
- `failure.json` (values-only; `data/layer1/1A/validation/failures/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/`)


---

# 1A.S5 artefacts/policies/configs (from state.1A.s5.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.ingress.layer1.yaml`
  - `schemas.1A.yaml`
  - `schemas.layer1.yaml` (RNG/log conventions only; S5 emits no RNG)
- Dataset dictionary: `dataset_dictionary.layer1.1A.yaml`
- Ingress reference surfaces:
  - `settlement_shares_2024Q4` (schema `schemas.ingress.layer1.yaml#/settlement_shares`)
  - `ccy_country_shares_2024Q4` (schema `schemas.ingress.layer1.yaml#/ccy_country_shares`)
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `iso_legal_tender_2024` (schema `schemas.ingress.layer1.yaml#/iso_legal_tender_2024`)
- Governed policy/config (parameter-hash member):
  - `config/allocation/ccy_smoothing_params.yaml` (`ccy_smoothing_params`)
- Licence mapping artefact: `licenses/license_map.yaml`

## Outputs / datasets (parameter-scoped)
- `ccy_country_weights_cache` (schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`)
- `merchant_currency` (optional; schema `schemas.1A.yaml#/prep/merchant_currency`)
- `sparse_flag` (optional diagnostics; schema `schemas.1A.yaml#/prep/sparse_flag`)

## Validation / receipt artefacts (parameter-scoped gate)
- `S5_VALIDATION.json` (written alongside weights cache partition)
- `_passed.flag` (hash over `S5_VALIDATION.json`)


---
# 1A.S6 artefacts/policies/configs (from state.1A.s6.expanded.md only)

## Inputs / references
- Upstream datasets:
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`)
  - `rng_event_ztp_final` (schema `schemas.layer1.yaml#/rng/events/ztp_final`)
  - `ccy_country_weights_cache` (schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`)
  - `merchant_currency` (optional; schema `schemas.1A.yaml#/prep/merchant_currency`)
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `crossborder_eligibility_flags` (gate; `is_eligible==true`)
  - S5 PASS receipt (`S5_VALIDATION.json` + `_passed.flag`) for the same `parameter_hash`
- Schema / dictionary authority:
  - `schemas.ingress.layer1.yaml`
  - `schemas.1A.yaml`
  - `schemas.layer1.yaml`
  - `dataset_dictionary.layer1.1A.yaml`
- S6 policy set (governed parameters):
  - S6 policy file(s) registered under `schemas.layer1.yaml#/policy/s6_selection` (basenames enumerated in S0.2.2 governed set 𝓟)

## Outputs / datasets (seed + parameter-scoped logs)
- `rng_event.gumbel_key` (schema `schemas.layer1.yaml#/rng/events/gumbel_key`)
  - `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `rng_audit_log` (core RNG log)
- `rng_trace_log` (core RNG trace; appended after each event)
- `s6_membership` (optional convenience surface; schema `schemas.1A.yaml#/s6/membership`)
  - partition `{seed, parameter_hash}`

## Validation / receipt artefacts (seed + parameter-scoped gate)
- `S6_VALIDATION.json` (path `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/`)
- `_passed.flag` (hash over receipt files)
- `S6_VALIDATION_DETAIL.jsonl` (optional per-merchant detail)


---

# 1A.S7 artefacts/policies/configs (from state.1A.s7.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.ingress.layer1.yaml`
  - `schemas.1A.yaml`
  - `schemas.layer1.yaml`
- Dataset dictionary: `dataset_dictionary.layer1.1A.yaml`
- Numeric policy artefacts (S0.8):
  - `numeric_policy.json`
  - `math_profile_manifest.json`
- Upstream datasets:
  - `rng_event.nb_final` (schema `schemas.layer1.yaml#/rng/events/nb_final`)
  - `rng_event.ztp_final` (schema `schemas.layer1.yaml#/rng/events/ztp_final`)
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`)
  - `ccy_country_weights_cache` (schema `schemas.1A.yaml#/prep/ccy_country_weights_cache`)
  - `s6_membership` (optional; schema `schemas.1A.yaml#/s6/membership`)
  - `rng_event.gumbel_key` (schema `schemas.layer1.yaml#/rng/events/gumbel_key`)
  - `merchant_currency` (optional; schema `schemas.1A.yaml#/prep/merchant_currency`)
- PASS receipts (gates):
  - `S5_VALIDATION.json` + `_passed.flag` (for weights)
  - `S6_VALIDATION.json` + `_passed.flag` (for membership, if read)

## Outputs / datasets (logs-only)
- `rng_event.residual_rank` (schema `schemas.layer1.yaml#/rng/events/residual_rank`)
- `rng_trace_log` (schema `schemas.layer1.yaml#/rng/core/rng_trace_log`; append after each event)
- `rng_event.dirichlet_gamma_vector` (feature-flag; schema `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector`)

## Optional sidecars
- `_MANIFEST.json` (optional folder manifest for output partitions)


---

# 1A.S8 artefacts/policies/configs (from state.1A.s8.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.1A.yaml` (egress + S3 anchors)
  - `schemas.layer1.yaml` (RNG/core logs + event families)
  - `schemas.ingress.layer1.yaml` (FK targets, ISO registry)
- Dataset dictionary: `dataset_dictionary.layer1.1A.yaml`
- Numeric policy artefacts / attestation:
  - `numeric_policy_attest.json` (S0 validation bundle; must have passed)
  - `numeric_policy_profile` (registry-pinned)
- Upstream datasets:
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`)
  - `rng_event.nb_final` (schema `schemas.layer1.yaml#/rng/events/nb_final`)
  - `s3_integerised_counts` (optional; schema `schemas.1A.yaml#/s3/integerised_counts`)
  - `s6_membership` (optional; schema `schemas.1A.yaml#/s6/membership`)
  - `rng_event.gumbel_key` (schema `schemas.layer1.yaml#/rng/events/gumbel_key`)
  - `rng_event.ztp_final` (schema `schemas.layer1.yaml#/rng/events/ztp_final`)
  - `rng_event.residual_rank` (schema `schemas.layer1.yaml#/rng/events/residual_rank`)
  - `s3_site_sequence` (optional; schema `schemas.1A.yaml#/s3/site_sequence`)
- PASS receipts (gates):
  - `S6_VALIDATION.json` + `_passed.flag` (for `s6_membership`, if read)
  - `validation_bundle_1A` + `_passed.flag` (egress consumer gate for `outlet_catalogue`)

## Outputs / datasets
- `outlet_catalogue` (egress; schema `schemas.1A.yaml#/egress/outlet_catalogue`)

## Outputs / logs (instrumentation)
- `rng_event.sequence_finalize` (schema `schemas.layer1.yaml#/rng/events/sequence_finalize`)
- `rng_event.site_sequence_overflow` (schema `schemas.layer1.yaml#/rng/events/site_sequence_overflow`)
- `rng_trace_log` (schema `schemas.layer1.yaml#/rng/core/rng_trace_log`; append after each event)
- `rng_audit_log` (schema `schemas.layer1.yaml#/rng/core/rng_audit_log`)

## Validation bundle artefacts (fingerprint-scoped)
- `rng_accounting.json`
- `s8_metrics.json`
- `egress_checksums.json`

# 1A.S9 artefacts/policies/configs (from state.1A.s9.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.layer1.yaml`
  - `schemas.1A.yaml`
  - `schemas.ingress.layer1.yaml`
- Dataset dictionary: `dataset_dictionary.layer1.1A.yaml`
- Numeric policy artefacts:
  - `math_profile_manifest.json`
- Egress + tables in scope:
  - `outlet_catalogue` (schema `schemas.1A.yaml#/egress/outlet_catalogue`)
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`)
  - `s3_integerised_counts` (optional; schema `schemas.1A.yaml#/s3/integerised_counts`)
  - `s3_site_sequence` (optional; schema `schemas.1A.yaml#/s3/site_sequence`)
- RNG logs/events in scope:
  - `rng_audit_log` (schema `schemas.layer1.yaml#/rng/core/rng_audit_log`)
  - `rng_trace_log` (schema `schemas.layer1.yaml#/rng/core/rng_trace_log`)
  - Event families under `schemas.layer1.yaml#/rng/events/*` for 1A (hurdle/gamma/poisson/ztp/gumbel/residual_rank/sequence_finalize/site_sequence_overflow)
- Membership surfaces (choose one, with gate):
  - `s6_membership` (schema `schemas.1A.yaml#/alloc/membership`) + `s6_validation_receipt` gate (`schemas.layer1.yaml#/validation/s6_receipt`)
  - `rng_event.gumbel_key` (schema `schemas.layer1.yaml#/rng/events/gumbel_key`)
- FK target:
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)

## Outputs / validation bundle (fingerprint-scoped)
- `validation_bundle_1A` (schema `schemas.1A.yaml#/validation/validation_bundle`)
  - `MANIFEST.json`
  - `parameter_hash_resolved.json`
  - `manifest_fingerprint_resolved.json`
  - `rng_accounting.json`
  - `s9_summary.json`
  - `egress_checksums.json`
  - `index.json`
  - `param_digest_log.jsonl` (if present from S0)
  - `fingerprint_artifacts.jsonl` (if present from S0)
  - `numeric_policy_attest.json` (if present from S0)
- `_passed.flag` (hash over files listed in `index.json`)


---
