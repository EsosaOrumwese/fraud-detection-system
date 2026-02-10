# Platform Implementation Map (dev_substrate)
_As of 2026-02-10_

## Entry: 2026-02-10 7:20PM - Routing start for dev substrate promotion track

### Context
This file begins the active implementation map track for dev substrate promotion.

### Routing
- Baseline local-parity implementation history remains at:
  - `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
  - component maps under `docs/model_spec/platform/implementation_maps/local_parity/`
- New dev substrate decisions are appended under:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/*.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/*.build_plan.md`

### Scope posture
This track is a substrate promotion (not platform semantic rewrite): maintain the same rails/contracts while swapping infrastructure and tightening runtime posture.

## Entry: 2026-02-10 7:26PM - Applied implementation-map track split (baseline vs dev substrate)

### Problem / goal
Separate baseline local-parity implementation history from active dev substrate promotion decision flow, while preserving append-only traceability.

### Changes applied
- Created track folders:
  - `docs/model_spec/platform/implementation_maps/local_parity/`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/`
- Moved existing root map files (39 files) into `local_parity/`.
- Added new active-track starters:
  - `dev_substrate/platform.build_plan.md`
  - `dev_substrate/platform.impl_actual.md`
  - `dev_substrate/README.md`
- Replaced root `implementation_maps/README.md` with a routing/index README.
- Updated baseline README at `local_parity/README.md` to mark it as historical baseline.
- Updated `AGENTS.md` to route active implementation-map writes to `dev_substrate/` and baseline lookups to `local_parity/`.
- Added a routing continuity entry in `local_parity/platform.impl_actual.md`.

### Validation
- Verified root now contains only routing README.
- Verified `dev_substrate/` contains active platform map starters.
- Verified baseline folder preserves all moved historical map files.
- Verified AGENTS path/routing references now point to `dev_substrate` for active work.

### Drift sentinel check
No platform semantic rails were changed. This was a documentation/process routing restructure only.
