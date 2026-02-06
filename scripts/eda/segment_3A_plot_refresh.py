from __future__ import annotations

import glob
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/3A")
OUT_PLOTS = Path("docs/reports/reports/eda/segment_3A/plots")
OUT_PLOTS_DIAG = Path("docs/reports/reports/eda/segment_3A/plots_diag")


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
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No matches for pattern: {pattern}")
    return matches


def _load_frames() -> dict[str, pl.DataFrame]:
    s1 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s1_escalation_queue" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    s2 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s2_country_zone_priors" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    s3 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s3_zone_shares" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    s4 = pl.read_parquet(_glob_many(str(RUN_ROOT / "s4_zone_counts" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    za = pl.read_parquet(_glob_many(str(RUN_ROOT / "zone_alloc" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    return {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "za": za}


def _safe_div(num: pl.Expr, den: pl.Expr) -> pl.Expr:
    return pl.when(den > 0).then(num / den).otherwise(0.0)


def _precompute(frames: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    s1, s2, s3, s4, za = frames["s1"], frames["s2"], frames["s3"], frames["s4"], frames["za"]

    s2_country = (
        s2.group_by("country_iso")
        .agg(
            [
                pl.max("share_effective").alias("top1_share"),
                (pl.col("share_effective") ** 2).sum().alias("hhi"),
                pl.n_unique("tzid").alias("tz_count"),
            ]
        )
        .sort("country_iso")
    )

    s2_raw = s2.with_columns(
        (pl.col("alpha_raw") / pl.col("alpha_raw").sum().over("country_iso")).alias("share_raw")
    )

    s3_mc = (
        s3.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.max("share_drawn").alias("top1_s3"),
                pl.n_unique("tzid").alias("tz_count_s3"),
                ((-pl.col("share_drawn") * pl.col("share_drawn").log()).sum()).alias("entropy_raw"),
            ]
        )
        .with_columns(
            _safe_div(pl.col("entropy_raw"), pl.col("tz_count_s3").cast(pl.Float64).log()).alias("entropy_norm")
        )
    )

    s3_ct = s3.group_by(["legal_country_iso", "tzid"]).agg(
        [
            pl.mean("share_drawn").alias("mean_share_drawn"),
            pl.std("share_drawn").alias("std_share_drawn"),
        ]
    )

    s4_mc = (
        s4.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.sum((pl.col("zone_site_count") > 0).cast(pl.Int64)).alias("nonzero_zones"),
                pl.max("zone_site_count").alias("max_zone_count"),
                pl.sum("zone_site_count").alias("sum_zone_count"),
            ]
        )
        .with_columns(_safe_div(pl.col("max_zone_count").cast(pl.Float64), pl.col("sum_zone_count")).alias("top1_s4"))
    )

    za_mc = (
        za.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.max("zone_site_count").alias("max_zone_count"),
                pl.sum("zone_site_count").alias("sum_zone_count"),
            ]
        )
        .with_columns(_safe_div(pl.col("max_zone_count").cast(pl.Float64), pl.col("sum_zone_count")).alias("top1_za"))
    )

    s1_key = s1.select(["merchant_id", "legal_country_iso", "site_count", "zone_count_country", "is_escalated"])

    thresholds = [0.50, 0.20, 0.10, 0.05, 0.01]
    eff_rows: list[tuple[str, int]] = []
    s3_pd = s3.select(["merchant_id", "legal_country_iso", "tzid", "share_drawn"]).to_pandas()
    grp = s3_pd.groupby(["merchant_id", "legal_country_iso"])["share_drawn"]
    for t in thresholds:
        counts = grp.apply(lambda x: int((x >= t).sum()))
        eff_rows.extend([(f">={t:.2f}", int(v)) for v in counts.values])
    s3_effective = pd.DataFrame(eff_rows, columns=["threshold", "effective_zone_count"])

    return {
        "s1_key": s1_key,
        "s2_country": s2_country,
        "s2_raw": s2_raw,
        "s3_mc": s3_mc,
        "s3_ct": s3_ct,
        "s4_mc": s4_mc,
        "za_mc": za_mc,
        "s3_effective": pl.from_pandas(s3_effective),
    }


def _plot_main(metrics: dict[str, pl.DataFrame]) -> None:
    s1 = metrics["s1_key"]
    s2_country = metrics["s2_country"]
    s2_raw = metrics["s2_raw"]
    s3_mc = metrics["s3_mc"]
    s3_ct = metrics["s3_ct"]
    s4_mc = metrics["s4_mc"]
    za_mc = metrics["za_mc"]

    # 14.1
    zc = (
        s1.group_by("zone_count_country")
        .agg([pl.len().alias("n"), pl.col("is_escalated").cast(pl.Float64).mean().alias("escalation_rate")])
        .sort("zone_count_country")
        .to_pandas()
    )
    fig, ax1 = plt.subplots(figsize=(8.6, 5.4))
    ax1.plot(zc["zone_count_country"], zc["escalation_rate"], marker="o", color="#1F77B4", linewidth=1.8)
    ax1.set_xlabel("zone_count_country")
    ax1.set_ylabel("escalation rate")
    ax1.set_ylim(0, 1.02)
    ax2 = ax1.twinx()
    ax2.bar(zc["zone_count_country"], zc["n"], alpha=0.22, color="#7F7F7F")
    ax2.set_ylabel("sample size")
    ax1.set_title("S1 Escalation Rate by zone_count_country")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_escalation_rate_by_zone_count.png")
    plt.close(fig)

    # 14.2
    bins = [0, 2, 4, 8, 16, 32, 64, 128, 10_000]
    labels = ["1-2", "3-4", "5-8", "9-16", "17-32", "33-64", "65-128", "129+"]
    sb = (
        s1.with_columns(
            pl.col("site_count")
            .cut(breaks=bins[1:-1], labels=labels, left_closed=True)
            .alias("site_bucket")
        )
        .group_by("site_bucket")
        .agg([pl.len().alias("n"), pl.col("is_escalated").cast(pl.Float64).mean().alias("escalation_rate")])
        .sort("site_bucket")
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    sns.barplot(data=sb, x="site_bucket", y="escalation_rate", color="#2A9D8F", ax=ax)
    for i, row in sb.iterrows():
        ax.text(i, row["escalation_rate"] + 0.01, f"n={int(row['n'])}", ha="center", fontsize=8, rotation=90)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("site_count bucket")
    ax.set_ylabel("escalation rate")
    ax.set_title("S1 Escalation Rate by site_count Bucket")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s1_escalation_rate_by_site_bucket.png")
    plt.close(fig)

    # 14.3
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    sns.histplot(s2_country["top1_share"].to_numpy(), bins=25, color="#3B82F6", ax=ax)
    ax.set_xlabel("country top-1 share (S2)")
    ax.set_ylabel("country count")
    ax.set_title("S2 Top-1 Share Distribution by Country")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s2_top1_share_hist.png")
    plt.close(fig)

    # 14.4
    hhi = np.sort(s2_country["hhi"].to_numpy())
    y = np.arange(1, len(hhi) + 1) / len(hhi)
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(hhi, y, color="#EF4444", linewidth=2.0)
    ax.set_xlabel("HHI by country (S2)")
    ax.set_ylabel("ECDF")
    ax.set_title("S2 Country HHI ECDF")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s2_hhi_ecdf.png")
    plt.close(fig)

    # 14.5
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    sns.scatterplot(data=s2_country.to_pandas(), x="tz_count", y="top1_share", s=55, color="#8B5CF6", ax=ax)
    ax.set_xlabel("tz_count per country")
    ax.set_ylabel("top-1 share")
    ax.set_title("S2 tz_count vs Top-1 Share")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s2_tzcount_vs_top1.png")
    plt.close(fig)

    # 14.6
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    sns.histplot(s3_mc["top1_s3"].to_numpy(), bins=30, color="#2563EB", ax=ax)
    ax.set_xlabel("merchant-country top-1 share (S3)")
    ax.set_ylabel("merchant-country count")
    ax.set_title("S3 Top-1 Share Distribution by Merchant-Country")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_top1_share_hist.png")
    plt.close(fig)

    # 14.7
    eff = metrics["s3_effective"].to_pandas()
    order = [">=0.50", ">=0.20", ">=0.10", ">=0.05", ">=0.01"]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.boxplot(data=eff, x="threshold", y="effective_zone_count", order=order, color="#60A5FA", ax=ax, showfliers=False)
    ax.set_xlabel("share threshold")
    ax.set_ylabel("effective zone count")
    ax.set_title("S3 Effective Zone Counts by Share Threshold")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_effective_zone_count_thresholds.png")
    plt.close(fig)

    # 14.8
    s2_join = s2_raw.select(["country_iso", "tzid", "share_raw"]).rename({"country_iso": "legal_country_iso"})
    mean_join = s3_ct.join(s2_join, on=["legal_country_iso", "tzid"], how="inner").to_pandas()
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    hb = ax.hexbin(mean_join["share_raw"], mean_join["mean_share_drawn"], gridsize=45, bins="log", mincnt=1, cmap="viridis")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("bin count (log10)")
    lo = float(min(mean_join["share_raw"].min(), mean_join["mean_share_drawn"].min()))
    hi = float(max(mean_join["share_raw"].max(), mean_join["mean_share_drawn"].max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", color="#9CA3AF")
    ax.set_xlabel("S2 share_raw")
    ax.set_ylabel("S3 mean share_drawn")
    ax.set_title("S3 Mean Share vs S2 Prior Share")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s3_mean_vs_prior_share_hexbin.png")
    plt.close(fig)

    # 14.9
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    sns.histplot(s4_mc["nonzero_zones"].to_numpy(), bins=30, color="#0891B2", ax=ax)
    ax.set_xlabel("nonzero zones per merchant-country (S4)")
    ax.set_ylabel("merchant-country count")
    ax.set_title("S4 Nonzero Zone Count Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_nonzero_zones_hist.png")
    plt.close(fig)

    # 14.10
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    sns.histplot(s4_mc["top1_s4"].to_numpy(), bins=30, color="#0EA5E9", ax=ax)
    ax.set_xlabel("top-1 share from counts (S4)")
    ax.set_ylabel("merchant-country count")
    ax.set_title("S4 Top-1 Share from Integerised Counts")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "s4_top1_share_hist.png")
    plt.close(fig)

    # 14.11
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    sns.histplot(za_mc["top1_za"].to_numpy(), bins=30, color="#2563EB", ax=ax)
    ax.set_xlabel("top-1 share (zone_alloc)")
    ax.set_ylabel("merchant-country count")
    ax.set_title("zone_alloc Top-1 Share Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "zone_alloc_top1_share_hist.png")
    plt.close(fig)


def _plot_diag(metrics: dict[str, pl.DataFrame]) -> None:
    s1 = metrics["s1_key"]
    s2_country = metrics["s2_country"]
    s2_raw = metrics["s2_raw"]
    s3_mc = metrics["s3_mc"]
    s3_ct = metrics["s3_ct"]
    s4_mc = metrics["s4_mc"]

    # 15.1
    d1 = s2_country.sort("top1_share").head(30).to_pandas()
    fig, ax = plt.subplots(figsize=(10.0, 6.2))
    sns.barplot(data=d1, y="country_iso", x="top1_share", color="#4C78A8", ax=ax)
    ax.set_xlabel("top-1 share")
    ax.set_ylabel("country")
    ax.set_title("S2 Lowest Top-1 Shares (Bottom 30 Countries)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d1_s2_top1_share_bottom30.png")
    plt.close(fig)

    # 15.2
    d2 = s2_country.to_pandas()
    fig, ax = plt.subplots(figsize=(10.0, 6.0))
    sns.scatterplot(data=d2, x="tz_count", y="top1_share", s=55, color="#8B5CF6", ax=ax)
    for _, row in d2.iterrows():
        ax.text(row["tz_count"] + 0.04, row["top1_share"] + 0.003, row["country_iso"], fontsize=8, alpha=0.85)
    ax.set_xlabel("tz_count")
    ax.set_ylabel("top-1 share")
    ax.set_title("S2 tz_count vs Top-1 Share (Labeled Countries)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d2_s2_tzcount_vs_top1_labeled.png")
    plt.close(fig)

    # 15.3
    ratio = (s2_raw["alpha_effective"] / s2_raw["alpha_raw"]).to_numpy()
    ratio = ratio[np.isfinite(ratio) & (ratio > 0)]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    sns.histplot(ratio, bins=35, color="#EF4444", ax=ax)
    ax.set_xscale("log")
    ax.set_xlabel("alpha_effective / alpha_raw (log scale)")
    ax.set_ylabel("row count")
    ax.set_title("S2 Alpha Ratio Distribution")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d3_alpha_ratio_hist_logx.png")
    plt.close(fig)

    # 15.4
    d4 = s2_raw.select(["share_raw", "share_effective"]).to_pandas()
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    hb = ax.hexbin(d4["share_raw"], d4["share_effective"], gridsize=45, bins="log", mincnt=1, cmap="mako")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("bin count (log10)")
    lo = float(min(d4["share_raw"].min(), d4["share_effective"].min()))
    hi = float(max(d4["share_raw"].max(), d4["share_effective"].max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", color="#9CA3AF")
    ax.set_xlabel("share_raw")
    ax.set_ylabel("share_effective")
    ax.set_title("S2 share_raw vs share_effective")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d4_share_raw_vs_effective.png")
    plt.close(fig)

    # 15.5
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    sns.histplot(s3_mc["entropy_norm"].to_numpy(), bins=35, color="#0EA5E9", ax=ax)
    ax.set_xlabel("normalized entropy (S3 merchant-country)")
    ax.set_ylabel("merchant-country count")
    ax.set_title("S3 Entropy Distribution by Merchant-Country")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d5_s3_entropy_hist.png")
    plt.close(fig)

    # 15.6
    std_vals = s3_ct["std_share_drawn"].fill_null(0.0).to_numpy()
    std_vals = std_vals[std_vals > 0]
    log_std = np.log10(std_vals) if len(std_vals) else np.array([0.0])
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    sns.histplot(log_std, bins=35, color="#9333EA", ax=ax)
    ax.set_xlabel("log10 std(share_drawn) by country-tz")
    ax.set_ylabel("country-tz count")
    ax.set_title("S3 Std-Dev of Shares by Country-TZ")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d6_s3_std_share_log10_hist.png")
    plt.close(fig)

    # 15.7
    d7 = s3_mc.join(s4_mc.select(["merchant_id", "legal_country_iso", "top1_s4"]), on=["merchant_id", "legal_country_iso"], how="inner").to_pandas()
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    hb = ax.hexbin(d7["top1_s3"], d7["top1_s4"], gridsize=45, bins="log", mincnt=1, cmap="viridis")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("bin count (log10)")
    lo = float(min(d7["top1_s3"].min(), d7["top1_s4"].min()))
    hi = float(max(d7["top1_s3"].max(), d7["top1_s4"].max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", color="#9CA3AF")
    ax.set_xlabel("S3 top-1 share")
    ax.set_ylabel("S4 top-1 share")
    ax.set_title("S3 vs S4 Top-1 Share (Rounding Effect)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d7_s3_vs_s4_top1_hexbin.png")
    plt.close(fig)

    # 15.8
    mz = (
        s4_mc.with_columns((pl.col("nonzero_zones") >= 2).alias("is_multi_zone"))
        .join(s1.select(["merchant_id", "legal_country_iso", "is_escalated"]), on=["merchant_id", "legal_country_iso"], how="inner")
        .group_by("is_escalated")
        .agg([pl.len().alias("n"), pl.col("is_multi_zone").cast(pl.Float64).mean().alias("multi_zone_rate")])
        .sort("is_escalated")
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    sns.barplot(data=mz, x="is_escalated", y="multi_zone_rate", color="#22C55E", ax=ax)
    for i, row in mz.iterrows():
        ax.text(i, row["multi_zone_rate"] + 0.005, f"n={int(row['n'])}", ha="center", fontsize=9)
    lo = max(0.0, float(mz["multi_zone_rate"].min()) - 0.05)
    hi = min(1.0, float(mz["multi_zone_rate"].max()) + 0.05)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("is_escalated")
    ax.set_ylabel("multi-zone rate (nonzero_zones >= 2)")
    ax.set_title("S4 Multi-Zone Rate by Escalation Flag (Zoomed)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS_DIAG / "d8_multi_zone_rate_by_escalated_zoom.png")
    plt.close(fig)


def main() -> None:
    _set_theme()
    OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    OUT_PLOTS_DIAG.mkdir(parents=True, exist_ok=True)

    frames = _load_frames()
    metrics = _precompute(frames)
    _plot_main(metrics)
    _plot_diag(metrics)
    print("3A plot refresh complete.")


if __name__ == "__main__":
    main()
