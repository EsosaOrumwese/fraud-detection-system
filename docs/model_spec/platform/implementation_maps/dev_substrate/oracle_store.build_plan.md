# Oracle Store Build Plan (dev_substrate, engine-owned truth)
_As of 2026-02-11_

## Objective
Close Phase `3.C.1` with the correct ownership posture:
1. Data Engine is the producer/owner of Oracle artifacts.
2. Platform is a consumer that must use explicit Oracle pins and fail closed when Oracle truth is missing/ambiguous.
3. Until direct engine->AWS S3 write is configured, `dev_min` uses controlled landing sync/backfill into the managed Oracle root.

## Ownership boundary (non-negotiable)
- Data Engine owns:
  - Oracle world artifact production,
  - artifact structure and semantic truth.
- Platform owns:
  - selecting one explicit Oracle root for the run,
  - validating availability/compatibility for downstream consumption,
  - preserving by-ref provenance in SR/WSP/IG evidence.

## Current migration mode and target mode
- Mode A (current, transitional):
  - source engine run artifacts are copied/synced into AWS S3 Oracle root.
- Mode B (target):
  - engine writes Oracle artifacts directly to the AWS S3 Oracle root.
- Acceptance law:
  - Platform contracts must be identical in both modes (only ingestion path changes).

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.1`)
- Local baseline carry-forward:
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.build_plan.md`

## O1 phase plan (authority lock via managed landing)
### O1.A Source pin and landing contract
**Intent:** remove ambiguity before any copy/sync starts.

**Implementation checklist:**
- [ ] Pin source engine run artifact root (`source_root`) and scenario scope.
- [ ] Pin managed Oracle destination root (`oracle_engine_run_root`) under settlement `oracle_prefix`.
- [ ] Pin `oracle_stream_view_root` and scenario id expected by SR/WSP.
- [ ] Record pinned refs in run-scoped evidence.

**DoD:**
- [ ] No implicit `latest` selection.
- [ ] Root + scenario pins are explicit and non-empty.
- [ ] Destination root is `s3://...` and not local-path derived.

### O1.B Managed landing sync/backfill
**Intent:** land Oracle artifacts in AWS S3 while preserving source fidelity.

**Implementation checklist:**
- [ ] Execute deterministic one-way sync from `source_root` -> `oracle_engine_run_root`.
- [ ] Collect transfer evidence (source root, destination root, object count/sample).
- [ ] Allow long-running sync to continue while other C&I component build work proceeds.

**DoD:**
- [ ] Landing copy is complete enough for Oracle validation gates.
- [ ] Sync evidence is emitted and linked.
- [ ] No destructive mutation of source root occurs.

### O1.C Oracle authority validation (consumer-side)
**Intent:** prove platform can safely consume the landed Oracle truth.

**Implementation checklist:**
- [ ] Validate required receipt/seal/manifest artifacts under destination root.
- [ ] Validate required stream-view roots and output-id paths for active scenario.
- [ ] Emit stable fail reasons on missing/ambiguous Oracle artifacts.

**DoD:**
- [ ] Validation PASS is evidenced by-ref.
- [ ] Any missing required artifact is `FAIL_CLOSED`.
- [ ] Local fallback is rejected under `dev_min`.

### O1.D Platform contract readiness for SR/WSP
**Intent:** ensure downstream components consume a single authoritative Oracle identity.

**Implementation checklist:**
- [ ] SR run facts and WSP source wiring resolve to the same pinned root/scenario.
- [ ] Root/scope mismatch is blocked before integrated stream tests.
- [ ] Contract refs are linkable in governance/report evidence.

**DoD:**
- [ ] SR/WSP Oracle root identity is consistent for the run.
- [ ] Mixed-root posture is blocked.
- [ ] Evidence graph preserves provenance by-ref.

### O1.E Closure and gating rule
**Intent:** define exactly what is blocked vs allowed while sync is in-flight.

**Allowed while sync is in-flight:**
- Build/config wiring for SR/WSP/IG/EB components.
- Non-integrated component matrix prep that does not require live Oracle consumption.

**Blocked until O1 is green:**
- Coupled C&I integrated run (`3.C.6` path).
- Any acceptance claiming Oracle authority is ready.

**DoD:**
- [ ] O1 PASS evidence exists and is linked in impl/logbook notes.
- [ ] Platform `3.C.1` may be marked complete only after O1 closure evidence.

## Validation matrix expectations for Oracle in dev_substrate
- Mandatory PASS set:
  - source/destination pin contract complete,
  - landing sync evidence complete,
  - receipt/seal/manifest checks complete,
  - stream-view presence checks complete,
  - SR/WSP root-coupling checks complete.
- Failure policy:
  - unknown/missing/ambiguous Oracle contract evidence => `FAIL_CLOSED`.

## Security and cost posture
- Never store credentials or secret values in docs/evidence/logbook.
- Track S3 sync/list/head activity as paid-surface usage.
- Record `KEEP ON` / `TURN OFF NOW` decision after each O1 execution step.

## Current status
- O1.A: not started
- O1.B: not started
- O1.C: not started
- O1.D: not started
- O1.E: not started
