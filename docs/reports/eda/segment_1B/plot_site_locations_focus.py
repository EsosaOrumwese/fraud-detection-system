# Focused realism plots for site_locations only (no tile/policy inputs)
import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(r"runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1B")
OUT_DIR = Path(r"reports\eda\segment_1B\plots_focus")
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8")
plt.rcParams.update({
    "figure.dpi": 140,
    "savefig.dpi": 140,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "legend.frameon": False,
})

site_file = next((BASE / "site_locations").rglob("*.parquet"))
site = pl.read_parquet(site_file)

lon = site["lon_deg"].to_numpy()
lat = site["lat_deg"].to_numpy()

# 1) Country-level choropleth (counts per country)
try:
    import geopandas as gpd
    import pyarrow.parquet as pq
    from shapely import wkb

    geo_path = Path(r"reference\spatial\world_countries\2024\world_countries.parquet")
    table = pq.read_table(geo_path, columns=["country_iso", "name", "geom"])
    geoms = [wkb.loads(b) if b is not None else None for b in table.column("geom").to_pylist()]
    world = gpd.GeoDataFrame(
        {
            "country_iso": table.column("country_iso").to_pylist(),
            "name": table.column("name").to_pylist(),
        },
        geometry=geoms,
        crs="EPSG:4326",
    )

    per_country = site.group_by("legal_country_iso").agg(pl.len().alias("site_count"))
    counts_df = per_country.rename({"legal_country_iso": "country_iso"}).to_pandas()
    world = world.merge(counts_df, on="country_iso", how="left")
    world["site_count"] = world["site_count"].fillna(0).astype(int)

    # Split zero vs nonzero so 0 can be light/white
    world_zero = world[world["site_count"] == 0]
    world_nonzero = world[world["site_count"] > 0].copy()
    world_nonzero["log_sites"] = np.log10(world_nonzero["site_count"])

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    # base: zero-count countries in light gray/white
    world_zero.plot(ax=ax, color="#f2f2f2", edgecolor="#c0c0c0", linewidth=0.2)
    # nonzero: sequential colormap with monotonic brightness
    cmap = plt.cm.cividis
    world_nonzero.plot(column="log_sites", ax=ax, cmap=cmap, linewidth=0.2, edgecolor="#5c677d")

    ax.set_title("Site Locations: Country-Level Concentration (log10 count)")
    ax.set_axis_off()

    # colorbar with human-friendly ticks
    vmin = world_nonzero["log_sites"].min()
    vmax = world_nonzero["log_sites"].max()
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin, vmax))
    sm._A = []
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    # choose sensible tick marks
    ticks = [t for t in [0, 1, 2, 3, 3.5, 4] if vmin <= t <= vmax]
    if ticks:
        cbar.set_ticks(ticks)
        cbar.set_ticklabels([f"{int(round(10**t)):,}" for t in ticks])
    cbar.set_label("Site count (log scale)")

    fig.tight_layout()
    fig.savefig(OUT_DIR / "1_country_choropleth.png")
    plt.close(fig)
except Exception:
    pass

# 2) Latitude & Longitude distributions
fig, ax = plt.subplots(1, 2, figsize=(9.2, 4.0))
ax[0].hist(lat, bins=40, color="#264653", alpha=0.85)
ax[0].set_title("Latitude Distribution")
ax[0].set_xlabel("Latitude")
ax[0].set_ylabel("Count")
ax[1].hist(lon, bins=40, color="#2a9d8f", alpha=0.85)
ax[1].set_title("Longitude Distribution")
ax[1].set_xlabel("Longitude")
ax[1].set_ylabel("Count")
fig.tight_layout()
fig.savefig(OUT_DIR / "2_lat_lon_hist.png")
plt.close(fig)

# 3) Country concentration (Top 20 bar)
per_country = site.group_by("legal_country_iso").agg(pl.len().alias("site_count")).sort("site_count", descending=True)
top = per_country.head(20)
fig, ax = plt.subplots(figsize=(8.6, 4.6))
ax.bar(top["legal_country_iso"].to_list(), top["site_count"].to_list(), color="#457b9d")
ax.set_title("Top 20 Countries by Site Count")
ax.set_xlabel("Country")
ax.set_ylabel("Site count")
ax.tick_params(axis="x", rotation=45, labelsize=8)
fig.tight_layout()
fig.savefig(OUT_DIR / "3_top20_countries.png")
plt.close(fig)

# 4) Country concentration (Lorenz curve)
counts = per_country["site_count"].to_numpy()
counts = np.sort(counts)
lorenz_y = np.insert(np.cumsum(counts) / np.sum(counts), 0, 0)
lorenz_x = np.insert(np.arange(1, len(counts) + 1) / len(counts), 0, 0)
fig, ax = plt.subplots(figsize=(6.5, 6.0))
ax.plot(lorenz_x, lorenz_y, color="#2a9d8f", linewidth=2.0, label="Lorenz curve")
ax.plot([0, 1], [0, 1], color="#bcb8b1", linestyle="--", label="Perfect equality")
ax.set_xlabel("Cumulative share of countries")
ax.set_ylabel("Cumulative share of sites")
ax.set_title("Country Concentration (Lorenz Curve)")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(OUT_DIR / "4_country_lorenz.png")
plt.close(fig)

# 5) Nearest-neighbor distance distribution (sample, log x-axis)
# Use a 2k sample to keep runtime/memory low
sample = site.sample(n=min(2000, site.height), seed=42)
lat_s = np.radians(sample["lat_deg"].to_numpy())
lon_s = np.radians(sample["lon_deg"].to_numpy())
lat1 = lat_s[:, None]
lon1 = lon_s[:, None]
dlat = lat1 - lat_s[None, :]
dlon = lon1 - lon_s[None, :]
a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat_s[None, :]) * np.sin(dlon / 2) ** 2
c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
np.fill_diagonal(c, np.inf)
km = c.min(axis=1) * 6371.0

fig, ax = plt.subplots(figsize=(7.2, 4.5))
bins = np.logspace(np.log10(max(km.min(), 0.1)), np.log10(km.max()), 40)
ax.hist(km, bins=bins, color="#1d3557", alpha=0.85)
ax.set_xscale("log")
ax.set_xlabel("Nearest neighbor distance (km, log scale)")
ax.set_ylabel("Count")
ax.set_title("Nearest-Neighbor Distance (sample n=2000)")
fig.tight_layout()
fig.savefig(OUT_DIR / "5_nearest_neighbor_dist.png")
plt.close(fig)

print("plots_written", len(list(OUT_DIR.glob("*.png"))))
