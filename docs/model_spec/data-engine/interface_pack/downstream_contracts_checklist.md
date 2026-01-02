# Downstream Boundary Contracts Checklist

This checklist enumerates boundary contracts needed by non-engine components to consume the Data Engine interface. It does not redefine engine internals; it identifies missing platform-side contracts that should be specified alongside the narratives.

## Control & Ingress
- Run record surface contract (already exists):
  - `docs/model_spec/observability_and_governance/cross_cutting_rails/contracts/run_record.schema.yaml`
- Run discovery / run-facts locator surface (missing):
  - Proposed: `run_facts_view.schema.yaml` (contains array of output locators, HashGate receipts, run metadata).
- Ingestion gate receipt schema (missing):
  - Proposed: `ingestion_gate_receipt.schema.yaml` (schema validation outcome, dedupe status, arrival stamp).

## Real-time Decision Loop
- Decision log / audit record schema (missing):
  - Proposed: `decision_log_record.schema.yaml` (event ref, decision action, reasons, model/policy ids, feature snapshot hash, timing).
- Action outcome event schema (missing):
  - Proposed: `action_outcome_event.schema.yaml` (action id, result, idempotency key, error codes).
- Online feature snapshot schema (missing):
  - Proposed: `feature_snapshot.schema.yaml` (feature set id, values or pointer, snapshot hash).

## Label & Case
- Label store flow-level schema (missing):
  - Proposed: `label_flow.schema.yaml` (flow id, truth label, bank-view label, lifecycle state, timestamps).
- Label store event-level schema (missing):
  - Proposed: `label_event.schema.yaml` (event id, label, lifecycle state, timestamps).
- Case timeline schema (missing):
  - Proposed: `case_timeline.schema.yaml` (case id, linked entities, state transitions, outcomes).

## Learning & Evolution
- Offline feature snapshot schema (missing):
  - Proposed: `offline_feature_snapshot.schema.yaml` (feature set, window, snapshot hash, provenance).
- Training dataset manifest schema (missing):
  - Proposed: `training_dataset_manifest.schema.yaml` (cohort definition, label cutoff, feature schema refs, world ids).
- Model bundle / registry entry schema (missing):
  - Proposed: `model_bundle.schema.yaml` and `model_registry_entry.schema.yaml`.

## Observability & Governance
- Metrics envelope schema (missing):
  - Proposed: `metrics_envelope.schema.yaml` (metric name, value, dimensions, world ids, timestamps).
- Degrade ladder policy schema (missing):
  - Proposed: `degrade_policy.schema.yaml` (thresholds, actions, safe fallback order).
- Change-control receipt schema (missing):
  - Proposed: `change_control_receipt.schema.yaml` (approval ids, test evidence refs, rollout stage).

## Notes
- All contracts should use the shared ID types from:
  - `docs/model_spec/observability_and_governance/cross_cutting_rails/contracts/id_types.schema.yaml`
- Each schema should include `schema_ref`, enforce `additionalProperties: false`, and embed world/run identity where applicable.
