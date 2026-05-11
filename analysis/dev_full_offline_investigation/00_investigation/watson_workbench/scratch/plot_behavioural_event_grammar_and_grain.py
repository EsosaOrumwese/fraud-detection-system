from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[5]
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
    / "branches"
    / "event_grammar_and_grain"
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
BLUE = "#557a95"
PURPLE = "#7d4e73"


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


def millions_formatter(x: float, _: int) -> str:
    return f"{x / 1_000_000:.0f}M"


def percent_formatter(x: float, _: int) -> str:
    return f"{x:.0%}"


def plot_event_vs_flow_grain() -> None:
    grain = read_csv("stream_event_flow_grain.csv")
    seq_shape = read_csv("event_seq_type_shape.csv")
    streams = ["baseline", "with_fraud"]
    display = {"baseline": "baseline", "with_fraud": "with fraud"}

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1.2, 1]})
    fig.suptitle("Behavioural Stream Rows Are Event Sides, Not Flow Rows", fontsize=18, color=TEXT)

    ax = axes[0]
    x = np.arange(len(streams))
    request = [
        seq_shape[(seq_shape["stream_name"] == stream) & (seq_shape["event_type"] == "AUTH_REQUEST")]["rows"].iloc[0]
        for stream in streams
    ]
    response = [
        seq_shape[(seq_shape["stream_name"] == stream) & (seq_shape["event_type"] == "AUTH_RESPONSE")]["rows"].iloc[0]
        for stream in streams
    ]
    ax.bar(x, request, color=GREEN, width=0.58, label="AUTH_REQUEST")
    ax.bar(x, response, bottom=request, color=GOLD, width=0.58, label="AUTH_RESPONSE")
    for i, stream in enumerate(streams):
        total = request[i] + response[i]
        ax.text(i, total + 8_000_000, f"{total / 1_000_000:.1f}M\nevent rows", ha="center", va="bottom", fontsize=10, color=TEXT)
        ax.text(i, request[i] / 2, "50%", ha="center", va="center", fontsize=12, color="white", weight="bold")
        ax.text(i, request[i] + response[i] / 2, "50%", ha="center", va="center", fontsize=12, color=TEXT, weight="bold")
    ax.set_xticks(x, [display[s] for s in streams])
    ax.set_ylabel("Rows")
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.set_title("Each stream is split into request and response rows", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, loc="upper center")
    ax.set_ylim(0, 540_000_000)
    style_ax(ax)

    ax = axes[1]
    width = 0.34
    event_rows = [grain.loc[grain["stream_name"] == stream, "event_rows"].iloc[0] for stream in streams]
    implied_flows = [grain.loc[grain["stream_name"] == stream, "implied_flows_from_balanced_sequence"].iloc[0] for stream in streams]
    ax.bar(x - width / 2, event_rows, width=width, color=INK, label="event rows")
    ax.bar(x + width / 2, implied_flows, width=width, color=RUST, label="implied flows")
    ax.text(
        0.5,
        0.09,
        "For both streams: event rows = 2.0x implied flows",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=10,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.35", facecolor=BG, edgecolor=GRID, alpha=0.92),
    )
    ax.set_xticks(x, [display[s] for s in streams])
    ax.set_ylabel("Rows / implied flows")
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.set_title("The event denominator is twice the implied flow denominator", fontsize=13, weight="bold")
    ax.legend(frameon=True, facecolor=BG, edgecolor=GRID)
    ax.set_ylim(0, 540_000_000)
    style_ax(ax)

    savefig(fig, "01_event_rows_vs_implied_flows.png")


def plot_sequence_type_grammar() -> None:
    seq_shape = read_csv("event_seq_type_shape.csv")
    streams = ["baseline", "with_fraud"]
    event_types = ["AUTH_REQUEST", "AUTH_RESPONSE"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharey=True)
    fig.suptitle("Event Sequence and Event Type Form a Fixed Two-Side Grammar", fontsize=18, color=TEXT)

    for ax, stream in zip(axes, streams):
        matrix = np.zeros((2, 2), dtype=float)
        for _, row in seq_shape[seq_shape["stream_name"] == stream].iterrows():
            seq_idx = int(row["event_seq"])
            type_idx = event_types.index(row["event_type"])
            matrix[seq_idx, type_idx] = row["rows"] / 1_000_000
        im = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=250)
        ax.set_xticks([0, 1], ["AUTH_REQUEST", "AUTH_RESPONSE"], rotation=20, ha="right")
        ax.set_yticks([0, 1], ["event_seq 0", "event_seq 1"])
        ax.set_title(stream.replace("_", " "), fontsize=13, weight="bold")
        for i in range(2):
            for j in range(2):
                value = matrix[i, j]
                label = f"{value:.1f}M" if value else "0"
                color = "white" if value > 100 else TEXT
                ax.text(j, i, label, ha="center", va="center", color=color, fontsize=12, weight="bold")
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT)
        for spine in ax.spines.values():
            spine.set_visible(False)

    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.82, pad=0.03)
    cbar.set_label("Rows (millions)", color=TEXT)
    cbar.ax.tick_params(colors=TEXT)

    savefig(fig, "02_sequence_type_grammar_matrix.png")


def plot_approx_flow_count_caution() -> None:
    grain = read_csv("stream_event_flow_grain.csv")
    seq_shape = read_csv("event_seq_type_shape.csv")
    baseline_seq = seq_shape[(seq_shape["stream_name"] == "baseline") & (seq_shape["event_seq"] == 0)].iloc[0]
    implied = grain.loc[grain["stream_name"] == "baseline", "implied_flows_from_balanced_sequence"].iloc[0]
    approx = baseline_seq["approx_flows"]
    excess = approx - implied
    excess_pct = excess / implied

    fig, ax = plt.subplots(figsize=(9, 6))
    fig.suptitle("Approximate Flow Counts Are Profiling Signals, Not the Flow Denominator", fontsize=17, color=TEXT)
    labels = ["implied flows\nfrom grammar", "approx_count_distinct\nprofiling output"]
    values = [implied, approx]
    bars = ax.bar(labels, values, color=[GREEN, RUST], edgecolor="none", width=0.55)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 2_000_000, f"{value / 1_000_000:.1f}M", ha="center", va="bottom", fontsize=12, color=TEXT)
    ax.annotate(
        f"+{excess / 1_000_000:.1f}M\n({excess_pct:.1%})",
        xy=(1, approx),
        xytext=(0.52, approx + 22_000_000),
        ha="center",
        fontsize=11,
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED, "linewidth": 1.1},
        bbox=dict(boxstyle="round,pad=0.35", facecolor=BG, edgecolor=GRID),
    )
    ax.set_ylabel("Count")
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.set_ylim(0, approx * 1.18)
    ax.set_title("The branch uses the grammar-derived denominator for business-facing flow language", fontsize=12, weight="bold")
    style_ax(ax)

    savefig(fig, "03_approx_flow_count_caution.png")


def plot_amount_surface_mirroring() -> None:
    amount = read_csv("amount_surface_by_event_side.csv")
    streams = ["baseline", "with_fraud"]
    display = {"baseline": "baseline", "with_fraud": "with fraud"}

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), sharey=True)
    fig.suptitle("Amount Is Present on Both Event Sides, with Aggregate Mirroring", fontsize=18, color=TEXT)

    for ax, stream in zip(axes, streams):
        subset = amount[amount["stream_name"] == stream].set_index("event_type").loc[["AUTH_REQUEST", "AUTH_RESPONSE"]]
        x = np.arange(2)
        width = 0.34
        ax.bar(x - width / 2, subset["mean_amount"], width=width, color=GREEN, label="mean")
        ax.bar(x + width / 2, subset["median_amount"], width=width, color=GOLD, label="median")
        for i, event_type in enumerate(subset.index):
            ax.text(i - width / 2, subset.loc[event_type, "mean_amount"] + 0.5, f"{subset.loc[event_type, 'mean_amount']:.2f}", ha="center", fontsize=10, color=TEXT)
            ax.text(i + width / 2, subset.loc[event_type, "median_amount"] + 0.5, f"{subset.loc[event_type, 'median_amount']:.2f}", ha="center", fontsize=10, color=TEXT)
        ax.set_xticks(x, ["AUTH_REQUEST", "AUTH_RESPONSE"], rotation=15, ha="right")
        ax.set_title(display[stream], fontsize=13, weight="bold")
        ax.set_ylabel("Amount")
        ax.set_ylim(0, 30)
        ax.legend(frameon=True, facecolor=BG, edgecolor=GRID, loc="upper right")
        style_ax(ax)

    savefig(fig, "04_amount_surface_by_event_side.png")


def plot_fraud_balance_by_event_side() -> None:
    fraud = read_csv("fraud_balance_by_event_side.csv")
    true_rows = fraud[fraud["fraud_flag"].astype(str).str.lower() == "true"].copy()
    true_rows = true_rows.sort_values("event_seq")
    fraud_event_rows = int(true_rows["rows"].sum())
    fraud_flows = fraud_event_rows // 2

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.suptitle("Fraud Marking Is Sparse, Balanced by Event Side, and Grain-Sensitive", fontsize=17, color=TEXT)

    ax = axes[0]
    x = np.arange(len(true_rows))
    labels = [f"{row.event_type}\nseq {int(row.event_seq)}" for row in true_rows.itertuples()]
    bars = ax.bar(x, true_rows["rows"], color=[GREEN, GOLD], width=0.55)
    for bar, row in zip(bars, true_rows.itertuples()):
        ppm = row.share_within_event_type * 1_000_000
        ax.text(bar.get_x() + bar.get_width() / 2, row.rows + 180, f"{int(row.rows):,}\n{ppm:.1f} ppm", ha="center", va="bottom", fontsize=11, color=TEXT)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Fraud-marked event rows")
    ax.set_title("Fraud rows split evenly across event sides", fontsize=13, weight="bold")
    ax.set_ylim(0, 8_200)
    style_ax(ax)

    ax = axes[1]
    bars = ax.bar(["fraud\nevent rows", "fraud\nflows"], [fraud_event_rows, fraud_flows], color=[INK, RUST], width=0.55)
    for bar, value in zip(bars, [fraud_event_rows, fraud_flows]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 380, f"{value:,}", ha="center", va="bottom", fontsize=12, color=TEXT)
    ax.annotate(
        "2 event rows\nper fraud flow",
        xy=(1, fraud_flows),
        xytext=(0.47, fraud_event_rows * 0.78),
        ha="center",
        color=TEXT,
        fontsize=11,
        arrowprops={"arrowstyle": "<->", "color": MUTED, "linewidth": 1.2},
    )
    ax.set_ylabel("Count")
    ax.set_title("The fraud numerator changes by grain", fontsize=13, weight="bold")
    ax.set_ylim(0, fraud_event_rows * 1.18)
    style_ax(ax)

    savefig(fig, "05_fraud_balance_and_grain_translation.png")


def main() -> None:
    plot_event_vs_flow_grain()
    plot_sequence_type_grammar()
    plot_approx_flow_count_caution()
    plot_amount_surface_mirroring()
    plot_fraud_balance_by_event_side()


if __name__ == "__main__":
    main()
