from pathlib import Path

import matplotlib

# Use a non-interactive backend so plots can be rendered from the terminal.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
import seaborn as sns


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
WORKBENCH = ROOT / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench"
EXPORTS = WORKBENCH / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)

MERCHANT_PATH = ROOT / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"


def style_dual_axis(ax1, ax2) -> None:
    # Keep the bar axis visually primary.
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    ax1.grid(axis="x", visible=False)

    # Keep the cumulative axis readable without adding a competing vertical spine.
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(False)
    ax2.tick_params(axis="y", colors="#555555", length=0, pad=6)
    ax2.yaxis.label.set_color("#555555")


def country_pareto(df: pd.DataFrame) -> None:
    country = df["home_country_iso"].value_counts().rename_axis("home_country_iso").reset_index(name="merchant_count")
    country["merchant_share_pct"] = country["merchant_count"] / len(df) * 100
    country["cumulative_share_pct"] = country["merchant_share_pct"].cumsum()
    country_top = country.head(30).copy()

    fig, ax1 = plt.subplots(figsize=(14, 6))
    sns.barplot(data=country_top, x="home_country_iso", y="merchant_count", color="#4C78A8", ax=ax1)
    ax1.set_title("Merchant Universe Concentration by Home Country (Top 30)")
    ax1.set_xlabel("Home Country ISO")
    ax1.set_ylabel("Merchant Count")
    ax1.tick_params(axis="x", rotation=60)

    ax2 = ax1.twinx()
    ax2.plot(
        range(len(country_top)),
        country_top["cumulative_share_pct"],
        color="#E45756",
        marker="o",
        markersize=3.5,
        linewidth=2,
        zorder=3,
    )
    ax2.set_ylabel("Cumulative Share (%)")
    ax2.set_ylim(0, 100)
    ax2.yaxis.set_major_formatter(PercentFormatter(100))

    style_dual_axis(ax1, ax2)
    fig.tight_layout()
    fig.savefig(EXPORTS / "transaction_schema_merchant_ids_country_pareto.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def mcc_pareto(df: pd.DataFrame) -> None:
    mcc = df["mcc"].value_counts().rename_axis("mcc").reset_index(name="merchant_count")
    mcc["merchant_share_pct"] = mcc["merchant_count"] / len(df) * 100
    mcc["cumulative_share_pct"] = mcc["merchant_share_pct"].cumsum()
    mcc_top = mcc.head(30).copy()
    mcc_top["mcc"] = mcc_top["mcc"].astype(str)

    fig, ax1 = plt.subplots(figsize=(14, 6))
    sns.barplot(data=mcc_top, x="mcc", y="merchant_count", color="#72B7B2", ax=ax1)
    ax1.set_title("Merchant Universe Concentration by MCC (Top 30)")
    ax1.set_xlabel("MCC")
    ax1.set_ylabel("Merchant Count")
    ax1.tick_params(axis="x", rotation=60)

    ax2 = ax1.twinx()
    ax2.plot(
        range(len(mcc_top)),
        mcc_top["cumulative_share_pct"],
        color="#F58518",
        marker="o",
        markersize=3.5,
        linewidth=2,
        zorder=3,
    )
    ax2.set_ylabel("Cumulative Share (%)")
    ax2.set_ylim(0, 100)
    ax2.yaxis.set_major_formatter(PercentFormatter(100))

    style_dual_axis(ax1, ax2)
    fig.tight_layout()
    fig.savefig(EXPORTS / "transaction_schema_merchant_ids_mcc_pareto.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def channel_split(df: pd.DataFrame) -> None:
    channel = df["channel"].value_counts(dropna=False).rename_axis("channel").reset_index(name="merchant_count")
    channel["merchant_share_pct"] = channel["merchant_count"] / len(df) * 100

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=channel,
        x="channel",
        y="merchant_count",
        hue="channel",
        dodge=False,
        palette=["#54A24B", "#EECA3B"],
        ax=ax,
    )
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()

    ax.set_title("Merchant Universe Channel Split")
    ax.set_xlabel("Channel")
    ax.set_ylabel("Merchant Count")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    ax.grid(axis="x", visible=False)

    for i, row in channel.reset_index(drop=True).iterrows():
        ax.text(
            i,
            row["merchant_count"] + 80,
            f"{row['merchant_count']:,}\n({row['merchant_share_pct']:.2f}%)",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    fig.tight_layout()
    fig.savefig(EXPORTS / "transaction_schema_merchant_ids_channel_split.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    sns.set_theme(style="whitegrid")
    merchant_ids_df = pd.read_parquet(MERCHANT_PATH)
    country_pareto(merchant_ids_df)
    mcc_pareto(merchant_ids_df)
    channel_split(merchant_ids_df)

    for path in sorted(EXPORTS.glob("transaction_schema_merchant_ids_*.png")):
        print(path)


if __name__ == "__main__":
    main()
