# Degrade Ladder Policy Profiles (v0)
_As of 2026-02-07_

This directory pins DL posture policy profiles used by the RTDL decision core.

## File
- `config/platform/dl/policy_profiles_v0.yaml`

## Contract summary
- Top-level revision identity:
  - `schema_version`
  - `policy_id`
  - `revision`
  - optional `content_digest` (computed by loader when omitted)
- Per profile entry (`local`, `local_parity`, `dev`, `prod`):
  - `mode_sequence` (must be exactly: `NORMAL`, `DEGRADED_1`, `DEGRADED_2`, `FAIL_CLOSED`)
  - `signals`:
    - `required` (non-empty list)
    - `optional` (list)
    - `required_max_age_seconds` (positive integer)
  - `thresholds` (latency budgets, hysteresis, signal freshness)
  - `modes.<MODE>.capabilities_mask`

## Capability mask fields (required)
- `allow_ieg`
- `allowed_feature_groups`
- `allow_model_primary`
- `allow_model_stage2`
- `allow_fallback_heuristics`
- `action_posture` (`NORMAL` or `STEP_UP_ONLY`)

## Profile references
Platform profiles reference this file under:
```
dl:
  policy:
    profiles_ref: config/platform/dl/policy_profiles_v0.yaml
    profile_id: <local|local_parity|dev|prod>
```

## Notes
- DL policy profile is outcome-affecting config and should be stamped as `policy_rev` in downstream posture/decision artifacts.
- Unknown or invalid profile data should fail closed during DL bootstrap.
