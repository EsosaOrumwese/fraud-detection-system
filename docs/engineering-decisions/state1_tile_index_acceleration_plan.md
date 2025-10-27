# Engineering Decision: Segment 1B S1 Tile Index Acceleration

**Date:** 2025‑10‑27  
**Owners:** Data Engine L1 / Segment 1B team  
**Status:** Draft (implementation in progress)  
**Scope:** `packages/engine/src/engine/layers/l1/seg_1B/s1_tile_index/**`

## Background
S1 (Tile Index) enumerates every admissible raster cell for 249 countries across a 16 755 × 43 199 population grid (~724 M cells). The original algorithm:

* iterated per cell with shapely predicates,
* buffered every tile in memory before writing parquet, and
* ran strictly on a single CPU core.

Even after recent streaming tweaks, the stage still takes *hours* and routinely starves the rest of Segment 1B. We need a deliberate roadmap that drops S1 to “mere minutes” without compromising determinism, contract fidelity, or observability.

## Goals
1. **Runtime:** Reduce end-to-end S1 execution to < 15 minutes on an 8‑core workstation.
2. **Memory:** Keep RSS < 2 GB regardless of raster size.
3. **Determinism:** Preserve tile ordering, schema, and validation receipts verbatim.
4. **Observability:** Emit progress telemetry (country/second, tiles/sec, shard flushes) for ops.
5. **Safety:** Provide guardrails/tests that prove parity vs the legacy enumerator on sampled windows before rollout.

## Constraints
* S1 output contracts (`tile_index`, `tile_bounds`, country summaries) are frozen.
* We cannot alter the governed raster or polygon inputs.
* Parallel execution must remain deterministic (stable ordering + reproducible shards).

## Plan of Record
The acceleration strategy spans four complementary tracks. Each track is independently valuable, but all four are required to reliably reach the sub‑15 minute target.

### Track 1 – Precise Windowing & Chunking (In Progress)
* Replace `_raster_window_for_geometry` with `dataset.window(*geometry.bounds)` followed by clipping to raster extents. This removes the coarse corner sampling and avoids scanning huge ocean boxes.
* Standardize chunk windows (e.g. 1024×1024) and walk them deterministically (row-major). Record timing per chunk in the stage log.
* Outcome: fewer rasterize calls + predictable chunk counts.

### Track 2 – Vectorized Inclusion & Geometry (In Progress)
* Already swapped to chunked `rasterio.features.rasterize`; next steps:
  * Cache per-country masks (or polygon envelopes) and slice them instead of re-rasterizing every chunk.
  * Compute centroid grids via affine math once per chunk and reuse for all rules.
  * Batch geodesic area calls (use `Geod.polygon_area_perimeter` on polygons derived from chunk bounds) or adopt planar approximations validated against the reference implementation.
  * Maintain parity tests comparing old and new outputs on sampled windows.
* Outcome: CPU work dominated by fast NumPy ops rather than shapely loops.

### Track 3 – Parallel Execution & Streaming Shards (Planned)
* Partition countries into work units (e.g. by raster footprint) and dispatch them to a `ProcessPoolExecutor`.
* Each worker writes to its own temp shard directories (`tile_index/worker-<id>`). After workers finish, deterministically merge shards (sorted by country ISO + tile_id) into the canonical partition while preserving batch hashes and RNG accounting.
* Extend PAT metrics to include per-worker timings, bytes, and throughput.
* Outcome: use all CPU cores; bring runtime down by ~N_workers.

### Track 4 – Validation, Guardrails, and Rollout (Planned)
* Build a golden regression suite:
  * Sampled countries (e.g. US, BRA, IND, ISL) across both inclusion rules.
  * Compare row counts, hashes, and country summaries vs the last “correct” build.
* Add feature flag / CLI switch to fall back to the legacy path for comparison until the new pipeline is proven.
* Update documentation (runbook + README) to reflect new dependencies (e.g. rasterio masks) and logging expectations.
* Outcome: safe rollout with clear rollback path.

## Additional Enhancements
* **Adaptive chunk size:** scale chunk dimensions based on polygon area to reduce rasterize calls on small islands while keeping memory bounded on large countries.
* **On-disk mask cache:** for the heaviest countries, persist vectorized masks between runs (keyed by manifest) to avoid recomputation when seeds differ but geometry doesn’t.
* **Metrics export:** capture tiles/sec, batches/sec, and shard flush intervals for SLO tracking.

## Success Criteria
* Single full-world run on reference hardware completes S1 in ≤ 15 minutes.
* Peak RSS under 2 GB across all workers.
* Contract tests + sampled comparisons show byte-for-byte alignment (or documented tolerances) with historical outputs.
* Stage logs clearly identify throughput and hotspots for future tuning.

## Next Steps
1. Track 1 detailed breakdown (current focus):
   - **1.A – Exact windowing.** Replace `_raster_window_for_geometry` with a deterministic `dataset.window`/`rowcol` mapping for the polygon bounds (plus fallback). This ensures the chunk iterator only touches cells that truly belong to the country.
   - **1.B – Chunk instrumentation.** Emit per-chunk telemetry (`country`, row/col span, tiles visited/included, duration) so we can see hot spots immediately in `segment1b_regen*.log`.
   - **1.C – Validation harness.** Run sampled countries through the tightened window to confirm we still enumerate the exact tile set (hash + count) before moving to later tracks.
2. Track 2 polish (in flight):
   - Cache per-country raster masks (largest footprints) to avoid re-rasterizing every chunk when the geometry doesn’t change across runs.
   - Batch geodesic area computations so each chunk amortizes the cost of `Geod.polygon_area_perimeter`.
   - Confirm the vectorized path stays byte-for-byte aligned via the new pytest parity harness.
3. Track 3 design (approved by project owner):
   - Use a `ProcessPoolExecutor` to assign countries/chunks to workers, each writing to its own temp shard directories (`tile_index/worker-XXX`, `tile_bounds/worker-XXX`).
   - Once workers finish, deterministically merge sorted shards (ISO + tile_id) into the canonical partition, preserving manifest+hash rules.
   - Propagate per-worker telemetry (tiles/sec, chunk counts) to the stage logs and PAT metrics.

### Track 3 Implementation Plan (draft)
1. **Work partitioning.** Group countries into work units (default: one country per unit, with optional splitting for large window footprints). Enqueue jobs in the main process; each job contains the ISO code, bounding window metadata, and seeds.
2. **Worker pool.** Spin up a `ProcessPoolExecutor(max_workers = min(cpu_count, configured_cap))`. Each worker re-opens the raster/dictionary, runs `_enumerate_tiles` for its assigned country, and writes to a dedicated temp directory (`tile_index/.tmp.worker-<pid>` etc.).
3. **Progress/telemetry.** The main process tracks futures, logging start/finish events per country (tiles emitted, duration). Workers emit chunk-level logs locally; the parent aggregates per-worker tiles/sec and writes them into the PAT metrics (`workers_used`, `tiles_per_sec`, etc.).
4. **Shard merge.** After all futures resolve, the parent process reads each worker’s shards, merges them in deterministic order (sort by `country_iso`, `tile_id`) into the final partition using `_ParquetBatchWriter`, computes the combined digest, and removes the temp directories. Failures trigger cleanup of the worker temp dirs before raising.
5. **Fallback & toggles.** Keep a CLI flag (`--s1-workers=N` / `--s1-single-thread`) so we can switch between legacy single-thread and the new multiprocess path until parity tests pass in CI. Default to the single-thread path until Track 4 sign-off.
6. **Validation hook.** During the merge phase, optionally re-hash worker shards or sample rows to confirm ordering before writing the canonical files. Integrate this with the Track 4 regression harness.
4. Track 4 (validation & rollout):
   - Stand up the golden-country regression harness (US/BRA/IND/etc.) and block feature flags until hashes align.
   - Document rollout toggles in `docs/runbooks/segment1a_1b_execution.md` once parallel S1 ships.

This document will track updates as each track is delivered. Once runtime targets are consistently hit, we will freeze the design and mark the decision “Accepted.”
