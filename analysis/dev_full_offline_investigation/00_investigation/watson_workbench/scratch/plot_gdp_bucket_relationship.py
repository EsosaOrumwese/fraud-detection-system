from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[5]
EXPORTS = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "gdp_bucket_map"
)

SUMMARY_PATH = EXPORTS / "gdp_bucket_map_merchant_country_summary.csv"
BUCKET_DIST_PATH = EXPORTS / "gdp_bucket_map_bucket_distribution.csv"

SUMMARY_DF = pd.read_csv(SUMMARY_PATH)
BUCKET_DIST_DF = pd.read_csv(BUCKET_DIST_PATH)

sns.set_theme(style="whitegrid")

BUCKET_COLORS = {
    1: "#E45756",
    2: "#F58518",
    3: "#72B7B2",
    4: "#4C78A8",
    5: "#6F4E7C",
}


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_relationship_scatter() -> None:
    df = SUMMARY_DF.copy()
    fig, ax = plt.subplots(figsize=(11.5, 7))

    colors = [BUCKET_COLORS[int(v)] for v in df["bucket_id"]]
    ax.scatter(
        df["gdp_pc_usd_2015"],
        df["merchant_count"],
        s=36,
        c=colors,
        alpha=0.82,
        edgecolors="white",
        linewidths=0.5,
    )

    ax.set_xscale("log")
    ax.set_title("Merchant Count vs GDP per Capita by Country")
    ax.set_xlabel("GDP per Capita, constant 2015 USD (log scale)")
    ax.set_ylabel("Merchant Count")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    top_labels = set(df.nlargest(10, "merchant_count")["home_country_iso"].tolist() + ["GH"])
    for _, row in df[df["home_country_iso"].isin(top_labels)].iterrows():
        ax.text(
            row["gdp_pc_usd_2015"] * 1.03,
            row["merchant_count"] + 7,
            row["home_country_iso"],
            fontsize=9,
            ha="left",
            va="bottom",
        )

    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=f"Bucket {bucket}",
            markerfacecolor=color,
            markeredgecolor="white",
            markersize=8,
        )
        for bucket, color in BUCKET_COLORS.items()
    ]
    legend = ax.legend(handles=handles, title="GDP Bucket", loc="upper left", frameon=True)
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#BBBBBB")

    rho = df[["merchant_count", "gdp_pc_usd_2015"]].corr(method="spearman").iloc[0, 1]
    ax.text(
        0.985,
        0.03,
        f"Spearman ρ = {rho:.4f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.3"},
    )

    _save(fig, EXPORTS / "gdp_bucket_map_relationship_scatter.png")


def draw_top20_bucket_membership() -> None:
    df = SUMMARY_DF.nlargest(20, "merchant_count").copy().sort_values("merchant_count", ascending=True)
    fig, ax = plt.subplots(figsize=(10.5, 8))

    bar_colors = [BUCKET_COLORS[int(v)] for v in df["bucket_id"]]
    ax.barh(df["home_country_iso"], df["merchant_count"], color=bar_colors, edgecolor="white")
    ax.set_title("Top 20 Merchant Countries, Colored by GDP Bucket")
    ax.set_xlabel("Merchant Count")
    ax.set_ylabel("Home Country ISO")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for _, row in df.iterrows():
        ax.text(
            row["merchant_count"] + 8,
            row["home_country_iso"],
            f"B{int(row['bucket_id'])}",
            va="center",
            ha="left",
            fontsize=9,
        )

    handles = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            label=f"Bucket {bucket}",
            markerfacecolor=color,
            markersize=10,
        )
        for bucket, color in BUCKET_COLORS.items()
    ]
    legend = ax.legend(handles=handles, title="GDP Bucket", loc="lower right", frameon=True)
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#BBBBBB")

    _save(fig, EXPORTS / "gdp_bucket_map_top20_bucket_membership.png")


def draw_bucket_compression() -> None:
    df = BUCKET_DIST_DF.copy()
    x = np.arange(len(df))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10, 6.2))
    left = ax.bar(
        x - width / 2,
        df["country_share_pct"],
        width,
        color="#B8BDC6",
        label="Country Share",
        edgecolor="white",
    )
    right = ax.bar(
        x + width / 2,
        df["merchant_share_pct"],
        width,
        color="#4C78A8",
        label="Merchant Share",
        edgecolor="white",
    )

    ax.set_title("GDP Buckets: Country Share vs Merchant Share")
    ax.set_xlabel("GDP Bucket")
    ax.set_ylabel("Share of Total")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Bucket {int(v)}" for v in df["bucket_id"]])
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bars in (left, right):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.7,
                f"{height:.2f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    legend = ax.legend(loc="upper right", frameon=True)
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_edgecolor("#BBBBBB")

    _save(fig, EXPORTS / "gdp_bucket_map_bucket_compression.png")


def draw_bucket1_exception() -> None:
    df = SUMMARY_DF[SUMMARY_DF["bucket_id"] == 1].copy().nlargest(12, "merchant_count").sort_values("merchant_count", ascending=True)
    fig, ax = plt.subplots(figsize=(10.5, 6.8))

    colors = ["#E45756" if iso == "GH" else "#B8BDC6" for iso in df["home_country_iso"]]
    ax.barh(df["home_country_iso"], df["merchant_count"], color=colors, edgecolor="white")
    ax.set_title("Bucket 1 Peer View: `GH` vs Other Low-GDP Countries")
    ax.set_xlabel("Merchant Count")
    ax.set_ylabel("Home Country ISO")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for _, row in df.iterrows():
        ax.text(
            row["merchant_count"] + 3,
            row["home_country_iso"],
            f"{int(row['merchant_count'])} | GDP {row['gdp_pc_usd_2015']:,.0f}",
            va="center",
            ha="left",
            fontsize=9,
        )

    note = (
        "GH is the only top-country outlier in Bucket 1.\n"
        "The next peer group is an order of magnitude lower."
    )
    ax.text(
        0.985,
        0.04,
        note,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.3"},
    )

    _save(fig, EXPORTS / "gdp_bucket_map_bucket1_exception.png")


if __name__ == "__main__":
    draw_relationship_scatter()
    draw_top20_bucket_membership()
    draw_bucket_compression()
    draw_bucket1_exception()
