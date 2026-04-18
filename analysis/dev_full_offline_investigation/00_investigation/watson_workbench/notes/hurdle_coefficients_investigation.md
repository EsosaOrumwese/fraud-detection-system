# `hurdle_coefficients.yaml` Investigation

## Why this object matters

For `1A.S1`, this is the first governed artefact that actually tells the engine how to branch the merchant world. It is not just configuration in the abstract. It is the sealed coefficient bundle that turns the merchant predictor basis into the authoritative `single-site` vs `multi-site` split.

But the bundle also does more than its name first suggests. It is a dual-purpose artefact:

- `beta` drives the `S1` hurdle decision
- `beta_mu` is carried forward into `S2` for the NB mean path

So this is not merely "the hurdle file." It is a governed coefficient bundle that spans the `S1` and `S2` boundary inside Segment `1A`.

## The exact bundle used by our pinned run

The active run seals this exact file:

- [`config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml`](../../../../../config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml)

This is recorded in the run's sealed inputs:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json`](../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer1/1A/sealed_inputs/manifest_fingerprint=76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460/sealed_inputs_1A.json)

The sealed-input path matters because it tells us that this is not a speculative "latest config" investigation. This is the actual bundle that authored the active `S1` branch world in the run we are studying.

## What the bundle contains

The bundle carries these top-level keys:

- `semver`
- `version`
- `metadata`
- `dict_mcc`
- `dict_ch`
- `dict_dev5`
- `design`
- `beta`
- `beta_mu`

That matches the hurdle schema contract in:

- [`docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`](../../../../../docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml)

The key structural fact is that the bundle freezes the dictionaries and the order contract at the same time as the coefficients. So it is not just a list of numbers; it is also the authority for how those numbers are to be interpreted.

## Structural shape of the active bundle

From the active run bundle:

- `|dict_mcc| = 290`
- `dict_ch = ["CP", "CNP"]`
- `dict_dev5 = [1, 2, 3, 4, 5]`
- `len(beta) = 298`
- `len(beta_mu) = 293`

Those lengths are exactly what the design contract implies:

- `beta = 1 + 290 + 2 + 5 = 298`
- `beta_mu = 1 + 290 + 2 = 293`

The bundle therefore satisfies the core frozen-order requirement that the engine expects in `S1` and `S2`. This aligns with the implementation note:

- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)

Relevant implementation line of thought there:

- the engine loads `dict_mcc`, `dict_ch`, `dict_dev5`, and `beta`
- it validates `dict_ch == ["CP","CNP"]`
- it validates `dict_dev5 == [1,2,3,4,5]`
- it validates the exact coefficient length

## What this says about how `S1` sees the merchant world

The bundle defines the frozen hurdle feature order as:

- intercept
- MCC one-hot in `dict_mcc` order
- channel one-hot in `["CP","CNP"]` order
- GDP bucket one-hot in `[1,2,3,4,5]` order

That means `S1` does not look at arbitrary merchant attributes. It only sees:

- merchant category
- channel
- GDP bucket
- an intercept

This is an important narrowing point. By the time we reach `S1`, the merchant world is already compressed into a very specific governed predictor basis.

## Alignment to the active merchant parquet

I compared the bundle's `dict_mcc` directly against the active merchant parquet at:

- [`reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet`](../../../../../reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet)

Result:

- parquet distinct MCC count: `290`
- `dict_mcc` count: `290`
- exact ordered match: `true`
- missing MCCs from the bundle: `0`
- extra MCCs in the bundle: `0`

This is a strong result. The bundle is not carrying a stale or inflated MCC vocabulary. Its frozen MCC basis matches the active merchant universe exactly.

## What the coefficient blocks look like

### `beta` block (the actual hurdle lane for `S1`)

- intercept: `1.060423738098163`
- channel coefficients:
  - `CP`: `-0.28750660784290355`
  - `CNP`: `-0.8520696527283449`
- GDP bucket coefficients:
  - bucket `1`: `-0.7844325078593459`
  - bucket `2`: `-0.4810454702602077`
  - bucket `3`: `-0.2560555372181693`
  - bucket `4`: `-0.007979490332166226`
  - bucket `5`: `0.38993674638828835`

Two important features of the active hurdle lane stand out immediately:

1. The GDP bucket effect is strictly ordered upward.
   - It is monotone from bucket `1` through bucket `5`.
   - So higher GDP bucket is systematically associated with a stronger push toward the multi-site path.

2. Both channel coefficients are negative, but `CNP` is more negative than `CP`.
   - So, relative to the intercept and other terms, `CNP` is the more suppressive channel with respect to the multi-site branch.

This is consistent with the run-level branch pattern we already observed from the emitted hurdle events, where `card_present` merchants branch multi-site more often than `card_not_present` merchants.

### Hurdle MCC spread

The hurdle MCC block is broad rather than flat:

- min MCC hurdle coefficient: `-6.86544681845988`
- mean MCC hurdle coefficient: `-0.00392957331449067`
- max MCC hurdle coefficient: `1.7896311722781808`

Selected top positive MCC hurdle coefficients:

- `5541`: `1.7896`
- `5532`: `1.7827`
- `4829`: `1.6774`
- `5531`: `1.6197`
- `5542`: `1.3116`

Selected bottom MCC hurdle coefficients:

- `8911`: `-6.8654`
- `8398`: `-6.8501`
- `4815`: `-5.5563`
- `5940`: `-1.6917`
- `7534`: `-1.6262`

This means the hurdle lane is not a mild smooth preference surface. It contains some very strong MCC-level pushes and suppressions.

### `beta_mu` block (the `S2` carry-forward lane)

- intercept: `1.7814957339620379`
- channel coefficients:
  - `CP`: `1.128766904935765`
  - `CNP`: `0.7572450117988003`

Selected top positive `beta_mu` MCC coefficients:

- `5542`: `1.3755`
- `5441`: `1.3167`
- `5411`: `1.1797`
- `5541`: `1.1291`
- `5462`: `1.1151`

Selected bottom `beta_mu` MCC coefficients:

- `8011`: `-1.4481`
- `7299`: `-1.1626`
- `2741`: `-1.1450`
- `7992`: `-1.0018`
- `8299`: `-0.9265`

This reinforces the earlier point: the file name hides some of what this artefact really is. The bundle is not only about hurdle branching. It is also carrying the next lane of outlet-count authoring for the multi-site branch.

## How this bundle came about

The bundle points back to an offline training corpus via:

- `metadata.simulation_manifest`

In the active file, that points to:

- [`artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/manifest.json`](../../../../../artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/manifest.json)

That manifest records:

- the priors file
- the merchant parquet snapshot
- GDP parquet
- GDP bucket map
- ISO canonical
- dataset digests for the sealed training outputs
- the simulation seed
- summary realism targets for the corpus

The export script that authored this family of bundles is:

- [`scripts/build_hurdle_exports.py`](../../../../../scripts/build_hurdle_exports.py)

From the script, the authoring route is explicit:

1. load the priors YAML
2. build deterministic dictionaries (`dict_mcc`, `dict_ch`, `dict_dev5`)
3. materialize logistic and NB training datasets
4. fit hurdle logistic coefficients and NB mean coefficients
5. write the manifest
6. export the governed YAML bundle with the frozen design orders

So the correct mental model is:

- the active bundle is not hand-authored
- it is an offline-trained and then governed-exported artefact
- later remediation can then create successor bundles by controlled adjustments on the exported coefficients

## The remediation trail inside the active bundle

This bundle carries its own remediation metadata:

- `wave: P4.R4A`
- `change: beta_mu_non_intercept_downscale_midpoint_pass`
- `parent_bundle: version=2026-02-14/20260214T125000Z`
- `non_intercept_scale: 0.92`
- `intercept_delta: 0.0`

This immediately tells us something critical:

- the active sealed bundle is not a pristine direct export from the January training manifest
- it is a later governed remediation bundle
- the remediation specifically targeted the `beta_mu` lane

That is confirmed by direct comparison with the parent bundle:

- `beta` is exactly unchanged relative to the parent
- `beta_mu` is changed
- `beta_mu` intercept is unchanged
- the change is a non-intercept reshaping step, not a hurdle-lane reshaping step

This lines up with the implementation and logbook trail:

- [`docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`](../../../../../docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md)
- [`docs/logbook/02-2026/2026-02-12.md`](../../../../../docs/logbook/02-2026/2026-02-12.md)

The broader remediation story there is:

- the earlier `2026-02-12` bundle family was locked after `P1`
- a later bounded reopen for `1B P4.R4A` targeted upstream `1A` home-support shape
- the chosen low-blast move was to adjust `beta_mu` while holding hurdle and dispersion posture stable

So the active `2026-02-14/20260214T173000Z` bundle is best understood as:

- an upstream reopen candidate / remediation bundle
- built on top of the earlier certified coefficient family
- with the `S1` hurdle lane held fixed and the `S2` mean lane modified

## What it contributes to `S1` specifically

For `S1`, the file contributes:

- the exact hurdle coefficient vector `beta`
- the exact MCC dictionary order
- the exact channel dictionary order
- the exact GDP-bucket dictionary order
- the frozen design-order contract

In other words, `S1` does not merely "use the coefficients." It uses this bundle as the authority for:

- what predictor blocks exist
- what their order is
- and what the branch scoring vector is

That is why the implementation is strict about loading the bundle atomically and checking the dictionary and vector lengths before any hurdle event is emitted.

## What it contributes beyond `S1`

The bundle also contributes `beta_mu` to `S2`.

That means one governed artefact spans two adjacent modelling states:

- `S1` branch decision
- `S2` count-shape mean lane

This is an important architectural fact. It means later changes to this bundle can leave `S1` untouched while still materially changing downstream site-count behaviour through `beta_mu`.

That is exactly what the active remediation metadata shows happened here.

## Important anomalies / governance tensions uncovered

### 1. Path version vs internal version mismatch

The active sealed path is:

- `version=2026-02-14/20260214T173000Z/...`

But inside the YAML:

- `version: '2026-02-12'`

That is a real inconsistency.

It does not necessarily break runtime use, because the path is what the sealed input system resolved and hashed. But it weakens interpretability, because the internal semantic version field is lagging behind the publication path.

### 2. The bundle points back to a January training manifest while serving a February remediated run

This is explainable, not necessarily wrong:

- the January manifest captures the original offline training corpus
- the February bundle captures a later governed remediation derived from that lineage

But it means the `simulation_manifest` alone does not fully explain the final active numbers. To understand the active bundle, you must also consult:

- the remediation metadata in the YAML itself
- the `segment_1A.impl_actual.md` decision trail
- the February logbook entries

### 3. Absolute Windows paths in bundle metadata

The bundle metadata and manifest store `C:/...` paths.

This is acceptable for local provenance in this repo, but it is not ideal as a portable governance posture. For our investigation it is fine, but it is worth noting as a production-facing portability weakness.

## Current judgment

This bundle is structurally strong and operationally meaningful.

What is good:

- it is sealed into the run cleanly
- it matches the merchant MCC universe exactly
- its design order and lengths align with the runtime contract
- it clearly encodes the hurdle lane and the NB mean lane
- it carries remediation metadata instead of silently overwriting lineage

What is less clean:

- the internal `version` field lags the published bundle path
- understanding the active coefficients requires reading both the YAML and the implementation/logbook trail
- the artefact name understates its cross-state role, because it also contains `beta_mu`

## Where this leaves us

At this point, the bundle has already taught us three important things before touching the design matrix:

1. `S1` is acting on a tightly governed and narrow predictor basis, not a loose merchant feature world.
2. The active bundle is not simply a static export; it is a remediated governed artefact with an explicit path through the engine's hardening history.
3. The active run's `S1` hurdle lane is intentionally frozen while the neighbouring `S2` mean lane has been adjusted.

That means the next object, `hurdle_design_matrix`, should be read in light of this: not as a random feature table, but as the merchant-level realization of the frozen basis this bundle expects.
