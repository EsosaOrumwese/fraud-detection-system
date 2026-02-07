from __future__ import annotations

import math
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/2A")
OUT_PLOTS = Path("docs/reports/reports/eda/segment_2A/plots")


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
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "savefig.dpi": 170,
            "figure.dpi": 170,
        }
    )


def _load() -> pd.DataFrame:
    p_site_tz = RUN_ROOT / "site_timezones/seed=42/manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8/part-00000.parquet"
    p_lookup = RUN_ROOT / "s1_tz_lookup/seed=42/manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8/part-00000.parquet"

    site_tz = pl.read_parquet(str(p_site_tz))
    lookup = pl.read_parquet(str(p_lookup))
    df = (
        site_tz.join(
            lookup.select(
                [
                    "merchant_id",
                    "legal_country_iso",
                    "site_order",
                    "lat_deg",
                    "lon_deg",
                ]
            ),
            on=["merchant_id", "legal_country_iso", "site_order"],
            how="left",
        )
        .select(
            [
                "merchant_id",
                "legal_country_iso",
                "site_order",
                "tzid",
                "lat_deg",
                "lon_deg",
            ]
        )
        .to_pandas()
    )
    return df


def _country_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("legal_country_iso", as_index=False).agg(
        site_count=("site_order", "count"),
        lat_min=("lat_deg", "min"),
        lat_max=("lat_deg", "max"),
        lon_min=("lon_deg", "min"),
        lon_max=("lon_deg", "max"),
        tzid_count=("tzid", "nunique"),
    )
    g["lat_span"] = g["lat_max"] - g["lat_min"]
    g["lon_span"] = g["lon_max"] - g["lon_min"]
    g["mid_lat"] = (g["lat_max"] + g["lat_min"]) / 2.0
    km_per_deg_lat = 111.32
    g["km_per_deg_lon"] = km_per_deg_lat * np.cos(np.deg2rad(g["mid_lat"]).clip(-89.0, 89.0))
    # BBox area approximation (km^2); tiny epsilon to keep log plots stable.
    g["bbox_area_km2"] = (
        (g["lat_span"].abs() * km_per_deg_lat) * (g["lon_span"].abs() * g["km_per_deg_lon"].abs())
    ).clip(lower=1e-4)
    g["log10_bbox_area"] = np.log10(g["bbox_area_km2"])
    return g


def _country_tz_counts(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["legal_country_iso", "tzid"], as_index=False)
        .size()
        .rename(columns={"size": "site_count"})
    )


def _plot_1_bbox_area_vs_count(country: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    sns.scatterplot(data=country, x="site_count", y="bbox_area_km2", s=60, alpha=0.85, color="#4C72B0", ax=ax)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Site count (log scale)")
    ax.set_ylabel("BBox area approx (km^2, log scale)")
    ax.set_title("Country Spatial Spread vs Site Count")

    # Annotate largest-area outliers for interpretability.
    for _, r in country.nlargest(5, "bbox_area_km2").iterrows():
        ax.annotate(
            r["legal_country_iso"],
            (r["site_count"], r["bbox_area_km2"]),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=8,
            color="#374151",
        )
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "1_bbox_area_vs_count.png")
    plt.close(fig)


def _plot_2_tzid_diversity_vs_count(country: pd.DataFrame) -> None:
    rng = np.random.default_rng(42)
    c = country.copy()
    c["tzid_jitter"] = c["tzid_count"] + rng.uniform(-0.09, 0.09, size=len(c))

    fig, ax = plt.subplots(figsize=(8.8, 6.0))
    sc = ax.scatter(
        c["site_count"],
        c["tzid_jitter"],
        c=c["log10_bbox_area"],
        cmap="viridis",
        s=70,
        alpha=0.9,
        edgecolors="none",
    )
    ax.set_xscale("log")
    y_min = int(max(1, c["tzid_count"].min()))
    y_max = int(c["tzid_count"].max())
    ax.set_yticks(np.arange(y_min, y_max + 1))
    ax.set_ylim(y_min - 0.15, y_max + 0.2)
    ax.set_xlabel("Site count (log scale)")
    ax.set_ylabel("Distinct tzids per country")
    ax.set_title("TZID Diversity vs Site Count (Jittered, Integer Y)")
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("log10(bbox area km^2)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "2_tzid_diversity_vs_count.png")
    plt.close(fig)


def _plot_3_country_small_multiples(df: pd.DataFrame, country: pd.DataFrame) -> None:
    top_countries = country.sort_values("site_count", ascending=False).head(12)["legal_country_iso"].tolist()
    sub = df[df["legal_country_iso"].isin(top_countries)].copy()
    order = top_countries
    fig, axes = plt.subplots(3, 4, figsize=(14.0, 10.0))
    axes = axes.flatten()

    for i, iso in enumerate(order):
        ax = axes[i]
        p = sub[sub["legal_country_iso"] == iso]
        ax.scatter(p["lon_deg"], p["lat_deg"], s=10, alpha=0.7, color="#4C72B0")
        lat_span = p["lat_deg"].max() - p["lat_deg"].min()
        lon_span = p["lon_deg"].max() - p["lon_deg"].min()
        ax.set_title(f"{iso} n={len(p)}\nΔlat={lat_span:.3f} Δlon={lon_span:.3f}", fontsize=10)
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        ax.ticklabel_format(style="plain", useOffset=False, axis="both")

    for j in range(len(order), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Top Countries: Local Site Spread (lat/lon)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "3_country_small_multiples.png")
    plt.close(fig)


def _plot_4_country_tzid_share_matrix(country_tz: pd.DataFrame, country: pd.DataFrame) -> None:
    top_countries = country.sort_values("site_count", ascending=False).head(20)["legal_country_iso"].tolist()
    top_tz = country_tz.groupby("tzid", as_index=False)["site_count"].sum().sort_values("site_count", ascending=False).head(14)["tzid"].tolist()

    ct = country_tz[country_tz["legal_country_iso"].isin(top_countries)].copy()
    ct["tz_bucket"] = np.where(ct["tzid"].isin(top_tz), ct["tzid"], "OTHER")
    pvt = (
        ct.groupby(["legal_country_iso", "tz_bucket"], as_index=False)["site_count"]
        .sum()
        .pivot(index="legal_country_iso", columns="tz_bucket", values="site_count")
        .fillna(0.0)
    )
    row_sum = pvt.sum(axis=1).replace(0, 1.0)
    pvt_share = pvt.div(row_sum, axis=0)

    cols = [c for c in top_tz if c in pvt_share.columns] + (["OTHER"] if "OTHER" in pvt_share.columns else [])
    pvt_share = pvt_share.loc[top_countries, cols]

    fig, ax = plt.subplots(figsize=(16.0, 7.5))
    sns.heatmap(
        pvt_share,
        cmap="mako",
        vmin=0.0,
        vmax=1.0,
        cbar_kws={"label": "share within country"},
        ax=ax,
    )
    ax.set_xlabel("TZID")
    ax.set_ylabel("Country")
    ax.set_title("Country x TZID Share Matrix (Top Countries / Top TZIDs + OTHER)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "4_country_tzid_heatmap.png")
    plt.close(fig)


def _plot_5_top1_share(country_tz: pd.DataFrame, country: pd.DataFrame) -> None:
    agg = country_tz.groupby("legal_country_iso", as_index=False)["site_count"].sum().rename(columns={"site_count": "country_sites"})
    top1 = (
        country_tz.sort_values(["legal_country_iso", "site_count"], ascending=[True, False])
        .groupby("legal_country_iso", as_index=False)
        .first()[["legal_country_iso", "site_count"]]
        .rename(columns={"site_count": "top1_sites"})
    )
    m = top1.merge(agg, on="legal_country_iso", how="left")
    m["top1_share"] = m["top1_sites"] / m["country_sites"]
    m = m.merge(country[["legal_country_iso", "site_count"]], on="legal_country_iso", how="left")
    m = m.sort_values("site_count", ascending=False).head(30).sort_values("top1_share", ascending=True)

    fig, ax = plt.subplots(figsize=(9.0, 8.8))
    sns.barplot(data=m, y="legal_country_iso", x="top1_share", color="#E17C3A", ax=ax)
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("Top-1 tzid share within country")
    ax.set_ylabel("Country (top-30 by site count)")
    ax.set_title("Country Top-1 TZID Share")
    ax.axvline(m["top1_share"].median(), linestyle="--", color="#9CA3AF", linewidth=1.2)
    ax.text(0.985, 0.05, f"median={m['top1_share'].median():.2f}", transform=ax.transAxes, ha="right", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "5_country_top1_tz_share.png")
    plt.close(fig)


def _plot_6_entropy_vs_count(country_tz: pd.DataFrame, country: pd.DataFrame) -> None:
    ct = country_tz.copy()
    totals = ct.groupby("legal_country_iso", as_index=False)["site_count"].sum().rename(columns={"site_count": "n"})
    ct = ct.merge(totals, on="legal_country_iso", how="left")
    ct["p"] = ct["site_count"] / ct["n"].replace(0, 1.0)
    ent = (
        ct.groupby("legal_country_iso")
        .agg(
            entropy=("p", lambda s: float(-(s * np.log(np.clip(s, 1e-12, None))).sum())),
            k=("tzid", "nunique"),
        )
        .reset_index()
    )
    ent["entropy_norm"] = np.where(ent["k"] > 1, ent["entropy"] / np.log(ent["k"]), 0.0)
    m = ent.merge(country[["legal_country_iso", "site_count", "log10_bbox_area"]], on="legal_country_iso", how="left")

    fig, ax = plt.subplots(figsize=(8.8, 6.0))
    sc = ax.scatter(
        m["site_count"],
        m["entropy_norm"],
        c=m["log10_bbox_area"],
        cmap="viridis",
        s=65,
        alpha=0.9,
        edgecolors="none",
    )
    ax.set_xscale("log")
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Site count (log scale)")
    ax.set_ylabel("Normalized tzid entropy")
    ax.set_title("TZID Entropy vs Site Count")
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("log10(bbox area km^2)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "6_country_tz_entropy_vs_site_count.png")
    plt.close(fig)


def _plot_7_top1_top2_gap(country_tz: pd.DataFrame, country: pd.DataFrame) -> None:
    sorted_ct = country_tz.sort_values(["legal_country_iso", "site_count"], ascending=[True, False]).copy()
    top2 = (
        sorted_ct.groupby("legal_country_iso", as_index=False)
        .head(2)
        .groupby("legal_country_iso")
        .agg(top1_sites=("site_count", "max"), top2_sites=("site_count", "min"), k=("tzid", "nunique"))
        .reset_index()
    )
    totals = country_tz.groupby("legal_country_iso", as_index=False)["site_count"].sum().rename(columns={"site_count": "country_sites"})
    m = top2.merge(totals, on="legal_country_iso", how="left")
    m["gap_share"] = np.where(m["k"] >= 2, (m["top1_sites"] - m["top2_sites"]) / m["country_sites"], m["top1_sites"] / m["country_sites"])
    m = m.merge(country[["legal_country_iso", "site_count"]], on="legal_country_iso", how="left")
    m = m.sort_values("site_count", ascending=False).head(30).sort_values("gap_share", ascending=True)

    fig, ax = plt.subplots(figsize=(9.0, 8.8))
    sns.barplot(data=m, y="legal_country_iso", x="gap_share", color="#22A884", ax=ax)
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("Top-1 minus Top-2 tzid share")
    ax.set_ylabel("Country (top-30 by site count)")
    ax.set_title("Country TZID Dominance Gap (Top-1 minus Top-2)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "7_country_top1_top2_gap.png")
    plt.close(fig)


def _plot_8_tzid_count_ecdf(country: pd.DataFrame) -> None:
    vals = country["tzid_count"].sort_values().to_numpy()
    y = np.arange(1, len(vals) + 1) / len(vals)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.8))
    bins = np.arange(vals.min(), vals.max() + 2) - 0.5
    ax1.hist(vals, bins=bins, color="#8B5CF6", alpha=0.9)
    ax1.set_xticks(np.arange(vals.min(), vals.max() + 1))
    ax1.set_xlabel("Distinct tzids per country")
    ax1.set_ylabel("Country count")
    ax1.set_title("TZID Count Distribution")

    ax2.step(vals, y, where="post", color="#2563EB", linewidth=2.0)
    ax2.set_xlabel("Distinct tzids per country")
    ax2.set_ylabel("ECDF")
    ax2.set_ylim(0.0, 1.0)
    ax2.set_title("TZID Count ECDF")

    fig.suptitle("Country TZID-Count Diagnostics")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "8_country_tzid_count_ecdf.png")
    plt.close(fig)


def main() -> None:
    _set_theme()
    OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    df = _load()
    country = _country_summary(df)
    country_tz = _country_tz_counts(df)

    _plot_1_bbox_area_vs_count(country)
    _plot_2_tzid_diversity_vs_count(country)
    _plot_3_country_small_multiples(df, country)
    _plot_4_country_tzid_share_matrix(country_tz, country)
    _plot_5_top1_share(country_tz, country)
    _plot_6_entropy_vs_count(country_tz, country)
    _plot_7_top1_top2_gap(country_tz, country)
    _plot_8_tzid_count_ecdf(country)
    print("2A plot refresh complete.")


if __name__ == "__main__":
    main()
