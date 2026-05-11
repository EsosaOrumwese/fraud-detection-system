from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
ARRIVAL_ROOT = RUN_ROOT / "data" / "layer2" / "5B" / "arrival_events"
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
    / "channel_structure"
)
FIGURE_DIR = EXPORT_DIR / "figures"


COLORS = {
    "ink": "#292724",
    "grid": "#d9d2c3",
    "paper": "#fbf7ef",
    "soft": "#efe8dc",
    "blue": "#1f4e5f",
    "rust": "#b86b42",
    "gold": "#c9a227",
    "green": "#6d8f71",
    "slate": "#5d6d7e",
}

CHANNEL_COLORS = {
    "card_present": COLORS["blue"],
    "card_not_present": COLORS["rust"],
}
ROUTE_COLORS = {
    "physical": COLORS["green"],
    "virtual": COLORS["gold"],
}


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": COLORS["paper"],
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "text.color": COLORS["ink"],
            "axes.titleweight": "bold",
        }
    )


def style_axes(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.8, alpha=0.72)
    ax.set_axisbelow(True)


def compact_int(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def savefig(name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGURE_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()


def load_inputs() -> dict[str, pd.DataFrame]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    merchant_counts_path = EXPORT_DIR / "merchant_channel_counts.csv"
    if not merchant_counts_path.exists():
        con = duckdb.connect()
        con.execute("SET threads TO 8")
        con.execute(
            f"""
            CREATE OR REPLACE VIEW arrivals AS
            SELECT *
            FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
            """
        )
        merchant_counts = con.execute(
            """
            SELECT
                merchant_id,
                channel_group,
                COUNT(*)::UBIGINT AS rows,
                COUNT(DISTINCT CASE WHEN is_virtual THEN edge_id END)::UBIGINT AS virtual_edges,
                COUNT(DISTINCT CASE WHEN NOT is_virtual THEN site_id END)::UBIGINT AS physical_sites,
                SUM(CASE WHEN is_virtual THEN 1 ELSE 0 END)::UBIGINT AS virtual_rows,
                SUM(CASE WHEN NOT is_virtual THEN 1 ELSE 0 END)::UBIGINT AS physical_rows
            FROM arrivals
            GROUP BY merchant_id, channel_group
            ORDER BY channel_group, rows DESC, merchant_id
            """
        ).fetchdf()
        merchant_counts.to_csv(merchant_counts_path, index=False)

    daily = pd.read_csv(EXPORT_DIR / "channel_daily_summary.csv", parse_dates=["utc_date"])
    daily["daily_row_share"] = daily["rows"] / daily.groupby("utc_date")["rows"].transform("sum")

    return {
        "overview": pd.read_csv(EXPORT_DIR / "channel_overview.csv"),
        "route": pd.read_csv(EXPORT_DIR / "channel_by_route_mode.csv"),
        "stability": pd.read_csv(EXPORT_DIR / "merchant_channel_stability.csv"),
        "volume_stats": pd.read_csv(EXPORT_DIR / "merchant_volume_by_channel.csv"),
        "merchant_counts": pd.read_csv(merchant_counts_path),
        "daily": daily,
        "daily_share_stats": pd.read_csv(EXPORT_DIR / "channel_daily_share_stats.csv"),
    }


def plot_channel_identity_and_denominators(data: dict[str, pd.DataFrame]) -> None:
    overview = data["overview"].copy()
    stability = data["stability"].copy()
    order = ["card_present", "card_not_present"]
    overview["channel_group"] = pd.Categorical(overview["channel_group"], categories=order, ordered=True)
    overview = overview.sort_values("channel_group")

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), gridspec_kw={"width_ratios": [0.9, 1.35]})
    fig.suptitle("Channel Is Merchant-Stable, but Row Exposure and Merchant Participation Diverge", fontsize=15, y=1.02)

    ax = axes[0]
    ax.barh(
        stability["channel_count"].astype(str),
        stability["merchants"],
        color=COLORS["slate"],
        edgecolor="none",
        linewidth=0,
    )
    for _, row in stability.iterrows():
        ax.text(row["merchants"] * 0.5, str(row["channel_count"]), f"{int(row['merchants']):,} merchants", va="center", ha="center", color="white", fontweight="bold")
    ax.set_yticks([0], ["exactly one"])
    ax.set_title("Merchant channel-count validation")
    ax.set_xlabel("Merchants")
    ax.set_ylabel("Distinct channel groups per merchant")
    ax.set_xlim(0, stability["merchants"].max() * 1.08)
    style_axes(ax, "x")

    ax = axes[1]
    x = np.arange(len(overview))
    width = 0.36
    ax.bar(
        x - width / 2,
        overview["row_share"],
        width=width,
        label="Arrival-row share",
        color=[CHANNEL_COLORS[ch] for ch in overview["channel_group"].astype(str)],
        alpha=0.92,
        edgecolor="none",
        linewidth=0,
    )
    ax.bar(
        x + width / 2,
        overview["merchant_share"],
        width=width,
        label="Merchant share",
        color=[CHANNEL_COLORS[ch] for ch in overview["channel_group"].astype(str)],
        alpha=0.45,
        edgecolor="none",
        linewidth=0,
    )
    for xpos, value in zip(x - width / 2, overview["row_share"]):
        ax.text(xpos, value + 0.018, pct(value), ha="center", va="bottom", fontsize=9)
    for xpos, value in zip(x + width / 2, overview["merchant_share"]):
        ax.text(xpos, value + 0.018, pct(value), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, ["card present", "card not present"])
    ax.set_ylim(0, 0.9)
    ax.set_ylabel("Share of total")
    ax.set_title("Same channel split, different denominator")
    ax.legend(frameon=False, loc="upper right")
    ax.yaxis.set_major_formatter(lambda y, _: pct(y))
    style_axes(ax)

    fig.tight_layout()
    savefig("01_channel_identity_and_denominators.png")


def plot_merchant_exposure_distribution(data: dict[str, pd.DataFrame]) -> None:
    merchant_counts = data["merchant_counts"].copy()
    order = ["card_present", "card_not_present"]
    labels = ["card present", "card not present"]
    samples = [merchant_counts.loc[merchant_counts["channel_group"].eq(ch), "rows"].to_numpy() for ch in order]

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), gridspec_kw={"width_ratios": [1.1, 1.0]})
    fig.suptitle("Card-Not-Present Has Fewer Merchants but Heavier Arrival Exposure per Merchant", fontsize=15, y=1.02)

    ax = axes[0]
    box = ax.boxplot(
        samples,
        vert=False,
        patch_artist=True,
        tick_labels=labels,
        showmeans=True,
        widths=0.54,
        medianprops={"color": COLORS["ink"], "linewidth": 1.6},
        meanprops={"marker": "D", "markerfacecolor": COLORS["gold"], "markeredgecolor": COLORS["ink"], "markersize": 5},
        whiskerprops={"color": COLORS["ink"]},
        capprops={"color": COLORS["ink"]},
        flierprops={"marker": ".", "markerfacecolor": COLORS["slate"], "markeredgecolor": "none", "markersize": 3, "alpha": 0.28},
    )
    for patch, ch in zip(box["boxes"], order):
        patch.set_facecolor(CHANNEL_COLORS[ch])
        patch.set_alpha(0.72)
        patch.set_edgecolor("none")
        patch.set_linewidth(0)
    ax.set_xscale("log")
    ax.set_xlabel("Rows per merchant over the 90-day window (log scale)")
    ax.set_title("Distribution at merchant grain")
    style_axes(ax, "x")

    ax = axes[1]
    quantiles = [0.05, 0.25, 0.50, 0.75, 0.95]
    q_labels = ["p05", "p25", "median", "p75", "p95"]
    for ch, label in zip(order, labels):
        values = np.quantile(merchant_counts.loc[merchant_counts["channel_group"].eq(ch), "rows"], quantiles)
        ax.plot(q_labels, values, marker="o", color=CHANNEL_COLORS[ch], linewidth=2.3, label=label)
        for i, value in enumerate(values):
            ax.text(i, value * 1.045, compact_int(value), ha="center", va="bottom", fontsize=8, color=CHANNEL_COLORS[ch])
    ax.set_yscale("log")
    ax.set_ylabel("Rows per merchant (log scale)")
    ax.set_title("Quantile profile")
    ax.legend(frameon=False)
    style_axes(ax)

    fig.tight_layout()
    savefig("02_merchant_exposure_distribution_by_channel.png")


def plot_channel_route_interaction(data: dict[str, pd.DataFrame]) -> None:
    route = data["route"].copy()
    route["route_mode"] = np.where(route["is_virtual"], "virtual", "physical")
    order = ["card_present", "card_not_present"]
    labels = ["card present", "card not present"]

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), gridspec_kw={"width_ratios": [1.1, 1.0]})
    fig.suptitle("Channel and Route Mode Interact Strongly Without Being the Same Thing", fontsize=15, y=1.02)

    ax = axes[0]
    y = np.arange(len(order))
    left = np.zeros(len(order))
    for mode in ["physical", "virtual"]:
        vals = []
        for ch in order:
            value = route.loc[(route["channel_group"].eq(ch)) & (route["route_mode"].eq(mode)), "share_within_channel"].iloc[0]
            vals.append(value)
        ax.barh(
            y,
            vals,
            left=left,
            label=mode,
            color=ROUTE_COLORS[mode],
            edgecolor="none",
            linewidth=0,
        )
        for yi, start, value in zip(y, left, vals):
            if value > 0.08:
                ax.text(start + value / 2, yi, pct(value), ha="center", va="center", fontsize=9, color=COLORS["ink"])
            elif mode == "virtual":
                ax.text(0.985, yi, pct(value), ha="right", va="center", fontsize=9, color=COLORS["ink"])
        left += np.array(vals)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Route-mode share within channel")
    ax.xaxis.set_major_formatter(lambda x, _: pct(x))
    ax.set_title("Within-channel route composition")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=2)
    style_axes(ax, "x")

    ax = axes[1]
    virtual = route.loc[route["route_mode"].eq("virtual")].copy()
    total_virtual_rows = virtual["rows"].sum()
    total_virtual_edges = virtual["edges"].sum()
    metric_rows = []
    for ch in order:
        row = virtual.loc[virtual["channel_group"].eq(ch)].iloc[0]
        metric_rows.append(
            {
                "channel": ch,
                "Virtual-row share": row["rows"] / total_virtual_rows,
                "Virtual-edge share": row["edges"] / total_virtual_edges,
            }
        )
    metric_df = pd.DataFrame(metric_rows)
    x = np.arange(len(order))
    width = 0.34
    ax.bar(
        x - width / 2,
        metric_df["Virtual-row share"],
        width=width,
        color=COLORS["gold"],
        label="Virtual rows",
        edgecolor="none",
        linewidth=0,
    )
    ax.bar(
        x + width / 2,
        metric_df["Virtual-edge share"],
        width=width,
        color=COLORS["slate"],
        label="Virtual edges",
        edgecolor="none",
        linewidth=0,
    )
    for xpos, value in zip(x - width / 2, metric_df["Virtual-row share"]):
        ax.text(xpos, value + 0.02, pct(value), ha="center", fontsize=9)
    for xpos, value in zip(x + width / 2, metric_df["Virtual-edge share"]):
        ax.text(xpos, value + 0.02, pct(value), ha="center", fontsize=9)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 0.96)
    ax.set_ylabel("Share of all virtual route evidence")
    ax.yaxis.set_major_formatter(lambda y, _: pct(y))
    ax.set_title("Where virtual routing concentrates")
    ax.legend(frameon=False)
    style_axes(ax)

    fig.tight_layout()
    savefig("03_channel_route_mode_interaction.png")


def plot_daily_channel_continuity(data: dict[str, pd.DataFrame]) -> None:
    daily = data["daily"].copy()
    order = ["card_present", "card_not_present"]
    labels = {"card_present": "card present", "card_not_present": "card not present"}

    fig, axes = plt.subplots(2, 1, figsize=(13.5, 7.0), sharex=True, gridspec_kw={"height_ratios": [1.35, 1.0]})
    fig.suptitle("Both Channel Lanes Persist Across the Full 90-Day Operating Window", fontsize=15, y=0.99)

    ax = axes[0]
    for ch in order:
        subset = daily.loc[daily["channel_group"].eq(ch)].sort_values("utc_date")
        ax.plot(subset["utc_date"], subset["daily_row_share"], color=CHANNEL_COLORS[ch], linewidth=2.1, label=labels[ch])
    ax.set_ylabel("Daily row share")
    ax.yaxis.set_major_formatter(lambda y, _: pct(y))
    ax.set_ylim(0.25, 0.74)
    ax.set_title("Daily channel mix is continuous and bounded, not absent or flat")
    ax.legend(frameon=False, ncol=2, loc="upper center")
    style_axes(ax)

    ax = axes[1]
    for ch in order:
        subset = daily.loc[daily["channel_group"].eq(ch)].sort_values("utc_date")
        ax.plot(subset["utc_date"], subset["merchants"], color=CHANNEL_COLORS[ch], linewidth=2.0, label=labels[ch])
    ax.set_ylabel("Active merchants")
    ax.set_xlabel("UTC date")
    ax.set_title("Daily merchant participation by channel")
    ax.set_xlim(daily["utc_date"].min(), daily["utc_date"].max())
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    style_axes(ax)

    fig.tight_layout()
    savefig("04_daily_channel_share_and_presence.png")


def plot_channel_operating_footprint(data: dict[str, pd.DataFrame]) -> None:
    overview = data["overview"].copy()
    order = ["card_present", "card_not_present"]
    labels = ["card present", "card not present"]
    metrics = [
        ("row_share", "arrival rows"),
        ("merchant_share", "merchants"),
        ("sites", "physical sites"),
        ("edges", "virtual edges"),
        ("zones", "zones"),
        ("operational_timezones", "operational timezones"),
    ]
    rows = []
    for metric, label in metrics:
        total = overview[metric].sum() if metric not in {"row_share", "merchant_share"} else 1.0
        for ch in order:
            value = overview.loc[overview["channel_group"].eq(ch), metric].iloc[0]
            rows.append({"channel": ch, "metric": label, "share": value / total})
    footprint = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12.8, 6.0))
    y = np.arange(len(metrics))
    left = np.zeros(len(metrics))
    for ch, label in zip(order, labels):
        vals = [footprint.loc[(footprint["metric"].eq(metric_label)) & (footprint["channel"].eq(ch)), "share"].iloc[0] for _, metric_label in metrics]
        label_color = "white" if ch == "card_present" else COLORS["ink"]
        ax.barh(
            y,
            vals,
            left=left,
            color=CHANNEL_COLORS[ch],
            label=label,
            edgecolor="none",
            linewidth=0,
            alpha=0.9 if ch == "card_present" else 0.82,
        )
        for yi, start, value in zip(y, left, vals):
            if value >= 0.08:
                ax.text(
                    start + value / 2,
                    yi,
                    pct(value),
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=label_color,
                    fontweight="bold" if ch == "card_present" else "normal",
                )
        left += np.array(vals)
    ax.set_yticks(y, [label for _, label in metrics])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share within each operating footprint")
    ax.xaxis.set_major_formatter(lambda x, _: pct(x))
    ax.set_title("Channel footprint changes depending on what is being counted")
    ax.legend(frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.18))
    style_axes(ax, "x")

    fig.tight_layout()
    savefig("05_channel_operating_footprint.png")


def main() -> None:
    apply_style()
    data = load_inputs()
    plot_channel_identity_and_denominators(data)
    plot_merchant_exposure_distribution(data)
    plot_channel_route_interaction(data)
    plot_daily_channel_continuity(data)
    plot_channel_operating_footprint(data)
    print(f"Wrote channel-structure figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
