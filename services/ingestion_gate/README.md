# Ingestion Gate (IG) Service
_As of 2026-01-25_

This is a minimal service wrapper for IG v0. It supports:
- **Pull ingestion** from SR `run_facts_view` (engine materialized outputs).
- **Push ingestion** for pre-framed canonical envelopes.

## CLI (local)
Run pull ingestion:
```
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --run-facts <path-to-run_facts_view.json>
```

Run push ingestion:
```
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --push-file <path-to-envelope.json>
```

Lookup outcomes:
```
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-event-id <event_id>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-receipt-id <receipt_id>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-dedupe-key <dedupe_key>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --rebuild-index
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --health
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --audit-verify <run_id>
```

Smoke test (uses SR artifacts if present):
```
python -m pytest tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q
```

Notes:
- This smoke test looks for SR artifacts under:
  - `%SR_ARTIFACTS_ROOT%` (preferred)
  - `runs/fraud-platform/sr` (repo-local default)
- If none are found, the test skips with a clear message.
- SR/IG append to a shared platform log by default: `runs/fraud-platform/platform.log`. Override with `PLATFORM_LOG_PATH` if needed.
- Optional per‑session logs live under `runs/fraud-platform/platform_runs/<platform_run_id>/platform.log` when a run ID is set.
- `pull_time_budget_seconds` (profile wiring) can cap local smoke runs; leave unset for production.

## Service (local)
Run HTTP service:
```
python -m fraud_detection.ingestion_gate.service --profile config/platform/profiles/local.yaml --port 8081
```

Enable READY polling inside the service (PowerShell):
```
$env:IG_READY_CONSUMER="1"
```

Auth + rate limits (profile wiring):
- `wiring.security.auth_mode: api_key` to require API keys on `/v1/ingest/*` and `/v1/ops/*`.
- `wiring.security.auth_allowlist_ref` points to a newline-delimited allowlist file.
- `wiring.security.push_rate_limit_per_minute` and `ready_rate_limit_per_minute` enforce basic backpressure.
- `wiring.ready_lease.backend: postgres` enables distributed READY consumption (requires DSN in env).

Push ingest example:
```
curl -X POST http://127.0.0.1:8081/v1/ingest/push ^
  -H "Content-Type: application/json" ^
  -d "{\"event_id\":\"evt-1\",\"event_type\":\"arrival_events_5B\",\"ts_utc\":\"2026-01-01T00:00:00.000000Z\",\"manifest_fingerprint\":\"<hex64>\",\"payload\":{}}"
```

Pull ingest example:
```
curl -X POST http://127.0.0.1:8081/v1/ingest/pull ^
  -H "Content-Type: application/json" ^
  -d "{\"run_id\":\"<run_id>\"}"
```

## READY consumer (local file control bus)
Process READY events once:
```
python -m fraud_detection.ingestion_gate.ready_consumer --profile config/platform/profiles/local.yaml --once
```

Run READY poll loop:
```
python -m fraud_detection.ingestion_gate.ready_consumer --profile config/platform/profiles/local.yaml --interval 2
```

## Runbook + alerts (Phase 5)
Failure modes and first actions:
- **IG health RED (IG_UNHEALTHY)**: check object store access, ops DB path, and bus connectivity; re-run `--health` to confirm reasons.
- **RUN_FACTS_UNREADABLE / RUN_FACTS_MISSING**: verify `run_facts_view` path or S3 endpoint/region/path-style settings; confirm SR READY emitted a facts ref.
- **EB_PUBLISH_FAILED**: verify EB endpoint, topic availability, and permissions; health should flip RED if failures persist.
- **RATE_LIMITED**: increase limits or reduce caller concurrency; READY consumer should back off rather than re-ingest.
- **RUN_NOT_ALLOWED / UNAUTHORIZED**: confirm allowlists and API key header name; rotate allowlist files if needed.

Alert triggers to wire:
- Health state transitions to RED/AMBER (bus, store, or ops DB degradation).
- Quarantine spikes (threshold over rolling window; see `wiring.quarantine_spike_*`).
- READY processing failures (status=FAILED in pull run records, missing facts refs).

Operational signals:
- Metrics log lines (`IG metrics`) include counters and latencies:
  - `phase.validate_seconds`, `phase.verify_seconds`, `phase.publish_seconds`, `phase.receipt_seconds`
  - `admission_seconds` (end-to-end admission)
- Governance events: `ig.policy.activation`, `ig.pull.run`, and quarantine spike notices are emitted to the audit/control bus.
