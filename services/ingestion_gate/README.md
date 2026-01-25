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

Lookup outcomes:
```
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-event-id <event_id>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-receipt-id <receipt_id>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --lookup-dedupe-key <dedupe_key>
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --rebuild-index
python -m fraud_detection.ingestion_gate.cli --profile config/platform/profiles/local.yaml --health
```

Smoke test (uses runs/ artifacts if present):
```
python -m pytest tests/services/ingestion_gate/test_ops_rebuild_runs_smoke.py -q
```

## Service (local)
Run HTTP service:
```
python -m fraud_detection.ingestion_gate.service --profile config/platform/profiles/local.yaml --port 8081
```
Enable READY polling inside the service (PowerShell):
```
$env:IG_READY_CONSUMER="1"
```

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

Notes:
- This smoke test looks for SR artifacts under:
  - `%SR_ARTIFACTS_ROOT%` (preferred)
  - `artefacts/fraud-platform/sr` (repo-local default)
- If none are found, the test skips with a clear message.
```

## Notes
- IG validates canonical envelopes and applies schema policy allowlists.
- EB publisher is a **local file bus** for v0 tests; Kafka-compatible adapter will be plugged in later.
- Receipts/quarantine are written by-ref under `fraud-platform/ig/`.
