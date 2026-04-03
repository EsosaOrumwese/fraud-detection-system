from __future__ import annotations

import json
import shutil
import textwrap
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
    / r"artefacts\analytics_slices\data_analyst\huc\01_multi_source_service_performance"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

RUN_BASE = (
    BASE
    / r"runs\local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1\data\layer3\6B"
)
UPSTREAM_BOUNDED_LOG = (
    BASE
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\05_governed_explainable_ai\logs\bounded_file_selection.json"
)

SERVICE_LINE_BASE = EXTRACTS_DIR / "service_line_performance_base_v1.parquet"
SERVICE_LINE_KPIS = EXTRACTS_DIR / "service_line_kpis_v1.parquet"
SERVICE_LINE_SEGMENTS = EXTRACTS_DIR / "service_line_segment_summary_v1.parquet"
SERVICE_LINE_DISCREPANCY = EXTRACTS_DIR / "service_line_discrepancy_summary_v1.parquet"

PRIOR_WEEK = "2026-03-16 00:00:00"
CURRENT_WEEK = "2026-03-23 00:00:00"
ANALYSIS_END = "2026-03-31 23:59:59"


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
    json_path.write_text(df.to_json(orient="records", indent=2, date_format="iso"), encoding="utf-8")


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
    }
    return mapping.get(value, value)


def short_stage(value: str) -> str:
    mapping = {
        "opened_only": "opened_only",
        "chargeback_decision": "chargeback_dec",
        "customer_dispute": "cust_dispute",
        "detection_event_attached": "det_event",
        "no_case": "no_case",
    }
    return mapping.get(value, value)


def metric_delta(current: float, prior: float, scale: str = "pp") -> str:
    if scale == "pct":
        return pct((current / prior) - 1) if prior else "n/a"
    return f"{(current - prior) * 100:.2f} pp"


def main() -> None:
    sns.set_theme(style="whitegrid", context="talk")

    if UPSTREAM_BOUNDED_LOG.exists():
        shutil.copy2(UPSTREAM_BOUNDED_LOG, LOGS_DIR / "bounded_file_selection.json")

    replacements = {
        "$flow_path": sql_path(RUN_BASE / "s2_flow_anchor_baseline_6B"),
        "$event_path": sql_path(RUN_BASE / "s2_event_stream_baseline_6B"),
        "$case_path": sql_path(RUN_BASE / "s4_case_timeline_6B"),
        "$truth_path": sql_path(RUN_BASE / "s4_flow_truth_labels_6B"),
        "$bank_path": sql_path(RUN_BASE / "s4_flow_bank_view_6B"),
        "$service_line_base_output": sql_path(SERVICE_LINE_BASE),
        "$service_line_base_path": sql_path(SERVICE_LINE_BASE),
        "$service_line_kpis_output": sql_path(SERVICE_LINE_KPIS),
        "$service_line_segment_output": sql_path(SERVICE_LINE_SEGMENTS),
        "$service_line_discrepancy_output": sql_path(SERVICE_LINE_DISCREPANCY),
        "$prior_week": PRIOR_WEEK,
        "$current_week": CURRENT_WEEK,
        "$analysis_end": ANALYSIS_END,
    }

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")

    for sql_name in [
        "01_build_service_line_performance_base.sql",
        "02_build_service_line_kpis.sql",
        "03_build_service_line_segment_summary.sql",
        "04_build_service_line_discrepancy_summary.sql",
    ]:
        con.execute(render_sql(read_sql(sql_name), replacements))

    kpi_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(SERVICE_LINE_KPIS)}) ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END"
    ).fetchdf()
    segment_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(SERVICE_LINE_SEGMENTS)}) ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END, amount_band"
    ).fetchdf()
    discrepancy_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(SERVICE_LINE_DISCREPANCY)}) ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END"
    ).fetchdf()

    input_profile_df = con.execute(
        f"""
        SELECT 'event_stream' AS input_name, COUNT(*) AS rows FROM parquet_scan({sql_path(RUN_BASE / "s2_event_stream_baseline_6B")})
        UNION ALL
        SELECT 'flow_anchor', COUNT(*) FROM parquet_scan({sql_path(RUN_BASE / "s2_flow_anchor_baseline_6B")})
        UNION ALL
        SELECT 'case_timeline', COUNT(*) FROM parquet_scan({sql_path(RUN_BASE / "s4_case_timeline_6B")})
        UNION ALL
        SELECT 'flow_truth', COUNT(*) FROM parquet_scan({sql_path(RUN_BASE / "s4_flow_truth_labels_6B")})
        UNION ALL
        SELECT 'flow_bank_view', COUNT(*) FROM parquet_scan({sql_path(RUN_BASE / "s4_flow_bank_view_6B")})
        """
    ).fetchdf()
    write_frame_outputs(
        input_profile_df,
        METRICS_DIR / "01_service_line_input_profile.csv",
        METRICS_DIR / "01_service_line_input_profile.json",
    )

    output_profile_df = pd.DataFrame(
        [
            {
                "output_name": "service_line_performance_base_v1",
                "rows": int(con.execute(f"SELECT COUNT(*) FROM parquet_scan({sql_path(SERVICE_LINE_BASE)})").fetchone()[0]),
            },
            {"output_name": "service_line_kpis_v1", "rows": len(kpi_df)},
            {"output_name": "service_line_segment_summary_v1", "rows": len(segment_df)},
            {"output_name": "service_line_discrepancy_summary_v1", "rows": len(discrepancy_df)},
        ]
    )
    write_frame_outputs(
        output_profile_df,
        METRICS_DIR / "02_service_line_output_profile.csv",
        METRICS_DIR / "02_service_line_output_profile.json",
    )
    write_frame_outputs(
        kpi_df,
        METRICS_DIR / "03_service_line_kpis.csv",
        METRICS_DIR / "03_service_line_kpis.json",
    )
    write_frame_outputs(
        segment_df,
        METRICS_DIR / "04_service_line_segment_summary.csv",
        METRICS_DIR / "04_service_line_segment_summary.json",
    )
    write_frame_outputs(
        discrepancy_df,
        METRICS_DIR / "05_service_line_discrepancy_summary.csv",
        METRICS_DIR / "05_service_line_discrepancy_summary.json",
    )

    stage_df = con.execute(
        f"""
        SELECT
            week_role,
            pathway_stage,
            COUNT(*) AS flow_rows,
            AVG(CASE WHEN has_case_opened = 1 THEN CAST(is_fraud_truth AS DOUBLE) END) AS fraud_truth_rate
        FROM parquet_scan({sql_path(SERVICE_LINE_BASE)})
        WHERE has_case_opened = 1
        GROUP BY week_role, pathway_stage
        ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END, flow_rows DESC
        """
    ).fetchdf()
    write_frame_outputs(
        stage_df,
        METRICS_DIR / "06_service_line_stage_summary.csv",
        METRICS_DIR / "06_service_line_stage_summary.json",
    )

    sample_df = con.execute(
        f"""
        SELECT
            week_role,
            CAST(flow_id AS VARCHAR) AS flow_id,
            amount_band,
            pathway_stage,
            amount,
            lifecycle_hours,
            is_fraud_truth,
            is_fraud_bank_view,
            truth_bank_mismatch_flag
        FROM parquet_scan({sql_path(SERVICE_LINE_BASE)})
        WHERE week_role = 'current' AND amount_band = '50_plus'
        ORDER BY truth_bank_mismatch_flag DESC, amount DESC
        LIMIT 8
        """
    ).fetchdf()
    con.close()

    current = kpi_df[kpi_df["week_role"] == "current"].iloc[0]
    prior = kpi_df[kpi_df["week_role"] == "prior"].iloc[0]
    current_segments = segment_df[segment_df["week_role"] == "current"].copy()
    prior_segments = segment_df[segment_df["week_role"] == "prior"].copy()
    current_segments["amount_band_short"] = current_segments["amount_band"].map(short_band)
    prior_segments["amount_band_short"] = prior_segments["amount_band"].map(short_band)

    merged_segments = current_segments.merge(
        prior_segments,
        on="amount_band",
        suffixes=("_current", "_prior"),
    )
    issue_row = merged_segments.sort_values(
        ["case_open_rate_current", "case_truth_rate_current"], ascending=[False, True]
    ).iloc[0]
    discrepancy_issue = discrepancy_df[discrepancy_df["week_role"] == "current"].iloc[0]

    write_md(
        ARTEFACT / "service_line_source_map_v1.md",
        f"""
        # Service Line Source Map v1

        Review windows:
        - prior week: `{PRIOR_WEEK[:10]}`
        - current week: `{CURRENT_WEEK[:10]}`

        Source purposes:
        - `s2_event_stream_baseline_6B`: entry-event coverage and event-volume context for flows in the bounded service-line windows
        - `s2_flow_anchor_baseline_6B`: anchor grain, amount, and review-window membership
        - `s4_case_timeline_6B`: case opening, closure, pathway stage, and lifecycle burden
        - `s4_flow_truth_labels_6B`: authoritative outcome-quality signal for the service-line KPIs
        - `s4_flow_bank_view_6B`: comparison-only operational outcome surface used for discrepancy reading, not KPI authority

        Grain note:
        - the merged analytical base is at `flow_id`
        - KPI outputs aggregate that base to `week_role` and `amount_band`

        Fit-for-use note:
        - event coverage is complete across the bounded windows
        - truth and bank-view coverage are complete across the bounded windows
        - case chronology is available for the bounded service-line slice
        """,
    )

    write_md(
        ARTEFACT / "service_line_authoritative_source_rules_v1.md",
        f"""
        # Service Line Authoritative Source Rules v1

        KPI authority:
        - workflow-entry volume: `s2_flow_anchor_baseline_6B`
        - event-entry volume context: `s2_event_stream_baseline_6B`
        - conversion into case work: `s4_case_timeline_6B`
        - lifecycle burden and pathway stage: `s4_case_timeline_6B`
        - outcome quality: `s4_flow_truth_labels_6B`

        Comparison-only rule:
        - `s4_flow_bank_view_6B` is used only to identify discrepancy between operational comparison labels and authoritative truth
        - it must not override the authoritative outcome-quality KPI

        Current bounded discrepancy:
        - current truth-versus-bank mismatch on case-opened flows is {short_pct(float(discrepancy_issue['truth_bank_mismatch_rate']))}
        - current bank-view case rate is {short_pct(float(discrepancy_issue['bank_case_rate']))}
        - current authoritative truth case rate is {short_pct(float(discrepancy_issue['truth_case_rate']))}
        """,
    )

    write_md(
        ARTEFACT / "service_line_join_lineage_v1.md",
        """
        # Service Line Join Lineage v1

        Join path:
        - start from `s2_flow_anchor_baseline_6B` at `flow_id` grain for the bounded current and prior review weeks
        - attach event coverage from `s2_event_stream_baseline_6B` by `flow_id`
        - attach case chronology from `s4_case_timeline_6B` by `flow_id`
        - attach authoritative truth from `s4_flow_truth_labels_6B` by `flow_id`
        - attach comparison-only bank view from `s4_flow_bank_view_6B` by `flow_id`

        Usage boundary:
        - this slice is for bounded service-line performance comparison and discrepancy-aware reporting
        - it is not a full operational estate and not a whole-platform throughput claim
        """,
    )

    write_md(
        ARTEFACT / "service_line_discrepancy_log_v1.md",
        """
        # Service Line Discrepancy Log v1

        ## Issue 1
        - issue: bank-view outcome logic materially disagrees with authoritative truth on case-opened flows
        - likely cause: bank view is an operational comparison surface rather than the authoritative outcome-quality source
        - affected KPI: outcome quality
        - severity: high
        - action: use authoritative truth as the only outcome-quality KPI source

        ## Issue 2
        - issue: the highest-conversion amount segment returns weaker authoritative truth quality than lower-amount segments
        - likely cause: escalation into case work is not tightly aligned with outcome quality in that segment
        - affected KPI: conversion into case work, outcome quality
        - severity: medium
        - action: review escalation or review rules for the higher-amount segment
        """,
    )

    write_md(
        ARTEFACT / "service_line_what_changed_v1.md",
        f"""
        # Service Line What Changed v1

        Current-versus-prior reading:
        - flow pressure rose from {comma(float(prior['flow_rows']))} to {comma(float(current['flow_rows']))} ({metric_delta(float(current['flow_rows']), float(prior['flow_rows']), 'pct')})
        - case-open rate moved from {short_pct(float(prior['case_open_rate']))} to {short_pct(float(current['case_open_rate']))} ({metric_delta(float(current['case_open_rate']), float(prior['case_open_rate']))})
        - authoritative case truth rate moved from {short_pct(float(prior['case_truth_rate']))} to {short_pct(float(current['case_truth_rate']))} ({metric_delta(float(current['case_truth_rate']), float(prior['case_truth_rate']))})

        Practical reading:
        - overall service-line pressure is slightly higher in the current week
        - conversion and outcome quality are broadly flat at the top level
        - the more important issue is structural: the higher-amount segment is still escalating into case work more often while delivering weaker authoritative truth yield
        """,
    )

    write_md(
        ARTEFACT / "service_line_problem_statement_v1.md",
        f"""
        # Service Line Problem Statement v1

        Current service-line problem:
        - the current `{short_band(issue_row['amount_band'])}` segment has the highest case-open rate at {short_pct(float(issue_row['case_open_rate_current']))}
        - but it carries the weakest authoritative truth rate at {short_pct(float(issue_row['case_truth_rate_current']))}
        - lower-amount segments convert into case work less often while returning stronger outcome quality

        Why this matters:
        - the service is carrying extra case-review workload in the segment most likely to create burden without corresponding quality
        - this is visible only after combining entry volume, case chronology, and authoritative outcome surfaces
        """,
    )

    write_md(
        ARTEFACT / "service_line_kpi_definitions_v1.md",
        """
        # Service Line KPI Definitions v1

        Core KPI families:
        - `flow_rows`: bounded workflow-entry pressure at `flow_id` grain
        - `case_open_rate`: share of flows converting into case work
        - `long_lifecycle_share`: share of case-opened flows taking at least 168 hours from flow to closure or horizon
        - `case_truth_rate`: authoritative outcome quality among case-opened flows

        Supporting trust KPI:
        - `truth_bank_mismatch_rate`: share of case-opened flows where bank-view outcome disagrees with authoritative truth
        """,
    )

    write_md(
        ARTEFACT / "service_line_page_notes_v1.md",
        """
        # Service Line Page Notes v1

        Page 1 - Executive overview:
        - compares current week to prior week for the bounded service-line question
        - keeps focus on pressure, conversion, burden, and quality

        Page 2 - Workflow health:
        - shows where conversion and long-lifecycle burden sit by amount band
        - includes the truth-versus-bank discrepancy note because source trust affects outcome reading

        Page 3 - Drill-through and detail:
        - shows segment-level quality comparison
        - keeps the discrepancy sample small and readable
        - links the operational issue directly to follow-up action
        """,
    )

    write_md(
        ARTEFACT / "service_line_exec_brief_v1.md",
        f"""
        # Service Line Executive Brief v1

        What changed:
        - bounded service-line flow pressure increased slightly to {comma(float(current['flow_rows']))} in the current week
        - overall case-open conversion stayed broadly flat at {short_pct(float(current['case_open_rate']))}
        - authoritative case outcome quality also stayed broadly flat at {short_pct(float(current['case_truth_rate']))}

        Why it matters:
        - the top-line position looks stable, but the current higher-amount segment continues to convert into case work more aggressively than the rest of the service line
        - that same segment delivers the weakest authoritative truth yield
        """,
    )

    write_md(
        ARTEFACT / "service_line_action_note_v1.md",
        f"""
        # Service Line Action Note v1

        Immediate attention area:
        - the current `{short_band(issue_row['amount_band'])}` amount segment has the highest case-open rate at {short_pct(float(issue_row['case_open_rate_current']))}
        - its authoritative truth rate is only {short_pct(float(issue_row['case_truth_rate_current']))}

        Suggested follow-up:
        - review current escalation or review rules for the higher-amount segment
        - validate whether the segment is creating avoidable case-review burden
        - use authoritative truth rather than bank view when judging outcome quality
        """,
    )

    write_md(
        ARTEFACT / "service_line_challenge_response_v1.md",
        f"""
        # Service Line Challenge Response v1

        Why trust this pack?
        - it is built from four governed source families rather than one report-only table
        - the current and prior windows use the same join path and KPI definitions
        - source disagreement is exposed explicitly rather than hidden

        Main caveat:
        - bank-view outcome logic disagrees with authoritative truth on {short_pct(float(discrepancy_issue['truth_bank_mismatch_rate']))} of case-opened flows in the current week
        - bank view should not be treated as the KPI authority for outcome quality
        """,
    )

    fig, axes = plt.subplots(1, 3, figsize=(18.5, 6.5), gridspec_kw={"width_ratios": [1.0, 1.05, 1.0]})
    axes[0].axis("off")
    axes[0].text(0.0, 0.95, "Executive Overview", fontsize=20, fontweight="bold", ha="left", va="top")
    axes[0].text(0.0, 0.82, "Current week compared to the prior week for one bounded service-line review question.", fontsize=11, ha="left", va="top")
    kpis = [
        ("Flows in scope", comma(float(current["flow_rows"])), comma(float(prior["flow_rows"]))),
        ("Case-open rate", short_pct(float(current["case_open_rate"])), short_pct(float(prior["case_open_rate"]))),
        ("Long lifecycle share", short_pct(float(current["long_lifecycle_share"])), short_pct(float(prior["long_lifecycle_share"]))),
        ("Case truth rate", short_pct(float(current["case_truth_rate"])), short_pct(float(prior["case_truth_rate"]))),
    ]
    y = 0.62
    for label, current_value, prior_value in kpis:
        axes[0].text(0.02, y, label, fontsize=12, ha="left", va="center")
        axes[0].text(0.72, y, current_value, fontsize=12, fontweight="bold", ha="right", va="center")
        axes[0].text(0.98, y, prior_value, fontsize=11, color="#666666", ha="right", va="center")
        y -= 0.11
    axes[0].text(
        0.02,
        0.10,
        f"Top issue: the {short_band(issue_row['amount_band'])} segment converts into case work most often\n"
        f"but delivers only {short_pct(float(issue_row['case_truth_rate_current']))} authoritative truth.",
        fontsize=10.5,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    kpi_plot_df = pd.DataFrame(
        {
            "kpi": ["Case-open", "Long lifecycle", "Truth quality"],
            "prior": [float(prior["case_open_rate"]), float(prior["long_lifecycle_share"]), float(prior["case_truth_rate"])],
            "current": [float(current["case_open_rate"]), float(current["long_lifecycle_share"]), float(current["case_truth_rate"])],
        }
    ).melt(id_vars="kpi", var_name="week_role", value_name="metric_value")
    sns.barplot(data=kpi_plot_df, x="kpi", y="metric_value", hue="week_role", palette=["#9fc5e8", "#3d85c6"], ax=axes[1])
    axes[1].set_title("Current vs Prior KPI Read")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Rate")
    axes[1].legend(title="", loc="best", fontsize=10)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=9)

    cohort_issue_df = current_segments.sort_values("case_open_rate", ascending=False)
    sns.barplot(data=cohort_issue_df, x="case_open_rate", y="amount_band_short", hue="amount_band_short", palette="Blues_r", legend=False, ax=axes[2])
    axes[2].set_title("Current Conversion by Amount Band")
    axes[2].set_xlabel("Case-open rate")
    axes[2].set_ylabel("")
    for container in axes[2].containers:
        axes[2].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=4, fontsize=9)
    fig.suptitle("Reporting Pack Page 1 - Executive Overview", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "executive_overview.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={"width_ratios": [1.0, 1.0, 0.95]})
    conversion_plot = segment_df.copy()
    conversion_plot["amount_band_short"] = conversion_plot["amount_band"].map(short_band)
    sns.barplot(data=conversion_plot, x="amount_band_short", y="case_open_rate", hue="week_role", palette=["#9fc5e8", "#3d85c6"], ax=axes[0])
    axes[0].set_title("Conversion Into Case Work")
    axes[0].set_xlabel("Amount band")
    axes[0].set_ylabel("Case-open rate")
    axes[0].legend(title="", loc="best", fontsize=10)
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)

    sns.barplot(data=conversion_plot, x="amount_band_short", y="long_lifecycle_share", hue="week_role", palette=["#d9ead3", "#6aa84f"], ax=axes[1])
    axes[1].set_title("Long Lifecycle Burden")
    axes[1].set_xlabel("Amount band")
    axes[1].set_ylabel("Share of case-opened flows >= 168h")
    axes[1].legend(title="", loc="best", fontsize=10)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)

    discrepancy_plot = discrepancy_df.melt(
        id_vars="week_role",
        value_vars=["truth_case_rate", "bank_case_rate", "truth_bank_mismatch_rate"],
        var_name="metric_name",
        value_name="metric_value",
    )
    discrepancy_plot["metric_name"] = discrepancy_plot["metric_name"].map(
        {
            "truth_case_rate": "Truth quality",
            "bank_case_rate": "Bank-view quality",
            "truth_bank_mismatch_rate": "Mismatch rate",
        }
    )
    sns.barplot(data=discrepancy_plot, x="metric_name", y="metric_value", hue="week_role", palette=["#f4cccc", "#cc0000"], ax=axes[2])
    axes[2].set_title("Outcome Trust Check")
    axes[2].set_xlabel("")
    axes[2].set_ylabel("Rate")
    axes[2].legend(title="", loc="best", fontsize=10)
    for container in axes[2].containers:
        axes[2].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)
    fig.suptitle("Reporting Pack Page 2 - Workflow Health", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "workflow_health.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={"width_ratios": [1.0, 1.0, 1.25]})
    quality_plot = conversion_plot.copy()
    sns.barplot(data=quality_plot, x="amount_band_short", y="case_truth_rate", hue="week_role", palette=["#b6d7a8", "#38761d"], ax=axes[0])
    axes[0].set_title("Authoritative Outcome Quality")
    axes[0].set_xlabel("Amount band")
    axes[0].set_ylabel("Case truth rate")
    axes[0].legend(title="", loc="best", fontsize=10)
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)

    scatter_df = current_segments.copy()
    sns.scatterplot(
        data=scatter_df,
        x="case_open_rate",
        y="case_truth_rate",
        size="flow_rows",
        hue="amount_band_short",
        sizes=(180, 900),
        palette="mako",
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Current Segment Burden vs Quality")
    axes[1].set_xlabel("Case-open rate")
    axes[1].set_ylabel("Case truth rate")
    for _, row in scatter_df.iterrows():
        axes[1].text(row["case_open_rate"], row["case_truth_rate"], f"{row['amount_band_short']}\n{short_pct(float(row['case_truth_rate']))}", fontsize=8.5, ha="left", va="bottom")

    sample_df["flow_id"] = sample_df["flow_id"].str[-8:]
    sample_df["amount"] = sample_df["amount"].map(lambda v: f"{v:,.0f}")
    sample_df["amount_band"] = sample_df["amount_band"].map(short_band)
    sample_df["pathway_stage"] = sample_df["pathway_stage"].map(short_stage)
    sample_df["truth_bank_mismatch_flag"] = sample_df["truth_bank_mismatch_flag"].map(lambda v: "yes" if int(v) == 1 else "no")
    axes[2].axis("off")
    axes[2].set_title("Current Segment Sample", loc="left", pad=12)
    table = axes[2].table(
        cellText=sample_df[["week_role", "flow_id", "amount_band", "pathway_stage", "amount", "truth_bank_mismatch_flag"]].values.tolist(),
        colLabels=["Week", "Flow", "Band", "Stage", "Amount", "Mismatch"],
        loc="center",
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.3)
    fig.suptitle("Reporting Pack Page 3 - Detail and Interpretation", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "drillthrough_detail.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    write_md(
        ARTEFACT / "service_line_reporting_pack_v1.md",
        """
        # Service Line Reporting Pack v1

        This pack operationalises the bounded multi-source service-performance slice into three stakeholder-facing pages.

        ## Page 1 - Executive Overview

        ![Executive overview](figures/executive_overview.png)

        ## Page 2 - Workflow Health

        ![Workflow health](figures/workflow_health.png)

        ## Page 3 - Drill-Through Detail

        ![Drill-through detail](figures/drillthrough_detail.png)
        """,
    )

    figure_manifest = {
        "generated_figures": [
            "executive_overview.png",
            "workflow_health.png",
            "drillthrough_detail.png",
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(json.dumps(figure_manifest, indent=2), encoding="utf-8")

    fact_pack = {
        "slice": "huc/01_multi_source_service_performance",
        "review_windows": {"prior_week": PRIOR_WEEK[:10], "current_week": CURRENT_WEEK[:10]},
        "kpis": json.loads(kpi_df.to_json(orient="records")),
        "discrepancy_summary": json.loads(discrepancy_df.to_json(orient="records")),
        "top_issue_segment": {
            "amount_band": str(issue_row["amount_band"]),
            "current_case_open_rate": float(issue_row["case_open_rate_current"]),
            "current_case_truth_rate": float(issue_row["case_truth_rate_current"]),
        },
        "assets": {
            "service_line_base": str(SERVICE_LINE_BASE),
            "service_line_kpis": str(SERVICE_LINE_KPIS),
            "service_line_segment_summary": str(SERVICE_LINE_SEGMENTS),
            "service_line_discrepancy_summary": str(SERVICE_LINE_DISCREPANCY),
            "reporting_pack": str(ARTEFACT / "service_line_reporting_pack_v1.md"),
        },
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    print("service_line_performance build complete")


if __name__ == "__main__":
    main()
