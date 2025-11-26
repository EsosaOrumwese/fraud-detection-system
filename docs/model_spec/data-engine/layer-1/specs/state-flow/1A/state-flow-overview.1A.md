# Layer-1 - Segment 1A - State Overview (S0-S9)

Segment 1A turns the merchant universe into deterministic outlet counts, ordered cross-border candidates, and the outlet stubs that every downstream layer reads. Everything is governed by JSON-Schema, sealed by (`parameter_hash`, `manifest_fingerprint`), and remains read-only once S9 publishes a PASS bundle.

## Segment role at a glance
- Establishes run-lineage (`parameter_hash`, `manifest_fingerprint`, `run_id`) plus the RNG budget law that every later state obeys.
- Decides single vs multi-site merchants, realises multi-site outlet counts, and fixes candidate foreign countries together with their total order.
- Samples the foreign-target count (`K_target`) and deterministically allocates outlets across `{home} U foreigns` using weight surfaces from S5.
- Materialises outlet stubs (`outlet_catalogue`, partitioned by `seed` x `fingerprint`) and ships the validation bundle plus `_passed.flag` that unlock downstream reads.

---

## S0 - Universe, hashes, and RNG law (RNG-free)
**Purpose & scope**
- Freeze the merchant universe from `merchant_ids`, canonical ISO/GDP references, and the JSON-Schema authority so every later state is reproducible.
- Derive and publish `parameter_hash`, `manifest_fingerprint`, `run_id`, and initialise `rng_audit_log` / `rng_trace_log` envelopes for all 1A RNG families.

**Preconditions & gates**
- Ingress references (`merchant_ids`, ISO-3166, GDP 2025-04-15, Jenks buckets) must validate via `schemas.ingress.layer1.yaml`.
- Artefact registry/dictionary entries must point to JSON-Schema only; any Avro reference is a hard fail.

**Inputs (dataset-level)**
- `merchant_ids` (ingress), ISO list, GDP map, GDP bucket map, and governed parameter packs (`hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`, `crossborder_hyperparams.yaml`, `ccy_smoothing_params.yaml`, `s6_selection_policy.yaml`).
- Layer-wide schemas (`schemas.layer1.yaml`, `schemas.1A.yaml`, `schemas.ingress.layer1.yaml`).

**Outputs & identity**
- Parameter-scoped prep artefacts such as `hurdle_design_matrix`, `crossborder_features`, and gating tables (all partitioned by `parameter_hash={parameter_hash}`).
- Run-scoped logs: `rng_audit_log` and `rng_trace_log` under `logs/rng/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.
- Lineage receipts: `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_seed_manifest.json`.

**RNG posture**
- RNG-free; S0 only defines Philox counter families (for example `hurdle_bernoulli`, `gamma_component`, `ztp_final`, `gumbel_key`, `sequence_finalize`) and the open-interval mapping law in `schemas.layer1.yaml#/rng`.

**Key invariants**
- JSON-Schema is the sole authority; every later dataset must embed the same lineage keys as its path (`parameter_hash`, `seed`, `fingerprint`, `run_id`).
- `parameter_hash` tuples include artefact basenames; `manifest_fingerprint` couples opened artefacts plus the repo commit and `parameter_hash`.
- File order is never authoritative; equality is set-based and schema-enforced.

**Downstream consumers**
- All S1-S9 states rely on S0 lineage keys, reference data, and the RNG stream registry; S9 replays S0 hashes before re-validating the segment.

---

## S1 - Hurdle (single vs multi-site merchants)
**Purpose & scope**
- Evaluate logistic hurdle probabilities (pi_m) per merchant and decide `is_multi`, consuming RNG only when the decision is stochastic.

**Preconditions & gates**
- S0 resolved merchants, design matrix `hurdle_design_matrix`, and coefficient pack `hurdle_coefficients`.
- Layer RNG envelope initialised; `rng_audit_log` / `rng_trace_log` partitions exist for `(seed, parameter_hash, run_id)`.

**Inputs**
- `hurdle_design_matrix` (parameter-scoped) and governed coefficients; deterministic design guarantees identical column order.

**Outputs & identity**
- `hurdle_pi_probs` at `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/` (schema `schemas.1A.yaml#/model/hurdle_pi_probs`).
- `rng_event_hurdle_bernoulli` at `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`; one row per stochastic merchant with the standard envelope (`module`, `substream_label`, `before`, `after`, `blocks`, `draws`, lineage columns).

**RNG posture**
- RNG only when `0 < pi_m < 1`; deterministic branches emit no events. Each event uses one Philox block (low lane) mapped to `u in (0,1)`.

**Key invariants**
- Exactly one hurdle decision per `(seed, parameter_hash, merchant_id)`; deterministic branches are RNG-free.
- Branch purity: S2+ states may only execute when `is_multi=true` surfaced by S1 output.
- Envelope equality: lineage columns embedded in events match path keys byte-for-byte; budgets reconcile with `rng_trace_log`.

**Downstream consumers**
- S2 reads `is_multi` to decide whether to draw counts; later segments replay hurdle events for branch gating, and S9 rebuilds pi and Bernoulli draws to prove PASS.

---

## S2 - Total outlet count `N` (Negative-Binomial via Poisson-Gamma)
**Purpose & scope**
- For multi-site merchants, draw `N >= 2` using a NB mixture (Gamma then Poisson) with rejection until the constraint holds; emit RNG evidence for every attempt.

**Preconditions & gates**
- Only merchants with `is_multi=1` may enter; hurdle design/coefficients available; RNG context seeded in S0.

**Inputs**
- Hurdle outputs (`hurdle_pi_probs`), NB coefficients (`nb_dispersion_coefficients`), and feature tuples assembled in S2.1.

**Outputs & identity**
- Event streams: `rng_event_gamma_component`, `rng_event_poisson_component`, and `rng_event_nb_final` (all under `logs/rng/events/*/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`).
- No additional tables; `N` is recovered from `rng_event_nb_final.payload.n_outlets`.

**RNG posture**
- Each Gamma attempt consumes one Philox block (two uniforms); Poisson draws consume per-lane uniforms; `nb_final` is non-consuming and records acceptance metadata (`attempts`, `n_outlets`).

**Key invariants**
- Only multi-site merchants enter; single-site merchants bypass S2 entirely.
- Attempt loop enforces `N >= 2`; `nb_final` writes at most once per merchant with `before == after`.
- Counters are monotone; validators replay draws and reconcile budgets via `rng_trace_log`.

**Downstream consumers**
- S3 and S7 treat `raw_nb_outlet_draw` as authoritative; S6 membership cannot exceed the realised `N`; S9 replays S2 draws and rejection counts.

---

## S3 - Cross-border candidate set, integer counts, sequencing (deterministic)
**Purpose & scope**
- Construct the admissible country set per merchant, assign the total inter-country order (`candidate_rank`, home rank 0), and optionally emit deterministic counts and within-country sequences.

**Preconditions & gates**
- S1 hurdle decisions, S2 outlet counts, and S0 references available; `crossborder_eligibility_flags` / policy ladder validated.

**Inputs**
- Parameter-scoped prep surfaces: `crossborder_eligibility_flags`, weight priors (optional), integerisation policy, bounding config, and `raw_nb_outlet_draw`.

**Outputs & identity**
- `s3_candidate_set` (sole inter-country order authority) at `data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/`, PK `(merchant_id, candidate_rank)`.
- Optional deterministic tables: `s3_base_weight_priors`, `s3_integerised_counts`, `s3_site_sequence` (all parameter-scoped). Sequencing uses `site_order=1..n_i` per `(merchant,country)` and may emit six-digit `site_id`.

**RNG posture**
- RNG-free; all selection, ordering, integerisation, and sequencing steps are deterministic functions of inputs.

**Key invariants**
- Candidate ranks are contiguous integers with `candidate_rank=0` reserved for the merchant home country; no downstream dataset re-encodes cross-country order.
- Integerised counts sum to `N` per merchant, with residuals quantised to `dp=8`; overflow (`n_i > 999999`) raises `ERR_S3_SITE_SEQUENCE_OVERFLOW`.
- Path keys (`parameter_hash`) equal embedded columns; file order is non-authoritative.

**Downstream consumers**
- `s3_candidate_set` is consumed by S4-S9 and by segment 1B when imposing cross-country order; S6 iterates it to emit Gumbel keys; S8/S9 join it to ensure egress never invents ordering.

---

## S4 - `K_target` via Zero-Truncated Poisson (logs only)
**Purpose & scope**
- Sample the target number of foreign countries per merchant using a zero-truncated Poisson draw with governed caps and emit evidence only (no tables).

**Preconditions & gates**
- S3 determined admissible candidate count `A`; S2 provided `N`; S5/S0 produced features required for the link function; merchants flagged `eligible_crossborder` must pass gating.

**Inputs**
- Parameter-scoped features (`crossborder_features`), `s3_candidate_set` for `A`, governed hyperparameters, and RNG envelopes from S0.

**Outputs & identity**
- Event streams: reuse `rng_event_poisson_component` for Poisson draws and write `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, and `rng_event_ztp_final` (all under `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`).
- No persistent dataset; `K_target` is reconstructed from `rng_event_ztp_final.payload.K_target`.

**RNG posture**
- Each attempt consumes one Poisson draw; finalisers are non-consuming; short-circuit branches (for example `A=0`) emit deterministic zero-target rows without draws.

**Key invariants**
- `0 <= K_target <= A`; merchants with zero admissible foreigns log a deterministic `K_target=0`.
- Attempt order is logged; event envelope budgets reconcile with `rng_audit_log`.
- Downstream states must use `K_realized = min(K_target, A)`; S4 never chooses specific countries.

**Downstream consumers**
- S6 and S7 read `K_target` from logs to cap membership; S9 replays the ZTP loop before certifying the bundle.

---

## S5 - Currency-country weight expansion (deterministic)
**Purpose & scope**
- Expand settlement currencies into per-country weights that downstream allocation can trust; no RNG, no per-merchant variation beyond deterministic policy.

**Preconditions & gates**
- Currency share surfaces, smoothing policy, and ISO coverage validated in S0; gating ensures JSON-Schema alignment.

**Inputs**
- Policy files referenced in `ccy_smoothing_params.yaml`, currency coverage metadata, and (optionally) merchant currency overrides.

**Outputs & identity**
- `ccy_country_weights_cache` (`data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`, schema `#/prep/ccy_country_weights_cache`).
- Optional helper surfaces: `merchant_currency` and `sparse_flag` (same partitioning).

**RNG posture**
- RNG-free; deterministic smoothing and quantisation (fixed decimal precision, typically 1e-6) enforce `sum(weights) = 1` after rounding.

**Key invariants**
- Every currency row sums to exactly 1.000000 in fixed dp; weights are non-negative and respect governance floors/ceilings.
- Coverage equals the governed currency universe; no on-the-fly additions.
- Path keys embed `parameter_hash`; row-set equality defines dataset equivalence.

**Downstream consumers**
- S6 restricts weights to each merchant candidate set before sampling; S7 uses the same surface to convert expectations into integer counts.

---

## S6 - Foreign-set selection (Gumbel-top-k)
**Purpose & scope**
- Select up to `K_realized` foreign countries using Gumbel-top-k over deterministic weights; produce RNG evidence and an optional convenience membership surface.

**Preconditions & gates**
- `s3_candidate_set` present, `K_target` logged by S4, `ccy_country_weights_cache` available, and eligibility flags from S3 enforced.
- S6 must verify S5 PASS receipts and S4 event coverage before running; publishes `s6_validation_receipt` that S7/S8 must check (`data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/`).

**Inputs**
- Candidate rows ordered by `candidate_rank`, weight vectors restricted to each merchant candidate set, and `K_target`.

**Outputs & identity**
- `rng_event_gumbel_key` (one record per candidate per merchant) plus supporting `rng_event_stream_jump` (when substreams advance) at `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.
- Optional dataset `s6_membership` (partitioned by `seed` and `parameter_hash`) listing selected foreign ISO codes (order-free).
- PASS receipt folder `s6_validation_receipt` gating downstream readers.

**RNG posture**
- Each candidate consumes one uniform mapped through the Gumbel key formula; events logged in S3 order so validators can recompute the selection.

**Key invariants**
- Selected set is a subset of `s3_candidate_set` and has size `min(K_target, A)`; membership never encodes order (S3 remains the sole order authority).
- Envelope budgets (blocks/draws) track exactly one Philox block per candidate; `after` counters increase monotonically per merchant substream.
- No write until the PASS receipt is produced; re-runs are idempotent via `(seed, parameter_hash, merchant_id)`.

**Downstream consumers**
- S7 needs the PASS receipt plus membership evidence to allocate integers; S8/S9 verify the receipt before reading membership; 1B can optionally read `s6_membership` but must still trust Gumbel logs for authority.

---

## S7 - Integer allocation across the legal country set
**Purpose & scope**
- Turn real-valued expectations (home plus selected foreigns) into integer counts that sum to `N`, respecting optional bounds and deterministic residual ranking; emits diagnostics but no new tables.

**Preconditions & gates**
- `s6_validation_receipt` PASS, `s3_candidate_set` and `s3_integerised_counts` (if enabled) available, `ccy_country_weights_cache` accessible, and `raw_nb_outlet_draw` from S2 provided.

**Inputs**
- Deterministic expectation vector derived from weights and membership, `N`, and optional bounds or per-country floors.

**Outputs & identity**
- Instrumentation streams: `rng_event_residual_rank` (records deterministic residual order) and, when the optional Dirichlet variant is enabled, `rng_event_dirichlet_gamma_vector`. Both live under `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.
- No new persistent dataset unless S3 delegates integerisation; otherwise counts are materialised via `s3_integerised_counts`.

**RNG posture**
- Default lane is RNG-free; optional Dirichlet gamma vectors (feature-flagged) consume Philox blocks logged in `rng_event_dirichlet_gamma_vector`. Residual-rank events are non-consuming (`before == after`).

**Key invariants**
- Per-merchant integer counts exactly sum to `N`; zero-mass candidates never receive outlets.
- Residual ranks follow a total order: fractional part descending, then ISO tie-breakers; validators recompute this order to confirm determinism.
- Bounds (if enabled) are enforced deterministically; infeasible configurations hard-fail the merchant.

**Downstream consumers**
- S8 reads final integer counts per `(merchant, country)`; S9 replays the allocation math (floors plus residual bumps) and cross-checks with `rng_event_residual_rank`.

---

## S8 - Materialise outlet stubs and sequences (egress)
**Purpose & scope**
- Emit immutable outlet stubs per `(merchant_id, legal_country_iso, site_order)` with deterministic within-country sequencing and guardrails for overflow; no geographic placement yet (1B handles that).

**Preconditions & gates**
- `s6_validation_receipt` PASS verified; `s3_candidate_set` for order joins; integer counts from S3/S7 available; `manifest_fingerprint` sealed in S0/S2.

**Inputs**
- Per-merchant counts, membership, and sequencing policy; `s3_site_sequence` (if emitted) or S7 evidence to reconstruct `site_order`.

**Outputs & identity**
- `outlet_catalogue` at `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` (schema `schemas.1A.yaml#/egress/outlet_catalogue`), writer sort `[merchant_id, legal_country_iso, site_order]`, PK `(merchant_id, legal_country_iso, site_order)`.
- Instrumentation events: `rng_event_sequence_finalize` (non-consuming, per `(merchant,country)` block) and `rng_event_site_sequence_overflow` (error path if site count exceeds 999999), under the standard logs path keyed by `seed/parameter_hash/run_id`.

**RNG posture**
- RNG-free; instrumentation events log deterministic completion and overflow guards only.

**Key invariants**
- For each `(merchant, country)` with `n_i` sites, rows exist with `site_order = 1..n_i` and `site_id = "{site_order:06d}"`; sums over countries equal the `raw_nb_outlet_draw`.
- No inter-country order is encoded; consumers must join `s3_candidate_set.candidate_rank`.
- Embedded lineage columns (`seed`, `manifest_fingerprint`) equal their partition tokens; dataset is immutable once `_passed.flag_1A` is published.

**Downstream consumers**
- Segment 1B (geo realism) and every later layer read `outlet_catalogue` only after verifying `_passed.flag_1A`; S9 cross-checks site counts and overflow telemetry before declaring PASS.

---

## S9 - Replay validation and PASS gate
**Purpose & scope**
- Re-derive S1-S8 outcomes, reconcile RNG budgets, and publish the validation bundle plus `_passed.flag_1A` that governs the "no PASS -> no read" rule for all 1A artefacts.

**Preconditions & gates**
- All prior states completed successfully, their datasets are discoverable through the dictionary, and RNG logs/events are available for the run.

**Inputs**
- Egress (`outlet_catalogue`), parameter-scoped authorities (`s3_candidate_set`, `ccy_country_weights_cache`, `s3_integerised_counts`, `s3_site_sequence`), RNG logs (`rng_audit_log`, `rng_trace_log`, every `rng_event_*` family), and optional convenience tables (for example `s6_membership`).

**Outputs & identity**
- `validation_bundle_1A/` under `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` containing `manifest_fingerprint_resolved.json`, `parameter_hash_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, plots, etc.
- `_passed.flag_1A` (same directory) containing `sha256_hex=<bundle_digest>` where the digest is computed over lex ordered bundle entries.

**RNG posture**
- RNG-free; validator replays draws by recomputing Philox counters and comparing to `rng_event_*` envelopes.

**Key invariants**
- All datasets conform to their schemas and partition laws; embedded lineage equals path tokens.
- RNG accounting closes: total draws and total blocks per event family exactly match the trace; `rng_audit_log` and `rng_trace_log` row counts align with event append totals.
- Cross-state joins hold: S1 hurdle coverage, S2 counts, S3 order, S4 `K_target`, S6 membership, S7 allocation, S8 egress counts, and instrumentation events all cohere.

**Downstream consumers**
- Any consumer (1B, Layer 2/3, Ingestion Gate, Event Bus) must verify `_passed.flag_1A` matches the recomputed bundle digest before reading 1A artefacts; release tooling ingests the bundle for manifest attestation.
