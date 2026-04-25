# `1A.S2` Investigation: Entry and Authority

## Why this block matters

If `S1` is the gate that decides whether a merchant is allowed into the multi-site branch, then `S2` is the first state that decides how large that admitted merchant becomes.

But before reading the Gamma-Poisson realization itself, the first thing to settle is simpler and more foundational:

- **who is actually allowed into `S2`**
- **what exact artefacts govern the count world once they enter**
- **how the engine assembles the deterministic NB context before any draw occurs**

That is what this note investigates.

This is not yet the full `S2` count-world analysis. It is the authority block that fixes the entry population, the governing files, and the deterministic parameter law that later emits `rng_event_gamma_component`, `rng_event_poisson_component`, and `rng_event_nb_final`.

## Working plan used in this investigation

I approached the `S2` entry-and-authority block in four steps:

1. **Fix the state contract**
   Read the `S2` state-expanded spec, the implementation map, and the design flow to pin what the state is supposed to do before looking at the run itself.
2. **Check the actual gate population**
   Verify that the pinned run admits exactly the merchants that `S1` marked as `is_multi=true`, with no leakage from single-site merchants.
3. **Resolve the governing artefacts**
   Identify the exact files sealed into the run for the mean and dispersion lanes, plus the merchant and GDP surfaces needed to build the runtime NB context.
4. **Rebuild the deterministic `S2` context**
   Recompute the emitted `mu` and `dispersion_k` from the sealed authority surfaces and compare them back to `nb_final`.

One important discovery changed the method slightly: unlike `S1`, `S2` does **not** persist a runtime design matrix or parameter parquet of its own in the run directory. So instead of reading an `S2` design surface directly, I had to reconstruct the authoritative `S2` parameter context from the sealed merchant inputs, the GDP reference, and the two governing coefficient bundles, then reconcile that back to `nb_final`.

## Core references

Design and contract:

- [`docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md)
- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml)
- [`docs/design/data-engine/layer-1/1A/1A-S2-design-flow.mmd`](../../../../../docs/design/data-engine/layer-1/1A/1A-S2-design-flow.mmd)

Run and authority surfaces used below:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/gamma_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/gamma_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)
- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml)
- [`reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet)
- [`reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet`](../../../../../reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet)

Scratch analysis used for the derived checks in this note:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_s2_entry_authority.py`](../scratch/analyze_s2_entry_authority.py)

## What `S2` is supposed to do at this boundary

The state contract is very specific.

`S2` is the NB-outlet state. It does **not** decide whether a merchant is multi-site. That decision already belongs to `S1`.

What `S2` does is:

- admit only merchants for which `S1` emitted `is_multi=true`
- build the deterministic NB context for those admitted merchants
- turn that context into a total accepted outlet count `N`

The contract’s deterministic context is:

$$
\mu_m = \exp\!\left(\beta_\mu^\top x^{(\mu)}_m\right)
$$

where:

- `m` = merchant
- `x^{(\mu)}_m` = the NB-mean design vector
- `\beta_\mu` = the NB-mean coefficient vector carried inside `hurdle_coefficients.yaml`
- `\mu_m` = the expected outlet count of merchant `m` once it is already inside the multi-site branch

and

$$
\phi_m = \exp\!\left(\beta_\phi^\top x^{(\phi)}_m\right)
$$

where:

- `x^{(\phi)}_m` = the NB-dispersion design vector
- `\beta_\phi` = the NB-dispersion coefficient vector carried inside `nb_dispersion_coefficients.yaml`
- `\phi_m` = the dispersion / shape parameter governing the spread of the outlet-count distribution

The design vectors are also contractually narrow:

$$
x^{(\mu)}_m = [1,\ \Phi_{\mathrm{mcc}}(m),\ \Phi_{\mathrm{ch}}(m)]^\top
$$

$$
x^{(\phi)}_m = [1,\ \Phi_{\mathrm{mcc}}(m),\ \Phi_{\mathrm{ch}}(m),\ \ln g_c]^\top
$$

where:

- `1` = intercept term
- `\Phi_{\mathrm{mcc}}(m)` = MCC one-hot block for merchant `m`
- `\Phi_{\mathrm{ch}}(m)` = channel one-hot block for merchant `m`
- `g_c` = GDP per capita scalar for the merchant’s home country `c`

That last point is important because it tells us that `S2` does **not** inherit the same GDP-bucket design basis used by the `S1` hurdle lane. At `S2`, GDP reappears as a **continuous log GDP scalar in the dispersion lane**, not as a five-bucket one-hot block.

## The exact authority surfaces sealed into our pinned run

The pinned run’s sealed-input inventory confirms the exact files that mattered to `S2` entry and parameter authority.

The relevant sealed artefacts are:

- `hurdle_coefficients.yaml`
- `nb_dispersion_coefficients.yaml`
- `transaction_schema_merchant_ids`
- `world_bank_gdp_per_capita_20250415`

That matters because it fixes this investigation to the actual run rather than to whatever configuration happens to exist in the repo today.

Two practical observations matter here:

1. The active NB-dispersion file for this run lives at:
   - [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml)
   and not under a separate `models/nb_dispersion/...` tree.
2. There is **no persisted `S2` design matrix parquet** in the run output tree. Under `runs/.../data/layer1/1A/`, we still see the `S1` surfaces such as `hurdle_design_matrix`, but no materialized `S2` design table. So the authoritative `S2` parameter context has to be reconstructed from the sealed merchant and GDP inputs plus the two coefficient bundles.

That second discovery became central to the investigation method.

## What the gate into `S2` looks like in this run

The admission gate is the `S1` Bernoulli event stream.

In our pinned run:

- total hurdle rows: `10,000`
- `is_multi=true`: `5,817`
- `is_multi=false`: `4,183`

Those `5,817` merchants are the exact entry population for `S2`.

The emitted `S2` families then look like this:

- `gamma_component` rows: `5,834`
- `poisson_component` rows: `5,834`
- `nb_final` rows: `5,817`

The merchant coverage underneath those row counts is the more important fact:

- distinct merchants in `gamma_component`: `5,817`
- distinct merchants in `poisson_component`: `5,817`
- distinct merchants in `nb_final`: `5,817`

So the first entry result is clean: the number of merchants that reached `nb_final` is **exactly** the number of merchants that `S1` admitted into the multi-site branch.

## Branch purity: did any single-site merchant leak into `S2`?

This is the first thing that had to be checked, because if `S2` has event rows for merchants that `S1` marked as single-site, then the entire downstream interpretation becomes unsafe.

In this run, the branch-purity check is exact:

- single-site merchants appearing in `gamma_component`: `0`
- single-site merchants appearing in `poisson_component`: `0`
- single-site merchants appearing in `nb_final`: `0`

And from the other direction:

- admitted multi-site merchants missing `gamma_component`: `0`
- admitted multi-site merchants missing `poisson_component`: `0`
- admitted multi-site merchants missing `nb_final`: `0`

So the branch law at the `S1 -> S2` boundary is behaving exactly as the contract says it should:

- **no single-site merchant leaks into `S2`**
- **every admitted multi-site merchant reaches `nb_final`**

This is the first key conclusion of the authority block. The runtime population entering `S2` is not ambiguous.

## Lineage and event identity are singular

Across the `S1` hurdle gate and all three `S2` event families, the lineage surface is singular on:

- `seed`
- `parameter_hash`
- `manifest_fingerprint`
- `run_id`
- `module`
- `substream_label`

That means the `S2` authority surfaces are not a mixed replay of multiple runs or multiple policy bundles. They are one coherent run-scoped boundary with one fixed lineage identity.

This is easy to gloss over, but it matters. If `nb_final` had been produced under a different `parameter_hash` or `manifest_fingerprint` than the merchant/GDP inputs we were using to interpret it, the reconstruction work below would have been meaningless.

## What exactly governs the mean lane

The first governing artefact is:

- [`hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)

For `S2`, this file matters not because of the hurdle `beta` lane, but because it carries `beta_mu`.

The active `beta_mu` bundle has:

- `|dict_mcc| = 290`
- `dict_ch = ["CP", "CNP"]`
- `len(beta_mu) = 293`

That length is exactly the deterministic shape implied by the mean-lane design basis:

```text
1 intercept + 290 MCC terms + 2 channel terms = 293
```

So the mean lane does **not** include GDP directly. It is structurally:

- intercept
- MCC
- channel

The active channel terms are:

- `CP = +1.128766904935765`
- `CNP = +0.7572450117988003`

and the mean-lane intercept is:

- `1.7814957339620379`

So at a structural level, the active `S2` mean law favors `CP` over `CNP`, holding MCC fixed.

## What exactly governs the dispersion lane

The second governing artefact is:

- [`nb_dispersion_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml)

This file carries `beta_phi`, the dispersion authority for `S2`.

The active bundle has:

- `|dict_mcc| = 290`
- `dict_ch = ["CP", "CNP"]`
- `len(beta_phi) = 294`

That length is exactly:

```text
1 intercept + 290 MCC terms + 2 channel terms + 1 ln(GDP) term = 294
```

So the dispersion lane is not just “another copy of the mean lane.” It has one extra scalar authority term:

- `ln(gdp_pc)`

The active channel terms are:

- `CP = -0.07`
- `CNP = +0.07`

The active GDP coefficient is:

- `ln(gdp_pc)` term = `+0.03`

And the dispersion-lane intercept is:

- `2.2024682328784246`

So the structural story is quite specific:

- `CP` merchants are favored on the **mean** lane
- `CNP` merchants are slightly favored on the **dispersion** lane
- higher home-country GDP pushes `\phi` upward, not `\mu`, because GDP enters only the dispersion law

This is exactly the sort of distinction that is easy to miss if one treats `S2` as “just NB counts.” It is not one undifferentiated count law. It is two connected deterministic laws, one for level and one for spread.

## Reconstructing the runtime `S2` parameter context

Because there is no persisted `S2` design matrix, I reconstructed the deterministic runtime authority using:

- merchant descriptors from `transaction_schema_merchant_ids`
- home-country GDP values from `gdp.parquet`
- the frozen dictionaries and coefficients from the two policy bundles

The joins needed for that reconstruction are complete:

- `nb_final` rows: `5,817`
- missing merchant MCC: `0`
- missing merchant channel: `0`
- missing home-country GDP: `0`

So there is no hidden incompleteness in the surfaces needed to rebuild the deterministic `S2` context.

The GDP surface used in this run is the `gdp_pc_usd_2015` column, with values ranging across the admitted merchant population from about:

- minimum GDP per capita: `268.700857391724`
- maximum GDP per capita: `247170.219910657`

That range matters because the dispersion law is fed by `ln(gdp_pc)`, so this is not a negligible scalar.

## Do the emitted `mu` and `dispersion_k` actually come from those sealed authority surfaces?

This is the core check of the investigation.

I rebuilt:

$$
\mu_m = \exp\!\left(\beta_\mu^\top x^{(\mu)}_m\right)
$$

and

$$
\phi_m = \exp\!\left(\beta_\phi^\top x^{(\phi)}_m\right)
$$

for every merchant that reached `nb_final`, using only:

- merchant MCC
- merchant channel
- home-country GDP
- `beta_mu`
- `beta_phi`

and then compared the rebuilt values back to the emitted `nb_final.mu` and `nb_final.dispersion_k`.

The match is exact to machine precision:

- mean absolute difference in `mu`: `2.4225268707172403e-15`
- max absolute difference in `mu`: `2.1316282072803006e-14`
- mean absolute difference in `phi`: `2.1693723546672478e-15`
- max absolute difference in `phi`: `1.0658141036401503e-14`

All `5,817` merchants are within `1e-12` for both `mu` and `phi`.

That is the strongest authority result in this note.

It means the run’s `nb_final` surface is not carrying arbitrary or stale parameters. Its emitted `mu` and `dispersion_k` are exactly the deterministic consequences of:

- the sealed merchant descriptors
- the sealed GDP reference
- the active `beta_mu`
- the active `beta_phi`

So for this run, the deterministic `S2` context is not merely documented by the contract. It is **provably the one that authored the emitted `nb_final` rows**.

## What the admitted `S2` population looks like at this boundary

Because `S2` only sees merchants that passed the hurdle, its input population is not the full merchant universe but the admitted branch.

Within those entrants:

- mean `S1` branch probability among `S2` entrants: `0.630177`
- median `S1` branch probability among `S2` entrants: `0.644945`
- minimum among entrants: `0.154759`
- maximum among entrants: `0.950381`

So entry into `S2` is not restricted only to the highest-confidence branch cases. Some lower-propensity merchants still cross into the multi-site world, which is exactly what a Bernoulli gate should allow.

The deterministic `S2` authority then turns that admitted population into the following parameter world:

### `mu` surface

- mean `mu`: `20.139260`
- median `mu`: `17.695618`
- 25th percentile: `12.727214`
- 75th percentile: `24.469441`
- max: `72.658507`

### `phi` surface

- mean `phi`: `12.201235`
- median `phi`: `12.055353`
- 25th percentile: `10.998862`
- 75th percentile: `13.197001`
- max: `19.178568`

This is still not the realized count world yet. But it does tell us what sort of count world `S2` was instructed to attempt before any Gamma or Poisson draw occurred.

## A first read on channel structure at the `S2` boundary

Looking at the admitted merchants by channel:

### `CNP`

- merchants: `1,228`
- mean `S1` branch probability: `0.536866`
- mean `mu`: `14.659459`
- mean `phi`: `13.602407`
- mean realized `n_outlets`: `14.846091`

### `CP`

- merchants: `4,589`
- mean `S1` branch probability: `0.655147`
- mean `mu`: `21.605635`
- mean `phi`: `11.826286`
- mean realized `n_outlets`: `21.438440`

This is already a useful structural clue.

`CP` merchants are more likely to enter `S2` in the first place, and once admitted, they also sit on a materially higher NB mean surface than `CNP` merchants. But the dispersion lane is slightly higher for `CNP`, which is consistent with the sign pattern in the active `beta_phi` channel terms.

So even at the authority block, we can already see that the count world is not a simple “all admitted merchants now share one outlet-count law.” The law is still structurally segmented by channel.

## What the GDP term is actually doing here

One question I wanted to settle was whether GDP is still acting like a broad count-level driver in `S2`, or whether it has moved into a more specific role.

The contract answer says:

- GDP is **not** part of the mean lane
- GDP **is** part of the dispersion lane

The reconstructed run agrees with that.

Across the admitted merchants:

- correlation of `ln(gdp_pc)` with `mu`: about `-0.0125`
- correlation of `ln(gdp_pc)` with `phi`: about `0.2371`

This should not be over-read as a causal estimate, because MCC and channel also move both parameters. But it does line up with the actual authored law:

- GDP is functionally absent from `\mu`
- GDP is structurally present in `\phi`

So the role of GDP in `S2` is narrower and more specific than its role in `S1`. It is no longer part of the branch gate’s broad predictor basis. It is now a direct contributor to **dispersion posture** within the admitted multi-site world.

## What `S2` owns at this boundary, and what it does not

At the end of this authority investigation, the clean ownership picture is:

### `S2` does own

- the admitted multi-site count world
- the deterministic `mu` / `phi` parameter context for admitted merchants
- the Gamma-Poisson attempt streams
- the final accepted outlet count `N` in `nb_final`

### `S2` does not own

- the branch decision itself
  - this belongs to `S1`
- the merchant catalog
  - this belongs to `S0`
- a persisted `S2` runtime design parquet
  - the authority has to be reconstructed from the sealed merchant and GDP inputs plus the active policy bundles

That last point is important for how we continue the investigation. In the notebook, we should not go looking for a missing `S2` feature table as though the run is incomplete. The state’s persisted authority is the event surface, while the deterministic context has to be rebuilt.

## Current conclusions from the entry-and-authority block

The main conclusions are:

1. **The `S1 -> S2` gate is clean.**
   Every `S2` merchant is an `S1` multi-site merchant, and no single-site merchant leaks into `S2`.

2. **The active authority is sealed and singular.**
   The relevant `S2` run surfaces all share one lineage identity on `seed`, `parameter_hash`, `manifest_fingerprint`, and `run_id`.

3. **`S2` is governed by two different deterministic laws.**
   - `beta_mu` in `hurdle_coefficients.yaml` governs the mean lane
   - `beta_phi` in `nb_dispersion_coefficients.yaml` governs the dispersion lane

4. **GDP has a different role in `S2` than in `S1`.**
   It does not enter the mean lane, and it is not represented as a bucket one-hot. It enters `S2` as a continuous `ln(gdp_pc)` scalar in the dispersion lane.

5. **The emitted `nb_final.mu` and `nb_final.dispersion_k` are fully explained by the sealed authority surfaces.**
   Recomputing them from merchant descriptors, GDP, and the two coefficient bundles matches the emitted values to machine precision.

6. **There is no persisted `S2` design matrix.**
   So the correct investigative posture for `S2` is to treat the event streams as the authoritative persisted surface and rebuild the deterministic context when needed.

## What this sets up next

With entry and authority now fixed, the next workbench block should move into the stochastic realization itself:

- how `gamma_component` and `poisson_component` decompose the NB sampler
- how acceptance to `N >= 2` behaves in practice
- how `nb_final` authors the realized total outlet-count world

That is where the deeper `S2` EDA begins.
