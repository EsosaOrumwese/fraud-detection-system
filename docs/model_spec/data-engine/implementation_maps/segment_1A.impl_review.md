# Segment 1A Implementation Review (code-derived)

## Scope and sources
- Derived from `packages/engine` only; implementation maps were not used.
- Covers Segment 1A from pre-state inputs through S9 validation as executed today.
- The intent is descriptive: what the engine does, what it reads/writes, and how it logs and validates.

## Entry points and execution flow
### CLI entry point
- `packages/engine/src/engine/cli/segment1a.py` is the user-facing runner.
- Stages Segment 1B reference surfaces into `<output-dir>/reference/**` when `--stage-seg1b-refs` is enabled.
- Collects parameters (`--param NAME=PATH`), validation policy, extra manifest artifacts, and S3/S4 toggles.
- Invokes `Segment1AOrchestrator.run` and optionally writes a JSON summary via `--result-json`.
- Note: the CLI docstring says S0-S7, but it calls the orchestrator which runs S0-S9.

### Orchestrator (S0-S9 pipeline)
- `packages/engine/src/engine/scenario_runner/l1_seg_1A.py` (`Segment1AOrchestrator.run`) is the main pipeline.
- Flow is sequential: S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9.
- Uses `state_heartbeat` logging around each state for progress tracking.
- Builds deterministic contexts between states (`engine/scenario_runner/l1_seg_1A_contexts.py`).

### Policy and config resolution
- S5 policy resolution in `Segment1AOrchestrator._resolve_s5_policy_path` checks:
  - `ccy_smoothing_params.yaml` and `config/allocation/ccy_smoothing_params.yaml` as fallbacks.
- S6 policy resolution in `_resolve_s6_policy_path` checks:
  - `s6_selection_policy.yaml` and `config/allocation/s6_selection_policy.yaml` as fallbacks.
- S7 thresholds policy resolution in `_resolve_s7_policy_path` checks:
  - `policy.s3.thresholds.yaml` and `config/policy/s3.thresholds.yaml` as fallbacks.
- `s7_integer_allocation/policy.py` also loads:
  - Residual quantisation policy default: `config/numeric/residual_quantisation.yaml`.
  - Dirichlet policy default: `config/models/allocation/dirichlet_alpha_policy.yaml`.

## Cross-cutting conventions
### Lineage identifiers
- `parameter_hash`, `manifest_fingerprint`, and `run_id` are minted in S0 and threaded through S1-S9.
- `seed` is user-supplied and is the Philox root seed.

### Dataset dictionary and path resolution
- `packages/engine/src/engine/layers/l1/seg_1A/shared/dictionary.py` loads
  `contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`.
- `resolve_dataset_path()` resolves dataset IDs with template args into concrete paths.
- If dataset paths include `part-*.parquet`, resolution canonicalizes to `part-00000.parquet`.

### Passed flag gate
- `_passed.flag` format is defined in `packages/engine/src/engine/layers/l1/seg_1A/shared/passed_flag.py`.
- S5 writes `S5_VALIDATION.json` and `_passed.flag` and S6 refuses to read weights without it.
- S6 writes `S6_VALIDATION.json` and `_passed.flag`, which S8 and S9 verify when membership is present.
- S8 validation bundles are gated with `_passed.flag` via `refresh_validation_bundle_flag`.
- S9 validation bundles write `_passed.flag` when validation passes.

### RNG logs
- Most RNG event streams are written under `logs/rng/events/<stream>/seed=.../parameter_hash=.../run_id=.../part-00000.jsonl`.
- Trace logs are generally under `logs/rng/trace/seed=.../parameter_hash=.../run_id=.../rng_trace_log.jsonl`.
- S0 writes audit logs under `logs/rng/audit/seed=.../parameter_hash=.../run_id=.../rng_audit_log.jsonl`.
- S7 residual and dirichlet writers do not embed `parameter_hash`/`manifest_fingerprint` in event payloads.

### Validation bundles
- S0 writes `validation_bundle_1A` using the dataset dictionary path.
- S8 writes a `validation_bundle_1A` with `rng_accounting.json`, `s8_metrics.json`,
  `egress_checksums.json`, and `_passed.flag`.
- S9 writes its own bundle under `data/layer1/1A/validation/fingerprint=...` and
  includes `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`,
  `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`, and optional `_passed.flag`.

## State-by-state implementation

### S0 Foundations
Code: `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/output.py`

Inputs:
- Merchant, ISO, GDP, and GDP bucket tables (parquet).
- Parameter files (see `_REQUIRED_PARAMETER_FILES` in `s0_foundations/l2/runner.py`).
- Required governance inputs: `numeric_policy.json` and `math_profile_manifest.json`.
- Extra manifest artifacts include staged Segment 1B references, S5/S6/S7 policies, and optional S4 feature view.

Processing:
- Builds `RunContext` from ingress tables and schema authority.
- Computes `parameter_hash` from required parameter files.
- Computes `manifest_fingerprint` from manifest artifacts plus git commit hex and parameter hash.
- Derives `run_id` using the manifest fingerprint, seed, and current time.
- Emits an anchor RNG event using `RNGLogWriter` (`s0_foundations/l2/rng_logging.py`).

Outputs:
- `crossborder_eligibility_flags` (parquet)
- `hurdle_design_matrix` (parquet)
- Optional diagnostics: `hurdle_pi_probs` (parquet)
- Validation bundle `validation_bundle_1A` with lineage and policy attestations
- `rng_audit_log` JSONL

Validation and gating:
- If `validate=True`, runs `s0_foundations/l3/validator.validate_outputs`.
- On failure, emits a failure record via `s0_foundations/l2/failure.py`.

### S1 Hurdle
Code: `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/l2/output.py`

Inputs:
- Hurdle coefficients from S0 and per-merchant design vectors.
- Philox seed and manifest fingerprint from S0.

Processing:
- Derives per-merchant hurdle substreams (`HURDLE_SUBSTREAM_LABEL = hurdle_bernoulli`).
- Writes hurdle Bernoulli events and trace logs.
- Builds a catalogue of gated streams (if present) and a list of multi-site merchants.

Outputs:
- RNG events: `logs/rng/events/hurdle_bernoulli/.../part-00000.jsonl`
- RNG trace: `logs/rng/trace/.../rng_trace_log.jsonl`
- Hurdle catalogue via `s1_hurdle/l3/catalogue.py`

Validation:
- `validate_hurdle_run` is called by the orchestrator when `validate_s1=True`.

### S2 Negative Binomial Outlets
Code: `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/l2/output.py`

Inputs:
- Deterministic context built from S0 outputs and S1 decisions.

Processing:
- Uses Philox substreams to emit gamma and poisson components.
- Emits a non-consuming `nb_final` event per merchant with accepted outlet counts.

Outputs:
- RNG events: `gamma_component`, `poisson_component`, `nb_final` streams.
- RNG trace: `logs/rng/trace/.../rng_trace_log.jsonl`.
- Catalogue and validation artifacts via `s2_nb_outlets/l3/catalogue.py` and `s2_nb_outlets/l3/bundle.py`.

Validation:
- When `validate_s2=True`, runs `validate_nb_run` with the provided validation policy.

### S3 Crossborder Universe
Code: `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder_universe/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder_universe/l1/kernels.py`

Inputs:
- Merchant profiles (multi-site only), S1 decisions, S2 finals, ISO table.
- Required policy: `policy.s3.rule_ladder.yaml`.
- Optional policies: base weight, thresholds, bounds.
- Feature toggles: priors, integerisation, sequencing.

Processing:
- Evaluates rule ladder and builds candidate sets.
- Optional: base weight priors, integerised counts, site sequencing.

Outputs:
- `s3_candidate_set` (parquet)
- Optional `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence` (parquet)
- Validation artifacts via `s3_crossborder_universe/l3/bundle.py`.

Validation:
- `validate_s3_outputs` runs when `validate_s3=True` and emits validation artifacts.

### S4 ZTP Target
Code: `packages/engine/src/engine/layers/l1/seg_1A/s4_ztp_target/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s4_ztp_target/l0/writer.py`

Inputs:
- `crossborder_hyperparams.yaml` and deterministic context from S1/S2/S3/S0.
- Optional `crossborder_features` view.

Processing:
- Uses ZTP sampler with Philox RNG.
- Writes gamma, poisson, rejection, retry_exhausted, and final events.

Outputs:
- RNG events: `rng_event_gamma_component`, `rng_event_poisson_component`,
  `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, `rng_event_ztp_final`.
- RNG trace: `logs/rng/trace/.../rng_trace_log.jsonl`.
- Validation bundle via `s4_ztp_target/l3/bundle.py` when enabled.

### S5 Currency Weights
Code: `packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/persist.py`

Inputs:
- Policy file `ccy_smoothing_params.yaml` (governed, resolved by orchestrator).
- Reference surfaces from `reference/network/...` and `reference/iso/...`.
- Merchant currency inputs derived from S0 ingress records.

Processing:
- Loads share surfaces and legal tender mapping.
- Builds blended weights per currency with quantisation and overrides.
- Optional derivation of `merchant_currency` cache.
- Stage logging under `logs/stages/s5_currency_weights/.../S5_STAGES.jsonl`.
- Uses a staging dir under `<base_path>/tmp/s5_<uuid>` and atomically moves to final partitions.

Outputs:
- `ccy_country_weights_cache` (parquet)
- Optional `sparse_flag` (parquet)
- Optional `merchant_currency` (parquet)
- Receipt: `S5_VALIDATION.json` and `_passed.flag` alongside weights partition

Validation:
- Verifies that RNG totals do not change during S5 (must be deterministic).

### S6 Foreign Selection
Code: `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_selection/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_selection/loader.py`

Inputs:
- `s3_candidate_set` and S5 weights (`ccy_country_weights_cache`).
- S4 `rng_event_ztp_final` for K targets.
- `crossborder_eligibility_flags` (S0).
- Optional `merchant_currency` (S5) or fallback via ISO legal tender lookup.
- Policy file `s6_selection_policy.yaml` (governed, resolved by orchestrator).

Processing:
- Verifies S5 receipt before reading weights.
- Uses Philox Gumbel substream per merchant and candidate.
- Writes gumbel_key events for selected candidates or full candidate domain depending on policy.
- Optional membership dataset for selected countries.

Outputs:
- RNG events: `rng_event.gumbel_key` stream under `logs/rng/events/gumbel_key`.
- RNG trace: `logs/rng/trace/.../rng_trace_log.jsonl`.
- Optional `s6_membership` parquet.
- Receipt: `S6_VALIDATION.json` and `_passed.flag` under `s6_validation_receipt`.
- Metrics log: `logs/metrics/s6/.../merchant_metrics.jsonl`.

Validation:
- `s6_foreign_selection/validate.py` validates events, membership alignment, and counter replay.

### S7 Integer Allocation
Code: `packages/engine/src/engine/layers/l1/seg_1A/s7_integer_allocation/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s7_integer_allocation/kernel.py`

Inputs:
- S6 deterministic context and selection results.
- S2 final outlet counts (`nb_final`).
- Policies: thresholds, residual quantisation, optional dirichlet alpha policy.

Processing:
- Builds allocation domain of home + selected foreigns.
- Applies largest-remainder allocation with optional bounds.
- Emits non-consuming residual_rank events for every merchant-country allocation.
- Optional dirichlet_gamma_vector events if the dirichlet policy is enabled.

Outputs:
- RNG events: `rng_event.residual_rank` (non-consuming).
- Optional RNG events: `rng_event.dirichlet_gamma_vector`.
- RNG trace: `logs/rng/trace/.../rng_trace_log.jsonl`.
- Allocation results are returned in memory to S8 (no parquet outputs here).

Validation:
- `s7_integer_allocation/validate.py` checks structural invariants on allocation results.

### S8 Outlet Catalogue
Code: `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/persist.py`

Inputs:
- S0 merchant universe, S1 hurdle decisions, S2 nb_final results.
- S7 allocation results (in memory).
- Optional S6 membership (parquet) and S3 integerised counts (parquet).
- `s3_candidate_set` for candidate rank lookups.

Processing:
- Builds per-merchant sequencing inputs and emits outlet rows.
- Enforces per-merchant sum law and site_id sequence bounds (MAX_SEQUENCE=999999).
- Emits sequence_finalize and overflow events (non-consuming).
- Writes stage log `logs/stages/s8_outlet_catalogue/S8_STAGES.jsonl`.

Outputs:
- `outlet_catalogue` parquet partition (seed and manifest_fingerprint scoped).
- RNG events: `rng_event.sequence_finalize` and `rng_event.site_sequence_overflow`.
- RNG trace entries updated via the S8 event writer.
- Validation bundle under `validation_bundle_1A` with `rng_accounting.json`,
  `s8_metrics.json`, and `egress_checksums.json` plus `_passed.flag`.

Validation:
- `s8_outlet_catalogue/validate.py` validates partition tokens, PK uniqueness,
  count histograms, membership alignment, and RNG trace deltas.

### S9 Validation (handover)
Code: `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/validator_core.py`,
`packages/engine/src/engine/layers/l1/seg_1A/s9_validation/persist.py`

Inputs:
- `outlet_catalogue`, `s3_candidate_set` (required).
- Optional `s3_integerised_counts`, `s3_site_sequence`, `s6_membership`.
- RNG logs: `rng_audit_log`, `rng_trace_log`, and all RNG event families.
- Upstream S0 validation bundle (used to pull lineage details when present).

Processing:
- Validates partition tokens for all input datasets.
- Validates required columns, schema refs, ISO codes, and uniqueness.
- Verifies candidate rank continuity and sum-law alignment with counts or nb_final.
- Verifies membership alignment and overflow handling.
- Performs RNG budget accounting and trace coverage checks per event family.
- Recomputes and validates lineage values against upstream manifests.

Outputs:
- Validation bundle written under `data/layer1/1A/validation/fingerprint=...`.
- Files include `MANIFEST.json`, `parameter_hash_resolved.json`,
  `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`,
  `egress_checksums.json`, `index.json`, and optional `_passed.flag`.
- Stage log: `logs/stages/s9_validation/S9_STAGES.jsonl`.

## Observed implementation notes (for contract review)
- Dataset dictionary resolution uses `contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`,
  while several validators load schemas from `docs/model_spec/.../schemas.1A.yaml` and
  other schemas from `contracts/schemas/...`.
- S8 and S9 validation code expects outlet catalogue partitions to use `fingerprint=...`
  in the path tokens, not `manifest_fingerprint=...`.
- S9 writes its validation bundle to a hard-coded path under `data/layer1/1A/validation/`
  instead of using the dataset dictionary.
- Default policy paths in S5/S6/S7 loaders still reference `config/allocation` and
  `config/policy` and may not align with the updated layer-scoped config layout.
