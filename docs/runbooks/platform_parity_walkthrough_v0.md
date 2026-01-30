# Platform Parity Walkthrough (v0) — Oracle Store → SR → WSP → IG → EB
_As of 2026-01-30_

This runbook executes a **local_parity** end‑to‑end flow capped to **500,000 events**.
It uses **MinIO (S3)** for the Oracle Store + platform artifacts, **LocalStack Kinesis** for control/event buses, and **Postgres** for IG/WSP state.

---

## 0) Preconditions

**Required local stack (parity):**
- MinIO (S3‑compatible) for `oracle-store` and `fraud-platform` buckets
- LocalStack Kinesis for `sr-control-bus` and `fp-traffic-bus`
- Postgres for IG admission DB + WSP checkpoints

**Profiles used:**
- `config/platform/profiles/local_parity.yaml`
- `config/platform/sr/wiring_local_kinesis.yaml`

**Oracle Store assumption:**
The engine outputs exist locally **and are synced into MinIO** (Oracle Store) before sealing. The packer writes
manifest/seal files; it does not copy the dataset unless you sync it.

---

## 1) Start parity stack

```
make platform-parity-stack-up
make platform-parity-bootstrap
make platform-parity-stack-status
```

**Expected:**
- MinIO + Postgres + LocalStack are running.
- Buckets exist: `oracle-store`, `fraud-platform`.
- Streams exist: `sr-control-bus`, `fp-traffic-bus`.

**What bootstrap does:**
- Creates the **Kinesis streams** in LocalStack (`sr-control-bus`, `fp-traffic-bus`).
- Creates the **MinIO buckets** (`oracle-store`, `fraud-platform`).

---

## 2) Set parity environment variables (no secrets stored)

> Use your own values or set these in a `.env.platform.local` file.  
> Do **not** write secrets into docs or git.

```
$env:PARITY_OBJECT_STORE_ENDPOINT="http://localhost:9000"
$env:PARITY_OBJECT_STORE_REGION="us-east-1"
$env:PARITY_MINIO_ACCESS_KEY="<minio_access_key>"
$env:PARITY_MINIO_SECRET_KEY="<minio_secret_key>"

$env:PARITY_AWS_ACCESS_KEY_ID="<localstack_access_key>"
$env:PARITY_AWS_SECRET_KEY="<localstack_secret_key>"
$env:PARITY_AWS_EC2_METADATA_DISABLED="true"

$env:PARITY_CONTROL_BUS_STREAM="sr-control-bus"
$env:PARITY_CONTROL_BUS_REGION="us-east-1"
$env:PARITY_CONTROL_BUS_ENDPOINT_URL="http://localhost:4566"

$env:PARITY_EVENT_BUS_STREAM="fp-traffic-bus"
$env:PARITY_EVENT_BUS_REGION="us-east-1"
$env:PARITY_EVENT_BUS_ENDPOINT_URL="http://localhost:4566"

$env:PARITY_IG_ADMISSION_DSN="<postgres_dsn>"
$env:PARITY_WSP_CHECKPOINT_DSN="<postgres_dsn>"

$env:OBJECT_STORE_ENDPOINT="http://localhost:9000"
$env:OBJECT_STORE_REGION="us-east-1"
$env:AWS_ACCESS_KEY_ID="<minio_access_key>"
$env:AWS_SECRET_ACCESS_KEY="<minio_secret_key>"

$env:ORACLE_ROOT="s3://oracle-store"
$env:ORACLE_PACK_ROOT="s3://oracle-store/local_full_run-5/pack_<timestamp>"
$env:ORACLE_ENGINE_RUN_ROOT="s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92"
$env:ORACLE_SCENARIO_ID="baseline_v1"
$env:ORACLE_ENGINE_RELEASE="local"
```

---

## 3) Create a new platform run id

```
make platform-run-new
```

**Find the run id:**
```
Get-Content runs/fraud-platform/ACTIVE_RUN_ID
```

Artifacts and logs will live under:
```
runs/fraud-platform/<platform_run_id>/
```

---

## 4) Populate Oracle Store in MinIO (sync + seal)

This step does **two things**: (1) copy the engine outputs into MinIO, (2) write the Oracle pack manifest + seal.

**4.1 Sync engine outputs into MinIO**
```
AWS_ACCESS_KEY_ID=<minio_access_key> AWS_SECRET_ACCESS_KEY=<minio_secret_key> AWS_DEFAULT_REGION=us-east-1 AWS_EC2_METADATA_DISABLED=true `
aws --endpoint-url http://localhost:9000 s3 sync `
  runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92 `
  s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92
```

**Why this prefix is required:** the AWS CLI does **not** read `.env.platform.local`. It uses its own credential chain, so we explicitly inject MinIO creds for this one command without touching real AWS credentials.

**4.2 Seal the Oracle pack (manifest + _SEALED.json)**
```
make platform-oracle-pack `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT `
  ORACLE_SCENARIO_ID=$env:ORACLE_SCENARIO_ID `
  ORACLE_ENGINE_RELEASE=$env:ORACLE_ENGINE_RELEASE
```

Optional strict‑seal check:
```
make platform-oracle-check-strict `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT
```

**Expected:** strict‑seal reports OK or no errors.

**If you hit `MANIFEST_MISMATCH`:**
- Use a fresh pack root:
```
$env:ORACLE_PACK_ROOT="s3://oracle-store/local_full_run-5/pack_<timestamp>"
make platform-oracle-pack ORACLE_PROFILE=config/platform/profiles/local_parity.yaml
```
- Or skip packing and verify the existing pack:
```
make platform-oracle-check-strict ORACLE_PROFILE=config/platform/profiles/local_parity.yaml
```

**Note:** Oracle pack uses `OBJECT_STORE_ENDPOINT/REGION` + `AWS_ACCESS_KEY_ID/SECRET` for MinIO access. If those are unset, boto may fall back to your shared AWS credentials and the endpoint may be invalid.

---

## 5) Start IG service (parity profile)

In a **separate terminal**:
```
make platform-ig-service-parity
```

---

## 6) SR publishes READY (control bus)

```
make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml
```

**Expected in platform log:**
- `SR: submit request received`
- `SR: READY committed`
- `READY published`

---

## 7) WSP consumes READY and streams 500k events

```
$env:WSP_READY_MAX_EVENTS="500000"
make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml
```

**Expected:**
- WSP reads READY from Kinesis
- WSP streams up to 500k events to IG
- IG admits and publishes to EB (Kinesis)

---

## 8) Observe logs (single run, all components)

Tail the platform log:
```
Get-Content runs/fraud-platform/<platform_run_id>/platform.log -Wait
```

Look for:
- **SR**: `READY committed`, `READY published`
- **WSP**: `READY poll processed=...` and `STREAMED`
- **IG**: `admitted`, `receipt emitted`
- **EB**: publish acknowledgements (offsets)

---

## 9) Verify artifacts (MinIO)

List SR artifacts:
```
aws --endpoint-url http://localhost:9000 s3 ls s3://fraud-platform/<platform_run_id>/sr/
```

List IG receipts:
```
aws --endpoint-url http://localhost:9000 s3 ls s3://fraud-platform/<platform_run_id>/ig/receipts/ | Select-Object -First 5
```

Fetch a receipt:
```
aws --endpoint-url http://localhost:9000 s3 cp s3://fraud-platform/<platform_run_id>/ig/receipts/<receipt_id>.json -
```

**Expected:** receipt contains an `eb_ref` with `offset_kind: kinesis_sequence`.

---

## 10) Verify EB records (LocalStack Kinesis)

List streams:
```
aws --endpoint-url http://localhost:4566 kinesis list-streams
```

Read a few records:
```
$iterator = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp-traffic-bus `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $iterator --limit 5
```

**Expected:** payloads are canonical envelopes (base64 in Kinesis).

---

## 11) Shutdown (optional)
```
make platform-parity-stack-down
```

---

## What “green” looks like
- SR emits READY with facts_view + oracle_pack_ref.
- WSP streams and records READY processing under `wsp/ready_runs`.
- IG admits events and writes receipts under `ig/receipts`.
- EB offsets advance and are visible in receipt `eb_ref`.
- Platform log shows SR → WSP → IG → EB in order for the same run id.


