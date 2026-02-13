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
- ContextPins requirements enforced per class (traffic/control/audit/context).

#### Phase 1.2 — Gate verification + lineage
**Goal:** enforce “no PASS → no read” before admission.

**DoD checklist:**
- Required engine gates verified for run/world scope via SR join surface.
- Missing/invalid PASS evidence fails closed (QUARANTINE or WAITING per policy).
- Receipts include by‑ref evidence pointers (gate receipt refs, SR run_facts_view ref).

#### Phase 1.3 — Idempotency + dedupe
**Goal:** admit duplicates safely under at‑least‑once.

**DoD checklist:**
- Deterministic dedupe tuple `(platform_run_id, event_class, event_id)`.
- `payload_hash` persisted for anomaly detection (same tuple + different hash -> QUARANTINE).
- Duplicate admissions return the original EB ref and/or receipt ref.
- Dedupe logic is stable under retries.

#### Phase 1.4 — Deterministic partitioning + EB append
**Goal:** stamp partition key deterministically and append to EB.

**DoD checklist:**
- `partitioning_profile_id` is applied per stream class (traffic + context + control + audit).
- EB ACK implies durable append with `(stream, partition, offset)`.
- ADMITTED receipt is emitted only when EB coordinates exist.

#### Phase 1.4a — Admission state machine (publish ambiguity)
**Goal:** handle unknown publish outcomes without double‑publishing.

**DoD checklist:**
- Admission row created as `PUBLISH_IN_FLIGHT` before publish.
- On ACK, transition to `ADMITTED` with `eb_ref`.
- On timeout/unknown, transition to `PUBLISH_AMBIGUOUS` with no auto‑republish.

#### Phase 1.5 — Receipt + quarantine storage
**Goal:** persist admission outcomes and evidence by‑ref.

**DoD checklist:**
- Receipts written to `ig/receipts/` by‑ref with schema validation.
- Quarantine evidence stored under `ig/quarantine/` with reason codes.
- Receipts include `event_class`, `payload_hash`, `admitted_at_utc`, and both run ids.
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

### Phase 4 — Serviceization + READY automation
**Intent:** turn IG into a deployable service with control‑plane triggered pull ingestion and durable pull checkpoints.

#### Phase 4.1 — Service boundary (HTTP + CLI parity)
**Goal:** provide a stable service interface for push and pull ingestion with explicit error surfaces.

**DoD checklist:**
- HTTP service wrapper can start from a single profile and exposes:
  - push ingestion (canonical envelope)
  - pull ingestion (run_facts_view ref or run_id)
  - ops lookups (event_id/receipt_id/dedupe_key) + health
- Requests validated against canonical envelope and policy allowlist.
- Responses include receipt refs and decision status; non‑admission returns reason codes.
- Service logs include admission phases (validate → verify → dedupe → publish → receipt).

#### Phase 4.2 — READY trigger consumption (control bus)
**Goal:** automatically pull ingest when SR publishes READY.

**DoD checklist:**
- Control bus consumer subscribes to `fp.bus.control.v1` and filters READY events.
- READY message ids are deduped (idempotent replays do not double‑ingest).
- Pull ingestion uses `run_facts_view` ref from READY signal; fail‑closed if missing/invalid.
- Per‑run ingestion emits a governance fact with counts and outcome.

#### Phase 4.3 — Pull ingestion checkpoints + recovery
**Goal:** survive interruptions and allow deterministic resume.

**DoD checklist:**
- Each pull ingestion creates a durable `ingestion_run_record` with start/end times, output ids, and counts.
- Checkpointing records progress per output_id (or per locator) to allow resume.
- Re‑runs are idempotent: already‑processed outputs are skipped based on recorded checkpoints.
- Ops index can be rebuilt to include pull ingestion receipts.

### Phase 5 — Production hardening
**Intent:** harden IG for production security, reliability, and non‑local environments.

#### Phase 5.1 — AuthN/AuthZ boundary
**Goal:** ensure only authorized producers and operators can trigger ingestion.

**DoD checklist:**
- Request authentication enforced for push ingress (mTLS/API key/JWT; profile‑driven).
- READY consumer validates provenance (allowed topics + message signature/allowlist).
- Unauthorized requests return explicit reason codes; no partial processing.

#### Phase 5.2 — Non‑local object store support for pull
**Goal:** allow IG to pull run_facts_view from S3‑style object stores.

**DoD checklist:**
- Run facts ref resolution supports `s3://` and by‑ref paths.
- Object store reads are retried with bounded backoff.
- Missing/invalid refs fail closed with explicit reason codes.

#### Phase 5.3 — Resilience + backpressure
**Goal:** protect EB and downstream from overload or dependency failure.

**DoD checklist:**
- Circuit breakers for EB publish and object store operations.
- Configurable rate limits for push ingress + READY pull.
- Health transitions (AMBER/RED) block intake when thresholds exceeded.

#### Phase 5.4 — Ops runbook + alerts
**Goal:** provide operational clarity for on‑call responders.

**DoD checklist:**
- Runbook updated with common failure modes + recovery steps.
- Alerts defined for health state changes, quarantine spikes, READY failures.
- Metrics include per‑phase latency (validate→verify→publish→receipt).

### Phase 6 — Scale + governance hardening
**Intent:** support horizontal scale and audit‑grade integrity.

#### Phase 6.1 — Horizontal READY consumer
**Goal:** allow multiple IG instances without duplicate pull ingestion.

**DoD checklist:**
- Distributed lease/lock on READY message processing.
- Exactly‑once processing per message_id (at‑least‑once transport safe).

#### Phase 6.2 — Pull sharding + checkpoints
**Goal:** scale pull ingestion across large outputs.

**DoD checklist:**
- Shard pull by output_id or locator range with deterministic partitioning.
- Checkpoints record shard progress and allow resume without duplicates.

#### Phase 6.3 — Integrity + audit proofing
**Goal:** strengthen provenance and audit evidence.

**DoD checklist:**
- Optional hash chain for pull run events (tamper‑evident).
- Governance facts include policy_rev + run pins + READY bundle hash.
- Periodic audit job validates receipt/index parity.

#### Phase 6.4 — Local smoke time budget (operator guardrail)
**Goal:** allow bounded local pull runs without weakening production defaults.

**DoD checklist:**
- Wiring supports `pull_time_budget_seconds` (optional).
- Budget exhaustion emits `TIME_BUDGET_EXCEEDED` and halts further outputs.
- Local profile sets a default cap (10 minutes).
- Unit test validates deterministic budget behavior.

---

## Phase 7 — Streaming‑only alignment (docs + contracts)
_This alignment supersedes the legacy pull‑ingest posture. IG becomes **push‑only**; READY/pull paths are retired._

**Intent:** remove ambiguity: IG is a push boundary only; SR READY is a trigger for WSP (not IG).

**DoD checklist:**
- IG design authority and narratives explicitly state **push‑only** ingestion.
- Any IG docs that mention READY‑triggered pull are marked **legacy/retired**.
- Profiles remove READY/pull wiring in the default path (kept only as deprecated legacy stubs if necessary).

## Phase 8 — Streaming‑only alignment (implementation retirement)
**Intent:** remove READY consumer + pull ingestion code paths to prevent drift.

**DoD checklist:**
- READY consumer, pull store, and pull ingestion APIs are removed or hard‑disabled.
- `run_facts_view` is no longer a runtime dependency for IG.
- IG config fails closed if pull‑only settings are supplied (explicit error).
- Push ingestion path remains unchanged and hardened.

## Phase 9 — Streaming‑only alignment (validation)
**Intent:** prove IG is stable without any pull path.

**DoD checklist:**
- Push ingestion tests remain green (schema + dedupe + receipts).
- No tests rely on READY/pull ingestion.
- Local smoke: WSP → IG push‑only path validated.

## Status (rolling)
- Note: Phases 4–6 describe the legacy pull path; retired by the Phase 7–8 streaming‑only alignment.
- Phase 1: complete (admission spine + run joinability + optional gate re-hash; unit tests added).
- Phase 2: complete (policy digesting + ops index + health/ingress control + governance/metrics; tests green).
- Phase 3: complete (replay/load/recovery tests added; suite green + SR‑artifact smoke test).
- Phase 4: complete (service boundary + READY consumer + pull checkpoints implemented; Phase‑4 tests green).
- Phase 5: complete (auth/rate limits + S3 run_facts support + retries/backpressure + per-phase metrics + runbook/alerts; tests green).
- Phase 6: in progress (READY leases, optional sharding checkpoints, hash-chain integrity, audit CLI; time-budget guard done).
- Phase 7: complete (streaming‑only docs + contracts alignment).
- Phase 8: complete (pull/READY implementation removed; config fails closed).
- Phase 9: complete (push‑only validation; WSP→IG local parity smoke executed).

**v0 green summary (IG):** push‑only ingestion, run‑scoped receipts/health/quarantine in MinIO, EB publish refs recorded for traffic + context topics, local parity smoke confirmed.
