# Platform Parity Walkthrough (v0) — Oracle Store → SR → WSP → IG → EB → IEG/OFP/CSFB/DF/DL/AL/DLA/CaseTrigger/CM/LS + Platform Reporter/Conformance
_As of 2026-02-10_

This runbook executes a **local_parity** end‑to‑end flow capped to **500,000 events**, then validates the implemented RTDL + Case/Label + Obs/Gov surfaces (**IEG/OFP/CSFB/DF/DL/AL/DLA/CaseTrigger/CM/LS + Platform Reporter/Conformance**) against admitted EB topics.
It uses **MinIO (S3)** for the Oracle Store + platform artifacts, **LocalStack Kinesis** for control/event buses, and **Postgres** for IG/WSP state.

---

## 0) Preconditions

**Required local stack (parity):**
- MinIO (S3‑compatible) for `oracle-store` and `fraud-platform` buckets
- LocalStack Kinesis (context + traffic + audit):
  - Control: `sr-control-bus`
  - Traffic: `fp.bus.traffic.fraud.v1` (baseline optional)
  - RTDL lane: `fp.bus.rtdl.v1`
  - Case lane: `fp.bus.case.v1`
  - Context: `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.baseline.v1`, `fp.bus.context.flow_anchor.fraud.v1`
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
- Streams exist: `sr-control-bus`, `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.baseline.v1`, `fp.bus.context.flow_anchor.fraud.v1`, `fp.bus.rtdl.v1`, `fp.bus.case.v1`, `fp.bus.audit.v1`.

**What bootstrap does:**
- Creates the **Kinesis streams** in LocalStack (`sr-control-bus`, `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.baseline.v1`, `fp.bus.context.flow_anchor.fraud.v1`, `fp.bus.rtdl.v1`, `fp.bus.case.v1`, `fp.bus.audit.v1`).
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
PARITY_IEG_PROJECTION_DSN=<postgres_dsn>
PARITY_OFP_PROJECTION_DSN=<postgres_dsn>
PARITY_OFP_SNAPSHOT_INDEX_DSN=<postgres_dsn>
PARITY_CSFB_PROJECTION_DSN=<postgres_dsn>

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

## 3.1) Run/Operate orchestration (meta-layer lifecycle contract)

Use the platform orchestrator for always-on packs instead of terminal-by-terminal startup:

```
make platform-operate-control-ingress-up
make platform-operate-rtdl-core-up
make platform-operate-rtdl-decision-up
make platform-operate-case-labels-up
make platform-operate-obs-gov-up
make platform-operate-parity-status
```

Equivalent shorthand:
```
make platform-operate-parity-up
```

Shutdown/restart:

```
make platform-operate-parity-down
make platform-operate-parity-restart
```

Pack and evidence surfaces:
- Packs:
  - `config/platform/run_operate/packs/local_parity_control_ingress.v0.yaml`
  - `config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml`
  - `config/platform/run_operate/packs/local_parity_rtdl_decision_lane.v0.yaml`
  - `config/platform/run_operate/packs/local_parity_case_labels.v0.yaml`
  - `config/platform/run_operate/packs/local_parity_obs_gov.v0.yaml`
- Orchestrator state/logs:
  - `runs/fraud-platform/operate/<pack_id>/state.json`
  - `runs/fraud-platform/operate/<pack_id>/events.jsonl`
  - `runs/fraud-platform/operate/<pack_id>/status/last_status.json`
  - `runs/fraud-platform/operate/<pack_id>/logs/<process>.log`

Notes:
- RTDL core pack enforces active run scope via `ACTIVE_RUN_ID` -> `*_REQUIRED_PLATFORM_RUN_ID`.
- RTDL decision-lane pack enforces active run scope for `DL/DF/AL/DLA` with the same run pin.
- Case/Label pack enforces active run scope for `CaseTrigger/CM/LS` with the same run pin.
- Obs/Gov pack enforces active run scope for `platform_run_reporter/platform_conformance` with the same run pin.
- Orchestrator contract is plane-agnostic; future planes onboard by adding new process-pack files, not by changing orchestrator code.
- Mode boundary:
  - If packs are running, treat them as source-of-truth daemons and avoid launching duplicate manual consumers for the same component.
  - Use manual component commands only for targeted diagnosis or matrix/boundary checks.

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
- Builds **one sorted dataset per output_id** (traffic + context, based on output list) under:
  `.../stream_view/ts_utc/output_id=<output_id>/part-*.parquet`
- Sorts **within each output** by `ts_utc` with tie‑breakers `filename` + `file_row_number`.
- Writes `_stream_view_manifest.json` + `_stream_sort_receipt.json` for **each output**.
- Is **idempotent** per output: if a valid receipt exists, it skips; if it conflicts, it fails.
- Uses `config/platform/wsp/traffic_outputs_v0.yaml` as the default **traffic** output_id list unless overridden.
  - **Note:** default (single‑pass) writes a **single** `part-000000.parquet` per output.
    Set `STREAM_SORT_CHUNK_DAYS=1` (or higher) to produce **multiple** ordered parts.

**Run one output at a time (separate terminals if you want progress per dataset):**
```
make platform-oracle-stream-sort `
  ORACLE_PROFILE=config/platform/profiles/local_parity.yaml `
  ORACLE_ENGINE_RUN_ROOT=$env:ORACLE_ENGINE_RUN_ROOT `
  ORACLE_SCENARIO_ID=$env:ORACLE_SCENARIO_ID `
  ORACLE_STREAM_OUTPUT_ID=s3_event_stream_with_fraud_6B
```
For large outputs, consider `STREAM_SORT_CHUNK_DAYS=1` if memory spikes.

**Dependency note:** this step uses `duckdb` (declared in `pyproject.toml`). If missing, install deps before running.

`ORACLE_STREAM_VIEW_ROOT` should point to the **base** (`.../stream_view/ts_utc`); **WSP reads**:
`<ORACLE_STREAM_VIEW_ROOT>/output_id=<output_id>/part-*.parquet`.
If you need a fresh view, delete the prior output_id view or set a new base path.
**If you see `STREAM_VIEW_PARTIAL_EXISTS`:** a prior sort left partial parquet files. Delete the output_id stream view prefix and re‑run Section 4.3.
**Important:** the stream view ID is derived from `ORACLE_ENGINE_RUN_ROOT` + `ORACLE_SCENARIO_ID` + `output_id`. Ensure `ORACLE_ENGINE_RUN_ROOT` matches the MinIO path you sorted (s3://...), not the local `runs/...` path.

**Traffic stream selection (single‑stream default, dual available):**
- Default traffic output list lives in `config/platform/wsp/traffic_outputs_v0.yaml` (now **fraud only**).
- **Override at runtime** (no file edits):
  - `WSP_TRAFFIC_OUTPUT_IDS="s3_event_stream_with_fraud_6B"` (or baseline)
  - `WSP_TRAFFIC_OUTPUT_IDS_REF="config/platform/wsp/traffic_outputs_v0.yaml"`
  - `WSP_TRAFFIC_OUTPUT_IDS_REF="config/platform/wsp/traffic_outputs_baseline_v0.yaml"`
- For a new engine dataset, **sort both baseline + fraud streams** so you can switch later without re‑sorting:
  - `make platform-oracle-stream-sort-traffic-both ORACLE_PROFILE=... ORACLE_ENGINE_RUN_ROOT=... ORACLE_SCENARIO_ID=...`

**Context stream sorting (single‑mode per run):**
- Default **fraud** context list:
  - `config/platform/wsp/context_fraud_outputs_v0.yaml`
  - Target outputs: `arrival_events_5B`, `s1_arrival_entities_6B`, `s3_flow_anchor_with_fraud_6B`
- **Baseline** context list (only when running baseline mode):
  - `config/platform/wsp/context_baseline_outputs_v0.yaml`
  - Target outputs: `arrival_events_5B`, `s1_arrival_entities_6B`, `s2_flow_anchor_baseline_6B`
- Run the appropriate stream‑sort target before a run:
  - `make platform-oracle-stream-sort-context-fraud ORACLE_PROFILE=... ORACLE_ENGINE_RUN_ROOT=... ORACLE_SCENARIO_ID=...`
  - `make platform-oracle-stream-sort-context-baseline ORACLE_PROFILE=... ORACLE_ENGINE_RUN_ROOT=... ORACLE_SCENARIO_ID=...`

**Resource guardrails (recommended):**
- This step can be **CPU + disk heavy**. If you are on a laptop, set limits before running:
  - `STREAM_SORT_MEMORY_LIMIT="8GB"` (or lower if you see OOM)
  - `STREAM_SORT_MAX_TEMP_SIZE="50GiB"` (or a safe value for your free disk)
  - `STREAM_SORT_THREADS="4"` (fewer threads = lower memory pressure)
  - `STREAM_SORT_TEMP_DIR="temp/duckdb"` (keeps temp inside the repo)
  - For very large outputs (e.g., `arrival_events_5B`), prefer `STREAM_SORT_THREADS="2"` and `STREAM_SORT_MEMORY_LIMIT="16GB"` if you have enough RAM.
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

**If decision-lane publish fails with `ResourceNotFoundException` for `fp.bus.rtdl.v1`:**

```powershell
aws --endpoint-url http://localhost:4566 kinesis create-stream --stream-name fp.bus.rtdl.v1 --shard-count 1
```

**If case-lane publish fails with `ResourceNotFoundException` for `fp.bus.case.v1`:**

```powershell
aws --endpoint-url http://localhost:4566 kinesis create-stream --stream-name fp.bus.case.v1 --shard-count 1
```

---

## 6) SR publishes READY (control bus)

```
$env:SR_RUN_EQUIVALENCE_KEY="parity_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
make platform-sr-run-reuse SR_WIRING=config/platform/sr/wiring_local_kinesis.yaml
```

`platform-sr-run-reuse` pins `PLATFORM_RUN_ID` from `runs/fraud-platform/ACTIVE_RUN_ID` for this invocation so SR emits READY for the current active platform run.

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

## 7) WSP consumes READY and streams events (traffic + context)

**Traffic policy (single‑mode):** WSP emits **one traffic stream per run** (baseline **or** fraud; default is fraud).  
Traffic outputs are **not interleaved** across modes; only the selected stream is produced.

```
$env:WSP_READY_MAX_EVENTS="500000"; make platform-wsp-ready-consumer-once WSP_PROFILE=config/platform/profiles/local_parity.yaml
```

If `control_ingress` pack is already up (`make platform-operate-control-ingress-up`), do not run this command in parallel; the pack already runs WSP ready-consumer.

**Expected:**
- WSP reads READY from Kinesis
- WSP streams to IG from the **stream view** (per‑output `ts_utc` order; speedup preserves ordering)
- IG admits and publishes to EB (Kinesis)

**Concurrency + caps (important):**
- WSP streams **multiple outputs concurrently** when more than one output exists (default).
- `WSP_READY_MAX_EVENTS` is treated **per output** in concurrent mode.
- If you want an explicit per‑output cap, set `WSP_MAX_EVENTS_PER_OUTPUT` (example below).

Example: 200 events **per output** (traffic):
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
- EB publisher diagnostics: `runs/fraud-platform/<platform_run_id>/event_bus/event_bus.log` (emitted by components that call EB publisher)
- Run/operate diagnostics: `runs/fraud-platform/operate/<pack_id>/logs/<process>.log`

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

**Quick IG check (traffic + context receipts):**
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
Inspect `fp.bus.rtdl.v1` to confirm decision-lane events (`decision_response`, `action_intent`, `action_outcome`) are routed off the traffic stream.

**Quick traffic channel check (baseline/fraud):**
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

**Context stream check (arrival + flow anchor):**
```
$arrival = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp.bus.context.arrival_events.v1 `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

$anchor = (aws --endpoint-url http://localhost:4566 kinesis get-shard-iterator `
  --stream-name fp.bus.context.flow_anchor.fraud.v1 `
  --shard-id shardId-000000000000 `
  --shard-iterator-type TRIM_HORIZON | ConvertFrom-Json).ShardIterator

aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $arrival --limit 5
aws --endpoint-url http://localhost:4566 kinesis get-records --shard-iterator $anchor --limit 5
```

**Expected:** payloads are canonical envelopes (base64 in Kinesis).

---

## 11) Run IEG (projector + artifacts)

If you are **not** running the `rtdl_core` pack, IEG is not auto-started in parity and must be run explicitly after EB has admitted events.

**11.1 Set run scope (recommended)**
```
$env:PLATFORM_RUN_ID = (Get-Content runs/fraud-platform/ACTIVE_RUN_ID).Trim()
$env:IEG_REQUIRED_PLATFORM_RUN_ID = $env:PLATFORM_RUN_ID
$env:IEG_PROJECTION_DSN = $env:PARITY_IEG_PROJECTION_DSN
```

**11.2 Run the projector (Kinesis EB)**
```
.venv/Scripts/python.exe -m fraud_detection.identity_entity_graph.projector `
  --profile config/platform/profiles/local_parity.yaml --once
```

If you want the projector to keep polling:
```
.venv/Scripts/python.exe -m fraud_detection.identity_entity_graph.projector `
  --profile config/platform/profiles/local_parity.yaml
```

**11.2a Live parity mode (run_forever)**
Use this when you want the projector to behave like dev/prod (always-on). Keep it in a separate terminal.

Recommended scope locks (so it only consumes the active run):
```
$env:PLATFORM_RUN_ID = (Get-Content runs/fraud-platform/ACTIVE_RUN_ID).Trim()
$env:IEG_REQUIRED_PLATFORM_RUN_ID = $env:PLATFORM_RUN_ID
$env:IEG_LOCK_RUN_SCOPE = "true"
```

Start the projector in live mode:
```
.venv/Scripts/python.exe -m fraud_detection.identity_entity_graph.projector `
  --profile config/platform/profiles/local_parity.yaml
```

Stop it explicitly when the run is finished.

**11.3 Expected artifacts (run-scoped)**
- Projection store:
  - local_parity default: Postgres (`$env:PARITY_IEG_PROJECTION_DSN`)
  - optional local override: run-scoped SQLite path
- Health: `runs/fraud-platform/<platform_run_id>/identity_entity_graph/health/last_health.json`
- Metrics: `runs/fraud-platform/<platform_run_id>/identity_entity_graph/metrics/last_metrics.json`
- Reconciliation: `runs/fraud-platform/<platform_run_id>/identity_entity_graph/reconciliation/reconciliation.json`

Quick check:
```
Get-Content runs/fraud-platform/<platform_run_id>/identity_entity_graph/reconciliation/reconciliation.json
```

**11.4 (Optional) Write replay manifest (EB basis)**
```
.venv/Scripts/python.exe -m fraud_detection.identity_entity_graph.replay_manifest_writer `
  --profile config/platform/profiles/local_parity.yaml
```
This writes:
`runs/fraud-platform/<platform_run_id>/identity_entity_graph/replay/replay_manifest.json`

---

## 12) (Optional) Start IEG query service

```
.venv/Scripts/python.exe -m fraud_detection.identity_entity_graph.service `
  --profile config/platform/profiles/local_parity.yaml --port 8091
```

**Status check** (requires `scenario_run_id`):
1) List SR run_facts_view objects:
```
aws --endpoint-url http://localhost:9000 s3 ls s3://fraud-platform/<platform_run_id>/sr/run_facts_view/
```
2) Use the filename (minus `.json`) as `scenario_run_id`:
```
Invoke-RestMethod "http://127.0.0.1:8091/v1/ops/status?scenario_run_id=<scenario_run_id>"
```

---

## 13) Shutdown (optional)
```
make platform-parity-stack-down
```

---

## What “green” looks like
- SR emits READY with facts_view + oracle_pack_ref.
- WSP streams and records READY processing under `wsp/ready_runs`.
- IG admits events and writes receipts under `ig/receipts`.
- EB offsets advance and are visible in receipt `eb_ref`.
- IEG projector creates projection DB + reconciliation artifact under `identity_entity_graph/`.
- Platform log shows SR → WSP → IG → EB in order for the same run id.

---

## 14) v0 green checklist (control & ingress + IEG)

Use this list to confirm the **v0 control & ingress plane** is green.

**Run-scoped artifacts**
- [ ] `runs/fraud-platform/ACTIVE_RUN_ID` points to the latest run.
- [ ] SR artifacts exist under `s3://fraud-platform/<run_id>/sr/` (status/record/facts).
- [ ] WSP ready logs exist under `runs/fraud-platform/<run_id>/world_streamer_producer/world_streamer_producer.log`.
- [ ] IG receipts exist under `s3://fraud-platform/<run_id>/ig/receipts/`.
- [ ] IEG projection store is reachable (local_parity default DSN: `PARITY_IEG_PROJECTION_DSN`).
- [ ] IEG reconciliation artifact exists under `runs/fraud-platform/<run_id>/identity_entity_graph/reconciliation/reconciliation.json`.

**Narrative platform log**
- [ ] `platform.log` includes `SR READY published` for the same run id.
- [ ] `platform.log` includes `WSP stream start` and `WSP stream stop` for that run.
- [ ] `platform.log` includes IG summary lines (admit/duplicate/quarantine) after traffic.

**Event bus offsets**
- [ ] LocalStack streams `fp.bus.traffic.baseline.v1` / `fp.bus.traffic.fraud.v1` return records (traffic).
- [ ] LocalStack stream `fp.bus.rtdl.v1` returns records (decision lane).
- [ ] LocalStack stream `fp.bus.case.v1` returns records (case trigger lane).
- [ ] LocalStack streams `fp.bus.context.arrival_events.v1` / `fp.bus.context.flow_anchor.fraud.v1` return records (context).
- [ ] IG receipts include `eb_ref` with `offset_kind=kinesis_sequence`.

**Health posture**
- [ ] IG health is AMBER before traffic (OK).
- [ ] After traffic, IG health moves toward GREEN or shows admissions in logs.

---

## 14.1) Meta-layer closure checks (run/operate + obs/gov)

Run these after each parity stream pass (`20` gate and `200` full):

```powershell
make platform-run-report
make platform-governance-query GOVERNANCE_QUERY_LIMIT=20
make platform-env-conformance
```

If `platform-operate-obs-gov-up` is active, these artifacts are emitted continuously.
Do not run manual `make platform-run-report` concurrently with the reporter worker (can race and produce governance `S3_APPEND_CONFLICT` on append).
Use manual commands as explicit spot-check re-runs only when the obs/gov pack is stopped.

Expected artifacts:
- Platform run report: `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`
- Governance log (object store): `s3://fraud-platform/<platform_run_id>/obs/governance/events.jsonl`
- Environment conformance: `runs/fraud-platform/<platform_run_id>/obs/environment_conformance.json`

Use this as the operator closeout:
- Verify ingress counters and RTDL counters are internally consistent for the active run.
- Verify governance stream includes `RUN_REPORT_GENERATED` and evidence-resolution events.
- Verify conformance gate reports pass for active profile expectations before moving to the next plane.

`4.6.L` strict closeout additions (required for Phase 4.6 PASS):
- Verify `IEG` and `DL` both publish run-scoped observability files for the active run:
  - `runs/fraud-platform/<platform_run_id>/identity_entity_graph/metrics/last_metrics.json`
  - `runs/fraud-platform/<platform_run_id>/identity_entity_graph/health/last_health.json`
  - `runs/fraud-platform/<platform_run_id>/degrade_ladder/metrics/last_metrics.json`
  - `runs/fraud-platform/<platform_run_id>/degrade_ladder/health/last_health.json`
- Apply bounded local-parity watermark-age rule:
  - treat `WATERMARK_TOO_OLD` as gate-failing only while ingress is actively progressing for the run,
  - after bounded-run stream idle/teardown, stale watermark is informational for local parity and must be recorded in implementation notes.
- Apply bounded local-parity DF fail-closed acceptance rule:
  - acceptable only when posture is deterministic and explainable from compatibility reasons (`ACTIVE_BUNDLE_INCOMPATIBLE`, `FAIL_CLOSED_NO_COMPATIBLE_BUNDLE`, `REGISTRY_FAIL_CLOSED`, etc.),
  - must include explicit env-ladder remediation note: dev/prod promotion requires compatible ACTIVE bundle + feature-group contract, not continued fail-closed operation.

---

## 15) OFP/OFS local-parity boundary checks (projector + snapshot + observability)

Use this section when you want to validate OFP directly from admitted EB traffic for the active run.
Naming note: in this repo the component is `OFP` (`online_feature_plane`); if you use `OFS` as shorthand, this is the same section.

**15.1 Pin run scope**
```powershell
$run = (Get-Content runs/fraud-platform/ACTIVE_RUN_ID -Raw).Trim()
$run = ($run -replace '[^A-Za-z0-9_:-]','')
$env:PLATFORM_RUN_ID = $run
$env:OFP_REQUIRED_PLATFORM_RUN_ID = $run
$env:OFP_PROJECTION_DSN = $env:PARITY_OFP_PROJECTION_DSN
$env:OFP_SNAPSHOT_INDEX_DSN = $env:PARITY_OFP_SNAPSHOT_INDEX_DSN
$env:PLATFORM_STORE_ROOT = 'runs/fraud-platform'
```

**15.2 Run OFP projector once**
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.projector `
  --profile config/platform/profiles/local_parity.yaml `
  --once
```

**15.3 Discover `scenario_run_id` in OFP state**
```powershell
@'
import os
from pathlib import Path
import psycopg
run_id = Path("runs/fraud-platform/ACTIVE_RUN_ID").read_text(encoding="utf-8").strip()
dsn = os.environ.get("OFP_PROJECTION_DSN") or os.environ.get("PARITY_OFP_PROJECTION_DSN")
if not dsn:
    raise SystemExit("OFP_PROJECTION_DSN is required")
stream_id = f"ofp.v0::{run_id}"
with psycopg.connect(dsn) as conn:
    rows = conn.execute(
        "select distinct scenario_run_id from ofp_feature_state where stream_id=%s order by scenario_run_id",
        (stream_id,),
    ).fetchall()
for row in rows:
    print(row[0])
'@ | .venv\Scripts\python.exe -
```

**15.4 Materialize OFP snapshot**
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.snapshotter `
  --profile config/platform/profiles/local_parity.yaml `
  --platform-run-id $env:PLATFORM_RUN_ID `
  --scenario-run-id <SCENARIO_RUN_ID>
```

Expected snapshot path shape:
- `runs/fraud-platform/<platform_run_id>/online_feature_plane/snapshots/<scenario_run_id>/<snapshot_hash>.json`

**15.5 Export OFP observability**
```powershell
.venv\Scripts\python.exe -m fraud_detection.online_feature_plane.observe `
  --profile config/platform/profiles/local_parity.yaml `
  --scenario-run-id <SCENARIO_RUN_ID>
```

Expected outputs:
- `runs/fraud-platform/<platform_run_id>/online_feature_plane/metrics/last_metrics.json`
- `runs/fraud-platform/<platform_run_id>/online_feature_plane/health/last_health.json`

**15.6 Required counters to inspect**
- `snapshots_built`
- `snapshot_failures`
- `events_applied`
- `duplicates`
- `stale_graph_version`
- `missing_features`

Boundary note:
This validates OFP at its current component boundary (projection, snapshot, observability). Use Sections `16` and `17` for DL and DF boundary checks available today.
In parity, DF/AL/DLA decision-lane families publish on `fp.bus.rtdl.v1`; OFP continues to ignore RTDL families and only mutates state from admitted traffic/context families.

---

## 16) DL local-parity boundary checks (policy, posture, governance)

Use this section to validate Degrade Ladder behavior in local-parity with the current implementation surface.

**16.1 Validate DL policy profile load**
```powershell
@'
from pathlib import Path
from fraud_detection.degrade_ladder.config import load_policy_bundle

bundle = load_policy_bundle(Path("config/platform/dl/policy_profiles_v0.yaml"))
profile = bundle.profile("local_parity")
print("policy_rev:", bundle.policy_rev.policy_id, bundle.policy_rev.revision)
print("profile_id:", profile.profile_id)
print("mode_sequence:", ",".join(profile.mode_sequence))
'@ | .venv\Scripts\python.exe -
```

**16.2 Run DL component validation suite**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/degrade_ladder -q
```

Expected result:
- all tests pass (`40 passed` on current baseline).

Boundary note:
DL validates through its contract/store/serve/emission/governance surfaces and tests, and now also has a standalone daemon worker (`fraud_detection.degrade_ladder.worker`) for run/operate parity.

---

## 17) DF local-parity boundary checks (identity, inlet, synthesis, replay)

Use this section to validate Decision Fabric boundary behavior with the current implementation surface.

**17.1 Run DF component validation suite**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/decision_fabric -q
```

Expected result:
- all tests pass (`69 passed` on current baseline).

**17.2 Optional targeted drift-closure smoke**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest `
  tests/services/decision_fabric/test_phase1_ids.py `
  tests/services/decision_fabric/test_phase2_inlet.py `
  tests/services/decision_fabric/test_phase3_posture.py `
  tests/services/decision_fabric/test_phase6_synthesis.py -q
```

What this confirms:
- deterministic `decision_id` identity anchored to source `origin_offset`,
- inlet tuple + payload-hash collision discipline,
- deterministic scope-key normalization at DF<->DL posture boundary,
- deterministic synthesis output for fixed basis.

Boundary note:
DF validates through component contracts/tests and IG publish boundary logic, and now also has a standalone daemon worker (`fraud_detection.decision_fabric.worker`) for run/operate parity.


## 18) Context Store + FlowBinding local-parity checks (join plane intake + query)

Use this section to validate the shared RTDL join plane (`context_store_flow_binding`) for the active platform run.

**18.1 Pin run scope**
```powershell
$run = (Get-Content runs/fraud-platform/ACTIVE_RUN_ID -Raw).Trim()
$run = ($run -replace '[^A-Za-z0-9_:-]','')
$env:PLATFORM_RUN_ID = $run
$env:CSFB_REQUIRED_PLATFORM_RUN_ID = $run
$env:CSFB_PROJECTION_DSN = $env:PARITY_CSFB_PROJECTION_DSN
```

**18.2 Run CSFB intake once (parity profile)**
```powershell
make platform-context-store-flow-binding-parity-once
```

Live mode (continuous consume):
```powershell
make platform-context-store-flow-binding-parity-live
```

**18.3 Monitored 20-event pass**
1. Run SR -> WSP 20-event parity flow first (Sections 6-7 with `WSP_MAX_EVENTS_PER_OUTPUT=20`).
2. Run `make platform-context-store-flow-binding-parity-once`.
3. Inspect CSFB metrics/reconciliation:
```powershell
@'
import json
from pathlib import Path
from fraud_detection.context_store_flow_binding import CsfbInletPolicy, CsfbObservabilityReporter

run_id = Path("runs/fraud-platform/ACTIVE_RUN_ID").read_text(encoding="utf-8").strip()
profile = "config/platform/profiles/local_parity.yaml"
policy = CsfbInletPolicy.load(Path(profile))
reporter = CsfbObservabilityReporter.build(locator=policy.projection_db_dsn, stream_id=policy.stream_id)
payload = reporter.collect(platform_run_id=run_id, scenario_run_id=None)
print(json.dumps({
    "platform_run_id": run_id,
    "join_hits": payload["metrics"]["join_hits"],
    "join_misses": payload["metrics"]["join_misses"],
    "apply_failures": payload["metrics"]["apply_failures"],
    "lag_seconds": payload["lag_seconds"],
    "health_state": payload["health_state"],
}, indent=2, sort_keys=True))
'@ | .venv\Scripts\python.exe -
```

**18.4 Monitored 200-event pass**
1. Run SR -> WSP parity flow with `WSP_MAX_EVENTS_PER_OUTPUT=200`.
2. Re-run `make platform-context-store-flow-binding-parity-once`.
3. Re-run the metrics snippet above and compare:
- `join_hits` should increase monotonically with context flow.
- `join_misses`/`apply_failures` should remain bounded and explainable.
- lag/health should remain non-divergent under repeated `--once` polling.

**18.5 Query join readiness (DF/DL contract surface)**
```powershell
@'
from pathlib import Path
from fraud_detection.context_store_flow_binding import ContextStoreFlowBindingQueryService

run_id = Path("runs/fraud-platform/ACTIVE_RUN_ID").read_text(encoding="utf-8").strip()
service = ContextStoreFlowBindingQueryService.build_from_policy("config/platform/profiles/local_parity.yaml")

request = {
    "request_id": "parity-csfb-query-1",
    "query_kind": "resolve_flow_binding",
    "flow_id": "<FLOW_ID_FROM_FLOW_ANCHOR>",
    "pins": {
        "platform_run_id": run_id,
        "scenario_run_id": "<SCENARIO_RUN_ID>",
        "manifest_fingerprint": "<MANIFEST_FINGERPRINT>",
        "parameter_hash": "<PARAMETER_HASH>",
        "scenario_id": "<SCENARIO_ID>",
        "seed": "<SEED>",
        "run_id": "<RUN_ID>",
    },
}

print(service.query(request))
'@ | .venv\Scripts\python.exe -
```

Expected statuses:
- `READY` when flow binding and join frame exist and pins match.
- `MISSING_BINDING` / `MISSING_JOIN_FRAME` when context is not ready.
- `CONFLICT` on pin mismatch (fail-closed).


## 19) AL local-parity boundary checks (DF intent -> outcome publish)

Use this section to validate Action Layer Phase 8 closure at component boundary.

**19.1 Run AL Phase 8 validation matrix**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/action_layer/test_phase8_validation_matrix.py -q
```

Expected result:
- `3 passed` (includes:
  - DF->AL continuity proof,
  - `20` event parity proof,
  - `200` event parity proof + replay/no-duplicate effect proof).

**19.2 Run full AL suite**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/action_layer -q
```

Expected result:
- full AL suite passes (current baseline: `45 passed`).

**19.3 Inspect parity proof artifacts**
```powershell
Get-Content runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_20.json
Get-Content runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_200.json
```

Expected fields:
- `status: PASS`
- `expected_events == observed_outcomes`
- `duplicate_drops == expected_events`
- `effect_execution_calls == expected_events`

Boundary note:
This validates AL at its component boundary for Phase 8. AL is also daemonized for parity via `fraud_detection.action_layer.worker` in the decision-lane run/operate pack.

## 20) DLA local-parity boundary checks (append-only intake + reconciliation)

Use this section to validate Decision Log/Audit Phase 8 closure at component boundary.

**20.1 Run DLA Phase 8 validation matrix**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/decision_log_audit/test_dla_phase8_validation_matrix.py -q
```

Expected result:
- `4 passed` (includes:
  - DF->DLA parity proof (`20` events),
  - AL->DLA parity proof (`20` events),
  - combined DF/AL->DLA parity proof (`200` events) with replay-safe append behavior).

**20.2 Run full DLA suite**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/decision_log_audit -q
```

Expected result:
- full DLA suite passes (current baseline expected green).

**20.3 Inspect parity proof artifacts**
```powershell
Get-Content runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_20.json
Get-Content runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_200.json
```

Expected fields:
- `status: PASS`
- `records_total` matches expected intake volume for the test scenario
- `append_only_violations == 0`
- reconciliation indicates monotonic checkpoint/offset progression

Boundary note:
This validates DLA at its component boundary for Phase 8 (append-only intake, lineage/reconciliation, and parity proofs). DLA is also daemonized for parity via `fraud_detection.decision_log_audit.worker` in the decision-lane run/operate pack.

## 21) CaseTrigger local-parity boundary checks (DF evidence -> trigger corridor -> checkpoint)

Use this section to validate CaseTrigger Phase 8 closure at component boundary.

**21.1 Run CaseTrigger Phase 8 validation matrix**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/case_trigger/test_phase8_validation_matrix.py -q
```

Expected result:
- `4 passed` (includes:
  - DF->CaseTrigger continuity proof,
  - `20` event parity proof,
  - `200` event parity proof with replay/duplicate-safe checkpoint behavior,
  - negative-path fail-closed proof for unsupported source + collision mismatch).

**21.2 Run CaseTrigger + CM integration regression**
```powershell
$env:PYTHONPATH='.;src'
.venv\Scripts\python.exe -m pytest tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py -q
.venv\Scripts\python.exe -m pytest tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py -q
```

Expected result:
- CaseTrigger+IG suite passes (current baseline: `45 passed`).
- CM Phase1+2 suite passes (current baseline: `16 passed`).

**21.3 Inspect CaseTrigger parity proof artifacts**
```powershell
Get-Content runs/fraud-platform/platform_20260209T180000Z/case_trigger/reconciliation/phase8_parity_proof_20.json
Get-Content runs/fraud-platform/platform_20260209T180000Z/case_trigger/reconciliation/phase8_parity_proof_200.json
Get-Content runs/fraud-platform/platform_20260209T180000Z/case_trigger/reconciliation/phase8_negative_path_proof.json
```

Expected fields:
- `status: PASS` on both parity proof artifacts.
- `triggers_seen_total == 2 * expected_events`.
- `published_total == expected_events`.
- `duplicate_total == expected_events`.
- `checkpoint_committed_total == 2 * expected_events`.
- negative-path proof reports:
  - `unsupported_source_fail_closed: true`,
  - `collision_mismatch_outcome: PAYLOAD_MISMATCH`,
  - governance dedupe working with exactly one emitted collision event.

Boundary note:
This validates CaseTrigger at its component boundary for Phase 8 closure. CaseTrigger is now also daemonized in the run/operate Case+Label pack for live parity operation.

## 22) Full live daemon baseline (current v0 daemon surfaces)

Use this when you want always-on parity consumers for the full implemented lane under run/operate (C&I + RTDL + Case/Label).

Bring all packs up:
```powershell
make platform-operate-control-ingress-up
make platform-operate-rtdl-core-up
make platform-operate-rtdl-decision-up
make platform-operate-case-labels-up
make platform-operate-obs-gov-up
make platform-operate-parity-status
```

Shutdown sequence:
```powershell
make platform-operate-obs-gov-down
make platform-operate-case-labels-down
make platform-operate-rtdl-decision-down
make platform-operate-rtdl-core-down
make platform-operate-control-ingress-down
```

Optional manual terminal mode (without run/operate pack) for RTDL core only:
```powershell
make platform-rtdl-core-parity-live
```

Scope note:
- `control_ingress` pack covers `IG + WSP ready_consumer`.
- `rtdl_core` pack covers `IEG/OFP/CSFB`.
- `rtdl_decision_lane` pack covers `DL/DF/AL/DLA`.
- `case_labels` pack covers `CaseTrigger/CM/LS`.
- `obs_gov` pack covers `platform_run_reporter + environment_conformance` daemon workers.
- Component matrices in Sections 16/17/19/20 remain required as deterministic boundary checks; they now complement (not replace) daemonized runtime operation.

### 22.1) Full-stream gate pattern (`20` then `200`)
Use this sequence for platform acceptance:
- run `20` bounded stream first (`WSP_MAX_EVENTS_PER_OUTPUT=20`) and require all-green component health.
- run `200` bounded stream next (`WSP_MAX_EVENTS_PER_OUTPUT=200`) and require all-green component health + throughput closure.
- take matrix snapshots from:
  - `runs/fraud-platform/<platform_run_id>/obs/fullstream_snapshot_20_*.json`
  - `runs/fraud-platform/<platform_run_id>/obs/fullstream_snapshot_200_*.json`
- verify canonical reporter artifact:
  - `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`


