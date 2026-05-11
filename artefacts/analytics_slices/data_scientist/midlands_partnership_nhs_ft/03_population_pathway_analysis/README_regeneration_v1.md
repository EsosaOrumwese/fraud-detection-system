# README Regeneration v1

Purpose:
- explain how to rebuild the bounded population-pathway slice
- keep the regeneration path explicit and handover-safe

Scope:
- bounded 20-part governed subset from `runs/local_full_run-7`
- linked population, cohort, pathway, and KPI slice only
- not a full-platform rebuild

Core entrypoint:
- `models/build_population_pathway_analysis.py`

What the build script does:
1. reads the bounded file selection in `logs/bounded_file_selection.json`
2. runs the trust-gate profiling pack
3. materialises `population_pathway_base_v1.parquet`
4. materialises `population_cohort_metrics_v1.parquet`
5. materialises `population_pathway_reporting_v1.parquet`
6. materialises `population_pathway_kpis_v1.parquet`
7. materialises `population_pathway_problem_summary_v1.parquet`
8. writes fit-for-use metrics and the execution fact pack

How to rerun:

```powershell
python artefacts/analytics_slices/data_scientist/midlands_partnership_nhs_ft/03_population_pathway_analysis/models/build_population_pathway_analysis.py
```

Expected outputs:
- `extracts/population_pathway_base_v1.parquet`
- `extracts/population_cohort_metrics_v1.parquet`
- `extracts/population_pathway_reporting_v1.parquet`
- `extracts/population_pathway_kpis_v1.parquet`
- `extracts/population_pathway_problem_summary_v1.parquet`
- profiling and fit-check outputs under `metrics/`

Preconditions:
- the bounded governed parquet files referenced in `logs/bounded_file_selection.json` must exist
- the local Python environment must have `duckdb`

Non-goals:
- this does not regenerate the Data Engine
- this does not rebuild the full governed world
- this does not run a full predictive-modelling programme
