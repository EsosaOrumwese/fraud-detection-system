# Generates realism plots for 1B site_locations and supporting datasets
# Uses headless backend for CLI execution.
import json
from pathlib import Path
import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(r"runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1B")
OUT_DIR = Path(r"reports\eda\segment_1B\plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)
PARAM_HASH = "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7"

plt.style.use("seaborn-v0_8")
plt.rcParams.update({
    "figure.dpi": 140,
    "savefig.dpi": 140,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "legend.frameon": False,
})

# Load core datasets
site_file = next((BASE / "site_locations").rglob("*.parquet"))
s5_file = next((BASE / "s5_site_tile_assignment").rglob("*.parquet"))
s6_file = next((BASE / "s6_site_jitter").rglob("*.parquet"))

site = pl.read_parquet(site_file)
s5 = pl.read_parquet(s5_file)
s6 = pl.read_parquet(s6_file)

# Optional geo
geo_ok = False
geo_note = ""

try:
    import geopandas as gpd
    from shapely.geometry import Point
    from shapely import wkb
    import pyarrow.parquet as pq
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
    geo_ok = True
except Exception as e:
    world = None
    geo_note = f"world_countries load failed: {e}"


# --- Plot 1: Global density heatmap (hexbin)
fig, ax = plt.subplots(figsize=(9.0, 4.8))
if geo_ok:
    world.boundary.plot(ax=ax, linewidth=0.3, color="#6c757d")
ax.hexbin(site["lon_deg"].to_numpy(), site["lat_deg"].to_numpy(), gridsize=80, bins="log", cmap="inferno")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Global Site Density (Hexbin, log count)")
ax.set_xlim(-180, 180)
ax.set_ylim(-60, 85)
fig.tight_layout()
fig.savefig(OUT_DIR / "1_global_density_hexbin.png")
plt.close(fig)

# Note: Area-based comparison plot removed to keep focus strictly on site_locations

# Note: Tile-weight plots intentionally removed per request to focus strictly on site_locations.

# --- Plot 5: Jitter fraction distributions
bounds_root = BASE / "tile_bounds"
bounds_files = list(bounds_root.rglob("*.parquet"))
if bounds_files:
    bounds = pl.scan_parquet([str(f) for f in bounds_files]).select(
        ["country_iso", "tile_id", "min_lat_deg", "max_lat_deg", "min_lon_deg", "max_lon_deg"]
    ).collect()
    sub = s6.join(bounds, left_on=["legal_country_iso", "tile_id"], right_on=["country_iso", "tile_id"], how="left")
    sub = sub.with_columns([
        ((pl.col("max_lat_deg") - pl.col("min_lat_deg")) / 2).alias("half_lat"),
        ((pl.col("max_lon_deg") - pl.col("min_lon_deg")) / 2).alias("half_lon"),
    ]).with_columns([
        (pl.col("delta_lat_deg").abs() / pl.col("half_lat")).alias("lat_frac"),
        (pl.col("delta_lon_deg").abs() / pl.col("half_lon")).alias("lon_frac"),
    ])
    jf = sub.select(["lat_frac", "lon_frac"])
    fig, ax = plt.subplots(1, 2, figsize=(9.6, 4.0))
    ax[0].hist(jf["lat_frac"].to_numpy(), bins=40, color="#e76f51", alpha=0.85)
    ax[1].hist(jf["lon_frac"].to_numpy(), bins=40, color="#2a9d8f", alpha=0.85)
    ax[0].set_title("Jitter Fraction (Lat)")
    ax[1].set_title("Jitter Fraction (Lon)")
    ax[0].set_xlabel("|delta_lat| / half_tile_lat")
    ax[1].set_xlabel("|delta_lon| / half_tile_lon")
    ax[0].set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "5_jitter_fraction_hist.png")
    plt.close(fig)

# --- Plot 6: Point-in-polygon validation (sample)
if geo_ok:
    # sample to keep it light
    sample = site.sample(n=min(5000, site.height), seed=42)
    # build iso -> geometry map
    geom_map = {row["country_iso"]: row.geometry for _, row in world.iterrows()}
    inside = []
    points = []
    for row in sample.iter_rows(named=True):
        geom = geom_map.get(row["legal_country_iso"])
        if geom is None:
            inside.append(False)
        else:
            inside.append(Point(row["lon_deg"], row["lat_deg"]).within(geom))
        points.append((row["lon_deg"], row["lat_deg"]))
    inside = np.array(inside)
    pts = np.array(points)

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    world.boundary.plot(ax=ax, linewidth=0.3, color="#6c757d")
    ax.scatter(pts[inside, 0], pts[inside, 1], s=6, color="#2a9d8f", alpha=0.6, label="inside")
    ax.scatter(pts[~inside, 0], pts[~inside, 1], s=10, color="#e63946", alpha=0.8, label="outside")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 85)
    ax.set_title("Point-in-Polygon Check (sample)")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "6_point_in_polygon.png")
    plt.close(fig)

# --- Plot 7: Latitude distribution by hemisphere
lat = site["lat_deg"].to_numpy()
fig, ax = plt.subplots(figsize=(7.2, 4.5))
ax.hist(lat[lat >= 0], bins=30, alpha=0.8, label="Northern", color="#264653")
ax.hist(lat[lat < 0], bins=30, alpha=0.8, label="Southern", color="#f4a261")
ax.set_xlabel("Latitude")
ax.set_ylabel("Count")
ax.set_title("Latitude Distribution by Hemisphere")
ax.legend()
fig.tight_layout()
fig.savefig(OUT_DIR / "7_latitude_hemispheres.png")
plt.close(fig)

# --- Plot 8: Nearest-neighbor distance distribution (sample)
try:
    # Pure numpy fallback to avoid heavy dependencies
    sample = site.sample(n=min(2000, site.height), seed=42)
    lat = np.radians(sample["lat_deg"].to_numpy())
    lon = np.radians(sample["lon_deg"].to_numpy())
    # Haversine distance matrix (O(n^2) for small sample)
    lat1 = lat[:, None]
    lon1 = lon[:, None]
    dlat = lat1 - lat[None, :]
    dlon = lon1 - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    # set diagonal to inf to ignore self
    np.fill_diagonal(c, np.inf)
    earth_km = 6371.0
    nn_km = np.min(c, axis=1) * earth_km
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    bins = np.logspace(np.log10(max(nn_km.min(), 0.1)), np.log10(nn_km.max()), 40)
    ax.hist(nn_km, bins=bins, color="#1d3557", alpha=0.85)
    ax.set_xscale("log")
    ax.set_xlabel("Nearest neighbor distance (km, log scale)")
    ax.set_ylabel("Count")
    ax.set_title("Nearest-Neighbor Distance Distribution (sample)")
    ax.text(0.98, 0.02, "sample n=2000", transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#6c757d")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "8_nearest_neighbor_dist.png")
    plt.close(fig)
except Exception:
    pass

# --- Plot 9: Country concentration (Lorenz curve)
per_country = site.group_by("legal_country_iso").agg(pl.len().alias("site_count")).sort("site_count")
counts = per_country["site_count"].to_numpy()
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
fig.savefig(OUT_DIR / "9_country_lorenz.png")
plt.close(fig)

# --- Image QC metrics
from matplotlib.image import imread

qc = {}
for img_path in OUT_DIR.glob("*.png"):
    img = imread(img_path)
    # handle RGBA
    rgb = img[..., :3]
    # normalize if integer
    if rgb.dtype != np.float32 and rgb.dtype != np.float64:
        rgb = rgb / 255.0
    brightness = rgb.mean(axis=2)
    qc[str(img_path.name)] = {
        "shape": list(rgb.shape),
        "file_bytes": img_path.stat().st_size,
        "brightness_mean": float(brightness.mean()),
        "brightness_std": float(brightness.std()),
        "nonwhite_ratio": float((brightness < 0.98).mean()),
    }

with open(OUT_DIR / "plot_qc.json", "w", encoding="utf-8") as f:
    json.dump(qc, f, indent=2)

# Save a run note
with open(OUT_DIR / "plot_run_note.json", "w", encoding="utf-8") as f:
    json.dump({"geo_ok": geo_ok, "geo_note": geo_note}, f, indent=2)

print("plots_written", len(list(OUT_DIR.glob("*.png"))))
print("geo_ok", geo_ok, "pop_ok", pop_ok)
