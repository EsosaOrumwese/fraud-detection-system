# Real-Time Decision Loop Contracts (v0)
_As of 2026-01-31_

These schemas define **RTDL payloads** and **by-ref artifacts** used by IEG/OFP/DF/DL/AL/DLA.

## Envelope rule (binding)
All RTDL events published to a bus must be wrapped in the **canonical event envelope**:
`docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`

The schemas in this folder define **payloads** and **by-ref artifacts** that live inside the envelope
or are written to object storage (S3/MinIO) by reference.

## Event types (v0)
RTDL bus-visible payloads use stable `event_type` names with `schema_version = v1`.
- `decision_response`
- `action_intent`
- `action_outcome`
- `degrade_posture` (optional control/audit emission)

## Pins (v0)
RTDL payloads must carry **run identity** and **ContextPins**:
- Required pins: `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed`.
- `run_id` remains a legacy alias (when present it should match `scenario_run_id`).

## Provenance minimums
Decision/audit artifacts must carry:
- `run_config_digest` + `policy_rev`
- `eb_offset_basis` (exclusive-next offsets)
- `graph_version` (if IEG was consulted)
- `snapshot_hash` + optional snapshot ref
- `bundle_ref` and explicit `degrade_posture` (mode + capabilities_mask)

## Schema list
- `eb_offset_basis.schema.yaml`
- `graph_version.schema.yaml`
- `feature_snapshot.schema.yaml`
- `decision_payload.schema.yaml`
- `degrade_posture.schema.yaml`
- `action_intent.schema.yaml`
- `action_outcome.schema.yaml`
- `audit_record.schema.yaml`
