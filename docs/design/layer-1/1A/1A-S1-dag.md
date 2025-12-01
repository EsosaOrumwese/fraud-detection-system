```
          LAYER 1 · SEGMENT 1A — STATE S1 (HURDLE: SINGLE vs MULTI)

Authoritative inputs at S1 entry (read-only)
-------------------------------------------
[X] hurdle_design_matrix
      path: data/layer1/1A/hurdle_design_matrix/parameter_hash={parameter_hash}/…
      scope: parameter-scoped (no seed/run_id)
      role: design vector x_m per merchant (from S0.5)

[B] hurdle_coefficients.yaml
      scope: governed model bundle
      role: logistic β for hurdle (single YAML, atomic load)

[K] lineage keys (from S0.2)
      { seed, parameter_hash, manifest_fingerprint, run_id }

[L] RNG + numeric law (from S0.3/S0.8)
      - Philox2x64-10 with open-interval U(0,1)
      - numeric_policy.json & math_profile_manifest.json
      - event envelope & budget rules for substream "hurdle_bernoulli"

[D] Contracts
      - schemas.layer1.yaml#/rng/events/hurdle_bernoulli
      - dataset_dictionary.layer1.1A.yaml (gating, partitions, retention)


Segment-level context (where S1 sits)
-------------------------------------

(S0) Universe, hashes, RNG & numeric law (no RNG draws)
    ├─> hurdle_design_matrix          @ [parameter_hash]
    ├─> crossborder_eligibility_flags @ [parameter_hash]      (used later)
    └─> {seed, parameter_hash, manifest_fingerprint, run_id} + RNG engine & numeric profile

[X] + [B] + [K] + [L]
        |
        v
(S1) Hurdle sampler  [RNG-bounded]
     - For each canonical merchant m:
         • read row x_m from hurdle_design_matrix
         • compute η_m = βᵀ x_m under numeric_policy_profile
         • compute π_m = σ(η_m)
         • draw u_m ∈ (0,1) from substream "hurdle_bernoulli"
         • decide is_multi_m ∈ {false,true}
         • emit exactly one hurdle event row for m
     -> rng_event.hurdle_bernoulli
            path: logs/rng/events/hurdle_bernoulli/
                  seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
            payload (per row, per merchant):
              envelope: ts_utc, run_id, seed, parameter_hash, manifest_fingerprint,
                        module="1A.hurdle_sampler",
                        substream_label="hurdle_bernoulli",
                        rng_counter_before/after (hi/lo), draws, blocks
              body: merchant_id, pi, u|null, is_multi, deterministic

Downstream touchpoints (who depends on S1)
------------------------------------------
- S2 (NB mixture → N≥2):
    • entry condition: exactly one S1 hurdle record for m
    • only merchants with is_multi = true may enter S2
    • S2 never re-derives π; it just uses the branch decision

- S3 (candidate universe & order):
    • uses is_multi to restrict to multi-site merchants for cross-border world building

- S4 / S6 / S7 / S8 (ZTP, Gumbel, allocation, outlet_catalogue):
    • all RNG-heavy families for outlet counts & cross-border structure are
      transitively gated by S1.is_multi = true
    • single-site merchants never generate NB / ZTP / Gumbel / residual_rank / sequence RNG events

- S9 (validation / replay):
    • replays S1 deterministically from hurdle_design_matrix + β
    • checks:
         – exactly 1 hurdle event per merchant
         – partition & envelope correctness
         – draw/block budgets vs rng_trace_log
         – consistency of recomputed is_multi vs logged is_multi


Legend
------
(Sx)           = state
[name]         = dataset or artefact
@[keys]        = partition keys
[RNG-bounded]  = state that consumes RNG; events logged under [seed, parameter_hash, run_id]
```

---

```
      LAYER 1 · SEGMENT 1A — S1.DAG-B
      INTERNAL FLOW: S1.1 → S1.2 → S1.3 → S1.4 → S1.7

Inputs at S1 entry (from S0)
----------------------------
- hurdle_design_matrix      (parameter-scoped; one row x_m per merchant)
- hurdle_coefficients.yaml  (β vector; atomic load)
- lineage keys: { seed, parameter_hash, manifest_fingerprint, run_id }
- RNG engine + substream law for "hurdle_bernoulli" (Philox, counters, budgets)
- numeric policy pinned in S0 (binary64, RNE, Neumaier dot, two-branch logistic)
- rng_audit_log row already present for {seed, parameter_hash, run_id}

Internal flow
-------------

  +---------------------------------------------------------+
  |  S1.1 — Inputs, Preconditions, Write Targets            |
  |---------------------------------------------------------|
  | - For each merchant m:                                  |
  |     • load x_m from hurdle_design_matrix                |
  |     • load β from hurdle_coefficients.yaml              |
  | - Check:                                                |
  |     • dim(x_m) == dim(β), encoder orders match S0.5     |
  |     • numeric policy from S0 is in force                |
  |     • rng_audit_log exists for this (seed, run_id, …)   |
  | - If any precondition fails → fail via S1.6/S0.9        |
  +---------------------------+-----------------------------+
                              |
                              v
  +---------------------------------------------------------+
  |  S1.2 — Linear Predictor & Logistic Map                 |
  |---------------------------------------------------------|
  | - Compute η_m = βᵀ x_m with fixed-order Neumaier sum    |
  | - Compute π_m via two-branch logistic                   |
  | - Guards: η, π finite and 0.0 ≤ π ≤ 1.0                 |
  | - Classify:                                             |
  |     • deterministic case: π ∈ {0.0, 1.0}                |
  |     • stochastic case:  0 < π < 1                       |
  | - Hand off (η_m, π_m) to S1.3                           |
  +---------------------------+-----------------------------+
                              |
                              v
  +---------------------------------------------------------+
  |  S1.3 — RNG Substream & Bernoulli Decision              |
  |---------------------------------------------------------|
  | - Derive Philox counter base from:                      |
  |     (seed, manifest_fingerprint,                        |
  |      substream_label="hurdle_bernoulli", merchant_id)   |
  | - If 0 < π < 1 (stochastic):                            |
  |     • consume exactly 1 uniform u ∈ (0,1)               |
  |     • draws = "1", blocks = 1                           |
  |     • is_multi = (u < π)                                |
  | - If π ∈ {0,1} (deterministic):                         |
  |     • no uniform draw; u := null                        |
  |     • draws = "0", blocks = 0                           |
  |     • is_multi = (π == 1.0)                             |
  | - Compute rng_counter_before/after and enforce:         |
  |     Δcounter == parse_u128(draws)                       |
  +---------------------------+-----------------------------+
                              |
                              v
  +---------------------------------------------------------+
  |  S1.4 — Event Assembly & Persisted Hurdle Record        |
  |---------------------------------------------------------|
  | - Build full RNG envelope fields:                       |
  |     ts_utc, run_id, seed, parameter_hash,               |
  |     manifest_fingerprint, module="1A.hurdle_sampler",   |
  |     substream_label="hurdle_bernoulli",                 |
  |     rng_counter_before_{hi,lo},                         |
  |     rng_counter_after_{hi,lo}, draws, blocks            |
  | - Build body payload:                                   |
  |     { merchant_id, pi, is_multi, deterministic, u }     |
  | - Append one JSONL row to:                              |
  |     logs/rng/events/hurdle_bernoulli/                   |
  |       seed={seed}/parameter_hash={parameter_hash}/      |
  |       run_id={run_id}/part-*.jsonl                      |
  | - Update rng_trace_log for (module="1A.hurdle_sampler", |
  |   substream_label="hurdle_bernoulli")                   |
  +---------------------------+-----------------------------+
                              |
                              v
  +---------------------------------------------------------+
  |  S1.7 — Outputs of S1 (State Boundary)                  |
  |---------------------------------------------------------|
  |  A) Authoritative persisted stream                      |
  |     - Exactly ONE hurdle_bernoulli event per merchant   |
  |       within {seed, parameter_hash, run_id}.            |
  |     - Path partitions {seed, parameter_hash, run_id}    |
  |       must equal embedded envelope fields.              |
  |     - Consistency laws:                                 |
  |         * π ∈ {0,1} ⇔ deterministic=true               |
  |           ⇔ draws="0" ⇔ u=null                        |
  |         * 0<π<1 ⇔ deterministic=false                  |
  |           ⇔ draws="1" ⇔ u∈(0,1)                       |
  |  B) In-memory handoff tuple to orchestrator             |
  |     - For each merchant, form                           |
  |         Ξ_m = (is_multi, N, K, 𝓒, C★)                  |
  |       where initially:                                  |
  |         * is_multi  from hurdle event                   |
  |         * N := 1, K := 0 on single-site path            |
  |         * 𝓒 := { home_country_iso(m) }                  |
  |         * C★ := post-counter u128 from the event        |
  |     - Branch routing:                                   |
  |         if is_multi == false → single-site path (later  |
  |             treated as N=1, K=0 in allocation)          |
  |         if is_multi == true  → NB path in S2            |
  +---------------------------------------------------------+

State-boundary invariants (what S2+ can rely on)
------------------------------------------------
- There is exactly one hurdle event per merchant per run.
- All hurdle events obey counter/draw/block budget rules.
- All downstream 1A RNG streams are gated indirectly by
  is_multi (via the dictionary gating contract), and S9 can
  replay S1 deterministically from x_m and β.
```
