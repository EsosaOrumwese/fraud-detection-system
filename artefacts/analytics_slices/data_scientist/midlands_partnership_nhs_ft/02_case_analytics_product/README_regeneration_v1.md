# README Regeneration v1

Purpose:
- explain how to rebuild the bounded case analytics product for this slice
- keep the regeneration path explicit and handover-safe

Scope:
- bounded 20-part governed subset from `runs/local_full_run-7`
- case-centric analytical product only
- not a full-platform or full-run rebuild

Core entrypoint:
- `models/build_case_analytics_product.py`

What the build script does:
1. reads the bounded file selection in `logs/bounded_file_selection.json`
2. runs the case-grain profiling pack
3. materialises `case_chronology_rollup_v1.parquet`
4. materialises `case_analytics_product_v1.parquet`
5. materialises `case_model_ready_v1.parquet`
6. materialises `case_reporting_ready_v1.parquet`
7. materialises the consumer summaries
8. writes fit-for-use metrics

How to rerun:

```powershell
python artefacts/analytics_slices/data_scientist/midlands_partnership_nhs_ft/02_case_analytics_product/models/build_case_analytics_product.py
```

Expected outputs:
- `extracts/case_chronology_rollup_v1.parquet`
- `extracts/case_analytics_product_v1.parquet`
- `extracts/case_model_ready_v1.parquet`
- `extracts/case_reporting_ready_v1.parquet`
- `extracts/case_product_consumer_summary_v1.parquet`
- `extracts/case_product_pathway_summary_v1.parquet`
- profiling and fit-check outputs under `metrics/`

Preconditions:
- the bounded governed parquet files referenced in `logs/bounded_file_selection.json` must exist
- the local Python environment must have `duckdb`

Non-goals:
- this does not regenerate the Data Engine
- this does not rebuild the full governed world
- this does not run a full downstream modelling programme
