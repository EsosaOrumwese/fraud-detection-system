from __future__ import annotations

import json
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
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\06_dashboard_decision_support"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

UPSTREAM_MODEL = (
    BASE
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\05_governed_explainable_ai"
)
UPSTREAM_PATHWAY = (
    BASE
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\03_population_pathway_analysis"
)

DASHBOARD_BASE = EXTRACTS_DIR / "flow_dashboard_base_v1.parquet"
DASHBOARD_SUMMARY = EXTRACTS_DIR / "flow_dashboard_summary_v1.parquet"
DASHBOARD_DRILLTHROUGH = EXTRACTS_DIR / "flow_dashboard_drillthrough_v1.parquet"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def short_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def comma(value: float) -> str:
    return f"{int(round(value)):,}"


def write_md(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    con = duckdb.connect()
    con.register("tmp_df", df)
    con.execute(
        f"COPY tmp_df TO '{str(path).replace(chr(92), '/')}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    con.close()


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


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def short_cohort_label(value: str) -> str:
    mapping = {
        "not_case_selected": "not_case",
        "fast_converting_high_yield": "fast_high",
        "slow_converting_high_yield": "slow_high",
        "high_burden_low_yield": "high_burden",
        "low_burden_low_yield": "low_burden",
    }
    return mapping.get(value, value)


def main() -> None:
    sns.set_theme(style="whitegrid", context="talk")

    replacements = {
        "$validation_scores_path": sql_path(UPSTREAM_MODEL / "extracts" / "validation_scores_selected_v1.parquet"),
        "$test_scores_path": sql_path(UPSTREAM_MODEL / "extracts" / "test_scores_selected_v1.parquet"),
        "$model_base_path": sql_path(UPSTREAM_MODEL / "extracts" / "flow_model_ready_slice_v2_encoded.parquet"),
        "$population_pathway_base_path": sql_path(UPSTREAM_PATHWAY / "extracts" / "population_pathway_base_v1.parquet"),
        "$dashboard_base_output": sql_path(DASHBOARD_BASE),
        "$dashboard_base_path": sql_path(DASHBOARD_BASE),
        "$dashboard_summary_output": sql_path(DASHBOARD_SUMMARY),
        "$dashboard_drillthrough_output": sql_path(DASHBOARD_DRILLTHROUGH),
    }

    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")

    input_profile_df = con.execute(
        f"""
        WITH validation_scores AS (
            SELECT COUNT(*) AS rows FROM parquet_scan({sql_path(UPSTREAM_MODEL / "extracts" / "validation_scores_selected_v1.parquet")})
        ),
        test_scores AS (
            SELECT COUNT(*) AS rows FROM parquet_scan({sql_path(UPSTREAM_MODEL / "extracts" / "test_scores_selected_v1.parquet")})
        ),
        pathway_reporting AS (
            SELECT COUNT(*) AS rows FROM parquet_scan({sql_path(UPSTREAM_PATHWAY / "extracts" / "population_pathway_reporting_v1.parquet")})
        ),
        pathway_kpis AS (
            SELECT COUNT(*) AS rows FROM parquet_scan({sql_path(UPSTREAM_PATHWAY / "extracts" / "population_pathway_kpis_v1.parquet")})
        )
        SELECT 'validation_scores_selected_v1' AS input_name, rows FROM validation_scores
        UNION ALL
        SELECT 'test_scores_selected_v1', rows FROM test_scores
        UNION ALL
        SELECT 'population_pathway_reporting_v1', rows FROM pathway_reporting
        UNION ALL
        SELECT 'population_pathway_kpis_v1', rows FROM pathway_kpis
        """
    ).fetchdf()
    write_frame_outputs(
        input_profile_df,
        METRICS_DIR / "01_dashboard_input_profile.csv",
        METRICS_DIR / "01_dashboard_input_profile.json",
    )

    for sql_name in [
        "01_build_flow_dashboard_base.sql",
        "02_build_flow_dashboard_summary.sql",
        "03_build_flow_dashboard_drillthrough.sql",
    ]:
        con.execute(render_sql(read_sql(sql_name), replacements))

    base_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(DASHBOARD_BASE)}) ORDER BY split_role, priority_rank"
    ).fetchdf()
    summary_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(DASHBOARD_SUMMARY)})"
    ).fetchdf()
    drillthrough_df = con.execute(
        f"SELECT * FROM parquet_scan({sql_path(DASHBOARD_DRILLTHROUGH)}) ORDER BY priority_rank"
    ).fetchdf()
    con.close()

    output_profile_df = pd.DataFrame(
        [
            {"output_name": "flow_dashboard_base_v1", "rows": len(base_df)},
            {"output_name": "flow_dashboard_summary_v1", "rows": len(summary_df)},
            {"output_name": "flow_dashboard_drillthrough_v1", "rows": len(drillthrough_df)},
        ]
    )
    write_frame_outputs(
        output_profile_df,
        METRICS_DIR / "02_dashboard_output_profile.csv",
        METRICS_DIR / "02_dashboard_output_profile.json",
    )

    split_profile_df = (
        base_df.groupby("split_role")
        .agg(
            flow_rows=("flow_id", "count"),
            high_band_rows=("risk_band", lambda s: int((s == "High").sum())),
            medium_band_rows=("risk_band", lambda s: int((s == "Medium").sum())),
            fraud_truth_rate=("target_is_fraud_truth", "mean"),
            case_open_rate=("has_case_opened", "mean"),
        )
        .reset_index()
    )
    write_frame_outputs(
        split_profile_df,
        METRICS_DIR / "03_dashboard_split_profile.csv",
        METRICS_DIR / "03_dashboard_split_profile.json",
    )

    selected_model_fact = json.loads(
        (UPSTREAM_MODEL / "metrics" / "execution_fact_pack.json").read_text(encoding="utf-8")
    )
    top_coeffs_df = pd.DataFrame(selected_model_fact["top_coefficients"])

    current_df = base_df[base_df["split_role"] == "test"].copy()
    previous_df = base_df[base_df["split_role"] == "validation"].copy()
    current_case_df = current_df[current_df["is_case_selected"] == 1].copy()

    current_high = current_df[current_df["risk_band"] == "High"]
    current_medium = current_df[current_df["risk_band"] == "Medium"]
    previous_high = previous_df[previous_df["risk_band"] == "High"]

    current_high_rate = float(current_high["target_is_fraud_truth"].mean())
    previous_high_rate = float(previous_high["target_is_fraud_truth"].mean())
    current_case_open_rate = float(current_df["has_case_opened"].mean())
    previous_case_open_rate = float(previous_df["has_case_opened"].mean())

    cohort_share_df = (
        current_case_df.groupby("cohort_label")
        .size()
        .reset_index(name="flow_rows")
        .assign(share=lambda d: d["flow_rows"] / d["flow_rows"].sum())
        .sort_values("share", ascending=False)
    )

    pathway_stage_df = (
        current_case_df.groupby("pathway_stage")
        .agg(
            flow_rows=("flow_id", "count"),
            fraud_truth_rate=("target_is_fraud_truth", "mean"),
            avg_lifecycle_hours=("lifecycle_hours", "mean"),
        )
        .reset_index()
        .sort_values("flow_rows", ascending=False)
    )

    risk_band_df = (
        current_df.groupby("risk_band")
        .agg(
            flow_rows=("flow_id", "count"),
            fraud_truth_rate=("target_is_fraud_truth", "mean"),
            avg_score=("predicted_probability", "mean"),
        )
        .reset_index()
    )
    risk_band_df["risk_band"] = pd.Categorical(
        risk_band_df["risk_band"], categories=["High", "Medium", "Low"], ordered=True
    )
    risk_band_df = risk_band_df.sort_values("risk_band")

    weekly_trend_df = (
        base_df.groupby(["split_role", "flow_week_utc"])
        .agg(
            high_medium_share=("risk_band", lambda s: float(((s == "High") | (s == "Medium")).mean())),
            fraud_truth_rate=("target_is_fraud_truth", "mean"),
        )
        .reset_index()
    )

    top_priority_df = current_df[
        [
            "priority_rank",
            "flow_id",
            "risk_band",
            "cohort_label",
            "pathway_stage",
            "amount",
        ]
    ].head(8).copy()
    top_priority_df["flow_id"] = top_priority_df["flow_id"].astype(str).str[-8:]
    top_priority_df["cohort_label"] = top_priority_df["cohort_label"].map(short_cohort_label)
    top_priority_df["amount"] = top_priority_df["amount"].map(lambda v: f"{v:,.0f}")

    write_frame_outputs(
        cohort_share_df,
        METRICS_DIR / "04_dashboard_cohort_share.csv",
        METRICS_DIR / "04_dashboard_cohort_share.json",
    )
    write_frame_outputs(
        pathway_stage_df,
        METRICS_DIR / "05_dashboard_pathway_stage.csv",
        METRICS_DIR / "05_dashboard_pathway_stage.json",
    )
    write_frame_outputs(
        risk_band_df,
        METRICS_DIR / "06_dashboard_risk_band.csv",
        METRICS_DIR / "06_dashboard_risk_band.json",
    )

    # Page 1: Executive overview
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.4), gridspec_kw={"width_ratios": [1.05, 1.2, 1.0]})
    axes[0].axis("off")
    axes[0].text(0.0, 0.95, "Executive Overview", fontsize=20, fontweight="bold", ha="left", va="top")
    axes[0].text(
        0.0,
        0.82,
        "Current bounded view: latest scored test window from the governed selection.\n"
        "Previous window shown for immediate comparison only.",
        fontsize=11,
        ha="left",
        va="top",
    )
    kpis = [
        ("Flows in scope", comma(len(current_df)), comma(len(previous_df))),
        ("High-band workload", comma(len(current_high)), comma(len(previous_high))),
        ("High-band truth rate", short_pct(current_high_rate), short_pct(previous_high_rate)),
        ("Case-open rate", short_pct(current_case_open_rate), short_pct(previous_case_open_rate)),
    ]
    y = 0.62
    for label, current_value, previous_value in kpis:
        axes[0].text(0.02, y, label, fontsize=12, ha="left", va="center")
        axes[0].text(0.72, y, current_value, fontsize=12, fontweight="bold", ha="right", va="center")
        axes[0].text(0.98, y, previous_value, fontsize=11, color="#666666", ha="right", va="center")
        y -= 0.11
    axes[0].text(
        0.02,
        0.12,
        "Current view keeps the strong selected-model concentration:\n"
        f"High-band truth rate is {short_pct(current_high_rate)} with {len(current_high):,} flows.",
        fontsize=11,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    sns.lineplot(
        data=weekly_trend_df,
        x="flow_week_utc",
        y="high_medium_share",
        hue="split_role",
        marker="o",
        palette=["#6fa8dc", "#3d85c6"],
        ax=axes[1],
    )
    axes[1].set_title("Weekly Priority Share")
    axes[1].set_xlabel("Week")
    axes[1].set_ylabel("High + Medium share")
    axes[1].legend(title="", loc="best", fontsize=10)
    axes[1].tick_params(axis="x", rotation=30)

    sns.barplot(
        data=cohort_share_df,
        x="share",
        y="cohort_label",
        hue="cohort_label",
        palette="Blues_r",
        legend=False,
        ax=axes[2],
    )
    axes[2].set_title("Case-Selected Cohort Concentration")
    axes[2].set_xlabel("Share of case-selected flows")
    axes[2].set_ylabel("")
    for container in axes[2].containers:
        axes[2].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=4, fontsize=9)

    fig.suptitle("Dashboard Pack Page 1 - Executive Overview", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "executive_overview.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Page 2: Workflow and prioritisation
    fig, axes = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={"width_ratios": [1.0, 1.0, 1.25]})

    sns.barplot(
        data=pathway_stage_df,
        x="fraud_truth_rate",
        y="pathway_stage",
        hue="pathway_stage",
        palette="crest",
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Pathway Stage Truth Rate")
    axes[0].set_xlabel("Fraud-truth rate")
    axes[0].set_ylabel("")
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[short_pct(v) for v in container.datavalues], padding=4, fontsize=9)

    bars = axes[1].bar(
        risk_band_df["risk_band"].astype(str),
        risk_band_df["flow_rows"],
        color=["#1f4e79", "#6fa8dc", "#cfe2f3"],
    )
    axes[1].set_title("Risk-Band Workload")
    axes[1].set_xlabel("Risk band")
    axes[1].set_ylabel("Flows")
    for bar, val in zip(bars, risk_band_df["flow_rows"]):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height(), comma(val), ha="center", va="bottom", fontsize=9)
    ax2 = axes[1].twinx()
    ax2.plot(
        risk_band_df["risk_band"].astype(str),
        risk_band_df["fraud_truth_rate"],
        color="#c00000",
        marker="o",
        linewidth=2,
    )
    ax2.set_ylabel("Truth rate")
    ax2.set_ylim(0, max(risk_band_df["fraud_truth_rate"]) * 1.25)
    for x, yv in zip(risk_band_df["risk_band"].astype(str), risk_band_df["fraud_truth_rate"]):
        ax2.text(x, yv, short_pct(yv), color="#c00000", ha="center", va="bottom", fontsize=9)

    axes[2].axis("off")
    axes[2].set_title("Priority Table", loc="left", pad=12)
    table = axes[2].table(
        cellText=top_priority_df.values.tolist(),
        colLabels=["Rank", "Flow", "Band", "Cohort", "Stage", "Amount"],
        loc="center",
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.35)

    fig.suptitle("Dashboard Pack Page 2 - Workflow and Prioritisation", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "workflow_and_prioritisation.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Page 3: Explanation and drill-through
    fig, axes = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={"width_ratios": [1.0, 1.0, 1.25]})

    coeffs = top_coeffs_df.sort_values("abs_coefficient", ascending=True)
    sns.barplot(
        data=coeffs,
        x="abs_coefficient",
        y="feature",
        hue="feature",
        palette=["#cfe2f3"] * len(coeffs),
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Top Selected-Model Drivers")
    axes[0].set_xlabel("Absolute coefficient")
    axes[0].set_ylabel("")

    cohort_truth_df = (
        current_case_df.groupby("cohort_label")
        .agg(
            fraud_truth_rate=("target_is_fraud_truth", "mean"),
            avg_lifecycle_hours=("lifecycle_hours", "mean"),
            flow_rows=("flow_id", "count"),
        )
        .reset_index()
        .sort_values("avg_lifecycle_hours", ascending=False)
    )
    sns.scatterplot(
        data=cohort_truth_df,
        x="avg_lifecycle_hours",
        y="fraud_truth_rate",
        size="flow_rows",
        hue="cohort_label",
        sizes=(180, 900),
        palette="mako",
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Cohort Burden vs Value")
    axes[1].set_xlabel("Average lifecycle hours")
    axes[1].set_ylabel("Fraud-truth rate")
    axes[1].set_ylim(-0.05, 1.05)
    for _, row in cohort_truth_df.iterrows():
        axes[1].text(
            row["avg_lifecycle_hours"],
            row["fraud_truth_rate"],
            f"{row['cohort_label']}\n{short_pct(row['fraud_truth_rate'])}",
            fontsize=8.5,
            ha="left",
            va="bottom",
        )

    sample_drill = drillthrough_df.head(8).copy()
    sample_drill["flow_id"] = sample_drill["flow_id"].astype(str).str[-8:]
    sample_drill["cohort_label"] = sample_drill["cohort_label"].map(short_cohort_label)
    sample_drill["lifecycle_hours"] = sample_drill["lifecycle_hours"].fillna(0).round(0).astype(int)
    axes[2].axis("off")
    axes[2].set_title("Drill-Through Sample", loc="left", pad=12)
    drill_table = axes[2].table(
        cellText=sample_drill[
            ["priority_rank", "flow_id", "risk_band", "cohort_label", "pathway_stage", "lifecycle_hours"]
        ].values.tolist(),
        colLabels=["Rank", "Flow", "Band", "Cohort", "Stage", "Hours"],
        loc="center",
        cellLoc="left",
        colLoc="left",
    )
    drill_table.auto_set_font_size(False)
    drill_table.set_fontsize(8.5)
    drill_table.scale(1.0, 1.32)

    fig.suptitle("Dashboard Pack Page 3 - Explanation and Drill-Through", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "explanation_and_drillthrough.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    figure_manifest = {
        "generated_figures": [
            "executive_overview.png",
            "workflow_and_prioritisation.png",
            "explanation_and_drillthrough.png",
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(json.dumps(figure_manifest, indent=2), encoding="utf-8")

    top_case_cohort = cohort_share_df.iloc[0]
    top_pathway_stage = pathway_stage_df.iloc[0]
    top_priority_count = len(current_df[current_df["risk_band"].isin(["High", "Medium"])])

    write_md(
        ARTEFACT / "flow_dashboard_product_contract_v1.md",
        f"""
        # Flow Dashboard Product Contract v1

        Grain:
        - `flow_id`

        Intended pack:
        - one executive view
        - one workflow and prioritisation view
        - one explanation and drill-through view

        Allowed use:
        - decision-support reporting over governed model and cohort outputs
        - prioritisation discussion and monitoring

        Caveats:
        - this is a bounded reporting pack over validation and test windows only
        - it does not replace the governed model notes, caveats, or human review boundary
        """,
    )

    write_md(
        ARTEFACT / "dashboard_kpi_definitions_v1.md",
        """
        # Dashboard KPI Definitions v1

        Core KPIs:
        - `flows_in_scope`: total scored flows in the bounded reporting window
        - `high_band_flows`: scored flows in the selected High band
        - `medium_band_flows`: scored flows in the selected Medium band
        - `fraud_truth_rate`: authoritative fraud-truth rate in the bounded slice
        - `case_open_rate`: share of scored flows with opened cases
        - `high_band_truth_rate`: authoritative fraud-truth rate inside the selected High band

        Reuse rule:
        - KPI names and meanings must stay consistent across executive, workflow, and drill-through pages

        Audience rule:
        - executive view gets headline volume, band, and trend metrics first
        - workflow view gets stage, workload, and prioritisation metrics
        - drill-through view gets detailed cohort and explanation context
        """,
    )

    write_md(
        ARTEFACT / "dashboard_page_notes_v1.md",
        f"""
        # Dashboard Page Notes v1

        Page 1 - Executive overview:
        - current view compares the test window against the earlier validation window
        - headline view keeps focus on workload, High-band value, and case-open rate

        Page 2 - Workflow and prioritisation:
        - workflow pressure is read through pathway stages and current risk-band workload
        - prioritisation table is bounded to the highest-ranked current test flows

        Page 3 - Explanation and drill-through:
        - explanation shows the selected-model driver family
        - cohort contrast shows where value and burden separate
        - drill-through sample is bounded to the current high-priority queue
        """,
    )

    write_md(
        ARTEFACT / "dashboard_executive_brief_v1.md",
        f"""
        # Dashboard Executive Brief v1

        What changed:
        - the current bounded reporting window contains {comma(len(current_df))} scored flows
        - {comma(len(current_high))} are in the High band and {comma(len(current_medium))} are in the Medium band
        - the current High-band truth rate is {short_pct(current_high_rate)}

        Why it matters:
        - the selected score is concentrating authoritative fraud truth into a review-first workload rather than leaving value diffuse across the full population
        - the case-selected burden remains concentrated in `{top_case_cohort.cohort_label}`

        What to monitor next:
        - whether High + Medium share continues to hold steady
        - whether the largest case-selected cohort remains dominated by burden rather than value
        """,
    )

    write_md(
        ARTEFACT / "dashboard_operations_note_v1.md",
        f"""
        # Dashboard Operations Note v1

        Immediate attention area:
        - the current High + Medium queue contains {comma(top_priority_count)} flows
        - strongest review priority should remain the High band

        Current workflow signal:
        - the largest current case-selected pathway stage is `{top_pathway_stage.pathway_stage}`
        - its authoritative fraud-truth rate is {short_pct(float(top_pathway_stage.fraud_truth_rate))}

        Suggested action:
        - review the High band first
        - then use cohort and pathway context to separate high-value attention from high-burden low-value work
        """,
    )

    write_md(
        ARTEFACT / "dashboard_challenge_response_v1.md",
        """
        # Dashboard Challenge Response v1

        Why trust this pack?
        - it is built from governed model and pathway outputs rather than ad hoc chart logic
        - KPI definitions are shared across pages
        - the selected score already carries its own threshold and caveat notes

        What does this pack not claim?
        - it does not claim autonomous decisioning
        - it does not replace the underlying governed-model caveats
        - it does not claim a full enterprise BI estate

        What should a reader keep in mind?
        - High and Medium bands are prioritisation support, not automatic outcome decisions
        - drill-through tables are bounded examples, not the full operating universe
        """,
    )

    dashboard_pack_md = f"""
    # Dashboard Pack v1

    This pack operationalises the bounded governed model and pathway outputs into three audience-shaped reporting pages.

    ## Page 1 - Executive Overview

    ![Executive overview](figures/executive_overview.png)

    ## Page 2 - Workflow and Prioritisation

    ![Workflow and prioritisation](figures/workflow_and_prioritisation.png)

    ## Page 3 - Explanation and Drill-Through

    ![Explanation and drill-through](figures/explanation_and_drillthrough.png)
    """
    write_md(ARTEFACT / "dashboard_pack_v1.md", dashboard_pack_md)

    fact_pack = {
        "slice": "midlands_partnership_nhs_ft/06_dashboard_decision_support",
        "input_profile": records(input_profile_df),
        "output_profile": records(output_profile_df),
        "split_profile": records(split_profile_df),
        "current_window": {
            "split_role": "test",
            "flow_rows": int(len(current_df)),
            "high_band_rows": int(len(current_high)),
            "medium_band_rows": int(len(current_medium)),
            "high_band_truth_rate": current_high_rate,
            "case_open_rate": current_case_open_rate,
            "top_case_selected_cohort": str(top_case_cohort.cohort_label),
            "top_case_selected_cohort_share": float(top_case_cohort.share),
            "top_pathway_stage": str(top_pathway_stage.pathway_stage),
            "top_pathway_stage_truth_rate": float(top_pathway_stage.fraud_truth_rate),
        },
        "top_priority_queue_size": int(top_priority_count),
        "top_model_drivers": selected_model_fact["top_coefficients"],
        "assets": {
            "dashboard_base": str(DASHBOARD_BASE),
            "dashboard_summary": str(DASHBOARD_SUMMARY),
            "dashboard_drillthrough": str(DASHBOARD_DRILLTHROUGH),
            "executive_overview_figure": str(FIGURES_DIR / "executive_overview.png"),
            "workflow_figure": str(FIGURES_DIR / "workflow_and_prioritisation.png"),
            "explanation_figure": str(FIGURES_DIR / "explanation_and_drillthrough.png"),
            "dashboard_pack": str(ARTEFACT / "dashboard_pack_v1.md"),
        },
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    print("dashboard_decision_support build complete")


if __name__ == "__main__":
    main()
