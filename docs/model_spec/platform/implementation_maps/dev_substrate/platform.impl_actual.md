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

## Entry: 2026-02-10 9:03PM - Authority review checkpoint: dev-min managed-substrate migration design doc

### Reviewed authority
- `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

### Review outcome (alignment to active dev_substrate track)
- The document is implementation-ready and aligned with current track posture:
  - env ladder semantics preserved (`local_parity -> dev -> prod`) with `dev_min` as a dev rung/profile.
  - managed substrate pinned (Confluent Kafka + AWS S3 evidence posture).
  - invariant laws explicitly pinned (dedupe, append-only truth, origin_offset replay anchors, explicit degrade, provenance pins).
  - Terraform split (`core` persistent + `demo` ephemeral) aligns with current topology intent.

### Interaction with repository topology decision
- Active topology pin in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.repo_topology.md`
  is compatible with this authority.
- Naming is the only pending normalization:
  - authority uses `core/demo`;
  - topology draft currently uses `dev_min_core/dev_min_demo`.
- Next step must pin one canonical naming scheme before Terraform unlock.

### Drift sentinel check
No drift detected against flow narrative, platform-wide rails, or truth ownership boundaries during this authority review.

## Entry: 2026-02-10 9:06PM - Corrective routing after user removed separate topology draft

### Context
User removed the separate topology draft document because it was not useful in its previous form.

### Decision
- Continue the dev-substrate track without a standalone topology draft file.
- Use the pinned authority directly as the placement/structure source:
  - `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
- Keep topology/placement decisions as append-only entries in this file and corresponding phase items in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Consequence
Earlier references to a separate topology draft are now historical context only; active implementation should not depend on that file.

### Drift sentinel check
No semantic drift. This is a documentation routing correction only.
