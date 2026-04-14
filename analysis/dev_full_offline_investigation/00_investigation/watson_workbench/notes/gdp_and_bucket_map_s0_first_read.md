# `world_bank_gdp_per_capita_20250415` and `gdp_bucket_map_2024` S0 first read

## Question

What do the sealed GDP artefact and the frozen GDP bucket map actually contribute at `1A.S0`, and how much do they explain the merchant-country concentration we have already observed?

## Why this matters

The merchant-allocation story is no longer just a question of "some rich countries are heavy." We now need to pin:

- whether the GDP surface itself is complete and clean for the merchant universe
- whether the bucket map fully covers the same country set
- whether the heavy-country cluster is materially concentrated in the upper GDP buckets
- whether any large country sits outside that macro-economic explanation

This is the difference between saying "the chart looks rich-country skewed" and being able to explain the exact governed artefacts that author that skew.

## Authoritative sources checked

- acquisition guide: `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/world_bank_gdp_per_capita_20250415_acquisition-guide.md`
- acquisition guide: `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/gdp_bucket_map_2024_acquisition-guide.md`
- state authority: `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md`
- sealed GDP artefact: `reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet`
- sealed GDP bucket artefact: `reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet`
- canonical ISO authority: `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
- merchant universe already under investigation: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`

## What the spec says these surfaces are

The GDP artefact is the pinned World Bank GDP-per-capita vintage:

- ID: `world_bank_gdp_per_capita_20250415`
- indicator: `NY.GDP.PCAP.KD`
- meaning: GDP per capita in constant 2015 USD
- required observation year: `2024`

The bucket map is a precomputed categorical view of that same GDP surface:

- ID: `gdp_bucket_map_2024`
- method: `jenks`
- `k = 5`
- required source year: `2024`
- runtime posture: frozen input, not something to recompute inside the engine path

The state doc is explicit that both are required sealed inputs at `1A.S0`, and it even calls out the optional CI-only check of recomputing the Jenks split and diffing it against the frozen bucket map. So the intended design is:

- GDP artefact = authoritative continuous macro-economic surface
- bucket map = authoritative frozen discretisation of that surface

## What is actually in the sealed artefacts

### GDP artefact

The sealed GDP parquet contains:

- `190` rows
- `190` unique `country_iso`
- columns:
  - `country_iso`
  - `observation_year`
  - `gdp_pc_usd_2015`
  - `source_series`

Validity checks:

- `observation_year` is `2024` for all rows
- `source_series` is `NY.GDP.PCAP.KD` for all rows
- every GDP ISO joins cleanly to the canonical ISO table

### Bucket map artefact

The sealed bucket parquet contains:

- `190` rows
- `190` unique `country_iso`
- columns:
  - `country_iso`
  - `bucket_id`
  - `bucket_label`
  - `method`
  - `k`
  - `source_year`

Validity checks:

- `bucket_id ∈ {1,2,3,4,5}` for all rows
- `method = "jenks"` for all rows
- `k = 5` for all rows
- `source_year = 2024` for all rows
- every bucket ISO joins cleanly to the canonical ISO table

One small but important implementation detail:

- `bucket_label` is null for all `190 / 190` rows

That is not a contract failure because the acquisition guide marks `bucket_label` as nullable and optional. So this artefact is behaving as a numeric bucket authority, not as a labelled presentation table.

## Coverage against the merchant universe

The merchant universe uses:

- `10,000` merchants
- `190` distinct `home_country_iso` values

Coverage result:

- merchant countries missing GDP row: `0`
- merchant countries missing bucket row: `0`

So the merchant-country universe is fully covered by both the continuous GDP surface and the frozen GDP-bucket surface. There is no need for fallback/default GDP handling on the current merchant set.

## Direct relationship to the merchant-country concentration

The relationship is extremely strong.

- Spearman correlation between `merchant_count` and `gdp_pc_usd_2015`: `0.9813`

That is strong enough that the broad merchant-country ranking should be read as materially GDP-shaped rather than only vaguely GDP-influenced.

The top countries make that visible immediately:

- `MC`: `800` merchants, GDPpc `247,170`, bucket `5`
- `BM`: `436` merchants, GDPpc `122,118`, bucket `4`
- `LU`: `379` merchants, GDPpc `104,147`, bucket `4`
- `IE`: `337` merchants, GDPpc `94,475`, bucket `4`
- `CH`: `304` merchants, GDPpc `90,067`, bucket `4`
- `NO`: `262` merchants, GDPpc `79,668`, bucket `4`
- `SG`: `238` merchants, GDPpc `67,707`, bucket `3`
- `AU`: `212` merchants, GDPpc `61,481`, bucket `3`
- `US`: `211` merchants, GDPpc `66,356`, bucket `3`

So the rich-country cluster is not just visually rich-country skewed; it is almost perfectly aligned with the governed GDP and bucket artefacts.

## The one obvious exception

`GH` is the country that does not fit the upper-bucket story:

- `GH`: `315` merchants, GDPpc `2,168`, bucket `1`

That is exactly why `GH` mattered in the earlier merchant investigation. It is the country whose prominence cannot be explained by the macro-economic surfaces alone and instead traces back to the residual-allocation implementation in the merchant builder.

So the GDP/bucket read strengthens, rather than weakens, the earlier conclusion:

- most of the heavy-country pattern is policy-shaped and GDP-authored
- `GH` is the visible artifact-amplified exception

## How the bucket map compresses the GDP surface

Country distribution across buckets:

- bucket `1`: `122` countries (`64.21%`) and `1,517` merchants (`15.17%`)
- bucket `2`: `39` countries (`20.53%`) and `2,239` merchants (`22.39%`)
- bucket `3`: `23` countries (`12.11%`) and `3,726` merchants (`37.26%`)
- bucket `4`: `5` countries (`2.63%`) and `1,718` merchants (`17.18%`)
- bucket `5`: `1` country (`0.53%`) and `800` merchants (`8.00%`)

This is the most important compression result:

- the lower buckets contain most of the countries
- the upper buckets contain most of the merchant weight

So the merchant universe is not just "more rich countries than poor countries." It is a world where a relatively small set of upper-bucket countries carries a disproportionate share of merchants.

## GDP ranges by bucket

The frozen Jenks split currently implies:

- bucket `1`: GDPpc `269` to `13,122`
- bucket `2`: GDPpc `14,579` to `37,153`
- bucket `3`: GDPpc `39,683` to `67,707`
- bucket `4`: GDPpc `79,668` to `122,118`
- bucket `5`: GDPpc `247,170` only

So the top of the merchant universe sits in a very compressed high-income band:

- one ultra-outlier bucket (`MC` alone in bucket `5`)
- a very small upper-rich cluster in bucket `4`
- a broader affluent cluster in bucket `3`

This helps explain why the top countries feel unusually concentrated without requiring the distribution to be uniform across all `190` countries.

## Compression views now exposed

The compression story is now exposed from three complementary angles:

- ranked continuous GDP surface, coloured by frozen bucket membership
- within-bucket GDP distributions
- explicit bucket-range compression with min / median / max GDP per bucket

Those views make three things visually clear:

- the continuous GDP surface is smooth, but the bucket map segments it into discrete ordered macro-economic bands
- the segmentation is not uniform: the low-income end is long and dense, while the upper-income end is short and highly compressed
- the bucket map preserves more macro-economic distinction at the rich end than at the poor end

So the bucket map is not just a convenience label surface. It is an asymmetric compression of the continuous GDP world that later policy and allocation logic inherits directly.

## Top-country composition by bucket

Within the top `20` merchant countries:

- bucket `1`: `1` country, `315` merchants (`5.99%` of top-20 merchant weight)
- bucket `3`: `13` countries, `2,429` merchants (`46.16%`)
- bucket `4`: `5` countries, `1,718` merchants (`32.65%`)
- bucket `5`: `1` country, `800` merchants (`15.20%`)
- bucket `2`: `0` countries in the top `20`

That is a clean result:

- the heavy-country cluster is overwhelmingly a bucket `3–5` phenomenon
- bucket `2` does not meaningfully participate in the extreme top end
- the lone low-bucket exception is `GH`

## Direct interpretation

These two artefacts are doing exactly what they were supposed to do at `S0`:

- `world_bank_gdp_per_capita_20250415` gives the merchant builder a complete, pinned macro-economic surface
- `gdp_bucket_map_2024` gives downstream policy logic a frozen categorical compression of the same surface

And analytically, they explain most of the merchant-country concentration:

- the ranking is overwhelmingly GDP-shaped
- the upper merchant mass is concentrated into a small upper-bucket set
- the bucket map makes that concentration easier to reason about in later policy layers

The only country that clearly resists that explanation is `GH`, which remains best understood as a builder-side residual-allocation artifact rather than a macro-economic top-country.

## What this suggests next

The next useful governed-artefact check after this is the merchant-allocation policy itself:

- `config/layer1/1A/policy/merchant_allocation.1A.yaml`

Reason:

- we now know the continuous and bucketed macro-economic surfaces are clean and complete
- the next question is exactly how the allocation policy turns those surfaces into country counts, caps, boosts, and the observed long-tail shape

## Files written

- merchant-country GDP/bucket summary:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_merchant_country_summary.csv`
- bucket distribution summary:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket_distribution.csv`
- bucket GDP-range summary:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket_ranges.csv`
- relationship scatter:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_relationship_scatter.png`
- top-country bucket-membership view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_top20_bucket_membership.png`
- bucket-compression view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket_compression.png`
- low-bucket exception view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket1_exception.png`
- ranked GDP surface view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_ranked_surface.png`
- within-bucket GDP distribution view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket_distributions.png`
- explicit GDP range compression view:
  - `analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/gdp_bucket_map_bucket_ranges.png`
