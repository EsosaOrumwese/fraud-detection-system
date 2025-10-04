# Building `population_raster_2025`
Below is a practical, reproducible plan for turning raw population data into the **ingestion‑ready `population_raster_2025`** your engine expects.  It incorporates the constrained country universe (≈69 ISO‑2 codes) and adheres to the schema requirements (Cloud‑Optimized GeoTIFF, EPSG4326, one float‑32 band, nodata –1.0, overviews [2,4,8,16]).

---

## 1. Choose the raw source

Two main open sources exist:

1. **WorldPop 2025 population counts** – per‑country GeoTIFFs at 3 arc‑second (~100m) resolution, WGS84, pixel values are the number of people per cell.  Requires mosaicking dozens of files. [1](https://hub.worldpop.org/geodata/summary#:~:text=Estimates%20of%202025%2C%20total%20number,in%20the%20%2021%20Release)
2. **GHS‑POP R2023A (epoch 2025)** – global grids derived from CIESIN GPWv4 and built‑up area maps.  Available at 3 arc‑second (“3ss”) and 30 arc‑second (“30ss”) resolutions in EPSG 4326, with data broken into **tiles** accessible via simple HTTP.  Pixel values are floats representing the number of people per cell. [2](https://data.jrc.ec.europa.eu/dataset/2ff68a52-5b5b-4a22-8f40-c41da8332cfe#:~:text=Description)[,3](https://data.jrc.ec.europa.eu/dataset/2ff68a52-5b5b-4a22-8f40-c41da8332cfe#:~:text=,seconds.%20The%20compressed)

For reproducibility and simplicity, this plan uses **GHS‑POP 2025** (3ss tiles).  It provides global coverage in the required projection, can be downloaded tile‑by‑tile, and avoids per‑country mosaic complexity.  If storage is constrained, the 30ss tiles (1km resolution) are a fallback.

---

## 2. Identify required tiles

1. **Compile the country universe:** read the ISO‑2 codes from `ccy_country_shares_2024Q4.csv` and build a list of target countries (e.g., 69 codes).
2. **Get country bounding boxes:** use your `world_countries.parquet` (or another geotable) to extract the lat/lon extent of each target country.
3. **Tile index layout:** GHS‑POP tiles are named `R<row>_C<col>` (row1 = north, column1 = west).  Each tile covers 10° × 10° at 3 arc‑second resolution.  Use simple arithmetic to map country bounding boxes to tile row/column ranges:

   * `col_start = floor((lon_min + 180) / 10) + 1`
   * `col_end   = floor((lon_max + 180) / 10) + 1`
   * `row_start = floor((90 – lat_max) / 10) + 1`
   * `row_end   = floor((90 – lat_min) / 10) + 1`
4. **Produce a unique list of tiles** that intersect any target country.  Expect dozens, not hundreds, for 69 countries.

---

## 3. Download and unpack tiles

The files live at:

```
http://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles/R<row>_C<col>.zip
```

1. **Loop over the tile list** and download each ZIP with `wget` or `curl`.  For example:

   ```bash
   wget -O R1_C8.zip \
     http://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles/R1_C8.zip
   ```
2. **Unzip** each file.  Each ZIP contains a GeoTIFF named `GHS_POP_E2025_GLOBE_R2023A_4326_3ss_R<row>_C<col>.tif`.

Keep a manifest of downloaded files (tile name, URL, SHA‑256 checksum).

---

## 4. Mosaic and clip

Because the engine only needs the population raster over the target countries:

1. **Merge the tiles** using GDAL:

   ```bash
   gdal_merge.py -o merged_raw.tif -n -9999 -a_nodata -9999 \
     $(ls GHS_POP_E2025_GLOBE_R2023A_4326_3ss_R*_C*.tif)
   ```

   This creates a temporary mosaic (`merged_raw.tif`) in EPSG4326.  The GHS‑POP nodata is usually 0 or –9999; we will replace it later.
2. **Clip to the union of target country extents** (optional) to reduce size:

   * Build a shapefile/GeoJSON of the target country polygons.
   * Use `gdalwarp` to clip:

     ```bash
     gdalwarp -cutline target_countries.shp -crop_to_cutline \
       -dstnodata -9999 merged_raw.tif merged_clipped.tif
     ```

---

## 5. Convert to float‑32 and set nodata

Ensure the pixel values are float‐32 and set the engine’s nodata value to **–1.0**:

```bash
gdal_translate -of GTiff -a_nodata -1 \
  -ot Float32 merged_clipped.tif merged_float.tif
```

This command writes a new TIFF with float‑32 data type and nodata = –1.

---

## 6. Build overviews (2, 4, 8, 16)

Overviews must be built before creating a COG:

```bash
gdaladdo -r average merged_float.tif 2 4 8 16
```

The `-r average` resampling matches the spec for population densities.

---

## 7. Produce a Cloud‑Optimized GeoTIFF

Finally, create the ingestion‑ready COG:

```bash
gdal_translate merged_float.tif population.tif \
  -co COMPRESS=LZW \
  -co TILED=YES \
  -co BLOCKXSIZE=512 \
  -co BLOCKYSIZE=512 \
  -co COPY_SRC_OVERVIEWS=YES
```

* `population.tif` is the final file.
* Ensure the band count is 1, dtype is Float32, nodata is –1, pixel unit can be documented in metadata (`-mo UNIT=persons` if desired).

---

## 8. Verify and register

1. **Check schema:** use `gdalinfo population.tif` to confirm:

   * Driver is `GTiff/COG`.
   * Size in pixels and degrees matches expectations.
   * `NoData Value=-1`.
   * Overview levels 2,4,8,16 are present.
2. **Record provenance:**

   * Source tile list + checksums.
   * GDAL versions used.
   * SHA‑256 of the final `population.tif`.
3. **Place the file** in the engine’s canonical path `reference/spatial/population/2025/population.tif` and update the artefact registry/dictionary entries accordingly.

---

## Notes and alternatives

* **Resolution choice:** 3 arc‑second (~100m) matches the engine’s other spatial priors (HRSL).  For a lighter file, use the 30 arc‑second tiles; the same workflow applies.
* **WorldPop** alternative: download per‑country GeoTIFFs from WorldPop, mosaic them via `gdal_merge`, and follow the same steps (dtype cast, nodata, overviews, COG).  Ensure the Random‑Forest counts align with UN totals.
* **Small countries:** if a target country has no coverage in GHS‑POP (rare), fallback to HRSL or WorldPop for that area, but ensure the final mosaic still meets the single‑band, float32, EPSG 4326 COG spec.

By following this plan, you can reproduce a **population_raster_2025** dataset that satisfies the engine’s ingestion contract: a single Cloud‑Optimized GeoTIFF in WGS 84 with float‑32 counts and proper overviews.

## Code

Below is an **inline script** (split into Python and GDAL parts) that you can adapt to build the `population_raster_2025` dataset in your own environment.  It implements the plan I described: selecting only the tiles that intersect your country universe, mosaicking them, casting to float‑32 with nodata = –1.0, and producing a Cloud‑Optimized GeoTIFF with overviews.  You will need `geopandas`, `rasterio` and GDAL (`gdal_merge.py`, `gdalwarp`, `gdaladdo`, `gdal_translate`) installed.

---

### 1. Python script `build_population_raster.py`

```python
#!/usr/bin/env python3
import os, math, io, zipfile, requests
import geopandas as gpd
import rasterio
from rasterio.merge import merge
import rasterio.mask

def compute_tile_indices(lon_min, lat_min, lon_max, lat_max):
    """
    Convert a lat/lon bounding box to GHS‑POP tile row/column ranges.
    Each tile covers 10° × 10°, with columns numbered from 1 at −180°
    and rows numbered from 1 at +90° downwards.
    """
    col_start = math.floor((lon_min + 180) / 10.0) + 1
    col_end   = math.floor((lon_max + 180) / 10.0) + 1
    row_start = math.floor((90 - lat_max) / 10.0) + 1
    row_end   = math.floor((90 - lat_min) / 10.0) + 1
    return range(row_start, row_end + 1), range(col_start, col_end + 1)

def main():
    # ---- User‑defined inputs ----
    iso_list_path      = "target_iso2_universe.txt"      # one ISO‑2 code per line
    world_countries    = "world_countries.parquet"       # your geotable of country polygons
    tiles_url_root     = ("http://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/"
                          "GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2025_GLOBE_R2023A_4326_3ss/V1-0/tiles")
    tiles_dir          = "downloaded_tiles"              # will be created
    intermediate_tif   = "population_raw.tif"
    clipped_tif        = "population_clipped.tif"
    # ----------------------------

    os.makedirs(tiles_dir, exist_ok=True)

    # 1) Read ISO codes and country polygons
    with open(iso_list_path, "r", encoding="utf-8") as f:
        target_iso = {line.strip().upper() for line in f if line.strip()}
    countries = gpd.read_file(world_countries)
    target_countries = countries[countries["country_iso"].isin(target_iso)]

    # 2) Determine which 10°×10° tiles intersect the combined extent
    minx, miny, maxx, maxy = target_countries.total_bounds
    row_range, col_range = compute_tile_indices(minx, miny, maxx, maxy)

    tile_files = []
    print(f"Fetching tiles for rows {row_range} and cols {col_range} ...")
    for r in row_range:
        for c in col_range:
            tile_name = f"R{r}_C{c}"
            url = f"{tiles_url_root}/{tile_name}.zip"
            print(f"  downloading {tile_name} …")
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                tif_name = [n for n in zf.namelist() if n.lower().endswith(".tif")][0]
                out_fp = os.path.join(tiles_dir, tif_name)
                with open(out_fp, "wb") as fout:
                    fout.write(zf.read(tif_name))
                tile_files.append(out_fp)

    # 3) Mosaic tiles in memory using rasterio
    print(f"Merging {len(tile_files)} tiles …")
    datasets = [rasterio.open(fp) for fp in tile_files]
    mosaic, out_transform = merge(datasets)
    # Cast to float32 and set nodata to −1.0
    mosaic = mosaic.astype("float32")
    # GHS‑POP uses 0 or −9999 for nodata; set values ≤0 to −1
    mosaic[mosaic <= 0] = -1

    out_meta = datasets[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform,
        "dtype": "float32",
        "nodata": -1.0,
        "count": 1,
        "crs": "EPSG:4326"
    })

    with rasterio.open(intermediate_tif, "w", **out_meta) as dest:
        dest.write(mosaic)

    # 4) Clip to the union of target countries to shrink file size (optional but recommended)
    mask_geom = [target_countries.unary_union]
    with rasterio.open(intermediate_tif) as src:
        out_image, out_transform = rasterio.mask.mask(src, mask_geom, crop=True, filled=True, nodata=-1.0)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })
        with rasterio.open(clipped_tif, "w", **out_meta) as dest:
            dest.write(out_image)

    print("Finished writing", clipped_tif)
    print("Next steps: build overviews and convert to COG with GDAL.")

if __name__ == "__main__":
    main()
```

1. Save the above as `build_population_raster.py`.
2. Prepare a text file `target_iso2_universe.txt` with one ISO‑2 code per line (your 69 countries).
3. Ensure you have `world_countries.parquet` from your earlier work.
4. Run:

```bash
python3 build_population_raster.py
```

This writes two TIFFs: `population_raw.tif` and `population_clipped.tif`.  Use the clipped version.

---

### 2. Build overviews and create the COG

Once the script finishes:

```bash
# build 2×, 4×, 8×, 16× overviews (average resampling)
gdaladdo -r average population_clipped.tif 2 4 8 16

# convert to a Cloud‑Optimized GeoTIFF with LZW compression and tiling
gdal_translate population_clipped.tif \
  reference/spatial/population/2025/population.tif \
  -co COMPRESS=LZW -co TILED=YES -co BLOCKXSIZE=512 -co BLOCKYSIZE=512 \
  -co COPY_SRC_OVERVIEWS=YES -a_nodata -1
```

* After running these commands, your final file is `reference/spatial/population/2025/population.tif`.
* Verify with `gdalinfo` that it has one float‑32 band, `NoData Value=-1`, EPSG 4326 CRS, and overviews at 2, 4, 8 and 16.

This script and GDAL commands will take you from raw population tiles to the ingestion‑ready COG that the engine expects.
