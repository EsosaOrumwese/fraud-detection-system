# Ingestion Gate Build Plan (v0)
_As of 2026-01-25_

## Purpose
Provide a progressive, component‑scoped build plan for the Ingestion Gate (IG). This plan is detailed only as phases begin, per platform rules.

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half‑baked phases: do not advance until DoD is fully satisfied.
- Rails are non‑negotiable: ContextPins, canonical envelope, no‑PASS‑no‑read, by‑ref receipts, idempotency, append‑only truth, deterministic partitioning.

## Phase plan (v0)

### Phase 1 — Admission boundary core
**Intent:** enforce schema + lineage + gate verification and emit receipts with by‑ref evidence.

#### Phase 1.1 — Envelope + schema policy
**Goal:** validate canonical envelope and versioned payload schemas.

**DoD checklist:**
- Canonical envelope validated against `canonical_event_envelope.schema.yaml`.
- Payload schema versioning enforced via policy (allowlist per `event_type` + version).
- ContextPins requirements enforced per class (traffic/control/audit).

#### Phase 1.2 — Gate verification + lineage
**Goal:** enforce “no PASS → no read” before admission.

**DoD checklist:**
- Required engine gates verified for run/world scope via SR join surface.
- Missing/invalid PASS evidence fails closed (QUARANTINE or WAITING per policy).
- Receipts include by‑ref evidence pointers (gate receipt refs, SR run_facts_view ref).

#### Phase 1.3 — Idempotency + dedupe
**Goal:** admit duplicates safely under at‑least‑once.

**DoD checklist:**
- Deterministic dedupe key per event class.
- Duplicate admissions return the original EB ref and/or receipt ref.
- Dedupe logic is stable under retries.

#### Phase 1.4 — Deterministic partitioning + EB append
**Goal:** stamp partition key deterministically and append to EB.

**DoD checklist:**
- `partitioning_profile_id` is applied per stream class.
- EB ACK implies durable append with `(stream, partition, offset)`.
- ADMITTED receipt is emitted only when EB coordinates exist.

#### Phase 1.5 — Receipt + quarantine storage
**Goal:** persist admission outcomes and evidence by‑ref.

**DoD checklist:**
- Receipts written to `ig/receipts/` by‑ref with schema validation.
- Quarantine evidence stored under `ig/quarantine/` with reason codes.
- No secret material is written into receipts/evidence.

### Phase 2 — Control plane + operations hardening
**Intent:** add governance hooks, observability, and operational safety.

**DoD (high level):**
- Policy revision stamping on receipts.
- Governance facts emitted for policy changes and quarantine spikes.
- OTel metrics/logs with ContextPins tags.

### Phase 3 — Scale & replay readiness
**Intent:** ensure IG behaves predictably under load and replay.

**DoD (high level):**
- Load/soak tests with duplicate traffic patterns.
- Replay simulations validate idempotency and receipt stability.

## Status (rolling)
- Phase 1: complete (admission spine + run joinability + optional gate re-hash; unit tests added).
- Phase 2+: not started.
