# Scenario Runner Build Plan (Living, Progressive Elaboration)
_As of 2026-01-24_

This plan is intentionally progressive: it starts as phase milestones, then expands only the current phase into sections with definition‑of‑done (DoD) checklists. Later phases remain high‑level until we enter them.

---

## Phase Summary (roadmap)
1) Phase 1 — Contracts + Truth Surfaces (COMPLETE)
2) Phase 2 — Durable storage + idempotency (COMPLETE)
3) Phase 3 — Evidence + gate verification completeness
4) Phase 4 — Engine invocation integration
5) Phase 5 — Control bus + re‑emit operations
6) Phase 6 — Observability + governance
7) Phase 7 — Security + ops hardening
8) Phase 8 — Integration tests + CI gates

---

## Phase 1 — Contracts + Truth Surfaces (COMPLETE)

### Definition of done (met)
- RunRequest, RunPlan, RunRecord, RunStatus, RunFactsView, RunReadySignal schemas exist and are versioned under SR contracts.
- Ingress and commit‑time schema validation wired and fail‑closed.
- Deterministic run_id + attempt_id + plan_hash derivations implemented.
- Core IP1/IP2/IP3/IP5 flows wired for v0 skeleton.
- Policy revision pinned into truth surfaces.

---

## Phase 2 — Durable storage + idempotency (COMPLETE)

### Scope intent
Make SR truth durable and correct under at‑least‑once behavior using persistent storage and a real idempotency/lease authority. This is “truth, not demos.”

### Implementation choices (current)
- Object store interface with Local + S3‑compatible backends (boto3).
- Authority store DSN with SQLite for local, Postgres for dev/prod (psycopg).

### Locked platform stack (decision)
- **Object storage:** Amazon S3.
- **Authority store:** Amazon RDS Postgres.
- **Runtime:** ECS Fargate.
- **Control bus:** Amazon Kinesis.

### Local dev stack (parity first)
To avoid drift, local dev should mirror AWS semantics:
- **Recommended:** MinIO (S3‑compatible) + Postgres container.
- **Not recommended:** Local filesystem + SQLite (only acceptable for quick smoke runs; not valid for Phase 2.5 hardening or correctness claims).
Phase 2.5 hardening tests must run against MinIO + Postgres where available.

### Section 2.1 — Object store abstraction (durable, by‑ref)
**Goal:** replace the local-only store with a real abstraction suitable for S3/MinIO and ensure atomic writes + by‑ref artifact refs are enforced.

**Definition of done**
- Introduce a storage interface with implementations for local filesystem and S3‑compatible backends.
- Writes are atomic (tmp + replace or multipart/etag strategy depending on backend).
- All SR artifacts are written by‑ref (paths/URIs only; no inline payloads in control bus).
- Artifact paths stay under `fraud-platform/sr/` and follow the SR contract layout.
- Ledger uses the storage abstraction exclusively (no direct filesystem writes).

### Section 2.2 — Idempotency binding + lease authority (real, durable)
**Goal:** ensure single‑writer correctness and safe duplicate handling across processes.

**Definition of done**
- Replace file‑based lease store with a durable backend (SQLite for local, Postgres for dev/prod).
- Lease acquire/renew/expire are transactional and race‑safe.
- Run‑equivalence binding is durable and conflict‑checked (intent_fingerprint mismatch rejects).
- Duplicate submissions return stable pointers without re‑executing side‑effects.
- Lease loss prevents any further writes from that worker.

### Section 2.3 — Ledger immutability + idempotent events
**Goal:** guarantee append‑only truths and monotonic status under retries.

**Definition of done**
- run_record is append‑only with idempotent event IDs (duplicate events are no‑ops).
- run_status transitions remain monotonic and validated; regressions are rejected.
- run_plan and run_facts_view are immutable after commit (drift raises errors).
- READY publish remains strictly ordered after facts_view + run_status READY commit.

### Section 2.4 — Tests + validation for Phase 2
**Goal:** prove correctness under duplicate submissions and lease contention.

**Definition of done**
- Unit tests for lease acquire/renew/expire semantics and idempotency binding.
- Integration tests for duplicate submits and concurrent leases (only one leader writes).
- Storage tests for atomic writes and by‑ref behavior (local + at least one object store backend).
- All Phase 2 tests logged in docs/logbook with results.

### Section 2.5 — Phase 2 hardening (rock‑solid durability)
**Goal:** eliminate correctness gaps in durable storage + idempotency before Phase 3.

**Definition of done**
- S3 writes for immutable artifacts use explicit write‑once semantics (e.g., `If-None-Match: *`).
- run_record append on S3 is CAS‑protected (ETag `If-Match`) **or** segmented into immutable chunks.
- Lease fencing enforced on state‑advancing writes; lease renewal during long runs.
- Distinguish missing vs access/network failures in object store operations (fail‑closed on errors).
- Postgres authority store exercised in test (smoke or integration) and logged.
- Concurrency tests for duplicate submissions and lease contention pass.

**Status:** COMPLETE (local parity tests passed on 2026-01-24).

---

## Phase 3 — Evidence + gate verification completeness
High‑level intent: enforce full HashGate coverage and instance‑proof binding (seed/scenario/run_id) with deterministic COMPLETE/WAITING/FAIL/CONFLICT outcomes.

**Status:** COMPLETE (parity reuse targets deep gate 6A; unknown gate/output handling added; SR tests green).

### Section 3.1 — Gate closure + required set
**Goal:** compute the authoritative gate closure for intended outputs.

**Definition of done**
- Required gates derive from interface pack (gate map + output catalogue) and are deterministic.
- Unknown output_id or gate_id fails closed.
- Output read_requires_gates are enforced.

### Section 3.2 — Receipt validation + scope binding
**Goal:** validate gate receipts and enforce scope‑appropriate pin binding.

**Definition of done**
- Gate receipts are validated against schemas before use.
- Instance‑scoped gates enforce pins (seed/scenario_id/run_id/parameter_hash); broader gates do not require instance pins.
- Receipt scope mismatch → FAIL/QUARANTINE.
- Instance‑scoped outputs emit SR verifier receipts under `fraud-platform/sr/instance_receipts/...` with drift detection.

### Section 3.3 — Output locator integrity
**Goal:** produce immutable, verifiable output locators for all intended outputs.

**Definition of done**
- Locator schema validation passes for all outputs.
- content_digest computed deterministically for file/dir/glob outputs.
- Missing outputs follow WAITING→FAIL semantics with evidence_deadline.

### Section 3.4 — Evidence classification + bundle hash
**Goal:** deterministic COMPLETE/WAITING/FAIL/CONFLICT outcomes.

**Definition of done**
- Evidence bundle hash is stable across retries (sorted locators/receipts + policy_rev).
- Explicit, stable reason codes for WAITING/FAIL/CONFLICT.
- Fail‑closed on unknown compatibility or malformed receipts.

### Section 3.5 — Tests + validation
**Goal:** prove evidence logic under mismatches and conflicts.

**Definition of done**
- Unit tests for gate scope binding, missing receipts, and conflict detection.
- Receipt drift test: pre‑seed mismatching receipt → FAIL with reason `INSTANCE_RECEIPT_DRIFT`.
- Integration tests using real engine artefacts (local parity stack).
  - Full SR reuse flow with real engine run root (locators + gates + receipts + READY).
  - Negative evidence case (missing gate flag or output) → WAITING/FAIL as expected.
- Interface pack now carries gate hashing laws for 2A/2B/3B/5A/5B/6A (index‑driven, 2B run‑root base, 6A index‑order); gate‑verifier tests cover these segments.
- All Phase 3 tests logged with results.

---

## Phase 4 — Engine invocation integration
High‑level intent: real job runner adapter with attempt lifecycle, retries, and idempotency.

**Status:** IN PROGRESS (all Section 4.1–4.5 work implemented; awaiting phase sign‑off).

### Section 4.1 — Invocation adapter interface (engine remains black box)
**Goal:** define a stable invoker interface with clear inputs/outputs and no engine internals.

**Definition of done**
- Invoker contract includes: engine_run_root, manifest_fingerprint, parameter_hash, seed, scenario_id, run_id, attempt_id.
- Invoker returns: outcome (SUCCEEDED/FAILED), reason_code, duration, run_receipt_ref (if any), logs_ref (optional).
- Local subprocess adapter implemented for dev with deterministic run root and captured stdout/stderr.
- No credentials or platform secrets in code.

### Section 4.2 — Attempt lifecycle + idempotency
**Goal:** record attempts in append‑only ledger and enforce retry limits safely.

**Definition of done**
- Attempt record schema exists and is appended per attempt (attempt_id, started_at, ended_at, outcome, reason, run_receipt_ref).
- attempt_id is deterministic per (run_id, attempt_number, invoker_id).
- attempt_limit enforced; additional attempts rejected with reason code `ATTEMPT_LIMIT_EXCEEDED`.
- Failed attempts do not mutate run facts; only success proceeds to evidence collection.

### Section 4.3 — Receipt gating (post‑attempt validation)
**Goal:** validate run receipts before evidence collection.

**Definition of done**
- Missing run receipt after SUCCEEDED attempt → FAIL with `ENGINE_RECEIPT_MISSING`.
- Invalid run receipt schema → FAIL with `ENGINE_RECEIPT_INVALID`.
- Receipt pins (manifest_fingerprint / parameter_hash / seed / scenario_id) match the run intent (fail‑closed on mismatch).

### Section 4.4 — Failure taxonomy + messaging
**Goal:** explicit, stable reason codes for engine failures.

**Definition of done**
- Reason codes include `ENGINE_EXIT_NONZERO`, `ENGINE_RECEIPT_MISSING`, `ENGINE_RECEIPT_INVALID`, `ENGINE_RECEIPT_MISMATCH`.
- Terminal failures are committed with these codes and surfaced in RunStatus.
- Narrative logs describe attempt start/end and reason.

### Section 4.5 — Tests + validation
**Goal:** prove attempt handling and receipt gating.

**Definition of done**
- Unit tests for attempt record creation + retry limit enforcement.
- Integration test for local invoker with a stub engine (non‑zero exit and missing receipt cases).
- Test results logged in docs/logbook.

---

## Phase 5 — Control bus + re‑emit operations
High‑level intent: publish READY to a real bus with idempotent keys; implement re‑emit (N7).

---

## Phase 6 — Observability + governance
High‑level intent: structured event taxonomy, metrics/traces, audit‑ready provenance stamps.

---

## Phase 7 — Security + ops hardening
High‑level intent: authn/authz, secrets hygiene, quarantine workflows, operator tooling.

---

## Phase 8 — Integration tests + CI gates
High‑level intent: golden path + duplicate + reuse + fail‑closed + re‑emit + correction tests; contract compatibility checks in CI.
