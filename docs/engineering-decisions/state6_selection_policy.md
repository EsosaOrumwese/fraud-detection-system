# State 6 – `s6_selection_policy.yaml`

## Context
- Spec: `docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s6.expanded.md` (§4).
- Purpose: govern S6 foreign-set selection (logging mode, caps, membership emission); policy bytes participate in `parameter_hash`.

## Parameter set authored (2025-10-16)
```yaml
policy_semver: "0.1.0"
policy_version: "2025-10-16"
defaults:
  emit_membership_dataset: false
  log_all_candidates: true
  max_candidates_cap: 0
  zero_weight_rule: "exclude"
per_currency:
  USD:
    emit_membership_dataset: true
    max_candidates_cap: 10
    zero_weight_rule: "exclude"
```

## Rationale / assumptions
- Start S6 in full logging mode so validators can recompute keys directly; cap defaults to zero (no truncation) until profiling data suggests otherwise.
- Membership surface remains off globally to avoid unnecessary storage, with overrides documented explicitly.
- Zero-weight candidates stay excluded to mirror S5 behaviour; any inclusion must be intentional and coordinated with validators.

## TODO / follow-ups
- [ ] Finalise per-currency overrides once calibration data is available.
- [ ] Revisit membership emission defaults after S7 consumers review needs.
- [ ] Record future updates here with dated entries.
