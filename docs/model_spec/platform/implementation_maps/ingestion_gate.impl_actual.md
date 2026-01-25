# Ingestion Gate Implementation Map
_As of 2026-01-25_

---

## Entry: 2026-01-25 06:07:06 — IG v0 planning start

### Problem / goal
Stand up the Ingestion Gate (IG) as the platform’s admission authority. IG must validate canonical envelopes, enforce schema + lineage + gate policies, stamp deterministic partition keys, append to EB, and emit receipts/quarantine evidence by‑ref.

### Authorities / inputs (binding)
- Root AGENTS.md (rails: ContextPins, no‑PASS‑no‑read, by‑ref, idempotency, append‑only, fail‑closed).
- Platform rails/substrate docs (platform_rails_and_substrate_v0.md, by‑ref validation checklist, partitioning policy guidance).
- Engine interface pack contracts (canonical_event_envelope, gate_receipt, engine_output_locator, instance_proof_receipt).
- IG design‑authority doc (component‑specific).

### Decision trail (initial)
- IG plan must be component‑scoped and progressive‑elaboration; Phase 1 broken into envelope/schema, gate verification, idempotency, partitioning, and receipt/quarantine storage.
- IG must never become a “transformer”; it validates and admits only, emitting receipts with by‑ref evidence.
- Partitioning policy is explicit and versioned (`partitioning_profile_id`), with IG stamping partition_key; EB never infers routing.

### Planned mechanics (Phase 1 focus)
- **Envelope validation:** validate canonical envelope + versioned payload schema with allowlist policy.
- **Lineage + gate checks:** verify required PASS gates via SR join surface; fail‑closed on missing/invalid evidence.
- **Idempotency:** deterministic dedupe key; duplicates return original EB ref/receipt.
- **EB append:** admitted only when EB returns `(stream, partition, offset)`; receipts record EB ref.
- **Quarantine:** store evidence by‑ref under `ig/quarantine/` with reason codes.

### Open items / risks
- Exact schema for IG receipts and quarantine records (must align with platform pins and avoid secret material).
- Policy format for schema acceptance and partitioning profiles (initial stubs exist; may need expansion).

---

## Entry: 2026-01-25 06:18:07 — IG Phase 1 implementation plan (component scope)

### Problem / goal
Implement IG Phase 1 admission boundary: schema + lineage + gate verification, idempotent admission, deterministic partitioning, and receipts/quarantine by‑ref. This is the minimal production‑shaped IG that can ingest engine traffic (pull) and producer traffic (push) under the same outcome semantics.

### Inputs / authorities
- IG design‑authority doc (pinned overview + joins; push + pull ingestion modes).
- Platform rails/substrate docs (canonical envelope, by‑ref validation checklist, partitioning policy guidance, secrets posture).
- Engine interface pack contracts + catalogue (canonical envelope, engine_output_locator, gate_receipt, instance_proof_receipt, engine_outputs.catalogue.yaml roles).
- Platform contracts index + profiles (`config/platform/profiles/*`, `config/platform/ig/partitioning_profiles_v0.yaml`).

### Live decisions / reasoning
- **No engine streaming assumption.** IG supports **push ingestion** (producers already framed) and **pull ingestion** (engine outputs after SR READY). Pulling from engine outputs does *not* require engine to stream; v0 can frame from materialized outputs referenced by `sr/run_facts_view`.
- **Single admission spine.** Both push and pull modes must converge into the same admission pipeline so receipts, dedupe, partitioning, and EB semantics remain identical.
- **Component layout.** Create a new `src/fraud_detection/ingestion_gate/` package and a thin service wrapper under `services/ingestion_gate/` for consistency with SR; leave legacy `services/ingestion/` untouched as placeholder.
- **Deterministic identity.** If upstream payload lacks `event_id`, IG must derive a deterministic `event_id` from stable keys + pins (for engine rows, use output_id + primary keys + pins).
- **Partitioning is policy.** IG uses `partitioning_profiles_v0.yaml`; no inference by EB or ad‑hoc selection in code.

### Planned implementation steps (Phase 1)
1) **Contracts + policy stubs**
   - Add `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`.
   - Add `docs/model_spec/platform/contracts/ingestion_gate/quarantine_record.schema.yaml` (by‑ref evidence pointers + reason codes).
   - Add `config/platform/ig/schema_policy_v0.yaml` (allowlist per event_type/version + class).
   - Add `config/platform/ig/class_map_v0.yaml` (event_type → class: traffic/control/audit; required pins).

2) **Core package skeleton (src)**
   - `src/fraud_detection/ingestion_gate/models.py` (Envelope, AdmissionDecision, Receipt, QuarantineRecord).
   - `src/fraud_detection/ingestion_gate/schema.py` (canonical envelope validation + payload schema policy).
   - `src/fraud_detection/ingestion_gate/partitioning.py` (partition_key derivation from profile).
   - `src/fraud_detection/ingestion_gate/dedupe.py` (dedupe key, deterministic event_id derivation).
   - `src/fraud_detection/ingestion_gate/engine_pull.py` (read SR run_facts_view → fetch engine traffic outputs → frame rows to canonical envelope).
   - `src/fraud_detection/ingestion_gate/admission.py` (single admission spine: validate → gate check → dedupe → partition → EB append → receipt).
   - `src/fraud_detection/ingestion_gate/receipts.py` (write receipts/quarantine by‑ref to object store).
   - `src/fraud_detection/ingestion_gate/store.py` (object store + optional receipt index abstraction; local FS and S3 variants).

3) **Service wrapper + CLI**
   - `services/ingestion_gate/` minimal HTTP endpoint for push ingestion and a CLI/runner for pull ingestion.

4) **Tests**
   - Unit: envelope validation, schema allowlist, partitioning determinism, dedupe key derivation.
   - Integration: pull ingestion from engine artifacts (use local_full_run fixture), verify gate enforcement and receipt writing.
   - EB publish stub tests (LocalStack/Kinesis) for admission ACK semantics.

### Invariants to enforce (explicit)
- **No PASS → no read** (missing/invalid gate evidence = quarantine/waiting).
- **ADMITTED iff EB acked** and `(stream, partition, offset)` exists in receipt.
- **Deterministic partitioning** from policy profiles only.
- **Receipts/quarantine are by‑ref** and never contain secret material.

### Open items / risks
- Receipt/quarantine schemas must align with platform pins and avoid payload bloat.
- Push ingestion authN/authZ profile (allowlists) to be pinned for prod; v0 can be permissive but must be explicit.

---

## Entry: 2026-01-25 07:19:11 — IG Phase 1 implementation execution (admission spine hardening)

### Problem / goal
Harden IG Phase 1 implementation so the admission boundary is deterministic, auditable, and aligned with the platform rails: canonical envelope validation, policy‑driven schema enforcement, no‑PASS‑no‑read, idempotency, deterministic partitioning, and by‑ref receipts/quarantine.

### Observations (current state)
- `_admit_event` has a control‑flow bug: the duplicate path returns early, and the normal admission path is unreachable; when no duplicate exists, `decision` is undefined.
- IG wiring currently assumes an IG‑specific profile shape, but the CLI points at `config/platform/profiles/*.yaml` (platform profile shape). This can mis‑resolve `object_store_root` and event bus settings.
- Gate verification currently only checks `run_facts_view.gate_receipts` status and does not enforce instance‑proof receipts for instance‑scoped outputs.
- Reason codes are raw exception strings; they are not normalized or safe for operator‑level debugging.

### Decision trail (live)
- **Dedupe semantics:** Duplicates must not append to EB. IG will return a DUPLICATE receipt that **references the original EB coordinates** and (when available) the **original receipt ref** as evidence. Receipts are written with **write‑once** semantics to preserve append‑only truth.
- **Reason codes:** Introduce a small internal reason‑code taxonomy and a dedicated `IngestionError` to carry a stable `code` + optional detail. Quarantine receipts will record **only the stable reason code**; details remain in logs to avoid leaking sensitive content.
- **Gate + instance verification:** For v0, IG will **require PASS receipts** from `run_facts_view` for required gates **and** instance‑proof receipts for instance‑scoped outputs. This satisfies “no PASS → no read” while keeping the engine a black box. Full re‑hash verification can be layered later when a stable `engine_root` is configured.
- **Required gate set expansion:** Use `read_requires_gates` from the catalogue when present; otherwise derive required gates from `engine_gates.map.yaml` and include upstream dependencies.
- **Instance scope detection:** Use output `scope` (catalogue field) to detect instance‑scoped outputs (seed/parameter_hash/scenario_id/run_id tokens) and enforce instance receipts accordingly.
- **Partitioning → topic selection:** Derive EB topic from the **partitioning profile** (policy) rather than hard‑coding topic names in code.
- **Profile parsing:** Extend IG wiring loader to accept the **platform profile shape** (object_store bucket + endpoint). When an endpoint is present, map to `s3://{bucket}` and pass endpoint/region/path‑style into the object store builder.

### Planned edits (stepwise)
1) Fix `_admit_event` control‑flow; implement explicit duplicate path; gate EB publish only on non‑duplicate; write receipts immutably; record admissions in the idempotency index.
2) Add `ingestion_gate/errors.py` with `IngestionError` + reason‑code constants; update schema/pins/gate/partition checks to raise stable codes and keep details in logs.
3) Extend `OutputCatalogue` to load `scope`; add an `is_instance_scope()` helper in IG to enforce instance‑proof receipts.
4) Implement gate + instance verification against `run_facts_view` receipts; include required gate expansion via the gate map.
5) Use partitioning profile stream as the EB topic; add narrative logging at each admission phase (validate → verify → dedupe → partition → publish → receipt).
6) Update `WiringProfile` to support platform profile shape and propagate object‑store endpoint settings.
7) Add unit tests for: duplicate idempotency; missing gate PASS; missing instance receipt; partitioning‑driven topic selection.

---

## Entry: 2026-01-25 07:30:47 — IG Phase 1 implementation progress (code + tests)

### Implementation decisions applied
- **Admission spine fix:** rewired `_admit_event` to separate duplicate vs admit paths; duplicates now return a receipt with the original EB ref and optional receipt ref evidence, without re‑publishing to EB.
- **Reason‑code handling:** added `ingestion_gate/errors.py` (`IngestionError` + `reason_code`) and updated schema/pins/gate/partitioning to raise stable codes instead of raw exceptions.
- **Gate/instance enforcement:** expanded required gate set via `engine_gates.map.yaml` (filtered to `required_by_components: ingestion_gate`) when catalogue lacks explicit requirements; enforced instance‑proof receipts for instance‑scoped outputs (scope token detection).
- **Partitioning → topic:** EB topic is now derived from the selected partitioning profile’s `stream` (policy‑driven; no hard‑coded topic strings).
- **Wiring alignment:** IG wiring now accepts the platform profile shape and maps object store buckets to `s3://` roots when endpoints are configured; admission index is stored locally via `admission_db_path` even when the object store is remote.
- **Narrative logging:** added clear log statements at intake, validation, gate check, duplicate detection, publish, and quarantine for operator‑readable traces.

### Files touched / created (code)
- `src/fraud_detection/ingestion_gate/admission.py`: fixed duplicate/admit flow, added gate + instance checks, pruning of optional pins, and narrative logs.
- `src/fraud_detection/ingestion_gate/errors.py`: stable error taxonomy and reason extraction.
- `src/fraud_detection/ingestion_gate/gates.py`: gate map parser + required gate expansion.
- `src/fraud_detection/ingestion_gate/scopes.py`: instance‑scope detector.
- `src/fraud_detection/ingestion_gate/catalogue.py`: load `scope` field.
- `src/fraud_detection/ingestion_gate/partitioning.py`: stable error codes on missing/unsupported keys.
- `src/fraud_detection/ingestion_gate/ids.py`: stable error codes on missing primary keys.
- `src/fraud_detection/ingestion_gate/engine_pull.py`: narrative logging + stable errors for missing event time.
- `src/fraud_detection/ingestion_gate/config.py`: accept platform profile shape; add admission DB path and object‑store endpoint fields.
- `src/fraud_detection/ingestion_gate/receipts.py`: write‑once receipt/quarantine semantics.
- `src/fraud_detection/ingestion_gate/cli.py`: consistent logging for CLI runs.

### Tests added / results
- **Added:** `tests/services/ingestion_gate/test_admission.py`
  - duplicate does not republish (EB log stays 1 line)
  - missing gate PASS → quarantine
  - missing instance receipt → quarantine
- **Test run:** `python -m pytest tests/services/ingestion_gate/test_admission.py -q`
  - Initial failure due to `None` pins violating receipt schema; fixed by pruning `None` values in receipt/quarantine payloads.
  - Final result: **3 passed**.

### Follow‑ups / open edges
- Push‑ingest run joinability is still policy‑only (pins enforced but no SR readiness lookup yet).
- Full gate re‑hash verification (reading engine artifacts) remains a later hardening step when a stable `engine_root` configuration is introduced.

---

## Entry: 2026-01-25 07:30:47 — IG Phase 1 continuation (run joinability + optional gate re‑hash)

### Problem / goal
Close remaining Phase‑1 gaps: make push‑ingest run‑scoped events join to SR READY + run_facts_view, and optionally hard‑verify gate artifacts when a local engine root is configured. Both must preserve black‑box constraints and fail‑closed posture.

### Decision trail (live)
- **Run joinability for push:** If an event class is run‑scoped (pins require any of `run_id`, `scenario_id`, `parameter_hash`, `seed`), IG must check SR readiness before admission. This avoids admitting run‑scoped events into EB when the run context is not anchored.
- **SR lookup path:** Use SR ledger paths under a configurable prefix (`sr_ledger_prefix`, default `fraud-platform/sr`). Read `run_status/{run_id}.json`, require `state == READY`, then follow `facts_view_ref` (or default to `run_facts_view/{run_id}.json`). This preserves the “no scan, no latest” rule.
- **Run pin consistency:** When a READY run is found, validate envelope pins against run_facts pins (manifest_fingerprint, parameter_hash, seed, scenario_id, run_id). Any mismatch is quarantine.
- **Gate re‑hash verification (optional):** If `engine_root_path` is configured, IG performs an additional gate‑artifact check using the engine’s gate map and verification method. This is a defensive integrity check layered on top of `run_facts_view` receipts. If it fails/misses, IG quarantines with a stable reason code.
- **Black‑box respected:** No changes to engine code; verification reads only artifacts by path from the engine root when configured. If not configured, IG relies on run_facts receipts only.

### Implementation changes (stepwise)
1) Extend `WiringProfile` to include `sr_ledger_prefix` (default `fraud-platform/sr`) and optional `engine_root_path` (enable gate re‑hash).
2) Add `_ensure_run_ready()` and `_verify_run_pins()` to enforce SR READY + pin equality for run‑scoped push events.
3) Add optional gate artifact verification in `_verify_required_gates()` using `GateVerifier` when `engine_root_path` is set.
4) Add tests: push events quarantine when run is not READY; gate re‑hash verification passes when artifacts match.

---

## Entry: 2026-01-25 07:41:05 — IG Phase 1 completion (joinability + gate re‑hash)

### Implementation decisions applied
- **Run joinability enforcement:** IG now checks SR `run_status` + `run_facts_view` for run‑scoped push events (based on required pins). Missing status, non‑READY state, or pin mismatches are quarantine‑level errors.
- **Optional gate re‑hash:** When `engine_root_path` is provided, IG verifies gate artifacts using the engine’s gate map/verification method in addition to run_facts receipts. This is a defensive integrity check; if artifacts are missing or conflict, IG quarantines.
- **Wiring extensions:** Added `sr_ledger_prefix` and `engine_root_path` to IG wiring, keeping defaults safe for local use and preserving black‑box posture when unset.
- **Test‑driven sanity:** The run‑scoped check is triggered by required pins; tests explicitly configure required pins to exercise the joinability path.

### Files updated
- `src/fraud_detection/ingestion_gate/config.py`: added `sr_ledger_prefix`, `engine_root_path`.
- `src/fraud_detection/ingestion_gate/admission.py`: SR READY lookup + pin match, optional gate re‑hash verification, and required‑pin run‑scope detection.
- `tests/services/ingestion_gate/test_admission.py`: added tests for push joinability and gate re‑hash, plus helper for gate artifacts.

### Tests run / outcomes
- **Command:** `python -m pytest tests/services/ingestion_gate/test_admission.py -q`
  - First run: push‑joinability test did not trigger because the class_map required pins were too permissive.
  - Fix: allow tests to specify run‑scoped required pins explicitly.
  - Final result: **5 passed**.

---

## Entry: 2026-01-25 07:41:51 — IG hardening tweak (gate verifier availability)

### Decision / rationale
If `engine_root_path` is configured, IG must **fail fast** when the gate verifier dependency cannot be loaded. Silent fallback would weaken the intended integrity check and violate fail‑closed posture.

### Change applied
- `IngestionGate.build` now raises `GATE_VERIFIER_UNAVAILABLE` if `engine_root_path` is set but the verifier cannot be imported.

---

## Entry: 2026-01-25 07:49:58 — IG Phase 2 planning (control plane + ops hardening)

### Problem / goal
Phase 2 turns IG from a strict admission boundary into an **operationally safe** service: it must be queryable, observable, and resilient under dependency failures without violating rails (no silent drop, no PASS→no read, append‑only truth).

### Authorities / inputs
- Root AGENTS rails + platform doctrine (idempotency, append‑only truth, fail‑closed).
- IG design‑authority (M10 ops surfaces; J19 ingress control; governance facts).
- Platform profiles + policy split (policy vs wiring).
- SR ledger conventions (run_status / run_facts_view; READY gating).

### Live reasoning (detail trail)
- **Policy attribution is mandatory**: we already stamp `policy_id`+`revision` but **content_digest** is missing. Without digest, downstream cannot prove the exact policy bundle.  
  Options considered:
  1) Hardcode digest in config → fragile and easy to drift.
  2) Compute digest from a fixed set of policy files at runtime (preferred).
  Decision: compute digest at IG startup from `schema_policy`, `class_map`, `partitioning_profiles` (and any IG‑specific policy docs); stamp into `policy_rev.content_digest`. This keeps receipts auditable without introducing secrets.

- **Ops surfaces must not scan EB/object store**: receipt lookup needs a DB‑backed index.  
  Options:
  1) Extend existing `AdmissionIndex` DB with new tables for receipts/quarantine (preferred: fewer DBs).
  2) New ops DB (cleaner separation, but more moving parts).
  Decision: extend the current SQLite index with `receipts` and `quarantines` tables; keep schema append‑only. The object store remains the evidence authority; DB is a query cache, not truth.

- **Ingress control cannot be implicit**: if EB or object store is unhealthy, IG must throttle or pause intake rather than admit and fail later.  
  Minimal Phase‑2 approach:
  - A `HealthProbe` that checks: object‑store write (receipt/quarantine), EB publish readiness, and DB availability.
  - Map probe results to `GREEN|AMBER|RED`; RED causes intake refusal; AMBER may log throttling decisions.
  - Emit explicit state‑change logs with reason codes.

- **Observability must be narrative + structured**: Phase‑1 added narrative logs, but Phase‑2 must also produce counters and latencies.  
  Approach: in‑process counters with periodic log flush (no new deps). Keep OTel as a later enhancement once the metrics surface is stable. Metrics tags include `decision`, `event_type`, `policy_rev`, and run pins where available.

- **Governance facts**: policy change and quarantine spikes should emit to audit/control streams.  
  For v0: define a small `ig_audit_event` payload and emit on:
  - policy activation (new digest)
  - quarantine spike (thresholded rate)
  Emission uses existing EB publisher (audit/control topic).

### Proposed Phase‑2 mechanics (stepwise)
1) **Policy digesting**
   - Add a `PolicyDigest` helper to compute sha256 over the resolved policy bundle (schema_policy + class_map + partitioning_profiles + optional IG policy YAML).
   - Include `content_digest` in `policy_rev` and in logs/metrics.

2) **Ops index**
   - Extend `AdmissionIndex` or add `OpsIndex` with:
     - `receipts` table: receipt_id, event_id, event_type, dedupe_key, decision, eb_ref, pins, policy_rev, created_at_utc, receipt_ref.
     - `quarantines` table: quarantine_id, event_id, reason_codes, pins, evidence_ref, created_at_utc.
   - Insert records on every decision path (ADMIT/DUPLICATE/QUARANTINE).
   - Provide a small CLI query (`ig ops lookup --event-id/--receipt-id`) without secrets.

3) **Health + ingress control**
   - Add `IGHealthState` computation that checks:
     - object store write probe (write‑once sentinel)
     - EB publish probe (no‑op or test append for file bus)
     - DB availability (simple SELECT/PRAGMA)
   - Enforce: RED → refuse intake; AMBER → log throttle recommendation.

4) **Observability + governance facts**
   - Add in‑process counters + latencies; flush to logs at interval.
   - Emit governance events to `fp.bus.audit.v1` on policy change and quarantine spikes.

### Invariants to enforce (Phase‑2)
- No ingestion proceeds when dependencies are unhealthy (fail‑closed).
- Indexes are append‑only mirrors of receipt/quarantine objects; never authoritative over object store.
- Governance facts are additive and do not alter admission outcomes.

### Implementation notes (paths)
- `src/fraud_detection/ingestion_gate/ops_index.py` (new)
- `src/fraud_detection/ingestion_gate/policy_digest.py` (new)
- `src/fraud_detection/ingestion_gate/health.py` (new)
- `src/fraud_detection/ingestion_gate/metrics.py` (new)
- CLI extension under `src/fraud_detection/ingestion_gate/cli.py`

### Testing plan (Phase‑2)
- Unit: policy digest reproducibility; ops index insert/query; health state transitions.
- Integration: simulate EB failure → intake refuses; quarantine spike emits audit event; policy digest stamped in receipts.

---

## Entry: 2026-01-25 07:52:12 — IG Phase 2 implementation start (ops hardening)

### Implementation intent (before coding)
Proceed section‑by‑section (2.1→2.4) with hardened behavior and tests. Priority order:
1) Policy digesting + policy_rev stamping (content_digest).
2) Ops index tables + lookup surface (CLI).
3) Health probe + ingress control gating (fail‑closed on RED).
4) Metrics + governance facts (policy activation, quarantine spikes).

### Non‑negotiables carried into implementation
- No secrets in docs/logs/receipts.
- Fail‑closed posture for readiness/compatibility.
- Append‑only truth in object store; DB is a query cache only.
- Avoid adding heavy dependencies; use stdlib where possible.

### Implementation notes (pre‑commit decisions)
- Compute policy digest from **resolved policy artifacts**: `schema_policy`, `class_map`, `partitioning_profiles`. Use canonical JSON dumps with sorted keys for deterministic hashing.
- Extend IG SQLite DB (same file as admission index) with ops tables; writes must be **idempotent** (`INSERT OR IGNORE`).
- Health probe should be **rate‑limited** (avoid probing dependencies on every event). Cache last result for a configurable interval.
- Governance events are emitted using the existing EB publisher on the **audit** stream, using a canonical envelope with a synthetic manifest fingerprint (`0`*64).

---

## Entry: 2026-01-25 08:02:18 — IG Phase 2 implementation progress (policy digest + ops surfaces)

### Implementation decisions applied
- **Policy digesting** implemented as deterministic sha256 over canonical JSON dumps of `schema_policy`, `class_map`, and `partitioning_profiles`. The resulting digest is stamped into `policy_rev.content_digest` on every receipt/quarantine.
- **Policy activation governance** emits a canonical audit event (`ig.policy.activation`) only when the stored active digest changes; state is tracked in object store at `fraud-platform/ig/policy/active.json`.
- **Ops index** added as an append‑only SQLite mirror for receipts/quarantine (`OpsIndex`); this is a query cache, not authority.
- **Health probe** added with a cached probe interval. Object store + ops DB failures yield RED health (fail‑closed). Bus health is AMBER if unknown.
- **Metrics recorder** added for per‑decision counters and admission latencies; periodically flushed to logs for observability.
- **Quarantine spikes** emit audit events on thresholded counts within the configured window.
- **CLI** extended with receipt lookup + health probe output.

### Files added / updated
- Added: `src/fraud_detection/ingestion_gate/policy_digest.py`
- Added: `src/fraud_detection/ingestion_gate/ops_index.py`
- Added: `src/fraud_detection/ingestion_gate/health.py`
- Added: `src/fraud_detection/ingestion_gate/metrics.py`
- Added: `src/fraud_detection/ingestion_gate/governance.py`
- Updated: `src/fraud_detection/ingestion_gate/admission.py` (health gating, ops index writes, metrics, governance)
- Updated: `src/fraud_detection/ingestion_gate/config.py` (health/metrics/quarantine thresholds)
- Updated: `src/fraud_detection/ingestion_gate/cli.py` (ops lookups + health)

### Tests added / adjusted
- Added `tests/services/ingestion_gate/test_ops_index.py` (policy digest determinism + ops index probe).
- Extended `tests/services/ingestion_gate/test_admission.py` for Phase‑2 wiring fields.
- Fix applied: include `ig.partitioning.v0.audit` in test partitioning profiles so policy activation audit emission can route.

### Test results
- `python -m pytest tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_ops_index.py -q`
  - Initial failures due to missing audit partition profile in test fixtures.
  - Fixed by adding audit profile to test partitioning profile.
  - Final result: **7 passed**.
