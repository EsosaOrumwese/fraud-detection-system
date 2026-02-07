from __future__ import annotations

import glob
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/2B")
OUT_PLOTS = Path("docs/reports/reports/eda/segment_2B/plots")


def _set_theme() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#D2D6DC",
            "grid.color": "#E5E7EB",
            "grid.linestyle": "-",
            "grid.alpha": 1.0,
            "axes.titlesize": 16,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "savefig.dpi": 170,
            "figure.dpi": 170,
        }
    )


def _glob_many(pattern: str) -> list[str]:
    matches = sorted(glob.glob(pattern, recursive=True))
    if not matches:
        raise FileNotFoundError(f"No matches for pattern: {pattern}")
    return matches


def _load() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pd.DataFrame]:
    s1 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s1_site_weights" / "**" / "*.parquet")))
    s3 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s3_day_effects" / "**" / "*.parquet")))
    s4 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s4_group_weights" / "**" / "*.parquet")))

    roster_files = _glob_many(str(RUN_ROOT / "s5_arrival_roster" / "**" / "*.jsonl"))
    rows: list[dict[str, object]] = []
    with open(roster_files[0], "r", encoding="utf-8") as handle:
        for line in handle:
            rows.append(json.loads(line))
    s5 = pd.DataFrame(rows)
    return s1, s3, s4, s5


def _safe_norm_entropy(weights: np.ndarray) -> float:
    n = len(weights)
    if n <= 1:
        return 0.0
    eps = 1e-12
    w = np.clip(weights, eps, 1.0)
    h = -np.sum(w * np.log(w))
    return float(h / np.log(n))


def _plot_s1(s1: pl.DataFrame) -> None:
    s1_m = (
        s1.group_by("merchant_id")
        .agg(
            [
                pl.len().alias("site_count"),
                pl.max("p_weight").alias("top1"),
                pl.col("p_weight").sort(descending=True).head(2).alias("top2"),
                (pl.col("p_weight") ** 2).sum().alias("hhi"),
                pl.col("p_weight").alias("weights"),
            ]
        )
        .to_pandas()
    )
    s1_m["top2_val"] = s1_m["top2"].apply(lambda x: x[1] if len(x) > 1 else x[0])
    s1_m["entropy_norm"] = s1_m["weights"].apply(_safe_norm_entropy)
    s1_m["hhi_resid"] = s1_m["hhi"] - (1.0 / s1_m["site_count"])
    s1_m["top1_resid"] = s1_m["top1"] - (1.0 / s1_m["site_count"])
    s1_m["entropy_resid"] = s1_m["entropy_norm"] - 1.0
    s1_m["gini"] = 1.0 - s1_m["entropy_norm"]  # equivalent for perfectly uniform detection here

    # s1_site_count_distribution
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.histplot(s1_m["site_count"], bins=30, color="#3B82F6", ax=ax)
    ax.set_xscale("log")
    ax.set_xlabel("sites per merchant (log scale)")
    ax.set_ylabel("merchant count")
    ax.set_title("S1 Sites per Merchant Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_site_count_distribution.png")
    plt.close(fig)

    # s1_top1_vs_top2
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    sns.scatterplot(data=s1_m, x="top1", y="top2_val", s=25, alpha=0.55, color="#2563EB", ax=ax)
    lo = float(min(s1_m["top1"].min(), s1_m["top2_val"].min()))
    hi = float(max(s1_m["top1"].max(), s1_m["top2_val"].max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", color="#9CA3AF")
    ax.set_xlabel("top-1 weight")
    ax.set_ylabel("top-2 weight")
    ax.set_title("S1 Top-1 vs Top-2 Site Weight")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_top1_vs_top2.png")
    plt.close(fig)

    # s1_hhi_distribution
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(s1_m["hhi"], bins=35, color="#8B5CF6", ax=ax)
    ax.set_xscale("log")
    ax.set_xlabel("HHI")
    ax.set_ylabel("merchant count")
    ax.set_title("S1 HHI Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_hhi_distribution.png")
    plt.close(fig)

    # s1_lorenz_sample (reworked with gini panel)
    rng = np.random.default_rng(42)
    sample = s1_m.sample(n=min(6, len(s1_m)), random_state=42)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.6))
    for _, row in sample.iterrows():
        w = np.sort(np.asarray(row["weights"], dtype=float))
        cw = np.cumsum(w)
        cw = np.insert(cw, 0, 0.0)
        x = np.linspace(0, 1, len(cw))
        ax1.plot(x, cw, alpha=0.8)
    ax1.plot([0, 1], [0, 1], linestyle="--", color="#9CA3AF")
    ax1.set_title("Sample Lorenz Curves")
    ax1.set_xlabel("cumulative share of sites")
    ax1.set_ylabel("cumulative share of weight")
    sns.histplot(s1_m["gini"], bins=20, color="#22C55E", ax=ax2)
    ax2.set_title("Inequality Gap (1 - norm entropy)")
    ax2.set_xlabel("inequality gap")
    ax2.set_ylabel("merchant count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_lorenz_sample.png")
    plt.close(fig)

    # s1_hhi_vs_site_count (residual diagnostic)
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.scatterplot(data=s1_m, x="site_count", y="hhi_resid", s=20, alpha=0.6, color="#2563EB", ax=ax)
    ax.axhline(0.0, linestyle="--", color="#9CA3AF")
    ax.set_xscale("log")
    ax.set_xlabel("site_count (log scale)")
    ax.set_ylabel("HHI - 1/N")
    ax.set_title("S1 Concentration Residual by Site Count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_hhi_vs_site_count.png")
    plt.close(fig)

    # s1_top1_vs_site_count (residual diagnostic)
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.scatterplot(data=s1_m, x="site_count", y="top1_resid", s=20, alpha=0.6, color="#0EA5E9", ax=ax)
    ax.axhline(0.0, linestyle="--", color="#9CA3AF")
    ax.set_xscale("log")
    ax.set_xlabel("site_count (log scale)")
    ax.set_ylabel("top1 - 1/N")
    ax.set_title("S1 Top-1 Residual by Site Count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_top1_vs_site_count.png")
    plt.close(fig)

    # s1_weight_source_breakdown (provenance compact)
    ws = s1.group_by("weight_source").agg(pl.len().alias("n")).sort("n", descending=True).to_pandas()
    qb = s1.group_by("quantised_bits").agg(pl.len().alias("n")).sort("quantised_bits").to_pandas()
    fa = s1.group_by("floor_applied").agg(pl.len().alias("n")).sort("floor_applied").to_pandas()
    fig, axs = plt.subplots(1, 3, figsize=(12.2, 4.2))
    sns.barplot(data=ws, x="weight_source", y="n", color="#6366F1", ax=axs[0])
    axs[0].set_title("weight_source")
    axs[0].tick_params(axis="x", rotation=35)
    sns.barplot(data=qb, x="quantised_bits", y="n", color="#8B5CF6", ax=axs[1])
    axs[1].set_title("quantised_bits")
    sns.barplot(data=fa, x="floor_applied", y="n", color="#A855F7", ax=axs[2])
    axs[2].set_title("floor_applied")
    fig.suptitle("S1 Policy/Provenance Breakdown")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_weight_source_breakdown.png")
    plt.close(fig)

    # s1_entropy_vs_site_count (residual diagnostic)
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.scatterplot(data=s1_m, x="site_count", y="entropy_resid", s=20, alpha=0.6, color="#7C3AED", ax=ax)
    ax.axhline(0.0, linestyle="--", color="#9CA3AF")
    ax.set_xscale("log")
    ax.set_xlabel("site_count (log scale)")
    ax.set_ylabel("norm entropy - 1")
    ax.set_title("S1 Entropy Residual by Site Count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_entropy_vs_site_count.png")
    plt.close(fig)

    # new: s1_uniformity_residuals
    s1_pd = s1.select(["merchant_id", "p_weight"]).join(
        s1.group_by("merchant_id").agg(pl.len().alias("site_count")), on="merchant_id", how="left"
    ).to_pandas()
    s1_pd["resid"] = s1_pd["p_weight"] - (1.0 / s1_pd["site_count"])
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.histplot(s1_pd["resid"], bins=40, color="#0EA5E9", ax=ax)
    ax.axvline(0.0, linestyle="--", color="#9CA3AF")
    ax.set_xlabel("p_weight - (1/site_count)")
    ax.set_ylabel("site rows")
    ax.set_title("S1 Uniformity Residuals")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_uniformity_residuals.png")
    plt.close(fig)


def _plot_s3_s4(s1: pl.DataFrame, s3: pl.DataFrame, s4: pl.DataFrame) -> None:
    s4_md = (
        s4.group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.col("p_group").sum().alias("sum_p"),
                pl.max("p_group").alias("max_p"),
                pl.n_unique("tz_group_id").alias("n_groups"),
                (-(pl.col("p_group") * pl.col("p_group").log()).sum()).alias("entropy"),
            ]
        )
        .to_pandas()
    )
    s1_counts = s1.group_by("merchant_id").agg(pl.len().alias("site_count")).to_pandas()
    s4_md = s4_md.merge(s1_counts, on="merchant_id", how="left")

    # s4_max_p_group_distribution
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(s4_md["max_p"], bins=40, color="#2563EB", ax=ax)
    ax.set_xlabel("max p_group per merchant-day")
    ax.set_ylabel("merchant-days")
    ax.set_title("S4 Max p_group Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_max_p_group_distribution.png")
    plt.close(fig)

    # s4_tz_groups_per_day
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(s4_md["n_groups"], bins=range(1, int(s4_md["n_groups"].max()) + 2), color="#7C3AED", ax=ax)
    ax.set_xlabel("distinct tz_groups per merchant-day")
    ax.set_ylabel("merchant-days")
    ax.set_title("S4 TZ-Group Count per Merchant-Day")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_tz_groups_per_day.png")
    plt.close(fig)

    # s4_entropy_distribution
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(s4_md["entropy"], bins=40, color="#8B5CF6", ax=ax)
    ax.set_xlabel("entropy")
    ax.set_ylabel("merchant-days")
    ax.set_title("S4 Entropy of Group Weights")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_entropy_distribution.png")
    plt.close(fig)

    # s4_groups_vs_site_count (bucketed for readability on discrete y)
    s4_md["site_bucket"] = pd.cut(
        s4_md["site_count"],
        bins=[1, 5, 10, 25, 50, 100, 250, 10_000],
        labels=["2-5", "6-10", "11-25", "26-50", "51-100", "101-250", "251+"],
        include_lowest=True,
        right=True,
    )
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    sns.boxplot(
        data=s4_md,
        x="site_bucket",
        y="n_groups",
        color="#0EA5E9",
        showfliers=False,
        ax=ax,
    )
    ax.set_xlabel("sites per merchant bucket")
    ax.set_ylabel("distinct tz_groups per merchant-day")
    ax.set_title("S4 TZ-Group Count vs Site Count Bucket")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_groups_vs_site_count.png")
    plt.close(fig)

    # s4_sum_p_group_distribution (centered around 1)
    dev = s4_md["sum_p"] - 1.0
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.histplot(dev, bins=50, color="#14B8A6", ax=ax)
    ax.axvline(0.0, linestyle="--", color="#9CA3AF")
    ax.set_xlabel("sum(p_group) - 1")
    ax.set_ylabel("merchant-days")
    ax.set_title("S4 Normalization Residual Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_sum_p_group_distribution.png")
    plt.close(fig)

    # new: s4_dominance_by_group_count
    s4_md["group_bucket"] = pd.cut(
        s4_md["n_groups"], bins=[0, 1, 2, 4, 8, 100], labels=["1", "2", "3-4", "5-8", "9+"]
    )
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    sns.boxplot(data=s4_md, x="group_bucket", y="max_p", color="#22C55E", showfliers=False, ax=ax)
    ax.set_xlabel("tz-group count bucket")
    ax.set_ylabel("max p_group")
    ax.set_title("S4 Dominance by TZ-Group Breadth")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_dominance_by_group_count.png")
    plt.close(fig)

    # S3
    s3_pd = s3.select(["merchant_id", "utc_day", "tz_group_id", "gamma", "sigma_gamma"]).to_pandas()

    # s3_sigma_gamma_distribution (unique-value diagnostic)
    sigma_vals = np.sort(s3_pd["sigma_gamma"].unique())
    sigma_counts = s3_pd.groupby("sigma_gamma").size().reset_index(name="n")
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    sns.barplot(data=sigma_counts, x="sigma_gamma", y="n", color="#0EA5E9", ax=ax)
    ax.set_title(f"S3 Sigma-Gamma Unique Values (unique={len(sigma_vals)})")
    ax.set_xlabel("sigma_gamma")
    ax.set_ylabel("rows")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_sigma_gamma_distribution.png")
    plt.close(fig)

    # s3_gamma_distribution
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(s3_pd["gamma"], bins=50, kde=True, color="#8B5CF6", ax=ax)
    ax.set_xlabel("gamma")
    ax.set_ylabel("rows")
    ax.set_title("S3 Gamma Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_gamma_distribution.png")
    plt.close(fig)

    # s3_gamma_by_tzgroup (top 10 by volume, horizontal for label readability)
    top_tz = s3_pd["tz_group_id"].value_counts().head(10).index.tolist()
    g10 = s3_pd[s3_pd["tz_group_id"].isin(top_tz)].copy()
    g10["tz_group_id"] = g10["tz_group_id"].astype(str)
    order = (
        g10.groupby("tz_group_id", as_index=False)["gamma"]
        .median()
        .sort_values("gamma", ascending=False)["tz_group_id"]
        .tolist()
    )
    counts = g10["tz_group_id"].value_counts().to_dict()
    fig, ax = plt.subplots(figsize=(10.4, 5.8))
    sns.boxplot(
        data=g10,
        y="tz_group_id",
        x="gamma",
        order=order,
        showfliers=False,
        color="#3B82F6",
        ax=ax,
    )
    # Robust limits: avoid hidden outliers stretching the axis and flattening the boxes.
    x_lo = float(g10["gamma"].quantile(0.005))
    x_hi = float(g10["gamma"].quantile(0.995))
    x_span = max(x_hi - x_lo, 0.25)
    x_pad = x_span * 0.28
    ax.set_xlim(x_lo - (x_span * 0.05), x_hi + x_pad)
    for i, label in enumerate(order):
        ax.text(
            x_hi + (x_pad * 0.06),
            i,
            f" n={counts.get(label, 0):,}",
            va="center",
            ha="left",
            fontsize=8,
            color="#4B5563",
            clip_on=True,
        )
    ax.set_xlabel("gamma")
    ax.set_ylabel("tz_group_id (top 10 by rows)")
    ax.set_title("S3 Gamma by TZ Group (Top 10)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_gamma_by_tzgroup.png")
    plt.close(fig)

    # s3_gamma_time_series (cleaner sample + rolling mean)
    sample_merchants = (
        s3_pd["merchant_id"].drop_duplicates().sample(n=min(6, s3_pd["merchant_id"].nunique()), random_state=42)
    )
    ts = s3_pd[s3_pd["merchant_id"].isin(sample_merchants)].copy()
    ts["utc_day"] = pd.to_datetime(ts["utc_day"])
    ts = ts.groupby(["merchant_id", "utc_day"], as_index=False)["gamma"].mean()
    ts["gamma_roll7"] = ts.sort_values("utc_day").groupby("merchant_id")["gamma"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    sns.lineplot(data=ts, x="utc_day", y="gamma_roll7", hue="merchant_id", linewidth=1.8, ax=ax, legend=False)
    ax.set_xlabel("utc_day")
    ax.set_ylabel("gamma (7-day rolling mean)")
    ax.set_title("S3 Gamma Over Time (Sample Merchants, Smoothed)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_gamma_time_series.png")
    plt.close(fig)

    # s3_mean_gamma_per_merchant
    mean_g = s3_pd.groupby("merchant_id", as_index=False)["gamma"].mean()
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(mean_g["gamma"], bins=40, color="#C26E3A", ax=ax)
    ax.set_xlabel("mean gamma per merchant")
    ax.set_ylabel("merchant count")
    ax.set_title("S3 Mean Gamma per Merchant")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_mean_gamma_per_merchant.png")
    plt.close(fig)

    # s3_days_covered_per_merchant
    days_cov = s3_pd.groupby("merchant_id")["utc_day"].nunique().reset_index(name="days_covered")
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.histplot(days_cov["days_covered"], bins=20, color="#7C3AED", ax=ax)
    ax.axvline(days_cov["days_covered"].median(), linestyle="--", color="#9CA3AF")
    ax.text(
        0.98,
        0.93,
        f"median={int(days_cov['days_covered'].median())}, min={days_cov['days_covered'].min()}, max={days_cov['days_covered'].max()}",
        transform=ax.transAxes,
        ha="right",
        fontsize=9,
    )
    ax.set_xlabel("distinct days covered per merchant")
    ax.set_ylabel("merchant count")
    ax.set_title("S3 Days Covered per Merchant")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_days_covered_per_merchant.png")
    plt.close(fig)

    # new: s3_panel_rectangularity
    m_sample = days_cov["merchant_id"].sample(n=min(120, len(days_cov)), random_state=42).tolist()
    panel = (
        s3_pd[s3_pd["merchant_id"].isin(m_sample)]
        .groupby(["merchant_id", "utc_day"], as_index=False)
        .size()
        .pivot(index="merchant_id", columns="utc_day", values="size")
        .fillna(0.0)
    )
    panel_vals = (panel.values > 0).astype(float)
    fig, ax = plt.subplots(figsize=(10.4, 5.2))
    sns.heatmap(panel_vals, cmap="Blues", cbar_kws={"label": "coverage flag"}, ax=ax)
    ax.set_xlabel("utc_day (sampled panel columns)")
    ax.set_ylabel("merchant sample")
    ax.set_title("S3 Panel Rectangularity (Merchant-Day Coverage Sample)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_panel_rectangularity.png")
    plt.close(fig)


def _plot_s5(s5: pd.DataFrame) -> None:
    s5["utc_day"] = pd.to_datetime(s5["utc_day"])
    per_day = s5.groupby("utc_day").size().reset_index(name="arrivals")
    per_merchant = s5.groupby("merchant_id").size().reset_index(name="arrivals")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.8, 4.8))
    sns.barplot(data=per_day, x="utc_day", y="arrivals", color="#0EA5E9", ax=ax1)
    ax1.set_title("Arrivals per Day")
    ax1.set_xlabel("utc_day")
    ax1.tick_params(axis="x", rotation=30)
    sns.histplot(per_merchant["arrivals"], bins=10, color="#22C55E", ax=ax2)
    ax2.set_title("Arrivals per Merchant")
    ax2.set_xlabel("arrival count")
    fig.suptitle("S5 Workload Profile")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s5_workload_profile.png")
    plt.close(fig)


def main() -> None:
    _set_theme()
    OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    s1, s3, s4, s5 = _load()
    _plot_s1(s1)
    _plot_s3_s4(s1, s3, s4)
    _plot_s5(s5)
    print("2B plot refresh complete.")


if __name__ == "__main__":
    main()
