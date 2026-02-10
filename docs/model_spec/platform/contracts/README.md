# Platform Contracts Index (v0)
_As of 2026-01-25_

This index points to **authoritative contracts** used across the platform.  
It avoids duplicating engine contracts and reduces drift.

## Boundary contracts (authoritative)

### Canonical Event Envelope (IG/EB boundary)
`docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`

### Engine Output Locator (by‑ref addressing)
`docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml`

### Gate Receipt (no‑PASS‑no‑read)
`docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml`

### Instance Proof Receipt (instance‑scoped outputs)
`docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml`

---

## Platform‑native contracts (SR, v0)
These live under:
`docs/model_spec/platform/contracts/scenario_runner/`

## Platform‑native contracts (IG, v0)
These live under:
`docs/model_spec/platform/contracts/ingestion_gate/`

- `ingestion_receipt.schema.yaml`
- `quarantine_record.schema.yaml`
- `ig_policy_activation.schema.yaml`
- `ig_quarantine_spike.schema.yaml`
- `ig_pull_run.schema.yaml` (legacy pull-only; deprecated)
- `ig_audit_verify.schema.yaml`

## Platform‑native contracts (Oracle Store, v0)
These live under:
`docs/model_spec/platform/contracts/oracle_store/`

- `oracle_pack_manifest.schema.yaml`
- `oracle_pack_seal.schema.yaml`

## Platform‑native contracts (Event Bus, v0)
These live under:
`docs/model_spec/platform/contracts/event_bus/`

- `eb_ref.schema.yaml`

## Platform‑native contracts (RTDL, v0)
These live under:
`docs/model_spec/platform/contracts/real_time_decision_loop/`

- `eb_offset_basis.schema.yaml`
- `graph_version.schema.yaml`
- `feature_snapshot.schema.yaml`
- `ofp_get_features_request.schema.yaml`
- `ofp_get_features_response.schema.yaml`
- `ofp_get_features_error.schema.yaml`
- `ofp_ofs_parity_contract_v0.md`
- `decision_payload.schema.yaml` (`decision_response` payload schema)
- `degrade_posture.schema.yaml`
- `action_intent.schema.yaml`
- `action_outcome.schema.yaml`
- `audit_record.schema.yaml`

## Platform-native contracts (Archive, v0)
These live under:
`docs/model_spec/platform/contracts/archive/`

- `archive_event_record_v0.schema.yaml`

## Platform-native contracts (Case + Labels, v0)
These live under:
`docs/model_spec/platform/contracts/case_and_labels/`

- `case_trigger.schema.yaml`
- `case_timeline_event.schema.yaml`
- `label_assertion.schema.yaml`

## Platform-native contracts (Learning + Registry, v0)
These live under:
`docs/model_spec/platform/contracts/learning_registry/`

- `dataset_manifest_v0.schema.yaml`
- `eval_report_v0.schema.yaml`
- `bundle_publication_v0.schema.yaml`
- `registry_lifecycle_event_v0.schema.yaml`
- `df_bundle_resolution_v0.schema.yaml`
