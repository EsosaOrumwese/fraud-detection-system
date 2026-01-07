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


---

# 3A.S0 artefacts/policies/configs (from state.3A.s0.expanded.md only)

## Inputs / references
- Upstream PASS artefacts:
  - `validation_bundle_1A` + `_passed.flag`
  - `validation_bundle_1B` + `_passed.flag`
  - `validation_bundle_2A` + `_passed.flag`
- Upstream egress surfaces (sealed for 3A):
  - `outlet_catalogue` (1A egress)
  - `site_timezones` (2A egress)
  - `tz_timetable_cache` (2A cache)
  - `s4_legality_report` (2A validation; optional in later 3A diagnostics)
  - `tz_index_manifest` (optional 2A TZ index digest)
- Ingress/reference data:
  - `iso3166_canonical_2024`
  - `tz_world_2025a`
- Policy/prior configs (token-less, sealed in parameter_hash):
  - `zone_mixture_policy` (e.g., `zone_mixture_policy_3A`)
  - `country_zone_alphas` (e.g., `country_zone_alphas_3A`)
  - `zone_floor_policy` (e.g., `zone_floor_policy_3A`)
  - `day_effect_policy_v1` (2B policy sealed as a parameter input)
- Catalogue authorities (resolved by ID):
  - `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.2B.yaml`, `schemas.3A.yaml`
  - `dataset_dictionary.layer1.1A.yaml`, `dataset_dictionary.layer1.1B.yaml`, `dataset_dictionary.layer1.2A.yaml`, `dataset_dictionary.layer1.2B.yaml`, `dataset_dictionary.layer1.3A.yaml`
  - `artefact_registry_1A.yaml`, `artefact_registry_1B.yaml`, `artefact_registry_2A.yaml`, `artefact_registry_2B.yaml`, `artefact_registry_3A.yaml`

## Outputs / datasets
- `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
- `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)

## Deliverables / reports
- Segment-state run-report row (one per `(parameter_hash, manifest_fingerprint, seed)`)
- Metrics counters (sealed inputs totals and by-segment gauges)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; S0 verifies upstream 1A/1B/2A bundles and `_passed.flag` before sealing inputs
- `created_utc` set to the canonical S0 verified time; `seed` is metadata only for S0
- Output partition is fingerprint-only; path-embed equality is binding
- Write-once/atomic publish; no other persistent outputs beyond `s0_gate_receipt_3A` and `sealed_inputs_3A`


---

# 3A.S1 artefacts/policies/configs (from state.3A.s1.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required inputs:
  - `outlet_catalogue` (schema `schemas.1A.yaml#/egress/outlet_catalogue`)
  - `iso3166_canonical_2024` (ingress reference)
  - `tz_world_2025a` (ingress reference)
  - `zone_mixture_policy_3A` (schema `schemas.3A.yaml#/policy/zone_mixture_policy_3A`)
- Optional input:
  - `tz_timetable_cache` (2A cache manifest, for tz universe validation)

## Outputs / datasets
- `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)

## Deliverables / reports
- Segment-state run-report row (one per `(parameter_hash, manifest_fingerprint, seed)`)
- Metrics counters (pairs/escalations/zone counts per spec)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; escalation is deterministic from sealed inputs + mixture policy
- `s1_escalation_queue` is the sole authority for escalated vs monolithic pairs
- Output partition `[seed, fingerprint]`; path-embed equality is binding
- Write-once/atomic publish; no other datasets produced in S1


---

# 3A.S2 artefacts/policies/configs (from state.3A.s2.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required policy/prior inputs:
  - `country_zone_alphas_3A` (schema `schemas.3A.yaml#/policy/country_zone_alphas_v1`)
  - `zone_floor_policy_3A` (schema `schemas.3A.yaml#/policy/zone_floor_policy_v1`)
- Zone-universe references:
  - `iso3166_canonical_2024`
  - `tz_world_2025a` (or sealed `country_tz_universe` mapping if present)
- Optional hyperparameter packs (if present in sealed inputs)

## Outputs / datasets
- `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)

## Deliverables / reports
- Segment-state run-report row (parameter-scoped; includes manifest_fingerprint_ref)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; priors and floor/bump rules applied deterministically
- Output partition is `parameter_hash` only (no seed/fingerprint)
- `s2_country_zone_priors` is the sole authority for effective Dirichlet alpha vectors
- Write-once/atomic publish; no other datasets produced in S2


---

# 3A.S3 artefacts/policies/configs (from state.3A.s3.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required inputs:
  - `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)
  - `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)
- Structural references:
  - `iso3166_canonical_2024`
  - `country_tz_universe` (or equivalent sealed mapping, if present)
- RNG configuration (sealed policies):
  - Layer-1 RNG policy artefacts (philox/envelope)
  - 3A RNG layout policy (e.g., `zone_rng_policy_3A`) if registered/sealed

## Outputs / datasets
- `s3_zone_shares` (schema `schemas.3A.yaml#/plan/s3_zone_shares`)
- `rng_event_zone_dirichlet` (Layer-1 RNG event family; one per escalated merchant-country)
- `rng_audit_log` (run-scoped JSONL core log)
- `rng_trace_log` (run-scoped JSONL core log)

## Deliverables / reports
- Segment-state run-report row (run-scoped; includes RNG totals and `s3_zone_shares` counts)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-bounded; Dirichlet draws via Philox with `rng_event_zone_dirichlet` and trace reconciliation
- `s1_escalation_queue` is the escalation authority; `s2_country_zone_priors` is the alpha authority
- Output partition `[seed, fingerprint]`; RNG logs/events partition `[seed, parameter_hash, run_id]`
- Write-once/atomic publish; `s3_zone_shares` is the stochastic planning surface


---

# 3A.S4 artefacts/policies/configs (from state.3A.s4.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required inputs:
  - `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)
  - `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)
  - `s3_zone_shares` (schema `schemas.3A.yaml#/plan/s3_zone_shares`)
- Optional external references (if used for structural checks):
  - `iso3166_canonical_2024`
  - `country_tz_universe` or `tz_world_2025a`

## Outputs / datasets
- `s4_zone_counts` (schema `schemas.3A.yaml#/plan/s4_zone_counts`)

## Deliverables / reports
- Segment-state run-report row (run-scoped; integerisation totals)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; deterministic integerisation of S3 shares with count conservation
- `s1_escalation_queue` defines domain and `site_count`; `s2_country_zone_priors` defines `Z(c)`; `s3_zone_shares` defines draws
- Output partition `[seed, fingerprint]`; path-embed equality is binding
- Write-once/atomic publish; `s4_zone_counts` is the sole authoritative zone-count surface


---

# 3A.S5 artefacts/policies/configs (from state.3A.s5.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required internal inputs:
  - `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)
  - `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)
  - `s3_zone_shares` (schema `schemas.3A.yaml#/plan/s3_zone_shares`)
  - `s4_zone_counts` (schema `schemas.3A.yaml#/plan/s4_zone_counts`)
- Policy/prior artefacts (sealed; used for digests):
  - `zone_mixture_policy_3A` (schema `schemas.3A.yaml#/policy/zone_mixture_policy_3A`)
  - `country_zone_alphas_3A` (schema `schemas.3A.yaml#/policy/country_zone_alphas_v1`)
  - `zone_floor_policy_3A` (schema `schemas.3A.yaml#/policy/zone_floor_policy_v1`)
  - `day_effect_policy_v1` (schema `schemas.2B.yaml#/policy/day_effect_policy_v1`)

## Outputs / datasets
- `zone_alloc` (schema `schemas.3A.yaml#/egress/zone_alloc`)
- `zone_alloc_universe_hash` (schema `schemas.3A.yaml#/validation/zone_alloc_universe_hash`)

## Deliverables / reports
- Segment-state run-report row (run-scoped; zone_alloc counts and digest summary)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; S5 projects S4 counts into `zone_alloc` and computes digests for routing universe hash
- Output partition for `zone_alloc` is `[seed, fingerprint]`; `zone_alloc_universe_hash` is fingerprint-only
- `zone_alloc` is cross-layer egress; `zone_alloc_universe_hash` binds priors/mixture/floor/day-effect + `zone_alloc`
- Write-once/atomic publish; no other datasets produced in S5


---

# 3A.S6 artefacts/policies/configs (from state.3A.s6.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required internal inputs:
  - `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)
  - `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)
  - `s3_zone_shares` (schema `schemas.3A.yaml#/plan/s3_zone_shares`)
  - `s4_zone_counts` (schema `schemas.3A.yaml#/plan/s4_zone_counts`)
  - `zone_alloc` (schema `schemas.3A.yaml#/egress/zone_alloc`)
  - `zone_alloc_universe_hash` (schema `schemas.3A.yaml#/validation/zone_alloc_universe_hash`)
- RNG evidence:
  - `rng_event_zone_dirichlet` (Layer-1 RNG events for S3)
  - `rng_trace_log` (Layer-1 core log for S3 reconciliation)
- External references/policies (sealed in `sealed_inputs_3A` for checks):
  - `zone_mixture_policy_3A`
  - `country_zone_alphas_3A`
  - `zone_floor_policy_3A`
  - `day_effect_policy_v1`
  - `iso3166_canonical_2024`, `country_tz_universe` or `tz_world_2025a`

## Outputs / datasets
- `s6_validation_report_3A` (schema `schemas.3A.yaml#/validation/s6_validation_report_3A`)
- `s6_issue_table_3A` (schema `schemas.3A.yaml#/validation/s6_issue_table_3A`)
- `s6_receipt_3A` (schema `schemas.3A.yaml#/validation/s6_receipt_3A`)

## Deliverables / reports
- Segment-state run-report row (S6 run status + overall_status)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; read-only structural validation across S0-S5 + RNG accounting for S3
- Outputs are fingerprint-scoped; path-embed equality is binding
- Write-once/atomic publish; S6 outputs are authoritative for segment validation status


---

# 3A.S7 artefacts/policies/configs (from state.3A.s7.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3A` (schema `schemas.3A.yaml#/validation/s0_gate_receipt_3A`)
  - `sealed_inputs_3A` (schema `schemas.3A.yaml#/validation/sealed_inputs_3A`)
- Required internal artefacts for bundling:
  - `s1_escalation_queue` (schema `schemas.3A.yaml#/plan/s1_escalation_queue`)
  - `s2_country_zone_priors` (schema `schemas.3A.yaml#/plan/s2_country_zone_priors`)
  - `s3_zone_shares` (schema `schemas.3A.yaml#/plan/s3_zone_shares`)
  - `s4_zone_counts` (schema `schemas.3A.yaml#/plan/s4_zone_counts`)
  - `zone_alloc` (schema `schemas.3A.yaml#/egress/zone_alloc`)
  - `zone_alloc_universe_hash` (schema `schemas.3A.yaml#/validation/zone_alloc_universe_hash`)
  - `s6_validation_report_3A` (schema `schemas.3A.yaml#/validation/s6_validation_report_3A`)
  - `s6_issue_table_3A` (schema `schemas.3A.yaml#/validation/s6_issue_table_3A`)
  - `s6_receipt_3A` (schema `schemas.3A.yaml#/validation/s6_receipt_3A`)
- Required evidence:
  - Segment-state run-report row for S6 with `status="PASS"` and `s6_receipt_3A.overall_status="PASS"`

## Outputs / datasets
- `validation_bundle_3A` (bundle directory with `index.json`; schema `schemas.layer1.yaml#/validation/validation_bundle_index_3A`)
- `validation_passed_flag_3A` (`_passed.flag` with composite bundle digest)

## Deliverables / reports
- Segment-state run-report row (S7 run status + bundle digest)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; S7 only packages and hashes artefacts; no re-validation beyond S6 gate
- Outputs are fingerprint-scoped; `_passed.flag` is the authoritative PASS signal for 3A
- Write-once/atomic publish; `index.json` member digests drive the composite HashGate digest


---

# 3B.S0 artefacts/policies/configs (from state.3B.s0.expanded.md only)

## Inputs / references
- Upstream PASS artefacts:
  - `validation_bundle_1A` + `_passed.flag`
  - `validation_bundle_1B` + `_passed.flag`
  - `validation_bundle_2A` + `_passed.flag`
  - `validation_bundle_3A` + `_passed.flag`
- Upstream datasets (metadata-only in S0):
  - `outlet_catalogue` (1A egress)
  - `site_locations` (1B egress)
  - `site_timezones` (2A egress)
  - `tz_timetable_cache` (2A cache)
  - `zone_alloc` (3A egress)
  - `zone_alloc_universe_hash` (3A validation artefact)
- 3B policies (sealed):
  - Virtual classification rules (e.g., `mcc_channel_rules.yaml`)
  - `virtual_settlement_coords` (legal anchor coordinates)
  - `cdn_country_weights` (CDN country mix policy)
  - `virtual_validation` policy (post-hoc thresholds)
- Geospatial/time assets (sealed):
  - HRSL / population rasters
  - world polygons / country shapes
  - tz-world polygons + pinned tzdb archive/release
- RNG/routing policies (sealed):
  - `route_rng_policy_v1`
  - `cdn_rng_policy_v1` / `cdn_key_digest` (if defined)
- Catalogue authorities:
  - `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`
  - `dataset_dictionary.layer1.3B.yaml`, `artefact_registry_3B.yaml`
  - upstream schema/dictionary/registry packs (1A/1B/2A/2B/3A)

## Outputs / datasets
- `s0_gate_receipt_3B` (schema `schemas.3B.yaml#/validation/s0_gate_receipt_3B`)
- `sealed_inputs_3B` (schema `schemas.3B.yaml#/validation/sealed_inputs_3B`)

## Deliverables / reports
- S0 run-report record (outputs_written, gate verification summary, paths)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; verifies upstream HashGate bundles for 1A/1B/2A/3A before sealing
- Output partition is fingerprint-only; path-embed equality is binding
- Write-once/atomic publish; sealed inputs define the only admissible 3B input universe


---

# 3B.S1 artefacts/policies/configs (from state.3B.s1.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3B` (schema `schemas.3B.yaml#/validation/s0_gate_receipt_3B`)
  - `sealed_inputs_3B` (schema `schemas.3B.yaml#/validation/sealed_inputs_3B`)
- Required control-plane artefacts (sealed):
  - virtual classification rules (schema `schemas.3B.yaml#/policy/virtual_classification_rules`)
  - virtual settlement coordinate source (schema `schemas.3B.yaml#/ingress/virtual_settlement_coords`)
  - any S1-specific overrides (allow/deny lists) if required
  - timezone/geospatial assets for settlement tzid resolution (tz-world/tzdb), if S1 resolves tzids directly
- Required data-plane input:
  - merchant reference dataset (merchant_id, mcc, channel, legal_country_iso) per ingress/1A schema
- Optional consistency inputs (sealed):
  - `outlet_catalogue`, `site_locations`, `site_timezones` (for checks)

## Outputs / datasets
- `virtual_classification_3B` (schema `schemas.3B.yaml#/plan/virtual_classification_3B`)
- `virtual_settlement_3B` (schema `schemas.3B.yaml#/plan/virtual_settlement_3B`)

## Deliverables / reports
- S1 run-report record (classification counts, settlement row count, output paths)

## Authority / policies / configs
- JSON-Schema is the sole shape authority; Dataset Dictionary governs IDs/paths/partitions/format; Artefact Registry records provenance/licences
- RNG-free; classification and settlement are deterministic from sealed inputs
- Output partitions `[seed, fingerprint]`; path-embed equality is binding
- Write-once/atomic publish; S1 outputs are authoritative for virtual status and settlement nodes


---

# 3B.S2 artefacts/policies/configs (from state.3B.s2.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3B`
  - `sealed_inputs_3B`
- S1 outputs:
  - `virtual_classification_3B`
  - `virtual_settlement_3B`
- CDN edge-budget policy artefacts:
  - `cdn_country_weights`
  - per-merchant override policies (if present)
- Spatial surfaces:
  - `tile_index`, `tile_weights` (1B-owned or 3B-specific tiling)
  - HRSL / population rasters
  - world-country polygons
- Timezone assets:
  - tz-world polygons
  - tzdb archive/release
  - tz override packs (if present)
- RNG/routing policy artefacts for 3B.S2 streams (Philox envelope; substreams like `edge_tile_assign`, `edge_jitter`)
- Feature flags in the governed parameter set (examples: `enable_virtual_edges`, `shared_tile_surfaces`, `fixed_edges_per_merchant`)

## Outputs / datasets
- `edge_catalogue_3B` (schema `schemas.3B.yaml#/plan/edge_catalogue_3B`)
- `edge_catalogue_index_3B` (schema `schemas.3B.yaml#/plan/edge_catalogue_index_3B`)
- Optional planning surface `edge_tile_plan_3B` (if persisted; per-merchant tile allocations)
- RNG logs/events (Layer-1 shared):
  - `rng_audit_log`
  - `rng_trace_log`
  - `rng_event_edge_tile_assign`
  - `rng_event_edge_jitter`

## Deliverables / reports
- S2 run-report record (status, counts, and paths for gate receipts, S1 inputs, and S2 outputs)
- Structured lifecycle logs (`start`, `finish`) and error log events (`E3B_S2_*`)
- Metrics counters/gauges (e.g. `3b_s2_runs_total`, `3b_s2_edge_count_total`, jitter resample counters)

## Authority / policies / configs
- JSON-Schema packs: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.3B.yaml`
- Dataset dictionaries: `dataset_dictionary.layer1.3B.yaml` (plus ingress/1B/2A dictionaries for inputs)
- Artefact registries: `artefact_registry_3B.yaml` (plus ingress/1B/2A registries for inputs)
- Policy schema anchors (examples): `schemas.3B.yaml#/policy/cdn_country_weights`, `schemas.3B.yaml#/spatial/virtual_tile_surface`


---

# 3B.S3 artefacts/policies/configs (from state.3B.s3.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3B`
  - `sealed_inputs_3B`
- S1 outputs (consistency checks):
  - `virtual_classification_3B`
  - `virtual_settlement_3B`
- S2 outputs (edge universe):
  - `edge_catalogue_3B`
  - `edge_catalogue_index_3B`
- Alias layout policy (e.g. `edge_alias_layout_policy_v1`; schema `schemas.3B.yaml#/policy/edge_alias_layout_policy`)
- RNG/routing policy (compat expectations for 2B decode; supported alias layout versions)
- Policy digests used by `edge_universe_hash_3B`:
  - `cdn_country_weights` + overrides
  - spatial surface digests (tiles/rasters used by S2)
  - alias layout policy digest
  - RNG policy digest
- Optional input: 3A zone-universe hash descriptor (e.g. `zone_alloc_universe_hash`) if sealed
- Feature flags in governed parameter set (examples: `alias_layout_version`, `enable_global_alias_header`, `enable_additional_alias_metadata`)

## Outputs / datasets
- `edge_alias_blob_3B` (binary blob; header schema `schemas.3B.yaml#/binary/edge_alias_blob_header_3B`)
- `edge_alias_index_3B` (schema `schemas.3B.yaml#/plan/edge_alias_index_3B`)
- `edge_universe_hash_3B` (schema `schemas.3B.yaml#/validation/edge_universe_hash_3B`)
- Optional run-summary/receipt dataset (e.g. `s3_run_summary_3B` or `s3_gate_receipt_3B`) if declared

## Deliverables / reports
- S3 run-report record (status, counts, alias blob size, and paths for S0/S2/S3 artefacts)
- Structured lifecycle logs (`start`, `finish`) and error logs with `E3B_S3_*` codes
- Metrics counters/gauges (e.g. `3b_s3_runs_total`, `3b_s3_alias_blob_size_bytes`, alias table length histogram)

## Authority / policies / configs
- JSON-Schema packs: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`
- Dataset dictionary: `dataset_dictionary.layer1.3B.yaml`
- Artefact registry: `artefact_registry_3B.yaml`
- Alias layout policy is the sole authority on blob/index layout and quantisation; RNG/routing policy is the sole authority on 2B decode compatibility
- RNG-free; S3 must not emit RNG events or logs


---

# 3B.S4 artefacts/policies/configs (from state.3B.s4.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3B`
  - `sealed_inputs_3B`
- S1 outputs:
  - `virtual_classification_3B`
  - `virtual_settlement_3B`
- S2 outputs:
  - `edge_catalogue_3B`
  - `edge_catalogue_index_3B`
- S3 outputs:
  - `edge_alias_blob_3B`
  - `edge_alias_index_3B`
  - `edge_universe_hash_3B`
- Virtual validation policy pack (e.g. `virtual_validation.yml`)
- Routing/RNG policy (2B compatibility; alias layout support and RNG stream bindings)
- Event schema / routing field contracts (2B event schema anchors / routing field bindings)
- Feature flags in governed parameter set (examples: `enable_virtual_routing`, `virtual_validation_profile`, hybrid routing modes)

## Outputs / datasets
- `virtual_routing_policy_3B` (schema `schemas.3B.yaml#/egress/virtual_routing_policy_3B`)
- `virtual_validation_contract_3B` (schema `schemas.3B.yaml#/egress/virtual_validation_contract_3B`)
- Optional run-summary/receipt `s4_run_summary_3B` (schema `schemas.3B.yaml#/validation/s4_run_summary_3B`)

## Deliverables / reports
- S4 run-report record (status, counts, and paths for S0-S3 inputs plus S4 outputs)
- Structured lifecycle logs (`start`, `finish`) and error logs with `E3B_S4_*` codes
- Metrics counters/gauges for S4 runs and contract sizes

## Authority / policies / configs
- JSON-Schema packs: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.3B.yaml`
- Dataset dictionary: `dataset_dictionary.layer1.3B.yaml`
- Artefact registry: `artefact_registry_3B.yaml`
- Routing policy and validation policy are the only authorities on routing semantics and validation tests
- RNG-free; S4 must not emit RNG events or logs


---

# 3B.S5 artefacts/policies/configs (from state.3B.s5.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_3B`
  - `sealed_inputs_3B`
- S1 outputs:
  - `virtual_classification_3B`
  - `virtual_settlement_3B`
- S2 outputs:
  - `edge_catalogue_3B`
  - `edge_catalogue_index_3B`
  - S2 RNG logs/events (`rng_audit_log`, `rng_trace_log`, S2 event streams)
- S3 outputs:
  - `edge_alias_blob_3B`
  - `edge_alias_index_3B`
  - `edge_universe_hash_3B`
- S4 outputs:
  - `virtual_routing_policy_3B`
  - `virtual_validation_contract_3B`
- Sealed policies and governance:
  - CDN edge policy (e.g. `cdn_country_weights` + overrides)
  - spatial/tiling assets + world polygons
  - tz-world, tzdb archive, tz overrides
  - alias layout policy
  - routing/RNG policy
  - virtual validation policy

## Outputs / datasets
- `validation_bundle_3B` (bundle directory under `data/layer1/3B/validation/fingerprint={manifest_fingerprint}/`)
- `validation_bundle_index_3B` (`index.json` inside the bundle)
- `validation_passed_flag_3B` (`_passed.flag`)
- Optional evidence/summary files (if declared): `s5_manifest_3B`, `s5_run_summary_3B`

## Deliverables / reports
- S5 run-report record (status, evidence counts, RNG discrepancy counts, and bundle/index/flag paths)
- Structured lifecycle logs (`start`, `finish`) and error logs with `E3B_S5_*` codes
- Metrics counters/gauges (e.g. `3b_s5_runs_total`, `3b_s5_evidence_file_count`, `3b_s5_rng_discrepancies_total`)

## Authority / policies / configs
- JSON-Schema packs: `schemas.layer1.yaml`, `schemas.3B.yaml` (bundle/index/flag schemas)
- Dataset dictionary: `dataset_dictionary.layer1.3B.yaml`
- Artefact registry: `artefact_registry_3B.yaml`
- HashGate law for bundle hashing and `_passed.flag` content is authoritative
- RNG-free; S5 must not emit RNG events or logs


---

# 5A.S0 artefacts/policies/configs (from state.5A.s0.expanded.md only)

## Inputs / references
- Run context: `parameter_hash`, `manifest_fingerprint`, `run_id`
- Upstream validation artefacts (for 1A, 1B, 2A, 2B, 3A, 3B):
  - `validation_bundle_*` directories
  - `_passed.flag` files
- Contract catalogues:
  - `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, `schemas.5A.yaml`
  - `dataset_dictionary.layer1.1A.yaml` .. `dataset_dictionary.layer1.3B.yaml`
  - `dataset_dictionary.layer2.5A.yaml`
  - `artefact_registry_1A.yaml` .. `artefact_registry_3B.yaml`
  - `artefact_registry_5A.yaml`
- Upstream world surfaces (sealed as admissible inputs):
  - 1A: `outlet_catalogue`, merchant reference tables (MCC, channel, etc.)
  - 1B: `site_locations`
  - 2A: `site_timezones`, `tz_timetable_cache`
  - 2B: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`
  - 3A: `zone_alloc`, `zone_alloc_universe_hash`
  - 3B: `virtual_classification_3B`, `virtual_settlement_3B`, `virtual_routing_policy_3B`, `virtual_validation_contract_3B`, `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`
- Scenario configs (Layer-2):
  - `scenario_calendar`
  - `scenario_metadata`
- 5A policies:
  - `merchant_class_policy_5A`
  - `shape_library_5A`
  - `calendar_overlay_policy_5A`
  - additional Layer-2 knobs (default scale factors, clipping thresholds)

## Outputs / datasets
- `s0_gate_receipt_5A` (fingerprint-scoped gate receipt)
- `sealed_inputs_5A` (fingerprint-scoped inventory of allowed artefacts)
- Optional `scenario_manifest_5A` (fingerprint-scoped scenario summary)

## Deliverables / reports
- Run-report entry for 5A.S0 (status, sealed_inputs_digest/counts, upstream status summary)
- Structured lifecycle logs (`state_start`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s0_runs_total`, upstream missing/fail counters, sealed input counts)

## Authority / policies / configs
- Catalogue-only discovery: schemas, dictionaries, and registries are the sole authority on shapes/paths/roles
- Upstream validation bundle/hash laws are authoritative per segment
- RNG-free; S0 must not emit RNG events or read row-level data


---

# 5A.S1 artefacts/policies/configs (from state.5A.s1.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5A`
  - `sealed_inputs_5A` (including `sealed_inputs_digest`)
- Required upstream segments must be `PASS` in `s0_gate_receipt_5A`:
  - `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
- Required sealed inputs (via `sealed_inputs_5A`):
  - Merchant attributes (Layer-1/ingress tables: `merchant_id`, `legal_country_iso`, MCC, channel, size buckets)
  - 3A `zone_alloc` (merchant, legal_country_iso, tzid domain)
  - 3B virtual artefacts (if virtual in scope): `virtual_classification_3B`, optional `virtual_settlement_3B`
  - Scenario metadata (scenario ID/type flags)
  - 5A policies: `merchant_class_policy_5A`, `demand_scale_policy_5A`
  - Optional reference inputs (GDP buckets, region clusters, auxiliary merchant descriptors)

## Outputs / datasets
- `merchant_zone_profile_5A` (required; per merchant/zone demand class + base scale)
- `merchant_class_profile_5A` (optional convenience aggregate per merchant)
- Optional diagnostic tables only if declared in dictionary/registry

## Deliverables / reports
- Run-report entry for 5A.S1 (status, domain sizes, class distribution, scale stats, policies used, scenario_id)
- Structured logs (`state_start`, `inputs_resolved`, `domain_built`, `classification_summary`, `scale_summary`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s1_runs_total`, domain size gauges, class counts, scale distribution stats)

## Authority / policies / configs
- `s0_gate_receipt_5A` is the authority on upstream PASS/FAIL status and scenario binding
- `sealed_inputs_5A` is the only authority on what S1 may read and at what scope
- `zone_alloc` defines the merchant/zone domain; merchant attributes are authoritative for MCC/channel/etc.
- RNG-free; S1 must not emit RNG events or time-series outputs


---

# 5A.S2 artefacts/policies/configs (from state.5A.s2.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5A`
  - `sealed_inputs_5A` (including `sealed_inputs_digest`)
- Required upstream segments must be `PASS` in `s0_gate_receipt_5A`:
  - `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
- S1 output (domain discovery):
  - `merchant_zone_profile_5A` (used only to derive `DOMAIN_S2`)
- Time-grid config:
  - `shape_time_grid_policy_5A` (bucket size, `T_week`, mapping rules)
- Shape library policy/config:
  - `shape_library_policy_5A`
  - optional class-to-template mapping tables and region/tz hint tables
- Scenario metadata (if scenario-sensitive shapes are enabled)
- Optional reference inputs (weekend patterns, zone overrides, diagnostics)

## Outputs / datasets
- `shape_grid_definition_5A` (required; local-week bucket grid)
- `class_zone_shape_5A` (required; normalised weekly shapes per class/zone[/channel])
- Optional `class_shape_catalogue_5A` (base template catalogue)

## Deliverables / reports
- Run-report entry for 5A.S2 (grid summary, domain counts, shape sanity stats, policies used, `s2_spec_version`)
- Structured logs (`state_start`, `inputs_resolved`, `domain_built`, `grid_built`, `shape_summary`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s2_runs_total`, grid size, domain size, shape L1 error stats)

## Authority / policies / configs
- `s0_gate_receipt_5A` and `sealed_inputs_5A` are the sole authority on gating and allowed inputs
- `merchant_zone_profile_5A` defines the class/zone domain (no per-merchant scale usage)
- Time-grid and shape policies are the only authority on grid and shape semantics
- RNG-free; S2 must not emit RNG events or per-merchant intensities


---

# 5A.S3 artefacts/policies/configs (from state.5A.s3.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5A`
  - `sealed_inputs_5A` (including `sealed_inputs_digest`)
- Required upstream segments must be `PASS` in `s0_gate_receipt_5A`:
  - `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
- S1 output:
  - `merchant_zone_profile_5A` (demand_class + base scale per merchant/zone)
- S2 outputs:
  - `shape_grid_definition_5A`
  - `class_zone_shape_5A`
- S3 baseline policy (if required):
  - `baseline_intensity_policy_5A` (scale field choice, units, clipping)
- Scenario metadata (scenario_id bound to the run)
- Optional reference inputs for diagnostics (if sealed)

## Outputs / datasets
- `merchant_zone_baseline_local_5A` (required; baseline local-week intensities per merchant/zone/bucket)
- Optional aggregates:
  - `class_zone_baseline_local_5A`
  - `merchant_zone_baseline_utc_5A` (if UTC mapping is materialised)

## Deliverables / reports
- Run-report entry for 5A.S3 (domain counts, lambda stats, weekly-sum error stats, policy/spec versions)
- Structured logs (`state_start`, `inputs_resolved`, `domain_built`, `intensity_summary`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s3_runs_total`, domain size, lambda min/max, weekly sum error)

## Authority / policies / configs
- `s0_gate_receipt_5A` and `sealed_inputs_5A` are the sole authority on gating and allowed inputs
- `merchant_zone_profile_5A` is the only authority for class and base scale
- `shape_grid_definition_5A` and `class_zone_shape_5A` are the only authority for grid and shapes
- RNG-free; S3 must not emit RNG events or calendar overlays


---

# 5A.S4 artefacts/policies/configs (from state.5A.s4.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5A`
  - `sealed_inputs_5A` (including `sealed_inputs_digest`)
- Required upstream segments must be `PASS` in `s0_gate_receipt_5A`:
  - `1A`, `1B`, `2A`, `2B`, `3A`, `3B`
- S1 outputs:
  - `merchant_zone_profile_5A`
- S2 outputs:
  - `shape_grid_definition_5A`
  - `class_zone_shape_5A`
- S3 outputs:
  - `merchant_zone_baseline_local_5A`
- Scenario/calendar config:
  - `scenario_calendar_5A` (events)
  - `scenario_horizon_config_5A` (horizon grid)
  - scenario metadata (scenario_id/type)
- Overlay policies:
  - `scenario_overlay_policy_5A`
  - optional `overlay_ordering_policy_5A`
  - optional `scenario_overlay_validation_policy_5A`
- Optional reference inputs for event scoping/diagnostics

## Outputs / datasets
- `merchant_zone_scenario_local_5A` (required; scenario-adjusted local intensities)
- Optional:
  - `merchant_zone_overlay_factors_5A` (overlay factor table)
  - `merchant_zone_scenario_utc_5A` (UTC-projected intensities)

## Deliverables / reports
- Run-report entry for 5A.S4 (domain/horizon sizes, overlay stats, lambda stats, policy/spec IDs)
- Structured logs (`state_start`, `inputs_resolved`, `domain_built`, `overlay_summary`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s4_runs_total`, overlay factor min/max, horizon buckets)

## Authority / policies / configs
- `s0_gate_receipt_5A` and `sealed_inputs_5A` are the sole authority on gating and allowed inputs
- `merchant_zone_baseline_local_5A` is the only baseline authority; S4 only applies overlays
- Scenario calendar and overlay policies are the only authority on event timing and factor rules
- RNG-free; S4 must not emit RNG events or generate arrivals


---

# 5A.S5 artefacts/policies/configs (from state.5A.s5.expanded.md only)

## Inputs / references
- Gate evidence:
  - `s0_gate_receipt_5A`
  - `sealed_inputs_5A`
- 5A outputs to validate:
  - S1: `merchant_zone_profile_5A`
  - S2: `shape_grid_definition_5A`, `class_zone_shape_5A`
  - S3: `merchant_zone_baseline_local_5A` (plus any optional S3 outputs)
  - S4: `merchant_zone_scenario_local_5A` (plus any optional S4 outputs)
- 5A policies/configs used in validation:
  - S1 classing/scale policies
  - S2 time-grid and shape policies
  - S3 baseline intensity policy
  - S4 overlay policies and horizon config
- Upstream validation artefacts (1A-3B) as sealed inputs (optional corroboration)

## Outputs / datasets
- `validation_bundle_5A` (bundle directory)
- `validation_bundle_index_5A` (index file inside bundle)
- `validation_report_5A` (summary report)
- `validation_issue_table_5A` (optional issue table)
- `_passed.flag` (validation gate flag)

## Deliverables / reports
- Run-report entry for 5A.S5 (bundle/flag presence, overall_status_5A, counts of validated packs/scenarios)
- Structured logs (`state_start`, `inputs_resolved`, `runs_discovered`, `validation_summary`, `bundle_built`, `flag_written`, `state_success`, `state_failure`)
- Metrics (e.g. `fraudengine_5A_s5_runs_total`, bundle sizes, PASS/FAIL breakdown)

## Authority / policies / configs
- `sealed_inputs_5A` is the only universe of admissible inputs
- S5 is the sole authority to emit `validation_bundle_5A` and `_passed.flag`
- RNG-free; S5 must not emit RNG events or modify S1-S4 outputs


---

# 5B.S0 artefacts/policies/configs (from state.5B.s0.expanded.md only)

## Inputs / references
- Run context: `parameter_hash`, `manifest_fingerprint`, `seed`, `run_id`, `scenario_set`
- Upstream validation artefacts:
  - Layer-1 segments `1A`–`3B` validation bundles + `_passed.flag`
  - Layer-2 `5A` validation bundle + `_passed.flag`
- Contract catalogues:
  - `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`, `schemas.5A.yaml`, `schemas.5B.yaml`
  - `dataset_dictionary.layer1.1A.yaml` .. `dataset_dictionary.layer1.3B.yaml`
  - `dataset_dictionary.layer2.5A.yaml`, `dataset_dictionary.layer2.5B.yaml`
  - `artefact_registry_1A.yaml` .. `artefact_registry_3B.yaml`
  - `artefact_registry_5A.yaml`, `artefact_registry_5B.yaml`
- Upstream world surfaces (sealed as admissible inputs):
  - 1B `site_locations`, 2A `site_timezones` / `tz_timetable_cache`
  - 2B routing artefacts (weights, alias tables, day effects)
  - 3A `zone_alloc`, `zone_alloc_universe_hash`
  - 3B virtual artefacts (classification, edge catalogue, alias tables, universe hash)
  - 5A scenario/intensity surfaces + scenario metadata
- 5B configs/policies:
  - arrival/LGCP hyper-parameters
  - arrival RNG policy
  - arrival validation policy

## Outputs / datasets
- `s0_gate_receipt_5B` (fingerprint-scoped gate receipt)
- `sealed_inputs_5B` (fingerprint-scoped inventory of allowed artefacts)

## Deliverables / reports
- Run-report record for 5B.S0 (status, upstream PASS/FAIL counts, sealed input row counts, sealed_inputs_digest)
- Structured log of `upstream_segments` map (segment → status/spec_version/bundle_digest)

## Authority / policies / configs
- Catalogue-only discovery: dictionaries/registries are the sole authority on shapes/paths/roles
- `s0_gate_receipt_5B` is the authority on upstream PASS/FAIL map and sealed_inputs_digest
- `sealed_inputs_5B` is the only whitelist of admissible 5B inputs
- RNG-free; S0 must not emit RNG events or read row-level data


---

# 5B.S1 artefacts/policies/configs (from state.5B.s1.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5B` (includes `scenario_set_5B`, upstream status map, `parameter_hash`, `manifest_fingerprint`)
  - `sealed_inputs_5B` (whitelisted artefacts + `read_scope`)
- Required upstream statuses in `s0_gate_receipt_5B`:
  - `1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A` all `PASS`
- 5A scenario and horizon authority:
  - `scenario_manifest_5A` (scenario_id list, horizon start/end in UTC)
- 5A domain keys (row-level allowed if sealed):
  - `merchant_zone_scenario_local_5A` (keys and bucket index domain only)
  - Other 5A surfaces may be used for structural alignment only (no intensity changes)
- 2A civil-time metadata (metadata-only):
  - `tz_timetable_cache`
  - `site_timezones`
- 2B/3A/3B domain hints (metadata-only):
  - `s1_site_weights`
  - `s4_group_weights`
  - `zone_alloc`
  - `zone_alloc_universe_hash`
  - `virtual_classification_3B`
  - `virtual_settlement_3B`
- 5B local configs/policies (row-level):
  - `time_grid_policy_5B` (name to be fixed; bucket duration/alignment rules)
  - `grouping_policy_5B` (grouping keys and pooling rules)

## Outputs / datasets
- `s1_time_grid_5B` (schema `schemas.5B.yaml#/model/s1_time_grid_5B`)
  - Partitioned by `fingerprint` + `scenario_id`
- `s1_grouping_5B` (schema `schemas.5B.yaml#/model/s1_grouping_5B`)
  - Partitioned by `fingerprint` + `scenario_id`

## Deliverables / reports
- Run-report record (state_id `5B.S1`, status, error_code, timing, scenario_set)
- Required metrics:
  - `scenario_count_requested`, `scenario_count_succeeded`, `scenario_count_failed`
  - `total_bucket_count`
  - `total_grouping_rows`
  - `total_unique_group_ids`
- Optional structured payload details (per-scenario bucket/group counts, first/last bucket bounds)

## Authority / policies / configs
- `s0_gate_receipt_5B` is authoritative for upstream PASS/FAIL, scenario_set, and sealed_inputs_digest
- `sealed_inputs_5B` is the only authority on admissible inputs and `read_scope`
- `scenario_manifest_5A` is authoritative for scenario_id and horizon bounds
- 2A `tz_timetable_cache` is authoritative for UTC/local mapping and gap/fold semantics
- 2B/3A/3B artefacts are authoritative for routing/zone/virtual metadata (S1 uses metadata only)
- `time_grid_policy_5B` and `grouping_policy_5B` are the only authorities for grid/group rules
- RNG-free; no RNG logs or metrics


---

# 5B.S2 artefacts/policies/configs (from state.5B.s2.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5B`
  - `sealed_inputs_5B` (whitelisted artefacts + `read_scope`)
- S1 planning outputs (row-level):
  - `s1_time_grid_5B` (schema `schemas.5B.yaml#/model/s1_time_grid_5B`)
  - `s1_grouping_5B` (schema `schemas.5B.yaml#/model/s1_grouping_5B`)
- 5A deterministic intensity surface (row-level, designated ? source):
  - `merchant_zone_scenario_local_5A` (or the designated 5A scenario surface listed in `sealed_inputs_5B`)
- 2A/2B/3A/3B metadata (metadata-only, if needed):
  - `tz_timetable_cache`
  - `site_timezones`
  - optional metadata for grouping/context (2B/3A/3B artefacts)
- 5B configs/policies (row-level, must be sealed):
  - arrival-process / LGCP config (name to be fixed, e.g. `arrival_lgcp_config_5B`)
  - 5B RNG policy (e.g. `arrival_rng_policy_5B`)
  - optional S2 validation config (if present)

## Outputs / datasets
- `s2_realised_intensity_5B` (required; schema `schemas.5B.yaml#/model/s2_realised_intensity_5B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s2_latent_field_5B` (optional; schema `schemas.5B.yaml#/model/s2_latent_field_5B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`

## RNG logs / events
- RNG event logs per 5B RNG policy (LOG artefacts), e.g. `rng_event_arrival_lgcp_gaussian`
- RNG event/trace logs are used for run-report RNG metrics

## Deliverables / reports
- Run-report record (state_id `5B.S2`, status, error_code, timing, scenario_set, seed, run_id)
- Required metrics:
  - `scenario_count_requested`, `scenario_count_succeeded`, `scenario_count_failed`
  - `total_bucket_count`
  - `total_entity_bucket_count`
  - `total_group_count`
  - `total_latent_values`
  - `latent_field_rows_written` (if `s2_latent_field_5B` is produced)
  - `latent_rng_event_count`, `latent_rng_total_draws`, `latent_rng_total_blocks`
- Optional summary stats (recommended in run-report payload):
  - summary stats for latent values and `lambda_realised`

## Authority / policies / configs
- `s0_gate_receipt_5B` is authoritative for upstream PASS/FAIL and sealed world identity
- `sealed_inputs_5B` is authoritative for admissible inputs and `read_scope`
- `s1_time_grid_5B` and `s1_grouping_5B` are authoritative for bucket structure and grouping
- 5A scenario intensity surface is authoritative for `lambda_target`
- LGCP config and RNG policy are the only authorities for stochastic law and RNG layout
- Contract files: `schemas.5B.yaml`, `schemas.layer2.yaml`, `dataset_dictionary.layer2.5B.yaml`, `artefact_registry_5B.yaml`
- RNG-bearing; outputs deterministic for `(parameter_hash, manifest_fingerprint, seed)` and independent of `run_id`


---

# 5B.S3 artefacts/policies/configs (from state.5B.s3.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5B`
  - `sealed_inputs_5B` (whitelisted artefacts + `read_scope`)
- S1 planning outputs (row-level):
  - `s1_time_grid_5B` (schema `schemas.5B.yaml#/model/s1_time_grid_5B`)
  - `s1_grouping_5B` (schema `schemas.5B.yaml#/model/s1_grouping_5B`)
- S2 realised intensities (row-level):
  - `s2_realised_intensity_5B` (schema `schemas.5B.yaml#/model/s2_realised_intensity_5B`)
- 5B configs/policies (row-level, must be sealed):
  - arrival/count-law config (e.g. `arrival_count_config_5B`)
  - S3 RNG policy (may be shared `arrival_rng_policy_5B`)
  - optional S3 validation/guardrail config (if present)
- Optional metadata-only references:
  - 2A `tz_timetable_cache` (if duration checks needed)
  - upstream metadata (5A/2B/3A/3B) for structural hints only

## Outputs / datasets
- `s3_bucket_counts_5B` (required; schema `schemas.5B.yaml#/model/s3_bucket_counts_5B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`

## RNG logs / events
- Count-draw RNG event logs (LOG artefacts per 5B RNG policy)
- RNG trace logs paired to count-draw events

## Deliverables / reports
- Run-report record (state_id `5B.S3`, status, error_code, timing, scenario_set, seed, run_id)
- Required metrics:
  - `scenario_count_requested`, `scenario_count_succeeded`, `scenario_count_failed`
  - `total_entity_bucket_domain`
  - `total_count_rows`
  - `sum_count_N`
  - `count_rng_event_count`, `count_rng_total_draws`, `count_rng_total_blocks`
- Optional payload summaries:
  - `count_rows_min/max/mean`, `sum_count_N_min/max/mean`
  - count vs mean summaries, optional Fano hints (if configured)

## Authority / policies / configs
- `s0_gate_receipt_5B` is authoritative for upstream PASS/FAIL and sealed world identity
- `sealed_inputs_5B` is authoritative for admissible inputs and `read_scope`
- `s1_time_grid_5B` and `s1_grouping_5B` are authoritative for bucket structure and domain
- `s2_realised_intensity_5B` is authoritative for `lambda_realised`
- Arrival/count-law config and S3 RNG policy are the only authorities for count law and RNG layout
- Contract files: `schemas.5B.yaml`, `schemas.layer2.yaml`, `dataset_dictionary.layer2.5B.yaml`, `artefact_registry_5B.yaml`
- RNG-bearing; outputs deterministic for `(parameter_hash, manifest_fingerprint, seed)` and independent of `run_id`


---

# 5B.S4 artefacts/policies/configs (from state.5B.s4.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5B`
  - `sealed_inputs_5B` (whitelisted artefacts + `read_scope`)
- S1 planning outputs (row-level):
  - `s1_time_grid_5B`
  - `s1_grouping_5B`
- S2 realised intensities (optional, row-level):
  - `s2_realised_intensity_5B` (provenance/diagnostics only)
- S3 bucket counts (row-level, hard dependency):
  - `s3_bucket_counts_5B`
- Layer-1/2 routing & time surfaces (sealed, schema-valid):
  - 1B: `site_locations`
  - 2A: `site_timezones`, `tz_timetable_cache`
  - 2B: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, `route_rng_policy_v1`, alias layout policy
  - 3A: `zone_alloc`, `zone_alloc_universe_hash`
  - 3B: `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`
- 5B configs/policies (row-level, must be sealed):
  - time placement config (e.g. `arrival_time_placement_policy_5B`)
  - routing config (e.g. `arrival_routing_policy_5B`)
  - S4 RNG policy (time draws, site picks, edge picks)

## Outputs / datasets
- `s4_arrival_events_5B` (required; canonical arrival event stream)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
  - `parameter_hash` carried as a column
- Optional diagnostics:
  - `s4_arrival_summary_5B`
  - `s4_arrival_anomalies_5B`

## RNG logs / events
- RNG event families (LOG artefacts):
  - `arrival_time_jitter`
  - `arrival_site_pick`
  - `arrival_edge_pick`
- RNG trace log entries for S4 event families

## Deliverables / reports
- Run-report record (state_id `5B.S4`, status, error_code, timing, scenario_id, seed, run_id)
- Required core metrics:
  - `n_buckets_total`, `n_buckets_nonzero`, `n_arrivals_total`
  - `n_arrivals_physical`, `n_arrivals_virtual` (plus optional share fields)
  - `min_bucket_duration`, `max_bucket_duration`
  - `n_arrivals_at_bucket_start`, `n_arrivals_at_bucket_end_minus_epsilon`
  - `counts_match_s3`
  - `schema_ok`, `partition_ok`
- Required RNG metrics:
  - `rng_draws_time`, `rng_draws_site`, `rng_draws_edge`
  - `rng_blocks_time`, `rng_blocks_site`, `rng_blocks_edge`
  - `rng_accounting_ok`

## Authority / policies / configs
- `s0_gate_receipt_5B` is authoritative for run identity and sealed inputs
- `sealed_inputs_5B` is authoritative for admissible inputs and `read_scope`
- `s1_time_grid_5B` is authoritative for bucket windows
- `s3_bucket_counts_5B` is authoritative for `N` (counts)
- 2A owns civil time; 2B/3A/3B own routing/zone/virtual semantics
- S4 owns only intra-bucket timing and routing choices under its policies
- Contract files: `schemas.5B.yaml`, `schemas.layer2.yaml`, `dataset_dictionary.layer2.5B.yaml`, `artefact_registry_5B.yaml`
- RNG-bearing; outputs deterministic for `(parameter_hash, manifest_fingerprint, scenario_id, seed)` and independent of `run_id`


---

# 5B.S5 artefacts/policies/configs (from state.5B.s5.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_5B`
  - `sealed_inputs_5B` (whitelisted artefacts + `read_scope`)
- S1/S2/S3/S4 outputs (schema-valid evidence):
  - `s1_time_grid_5B`
  - `s1_grouping_5B` (optional evidence)
  - `s2_realised_intensity_5B`
  - `s3_bucket_counts_5B`
  - `s4_arrival_events_5B`
- Upstream segment PASS flags (verified via S0 receipt):
  - `_passed.flag` for required upstream segments (1A, 1B, 2A, 2B, 3A, 3B, 5A)
- Layer-1/2 upstream artefacts used for validation:
  - 1B: `site_locations`
  - 2A: `site_timezones`, `tz_timetable_cache`
  - 2B: `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s4_group_weights`, `route_rng_policy_v1`, alias layout policy
  - 3A: `zone_alloc`, `zone_alloc_universe_hash`
  - 3B: `virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_3B`, `edge_alias_index_3B`, `edge_alias_blob_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`
  - 5A intensity surfaces (e.g. `merchant_zone_scenario_local_5A`, `merchant_zone_scenario_utc_5A`) + 5A validation artefacts (for domain/sanity checks only)
- RNG infrastructure (for S2/S3/S4 accounting):
  - `rng_audit_log`, `rng_trace_log`
  - RNG event tables for S2/S3/S4 families (listed in `sealed_inputs_5B`)
- Catalogue/contract files (required for discovery):
  - `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.5B.yaml`
  - `dataset_dictionary.layer2.5B.yaml`
  - `artefact_registry_5B.yaml`
- 5B S5 configs (if present in sealed inputs):
  - validation policy (checks + thresholds)
  - bundle layout policy

## Outputs / datasets (fingerprint-scoped)
- `validation_bundle_5B` (bundle directory)
  - `index.json` (bundle index)
  - evidence files (e.g. `validation_report_5B`, RNG summaries, receipts)
- `validation_bundle_index_5B` (schema `schemas.layer2.yaml#/validation/validation_bundle_index_5B`)
- `validation_report_5B` (schema `schemas.layer2.yaml#/validation/validation_report_5B`)
- `validation_issue_table_5B` (optional; schema `schemas.layer2.yaml#/validation/validation_issue_table_5B`)
- `_passed.flag` / `validation_passed_flag_5B` (bundle digest)
- Optional S5 receipt object (if produced, must live inside bundle and be indexed)

## Deliverables / reports
- Run-report record (state_id `5B.S5`, status, error_code, run_id, `5B_spec_version`)
- Required metrics:
  - `n_parameter_hashes`, `n_scenarios`, `n_seeds`
  - `n_buckets_total`, `n_buckets_nonzero`, `n_arrivals_total`
  - `n_arrivals_physical`, `n_arrivals_virtual`
  - `counts_match_s3`, `time_windows_ok`, `civil_time_ok`, `routing_ok`
  - `schema_partition_pk_ok`, `rng_accounting_ok`, `bundle_integrity_ok`
  - RNG summary: `rng_checked_states`, `rng_families_ok` (optional `rng_draws_by_family`, `rng_blocks_by_family`)
  - `bundle_sha256` (echoed from `_passed.flag`)

## Authority / policies / configs
- `s0_gate_receipt_5B` is authoritative for upstream PASS/FAIL and world identity
- `sealed_inputs_5B` is authoritative for admissible evidence inputs
- S5 is the sole authority for `validation_bundle_5B` and `_passed.flag`
- Bundle/hash law is authoritative; S5 is RNG-free


---

# 6A.S0 artefacts/policies/configs (from state.6A.s0.expanded.md only)

## Inputs / references
- Upstream HashGates (bundle + flag) required:
  - 1A: `validation_bundle_1A` + `_passed.flag`
  - 1B: `validation_bundle_1B` + `_passed.flag`
  - 2A: `validation_bundle_2A` + `_passed.flag`
  - 2B: `validation_bundle_2B` + `_passed.flag`
  - 3A: `validation_bundle_3A` + `_passed.flag`
  - 3B: `validation_bundle_3B` + `_passed.flag`
  - 5A: `validation_bundle_5A` + `_passed.flag`
  - 5B: `validation_bundle_5B` + `_passed.flag`
- Layer-1/2 shape authority (schemas + catalogues):
  - `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.layer2.yaml`
  - dataset dictionaries + artefact registries for 1A-3B and 5A-5B
- Layer-3 / 6A contracts:
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- 6A prior/config packs (as referenced by the 6A registry):
  - population priors
  - segmentation priors
  - product mix priors
  - device/IP priors
  - fraud-role priors
  - taxonomy/enumeration packs
- Upstream egress candidates for sealing (metadata-only at S0):
  - 1A: `outlet_catalogue`
  - 1B: `site_locations`
  - 2A: `site_timezones`, `tz_timetable_cache`
  - 3A: `zone_alloc`, `zone_alloc_universe_hash`
  - 3B: `virtual_classification_3B`, `virtual_settlement_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`
  - 5A: `merchant_zone_profile_5A` and related intensity surfaces
  - 5B: `arrival_events_5B` (metadata-only)

## Outputs / datasets
- `s0_gate_receipt_6A` (gate receipt; schema `schemas.layer3.yaml#/gate/6A/s0_gate_receipt_6A`)
- `sealed_inputs_6A` (sealed input manifest; schema `schemas.layer3.yaml#/gate/6A/sealed_inputs_6A`)
- `sealed_inputs_digest_6A` (digest recorded in `s0_gate_receipt_6A`)

## Deliverables / reports
- Run-report record (state_id `6A.S0`, status, error_code, run_id, `spec_version_6A`)
- Required run-report fields/metrics:
  - `sealed_inputs_digest_6A`, `sealed_inputs_row_count`
  - `upstream_gates_summary` (counts of PASS/FAIL/MISSING)
  - `prior_packs_summary` (counts by prior role)
  - `upstream_segments_required`, `upstream_segments_pass`, `upstream_segments_fail`, `upstream_segments_missing`
  - `sealed_inputs_by_role`, `sealed_inputs_by_status`, `sealed_inputs_by_read_scope`

## Authority / policies / configs
- S0 is the sole authority for `s0_gate_receipt_6A` and `sealed_inputs_6A`
- Upstream HashGates are authoritative for segment PASS/FAIL
- 6A contracts (schemas/dictionary/registry) are authoritative for 6A shapes
- RNG-free; control-plane only


---

# 6A.S1 artefacts/policies/configs (from state.6A.s1.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6A`
  - `sealed_inputs_6A` (whitelisted artefacts + `read_scope`)
  - latest 6A.S0 run-report must be `PASS`
- Required priors/taxonomies (ROW_LEVEL; `status=REQUIRED`):
  - `POPULATION_PRIOR` artefacts (population scale + regional splits)
  - `SEGMENT_PRIOR` artefacts (segment mix per region/type)
  - `TAXONOMY` artefacts (party types, segments, region codes)
- 6A contracts (METADATA_ONLY):
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- Optional contextual inputs (if sealed):
  - upstream region/country surfaces or aggregate 5A/5B volume summaries (must respect `read_scope`)

## Outputs / datasets
- `s1_party_base_6A` (required; schema `schemas.6A.yaml#/s1/party_base`)
  - Partition keys: `seed`, `manifest_fingerprint`
  - Columns include `parameter_hash` and party identity/segment/geography fields
- `s1_party_summary_6A` (optional; schema `schemas.6A.yaml#/s1/party_summary`)
  - Derived aggregate counts from `s1_party_base_6A`

## RNG logs / events
- RNG families for:
  - `party_count_realisation`
  - `party_attribute_sampling`
- RNG event tables + layer-wide trace logs (Philox envelope)

## Deliverables / reports
- Run-report record (state_id `6A.S1`, status, error_code, run_id, `spec_version_6A`)
- Required metrics:
  - `total_parties`
  - `parties_by_region`, `parties_by_segment`, `parties_by_party_type`
  - `N_world_target`, `N_world_int` (plus optional region summaries)
  - `rng_party_count_events`, `rng_party_count_draws`
  - `rng_party_attribute_events`, `rng_party_attribute_draws`

## Authority / policies / configs
- `s0_gate_receipt_6A` and `sealed_inputs_6A` are authoritative for allowed inputs
- Population/segment priors and taxonomies are authoritative for party counts/attributes
- S1 is the sole authority for the party base for `(manifest_fingerprint, seed)`
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, seed)` and independent of `run_id`


---

# 6A.S2 artefacts/policies/configs (from state.6A.s2.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6A`
  - `sealed_inputs_6A` (whitelisted artefacts + `read_scope`)
  - latest 6A.S0 run-report must be `PASS`
- S1 party base gate:
  - latest 6A.S1 run-report must be `PASS`
  - `s1_party_base_6A` (schema `schemas.6A.yaml#/s1/party_base`)
- Required priors/taxonomies (ROW_LEVEL; `status=REQUIRED`):
  - `PRODUCT_PRIOR` artefacts (product mix, account-per-party distributions)
  - product linkage/eligibility rules (e.g. `PRODUCT_LINKAGE_RULES`, `PRODUCT_ELIGIBILITY_CONFIG`)
  - `TAXONOMY` artefacts (account types, product families, enums)
- 6A contracts (METADATA_ONLY):
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- Optional contextual inputs (if sealed):
  - upstream region/geo or socio-economic surfaces
  - aggregate 5A/5B volume hints (must respect `read_scope`)

## Outputs / datasets
- `s2_account_base_6A` (required; schema `schemas.6A.yaml#/s2/account_base`)
  - Partition keys: `seed`, `manifest_fingerprint`
  - Columns include `parameter_hash`, `account_id`, owner refs, product attributes
- `s2_party_product_holdings_6A` (required; schema `schemas.6A.yaml#/s2/party_product_holdings`)
  - Derived from `s2_account_base_6A` and `s1_party_base_6A`
- Optional derived views:
  - `s2_merchant_account_base_6A` (schema `schemas.6A.yaml#/s2/merchant_account_base`)
  - `s2_account_summary_6A` (schema `schemas.6A.yaml#/s2/account_summary`)

## RNG logs / events
- RNG families for:
  - `account_count_realisation`
  - `account_allocation_sampling`
  - `account_attribute_sampling`
- RNG event tables + layer-wide trace logs (Philox envelope)

## Deliverables / reports
- Run-report record (state_id `6A.S2`, status, error_code, run_id, `spec_version_6A`)
- Required metrics:
  - `total_accounts`
  - `accounts_by_type`, `accounts_by_product_family` (optional), `accounts_by_region`, `accounts_by_segment`
  - `accounts_per_party_min`, `accounts_per_party_max`, `accounts_per_party_mean`, `accounts_per_party_pXX`
  - `rng_account_count_events`, `rng_account_count_draws`
  - `rng_account_allocation_events`, `rng_account_allocation_draws`
  - `rng_account_attribute_events`, `rng_account_attribute_draws`

## Authority / policies / configs
- `s0_gate_receipt_6A` and `sealed_inputs_6A` are authoritative for allowed inputs
- `s1_party_base_6A` is authoritative for party identity and segmentation
- S2 is the sole authority for account universe and ownership topology
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, seed)` and independent of `run_id`


---

# 6A.S3 artefacts/policies/configs (from state.6A.s3.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6A`
  - `sealed_inputs_6A` (whitelisted artefacts + `read_scope`)
  - latest 6A.S0 run-report must be `PASS`
- S1/S2 gates:
  - latest 6A.S1 run-report must be `PASS`
  - `s1_party_base_6A` (schema `schemas.6A.yaml#/s1/party_base`)
  - latest 6A.S2 run-report must be `PASS`
  - `s2_account_base_6A` (schema `schemas.6A.yaml#/s2/account_base`)
  - `s2_party_product_holdings_6A` (schema `schemas.6A.yaml#/s2/party_product_holdings`)
- Required priors/taxonomies (ROW_LEVEL; `status=REQUIRED`):
  - instrument mix priors (`PRODUCT_PRIOR` / `INSTRUMENT_PRIOR`)
  - instrument linkage/eligibility rules (`INSTRUMENT_LINKAGE_RULES` / `PRODUCT_LINKAGE_RULES`)
  - `TAXONOMY` artefacts (instrument types, schemes, brands, token types)
- 6A contracts (METADATA_ONLY):
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- Optional contextual inputs (if sealed):
  - region/scheme penetration hints, aggregated L2 volume hints (must respect `read_scope`)

## Outputs / datasets
- `s3_instrument_base_6A` (required; schema `schemas.6A.yaml#/s3/instrument_base`)
  - Partition keys: `seed`, `manifest_fingerprint`
- `s3_account_instrument_links_6A` (required; schema `schemas.6A.yaml#/s3/account_instrument_links`)
  - Partition keys: `seed`, `manifest_fingerprint`
- Optional derived views:
  - `s3_party_instrument_holdings_6A` (derived holdings)
  - `s3_instrument_summary_6A` (aggregate counts/QA)

## RNG logs / events
- RNG families for:
  - `instrument_count_realisation`
  - `instrument_allocation_sampling`
  - `instrument_attribute_sampling`
- RNG event tables + layer-wide trace logs (Philox envelope)

## Deliverables / reports
- Run-report record (state_id `6A.S3`, status, error_code, run_id, `spec_version_6A`)
- Required metrics:
  - `total_instruments`
  - `instruments_by_type`, `instruments_by_scheme`, `instruments_by_account_type`
  - `instruments_by_party_segment`, `instruments_by_region`
  - `instruments_per_account_min`, `instruments_per_account_max`, `instruments_per_account_mean`, `instruments_per_account_pXX`
  - optional `instruments_per_party_*` metrics
  - `rng_instrument_count_events`, `rng_instrument_count_draws`
  - `rng_instrument_allocation_events`, `rng_instrument_allocation_draws`
  - `rng_instrument_attribute_events`, `rng_instrument_attribute_draws`

## Authority / policies / configs
- `s0_gate_receipt_6A` and `sealed_inputs_6A` are authoritative for allowed inputs
- `s1_party_base_6A` is authoritative for party identity/segmentation
- `s2_account_base_6A` is authoritative for account identity/ownership
- S3 is the sole authority for instrument universe and account-instrument links
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, seed)` and independent of `run_id`


---

# 6A.S4 artefacts/policies/configs (from state.6A.s4.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6A`
  - `sealed_inputs_6A` (whitelisted artefacts + `read_scope`)
  - latest 6A.S0 run-report must be `PASS`
- S1/S2/S3 gates:
  - latest 6A.S1 run-report must be `PASS`
  - `s1_party_base_6A` (schema `schemas.6A.yaml#/s1/party_base`)
  - latest 6A.S2 run-report must be `PASS`
  - `s2_account_base_6A` (schema `schemas.6A.yaml#/s2/account_base`)
  - `s2_party_product_holdings_6A` (schema `schemas.6A.yaml#/s2/party_product_holdings`)
  - latest 6A.S3 run-report must be `PASS`
  - `s3_instrument_base_6A` (schema `schemas.6A.yaml#/s3/instrument_base`)
  - `s3_account_instrument_links_6A` (schema `schemas.6A.yaml#/s3/account_instrument_links`)
- Required priors/taxonomies (ROW_LEVEL; `status=REQUIRED`):
  - `DEVICE_PRIOR` artefacts (device counts + device-type mix)
  - `IP_PRIOR` / `ENDPOINT_PRIOR` artefacts (IP counts + IP-type mix)
  - graph/linkage rules (`GRAPH_LINKAGE_RULES` / `DEVICE_LINKAGE_RULES`)
  - `TAXONOMY` artefacts (device_type, os_family, ip_type, asn_class, risk tags)
- 6A contracts (METADATA_ONLY):
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- Optional contextual inputs (if sealed):
  - connectivity/ASN mix surfaces, merchant channel mix hints (respect `read_scope`)

## Outputs / datasets
- `s4_device_base_6A` (required; schema `schemas.6A.yaml#/s4/device_base`)
- `s4_ip_base_6A` (required; schema `schemas.6A.yaml#/s4/ip_base`)
- `s4_device_links_6A` (required; schema `schemas.6A.yaml#/s4/device_links`)
- `s4_ip_links_6A` (required; schema `schemas.6A.yaml#/s4/ip_links`)
- Optional derived views:
  - `s4_entity_neighbourhoods_6A`
  - `s4_network_summary_6A`

## RNG logs / events
- RNG families for:
  - `device_count_realisation`
  - `device_allocation_sampling`
  - `device_attribute_sampling`
  - `ip_count_realisation`
  - `ip_allocation_sampling`
  - `ip_attribute_sampling`
- RNG event tables + layer-wide trace logs (Philox envelope)

## Deliverables / reports
- Run-report record (state_id `6A.S4`, status, error_code, run_id, `spec_version_6A`)
- Required metrics:
  - `total_devices`, `total_ips`
  - `devices_by_type`, `devices_by_os_family`, `devices_by_region` (optional `devices_by_party_segment`)
  - `ips_by_type`, `ips_by_asn_class`, `ips_by_region`
  - `devices_per_party_min`, `devices_per_party_max`, `devices_per_party_mean`, `devices_per_party_pXX`
  - `ips_per_device_min`, `ips_per_device_max`, `ips_per_device_mean`, `ips_per_device_pXX`
  - shared-device/shared-IP counts (high-degree indicators)
  - `rng_device_count_events`, `rng_device_count_draws`
  - `rng_device_allocation_events`, `rng_device_allocation_draws`
  - `rng_device_attribute_events`, `rng_device_attribute_draws`
  - `rng_ip_count_events`, `rng_ip_count_draws`
  - `rng_ip_allocation_events`, `rng_ip_allocation_draws`
  - `rng_ip_attribute_events`, `rng_ip_attribute_draws`

## Authority / policies / configs
- `s0_gate_receipt_6A` and `sealed_inputs_6A` are authoritative for allowed inputs
- `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A` are authoritative for parties/accounts/instruments
- S4 is the sole authority for device/IP universes and graph links
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, seed)` and independent of `run_id`


---

# 6A.S5 artefacts/policies/configs (from state.6A.s5.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6A`
  - `sealed_inputs_6A` (whitelisted artefacts + `read_scope`)
  - latest 6A.S0 run-report must be `PASS`
- S1-S4 gates and bases:
  - latest 6A.S1/S2/S3/S4 run-reports must be `PASS`
  - `s1_party_base_6A`, `s2_account_base_6A`, `s2_party_product_holdings_6A`
  - `s3_instrument_base_6A`, `s3_account_instrument_links_6A`
  - `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A`
- Required priors/taxonomies (ROW_LEVEL; `status=REQUIRED`):
  - fraud-role priors (`FRAUD_ROLE_PRIOR` / `FRAUD_PRIOR`)
  - fraud taxonomies (`TAXONOMY` for party/account/merchant/device/ip roles, risk tiers)
  - validation policy/checklist (`VALIDATION_POLICY_6A` / `SEGMENT_CHECKLIST_6A`)
- 6A contracts (METADATA_ONLY):
  - `schemas.layer3.yaml`
  - `schemas.6A.yaml`
  - `dataset_dictionary.layer3.6A.yaml`
  - `artefact_registry_6A.yaml`
- Optional contextual inputs (if sealed):
  - upstream risk summaries or policy parameters (must respect `read_scope`)

## Outputs / datasets
- Fraud-role surfaces (seed-scoped):
  - `s5_party_fraud_roles_6A`
  - `s5_account_fraud_roles_6A`
  - `s5_merchant_fraud_roles_6A`
  - `s5_device_fraud_roles_6A`
  - `s5_ip_fraud_roles_6A`
- Validation artefacts (fingerprint-scoped):
  - `s5_validation_report_6A`
  - `s5_issue_table_6A` (optional)
  - `validation_bundle_index_6A`
  - `validation_passed_flag_6A` (`_passed.flag`)

## RNG logs / events
- RNG families for fraud-role sampling:
  - `fraud_role_sampling_party`
  - `fraud_role_sampling_account`
  - `fraud_role_sampling_merchant`
  - `fraud_role_sampling_device`
  - `fraud_role_sampling_ip`
- RNG event tables + layer-wide trace/audit logs

## Deliverables / reports
- Seed-level run-report record (state_id `6A.S5`, status, error_code, run_id, `spec_version_6A`)
- Required metrics (per seed):
  - entity totals: `total_parties`, `total_accounts`, `total_merchants`, `total_devices`, `total_ips`
  - role counts/proportions per entity type (`roles_*_counts`, `roles_*_proportions`)
  - optional cell-level fraud summaries (per region/segment/type)
  - RNG metrics: `rng_party_role_events/draws`, `rng_account_role_events/draws`, `rng_merchant_role_events/draws`, `rng_device_role_events/draws`, `rng_ip_role_events/draws`
- World-level status exposure via validation bundle + `_passed.flag`

## Authority / policies / configs
- `s0_gate_receipt_6A` and `sealed_inputs_6A` are authoritative for allowed inputs
- S1-S4 bases are authoritative for world structure; S5 overlays static fraud roles
- S5 is the sole authority for fraud-role surfaces and the 6A validation bundle/HashGate
- RNG-bearing for role sampling; outputs deterministic for `(manifest_fingerprint, seed)` and independent of `run_id`


---

# 6B.S0 artefacts/policies/configs (from state.6B.s0.expanded.md only)

## Inputs / references
- Required upstream HashGates (bundle + `_passed.flag`):
  - 1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A
- Upstream sealed-input manifests (where available):
  - `sealed_inputs_5A`, `sealed_inputs_5B`, `sealed_inputs_6A` (must be schema-valid)
- Layer-3 / 6B contracts:
  - `schemas.layer3.yaml`
  - `schemas.6B.yaml`
  - `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_6B.yaml`
- Catalogue/dictionary/registry for upstream segments:
  - `schemas.layer1.yaml`, `schemas.layer2.yaml`
  - dataset dictionaries + artefact registries for 1A-3B, 5A-5B, 6A
- 6B config/policy packs (sealed, schema-valid):
  - behaviour priors (e.g. `behaviour_prior_pack_6B`)
  - campaign config (e.g. `campaign_catalogue_config_6B`)
  - labelling policy (e.g. `labelling_policy_6B`)
  - validation policy (e.g. `validation_policy_6B`)

## Outputs / datasets
- `s0_gate_receipt_6B` (gate receipt; schema `schemas.layer3.yaml#/gate/6B/s0_gate_receipt_6B`)
- `sealed_inputs_6B` (sealed input manifest; schema `schemas.layer3.yaml#/gate/6B/sealed_inputs_6B`)
- `sealed_inputs_digest_6B` (digest recorded in `s0_gate_receipt_6B`)

## Deliverables / reports
- Run-report section for `segment=6B`, `state=S0` (world-scoped)
- Required run-report fields:
  - `manifest_fingerprint`, `spec_version_6B`, `parameter_hash`
  - `status`, `primary_error_code`, `secondary_error_codes`
  - `sealed_inputs_digest_6B`
  - `upstream_segment_summary` (required segments + status/bundle sha/flag path)
  - `sealed_inputs_summary`:
    - `total_rows`, `rows_by_layer`, `rows_by_segment`
    - `required_rows`, `optional_rows`, `metadata_only_rows`
    - `arrivals_present`, `entity_graph_present`

## Authority / policies / configs
- Upstream HashGates are authoritative for segment PASS/FAIL
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are the sole authority on 6B inputs
- RNG-free; metadata-only state


---

# 6B.S1 artefacts/policies/configs (from state.6B.s1.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6B`
  - `sealed_inputs_6B` (whitelisted artefacts + `read_scope`)
  - run-report must show 6B.S0 `status="PASS"` for `manifest_fingerprint`
- Required arrivals (ROW_LEVEL):
  - `arrival_events_5B` (from 5B; partitioned by `seed`, `manifest_fingerprint`, `scenario_id`)
- Required entities/posture (ROW_LEVEL, from 6A):
  - `s1_party_base_6A`
  - `s2_account_base_6A`
  - `s3_instrument_base_6A`
  - `s3_account_instrument_links_6A` (or equivalent)
  - `s4_device_base_6A`
  - `s4_ip_base_6A`
  - `s4_device_links_6A`
  - `s4_ip_links_6A`
  - `s5_party_fraud_roles_6A`
  - `s5_account_fraud_roles_6A`
  - `s5_device_fraud_roles_6A`
  - `s5_ip_fraud_roles_6A`
  - `s5_merchant_fraud_roles_6A` (if required by policy)
- 6B behaviour configs/policies (ROW_LEVEL):
  - `behaviour_prior_pack_6B`
  - `sessionisation_policy_6B` (may be embedded in behaviour pack)
  - `entity_attachment_policy_6B` (if separate)
  - `rng_policy_6B_S1` (if separate from layer RNG config)
- Layer-3 RNG/numeric policy (metadata-only):
  - Layer-3 RNG envelope/event family definitions
  - numeric policy / math profile for probabilities (sealed via contracts)
- Contract files / dictionaries:
  - `schemas.layer3.yaml` (gate + RNG envelope)
  - `schemas.6B.yaml` (S1 outputs)
  - `schemas.5B.yaml`, `schemas.6A.yaml` (input schema refs in `sealed_inputs_6B`)
  - `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_6B.yaml`
  - `dataset_dictionary.layer2.5B.yaml` (arrival partitions)

## Outputs / datasets
- `s1_arrival_entities_6B` (required; schema `schemas.6B.yaml#/s1/arrival_entities_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s1_session_index_6B` (required; schema `schemas.6B.yaml#/s1/session_index_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`

## RNG logs / events
- RNG families (Layer-3 envelope):
  - `rng_event_entity_attach`
  - `rng_event_session_boundary`

## Deliverables / reports
- Run-report entry per `(manifest_fingerprint, seed, scenario_id)`
- Required summary metrics:
  - `arrival_count_5B`, `arrival_count_S1`, `session_count_S1`
  - `arrival_coverage_ok`, `session_coverage_ok`
  - `attachment_missing_entities_count`, `attachment_invalid_fk_count`
  - session distribution hints (e.g. `avg_arrivals_per_session`, `p95_arrivals_per_session`, `max_arrivals_per_session`, `avg_session_duration_seconds`)

## Authority / policies / configs
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are authoritative for allowed inputs
- `arrival_events_5B` is authoritative for arrivals; 6A bases/links/posture are authoritative for entities
- S1 is the sole authority for arrival-entity attachments and sessionisation
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and independent of `run_id`


---

# 6B.S2 artefacts/policies/configs (from state.6B.s2.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6B`
  - `sealed_inputs_6B` (whitelisted artefacts + `read_scope`)
  - run-report must show 6B.S0 `status="PASS"` for `manifest_fingerprint`
- S1 gate evidence:
  - run-report must show 6B.S1 `status="PASS"` for `(manifest_fingerprint, seed, scenario_id)`
- Required S1 surfaces (ROW_LEVEL):
  - `s1_arrival_entities_6B`
  - `s1_session_index_6B`
- Required S2 config packs (ROW_LEVEL; names per 6B contracts):
  - `flow_shape_policy_6B` (flow structure priors)
  - `amount_model_6B` (amount/currency model)
  - `timing_policy_6B` (timing/spacing policy, if separate)
  - `flow_rng_policy_6B` (S2 RNG family/budget policy)
- Optional context inputs (if sealed in 6B; `status="OPTIONAL"`):
  - `arrival_events_5B` (role `arrival_stream`, typically `read_scope="METADATA_ONLY"`)
  - 6A bases and fraud roles (`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s4_device_base_6A`, `s4_ip_base_6A`, `s5_*_fraud_roles_6A`)
  - 5A intensity surfaces (`merchant_zone_*_5A`)
  - 2B routing plan surfaces
  - 3B virtual routing policy
- Layer-3 RNG/numeric policy (metadata-only):
  - Layer-3 RNG envelope/event family definitions
  - numeric policy / math profile (sealed via contracts)
- Contract files / dictionaries:
  - `schemas.layer3.yaml` (gate + RNG envelope)
  - `schemas.6B.yaml` (S2 outputs and config pack schema refs)
  - `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_6B.yaml`

## Outputs / datasets
- `s2_flow_anchor_baseline_6B` (required plan surface; schema `schemas.6B.yaml#/s2/flow_anchor_baseline_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s2_event_stream_baseline_6B` (required plan surface; schema `schemas.6B.yaml#/s2/event_stream_baseline_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`

## RNG logs / events
- RNG families (Layer-3 envelope, via `flow_rng_policy_6B`):
  - `rng_event_flow_shape`
  - `rng_event_event_timing`
  - `rng_event_amount_draw`

## Deliverables / reports
- Run-report entry per `(manifest_fingerprint, seed, scenario_id)`
- Required summary metrics:
  - `session_count_S1`, `arrival_count_S1`
  - `flow_count_S2`, `event_count_S2`
  - `flows_have_events_ok`, `no_orphan_events_ok`
  - `session_linkage_ok`, `arrival_linkage_ok`
  - `temporal_consistency_ok`, `amount_consistency_ok`
  - `avg_events_per_flow`, `p95_events_per_flow`, `max_events_per_flow`
  - `fraction_flows_with_refund`, `fraction_flows_declined`

## Authority / policies / configs
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are authoritative for allowed inputs
- `s1_arrival_entities_6B` and `s1_session_index_6B` are authoritative for arrival-entity and session mappings
- `arrival_events_5B` is authoritative for arrival identity/timestamps/routing when cross-checking
- 6A bases/fraud roles are authoritative for entity attributes/posture when used
- 6B flow/amount/timing/RNG policy packs are the only authority for S2 flow/event synthesis
- S2 is the sole authority for baseline flow anchors and baseline event stream
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and independent of `run_id`


---

# 6B.S3 artefacts/policies/configs (from state.6B.s3.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6B`
  - `sealed_inputs_6B` (whitelisted artefacts + `read_scope`)
  - run-report must show 6B.S0 `status="PASS"` for `manifest_fingerprint`
- S1 and S2 gate evidence:
  - run-report must show 6B.S1 and 6B.S2 `status="PASS"` for `(manifest_fingerprint, seed, scenario_id)`
- Required S1/S2 surfaces (ROW_LEVEL):
  - `s1_arrival_entities_6B`
  - `s1_session_index_6B`
  - `s2_flow_anchor_baseline_6B`
  - `s2_event_stream_baseline_6B`
- Required 6A fraud posture surfaces (ROW_LEVEL unless policy allows metadata-only):
  - `s5_party_fraud_roles_6A`
  - `s5_account_fraud_roles_6A`
  - `s5_device_fraud_roles_6A`
  - `s5_ip_fraud_roles_6A`
  - `s5_merchant_fraud_roles_6A` (if required by policy)
- Required fraud/abuse config packs (ROW_LEVEL; names per 6B contracts):
  - `fraud_campaign_catalogue_config_6B` (campaign templates)
  - `fraud_overlay_policy_6B` (overlay mutation rules)
  - `fraud_rng_policy_6B` (S3 RNG families/budgets)
- Optional context inputs (if sealed in 6B; `status="OPTIONAL"`):
  - Additional 6A attributes and posture tables (for targeting/enrichment)
  - 5A/5B context surfaces
  - 2B routing plan surfaces
  - 3B virtual routing policy
- Layer-3 RNG/numeric policy (metadata-only):
  - Layer-3 RNG envelope/event family definitions
  - numeric policy / math profile (sealed via contracts)
- Contract files / dictionaries:
  - `schemas.layer3.yaml` (gate + RNG envelope)
  - `schemas.6B.yaml` (S3 outputs and config pack schema refs)
  - `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_6B.yaml`

## Outputs / datasets
- `s3_campaign_catalogue_6B` (required; schema `schemas.6B.yaml#/s3/campaign_catalogue_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`
- `s3_flow_anchor_with_fraud_6B` (required; schema `schemas.6B.yaml#/s3/flow_anchor_with_fraud_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s3_event_stream_with_fraud_6B` (required; schema `schemas.6B.yaml#/s3/event_stream_with_fraud_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`

## RNG logs / events
- RNG families (Layer-3 envelope, via `fraud_rng_policy_6B`):
  - `rng_event_campaign_activation`
  - `rng_event_campaign_targeting`
  - `rng_event_overlay_mutation`

## Deliverables / reports
- Run-report entry per `(manifest_fingerprint, seed)` for `state="S3_campaign"`
- Run-report entry per `(manifest_fingerprint, seed, scenario_id)` for `state="S3_overlay"`
- Required summary metrics (campaign scope):
  - `campaign_count_total`
  - `campaign_count_by_type`
  - `campaigns_with_targets_total`, `campaigns_without_targets_total`
  - `campaign_target_flow_count_total`, `campaign_target_event_count_total`
- Required summary metrics (overlay scope):
  - `flow_count_baseline`, `flow_count_with_fraud`
  - `event_count_baseline`, `event_count_with_fraud`
  - `flows_untouched_count`, `flows_touched_count`
  - `baseline_flow_coverage_ok`, `flow_event_coverage_ok`, `campaign_linkage_ok`, `entity_routing_consistency_ok`
  - `fraud_flow_fraction`, `fraud_event_fraction`, `avg_fraud_events_per_fraud_flow`
  - Optional per-pattern maps: `fraud_flow_count_by_pattern_type`, `fraud_event_count_by_pattern_type`

## Authority / policies / configs
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are authoritative for allowed inputs
- S1 and S2 outputs are authoritative for attachments, sessions, baseline flows, and baseline events
- 6A fraud role surfaces are authoritative for static fraud posture
- 6B campaign/overlay/RNG policy packs are the only authority for overlay behaviour and targeting
- S3 is the sole authority for campaign catalogue and fraud overlay surfaces
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and independent of `run_id`


---

# 6B.S4 artefacts/policies/configs (from state.6B.s4.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6B`
  - `sealed_inputs_6B` (whitelisted artefacts + `read_scope`)
  - run-report must show 6B.S0 `status="PASS"` for `manifest_fingerprint`
- S1/S2/S3 gate evidence:
  - run-report must show 6B.S1, 6B.S2, and 6B.S3 `status="PASS"` for `(manifest_fingerprint, seed, scenario_id)`
- Required S3 behavioural canvases (ROW_LEVEL):
  - `s3_flow_anchor_with_fraud_6B`
  - `s3_event_stream_with_fraud_6B`
- Required S3 provenance:
  - `s3_campaign_catalogue_6B`
- Required context surfaces (if mandated by label policy):
  - S2 baseline surfaces: `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B` (often `METADATA_ONLY`)
  - S1 surfaces: `s1_arrival_entities_6B`, `s1_session_index_6B`
  - 6A fraud roles: `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`
- Required S4 config packs (ROW_LEVEL; names per 6B contracts):
  - `truth_labelling_policy_6B`
  - `bank_view_policy_6B`
  - `delay_models_6B`
  - `case_policy_6B`
  - `label_rng_policy_6B`
- Optional context inputs (if sealed in 6B; `status="OPTIONAL"`):
  - Additional 6A attributes or monitoring surfaces
- Layer-3 RNG/numeric policy (metadata-only):
  - Layer-3 RNG envelope/event family definitions
  - numeric policy / math profile (sealed via contracts)
- Contract files / dictionaries:
  - `schemas.layer3.yaml` (gate + RNG envelope)
  - `schemas.6B.yaml` (S4 outputs and policy schema refs)
  - `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_6B.yaml`

## Outputs / datasets
- `s4_flow_truth_labels_6B` (required; schema `schemas.6B.yaml#/s4/flow_truth_labels_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s4_flow_bank_view_6B` (required; schema `schemas.6B.yaml#/s4/flow_bank_view_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s4_event_labels_6B` (required; schema `schemas.6B.yaml#/s4/event_labels_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`, `scenario_id`
- `s4_case_timeline_6B` (required; schema `schemas.6B.yaml#/s4/case_timeline_6B`)
  - Partition keys: `seed`, `manifest_fingerprint`

## RNG logs / events
- RNG families (Layer-3 envelope, via `label_rng_policy_6B`):
  - `rng_event_truth_label_ambiguity`
  - `rng_event_detection_delay`
  - `rng_event_dispute_delay`
  - `rng_event_chargeback_delay`
  - `rng_event_case_timeline`

## Deliverables / reports
- Run-report entry per `(manifest_fingerprint, seed, scenario_id)` for `state="S4_labels"`
- Run-report entry per `(manifest_fingerprint, seed)` for `state="S4_cases"`
- Required summary metrics (label scope):
  - `flow_count_S3`, `flow_count_labeled`
  - `truth_label_distribution`, `truth_subtype_distribution`
  - `bank_view_label_distribution`, `detection_outcome_distribution`
  - `fraud_flow_count_truth`, `fraud_flow_detected_count`, `fraud_detection_rate`
  - `chargeback_count`
  - `event_count_S3`, `event_count_labeled`
  - `fraud_event_count_truth`, `detection_event_count`, `case_event_flagged_count`
  - `flow_label_coverage_ok`, `event_label_coverage_ok`
  - `truth_consistency_ok`, `bank_view_consistency_ok`
- Required summary metrics (case scope):
  - `case_count_total`, `case_event_count_total`
  - `flows_in_cases_total`, `flows_in_cases_by_truth_label`
  - `case_status_distribution` (if encoded)
  - `avg_case_duration_seconds`

## Authority / policies / configs
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are authoritative for allowed inputs
- S3 overlays are authoritative for behavioural surfaces to label
- S2 baseline surfaces are reference context only; S4 must not bypass S3
- 6A fraud roles are authoritative for static posture
- S4 policy packs are the only authority for truth labels, bank-view outcomes, delays, and case rules
- S4 is the sole authority for label and case timeline outputs
- RNG-bearing; outputs deterministic for `(manifest_fingerprint, parameter_hash, seed, scenario_id)` and independent of `run_id`


---

# 6B.S5 artefacts/policies/configs (from state.6B.s5.expanded.md only)

## Inputs / references
- Gate evidence (from S0):
  - `s0_gate_receipt_6B`
  - `sealed_inputs_6B` (whitelisted artefacts + `read_scope`)
- Required upstream HashGates (bundle + `_passed.flag`):
  - 1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A
- Required 6B data-plane surfaces (S1-S4):
  - `s1_arrival_entities_6B`, `s1_session_index_6B`
  - `s2_flow_anchor_baseline_6B`, `s2_event_stream_baseline_6B`
  - `s3_campaign_catalogue_6B`, `s3_flow_anchor_with_fraud_6B`, `s3_event_stream_with_fraud_6B`
  - `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_event_labels_6B`, `s4_case_timeline_6B`
- Required control-plane/report inputs:
  - Layer-3 run-report entries for S1, S2, S3_overlay, S4_labels (per seed/scenario)
  - Layer-3 run-report entries for S4_cases (per seed)
- Required S5 policy packs:
  - `segment_validation_policy_6B`
  - `segment_validation_rng_policy_6B` (if non-trivial; S5 typically RNG-free)
- Contract files / dictionaries / registries:
  - `schemas.layer1.yaml`, `schemas.layer2.yaml`, `schemas.layer3.yaml`
  - `schemas.1A.yaml` .. `schemas.3B.yaml`, `schemas.5A.yaml`, `schemas.5B.yaml`, `schemas.6A.yaml`, `schemas.6B.yaml`
  - `dataset_dictionary.layer1.*.yaml`, `dataset_dictionary.layer2.*.yaml`, `dataset_dictionary.layer3.6A.yaml`, `dataset_dictionary.layer3.6B.yaml`
  - `artefact_registry_1A.yaml` .. `artefact_registry_3B.yaml`, `artefact_registry_5A.yaml`, `artefact_registry_5B.yaml`, `artefact_registry_6A.yaml`, `artefact_registry_6B.yaml`

## Outputs / datasets
- `s5_validation_report_6B` (required; schema `schemas.layer3.yaml#/validation/6B/s5_validation_report`)
  - Partition keys: `manifest_fingerprint`
- `s5_issue_table_6B` (optional; schema `schemas.layer3.yaml#/validation/6B/s5_issue_table`)
  - Partition keys: `manifest_fingerprint`
- `validation_bundle_6B` (bundle directory under `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/`)
- `validation_bundle_index_6B` (`index.json`; schema `schemas.layer3.yaml#/validation/6B/validation_bundle_index_6B`)
  - Partition keys: `manifest_fingerprint`
- `validation_passed_flag_6B` (`_passed.flag`; schema `schemas.layer3.yaml#/validation/6B/passed_flag_6B`)

## Deliverables / reports
- World-scoped run-report entry for `segment="6B"`, `state="S5"`
- `s5_validation_report_6B` with per-check PASS/WARN/FAIL and `overall_status`
- Optional `s5_issue_table_6B` with per-check or per-artefact anomalies

## Authority / policies / configs
- `s0_gate_receipt_6B` and `sealed_inputs_6B` are authoritative for allowed inputs and contracts
- Upstream HashGate `_passed.flag` bundles are authoritative for upstream segment validity
- Schema packs and dictionaries/registries are authoritative for shapes, ids, and paths
- `segment_validation_policy_6B` is the sole authority for S5 check selection and severity
- S5 is the sole authority to emit `validation_bundle_6B` and `validation_passed_flag_6B`
- Hashing law: bundle index paths sorted ASCII-lex; SHA-256 over raw bytes of listed files; `_passed.flag` excluded from index
- RNG-free by default; if RNG is configured, must follow `segment_validation_rng_policy_6B`
