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
    / r"artefacts\analytics_slices\data_analyst\inhealth_group\03_trend_risk_and_opportunity_identification"
)
SQL_DIR = ARTEFACT / "sql"
EXTRACTS_DIR = ARTEFACT / "extracts"
METRICS_DIR = ARTEFACT / "metrics"
FIGURES_DIR = ARTEFACT / "figures"
LOGS_DIR = ARTEFACT / "logs"

RUN_BASE = (
    BASE
    / r"runs\local_full_run-7\a3bd8cac9a4284cd36072c6b9624a0c1\data\layer3\6B"
)

FLOW_PATH = RUN_BASE / "s2_flow_anchor_baseline_6B"
CASE_PATH = RUN_BASE / "s4_case_timeline_6B"
TRUTH_PATH = RUN_BASE / "s4_flow_truth_labels_6B"

MONTH_1 = "2026-01-01"
MONTH_2 = "2026-02-01"
MONTH_3 = "2026-03-01"

MONTH_BAND_AGG = EXTRACTS_DIR / "trend_month_band_agg_v1.parquet"
TREND_COMPARE = EXTRACTS_DIR / "monthly_trend_compare_v1.parquet"
FOCUS_VIEW = EXTRACTS_DIR / "monthly_risk_opportunity_focus_v1.parquet"
RELEASE_CHECKS = EXTRACTS_DIR / "trend_release_checks_v1.parquet"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def short_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def month_label(value: str) -> str:
    return pd.to_datetime(value).strftime("%b %Y")


def short_band(value: str) -> str:
    return {
        "under_10": "<10",
        "10_to_25": "10-25",
        "25_to_50": "25-50",
        "50_plus": "50+",
    }.get(value, value)


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


def build_sql_outputs(con: duckdb.DuckDBPyConnection) -> None:
    replacements = {
        "$flow_path": sql_path(FLOW_PATH),
        "$case_path": sql_path(CASE_PATH),
        "$truth_path": sql_path(TRUTH_PATH),
        "$month_1": MONTH_1,
        "$month_2": MONTH_2,
        "$month_3": MONTH_3,
        "$output_path": sql_path(MONTH_BAND_AGG),
    }
    con.execute(render_sql(read_sql("01_build_trend_month_band_agg.sql"), replacements))

    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$output_path": sql_path(TREND_COMPARE),
    }
    con.execute(render_sql(read_sql("02_build_monthly_trend_compare.sql"), replacements))

    replacements = {
        "$agg_path": sql_path(MONTH_BAND_AGG),
        "$output_path": sql_path(FOCUS_VIEW),
    }
    con.execute(render_sql(read_sql("03_build_monthly_risk_opportunity_focus.sql"), replacements))

    replacements = {
        "$trend_path": sql_path(TREND_COMPARE),
        "$focus_path": sql_path(FOCUS_VIEW),
        "$output_path": sql_path(RELEASE_CHECKS),
    }
    con.execute(render_sql(read_sql("04_build_trend_release_checks.sql"), replacements))


def render_figures(trend_df: pd.DataFrame, focus_df: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid", context="talk")
    blue = "#2f5b8f"
    blue_light = "#9eb6cf"
    red = "#c85a5a"
    green = "#4d8f6d"
    green_light = "#b7d3c1"
    grid = "#d7dde5"
    text = "#22313f"

    trend_plot = trend_df.copy()
    trend_plot["month_label"] = trend_plot["month_start_date"].dt.strftime("%b %Y")

    fig, axes = plt.subplots(3, 1, figsize=(10.8, 8.4), constrained_layout=True)

    axes[0].bar(
        trend_plot["month_label"],
        trend_plot["flow_rows"] / 1_000_000,
        color=[blue_light, blue_light, blue],
        width=0.58,
    )
    for x, y in zip(trend_plot["month_label"], trend_plot["flow_rows"] / 1_000_000):
        axes[0].text(x, y + 0.45, f"{y:.2f}M", ha="center", va="bottom", fontsize=10, color=text)
    axes[0].set_title("Monthly Flow Volume")
    axes[0].set_ylabel("Flows (millions)")
    axes[0].grid(axis="y", color=grid, linewidth=0.8)
    axes[0].spines[["top", "right"]].set_visible(False)

    axes[1].plot(
        trend_plot["month_label"],
        trend_plot["case_open_rate"] * 100,
        marker="o",
        color=blue,
        linewidth=2.2,
        markersize=8,
    )
    for x, y in zip(trend_plot["month_label"], trend_plot["case_open_rate"] * 100):
        axes[1].text(x, y + 0.02, f"{y:.2f}%", ha="center", va="bottom", fontsize=10, color=text)
    axes[1].set_title("Overall Case-open Rate")
    axes[1].set_ylabel("Rate (%)")
    axes[1].grid(axis="y", color=grid, linewidth=0.8)
    axes[1].spines[["top", "right"]].set_visible(False)

    axes[2].plot(
        trend_plot["month_label"],
        trend_plot["case_truth_rate"] * 100,
        marker="o",
        color=green,
        linewidth=2.2,
        markersize=8,
    )
    for x, y in zip(trend_plot["month_label"], trend_plot["case_truth_rate"] * 100):
        axes[2].text(x, y + 0.03, f"{y:.2f}%", ha="center", va="bottom", fontsize=10, color=text)
    axes[2].set_title("Overall Truth Quality")
    axes[2].set_ylabel("Rate (%)")
    axes[2].set_xlabel("Month")
    axes[2].grid(axis="y", color=grid, linewidth=0.8)
    axes[2].spines[["top", "right"]].set_visible(False)

    fig.suptitle("Monthly Trend Context", fontsize=18, color=text, y=1.02)
    fig.savefig(FIGURES_DIR / "monthly_trend_context.png", bbox_inches="tight")
    plt.close(fig)

    focus_top = focus_df.loc[focus_df["priority_attention_flag"] == 1].copy()
    focus_top["month_label"] = focus_top["month_start_date"].dt.strftime("%b %Y")

    fig, (ax_case, ax_truth) = plt.subplots(1, 2, figsize=(12.6, 5.6), constrained_layout=True)

    ax_case.plot(
        focus_top["month_label"],
        focus_top["case_open_rate"] * 100,
        marker="o",
        color=red,
        linewidth=2.2,
        markersize=8,
        label="50+ case-open rate",
    )
    ax_case.plot(
        focus_top["month_label"],
        focus_top["peer_case_open_rate"] * 100,
        marker="o",
        color=blue_light,
        linewidth=2.2,
        markersize=8,
        label="Peer average",
    )
    for _, row in focus_top.iterrows():
        ax_case.text(
            row["month_label"],
            row["case_open_rate"] * 100 + 0.03,
            f"{row['case_open_rate'] * 100:.2f}%",
            ha="center",
            va="bottom",
            fontsize=9.8,
            color=red,
        )
        ax_case.text(
            row["month_label"],
            row["peer_case_open_rate"] * 100 - 0.05,
            f"{row['peer_case_open_rate'] * 100:.2f}%",
            ha="center",
            va="top",
            fontsize=9.8,
            color=blue,
        )
    ax_case.set_title("50+ Case-open Rate Vs Peer Average")
    ax_case.set_ylabel("Rate (%)")
    ax_case.grid(axis="y", color=grid, linewidth=0.8)
    ax_case.spines[["top", "right"]].set_visible(False)
    ax_case.legend(frameon=False, loc="lower right", fontsize=9)

    ax_truth.plot(
        focus_top["month_label"],
        focus_top["case_truth_rate"] * 100,
        marker="o",
        color=red,
        linewidth=2.2,
        markersize=8,
        label="50+ truth quality",
    )
    ax_truth.plot(
        focus_top["month_label"],
        focus_top["peer_case_truth_rate"] * 100,
        marker="o",
        color=green_light,
        linewidth=2.2,
        markersize=8,
        label="Peer average",
    )
    for _, row in focus_top.iterrows():
        ax_truth.text(
            row["month_label"],
            row["case_truth_rate"] * 100 - 0.05,
            f"{row['case_truth_rate'] * 100:.2f}%",
            ha="center",
            va="top",
            fontsize=9.8,
            color=red,
        )
        ax_truth.text(
            row["month_label"],
            row["peer_case_truth_rate"] * 100 + 0.03,
            f"{row['peer_case_truth_rate'] * 100:.2f}%",
            ha="center",
            va="bottom",
            fontsize=9.8,
            color=green,
        )
    ax_truth.set_title("50+ Truth Quality Vs Peer Average")
    ax_truth.set_ylabel("Rate (%)")
    ax_truth.grid(axis="y", color=grid, linewidth=0.8)
    ax_truth.spines[["top", "right"]].set_visible(False)
    ax_truth.legend(frameon=False, loc="lower right", fontsize=9)

    fig.suptitle("Persistent Risk Focus: 50+ Vs The Rest Of The Lane", fontsize=18, color=text, y=1.02)
    fig.savefig(FIGURES_DIR / "risk_or_opportunity_focus.png", bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "figures": [
            {
                "file": "monthly_trend_context.png",
                "purpose": "Show the rolling three-month overall trend and confirm that the topline is broadly stable rather than sharply deteriorating.",
            },
            {
                "file": "risk_or_opportunity_focus.png",
                "purpose": "Show that 50+ remains the persistent risk pocket when compared with the rest of the lane across the rolling window.",
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

    month_band_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(MONTH_BAND_AGG)}) ORDER BY month_start_date, amount_band"
    ).df()
    trend_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(TREND_COMPARE)}) ORDER BY month_start_date"
    ).df()
    focus_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(FOCUS_VIEW)}) ORDER BY month_start_date, priority_rank"
    ).df()
    release_df = con.execute(
        f"SELECT * FROM read_parquet({sql_path(RELEASE_CHECKS)})"
    ).df()

    for df in [month_band_df, trend_df, focus_df]:
        df["month_start_date"] = pd.to_datetime(df["month_start_date"])

    write_frame_outputs(
        month_band_df,
        METRICS_DIR / "01_trend_month_band_agg.csv",
        METRICS_DIR / "01_trend_month_band_agg.json",
    )
    write_frame_outputs(
        trend_df,
        METRICS_DIR / "02_monthly_trend_compare.csv",
        METRICS_DIR / "02_monthly_trend_compare.json",
    )
    write_frame_outputs(
        focus_df,
        METRICS_DIR / "03_monthly_risk_opportunity_focus.csv",
        METRICS_DIR / "03_monthly_risk_opportunity_focus.json",
    )
    write_frame_outputs(
        release_df,
        METRICS_DIR / "04_trend_release_checks.csv",
        METRICS_DIR / "04_trend_release_checks.json",
    )

    trend_df["month_label"] = trend_df["month_start_date"].dt.strftime("%b %Y")
    focus_top = focus_df.loc[focus_df["priority_attention_flag"] == 1].copy()
    focus_top["month_label"] = focus_top["month_start_date"].dt.strftime("%b %Y")
    latest = trend_df.iloc[-1]
    earliest = trend_df.iloc[0]
    latest_focus = focus_top.iloc[-1]

    regeneration_seconds = time.perf_counter() - start

    fact_pack = {
        "slice": "inhealth_group/03_trend_risk_and_opportunity_identification",
        "months_compared": trend_df["month_label"].tolist(),
        "month_count": int(len(trend_df)),
        "kpi_family_count": 4,
        "earliest_flow_rows": int(round(float(earliest["flow_rows"]))),
        "latest_flow_rows": int(round(float(latest["flow_rows"]))),
        "earliest_case_open_rate": float(earliest["case_open_rate"]),
        "latest_case_open_rate": float(latest["case_open_rate"]),
        "earliest_case_truth_rate": float(earliest["case_truth_rate"]),
        "latest_case_truth_rate": float(latest["case_truth_rate"]),
        "latest_fifty_plus_share": float(latest["fifty_plus_share"]),
        "persistent_focus_band": str(latest_focus["amount_band"]),
        "persistent_focus_case_open_rate": float(latest_focus["case_open_rate"]),
        "persistent_focus_peer_case_open_rate": float(latest_focus["peer_case_open_rate"]),
        "persistent_focus_truth_rate": float(latest_focus["case_truth_rate"]),
        "persistent_focus_peer_truth_rate": float(latest_focus["peer_case_truth_rate"]),
        "release_checks_passed": int(release_df["passed_flag"].sum()),
        "release_check_count": int(len(release_df)),
        "regeneration_seconds": regeneration_seconds,
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(json.dumps(fact_pack, indent=2), encoding="utf-8")

    write_md(
        ARTEFACT / "trend_question_note_v1.md",
        f"""
        # Trend Question Note v1

        Analytical question:
        - over the rolling `{month_label(MONTH_1)} -> {month_label(MONTH_3)}` window, does the programme lane show broad deterioration, broad improvement, or a concentrated pattern that deserves attention first?

        Bounded answer:
        - the topline remains broadly stable
        - the strongest recurring risk pocket remains the `{short_band(str(latest_focus["amount_band"]))}` band
        - that band opens more aggressively than the rest of the lane while continuing to return weaker truth quality
        """,
    )

    write_md(
        ARTEFACT / "trend_reading_note_v1.md",
        f"""
        # Trend Reading Note v1

        Rolling monthly reading:
        - flow volume moves from `{month_label(MONTH_1)}` `{int(round(float(earliest["flow_rows"]))):,}` to `{month_label(MONTH_3)}` `{int(round(float(latest["flow_rows"]))):,}`
        - overall case-open rate moves only from `{pct(float(earliest["case_open_rate"]))}` to `{pct(float(latest["case_open_rate"]))}`
        - overall truth quality moves only from `{pct(float(earliest["case_truth_rate"]))}` to `{pct(float(latest["case_truth_rate"]))}`

        Interpretation:
        - the rolling window does not support a broad deterioration story
        - the strongest analytical value comes from identifying the persistent concentrated risk pocket rather than escalating the whole lane
        """,
    )

    write_md(
        ARTEFACT / "risk_or_opportunity_note_v1.md",
        f"""
        # Risk Or Opportunity Note v1

        Selected focus:
        - persistent risk pocket in `{short_band(str(latest_focus["amount_band"]))}`

        Current-month evidence:
        - case-open rate `{pct(float(latest_focus["case_open_rate"]))}` versus peer average `{pct(float(latest_focus["peer_case_open_rate"]))}`
        - truth quality `{pct(float(latest_focus["case_truth_rate"]))}` versus peer average `{pct(float(latest_focus["peer_case_truth_rate"]))}`
        - flow share `{pct(float(latest["fifty_plus_share"]))}`

        Why it matters:
        - the band keeps drawing more case effort than the rest of the lane
        - it continues to return weaker truth quality than peers
        - the most defensible attention point is therefore concentrated risk in `{short_band(str(latest_focus["amount_band"]))}`, not broad lane deterioration
        """,
    )

    write_md(
        ARTEFACT / "trend_usage_note_v1.md",
        f"""
        # Trend Usage Note v1

        Use this slice to:
        - explain the recent monthly direction of travel
        - show that the lane is broadly stable at top line
        - surface where concentrated risk remains visible

        Do not use this slice to:
        - claim that process improvement has already been delivered
        - claim that the whole lane is deteriorating
        - imply that every future trend will be monitored automatically without review
        """,
    )

    write_md(
        ARTEFACT / "trend_caveats_v1.md",
        f"""
        # Trend Caveats v1

        Caveats:
        - the slice is bounded to three months only:
          - `{month_label(MONTH_1)}`
          - `{month_label(MONTH_2)}`
          - `{month_label(MONTH_3)}`
        - the pattern should be read as concentrated risk identification, not broad operational collapse
        - the slice is built from one programme-style lane and should not be generalised to the whole service estate
        """,
    )

    write_md(
        ARTEFACT / "README_trend_risk_regeneration.md",
        f"""
        # Trend Risk Regeneration

        Regeneration posture:
        - heavy work stays in `DuckDB`
        - bounded monthly raw scans only
        - no broad raw-data pandas loads
        - Python reads only compact shaped outputs after SQL reduction

        Execution order:
        1. build `trend_month_band_agg_v1.parquet`
        2. build `monthly_trend_compare_v1.parquet`
        3. build `monthly_risk_opportunity_focus_v1.parquet`
        4. build `trend_release_checks_v1.parquet`
        5. regenerate notes and figures

        Current regeneration time:
        - about `{regeneration_seconds:.1f}` seconds
        """,
    )

    write_md(
        ARTEFACT / "trend_risk_evidence_pack_v1.md",
        f"""
        # Trend Risk Evidence Pack v1

        Trend context:
        - the rolling `{month_label(MONTH_1)} -> {month_label(MONTH_3)}` window remains broadly stable at top line
        - case-open rate moves from `{pct(float(earliest["case_open_rate"]))}` to `{pct(float(latest["case_open_rate"]))}`
        - truth quality moves from `{pct(float(earliest["case_truth_rate"]))}` to `{pct(float(latest["case_truth_rate"]))}`

        Concentrated risk:
        - `{short_band(str(latest_focus["amount_band"]))}` remains the top monthly attention band across the full rolling window
        - current-month case-open rate is `{pct(float(latest_focus["case_open_rate"]))}` versus peer average `{pct(float(latest_focus["peer_case_open_rate"]))}`
        - current-month truth quality is `{pct(float(latest_focus["case_truth_rate"]))}` versus peer average `{pct(float(latest_focus["peer_case_truth_rate"]))}`
        """,
    )

    render_figures(trend_df, focus_df)


if __name__ == "__main__":
    main()
