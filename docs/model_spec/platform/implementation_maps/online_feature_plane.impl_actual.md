# Online Feature Plane Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:13:10 — Phase 4 planning kickoff (OFP scope + pins)

### Problem / goal
Prepare Phase 4.3 by locking OFP v0 outer-contract decisions (inputs, provenance, and serve semantics) before code is written.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- Platform rails (canonical envelope, ContextPins, no-PASS-no-read).
- RTDL contracts in `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- OFP is **hot-path projector + serve surface**; consumes admitted EB events; no batch-only posture.
- Scope is **run/world-scoped by ContextPins**; no cross-run features in v0.
- Serving is **as-of time**: DF calls `get_features(as_of_time_utc = event ts_utc)`; no hidden “now.”
- Provenance required in every response: `input_basis` (EB offsets), feature group versions, `graph_version` (if IEG consulted), and `snapshot_hash`.
- Idempotent update key must include `(stream, partition, offset, key_type, key_id, group_name, group_version)`; duplicates/out-of-order are normal.
- Feature definitions are versioned artifacts; OFP records the activated feature-def policy revision in snapshot provenance.

### Planned implementation scope (Phase 4.3)
- Define Postgres schema for feature state + checkpoints.
- Implement EB consumer (file-bus first; Kinesis later) with idempotent apply.
- Implement `get_features` API (internal call surface) returning deterministic snapshot + provenance.
- Emit OFP health/lag signals for DL input (metrics/logs; no business events).

---

## Entry: 2026-02-06 15:36:00 — Phase 4.3 planning expansion (DoD-closure map + narrative alignment)

### Problem / goal
The OFP component build plan is still too high-level to execute against the expanded Phase 4.3 DoDs. We need a closure-grade plan that is:
- aligned to RTDL pre-design decisions,
- consistent with the pinned flow narrative (`EB -> OFP (projector)`, optional `OFP <-> IEG`, `DF -> OFP get_features`),
- explicit on what can be finished within OFP versus what is integration-dependent (DF/DL/OFS/MPR).

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 4.3 scaffold)

### Key planning decisions
- OFP intake source in v0 is **admitted EB traffic**, not IEG-only. IEG is optional query support for identity-resolution / graph_version provenance.
- OFP must remain a **projector + serve surface**: no hidden batch-only semantics and no implicit "latest" serving.
- `input_basis` semantics are pinned as **exclusive-next offsets**; one coherent basis token per response.
- Snapshot provenance is first-class and must always include ContextPins + feature versions + `input_basis` + `snapshot_hash` (+ `graph_version` when OFP consulted IEG).
- Build plan must separate:
  - component-closed DoDs (contracts, hash determinism, state/checkpoint atomics, serve semantics, health),
  - integration DoDs (DF contract compatibility, DL degrade consumption, OFS parity gates).

### Planned edits (documentation only in this step)
1. Expand `online_feature_plane.build_plan.md` into phased sections that map directly to platform 4.3.A-4.3.H.
2. Add per-phase closure criteria that include:
   - exact invariants,
   - expected artifacts/contracts,
   - test gates and parity checks.
3. Correct platform 4.3 wording drift in `platform.build_plan.md` so OFP intake and optional IEG usage match pinned narrative.
4. Record all updates in the daily logbook.

### Invariants to preserve while planning
- No Oracle reads by OFP in hot-path.
- No cross-run feature state mixing.
- Idempotent apply under at-least-once delivery.
- Deterministic snapshot hash and replay reproducibility.
- Explicit failure posture (no fabricated context).

---

## Entry: 2026-02-06 16:18:13 — Phase 1 implementation start (contracts + provenance authority)

### Problem / goal
Begin Phase 1 implementation by making the OFP contract surface explicit and enforceable in code/tests: request shape, success response provenance requirements, error posture, and deterministic snapshot hash behavior.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 1 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- RTDL contract folder `docs/model_spec/platform/contracts/real_time_decision_loop/`

### Decisions for this implementation slice
- Add explicit OFP API contracts under RTDL contracts:
  - `ofp_get_features_request.schema.yaml`
  - `ofp_get_features_response.schema.yaml`
  - `ofp_get_features_error.schema.yaml`
- Keep `feature_snapshot.schema.yaml` as the canonical by-ref artifact contract; OFP response references the same provenance fields and semantics.
- Add a minimal OFP contract helper module for deterministic `snapshot_hash` canonicalization and explicit error response mapping.
- Add targeted tests for:
  - request validation failures,
  - snapshot hash determinism,
  - error semantics (code + retryable posture),
  - success response required fields.

### Planned files
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_request.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_response.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_error.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
- `docs/model_spec/platform/contracts/README.md`
- `src/fraud_detection/online_feature_plane/__init__.py`
- `src/fraud_detection/online_feature_plane/contracts.py`
- `tests/services/online_feature_plane/test_contracts.py`

---

## Entry: 2026-02-06 16:20:47 — Phase 1 implemented (contracts + provenance helpers)

### Changes applied
- Added OFP request/response/error schemas to the RTDL contract set:
  - `ofp_get_features_request.schema.yaml`
  - `ofp_get_features_response.schema.yaml`
  - `ofp_get_features_error.schema.yaml`
- Updated RTDL contract indexes to include the OFP schemas:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- Added OFP contract helper module:
  - `src/fraud_detection/online_feature_plane/contracts.py`
  - `src/fraud_detection/online_feature_plane/__init__.py`
- Helper module provides:
  - request validation (`validate_get_features_request`)
  - deterministic snapshot hash canonicalization (`build_snapshot_hash`)
  - explicit success/error response builders with pinned error semantics.
- Added tests for Phase 1 contract behavior:
  - `tests/services/online_feature_plane/test_contracts.py`

### Validation
- `python -m pytest tests/services/online_feature_plane/test_contracts.py -q` -> `4 passed`.

### Notes
- This implementation closes Phase 1 contract authority at component level.
- Projector/serve runtime and store mechanics remain Phase 2+ work.

---

## Entry: 2026-02-06 16:22:00 — Phase 2 implementation plan (EB projector core + atomic checkpoints)

### Problem / goal
Implement OFP Phase 2 so the component can consume admitted EB events, apply deterministic/idempotent updates, persist state/checkpoints atomically, and expose `input_basis` for downstream provenance.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- Existing EB adapters (`EventBusReader`, `KinesisEventBusReader`)

### Design choices for Phase 2
- Build a minimal OFP runtime package with:
  - `config.py` for profile loading and run-scoped DSN resolution
  - `store.py` for projection state + idempotency + checkpoint persistence (SQLite/Postgres)
  - `projector.py` for EB intake (`--once` and continuous mode)
- Idempotency key for apply path in v0 runtime:
  - `(stream_id, topic, partition, offset_kind, offset)` for at-least-once replay safety.
- State model for Phase 2:
  - deterministic aggregate rows keyed by ContextPins + `key_type/key_id` + `group_name/group_version`
  - initial feature payload: event_count, optional amount sum, last_event_ts_utc
- Input basis exposure:
  - computed from per-partition checkpoints as exclusive-next offsets with stable basis digest.

### Planned files
- `src/fraud_detection/online_feature_plane/config.py`
- `src/fraud_detection/online_feature_plane/store.py`
- `src/fraud_detection/online_feature_plane/projector.py`
- `tests/services/online_feature_plane/test_phase2_projector.py`

### Validation plan
- Unit/integration tests with file-bus fixtures:
  - duplicate replay does not double-apply state
  - checkpoint vector advances deterministically
  - input_basis is emitted and stable for same replay basis
  - restart/re-run yields same state + basis

---

## Entry: 2026-02-06 16:42:00 - Phase 2 implemented (projector/store core + atomic checkpoints)

### Problem / goal
The initial Phase 2 implementation landed with a corrupted `store.py` class layout (mixed SQLite/Postgres methods), which broke projector persistence (`SqliteOfpStore` attempted Postgres connect path). Goal was to restore a clean backend split and close Phase 2 DoDs with passing tests.

### What was changed
- Rebuilt `src/fraud_detection/online_feature_plane/store.py` with clean backend boundaries:
  - `SqliteOfpStore` owns SQLite DDL, idempotent apply, checkpoint advancement, metrics, and basis reconstruction.
  - `PostgresOfpStore` owns Postgres DDL and equivalent apply/checkpoint/metrics behavior.
  - `build_store(...)` retains DSN-based backend selection and sqlite DSN normalization.
- Preserved pinned Phase 2 invariants:
  - idempotent apply key: `(stream_id, topic, partition, offset_kind, offset)`,
  - atomic per-record mutation: metrics + apply + checkpoint within one DB transaction scope,
  - deterministic `input_basis` digest from exclusive-next checkpoint vector.
- Hardened projector test fixture against ambient env run-scope gates:
  - `tests/services/online_feature_plane/test_phase2_projector.py` now sets `required_platform_run_id` explicitly in the generated test profile to avoid host `PLATFORM_RUN_ID` bleed-through.

### Validation results
- Command: `python -m pytest tests/services/online_feature_plane -q`
- Result: `6 passed` (contracts + phase2 projector/store tests).
- Verified outcomes:
  - replaying same offset is `DUPLICATE` and does not increment state totals,
  - projector file-bus run applies events, writes feature state, and produces deterministic checkpoint basis (`offset=2` after two records),
  - second `run_once` is a no-op (`processed == 0`) under unchanged input.

### Phase status impact
- OFP Phase 2 DoDs are closed at component scope for v0 local-parity behavior.
- Remaining Phase 3+ work (feature definition authority, snapshot materialization, serve API semantics, replay parity, health integration) is unchanged.

---

## Entry: 2026-02-06 16:48:36 - Phase 3 implementation plan (feature definition authority + window/TTL policy)

### Problem / goal
Phase 2 projector/store mechanics are green, but Phase 3 DoDs remain open: OFP still treats feature semantics as inline config (`feature_group_name/version`) without a singular versioned feature-definition authority, window/TTL policy is not explicit in runtime state, and active policy revision is not carried into runtime provenance.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 3)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.B)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (window-based OFP TTL)
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md` (active `feature_def_policy_rev`, singular definition authority)

### Decision
Implement Phase 3 as a strict configuration/runtime hardening slice:
1. Introduce a versioned OFP feature-definition artifact (`features_ref`) with explicit policy id/revision and group window/TTL rules.
2. Make runtime fail closed when this revisioned artifact is missing/invalid; no implicit "latest" fallback.
3. Thread active `feature_def_policy_rev` into OFP runtime metadata/provenance state so subsequent serve/snapshot phases can stamp outputs without ambiguity.

### Planned file changes
- Add authoritative v0 feature definition artifact:
  - `config/platform/ofp/features_v0.yaml`
- Extend OFP config loader:
  - `src/fraud_detection/online_feature_plane/config.py`
  - parse `features_ref`, validate policy revision, parse window/TTL specs (default 1h/24h/7d), and include policy revision in `run_config_digest`.
- Extend OFP store metadata for provenance:
  - `src/fraud_detection/online_feature_plane/store.py`
  - add `ofp_projection_meta` table and read accessor carrying `feature_def_policy_rev` and `run_config_digest`.
- Wire projector to use authoritative group config and policy metadata:
  - `src/fraud_detection/online_feature_plane/projector.py`
- Add/extend tests:
  - `tests/services/online_feature_plane/test_phase2_projector.py` (adapt profile helper if needed)
  - `tests/services/online_feature_plane/test_phase3_policy.py` (new)

### Invariants to enforce
- One authoritative active feature-definition revision per OFP runtime profile.
- Explicit windows/TTL policy available in-memory; no hidden defaults except the documented v0 default set.
- Active revision identity is queryable from OFP runtime metadata.
- Existing Phase 2 idempotency/checkpoint guarantees remain unchanged.

### Validation plan
- `python -m pytest tests/services/online_feature_plane -q`
- New assertions:
  - invalid/missing policy revision fails closed,
  - window/TTL parsing and defaults deterministic,
  - runtime metadata includes active feature_def policy revision/digest.

---

## Entry: 2026-02-06 16:54:32 - Phase 3 implemented (feature policy authority + window/TTL rules + provenance metadata)

### Summary of implementation
Phase 3 was implemented to remove OFP semantic ambiguity and pin feature semantics to a singular revisioned artifact.

### Changes applied
- Added authoritative OFP feature-definition artifact:
  - `config/platform/ofp/features_v0.yaml`
  - includes `policy_id`, `revision`, and explicit window/TTL definitions.
- Extended OFP runtime config parsing in `src/fraud_detection/online_feature_plane/config.py`:
  - loads `policy.features_ref` (or `OFP_FEATURES_REF`) as the only definition source,
  - fails closed when policy revision metadata is missing/invalid,
  - parses explicit window/TTL durations and applies documented v0 defaults (`1h/24h/7d`) when omitted,
  - validates configured active group (`feature_group_name/version`) against policy content,
  - includes `feature_def_policy_rev` + group window specs in `run_config_digest` canonicalization.
- Wired feature policy revision into runtime/store provenance:
  - `src/fraud_detection/online_feature_plane/projector.py` passes policy id/revision/content digest to the store at startup.
  - `src/fraud_detection/online_feature_plane/store.py` now persists `ofp_projection_meta` (SQLite/Postgres) with:
    - `run_config_digest`
    - `feature_def_policy_id`
    - `feature_def_revision`
    - `feature_def_content_digest`
  - added `projection_meta()` accessor for downstream provenance use.
- Updated platform profile stanzas to pin features artifact explicitly:
  - `config/platform/profiles/local.yaml`
  - `config/platform/profiles/local_parity.yaml`
  - `config/platform/profiles/dev.yaml`
  - `config/platform/profiles/prod.yaml`
- Added/updated OFP tests:
  - `tests/services/online_feature_plane/test_phase2_projector.py` (profile fixture now includes `features_ref`)
  - `tests/services/online_feature_plane/test_phase3_policy.py` (new)

### Validation
- Command: `python -m pytest tests/services/online_feature_plane -q`
- Result: `9 passed`.
- Phase 3-specific checks covered:
  - fail-closed behavior when policy revision is missing,
  - deterministic default window/TTL expansion,
  - projector/store metadata carries active feature policy revision and digest.

### DoD closure impact
- Phase 3 DoDs are closed at OFP component scope:
  - singular feature definition source,
  - explicit window/TTL policy,
  - no implicit "latest" revision,
  - revision carried into runtime provenance.
- Integration into serve snapshots/DF responses remains part of later phases (Phase 4+).
