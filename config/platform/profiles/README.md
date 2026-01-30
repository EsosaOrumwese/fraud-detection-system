# Platform Profiles (v0)
_As of 2026-01-24_

Profiles separate **policy config** (outcome-affecting) from **wiring config** (endpoints/resources).
No secrets live in these files. Secrets are injected at runtime via environment/secret store.

## Location
```
config/platform/profiles/
```

## Shape (v0)
```
profile_id: <local|local_parity|dev|prod>
policy:
  policy_rev: <version tag>
  partitioning_profiles_ref: config/platform/ig/partitioning_profiles_v0.yaml
  partitioning_profile_id: <ig partition strategy id>
  require_gate_pass: true
  stream_speedup: 1.0
  stream_mode: engine | stream_view
  traffic_output_ids_ref: config/platform/wsp/traffic_outputs_v0.yaml
wiring:
  object_store:
    bucket: fraud-platform
    endpoint: ${OBJECT_STORE_ENDPOINT}
  oracle_root: runs/local_full_run-5
  oracle_engine_run_root: runs/local_full_run-5/<run_id>
  oracle_scenario_id: baseline_v1
  oracle_stream_view_root: s3://oracle-store/<engine_run_root>/stream_view/ts_utc
  ig_ingest_url: http://localhost:8081
  event_bus:
    root: runs/fraud-platform/<platform_run_id>/eb
    topic_traffic: fp.bus.traffic.v1
    topic_control: fp.bus.control.v1
    topic_audit: fp.bus.audit.v1
  control_bus:
    kind: file | kinesis
    root: runs/fraud-platform/<platform_run_id>/control_bus
    topic: fp.bus.control.v1
    stream: sr-control-bus
    region: us-east-1
    endpoint_url: http://localhost:4566
  wsp_checkpoint:
    backend: file | postgres
    root: runs/fraud-platform/<platform_run_id>/wsp/checkpoints
    dsn: ${WSP_CHECKPOINT_DSN}
    flush_every: 1
  admission_db_path: ${IG_ADMISSION_DSN}
  wsp_producer:
    producer_id: svc:world_stream_producer
    allowlist_ref: config/platform/wsp/producer_allowlist_v0.txt
  security:
    auth_mode: disabled | api_key
    api_key_header: X-IG-Api-Key
    auth_allowlist_ref: path/to/allowlist.txt
    push_rate_limit_per_minute: 0
    store_read_failure_threshold: 3
```

Notes:
- `policy_rev` must be stamped into receipts/decisions/outcomes where applicable.
- `partitioning_profile_id` is chosen by IG policy (mapped by stream class); EB never infers partitioning.
- `partitioning_profiles_ref` anchors the versioned profile set used by IG.
- `traffic_output_ids_ref` defines the **WSP business_traffic allowlist** (engine output_ids eligible to stream).
- `stream_mode` controls WSP source: `engine` (legacy pull) or `stream_view` (global `ts_utc` view).
- Wiring endpoints are placeholders; actual values come from env/secret store.
- `${VAR}` placeholders are resolved from environment variables at load time.
- `control_bus` wiring is used by the WSP control plane (SR → WSP); IG ignores it in streaming-only v0.
- Parity profiles use **Kinesis** control bus with `stream/region/endpoint_url` set (LocalStack locally, AWS in dev/prod).
- `oracle_root` points to the sealed engine world store (Oracle Store); it is wiring, not policy.
- `oracle_engine_run_root` optionally pins WSP to a specific engine world (no “latest” scanning).
- `oracle_scenario_id` can be used when a world contains multiple scenarios (avoid ambiguity).
- `oracle_stream_view_root` points to the **stream view base** (`.../stream_view/ts_utc`). WSP appends the computed stream_view_id.
- `wsp_checkpoint` controls WSP resume state (file backend for local smoke; Postgres for parity/dev/prod).
- `flush_every` defines how often WSP persists its cursor (lower = fewer duplicates after crash).
- `wsp_producer` pins the producer identity stamped on envelopes; allowlist restricts valid producer_ids.
- `ig_ingest_url` is the WSP → IG push endpoint (non‑secret; can be local or service DNS).
- Local file runs use `object_store.root: runs` so platform artifacts resolve under `runs/fraud-platform/<platform_run_id>/`.
- Local parity uses **S3‑compatible** storage (`s3://fraud-platform`) and **Kinesis** for event/control buses.
- `security` is wiring‑scoped: it can enable auth and rate limits without changing policy behavior.
- Auth applies to **ingest and ops endpoints** when enabled; only CLI/internal calls bypass it.
- IG rejects legacy pull wiring keys (`ready_lease`, `pull_sharding`, `pull_time_budget_seconds`, `security.ready_*`) in streaming‑only v0.
- `stream_speedup` is a **policy knob** that affects pacing only (same semantics across envs).

Parity env vars (local_parity/dev/prod):
- `OBJECT_STORE_ENDPOINT`, `OBJECT_STORE_REGION`
- `ORACLE_ROOT`, `ORACLE_ENGINE_RUN_ROOT`, `ORACLE_SCENARIO_ID`
- `ORACLE_STREAM_VIEW_ROOT`
- `IG_ADMISSION_DSN`, `WSP_CHECKPOINT_DSN`
- `EVENT_BUS_STREAM`
- `CONTROL_BUS_STREAM`, `CONTROL_BUS_REGION`, `CONTROL_BUS_ENDPOINT_URL`

Testing policy (current):
- **local.yaml** → fast smoke validation (file‑bus + SQLite).
- **local_parity.yaml** → parity validation (MinIO + LocalStack + Postgres).
- **local_parity.yaml** → parity validation (MinIO + LocalStack + Postgres).
- **dev.yaml** → dev infra (S3/Kinesis/RDS).
