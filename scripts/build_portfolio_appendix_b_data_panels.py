from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "experience_lake" / "outward-facing-assets" / "portfolio" / "_assets"
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1" / "data"

ARRIVAL_GLOB = str(RUN_ROOT / "layer2" / "5B" / "arrival_events" / "**" / "*.parquet")
LABEL_GLOB = str(RUN_ROOT / "layer3" / "6B" / "s4_flow_truth_labels_6B" / "**" / "*.parquet")
CASE_GLOB = str(RUN_ROOT / "layer3" / "6B" / "s4_case_timeline_6B" / "**" / "*.parquet")

BG = "#F7F4ED"
TEXT = "#161514"
MUTED = "#5E5A55"
GRID = "#D9D1C7"
EDGE = "#2F2A24"
BLUE = "#204B57"
ORANGE = "#B5653A"
GREEN = "#4A7C59"
PLUM = "#8E6C8A"


def ensure_dir() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(ASSET_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor=BG)
    fig.savefig(ASSET_DIR / f"{stem}.svg", bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def query_df(sql: str) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        return con.sql(sql).df()
    finally:
        con.close()


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)


def build_panel_1_daily_rhythm() -> None:
    sql = f"""
    with base as (
      select cast(strptime(ts_local_primary, '%Y-%m-%dT%H:%M:%S.%f') as timestamp) as ts_local
      from read_parquet('{ARRIVAL_GLOB}', hive_partitioning=1)
    )
    select cast(ts_local as date) as local_date, count(*) as arrivals
    from base
    group by 1
    having local_date between date '2026-01-01' and date '2026-03-31'
    order by 1
    """
    df = query_df(sql)
    df["arrivals_m"] = df["arrivals"] / 1_000_000.0
    df["rolling_7d_m"] = df["arrivals_m"].rolling(7, min_periods=3).mean()
    write_csv(ASSET_DIR / "appendix_b_panel_temporal_realism.source.csv", df)

    weekend_mask = pd.to_datetime(df["local_date"]).dt.dayofweek >= 5
    weekday_avg = df.loc[~weekend_mask, "arrivals_m"].mean()
    weekend_avg = df.loc[weekend_mask, "arrivals_m"].mean()

    fig, ax = plt.subplots(figsize=(13.5, 7.5), facecolor=BG)
    style_axes(ax)
    ax.plot(pd.to_datetime(df["local_date"]), df["arrivals_m"], color=BLUE, linewidth=1.6, alpha=0.35, label="Daily arrivals")
    ax.plot(pd.to_datetime(df["local_date"]), df["rolling_7d_m"], color=ORANGE, linewidth=2.8, label="7-day rolling average")
    fig.suptitle("Appendix B Panel 1 — Daily Operating Rhythm", x=0.06, y=0.98, ha="left", fontsize=19, color=TEXT, fontweight="bold")
    fig.text(
        0.06,
        0.92,
        "Three months of arrivals show stable weekly seasonality rather than flat synthetic traffic.",
        fontsize=10.8,
        color=MUTED,
    )
    ax.set_ylabel("Daily arrivals (millions)")
    ax.set_xlabel("Local calendar date")
    ax.grid(axis="y", linestyle="--", color=GRID, alpha=0.9)
    ax.legend(frameon=False, loc="upper left")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.setp(ax.get_xticklabels(), rotation=0, ha="center")

    ax.text(
        0.99,
        0.16,
        f"Average weekday volume: {weekday_avg:.2f}M\nAverage weekend volume: {weekend_avg:.2f}M",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10.5,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#FCFAF6", edgecolor=GRID),
    )
    plt.tight_layout(rect=[0, 0.00, 1, 0.88])
    save(fig, "appendix_b_panel_temporal_realism")


def build_panel_2_concentration() -> None:
    sql = f"""
    select merchant_id, count(*) as arrivals
    from read_parquet('{ARRIVAL_GLOB}', hive_partitioning=1)
    group by 1
    order by arrivals desc
    """
    df = query_df(sql)
    df["rank"] = np.arange(1, len(df) + 1)
    df["merchant_pct"] = df["rank"] / len(df) * 100.0
    df["cumulative_share_pct"] = df["arrivals"].cumsum() / df["arrivals"].sum() * 100.0
    write_csv(ASSET_DIR / "appendix_b_panel_load_concentration.source.csv", df[["merchant_id", "arrivals", "rank", "merchant_pct", "cumulative_share_pct"]])

    def share_at(pct: float) -> float:
        n = max(1, int(np.ceil(len(df) * pct / 100.0)))
        return float(df.iloc[:n]["arrivals"].sum() / df["arrivals"].sum() * 100.0)

    share_1 = share_at(1)
    share_5 = share_at(5)
    share_10 = share_at(10)

    fig, ax = plt.subplots(figsize=(13.5, 7.5), facecolor=BG)
    style_axes(ax)
    ax.plot(df["merchant_pct"], df["cumulative_share_pct"], color=BLUE, linewidth=2.8, label="Observed cumulative share")
    ax.plot([0, 100], [0, 100], color=GRID, linewidth=1.4, linestyle="--", label="Uniform world reference")
    fig.suptitle("Appendix B Panel 2 — Merchant Concentration", x=0.06, y=0.98, ha="left", fontsize=19, color=TEXT, fontweight="bold")
    fig.text(
        0.06,
        0.92,
        "Traffic is unevenly distributed across the merchant base, which is what a real operating world should look like.",
        fontsize=10.8,
        color=MUTED,
    )
    ax.set_xlabel("Share of merchants (highest volume first, %)")
    ax.set_ylabel("Share of all arrivals captured (%)")
    ax.grid(True, linestyle="--", color=GRID, alpha=0.85)
    ax.legend(frameon=False, loc="lower right")

    points = [(1, share_1), (5, share_5), (10, share_10)]
    for x, y in points:
        ax.scatter([x], [y], color=ORANGE, s=36, zorder=5)
        ax.text(x + 1.4, y + 1.0, f"Top {x}% -> {y:.1f}%", fontsize=10.2, color=TEXT)

    plt.tight_layout(rect=[0, 0.00, 1, 0.88])
    save(fig, "appendix_b_panel_load_concentration")


def build_panel_3_supervision() -> None:
    label_sql = f"""
    select fraud_label, count(*) as flow_count
    from read_parquet('{LABEL_GLOB}', hive_partitioning=1)
    group by 1
    order by flow_count desc
    """
    case_sql = f"""
    with per_case as (
      select
        case_id,
        count(*) as case_event_count,
        datediff('hour', min(cast(ts_utc as timestamp)), max(cast(ts_utc as timestamp))) / 24.0 as duration_days
      from read_parquet('{CASE_GLOB}', hive_partitioning=1)
      group by 1
    )
    select
      count(*) as case_count,
      avg(case_event_count) as avg_case_event_count,
      quantile_cont(case_event_count, 0.50) as p50_case_event_count,
      quantile_cont(case_event_count, 0.95) as p95_case_event_count,
      quantile_cont(duration_days, 0.50) as p50_duration_days,
      quantile_cont(duration_days, 0.75) as p75_duration_days,
      quantile_cont(duration_days, 0.95) as p95_duration_days
    from per_case
    """
    label_df = query_df(label_sql)
    case_summary = query_df(case_sql)
    write_csv(ASSET_DIR / "appendix_b_panel_supervision_realism.labels.source.csv", label_df)
    write_csv(ASSET_DIR / "appendix_b_panel_supervision_realism.case_summary.source.csv", case_summary)

    total_labels = float(label_df["flow_count"].sum())
    label_df["share_pct"] = label_df["flow_count"] / total_labels * 100.0

    case_row = case_summary.iloc[0]
    quantile_df = pd.DataFrame(
        {
            "quantile": ["p50", "p75", "p95"],
            "duration_days": [case_row["p50_duration_days"], case_row["p75_duration_days"], case_row["p95_duration_days"]],
        }
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 7.5), facecolor=BG)
    style_axes(ax1)
    style_axes(ax2)

    bars = ax1.bar(label_df["fraud_label"], label_df["share_pct"], color=[BLUE, ORANGE, PLUM], edgecolor=EDGE, linewidth=1.0)
    ax1.set_yscale("log")
    ax1.set_ylabel("Share of flow-truth labels (%) — log scale")
    ax1.set_title("Label mix", loc="left", fontsize=13.5, color=TEXT)
    for bar, pct, count in zip(bars, label_df["share_pct"], label_df["flow_count"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            pct * 1.12,
            f"{pct:.3f}%\n({int(count):,})",
            ha="center",
            va="bottom",
            fontsize=9.2,
            color=TEXT,
        )

    bars2 = ax2.bar(quantile_df["quantile"], quantile_df["duration_days"], color=GREEN, edgecolor=EDGE, linewidth=1.0, width=0.6)
    ax2.set_ylabel("Case duration (days)")
    ax2.set_title("Case duration quantiles", loc="left", fontsize=13.5, color=TEXT)
    ax2.grid(axis="y", linestyle="--", color=GRID, alpha=0.85)
    for bar, val in zip(bars2, quantile_df["duration_days"]):
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + max(2.0, val * 0.03),
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9.5,
            color=TEXT,
        )
    ax2.text(
        0.98,
        0.96,
        f"Average case events / case: {case_row['avg_case_event_count']:.2f}\n"
        f"Median case events / case: {case_row['p50_case_event_count']:.0f}\n"
        f"p95 case events / case: {case_row['p95_case_event_count']:.0f}",
        transform=ax2.transAxes,
        ha="right",
        va="top",
        fontsize=10.0,
        color=TEXT,
        bbox=dict(boxstyle='round,pad=0.35', facecolor='#FCFAF6', edgecolor=GRID),
    )

    fig.suptitle("Appendix B Panel 3 — Supervision Realism", x=0.06, y=0.98, ha="left", fontsize=19, color=TEXT, fontweight="bold")
    fig.text(
        0.06,
        0.92,
        "Truth in this world is sparse and delayed: labels are highly imbalanced, and case closure can stretch across weeks.",
        fontsize=10.8,
        color=MUTED,
    )
    plt.tight_layout(rect=[0, 0.00, 1, 0.88])
    save(fig, "appendix_b_panel_supervision_realism")


def main() -> None:
    ensure_dir()
    build_panel_1_daily_rhythm()
    build_panel_2_concentration()
    build_panel_3_supervision()


if __name__ == "__main__":
    main()
