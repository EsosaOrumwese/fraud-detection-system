# Real-Time Decision Loop Contracts (v0)
_As of 2026-01-31_

These schemas define **RTDL payloads** and **by-ref artifacts** used by IEG/OFP/DF/DL/AL/DLA.

## Envelope rule (binding)
All RTDL events published to a bus must be wrapped in the **canonical event envelope**:
`docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`

The schemas in this folder define **payloads** and **by-ref artifacts** that live inside the envelope
or are written to object storage (S3/MinIO) by reference.

## Schema list
- `eb_offset_basis.schema.yaml`
- `graph_version.schema.yaml`
- `feature_snapshot.schema.yaml`
- `decision_payload.schema.yaml`
- `degrade_posture.schema.yaml`
- `action_intent.schema.yaml`
- `action_outcome.schema.yaml`
- `audit_record.schema.yaml`
