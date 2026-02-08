# Online Feature Plane Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-08 13:27:06 - OFP parity Postgres-default alignment note (reviewer item 8)

### Problem framing
OFP runtime supports both SQLite and Postgres locators, but parity launcher defaults were still passing run-root filesystem locators. That creates backend drift versus dev/prod posture.

### Decision
Switch parity launcher defaults and runbook guidance to Postgres DSN-backed OFP stores:
- projection store
- snapshot index store

### Why this is the right scope
- No OFP business logic changes are required.
- Keeps dual-backend support intact while making local_parity behavior operationally closer to dev/prod.
- Reduces parity-only drift caused by implicit filesystem defaults.

### Guardrails
- Keep explicit override path for local SQLite testing.
- Ensure runbook clearly separates "default parity backend" from "optional local override."

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

---

## Entry: 2026-02-06 17:06:05 - Phase 4 implementation plan (snapshot materialization + index)

### Problem / goal
Phase 4 DoDs require OFP to emit immutable by-ref feature snapshot artifacts and persist snapshot index metadata for deterministic retrieval by hash. Current OFP has projector state/checkpoints only; no snapshot artifact/index surface exists yet.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 4)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.C, 4.3.D)
- `docs/model_spec/platform/contracts/real_time_decision_loop/feature_snapshot.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_response.schema.yaml`
- `src/fraud_detection/online_feature_plane/contracts.py` (`build_snapshot_hash`)

### Decision
Implement Phase 4 as component-scoped primitives that Phase 5 serve API can call directly:
1. Add OFP snapshot materializer that:
   - reads projection state + input basis + feature policy metadata,
   - constructs canonical snapshot payload,
   - computes deterministic `snapshot_hash`,
   - writes immutable snapshot artifact to object store by-ref path.
2. Add snapshot index store with SQLite/Postgres backends:
   - index by `snapshot_hash`,
   - persist provenance metadata and artifact ref,
   - support deterministic lookup by hash.
3. Keep graph_version nullable in Phase 4 (IEG integration remains later); preserve contract fields where available.

### Planned file changes
- New runtime modules:
  - `src/fraud_detection/online_feature_plane/snapshots.py`
  - `src/fraud_detection/online_feature_plane/snapshot_index.py`
- Extend OFP config:
  - `src/fraud_detection/online_feature_plane/config.py`
  - add snapshot index DSN + snapshot object-store root wiring defaults.
- Extend OFP store query helpers if needed:
  - `src/fraud_detection/online_feature_plane/store.py`
- Export Phase 4 primitives:
  - `src/fraud_detection/online_feature_plane/__init__.py`
- Tests:
  - `tests/services/online_feature_plane/test_phase4_snapshots.py`

### Invariants to enforce
- Snapshot artifact path is content-addressable by `snapshot_hash` and immutable (`write_if_absent`).
- Snapshot hash is computed from canonical snapshot payload via existing contract helper.
- Index row for same `snapshot_hash` is idempotent (upsert with same truth).
- Snapshot retrieval by hash resolves to exactly one artifact ref and provenance payload.

### Validation plan
- `python -m pytest tests/services/online_feature_plane -q`
- New checks:
  - deterministic same-input snapshot hash,
  - immutable artifact path behavior,
  - index lookup by hash returns expected provenance + ref.

---

## Entry: 2026-02-06 17:12:05 - Phase 4 implemented (snapshot artifact + index)

### Summary of implementation
Implemented OFP Phase 4 component primitives for snapshot artifact materialization and metadata indexing.

### Changes applied
- Added snapshot index persistence backends:
  - `src/fraud_detection/online_feature_plane/snapshot_index.py`
  - supports SQLite and Postgres via DSN auto-detection.
  - stores deterministic lookup metadata keyed by `snapshot_hash`.
- Added snapshot materializer runtime:
  - `src/fraud_detection/online_feature_plane/snapshots.py`
  - builds snapshot from OFP projection state + basis + active feature policy metadata,
  - computes deterministic `snapshot_hash` via existing contract helper,
  - writes immutable by-ref snapshot JSON artifact using `write_json_if_absent`,
  - records index row with provenance payloads (`feature_def_policy_rev`, `run_config_digest`, `eb_offset_basis`, optional `graph_version`).
- Added materializer CLI utility:
  - `src/fraud_detection/online_feature_plane/snapshotter.py`
- Extended OFP config wiring for Phase 4:
  - `src/fraud_detection/online_feature_plane/config.py`
  - new wiring fields:
    - `snapshot_index_dsn`
    - `snapshot_store_root`
    - `snapshot_store_endpoint`
    - `snapshot_store_region`
    - `snapshot_store_path_style`
  - defaults resolve from `OFP_*` vars and/or `PLATFORM_STORE_ROOT`.
- Extended OFP projection store query surface:
  - `src/fraud_detection/online_feature_plane/store.py`
  - added `list_group_states(...)` (SQLite/Postgres) for deterministic snapshot assembly.
- Updated package exports:
  - `src/fraud_detection/online_feature_plane/__init__.py`
- Added Phase 4 tests:
  - `tests/services/online_feature_plane/test_phase4_snapshots.py`

### Invariant checks satisfied
- Snapshot path is content-addressable (`.../<snapshot_hash>.json`) and immutable on re-materialization.
- Same basis + state yields same `snapshot_hash`.
- Snapshot index resolves metadata deterministically by hash.
- No changes to Phase 2/3 idempotent projector behavior.

### Validation
- Command: `python -m pytest tests/services/online_feature_plane -q`
- Result: `10 passed`.
- New test coverage:
  - snapshot artifact write + index upsert,
  - deterministic repeated materialization hash,
  - index retrieval + artifact load by hash.

### Phase status impact
- OFP Phase 4 DoDs (4.3.C + 4.3.D) are closed at component scope.
- Phase 5+ serve semantics/integration remain pending.

---

## Entry: 2026-02-06 17:20:00 - Phase 5 implementation plan (serve API + deterministic semantics)

### Problem / goal
Phase 4 snapshot primitives are green, but OFP still lacks a formal `get_features` serve surface that enforces Phase 5 semantics:
- explicit `as_of_time_utc` (no hidden now),
- coherent single-response basis/provenance,
- `graph_version` stamping when identity graph is consulted,
- explicit dependency posture flags for stale/missing dependencies to support DF/DL degrade handling.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.E)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md` (PD-OFP-OUT-06/07)
- Snapshot smoke evidence (local parity):
  - run: `platform_20260206T143456Z`
  - scenario_run_id: `dddddddddddddddddddddddddddddddd`
  - snapshot_hash: `a00d88a2ac4a3a3bbeecc805b05cbb6e253b5cbe427447b95bb5f728b37dd8a6`
  - artifact: `runs/fraud-platform/platform_20260206T143456Z/ofp/snapshots/dddddddddddddddddddddddddddddddd/a00d88a2ac4a3a3bbeecc805b05cbb6e253b5cbe427447b95bb5f728b37dd8a6.json`
  - index DB: `runs/fraud-platform/platform_20260206T143456Z/online_feature_plane/index/ofp_snapshot_index.db`

### Decision
Implement a dedicated OFP serve module that reuses the existing contract validator + snapshot materializer and adds deterministic response shaping:
1. New `OfpGetFeaturesService` surface:
   - validates request (`as_of_time_utc` required),
   - materializes snapshot for request pins and as-of,
   - filters to requested feature keys.
2. Graph consultation posture:
   - optional resolver hook for IEG graph tokens,
   - stamps `graph_version` when resolver returns a token,
   - fails closed (`UNAVAILABLE`) when request requires IEG and resolver/token is unavailable.
3. Dependency posture surface:
   - always emit explicit freshness posture fields (`state`, `flags`),
   - mark stale basis when `as_of_time_utc` exceeds basis window end,
   - mark missing feature dependencies when requested keys/groups are absent.
4. Keep response basis coherent:
   - one materialization call per response,
   - one `eb_offset_basis` token and digest in returned snapshot.

### Planned files
- `src/fraud_detection/online_feature_plane/serve.py` (new)
- `src/fraud_detection/online_feature_plane/__init__.py` (export serve surface)
- `docs/model_spec/platform/contracts/real_time_decision_loop/feature_snapshot.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_response.schema.yaml`
- `tests/services/online_feature_plane/test_phase5_serve.py` (new)

### Validation plan
- Unit tests for:
  - `as_of_time_utc` requirement enforcement,
  - deterministic basis/provenance in responses,
  - graph_version stamping when resolver is used,
  - explicit posture flags for missing/stale dependencies.
- Full OFP suite:
  - `python -m pytest tests/services/online_feature_plane -q`

---

## Entry: 2026-02-06 17:24:00 - Phase 5 implemented (serve API + deterministic semantics)

### Summary of implementation
Implemented OFP Phase 5 query surface with explicit request validation, deterministic response basis/provenance, optional graph-version stamping, and explicit stale/missing dependency posture flags.

### Changes applied
- Added OFP serve module:
  - `src/fraud_detection/online_feature_plane/serve.py`
  - new `OfpGetFeaturesService`:
    - validates request via `validate_get_features_request` (enforces required `as_of_time_utc`),
    - materializes snapshot through Phase 4 materializer (single coherent basis per response),
    - filters response to requested feature keys,
    - emits explicit freshness posture fields:
      - `state` (`GREEN|AMBER|RED`)
      - `flags`
      - `stale_groups`
      - `missing_groups`
      - `missing_feature_keys`
    - supports optional graph resolver hook:
      - stamps `graph_version` when resolver returns a token,
      - fail-closed `UNAVAILABLE` when `graph_resolution_mode=require_ieg` and resolver/token unavailable.
- Updated exports:
  - `src/fraud_detection/online_feature_plane/__init__.py` now exports `OfpGetFeaturesService`.
- Updated RTDL OFP snapshot contract schemas for explicit posture flags:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/feature_snapshot.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_response.schema.yaml`
- Added Phase 5 tests:
  - `tests/services/online_feature_plane/test_phase5_serve.py`
  - coverage includes:
    - required `as_of_time_utc` behavior,
    - graph_version stamping with resolver,
    - stale/missing dependency posture flags,
    - fail-closed behavior for `require_ieg` without resolver.

### Validation
- Snapshot smoke evidence used as Phase 5 input:
  - run: `platform_20260206T143456Z`
  - scenario_run_id: `dddddddddddddddddddddddddddddddd`
  - snapshot_hash: `a00d88a2ac4a3a3bbeecc805b05cbb6e253b5cbe427447b95bb5f728b37dd8a6`
- Test command:
  - `python -m pytest tests/services/online_feature_plane -q`
- Result:
  - `14 passed`

### DoD impact
- Phase 5 DoDs are closed at OFP component scope:
  - explicit as-of semantics enforced,
  - deterministic per-response basis/provenance surface,
  - graph_version stamped when graph dependency is consulted,
  - stale/missing dependencies surfaced as explicit posture flags for DF/DL degrade handling.
- Integration-dependent phases (4.3.F-4.3.H) remain pending.

---

## Entry: 2026-02-06 17:31:00 - Phase 6 implementation plan (rebuild + replay determinism)

### Problem / goal
Close OFP Phase 6 (4.3.F) at component scope by proving deterministic rebuild/replay behavior and pinning OFP/OFS parity expectations around basis and snapshot hash semantics.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.F)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (parity expectation)
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md` (input_basis + replay-safe semantics)
- Existing OFP projector/store/snapshot code and Phase 2-5 tests.

### Decision
Implement Phase 6 closure in two tracks:
1. Determinism test coverage:
   - same basis => same `snapshot_hash` and feature values across isolated rebuilds,
   - restart/resume from checkpoints produces same terminal snapshot as single-pass processing,
   - out-of-order event-time delivery (different file order, same event set) produces identical terminal snapshot hash and basis.
2. Pin OFP/OFS parity contract in docs:
   - same feature policy revision + same basis token (`eb_offset_basis`) + same graph token policy => same `snapshot_hash` expectations.

### Planned files
- `tests/services/online_feature_plane/test_phase6_replay.py` (new)
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_ofs_parity_contract_v0.md` (new)
- `docs/model_spec/platform/contracts/real_time_decision_loop/README.md` (contract index update)
- Potentially minor OFP runtime adjustments if tests expose non-determinism.

### Validation plan
- `python -m pytest tests/services/online_feature_plane/test_phase6_replay.py -q`
- `python -m pytest tests/services/online_feature_plane -q`
- Record evidence and update Phase 6 status in OFP/platform build plans.

---

## Entry: 2026-02-06 17:33:00 - Phase 6 implemented (rebuild + replay determinism)

### Summary of implementation
Closed OFP Phase 6 at component scope by adding deterministic replay/rebuild coverage and pinning an OFP/OFS parity identity contract.

### Changes applied
- Added Phase 6 replay determinism suite:
  - `tests/services/online_feature_plane/test_phase6_replay.py`
  - scenarios covered:
    - isolated rebuilds from same event basis produce identical `snapshot_hash` + values,
    - restart/resume from checkpoints converges to the same terminal snapshot as single-pass apply,
    - out-of-order event-time arrival converges to identical terminal snapshot hash/basis,
    - post-checkpoint reprocessing is a no-op for terminal snapshot hash.
- Added OFP/OFS parity contract note:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_ofs_parity_contract_v0.md`
  - pins parity identity tuple, basis identity, `graph_version` expectations, and mismatch posture.
- Updated contract indexes:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
  - `docs/model_spec/platform/contracts/README.md`
- Updated build plans:
  - `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 6 status -> completed with evidence)
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3 status + 4.3.F evidence and invariant wording)

### Validation
- `python -m pytest tests/services/online_feature_plane/test_phase6_replay.py -q` -> `4 passed`
- `python -m pytest tests/services/online_feature_plane -q` -> `18 passed`

### DoD impact
- Phase 6 DoDs are closed at OFP component scope:
  - replay determinism proven for v0 projector/snapshot path,
  - parity identity rules pinned for OFP/OFS comparison.
- Remaining OFP component phases:
  - Phase 7 (observability + health)
  - Phase 8 (integration closure with DF/DL and runbook handoff)

---

## Entry: 2026-02-06 17:42:00 - Phase 7 implementation plan (health + observability)

### Problem / goal
Close OFP Phase 7 (4.3.G) by making required counters observable and by defining an explicit OFP health state model (`GREEN|AMBER|RED`) that can be consumed by DL/operators in local parity.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 7 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.G)
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md` (operability/observability posture)
- Existing OFP modules (`projector`, `snapshots`, `serve`, `store`) and Phase 2-6 tests.

### Decision
Implement Phase 7 in three layers:
1. Metric source closure:
   - make `ofp_metrics` usable as a generic counter sink for all required counters.
   - increment:
     - `snapshots_built` / `snapshot_failures` in snapshot materialization path,
     - `missing_features` / `stale_graph_version` in serve path when relevant.
2. Health model:
   - add OFP observability reporter deriving:
     - required counters,
     - watermark age and lag/checkpoint age,
     - explicit health state + reasons via deterministic thresholds.
3. Export surface:
   - write run-scoped artifacts (local parity) for operators:
     - `online_feature_plane/metrics/last_metrics.json`
     - `online_feature_plane/health/last_health.json`

### Planned files
- `src/fraud_detection/online_feature_plane/store.py` (public metric/checkpoint summary accessors)
- `src/fraud_detection/online_feature_plane/snapshots.py` (snapshot success/failure counters)
- `src/fraud_detection/online_feature_plane/serve.py` (missing/stale counters)
- `src/fraud_detection/online_feature_plane/observability.py` (new reporter + health derivation)
- `src/fraud_detection/online_feature_plane/__init__.py` (export reporter)
- `tests/services/online_feature_plane/test_phase7_observability.py` (new)

### Validation plan
- `python -m pytest tests/services/online_feature_plane/test_phase7_observability.py -q`
- `python -m pytest tests/services/online_feature_plane -q`
- Update Phase 7 status in OFP/platform build plans with evidence.

---

## Entry: 2026-02-06 17:48:00 - Phase 7 implemented (health + observability)

### Summary of implementation
Closed OFP Phase 7 at component scope by adding explicit counter exports, a deterministic health-state model, and run-scoped observability artifacts.

### Changes applied
- Extended OFP metric access surface:
  - `src/fraud_detection/online_feature_plane/store.py`
  - added public methods:
    - `increment_metric(...)`
    - `checkpoints_summary()`
- Wired required Phase 7 counters into runtime paths:
  - `src/fraud_detection/online_feature_plane/snapshots.py`
    - increments `snapshots_built` on successful materialization,
    - increments `snapshot_failures` on materialization failure (best-effort).
  - `src/fraud_detection/online_feature_plane/serve.py`
    - increments `missing_features` when requested feature keys are absent,
    - increments `stale_graph_version` when request `as_of_time_utc` exceeds returned graph watermark.
- Added observability reporter:
  - `src/fraud_detection/online_feature_plane/observability.py`
  - provides:
    - required counters payload,
    - lag/watermark/checkpoint age metrics,
    - explicit health derivation (`GREEN|AMBER|RED`) with reasons,
    - run-scoped artifact export:
      - `online_feature_plane/metrics/last_metrics.json`
      - `online_feature_plane/health/last_health.json`
- Added observability CLI:
  - `src/fraud_detection/online_feature_plane/observe.py`
  - usage: `python -m fraud_detection.online_feature_plane.observe --profile <...> --scenario-run-id <...> [--output-root <...>]`
- Updated OFP exports:
  - `src/fraud_detection/online_feature_plane/__init__.py`
    - exports `OfpObservabilityReporter` and `OfpHealthThresholds`.
- Added Phase 7 tests:
  - `tests/services/online_feature_plane/test_phase7_observability.py`
  - coverage:
    - counter presence + increments for snapshot/serve paths,
    - health-state derivation and artifact export,
    - snapshot failure counter export.

### Validation
- `python -m pytest tests/services/online_feature_plane/test_phase7_observability.py -q` -> `2 passed`
- `python -m pytest tests/services/online_feature_plane -q` -> `20 passed`

### DoD impact
- Phase 7 DoDs are closed at OFP component scope:
  - required counters exist and are exportable,
  - explicit health status model implemented,
  - serve-side degraded dependency posture remains explicit (Phase 5).
- Remaining OFP component phase:
  - Phase 8 (integration closure / 4.3.H).

---

## Entry: 2026-02-06 17:53:00 - Phase 8 split-closure plan (8A now, 8B when DF/DL exist)

### Problem / goal
We cannot fully close OFP Phase 8 while DF/DL are not yet implemented, because Phase 8 includes explicit DF compatibility and DL consume-path requirements. The goal is to close what is truly closable now and make remaining blockers explicit.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (Phase 8 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (4.3.H + 4.4 adjacency)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- Current OFP completed phases (1-7) and tests.

### Decision
Split Phase 8 into:
1. **Phase 8A (integration-ready, closable now)**:
   - OFP contracts/provenance fields are stable and test-backed.
   - OFP/OFS parity checkpoint semantics are documented.
   - local_parity runbook exists for OFP validation up to the current boundary.
2. **Phase 8B (integration closure, blocked)**:
   - DF compatibility tests (consumer contract assertions) require DF implementation.
   - DL policy-posture consumption tests require DL implementation.

### Planned edits
- Update OFP build plan Phase 8 status/checklist to 8A complete and 8B pending.
- Update platform build plan 4.3.H wording so it reflects partial closure and explicit block on DF/DL.
- Add OFP local parity runbook doc under platform docs.
- Record closure rationale and evidence in this impl map and in the logbook.

---

## Entry: 2026-02-06 17:57:00 - Phase 8 split closure applied (8A complete, 8B pending)

### Summary of implementation
Applied the Phase 8 split-closure model so the plan reflects actual readiness:
- closed what OFP can close independently now (8A),
- marked DF/DL dependent checks as explicit pending work (8B).

### Changes applied
- Updated OFP build plan:
  - `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md`
  - Phase 8 now has explicit status:
    - 8A integration-ready complete,
    - 8B cross-component integration pending.
- Updated platform build plan:
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - 4.3 status now reflects partial 4.3.H closure and explicit DF/DL dependency.
  - 4.3.H checklist now distinguishes component-level validation vs pending integration tests.
- Added OFP local parity runbook:
  - `docs/runbooks/platform_parity_walkthrough_v0.md`
  - includes run-scoping, projector, snapshotter, observability export, and verification steps.

### Closure stance
- **Phase 8A (complete):**
  - OFP/OFS parity checkpoint semantics documented.
  - OFP boundary runbook exists for local parity.
  - OFP component validations green (`20 passed` suite).
- **Phase 8B (pending by design):**
  - DF compatibility integration assertions.
  - DL consume-path checks for OFP health/degrade signals.

---

## Entry: 2026-02-06 18:28:00 - Local-parity monitored validation (20 then 200) for OFP boundary

### Problem / goal
Validate OFP runtime behavior against live local-parity flow with active monitoring and concrete evidence:
1) small pass (20) to detect duds quickly,
2) larger pass (200) to validate stable ingestion/projector/snapshot behavior.

### Authorities / inputs
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `config/platform/profiles/local_parity.yaml`
- `config/platform/sr/wiring_local_kinesis.yaml`
- Live local-parity stack (`postgres/minio/localstack`) and IG service parity target.

### Runtime decisions taken during validation
1. Cleared host-pinned `PLATFORM_RUN_ID` that was forcing stale run reuse (`platform_20260201T224449Z`) and regenerated active run id using `make platform-run-new PLATFORM_RUN_ID=`.
2. Forced single IG parity process chain (killed orphan chains from repeated starts) to avoid ambiguous ingress observations.
3. For 200-event controlled pass, isolated SR READY traffic on a dedicated control stream by using a temporary SR wiring override:
   - `runs/fraud-platform/tmp/sr_wiring_iso.yaml`
   - `control_bus_stream: sr-control-bus-20260206T181720Z`
4. Kept OFP run-scope lock enabled:
   - `OFP_REQUIRED_PLATFORM_RUN_ID=<active_run>`
5. Accepted current projector startup behavior (TRIM_HORIZON/backlog scan with run-scope mismatches counted) and advanced with repeated `--once` passes until run-scoped applied rows converged.

### 20-pass evidence (smoke)
- Active run: `platform_20260206T180502Z`
- SR scenario run: `e070b450e60eea2c494f3c7d0aa13999`
- WSP emitted: `80` (20 per output x 4 outputs, concurrent mode)
- OFP evidence:
  - Projection DB: `runs/fraud-platform/platform_20260206T180502Z/online_feature_plane/projection/online_feature_plane.db`
  - Snapshot: `runs/fraud-platform/platform_20260206T180502Z/ofp/snapshots/e070b450e60eea2c494f3c7d0aa13999/17a551efe62b37e154e76cdb53362c876f21590a0367dd5cf160a75fb10b0f78.json`
  - Metrics/health exported under `runs/fraud-platform/platform_20260206T180502Z/online_feature_plane/{metrics,health}/`

### 200-pass evidence (isolated control stream)
- Active run: `platform_20260206T181729Z`
- SR scenario run: `7ac45fb53668e252cd4125f38b067fcd`
- READY message on isolated stream:
  - stream: `sr-control-bus-20260206T181720Z`
  - message_id: `944707c7709f256cfca32c874da20ee9fd9b4eaf002f042b54a0d1a86ac91853`
- WSP emitted:
  - `800` (200 per output x 4 outputs, concurrent mode)
  - result bound to SR scenario run `7ac45fb53668e252cd4125f38b067fcd`
- IG ingress truth (postgres):
  - `admissions`: `800` for platform run `platform_20260206T181729Z`
  - `receipts`: `800` for `pins_json.platform_run_id=platform_20260206T181729Z`
  - `receipts` scenario grouping: only `7ac45fb53668e252cd4125f38b067fcd` with count `800`
  - `quarantines`: `0` for this run
- OFP convergence:
  - first projector `--once` pass saw backlog (run_scope_mismatch metrics) with `processed=200`, `applied=0`
  - after two additional `--once` passes: `applied=200`, `feature_state=100`
- OFP projection/snapshot evidence:
  - Projection DB: `runs/fraud-platform/platform_20260206T181729Z/online_feature_plane/projection/online_feature_plane.db`
  - Snapshot: `runs/fraud-platform/platform_20260206T181729Z/ofp/snapshots/7ac45fb53668e252cd4125f38b067fcd/047e0b6b819ffdce783948da371df72778eedcee5b2fca9274854b6e013b69ee.json`
  - Snapshot basis digest: `19cf8ef9eeb637e29971bc472ce04b3f2dccd38145655d2a4d1f087b591477e3`
  - Snapshot feature count: `100`
  - Metrics artifact: `runs/fraud-platform/platform_20260206T181729Z/online_feature_plane/metrics/last_metrics.json`
  - Health artifact: `runs/fraud-platform/platform_20260206T181729Z/online_feature_plane/health/last_health.json`

### Validation outcome
- OFP boundary is functioning for both smoke and 200-event local-parity passes when run-scoped pins are enforced.
- Current operational caveat remains: on fresh run-scoped OFP DB/checkpoint, projector can initially consume historical EB backlog before reaching current run events; repeated `--once` passes converge correctly under run-scope filtering.

---

## Entry: 2026-02-06 18:40:00 - Drift-closure implementation plan (approved): inlet semantics, topic scope, live parity, artifact namespace

### Problem statement
User approved four specific OFP closures to remove drift against the RTDL flow narrative:
1. inlet dedupe semantics aligned to `(platform_run_id, event_class, event_id)` plus payload hash collision handling,
2. multi-topic intake (traffic + context capable, policy-bounded),
3. live parity operation (`run_forever`) with explicit start-position policy,
4. artifact namespace normalization (`ofp/` vs `online_feature_plane/`).

### Authorities and constraints
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (RTDL/OFP narrative)
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md` (phase closure context)
- OFP v0 contracts and existing tests (`tests/services/online_feature_plane/*`)
- platform doctrine: fail closed, run-scoped pins, append-only/auditable behavior.

### Design decisions before coding
1. **Dual idempotency layers (intentional):**
   - Keep transport dedupe by `(stream_id, topic, partition, offset_kind, offset)` for replay safety.
   - Add semantic dedupe table keyed by `(stream_id, platform_run_id, event_class, event_id)` with stored payload hash.
   - Behavior:
     - same tuple + same hash => semantic duplicate (`duplicates` counter, no state mutation),
     - same tuple + different hash => collision (`payload_hash_mismatch` counter, no state mutation, fail-closed by non-application).
2. **Event class derivation in OFP inlet:**
   - Prefer envelope field `event_class` when present.
   - Fallback to deterministic topic-to-class mapping from configured topics in profile.
   - If no class can be resolved, mark invalid (`invalid_event_class`) and advance checkpoint only.
3. **Multi-topic profile model:**
   - Replace single `event_bus_topic` assumption with `event_bus_topics: list[str]`.
   - Preserve backward compatibility by keeping `event_bus_topic` as first topic alias for old call sites during migration.
4. **Start-position policy:**
   - Add `event_bus_start_position` in OFP wiring (`trim_horizon` default, `latest` optional).
   - Apply only when no checkpoint exists for shard/partition.
5. **Artifact namespace normalization:**
   - New canonical snapshot path under `online_feature_plane/snapshots/<scenario_run_id>/<snapshot_hash>.json`.
   - Keep read compatibility for old `ofp/snapshots/...` refs (loader fallback) during migration window.

### Files planned for implementation
- `src/fraud_detection/online_feature_plane/config.py`
- `src/fraud_detection/online_feature_plane/projector.py`
- `src/fraud_detection/online_feature_plane/store.py`
- `src/fraud_detection/online_feature_plane/snapshots.py`
- `src/fraud_detection/event_bus/kinesis.py`
- `makefile` (new local-parity OFP live target)
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- OFP tests under `tests/services/online_feature_plane/`

### Validation plan (pre-committed)
- Unit/integration:
  - `python -m pytest tests/services/online_feature_plane -q`
- Focus checks:
  - semantic duplicate no-op,
  - payload hash collision detection,
  - multi-topic projector ingestion,
  - `latest` start-position behavior with empty checkpoints,
  - snapshot path canonicalization + backward load compatibility.
- Parity smoke:
  - short monitored run to ensure no regression in run-scoped processing and artifact emission.

---

## Entry: 2026-02-06 22:50:00 - Drift-closure implementation completed (OFP): namespace normalization, compatibility, and fresh parity evidence

### Scope closed in this pass
1. Completed artifact namespace normalization so OFP snapshots write under the canonical component namespace.
2. Kept backward compatibility for historical `ofp/snapshots/...` refs during read/load.
3. Revalidated OFP tests and local-parity flow evidence after code changes.

### Code-level outcomes
- `src/fraud_detection/online_feature_plane/snapshots.py`
  - canonical snapshot path now writes to: `online_feature_plane/snapshots/<scenario_run_id>/<snapshot_hash>.json`.
  - materializer prefers canonical path, but if a legacy object already exists it reuses that ref instead of duplicating writes.
  - loader now tries both canonical and legacy path variants from the stored ref and fails closed only if neither exists.
- `tests/services/online_feature_plane/test_phase4_snapshots.py`
  - updated canonical-path assertion.
  - added legacy-index-ref fallback test to ensure migration compatibility.
- `docs/runbooks/platform_parity_walkthrough_v0.md`
  - expected snapshot artifact shape updated to canonical `online_feature_plane/snapshots/...`.

### Validation evidence (unit/integration)
- `.venv/Scripts/python.exe -m pytest tests/services/online_feature_plane/test_phase4_snapshots.py -q` -> `2 passed`
- `.venv/Scripts/python.exe -m pytest tests/services/online_feature_plane -q` -> `25 passed`

### Validation evidence (fresh local-parity passes)
Controlled passes were executed with:
- fresh platform run ids (`make platform-run-new PLATFORM_RUN_ID=`),
- isolated SR control stream per pass,
- WSP `--max-messages 1`,
- OFP run-scope pinning (`OFP_REQUIRED_PLATFORM_RUN_ID=<run>`),
- snapshot materialization + observability export after projection.

#### Pass A (20)
- `platform_run_id`: `platform_20260206T223612Z`
- `scenario_run_id`: `6bebc0ed93d1606cf8b4bcd87223b64b`
- OFP projection DB: `runs/fraud-platform/platform_20260206T223612Z/online_feature_plane/projection/online_feature_plane.db`
- Metrics: `events_seen=20`, `events_applied=20`, `duplicates=0`, `payload_hash_mismatch=0`
- Feature-state rows: `10`
- Snapshot: `runs/fraud-platform/platform_20260206T223612Z/online_feature_plane/snapshots/6bebc0ed93d1606cf8b4bcd87223b64b/aef9042de54a88f5ec6869c4d643db7610190c1da94d9951807d4de75b2ad626.json`

#### Pass B (200)
- `platform_run_id`: `platform_20260206T223857Z`
- `scenario_run_id`: `e49846109f26d4cd2442a0ccd3241c19`
- OFP projection DB: `runs/fraud-platform/platform_20260206T223857Z/online_feature_plane/projection/online_feature_plane.db`
- Metrics: `events_seen=200`, `events_applied=200`, `duplicates=0`, `payload_hash_mismatch=0`
- Feature-state rows: `100`
- Snapshot: `runs/fraud-platform/platform_20260206T223857Z/online_feature_plane/snapshots/e49846109f26d4cd2442a0ccd3241c19/fbc946cf89850cf29ade3b0fcce232b991e742f0e137527cfbbeb1bbad030873.json`

### Interpretation
- Drift item #4 (artifact namespace split) is now closed in code and runbook, with backward read compatibility in place.
- Drift items #1/#2/#3 remain validated in current code path (semantic dedupe + topic handling + live start-position support) and pass regression (`25` tests).
- For v0, OFP applies admitted events from the configured topic set in `config/platform/ofp/topics_v0.yaml` (`fp.bus.traffic.fraud.v1`), so applied counts naturally track that topic scope.

---

## Entry: 2026-02-06 23:00:00 - Doc consolidation plan: retire standalone OFP runbook and fold into platform parity walkthrough

### Problem
User requested removal of `docs/model_spec/platform/runbooks/local_parity_ofp_runbook.md` and consolidation into `docs/runbooks/platform_parity_walkthrough_v0.md`.

### Decision
1. Move OFP local-parity operating steps into the platform parity walkthrough as an explicit OFP section.
2. Delete the standalone OFP runbook file.
3. Update build-plan / implementation-map references so no docs point to deleted paths.

### Files targeted
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md`
- `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`
- delete `docs/model_spec/platform/runbooks/local_parity_ofp_runbook.md`


## Entry: 2026-02-06 23:08:00 - Doc consolidation completed: OFP runbook folded into platform parity walkthrough

### Changes applied
1. Removed standalone file:
   - `docs/model_spec/platform/runbooks/local_parity_ofp_runbook.md`
2. Added OFP boundary operation section to platform walkthrough:
   - `docs/runbooks/platform_parity_walkthrough_v0.md`
   - new Section 15 includes run-scope pinning, projector invocation, scenario discovery, snapshot materialization, observability export, and required counters.
3. Updated OFP build-plan and impl-map references to use the platform walkthrough path:
   - `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`

### Validation
- Searched docs for live links to deleted runbook path; no active references remain outside historical log/decision text.

---

## Entry: 2026-02-07 13:00:00 - Plan: align OFP semantic dedupe tuple to corridor law

### Problem
OFP currently keys semantic dedupe by `(stream_id, platform_run_id, event_class, event_id)`. Corridor semantics require idempotency by `(platform_run_id, event_class, event_id)` plus payload-hash anomaly checks. Including `stream_id` risks semantic divergence across stream-id variants while representing the same admitted event identity.

### Authorities
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`

### Decision and migration posture
1. Keep transport dedupe exactly as-is (`stream_id/topic/partition/offset_kind/offset`).
2. Change semantic dedupe table PK and lookup to `(platform_run_id, event_class, event_id)`.
3. Preserve `stream_id` as metadata in applied/checkpoint lanes, not semantic identity.
4. Preserve `payload_hash` mismatch handling and metrics behavior.

### Files planned
- `src/fraud_detection/online_feature_plane/store.py`
- `tests/services/online_feature_plane/*` (semantic dedupe/collision tests + migration-sensitive assertions)

### Validation plan
- `python -m pytest tests/services/online_feature_plane -q`
- ensure no regressions in projection/apply/checkpoint behavior.

---

## Entry: 2026-02-07 13:09:19 - OFP semantic dedupe tuple drift closed

### What changed
1. OFP semantic dedupe key was migrated from:
   - `(stream_id, platform_run_id, event_class, event_id)`
   to:
   - `(platform_run_id, event_class, event_id)`.
2. Kept `stream_id` as metadata on semantic rows and retained transport dedupe unchanged.
3. Added semantic dedupe schema migration paths for both SQLite and Postgres:
   - automatic table rebuild when legacy PK includes `stream_id`,
   - deterministic row collapse by semantic tuple during migration.
4. Updated semantic insert/select conflict clauses to ignore `stream_id` for semantic identity.
5. Added regression test proving semantic dedupe is stream-independent.

### Files changed
- `src/fraud_detection/online_feature_plane/store.py`
- `tests/services/online_feature_plane/test_phase2_projector.py`

### Validation
- `python -m pytest tests/services/online_feature_plane -q` -> `26 passed`.

### Invariant confirmation
- Transport checkpoint/idempotency remains keyed by stream/topic/partition/offset.
- Semantic payload-hash mismatch is still surfaced as `PAYLOAD_HASH_MISMATCH`.

---

## Entry: 2026-02-07 14:23:00 - Plan: prevent OFP mutation on DF output families in shared v0 traffic stream

### Problem
OFP currently resolves event class by topic first. With DF outputs routed to `fp.bus.traffic.fraud.v1` in v0 parity, `decision_response`/`action_intent` can be misclassified as `traffic_fraud` and mutate feature state.

### Why this is drift
This violates the RTDL boundary that DF output families are non-feature inputs in v0 and should not participate in OFP projector mutation.

### Decision threads
1. **Event-type suppression location**
   - Option A: config-only topic split.
   - Option B: projector event-type ignore/blocklist.
   - Selected: Option B now (minimal and deterministic), while keeping stream topology unchanged.
2. **Checkpoint semantics for suppressed events**
   - Option A: skip without checkpoint advance.
   - Option B: advance checkpoint + count ignored.
   - Selected: Option B to avoid replay stalls and keep observability explicit.
3. **Counter posture**
   - Add dedicated `ignored_event_type` counters (global + per-topic) using existing metric mechanism.

### Planned mechanics
- In projector `_process_record`, after envelope/run/pin validation and before class resolution/mutation:
  - if `event_type in {decision_response, action_intent}`:
    - advance checkpoint,
    - count as `ignored_event_type`,
    - return without `apply_event`.

### Validation plan
- Add targeted OFP test proving:
  - shared-traffic DF event is consumed,
  - checkpoint advances,
  - no feature-state mutation,
  - `ignored_event_type` metric increments.

---

## Entry: 2026-02-07 14:26:00 - Implemented OFP DF-family ignore path on shared traffic stream

### Code changes
1. Added explicit OFP ignore set:
   - `decision_response`
   - `action_intent`
2. Added early suppression branch in projector `_process_record`:
   - validates envelope/pins/run-scope as usual,
   - advances checkpoint with `count_as="ignored_event_type"`,
   - exits before key/event_class resolution and before `apply_event`.

File changed:
- `src/fraud_detection/online_feature_plane/projector.py`

### Why this exact placement
Suppression was placed after canonical envelope/pin checks and before mutation/classification so:
- invalid events still surface as invalid,
- valid DF events do not mutate feature state,
- offsets always progress for deterministic replay continuity.

### Test coverage added
- `tests/services/online_feature_plane/test_phase2_projector.py`
  - `test_projector_ignores_df_families_on_shared_traffic_topic`
  - asserts:
    - one shared-stream DF event is consumed,
    - no feature-state rows are produced,
    - `ignored_event_type` counters increment,
    - checkpoint/input basis advances to next offset.

### Validation evidence
- `python -m pytest tests/services/online_feature_plane/test_phase2_projector.py -q` (included in targeted run) -> pass.
- `python -m pytest tests/services/online_feature_plane -q` -> `27 passed`.

## Entry: 2026-02-07 22:06:15 - OFP Phase 8 integration closure decision (v0)

### Trigger
Platform Phase 4 closure pass required resolving OFP build-plan `Phase 8` from partial closure to explicit cross-component closure.

### Decision and reasoning
1. Treat OFP `8B` as closed only with cross-component evidence, not component-local assertions.
   - Reasoning: OFP integration claims require DF and DL compatibility surfaces, not projector-only tests.
2. Use the full RTDL regression sweep as primary closure evidence.
   - Command executed:
     - `$env:PYTHONPATH='.;src'; python -m pytest --import-mode=importlib tests/services/identity_entity_graph tests/services/online_feature_plane tests/services/context_store_flow_binding tests/services/degrade_ladder tests/services/decision_fabric tests/services/action_layer tests/services/decision_log_audit tests/services/ingestion_gate/test_phase10_df_output_onboarding.py -q`
   - Result: `275 passed`.
3. Keep closure scoped to current v0 contracts.
   - Reasoning: any future extension of OFP/DL signal taxonomy is additional hardening, not a blocker for this closure gate.

### Applied plan update
- Updated `docs/model_spec/platform/implementation_maps/online_feature_plane.build_plan.md`:
  - Phase 8 status moved from `partial closure` to `completed`.
  - Added explicit 8B evidence references to DF context and DL signal paths covered by the regression sweep.

### Outcome
- OFP build plan now reflects integration-closed status at current v0 scope, aligned with platform Phase 4 closeout criteria.

---

## Entry: 2026-02-08 13:11:44 - Parity Postgres-default wiring closure (reviewer item 8)

### Trigger
Reviewer item 8 required local_parity RTDL stores to default to Postgres instead of implicit sqlite behavior.

### Decision
Keep OFP runtime code unchanged and close through explicit parity wiring controls:
1. profile wiring includes explicit snapshot index DSN source,
2. make parity-live target passes Postgres DSNs by default,
3. runbook commands use parity DSN environment variables directly.

### Applied changes touching OFP operation
- `config/platform/profiles/local_parity.yaml`
  - added `ofp.wiring.snapshot_index_dsn: ${OFP_SNAPSHOT_INDEX_DSN}`.
- `makefile`
  - `platform-ofp-projector-parity-live` now exports:
    - `OFP_PROJECTION_DSN=$(PARITY_OFP_PROJECTION_DSN)`
    - `OFP_SNAPSHOT_INDEX_DSN=$(PARITY_OFP_SNAPSHOT_INDEX_DSN)`
- `docs/runbooks/platform_parity_walkthrough_v0.md`
  - OFP parity steps now set/use the Postgres parity DSN variables.

### Why this approach
- Preserves existing OFP projector semantics while making environment posture deterministic.
- Avoids accidental sqlite fallback in parity operation and keeps parity/dev/prod substrate alignment clearer.

### Outcome
OFP parity operational path is now pinned to Postgres-default DSN wiring, with no hidden store-mode switch in the normal local_parity flow.

---
## Entry: 2026-02-08 14:47:54 - Plan: fix Postgres reserved identifier crash in OFP live projector

### Problem
`platform-ofp-projector-parity-live` fails during Postgres store init (`ofp_applied_events` DDL) at `offset` column.

### Plan
- Quote `"offset"` in OFP applied-events table DDL (sqlite + postgres branches for parity consistency).
- Quote `"offset"` in OFP insert/conflict SQL for applied-events writes.
- Validate by re-running `make platform-ofp-projector-parity-live` startup.

### Invariant
No change to OFP basis/dedupe semantics; SQL identifier hardening only.

---
## Entry: 2026-02-08 15:30:54 - Implemented reserved-identifier fix; parity run shows OFP undercount caveat

### Implementation applied
- Quoted `"offset"` in OFP applied-events DDL (sqlite + postgres branches).
- Quoted `"offset"` in applied-events insert + conflict target SQL.

File:
- `src/fraud_detection/online_feature_plane/store.py`

### Runtime evidence for requested 200-event run
Run scope:
- `platform_run_id=platform_20260208T151238Z`
- `scenario_run_id=9bad140a881372d00895211fae6b3789`

Observed OFP store metrics (`ofp_metrics`):
- `events_seen=194`
- `events_applied=194`
- topic-scoped metric agrees (`events_applied|topic=fp.bus.traffic.fraud.v1=194`)

Cross-check:
- IG + EB evidence for the same run shows `200` admitted traffic events on `fp.bus.traffic.fraud.v1`.

### Diagnostic action taken
- Removed run-scoped OFP checkpoints (`ofp_checkpoints` for `ofp.v0::platform_20260208T151238Z`) to test a fresh read path.
- Attempted explicit one-pass reconsume; runtime auth/environment mismatch prevented a clean replay in that diagnostic attempt.
- Count remained `194` after diagnostics.

### Decision
Track as an operational parity caveat (live startup/checkpoint timing/auth path), not as a schema/contract issue and not solved by weakening OFP semantics.

---
## Entry: 2026-02-08 15:59:29 - Plan: eliminate OFP parity undercount via start-position hardening

### Problem
OFP run-scoped applied rows are `194` while traffic admissions/records are `200` for the same run.

### Diagnosis summary
- Compared Kinesis traffic sequence numbers with `ofp_applied_events.offset`.
- The 6 missing offsets are the earliest 6 in the stream.
- This indicates startup race under `LATEST` consumer start position.

### Change plan
1. Update parity live launcher default to `trim_horizon`.
2. Keep explicit override path for `latest`.
3. Reconcile affected run by run-scoped OFP replay from trim_horizon after clearing only OFP rows for the run stream id.

### Validation to require
- Sequence diff closes to zero missing.
- `ofp_applied_events` run/scenario count reaches `200`.
- OFP projector/phase tests remain green.

---
## Entry: 2026-02-08 16:01:22 - OFP undercount remediation implemented and validated

### Implementation
1. Updated parity OFP live default:
   - `makefile`: `OFP_EVENT_BUS_START_POSITION ?= trim_horizon`.
2. Updated parity runbook note to document default and override:
   - `docs/runbooks/platform_parity_walkthrough_v0.md` section 21.

### Why this closes the issue
The prior default (`latest`) could attach after initial stream records already existed, causing early-record loss on startup in live parity mode.
`trim_horizon` removes that startup race for run-scoped parity validation while preserving explicit operator override when tailing-only behavior is desired.

### Run-scoped proof (same affected run)
- run: `platform_20260208T151238Z`
- scenario: `9bad140a881372d00895211fae6b3789`
- OFP stream id: `ofp.v0::platform_20260208T151238Z`

Actions:
- cleared only OFP rows for this stream id,
- replayed once with `trim_horizon`.

Evidence:
- `ofp_run_once_processed=200`
- `ofp_applied_events_for_run=200`
- metrics:
  - `events_seen=200`
  - `events_applied=200`
- sequence diff:
  - Kinesis traffic records: `200`
  - OFP applied offsets: `200`
  - missing offsets: `0`

### Regression validation
- `python -m pytest tests/services/online_feature_plane -q` -> `29 passed`.

### Outcome
OFP 194/200 parity gap is closed and default parity launcher behavior is hardened to avoid recurrence.

---
