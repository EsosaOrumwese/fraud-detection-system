# First Read: `channel_policy.1A.yaml`

## Question

After resolving the bootstrap-policy question, the next authoring question for the merchant parquet was:

> How does `config/layer1/1A/policy/channel_policy.1A.yaml` shape the `card_present` / `card_not_present` world we see in `transaction_schema_merchant_ids`?

This note answers that against the active merchant snapshot:

- parquet: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`
- manifest: `reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.manifest.json`
- builder: `scripts/build_transaction_schema_merchant_ids.py`
- policy: `config/layer1/1A/policy/channel_policy.1A.yaml`

## Where this policy sits

Unlike the bootstrap policy, this one is clearly part of the **active** authoring path.

The current builder script explicitly uses it in three stages:

1. `initial_channel(...)`
   - assign an initial default channel by MCC band
2. `adjust_iso_channels(...)`
   - rebalance each ISO's channel mix into the allowed CNP corridor
3. `enforce_global_mix(...)`
   - verify the final global channel mix stays within the configured global bounds

So the policy is not just a passive reference. It directly governs how the parquet's `channel` column is built.

Relevant source:

- [`scripts/build_transaction_schema_merchant_ids.py`](../../../../../scripts/build_transaction_schema_merchant_ids.py)

## What the policy says

The policy has three important pieces:

1. Global channel corridor
   - `card_present`: `0.60` to `0.90`
   - `card_not_present`: `0.10` to `0.40`

2. MCC bands that default to `card_not_present`
   - `4800-4899`
   - `5960-5969`
   - `5990-5999`
   - `7390-7399`

3. ISO-specific CNP overrides
   - `US`: `0.25` to `0.40`
   - `GB`: `0.20` to `0.40`

Tolerance:

- `channel_ratio_abs = 0.02`

The important implementation detail is that the builder does **not** stop at assigning MCC-band defaults.
It then rebalances each ISO toward the midpoint of its allowed CNP range, subject to integer constraints.

That midpoint logic is what explains a lot of the merchant parquet's channel structure.

## What the active parquet actually does

### 1. Global mix

Observed channel counts in the active parquet:

- `card_not_present = 2527`
- `card_present = 7473`

Observed global CNP ratio:

- `0.2527`

This fits the policy cleanly:

- global CNP target range is `0.10` to `0.40`
- observed `0.2527` sits comfortably inside it

So at the top level, the policy is working exactly as a bounded global control.

## 2. MCC-band behavior

The configured CNP-default bands behave almost exactly as the policy suggests they should.

### Policy-band summary in the active parquet

| policy band | merchants | CNP ratio | distinct MCCs |
|---|---:|---:|---:|
| `4800-4899` | 206 | 1.0000 | 7 |
| `5960-5969` | 287 | 0.9965 | 9 |
| `5990-5999` | 274 | 0.9927 | 8 |
| `7390-7399` | 189 | 0.9947 | 5 |
| `policy_default` | 9044 | 0.1741 | 261 |

This is one of the clearest policy-to-data matches we have seen so far in the merchant parquet.

Interpretation:

- the configured CNP-heavy MCC ranges are not mildly tilted; they are almost entirely CNP
- everything outside those ranges is much more CP-heavy
- so the policy is creating a structurally two-tier channel world:
  - near-all-CNP specialist bands
  - a broad default world with much lower CNP share

This is much stronger evidence of active policy authorship than anything we saw for the bootstrap file.

### MCC-level details

Within those bands, most MCCs are exactly or almost exactly 100% CNP.

Examples:

- `4812`, `4814`, `4815`, `4816`, `4821`, `4829`, `4899` -> all `1.0`
- `5960`, `5962`, `5963`, `5964`, `5965`, `5966`, `5968`, `5969` -> all `1.0`
- `5992`, `5993`, `5995`, `5996`, `5997`, `5998`, `5999` -> all `1.0`
- `7393`, `7394`, `7395`, `7399` -> all `1.0`

Only a few MCCs in those bands are slightly lower, for example:

- `5967` -> `0.9744`
- `5994` -> `0.9444`
- `7392` -> `0.9762`

That is still extremely close to the policy's intended default posture.

## 3. ISO-level behavior

The ISO-level results are where the builder's midpoint rebalance becomes most visible.

### The striking pattern in the top countries

For most of the leading countries, the CNP ratio is almost exactly `0.25`.

Examples from the top merchant countries:

- `MC`: `0.2500`
- `BM`: `0.2500`
- `LU`: `0.2507`
- `IE`: `0.2493`
- `GH`: `0.2508`
- `CH`: `0.2500`
- `NO`: `0.2519`
- `SG`: `0.2521`
- `AU`: `0.2500`

This is not accidental.

For non-override countries, the policy corridor is:

- min CNP = `0.10`
- max CNP = `0.40`

The builder targets the midpoint:

- `(0.10 + 0.40) / 2 = 0.25`

So the repeated `~25%` CNP posture across the big countries is a direct expression of the builder logic.

This is a very important explanatory result, because it tells us the merchant parquet's country-channel structure is not "naturally emerging." It is being actively regularised into a governed posture.

## 4. ISO overrides

The two explicit overrides are also visible in the active parquet.

### Observed override countries

| ISO | override range | observed CNP ratio | merchants |
|---|---|---:|---:|
| `US` | `0.25` to `0.40` | `0.3270` | 211 |
| `GB` | `0.20` to `0.40` | `0.2986` | 144 |

These fit the midpoint logic as well:

- `US` midpoint = `0.325` -> observed `0.3270`
- `GB` midpoint = `0.300` -> observed `0.2986`

So the override logic is not merely present in code. It is clearly expressed in the data.

## 5. Compliance across all countries

I checked the final ISO-level CNP ratios against the effective policy bounds, using:

- override bounds where present
- otherwise the global bounds
- plus the configured absolute tolerance of `0.02`

Result:

- total ISO countries: `190`
- countries within effective bounds: `190`
- countries outside bounds: `0`

That means the builder is not only expressing the policy directionally. It is satisfying the policy constraints completely across the authored merchant world.

## 6. Stronger than the manifest summary suggests

One governance detail is worth recording.

The active manifest does record a `channel_policy` section, but it only carries:

- `policy_version`
- global `card_present` / `card_not_present` bounds

It does **not** preserve the full active logic:

- the MCC-band defaults
- the ISO overrides
- the tolerance

So the active authoring path is stronger than the manifest summary alone suggests.

This is not a data-shape problem, but it is a governance detail:

- the data clearly reflects the full channel policy
- the manifest only records a reduced slice of that policy

That means the manifest understates how much of the channel world is actually policy-authored.

## Conclusion

`channel_policy.1A.yaml` is a strong explanatory policy for the active merchant parquet.

It explains:

- the overall `~25%` global CNP posture
- the repeated `~25%` CNP ratios across most large non-override countries
- the special `US` and `GB` country-level channel posture
- the near-total CNP behavior of the configured MCC bands

So unlike the bootstrap artefact, this policy does not sit awkwardly beside the parquet. It fits the parquet very well.

The key analytical conclusion is:

> The merchant parquet's channel world is not loosely correlated with the policy. It is tightly authored by it.

And the most important practical reading is:

> The current merchant universe does not merely contain a CP/CNP split. It contains a governed, builder-enforced channel posture that has been regularised both by MCC semantics and by ISO-level corridor controls.

That makes `channel_policy.1A.yaml` one of the clearest active authoring surfaces we have encountered so far in `1A.S0`.
