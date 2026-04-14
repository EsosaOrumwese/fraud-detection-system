# Merchant Allocation Policy: First Read

## Why this note exists

After the GDP artefact and frozen bucket-map read, the next question was whether
[merchant_allocation.1A.yaml](../../../../../config/layer1/1A/policy/merchant_allocation.1A.yaml)
is important to the current investigation, and if so, where it sits in the `1A.S0`
story.

The answer is yes, it is important, but not as a live `S0` runtime input.

It matters because it is the upstream authoring policy that shapes the merchant-country
count world inside
[transaction_schema_merchant_ids.parquet](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet)
before the engine ever starts `1A.S0`.

## Where it sits in the pipeline

### Not on the executed `S0` runtime path

The live `1A.S0` runner resolves only the reference dataset inputs:

- `transaction_schema_merchant_ids`
- `iso3166_canonical_2024`
- `world_bank_gdp_per_capita_20250415`
- `gdp_bucket_map_2024`

That is explicit in:

- [packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/inputs.py](../../../../../packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/inputs.py)
- [packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py](../../../../../packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py)

So this policy is not something `S0` actively reads when sealing the merchant universe.

### It is used one step earlier, in the reference builder

The policy is consumed by
[scripts/build_transaction_schema_merchant_ids.py](../../../../../scripts/build_transaction_schema_merchant_ids.py).

That builder:

- loads GDP, bucket, ISO, MCC, channel policy, and allocation policy
- computes country weights from the allocation policy
- turns those weights into country merchant counts
- then writes the merchant parquet that `S0` later ingests

So the placement is:

- **pre-engine / reference authoring**
- not **in-engine / S0 runtime**

That is why this file matters now. We are trying to understand the merchant universe that `S0`
receives, and this policy is one of the main surfaces that authored it.

## What the policy controls

The active policy embedded in the `2026-01-03` merchant manifest is:

- `total_merchants = 10000`
- `min_per_iso = 3`
- `max_per_iso = 800`
- `base_metric = gdp_per_capita`
- `exponent = 1.2`
- `heavy_tail = 0.15`
- regional multipliers:
  - `EU = 1.05`
  - `APAC = 1.10`

So, in plain terms, it controls:

- the size of the merchant world
- the floor and cap on country counts
- the GDP-driven weighting basis
- regional uplifts
- and a final heavy-tail concentration boost

## What I tested against the merchant parquet

I reconstructed the merchant-country count surface from the same artefacts used by the current
`2026-01-03` reference snapshot and compared four worlds:

1. **GDP-only**
   - exponent applied
   - no regional multipliers
   - no heavy-tail step
2. **GDP + region**
   - regional multipliers added
   - no heavy-tail step
3. **Corrected final policy**
   - same policy weights
   - correct one-by-one remainder allocation
4. **Implemented final policy**
   - the current builder behavior

This let me separate:

- the intended macro-allocation logic
- from the builder implementation artifact

## First result: the parquet exactly follows the implemented policy path

The current merchant parquet is an exact output of the current builder logic.

- `190 / 190` ISO country counts reproduced exactly
- `sum_abs(observed - implemented) = 0`

So the merchant-country distribution we have been reading is not merely "consistent with" the policy.
It is the direct realised output of the current implementation.

## Second result: the policy itself explains most of the broad country structure

The basic shape is already present under GDP-only corrected allocation.

Examples from the top observed countries:

| ISO | Observed | GDP-only corrected |
| --- | ---: | ---: |
| `MC` | 800 | 800 |
| `BM` | 436 | 426 |
| `LU` | 379 | 353 |
| `IE` | 337 | 314 |
| `CH` | 304 | 297 |
| `NO` | 262 | 257 |
| `SG` | 238 | 212 |
| `AU` | 212 | 189 |
| `US` | 211 | 207 |

So the broad rich-country heaviness is not being invented by later steps. GDP-per-capita weighting
already creates a materially top-heavy country world.

## Third result: the regional multipliers are selective, not dominant

Using corrected allocation, the strongest intended regional uplifts are:

| ISO | Region effect |
| --- | ---: |
| `SG` | +15 |
| `AU` | +14 |
| `HK` | +10 |
| `LU` | +9 |
| `NZ` | +9 |
| `IE` | +8 |
| `JP` | +7 |
| `KR` | +7 |

This is coherent with the policy:

- APAC uplift clearly helps `SG`, `AU`, `HK`, `NZ`, `JP`, `KR`
- EU uplift clearly helps `LU`, `IE`, and other EU names further down

So the regional multipliers are real and visible, but they are not the main reason the country distribution looks top-heavy.

## Fourth result: the heavy-tail step adds another concentrated boost to already-heavy countries

Using corrected allocation, the strongest intended heavy-tail effects are:

| ISO | Heavy-tail effect |
| --- | ---: |
| `BM` | +20 |
| `LU` | +18 |
| `IE` | +16 |
| `CH` | +15 |
| `NO` | +12 |
| `SG` | +12 |
| `AU` | +10 |
| `DK` | +10 |
| `US` | +10 |

So the policy is doing what its description suggests:

- GDP creates the base hierarchy
- region multipliers selectively strengthen favored blocs
- heavy-tail then further concentrates weight into already-strong markets

This is the main authored explanation for why the merchant-country world looks so concentrated.

## Fifth result: `GH` is not a normal policy outcome

This is the most important exception.

For `GH`:

- observed = `315`
- GDP-only corrected = `7`
- GDP + region corrected = `7`
- corrected final policy = `6`
- implemented final policy = `315`

So `GH` is not being made large by:

- GDP weighting
- regional uplift
- or the intended heavy-tail policy

It is being made large by the **current builder implementation**.

## What the implementation artifact is

The builder's leftover-reconciliation logic grants residual merchants in chunks to the current
highest-ranked eligible country, rather than one-by-one across the ranked remainder set.

That means one country can absorb an abnormally large share of unresolved remainder mass.

Against the corrected final policy:

- `189` ISO rows change
- total absolute difference = `616`

But almost all countries move only by `-1` or `-2`.

The distortion is concentrated mainly in one place:

- `GH`: implemented `315` vs corrected `6` => artifact `+309`

So the anomaly is not that the whole policy is broken. It is that the current implementation
of the final reconciliation step produces one major outlier.

## Assessment

The policy is worth looking at at this point in the investigation because it explains the authored
merchant-country world that `S0` receives.

And the assessment is now clear:

- the current merchant parquet is the exact output of the current policy implementation
- the broad concentration in countries is genuinely policy-authored
- GDP-per-capita weighting is the base driver
- regional multipliers add selective bloc-specific uplift
- the heavy-tail step adds further concentration to already-strong countries
- the extreme `GH` case is not part of that intended macro story
- `GH` is a builder-side residual-allocation artifact

## What this means for our `1A.S0` investigation

This policy does matter now, but in a very specific way.

It should be read as:

- a **pre-engine authoring policy** for the merchant parquet

and not as:

- a **live `S0` runtime control surface**

So when we interpret the merchant universe in `1A.S0`, we should distinguish between:

- country structure that is intentionally authored by policy
- and country anomalies that are being introduced by the builder implementation

That distinction is essential if we want to understand what the `S0` world really means before moving deeper into `1A`.
