# `rng_event_hurdle_bernoulli` Investigation

## Why this object matters

`rng_event_hurdle_bernoulli` is the first authoritative stochastic decision stream in Segment `1A`.

The priors explain how the synthetic training world was authored. The coefficient bundle explains the scoring law that the engine consumes. The design matrix is the runtime `X`. `hurdle_pi_probs` is a diagnostic probability cache.

But `rng_event_hurdle_bernoulli` is where the branch decision actually becomes real.

For each merchant, `S1` takes the scored multi-site probability, draws one keyed uniform, and decides whether that merchant becomes:

- single-site, with the downstream single-site route
- multi-site, with the downstream `S2` NB-count route

So this stream is not just another diagnostic table. It is the branch authority that determines which merchants are allowed to enter the multi-site side of the governed world.

## What this stream is

The active event stream is:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)

Its contract entry is:

- [`docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`](../../../../../docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml)

The contract describes it as Bernoulli draws per merchant for the hurdle decision. In practical terms, each row carries:

- lineage keys: `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`
- RNG identity: `module`, `substream_label`, before/after counters
- branch probability: `pi`
- random draw: `u`
- branch outcome: `is_multi`
- accounting fields: `draws`, `blocks`, `deterministic`

The reason this stream uses a Bernoulli draw is that `S1` is answering a binary branch question:

```text
Does this merchant enter the multi-site path?
```

There are only two valid outcomes:

```text
is_multi = true
is_multi = false
```

So the statistical object that fits the state is a Bernoulli trial:

```text
is_multi_m ~ Bernoulli(pi_m)
```

where:

- `m` is the merchant
- `pi_m` is the merchant's model-scored probability of being multi-site
- `is_multi_m = true` means the merchant enters the multi-site branch
- `is_multi_m = false` means the merchant remains on the single-site side

This is why the stream is not categorical, Poisson, negative binomial, normal, or lognormal. Those would answer different statistical questions. A categorical draw would make sense if the state had more than two branch choices. A count distribution would make sense if the state were asking how many outlets the merchant has. A continuous distribution would make sense for a continuous quantity. But `S1` is only the yes/no gate.

The count question comes later. Once `S1` has emitted `is_multi = true`, `S2` can ask how large the multi-site merchant should be. That is where the NB-count world becomes relevant. `S1` only decides whether the merchant crosses the hurdle at all.

The core decision is:

```text
is_multi_m = true  when u_m < pi_m
is_multi_m = false when u_m >= pi_m
```

where:

- `m` is the merchant
- `pi_m` is the logistic hurdle probability for merchant `m`
- `u_m` is the open-interval uniform draw for merchant `m`
- `is_multi_m` is the emitted branch outcome

This is the key distinction from `hurdle_pi_probs`: `hurdle_pi_probs` contains propensity, while `rng_event_hurdle_bernoulli` contains the realised decision.

## Where it sits in `1A.S1`

The implementation notes define `S1` as:

- load the run receipt and lineage keys
- load the parameter-scoped `hurdle_design_matrix`
- resolve the sealed `hurdle_coefficients.yaml`
- compute `eta = beta dot x_m`
- compute `pi = sigmoid(eta)`
- derive the merchant-keyed `hurdle_bernoulli` substream
- draw `u`
- emit `is_multi`
- append RNG trace rows
- validate the event stream by replay

The relevant implementation section is:

- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

That means the event stream should be read as the runtime endpoint of this chain:

```text
hurdle_simulation.priors.yaml
  -> synthetic training corpus
  -> hurdle_coefficients.yaml
  -> hurdle_design_matrix as runtime X
  -> pi
  -> keyed Bernoulli draw
  -> rng_event_hurdle_bernoulli
```

The branch authority is the final event stream, not the prior recipe and not the diagnostic probability table.

## Inputs and comparison surfaces used in this investigation

The checks below use:

- event stream: [`rng_event_hurdle_bernoulli`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- RNG trace: [`rng_trace_log.jsonl`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/trace/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/rng_trace_log.jsonl)
- runtime design surface: [`hurdle_design_matrix`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/hurdle_design_matrix/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/part-00000.parquet)
- diagnostic probability cache: [`hurdle_pi_probs`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/hurdle_pi_probs/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/part-00000.parquet)
- active coefficient bundle: [`hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)
- merchant seed universe: [`transaction_schema_merchant_ids.parquet`](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet)

The scratch script used for the derived checks is:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_rng_event_hurdle_bernoulli.py`](../scratch/analyze_rng_event_hurdle_bernoulli.py)

## Coverage and lineage checks

The stream has complete merchant coverage:

- event rows: `10,000`
- distinct event merchants: `10,000`
- design matrix rows: `10,000`
- diagnostic `pi` rows: `10,000`
- merchant seed rows: `10,000`
- missing design rows after join: `0`
- missing diagnostic `pi` rows after join: `0`
- missing merchant-country rows after join: `0`

The lineage surface is also singular:

- `seed = 42`
- `parameter_hash = 0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00`
- `manifest_fingerprint = 76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460`
- `run_id = a3bd8cac9a4284cd36072c6b9624a0c1`
- `module = 1A.hurdle_sampler`
- `substream_label = hurdle_bernoulli`

This matters because a mixed lineage would make the branch surface analytically unsafe. Here, the event stream is a single coherent run-scoped authority surface.

## Probability alignment checks

Before interpreting the branch outcomes, we need to know whether the `pi` written inside the event stream is the right `pi`.

This matters because `rng_event_hurdle_bernoulli` carries both:

- the probability used for the branch decision: `pi`
- the random draw that realises the branch decision: `u`

If the event `pi` were stale, rounded incorrectly, produced from a different coefficient bundle, or joined to the wrong merchant design row, then the later `is_multi` analysis would be misleading. We would be analysing a branch stream without knowing whether its probability surface actually came from the active S1 model.

So this check asks:

```text
Does the pi inside the event stream really come from the active hurdle coefficients
applied to the current runtime design matrix?
```

There are two comparison surfaces.

The first comparison is against `hurdle_pi_probs`. That file is the optional S0.7 diagnostic cache. It stores the same intended scored probability surface, but it is narrowed to float32 for storage. Because of that narrowing, we should expect tiny differences, not exact equality.

Observed comparison:

- max absolute event `pi` minus diagnostic `pi`: `2.98e-08`
- mean absolute event `pi` minus diagnostic `pi`: `1.26e-08`

This tells us the event probability and the diagnostic probability cache are effectively the same surface. The tiny gap is storage precision, not a meaningful modelling difference.

The second comparison is stronger. I recomputed `pi` directly from:

- the active `hurdle_coefficients.yaml`
- the runtime `hurdle_design_matrix`

That means rebuilding:

```text
eta_m = beta dot x_m
pi_m = sigmoid(eta_m)
```

and then comparing that recomputed `pi_m` to the `pi` written in the event row.

Observed comparison:

- max absolute event `pi` minus recomputed `pi`: `2.22e-16`
- mean absolute event `pi` minus recomputed `pi`: `1.09e-17`

This is the key result. It says the event stream's probability field is not an independent or stale value. It is the active coefficient bundle applied to the current runtime merchant design surface.

What would we have looked out for?

- Large event-vs-diagnostic differences would suggest `hurdle_pi_probs` and the event stream were produced from different scoring surfaces, or that one of them had drifted.
- Large event-vs-recomputed differences would be more serious. That would suggest a wrong coefficient bundle, wrong feature ordering, stale design matrix, bad channel/MCC/bucket mapping, or a runtime scoring bug.
- Missing joins would suggest that the event stream no longer covered the same merchant universe as the design matrix or diagnostic probability table.

None of those failure patterns appear here.

The runtime chain is therefore internally consistent:

```text
active beta + runtime X
  -> recomputed pi
  == event pi
  ~= diagnostic pi cache
```

So when we later interpret `is_multi`, we can treat it as a Bernoulli realisation of the active S1 scoring law, not as an unexplained or disconnected event field.

## RNG and decision accounting

Every merchant event is stochastic in this run:

- deterministic rows: `0`
- stochastic rows: `10,000`
- rows with `draws = 1`: `10,000`
- rows with `blocks = 1`: `10,000`
- non-null `u` rows: `10,000`
- null `u` rows: `0`

The uniform draws are in the expected open interval:

- min `u`: `0.0000235697`
- mean `u`: `0.501056`
- median `u`: `0.504838`
- max `u`: `0.999983`

The decision equation is exact:

- rows where `(u < pi) != is_multi`: `0`

The counter movement is also consistent with one consumed block per merchant:

- rows where counter high changed unexpectedly: `0`
- rows where counter low delta was not `1`: `0`

The trace side agrees for the `hurdle_bernoulli` family:

- hurdle trace rows: `10,000`
- max hurdle trace `events_total`: `10,000`
- max hurdle trace `draws_total`: `10,000`
- max hurdle trace `blocks_total`: `10,000`

This is important because the event stream is not only statistically plausible; it also has the RNG-accounting shape expected of an auditable stochastic authority.

The final Segment `1A` validation bundle also records the hurdle family as green:

- [`rng_accounting.json`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/validation/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/rng_accounting.json)
- [`s9_summary.json`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/validation/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/s9_summary.json)

The validation summary records `PASS`, with `rng_envelope`, `rng_trace_coverage`, and `s1..s8_replay` all true.

## The branch world that was actually created

Summing the event probabilities gives the expected number of multi-site merchants:

- expected multi-site merchants: `5,829.39`
- expected multi-site rate: `58.2939%`

The realised Bernoulli stream emits:

- realised multi-site merchants: `5,817`
- realised multi-site rate: `58.1700%`
- single-site merchants: `4,183`

The difference is small:

- residual count: `-12.39`
- residual rate: `-0.124` percentage points
- Bernoulli standard deviation: `46.45`
- residual z-score: `-0.267`

This is the main statistical reading: the realised branch world is not drifting away from the probability surface. It is almost exactly what the active hurdle coefficients asked the stochastic engine to create.

So if we later see downstream population size effects, the first-order branch population size is not a surprise or a stochastic anomaly. The S1 gate deliberately sends about `58%` of the merchant universe into the multi-site path.

## Runtime `pi` surface

The emitted probability surface is broad:

- min `pi`: `0.000794`
- 5th percentile `pi`: `0.2975`
- median `pi`: `0.5993`
- mean `pi`: `0.5829`
- 95th percentile `pi`: `0.8281`
- max `pi`: `0.9504`

This is a meaningful point in light of the priors investigation.

The original prior-generated training world used a `pi` corridor to keep synthetic probabilities within a controlled band. The active runtime event stream is not simply replaying that training clamp. It is applying the active remediated coefficient bundle to the current merchant world, and the resulting probabilities can be wider than the prior corridor.

That does not by itself mean the event stream is wrong. The implementation notes explicitly state that `S1` computes `pi` with the logistic function and no runtime clamp. But analytically it tells us that the active bundle is more assertive than the original synthetic training probability corridor.

## Channel shape

Channel remains one of the clearest structured effects in the hurdle branch.

| channel | merchants | expected multi | realised multi | expected rate | realised rate |
|---|---:|---:|---:|---:|---:|
| `card_present` | `7,473` | `4,593.50` | `4,589` | `61.47%` | `61.41%` |
| `card_not_present` | `2,527` | `1,235.90` | `1,228` | `48.91%` | `48.60%` |

This matches the coefficient investigation. The active hurdle lane gives `CNP` a stronger negative coefficient than `CP`, so card-not-present merchants receive lower multi-site propensity.

The realised outcomes do not distort that relationship. Both channel residuals are small relative to their Bernoulli variance.

So the channel story is: `S1` is not simply preserving the S0 channel split. It is using channel as an actual branch-shaping feature.

## GDP-bucket shape

The GDP-bucket branch surface is ordered upward in expectation:

| GDP bucket | merchants | expected multi | realised multi | expected rate | realised rate |
|---:|---:|---:|---:|---:|---:|
| `1` | `1,517` | `719.80` | `704` | `47.45%` | `46.41%` |
| `2` | `2,239` | `1,215.79` | `1,224` | `54.30%` | `54.67%` |
| `3` | `3,726` | `2,194.62` | `2,182` | `58.90%` | `58.56%` |
| `4` | `1,718` | `1,113.25` | `1,123` | `64.80%` | `65.37%` |
| `5` | `800` | `585.94` | `584` | `73.24%` | `73.00%` |

This is exactly the kind of surface we expected after inspecting the active hurdle coefficients:

- bucket `1` is suppressive
- bucket `5` is strongly uplifted
- the expected multi-site rate rises with GDP bucket

This also helps contextualise the earlier merchant-allocation findings. A country can be heavy in the merchant catalog and still not be equally heavy in the multi-site branch if it sits in a lower GDP bucket. `GH` is the obvious example: it has `315` merchants because of the residual allocation artifact, but its expected S1 multi-site rate is only about `47.32%`, and its realised rate is `43.17%`.

So `S1` partially counteracts the S0 merchant-count artifact by applying the GDP-bucket branch law. It does not remove the extra `GH` merchants from the world, but it lowers their probability of entering the multi-site path.

## Channel-by-bucket shape

The channel and GDP effects combine in the expected direction:

| channel | bucket | merchants | expected rate | realised rate |
|---|---:|---:|---:|---:|
| `card_present` | `1` | `1,132` | `50.49%` | `49.65%` |
| `card_present` | `2` | `1,681` | `57.50%` | `58.42%` |
| `card_present` | `3` | `2,772` | `62.08%` | `62.01%` |
| `card_present` | `4` | `1,288` | `67.98%` | `67.70%` |
| `card_present` | `5` | `600` | `76.49%` | `75.67%` |
| `card_not_present` | `1` | `385` | `38.51%` | `36.88%` |
| `card_not_present` | `2` | `558` | `44.65%` | `43.37%` |
| `card_not_present` | `3` | `954` | `49.67%` | `48.53%` |
| `card_not_present` | `4` | `430` | `55.26%` | `58.37%` |
| `card_not_present` | `5` | `200` | `63.50%` | `65.00%` |

This is a useful view because it shows that neither channel nor GDP bucket alone fully defines the branch posture. The same GDP bucket has lower branch probability under `card_not_present`, and the same channel rises as GDP bucket rises.

The event stream therefore embodies a two-axis branch law:

- GDP bucket pushes upward
- `card_not_present` pushes downward

The realised outcomes remain close enough to the expected rates that the pattern should be read as model structure, not random noise.

## Probability decile check

Grouping merchants by event `pi` decile gives a simple calibration sanity read:

| pi decile | merchants | expected rate | realised rate |
|---:|---:|---:|---:|
| `1` | `1,002` | `26.99%` | `27.15%` |
| `2` | `1,003` | `40.56%` | `38.78%` |
| `3` | `998` | `47.20%` | `47.60%` |
| `4` | `998` | `52.70%` | `53.21%` |
| `5` | `1,001` | `57.54%` | `58.04%` |
| `6` | `1,009` | `62.17%` | `62.93%` |
| `7` | `989` | `66.49%` | `64.51%` |
| `8` | `1,004` | `70.66%` | `70.82%` |
| `9` | `997` | `75.42%` | `75.13%` |
| `10` | `999` | `83.38%` | `83.68%` |

The decile curve is coherent: higher scored `pi` deciles realise higher multi-site rates.

There is ordinary binomial variation inside individual deciles, but no reversal of the main ordering. This supports the reading that the event stream is faithfully realising the probability surface rather than adding a second hidden policy layer.

## Country read

The largest country groups behave as expected from the joined branch surface:

| country | merchants | expected rate | realised rate |
|---|---:|---:|---:|
| `MC` | `800` | `73.24%` | `73.00%` |
| `BM` | `436` | `64.24%` | `66.97%` |
| `LU` | `379` | `65.86%` | `63.85%` |
| `IE` | `337` | `64.83%` | `63.80%` |
| `GH` | `315` | `47.32%` | `43.17%` |
| `CH` | `304` | `64.30%` | `64.47%` |
| `NO` | `262` | `64.73%` | `67.94%` |
| `SG` | `238` | `58.41%` | `53.36%` |
| `AU` | `212` | `59.67%` | `57.08%` |
| `US` | `211` | `58.39%` | `56.87%` |

The high-GDP heavy countries remain high-propensity multi-site populations. `MC`, which was already capped at `800` merchants in the S0 allocation surface, has an expected S1 multi-site rate above `73%`.

`GH` is different. Its S0 merchant count was artifact-amplified, but the hurdle gate does not treat it like the high-GDP cluster. Its expected branch rate is much lower, consistent with its bucket position. This is a useful cross-state finding: S0 determines how many merchants enter the world, while S1 determines which of them cross into the multi-site branch.

## MCC read

At MCC level, the counts are much smaller, so individual residuals should be treated carefully. For example:

- MCC `5046`: `47` merchants, expected `28.12`, realised `38`
- MCC `8651`: `52` merchants, expected `31.75`, realised `25`

Those look visually large as percentages, but they are small-cell Bernoulli outcomes. They should not be over-interpreted without either larger samples or repeated seeds.

The important MCC-level point for this stage is not a particular category anomaly. It is that MCC is part of the active feature law, and the event stream preserves that law through the coefficient-derived `pi`. If we later investigate category-specific downstream outlet shapes, MCC should come back into view after `S2`, where count generation begins.

## What this tells us about the S1 world

The S1 branch world is governed and internally coherent.

The event stream is complete, lineage-consistent, and replay-aligned with the active coefficient bundle. The realised multi-site population is almost exactly what the probability surface predicts. The stochastic draw layer does not appear to introduce unexplained drift.

The statistical structure is also clear:

- `S1` sends about `58%` of merchants into the multi-site path.
- GDP bucket is a strong upward branch driver.
- `card_not_present` is a downward branch driver relative to `card_present`.
- High-GDP heavy merchant countries stay strongly multi-site.
- The `GH` merchant-count artifact from S0 is not amplified by S1; the hurdle law suppresses it relative to the high-GDP cluster.
- The active runtime `pi` surface is wider than the original prior training corridor, reflecting the active remediated coefficient bundle and the no-clamp runtime scoring rule.

So the investigative conclusion is not merely "the event log has 10,000 rows." The conclusion is that this stream is the point where the governed merchant catalog becomes a two-branch world, and that branch split is both auditable and materially shaped by the coefficient law we already inspected.

## What this means for where we go next

The natural next object is `S2`, because `S2` only applies to the `5,817` merchants that passed this gate.

That means downstream NB-count analysis should not be interpreted over the full 10,000-merchant catalog. It should be interpreted over the S1 multi-site branch:

```text
10,000 merchants
  -> 5,817 multi-site merchants
  -> S2 NB count world
```

This changes the frame of the next investigation. We are no longer asking which merchants exist. We are asking how the already-gated multi-site merchants receive their outlet-count structure.

## Derived files written

- [`rng_event_hurdle_bernoulli_summary.json`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_summary.json)
- [`rng_event_hurdle_bernoulli_by_channel.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_by_channel.csv)
- [`rng_event_hurdle_bernoulli_by_gdp_bucket.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_by_gdp_bucket.csv)
- [`rng_event_hurdle_bernoulli_by_channel_bucket.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_by_channel_bucket.csv)
- [`rng_event_hurdle_bernoulli_pi_deciles.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_pi_deciles.csv)
- [`rng_event_hurdle_bernoulli_top_country_summary.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_top_country_summary.csv)
- [`rng_event_hurdle_bernoulli_top_mcc_summary.csv`](../exports/rng_event_hurdle_bernoulli/rng_event_hurdle_bernoulli_top_mcc_summary.csv)
