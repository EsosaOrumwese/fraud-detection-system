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
    / r"artefacts\analytics_slices\data_analyst\huc\03_conversion_discrepancy_handling"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

UPSTREAM = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\huc\01_multi_source_service_performance"
)
UPSTREAM_KPIS = UPSTREAM / "extracts" / "service_line_kpis_v1.parquet"
UPSTREAM_FACT_PACK = UPSTREAM / "metrics" / "execution_fact_pack.json"

DISCREPANCY_OUT = EXTRACTS_DIR / "conversion_discrepancy_summary_v1.parquet"
BEFORE_AFTER_OUT = EXTRACTS_DIR / "conversion_before_after_kpi_v1.parquet"
RELEASE_CHECKS_OUT = EXTRACTS_DIR / "conversion_release_checks_v1.parquet"


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
    json_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def sql_path(path: Path) -> str:
    return f"'{str(path).replace(chr(92), '/')}'"


def render_sql(sql_text: str, replacements: dict[str, str]) -> str:
    rendered = sql_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def copy_upstream_log() -> None:
    if UPSTREAM_FACT_PACK.exists():
        LOGS_DIR.joinpath("upstream_fact_pack_snapshot.json").write_text(
            UPSTREAM_FACT_PACK.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def main() -> None:
    start = time.perf_counter()
    sns.set_theme(style="whitegrid", context="talk")
    copy_upstream_log()

    con = duckdb.connect()
    replacements = {
        "$kpi_path": sql_path(UPSTREAM_KPIS),
        "$discrepancy_path": sql_path(DISCREPANCY_OUT),
        "$before_after_path": sql_path(BEFORE_AFTER_OUT),
        "$output_path": sql_path(DISCREPANCY_OUT),
    }
    con.execute(render_sql(read_sql("01_build_conversion_discrepancy_summary.sql"), replacements))

    replacements["$output_path"] = sql_path(BEFORE_AFTER_OUT)
    con.execute(render_sql(read_sql("02_build_conversion_before_after_kpi.sql"), replacements))

    replacements["$output_path"] = sql_path(RELEASE_CHECKS_OUT)
    con.execute(render_sql(read_sql("03_build_conversion_release_checks.sql"), replacements))

    discrepancy_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(DISCREPANCY_OUT)}) ORDER BY week_role"
    ).df()
    before_after_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(BEFORE_AFTER_OUT)}) ORDER BY week_role, metric_version"
    ).df()
    release_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RELEASE_CHECKS_OUT)})"
    ).df()

    write_frame_outputs(
        discrepancy_df,
        METRICS_DIR / "01_conversion_discrepancy_summary.csv",
        METRICS_DIR / "01_conversion_discrepancy_summary.json",
    )
    write_frame_outputs(
        before_after_df,
        METRICS_DIR / "02_conversion_before_after_kpi.csv",
        METRICS_DIR / "02_conversion_before_after_kpi.json",
    )
    write_frame_outputs(
        release_df,
        METRICS_DIR / "03_conversion_release_checks.csv",
        METRICS_DIR / "03_conversion_release_checks.json",
    )

    current_row = discrepancy_df.loc[discrepancy_df["week_role"] == "current"].iloc[0]
    prior_row = discrepancy_df.loc[discrepancy_df["week_role"] == "prior"].iloc[0]
    release_pass_count = int(release_df["passed_flag"].sum())
    release_check_count = int(len(release_df))

    write_md(
        ARTEFACT / "conversion_discrepancy_source_map_v1.md",
        """
        # Conversion Discrepancy Source Map v1

        Compared reporting views:
        - view A: service-line KPI view using `flow_rows` as the conversion denominator
        - view B: linked reporting interpretation that normalises the same case-open count by `entry_event_rows`

        Source path:
        - event source contributes workflow-entry pressure
        - flow source defines the analytical `flow_id` denominator
        - case-open conversion should therefore be a flow-to-case KPI, not an event-to-case KPI

        Why the views should align:
        - both are intended to describe suspicious-to-case conversion inside the same weekly reporting lane
        - the only legitimate conversion denominator for this KPI is `flow_rows`
        """,
    )

    write_md(
        ARTEFACT / "conversion_discrepancy_source_rules_v1.md",
        """
        # Conversion Discrepancy Source Rules v1

        Authoritative conversion definition:
        - numerator: case-opened flows
        - denominator: total flows in the reporting window

        Comparison-only interpretation that must not be used as KPI authority:
        - case-opened flows divided by entry events

        Reason:
        - entry events are not the same analytical unit as flows
        - using event rows as the denominator halves the apparent conversion rate in this bounded lane
        """,
    )

    write_md(
        ARTEFACT / "conversion_discrepancy_lineage_v1.md",
        """
        # Conversion Discrepancy Lineage v1

        Reporting lineage:
        - bounded weekly service-line KPI summary
        - derived case-open count
        - conversion reported in two linked views

        Control problem:
        - one linked view preserved the correct flow-based denominator
        - one linked interpretation reused the same numerator against event-entry volume

        Corrected lineage rule:
        - suspicious-to-case conversion must remain a flow-normalised KPI in all reporting surfaces
        """,
    )

    write_md(
        ARTEFACT / "conversion_discrepancy_issue_log_v1.md",
        f"""
        # Conversion Discrepancy Issue Log v1

        Issue:
        - suspicious-to-case conversion did not align across two linked weekly reporting views

        Affected KPI:
        - suspicious-to-case conversion

        Current-week discrepancy:
        - corrected flow-based conversion: {short_pct(float(current_row['corrected_flow_conversion_rate']))}
        - discrepant event-normalized conversion: {short_pct(float(current_row['discrepant_conversion_rate']))}
        - absolute gap: {short_pct(float(current_row['absolute_gap']))}

        Likely root cause:
        - numerator was reused correctly, but denominator drifted from `flow_rows` to `entry_event_rows`

        Severity:
        - high, because the discrepant view makes weekly conversion look materially weaker than it really is

        Immediate corrective action:
        - keep `flow_rows` as the only allowed denominator for suspicious-to-case conversion

        Long-term control:
        - add a release check that compares the corrected flow-based rate to any linked reporting view before pack release
        """,
    )

    write_md(
        ARTEFACT / "conversion_operational_impact_v1.md",
        f"""
        # Conversion Operational Impact v1

        What the discrepant view would have implied:
        - current weekly conversion would have been read as {short_pct(float(current_row['discrepant_conversion_rate']))} instead of {short_pct(float(current_row['corrected_flow_conversion_rate']))}

        Why that matters:
        - it would suggest false deterioration in suspicious-to-case conversion
        - it would make weekly pressure look less productive than it actually was
        - it could misdirect operational attention toward a conversion problem that was mostly denominator logic

        Corrected reading:
        - current conversion is stable at {short_pct(float(current_row['corrected_flow_conversion_rate']))}
        - the reporting issue is control failure, not a sudden workflow collapse
        """,
    )

    write_md(
        ARTEFACT / "conversion_intervention_note_v1.md",
        """
        # Conversion Intervention Note v1

        What should now be monitored:
        - any reporting view that uses entry-event volume in a conversion context
        - any weekly pack where conversion drops sharply without similar movement in case-opened counts

        Immediate follow-up:
        - keep the conversion KPI definition sheet attached to the recurring reporting cycle
        - require discrepancy review before releasing the weekly pack when conversion views are updated
        """,
    )

    write_md(
        ARTEFACT / "conversion_kpi_definition_note_v1.md",
        """
        # Conversion KPI Definition Note v1

        KPI:
        - suspicious-to-case conversion

        Correct definition:
        - numerator: case-opened flows
        - denominator: total flows in the weekly reporting window

        Not allowed:
        - using entry-event volume as the denominator for this KPI

        Why:
        - the KPI describes flow-to-case movement, not event-to-case movement
        """,
    )

    write_md(
        ARTEFACT / "conversion_drillthrough_note_v1.md",
        f"""
        # Conversion Drill-Through Note v1

        Weekly discrepancy reading:
        - prior corrected conversion: {short_pct(float(prior_row['corrected_flow_conversion_rate']))}
        - prior discrepant conversion: {short_pct(float(prior_row['discrepant_conversion_rate']))}
        - current corrected conversion: {short_pct(float(current_row['corrected_flow_conversion_rate']))}
        - current discrepant conversion: {short_pct(float(current_row['discrepant_conversion_rate']))}

        Corrected interpretation:
        - conversion remained broadly stable across weeks
        - the apparent drop came from denominator drift, not true operational collapse
        """,
    )

    write_md(
        ARTEFACT / "README_conversion_anomaly_checks.md",
        """
        # README - Conversion Anomaly Checks

        Regeneration entrypoint:
        - `python artefacts/analytics_slices/data_analyst/huc/03_conversion_discrepancy_handling/models/build_conversion_discrepancy_handling.py`

        Inputs:
        - compact weekly KPI output from HUC slice 1

        Regeneration posture:
        - this slice does not read the full merged service-line base into memory
        - it derives the discrepancy from compact reporting-ready KPI inputs only

        Outputs:
        - discrepancy summary
        - before-and-after KPI view
        - release checks
        - compact two-page exception pack
        - figures
        - issue, caveat, and rerun-control notes
        """,
    )

    write_md(
        ARTEFACT / "conversion_report_run_checklist_v1.md",
        """
        # Conversion Report Run Checklist v1

        Before release:
        - confirm suspicious-to-case conversion uses `flow_rows` as denominator
        - compare any linked conversion view against the authoritative flow-based rate
        - review the discrepancy summary for a material gap

        Trigger for review:
        - absolute conversion gap at or above 1 percentage point

        Required release checks:
        - two period rows present
        - material gap check executed
        - before-and-after KPI view refreshed
        """,
    )

    write_md(
        ARTEFACT / "conversion_reporting_caveats_v1.md",
        """
        # Conversion Reporting Caveats v1

        Main caveat:
        - suspicious-to-case conversion is a flow-based KPI
        - entry-event volume may be useful as pressure context, but it must not replace the flow denominator for conversion

        Comparability caveat:
        - any future change to numerator or denominator logic should be recorded before periods are compared
        """,
    )

    write_md(
        ARTEFACT / "CHANGELOG_conversion_reporting.md",
        """
        # CHANGELOG - Conversion Reporting

        Version `v1`:
        - identified a suspicious-to-case conversion discrepancy across linked reporting views
        - traced the mismatch to denominator drift from `flow_rows` to `entry_event_rows`
        - fixed the KPI authority rule and added a recurring discrepancy control
        """,
    )

    fig, ax = plt.subplots(1, 1, figsize=(9.8, 6.2))
    summary_plot = before_after_df.loc[
        before_after_df["metric_version"].isin(
            ["original_discrepant_view", "corrected_flow_view"]
        )
    ].copy()
    summary_plot["metric_label"] = summary_plot["metric_version"].map(
        {
            "original_discrepant_view": "Original discrepant",
            "corrected_flow_view": "Corrected flow-based",
        }
    )
    sns.barplot(
        data=summary_plot,
        x="metric_label",
        y="conversion_rate",
        hue="week_role",
        palette=["#9fc5e8", "#3d85c6"],
        ax=ax,
    )
    ax.set_title("Corrected vs Discrepant Conversion")
    ax.set_xlabel("")
    ax.set_ylabel("Conversion rate")
    ax.legend(title="", loc="upper right", fontsize=10)
    for container in ax.containers:
        ax.bar_label(
            container,
            labels=[short_pct(v) for v in container.datavalues],
            padding=3,
            fontsize=9,
        )
    fig.suptitle("Figure 1 - Conversion Discrepancy Summary", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "conversion_discrepancy_summary.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.2), gridspec_kw={"width_ratios": [1.0, 1.0]})
    line_df = discrepancy_df.copy()
    x_positions = list(range(len(line_df)))
    axes[0].hlines(
        y=x_positions,
        xmin=line_df["discrepant_conversion_rate"],
        xmax=line_df["corrected_flow_conversion_rate"],
        color="#b7b7b7",
        linewidth=3,
        alpha=0.9,
    )
    axes[0].scatter(
        line_df["discrepant_conversion_rate"],
        x_positions,
        color="#e69138",
        s=220,
        label="Discrepant view",
        zorder=3,
    )
    axes[0].scatter(
        line_df["corrected_flow_conversion_rate"],
        x_positions,
        color="#3d85c6",
        s=220,
        label="Corrected view",
        zorder=3,
    )
    axes[0].set_yticks(x_positions)
    axes[0].set_yticklabels(line_df["week_role"])
    axes[0].set_xlim(0.04, 0.105)
    axes[0].set_title("Where the Reporting Views Diverged")
    axes[0].set_xlabel("Conversion rate")
    axes[0].set_ylabel("Week")
    axes[0].legend(title="", loc="lower right", fontsize=10)
    for idx, row in line_df.iterrows():
        axes[0].text(
            float(row["corrected_flow_conversion_rate"]) + 0.0015,
            idx,
            f"{short_pct(float(row['discrepant_conversion_rate']))} -> {short_pct(float(row['corrected_flow_conversion_rate']))}",
            fontsize=8.5,
            va="center",
        )

    denominator_plot = pd.DataFrame(
        {
            "week_role": ["current", "current", "prior", "prior"],
            "denominator": [
                "Authoritative flow denominator",
                "Event-row denominator",
                "Authoritative flow denominator",
                "Event-row denominator",
            ],
            "rows_millions": [
                float(current_row["flow_rows"]) / 1_000_000,
                float(current_row["entry_event_rows"]) / 1_000_000,
                float(prior_row["flow_rows"]) / 1_000_000,
                float(prior_row["entry_event_rows"]) / 1_000_000,
            ],
        }
    )
    sns.barplot(
        data=denominator_plot,
        x="week_role",
        y="rows_millions",
        hue="denominator",
        palette=["#3d85c6", "#e69138"],
        ax=axes[1],
    )
    axes[1].set_title("Denominator Drift That Caused the Gap")
    axes[1].set_xlabel("Week")
    axes[1].set_ylabel("Rows (millions)")
    axes[1].legend(title="", loc="best", fontsize=10)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[f"{v:.2f}M" for v in container.datavalues], padding=3, fontsize=8.5)
    fig.suptitle("Figure 2 - Root Cause and Corrected Interpretation", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "conversion_root_cause_and_correction.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    write_md(
        ARTEFACT / "conversion_exception_pack_v1.md",
        """
        # Conversion Exception Pack v1

        This pack operationalises one anomaly-to-resolution cycle for suspicious-to-case conversion through two complementary evidence figures.

        ## Figure 1 - Conversion Discrepancy Summary

        ![Conversion discrepancy summary](figures/conversion_discrepancy_summary.png)

        ## Figure 2 - Root Cause and Corrected Interpretation

        ![Conversion root cause and correction](figures/conversion_root_cause_and_correction.png)
        """,
    )

    duration_seconds = time.perf_counter() - start
    fact_pack = {
        "slice": "huc/03_conversion_discrepancy_handling",
        "kpi": "suspicious_to_case_conversion",
        "current_corrected_conversion_rate": float(current_row["corrected_flow_conversion_rate"]),
        "current_discrepant_conversion_rate": float(current_row["discrepant_conversion_rate"]),
        "current_absolute_gap": float(current_row["absolute_gap"]),
        "prior_corrected_conversion_rate": float(prior_row["corrected_flow_conversion_rate"]),
        "prior_discrepant_conversion_rate": float(prior_row["discrepant_conversion_rate"]),
        "prior_absolute_gap": float(prior_row["absolute_gap"]),
        "current_case_opened_rows": int(round(float(current_row["case_opened_rows"]))),
        "release_checks_passed": release_pass_count,
        "release_check_count": release_check_count,
        "regeneration_seconds": round(duration_seconds, 2),
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2),
        encoding="utf-8",
    )

    (FIGURES_DIR / "figure_manifest.json").write_text(
        json.dumps(
            {
                "generated_figures": [
                    "conversion_discrepancy_summary.png",
                    "conversion_root_cause_and_correction.png",
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    for stale_name in [
        "conversion_exception_summary.png",
        "conversion_drillthrough_and_explanation.png",
    ]:
        stale_path = FIGURES_DIR / stale_name
        if stale_path.exists():
            stale_path.unlink()

    print("conversion_discrepancy_handling build complete")


if __name__ == "__main__":
    main()
