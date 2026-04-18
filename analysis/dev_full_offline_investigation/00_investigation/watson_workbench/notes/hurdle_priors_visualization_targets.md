# `hurdle_simulation.priors.yaml` Visualization Targets

This note is not the plotting itself. It is the compact list of concepts from the priors investigation that should be made visually legible before we move them into the notebook.

## What needs to be visualized

- The overall authoring pipeline:
  how `hurdle_simulation.priors.yaml` flows into the synthetic corpus, then into fitted coefficients, and then into the active remediated bundle.

- The calibration targets:
  what `mean_pi_target`, `mean_mu_target_multi`, and `median_phi_target` are trying to control in the synthetic world.

- The calibration mechanics:
  how the bounded search over `base_logit`, `base_log_mean`, and `base_log_phi` moves from starting values to solved values.

- The effect of changing calibration targets:
  what changes when lower guide-style targets are used versus the current priors targets versus the more aggressive late-December values.

- The role of clamps:
  what it means to clamp `pi`, `mu`, and `phi`, and why the chosen clamp ranges matter for the synthetic world.

- The belt-and-braces corridor:
  which corridor checks the export must satisfy and why they forced the late-December retuning of targets and floors.

- The hurdle authored shape:
  how channel offsets, GDP-bucket offsets, MCC range offsets, and MCC overrides define the initial hurdle branch contour.

- The NB-mean authored shape:
  how the priors define the initial multi-site count world before any later remediation of `beta_mu`.

- The dispersion authored shape:
  how `base_log_phi`, `gdp_log_slope`, channel offsets, MCC range offsets, and MCC overrides define the dispersion world.

- The synthetic training outputs:
  what `logistic.parquet` and `nb_mean.parquet` actually represent and how they differ in population and purpose.

- The priors-to-bundle relationship:
  what parts of the active coefficient bundle still reflect the priors directly, and what parts no longer do.

- The remediation break from the original priors world:
  how the active run diverged from the original January training export, especially the later `+2.2` hurdle intercept shift and the subsequent `beta_mu` lane edits.

- The guide-versus-implementation nuance:
  where the authoring guide describes one calibration posture, but the current export script actually calibrates using a different practical method.

- The documentary drift:
  where surrounding docs or evidence notes no longer line up cleanly with the active training lineage we are actually investigating.

## Immediate plotting rule

Every plot we generate from here should answer one of the bullets above clearly enough that a human reader can tell:

- what concept is being shown
- what relationship or contrast matters
- and why that point changes the interpretation of the priors or the resulting bundle
