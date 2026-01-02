# Guide: Derive `contracts/engine_invocation.schema.yaml` (Binding)
Goal: define what Scenario Runner (or orchestrator) sends to the Data Engine.

## A) Primary sources
- Implementation entrypoint (CLI/API) for the engine run
- Any existing schema/contract for run requests
- Expanded docs where engine identity is described

## B) Minimal required fields
- parameter_hash
- manifest_fingerprint
- seed
- scenario_id (if used)
- run_id (if used; logs-only)
- request_id / idempotency_key (recommended)
- optional: scenario definition ref(s), limits, knobs (only if stable)

## C) How to derive
1) Find engine entrypoint in code:
   - CLI args, config object, or API request model
2) Identify which fields are required vs optional
3) Map each required field to:
   - type, format constraints (hex length, uint64, etc.)
4) Add `additionalProperties: false` unless you intentionally allow extras
5) Add examples in `examples/engine_invocation.min.json`

## D) Acceptance checks
- Schema compiles
- Identity fields match those used in paths/logs
- Does not include internal segment knobs unless explicitly intended
