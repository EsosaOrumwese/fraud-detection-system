from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
from matplotlib.ticker import FuncFormatter

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/1B")
OUT_PLOTS = Path("docs/reports/reports/eda/segment_1B/plots")


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


def _fmt_int(x: float, _: int) -> str:
    return f"{int(x):,}"


def _haversine_nn_km(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    lat = np.radians(lat_deg.astype(float))
    lon = np.radians(lon_deg.astype(float))
    lat1 = lat[:, None]
    lon1 = lon[:, None]
    dlat = lat1 - lat[None, :]
    dlon = lon1 - lon[None, :]
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat[None, :]) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(np.clip(1.0 - a, 0.0, 1.0)))
    np.fill_diagonal(c, np.inf)
    return np.min(c, axis=1) * 6371.0


def _load_site_locations() -> pd.DataFrame:
    p_site = next((RUN_ROOT / "site_locations").rglob("*.parquet"))
    return pl.read_parquet(str(p_site)).to_pandas()


def _country_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("legal_country_iso", as_index=False)
        .agg(
            site_count=("site_order", "count"),
            lat_min=("lat_deg", "min"),
            lat_max=("lat_deg", "max"),
            lon_min=("lon_deg", "min"),
            lon_max=("lon_deg", "max"),
        )
        .sort_values("site_count", ascending=False)
        .reset_index(drop=True)
    )
    g["lat_span"] = g["lat_max"] - g["lat_min"]
    g["lon_span"] = g["lon_max"] - g["lon_min"]
    g["mid_lat"] = (g["lat_max"] + g["lat_min"]) / 2.0
    km_per_deg_lat = 111.32
    g["km_per_deg_lon"] = km_per_deg_lat * np.cos(np.deg2rad(g["mid_lat"]).clip(-89.0, 89.0))
    g["bbox_area_km2"] = (
        (g["lat_span"].abs() * km_per_deg_lat) * (g["lon_span"].abs() * g["km_per_deg_lon"].abs())
    ).clip(lower=1e-4)
    g["log10_bbox_area"] = np.log10(g["bbox_area_km2"])
    return g


def _plot_1_choropleth(country: pd.DataFrame) -> None:
    try:
        import geopandas as gpd
        import pyarrow.parquet as pq
        from shapely import wkb
    except Exception:
        return

    geo_path = Path("reference/spatial/world_countries/2024/world_countries.parquet")
    table = pq.read_table(str(geo_path), columns=["country_iso", "name", "geom"])
    geoms = [wkb.loads(b) if b is not None else None for b in table.column("geom").to_pylist()]
    world = gpd.GeoDataFrame(
        {
            "country_iso": table.column("country_iso").to_pylist(),
            "name": table.column("name").to_pylist(),
        },
        geometry=geoms,
        crs="EPSG:4326",
    )

    counts_df = country[["legal_country_iso", "site_count"]].rename(columns={"legal_country_iso": "country_iso"})
    world = world.merge(counts_df, on="country_iso", how="left")
    world["site_count"] = world["site_count"].fillna(0).astype(int)

    world_zero = world[world["site_count"] == 0]
    world_nonzero = world[world["site_count"] > 0].copy()
    world_nonzero["log_sites"] = np.log10(world_nonzero["site_count"])

    fig, ax = plt.subplots(figsize=(13.2, 7.0))
    world_zero.plot(ax=ax, color="#F4F5F7", edgecolor="#D1D5DB", linewidth=0.25)
    cmap = plt.cm.cividis
    world_nonzero.plot(column="log_sites", ax=ax, cmap=cmap, edgecolor="#626C7A", linewidth=0.25)

    ax.set_title("Site Locations: Country-Level Concentration (log10 count)")
    ax.set_axis_off()

    vmin = float(world_nonzero["log_sites"].min())
    vmax = float(world_nonzero["log_sites"].max())
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    ticks = [t for t in [1, 2, 3, 3.5, 4] if vmin <= t <= vmax]
    if ticks:
        cbar.set_ticks(ticks)
        cbar.set_ticklabels([f"{int(round(10**t)):,}" for t in ticks])
    cbar.set_label("Site count (log scale)")

    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "1_country_choropleth.png")
    plt.close(fig)


def _plot_2_lat_lon_hist(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.9))
    lat = df["lat_deg"].to_numpy()
    lon = df["lon_deg"].to_numpy()

    sns.histplot(lat, bins=44, color="#3B556D", edgecolor="white", linewidth=0.35, ax=ax[0])
    ax[0].axvline(np.median(lat), linestyle="--", color="#1F2937", linewidth=1.1)
    ax[0].set_title("Latitude Distribution")
    ax[0].set_xlabel("Latitude")
    ax[0].set_ylabel("Count")
    ax[0].yaxis.set_major_formatter(FuncFormatter(_fmt_int))

    sns.histplot(lon, bins=44, color="#4AA79B", edgecolor="white", linewidth=0.35, ax=ax[1])
    ax[1].axvline(np.median(lon), linestyle="--", color="#1F2937", linewidth=1.1)
    ax[1].set_title("Longitude Distribution")
    ax[1].set_xlabel("Longitude")
    ax[1].set_ylabel("Count")
    ax[1].yaxis.set_major_formatter(FuncFormatter(_fmt_int))

    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "2_lat_lon_hist.png")
    plt.close(fig)


def _plot_3_top20_countries(country: pd.DataFrame) -> None:
    top = country.head(20).copy()
    fig, ax = plt.subplots(figsize=(12.0, 6.5))
    sns.barplot(data=top, x="legal_country_iso", y="site_count", color="#3F7AA6", ax=ax)
    ax.set_title("Top 20 Countries by Site Count")
    ax.set_xlabel("Country")
    ax.set_ylabel("Site count")
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_int))
    for i, v in enumerate(top["site_count"].tolist()):
        ax.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8, color="#374151")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "3_top20_countries.png")
    plt.close(fig)


def _plot_4_country_lorenz(country: pd.DataFrame) -> None:
    counts = np.sort(country["site_count"].to_numpy())
    lorenz_y = np.insert(np.cumsum(counts) / counts.sum(), 0, 0.0)
    lorenz_x = np.insert(np.arange(1, len(counts) + 1) / len(counts), 0, 0.0)
    area = np.trapezoid(lorenz_y, lorenz_x)
    gini = 1.0 - 2.0 * area

    fig, ax = plt.subplots(figsize=(8.1, 7.2))
    ax.plot(lorenz_x, lorenz_y, linewidth=2.4, color="#2A9D8F", label="Lorenz curve")
    ax.plot([0, 1], [0, 1], linestyle="--", color="#9CA3AF", linewidth=1.7, label="Perfect equality")
    ax.set_title(f"Country Concentration (Lorenz Curve, Gini={gini:.3f})")
    ax.set_xlabel("Cumulative share of countries")
    ax.set_ylabel("Cumulative share of sites")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "4_country_lorenz.png")
    plt.close(fig)


def _plot_5_nearest_neighbor(df: pd.DataFrame, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    n = min(2500, len(df))
    idx = rng.choice(len(df), size=n, replace=False)
    sub = df.iloc[idx].copy()
    nn_km = _haversine_nn_km(sub["lat_deg"].to_numpy(), sub["lon_deg"].to_numpy())

    fig, ax = plt.subplots(figsize=(10.2, 6.0))
    bins = np.logspace(np.log10(max(nn_km.min(), 0.06)), np.log10(nn_km.max()), 42)
    ax.hist(nn_km, bins=bins, color="#1F3E5A", alpha=0.9, edgecolor="white", linewidth=0.25)
    ax.set_xscale("log")
    ax.set_xlabel("Nearest neighbor distance (km, log scale)")
    ax.set_ylabel("Count")
    ax.set_title("Nearest-Neighbor Distance (sample n=2,500)")
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_int))

    for p, c in zip(
        [50, 90, 99],
        ["#6B7280", "#F59E0B", "#DC2626"],
    ):
        q = np.percentile(nn_km, p)
        ax.axvline(q, linestyle="--", linewidth=1.2, color=c)
        ax.text(q, ax.get_ylim()[1] * 0.92, f"p{p}={q:.2f} km", rotation=90, ha="right", va="top", fontsize=8, color=c)

    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "5_nearest_neighbor_dist.png")
    plt.close(fig)


def _plot_6_spread_vs_count(country: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.2, 6.8))
    sns.scatterplot(data=country, x="site_count", y="bbox_area_km2", s=72, color="#5A7AA5", alpha=0.9, ax=ax)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Site count (log scale)")
    ax.set_ylabel("BBox area approx (km^2, log scale)")
    ax.set_title("Country Spatial Spread vs Site Count")

    annotate_iso: Iterable[str] = set(
        country.nlargest(3, "bbox_area_km2")["legal_country_iso"].tolist()
        + country.nlargest(3, "site_count")["legal_country_iso"].tolist()
    )
    for _, r in country[country["legal_country_iso"].isin(annotate_iso)].iterrows():
        ax.annotate(
            r["legal_country_iso"],
            (r["site_count"], r["bbox_area_km2"]),
            textcoords="offset points",
            xytext=(4, 3),
            fontsize=9,
            color="#374151",
        )
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "6_country_spread_vs_site_count.png")
    plt.close(fig)


def _plot_7_country_small_multiples(df: pd.DataFrame, country: pd.DataFrame) -> None:
    top_countries = country.head(12)["legal_country_iso"].tolist()
    sub = df[df["legal_country_iso"].isin(top_countries)].copy()

    fig, axes = plt.subplots(3, 4, figsize=(15.3, 10.8))
    axes = axes.flatten()
    for i, iso in enumerate(top_countries):
        ax = axes[i]
        p = sub[sub["legal_country_iso"] == iso]
        ax.scatter(p["lon_deg"], p["lat_deg"], s=10, alpha=0.75, color="#5B84C4", edgecolors="none")
        lat_span = p["lat_deg"].max() - p["lat_deg"].min()
        lon_span = p["lon_deg"].max() - p["lon_deg"].min()
        ax.set_title(f"{iso} n={len(p)}\nDlat={lat_span:.3f} Dlon={lon_span:.3f}", fontsize=9)
        ax.set_xlabel("lon", fontsize=9)
        ax.set_ylabel("lat", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.ticklabel_format(style="plain", useOffset=False, axis="both")

    for j in range(len(top_countries), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Top Countries: Local Site Spread (lat/lon)", fontsize=14, fontweight="semibold")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "7_country_small_multiples.png")
    plt.close(fig)


def _plot_8_concentration_profile(country: pd.DataFrame) -> None:
    counts = country["site_count"].to_numpy()
    sorted_counts = np.sort(counts)[::-1]
    cum_share = np.cumsum(sorted_counts) / sorted_counts.sum()
    rank_pct = np.arange(1, len(sorted_counts) + 1) / len(sorted_counts) * 100.0

    top1 = sorted_counts[: max(1, int(np.ceil(0.01 * len(sorted_counts))))].sum() / sorted_counts.sum()
    top10 = sorted_counts[: max(1, int(np.ceil(0.10 * len(sorted_counts))))].sum() / sorted_counts.sum()

    fig, ax = plt.subplots(1, 2, figsize=(13.5, 5.5))
    ax[0].plot(rank_pct, cum_share, color="#3E6FB5", linewidth=2.5)
    ax[0].axhline(top10, linestyle="--", color="#EF4444", linewidth=1.3)
    ax[0].text(0.02, 0.95, f"top10 share={top10:.2%}", transform=ax[0].transAxes, ha="left", va="top", fontsize=10)
    ax[0].set_xlabel("rank percentile of countries")
    ax[0].set_ylabel("cumulative site share")
    ax[0].set_title("Country Concentration Profile")

    buckets = pd.DataFrame(
        {
            "bucket": ["top1%", "top5%", "top10%"],
            "share": [
                top1,
                sorted_counts[: max(1, int(np.ceil(0.05 * len(sorted_counts))))].sum() / sorted_counts.sum(),
                top10,
            ],
        }
    )
    sns.barplot(data=buckets, x="bucket", y="share", color="#B07AA1", ax=ax[1])
    ax[1].set_ylim(0, 1)
    ax[1].set_xlabel("country bucket")
    ax[1].set_ylabel("site share")
    ax[1].set_title("Top-Country Share of Sites")
    for i, v in enumerate(buckets["share"].tolist()):
        ax[1].text(i, v, f"{v:.2%}", ha="center", va="bottom", fontsize=9, color="#374151")

    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "8_country_concentration_profile.png")
    plt.close(fig)


def _plot_9_nn_by_country(df: pd.DataFrame, country: pd.DataFrame, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    top_countries = country.head(10)["legal_country_iso"].tolist()
    rows: list[dict[str, float | str]] = []

    for iso in top_countries:
        p = df[df["legal_country_iso"] == iso]
        if len(p) < 30:
            continue
        sample_n = min(500, len(p))
        p = p.iloc[rng.choice(len(p), size=sample_n, replace=False)]
        nn_km = _haversine_nn_km(p["lat_deg"].to_numpy(), p["lon_deg"].to_numpy())
        rows.extend([{"iso": iso, "nn_km": float(v)} for v in nn_km if np.isfinite(v) and v > 0])

    if not rows:
        return

    d = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(10.8, 6.5))
    sns.boxplot(data=d, x="iso", y="nn_km", color="#6B8CC2", showfliers=False, ax=ax)
    ax.set_yscale("log")
    ax.set_xlabel("Country (top-10 by site count)")
    ax.set_ylabel("Nearest-neighbor distance (km, log scale)")
    ax.set_title("Within-Country Nearest-Neighbor Distance (sampled)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "9_nn_by_country_boxplot.png")
    plt.close(fig)


def main() -> None:
    OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    _set_theme()
    df = _load_site_locations()
    country = _country_summary(df)

    _plot_1_choropleth(country)
    _plot_2_lat_lon_hist(df)
    _plot_3_top20_countries(country)
    _plot_4_country_lorenz(country)
    _plot_5_nearest_neighbor(df)
    _plot_6_spread_vs_count(country)
    _plot_7_country_small_multiples(df, country)
    _plot_8_concentration_profile(country)
    _plot_9_nn_by_country(df, country)

    print("plots_written")
    for p in sorted(OUT_PLOTS.glob("*.png")):
        print(p.name)


if __name__ == "__main__":
    main()
