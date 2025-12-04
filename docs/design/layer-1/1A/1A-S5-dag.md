```
                LAYER 1 · SEGMENT 1A — STATE S5 (CURRENCY→COUNTRY WEIGHT EXPANSION)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[M] Merchant universe (for optional S5.0 κₘ cache):
    - merchant_ids (ingress) @ schemas.ingress.layer1.yaml#/merchant_ids
        · merchant_id, home_country_iso (FK to ISO), mcc, channel (others unused here)

[I] Share surfaces & ISO enumerations:
    - settlement_shares_2024Q4
        · path: reference/network/settlement_shares/2024Q4/settlement_shares.parquet
        · schema: schemas.ingress.layer1.yaml#/settlement_shares
        · PK: (currency, country_iso), columns: share∈[0,1], obs_count≥0
    - ccy_country_shares_2024Q4
        · path: reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet
        · schema: schemas.ingress.layer1.yaml#/ccy_country_shares
        · PK: (currency, country_iso), columns: share∈[0,1], obs_count≥0
    - iso3166_canonical_2024
        · canonical ISO-2 set; PK: (country_iso)
    - (optional, only if producing merchant_currency)
      iso_legal_tender_2024
        · ISO2 → primary legal tender; schema: schemas.ingress.layer1.yaml#/iso_legal_tender_2024

[P] Policy / config (parameter-scoped; contributes to parameter_hash):
    - configs/allocation/ccy_smoothing_params.yaml  (id: ccy_smoothing_params)
        · dp ∈ [0,18] (fixed decimals for output weights)
        · defaults: { blend_weight∈[0,1], alpha≥0, obs_floor≥0, min_share∈[0,1], shrink_exponent≥0 }
        · per_currency: optional overrides per ISO-4217 code
        · overrides: { alpha_iso[cur][iso]≥0, min_share_iso[cur][iso]∈[0,1] }
        · (sparsity / degrade thresholds also live here; names are policy-level, not re-specified in DAG)
    - override precedence: ISO override → currency override → global default (missing ⇒ hard FAIL)

[N] Numeric / math profile (inherited from S0):
    - numeric_policy.json
    - math_profile_manifest.json
        · IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ
        · deterministic libm; fixed-order reductions; no data-dependent reordering

[G] Run & lineage context:
    - {parameter_hash, manifest_fingerprint, seed, run_id} from S0
    - lineage rules:
        · S5 outputs are parameter-scoped only (partitioning: [parameter_hash])
        · embedded parameter_hash column MUST equal path key byte-for-byte
    - RNG non-interaction contract:
        · S5 MUST NOT emit any rng_* datasets or touch rng_trace_log for this run

[Dict] Dictionary & registry anchors:
    - dataset_dictionary.layer1.1A.yaml
        · ids, schema_ref, path, partitioning for:
            - ccy_country_weights_cache
            - merchant_currency      (S5.0)
            - sparse_flag
    - artefact_registry_1A.yaml
        · entry for ccy_smoothing_params (path + digest included in parameter_hash closure)


----------------------------------------------------------------- DAG (S5.0–S5.8 · deterministic; parameter-scoped; no RNG)

[M],[I],[Dict]  ->  (S5.0) Optional κₘ cache — derive merchant_currency
                       - Precondition:
                           * S5.0 runs only if at least one declared κₘ source exists in the dictionary:
                               · an ingress per-merchant share/vector source, and/or
                               · iso_legal_tender_2024 (country→primary legal tender).
                       - For each merchant_id in merchant_ids:
                           1) Resolve κₘ candidates from configured sources:
                               · ingress_share_vector (if declared):
                                   – read sealed surface, find currency/ies with maximal share for this merchant
                               · home_primary_legal_tender (if iso_legal_tender_2024 present):
                                   – κₘ = primary legal tender of home_country_iso
                           2) Apply precedence (binding):
                               · if ingress_share_vector present: use it as primary source;
                                   – if multiple currencies share the same max share, pick lexicographically smallest ISO-4217;
                                     tie_break_used = true
                               · if ingress_share_vector absent but legal tender present: use home_primary_legal_tender; tie_break_used = false
                           3) Validity:
                               · κₘ must be uppercase ISO-4217; unknown codes ⇒ E_MCURR_RESOLUTION (run FAIL)
                       - Emission (all or nothing):
                           * If merchant_currency is produced:
                               · exactly one row per merchant in the S0 merchant universe
                               · schema: schemas.1A.yaml#/prep/merchant_currency
                               · path: data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/
                               · PK: (merchant_id)
                           * If no valid source exists at all (neither ingress nor legal tender declared):
                               · S5.0 MUST NOT produce merchant_currency for any merchant (dataset absent)
                               · partial tables are forbidden.

[I],[P],[N],
[Dict],[G]       ->  (S5.1) Pre-flight checks & per-currency working sets
                       - Validate all three reference inputs (settlement_shares, ccy_country_shares, iso3166) against their schemas:
                           · PK uniqueness, required columns, domains, FK to iso3166_canonical_2024
                           · per-currency Σ share ≈ 1 (within ingress tolerance, e.g. ±1e-6); S5 does NOT repair ingress
                       - If any ingress contract fails ⇒ E_INPUT_SCHEMA / E_INPUT_SUM (hard FAIL; no outputs).
                       - For each currency cur:
                           · construct working country set C_cur as union of country_iso appearing for cur in either share surface
                           · sort C_cur lexicographically by country_iso A→Z (determinism; writer order only)
                           · ensure all country_iso ∈ canonical ISO set
                           · if C_cur is empty ⇒ currency is out of scope; S5 writes no rows and logs nothing for cur.

[I],[P],[N]     ->  (S5.2) Blend share surfaces (per currency, binary64)
                       - Resolve per-currency blend_weight w_cur via policy precedence (ISO override → per_currency → defaults.blend_weight).
                       - For each currency cur and each c ∈ C_cur:
                           · read s_ccy[c] from ccy_country_shares_2024Q4 (default 0 if missing)
                           · read s_settle[c] from settlement_shares_2024Q4 (default 0 if missing)
                           · compute blended share:
                               q[c] = w_cur · s_ccy[c] + (1 − w_cur) · s_settle[c]
                       - Handle degenerate source coverage (per-currency degrade, not a failure):
                           · only ccy_country_shares rows present  ⇒ degrade_mode="ccy_only"
                           · only settlement_shares rows present   ⇒ degrade_mode="settlement_only"
                           · neither surface has cur               ⇒ currency out-of-scope (already filtered in S5.1)
                       - No RNG; q[c] is purely deterministic in binary64.

[I],[P],[N]     ->  (S5.3) Effective evidence mass N_eff (sparsity robustness)
                       - Resolve obs_floor ≥ 0 and shrink_exponent ≥ 0 for each cur via policy precedence.
                       - For each cur:
                           · let e = max(shrink_exponent, 1.0)
                           · let N0   = w_cur · Σ_c n_ccy[c] + (1 − w_cur) · Σ_c n_settle[c]
                           · let N_eff = max(obs_floor, N0^(1/e))  (binary64)
                       - If N0 < 0, or N_eff is NaN/Inf ⇒ policy/numeric error ⇒ hard FAIL.
                       - N_eff is carried forward both to smoothing (S5.4) and sparsity diagnostics (S5.7).

[I],[P],[N]     ->  (S5.4) Dirichlet-style smoothing (posterior)
                       - Resolve α parameters:
                           · base alpha per currency via precedence
                           · alpha_iso[cur][iso] overrides for specific ISO2 (if present)
                           · ensure α[c] ≥ 0 for all c; unknown ISO/currency keys ⇒ E_POLICY_UNKNOWN_CODE.
                       - Compute A = Σ_c α[c] (binary64).
                       - For each c:
                           · posterior[c] = ( q[c] · N_eff + α[c] ) / ( N_eff + A )
                           · guard: denominator N_eff + A > 0; if 0 ⇒ E_ZERO_MASS (hard FAIL).
                       - posterior[c] is the smoothed, but not-yet-floored probability for cur.

[I],[P],[N]     ->  (S5.5) Floors, feasibility & renormalisation (Σ=1 pre-quantisation)
                       - Resolve min_share and min_share_iso via policy precedence:
                           · global min_share; optional currency- and ISO-specific overrides.
                       - For each c:
                           · p′[c] = max(posterior[c], min_share_for_c)
                       - Policy feasibility check:
                           · for any cur with ISO-level floors, Σ_c min_share_iso[cur][c] ≤ 1.0 MUST hold
                             ⇒ otherwise E_POLICY_MINSHARE_FEASIBILITY (run FAIL).
                       - Renormalise in binary64:
                           · if Σ_c p′[c] == 0  ⇒ E_ZERO_MASS (hard FAIL)
                           · set p[c] = p′[c] / Σ_c p′[c] for all c
                           · after renormalisation, Σ_c p[c] == 1 within binary64 arithmetic.

[P],[N]         ->  (S5.6) Quantisation at dp & exact Σ at dp
                       - dp (decimal places) taken from policy (0 ≤ dp ≤ 18); global, not per-currency.
                       - For each cur:
                           1) Half-even rounding at dp:
                               · compute t[c] = 10^dp · p[c] (binary64)
                               · apply round-half-even (banker’s rounding) to get integer ULP count u[c] (≥0)
                           2) Let S = Σ_c u[c] and T = 10^dp (target sum).
                               · if S == T: ok
                               · if S < T (shortfall):
                                   – add T−S one-ULP increments:
                                       · pick countries sorted by descending fractional remainder r[c] = frac(10^dp · p[c])
                                       · tie-break by country_iso A→Z
                               · if S > T (overshoot):
                                   – subtract S−T one-ULP:
                                       · pick countries sorted by ascending r[c]
                                       · tie-break by country_iso Z→A
                           3) Persist:
                               · weight = u[c] / 10^dp   (numeric pct01 per schema)
                               · guarantee: Σ_c weight == 1.0 at exactly dp decimal places
                       - If no allocation of one-ULP steps can make Σ weights exactly 1.0 at dp ⇒ E_QUANT_SUM_MISMATCH (hard FAIL).

[I],[P],[N]     ->  (S5.7) Sparsity diagnostics & sparse_flag (optional)
                       - Using N_eff from S5.3 and a policy-defined sparsity threshold:
                           · if N_eff < threshold for currency cur:
                               – mark cur as sparse:
                                   · is_sparse = true
                                   · obs_count = round(N0) or other policy-fixed observable
                                   · threshold = configured cutoff
                               – emit one sparse_flag row for cur
                           · else:
                               – either omit row or emit is_sparse=false (per schema/policy)
                       - Dataset (if emitted):
                           · id: sparse_flag
                           · schema: schemas.1A.yaml#/prep/sparse_flag
                           · path: data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/
                           · PK: (currency)
                       - Sparsity is **diagnostic only** (not a degrade mode); S5 still enforces Σ=1 invariants.

[I],[P],[N],
[Dict],[G]      ->  (S5.8) Write authority surfaces & enforce invariants
                       - ccy_country_weights_cache (required if S5 succeeds):
                           · schema: schemas.1A.yaml#/prep/ccy_country_weights_cache
                           · path: data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/
                           · partitioning: [parameter_hash] only
                           · PK: (currency, country_iso)
                           · columns (core):
                               – currency (ISO-4217, uppercase)
                               – country_iso (ISO-3166-1 alpha-2, uppercase; FK to iso3166_canonical_2024)
                               – weight (numeric pct01, 0 ≤ weight ≤ 1)
                               – obs_count, degrade_mode, any override and diagnostics columns per schema
                           - Writer discipline:
                               · rows sorted (currency ASC, country_iso ASC) for byte-stable reruns
                               · embedded parameter_hash column == partition key, byte-for-byte
                               · for each currency:
                                   – set of country_iso matches the working set C_cur unless narrowed by explicit policy
                                   – Σ_c weight == 1.0 at dp (group sum), and each weight ∈ [0,1]
                       - merchant_currency (optional; from S5.0):
                           · if produced, MUST be complete (one row per merchant_id in universe) or absent; no partials.
                       - sparse_flag (optional):
                           · if produced, PK=(currency), codes valid, thresholds ≥0; partitioned by parameter_hash.
                       - Any violation of schema, PK/FK, Σ or path↔embed equality ⇒ hard FAIL; S5 outputs MUST NOT be partially visible.


State boundary (authoritative outputs of S5)
-------------------------------------------
- ccy_country_weights_cache @ [parameter_hash]   (required)
    * Sole persisted authority for currency→country weights in Layer 1.
    * PK: (currency, country_iso); Σ weight == 1.0 per currency at dp; codes FK to canonical ISO tables.

- merchant_currency @ [parameter_hash]          (optional submodule S5.0)
    * Deterministic κₘ per merchant (if produced).
    * PK: (merchant_id); κₘ source and tie_break_used documented.

- sparse_flag @ [parameter_hash]                (optional diagnostics)
    * PK: (currency); flags currencies with low effective mass per policy.
    * Used for validation & monitoring; does not change weight contracts.

All S5 datasets are **parameter-scoped only**; S5 defines **no RNG families** and must not emit any rng_* artefacts.


Downstream touchpoints (from S5 outputs)
----------------------------------------
- S6 (Foreign membership selection & campaign targeting):
    * Uses:
        - merchant_currency (if present) to know κₘ per merchant (must not override κₘ).
        - ccy_country_weights_cache as the only persisted currency→country weight surface.
    * MUST:
        - join weights on (currency, country_iso) and restrict to S3’s s3_candidate_set for each merchant before rescaling.
        - treat any renormalised / restricted weights as in-memory only; MUST NOT persist alternative weight surfaces.

- S7 (Integer allocation across legal set):
    * Treats ccy_country_weights_cache as base-per-currency weights when allocating counts across `{home} ∪ foreigns`.
    * MUST NOT create or persist its own long-lived currency→country weight table; S5 remains authority.

- Validation & CI (S9 / CI jobs):
    * Re-validate:
        - Σ weights at dp, PK/FK, domains, path↔embed equality.
        - alignment of any observed narrows / overrides / degrade_mode with policy & metrics.
    * Enforce read gate:
        - no consumer (including 1A internals) may rely on S5 outputs unless the S5 run is included in a PASSing validation bundle
          for the corresponding manifest_fingerprint (no PASS → no read).

- Order authority:
    * All downstream states that require inter-country order MUST continue to use:
        - S3.s3_candidate_set.candidate_rank (home = 0)
    * S5 outputs encode **no** cross-country order; physical row order is implementation detail only.
```