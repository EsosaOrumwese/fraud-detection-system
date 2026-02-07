# Decision Fabric Trigger Policy (v0)

This folder pins Decision Fabric inlet trigger policy for RTDL.

## Files
- `trigger_policy_v0.yaml`
- `registry_resolution_policy_v0.yaml`

## v0 intent
- Only admitted traffic topics are trigger-eligible.
- Context/control/audit topics are never decision triggers.
- Trigger event types are explicit and versioned (`event_type` + allowed `schema_versions`).
- Loop-prevention blocks DF/AL/IG output families from retriggering DF.
- Required pins are validated at inlet before candidate creation.
- Registry bundle resolution is deterministic by explicit scope key axes:
  - `environment`
  - `mode`
  - `bundle_slot`
  - `tenant_id` (optional)
- Registry compatibility mismatches fail closed by default unless bounded fallback policy is explicitly configured.

## Change discipline
- Bump `revision` when trigger semantics change.
- Keep `policy_id` stable within this policy family.
- Do not silently widen allowlists without corresponding implementation-map/logbook note.
