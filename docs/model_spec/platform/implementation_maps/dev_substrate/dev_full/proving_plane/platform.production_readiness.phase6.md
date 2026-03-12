# Phase 6 - Working Network + Learning Coupled Readiness

The goal of `Phase 6` is to prove that the promoted runtime network and the promoted learning corridor remain one explainable, deterministic, production-credible system once active bundle truth is coupled back into runtime resolution.

This phase does not close because a candidate bundle exists. It closes only when runtime bundle resolution, policy fallback truth, and managed promotion truth all agree on the same active bundle without semantic ambiguity.

## What must be true for Phase 6 to close
`Phase 6` closes only when all of the following are true:

1. `Phase 4` source runtime truth remains the promoted operating basis,
2. `Phase 5` learning-plane proof is green on an admitted current semantic basis,
3. Decision Fabric runtime resolution reads the same governed bundle truth the learning corridor claims is active,
4. registry snapshot truth, policy fallback truth, and managed promotion truth do not drift,
5. runtime compatibility remains green on the managed active bundle truth,
6. the coupled evidence is explainable, attributable, and auditable.

## Coupled boundary in scope

### Promoted runtime basis
- working platform entering this phase:
  - `Control + Ingress + RTDL + Case + Label`
- coupled source scope:
  - `execution_id = phase4_case_label_coupled_20260312T003302Z`
  - `platform_run_id = platform_20260312T003302Z`

### Promoted learning basis
- bounded learning proof:
  - `execution_id = phase5_learning_mlops_bound_20260312T035531Z`
  - `verdict = PHASE5_READY`
- governed active bundle ref:
  - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mf/candidate_bundle.json`

### Runtime resolution surfaces
- Decision Fabric registry snapshot:
  - `config/platform/df/registry_snapshot_dev_full_v0.yaml`
- Decision Fabric resolution policy:
  - `config/platform/df/registry_resolution_policy_v0.yaml`
- runtime resolver contract:
  - `src/fraud_detection/decision_fabric/registry.py`

## Phase 6.A - Coupled runtime-resolution proof
Purpose:
- prove that active runtime bundle resolution remains governed by the same bundle truth the managed learning corridor claims is active.

This subphase is green only when all of the following are true:
1. fraud and baseline runtime scopes both resolve cleanly,
2. both scopes resolve to the expected governed bundle ref,
3. explicit policy fallbacks do not drift from the governed active bundle truth,
4. runtime compatibility remains green on the active bundle truth.

## Current telemetry and proof surfaces

### Live boundary health
- `Phase 4` source receipt
- `Phase 5` bounded proof receipt and summary
- Decision Fabric registry snapshot + policy readability
- runtime fraud / baseline scope resolution results
- managed promotion and active-resolution evidence readability

### Minimal hardening artifacts
- one coupled summary
- one coupled receipt

## Current accepted coupled result
- `execution_id = phase6_learning_coupled_20260312T035601Z`
- `verdict = PHASE6_READY`
- `open_blockers = 0`

Accepted proof details:
- Decision Fabric runtime resolution now resolves both:
  - `dev_full|fraud|primary| -> RESOLVED`
  - `dev_full|baseline|primary| -> RESOLVED`
- both runtime scopes resolve to:
  - `bundle_id = 40d27a4c62e2438e`
  - `bundle_version = m11g_candidate_bundle_20260227T081200Z`
  - `registry_ref = s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/learning/mf/candidate_bundle.json`
- policy explicit fallbacks remain aligned with the same governed bundle ref
- active managed-resolution evidence remains aligned with the same governed bundle ref
- runtime compatibility remained green through the retained `m12f` active-resolution proof

## Phase 6 closure rule
`Phase 6` closes only when:

1. runtime fraud and baseline scope resolution are both deterministic,
2. runtime resolution matches the governed active bundle truth,
3. policy fallback truth and managed promotion truth do not drift,
4. the enlarged working platform remains explainable and auditable.

If any one of those is false, `Phase 6` remains open.

## Current judgment
- `Phase 6` is closed green.
- The promoted working platform is now:
  - `Control + Ingress + RTDL + Case + Label + Learning + Evolution / MLOps`
- The next honest active phase is:
  - `Phase 7 - Operations / Governance / Meta readiness`
