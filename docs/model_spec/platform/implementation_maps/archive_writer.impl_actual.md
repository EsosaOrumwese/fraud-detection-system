# Archive Writer Implementation Map
_As of 2026-02-10_

---

## Entry: 2026-02-10 10:34AM - Phase 6.0 execution start (archive readiness corridor)

### Problem / goal
Implement a production-shaped `archive_writer` component for local parity so archive truth is no longer implied. The worker must copy admitted EB events to immutable archive records carrying origin-offset provenance and ContextPins, expose run-scoped health/metrics/reconciliation artifacts, and surface replay-basis mismatch anomalies.

### Inputs / authorities
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (archive writer semantics, replay mismatch fail-closed)
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md` (H1 Archive continuation of EB; H5 DatasetManifest bridge)
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md` (Archive RTA posture)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`Phase 6.0` DoD)
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

### Design choices (pre-code)
1. Worker mode:
   - single worker process in local parity pack, consuming admitted topics from EB.
2. Archive addressing:
   - immutable object path per origin-offset tuple:
     - `{platform_run_id}/archive/events/topic=<topic>/partition=<partition>/offset_kind=<kind>/offset=<offset>.json`
3. Replay-basis integrity:
   - ledger key uses `(stream_id, topic, partition, offset_kind, offset)`.
   - same key + different payload hash -> `PAYLOAD_HASH_MISMATCH` anomaly surface.
4. State backend:
   - configurable locator (Postgres in parity by default via env), with sqlite fallback available for non-parity local use.
5. Observability:
   - run-scoped metrics at `runs/<platform_run_id>/archive_writer/metrics/last_metrics.json`,
   - health at `runs/<platform_run_id>/archive_writer/health/last_health.json`,
   - reconciliation at `runs/<platform_run_id>/archive/reconciliation/archive_writer_reconciliation.json`.

### Validation plan
- unit tests for archive contract validation + hash stability,
- unit tests for ledger dedupe/mismatch behavior,
- worker run-once test with file-bus fixtures ensuring immutable archive write + metrics/reconciliation generation.

## Entry: 2026-02-10 10:49AM - Archive writer implementation applied + Postgres schema fix

### Implemented artifacts
- New component package:
  - `src/fraud_detection/archive_writer/contracts.py`
  - `src/fraud_detection/archive_writer/store.py`
  - `src/fraud_detection/archive_writer/observability.py`
  - `src/fraud_detection/archive_writer/reconciliation.py`
  - `src/fraud_detection/archive_writer/worker.py`
  - `src/fraud_detection/archive_writer/__init__.py`
- Profile + run/operate onboarding:
  - `config/platform/archive_writer/policy_v0.yaml`
  - `config/platform/archive_writer/topics_v0.yaml`
  - `config/platform/profiles/local_parity.yaml` (`archive_writer` section)
  - `config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml` (`archive_writer_worker`)
  - `makefile` + `.env.platform.local` (`PARITY_ARCHIVE_WRITER_LEDGER_DSN`)
- Obs/Gov/reporter integration:
  - `src/fraud_detection/platform_reporter/run_reporter.py` archive summary + reconciliation ref discovery.

### Runtime issue encountered
- Initial daemon start failed in local-parity Postgres mode:
  - `psycopg.errors.SyntaxError` due reserved SQL identifier `offset` in archive ledger schema.

### Decision and corrective action
- Renamed SQL column `offset` -> `offset_value` across archive ledger tables/queries.
- Revalidated worker startup under run/operate pack; process now remains running-ready.

### Validation results
- Targeted tests:
  - `tests/services/archive_writer/*` green
- Integration regressions:
  - `tests/services/platform_reporter/test_run_reporter.py` green
- Run/operate status:
  - `local_parity_rtdl_core_v0` now includes `archive_writer_worker` and reports `running ready`.
- Run-scoped artifacts observed:
  - `runs/fraud-platform/<platform_run_id>/archive_writer/metrics/last_metrics.json`
  - `runs/fraud-platform/<platform_run_id>/archive_writer/health/last_health.json`
  - `runs/fraud-platform/<platform_run_id>/archive/reconciliation/archive_writer_reconciliation.json`

## Entry: 2026-02-10 10:54AM - Phase 6.0 verification rerun and operational evidence capture

### Why this follow-up entry exists
Close the component decision trail with explicit post-fix validation after introducing archive writer into run/operate and reporter surfaces.

### Validation rerun
- Syntax check:
  - `python -m py_compile src/fraud_detection/archive_writer/contracts.py src/fraud_detection/archive_writer/store.py src/fraud_detection/archive_writer/observability.py src/fraud_detection/archive_writer/reconciliation.py src/fraud_detection/archive_writer/worker.py` (`PASS`).
- Test matrix:
  - `python -m pytest tests/services/archive_writer tests/services/platform_reporter/test_run_reporter.py -q --import-mode=importlib` (`PASS`, included in combined Phase 6.0/6.1 matrix).

### Operational evidence snapshot
- Executed `make platform-run-report` against active run `platform_20260210T091951Z`.
- Reporter output confirms:
  - `archive` top-level section emitted in report payload,
  - archive reconciliation ref discovered under `component_reconciliation_refs`,
  - archive health reported `GREEN`.

### Observed caveat and interpretation
- Archive counters in this specific snapshot are `0` (`seen_total=0`, `archived_total=0`) because no new stream session was run after worker onboarding for this run id.
- This is acceptable for readiness closure because corridor/process/reporting are live and validated; non-zero stream proof should be captured during next strict live-stream gate run in later Phase 6 integration gates.

### Security note
- No credentials/tokens added to component docs; only by-ref run artifact paths recorded.
