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

Notes:
- This smoke test looks for SR artifacts under:
  - `%SR_ARTIFACTS_ROOT%` (preferred)
  - `%TEMP%\\artefacts\\fraud-platform\\sr`
  - `artefacts/fraud-platform/sr` (repo-local)
- If none are found, the test skips with a clear message.
```

## Notes
- IG validates canonical envelopes and applies schema policy allowlists.
- EB publisher is a **local file bus** for v0 tests; Kafka-compatible adapter will be plugged in later.
- Receipts/quarantine are written by-ref under `fraud-platform/ig/`.
