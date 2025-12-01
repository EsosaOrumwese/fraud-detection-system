```
                LAYER 1 · SEGMENT 1A — STATE S0 (FOUNDATION / NO RNG DRAWS)

Authoritative inputs (read-only)
--------------------------------
[M] merchant_ids (ingress):
    - merchant_id, mcc, channel, home_country_iso

[R] Reference artefacts:
    - iso3166_canonical_2024
    - world_bank_gdp_per_capita_20250415
    - gdp_bucket_map_2024 (Jenks K=5 buckets, precomputed)

[C] Model coeffs:
    - hurdle_coefficients.yaml
    - nb_dispersion_coefficients.yaml

[P] Policy / hyperparams:
    - crossborder_hyperparams.yaml
    - policy.s3.rule_ladder.yaml  (eligibility rules)
    - (later) ccy_smoothing_params.yaml, etc. (for downstream states, but included in S0 hashing)

[N] Numeric / math policy artefacts:
    - numeric_policy.json
    - math_profile_manifest.json
    - residual_quantisation.yaml        (S7 / legacy integerisation)

[G] Run context:
    - git_commit (32 raw bytes)
    - run_seed (u64, input knob)
    - registry + dataset_dictionary (paths, schema_refs, produced_by, partitions, etc.)

----------------------------------------------------------------- DAG (S0.1–S0.10, no RNG consumption)
[M],[R],[G]  ->  (S0.1) Universe, Symbols, Authority
                   - Validate merchant_ids against schemas.ingress.layer1.yaml#/merchant_ids
                   - Load ISO set, GDP vintage, GDP bucket map
                   - Assert JSON-Schema is sole authority (no Avro in dictionary/registry)
                   - Freeze run context U = (M, I, G, B, SchemaAuthority)
                   - Global law: S3.candidate_set.candidate_rank is the only cross-country order authority

(C),(P),(N),
[R],[G], U   ->  (S0.2) Hashes & Identifiers
                   - Compute parameter_hash (tuple-hash over governed param artefacts)
                   - Compute manifest_fingerprint (tuple-hash over all opened artefacts + git + parameter_hash)
                   - Derive run_id (hex32) from (fingerprint_bytes, seed_u64, start_time_ns)
                   - These four keys are fixed for the run:
                        * parameter_hash (partitions parameter-scoped artefacts)
                        * manifest_fingerprint (partitions egress/validation)
                        * seed (u64 modelling seed)
                        * run_id (logs only)

(seed, parameter_hash,
 manifest_fingerprint,
 N, G)      ->  (S0.3) RNG Engine, Substreams, Samplers & Draw Accounting
                   - Pin PRNG: Philox 2x64-10, low-lane policy, open-interval U(0,1)
                   - Define event envelope (rng_counter_before/after, blocks, draws, module, substream_label, ts_utc)
                   - Define per-family budgets (uniform1, normal, gamma_component, poisson_component, gumbel_key, etc.)
                   - Emit ONE rng_audit_log row for this run (no RNG draws)
                   - Define rng_trace_log contract (one row per (module, substream_label); filled by RNG-consuming states)

U,[R]       ->  (S0.4) Deterministic GDP Bucket Assignment
                   - For each merchant m:
                       * look up G(c) from GDP table using home_country_iso
                       * look up B(c) in gdp_bucket_map_2024
                   - Provide g_c and bucket b_m into the feature stack for S0.5
                   - (Optional) materialise a tiny GDP-feature table under parameter_hash; otherwise ephemeral into S0.5

U,[R],[C],
g_c, b_m    ->  (S0.5) Design Matrices (Hurdle & NB)
                   - Build column-frozen design vectors x_m for:
                       * hurdle logistic (S1)
                       * NB mean/dispersion links (S2)
                   - Validate lengths vs bundle dictionaries (mcc levels, channel, GDP bucket)
                   - Persist:
                       * hurdle_design_matrix @ parameter_hash
                   - NB design is defined and used, but remains an internal view, not a separate dataset

U,[P]       ->  (S0.6) Cross-border Eligibility (deterministic gate)
                   - Apply rule ladder over per-merchant features (mcc, channel_sym, GDP bucket, etc.)
                   - Decide is_eligible, decision_source, reason_code, rule_set for each merchant
                   - Persist:
                       * crossborder_eligibility_flags @ parameter_hash
                   - This is the only deterministic gate that decides who may attempt cross-border in S4–S6

hurdle_design_matrix,
[C], parameter_hash
             ->  (S0.7) Hurdle π Diagnostic Cache (optional)
                   - Re-evaluate η_m and π_m = σ(η_m) for every merchant using numeric profile
                   - Persist diagnostics only:
                       * hurdle_pi_probs @ parameter_hash
                   - Never used by samplers; purely for monitoring/validation

[N], G      ->  (S0.8) Numeric Policy & Determinism Controls
                   - Pin numeric environment:
                       * binary64, round-to-nearest-ties-even
                       * FMA off, no FTZ/DAZ, no fast-math
                       * deterministic libm profile (exp/log/sin/cos/atan2/pow/...)
                       * deterministic reduction/sorting rules and ULP-based tolerances
                   - Run self-tests; on failure, raise F2/F8 and abort
                   - Emit:
                       * numeric_policy_attest.json (summarises env, flags, libm profile)
                     (Included in validation bundle and hashed into manifest_fingerprint input set)

S0.*        ->  (S0.9) Failure Modes & Abort Semantics
                   - Define F1–F10 failure classes and codes (schema-level)
                   - On first fatal failure anywhere in 1A:
                       * write validation/fingerprint=.../failure.json
                       * write validation/fingerprint=.../_FAILED.SENTINEL.json
                       * abort entire 1A run (no further states execute)
                   - Guarantees bit-identical failure.json for identical inputs/env

(parameter_hash,
 manifest_fingerprint,
 seed, run_id,
 S0.2–S0.8 contracts)
             ->  (S0.10) Outputs, Partitions & Validation Bundle Contract
                   - Re-state lineage roles:
                       * parameter_hash -> parameter-scoped artefacts
                       * manifest_fingerprint -> egress & validation artefacts
                       * seed, run_id -> RNG/log partitions only
                   - Embed-key rule: any row with parameter_hash/manifest_fingerprint columns
                     must embed values equal to the directory keys
                   - Specify format and semantics of:
                       * validation_bundle_1A/ (to be written in S9)
                       * _passed.flag (sha256_hex over bundle contents; flag excluded)
                   - Downstream rule: any consumer of outlet_catalogue
                     MUST verify _passed.flag before reading (no PASS -> no read)

Downstream touchpoints (from S0 outputs)
----------------------------------------
- S1 uses:
    * hurdle_design_matrix
    * RNG engine + budgets from S0.3
    * numeric policy from S0.8
- S2 uses:
    * NB design surface implied by S0.5 (and GDP features from S0.4)
    * same RNG/numeric contracts
- S4 uses:
    * crossborder_eligibility_flags (gate)
    * GDP/GDP-bucket features as part of λ_extra features
- All 1A states use:
    * lineage keys (parameter_hash, manifest_fingerprint, seed, run_id)
    * failure contract (S0.9)
    * partitioning & validation-bundle semantics (S0.10)
```

----

```
                 LAYER 1 · SEGMENT 1A — S0 ONLY (no RNG draws)

External inputs (read-only)
---------------------------
[M] merchant_ids (ingress)
[R] iso3166_canonical_2024, gdp_per_capita_2025-04-15, gdp_bucket_map_2024
[C] hurdle_coefficients.yaml, nb_dispersion_coefficients.yaml
[P] crossborder_hyperparams.yaml, policy.s3.rule_ladder.yaml, etc.
[N] numeric_policy.json, math_profile_manifest.json, residual_quantisation.yaml
[S] JSON-Schema files (schemas.ingress.layer1.yaml, schemas.1A.yaml, schemas.layer1.yaml, ...)

Flow inside S0
--------------

[M] + [R] + [S]
      |
      v
 (S0.1) Universe, Symbols, Authority
        - freeze merchant universe, ISO set, GDP/bucket tables
        - assert JSON-Schema authority
        - state global “S3.candidate_rank is sole cross-country order” law
        |
        v
 [C] + [P] + [N] + (opened artefacts from S0.1)
        |
        v
 (S0.2) Hashes & Identifiers
        - compute parameter_hash
        - compute manifest_fingerprint
        - derive run_id from (fingerprint, seed, time)
        |
        +-----------------------------+
        |                             |
        v                             v
 (S0.3) RNG Engine, Substreams        (S0.8) Numeric Policy & Determinism
        - pin Philox engine                    - pin FP env, math profile
        - define event envelope                - run numeric self-tests
        - define family budgets                - emit numeric_policy_attest
        - emit rng_audit_log row

from S0.1+S0.2:
        |
        v
 (S0.4) GDP Bucket Assignment
        - attach g_c, b_m to each merchant
        |
        v
 (S0.5) Design Matrices (Hurdle & NB)
        - build hurdle_design_matrix (persisted)
        - define NB design (internal view only)

from S0.1 (merchant features) + [P]:
        |
        v
 (S0.6) Cross-border Eligibility
        - apply rule ladder
        - emit crossborder_eligibility_flags (@ parameter_hash)

from S0.5 (design) + [C]:
        |
        v
 (S0.7) Hurdle π Diagnostic Cache (optional)
        - recompute η_m, π_m
        - emit hurdle_pi_probs (@ parameter_hash)

cross-cutting over all S0.*
        |
        v
 (S0.9) Failure Modes & Abort Semantics
        - define F1–F10 classes
        - first fatal ⇒ write failure.json + _FAILED.SENTINEL, abort 1A

final recap / contracts
        |
        v
 (S0.10) Outputs, Partitions & Validation Bundle Contract
        - fix roles of parameter_hash, manifest_fingerprint, seed, run_id
        - embed-key rule (path vs embedded cols)
        - define validation_bundle_1A layout
        - define _passed.flag = SHA256(bundle bytes)
        - downstream rule: outlet_catalogue consumers must “PASS-gate” on this
```
