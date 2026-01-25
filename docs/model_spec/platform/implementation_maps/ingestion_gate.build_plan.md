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

#### Phase 2.1 — Active policy resolution + stamping
**Goal:** make all IG outcomes attributable to a specific policy revision and profile set.

**DoD checklist:**
- A single **ActivePolicyPointer** is resolved at IG startup and reload.
- `policy_rev` in receipts includes `policy_id`, `revision`, and `content_digest`.
- Policy changes are atomic (no half‑applied config across modules).
- `policy_rev` is emitted in logs/metrics for auditability.

#### Phase 2.2 — Ops index + lookup surfaces (receipts/quarantine)
**Goal:** make “what happened to my event?” and quarantine triage queryable without scanning object store or EB.

**DoD checklist:**
- Receipt index persisted (receipt_id, event_id, dedupe_key, decision, EB coords, reason codes, pins).
- Quarantine index persisted (quarantine_id, reason codes, pins, evidence ref).
- CLI or lightweight API can query by event_id or receipt_id.
- Index contents are consistent with object receipts (append‑only; no mutation).

#### Phase 2.3 — Health + ingress control (throttle/pause)
**Goal:** keep correctness under dependency failures and overload.

**DoD checklist:**
- Health probe evaluates EB connectivity, object‑store writes, and index DB availability.
- Explicit health state (`GREEN|AMBER|RED`) computed from thresholds.
- In RED: IG refuses intake or pauses bus consumption (fail‑closed).
- State transitions are logged with reason codes.

#### Phase 2.4 — Observability + governance facts
**Goal:** make IG behavior visible and produce governance‑worthy signals.

**DoD checklist:**
- Structured logs for admission path (validate→verify→dedupe→publish→receipt).
- Metrics counters/histograms for admit/duplicate/quarantine, latency, and backlog.
- Governance facts emitted to audit/control stream on policy change + quarantine spikes.
- All telemetry tagged with run pins and `policy_rev` when available.

### Phase 3 — Scale & replay readiness
**Intent:** ensure IG behaves predictably under load and replay.

#### Phase 3.1 — Replay/duplicate torture suite
**Goal:** prove at‑least‑once safety and receipt stability under heavy duplicates.

**DoD checklist:**
- Replay the same batch with duplicate rates ≥50%; EB appends only once per event_id.
- Duplicate admissions always return original EB coords + receipt ref.
- Receipts and ops index remain consistent under repeated replays.

#### Phase 3.2 — Load/soak stability + backpressure
**Goal:** validate IG behavior under sustained load and dependency degradation.

**DoD checklist:**
- Sustained admission throughput for N minutes without error spikes.
- Health probe transitions to AMBER/RED under injected failures and intake refuses on RED.
- No data loss: all inputs have receipts/quarantine evidence.

#### Phase 3.3 — Recovery drills (ops index + policy)
**Goal:** prove recovery after index loss or policy drift.

**DoD checklist:**
- Ops index rebuild restores lookup accuracy from object store.
- Policy digest mismatch detected and emitted as governance event.
- Audit stream contains activation + spike events for the test run.

## Status (rolling)
- Phase 1: complete (admission spine + run joinability + optional gate re-hash; unit tests added).
- Phase 2: complete (policy digesting + ops index + health/ingress control + governance/metrics; tests green).
- Phase 3: planning in progress (sections + DoD defined; implementation not started).
