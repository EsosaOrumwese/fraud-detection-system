"""State 5 – currency→country weights expansion (Layer 1 / Segment 1A).

This package wires the deterministic pipeline described in
`docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s5.expanded.md`:

- loads governed smoothing policy (`config/allocation/ccy_smoothing_params.yaml`)
- reads sealed reference share surfaces and ISO legal tender lookup
- materialises `ccy_country_weights_cache` (+ optional `merchant_currency`, `sparse_flag`)
- publishes parameter-scoped validation receipts and QA metrics

Modules:
- `loader.py` – ingress readers for share surfaces & ISO tables
- `policy.py` – parsing + validation of smoothing parameters
- `builder.py` – core smoothing/blending algorithm
- `persist.py` – writers for datasets + validation receipts
- `validate.py` – reusable schema/coverage validators
- `cli.py` – orchestration entry point (hooked into engine CLI)
"""

``` TODO: implementation in state_5_build branch ```
