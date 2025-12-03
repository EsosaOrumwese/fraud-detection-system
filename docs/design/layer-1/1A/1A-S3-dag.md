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

---

```
      LAYER 1 · SEGMENT 1A — S3.DAG-B
      INTERNAL FLOW: S3.0 → S3.1 → S3.2 → S3.3 → (S3.4?) → (S3.5?) → S3.6
      All steps are PURELY DETERMINISTIC — NO RNG, NO RNG EVENTS

Inputs at S3 entry (from S0/S1/S2, read-only)
---------------------------------------------
- merchant_ids (ingress row for this merchant)
- rng_event.hurdle_bernoulli (S1; exactly 1 row; must have is_multi = true)
- rng_event.nb_final (S2; exactly 1 row; N = n_outlets ≥ 2)
- iso3166_canonical_2024
- policy.s3.rule_ladder.yaml (+ any named sets / tags / reason codes)
- static.currency_to_country.map.json (if used by ladder)
- (optional) policy.s3.base_weight.yaml, etc. (if S3 owns priors)
- lineage: { parameter_hash, manifest_fingerprint, seed, run_id }
- numeric policy (for deterministic comparisons only; no new numbers created aside from priors/allocs)

Internal flow (one merchant at a time)
--------------------------------------

  +--------------------------------------------------------------+
  |  S3.0 — Load scopes & build Context (deterministic)          |
  |--------------------------------------------------------------|
  | - Resolve all inputs via artefact registry + dataset dict.   |
  | - Enforce gates:                                             |
  |     • exactly 1 hurdle row (is_multi == true)                |
  |     • exactly 1 nb_final row with N ≥ 2                      |
  |     • all governed artefacts present with expected digests   |
  |     • path partitions == embedded {seed, parameter_hash,     |
  |       run_id} on S1/S2 rows                                  |
  | - Validate vocabularies & ISO codes (merchant home in ISO).  |
  | - Build immutable Context Ctx with fields like:              |
  |     { merchant_id, home_country_iso, mcc, channel, N,        |
  |       seed, parameter_hash, manifest_fingerprint,            |
  |       artefact digests (…) }                                 |
  | - On any violation → ERR_S3_* and STOP S3 for this merchant. |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.1 — Rule ladder evaluation (deterministic policy)        |
  |--------------------------------------------------------------|
  | - Input: Ctx + full rule_ladder.rules[] (ordered).           |
  | - For each rule r in ladder order:                           |
  |     • evaluate r.predicate(Ctx) (no I/O, no RNG)             |
  |     • if true, add to Fired[] with metadata:                 |
  |           {rule_id, precedence_class, priority,              |
  |            is_decision_bearing, reason_code, tags[]}         |
  | - Resolve precedence:                                        |
  |     • DENY ≻ ALLOW ≻ {CLASS, LEGAL, THRESHOLD, DEFAULT}     |
  |     • within a class: priority ascending, then rule_id A→Z   |
  | - Output:                                                    |
  |     • eligible_crossborder : bool                            |
  |     • decision_source      : rule_id                         |
  |     • rule_trace[]         : ordered list of fired rules     |
  | - No writes; no RNG.                                         |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.2 — Candidate universe (unordered C)                     |
  |--------------------------------------------------------------|
  | - Start with C := { home_country_iso }                       |
  |     • emit row with is_home = true; add tag "HOME"           |
  | - If eligible_crossborder == true:                           |
  |     • expand named sets / admit lists from ladder:           |
  |         – add extra ISO country codes to C (foreigns)        |
  |         – for each country, accumulate tags & reason_codes   |
  |           from all contributing rules (stable union, A→Z)    |
  | - Enforce domain constraints:                                |
  |     • all country_iso in C must exist in iso3166 artefact    |
  |     • C is non-empty and contains home                       |
  | - Output (still unordered):                                  |
  |     candidate rows:                                          |
  |       { merchant_id, country_iso, is_home,                   |
  |         filter_tags[], reason_codes[],                       |
  |         (optional) base_weight_inputs }                      |
  | - On any invalid expansion → ERR_S3_CANDIDATE_*; stop S3     |
  |   for this merchant.                                         |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.3 — Ordering & tie-break (total order)                   |
  |--------------------------------------------------------------|
  | - Input: unordered C from S3.2 + Ctx (home_country_iso).     |
  | - Define deterministic comparator over candidates:           |
  |     1) home row first (is_home=true → rank 0)                |
  |     2) then foreigns; order determined by:                   |
  |          • precedence of reason_codes / tags (ladder rules)  |
  |          • ISO / rule_id / explicit policy-defined keys      |
  |        (exact key spec in doc; sort is stable)               |
  | - Apply stable sort with that comparator.                    |
  | - Assign candidate_rank:                                     |
  |     • 0 to the home row                                      |
  |     • 1..K_foreign to foreign rows, contiguous, no gaps      |
  | - Augment each candidate row with candidate_rank (and        |
  |   optional non-emitted order_key debug struct).              |
  | - Output: ranked candidate list R with candidate_rank.       |
  | - Invariants:                                                |
  |     • candidate_rank(home) = 0                               |
  |     • ranks are contiguous per merchant, no duplicates       |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.4 — Integerisation (optional: only if S3 owns counts)    |
  |--------------------------------------------------------------|
  | - Input: Ctx.N (total outlets), ranked candidates R,         |
  |          optional deterministic priors w_i (quantised dp).   |
  | - Path A (priors present):                                   |
  |     • normalise priors: s_i = w_i / Σ_j w_j                  |
  |     • ideal fractional counts: a_i = N · s_i                 |
  | - Path B (no priors):                                        |
  |     • use uniform or policy-defined fallback to build a_i    |
  | - Quantise residuals to dp_resid = 8 and run largest-        |
  |   remainder scheme:                                          |
  |     • b_i = floor(a_i)                                       |
  |     • d = N - Σ_i b_i                                        |
  |     • compute residuals r_i = a_i - b_i                      |
  |     • order residuals by r_i desc, then ISO / candidate_rank |
  |       to get residual_rank (1..M)                            |
  |     • bump the top d countries: count_i = b_i + 1            |
  | - Outputs per candidate:                                     |
  |     • count_i (≥0), residual_rank_i (1..M)                   |
  | - Invariants:                                                |
  |     • Σ_i count_i = N                                        |
  |     • candidate_rank(home) still 0 (order not changed)       |
  | - On errors (e.g. Σ w_i = 0, infeasible bounds):             |
  |     → ERR_S3_INTEGER_* and stop S3 for this merchant.        |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.5 — Sequencing & IDs (optional: if S3 owns sequencing)   |
  |--------------------------------------------------------------|
  | - Input: ranked candidates R + counts per country.           |
  | - For each (merchant_id, country_iso) with count_i ≥ 1:      |
  |     • emit site_order = 1..count_i                           |
  |     • optionally derive site_id = zero-padded 6-digit        |
  |         "{site_order:06d}"                                   |
  | - Invariants:                                                |
  |     • within each (merchant, country):                       |
  |         – site_order is exactly {1..count_i}                 |
  |         – no duplicates of site_order                        |
  |     • if site_id present: unique within that block           |
  |     • if count_i > 999999 → ERR_S3_SITE_SEQUENCE_OVERFLOW    |
  |       and no sequencing for that merchant                    |
  | - Output (optional): in-memory sequence rows or              |
  |   s3_site_sequence records to be emitted in S3.6.            |
  +------------------------------+-------------------------------+
                                 |
                                 v
  +--------------------------------------------------------------+
  |  S3.6 — Emit tables (authoritative, parameter-scoped)        |
  |--------------------------------------------------------------|
  | - Resolve physical paths via dataset_dictionary only.        |
  | - Partition scope: parameter_hash={…} (no seed partition).   |
  | - Always emit:                                               |
  |     • s3_candidate_set                                       |
  |         merchant_id, country_iso, is_home, candidate_rank,   |
  |         filter_tags[], reason_codes[], parameter_hash, …     |
  | - Optionally emit (if configured / implemented):             |
  |     • s3_base_weight_priors (fixed-dp strings)               |
  |     • s3_integerised_counts (count, residual_rank)           |
  |     • s3_site_sequence (site_order, optional site_id)        |
  | - Enforce:                                                   |
  |     • embedded parameter_hash matches path                   |
  |     • ordering guarantees per table (e.g. candidate_set:     |
  |       (merchant_id, candidate_rank, country_iso))            |
  |     • atomic publish (stage → fsync → rename)                |
  |     • identical inputs ⇒ byte-identical outputs             |
  +--------------------------------------------------------------+


State-boundary invariants (what downstream relies on)
-----------------------------------------------------
- S3 defines **no RNG**; there are zero rng_event.* streams from S3.
- `s3_candidate_set.candidate_rank` is the **only authority** for cross-country order in 1A.
- All S3 outputs are parameter-scoped (partitioned by `parameter_hash` only).
- Any integer counts or sequences emitted by S3:
    • respect Σ_i count_i = N and candidate_rank(home)=0
    • never encode a second notion of inter-country order.
- Failure in any S3.x step for a merchant ⇒ **no S3 rows** for that merchant; other merchants are unaffected.
```