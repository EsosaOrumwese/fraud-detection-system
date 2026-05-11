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
        / "03_population_pathway_analysis"
    )
    sql_dir = root / "sql"
    metrics_dir = root / "metrics"
    extracts_dir = root / "extracts"
    selection = json.loads((root / "logs" / "bounded_file_selection.json").read_text())

    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")

    profiling_steps = [
        ("01_profile_population_sources", {"event_files": selection["event_files"], "case_files": selection["case_files"]}),
        ("02_profile_event_case_alignment", {"event_files": selection["event_files"], "case_files": selection["case_files"]}),
        (
            "03_profile_link_coverage",
            {
                "event_files": selection["event_files"],
                "anchor_files": selection["anchor_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
            },
        ),
    ]
    for step_name, params in profiling_steps:
        sql = (sql_dir / f"{step_name}.sql").read_text()
        df = con.execute(sql, params).fetchdf()
        write_frame_outputs(df, metrics_dir / f"{step_name}.csv", metrics_dir / f"{step_name}.json")

    build_steps = [
        (
            "04_build_population_pathway_base",
            {
                "event_files": selection["event_files"],
                "anchor_files": selection["anchor_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
                "population_pathway_base_output": str(extracts_dir / "population_pathway_base_v1.parquet"),
            },
        ),
        (
            "05_build_population_cohort_metrics",
            {
                "population_pathway_base_path": str(extracts_dir / "population_pathway_base_v1.parquet"),
                "population_cohort_metrics_output": str(extracts_dir / "population_cohort_metrics_v1.parquet"),
            },
        ),
        (
            "06_build_population_pathway_reporting",
            {
                "population_pathway_base_path": str(extracts_dir / "population_pathway_base_v1.parquet"),
                "population_pathway_reporting_output": str(extracts_dir / "population_pathway_reporting_v1.parquet"),
            },
        ),
        (
            "07_build_population_pathway_kpis",
            {
                "population_pathway_base_path": str(extracts_dir / "population_pathway_base_v1.parquet"),
                "population_pathway_kpis_output": str(extracts_dir / "population_pathway_kpis_v1.parquet"),
            },
        ),
        (
            "09_population_pathway_problem_summary",
            {
                "population_cohort_metrics_path": str(extracts_dir / "population_cohort_metrics_v1.parquet"),
                "population_pathway_problem_summary_output": str(extracts_dir / "population_pathway_problem_summary_v1.parquet"),
            },
        ),
    ]
    for step_name, params in build_steps:
        sql = (sql_dir / f"{step_name}.sql").read_text()
        con.execute(sql, params)

    fit_sql = (sql_dir / "08_population_pathway_fit_for_use_checks.sql").read_text()
    fit_df = con.execute(
        fit_sql,
        {
            "population_pathway_base_path": str(extracts_dir / "population_pathway_base_v1.parquet"),
            "population_cohort_metrics_path": str(extracts_dir / "population_cohort_metrics_v1.parquet"),
            "population_pathway_reporting_path": str(extracts_dir / "population_pathway_reporting_v1.parquet"),
            "population_pathway_kpis_path": str(extracts_dir / "population_pathway_kpis_v1.parquet"),
        },
    ).fetchdf()
    write_frame_outputs(
        fit_df,
        metrics_dir / "08_population_pathway_fit_for_use_checks.csv",
        metrics_dir / "08_population_pathway_fit_for_use_checks.json",
    )

    fact_pack = {
        "slice": "midlands_partnership_nhs_ft/03_population_pathway_analysis",
        "bounded_selection": selection,
        "source_profile": json.loads((metrics_dir / "01_profile_population_sources.json").read_text()),
        "event_case_alignment": json.loads((metrics_dir / "02_profile_event_case_alignment.json").read_text()),
        "link_coverage": json.loads((metrics_dir / "03_profile_link_coverage.json").read_text()),
        "fit_for_use": json.loads((metrics_dir / "08_population_pathway_fit_for_use_checks.json").read_text()),
        "kpi_summary": con.execute(
            "SELECT * FROM parquet_scan(?) ORDER BY split_role",
            [str(extracts_dir / "population_pathway_kpis_v1.parquet")],
        ).fetchdf().to_dict(orient="records"),
        "pathway_summary": con.execute(
            "SELECT * FROM parquet_scan(?) ORDER BY split_role, pathway_stage",
            [str(extracts_dir / "population_pathway_reporting_v1.parquet")],
        ).fetchdf().to_dict(orient="records"),
        "cohort_summary": con.execute(
            "SELECT * FROM parquet_scan(?) ORDER BY split_role, cohort_label",
            [str(extracts_dir / "population_cohort_metrics_v1.parquet")],
        ).fetchdf().to_dict(orient="records"),
        "problem_summary": con.execute(
            "SELECT * FROM parquet_scan(?) ORDER BY burden_rank, yield_rank, cohort_label",
            [str(extracts_dir / "population_pathway_problem_summary_v1.parquet")],
        ).fetchdf().to_dict(orient="records"),
        "generated_assets": {
            "population_pathway_base": str(extracts_dir / "population_pathway_base_v1.parquet"),
            "population_cohort_metrics": str(extracts_dir / "population_cohort_metrics_v1.parquet"),
            "population_pathway_reporting": str(extracts_dir / "population_pathway_reporting_v1.parquet"),
            "population_pathway_kpis": str(extracts_dir / "population_pathway_kpis_v1.parquet"),
            "population_pathway_problem_summary": str(extracts_dir / "population_pathway_problem_summary_v1.parquet"),
            "build_script": str(root / "models" / "build_population_pathway_analysis.py"),
        },
    }
    (metrics_dir / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2))

    print("population_pathway_analysis build complete")


if __name__ == "__main__":
    main()
