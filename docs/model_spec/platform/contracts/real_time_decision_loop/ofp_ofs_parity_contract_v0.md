# OFP/OFS Parity Contract (v0)
_As of 2026-02-06_

This contract pins what "parity" means between:
- OFP online snapshot materialization, and
- OFS offline recomputation.

## Purpose
Guarantee replay-comparable feature outputs for the same evidence basis.

## Identity tuple (must match)
Parity comparisons are only valid when all fields below match:
- `feature_def_policy_rev.policy_id`
- `feature_def_policy_rev.revision`
- `feature_def_policy_rev.content_digest`
- `run_config_digest`
- `pins.platform_run_id`
- `pins.scenario_run_id`
- `pins.scenario_id`
- `pins.manifest_fingerprint`
- `pins.parameter_hash`
- `pins.seed`
- `as_of_time_utc`

## Evidence basis (must match)
- `eb_offset_basis.stream`
- `eb_offset_basis.offset_kind`
- `eb_offset_basis.offsets[]` (exclusive-next offsets by partition)
- `eb_offset_basis.basis_digest`
- `graph_version` semantics:
  - if OFP used IEG in feature derivation, parity must include equivalent graph token.
  - if OFP did not use IEG, parity comparison must not inject graph-backed derivations.

## Snapshot hash expectations
- `snapshot_hash` is computed from canonical JSON using the pinned OFP hash function.
- For identical identity tuple + evidence basis + feature values:
  - expected result is identical `snapshot_hash`.
- Any mismatch in identity tuple or evidence basis:
  - expected result is a different `snapshot_hash`.

## Determinism expectations
- Duplicate deliveries under at-least-once replay must not alter terminal snapshot for the same basis.
- Out-of-order event-time arrivals must converge to the same terminal snapshot when evidence basis is equivalent.
- Restart/resume from checkpoints must converge to the same terminal snapshot as single-pass apply.

## Failure posture
- If basis identity cannot be established, parity result is `UNCHECKABLE`.
- If basis identity matches but hash differs, parity result is `MISMATCH` and requires anomaly investigation.

