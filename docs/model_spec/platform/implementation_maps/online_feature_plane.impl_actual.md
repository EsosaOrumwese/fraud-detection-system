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
