from __future__ import annotations

import json
import shutil
import sys
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

    rebuild_sql = "--rebuild-sql" in sys.argv or not all(
        path.exists()
        for path in [
            SERVICE_LINE_BASE,
            SERVICE_LINE_KPIS,
            SERVICE_LINE_SEGMENTS,
            SERVICE_LINE_DISCREPANCY,
        ]
    )
    if rebuild_sql:
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

        Figure 1 - Source integration and trust boundary:
        - shows that the bounded service-line view really combines four governed source families
        - keeps the linkage posture and trust caveat visible

        Figure 2 - Current vs prior KPI movement:
        - focuses on top-line weekly movement in the KPI family
        - keeps the service-line reading centered on pressure, conversion, burden, and quality

        Figure 3 - Segment and stage issue pattern:
        - shows where the structural burden issue sits
        - combines segment burden-versus-quality and pathway-stage yield so the operational problem is visible without a dashboard page
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

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.2))

    linkage_plot = discrepancy_df.melt(
        id_vars="week_role",
        value_vars=["event_link_rate", "case_row_link_rate", "truth_link_rate", "bank_link_rate"],
        var_name="metric_name",
        value_name="metric_value",
    )
    linkage_plot["metric_name"] = linkage_plot["metric_name"].map(
        {
            "event_link_rate": "Event link",
            "case_row_link_rate": "Case link",
            "truth_link_rate": "Truth link",
            "bank_link_rate": "Bank link",
        }
    )
    sns.barplot(data=linkage_plot, x="metric_name", y="metric_value", hue="week_role", palette=["#d9ead3", "#6aa84f"], ax=axes[0])
    axes[0].set_title("Source Linkage Coverage")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Rate")
    axes[0].legend(title="", loc="best", fontsize=10)
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)

    trust_plot = discrepancy_df.melt(
        id_vars="week_role",
        value_vars=["truth_case_rate", "bank_case_rate", "truth_bank_mismatch_rate"],
        var_name="metric_name",
        value_name="metric_value",
    )
    trust_plot["metric_name"] = trust_plot["metric_name"].map(
        {
            "truth_case_rate": "Truth quality",
            "bank_case_rate": "Bank-view quality",
            "truth_bank_mismatch_rate": "Mismatch rate",
        }
    )
    sns.barplot(data=trust_plot, x="metric_name", y="metric_value", hue="week_role", palette=["#f4cccc", "#cc0000"], ax=axes[1])
    axes[1].set_title("Truth vs Bank-View Boundary")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Rate")
    axes[1].legend(title="", loc="best", fontsize=10)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=8.5)
    fig.suptitle("Figure 1 - Source Integration and Trust Boundary", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "source_integration_and_trust_boundary.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.5), gridspec_kw={"width_ratios": [1.0, 0.95]})
    kpi_plot_df = pd.DataFrame(
        {
            "kpi": ["Case-open", "Long lifecycle", "Truth quality"],
            "prior": [float(prior["case_open_rate"]), float(prior["long_lifecycle_share"]), float(prior["case_truth_rate"])],
            "current": [float(current["case_open_rate"]), float(current["long_lifecycle_share"]), float(current["case_truth_rate"])],
        }
    ).melt(id_vars="kpi", var_name="week_role", value_name="metric_value")
    sns.barplot(data=kpi_plot_df, x="kpi", y="metric_value", hue="week_role", palette=["#9fc5e8", "#3d85c6"], ax=axes[0])
    axes[0].set_title("Current vs Prior KPI Movement")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Rate")
    axes[0].legend(title="", loc="best", fontsize=10)
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=3, fontsize=9)

    volume_plot = pd.DataFrame(
        {
            "metric": ["Flow rows", "Entry events"],
            "prior_millions": [float(prior["flow_rows"]) / 1_000_000, float(prior["entry_event_rows"]) / 1_000_000],
            "current_millions": [float(current["flow_rows"]) / 1_000_000, float(current["entry_event_rows"]) / 1_000_000],
        }
    ).melt(id_vars="metric", var_name="week_role", value_name="millions")
    volume_plot["week_role"] = volume_plot["week_role"].map({"prior_millions": "prior", "current_millions": "current"})
    sns.barplot(data=volume_plot, x="metric", y="millions", hue="week_role", palette=["#c9daf8", "#1c4587"], ax=axes[1])
    axes[1].set_title("Pressure Volume Context")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Rows (millions)")
    axes[1].legend(title="", loc="best", fontsize=10)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[f"{v:.2f}M" for v in container.datavalues], padding=3, fontsize=9)
    fig.suptitle("Figure 2 - Current vs Prior KPI Movement", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "current_vs_prior_kpi_movement.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.5), gridspec_kw={"width_ratios": [1.0, 0.95]})
    gap_df = current_segments.copy()
    gap_df = gap_df.sort_values("case_open_rate", ascending=True).reset_index(drop=True)
    y_positions = list(range(len(gap_df)))
    axes[0].hlines(
        y=y_positions,
        xmin=gap_df["case_open_rate"],
        xmax=gap_df["case_truth_rate"],
        color="#b7b7b7",
        linewidth=3,
        alpha=0.9,
    )
    axes[0].scatter(gap_df["case_open_rate"], y_positions, s=220, color="#3d85c6", label="Case-open rate", zorder=3)
    axes[0].scatter(gap_df["case_truth_rate"], y_positions, s=220, color="#38761d", label="Truth quality", zorder=3)
    axes[0].set_title("Current Segment Burden vs Quality")
    axes[0].set_xlabel("Rate")
    axes[0].set_ylabel("Amount band")
    axes[0].set_yticks(y_positions)
    axes[0].set_yticklabels(gap_df["amount_band_short"])
    axes[0].legend(title="", loc="lower right", fontsize=10)
    axes[0].set_xlim(0.08, 0.22)
    for idx, row in gap_df.iterrows():
        axes[0].text(float(row["case_truth_rate"]) + 0.003, idx, f"{short_pct(float(row['case_open_rate']))} -> {short_pct(float(row['case_truth_rate']))}", fontsize=8.5, va="center")

    current_stage = stage_df[stage_df["week_role"] == "current"].copy()
    current_stage["pathway_stage_short"] = current_stage["pathway_stage"].map(short_stage)
    current_stage = current_stage.sort_values("flow_rows", ascending=True)
    sns.barplot(data=current_stage, x="fraud_truth_rate", y="pathway_stage_short", hue="pathway_stage_short", palette="Greens", legend=False, ax=axes[1])
    axes[1].set_title("Current Pathway Stage Yield")
    axes[1].set_xlabel("Authoritative truth rate")
    axes[1].set_ylabel("")
    for idx, row in current_stage.reset_index(drop=True).iterrows():
        axes[1].text(float(row["fraud_truth_rate"]) + 0.01, idx, f"{comma(float(row['flow_rows']))} flows", fontsize=8.5, va="center")
    axes[1].set_xlim(0, 1.05)
    fig.suptitle("Figure 3 - Segment and Stage Issue Pattern", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "segment_and_stage_issue_pattern.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    write_md(
        ARTEFACT / "service_line_reporting_pack_v1.md",
        """
        # Service Line Reporting Pack v1

        This pack operationalises the bounded multi-source service-performance slice into three complementary evidence figures.

        ## Figure 1 - Source Integration and Trust Boundary

        ![Source integration and trust boundary](figures/source_integration_and_trust_boundary.png)

        ## Figure 2 - Current vs Prior KPI Movement

        ![Current vs prior KPI movement](figures/current_vs_prior_kpi_movement.png)

        ## Figure 3 - Segment and Stage Issue Pattern

        ![Segment and stage issue pattern](figures/segment_and_stage_issue_pattern.png)
        """,
    )

    figure_manifest = {
        "generated_figures": [
            "source_integration_and_trust_boundary.png",
            "current_vs_prior_kpi_movement.png",
            "segment_and_stage_issue_pattern.png",
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(json.dumps(figure_manifest, indent=2), encoding="utf-8")

    for stale_name in [
        "executive_overview.png",
        "workflow_health.png",
        "drillthrough_detail.png",
    ]:
        stale_path = FIGURES_DIR / stale_name
        if stale_path.exists():
            stale_path.unlink()

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
