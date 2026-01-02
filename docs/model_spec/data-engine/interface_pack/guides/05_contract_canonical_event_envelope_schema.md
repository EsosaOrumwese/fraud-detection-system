# Guide: Derive `contracts/canonical_event_envelope.schema.yaml` (Binding)
Goal: define the envelope every engine-emitted event must carry (for ingestion/bus).

## A) Decide scope
This envelope is for platform interoperability:
- applies to RNG events (if ingested)
- applies to transaction stream events
- applies to any label/decision events emitted

## B) Required envelope fields (recommended minimal)
- event_id (dedupe key)
- event_type
- schema_version
- event_time (domain time)
- emitted_at (engine emission time)
- identity tags:
  - manifest_fingerprint
  - parameter_hash (if relevant)
  - seed (if relevant)
  - run_id / scenario_id (correlation)
- optional correlation:
  - trace_id, span_id, parent_event_id

## C) Derivation steps
1) Scan existing event schemas (e.g. rng_event_* in shared schemas)
2) Identify common header fields already used
3) Define envelope as a reusable `$defs.EventEnvelope`
4) Update specific event schemas (optional) to `allOf: [EventEnvelope, Payload]`

## D) Acceptance checks
- Works for both “stream events” and “audit events” without forcing irrelevant fields
- Field names align with existing contracts
