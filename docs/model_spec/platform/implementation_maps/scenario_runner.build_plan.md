# Scenario Runner Build Plan (Living, Progressive Elaboration)
_As of 2026-01-24_

This plan is intentionally progressive: it starts as phase milestones, then expands only the current phase into sections with definition‑of‑done (DoD) checklists. Later phases remain high‑level until we enter them.

---

## Phase Summary (roadmap)
1) Phase 1 — Contracts + Truth Surfaces (COMPLETE)
2) Phase 2 — Durable storage + idempotency (COMPLETE)
3) Phase 3 — Evidence + gate verification completeness (COMPLETE)
4) Phase 4 — Engine invocation integration (COMPLETE)
5) Phase 5 — Control bus + re‑emit operations (COMPLETE)
6) Phase 6 — Observability + governance (COMPLETE)
7) Phase 7 — Security + ops hardening (COMPLETE)
8) Phase 8 — Integration tests + CI gates
9) Phase 9 — WSP alignment (docs + contracts) (COMPLETE)
10) Phase 10 — WSP alignment (implementation) (COMPLETE)
11) Phase 11 — WSP alignment (validation) (COMPLETE)

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
- Artifact paths stay under `fraud-platform/<platform_run_id>/sr/` and follow the SR contract layout.
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
- Instance‑scoped outputs emit SR verifier receipts under `fraud-platform/<platform_run_id>/sr/instance_receipts/...` with drift detection.

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

**Status:** COMPLETE.

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

**Status:** COMPLETE.

### Section 5.1 — Control bus abstraction + real adapter
**Goal:** make control‑bus publishing real (AWS Kinesis in prod) while keeping semantics identical across envs.

**Definition of done**
- ControlBus interface supports publish + idempotency key + message attributes.
- Kinesis adapter implemented (production target); file‑based bus remains for local/dev.
- Publish does not block truth commits; failures are recorded and surfaced.
- No credentials or secrets are embedded in code or docs.

### Section 5.2 — READY publish idempotency + envelope
**Goal:** ensure READY publish is safe under retries and duplicates.

**Definition of done**
- READY publish key is deterministic: `(run_id, bundle_hash)` (or equivalent stable facts_view hash).
- READY payload includes `facts_view_ref` and pins; payload validated against run_ready_signal schema.
- Duplicate READY publishes are idempotent and safe for downstream.

### Section 5.3 — Re‑emit operations (N7)
**Goal:** provide an ops‑safe re‑emit path that replays control facts without recomputing or mutating truth.

**Definition of done**
- Re‑emit API/CLI accepts `run_id`, `reemit_kind` (READY_ONLY / TERMINAL_ONLY / BOTH), and `reason` (audit).
- Re‑emit reads `run_status` + `run_facts_view` (if READY) from SR truth; no engine calls.
- Re‑emit uses a short ops micro‑lease to prevent stampede.
- Re‑emit publishes idempotently with deterministic keys:
  - READY key: `sha256("ready|" + run_id + "|" + facts_view_hash)`.
  - TERMINAL key: `sha256("terminal|" + run_id + "|" + status_state + "|" + status_hash)`.
- Re‑emit appends run_record events (`REEMIT_REQUESTED`, `REEMIT_PUBLISHED`, `REEMIT_FAILED`) without changing run_status.

### Section 5.4 — Failure posture + audit trail
**Goal:** keep control‑bus failures observable without violating truth immutability.

**Definition of done**
- Publish failures do **not** alter run_status or facts_view.
- Failures are appended to run_record with reason codes.
- SR returns a clear response to the operator (success/failure/busy).

### Section 5.5 — Tests + validation
**Goal:** prove control‑bus idempotency and re‑emit behavior.

**Definition of done**
- Unit tests for READY idempotency key and re‑emit key derivation.
- Integration test for re‑emit READY against a ready run (file bus), verifying message payload and idempotency key.
- Integration test for re‑emit terminal (FAILED/QUARANTINED) with correct status refs.
- All Phase 5 tests logged in docs/logbook with results.

---

## Phase 6 — Observability + governance
High‑level intent: structured event taxonomy, metrics/traces, audit‑ready provenance stamps.

**Status:** COMPLETE.

### Section 6.1 — Event taxonomy + structured events
**Goal:** define and emit a stable SR observability event model.

**Definition of done**
- Canonical SR event taxonomy defined (ingress, plan, engine, evidence, commit, re‑emit).
- Structured event model includes pins + policy_rev + attempt_id when applicable.
- Emission is best‑effort and never blocks truth commits.

### Section 6.2 — Governance facts (policy_rev / plan_hash / bundle_hash)
**Goal:** emit explicit governance facts for audit‑ready provenance.

**Definition of done**
- Emit policy_rev + plan_hash facts at plan commit.
- Emit bundle_hash facts at READY commit.
- Emit re‑emit keys for READY/TERMINAL replays.
- Facts are append‑only in run_record; no run_status mutation.

### Section 6.3 — Metrics counters + durations
**Goal:** produce minimal golden‑signal metrics from structured events.

**Definition of done**
- Counters for run requests, ready, failed, quarantined, engine attempts.
- Duration metrics for engine attempt and evidence wait (tracked in process).
- Metrics emission is best‑effort and non‑blocking.

### Section 6.4 — Sinks + degrade posture
**Goal:** provide a sink strategy that never blocks SR truth.

**Definition of done**
- Console JSON sink for local/dev.
- Optional OTLP sink scaffolded (feature‑flagged).
- Degrade posture: drop DEBUG first; never block on sink failure.

### Section 6.5 — Tests + validation
**Goal:** prove observability and governance facts without affecting truth.

**Definition of done**
- Unit tests for event emission and presence of governance facts in run_record.
- Tests confirm emit failures do not block READY commits.
- Log test results in docs/logbook.

---

## Phase 7 — Security + ops hardening
High‑level intent: authn/authz, secrets hygiene, quarantine workflows, operator tooling.

**Status:** COMPLETE.

### Section 7.1 — AuthN/AuthZ gates (ingress + re‑emit)
**Goal:** explicit authorization for run submit and re‑emit operations.

**Definition of done**
- Policy‑based allowlist for ingress + re‑emit (local/dev permissive, prod explicit).
- Auth failures are explicit and audited (run_record + obs event).

### Section 7.2 — Secrets hygiene + redaction
**Goal:** eliminate secrets from logs/artifacts.

**Definition of done**
- Redaction helper for DSNs/env vars in logs.
- No secret material in SR artifacts or control signals.

### Section 7.3 — Quarantine artifacts + operator tooling
**Goal:** make quarantined runs inspectable without mutating truth.

**Definition of done**
- Quarantine artifacts stored under `fraud-platform/<platform_run_id>/sr/quarantine/`.
- CLI tooling to list/inspect quarantined runs (read‑only).

### Section 7.4 — Ops guardrails (rate limits + dry‑run)
**Goal:** prevent ops misuse and accidental flooding.

**Definition of done**
- Re‑emit rate limits per run (time‑windowed).
- Dry‑run re‑emit option validates availability without publishing.

### Section 7.5 — Tests + validation
**Goal:** prove security + ops hardening without breaking truth flow.

**Definition of done**
- Tests for auth allow/deny behavior.
- Tests for redaction helper (secrets masked).
- Tests for quarantine artifact presence.
- Tests for re‑emit rate limits + dry‑run.

---

## Phase 8 — Integration tests + CI gates
High‑level intent: golden path + duplicate + reuse + fail‑closed + re‑emit + correction tests; contract compatibility checks in CI.

**Status:** COMPLETE (8.1–8.7 implemented + validated across Tier 0, parity, localstack, engine_fixture).

### Section 8.1 — Test tiers + markers
**Goal:** define a tiered integration test strategy that is fast on PRs and deep on nightly/explicit runs.

**Definition of done**
- Define pytest markers: `unit`, `parity`, `localstack`, `engine_fixture`.
- Tier 0 (PR): unit + fast integration (no external services).
- Tier 1 (PR or manual): MinIO + Postgres parity tests (storage + evidence).
- Tier 2 (nightly/manual): LocalStack Kinesis control bus + re‑emit E2E.
- Tier 3 (manual/nightly): engine fixture reuse tests using `runs/local_full_run-*`.
- Each marker has a short runbook in README or docs (how to run locally).

### Section 8.2 — Golden path integration (SR core)
**Goal:** prove the full SR pipeline from submit → plan → attempt → evidence → READY on real storage backends.

**Definition of done**
- Integration test uses parity stack (MinIO + Postgres).
- Test asserts: run_record append-only, run_status READY, facts_view emitted, READY publish recorded.
- Evidence verification uses real gate map and locators (no mocks).

### Section 8.3 — Duplicate + at‑least‑once behavior
**Goal:** validate idempotency in integration conditions (not just unit tests).

**Definition of done**
- Integration test submits the same run twice and proves equivalence binding (same run_id, no duplicate writes).
- Concurrent lease contention test proves only one writer commits truth.
- Duplicate READY publish is idempotent and does not mutate truth.

### Section 8.4 — Fail‑closed integration (negative cases)
**Goal:** ensure SR refuses to proceed when contracts/evidence are incomplete or incompatible.

**Definition of done**
- Missing gate receipt → WAITING/FAIL with stable reason code.
- Receipt drift → FAIL with `INSTANCE_RECEIPT_DRIFT`.
- Unknown output/gate → FAIL with explicit reason.
- Contract validation failure → FAIL closed, no READY.

### Section 8.5 — Control bus + re‑emit E2E (LocalStack)
**Goal:** prove that Kinesis adapter + re‑emit work end‑to‑end under a real API surface.

**Definition of done**
- LocalStack test publishes READY to Kinesis with deterministic idempotency key.
- Re‑emit READY/TERMINAL publishes with expected keys and payloads.
- Publish failures are recorded in run_record but do not mutate run_status.

### Section 8.6 — Contract compatibility checks
**Goal:** fail CI when interface_pack contracts drift or break SR assumptions.

**Definition of done**
- Validation step loads interface_pack schemas and gate map, compiles all $refs, and fails on missing/invalid contracts.
- Gate map hashing laws are parsed and validated for required outputs (2A/2B/3B/5A/5B/6A/6B).
- No engine code changes; strictly read-only validation.

### Section 8.7 — CI gates + runbooks
**Goal:** define clear CI gates and local reproduction steps.

**Definition of done**
- CI targets:
  - PR: Tier 0 tests only (fast).
  - Nightly/manual: Tier 1–3 integration tests.
- Runbook documents which env vars are required and how to start local parity stacks.
- Test results logged in docs/logbook when executed.

---

## Phase 9 — WSP alignment (docs + contracts) (COMPLETE)

**Intent:** align SR docs and contracts to WSP‑first runtime while preserving SR as readiness authority and Oracle Store as external truth.

**Traffic policy (v0):** SR publishes READY for **one behavioural stream per run** (baseline **or** fraud). Context streams are deferred to RTDL plane work (not emitted in v0 control & ingress).

### Section 9.1 — Control‑plane re‑scope (docs)
**Definition of done**
- SR docs/contracts explicitly state SR is **control‑plane only** (readiness authority).
- SR does not claim ownership of data‑plane streaming (WSP is the primary producer).
- Narrative docs treat IG pull path as **legacy/backfill** only.

### Section 9.2 — Oracle pack linking (contract updates)
**Definition of done**
- SR truth surfaces include **by‑ref pack identity**:
  - `oracle_pack_id` (if present),
  - `engine_run_root` (or oracle root pointer),
  - pack manifest ref (by‑ref path/URI).
- Schema validation enforces presence/format when available (fail‑closed on mismatch).

### Section 9.3 — Legacy pull compatibility (doc’d)
**Definition of done**
- run_facts_view locators remain valid for legacy pull/backfill.
- Explicit doc notes that WSP is the primary runtime path.

### Section 9.4 — Ops guidance (docs)
**Definition of done**
- Operator guides + examples show WSP‑first flow and SR’s readiness role.
- SR re‑emit operations remain supported for control bus/audit workflows.

---

## Phase 10 — WSP alignment (implementation) (COMPLETE)

**Intent:** implement SR truth‑surface changes and READY payload linking to Oracle pack identity without changing SR’s core readiness logic.

### Section 10.1 — Truth surface extensions
**Definition of done**
- run_facts_view and READY include pack identity refs (by‑ref paths/ids).
- SR still publishes legacy locators for backfill.

### Section 10.2 — Ingress/evidence binding
**Definition of done**
- Pack identity is validated when present (schema + mismatch fail‑closed).
- SR does **not** attempt to stream data or own Oracle Store.

### Section 10.3 — Control bus payload updates
**Definition of done**
- READY payload carries pack refs for WSP/ops correlation.
- Re‑emit preserves pack refs.

---

## Phase 11 — WSP alignment (validation) (COMPLETE)

**Intent:** validate SR alignment without breaking backfill or compatibility.

### Section 11.1 — Compatibility tests
**Definition of done**
- SR publishes READY with pack references (when available).
- run_facts_view still supports IG legacy pull.

### Section 11.2 — Fail‑closed tests
**Definition of done**
- Pack ref mismatch → FAIL/QUARANTINE with explicit reason.
- Missing pack refs allowed only when manifest absent (local/dev rules).
