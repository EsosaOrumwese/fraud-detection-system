# Scenario Runner Contracts
Status: v0 (authoritative for SR runtime validation)
Contains JSON Schema for SR request + truth artifacts.

Compatibility notes:
- `run_facts_view` now uses digest objects (`{algo, hex}`) and gate receipt artifacts aligned with engine contracts.
- `run_facts_view` may include optional `instance_receipts` for instance-scoped outputs.
 - `run_facts_view` and `run_ready_signal` may include an optional `oracle_pack_ref` block that links control-plane readiness to the external Oracle Store pack (by-ref only).
  - `oracle_pack_ref` may also carry Oracle stream authority refs (`scenario_id`, `stream_view_root`, `stream_view_output_refs`) for downstream by-ref resolution.
  - SR emits **verifier receipts** into its own object store (black-box safe), under:
    `fraud-platform/<platform_run_id>/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`
- Phase 5 additions:
  - `reemit_request.schema.yaml` defines the ops re-emit contract.
    - includes optional `emit_platform_run_id` and `cross_run_override` evidence block for governed cross-run re-emit posture.
  - `run_terminal_signal.schema.yaml` defines terminal control signals for re-emit.
