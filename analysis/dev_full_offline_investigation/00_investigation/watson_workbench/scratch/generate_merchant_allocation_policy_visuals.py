from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import polars as pl
import seaborn as sns


ROOT = Path(__file__).resolve().parents[5]
WORKBENCH = Path(__file__).resolve().parents[1]
EXPORTS = WORKBENCH / "exports" / "merchant_allocation_policy"

MERCHANT_PATH = (
    ROOT
    / "reference"
    / "layer1"
    / "transaction_schema_merchant_ids"
    / "2026-01-03"
    / "transaction_schema_merchant_ids.parquet"
)
MANIFEST_PATH = (
    ROOT
    / "reference"
    / "layer1"
    / "transaction_schema_merchant_ids"
    / "2026-01-03"
    / "transaction_schema_merchant_ids.manifest.json"
)
BUILDER_PATH = ROOT / "scripts" / "build_transaction_schema_merchant_ids.py"


WORLD_COLORS = {
    "GDP-only": "#4C78A8",
    "GDP + region": "#54A24B",
    "Corrected final": "#F58518",
    "Implemented final": "#E45756",
}

EFFECT_COLORS = {
    "Regional uplift": "#54A24B",
    "Heavy-tail uplift": "#F58518",
    "Implementation artifact": "#E45756",
}


def load_builder_module():
    spec = importlib.util.spec_from_file_location("merchant_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def corrected_allocate(weights: dict[str, float], allocation_policy: dict) -> dict[str, int]:
    total_merchants = int(allocation_policy["total_merchants"])
    min_per_iso = int(allocation_policy["min_per_iso"])
    max_per_iso = int(allocation_policy["max_per_iso"])

    iso_list = sorted(weights.keys())
    counts = {iso: min_per_iso for iso in iso_list}
    remaining = total_merchants - min_per_iso * len(iso_list)
    capacity = {iso: max(0, max_per_iso - counts[iso]) for iso in iso_list}
    usable_weights = {iso: weights[iso] if capacity[iso] > 0 else 0.0 for iso in iso_list}
    total_weight = sum(usable_weights.values())
    raw_extra = {iso: (usable_weights[iso] / total_weight) * remaining for iso in iso_list}
    extra = {iso: min(capacity[iso], math.floor(raw_extra[iso])) for iso in iso_list}
    leftover = remaining - sum(extra.values())

    if leftover > 0:
        fractional = {
            iso: raw_extra[iso] - math.floor(raw_extra[iso]) if capacity[iso] > extra[iso] else -1.0
            for iso in iso_list
        }
        eligible = [iso for iso in iso_list if capacity[iso] > extra[iso]]
        eligible.sort(key=lambda iso: (-fractional[iso], iso))
        for iso in eligible[:leftover]:
            extra[iso] += 1

    for iso in iso_list:
        counts[iso] += extra[iso]
    return counts


def style_axes(ax, grid_x: bool = False, grid_y: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(colors="#333333", labelsize=9)
    if grid_y:
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.85)
    if grid_x:
        ax.grid(axis="x", color="#E6E6E6", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)


def build_worlds() -> pl.DataFrame:
    builder = load_builder_module()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy = manifest["allocation_policy"]

    merchant_df = pl.read_parquet(MERCHANT_PATH)
    observed_df = (
        merchant_df.group_by("home_country_iso")
        .len()
        .rename({"home_country_iso": "iso", "len": "observed_count"})
    )

    iso_set = builder.load_iso_set("2024-12-31")
    gdp_df = builder.load_gdp_table("2025-04-15")
    bucket_map = builder.load_bucket_map("2024")
    valid_iso = sorted(set(bucket_map.keys()) & iso_set)
    gdp_df = gdp_df.filter(pl.col("iso").is_in(valid_iso))

    gdp_only_policy = json.loads(json.dumps(policy))
    gdp_only_policy["regional_adjustments"] = {}
    gdp_only_policy["weighting"]["heavy_tail"] = 0.0

    gdp_region_policy = json.loads(json.dumps(policy))
    gdp_region_policy["weighting"]["heavy_tail"] = 0.0

    weights_gdp_only = {
        iso: weight
        for iso, weight in builder.compute_weights(gdp_df, gdp_only_policy).items()
        if iso in valid_iso
    }
    weights_gdp_region = {
        iso: weight
        for iso, weight in builder.compute_weights(gdp_df, gdp_region_policy).items()
        if iso in valid_iso
    }
    weights_final = {
        iso: weight
        for iso, weight in builder.compute_weights(gdp_df, policy).items()
        if iso in valid_iso
    }

    gdp_only_counts = corrected_allocate(weights_gdp_only, gdp_only_policy)
    gdp_region_counts = corrected_allocate(weights_gdp_region, gdp_region_policy)
    corrected_final_counts = corrected_allocate(weights_final, policy)
    implemented_final_counts = builder.allocate_merchants(weights_final, policy)

    return (
        observed_df.join(
            pl.DataFrame({"iso": list(gdp_only_counts), "gdp_only_count": list(gdp_only_counts.values())}),
            on="iso",
            how="inner",
        )
        .join(
            pl.DataFrame(
                {"iso": list(gdp_region_counts), "gdp_region_count": list(gdp_region_counts.values())}
            ),
            on="iso",
            how="inner",
        )
        .join(
            pl.DataFrame(
                {"iso": list(corrected_final_counts), "corrected_final_count": list(corrected_final_counts.values())}
            ),
            on="iso",
            how="inner",
        )
        .join(
            pl.DataFrame(
                {"iso": list(implemented_final_counts), "implemented_final_count": list(implemented_final_counts.values())}
            ),
            on="iso",
            how="inner",
        )
        .with_columns(
            [
                pl.col("observed_count").cast(pl.Int64),
                pl.col("gdp_only_count").cast(pl.Int64),
                pl.col("gdp_region_count").cast(pl.Int64),
                pl.col("corrected_final_count").cast(pl.Int64),
                pl.col("implemented_final_count").cast(pl.Int64),
                (pl.col("gdp_region_count") - pl.col("gdp_only_count")).alias("regional_uplift"),
                (pl.col("corrected_final_count") - pl.col("gdp_region_count")).alias("heavytail_uplift"),
                (pl.col("implemented_final_count") - pl.col("corrected_final_count")).alias("implementation_artifact"),
            ]
        )
    )


def plot_ranked_worlds(df: pl.DataFrame) -> None:
    worlds = [
        ("GDP-only", "gdp_only_count"),
        ("GDP + region", "gdp_region_count"),
        ("Corrected final", "corrected_final_count"),
        ("Implemented final", "implemented_final_count"),
    ]
    fig, ax = plt.subplots(figsize=(12.5, 7))
    for label, col in worlds:
        ranked = df.select(col).sort(col, descending=True).to_series().to_list()
        ranks = list(range(1, len(ranked) + 1))
        ax.plot(ranks, ranked, linewidth=2.2, color=WORLD_COLORS[label], label=label)

    ax.set_title("Merchant-Country Count Surface Across the Four Worlds", fontsize=14, pad=14)
    ax.set_xlabel("Country rank by merchant count", fontsize=10)
    ax.set_ylabel("Merchant count", fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=10))
    style_axes(ax, grid_y=True)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_ranked_worlds.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_ranked_worlds_top_end(df: pl.DataFrame, top_n: int = 30) -> None:
    worlds = [
        ("GDP-only", "gdp_only_count"),
        ("GDP + region", "gdp_region_count"),
        ("Corrected final", "corrected_final_count"),
        ("Implemented final", "implemented_final_count"),
    ]
    fig, ax = plt.subplots(figsize=(12.5, 7))
    for label, col in worlds:
        ranked = df.select(col).sort(col, descending=True).to_series().to_list()[:top_n]
        ranks = list(range(1, len(ranked) + 1))
        ax.plot(ranks, ranked, marker="o", markersize=3.8, linewidth=2.2, color=WORLD_COLORS[label], label=label)

    ax.set_title(f"Top-{top_n} Country Ranks Across the Four Worlds", fontsize=14, pad=14)
    ax.set_xlabel("Country rank by merchant count", fontsize=10)
    ax.set_ylabel("Merchant count", fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    style_axes(ax, grid_y=True)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_ranked_worlds_top30.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_world_differences_by_rank(df: pl.DataFrame, top_n: int = 30) -> None:
    ranked = (
        df.sort("observed_count", descending=True)
        .with_row_index("rank", offset=1)
        .head(top_n)
        .with_columns(
            [
                (pl.col("gdp_region_count") - pl.col("gdp_only_count")).alias("regional_delta"),
                (pl.col("corrected_final_count") - pl.col("gdp_region_count")).alias("heavytail_delta"),
                (pl.col("implemented_final_count") - pl.col("corrected_final_count")).alias("artifact_delta"),
            ]
        )
        .to_pandas()
    )

    fig, ax = plt.subplots(figsize=(13, 7))
    ax.bar(ranked["rank"], ranked["regional_delta"], color=EFFECT_COLORS["Regional uplift"], label="GDP + region minus GDP-only")
    ax.bar(
        ranked["rank"],
        ranked["heavytail_delta"],
        bottom=ranked["regional_delta"],
        color=EFFECT_COLORS["Heavy-tail uplift"],
        label="Corrected final minus GDP + region",
    )
    ax.bar(
        ranked["rank"],
        ranked["artifact_delta"],
        bottom=ranked["regional_delta"] + ranked["heavytail_delta"],
        color=EFFECT_COLORS["Implementation artifact"],
        label="Implemented final minus corrected final",
    )

    gh_rows = ranked.loc[ranked["iso"] == "GH"]
    if not gh_rows.empty:
        gh_rank = int(gh_rows.iloc[0]["rank"])
        ax.axvline(gh_rank, color="#444444", linestyle="--", linewidth=1.1, alpha=0.85)
        ax.text(gh_rank + 0.4, ax.get_ylim()[1] * 0.92, "GH rank", fontsize=9, color="#333333")

    ax.set_title(f"Top-{top_n} Rank Differences Between the Four Worlds", fontsize=14, pad=14)
    ax.set_xlabel("Observed country rank", fontsize=10)
    ax.set_ylabel("Incremental change in merchant count", fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    style_axes(ax, grid_y=True)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_rank_differences_top30.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_implemented_vs_corrected_artifact(df: pl.DataFrame) -> None:
    artifact_df = (
        df.sort("observed_count", descending=True)
        .select(["iso", "implemented_final_count", "corrected_final_count"])
        .with_columns((pl.col("implemented_final_count") - pl.col("corrected_final_count")).alias("artifact_delta"))
        .filter(pl.col("artifact_delta") != 0)
        .sort("artifact_delta", descending=True)
        .to_pandas()
    )
    display_df = artifact_df.head(12).copy()

    fig, ax = plt.subplots(figsize=(11.5, 7))
    colors = ["#E45756" if value > 0 else "#4C78A8" for value in display_df["artifact_delta"]]
    ax.barh(display_df["iso"], display_df["artifact_delta"], color=colors)
    ax.axvline(0, color="#444444", linewidth=1.0)
    ax.set_title("Implemented vs Corrected Final: Where the Builder Alters Country Counts", fontsize=14, pad=14)
    ax.set_xlabel("Implemented final minus corrected final", fontsize=10)
    ax.set_ylabel("Country ISO", fontsize=10)
    style_axes(ax, grid_x=True, grid_y=False)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_implementation_artifact.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    artifact_ex_gh = artifact_df.loc[artifact_df["iso"] != "GH"].head(12).copy()
    fig, ax = plt.subplots(figsize=(11.5, 7))
    colors = ["#E45756" if value > 0 else "#4C78A8" for value in artifact_ex_gh["artifact_delta"]]
    ax.barh(artifact_ex_gh["iso"], artifact_ex_gh["artifact_delta"], color=colors)
    ax.axvline(0, color="#444444", linewidth=1.0)
    ax.set_title("Implemented vs Corrected Final: Builder Drift Outside GH", fontsize=14, pad=14)
    ax.set_xlabel("Implemented final minus corrected final", fontsize=10)
    ax.set_ylabel("Country ISO", fontsize=10)
    style_axes(ax, grid_x=True, grid_y=False)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_implementation_artifact_ex_gh.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_top15_worlds(df: pl.DataFrame) -> None:
    top15 = df.sort("observed_count", descending=True).head(15).to_pandas()
    long_df = top15.melt(
        id_vars=["iso"],
        value_vars=["gdp_only_count", "gdp_region_count", "corrected_final_count", "implemented_final_count"],
        var_name="world",
        value_name="merchant_count",
    )
    label_map = {
        "gdp_only_count": "GDP-only",
        "gdp_region_count": "GDP + region",
        "corrected_final_count": "Corrected final",
        "implemented_final_count": "Implemented final",
    }
    long_df["world"] = long_df["world"].map(label_map)

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.barplot(
        data=long_df,
        x="iso",
        y="merchant_count",
        hue="world",
        palette=WORLD_COLORS,
        ax=ax,
    )
    ax.set_title("Top 15 Merchant Countries Under the Four Worlds", fontsize=14, pad=14)
    ax.set_xlabel("Country ISO", fontsize=10)
    ax.set_ylabel("Merchant count", fontsize=10)
    ax.tick_params(axis="x", rotation=45)
    style_axes(ax, grid_y=True)
    ax.legend(title="World", frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_top15_worlds.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_policy_step_effects(df: pl.DataFrame) -> None:
    top12 = (
        df.filter(pl.col("iso") != "GH")
        .sort("observed_count", descending=True)
        .select(["iso", "regional_uplift", "heavytail_uplift", "implementation_artifact"])
        .head(12)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(12.5, 7))
    left = [0] * len(top12)
    for col, label in [
        ("regional_uplift", "Regional uplift"),
        ("heavytail_uplift", "Heavy-tail uplift"),
        ("implementation_artifact", "Implementation artifact"),
    ]:
        ax.barh(top12["iso"], top12[col], left=left, color=EFFECT_COLORS[label], label=label)
        left = [l + v for l, v in zip(left, top12[col])]

    ax.set_title("How the Policy Steps Move the Top Merchant Countries (Excluding GH)", fontsize=14, pad=14)
    ax.set_xlabel("Change in merchant count relative to GDP-only world", fontsize=10)
    ax.set_ylabel("Country ISO", fontsize=10)
    style_axes(ax, grid_x=True, grid_y=False)
    ax.legend(frameon=False, loc="lower right")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_step_effects.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_gh_spotlight(df: pl.DataFrame) -> None:
    gh = df.filter(pl.col("iso") == "GH").to_dicts()[0]
    stages = ["GDP-only", "GDP + region", "Corrected final", "Implemented final"]
    values = [
        gh["gdp_only_count"],
        gh["gdp_region_count"],
        gh["corrected_final_count"],
        gh["implemented_final_count"],
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(stages, values, marker="o", linewidth=2.4, color="#E45756")
    for x, y in zip(stages, values):
        ax.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_title("GH Across the Four Worlds", fontsize=14, pad=14)
    ax.set_xlabel("World", fontsize=10)
    ax.set_ylabel("Merchant count", fontsize=10)
    style_axes(ax, grid_y=True)
    fig.tight_layout()
    fig.savefig(EXPORTS / "merchant_allocation_policy_gh_spotlight.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    df = build_worlds()
    plot_ranked_worlds(df)
    plot_ranked_worlds_top_end(df)
    plot_world_differences_by_rank(df)
    plot_implemented_vs_corrected_artifact(df)
    plot_top15_worlds(df)
    plot_policy_step_effects(df)
    plot_gh_spotlight(df)


if __name__ == "__main__":
    main()
