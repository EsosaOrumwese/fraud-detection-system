```
        LAYER 1 – SEGMENT 1A - STATE S3
        CANDIDATE UNIVERSE & INTER-COUNTRY ORDER (DETERMINISTIC)

Authoritative inputs at S3 entry (read-only)
--------------------------------------------
[M] Merchant scope (ingress row)
      - merchant_id, home_country_iso, mcc, channel

[H] Hurdle decision (S1)
      - rng_event.hurdle_bernoulli
      - exactly 1 row per merchant; S3 requires is_multi == true

[N] Accepted outlet count (S2)
      - rng_event.nb_final (non-consuming)
      - exactly 1 row per (multi-site) merchant with n_outlets = N >= 2

[P] Policy: S3 rule ladder
      - policy.s3.rule_ladder.yaml (governed artefact)
      - closed vocabularies for decision_type, reason_codes, tags, channel, etc.
      - defines precedence, default, and trace rules

[ISO] Static references
      - iso3166_canonical_2024      (canonical ISO-3166-1 list)
      - (optional) static.currency_to_country.map.json
           * static currency→country mapping (if used by ladder / priors)

[W] (Optional) deterministic weight params
      - policy.s3.base_weight.yaml, policy.s3.thresholds.yaml
      - only if S3 also computes priors / integerised counts

[K] Lineage keys (from S0)
      - parameter_hash       (partition for all S3 outputs)
      - manifest_fingerprint (for provenance only; may be embedded)

[NM] Numeric / RNG note
      - S3 uses numeric policy but **defines no RNG families**
      - no RNG labels, no budgets, no rng_envelope, no RNG events


Segment-level context (where S3 sits in 1A)
-------------------------------------------

(S0) Universe, hashes, RNG & numeric law (no RNG draws)
    ⇒ hurdle_design_matrix                 @ [parameter_hash]
    ⇒ crossborder_eligibility_flags        @ [parameter_hash]   (alternative gate; S3 has its own ladder)
    ⇒ {seed, parameter_hash, manifest_fingerprint, run_id} + numeric policy

(S1) Hurdle: single vs multi   [RNG-bounded]
    ⇒ rng_event.hurdle_bernoulli          @ [seed, parameter_hash, run_id]
          · exactly 1 per merchant
          · is_multi gates S2/S3/S4/S6/S7/S8

(S2) NB mixture → total outlets N >= 2   [RNG-bounded]
    ⇒ rng_event.nb_final (non-consuming) @ [seed, parameter_hash, run_id]
          · exactly 1 per multi-site merchant
          · n_outlets = N (N >= 2)


[ M ] + [ H ] + [ N ] + [ P ] + [ ISO ] + [ W? ] + [ K ]
                        |
                        v

(S3) Candidate universe & inter-country order  [DETERMINISTIC; NO RNG]

    Conceptual responsibilities (per multi-site merchant):

      1) S3.0 - Load scopes
           - Resolve all inputs via dataset_dictionary / artefact registry.
           - Enforce gates:
                * exactly 1 hurdle row with is_multi == true
                * exactly 1 nb_final row with N >= 2
                * ladder + ISO (+ static map / weight params if used) present with expected digests
           - Build immutable Context:
                { merchant_id, home_country_iso, mcc, channel, N,
                  parameter_hash, manifest_fingerprint, artefact digests }

      2) S3.1 - Rule ladder (policy evaluation; no RNG)
           - Evaluate ordered, deterministic rule ladder over Context.
           - Collect fired rules; compute:
                * eligible_crossborder : bool
                * decision_source      : rule_id
                * rule_trace[]         : ordered trace of fired rules

      3) S3.2 - Candidate universe (unordered set C)
           - Build candidate set C of country_iso values:
                * always includes home_country_iso (marked is_home=true)
                * may add foreigns selected by ladder / static map
           - Attach per-row metadata:
                * filter_tags[]  (tags from ladder, incl. "HOME" for home row)
                * reason_codes[] (reason codes from admitting rules)
                * (optional) base_weight_inputs (if priors enabled later)
           - Domain constraints:
                * C is non-empty and contains home
                * if eligible_crossborder == false ⇒ C == {home}

      4) S3.3 - Ordering & tie-break (total order)
           - Impose **single canonical comparator** over C:
                · candidate_rank(home) = 0
                · all foreigns strictly after home, ranks 1..K
                · ranks contiguous, no gaps, no duplicates
           - Comparator uses only:
                * home vs foreign
                * reason_codes, tags, ISO
                * rule ladder semantics
           - No weights, no RNG; sort must be stable.

      5) Optional S3.4–S3.5 (if enabled; priors / integerised counts / sequences)
           - deterministic base-weight priors:
                * compute base_weight_dp (scaled decimals) per candidate
                * emit s3_base_weight_priors (deterministic scores, not probabilities)
           - deterministic integerisation:
                * given N and weights, compute integer counts per country (sum = N)
                * record residual_rank for largest-remainder tie-break
           - optional site sequencing:
                * derive per-country site_order, optional site_id
                * never introduce a second notion of inter-country order

      6) S3.6 - Emit tables (authoritative, parameter-scoped)
           - Resolve paths via dataset_dictionary only.
           - Partition scope: parameter_hash={…} (no seed partition).
           - Always emit:
                · s3_candidate_set
                     merchant_id, country_iso, is_home, candidate_rank,
                     filter_tags[], reason_codes[], parameter_hash, …
           - Optionally emit (if configured / implemented):
                · s3_base_weight_priors (fixed-dp decimals)
                · s3_integerised_counts (count, residual_rank)
                · s3_site_sequence (site_order, optional site_id)
           - Enforce:
                · embedded parameter_hash matches path
                · writer sort e.g. (merchant_id, candidate_rank, country_iso)
                · atomic publish; identical inputs ⇒ byte-identical outputs


Downstream touchpoints (what depends on S3)
-------------------------------------------
- S4 - ZTP foreign K_target:
    · uses s3_candidate_set to define admissible foreign set and A = |foreigns|

- S5 / S6 / S7:
    · treat s3_candidate_set as the domain when intersecting with currency weights
      and selecting foreign membership / counts

- S8 - outlet_catalogue egress:
    · NEVER encodes cross-country order; within-country only.
    · Any code needing inter-country order MUST join s3_candidate_set.candidate_rank.

- S9 - Validation & replay:
    · replays S3 deterministically from:
         merchant ingress, S1 hurdle, S2 nb_final, rule ladder artefact, ISO (+ static map if used).
    · checks:
         - gates (is_multi, N>=2) were respected
         - s3_candidate_set ranks are total & contiguous
         - any optional priors / integerised counts match N and the S3 comparator
    · enforces S3 as **single authority** for inter-country order within 1A.


Legend
------
(Sx)          = state
[name]        = artefact / dataset id
@[keys]       = partition keys
[DETERMINISTIC; NO RNG] = no Philox substreams, no RNG events; pure functions of inputs
```

