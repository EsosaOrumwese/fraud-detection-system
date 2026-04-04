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
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\01_reporting_support_for_operational_and_regional_teams"
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

FLOW_PATH = RUN_BASE / "s2_flow_anchor_baseline_6B"
CASE_PATH = RUN_BASE / "s4_case_timeline_6B"
TRUTH_PATH = RUN_BASE / "s4_flow_truth_labels_6B"

PRIOR_MONTH = "2026-02-01"
CURRENT_MONTH = "2026-03-01"

MONTH_BAND_AGG = EXTRACTS_DIR / "programme_month_band_agg_v1.parquet"
MONTHLY_SUMMARY = EXTRACTS_DIR / "programme_monthly_summary_v1.parquet"
FOLLOW_UP = EXTRACTS_DIR / "programme_ad_hoc_follow_up_v1.parquet"
RELEASE_CHECKS = EXTRACTS_DIR / "programme_release_checks_v1.parquet"


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
        "$prior_month": PRIOR_MONTH,
        "$current_month": CURRENT_MONTH,
        "$output_path": sql_path(MONTH_BAND_AGG),
    }
    con.execute(render_sql(read_sql("01_build_programme_month_band_agg.sql"), replacements))

    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$output_path": sql_path(MONTHLY_SUMMARY),
    }
    con.execute(render_sql(read_sql("02_build_programme_monthly_summary.sql"), replacements))

    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$output_path": sql_path(FOLLOW_UP),
    }
    con.execute(render_sql(read_sql("03_build_programme_ad_hoc_follow_up.sql"), replacements))

    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$summary_path": sql_path(MONTHLY_SUMMARY),
        "$follow_up_path": sql_path(FOLLOW_UP),
        "$output_path": sql_path(RELEASE_CHECKS),
    }
    con.execute(render_sql(read_sql("04_build_programme_release_checks.sql"), replacements))

    month_band_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(MONTH_BAND_AGG)}) ORDER BY month_start_date, amount_band"
    ).df()
    summary_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(MONTHLY_SUMMARY)})"
    ).df()
    follow_up_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(FOLLOW_UP)}) ORDER BY priority_rank"
    ).df()
    release_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RELEASE_CHECKS)})"
    ).df()

    scope_profile_df = con.execute(
        f"""
        WITH flow_month_counts AS (
            SELECT
                DATE_TRUNC('month', ts_utc::TIMESTAMP) AS month_start,
                COUNT(*) AS flow_rows
            FROM parquet_scan({sql_path(FLOW_PATH)})
            WHERE DATE_TRUNC('month', ts_utc::TIMESTAMP) IN (DATE '{PRIOR_MONTH}', DATE '{CURRENT_MONTH}')
            GROUP BY 1
        ),
        agg_coverage AS (
            SELECT
                month_start_date,
                SUM(flow_rows) AS flow_rows,
                SUM(case_opened_flow_rows) AS case_opened_flow_rows,
                SUM(truth_linked_flow_rows) AS truth_linked_flow_rows
            FROM read_parquet({sql_path(MONTH_BAND_AGG)})
            GROUP BY 1
        )
        SELECT
            c.month_start AS month_start_date,
            c.flow_rows AS raw_flow_rows,
            a.case_opened_flow_rows,
            a.truth_linked_flow_rows,
            CAST(a.case_opened_flow_rows AS DOUBLE) / NULLIF(a.flow_rows, 0) AS case_link_rate,
            CAST(a.truth_linked_flow_rows AS DOUBLE) / NULLIF(a.flow_rows, 0) AS truth_link_rate
        FROM flow_month_counts c
        LEFT JOIN agg_coverage a
            ON c.month_start = a.month_start_date
        ORDER BY c.month_start
        """
    ).df()

    write_frame_outputs(
        scope_profile_df,
        METRICS_DIR / "00_scope_profile.csv",
        METRICS_DIR / "00_scope_profile.json",
    )
    write_frame_outputs(
        summary_df,
        METRICS_DIR / "01_programme_monthly_summary.csv",
        METRICS_DIR / "01_programme_monthly_summary.json",
    )
    write_frame_outputs(
        follow_up_df,
        METRICS_DIR / "02_programme_ad_hoc_follow_up.csv",
        METRICS_DIR / "02_programme_ad_hoc_follow_up.json",
    )
    write_frame_outputs(
        release_df,
        METRICS_DIR / "03_programme_release_checks.csv",
        METRICS_DIR / "03_programme_release_checks.json",
    )

    summary = summary_df.iloc[0]
    top_follow_up = follow_up_df.loc[follow_up_df["priority_attention_flag"] == 1].iloc[0]
    prior_month_name = month_label(PRIOR_MONTH)
    current_month_name = month_label(CURRENT_MONTH)
    regeneration_seconds = time.perf_counter() - start

    fact_pack = {
        "slice": "inhealth_group/01_reporting_support_for_operational_and_regional_teams",
        "prior_month": PRIOR_MONTH,
        "current_month": CURRENT_MONTH,
        "reporting_cadence": "monthly",
        "audiences": ["operations", "regional oversight"],
        "kpi_family_count": 4,
        "monthly_flow_rows": int(round(float(summary["flow_rows"]))),
        "prior_month_flow_rows": int(round(float(summary["prior_flow_rows"]))),
        "current_case_open_rate": float(summary["case_open_rate"]),
        "prior_case_open_rate": float(summary["prior_case_open_rate"]),
        "current_case_truth_rate": float(summary["case_truth_rate"]),
        "prior_case_truth_rate": float(summary["prior_case_truth_rate"]),
        "current_truth_link_rate": float(summary["truth_link_rate"]),
        "current_fifty_plus_share": float(summary["fifty_plus_share"]),
        "top_follow_up_band": {
            "amount_band": str(top_follow_up["amount_band"]),
            "case_open_rate": float(top_follow_up["case_open_rate"]),
            "case_truth_rate": float(top_follow_up["case_truth_rate"]),
            "flow_share": float(top_follow_up["flow_share"]),
        },
        "release_checks_passed": int(release_df["passed_flag"].sum()),
        "release_check_count": int(len(release_df)),
        "regeneration_seconds": regeneration_seconds,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    write_md(
        ARTEFACT / "programme_monthly_reporting_requirements_v1.md",
        f"""
        # Programme Monthly Reporting Requirements v1

        Reporting lane:
        - one bounded monthly reporting cycle for a programme-style operational lane

        Audiences:
        - operations
        - regional or programme oversight

        Reporting purpose:
        - give operations a stable monthly reading of current workload conversion and outcome quality
        - give regional readers a compact month-on-month view built from the same governed logic
        - answer one realistic follow-up need without redefining the KPI logic

        Current comparison window:
        - prior month: `{prior_month_name}`
        - current month: `{current_month_name}`

        Current follow-up emphasis:
        - the `{short_band(str(top_follow_up["amount_band"]))}` band remains the strongest follow-up cut because it opens to case work at {short_pct(float(top_follow_up["case_open_rate"]))} while returning only {short_pct(float(top_follow_up["case_truth_rate"]))} truth quality across {short_pct(float(top_follow_up["flow_share"]))} of current-month flow volume
        """,
    )

    write_md(
        ARTEFACT / "programme_kpi_definition_note_v1.md",
        f"""
        # Programme KPI Definition Note v1

        KPI families:
        - `flow_rows`: monthly bounded workflow-entry volume
        - `case_open_rate`: share of flows that convert into case-opened work
        - `case_truth_rate`: authoritative truth quality on case-opened flows
        - `fifty_plus_share`: concentration of flow volume in the `50+` amount band, used as a stable follow-up lens rather than a broad performance claim

        Supporting control metric:
        - `truth_link_rate`: coverage of authoritative truth linkage across the bounded monthly slice

        Current month window:
        - `{current_month_name}`

        Prior month window:
        - `{prior_month_name}`
        """,
    )

    write_md(
        ARTEFACT / "programme_audience_usage_note_v1.md",
        f"""
        # Programme Audience Usage Note v1

        Operations should look at first:
        - current-month `case_open_rate`
        - current-month `case_truth_rate`
        - the follow-up cut showing which segment deserves the next reporting question

        Regional or programme oversight should look at first:
        - month-on-month movement in `flow_rows`
        - month-on-month movement in conversion and truth quality
        - whether the same governed KPI logic supports both the recurring monthly pack and the follow-up output

        What not to overread:
        - this slice proves dependable monthly and ad hoc reporting support for one bounded lane
        - it does not claim broad patient-level dataset stewardship, which belongs to the next InHealth responsibility lane
        """,
    )

    write_md(
        ARTEFACT / "programme_reporting_run_checklist_v1.md",
        f"""
        # Programme Reporting Run Checklist v1

        1. Confirm the monthly window is still bounded to `{prior_month_name}` and `{current_month_name}` for the current slice run.
        2. Run the month-band aggregate build in SQL before any Python reporting step.
        3. Confirm the monthly summary output contains `1` current row with populated core metrics.
        4. Confirm the ad hoc follow-up output contains `4` amount-band rows and one clear priority band.
        5. Confirm the release checks pass before figures or notes are regenerated.
        6. Confirm the follow-up output uses the same KPI definitions as the monthly pack.
        """,
    )

    write_md(
        ARTEFACT / "programme_reporting_caveats_v1.md",
        f"""
        # Programme Reporting Caveats v1

        This slice is intentionally bounded:
        - monthly comparison only: `{prior_month_name}` versus `{current_month_name}`
        - one programme-style lane only
        - one follow-up dimension only: amount band

        This slice proves:
        - dependable recurring monthly reporting from governed logic
        - one realistic follow-up reporting cut from the same governed base

        This slice does not prove:
        - broad patient-level stewardship
        - a full regional reporting estate
        - external or board-grade reporting
        """,
    )

    write_md(
        ARTEFACT / "README_programme_reporting_regeneration.md",
        f"""
        # Programme Reporting Regeneration README

        Regeneration posture:
        - heavy work stays in `DuckDB`
        - raw parquet is scanned only through bounded SQL
        - Python reads only compact outputs after SQL reduction

        Execution window:
        - prior month: `{prior_month_name}`
        - current month: `{current_month_name}`

        Regenerated outputs:
        - `programme_month_band_agg_v1.parquet`
        - `programme_monthly_summary_v1.parquet`
        - `programme_ad_hoc_follow_up_v1.parquet`
        - `programme_release_checks_v1.parquet`
        """,
    )

    write_md(
        ARTEFACT / "programme_monthly_reporting_pack_v1.md",
        f"""
        # Programme Monthly Reporting Pack v1

        Monthly reporting position:
        - current month: `{current_month_name}`
        - prior month: `{prior_month_name}`
        - current flow volume: `{comma(float(summary["flow_rows"]))}`
        - current case-open rate: `{pct(float(summary["case_open_rate"]))}`
        - current truth quality: `{pct(float(summary["case_truth_rate"]))}`
        - current truth-link coverage: `{pct(float(summary["truth_link_rate"]))}`

        Month-on-month movement:
        - flow volume delta: `{comma(float(summary["flow_rows_delta"]))}`
        - case-open rate delta: `{(float(summary["case_open_rate_delta"]) * 100):.2f} pp`
        - truth quality delta: `{(float(summary["case_truth_rate_delta"]) * 100):.2f} pp`
        - `50+` share delta: `{(float(summary["fifty_plus_share_delta"]) * 100):.2f} pp`

        Operational note:
        - the monthly lane remains broadly stable in conversion and truth quality, but the `{short_band(str(top_follow_up["amount_band"]))}` band remains the most useful follow-up cut because it carries the highest case-open rate at `{pct(float(top_follow_up["case_open_rate"]))}` while trailing the other bands on truth quality at `{pct(float(top_follow_up["case_truth_rate"]))}`
        """,
    )

    write_md(
        ARTEFACT / "programme_ad_hoc_follow_up_pack_v1.md",
        f"""
        # Programme Ad Hoc Follow-Up Pack v1

        Follow-up question:
        - which current-month segment is the most useful next reporting cut for operational and regional readers?

        Selected current-month follow-up:
        - `{short_band(str(top_follow_up["amount_band"]))}` is the priority follow-up band
        - flow share: `{pct(float(top_follow_up["flow_share"]))}`
        - case-open rate: `{pct(float(top_follow_up["case_open_rate"]))}`
        - truth quality: `{pct(float(top_follow_up["case_truth_rate"]))}`

        Why this follow-up is useful:
        - it is derived from the same governed monthly KPI base as the recurring pack
        - it answers a realistic next question without redefining the metrics
        - it gives operations and regional oversight a common follow-up view from the same reporting logic
        """,
    )

    # Figure 1: monthly position and movement
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    axes[0].bar(
        [prior_month_name, current_month_name],
        [float(summary["prior_flow_rows"]), float(summary["flow_rows"])],
        color=["#AAB7C4", "#2E5B88"],
    )
    axes[0].set_title("Monthly Flow Volume")
    axes[0].set_ylabel("Flow rows")
    axes[0].ticklabel_format(style="plain", axis="y")

    delta_df = pd.DataFrame(
        {
            "metric": ["Case-open rate", "Truth quality", "50+ share"],
            "delta_pp": [
                float(summary["case_open_rate_delta"]) * 100,
                float(summary["case_truth_rate_delta"]) * 100,
                float(summary["fifty_plus_share_delta"]) * 100,
            ],
        }
    )
    axes[1].barh(
        delta_df["metric"],
        delta_df["delta_pp"],
        color=["#4C78A8" if value >= 0 else "#D95F5F" for value in delta_df["delta_pp"]],
    )
    axes[1].axvline(0, color="#444444", linewidth=1)
    axes[1].set_title("Change From Prior Month")
    axes[1].set_xlabel("Percentage points")

    fig.suptitle(f"Monthly Position: {current_month_name} vs {prior_month_name}", fontsize=16, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "monthly_position_and_movement.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: follow-up by segment
    follow_plot = follow_up_df.copy()
    follow_plot["label"] = follow_plot["amount_band"].map(short_band)
    fig, ax = plt.subplots(figsize=(10, 6))
    y_positions = list(range(len(follow_plot)))
    for idx, row in follow_plot.iterrows():
        color = "#D95F5F" if int(row["priority_attention_flag"]) == 1 else "#7A8FA6"
        ax.plot(
            [float(row["case_truth_rate"]) * 100, float(row["case_open_rate"]) * 100],
            [idx, idx],
            color=color,
            linewidth=3,
            solid_capstyle="round",
        )
        ax.scatter(float(row["case_truth_rate"]) * 100, idx, color="#2E5B88", s=70, zorder=3)
        ax.scatter(float(row["case_open_rate"]) * 100, idx, color="#D95F5F", s=70, zorder=3)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(follow_plot["label"])
    ax.set_xlabel("Rate (%)")
    ax.set_title(f"Current-Month Follow-Up Cut: {current_month_name}")
    ax.text(0.01, 1.02, "Blue = truth quality, Red = case-open rate", transform=ax.transAxes, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "current_month_follow_up_by_segment.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    figure_manifest = {
        "figures": [
            {
                "file": "monthly_position_and_movement.png",
                "purpose": "show current versus prior month position without forcing unlike KPI levels onto one axis",
            },
            {
                "file": "current_month_follow_up_by_segment.png",
                "purpose": "show the bounded ad hoc follow-up cut and identify the most useful current-month segment for next reporting attention",
            },
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(json.dumps(figure_manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
