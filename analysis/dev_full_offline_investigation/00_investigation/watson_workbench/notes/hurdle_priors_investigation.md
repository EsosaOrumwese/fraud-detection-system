# `hurdle_simulation.priors.yaml` Investigation

## Why this object matters

If `hurdle_coefficients.yaml` is the sealed coefficient bundle that the engine consumes, then `hurdle_simulation.priors.yaml` is part of the upstream authored world that explains how that bundle first came into existence.

This matters because the active hurdle bundle does not come from observed production transactions. It comes from an offline simulated training route. So if we want to understand how the coefficients were born, we need to understand what the priors were instructing the offline trainer to create.

The active priors file is:

- [`config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml`](../../../../../config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml)

## What this file is

This is not a generic machine-learning hyperparameter file. It is a governed simulation specification for the offline hurdle export process.

It defines:

- the RNG posture of the simulation
- the calibration targets the synthetic corpus should satisfy
- the noise injected into the synthetic merchant-level world
- the clamps that keep simulated `pi`, `mu`, and `phi` inside allowed corridors
- the handcrafted structural offsets for:
  - hurdle branching
  - NB mean
  - dispersion

So the priors file is better thought of as an **authored synthetic world recipe** than as a narrow model-fit settings file.

## Where it is used

The priors file is consumed by:

- [`scripts/build_hurdle_exports.py`](../../../../../scripts/build_hurdle_exports.py)

That script:

1. loads the priors YAML
2. loads the merchant parquet, GDP, bucket map, and ISO canonical
3. builds a simulated hurdle world and NB-count world
4. writes the sealed training datasets:
   - `logistic.parquet`
   - `nb_mean.parquet`
5. fits the coefficient vectors
6. exports the governed hurdle / dispersion bundles

This is visible directly in the script:

- priors are loaded near the top of the execution path
- the calibration and simulation sections are pulled out explicitly
- the synthetic logistic and NB targets are then generated before fitting

## The training lineage the priors point to

The active bundle's metadata points back to:

- [`artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/manifest.json`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/manifest.json)

That manifest records:

- the priors path and digest
- the merchant parquet path and digest
- GDP and GDP bucket map paths and digests
- ISO canonical path and digest
- the simulation seed
- the two emitted training datasets:
  - `logistic.parquet`
  - `nb_mean.parquet`
- the fitted-world summary metrics

So, in lineage terms, the priors file is not just conceptually connected to the bundle. It is explicitly recorded in the training manifest that the bundle points back to.

## What are the simulated hurdle world and NB-count world?

The phrase "simulated hurdle world" means the synthetic merchant-level branch world created for training the `S1` hurdle model.

In that world:

- every merchant from the merchant parquet is present
- each merchant is given the same core descriptors the hurdle model will later understand:
  - `mcc`
  - `channel`
  - `home_country_iso`
  - `gdp_bucket`
  - `ln_gdp_pc_usd_2015`

The branch probability is created in stages.

First, the priors assign each merchant a latent branch tendency. That latent tendency is the hurdle logit, usually written as `eta`:

$$
\eta_m =
\text{base\_logit}
+ \Delta_{\text{channel}(m)}
+ \Delta_{\text{bucket}(m)}
+ \Delta_{\text{MCC}(m)}
+ \epsilon_{\text{logit},m}
$$

This `eta` is not yet a probability. It is a log-odds score on the real number line. Higher `eta` means stronger synthetic tendency toward the multi-site branch; lower `eta` means stronger synthetic tendency toward the single-site branch.

Second, the script maps `eta` through the logistic sigmoid:

$$
\pi_m^{raw} = \sigma(\eta_m) = \frac{1}{1 + e^{-\eta_m}}
$$

That sigmoid is what turns the unrestricted latent tendency into a value between `0` and `1`.

Third, the resulting probability is clipped to the configured `pi` corridor:

$$
\pi_m = \mathrm{clip}(\pi_m^{raw},\ \pi_{\min},\ \pi_{\max})
$$

For the active priors, this corridor is `[0.01, 0.75]`. This keeps the simulated training world away from merchants that are effectively impossible or certain to be multi-site.

Finally, a deterministic RNG draw turns that probability into the synthetic training label:

$$
y_{\text{hurdle},m} = \mathbf{1}\{u_m < \pi_m\}
$$

So the simulated hurdle world is the training-time answer to:

> If this merchant universe had realistic single-site vs multi-site behaviour, which merchants would be labelled multi-site in the synthetic corpus?

The output surface for this world is:

- [`logistic.parquet`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/logistic.parquet)

It has one row per merchant and contains the synthetic target:

- `y_hurdle`

That `y_hurdle` is what the offline fitter uses as the training label for the hurdle coefficients.

The phrase "NB-count world" means the synthetic outlet-count world created for training the `S2` count model.

In that world:

- only merchants that landed on the simulated multi-site branch receive a count target
- the retained merchant descriptors are the same core descriptors carried by the hurdle training surface:
  - `mcc`
  - `channel`
  - `home_country_iso`
  - `gdp_bucket`
  - `ln_gdp_pc_usd_2015`
- the priors assign each such merchant a synthetic count posture using:
  - base log mean
  - channel offsets
  - MCC offsets
  - merchant-level log-mu noise
  - dispersion structure

This is not another `pi` lane. The NB-count world is not asking "does this merchant become multi-site?" That question has already been answered by `y_hurdle`.

Instead, the NB-count world asks: given that this merchant is already on the synthetic multi-site branch, how large should its outlet count be?

The NB mean lane therefore builds a log-scale mean:

$$
   \log \mu_m =
   \text{base\_log\_mean}
   + \Delta_{\text{channel}(m)}
   + \Delta_{\text{MCC}(m)}
   + \epsilon_{\log \mu,m}
$$

and maps it to a positive mean:

$$
   \mu_m = \exp(\log \mu_m)
$$

The dispersion lane builds a log-scale dispersion:

$$
   \log \phi_m =
   \text{base\_log\_phi}
   + s_{\text{gdp}}\log(g_m)
   + \Delta_{\text{channel}(m)}
   + \Delta_{\text{MCC}(m)}
   + \epsilon_{\log \phi,m}
$$

and maps it to a positive dispersion:

$$
   \phi_m = \exp(\log \phi_m)
$$

Both `mu` and `phi` are then clipped to their configured corridors. The script uses these quantities to sample a zero-truncated NB-style count target, `y_nb`.

The output surface for this world is:

- [`nb_mean.parquet`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/nb_mean.parquet)

It contains the synthetic target:

- `y_nb`

That `y_nb` is what the offline fitter uses as the training target for `beta_mu`, the NB-mean lane carried by `hurdle_coefficients.yaml`.

So the two worlds are related but not identical:

- the simulated hurdle world trains **who becomes multi-site**
- the NB-count world trains **how large the multi-site merchant becomes**
- the NB-count world keeps the same merchant context columns for lineage and analysis, but `beta_mu` itself is fit from the narrower NB-mean design: intercept, MCC one-hot, and channel one-hot
- `pi` belongs to the hurdle branch lane; the NB-count world depends on the hurdle result for admission, but its own synthetic quantities are `mu`, `phi`, and `y_nb`

This is why the priors file defines more than one kind of structure. It needs one authored structure for the branch decision and another authored structure for the multi-site count behaviour.

## What the priors declare

### 1. RNG posture

The file fixes:

- `algorithm = philox2x64-10`
- `seed = 9248923`

So the synthetic training world is itself deterministic and replayable, not a vague ad hoc simulation.

### 2. Calibration targets

The priors set these training-world targets:

- `mean_pi_target = 0.16`
- `mean_mu_target_multi = 6.5`
- `median_phi_target = 45.0`

And it also supplies bracket ranges for solving the base levels:

- `base_logit`
- `base_log_mean`
- `base_log_phi`

This tells us the synthetic corpus is not generated by fixed arbitrary constants only. The export script searches inside these brackets so that the simulated world lands near the desired merchant-level averages.

### 3. Merchant-level noise

The priors inject per-merchant randomness into:

- logit
- log-mu
- log-phi

with standard deviations:

- `per_merchant_logit_sd = 0.38`
- `per_merchant_log_mu_sd = 0.22`
- `per_merchant_log_phi_sd = 0.18`

So the training world is not just deterministic offsets by MCC / channel / bucket. It is an offset structure plus merchant-level noise.

### 4. Corridor clamps

The priors clamp the synthetic outputs:

- `pi` to `[0.01, 0.75]`
- `mu` to `[4.0, 35.0]`
- `phi` to `[12.0, 80.0]`

This is a strong design decision. It means the simulated world is prevented from producing very low or very high values even before the later fit/export process. So the coefficients are being fit to a bounded synthetic world, not to an unrestricted one.

### 5. Authored structure for the hurdle lane

The hurdle section provides:

- `base_logit = -1.15`
- channel offsets:
  - `CP = 0.0`
  - `CNP = -0.55`
- GDP bucket offsets:
  - `1 = -0.60`
  - `2 = -0.30`
  - `3 = 0.0`
  - `4 = 0.30`
  - `5 = 0.60`
- MCC range offsets
- specific MCC overrides

This is the first major authored shape for the branch world.

### 6. Authored structure for the NB-mean lane

The NB mean section provides:

- `base_log_mean = 0.70`
- channel offsets:
  - `CP = 0.05`
  - `CNP = -0.20`
- MCC range offsets
- specific MCC overrides

### 7. Authored structure for the dispersion lane

The dispersion section provides:

- `base_log_phi = 2.85`
- `gdp_log_slope = 0.08`
- channel offsets
- MCC range offsets
- specific MCC overrides
- MOM settings (`epsilon`, `n_min`, `cell_weight_rule`)

So the priors file is really defining three synthetic sub-worlds at once:

- hurdle branch world
- NB mean world
- dispersion world

## What the export script does with the priors

The authoring script follows a fairly concrete sequence.

### Step 1. Build the merchant-enriched simulation frame

The script loads:

- merchant parquet
- GDP
- GDP bucket map
- ISO canonical

Then it enriches the merchant frame with:

- `channel` normalized to `CP` / `CNP`
- GDP per capita
- GDP bucket
- log GDP per capita

This means the priors are not operating in a vacuum. They are applied on top of the actual merchant universe snapshot.

### Step 2. Build deterministic dictionaries

The script then fixes:

- `dict_mcc`
- `dict_ch = ["CP", "CNP"]`
- `dict_dev5 = [1,2,3,4,5]`

This is the structural bridge from merchant parquet to coefficient bundle.

### Step 3. Apply authored offsets + merchant noise

The script maps:

- MCC offsets
- MCC range offsets
- channel offsets
- bucket offsets

and combines them with merchant-level noise.

At this point, the simulated world is being authored in the exact dimensions the coefficient bundle will later freeze.

### Step 4. Calibrate the base levels

If calibration is enabled, the script numerically solves for:

- `base_logit`
- `base_log_mean`
- `base_log_phi`

inside the configured brackets, so that the synthetic world lands near:

- target mean `pi`
- target mean `mu` on the multi-site-weighted world
- target median `phi`

The manifest confirms the resulting solved values for the January training run:

- `base_logit ≈ -1.7515`
- `base_log_mean ≈ 1.6285`
- `base_log_phi ≈ 2.9114`

This is important because these are not the same as the raw prior defaults. The raw prior defaults are starting posture; the solved calibrated values are what the synthetic training world actually used.

### What the calibration targets are really doing

The three calibration targets are not arbitrary thresholds stapled onto the file. They are the control points that tell the script what kind of synthetic world to solve for.

- `mean_pi_target`
  - sets the average hurdle propensity of the synthetic merchant world
- `mean_mu_target_multi`
  - sets the average scale of the synthetic outlet-count world
- `median_phi_target`
  - sets the typical dispersion level of that synthetic count world

The bracket values:

- `base_logit: [-10, 2]`
- `base_log_mean: [-2, 4]`
- `base_log_phi: [1, 5]`

are there because the script does not trust the starting constants blindly. It performs bounded search inside those ranges and solves the final baselines numerically.

So these bracket ranges are search corridors, not final parameter claims.

### Why these particular target values

The repo trail shows that the current `0.16 / 6.5 / 45.0` posture is not an arbitrary trio.

First, the authoring guide gives lower example-style targets such as:

- `mean_pi_target = 0.12`
- `mean_mu_target_multi = 5.0`
- `median_phi_target = 22.0`

See:

- [`docs/model_spec/data-engine/layer-1/specs/data-intake/1A/hurdle_simulation.priors_authoring-guide.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/data-intake/1A/hurdle_simulation.priors_authoring-guide.md)

Second, the `2025-12-31` logbook shows the values being pushed upward in response to corridor failures:

- `mean_mu_target_multi = 6.0`, `median_phi_target = 30.0`
- then `8.0`, `40.0`
- then `9.0`, `45.0`
- `clamps.mu.min` raised from `3.0` to `4.0`

with the explicit reason being belt-and-braces corridor pressure.

See:

- [`docs/logbook/12-2025/2025-12-31.md`](../../../../../docs/logbook/12-2025/2025-12-31.md)

Third, the evidence note then describes the settled priors as a data-informed retune aligned to the current merchant world:

- `mean_pi_target = 0.16`
- `mean_mu_target_multi = 6.5`
- `median_phi_target = 45.0`

See:

- [`docs/model_spec/data-engine/layer-1/specs/data-intake/evidence.md`](../../../../../docs/model_spec/data-engine/layer-1/specs/data-intake/evidence.md)

So the best reading is:

- guide examples were the lower conceptual baseline
- corridor failures forced an upward late-December escalation
- the final `6.5 / 45.0` posture is a moderated settled value rather than the peak escalation state

### Bounded calibration check

I reproduced the script's calibration mechanics against the current merchant universe and current priors structure.

Using lower guide-style targets:

- `mean_pi_target = 0.12`
- `mean_mu_target_multi = 5.0`
- `median_phi_target = 22.0`

the solved baselines come out roughly as:

- `base_logit ≈ -2.1049`
- `base_log_mean ≈ 1.3027`
- `base_log_phi ≈ 2.1925`

Using the current priors:

- `mean_pi_target = 0.16`
- `mean_mu_target_multi = 6.5`
- `median_phi_target = 45.0`

the solved baselines are:

- `base_logit ≈ -1.7515`
- `base_log_mean ≈ 1.6285`
- `base_log_phi ≈ 2.9114`

And if the mean target is pushed further upward while the others stay fixed:

- `mean_mu_target_multi = 9.0`

the solved mean baseline rises again:

- `base_log_mean ≈ 1.9615`

So these targets directly shift the center of mass of the synthetic world. They are not cosmetic metadata.

### Step 5. Generate synthetic labels and counts

The script computes:

- merchant-level `pi`
- hurdle draws and `y_hurdle`
- merchant-level `mu`
- merchant-level `phi`
- zero-truncated NB counts for the multi-site merchants

and writes:

- [`logistic.parquet`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/logistic.parquet)
- [`nb_mean.parquet`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/nb_mean.parquet)

Those datasets look as expected:

- `logistic.parquet`
  - `10,000` rows
  - one row per merchant
  - includes `y_hurdle`
- `nb_mean.parquet`
  - `1,609` rows
  - only the merchants that landed on the synthetic multi-site branch
  - includes `y_nb`

This means the active training lineage does indeed reflect a synthetic world where roughly `16%` of merchants were multi-site, which matches the training target rather than the active run's current `S1` split.

## The corridor logic behind the clamps and the higher `phi` target

The export script runs a belt-and-braces selfcheck after fitting the bundles.

That selfcheck enforces:

- `rho_hat <= 0.055`
- `p_rej < 0.25`
- `infl <= 1.20`
- mean `pi` within `[0.05, 0.30]`
- `q90_mu` within `[3.0, 40.0]`
- `median_mu_over_phi >= 0.02`

This matters because the late-December tuning trail is clearly reacting to those checks.

So the move to:

- `median_phi_target = 45.0`
- `clamps.mu.min = 4.0`

is not a stylistic preference. It is part of keeping the synthetic count world away from a low-count, high-rejection regime that would fail corridor checks.

In other words:

- higher `phi` helps keep the dispersion world realistic without creating pathological rejection inflation
- the `mu` floor helps avoid too much mass near `N <= 1`

Those choices are corridor-management choices.

## One implementation nuance we should not miss

The authoring guide describes calibration in a thresholded multi-site style, for example using merchants with `pi >= 0.5` for some steps.

The current script does not implement calibration that literally.

What it actually does:

- solves `base_logit` from the mean of `pi`
- solves `base_log_mean` from a **pi-weighted** mean of `mu`
- solves `base_log_phi` from a **pi-weighted** median of `phi`

Only later, in the belt-and-braces selfcheck, does it switch to:

- `pi_mask = pi_eval >= 0.5`

for metrics such as:

- `q90_mu`
- `median_mu_over_phi`

So there is a real guide-vs-implementation nuance:

- the guide describes one calibration posture
- the script currently calibrates with weighted global surfaces, then validates with the `pi >= 0.5` segment

That does not automatically make the script wrong, but it does mean the current implementation is more specific than the guide wording.

## One documentary wrinkle

The evidence note says the priors were calibrated to the current `50k` merchant universe.

But the active training manifest we are actually following is built on the `2026-01-03` merchant parquet with `10,000` merchants.

So either:

- the evidence note is describing a nearby but different lineage point
- or it is lagging the active training world we are now inspecting

That is a small but real documentation drift.

## How the priors affect our interpretation of the coefficient bundle

### 1. They explain the original sign structure

The priors clearly push the hurdle world in particular directions:

- `CNP` is more suppressive than `CP`
- GDP buckets rise from `1` to `5`
- some MCC bands are encouraged, others discouraged

That same qualitative structure survives into the active hurdle bundle:

- active hurdle channel block:
  - `CP = -0.2875`
  - `CNP = -0.8521`
- active hurdle GDP bucket block rises monotonically from bucket `1` to `5`

So the priors do explain the qualitative shape of the hurdle lane.

They explain the contour more than the final level. The active run kept the same broad directional structure, but later remediation changed where that contour sits vertically by altering the hurdle intercept.

### 2. They do **not** fully explain the active bundle numerically

This is the most important finding from this investigation.

The active run bundle is not numerically identical to the original January training export.

Comparing:

- [`config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/hurdle_coefficients.yaml)
- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)

shows:

- dictionaries unchanged
- `beta` not identical
- `beta_mu` not identical

Most importantly:

- only **one** hurdle coefficient changed between the original January export and the active February bundle
- that change is the hurdle intercept
- delta: `+2.2`

Concretely:

- original hurdle intercept: `-1.1395762619018373`
- active hurdle intercept: `1.060423738098163`

This exactly matches the `P1b` remediation metadata in the February bundle family:

- [`config/layer1/1A/models/hurdle/exports/version=2026-02-12/20260212T171900Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-12/20260212T171900Z/hurdle_coefficients.yaml)

which records:

- `change: hurdle_intercept_shift`
- `delta_intercept: 2.2`

And it matches the implementation notes:

- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

where the engine hardening trail explicitly says:

- mean hurdle probability around `0.16` was too low
- a `+2.2` hurdle intercept shift was chosen to move single-site share into the desired corridor

So the priors explain the original simulated hurdle world, but the active run's hurdle branch world has already been deliberately moved away from that original authoring point by a governed intercept correction.

### 3. They explain why the manifest summary and the active run can disagree

The January training manifest says:

- `mean_pi = 0.16`
- `rows_nb = 1609`

But the active run's `S1` world is much higher:

- active mean `pi ≈ 0.583`
- active multi-site count `5817`

This is not a contradiction once the remediation trail is understood.

What happened is:

1. priors authored the original simulated training world
2. the original export produced a low hurdle posture around the target `0.16`
3. later `P1b` remediation shifted the hurdle intercept by `+2.2`
4. that changed the active `S1` branch posture while keeping the rest of the hurdle block structure intact
5. later `P4.R4A` work then modified `beta_mu`, not `beta`

So the priors are foundational, but not final.

## What design decisions the priors reveal

The priors expose several strong design decisions:

### A. The hurdle world is intentionally macro-aware

GDP bucket is not incidental; it is deliberately built into the hurdle structure with an ordered ladder. This means multi-site propensity is authored to rise with macro-economic tier.

### B. Channel is treated as a structural branching feature

`CNP` is intentionally suppressed relative to `CP`. This is not discovered from downstream behaviour alone; it is explicitly authored at the simulation level.

### C. MCC semantics are partly smooth and partly hand-steered

The priors use both:

- range-based MCC offsets
- explicit MCC overrides

So the designer did not rely on a pure broad-brush category model. Certain merchant classes were intentionally singled out.

### D. The synthetic world is corridor-controlled

Because `pi`, `mu`, and `phi` are all clamped and calibrated, this is not an unconstrained generative model. It is a bounded realism authoring system.

### E. The bundle family is designed to be remediable

The later engine history shows that after the initial simulated authoring, the exported bundle can be reopened and adjusted in tightly controlled ways.

That means the true design is two-stage:

1. priors-driven simulation authoring
2. governed remediation on exported coefficients

## Current judgment

The priors file is important, but we need to use it correctly in interpretation.

What it does explain well:

- the original simulated design intent
- the qualitative shape of the coefficient lanes
- why GDP bucket, channel, and MCC all appear in the coefficient bundle
- why the training manifest has the targets it does

What it does **not** explain on its own:

- the exact active hurdle intercept in the current run
- the current active `S1` branch rate
- the final active `beta_mu` lane in the remediated February bundle

So the correct statement is:

- the priors explain the **authoring origin**
- the implementation/logbook trail explains the **active remediated posture**

Both are needed if we want to understand what this hurdle bundle is really doing in the current governed data world.

## What this changes in our reading of the hurdle bundle

Before this priors investigation, it was possible to read the active bundle as though it were simply "the training export."

That is no longer the right reading.

The right reading is:

- the active bundle is a descendant of a priors-authored synthetic training world
- the original qualitative shape comes from that priors world
- but the active run's numerical posture also reflects later engine-hardening interventions, beginning with the `+2.2` hurdle intercept shift and then later `beta_mu` remediation

That is the proper context for any further `S1` interpretation.
