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

## 2) Confirm parity env in `.env.platform.local`

Make loads `.env.platform.local` automatically. You should not need to export these unless you are overriding a value.

```
PARITY_OBJECT_STORE_ENDPOINT=http://localhost:9000
PARITY_OBJECT_STORE_REGION=us-east-1
PARITY_MINIO_ACCESS_KEY=<minio_access_key>
PARITY_MINIO_SECRET_KEY=<minio_secret_key>

PARITY_AWS_ACCESS_KEY_ID=<localstack_access_key>
PARITY_AWS_SECRET_KEY=<localstack_secret_key>
PARITY_AWS_EC2_METADATA_DISABLED=true

PARITY_CONTROL_BUS_STREAM=sr-control-bus
PARITY_CONTROL_BUS_REGION=us-east-1
PARITY_CONTROL_BUS_ENDPOINT_URL=http://localhost:4566

PARITY_EVENT_BUS_STREAM=fp-traffic-bus
PARITY_EVENT_BUS_REGION=us-east-1
PARITY_EVENT_BUS_ENDPOINT_URL=http://localhost:4566

PARITY_IG_ADMISSION_DSN=<postgres_dsn>
PARITY_WSP_CHECKPOINT_DSN=<postgres_dsn>

OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_REGION=us-east-1
AWS_ACCESS_KEY_ID=<minio_access_key>
AWS_SECRET_ACCESS_KEY=<minio_secret_key>
AWS_EC2_METADATA_DISABLED=true

ORACLE_ROOT=s3://oracle-store
ORACLE_ENGINE_RUN_ROOT=s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92
ORACLE_PACK_ROOT=s3://oracle-store/local_full_run-5/pack_current
ORACLE_SYNC_SOURCE=runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92
ORACLE_SCENARIO_ID=baseline_v1
ORACLE_ENGINE_RELEASE=local
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
make platform-oracle-sync
```

This uses:
- `ORACLE_SYNC_SOURCE` (local engine run path)
- `ORACLE_ENGINE_RUN_ROOT` (S3 path in MinIO)

MinIO runs locally, so this **copies** the engine outputs into the MinIO volume (disk usage will increase accordingly).

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

**If you hit `MANIFEST_MISMATCH`:** set a fresh pack root (e.g., `pack_YYYYMMDDTHHMMSSZ`) and re‑run `make platform-oracle-pack`.

**Note:** Oracle pack uses the MinIO S3 endpoint + credentials from `.env.platform.local` (exported by Make).

---

## 5) Start IG service (parity profile)

**What this does:** starts the **Ingestion Gate HTTP service** that receives streamed traffic from WSP, validates it against schema + policy, and writes receipts + admission state to the platform run. It must stay running while SR/WSP execute.

In a **separate terminal**:
```
make platform-ig-service-parity
```

**IG service URL:** `http://127.0.0.1:8081`  
The root path (`/`) is not defined, so a browser at `http://127.0.0.1:8081` will show **Not Found**.  

**Health check (expected before traffic):**
```
Invoke-RestMethod http://127.0.0.1:8081/v1/ops/health
```
Example output:
```
reasons              state
-------              -----
{BUS_HEALTH_UNKNOWN} AMBER
```

**Why AMBER is OK here:** the event bus has not been exercised yet. After SR publishes READY and WSP streams, health should move toward GREEN.

---

## 6) SR publishes READY (control bus)

```
make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml
```

**Note:** SR writes run artifacts to MinIO S3 in parity mode. If you see a `403` here, confirm `.env.platform.local` has the MinIO credentials set and re‑run.

**Expected in platform log:**
- `SR: submit request received`
- `SR: READY committed`
- `READY published`

**If you see `LEASE_BUSY`:**
SR found an existing lease for the same run equivalence key. Set a new key and re‑run:
```
$env:SR_RUN_EQUIVALENCE_KEY="parity_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml
```

If you want to reuse the same equivalence key, either:
- **Wait for TTL** (default 300s), then re‑run; or
- **Clear the lease** in Postgres (run_id shown in SR output):
```
docker exec local-postgres-1 psql -U platform -d platform -c "delete from sr_run_leases where run_id='<run_id>';"
```

---

## 7) WSP consumes READY and streams 500k events

```
$env:WSP_READY_MAX_EVENTS="500000"; make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml
```

**Expected:**
- WSP reads READY from Kinesis
- WSP streams up to 500k events to IG
- IG admits and publishes to EB (Kinesis)

**If you see `Invalid endpoint`:** verify `.env.platform.local` has `OBJECT_STORE_ENDPOINT` and MinIO creds; Make exports them to WSP.
**If you see `CONTROL_BUS_STREAM_MISSING`:** ensure `PARITY_CONTROL_BUS_STREAM/REGION/ENDPOINT_URL` are set in `.env.platform.local` (Make exports them as `CONTROL_BUS_*` for WSP).
**If you see `CHECKPOINT_DSN_MISSING`:** ensure `PARITY_WSP_CHECKPOINT_DSN` is set in `.env.platform.local` (Make exports it as `WSP_CHECKPOINT_DSN`).
**If you see `Invalid URL '/v1/ingest/push'`:** ensure `PARITY_IG_INGEST_URL` is set in `.env.platform.local` (Make exports it as `IG_INGEST_URL`).

---

**What this SR command does (summary)**
`make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml`:
- Resolves the **run equivalence key → run_id**.
- Anchors the run and writes **SR run ledger** under the platform run.
- Verifies gates against the **Oracle Store** and builds the **READY bundle**.
- Commits READY and publishes it to the **control bus (Kinesis)** for WSP.

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


