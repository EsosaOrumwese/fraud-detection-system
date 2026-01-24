# Scenario Runner service
Status: v0 (in progress).
Purpose: Run authority + join surface publisher.
Owns: run_plan/run_record/run_status/run_facts_view; READY control signal.
Boundaries: engine internals; ingestion; downstream processing.

Notes: This service is the control-plane entrypoint for runs. It must stay fail-closed and by-ref.
run_facts_view now includes engine-contract digest objects and may include optional `instance_receipts` for instance-scoped outputs.
SR emits **verifier receipts** in its own object store (engine remains a black box):
- `fraud-platform/sr/instance_receipts/output_id=<output_id>/<scope partitions>/instance_receipt.json`

Profiles:
- `config/platform/sr/wiring_local.yaml` — local smoke (filesystem + SQLite; not valid for hardening).
- `config/platform/sr/wiring_local_parity.yaml` — local parity (MinIO + Postgres).
- `config/platform/sr/wiring_aws.yaml` — AWS target (S3 + RDS Postgres + Kinesis placeholder).
  - Note: wiring profiles now include `engine_contracts_root` (engine boundary schemas).

Policy:
- `config/platform/sr/policy_v0.yaml` omits any instance‑proof bridge; SR emits verifier receipts directly.

Local parity stack (MinIO + Postgres):
- `docker compose -f infra/local/docker-compose.sr-parity.yaml up -d`
- MinIO console: http://localhost:9001 (minio / minio123)
- Bucket created: `sr-local`
- Postgres port: 5433 (user/pass/db: sr / sr / sr_dev)

Phase 2.5 integration tests (local parity):
1) Ensure Docker stack is up (command above).
2) Load env vars from `.env` (PowerShell):
   - `Get-Content .env | ForEach-Object { if ($_ -match '^(\\w+)=(.*)$') { Set-Item -Path "Env:$($matches[1])" -Value $matches[2] } }`
3) Run tests:
   - `& .\\.venv\\Scripts\\python.exe -m pytest tests/services/scenario_runner/test_s3_store.py tests/services/scenario_runner/test_authority_store_postgres.py`
