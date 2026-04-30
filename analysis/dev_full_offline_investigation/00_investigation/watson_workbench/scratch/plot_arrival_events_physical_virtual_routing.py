from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


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
    / "physical_virtual_routing"
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
    "plum": "#7b3f61",
}

ROUTE_COLORS = {
    "physical": COLORS["green"],
    "virtual": COLORS["gold"],
}

CHANNEL_COLORS = {
    "card_present": COLORS["blue"],
    "card_not_present": COLORS["rust"],
}


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


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def compact_int(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def savefig(name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGURE_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()


def load_inputs() -> dict[str, pd.DataFrame]:
    daily = pd.read_csv(EXPORT_DIR / "route_daily_summary.csv", parse_dates=["utc_date"])
    daily["daily_row_share"] = daily["rows"] / daily.groupby("utc_date")["rows"].transform("sum")

    return {
        "overview": pd.read_csv(EXPORT_DIR / "route_overview.csv"),
        "consistency": pd.read_csv(EXPORT_DIR / "route_consistency.csv"),
        "stability": pd.read_csv(EXPORT_DIR / "merchant_route_stability.csv"),
        "merchant_volume": pd.read_csv(EXPORT_DIR / "merchant_volume_by_route.csv"),
        "endpoint_density": pd.read_csv(EXPORT_DIR / "endpoint_density.csv"),
        "route_channel": pd.read_csv(EXPORT_DIR / "route_by_channel.csv"),
        "daily": daily,
        "daily_share_stats": pd.read_csv(EXPORT_DIR / "route_daily_share_stats.csv"),
        "top_zones": pd.read_csv(EXPORT_DIR / "top_zones_by_route.csv"),
    }


def plot_route_scale_and_denominators(data: dict[str, pd.DataFrame]) -> None:
    overview = data["overview"].copy()
    order = ["physical", "virtual"]
    overview["route_mode"] = pd.Categorical(overview["route_mode"], categories=order, ordered=True)
    overview = overview.sort_values("route_mode")

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 5.6), gridspec_kw={"width_ratios": [1.05, 1.35]})
    fig.suptitle("Physical Routing Dominates Scale, but Virtual Routing Is Material by Exposure", fontsize=15, y=1.03)

    ax = axes[0]
    metrics = [
        ("arrival rows", overview.loc[overview["route_mode"].eq("physical"), "row_share"].iloc[0], overview.loc[overview["route_mode"].eq("virtual"), "row_share"].iloc[0]),
        ("merchants", overview.loc[overview["route_mode"].eq("physical"), "merchant_share"].iloc[0], overview.loc[overview["route_mode"].eq("virtual"), "merchant_share"].iloc[0]),
        (
            "route endpoints",
            overview.loc[overview["route_mode"].eq("physical"), "sites"].iloc[0] / (overview["sites"].sum() + overview["edges"].sum()),
            overview.loc[overview["route_mode"].eq("virtual"), "edges"].iloc[0] / (overview["sites"].sum() + overview["edges"].sum()),
        ),
    ]
    metric_df = pd.DataFrame(metrics, columns=["denominator", "physical", "virtual"])
    y = np.arange(len(metric_df))
    left = np.zeros(len(metric_df))
    for route in ["physical", "virtual"]:
        values = metric_df[route].to_numpy(dtype=float)
        ax.barh(y, values, left=left, color=ROUTE_COLORS[route], label=route, edgecolor="none", linewidth=0)
        label_color = "white" if route == "physical" else COLORS["ink"]
        for yi, start, value in zip(y, left, values):
            if value >= 0.07:
                ax.text(
                    start + value / 2,
                    yi,
                    pct(value),
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=label_color,
                    fontweight="bold" if route == "physical" else "normal",
                )
            else:
                ax.text(start + value + 0.012, yi, pct(value), ha="left", va="center", fontsize=8, color=COLORS["ink"])
        left += values
    ax.set_yticks(y, metric_df["denominator"])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share within mutually exclusive denominator")
    ax.xaxis.set_major_formatter(lambda x, _: pct(x))
    ax.set_title("Route share changes by denominator")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    style_axes(ax, "x")

    ax = axes[1]
    context = overview.set_index("route_mode").loc[["physical", "virtual"], ["zones", "primary_timezones", "settlement_timezones", "operational_timezones"]]
    context = context.rename(columns={"primary_timezones": "primary tz", "settlement_timezones": "settlement tz", "operational_timezones": "operational tz"})
    x = np.arange(len(context.columns))
    width = 0.34
    for offset, route in [(-width / 2, "physical"), (width / 2, "virtual")]:
        values = context.loc[route].to_numpy(dtype=float)
        ax.bar(x + offset, values, width=width, color=ROUTE_COLORS[route], label=route, edgecolor="none", linewidth=0)
        for xpos, value in zip(x + offset, values):
            ax.text(xpos, value + 5, compact_int(value), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, context.columns, rotation=18, ha="right")
    ax.set_ylabel("Distinct count")
    ax.set_title("Context coverage counts, not additive shares")
    ax.legend(frameon=False)
    style_axes(ax)

    fig.tight_layout()
    savefig("01_route_scale_and_denominators.png")


def plot_route_contract_cleanliness(data: dict[str, pd.DataFrame]) -> None:
    consistency = data["consistency"].copy()
    stability = data["stability"].copy()
    state_labels = {
        "physical_valid_site_only": "physical rows:\nsite only",
        "virtual_valid_edge_only": "virtual rows:\nedge only",
    }
    consistency["state_label"] = consistency["route_key_state"].map(state_labels).fillna(consistency["route_key_state"])

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.0), gridspec_kw={"width_ratios": [1.25, 0.85]})
    fig.suptitle("The Endpoint Null Pattern Is Structural, Not Missingness", fontsize=15, y=1.04)

    ax = axes[0]
    valid = consistency.loc[consistency["route_key_state"].str.contains("valid")].copy()
    invalid_rows = consistency.loc[~consistency["route_key_state"].str.contains("valid"), "rows"].sum()
    bars = pd.concat(
        [
            valid[["state_label", "rows"]],
            pd.DataFrame([{"state_label": "invalid endpoint\nstates", "rows": invalid_rows}]),
        ],
        ignore_index=True,
    )
    colors = [ROUTE_COLORS["physical"], ROUTE_COLORS["virtual"], COLORS["rust"]]
    ax.barh(bars["state_label"], bars["rows"], color=colors, edgecolor="none", linewidth=0)
    for _, row in bars.iterrows():
        if row["rows"] > 0:
            text_x = row["rows"] * 0.5
            text_color = "white" if row["rows"] > 50_000_000 else COLORS["ink"]
            ax.text(text_x, row["state_label"], compact_int(row["rows"]), va="center", ha="center", color=text_color, fontweight="bold")
        else:
            ax.text(consistency["rows"].max() * 0.015, row["state_label"], "0", va="center", ha="left", color=COLORS["ink"], fontweight="bold")
    ax.set_xlim(0, consistency["rows"].max() * 1.08)
    ax.set_xlabel("Rows")
    ax.xaxis.set_major_formatter(lambda x, _: compact_int(x))
    ax.set_title("Route-key states observed in the surface")
    style_axes(ax, "x")
    ax.text(
        0.02,
        -0.28,
        "The zero invalid row count is the evidence that nulls are contract-coded endpoints, not missing data.",
        transform=ax.transAxes,
        fontsize=9,
        color=COLORS["ink"],
    )

    ax = axes[1]
    ax.barh(
        stability["route_mode_count"].astype(str),
        stability["merchants"],
        color=COLORS["slate"],
        edgecolor="none",
        linewidth=0,
    )
    for _, row in stability.iterrows():
        ax.text(row["merchants"] * 0.5, str(row["route_mode_count"]), f"{int(row['merchants']):,} merchants", va="center", ha="center", color="white", fontweight="bold")
    ax.set_yticks([0], ["exactly one"])
    ax.set_xlim(0, stability["merchants"].max() * 1.08)
    ax.set_xlabel("Merchants")
    ax.set_ylabel("Distinct route modes per merchant")
    ax.set_title("Merchant route stability")
    style_axes(ax, "x")

    fig.tight_layout()
    savefig("02_route_contract_cleanliness.png")


def plot_merchant_exposure_density(data: dict[str, pd.DataFrame]) -> None:
    merchant = data["merchant_volume"].set_index("route_mode").loc[["physical", "virtual"]]
    quantile_cols = [
        "p05_rows_per_merchant",
        "p25_rows_per_merchant",
        "median_rows_per_merchant",
        "p75_rows_per_merchant",
        "p95_rows_per_merchant",
    ]
    labels = ["p05", "p25", "median", "p75", "p95"]

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.2), gridspec_kw={"width_ratios": [1.25, 0.95]})
    fig.suptitle("Virtual Merchants Are Fewer, but More Arrival-Dense", fontsize=15, y=1.04)

    ax = axes[0]
    for route in ["physical", "virtual"]:
        values = merchant.loc[route, quantile_cols].to_numpy(dtype=float)
        ax.plot(labels, values, marker="o", linewidth=2.4, color=ROUTE_COLORS[route], label=route)
        for idx, value in enumerate(values):
            ax.text(idx, value * 1.045, compact_int(value), ha="center", va="bottom", fontsize=8, color=ROUTE_COLORS[route])
    ax.set_yscale("log")
    ax.set_ylabel("Rows per merchant (log scale)")
    ax.set_title("Merchant-level exposure quantiles")
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[1]
    ratios = pd.Series(
        {
            "mean": merchant.loc["virtual", "mean_rows_per_merchant"] / merchant.loc["physical", "mean_rows_per_merchant"],
            "median": merchant.loc["virtual", "median_rows_per_merchant"] / merchant.loc["physical", "median_rows_per_merchant"],
            "p95": merchant.loc["virtual", "p95_rows_per_merchant"] / merchant.loc["physical", "p95_rows_per_merchant"],
        }
    )
    x = np.arange(len(ratios))
    ax.bar(x, ratios, color=COLORS["gold"], edgecolor="none", linewidth=0)
    ax.axhline(1, color=COLORS["ink"], linewidth=1.1)
    for xpos, value in zip(x, ratios):
        ax.text(xpos, value + 0.08, f"{value:.2f}x", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x, ratios.index)
    ax.set_ylim(0, max(ratios) * 1.28)
    ax.set_ylabel("Virtual / physical")
    ax.set_title("Virtual merchant density lift")
    style_axes(ax)

    fig.tight_layout()
    savefig("03_merchant_exposure_density_by_route.png")


def plot_endpoint_density(data: dict[str, pd.DataFrame]) -> None:
    endpoint = data["endpoint_density"].copy()
    endpoint["route_mode"] = endpoint["endpoint_type"].map({"physical_site": "physical", "virtual_edge": "virtual"})
    endpoint = endpoint.set_index("route_mode").loc[["physical", "virtual"]]
    quantile_cols = [
        "p05_rows_per_endpoint",
        "p25_rows_per_endpoint",
        "median_rows_per_endpoint",
        "p75_rows_per_endpoint",
        "p95_rows_per_endpoint",
    ]
    labels = ["p05", "p25", "median", "p75", "p95"]

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.2), gridspec_kw={"width_ratios": [1.25, 0.95]})
    fig.suptitle("Virtual Edges Compress Arrival Load Into a Smaller Endpoint Estate", fontsize=15, y=1.04)

    ax = axes[0]
    for route in ["physical", "virtual"]:
        values = endpoint.loc[route, quantile_cols].to_numpy(dtype=float)
        ax.plot(labels, values, marker="o", linewidth=2.4, color=ROUTE_COLORS[route], label=route)
        for idx, value in enumerate(values):
            ax.text(idx, value * 1.045, compact_int(value), ha="center", va="bottom", fontsize=8, color=ROUTE_COLORS[route])
    ax.set_yscale("log")
    ax.set_ylabel("Rows per endpoint (log scale)")
    ax.set_title("Endpoint-level exposure quantiles")
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[1]
    ratios = pd.Series(
        {
            "mean": endpoint.loc["virtual", "mean_rows_per_endpoint"] / endpoint.loc["physical", "mean_rows_per_endpoint"],
            "median": endpoint.loc["virtual", "median_rows_per_endpoint"] / endpoint.loc["physical", "median_rows_per_endpoint"],
            "p95": endpoint.loc["virtual", "p95_rows_per_endpoint"] / endpoint.loc["physical", "p95_rows_per_endpoint"],
        }
    )
    x = np.arange(len(ratios))
    ax.bar(x, ratios, color=COLORS["gold"], edgecolor="none", linewidth=0)
    ax.axhline(1, color=COLORS["ink"], linewidth=1.1)
    for xpos, value in zip(x, ratios):
        ax.text(xpos, value + 0.12, f"{value:.2f}x", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x, ratios.index)
    ax.set_ylim(0, max(ratios) * 1.28)
    ax.set_ylabel("Virtual edge / physical site")
    ax.set_title("Virtual endpoint density lift")
    style_axes(ax)

    fig.tight_layout()
    savefig("04_endpoint_density_by_route.png")


def plot_route_channel_intersection(data: dict[str, pd.DataFrame]) -> None:
    route_channel = data["route_channel"].copy()
    routes = ["physical", "virtual"]
    channels = ["card_present", "card_not_present"]
    channel_labels = ["card present", "card not present"]

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.5), gridspec_kw={"width_ratios": [1.1, 1.05]})
    fig.suptitle("Route Mode and Channel Are Related, but They Do Not Collapse Into One Field", fontsize=15, y=1.04)

    ax = axes[0]
    y = np.arange(len(routes))
    left = np.zeros(len(routes))
    for channel, label in zip(channels, channel_labels):
        values = []
        for route in routes:
            values.append(
                route_channel.loc[
                    route_channel["route_mode"].eq(route) & route_channel["channel_group"].eq(channel),
                    "share_within_route_mode",
                ].iloc[0]
            )
        ax.barh(
            y,
            values,
            left=left,
            color=CHANNEL_COLORS[channel],
            label=label,
            edgecolor="none",
            linewidth=0,
        )
        label_color = "white" if channel == "card_present" else COLORS["ink"]
        for yi, start, value in zip(y, left, values):
            if value >= 0.08:
                ax.text(start + value / 2, yi, pct(value), ha="center", va="center", fontsize=9, color=label_color, fontweight="bold" if channel == "card_present" else "normal")
        left += np.array(values)
    ax.set_yticks(y, routes)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Channel share within route mode")
    ax.xaxis.set_major_formatter(lambda x, _: pct(x))
    ax.set_title("Within-route channel composition")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=2)
    style_axes(ax, "x")

    ax = axes[1]
    pivot = route_channel.pivot(index="route_mode", columns="channel_group", values="rows").loc[routes, channels]
    total = pivot.to_numpy().sum()
    matrix = pivot.to_numpy() / total
    im = ax.imshow(matrix, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("route_heat", [COLORS["soft"], COLORS["gold"], COLORS["rust"]]), aspect="auto")
    ax.set_xticks(np.arange(len(channels)), channel_labels, rotation=15, ha="right")
    ax.set_yticks(np.arange(len(routes)), routes)
    for i, route in enumerate(routes):
        for j, channel in enumerate(channels):
            value = matrix[i, j]
            rows = pivot.iloc[i, j]
            text_color = "white" if value > 0.35 else COLORS["ink"]
            ax.text(j, i, f"{pct(value)}\n{compact_int(rows)} rows", ha="center", va="center", color=text_color, fontsize=9, fontweight="bold" if value > 0.35 else "normal")
    ax.set_title("Four-way operating footprint share")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.yaxis.set_major_formatter(lambda x, _: pct(x))

    fig.tight_layout()
    savefig("05_route_channel_intersection.png")


def plot_daily_route_continuity(data: dict[str, pd.DataFrame]) -> None:
    daily = data["daily"].copy()
    overview = data["overview"].set_index("route_mode")
    route_universe = {
        "physical": overview.loc["physical", "merchants"],
        "virtual": overview.loc["virtual", "merchants"],
    }
    daily["merchant_presence_share"] = daily.apply(lambda row: row["merchants"] / route_universe[row["route_mode"]], axis=1)

    fig, axes = plt.subplots(2, 1, figsize=(13.4, 7.2), sharex=True, gridspec_kw={"height_ratios": [1.25, 1.0]})
    fig.suptitle("Physical and Virtual Routing Persist Across the Full Operating Window", fontsize=15, y=0.995)

    ax = axes[0]
    subset = daily.loc[daily["route_mode"].eq("virtual")].sort_values("utc_date")
    mean = subset["daily_row_share"].mean()
    ax.fill_between(subset["utc_date"], subset["daily_row_share"].min(), subset["daily_row_share"].max(), color=COLORS["gold"], alpha=0.12, label="virtual daily range")
    ax.plot(subset["utc_date"], subset["daily_row_share"], color=ROUTE_COLORS["virtual"], linewidth=2.2, label="virtual")
    ax.axhline(mean, color=COLORS["ink"], linewidth=1.3, linestyle="--", label=f"mean {pct(mean)}")
    ax.set_ylabel("Daily row share")
    ax.yaxis.set_major_formatter(lambda y, _: pct(y))
    ax.set_ylim(max(0, subset["daily_row_share"].min() - 0.01), subset["daily_row_share"].max() + 0.012)
    ax.set_title("Virtual route share is visible when not crushed against physical dominance")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    style_axes(ax)

    ax = axes[1]
    for route in ["physical", "virtual"]:
        subset = daily.loc[daily["route_mode"].eq(route)].sort_values("utc_date")
        ax.plot(subset["utc_date"], subset["merchant_presence_share"], color=ROUTE_COLORS[route], linewidth=2.0, label=route)
    ax.set_ylabel("Share of route merchants active")
    ax.yaxis.set_major_formatter(lambda y, _: pct(y))
    ax.set_ylim(0.975, 1.003)
    ax.set_xlabel("UTC date")
    ax.set_title("Route-specific merchant presence is effectively complete each day")
    ax.set_xlim(daily["utc_date"].min(), daily["utc_date"].max())
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(frameon=False, ncol=2, loc="lower left")
    style_axes(ax)

    fig.tight_layout()
    savefig("06_daily_route_continuity.png")


def plot_zone_and_timezone_footprint(data: dict[str, pd.DataFrame]) -> None:
    overview = data["overview"].set_index("route_mode").loc[["physical", "virtual"]].copy()
    zones = data["top_zones"].copy()

    fig, axes = plt.subplots(1, 3, figsize=(15.8, 6.4), gridspec_kw={"width_ratios": [0.9, 1.0, 1.0]})
    fig.suptitle("Virtual Routing Is Geographically Broad, but Its Settlement Clock Footprint Is Compressed", fontsize=15, y=1.02)

    ax = axes[0]
    metrics = ["zones", "primary_timezones", "settlement_timezones", "operational_timezones"]
    labels = ["zones", "primary tz", "settlement tz", "operational tz"]
    x = np.arange(len(metrics))
    width = 0.34
    for offset, route in [(-width / 2, "physical"), (width / 2, "virtual")]:
        values = overview.loc[route, metrics].to_numpy(dtype=float)
        ax.bar(x + offset, values, width=width, color=ROUTE_COLORS[route], label=route, edgecolor="none", linewidth=0)
        for xpos, value in zip(x + offset, values):
            ax.text(xpos, value + 5, compact_int(value), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, labels, rotation=18, ha="right")
    ax.set_ylabel("Distinct count")
    ax.set_title("Geographic and timezone footprint")
    ax.legend(frameon=False)
    style_axes(ax)

    for ax, route in zip(axes[1:], ["physical", "virtual"]):
        subset = zones.loc[zones["route_mode"].eq(route)].sort_values("route_rank").head(8).iloc[::-1].copy()
        subset["zone_label"] = subset["zone_representation"].str.replace("_", " ", regex=False)
        y = np.arange(len(subset))
        ax.barh(y, subset["share_within_route_mode"], color=ROUTE_COLORS[route], edgecolor="none", linewidth=0)
        ax.set_yticks(y, subset["zone_label"])
        ax.xaxis.set_major_formatter(lambda x, _: pct(x))
        ax.set_xlabel("Share within route mode")
        ax.set_xlim(0, max(0.085, subset["share_within_route_mode"].max() * 1.12))
        ax.set_title(f"Top {route} zones")
        for yi, value in zip(y, subset["share_within_route_mode"]):
            ax.text(value + 0.001, yi, pct(value), va="center", ha="left", fontsize=8)
        style_axes(ax, "x")

    fig.tight_layout()
    savefig("07_zone_and_timezone_footprint.png")


def main() -> None:
    apply_style()
    data = load_inputs()
    plot_route_scale_and_denominators(data)
    plot_route_contract_cleanliness(data)
    plot_merchant_exposure_density(data)
    plot_endpoint_density(data)
    plot_route_channel_intersection(data)
    plot_daily_route_continuity(data)
    plot_zone_and_timezone_footprint(data)
    print(f"Wrote physical-vs-virtual routing figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
