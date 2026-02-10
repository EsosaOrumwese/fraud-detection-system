# Case + Labels Contracts (v0)
_As of 2026-02-09_

These schemas define Phase 5.1 cross-plane contracts for:
- case trigger intake,
- append-only case timeline events,
- label assertions written to Label Store.

## Identity and idempotency posture (v0)
- `case_id = H(CaseSubjectKey)[:32]`, where `CaseSubjectKey=(platform_run_id,event_class,event_id)`.
- `case_trigger_id = H(case_id + trigger_type + source_ref_id)[:32]`.
- `case_timeline_event_id = H(case_id + timeline_event_type + source_ref_id)[:32]`.
- `label_assertion_id = H(case_timeline_event_id + LabelSubjectKey + label_type)[:32]`.

## Payload hash canonicalization rule (v0)
- Canonical hash excludes transport metadata and uses stable ordering.
- `evidence_refs` are sorted by `(ref_type, ref_id, ref_scope)` before hashing.
- Same deterministic key + different canonical payload hash is treated as anomaly/fail-closed.

## Schema list
- `case_trigger.schema.yaml`
- `case_timeline_event.schema.yaml`
- `label_assertion.schema.yaml`
