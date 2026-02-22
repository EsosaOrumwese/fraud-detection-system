# Dev-Full Managed-Substrate Migration (Learning/Evolution + Full Platform) - Design-Authority v0

## 0. Document Control

### 0.1 Status
- Status: v0 (draft-initial, fail-closed)
- As-of: 2026-02-22 (Europe/London)
- Scope of v0: pin the environment boundary and migration posture for `M11+` only.

### 0.2 Scope Boundary (Pinned)
- `dev_min` remains the certified Spine Green v0 managed-substrate baseline (`M1..M10`).
- `M11+` (Learning/Registry + full-platform closure) targets `dev_full`, not `dev_min`.
- No local/laptop compute is allowed for `M11+` runtime lanes.
- Any unresolved dev_full authority/handle dependency is a blocker (`HOLD_M11`).

### 0.3 Why This Repin Exists
- The migration objective has moved beyond "off-laptop spine" and now includes managed Learning/Evolution tooling exposure.
- The implementation target for `M11+` should reflect production-shaped toolchain experience (for example: SageMaker/Aurora/Databricks/MLflow/Airflow) rather than handwritten service replicas.
- Cost posture still applies: phase-aware activation, teardown discipline, and cross-platform cost evidence.

## 1. Authority Boundaries

### 1.1 Pinned (MUST)
- `M11..M14` must be planned and executed against dev_full authority + dev_full handles.
- `M8..M10` spine non-regression remains mandatory before any `M11+` close verdict.
- Managed substrate law stays in force: Terraform + GitHub Actions are control-plane authority.
- Evidence law stays in force: every phase publishes local + durable evidence artifacts.

### 1.2 Deferred (Must be pinned in M11.A/M11.B before execution)
- Exact service choices and run modes per learning lane (job/service/workflow engine).
- Exact role/secret paths and trust policies.
- Exact data-store and path contracts (feature sets, training data, model/artifact stores, registry paths).
- Exact promotion and rollback corridor semantics for registry.

## 2. Required References
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M11.build_plan.md`
- `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
- `docs/model_spec/platform/platform-wide/dev_substrate_to_production_resource_tooling_notes.md`

## 3. Fail-Closed Entry Rule (M11)
- `M11` cannot enter execution if either of these is missing or unresolved:
  - this authority document,
  - `dev_full_handles.registry.v0.md` required-handle matrix.
