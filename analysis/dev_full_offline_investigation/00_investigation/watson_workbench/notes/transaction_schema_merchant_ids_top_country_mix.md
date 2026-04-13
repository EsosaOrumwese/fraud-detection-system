# transaction_schema_merchant_ids top-country mix follow-up

## Question

Once we know the merchant universe is country-concentrated, do the heavy countries actually behave differently from the rest of the seed world, or are they mostly enlarged versions of the same merchant universe?

## Why this matters

The country Pareto chart tells us where merchant weight sits, but not whether that weight implies specialised merchant composition, different channel behaviour, or a structural analytical risk. This follow-up checks the top-country mix directly.

## Inputs used

- merchant universe: `reference\layer1\transaction_schema_merchant_ids\2026-01-03\transaction_schema_merchant_ids.parquet`
- channel policy: `config\layer1\1A\policy\channel_policy.1A.yaml`
- concentration explanation: `analysis\dev_full_offline_investigation\00_investigation\watson_workbench\notes\transaction_schema_country_concentration_explanation.md`
- residual-effect table: `analysis\dev_full_offline_investigation\00_investigation\watson_workbench\exports\transaction_schema_country_concentration_residual_effect.csv`

## Top-country set

- Investigated countries: `MC, BM, LU, IE, GH, CH, NO, SG, AU, US`
- These are the top 10 home countries by merchant count in the 10,000-row merchant universe.

## 1) Country-level MCC mix comparison

- The global merchant world is broad on category: `290` distinct MCCs, with the global top 10 MCCs accounting for only `4.91%` of merchants.
- The heavy countries are also broad rather than narrow. Even the top country group carries high MCC distinctness:
  - `MC`: `267` distinct MCCs
  - `BM`: `227` distinct MCCs
  - `LU`: `208` distinct MCCs
  - `IE`: `196` distinct MCCs
  - `GH`: `196` distinct MCCs
- The top-10-MCC share inside the heavy countries ranges from about `8.63%` (`MC`) to `14.69%` (`US`). That is more concentrated than the global `4.91%`, but still far from a narrow-category universe.
- Jensen-Shannon divergence against the global MCC distribution stays modest rather than explosive. `MC` is closest to the global MCC shape (`0.0823` bits), while `AU` (`0.3209`) and `US` (`0.3015`) drift furthest among the top countries we checked.
- Here Jensen-Shannon divergence is just a distance measure between two category mixes: the country's MCC distribution and the full global MCC distribution. `0` would mean the two shapes are effectively the same; larger values mean the country's merchant-category profile is further away from the global pattern. In this note, the metric is being used to test whether a heavy country is merely large or whether it is also structurally unusual on merchant-category composition.
- The unit is reported in `bits` because the divergence is calculated with base-2 logarithms. That does not make it a business KPI or a percentage; it is just the information-distance unit coming out of the formula. In practice, the useful reading is relative: lower values mean closer to the global MCC mix, higher values mean further away.
- A lower or higher divergence is not automatically `good` or `bad`. Lower divergence means the country looks more like a scaled version of the whole merchant world; higher divergence means the country is more compositionally distinctive. The real analytical risk is not difference itself, but failing to explain or account for that difference when interpreting downstream traffic, fraud, case, or label behaviour.
- So the main interpretation is that the heavy countries are not tiny specialised merchant pockets. They are broad merchant populations with varying but still recognisable distance from the global MCC mix.

## 2) Country-level channel mix comparison

- The global channel split is `card_present = 74.73%` and `card_not_present = 25.27%`.
- For almost every top country, the local channel split sits almost exactly on that global mix:
  - `MC`: `75.00 / 25.00`
  - `BM`: `75.00 / 25.00`
  - `LU`: `74.93 / 25.07`
  - `IE`: `75.07 / 24.93`
  - `GH`: `74.92 / 25.08`
- This means channel is far more policy-governed than country-sensitive in the merchant universe. The builder is not letting local country composition naturally drift into very different CP/CNP mixes.
- The clear exception is `US`, which lands at `67.30%` `card_present` / `32.70%` `card_not_present`. That lines up with the explicit US override in the channel policy (`CNP min=0.25, max=0.40`) rather than with emergent merchant behaviour.
- So the analytical takeaway is that country-level channel mix is mostly constrained by policy, not discovered from country-specific merchant composition.

## 3) Policy-shaped versus artifact-shaped summary

- The top-country table should not be read as if every heavy country means the same thing.
- `MC`, `BM`, `LU`, `IE`, `CH`, `NO`, `SG`, `AU`, and `US` are best treated as `policy-shaped` countries: their counts follow the governed GDP-heavy, heavy-tail allocation policy, and their residual effect relative to a standard largest-remainder allocation is immaterial (`0` or `-1`).
- `GH` is best treated as `artifact-amplified`: it picks up `309` extra merchants versus the standard largest-remainder counterfactual because the builder grants the full leftover block to the first-ranked fractional remainder country.
- That amplification is not something I found documented as an intentional realism remediation. The design/implementation surfaces describe the integerisation law as deterministic largest-remainder with stable tie-breaks and `+1` bumps to the top `d` residuals. So the `GH` jump is best read as current builder behaviour drifting away from the documented law, not as a separately-authorised policy choice.
- That matters because a heavy country can therefore mean two different things in this merchant universe:
  - real policy-shaped weight (`MC`, `BM`, `LU`, `IE`, ...)
  - builder-side residual artifact (`GH`)

## Direct answer

The optional checks strengthen the earlier conclusion rather than overturn it. The heavy countries are mostly broad merchant populations, not narrow MCC clusters. Their channel mix is almost entirely policy-governed and globally pinned. The only strong exception in the top-country set is `GH`, whose prominence is primarily a residual-allocation artifact rather than a deep structural property of the merchant world.

## Files written

- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_mix_summary.csv`
- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_channel_mix.csv`
- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_policy_artifact_summary.csv`
- `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/transaction_schema_top_country_mcc_top5.csv`
