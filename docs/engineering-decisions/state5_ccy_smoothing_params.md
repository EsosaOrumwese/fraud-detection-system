# State 5 – `ccy_smoothing_params.yaml`

## Context
- Spec: `docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s5.expanded.md` (§4).
- Purpose: govern deterministic blending of `settlement_shares_2024Q4` and `ccy_country_shares_2024Q4` when building `ccy_country_weights_cache` (and optional `merchant_currency`).

## Parameter set authored (2025-10-16)
```yaml
semver: "0.1.0"
version: "2025-10-16"
dp: 6
defaults:
  blend_weight: 0.6
  alpha: 1.0
  obs_floor: 250
  min_share: 0.0005
  shrink_exponent: 1.0
per_currency:
  USD:
    blend_weight: 0.65
    alpha: 1.2
    obs_floor: 500
  EUR:
    blend_weight: 0.62
    min_share: 0.0008
overrides:
  alpha_iso:
    USD:
      PR: 1.1
  min_share_iso:
    EUR:
      IE: 0.0012
```

## Rationale / assumptions
- **Defaults** chosen as conservative smoothing weights until production calibration arrives. Blend 0.6 biases toward settlement shares while allowing priors to pull sparse currencies.
- **Alpha / min-share** values follow the spec’s non-negative constraints and keep total ISO floors well below 1.0.
- **Currency overrides** cover USD/EUR since they dominate our synthetic share surfaces; values are illustrative but respect the domain guards.
- **ISO overrides** demonstrate min-share boosts for specific ISO codes (Ireland for EUR) and extra alpha mass for USD→PR where merchant settlement behaviour is known to be noisy.
- These numbers are **development placeholders**. We must revisit once real calibration data is available; changing the file will flip `parameter_hash` as required.

## TODO / follow-ups
- ✅ Automated validation now runs in the S5 suite (`tests/engine/layers/l1/seg_1A/s5_currency_weights`) covering Σ discipline, coverage rules, and receipt metrics per spec §14.
- ✅ `merchant_currency` emission is wired to the sealed legal-tender artefact and the runner enforces provenance (`packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py`).
- Document any future calibration updates in this directory with dated sections.
