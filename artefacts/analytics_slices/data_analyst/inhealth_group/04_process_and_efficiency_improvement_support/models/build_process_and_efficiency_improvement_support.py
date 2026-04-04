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
from matplotlib.ticker import FuncFormatter


BASE = Path(
    r"C:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system"
)
ARTEFACT = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\04_process_and_efficiency_improvement_support"
)
SQL_DIR = ARTEFACT / "sql"
EXTRACTS_DIR = ARTEFACT / "extracts"
METRICS_DIR = ARTEFACT / "metrics"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

SOURCE_ARTEFACT = (
    BASE
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\03_trend_risk_and_opportunity_identification\extracts"
)

TREND_COMPARE = SOURCE_ARTEFACT / "monthly_trend_compare_v1.parquet"
FOCUS_VIEW = SOURCE_ARTEFACT / "monthly_risk_opportunity_focus_v1.parquet"
MONTH_BAND_AGG = SOURCE_ARTEFACT / "trend_month_band_agg_v1.parquet"

EFFICIENCY_COMPARE = EXTRACTS_DIR / "efficiency_support_compare_v1.parquet"
TARGETED_REVIEW = EXTRACTS_DIR / "targeted_review_support_v1.parquet"
RELEASE_CHECKS = EXTRACTS_DIR / "improvement_release_checks_v1.parquet"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    return f"{value * 100:+.2f} pp"


def month_label(value: pd.Timestamp | str) -> str:
    return pd.to_datetime(value).strftime("%b %Y")


def sql_path(path: Path) -> str:
    return f"'{str(path).replace(chr(92), '/')}'"


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def render_sql(sql_text: str, replacements: dict[str, str]) -> str:
    rendered = sql_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def write_md(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def write_frame_outputs(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    df.to_csv(csv_path, index=False)
    json_path.write_text(
        df.to_json(orient="records", indent=2, date_format="iso"), encoding="utf-8"
    )


def ensure_dirs() -> None:
    for path in [EXTRACTS_DIR, METRICS_DIR, FIGURES_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def axis_pct(decimals: int = 1) -> FuncFormatter:
    return FuncFormatter(lambda value, _: f"{value:.{decimals}f}%")


def build_sql_outputs(con: duckdb.DuckDBPyConnection) -> None:
    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$focus_path": sql_path(FOCUS_VIEW),
        "$output_path": sql_path(EFFICIENCY_COMPARE),
    }
    con.execute(render_sql(read_sql("01_build_efficiency_support_compare.sql"), replacements))

    replacements = {
        "$trend_path": sql_path(TREND_COMPARE),
        "$efficiency_path": sql_path(EFFICIENCY_COMPARE),
        "$output_path": sql_path(TARGETED_REVIEW),
    }
    con.execute(render_sql(read_sql("02_build_targeted_review_support.sql"), replacements))

    replacements = {
        "$efficiency_path": sql_path(EFFICIENCY_COMPARE),
        "$review_path": sql_path(TARGETED_REVIEW),
        "$output_path": sql_path(RELEASE_CHECKS),
    }
    con.execute(render_sql(read_sql("03_build_improvement_release_checks.sql"), replacements))


def render_figures(review_df: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid", context="talk")
    blue = "#2f5b8f"
    blue_light = "#9eb6cf"
    red = "#c85a5a"
    green = "#4d8f6d"
    text = "#22313f"
    grid = "#d7dde5"

    plot_df = review_df.copy()
    plot_df["month_label"] = plot_df["month_start_date"].dt.strftime("%b %Y")

    fig, ax = plt.subplots(figsize=(10.0, 5.8), constrained_layout=True)
    ax.plot(
        plot_df["month_label"],
        plot_df["case_open_share"] * 100,
        marker="o",
        linewidth=2.4,
        markersize=8,
        color=red,
    )
    ax.plot(
        plot_df["month_label"],
        plot_df["truth_share"] * 100,
        marker="o",
        linewidth=2.4,
        markersize=8,
        color=green,
    )
    ax.fill_between(
        plot_df["month_label"],
        plot_df["case_open_share"] * 100,
        plot_df["truth_share"] * 100,
        color=red,
        alpha=0.10,
    )
    ax.set_ylabel("Share of monthly total (%)")
    ax.yaxis.set_major_formatter(axis_pct(1))
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    last = plot_df.iloc[-1]
    ax.annotate(
        f"Case work {last['case_open_share'] * 100:.2f}%",
        xy=(last["month_label"], last["case_open_share"] * 100),
        xytext=(8, 6),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=10,
        color=red,
    )
    ax.annotate(
        f"Truth {last['truth_share'] * 100:.2f}%",
        xy=(last["month_label"], last["truth_share"] * 100),
        xytext=(8, -10),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=10,
        color=green,
    )
    ax.annotate(
        f"Gap {last['burden_minus_yield_share'] * 100:+.2f} pp",
        xy=(last["month_label"], ((last["case_open_share"] + last["truth_share"]) / 2) * 100),
        xytext=(14, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=10,
        color=text,
    )
    fig.suptitle("50+ Burden Vs Yield", fontsize=18, color=text, y=1.01)
    fig.savefig(FIGURES_DIR / "focus_burden_vs_yield.png", bbox_inches="tight")
    plt.close(fig)

    latest = plot_df.iloc[-1]
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(12.4, 5.8), constrained_layout=True)

    left_labels = ["Case-open rate", "Truth quality"]
    left_values = [
        latest["case_open_change_from_start"] * 100,
        latest["truth_change_from_start"] * 100,
    ]
    left_colors = [blue, green]
    ax_left.barh(left_labels, left_values, color=left_colors, height=0.52)
    left_min = min(left_values)
    left_max = max(left_values)
    ax_left.set_xlim(left_min - 0.03, left_max + 0.03)
    for i, value in enumerate(left_values):
        ax_left.annotate(
            f"{value:+.2f} pp",
            xy=(value, i),
            xytext=(6 if value >= 0 else -6, 0),
            textcoords="offset points",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=10,
            color=text,
        )
    ax_left.axvline(0, color="#9aa5b1", linewidth=1.0)
    ax_left.set_title("Whole-lane Jan→Mar change", loc="left", fontsize=14, color=text, pad=8)
    ax_left.set_xlabel("Percentage points")
    ax_left.grid(axis="x", color=grid, linewidth=0.8)
    ax_left.spines[["top", "right"]].set_visible(False)

    right_labels = ["50+ burden gap", "50+ case-open gap", "50+ truth gap"]
    right_values = [
        latest["burden_minus_yield_share"] * 100,
        latest["case_open_gap_to_peer"] * 100,
        latest["case_truth_gap_to_peer"] * 100,
    ]
    right_colors = [red, red, blue]
    ax_right.barh(right_labels, right_values, color=right_colors, height=0.52)
    right_min = min(right_values)
    right_max = max(right_values)
    ax_right.set_xlim(right_min - 0.2, right_max + 0.2)
    for i, value in enumerate(right_values):
        ax_right.annotate(
            f"{value:+.2f} pp",
            xy=(value, i),
            xytext=(6 if value >= 0 else -6, 0),
            textcoords="offset points",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=10,
            color=text,
        )
    ax_right.axvline(0, color="#9aa5b1", linewidth=1.0)
    ax_right.set_title("Mar 2026 focus-band gaps", loc="left", fontsize=14, color=text, pad=8)
    ax_right.set_xlabel("Percentage points")
    ax_right.grid(axis="x", color=grid, linewidth=0.8)
    ax_right.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Why Targeted Review Beats Broad Escalation", fontsize=18, color=text, y=1.01)
    fig.savefig(FIGURES_DIR / "targeted_review_vs_broad_escalation.png", bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "figures": [
            {
                "file": "focus_burden_vs_yield.png",
                "purpose": "Show that the 50+ band persistently absorbs a larger share of case work than the share of truth outcomes it returns.",
            },
            {
                "file": "targeted_review_vs_broad_escalation.png",
                "purpose": "Show that whole-lane movement is small while the 50+ focus-band gaps remain materially larger, supporting targeted review over broad lane-wide action.",
            },
        ]
    }
    (FIGURES_DIR / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    start = time.perf_counter()

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    build_sql_outputs(con)

    efficiency_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(EFFICIENCY_COMPARE)}) ORDER BY month_start_date, priority_rank"
    ).df()
    review_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(TARGETED_REVIEW)}) ORDER BY month_start_date"
    ).df()
    release_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RELEASE_CHECKS)})"
    ).df()

    for df in [efficiency_df, review_df]:
        df["month_start_date"] = pd.to_datetime(df["month_start_date"])

    write_frame_outputs(
        efficiency_df,
        METRICS_DIR / "01_efficiency_support_compare.csv",
        METRICS_DIR / "01_efficiency_support_compare.json",
    )
    write_frame_outputs(
        review_df,
        METRICS_DIR / "02_targeted_review_support.csv",
        METRICS_DIR / "02_targeted_review_support.json",
    )
    write_frame_outputs(
        release_df,
        METRICS_DIR / "03_improvement_release_checks.csv",
        METRICS_DIR / "03_improvement_release_checks.json",
    )

    latest = review_df.iloc[-1]
    earliest = review_df.iloc[0]
    regeneration_seconds = time.perf_counter() - start

    fact_pack = {
        "slice": "inhealth_group/04_process_and_efficiency_improvement_support",
        "months_compared": [month_label(v) for v in review_df["month_start_date"].tolist()],
        "focus_band": str(latest["focus_band"]),
        "kpi_family_count": 4,
        "current_focus_flow_share": float(latest["flow_share"]),
        "current_focus_case_open_share": float(latest["case_open_share"]),
        "current_focus_truth_share": float(latest["truth_share"]),
        "current_focus_burden_minus_yield_share": float(latest["burden_minus_yield_share"]),
        "current_focus_case_open_gap_to_peer": float(latest["case_open_gap_to_peer"]),
        "current_focus_truth_gap_to_peer": float(latest["case_truth_gap_to_peer"]),
        "current_focus_truth_per_case_open": float(latest["truth_per_case_open"]),
        "overall_case_open_change_from_start": float(latest["case_open_change_from_start"]),
        "overall_truth_change_from_start": float(latest["truth_change_from_start"]),
        "release_checks_passed": int(release_df["passed_flag"].sum()),
        "release_check_count": int(len(release_df)),
        "regeneration_seconds": regeneration_seconds,
        "recommendation": "Review 50_plus queue case-opening or escalation rules before any broad lane-wide intervention.",
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    write_md(
        ARTEFACT / "improvement_question_note_v1.md",
        f"""
        # Improvement Question Note v1

        Analytical question:
        - does the recurring `{latest["focus_band"]}` pattern justify targeted process or efficiency review before any broad lane-wide intervention?

        Bounded answer:
        - the whole lane remains broadly stable from `{month_label(earliest["month_start_date"])}` to `{month_label(latest["month_start_date"])}`
        - the recurring issue remains concentrated in `{latest["focus_band"]}`
        - the strongest next step is targeted review, not broad escalation
        """,
    )

    write_md(
        ARTEFACT / "efficiency_interpretation_note_v1.md",
        f"""
        # Efficiency Interpretation Note v1

        Current-month reading:
        - `{latest["focus_band"]}` carries `{pct(float(latest["case_open_share"]))}` of case-opened workload
        - the same band returns only `{pct(float(latest["truth_share"]))}` of truth outcomes
        - the burden-minus-yield gap is `{pp(float(latest["burden_minus_yield_share"]))}`

        Interpretation:
        - the band keeps absorbing a larger share of case effort than the share of stronger outcomes it returns
        - that is the bounded efficiency-support signal in this slice
        - the output supports targeted review of the concentration pocket rather than a broad claim that the whole lane is inefficient
        """,
    )

    write_md(
        ARTEFACT / "targeted_review_recommendation_v1.md",
        f"""
        # Targeted Review Recommendation v1

        Recommendation:
        - review `{latest["focus_band"]}` queue case-opening or escalation rules before any broad lane-wide intervention

        Why this recommendation is proportionate:
        - whole-lane case-open movement from `{month_label(earliest["month_start_date"])}` to `{month_label(latest["month_start_date"])}` is only `{pp(float(latest["case_open_change_from_start"]))}`
        - whole-lane truth-quality movement over the same window is only `{pp(float(latest["truth_change_from_start"]))}`
        - current-month `{latest["focus_band"]}` case-open gap to peers is `{pp(float(latest["case_open_gap_to_peer"]))}`
        - current-month `{latest["focus_band"]}` truth-quality gap to peers is `{pp(float(latest["case_truth_gap_to_peer"]))}`
        """,
    )

    write_md(
        ARTEFACT / "challenge_response_note_v1.md",
        f"""
        # Challenge Response Note v1

        Challenge:
        - why recommend targeted review instead of broad lane-wide action?

        Response:
        - the whole lane is broadly stable over the bounded three-month window
        - the recurring issue is concentrated in `{latest["focus_band"]}`, not spread evenly across all bands
        - the focus band consumes `{pct(float(latest["case_open_share"]))}` of case-opened workload but returns `{pct(float(latest["truth_share"]))}` of truth outcomes
        - that makes targeted review the most defensible next step from the current evidence

        Boundary:
        - this slice does not prove that the review was already completed
        - this slice does not claim that efficiency gains were already achieved
        """,
    )

    write_md(
        ARTEFACT / "improvement_support_caveats_v1.md",
        f"""
        # Improvement Support Caveats v1

        Caveats:
        - this slice reuses the bounded `{month_label(earliest["month_start_date"])} -> {month_label(latest["month_start_date"])}` window only
        - the recommendation is a review recommendation, not a delivered operational change
        - the slice is strongest as targeted improvement-support evidence, not as proof of achieved process improvement
        - no broad lane-wide intervention is justified from this bounded evidence alone
        """,
    )

    write_md(
        ARTEFACT / "README_process_efficiency_regeneration.md",
        f"""
        # Process Efficiency Regeneration

        Regeneration posture:
        - compact `3.D` outputs reused first
        - heavy raw rescans not required for this slice
        - heavy work stays in `DuckDB`
        - Python reads only compact shaped outputs after SQL reduction

        Execution order:
        1. build `efficiency_support_compare_v1.parquet`
        2. build `targeted_review_support_v1.parquet`
        3. build `improvement_release_checks_v1.parquet`
        4. regenerate notes and figures

        Current regeneration time:
        - about `{regeneration_seconds:.1f}` seconds
        """,
    )

    write_md(
        ARTEFACT / "process_efficiency_evidence_pack_v1.md",
        f"""
        # Process Efficiency Evidence Pack v1

        Whole-lane context:
        - case-open movement from `{month_label(earliest["month_start_date"])}` to `{month_label(latest["month_start_date"])}` is `{pp(float(latest["case_open_change_from_start"]))}`
        - truth-quality movement over the same window is `{pp(float(latest["truth_change_from_start"]))}`
        - the lane remains broadly stable at topline

        Concentrated efficiency-support signal:
        - `{latest["focus_band"]}` carries `{pct(float(latest["case_open_share"]))}` of current-month case-opened workload
        - `{latest["focus_band"]}` returns `{pct(float(latest["truth_share"]))}` of current-month truth outcomes
        - the burden-minus-yield gap is `{pp(float(latest["burden_minus_yield_share"]))}`
        - current-month case-open gap to peers is `{pp(float(latest["case_open_gap_to_peer"]))}`
        - current-month truth-quality gap to peers is `{pp(float(latest["case_truth_gap_to_peer"]))}`

        Bounded recommendation:
        - review `{latest["focus_band"]}` queue case-opening or escalation rules before broad lane-wide intervention
        """,
    )

    render_figures(review_df)


if __name__ == "__main__":
    main()
