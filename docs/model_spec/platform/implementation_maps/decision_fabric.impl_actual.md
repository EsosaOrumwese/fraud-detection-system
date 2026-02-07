# Decision Fabric Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:13:45 — Phase 4 planning kickoff (DF scope + output contracts)

### Problem / goal
Prepare Phase 4.4 by locking DF v0 inputs/outputs and decision provenance requirements before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Platform rails (canonical envelope, ContextPins, no-PASS-no-read, append-only).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DF is **EB-driven only**: consumes admitted events, emits DecisionResponse + ActionIntent via IG→EB.
- Decision boundary time is `ts_utc` (domain time). No hidden “now.”
- Decision provenance must include: `bundle_ref`, `snapshot_hash`, `graph_version`, `eb_offset_basis`, `degrade_posture`, `policy_rev`, `run_config_digest`.
- DecisionResponse event_id is deterministic: `H("decision_response", ContextPins, input_event_id, decision_scope)`.
- ActionIntent event_id is deterministic: `H("action_intent", ContextPins, input_event_id, action_domain)`; ActionIntent carries its own `idempotency_key` for AL.
- Degrade posture is a hard constraint; DF fails closed when DL/Registry/OFP is unavailable.

### Planned implementation scope (Phase 4.4)
- Implement EB consumer for traffic + context topics.
- Build deterministic decision plan: resolve registry bundle, fetch features (OFP), consult DL, produce DecisionResponse + ActionIntents.
- Publish outputs through IG admission (no direct EB writes).

---

## Entry: 2026-02-07 02:53:29 — Plan: expand DF component build plan phase-by-phase from platform 4.4

### Problem / goal
Current `decision_fabric.build_plan.md` is too compact (3 broad phases) for direct implementation execution. Platform `Phase 4.4` was expanded into explicit `4.4.A..4.4.L` DoD gates, so DF component planning must now be expanded with component-granular phases and acceptance checks.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (expanded Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Existing DF build/impl docs.

### Decision trail (live)
1. Keep DF plan strictly component-scoped; do not absorb AL/DLA ownership from platform Phase 4.5.
2. Expand DF into implementation phases that map cleanly to platform 4.4 concerns:
   - trigger boundary,
   - DL/Registry integration,
   - context/feature acquisition and budget handling,
   - decision/intent synthesis and publish boundary,
   - determinism/idempotency,
   - observability/validation.
3. Make each phase contain executable DoD checks with explicit artifacts/tests expected.
4. Preserve progressive elaboration doctrine while still giving enough detail to execute v0 without ambiguity.

### Planned edits
- Replace the short three-phase DF plan with a phased v0 map and explicit DoD checklists aligned to platform 4.4.A-L.
- Mark integration-dependent checks (that require AL/DLA closure) explicitly as pending gates, not hidden assumptions.

---

## Entry: 2026-02-07 02:55:08 — Applied DF phase-by-phase build plan expansion

### Change applied
Updated `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` from a 3-phase high-level outline to an executable 8-phase plan with explicit DoD checklists.

### New DF phase map (v0)
1. Contracts + deterministic identity
2. Inlet boundary + trigger gating
3. DL integration + fail-safe enforcement
4. Registry bundle resolution + compatibility
5. Context/features acquisition + decision-time budgets
6. Decision synthesis + intent emission
7. Idempotency/checkpoints/replay safety
8. Observability/validation/closure boundary

### Alignment checks
- Mapped to platform Phase 4.4 gates (A-L) without absorbing AL/DLA authority from Phase 4.5.
- Preserved RTDL pre-design defaults (fail-closed compatibility, join budgets, deterministic resolver/output behavior, provenance minimums).
- Added explicit closure statement to keep component-green scope clear vs integration-pending gates.

---

## Entry: 2026-02-07 10:27:17 — Phase 1 implementation plan (contracts + deterministic identity)

### Problem / goal
Begin Decision Fabric implementation by closing Phase 1 DoD end-to-end:
- pin DF contracts and provenance requirements in code-facing helpers,
- lock deterministic identity recipes for decision and action events,
- pin RTDL event taxonomy/schema compatibility behavior (major mismatch fail-closed),
- keep docs/index references drift-safe.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 1)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml`

### Decision trail (before coding)
1. Create a new `src/fraud_detection/decision_fabric` package now, but keep Phase 1 runtime-surface minimal:
   - contracts/parsing helpers,
   - deterministic identity helpers,
   - taxonomy compatibility helper.
2. Preserve current contract file names to avoid churn (`decision_payload.schema.yaml` remains authoritative for DecisionResponse payload in v0), while making documentation explicit that DF `decision_response` event_type uses that schema path.
3. Identity recipes will be canonicalized with stable JSON hashing (sorted keys, compact separators, UTF-8) and explicit recipe constants for:
   - `decision_id`,
   - DecisionResponse envelope `event_id`,
   - ActionIntent envelope `event_id`,
   - ActionIntent `idempotency_key`.
4. Taxonomy compatibility guard:
   - allowed `event_type` set is explicit for Phase 1 (`decision_response`, `action_intent`),
   - `schema_version` parser enforces `v<major>[.<minor>]` form,
   - major version mismatch fails closed by raising typed contract/taxonomy error.
5. Add DF Phase 1 tests under `tests/services/decision_fabric/` for schema validity checks, deterministic identity behavior, and taxonomy compatibility enforcement.

### Files planned
- New:
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `src/fraud_detection/decision_fabric/contracts.py`
  - `src/fraud_detection/decision_fabric/ids.py`
  - `src/fraud_detection/decision_fabric/taxonomy.py`
  - `tests/services/decision_fabric/test_phase1_contracts.py`
  - `tests/services/decision_fabric/test_phase1_ids.py`
  - `tests/services/decision_fabric/test_phase1_taxonomy.py`
- Update:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
  - `docs/model_spec/platform/contracts/README.md`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 1 status)

### Invariants to enforce
- DF contract helpers reject missing required provenance keys.
- Identity digests are deterministic across process runs and key orderings.
- Taxonomy acceptance is explicit and fail-closed for unknown event type or incompatible schema major.
- No silent alias drift in contract docs/index for decision_response/action_intent.

### Validation plan
- Run `python -m pytest tests/services/decision_fabric -q`.
- Re-run with package-level import smoke:
  - `python -c "import fraud_detection.decision_fabric as df; print(sorted(df.__all__))"`.
- Append implementation closure details and evidence after tests are green.

---

## Entry: 2026-02-07 10:30:56 — Phase 1 implementation closure (DF contracts + deterministic identity)

### What was implemented
1. Added DF Phase 1 package scaffold:
   - `src/fraud_detection/decision_fabric/__init__.py`
   - `src/fraud_detection/decision_fabric/contracts.py`
   - `src/fraud_detection/decision_fabric/ids.py`
   - `src/fraud_detection/decision_fabric/taxonomy.py`
2. Implemented contract helpers:
   - `DecisionResponse.from_payload(...)` and `ActionIntent.from_payload(...)` enforce required provenance and identity fields,
   - explicit validation for pins, policy revision, degrade posture mask shape, bundle identity, and lineage linkage (`validate_action_intent_lineage`).
3. Implemented deterministic identity recipes (v1):
   - decision ID: deterministic 32-hex hash over source event + scope + bundle + EB basis,
   - DecisionResponse event ID and ActionIntent event ID: deterministic recipe hashes over source event + pins scope + domain/scope,
   - ActionIntent idempotency key: deterministic recipe hash over source event + pins scope + action domain.
4. Implemented fail-closed taxonomy/compatibility guard:
   - allowlisted event types (`decision_response`, `action_intent`),
   - parsed schema versions as `v<major>[.<minor>]`,
   - major mismatch raises explicit compatibility error (fail-closed posture).
5. Updated contract index/readme references to make DecisionResponse payload authority explicit:
   - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
   - `docs/model_spec/platform/contracts/README.md`

### Validation results
- `python -m pytest tests/services/decision_fabric -q` -> `14 passed`.
- `PYTHONPATH=.;src python -c "import fraud_detection.decision_fabric as df; print(sorted(df.__all__))"` succeeded.

### DoD closure mapping (Phase 1)
- DecisionResponse + ActionIntent required provenance/identity fields: complete.
- Deterministic identity rules pinned in code (decision_id + output event IDs + idempotency key): complete.
- Event taxonomy + compatibility posture (major mismatch fail-closed): complete.
- Contract docs/index reflect authoritative schema paths without introducing duplicate schema files: complete.

### Follow-on boundary
- Phase 2 will implement runtime inlet gating against admitted traffic topics and trigger allowlists.

---

## Entry: 2026-02-07 10:32:23 — Phase 1 test hardening follow-up

### Problem / observation
After Phase 1 closure, the identity determinism test for reordered offsets used a dict-expansion expression that could mask intended field ordering variation.

### Corrective change
- Updated `tests/services/decision_fabric/test_phase1_ids.py` to build a dedicated `reordered_offsets_basis` object explicitly, ensuring the test truly exercises order-insensitive normalization inside DF identity hashing.

### Re-validation
- `python -m pytest tests/services/decision_fabric -q` -> `14 passed`.

### Outcome
- No behavioral code changes were needed.
- Phase 1 closure remains valid with stronger determinism evidence.

---
