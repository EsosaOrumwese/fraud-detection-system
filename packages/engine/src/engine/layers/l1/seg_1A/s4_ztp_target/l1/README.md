# S4 ZTP Target - L1 Helpers

Status: **Implemented** (kernels ready for reuse).

L1 owns the pure logic that turns deterministic merchant inputs into
zero-truncated Poisson outcomes while emitting the mandated RNG logs.

## Surfaces
- `compute_lambda_regime`: applies the governed link to produce
  `lambda_extra` and selects the inversion vs PTRS regime using the frozen
  threshold (`10.0`).
- `derive_poisson_substream`: derives the Philox substream label for S4
  using the merchant id.
- `run_sampler`: drives the attempt loop, coordinating with the L0
  `ZTPEventWriter` to emit Poisson attempts, zero rejections, exhaustion
  markers, and the non-consuming finaliser.
- `SamplerOutcome`: frozen summary of the sampler for downstream
  validation/reporting.

The helpers assume all gatekeeping (multi-site, eligibility, admissible
foreign count) has been enforced by the caller; violations raise the S4
exception taxonomy declared in `s0_foundations.exceptions`.
