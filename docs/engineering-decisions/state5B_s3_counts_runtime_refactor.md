# State 5B S3 Bucket Counts — Runtime Refactor (Full Fidelity)

## Context

Segment 5B S3 (bucket counts) was taking hours at full 90-day / 1-hour fidelity because it built large Python lists and used per-row loops. The requirement was to keep **full-fidelity outputs** (no resolution downscale) while delivering the **fastest runtime at current scale**.

## Constraints (binding)

- **State-expanded docs are the binding spec** for output schema and ordering.
- **Output ordering** must preserve the writer ordering in the spec: rows sorted by
  `scenario_id, merchant_id, zone_representation, channel_group, bucket_index`.
- **RNG determinism** must be preserved for the same `(seed, manifest_fingerprint, parameter_hash, scenario_id)` identity.
- **Outputs must remain byte-stable** for the same identity partition.

## Decision

Refactor S3 to **process Parquet row-group chunks in parallel**, then **merge outputs deterministically** in row-group order. RNG events are written per-chunk and merged into a single canonical log, with trace/summary reconstructed after merge.

This keeps full fidelity while removing the large in-memory row lists that caused multi-hour runtimes.

## Implementation (what was done)

### 1) Chunked, parallel processing

- Read `s2_realised_intensity_5B` via PyArrow in **row-group ranges** (not full scans).
- Partition row groups into deterministic chunks.
- Process chunks with a `ProcessPoolExecutor`.
- Each chunk writes:
  - a **counts part file** (Parquet) and
  - an **RNG event log part** (JSONL).

### 2) Deterministic merge

- Merge counts parts **in row-group order** into the final
  `s3_bucket_counts_5B.parquet`.
- Merge RNG event parts **in the same row-group order** into
  `logs/rng/events/.../part-00000.jsonl`.
- Rebuild:
  - `rng_trace_log.jsonl`
  - `rng_totals.json`
  from the merged event stream to keep determinism receipts intact.

### 3) RNG logging support (event-only mode)

- Extended RNG logging to allow **event-only** mode with configurable filenames.
- S3 writes events only during chunk processing; trace/summary are generated **once** after merge.

### 4) Housekeeping

- Reset S3 RNG logs once per run_id at S3 start to avoid duplicates.
- Clean up chunk part files after merge.

## Operational notes

- Concurrency is controlled by `S3_MAX_WORKERS` (default: `os.cpu_count()`).
- This refactor assumes **S2 emits sorted intensity rows** in the spec order.
- Chunking uses row-group boundaries to preserve order without global sort.

## Files changed

- `packages/engine/src/engine/layers/l2/seg_5B/s3_counts/runner.py`
  - row-group chunking, parallel processing, deterministic merge, RNG log merge.
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/rng_logging.py`
  - event-only logging, configurable filenames, optional trace/summary emission.

## Guidance for downstream interventions

If another state needs similar scale intervention while preserving determinism:

1) **Choose a deterministic chunk key** (row-group index is ideal if input is already ordered).
2) **Never reorder across chunks** unless the spec explicitly allows it.
3) **Write per-chunk outputs**, then merge in deterministic order.
4) If RNG is involved, **log events per chunk** and rebuild trace/summary post-merge.
5) Keep any **schema ordering guarantees** intact in the final write.

This pattern keeps outputs byte-stable without reducing fidelity.
