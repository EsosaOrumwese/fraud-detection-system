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

Local parity stack (MinIO + Postgres):
- `docker compose -f infra/local/docker-compose.sr-parity.yaml up -d`
- MinIO console: http://localhost:9001 (minio / minio123)
- Bucket created: `sr-local`
- Postgres port: 5433 (user/pass/db: sr / sr / sr_dev)

Phase 2.5 integration tests (local parity):
1) Ensure Docker stack is up (command above).
2) Load env vars from `.env` (PowerShell):
   - `Get-Content .env | ForEach-Object { if ($_ -match '^(\\w+)=(.*)$') { $env:$($matches[1])=$matches[2] } }`
3) Run tests:
   - `& .\\.venv\\Scripts\\python.exe -m pytest tests/services/scenario_runner/test_s3_store.py tests/services/scenario_runner/test_authority_store_postgres.py`
