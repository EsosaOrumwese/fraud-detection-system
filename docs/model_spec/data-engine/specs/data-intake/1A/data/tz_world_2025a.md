# Building `tz_world_2025a`

Here’s a **practical, reproducible plan** to move from the raw time‑zone polygons to the refined `tz_world_2025a` dataset your engine requires.  Follow these steps exactly; they mirror how I built the final artefact.

---

## 1. Locate and download the raw data

1. **Find the 2025a release on the timezone‑boundary‑builder project**.  The official source for tz polygons is the `timezone‑boundary‑builder` GitHub repository.  Their 2025a release contains a file called **`timezones-with-oceans.geojson.zip`**.  The project is recommended by the timezonefinder library, and the BigQuery mirror confirms version `2025a` includes tables named `timezones-with-oceans` and `timezones`.
2. **Download the zip file directly**.  Use a direct download URL of the form:

   ```
   https://github.com/evansiroky/timezone-boundary-builder/releases/download/2025a/timezones-with-oceans.geojson.zip
   ```

   (Use `wget` or `curl` in a terminal to avoid the GitHub web UI.)
3. **Record provenance**: note the URL, timestamp, and compute a SHA‑256 checksum of the downloaded zip.  Example:

   ```bash
   sha256sum timezones-with-oceans.geojson.zip > tz_world_2025a.sha256
   ```

---

## 2. Extract and inspect the raw GeoJSON

1. **Unzip the archive**:

   ```bash
   unzip timezones-with-oceans.geojson.zip -d tz_raw
   ```

   This yields a file named `combined-with-oceans.json`.
2. **Inspect the file**.  It is a **GeoJSON FeatureCollection** of ~443 features, each with `properties.tzid` and either a `Polygon` or `MultiPolygon` geometry.  Verify that the GeoJSON uses WGS‑84 (EPSG4326) coordinates.

---

## Pipeline: Python + GeoPandas → **GeoParquet**

### A.1. Environment

```bash
# Python 3.10+ recommended
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip

# Versions that write proper GeoParquet metadata
pip install "geopandas>=0.13" "pyarrow>=14" "shapely>=2.0" fiona
```

### A.2. Fetch & verify the raw release asset

```bash
# 2025a time zone polygons with oceans (GeoJSON)
wget -O timezones-with-oceans.geojson.zip \
  https://github.com/evansiroky/timezone-boundary-builder/releases/download/2025a/timezones-with-oceans.geojson.zip
sha256sum timezones-with-oceans.geojson.zip > tz_world_2025a.sha256

unzip -d tz_raw timezones-with-oceans.geojson.zip   # -> tz_raw/combined-with-oceans.json
```

(The timezone-boundary-builder project is the canonical OSM-derived source for TZ polygons, and is the data used by timezonefinder; see its release/mirror notes.) 

### A.3. Build script (explode MultiPolygons, enumerate `polygon_id`, write **GeoParquet**)

Save as `build_tz_world_geoparquet.py`:

```python
import argparse, json, hashlib, sys
import geopandas as gpd
import pandas as pd

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

ap = argparse.ArgumentParser()
ap.add_argument("--in-json",  required=True)   # tz_raw/combined-with-oceans.json
ap.add_argument("--out-parquet", required=True) # reference/spatial/tz_world/2025a/tz_world.parquet
ap.add_argument("--round-decimals", type=int, default=6) # optional: reduce size
ap.add_argument("--tzdb-release", default="2025a", help="IANA TZDB release tag used to build this artefact (default 2025a)")
ap.add_argument("--source-url", default="", help="(optional) provenance URL for the downloaded release asset")
args = ap.parse_args()

# 1) Read GeoJSON as GeoDataFrame (WGS84)
gdf = gpd.read_file(args.in_json)
gdf = gdf.set_crs(4326, allow_override=True)

# 2) Keep only needed column and geometry
assert "tzid" in gdf.columns or "TZID" in gdf.columns, "tzid column missing"
gdf["tzid"] = gdf["tzid"] if "tzid" in gdf.columns else gdf["TZID"]
gdf = gdf[["tzid", "geometry"]]

# 3) Explode MultiPolygons into individual polygons
gdf = gdf.explode(index_parts=False, ignore_index=True)

# 4) Optional: round coordinates safely (via Shapely WKB rounding_precision)
from shapely import wkb as _wkb
if args.round_decimals is not None:
    def _round_geom(geom, nd=args.round_decimals):
        if geom is None or geom.is_empty:
            return geom
        # WKB round-trip with rounding_precision preserves topology and types
        return _wkb.loads(_wkb.dumps(geom, rounding_precision=nd))
    gdf["geometry"] = gdf["geometry"].apply(_round_geom)
# NOTE: rounding is optional; skip with --round-decimals omitted if you prefer source precision.

# 5) Assign polygon_id per tzid (1..N)
gdf["polygon_id"] = gdf.groupby("tzid").cumcount() + 1

# 6) Rename geometry column to 'geom' to match schema; keep it as active geometry
gdf = gdf.rename_geometry("geom")    # geopandas >= 0.13
# or: gdf = gdf.rename(columns={"geometry":"geom"}).set_geometry("geom")

# 7) Order columns and write GeoParquet (with GeoParquet metadata)
out_cols = ["tzid", "polygon_id", "geom"]
gdf["tzid"] = gdf["tzid"].astype("string")
gdf = gdf[out_cols].sort_values(["tzid","polygon_id"], kind="mergesort").reset_index(drop=True)
gdf.to_parquet(args.out_parquet, index=False)

meta = {
    "dataset_id": "tz_world_2025a",
    "tzdb_release": args.tzdb_release,
    "in_json": args.in_json,
    "in_sha256": sha256_of(args.in_json),
    "out_parquet": args.out_parquet,
    "source_url": args.source_url or None
}
print(meta)
from pathlib import Path as _Path
man_path = _Path(args.out_parquet).with_name("_manifest.json")
with open(man_path, "w", encoding="utf-8") as _mf:
    json.dump(meta, _mf, indent=2)
```

Run it:

```bash
python build_tz_world_geoparquet.py \
  --in-json tz_raw/combined-with-oceans.json \
  --out-parquet reference/spatial/tz_world/2025a/tz_world.parquet \
  --round-decimals 6
```

### A.4. Validation (binds to your schema)

```python
import geopandas as gpd
g = gpd.read_parquet("reference/spatial/tz_world/2025a/tz_world.parquet")

# CRS exactly EPSG:4326
assert g.crs and int(g.crs.to_epsg()) == 4326

# Columns and types
assert list(g.columns) == ["tzid","polygon_id","geom"]
assert g.geom_type.isin(["Polygon","MultiPolygon"]).all()

# PK uniqueness: (tzid, polygon_id)
assert not g.duplicated(["tzid","polygon_id"]).any()

# tzid domain looks like IANA TZIDs
import re
pat = re.compile(r"^[A-Za-z0-9_\+\-./]+$")
assert g["tzid"].apply(lambda s: bool(pat.fullmatch(str(s)))).all()
# deterministic order (nice for diffs)
g = g.sort_values(["tzid","polygon_id"], kind="mergesort").reset_index(drop=True)
```

That produces the **GeoParquet** exactly as your dictionary + schema require (format **parquet**, geometry column **`geom`**, CRS **EPSG:4326**, PK `["tzid","polygon_id"]`).  

---

## Final check before sealing the artefact

* Schema pass against `#/tz_world_shp` (alias to `#/tz_world_2025a`). 
* PK uniqueness (`tzid, polygon_id`) and CRS = EPSG:4326. 
* Update the registry/dictionary entries only if paths change; otherwise you’re aligned with **GeoParquet**. 

If you want, I can now run the **GeoParquet build** from your uploaded GeoJSON and drop the file into the exact path the dictionary expects.

