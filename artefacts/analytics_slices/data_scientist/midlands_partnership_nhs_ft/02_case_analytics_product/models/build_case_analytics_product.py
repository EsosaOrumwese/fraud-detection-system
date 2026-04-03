from __future__ import annotations

import json
from pathlib import Path

import duckdb


def write_frame_outputs(df, out_csv: Path, out_json: Path) -> None:
    df.to_csv(out_csv, index=False)
    out_json.write_text(df.to_json(orient="records", indent=2, date_format="iso"))


def main() -> None:
    repo = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
    root = (
        repo
        / "artefacts"
        / "analytics_slices"
        / "data_scientist"
        / "midlands_partnership_nhs_ft"
        / "02_case_analytics_product"
    )
    sql_dir = root / "sql"
    metrics_dir = root / "metrics"
    extracts_dir = root / "extracts"
    selection = json.loads((root / "logs" / "bounded_file_selection.json").read_text())

    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")

    profiling_steps = [
        (
            "01_profile_case_grain",
            {
                "case_timeline_files": selection["case_timeline_files"],
                "anchor_files": selection["anchor_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
            },
        ),
        (
            "02_profile_case_event_types",
            {
                "case_timeline_files": selection["case_timeline_files"],
            },
        ),
        (
            "03_profile_case_link_shape",
            {
                "case_timeline_files": selection["case_timeline_files"],
            },
        ),
    ]
    for step_name, params in profiling_steps:
        sql = (sql_dir / f"{step_name}.sql").read_text()
        df = con.execute(sql, params).fetchdf()
        write_frame_outputs(df, metrics_dir / f"{step_name}.csv", metrics_dir / f"{step_name}.json")

    build_steps = [
        (
            "04_build_case_chronology_rollup",
            {
                "case_timeline_files": selection["case_timeline_files"],
                "case_chronology_rollup_output": str(extracts_dir / "case_chronology_rollup_v1.parquet"),
            },
        ),
        (
            "05_build_case_analytics_product",
            {
                "case_chronology_rollup_path": str(extracts_dir / "case_chronology_rollup_v1.parquet"),
                "anchor_files": selection["anchor_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
                "case_analytics_product_output": str(extracts_dir / "case_analytics_product_v1.parquet"),
            },
        ),
        (
            "06_build_case_model_ready",
            {
                "case_analytics_product_path": str(extracts_dir / "case_analytics_product_v1.parquet"),
                "case_model_ready_output": str(extracts_dir / "case_model_ready_v1.parquet"),
            },
        ),
        (
            "07_build_case_reporting_ready",
            {
                "case_analytics_product_path": str(extracts_dir / "case_analytics_product_v1.parquet"),
                "case_reporting_ready_output": str(extracts_dir / "case_reporting_ready_v1.parquet"),
            },
        ),
        (
            "09_case_product_consumer_summary",
            {
                "case_reporting_ready_path": str(extracts_dir / "case_reporting_ready_v1.parquet"),
                "case_product_consumer_summary_output": str(extracts_dir / "case_product_consumer_summary_v1.parquet"),
            },
        ),
        (
            "10_case_product_pathway_summary",
            {
                "case_reporting_ready_path": str(extracts_dir / "case_reporting_ready_v1.parquet"),
                "case_product_pathway_summary_output": str(extracts_dir / "case_product_pathway_summary_v1.parquet"),
            },
        ),
    ]
    for step_name, params in build_steps:
        sql = (sql_dir / f"{step_name}.sql").read_text()
        con.execute(sql, params)

    fit_sql = (sql_dir / "08_case_product_fit_for_use_checks.sql").read_text()
    fit_df = con.execute(
        fit_sql,
        {
            "case_analytics_product_path": str(extracts_dir / "case_analytics_product_v1.parquet"),
            "case_model_ready_path": str(extracts_dir / "case_model_ready_v1.parquet"),
            "case_reporting_ready_path": str(extracts_dir / "case_reporting_ready_v1.parquet"),
        },
    ).fetchdf()
    write_frame_outputs(
        fit_df,
        metrics_dir / "08_case_product_fit_for_use_checks.csv",
        metrics_dir / "08_case_product_fit_for_use_checks.json",
    )

    print("case_analytics_product build complete")


if __name__ == "__main__":
    main()
