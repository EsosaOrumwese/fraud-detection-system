# Scenario Runner Contracts

Binding JSON Schemas owned by Scenario Runner. These define the control-plane request,
scenario definition, and discovery surfaces used by downstream components.

## Contracts

- `scenario_run_request.schema.yaml` - tool-agnostic request to plan/create a run.
- `scenario_definition.schema.yaml` - scenario catalogue item (read-only authority surface).
- `run_facts_view.schema.yaml` - discovery surface for active runs and pinned references.
- `run_status_event.payload.schema.yaml` - optional payload-only status change event (envelope is Rails-owned).

## Notes

- These schemas MUST align with Platform Rails and the Data Engine Interface Pack boundaries.
- Examples live in `../examples/`.
