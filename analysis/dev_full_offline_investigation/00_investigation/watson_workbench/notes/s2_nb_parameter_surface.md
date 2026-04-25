# `1A.S2` Investigation: Deterministic NB Construction

## Why this block matters

The previous note fixed the boundary into `S2`: who enters, which files govern the state, and whether the emitted `nb_final` rows really belong to the admitted `S1` multi-site branch.

This note moves one step deeper.

Before `S2` becomes a stochastic Gamma-Poisson world, it is first a **deterministic parameter-construction world**. For each admitted merchant, the engine builds:

$$
\mu_m = \exp\!\left(\beta_\mu^\top x^{(\mu)}_m\right)
$$

where:

- `m` = merchant
- `x^{(\mu)}_m` = mean-lane design vector for merchant `m`
- `\beta_\mu` = governed NB-mean coefficient vector
- `\mu_m` = expected multi-site outlet count before stochastic realization

and

$$
\phi_m = \exp\!\left(\beta_\phi^\top x^{(\phi)}_m\right)
$$

where:

- `x^{(\phi)}_m` = dispersion-lane design vector for merchant `m`
- `\beta_\phi` = governed NB-dispersion coefficient vector
- `\phi_m` = dispersion / shape parameter controlling the spread of the count world

The point of this block is to understand that deterministic law itself:

- what exactly goes into `x^{(\mu)}` and `x^{(\phi)}`
- how much structure is coming from MCC, channel, and GDP
- what kind of `mu`/`phi` surface the admitted merchant world is being placed on before the first Gamma draw happens

## Working plan used in this investigation

I approached the deterministic block in four steps:

1. **Pin the contract definition**
   Re-read `S2.1` and `S2.2` to fix the exact mathematical form of `x^{(\mu)}`, `x^{(\phi)}`, `\beta_\mu`, and `\beta_\phi`.
2. **Rebuild the parameter surface**
   Reconstruct `eta_mu`, `eta_phi`, `mu`, and `phi` for the admitted merchants from the sealed merchant/GDP inputs and the active coefficient bundles.
3. **Decompose the contributions**
   Split the deterministic law into intercept, MCC, channel, and GDP pieces to see where heterogeneity is really coming from.
4. **Read the resulting surface**
   Quantify the heterogeneity and interpret what sort of count world the deterministic law is setting up for the stochastic sampler.

## Core references

Contract and decision trail:

- [`docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md)
- [`docs/model_spec/data-engine/implementation_maps/segment_1A.build_plan.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.build_plan.md)
- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

Authority surfaces:

- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)
- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/nb_dispersion_coefficients.yaml)
- [`reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet)
- [`reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet`](../../../../../reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)

Supporting note from the previous block:

- [`s2_nb_authority_and_entry.md`](./s2_nb_authority_and_entry.md)

Scratch analysis used for the derived checks in this note:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_s2_deterministic_nb_construction.py`](../scratch/analyze_s2_deterministic_nb_construction.py)

## The deterministic `S2` law the contract actually defines

The contract is very explicit that `S2` does **not** score one generic design vector.

It defines two related but different design vectors:

$$
x^{(\mu)}_m = [1,\ \Phi_{\mathrm{mcc}}(m),\ \Phi_{\mathrm{ch}}(m)]^\top
$$

where:

- `1` = intercept
- `\Phi_{\mathrm{mcc}}(m)` = MCC one-hot block
- `\Phi_{\mathrm{ch}}(m)` = channel one-hot block

and

$$
x^{(\phi)}_m = [1,\ \Phi_{\mathrm{mcc}}(m),\ \Phi_{\mathrm{ch}}(m),\ \ln g_c]^\top
$$

where:

- `g_c` = GDP per capita of the merchant’s home country `c`
- `\ln g_c` = the natural log GDP term included only in the dispersion lane

That means the two lanes answer different questions:

- the **mean lane** asks how large the merchant should be, on average, once it is already admitted into the multi-site branch
- the **dispersion lane** asks how much spread or variability that merchant’s count law should carry around that mean

This is not a cosmetic distinction. It means GDP is not a broad size driver in `S2`. GDP is a **dispersion driver** in `S2`.

## A practical constraint discovered while investigating

There is no persisted `S2` design matrix or `S2` parameter parquet in the run output tree.

So the deterministic NB construction has to be investigated by reconstructing the runtime context from:

- the admitted merchants from `nb_final`
- the merchant descriptors in `transaction_schema_merchant_ids`
- the home-country GDP surface
- `beta_mu` from `hurdle_coefficients.yaml`
- `beta_phi` from `nb_dispersion_coefficients.yaml`

This matters because it changes the right posture. We are not reading a missing artefact. We are rebuilding the deterministic authority surface the state used in memory.

## Coverage and vocabulary closure

The reconstructed deterministic surface is complete for the admitted merchants:

- admitted merchants: `5,817`
- missing mean-lane MCC terms: `0`
- missing mean-lane channel terms: `0`
- missing dispersion-lane MCC terms: `0`
- missing dispersion-lane channel terms: `0`
- missing GDP terms: `0`

The admitted merchant population spans:

- distinct entrant MCCs: `287`
- entrant channels:
  - `CP`: `4,589`
  - `CNP`: `1,228`

So there is no vocabulary drift between the admitted run population and the active coefficient bundles.

## The active mean lane

The active `beta_mu` bundle has:

- `len(beta_mu) = 293`
- `|dict_mcc| = 290`
- `dict_ch = ["CP", "CNP"]`

So the mean lane is exactly:

```text
1 intercept + 290 MCC terms + 2 channel terms
```

The active mean-lane intercept is:

- `1.7814957339620379`

The active channel terms are:

- `CP = +1.128766904935765`
- `CNP = +0.7572450117988003`

That means the channel gap inside `eta_mu` is about:

- `0.3715`

before any MCC effect is applied.

The reconstructed mean-lane component summaries across the admitted merchants are:

### `eta_mu` intercept

- constant at `1.7815`

### `eta_mu` MCC contribution

- mean: `0.0427`
- std: `0.4753`
- min: `-1.4481`
- max: `+1.3755`

### `eta_mu` channel contribution

- mean: `1.0503`
- std: `0.1516`
- min: `0.7572`
- max: `1.1288`

### `eta_mu` total

- mean: `2.8745`
- std: `0.4990`
- min: `1.0907`
- max: `4.2858`

This is the first important deterministic result.

The mean lane is not dominated by one trivial term. The intercept sets the baseline, but the MCC block contributes the largest spread, while the channel block adds a consistent level shift on top of that. The correlation of the MCC contribution with final `mu` is about `0.908`, while the channel contribution correlates with `mu` at about `0.255`.

So the main heterogeneity in expected outlet count comes from the MCC surface, with channel acting as a strong but coarser offset.

## The active dispersion lane

The active `beta_phi` bundle has:

- `len(beta_phi) = 294`
- `|dict_mcc| = 290`
- `dict_ch = ["CP", "CNP"]`

So the dispersion lane is exactly:

```text
1 intercept + 290 MCC terms + 2 channel terms + 1 ln(GDP) term
```

The active dispersion-lane intercept is:

- `2.2024682328784246`

The active channel terms are:

- `CP = -0.07`
- `CNP = +0.07`

The active GDP slope is:

- `ln(gdp_pc)` coefficient = `+0.03`

The reconstructed dispersion-lane component summaries across the admitted merchants are:

### `eta_phi` intercept

- constant at `2.2025`

### `eta_phi` MCC contribution

- mean: `0.0091`
- std: `0.1197`
- min: `-0.3663`
- max: `+0.3448`

### `eta_phi` channel contribution

- mean: `-0.0404`
- std: `0.0571`
- min: `-0.0700`
- max: `+0.0700`

### `eta_phi` GDP contribution

- mean: `0.3210`
- std: `0.0334`
- min: `0.1678`
- max: `0.3725`

### `eta_phi` total

- mean: `2.4921`
- std: `0.1368`
- min: `2.0487`
- max: `2.9538`

This surface has a very different shape from the mean lane.

The dispersion law is much tighter. The intercept dominates the level, the MCC block still provides the strongest merchant-specific spread, and the GDP term provides a broad macroeconomic lift whose range is comparable to the channel gap. The GDP contribution is not enormous, but it is also not negligible. It is part of the authored dispersion posture in a visible way.

The correlations to final `phi` make the hierarchy clear:

- MCC contribution to `phi`: `0.867`
- channel contribution to `phi`: `0.428`
- GDP contribution to `phi`: `0.237`

So GDP does matter, but within this deterministic law it is not the main source of merchant-to-merchant dispersion heterogeneity. MCC remains the stronger structuring force.

## The parameter surface is exactly the one echoed by `nb_final`

Rebuilding the deterministic surface from the active bundles and sealed merchant/GDP inputs gives:

- max absolute difference between recomputed `mu` and emitted `nb_final.mu`: `2.13e-14`
- max absolute difference between recomputed `phi` and emitted `nb_final.dispersion_k`: `1.07e-14`

So the deterministic construction we are describing here is not theoretical. It is the exact law that the emitted `nb_final` rows are echoing in this run.

## What kind of parameter world this deterministic law creates

Across the admitted merchants, the resulting parameter world is:

### `mu`

- mean: `20.1393`
- median: `17.6956`
- std: `11.1278`
- min: `2.9763`
- max: `72.6585`

### `phi`

- mean: `12.2012`
- median: `12.0554`
- std: `1.6941`
- min: `7.7577`
- max: `19.1786`

The contrast between these two surfaces is very telling.

The mean lane is intentionally broad:

- `CV(mu) = 0.5525`
- `P95/P05(mu) = 5.1220`

The dispersion lane is intentionally much tighter:

- `CV(phi) = 0.1388`
- `P95/P05(phi) = 1.5760`

That lines up directly with the remediation posture recorded in the build plan for `S2`:

- restore count-level realism through the NB mean path
- restore dispersion heterogeneity through `beta_phi`
- avoid the earlier near-constant `phi` pathology

The current run’s `phi` heterogeneity also sits inside the build-plan target bands for the accepted remediation posture:

- `CV(phi)` target band: `0.05 to 0.20`
- `P95/P05(phi)` target band: `1.25 to 2.0`

So the deterministic dispersion world is not only heterogeneous; it is heterogeneous at roughly the level the remediation program was explicitly aiming for.

## Channel read of the deterministic surface

By channel, the deterministic world looks like this:

### `CNP`

- merchants: `1,228`
- mean `eta_mu`: `2.5803`
- mean `mu`: `14.6595`
- mean `eta_phi`: `2.6034`
- mean `phi`: `13.6024`
- mean GDP contribution to `eta_phi`: `0.3221`

### `CP`

- merchants: `4,589`
- mean `eta_mu`: `2.9532`
- mean `mu`: `21.6056`
- mean `eta_phi`: `2.4624`
- mean `phi`: `11.8263`
- mean GDP contribution to `eta_phi`: `0.3207`

This is a strong deterministic contrast.

`CP` merchants are being placed on a materially higher expected count surface than `CNP` merchants, but on a somewhat lower dispersion surface. So the current count world is not just saying “CP merchants are larger.” It is also saying “CNP merchants are slightly more dispersed around their lower expected size.”

This is one of the clearest signs that the engine is authoring a structured count world rather than a generic one.

## GDP read of the deterministic surface

To isolate the GDP role a bit more, I split the admitted merchants into GDP quintiles.

Across those quintiles:

- the mean GDP contribution to `eta_phi` rises steadily from about `0.2695` in the lowest quintile to `0.3614` in the highest quintile
- mean `phi` rises correspondingly from about `11.54` to `12.65`
- mean `mu` does **not** rise monotonically with GDP

This is exactly what the contract says should happen.

GDP in `S2` is not the main driver of count level. It is a driver of count spread. It helps shape how variable the outlet-count law is once the merchant has already entered the multi-site branch.

## The MCC blocks are the strongest merchant-specific source of structure

The extremes in the MCC coefficient blocks show just how much structure the deterministic law can impose before any sampling.

### Lowest mean-lane MCC terms

- `8011 = -1.4481`
- `7299 = -1.1626`
- `2741 = -1.1450`

### Highest mean-lane MCC terms

- `5411 = +1.1797`
- `5441 = +1.3167`
- `5542 = +1.3755`

### Lowest dispersion-lane MCC terms

- `8011 = -0.3663`
- `7299 = -0.2944`
- `2741 = -0.2900`

### Highest dispersion-lane MCC terms

- `5411 = +0.2955`
- `5441 = +0.3299`
- `5542 = +0.3448`

So the same broad pattern holds in both lanes:

- MCC is the main merchant-level differentiator
- channel gives a coarser structural offset
- GDP only enters the dispersion lane

The important thing is not the individual MCC labels by themselves, but the fact that the deterministic law is not flat inside the merchant universe. It has enough coefficient spread to create a structured parameter surface well before any randomness enters.

## How this deterministic law came about

The metadata inside the active bundles helps explain why the current run looks the way it does.

The active `beta_mu` bundle records a `P4.R4A` remediation note with:

- `change = beta_mu_non_intercept_downscale_midpoint_pass`
- `non_intercept_scale = 0.92`
- `parent_bundle = version=2026-02-14/20260214T125000Z`

The active `beta_phi` bundle records:

- `change = carry_forward_dispersion_bundle_for_home_support_lane`
- `gdp_slope = 0.03`
- `target_median_phi = 12.0`
- `parent_bundle = version=2026-02-12/20260212T200823Z`

This is analytically useful.

It tells us the current deterministic `S2` world is **not** a naive untouched baseline. The mean lane and dispersion lane were treated differently:

- the mean lane was still being tuned in a controlled reopen posture
- the dispersion lane was intentionally carried forward as a stabilized authority surface

That aligns with the shape we now see:

- `mu` is broad and more heterogeneous
- `phi` is narrower but still properly heterogeneous, not near-constant

## Current conclusions from the deterministic block

The main conclusions are:

1. **`S2` is governed by two genuinely different deterministic laws.**
   The mean lane uses MCC and channel only. The dispersion lane uses MCC, channel, and `ln(gdp_pc)`.

2. **The mean lane is the broader heterogeneity surface.**
   `mu` varies far more across admitted merchants than `phi`, and most of that spread is coming from the MCC block, with channel adding a strong coarser shift.

3. **The dispersion lane is narrower but meaningfully structured.**
   `phi` is not flat. Its heterogeneity is real, sits within the accepted remediation target bands, and is driven mainly by MCC, then channel, then GDP.

4. **GDP’s role in `S2` is specific rather than general.**
   It does not act as a broad count-level driver. It contributes to the dispersion posture only.

5. **The deterministic parameter surface is exactly the one echoed by `nb_final`.**
   Recomputed `mu` and `phi` match the emitted values to machine precision, so this note is describing the actual law used by the run.

6. **The current run still carries remediation history inside the active law.**
   The mean lane was moved in a controlled reopen posture while the dispersion lane was largely carried forward, and the resulting parameter surface reflects that design decision.

## What this sets up next

With the deterministic parameter surface fixed, the next block should move into the stochastic realization:

- how Gamma and Poisson are composed per attempt
- how the rejection rule `N >= 2` behaves in practice
- how the accepted `nb_final` world differs from the deterministic `mu` / `phi` world it starts from

That is where `S2` stops being a parameter surface and becomes an authored count world.
