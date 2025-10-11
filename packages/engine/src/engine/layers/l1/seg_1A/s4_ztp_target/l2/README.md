# S4 ZTP Target – L2 Orchestration

Status: **Implemented** (runner + deterministic assembly).

L2 builds the deterministic merchant view, coordinates the L1 kernels, and
returns the structured run artefacts that downstream consumers rely on.

## Surfaces
- `deterministic.py` materialises `S4DeterministicArtefacts` and
  `build_deterministic_context`, wiring governed hyperparameters, feature
  inputs, and resume-aware output locations.
- `runner.py` houses `S4ZTPTargetRunner`, which derives Philox substreams per
  merchant, invokes `run_sampler`, persists RNG logs via the L0 writer, and
  returns `S4RunResult`/`S4StateContext` summaries.
- `__init__.py` re-exports the public orchestrator API so scenario runners and
  tests can import the layer through `engine.layers.l1.seg_1A.s4_ztp_target.l2`.

The implementations honour branch purity (multi + eligible merchants only),
resume semantics (reads existing logs before appending), and propagate metrics
that the validator can confirm.
