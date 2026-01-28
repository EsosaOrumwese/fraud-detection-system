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
- `ig_pull_run.schema.yaml`
- `ig_audit_verify.schema.yaml`

## Platform‑native contracts (Oracle Store, v0)
These live under:
`docs/model_spec/platform/contracts/oracle_store/`

- `oracle_pack_manifest.schema.yaml`
- `oracle_pack_seal.schema.yaml`
