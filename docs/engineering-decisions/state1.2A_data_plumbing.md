# Segment 2A · State 1 — Data Plumbing Notes

## Goals

- Reuse the S0 gate receipt to resolve every sealed input for a `(seed, manifest_fingerprint)` pair.
- Stream `site_locations` rows into a deterministic lookup kernel that joins against `tz_world` polygons and applies the sealed `tz_nudge` policy.
- Persist `s1_tz_lookup` (plan table) plus optional diagnostics, obeying schema/identity law and resumability.

## Asset Resolution

1. Load the S0 gate receipt via dictionary path `data/layer1/2A/s0_gate_receipt/fingerprint={fp}/s0_gate_receipt.json`.
2. Resolve sealed datasets using the dictionary helpers that already back S0:
   | Asset ID | Source | Notes |
   | --- | --- | --- |
   | `site_locations` | `data/layer1/1B/site_locations/seed={seed}/fingerprint={fp}/` | 1B egress for this run; **read-only** |
   | `tz_world_2025a` | `reference/spatial/tz_world/2025a/tz_world.parquet` | Must match CRS=WGS84 |
   | `tz_nudge` | `config/timezone/tz_nudge.yml` | Contains ε (0.0001° by default) and digest |
   | `tz_overrides` | *sealed but unused in S1* | Logged for completeness; overrides applied in S2 |
3. Assert path↔manifest equality: any resolved path must contain the same `{seed, fingerprint}` tokens captured in the sealed manifest.

## Runner Architecture

```
Segment2AS1Config
  ├─ data_root (Path)
  ├─ seed (int)
  ├─ manifest_fingerprint (str)
  ├─ tzdb_release_tag (str)  # only for logging lineage
  └─ dictionary/dictionary_path overrides

Segment2AS1Runner
  ├─ _load_receipt() → GateReceipt dataclass
  ├─ _resolve_site_locations() → iterator[pl.DataFrame | Arrow batch]
  ├─ _build_tz_index() → geometry lookup primitive (STR tree)
  ├─ _assign_tz(batch, lookup_ctx, nudge_policy) → DataFrame with tzid + nudge cols
  ├─ _write_output(iterator) → writes `s1_tz_lookup` partitioned by seed/fingerprint
  └─ run(config) → Segment2AS1Result(resume flag, output paths)
```

## Streaming Strategy

- Use Polars scan or PyArrow dataset to stream `site_locations` in bounded batches (e.g., 250k rows) to keep memory predictable.
- Build the polygon lookup index once per run (e.g., via Shapely/pygeos) using the sealed `tz_world` parquet; store geometry and metadata in an immutable context struct.
- For each batch:
  1. Convert lat/lon pairs into shapely `Point`s.
  2. Query the polygon index; if >1 match, defer to ε-nudge helper (uses vector math) and record `nudge_lat_deg/nudge_lon_deg`.
  3. Emit deterministic `created_utc` from `datetime.now(timezone.utc)` once per batch.

## Persistence & Resumability

- Output path: `data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={fp}/part-*.parquet`.
- If the partition already exists and matches schema digest (quick check: row count + Polars `frame_equal` against a regenerated sample), honor `--resume` and skip execution.
- Log structured INFO entries mirroring 1A/1B: start, streaming progress (rows processed, nudged count), completion.

## Next Steps

1. Add S1 config/result dataclasses + orchestrator hooks alongside the existing S0 runner.
2. Implement shared helpers for reading the gate receipt and resolving sealed assets (can live under `engine.layers.l1.seg_2A.shared`).
3. Wire up the CLI/Makefile once S1 runner stabilizes so `make segment2a` can optionally continue from S0 → S1.

