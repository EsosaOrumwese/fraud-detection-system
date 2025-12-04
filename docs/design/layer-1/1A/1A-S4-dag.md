```
        LAYER 1 · SEGMENT 1A — STATE S4 (FOREIGN-COUNTRY TARGET K_target via ZTP)  [RNG · LOGS-ONLY]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[M] Merchant scope & upstream gates:
    - merchant_ids (ingress) @ schemas.ingress.layer1.yaml#/merchant_ids
        · merchant_id:u64, home_country_iso:ISO-2, mcc, channel
    - rng_event_hurdle_bernoulli @ [seed, parameter_hash, run_id]
        · payload: {merchant_id, is_multi, …}; exactly 1 per merchant
        · gate: S4 runs only for is_multi == true
    - rng_event_nb_final @ [seed, parameter_hash, run_id]
        · payload: {merchant_id, n_outlets=N_m≥2, mu, dispersion_k, nb_rejections}
        · non-consuming finaliser (before==after; blocks=0; draws="0")
    - S3 crossborder_eligibility_flags @ [parameter_hash]
        · payload: {merchant_id, is_eligible:bool, …}
        · gate: S4 runs only for is_eligible == true
    - S3 candidate_set @ [parameter_hash]
        · payload: {merchant_id, country_iso, candidate_rank, is_home, …}
        · used only to compute A := |foreign admissible set| = size(candidate_set \ {home})

[H] ZTP hyperparameters (governed; participate in parameter_hash):
    - crossborder_hyperparams @ [parameter_hash]
        · θ = (θ₀, θ₁, θ₂, …)       – link parameters for η
        · MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺ (default 64 if not overridden)
        · ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}

[F] Cross-border features (optional; deterministic):
    - crossborder_features @ [parameter_hash]
        · view keyed by merchant_id with X_m ∈ [0,1] (or similar features)
        · if X_m missing, S4 MUST use X_m := 0.0 (deterministic default, governed)

[N] Numeric / math policy (inherited from S0):
    - numeric_policy.json, math_profile_manifest.json
        · IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ
        · deterministic libm; fixed-order reductions; open-interval u ∈ (0,1)

[G] Run & RNG context (from S0):
    - {seed:u64, parameter_hash:hex64, manifest_fingerprint, run_id}
    - rng_audit_log @ [seed, parameter_hash, run_id] (one row for run)
    - rng_trace_log   @ [seed, parameter_hash, run_id]
    - RNG engine: counter-based Philox; envelope budgeting law already fixed in S0

[Dict] Dictionary & schemas:
    - dataset_dictionary.layer1.1A.yaml
        · ids & partitions for:
            - rng_event_poisson_component (allowed_producers: 1A.nb_poisson_component, 1A.ztp_sampler)
            - rng_event_ztp_rejection
            - rng_event_ztp_retry_exhausted
            - rng_event_ztp_final
    - schemas.layer1.yaml#/rng/events/*
        · row shape & payload/envelope for:
            - poisson_component (context:"ztp")
            - ztp_rejection
            - ztp_retry_exhausted
            - ztp_final

Optional observability surfaces:
    - s4.* counters/histograms (values only; not gates; updated alongside events).


----------------------------------------------------------------- DAG (S4.1–S4.8 · ZTP link + attempt loop + outcomes)

[M],[H],[F],
[N],[G],[Dict] ->  (S4.1) Scope, Branch Purity & Context Assembly
                      - Resolve all physical locations via the Data Dictionary (no literal paths).
                      - For each merchant_id:
                          * read ingress merchant row (home_country_iso, etc.)
                          * read exactly one rng_event_hurdle_bernoulli row
                          * read exactly one rng_event_nb_final row
                          * read exactly one crossborder_eligibility_flags row
                          * enforce path↔embed equality on {seed, parameter_hash, run_id} for all logs
                      - Branch purity (per merchant m):
                          * if is_multi == false         ⇒ BYPASS S4 (domestic-only); emit no S4 events for m
                          * if is_eligible == false      ⇒ BYPASS S4 (domestic-only); emit no S4 events for m
                          * missing hurdle or nb_final   ⇒ UPSTREAM_MISSING_S1 / UPSTREAM_MISSING_S2 (merchant-scoped abort; no S4 rows)
                      - Compute admissible foreign set size from S3:
                          * A_m = size({ rows in candidate_set where merchant_id=m and is_home==false })
                      - Load governed hyperparameters & features:
                          * θ from crossborder_hyperparams (closed shape; participates in parameter_hash)
                          * MAX_ZTP_ZERO_ATTEMPTS ∈ ℕ⁺  (cap)
                          * ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}
                          * X_m from crossborder_features (if missing ⇒ X_m := 0.0)
                      - Outputs (ephemeral context for S4.2–S4.5):
                          * per-merchant Ctx_S4(m) = {N_m, A_m, θ, X_m, MAX_ZTP_ZERO_ATTEMPTS, ztp_exhaustion_policy, …}
                      - No RNG used; no S4 rows written yet.

Ctx_S4,[N]          ->  (S4.2) Parameterise link η_m & λ_extra (Deterministic)
                          - For each merchant m that passed S4.1:
                              * compute η_m = θ₀ + θ₁·log N_m + θ₂·X_m + … in binary64:
                                  – fixed evaluation order; no data-dependent re-ordering
                                  – log evaluated under numeric policy; N_m≥2 from nb_final
                              * compute λ_extra,m = exp(η_m)
                          - Guards:
                              * if η_m or λ_extra,m is NaN/Inf or λ_extra,m ≤ 0:
                                  – record NUMERIC_INVALID for m
                                  – write **no** S4 events for m
                          - Outputs (ephemeral, authoritative for S4.3+):
                              * η_m, λ_extra,m (float64 > 0) per merchant
                          - Still no RNG consumption; still no events written.

Ctx_S4,λ_extra,
A_m,[G],[Dict]      ->  (S4.3) Universe-aware Short-circuit (A = 0)
                          - For each merchant with valid λ_extra,m:
                              * if A_m == 0 (no admissible foreign countries):
                                  – **do not attempt any Poisson draw**
                                  – set attempts = 0
                                  – derive regime from λ_extra,m (see S4.4; inversion vs ptrs threshold λ★=10)
                                  – emit exactly one non-consuming ztp_final row:
                                      · envelope:
                                          ts_utc, module="1A.ztp_sampler",
                                          substream_label="poisson_component",
                                          context="ztp",
                                          rng_counter_before == rng_counter_after,
                                          blocks = 0, draws = "0"
                                      · payload:
                                          merchant_id,
                                          K_target = 0,
                                          lambda_extra = λ_extra,m,
                                          attempts = 0,
                                          exhausted = false,
                                          optional reason = "no_admissible" (if schema includes)
                                  – append one rng_trace_log row for this event (saturating totals)
                                  – S4 writes **no poisson_component, no ztp_rejection, no ztp_retry_exhausted** for m
                                  – mark merchant as **resolved by short-circuit**
                              * else (A_m > 0) → pass to S4.4
                          - ZTP yields K≥1; here K_target=0 arises solely via A=0 short-circuit.
                          - No RNG used in A=0 path; only non-consuming finaliser.

Ctx_S4,λ_extra,
A_m>0,[G],[N],
[Dict]             ->  (S4.4) Regime Selection & Poisson Attempt Loop  [RNG]
                          - For each merchant with A_m>0 and valid λ_extra,m:
                              * select regime:
                                  – if λ_extra,m < 10.0 ⇒ regime = "inversion"
                                  – else                ⇒ regime = "ptrs"
                                (single float comparison in binary64; set once; constant per merchant)
                              * initialise:
                                  – attempt a := 1
                                  – zero_draws := 0
                              * Loop (while not resolved):
                                  1) Draw K_a ~ Poisson(λ_extra,m) using **fixed regime**:
                                      · sampler obeys open-interval u01, numeric policy
                                      · consumes ≥1 uniforms per attempt (regime-dependent)
                                      · emit one consuming poisson_component(context="ztp") event:
                                          envelope:
                                              ts_utc, module="1A.ztp_sampler",
                                              substream_label="poisson_component",
                                              context="ztp",
                                              before, after, blocks, draws
                                              (blocks = after−before; draws > 0)
                                          payload:
                                              { merchant_id, attempt=a, k=K_a, lambda_extra=λ_extra,m, regime }
                                      · append one rng_trace_log row for this event (saturating totals)
                                  2) Branch on K_a:
                                      – if K_a ≥ 1 ⇒ ACCEPT (hand off to S4.5, accepted branch)
                                      – if K_a == 0:
                                          · emit one non-consuming ztp_rejection event:
                                              envelope: before==after; blocks=0; draws="0"
                                              payload: { merchant_id, attempt=a, k:0, lambda_extra=λ_extra,m }
                                          · append one rng_trace_log row
                                          · zero_draws := zero_draws + 1
                                          · if zero_draws == MAX_ZTP_ZERO_ATTEMPTS ⇒ CAP HIT (hand off to S4.5, cap branch)
                                          · else: a := a+1; continue loop
                          - Attempt indices must be contiguous 1..a for each merchant that enters loop.

K_a path,
zero_draws,
λ_extra,regime,
policy,[G],[Dict] ->  (S4.5) Acceptance, Cap Policy & Finaliser Emission
                          - For merchants that ACCEPT (some attempt a with K_a ≥ 1 before cap):
                              * emit one non-consuming ztp_final event:
                                  envelope:
                                      before==after; blocks=0; draws="0"
                                  payload:
                                      merchant_id,
                                      K_target = K_a (≥1),
                                      lambda_extra = λ_extra,m,
                                      attempts = a,
                                      regime = regime,
                                      exhausted = false
                              * append one rng_trace_log row
                              * no ztp_retry_exhausted for accepted merchants
                          - For merchants that hit cap (zero_draws == MAX_ZTP_ZERO_ATTEMPTS with all K_a == 0):
                              * policy = ztp_exhaustion_policy from hyperparams:
                                  – if "abort":
                                       · emit one non-consuming ztp_retry_exhausted event:
                                           envelope: before==after; blocks=0; draws="0"
                                           payload:
                                               { merchant_id, attempts=MAX_ZTP_ZERO_ATTEMPTS,
                                                 lambda_extra=λ_extra,m, aborted:true }
                                       · append one rng_trace_log row
                                       · **no ztp_final for this merchant** (hard abort; merchant unresolved)
                                  – if "downgrade_domestic":
                                       · emit one non-consuming ztp_final event:
                                           envelope: before==after; blocks=0; draws="0"
                                           payload:
                                               { merchant_id,
                                                 K_target=0,
                                                 lambda_extra=λ_extra,m,
                                                 attempts=MAX_ZTP_ZERO_ATTEMPTS,
                                                 regime=regime,
                                                 exhausted=true }
                                       · append one rng_trace_log row
                              * no further S4 events for that merchant
                          - Invariants:
                              * per merchant that enters loop:
                                  – attempts field on ztp_final / ztp_retry_exhausted equals last attempt index a
                                  – all poisson_component attempts indexed 1..a with no gaps.

All S4 events,
[G],[Dict]        ->  (S4.6) RNG Discipline & Trace Totals  (Module "1A.ztp_sampler")
                          - Label / module mapping (frozen):
                              * poisson_component(context="ztp")   → module="1A.ztp_sampler", substream_label="poisson_component"
                              * ztp_rejection                      → same module/substream_label, context="ztp"
                              * ztp_retry_exhausted               → same
                              * ztp_final                         → same
                          - Substream law:
                              * base counter per merchant derived from (seed, manifest_fingerprint, "poisson_component", merchant_id)
                              * per event: blocks = after−before; draws = uniforms consumed (uint128-dec string)
                              * consuming events (poisson_component) have draws>0, blocks>0
                              * non-consuming events (ztp_rejection, ztp_retry_exhausted, ztp_final) have before==after, blocks=0, draws="0"
                          - Interval discipline:
                              * for each merchant & substream, envelopes form a monotone, non-overlapping sequence [[before,after))
                              * no counter reuse, no overlap, no regression
                          - rng_trace_log (for module="1A.ztp_sampler", substream_label="poisson_component"):
                              * after each event append, emit exactly one trace row with cumulative:
                                  – events_total, blocks_total, draws_total (saturating)
                              * later validators reconcile trace totals with event envelopes.

All S4 inputs
& outputs       ->  (S4.7) Failure Modes & Validator Hooks
                          - Merchant-scoped aborts (no S4 rows for m):
                              * UPSTREAM_MISSING_S1     – no hurdle event for merchant
                              * UPSTREAM_MISSING_S2     – no nb_final event for merchant
                              * UPSTREAM_MISSING_S3     – missing eligibility or candidate_set
                              * NUMERIC_INVALID         – non-finite or ≤0 λ_extra
                          - Branch purity failures (run-scoped):
                              * BRANCH_PURITY           – any S4 event exists for:
                                  – is_multi == false, or
                                  – is_eligible == false
                          - Structural RNG failures (run-scoped):
                              * PARTITION_MISMATCH      – {seed, parameter_hash, run_id} path vs envelope mismatch
                              * ATTEMPT_GAPS            – attempt indices not contiguous 1..a for a resolved merchant
                              * COUNTER_OVERLAP / REG   – substream counter intervals overlap or regress
                              * BUDGET_MISMATCH         – blocks != after−before, or non-consuming events with blocks>0/draws!="0"
                          - Universe / policy failures:
                              * A_ZERO_MISSHANDLED      – A=0 but any Poisson attempt occurred, or missing K_target=0 finaliser
                              * CAP_POLICY_INCONSISTENT – cap reached but events inconsistent with policy ("abort" vs "downgrade_domestic")
                          - Validator duties (S9 hook):
                              * re-evaluate λ_extra,m from S1/S2/S3 + hyperparams; check constancy per merchant
                              * validate regime choice from λ threshold (λ<10 vs ≥10)
                              * rebuild Poisson attempts from counters & envelopes; check attempt numbering & budgets
                              * ensure:
                                  – ≤1 ztp_final per resolved merchant
                                  – ztp_final.present ↔ merchant resolved via short-circuit, accept, or downgrade
                                  – no ztp_final under "abort" cap policy

All above        ->  (S4.8) Outputs (State Boundary) & Downstream Hand-off
                          - Persisted S4 RNG streams (logs-only; all @ [seed, parameter_hash, run_id]):
                              1) rng_event_poisson_component (context="ztp")
                                   · ≥0 rows per merchant (0 if A=0 short-circuit)
                                   · consuming; attempts 1..a; k≥0; λ_extra, regime constant per merchant
                              2) rng_event_ztp_rejection
                                   · 0..MAX rows per merchant; one per zero draw; non-consuming
                              3) rng_event_ztp_retry_exhausted
                                   · ≤1 row per merchant; only when cap hit AND policy="abort"; non-consuming
                              4) rng_event_ztp_final
                                   · exactly 1 row per merchant that is **resolved**:
                                       – A=0 short-circuit      → K_target=0, attempts=0, exhausted=false, optional reason="no_admissible"
                                       – ZTP accept (K≥1)       → K_target=K, attempts=a, exhausted=false
                                       – downgrade_domestic cap → K_target=0, attempts=MAX_ZTP_ZERO_ATTEMPTS, exhausted=true
                                   · absent only on hard abort (NUMERIC_INVALID, or cap+policy="abort")
                          - rng_trace_log rows:
                              * module="1A.ztp_sampler", substream_label="poisson_component"
                              * cumulative budget/coverage totals; updated after each S4 event
                          - No Parquet egress; S4 is a pure log producer.


State boundary (authoritative outputs of S4)
-------------------------------------------
- rng_event_poisson_component (context="ztp")   @ [seed, parameter_hash, run_id]
    * consuming Poisson attempts (k, attempt, lambda_extra, regime).
- rng_event_ztp_rejection                        @ [seed, parameter_hash, run_id]
    * non-consuming markers for zero draws.
- rng_event_ztp_retry_exhausted                  @ [seed, parameter_hash, run_id]
    * non-consuming markers when zero-draw cap hit and policy="abort".
- rng_event_ztp_final                            @ [seed, parameter_hash, run_id]
    * non-consuming finaliser; sole authority for K_target per merchant in S4’s universe.
- rng_trace_log rows for module="1A.ztp_sampler", substream_label="poisson_component".


Downstream touchpoints (from S4 outputs)
----------------------------------------
- S5 (Currency→country weight surfaces):
    * does **not** read S4; purely deterministic; no dependency on K_target.

- S6 (Foreign membership selection & realisation):
    * consumes ztp_final{K_target, lambda_extra, attempts, regime, exhausted?, reason?}:
        · computes K_realized = min(K_target, A_m) using its own admissible foreign set (from S3)
        · may log shortfall if K_realized < K_target
    * MUST NOT:
        · reinterpret λ_extra or regime,
        · treat λ_extra as a selection weight,
        · resample or adjust K_target.
    * treats K_target=0 as:
        · domestically-only case (A=0 or downgrade_domestic cap) — no foreign membership for that merchant.

- S7 / S8:
    * do not call S4 directly; they work on counts and sequences once S6 has realised membership and S7 has allocated.

- S9 (Validation bundle for 1A):
    * replays ZTP sampling from:
        · rng_event_poisson_component(context="ztp"),
          rng_event_ztp_rejection, rng_event_ztp_retry_exhausted, rng_event_ztp_final,
          rng_trace_log (S4 substreams),
          plus deterministic inputs (S1/S2/S3, crossborder_hyperparams, crossborder_features).
    * asserts all S4 invariants and failure modes before including S4 in validation_bundle_1A and its HashGate.
```