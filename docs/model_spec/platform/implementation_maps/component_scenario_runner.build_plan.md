# Scenario Runner Build Plan (Living, Progressive Elaboration)
_As of 2026-01-24_

This plan is intentionally progressive: it starts as phase milestones, then expands only the current phase into sections with definition‑of‑done (DoD) checklists. Later phases remain high‑level until we enter them.

---

## Phase Summary (roadmap)
1) Phase 1 — Contracts + Truth Surfaces (COMPLETE)
2) Phase 2 — Durable storage + idempotency (NEXT)
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

## Phase 2 — Durable storage + idempotency (NEXT)

### Scope intent
Make SR truth durable and correct under at‑least‑once behavior using persistent storage and a real idempotency/lease authority. This is “truth, not demos.”

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

---

## Phase 3 — Evidence + gate verification completeness
High‑level intent: enforce full HashGate coverage and instance‑proof binding (seed/scenario/run_id) with deterministic COMPLETE/WAITING/FAIL/CONFLICT outcomes.

---

## Phase 4 — Engine invocation integration
High‑level intent: real job runner adapter with attempt lifecycle, retries, and idempotency.

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

