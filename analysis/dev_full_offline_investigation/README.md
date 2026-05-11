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

## Active source basis

Current offline investigation basis:

- `runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`

Pinned identity:

- `run_id = a3bd8cac9a4284cd36072c6b9624a0c1`
- `seed = 42`
- `manifest_fingerprint = 76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460`
- `parameter_hash = 0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00`

This run is the default basis for notebooks, SQL, extracts, and figures in this workspace unless a later note explicitly repins the scope.
