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

## Notes
- IG validates canonical envelopes and applies schema policy allowlists.
- EB publisher is a **local file bus** for v0 tests; Kafka-compatible adapter will be plugged in later.
- Receipts/quarantine are written by-ref under `fraud-platform/ig/`.
