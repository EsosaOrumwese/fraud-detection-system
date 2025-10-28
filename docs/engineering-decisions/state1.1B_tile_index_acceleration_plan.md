# Engineering Decision Addendum: Segment 1B S1 Tile Index – Sub‑5 Minute Acceleration Path

**Date:** 2025-10-27  
**Owners:** Data Engine L1 / Segment 1B team  
**Status:** Draft (pending execution)  
**Supersedes/Extends:** `state1_tile_index_acceleration_plan.md` (Tracks 1–3 baseline)

## Purpose

Track 1–3 improvements have reduced the worst pain points of the Segment 1B tile index stage, but the latest multiprocess build still requires ~51 minutes. This addendum records the focused optimisation path required to hit the “few minutes” objective (target ≤ 5 minutes on the reference 12‑core workstation) while preserving determinism and contract fidelity.

## Scope

Applies to `packages/engine/src/engine/layers/l1/seg_1B/s1_tile_index/**`, the associated PAT metrics, and runbook collateral. The work items below layer on top of the existing Tracks 1–3 plan and must be reflected in Track 4 validation before rollout.

## Acceleration Strategy

1. **Profile-Guided Prioritisation**
   - Capture a representative S1 execution under `py-spy` (wall clock) and `cProfile` (per-function CPU) with `--s1-workers` set to current default (12).
   - Annotate the flame graphs to quantify time spent in: raster mask generation, per-tile Python loops, parquet flushes, and merge/scatter phases.
   - Use these measurements to sequence the optimisation tasks below and to guard against regressions during implementation.

2. **Vectorise the Chunk Hot Loop**
   - Replace the per-tile Python loop at `runner.py#L700+` with batch operations:
     * Derive `tile_id = row * ncols + col` using NumPy arrays for the entire chunk.
     * Compute centroid lon/lat via affine transforms in bulk (`Affine * np.stack`).
     * Generate tile bounds from precomputed lon/lat edge arrays instead of repeated `tile_bounds()` calls.
   - Emit columnar batches directly into the parquet writer, eliminating Python-level iteration over the ~221 M rows.

3. **Amortise Writer Overhead**
   - Extend `_ParquetBatchWriter` (or replace it with a shared `pyarrow.ParquetWriter`) to accept array batches, bump row-group size (≥ 1 M rows), and switch to a faster compression codec (Snappy/LZ4) while validating file sizes.
   - Reduce flush frequency to minimise filesystem churn; ensure shard naming remains deterministic.

4. **Cost-Aware Worker Scheduling**
   - Replace the round-robin `_partition_countries` splitter with a priority queue that assigns the next heaviest raster window (by pixel count) to the next available worker.
   - Persist per-country cost estimates (window area, historical tiles/sec) so subsequent runs warm the queue ordering.
   - Goal: keep all workers busy until the final seconds; avoid the long tail where one worker carries tens of millions of tiles.

5. **Warm Caches & Shared Metadata**
   - Precompute per-row geodesic areas and lon/lat edge vectors once per process, store them in shared memory (e.g. `multiprocessing.shared_memory` / `numpy.memmap`) to avoid repeated `Geod` calls.
   - Cache rasterised inclusion masks for the heaviest countries between chunks and across runs (keyed by manifest hash) when inclusion rule is deterministic.

6. **Iterate with Continuous Measurement**
   - After each optimisation pass, execute Segment 1B with PAT telemetry enabled; record tiles/sec per worker, rows flushed per shard, and wall clock totals in the logbook.
   - Update this addendum and the primary decision document with achieved timings, noting deltas against the 51 minute baseline.
   - Once S1 consistently completes ≤ 5 minutes, capture before/after metrics and promote the new defaults via Track 4 validation.

## Validation & Rollout Guardrails

- Extend the Track 4 regression harness to cover multi-worker runs with the vectorised writer path, ensuring byte-for-byte parity on sampled countries (US, BR, IN, island cases).
- Stress test with varying `--s1-workers` (1, 4, 8, 12) and multiple seeds to confirm determinism of shard ordering and hash receipts.
- Document new operational knobs (e.g. `--s1-workers`, optional compression overrides) in `docs/runbooks/segment1a_1b_execution.md`.
- Maintain the legacy single-thread path behind a CLI flag until validation sign-off.

## Deliverables

- Profiling artefacts (SVG/JSON) committed to `docs/perf/segment1b_s1/`.
- Pull requests covering:
  1. Vectorised enumerator + writer enhancements.
  2. Scheduler upgrade + telemetry extensions.
  3. Cache layer integration + config toggles.
  4. Regression harness updates and runbook documentation.
- Updated PAT metrics referencing new counters (`tiles_per_second_peak`, `worker_idle_seconds`, cache hit ratios).

## Success Criteria

- S1 completes within ≤ 5 minutes on the reference workstation with 12 workers.
- Peak RSS remains below 2 GB per process; aggregate disk IO does not exceed existing thresholds.
- PAT/run-report artefacts show increased throughput (≥ 40 k tiles/sec aggregate) and balanced worker utilisation (≤ 10 % idle variance).
- Regression suite confirms deterministic outputs across seeds, worker counts, and inclusion rules.

Once these criteria are met, merge the addendum back into the primary decision document and mark both plans as “Accepted”.

## Profiling Snapshot (2025-10-27)

- Harness: `python -m cProfile -o docs/perf/segment1b_s1/s1_subset_workers12.pstats scratch_files/run_s1_profile.py` (12-country heavy subset, `--workers=12`)  
  - Wall clock ≈ 2 442 s, 139 M tiles emitted, 57 k tiles/sec aggregate.  
  - Worker telemetry shows RU alone consumes ~2 444 s despite multiprocessing, signalling the need for cost-aware scheduling.
- Single-process baseline: `docs/perf/segment1b_s1/s1_subset_single.pstats` (same subset, `--mode single`)  
  - Wall clock ≈ 12 137 s, 11.5 k tiles/sec.  
  - Hotspots (cumulative time) align with the Stage 2 action items:  
    1. `tile_bounds` / `rasterio.transform.xy` (affine transforms) ≈ 18 ks combined.  
    2. `_ParquetBatchWriter.append_row` + Polars frame construction ≈ 1.8 ks.  
    3. `record_included_tile` / per-row bookkeeping ≈ 0.6 ks.  
  - Confirms vectorising chunk geometry and batching writes should yield the steepest gains.
- All profiling artefacts live in `docs/perf/segment1b_s1/`; scripts to reproduce:  
  - `scratch_files/run_s1_profile.py` (subset runner with single/multi mode).  
  - `scratch_files/show_profile_stats.py` (quick pstats inspection).  
  - `scratch_files/top_countries.py` (rank countries by raster footprint for targeted subsets).

These numbers establish the baseline against which the upcoming optimisation work will be measured.
