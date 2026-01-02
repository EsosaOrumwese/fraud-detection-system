# Guide: Derive `contracts/engine_output_locator.schema.yaml` (Binding)
Goal: define a standard “pin” object used to reference engine outputs in run facts.

## A) Required fields
- output_id
- manifest_fingerprint
- path
- schema_ref (or schema_id)
- partitions (optional object: seed/run_id/scenario_id/parameter_hash)
- content_digest (optional but recommended)
- produced_at (optional)

## B) Derivation steps
1) Identify how Scenario Runner will expose run discovery (`run_facts_view`)
2) Make output_locator the reusable element type inside run facts
3) Ensure locator references match output_ids in catalogue

## C) Acceptance checks
- output_id enum can be validated against catalogue (optional in schema; enforce in code)
- supports both fingerprint-only and run-scoped outputs
