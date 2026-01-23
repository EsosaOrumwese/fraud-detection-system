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

