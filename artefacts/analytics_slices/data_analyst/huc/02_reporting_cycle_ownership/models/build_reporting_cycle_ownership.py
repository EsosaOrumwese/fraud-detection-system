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
    / r"artefacts\analytics_slices\data_analyst\huc\02_reporting_cycle_ownership"
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
UPSTREAM_SEGMENTS = UPSTREAM / "extracts" / "service_line_segment_summary_v1.parquet"
UPSTREAM_DISCREPANCY = (
    UPSTREAM / "extracts" / "service_line_discrepancy_summary_v1.parquet"
)
UPSTREAM_FACT_PACK = UPSTREAM / "metrics" / "execution_fact_pack.json"

SUMMARY_OUT = EXTRACTS_DIR / "reporting_cycle_summary_v1.parquet"
EXCEPTIONS_OUT = EXTRACTS_DIR / "reporting_cycle_exception_view_v1.parquet"
RELEASE_CHECKS_OUT = EXTRACTS_DIR / "reporting_cycle_release_checks_v1.parquet"


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


def short_band(value: str) -> str:
    mapping = {
        "under_10": "<10",
        "10_to_25": "10-25",
        "25_to_50": "25-50",
        "50_plus": "50+",
    }
    return mapping.get(value, value)


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
        "$segment_path": sql_path(UPSTREAM_SEGMENTS),
        "$discrepancy_path": sql_path(UPSTREAM_DISCREPANCY),
        "$output_path": sql_path(SUMMARY_OUT),
    }
    con.execute(render_sql(read_sql("01_build_reporting_cycle_summary.sql"), replacements))

    replacements["$output_path"] = sql_path(EXCEPTIONS_OUT)
    con.execute(render_sql(read_sql("02_build_reporting_cycle_exception_view.sql"), replacements))

    replacements["$output_path"] = sql_path(RELEASE_CHECKS_OUT)
    con.execute(render_sql(read_sql("03_build_reporting_cycle_release_checks.sql"), replacements))

    summary_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(SUMMARY_OUT)})"
    ).df()
    exception_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(EXCEPTIONS_OUT)})"
    ).df()
    release_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RELEASE_CHECKS_OUT)})"
    ).df()
    upstream_kpis = con.execute(
        f"SELECT * FROM read_parquet({sql_path(UPSTREAM_KPIS)})"
    ).df()

    summary_df["reporting_cadence"] = "weekly"
    summary_df["audience_count"] = 2
    summary_df["pack_page_count"] = 3
    summary_df["kpi_family_count"] = 4

    write_frame_outputs(
        summary_df,
        METRICS_DIR / "01_reporting_cycle_summary.csv",
        METRICS_DIR / "01_reporting_cycle_summary.json",
    )
    write_frame_outputs(
        exception_df,
        METRICS_DIR / "02_reporting_cycle_exception_view.csv",
        METRICS_DIR / "02_reporting_cycle_exception_view.json",
    )
    write_frame_outputs(
        release_df,
        METRICS_DIR / "03_reporting_cycle_release_checks.csv",
        METRICS_DIR / "03_reporting_cycle_release_checks.json",
    )

    current_row = upstream_kpis.loc[upstream_kpis["week_role"] == "current"].iloc[0]
    prior_row = upstream_kpis.loc[upstream_kpis["week_role"] == "prior"].iloc[0]
    top_segment = exception_df.loc[exception_df["priority_attention_flag"] == 1].iloc[0]

    write_md(
        ARTEFACT / "service_line_reporting_requirements_v1.md",
        f"""
        # Service Line Reporting Requirements v1

        Reporting lane:
        - weekly owned service-line performance pack for one bounded operational fraud lane

        Core audiences:
        - operations
        - leadership

        Reporting purpose:
        - give operations one stable weekly view of pressure, conversion, burden, and outcome quality
        - give leadership one compact current-versus-prior summary with one clear issue statement
        - keep the pack small enough to rerun on time without redefining KPI meaning each cycle

        What makes the pack useful:
        - the same KPI families appear every cycle
        - the same current-versus-prior comparison logic holds every cycle
        - one anomaly or exception is highlighted rather than burying the reader in movement

        Current bounded issue carried into the pack:
        - the `50+` amount band remains the main exception because it opens to case work at {short_pct(float(top_segment["case_open_rate"]))} but returns only {short_pct(float(top_segment["case_truth_rate"]))} authoritative truth quality
        """,
    )

    write_md(
        ARTEFACT / "service_line_process_map_v1.md",
        """
        # Service Line Process Map v1

        Reporting journey:
        - workflow-entry pressure enters the lane at `flow_id` grain
        - a share of those flows converts into case work
        - case-opened flows accumulate long-lifecycle burden
        - authoritative truth measures downstream outcome quality

        Reporting decision points:
        - leadership needs to know whether the lane is materially changing week over week
        - operations needs to know where burden is accumulating and where intervention is justified
        - both audiences need the source-trust caveat carried with the pack when comparison-only surfaces disagree with authoritative truth
        """,
    )

    write_md(
        ARTEFACT / "service_line_stakeholder_view_matrix_v1.md",
        """
        # Service Line Stakeholder View Matrix v1

        Operations:
        - needs conversion, burden, and exception detail
        - needs to know which slice needs attention first
        - needs the trust caveat when quality metrics are discussed

        Leadership:
        - needs a top-line current-versus-prior summary
        - needs one clear issue statement rather than a large KPI wall
        - needs to know whether the issue is structural or temporary
        """,
    )

    write_md(
        ARTEFACT / "service_line_kpi_purpose_notes_v1.md",
        """
        # Service Line KPI Purpose Notes v1

        KPI families:
        - `flow_rows`: weekly workflow-entry pressure
        - `case_open_rate`: conversion into case work
        - `long_lifecycle_share`: backlog or aging burden proxy
        - `case_truth_rate`: authoritative outcome quality

        Supporting trust KPI:
        - `truth_bank_mismatch_rate`: source-disagreement warning, not a headline performance KPI

        Headline use:
        - page 1: top-line current-versus-prior movement
        - page 2: operational interpretation of conversion, burden, and trust caveat
        - page 3: segment exception and detail
        """,
    )

    write_md(
        ARTEFACT / "service_line_what_changed_v1.md",
        f"""
        # Service Line What Changed v1

        Current versus prior:
        - flow pressure increased from {comma(float(prior_row["flow_rows"]))} to {comma(float(current_row["flow_rows"]))}
        - case-open conversion stayed broadly flat at {short_pct(float(prior_row["case_open_rate"]))} versus {short_pct(float(current_row["case_open_rate"]))}
        - long-lifecycle burden stayed broadly flat at {short_pct(float(prior_row["long_lifecycle_share"]))} versus {short_pct(float(current_row["long_lifecycle_share"]))}
        - authoritative outcome quality stayed broadly flat at {short_pct(float(prior_row["case_truth_rate"]))} versus {short_pct(float(current_row["case_truth_rate"]))}

        Reading:
        - the reporting cycle should describe this as a stable topline week with a persistent structural burden issue, not as a sharp deterioration event
        """,
    )

    write_md(
        ARTEFACT / "service_line_intervention_note_v1.md",
        f"""
        # Service Line Intervention Note v1

        Priority attention area:
        - the `50+` amount band remains the clearest exception in the current cycle
        - it opens to case work at {short_pct(float(top_segment["case_open_rate"]))}
        - its authoritative truth quality is only {short_pct(float(top_segment["case_truth_rate"]))}

        Suggested follow-up:
        - keep this segment as the main exception note in the recurring pack
        - review whether escalation into case work in the higher-amount lane is creating avoidable review burden
        - keep authoritative truth as the only outcome-quality KPI source
        """,
    )

    write_md(
        ARTEFACT / "service_line_kpi_definition_sheet_v1.md",
        """
        # Service Line KPI Definition Sheet v1

        Stable KPI definitions:
        - `flow_rows`: weekly workflow-entry pressure at `flow_id` grain
        - `case_open_rate`: share of flows converting into case work
        - `long_lifecycle_share`: share of case-opened flows taking at least 168 hours
        - `case_truth_rate`: authoritative outcome quality among case-opened flows

        Supporting control metric:
        - `truth_bank_mismatch_rate`: share of case-opened flows where bank-view outcome disagrees with authoritative truth

        Definition stability rule:
        - the four headline KPI meanings must remain unchanged across reporting cycles unless the changelog records a deliberate definition change
        """,
    )

    write_md(
        ARTEFACT / "service_line_page_notes_v1.md",
        """
        # Service Line Page Notes v1

        Figure 1 - Reporting cycle scope and stable reporting contract:
        - shows the fixed cadence, audience pair, and recurring reporting purpose
        - keeps the owned-cycle contract visible without turning the figure into a prose-heavy page

        Figure 2 - Period comparison and exception evidence:
        - shows current-versus-prior KPI movement and the recurring exception segment gap
        - keeps the figure visual-first rather than explanatory-text-first

        Figure 3 - Release controls and regeneration posture:
        - shows release checks, regeneration posture, and stability controls
        - makes clear that the slice is proving reporting-cycle ownership and repeatable release discipline
        """,
    )

    write_md(
        ARTEFACT / "service_line_report_run_checklist_v1.md",
        """
        # Service Line Report Run Checklist v1

        Before rerun:
        - confirm the current and prior reporting windows
        - confirm the compact KPI, segment, and discrepancy inputs are present
        - confirm KPI definitions have not changed outside the changelog

        Run order:
        1. build the reporting-cycle summary extract
        2. build the current exception extract
        3. build the release-check extract
        4. regenerate figures and the reporting pack
        5. refresh the notes and control files if meaning has changed

        Release checks:
        - two period rows present
        - four current segment rows present
        - discrepancy rows present for both periods
        - page notes, caveats, and challenge language aligned to the pack
        """,
    )

    write_md(
        ARTEFACT / "service_line_reporting_changelog_v1.md",
        """
        # Service Line Reporting Changelog v1

        Version `v1`:
        - established the owned weekly service-line reporting cycle
        - fixed the headline KPI family at four performance KPIs plus one supporting trust KPI
        - defined the recurring three-page pack structure
        - added explicit rerun and release-control notes

        Current definition status:
        - no deliberate KPI-definition drift recorded from the initial owned-cycle version
        """,
    )

    write_md(
        ARTEFACT / "service_line_reporting_caveats_v1.md",
        f"""
        # Service Line Reporting Caveats v1

        Main caveat:
        - bank-view outcome logic disagrees with authoritative truth on {short_pct(float(current_row["truth_bank_mismatch_rate"]))} of current case-opened flows
        - bank view must remain comparison-only and must not override the authoritative outcome-quality KPI

        Scope caveat:
        - this pack is a bounded weekly service-line analogue, not a full HUC reporting estate

        Interpretation caveat:
        - stable topline movement does not mean the lane is healthy; the recurring exception remains structural burden in the `50+` segment
        """,
    )

    write_md(
        ARTEFACT / "README_service_line_reporting_regeneration.md",
        """
        # README - Service Line Reporting Regeneration

        Regeneration entrypoint:
        - `python artefacts/analytics_slices/data_analyst/huc/02_reporting_cycle_ownership/models/build_reporting_cycle_ownership.py`

        Inputs:
        - compact KPI output from HUC slice 1
        - compact segment summary from HUC slice 1
        - compact discrepancy summary from HUC slice 1

        Regeneration posture:
        - this slice does not read the full merged service-line base into memory
        - it reuses compact reporting-ready outputs only

        Outputs:
        - reporting-cycle summary extract
        - exception extract
        - release-check extract
        - recurring three-page reporting pack
        - figures
        - requirement, caveat, and rerun-control notes
        """,
    )

    release_pass_count = int(release_df["passed_flag"].sum())
    release_check_count = int(len(release_df))

    write_md(
        ARTEFACT / "service_line_exec_brief_v1.md",
        f"""
        # Service Line Executive Brief v1

        Cycle reading:
        - this weekly pack should be described as stable at topline rather than materially deteriorating
        - pressure increased slightly to {comma(float(current_row["flow_rows"]))}
        - the main issue remains concentrated burden in the `50+` amount band

        What leadership should watch:
        - whether the exception segment keeps opening to case work faster than it returns authoritative value
        - whether the trust caveat is carried correctly when discussing outcome quality
        """,
    )

    # Figures
    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.8), gridspec_kw={"width_ratios": [0.95, 1.05]})
    scope_df = pd.DataFrame(
        {
            "measure": ["Audience groups", "KPI families", "Reporting figures", "Release checks"],
            "count": [2, 4, 3, release_check_count],
        }
    )
    sns.barplot(data=scope_df, x="measure", y="count", hue="measure", palette="Blues", legend=False, ax=axes[0])
    axes[0].set_title("Owned Cycle Scope Counts")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Count")
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[f"{v:.0f}" for v in container.datavalues], padding=3, fontsize=9)

    matrix_df = pd.DataFrame(
        [
            {"kpi_family": "Flow pressure", "Scope figure": 1, "Period figure": 1, "Control figure": 0},
            {"kpi_family": "Case-open conversion", "Scope figure": 1, "Period figure": 1, "Control figure": 1},
            {"kpi_family": "Long-lifecycle burden", "Scope figure": 0, "Period figure": 1, "Control figure": 0},
            {"kpi_family": "Truth quality", "Scope figure": 0, "Period figure": 1, "Control figure": 1},
        ]
    ).set_index("kpi_family")
    sns.heatmap(
        matrix_df,
        cmap=sns.light_palette("#1c4587", as_cmap=True),
        vmin=0,
        vmax=1,
        linewidths=1,
        linecolor="white",
        cbar=False,
        annot=True,
        fmt=".0f",
        ax=axes[1],
    )
    axes[1].set_title("Stable Reporting Contract")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")
    fig.suptitle("Figure 1 - Reporting Cycle Scope and Stable Reporting Contract", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "reporting_cycle_scope_and_kpi_reuse.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.5), gridspec_kw={"width_ratios": [1.0, 0.95]})
    operational_plot = pd.DataFrame(
        {
            "kpi": ["Case-open", "Long lifecycle", "Truth quality", "Mismatch"],
            "prior": [
                prior_row["case_open_rate"],
                prior_row["long_lifecycle_share"],
                prior_row["case_truth_rate"],
                prior_row["truth_bank_mismatch_rate"],
            ],
            "current": [
                current_row["case_open_rate"],
                current_row["long_lifecycle_share"],
                current_row["case_truth_rate"],
                current_row["truth_bank_mismatch_rate"],
            ],
        }
    )
    melted = operational_plot.melt(id_vars="kpi", var_name="period", value_name="rate")
    sns.barplot(
        data=melted,
        x="kpi",
        y="rate",
        hue="period",
        palette=["#9fc5e8", "#3d85c6"],
        ax=axes[0],
    )
    axes[0].set_title("Current vs Prior KPI Layer")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Rate")
    axes[0].legend(title="")
    for container in axes[0].containers:
        axes[0].bar_label(
            container,
            labels=[short_pct(v) for v in container.datavalues],
            padding=3,
            fontsize=8.5,
        )
    axes[0].text(
        0.02,
        -0.26,
        "Trust note: bank-view quality is comparison-only.\nAuthoritative truth remains the KPI source for outcome quality.",
        transform=axes[0].transAxes,
        fontsize=9.5,
        va="top",
        ha="left",
        color="#7a0000",
    )

    current_exception = exception_df.copy()
    current_exception["amount_band_short"] = current_exception["amount_band"].map(short_band)
    axes[1].hlines(
        y=list(range(len(current_exception))),
        xmin=current_exception["case_open_rate"],
        xmax=current_exception["case_truth_rate"],
        color="#b7b7b7",
        linewidth=3,
        alpha=0.9,
    )
    axes[1].scatter(
        current_exception["case_open_rate"],
        list(range(len(current_exception))),
        color="#3d85c6",
        s=220,
        label="Case-open rate",
        zorder=3,
    )
    axes[1].scatter(
        current_exception["case_truth_rate"],
        list(range(len(current_exception))),
        color="#38761d",
        s=220,
        label="Truth quality",
        zorder=3,
    )
    axes[1].set_yticks(list(range(len(current_exception))))
    axes[1].set_yticklabels(current_exception["amount_band_short"])
    axes[1].set_xlim(0.08, 0.22)
    axes[1].set_title("Recurring Exception Segment Gap")
    axes[1].set_xlabel("Rate")
    axes[1].set_ylabel("Amount band")
    axes[1].legend(title="", loc="lower right", fontsize=10)
    for idx, row in current_exception.iterrows():
        axes[1].text(
            float(row["case_truth_rate"]) + 0.003,
            idx,
            f"{short_pct(float(row['case_open_rate']))} -> {short_pct(float(row['case_truth_rate']))}",
            fontsize=8.5,
            va="center",
        )
    fig.suptitle("Figure 2 - Period Comparison and Exception Evidence", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "period_comparison_and_exception_evidence.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.5), gridspec_kw={"width_ratios": [0.9, 1.1]})
    checklist_plot = release_df.copy()
    checklist_plot["check_label"] = checklist_plot["check_name"].str.replace("_", "\n")
    sns.barplot(
        data=checklist_plot,
        x="check_label",
        y="passed_flag",
        hue="check_label",
        palette=["#6aa84f"] * len(checklist_plot),
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Release Checks")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Passed flag")
    axes[0].set_ylim(0, 1.1)
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=["pass" if v >= 1 else "fail" for v in container.datavalues], padding=3, fontsize=9)

    control_df = pd.DataFrame(
        {
            "control_asset": [
                "KPI definition",
                "Run checklist",
                "Caveat note",
                "Changelog",
                "Regeneration README",
            ],
            "present_flag": [1, 1, 1, 1, 1],
        }
    )
    sns.barplot(
        data=control_df,
        x="present_flag",
        y="control_asset",
        hue="control_asset",
        palette="Greens",
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Control Assets Present")
    axes[1].set_xlabel("Present flag")
    axes[1].set_ylabel("")
    axes[1].set_xlim(0, 1.1)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=["yes" if v >= 1 else "no" for v in container.datavalues], padding=3, fontsize=9)
    fig.suptitle("Figure 3 - Release Controls and Regeneration Posture", fontsize=18, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "release_controls_and_regeneration_posture.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    write_md(
        ARTEFACT / "service_line_reporting_pack_v1.md",
        """
        # Service Line Reporting Pack v1

        This pack operationalises one owned weekly service-line reporting cycle into three complementary evidence figures.

        ## Figure 1 - Reporting Cycle Scope and Stable Reporting Contract

        ![Reporting cycle scope and KPI reuse](figures/reporting_cycle_scope_and_kpi_reuse.png)

        ## Figure 2 - Period Comparison and Exception Evidence

        ![Period comparison and exception evidence](figures/period_comparison_and_exception_evidence.png)

        ## Figure 3 - Release Controls and Regeneration Posture

        ![Release controls and regeneration posture](figures/release_controls_and_regeneration_posture.png)
        """,
    )

    duration_seconds = time.perf_counter() - start
    fact_pack = {
        "slice": "huc/02_reporting_cycle_ownership",
        "reporting_cadence": "weekly",
        "audiences": ["operations", "leadership"],
        "kpi_family_count": 4,
        "page_count": 3,
        "current_week_flow_rows": int(current_row["flow_rows"]),
        "prior_week_flow_rows": int(prior_row["flow_rows"]),
        "current_case_open_rate": float(current_row["case_open_rate"]),
        "current_long_lifecycle_share": float(current_row["long_lifecycle_share"]),
        "current_case_truth_rate": float(current_row["case_truth_rate"]),
        "current_truth_bank_mismatch_rate": float(current_row["truth_bank_mismatch_rate"]),
        "top_exception_segment": {
            "amount_band": str(top_segment["amount_band"]),
            "case_open_rate": float(top_segment["case_open_rate"]),
            "case_truth_rate": float(top_segment["case_truth_rate"]),
        },
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
                    "reporting_cycle_scope_and_kpi_reuse.png",
                    "period_comparison_and_exception_evidence.png",
                    "release_controls_and_regeneration_posture.png",
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    for stale_name in [
        "executive_service_line_overview.png",
        "operational_performance_view.png",
        "drillthrough_and_controls.png",
    ]:
        stale_path = FIGURES_DIR / stale_name
        if stale_path.exists():
            stale_path.unlink()

    print("reporting_cycle_ownership build complete")


if __name__ == "__main__":
    main()
