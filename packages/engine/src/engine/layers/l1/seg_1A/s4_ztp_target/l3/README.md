# S4 ZTP Target – L3 Validation

Status: **Implemented** (validator + bundle publisher).

L3 verifies that the emitted RNG logs satisfy the S4 contract and publishes the
optional metrics bundle used by sealed runs.

## Surfaces
- `validator.py` exposes `validate_s4_run`, replaying Poisson attempts,
  ensuring zero-handling/exhaustion semantics, and guarding counter, trace, and
  payload constraints. It returns metrics that the CLI surfaces.
- `expectations.py` lists the failure vocabulary and stream contracts so other
  layers can reuse the canonical error codes.
- `bundle.py` provides `publish_s4_validation_artifacts`, copying validation
  outputs into the run’s `validation_bundle/manifest_fingerprint=*/s4_ztp_target`
  directory and refreshing the pass flag.

Import these helpers via `engine.layers.l1.seg_1A.s4_ztp_target.l3` to keep the
validation behaviour consistent across tests, scenario runners, and the CLI.
