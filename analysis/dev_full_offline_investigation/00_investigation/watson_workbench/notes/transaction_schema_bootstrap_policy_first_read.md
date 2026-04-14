# First Read: `transaction_schema_merchant_ids.bootstrap.yaml`

## Question

We had already explained the current merchant parquet's country shape using:

- `world_bank_gdp_per_capita_20250415`
- `gdp_bucket_map_2024`
- `merchant_allocation.1A.yaml`

The next question was narrower:

> Does `config/layer1/1A/ingress/transaction_schema_merchant_ids.bootstrap.yaml` actually explain how the current `transaction_schema_merchant_ids` parquet was authored?

This note answers that question against the active snapshot:

- parquet: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`
- manifest: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.manifest.json`
- builder: `scripts/build_transaction_schema_merchant_ids.py`

## Where the bootstrap policy sits

At the `1A.S0` documentation level, the bootstrap policy still matters.

- The acquisition guide treats it as the binding Route B config for a closed-world authored merchant universe:
  [`docs/model_spec/data-engine/layer-1/specs/data-intake/1A/transaction_schema_merchant_ids_acquisition-guide.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/data-intake/1A/transaction_schema_merchant_ids_acquisition-guide.md)
- The S0 expanded spec says that when `transaction_schema_merchant_ids` is opened, runtime dependency closure must also open and hash `transaction_schema_merchant_ids_bootstrap_policy`:
  [`docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md)
- The artefact registry still registers it as the dependency of the merchant parquet:
  [`docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`](../../../../../docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml)
- The active run's sealed inputs still include it for `1A` lineage:
  [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json)

So for `1A.S0`, the bootstrap file is still part of the governed sealed world.

The issue is not whether it exists in lineage. The issue is whether it is still the policy that actually authored the current parquet.

## What the current parquet says authored it

The active `2026-01-03` manifest points to a different authoring path:

- generator script:
  [`scripts/build_transaction_schema_merchant_ids.py`](../../../../../scripts/build_transaction_schema_merchant_ids.py)
- manifest:
  [`reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.manifest.json`](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.manifest.json)

The current manifest explicitly records:

- `allocation_policy = config/layer1/1A/policy/merchant_allocation.1A.yaml`
- `channel_policy = config/layer1/1A/policy/channel_policy.1A.yaml`
- plus GDP, bucket map, ISO canonical, MCC canonical, and numeric policy inputs

The current builder script also loads:

- `merchant_allocation.1A.yaml`
- `channel_policy.1A.yaml`

and does **not** load the bootstrap file at all.

I checked the current builder path directly. The script contains no runtime use of the bootstrap-specific knobs:

- `floor_weight`
- `bucket_base`
- `range_boosts`
- `base_p_cnp`
- bootstrap `online_heavy.mcc_set`
- bootstrap `in_person_heavy.mcc_set`

So the current state is:

- the bootstrap file is still sealed into `S0` lineage
- but the current parquet authoring path runs through `merchant_allocation.1A.yaml` and `channel_policy.1A.yaml`, not through the bootstrap file

That is the first important finding.

## What the bootstrap policy claims to govern

The bootstrap file itself declares three authored dimensions:

1. `home_country`
   - `floor_weight: 0.10`
   - `bucket_base: 2.0`
   - `min_distinct: 50`
   - explicit rule:
     `w(c) = floor_weight + bucket_base^(bucket_id(c)-1)`

2. `mcc`
   - `min_distinct: 200`
   - boosted ranges:
     - `5000-5999 x2.0`
     - `5400-5499 x4.0`
     - `5500-5599 x3.0`
     - `5800-5899 x4.0`
     - `9000-9999 x0.5`

3. `channel`
   - `base_p_cnp: 0.25`
   - online-heavy MCC set:
     `[5964, 5969, 6051, 6012]` with `p_cnp = 0.75`
   - in-person-heavy MCC set:
     `[5411, 5541, 5542, 5812, 5814]` with `p_cnp = 0.10`

The test, then, is simple:

> If this bootstrap file authored the active parquet, does the parquet actually behave like these rules?

## Test 1: country allocation against the bootstrap rule

The bootstrap home-country rule is bucket-only.

That means countries within the same GDP bucket should be treated equally by the bootstrap weighting rule itself. It has no GDP-within-bucket gradient, no regional adjustment, no heavy-tail parameter, and no per-ISO cap.

The current parquet does not behave that way.

### Observed within-bucket country spread in the active parquet

| bucket | countries | observed mean merchants/country | observed min | observed max | observed std |
|---|---:|---:|---:|---:|---:|
| 1 | 122 | 12.43 | 3 | 315 | 28.46 |
| 2 | 39 | 57.41 | 32 | 102 | 20.70 |
| 3 | 23 | 162.00 | 104 | 238 | 35.98 |
| 4 | 5 | 343.60 | 262 | 436 | 67.20 |
| 5 | 1 | 800.00 | 800 | 800 | 0.00 |

### What a bootstrap-only bucket rule would imply

Using the bootstrap weighting law naively across the active `190` countries, the expected equal-per-country mass by bucket would be approximately:

| bucket | bootstrap expected merchants/country |
|---|---:|
| 1 | 2.86 |
| 2 | 17.09 |
| 3 | 56.59 |
| 4 | 514.29 |
| 5 | 5111.11 |

That is not what the parquet looks like.

What the parquet actually shows is the pattern we already uncovered in the allocation-policy analysis:

- bucket compression exists, yes
- but within-bucket dispersion is substantial
- high bucket countries are further differentiated
- and the whole surface is capped by the builder's `max_per_iso = 800`

So the country allocation of the active parquet is not being authored by the bootstrap's bucket-only rule. It is being authored by the separate merchant allocation policy.

## Test 2: MCC allocation against bootstrap range boosts

If the bootstrap file were active, its MCC boosts should make the specified bands materially over- or under-represented relative to the underlying canonical MCC set.

That does not happen in the active parquet.

### Actual merchant share by bootstrap MCC band

| bootstrap MCC band | merchant share | canonical MCC share | share ratio vs uniform |
|---|---:|---:|---:|
| `5000-5999 x2.0` | 46.22% | 45.86% | 1.008 |
| `9000-9999 x0.5` | 1.99% | 2.07% | 0.962 |
| all other MCCs | 51.79% | 52.07% | 0.995 |

Those ratios are extremely close to `1.0`.

That means the active parquet is not showing the kind of amplified MCC skew that the bootstrap boosts would create. Instead, it looks close to a near-uniform assignment across the canonical MCC list, which is exactly what the current builder does via `assign_mcc_sequence(...)`.

So on MCC as well, the active parquet behaves like the current builder path, not like the bootstrap file.

## Test 3: channel assignment against bootstrap channel rules

The bootstrap file declares:

- base `card_not_present` probability = `0.25`
- online-heavy set should move to `0.75`
- in-person-heavy set should move to `0.10`

The active parquet does not follow those exact rules.

### Behaviour if grouped by the bootstrap special MCC sets

| bootstrap group | merchants | observed CNP ratio |
|---|---:|---:|
| all other MCCs | 9705 | 25.05% |
| bootstrap in-person-heavy set | 177 | 17.51% |
| bootstrap online-heavy set | 118 | 55.08% |

This is only a partial fit:

- the all-other group does sit near the bootstrap base `0.25`
- but the online-heavy set is not at `0.75`
- and the in-person-heavy set is not at `0.10`

At the MCC level the mismatch is even clearer:

- `5964`, `5969` are effectively 100% CNP
- but `6012` and `6051`, which bootstrap also marks as online-heavy, are only about `15%` and `14%` CNP
- the in-person-heavy MCCs do skew lower-CNP, but not to a strict `10%` rule

### What the active parquet matches better instead

The current parquet fits the separate channel policy much better:

- `4800-4899` -> ~100% CNP
- `5960-5969` -> ~99.7% CNP
- `5990-5999` -> ~99.3% CNP
- `7390-7399` -> ~99.5% CNP
- all other MCCs -> ~17.4% CNP

That is the signature of:

- `config/layer1/1A/policy/channel_policy.1A.yaml`
- plus the builder's per-ISO adjustment logic and global bounds enforcement

not the bootstrap file's special-MCC set rules.

## Historical clue

There is evidence that the bootstrap file was genuinely the authoring artefact for older merchant snapshots.

For example:

- the older `2025-12-31` provenance sidecar explicitly records the bootstrap config path and bootstrap SHA:
  [`reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.provenance.json`](../../../../../reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.provenance.json)
- the `2026-01-03` logbook also records a bootstrap-driven regeneration story:
  [`docs/logbook/01-2026/2026-01-03.md`](../../../../../docs/logbook/01-2026/2026-01-03.md)

But the current `2026-01-03` manifest and current builder code now describe a different authoring regime.

So the most defensible reading is:

- the bootstrap file is a legacy or transitional authoring artefact
- it remains sealed into `S0` dependency closure
- but the current merchant parquet has been authored by a newer builder path that no longer consumes it directly

## Conclusion

For our current `1A.S0` investigation, `transaction_schema_merchant_ids.bootstrap.yaml` is **still important**, but not in the way we first assumed.

It is important as:

- a sealed lineage artefact
- a documentation clue about the intended Route B closed-world merchant authoring posture
- evidence of how this ingress surface was originally meant to be governed

It is **not** the best explanatory policy for the active `2026-01-03` merchant parquet.

The active parquet is explained much better by:

- `merchant_allocation.1A.yaml` for country mass
- `channel_policy.1A.yaml` for channel behaviour
- the current builder implementation in `scripts/build_transaction_schema_merchant_ids.py`
- and the builder-side residual allocation artifact we already traced through `GH`

So if the analytical question is:

> How was the active merchant parquet authored?

then the answer is:

- not primarily by the bootstrap file
- but by the newer builder path whose manifest records allocation policy + channel policy as the operative inputs

## What this means for the notebook

If we bring the bootstrap file into the notebook, the right framing is not:

> "This is the policy that authored the current parquet."

The right framing is:

> "This is the sealed bootstrap artefact that `1A.S0` still treats as part of the governed ingress world, but the active parquet no longer behaves as though it was authored by this file directly."

That makes it an important investigative finding rather than a dead end:

- the governed lineage story still points to bootstrap
- the active authoring story now points elsewhere
- that gap itself is part of understanding the real governed world we are standing in
