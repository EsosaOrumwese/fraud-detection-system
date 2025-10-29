# S6 Jitter Acceleration Plan

**Date:** 2025-10-29
**Owners:** Data Engine L1 / Segment 1B team
**Status:** Draft (pending execution)

## Objective

Trim Segment 1B state-6 (site jitter) from ~55 minutes to under 5 minutes on the reference 12-core workstation while retaining deterministic output, RNG budgets, and existing contracts.

## Baseline Observations

* Current run (2025-10-29) shows S6 takes ~55 minutes. Logs reveal long tails on high-site countries (e.g., US, QA, NL).
* Per-country loop still issues per-site Shapely calls and per-attempt RNG draws; memory remains stable but CPU is the bottleneck.
* Each jitter attempt currently consumes one RNG block (after the recent fix); logging now captures start/complete per ISO but lacks timings.

## Action Plan

### 1. Profiling (WIP)
- Added per-country start/complete logging (with site counts and elapsed seconds) and introduced 	ools/perf/run_s6_profile.py to capture cProfile stats for S6 in isolation.
- Next: capture targeted cProfile/py-spy traces for heavy countries (US, QA, RU) using the harness and annotate wall-clock hotspots per ISO.

### 2. Vectorised Containment
- Replace per-site Shapely contains calls with batched evaluation: explore shapely.vectorized.contains or raster-based mask reuse.
- Cache converted polygon data (triangulation or bounding boxes) to avoid re-preparing geometries per point.

### 3. RNG Batching & Attempt Control
- Generate random offsets in vector form (NumPy) to reduce Python overhead per attempt.
- Monitor attempt distribution (histogram per country) to tune the max-attempt limit; adjust heuristics for island-heavy ISOs to avoid wasted retries.

### 4. Data Access Optimisation
- Pre-materialise tile bounds/centroids for high-site countries into NumPy arrays; keep streaming for small ISOs.
- Evaluate a memory-mapped representation of tile bounds to avoid repeated PyArrow conversions.

### 5. Telemetry Enhancements
- Log start/complete per ISO with: planned sites, actual sites, RNG events, elapsed seconds.
- Emit summary histogram (e.g., top 10 countries by wall-clock) in the run report for post-analysis.

### 6. Validation & Rollout
- Build a deterministic fixture (two heavy countries + islands) to run S6 in isolation and unit-test batching code.
- After each optimisation, run the full Segment 1B stack, comparing S6 metrics (wall-clock, RNG counts, output hashes).
- Update PAT expectations if jitter write performance changes significantly.

## Deliverables

1. docs/perf/s6_jitter profiling artefacts and reproduction script.
2. Code changes implementing vectorised containment / RNG batching.
3. Updated logbook entries capturing before/after timings.
4. Regression coverage: new S6 fixture plus Segment 1B integration test when feasible.

## Success Criteria

* S6 completes under 5 minutes on the reference workstation (seed 2025102601, 12 cores).
* Per-country maximum wall-clock < 20 s, median < 2 s.
* RNG budget checks remain at 1 block per attempt; total RNG events unchanged (within tolerance).
* Memory footprint stays within current envelope (< 4 GB per process).
* Determinism maintained across seeds; run report diff shows only performance metrics improving.


