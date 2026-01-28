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
profile_id: <local|dev|prod>
policy:
  policy_rev: <version tag>
  partitioning_profiles_ref: config/platform/ig/partitioning_profiles_v0.yaml
  partitioning_profile_id: <ig partition strategy id>
  require_gate_pass: true
  stream_speedup: 1.0
wiring:
  object_store:
    bucket: fraud-platform
    endpoint: ${OBJECT_STORE_ENDPOINT}
  oracle_root: runs/local_full_run-5
  ig_ingest_url: http://localhost:8081
  event_bus:
    topic_traffic: fp.bus.traffic.v1
    topic_control: fp.bus.control.v1
    topic_audit: fp.bus.audit.v1
  control_bus:
    kind: file
    root: runs/fraud-platform/control_bus
    topic: fp.bus.control.v1
  ready_lease:
    backend: none | postgres
    dsn: ${IG_READY_LEASE_DSN}
    namespace: ig_ready
    owner_id: ${IG_INSTANCE_ID}
  pull_sharding:
    mode: output_id | locator_range
    shard_size: 0
  pull_time_budget_seconds: 0
  security:
    auth_mode: disabled | api_key
    api_key_header: X-IG-Api-Key
    auth_allowlist_ref: path/to/allowlist.txt
    ready_allowlist_run_ids: [run_id_1, run_id_2]
    ready_allowlist_ref: path/to/ready_allowlist.txt
    push_rate_limit_per_minute: 0
    ready_rate_limit_per_minute: 0
    store_read_failure_threshold: 3
    store_read_retry_attempts: 3
    store_read_retry_backoff_seconds: 0.2
    store_read_retry_max_seconds: 2.0
```

Notes:
- `policy_rev` must be stamped into receipts/decisions/outcomes where applicable.
- `partitioning_profile_id` is chosen by IG policy (mapped by stream class); EB never infers partitioning.
- `partitioning_profiles_ref` anchors the versioned profile set used by IG.
- Wiring endpoints are placeholders; actual values come from env/secret store.
- `${VAR}` placeholders are resolved from environment variables at load time.
- `control_bus` wiring tells IG where to read SR READY control events (file bus in v0).
- `oracle_root` points to the sealed engine world store (Oracle Store); it is wiring, not policy.
- `ig_ingest_url` is the WSP → IG push endpoint (non‑secret; can be local or service DNS).
- Local file runs use `object_store.root: runs` so platform artifacts resolve under `runs/fraud-platform/`.
- `security` is wiring‑scoped: it can enable auth and rate limits without changing policy behavior.
- Auth applies to **ingest and ops endpoints** when enabled; only CLI/internal calls bypass it.
- `ready_lease` enables **distributed READY** consumption. Postgres advisory locks are recommended for multi‑instance deployments.
- `pull_sharding` defaults to `output_id` for v0; `locator_range` is opt‑in for large outputs.
- `pull_time_budget_seconds` is optional and intended for **local smoke runs**; leave unset for production.
- `stream_speedup` is a **policy knob** that affects pacing only (same semantics across envs).

Testing policy (current):
- **local.yaml** → smoke validation only (bounded with `pull_time_budget_seconds`).
- **dev_local.yaml** → completion runs (uncapped; uses local filesystem).
- **dev.yaml** → reserved for true dev infra (S3/RDS/etc.) when available.
