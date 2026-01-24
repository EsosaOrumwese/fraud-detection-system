# Scenario Runner Implementation Map
_As of 2026-01-23_

---

## Entry: 2026-01-23 21:29:50 — SR v0 foundation plan + locked decisions

### Problem / goal
Stand up the Scenario Runner (SR) as the production-grade run authority for the platform. SR must publish a pinned join surface (run facts + READY) with strict HashGate enforcement, support idempotent run admission, enable reuse of validated worlds, and provide a control-plane re-emit path. SR is the only authority for run readiness and the join surface consumed by IG/EB and downstream services.

### Authorities / inputs (binding)
- Root AGENTS.md (platform scope + doctrine; SR is run readiness authority; no-PASS-no-read; by-ref refs; idempotency; fail-closed).
- Platform-wide notes: docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md + deployment_tooling_notes_v0.md (graph shape, substrate, environment ladder).
- Engine interface pack: docs/model_spec/data-engine/interface_pack/ (identity tuple, output catalogue, gate map, locator schema, gate receipts).
- Platform narratives (control+ingress; real-time loop; label/case; learning; obs/gov) for cross-plane expectations.
- SR design-authority: docs/model_spec/platform/component-specific/scenario_runner.design-authority.md (pins, paths, internal subnetworks, invariants).

### Locked decisions (user-approved defaults)
1) **Deployment shape**: SR runs as an always-on service (HTTP/gRPC) with a CLI wrapper for local/dev single-run invocation. Reason: production semantics (idempotent admission, leases, re-emit) while preserving local iteration.
2) **Truth storage**: SR truth artifacts are stored in object storage (append-only by-ref), with an optional rebuildable DB index for ops/lookup. Reason: truth stays immutable, index can be skipped in v0 if needed.
3) **Control bus + prefix naming**: Use control topic name fp.bus.control.v1 and object-store prefix family fraud-platform/sr/ (or equivalent bucket/prefix pair). Reason: avoid naming drift, keep join semantics consistent. (Names are defaults, not binding to a vendor.)

### Alternatives considered (and why rejected)
- **CLI-only SR**: rejected because it weakens production semantics (no long-lived idempotency surface, leases, re-emit authorization path).
- **DB-only truth**: rejected because it breaks by-ref truth transport and immutability posture; also blurs “truth vs index.”
- **“Latest outputs” discovery**: rejected due to explicit platform rule: downstream must start from SR join surface; no scanning.

### Intended mechanics (v0 scope)
Implement the SR backbone as a set of subnetworks per design authority (N1–N8). v0 focuses on correctness of control truth and evidence gating, not throughput.

**Core flows to implement first (mandatory):**
- IP1: new run → invoke engine → gather evidence → verify gates → publish READY.
- IP2: duplicate submission (idempotent re-entry).
- IP3: reuse path (engine not invoked; verify evidence).
- IP5: missing/FAIL PASS evidence (WAITING/FAIL/COLLISION → fail-closed/quarantine).

**Secondary flows (after core):**
- IP7: control-plane re-emit (rehydration).
- IP6: post-READY correction via supersede (no mutation).
- IP8: offline rebuild entrypoint (read-only join surface exposure).

### Data model + truth artifacts (object store)
**Base prefix:** fraud-platform/sr/
- run_plan/{run_id}.json (immutable; canonical plan + plan_hash)
- run_record/{run_id}.jsonl (append-only event ledger; all state transitions)
- run_status/{run_id}.json (monotonic snapshot; derived from run_record)
- run_facts_view/{run_id}.json (join surface; pins + engine locators + PASS receipts)
- ready_signal/{run_id}.json (control fact emitted to EB control topic; points to facts view)

**Invariants:**
- READY only after all required PASS evidence is verified.
- All artifacts carry ContextPins + policy revision.
- run_status is derived, never authoritative; run_record is append-only truth.
- run_facts_view is immutable per run_id; corrections are supersedes (new run_facts_view + new control fact).

### Algorithm & data-flow choices (by subnetwork)
- **N1 (Ingress)**: canonicalize run intent, validate minimal shape, enforce authn/authz, derive run-equivalence key.
- **N2 (Run Authority Core)**: resolve run_id from equivalence key; single-writer lease; idempotent admission; produce RunHandle.
- **N3 (Plan/Policy)**: load wiring profile + policy profile; compile output intent; derive required gate closure; select strategy (invoke vs reuse); compute plan_hash; emit plan ticket(s).
- **N4 (Engine Orchestrator)**: idempotent engine invocation + attempt tracking; no direct writes except through N6; emits attempt result.
- **N5 (Evidence Assembly)**: build engine output locators; resolve gate graph; verify gates using interface pack; bind instance receipts; classify evidence completeness (COMPLETE/WAITING/FAIL/CONFLICT); compute bundle hash.
- **N6 (Ledger/Join Surface)**: append run_record; commit run_plan; update run_status (monotonic); write run_facts_view; emit READY control fact only when evidence COMPLETE.
- **N7 (Re-emit Ops)**: authorized re-emit with ops micro-lease; reconstruct control facts from ledger; no mutation.
- **N8 (Obs/Gov)**: emit structured events (ingress, planning, engine boundary, evidence, commit/publish, re-emit/supersede) with policy revision + pins.

### Security / governance posture
- Authn/authz on SR ingress and re-emit endpoints.
- Policy config is versioned (policy_rev stamped into run_plan, receipts, READY).
- Secrets never appear in SR artifacts; only secret IDs if needed.
- Quarantine path for evidence conflicts or invalid gate receipts.

### Performance / reliability
- v0 prioritizes correctness; concurrency is limited by N2 lease.
- Idempotent handlers on all entrypoints; duplicate requests return existing run pointers.
- Evidence verification may be async; WAITING status exposed without READY.

### Deployment + environment ladder assumptions
- Local/dev/prod share semantics; only wiring/policy profiles vary.
- EB control topic exists; object store available (S3-compatible); optional DB index can be off in local.

### File path plan (initial implementation target)
- New SR service package under services/scenario_runner/ (if no existing SR service).
- Shared schema contracts under contracts/ as needed for SR run artifacts.
- SR config profiles under config/platform/sr/ (wiring + policy profiles).
- Tests under tests/services/scenario_runner/.

### Validation & test plan (to be executed and logged)
- Unit: run-equivalence key, plan_hash determinism, gate-closure derivation, evidence classification.
- Integration: IP1/IP2/IP3/IP5 flows with mocked engine outputs + gate receipts.
- End-to-end: SR emits READY → IG can join via run_facts_view ref (control topic).

### Open questions / risks
- Exact schema for run artifacts (run_plan/run_record/run_status/run_facts_view) needs finalization—must align with interface pack and platform pins.
- Engine invocation mechanism (job runner vs adapter) still needs concrete binding in this repo (N4).
- Quarantine storage location for SR evidence conflicts (likely fraud-platform/sr/quarantine/).

---

## Entry: 2026-01-23 21:44:32 — SR v0 skeleton plan (N1–N6 + IP1/IP2/IP3/IP5)

### Scope
Implement the first runnable Scenario Runner skeleton with correct truth artifacts, deterministic IDs, and the core flow behaviors: IP1 (new run invoke), IP2 (duplicate), IP3 (reuse), IP5 (waiting/fail/ quarantine). Provide a minimal CLI + service wrapper and local object-store persistence. Keep interfaces pluggable for future production wiring.

### Design choices (applied)
- SR code lives under `src/fraud_detection/scenario_runner/` (package) with a thin service wrapper under `services/scenario_runner/` to match repo conventions.
- Object-store truth is implemented as a local filesystem root with deterministic `sr/` artifact paths; optional indexes live under `sr/index/` and are rebuildable.
- Engine invocation is a pluggable adapter; v0 uses a local “no-op” invoker that returns a structured AttemptResult and allows pointing to an existing engine run root for evidence harvest.
- Gate verification uses the engine gate map and verifies `_passed.flag` using the correct method:
  - `sha256_bundle_digest`: sha256 of concatenated bytes of all files under bundle_root (exclude `_passed.flag`), sorted by relative path.
  - `sha256_member_digest_concat`: sha256 of concatenated member digest strings from index.json in array order.

### Files to add/update (planned)
- `src/fraud_detection/scenario_runner/__init__.py`
- `src/fraud_detection/scenario_runner/models.py` (request/plan/status/facts models)
- `src/fraud_detection/scenario_runner/ids.py` (run_id/attempt_id derivation)
- `src/fraud_detection/scenario_runner/storage.py` (local object store + atomic writes)
- `src/fraud_detection/scenario_runner/ledger.py` (run_record append, run_status monotonic, run_plan commit, facts_view commit, READY publish ordering)
- `src/fraud_detection/scenario_runner/evidence.py` (locators, receipts, bundle hashing, verification)
- `src/fraud_detection/scenario_runner/engine.py` (EngineInvoker interface + local stub)
- `src/fraud_detection/scenario_runner/runner.py` (ScenarioRunner orchestration with IP1/IP2/IP3/IP5)
- `src/fraud_detection/scenario_runner/cli.py` (CLI submit)
- `src/fraud_detection/scenario_runner/service.py` (Flask app factory + /runs endpoint)
- `services/scenario_runner/README.md` + `services/scenario_runner/AGENTS.md`
- `config/platform/sr/wiring_local.yaml` + `config/platform/sr/policy_v0.yaml`
- `tests/services/scenario_runner/test_ids.py` + `test_gate_verifier.py` (minimal correctness tests)

### Invariants enforced in code
- One `run_equivalence_key` → one run_id; collision on intent fingerprint is rejected.
- Lease required for any state-advancing write; follower returns pointers only.
- Commit order: `run_facts_view` → `run_status=READY` → `run_record` append → READY publish.
- `run_plan` immutable once committed; `run_facts_view` immutable once READY.
- Fail-closed: missing/invalid gate evidence yields WAITING/FAIL/QUARANTINED (never READY).

### Validation plan (execute + log)
- Unitests for run_id/attempt_id determinism and scenario_set → scenario_id derivation.
- Gate verification tests against existing run artifacts in `runs/local_full_run-5` for one `sha256_bundle_digest` gate (6B) and one `sha256_member_digest_concat` gate (3A).
- Smoke flow: submit run with reuse strategy + existing engine run root; expect READY and artifacts in `sr/`.

---
## Entry: 2026-01-23 21:58:40 — Implemented SR v0 skeleton (core flows + artifacts)

### What changed
- Added SR package under `src/fraud_detection/scenario_runner/` with models, IDs, storage, ledger, evidence verification, engine adapter, and core orchestration (IP1/IP2/IP3/IP5).
- Added CLI (`cli.py`) and Flask service wrapper (`service.py`).
- Added SR service stubs in `services/scenario_runner/` and local wiring/policy profiles in `config/platform/sr/`.
- Added minimal tests for ID determinism and gate verification using existing local engine run artifacts.

### Key mechanics implemented
- Deterministic `run_id` and `attempt_id` derivation (hex32 sha256) and scenario_set → scenario_id normalization.
- Ledger commit ordering enforced in code: facts view before READY status and READY publish; run_record append-only with idempotent event IDs.
- Gate verification methods implemented:
  - sha256_bundle_digest: sha256 of concatenated file bytes under bundle root (exclude _passed.flag, ascii-lex ordering).
  - sha256_member_digest_concat: sha256 of concatenated member digest strings in index.json order.
- Evidence evaluation returns COMPLETE/WAITING/FAIL/CONFLICT per design; missing gates/outputs produce WAITING before deadline, FAIL after deadline.

### Notes / deviations
- v0 evidence collection accepts an explicit `engine_run_root` from request or wiring; engine invocation is a stubbed adapter that returns a structured AttemptResult without running engine jobs.
- Output role tagging is derived from policy’s `traffic_output_ids` list; non-listed outputs are tagged `non_traffic` in facts view.

### Tests
- Added: `tests/services/scenario_runner/test_ids.py`, `test_gate_verifier.py`.
- Pytest unavailable in PATH on this machine (logged in logbook).

---
## Entry: 2026-01-23 22:02:18 — SR policy profile content_digest update

### Change
Updated `config/platform/sr/policy_v0.yaml` content_digest after editing the file. The digest is treated as a pinned policy identifier (not a self-verifying checksum).

### Reason
Keep policy_rev non-empty for provenance; digest verification is deferred until a formal policy artifact pipeline exists.

---
## Entry: 2026-01-23 22:08:08 — SR production‑ready roadmap (design intent + execution plan)

### Purpose
Lock a production‑grade execution roadmap for Scenario Runner (SR) that follows the design intent but is not constrained by any single doc. This entry is the canonical plan to prevent drift as we scale from v0 skeleton to production‑ready SR.

### Design intent (non‑negotiable outcomes)
SR must:
- be the **run readiness authority** and only publisher of READY for a run.
- publish the **join surface** (`run_facts_view`) that is the single downstream entrypoint.
- enforce **no‑PASS‑no‑read** by verifying required HashGates before READY.
- remain **idempotent** and correct under at‑least‑once and duplicate submissions.
- make **provenance first‑class** (pins + policy_rev + evidence refs everywhere).
- be **fail‑closed** (missing/unknown gate evidence → WAITING/FAIL/QUARANTINE, never READY).

### Production roadmap (phased, explicit)

**Phase 1 — Contracts + Truth Surfaces (stabilize the meaning)**
- Define canonical schemas for:
  - RunRequest (ingress), RunPlan (intended actions), RunRecord (append‑only ledger), RunStatus (monotonic snapshot), RunFactsView (join surface), RunReadySignal (control bus trigger).
- Validate schemas at N1 ingress and at N6 commit boundaries.
- Canonicalize pins and scenario binding; freeze `run_id` + `attempt_id` derivation.

**Phase 2 — Durable storage + idempotency (truth, not demos)**
- Implement object‑store abstraction with atomic writes and by‑ref artifact refs.
- Implement real idempotency binding + lease manager (SQLite/Postgres for local; Postgres for dev/prod).
- Ensure run_record append‑only + idempotent event IDs; run_status monotonic only.

**Phase 3 — Evidence + gate verification completeness (fail‑closed)**
- Implement N5 fully: output intent → required gate closure; gate verification by gate‑specific method.
- Enforce instance‑proof binding where scope includes seed/scenario_id/parameter_hash/run_id.
- Classify COMPLETE / WAITING / FAIL / CONFLICT deterministically.

**Phase 4 — Engine invocation integration (true IP1)**
- Implement N4 job runner adapter with attempt idempotency and retry budget.
- Record attempt lifecycle in run_record; ensure lease loss halts writes.
- Return normalized AttemptResult for evidence harvesting.

**Phase 5 — Control bus + re‑emit (operational truth)**
- Wire to real bus (Kafka/Redpanda). Ensure READY publish idempotency key = (run_id, facts_view_hash).
- Implement N7 re‑emit with ops micro‑lease and strict “read truth → re‑publish” behavior.

**Phase 6 — Observability + governance (audit‑ready)**
- Implement N8 normalized eventaxonomy; emit metrics, traces, and governance facts.
- Stamp policy_rev + plan hash + evidence hash on all runs.
- Enforce telemetry never blocks truth commits (drop DEBUG first, keep governance facts).

**Phase 7 — Security + ops hardening**
- AuthN/AuthZ for run submit, re‑emit, correction.
- Secrets never in artifacts; only key IDs.
- Quarantine path + operator inspection tooling.

**Phase 8 — Integration tests + CI gates**
- Golden path, duplicate, reuse, fail‑closed, re‑emit, correction.
- Contract compliance tests.
- CI checks for schema compatibility + invariantests.

### Mapping to SR subnetworks
- N1: ingress validation, scenario normalization, run_equivalence_key enforcement.
- N2: idempotency binding + lease authority.
- N3: plan compilation + policy_rev stamping.
- N4: engine attempt lifecycle with idempotency.
- N5: evidence + gate verification (COMPLETE/WAITING/FAIL/CONFLICT).
- N6: ledger + facts_view + READY ordering and immutability.
- N7: re‑emit control facts (no recompute).
- N8: observability + governance emission (never truth).

### Guardrails against drift
- READY without admissible PASS evidence is forbidden.
- Downstream must start from READY → run_facts_view; scanning “latest” is forbidden.
- run_plan and run_facts_view are immutable after commit; corrections use supersede.
- Evidence decisions are deterministic, no “best effort.”

### Immediate next work item (if not overridden)
Proceed to **Phase 1: Contracts + Truth Surfaces** (schemas + validation wiring), then Phase 2 (durable idempotency/lease store).

---
## Entry: 2026-01-23 22:14:40 — Phase 1: SR contracts + validation wiring

### Change summary
- Added SR JSON Schemas under `docs/model_spec/platform/contracts/scenario_runner/`:
  - run_request.schema.yaml
  - run_plan.schema.yaml
  - run_record.schema.yaml
  - run_status.schema.yaml
  - run_facts_view.schema.yaml
  - run_ready_signal.schema.yaml
- Implemented SchemaRegistry with Draft 2020-12 validation and wired it into SR:
  - RunRequest validated at ingress.
  - run_plan/run_record/run_status/run_facts_view/run_ready_signal validated at commit time.
- Wiring profile now carries `schema_root` for SR validation.

### Design intent alignment
- Contracts now explicitly define SR truth surfaces and the READY signal, reducing drift risk.
- Validation is fail‑closed: schema violations prevent commits/publish.

### Notes
- Schemas live under docs/model_spec/platform/contracts (not root `contracts/` which is locked); this is intentional to keep authority local to platform specs until the contracts root is unlocked.

---
## Entry: 2026-01-24 04:41:45 — Phase 1 sanity check (schema validation mismatch)

### What I checked
Ran a quick end-to-end SR sanity flow with local wiring/policy:
- Instantiated ScenarioRunner with `config/platform/sr/wiring_local.yaml` + `policy_v0.yaml`.
- Submitted a minimal RunRequest (single output, local engine_run_root).
- Expected WAITING due to missing outputs.

### Finding
`ScenarioRunner.submit_run()` currently fails at schema validation because it validates `request.model_dump()` (Python objects) againsthe JSON Schema, which expects JSON-compatible types and omits null fields.

Observed failures:
- `window_start_utc` / `window_end_utc` are datetime objects (schema expects RFC3339 strings).
- Optional fields with `None` are still present (schema disallows nulls).
- `scenario.scenario_set=None` causes a `oneOf` conflict (both scenario_id and scenario_set present).
- `requested_strategy=None` fails enum constraint; `output_ids=None` fails array constraint.

### Implication
Phase 1 validation wiring exists, but ingress validation is not yet operational for Pydantic inputs without a JSON-mode dump. This is a correctness bug that should be fixed before Phase 2.

### Recommended fix (next action before Phase 2)
In `ScenarioRunner.submit_run`, validate a JSON-safe payload:
- `request.model_dump(mode="json", exclude_none=True)` (or equivalent)
This will:
  - Serialize datetimes to strings,
  - Remove `None` fields,
  - Avoid scenario_set/oneOf conflicts when only scenario_id is set,
  - Align with schema requirements.

---
## Entry: 2026-01-24 04:44:09 — Fix ingress schema validation (JSON-safe dump)

### Change
Updated SR ingress schema validation to validate a JSON-safe payload:
- `ScenarioRunner.submit_run` now validates `request.model_dump(mode="json", exclude_none=True)`.

### Reasoning
JSON Schema expects JSON types and disallows nulls for optional fields. Pydantic model_dump (default) emits Python datetimes and includes `None` fields, causing schema validation to fail even for valid requests.

### Expected outcome
Ingress validation now accepts valid RunRequest inputs and fails only on true schema violations, restoring Phase 1 correctness.

---
## Entry: 2026-01-24 04:45:48 — Fix ledger schema validation + JSON persistence

### Change
Converted RunPlan/RunStatus payloads to JSON-safe dumps in the ledger:
- `anchor_run` uses `status.model_dump(mode="json", exclude_none=True)`
- `commit_plan` uses `plan.model_dump(mode="json", exclude_none=True)` for compare/validate/write
- `_update_status` uses JSON-safe dump before validate/write

### Reasoning
RunPlan and RunStatus include datetimes and optional fields; JSON Schema expects RFC3339 strings and omits nulls. The JSON writer also fails on raw datetime objects, so dumps must be JSON-compatible.

### Sanity check
Re-ran a local submit flow after the fix; schema validation passed. The response returned “lease held by another runner,” indicating a stale local lease from a prior failed attempt (expected in local dev, can be cleaned).

---
## Entry: 2026-01-24 05:07:44 — Create SR build plan doc (living plan format)

### Problem / request
Root AGENTS.md now requires a living build‑plan doc at `component_{COMP}.build_plan.md` using progressive elaboration (phase list first; phase sections expanded with definition‑of‑done checklists as we enter them). User requested creation for SR.

### Decision
Create `docs/model_spec/platform/implementation_maps/component_scenario_runner.build_plan.md`:
- Start with Phase 1–Phase X list aligned to the SR roadmap.
- Mark Phase 1 as completed.
- Expand Phase 2 into sections with DoD checklists (since Phase 2 is next).
- Keep later phases high‑level until we enter them.

### Next actions
Add the build‑plan file with the structure above and log the action.

---
## Entry: 2026-01-24 05:20:30 — Phase 2 plan (durable storage + idempotency)

### Problem / goal
Advance SR from local-only persistence to production‑grade durability and idempotency:
- Durable object store abstraction (local + S3‑compatible).
- Durable idempotency + lease authority (SQLite local; Postgres dev/prod).
- Preserve SR truth invariants (append‑only record, monotonic status, by‑ref facts).

### Authorities / inputs
- Root AGENTS.md doctrine: by‑ref artifacts, idempotency, append‑only truths, fail‑closed.
- SR design‑authority (N2/N6 invariants) + Phase 2 build‑plan intent.
- Engine interface pack (pins + outputs/gates remain unchanged).
- Existing SR v0 code + schemas (run_record/run_status/run_plan/run_facts_view/ready_signal).

### Decisions (proposed)
1) **Object store abstraction**:
   - Introduce `ObjectStore` interface in SR storage module.
   - Implement `LocalObjectStore` (existing) and `S3ObjectStore` (boto3).
   - Auto‑select backend from `object_store_root` (path vs `s3://bucket/prefix`).
2) **Atomic writes**:
   - Local: tmp + replace (current behavior).
   - S3: `put_object` is atomic per key; use `IfNoneMatch='*'` when immutability is required.
   - For `append_jsonl` on S3: read + append + conditional `IfMatch` on ETag to avoid lost updates (leader‑only writes still expected).
3) **Idempotency + lease authority**:
   - Replace file‑based equivalence + leases with DB‑backed store.
   - SQLite for local dev (file DB); Postgres for dev/prod (psycopg sync client).
   - Tables: `sr_run_equivalence` (key → run_id + fingerprint) and `sr_run_leases` (run_id → lease state).
4) **Wiring**:
   - Add `authority_store_dsn` to SR wiring profile.
   - Default local DSN under `artefacts/fraud-platform/sr/index/` if not provided.

### Invariants to preserve
- One `run_equivalence_key` → one `run_id`; mismatch in intent_fingerprint hard‑fails.
- Only the lease holder may advance state; lease loss halts writes.
- run_record append‑only with idempotent event IDs.
- run_status transitions are monotonic and validated against schema.
- READY publish order remains: facts_view → status READY → record append → ready signal → control bus.

### Security / governance
- DB creds only via DSN/env; no secrets in artifacts.
- Lease tokens opaque; never written to public artifacts.
- Fail‑closed on DB or object‑store errors (no READY on uncertainty).

### Performance considerations
- Lease and equivalence operations are single‑row transactions; no hot scans.
- Append‑jsonl on S3 is O(n) in file size; acceptable for small run_record; can be segmented later if needed.

### Deployment / environment
- Local: SQLite file + LocalObjectStore.
- Dev/Prod: Postgres DSN + S3‑compatible object store (MinIO/S3).

### Validation / tests
- Unit: idempotency resolve collision; lease acquire/renew/expire.
- Integration: duplicate submits with concurrent leases; ensure only one leader writes.
- Storage: Local + S3 write/append behavior (S3 tests can be stubbed or skipped if no credentials).

### Execution steps (next)
1) Add `ObjectStore` interface + `S3ObjectStore`; refactor SR to use store factory.
2) Add DB‑backed authority store; refactor EquivalenceRegistry/LeaseManager usage.
3) Wire new config fields + update docs/build plan/logbook.
4) Add tests + run targeted sanity checks; log results.

---
## Entry: 2026-01-24 05:28:30 — Phase 2 implementation (storage + authority store)

### What changed
**Storage abstraction**
- Replaced direct LocalObjectStore usage with an `ObjectStore` protocol.
- Added `S3ObjectStore` (boto3) and `build_object_store` factory (path vs `s3://`).
- Ledger now accepts an `ObjectStore` instead of the local‑only type.

**Authority store (idempotency + leases)**
- Replaced file‑based equivalence/lease tracking with DB‑backed stores:
  - `SQLiteAuthorityStore` for local.
  - `PostgresAuthorityStore` for dev/prod (psycopg).
- Added `build_authority_store(dsn)` and refactored EquivalenceRegistry/LeaseManager to wrap the store.
- Added `authority_store_dsn` to SR wiring; local wiring uses SQLite under `artefacts/fraud-platform/sr/index/`.

**Dependencies + tests**
- Added `psycopg[binary]` to pyproject dependencies.
- Added SQLite authority store tests; pytest run green (2 tests).

### Files touched (high‑signal)
- `src/fraud_detection/scenario_runner/storage.py` (ObjectStore + S3 backend + factory)
- `src/fraud_detection/scenario_runner/authority.py` (DB‑backed authority store)
- `src/fraud_detection/scenario_runner/ledger.py` (ObjectStore type)
- `src/fraud_detection/scenario_runner/runner.py` (store + authority wiring)
- `config/platform/sr/wiring_local.yaml` (authority_store_dsn)
- `pyproject.toml` (psycopg dependency)
- `tests/services/scenario_runner/test_authority_store.py` (new tests)

### Notes / constraints
- S3 append_jsonl is implemented as read‑append‑write (leader‑only writes assumed).
- If `object_store_root` is non‑local and `authority_store_dsn` is not set, SR fails closed.

### Validation
- `pytestests/services/scenario_runner/test_authority_store.py` → 2 passed.

---
## Entry: 2026-01-24 05:35:58 — Phase 2 hardening gap (plan correction)

### Correction
Phase 2 implementation delivered functional durability but did not include the hardening items required for “rock‑solid” production semantics (S3 immutability guards, CAS append or segmentation, lease fencing/renewal, error‑class distinction, Postgres smoke, concurrency tests).

### Action
Updated the SR build plan to add **Phase 2.5 Hardening** with explicit DoD items. Phase 2 is not considered complete until those are implemented and validated.

---
## Entry: 2026-01-24 05:42:32 — Locked SR platform stack (AWS)

### Decision
Lock the SR target platform stack to AWS:
- **Object storage:** Amazon S3 (truth artifacts, run ledger).
- **Authority store:** Amazon RDS Postgres (idempotency + leases).
- **Runtime:** ECS Fargate (SR service deployment).
- **Control bus:** Amazon Kinesis (READY/control events).

### Implications
- Wiring/config mustarget S3 + Postgres DSN in dev/prod.
- FileControlBus remains local-only; Kinesis adapter will be implemented in Phase 5.
- Phase 2.5 hardening must assume S3 semantics (immutability guards + CAS/segmented append).

---
## Entry: 2026-01-24 05:47:18 — Phase 2.5 hardening plan (rock‑solid durability)

### Problem / goal
Phase 2 is functional but not rock‑solid. Hardening is required for production‑grade durability and idempotency:
- S3 immutability guards for write‑once artifacts.
- CAS/segmented run_record append to avoid lost updates.
- Lease fencing + renewal checks on state‑advancing writes.
- Fail‑closed object store errors (distinguish missing vs access/network).
- Postgres authority store smoke coverage and concurrency tests.

### Decisions (this phase)
1) **Immutability guards**: add `write_json_if_absent` / `write_text_if_absent` to the ObjectStore; use for run_plan, run_facts_view, ready_signal.
2) **CAS append**: S3 append uses ETag `IfMatch` to prevent lost updates; raise on precondition failure.
3) **Lease validation**: add `check_lease` to AuthorityStore; require valid lease (and renew) before any state‑advancing ledger write.
4) **Fail‑closed store errors**: only treat 404/NoSuchKey as missing; all other errors propagate.

### Steps
1) Extend storage interface + S3 behavior (immutability + CAS + error classification).
2) Extend authority store interface with `check_lease`; update SQLite/Postgres implementations.
3) Enforce lease validation/renew in ScenarioRunner before commitransitions.
4) Add/extend tests for lease validation; log results.

---
## Entry: 2026-01-24 05:50:29 — Phase 2.5 hardening implementation (partial)

### What changed
**Object store hardening**
- Added write‑once methods (`write_json_if_absent`, `write_text_if_absent`) and wired them into the ledger for immutable artifacts (run_plan, run_facts_view, ready_signal).
- Added S3 CAS protection on append (ETag `IfMatch`) with explicit conflict error.
- S3 `exists` now distinguishes missing vs access/network errors (fail‑closed on non‑404).

**Lease validation**
- Added `check_lease` to the authority store; ScenarioRunner now validates + renews the lease before any state‑advancing writes.

**Tests**
- Extended SQLite authority store tests to cover `check_lease`; pytest run green (2 tests).

### Files touched
- `src/fraud_detection/scenario_runner/storage.py`
- `src/fraud_detection/scenario_runner/ledger.py`
- `src/fraud_detection/scenario_runner/authority.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `tests/services/scenario_runner/test_authority_store.py`

### Still pending for Phase 2.5 completion
- Postgres authority store smoke/integration test (needs DSN).
- Concurrency tests for duplicate submits + lease contention.
- S3 integration tests (immutability + CAS append) against a real bucket or MinIO.
- Lease fencing token enforcement on writes (beyond check/renew) if required by ops policy.

---
## Entry: 2026-01-24 05:55:04 — Phase 2.5 hardening tests plan (remaining items)

### Goal
Complete the remaining Phase 2.5 hardening items with explicit, verifiable tests:
- Postgres authority store smoke coverage (env‑gated).
- Concurrency behavior under duplicate submissions and lease contention.
- S3 immutability + CAS append integration tests (env‑gated).

### Approach
1) **Postgres authority store smoke test**
   - Add pytesthat runs only when `SR_TEST_PG_DSN` is set.
   - Validate equivalence resolve + lease acquire/check/renew/release.
2) **Concurrency test**
   - Use multiple threads to submithe same RunRequest via ScenarioRunner.
   - Assert exactly one leader advances (others return lease‑held response) and the run_status is stable.
3) **S3 integration tests**
   - Add pytestests that run only when `SR_TEST_S3_BUCKET` is set (optional prefix via `SR_TEST_S3_PREFIX`).
   - Validate `write_json_if_absent` immutability (second write raises FileExistsError).
   - Validate `append_jsonl` CAS conflicts by forcing an ETag mismatch.

### Notes
Tests will be skipped if required env vars are not present; failures should be fail‑closed in prod.

---
## Entry: 2026-01-24 05:58:14 — Phase 2.5 hardening tests + plan_hash fix

### What changed
**Tests added**
- Postgres authority store smoke test (env‑gated via `SR_TEST_PG_DSN`).
- Concurrency test for duplicate submissions/lease contention (threads; one leader expected).
- S3 store tests:
  - Unit‑style CAS conflict handling for append.
  - Integration test for write‑once + append (env‑gated via `SR_TEST_S3_BUCKET`).

**Bug fix**
- `RunPlan.plan_hash` computation now uses JSON‑safe dump (`mode="json"`) to avoid datetime serialization errors.

### Files touched
- `tests/services/scenario_runner/test_authority_store_postgres.py`
- `tests/services/scenario_runner/test_scenario_runner_concurrency.py`
- `tests/services/scenario_runner/test_s3_store.py`
- `src/fraud_detection/scenario_runner/runner.py`

### Test results
- `pytestests/services/scenario_runner/test_scenario_runner_concurrency.py tests/services/scenario_runner/test_s3_store.py tests/services/scenario_runner/test_authority_store_postgres.py`
  - 2 passed, 2 skipped (Postgres + S3 integration tests skipped; env vars not set).

### Remaining Phase 2.5 items
- Run Postgres smoke test in an environment with `SR_TEST_PG_DSN`.
- Run S3 integration test with `SR_TEST_S3_BUCKET` (or MinIO).
- Decide on additional lease fencing if required by ops policy.

---
## Entry: 2026-01-24 07:09:54 — Implementation map rename (drop component_ prefix)

### Change
Renamed SR implementation map + build plan files to drop the `component_` prefix:
- `docs/model_spec/platform/implementation_maps/component_scenario_runner.impl_actual.md` → `docs/model_spec/platform/implementation_maps/scenario_runner.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/component_scenario_runner.build_plan.md` → `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`

### Reason
Align with new naming convention: use `{COMP}.impl_actual.md` and `{COMP}.build_plan.md`.

---
## Entry: 2026-01-24 09:58:16 — Plan clarification (local dev stack parity)

### Gap
The Phase 2/2.5 plans locked the AWS target stack but did not explicitly state the **local dev stack** preference (parity vs speed). This made it unclear whether we were intentionally keeping local on AWS semantics.

### Clarification
Documented local dev guidance in the build plan:
- **Recommended:** MinIO + Postgres (S3/RDS parity).
- **Allowed:** filesystem + SQLite for speed, with reduced fidelity.

---
## Entry: 2026-01-24 09:59:41 — Correction (local FS + SQLite not recommended)

### Correction
Clarified that **local filesystem + SQLite are not recommended** for SR Phase 2/2.5 hardening. They may be used only for quick smoke checks and are not valid for correctness claims.

### Current guidance
Local dev should mirror AWS semantics with **MinIO + Postgres**; Phase 2.5 hardening must run againsthat stack where available.

---
## Entry: 2026-01-24 10:40:41 — Local parity profiles plan (MinIO + Postgres)

### Goal
Set up SR local profiles that mirror the AWS stack semantics (S3 + RDS Postgres) to run Phase 2.5 integration tests and reduce drift.

### Planned changes
- Add a local parity wiring profile targeting MinIO + Postgres.
- Extend SR wiring + storage to allow S3 endpoint/region/path‑style overrides (needed for MinIO).
- Documenthe available wiring profiles in the SR service README.

---
## Entry: 2026-01-24 10:41:47 — Local parity profiles implementation

### What changed
- Added MinIO/Postgres local parity wiring profile.
- Added S3 endpoint/region/path‑style overrides in wiring + S3 client builder (needed for MinIO).
- Documented available profiles in SR service README.

### Files touched
- `config/platform/sr/wiring_local_parity.yaml`
- `src/fraud_detection/scenario_runner/config.py`
- `src/fraud_detection/scenario_runner/storage.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `services/scenario_runner/README.md`

### Notes
- For MinIO, set `s3_endpoint_url` and `s3_path_style: true` in wiring.
- Environment overrides still supported via `SR_S3_ENDPOINT_URL`, `SR_S3_REGION`, `SR_S3_PATH_STYLE`.

---
## Entry: 2026-01-24 11:24:39 — Phase 2.5 local‑parity execution notes (decision trail)

### Context / intent
Phase 2.5 requires **real** S3 + Postgres semantics to validate immutability, CAS append, and idempotency under duplicates. Local filesystem + SQLite are not acceptable for correctness claims, so we moved to **MinIO + Postgres** parity and ran env‑gated tests.

### Decisions and reasoning
1) **Use Docker compose for parity stack**
   - **Why:** fastest way to mirror S3/RDS semantics locally with minimal operator effort.
   - **Alternative:** install native Postgres + MinIO services. Rejected for reproducibility and onboarding friction.

2) **MinIO bucket initialization via `mc`**
   - **Why:** avoid manual console steps; deterministic bucket creation for tests (`sr-local`).
   - **Issue:** `minio/mc` image does not run `/bin/sh` entrypoint; switched to direct `mc` commands and `MC_HOST_*` env var.
   - **Decision:** keep `mc` container in compose but also document fallback with `docker run ... mc` if init fails.

3) **S3 client configuration for local parity**
   - **Why:** MinIO requires endpoint override + path‑style addressing.
   - **Action:** added wiring fields `s3_endpoint_url`, `s3_region`, `s3_path_style`, and env overrides (`SR_S3_*`) to support MinIO and AWS without code changes.

4) **Image tags**
   - Initial pinned tags (`RELEASE.2024-12-18...`) failed to resolve from Docker Hub.
   - **Decision:** switch to `latest` for MinIO/MC so the stack is runnable; accepthe drift risk and plan to pin later once a valid tag is confirmed.

5) **Postgres auth failures**
   - Tests failed with `password authentication failed for user "sr"` even though the container was healthy.
   - Root cause: **local Windows Postgres service already bound to port 5432**, so the test DSN hithe local service instead of Docker.
   - **Decision:** change compose port mapping to `5433:5432` to avoid the conflict (keeps dockerized Postgres as the testarget).
   - Consequence: update local parity wiring + test DSN to use port 5433.

6) **Python dependency for Postgres**
   - **Issue:** `psycopg` missing in venv; tests failed.
   - **Decision:** install `psycopg[binary]` in the active venv to match `pyproject.toml` and enable tests.

### Evidence / outcomes
- Docker daemon initially offline; switched contexto `desktop-linux`.
- MinIO + Postgres stack started successfully via compose after image tag fix.
- S3 integration tests passed once MinIO creds were set and bucket created.
- Postgres smoke still failed until port conflict identified (local Postgres on 5432).

### Follow‑ups required
- Update local parity wiring + test DSN to **port 5433**.
- Re‑run Postgres smoke test against Dockerized DB.
- Document final test results and mark Phase 2.5 complete when both S3 and Postgres integration tests pass.

---
## Entry: 2026-01-24 11:26:44 — Phase 2.5 local parity tests (completion)

### What we did (execution)
1) **Local parity stack**
   - Started MinIO + Postgres via `infra/local/docker-compose.sr-parity.yaml`.
   - Switched Docker contexto `desktop-linux` and corrected MinIO/MC image tags to `latest` (previous pinned tag not found).
   - Fixed MC initialization to use `MC_HOST_local` + `mb --ignore-existing` (shell entrypoint not supported).
2) **Port conflict resolution**
   - Identified Windows Postgres on **5432**, which hijacked test DSN.
   - Rebound Dockerized Postgres to **5433** and updated local parity wiring accordingly.
3) **Test dependencies**
   - Installed `psycopg[binary]` into the active venv to run Postgres smoke tests.
4) **Integration tests**
   - S3 integration tests executed against MinIO.
   - Postgres authority store smoke executed against Dockerized Postgres.

### Evidence (commands + env)
Environment used (values redacted; set locally as required):
- `SR_TEST_PG_DSN` (local Postgres DSN on port 5433)
- `SR_TEST_S3_BUCKET`
- `SR_TEST_S3_PREFIX`
- `SR_S3_ENDPOINT_URL`
- `SR_S3_REGION`
- `SR_S3_PATH_STYLE`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Test run:
- `pytestests/services/scenario_runner/test_s3_store.py tests/services/scenario_runner/test_authority_store_postgres.py`
  - Result: **3 passed**

### Conclusion
Phase 2.5 hardening tests now pass on a local parity stack (MinIO + Postgres). Combined with prior concurrency testing, Phase 2.5 is **complete** for local parity validation.

---
## Entry: 2026-01-24 12:01:45 — Phase 1 & Phase 2 completion confirmation

### Confirmation
Based on implemented code + local parity integration tests (MinIO + Postgres), Phase 1 and Phase 2 are **100% complete**:
- **Phase 1:** contracts + truth surfaces validated and wired.
- **Phase 2:** durable storage + idempotency + hardening (2.1–2.5) completed, with local parity tests passing.

### Evidence
- Phase 2.5 integration tests passed on local parity stack (see Entry: 2026-01-24 11:26:44).
- Build plan updated to mark Phase 2 complete.

---
## Entry: 2026-01-24 12:04:07 — Phase 3 planning (evidence + gate completeness)

### Problem / goal
Phase 3 must make SR evidence handling **production‑complete**:
- enforce full HashGate coverage,
- validate receipts and output locators against contracts,
- bind evidence to instance scope deterministically,
- and keep the system fail‑closed.

### Decision trail (brainstorm + choices)
1) **Gate closure is authoritative**
   - **Assumption:** engine interface pack is the only source of gate requirements.
   - **Decision:** required_gates = `gate_map.required_gate_set(outputs)` ∪ `output.read_requires_gates`.
   - **Rationale:** prevents “latest output” scanning and enforces no‑PASS‑no‑read.

2) **Receipt validation is mandatory**
   - **Decision:** validate gate receipts against their schemas (interface pack) before using them.
   - **Rationale:** receipts are proof artifacts; schema violations must fail‑closed.

3) **Instance‑proof binding**
   - **Observation:** not all gates are instance‑scoped; some are static/world‑level.
   - **Decision:** enforce pin binding only when gate scope is instance‑scoped (seed/scenario/run_id/parameter_hash); otherwise accept gate at broader scope.
   - **Rationale:** avoids false negatives while preserving provenance.

4) **Output locator integrity**
   - **Decision:** validate locators against output schema (path + pins + content_digest), and compute content_digest deterministically for files/dirs/globs.
   - **Rationale:** downstream needs immutable by‑ref locators with verifiable provenance.

5) **Evidence bundle determinism**
   - **Decision:** bundle_hash computed from sorted locators + receipts + policy_rev; record stable reason codes for WAITING/FAIL/CONFLICT.
   - **Rationale:** supports replay + audit; idempotent results across retries.

6) **Fail‑closed posture**
   - Missing/invalid gates or mismatched instance pins → WAITING/FAIL/QUARANTINE.
   - Unknown compatibility versions → reject/quarantine rather than guess.

### Alternatives considered
- **Lenient receipt parsing:** rejected (breaks no‑PASS‑no‑read).
- **Force instance‑proof on all gates:** rejected (false conflicts for static gates).

### Outputs / deliverables (Phase 3)
- Gate receipt schema validation + instance‑scope enforcement.
- Output locator validation + integrity digest rules.
- Evidence classification rules (COMPLETE/WAITING/FAIL/CONFLICT) tightened.
- Tests for each branch and for mismatched scopes.

---
## Entry: 2026-01-24 12:20:05 — Phase 3 scratchpad (live decision notes)

Re‑reading interface pack because the previous entry feels too clean. A few things hitting me immediately:
- `engine_gates.map.yaml` scopes are all **fingerprint** right now. That means PASS receipts we can verify are tied only to `manifest_fingerprint`.
- `engine_outputs.catalogue.yaml` lists **many outputs with instance scopes** (`scope_seed_manifest_fingerprint[_scenario_id]`, `scope_seed_manifest_fingerprint_parameter_hash...`, `scope_seed_parameter_hash_run_id`, etc).
- `data_engine_interface.md` explicitly says: **instance‑scoped outputs require instance proof** (receipt bound to `engine_output_locator` + digest).

This is a tension: **we don’t see any instance‑proof receipts in the pack**, only segment PASS flags and s0_gate_receipts that are fingerprint‑scoped. So if we go strict, SR will likely WAITING/FAIL for a lot of instance‑scoped outputs (because the required receipt doesn’t exist yet).

I need to choose how to handle this in Phase 3:
1) **Strict fail‑closed**: require an instance‑proof receipt; if missing → WAITING → FAIL at deadline. This aligns with doctrine but may block readiness on most runs.
2) **Temporary bridge**: accepthe output locator content_digest as “instance proof” even without a receipt. That’s not whathe interface pack says, but it keeps SR usable.
3) **Policy flag**: default strict, but allow a controlled exception for dev only (still uncomfortable).

My bias: **option 1** (strict fail‑closed) unless you explicitly want a bridge. If we choose strict, we should surface a spec gap to the engine interface pack rather than silently weakening SR.

Concrete implementation notes:
- Add a **scope classifier** in SR: parse `output.scope` and mark outputs as instance‑scoped when scope includes seed/scenario_id/parameter_hash/run_id.
- For instance‑scoped outputs, SR should **look for an instance‑proof receipt** bound to locator/digest (not currently available).
- If that receipt doesn’t exist, evidence should be WAITING/FAIL (explicit reason code like `INSTANCE_PROOF_MISSING`).
- For fingerprint‑scoped outputs, existing PASS gate receipts remain sufficient.

Open question I need your call on:
→ Do we enforce strict instance‑proof now and accepthat it may block readiness, or do we allow a temporary bridge (clearly marked) while the interface pack is extended?

---
## Entry: 2026-01-24 12:18:50 — Phase 3 planning expansion (corrective; detail-first)

I’m correcting the earlier Phase 3 planning entry because it reads like a checklist. Below is the actual decision trail I’m following in real time so the intent and tradeoffs are explicit.

### What triggered this phase (problem framing)
I need to make SR evidence handling production-grade and **fail-closed** while aligning with the engine interface pack. Phase 3 is where we eliminate ambiguous evidence handling and make the gate + receipt + locator chain deterministic and auditable. The key friction I’m seeing: **gate receipts appear fingerprint-scoped**, while **many outputs are instance-scoped**. That creates a mismatch if we require instance proof for instance outputs (which the interface pack says we must).

### Authorities I’m using (inputs)
- docs\model_spec\data-engine\interface_pack\engine_gates.map.yaml
- docs\model_spec\data-engine\interface_pack\engine_outputs.catalogue.yaml
- docs\model_spec\data-engine\interface_pack\data_engine_interface.md
- SR design authority notes (N1–N8) for evidence intent and no-PASS-no-read posture.
- Platform doctrine (pins as law, fail-closed, provenance first-class).

### What I actually observe (not assumptions)
- Gate map entries are **fingerprint-scoped** (manifest_fingerprint). I don’t see any receipt artifacts that bind to run_id/parameter_hash/scenario_id.
- Output catalogue includes many **instance-scoped outputs** (scopes include seed/scenario_id/parameter_hash/run_id).
- Interface pack text says: **instance-scoped outputs require instance proof** (receipt bound to locator + digest). That proof doesn’t exist in the pack today.

### Tension / risk surfaced
If I enforce instance-proof strictly, SR will WAIT/FAIL a large class of instance-scoped outputs because the required receipt isn’t available. If I relax the requirement, I would be violating the doctrine and could allow “latest output” reads without proof.

### Options I’m weighing (with why they matter)
1) **Strict fail-closed** (default):
   - Require instance proof receipts for instance-scoped outputs. If missing, SR stays WAITING and eventually FAILS.
   - Pros: aligned with doctrine, no false proof, auditability clean.
   - Cons: likely blocks readiness until engine pack adds instance-proof receipts.
2) **Temporary bridge (explicitly flagged)**:
   - Accept an output locator digest as “instance proof” even without a receipt.
   - Pros: keeps SR usable short-term.
   - Cons: breaks spec; weakens evidence chain; must be clearly marked as non-prod.
3) **Policy toggle** (strict by default, allow bridge in dev only):
   - Pros: safety in prod, dev unblocked.
   - Cons: risk of “temporary” becoming permanent; adds complexity.

My current bias is **option 1 (strict)**, and if that blocks, we surface the pack gap to the engine side rather than diluting SR. But I need explicit confirmation if you want a bridge.

### Intended mechanics (what I’d actually build)
- **Gate requirement resolution**:
  - Compute required_gates = gate_map.required_gate_set(outputs) UNION outputs.read_requires_gates.
  - This prevents “latest output” reads and enforces no-PASS-no-read.
- **Receipt validation**:
  - Validate receipts against gate schemas from interface pack before using them.
  - Reject malformed receipts early; record reason codes (e.g., RECEIPT_SCHEMA_INVALID).
- **Scope classification**:
  - Parse output.scope and classify as 
ingerprint vs instance.
  - Instance scope = any of seed/scenario_id/parameter_hash/run_id in scope string.
- **Instance-proof enforcement**:
  - For instance-scoped outputs, require receipt bound to locator + digest.
  - Missing/invalid => WAITING then FAIL at deadline, with explicit reason INSTANCE_PROOF_MISSING.
- **Output locator integrity**:
  - Validate locator fields (pins + path + content_digest) and compute digest deterministically.
  - For dirs/globs, compute stable digest over sorted file listing.
- **Evidence bundling**:
  - bundle_hash from sorted locators + receipt ids + policy_rev.
  - Evidence status is monotonic (WAITING -> COMPLETE/FAIL/CONFLICT only).

### Invariants to enforce
- No-PASS-no-read: if a required gate is missing/invalid, SR must not read.
- Evidence decisions are deterministic given the same inputs.
- Append-only evidence trail; no mutable overwrites.
- Monotonic evidence status; no downgrade from COMPLETE.

### Logging + audit points
- Log evidence evaluation start/end with reason codes.
- Record missing gates/receipts in SR ledger.
- Include pins + policy_rev in evidence outputs for replay.

### Security / compliance posture
- Fail-closed on unknown compatibility, missing receipts, or schema mismatch.
- No secret material in logs or implementation notes.
- Explicit provenance linking (pins + receipt IDs + locator digests).

### Performance considerations
- Avoid scanning all outputs; derive required gates from map + per-output requirements.
- Digest computation should be streaming for large files.
- Cache gate map and output catalogue parsing within SR process.

### Deployment / environment considerations
- Production target: AWS (S3 + RDS Postgres + ECS Fargate + Kinesis).
- Local parity: MinIO + Postgres remains valid for Phase 3 tests.
- Ensure behavior is identical across local parity and prod (only endpoint differences).

### Concrete file touchpoints (planned)
- src/fraud_detection/scenario_runner/evidence.py (core classification + receipt/locator checks)
- src/fraud_detection/scenario_runner/schemas.py (schema validation helpers)
- src/fraud_detection/scenario_runner/runner.py (wiring evidence evaluation)
-tests/services/scenario_runner/ (new tests for instance-proof + receipt invalid cases)

### Validation plan (tests)
- Instance-scoped output with no instance proof => WAITING/FAIL with reason.
- Fingerprint-scoped output with PASS receipt => COMPLETE.
- Invalid receipt schema => FAIL (reason code matches).
- Output locator digest mismatch => FAIL/CONFLICT.

### Decision status
Pending: strict vs temporary bridge. I’m ready to implement strict fail-closed unless you ask for a bridge.

---
## Entry: 2026-01-24 12:29:03 — Phase 3 implementation start (evidence strictness + schema alignment)

I’m about to implement Phase 3 evidence hardening. I’m writing this before touching code so the decision trail stays live, not retrospective.

### Starting point (what exists)
- Evidence collection currently builds locators + gate receipts but **does not validate** them against engine contracts.
- Locators/receipts are serialized with `__dict__` and include `None` fields + digest as raw hex string.
- run_facts_view.schema.yaml expects the old “flat hex” digest + receipt_ref shape, which is **not aligned** with engine interface pack.
- Gate verification uses engine_gates.map.yaml but gate scope tokens are always full (manifest/parameter/seed/scenario/run_id), even when gate scope is fingerprint-only.
- Instance-proof receipts (required for instance-scoped outputs) are **not represented** in code or in interface pack artifacts.

### Phase 3 decision (already confirmed with you)
- **Strict fail-closed** in prod.
- **Dev-only bridge** allowed via policy flag, but only for local/dev; default is strict.
- Bridge = accept locator digest as provisional proof when instance receipt is missing. Must be explicitly flagged in run_facts_view so it’s never mistaken for true proof.

### Key design choices I’m making now
1) **Align SR facts view with engine contracts.**
   - Update run_facts_view.schema.yaml to accept engine-style digest objects and gate_receipt shape with artifacts instead of receipt_ref.
   - This is required because we’re now validating against engine_output_locator + gate_receipt contracts.

2) **Add engine-contract validation.**
   - Create a second schema registry for engine contracts (root = interface_pack/contracts).
   - Validate each produced locator against engine_output_locator.schema.yaml.
   - Validate each produced gate receipt against gate_receipt.schema.yaml.
   - If validation fails → **FAIL** (strict fail-closed) with explicit reason codes.

3) **Scope-correct pins.**
   - Use catalogue partitions to decide which pins belong on each locator.
   - Gate receipts will carry only pins that match the gate’s scope (fingerprint/parameter/seed/scenario/run).
   - Remove `None` fields from serialized payloads (schema does not allow nulls).

4) **Instance-proof enforcement.**
   - Output scope classified as instance-scoped if scope includes any of: seed, scenario_id, parameter_hash, run_id.
   - If instance-scoped:
     - require content_digest on locator (to bind proof).
     - require instance-proof receipt (not available in pack yet). If missing:
       - strict mode → WAITING/FAIL (reason INSTANCE_PROOF_MISSING).
       - dev-bridge mode → allow but mark evidence_notes with INSTANCE_PROOF_BRIDGE_USED.
   - This keeps us compliant by default while still letting dev iterate.

### Open risk I’m explicitly accepting (with mitigation)
- **Spec gap:** interface pack does not yet define instance-proof receipts. Strict mode may block readiness for instance-scoped outputs. I will surface this gap explicitly in the impl_actual entries and in reason codes so it can’t be ignored.

### Files I expecto touch
- src/fraud_detection/scenario_runner/evidence.py (digest objects, helpers, scope classifier, wire conversion)
- src/fraud_detection/scenario_runner/runner.py (scope-correctokens, instance-proof checks, schema validation integration)
- src/fraud_detection/scenario_runner/catalogue.py (capture availability, partitions usage)
- src/fraud_detection/scenario_runner/config.py + config/platform/sr/*.yaml (add engine_contracts_root, allow_instance_proof_bridge)
- docs/model_spec/platform/contracts/scenario_runner/run_facts_view.schema.yaml (align with engine contracts)
- tests/services/scenario_runner/* (new tests for schema/instance-proof path; update wiring helpers)

### Guardrails
- No credentials in this document.
- Every step will be appended as I decide/adjust.

---
## Entry: 2026-01-24 12:37:56 — Phase 3 implementation notes (decisions while coding)

I’ve started coding Phase 3 and documented the key decisions as they landed:

### Evidence payload alignment (schema + wire shapes)
- **Updated SR run_facts_view contract** to align with engine contracts:
  - locators now use `{algo, hex}` digest objects (not raw hex strings).
  - gate receipts now include artifacts and match the engine gate_receipt shape (no receipt_ref).
  - Added optional evidence_notes so bridge usage is explicitly recorded.
- Rationale: SR needs to emit portable evidence objects that can be validated againsthe engine interface pack.

### Schema validation strategy
- Added an **engine contracts schema registry** (root = interface_pack/contracts) and validate:
  - each locator against engine_output_locator.schema.yaml
  - each gate receipt against gate_receipt.schema.yaml
- Any schema mismatch is treated as **FAIL** with explicit reason codes (LOCATOR_SCHEMA_INVALID, RECEIPT_SCHEMA_INVALID).

### Gate scope tokens
- Gate receipts now include **only scope-appropriate tokens** but always include manifest_fingerprint (required by gate_receipt schema).
- Missing tokens in templates now produce a **missing evidence** outcome rather than a malformed path.

### Output locator pins
- Locator pins are derived from the output’s **catalogue partitions**.
- If partitions are empty, I still include manifest_fingerprint so engine_output_locator validation can succeed; this is a pragmatic assumption that “global” outputs are still anchored to the manifest. If the engine pack later clarifies truly global outputs, we should revisithis.

### Instance-proof enforcement + dev bridge
- Instance-scoped outputs are now detected from scope and require instance proof.
- Because instance receipts are not present in the interface pack, **strict mode will WAIT/FAIL** with instance_proof:{output_id}.
- If allow_instance_proof_bridge=true (dev only), SR marks evidence_notes: ["INSTANCE_PROOF_BRIDGE:{output_id}"] and proceeds.

### Policy digest update (non-circular)
- Recomputed policy_v0.yaml content_digest as **sha256 of the policy content excluding content_digest itself** (avoids circular hash).

No credentials were written anywhere.

---

## Entry: 2026-01-24 12:42:52 — Schema ref resolution fix (interface_pack path mismatch)

While adding engine contract validation, tests failed because the interface_pack contract $ref paths resolve to .../interface_pack/layer-1/..., buthe actual schemas live under docs/model_spec/data-engine/layer-1/.... The pack’s relative refs appear to be **one directory too shallow**.

Decision taken:
- In SchemaRegistry._load_yaml_ref, if the resolved file:// path does not exist and contains interface_pack, I now **fallback by removing the interface_pack/ segment** and retry.
- This is a pragmatic resolver shim to keep SR strict validation working while we wait for the interface pack paths to be corrected.

This preserves fail-closed behavior while acknowledging a spec packaging mismatch.

---

## Entry: 2026-01-24 12:43:38 — Phase 3 test scaffolding (instance-proof strict vs bridge)

Added dedicated tests to ensure Phase 3 evidence behavior is explicit:
- test_instance_proof_strict_waits: strict mode should WAIT when instance proof is missing.
- test_instance_proof_bridge_allows_ready: dev bridge should yield READY and emit evidence_notes.

These tests use a **minimal gate map** (no gates) and a **minimal output catalogue** (instance-scoped output) to isolate the instance-proof logic without requiring full engine artifacts.

---
## Entry: 2026-01-24 12:44:12 — Output availability handling

Noticed the engine catalogue includes availability: optional. I added this to OutputEntry and treat missing optional outputs as **non-blocking** (no WAIT/FAIL). Required outputs still block evidence as before.

---
## Entry: 2026-01-24 13:01:34 — Phase 3 extension: instance-proof receipts + downstream compatibility

I’m starting the next Phase 3 slice: making instance-proof receipts real (schema + path convention) and wiring SR to consume them, plus adding a parity-grade gate verification test. I’m capturing decisions live.

### What I need to solve now
1) **Instance-proof receipts aren’t defined in the interface pack**, but SR strict mode now depends on them. I must define a schema + path convention so the contract is real.
2) SR must be able to **locate, validate, and bind** those receipts to locators (target_ref + digest).
3) Downstream consumers read 
run_facts_view; we changed digest shape + receipt artifacts, so I must decide how to communicate/update that boundary.

### Decision direction (pre-implementation)
- **Define a new contract**: instance_proof_receipt.schema.yaml in interface_pack/contracts.
- **Path convention**: place instance receipts under the same layer/segment namespace as the outputs they prove, using 
receipts/instance/ and the output’s partitions. This keeps provenance localized and avoids cross-segment ambiguity.
- **SR behavior**: for instance-scoped outputs, require a PASS instance receipt whose  target_ref matches the locator and whose  target_digest equals locator.content_digest.
- **run_facts_view**: add a new optional instance_receipts array (do not overload gate_receipts). Keep backward compatibility by making it optional. Update docs so downstream is aware.
- **Downstream update decision**: update platform/docs now (even if no code yet) so that IG/OFS/others know the new receipt shape and optional field.

### Risks and mitigations
- Contract drift if engine doesn’t emit instance receipts yet → SR strict mode still WAIT/FAIL until engine implements it. This is acceptable; we’re closing the spec gap first.
- Added instance_receipts field means downstream must be made aware; I’ll update platform-wide notes + SR contract README.

### Planned touchpoints
- docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml
- docs/model_spec/data-engine/interface_pack/data_engine_interface.md
- docs/model_spec/data-engine/interface_pack/storage_layout_v1.md
- docs/model_spec/data-engine/interface_pack/README.md
- docs/model_spec/platform/contracts/scenario_runner/run_facts_view.schema.yaml
- src/fraud_detection/scenario_runner/runner.py (receipt lookup + validation + facts view field)
-tests/services/scenario_runner/test_gate_verification_integration.py
- docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md (compat note)

----
## Entry: 2026-01-24 13:08:38 — Instance-proof receipt contract + SR consumption (implemented)

### Interface pack changes
- Added contracts/instance_proof_receipt.schema.yaml and xamples/instance_proof_receipt.example.json.
- Documented instance-proof receipt path convention in data_engine_interface.md and storage_layout_v1.md.
- Updated interface pack README to listhe new contract + example.

### SR behavior updates
- SR now looks for instance receipts at:
  data/<layer>/<segment>/receipts/instance/output_id=<output_id>/<partitions>/instance_receipt.json
- Rreceipts are validated against instance_proof_receipt.schema.yaml and bound to the locator:
  -  target_ref.output_id must match locator output_id.
  -  target_ref.path must match locator path (relative paths allowed vs engine_root).
  -  target_digest.hex must equal locator.content_digest.hex.
- Missing receipts → WAIT/FAIL unless allow_instance_proof_bridge=true (dev-only).
- Facts view now includes optional instance_receipts when present.

### Tests added
-  test_gate_verification_integration uses the real gate map and a synthetic bundle to verify HashGate PASS flow end-to-end (SR reuse path → READY).

### Compatibility updates
- run_facts_view contract documents instance_receipts and digest object shapes; platform blueprint note updated to alert downstream consumers.

---
## Entry: 2026-01-24 14:30:15 — Black-box instance proof (SR-verifier receipts)

You explicitly require the engine to remain a black box. That means SR cannot rely on engine-emitted instance receipts. Instead, SR must generate **verifier receipts** itself, based only on the output bytes it reads.

### Why compute a digest at all
- A schema only proves **shape**, not **identity** or **immutability**.
- The digest binds the exact output instance bytes to the run pins (manifest_fingerprint, seed, scenario_id, etc.).
- This creates a deterministic, auditable proof that “this exact output instance was the one SR used,” which is required for no‑PASS‑no‑read on instance‑scoped outputs.

### Black-box compliant plan
- SR computes content_digest over the output bytes (already required for locators).
- SR writes an instance_proof_receipt into **SR’s own object store** (not engine storage).
- run_facts_view.instance_receipts includes the receipt payload and references the SR receipt path.
- This keeps the engine opaque while still enforcing strict instance proof.

---

## Entry: 2026-01-24 14:36:13 — Phase 3 black‑box instance‑proof implementation plan (SR‑verifier receipts)

I’m about to implement the black‑box‑safe instance‑proof path. This entry captures the actual thinking path before code changes so the reasoning trail stays live.

### What forced this change
You’ve made it explicit that the engine must remain a black box. That means SR **cannot** depend on engine‑emitted instance receipts or on modifying engine storage/layout. If SR still enforces instance‑scoped proofs, it must generate that proof itself using only the bytes it already reads.

### What I’m trying to guarantee (non‑negotiable)
- **No‑PASS‑no‑read** still holds for instance‑scoped outputs.
- **Fail‑closed** on missing/invalid instance proof (no “best effort”).
- **Idempotent + append‑only**: instance receipts must be write‑once and stable across retries.
- **Black‑box safety**: no assumptions about engine internals, no writes into engine storage, no engine‑side code changes.

### Options I considered (and why I chose the final one)
1) **Keep consuming engine receipts** (current behavior)
   - Rejected because it violates the black‑box constraint and requires engine changes to pass strict mode.
2) **Skip receipts and treat locator digest as “good enough”**
   - Rejected because it weakens the proof chain and collapses “evidence of bytes” into “mere pointer.”
3) **SR‑verifier receipts in SR object store (chosen)**
   - SR already computes locator digests; we can bind those bytes to scope and emit an auditable receipt in SR’s own store.
   - Keeps engine opaque while still enforcing instance‑proof.

### Decision I’m locking in now
- **SR emits instance‑proof receipts** in its own object store (under the SR prefix), not in engine storage.
- Receipts are produced only for **instance‑scoped** outputs and must bind:
  - output_id
  - scope tokens (manifest_fingerprint + any instance partitions)
  - target_ref = locator (path + pins)
  - target_digest = locator.content_digest
- Receipts are **validated against the instance_proof_receipt.schema.yaml** contract so they are portable and audit‑friendly.

### Concrete mechanics I will implement
- **Receipt path convention (SR store):**
  `fraud-platform/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`
  - Scope partitions ordered: manifest_fingerprint, parameter_hash, seed, scenario_id, run_id.
  - This path is deterministic so the receipt is idempotent across retries.
- **Receipt creation flow** (inside evidence collection):
  1) For each instance‑scoped output with a content digest, build scope tokens.
  2) Build receipt payload (status=PASS, receipt_kind=instance_proof, target_ref/target_digest).
  3) Write with `write_json_if_absent` to enforce immutability.
  4) If a receipt exists, read and verify that **critical fields match** (ignore produced_at_utc if present) to prevent drift.
- **Evidence gating:**
  - If scope tokens or digest are missing → WAITING/FAIL (same as missing evidence).
  - No dev‑bridge for instance proof in this path; the receipt is always created by SR when possible.

### Why compute the digest at all (the core rationale)
- The digest is the **only objective binding** between “the bytes SR saw” and “the run pins.”
- It prevents a downstream reader from swapping content while reusing the same locator path.
- It makes evidence **replayable and auditable** even though the engine is opaque.

### Planned code touchpoints (before writing)
- `src/fraud_detection/scenario_runner/runner.py`
  - Remove engine‑receipt lookup.
  - Add receipt creation + storage in SR object store.
  - Update instance‑proof evidence evaluation to use SR receipts.
- `tests/services/scenario_runner/test_instance_proof_bridge.py`
  - Replace “strict vs bridge” expectations with “receipt emitted by SR” expectations.
- `docs/model_spec/...`
  - Update SR contract README to describe SR‑emitted receipts and SR receipt path.
  - Clarify in interface_pack docs that engine receipts are optional; SR verifier receipts are used when engine is black‑box.

### Note on text integrity
I also fixed missing‑letter typos in earlier impl_actual entries (no semantic changes), since you asked for clean, readable notes.

---

## Entry: 2026-01-24 14:43:08 — Phase 3 black‑box receipts implemented (SR‑verifier receipts)

I’ve now applied the black‑box path in code. This captures the concrete decisions made while implementing it, not just the outcome.

### What changed in SR evidence flow
- Removed engine‑receipt lookup entirely; SR now **generates verifier receipts** in its own object store.
- Instance‑scoped outputs are handled by a new `_ensure_instance_receipt` flow that:
  - builds a scope from catalogue partitions + manifest_fingerprint,
  - binds `target_ref` to the output locator,
  - binds `target_digest` to the locator’s content_digest,
  - writes receipts **write‑once** using `write_json_if_absent`, and
  - validates against `instance_proof_receipt.schema.yaml` before commit.
- Receipt path now lives under SR’s prefix:
  `fraud-platform/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`
  (partition order: manifest_fingerprint → parameter_hash → seed → scenario_id → run_id).

### Why I omitted produced_at_utc in receipts
- A timestamp makes the payload non‑deterministic and can cause drift on re‑entry.
- Since receipts are write‑once, the store itself preserves the creation time if we ever need it (via object metadata or audit logs). I can add produced_at_utc later if we agree to treat it as immutable once written.

### New strict failure points (explicit reason codes)
- `INSTANCE_DIGEST_MISSING` if a locator lacks a digest (shouldn’t happen if output exists).
- `INSTANCE_SCOPE_MISSING` if required scope tokens are missing (configuration error).
- `INSTANCE_RECEIPT_SCHEMA_INVALID` if the receipt payload fails schema validation.
- `INSTANCE_RECEIPT_DRIFT` if an existing receipt’s critical fields don’t match the newly computed proof.

### Test + contract adjustments made during implementation
- Updated `tests/services/scenario_runner/test_instance_proof_bridge.py` to assert SR emits a verifier receipt and commits READY.
- Ran pytest for that test (1 passed; only RefResolver deprecation warnings).
- Fixed a YAML escaping issue in `instance_proof_receipt.schema.yaml` (regex pattern string) uncovered by schema validation.

### Documentation updates while coding
- Clarified in `data_engine_interface.md` and `storage_layout_v1.md` that engine‑emitted receipts are optional and SR verifier receipts live under the SR object store.
- Updated SR contract README + service README to document the SR receipt path and black‑box posture.
- Added a note to interface_pack README that instance receipts may be emitted by SR when the engine is opaque.

### Compatibility note (policy flag)
- `allow_instance_proof_bridge` remains in policy for backward compatibility but is now deprecated in SR behavior (no bridge path in black‑box mode).

---

## Entry: 2026-01-24 14:48:32 — Phase 3 follow‑ups (remove bridge flag, add drift test, update plan)

I’m about to execute the three requested follow‑ups. This entry captures the intent and the reasoning trail before touching code.

### Why these changes are needed
- **Bridge flag removal**: the SR now emits verifier receipts in a black‑box‑safe way. Keeping `allow_instance_proof_bridge` creates a false affordance and an unused prod risk knob.
- **Receipt drift test**: we must prove that SR rejects pre‑existing receipts that don’t match the computed proof (idempotency + immutability enforcement).
- **Build plan update**: Phase 3 status should reflect that instance‑proof receipts are now implemented in SR (no longer blocked by interface pack gap).

### Decisions I’m making now
1) **Remove `allow_instance_proof_bridge` everywhere** (policy schema, policy YAML, tests, README notes).
   - Keep the historical impl_actual mentions unchanged; record the removal as a new entry (append‑only).
2) **Add a receipt‑drift integration test** using the minimal output catalogue.
   - Pre‑seed a mismatching receipt in SR’s object store and assert the run fails with `INSTANCE_RECEIPT_DRIFT`.
   - This proves write‑once + drift detection semantics, not just presence.
3) **Update Phase 3 build plan** to mark instance‑proof receipts as implemented and add drift test to DoD.

### Files I will touch (planned)
- `src/fraud_detection/scenario_runner/config.py` (remove policy field)
- `config/platform/sr/policy_v0.yaml` (remove field, recompute content_digest)
- `tests/services/scenario_runner/test_instance_proof_bridge.py` (add drift test; remove bridge logic)
- `tests/services/scenario_runner/test_gate_verification_integration.py` (remove bridge param)
- `services/scenario_runner/README.md` (remove deprecated flag mention)
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md` (Phase 3 status + DoD)
- `docs/logbook/01-2026/2026-01-24.md` (record actions + test results)

### Guardrails
- No credentials in plan or notes.
- Receipt drift test will only touch local temp artefacts.
- Content digest recomputed deterministically from policy content without the digest field.

---

## Entry: 2026-01-24 14:50:32 — Phase 3 follow‑ups executed (bridge removal + drift test + plan update)

I’ve completed the three requested actions. Here is what I actually changed and why, in the same decision‑trail style.

### 1) Bridge flag removal (policy + tests + docs)
- **Removed** `allow_instance_proof_bridge` from `PolicyProfile` and from `config/platform/sr/policy_v0.yaml`.
- **Why:** SR now always emits verifier receipts; a bridge flag is unused and creates a false safety‑off switch for production.
- **Impact:** policy content_digest was recomputed after removing the field to preserve pinned policy_rev integrity.
- **Docs:** service README now states there is no bridge; SR emits verifier receipts directly.

### 2) Receipt‑drift test (immutability proof)
- Added a new test that **pre‑seeds** a mismatching receipt in SR’s object store, then submits a run.
- Expected behavior verified: SR fails the run with reason `INSTANCE_RECEIPT_DRIFT` (idempotent, fail‑closed).
- This protects against silent drift if a receipt already exists with different target_ref/digest.

### 3) Build plan update
- Phase 3 status now reflects that black‑box verifier receipts are implemented.
- Added an explicit DoD item for receipt drift testing under Phase 3 validation.

### Test run
- `pytest tests/services/scenario_runner/test_instance_proof_bridge.py` → 2 passed (RefResolver deprecation warnings only).

### Files touched (high‑signal)
- `src/fraud_detection/scenario_runner/config.py`
- `config/platform/sr/policy_v0.yaml`
- `tests/services/scenario_runner/test_instance_proof_bridge.py`
- `tests/services/scenario_runner/test_gate_verification_integration.py`
- `services/scenario_runner/README.md`
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`

---

## Entry: 2026-01-24 15:05:10 — Gate map alignment with engine specs (6B hashing law)

I’m about to update the interface_pack gate map to match the **engine specs** (source‑of‑truth), not the run artefacts. The failing test shows a mismatch, and the correct fix is to derive the interface pack from the engine contracts/policies.

### Source‑of‑truth consulted
- `config/layer3/6B/segment_validation_policy_6B.yaml` → `bundle_hashing_law: index_json_ascii_lex_raw_bytes_excluding_passed_flag`.
- `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml` → 6B passed flag encodes SHA‑256 over the validation bundle; index.json is a bundle artefact.
- 6B index.json in the run artefact lists the evidence file paths.

### Decision
Update `engine_gates.map.yaml` for `gate.layer3.6B.validation` to reflect the policy’s hashing law and extend GateVerifier accordingly.

### Expected behavior after change
- GateVerifier will hash **raw bytes of files listed in index.json**, sorted ASCII‑lex, excluding `_passed.flag`.
- This matches the 6B policy and makes the 6B gate test pass **for the right reason**.

### Planned code/doc touchpoints
- `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml` (new verification_method kind for 6B).
- `src/fraud_detection/scenario_runner/evidence.py` (GateVerifier supports new hashing law).
- `tests/services/scenario_runner/test_gate_verifier.py` should pass for 6B after update.

---

## Entry: 2026-01-24 15:20:47 — 6B gate verification fixed via engine policy law

I updated the interface pack and GateVerifier to match the **engine policy** for Segment 6B hashing.

### What changed
- `engine_gates.map.yaml`: `gate.layer3.6B.validation` now uses verification_method
  `sha256_index_json_ascii_lex_raw_bytes` and excludes `_passed.flag` and `index.json`.
- `GateVerifier` now supports this method by:
  - reading index.json,
  - collecting `path` entries,
  - ASCII‑lex ordering,
  - hashing raw bytes of those files relative to the bundle root.

### Why this is the correct derivation
The 6B validation policy (`config/layer3/6B/segment_validation_policy_6B.yaml`) explicitly defines
`bundle_hashing_law: index_json_ascii_lex_raw_bytes_excluding_passed_flag`, which implies
index‑driven raw‑bytes hashing rather than “hash all files in the directory.”

### Test result
- `pytest tests/services/scenario_runner/test_gate_verifier.py` → 2 passed.

### Residual risk
- If other segments later adopt index‑driven hashing, we’ll need to update their gate map entries
  (and possibly expand test coverage beyond 6B).

---

## Entry: 2026-01-24 15:24:03 — RefResolver deprecation fix (move to referencing registry)

I’m about to remove `jsonschema.RefResolver` usage and replace it with the modern `referencing` registry. This eliminates the deprecation warning and aligns SR with jsonschema’s current APIs.

### Why this change is needed
- `RefResolver` is deprecated and will be removed in a future jsonschema release.
- Our SchemaRegistry also includes a **shim** to fix interface_pack $ref path issues; that needs to be preserved.

### Design constraints I’m honoring
- **Fail‑closed**: any schema validation failure remains a hard error.
- **Interface pack shim**: keep the fallback that strips `interface_pack/` when a $ref path doesn’t exist.
- **Minimal surface area**: only touch SchemaRegistry; keep callers unchanged.

### Planned approach
- Replace `RefResolver` with `referencing.Registry` and `Resource`.
- Custom resolver for `file://` URIs that:
  - loads YAML/JSON,
  - if path missing and contains `interface_pack/`, retries without that segment,
  - registers loaded resources with the registry for recursive references.

### Files to touch
- `src/fraud_detection/scenario_runner/schemas.py`
- logbook + impl_actual entries.

---

## Entry: 2026-01-24 15:25:55 — RefResolver removed; referencing registry in use

I replaced `jsonschema.RefResolver` with the `referencing` registry to eliminate the deprecation warning and align with current jsonschema APIs.

### What changed
- `SchemaRegistry.validate` now builds a `Registry(retrieve=...)` and seeds it with the root schema’s URI.
- Custom `file://` retriever loads YAML and applies the interface_pack path‑shim (strip `interface_pack/` when needed).
- Unknown/unsupported URIs now raise `NoSuchResource`, keeping fail‑closed behavior.

### Why this preserves behavior
- The same YAML loading logic is used, but reference resolution is now standards‑compliant and forward‑compatible.
- The interface_pack shim remains intact so validation doesn’t regress due to the known path mismatch.

### Test result
- `pytest tests/services/scenario_runner/test_gate_verifier.py` → 2 passed, no deprecation warnings.

---

## Entry: 2026-01-24 15:32:40 — Phase 3 hardening plan (parity integration + negative evidence cases)

I’m proceeding with Phase 3 hardening. I’m writing this **before** coding and will keep appending as decisions are made.

### What remains open (Phase 3 DoD gaps)
1) **Full SR reuse integration test** against real engine artefacts (not synthetic).
   - This must exercise: output locators + gate verification + instance‑proof receipts + READY commit.
2) **Negative evidence cases** against real artefacts (missing gate or output) to assert WAITING/FAIL behavior.

### My approach (senior MLOps posture)
- Treat the engine artefacts under `runs/local_full_run-5` as **immutable truth**.
- Avoid modifying engine artefacts; tests must be non‑destructive (use a temp copy or selectively remove via temp dir).
- Use `Strategy.FORCE_REUSE` so SR only validates evidence (no engine invocation).

### Planned design for tests
**A) Full SR parity reuse test (positive):**
- Build a RunRequest pointing at `runs/local_full_run-5/...` as `engine_run_root`.
- Use the real `engine_outputs.catalogue.yaml` + `engine_gates.map.yaml` from interface_pack.
- Assert:
  - response message is READY
  - run_facts_view exists
  - gate_receipts length > 0
  - instance_receipts length > 0 (SR verifier receipts emitted)

**B) Negative evidence test (gate missing):**
- Copy only the minimal 6B validation bundle to a temp engine_root and delete `_passed.flag`.
- Force SR reuse with that engine_root.
- Expect WAITING (if within evidence_deadline) or FAIL if we set evidence_wait_seconds=0.
- Use policy override in test to keep this deterministic.

### Files I expect to touch
- `tests/services/scenario_runner/test_gate_verification_integration.py` (add parity SR flow)
- `tests/services/scenario_runner/test_instance_proof_bridge.py` or new test file for negative evidence case
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md` (Phase 3 DoD update)
- Logbook + impl_actual append entries as I go

---

## Entry: 2026-01-24 15:33:24 — Phase 3 hardening: start building parity integration test

I’m moving into the parity integration test now. I want to use the real run artefacts without mutating them, so the safest path is to **read them in place** for the positive test and **copy a minimal subset** for the negative case.

### Evidence I need from local_full_run‑5
- gate map + output catalogue from interface_pack
- a stable engine_root that contains validation bundles + outputs for at least one segment (6B is the most complete)

### Test shape (positive)
- SR run request uses `engine_run_root = runs/local_full_run-5/<run_id>`
- Strategy = FORCE_REUSE (SR doesn’t invoke engine)
- Assert READY, non‑empty gate_receipts, and SR‑emitted instance_receipts

I’m going to implement this by extending `test_gate_verification_integration.py` because it already wires SR with the real gate map/catalogue.

---

## Entry: 2026-01-24 15:37:52 — Phase 3 hardening: negative evidence test (missing gate flag)

I implemented the negative evidence case using **real artefacts copied to a temp engine_root** so we don’t mutate the canonical run data.

### What I actually built
- New test: `tests/services/scenario_runner/test_evidence_negative_integration.py`.
- It copies the **6B validation bundle** into a temp engine_root, then deletes `_passed.flag`.
- It also copies a required output (`sealed_inputs_6B.json`) so the only failure is the missing gate flag.
- Policy sets `evidence_wait_seconds=0` to make the outcome deterministic (`EVIDENCE_MISSING_DEADLINE`).

### Why this is the right negative case
- Missing `_passed.flag` is the cleanest “no‑PASS‑no‑read” failure and aligns with gate semantics.
- We keep outputs present so we’re testing gate enforcement, not output discovery.
- The test is non‑destructive because it operates on a temp copy.

### Expected outcome
- SR returns “Reuse evidence failed.”
- run_status = FAILED
- reason_code = EVIDENCE_MISSING_DEADLINE

---

## Entry: 2026-01-24 15:42:18 — Phase 3 parity test adjustment (gate conflicts in local_full_run‑5)

I tried to use `s3_flow_anchor_with_fraud_6B` for the full reuse parity test, but SR quarantined the run due to **gate conflicts** across upstream segments. I validated this directly:

- Required gates for 6B include 1A/1B/2A/2B/3A/3B/5A/5B/6A/6B.
- Only 1A, 1B, 3A, 6B pass with the current artefacts.
- 2A/2B/3B/5A/5B/6A fail under the gate hashing law in the interface pack.

That means a “deep” 6B output won’t reach READY without also fixing the gate map for those segments (derived from their policies). That’s a larger scope than Phase 3 hardening right now.

### Decision (short‑term, still valid for Phase 3 DoD)
- Keep the parity reuse test **real** but target a **1A output** (`sealed_inputs_1A`) so the gate closure is just `gate.layer1.1A.validation`, which passes in local_full_run‑5.
- This still exercises SR reuse flow, real gate verification, locator creation, facts_view commit, and READY emission using real artefacts.

### Follow‑up (future hardening)
- Derive gate hashing laws for 2A/2B/3B/5A/5B/6A from their segment policies, then re‑enable a deep 6B output for the parity test.

---

## Entry: 2026-01-24 15:40:00 — Phase 3 hardening: parity + negative tests executed

I ran the new parity and negative evidence integration tests after adjusting the parity target to a 1A output.

### Test runs
- `pytest tests/services/scenario_runner/test_gate_verification_integration.py tests/services/scenario_runner/test_evidence_negative_integration.py`
  - Result: **3 passed**

### What this proves now
- SR reuse flow can reach READY against **real artefacts** (1A output, real gate map, real engine root).
- SR fails closed on **missing gate flag** with deterministic `EVIDENCE_MISSING_DEADLINE` when evidence_wait_seconds=0.
- We have at least one positive + one negative parity case, both non‑destructive.

### Remaining Phase 3 hardening gap (explicit)
- Deep outputs (6B) still conflict because upstream gate hashing laws for 2A/2B/3B/5A/5B/6A are not yet derived into the interface pack.

---

## Entry: 2026-01-24 15:41:12 — Referencing resolver fix for relative $id

During the new parity tests, schema validation failed with `Unresolvable: ../layer-1/...` even after switching to `referencing`. Root cause: engine interface pack schemas use **relative $id** values (e.g., `engine_output_locator.schema.yaml`), so the resolver base URI became relative and the registry could not resolve `../layer-1/...` refs unless we normalised the base.

### Fix applied
- When a schema has a relative `$id`, I override it **in-memory** with the file URI of the schema path for validation.
- This keeps the schema files untouched while ensuring references resolve as file paths.
- The interface_pack shim (strip `interface_pack/` on missing paths) still applies.

### Result
- Parity + negative tests now resolve refs correctly under `referencing`.

---

## Entry: 2026-01-24 15:48:12 — Narrative logging plan (SR runtime visibility)

I’m adding narrative logging to SR so the console isn’t idle and a new user can follow what’s happening. This is **not** telemetry plumbing yet; it’s run‑flow narration at INFO level.

### Why now
- SR is doing correct work but is silent during reuse/verification flows, which is confusing for new operators.
- Engine logs show the value of “always‑on narration” during long jobs; SR should do the same for control‑plane steps.

### Logging strategy (non‑intrusive, safe)
- Use Python’s stdlib `logging` (no new dependencies).
- Add `configure_logging()` for CLI/service so INFO logs show by default.
- In SR core, log **major flow milestones** and **summaries**, not every item.

### Planned log points
- Submit received (run_equivalence_key, requested outputs count, engine_root).
- Run_id resolved + lease acquisition outcome.
- Plan compiled (outputs count, required gates count, strategy).
- Evidence collection start + output locator summary.
- Gate verification summary (passed/failed/missing/conflicts).
- Instance‑receipt emission summary.
- Evidence result (COMPLETE/WAITING/FAIL/CONFLICT + reason).
- Commit actions (READY/WAITING/FAILED/QUARANTINED).

### Guardrails
- No secrets or config values in logs (only IDs, counts, and statuses).
- Keep logs human‑readable and friendly to “noob” readers.
- Avoid high‑volume per‑row logs; summarise counts.

### Files to touch
- `src/fraud_detection/scenario_runner/runner.py`
- `src/fraud_detection/scenario_runner/evidence.py` (if needed for gate summaries)
- `src/fraud_detection/scenario_runner/cli.py`
- `src/fraud_detection/scenario_runner/service.py`
- `src/fraud_detection/scenario_runner/logging_utils.py` (new helper)

---

## Entry: 2026-01-24 15:55:06 — Narrative logging implemented (SR flow visibility)

I’ve added INFO‑level narrative logs across the SR run flow and wired default logging in CLI/service so new users see activity in the console.

### What I logged (human‑readable milestones)
- Submit received (run_equivalence_key, requested outputs count, engine_root).
- Run_id resolved + lease outcome.
- Plan committed (outputs count, required gates count, strategy).
- Evidence collection start + locator scan summary.
- Gate verification summary (passed/failed/missing/conflicts).
- Instance receipt emission summary.
- Evidence outcome + commit actions (READY / WAITING / terminal).

### Where it lives
- `src/fraud_detection/scenario_runner/runner.py` (core narration)
- `src/fraud_detection/scenario_runner/logging_utils.py` (configure_logging helper)
- `src/fraud_detection/scenario_runner/cli.py` + `service.py` (enable INFO logs by default)

### Why this helps “noob” operators
The SR flow is now visible without digging into artefacts. It mirrors the engine’s run log style at a higher level: milestones, counts, and decisions instead of silent execution.

---

### Entry: 2026-01-24 15:57:01 — Gate hashing laws alignment (2A/2B/3B/5A/5B/6A)

Context + problem framing:
- SR HashGate verification currently uses `sha256_bundle_digest` for several upstream gates (2A/2B/3B/5A/5B/6A), which hashes the full bundle directory. Engine docs indicate these gates compute `_passed.flag` from **index-defined evidence sets**, not a raw directory hash. This mismatch risks false FAILs or false PASSes if the bundle root contains index.json or non-indexed files.
- We must treat the engine as a black box and derive the HashGate law from engine implementation notes or state-expanded specs. The interface pack should reflect those laws, and SR verification must implement them exactly.

Primary authorities to consult (in order):
- `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md`
- `docs/model_spec/data-engine/implementation_maps/segment_2B.impl_actual.md`
- `docs/model_spec/data-engine/implementation_maps/segment_3B.impl_actual.md`
- `docs/model_spec/data-engine/implementation_maps/segment_5A.impl_actual.md`
- `docs/model_spec/data-engine/implementation_maps/segment_5B.impl_actual.md`
- `docs/model_spec/data-engine/implementation_maps/segment_6A.impl_actual.md`
- If any hashing law is ambiguous, fall back to the state-expanded validation spec for that segment (S5 for 5B/6A, S5 for 3B, etc.).

Findings (from impl_actual/spec, summarized for use in SR):
- 2A: `_passed.flag` = SHA256 over raw bytes of files listed in `index.json` (index order, which is ASCII-lex by contract); `_passed.flag` and `index.json` are **excluded** from the index/digest.
- 2B: `_passed.flag` = SHA256 over raw bytes of files listed in `index.json`, sorted ASCII-lex by path; **index paths are run-root-relative** (index-only bundle) → digest must be computed from run-root base, not bundle root.
- 3B: `_passed.flag` = SHA256 over raw bytes of evidence files in ASCII-lex `path` order as listed in `validation_bundle_index_3B` (explicitly *not* the 3A index-only hex concat law).
- 5A: `_passed.flag` JSON contains `bundle_digest_sha256` computed from raw bytes of files listed in `validation_bundle_index_5A` (entries list) in ASCII-lex `path` order.
- 5B: `_passed.flag` JSON contains `bundle_digest_sha256` computed from raw bytes of files listed in `index.json` (entries list) sorted by `path` (state-expanded §6.7).
- 6A: `_passed.flag` (text) uses bundle digest computed from raw bytes of files listed in `validation_bundle_index_6A` (items list) in deterministic path order.

Decision (why + what):
- **Update interface pack HashGate verification_method** for 2A/2B/3B/5A/5B/6A to use an explicit **index-driven raw-bytes digest** method rather than bundle-root hashing. This aligns SR verification with the engine’s bundle laws and avoids false negatives/positives.
- **Extend SR GateVerifier** to:
  - Parse index formats across segments (`files`, `entries`, `items`, `members`, and top-level list).
  - Allow index-path resolution relative to **bundle root** (default) or **run root** (required for 2B).
  - Honor ASCII-lex ordering and exclusion rules.

Alternatives considered:
1) Keep `sha256_bundle_digest` and tweak exclude list → rejected because digest law is index-based, not directory-based; also fails for 2B index-only bundles.
2) Require SR to revalidate per-file `sha256_hex` vs index and compute digest from that list → unnecessary duplication; HashGate only needs the bundle digest law and does not mandate re-hashing per entry.
3) Skip digest recomputation and trust `_passed.flag` → rejected; violates “no-PASS-no-read” evidence verification and SR’s audit posture.

Implementation plan (stepwise, before coding):
1) Record hashing law evidence in this entry (done) and add logbook note with timestamp.
2) Update `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`:
   - 2A/2B/3B/5A/5B/6A `verification_method.kind` → `sha256_index_json_ascii_lex_raw_bytes`.
   - Add `path_base: run_root` for 2B; use default bundle_root for others.
   - Ensure `exclude_filenames` includes `_passed.flag` and `index.json` where appropriate.
3) Extend `src/fraud_detection/scenario_runner/evidence.py`:
   - `_digest_index_raw_bytes(...)` to handle index list variants (`files`, `entries`, `items`, `members`, or top-level list).
   - Add support for `path_base` (bundle_root vs run_root) and avoid silently ignoring missing files.
4) Run SR tests that cover gate verification and evidence integration; add/adjust tests if needed for 2B index-only base.
5) Log all actions + outcomes in `docs/logbook` with local time.

Invariants to enforce:
- Digest law must be deterministic and must follow the index ordering contract (ASCII-lex by path).
- `_passed.flag` must be excluded from digest input; `index.json` should not be included unless the index schema explicitly includes it (current segments exclude it).
- Any missing index entry file should produce a FAIL (conflict) rather than a PASS; missing bundle/flag should surface as MISSING.

Security posture:
- No credentials in plans/logs; only reference file paths and public artifacts.

Validation plan:
- Re-run SR gate verification tests on a known local run root (local_full_run-5) and ensure the HashGate PASS/FAIL matches engine artifacts.
- If 2B gate verification fails, confirm index paths are run-root-relative and digest computation uses `run_root / path`.

---

### Entry: 2026-01-24 16:00:28 — Implemented index-driven HashGate verification

What changed:
- Updated `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml` to use `sha256_index_json_ascii_lex_raw_bytes` for HashGate verification on 2A/2B/3B/5A/5B/6A (aligning SR with engine bundle laws). Added `path_base: run_root` for 2B to honor its run-root-relative index paths.
- Extended SR GateVerifier (`src/fraud_detection/scenario_runner/evidence.py`) to parse index formats across segments (`files`, `entries`, `items`, `members`, or top-level list) and to resolve index paths relative to bundle root or run root depending on the gate’s `path_base`.
- Added exclude-by-basename handling so `_passed.flag` is reliably skipped if it ever appears in index entries.

Reasoning check:
- The engine’s bundle law uses index-defined evidence sets; hashing the bundle root directory is insufficient and inconsistent with 2A/2B/3B/5A/5B/6A emission logic. This change puts SR in strict agreement with engine contracts while keeping the engine as a black box.

Files touched:
- `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
- `src/fraud_detection/scenario_runner/evidence.py`

Next validation steps:
- Re-run SR gate verification tests on local_full_run-5 to confirm 2B’s run-root base works and that 3B/5A/5B/6A gate digests match their `_passed.flag` values.

---

### Entry: 2026-01-24 16:07:47 — HashGate alignment fixes + tests

Corrections applied:
- Restored `gate.layer1.1A.validation` and `gate.layer1.1B.validation` to their original `sha256_bundle_digest` method after an unintended edit while updating the gate map.
- Updated `gate.layer1.2B.validation` and `gate.layer1.3B.validation` in the interface pack to the index-driven digest method (as intended).
- Adjusted `gate.layer3.6A.validation` ordering to `index_order` after confirming that the current engine output writes `validation_bundle_index_6A.items` in non-ASCII order while computing `_passed.flag` from that exact order.

Design intent / rationale:
- 6A spec calls for ASCII-lex ordering, but the **actual engine output** is not sorted and `_passed.flag` matches index order. For SR to verify real engine artifacts (black-box posture), we must follow the observed contract until the engine output is corrected. Documenting this mismatch here so it is explicit.

Test coverage added:
- Added gate-verifier tests for 2A/2B/3B/5A/5B/6A to cover each index shape (`files`, list, `members`, `entries`, `items`) and the 2B run-root base path.

Test results:
- `python -m pytest tests/services/scenario_runner/test_gate_verifier.py -q` (venv) → **8 passed**.

Open follow-up:
- Consider filing an engine-side note to sort `validation_bundle_index_6A.items` by path to align with the stated spec; until then, SR uses `index_order` to match real outputs.

---

### Entry: 2026-01-24 16:36:40 — Interface-pack compatibility notes (engine black-box)

Decision context:
- User explicitly wants **no engine code changes**. Therefore SR must remain aligned to actual engine outputs, even where the state-expanded spec would imply stricter ordering rules.

Decision:
- Add a small compatibility note in the interface pack (engine_gates map) documenting the 6A bundle index ordering mismatch and why SR uses `index_order`.
- This keeps SR verification correct for real outputs while making the spec deviation visible to future readers.

Planned edit:
- Update `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml` to include a top-level `compatibility_notes` section, noting:
  - 6A `validation_bundle_index_6A.items` is not ASCII-lex ordered in current engine outputs.
  - `_passed.flag` matches the **index order**, so SR uses `ordering: index_order` until the engine behavior changes.

Validation plan:
- No code behavior changes; note is documentation-only. Existing gate verifier tests remain the validation signal for correctness.

---

### Entry: 2026-01-24 16:44:51 — Phase 3 parity reuse deep-gate update + SR tests

Context:
- Phase 3 is near-complete but parity reuse integration still targets 1A. HashGate laws for 2A/2B/3B/5A/5B/6A are now aligned in the interface pack and SR verifier.
- We need to harden Phase 3 by reusing **deeper gates** to prove SR can verify real engine artifacts beyond 1A.

Decision:
- Update the parity reuse integration test to target a deeper gate (prefer 5B or 6A if their `_passed.flag` exists for the local_full_run-5 manifest). Keep the test deterministic and pinned to local_full_run-5 outputs.
- Run the SR test suite (`tests/services/scenario_runner`) after updating the test.

Implementation plan:
1) Inspect `tests/services/scenario_runner/test_gate_verification_integration.py` to locate the parity reuse test.
2) Switch the selected output(s) to one authorized by a deeper gate (priority: 6A → 5B → 5A). Use only outputs that are present in local_full_run-5.
3) Ensure the test still uses the same run_root + manifest_fingerprint and validates the gate receipts (PASS) and evidence bundle hash stability.
4) Run `pytest tests/services/scenario_runner -q` under the venv.
5) Log results and update Phase 3 status if all tests pass and the DoD is satisfied.

Validation plan:
- Full SR test subset run, with explicit output in logbook.

---

### Entry: 2026-01-24 16:45:51 — Parity reuse test now targets 6A

Change applied:
- Updated `tests/services/scenario_runner/test_gate_verification_integration.py` so the real-run parity reuse test targets `s5_validation_report_6A` (deep gate) instead of `sealed_inputs_1A`.
- Parameterized `_build_policy` so the 1A synthetic test still uses `sealed_inputs_1A`, while the parity test uses `s5_validation_report_6A`.

Reasoning:
- Phase 3 hashing alignment is now complete across 2A/2B/3B/5A/5B/6A, so the reuse test should exercise a deeper gate to prove real-world verification beyond 1A.

---

### Entry: 2026-01-24 16:46:30 — SR test suite run (Phase 3)

Test run:
- `python -m pytest tests/services/scenario_runner -q` (venv)

Results:
- 19 passed, 2 skipped

Notes:
- Skip reasons unchanged (local_full_run-5 gating when run root absent).
- Parity reuse now exercises 6A gate with real engine artifacts.

---

### Entry: 2026-01-24 16:59:35 — Phase 3 DoD gap: unknown gate_id handling

Problem:
- Phase 3 DoD expects unknown gate IDs to fail closed with explicit reason codes. Currently an unknown gate ID (e.g., in `read_requires_gates`) can surface as a raw KeyError from `GateMap.gate_entry` during verification.

Decision:
- Add explicit validation for gate IDs in plan compilation and verification steps. Unknown gate IDs should produce a deterministic FAIL with a clear reason code (e.g., `UNKNOWN_GATE_ID`).

Planned changes:
1) In `_compile_plan`, after assembling `required_gates`, validate each gate_id exists in `GateMap.gates`; if any missing, raise `RuntimeError` with a stable reason (so submit_run returns FAIL with reason code).
2) In evidence collection, if a gate_id is missing, return `EvidenceBundle` with `FAIL` and `reason="UNKNOWN_GATE_ID"`.
3) Add/extend a unit test to cover this path (use a test catalogue with `read_requires_gates` pointing at a missing gate).

Validation:
- Run SR test suite after adding the test.

---

### Entry: 2026-01-24 17:03:17 — Unknown gate_id fail‑closed handling (Phase 3 DoD)

What changed:
- Added explicit UNKNOWN gate/output handling at plan compile time and during evidence verification.
  - `_compile_plan` now raises `UNKNOWN_OUTPUT_ID:<id>` for missing outputs.
  - Missing gate IDs in the required gate set raise `UNKNOWN_GATE_ID:<ids>`.
  - `submit_run` now catches these plan errors, commits a terminal FAIL with reason `UNKNOWN_GATE_ID` or `UNKNOWN_OUTPUT_ID`, and returns a stable "Run failed." response.
  - `_collect_evidence` also fails closed with `UNKNOWN_GATE_ID` if a gate_id is missing at verification time (defensive).
- Added a unit test that injects `read_requires_gates: [gate.unknown.missing]` and asserts `UNKNOWN_GATE_ID` on failure.

Files touched:
- `src/fraud_detection/scenario_runner/runner.py`
- `src/fraud_detection/scenario_runner/evidence.py`
- `tests/services/scenario_runner/test_instance_proof_bridge.py`

Tests:
- `python -m pytest tests/services/scenario_runner -q` (venv) → 20 passed, 2 skipped.

---

### Entry: 2026-01-24 17:06:22 — Phase 3 complete (evidence + gate verification)

Decision:
- Phase 3 is now **COMPLETE**. All DoD items are satisfied:
  - Required gate closure derived from interface pack and enforced (including explicit UNKNOWN gate/output fail‑closed handling).
  - Gate receipts schema‑validated; instance receipts emitted with drift protection.
  - Locator integrity + deterministic content digests implemented.
  - Evidence classification uses stable COMPLETE/WAITING/FAIL/CONFLICT reasons + deterministic bundle hash.
  - Tests cover deep gate verification (2A/2B/3B/5A/5B/6A), parity reuse on 6A, negative gate evidence, and instance receipt drift.

Next phase entry:
- Proceed to Phase 4 — Engine invocation integration (real job runner adapter, attempt lifecycle, retries, idempotency).

---

### Entry: 2026-01-24 17:10:30 — Phase 4 planning (engine invocation integration)

Problem framing:
- Phase 4 must turn SR’s “invoke engine” path from a placeholder into a real, production‑grade job runner adapter with attempt lifecycle, retries, idempotency, and explicit failure posture.
- The engine must remain a black box; SR can only interact via defined contracts + run root and must not assume internal engine behavior beyond outputs and run receipts.

Inputs / authorities:
- SR contracts: `docs/model_spec/platform/contracts/scenario_runner/*`
- Interface pack: `docs/model_spec/data-engine/interface_pack/` (outputs catalogue + gates map + engine contract schemas)
- Existing SR code: `src/fraud_detection/scenario_runner/runner.py`, `engine.py`, `models.py`, `ledger.py`, `authority_store.py`

Key decisions to make (and how I’ll decide):
1) **Invocation mode(s)**
   - Options: (a) local subprocess CLI, (b) Docker container (local parity), (c) remote job runner (ECS/Batch) adapter.
   - Decision criteria: deterministic run root placement, observable attempt lifecycle, ability to pass pins and capture run receipts.
   - Likely: implement a local subprocess adapter first (to keep dev unblocked), and define a stable interface for a future ECS adapter without wiring AWS creds in code.

2) **Attempt lifecycle & idempotency**
   - Define attempt record shape: attempt_id, started_at, ended_at, outcome, reason_code, engine_run_root, run_receipt_ref.
   - Decision: attempt_id derived as hash of (run_id, attempt_n, invoker_id) to make retries explicit and safe.
   - Enforce “no PASS‑no read”: evidence collection only after attempt reports success and run receipt is present/valid.

3) **Failure semantics**
   - Distinguish between engine hard failures (non‑zero exit, missing run receipt, invalid receipt) and evidence failures.
   - Decision: commit terminal FAIL with reason codes like `ENGINE_EXIT_NONZERO`, `ENGINE_RECEIPT_MISSING`, `ENGINE_RECEIPT_INVALID`.

4) **Run root ownership**
   - SR must not write into engine outputs other than its own receipts/logging; engine owns the run root content.
   - Decision: SR only passes `engine_run_root` + pins; engine writes; SR later verifies receipts and gates.

Plan (stepwise, before coding):
1) **Build plan update**
   - Expand Phase 4 in `scenario_runner.build_plan.md` into sections with DoD.
2) **Define attempt model + receipt envelope**
   - Add attempt record schema if missing (SR contracts) and wire into ledger append‑only record.
3) **Engine invoker interface hardening**
   - Ensure `engine.py` exposes a clean adapter interface (invoke, poll, collect logs, return outcome + receipt ref).
   - Implement local subprocess adapter with deterministic run root and captured stdout/stderr to SR logs.
4) **Runner wiring**
   - Update `_invoke_engine` to create attempt record, call invoker, persist attempt outcome, and perform post‑attempt receipt checks.
5) **Failure reason codes + tests**
   - Add tests for: non‑zero exit, missing receipt, invalid receipt, and retry limit enforcement.
6) **Observability**
   - Emit narrative logs around attempt start/finish with attempt_id, duration, and reason.

Security posture:
- No credentials in code or plans. Local adapter uses local paths only. Remote adapter (future) requires explicit injected credentials or role assumption (documented, not embedded).

Validation plan:
- Unit tests for attempt record creation + outcomes.
- Integration test that runs a local “engine stub” (or the existing LocalEngineInvoker) and confirms receipts are validated before evidence collection.

---

### Entry: 2026-01-24 17:22:09 — Phase 4 implementation begins (exhaustive reasoning)

Intent:
- Proceed with Phase 4 implementation in a fully documented, step‑by‑step fashion (reasoning recorded as it happens).

Immediate next actions (before code edits):
1) Inspect current invoker code (`src/fraud_detection/scenario_runner/engine.py`) and `_invoke_engine` in `runner.py` to understand existing contract and gaps.
2) Inventory current ledger record shapes for attempts (if any) and determine whether a new attempt schema is needed in SR contracts.
3) Draft a minimal, explicit invoker result envelope and decide where it is persisted.

Rationale:
- We must not touch engine internals. The invoker interface is the boundary that gives SR deterministic control and observability over attempts.
- Attempt lifecycle must be append‑only and idempotent to align with platform doctrine.

---

### Entry: 2026-01-24 17:26:13 — Phase 4 decisions (attempt lifecycle + receipt gating)

Observations from code:
- `EngineInvoker.invoke` currently returns a minimal `EngineAttemptResult` and LocalEngineInvoker always returns SUCCEEDED when engine_root is present.
- `_invoke_engine` always uses attempt_no=1 and does not validate run receipts; no attempt records exist besides a single finish event.
- `run_record` schema allows arbitrary details; there is no explicit attempt payload schema.

Decisions (with rationale):
1) **Attempt counting via run_record (no new DB tables).**
   - Implement a lightweight `Ledger.read_record_events()` to parse the run_record JSONL and count prior attempt events.
   - This avoids touching authority store schemas and keeps attempt logic append‑only.
   - We will count events of kind `ENGINE_ATTEMPT_FINISHED` to derive `attempt_no`.

2) **Add explicit attempt payload schema in SR contracts.**
   - New schema file `engine_attempt.schema.yaml` under SR contracts.
   - Validate attempt payload before appending to run_record to make attempts auditable and structured.

3) **Engine invocation contract validation.**
   - Validate the invocation payload against `engine_invocation.schema.yaml` before calling the invoker.
   - Add optional `engine_run_root` to the invocation schema (currently used by SR but not allowed by schema).

4) **Run receipt validation before evidence collection.**
   - Add `run_receipt.schema.yaml` under interface pack contracts and validate `run_receipt.json` after a SUCCEEDED attempt.
   - Enforce pins: `run_id`, `manifest_fingerprint`, `parameter_hash`, `seed` must match the run intent.
   - Failure reasons: `ENGINE_RECEIPT_MISSING`, `ENGINE_RECEIPT_INVALID`, `ENGINE_RECEIPT_MISMATCH`.

5) **Attempt limit enforcement.**
   - Compute `attempt_no = prior_attempts + 1`; if `attempt_no > plan.attempt_limit`, return FAILED with `ATTEMPT_LIMIT_EXCEEDED` and append an attempt event without invoking the engine.

6) **Event taxonomy.**
   - Keep `ENGINE_ATTEMPT_LAUNCH_REQUESTED` but enrich details; append `ENGINE_ATTEMPT_FINISHED` with full attempt payload (validated).

Next steps (implementation order):
1) Add schemas: `engine_attempt.schema.yaml` (SR contracts) and `run_receipt.schema.yaml` (interface pack).
2) Update `engine_invocation.schema.yaml` to allow `engine_run_root`.
3) Add `Ledger.read_record_events` helper for attempt counting.
4) Update `_invoke_engine` to validate invocation, enforce attempt_limit, validate run_receipt, and append attempt payload events.
5) Add tests for missing/invalid run_receipt and attempt_limit handling.

---

### Entry: 2026-01-24 17:32:21 — Phase 4 implementation: invoker + attempt lifecycle + receipt gating

Implemented changes (with reasoning):
- **Invocation validation**: `_invoke_engine` now validates the invocation payload against `engine_invocation.schema.yaml` before calling the invoker. This prevents SR from sending malformed or schema‑drifting requests to the engine.
- **Scenario binding shape fix**: only `scenario_id` OR `scenario_set` is populated (never both), aligning with the invocation schema’s `oneOf` contract.
- **Attempt counting without new DB tables**: introduced `Ledger.read_record_events()` to parse run_record JSONL and count prior `ENGINE_ATTEMPT_FINISHED` events. This keeps attempt tracking append‑only and avoids changing authority DB schemas.
- **Attempt limit enforcement**: if `attempt_no > plan.attempt_limit`, SR writes a finished attempt event with `ATTEMPT_LIMIT_EXCEEDED` and fails closed without invoking the engine.
- **Attempt payload schema**: added `engine_attempt.schema.yaml` under SR contracts and validate attempt payloads before they are written to run_record for auditability.
- **Run receipt gating**: after a SUCCEEDED attempt, SR loads `run_receipt.json`, validates it against new `run_receipt.schema.yaml`, and enforces pin equality (`run_id`, `manifest_fingerprint`, `parameter_hash`, `seed`). Fail‑closed reasons: `ENGINE_RECEIPT_MISSING`, `ENGINE_RECEIPT_INVALID`, `ENGINE_RECEIPT_MISMATCH`.
- **Attempt event details**: `ENGINE_ATTEMPT_LAUNCH_REQUESTED` now includes attempt_id/attempt_no/invoker; `ENGINE_ATTEMPT_FINISHED` carries the validated attempt payload (start/end/duration, invocation, outcome, receipt ref).

Contract updates:
- Added `docs/model_spec/platform/contracts/scenario_runner/engine_attempt.schema.yaml`.
- Added `docs/model_spec/data-engine/interface_pack/contracts/run_receipt.schema.yaml`.
- Updated `docs/model_spec/data-engine/interface_pack/contracts/engine_invocation.schema.yaml` to allow `engine_run_root`.

Tests added:
- `tests/services/scenario_runner/test_engine_invocation.py` covering:
  - Missing receipt → `ENGINE_RECEIPT_MISSING`
  - Invalid receipt → `ENGINE_RECEIPT_INVALID`
  - Mismatched receipt → `ENGINE_RECEIPT_MISMATCH`
  - Attempt limit exceeded → `ATTEMPT_LIMIT_EXCEEDED`

Test results:
- `python -m pytest tests/services/scenario_runner -q` (venv) → **24 passed, 2 skipped**

Notes / known limits:
- Attempt counting is based on `ENGINE_ATTEMPT_FINISHED` events in run_record; this is sufficient for v0 but can be replaced by a dedicated attempt index if/when record size becomes a concern.

---

### Entry: 2026-01-24 17:38:41 — Phase 4.1: implement real local subprocess invoker

Intent:
- Replace the stubbed LocalEngineInvoker with a real local subprocess adapter that runs the engine CLI, captures stdout/stderr, and maps exit code to attempt outcome.

Key constraints:
- Engine is a black box: invocation must use the engine’s published CLI/contract surface only.
- No credentials or secrets embedded in code or docs.

Plan (stepwise):
1) Locate engine CLI entrypoints or scripts (likely under `packages/engine/` or `scripts/`) and determine the correct invocation command for a full run using only the invocation payload.
2) Define a local adapter interface: it should build the CLI command, set environment variables if needed (without embedding secrets), and capture stdout/stderr to SR artifact store (logs_ref).
3) Implement subprocess execution in `LocalEngineInvoker` with timeout handling and clear reason codes for non‑zero exits.
4) Add tests using a stub command (e.g., a small Python script) to simulate success and failure without depending on engine internals.
5) Update impl_actual and logbook with all decisions.

---

### Entry: 2026-01-24 17:41:04 — Subprocess invoker design decisions

Decision trail (live):
- **Command source**: add optional `engine_command` to WiringProfile so SR can run a user‑supplied CLI without hardcoding engine internals. This keeps engine black‑box and avoids embedding a specific segment/state runner.
- **Command template**: allow placeholder substitution in command tokens using invocation fields (`manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_id`, `engine_run_root`). This keeps SR generic and lets the user point to any engine wrapper.
- **Invocation payload transport**: pass invocation JSON via an env var (`SR_ENGINE_INVOCATION_JSON`) for local subprocess runs; also expose `{invocation_json}` placeholder for token substitution. This avoids writing into engine run root while still allowing a wrapper script to read the payload.
- **stdout/stderr capture**: capture subprocess output in the invoker and persist into SR object store at `fraud-platform/sr/engine_attempt_logs/run_id=.../attempt_no=.../stdout.log|stderr.log`. Store refs in the attempt record (`logs_ref`).
- **Exit code mapping**: non‑zero exit → `ENGINE_EXIT_NONZERO`; timeout → `ENGINE_TIMEOUT`; missing command → `ENGINE_COMMAND_MISSING`.

Why this path:
- Keeps SR generic and black‑box compliant, avoids coupling to engine CLI internals.
- Provides audit‑ready logs without polluting engine run roots.

Planned code touchpoints:
- `src/fraud_detection/scenario_runner/config.py` (add wiring fields)
- `src/fraud_detection/scenario_runner/engine.py` (LocalSubprocessInvoker + stdout/stderr capture)
- `src/fraud_detection/scenario_runner/runner.py` (store logs + include logs_ref in attempt payload)
- `docs/model_spec/platform/contracts/scenario_runner/engine_attempt.schema.yaml` (add logs_ref)
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md` (note completion once done)
- Tests for subprocess invoker (stub command) + verify logs_ref persisted.

---

### Entry: 2026-01-24 17:45:27 — Local subprocess invoker implemented

Implementation summary (with details):
- Added **LocalSubprocessInvoker** in `src/fraud_detection/scenario_runner/engine.py`.
  - Accepts a `command` list, optional `cwd`, and optional timeout.
  - Performs placeholder substitution in command tokens using invocation fields.
  - Exposes invocation JSON via `SR_ENGINE_INVOCATION_JSON` and `SR_ENGINE_RUN_ROOT` env vars.
  - Captures stdout/stderr and maps exit codes to `ENGINE_EXIT_NONZERO`, missing command to `ENGINE_COMMAND_MISSING`, and timeouts to `ENGINE_TIMEOUT`.
- Extended `EngineAttemptResult` to carry stdout/stderr.
- Added log persistence in `_invoke_engine`:
  - Writes stdout/stderr to SR object store under `fraud-platform/sr/engine_attempt_logs/run_id=.../attempt_no=.../`.
  - Stores log refs in attempt payload (`logs_ref`).
- Added wiring fields for `engine_command`, `engine_command_cwd`, `engine_command_timeout_seconds` and wired CLI/service to use LocalSubprocessInvoker when `engine_command` is present.
- Updated `engine_attempt.schema.yaml` to include `logs_ref`.

Tests added:
- `tests/services/scenario_runner/test_engine_subprocess_invoker.py`:
  - Ensures stdout/stderr capture works for a stub engine subprocess.
  - Ensures SR persists attempt logs and refs them in run_record.

Test results:
- `python -m pytest tests/services/scenario_runner/test_engine_subprocess_invoker.py -q` → 2 passed.

Notes:
- LocalEngineInvoker stub remains for tests and for wiring profiles without `engine_command`.
- SR remains black‑box compliant: invocation contract is passed to the subprocess; no engine internals are assumed.

---

### Entry: 2026-01-24 17:46:29 — SR test suite after subprocess invoker

Test run:
- `python -m pytest tests/services/scenario_runner -q` (venv)

Result:
- 26 passed, 2 skipped
