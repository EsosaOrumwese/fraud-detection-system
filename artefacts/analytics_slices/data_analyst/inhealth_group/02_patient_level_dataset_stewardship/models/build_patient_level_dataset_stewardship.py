from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


BASE = Path(
    r"C:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system"
)
ARTEFACT = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\02_patient_level_dataset_stewardship"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
FIGURES_DIR = ARTEFACT / "figures"

RUN_BASE = (
    BASE
    / r"runs\local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1\data\layer3\6B"
)

FLOW_PATH = RUN_BASE / "s2_flow_anchor_baseline_6B"
CASE_PATH = RUN_BASE / "s4_case_timeline_6B"
TRUTH_PATH = RUN_BASE / "s4_flow_truth_labels_6B"

REPORTING_SUPPORT_BASE = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\01_reporting_support_for_operational_and_regional_teams"
)
MONTH_BAND_AGG_PATH = (
    REPORTING_SUPPORT_BASE / "extracts" / "programme_month_band_agg_v1.parquet"
)

CURRENT_MONTH = "2026-03-01"

SOURCE_PROFILE = EXTRACTS_DIR / "patient_level_source_profile_v1.parquet"
REPORTING_DATASET = EXTRACTS_DIR / "patient_level_reporting_dataset_v1.parquet"
VALIDATION_CHECKS = EXTRACTS_DIR / "patient_level_validation_checks_v1.parquet"
SAFE_SUMMARY = EXTRACTS_DIR / "patient_level_reporting_safe_summary_v1.parquet"
RECONCILIATION = EXTRACTS_DIR / "patient_level_reconciliation_checks_v1.parquet"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def short_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def comma(value: float) -> str:
    return f"{int(round(value)):,}"


def write_md(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def write_frame_outputs(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    df.to_csv(csv_path, index=False)
    json_path.write_text(
        df.to_json(orient="records", indent=2, date_format="iso"),
        encoding="utf-8",
    )


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def sql_path(path: Path) -> str:
    return f"'{str(path).replace(chr(92), '/')}'"


def render_sql(sql_text: str, replacements: dict[str, str]) -> str:
    rendered = sql_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def short_band(value: str) -> str:
    mapping = {
        "under_10": "<10",
        "10_to_25": "10-25",
        "25_to_50": "25-50",
        "50_plus": "50+",
        "__overall__": "Overall",
    }
    return mapping.get(value, value)


def month_label(value: str) -> str:
    return pd.to_datetime(value).strftime("%b %Y")


def main() -> None:
    start = time.perf_counter()
    sns.set_theme(style="whitegrid", context="talk")

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")

    replacements = {
        "$flow_path": sql_path(FLOW_PATH),
        "$case_path": sql_path(CASE_PATH),
        "$truth_path": sql_path(TRUTH_PATH),
        "$current_month": CURRENT_MONTH,
        "$output_path": sql_path(SOURCE_PROFILE),
    }
    con.execute(
        render_sql(read_sql("01_build_patient_level_source_profile.sql"), replacements)
    )

    replacements = {
        "$flow_path": sql_path(FLOW_PATH),
        "$case_path": sql_path(CASE_PATH),
        "$truth_path": sql_path(TRUTH_PATH),
        "$current_month": CURRENT_MONTH,
        "$output_path": sql_path(REPORTING_DATASET),
    }
    con.execute(
        render_sql(read_sql("02_build_patient_level_reporting_dataset.sql"), replacements)
    )

    replacements = {
        "$flow_path": sql_path(FLOW_PATH),
        "$truth_path": sql_path(TRUTH_PATH),
        "$current_month": CURRENT_MONTH,
        "$dataset_path": sql_path(REPORTING_DATASET),
        "$output_path": sql_path(VALIDATION_CHECKS),
    }
    con.execute(
        render_sql(read_sql("03_build_patient_level_validation_checks.sql"), replacements)
    )

    replacements = {
        "$flow_path": sql_path(FLOW_PATH),
        "$current_month": CURRENT_MONTH,
        "$dataset_path": sql_path(REPORTING_DATASET),
        "$output_path": sql_path(SAFE_SUMMARY),
    }
    con.execute(
        render_sql(
            read_sql("04_build_patient_level_reporting_safe_summary.sql"), replacements
        )
    )

    replacements = {
        "$safe_summary_path": sql_path(SAFE_SUMMARY),
        "$month_band_agg_path": sql_path(MONTH_BAND_AGG_PATH),
        "$output_path": sql_path(RECONCILIATION),
    }
    con.execute(
        render_sql(
            read_sql("05_build_patient_level_reconciliation_checks.sql"), replacements
        )
    )

    source_profile_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(SOURCE_PROFILE)})"
    ).df()
    validation_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(VALIDATION_CHECKS)})"
    ).df()
    safe_summary_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(SAFE_SUMMARY)})"
    ).df()
    reconciliation_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RECONCILIATION)})"
    ).df()

    dataset_metrics_df = con.execute(
        f"""
        SELECT
            COUNT(*) AS maintained_rows,
            COUNT(DISTINCT flow_id) AS distinct_flow_id,
            COUNT(DISTINCT case_id) AS distinct_case_id,
            AVG(CAST(raw_case_event_rows AS DOUBLE)) AS avg_raw_case_event_rows,
            MAX(raw_case_event_rows) AS max_raw_case_event_rows
        FROM read_parquet({sql_path(REPORTING_DATASET)})
        """
    ).df()

    overall_profile = source_profile_df.loc[
        source_profile_df["amount_band"] == "__overall__"
    ].iloc[0]
    band_profile_df = source_profile_df.loc[
        source_profile_df["amount_band"] != "__overall__"
    ].copy()
    band_profile_df["label"] = band_profile_df["amount_band"].map(short_band)
    band_profile_df["duplication_factor"] = (
        band_profile_df["raw_case_event_rows_on_linked_flows"]
        / band_profile_df["case_linked_rows"].replace({0: pd.NA})
    )

    safe_band_df = safe_summary_df.loc[safe_summary_df["amount_band"] != "__overall__"].copy()
    safe_band_df["label"] = safe_band_df["amount_band"].map(short_band)
    overall_safe = safe_summary_df.loc[safe_summary_df["amount_band"] == "__overall__"].iloc[0]
    dataset_metrics = dataset_metrics_df.iloc[0]

    write_frame_outputs(
        source_profile_df,
        METRICS_DIR / "00_patient_level_source_profile.csv",
        METRICS_DIR / "00_patient_level_source_profile.json",
    )
    write_frame_outputs(
        validation_df,
        METRICS_DIR / "01_patient_level_validation_checks.csv",
        METRICS_DIR / "01_patient_level_validation_checks.json",
    )
    write_frame_outputs(
        safe_summary_df,
        METRICS_DIR / "02_patient_level_reporting_safe_summary.csv",
        METRICS_DIR / "02_patient_level_reporting_safe_summary.json",
    )
    write_frame_outputs(
        reconciliation_df,
        METRICS_DIR / "03_patient_level_reconciliation_checks.csv",
        METRICS_DIR / "03_patient_level_reconciliation_checks.json",
    )
    write_frame_outputs(
        dataset_metrics_df,
        METRICS_DIR / "04_patient_level_dataset_metrics.csv",
        METRICS_DIR / "04_patient_level_dataset_metrics.json",
    )

    current_month_name = month_label(CURRENT_MONTH)
    regeneration_seconds = time.perf_counter() - start

    fact_pack = {
        "slice": "inhealth_group/02_patient_level_dataset_stewardship",
        "current_month": CURRENT_MONTH,
        "maintained_dataset_rows": int(dataset_metrics["maintained_rows"]),
        "distinct_flow_id": int(dataset_metrics["distinct_flow_id"]),
        "distinct_case_id": int(dataset_metrics["distinct_case_id"]),
        "march_flow_rows": int(overall_profile["flow_rows"]),
        "case_linked_rows": int(overall_profile["case_linked_rows"]),
        "case_opened_rows": int(overall_profile["case_opened_rows"]),
        "raw_case_event_rows_on_linked_flows": int(
            overall_profile["raw_case_event_rows_on_linked_flows"]
        ),
        "avg_case_event_rows_when_linked": float(
            overall_profile["avg_case_event_rows_when_linked"]
        ),
        "overall_case_open_rate": float(overall_safe["case_open_rate"]),
        "overall_case_truth_rate": float(overall_safe["case_truth_rate"]),
        "validation_checks_passed": int(validation_df["passed_flag"].sum()),
        "validation_check_count": int(len(validation_df)),
        "reconciliation_matches": int(reconciliation_df["matched_flag"].sum()),
        "reconciliation_count": int(len(reconciliation_df)),
        "regeneration_seconds": regeneration_seconds,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )

    write_md(
        ARTEFACT / "patient_level_dataset_source_map_v1.md",
        f"""
        # Patient-Level Dataset Source Map v1

        Bounded stewardship window:
        - `{current_month_name}`

        Maintained detailed dataset grain:
        - one row per `flow_id` where the bounded monthly flow converted into a case-opened record

        Source responsibilities:
        - `s2_flow_anchor_baseline_6B`
          - authoritative for `flow_id`, `flow_ts_utc`, `amount`, `merchant_id`, `party_id`
        - `s4_case_timeline_6B`
          - authoritative for `case_id`
          - not safe to join directly because it is event-grain rather than maintained reporting grain
        - `s4_flow_truth_labels_6B`
          - authoritative for `is_fraud_truth` and `fraud_label`

        Maintained join path:
        - flow-month slice first
        - case timeline rolled to one row per `flow_id`
        - truth labels joined at `flow_id`
        """,
    )

    write_md(
        ARTEFACT / "patient_level_dataset_field_authority_v1.md",
        f"""
        # Patient-Level Dataset Field Authority v1

        Maintained reporting dataset fields:
        - `flow_id`: authoritative from flow anchor
        - `flow_ts_utc`: authoritative from flow anchor
        - `amount`: authoritative from flow anchor
        - `amount_band`: derived from authoritative `amount`
        - `merchant_id`: authoritative from flow anchor
        - `party_id`: authoritative from flow anchor
        - `case_id`: authoritative from rolled case timeline
        - `raw_case_event_rows`: control field from rolled case timeline used to prove why event-grain joins are unsafe
        - `case_opened_flag`: maintained dataset inclusion rule, fixed to `1`
        - `is_fraud_truth`: authoritative from truth labels
        - `fraud_label`: authoritative from truth labels

        Core stewardship rule:
        - event-grain case rows are not reporting-safe
        - the maintained dataset only admits one rolled case state per `flow_id`
        """,
    )

    write_md(
        ARTEFACT / "patient_level_dataset_issue_note_v1.md",
        f"""
        # Patient-Level Dataset Issue Note v1

        Trust risk identified:
        - the case surface is event-grain, not maintained reporting grain

        Why this matters:
        - `{comma(float(overall_profile["case_linked_rows"]))}` March flows linked to case activity
        - those linked flows carry `{comma(float(overall_profile["raw_case_event_rows_on_linked_flows"]))}` raw case-event rows
        - that is an average of `{float(overall_profile["avg_case_event_rows_when_linked"]):.2f}` raw case-event rows per linked flow

        Control applied:
        - rolled the case timeline to one row per `flow_id` before joining it into the maintained detailed dataset

        Reporting protection consequence:
        - downstream monthly reporting can now use one maintained detailed dataset without event-grain duplication inflating case-linked counts
        """,
    )

    write_md(
        ARTEFACT / "patient_level_reporting_protection_note_v1.md",
        f"""
        # Patient-Level Reporting Protection Note v1

        Protected downstream use:
        - current-month reporting-safe summary for the InHealth `3.A` reporting lane

        Protection result:
        - the maintained dataset reproduces the current-month reporting lane exactly across `{int(reconciliation_df["matched_flag"].sum())}/{len(reconciliation_df)}` amount bands
        - overall protected case-open rate: `{pct(float(overall_safe["case_open_rate"]))}`
        - overall protected truth quality: `{pct(float(overall_safe["case_truth_rate"]))}`

        Why the maintained dataset matters:
        - a direct join to the raw case timeline would work at the wrong grain
        - the maintained dataset protects reporting by admitting one controlled case state per monthly flow record
        """,
    )

    write_md(
        ARTEFACT / "patient_level_dataset_maintenance_checklist_v1.md",
        f"""
        # Patient-Level Dataset Maintenance Checklist v1

        1. Confirm the stewardship window is bounded to `{current_month_name}`.
        2. Run source profiling before any maintained dataset build.
        3. Confirm monthly `flow_id` remains unique at the bounded flow grain.
        4. Confirm truth labels remain unique at `flow_id`.
        5. Roll the case timeline to one row per `flow_id` before joining.
        6. Confirm the maintained dataset contains only `case_opened_flag = 1` rows.
        7. Confirm required maintained fields are complete.
        8. Confirm the protected reporting-safe summary matches the InHealth `3.A` reporting lane before issuing downstream claims.
        """,
    )

    write_md(
        ARTEFACT / "patient_level_dataset_caveats_v1.md",
        f"""
        # Patient-Level Dataset Caveats v1

        This slice is intentionally bounded:
        - one month only: `{current_month_name}`
        - one programme-style lane only
        - one maintained detailed dataset only: case-opened monthly flow records

        This slice proves:
        - careful maintenance of a detailed reporting dataset
        - validation and reconciliation logic around the maintained grain
        - protected downstream reporting from the maintained dataset

        This slice does not prove:
        - broad healthcare patient-record stewardship
        - a full multi-month detailed data-management programme
        - all possible downstream reporting uses
        """,
    )

    write_md(
        ARTEFACT / "README_patient_level_dataset_regeneration.md",
        f"""
        # Patient-Level Dataset Regeneration README

        Regeneration posture:
        - heavy work stays in `DuckDB`
        - raw parquet is scanned only through bounded SQL
        - Python reads only compact outputs after SQL reduction

        Bounded window:
        - `{current_month_name}`

        Regenerated outputs:
        - `patient_level_source_profile_v1.parquet`
        - `patient_level_reporting_dataset_v1.parquet`
        - `patient_level_validation_checks_v1.parquet`
        - `patient_level_reporting_safe_summary_v1.parquet`
        - `patient_level_reconciliation_checks_v1.parquet`
        """,
    )

    # Figure 1: raw event-join risk
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    overall_bars = pd.DataFrame(
        {
            "stage": [
                "Linked monthly flows",
                "Raw case-event rows on linked flows",
                "Maintained rows (1 per linked flow)",
            ],
            "rows": [
                float(overall_profile["case_linked_rows"]),
                float(overall_profile["raw_case_event_rows_on_linked_flows"]),
                float(dataset_metrics["maintained_rows"]),
            ],
        }
    )
    axes[0].bar(
        overall_bars["stage"],
        overall_bars["rows"],
        color=["#AAB7C4", "#D95F5F", "#2E5B88"],
    )
    axes[0].ticklabel_format(style="plain", axis="y")
    axes[0].set_title("Why The Raw Event-Grain Join Is Unsafe")
    axes[0].set_ylabel("Rows")
    axes[0].tick_params(axis="x", rotation=18)
    axes[0].annotate(
        f"March monthly flow rows: {comma(float(overall_profile['flow_rows']))}\nComparison here is the linked subset only.",
        xy=(0.02, 0.96),
        xycoords="axes fraction",
        ha="left",
        va="top",
        fontsize=10,
        color="#444444",
    )

    axes[1].barh(
        band_profile_df["label"],
        band_profile_df["duplication_factor"],
        color=[
            "#D95F5F" if band == "50+" else "#7A8FA6"
            for band in band_profile_df["label"]
        ],
    )
    axes[1].set_title("Raw Event Rows Per Linked Flow")
    axes[1].set_xlabel("Average raw case-event rows")
    axes[1].invert_yaxis()

    fig.suptitle(f"Detailed Dataset Trust Posture: {current_month_name}", fontsize=16, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "raw_case_event_join_risk.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: protected downstream summary
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].bar(
        safe_band_df["label"],
        safe_band_df["case_open_rate"] * 100,
        color=["#AAB7C4", "#AAB7C4", "#AAB7C4", "#D95F5F"],
    )
    axes[0].set_title("Protected Case-Open Rate By Band")
    axes[0].set_ylabel("Case-open rate (%)")

    axes[1].plot(
        safe_band_df["label"],
        safe_band_df["case_truth_rate"] * 100,
        marker="o",
        linewidth=2.5,
        color="#2E5B88",
    )
    axes[1].set_title("Protected Truth Quality By Band")
    axes[1].set_ylabel("Truth quality (%)")
    axes[1].annotate(
        f"{int(reconciliation_df['matched_flag'].sum())}/{len(reconciliation_df)} bands matched current reporting lane",
        xy=(0.02, 0.02),
        xycoords="axes fraction",
        fontsize=10,
        color="#444444",
    )

    fig.suptitle("Maintained Dataset Reporting Protection", fontsize=16, y=1.02)
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "maintained_dataset_reporting_protection.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)

    figure_manifest = {
        "figures": [
            {
                "file": "raw_case_event_join_risk.png",
                "purpose": "show why the raw case timeline must be rolled before joining into a detailed reporting dataset",
            },
            {
                "file": "maintained_dataset_reporting_protection.png",
                "purpose": "show the protected downstream monthly rates derived from the maintained dataset and note exact reconciliation to the InHealth 3.A reporting lane",
            },
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(
        json.dumps(figure_manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
