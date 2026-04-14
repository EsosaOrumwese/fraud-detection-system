from pathlib import Path

import matplotlib

# Use a non-interactive backend for terminal-side rendering.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import pandas as pd
import seaborn as sns


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
WORKBENCH = ROOT / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench"
EXPORTS = WORKBENCH / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    merchant_df = pd.read_parquet(
        ROOT / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
    )
    iso_df = pd.read_parquet(ROOT / "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet")
    gdp_df = pd.read_parquet(ROOT / "reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet")
    bucket_df = pd.read_parquet(ROOT / "reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet")

    merchant_country_df = (
        merchant_df.groupby("home_country_iso")
        .size()
        .rename("merchant_count")
        .reset_index()
        .merge(iso_df[["country_iso", "name"]], left_on="home_country_iso", right_on="country_iso", how="left")
        .merge(
            gdp_df[["country_iso", "gdp_pc_usd_2015"]],
            left_on="home_country_iso",
            right_on="country_iso",
            how="left",
            suffixes=("", "_gdp"),
        )
        .merge(
            bucket_df[["country_iso", "bucket_id"]],
            left_on="home_country_iso",
            right_on="country_iso",
            how="left",
            suffixes=("", "_bucket"),
        )
        .drop(columns=["country_iso_gdp", "country_iso_bucket"], errors="ignore")
    )

    return merchant_country_df.sort_values("gdp_pc_usd_2015").reset_index(drop=True)


GDP_BUCKET_COLORS = {
    1: "#E45756",
    2: "#F58518",
    3: "#72B7B2",
    4: "#54A24B",
    5: "#4C78A8",
}


def style_axes(ax, *, grid_x: bool = False, grid_y: bool = True) -> None:
    # Keep the main plotting frame explicit so the chart does not feel visually detached.
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(axis="both", colors="#333333")
    if grid_y:
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    else:
        ax.grid(axis="y", visible=False)
    if grid_x:
        ax.grid(axis="x", color="#E6E6E6", linewidth=0.8)
    else:
        ax.grid(axis="x", visible=False)


def plot_ranked_gdp_surface(df: pd.DataFrame) -> None:
    ranked_df = df.sort_values("gdp_pc_usd_2015").reset_index(drop=True).copy()
    ranked_df["gdp_rank"] = ranked_df.index + 1

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.scatterplot(
        data=ranked_df,
        x="gdp_rank",
        y="gdp_pc_usd_2015",
        hue="bucket_id",
        palette=GDP_BUCKET_COLORS,
        s=46,
        edgecolor="none",
        ax=ax,
    )

    # Mark where the frozen bucket transitions happen along the continuous ranked GDP surface.
    bucket_boundaries = (
        ranked_df.groupby("bucket_id")["gdp_rank"]
        .agg(["min", "max"])
        .reset_index()
        .sort_values("bucket_id")
    )
    for _, row in bucket_boundaries.iloc[:-1].iterrows():
        ax.axvline(row["max"] + 0.5, color="#888888", linestyle="--", linewidth=1, alpha=0.7)

    ax.set_title("Continuous GDP Surface Ordered by Rank and Coloured by Frozen Bucket")
    ax.set_xlabel("Country Rank by GDP per Capita")
    ax.set_ylabel("GDP per Capita (constant 2015 USD, log scale)")
    ax.set_yscale("log")
    style_axes(ax, grid_x=False, grid_y=True)
    ax.legend(title="Frozen bucket", frameon=False, ncol=5, loc="upper left")

    fig.tight_layout()
    fig.savefig(EXPORTS / "gdp_bucket_map_ranked_surface.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_bucket_distribution(df: pd.DataFrame) -> None:
    plot_df = df.copy()
    plot_df["bucket_id"] = plot_df["bucket_id"].astype(int).astype(str)

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(
        data=plot_df,
        x="bucket_id",
        y="gdp_pc_usd_2015",
        color="#D3D3D3",
        width=0.55,
        fliersize=0,
        ax=ax,
    )
    sns.stripplot(
        data=plot_df,
        x="bucket_id",
        y="gdp_pc_usd_2015",
        hue="bucket_id",
        palette={str(k): v for k, v in GDP_BUCKET_COLORS.items()},
        jitter=0.18,
        size=4.5,
        alpha=0.75,
        dodge=False,
        ax=ax,
    )

    ax.set_title("GDP Distribution Within Each Frozen Bucket")
    ax.set_xlabel("Bucket ID")
    ax.set_ylabel("GDP per Capita (constant 2015 USD, log scale)")
    ax.set_yscale("log")
    style_axes(ax, grid_x=False, grid_y=True)

    legend_handles = [Patch(facecolor="#D3D3D3", edgecolor="#888888", label="Box = within-bucket spread")]
    legend_handles.extend(
        Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=8, label=f"Bucket {bucket_id}")
        for bucket_id, color in GDP_BUCKET_COLORS.items()
    )
    ax.legend(handles=legend_handles, title="Encoding", frameon=False, loc="upper left", ncol=3)

    fig.tight_layout()
    fig.savefig(EXPORTS / "gdp_bucket_map_bucket_distributions.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_bucket_ranges(df: pd.DataFrame) -> None:
    range_df = (
        df.groupby("bucket_id")
        .agg(
            min_gdp=("gdp_pc_usd_2015", "min"),
            median_gdp=("gdp_pc_usd_2015", "median"),
            max_gdp=("gdp_pc_usd_2015", "max"),
            country_count=("home_country_iso", "nunique"),
        )
        .reset_index()
        .sort_values("bucket_id")
    )

    fig, ax = plt.subplots(figsize=(12, 5))

    for _, row in range_df.iterrows():
        y = int(row["bucket_id"])
        color = GDP_BUCKET_COLORS[y]
        ax.hlines(y=y, xmin=row["min_gdp"], xmax=row["max_gdp"], color=color, linewidth=6, alpha=0.85)
        ax.scatter(row["median_gdp"], y, color="black", s=32, zorder=3)
        ax.text(row["max_gdp"] * 1.03, y, f"{int(row['country_count'])} countries", va="center", fontsize=9)

    ax.set_title("GDP Range Compression by Frozen Bucket")
    ax.set_xlabel("GDP per Capita (constant 2015 USD, log scale)")
    ax.set_ylabel("Bucket ID")
    ax.set_xscale("log")
    ax.set_yticks(range_df["bucket_id"].tolist())
    ax.set_ylim(0.5, range_df["bucket_id"].max() + 0.5)
    style_axes(ax, grid_x=True, grid_y=False)

    legend_handles = [
        Line2D([0], [0], color="#666666", linewidth=6, label="Range = min to max GDP in bucket"),
        Line2D([0], [0], marker="o", color="black", linewidth=0, markersize=7, label="Dot = median GDP"),
    ]
    ax.legend(handles=legend_handles, title="Encoding", frameon=False, loc="lower right")

    fig.tight_layout()
    fig.savefig(EXPORTS / "gdp_bucket_map_bucket_ranges.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    sns.set_theme(style="whitegrid")
    df = load_data()
    plot_ranked_gdp_surface(df)
    plot_bucket_distribution(df)
    plot_bucket_ranges(df)

    for path in sorted(
        [
            EXPORTS / "gdp_bucket_map_ranked_surface.png",
            EXPORTS / "gdp_bucket_map_bucket_distributions.png",
            EXPORTS / "gdp_bucket_map_bucket_ranges.png",
        ]
    ):
        print(path)


if __name__ == "__main__":
    main()
