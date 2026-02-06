# Online Feature Plane Build Plan (v0)
_As of 2026-02-06_

## Purpose
Provide a closure-grade, component-scoped plan for OFP aligned to platform Phase 4.3 and the pinned RTDL narrative flow.

## Scope and role
- OFP is a hot-path `projector + serve surface`.
- Primary flow: `IG -> EB(admitted traffic) -> OFP(projector) -> DF(get_features) -> DLA`.
- Optional flow: `OFP -> IEG` query for identity resolution and `graph_version` provenance.
- OFP does not own admission truth, decision truth, or label truth.

## Authorities (must hold)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/`

## Binding rails
- ContextPins are mandatory on all inputs/outputs.
- No cross-run feature state mixing.
- Idempotent apply under at-least-once delivery.
- Deterministic serve (`as_of_time_utc`, no hidden "now").
- Provenance is mandatory: `input_basis`, feature versions, `snapshot_hash`, optional `graph_version`.

## Phase map (v0)

### Phase 1 - Contracts and provenance authority (4.3.A, 4.3.C)
**Intent:** lock the meaning of OFP outputs before implementation details.

**DoD checklist:**
- `get_features` response contract includes:
  - ContextPins
  - `as_of_time_utc`
  - feature groups and versions
  - `input_basis` (exclusive-next offsets)
  - `snapshot_hash`
  - `graph_version` when IEG was consulted
  - `run_config_digest`
- Snapshot hash canonicalization is pinned (stable JSON ordering + encoding).
- Failure contract is explicit (`NOT_FOUND`, `UNAVAILABLE`, validation errors) and never fabricates context.
- Contract references are linked to authoritative schema files under `contracts/real_time_decision_loop/`.

### Phase 2 - Intake projector core (4.3.A, 4.3.F)
**Intent:** build deterministic state from admitted EB traffic.
**Status:** completed (2026-02-06, component scope).

**DoD checklist:**
- OFP consumes admitted EB traffic topics only; no Oracle side reads.
- Apply path is idempotent and replay-safe.
- Checkpoint advance occurs only after durable state commit (transactional state + checkpoint write).
- `input_basis` vector can be reconstructed from checkpoint state at any time.
- Required pins are validated per event; run-scope violations fail closed.
- Evidence: `python -m pytest tests/services/online_feature_plane -q` -> `6 passed`; details logged in `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`.

### Phase 3 - Feature definitions and windows (4.3.B)
**Intent:** make feature computation versioned and reproducible.
**Status:** completed (2026-02-06, component scope).

**DoD checklist:**
- Feature definition source is singular and version-locked.
- Window definitions and TTLs are explicit (v0 defaults: `1h/24h/7d`, configurable).
- No implicit "latest feature definition" at runtime; active revision is declared and logged.
- Definition/profile revision is carried into provenance (`feature_def_policy_rev` or digest).
- Evidence: `python -m pytest tests/services/online_feature_plane -q` -> `9 passed`; details in `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`.

### Phase 4 - Snapshot materialization and index (4.3.C, 4.3.D)
**Intent:** serve immutable snapshots without duplicating truth incorrectly.
**Status:** completed (2026-02-06, component scope).

**DoD checklist:**
- Snapshot artifact stored by-ref in object store (JSON v0, optional compression).
- Snapshot index metadata persisted in Postgres:
  - `snapshot_hash`
  - `graph_version` (nullable)
  - `input_basis`
  - `run_config_digest`
  - object-store ref
- Snapshot retrieval by hash is deterministic and immutable.
- Snapshot record includes enough basis to replay and compare with OFS parity builds.
- Evidence: `python -m pytest tests/services/online_feature_plane -q` -> `10 passed`; details in `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`.

### Phase 5 - Serve API and deterministic semantics (4.3.E)
**Intent:** DF receives stable features for decision-time use.

**DoD checklist:**
- `get_features` requires `as_of_time_utc` and never defaults to hidden "now".
- Response basis is atomic per response (single coherent `input_basis` token).
- If IEG is consulted, returned `graph_version` is stamped in provenance.
- Missing or stale dependencies surface explicit posture flags for DF/DL degrade handling.

### Phase 6 - Rebuild and replay determinism (4.3.F, 4.3.H)
**Intent:** prove OFP can be rebuilt and matched.

**DoD checklist:**
- Replay from same basis yields identical `snapshot_hash` and values.
- Determinism test covers:
  - duplicate deliveries
  - out-of-order arrivals
  - restart/resume from checkpoints
- Parity contract for OFS is pinned:
  - same feature definitions
  - same basis
  - same expected `snapshot_hash` behavior

### Phase 7 - Health and observability (4.3.G)
**Intent:** expose actionable operational truth to DL and operators.

**DoD checklist:**
- Core counters exist and are exported:
  - `snapshots_built`
  - `snapshot_failures`
  - `events_applied`
  - `duplicates`
  - `stale_graph_version`
  - `missing_features`
  - lag and watermark age
- Health status model is explicit (GREEN/AMBER/RED with thresholds).
- Serve responses can carry stale/missing posture without hiding degraded context.

### Phase 8 - Integration closure (4.3 -> 4.4 readiness)
**Intent:** close OFP component DoDs and prepare handoff to DF/DL integration.

**DoD checklist:**
- DF compatibility checks pass for required provenance fields.
- DL can consume OFP health/degrade signals for policy posture.
- OFS parity checkpoints and evidence format are agreed and documented.
- Runbook steps exist for local_parity validation of OFP end-to-end path.

## Validation gate (required before phase advancement)
- Unit tests for:
  - hash determinism
  - idempotent apply
  - as-of semantics
  - window TTL behavior
- Replay test: same offsets -> same snapshot hash and state.
- Integration test: `EB -> OFP -> DF-contract` with provenance assertions.
- Evidence logged in:
  - `docs/model_spec/platform/implementation_maps/online_feature_plane.impl_actual.md`
  - `docs/logbook/<month>/<date>.md`

## Non-goals for v0
- No OFP-authored decisionable bus stream.
- No silent fallback on missing feature definitions.
- No cross-run shared cache treated as truth.
