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
        / "04_flow_quality_assurance"
    )
    sql_dir = root / "sql"
    metrics_dir = root / "metrics"
    extracts_dir = root / "extracts"
    selection = json.loads((root / "logs" / "bounded_file_selection.json").read_text())

    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")

    profiling_steps = [
        (
            "01_profile_flow_quality_scope",
            {
                "event_files": selection["event_files"],
                "anchor_files": selection["anchor_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
            },
        ),
        (
            "02_flow_quality_reconciliation_checks",
            {
                "event_files": selection["event_files"],
                "anchor_files": selection["anchor_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
            },
        ),
        (
            "03_flow_quality_anomaly_checks",
            {
                "event_files": selection["event_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
            },
        ),
        (
            "04_flow_quality_label_crosswalk",
            {
                "event_files": selection["event_files"],
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
            "05_build_flow_quality_kpi_before_after",
            {
                "event_files": selection["event_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
                "flow_quality_kpi_before_after_output": str(extracts_dir / "flow_quality_kpi_before_after_v1.parquet"),
            },
        ),
        (
            "06_build_flow_quality_reporting_ready",
            {
                "event_files": selection["event_files"],
                "case_files": selection["case_files"],
                "truth_files": selection["truth_files"],
                "bank_files": selection["bank_files"],
                "flow_quality_reporting_ready_output": str(extracts_dir / "flow_quality_reporting_ready_v1.parquet"),
            },
        ),
    ]
    for step_name, params in build_steps:
        sql = (sql_dir / f"{step_name}.sql").read_text()
        con.execute(sql, params)

    kpi_df = con.execute(
        "SELECT * FROM parquet_scan(?) ORDER BY split_role, kpi_name, kpi_scope",
        [str(extracts_dir / "flow_quality_kpi_before_after_v1.parquet")],
    ).fetchdf()
    write_frame_outputs(
        kpi_df,
        metrics_dir / "05_flow_quality_kpi_before_after.csv",
        metrics_dir / "05_flow_quality_kpi_before_after.json",
    )

    reporting_df = con.execute(
        "SELECT * FROM parquet_scan(?) ORDER BY split_role, pathway_stage",
        [str(extracts_dir / "flow_quality_reporting_ready_v1.parquet")],
    ).fetchdf()
    write_frame_outputs(
        reporting_df,
        metrics_dir / "06_flow_quality_reporting_ready.csv",
        metrics_dir / "06_flow_quality_reporting_ready.json",
    )

    profile = {row["metric_name"]: row["metric_value"] for row in json.loads((metrics_dir / "01_profile_flow_quality_scope.json").read_text())}
    reconciliation = {row["check_name"]: row["check_value"] for row in json.loads((metrics_dir / "02_flow_quality_reconciliation_checks.json").read_text())}
    kpi = json.loads((metrics_dir / "05_flow_quality_kpi_before_after.json").read_text())
    reporting = json.loads((metrics_dir / "06_flow_quality_reporting_ready.json").read_text())

    test_overall = next(row for row in kpi if row["split_role"] == "test" and row["kpi_scope"] == "all_case_selected_flows")
    test_opened_only = next(row for row in kpi if row["split_role"] == "test" and row["kpi_scope"] == "opened_only")
    test_chargeback = next(row for row in kpi if row["split_role"] == "test" and row["kpi_scope"] == "chargeback_decision")

    fact_pack = {
        "slice": "midlands_partnership_nhs_ft/04_flow_quality_assurance",
        "bounded_selection": selection,
        "scope_profile": json.loads((metrics_dir / "01_profile_flow_quality_scope.json").read_text()),
        "reconciliation_checks": json.loads((metrics_dir / "02_flow_quality_reconciliation_checks.json").read_text()),
        "anomaly_checks": json.loads((metrics_dir / "03_flow_quality_anomaly_checks.json").read_text()),
        "label_crosswalk": json.loads((metrics_dir / "04_flow_quality_label_crosswalk.json").read_text()),
        "kpi_before_after": kpi,
        "reporting_ready": reporting,
        "headline_facts": {
            "case_selected_flows": profile["case_selected_flows"],
            "test_case_selected_flows": profile["test_case_selected_flows"],
            "truth_negative_bank_positive_case_selected_flows": profile["truth_negative_bank_positive_case_selected_flows"],
            "truth_positive_bank_negative_case_selected_flows": profile["truth_positive_bank_negative_case_selected_flows"],
            "flows_with_multiple_cases": profile["flows_with_multiple_cases"],
            "event_to_case_link_rate": reconciliation["event_to_case_link_rate"],
            "test_overall_raw_bank_view_rate": test_overall["raw_bank_view_rate"],
            "test_overall_corrected_truth_rate": test_overall["corrected_truth_rate"],
            "test_overall_absolute_gap": test_overall["absolute_gap"],
            "test_opened_only_raw_bank_view_rate": test_opened_only["raw_bank_view_rate"],
            "test_opened_only_corrected_truth_rate": test_opened_only["corrected_truth_rate"],
            "test_opened_only_absolute_gap": test_opened_only["absolute_gap"],
            "test_chargeback_raw_bank_view_rate": test_chargeback["raw_bank_view_rate"],
            "test_chargeback_corrected_truth_rate": test_chargeback["corrected_truth_rate"],
            "test_chargeback_absolute_gap": test_chargeback["absolute_gap"],
        },
        "generated_assets": {
            "flow_quality_kpi_before_after": str(extracts_dir / "flow_quality_kpi_before_after_v1.parquet"),
            "flow_quality_reporting_ready": str(extracts_dir / "flow_quality_reporting_ready_v1.parquet"),
            "build_script": str(root / "models" / "build_flow_quality_assurance.py"),
        },
    }
    (metrics_dir / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2))

    print("flow_quality_assurance build complete")


if __name__ == "__main__":
    main()
