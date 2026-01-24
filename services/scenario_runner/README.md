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
- `config/platform/sr/wiring_local_kinesis.yaml` — local parity + LocalStack Kinesis (control bus).
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

LocalStack Kinesis test (end-to-end):
1) Start LocalStack (Kinesis enabled):
   - `docker run --rm -p 4566:4566 -e SERVICES=kinesis localstack/localstack:latest`
   - Optional (narrative logs): `.\scripts\localstack.ps1 logs`
2) Set env vars (PowerShell):
   - `Get-Content .env.localstack.example | ForEach-Object { if ($_ -match '^(\\w+)=(.*)$') { Set-Item -Path "Env:$($matches[1])" -Value $matches[2] } }`
   - (or set them manually below)
   - `$env:SR_KINESIS_ENDPOINT_URL="http://localhost:4566"`
   - `$env:SR_KINESIS_STREAM="sr-control-bus"`
   - `$env:SR_KINESIS_REGION="us-east-1"`
   - `$env:AWS_ACCESS_KEY_ID="test"`
   - `$env:AWS_SECRET_ACCESS_KEY="test"`
3) Run the Kinesis adapter test:
   - `& .\\.venv\\Scripts\\python.exe -m pytest tests/services/scenario_runner/test_control_bus_kinesis.py -q`

Test tiers (Phase 8):
- Tier 0 (default, fast): unit + fast integration (no external services).
  - `python -m pytest tests/services/scenario_runner -m "not parity and not localstack and not engine_fixture" -q`
- Tier 1 (parity: MinIO + Postgres): requires `SR_TEST_S3_BUCKET` + `SR_TEST_PG_DSN`.
  - Optional: `SR_TEST_S3_ENDPOINT_URL`, `SR_TEST_S3_REGION`, `SR_TEST_S3_PATH_STYLE`.
  - `python -m pytest tests/services/scenario_runner -m "parity" -q`
- Tier 2 (LocalStack Kinesis): requires the env vars above for LocalStack.
  - `python -m pytest tests/services/scenario_runner -m "localstack" -q`
- Tier 3 (engine fixtures): requires `runs/local_full_run-*` artifacts.
  - `python -m pytest tests/services/scenario_runner -m "engine_fixture" -q`

CI gates (recommended):
- PR gate: Tier 0 only.
- Nightly/manual: Tier 1 + Tier 2 + Tier 3.

Helper script (PowerShell):
- `.\scripts\run_sr_tests.ps1 -Tier tier0`
- `.\scripts\run_sr_tests.ps1 -Tier parity`
- `.\scripts\run_sr_tests.ps1 -Tier localstack`
- `.\scripts\run_sr_tests.ps1 -Tier engine_fixture`
