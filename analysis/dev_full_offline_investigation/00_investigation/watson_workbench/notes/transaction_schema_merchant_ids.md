# transaction_schema_merchant_ids

## Question

What kind of merchant universe does `transaction_schema_merchant_ids` define before `1A` starts building outlet-world structure?

## Why this matters

This dataset is the merchant seed universe for `1A`. Before trying to explain anything with external policy or later states, we first need to understand the shape of the merchant world it gives us.

## Current findings

- Rows: `10,000`
- Grain: one row per merchant seed
- Core fields: `merchant_id`, `mcc`, `channel`, `home_country_iso`
- Distinct countries: `190`
- Distinct MCCs: `290`
- Distinct channels: `2`

## What the merchant world looks like

- Country assignment is concentrated.
  - Top 5 countries hold `22.67%` of merchants.
  - Top 10 countries hold `34.94%`.
  - Top 20 countries hold `52.62%`.
  - Top 50 countries hold `80.27%`.
- MCC assignment is much more diffuse.
  - Top 5 MCCs hold only `2.54%` of merchants.
  - Top 10 MCCs hold `4.91%`.
  - Top 20 MCCs hold `9.36%`.
  - Top 50 MCCs hold `21.92%`.
- Channel assignment is globally stable.
  - `card_present`: `74.73%`
  - `card_not_present`: `25.27%`

## What this tells us

- The merchant universe is not dominated by a few MCCs. It is broad on merchant category.
- The strong structure is on home-country allocation, not on MCC allocation.
- The channel split looks globally governed rather than organically varying by country.

## Additional check on the heavy countries

The countries with the highest merchant counts are not narrow merchant-type clusters. They still carry broad MCC diversity.

- `MC`: `800` merchants, `267` distinct MCCs
- `BM`: `436` merchants, `227` distinct MCCs
- `LU`: `379` merchants, `208` distinct MCCs
- `IE`: `337` merchants, `196` distinct MCCs

This means the heavy countries currently look more like enlarged merchant populations than tiny specialised merchant pockets.

## Next good questions from this dataset alone

- Are the largest countries simply larger versions of the same merchant world, or do they have distinctive MCC mixes?
- Is the channel split effectively constant because of policy, or are some MCCs materially shifting it?
- Does merchant density by country feel realistic enough for the world `1A` is trying to build?
