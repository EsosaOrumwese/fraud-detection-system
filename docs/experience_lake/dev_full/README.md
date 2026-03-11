# dev_full Experience Lake

This folder is the working narrative space for the `dev_full` platform story.

It is organized around the three cumulative goals:

- `a_production_wiring/`
  Baseline platform-foundation understanding.
  Use this for notes about why the wired platform was designed the way it was, which paths are necessary, what each path is for, and what tradeoffs or constraints were accepted.
  Reference docs:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.impl_actual.md`
  - relevant `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M*.build_plan.md` files as needed for the original wiring decisions

- `bi_production_readiness/`
  Production-pressure and readiness reasoning.
  Use this for notes about what broke, what proved insufficient under pressure, what changed, and why those changes were the correct engineering response.

- `bii_production_proven/`
  Operational proof and defended production posture.
  Use this for notes about bounded proof, repeatability, drills, closure evidence, and the auditable operating story.

## Intent

This folder is not the build authority and not the proving authority.

Its job is to help turn the platform work into a clear, reviewable, senior-level engineering narrative:

1. there is a real engineered foundation,
2. that foundation was reasoned toward production readiness under pressure,
3. and that readiness was then turned into operational proof.
