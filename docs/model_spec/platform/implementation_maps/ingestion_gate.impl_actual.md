# Ingestion Gate Implementation Map
_As of 2026-01-25_

---

## Entry: 2026-01-25 06:07:06 — IG v0 planning start

### Problem / goal
Stand up the Ingestion Gate (IG) as the platform’s admission authority. IG must validate canonical envelopes, enforce schema + lineage + gate policies, stamp deterministic partition keys, append to EB, and emit receipts/quarantine evidence by‑ref.

### Authorities / inputs (binding)
- Root AGENTS.md (rails: ContextPins, no‑PASS‑no‑read, by‑ref, idempotency, append‑only, fail‑closed).
- Platform rails/substrate docs (platform_rails_and_substrate_v0.md, by‑ref validation checklist, partitioning policy guidance).
- Engine interface pack contracts (canonical_event_envelope, gate_receipt, engine_output_locator, instance_proof_receipt).
- IG design‑authority doc (component‑specific).

### Decision trail (initial)
- IG plan must be component‑scoped and progressive‑elaboration; Phase 1 broken into envelope/schema, gate verification, idempotency, partitioning, and receipt/quarantine storage.
- IG must never become a “transformer”; it validates and admits only, emitting receipts with by‑ref evidence.
- Partitioning policy is explicit and versioned (`partitioning_profile_id`), with IG stamping partition_key; EB never infers routing.

### Planned mechanics (Phase 1 focus)
- **Envelope validation:** validate canonical envelope + versioned payload schema with allowlist policy.
- **Lineage + gate checks:** verify required PASS gates via SR join surface; fail‑closed on missing/invalid evidence.
- **Idempotency:** deterministic dedupe key; duplicates return original EB ref/receipt.
- **EB append:** admitted only when EB returns `(stream, partition, offset)`; receipts record EB ref.
- **Quarantine:** store evidence by‑ref under `ig/quarantine/` with reason codes.

### Open items / risks
- Exact schema for IG receipts and quarantine records (must align with platform pins and avoid secret material).
- Policy format for schema acceptance and partitioning profiles (initial stubs exist; may need expansion).

---

## Entry: 2026-01-25 06:18:07 — IG Phase 1 implementation plan (component scope)

### Problem / goal
Implement IG Phase 1 admission boundary: schema + lineage + gate verification, idempotent admission, deterministic partitioning, and receipts/quarantine by‑ref. This is the minimal production‑shaped IG that can ingest engine traffic (pull) and producer traffic (push) under the same outcome semantics.

### Inputs / authorities
- IG design‑authority doc (pinned overview + joins; push + pull ingestion modes).
- Platform rails/substrate docs (canonical envelope, by‑ref validation checklist, partitioning policy guidance, secrets posture).
- Engine interface pack contracts + catalogue (canonical envelope, engine_output_locator, gate_receipt, instance_proof_receipt, engine_outputs.catalogue.yaml roles).
- Platform contracts index + profiles (`config/platform/profiles/*`, `config/platform/ig/partitioning_profiles_v0.yaml`).

### Live decisions / reasoning
- **No engine streaming assumption.** IG supports **push ingestion** (producers already framed) and **pull ingestion** (engine outputs after SR READY). Pulling from engine outputs does *not* require engine to stream; v0 can frame from materialized outputs referenced by `sr/run_facts_view`.
- **Single admission spine.** Both push and pull modes must converge into the same admission pipeline so receipts, dedupe, partitioning, and EB semantics remain identical.
- **Component layout.** Create a new `src/fraud_detection/ingestion_gate/` package and a thin service wrapper under `services/ingestion_gate/` for consistency with SR; leave legacy `services/ingestion/` untouched as placeholder.
- **Deterministic identity.** If upstream payload lacks `event_id`, IG must derive a deterministic `event_id` from stable keys + pins (for engine rows, use output_id + primary keys + pins).
- **Partitioning is policy.** IG uses `partitioning_profiles_v0.yaml`; no inference by EB or ad‑hoc selection in code.

### Planned implementation steps (Phase 1)
1) **Contracts + policy stubs**
   - Add `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`.
   - Add `docs/model_spec/platform/contracts/ingestion_gate/quarantine_record.schema.yaml` (by‑ref evidence pointers + reason codes).
   - Add `config/platform/ig/schema_policy_v0.yaml` (allowlist per event_type/version + class).
   - Add `config/platform/ig/class_map_v0.yaml` (event_type → class: traffic/control/audit; required pins).

2) **Core package skeleton (src)**
   - `src/fraud_detection/ingestion_gate/models.py` (Envelope, AdmissionDecision, Receipt, QuarantineRecord).
   - `src/fraud_detection/ingestion_gate/schema.py` (canonical envelope validation + payload schema policy).
   - `src/fraud_detection/ingestion_gate/partitioning.py` (partition_key derivation from profile).
   - `src/fraud_detection/ingestion_gate/dedupe.py` (dedupe key, deterministic event_id derivation).
   - `src/fraud_detection/ingestion_gate/engine_pull.py` (read SR run_facts_view → fetch engine traffic outputs → frame rows to canonical envelope).
   - `src/fraud_detection/ingestion_gate/admission.py` (single admission spine: validate → gate check → dedupe → partition → EB append → receipt).
   - `src/fraud_detection/ingestion_gate/receipts.py` (write receipts/quarantine by‑ref to object store).
   - `src/fraud_detection/ingestion_gate/store.py` (object store + optional receipt index abstraction; local FS and S3 variants).

3) **Service wrapper + CLI**
   - `services/ingestion_gate/` minimal HTTP endpoint for push ingestion and a CLI/runner for pull ingestion.

4) **Tests**
   - Unit: envelope validation, schema allowlist, partitioning determinism, dedupe key derivation.
   - Integration: pull ingestion from engine artifacts (use local_full_run fixture), verify gate enforcement and receipt writing.
   - EB publish stub tests (LocalStack/Kinesis) for admission ACK semantics.

### Invariants to enforce (explicit)
- **No PASS → no read** (missing/invalid gate evidence = quarantine/waiting).
- **ADMITTED iff EB acked** and `(stream, partition, offset)` exists in receipt.
- **Deterministic partitioning** from policy profiles only.
- **Receipts/quarantine are by‑ref** and never contain secret material.

### Open items / risks
- Receipt/quarantine schemas must align with platform pins and avoid payload bloat.
- Push ingestion authN/authZ profile (allowlists) to be pinned for prod; v0 can be permissive but must be explicit.

---
