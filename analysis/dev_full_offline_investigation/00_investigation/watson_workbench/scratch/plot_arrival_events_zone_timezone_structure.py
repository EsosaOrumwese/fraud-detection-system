from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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
    / "zone_timezone_structure"
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


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORT_DIR / name)


def savefig(fig: plt.Figure, filename: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / filename, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(TEXT)
    ax.spines["bottom"].set_color(TEXT)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)


def fmt_millions(value: float) -> str:
    return f"{value / 1_000_000:.1f}M"


def ensure_merchant_detail_exports() -> None:
    merchant_zone_path = EXPORT_DIR / "merchant_zone_detail.csv"
    merchant_zone_hour_path = EXPORT_DIR / "merchant_zone_top_detail.csv"
    if merchant_zone_path.exists() and merchant_zone_hour_path.exists():
        return

    con = duckdb.connect()
    con.execute("SET threads TO 8")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW arrivals AS
        SELECT *
        FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
        """
    )

    merchant_detail = con.execute(
        """
        WITH merchant_zone_rows AS (
            SELECT
                merchant_id,
                zone_representation,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY merchant_id, zone_representation
        ),
        ranked AS (
            SELECT
                merchant_id,
                zone_representation,
                rows,
                SUM(rows) OVER (PARTITION BY merchant_id) AS merchant_rows,
                ROW_NUMBER() OVER (PARTITION BY merchant_id ORDER BY rows DESC, zone_representation) AS zone_rank
            FROM merchant_zone_rows
        )
        SELECT
            merchant_id,
            MAX(merchant_rows)::UBIGINT AS rows,
            COUNT(*)::UBIGINT AS zones,
            MAX(zone_representation) FILTER (WHERE zone_rank = 1) AS top_zone,
            MAX(rows) FILTER (WHERE zone_rank = 1)::UBIGINT AS top_zone_rows,
            MAX(rows / merchant_rows) FILTER (WHERE zone_rank = 1) AS top_zone_row_share
        FROM ranked
        GROUP BY merchant_id
        ORDER BY rows DESC
        """
    ).fetchdf()
    merchant_detail.to_csv(merchant_zone_path, index=False)

    top_zone_detail = con.execute(
        """
        WITH merchant_zone_rows AS (
            SELECT
                merchant_id,
                zone_representation,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY merchant_id, zone_representation
        ),
        ranked AS (
            SELECT
                merchant_id,
                zone_representation,
                rows,
                SUM(rows) OVER (PARTITION BY merchant_id) AS merchant_rows,
                ROW_NUMBER() OVER (PARTITION BY merchant_id ORDER BY rows DESC, zone_representation) AS zone_rank
            FROM merchant_zone_rows
        )
        SELECT
            zone_representation AS top_zone,
            COUNT(*)::UBIGINT AS merchants_where_top_zone,
            SUM(merchant_rows)::UBIGINT AS merchant_rows,
            AVG(rows / merchant_rows) AS mean_top_zone_share
        FROM ranked
        WHERE zone_rank = 1
        GROUP BY zone_representation
        ORDER BY merchants_where_top_zone DESC, merchant_rows DESC
        """
    ).fetchdf()
    top_zone_detail.to_csv(merchant_zone_hour_path, index=False)


def plot_zone_timezone_identity() -> None:
    overview = read_csv("zone_timezone_overview.csv").iloc[0]
    by_route = read_csv("zone_timezone_equality_by_route.csv")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle(
        "Zone Representation Is Related to Timezone Context, but It Is Not the Same Field",
        fontsize=18,
        color=TEXT,
        y=1.02,
    )

    ax = axes[0]
    labels = [
        "zone representations",
        "primary timezones",
        "settlement timezones",
        "operational timezones",
        "zone-primary pairs",
        "timezone triples",
    ]
    values = [
        overview["zones"],
        overview["primary_timezones"],
        overview["settlement_timezones"],
        overview["operational_timezones"],
        overview["zone_primary_pairs"],
        overview["timezone_triples"],
    ]
    colors = [GREEN, BLUE, PURPLE, BLUE, RUST, GOLD]
    y = np.arange(len(labels))
    ax.barh(y, values, color=colors, edgecolor="none", alpha=0.92)
    for i, value in enumerate(values):
        ax.text(value * 1.015, i, f"{int(value):,}", ha="left", va="center", fontsize=10, color=TEXT)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Distinct count")
    ax.set_title("Cardinality: one zone field, many clock relationships", fontsize=13, weight="bold")
    style_ax(ax)

    ax = axes[1]
    rows = by_route["rows"].to_numpy(dtype=float)
    match = by_route["rows_zone_equals_primary"].to_numpy(dtype=float)
    mismatch = rows - match
    x = np.arange(len(by_route))
    ax.bar(x, match / rows, color=GREEN, edgecolor="none", label="zone equals primary timezone")
    ax.bar(x, mismatch / rows, bottom=match / rows, color=RUST, edgecolor="none", label="zone differs from primary timezone")
    for i, row in by_route.iterrows():
        ax.text(
            i,
            0.04,
            f"{row['share_zone_equals_primary']:.1%}\nmatch",
            ha="center",
            va="bottom",
            fontsize=10,
            color="white" if row["share_zone_equals_primary"] > 0.22 else TEXT,
            weight="bold",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(by_route["route_mode"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of rows")
    ax.set_title("Most rows do not have zone = active timezone", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, fontsize=10, loc="upper right")
    style_ax(ax)

    savefig(fig, "01_zone_timezone_identity_check.png")


def plot_zone_exposure_concentration() -> None:
    zones = read_csv("zone_overview.csv")
    ranked = read_csv("zone_concentration_ranked.csv")
    top = zones.head(15).copy()
    top = top.sort_values("rows")

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.suptitle("Zone Exposure Is Broad, but the Arrival Rows Still Have a Concentrated Head", fontsize=18, color=TEXT)

    ax = axes[0]
    ax.barh(top["zone_representation"], top["rows"] / 1_000_000, color=GREEN, edgecolor="none", alpha=0.9)
    for y, row in enumerate(top.itertuples(index=False)):
        ax.text(row.rows / 1_000_000 + 0.15, y, f"{row.row_share:.1%}", va="center", fontsize=9, color=TEXT)
    ax.set_xlabel("Arrival rows (millions)")
    ax.set_title("Largest zone representations by arrival exposure", fontsize=13, weight="bold")
    style_ax(ax)

    ax = axes[1]
    ax.plot(ranked["zone_rank"], ranked["cumulative_row_share"], color=INK, linewidth=2.5)
    ax.fill_between(ranked["zone_rank"], ranked["cumulative_row_share"], color=GOLD, alpha=0.22)
    for rank in [5, 10, 20, 50, 100]:
        row = ranked.loc[ranked["zone_rank"] == rank].iloc[0]
        ax.scatter([rank], [row["cumulative_row_share"]], color=RUST, s=48, zorder=3)
        ax.text(rank + 4, row["cumulative_row_share"], f"top {rank}: {row['cumulative_row_share']:.1%}", fontsize=9, color=TEXT)
    ax.set_xlim(1, ranked["zone_rank"].max())
    ax.set_ylim(0, 1.03)
    ax.set_xlabel("Zone rank by rows")
    ax.set_ylabel("Cumulative row share")
    ax.set_title("No single zone dominates, but the head matters", fontsize=13, weight="bold")
    style_ax(ax)

    savefig(fig, "02_zone_exposure_concentration.png")


def plot_zone_exposure_vs_merchants() -> None:
    zones = read_csv("zone_overview.csv")
    top_names = set(zones.head(8)["zone_representation"])
    highlight_names = top_names | {"Africa/Accra", "Asia/Shanghai", "America/New_York"}

    fig, ax = plt.subplots(figsize=(12, 8))
    sizes = np.clip(zones["primary_timezones"], 10, 150)
    ax.scatter(
        zones["merchants"],
        zones["rows"] / 1_000_000,
        s=sizes,
        color=GREEN,
        alpha=0.58,
        edgecolor="none",
    )
    for row in zones[zones["zone_representation"].isin(highlight_names)].itertuples(index=False):
        ax.text(row.merchants + 18, row.rows / 1_000_000, row.zone_representation, fontsize=9, color=TEXT)
    ax.set_xlabel("Distinct merchants observed in zone")
    ax.set_ylabel("Arrival rows (millions)")
    ax.set_title(
        "Zone exposure is not only merchant presence: some zones are volume-heavy for their merchant count",
        fontsize=16,
        color=TEXT,
        pad=15,
    )
    ax.text(
        0.02,
        0.96,
        "Bubble size = distinct primary timezones within the zone",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        color=MUTED,
        bbox=dict(boxstyle="round,pad=0.35", facecolor=BG, edgecolor=GRID),
    )
    style_ax(ax)

    savefig(fig, "03_zone_rows_vs_merchants.png")


def plot_merchant_zone_spread() -> None:
    ensure_merchant_detail_exports()
    merchants = read_csv("merchant_zone_detail.csv")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Every Merchant Is Multi-Zone, but Most Merchants Still Have a Dominant Zone", fontsize=18, color=TEXT)

    ax = axes[0]
    bins = np.arange(0, merchants["zones"].max() + 5, 3)
    ax.hist(merchants["zones"], bins=bins, color=GREEN, edgecolor="none", alpha=0.9)
    median = merchants["zones"].median()
    p95 = merchants["zones"].quantile(0.95)
    ax.axvline(median, color=INK, linestyle="--", linewidth=2, label=f"median: {median:.0f}")
    ax.axvline(p95, color=RUST, linestyle=":", linewidth=2.5, label=f"p95: {p95:.0f}")
    ax.set_xlabel("Distinct zones per merchant")
    ax.set_ylabel("Merchants")
    ax.set_title("Zone is not a fixed merchant-home field", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    ax = axes[1]
    ax.hist(merchants["top_zone_row_share"], bins=np.linspace(0, 1, 31), color=GOLD, edgecolor="none", alpha=0.9)
    median_share = merchants["top_zone_row_share"].median()
    p25 = merchants["top_zone_row_share"].quantile(0.25)
    p75 = merchants["top_zone_row_share"].quantile(0.75)
    ax.axvline(median_share, color=INK, linestyle="--", linewidth=2, label=f"median: {median_share:.1%}")
    ax.axvspan(p25, p75, color=RUST, alpha=0.18, label=f"IQR: {p25:.0%}-{p75:.0%}")
    ax.set_xlabel("Share of merchant rows in its largest zone")
    ax.set_ylabel("Merchants")
    ax.set_title("Multi-zone does not mean evenly spread", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    savefig(fig, "04_merchant_zone_spread_and_dominance.png")


def plot_timezone_relationship_by_route() -> None:
    rel = read_csv("timezone_field_relationships_by_route.csv")
    pivot = rel.pivot(index="route_mode", columns="timezone_relationship", values="share_within_route").fillna(0)
    for col in ["all_three_equal", "primary_equals_operational_only"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot = pivot.loc[["physical", "virtual"], ["all_three_equal", "primary_equals_operational_only"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(pivot))
    colors = {"all_three_equal": GREEN, "primary_equals_operational_only": PURPLE}
    labels = {
        "all_three_equal": "primary = settlement = operational",
        "primary_equals_operational_only": "primary = operational, settlement differs",
    }
    x = np.arange(len(pivot))
    for col in pivot.columns:
        values = pivot[col].to_numpy(dtype=float)
        ax.bar(x, values, bottom=bottom, color=colors[col], edgecolor="none", label=labels[col])
        for i, value in enumerate(values):
            if value > 0.06:
                ax.text(i, bottom[i] + value / 2, f"{value:.1%}", ha="center", va="center", color="white", fontsize=11, weight="bold")
        bottom += values

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share within route mode")
    ax.set_title("Virtual routing is where settlement clock separation enters the arrival surface", fontsize=16, color=TEXT, pad=14)
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, loc="upper right")
    style_ax(ax)

    savefig(fig, "05_timezone_relationship_by_route.png")


def plot_utc_vs_local_hour_profiles() -> None:
    utc = read_csv("hour_profile_utc.csv").assign(clock_field="utc", hour=lambda d: d["utc_hour"])[["clock_field", "hour", "row_share"]]
    local = read_csv("hour_profile_local.csv").rename(columns={"local_hour": "hour"})[["clock_field", "hour", "row_share"]]
    local["clock_field"] = local["clock_field"].map(
        {"primary": "primary_local", "settlement": "settlement_local", "operational": "operational_local"}
    )
    profiles = pd.concat([utc, local], ignore_index=True)

    colors = {
        "utc": INK,
        "primary_local": GREEN,
        "operational_local": BLUE,
        "settlement_local": PURPLE,
    }
    labels = {
        "utc": "UTC",
        "primary_local": "primary local",
        "operational_local": "operational local",
        "settlement_local": "settlement local",
    }

    fig, ax = plt.subplots(figsize=(13, 7))
    for clock in ["utc", "primary_local", "operational_local", "settlement_local"]:
        sub = profiles[profiles["clock_field"] == clock].sort_values("hour")
        ax.plot(sub["hour"], sub["row_share"], marker="o", linewidth=2.2, markersize=4, color=colors[clock], label=labels[clock])

    ax.axvspan(10, 17, color=GOLD, alpha=0.12, label="10-17 hour band")
    ax.axvspan(3, 5, color=RUST, alpha=0.10, label="03-05 hour band")
    ax.set_xticks(range(0, 24))
    ax.set_xlabel("Hour")
    ax.set_ylabel("Share of rows")
    ax.set_title("UTC hour has a business-day shape, but local clocks sharpen the operating rhythm", fontsize=16, color=TEXT, pad=14)
    ax.legend(ncol=3, frameon=True, facecolor=BG, edgecolor=GRID, loc="upper left")
    style_ax(ax)

    savefig(fig, "06_utc_vs_local_hour_profiles.png")


def plot_top_zone_hour_heatmap() -> None:
    zone_hours = read_csv("zone_hour_profile_top_zones.csv")
    zones = read_csv("zone_overview.csv").head(20)["zone_representation"].tolist()
    matrix = (
        zone_hours[zone_hours["zone_representation"].isin(zones)]
        .pivot(index="zone_representation", columns="utc_hour", values="row_share")
        .reindex(zones)
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(15, 9))
    im = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="YlOrBr")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=10)
    ax.set_xticks(np.arange(24))
    ax.set_xticklabels([str(i) for i in range(24)])
    ax.set_xlabel("UTC hour")
    ax.set_title("The global UTC-hour shape does not repeat identically inside each high-volume zone", fontsize=16, color=TEXT, pad=14)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Share of zone rows")
    cbar.ax.tick_params(labelsize=9, colors=TEXT)

    for y, zone in enumerate(matrix.index):
        peak_hour = int(matrix.loc[zone].idxmax())
        ax.scatter([peak_hour], [y], marker="o", s=38, color=PURPLE, edgecolor="white", linewidth=0.8)

    ax.text(
        0.01,
        -0.09,
        "Purple dots mark each zone's peak UTC hour.",
        transform=ax.transAxes,
        fontsize=10,
        color=MUTED,
    )
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(TEXT)

    savefig(fig, "07_top_zone_utc_hour_heatmap.png")


def plot_zone_peak_hour_rollup() -> None:
    summary = read_csv("zone_hour_shape_summary.csv")
    top = summary[summary["rows"] >= 100_000].copy()

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Zone-Level UTC Peaks Are Distributed, Not Locked to the Global Peak", fontsize=18, color=TEXT)

    ax = axes[0]
    bins = np.arange(-0.5, 24.5, 1)
    ax.hist(summary["peak_utc_hour"], bins=bins, color=GREEN, alpha=0.75, edgecolor="none", label="all zones")
    ax.hist(top["peak_utc_hour"], bins=bins, color=RUST, alpha=0.55, edgecolor="none", label="zones with >=100k rows")
    ax.axvspan(10, 17, color=GOLD, alpha=0.15, label="global 10-17 band")
    ax.set_xticks(range(0, 24))
    ax.set_xlabel("Peak UTC hour")
    ax.set_ylabel("Zones")
    ax.set_title("Where each zone reaches its own UTC peak", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    ax = axes[1]
    ax.scatter(
        summary["rows"] / 1_000_000,
        summary["utc_business_band_share"],
        color=BLUE,
        alpha=0.62,
        edgecolor="none",
        s=38,
    )
    top5 = summary.sort_values("rows", ascending=False).head(8)
    for row in top5.itertuples(index=False):
        ax.text(row.rows / 1_000_000 + 0.08, row.utc_business_band_share, row.zone_representation, fontsize=9, color=TEXT)
    ax.axhline(0.42282234035639626, color=INK, linestyle="--", linewidth=2, label="global UTC 10-17 share")
    ax.set_xlabel("Zone rows (millions)")
    ax.set_ylabel("Share of zone rows in 10-17 UTC")
    ax.set_title("Large zones can have different UTC business-band exposure", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    style_ax(ax)

    savefig(fig, "08_zone_peak_hour_rollup.png")


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plot_zone_timezone_identity()
    plot_zone_exposure_concentration()
    plot_zone_exposure_vs_merchants()
    plot_merchant_zone_spread()
    plot_timezone_relationship_by_route()
    plot_utc_vs_local_hour_profiles()
    plot_top_zone_hour_heatmap()
    plot_zone_peak_hour_rollup()


if __name__ == "__main__":
    main()
