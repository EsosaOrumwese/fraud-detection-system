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


---

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

# 1B.S0 artefacts/policies/configs (from state.1B.s0.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.layer1.yaml`
  - `schemas.ingress.layer1.yaml`
  - `schemas.1A.yaml`
  - `schemas.1B.yaml`
- Dataset dictionaries:
  - `dataset_dictionary.layer1.1A.yaml`
  - `dataset_dictionary.layer1.1B.yaml`
- Validation bundle gate (1A):
  - `validation_bundle_1A` (schema `schemas.1A.yaml#/validation/validation_bundle`)
  - `_passed.flag` (ASCII-lex hash over `index.json`-listed files)
  - `index.json` (bundle index; relative paths)
- Egress surfaces read after PASS:
  - `outlet_catalogue` (schema `schemas.1A.yaml#/egress/outlet_catalogue`)
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`)
- Reference / FK targets pinned by S0 for 1B:
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `world_countries` (schema `schemas.ingress.layer1.yaml#/world_countries`)
  - `population_raster_2025` (schema `schemas.ingress.layer1.yaml#/population_raster_2025`)
  - `tz_world_2025a` (schema `schemas.ingress.layer1.yaml#/tz_world_2025a`)
- Numeric policy artefacts (lineage):
  - `numeric_policy.json`
  - `math_profile_manifest.json`

## Outputs / datasets (fingerprint-scoped)
- `s0_gate_receipt_1B`
  - Path: `data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json`
  - Schema: `schemas.1B.yaml#/validation/s0_gate_receipt`


---

# 1B.S1 artefacts/policies/configs (from state.1B.s1.expanded.md only)

## Inputs / references
- Schema authority bundle: `schemas.1B.yaml` (tile_index anchor)
- Dataset dictionary: `dataset_dictionary.layer1.1B.yaml` (tile_index ID/path/partition/sort)
- Ingress reference surfaces:
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `world_countries` (schema `schemas.ingress.layer1.yaml#/world_countries`)
  - `population_raster_2025` (schema `schemas.ingress.layer1.yaml#/population_raster_2025`)
  - `tz_world_2025a` (schema `schemas.ingress.layer1.yaml#/tz_world_2025a`, listed but not consumed)
- Gate context (read-only reference): `schemas.1A.yaml#/validation/validation_bundle` (S1 itself does not read 1A egress)

## Outputs / datasets
- `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)

## Deliverables / reports
- `s1_run_report.json` (single-object run report)
- Per-country summary JSON lines (optional)


---

# 1B.S2 artefacts/policies/configs (from state.1B.s2.expanded.md only)

## Inputs / references
- Schema authority bundle: `schemas.1B.yaml` (tile_weights, tile_index anchors)
- Dataset dictionary: `dataset_dictionary.layer1.1B.yaml` (tile_weights and tile_index IDs/paths/partitions/sort)
- Upstream dataset:
  - `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)
- Ingress reference surfaces (sealed, read-only):
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `world_countries` (schema `schemas.ingress.layer1.yaml#/world_countries`)
  - `population_raster_2025` (schema `schemas.ingress.layer1.yaml#/population_raster_2025`)
  - `tz_world_2025a` (schema `schemas.ingress.layer1.yaml#/tz_world_2025a`, provenance only)

## Outputs / datasets
- `tile_weights` (schema `schemas.1B.yaml#/prep/tile_weights`)

## Deliverables / reports
- `s2_run_report.json` (single-object run report)
- Per-country normalization summary (JSON lines)


---

# 1B.S3 artefacts/policies/configs (from state.1B.s3.expanded.md only)

## Inputs / references
- Schema authority bundles:
  - `schemas.1B.yaml` (anchors: `#/plan/s3_requirements`, `#/prep/tile_weights`, `#/validation/s0_gate_receipt`)
  - `schemas.1A.yaml` (anchors: `#/egress/outlet_catalogue`, `#/s3/candidate_set`)
  - `schemas.ingress.layer1.yaml` (anchor: `#/iso3166_canonical_2024`)
- Gate receipt:
  - `s0_gate_receipt_1B` (schema `schemas.1B.yaml#/validation/s0_gate_receipt`)
- Sealed inputs (from the S0 receipt; S3 reads only the ones listed under "Inputs S3 will actually read"):
  - `outlet_catalogue` (schema `schemas.1A.yaml#/egress/outlet_catalogue`)
  - `s3_candidate_set` (schema `schemas.1A.yaml#/s3/candidate_set`, sealed not read)
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
  - `world_countries` (schema `schemas.ingress.layer1.yaml#/world_countries`, sealed not read)
  - `population_raster_2025` (schema `schemas.ingress.layer1.yaml#/population_raster_2025`, sealed not read)
  - `tz_world_2025a` (sealed not read)
- Additional S3 read:
  - `tile_weights` (schema `schemas.1B.yaml#/prep/tile_weights`)
- Sealed but not read by S3 (declared for lineage/forward use):
  - `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)
  - `validation_bundle_1A` (basis of the S0 gate proof)

## Outputs / datasets
- `s3_requirements` (schema `schemas.1B.yaml#/plan/s3_requirements`)

## Deliverables / reports (outside the dataset partition)
- S3 run report (single JSON object; required fields include `seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, `merchants_total`, `countries_total`, `source_rows_total`, `ingress_versions`, `determinism_receipt`)
- Determinism receipt `{partition_path, sha256_hex}` (composite SHA-256 over partition files)
- Optional summaries:
  - Per-merchant summary (countries, `n_sites_total`, pairs)
  - Run-scale health counters (e.g., `fk_country_violations`, `coverage_missing_countries`)

## Failure / event artefacts
- Failure record with `{code, scope?, reason, seed, manifest_fingerprint, parameter_hash}` (optionally `merchant_id`, `legal_country_iso`)
- `S3_ERROR` failure event (structured; required on failure)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- Gate law: `s0_gate_receipt_1B` proves PASS before reading `outlet_catalogue` ("No PASS, no read")
- Write-once/atomic publish; determinism receipt stored in the run report; evidence kept outside the dataset partition (retain >= 30 days)


---

# 1B.S4 artefacts/policies/configs (from state.1B.s4.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_1B` (schema `schemas.1B.yaml#/validation/s0_gate_receipt`)
- Required datasets (reads):
  - `s3_requirements` (schema `schemas.1B.yaml#/plan/s3_requirements`)
  - `tile_weights` (schema `schemas.1B.yaml#/prep/tile_weights`)
  - `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
- Sealed but not read:
  - `outlet_catalogue` (upstream egress)
  - `s3_candidate_set` (inter-country order authority)
- Disallowed surfaces (must not read):
  - `world_countries`
  - `population_raster_2025`
  - `tz_world_2025a`

## Outputs / datasets
- `s4_alloc_plan` (schema `schemas.1B.yaml#/plan/s4_alloc_plan`)

## Deliverables / reports (outside the dataset partition)
- S4 run report (single JSON object; required fields include `seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, `merchants_total`, `pairs_total`, `alloc_sum_equals_requirements`, `ingress_versions`, `determinism_receipt`)
- Determinism receipt `{partition_path, sha256_hex}` (composite SHA-256 over partition files)
- Optional summaries:
  - Per-merchant summary (countries, `n_sites_total`, pairs)
  - Run-scale health counters (`fk_country_violations`, `coverage_missing_countries`, `tile_not_in_index`)

## Failure / event artefacts
- Failure record with `{code, scope?, reason, seed, manifest_fingerprint, parameter_hash}` (optionally `merchant_id`, `legal_country_iso`)
- `S4_ERROR` failure event (structured; required on failure)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- Integer arithmetic requirement: use >=128-bit intermediates or bignum for `weight_fp x n_sites` and related sums; overflow is a hard error
- S4 is RNG-free and writes no RNG logs
- Gate law: rely on `s0_gate_receipt_1B` (no re-hash of the 1A bundle) before reads
- Write-once/atomic publish; determinism receipt stored in the run report; evidence kept outside the dataset partition (retain >= 30 days)


---

# 1B.S5 artefacts/policies/configs (from state.1B.s5.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_1B` (schema `schemas.1B.yaml#/validation/s0_gate_receipt`)
- Required datasets (reads):
  - `s4_alloc_plan` (schema `schemas.1B.yaml#/plan/s4_alloc_plan`)
  - `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)
  - `iso3166_canonical_2024` (schema `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`)
- Optional diagnostics:
  - `s3_requirements` (same identity as S4; not required for assignment logic)
- Sealed but not read by S5:
  - `outlet_catalogue`
  - `s3_candidate_set`
  - `tile_weights`
- Disallowed surfaces (must not read):
  - `world_countries`
  - `population_raster_2025`
  - `tz_world_2025a`

## Outputs / datasets
- `s5_site_tile_assignment` (schema `schemas.1B.yaml#/plan/s5_site_tile_assignment`)

## Outputs / RNG logs
- `site_tile_assign` RNG events (schema `schemas.layer1.yaml#/rng/events/site_tile_assign`)
  - `logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`

## Deliverables / reports (outside the dataset partition)
- S5 run report (single JSON object; required fields include `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `pairs_total`, `rng_events_emitted`, `determinism_receipt`)
- Determinism receipt `{partition_path, sha256_hex}` (composite SHA-256 over dataset partition files only)
- Optional summaries:
  - Per-merchant summary (countries, `sites_total`, `tiles_distinct`, `assignments_by_country`)
  - RNG budgeting summary (`expected_events`, `actual_events`)
  - Health counters (`fk_country_violations`, `tile_not_in_index`, `quota_mismatches`, `dup_sites`)

## Failure / event artefacts
- Failure record with `{code, scope?, reason, seed, manifest_fingerprint, parameter_hash}` (optionally `merchant_id`, `legal_country_iso`)
- `S5_ERROR` failure event (structured; required on failure)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- RNG envelope: substream `site_tile_assign`, budget is exactly one draw per assigned site, single `run_id` per publish
- Gate law: rely on `s0_gate_receipt_1B` (no re-hash of the 1A bundle) before reads
- Write-once/atomic publish; determinism receipt stored in the run report; evidence kept outside the dataset partition (retain >= 30 days)


---

# 1B.S6 artefacts/policies/configs (from state.1B.s6.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_1B` (authorises reads after PASS)
- Required datasets (reads):
  - `s5_site_tile_assignment` (schema `schemas.1B.yaml#/plan/s5_site_tile_assignment`)
  - `tile_index` (schema `schemas.1B.yaml#/prep/tile_index`)
  - `world_countries` (country polygons; point-in-country authority)
- FK reference surface:
  - canonical ISO-3166 ingress surface (FK target for `legal_country_iso`)

## Outputs / datasets
- `s6_site_jitter` (schema `schemas.1B.yaml#/plan/s6_site_jitter`)

## Outputs / RNG logs
- `rng_event_in_cell_jitter` (schema `schemas.layer1.yaml#/rng/events/in_cell_jitter`)
  - `logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- RNG core logs:
  - `rng_audit_log`
  - `rng_trace_log` (append one row per RNG event)

## Deliverables / reports (forwarded to S7; outside dataset partition)
- S6 run-report counters (JSON object with `identity`, `counts`, `validation_counters`, `by_country`)
  - `identity`: `{seed, parameter_hash, manifest_fingerprint, run_id}`
  - `counts`: `sites_total`, `rng.events_total`, `rng.draws_total`, `rng.blocks_total`, `rng.counter_span`
  - `validation_counters`: `fk_tile_index_failures`, `point_outside_pixel`, `point_outside_country`, `path_embed_mismatches`
  - `by_country`: per-ISO `sites`, `rng_events`, `rng_draws`, `outside_pixel`, `outside_country`

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- RNG envelope: per-attempt events under `in_cell_jitter`, `blocks=1`, `draws="2"`, `sigma_lat_deg=0.0`, `sigma_lon_deg=0.0` (uniform-in-pixel lane)
- Bounded resample policy `MAX_ATTEMPTS` (abort on exhaustion; resample attempts appear as multiple events per site)
- Gate law: rely on `s0_gate_receipt_1B` (No PASS, no read)
- Write-once/atomic publish for `s6_site_jitter`; RNG logs append-only; file order non-authoritative


---

# 1B.S7 artefacts/policies/configs (from state.1B.s7.expanded.md only)

## Inputs / references
- Gate condition (before reading 1A egress):
  - 1A validation bundle `_passed.flag` must be valid for `manifest_fingerprint` (No PASS, no read)
- Required datasets (reads):
  - `s5_site_tile_assignment` (schema `schemas.1B.yaml#/plan/s5_site_tile_assignment`)
  - `s6_site_jitter` (schema `schemas.1B.yaml#/plan/s6_site_jitter`)
  - `tile_bounds` (schema `schemas.1B.yaml#/prep/tile_bounds`)
  - `outlet_catalogue` (1A egress; coverage parity check)

## Outputs / datasets
- `s7_site_synthesis` (schema `schemas.1B.yaml#/plan/s7_site_synthesis`)

## Downstream reference (not produced here)
- `site_locations` (S8 egress; schema `schemas.1B.yaml#/egress/site_locations`, partitions `[seed, fingerprint]`)

## Deliverables / reports (forwarded to S8; outside dataset partition)
- S7 run-summary counters (JSON object with keys `identity`, `sizes`, `validation_counters`, `by_country`, `gates`)
- Optional determinism receipt `{partition_path, sha256_hex}` for the S7 partition

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- RNG-free; no new RNG logs introduced
- Path-embed equality for `manifest_fingerprint` is binding
- Inside-pixel conformance check against S1 `tile_bounds`; optional point-in-country recheck allowed
- No inter-country order encoding (order authority remains 1A `s3_candidate_set`)


---

# 1B.S8 artefacts/policies/configs (from state.1B.s8.expanded.md only)

## Inputs / references
- Required dataset (read):
  - `s7_site_synthesis` (schema `schemas.1B.yaml#/plan/s7_site_synthesis`)

## Outputs / datasets
- `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`, final_in_layer)

## Deliverables / reports (outside dataset partition)
- S8 run-summary JSON with keys `identity`, `sizes`, `validation_counters`, `by_country`

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- Egress is order-free; inter-country order remains via 1A `s3_candidate_set`
- Partition shift: drop `parameter_hash` and publish under `[seed, fingerprint]`
- Write-once/atomic publish; file order non-authoritative


---

# 1B.S9 artefacts/policies/configs (from state.1B.s9.expanded.md only)

## Inputs / references
- Required datasets (reads):
  - `s7_site_synthesis` (schema `schemas.1B.yaml#/plan/s7_site_synthesis`)
  - `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`)
- Required RNG evidence (reads):
  - `rng_event_site_tile_assign` (schema `schemas.layer1.yaml#/rng/events/site_tile_assign`)
  - `rng_event_in_cell_jitter` (schema `schemas.layer1.yaml#/rng/events/in_cell_jitter`)
  - `rng_audit_log` (core RNG log)
  - `rng_trace_log` (core RNG log)

## Outputs / validation bundle (fingerprint-scoped)
- Bundle root: `data/layer1/1B/validation/fingerprint={manifest_fingerprint}/`
- Required files:
  - `MANIFEST.json`
  - `parameter_hash_resolved.json`
  - `manifest_fingerprint_resolved.json`
  - `rng_accounting.json`
  - `s9_summary.json`
  - `egress_checksums.json`
  - `index.json` (1A bundle-index schema)
  - `_passed.flag` (only on success)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/writer sort/licence; Artefact Registry records provenance/licences
- Hashing/index law: `_passed.flag` is SHA-256 over raw bytes of all files listed in `index.json` (ASCII-lex by `path`, flag excluded)
- Gate law: consumers must verify `_passed.flag` before reading 1B egress (No PASS, no read)
- Publish posture: write-once, stage+fsync+atomic move; file order non-authoritative; omit `_passed.flag` on failure


---

# 2A.S0 artefacts/policies/configs (from state.2A.s0.expanded.md only)

## Inputs / references
- Upstream PASS artefacts (1B):
  - `validation_bundle_1B` (fingerprint-scoped bundle)
  - `validation_passed_flag_1B` (`_passed.flag`)
- Upstream egress pointer:
  - `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`)
- Timezone assets:
  - `tz_world_<release>` polygons (schema `schemas.ingress.layer1.yaml#/tz_world_2025a` example)
  - IANA tzdb archive + release metadata (e.g., `tzdata2025a.tar.gz`, `zoneinfo_version.yml`)
- Policy/config inputs:
  - `config/timezone/tz_overrides.yaml`
  - `config/timezone/tz_nudge.yml`
- Optional auxiliaries (only if referenced by later 2A states):
  - `iso3166_canonical_2024`
  - `world_countries`

## Outputs / datasets
- `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- `sealed_inputs_v1` inventory (schema `schemas.2A.yaml#/manifests/sealed_inputs_v1`)

## Deliverables / reports
- S0 run-report JSON (single object; fields include upstream gate results, sealed input counts/digests, tz asset summary, determinism receipt)
- Determinism receipt for the fingerprint partition (directory hash)
- Structured log records (`GATE`, `SEAL`, `HASH`, `EMIT`, `DETERMINISM`, `VALIDATION`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify 1B `_passed.flag` before admitting `site_locations` (No PASS, no read)
- Sealing rules: content-addressed assets, no aliasing/duplicates, explicit version tags, minimal sanity checks (e.g., CRS=WGS84)
- Write-once/atomic publish; path-embed equality for `manifest_fingerprint` is binding


---

# 2A.S1 artefacts/policies/configs (from state.2A.s1.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- Required datasets (reads):
  - `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`)
  - `tz_world_<release>` polygons (schema `schemas.ingress.layer1.yaml#/tz_world_2025a` example)
  - `tz_nudge` policy (schema `schemas.2A.yaml#/policy/tz_nudge_v1`)

## Outputs / datasets
- `s1_tz_lookup` (schema `schemas.2A.yaml#/plan/s1_tz_lookup`)

## Deliverables / reports
- S1 run-report JSON (single object with gate verification, input IDs, counts, and diagnostics)
- Structured log records (`GATE`, `INPUTS`, `LOOKUP`, `VALIDATION`, `EMIT`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify the 2A.S0 receipt before reading `site_locations` (No PASS, no read)
- RNG-free; deterministic point-in-polygon assignment with single î-nudge (record `nudge_*` when applied)
- Write-once/atomic publish; path-embed equality for `manifest_fingerprint` is binding


---

# 2A.S2 artefacts/policies/configs (from state.2A.s2.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- Required datasets (reads):
  - `s1_tz_lookup` (schema `schemas.2A.yaml#/plan/s1_tz_lookup`)
  - `tz_overrides` policy (schema `schemas.2A.yaml#/policy/tz_overrides_v1`)
  - `tz_world_<release>` polygons (schema `schemas.ingress.layer1.yaml#/tz_world_2025a` example; membership validation)
- Optional input (only if MCC overrides are used):
  - merchant-to-MCC mapping (programme-specific; must be sealed in S0)

## Outputs / datasets
- `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`, final_in_layer)

## Deliverables / reports
- S2 run-report JSON (single object with gate verification, override counts, and output path)
- Structured log records (`GATE`, `INPUTS`, `OVERRIDES`, `VALIDATION`, `EMIT`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify the 2A.S0 receipt before reading inputs (No PASS, no read)
- Override precedence: site > mcc > country; active iff expiry is null or on/after S0 receipt date
- RNG-free; `created_utc` set to S0 receipt `verified_at_utc`; carry through `nudge_*` unchanged
- Write-once/atomic publish; path-embed equality for `manifest_fingerprint` is binding


---

# 2A.S3 artefacts/policies/configs (from state.2A.s3.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- Required inputs:
  - `tzdb_release` (schema `schemas.2A.yaml#/ingress/tzdb_release_v1`)
  - `tz_world_<release>` polygons (schema `schemas.ingress.layer1.yaml#/tz_world_2025a` example; tzid coverage domain)

## Outputs / datasets
- `tz_timetable_cache` (schema `schemas.2A.yaml#/cache/tz_timetable_cache`)

## Deliverables / reports
- S3 run-report JSON (single object with gate verification, tzdb parsing, cache summary, coverage counts)
- Structured log records (`GATE`, `INPUTS`, `TZDB_PARSE`, `COMPILE`, `CANONICALISE`, `COVERAGE`, `VALIDATION`, `EMIT`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify the 2A.S0 receipt before reading inputs (No PASS, no read)
- RNG-free; `created_utc` set to S0 receipt `verified_at_utc`
- Fingerprint-scoped output `[fingerprint]` only; path-embed equality for `manifest_fingerprint` is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2A.S4 artefacts/policies/configs (from state.2A.s4.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- Required datasets (reads):
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
  - `tz_timetable_cache` (schema `schemas.2A.yaml#/cache/tz_timetable_cache`)

## Outputs / datasets
- `s4_legality_report` (schema `schemas.2A.yaml#/validation/s4_legality_report`)

## Deliverables / reports
- S4 run-report JSON (single object with gate verification, cache IDs, legality counts)
- Structured log records (`GATE`, `INPUTS`, `CHECK`, `VALIDATION`, `EMIT`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify the 2A.S0 receipt before reading inputs (No PASS, no read)
- RNG-free; `generated_utc` set to S0 receipt `verified_at_utc`
- Seed+fingerprint output `[seed, fingerprint]`; path-embed equality is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2A.S5 artefacts/policies/configs (from state.2A.s5.expanded.md only)

## Inputs / references
- Gate receipt:
  - `s0_gate_receipt_2A` (schema `schemas.2A.yaml#/validation/s0_gate_receipt_v1`)
- Required evidence:
  - `tz_timetable_cache` (schema `schemas.2A.yaml#/cache/tz_timetable_cache`)
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`) for seed discovery
  - `s4_legality_report` (schema `schemas.2A.yaml#/validation/s4_legality_report`) per discovered seed

## Outputs / datasets
- `validation_bundle_2A` (schema `schemas.2A.yaml#/validation/validation_bundle_2A`)
- `bundle_index_v1` (schema `schemas.2A.yaml#/validation/bundle_index_v1`)
- `validation_passed_flag_2A` (schema `schemas.2A.yaml#/validation/passed_flag`)

## Deliverables / reports
- S5 run-report JSON (single object with seed discovery, evidence checks, digest/flag status)
- Structured log records (`GATE`, `DISCOVERY`, `EVIDENCE`, `INDEX`, `DIGEST`, `VALIDATION`, `EMIT`)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify the 2A.S0 receipt before any reads (No PASS, no read)
- Bundle law: index lists relative paths in ASCII-lex order; `_passed.flag` hashes raw bytes of indexed files (flag excluded)
- Fingerprint-scoped output `[fingerprint]` only; path-embed equality is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2B.S0 artefacts/policies/configs (from state.2B.s0.expanded.md only)

## Inputs / references
- Upstream gate artefacts (1B):
  - `validation_bundle_1B` (bundle root)
  - `_passed.flag` (companion flag)
- Required pins:
  - `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`)
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
- Policy packs (fingerprint-scoped; IDs per Dictionary):
  - `route_rng_policy_v1`
  - `alias_layout_policy_v1`
  - `day_effect_policy_v1`
  - `virtual_edge_policy_v1`
- Optional cache (if declared for the fingerprint):
  - `tz_timetable_cache` (schema `schemas.2A.yaml#/cache/tz_timetable_cache`)

## Outputs / datasets
- `s0_gate_receipt_2B` (schema `schemas.2B.yaml#/validation/s0_gate_receipt_v1`)
- `sealed_inputs_v1` inventory (schema `schemas.2B.yaml#/validation/sealed_inputs_v1`)

## Deliverables / reports
- S0 run-report JSON (stdout; gate verification, inventory summary, validators)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- Gate law: verify 1B bundle hash from index (ASCII-lex order, flag excluded) before any egress read
- Dictionary-only resolution; no literal paths; no network fetches
- Write-once/atomic publish; fingerprint-only outputs; path-embed equality for `manifest_fingerprint` is binding


---

# 2B.S1 artefacts/policies/configs (from state.2B.s1.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `site_locations` (schema `schemas.1B.yaml#/egress/site_locations`)
  - `alias_layout_policy_v1` (schema `schemas.2B.yaml#/policy/alias_layout_policy_v1`)
- Optional pins (all-or-none; read-only):
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
  - `tz_timetable_cache` (schema `schemas.2A.yaml#/cache/tz_timetable_cache`)

## Outputs / datasets
- `s1_site_weights` (schema `schemas.2B.yaml#/plan/s1_site_weights`)

## Deliverables / reports
- S1 run-report JSON (stdout; gate, policy, transform metrics, validators)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; deterministic normalisation + quantisation per `alias_layout_policy_v1`
- `created_utc` set to S0 receipt `verified_at_utc`
- Output partition `[seed, fingerprint]`; PK writer order; path-embed equality is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2B.S2 artefacts/policies/configs (from state.2B.s2.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `s1_site_weights` (schema `schemas.2B.yaml#/plan/s1_site_weights`)
  - `alias_layout_policy_v1` (schema `schemas.2B.yaml#/policy/alias_layout_policy_v1`)

## Outputs / datasets
- `s2_alias_index` (schema `schemas.2B.yaml#/plan/s2_alias_index`)
- `s2_alias_blob` (schema `schemas.2B.yaml#/binary/s2_alias_blob`)

## Deliverables / reports
- S2 run-report JSON (stdout; gate, policy, encode/serialize metrics, validators)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; deterministic grid reconstruction + alias encode per `alias_layout_policy_v1`
- `created_utc` set to S0 receipt `verified_at_utc`
- Output partitions `[seed, fingerprint]`; index writer order by `merchant_id`; path-embed equality is binding
- Write-once/atomic publish; blob digest `blob_sha256` must match raw bytes


---

# 2B.S3 artefacts/policies/configs (from state.2B.s3.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `s1_site_weights` (schema `schemas.2B.yaml#/plan/s1_site_weights`)
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
  - `day_effect_policy_v1` (schema `schemas.2B.yaml#/policy/day_effect_policy_v1`)

## Outputs / datasets
- `s3_day_effects` (schema `schemas.2B.yaml#/plan/s3_day_effects`)

## Deliverables / reports
- S3 run-report JSON (stdout; gate, policy, RNG accounting, coverage)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-bounded; one Philox draw per row per `day_effect_policy_v1`; counters recorded
- `created_utc` set to S0 receipt `verified_at_utc`
- Output partition `[seed, fingerprint]`; PK writer order; path-embed equality is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2B.S4 artefacts/policies/configs (from state.2B.s4.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `s1_site_weights` (schema `schemas.2B.yaml#/plan/s1_site_weights`)
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
  - `s3_day_effects` (schema `schemas.2B.yaml#/plan/s3_day_effects`)

## Outputs / datasets
- `s4_group_weights` (schema `schemas.2B.yaml#/plan/s4_group_weights`)

## Deliverables / reports
- S4 run-report JSON (stdout; validators, counts, normalisation metrics, samples)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; deterministic tz-group aggregation + renormalisation using S3 `gamma` values
- Normalisation tolerance uses the program epsilon constant (per spec)
- `created_utc` set to S0 receipt `verified_at_utc`
- Output partition `[seed, fingerprint]`; PK writer order; path-embed equality is binding
- Write-once/atomic publish; file order non-authoritative


---

# 2B.S5 artefacts/policies/configs (from state.2B.s5.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Upstream reference:
  - `s3_day_effects` (day effects surface)
- Required inputs:
  - `s4_group_weights` (schema `schemas.2B.yaml#/plan/s4_group_weights`)
  - `s1_site_weights` (schema `schemas.2B.yaml#/plan/s1_site_weights`)
  - `site_timezones` (schema `schemas.2A.yaml#/egress/site_timezones`)
  - `s2_alias_index` (schema `schemas.2B.yaml#/plan/s2_alias_index`)
  - `s2_alias_blob` (schema `schemas.2B.yaml#/binary/s2_alias_blob`)
  - `route_rng_policy_v1` (schema `schemas.2B.yaml#/policy/route_rng_policy_v1`)
  - `alias_layout_policy_v1` (schema `schemas.2B.yaml#/policy/alias_layout_policy_v1`)

## Outputs / datasets
- `rng_audit_log` (run-scoped JSONL core log)
- `rng_trace_log` (run-scoped JSONL core log)
- `rng_event.alias_pick_group` (per-arrival RNG event family)
- `rng_event.alias_pick_site` (per-arrival RNG event family)
- `s5_selection_log` (optional; schema `schemas.2B.yaml#/trace/s5_selection_log_row`, only if Dictionary registers it)

## Deliverables / reports
- S5 run-report JSON (stdout; policy digests, selections processed, RNG accounting, samples)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-bounded; two single-uniform draws per arrival per `route_rng_policy_v1`; events logged in order (group then site) with trace updates
- Alias layout/endianness/alignment from `alias_layout_policy_v1`; `s2_alias_index` header must match and `s2_alias_blob` digest validated
- `created_utc` set to S0 receipt `verified_at_utc`
- Inputs read at `[seed, fingerprint]`; RNG logs/events partition `[seed, parameter_hash, run_id]`; optional `s5_selection_log` partition `[seed, parameter_hash, run_id, utc_day]` with `manifest_fingerprint` as a column
- Write-once/atomic publish; no mandatory persisted egress dataset


---

# 2B.S6 artefacts/policies/configs (from state.2B.s6.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required policies (token-less, S0-sealed):
  - `route_rng_policy_v1` (schema `schemas.2B.yaml#/policy/route_rng_policy_v1`)
  - `virtual_edge_policy_v1` (schema `schemas.2B.yaml#/policy/virtual_edge_policy_v1`)
- Optional context (no decode in v1):
  - `s2_alias_index` (schema `schemas.2B.yaml#/plan/s2_alias_index`)
  - `s2_alias_blob` (schema `schemas.2B.yaml#/binary/s2_alias_blob`)

## Outputs / datasets
- `rng_audit_log` (run-scoped JSONL core log)
- `rng_trace_log` (run-scoped JSONL core log)
- `rng_event.cdn_edge_pick` (single-uniform RNG event family; one per virtual arrival)
- `s6_edge_log` (optional; schema `schemas.2B.yaml#/trace/s6_edge_log_row`, only if Dictionary registers it)

## Deliverables / reports
- S6 run-report JSON (stdout; sealed policy selection, virtual-arrival draw counts, RNG accounting, evidence summary)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-bounded; one single-uniform draw per virtual arrival on the `routing_edge` stream; no draws for non-virtual arrivals
- `created_utc` set to S0 receipt `verified_at_utc`
- Policies selected by exact S0-sealed path+digest; token-less policies use empty partition maps
- RNG logs/events partition `[seed, parameter_hash, run_id]`; optional `s6_edge_log` partition `[seed, parameter_hash, run_id, utc_day]` with `manifest_fingerprint` as a column
- Write-once/atomic publish; no mandatory fingerprint-scoped egress dataset


---

# 2B.S7 artefacts/policies/configs (from state.2B.s7.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `s2_alias_index` (schema `schemas.2B.yaml#/plan/s2_alias_index`)
  - `s2_alias_blob` (schema `schemas.2B.yaml#/binary/s2_alias_blob`)
  - `s3_day_effects` (schema `schemas.2B.yaml#/plan/s3_day_effects`)
  - `s4_group_weights` (schema `schemas.2B.yaml#/plan/s4_group_weights`)
- Policies (token-less, S0-sealed):
  - `alias_layout_policy_v1` (schema `schemas.2B.yaml#/policy/alias_layout_policy_v1`)
  - `route_rng_policy_v1` (schema `schemas.2B.yaml#/policy/route_rng_policy_v1`)
  - `virtual_edge_policy_v1` (schema `schemas.2B.yaml#/policy/virtual_edge_policy_v1`)
- Optional router diagnostics (run-scoped, if present):
  - `s5_selection_log` (schema `schemas.2B.yaml#/trace/s5_selection_log_row`)
  - `s6_edge_log` (schema `schemas.2B.yaml#/trace/s6_edge_log_row`)
  - `rng_audit_log` / `rng_trace_log` (Layer-1 core logs for reconciliation)

## Outputs / datasets
- `s7_audit_report` (schema `schemas.2B.yaml#/validation/s7_audit_report_v1`)

## Deliverables / reports
- S7 run-report JSON (stdout; diagnostic only)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; validates S2 alias parity, S3/S4 coherence, and optional router logs against Layer-1 RNG evidence
- `created_utc` set to S0 receipt `verified_at_utc`
- Inputs read at `[seed, fingerprint]`; optional logs at `[seed, parameter_hash, run_id, utc_day]`; policies selected by exact S0-sealed path+digest
- Output partition `[seed, fingerprint]`; path-embed equality is binding
- Write-once/atomic publish; `s7_audit_report` is the sole authoritative persisted output


---

# 2B.S8 artefacts/policies/configs (from state.2B.s8.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_2B`
  - `sealed_inputs_v1`
- Required inputs:
  - `s7_audit_report` (schema `schemas.2B.yaml#/validation/s7_audit_report_v1`)
  - `s2_alias_index` (schema `schemas.2B.yaml#/plan/s2_alias_index`)
  - `s2_alias_blob` (schema `schemas.2B.yaml#/binary/s2_alias_blob`)
  - `s3_day_effects` (schema `schemas.2B.yaml#/plan/s3_day_effects`)
  - `s4_group_weights` (schema `schemas.2B.yaml#/plan/s4_group_weights`)
- Policies (token-less, S0-sealed):
  - `alias_layout_policy_v1`
  - `route_rng_policy_v1`
  - `virtual_edge_policy_v1`

## Outputs / datasets
- `index.json` (validation bundle index; `{path, sha256_hex}` entries in ASCII-lex order)
- `_passed.flag` (single-line bundle digest; not listed in `index.json`)

## Deliverables / reports
- S8 run-report JSON (stdout; diagnostic bundle/seed summary)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; seed set is the intersection of seeds across `s2_alias_index`, `s3_day_effects`, `s4_group_weights`
- S7 audit reports must exist per seed and be PASS before publish
- `created_utc` set to S0 receipt `verified_at_utc`
- Bundle output is fingerprint-only (`data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`); path-embed equality is binding
- Write-once/atomic publish; index/flag hash law is canonical; no re-auditing
