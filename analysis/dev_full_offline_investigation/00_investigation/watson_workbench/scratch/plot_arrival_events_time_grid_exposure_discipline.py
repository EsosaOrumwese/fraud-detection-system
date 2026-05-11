from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
    / "branches"
    / "time_grid_exposure_discipline"
)
FIGURE_DIR = EXPORT_DIR / "figures"

BG = "#f7f1e8"
GRID = "#d9cfbd"
TEXT = "#2b2926"
MUTED = "#7b7165"
GREEN = "#6f9477"
GOLD = "#c9a129"
RUST = "#b86e45"
INK = "#282828"
PURPLE = "#7d4e73"
BLUE = "#557a95"
RED = "#9f4f45"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORT_DIR / name)


def savefig(fig: plt.Figure, filename: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / filename, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.85)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(TEXT)
    ax.spines["bottom"].set_color(TEXT)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)


def plot_bucket_grid_contract() -> None:
    summary = read_csv("bucket_grid_summary.csv").iloc[0]
    profile = read_csv("bucket_profile.csv")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1, 1.45]})
    fig.suptitle("Bucket Index Is Complete and Aligned, but It Is a Time Coordinate Rather Than Row Identity", fontsize=18, color=TEXT)

    ax = axes[0]
    checks = [
        ("expected\nbuckets", summary["expected_buckets"]),
        ("observed\nbuckets", summary["observed_buckets"]),
        ("missing\nbuckets", summary["missing_buckets"]),
        ("hour\nmismatch rows", summary["rows_bucket_hour_mismatch"]),
    ]
    labels = [x[0] for x in checks]
    values = [x[1] for x in checks]
    colors = [GREEN, GREEN, RUST, RUST]
    bars = ax.bar(labels, values, color=colors, edgecolor="none", alpha=0.92)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, max(value, 1) + 35, f"{int(value):,}", ha="center", va="bottom", fontsize=11, color=TEXT)
    ax.set_ylabel("Count")
    ax.set_title("Grid contract checks", fontsize=13, weight="bold")
    ax.set_ylim(0, 2350)
    style_ax(ax)

    ax = axes[1]
    ax.scatter(profile["bucket_index"], profile["bucket_hour_index"], s=5, color=INK, alpha=0.45, edgecolor="none")
    ax.set_xlabel("bucket_index")
    ax.set_ylabel("bucket_index % 24")
    ax.set_yticks(range(0, 24, 2))
    ax.set_title("The modulo pattern repeats exactly across the 90-day horizon", fontsize=13, weight="bold")
    ax.text(
        0.02,
        0.95,
        f"first: {summary['first_ts_utc']}\nlast: {summary['last_ts_utc']}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.35", facecolor=BG, edgecolor=GRID),
    )
    style_ax(ax)

    savefig(fig, "01_bucket_grid_contract.png")


def plot_bucket_intensity_surface() -> None:
    profile = read_csv("bucket_profile.csv")
    matrix = profile.pivot(index="bucket_day_index", columns="bucket_hour_index", values="rows").sort_index()

    fig, axes = plt.subplots(1, 2, figsize=(18, 7), gridspec_kw={"width_ratios": [1.45, 1]})
    fig.suptitle("The Hour Grid Is Complete, but Arrival Intensity Moves Inside It", fontsize=18, color=TEXT)

    ax = axes[0]
    im = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="YlOrBr")
    ax.set_xlabel("UTC hour")
    ax.set_ylabel("Operating day index")
    ax.set_xticks(range(0, 24, 2))
    ax.set_title("Rows per bucket across 90 days x 24 hours", fontsize=13, weight="bold")
    cbar = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.035)
    cbar.set_label("Rows in bucket")
    cbar.ax.tick_params(labelsize=9, colors=TEXT)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(TEXT)

    ax = axes[1]
    ax.hist(profile["rows"], bins=35, color=GREEN, alpha=0.88, edgecolor="none")
    median = profile["rows"].median()
    p05 = profile["rows"].quantile(0.05)
    p95 = profile["rows"].quantile(0.95)
    ax.axvline(median, color=INK, linestyle="--", linewidth=2, label=f"median: {median:,.0f}")
    ax.axvspan(p05, p95, color=GOLD, alpha=0.18, label=f"p05-p95: {p05:,.0f}-{p95:,.0f}")
    ax.set_xlabel("Rows per bucket")
    ax.set_ylabel("Buckets")
    ax.set_title("Complete does not mean uniform", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    savefig(fig, "02_bucket_intensity_surface.png")


def plot_hourly_bucket_profile() -> None:
    hours = read_csv("bucket_hour_profile.csv")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Hourly Bucket Intensity Has a Stable Shape, with Different Channel Contributions", fontsize=18, color=TEXT)

    ax = axes[0]
    ax.plot(hours["utc_hour"], hours["mean_rows_per_bucket"], color=INK, linewidth=2.4, marker="o", label="mean")
    ax.fill_between(hours["utc_hour"], hours["min_rows_per_bucket"], hours["max_rows_per_bucket"], color=GOLD, alpha=0.22, label="min-max across 90 buckets")
    ax.axvspan(3, 5, color=RUST, alpha=0.10)
    ax.axvspan(10, 17, color=GOLD, alpha=0.12)
    ax.set_xticks(range(24))
    ax.set_xlabel("UTC hour")
    ax.set_ylabel("Rows per bucket")
    ax.set_title("Mean, minimum, and maximum bucket intensity by UTC hour", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    ax = axes[1]
    x = hours["utc_hour"].to_numpy()
    card_present = hours["card_present_rows"].to_numpy()
    card_not_present = hours["card_not_present_rows"].to_numpy()
    ax.stackplot(x, card_present, card_not_present, colors=[GREEN, GOLD], labels=["card_present", "card_not_present"], alpha=0.88)
    ax.set_xticks(range(24))
    ax.set_xlabel("UTC hour")
    ax.set_ylabel("Rows")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1_000_000:.0f}M"))
    ax.set_title("The same UTC hour has changing channel composition", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, loc="upper left")
    style_ax(ax)

    savefig(fig, "03_hourly_bucket_profile_and_channel_mix.png")


def plot_channel_route_hour_shapes() -> None:
    df = read_csv("bucket_hour_by_channel_route.csv")
    df["lane"] = df["channel_group"] + " / " + df["route_mode"]
    lane_order = [
        "card_present / physical",
        "card_not_present / physical",
        "card_not_present / virtual",
        "card_present / virtual",
    ]
    colors = {
        "card_present / physical": GREEN,
        "card_not_present / physical": GOLD,
        "card_not_present / virtual": PURPLE,
        "card_present / virtual": BLUE,
    }

    fig, ax = plt.subplots(figsize=(14, 7))
    for lane in lane_order:
        sub = df[df["lane"] == lane].sort_values("utc_hour")
        if sub.empty:
            continue
        ax.plot(
            sub["utc_hour"],
            sub["share_within_channel_route"],
            marker="o",
            linewidth=2.2,
            markersize=4,
            color=colors[lane],
            label=lane,
        )
        peak = sub.loc[sub["share_within_channel_route"].idxmax()]
        ax.scatter([peak["utc_hour"]], [peak["share_within_channel_route"]], s=70, color=colors[lane], edgecolor=TEXT, zorder=4)

    ax.set_xticks(range(24))
    ax.set_xlabel("UTC hour")
    ax.set_ylabel("Share within channel/route lane")
    ax.set_title("The same bucket grid carries different hourly shapes by channel and route", fontsize=17, color=TEXT, pad=14)
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, ncol=2)
    style_ax(ax)

    savefig(fig, "04_channel_route_hour_shapes.png")


def plot_merchant_exposure_distribution() -> None:
    exposure = read_csv("merchant_exposure_ranked.csv")
    summary = read_csv("merchant_exposure_summary.csv").iloc[0]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1, 1.1]})
    fig.suptitle("Merchant Exposure Is Unequal, but the Surface Is Not Single-Merchant Dominated", fontsize=18, color=TEXT)

    ax = axes[0]
    ax.hist(exposure["rows"], bins=45, color=GREEN, alpha=0.9, edgecolor="none")
    ax.set_xscale("log")
    ax.axvline(summary["median_rows_per_merchant"], color=INK, linestyle="--", linewidth=2, label=f"median: {summary['median_rows_per_merchant']:,.0f}")
    ax.axvline(summary["p95_rows_per_merchant"], color=RUST, linestyle=":", linewidth=2.5, label=f"p95: {summary['p95_rows_per_merchant']:,.0f}")
    ax.set_xlabel("Rows per merchant (log scale)")
    ax.set_ylabel("Merchants")
    ax.set_title("Merchant row counts span orders of magnitude", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    ax = axes[1]
    ax.plot(exposure["merchant_rank"], exposure["cumulative_row_share"], color=INK, linewidth=2.4)
    ax.fill_between(exposure["merchant_rank"], exposure["cumulative_row_share"], color=GOLD, alpha=0.18)
    markers = [
        (1, summary["top_1_share"], "top 1", (240, 0.035)),
        (10, summary["top_10_share"], "top 10", (240, 0.070)),
        (100, summary["top_100_share"], "top 100", (240, 0.180)),
        (405, summary["top_10pct_merchants_share"], "top 10%", (470, 0.405)),
    ]
    for rank, share, label, text_xy in markers:
        ax.scatter([rank], [share], color=RUST, s=55, zorder=4)
        ax.annotate(
            f"{label}: {share:.1%}",
            xy=(rank, share),
            xytext=text_xy,
            textcoords="data",
            fontsize=10,
            color=TEXT,
            va="center",
            arrowprops={"arrowstyle": "-", "color": RUST, "linewidth": 1.0, "shrinkA": 2, "shrinkB": 4},
        )
    ax.set_xlim(1, len(exposure))
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Merchant rank by arrival rows")
    ax.set_ylabel("Cumulative row share")
    ax.set_title("High-volume cohort weighting, not one-merchant domination", fontsize=13, weight="bold")
    style_ax(ax)

    savefig(fig, "05_merchant_exposure_distribution_and_concentration.png")


def plot_exception_context() -> None:
    daily = read_csv("daily_merchant_presence.csv")
    exception = read_csv("merchant_day_exception_context.csv")
    exception["context_utc_date"] = pd.to_datetime(exception["context_utc_date"])
    missing_date = pd.to_datetime(exception["missing_utc_date"].iloc[0])
    merchant_id = int(exception["merchant_id"].iloc[0])

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.suptitle("The One Merchant-Day Exception Is Real, but Localized", fontsize=18, color=TEXT)

    ax = axes[0]
    daily["utc_date"] = pd.to_datetime(daily["utc_date"])
    ax.plot(daily["utc_date"], daily["merchants"], color=INK, linewidth=2)
    ax.scatter([missing_date], [4049], color=RED, s=70, zorder=4)
    ax.set_ylim(4048.5, 4050.5)
    ax.set_ylabel("Active merchants")
    ax.set_title("Daily merchant presence across the quarter", fontsize=13, weight="bold")
    ax.text(missing_date, 4048.72, "2026-03-22\n4,049 merchants", ha="center", va="bottom", fontsize=10, color=RED)
    style_ax(ax)

    ax = axes[1]
    days = pd.date_range(missing_date - pd.Timedelta(days=3), missing_date + pd.Timedelta(days=3), freq="D")
    plot_df = pd.DataFrame({"context_utc_date": days}).merge(exception[["context_utc_date", "rows"]], on="context_utc_date", how="left").fillna({"rows": 0})
    colors = [RED if d == missing_date else GREEN for d in plot_df["context_utc_date"]]
    ax.bar(plot_df["context_utc_date"].dt.strftime("%m-%d"), plot_df["rows"], color=colors, edgecolor="none", alpha=0.9)
    for i, row in plot_df.iterrows():
        ax.text(i, row["rows"] + 1, f"{int(row['rows'])}", ha="center", va="bottom", fontsize=10, color=TEXT)
    ax.set_ylabel("Rows for missing merchant")
    ax.set_title(f"Merchant {merchant_id} around missing date", fontsize=13, weight="bold")
    style_ax(ax)

    savefig(fig, "06_merchant_day_exception_context.png")


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plot_bucket_grid_contract()
    plot_bucket_intensity_surface()
    plot_hourly_bucket_profile()
    plot_channel_route_hour_shapes()
    plot_merchant_exposure_distribution()
    plot_exception_context()


if __name__ == "__main__":
    main()
