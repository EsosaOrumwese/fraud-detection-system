```
                LAYER 1 · SEGMENT 1A — STATE S6 (FOREIGN SET SELECTION)  [RNG]

Authoritative inputs (read-only at S6 entry)
-------------------------------------------
[S3] S3 candidate set (domain & order authority):
    - s3_candidate_set @ [parameter_hash]
      · schema: schemas.1A.yaml#/s3/candidate_set
      · one row per merchant_id × country_iso
      · columns (core): merchant_id, country_iso, is_home, candidate_rank, …
      · contracts:
          * home row present with candidate_rank=0
          * foreign rows have candidate_rank>0, contiguous per merchant
          * **sole authority for inter-country order** (no other state may invent order)

[S4] ZTP target K (logs-only):
    - rng_event_ztp_final @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/ztp_final
      · one row per merchant that S4 resolved
      · payload (core): merchant_id, K_target:int≥0, lambda_extra:float>0,
                        attempts:int≥0, exhausted:bool, regime, reason?
      · non-consuming finaliser: before==after, blocks=0, draws="0"

[S5] Currency→country weights & merchant currency:
    - ccy_country_weights_cache @ [parameter_hash]
      · schema: schemas.1A.yaml#/prep/ccy_country_weights_cache
      · PK: (currency, country_iso); Σ_c weight == 1.0 per currency at dp
      · **sole persisted authority** for currency→country weights
    - (optional) merchant_currency @ [parameter_hash]
      · schema: schemas.1A.yaml#/prep/merchant_currency
      · PK: (merchant_id)
      · κ_m (ISO-4217) per merchant, plus provenance / tie_break_used
      · if absent, S6 falls back to policy-specified κ_m rules (still deterministic)
    - iso3166_canonical_2024
      · canonical ISO-2 FK table; all country_iso must FK here

[P] S6 policy (governed, participates in parameter_hash):
    - s6_selection_policy @ config/allocation/s6_selection_policy.yaml
      · validated against S6 policy JSON-Schema; unknown keys are hard FAIL
      · global defaults + per-currency overrides:
          * emit_membership_dataset : bool (default false)
          * log_all_candidates      : bool (default true)
              - true  → log key for every considered candidate
              - false → log keys only for selected candidates (validator counter-replays)
          * max_candidates_cap      : int≥0 (0 = no cap; >0 = truncate by S3.candidate_rank)
          * zero_weight_rule        : enum{"exclude","include"} (default "exclude")
              - "exclude": drop weight==0 from considered domain
              - "include": may consider weight==0 (keys/logging) but never eligible
          * dp_score_print          : int≥0 (optional; affects printing only, not selection)
      · override precedence: per_currency override → defaults

[N] Numeric / math environment:
    - numeric_policy.json, math_profile_manifest.json
      · inherit S0.8: IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ
      · deterministic libm; fixed-order reductions; open-interval U(0,1)

[G] Run & RNG context:
    - {seed, parameter_hash, manifest_fingerprint, run_id} from S0
    - rng_audit_log @ [seed, parameter_hash, run_id]  (run-scoped; already created in S0)
    - rng_trace_log @ [seed, parameter_hash, run_id]  (per (module, substream_label))
    - RNG engine & envelope law:
        · Philox 2x64-10, open-interval u∈(0,1), S0 budget rules

[Dict] Dictionary & registry:
    - dataset_dictionary.layer1.1A.yaml
      · ids/paths/schemas for:
          * rng_event_gumbel_key
          * (optional) s6_membership
      · gating for rng_event_gumbel_key:
          * gated_by: rng_event_hurdle_bernoulli
          * predicate: is_multi == true
          * also_requires: crossborder_eligibility_flags.is_eligible == true
    - artefact_registry_1A.yaml
      · S6 policy basenames & digests; S6 receipt path
      · confirms that S3/S4/S5 artefacts participate in manifest_fingerprint


----------------------------------------------------------------- DAG (S6.1–S6.8 · domain → keys → membership → receipt)

[S3],[S4],[S5],
[P],[N],[G],
[Dict]          ->  (S6.1) Pre-flight & gating (per-run and per-merchant)
                       - Resolve all dataset locations via the Data Dictionary (no hard-coded paths).
                       - Assert required artefacts exist and validate against schemas:
                           * s3_candidate_set @ parameter_hash
                           * rng_event_ztp_final @ {seed, parameter_hash, run_id}
                           * ccy_country_weights_cache @ parameter_hash
                           * S5 PASS receipt present for same parameter_hash (**no PASS → no read**)
                           * S6 policy files 𝓟 valid vs S6 policy schema
                       - For each merchant m:
                           * read S3 candidate_set rows (home+foreign) for merchant_id=m
                           * check S3 invariants:
                               – exactly one home row; candidate_rank(home)=0
                               – foreign ranks contiguous 1..A_raw
                           * read S4 rng_event_ztp_final row (if absent → merchant fails S4; S6 does not run for m)
                           * derive K_target_m from S4 payload
                           * derive κ_m (currency) either from merchant_currency or policy rule (deterministic)
                           * ensure κ_m appears in ccy_country_weights_cache; otherwise merchant is considered “no weights”
                       - Merchant-level S6 gating:
                           * proceed only if:
                               – S1 decided is_multi==true (via dictionary gating)
                               – S3 candidate_set present and valid
                               – S4 ztp_final present (K_target fixed)
                               – S5 weights present and PASSed
                           * else: mark merchant as gated_out (no S6 events; membership empty)
                       - Outputs (ephemeral, per-merchant context Ctx₆(m)):
                           * S3 foreign rows, K_target_m, κ_m, S5 weights for κ_m, policy overrides

Ctx₆,[P],[S3],
[S5]            ->  (S6.2) Selection domain Dₘ & weights (considered vs eligible)
                       - For each gated merchant m:
                           1) Start from S3 foreign candidate set:
                               · F_m = {foreign rows in s3_candidate_set for m (candidate_rank>0)}
                           2) Intersect with S5 weight support for κ_m:
                               · join on country_iso to get w_raw[c] for each c ∈ F_m
                               · drop any country with no S5 row
                           3) Apply optional cap:
                               · if max_candidates_cap>0:
                                   – sort by S3.candidate_rank (already the case)
                                   – keep first A_cap rows; drop the rest
                           4) Apply zero_weight_rule:
                               · `"exclude"` (default):
                                   – considered = eligible = {c : w_raw[c] > 0}
                                   – A_filtered = |considered|
                               · `"include"`:
                                   – considered = {c : w_raw[c] ≥ 0} (including w=0)
                                   – eligible   = {c : w_raw[c] > 0}
                                   – A_filtered = |considered|
                           5) Compute Eligible_size = |eligible|
                       - Deterministic-empties (no RNG, no keys):
                           * If A_filtered == 0:
                               – reason = NO_CANDIDATES
                               – K_realized = 0; selected set = ∅; proceed to S6.5 (empty outcome)
                           * Else if K_target_m == 0:
                               – reason = K_ZERO
                               – K_realized = 0; selected set = ∅
                           * Else if Eligible_size == 0:
                               – reason = ZERO_WEIGHT_DOMAIN
                               – K_realized = 0; selected set = ∅
                       - Only merchants with:
                           · A_filtered > 0
                           · K_target_m > 0
                           · Eligible_size > 0
                         advance to RNG-based selection in S6.3.

Ctx₆,eligible,
[P],[N],[G],
[Dict]          ->  (S6.3) RNG substream & Gumbel keys (per-merchant, per-candidate)  [RNG]
                       - Substream law for S6:
                           * module = "1A.foreign_country_selector"
                           * substream_label = "gumbel_key"
                           * base counter per merchant & label from S0 mapping:
                               – f(seed, manifest_fingerprint, "gumbel_key", merchant_id)
                       - For each merchant m that survived S6.2 empties:
                           * Compute renormalised weights over the **eligible** subset:
                               – within eligible: w[c] ≥ 0, Σ w[c] = 1 (binary64, fixed order)
                               – considered\eligible (zero-weight when include) keep w_raw[c] but are never eligible
                           * Iterate considered domain in **ascending S3.candidate_rank**:
                               – for each candidate c:
                                   1) draw u_c ~ U(0,1) via S0 open-interval mapping
                                   2) compute key_c for w_c>0:
                                          key_c = ln(w_c) − ln(−ln u_c)   (binary64)
                                      zero-weight rule:
                                          · if zero_weight_rule="include" and w_c==0:
                                              key_c := null  (treated as −∞ by validators)
                                          · if "exclude": such rows were removed already
                                   3) logging mode:
                                          – if log_all_candidates=true:
                                                · emit rng_event_gumbel_key for **every considered c**
                                          – if log_all_candidates=false:
                                                · emit rng_event_gumbel_key **only for selected c** (S6.4);
                                                  validator counter-replays missing keys
                                   4) Each gumbel_key event envelope:
                                          · before, after, blocks, draws="1"
                                          · ts_utc, seed, parameter_hash, manifest_fingerprint,
                                            module="1A.foreign_country_selector",
                                            substream_label="gumbel_key"
                                      payload (core):
                                          · merchant_id, country_iso, currency=κ_m,
                                            weight (S5 value for κ_m,c),
                                            key (float or null), maybe selection_order? (for selected only)
                               – After each event: append one rng_trace_log row for (module,substream_label)
                       - RNG invariants:
                           * each event: blocks = after−before; draws="1"
                           * substream intervals [before,after) do not overlap and are monotone per merchant
                           * rng_event_gumbel_key is the **only** RNG family S6 writes
                             (S6 does not emit NB/ZTP/Dirichlet/hurdle events)

gumbel_key events,
eligible, K_target,
Ctx₆,[P]        ->  (S6.4) Selection rule & K_realized (membership realisation)
                       - For each merchant m that drew keys:
                           * Define Eligible set E_m = {c : w_c>0 in eligible subset}
                           * Read K_target_m from S4 rng_event_ztp_final
                           * Sort E_m by:
                               1) key_c descending (higher first; null treated as −∞)
                               2) tie-break by S3.candidate_rank ascending
                               3) then country_iso A→Z
                           * Compute:
                               · K_realized_m = min(K_target_m, |E_m|)
                           * Selected set S_m:
                               · first K_realized_m countries in sorted E_m
                               · assign selection_order 1..K_realized_m (in-memory; membership surface may carry or omit)
                           * Shortfall:
                               · if |E_m| < K_target_m:
                                   – record diagnostic SHORTFALL_NOTED (non-error)
                       - Per-merchant cardinality invariant:
                           * |S_m| = K_realized_m = min(K_target_m, |E_m|)
                           * if K_target_m>0 and |E_m|>0 then K_realized_m ≥ 1
                       - Merchants that were deterministic-empty in S6.2 have S_m = ∅, K_realized_m = 0.

S_m, Ctx₆,
[Dict],[G],[P]  ->  (S6.5) Optional membership dataset (convenience only; no order)
                       - Controlled by policy:
                           * if emit_membership_dataset=false:
                               – **no table** is written; S6 outputs only RNG events + receipt
                           * if emit_membership_dataset=true:
                               – write s6_membership under:
                                      data/layer1/1A/s6_membership/seed={seed}/parameter_hash={parameter_hash}/…
                               – schema: schemas.1A.yaml#/s6/membership
                               – partitioning: [seed, parameter_hash]
                               – sort_keys: [merchant_id, country_iso] (writer policy only)
                               – PK: (merchant_id, country_iso)
                               – columns (core):
                                     · merchant_id
                                     · country_iso (FK→iso3166_canonical_2024)
                                     · seed, parameter_hash (must equal partition keys)
                                     · produced_by_fingerprint? (optional informational)
                               – **rows present iff** country_iso ∈ S_m for that merchant
                               – home country MUST NEVER appear in membership
                               – table encodes **no inter-country order** (S3.candidate_rank remains sole order authority)
                       - Authority note:
                           * s6_membership is **convenience-only**; true authority for membership is:
                               – rng_event_gumbel_key + S3 + S5 (+ counter-replay in reduced logging mode)
                           * validators must be able to re-derive membership from RNG events; mismatch ⇒ RE_DERIVATION_FAIL.

gumbel_key events,
rng_trace_log,
s6_membership?,
Ctx₆,[G],[Dict] ->  (S6.6) RNG discipline, isolation & trace accounting
                       - Module & substream labels (binding):
                           * gumbel_key → module="1A.foreign_country_selector", substream_label="gumbel_key"
                           * (optional) stream_jump for S6 not owned here; any use must obey global rng_event_stream_jump law
                       - Per-event budget invariants:
                           * draws="1", blocks = after−before for every rng_event_gumbel_key row
                           * non-consuming events (if any) must have before==after, blocks=0, draws="0"
                       - Per-merchant coverage:
                           * if log_all_candidates=true:
                               – #gumbel_key events = A_filtered (considered domain size) after cap/zero_weight_rule
                           * if false:
                               – #gumbel_key events = K_realized; validator counter-replays keys for unlogged candidates
                       - Isolation:
                           * S6 **MUST NOT** emit S1–S5 RNG families (no hurdle/NB/ZTP/Dirichlet events)
                           * rng_trace_log increments for (module="1A.foreign_country_selector", substream_label="gumbel_key")
                             must match sum of event budgets

all S6 inputs/
outputs,[G],
[Dict],[P]      ->  (S6.7) Validation, failure modes & S6 PASS receipt
                       - Structural checks:
                           * schemas/partitions/path↔embed equality for:
                               – rng_event_gumbel_key, rng_trace_log rows
                               – s6_membership (if emitted)
                           * membership ⊆ (S3 foreign candidates ∩ S5 weight support)
                           * no membership row for home country
                       - Content checks:
                           * re-compute A_filtered, Eligible_size, K_target_m, K_realized_m
                           * re-evaluate selection rule & tie-breaks
                           * ensure |S_m| = K_realized_m for all merchants
                           * ensure deterministic-empty reasons NO_CANDIDATES / K_ZERO / ZERO_WEIGHT_DOMAIN match inputs
                       - RNG accounting:
                           * reconcile rng_trace_log totals with per-event envelopes
                           * when log_all_candidates=true:
                               – assert #gumbel_key events == A_filtered
                           * when false:
                               – counter-replay keys in S3.candidate_rank order to reconstruct missing key_c
                       - Failure classes (non-exhaustive):
                           * E_UPSTREAM_GATE / E_SCHEMA_AUTHORITY / E_LINEAGE_PATH_MISMATCH
                           * E_EVENT_COVERAGE (wrong #gumbel_key events vs A_filtered or K_realized)
                           * E_S6_NOT_SUBSET_S3 / E_S6_NOT_SUBSET_S5 (membership outside S3/S5 support)
                           * E_DUP_PK (duplicate (merchant_id,country_iso) in membership)
                           * RE_DERIVATION_FAIL (cannot reconstruct membership from events + S3/S5)
                           * RNG_ACCOUNTING_FAIL / COUNTER_OVERLAP / REGRESSION
                       - On any hard FAIL:
                           * do **not** publish S6 receipt or membership surface
                           * downstream must treat S6 as failed for this (seed,parameter_hash)

all checks pass,
[G],[Dict],[P] ->  (S6.8) Outputs (state boundary) & downstream gates
                       - Authoritative RNG output:
                           * rng_event_gumbel_key @ [seed, parameter_hash, run_id]
                               – one row per considered candidate (log_all_candidates=true)
                                 or per selected candidate (false)
                               – sole RNG evidence for S6 keys & selection
                       - Optional convenience table:
            * s6_membership @ [seed, parameter_hash]  (if emit_membership_dataset=true)
                               – PK: (merchant_id, country_iso)
                               – encodes membership only; no order
                       - S6 PASS receipt (gate for convenience reads):
                           * S6_VALIDATION.json + _passed.flag under:
                                 data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/
                           * _passed.flag contains SHA-256 over ASCII-lexicographic concat of receipt files
                           * Downstream rule:
                               – **no PASS → no read** of any S6 convenience surface (membership)
                               – RNG events remain readable as part of core logs (for validation / audit)


State boundary (authoritative outputs of S6)
-------------------------------------------
- rng_event_gumbel_key              @ [seed, parameter_hash, run_id]
    * sole RNG evidence for foreign membership keys (Gumbel-top-K) per merchant.
    * gating: only for merchants with is_multi==true and crossborder_eligibility_flags.is_eligible==true.

- (optional) s6_membership          @ [seed, parameter_hash]
    * convenience-only selected-foreign surface; PK (merchant_id, country_iso).
    * no inter-country order; true authority remains S3 + S5 + rng_event_gumbel_key.

- S6 PASS receipt:
    * S6_VALIDATION.json + _passed.flag under data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/.
    * gates downstream reads of any S6 convenience surfaces (membership).  **No PASS → no read.**


Downstream touchpoints (from S6 outputs)
----------------------------------------
- S7 (allocation across `{home} ∪ foreigns`):
    * Domain D = {home} ∪ (S6-selected foreigns):
        – if K_target=0 or selected set empty → D={home} only.
    * Membership authority:
        – prefers s6_membership (if present and PASSed) for domain;
        – may re-derive from rng_event_gumbel_key + S3 + S5 when membership absent.
    * Order authority:
        – always uses S3.s3_candidate_set.candidate_rank (home=0), not S6.

- S8 (outlet materialisation):
    * Never reads S6 directly; relies on S7’s count allocation and S3’s order.
    * Must not infer any cross-country order from S6 outputs.

- S9 (layer-1 validation bundle / HashGate):
    * Incorporates S6 checks into validation_bundle_1A:
        – structural, content, RNG invariants, membership ⊆ S3/S5.
    * Enforces that any S6 convenience surfaces used elsewhere are guarded by S6 PASS.
```
