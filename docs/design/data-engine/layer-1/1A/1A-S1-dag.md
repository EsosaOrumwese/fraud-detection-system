```
                LAYER 1 · SEGMENT 1A — STATE S1 (HURDLE: SINGLE vs MULTI-SITE)  [RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[M] Merchant universe (from S0):
    - merchant_ids (canonical merchants for this manifest_fingerprint)
    - home_country_iso, mcc, channel  (already validated in S0.1)

[D] Design surface (parameter-scoped, deterministic):
    - hurdle_design_matrix @ [parameter_hash]
      - one row per merchant m: frozen feature vector x_m
      - column order & encoders fixed by S0.5 (intercept, MCC, channel, GDP_bucket)

[C] Model coefficients (governed artefact):
    - hurdle_coefficients.yaml
      - single logistic hurdle vector β, shape == dim(x_m)
      - registry-backed; included in parameter_hash input set

[N] Numeric / math policy artefacts:
    - numeric_policy.json
    - math_profile_manifest.json
      - enforce S0.8: IEEE-754 binary64, RN-even, FMA-off, no FTZ/DAZ, fixed-order reductions

[G] Run & RNG context (from S0):
    - {parameter_hash, manifest_fingerprint, seed, run_id}
    - rng_audit_log @ [seed, parameter_hash, run_id] (single row; established in S0.3)
    - rng_trace_log   @ [seed, parameter_hash, run_id] (per (module, substream_label))
    - RNG engine + envelope law from S0.3 (Philox 2x64-10, open-interval U(0,1))

[Dict] Registry / dictionary anchors:
    - dataset_dictionary.layer1.1A.yaml
      - schema_ref + partition law for rng_event_hurdle_bernoulli
      - gating for all downstream RNG families:
          * gated_by: rng_event_hurdle_bernoulli
          * predicate: is_multi == true
          * some also_require: crossborder_eligibility_flags.is_eligible == true
    - schemas.layer1.yaml#/rng/events/hurdle_bernoulli (event envelope + payload authority)

Optional diagnostics (non-authoritative):
    - hurdle_pi_probs @ [parameter_hash] (if present; S0-built π cache)
      - S1 MAY compare for sanity; **events remain sole authority**.


----------------------------------------------------------------- DAG (S1.1–S1.7, single Bernoulli family)
[M],[D],[C],
[N],[G]      ->  (S1.1) Inputs, Preconditions & Write Targets
                   - Assert design/coeff alignment:
                       * dim(β) == dim(x_m) for every merchant (block dictionaries match S0.5)
                   - Assert numeric environment attested by S0.8 (binary64, RN-even, no FMA/FTZ/DAZ).
                   - Assert run context is fixed:
                       * rng_audit_log row exists for {seed, parameter_hash, run_id}
                       * rng_trace_log contract available for layer-wide RNG tracing
                   - Pin write targets (no data written yet):
                       * rng_event_hurdle_bernoulli @ [seed, parameter_hash, run_id]
                       * rng_trace_log (rows for module="1A.hurdle_sampler", substream_label="hurdle_bernoulli")
                   - Any precondition failure → escalate to S0.9 failure law (no hurdle events emitted).

[D],[C],[N]  ->  (S1.2) Logistic Map η → π (Deterministic)
                   - For each merchant m:
                       * compute η_m = βᵀ x_m using fixed-order Neumaier reduction (binary64)
                       * compute π_m = logistic(η_m) via S0.8 two-branch logistic (no ad-hoc clamps)
                   - Classify branches:
                       * deterministic if π_m ∈ {0.0, 1.0} (exact binary64 endpoints)
                       * stochastic if 0 < π_m < 1
                   - Guard against NaN/Inf in η or π → hard numeric failure under S0.9.
                   - Outputs (ephemeral, not persisted): (η_m, π_m) per merchant handed to S1.3/S1.4.

π_m,[M],[G],
[N]          ->  (S1.3) RNG Substream & Bernoulli Decision
                   - Derive base counter for each merchant:
                       * label ℓ = "hurdle_bernoulli"
                       * keyed-substream mapping from S0.3 using (seed, manifest_fingerprint, ℓ, merchant_id)
                   - Deterministic branch (π_m ∈ {0.0,1.0}):
                       * draws = "0", blocks = 0
                       * after_counter = before_counter  (no Philox call)
                       * is_multi = (π_m == 1.0)
                   - Stochastic branch (0 < π_m < 1):
                       * consume exactly one uniform u ∈ (0,1) via open-interval mapping
                       * draws = "1", blocks = 1
                       * after_counter = before_counter + 1
                       * is_multi = (u < π_m)
                   - Enforce per-event budget identity (hurdle family only):
                       * u128(after) − u128(before) == parse_u128(draws)
                       * for hurdle, draws ∈ {"0","1"} and blocks ∈ {0,1} and blocks == draws.

[M],π_m,u,
is_multi,[G] ->  (S1.4) Event Emission & Trace Updates
                   - Emit exactly one flat JSON hurdle event per merchant to rng_event_hurdle_bernoulli:
                       * Envelope (from schemas.layer1.yaml#/rng/events/hurdle_bernoulli):
                           - ts_utc (RFC-3339, Z, 6 fractional digits)
                           - run_id, seed, parameter_hash, manifest_fingerprint
                           - module="1A.hurdle_sampler"
                           - substream_label="hurdle_bernoulli"
                           - rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}
                           - draws (u128 decimal string), blocks (uint64)
                       * Payload:
                           - merchant_id (id64 integer)
                           - pi (binary64 copy of π_m)
                           - is_multi (boolean)
                           - deterministic (boolean; true iff π_m ∈ {0.0,1.0})
                           - u:
                               · null  iff π_m ∈ {0.0,1.0}
                               · ∈ (0,1) iff 0 < π_m < 1
                   - Append / update rng_trace_log row for (module="1A.hurdle_sampler",
                     substream_label="hurdle_bernoulli"):
                       * events_total  += 1
                       * draws_total   += parse_u128(draws)
                       * blocks_total  += blocks
                   - Enforce partition/embedding equality:
                       * path keys {seed, parameter_hash, run_id} == embedded columns where present.

[M],π_m,u,
is_multi,[Dict]
,[G]          ->  (S1.5) Downstream RNG Gating Surface (via Dictionary)
                   - Treat rng_event_hurdle_bernoulli as the **gate** for all other 1A RNG streams:
                       * dataset_dictionary.gating.gated_by == "rng_event_hurdle_bernoulli"
                       * predicate: is_multi == true
                   - Consequences:
                       * For any merchant with is_multi == false:
                           - there MUST be no rng_event_gamma_component / poisson_component / nb_final /
                             ztp_* / dirichlet_gamma_vector / normal_box_muller /
                             sequence_finalize / residual_rank / site_sequence_overflow / stream_jump events.
                           - Any such event is a structural failure caught by validation.
                       * Some streams (e.g. ZTP / cross-border families) also require:
                           - crossborder_eligibility_flags.is_eligible == true
                   - S1 itself does **not** enumerate downstream stream names; the dictionary remains authority.

[M],[D],[C],
[N],[G]      ->  (S1.6) Determinism & Invariants (Hurdle Family)
                   - Bit-replay guarantee:
                       * Fix (x_m, β, seed, parameter_hash, manifest_fingerprint) ⇒
                         η_m, π_m, u (if drawn), is_multi are reproducible bit-for-bit.
                   - Budget & branch invariants:
                       * draws = "1"   ⇔   0 < π_m < 1
                       * draws = "0"   ⇔   π_m ∈ {0.0,1.0}
                       * after−before == draws (as u128) for every event
                   - Cardinality:
                       * exactly one hurdle event per merchant per {seed, parameter_hash, run_id}
                   - Payload invariants:
                       * deterministic flag matches π_m endpoint vs interior
                       * u null vs numeric matches deterministic vs stochastic classification.

rng_event_hurdle_bernoulli,
rng_trace_log,[G]
[S0 law]     ->  (S1.7) Failure Modes & Validator Hooks
                   - Local failure classes (mapped into S0.9):
                       * design/coeff mismatch, numeric overflow/NaN, envelope violations,
                         budget mismatches, duplicate/missing events, partition-embed mismatches.
                   - Validator responsibilities (S1.V):
                       * re-compute (η_m, π_m) and replay Bernoulli where draws="1"
                       * check budget identity per event and cumulative trace tallies
                       * enforce one-and-only-one hurdle event per merchant
                       * enforce dictionary-driven gating constraints over all 1A RNG streams.
                   - Any hard failure ⇒ run invalid under S0.9; downstream states must treat 1A as failed.

State boundary (authoritative outputs of S1)
-------------------------------------------
- rng_event_hurdle_bernoulli     @ [seed, parameter_hash, run_id]
    * one row per merchant; sole authority for is_multi decisions and π payload.
- rng_trace_log (hurdle substream rows) @ [seed, parameter_hash, run_id]
    * cumulative trace for (module="1A.hurdle_sampler", substream_label="hurdle_bernoulli").
- No new Parquet surfaces are owned by S1; any π caches (e.g. hurdle_pi_probs) remain optional diagnostics.

Downstream touchpoints (from S1 outputs)
----------------------------------------
- S2 (NB mixture → N):
    * gates entry on rng_event_hurdle_bernoulli.is_multi == true (branch purity: singles bypass S2 entirely).
    * relies on dictionary gating so that all NB-related RNG streams only appear for is_multi == true.
- S3 (Candidate universe & order):
    * runs its rule ladder only for multi-site merchants (is_multi == true) with accepted S2 N.
- S4 (ZTP foreign K_target):
    * runs only for merchants with is_multi == true and crossborder_eligibility_flags.is_eligible == true.
    * all ZTP-related rng_event_* streams are dictionary-gated by S1 hurdle events.
- S6 (Foreign membership selection):
    * indirectly depends on S1 via S4's ztp_final and S3's candidate_set; all are defined only for multi-site merchants.
- S9 (Validation bundle for 1A):
    * replays S1 logistic + Bernoulli decisions from rng_event_hurdle_bernoulli and rng_trace_log,
      and verifies all gating/branch invariants before writing validation_bundle_1A.
```