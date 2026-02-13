# Case Management Implementation Map
_As of 2026-02-09_

---

## Entry: 2026-02-09 03:26PM - Phase 5 planning kickoff (CM outer contract to executable plan)

### Objective
Start Case Management planning with an explicit, auditable execution map aligned to platform Phase 5 and pinned flow semantics.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5 sections)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

### Decisions captured (planning posture)
- CM truth ownership remains strict: case objects + append-only timeline only.
- CM intake will be explicit `CaseTrigger` driven in v0; no implicit multi-stream parsing boundary.
- v0 case identity is pinned to `CaseSubjectKey=(platform_run_id,event_class,event_id)` with deterministic `case_id`.
- CM->LS and CM->AL are handshake boundaries only; CM never claims LS or AL truth before downstream durable ack/outcome.
- Collision policy is explicit: same deterministic key + payload mismatch is anomaly/fail-closed, never overwrite.

### Planned implementation sequencing
1. Phase 1 contracts/identity pinning.
2. Trigger intake + idempotent case creation.
3. Timeline truth and derived workflow views.
4. Evidence-by-ref corridor.
5. Label emission handshake to LS.
6. Manual actions through AL.
7. Observability/governance/reconciliation.
8. Integration closure with parity evidence.

### Invariants to enforce
- ContextPins and by-ref evidence are mandatory across all CM boundaries.
- Append-only timeline semantics (no destructive edits).
- Actor attribution is mandatory on timeline and governance surfaces.
- At-least-once safe behavior for all inbound and outbound CM interactions.

## Entry: 2026-02-09 03:30PM - Pre-change lock for Phase 1 implementation (contracts + deterministic IDs)

### Problem / goal
Close CM Phase 1 by implementing concrete contract and identity artifacts that can be reused by later CM phases.

### Decisions locked before code
- CaseSubjectKey remains canonical `(platform_run_id, event_class, event_id)`.
- CaseTrigger shape is explicit and idempotent with stable `case_trigger_id`.
- Timeline event dedupe/identity uses `(case_id, timeline_event_type, source_ref_id)` and deterministic hash ID.
- Collision rule is fail-closed (same dedupe key + different payload hash => anomaly path).

### Planned module set
- `src/fraud_detection/case_mgmt/contracts.py`
- `src/fraud_detection/case_mgmt/ids.py`
- `src/fraud_detection/case_mgmt/__init__.py`
- tests under `tests/services/case_mgmt/` for contracts and identity determinism.

## Entry: 2026-02-09 03:40PM - Phase 1 implemented (CM contracts + deterministic IDs)

### Changes applied
- Added deterministic identity helpers:
  - `src/fraud_detection/case_mgmt/ids.py`
  - recipes pinned for `case_id`, `case_trigger_id`, `case_timeline_event_id`, and canonical payload hashes.
- Added CM contract validators:
  - `src/fraud_detection/case_mgmt/contracts.py`
  - `CaseSubjectKey`, `CaseTrigger`, `CaseTimelineEvent`, `EvidenceRef`, strict pin checks, deterministic-id validation, collision fail-closed checks.
- Added package exports:
  - `src/fraud_detection/case_mgmt/__init__.py`
- Added authoritative schemas:
  - `docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml`
  - `docs/model_spec/platform/contracts/case_and_labels/case_timeline_event.schema.yaml`
- Added taxonomy pin config:
  - `config/platform/case_mgmt/taxonomy_v0.yaml`
- Added tests:
  - `tests/services/case_mgmt/test_phase1_contracts.py`
  - `tests/services/case_mgmt/test_phase1_ids.py`

### Validation
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py` -> `12 passed`.
- `python -m py_compile src/fraud_detection/case_mgmt/__init__.py src/fraud_detection/case_mgmt/contracts.py src/fraud_detection/case_mgmt/ids.py` -> pass.

### Notes
- Identity and payload-hash recipes are deterministic and stable under evidence-ref ordering differences.
- Contract posture is fail-closed on deterministic key mismatches and payload hash mismatches.

## Entry: 2026-02-09 04:26PM - Pre-change lock for Phase 2 (CaseTrigger intake + idempotent case creation)

### Objective
Implement CM Phase 2 by adding an intake boundary that consumes CaseTrigger contracts directly and enforces idempotent case creation with deterministic duplicate behavior.

### Inputs / authorities
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/implementation_maps/case_trigger.build_plan.md` (Phase 6 CM integration gate)
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- Existing CM contract/identity modules:
  - `src/fraud_detection/case_mgmt/contracts.py`
  - `src/fraud_detection/case_mgmt/ids.py`

### Decisions locked before coding
1. Create `case_mgmt/intake.py` as explicit CM trigger intake service + persistence boundary.
2. Intake must parse/validate incoming triggers using `CaseTrigger.from_payload(...)` to guarantee direct contract conformance.
3. Case create semantics:
   - case identity = deterministic `case_id` from `CaseSubjectKey`,
   - first trigger creates case record,
   - subsequent triggers with same case subject attach to existing case,
   - no-merge policy remains enforced.
4. Trigger replay/collision semantics:
   - same `case_trigger_id` + same payload hash => `DUPLICATE_TRIGGER` (no new timeline append),
   - same `case_trigger_id` + different payload hash => `TRIGGER_PAYLOAD_MISMATCH` fail-closed.
5. Timeline semantics for this phase:
   - append one deterministic `CASE_TRIGGERED` timeline event per new trigger (`source_ref_id=case_trigger_id`),
   - duplicate trigger intake produces no duplicate timeline truth.
6. Backend posture:
   - sqlite and postgres parity in the intake store layer.

### Planned file changes
- New module: `src/fraud_detection/case_mgmt/intake.py`
- Export update: `src/fraud_detection/case_mgmt/__init__.py`
- New tests: `tests/services/case_mgmt/test_phase2_intake.py`

### Validation gate
- Compile checks on new/updated CM files.
- Pytest: CM Phase1+2 plus CaseTrigger Phase1-5 + IG onboarding regression set.

## Entry: 2026-02-09 04:33PM - Phase 2 implemented and validated (CaseTrigger intake + idempotent case creation)

### Implementation completed
1. Added explicit CM intake boundary:
- `src/fraud_detection/case_mgmt/intake.py`

2. Updated package exports:
- `src/fraud_detection/case_mgmt/__init__.py`

3. Added Phase 2 test suite:
- `tests/services/case_mgmt/test_phase2_intake.py`

### Runtime mechanics delivered
- Intake parses incoming payloads through `CaseTrigger.from_payload(...)`; invalid trigger contracts are rejected fail-closed before persistence.
- Case creation is idempotent on deterministic `case_id` (`CaseSubjectKey` identity). Cases are unique per `case_subject_hash`; no-merge posture is enforced.
- Trigger intake ledger outcomes are explicit:
  - `NEW_TRIGGER`
  - `DUPLICATE_TRIGGER`
  - `TRIGGER_PAYLOAD_MISMATCH`
- Collision discipline:
  - same `case_trigger_id` + same payload hash => duplicate/no-op,
  - same `case_trigger_id` + different payload hash => mismatch anomaly, no timeline append.
- Timeline behavior:
  - new triggers append one deterministic `CASE_TRIGGERED` timeline event,
  - duplicate/mismatch triggers do not append duplicate truth (`TIMELINE_NOOP`).

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase2_intake.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py`
  - result: `16 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `36 passed`

### Phase closure statement
- CM Phase 2 DoD is satisfied:
  - trigger intake consumes CaseTrigger contract directly,
  - case creation is idempotent on CaseSubjectKey,
  - duplicate trigger behavior is deterministic and no-merge remains enforced.

## Entry: 2026-02-09 04:36PM - Phase 2 hardening addendum (defensive JSON decode on lookup path)

### Why this addendum was needed
- Post-closure review identified a small robustness gap: lookup helpers in `case_mgmt/intake.py` parsed persisted JSON without guarding decode failures.
- While persisted rows are expected to be valid, defensive handling avoids lookup-path crashes under corrupted/test-fixture rows.

### Change applied
- `src/fraud_detection/case_mgmt/intake.py`
  - `_json_to_dict(...)` now catches `json.JSONDecodeError` and returns `{}` instead of raising.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py` -> pass.
- `python -m pytest -q tests/services/case_mgmt/test_phase2_intake.py` -> `4 passed`.
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py` -> `16 passed`.
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `36 passed`.

## Entry: 2026-02-09 05:00PM - Pre-change lock for Phase 3 (append-only timeline truth + workflow projection)

### Objective
Start CM Phase 3 by implementing the first production-safe slice of S2/S3 semantics:
- explicit append API for non-trigger timeline events with actor attribution,
- deterministic, projection-only case header/status derivation from timeline events,
- query surfaces for linked refs and state/time-window filters.

### Problem framing
- Phase 2 currently appends `CASE_TRIGGERED` events from intake and stores core case/timeline rows.
- Missing for Phase 3 closure:
  - actor-attributed append path for broader timeline event vocabulary,
  - deterministic workflow projection from timeline events only,
  - query surfaces beyond `case_id` lookup (`decision_id`/`action_outcome_id`/`audit_record_id`/`event_id`, queue/state, time-window).
- If we defer this, later phases (manual actions, label handshake) would risk hidden mutable state shortcuts.

### Alternatives considered
1. Add a separate S3 projection component now with independent tables/worker loop.
- Deferred: valid end-state, but too large for first Phase 3 slice; introduces premature run/operate complexity before projection semantics are pinned in tests.

2. Compute projections on read from existing timeline rows only (no projection cache), with deterministic ordering and filter support.
- Selected for this slice: keeps truth boundary strict, avoids hidden mutable bypass, and is sufficient to close core Phase 3 mechanics.

3. Store mutable header fields directly in `cm_cases` and update on writes.
- Rejected as primary source of truth: risks drift from append-only timeline and violates Phase 3 projection-only posture.

### Decisions locked before edits
1. Extend `CaseTriggerIntakeLedger` (existing CM boundary) with Phase 3 APIs rather than adding a parallel store class.
2. Add actor attribution at timeline row level (`actor_id`, `source_type`) and enforce it on non-trigger appends.
3. Add append semantics for timeline events:
- same deterministic key + same payload hash => duplicate no-op,
- same deterministic key + different payload hash => fail-closed mismatch anomaly,
- no updates/deletes to historical timeline rows.
4. Add deterministic projection function derived exclusively from ordered timeline events (order: `observed_time`, tie-break `case_timeline_event_id`).
5. Add link-index table for queryability by refs extracted from source refs, evidence refs, and known timeline payload fields.
6. Query surfaces to provide now:
- by `case_id` timeline + projection,
- by linked ref (`event_id`, `decision_id`, `action_outcome_id`, `audit_record_id`),
- by derived `status`/`queue`,
- by last-activity time window.

### Planned file changes
- `src/fraud_detection/case_mgmt/intake.py`
  - Phase 3 append/projection/query APIs and schema extensions.
- `src/fraud_detection/case_mgmt/__init__.py`
  - export new Phase 3 surfaces.
- `tests/services/case_mgmt/test_phase3_projection.py`
  - append-only + projection + linked-ref/time-window query matrix.
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`
  - expand Phase 3 section into executable sub-steps and DoD checks.

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase3_projection.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase3_projection.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py`
- CaseTrigger/IG regression to guard boundary compatibility:
  - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

## Entry: 2026-02-09 05:08PM - Phase 3 implemented and validated (append-only timeline truth + workflow projection)

### Implementation completed
1. Extended CM intake ledger with explicit Phase 3 timeline append surfaces:
- `append_timeline_event(...)` with required `actor_id`, `source_type`, and append timestamp.
- Deterministic append outcomes:
  - `TIMELINE_EVENT_NEW`
  - `TIMELINE_EVENT_DUPLICATE`
  - `TIMELINE_EVENT_PAYLOAD_MISMATCH`

2. Added projection and query APIs on CM ledger:
- `project_case(case_id)`
- `query_case_projections(status/queue/ref/time-window filters)`
- `find_case_ids_by_linked_ref(ref_type, ref_id)`

3. Added schema surfaces needed for Phase 3 queryability/auditability:
- `cm_case_timeline_stats` (actor/source attribution + replay/mismatch counters)
- `cm_case_timeline_mismatches` (fail-closed mismatch evidence)
- `cm_case_timeline_links` (linked-ref index by `ref_type/ref_id/observed_time`)

4. Updated trigger-intake timeline appends to include explicit system actor attribution:
- actor pinned as `SYSTEM::case_trigger_intake` + `source_type=SYSTEM`.

5. Added Phase 3 validation matrix:
- `tests/services/case_mgmt/test_phase3_projection.py`
  - append-only + duplicate/mismatch behavior,
  - projection mapping for status/queue/pending flags,
  - linked-ref queries (`decision_id`, `audit_record_id`) and state/time-window filters,
  - deterministic ordering under same-timestamp timeline appends.

### Key decisions during implementation
- Actor attribution is stored as timeline metadata persisted alongside each timeline event via `cm_case_timeline_stats`; timeline event content remains append-only and immutable.
- Projection is computed from timeline rows ordered by `observed_time ASC` then deterministic `case_timeline_event_id ASC`, avoiding hidden mutable-case-state bypass.
- Linked-ref queryability is implemented by indexing deterministic refs extracted from case-subject/event source refs/evidence refs/timeline payload keys, keeping evidence-by-ref posture while enabling operational queries.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase3_projection.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase3_projection.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py`
  - result: `20 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`

### Phase closure statement
- CM Phase 3 DoD is satisfied:
  - timeline truth is append-only with actor attribution,
  - workflow state is derived projection-only,
  - required query surfaces for refs/state/time windows are implemented,
  - deterministic behavior under replay/concurrent timestamp ties is evidenced.

## Entry: 2026-02-09 05:12PM - Phase 3 hardening addendum (timeline stats bootstrap on legacy rows)

### Why this addendum was applied
- During Phase 3 validation review, timeline duplicate/mismatch handling depended on `cm_case_timeline_stats` existence for each event id.
- Legacy rows (or partial migrations) could have timeline rows without stats rows, causing replay/mismatch counters to skip durable updates.

### Change applied
- `src/fraud_detection/case_mgmt/intake.py`
  - In `_append_timeline_tx`, when stats row is missing for an existing timeline event id, bootstrap stats row with actor/source and zero counters before continuing duplicate/mismatch handling.

### Validation refresh
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase3_projection.py` -> pass.
- `python -m pytest -q tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase2_intake.py` -> `8 passed`.
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py` -> `20 passed`.
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `45 passed`.

## Entry: 2026-02-09 05:16PM - Pre-change lock for Phase 4 (evidence-by-ref resolution corridor)

### Objective
Implement CM Phase 4 by adding a policy-gated evidence-resolution corridor that keeps evidence by-reference, records append-only status evolution, and makes missing/unresolvable evidence explicit without mutating case truth.

### Problem framing
- Phase 3 added linked-ref indexing and queryability, but there is no explicit CM evidence-resolution workflow boundary yet.
- Missing for Phase 4 closure:
  - policy-gated request/resolve corridor for evidence refs,
  - auditable, append-only status evolution per evidence ref,
  - explicit representation of `pending/unavailable` outcomes.
- Without this corridor, later CM phases may embed ad-hoc evidence reads and lose deterministic/auditable behavior.

### Alternatives considered
1. Embed evidence resolution state directly into `cm_case_timeline` rows.
- Rejected: mixes investigation truth with operational resolution state and increases mutation risk.

2. Keep resolution as in-memory helper only.
- Rejected: no durable audit trail and not replay-safe.

3. Add a dedicated CM evidence corridor store with append-only status events and policy gate.
- Selected: aligns with append-only/no-bypass rails and keeps timeline truth immutable.

### Decisions locked before edits
1. Add new module `src/fraud_detection/case_mgmt/evidence.py` for corridor logic (separate from timeline truth tables).
2. Add policy config `config/platform/case_mgmt/evidence_resolution_policy_v0.yaml` and loader in module.
3. Corridor behavior:
- deterministic `request_id = hash(case_id + case_timeline_event_id + ref_type + ref_id)[:32]`,
- request gate validates allowed ref types + actor principal prefixes,
- append-only status events with explicit statuses:
  - `PENDING`, `RESOLVED`, `UNAVAILABLE`, `QUARANTINED`, `FORBIDDEN`,
- terminal statuses are idempotent (duplicate attempts return current snapshot; no rewrite).
4. Minimal metadata posture:
- store only case/timeline ids, ref type/id, actor/source, status/reason, optional locator ref,
- no external payload snapshots.
5. Add API surfaces for tests/operations:
- `request_resolution(...)`, `record_resolution(...)`, `snapshot(...)`, `list_case_snapshots(...)`.

### Planned file changes
- New code:
  - `src/fraud_detection/case_mgmt/evidence.py`
  - `config/platform/case_mgmt/evidence_resolution_policy_v0.yaml`
- Export update:
  - `src/fraud_detection/case_mgmt/__init__.py`
- New tests:
  - `tests/services/case_mgmt/test_phase4_evidence_resolution.py`
- Plan/status updates after validation:
  - `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/evidence.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase4_evidence_resolution.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase4_evidence_resolution.py`
- CM regression:
  - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py`
- CaseTrigger/IG regression:
  - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

## Entry: 2026-02-09 05:22PM - Phase 4 implemented and validated (evidence-by-ref resolution corridor)

### Implementation completed
1. Added dedicated CM evidence corridor module:
- `src/fraud_detection/case_mgmt/evidence.py`

2. Added Phase 4 policy config:
- `config/platform/case_mgmt/evidence_resolution_policy_v0.yaml`

3. Updated CM exports for Phase 4 surfaces:
- `src/fraud_detection/case_mgmt/__init__.py`

4. Added Phase 4 test matrix:
- `tests/services/case_mgmt/test_phase4_evidence_resolution.py`

### Corridor mechanics delivered
- Deterministic request identity:
  - `request_id = sha256(case_id + case_timeline_event_id + ref_type + ref_id)[:32]`.
- Policy-gated request intake:
  - allowed ref types + allowed actor principal prefixes + allowed source types.
- Append-only status evolution with explicit states:
  - `PENDING`, `RESOLVED`, `UNAVAILABLE`, `QUARANTINED`, `FORBIDDEN`.
- Explicit fail-closed posture:
  - unsupported ref type / actor prefix produce `FORBIDDEN` snapshots with reason code.
- Minimal metadata-only storage:
  - stores only case/timeline ids, ref identifiers, actor/source, status/reason, optional locator ref.
  - no evidence payload copies.
- No CM truth mutation:
  - resolution corridor writes only corridor tables and does not mutate `cm_cases` or `cm_case_timeline` truth rows.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/evidence.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase4_evidence_resolution.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase4_evidence_resolution.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py`
  - result: `24 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`

### Phase closure statement
- CM Phase 4 DoD is satisfied:
  - refs remain minimal/by-ref,
  - resolution path is policy-gated and auditable,
  - missing/unresolvable evidence is explicit (`UNAVAILABLE`) without mutating case truth.

## Entry: 2026-02-09 05:27PM - Pre-change lock for Phase 5 (CM -> LS label emission handshake)

### Objective
Implement CM Phase 5 by adding deterministic LabelAssertion emission handshake logic that keeps LS as truth owner while CM records pending/accepted/rejected lifecycle on timeline.

### Problem framing
- CM Phase 1..4 are closed; there is no runtime module yet for CM label handshake behavior.
- Missing for Phase 5 closure:
  - deterministic LabelAssertion emission surface from CM,
  - pending-first timeline semantics before LS durable ack,
  - explicit ack/reject handling with append-only timeline events,
  - retry-safe idempotent emission tracking.

### Alternatives considered
1. Implement direct LS writes inline inside CM timeline append code.
- Rejected: mixes handshake side effects into core timeline store and increases coupling.

2. Add dedicated CM label handshake coordinator with pluggable LS writer boundary.
- Selected: keeps truth ownership boundaries explicit and testable.

3. Delay retry bookkeeping until Phase 7.
- Rejected: Phase 5 DoD explicitly requires idempotent retry-safe pending posture.

### Decisions locked before edits
1. Add new module `src/fraud_detection/case_mgmt/label_handshake.py` with:
- deterministic assertion construction via `label_store.contracts.LabelAssertion`,
- handshake state ledger (pending/accepted/rejected + attempts + mismatch anomaly),
- pending-first timeline append, then terminal ack/reject timeline append only after LS write outcome.
2. Keep CM truth discipline:
- CM appends `LABEL_PENDING` before submission,
- CM appends `LABEL_ACCEPTED` only on LS `ACCEPTED`,
- CM appends `LABEL_REJECTED` only on LS `REJECTED`,
- LS unavailable/unknown outcome leaves CM in pending state (no false acceptance claim).
3. Idempotency and collision handling:
- use deterministic `label_assertion_id` from `case_timeline_event_id + LabelSubjectKey + label_type`,
- same assertion id + payload hash match => duplicate-safe,
- same assertion id + payload hash mismatch => fail-closed anomaly (`PAYLOAD_MISMATCH`).
4. Add policy config for emission guardrails (actor prefix/source type/label type allowlist + retry cap).

### Planned files
- New code:
  - `src/fraud_detection/case_mgmt/label_handshake.py`
  - `config/platform/case_mgmt/label_emission_policy_v0.yaml`
- Export update:
  - `src/fraud_detection/case_mgmt/__init__.py`
- New tests:
  - `tests/services/case_mgmt/test_phase5_label_handshake.py`
- Status updates after validation:
  - `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/label_handshake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase5_label_handshake.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py`
- CM regression:
  - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py`
- CaseTrigger/IG regression:
  - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

## Entry: 2026-02-09 05:32PM - Phase 5 correction lock (SQLite nested-write hazard + handshake sequencing)

### New risk discovered before Phase 5 code finalization
- The in-progress `label_handshake.py` draft calls `CaseTriggerIntakeLedger.append_timeline_event(...)` from inside an open label-emission DB transaction.
- On SQLite this is a high-risk nested-write pattern (same DB file, separate connections) and can produce `database is locked` under normal operation.
- This also weakens failure semantics because pending timeline rows can commit independently while the enclosing emission transaction rolls back on writer exceptions.

### Correction decision
1. Rework Phase 5 handshake sequencing to avoid nested write transactions entirely:
- perform emission-row upsert/mismatch checks in short, isolated DB transactions,
- perform timeline appends outside those transactions via CM intake ledger API,
- apply status updates in subsequent short transactions.
2. Preserve DoD semantics explicitly:
- `LABEL_PENDING` emitted before LS write attempt,
- `LABEL_ACCEPTED`/`LABEL_REJECTED` emitted only after LS durable outcome,
- unknown LS outcome remains `PENDING` and never claims accepted truth.
3. Add exception hardening:
- LS writer exceptions map to `PENDING` with explicit reason (`LS_WRITE_EXCEPTION`) rather than aborting the handshake path.
4. Add stronger matrix tests covering:
- accepted/rejected/pending transitions,
- duplicate-safe re-submit,
- deterministic payload mismatch fail-closed,
- retry limit rejection path.

### Why this is the selected path
- Satisfies v0 rails (`at-least-once`, `append-only truth`, `fail-closed on ambiguity`) while removing a concrete local-parity deadlock risk.
- Keeps CM/LS boundary pluggable without forcing a wider refactor of `CaseTriggerIntakeLedger` internals.

## Entry: 2026-02-09 05:42PM - Phase 5 implemented and validated (CM -> LS label emission handshake)

### Implementation completed
1. Implemented lock-safe CM label handshake coordinator:
- `src/fraud_detection/case_mgmt/label_handshake.py`
- deterministic LabelAssertion build using LS contract,
- emission state ledger (`PENDING/ACCEPTED/REJECTED`) with retry counts,
- payload-mismatch anomaly recording (`cm_label_emission_mismatches`).

2. Added Phase 5 policy config:
- `config/platform/case_mgmt/label_emission_policy_v0.yaml`
- allowlists for `label_type`, actor prefixes, source types, and `max_retry_attempts`.

3. Updated CM public exports:
- `src/fraud_detection/case_mgmt/__init__.py` now exports Phase 5 constants/types/policy loader/coordinator.

4. Added Phase 5 validation matrix:
- `tests/services/case_mgmt/test_phase5_label_handshake.py`.

### Key mechanics delivered
- Pending-first semantics:
  - CM appends `LABEL_PENDING` before LS write attempt.
- LS truth ownership preserved:
  - `LABEL_ACCEPTED` appended only on LS `ACCEPTED`,
  - `LABEL_REJECTED` appended only on LS `REJECTED` or retry-limit fail-closed,
  - LS unknown/exception path remains `PENDING` (`LS_WRITE_EXCEPTION:*` reason retained).
- Deterministic idempotency/fail-closed:
  - stable `label_assertion_id` from LS contract,
  - same assertion id + payload mismatch => `PAYLOAD_MISMATCH` result + durable mismatch log,
  - source-case-event reference must exist in CM timeline for the same case (`fail closed` when missing).
- Local parity hardening:
  - removed nested write pattern that could lock SQLite (`intake timeline append` is no longer executed under open emission transaction).

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/label_handshake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase5_label_handshake.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py`
  - result: `6 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py`
  - result: `30 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`

### Phase closure statement
- CM Phase 5 DoD is satisfied:
  - LabelAssertion emission is deterministic and policy-gated,
  - pending/accepted/rejected lifecycle is append-only and provenance-carrying,
  - CM does not claim label truth before LS durable acknowledgement,
  - retry/idempotency/mismatch fail-closed behavior is evidenced.

## Entry: 2026-02-09 05:49PM - Pre-change lock for Phase 6 (CM -> AL manual action handshake)

### Objective
Implement CM Phase 6 by adding a deterministic, policy-gated manual ActionIntent emission boundary to AL plus by-ref ActionOutcome attachment back to CM timeline.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md` (ActionIntent key + outcome attach by `action_outcome_id`)
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md` sections `J-CM-02`, `B2`, `I-J12`, `I-J13`
- Existing AL contract: `src/fraud_detection/action_layer/contracts.py`

### Problem framing
Current CM phases close trigger/timeline/evidence/label lanes, but no explicit CM->AL manual-action boundary exists. Missing pieces for Phase 6 closure:
1. deterministic ActionIntent identity/idempotency contract at CM boundary,
2. submission-state recording without claiming execution truth,
3. attach-by-ref outcome linkage (`action_outcome_id`) into append-only timeline.

### Alternatives considered
1. Reuse label-handshake module pattern and store everything in timeline only.
- Rejected: submission-state and retry posture become opaque and difficult to query/operate.

2. Directly mutate case projection status on action submit/outcome updates.
- Rejected: violates append-only truth discipline.

3. Add dedicated CM action-handshake module with durable intent ledger + append-only timeline events.
- Selected: aligns with authority notes (CM requests only, AL executes, outcomes by-ref).

### Decisions locked before edits
1. New module `src/fraud_detection/case_mgmt/action_handshake.py` with:
- deterministic `action_idempotency_key = hash(case_id + source_case_event_id + action_kind + target_ref)`,
- deterministic `action_id` and fallback deterministic `decision_id` when explicit decision id is unavailable,
- AL ActionIntent payload validation via `action_layer.ActionIntent`.
2. Submission-state discipline:
- CM appends baseline `ACTION_INTENT_REQUESTED` (`submit_status=REQUESTED`),
- writer outcomes map to explicit statuses:
  - `SUBMITTED` (accepted),
  - `PRECHECK_REJECTED` (rejected),
  - `SUBMIT_FAILED_RETRYABLE` (pending/exception),
  - `SUBMIT_FAILED_FATAL` (retry ceiling),
- statuses are appended as timeline events (append-only; dedupe by stable source_ref suffix).
3. Outcome attachment discipline:
- CM attaches AL outcomes only by refs through `ACTION_OUTCOME_ATTACHED`,
- includes `ACTION_OUTCOME` ref + optional DLA/EB refs,
- no execution payload snapshots in CM.
4. Local parity lock-safety:
- avoid nested write transactions when appending timeline rows (same correction posture as Phase 5).
5. Projection hardening:
- `ACTION_INTENT_REQUESTED` handling will key off `submit_status` so rejected/fatal submission states are explicit and not treated as pending execution.

### Planned files
- New:
  - `src/fraud_detection/case_mgmt/action_handshake.py`
  - `config/platform/case_mgmt/action_emission_policy_v0.yaml`
  - `tests/services/case_mgmt/test_phase6_action_handshake.py`
- Update:
  - `src/fraud_detection/case_mgmt/intake.py` (projection semantics for submit statuses)
  - `src/fraud_detection/case_mgmt/__init__.py` (Phase 6 exports)
  - build-plan/impl-map/logbook status files after validation.

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/action_handshake.py src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase6_action_handshake.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase6_action_handshake.py`
- CM regression:
  - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py`
- CaseTrigger/IG regression:
  - existing `45` test matrix.

## Entry: 2026-02-09 05:55PM - Phase 6 implemented and validated (CM -> AL manual action boundary)

### Implementation completed
1. Added CM action-handshake coordinator:
- `src/fraud_detection/case_mgmt/action_handshake.py`
- deterministic `action_idempotency_key = hash(case_id + source_case_event_id + action_kind + target_ref)`,
- deterministic `action_id` + fallback deterministic `decision_id`,
- ActionIntent payload validation through AL contract (`action_layer.ActionIntent`),
- durable submission ledger + payload-mismatch anomaly ledger,
- by-ref ActionOutcome attachment to CM timeline.

2. Added Phase 6 policy config:
- `config/platform/case_mgmt/action_emission_policy_v0.yaml`
- allowlists for action kinds, actor principal prefixes, source types,
- fixed `origin=CASE`, AL policy-rev pins, and retry budget (`max_submit_attempts`).

3. Updated CM exports:
- `src/fraud_detection/case_mgmt/__init__.py` now exports Phase 6 constants, types, coordinator, and policy loader.

4. Updated projection semantics for action submission truth:
- `src/fraud_detection/case_mgmt/intake.py`
- `ACTION_INTENT_REQUESTED` now reads `submit_status` to distinguish pending vs precheck/fatal failures,
- `ACTION_OUTCOME_ATTACHED` treats `FAILED|DENIED|TIMED_OUT|UNKNOWN` as failed posture.

5. Added Phase 6 validation matrix:
- `tests/services/case_mgmt/test_phase6_action_handshake.py`.

### Key mechanics delivered
- CM remains request-only for side effects (no execution path in CM).
- Submission-state timeline discipline is append-only:
  - `REQUESTED` baseline event,
  - then explicit submission-state event: `SUBMITTED` | `PRECHECK_REJECTED` | `SUBMIT_FAILED_RETRYABLE` | `SUBMIT_FAILED_FATAL`.
- AL outcome closure is attach-by-ref only:
  - `ACTION_OUTCOME_ATTACHED` carries ids/status/refs,
  - includes `ACTION_OUTCOME` ref and optional DLA/EB refs,
  - no execution payload snapshots stored in CM.
- Fail-closed posture:
  - source-case-event mismatch rejects submission,
  - same idempotency key + payload hash mismatch is recorded and rejected.
- Lock-safety posture preserved:
  - timeline appends are not executed under open action-ledger write transactions (no nested SQLite write-lock pattern).

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/action_handshake.py src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase6_action_handshake.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase6_action_handshake.py`
  - result: `6 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py`
  - result: `36 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`

### Phase closure statement
- CM Phase 6 DoD is satisfied:
  - manual actions are emitted to AL with deterministic idempotency + evidence refs,
  - AL outcomes attach back by reference only,
  - failures/denials are explicit in append-only CM timeline without side-effect truth claims in CM.

## Entry: 2026-02-09 06:02PM - Pre-change lock for Phase 7 (CM observability/governance/reconciliation)

### Objective
Close CM Phase 7 by delivering run-scoped operational counters, governance lifecycle emission, low-noise anomaly surfacing, and CM contribution artifacts under `case_labels/reconciliation`.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md` (Phase 7 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.8 closure expectations)
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- Existing component patterns:
  - `src/fraud_detection/case_trigger/observability.py`
  - `src/fraud_detection/case_trigger/reconciliation.py`
  - `src/fraud_detection/decision_log_audit/observability.py`
  - `src/fraud_detection/platform_governance/writer.py`

### Problem framing
CM Phases 1..6 are implemented, but CM still lacks a unified run-scoped report surface that can be consumed by operations and platform reconciliation. Required gaps:
1. No durable CM counters artifact for run-level posture (`case_triggers`, `cases_created`, timeline and label lifecycle counts).
2. No deterministic lifecycle governance emission derived from CM timeline facts.
3. No single low-noise anomaly summary for mismatch/forbidden/unavailable lanes.
4. No case/labels-plane reconciliation contribution written by CM.

### Discovery before edits
- An interrupted run already created `src/fraud_detection/case_mgmt/observability.py` in the worktree.
- Decision: treat it as draft input, not as accepted implementation; validate against current rails and fill missing wiring/tests/docs before closure claim.

### Alternatives considered
1. Emit governance events inline during every CM mutation path (intake/label/action/evidence).
- Rejected for now: wider intrusive edits across stable Phase 1..6 paths and higher regression surface.
2. Build an offline run reporter over CM tables and emit idempotent governance/reconciliation artifacts from that reporter.
- Selected: least invasive to truth paths, deterministic from append-only tables, compatible with current v0 parity posture.

### Decisions locked before code edits
1. Keep CM truth ownership unchanged; observability module is read-only on CM domain tables and write-only for observability/governance outputs.
2. Counters will be filtered run-scoped by `pins` (`platform_run_id`, `scenario_run_id`) via `cm_cases.pins_json` membership.
3. Governance lifecycle events are mapped from timeline event types and deduped with marker files (`event_id` markers) to ensure replay-safe emission.
4. Anomaly reporting is lane-based and low-noise (counts only; no raw payload leaks).
5. CM writes contribution artifact to `runs/<platform_run_id>/case_labels/reconciliation/case_mgmt_reconciliation.json`.
6. Phase closure requires dedicated Phase 7 tests plus CM regression and CaseTrigger/IG boundary regression.

### Planned files
- New:
  - `tests/services/case_mgmt/test_phase7_observability.py`
- Update:
  - `src/fraud_detection/case_mgmt/observability.py` (finalize draft and contract hardening)
  - `src/fraud_detection/case_mgmt/__init__.py` (Phase 7 exports)
  - `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/observability.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase7_observability.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase7_observability.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

## Entry: 2026-02-09 06:09PM - Phase 7 implemented and validated (CM observability/governance/reconciliation)

### Implementation completed
1. Finalized CM observability reporter module:
- `src/fraud_detection/case_mgmt/observability.py`
- run-scoped metrics now include Phase 5.8 names (`case_triggers`, `cases_created`, `timeline_events_appended`, `label_assertions`, `labels_pending`, `labels_accepted`, `labels_rejected`) while retaining compatibility aliases used by earlier matrices.
- lifecycle governance extraction from timeline now carries actor attribution + normalized evidence refs and pin enrichment (`manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` when present).
- optional-table-safe query posture added for phased/partial deployments (missing optional tables resolve to empty lanes instead of failing reporter execution).

2. Reconciliation artifact posture aligned to authority path intent:
- `export()` now writes Case+Labels contribution to both:
  - `runs/<platform_run_id>/case_labels/reconciliation/<YYYY-MM-DD>.json`
  - `runs/<platform_run_id>/case_labels/reconciliation/case_mgmt_reconciliation.json`
- component-local reconciliation remains at:
  - `runs/<platform_run_id>/case_mgmt/reconciliation/last_reconciliation.json`

3. Wiring/exports updates:
- `src/fraud_detection/case_mgmt/__init__.py` exports Phase 7 surfaces (`CaseMgmtRunReporter`, thresholds, error type).
- `src/fraud_detection/platform_reporter/run_reporter.py` reconciliation-ref discovery now includes:
  - `case_mgmt/reconciliation/last_reconciliation.json`
  - `case_labels/reconciliation/case_mgmt_reconciliation.json`

4. Added Phase 7 matrix tests:
- `tests/services/case_mgmt/test_phase7_observability.py`
- coverage includes:
  - full export path (metrics, governance, anomalies, case_labels reconciliation),
  - idempotent lifecycle governance emission (marker-deduped),
  - strict run-scope filtering by `platform_run_id` + `scenario_run_id`,
  - optional-table-absent resilience.

### Key mechanics delivered
- Governance lifecycle emission is deterministic and replay-safe:
  - event id basis: `sha256(platform_run_id|case_timeline_event_id|lifecycle_type)`
  - marker files prevent duplicate governance writes under repeated export.
- Low-noise anomaly reporting:
  - structured lane counts only (`TRIGGER/TIMELINE/LABEL/ACTION payload mismatch`, `EVIDENCE_FORBIDDEN`, `EVIDENCE_UNAVAILABLE`).
- Reconciliation contribution under case/labels prefix is now explicit and date-stamped to support daily append posture.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/observability.py src/fraud_detection/case_mgmt/__init__.py src/fraud_detection/platform_reporter/run_reporter.py tests/services/case_mgmt/test_phase7_observability.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase7_observability.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py`
  - result: `40 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`
  - result: `2 passed`

### Phase closure statement
- CM Phase 7 DoD is satisfied:
  - run-scoped counters are emitted,
  - lifecycle governance events are emitted with actor attribution and evidence refs,
  - anomaly lanes are structured/low-noise,
  - CM contributes reconciliation under case/labels prefix.

## Entry: 2026-02-09 06:12PM - Pre-change lock for Phase 8 (CM integration closure and parity proof)

### Objective
Close CM Phase 8 by producing explicit end-to-end integration proof and negative-path parity evidence for the Case+Labels continuity lane.

### Authority inputs used
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md` (Phase 8 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5.9 integration closure gate)
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- Existing component parity closure pattern: `tests/services/case_trigger/test_phase8_validation_matrix.py`

### Problem framing
CM Phases 1..7 are green, but Phase 8 requires concrete closure artifacts proving full continuity and fail-closed behavior under replay/negative paths. Missing gates to close:
1. No dedicated CM integration matrix proving `DLA/AL evidence -> CaseTrigger -> CM timeline -> LabelAssertion submit -> LS ack`.
2. No CM-owned parity proof artifacts for `20`/`200` event monitored runs under deterministic checks.
3. No CM-owned negative-path proof artifact covering duplicate trigger replay, payload mismatch fail-closed, LS unavailable retry posture/idempotency.

### Alternatives considered
1. Reuse only existing unit tests from Phases 2..7 as closure evidence.
- Rejected: does not provide an explicit phase-level integrated proof artifact.
2. Add a dedicated Phase 8 CM matrix that composes existing CM lanes and emits proof files under run-scoped reconciliation path.
- Selected: aligns with CaseTrigger Phase 8 evidence style and satisfies auditable closure requirements.

### Decisions locked before code edits
1. Add `tests/services/case_mgmt/test_phase8_validation_matrix.py` as the authoritative CM Phase 8 matrix.
2. Matrix will include:
- single-flow continuity proof,
- parameterized parity proof for `20` and `200` events,
- negative-path injections for duplicate replay, hash mismatch fail-closed, LS unavailable + retry idempotency.
3. Proof artifacts will be written under:
- `runs/fraud-platform/<platform_run_id>/case_mgmt/reconciliation/phase8_parity_proof_{20,200}.json`
- `runs/fraud-platform/<platform_run_id>/case_mgmt/reconciliation/phase8_negative_path_proof.json`
4. Build-plan and platform status will only mark Phase 8 complete after matrix + regressions pass.

### Planned files
- New:
  - `tests/services/case_mgmt/test_phase8_validation_matrix.py`
- Update:
  - `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/case_mgmt.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/platform.impl_actual.md`
  - `docs/logbook/02-2026/2026-02-09.md`

### Validation plan
- `python -m py_compile tests/services/case_mgmt/test_phase8_validation_matrix.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase8_validation_matrix.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`

## Entry: 2026-02-09 06:17PM - Phase 8 implemented and validated (CM integration closure + parity proof)

### Implementation completed
1. Added dedicated CM Phase 8 validation matrix:
- `tests/services/case_mgmt/test_phase8_validation_matrix.py`
- test coverage includes:
  - end-to-end continuity proof from RTDL evidence lanes into CM + LS handshake,
  - component-local parity proof for `20` and `200` events,
  - negative-path proof for duplicate replay, trigger payload mismatch fail-closed, and LS-unavailable retry/idempotency.

2. Added parity proof artifact generation (run-scoped, auditable):
- `runs/fraud-platform/platform_20260209T210000Z/case_mgmt/reconciliation/phase8_parity_proof_20.json`
- `runs/fraud-platform/platform_20260209T210000Z/case_mgmt/reconciliation/phase8_parity_proof_200.json`
- `runs/fraud-platform/platform_20260209T210000Z/case_mgmt/reconciliation/phase8_negative_path_proof.json`

### Key mechanics delivered
- End-to-end continuity assertion now proves:
  - Trigger ingress with DLA/decision evidence refs,
  - CM timeline append continuity,
  - AL action submission + by-ref action outcome attach,
  - Label assertion submission and LS durable ack path (`LABEL_PENDING` -> `LABEL_ACCEPTED`).
- Parity matrix enforces deterministic idempotency at scale:
  - duplicate trigger replay remains duplicate-safe,
  - duplicate label submission remains duplicate-safe after terminal acceptance,
  - anomaly total remains zero in nominal parity loops.
- Negative-path matrix enforces fail-closed behavior:
  - same trigger identity + payload drift -> `TRIGGER_PAYLOAD_MISMATCH`,
  - LS write exception -> pending posture,
  - retry preserves assertion identity and converges via deterministic retry lane.

### Validation evidence
- `python -m py_compile tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py`
  - result: `44 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `45 passed`
- `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py`
  - result: `2 passed`

### Phase closure statement
- CM Phase 8 DoD is satisfied:
  - end-to-end CM continuity evidence exists,
  - required negative-path proofs exist,
  - monitored parity artifacts are captured and referenced.
- This closes CM-side integration closure and advances platform Phase `5.9` gating; full plane closure still depends on Label Store timeline/as-of integration closure evidence.

## Entry: 2026-02-09 08:07PM - Pre-change lock: CaseMgmt live worker onboarding (meta-layer closure)

### Scope
Implement CaseMgmt daemon worker consuming `case_trigger` stream for active run, persisting timeline/workflow state, and driving deterministic CM->LS auto-label handshake for live-plane continuity.

### Locked mechanics
- Consume `case_trigger` envelopes from case topic.
- Intake through `CaseTriggerIntakeLedger` with idempotent replay/mismatch behavior preserved.
- For newly-ingested triggers, submit deterministic auto label assertions through `CaseLabelHandshakeCoordinator` into LS writer boundary.
- Export CM run-scoped metrics/health/reconciliation/governance each loop via `CaseMgmtRunReporter`.

### Policy choices
- Auto-label defaults pinned to policy-safe values (`fraud_disposition` + `FRAUD_SUSPECTED`, source_type `AUTO`, actor `SYSTEM::case_mgmt_worker`).
- Evidence refs inherit trigger evidence + case-event linkage.

### Non-goals for this pass
- Manual investigator action loops are unchanged and remain existing service interfaces.
