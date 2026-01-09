```
        LAYER 1 · SEGMENT 2B — STATE S3 (CORPORATE-DAY MODULATION: γ DRAWS)  [RNG-BOUNDED]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: a valid 2B.S0 gate exists for this manifest_fingerprint
      · binds: { seed, manifest_fingerprint } for this S3 run
      · provides: canonical created_utc = verified_at_utc (echoed into all S3 rows)
    - sealed_inputs_2B @ data/layer1/2B/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/…
      · inventory of all artefacts S0 sealed for this fingerprint
      · S3 MUST treat any cross-layer or policy artefact it reads as part of this inventory (subset-of-S0 rule);
        within-segment datasets (e.g. `s1_site_weights`) are not S0-sealed but must be read at the exact
        `[seed, fingerprint]` partition via the Dictionary.

[Schema+Dict]
    - schemas.2B.yaml                     (shape authority for s1_site_weights, s3_day_effects, day_effect_policy_v1)
    - schemas.2A.yaml                     (shape authority for site_timezones)
    - schemas.layer1.yaml                 (id64, rfc3339_micros, numeric/RNG/bundle primitives)
    - dataset_dictionary.layer1.2B.yaml   (ID → path/partitions/format for 2B: s1_site_weights, s3_day_effects, policies)
    - dataset_dictionary.layer1.2A.yaml   (ID → path/partitions/format for site_timezones)
    - artefact_registry_2B.yaml           (existence/licence/retention; non-authoritative for paths)

[Required inputs (S3 MAY read, and nothing else)]
    - s1_site_weights
        · producer: 2B.S1
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns (min): merchant_id, legal_country_iso, site_order, p_weight, … (plus any S1 provenance)
        · role: defines the merchant×site universe and base mass over sites (but S3 uses it only to discover merchants & tz-groups)
    - site_timezones
        · producer: 2A
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns (min): merchant_id, legal_country_iso, site_order, tzid
        · role: provides tzid per site; S3 uses tzid as tz_group_id
    - day_effect_policy_v1
        · producer: 2B.governance
        · partition: [] (token-less; contract file)
        · path: contracts/policy/2B/day_effect_policy_v1.json (resolved exactly as sealed in S0)
        · minima (must exist):
            · rng_engine          (Philox variant for S3)
            · rng_stream_id       (reserved stream name/id for S3)
            · draws_per_row = 1   (exactly one Philox draw per output row)
            · sigma_gamma > 0     (std dev of log_gamma)
            · day_range           = { start_day: YYYY-MM-DD, end_day: YYYY-MM-DD }, inclusive, start_day ≤ end_day
            · record_fields       ⊇ { gamma, log_gamma, sigma_gamma, rng_stream_id, rng_counter_lo, rng_counter_hi }

[Output surface owned by S3]
    - s3_day_effects
        · description: per-merchant × per-UTC-day × per-tz-group γ multipliers (log-normal; Philox provenance)
        · partition keys: [seed, fingerprint]
        · PK & writer sort: [merchant_id, utc_day, tz_group_id]
        · columns_strict: {merchant_id, utc_day, tz_group_id, gamma, log_gamma,
                           sigma_gamma, rng_stream_id, rng_counter_lo, rng_counter_hi, created_utc}

[Numeric & RNG posture]
    - S3 is **RNG-bounded, reproducible**:
        · counter-based Philox (rng_engine from policy) with a dedicated rng_stream_id
        · exactly **one** Philox draw per output row (draws_per_row = 1)
    - Numeric discipline:
        · IEEE-754 binary64, round-to-nearest-even
        · deterministic libm for erf⁻¹, exp, etc.; no FMA/FTZ/DAZ; serial reductions only
    - Catalogue discipline:
        · all inputs resolved by Dataset Dictionary IDs; no literal paths, no network I/O
        · cross-layer/policy inputs must appear in sealed_inputs_2B; within-segment datasets are read at [seed,fingerprint] only


----------------------------------------------------------------------
DAG — 2B.S3 (s1_site_weights × site_timezones × day_range → s3_day_effects)  [RNG-BOUNDED]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Verify S0 receipt & fix run identity
                    - Resolve s0_gate_receipt_2B for target manifest_fingerprint via Dictionary.
                    - Verify:
                        · schema-valid, component="2B.S0",
                        · fingerprint in receipt equals target partition token,
                        · seed in receipt matches the run’s seed.
                    - Resolve sealed_inputs_2B for this fingerprint and build an in-memory set of sealed asset IDs+paths+digests.
                    - Derive canonical created_utc ← s0_gate_receipt_2B.verified_at_utc.
                        · S3 SHALL echo this into every s3_day_effects row.
                    - Confirm posture:
                        · subset-of-S0 for cross-layer/policy inputs: S3 SHALL NOT resolve any cross-layer or policy
                          artefact that is not listed in `sealed_inputs_2B`.
                        · no network I/O; no re-hash of 1B bundles.

[S0 Gate & Identity],
[Schema+Dict],
s1_site_weights,
site_timezones,
day_effect_policy_v1
                ->  (S3.2) Resolve required inputs & extract policy minima
                    - Resolve, via Dictionary only:
                        · s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · site_timezones@seed={seed}/fingerprint={manifest_fingerprint}
                        · day_effect_policy_v1 (token-less; exact S0-sealed path + digest)
                    - Enforce subset-of-S0 for cross-layer/policy inputs:
                        · `site_timezones` and `day_effect_policy_v1` MUST appear in `sealed_inputs_2B` for this fingerprint;
                        · `s1_site_weights` is a within-segment dataset and MUST be resolved by ID at
                          `seed={seed}/fingerprint={manifest_fingerprint}` but is not S0-sealed.
                    - Validate shapes:
                        · s1_site_weights and site_timezones match their schema anchors,
                          with PK [merchant_id, legal_country_iso, site_order].
                    - Extract policy minima (Abort if missing/invalid):
                        · rng_engine (Philox variant),
                        · rng_stream_id (reserved for S3),
                        · sigma_gamma > 0,
                        · day_range = {start_day,…,end_day} with inclusive semantics and start_day ≤ end_day,
                        · draws_per_row == 1,
                        · required record_fields superset {gamma, log_gamma, sigma_gamma,
                                                          rng_stream_id, rng_counter_lo, rng_counter_hi}.
                    - Derive UTC-day grid:
                        · D = { start_day, start_day+1, …, end_day } in ascending ISO date.
                        · Let #days = |D|; this will be used later for coverage/draw-budget checks.

s1_site_weights,
site_timezones
                ->  (S3.3) Build deterministic tz-groups & coverage universe
                    - Join basis:
                        · join s1_site_weights keys (merchant_id, legal_country_iso, site_order)
                          to site_timezones on the same key set; take tzid as tz_group_id.
                    - Cardinality:
                        · join MUST be 1:1 for all keys present in s1_site_weights;
                          missing or multi-tzid keys are an error.
                    - For each merchant_id:
                        · collect distinct tz_group_id (tzid) from the joined rows,
                        · sort tz_group_id lexicographically; this is the merchant’s tz-group universe.
                    - Define merchant set:
                        · M = set of all merchant_id present in s1_site_weights.
                    - Coverage universe:
                        · U = { (merchant_id, utc_day, tz_group_id) |
                                merchant_id ∈ M,
                                tz_group_id in merchant’s tz-group set,
                                utc_day ∈ D }.
                    - S3 SHALL produce exactly |U| output rows; coverage is validated post-publish.

day_effect_policy_v1,
{M, tz-groups, D} from (S3.3)
                ->  (S3.4) Configure Philox stream & row→counter mapping
                    - RNG engine:
                        · instantiate rng_engine from policy (Philox variant) with:
                            - key / stream parameters derived deterministically from
                              {manifest_fingerprint, seed, rng_stream_id} via the policy’s key-derivation rule.
                    - Define writer / row order:
                        · total order over U: (merchant_id ↑, utc_day ↑, tz_group_id ↑).
                    - Base counter:
                        · obtain a 128-bit base_counter from the policy (deterministic function of
                          {manifest_fingerprint, seed, rng_stream_id}); constant for the run.
                    - Per-row counter mapping:
                        · enumerate rows in writer order; for row at rank i (0-based):
                              counter = base_counter + i     // 128-bit unsigned add; wrap-around forbidden
                        · record (rng_counter_hi, rng_counter_lo) as the high/low 64-bit words of counter.
                    - Draw budget law:
                        · draws_total = |U| (exactly one draw per row),
                        · counters over writer order MUST form a strictly increasing sequence (no reuse, no wrap).

rng_engine stream @ (S3.4),
row ordering over U
                ->  (S3.5) Single-uniform → standard normal draw (ICDF)
                    - For each row in writer order:
                        1. Obtain a 64-bit unsigned integer r from Philox(counter).
                        2. Map to an open-interval uniform u ∈ (0,1):
                               u = (r + 0.5) · 2^-64
                           guaranteeing 0 < u < 1 deterministically.
                        3. Compute standard normal Z via inverse CDF:
                               Z = √2 · erf⁻¹(2u − 1)
                           using the programme’s deterministic libm and numeric policy:
                               · binary64, RNE, no FMA/FTZ/DAZ, no data-dependent approximation mode.
                        4. Exactly one uniform (and therefore one Z) per row; no caching or Box–Muller allowed.

(S3.5 Z per row),
day_effect_policy_v1
                ->  (S3.6) Log-normal γ factor with E[γ] = 1
                    - Let σ ← sigma_gamma from policy (shared across all rows).
                    - Compute μ = −½ · σ² (binary64).
                    - For each row:
                        · log_gamma = μ + σ · Z
                        · gamma     = exp(log_gamma)
                    - Domain checks (Abort on failure):
                        · gamma > 0 for every row,
                        · log_gamma is finite (no NaN/±Inf).

(S3.3 U),
(S3.4 row ordering),
(S3.6 γ/log-γ per row),
day_effect_policy_v1,
created_utc from S0
                ->  (S3.7) Materialise s3_day_effects rows (writer order = PK)
                    - For each row of U in writer order (merchant_id, utc_day, tz_group_id):
                        · emit:
                            merchant_id,
                            utc_day,
                            tz_group_id,
                            gamma,
                            log_gamma,
                            sigma_gamma = σ (policy echo),
                            rng_stream_id = policy.rng_stream_id,
                            rng_counter_hi,
                            rng_counter_lo,
                            created_utc = S0.verified_at_utc.
                    - Writer sort:
                        · emit rows strictly in PK order [merchant_id, utc_day, tz_group_id].
                    - Coverage & cardinality in-memory:
                        · rows_to_write = |U| = (#UTC days in D) × Σ_merchants ( #tz_groups for that merchant ).
                        · no duplicate PKs; no missing combinations.

(S3.7 rows),
[Schema+Dict]
                ->  (S3.8) Publish s3_day_effects (write-once; atomic)
                    - Target partition (Dictionary-resolved):
                        · data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/
                    - Immutability:
                        · if target partition is empty → allowed to publish,
                        · if non-empty:
                            - allowed only if existing bytes are bit-identical to the new output (idempotent re-emit),
                            - otherwise Abort with IMMUTABLE_OVERWRITE.
                    - Write:
                        · write Parquet output to staging path on same filesystem,
                        · fsync, then atomic rename into final Dictionary path,
                        · no partially written files may become visible.

(published s3_day_effects),
[Schema+Dict],
[S0 Gate & Identity],
day_effect_policy_v1
                ->  (S3.9) Post-publish assertions & run-report
                    - Path↔embed equality:
                        · any embedded {seed, manifest_fingerprint} in the dataset must equal the partition tokens.
                    - Schema & shape:
                        · validate s3_day_effects against schemas.2B.yaml#/plan/s3_day_effects (columns_strict, PK, partitions).
                    - Sigma & engine echo:
                        · all rows share the same sigma_gamma; it equals policy.sigma_gamma.
                        · all rows share the same rng_stream_id; it equals policy.rng_stream_id.
                    - RNG accounting:
                        · rows_written = |U|,
                        · draws_total = rows_written,
                        · (rng_counter_hi,rng_counter_lo) strictly increase with row rank; no reuse, no wrap-around.
                    - Coverage:
                        · for every merchant_id and every tz_group_id in that merchant’s tz-group set,
                          and every utc_day ∈ D, exactly one row exists.
                    - Environment guards:
                        · confirm that only the three sealed inputs were accessed (s1_site_weights, site_timezones,
                          day_effect_policy_v1) and that network I/O remained disabled.
                    - Run-report:
                        · emit a single JSON run-report to STDOUT on success (and on abort where possible),
                          capturing:
                              · component="2B.S3", fingerprint, seed, created_utc,
                              · catalogue_resolution, policy id/version,
                              · metrics (merchants, tz_groups, days, rows_written, draws_total),
                              · validator outcomes (PASS/FAIL/WARN) and error codes if any.
                        · Any persisted copy of the run-report is implementation-defined and MUST NOT be treated
                          as an input asset by downstream contracts.

Downstream touchpoints
----------------------
- **2B.S4 — Group weights (RNG-free):**
    - MUST treat s3_day_effects as the sole authority for per-(merchant, utc_day, tz_group_id) γ factors.
    - Uses γ and sigma_gamma (with s1_site_weights + site_timezones) to build day-specific group mixes.
- **2B.S7 — Routing audit:**
    - Uses s3_day_effects to verify RNG accounting (draw counts, counters) and γ semantics against routing logs.
- **Layer-2 (5A/5B) & later routing:**
    - Indirectly depend on S3 via S4 group weights; they MUST NOT re-draw γ or bypass s3_day_effects.
- **Validation bundle (2B.S8):**
    - The fingerprint-scoped validation_bundle_2B MUST treat s3_day_effects as a key evidence surface;
      consumers of 2B routing plans honour the segment-wide “No PASS → No Read” gate on this fingerprint.
```
