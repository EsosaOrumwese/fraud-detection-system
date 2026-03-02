# Cluster 8 - Round 1 Evidence

## Authority Files

1. `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
2. `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
4. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
5. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
6. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
7. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

## M0-M3 Evidence Roots

1. M0 governance closure (doc-first):
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
2. M1:
   - `runs/dev_substrate/m1_build_go/20260213T114002Z/`
3. M2:
   - `runs/dev_substrate/m2_j/20260213T205715Z/`
4. M3:
   - `runs/dev_substrate/m3/20260213T221631Z/`

## M1 Packaging Evidence

1. `runs/dev_substrate/m1_build_go/20260213T114002Z/packaging_provenance.json`
2. `runs/dev_substrate/m1_build_go/20260213T114002Z/build_command_surface_receipt.json`
3. `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
4. `runs/dev_substrate/m1_build_go/20260213T114002Z/ci_m1_outputs.json`

## Terraform and Script Roots

1. `infra/terraform/dev_min/core`
2. `infra/terraform/dev_min/confluent`
3. `infra/terraform/dev_min/demo`
4. `tools/dev_substrate`

## Secret and IAM Evidence

1. `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
2. `runs/dev_substrate/m1_build_go/20260213T114002Z/security_secret_injection_checks.json`
3. Key fields:
   - `checks.iam_simulation.app_role_allowed_count = 6`
   - `checks.iam_simulation.execution_role_allowed_count = 0`
   - `overall_pass = true`
   - `verdict = "PASS"`

## Budget and Teardown Evidence

1. `runs/dev_substrate/m2_i/20260213T201427Z/budget_guardrail_snapshot.json`
2. `runs/dev_substrate/m2_i/20260213T201427Z/teardown_viability_snapshot.json`
3. `runs/dev_substrate/cost_guardrail/20260213T201456Z/cost_guardrail_snapshot.json`

## M4.C Incident Closure

1. Fail:
   - `runs/dev_substrate/m4/20260214T121004Z/m4_c_iam_binding_snapshot.json`
2. Materialization:
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.plan.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_role_materialization.apply.txt`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_demo_outputs_after_apply.json`
   - `runs/dev_substrate/m4/20260214T133434Z/m4_c_lane_role_policy_surface.json`
3. Pass:
   - `runs/dev_substrate/m4/20260214T134520Z/m4_c_iam_binding_snapshot.json`
   - `overall_pass = true`
   - `blockers = []`
4. Durable pass mirror:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T134520Z/m4_c_iam_binding_snapshot.json`

