# transaction_schema_merchant_ids country concentration explanation

## Question

Why are some home countries unusually heavy in the merchant seed universe, and is that an intended property or an implementation artifact?

## Inputs used

- merchant universe: `reference\layer1\transaction_schema_merchant_ids\2026-01-03\transaction_schema_merchant_ids.parquet`
- merchant manifest: `reference\layer1\transaction_schema_merchant_ids\2026-01-03\transaction_schema_merchant_ids.manifest.json`
- allocation policy: `config\layer1\1A\policy\merchant_allocation.1A.yaml`
- GDP surface: `reference\economic\world_bank_gdp_per_capita\2025-04-15\gdp.parquet`
- GDP bucket map: `reference\economic\gdp_bucket_map\2024\gdp_bucket_map.parquet`
- outlet expansion surface: `runs\local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1\data\layer1\1A\outlet_catalogue\seed=42\manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460\part-00000.parquet`
- zone allocation surface: `runs\local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1\data\layer1\3A\zone_alloc\seed=42\manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460\part-00000.parquet`

## Direct answer

The concentration is mostly explained by the governed merchant-allocation policy, but one prominent country outlier is amplified by the residual-allocation implementation in the merchant builder.

## What is deliberately driving the shape

- The universe is intentionally skewed rather than uniform. The manifest and policy fix `total_merchants = 10000`, `min_per_iso = 3`, `max_per_iso = 800`, GDP-per-capita weighting with exponent `1.2`, and heavy-tail boost `0.15`.
- The policy also applies regional multipliers to `EU` and `APAC`, which further favours affluent / strategic markets.
- Reproducing the builder logic against the sealed GDP surface recreates the observed top-country counts exactly for the published merchant universe. This means the chart is policy-shaped, not a plotting mistake.

## Why the richest-country cluster appears at the top

- `MC`, `BM`, `LU`, `IE`, `CH`, `NO`, `SG`, `AU`, `US`, and similar markets are all high-GDP-per-capita countries or policy-boosted countries under the allocation law.
- `MC` reaches the hard cap of `800` merchants, which is why it lands exactly at `8.00%` of the 10,000-merchant universe.
- The top-country concentration is therefore not surprising in itself; it is the intended result of a GDP-heavy, long-tailed allocation policy.

## Where the non-obvious distortion appears

- After baseline and floor allocation, the builder had `310` merchants left to assign.
- The implemented reconciliation step does not grant those one at a time across the ranked fractional remainders. Instead, it gives `min(capacity, leftover)` to the current top-ranked country before moving on.
- `GH` had the highest fractional remainder (`0.9899`), so the builder granted the full residual block to `GH`.
- That pushes `GH` to `315` merchants in the published universe, whereas a standard one-by-one largest-remainder allocation would have left it at `6` merchants. The builder therefore adds `309` merchants to `GH` relative to the standard counterfactual.

## What this means analytically

- The heavy rich-country cluster should be explained as a governed property of the merchant-allocation policy.
- `GH` should not be explained in the same way. Its prominence is materially an allocation artifact produced by the residual reconciliation step in the builder.
- So the country Pareto chart is neither 'wrong' nor purely 'economically realistic'. It is a mix of intended policy shape and deterministic builder-side artifact.

## How the merchant skew carries forward downstream

- The merchant-country skew carries into outlet and zone construction rather than disappearing downstream.
- Example: `MC` has `800` merchants, `11,204` outlet rows, and `8,019` zone rows; `LU` has `379` merchants, `5,086` outlet rows, and `4,379` zone rows.
- `GH` still carries downstream (`315` merchants, `2,838` outlet rows, `754` zone rows), but it looks shallower than the richest-country cluster once outlet and zone expansion are applied.
- That supports the view that `GH` is a merchant-universe allocation anomaly rather than a deep structural dominant market across all later surfaces.

## Files written

- top-country table: `analysis\dev_full_offline_investigation\00_investigation\watson_workbench\exports\transaction_schema_country_concentration_top20.csv`
- residual-effect table: `analysis\dev_full_offline_investigation\00_investigation\watson_workbench\exports\transaction_schema_country_concentration_residual_effect.csv`
