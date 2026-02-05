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
  traffic_output_ids_ref: config/platform/wsp/traffic_outputs_v0.yaml
  context_output_ids_ref: config/platform/wsp/context_fraud_outputs_v0.yaml
  context_output_ids_baseline_ref: config/platform/wsp/context_baseline_outputs_v0.yaml
wiring:
  object_store:
    bucket: fraud-platform
    endpoint: ${OBJECT_STORE_ENDPOINT}
  health_bus_probe_mode: none | describe
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
- `traffic_output_ids_ref` defines the **WSP behavioural traffic allowlist** (engine output_ids eligible to stream).
- v0 traffic is **single‑mode per run** (baseline or fraud). Default is **fraud** (`s3_event_stream_with_fraud_6B`). Use `WSP_TRAFFIC_OUTPUT_IDS_REF` (e.g., `config/platform/wsp/traffic_outputs_baseline_v0.yaml`) to switch to baseline.
- `context_output_ids_ref` defines **behavioural_context allowlist** (join surfaces streamed as separate EB topics).
- `context_output_ids_baseline_ref` is used automatically when the traffic list is baseline; otherwise fraud context is used.
- `arrival_events_5B` and `s1_arrival_entities_6B` are streamed as **context topics**, not as traffic.
- Wiring endpoints are placeholders; actual values come from env/secret store.
- `${VAR}` placeholders are resolved from environment variables at load time.
- `control_bus` wiring is used by the WSP control plane (SR → WSP); IG ignores it in streaming-only v0.
- `health_bus_probe_mode` controls IG bus health probing (`none` leaves `BUS_HEALTH_UNKNOWN`, `describe` uses bus metadata calls).
- Parity profiles use **Kinesis** control bus with `stream/region/endpoint_url` set (LocalStack locally, AWS in dev/prod).
- Local parity Kinesis streams (v0): `sr-control-bus` (control), `fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1` (traffic), `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.baseline.v1`, `fp.bus.context.flow_anchor.fraud.v1` (context), `fp.bus.audit.v1` (audit).
- `oracle_root` points to the sealed engine world store (Oracle Store); it is wiring, not policy.
- `oracle_engine_run_root` optionally pins WSP to a specific engine world (no “latest” scanning).
- `oracle_scenario_id` can be used when a world contains multiple scenarios (avoid ambiguity).
- `oracle_stream_view_root` points to the **stream view base** (`.../stream_view/ts_utc`). WSP appends `output_id=<output_id>` and reads `part-*.parquet`.
- `wsp_checkpoint` controls WSP resume state (file backend for local smoke; Postgres for parity/dev/prod).
- `flush_every` defines how often WSP persists its cursor (lower = fewer duplicates after crash).
- `wsp_producer` pins the producer identity stamped on envelopes; allowlist restricts valid producer_ids.
- `ig_ingest_url` is the WSP → IG push endpoint (non‑secret; can be local or service DNS).
- For dual‑stream traffic, Kinesis publishes to **topic‑named streams** (`fp.bus.traffic.baseline.v1`, `fp.bus.traffic.fraud.v1`). Set `EVENT_BUS_STREAM=auto` (or `topic`) so IG uses the topic name as the stream.
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
