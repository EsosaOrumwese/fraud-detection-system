# Storage Layout v1.0 (Engine-wide)

This note defines the canonical storage layout for the data-engine contracts. It is authoritative for dictionaries, registries, and state-flow path references.

## 1) Roots (single purpose)

- `reference/` — curated, versioned reference tables (read-only).
- `artefacts/` — heavy/bundled assets (read-only; sealed by digest).
- `config/` — policies/config packs (read-only; YAML/JSON only).
- `data/` — deterministic outputs, receipts, validation bundles.
- `logs/` — operational logs (RNG, audit, selection, edge).
- `reports/` — run reports and ops telemetry.

No other top-level roots are used (e.g., `control/` is folded into `reports/`).

## 2) Run isolation

- Engine writes only to `data/`, `logs/`, `reports/`.
- Engine may read only from `reference/`, `artefacts/`, `config/`, and upstream `data/` outputs that are sealed in `sealed_inputs_*`.
- Large pinned assets (e.g., HRSL, Pelias, tzdata) are read in place and sealed by digest; they are not copied per run.

## 3) Config layout (layer + segment scoped)

Segment-scoped config MUST live under a layer + segment prefix:

```
config/layer1/{SEG}/{domain}/<files>
config/layer2/{SEG}/{domain}/<files>
config/layer3/{SEG}/{domain}/<files>
```

Engine-wide config MAY live under a shared bucket when it is not segment-owned:

```
config/shared/{domain}/<files>
```

## 4) Produced artefacts are segment-scoped

All produced artefacts include layer + segment in their path.

Data:
```
data/layer{1,2,3}/{SEG}/{dataset_id}/<partitions>/<files>
data/layer{1,2,3}/{SEG}/validation/manifest_fingerprint={manifest_fingerprint}/...
data/layer{1,2,3}/{SEG}/receipts/manifest_fingerprint={manifest_fingerprint}/...
data/layer{1,2,3}/{SEG}/receipts/instance/output_id={output_id}/<partitions>/instance_receipt.json
```
Note: The instance receipt path above is for engine-emitted receipts. If the engine is a black box and does not emit receipts, Scenario Runner writes verifier receipts in its own object store under `fraud-platform/sr/instance_receipts/...`.

Logs:
```
logs/layer{1,2,3}/{SEG}/rng/{audit|trace}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...
logs/layer{1,2,3}/{SEG}/rng/events/{family}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl
logs/layer{1,2,3}/{SEG}/edge/.../run_id={run_id}/...
```

Reports:
```
reports/layer{1,2,3}/{SEG}/state=S#/parameter_hash={parameter_hash}/run_report.json
reports/layer{1,2,3}/segment_state_runs/segment={SEG}/utc_day={utc_day}/segment_state_runs.jsonl
```

## 5) Token naming + order

Use only these token names: `seed`, `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, `utc_day`.

Order when multiple tokens apply:
`seed -> parameter_hash -> manifest_fingerprint -> scenario_id -> run_id -> utc_day`.

## 6) Config data policy

`config/` contains YAML/JSON only. Any parquet table is a dataset and belongs under `data/`.
