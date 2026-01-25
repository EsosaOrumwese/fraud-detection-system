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
