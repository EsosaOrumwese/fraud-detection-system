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
3) **Control bus + prefix naming**: Use control topic name fp.bus.control.v1 and object-store prefix family fraud-platform/<platform_run_id>/sr/ (or equivalent bucket/prefix pair). Reason: avoid naming drift, keep join semantics consistent. (Names are defaults, not binding to a vendor.)

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
**Base prefix:** fraud-platform/<platform_run_id>/sr/
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
- Quarantine storage location for SR evidence conflicts (likely fraud-platform/<platform_run_id>/sr/quarantine/).

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

---

## Entry: 2026-01-25 09:00:30 — Plan to trigger READY run for IG smoke test (reuse-only, engine blackbox safe)

### Problem / goal
The IG ops‑rebuild smoke test requires an SR READY run with a valid `run_facts_view` under the SR artifacts root. Current SR artifacts in `temp/artefacts/fraud-platform/sr` show QUARANTINED with no facts view. We need a READY run that reuses existing engine artifacts (engine remains a blackbox) so the IG smoke test can read a real join surface.

### Constraints / invariants honored
- **Engine remains a blackbox.** No engine code changes or re‑execution; SR will only read existing engine outputs and gate bundles under `runs/`.
- **No-PASS-no-read.** SR must only publish READY if required gates pass under the interface pack gate map.
- **Idempotency safe.** A new run_equivalence_key is used to avoid collision with any prior SR runs.
- **Secrets hygiene.** No credentials or secrets are written to impl_actual; only public artifact paths and fingerprints already in repo.

### Inputs / authorities consulted
- Engine run receipt at `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/run_receipt.json` for:
  - manifest_fingerprint: `c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`
  - parameter_hash: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
  - seed: `42`
- Scenario id observed under engine outputs: `scenario_id=baseline_v1` within `runs/local_full_run-5/.../arrival_events/...`.
- SR wiring profile: `config/platform/sr/wiring_local.yaml` (object_store_root=`artefacts`, control bus file, interface pack paths).
- SR policy: `config/platform/sr/policy_v0.yaml` (traffic outputs: arrival_events_5B, s2_flow_anchor_baseline_6B, s3_flow_anchor_with_fraud_6B; reuse_policy=ALLOW).

### Decision trail (why this approach)
1) **Reuse path vs engine invocation**
   - SR strategy AUTO first attempts reuse when reuse_policy=ALLOW.
   - Reuse avoids the engine invocation path that would enforce run_receipt run_id equality (SR run_id is deterministic from equivalence key and won’t match engine run_id). This keeps the engine blackbox while still verifying gates and outputs.
2) **Artifact root selection**
   - Use existing wiring profile to write SR artifacts under `artefacts/fraud-platform/sr` (already in repo and referenced by IG smoke test search order).
   - Avoid introducing new wiring variants for this run; keep configuration minimal and explicit.
3) **Scenario binding**
   - Use `scenario_id=baseline_v1` to match actual engine output partitions, ensuring locators resolve.
4) **Run window**
   - Provide a valid, timezone‑aware window (ISO8601 with `+00:00`) as required by schema; no functional coupling to engine output timestamps.

### Execution plan (pre‑run, explicit)
1) Submit SR run via CLI using reuse‑only path by providing engine_run_root and using policy reuse (AUTO).
2) Confirm SR output artifacts:
   - `artefacts/fraud-platform/<platform_run_id>/sr/run_status/{run_id}.json` state is READY.
   - `artefacts/fraud-platform/<platform_run_id>/sr/run_facts_view/{run_id}.json` exists with locators + gate receipts.
3) Run IG smoke test: `tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q` and confirm it reads the SR artifacts.
4) Log results in logbook + append follow‑up entry here with outcomes and any deviations.

### Planned CLI invocation (values to reuse)
```
.\.venv\Scripts\python.exe -m fraud_detection.scenario_runner.cli `
  --wiring config/platform/sr/wiring_local.yaml `
  --policy config/platform/sr/policy_v0.yaml `
  run `
  --run-equivalence-key sr_local_full_run_5_baseline_v1_2026-01-25 `
  --manifest-fingerprint c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8 `
  --parameter-hash 56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7 `
  --seed 42 `
  --scenario-id baseline_v1 `
  --window-start 2026-01-01T00:00:00+00:00 `
  --window-end 2026-01-02T00:00:00+00:00 `
  --engine-run-root runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92
```

---

## Entry: 2026-01-25 09:02:40 — RUN produced WAITING: arrival_events_5B path_template newline bug (fix in SR catalogue loader)

### What happened (observed)
Executed the planned SR CLI run and SR returned `WAITING_EVIDENCE` with `missing=['arrival_events_5B']`. This is incorrect: the arrival_events parquet files exist in the engine run root under:
`runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer2/5B/arrival_events/seed=42/manifest_fingerprint=.../scenario_id=baseline_v1/part-*.parquet`.

### Root cause analysis (decision trail)
1) Verified the arrival_events files exist at the expected path (seed=42, manifest_fingerprint=..., scenario_id=baseline_v1).
2) Inspected the interface pack catalogue entry for `arrival_events_5B` and printed `repr(path_template)`.
3) Found a trailing newline:  
   `data/layer2/5B/arrival_events/.../part-*.parquet\n`  
   This newline becomes part of the rendered path, so globbing never matches the real files. Result: SR treats `arrival_events_5B` as missing and moves to WAITING.

### Decision
Harden SR’s catalogue loader to normalize `path_template` by stripping leading/trailing whitespace when reading the interface pack. This keeps the engine blackbox intact, avoids mutating engine outputs, and makes SR tolerant of benign formatting artifacts in YAML (e.g., trailing newline introduced by the writer).

### Implementation steps (pre‑code)
1) Update `src/fraud_detection/scenario_runner/catalogue.py` to apply `.strip()` to `entry["path_template"]`.
2) Re‑run SR CLI with a new `run_equivalence_key` to avoid idempotent collision with the WAITING run.
3) Verify READY status and a `run_facts_view` under `artefacts/fraud-platform/<platform_run_id>/sr/`.
4) Re‑run IG smoke test to confirm it can rebuild ops index from the SR facts view.
5) Log results and update this entry with outcomes.

---

## Entry: 2026-01-25 09:05:50 — Fix applied; READY achieved; IG smoke test passes

### Changes applied
- Hardened SR catalogue loader to strip whitespace from `path_template` on load:
  - `src/fraud_detection/scenario_runner/catalogue.py` now uses `str(...).strip()` for `path_template`.
- Added regression test to lock this behavior:
  - `tests/services/scenario_runner/test_catalogue.py` verifies trailing newline is removed.

### SR run (reuse-only) results
- New run_equivalence_key: `sr_local_full_run_5_baseline_v1_2026-01-25b`
- Resulting run_id: `870056d6aaa95c99e1d770a484469563`
- Evidence reuse COMPLETE; READY committed.
- Artifacts written under:
  - `artefacts/fraud-platform/<platform_run_id>/sr/run_status/870056d6aaa95c99e1d770a484469563.json` (state READY)
  - `artefacts/fraud-platform/<platform_run_id>/sr/run_facts_view/870056d6aaa95c99e1d770a484469563.json`
  - `artefacts/fraud-platform/<platform_run_id>/sr/run_record/870056d6aaa95c99e1d770a484469563.jsonl`

### Validation (executed)
- SR unit test: `python -m pytest tests/services/scenario_runner/test_catalogue.py -q` → 1 passed.
- IG smoke test: `python -m pytest tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q` → 1 passed.

### Notes
- The earlier WAITING run (run_id=4d0c3c64c3e24c4f3091179259d19004) remains in SR artifacts for audit history; no mutation performed.

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
   - Default local DSN under `artefacts/fraud-platform/<platform_run_id>/sr/index/` if not provided.

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
- Added `authority_store_dsn` to SR wiring; local wiring uses SQLite under `artefacts/fraud-platform/<platform_run_id>/sr/index/`.

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
  `fraud-platform/<platform_run_id>/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`
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
  `fraud-platform/<platform_run_id>/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`
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
- **stdout/stderr capture**: capture subprocess output in the invoker and persist into SR object store at `fraud-platform/<platform_run_id>/sr/engine_attempt_logs/run_id=.../attempt_no=.../stdout.log|stderr.log`. Store refs in the attempt record (`logs_ref`).
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
  - Writes stdout/stderr to SR object store under `fraud-platform/<platform_run_id>/sr/engine_attempt_logs/run_id=.../attempt_no=.../`.
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

---

### Entry: 2026-01-24 17:55:42 — Phase 4 hardening fixes (invocation + command validation)

Problem:
- Phase 4 has three small hardening gaps: (1) invocation schema errors are not trapped; (2) empty engine_command can crash LocalSubprocessInvoker; (3) unresolved placeholders can lead to confusing CLI invocations.

Decision:
- Add explicit error handling for invocation validation and command definition.
- Enforce placeholder completeness (fail closed when unresolved tokens are detected).

Planned changes:
1) In `_invoke_engine`, catch invocation schema validation errors and fail with `ENGINE_INVOCATION_INVALID`.
2) In `LocalSubprocessInvoker`, validate command list is non‑empty; if empty, return `ENGINE_COMMAND_MISSING`.
3) In `LocalSubprocessInvoker`, detect unresolved `{...}` placeholders after substitution and fail with `ENGINE_COMMAND_TEMPLATE_UNRESOLVED` (record token list in stderr for audit).
4) Add/extend tests to cover these cases.

Validation:
- Re‑run SR tests after updates.

## Entry: 2026-01-24 18:02:22 — Phase 4 hardening fixes (implementation plan)

I’m fixing the three Phase 4 hardening gaps identified earlier. I’m writing this **before** any new edits so the decision trail is explicit.

### Problem statement (the three findings)
1) Invocation schema validation failures were not trapped at the SR boundary, so a schema error could bubble as an exception instead of a deterministic attempt outcome.
2) LocalSubprocessInvoker could be configured with an empty `engine_command`, leading to ambiguous failures.
3) Placeholder tokens in `engine_command` could remain unresolved, producing confusing CLI calls.

### Decision (what to do and why)
- Add explicit, fail‑closed handling for each gap with stable reason codes so the run ledger is auditable:
  - `ENGINE_INVOCATION_INVALID` when the invocation payload violates the engine invocation contract.
  - `ENGINE_COMMAND_MISSING` when the configured command list is empty or missing.
  - `ENGINE_COMMAND_TEMPLATE_UNRESOLVED` when a token still contains `{...}` after substitution.
- Ensure the attempt lifecycle still appends a finished attempt event even for these failures. This keeps run_record append‑only and avoids silent drops.

### Implementation plan (stepwise)
1) Update `LocalSubprocessInvoker.invoke` to guard empty command and unresolved placeholders; return FAILED with the above reason codes and a short stderr message for operator clarity.
2) Update `_invoke_engine` to catch invocation schema validation errors and convert them into a finished attempt with `ENGINE_INVOCATION_INVALID`.
3) Extend tests to cover all three cases; ensure test helpers import the needed symbols (avoid NameError from missing RunHandle import).
4) Re-run the SR test suite and log results.

### Invariants to preserve
- No‑PASS‑no‑read stays intact: invocation failures must not proceed to evidence collection.
- Every engine attempt request results in an append‑only `ENGINE_ATTEMPT_FINISHED` event with a stable reason.
- No secrets or credentials in code or docs.

---

## Entry: 2026-01-24 18:06:12 — Phase 4 hardening fixes implemented (invocation + command validation)

I implemented the three hardening fixes and validated them with tests.

### What changed (concrete)
- **Invocation schema failures are now deterministic**: `_invoke_engine` traps schema validation errors and returns a FAILED attempt with `ENGINE_INVOCATION_INVALID`, while still appending an `ENGINE_ATTEMPT_FINISHED` event.
- **Command guards in LocalSubprocessInvoker**:
  - Empty `engine_command` now returns FAILED with `ENGINE_COMMAND_MISSING`.
  - Unresolved `{...}` placeholders after substitution return FAILED with `ENGINE_COMMAND_TEMPLATE_UNRESOLVED` and a short stderr hint listing the unresolved tokens.
- **Tests updated** to cover the new failure paths and to ensure the attempt ledger captures the reason codes. (Fixed missing `RunHandle` import in the invocation test helper.)

### Why this satisfies the DoD gap
- Fail‑closed behavior is explicit and auditable with stable reason codes.
- Attempt lifecycle remains append‑only (even in validation failures).
- Operators get a clear stderr hint without leaking secrets.

### Validation
- `python -m pytest tests/services/scenario_runner -q` via venv → **29 passed, 2 skipped**.

---

## Entry: 2026-01-24 18:13:45 — Phase 4 marked COMPLETE

User requested Phase 4 sign‑off. I verified that all Section 4.1–4.5 DoD items are implemented and that the SR test suite passes under the venv.

### Completion evidence
- Local subprocess invoker in place with stdout/stderr capture and explicit failure codes.
- Attempt lifecycle + schema enforced; attempt_limit and receipt gating wired.
- Invocation validation + command guards fail closed with deterministic reason codes.
- SR test suite: 29 passed, 2 skipped (venv).

Decision:
- Mark Phase 4 as COMPLETE in the build plan.

---

## Entry: 2026-01-24 18:19:22 — Phase 5 planning (control bus + re‑emit operations)

I’m starting Phase 5 planning now. This is a live reasoning note, not a retrospective summary.

### Problem framing (what Phase 5 must solve)
- Phase 4 made engine invocation real, but SR still publishes READY to a file bus only. We need **production‑real control bus semantics** with idempotent publishing, and an **ops‑safe re‑emit path (N7)** that replays control facts without recomputation or mutation.
- This phase is about **control‑plane delivery**, not changing truth. The truth surfaces remain `sr/*` artifacts; the bus is a trigger.

### Authorities / inputs I’m grounding on
- Root AGENTS.md (pins: no‑PASS‑no‑read, by‑ref truth, idempotency, fail‑closed).
- SR design‑authority, especially N7 (rehydration / re‑emit) and the control‑bus join semantics.
- Platform blueprint notes (control bus is the entrypoint trigger; downstream starts at SR READY).
- Existing SR contracts: `run_ready_signal.schema.yaml` + run_record/run_status/run_facts_view schemas.
- Locked platform stack decision (control bus = Amazon Kinesis; local can remain file bus for parity).

### What I observe in current code
- `FileControlBus` is used in `ScenarioRunner` for READY publish; it’s a local artifact‑based bus.
- READY publish uses `bundle_hash` (or plan_hash) as a message_id, which is already aligned with idempotency intent.
- No explicit re‑emit capability exists yet; no re‑emit request schema or events in run_record.

### Decisions to make (and my reasoning)
1) **Control bus abstraction**
   - Keep `ControlBus` as an interface with at least `publish(topic, payload, message_id, attributes)`.
   - Add a **KinesisControlBus** adapter for production with partition key = `run_id` and dedupe key = message_id.
   - Keep `FileControlBus` for local/dev parity so unit tests stay deterministic.

2) **READY publish idempotency key**
   - Use a **stable key derived from `run_id + bundle_hash`**. The facts view already carries `bundle_hash`, which is stable for a run once READY.
   - If a READY payload lacks bundle_hash (should not in COMPLETE), fall back to a deterministic hash of the facts_view payload. This avoids “random publish keys.”

3) **Re‑emit contract and flow (N7)**
   - Re‑emit must be **read‑only against SR truth**, never recompute, never modify status.
   - Re‑emit must be idempotent and auditable: create run_record events for request + publish.
   - Use **ops micro‑lease** to prevent stampede; reject with BUSY if lease not acquired.
   - Re‑emit modes: READY_ONLY, TERMINAL_ONLY, BOTH. If the run is READY, publish READY; if terminal, publish terminal. If state doesn’t match requested kind, fail with reason.

4) **Terminal control messages**
   - I will emit a terminal control fact only for re‑emit (not for normal flow), because the platform’s entrypoint is READY; terminal control facts are strictly an ops/audit recovery tool.
   - Terminal re‑emit includes status_ref + record_ref for downstream inspection; no facts_view ref required.

5) **Authorization + safety**
   - In local/dev, allow re‑emit without hard auth (but keep the hooks). In prod, require explicit authn/authz (Phase 7 will harden). For Phase 5, include a policy‑gate stub to keep the shape right.

### Alternatives considered (and why I’m not choosing them)
- **Push READY directly to EB**: rejected because SR must publish only to control bus; EB is owned by IG and is append/replay.
- **Compute new facts_view on re‑emit**: rejected; violates “read truth → publish trigger.”
- **Skip micro‑lease**: rejected; ops re‑emit is prone to duplicate floods in outage scenarios.

### Proposed design (concrete mechanics)
**A) Control bus adapters**
- Add `KinesisControlBus` (new file under `src/fraud_detection/scenario_runner/bus.py` or sibling).
- Wiring profile gains `control_bus_kind` (file|kinesis) + `control_bus_stream` (name only; no secrets).
- `ScenarioRunner` chooses adapter via wiring.

**B) READY publish flow (N6)**
- Keep the commit order: facts_view → run_status READY → publish READY.
- Publish payload must validate `run_ready_signal.schema.yaml` before send.
- Use deterministic `message_id` = `bundle_hash` (or derived hash of facts_view) for idempotency.

**C) Re‑emit flow (N7)**
- Implement a `ReemitRequest` model + schema (under SR contracts) with:
  - `run_id`, `reemit_kind`, `reason`, `requested_by`, `requested_at_utc`.
- Re‑emit handler steps:
  1) Acquire ops micro‑lease keyed by `(run_id, reemit_kind)`.
  2) Read `run_status` (must exist) and `run_facts_view` (if READY).
  3) Derive re‑emit idempotency keys:
     - READY key: `sha256("ready|" + run_id + "|" + bundle_hash_or_facts_view_hash)`.
     - TERMINAL key: `sha256("terminal|" + run_id + "|" + state + "|" + status_hash)`.
  4) Append `REEMIT_REQUESTED` to run_record.
  5) Publish READY and/or terminal control fact based on state + kind.
  6) Append `REEMIT_PUBLISHED` or `REEMIT_FAILED` to run_record (no run_status changes).

**D) Control‑fact payloads**
- READY re‑emit uses the same payload as standard READY (run_ready_signal).
- Terminal re‑emit payload includes: run_id, status_state, status_ref, record_ref, reason_code, and reemit_key. (Schema to be added under SR contracts so it’s auditable.)

### File path plan (expected touchpoints)
- `src/fraud_detection/scenario_runner/bus.py` (add Kinesis adapter + interface extensions)
- `src/fraud_detection/scenario_runner/config.py` (wiring fields for bus kind/stream)
- `src/fraud_detection/scenario_runner/runner.py` (READY publish idempotency key from bundle hash)
- `src/fraud_detection/scenario_runner/service.py` + `cli.py` (re‑emit endpoint/command)
- `docs/model_spec/platform/contracts/scenario_runner/` (new re‑emit request + terminal signal schemas)
- `docs/model_spec/platform/contracts/scenario_runner/README.md` (document re‑emit contract)
- Tests under `tests/services/scenario_runner/` (re‑emit + publish idempotency)

### Invariants to enforce
- Re‑emit never mutates run_status or facts_view.
- READY publish remains strictly after facts_view + status READY commit.
- Message idempotency is deterministic and stable across retries.
- No credentials or secrets appear in code or docs.

### Observability expectations (light, Phase 5‑scoped)
- Log re‑emit start/end with run_id, kind, result, reemit_key.
- Append run_record events for re‑emit actions; this is the audit trail.

### Validation plan
- Unit tests for re‑emit key derivation + READY publish key determinism.
- Integration test for re‑emit READY using file bus (assert control message stored and idempotent).
- Integration test for terminal re‑emit (FAILED/QUARANTINED) verifying payload and refs.
- Log test results in logbook.

---

## Entry: 2026-01-24 18:22:10 — Phase 5 implementation begins (control bus + re‑emit)

I’m moving from planning into implementation now. I will append decisions as I touch each file.

Immediate next actions (before code edits):
1) Extend wiring to select a control‑bus adapter (file vs Kinesis) without embedding credentials.
2) Define re‑emit contracts (request + terminal signal schemas) under SR contracts.
3) Implement re‑emit flow in ScenarioRunner with ops micro‑lease, idempotency keys, and run_record audit events.
4) Wire service + CLI entrypoints for re‑emit requests (keeping existing run submit intact).
5) Add tests for re‑emit (READY + terminal) and idempotency key derivation.

Guardrails:
- Re‑emit must be read‑only against truth (no run_status/facts_view mutations).
- Control‑bus failures must be recorded but never block truth commits.
- No secrets/credentials in code or docs.

---

## Entry: 2026-01-24 18:33:40 — Phase 5 implementation (control bus + re‑emit)

I implemented the first Phase 5 slice: control‑bus adapter selection, READY publish idempotency, and N7 re‑emit (ops replay). This entry documents the concrete decisions and mechanics as implemented.

### What I changed (by concern)

**1) Control bus abstraction + adapter selection**
- Added wiring fields so SR can select a control‑bus adapter by config (default `file`).
- Implemented a **KinesisControlBus** adapter that publishes an envelope to a configured stream using boto3, without embedding credentials (credentials are still external to code).
- FileControlBus now writes a JSON envelope that includes `message_id`, `topic`, `attributes`, and `payload`, so local tests can validate message metadata deterministically.

Files touched:
- `src/fraud_detection/scenario_runner/config.py` (wiring fields)
- `src/fraud_detection/scenario_runner/bus.py` (FileControlBus envelope + KinesisControlBus)
- `src/fraud_detection/scenario_runner/runner.py` (adapter selection)

**2) READY publish idempotency (N6)**
- READY publish key is now deterministic by design: `sha256("ready|" + run_id + "|" + bundle_hash_or_plan_hash)`.
- READY publish is wrapped in a failure‑tolerant guard so **publish failures don’t block truth commits**. Failures append a `READY_PUBLISH_FAILED` event; successes append `READY_PUBLISHED`.

Files touched:
- `src/fraud_detection/scenario_runner/runner.py`

**3) Re‑emit operations (N7)**
- Added SR‑level **ReemitRequest** and response models.
- Implemented `ScenarioRunner.reemit()` with **ops micro‑lease**, read‑only truth access, deterministic re‑emit keys, and run_record audit events.
- Re‑emit READY uses `run_ready_signal` schema and publishes with `sha256("ready|" + run_id + "|" + facts_view_hash)`.
- Re‑emit TERMINAL publishes a new terminal control fact validated by `run_terminal_signal.schema.yaml` using key `sha256("terminal|" + run_id + "|" + status_state + "|" + status_hash)`.
- No mutation of run_status/run_facts_view occurs during re‑emit (read‑only by design).

Files touched:
- `src/fraud_detection/scenario_runner/models.py` (ReemitKind/ReemitRequest/ReemitResponse)
- `src/fraud_detection/scenario_runner/runner.py` (re‑emit flow)
- `docs/model_spec/platform/contracts/scenario_runner/reemit_request.schema.yaml`
- `docs/model_spec/platform/contracts/scenario_runner/run_terminal_signal.schema.yaml`
- `docs/model_spec/platform/contracts/scenario_runner/README.md`
- `src/fraud_detection/scenario_runner/cli.py` + `service.py` (re‑emit endpoint + CLI subcommand)

### Why these decisions
- **Re‑emit includes terminal facts** so ops can replay a terminal outcome without recomputation.
- **File bus remains default for local** to keep tests deterministic; Kinesis adapter is present but not required for local parity.
- **Envelope format** is used so metadata like message_id and reemit key can be validated locally without touching Kinesis.
- **Failure posture**: publishing must never block truth commits or mutate run status.

### Invariants enforced
- Re‑emit is read‑only against SR truth; no run_status or facts_view mutation.
- Idempotency keys are deterministic and stable across retries.
- No secrets or credentials appear in code or docs.

### Tests executed
- `python -m pytest tests/services/scenario_runner/test_reemit.py -q` → 2 passed.
- `python -m pytest tests/services/scenario_runner -q` → 31 passed, 2 skipped.

---

## Entry: 2026-01-24 18:37:10 — Re‑emit failure handling correction

While validating Phase 5 re‑emit behavior, I noticed that a publish failure could be misreported as “not applicable” because the response logic didn’t distinguish **attempted‑but‑failed** from **not attempted**. I corrected this by tracking whether a READY/TERMINAL publish was attempted and only emitting `REEMIT_NOT_APPLICABLE` when no publish was attempted due to state/kind mismatch.

Outcome:
- Re‑emit now returns “Reemit failed.” when a publish was attempted and failed, while keeping the detailed `REEMIT_FAILED` audit event with the error.

Tests re‑run:
- `python -m pytest tests/services/scenario_runner/test_reemit.py -q` → 2 passed.
- `python -m pytest tests/services/scenario_runner -q` → 31 passed, 2 skipped.

---

## Entry: 2026-01-24 18:41:30 — Phase 5 add-ons (LocalStack Kinesis test + re‑emit failure coverage)

I’m extending Phase 5 implementation based on the user’s choice to do option 1 and 2: add a LocalStack Kinesis integration test gate and expand re‑emit failure coverage tests. This entry captures the decisions before edits.

### Option 1 — LocalStack Kinesis integration test (gated)
- **Decision**: add a Kinesis adapter integration test that only runs when explicit env vars are present (so default CI/local runs remain deterministic). If env vars are missing, the test will skip.
- **Why**: we want real adapter coverage without hard‑requiring LocalStack or AWS credentials in every developer setup.
- **Planned env gates** (names to be used in test):
  - `SR_KINESIS_ENDPOINT_URL` (LocalStack endpoint)
  - `SR_KINESIS_STREAM` (stream name)
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (dummy values are fine for LocalStack)
  - `AWS_DEFAULT_REGION` (or `SR_KINESIS_REGION`)
- **Test behavior**:
  - Ensure stream exists (create if missing).
  - Publish via `KinesisControlBus`.
  - Read back one record with boto3 and assert envelope fields (`message_id`, `payload.run_id`, `attributes.kind`).
- **No secrets**: no credentials in code/docs; only environment expectations.

### Option 2 — Re‑emit failure coverage
- **Decision**: add tests for mismatch and missing truth surfaces:
  - READY_ONLY requested but run is terminal → should return “not applicable” and append `REEMIT_FAILED` with reason `REEMIT_READY_ONLY_MISMATCH`.
  - TERMINAL_ONLY requested but run is READY → should return “not applicable” and append `REEMIT_FAILED` with reason `REEMIT_TERMINAL_ONLY_MISMATCH`.
  - READY re‑emit when facts_view missing → should return “Reemit failed.” and append `REEMIT_FAILED` with reason `FACTS_VIEW_MISSING`.
  - Re‑emit when run_id not found → should return “Run not found.” and not publish.
- **Why**: closes DoD gap in Section 5.4 by proving re‑emit failure posture + audit trail determinism.

### Files expected to touch
- `tests/services/scenario_runner/test_reemit.py` (add failure‑case assertions)
- `tests/services/scenario_runner/test_control_bus_kinesis.py` (new LocalStack‑gated test)
- `docs/model_spec/platform/implementation_maps/scenario_runner.impl_actual.md` + logbook (this entry + results)

### Validation
- Run `python -m pytest tests/services/scenario_runner/test_reemit.py -q`.
- Run `python -m pytest tests/services/scenario_runner/test_control_bus_kinesis.py -q` (will skip unless env provided).
- Run `python -m pytest tests/services/scenario_runner -q` after updates.

---

## Entry: 2026-01-24 18:45:55 — Concurrency regression (Windows read lock) + fix plan

During the full SR test suite run, `test_scenario_runner_concurrency.py::test_concurrent_duplicate_submissions` failed on Windows with a `PermissionError` while a follower thread tried to read `run_status`. This happened while the leader thread was updating the same file via atomic replace.

### Diagnosis
- The failure is a Windows file‑locking edge case during concurrent `read_status` vs `write_json` (atomic replace) on the local object store.
- This is local‑store specific (LocalObjectStore); S3 is not affected.

### Decision
- Add a **small retry loop** for LocalObjectStore `read_json`/`read_text` to tolerate transient `PermissionError` during atomic replace.
- Keep retry bounded (short sleep, few attempts) to avoid hiding real errors.

### Why this is acceptable
- This is a local/dev‑only store; the production store is S3 and doesn’t have this file‑lock behavior.
- The retry is fail‑closed after a few attempts, so we don’t silently mask persistent failures.

### Planned change
- Implement retry (e.g., 5 attempts with 25–50 ms backoff) in LocalObjectStore `read_json` and `read_text`.
- Re‑run the full SR test suite to confirm the concurrency test passes.

---

## Entry: 2026-01-24 18:49:30 — LocalObjectStore read retry (Windows lock fix)

I implemented a small retry loop for LocalObjectStore reads to avoid transient `PermissionError` during concurrent writes on Windows.

### What changed
- `LocalObjectStore.read_json` and `read_text` now call `_read_text_with_retry`.
- `_read_text_with_retry` retries up to 5 times with a short delay on `PermissionError` and `FileNotFoundError` (covers atomic replace and race conditions).

### Why this is safe
- This only affects the local filesystem store (dev/test). S3 behavior is unchanged.
- The retry window is small and bounded; persistent failures still surface.

### Tests
- `python -m pytest tests/services/scenario_runner -q` → 35 passed, 3 skipped.

---

## Entry: 2026-01-24 18:56:05 — Phase 5 docs + wiring for LocalStack Kinesis

I’m adding a sample `wiring_local_kinesis.yaml` and short docs so the LocalStack Kinesis integration test can be run end‑to‑end. This is a small, scoped addition to keep local parity reproducible.

### Decisions (before edits)
- Create a new wiring profile `config/platform/sr/wiring_local_kinesis.yaml` that:
  - keeps object store settings aligned with local parity (MinIO + Postgres),
  - selects `control_bus_kind: kinesis`,
  - uses LocalStack endpoint + stream name fields (no credentials in file).
- Add a short “how to run LocalStack Kinesis test” section to the SR service README with env‑only instructions.
- Keep `.env` credentials out of docs; use example env variable names only.

### Files to touch
- `config/platform/sr/wiring_local_kinesis.yaml` (new)
- `services/scenario_runner/README.md` (add test instructions)
- logbook + impl_actual entries

---

## Entry: 2026-01-24 19:00:45 — LocalStack wiring + docs added

I added a sample LocalStack Kinesis wiring profile and short end‑to‑end instructions for running the Kinesis adapter test.

### What changed
- Added `config/platform/sr/wiring_local_kinesis.yaml` (MinIO + Postgres + LocalStack Kinesis settings; no secrets).
- Updated `services/scenario_runner/README.md` with a concise LocalStack Kinesis test walkthrough and noted the new wiring profile.

### Why this helps
- Keeps local parity reproducible without entangling real AWS credentials.
- Provides an explicit, copy‑paste path to validate the Kinesis adapter end‑to‑end.

---

## Entry: 2026-01-24 19:04:50 — LocalStack env example file

User requested LocalStack envs. I will add a `.env.localstack.example` file with placeholder values (no real credentials) so LocalStack tests can be run without modifying `.env`. No secrets will be included.

---

## Entry: 2026-01-24 19:06:40 — README note for .env.localstack.example

Added a short note in the SR service README showing how to load `.env.localstack.example` for the LocalStack Kinesis test.

---

## Entry: 2026-01-24 19:12:10 — LocalStack helper script

User asked for a small helper to start/stop LocalStack from CLI. I will add `scripts/localstack.ps1` with start/stop/status/logs actions using docker.

---

## Entry: 2026-01-24 19:31:20 — LocalStack log narration (dev UX fix)

User asked to refine LocalStack logs so they’re readable and narrative. I can’t change LocalStack’s internal logging, but I can provide a **filtered, human‑readable log view** via our helper script.

Plan (before edits):
- Update `scripts/localstack.ps1` to support a `-Mode narrative` log view that filters LocalStack’s raw logs into a small set of high‑level status lines (ready, stream create, publish, read, shutdown) and surfaces only ERROR/WARN lines.
- Keep a `-Mode raw` option for full output.
- Add a short README note so users know how to use the narrative log view.

No secrets will be added or logged.

---

## Entry: 2026-01-24 19:33:40 — LocalStack narrative logs

I added a narrative log filter to `scripts/localstack.ps1` so LocalStack logs are readable and “noob‑friendly.” Raw logs are still available via `-Mode raw`.

### Behavior
- `.scripts\localstack.ps1 logs` now prints high‑level milestones (ready, stream create, publish, read) and only surfaces WARN/ERROR lines.
- `.scripts\localstack.ps1 logs -Mode raw` shows the full LocalStack output.

### Docs
- Added a brief note in the SR README pointing to the narrative log view.

---

## Entry: 2026-01-24 19:44:12 — LocalStack Kinesis test run (end‑to‑end)

Ran the LocalStack Kinesis integration test using the `.env.localstack.example` env loader and a running LocalStack container.

Command:
- `python -m pytest tests/services/scenario_runner/test_control_bus_kinesis.py -q`

Result:
- 1 passed
- 7 warnings (botocore deprecation: datetime.utcnow)

Note:
- This validates the KinesisControlBus envelope publish + round‑trip read using LocalStack.

---

## Entry: 2026-01-24 19:50:30 — Phase 5 marked COMPLETE

User requested Phase 5 sign‑off. I verified that all Phase 5 DoD items are met (control‑bus adapter, READY idempotency, re‑emit ops flow, failure posture, tests including LocalStack Kinesis). Marking Phase 5 as COMPLETE.

---

## Entry: 2026-01-24 19:54:50 — Phase 6 planning (Observability + governance)

I’m starting Phase 6 planning now. This is a live decision trail before any code changes.

### Problem framing (what Phase 6 must solve)
- SR already emits narrative logs, but we need **structured observability + governance facts** that are consistent across environments and do not affect truth outcomes.
- Phase 6 must deliver a **stable event taxonomy**, **metrics**, and **governance facts** (policy_rev, plan_hash, bundle_hash) that let operators and auditors explain what happened without reading raw logs.
- Observability must **never block truth commits** (drop, buffer, or degrade without affecting SR outcomes).

### Authorities / inputs
- Root AGENTS.md doctrine: provenance first‑class, no‑PASS‑no‑read, append‑only truth, fail‑closed.
- SR design‑authority N8 (Observability / Governance) requirements and event taxonomy.
- Existing SR contracts and run_record events.

### Current state (baseline)
- SR has narrative INFO logs in `runner.py` but no structured event emitter.
- run_record captures core events but not a normalized taxonomy or metrics.
- No metrics/traces or governance fact emission beyond run_facts_view/pins.

### Decisions to make (initial)
1) **Event taxonomy source of truth**
   - Define a stable SR obs taxonomy (enum list) in code and optionally in docs.
   - Use it to normalize SR internal events into structured obs events.

2) **Emitter strategy**
   - Emit structured events to:
     - console JSON (local),
     - optional OTLP/metrics (future),
     - governance facts appended to run_record (authoritative index).
   - Do **not** block SR commits; emit is best‑effort.

3) **Governance facts**
   - Emit explicit facts in run_record:
     - policy_rev used,
     - plan_hash,
     - bundle_hash (READY),
     - re‑emit keys.
   - These should be emitted at commit boundaries and re‑emit operations.

4) **Metrics scope**
   - Start with a minimal set (counts + durations) derived from normalized events.
   - Keep in‑process counters only (no external dependency in v0).

5) **Trace scaffolding**
   - Add correlation IDs to structured logs (run_id, attempt_id, policy_rev) so traces can be added later without changing the event schema.

### Planned Phase 6 sections (to add to build plan)
- 6.1 Event taxonomy + structured event model
- 6.2 Governance fact emission (policy_rev / plan_hash / bundle_hash)
- 6.3 Metrics counters + durations
- 6.4 Log/telemetry sinks with degrade posture
- 6.5 Tests + validation

### File touchpoints (expected)
- `src/fraud_detection/scenario_runner/obs.py` (new structured event model + emitter)
- `src/fraud_detection/scenario_runner/runner.py` (emit normalized events at key points)
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md` (Phase 6 sections + DoD)
- `docs/model_spec/platform/implementation_maps/scenario_runner.impl_actual.md` (live decision trail)
- Tests under `tests/services/scenario_runner/` for event emission and governance facts

### Invariants to preserve
- Observability never blocks truth commits.
- All structured events include pins (run_id, manifest_fingerprint, parameter_hash, seed, scenario_id).
- Governance facts are append‑only and never mutate run_status or facts_view.

---

## Entry: 2026-01-24 19:59:30 — Phase 6 implementation begins (obs scaffolding)

I’m starting Phase 6 implementation with the smallest safe unit: a structured event taxonomy + lightweight emitter that is best‑effort and non‑blocking. I will log each decision before code changes.

Immediate steps:
1) Add `obs.py` with `ObsEvent` model + enum taxonomy and a `ConsoleObsSink`.
2) Add a `ScenarioRunner._emit_obs(...)` helper that never raises.
3) Wire emit points for core milestones (ingress, plan commit, attempt start/finish, evidence result, READY publish, re‑emit publish).
4) Add tests to assert governance facts are appended and emission failures don’t block.

Guardrails:
- No changes to truth semantics or commit ordering.
- Emission failure must not impact run outcomes.
- All events carry pins + policy_rev where known.

---

## Entry: 2026-01-24 20:11:30 — Phase 6 scaffolding implemented (structured obs events)

I added a first-pass structured observability scaffold with a stable event model and best‑effort emission, and wired core SR milestones to emit events. This is Phase 6 Section 6.1 work.

### What changed
- Added `src/fraud_detection/scenario_runner/obs.py` with:
  - `ObsPhase`, `ObsOutcome`, `ObsSeverity` enums.
  - `ObsEvent` dataclass + `to_dict()`.
  - `ConsoleObsSink` for local JSON emission.
- Wired `ScenarioRunner` to emit structured events at:
  - run request received
  - run accepted / anchored
  - plan committed / plan failed
  - engine attempt start/finish
  - evidence result (reuse + post‑attempt)
  - READY committed / READY published / READY publish failed
  - re‑emit requested / busy / not found / failed / not applicable
- Emission is best‑effort and non‑blocking (`_emit_obs` swallows exceptions).

### Why this is safe
- No truth semantics changed; all emissions are side‑channel only.
- Emission failure cannot block SR commits.
- Every event includes pins and policy_rev where available.

### Tests
- `python -m pytest tests/services/scenario_runner -q` → 35 passed, 3 skipped.

---

## Entry: 2026-01-24 20:14:50 — Phase 6.2 governance facts (plan + decision)

I’m moving to Phase 6.2: explicit governance facts in the run_record. This entry captures the decision trail before edits.

### Goal
Emit explicit governance facts (policy_rev, plan_hash, bundle_hash, re‑emit keys) into run_record as append‑only events, so audit trails are reconstructable without parsing free‑form logs.

### Design choices (pre‑code)
- Use **dedicated run_record events** rather than embedding these in existing events, so downstream audits can filter explicitly.
- Event kinds:
  - `GOV_POLICY_REV` (policy id/revision/digest)
  - `GOV_PLAN_HASH` (plan hash)
  - `GOV_BUNDLE_HASH` (bundle hash at READY)
  - `GOV_REEMIT_KEY` (READY/TERMINAL re‑emit keys)
- Append these at the same boundaries where the facts become true:
  - Plan commit (policy_rev + plan_hash)
  - READY commit (bundle_hash)
  - Re‑emit publish (reemit_key with kind)

### Invariants
- Append‑only; never mutate existing ledger entries.
- Best‑effort; if append fails, SR should continue but log the failure.

### Files to touch
- `src/fraud_detection/scenario_runner/runner.py`
- Tests for run_record contents (new or extended)

---

## Entry: 2026-01-24 20:22:10 — Phase 6.2 governance facts implemented

I added explicit governance fact events to run_record so audits can query policy_rev, plan_hash, bundle_hash, and re‑emit keys directly.

### What changed
- `ScenarioRunner._commit_plan` now appends:
  - `GOV_POLICY_REV` (policy_id/revision/content_digest)
  - `GOV_PLAN_HASH` (plan_hash)
- `ScenarioRunner._commit_ready` appends:
  - `GOV_BUNDLE_HASH` (bundle_hash) when READY is committed.
- Re‑emit publish appends:
  - `GOV_REEMIT_KEY` with kind READY/TERMINAL and the reemit_key.
- Added `_append_governance_fact(...)` helper that is best‑effort and logs warnings without blocking SR flow.

### Tests
- Added governance fact assertions in:
  - `tests/services/scenario_runner/test_engine_invocation.py` (policy_rev + plan_hash)
  - `tests/services/scenario_runner/test_reemit.py` (reemit key)
- `python -m pytest tests/services/scenario_runner -q` → 35 passed, 3 skipped.

---

## Entry: 2026-01-24 20:32:10 — Phase 6.3/6.4 metrics + sinks + degrade posture

I implemented Phase 6.3 (metrics counters/durations) and Phase 6.4 (sink strategy + degrade posture) in a minimal, non‑blocking way.

### What changed
- Added `MetricsObsSink` in `obs.py`:
  - Counts events by kind and outcome.
  - Captures duration_ms metrics from event details (min/max/avg snapshot).
- Added sink composition + degrade posture:
  - `CompositeObsSink` fan‑out with per‑sink exception isolation.
  - `NullObsSink` and `OtlpObsSink` scaffold (feature‑flagged; no external deps).
  - Drop DEBUG events by default via `SR_OBS_DROP_DEBUG=true`.
- `ScenarioRunner` now:
  - accepts optional `obs_sink` for tests,
  - otherwise uses Console + Metrics sinks (and OTLP if `SR_OTLP_ENABLED=true`).

### Tests
- Added `test_obs_emission.py` to ensure obs sink failures do not block READY.
- `python -m pytest tests/services/scenario_runner -q` → 36 passed, 3 skipped.

---

## Entry: 2026-01-24 20:41:20 — Phase 6.5 tests completed

Added a metrics‑sink test and re‑ran the SR suite to close out Phase 6.5.

### Tests
- `python -m pytest tests/services/scenario_runner/test_obs_emission.py -q` → 2 passed.
- `python -m pytest tests/services/scenario_runner -q` → 37 passed, 3 skipped.

Result:
- Phase 6 test coverage now includes structured event emission, governance fact presence, and non‑blocking failure posture.

---

## Entry: 2026-01-24 20:42:45 — Phase 6 marked COMPLETE

Phase 6 is now complete: structured obs events, governance facts, metrics counters, sink scaffolding + degrade posture, and tests are all in place. Marking Phase 6 COMPLETE in the build plan.

---

## Entry: 2026-01-24 20:13:30 — Phase 6 detailed reasoning expansion (post‑implementation)

This entry expands the Phase 6 decision trail in detail. The earlier Phase 6 entries were too summary‑style, so I’m recording the actual reasoning, trade‑offs, and mechanics in a more complete form here without rewriting history.

### Why Phase 6 exists (restated intent)
- SR already had narrative logs, but those are human‑only and not joinable. We needed a **structured, stable event model** that can be used for metrics, governance, and audits without scraping logs.
- Observability must **never block SR truth**. This is non‑negotiable: no missed READY commits because telemetry sinks were down.

### Core design choices (and why)

**1) Event model as a lightweight, stable schema**
- I created a minimal `ObsEvent` with: `event_kind`, `phase`, `outcome`, `severity`, `pins`, `ts_utc`, plus optional `policy_rev`, `attempt_id`, `details`.
- This keeps the “shape” stable and explicit, without coupling to any external telemetry stack (OTLP, Prometheus, etc.).
- Pins are mandatory because **joinability is the goal**. I decided to always include `run_id`, `manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id` once canonical intent is known. This ensures any event can be joined to truth.

**2) Explicit phases & outcomes**
- I used enums for `phase` and `outcome` to avoid drifting strings in logs.
- Phase list aligns to the SR subnetworks (INGRESS / AUTHORITY / PLAN / ENGINE / EVIDENCE / COMMIT / REEMIT). This makes it easy to aggregate metrics across flows without deep parsing.

**3) Best‑effort emission (never blocking)**
- Emission happens via `_emit_obs()` and is fully guarded; all exceptions are swallowed. This was a deliberate choice: observability failure is allowed, truth failure is not.
- I added a drop‑DEBUG switch (`SR_OBS_DROP_DEBUG=true` by default) to enforce degrade posture early without extra infra.

**4) Sink architecture**
- Implemented a `CompositeObsSink` so each sink is isolated and failures are contained. If one sink fails (console, metrics, future OTLP), others still run.
- `ConsoleObsSink` is the local default for readability and dev feedback.
- `MetricsObsSink` is the minimal in‑process aggregator (counts + durations). It doesn’t export yet — it just captures a snapshot. This keeps Phase 6 lightweight while still proving the model.
- `OtlpObsSink` is a **scaffold only**; it does nothing until Phase 6/7 introduces real telemetry infra. This prevents a new dependency while allowing the interface to be stable now.

**5) Metrics design**
- I avoided building a full metrics pipeline. Instead, I track a few core counters + durations from event details. The decision here was to keep metrics **derived from events** (so we don’t double‑count under retries).
- The `MetricsObsSink` uses `event_kind` and `outcome` to drive counters. Durations are pulled from `details.duration_ms` when present (engine attempt, evidence wait, etc.).

**6) Governance facts vs observability**
- Governance facts are written into the **run_record** as dedicated events (`GOV_POLICY_REV`, `GOV_PLAN_HASH`, `GOV_BUNDLE_HASH`, `GOV_REEMIT_KEY`). These are authoritative and append‑only.
- Observability events are a **side channel**; they can be dropped without affecting truth.
- This separation ensures audits rely on the ledger, not transient telemetry.

### Mechanics: where events are emitted
I intentionally chose **milestone points** that align with control‑plane decisions, not noisy inner loops:
- Ingress: `RUN_REQUEST_RECEIVED`
- Authority: `RUN_ACCEPTED`, `RUN_ANCHORED`, `LEASE_BUSY`
- Plan: `PLAN_COMMITTED` or `PLAN_FAILED`
- Engine: `ENGINE_ATTEMPT_START`, `ENGINE_ATTEMPT_FINISH`, `ENGINE_FAILED`
- Evidence: `EVIDENCE_REUSE_RESULT`, `EVIDENCE_COMPLETE`
- Commit: `READY_COMMITTED`, `READY_PUBLISHED`, `READY_PUBLISH_FAILED`
- Re‑emit: `REEMIT_REQUESTED`, `REEMIT_BUSY`, `REEMIT_NOT_FOUND`, `REEMIT_FAILED`, `REEMIT_NOT_APPLICABLE`

### Alternatives considered (and why rejected)
- **Emit only in run_record**: rejected because run_record is authoritative but not ergonomic for real‑time monitoring.
- **Push OTLP as a hard dependency**: rejected because it adds infra coupling and violates “non‑blocking.”
- **Emit every internal step**: rejected because it becomes noisy and undermines the “noob‑readable” goal.

### Validation strategy (why these tests)
- I added a test that uses a **failing obs sink** to ensure READY still commits. This proves “observability never blocks truth.”
- I added a metrics‑sink test to show that durations are captured without needing a real exporter.
- Full SR suite is green, which ensures no regressions in core SR flows.

### Remaining risk (tracked)
- Event schema is stable but **not yet versioned**. If we expect schema evolution, we should add versioning to `ObsEvent` in Phase 7.
- Metrics are in‑process only. We will need an exporter or collector later (Phase 6.4/Phase 7).

---

## Entry: 2026-01-24 20:20:40 — Phase 7 planning (Security + ops hardening)

Starting Phase 7 planning now. This is a live decision trail (not a summary) to capture the rationale before any code changes.

### Problem framing (what Phase 7 must solve)
We now have a production‑capable SR core, control bus, and observability. The remaining risk is **security posture and operational safety**: who can submit/re‑emit, how secrets are handled, how quarantine is inspected, and how ops can recover safely without violating invariants.

Phase 7 must deliver:
- explicit AuthN/AuthZ gates at SR ingress and re‑emit
- hardened secrets handling (no secret material in artifacts/logs)
- quarantine workflows for conflicts/failures
- operational tooling and guardrails (rate limits, micro‑leases, safe re‑emit)

### Authorities / inputs
- Root AGENTS.md doctrine: fail‑closed, provenance, no‑PASS‑no‑read, append‑only truths.
- SR design‑authority: N1 auth gate + N7 ops re‑emit must be controlled; quarantine path required.
- Platform blueprint: SR is control‑plane entrypoint; IG is trust boundary; no secrets in control artifacts.

### Decisions to make (initial)
1) **AuthN/AuthZ model**
   - For now, add a **policy‑based allowlist** for ingress and re‑emit (local/dev permissive by config; prod explicit).
   - Implement as a simple callable or policy section in wiring/policy (no external auth provider in v0).

2) **Secrets hygiene**
   - Audit all SR artifacts/logs to ensure no secret values are emitted.
   - Add explicit redaction guard for any future config logging (e.g., environment variables, DSNs with passwords).

3) **Quarantine workflow**
   - Define a quarantine artifact path under `fraud-platform/<platform_run_id>/sr/quarantine/` for conflict details.
   - Provide an operator CLI command to list/inspect quarantined runs without mutating truth.

4) **Ops rate limits / safety**
   - Add re‑emit rate‑limit guardrails (micro‑lease already in place; add a max re‑emit per run per window).
   - Add a “dry‑run” re‑emit option that validates availability of facts_view/status without publishing.

5) **Hardening checks**
   - Add checks to ensure SR rejects runs when required pins or policies are missing or incompatible.

### Planned Phase 7 sections (build plan expansion)
- 7.1 AuthN/AuthZ gates (ingress + re‑emit)
- 7.2 Secrets hygiene + redaction
- 7.3 Quarantine artifacts + operator tooling
- 7.4 Ops guardrails (rate limits, dry‑run, re‑emit safety)
- 7.5 Tests + validation

### File touchpoints (expected)
- `src/fraud_detection/scenario_runner/security.py` (auth policy + redaction helpers)
- `src/fraud_detection/scenario_runner/service.py` + `cli.py` (auth gate + dry‑run re‑emit)
- `src/fraud_detection/scenario_runner/runner.py` (re‑emit rate guard + quarantine artifact write)
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`
- `docs/model_spec/platform/implementation_maps/scenario_runner.impl_actual.md`

### Invariants to preserve
- No secrets ever in artifacts/logs.
- Quarantine and re‑emit must be append‑only (no truth mutation).
- Auth failure must be explicit and observable (audit events).

---

## Entry: 2026-01-24 20:26:40 — Phase 7 implementation start (auth, secrets, quarantine, ops guardrails)

Proceeding with Phase 7 implementation now. I will append decisions as I change each section.

Immediate steps (before code edits):
1) Extend wiring config for auth + ops guardrails (auth_mode, allowlists, re‑emit rate limits).
2) Add `security.py` helpers for auth checks and redaction.
3) Wire auth gate in submit_run and reemit (service + CLI carry actor identity).
4) Implement quarantine artifact write for CONFLICT.
5) Implement re‑emit rate limit + dry‑run support.
6) Add tests for auth, redaction, quarantine, rate‑limit, dry‑run.

---

## Entry: 2026-01-24 20:52:30 — Phase 7 implementation detail: auth gates, redaction, quarantine, ops guardrails

I completed Phase 7 sections 7.1–7.4 with explicit auth gates, secrets redaction helper, quarantine artifacts, and re‑emit guardrails. This entry captures the reasoning and mechanics in detail.

### 7.1 AuthN/AuthZ gates (ingress + re‑emit)
**Design choice:** use a **policy‑controlled allowlist** in wiring for v0. This keeps auth explicit without introducing external IAM complexity yet.

**Why allowlist now?**
- We need a deterministic, auditable gate immediately.
- External auth providers would add infra coupling before the system is ready.

**Implementation details**
- Added wiring fields:
  - `auth_mode` (default `disabled`)
  - `auth_allowlist` (submit)
  - `reemit_allowlist` (re‑emit)
- Introduced `security.is_authorized(actor, allowlist, mode)`.
- `ScenarioRunner.submit_run` checks `request.invoker` against allowlist when `auth_mode != disabled`.
  - On deny: append `AUTH_DENIED` to run_record (no run_status mutation), emit obs event, return `RunResponse` with `FAILED` + message “Unauthorized.”
- `ScenarioRunner.reemit` checks `requested_by` against re‑emit allowlist (or falls back to auth_allowlist).
  - On deny: append `AUTH_DENIED`, emit obs event, return “Unauthorized.”

**Why no run_status on deny?**
- We want **auditability without claiming a run exists**. We only append a record entry; we do not create a run_status or bind the equivalence key, so a later authorized request is not blocked.

### 7.2 Secrets hygiene + redaction
**Design choice:** keep a small, explicit redaction helper rather than trying to sanitize all logs globally.

**Implementation details**
- Added `security.redact_dsn()` to mask `user:password@` in DSNs.
- Added `security.redact_env()` to mask keys that include SECRET/PASSWORD or explicitly listed sensitive keys.
- Added unit test for redaction correctness.

**Why this minimal approach?**
- SR does not currently log DSNs or envs, so a lightweight helper is enough to meet DoD without changing runtime behavior.

### 7.3 Quarantine artifacts + operator tooling
**Design choice:** write a **quarantine artifact** when a run is quarantined (EVIDENCE_CONFLICT) so ops can inspect without mutating truth.

**Mechanics**
- `_commit_terminal` calls `_write_quarantine_record` when state=QUARANTINED.
- Artifact path: `fraud-platform/<platform_run_id>/sr/quarantine/{run_id}.json` with run_id, reason, missing, record_ref, status_ref, ts_utc.
- Added CLI tooling:
  - `quarantine list` to list quarantine files
  - `quarantine show --run-id` to load a record

**Why a separate artifact?**
- It’s a quick index for ops while keeping run_record as the canonical truth. It does not mutate run_status.

### 7.4 Ops guardrails (rate limits + dry‑run)
**Re‑emit rate limit**
- Implemented `_reemit_rate_limited` by scanning run_record for recent `REEMIT_PUBLISHED` events within a time window.
- Wiring fields:
  - `reemit_rate_limit_max`
  - `reemit_rate_limit_window_seconds`
- If limit exceeded: append `REEMIT_FAILED` with reason `REEMIT_RATE_LIMIT`, return “Reemit rate limit exceeded.”

**Dry‑run re‑emit**
- Added `dry_run` to `ReemitRequest` schema/model.
- If `dry_run`:
  - Determine whether READY/TERMINAL would be published based on current status + kind.
  - Append `REEMIT_DRY_RUN` with `would_publish` list.
  - Return “Dry‑run complete; no publish performed.” (or “not applicable”).
- Dry‑run bypasses actual publish and does not check rate‑limit (no side‑effects).

### CLI/service surface updates
- CLI `run` now accepts `--invoker` to provide an auth identity.
- CLI `reemit` accepts `--dry-run`.
- Service uses `X-SR-Actor` header to populate `invoker` / `requested_by` if missing.

### Tests (added)
- `test_security_ops.py` covers:
  - auth allow/deny
  - re‑emit auth deny
  - re‑emit rate limit
  - dry‑run behavior
  - quarantine artifact emission
  - redaction helper
- Full SR suite green.

---

## Entry: 2026-01-24 20:57:10 — Phase 7 marked COMPLETE

Phase 7 is complete: auth allowlists, redaction helpers, quarantine artifacts + CLI tooling, re‑emit guardrails (rate limits + dry‑run), and tests are all in place. Marked Phase 7 COMPLETE in the build plan.

---

## Entry: 2026-01-24 20:30:20 — Lease token exposure mitigation (SR runtime artifacts)

Problem surfaced:
- GitGuardian flagged a lease token file under `artefacts/fraud-platform/<platform_run_id>/sr/index/leases/...json`.
- Lease tokens are **capability tokens** (who holds it can renew/act as leader). Even though they are local/dev artifacts, they must be treated as secrets.

Decision:
- **Do not ignore all of `artefacts/`** (engine depends on it). Instead, ignore only SR runtime subpaths that can contain sensitive tokens.
- Add an explicit **user‑facing warning** (docs + runtime log) so operators are alerted to review and decide how to handle runtime artifacts after a run.

Actions taken:
1) Removed the tracked lease token file from git index (left local file intact).
2) Added `.gitignore` entries for `artefacts/fraud-platform/<platform_run_id>/sr/index/` (covers lease tokens + sqlite authority).
3) Added a security note in `services/scenario_runner/README.md` warning that SR runtime artifacts may include sensitive capability tokens.
4) Added a runtime warning in `ScenarioRunner.__init__` for local object_store roots to alert operators.

Rationale:
- Keeps engine artifacts in git while preventing SR runtime secrets from being committed.
- Provides an explicit, user‑visible alert so operators can choose whether to delete or preserve runtime artifacts after runs.

---

## Entry: 2026-01-24 20:45:30 — Phase 8 planning (Integration tests + CI gates)

Starting Phase 8 planning now. This is a live decision trail to capture reasoning before any implementation.

### Problem framing (what Phase 8 must solve)
We have a feature-complete SR through Phase 7, but we still need **confidence at scale**: integration tests that prove cross-cutting behavior (storage + evidence + invocation + control bus + re-emit) and CI gates that prevent regressions. Phase 8 is about **proving correctness across boundaries**, not adding new features.

Key risks to address:
- Regressions in at-least-once/idempotency under integration conditions.
- Silent contract drift between SR and engine interface_pack artifacts.
- Bus + re-emit flows that work in unit tests but fail in LocalStack parity.
- Tests that are too heavy for PR gates, leading to slow or flaky CI.

### Authorities / inputs
- Root AGENTS.md: fail-closed, append-only truth, black-box engine boundary.
- SR contracts and interface_pack gate map (authoritative for gate verification).
- Existing Phase 2.5/3 parity tests and LocalStack Kinesis tests.

### Decisions to make (Phase 8 scope + strategy)
1) **Test tiers and gating levels**
   - I want a **tiered test model** so PR gates are fast but still meaningful:
     - Tier 0: unit + fast integration (no external services).
     - Tier 1: local parity (MinIO + Postgres) storage + evidence tests.
     - Tier 2: LocalStack Kinesis end-to-end control bus + re-emit test.
     - Tier 3: engine-artifact reuse tests (using real run roots).
   - CI should run Tier 0 on every PR and defer heavier tiers to nightly/explicit runs.

2) **Contract drift checks**
   - Add a lightweight **schema compatibility check** that validates SR’s interface_pack reads
     (gate map, output catalog, instance receipt schema) without touching engine code.
   - The check should fail-closed if a referenced contract is missing or invalid.

3) **Engine artifacts as fixtures**
   - Use existing `runs/local_full_run-5/...` artifacts as fixtures (read-only).
   - Tests will **copy to temp** before mutation to avoid accidental drift.
   - If the fixture is missing, tests should skip with a clear reason.

4) **CI environment safety**
   - No credentials in CI config.
   - Use `.env.localstack.example` + ephemeral LocalStack for Tier 2.
   - Keep all integration tests opt-in or gated by env vars to avoid accidental CI flakiness.

### Planned Phase 8 sections (build plan expansion)
- 8.1 Test tiers + markers (unit, parity, localstack, engine-fixture)
- 8.2 Golden path integration (submit → plan → invoke stub → evidence → READY)
- 8.3 Duplicate/at-least-once integration (replay + idempotent events)
- 8.4 Fail-closed integration (missing gates, drifted receipts, unknown output)
- 8.5 Control bus + re-emit E2E (LocalStack Kinesis)
- 8.6 Contract compatibility checks (interface_pack validation)
- 8.7 CI gates + runbooks (what runs when, how to reproduce locally)

### File touchpoints (expected)
- `tests/services/scenario_runner/` (new integration tests + markers)
- `scripts/` or `config/ci/` (test runner presets)
- `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`
- `docs/model_spec/platform/implementation_maps/scenario_runner.impl_actual.md`
- `docs/logbook/01-2026/2026-01-24.md`

### Invariants to preserve
- Engine remains a black box (no engine code changes).
- Tests must never mutate canonical truth (use temp copies for artifacts).
- Fail closed on missing/invalid contracts.
- No secrets or credentials in code/docs/impl_actual.

---

## Entry: 2026-01-24 20:47:10 — Correction: sensitive-artifacts warning moved to AGENTS

I moved the sensitive runtime artifacts warning out of `services/scenario_runner/README.md` and into the root `AGENTS.md` so it is a **platformwide rule**, not SR-scoped.

Why:
- The risk (runtime capability tokens/credentials) is not SR-specific.
- Root AGENTS is the correct authority for cross-platform operational rules.

Action taken:
- Removed the SR README warning.
- Added a platformwide rule in AGENTS: do not commit sensitive runtime artifacts and explicitly alert the user when such artifacts are created.

No credentials were added or recorded during this change.

---

## Entry: 2026-01-24 20:57:20 — Phase 8 implementation start (tests + CI gates)

I am starting Phase 8 implementation now. This entry captures the concrete steps I will take before making code changes.

### Implementation steps (ordered)
1) **Define test tiers with markers** in pytest configuration (unit/parity/localstack/engine_fixture) and apply markers to existing SR tests that require external services or fixtures.
2) **Add contract compatibility tests** that validate interface_pack integrity (catalogue ↔ gate map references, schema refs, dictionary refs, upstream gate references). This is a read-only check to fail fast on contract drift.
3) **Add parity integration test** for SR reuse flow using MinIO + Postgres (env‑gated), to prove the full SR pipeline is correct under production‑like storage semantics.
4) **Update SR runbooks** with explicit tiered test commands and env var requirements (no secrets).
5) **Log test results** in the logbook once executed.

### Design intent for these changes
- Keep engine as a black box (no engine code changes).
- Fail closed on missing or incompatible contracts.
- Separate fast PR‑gating tests from heavier parity/LocalStack/fixture tiers.
- Ensure all integration tests are opt‑in (env‑gated) to avoid CI flakiness.

---

## Entry: 2026-01-24 21:01:10 — Phase 8 implementation detail: test markers + contract checks + parity reuse

I implemented the first Phase 8 steps now, with emphasis on **tiered tests** and **contract drift protection**.

### 1) Test tier markers (pytest.ini + SR tests)
I added explicit pytest markers so CI can gate fast vs heavy tiers:
- `unit` (fast, no external deps)
- `parity` (MinIO + Postgres)
- `localstack` (Kinesis)
- `engine_fixture` (real engine artifacts under `runs/`)

I **only marked tests that require external resources** to preserve fast Tier‑0 coverage:
- `test_s3_store.py` + `test_authority_store_postgres.py` → `parity`
- `test_control_bus_kinesis.py` → `localstack`
- `test_gate_verifier.py` → `engine_fixture`
- `test_gate_verification_integration.py` and `test_evidence_negative_integration.py`:
  - only the real‑fixture tests are marked `engine_fixture`
  - the synthetic gate verification test remains Tier‑0

This keeps the default SR test subset fast while still letting us opt into deeper tiers.

### 2) Interface‑pack contract compatibility tests (fail‑closed)
I added `test_contract_compatibility.py` to validate interface_pack integrity:
- Catalogue ↔ gate map consistency (no dangling gate/output IDs).
- Gates must authorize at least one output.
- Upstream gate dependencies must exist.
- `schema_ref` / `dictionary_ref` / `index_schema_ref` / `receipt_schema_ref` resolve to real files and JSON pointers.

This test is read‑only, fast, and fails closed if contracts drift.

### 3) Parity reuse integration test (MinIO + Postgres)
I added `test_parity_integration.py` to prove SR reuse under parity storage:
- Uses MinIO (S3‑compatible) + Postgres via env‑gated DSNs.
- Uses real engine artifacts from `runs/local_full_run-5`.
- Runs a full SR reuse pipeline and asserts READY commit with S3‑backed truth.

This is Tier‑1 + Tier‑3 combined (`parity` + `engine_fixture`) and opt‑in by env vars.

### 4) Runbook updates (no secrets)
I documented tiered test commands and required env var names in `services/scenario_runner/README.md` without embedding any credentials.

---

## Entry: 2026-01-24 21:05:10 — Phase 8 fix: pytestmark tuple error in parity test

I attempted a Tier‑0 run and pytest failed during collection because `pytestmark` in the new parity test was set to a tuple of MarkDecorators. Pytest expects a single Mark or a list of Marks.

Fix applied:
- Updated `tests/services/scenario_runner/test_parity_integration.py` to use
  `pytestmark = [pytest.mark.parity, pytest.mark.engine_fixture]`.

This is a test‑collection fix only; it does not change runtime SR behavior.

---

## Entry: 2026-01-24 21:12:10 — Phase 8 fix: contract compatibility resolver paths

Tier‑0 test run failed on `test_interface_pack_refs_resolve`. The issue was **my resolver assumed schema refs were repo‑root relative**, but the interface_pack uses **relative refs inside the interface_pack root** (e.g., `schemas.1A.yaml`).

Fix applied:
- Resolve refs relative to `docs/model_spec/data-engine/interface_pack` first, then fall back to repo root.
- Accept fragment pointers without a leading slash (treat `#foo` as `#/foo`).
- Marked the contract compatibility test as `unit` to keep it in Tier‑0.

This aligns the resolver with the interface_pack contract style while keeping it strict on missing files and bad pointers.

---

## Entry: 2026-01-24 21:18:40 — Phase 8 fix: schema/dictionary ref resolution rules

Tier‑0 still failed because interface_pack references use **schema file names without paths**
(`schemas.1A.yaml`, `schemas.layer3.yaml`) and **dictionary refs that point to dataset IDs**
instead of JSON‑Pointer paths. I updated the resolver to match the contract style:

Fixes applied:
- If a ref file is a bare filename, resolve it using the **segment context**:
  - map segment → layer (1A/1B/2A/2B/3A/3B → layer‑1, 5A/5B → layer‑2, 6A/6B → layer‑3)
  - prefer `docs/model_spec/data-engine/layer-{L}/specs/contracts/{segment}/{file}`
  - fall back to searching within that layer’s contracts; error on ambiguity
- If a dictionary_ref fragment is a bare token (e.g., `#outlet_catalogue`), treat it as
  a dataset **id lookup** within the dictionary file rather than a JSON‑Pointer path.

This aligns the check with how the engine specs and dictionaries are structured while
remaining strict on missing or ambiguous refs.

---

## Entry: 2026-01-24 21:24:30 — Phase 8 fix: schema $id anchor resolution + cross-layer schema lookup

Tier‑0 still failed for two reasons:
1) Some schema refs point to **subschema anchors via `$id`**, not via strict JSON‑Pointer paths.
2) Some outputs (e.g., 5B RNG logs) reference **schemas.layer1.yaml**, which lives under
   layer‑1 contracts even though the owning segment is layer‑2.

Fixes applied:
- When JSON‑Pointer traversal fails, fall back to **$id scan** (match `$id == #{pointer}` or `$id == pointer`).
- If segment‑layer lookup fails, allow a **global search across data‑engine contracts** for the schema filename.
  This still errors on ambiguity.

This makes the compatibility test faithful to how schemas are actually referenced in the specs.

---

## Entry: 2026-01-24 21:27:10 — Phase 8 validation: Tier‑0 tests green

I reran Tier‑0 tests after the resolver fixes:
`python -m pytest tests/services/scenario_runner -m "not parity and not localstack and not engine_fixture" -q`

Result: **35 passed, 15 deselected**. Tier‑0 is now green.

---

## Entry: 2026-01-24 21:32:40 — Phase 8 implementation: Sections 8.2–8.4 (golden path + duplicate/idempotency + fail‑closed)

I am proceeding with Phase 8 sections 8.2–8.4. This is the pre‑change decision trail.

### What I will add (tests only, no runtime behavior changes)
1) **Golden path integration test** that exercises:
   submit → plan → invoke → receipt validation → evidence collection → READY.
   - Use a **stub EngineInvoker** that writes a minimal engine run root
     (run_receipt + gate bundle + sealed_inputs_1A output).
   - Keep it Tier‑0 (no external services), mark as integration.

2) **Duplicate/idempotency integration test**:
   - Submit the same run twice with the same equivalence key.
   - Verify the second call returns the lease‑held response and does not duplicate READY commit or bus publish.

3) **Fail‑closed integration tests**:
   - Unknown output_id fails in plan compile with reason `UNKNOWN_OUTPUT_ID`.
   - Unknown gate_id fails in plan compile when gate map is missing required gate.

### Why this design
- It keeps the engine black‑box (no engine code changes).
- It tests SR invariants end‑to‑end using the real interface_pack contracts.
- It stays in Tier‑0 so CI can gate regressions without external services.

---

## Entry: 2026-01-24 21:40:20 — Phase 8 implementation detail: added 8.2–8.4 integration tests

I implemented the tests described in the pre‑change note. This section captures the mechanics.

### 8.2 Golden path integration (invoke → READY)
Added `tests/services/scenario_runner/test_golden_path_integration.py`:
- Uses a **StubEngineInvoker** that writes:
  - `run_receipt.json` with required pins (run_id/manifest/parameter/seed).
  - 1A validation bundle (`index.json` + `_passed.flag` digest).
  - `sealed_inputs_1A` output under the catalogue path.
- Runs SR with `Strategy.FORCE_INVOKE` to exercise the **engine invocation path**.
- Asserts READY commit, facts_view present, and locators populated.

This validates the full pipeline without external services.

### 8.3 Duplicate/idempotency integration
Added `tests/services/scenario_runner/test_duplicate_idempotency_integration.py`:
- Submits the same run twice (same equivalence key).
- Confirms second submit returns the **lease‑held** response.
- Confirms READY publish file count is unchanged and only one READY_COMMITTED event exists.

This proves at‑least‑once safety at the SR boundary.

### 8.4 Fail‑closed integration
Added `tests/services/scenario_runner/test_fail_closed_integration.py`:
- Unknown output_id → plan failure, status reason `UNKNOWN_OUTPUT_ID`.
- Gate map missing required gate → plan failure, status reason `UNKNOWN_GATE_ID`.

These enforce fail‑closed posture on contract inconsistencies.

All new tests are Tier‑0 (no external services) and marked `integration`.

---

## Entry: 2026-01-24 21:43:40 — Phase 8 validation: Tier‑0 tests green after 8.2–8.4

Ran Tier‑0 SR suite after adding the integration tests:
`python -m pytest tests/services/scenario_runner -m "not parity and not localstack and not engine_fixture" -q`

Result: **39 passed, 15 deselected**.

---

## Entry: 2026-01-24 21:48:10 — Phase 8 implementation start: 8.5–8.7 (LocalStack E2E + CI gates/runbooks)

Starting Option 2 now. This is the pre‑change decision trail.

### What I will implement
1) **LocalStack Kinesis E2E re‑emit tests (8.5)**:
   - Use real SR flow to publish READY to Kinesis.
   - Run re‑emit (READY + TERMINAL) and assert Kinesis envelope correctness.
   - Keep tests env‑gated and marked `localstack` + `integration`.

2) **CI gate + runbook wiring (8.7)**:
   - Add a small SR test runner script to codify the tier matrix.
   - Update SR README with explicit CI gating guidance and runbook commands.

### Constraints
- No credentials embedded anywhere.
- Engine remains a black box (no engine code changes).
- LocalStack tests must be opt‑in (env‑gated) to avoid CI flakiness.

---

## Entry: 2026-01-24 22:01:10 — Phase 8 implementation detail: LocalStack re‑emit E2E + CI/runbook wiring

I implemented 8.5–8.7 as planned.

### 8.5 LocalStack Kinesis E2E (re‑emit)
Added `tests/services/scenario_runner/test_localstack_reemit_e2e.py`:
- Env‑gated via `SR_KINESIS_ENDPOINT_URL`, `SR_KINESIS_STREAM`, `SR_KINESIS_REGION` (or `AWS_DEFAULT_REGION`), and AWS creds.
- Uses a **StubEngineInvoker** to produce a valid run_receipt + 1A validation bundle + `sealed_inputs_1A`.
- READY path:
  - Submit run with `Strategy.FORCE_INVOKE` so SR goes through attempt + receipt validation + evidence collection.
  - Call `runner.reemit(READY_ONLY)` and assert a **Kinesis envelope** with `kind=READY_REEMIT`.
- TERMINAL path:
  - Submit a run with `output_ids=["unknown_output"]` to force `UNKNOWN_OUTPUT_ID` failure.
  - Call `runner.reemit(TERMINAL_ONLY)` and assert envelope `kind=TERMINAL_REEMIT`.
- Assertions read Kinesis records and match `message_id` + payload.

### 8.7 CI gates + runbook wiring
Added `scripts/run_sr_tests.ps1` to codify the tier matrix:
- `-Tier tier0|parity|localstack|engine_fixture|all`
- Uses active Python by default (no credentials embedded).
Updated `services/scenario_runner/README.md`:
- CI gate recommendations (PR = Tier 0; nightly/manual = Tier 1–3).
- Script usage examples.

No engine code changes; all updates are tests/runbooks only.

---

## Entry: 2026-01-24 22:04:20 — Phase 8 validation: Tier‑0 tests green after 8.5–8.7

Ran Tier‑0 SR suite after adding LocalStack E2E tests and the runbook script:
`python -m pytest tests/services/scenario_runner -m "not parity and not localstack and not engine_fixture" -q`

Result: **39 passed, 17 deselected**.

---

## Entry: 2026-01-24 22:09:10 — Phase 8 fix: LocalStack re‑emit E2E fetch logic

LocalStack E2E failed because READY re‑emit uses the **same idempotency key** as the initial READY publish, so the first record fetched by message_id was the original READY envelope (`kind=READY`). The re‑emit record exists but is not the first match.

Fix:
- Updated `_fetch_envelope` to optionally wait for a specific `attributes.kind` and return the matching envelope, while still failing if the message_id never appears.

This preserves idempotency semantics while making the test assert the intended re‑emit envelope.

---

## Entry: 2026-01-24 22:12:40 — Phase 8 validation: LocalStack tier green

Ran LocalStack tier after fixing the re‑emit envelope matcher:
`python -m pytest tests/services/scenario_runner -m "localstack" -q`

Result: **3 passed, 53 deselected** (botocore `datetime.utcnow()` deprecation warnings only).

---

## Entry: 2026-01-24 22:16:10 — Phase 8 fix: parity reuse test lease collision

Parity tier initially failed because the test used a **fixed run_equivalence_key**, so the
Postgres lease persisted across runs and returned “lease held by another runner.” This is
expected for durable authority storage.

Fix:
- Updated `test_parity_integration.py` to use a **unique run_equivalence_key** per run
  (`sr-parity-reuse-6a-{uuid}`), ensuring a new run_id and fresh lease.

This keeps the parity test stable without weakening the lease semantics.

---

## Entry: 2026-01-24 22:22:10 — Phase 8 validation: parity + engine_fixture tiers green

Ran parity tier (MinIO + Postgres) with local credentials:
`python -m pytest tests/services/scenario_runner -m "parity" -q`
Result: **4 passed, 52 deselected** (botocore datetime.utcnow deprecation warnings).

Ran engine_fixture tier:
`python -m pytest tests/services/scenario_runner -m "engine_fixture" -q`
Result: **10 passed, 1 skipped, 45 deselected**.

LocalStack was stopped after validation.

---

## Entry: 2026-01-24 22:29:10 — Phase 8 doc update: runbook steps for parity/localstack tiers

User requested a clearer “how to run this” after tearing down containers. I will update
`services/scenario_runner/README.md` to include **explicit bring‑up/tear‑down steps**
for parity (MinIO + Postgres) and LocalStack tiers, plus the env var setup.

No code changes; docs only. No credentials will be embedded.

---

## Entry: 2026-01-25 20:56:20 — SR runtime root migration + run log output (pre‑change)

### Trigger
User commanded that SR runtime artifacts move from `artefacts/fraud-platform` to `runs/fraud-platform` and that SR runs emit a **platform run log** under `runs/fraud-platform/*.log` (similar to engine run logs). This must be done without touching the engine code.

### Live reasoning (what needs to change and why)
- SR already writes by‑ref refs like `fraud-platform/<platform_run_id>/sr/run_status/...`. If the object store root is set to `runs`, the resulting filesystem path becomes `runs/fraud-platform/<platform_run_id>/sr/...` which matches the new standard.
- The prior local root (`artefacts`) was meant for external inputs; SR outputs do not belong there. Moving the root fixes semantics and prevents cross‑component confusion.
- Logging must be explicit and readable. We need a deterministic SR run log path so the user can see what happened without scrolling console output.
- The run_id is deterministic from `run_equivalence_key`, so we can **compute it before running** and log to `runs/fraud-platform/<platform_run_id>/sr_run_<run_id>.log`.

### Plan (before code)
1) Update local SR wiring files:
   - `config/platform/sr/wiring_local.yaml` already uses `runs/` (verify).
   - Update `wiring_local_parity.yaml` and `wiring_local_kinesis.yaml` to use `runs/fraud-platform/<platform_run_id>/control_bus`.
   - Ensure `authority_store_dsn` defaults reference `runs/fraud-platform/<platform_run_id>/sr/index/`.
2) Update SR logging:
   - Extend `scenario_runner.logging_utils.configure_logging()` to accept an optional file path.
   - In `scenario_runner.cli`, compute `run_id` from `run_equivalence_key` and pass a `runs/fraud-platform/<platform_run_id>/sr_run_<run_id>.log` file.
   - For re‑emit/quarantine commands, emit a separate log file under `runs/fraud-platform/`.
3) Move the on‑disk SR artifacts directory from `artefacts/fraud-platform/sr` to `runs/fraud-platform/<platform_run_id>/sr` (and update any refs/tests/docs that search for it).

### Guardrails
- No secrets in logs or docs. Only deterministic IDs + non‑sensitive metadata appear in log paths.
- Engine remains a black box; SR only reuses its output paths.

---

## Entry: 2026-01-25 21:06:20 — Applied: SR runtime root migration + run logs

### Changes applied (concrete)
1) **SR logging**
   - `src/fraud_detection/scenario_runner/logging_utils.py`: added optional file handler support.
   - `src/fraud_detection/scenario_runner/cli.py`: logs now append to the **shared platform log** at `runs/fraud-platform/platform.log` (override via `PLATFORM_LOG_PATH`). This replaces the per‑run log files so all platform activity is in one place.
2) **Wiring updates**
   - `config/platform/sr/wiring_local_parity.yaml` and `wiring_local_kinesis.yaml`: control bus root now `runs/fraud-platform/<platform_run_id>/control_bus`.
   - `config/platform/sr/wiring_local.yaml` already uses `runs` and remains canonical.
3) **Runtime artifact migration**
   - Moved on‑disk SR artifacts from `artefacts/fraud-platform/` → `runs/fraud-platform/`.
   - Updated the synthetic `run_facts_view` locator paths to reference `runs/fraud-platform/engine_outputs/...` so IG pull can resolve them consistently.

### Outcome
SR now writes to the **platform runtime root** (`runs/fraud-platform`) and appends to the shared platform log (`runs/fraud-platform/platform.log`). No engine code touched.

---

## Entry: 2026-01-25 21:10:40 — Remove SR PowerShell helpers (Makefile only)

### Trigger
User requested that **all** PowerShell helpers be removed and the Makefile be the only workflow surface.

### Change
- Removed `scripts/run_sr_tests.ps1` and `scripts/localstack.ps1`.
- Added Make targets in `makefile` for SR test tiers and LocalStack lifecycle.
- Updated `services/scenario_runner/README.md` to reference Make targets.

### Notes
Historical entries referencing the PowerShell helpers remain as history; Make targets now supersede those workflows.

---

## Entry: 2026-01-25 22:51:05 — Plan: platform run ID + session logs (SR side)

### Trigger
User wants a **platform run ID** to separate runs and a shared platform log that still keeps session‑scoped logs.

### Plan (SR changes only)
1) Use a shared runtime helper to resolve `platform_run_id` (env → ACTIVE_RUN_ID → generate on SR run).
2) Update SR CLI logging to append to:
   - Global `runs/fraud-platform/platform.log`.
   - Session `runs/fraud-platform/<platform_run_id>/platform.log`.
3) Append a session event line for SR `run` and `reemit` commands with key refs (run_id, status_ref, facts_view_ref).

### Guardrails
- No secrets in session files.
- SR ledger paths remain unchanged.

## Entry: 2026-01-25 23:12:50 — Applied: platform run session logs (SR wiring)

### What changed
- SR CLI now uses shared runtime helper to write logs to:
  - Global `runs/fraud-platform/platform.log`.
  - Session log `runs/fraud-platform/<platform_run_id>/platform.log` when a run ID is active.
- SR service (`service.py`) is now aligned to the same log path resolution (no more silent console‑only logs).

### Session metadata
- SR `run` and `reemit` commands append a `session.jsonl` entry with non‑secret references (run_id, status_ref, facts_view_ref, publish status).

### Notes
- Platform run ID resolution: `PLATFORM_RUN_ID` env → `ACTIVE_RUN_ID` file → generate on SR run.
- No ledger paths or SR ownership semantics changed.


## Entry: 2026-01-25 23:30:20 — Local sharding + reemit workflow (SR/IG loop)

### What changed and why
- Enabling sharded pulls in `local.yaml` requires a **READY reemit loop** to advance checkpoints under the time budget.
- A Make target for SR reemit keeps this loop consistent with the Makefile‑only workflow directive.


## Entry: 2026-01-25 23:33:10 — Applied: SR READY reemit workflow note

### Change
- Added Make target + README note so operators can re‑emit READY for the same run_id (needed for checkpointed pulls).


## Entry: 2026-01-25 23:59:40 — Policy: local smoke vs dev completion

### Decision
- Local testing is **smoke‑only** with time budget caps.
- Dev testing is **completion‑grade** (no cap) to validate full READY ingestion.

### Why
Local hardware can’t finish large engine outputs within 10 minutes; the cap is necessary for deterministic smoke validation. Dev runs must prove full completion without weakening production semantics.


## Entry: 2026-01-28 19:45:26 — SR alignment planning (WSP‑first streaming + Oracle boundary)

### Trigger
User requested a plan to align SR with the **current streaming path** (WSP‑first) and the fact that **Data Engine + Oracle Store are outside the platform**.

### Problem framing
SR was built to publish a join surface (run_facts_view + READY) for IG’s legacy pull path. In the WSP‑first runtime, **data‑plane traffic comes from WSP**, not SR. SR must therefore be re‑scoped as **control‑plane authority** while still ensuring evidence/gate correctness and readiness governance. The plan must avoid conflating SR with WSP or Oracle Store ownership.

### Constraints / non‑negotiables
- Engine + Oracle Store remain **external truth** (SR may read by‑ref, never mutate).
- WSP is the primary runtime producer; IG is the ingest gatekeeper.
- SR remains the **sole readiness authority** and issues control signals, not traffic.
- Fail‑closed on unknown compatibility, missing evidence, or invalid receipts.

### Alignment decisions (high‑level)
1) **SR remains readiness authority, but not a data‑plane producer.**
   - SR publishes control facts and readiness only; no implied ownership of streaming.

2) **SR should explicitly surface Oracle pack identity** in its truth surfaces.
   - Add references (oracle pack id / engine run root / pack manifest ref) so WSP/ops can link control‑plane runs to data‑plane packs.

3) **Legacy IG pull remains optional/backfill.**
   - SR outputs must still be valid for backfill, but design narrative should treat pull as legacy.

4) **Phase plan update (v0 alignment track).**
   - Add a post‑v0 alignment phase to SR build plan so future work doesn’t drift.

### Plan outline to add to SR build plan
- **Phase 9 — WSP alignment + Oracle boundary**
  - 9.1 **Control‑plane re‑scope**: update SR docs/contracts to define SR as readiness authority only; remove any implied streaming responsibility.
  - 9.2 **Oracle pack linking**: add pack identity fields to run_facts_view / READY (by‑ref), with schema updates + validation.
  - 9.3 **Legacy pull compatibility**: keep run_facts_view locators for backfill; document WSP as primary path.
  - 9.4 **Ops guidance**: operator docs and examples reflect WSP‑first runtime; SR used to gate readiness.
  - 9.5 **Validation**: tests to ensure SR publishes control facts without depending on WSP or engine internals.

### Next actions (docs only, no code yet)
- Update `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md` with Phase 9 alignment.
- Capture this alignment intent in SR impl_actual as a decision trail entry (this entry).
- Log in docs/logbook.

---

## Entry: 2026-01-28 19:49:14 — SR alignment phased into 3 stages (docs/contracts, implementation, validation)

### Trigger
User requested the WSP alignment work be split into three robust phases rather than a single Phase 9.

### Decision
Expand the SR alignment track into **three phases** so we do not conflate:
1) **Docs + contracts** (design authority + schema changes + narrative alignment).
2) **Implementation** (SR truth surfaces + READY payload linking to Oracle pack identity).
3) **Validation** (compat tests + fail‑closed checks + legacy pull preservation).

### Rationale
- Design and contract updates are pre‑conditions to safe implementation.
- Implementation should only proceed after contracts reflect WSP‑first flow.
- Validation must be its own phase to ensure the alignment doesn’t break backfill or compatibility.

### Next steps
- Update SR build plan to add Phase 9/10/11 alignment sequence.
- Keep SR impl_actual trail in sync with the new phase breakdown.

---

## Entry: 2026-01-28 19:53:30 — Phase 9 planning (SR WSP‑alignment docs + contracts)

### Trigger
User initiated Phase 9 planning to realign SR with the WSP‑first runtime and Oracle Store boundary.

### Phase 9 scope (docs + contracts only)
Phase 9 updates **design authority + SR contracts** to reflect the WSP‑first runtime. No runtime code changes yet (those belong to Phase 10). The goal is to lock the **control‑plane semantics** and the **schema fields** SR will carry so implementation work does not drift.

### What must change (and why)
1) **SR is control‑plane authority only**
   - SR owns readiness, gates, and truth surfaces, but does not own the traffic stream.
   - This must be explicit in SR docs and platform narratives to avoid WSP/IG role confusion.

2) **Oracle Store is external truth**
   - SR should never imply ownership of engine outputs; it may only reference them by‑ref.
   - Contracts should express pack identity as references, not inline payload.

3) **Control‑plane ↔ data‑plane linkage**
   - SR must include *pack references* so operators and WSP can correlate readiness to the exact oracle pack.
   - These fields must be schema‑validated and fail‑closed on mismatches when present.

### Contracts to update (Phase 9 deliverables)
Target SR contracts under `docs/model_spec/platform/contracts/scenario_runner/`:
- **run_facts_view.schema.yaml**
- **run_ready_signal.schema.yaml**
- **run_record.schema.yaml** (if it carries derived control facts)

### Proposed schema additions (draft, to refine in Phase 9)
Add a **by‑ref pack block** with optional fields (presence rules below):
```
oracle_pack_ref:
  oracle_pack_id: <hex64>
  manifest_ref: <uri-or-path>
  engine_run_root: <uri-or-path>
  oracle_root: <uri-or-path>
  engine_release: <string>
```

**Presence rules (planning intent):**
- If `_oracle_pack_manifest.json` exists, SR must populate `oracle_pack_id` + `manifest_ref` (fail‑closed otherwise).
- `engine_run_root` should always be present when SR was invoked with it.
- `oracle_root` is optional but recommended for operator clarity.
- `engine_release` is included when present in the pack manifest (no requirement if absent).

### Doc updates required (Phase 9 deliverables)
- **SR design authority**: explicitly mark SR as control‑plane only; call out WSP as the primary runtime producer.
- **Platform narratives**: update control/ingress and real‑time decision loop to show WSP‑first path.
- **Platform blueprint note**: update “graph” description so WSP is on the data‑plane edge and SR feeds readiness only.
- **Contracts index**: update any cross‑references that imply SR is the data plane.

### Options considered (and why)
1) **Embed pack identity directly in READY only**
   - Rejected: run_facts_view is also consumed by ops/backfill; it should carry the same linkage.

2) **Put pack identity only in run_record**
   - Rejected: run_record is internal truth; READY + facts_view are the integration surfaces.

3) **New top‑level fields vs nested block**
   - Chosen: **nested `oracle_pack_ref` block** to keep schema evolution contained and optional.

### Phase 9 work plan (stepwise)
1) Review SR contract schemas and decide exact field names + validation rules.
2) Update schemas and any example payloads in docs.
3) Update SR design authority and relevant platform narratives to reflect WSP‑first runtime.
4) Update SR build plan + operator docs with the new linkage semantics.
5) Record decisions and update logbook immediately as changes are made.

### Out‑of‑scope for Phase 9 (explicit)
- No SR runtime code changes.
- No WSP changes.
- No IG changes.

---

## Entry: 2026-01-28 20:02:05 — Phase 9 implemented (docs + contracts alignment)

### Step‑by‑step decisions and changes
1) **Add Oracle pack references to SR control-plane contracts**
   - Updated `run_facts_view.schema.yaml` and `run_ready_signal.schema.yaml` to include an optional `oracle_pack_ref` block.
   - Chose a **nested object** to keep schema evolution contained and avoid cluttering top‑level fields.
   - Fields are **by‑ref only** (`oracle_pack_id`, `manifest_ref`, `engine_run_root`, `oracle_root`, `engine_release`) with `minProperties: 1` to prevent empty blocks.
   - Reason: link SR readiness to the exact external Oracle pack without implying SR owns the data plane.

2) **Document WSP‑first runtime explicitly in SR design authority**
   - Added a WSP‑first runtime note: SR is control‑plane only; WSP is the primary data‑plane producer.
   - Rewrote IG↔SR join text to treat IG pull as legacy/backfill and WSP streaming as primary.
   - Updated Path P1 to include WSP streaming into IG.
   - Reason: prevent role conflation and align the join surface narrative with the current runtime architecture.

3) **Align platform narratives and blueprint**
   - Control & Ingress narrative now names WSP as the stream producer and Oracle Store as external truth.
   - Real‑time decision loop explicitly references WSP as the streaming actor.
   - Blueprint note clarifies WSP is triggered by READY + pack refs and streams from Oracle Store (does not read SR for payloads).
   - Join surface section now lists Oracle pack refs as minimum required linkage.
   - Reason: keep platform‑wide narratives consistent with the WSP‑first runtime and Oracle boundary.

4) **Contract README update**
   - Added a compatibility note in SR contracts README to document the new optional `oracle_pack_ref` block.
   - Reason: ensure contract consumers understand the new linkage fields without searching schema diffs.

### Out‑of‑scope (kept out intentionally)
- No SR runtime code changes (Phase 10).
- No IG/WSP implementation changes.
- No behavior changes in READY emission; only contract + doc alignment.

### Tests run (local)
- `.\.venv\Scripts\python.exe - <<'PY'` (YAML parse sanity for updated schemas)

---

## Entry: 2026-01-28 20:05:02 — Phase 9 test command correction

### Correction
- YAML parse sanity was executed via PowerShell here‑string:
  `@'... '@ | .\.venv\Scripts\python.exe -`
- Result: ok

---

## Entry: 2026-01-28 20:11:39 — Phase 10 planning (SR implementation for WSP alignment)

### Trigger
User requested Phase 10 implementation after Phase 9 docs/contracts alignment.

### Scope (implementation only)
- Populate `oracle_pack_ref` in SR **run_facts_view** and **run_ready_signal**.
- Validate pack identity when a pack manifest exists (fail‑closed on mismatch/invalid).
- Preserve legacy locators in run_facts_view (backfill compatibility).
- Keep SR as control‑plane only (no WSP/IG behavior changes).

### Decisions (locked before coding)
1) **Pack ref source**
   - Source is the engine run root used for evidence collection (actual engine run root, not just request intent).
   - We will pass the resolved engine run root into `_commit_ready` to avoid losing invoker‑assigned paths.

2) **Manifest validation**
   - If `_oracle_pack_manifest.json` exists, validate against Oracle Store schema and compare its `world_key` to SR pins.
   - If validation fails or pins mismatch → SR fails closed with reason `ORACLE_PACK_INVALID` or `ORACLE_PACK_MISMATCH`.
   - If manifest is missing → proceed without pack id, but still include `engine_run_root` in `oracle_pack_ref`.

3) **Schema root for validation**
   - SR will load Oracle Store schemas from `docs/model_spec/platform/contracts/oracle_store` (sibling to SR schema root).

4) **Payload fields**
   - `oracle_pack_ref` will include:
     - `engine_run_root` always (when known),
     - `manifest_ref`, `oracle_pack_id`, `engine_release` when manifest is present and valid.
   - No `oracle_root` yet (SR lacks reliable oracle root context in wiring).

5) **Re-emit READY behavior**
   - Re-emit will reuse `oracle_pack_ref` from stored `run_facts_view` when present.
   - This keeps READY re-emit consistent without recomputing pack refs.

### Planned implementation steps
1) Add Oracle Store schema registry to SR runner.
2) Implement `_build_oracle_pack_ref(...)` helper with validation + pin matching.
3) Update `_commit_ready` to:
   - build pack ref,
   - fail‑closed on mismatch/invalid manifest,
   - attach `oracle_pack_ref` to facts_view + ready payload.
4) Update re-emit READY to include `oracle_pack_ref` from facts_view if available.
5) Run a schema‑validation sanity check for the new payload fields.

### Tests planned (Phase 10)
- Minimal schema validation check for run_facts_view + run_ready_signal with `oracle_pack_ref`.

---

## Entry: 2026-01-28 20:16:42 — Phase 10 implemented (SR pack refs in READY + facts_view)

### Step‑by‑step decisions and changes
1) **Oracle Store schema wiring inside SR**
   - Added a dedicated schema registry pointing at `docs/model_spec/platform/contracts/oracle_store`.
   - Reason: pack manifest validation must use the authoritative Oracle Store schema (avoid ad‑hoc validation).

2) **Pack ref extraction + validation helper**
   - Implemented `_build_oracle_pack_ref(engine_run_root, intent)` that:
     - always includes `engine_run_root` when provided,
     - reads `_oracle_pack_manifest.json` if present,
     - validates it against `oracle_pack_manifest.schema.yaml`,
     - compares `world_key` pins to SR intent (manifest_fingerprint, parameter_hash, scenario_id, seed).
   - Failure modes:
     - invalid manifest → `ORACLE_PACK_INVALID` (fail‑closed)
     - pin mismatch → `ORACLE_PACK_MISMATCH` (fail‑closed)
   - Reason: WSP‑first runtime depends on accurate pack identity; SR must not READY if that identity is ambiguous or wrong.

3) **READY + facts view payload linking**
   - `_commit_ready` now takes the resolved `engine_run_root` (actual root used for evidence collection).
   - When pack refs are valid, SR adds `oracle_pack_ref` to:
     - `run_facts_view` (control‑plane join surface)
     - `run_ready_signal` (control trigger)
   - Reason: allow WSP/ops to correlate READY to a specific sealed world without making SR a data‑plane producer.

4) **Fail‑closed readiness on pack mismatch**
   - If pack manifest exists but fails validation or pin match, SR commits a terminal failure instead of READY.
   - Reason: control‑plane readiness must not point to a misidentified world.

5) **READY re‑emit parity**
   - Re‑emit now reuses `oracle_pack_ref` from stored `run_facts_view` when present.
   - Reason: re‑emit must preserve the same control‑plane ↔ data‑plane linkage without recomputation.

### Tests run (local)
- Schema validation sanity (run_facts_view + run_ready_signal with oracle_pack_ref):
  `@'... '@ | .\.venv\Scripts\python.exe -` → ok

---

## Entry: 2026-01-28 20:22:16 — Phase 11 implemented (SR WSP‑alignment validation)

### Step‑by‑step decisions and changes
1) **Direct pack‑ref validation tests**
   - Added `test_oracle_pack_ref.py` to validate SR’s `_build_oracle_pack_ref` behavior:
     - **valid manifest** → returns ref with pack id + engine_release,
     - **missing manifest** → returns ref with engine_run_root only,
     - **pin mismatch** → fails closed with `ORACLE_PACK_MISMATCH`.
   - Reason: Phase 11 focuses on alignment correctness without requiring full SR run integration.

2) **READY re‑emit compatibility check**
   - Extended `test_reemit_ready_publishes_control_fact` to include `oracle_pack_ref` in stored facts_view and assert it is preserved in READY re‑emit payloads.
   - Reason: ensure control-plane ↔ data-plane linkage remains stable across re‑emit operations.

3) **No data‑plane behavior changes**
   - Tests avoid invoking WSP/IG or scanning the engine; they validate **control‑plane correctness only**.
   - Reason: preserve component boundaries and avoid role creep.

### Tests run (local)
- `.\.venv\Scripts\python.exe -m pytest tests/services/scenario_runner/test_oracle_pack_ref.py tests/services/scenario_runner/test_reemit.py -q` → 9 passed.

---

## Entry: 2026-01-29 19:13:20 — Align SR local parity wiring to shared S3 bucket

### Trigger
Parity stack uses MinIO with `fraud-platform` bucket; SR wiring still pointed to `sr-local`, which adds an unnecessary bucket and ladder friction.

### Decision
Switch SR local parity + local Kinesis wiring to use the **same bucket** (`s3://fraud-platform`) as the platform object store.

### Change
- `config/platform/sr/wiring_local_kinesis.yaml`: `object_store_root: s3://fraud-platform`
- `config/platform/sr/wiring_local_parity.yaml`: `object_store_root: s3://fraud-platform`

---

## Entry: 2026-01-30 00:05:50 — SR artifacts moved to run‑first layout

### Decision
SR artifacts and refs now live under `fraud-platform/<platform_run_id>/sr/*` so each platform run is self‑contained.

### Changes
- `ScenarioRunner` ledger prefix now `fraud-platform/<platform_run_id>/sr`.
- Status/record/facts refs updated to the run‑scoped prefix.
- File control‑bus root rewritten to `runs/fraud-platform/<platform_run_id>/control_bus` when a run is active.
- CLI now requires an active platform run ID for non‑run commands (reemit/quarantine).

## Entry: 2026-01-29 19:32:10 — Parity SR authority store DSN alignment

### Trigger
Parity stack moved Postgres to 5434 and uses `platform:platform` credentials; SR parity wiring still pointed to legacy `sr:sr@5433`.

### Decision
Align SR parity wiring to the parity Postgres instance to avoid blocking on missing DB.

### Change
- `config/platform/sr/wiring_local_kinesis.yaml`: `authority_store_dsn` → `postgresql://platform:platform@localhost:5434/platform`
- `config/platform/sr/wiring_local_parity.yaml`: same update.

## Entry: 2026-01-29 19:33:40 — Fix SR S3 root to align run_facts_view refs

### Trigger
WSP READY consumer failed with `RUN_FACTS_INVALID` because SR wrote run_facts under an extra `sr/` prefix in S3.

### Decision
Align SR S3 root to the **bucket root** so SR’s relative refs (`fraud-platform/<platform_run_id>/sr/...`) resolve correctly for WSP.

### Change
- `config/platform/sr/wiring_local_kinesis.yaml`: `object_store_root: s3://fraud-platform`
- `config/platform/sr/wiring_local_parity.yaml`: `object_store_root: s3://fraud-platform`

---

## Entry: 2026-01-30 00:28:50 — SR local wiring uses run‑scoped authority store

### Trigger
Run‑first artifacts require SR authority/lease state to live under the active platform run, not a hard‑coded path.

### Decision trail (live)
- `authority_store_dsn` should be optional for local runs so SR can derive the path from `object_store_root + run_prefix`.
- This keeps per‑run authority state aligned with `runs/fraud-platform/<platform_run_id>/sr/index` and avoids stale global DBs.
- Tests should avoid writing to repo‑global paths by using explicit run prefixes.

### Implementation notes
- Removed the explicit `authority_store_dsn` from local wiring (`config/platform/sr/wiring_local.yaml`).
- SR defaults now create `sr/index/sr_authority.db` under the active run when DSN is not provided.
- SR tests now pass a deterministic `run_prefix` to keep artifacts under test roots.

### Files touched
- `config/platform/sr/wiring_local.yaml`
- `tests/services/scenario_runner/test_security_ops.py`
- `tests/services/scenario_runner/test_instance_proof_bridge.py`
- `tests/services/scenario_runner/test_parity_integration.py`

## Entry: 2026-01-31 13:42:00 — SR always uses Oracle Store (S3) + S3‑aware evidence verification (plan)

### Problem / goal
User requires SR to **always** read engine outputs from the Oracle Store (S3/MinIO) and never from local disk, so local runs match production. Current SR evidence + gate verification paths assume local `Path` access, so S3 roots break (or silently fall back). We need SR to treat `oracle_engine_run_root` as the canonical engine root and to verify gates, locators, and pack manifests directly from S3.

### Constraints / invariants
- Engine remains a black box (read‑only by‑ref).
- No‑PASS‑no‑read must remain enforced.
- SR truth artifacts stay in platform object store (`fraud-platform/<run_id>/sr/...`).
- No secrets in docs.

### Decision trail (live)
1) **Introduce `oracle_engine_run_root` in SR wiring** so SR can override request‑level `engine_run_root` and ensure S3/Oracle is always used.
   - Reason: request input may still point to local paths; wiring is the authority for environment truth.
2) **Make evidence/gate verification S3‑aware** by reading via `ObjectStore` instead of `Path`.
   - Reason: gate receipts, passed flags, and bundles exist in MinIO for parity/dev/prod. Local path logic is a ladder friction.
3) **Keep local path support** for unit tests and legacy runs, but prefer Oracle root when present.
   - Reason: avoid breaking tests and allow explicit fallback, while still defaulting to Oracle store.

### Planned mechanics
- Extend `WiringProfile` with optional `oracle_engine_run_root`.
- In `ScenarioRunner.submit_run`, override canonical intent’s `engine_run_root` with wiring’s `oracle_engine_run_root` when present; log when request root is ignored.
- Build an engine object store for the resolved engine root and pass it to evidence/gate verification.
- Update evidence + gate verification to use store for exists/read/digest.
- Update oracle pack manifest read to use store (S3) instead of `Path`.
- Update SR wiring files for local_parity/local_kinesis to set Oracle S3 root explicitly.
- Update runbook to state SR always uses Oracle Store and does not read local engine outputs.

### Validation plan
- Re‑run SR reuse path with `engine_run_root` pointing to S3 Oracle store and confirm READY completes without local path access.
- Gate verification tests should continue to pass for local Path roots.

---

## Entry: 2026-01-31 14:05:00 — SR Oracle‑first engine root + S3‑aware evidence verification (implemented)

### What changed
- Added `oracle_engine_run_root` to SR wiring and made SR **prefer it** over any request‑level engine root (oracle‑first).
- Made SR evidence collection + gate verification **S3‑aware** by reading engine artifacts via `ObjectStore` (MinIO/S3), not local `Path` only.
- Updated oracle pack manifest reads to use object store so `_oracle_pack_manifest.json` can live in S3.
- Updated `make platform-sr-run-reuse` to default `SR_ENGINE_RUN_ROOT` from `ORACLE_ENGINE_RUN_ROOT`.
- Updated runbook to document oracle‑first SR behavior.

### Decision trail (live)
- **Why override request root:** request values are operator input; wiring is the environment authority. This avoids local‑path drift and keeps parity with prod.
- **Why object store in gate verification:** passed flags, bundles, and index files are in Oracle Store (S3). Local‑only gate checks are a ladder friction.
- **Why keep local compatibility:** tests and non‑parity flows still use local paths; S3 is only required when root is `s3://`.

### Mechanics (explicit)
- `ScenarioRunner.submit_run` now resolves `engine_run_root = wiring.oracle_engine_run_root || request.engine_run_root`.
- `GateVerifier` accepts `engine_root` as string and uses S3 store for exists/read/digest when the root is `s3://`.
- Evidence locator scan uses store listing + wildcard matching for S3 and preserves local globbing for filesystem roots.
- Oracle pack manifest ref is built as `s3://.../_oracle_pack_manifest.json` when in S3.

### Files touched
- `src/fraud_detection/scenario_runner/config.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `src/fraud_detection/scenario_runner/evidence.py`
- `src/fraud_detection/scenario_runner/storage.py`
- `config/platform/sr/wiring_local*.yaml`, `config/platform/sr/wiring_aws.yaml`
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

### Tests
- `\.venv\Scripts\python.exe -m pytest tests/services/scenario_runner/test_gate_verifier.py -q` → 8 passed.

---

---

## Entry: 2026-01-31 18:43:00 — SR traffic output list aligned to behavioural streams

### Trigger
Engine interface now defines traffic policy: only 6B behavioural event streams are eligible for traffic.

### Reasoning (SR scope)
- SR traffic_output_ids drive READY planning and downstream traffic expectations.
- `arrival_events_5B` and 6B flow anchors are join surfaces; they must not be flagged as traffic outputs.
- `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B` are the canonical traffic streams.

### Decision
- Update `config/platform/sr/policy_v0.yaml` `traffic_output_ids` to the two 6B event streams.

### Planned edits
- Align SR policy with WSP allowlist and Oracle stream-view targets.

---

## Entry: 2026-02-05 14:05:51 — SR alignment to Control & Ingress run identity + READY idempotency

### Problem / goal
Align SR run_facts_view and READY control signal with Control & Ingress P0 pins: carry both `platform_run_id` and `scenario_run_id`, and derive READY idempotency from both run ids + bundle/plan hash. Add `run_config_digest` to READY for run-level policy pinning.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
- SR contracts under `docs/model_spec/platform/contracts/scenario_runner/`.
- Current SR impl_actual + build plan.

### Decisions (locked)
- Canonical dedupe run id is `platform_run_id`; SR must always carry `scenario_run_id` explicitly.
- READY `message_id` must be `sha256("ready|platform_run_id|scenario_run_id|bundle_hash_or_plan_hash")` (hex32).
- READY + run_facts_view must include `run_config_digest` when available.

### Planned implementation steps
- Update SR contract schemas: `run_ready_signal.schema.yaml`, `run_facts_view.schema.yaml` to require both run ids and add `run_config_digest`.
- Update SR model/serialization to include `platform_run_id` + `scenario_run_id` in facts view and READY payloads.
- Update READY idempotency key derivation in publish path.
- Add or surface run_config_digest (from policy digest) into READY.
- Add tests for READY idempotency and schema validation.

### Invariants
- READY emitted only after facts view is committed.
- No mutation of prior run facts (append-only).

### Validation plan
- Unit: READY idempotency key includes both run ids.
- Schema: READY + facts_view validate with new fields.

---
