# Platform Parity Walkthrough (v0) — Oracle Store → SR → WSP → IG → EB
_As of 2026-02-01_

This runbook executes a **local_parity** end‑to‑end flow capped to **500,000 events**.
It uses **MinIO (S3)** for the Oracle Store + platform artifacts, **LocalStack Kinesis** for control/event buses, and **Postgres** for IG/WSP state.

---

## 0) Preconditions

**Required local stack (parity):**
- MinIO (S3‑compatible) for `oracle-store` and `fraud-platform` buckets
- LocalStack Kinesis (4 streams total):
  - Control: `sr-control-bus`
  - Traffic (dual‑stream): `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`
  - Audit: `fp.bus.audit.v1`
- Postgres for IG admission DB + WSP checkpoints

**Profiles used:**
- `config/platform/profiles/local_parity.yaml`
- `config/platform/sr/wiring_local_kinesis.yaml`

**Oracle Store assumption:**
The engine outputs exist locally **and are synced into MinIO** (Oracle Store) before sealing. The packer writes
manifest/seal files; it does not copy the dataset unless you sync it.

---

## 0.1) Component vs backend (quick clarity)

In this platform:
- **Component** = logical platform role (contract + behavior).
- **Backend** = concrete infrastructure used to implement that role.

**Examples in v0 parity:**
- **EB (Event Bus)** is a **component**.  
  **Backend:** Kinesis (LocalStack locally, AWS in dev/prod).
- **Oracle Store** is a **component**.  
  **Backend:** S3‑compatible object store (MinIO locally).
- **IG (Ingestion Gate)** is a **service component**.  
  It validates/admits and **calls EB’s publisher** (not a separate EB service).

So when you say “EB,” you’re referring to the **component**, and in parity it **uses Kinesis** as its backend.

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
- Streams exist: `sr-control-bus`, `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`, `fp.bus.audit.v1`.

**What bootstrap does:**
- Creates the **Kinesis streams** in LocalStack (`sr-control-bus`, `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`, `fp.bus.audit.v1`).
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

PARITY_EVENT_BUS_STREAM=auto
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
ORACLE_STREAM_VIEW_ROOT=s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/stream_view/ts_utc
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

## 4) Populate Oracle Store in MinIO (sync + seal + stream view)

This step does **three things**: (1) copy the engine outputs into MinIO, (2) write the Oracle pack manifest + seal,
(3) build **per‑output time‑sorted stream views** WSP will consume.

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

**4.3 Build the stream view (required; per‑output `ts_utc` order, flat output)**
```
make platform-oracle-stream-sort `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT `
  ORACLE_SCENARIO_ID=$env:ORACLE_SCENARIO_ID
```

**What this does:**
- **Why required:** engine outputs are not guaranteed to be globally `ts_utc`‑sorted; WSP consumes a **stream view** that is strictly ordered by `ts_utc`.
- Reads the **engine outputs** from MinIO.
- Builds **one sorted dataset per output_id** (traffic streams only) under:
  `.../stream_view/ts_utc/output_id=<output_id>/part-*.parquet`
- Sorts **within each output** by `ts_utc` with tie‑breakers `filename` + `file_row_number`.
- Writes `_stream_view_manifest.json` + `_stream_sort_receipt.json` for **each output**.
- Is **idempotent** per output: if a valid receipt exists, it skips; if it conflicts, it fails.
- Uses `config/platform/wsp/traffic_outputs_v0.yaml` as the default output_id list unless overridden.
  - **Note:** default (single‑pass) writes a **single** `part-000000.parquet` per output.
    Set `STREAM_SORT_CHUNK_DAYS=1` (or higher) to produce **multiple** ordered parts.

**Behavioural‑context + truth‑product stream views (8 outputs):**
These are **not traffic**, but are required as **join surfaces / labels** in downstream planes.
```
make platform-oracle-stream-sort-context-truth `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT `
  ORACLE_SCENARIO_ID=$env:ORACLE_SCENARIO_ID
```
Output list (default): `config/platform/wsp/context_truth_outputs_v0.yaml`.
**Note (sort keys):** Some context/truth outputs do **not** carry `ts_utc`. In those cases the stream view uses
the best available time/identity key: `s1_session_index_6B → session_start_utc`, `s4_event_labels_6B → flow_id,event_seq`,
`s4_flow_truth_labels_6B → flow_id`, `s4_flow_bank_view_6B → flow_id`. The receipt records the exact `sort_keys`.

**Run one output at a time (separate terminals if you want progress per dataset):**
```
make platform-oracle-stream-sort `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT `
  ORACLE_SCENARIO_ID=$env:ORACLE_SCENARIO_ID `
  ORACLE_STREAM_OUTPUT_ID=s1_session_index_6B
```
`s1_session_index_6B` is a **large single parquet**; consider `STREAM_SORT_CHUNK_DAYS=1` if memory spikes.

**Dependency note:** this step uses `duckdb` (declared in `pyproject.toml`). If missing, install deps before running.

`ORACLE_STREAM_VIEW_ROOT` should point to the **base** (`.../stream_view/ts_utc`); **WSP reads**:
`<ORACLE_STREAM_VIEW_ROOT>/output_id=<output_id>/part-*.parquet`.
If you need a fresh view, delete the prior output_id view or set a new base path.
**If you see `STREAM_VIEW_PARTIAL_EXISTS`:** a prior sort left partial parquet files. Delete the output_id stream view prefix and re‑run Section 4.3.
**Important:** the stream view ID is derived from `ORACLE_ENGINE_RUN_ROOT` + `ORACLE_SCENARIO_ID` + `output_id`. Ensure `ORACLE_ENGINE_RUN_ROOT` matches the MinIO path you sorted (s3://...), not the local `runs/...` path.

**Resource guardrails (recommended):**
- This step can be **CPU + disk heavy**. If you are on a laptop, set limits before running:
  - `STREAM_SORT_MEMORY_LIMIT="8GB"` (or lower if you see OOM)
  - `STREAM_SORT_MAX_TEMP_SIZE="50GiB"` (or a safe value for your free disk)
  - `STREAM_SORT_THREADS="4"` (fewer threads = lower memory pressure)
  - `STREAM_SORT_TEMP_DIR="temp/duckdb"` (keeps temp inside the repo)
- If the run still stalls or the system becomes unstable, **stop the sort** and lower `THREADS` + `MEMORY_LIMIT`.

```
$env:STREAM_SORT_THREADS="8"
$env:STREAM_SORT_MEMORY_LIMIT="8GB"
$env:STREAM_SORT_MAX_TEMP_SIZE="120GiB"
$env:STREAM_SORT_TEMP_DIR="temp\duckdb"
$env:STREAM_SORT_PROGRESS_SECONDS="5"
$env:STREAM_SORT_PRESERVE_ORDER="false"
$env:STREAM_SORT_CHUNK_DAYS="1"
```

**Verify stream view exists (MinIO):**
```
aws --endpoint-url http://localhost:9000 s3 ls `
  $env:ORACLE_STREAM_VIEW_ROOT/output_id=s2_event_stream_baseline_6B/ | Select-Object -First 5

aws --endpoint-url http://localhost:9000 s3 ls `
  $env:ORACLE_STREAM_VIEW_ROOT/output_id=s3_event_stream_with_fraud_6B/ | Select-Object -First 5
```

**Optional tuning knobs (set before running):**
- `STREAM_SORT_PROGRESS_SECONDS` → DuckDB progress bar refresh (seconds).
- `STREAM_SORT_SORT_MULTIPLIER` → ETA estimate multiplier (default 2.0). ETA logs emit only when the progress bar is **not** enabled.
- `STREAM_SORT_MEMORY_LIMIT` / `STREAM_SORT_TEMP_DIR` / `STREAM_SORT_THREADS` → performance tuning.
- `STREAM_SORT_MAX_TEMP_SIZE` → increases DuckDB temp spill allowance (e.g., `50GiB`).
- `STREAM_SORT_PRESERVE_ORDER` → set `false` to reduce memory (safe because query already `ORDER BY`).
- `STREAM_SORT_CHUNK_DAYS` → if you hit OOM on large outputs, set to `1` to sort day‑chunks (still produces `part-*.parquet` in order).

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

**If IG fails with `ResourceNotFoundException` for `fp.bus.audit.v1`:**

Run the parity bootstrap (creates the audit stream):
```
make platform-parity-bootstrap
```
Or create it manually:
```
aws --endpoint-url http://localhost:4566 kinesis create-stream --stream-name fp.bus.audit.v1 --shard-count 1
```

---

## 6) SR publishes READY (control bus)

```
$env:SR_RUN_EQUIVALENCE_KEY="parity_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml
```

**Note (oracle‑first):** SR **always** reads engine outputs from the Oracle Store (S3/MinIO) in parity mode. The wiring profile must set `oracle_engine_run_root` to the MinIO path (e.g. `s3://oracle-store/<engine_run_root>`). When present, SR ignores `SR_ENGINE_RUN_ROOT` from the CLI and uses the oracle root instead.

**Note (credentials):** SR writes run artifacts to MinIO S3 in parity mode. If you see a `403` here, confirm `.env.platform.local` has the MinIO credentials set and re‑run.

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

## 7) WSP consumes READY and streams events (dual‑stream)

**Traffic policy (dual-stream):** WSP emits **two concurrent traffic channels** only: `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B`. These are **not interleaved** in v0 (separate EB streams).

```
$env:WSP_READY_MAX_EVENTS="500000"; make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml
```

**Expected:**
- WSP reads READY from Kinesis
- WSP streams to IG from the **stream view** (per‑output `ts_utc` order; speedup preserves ordering)
- IG admits and publishes to EB (Kinesis)

**Concurrency + caps (important):**
- WSP streams **both outputs concurrently** when multiple traffic outputs exist (default).
- `WSP_READY_MAX_EVENTS` is treated **per output** in concurrent mode.
- If you want an explicit per‑output cap, set `WSP_MAX_EVENTS_PER_OUTPUT` (example below).

Example: 200 events **per stream** (baseline + fraud):
```
$env:WSP_MAX_EVENTS_PER_OUTPUT="200"
$env:WSP_OUTPUT_CONCURRENCY="2"
$env:WSP_READY_MAX_MESSAGES="1"
make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml
```

**If you see `Invalid endpoint`:** verify `.env.platform.local` has `OBJECT_STORE_ENDPOINT` and MinIO creds; Make exports them to WSP.
**If you see `CONTROL_BUS_STREAM_MISSING`:** ensure `PARITY_CONTROL_BUS_STREAM/REGION/ENDPOINT_URL` are set in `.env.platform.local` (Make exports them as `CONTROL_BUS_*` for WSP).
**If you see `CHECKPOINT_DSN_MISSING`:** ensure `PARITY_WSP_CHECKPOINT_DSN` is set in `.env.platform.local` (Make exports it as `WSP_CHECKPOINT_DSN`).
**If you see `STREAM_VIEW_ID_MISMATCH`:** confirm `.env.platform.local` sets `ORACLE_ENGINE_RUN_ROOT` to the **MinIO** path you used to build the stream view. WSP prefers this explicit oracle root in parity mode.
**If you see `Invalid URL '/v1/ingest/push'`:** ensure `PARITY_IG_INGEST_URL` is set in `.env.platform.local` (Make exports it as `IG_INGEST_URL`).
**If you see `STREAM_VIEW_MISSING`:** re‑run Section 4.3 (`platform-oracle-stream-sort`) or confirm `ORACLE_STREAM_VIEW_ROOT` is set.

**Live progress (WSP):** set these env vars to see periodic progress logs in `platform.log`:
```
$env:WSP_PROGRESS_EVERY="1000"
$env:WSP_PROGRESS_SECONDS="30"
```
You’ll see lines like `WSP progress emitted=...` during the stream.

**If WSP keeps restarting:** the READY control bus replays **all** messages (TRIM_HORIZON). Clear LocalStack streams (restart localstack + re‑bootstrap) or set `WSP_READY_MAX_MESSAGES=1` after you’ve verified the control bus only contains the newest READY.

---

**What this SR command does (summary)**
`make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml`:
- Resolves the **run equivalence key → run_id**.
- Anchors the run and writes **SR run ledger** under the platform run.
- Verifies gates against the **Oracle Store** and builds the **READY bundle**.
- Commits READY and publishes it to the **control bus (Kinesis)** for WSP.

---

## 8) Observe logs (single run, all components)

Tail the platform log (narrative + warnings/errors only):
```
Get-Content runs/fraud-platform/<platform_run_id>/platform.log -Wait
```

  Look for:
  - **SR**: `SR READY published`
  - **WSP**: `WSP stream start` / `WSP stream stop`
  - **IG**: `IG published to EB ...` and `IG summary admit=...`

  Component detail logs (full diagnostics):
  - SR: `runs/fraud-platform/<platform_run_id>/scenario_runner/scenario_runner.log`
  - WSP: `runs/fraud-platform/<platform_run_id>/world_streamer_producer/world_streamer_producer.log`
  - IG: `runs/fraud-platform/<platform_run_id>/ingestion_gate/ingestion_gate.log`
  - EB: `runs/fraud-platform/<platform_run_id>/event_bus/event_bus.log` (publish diagnostics)

**Quick WSP check (baseline + fraud progress):**
```
Select-String -Path runs/fraud-platform/<platform_run_id>/world_streamer_producer/world_streamer_producer.log -Pattern 'output_id=s2_event_stream_baseline_6B|output_id=s3_event_stream_with_fraud_6B' -SimpleMatch | Select-Object -First 5
```

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

**Quick IG check (baseline + fraud receipts):**
```
aws --endpoint-url http://localhost:9000 s3 ls s3://fraud-platform/<platform_run_id>/ig/receipts/ | Select-Object -First 5

# Optional: grep for event_type in recent receipts (requires jq installed)
# aws --endpoint-url http://localhost:9000 s3 cp s3://fraud-platform/<platform_run_id>/ig/receipts/<receipt_id>.json - | jq .event_type
```

---

## 10) Verify EB records (LocalStack Kinesis)

List streams:
```
aws --endpoint-url http://localhost:4566 kinesis list-streams
```

Read a few records:
```
$iterator = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp.bus.traffic.baseline.v1 `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

  aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $iterator --limit 5
  ```

Repeat with `--stream-name fp.bus.traffic.fraud.v1` to inspect the post‑overlay channel.

**Quick dual‑stream check (both channels):**
```
$baseline = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp.bus.traffic.baseline.v1 `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

$fraud = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp.bus.traffic.fraud.v1 `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $baseline --limit 5
aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $fraud --limit 5
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

---

## 12) v0 green checklist (control & ingress)

Use this list to confirm the **v0 control & ingress plane** is green.

**Run-scoped artifacts**
- [ ] `runs/fraud-platform/ACTIVE_RUN_ID` points to the latest run.
- [ ] SR artifacts exist under `s3://fraud-platform/<run_id>/sr/` (status/record/facts).
- [ ] WSP ready logs exist under `runs/fraud-platform/<run_id>/world_streamer_producer/world_streamer_producer.log`.
- [ ] WSP ready logs exist under `runs/fraud-platform/<run_id>/world_streamer_producer/world_streamer_producer.log`.
- [ ] IG receipts exist under `s3://fraud-platform/<run_id>/ig/receipts/`.

**Narrative platform log**
- [ ] `platform.log` includes `SR READY published` for the same run id.
- [ ] `platform.log` includes `WSP stream start` and `WSP stream stop` for that run.
- [ ] `platform.log` includes IG summary lines (admit/duplicate/quarantine) after traffic.

**Event bus offsets**
- [ ] LocalStack streams `fp.bus.traffic.baseline.v1` and `fp.bus.traffic.fraud.v1` return records.
- [ ] IG receipts include `eb_ref` with `offset_kind=kinesis_sequence`.

**Health posture**
- [ ] IG health is AMBER before traffic (OK).
- [ ] After traffic, IG health moves toward GREEN or shows admissions in logs.


