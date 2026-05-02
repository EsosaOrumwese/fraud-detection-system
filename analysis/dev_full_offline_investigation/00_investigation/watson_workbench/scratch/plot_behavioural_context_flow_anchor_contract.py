from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[5]
EXPORT_ROOT = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_context"
)
BRANCH_EXPORT_DIR = EXPORT_ROOT / "branches" / "flow_anchor_contract"
FIG_DIR = BRANCH_EXPORT_DIR / "figures"


PALETTE = {
    "ink": "#262421",
    "muted": "#6d6860",
    "grid": "#dfd8ca",
    "bg": "#fbfaf7",
    "stream": "#2f6267",
    "anchor": "#d28a5b",
    "shared": "#7fa18c",
    "baseline": "#2f6267",
    "post": "#a36d70",
    "positive": "#7fa18c",
    "negative": "#c56f5d",
}


def fmt_millions(value: float) -> str:
    return f"{value / 1_000_000:.0f}M"


def fmt_billions(value: float) -> str:
    return f"{value / 1_000_000_000:.3f}B"


def fmt_compact(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{int(value):,}"


def style_axis(ax: plt.Axes, *, grid_axis: str = "y") -> None:
    ax.set_facecolor(PALETTE["bg"])
    ax.figure.set_facecolor(PALETTE["bg"])
    ax.grid(axis=grid_axis, color=PALETTE["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#433f38")
    ax.tick_params(axis="both", colors=PALETTE["ink"], labelsize=11)
    ax.title.set_color(PALETTE["ink"])
    ax.xaxis.label.set_color(PALETTE["ink"])
    ax.yaxis.label.set_color(PALETTE["ink"])


def save(fig: plt.Figure, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename, bbox_inches="tight")
    plt.close(fig)


def plot_schema_responsibility(field_map: pd.DataFrame) -> None:
    pairs = [("baseline", "Baseline"), ("post_overlay", "Post-overlay")]
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 8.5), dpi=180, sharex=True)
    cmap = ListedColormap(["#f0ebe2", PALETTE["stream"], PALETTE["anchor"], PALETTE["shared"]])

    for ax, (pair_key, pair_label) in zip(axes, pairs):
        subset = field_map[field_map["pair"] == pair_key].copy()
        subset["state"] = (
            subset["in_event_stream"].astype(int) + subset["in_flow_anchor"].astype(int) * 2
        )
        order = [
            "flow_id",
            "event_seq",
            "event_type",
            "ts_utc",
            "amount",
            "arrival_seq",
            "merchant_id",
            "party_id",
            "account_id",
            "instrument_id",
            "device_id",
            "ip_id",
            "fraud_flag",
            "campaign_id",
            "seed",
            "manifest_fingerprint",
            "parameter_hash",
            "scenario_id",
        ]
        subset["column"] = pd.Categorical(subset["column"], categories=order, ordered=True)
        subset = subset.sort_values("column").dropna(subset=["column"])

        matrix = subset["state"].to_numpy().reshape(-1, 1)
        ax.imshow(matrix, cmap=cmap, vmin=0, vmax=3, aspect="auto")
        ax.set_title(pair_label, fontsize=15, weight="bold", pad=10)
        ax.set_yticks(np.arange(len(subset)))
        ax.set_yticklabels(subset["column"].astype(str))
        ax.set_xticks([0])
        ax.set_xticklabels(["Field location"])
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", labelsize=10)
        for idx, value in enumerate(subset["state"]):
            label = {1: "stream", 2: "anchor", 3: "both"}.get(int(value), "")
            ax.text(0, idx, label, ha="center", va="center", fontsize=8.5, color="white" if value else PALETTE["ink"])
        ax.spines[:].set_visible(False)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["stream"], label="Stream only"),
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["anchor"], label="Anchor only"),
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["shared"], label="Both"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=11)
    fig.suptitle("Event Stream and Flow Anchor Field Responsibility", fontsize=21, weight="bold", y=0.98)
    fig.subplots_adjust(bottom=0.12)
    save(fig, "01_event_anchor_field_responsibility.png")


def plot_grain_ratio(profile: pd.DataFrame) -> None:
    labels = ["Baseline", "Post-overlay"]
    x = np.arange(len(labels))
    width = 0.34

    fig, ax = plt.subplots(figsize=(11.5, 7.2), dpi=180)
    style_axis(ax)
    event_bars = ax.bar(
        x - width / 2,
        profile["event_rows"],
        width,
        color=PALETTE["stream"],
        edgecolor="none",
        label="Event rows",
    )
    anchor_bars = ax.bar(
        x + width / 2,
        profile["anchor_rows"],
        width,
        color=PALETTE["anchor"],
        edgecolor="none",
        label="Anchor rows",
    )
    ax.set_title("Event Rows vs Flow Anchor Rows", fontsize=20, weight="bold", pad=14)
    ax.set_ylabel("Rows")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: fmt_millions(y)))
    ax.legend(frameon=False, loc="upper right")

    for bars in [event_bars, anchor_bars]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + profile["event_rows"].max() * 0.025,
                fmt_millions(height),
                ha="center",
                va="bottom",
                fontsize=11,
                color=PALETTE["ink"],
            )

    save(fig, "02_event_anchor_grain_ratio.png")


def plot_amount_duplication(profile: pd.DataFrame) -> None:
    labels = ["Baseline", "Post-overlay"]
    x = np.arange(len(labels))
    width = 0.34

    fig, ax = plt.subplots(figsize=(11.5, 7.2), dpi=180)
    style_axis(ax)
    event_bars = ax.bar(
        x - width / 2,
        profile["event_total_amount"],
        width,
        color=PALETTE["stream"],
        edgecolor="none",
        label="Event total amount",
    )
    anchor_bars = ax.bar(
        x + width / 2,
        profile["anchor_total_amount"],
        width,
        color=PALETTE["anchor"],
        edgecolor="none",
        label="Anchor total amount",
    )
    ax.set_title("Event-Grain Amount Total vs Flow-Grain Amount Total", fontsize=20, weight="bold", pad=14)
    ax.set_ylabel("Amount")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: fmt_billions(y)))
    ax.legend(frameon=False, loc="upper right")

    for bars in [event_bars, anchor_bars]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + profile["event_total_amount"].max() * 0.025,
                fmt_billions(height),
                ha="center",
                va="bottom",
                fontsize=10.5,
                color=PALETTE["ink"],
            )

    save(fig, "03_event_anchor_amount_denominator.png")


def plot_entity_cardinality(profile: pd.DataFrame) -> None:
    row = profile.iloc[0]
    fields = ["merchants", "approx_parties", "approx_accounts", "approx_instruments", "approx_devices", "approx_ips"]
    labels = ["Merchants", "Parties", "Accounts", "Instruments", "Devices", "IPs"]
    values = [row[field] for field in fields]

    fig, ax = plt.subplots(figsize=(12.5, 7.2), dpi=180)
    style_axis(ax, grid_axis="y")
    bars = ax.bar(labels, values, color=PALETTE["shared"], edgecolor="none")
    ax.set_yscale("log")
    ax.set_title("Entity Breadth Recovered Through Flow Anchors", fontsize=20, weight="bold", pad=14)
    ax.set_ylabel("Approx distinct IDs (log scale)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: fmt_compact(y)))
    ax.tick_params(axis="x", rotation=20)

    for bar, value in zip(bars, values):
        label = fmt_compact(value)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.18,
            label,
            ha="center",
            va="bottom",
            fontsize=10.5,
            color=PALETTE["ink"],
        )

    save(fig, "04_anchor_entity_cardinality_profile.png")


def plot_fraud_overlay_contract(fraud_vs_baseline: pd.DataFrame) -> None:
    row = fraud_vs_baseline.iloc[0]
    total = int(row["fraud_flows"])
    checks = [
        ("Baseline match", int(row["matched_baseline_flows"]), int(row["missing_baseline_flows"])),
        ("Timestamp preserved", int(row["same_ts_rows"]), total - int(row["same_ts_rows"])),
        ("Amount changed", total - int(row["same_amount_rows"]), int(row["same_amount_rows"])),
    ]

    labels = [item[0] for item in checks]
    pass_values = [item[1] for item in checks]
    exception_values = [item[2] for item in checks]
    y = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(12, 6.8), dpi=180)
    style_axis(ax, grid_axis="x")
    pass_bars = ax.barh(y, pass_values, color=PALETTE["positive"], edgecolor="none", label="Pass")
    ax.barh(y, exception_values, left=pass_values, color=PALETTE["negative"], edgecolor="none", label="Exception")
    ax.set_title("Fraud Flow Overlay Checks Against Baseline Anchor", fontsize=20, weight="bold", pad=14)
    ax.set_xlabel("Fraud flows")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlim(0, total * 1.15)
    ax.legend(frameon=False, loc="lower right")

    for bar, pass_value, exception_value in zip(pass_bars, pass_values, exception_values):
        ax.text(
            pass_value - total * 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{pass_value:,}",
            ha="right",
            va="center",
            fontsize=11,
            color="white",
        )
        ax.text(
            pass_value + total * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{exception_value:,}",
            ha="left",
            va="center",
            fontsize=10.5,
            color=PALETTE["negative"],
        )

    save(fig, "06_fraud_overlay_anchor_checks.png")


def plot_fraud_amount_delta(delta_distribution: pd.DataFrame) -> None:
    row = delta_distribution.iloc[0]
    labels = ["Min", "P05", "P25", "Median", "Mean", "P75", "P95", "Max"]
    values = [
        float(row["min_amount_delta"]),
        float(row["p05_amount_delta"]),
        float(row["p25_amount_delta"]),
        float(row["median_amount_delta"]),
        float(row["mean_amount_delta"]),
        float(row["p75_amount_delta"]),
        float(row["p95_amount_delta"]),
        float(row["max_amount_delta"]),
    ]
    x = np.arange(len(labels))
    colors = [
        PALETTE["muted"],
        PALETTE["baseline"],
        PALETTE["post"],
        PALETTE["ink"],
        PALETTE["positive"],
        PALETTE["post"],
        PALETTE["baseline"],
        PALETTE["muted"],
    ]

    fig, ax = plt.subplots(figsize=(12.5, 6.8), dpi=180)
    style_axis(ax, grid_axis="y")
    ax.plot(x, values, color=PALETTE["post"], linewidth=2.5, alpha=0.55, zorder=2)
    ax.scatter(x, values, s=[110, 120, 130, 170, 180, 130, 120, 110], color=colors, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Amount delta (log scale)")
    ax.set_title("Fraud Flow Amount Delta Quantiles", fontsize=20, weight="bold", pad=14)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:,.2f}" if y < 10 else f"{y:,.0f}"))

    for idx, value in enumerate(values):
        ax.text(
            idx,
            value * 1.22,
            f"{value:.2f}",
            ha="center",
            va="bottom",
            fontsize=10.5,
            color=PALETTE["ink"],
        )

    save(fig, "07_fraud_anchor_amount_delta_range.png")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    field_map = pd.read_csv(BRANCH_EXPORT_DIR / "event_anchor_field_map.csv")
    profile = pd.read_csv(BRANCH_EXPORT_DIR / "event_anchor_pair_profile.csv")
    fraud_vs_baseline = pd.read_csv(EXPORT_ROOT / "fraud_anchor_vs_baseline.csv")
    delta_distribution = pd.read_csv(BRANCH_EXPORT_DIR / "fraud_anchor_amount_delta_distribution.csv")

    plot_schema_responsibility(field_map)
    plot_grain_ratio(profile)
    plot_amount_duplication(profile)
    plot_entity_cardinality(profile)
    plot_fraud_overlay_contract(fraud_vs_baseline)
    plot_fraud_amount_delta(delta_distribution)

    print(f"Wrote figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
