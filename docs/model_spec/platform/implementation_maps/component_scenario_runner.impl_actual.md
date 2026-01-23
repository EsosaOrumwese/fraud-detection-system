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
- Unit tests for run_id/attempt_id determinism and scenario_set → scenario_id derivation.
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
