# `1A.S2` Investigation: Stochastic NB Realization

## Why this block matters

The previous `S2` note stopped at the deterministic parameter surface.

By the end of `deterministic_nb_construction.md`, each admitted merchant already had a governed mean `\mu_m` and dispersion `\phi_m`. But that still does not tell us what `S2` actually authored in the run. The authored count world only appears once the engine turns those sealed parameters into component draws, retries failed low-count outcomes, and finally records one accepted outlet count per merchant.

This note investigates that stochastic realization itself.

The object here is not just to confirm that `S2` sampled something. The job is to understand:

- how the engine moves from `(\mu_m,\phi_m)` into concrete attempt events
- what evidence streams are emitted for those attempts
- how the rejection loop behaves in the pinned run
- what kind of realized outlet-count world emerges from that loop

## Working plan used in this investigation

I approached the stochastic block in five steps:

1. **Pin the stochastic contract**
   Re-read `S2.3`, `S2.4`, `S2.5`, and the validation clauses in `S2.6`/`S2.7` so the investigation stayed fixed on the actual Gamma → Poisson → accept contract rather than on a generic negative-binomial story.
2. **Separate the true `S2` streams from neighboring traffic**
   The `poisson_component` family path is shared later by `S4`, so the first runtime task was to isolate the `S2` subset explicitly.
3. **Reconstruct attempt order**
   Rebuild attempt number per merchant from the per-substream counter order and verify that Gamma and Poisson parity holds merchant by merchant.
4. **Check the composition identities**
   Confirm that the emitted component streams really satisfy the deterministic-to-stochastic bridge, especially `\lambda = (\mu/\phi)\cdot G`.
5. **Read the realized count world**
   Only after the mechanics checked out did I read retry behavior, accepted counts, and where stochastic variation is actually concentrated.

## Core references

Contract and decision trail:

- [`docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`](../../../../../../../docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md)
- [`docs/model_spec/data-engine/implementation_maps/segment_1A.build_plan.md`](../../../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.build_plan.md)
- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

Active run evidence:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/gamma_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/gamma_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00001.jsonl`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/poisson_component/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00001.jsonl)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/nb_final/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl)

Supporting deterministic note:

- [`deterministic_nb_construction.md`](./deterministic_nb_construction.md)

Scratch analysis used for the derived checks in this note:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_nb_stochastic_realization.py`](../../../scratch/analyze_nb_stochastic_realization.py)

## The stochastic contract we are actually investigating

The contract does not treat the negative-binomial count as one opaque draw.

It decomposes the count authoring into a visible two-stage stochastic chain. For merchant `m` and attempt `t`:

$$
G_{m,t} \sim \Gamma(\phi_m, 1)
$$

where:

- `G_{m,t}` = Gamma mixture draw for merchant `m` on attempt `t`
- `\phi_m` = the deterministic dispersion parameter from `S2.2`

Plainly stated, this first step does not decide the outlet count yet. It creates a **merchant-specific random multiplier** around the deterministic surface already fixed in `S2.2`.

The easiest way to think about it is this:

- `\mu_m` says where the merchant should sit on average
- `\phi_m` says how tight or loose we want that merchant’s count world to be around that average
- `G_{m,t}` is the attempt-level stochastic shock that realizes that looseness

If `G_{m,t}` lands near `\phi_m`, the attempt stays close to the deterministic expectation. If it lands below or above `\phi_m`, the attempt intensity is pulled down or pushed up before the Poisson count is even drawn.

Then:

$$
\lambda_{m,t} = \frac{\mu_m}{\phi_m} \, G_{m,t}
$$

where:

- `\mu_m` = deterministic NB mean from `S2.2`
- `\lambda_{m,t}` = Poisson intensity used on attempt `t`

This is the bridge from the deterministic world into the stochastic one.

`S2.2` already gave us a fixed merchant-level count posture through `\mu_m` and `\phi_m`. What this step does is convert that posture into an **attempt-specific intensity**. So `\lambda_{m,t}` is not a new independent policy surface. It is the deterministic NB law after it has been perturbed by the Gamma mixture for that particular attempt.

That distinction matters:

- `\mu_m` is the merchant’s governed average level
- `\lambda_{m,t}` is the attempt-level rate the engine actually hands to the Poisson sampler

So when we later inspect rejected attempts, accepted attempts, or draw budgets, we are reading the realized behavior of `\lambda`, not the raw deterministic `\mu` surface by itself.

Then:

$$
K_{m,t} \sim \mathrm{Poisson}(\lambda_{m,t})
$$

where:

- `K_{m,t}` = proposed outlet count on attempt `t`

This is the first point where a concrete count proposal exists.

Up to here, the engine has only said: “given this merchant’s deterministic count law, and given this attempt’s Gamma shock, the count intensity for this attempt should be `\lambda_{m,t}`.” The Poisson draw is what turns that intensity into an actual integer proposal such as `0`, `1`, `7`, or `32`.

So if the deterministic block answered “what size regime is this merchant in?”, the Poisson step answers “what count did this attempt actually propose?”

The rejection rule is:

$$
K_{m,t} \in \{0,1\} \Rightarrow \text{reject and resample}, \qquad
K_{m,t} \ge 2 \Rightarrow \text{accept}.
$$

If the first accepted attempt index is `t^\star`, then:

$$
N_m = K_{m,t^\star}, \qquad r_m = t^\star - 1
$$

where:

- `N_m` = final accepted outlet count persisted in `nb_final`
- `r_m` = number of rejected attempts persisted as `nb_rejections`

This acceptance rule is where the state stops being a generic NB sampler and becomes a **governed outlet-authoring process**.

The engine is not willing to let a merchant that already entered the multi-site branch in `S1` leave `S2` with `0` or `1` outlets. So the first accepted count is not simply “the first Poisson outcome.” It is the first outcome consistent with the semantic promise of the branch:

- `S1` said this merchant belongs to the multi-site path
- `S2` therefore insists on an accepted count of at least `2`

That is why `r_m` matters analytically. It is not only a technical retry counter. It measures how much effort the stochastic process needed before it produced a count consistent with the branch semantics.

This matters analytically because it means `S2` is not merely “adding noise” to `\mu_m`. It is constructing a fully auditable attempt process whose component evidence is preserved in the run.

Another way of saying the same thing is:

- the deterministic block tells us the count world the engine intended
- the stochastic block tells us how that intended world was actually realized attempt by attempt
- the acceptance rule tells us which realized attempts are allowed to become authoritative

## A practical runtime caution discovered early

The `poisson_component` family path in the run tree is **not** pure `S2`.

The active run contains:

- `part-00000.jsonl` for `S2` NB Poisson attempts
- `part-00001.jsonl` for later `S4` ZTP Poisson attempts

So the correct `S2` subset is not “everything in `poisson_component`”. It is specifically:

- `context = "nb"`
- `module = "1A.nb_poisson_component"`
- `substream_label = "poisson_nb"`

That filtration is essential. Without it, `S2` row counts and draw budgets are overstated by downstream traffic.

I also checked for a dedicated `rng_trace_log` event stream under the active run’s event tree and did not find one. For this investigation, that means the authoritative stochastic evidence is the per-event envelope on the component and final streams themselves. That is still enough to reconstruct attempt ordering and non-consumption behavior directly.

## Coverage and attempt reconstruction

Once the `poisson_component` family is filtered down to the true `S2` subset, the stochastic world is clean:

- `gamma_component` rows: `5,834`
- `poisson_component` rows in `S2` NB context: `5,834`
- `nb_final` rows: `5,817`
- distinct merchants in all three `S2` surfaces: `5,817`

The cardinality relationship is exact merchant by merchant:

- every admitted merchant has exactly one `nb_final`
- every admitted merchant has `gamma_n = poisson_n = nb_rejections + 1`
- the maximum observed attempt count is `3`

The per-merchant rejection distribution is:

- `5,801` merchants with `0` rejections
- `15` merchants with `1` rejection
- `1` merchant with `2` rejections

So the extra `17` component rows are not noise or duplication. They are the rejected attempts that occurred before final acceptance.

This is the first key stochastic result: the run does not contain missing attempts, duplicate finals, or merchants that somehow exit the state without a final accepted count. The attempt process closes exactly once per merchant.

That closure is more important than it first looks.

If this section had shown broken parity, then every downstream interpretation of `n_outlets` would be suspect, because we would not know whether the final count was actually backed by the component evidence the state claims to emit. Instead, the run gives us a clean one-to-one story:

- each merchant enters the stochastic loop
- each attempt leaves one Gamma event and one Poisson event
- exactly one accepted count is finalized per merchant

## Component identities hold exactly

After reconstructing attempt number within merchant from the counter order, the bridge identities all hold exactly:

- `max |lambda - (mu/phi) * gamma_value| = 0.0`
- `max |alpha - phi| = 0.0`
- the final accepted Poisson `k` equals `nb_final.n_outlets` for every merchant
- the final accepted attempt index equals `nb_rejections + 1` for every merchant

This is stronger than “the numbers look close.” It means the active run is not approximating the stochastic law loosely; it is emitting component evidence that ties back to the deterministic parameter surface without any visible drift at the event level.

It also clarifies the role of the three streams:

- `gamma_component` records the first stochastic perturbation away from the deterministic mean surface
- `poisson_component` records the concrete count proposal for that perturbed intensity
- `nb_final` records the one accepted count that survives the retry loop

That ordering is worth emphasizing because it is the real statistical anatomy of `S2`.

If someone reads only `nb_final`, they can see the accepted world but not how it was reached. The component streams let us distinguish:

- what the deterministic law expected
- how the attempt-level mixture moved that expectation
- what integer count the engine then proposed
- whether the proposal was accepted immediately or required retry

## Counter discipline is clean

The stochastic surfaces also satisfy the expected RNG discipline:

- `gamma_component` counter intervals are positive, monotone, and non-overlapping within merchant
- `poisson_component` counter intervals are positive, monotone, and non-overlapping within merchant
- `nb_final` is fully non-consuming for every row:
  - `before == after`
  - `blocks = 0`
  - `draws = "0"`

This matters because `nb_final` is not another random draw. It is a non-consuming finalisation record that echoes the accepted outcome after the stochastic work has already happened in the component streams.

The earlier implementation concern about `nb_final` needing its own substream lineage is therefore resolved in the active run posture we are studying.

## The Gamma layer is simpler than the Poisson layer in this run

One of the useful things this investigation exposes is that the two stochastic layers are not equally complex in the realized run.

For the Gamma component:

- no observed attempt has `alpha < 1`
- so the active run never enters the low-shape special branch

The draw budget is correspondingly tight:

- total Gamma draws: `17,553`
- mean draws per Gamma event: `3.009`
- p95 draws per Gamma event: `3`
- max draws per Gamma event: `6`

The realized draw distribution is almost degenerate:

- `5,817` Gamma events with `draws = 3`
- `17` Gamma events with `draws = 6`

So the Gamma layer is not where runtime variability or runtime cost is concentrated. In this run it is a disciplined, low-spread stochastic perturbation layer.

There is also a useful centering property visible in the output:

- mean `gamma_value = 12.170`
- mean `phi = 12.196`
- mean `gamma_value / phi = 0.9976`

This is exactly what we should expect if the Gamma layer is acting as a mean-preserving mixture around the deterministic dispersion surface rather than introducing a systematic bias.

That last sentence is important enough to make explicit in plain language.

The Gamma layer is not supposed to tilt the whole merchant population upward or downward. Its job is to create merchant-attempt variability around the deterministic count law. So seeing `gamma_value / phi` centered near `1` tells us that the mixture is behaving like a fluctuation layer, not like a hidden second policy that rewrites the mean surface behind our backs.

## The Poisson layer is where the runtime randomness really lives

The Poisson side is much more variable.

Once the Gamma mixture has produced an attempt intensity, the run splits across both normative Poisson regimes:

- attempts with `lambda < 10`: `1,059`
- attempts with `lambda >= 10`: `4,775`

So the active `S2` run is not “all inversion” or “all PTRS.” It exercises both regimes, with the higher-intensity PTRS side dominating.

The Poisson draw budgets show where most of the stochastic cost sits:

- total Poisson draws: `122,462`
- mean draws per Poisson event: `20.991`
- p95 draws per Poisson event: `47`
- max draws per Poisson event: `125`

Compared with the Gamma layer, the Poisson layer is clearly the dominant consumer of stochastic work in `S2`. That is operationally important because it means runtime variability in the NB count state is overwhelmingly driven by the count-authoring step itself, not by the Gamma mixture pre-step and not by finalisation.

It is also analytically important.

When we later talk about realized outlet-count spread, most of that visible spread is not coming from wild instability in the Gamma component. It is coming from the fact that once an attempt intensity is set, the integer count-authoring step still has to realize a Poisson outcome. So the Poisson layer is both:

- the main runtime cost center in `S2`
- the main source of visible count randomness in the authored world

## What rejected attempts look like in the run

The rejected attempt surface is extremely small but still informative.

Across all `5,834` attempts:

- accepted attempts: `5,817`
- rejected attempts: `17`

The rejected Poisson proposals are exactly what the contract says they should be:

- `k = 0`: `1`
- `k = 1`: `16`

Nothing else was rejected.

The rejected attempts are also visibly low-intensity relative to accepted attempts:

- rejected `lambda` mean: `5.243`
- accepted `lambda` mean: `20.094`

This is a good statistical sign. The retry loop is not firing arbitrarily across the surface. It is activating where the realized attempt intensity falls into the low-count tail where `0` and `1` are still plausible Poisson outcomes.

The Gamma layer reflects the same story:

- rejected-attempt `gamma_value` mean: `7.070`
- accepted-attempt `gamma_value` mean: `12.185`

So rejected attempts are not some exotic pathology. They are simply the low-intensity tail of the same governed mixture process.

That is the right way to read the rejection loop in this run.

The retries are not telling us that the sampler is unstable or that the branch is incoherent. They are telling us that for a very small subset of merchants, one realized attempt landed low enough that the multi-site branch promise was not yet satisfied. The engine then did exactly what the contract says it should do: sample again until the branch semantics were respected.

## The realized count world remains tied to the deterministic surface

One of the questions I wanted to settle here was whether the stochastic realization meaningfully preserves the deterministic NB world we reconstructed in the previous note.

The answer is yes, but not trivially.

At the population level:

- mean deterministic `mu`: `20.139`
- mean conditional accepted expectation: `20.160`
- mean realized `n_outlets`: `20.047`

So the realized world stays very close to the deterministic expectation once the acceptance rule is accounted for.

That “once the acceptance rule is accounted for” part matters.

If we compared realized `n_outlets` only to raw `\mu`, we would be mixing two different objects:

- `\mu` is the unconditional NB mean before the `K \ge 2` acceptance rule is enforced
- realized `n_outlets` is the accepted world after low-count outcomes have been screened out

So the cleaner comparison is to the **conditional accepted expectation**, not to raw `\mu` alone. That is why the close match here is meaningful: it says the realized accepted world still sits where the governed law said it should sit after the branch rule is respected.

At the merchant level, there is still real spread:

- `corr(mu, n_outlets) = 0.819`
- realized `n_outlets / mu` p05: `0.455`
- realized `n_outlets / mu` median: `0.957`
- realized `n_outlets / mu` p95: `1.677`

This is exactly the kind of result we want to see from a governed stochastic authoring process.

The deterministic law is not being erased; higher-`mu` merchants still tend to realize higher outlet counts. But the state is also not collapsing into a fake deterministic copy of `\mu`. The accepted world retains substantial merchant-level stochastic variation around that deterministic scaffold.

That is the balance we were hoping to see.

If the realized world had hugged `\mu` too tightly, `S2` would look cosmetically stochastic but practically deterministic. If it had drifted too far away, then the deterministic NB construction from the previous note would lose explanatory power. Instead, the run shows a middle position:

- deterministic structure still explains a large share of the outlet-count world
- stochastic realization still matters enough to make merchants with similar `\mu` land at different accepted counts

## Where retry risk actually lives

The retry process is sparse enough that a raw row count alone can mislead. The more useful view is to ask where on the modeled acceptance surface the retries actually concentrate.

For the per-merchant attempt acceptance probability:

- minimum `alpha_m`: `0.7538`
- p05 `alpha_m`: `0.9864`
- median `alpha_m`: `0.99984`
- p95 `alpha_m`: `0.99999997`
- maximum `alpha_m`: `0.99999999999`

So most merchants sit on an extremely high one-attempt acceptance surface. The retry loop exists, but for the overwhelming majority of merchants it is more of a guardrail than a common path.

The concentration of actual retries makes this even clearer:

- `16` merchants retried at least once
- retry share of merchants: `0.275%`
- overall rejection share of attempts: `0.291%`

When merchants are grouped by modeled acceptance decile, the retries are almost entirely concentrated in the weakest acceptance tail:

- the bottom acceptance decile contributes `15` of the `17` total rejections
- it contains `14` of the `16` merchants that retried at all
- every decile above the fourth is clean in this run

This is the right stochastic shape. The retry loop is not randomly scattered across the world. It mostly activates where the model itself says the chance of a low-count outcome is materially less suppressed.

That is exactly the kind of alignment we want between modeled risk and realized retries.

If retries were spread uniformly across all acceptance deciles, then the modeled `\alpha_m` surface would not be telling us much about actual branch difficulty. Instead, the run shows that the retry mechanism is concentrated where the model itself says acceptance should be least automatic. So the retry evidence is not fighting the law; it is reinforcing it.

It is also worth noting what this does **not** mean. A merchant showing one realized retry is not automatically “wrong” or “problematic.” With only `17` total rejections in the run, merchant-level retry outcomes are still noisy realizations. The stronger reading is run-level and surface-level: the retry behavior stays small and is concentrated where the acceptance law is weakest.

## What this block establishes

This investigation fixes the stochastic identity of `S2`.

`S2` is not just a mean-and-dispersion state with a final count attached to it later. It is a transparent Gamma → Poisson attempt machine with a governed acceptance rule, and the active run preserves that structure cleanly.

The main conclusions are:

- the `S2` stochastic world is fully reconstructible from its emitted evidence streams
- the component identities hold exactly, not approximately
- the finaliser is genuinely non-consuming and behaves as a pure acceptance echo
- the Gamma layer is light and mean-preserving in this run
- the Poisson layer is where most of the runtime randomness and draw budget live
- retry behavior is extremely sparse and concentrated in the lowest acceptance tail
- the realized outlet-count world remains strongly tied to the deterministic `\mu` surface while still preserving meaningful stochastic spread

That leaves the next block very clear.

The remaining `S2` question is no longer “what stochastic process did the engine run?” We have answered that. The remaining question is whether this realized stochastic world is healthy under the state’s corridor and acceptance standards.
