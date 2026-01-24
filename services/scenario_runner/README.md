# Scenario Runner service
Status: v0 (in progress).
Purpose: Run authority + join surface publisher.
Owns: run_plan/run_record/run_status/run_facts_view; READY control signal.
Boundaries: engine internals; ingestion; downstream processing.

Notes: This service is the control-plane entrypoint for runs. It must stay fail-closed and by-ref.

Profiles:
- `config/platform/sr/wiring_local.yaml` — local smoke (filesystem + SQLite; not valid for hardening).
- `config/platform/sr/wiring_local_parity.yaml` — local parity (MinIO + Postgres).
- `config/platform/sr/wiring_aws.yaml` — AWS target (S3 + RDS Postgres + Kinesis placeholder).
