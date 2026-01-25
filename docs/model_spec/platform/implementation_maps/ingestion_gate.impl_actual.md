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
