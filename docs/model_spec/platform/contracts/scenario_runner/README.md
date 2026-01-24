# Scenario Runner Contracts
Status: v0 (authoritative for SR runtime validation)
Contains JSON Schema for SR request + truth artifacts.

Compatibility notes:
- `run_facts_view` now uses digest objects (`{algo, hex}`) and gate receipt artifacts aligned with engine contracts.
- `run_facts_view` may include optional `instance_receipts` for instance-scoped outputs.
