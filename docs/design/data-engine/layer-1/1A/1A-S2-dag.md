```
                LAYER 1 · SEGMENT 1A — STATE S2 (NB MIXTURE: TOTAL OUTLETS N_m ≥ 2)  [RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[M] Merchant universe & hurdle gate (from S0/S1):
    - merchant_ids (canonical merchants for this manifest_fingerprint)
    - rng_event_hurdle_bernoulli @ [seed, parameter_hash, run_id]
      · exactly one event per merchant
      · payload: { merchant_id, pi, is_multi, deterministic, u }
      · S2 only runs for is_multi == true

[D] NB design surface (deterministic, implied by S0.5):
    - frozen encoders & column dictionaries from S0:
      · one-hot MCC block Φ_mcc(mcc_m)
      · one-hot channel block Φ_ch(channel_sym_m)
      · intercept term
    - GDP term for dispersion only:
      · g_c > 0 (GDP-per-capita for home ISO c)
      · ln g_c appears only in the dispersion design
    - S2 constructs, in-memory, per-merchant design vectors:
      · x^(μ)_m  for NB mean = [1, Φ_mcc(mcc_m), Φ_ch(channel_sym_m)]
      · x^(φ)_m  for dispersion = [1, Φ_mcc(mcc_m), Φ_ch(channel_sym_m), ln g_c]
    - no new dataset; shape & encoders are governed by S0

[C] Model coefficients (governed artefacts):
    - hurdle_coefficients.yaml
      · key beta_mu → NB mean vector β_μ
    - nb_dispersion_coefficients.yaml
      · key beta_phi → dispersion vector β_φ
    - (β_μ, β_φ) are the *only* sources for (μ_m, φ_m) in S2.2

[N] Numeric / math policy artefacts:
    - numeric_policy_attest.json
    - math_profile_manifest.json
      · assert S0.8 policy: IEEE-754 binary64, RN-even, FMA-OFF, no FTZ/DAZ
      · deterministic libm profile, fixed-order reductions

[G] Run & RNG context (from S0):
    - { seed, parameter_hash, manifest_fingerprint, run_id }
    - rng_audit_log @ [seed, parameter_hash, run_id] (one row for the run)
    - rng_trace_log   @ [seed, parameter_hash, run_id] (per (module, substream_label))
    - RNG engine + envelope law from S0.3 (Philox 2x64-10, open-interval U(0,1))

[Dict] Registry / dictionary anchors:
    - dataset_dictionary.layer1.1A.yaml
      · gating for NB streams:
          * rng_event_gamma_component.gating:
              gated_by: rng_event_hurdle_bernoulli, predicate: is_multi == true
          * rng_event_poisson_component.gating:
              gated_by: rng_event_hurdle_bernoulli, predicate: is_multi == true
          * rng_event_nb_final.gating:
              gated_by: rng_event_hurdle_bernoulli, predicate: is_multi == true
      · partitions & paths for gamma_component, poisson_component, nb_final
    - schemas.layer1.yaml:
      · #/rng/events/gamma_component
      · #/rng/events/poisson_component
      · #/rng/events/nb_final
      (envelope + payload contracts for these streams)

Optional diagnostics (non-authoritative):
    - GDP priors, corridor configs for monitoring (used in S2.7/validation only).


----------------------------------------------------------------- DAG (S2.1–S2.9, NB mixture with RNG consumption)
[M],[D],[C],
[N],[G],[Dict] ->  (S2.1) Scope, Preconditions & NB Context Assembly
                      - Entry gate (per merchant m):
                          * require exactly one rng_event_hurdle_bernoulli row under {seed, parameter_hash, run_id}
                          * verify hurdle.envelope.manifest_fingerprint == current run's manifest_fingerprint
                          * if missing → ERR_S2_ENTRY_MISSING_HURDLE (skip S2 for m)
                          * if is_multi == false → ERR_S2_ENTRY_NOT_MULTI (branch purity; skip S2 for m)
                      - Load feature primitives:
                          * mcc_m, channel_sym_m from merchant_ids / S0 feature prep
                          * GDP g_c > 0 from reference surfaces fixed in S0 (home ISO)
                      - Build NB design vectors (in-memory, not persisted):
                          * x^(μ)_m = [1, Φ_mcc(mcc_m), Φ_ch(channel_sym_m)]
                          * x^(φ)_m = [1, Φ_mcc(mcc_m), Φ_ch(channel_sym_m), ln g_c]
                          * NB mean excludes GDP; dispersion includes ln g_c only (per S0.5 / S2.2)
                          * missing feature → ERR_S2_INPUTS_INCOMPLETE (skip S2 for m)
                      - Load NB coefficient vectors:
                          * β_μ from hurdle_coefficients.yaml (key=beta_mu)
                          * β_φ from nb_dispersion_coefficients.yaml (key=beta_phi)
                          * dim(β_μ) == len(x^(μ)_m); dim(β_φ) == len(x^(φ)_m) (must)
                      - Pin NB RNG streams & schemas:
                          * gamma_component (context="nb")
                          * poisson_component (context="nb")
                          * nb_final (non-consuming)
                      - Successful S2.1 yields NB design context for S2.2; no RNG used, no events written.

x^(μ)_m,x^(φ)_m,
β_μ,β_φ,[N]      ->  (S2.2) NB2 Parameters (μ_m, φ_m) — Deterministic
                      - Compute linear predictors in binary64, FMA-OFF:
                          * η^(μ)_m = β_μᵀ x^(μ)_m
                          * η^(φ)_m = β_φᵀ x^(φ)_m
                      - Exponentiate:
                          * μ_m = exp(η^(μ)_m)
                          * φ_m = exp(η^(φ)_m)
                      - Guards:
                          * η, μ, φ must be finite; μ_m > 0, φ_m > 0
                          * else → ERR_S2_NUMERIC_INVALID (merchant-scoped abort; no S2 events for m)
                      - Outputs (ephemeral NB2 context):
                          * (μ_m, φ_m) handed to S2.3–S2.4 (and echoed later in nb_final)
                      - No RNG consumption; nothing persisted here.

(μ_m,φ_m),
[M],[G],[N]     ->  (S2.3) Single NB Attempt — Gamma + Poisson Components  [RNG]
                      - Substream labels (NB-only):
                          * ℓ_γ = "gamma_nb" (for gamma_component, context="nb")
                          * ℓ_π = "poisson_nb" (for poisson_component, context="nb")
                      - Base counter per (m, ℓ) from S0.3.3 / S2.6:
                          * c_base = keyed_substream_counter(seed, manifest_fingerprint, ℓ, merchant_id)
                            (exact SHA-256/encoding recipe lives in S0.3.3/S2.6)
                      - For each attempt t (t = 0,1,2,…):
                          1) Sample Gamma G ~ Gamma(α=φ_m, 1) using the NB Gamma sampler:
                              · variable number of uniforms per attempt
                          2) Compute λ_t = (μ_m / φ_m) * G in binary64 and guard before any emission:
                              · if λ_t is non-finite or λ_t ≤ 0 → ERR_S2_NUMERIC_INVALID
                                (abort S2 for m; no S2 events for this merchant)
                          3) Emit gamma_component event:
                              - envelope: full RNG envelope (before/after counters, blocks, draws, labels)
                              - payload: { merchant_id, context="nb", index=0, alpha=φ_m, gamma_value=G }
                          4) Sample K_t ~ Poisson(λ_t) via λ-dependent sampler (inversion vs PTRS):
                              · variable uniforms per attempt
                          5) Emit poisson_component event:
                              - payload: { merchant_id, context="nb", lambda=λ_t, k=K_t, attempt: t+1 }
                          6) Envelope per event:
                              · blocks = u128(after) − u128(before)    (block-span)
                              · draws  = decimal uint128 of U(0,1) draws consumed by the sampler(s)
                      - S2.3 defines a *single attempt*; S2.4 controls how many attempts are performed.

γ/π components,
K_t sequence   ->  (S2.4) Rejection Rule & Attempt Loop (Enforce N_m ≥ 2)
                      - For each merchant m with valid (μ_m, φ_m):
                          * initialise t = 0, r_m = 0
                          * repeat:
                              - run one attempt via S2.3 → (G_t, λ_t, K_t)
                              - if K_t ≥ 2:
                                  · accept; set N_m = K_t
                                  · stop loop
                              - else:
                                  · rejection; r_m := r_m + 1
                                  · t := t + 1; continue
                      - S2.4 consumes **no** RNG itself (all draws come from S2.3 events).
                      - Evidence requirements (checked later):
                          * ≥1 gamma_component(context="nb") and ≥1 poisson_component(context="nb") for any merchant with nb_final
                          * per attempt, exactly 2 events in order: Gamma → Poisson
                      - Hand-off to S2.5:
                          * (N_m ≥ 2, r_m ≥ 0) plus (μ_m, φ_m) for final echo.

(N_m,r_m,
 μ_m,φ_m),
[G]           ->  (S2.5) Emit nb_final (N_m, r_m, μ_m, φ_m) — Non-consuming Event
                      - For each merchant that accepted in S2.4:
                          * derive envelope with current counters; **must be non-consuming**:
                              · rng_counter_before == rng_counter_after
                              · blocks = 0, draws = "0"
                          * emit exactly one nb_final row to:
                              · logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
                          - Payload (schema layer1#/rng/events/nb_final):
                              · { merchant_id,
                                  mu=μ_m, dispersion_k=φ_m,
                                  n_outlets=N_m, nb_rejections=r_m }
                              · domains: mu>0, dispersion_k>0, n_outlets≥2, nb_rejections≥0
                          - Idempotency:
                              · composite key (seed, parameter_hash, run_id, merchant_id) appears exactly once.

[G],[Dict],
rng streams   ->  (S2.6) RNG Substreams & Counter Discipline (Bit-Replay Contract)
                      - Label→module mapping (registry-closed):
                          * gamma_component(context="nb")  ← module "1A.nb_and_dirichlet_sampler", substream_label="gamma_nb"
                          * poisson_component(context="nb") ← module "1A.nb_poisson_component", substream_label="poisson_nb"
                          * nb_final                        ← module "1A.nb_sampler", substream_label="nb_final"
                      - Substream base counter law (per merchant & label):
                          * c_base = f(seed, manifest_fingerprint, label, merchant_id)
                          * b-th block: (c_hi, c_lo) = (c_base_hi, c_base_lo + b) with 64-bit carry into hi
                      - Envelope arithmetic (per event):
                          * blocks := u128(after) − u128(before)
                          * draws  := uniforms actually consumed (uint128-dec string)
                          * non-consuming finalisers (nb_final) have blocks=0, draws="0"
                      - Interval discipline (per (m, label)):
                          * intervals [before_e, after_e) are disjoint and monotone:
                              · no overlap
                              · next.before ≥ prev.after
                      - rng_trace_log:
                          * per (module, substream_label), maintain blocks_total and draws_total
                          * validators reconcile:
                              · blocks_total == total counter span
                              · draws_total == Σ draws_event implied by samplers

(μ_m,φ_m,
 N_m,r_m,
 attempt log) ->  (S2.7) Monitoring Corridors & Run-Level Gates (No RNG)
                      - Compute run-level corridor metrics over all merchants with nb_final:
                          * overall rejection rate:
                              · total_rejections / total_attempts
                          * high quantile of r_m (e.g. 99th percentile)
                          * one-sided CUSUM for excess rejections vs model-expected α_m
                      - Model-expected α_m derived from NB2 parameters (μ_m, φ_m) via closed forms.
                      - If any corridor exceeds configured threshold:
                          * treat as run-scoped failure (F_S2_CORRIDOR)
                          * validators MUST mark run invalid; no `_passed.flag` for 1A

All above,
[G],[Dict]    ->  (S2.8) Failure Modes & Error Classes
                      - Merchant-scoped aborts (no NB events for m):
                          * ERR_S2_ENTRY_MISSING_HURDLE  – no S1 hurdle record for m
                          * ERR_S2_ENTRY_NOT_MULTI       – S1 hurdle present but is_multi == false
                          * ERR_S2_INPUTS_INCOMPLETE     – missing feature(s) or coeffs
                          * ERR_S2_NUMERIC_INVALID       – μ or φ non-finite/≤0
                      - Run-scoped structural failures (abort run):
                          * schema violations in gamma_component / poisson_component / nb_final
                          * gating violations (S2 events present for is_multi == false merchants)
                          * counter overlap/regression within any NB substream
                          * coverage breaches (nb_final exists but components missing)
                          * corridor breaches from S2.7
                      - Validators map these into S0.9’s global failure contract.

rng_event_gamma_component,
rng_event_poisson_component,
rng_event_nb_final,
rng_trace_log,[G] ->  (S2.9) Outputs (State Boundary) & Hand-off to S3
                      - Persisted authoritative NB RNG streams (per dataset_dictionary):
                          1) gamma_component (context="nb")
                             · path: logs/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
                             · schema: layer1#/rng/events/gamma_component
                             · cardinality: ≥1 per multi-site merchant (one per attempt)
                          2) poisson_component (context="nb")
                             · path: logs/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
                             · schema: layer1#/rng/events/poisson_component
                             · cardinality: ≥1 per attempt (same attempts as Gamma)
                          3) nb_final
                             · path: logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
                             · schema: layer1#/rng/events/nb_final
                             · cardinality: exactly 1 per merchant with S2 success
                      - In-memory export per merchant with nb_final:
                          * N_m ∈ {2,3,…}    (authoritative domestic outlet count, must NOT be resampled)
                          * r_m ∈ ℕ₀        (number of rejections; diagnostics only)
                          * (μ_m, φ_m)      (NB2 parameters; echoed in nb_final)
                      - Boundary invariants:
                          * if nb_final exists for m ⇒ ≥1 Gamma and ≥1 Poisson component rows for m under same keys
                          * all NB event paths/embeds respect {seed, parameter_hash, run_id, manifest_fingerprint}
                          * nb_final is non-consuming (before==after, blocks=0, draws="0")


State boundary (authoritative outputs of S2)
-------------------------------------------
- rng_event_gamma_component (context="nb")   @ [seed, parameter_hash, run_id]
    * one row per NB attempt (≥1 per multi-site merchant).
- rng_event_poisson_component (context="nb") @ [seed, parameter_hash, run_id]
    * one row per NB attempt (aligned 1:1 with gamma_component).
- rng_event_nb_final                          @ [seed, parameter_hash, run_id]
    * exactly one row per merchant that successfully left S2.
- rng_trace_log rows for:
    * ("1A.nb_and_dirichlet_sampler","gamma_nb")
    * ("1A.nb_poisson_component","poisson_nb")
    * ("1A.nb_sampler","nb_final")
- No new Parquet tables are introduced by S2; N_m and r_m are exported in-memory to S3 and validation.

Downstream touchpoints (from S2 outputs)
----------------------------------------
- S3 (Candidate universe & cross-border eligibility):
    * consumes N_m (domestic outlet count) for each multi-site merchant that has nb_final.
    * runs only for merchants with:
        - rng_event_hurdle_bernoulli.is_multi == true, and
        - an nb_final row (S2 success).
- S4 (ZTP foreign K_target, later):
    * typically uses N_m (often via log N_m) as part of λ_extra features.
    * reuses the poisson_component stream id with context="ztp" for its own Poisson draws (dictionary-separated from context="nb").
- S9 (Validation bundle for 1A):
    * replays NB sampling using:
        - rng_event_gamma_component, rng_event_poisson_component, rng_event_nb_final
        - rng_trace_log (NB substreams)
        - S2.1/2.2 deterministic NB context
    * checks all S2.6/S2.7/S2.8 invariants before allowing `_passed.flag_1A` to be written.
```
