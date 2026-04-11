# dev_full Offline Investigation Workbench

This workspace is the active analytical workbench for the governed `dev_full` data world.

It is intentionally separate from:

- `docs/`, which should remain the authoritative and published narrative surface
- `artefacts/`, which should remain the promoted output surface
- `scratch_files/`, which is too disposable for governed analytical work

## Purpose

Use this area for:

- notebooks and rough analytical development
- DuckDB and SQL query packs
- intermediate extracts and metrics
- working figures
- investigation notes that are not yet promoted

## Promotion posture

Work should usually move through these stages:

1. explored here in `analysis/dev_full_offline_investigation/`
2. stabilized as a reusable slice or extract
3. promoted into `artefacts/` or `docs/` once the result is claim-worthy

## Folder guide

- `00_surface_atlas/`: governed map of important data surfaces and their platform meaning
- `01_world_context/`: world-level profiling and governed source understanding
- `02_rtdl_case_label_learning/`: analysis of cross-plane relationships between traffic, context, truth, and learning basis
- `notebooks/`: exploratory and reproducible notebooks
- `sql/`: reusable DuckDB / SQL queries
- `figures/`: working figures that are not yet promoted
- `extracts/`: bounded parquet / csv outputs used during analysis
- `metrics/`: compact metrics packs produced by queries or notebooks
- `notes/`: working analytical notes

## Working rules

- treat engine outputs as read-only authority surfaces
- do not use this area for ad hoc dumps with unclear lineage
- keep extracts bounded and reproducible
- name outputs so the question they answer is obvious
- distinguish traffic, context, truth, and telemetry explicitly
- keep time-safety visible whenever a surface could be confused with live-decision context
