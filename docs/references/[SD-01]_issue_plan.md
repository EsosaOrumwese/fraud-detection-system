# SPEC-SD-01 · Entity Catalogues & Zipf Sampling
*Author · Esosa Orumwese — 16 Jun 2025*  
*Status · Proposed*

## 1 · Context
The current generator creates one-off `customer_id`, `card_pan_hash`, and `merchant_id` values.  
Real-world payment data shows **power-law skew**: a small share of entities generate the majority of transactions.  
To unlock realistic behavioural features (velocity, merchant loyalty, etc.) we need reusable entity catalogues and a Zipf-like sampling scheme.

## 2 · Objectives
* Generate three lookup Parquet tables  
  `customers.parquet`, `cards.parquet`, `merchants.parquet`.
* Re-use these entities in the generator so that:
  * Top 10 % of customers → ≥ 50 % of transactions.  
  * Top 10 % of merchants → ≥ 40 % of transactions.  
* Keep total Parquet size < 5 MB; generation ≤ 15 s on laptop.
* No new AWS spend (catalogues stored in existing `fraud-artifacts-*` bucket).

## 3 · Scope
### In-scope
* Polars script to build catalogue Parquets (committed once).  
* Generator flag `--realism v2` that activates Zipf sampling.  
* Unit test verifying distribution skew.

### Out-of-scope
* Scenario-based fraud injection (handled in SD-03).  
* Graph features (future sprint).

## 4 · Approach
1. **Catalogue builder** (`simulator/catalogues.py`)  
   * `customers`: 20 000 rows, fields = `customer_id`, `country_code`.  
   * `cards`: 200 000 rows, `card_pan_hash`, `customer_id`, `card_scheme`.  
   * `merchants`: 5 000 rows, `merchant_id`, `mcc_code`, `country`.
2. **Zipf weights**  
   * Pre-compute `weights = np.random.zipf(a=1.2, size=N)` → normalise.  
   * Use `rng.choice(population, p=weights)` inside generator.
3. **Integration**  
   * Generator takes `catalogue_dir` param (defaults to S3 path).  
   * Fallback to IID path when `--realism v1`.
4. **Acceptance validation**  
   * Polars group-by counts → assert distribution ratios in unit test.  
5. **Docs**  
   * Data dictionary update linking catalogue columns.  
   * ADR addendum in ADR-0006.

## 5 · Dependencies / Risks
* Requires ORCH-01 compose env to include Polars in Airflow image (already done).  
* Large weights array could bloat memory → mitigate by sampling indices only.

## 6 · Acceptance Criteria (BDD)
*Given* the generator is run with `--realism v2 --rows 1_000_000`  
*When* grouping by `customer_id`  
*Then* the top 10 % customers contribute **≥ 50 %** of rows.

*Given* catalogue Parquets are missing  
*Then* generator raises clear error with build-instructions link.

## 7 · Rollback / Safety
`--realism v1` path remains default; disabling v2 reverts to IID entities.  
Catalogue Parquets stored under `fraud-artifacts/catalogues/v1/` → versioned.


---

# Issue body — Implementation Checklist

*(create/attach to the SD-01 issue)*

### Tasks
- [ ] `catalogues.py` builder script
- [ ] Parquet tables generated locally & uploaded to `fraud-artifacts/...`
- [ ] Integrate Zipf sampling into `generate.py` (`--realism v2`)
- [ ] Unit test `test_zipf_distribution.py`
- [ ] Update docs (data dictionary + ADR addendum)
- [ ] CI passes (import test + unit test)

### Definition of Done
* Spec approved and linked  
* All checklist items complete, CI green  
* Parquet lookup tables visible in S3  
* Distribution test satisfies ≥ 50 % / ≥ 40 % thresholds


---