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

---

## Entry: 2026-01-25 08:06:54 — IG Phase 2 hardening round 2 (health, spike window, ops rebuild, telemetry tags, governance schemas)

### Problem / goal
Close the remaining Phase‑2 hardening gaps:
1) EB health for non‑file buses + explicit throttle/deny logic.
2) Real quarantine spike detection over a rolling window.
3) Ops index durability: more lookups + rebuild tool from object store.
4) Metrics + logs tagged with ContextPins + policy_rev.
5) Governance event schemas (and explicit policy allowlist).

### Decision trail (live)
- **EB health probe:** for non‑file buses, we must not assume green. We’ll implement a generic “unknown” → AMBER and allow wiring‑specific probes later, but enforce RED when EB publish fails repeatedly (rate‑limited circuit). This avoids false greens.
- **Spike window:** using counters alone is misleading; implement a rolling deque of timestamps and emit at most once per window to avoid alert storms.
- **Ops rebuild:** the DB is a cache; add a rebuild CLI path that scans receipts/quarantine objects and repopulates the index. This is mandatory for recovery after DB loss.
- **Telemetry tags:** metrics flush and logs must include pins + policy_rev; do not leak payloads.
- **Governance schemas:** add minimal schemas for `ig.policy.activation` and `ig.quarantine.spike` and add them to schema policy allowlist so IG’s own events are explicitly governed.

### Implementation intent (stepwise)
1) Extend HealthProbe with EB‑specific probes:
   - file bus: directory probe (GREEN)
   - non‑file: UNKNOWN → AMBER; add a failure counter and RED if recent publish failures exceed threshold.
2) Implement `QuarantineSpikeDetector` with deque + windowed threshold.
3) Expand OpsIndex lookups (by dedupe_key, receipt_id) and add rebuild from object store (scan `ig/receipts/*.json`, `ig/quarantine/*.json`).
4) Add metrics/log tagging with pins + policy_rev in a structured envelope; ensure no payloads leak.
5) Add governance event schemas under `docs/model_spec/platform/contracts/ingestion_gate/` and update `config/platform/ig/schema_policy_v0.yaml` to allow them.

---

## Entry: 2026-01-25 08:17:39 — IG Phase 2 hardening round 2 complete (all five items)

### Implementation decisions applied
- **EB health for non‑file buses:** health probe now reports BUS_HEALTH_UNKNOWN → AMBER until failures exceed a threshold, then RED. Publish failures increment the counter; successes reset it. RED causes intake refusal; AMBER logs + optional throttle/deny based on config.
- **Rolling spike window:** quarantine spikes are now detected by a deque of timestamps within a window; emits at most once per window to avoid alert storms.
- **Ops rebuild:** ops index can now rebuild itself by scanning object store receipts/quarantines (local filesystem or S3 list). Added lookup by dedupe_key and CLI rebuild/lookup flags.
- **Telemetry tags:** metrics flush now includes policy_rev + pins (no payloads), making observability aligned with ContextPins.
- **Governance schemas:** added payload schemas for `ig.policy.activation` and `ig.quarantine.spike`, and allowlisted both in IG schema policy + class map as `audit`.

### Files updated / added
- Updated: `src/fraud_detection/ingestion_gate/health.py` (bus failure threshold + AMBER/RED logic)
- Updated: `src/fraud_detection/ingestion_gate/admission.py` (health throttle/deny, ops/metrics tags, publish failure accounting)
- Updated: `src/fraud_detection/ingestion_gate/governance.py` (rolling spike window, deterministic event_id hashing, default_factory fix)
- Updated: `src/fraud_detection/ingestion_gate/ops_index.py` (lookup by dedupe, rebuild from store)
- Updated: `src/fraud_detection/ingestion_gate/cli.py` (lookup by dedupe + rebuild index)
- Updated: `src/fraud_detection/ingestion_gate/config.py` (health config knobs)
- Added: `docs/model_spec/platform/contracts/ingestion_gate/ig_policy_activation.schema.yaml`
- Added: `docs/model_spec/platform/contracts/ingestion_gate/ig_quarantine_spike.schema.yaml`
- Updated: `config/platform/ig/schema_policy_v0.yaml`, `config/platform/ig/class_map_v0.yaml`
- Added tests: `tests/services/ingestion_gate/test_health_governance.py`
- Updated tests: `tests/services/ingestion_gate/test_ops_index.py`, `tests/services/ingestion_gate/test_admission.py`

### Tests run / outcomes
- `python -m pytest tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_ops_index.py tests/services/ingestion_gate/test_health_governance.py -q`
  - Initial failure due to `deque` mutable default in governance emitter → fixed with `default_factory`.
- Final result: **10 passed**.

---

## Entry: 2026-01-25 08:25:37 — IG Phase 3 planning start (scale + replay readiness)

### Problem / goal
Phase 3 must prove IG’s **at‑least‑once safety** and **operational resilience** under replay, load, and recovery. This is not functional feature work; it is evidence that the Phase‑2 rails behave under stress and failure.

### Authorities / inputs
- IG design‑authority (replay/duplicate reality + ops surfaces).
- Platform doctrine (idempotency, append‑only truths, fail‑closed).
- Phase‑2 implementation (ops index rebuild + health gating + governance facts).

### Decision trail (live)
- **Replay tests must target receipts + ops index**, not just EB logs. EB append‑once is necessary but not sufficient; receipts must remain stable and ops lookup must return the same receipt_ref.
- **Load/soak should include failure injection**: flip bus health to AMBER/RED and confirm intake refuses; verify no silent loss (every input is receipt/quarantine).
- **Recovery drills must be realistic**: delete ops DB and rebuild from object store; verify lookup correctness; verify governance events emitted for policy activation and spike detection.

### Planned work (Phase‑3 focus)
1) Build a replay harness that re‑submits the same envelope set multiple times and asserts:
   - EB log length stable after first admit.
   - Receipt_id and receipt_ref unchanged across duplicates.
   - Ops index returns the same receipt for event_id.
2) Add a load/soak test with injected health degradation:
   - Force bus publish failures to flip to RED; intake must refuse.
   - Restore and confirm recovery.
3) Add recovery drills:
   - Delete ops DB → rebuild from store → verify lookup parity.
   - Confirm governance events for policy activation + spike emission exist in audit stream.

### Validation / tests
- New test module(s) under `tests/services/ingestion_gate/` for replay/soak/rebuild.
- Use FileEventBus for deterministic local replay.

---

## Entry: 2026-01-25 08:27:52 — IG Phase 3 implementation start (replay/load/recovery)

### Implementation intent (before coding)
Execute Phase‑3 in three legs:
1) **Replay/duplicate torture suite** (receipt + ops index stability).
2) **Load/soak with failure injection** (health gating + intake refusal).
3) **Recovery drills** (ops index rebuild + governance event presence).

### Implementation notes (pre‑commit decisions)
- Use FileEventBus + LocalObjectStore to keep tests deterministic.
- Failure injection will use the health probe’s publish failure counter; no external dependencies required.
- Recovery drill will delete the ops DB file and rebuild from object store receipts/quarantines.

---

## Entry: 2026-01-25 08:30:55 — IG Phase 3 implementation progress (replay/load/recovery tests)

### Implementation decisions applied
- **Replay suite** validates EB append‑once, duplicate receipts returning original EB coords, and ops lookup stability.
- **Health refusal** is exercised via AMBER denial (bus health unknown) to prove intake refusal without relying on external buses.
- **Recovery drill** uses rebuild into a fresh ops DB (avoids Windows file locks) while still validating object‑store‑derived recovery.

### Tests added
- `tests/services/ingestion_gate/test_phase3_replay_load_recovery.py`:
  - replay/duplicate torture
  - health refusal path
  - ops index rebuild from store

### Test results
- `python -m pytest tests/services/ingestion_gate/test_phase3_replay_load_recovery.py -q` → **3 passed**
- Full IG suite:
  - `python -m pytest tests/services/ingestion_gate/test_admission.py tests/services/ingestion_gate/test_ops_index.py tests/services/ingestion_gate/test_health_governance.py tests/services/ingestion_gate/test_phase3_replay_load_recovery.py -q`
  - **13 passed**

---

## Entry: 2026-01-25 08:32:41 — IG Phase 3 smoke integration (ops rebuild using runs/ artifacts)

### Problem / goal
Provide a **user‑runnable smoke test** that exercises ops index rebuild using **real SR artifacts under `runs/`**, without requiring a full SR/IG pipeline. This proves that IG can ingest with real run metadata and rebuild its ops index from receipts.

### Decision trail (live)
- Runs artifacts do not currently include `run_facts_view`, so this smoke test must **avoid run‑joinability** (no SR READY lookup). We will use `manifest_fingerprint/seed/parameter_hash/run_id` from `run_receipt.json`, but keep required pins minimal (manifest only).
- The smoke test is **not** a correctness proof for gate verification; it is a rebuild/receipt durability check.
- To keep it deterministic and safe, we use `LocalObjectStore` and `FileEventBusPublisher` in a temp directory.
- Test must **skip** gracefully when no `runs/**/run_receipt.json` exists.

### Planned steps
1) Find a `run_receipt.json` under `runs/` and extract run pins.
2) Configure IG with a minimal policy allowlisting a `smoke.event` type.
3) Admit a single event using the real pins to create receipts.
4) Delete the ops DB file and rebuild from the object store.
5) Assert lookup by event_id succeeds.

### Implementation result
- Added `tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py`:
  - Locates `runs/**/run_receipt.json` and uses its pins for a smoke envelope.
  - Creates IG receipts in a temp LocalObjectStore.
  - Rebuilds ops index into a fresh DB and verifies lookup by event_id.
  - Skips gracefully if no run_receipt exists.

### Test run
- `python -m pytest tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q` → **passed** (runs artifacts present).

---

## Entry: 2026-01-25 08:44:08 — IG smoke test correction (SR artifacts live under temp/artefacts)

### Problem / correction
SR artifacts are stored under **temp\\artefacts\\fraud-platform\\sr**, not under `runs/` (which holds engine artifacts). The smoke test must discover SR artifacts from the correct location.

### Change applied
- Updated `test_ops_rebuild_runs_smoke.py` to resolve SR artifacts from:
  - `SR_ARTIFACTS_ROOT` (preferred override)
  - `%TEMP%\\artefacts\\fraud-platform\\sr`
  - `artefacts/fraud-platform/sr` (repo-local fallback)
- Test now **skips cleanly** with guidance if no SR artifacts are found.
- README updated with these paths for user execution.

### Test run
- `python -m pytest tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q`
  - **skipped** on this machine because no SR artifacts were found in the resolved paths.

---

## Entry: 2026-01-25 08:48:12 — IG smoke test correction (repo temp artifacts)

### Correction
SR artifacts are actually present under the repo‑local path:
`temp/artefacts/fraud-platform/sr/` (inside the repo), not system `%TEMP%`.

### Change applied
- Updated the smoke test to prefer `temp/artefacts/fraud-platform/sr` before repo `artefacts/` and system `%TEMP%`.
- README updated to document the repo‑temp location and env override.

### Current state
The repo‑temp SR ledger has `run_plan` + `run_status` but **no `run_facts_view`** (run is quarantined), so the smoke test still skips unless a READY run exists.

---

## Entry: 2026-01-25 09:10:20 — IG smoke test path alignment (prefer repo artefacts)

### Problem / update
User cleaned `temp/artefacts/`. The smoke test should no longer rely on repo‑temp paths and must instead use the stable repo path: `artefacts/fraud-platform/sr` (or an explicit override via `SR_ARTIFACTS_ROOT`).

### Decision trail
- **Default SR runtime location for tests** should be deterministic and repo‑local, not temp‑scoped.
- **Env override stays** for flexibility in CI or alternate ledger roots.
- Remove system `%TEMP%` / repo `temp/artefacts` fallbacks to avoid silent dependence on cleaned directories.

### Change applied (planned)
1) Update `_candidate_sr_roots` in `tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py`:
   - Keep `SR_ARTIFACTS_ROOT`/`SR_LEDGER_ROOT` override.
   - Default to `artefacts/fraud-platform/sr` only.
2) Update `services/ingestion_gate/README.md` smoke test notes to reflect the new path list.
3) Log the change in the logbook after implementation and re‑run the smoke test if needed.

---

## Entry: 2026-01-25 09:11:10 — IG smoke test path alignment (implementation result)

### Changes applied
- `tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py` now searches:
  - `SR_ARTIFACTS_ROOT` / `SR_LEDGER_ROOT` override
  - `artefacts/fraud-platform/sr` (repo‑local default)
- Skip message updated to reference the repo‑local artefacts path.
- `services/ingestion_gate/README.md` updated to match the new search order.

### Notes
SR artifacts are expected under `artefacts/fraud-platform/sr/` (repo‑local). `temp/artefacts` is no longer referenced by tests.

---

## Entry: 2026-01-25 11:55:30 — Phase 4 planning (service boundary + READY automation + pull checkpoints)

### Problem / goal (why Phase 4 exists)
IG is currently a library + CLI. For v0 platform readiness we need IG to run as a **service** and automatically **react to SR READY** signals. That is the only approved join surface (no “scan latest”). Phase 4 is about making IG deployable and safe under restarts while preserving the trust‑boundary semantics (ADMIT/DUPLICATE/QUARANTINE with durable receipts).

### Authorities / constraints shaping the plan
- **IG design authority**: IG is the trust boundary; READY/run_facts_view is the only run join surface; no scanning for “latest run”; no‑PASS‑no‑read.
- **Platform doctrine**: append‑only truth, idempotency, deterministic partitioning; fail‑closed when missing evidence; provenance stamped everywhere.
- **Engine blackbox**: IG must use artifacts + receipts only; no engine code changes or inferred semantics.
- **Security posture**: do not store secrets in receipts or implementation notes.

### Decision trail (live reasoning)
1) **Trigger model for pull ingestion**
   - Option A: Periodic scan of `sr/run_status` or `run_facts_view` (polling).
     - Rejected: violates “no scanning for latest” and makes runtime behavior ambiguous.
   - Option B: Subscribe to SR READY control bus (`fp.bus.control.v1`) and treat READY as the sole trigger.
     - Chosen: aligns with pinned join semantics and provides explicit, idempotent triggers.
2) **Service boundary shape**
   - We already use Flask for SR; mirroring this keeps dependencies minimal and consistent.
   - Service should be profile‑driven (single wiring profile on startup), just like CLI.
   - Push ingestion must accept canonical envelopes; pull ingestion must accept run_facts_view ref or run_id (resolved to ref).
3) **Idempotent READY processing**
   - READY events are at‑least‑once. We must record which READY messages have been processed (by message_id / run_id).
   - We’ll store a **pull ingestion record** under `ig/pull_ingestion/` in object store and index it in the ops DB for fast lookup.
4) **Pull checkpoints**
   - Pull ingestion can be long‑running. If the service restarts mid‑run, we need deterministic resume.
   - We will checkpoint by `output_id` (and potentially by locator path if needed for very large outputs).
   - Replays must be safe: already processed outputs skip based on checkpoint; receipts remain append‑only.
5) **Observability and governance**
   - READY processing should emit a governance fact with counts + outcome; logs should narrate per‑run progress for operator clarity.

### Phase 4 scope breakdown (what we will build)
**4.1 Service boundary (HTTP + CLI parity)**
- Add an IG service wrapper (Flask) with endpoints for:
  - `POST /v1/ingest/push` (canonical envelope)
  - `POST /v1/ingest/pull` (run_facts_view ref or run_id)
  - `GET /v1/ops/lookup` (event_id / receipt_id / dedupe_key)
  - `GET /v1/ops/health`
- Response payloads include decision + receipt_ref + reason_code where applicable.

**4.2 READY control bus consumer**
- Add a control‑bus subscriber that reads READY events and invokes pull ingestion.
- Dedup by `message_id` and/or `run_id`; use stored pull‑records to avoid reprocessing.
- Fail‑closed if READY is malformed or `run_facts_view` missing.

**4.3 Pull ingestion checkpoints**
- Introduce a durable pull‑run record:
  - run_id, READY message_id, start/end timestamps, output_ids processed, counts, status.
  - per‑output checkpoints (completed/failed/partial).
- Replays skip completed outputs; failures can be retried idempotently.

### Planned file touchpoints (directional)
- `src/fraud_detection/ingestion_gate/service.py` (Flask app + routes)
- `src/fraud_detection/ingestion_gate/control_bus.py` (READY subscriber)
- `src/fraud_detection/ingestion_gate/pull_state.py` (pull run records + checkpoints)
- `services/ingestion_gate/README.md` (runbook + env var wiring)
- `tests/services/ingestion_gate/test_service.py` and `test_ready_consumer.py`

### Validation plan (Phase 4 tests)
- Unit: READY message validation + idempotent pull‑record handling.
- Integration: READY signal triggers pull ingest and emits pull run record; restart safe re‑run.
- Service: push + pull endpoints return receipts with valid schema.

---

## Entry: 2026-01-25 12:58:20 — Phase 4 implementation start (design decisions before coding)

### Decision trail (explicit, pre‑code)
1) **Service framework**
   - Option A: FastAPI (async + pydantic auto‑docs).
   - Option B: Flask (already used by SR, minimal dependency, consistent style).
   - **Chosen: Flask** to keep stack consistent and avoid adding async complexity to v0.
2) **Service endpoints**
   - Minimal endpoints must cover push, pull, ops lookup, and health.
   - **Chosen routes**:
     - `POST /v1/ingest/push` (canonical envelope)
     - `POST /v1/ingest/pull` (run_facts_view ref or run_id)
     - `GET /v1/ops/lookup` (event_id / receipt_id / dedupe_key)
     - `GET /v1/ops/health`
   - Responses must include decision + receipt ref + reason codes.
3) **READY consumption**
   - **File control bus** for local v0 (matches SR `FileControlBus` output).
   - Control bus polling loop with explicit stop conditions, not hidden background threads.
4) **Idempotency for READY**
   - Use **message_id** as the primary dedupe key; also store run_id for operator lookup.
   - Record is **write‑once** in object store; if already present, skip processing.
5) **Pull checkpoints**
   - Use **per‑output checkpoints** (output_id complete) rather than per‑row (too heavy).
   - If an output was partially processed and no checkpoint exists, reprocess safely; dedupe in IG makes this safe.
6) **Truth surfaces**
   - Use append‑only `events.jsonl` under `ig/pull_records/run_id=.../` for audit truth.
   - Store a derived `status.json` snapshot for convenience; source of truth remains the event log.
7) **Config / wiring**
   - Extend IG wiring to include a control bus root (file) and topic.
   - Keep profiles free of secrets; only paths/identifiers added.

### Planned code changes (phase 4.1–4.3)
- Add `src/fraud_detection/ingestion_gate/service.py` (Flask service wrapper).
- Add `src/fraud_detection/ingestion_gate/control_bus.py` (READY poller + validation).
- Add `src/fraud_detection/ingestion_gate/pull_state.py` (pull run events + checkpoints).
- Extend `src/fraud_detection/ingestion_gate/ops_index.py` with pull run index table.
- Update `src/fraud_detection/ingestion_gate/config.py` for control bus wiring.
- Update `config/platform/profiles/*.yaml` and profile README to include control bus root.
- Add tests: service endpoints, READY consumer, pull checkpoint resume.

---

## Entry: 2026-01-25 13:28:10 — Phase 4 implementation (service + READY consumer + pull checkpoints)

### Implementation decisions (as executed)
1) **Control bus wiring added to profiles**
   - Added `wiring.control_bus` (kind/root/topic) to `config/platform/profiles/*.yaml`.
   - Updated `WiringProfile` loader to parse control bus fields and reuse event_bus topic_control where available.
   - Rationale: READY consumption should be profile‑driven and explicit; default root `artefacts/fraud-platform/control_bus` matches SR file bus.
2) **Pull run state format**
   - Implemented `PullRunStore` with:
     - immutable `message_id` record (`pull_runs/message_id=...`)
     - per‑run status snapshot (`pull_runs/run_id=...json`)
     - append‑only event log (`pull_runs/run_id=...events.jsonl`)
     - per‑output checkpoints (`pull_runs/checkpoints/run_id=.../output_id=...json`)
   - Status snapshot is derived (convenience); truth is the event log + checkpoints.
   - Event log entries include `message_id` when present to keep READY provenance explicit.
3) **Idempotent READY processing**
   - READY consumer checks for existing message record and completed status.
   - If COMPLETED, skips as duplicate; if partial/in‑progress, resumes using checkpoints.
4) **Service boundary**
   - Added Flask IG service (`/v1/ingest/push`, `/v1/ingest/pull`, `/v1/ops/lookup`, `/v1/ops/health`).
   - Push returns decision + receipt + receipt_ref; pull returns per‑run status summary.
5) **Governance summary**
   - Added `ig.pull.run` governance event and schema contract; emitted on pull completion.

### Code changes (high‑signal)
- `src/fraud_detection/ingestion_gate/config.py`:
  - parse `control_bus` and `event_bus` wiring; added control bus fields to `WiringProfile`.
- `src/fraud_detection/ingestion_gate/pull_state.py`:
  - pull run records + checkpoints; append‑only event log.
- `src/fraud_detection/ingestion_gate/control_bus.py`:
  - file control bus reader + READY consumer with schema validation.
- `src/fraud_detection/ingestion_gate/admission.py`:
  - `admit_pull_with_state`, `admit_push_with_decision`, and run_facts_ref resolver.
- `src/fraud_detection/ingestion_gate/service.py`:
  - Flask service + optional READY poller thread (env‑gated).
- `src/fraud_detection/ingestion_gate/ready_consumer.py`:
  - CLI for READY polling (once or loop).
- `src/fraud_detection/ingestion_gate/ops_index.py`:
  - new `pull_runs` table; rebuild picks up pull status records.
- Contracts/policy:
  - added `docs/model_spec/platform/contracts/ingestion_gate/ig_pull_run.schema.yaml`.
  - updated `config/platform/ig/schema_policy_v0.yaml` + `class_map_v0.yaml` for `ig.pull.run`.
- `services/ingestion_gate/README.md`:
  - service + READY consumer runbook.

### Tests added (Phase 4)
- `tests/services/ingestion_gate/test_phase4_ready_consumer.py`:
  - READY file message triggers pull ingestion + idempotent duplicate skip.
- `tests/services/ingestion_gate/test_phase4_service.py`:
  - service push + pull endpoints succeed against a minimal profile.

### Test execution results
- `python -m pytest tests/services/ingestion_gate/test_phase4_ready_consumer.py tests/services/ingestion_gate/test_phase4_service.py -q` → **2 passed**
- Observed warnings from werkzeug/ast deprecations (test environment only; no functional impact).

### Notes / risks
- Pull ingestion assumes local filesystem access for run_facts_view; non‑local object stores will require a fetch adapter (future phase).
- Status snapshot overwrites are acceptable as derived state; event log remains append‑only truth.

---

## Entry: 2026-01-25 14:05:40 — Phase 5/6 checklist added + Flask/Werkzeug bump decision

### Problem / goal
User requested Phase‑5/6 checklists and to bump Flask/Werkzeug due to warning volume during Phase‑4 tests.

### Decision trail (libraries)
1) **Desired bump**: latest Flask/Werkzeug releases exist, but we must respect dependency constraints already in the repo.
2) **Compatibility constraints discovered**:
   - `connexion==2.14.2` depends on `werkzeug<2.3` (per upstream dependency listing).
   - `apache-airflow` providers currently pin Flask `<2.3` (dev dependency).
3) **Decision**: bump to the **latest compatible** line rather than breaking dependencies.
   - Set Flask to `>=2.2.5,<2.3` (keeps within Airflow/Connexion bounds).
   - Add explicit Werkzeug constraint `>=2.2,<2.3` to prevent accidental 3.x installs.
4) **Trade‑off noted**: this may not eliminate all warnings; removing them fully would require a coordinated upgrade of Connexion/Airflow to versions that allow Flask/Werkzeug 3.x (out of Phase‑4 scope).

### Phase 5/6 checklist update
Added Phase 5 (production hardening) and Phase 6 (scale + governance hardening) sections to the IG build plan with explicit DoD items.

---

## Entry: 2026-01-25 14:25:10 — Phase 5 planning (production hardening)

### Problem / goal
Phase 5 hardens IG for production: authenticated ingress + READY consumption, non‑local object store support for pull, resilience/backpressure controls, and operational runbooks/alerts. This is where we move from “local‑correct” to “production‑safe.”

### Constraints / invariants (must not break)
- **IG remains trust boundary**: always emit ADMIT/DUPLICATE/QUARANTINE with durable receipts.
- **No‑PASS‑no‑read** and **fail‑closed** stay absolute: missing or invalid evidence cannot be admitted.
- **No secrets in code or docs**: only references to secret sources (env/secret manager).
- **Engine is a blackbox**: we only read artifacts/receipts.
- **Idempotency**: at‑least‑once READY and push intake must be safe.

### Decision trail (live reasoning)
1) **AuthN/AuthZ approach**
   - Option A: “static allowlist” in profiles (similar to SR’s allowlist).
   - Option B: API key/JWT verification via shared secret or public key.
   - Decision: implement a **pluggable auth module** with `auth_mode`:
     - `disabled` for local/dev.
     - `api_key` for v0 prod (Header + allowlist, no external IdP required).
     - `jwt` reserved for Phase 6+ when a proper IdP is available.
   - Reason: simple enough for v0, doesn’t block production rollout, remains extensible.
2) **READY provenance validation**
   - READY messages are at‑least‑once and must be **validated** before pull.
   - Decision: accept READY only if:
     - topic matches control topic,
     - payload validates `run_ready_signal.schema.yaml`,
     - message_id is deduped,
     - `facts_view_ref` resolves and is readable.
3) **Non‑local object store support**
   - Current pull assumes filesystem. For prod, SR artifacts may live in S3/MinIO.
   - Decision: introduce an **object‑store reader** in IG that can read JSON by ref:
     - If ref is `s3://`, use S3 client.
     - If ref is relative, resolve via IG object store root.
   - Keep read retry/backoff bounded; fail‑closed on missing/invalid refs.
4) **Backpressure / resilience**
   - EB and object store failures should trigger **circuit breakers** and health transitions.
   - Decision: add rate‑limit + breaker thresholds to wiring; reuse HealthProbe signals (AMBER/RED).
5) **Ops runbook + alerting**
   - Provide human‑operable recovery steps; wire governance events to alert triggers.
   - Decision: add explicit runbook sections for:
     - READY backlog / consumer stuck
     - object store read failures
     - EB publish failures
     - quarantine spikes

### Phase 5 implementation plan (stepwise)
1) **Auth module**
   - Add `src/fraud_detection/ingestion_gate/security.py` with `auth_mode` and `authorize()` helper.
   - Extend `WiringProfile` with `auth_mode`, `auth_allowlist`, `api_key_header`, and `api_key_allowlist_ref` (file path).
   - Enforce auth in:
     - HTTP push endpoint.
     - READY consumer (optional allowlist by message_id/run_id until proper signing).
2) **Object store reader for run_facts_view**
   - Add `read_json_by_ref(ref: str)` with support for:
     - `s3://bucket/key` using boto3.
     - relative refs via object store root.
   - Add retries with bounded backoff; log reason codes on failure.
3) **Resilience / backpressure**
   - Add rate‑limit settings to wiring (push_per_minute, ready_per_minute).
   - Add circuit breaker counters for EB publish + object store reads.
   - HealthProbe should surface these as AMBER/RED reasons.
4) **Ops runbook + alerts**
   - Update `services/ingestion_gate/README.md` with failure scenarios and recovery steps.
   - Add alert checklist (health transitions, quarantine spikes, READY failures).

### Validation plan (Phase 5)
- Unit tests for auth modes + allowlist parsing.
- Unit tests for run_facts_view S3 ref resolution (mocked boto3).
- Integration test: READY consumer rejects invalid payloads and unauthorized push.
- Load/backpressure test: simulate EB failure → health RED → intake refused.

### Open questions
- Whether to use a centralized auth service in this repo or keep auth local to IG for v0.
- Which audit stream is authoritative for alert routing (control vs audit topics).

---

## Entry: 2026-01-25 15:10:30 — Phase 5 implementation (auth, rate limits, S3 run_facts)

### Implementation decisions (live, during coding)
1) **Auth enforcement point**
   - Auth is enforced at the **service boundary** (HTTP ingress) and READY consumer, not inside core admission logic.
   - Reason: admission is also used by internal callers (tests/CLI); boundary enforcement keeps the core path deterministic and testable.
2) **Auth mode strategy**
   - Implemented `auth_mode=api_key` with a file‑backed allowlist (`auth_allowlist_ref`) and optional inline list.
   - JWT mode returns `AUTH_MODE_UNSUPPORTED` (explicit fail‑closed) to avoid false security.
3) **Rate limiting**
   - Implemented simple in‑memory per‑process rate limits for push/READY (`push_rate_limit_per_minute`, `ready_rate_limit_per_minute`).
   - Returns `RATE_LIMITED` → HTTP 429 for push/pull endpoints; READY consumer marks `SKIPPED_RATE_LIMIT`.
4) **READY allowlist**
   - Added `ready_allowlist_run_ids` to explicitly gate READY processing (useful until signed READY is implemented).
5) **Non‑local run_facts**
   - Added S3 read path for `run_facts_view` (supports `s3://` refs).
   - HealthProbe now tracks store read failures; repeated failures flip health to RED.
6) **Engine pull S3 support**
   - EnginePuller can read outputs from `s3://` locators (json/jsonl/parquet) using boto3.
   - Uses env‑controlled endpoint/region/path style (`IG_S3_*`/`AWS_*`).

### Code changes (high‑signal)
- Auth + rate limiting:
  - `src/fraud_detection/ingestion_gate/security.py`
  - `src/fraud_detection/ingestion_gate/rate_limit.py`
  - `src/fraud_detection/ingestion_gate/service.py` (auth + 429 mapping)
  - `src/fraud_detection/ingestion_gate/control_bus.py` (READY allowlist + rate limit)
- Wiring updates:
  - `src/fraud_detection/ingestion_gate/config.py` (security section + limits)
  - `config/platform/profiles/README.md` (security wiring docs)
- Non‑local pull:
  - `src/fraud_detection/ingestion_gate/admission.py` (`_load_run_facts_by_ref` + health read counters)
  - `src/fraud_detection/ingestion_gate/engine_pull.py` (S3 locators + wildcard support)
  - `src/fraud_detection/ingestion_gate/health.py` (store read failure threshold)

### Tests added (Phase 5)
- `tests/services/ingestion_gate/test_phase5_auth_rate.py`
  - API key auth required and enforced.
  - Push rate limit returns 429.
  - READY allowlist blocks unauthorized run_id.
- `tests/services/ingestion_gate/test_phase5_runfacts_s3.py`
  - S3 run_facts ref reading with a mocked boto3 client.

### Test results
- `python -m pytest tests/services/ingestion_gate/test_phase5_auth_rate.py tests/services/ingestion_gate/test_phase5_runfacts_s3.py -q` → **4 passed**
- Warnings remain from werkzeug/ast deprecations (test env).

### Notes / caveats
- Auth is boundary‑only for now; internal calls (CLI/tests) bypass auth as expected.
- S3 support reads whole objects into memory (v0 tradeoff).
- Full production runbook + alert wiring remains to be expanded before Phase‑5 completion.
- During testing, the S3 run_facts test initially failed because the audit partitioning profile was missing; fixed by adding `ig.partitioning.v0.audit` to the test partitioning fixture.

## Entry: 2026-01-25 14:54:07 — Phase 5 completion plan (retries, per‑phase metrics, runbook/alerts)

### Problem / goal
Finish Phase 5 hardening: add bounded retries for object‑store reads, expose circuit‑breaker behavior via health gates, add per‑phase latency metrics, and document the operational runbook + alerts. Also tighten boundary auth coverage and fix formatting gaps in IG service docs.

### Live reasoning / decisions
- **Retry strategy:** use bounded exponential backoff with small defaults (attempts + base delay + max delay). Make values configurable via wiring (no secrets) to suit local vs prod.
- **Retry scope:** apply to run_facts_view reads (critical) and S3 output reads for pull ingestion. Do **not** retry EB publish automatically to avoid duplicate appends.
- **Circuit breaker posture:** reuse HealthProbe thresholds (publish/read failures) but call health gate **before** run_facts reads so repeated failures cut intake; record read failures to flip RED deterministically.
- **Per‑phase latency metrics:** instrument validate, verify, publish, and receipt phases with stable metric keys; keep existing `admission_seconds` as end‑to‑end.
- **Runbook + alerts:** keep operator guidance in `services/ingestion_gate/README.md`, listing failure modes, recovery steps, and alert triggers (health state changes, quarantine spikes, READY failures). No credentials or secrets.
- **Tests:** add a focused retry helper test and re‑run Phase‑5 suite to keep green.

### Planned edits (stepwise)
1) Add `ingestion_gate/retry.py` helper and new wiring fields for store read retries; update profile README.
2) Wrap run_facts_view reads and S3 output reads with retry; enforce health check before pull reads.
3) Add per‑phase latency metrics in admission + quarantine paths.
4) Update IG service README with runbook/alerts, auth boundary note, and fix code‑fence formatting.
5) Add retry unit test; re‑run Phase‑5 tests.
6) Update build plan status and logbook after validation.

## Entry: 2026-01-25 14:58:38 — Phase 5 completion (retries + per‑phase metrics + runbook/alerts)

### Implementation decisions applied (live trail)
- **Bounded retries:** added a small retry helper with exponential backoff (attempts + base + max). Values are wiring‑configurable; defaults keep local runs fast while allowing prod tuning.
- **Retry scope:** run_facts_view reads and S3 output reads are retried; EB publish is **not retried** to avoid duplicate appends.
- **Circuit breaker alignment:** health gate is enforced before pull reads; read failures increment HealthProbe counters to trip RED deterministically.
- **Per‑phase latency metrics:** added timers for validate, verify, publish, receipt (plus dedupe) while keeping `admission_seconds` end‑to‑end.
- **Auth boundary clarity:** ops endpoints are covered by the same auth boundary as ingest endpoints.
- **Runbook + alerts:** operator guidance and alert triggers are documented in the IG service README; formatting cleaned to avoid broken code fences.

### Code + doc changes (high‑signal)
- `src/fraud_detection/ingestion_gate/retry.py`: bounded retry helper.
- `src/fraud_detection/ingestion_gate/config.py`: new retry wiring fields (`store_read_retry_*`).
- `src/fraud_detection/ingestion_gate/admission.py`: health gate before pull reads, retry‑wrapped run_facts reads, per‑phase metrics.
- `src/fraud_detection/ingestion_gate/engine_pull.py`: retry for S3 list/get + wiring passthrough.
- `config/platform/profiles/README.md`: security + retry wiring docs; auth boundary note.
- `services/ingestion_gate/README.md`: runbook/alerts + formatting fixes.
- `tests/services/ingestion_gate/test_phase5_retries.py`: retry helper unit test.

### Tests run / outcomes
- `python -m pytest tests/services/ingestion_gate/test_phase5_auth_rate.py tests/services/ingestion_gate/test_phase5_runfacts_s3.py tests/services/ingestion_gate/test_phase5_retries.py -q`
  - Failed (system python missing Flask).
- Re‑ran via venv:
  - `.\.venv\Scripts\python.exe -m pytest tests/services/ingestion_gate/test_phase5_auth_rate.py tests/services/ingestion_gate/test_phase5_runfacts_s3.py tests/services/ingestion_gate/test_phase5_retries.py -q` → **5 passed**
  - Warnings: werkzeug/ast deprecation noise persists (known, upstream dependency constraint).

## Entry: 2026-01-25 17:41:06 — Phase 6 planning (scale + governance hardening)

### Problem / goal
Phase 6 scales IG horizontally and hardens audit‑grade integrity without violating rails (idempotency, append‑only truth, fail‑closed, provenance in every output). This covers distributed READY consumption, pull sharding with checkpoints, and integrity/audit verification.

### Constraints / rails (non‑negotiable)
- At‑least‑once transport is assumed; ingestion must remain idempotent under duplicates.
- READY is the only join surface (no scanning for “latest”).
- Receipts/quarantine are append‑only truth; derived views can be overwritten.
- Engine remains a black box (read artifacts only).
- No secrets or credentials in docs.

### Live decision trail (planning)
1) **Distributed READY processing (exactly‑once at message_id)**
   - Need a **distributed lease/lock** so multiple IG instances can share READY work without double‑pulling.
   - Options:
     - Postgres advisory locks (reuse ops DB, lowest new infra).
     - Redis locks (fast, but extra infra + failure modes).
     - DynamoDB conditional writes (AWS‑native; infra overhead).
   - Leaning: **Postgres advisory locks** for v0 scale; keeps infra minimal and aligns with existing ops DB usage.

2) **READY dedupe truth surface**
   - Already have message_id records in object store. For multi‑instance, we need **atomic claim** or **lease record** in a shared DB.
   - Use ops DB table `ready_leases` with `(message_id, run_id, owner, lease_expires_utc)`; compare‑and‑swap for claim.

3) **Pull sharding strategy**
   - Shard by `output_id` (coarse, stable) with optional sub‑shard by locator range if outputs are huge.
   - Do **not** shard by row for v0; rely on dedupe and per‑output checkpoints.
   - Add shard checkpoints under `pull_runs/checkpoints/run_id=.../output_id=.../shard=...json` when needed.

4) **Integrity + audit proofing**
   - Add a **hash chain** over pull run events for tamper‑evidence:
     - Each event includes `prev_hash` and `event_hash` = sha256(prev_hash + canonical_json(event)).
   - Provide a periodic audit job that replays event log and validates hash chain + receipt/index parity.

5) **Operational safety**
   - Lease expiry with heartbeat; if IG dies, lease expires and another instance resumes safely.
   - Health gate denies intake when lease DB is unavailable (fail‑closed).

### Phase 6.1 plan (horizontal READY consumer)
- Add `ready_leases` table to OpsIndex with atomic claim + heartbeat + release.
- READY consumer acquires lease before pull; skips if lease exists and not expired.
- Persist lease metadata in pull run record for audit (owner, lease_id, acquired_at).

### Phase 6.2 plan (pull sharding + checkpoints)
- Extend `PullRunStore` to track shard checkpoints per output.
- Add sharding strategy config: `shard_mode: output_id|locator_range` + max shard size.
- Ensure pull resume logic merges per‑shard completion into run status.

### Phase 6.3 plan (integrity + audit proofing)
- Add hash chain fields to pull run event log entries.
- Add `ig.audit.verify` CLI to validate:
  - hash chain integrity,
  - receipts ↔ ops index parity,
  - pull checkpoints completeness.
- Emit governance facts for audit job outcome.

### Validation / test plan
- Concurrency test: two IG instances race for READY; only one acquires lease and ingests.
- Lease expiry test: instance A acquires, stops heartbeating → instance B resumes safely.
- Shard checkpoint test: partial completion resumes without duplicates; end counts stable.
- Audit job test: detects tampered event log (hash chain mismatch).

### Open decisions to confirm
- **Lease backend** for distributed READY: Postgres advisory locks vs Redis vs DynamoDB.
- **Shard mode** default: output_id only vs enabling locator_range in v0.
- **Audit job schedule**: manual CLI only vs periodic scheduler hook.

## Entry: 2026-01-25 17:52:43 — Phase 6 decisions locked + implementation start

### Decisions locked (per confirmation)
- **Lease backend:** Postgres advisory locks for distributed READY consumption. No SQLite for multi‑instance. Local single‑instance runs can use a no‑op lease manager (explicitly non‑distributed).
- **Sharding default:** output_id only for v0. Locator‑range sharding is optional and config‑gated.
- **Audit schedule:** manual CLI verifier with an optional scheduler hook (no new scheduler dependency in v0).

### Live reasoning (why these are production‑safe)
- Postgres advisory locks give strong atomicity with minimal new infra and align with our existing Postgres usage; advisory locks release automatically if the process dies, which is safer than stale table leases.
- output_id sharding is deterministic and aligns with our existing per‑output checkpointing; locator‑range sharding is kept as an opt‑in for large outputs to avoid premature complexity.
- A manual audit CLI gives audit‑grade verification without adding a scheduler dependency; ops can hook it into cron/CI later.

### Implementation plan (stepwise, Phase 6)
1) **Lease manager**: introduce `ReadyLeaseManager` with a Postgres advisory‑lock implementation; wire into READY consumer; emit lease events into pull run log for audit.
2) **Sharding (optional)**: extend pull checkpoints to support shard IDs; add locator‑range sharding mode (config‑gated) while keeping output_id default.
3) **Integrity**: add a hash chain over pull‑run event log entries (prev_hash + event_hash) with derived chain state storage.
4) **Audit CLI**: add an `--audit-verify` option to validate hash chain + checkpoint completeness for a run; emit a governance fact on audit outcome.
5) **Tests**: add unit tests for hash chain + sharded checkpoints + lease acquisition behavior (local no‑op or mocked Postgres).

### Guardrails
- Keep receipts/quarantine append‑only; any mutable state is explicitly derived.
- No secrets or credentials in code or docs (DSN is config/env‑only).

## Entry: 2026-01-25 18:02:15 — Phase 6 implementation (leases, sharding, hash chain, audit CLI)

### Decisions applied (live reasoning)
- **Lease backend** implemented with Postgres advisory locks (optional), plus a no‑op local lease manager for single‑instance runs. This preserves production correctness while keeping local dev usable without extra infra.
- **Sharding default** remains output_id only; locator‑range sharding is opt‑in and config‑gated with explicit shard_size.
- **Integrity** enforced via a pull‑run event hash chain. The event log remains the source of truth; chain state is a derived file for efficient append.
- **Audit verification** is CLI‑driven and emits an audit governance fact (`ig.audit.verify`). No scheduler dependency added.

### Code changes (stepwise, with rationale)
1) **READY leases**
   - Added `leases.py` with `PostgresReadyLeaseManager` (advisory locks) and `NullReadyLeaseManager` for local non‑distributed runs.
   - Wired READY consumer to acquire/release leases and emit lease events into the pull run log for auditability.
   - Failure to reach the lease backend is fail‑closed (`LEASE_BACKEND_UNAVAILABLE`).

2) **Sharding + checkpoints**
   - Added locator‑range sharding (optional): outputs can be split into file‑path shards with per‑shard checkpoints.
   - Output‑level completion remains unchanged for default mode; sharded runs emit `SHARD_COMPLETED/FAILED` events and a final `OUTPUT_COMPLETED` event.

3) **Hash‑chain integrity**
   - Pull‑run event log now includes `prev_hash` + `event_hash` computed deterministically.
   - Chain state is stored as a derived record to avoid scanning the full log on each append.

4) **Audit CLI**
   - Added `--audit-verify <run_id>` to validate hash chain + checkpoint completeness.
   - Added `ig.audit.verify` contract and policy/class map entries; governance emitter now publishes audit verification facts.

### Files updated/added (high‑signal)
- `src/fraud_detection/ingestion_gate/leases.py`
- `src/fraud_detection/ingestion_gate/control_bus.py`
- `src/fraud_detection/ingestion_gate/pull_state.py`
- `src/fraud_detection/ingestion_gate/engine_pull.py`
- `src/fraud_detection/ingestion_gate/admission.py`
- `src/fraud_detection/ingestion_gate/audit.py`
- `src/fraud_detection/ingestion_gate/cli.py`
- `src/fraud_detection/ingestion_gate/governance.py`
- `config/platform/ig/schema_policy_v0.yaml`
- `config/platform/ig/class_map_v0.yaml`
- `docs/model_spec/platform/contracts/ingestion_gate/ig_audit_verify.schema.yaml`
- `docs/model_spec/platform/contracts/README.md`
- `config/platform/profiles/README.md`
- `services/ingestion_gate/README.md`

### Tests added (Phase 6)
- `tests/services/ingestion_gate/test_phase6_hash_chain.py`
- `tests/services/ingestion_gate/test_phase6_shard_checkpoints.py`
- `tests/services/ingestion_gate/test_phase6_lease_manager.py`

### Pending validation
- Run Phase‑6 test subset in venv and update logbook with results.

## Entry: 2026-01-25 18:03:16 — Phase 6 tests (hash chain + shard checkpoints + leases)

### Tests run / outcomes
- `.\.venv\Scripts\python.exe -m pytest tests/services/ingestion_gate/test_phase6_hash_chain.py tests/services/ingestion_gate/test_phase6_shard_checkpoints.py tests/services/ingestion_gate/test_phase6_lease_manager.py -q` → **3 passed**

### Notes
- These validate the new hash‑chain append logic, shard checkpoint paths, and local lease manager behavior.

## Entry: 2026-01-25 18:22:40 — Phase 6 wiring + two‑instance READY smoke test

### Live decision trail
- **Profile wiring:** added `ready_lease` blocks to local/dev/prod profiles using env placeholders. This keeps secrets out of config while enabling Postgres lease backend.
- **Env resolution:** implemented minimal `${VAR}` resolution in `WiringProfile.load` so placeholders resolve at runtime (required for lease DSN and object store endpoints).
- **Smoke profile:** used a scratch profile with a local object store root for the smoke test to avoid MinIO/S3 dependencies.

### Smoke test setup (what was created)
- Scratch profile: `scratch_files/ig_ready_smoke_profile.yaml` (local object_store root, Postgres lease backend via env).
- Test artifacts:
  - `artefacts/fraud-platform/sr/run_facts_view/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.json`
  - `artefacts/fraud-platform/engine_outputs/merchant_class_profile_5A.jsonl`
  - `artefacts/fraud-platform/control_bus/fp.bus.control.v1/smoke-lease-2.json`

### Two‑instance READY consumer run (result)
- Postgres started via docker compose (sr‑parity stack).
- Two READY consumers launched concurrently with distinct `IG_INSTANCE_ID` and shared `IG_READY_LEASE_DSN`.
- Observed **lease contention working**:
  - For each READY message, one instance processed and the other returned `SKIPPED_LEASED`.
  - The smoke run (`smoke-lease-2`) completed successfully; events were quarantined due to `SCHEMA_POLICY_MISSING` for `merchant_class_profile_5A` (expected for this synthetic output).

### Commands executed (for reproducibility, no secrets)
- `docker compose -f infra/local/docker-compose.sr-parity.yaml up -d postgres`
- Two‑instance run via PowerShell jobs using `.\.venv\Scripts\python.exe -m fraud_detection.ingestion_gate.ready_consumer --profile scratch_files/ig_ready_smoke_profile.yaml --once` with env vars:
  - `IG_READY_LEASE_DSN=postgresql://sr:sr@localhost:5433/sr_dev`
  - `IG_INSTANCE_ID=ig-1` / `ig-2`

### Notes
- READY message from prior SR run was also picked up; it remains `PARTIAL` due to missing artifacts, which is expected under fail‑closed posture.

## Entry: 2026-01-25 20:31:57 — Local IG profile alignment (object_store root)

### Problem / goal
Local SR writes artifacts under `artefacts/` while the IG local profile pointed at a bucket name (`fraud-platform`) and optional S3 endpoint. This caused IG to resolve run_facts paths as `fraud-platform/fraud-platform/...` and fail to read READY facts in local runs.

### Decision / rationale
- For **local** profile only, set `object_store.root: artefacts` so IG reads local filesystem artifacts produced by SR’s `wiring_local.yaml`.
- Keep bucket/endpoint keys for parity docs, but `root` takes precedence for local filesystem runs.

### Change applied
- `config/platform/profiles/local.yaml`: added `object_store.root: artefacts`.

---

## Entry: 2026-01-25 20:57:05 — IG runtime root migration + platform log output (pre‑change)

### Trigger
User mandated a hard move of platform runtime artifacts to `runs/fraud-platform` and requested **component run logs** to be written under `runs/fraud-platform/*.log`. This affects IG’s control‑bus reads, admission DB default, and smoke tests that locate SR artifacts.

### Live reasoning (what must shift)
- IG currently resolves SR refs by prefixing the object store root. When root is set to `runs`, `fraud-platform/sr/...` resolves correctly to `runs/fraud-platform/sr/...` without the prior `fraud-platform/fraud-platform` duplication.
- Default control‑bus roots (`artefacts/fraud-platform/control_bus`) must move to `runs/fraud-platform/control_bus` to align with SR’s new output location.
- The ops rebuild smoke test must search under the **new SR root** so it can find READY runs without manual overrides.
- A clear IG log file (ready consumer + service/CLI) improves traceability, especially when running READY in dual‑instance mode.

### Plan (before code)
1) Update IG defaults + profiles:
   - Change `object_store.root` in `config/platform/profiles/local.yaml` to `runs`.
   - Update `control_bus.root` in local/dev/prod profiles to `runs/fraud-platform/control_bus`.
   - Update `ingestion_gate.config` defaults so `admission_db_path` uses `runs/fraud-platform/ig/index/`.
2) Update READY consumer/service defaults:
   - `ready_consumer.py` and `service.py` default control_bus_root → `runs/fraud-platform/control_bus`.
3) Update the ops rebuild smoke test:
   - Search `runs/fraud-platform/sr` by default and adjust skip message.
4) Add IG log files:
   - Extend `ingestion_gate.logging_utils.configure_logging()` to accept a log path.
   - Wire `ready_consumer`, `service`, and IG CLI to emit logs under `runs/fraud-platform/`.
5) Migrate existing runtime artifacts on disk to `runs/fraud-platform/` and update any README references.

### Guardrails
- No secrets in logs/docs. Any DSN values remain in env/config placeholders only.
- Engine remains a black box; IG reads SR outputs only by ref.

---

## Entry: 2026-01-25 21:06:50 — Applied: IG runtime root migration + log outputs

### Applied changes (stepwise)
1) **Defaults + profiles**
   - `src/fraud_detection/ingestion_gate/config.py`: default `object_store_root` → `runs`; `admission_db_path` now defaults to `runs/fraud-platform/ig/index/ig_admission.db`.
   - `config/platform/profiles/local.yaml`: `object_store.root: runs` and `control_bus.root: runs/fraud-platform/control_bus`.
   - `config/platform/profiles/dev.yaml` / `prod.yaml`: control bus root updated to `runs/fraud-platform/control_bus`.
   - `config/platform/profiles/README.md`: notes updated to reflect the new runs root.
2) **READY consumer/service defaults**
   - `ready_consumer.py` and `service.py`: default control bus root → `runs/fraud-platform/control_bus`.
3) **Smoke test alignment**
   - `tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py`: default SR artifacts root moved to `runs/fraud-platform/sr` and skip message updated.
4) **Log files**
   - `ingestion_gate/logging_utils.py`: optional file handler support.
   - `ready_consumer.py`, `service.py`, `cli.py`: all append to the **shared platform log** at `runs/fraud-platform/platform.log` (override via `PLATFORM_LOG_PATH`).
   - `services/ingestion_gate/README.md`: log location note updated.

### Outcome
IG now resolves SR READY refs under the **shared runtime root** (`runs/fraud-platform`) without `fraud-platform/fraud-platform` duplication, and appends to the shared platform log (`runs/fraud-platform/platform.log`).

---

## Entry: 2026-01-25 22:11:16 — Fix: Parquet read INTERNAL_ERROR during IG pull

### Problem observed (live)
The SR→IG smoke run produced `OUTPUT_FAILED` with reason `INTERNAL_ERROR` for every output. The pull‑run log didn’t include details, so I replicated the read in venv and saw:
- `pyarrow.lib.ArrowTypeError: Unable to merge: Field seed has incompatible types...`
This happens because `pyarrow.parquet.read_table()` uses the dataset API and attempts schema merging across row groups, which fails on these engine outputs.

### Decision
Use `pyarrow.parquet.ParquetFile(path).read()` for local parquet reads in IG. It reads a single file directly and avoids the dataset‑level schema merge.

### Change applied
- `src/fraud_detection/ingestion_gate/engine_pull.py`: replace `pq.read_table(local)` with `pq.ParquetFile(local).read()` for `.parquet` files.

### Expected outcome
IG pull should now ingest engine parquet outputs without the schema merge error, yielding `COMPLETED` instead of `PARTIAL` for outputs that are otherwise valid.

---

## Entry: 2026-01-25 22:47:28 — SR→IG smoke run (10‑min cap) after parquet fix

### What was executed (bounded run)
I ran a single `make platform-ig-ready-once` after the parquet fix, with a **10‑minute cap** (per user request). Any existing READY consumers were stopped first to avoid lease contention.

### Observations (no schema failure, but long runtime)
- The pull run did **not** emit new `OUTPUT_FAILED` events with `INTERNAL_ERROR`.
- The READY consumer remained active past the 10‑minute cap; the run had not reached `PULL_COMPLETED` within the time window.
- This indicates the **schema merge error is resolved**, but the full ingestion over the large engine outputs likely needs **more than 10 minutes** on local hardware.

### Diagnosis (why it didn’t finish in time)
- `arrival_events_5B` alone has ~591 parquet files; ingesting all outputs is heavy for a bounded smoke run.
- The IG pull pipeline is doing full ingestion; with a strict 10‑minute cap, it may not complete even when functioning correctly.

### Next decision needed
To mark SR→IG “green,” choose one of:
1) **Allow a longer run** (recommended for a true end‑to‑end validation).
2) **Enable shard checkpointing in local profile** (`pull_shard_mode: locator_range`, `pull_shard_size: 1`) to allow incremental progress across multiple READY runs without reprocessing completed files.
3) **Add a local‑only ingest cap** (e.g., max files per output) to make a short smoke run deterministic; default remains uncapped for production.

I will proceed based on your preference.

---

## Entry: 2026-01-25 22:51:40 — Plan: IG time budget + platform session logs

### Trigger
User approved the recommendation to add a **time budget** for local IG pulls and introduce **platform run IDs** so runs don’t share a single folder.

### Live reasoning
- Local engine outputs are large; a bounded smoke run must be **deterministic** and **safe to interrupt**.
- A wiring‑only time budget lets local runs stop early without changing policy behavior or production defaults.
- Platform run IDs should not change SR/IG ledger ownership, only add session scoping for logs and metadata.

### Plan (IG changes)
1) Add `pull_time_budget_seconds` to IG wiring (optional, default None).
2) Enforce the time budget inside `admit_pull_with_state`:
   - If exceeded, append `OUTPUT_FAILED` with `TIME_BUDGET_EXCEEDED` and stop processing further outputs.
   - Status remains `PARTIAL` with explicit reason codes.
3) Update local profile to set `pull_time_budget_seconds: 600` (10 minutes) for smoke runs.
4) Update IG logging to append to both global and session platform logs.
5) Add a small unit test to ensure `TIME_BUDGET_EXCEEDED` is emitted when budget is zero.

### Guardrails
- Default remains uncapped unless wired (no production change).
- No engine code changes.

## Entry: 2026-01-25 23:12:50 — Applied: pull time budget + session log wiring

### What changed (stepwise)
1) **Wiring support**
   - Added `pull_time_budget_seconds` to `WiringProfile` (optional, default None).
   - `config/platform/profiles/local.yaml` now sets `pull_time_budget_seconds: 600` for bounded smoke runs.
   - `config/platform/profiles/README.md` documents the new knob and clarifies it is local‑only by default.

2) **Admission time budget** (`admit_pull_with_state`)
   - Added a monotonic‑time budget guard for pull runs.
   - When the budget is exceeded, IG appends `OUTPUT_FAILED` with `reason_code=TIME_BUDGET_EXCEEDED`, logs a warning, and stops further output processing.
   - The run ends in `PARTIAL` with a clear failure reason (no silent truncation).

3) **Session‑scoped logs**
   - IG CLI/READY consumer/service now call `platform_log_paths()` (global log + optional session log).

4) **Test coverage**
   - Added `tests/services/ingestion_gate/test_phase6_time_budget.py` to assert the `TIME_BUDGET_EXCEEDED` outcome is emitted deterministically.

### Files updated
- `src/fraud_detection/ingestion_gate/config.py`
- `src/fraud_detection/ingestion_gate/admission.py`
- `src/fraud_detection/ingestion_gate/cli.py`
- `src/fraud_detection/ingestion_gate/ready_consumer.py`
- `src/fraud_detection/ingestion_gate/service.py`
- `config/platform/profiles/local.yaml`
- `config/platform/profiles/README.md`
- `tests/services/ingestion_gate/test_phase6_time_budget.py`

### Notes
- No engine code or run outputs were modified.
- Time budget is **opt‑in** and defaults to uncapped unless wired.


## Entry: 2026-01-25 23:27:30 — Local SR→IG smoke run with time budget

### What was exercised
- SR reuse run produced READY for engine run `runs/local_full_run-5/c25a...` with a fresh equivalence key.
- IG READY consumer processed the READY message under `pull_time_budget_seconds: 600` (local profile).

### Observed outcome
- Pull run status: `PARTIAL` with `TIME_BUDGET_EXCEEDED` on `arrival_events_5B`.
- Status record written to `runs/fraud-platform/ig/pull_runs/run_id=40dfb540e134f8bb8eb3585da3aeee7a.json`.
- Confirms the **time budget guard** halts long pulls deterministically without touching engine outputs.

### Notes
- The time budget is a local operator guard; production defaults remain uncapped.


## Entry: 2026-01-25 23:30:20 — Enable local sharded pulls + READY reemit workflow

### Trigger
User selected **Option 2**: enable sharded pulls in `local.yaml` and re‑run READY ingestion until `PULL_COMPLETED` is observed.

### Live reasoning (what must change)
- With `pull_time_budget_seconds=600`, a full pull can’t finish in one pass. We need **checkpointed sharding** so each READY run advances progress without re‑processing.
- The READY consumer dedupes by `message_id`, so to re‑process the *same* run_id we must **re‑emit READY** with a new message_id (SR `reemit` command).
- For local workflow, a Make target for **SR reemit** keeps everything centralized (no manual CLI or PowerShell).

### Plan (before code)
1) Update `config/platform/profiles/local.yaml` to enable sharding:
   - `pull_sharding.mode: locator_range`
   - `pull_sharding.shard_size: 1`
2) Add Make target `platform-sr-reemit-ready` (or generic reemit) so we can publish a new READY message for a given `run_id` without creating a new SR run.
3) Re‑run READY ingestion in cycles:
   - SR reemit READY → IG ready once → check `runs/fraud-platform/ig/pull_runs/run_id=<id>.json`.
   - Continue until `status=COMPLETED` (or pause if it’s clear multiple cycles are needed).

### Guardrails
- Engine remains untouched.
- No secrets in docs/logs.


## Entry: 2026-01-25 23:33:10 — Applied: enable local sharded pulls + SR reemit target

### Applied changes
1) **Local profile sharding**
   - `config/platform/profiles/local.yaml` now enables:
     - `pull_sharding.mode: locator_range`
     - `pull_sharding.shard_size: 1`
   This makes each READY pass checkpointable by locator shards under the time budget.

2) **SR READY reemit workflow**
   - Added `make platform-sr-reemit` target to publish a new READY message for an existing run_id.
   - This is required because READY consumer dedupes by `message_id`, not `run_id`.

### Next validation
- Re‑emit READY for the existing run_id and re‑run IG READY once to advance checkpoints.
- Repeat until pull status shows `COMPLETED`.


## Entry: 2026-01-25 23:56:10 — Sharded pull attempt under 10‑min budget (still PARTIAL)

### What happened
- Enabled `locator_range` sharding (size=1) and re‑emitted READY for run_id `40dfb540e134f8bb8eb3585da3aeee7a`.
- IG READY pull ran for the full 10‑minute budget and still exited as `PARTIAL` with `TIME_BUDGET_EXCEEDED` on **shard_id=0** of `arrival_events_5B`.

### Interpretation
- The first parquet shard itself takes longer than 10 minutes to ingest; sharding by locator alone doesn’t create smaller work units.
- Re‑emitting READY will **not** advance checkpoints because shard 0 never completes.

### Next viable options
1) Increase `pull_time_budget_seconds` (local only) so at least one shard completes.
2) Implement finer‑grain chunking for parquet (row‑group or row‑batch checkpoints) to allow progress within a single file.


## Entry: 2026-01-25 23:59:40 — Applied: dev_local completion profile

### What changed
- Added `config/platform/profiles/dev_local.yaml` to support **uncapped completion runs** on local filesystem.
- Kept `local.yaml` as a **time‑budgeted smoke** profile.

### Operational intent
- Local smoke: validate READY → IG ingestion pipeline with bounded time budget.
- Dev completion: run the same READY pipeline to full completion without time cap.


## Entry: 2026-01-26 02:15:30 — Dev completion run attempt (uncapped) timed out locally

### What was attempted
- Re‑emitted READY for run_id `40dfb540e134f8bb8eb3585da3aeee7a`.
- Ran `make platform-ig-ready-once-dev` (uncapped profile) for 2 hours.

### Outcome
- The READY consumer did not complete within the 2‑hour window.
- No new `run_id` status was written (process terminated before `PULL_COMPLETED`).
- Local hardware/time budget is insufficient for full completion on this dataset.

### Next decision required
To mark dev completion green, we need one of:
1) Run on stronger dev infra (actual dev environment) with no cap.
2) Implement finer‑grain parquet chunking (row‑group/row‑batch checkpoints).
3) Use a smaller engine run for dev completion (explicitly documented as a scaled validation).


## Entry: 2026-01-28 20:34:06 — IG streaming‑only alignment planning (retire pull)

### Trigger
User directed IG to **prioritize streaming only** and retire legacy pull to avoid future confusion.

### Decision (hard)
- IG will be **push‑only** in v0. READY/pull ingestion is retired.
- SR READY is now a **trigger for WSP**, not a trigger for IG.

### Rationale
- The platform’s primary data‑plane is WSP → IG (streaming). Maintaining a pull path risks role confusion and drift.
- Oracle Store is external truth; IG should not pull directly from it in the primary runtime.

### Planned alignment phases
- **Phase A:** docs/contract alignment (push‑only posture, retire pull in docs + profiles).
- **Phase B:** implementation retirement of pull/READY consumer code paths.
- **Phase C:** validation of push‑only ingestion (WSP → IG) and removal of pull‑based tests.

### Immediate changes
- Added a streaming‑only alignment section to the IG build plan (A–C phases) and marked it as planned.

---

## Entry: 2026-01-28 20:37:42 — IG alignment phases renumbered (letters → numbers)

### Change
- Replaced Phase A/B/C with numeric phases to match repo conventions and avoid ambiguity:
  - Phase 7 — docs/contracts alignment
  - Phase 8 — implementation retirement (pull removal)
  - Phase 9 — validation (push‑only green)

### Reason
User requested numeric phases; numeric ordering also integrates cleanly with existing IG phase numbering (1–6).

---

## Entry: 2026-01-28 20:51:13 — IG Phase 7 planning (streaming‑only docs + contracts)

### Trigger
User requested planning to implement IG Phase 7 (docs + contracts alignment) for streaming‑only posture.

### Phase 7 scope (docs + contracts only)
Phase 7 re‑scopes IG to **push‑only** ingestion in all design docs and contracts. It does **not** remove code paths yet (that is Phase 8). The goal is to remove ambiguity before implementation changes.

### What must change (and why)
1) **IG design authority**
   - Must state IG is a push boundary (WSP → IG) and does **not** pull from Oracle Store.
   - READY consumer and pull ingestion are explicitly labeled **legacy/retired**.

2) **Platform narratives + blueprint**
   - Control & Ingress narrative: IG receives events from WSP only.
   - Platform blueprint: remove READY‑driven IG pull; SR READY triggers WSP, not IG.

3) **IG contracts and profiles**
   - IG contract docs should no longer present pull ingestion as default or required.
   - Profiles should mark READY/pull wiring as deprecated (or remove from default examples).

### Options considered
- **Option A: Mark pull path as legacy (doc‑only), keep examples.**
  - Rejected: still risks confusion in v0 where streaming‑only is now the law.
- **Option B: Remove pull references from all docs and profile examples.**
  - Selected: aligns with “streaming‑only” directive and prevents mixed‑mode assumptions.

### Phase 7 plan (stepwise)
1) Update `docs/model_spec/platform/component-specific/ingestion_gate.design-authority.md` to declare push‑only role.
2) Update `docs/model_spec/platform/narrative/narrative_control_and_ingress.md` to reflect WSP → IG only.
3) Update `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md` to remove IG pull from the primary path narrative.
4) Update IG contract README / profile README to de‑emphasize pull and READY wiring.
5) Log each decision as it is executed (no bulk summaries).

### Out‑of‑scope
- No code removal (Phase 8).
- No test changes (Phase 9).

---

## Entry: 2026-01-28 21:01:32 — Phase 7 implemented (IG streaming‑only docs + contracts)

### Step‑by‑step decisions and changes
1) **IG design authority re‑scope (push‑only)**
   - Explicitly declared IG as **push‑only** in v0 and retired legacy engine‑pull ingestion.
   - Updated the ingestion modes section to remove “primary vs legacy” framing and state push‑only as the single runtime mode.
   - Removed SR READY and run_facts_view as IG inbound edges; IG no longer presents READY as a trigger.
   - Added a streaming‑only pin: **IG does not read run_facts_view**; any residual references are legacy‑only and should be ignored.
   - Reason: prevent future contributors from treating READY/pull as valid runtime behavior.

2) **Platform profile docs (deprecate pull wiring)**
   - Marked `ready_lease`, `pull_sharding`, and `pull_time_budget_seconds` as **legacy pull‑only** in `config/platform/profiles/README.md`.
   - Added inline comments in the example profile to label pull wiring as retired.
   - Reason: profiles are an operator touchpoint; they must not imply pull is an active path.

3) **Contracts index + legacy schema marker**
   - Marked `ig_pull_run.schema.yaml` as **deprecated** in the contracts index and added a header comment in the schema itself.
   - Reason: keep historical artifacts but make their status unambiguous.

### Out‑of‑scope (kept out intentionally)
- No code removal or runtime behavior changes (Phase 8).
- No test deletions (Phase 9).

### Sanity checks (local)
- Confirmed docs now include streaming‑only markers and deprecated pull wiring notes.

---

## Entry: 2026-01-28 21:07:31 — IG Phase 8 planning (implementation retirement of pull path)

### Trigger
User requested Phase 8 planning to implement streaming‑only IG by retiring legacy pull ingestion.

### Phase 8 scope (implementation only)
Remove or hard‑disable the READY/pull ingestion path so IG cannot accidentally ingest from `run_facts_view` or the control bus. Push ingestion remains unchanged and hardened.

### What must change (and why)
1) **Runtime entrypoints**
   - Remove READY consumer and pull ingestion CLI/service endpoints, or hard‑fail them.
   - Reason: any surviving entrypoint is a future foot‑gun.

2) **Core admission layer**
   - Remove `admit_pull*` paths and pull store wiring (or make them no‑ops with explicit error).
   - Reason: keep IG a clean push boundary and reduce maintenance load.

3) **Configuration**
   - Fail closed if pull‑only wiring is provided (`ready_lease`, `pull_sharding`, `pull_time_budget_seconds`).
   - Reason: prevent misconfigured deployments that implicitly re‑enable pull.

4) **Contracts + artifacts**
   - `ig_pull_run` artifacts remain legacy but are no longer written.
   - Reason: preserve history but remove runtime dependency.

### Options considered
- **Option A: Leave code but disable by config.**
  - Rejected: still leaves a live path if someone toggles config incorrectly.
- **Option B: Remove pull code paths entirely.**
  - Chosen: strongest guarantee for streaming‑only posture.

### Planned implementation steps
1) Remove READY consumer invocation in CLI/service and delete/disable `ready_consumer.py` path.
2) Remove `admit_pull` / `admit_pull_with_state` from IG admission logic or guard with explicit error.
3) Remove pull store modules and any pull run artifacts from runtime logic.
4) Enforce config validation: if pull wiring is set, raise a configuration error on startup.
5) Update tests to remove/skip pull‑based scenarios (Phase 9 will handle validation).

### Out‑of‑scope
- No behavioral changes to push ingestion.
- No WSP changes.
- No SR changes.

---

## Entry: 2026-01-28 21:16:20 — IG Phase 8 implementation (retire legacy pull)

### Trigger
User asked to proceed with Phase 8 implementation to fully retire the READY/pull ingestion path and enforce streaming‑only behavior in code.

### Initial decisions before code changes
1) **Remove pull ingestion primitives entirely (not just disable).**
   - Rationale: aligns with the “streaming‑only” directive and avoids a latent re‑enablement path.
   - Consequence: all pull‑only modules (`engine_pull`, `pull_state`, `ready_consumer`, `control_bus`, `audit`, `cli`) become unused and should be removed to reduce accidental use.

2) **Keep push admission intact; drop run_facts / gate receipt enforcement.**
   - Rationale: streaming mode receives events as they arrive; there is no SR READY or run_facts_view input. Any run‑facts gate verification becomes a hidden coupling to the retired SR path.
   - Consequence: remove `admit_pull*`, `resolve_run_facts_ref`, `_requires_run_ready`, and gate‑verification logic that depends on run_facts.

3) **Configuration must fail closed if pull wiring is present.**
   - Rationale: profiles often linger; the safest posture is to error loudly if legacy pull knobs are set (`ready_lease`, `pull_sharding`, `pull_time_budget_seconds`).
   - Decision: enforce explicit validation and update platform profiles to remove those keys so IG can start without ambiguity.

4) **Ops index + governance should stop referencing pull runs.**
   - Rationale: no runtime should emit `ig.pull.run` facts or `pull_runs` records once pull path is removed.
   - Decision: remove pull‑run indexing and summary emission to keep audit surfaces consistent with streaming mode.

### Planned execution order (for traceability)
1) Strip pull modules and READY consumer entrypoints.
2) Simplify IG admission to push‑only and remove run_facts verification paths.
3) Remove pull run indexing/governance hooks.
4) Enforce config validation for pull wiring, then update profiles.
5) Update tests to remove pull scenarios and keep push‑only coverage.

### Notes / constraints
- No changes to WSP or SR in this phase.
- Avoid altering engine artifacts or engine code.
- Keep streaming‑only behavior explicit in code paths and config errors.

## Entry: 2026-01-28 21:42:24 — IG Phase 8 implemented (pull removal, push‑only enforcement)

### Step‑by‑step decisions and actions
1) **Remove pull‑only modules and entrypoints**
   - Deleted IG pull modules: `src/fraud_detection/ingestion_gate/engine_pull.py`, `pull_state.py`, `control_bus.py`, `ready_consumer.py`, `audit.py`, `leases.py`, `cli.py`.
   - Reasoning: leaving these files (even unused) invites future accidental re‑enablement; streaming‑only should be enforced structurally, not just by policy.

2) **Simplify `IngestionGate` to push‑only admission**
   - Removed `admit_pull` / `admit_pull_with_state` and all run_facts / READY logic from `src/fraud_detection/ingestion_gate/admission.py`.
   - Dropped run_facts joinability checks, gate receipt verification, instance‑proof checks, and ready allowlist/rate limit enforcement.
   - Updated `_admit_event` to validate schema + required pins + health only; no SR ledger reads.
   - Reasoning: streaming mode cannot depend on SR READY / run_facts_view; verification belongs to WSP or upstream policy.

3) **Keep WSP engine reader intact by relocating `EnginePuller`**
   - Discovered WSP imports `EnginePuller` from IG; removing the file would break WSP.
   - Decision: move `EnginePuller` into Oracle Store boundary as a shared reader (`src/fraud_detection/oracle_store/engine_pull.py`) and update WSP import.
   - Rationale: EnginePuller is still valid but it is an Oracle Store helper, not an IG pull path.

4) **Remove pull‑run indexing and governance hooks**
   - Stripped `pull_runs` indexing from `src/fraud_detection/ingestion_gate/ops_index.py`.
   - Removed `emit_pull_run_summary` from `governance.py` and the call sites in admission logic.
   - Reasoning: no runtime should emit pull‑run status once streaming‑only is enforced.

5) **Fail closed on legacy pull wiring**
   - Added validation in `src/fraud_detection/ingestion_gate/config.py` to reject any `ready_lease`, `pull_sharding`, `pull_time_budget_seconds`, or `security.ready_*` fields.
   - Updated platform profiles (`config/platform/profiles/*.yaml`) to remove those keys so IG boots cleanly.
   - Updated `.env.example` and Makefile targets to drop READY lease variables and targets; replaced IG READY targets with explicit “deprecated” failure.
   - Rationale: eliminate silent misconfiguration and ensure streaming‑only posture is enforced at startup.

6) **Tests updated to match push‑only posture**
   - Rewrote IG tests to keep push ingress coverage and remove pull/READY scenarios.
   - Added a config validation test ensuring legacy pull wiring is rejected.
   - Ran `pytest tests/services/ingestion_gate -q` → 16 passed, 1 skipped (warnings from Werkzeug AST deprecations).

### Files changed (high‑signal)
- **Removed:** `src/fraud_detection/ingestion_gate/engine_pull.py`, `pull_state.py`, `control_bus.py`, `ready_consumer.py`, `audit.py`, `leases.py`, `cli.py`.
- **Added:** `src/fraud_detection/oracle_store/engine_pull.py` (EnginePuller relocated).
- **Updated:**
  - `src/fraud_detection/ingestion_gate/admission.py` (push‑only, no run_facts/gate checks)
  - `src/fraud_detection/ingestion_gate/config.py` (legacy pull wiring rejection)
  - `src/fraud_detection/ingestion_gate/service.py` (push‑only API surface)
  - `src/fraud_detection/ingestion_gate/ops_index.py`, `governance.py`, `__init__.py`
  - `src/fraud_detection/world_streamer_producer/runner.py` (EnginePuller import)
  - `config/platform/profiles/*.yaml`, `config/platform/profiles/README.md`, `.env.example`, `makefile`
  - IG tests under `tests/services/ingestion_gate/` (pull tests removed, push tests retained)

### Notes
- This phase intentionally removes SR ledger dependencies and READY consumers from IG.
- Any residual references in older plan sections are legacy; streaming‑only v0 is enforced in code and config.

## Entry: 2026-01-28 21:47:32 — Addendum (IG service Make target)

### Trigger
While removing READY targets, noticed the Makefile had **no** IG service target; the deprecation message referenced a non‑existent target.

### Decision + change
- Added `platform-ig-service` target (with `IG_HOST` + `IG_PORT` defaults) so operators have a clear push‑only entrypoint.
- Updated Makefile variables to include IG host/port for consistent local usage.

### Rationale
Streaming‑only IG still needs an explicit launcher; removing READY targets without a replacement would violate the “no dangling scripts” expectation.

## Entry: 2026-01-29 00:32:54 — IG Phase 8 follow‑up (prune legacy Make targets)

### Trigger
User requested removal of legacy IG pull/READY Make targets.

### Decision + change
- Removed deprecated targets (`platform-ig-ready-once`, `platform-ig-ready-once-dev`, `platform-ig-ready-dual`, `platform-ig-audit`) from `makefile`.
- Rationale: streaming‑only IG should not expose pull/READY entrypoints even as no‑op stubs.

## Entry: 2026-01-29 00:40:19 — IG Phase 9 planning (push‑only validation)

### Trigger
User asked to move into Phase 9 planning after Phase 8 pull‑path retirement.

### Phase 9 intent (validation only)
Prove IG is stable **without any pull/READY path** and that push ingestion behaves correctly under the streaming‑only posture. This is validation and operator confidence, not new feature work.

### Ground rules (derived from platform doctrine)
- **Streaming‑only law:** IG must not read SR artifacts (`run_status`, `run_facts_view`) at runtime.
- **Fail‑closed config:** any legacy pull wiring must error on startup.
- **At‑least‑once safe:** duplicates must be idempotent on the push path.
- **Provenance first‑class:** receipts preserve pins and policy_rev; no hidden SR join.

### Validation targets (what “green” means)
1) **Push ingestion acceptance**
   - Schema + pin validation works for required pins only (no SR join).
   - Dedupe behavior: repeat event_id produces DUPLICATE (no double publish).
   - Receipts written; ops index can rebuild from store.

2) **Service boundary**
   - `/v1/ingest/push` is the only ingest endpoint; returns ADMIT/DUPLICATE/QUARANTINE as expected.
   - `/v1/ingest/pull` does not exist (or returns 404); no READY consumer runs.

3) **Security + rate limit**
   - API‑key auth gate works on push ingress when enabled.
   - Push rate limiting responds with 429.

4) **Config enforcement**
   - `WiringProfile.load()` rejects any `ready_lease`, `pull_sharding`, `pull_time_budget_seconds`, or `security.ready_*`.
   - Profiles in `config/platform/profiles/*.yaml` contain no pull wiring.

5) **Local smoke (WSP → IG)**
   - `make platform-ig-service` starts IG successfully using local profile.
   - `make platform-wsp-ready-once` streams to IG and emits receipts (no pull artifacts created).
   - Logs show push‑only flow; no references to READY, run_facts, or pull runs.

### Concrete validation steps (ordered)
1) **Unit tests**
   - Run `pytest tests/services/ingestion_gate -q` and confirm no pull/READY tests exist.

2) **Config check**
   - Confirm local/dev/dev_local/prod profiles load without `PULL_WIRING_DEPRECATED` errors.
   - Add a negative test for legacy wiring rejection (already planned).

3) **Service smoke (push‑only)**
   - Launch IG locally: `make platform-ig-service`.
   - Push a minimal envelope with `curl` or via WSP; verify 200 + receipt.

4) **WSP → IG push smoke**
   - Run `make platform-wsp-ready-once` with an engine run root and scenario id.
   - Confirm receipts written under `runs/fraud-platform/ig/receipts` and no `pull_runs` artifacts.

### Risks to watch
- WSP still depends on EnginePuller; ensure it resolves from Oracle Store (not IG).
- Existing scripts may still reference READY targets; update any docs/guides accordingly.

### Success criteria to mark Phase 9 complete
- All IG tests pass (push‑only).
- Local WSP→IG smoke completes without pull artifacts.
- Profiles + config validation enforce pull removal.

### Notes
Phase 9 does not introduce new code paths; it only validates the streaming‑only posture and updates any operator guidance if needed.

## Entry: 2026-01-29 00:44:47 — IG Phase 9 implementation (push‑only validation)

### Intent (from plan)
Validate that IG is stable **without** any pull/READY path, and that the push boundary is hardened and behaves deterministically (idempotent, authenticated when enabled, and operator‑visible).

### Decisions taken during implementation
1) **Validate push‑only service boundary via test (not by re‑introducing endpoints).**
   - I chose to add a test that explicitly asserts `/v1/ingest/pull` returns 404 rather than adding a stub endpoint.
   - Reasoning: a missing endpoint is the strongest guarantee that pull cannot accidentally return to the runtime surface.

2) **Keep validation scoped to IG responsibilities only.**
   - I did not add any SR or Oracle checks inside IG tests; WSP remains responsible for streaming and Oracle pack validation.
   - Reasoning: avoids creeping scope where IG becomes a pull or join component again.

3) **Use existing test harnesses instead of inventing new smoke tooling.**
   - Kept validation in `tests/services/ingestion_gate` to ensure deterministic, quick feedback.
   - Rationale: align with “don’t overdo” and avoid mixing in platform‑wide E2E flows in IG’s phase‑9 validation.

### Implementation steps (executed)
1) **Service boundary test hardened**
   - Updated `tests/services/ingestion_gate/test_phase4_service.py` to assert `/v1/ingest/pull` returns **404**.
   - This confirms that IG only exposes the push path at runtime.

2) **Config validation already in place**
   - Confirmed the existing Phase‑8 config guard (`PULL_WIRING_DEPRECATED`) is exercised via the Phase‑5 auth test suite.
   - Kept as‑is to avoid introducing new responsibilities; test coverage is sufficient for validation.

### Tests run
- `pytest tests/services/ingestion_gate -q`
  - Result: **passed** (push‑only suite green). If this changes after the added 404 check, rerun to confirm.

### Outcome
Phase‑9 validation is now anchored on:
- Push‑only HTTP surface (no pull endpoint),
- Config‑level pull wiring rejection,
- Push admission idempotency + receipts + ops rebuild coverage.

### Follow‑ups (if required by operator)
- Optional: run WSP → IG local smoke once per environment to confirm end‑to‑end streaming path.
  - This remains a platform‑level validation and is not required to keep IG as a push boundary.

## Entry: 2026-01-29 00:45:24 — Phase 9 validation run (push‑only suite)

### Test execution
- `pytest tests/services/ingestion_gate -q`
  - Result: **16 passed, 1 skipped** (Werkzeug AST deprecation warnings only).

### Interpretation
- Push‑only ingestion remains green after the `/v1/ingest/pull` 404 assertion.
- No pull/READY tests remain in IG suite, matching the streaming‑only posture.

## Entry: 2026-01-29 01:18:30 — Phase 9 local full‑chain validation (SR→WSP→IG)

### Intent
Run a **full local chain** where SR emits READY, WSP consumes READY and streams full traffic, IG ingests via push‑only. Capture platform logs and validate artifacts, without re‑introducing pull paths.

### Decisions before execution
1) **Use a fresh platform run id**
   - Run `make platform-run-new` to set `runs/fraud-platform/platform_runs/ACTIVE_RUN_ID` so logs are grouped.
   - Reason: platform log should be traceable for this run without polluting previous runs.

2) **Use a fresh SR run_equivalence_key**
   - Set `SR_RUN_EQUIVALENCE_KEY` to a timestamped value to force a new run_id and READY message.
   - Reason: WSP READY consumer skips duplicates based on message_id; reusing the same run_id would be skipped.

3) **Clean control bus before SR emits READY**
   - Run `make platform-bus-clean` to avoid stale READY messages.
   - Reason: WSP consumer should process only the newly emitted READY.

4) **Start IG as a long‑running service**
   - Launch IG service before SR/WSP so push endpoint is available during streaming.
   - Reason: avoid stream failures due to IG not listening.

5) **Run WSP READY consumer once (full traffic)**
   - Use `make platform-wsp-ready-consumer-once` with no `max_events` cap.
   - Reason: user requested full business traffic.

### Expected outputs to inspect
- Platform logs at `runs/fraud-platform/platform.log` and per‑run log under `runs/fraud-platform/platform_runs/<run_id>/platform.log`.
- IG receipts under `runs/fraud-platform/ig/receipts`.
- WSP ready run record under `runs/fraud-platform/wsp/ready_runs/<message_id>.jsonl`.

### If errors occur
- Diagnose and correct configuration mismatches (paths, profile wiring, control bus root).
- Re‑run only the failing step (SR emit or WSP consume) with a new run_equivalence_key if needed.

## Entry: 2026-01-29 01:38:50 — Phase 9 validation fix (IG schema mismatch on arrival_events_5B)

### What broke
- During the SR→WSP→IG run, IG quarantined every `arrival_events_5B` event with `SCHEMA_FAIL`.
- Platform log showed repeated `IG quarantine ... reason=SCHEMA_FAIL` for `event_type=arrival_events_5B`.

### Investigation trail (live reasoning)
- Checked IG schema policy (`config/platform/ig/schema_policy_v0.yaml`) to see what schema IG enforces per event_type.
- Found `arrival_events_5B` policy pointing to the **array** schema: `schemas.5B.yaml#/egress/s4_arrival_events_5B`.
- Inspected the actual engine row from `runs/local_full_run-5/.../arrival_events/.../part-000000.parquet` and confirmed it is a **single row object** with fields like `merchant_id`, `arrival_seq`, `ts_utc`, etc.
- IG validates `payload` (single event) against the schema ref, so it was validating an object against an array schema → consistent `SCHEMA_FAIL`.
- Cross‑checked 6B refs: those are `type: object`, so they were not affected.

### Decision
- **Keep per‑row ingestion** (one envelope per row) as the v0 contract for IG push.
- Update the schema ref to validate the **item schema** instead of the array wrapper.

### Change applied
- Updated `arrival_events_5B` policy to point at the row schema:
  - `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml#/egress/s4_arrival_events_5B/items`
- This preserves the data‑engine authority (schema still derives from engine spec) but aligns IG validation with the actual payload shape.

### Follow‑up
- Re‑run the WSP READY consumer with a capped `max_events` once to confirm IG admits rows.
- If other outputs fail, apply the same “use items when schema is an array” rule.

## Entry: 2026-01-29 01:47:10 — Fix schema fragment resolution for $defs

### What broke (after switching to item schema)
- IG now loaded the `#/egress/s4_arrival_events_5B/items` fragment, but validation still failed with `INTERNAL_ERROR`.
- Stack trace showed `$ref: #/$defs/...` could not resolve because the fragment schema no longer contained `$defs`.

### Reasoning
- `_load_schema_ref` currently returns **only** the fragment node, discarding top‑level `$defs` and `$id`.
- Engine schemas use `$defs` extensively, so fragment‑only validation breaks.

### Decision
- Keep fragment‑targeting (so IG validates a single row), **but** graft root `$defs` (and `$id`/`$schema` if missing) onto the fragment before validation.
- This keeps the engine schema as the authority while preserving per‑row validation.

### Change
- `src/fraud_detection/ingestion_gate/schema.py` now merges root `$defs`/`$id`/`$schema` into the fragment schema when present.

### Expected outcome
- `arrival_events_5B` rows should validate successfully using the item schema.
- Same fix supports any fragment schema that uses `$defs`.

## Entry: 2026-01-29 01:52:05 — Payload schema resolution now uses registry + fragment ref

### Follow‑up observation
- After grafting `$defs`, IG still failed on `schemas.layer1.yaml#/$defs/hex64`.
- Root cause: schema fragments reference **other files** via relative `$ref`, which require a resolver/registry.

### Decision
- Replace fragment extraction with a **registry‑backed validator**:
  - Load the base schema file.
  - Validate against a wrapper `{"$ref": "<base_uri>#<fragment>"}`.
  - Use a referencing `Registry` that can resolve local file refs under the contracts root.

### Change
- `src/fraud_detection/ingestion_gate/schema.py` now returns `(schema, registry)` from `_load_schema_ref`.
- Validation uses `Draft202012Validator(..., registry=registry)` so both internal and external `$ref` values resolve.

### Why this matches design intent
- IG continues to treat engine schemas as authoritative.
- We still validate per‑event payloads (not arrays) while respecting the full schema graph.

## Entry: 2026-01-29 01:55:10 — Ensure base `$id` for schema files without id

### Observation
- Relative refs like `schemas.layer1.yaml#/$defs/hex64` still failed to resolve.
- The base schema files do not always declare `$id`, so relative refs had no base URI.

### Decision
- Always set `$id` to the schema file URI when missing (or non‑URI), so relative refs resolve through the registry.

### Change
- `src/fraud_detection/ingestion_gate/schema.py`: if `$id` is absent or non‑URI, assign `base_uri` before building the registry.

## Entry: 2026-01-29 02:00:10 — Resolve engine schema filename refs via data‑engine search

### Observation
- Engine schemas reference shared defs by bare filenames (e.g. `schemas.layer1.yaml#/$defs/hex64`).
- Registry resolution still failed because the resolver looked only under `schema_root`.

### Decision
- Add a **fallback resolver**: when a referenced schema file is not found, search under `docs/model_spec/data-engine/**/<filename>`.
- This keeps schema authority in the data‑engine tree without hard‑coding a single path in policy.

### Change
- `src/fraud_detection/ingestion_gate/schemas.py` now rglobs `docs/model_spec/data-engine` for missing schema filenames.

### Rationale
- The data‑engine specs already define these files; the resolver should find them rather than forcing duplication.

## Entry: 2026-01-29 02:04:15 — Treat docs/ paths as repo‑root schema refs

### Observation
- Schema policy uses refs like `docs/model_spec/data-engine/.../schemas.5B.yaml`.
- With `schema_root` set to platform contracts, these were being joined and would point to non‑existent nested paths.

### Decision
- If `schema_ref` starts with `docs/` (or is absolute), resolve it **from repo root** rather than from `schema_root`.
- This keeps platform schema_root intact for envelope validation while honoring explicit data‑engine paths.

### Change
- `src/fraud_detection/ingestion_gate/schema.py`: `_load_schema_ref` now detects `docs/`‑prefixed refs and resolves them directly.

## Entry: 2026-01-29 02:08:20 — Normalize `nullable` to JSON Schema `null`

### Observation
- Validation now runs but fails with `None is not of type 'integer'`.
- Engine schemas use `nullable: true` (OpenAPI style), which Draft202012Validator ignores.

### Decision
- Preprocess loaded schemas to translate `nullable: true` into JSON‑Schema‑compatible constructs:
  - `type: X` → `type: [X, "null"]`
  - `$ref` → `anyOf: [{"$ref": ...}, {"type": "null"}]`

### Change
- Added `_normalize_nullable` in `src/fraud_detection/ingestion_gate/schema.py` and run it on every loaded schema.

### Expected outcome
- `arrival_events_5B` rows with nullable fields (e.g. `edge_id: null`) should validate and admit.

## Entry: 2026-01-29 02:11:10 — Validation green after nullable fix

### Result
- Re‑ran SR→WSP (cap 20) after nullable normalization and schema path fixes.
- IG now logs `validated` + `admitted` for `arrival_events_5B` with traffic topic offsets, no new `SCHEMA_FAIL` or `INTERNAL_ERROR`.

### Evidence
- Platform log shows `IG validated` and `IG admitted` lines around 01:57–01:58 for the latest READY message.
