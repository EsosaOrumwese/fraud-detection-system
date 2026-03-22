from __future__ import annotations

import argparse
import csv
import json
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
DEFAULT_RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1" / "data"
DEFAULT_PHASE5_SUMMARY = (
    ROOT
    / "runs"
    / "dev_substrate"
    / "dev_full"
    / "proving_plane"
    / "run_control"
    / "phase5_ofs_dataset_basis_20260312T054900Z"
    / "phase5_ofs_dataset_basis_summary.json"
)

RUN_ROOT = DEFAULT_RUN_ROOT
PHASE5_SUMMARY = DEFAULT_PHASE5_SUMMARY
ARRIVAL_GLOB = ""
EVENT_GLOB = ""
EVENT_LABEL_GLOB = ""
CAMPAIGN_GLOB = ""
LABEL_GLOB = ""
CASE_GLOB = ""

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


def resolve_existing_path(raw_path: str, *, default: Path, label: str) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path else default
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"missing_{label}:{candidate}")
    return candidate


def resolve_output_dir(raw_path: str, *, default: Path) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path else default
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    return candidate


def assert_has_parquet(directory: Path, *, label: str) -> None:
    if not directory.exists():
        raise FileNotFoundError(f"missing_{label}_dir:{directory}")
    if not any(directory.rglob("*.parquet")):
        raise FileNotFoundError(f"missing_{label}_parquet:{directory}")


def configure_inputs(*, run_root: Path, phase5_summary: Path, asset_dir: Path) -> None:
    global ASSET_DIR
    global RUN_ROOT
    global PHASE5_SUMMARY
    global ARRIVAL_GLOB
    global EVENT_GLOB
    global EVENT_LABEL_GLOB
    global CAMPAIGN_GLOB
    global LABEL_GLOB
    global CASE_GLOB

    RUN_ROOT = run_root
    PHASE5_SUMMARY = phase5_summary
    ASSET_DIR = asset_dir

    arrival_dir = RUN_ROOT / "layer2" / "5B" / "arrival_events"
    event_dir = RUN_ROOT / "layer3" / "6B" / "s3_event_stream_with_fraud_6B"
    event_label_dir = RUN_ROOT / "layer3" / "6B" / "s4_event_labels_6B"
    campaign_dir = RUN_ROOT / "layer3" / "6B" / "s3_campaign_catalogue_6B"
    label_dir = RUN_ROOT / "layer3" / "6B" / "s4_flow_truth_labels_6B"
    case_dir = RUN_ROOT / "layer3" / "6B" / "s4_case_timeline_6B"

    assert_has_parquet(arrival_dir, label="arrival_events")
    assert_has_parquet(event_dir, label="event_stream")
    assert_has_parquet(event_label_dir, label="event_labels")
    assert_has_parquet(campaign_dir, label="campaign_catalogue")
    assert_has_parquet(label_dir, label="flow_truth_labels")
    assert_has_parquet(case_dir, label="case_timeline")

    ARRIVAL_GLOB = str(arrival_dir / "**" / "*.parquet")
    EVENT_GLOB = str(event_dir / "**" / "*.parquet")
    EVENT_LABEL_GLOB = str(event_label_dir / "**" / "*.parquet")
    CAMPAIGN_GLOB = str(campaign_dir / "**" / "*.parquet")
    LABEL_GLOB = str(label_dir / "**" / "*.parquet")
    CASE_GLOB = str(case_dir / "**" / "*.parquet")


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


def load_phase5_slice_metrics() -> dict:
    summary = json.loads(PHASE5_SUMMARY.read_text(encoding="utf-8"))
    return summary["slice_metrics"]


def connect_for_large_query() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=4")
    return con


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
        "Daily arrivals stay in a stable weekly band across the quarter, with weekdays consistently above weekends.",
        fontsize=10.8,
        color=MUTED,
    )
    ax.set_ylabel("Daily arrivals (millions)")
    ax.set_xlabel("Local calendar date")
    ax.grid(axis="y", linestyle="--", color=GRID, alpha=0.9)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.01), ncol=2)
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
    plt.tight_layout(rect=[0, 0.00, 1, 0.86])
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
        "A small head of merchants carries a disproportionate share of traffic while the long tail remains material.",
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
        "Flow-truth labels are heavily imbalanced, and case closure stretches from weeks into months at the upper end.",
        fontsize=10.8,
        color=MUTED,
    )
    plt.tight_layout(rect=[0, 0.00, 1, 0.88])
    save(fig, "appendix_b_panel_supervision_realism")


def build_panel_4_event_volume_timeline() -> None:
    slice_metrics = load_phase5_slice_metrics()
    current_events = slice_metrics["events"]["row_count"]
    raw_events = slice_metrics["raw_horizons"]["event_row_count"]
    cutoff_ts = pd.to_datetime(slice_metrics["events"]["max_ts_utc"]).tz_localize(None)
    raw_max_ts = pd.to_datetime(slice_metrics["raw_horizons"]["event_max_ts_utc"]).tz_localize(None)

    sql = f"""
    select
      cast(ts_utc as date) as utc_date,
      count(*) as event_rows,
      sum(case when fraud_flag then 1 else 0 end) as fraud_events
    from read_parquet('{EVENT_GLOB}', hive_partitioning=1)
    group by 1
    order by 1
    """
    df = query_df(sql)
    df["utc_date"] = pd.to_datetime(df["utc_date"])
    df["event_rows_m"] = df["event_rows"] / 1_000_000.0
    df["rolling_7d_m"] = df["event_rows_m"].rolling(7, min_periods=3).mean()
    df["phase5_current_slice"] = df["utc_date"] < cutoff_ts.normalize()
    write_csv(ASSET_DIR / "appendix_b_panel_shared_world_event_timeline.source.csv", df)
    plot_df = df.loc[df["utc_date"] < raw_max_ts.normalize()].copy()

    fig, ax = plt.subplots(figsize=(14.0, 7.6), facecolor=BG)
    style_axes(ax)

    ax.plot(plot_df["utc_date"], plot_df["event_rows_m"], color=BLUE, linewidth=1.4, alpha=0.35, label="Daily event volume")
    ax.plot(plot_df["utc_date"], plot_df["rolling_7d_m"], color=ORANGE, linewidth=2.7, label="7-day rolling average")
    ax.axvspan(cutoff_ts.normalize(), plot_df["utc_date"].max(), color="#E8DED2", alpha=0.55, label="Raw-horizon remainder")
    ax.axvline(cutoff_ts, color=EDGE, linewidth=1.5, linestyle="--")

    fig.suptitle(
        "Appendix B Panel 4 — Current Slice vs Raw Horizon",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=19,
        color=TEXT,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.92,
        "The bounded current slice ends on 05 Mar, while the larger raw horizon continues beyond it into 01 Apr.",
        fontsize=10.8,
        color=MUTED,
    )

    ax.set_ylabel("Daily events (millions)")
    ax.set_xlabel("UTC date")
    ax.grid(axis="y", linestyle="--", color=GRID, alpha=0.9)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.01), ncol=3)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    ax.text(
        cutoff_ts,
        ax.get_ylim()[1] * 0.94,
        "Accepted current-slice cutoff\n2026-03-05 00:00 UTC",
        ha="left",
        va="top",
        fontsize=9.7,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#FCFAF6", edgecolor=GRID),
    )
    ax.text(
        0.985,
        0.12,
        f"Accepted current slice: {current_events / 1_000_000:.1f}M events\n"
        f"Raw horizon: {raw_events / 1_000_000:.1f}M events\n"
        f"Excess horizon beyond slice: {(raw_events - current_events) / 1_000_000:.1f}M events",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10.0,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#FCFAF6", edgecolor=GRID),
    )

    plt.tight_layout(rect=[0, 0.00, 1, 0.86])
    save(fig, "appendix_b_panel_shared_world_event_timeline")


def build_panel_5_supervision_operations_timeline() -> None:
    slice_metrics = load_phase5_slice_metrics()
    cutoff = slice_metrics["events"]["max_ts_utc"]

    con = connect_for_large_query()
    try:
        weekly_ops = con.sql(
            f"""
            select
              date_trunc('week', cast(ts_utc as timestamp)) as week_start,
              count(*) as event_rows,
              sum(case when fraud_flag then 1 else 0 end) as fraud_events
            from read_parquet('{EVENT_GLOB}', hive_partitioning=1)
            where cast(ts_utc as timestamp) <= cast('{cutoff}' as timestamp)
            group by 1
            order by 1
            """
        ).df()
        weekly_truth = con.sql(
            f"""
            with truth_labels as (
              select flow_id, event_seq, seed, manifest_fingerprint, parameter_hash, scenario_id
              from read_parquet('{EVENT_LABEL_GLOB}', hive_partitioning=1)
              where is_fraud_truth = true
            ),
            bounded_events as (
              select flow_id, event_seq, cast(ts_utc as timestamp) as ts_utc, seed, manifest_fingerprint, parameter_hash, scenario_id
              from read_parquet('{EVENT_GLOB}', hive_partitioning=1)
              where cast(ts_utc as timestamp) <= cast('{cutoff}' as timestamp)
            )
            select
              date_trunc('week', be.ts_utc) as week_start,
              count(*) as fraud_truth_events
            from bounded_events be
            join truth_labels tl
              on be.flow_id = tl.flow_id
             and be.event_seq = tl.event_seq
             and be.seed = tl.seed
             and be.manifest_fingerprint = tl.manifest_fingerprint
             and be.parameter_hash = tl.parameter_hash
             and be.scenario_id = tl.scenario_id
            group by 1
            order by 1
            """
        ).df()
    finally:
        con.close()

    df = weekly_ops.merge(weekly_truth, on="week_start", how="left").fillna({"fraud_truth_events": 0})
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["fraud_truth_events_m"] = df["fraud_truth_events"] / 1_000_000.0
    write_csv(ASSET_DIR / "appendix_b_panel_shared_world_supervision_operations_timeline.source.csv", df)

    fig, ax = plt.subplots(figsize=(14.0, 7.6), facecolor=BG)
    style_axes(ax)
    ax2 = ax.twinx()
    ax2.set_facecolor("none")
    for spine in ax2.spines.values():
        spine.set_color(GRID)
    ax2.tick_params(colors=MUTED)
    ax2.yaxis.label.set_color(MUTED)

    bars = ax.bar(
        df["week_start"],
        df["fraud_truth_events_m"],
        width=5.5,
        color=BLUE,
        alpha=0.85,
        edgecolor=EDGE,
        linewidth=0.7,
        label="Weekly fraud-truth events",
    )
    ax2.plot(
        df["week_start"],
        df["fraud_events"],
        color=ORANGE,
        linewidth=2.4,
        marker="o",
        markersize=4.0,
        label="Weekly fraud-overlay events",
    )

    fig.suptitle(
        "Appendix B Panel 5 — Supervision and Operations Timeline",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=19,
        color=TEXT,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.92,
        "Supervision remains active across the quarter, and the accepted slice closes into bounded review and case surfaces.",
        fontsize=10.8,
        color=MUTED,
    )

    ax.set_ylabel("Weekly fraud-truth events (millions)")
    ax2.set_ylabel("Weekly fraud-overlay events")
    ax.set_xlabel("Week start")
    ax.grid(axis="y", linestyle="--", color=GRID, alpha=0.9)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    handles_1, labels_1 = ax.get_legend_handles_labels()
    handles_2, labels_2 = ax2.get_legend_handles_labels()
    fig.legend(
        handles_1 + handles_2,
        labels_1 + labels_2,
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(0.06, 0.82),
        ncol=2,
    )

    ax.text(
        0.985,
        0.97,
        f"Accepted current-slice totals\n"
        f"Flow-truth labels: {slice_metrics['flow_truth_labels']['row_count']:,}\n"
        f"Case-history rows: {slice_metrics['case_timeline']['row_count']:,}\n"
        f"Distinct cases: {slice_metrics['case_timeline']['distinct_case_count']:,}\n"
        f"Fraud-truth events: {slice_metrics['event_labels']['fraud_truth_event_count'] / 1_000_000:.2f}M",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10.0,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#FCFAF6", edgecolor=GRID),
    )

    last_x = df["week_start"].iloc[-1]
    last_bar_h = df["fraud_truth_events_m"].iloc[-1]
    ax.annotate(
        "Partial final week\nSlice closes on 05 Mar",
        xy=(last_x, last_bar_h),
        xytext=(last_x - pd.Timedelta(days=16), last_bar_h + 0.16),
        textcoords="data",
        ha="left",
        va="bottom",
        fontsize=9.4,
        color=TEXT,
        arrowprops=dict(arrowstyle="->", color=EDGE, lw=1.0),
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#FCFAF6", edgecolor=GRID),
    )

    plt.tight_layout(rect=[0, 0.00, 1, 0.84])
    save(fig, "appendix_b_panel_shared_world_supervision_operations_timeline")


def build_panel_6_campaign_occupancy_distribution() -> None:
    slice_metrics = load_phase5_slice_metrics()
    cutoff = slice_metrics["events"]["max_ts_utc"]

    con = connect_for_large_query()
    try:
        df = con.sql(
            f"""
            with weekly_campaigns as (
              select
                date_trunc('week', cast(e.ts_utc as timestamp)) as week_start,
                e.campaign_id,
                c.campaign_label,
                count(*) as fraud_events
              from read_parquet('{EVENT_GLOB}', hive_partitioning=1) e
              left join read_parquet('{CAMPAIGN_GLOB}', hive_partitioning=1) c
                on e.campaign_id = c.campaign_id
               and e.seed = c.seed
               and e.manifest_fingerprint = c.manifest_fingerprint
               and e.parameter_hash = c.parameter_hash
               and e.scenario_id = c.scenario_id
              where cast(e.ts_utc as timestamp) <= cast('{cutoff}' as timestamp)
                and e.fraud_flag = true
                and e.campaign_id is not null
              group by 1,2,3
            )
            select * from weekly_campaigns order by week_start, campaign_label
            """
        ).df()
    finally:
        con.close()

    df["week_start"] = pd.to_datetime(df["week_start"])
    df["campaign_label"] = (
        df["campaign_label"]
        .fillna(df["campaign_id"])
        .str.replace("T_", "", regex=False)
        .str.replace("_", " ", regex=False)
        .str.title()
    )
    df["campaign_label"] = df["campaign_label"].replace(
        {
            "Ato Account Sweep": "ATO Account Sweep",
            "Ato Accountsweep": "ATO Account Sweep",
            "Ato Accounsweep": "ATO Account Sweep",
            "Merchant Collusion": "Merchant Collusion",
            "Merchantcollusion": "Merchant Collusion",
            "Merchancollusion": "Merchant Collusion",
        }
    )
    df["weekly_share_pct"] = df["fraud_events"] / df.groupby("week_start")["fraud_events"].transform("sum") * 100.0
    write_csv(ASSET_DIR / "appendix_b_panel_shared_world_campaign_occupancy_distribution.source.csv", df)

    totals = (
        df.groupby("campaign_label", as_index=False)["fraud_events"]
        .sum()
        .sort_values("fraud_events", ascending=False)
        .reset_index(drop=True)
    )
    campaign_order = totals["campaign_label"].tolist()
    week_order = sorted(df["week_start"].drop_duplicates())
    heatmap = (
        df.pivot(index="campaign_label", columns="week_start", values="weekly_share_pct")
        .reindex(index=campaign_order, columns=week_order)
        .fillna(0.0)
    )

    fig, (ax1, ax2) = plt.subplots(
        1,
        2,
        figsize=(15.2, 7.8),
        facecolor=BG,
        gridspec_kw={"width_ratios": [3.2, 1.2]},
    )
    style_axes(ax1)
    style_axes(ax2)

    im = ax1.imshow(heatmap.values, aspect="auto", cmap="YlOrBr", interpolation="nearest")
    ax1.set_yticks(np.arange(len(campaign_order)))
    ax1.set_yticklabels(campaign_order, color=TEXT)
    ax1.set_xticks(np.arange(len(week_order)))
    ax1.set_xticklabels([pd.Timestamp(x).strftime("%d %b") for x in week_order], rotation=0, ha="center")
    ax1.set_xlabel("Week start")
    ax1.set_title("Weekly share of fraud-overlay events (%)", loc="left", fontsize=13.5, color=TEXT)

    cbar = fig.colorbar(im, ax=ax1, fraction=0.03, pad=0.02)
    cbar.outline.set_edgecolor(GRID)
    cbar.ax.tick_params(colors=MUTED)
    cbar.set_label("Weekly fraud-event share (%)", color=MUTED)

    bars = ax2.barh(
        totals["campaign_label"],
        totals["fraud_events"],
        color=ORANGE,
        edgecolor=EDGE,
        linewidth=0.8,
    )
    ax2.invert_yaxis()
    ax2.set_xlabel("Fraud-overlay events")
    ax2.set_title("Bounded current-slice totals", loc="left", fontsize=13.5, color=TEXT)
    ax2.grid(axis="x", linestyle="--", color=GRID, alpha=0.85)
    for bar, val in zip(bars, totals["fraud_events"]):
        ax2.text(val + 35, bar.get_y() + bar.get_height() / 2.0, f"{int(val):,}", va="center", ha="left", fontsize=9.2, color=TEXT)

    fig.suptitle(
        "Appendix B Panel 6 — Campaign Occupancy and Distribution",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=19,
        color=TEXT,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.92,
        "Six campaigns remain active across the slice, with shifting weekly share and uneven total footprint.",
        fontsize=10.8,
        color=MUTED,
    )

    plt.tight_layout(rect=[0, 0.00, 1, 0.88])
    save(fig, "appendix_b_panel_shared_world_campaign_occupancy_distribution")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Appendix B outward-facing data-world panels from a chosen local run root."
    )
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--phase5-summary", default=str(DEFAULT_PHASE5_SUMMARY))
    parser.add_argument("--asset-dir", default=str(ASSET_DIR))
    args = parser.parse_args()

    configure_inputs(
        run_root=resolve_existing_path(args.run_root, default=DEFAULT_RUN_ROOT, label="run_root"),
        phase5_summary=resolve_existing_path(
            args.phase5_summary,
            default=DEFAULT_PHASE5_SUMMARY,
            label="phase5_summary",
        ),
        asset_dir=resolve_output_dir(args.asset_dir, default=ASSET_DIR),
    )
    ensure_dir()
    build_panel_1_daily_rhythm()
    build_panel_2_concentration()
    build_panel_3_supervision()
    build_panel_4_event_volume_timeline()
    build_panel_5_supervision_operations_timeline()
    build_panel_6_campaign_occupancy_distribution()


if __name__ == "__main__":
    main()
