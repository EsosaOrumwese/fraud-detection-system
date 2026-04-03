from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import seaborn as sns


BASE = Path(
    r"C:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system"
)
ARTEFACT = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\huc\04_issue_to_action_briefing"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

UPSTREAM_01 = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\huc\01_multi_source_service_performance"
)
UPSTREAM_02 = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\huc\02_reporting_cycle_ownership"
)
UPSTREAM_03 = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\huc\03_conversion_discrepancy_handling"
)

UPSTREAM_KPIS = UPSTREAM_01 / "extracts" / "service_line_kpis_v1.parquet"
UPSTREAM_SEGMENTS = UPSTREAM_01 / "extracts" / "service_line_segment_summary_v1.parquet"
UPSTREAM_EXCEPTIONS = UPSTREAM_02 / "extracts" / "reporting_cycle_exception_view_v1.parquet"
UPSTREAM_CONVERSION = (
    UPSTREAM_03 / "extracts" / "conversion_discrepancy_summary_v1.parquet"
)
UPSTREAM_FACT_PACK = UPSTREAM_02 / "metrics" / "execution_fact_pack.json"

PERIOD_COMPARE_OUT = EXTRACTS_DIR / "issue_period_compare_v1.parquet"
SEGMENT_FOCUS_OUT = EXTRACTS_DIR / "issue_segment_focus_v1.parquet"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def short_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def comma(value: float) -> str:
    return f"{int(round(value)):,}"


def short_band(value: str) -> str:
    mapping = {
        "under_10": "<10",
        "10_to_25": "10-25",
        "25_to_50": "25-50",
        "50_plus": "50+",
    }
    return mapping.get(value, value)


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
        LOGS_DIR.joinpath("upstream_reporting_cycle_fact_pack_snapshot.json").write_text(
            UPSTREAM_FACT_PACK.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def main() -> None:
    start = time.perf_counter()
    for directory in [SQL_DIR, METRICS_DIR, EXTRACTS_DIR, FIGURES_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")
    copy_upstream_log()

    con = duckdb.connect()
    replacements = {
        "$kpi_path": sql_path(UPSTREAM_KPIS),
        "$segment_path": sql_path(UPSTREAM_SEGMENTS),
        "$exception_path": sql_path(UPSTREAM_EXCEPTIONS),
        "$conversion_path": sql_path(UPSTREAM_CONVERSION),
        "$output_path": sql_path(PERIOD_COMPARE_OUT),
    }
    con.execute(render_sql(read_sql("01_build_issue_period_compare.sql"), replacements))

    replacements["$output_path"] = sql_path(SEGMENT_FOCUS_OUT)
    con.execute(render_sql(read_sql("02_build_issue_segment_focus.sql"), replacements))

    period_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(PERIOD_COMPARE_OUT)}) ORDER BY plot_order"
    ).df()
    segment_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(SEGMENT_FOCUS_OUT)}) ORDER BY priority_rank"
    ).df()
    conversion_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(UPSTREAM_CONVERSION)}) ORDER BY week_role"
    ).df()

    write_frame_outputs(
        period_df,
        METRICS_DIR / "01_issue_period_compare.csv",
        METRICS_DIR / "01_issue_period_compare.json",
    )
    write_frame_outputs(
        segment_df,
        METRICS_DIR / "02_issue_segment_focus.csv",
        METRICS_DIR / "02_issue_segment_focus.json",
    )

    current_segment = segment_df.loc[segment_df["priority_attention_flag"] == 1].iloc[0]
    current_conversion = conversion_df.loc[
        conversion_df["week_role"] == "current"
    ].iloc[0]
    pressure_metric = period_df.loc[period_df["metric"] == "Pressure flows"].iloc[0]
    conversion_metric = period_df.loc[period_df["metric"] == "Case-open rate"].iloc[0]
    burden_metric = period_df.loc[
        period_df["metric"] == "Long-lifecycle burden"
    ].iloc[0]
    quality_metric = period_df.loc[
        period_df["metric"] == "Authoritative truth quality"
    ].iloc[0]

    write_md(
        ARTEFACT / "issue_briefing_decision_question_v1.md",
        f"""
        # Issue Briefing Decision Question v1

        Decision question:
        - is the current service-line issue broad deterioration, or is one segment consuming disproportionate case effort without commensurate authoritative value, and where should attention go first?

        Bounded answer:
        - the top line is broadly stable
        - the `50+` amount band remains the recurring burden pocket
        - the briefing should therefore support targeted queue or case-opening review before broad lane-wide intervention
        """,
    )

    write_md(
        ARTEFACT / "issue_process_map_v1.md",
        """
        # Issue Process Map v1

        Minimum process:
        - workflow-entry pressure arrives at `flow_id` grain
        - a share of flows converts into case work
        - case-opened work accumulates lifecycle burden
        - authoritative truth measures downstream quality

        Interpretation rule:
        - the briefing is meant to explain where effort is concentrating and whether that effort is producing proportionate authoritative value
        """,
    )

    write_md(
        ARTEFACT / "issue_kpi_purpose_notes_v1.md",
        """
        # Issue KPI Purpose Notes v1

        KPI families:
        - `flow_rows`: top-line weekly pressure
        - `case_open_rate`: conversion into case work
        - `long_lifecycle_share`: burden or backlog proxy
        - `case_truth_rate`: authoritative downstream quality

        Reporting purpose:
        - use the first figure to show that the top line is broadly stable
        - use the second figure to show why one segment still deserves operational attention
        - keep the trust caveat in the notes, not as decorative prose inside the figures
        """,
    )

    write_md(
        ARTEFACT / "issue_stakeholder_view_matrix_v1.md",
        """
        # Issue Stakeholder View Matrix v1

        Operations:
        - needs to know which segment deserves attention first
        - needs to understand whether the issue is pressure, conversion, burden, or weak downstream quality
        - needs one practical follow-up rather than a broad strategic discussion

        Leadership:
        - needs to know whether the lane is deteriorating materially
        - needs to know whether the problem is concentrated or systemic
        - needs one concise recommendation and one monitoring point
        """,
    )

    write_md(
        ARTEFACT / "issue_what_changed_v1.md",
        f"""
        # Issue What Changed v1

        Current versus prior:
        - pressure increased slightly from {comma(float(pressure_metric["prior_value"]))} to {comma(float(pressure_metric["current_value"]))} flows
        - case-open conversion stayed broadly flat at {short_pct(float(conversion_metric["prior_value"]))} versus {short_pct(float(conversion_metric["current_value"]))}
        - long-lifecycle burden stayed broadly flat at {short_pct(float(burden_metric["prior_value"]))} versus {short_pct(float(burden_metric["current_value"]))}
        - authoritative truth quality stayed broadly flat at {short_pct(float(quality_metric["prior_value"]))} versus {short_pct(float(quality_metric["current_value"]))}

        Reading:
        - this is not a broad service-line deterioration story
        - the issue is that the same segment exception remains in place while the top line stays stable
        """,
    )

    write_md(
        ARTEFACT / "issue_why_it_matters_v1.md",
        f"""
        # Issue Why It Matters v1

        Main issue:
        - the `50+` amount band opens to case work at {short_pct(float(current_segment["case_open_rate"]))}, the highest rate in the bounded lane
        - its authoritative truth quality is only {short_pct(float(current_segment["case_truth_rate"]))}, the weakest among the current segments

        Why that matters:
        - it suggests effort is concentrating in a segment that is not returning proportionate authoritative value
        - it risks sustained review burden even when topline performance appears stable
        - it supports a targeted operational response rather than a broad lane-wide capacity or pressure narrative
        """,
    )

    write_md(
        ARTEFACT / "issue_kpi_definition_sheet_v1.md",
        """
        # Issue KPI Definition Sheet v1

        Stable KPI meanings used in this briefing:
        - `flow_rows`: weekly workflow-entry pressure at `flow_id` grain
        - `case_open_rate`: share of flows converting into case work
        - `long_lifecycle_share`: share of case-opened flows taking at least 168 hours
        - `case_truth_rate`: authoritative outcome quality among case-opened flows

        Control note:
        - suspicious-to-case conversion in this briefing uses the corrected flow-based denominator already stabilised in the anomaly-handling slice
        - bank-view outcome logic remains comparison-only and is not used as the quality authority
        """,
    )

    write_md(
        ARTEFACT / "issue_page_notes_v1.md",
        """
        # Issue Page Notes v1

        Figure 1 - Topline movement and issue context:
        - shows that current-versus-prior movement is broadly stable at the lane level
        - prevents the reader from overreacting to a false broad-deterioration story

        Figure 2 - Segment burden versus quality:
        - shows where the issue actually sits
        - lets the reader see that the `50+` segment has the highest conversion into case work and the weakest authoritative quality
        """,
    )

    write_md(
        ARTEFACT / "issue_exec_brief_v1.md",
        f"""
        # Issue Executive Brief v1

        Executive reading:
        - the current week is broadly stable at top line
        - the main issue is concentrated, not systemic
        - the `50+` segment remains the recurring burden pocket

        Why it matters now:
        - pressure has not collapsed or surged enough to justify a broad lane-wide response
        - targeted attention is more appropriate than expanding the issue into a full-service deterioration story

        What leadership should do next:
        - monitor the `50+` burden-versus-quality gap weekly
        - avoid broad intervention until the concentrated queue is reviewed first
        """,
    )

    write_md(
        ARTEFACT / "issue_operational_action_note_v1.md",
        f"""
        # Issue Operational Action Note v1

        Operational priority:
        - start with the `50+` queue

        Why:
        - it has the highest case-open rate at {short_pct(float(current_segment["case_open_rate"]))}
        - it has the weakest authoritative truth quality at {short_pct(float(current_segment["case_truth_rate"]))}

        Immediate follow-up:
        - review whether case-opening or escalation rules in the higher-amount lane are creating avoidable review burden
        - keep weekly monitoring focused on whether the burden-versus-quality gap narrows before widening intervention elsewhere
        """,
    )

    write_md(
        ARTEFACT / "issue_challenge_response_v1.md",
        f"""
        # Issue Challenge Response v1

        Why trust this briefing?
        - it reuses the compact governed HUC outputs rather than ad hoc extracts
        - suspicious-to-case conversion uses the corrected flow-based denominator
        - authoritative truth remains the quality authority

        Is the issue isolated or systemic?
        - the current bounded evidence points to a concentrated segment issue rather than broad lane deterioration

        What caveats apply?
        - bank-view outcome logic still disagrees materially with authoritative truth and remains comparison-only
        - this is a bounded weekly service-line analogue, not a claim about every queue or stakeholder surface

        What would invalidate the recommendation?
        - a deliberate change to KPI definitions
        - a shift in segment framing or reporting grain
        - new evidence showing the burden-quality gap has moved materially to another segment
        """,
    )

    plot_df = period_df.copy()
    plot_df["rate_metric"] = plot_df["metric"].isin(
        ["Case-open rate", "Long-lifecycle burden", "Authoritative truth quality"]
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.8, 6.2),
        gridspec_kw={"width_ratios": [0.9, 1.1]},
    )

    pressure_df = plot_df.loc[plot_df["metric"] == "Pressure flows"].copy()
    pressure_long = pressure_df.melt(
        id_vars=["metric"],
        value_vars=["prior_value", "current_value"],
        var_name="period",
        value_name="value",
    )
    pressure_long["period"] = pressure_long["period"].map(
        {"prior_value": "Prior", "current_value": "Current"}
    )
    sns.barplot(
        data=pressure_long,
        x="period",
        y="value",
        hue="period",
        palette=["#9fc5e8", "#3d85c6"],
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Pressure Stayed Broadly Stable")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Flows (millions)")
    axes[0].set_ylim(0, pressure_long["value"].max() * 1.18)
    axes[0].yaxis.set_major_formatter(
        FuncFormatter(lambda value, _pos: f"{value / 1_000_000:.1f}M")
    )
    for container in axes[0].containers:
        axes[0].bar_label(
            container,
            labels=[f"{v/1_000_000:.2f}M" for v in container.datavalues],
            padding=3,
            fontsize=9,
        )

    rate_df = plot_df.loc[plot_df["rate_metric"]].copy()
    y_positions = list(range(len(rate_df)))
    bar_height = 0.32
    axes[1].barh(
        [y - bar_height / 2 for y in y_positions],
        rate_df["prior_value"],
        height=bar_height,
        color="#9fc5e8",
        label="Prior",
    )
    axes[1].barh(
        [y + bar_height / 2 for y in y_positions],
        rate_df["current_value"],
        height=bar_height,
        color="#3d85c6",
        label="Current",
    )
    axes[1].set_yticks(y_positions)
    axes[1].set_yticklabels(rate_df["metric"])
    axes[1].set_xlim(0.08, 0.82)
    axes[1].set_title("Core Rates Were Broadly Flat")
    axes[1].set_xlabel("Rate")
    axes[1].set_ylabel("")
    axes[1].legend(title="", loc="lower right", fontsize=10)
    for pos, row in enumerate(rate_df.itertuples(index=False)):
        axes[1].text(
            float(row.current_value) + 0.01,
            pos + bar_height / 2,
            short_pct(float(row.current_value)),
            fontsize=8.5,
            va="center",
        )
        axes[1].text(
            float(row.prior_value) + 0.01,
            pos - bar_height / 2,
            short_pct(float(row.prior_value)),
            fontsize=8.5,
            va="center",
        )

    fig.suptitle("Figure 1 - Topline Movement and Issue Context", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "topline_movement_and_issue_context.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    segment_plot = segment_df.copy()
    segment_plot["amount_band_short"] = segment_plot["amount_band"].map(short_band)
    segment_plot["highlight"] = segment_plot["priority_attention_flag"].map(
        {1: "#c0392b", 0: "#7fa8d1"}
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.8, 6.4),
        sharey=True,
    )
    axes[0].barh(
        segment_plot["amount_band_short"],
        segment_plot["case_open_rate"],
        color=segment_plot["highlight"],
    )
    axes[0].set_title("Case-Open Rate by Segment")
    axes[0].set_xlabel("Rate")
    axes[0].set_ylabel("Amount band")
    axes[0].invert_yaxis()
    for idx, row in segment_plot.iterrows():
        axes[0].text(
            float(row["case_open_rate"]) + 0.0015,
            idx,
            short_pct(float(row["case_open_rate"])),
            va="center",
            fontsize=8.5,
        )

    axes[1].barh(
        segment_plot["amount_band_short"],
        segment_plot["case_truth_rate"],
        color=segment_plot["highlight"],
    )
    axes[1].set_title("Authoritative Truth Quality by Segment")
    axes[1].set_xlabel("Rate")
    axes[1].set_ylabel("")
    for idx, row in segment_plot.iterrows():
        axes[1].text(
            float(row["case_truth_rate"]) + 0.002,
            idx,
            short_pct(float(row["case_truth_rate"])),
            va="center",
            fontsize=8.5,
        )

    fig.suptitle("Figure 2 - Segment Burden Versus Quality", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "segment_burden_versus_quality.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    write_md(
        ARTEFACT / "issue_briefing_pack_v1.md",
        """
        # Issue Briefing Pack v1

        This pack translates one bounded HUC service-line issue into two complementary figures for leadership and operations.

        ## Figure 1 - Topline Movement and Issue Context

        ![Topline movement and issue context](figures/topline_movement_and_issue_context.png)

        ## Figure 2 - Segment Burden Versus Quality

        ![Segment burden versus quality](figures/segment_burden_versus_quality.png)
        """,
    )

    duration_seconds = time.perf_counter() - start
    fact_pack = {
        "slice": "huc/04_issue_to_action_briefing",
        "decision_question": "is the current issue broad deterioration or concentrated segment burden",
        "audiences": ["operations", "leadership"],
        "page_count": 2,
        "kpi_family_count": 4,
        "selected_issue_segment": str(current_segment["amount_band"]),
        "current_flow_rows": int(round(float(pressure_metric["current_value"]))),
        "current_case_open_rate": float(conversion_metric["current_value"]),
        "current_long_lifecycle_share": float(burden_metric["current_value"]),
        "current_case_truth_rate": float(quality_metric["current_value"]),
        "selected_segment_case_open_rate": float(current_segment["case_open_rate"]),
        "selected_segment_case_truth_rate": float(current_segment["case_truth_rate"]),
        "selected_segment_flow_rows": int(round(float(current_segment["flow_rows"]))),
        "current_corrected_conversion_rate": float(
            current_conversion["corrected_flow_conversion_rate"]
        ),
        "recommendation": "review 50_plus queue case-opening or escalation rules before broad lane-wide intervention",
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
                    "topline_movement_and_issue_context.png",
                    "segment_burden_versus_quality.png",
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("issue_to_action_briefing build complete")


if __name__ == "__main__":
    main()
